from __future__ import annotations

import asyncio
import html
import json
import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from .agent import AgentService
from .company_research import CompanyResearchTool
from .config import DEFAULT_CORS_ORIGIN_REGEX, PROJECT_ROOT, Settings
from .knowledge import KnowledgeRepository
from .llm import DeepSeekLLM, MockLLM
from .pdf_report import build_assessment_pdf
from .repository import AssessmentRepository
from .retrieval import HybridRetrievalProvider
from .schemas import (
    Assessment,
    AssessmentRequest,
    ChatRequest,
    CompanyInput,
    RetrievalQuery,
    ScenarioUpdateRequest,
)
from .web_search import WebSearchTool


settings = Settings.from_env()
repository = AssessmentRepository(settings.database_path)
knowledge_repository = KnowledgeRepository(settings.database_path)
retrieval = HybridRetrievalProvider(
    repository=knowledge_repository,
    web_search=WebSearchTool(enabled=settings.web_search_enabled),
)

if settings.llm_provider == "deepseek":
    if not settings.deepseek_api_key:
        raise RuntimeError(
            "LLM_PROVIDER=deepseek but DEEPSEEK_API_KEY is missing. "
            "Configure backend/.env or set LLM_PROVIDER=mock explicitly."
        )
    llm = DeepSeekLLM(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
elif settings.llm_provider == "mock":
    if settings.llm_required:
        raise RuntimeError(
            "LLM_REQUIRED=true but LLM_PROVIDER=mock. "
            "Configure DeepSeek or set LLM_REQUIRED=false explicitly."
        )
    llm = MockLLM()
else:
    raise RuntimeError(
        f"Unsupported LLM_PROVIDER={settings.llm_provider!r}. "
        "Use 'deepseek' or 'mock'."
    )

agent = AgentService(
    retrieval=retrieval,
    llm=llm,
    company_research=CompanyResearchTool(),
)
frontend_dir = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="Geopolitical Supply Chain Decision Agent",
    version="0.1.0",
    description="Evidence-based China+1 relocation assessment MVP.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# The frontend lives on its own branch, so the backend must also run without it.
if frontend_dir.is_dir():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/", include_in_schema=False, response_model=None)
def index() -> FileResponse | JSONResponse:
    index_file = frontend_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return JSONResponse(
        {
            "service": "Geopolitical Supply Chain Decision Agent",
            "frontend": "not bundled on this branch",
            "docs": "/docs",
            "health": "/health",
        }
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm_provider": llm.mode,
        "model": getattr(llm, "model", "mock"),
    }


@app.get("/api/v1/meta")
def meta() -> dict[str, object]:
    knowledge_stats = knowledge_repository.stats()
    return {
        "app_env": settings.app_env,
        "llm_provider": llm.mode,
        "retrieval_provider": (
            "hybrid+web" if settings.web_search_enabled else "hybrid"
        )
        if knowledge_stats["ready"]
        else "mock",
        "data_mode": "hybrid" if knowledge_stats["ready"] else "mock",
        "knowledge": knowledge_stats,
        "available_models": [
            {
                "id": "deepseek-flash",
                "name": "DeepSeek Flash",
                "description": "速度更快，适合常规分析和快速迭代。",
            },
            {
                "id": "deepseek-v4-pro",
                "name": "DeepSeek V4 Pro",
                "description": "深度思考更强，会展示更多推理过程。",
            },
        ],
        "contract_version": "1.0",
        "deepseek_configured": bool(settings.deepseek_api_key),
        "llm_configured": llm.mode == "deepseek" and bool(settings.deepseek_api_key),
        "llm_required": settings.llm_required,
        "supported_languages": ["en", "zh"],
        "cors_origins": list(settings.cors_origins),
        "cors_origin_regex": settings.cors_origin_regex,
        # The backend-owned key is sufficient. The browser key is only optional
        # when no server key is configured.
        "api_key_required": not bool(settings.deepseek_api_key),
    }


@app.get("/api/v1/evidence")
def evidence_lookup(
    query: str = Query(min_length=2, max_length=500),
    industry: str = "battery_ev",
    country: str = "CN",
    market: str = "US",
    limit: int = Query(default=10, ge=1, le=50),
):
    retrieval_query = RetrievalQuery(
        industry=industry,
        products=[query],
        home_country=country,
        production_countries=["VN"],
        target_markets=[market],
        decision_question=query,
        restrictions=[],
        limit=limit,
    )
    return {"items": retrieval.search(retrieval_query)}


@app.get("/api/v1/knowledge/stats")
def knowledge_stats() -> dict[str, int | bool]:
    return knowledge_repository.stats()


def _resolve_document_path(document_path: str | None) -> Path | None:
    """Resolve a stored document path to a file on disk (data branch layout)."""
    if not document_path:
        return None
    candidates = []
    raw = Path(document_path)
    candidates.append(raw if raw.is_absolute() else PROJECT_ROOT / raw)
    candidates.append(settings.data_root / raw.name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    # Fall back to a filename search under the data root.
    if settings.data_root.is_dir() and raw.name:
        for found in settings.data_root.rglob(raw.name):
            if found.is_file():
                return found
    return None


@app.get("/api/v1/evidence/{evidence_id}/document")
def evidence_document(evidence_id: str):
    """Serve the original document behind one evidence item.

    Local files (data branch) are streamed; web-only evidence redirects to the
    source URL so the frontend can always open something.
    """
    source_id = ""
    if evidence_id.startswith("EVD-"):
        chunk_id = evidence_id[4:]
        source_id = chunk_id.split("-C")[0] if "-C" in chunk_id else chunk_id

    source = knowledge_repository.document_source(source_id) if source_id else None

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No stored document for this evidence item. Web-search evidence is "
                "served from its original URL in the evidence `url` field."
            ),
        )

    local_file = _resolve_document_path(source.get("document_path"))
    if local_file:
        media_type = mimetypes.guess_type(str(local_file))[0] or "application/octet-stream"
        return FileResponse(local_file, media_type=media_type, filename=local_file.name)

    url = source.get("url")
    if url:
        return RedirectResponse(url, status_code=307)

    raise HTTPException(
        status_code=404,
        detail="This evidence item has no local document and no source URL.",
    )


@app.post("/api/v1/assessments/{assessment_id}/scenarios", response_model=Assessment)
def update_scenarios(
    assessment_id: str, request: ScenarioUpdateRequest
) -> Assessment:
    """Re-run the scenario stage with constraints gathered during consultation."""
    assessment = repository.get(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    try:
        updated = agent.resimulate(
            assessment,
            additional_constraints=request.additional_constraints,
            api_key=request.api_key,
            model_name=request.llm_model,
            language=request.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repository.save(updated)
    return updated


@app.post("/api/v1/assessments", response_model=Assessment)
def create_assessment(request: AssessmentRequest) -> Assessment:
    try:
        assessment = agent.run(
            request.company,
            api_key=request.api_key,
            model_name=request.llm_model,
            language=request.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repository.save(assessment)
    return assessment


@app.post("/api/v1/assessments/stream")
async def create_assessment_stream(request: AssessmentRequest) -> StreamingResponse:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict] = asyncio.Queue()

    def event_callback(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def run_job() -> None:
        try:
            assessment = await asyncio.to_thread(
                agent.run,
                request.company,
                request.api_key,
                request.llm_model,
                event_callback,
                request.language,
            )
            repository.save(assessment)
            await queue.put(
                {
                    "type": "assessment",
                    "assessment": assessment.model_dump(mode="json"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            await queue.put(
                {
                    "type": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )
        finally:
            await queue.put({"type": "done"})

    async def event_stream():
        task = asyncio.create_task(run_job())
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event, ensure_ascii=False) + "\n"
                if event["type"] == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.get("/api/v1/assessments/{assessment_id}", response_model=Assessment)
def get_assessment(assessment_id: str) -> Assessment:
    assessment = repository.get(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    return assessment


@app.post("/api/v1/assessments/{assessment_id}/chat", response_model=Assessment)
def chat(assessment_id: str, request: ChatRequest) -> Assessment:
    assessment = repository.get(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    try:
        updated = agent.chat(assessment, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    repository.save(updated)
    return updated


@app.get("/api/v1/assessments/{assessment_id}/report")
def report(assessment_id: str) -> StreamingResponse:
    assessment = repository.get(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    pdf_bytes = build_assessment_pdf(assessment)
    filename = f"{assessment.assessment_id}-decision-report.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.get(
    "/api/v1/assessments/{assessment_id}/report/html",
    response_class=HTMLResponse,
)
def report_html(assessment_id: str) -> HTMLResponse:
    assessment = repository.get(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    return HTMLResponse(_render_report(assessment))


@app.get("/api/v1/schema/assessment")
def assessment_schema() -> dict:
    return Assessment.model_json_schema()


def _render_report(assessment: Assessment) -> str:
    risks = "".join(
        f"<li><strong>{html.escape(item.name)}</strong>："
        f"{html.escape(item.business_impact)} "
        f"<small>({item.severity}, {item.probability}%)</small></li>"
        for item in assessment.risks
    )
    scenarios = "".join(
        f"<tr><td>{html.escape(item.name)}</td><td>{item.weighted_score}</td>"
        f"<td>{html.escape(item.description)}</td></tr>"
        for item in assessment.scenarios
    )
    evidence = "".join(
        f"<li>[{html.escape(item.evidence_id)}] {html.escape(item.title)} - "
        f"{html.escape(item.publisher)}"
        f"{' (MOCK)' if item.is_mock else ''}</li>"
        for item in assessment.evidence
    )
    limitations = "".join(
        f"<li>{html.escape(item)}</li>" for item in assessment.limitations
    )
    company_name = html.escape(assessment.company_profile.company_name)
    company_summary = html.escape(assessment.company_profile.summary)
    recommendation_headline = html.escape(assessment.recommendation.headline)
    recommendation_rationale = html.escape(assessment.recommendation.rationale)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{company_name} - 决策报告</title>
<style>
body {{ font-family: Arial, "Microsoft YaHei", sans-serif; max-width: 900px;
margin: 40px auto; color: #17212b; line-height: 1.65; }}
h1, h2 {{ color: #102a43; }}
table {{ width: 100%; border-collapse: collapse; margin: 18px 0; }}
th, td {{ border: 1px solid #d9e2ec; padding: 10px; text-align: left; }}
th {{ background: #eef4f8; }}
small {{ color: #52606d; }}
.print {{ margin-top: 24px; }}
@media print {{ .print {{ display: none; }} body {{ margin: 0; }} }}
</style>
</head>
<body>
<h1>供应链迁移决策初步报告</h1>
<p>{company_summary}</p>
<h2>主要风险</h2>
<ul>{risks}</ul>
<h2>情景比较</h2>
<table><thead><tr><th>方案</th><th>综合分</th><th>说明</th></tr></thead>
<tbody>{scenarios}</tbody></table>
<h2>初步建议</h2>
<p><strong>{recommendation_headline}</strong></p>
<p>{recommendation_rationale}</p>
<h2>证据</h2>
<ul>{evidence}</ul>
<h2>边界与不确定性</h2>
<ul>{limitations}</ul>
<button class="print" onclick="window.print()">打印或导出 PDF</button>
</body>
</html>"""
