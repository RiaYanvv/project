from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from typing import Any

from pydantic import ValidationError

from .company_research import CompanyResearchTool
from .llm import EventCallback, LLMProvider
from .retrieval import RetrievalProvider
from .schemas import (
    Assessment,
    ChatAnalysis,
    ChatRequest,
    ChatTurn,
    CompanyInput,
    CompanyEntity,
    CompanyIntelligence,
    CompanyProfile,
    LLMCallRecord,
    Recommendation,
    RetrievalQuery,
    RetrievedEvidence,
    RiskItem,
    ScenarioResult,
    TraceStep,
    utc_now,
)


class AgentService:
    # Normalised risk taxonomy so the frontend radar does not have to guess from
    # free-text categories (UI.md risk overview).
    RISK_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("trade", ("tariff", "trade", "duty", "customs", "import", "export control", "关税", "贸易")),
        ("political", ("geopolitic", "political", "sanction", "conflict", "地缘", "政治")),
        ("supply_chain", ("supplier", "supply", "ecosystem", "dependency", "logistics", "供应", "供应链")),
        ("regulatory", ("regulat", "compliance", "licence", "license", "law", "policy", "监管", "合规", "政策")),
        ("market_access", ("market access", "customer", "rules of origin", "市场准入", "客户")),
        ("operational", ("operat", "implementation", "workforce", "labor", "labour", "cost", "ramp", "运营", "实施", "成本")),
    )

    def __init__(
        self,
        retrieval: RetrievalProvider,
        llm: LLMProvider,
        company_research: CompanyResearchTool | None = None,
    ):
        self.retrieval = retrieval
        self.llm = llm
        self.company_research = company_research

    @classmethod
    def _risk_category_key(cls, name: str, category: str) -> str:
        text = f"{category} {name}".lower()
        for key, tokens in cls.RISK_CATEGORY_KEYWORDS:
            if any(token in text for token in tokens):
                return key
        return "operational"

    @staticmethod
    def _consume_llm_result(
        payload: Any,
        stage: str,
        llm: LLMProvider,
    ) -> tuple[Any, LLMCallRecord]:
        if not isinstance(payload, dict):
            return payload, LLMCallRecord(
                stage=stage,
                provider=getattr(llm, "mode", "unknown"),
                model=getattr(llm, "model", "unknown"),
                latency_ms=0,
                attempts=0,
                ok=False,
                error="model payload is not an object",
            )
        data = dict(payload)
        meta = data.pop("__llm_meta__", None)
        if isinstance(meta, dict):
            return data, LLMCallRecord.model_validate(meta)
        return data, LLMCallRecord(
            stage=stage,
            provider=getattr(llm, "mode", "unknown"),
            model=getattr(llm, "model", "unknown"),
            latency_ms=0,
            attempts=0,
            ok=getattr(llm, "mode", "unknown") != "mock",
            error="LLM call metadata missing",
        )

    @staticmethod
    def _scenario_confidence(
        evidence_ids: list[str], evidence: list[RetrievedEvidence]
    ) -> tuple[str, list[str]]:
        """Scenario-level confidence derived from the evidence it cites."""
        by_id = {item.evidence_id: item for item in evidence}
        items = [by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in by_id]
        if not items:
            return "low", ["no evidence is linked to this scenario"]
        strong = {
            item.authority_level for item in items
        } & {"S", "A+", "A", "B+"}
        mock_only = all(item.is_mock for item in items)
        if len(items) >= 3 and strong and not mock_only:
            return "high", [
                f"{len(items)} linked sources including {sorted(strong)[0]} material"
            ]
        if len(items) >= 2:
            return "medium", [
                f"{len(items)} linked sources"
                + (" (test data only)" if mock_only else ", no top-tier authority material")
            ]
        return "low", ["only one linked source"]

    def run(
        self,
        company: CompanyInput,
        api_key: str | None = None,
        model_name: str | None = None,
        event_callback: EventCallback | None = None,
        language: str = "en",
    ) -> Assessment:
        run_id = uuid.uuid4().hex[:10].upper()
        request_id = f"REQ-{run_id}"
        assessment_id = f"ASM-{run_id}"
        trace: list[TraceStep] = []
        llm_calls: list[LLMCallRecord] = []
        degraded_stages: list[str] = []
        selected_model = model_name or getattr(self.llm, "model", "mock")
        active_llm = self.llm.with_runtime(
            selected_model,
            api_key,
            event_callback,
        )
        if self.llm.mode == "deepseek":
            if not getattr(active_llm, "api_key", None):
                raise ValueError("Backend DeepSeek API Key is not configured")
            self._emit_event(
                event_callback,
                {
                    "type": "status",
                    "agent": "Runtime",
                    "message": "正在验证 API Key 和模型权限",
                },
            )
            if not active_llm.validate_key():
                raise ValueError("DeepSeek API Key 无效或没有模型访问权限")

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "ProfileAgent", "status": "started"},
        )
        profile = self._build_profile(company, request_id, language)
        trace.append(
            self._trace(
                agent="ProfileAgent",
                action="构建结构化企业画像",
                status="completed",
                detail="已标准化企业、生产布局、市场、约束和决策优先级。",
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "ProfileAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "EntityAgent", "status": "started"},
        )
        entity_payload = active_llm.understand_entity(company, language)
        entity_payload, entity_call = self._consume_llm_result(
            entity_payload, "EntityAgent", active_llm
        )
        llm_calls.append(entity_call)
        entity = self._coerce_entity(entity_payload.get("entity"), company)
        entity_degraded = not entity_call.ok
        if entity_degraded:
            degraded_stages.append("EntityAgent")
        trace.append(
            self._trace(
                agent="EntityAgent",
                action="企业实体识别与别名解析",
                status="fallback" if entity_degraded else "completed",
                detail=(
                    f"法律实体：{entity.legal_name or company.company_name}；"
                    f"别名：{', '.join(entity.aliases[:5]) or '未提供'}"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "EntityAgent", "status": "completed"},
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "ResearchAgent", "status": "started"},
        )
        evidence = self._retrieve(company, entity.aliases)
        data_mode = "mock" if all(item.is_mock for item in evidence) else "hybrid"
        trace.append(
            self._trace(
                agent="ResearchAgent",
                action="调用混合检索工具",
                status="completed",
                detail=f"返回 {len(evidence)} 条证据，数据模式为 {data_mode}。",
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "ResearchAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "IntelligenceAgent", "status": "started"},
        )
        intelligence_payload = active_llm.build_intelligence(
            company, profile, evidence, language
        )
        intelligence_payload, intelligence_call = self._consume_llm_result(
            intelligence_payload, "IntelligenceAgent", active_llm
        )
        llm_calls.append(intelligence_call)
        intelligence, intelligence_fallback = self._coerce_intelligence(
            intelligence_payload,
            company,
            profile,
            evidence,
            language,
            entity=entity,
        )
        intelligence_degraded = intelligence_fallback or not intelligence_call.ok
        if intelligence_degraded:
            degraded_stages.append("IntelligenceAgent")
        trace.append(
            self._trace(
                agent="IntelligenceAgent",
                action="构建企业情报画像",
                status="fallback" if intelligence_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if intelligence_degraded
                    else f"输出 {len(intelligence.overview)} 条概况事实与 "
                    f"{len(intelligence.information_gaps)} 项待确认信息。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "IntelligenceAgent", "status": "completed"},
        )

        heuristic = self._build_heuristic(company, evidence)

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "RiskAgent", "status": "started"},
        )
        risk_payload = active_llm.analyze_risks(
            company, evidence, heuristic["risks"], language
        )
        risk_payload, risk_call = self._consume_llm_result(
            risk_payload, "RiskAgent", active_llm
        )
        llm_calls.append(risk_call)
        risks, risk_fallback = self._coerce_risks(
            risk_payload.get("risks"), heuristic["risks"], evidence
        )
        risk_degraded = risk_fallback or not risk_call.ok
        if risk_degraded:
            degraded_stages.append("RiskAgent")
        trace.append(
            self._trace(
                agent="RiskAgent",
                action="识别与验证地缘政治风险",
                status="fallback" if risk_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if risk_degraded
                    else f"生成并校验 {len(risks)} 条风险。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "RiskAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "ScenarioAgent", "status": "started"},
        )
        scenario_payload = active_llm.simulate_scenarios(
            company,
            evidence,
            [item.model_dump(mode="json") for item in risks],
            heuristic["scenarios"],
            language,
        )
        scenario_payload, scenario_call = self._consume_llm_result(
            scenario_payload, "ScenarioAgent", active_llm
        )
        llm_calls.append(scenario_call)
        scenarios, scenario_fallback = self._coerce_scenarios(
            scenario_payload.get("scenarios"),
            heuristic["scenarios"],
            evidence,
            company,
        )
        scenarios = self._rank_scenarios(scenarios)
        scenario_degraded = scenario_fallback or not scenario_call.ok
        if scenario_degraded:
            degraded_stages.append("ScenarioAgent")
        trace.append(
            self._trace(
                agent="ScenarioAgent",
                action="模拟迁移方案并重算权重",
                status="fallback" if scenario_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if scenario_degraded
                    else f"生成并校验 {len(scenarios)} 个情景，并按综合分从高到低编号。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "ScenarioAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "AdvisorAgent", "status": "started"},
        )
        recommendation_payload = active_llm.generate_recommendation(
            company,
            evidence,
            [item.model_dump(mode="json") for item in risks],
            [item.model_dump(mode="json") for item in scenarios],
            {
                "recommendation": heuristic["recommendation"],
                "limitations": heuristic["limitations"],
            },
            language,
        )
        recommendation_payload, advisor_call = self._consume_llm_result(
            recommendation_payload, "AdvisorAgent", active_llm
        )
        llm_calls.append(advisor_call)
        recommendation, limitations, advisor_fallback = self._coerce_recommendation(
            recommendation_payload,
            heuristic,
            company,
            evidence,
            risks,
            scenarios,
        )
        advisor_degraded = advisor_fallback or not advisor_call.ok
        if advisor_degraded:
            degraded_stages.append("AdvisorAgent")
        trace.append(
            self._trace(
                agent="AdvisorAgent",
                action="生成建议与人工复核标记",
                status="fallback" if advisor_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if advisor_degraded
                    else "建议已关联方案、风险和人工复核条件。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "AdvisorAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "VerificationAgent", "status": "started"},
        )
        citations_valid = self._validate_citations(risks, scenarios, evidence)
        trace.append(
            self._trace(
                agent="VerificationAgent",
                action="校验引用与输出边界",
                status="completed" if citations_valid else "fallback",
                detail=(
                    "全部风险与情景引用均指向本次检索结果。"
                    if citations_valid
                    else "部分引用无效，已替换为可用证据或标记为 unverified。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "VerificationAgent",
                "status": "completed",
            },
        )

        degraded = bool(degraded_stages)
        if degraded:
            limitations = [
                *limitations,
                "以下阶段未获得有效模型输出，已显式降级为规则基线："
                + ", ".join(dict.fromkeys(degraded_stages)),
            ]

        now = utc_now()
        return Assessment(
            assessment_id=assessment_id,
            request_id=request_id,
            created_at=now,
            updated_at=now,
            language=language if language in {"en", "zh"} else "en",  # type: ignore[arg-type]
            company_input=company,
            scoring={
                item.dimension: item.weight for item in company.priorities
            },
            company_profile=profile,
            company_intelligence=intelligence,
            evidence=evidence,
            risks=risks,
            scenarios=scenarios,
            recommendation=recommendation,
            trace=trace,
            limitations=limitations,
            model_mode=active_llm.mode,
            model_name=selected_model,
            data_mode=data_mode,
            llm_calls=llm_calls,
            degraded=degraded,
        )

    def chat(self, assessment: Assessment, request: ChatRequest) -> Assessment:
        user_turn = ChatTurn(role="user", content=request.message, created_at=utc_now())
        step_started = time.perf_counter()
        active_llm = self.llm.with_runtime(
            assessment.model_name,
            request.api_key,
            None,
        )
        if self.llm.mode == "deepseek" and not getattr(active_llm, "api_key", None):
            raise ValueError("Backend DeepSeek API Key is not configured")
        language = request.language
        action = active_llm.choose_chat_action(assessment, request.message, language)
        action, action_call = self._consume_llm_result(
            action, "ChatActionAgent", active_llm
        )
        chat_calls = [*assessment.llm_calls, action_call]
        supplemental_evidence: list[RetrievedEvidence] = []
        trace_status = "completed" if action_call.ok else "fallback"

        if action.get("action") == "search_evidence":
            query = str(action.get("query") or request.message)[:500]
            supplemental_evidence = self._search_text(query)
            detail = f"ChatAgent 自主调用检索工具，补充 {len(supplemental_evidence)} 条证据。"
            if not supplemental_evidence:
                trace_status = "fallback"
                detail = "ChatAgent 请求检索，但没有获得补充证据。"
        else:
            detail = "ChatAgent 判断现有上下文足够，直接调用模型回答。"

        reply = active_llm.answer_chat(
            assessment,
            request.message,
            supplemental_evidence,
            language,
        )
        answer_meta = getattr(active_llm, "last_call_meta", None)
        if isinstance(answer_meta, dict):
            answer_call = LLMCallRecord.model_validate(answer_meta)
            chat_calls.append(answer_call)
            if not answer_call.ok:
                trace_status = "fallback"
        chat_analysis = self._chat_analysis(
            action, reply, request.message, supplemental_evidence
        )
        chat_trace = self._trace(
            agent="ChatAgent",
            action="选择工具并回答追问",
            status=trace_status,
            detail=detail,
            started=step_started,
        )

        assistant_turn = ChatTurn(role="assistant", content=reply, created_at=utc_now())
        history = [*assessment.chat_history, user_turn, assistant_turn]
        updated = assessment.model_copy(
            update={
                "chat_history": history,
                "chat_analysis": chat_analysis,
                "trace": [*assessment.trace, chat_trace],
                "llm_calls": chat_calls,
                "degraded": assessment.degraded or any(
                    not item.ok for item in chat_calls
                ),
                "updated_at": utc_now(),
            }
        )
        return updated

    def resimulate(
        self,
        assessment: Assessment,
        additional_constraints: list[str] | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        language: str = "en",
    ) -> Assessment:
        """Refresh the scenario comparison with constraints from the consultation.

        The company profile, evidence set and risk list are reused, so this is a
        scenario re-run rather than a full re-assessment.
        """
        company = assessment.company_input
        if company is None:
            raise ValueError(
                "this assessment has no stored company input, so scenarios cannot "
                "be re-run"
            )
        selected_model = model_name or getattr(self.llm, "model", "mock")
        active_llm = self.llm.with_runtime(selected_model, api_key, None)
        if self.llm.mode == "deepseek":
            if not getattr(active_llm, "api_key", None):
                raise ValueError("Backend DeepSeek API Key is not configured")
            if not active_llm.validate_key():
                raise ValueError("DeepSeek API Key 无效或没有模型访问权限")

        constraints = [
            item.strip()
            for item in (additional_constraints or [])
            if item and item.strip()
        ]
        if constraints:
            addition = " | ".join(
                f"Consultation input: {item}" for item in constraints
            )
            company = company.model_copy(
                update={"notes": ((company.notes or "") + "\n" + addition).strip()[:4000]}
            )

        heuristic = self._build_heuristic(company, assessment.evidence)
        step_started = time.perf_counter()
        scenario_payload = active_llm.simulate_scenarios(
            company,
            assessment.evidence,
            [item.model_dump(mode="json") for item in assessment.risks],
            heuristic["scenarios"],
            language,
        )
        scenario_payload, scenario_call = self._consume_llm_result(
            scenario_payload, "ScenarioAgent", active_llm
        )
        scenarios, scenario_fallback = self._coerce_scenarios(
            scenario_payload.get("scenarios"),
            heuristic["scenarios"],
            assessment.evidence,
            company,
        )
        scenarios = self._rank_scenarios(scenarios)
        recommendation_payload = active_llm.generate_recommendation(
            company,
            assessment.evidence,
            [item.model_dump(mode="json") for item in assessment.risks],
            [item.model_dump(mode="json") for item in scenarios],
            {
                "recommendation": heuristic["recommendation"],
                "limitations": heuristic["limitations"],
            },
            language,
        )
        recommendation_payload, advisor_call = self._consume_llm_result(
            recommendation_payload, "AdvisorAgent", active_llm
        )
        resim_calls = [
            *assessment.llm_calls,
            scenario_call,
            advisor_call,
        ]
        recommendation, limitations, _ = self._coerce_recommendation(
            recommendation_payload,
            heuristic,
            company,
            assessment.evidence,
            assessment.risks,
            scenarios,
        )
        trace_step = self._trace(
            agent="ScenarioAgent",
            action="按咨询新增约束重跑情景模拟",
            status=(
                "completed"
                if scenario_call.ok and advisor_call.ok and not scenario_fallback
                else "fallback"
            ),
            detail=(
                f"已纳入 {len(constraints)} 条咨询新增约束并重算权重。"
                if language == "zh"
                else f"Re-ran the scenario comparison with {len(constraints)} "
                "new consultation constraint(s)."
            ),
            started=step_started,
        )
        return assessment.model_copy(
            update={
                "scenarios": scenarios,
                "recommendation": recommendation,
                "limitations": limitations,
                "company_input": company,
                "company_profile": self._build_profile(
                    company, assessment.request_id, language
                ),
                "language": language if language in {"en", "zh"} else assessment.language,
                "trace": [*assessment.trace, trace_step],
                "llm_calls": resim_calls,
                "degraded": assessment.degraded or any(
                    not item.ok for item in resim_calls
                ),
                "updated_at": utc_now(),
            }
        )

    @staticmethod
    def _chat_analysis(
        action: dict[str, Any],
        reply: str,
        message: str,
        supplemental_evidence: list[RetrievedEvidence],
    ) -> ChatAnalysis:
        """Structured turn outcome for the consultation workspace (UI.md §19)."""

        def as_list(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(item) for item in value if str(item).strip()]
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            return []

        new_constraints = as_list(action.get("new_constraints"))
        new_preferences = as_list(action.get("new_preferences"))
        scenario_update_required = bool(action.get("scenario_update_required"))
        if not new_constraints and not new_preferences:
            # Conservative fallback: a substantive message that is not a question
            # is treated as new context worth folding into the next scenario run.
            substantive = len(message.strip()) > 40 and "?" not in message
            if substantive:
                new_constraints = [message.strip()[:400]]
            scenario_update_required = scenario_update_required or substantive
        summary = str(action.get("summary") or "").strip()
        if not summary:
            summary = reply.strip().split("\n", 1)[0][:300]
        return ChatAnalysis(
            new_constraints=new_constraints,
            new_preferences=new_preferences,
            scenario_update_required=scenario_update_required,
            summary=summary,
        )

    def _search_text(self, value: str) -> list[RetrievedEvidence]:
        query = RetrievalQuery(
            industry="supply_chain",
            products=[value],
            home_country="CN",
            production_countries=[],
            target_markets=[],
            decision_question=value,
            restrictions=[],
            limit=6,
        )
        return self.retrieval.search(query)

    def _retrieve(
        self,
        company: CompanyInput,
        aliases: list[str] | None = None,
    ) -> list[RetrievedEvidence]:
        query = RetrievalQuery(
            industry=company.industry,
            products=company.products,
            company_name=company.company_name,
            aliases=list(aliases or []),
            home_country=company.home_country,
            production_countries=[
                location.country for location in company.production_locations
            ],
            target_markets=company.target_markets,
            decision_question=company.decision_question,
            restrictions=company.restrictions,
            limit=10,
        )
        policy_evidence = self.retrieval.search(query)
        company_evidence = (
            self.company_research.search(company, aliases)
            if self.company_research
            else []
        )
        combined: list[RetrievedEvidence] = []
        seen: set[str] = set()
        for item in [*company_evidence, *policy_evidence]:
            identity = item.url or item.evidence_id
            if identity in seen:
                continue
            seen.add(identity)
            combined.append(item)
        return combined[: max(query.limit, 12)]

    def _coerce_risks(
        self,
        payload: Any,
        fallback: list[dict[str, Any]],
        evidence: list[RetrievedEvidence],
    ) -> tuple[list[RiskItem], bool]:
        candidates = payload if isinstance(payload, list) else fallback
        allowed_ids = {item.evidence_id for item in evidence}
        mock_ids = {item.evidence_id for item in evidence if item.is_mock}
        risks: list[RiskItem] = []
        used_fallback = not isinstance(payload, list)

        try:
            for index, item in enumerate(candidates[:8], start=1):
                filtered = self._filter_fields(item, RiskItem)
                filtered["risk_id"] = f"RSK-{index:03d}"
                filtered["category_key"] = self._risk_category_key(
                    str(filtered.get("name") or ""),
                    str(filtered.get("category") or ""),
                )
                evidence_ids = [
                    evidence_id
                    for evidence_id in filtered.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                if not evidence_ids:
                    evidence_ids = [item.evidence_id for item in evidence[:2]]
                filtered["evidence_ids"] = evidence_ids
                verification_status = (
                    "unverified"
                    if not evidence_ids
                    else "partial"
                    if set(evidence_ids).issubset(mock_ids)
                    else "verified"
                )
                filtered["verification_status"] = verification_status
                risks.append(
                    RiskItem.model_validate(filtered).model_copy(
                        update={"risk_id": f"RSK-{index:03d}"}
                    )
                )
        except (ValidationError, TypeError, KeyError, AttributeError):
            used_fallback = True
            risks = []

        if not risks:
            for index, item in enumerate(fallback, start=1):
                evidence_ids = [
                    evidence_id
                    for evidence_id in item.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                risks.append(
                    RiskItem.model_validate(item).model_copy(
                        update={
                            "risk_id": f"RSK-{index:03d}",
                            "category_key": self._risk_category_key(
                                str(item.get("name") or ""),
                                str(item.get("category") or ""),
                            ),
                            "evidence_ids": evidence_ids
                            or [evidence_item.evidence_id for evidence_item in evidence[:2]],
                            "verification_status": "partial"
                            if evidence_ids
                            and set(evidence_ids).issubset(mock_ids)
                            else "verified",
                        }
                    )
                )
        return risks, used_fallback

    def _coerce_scenarios(
        self,
        payload: Any,
        fallback: list[dict[str, Any]],
        evidence: list[RetrievedEvidence],
        company: CompanyInput,
    ) -> tuple[list[ScenarioResult], bool]:
        candidates = payload if isinstance(payload, list) else fallback
        allowed_ids = {item.evidence_id for item in evidence}
        scenarios: list[ScenarioResult] = []
        used_fallback = not isinstance(payload, list)

        try:
            for index, item in enumerate(candidates[:5], start=1):
                filtered = self._filter_fields(item, ScenarioResult)
                filtered["scenario_id"] = f"SCN-{index:03d}"
                evidence_ids = [
                    evidence_id
                    for evidence_id in filtered.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                filtered["evidence_ids"] = evidence_ids or [
                    item.evidence_id for item in evidence[:2]
                ]
                filtered["weighted_score"] = 0
                scenario = ScenarioResult.model_validate(filtered).model_copy(
                    update={"scenario_id": f"SCN-{index:03d}"}
                )
                confidence_label, confidence_reasons = self._scenario_confidence(
                    scenario.evidence_ids, evidence
                )
                scenarios.append(
                    scenario.model_copy(
                        update={
                            "weighted_score": self._weighted_scenario_score(
                                scenario, company
                            ),
                            "confidence": confidence_label,
                            "confidence_reasons": confidence_reasons,
                        }
                    )
                )
        except (ValidationError, TypeError, KeyError, AttributeError):
            used_fallback = True
            scenarios = []

        if len(scenarios) < 2:
            used_fallback = True
            scenarios = []
            for index, item in enumerate(fallback, start=1):
                evidence_ids = [
                    evidence_id
                    for evidence_id in item.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                scenario = ScenarioResult.model_validate(item).model_copy(
                    update={
                        "scenario_id": f"SCN-{index:03d}",
                        "evidence_ids": evidence_ids
                        or [evidence_item.evidence_id for evidence_item in evidence[:2]],
                    }
                )
                confidence_label, confidence_reasons = self._scenario_confidence(
                    scenario.evidence_ids, evidence
                )
                scenarios.append(
                    scenario.model_copy(
                        update={
                            "weighted_score": self._weighted_scenario_score(
                                scenario, company
                            ),
                            "confidence": confidence_label,
                            "confidence_reasons": confidence_reasons,
                        }
                    )
                )
        return scenarios, used_fallback

    @staticmethod
    def _rank_scenarios(
        scenarios: list[ScenarioResult],
    ) -> list[ScenarioResult]:
        ranked = sorted(
            scenarios,
            key=lambda item: item.weighted_score,
            reverse=True,
        )
        return [
            item.model_copy(update={"scenario_id": f"SCN-{index:03d}"})
            for index, item in enumerate(ranked, start=1)
        ]

    def _coerce_recommendation(
        self,
        payload: Any,
        heuristic: dict[str, Any],
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[RiskItem],
        scenarios: list[ScenarioResult],
    ) -> tuple[Recommendation, list[str], bool]:
        used_fallback = False
        candidate = (
            payload.get("recommendation")
            if isinstance(payload, dict)
            else heuristic["recommendation"]
        )
        limitations = (
            payload.get("limitations")
            if isinstance(payload, dict)
            and isinstance(payload.get("limitations"), list)
            else heuristic["limitations"]
        )
        try:
            filtered = self._filter_fields(candidate, Recommendation)
            recommendation = Recommendation.model_validate(filtered)
        except (ValidationError, TypeError, KeyError, AttributeError):
            used_fallback = True
            recommendation = Recommendation.model_validate(
                heuristic["recommendation"]
            )

        scenario_ids = {item.scenario_id for item in scenarios}
        if recommendation.recommended_scenario_id not in scenario_ids:
            used_fallback = True
            best = max(scenarios, key=lambda item: item.weighted_score)
            recommendation = recommendation.model_copy(
                update={
                    "recommended_scenario_id": best.scenario_id,
                    "rationale": (
                        f"模型返回的方案编号无效，已调整为综合得分最高的"
                        f"{best.name}。{recommendation.rationale}"
                    ),
                }
            )

        requires_review = (
            any(item.severity in {"high", "critical"} for item in risks)
            or any(item.verification_status == "unverified" for item in risks)
        )
        recommendation = recommendation.model_copy(
            update={"requires_human_review": requires_review}
        )
        confidence, confidence_score, confidence_reasons = (
            self._calculate_confidence(
                company,
                evidence,
                risks,
                scenarios,
                requires_review,
            )
        )
        recommendation = recommendation.model_copy(
            update={
                "confidence": confidence,
                "confidence_score": confidence_score,
                "confidence_reasons": confidence_reasons,
            }
        )
        return recommendation, [str(item) for item in limitations], used_fallback

    @staticmethod
    def _calculate_confidence(
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[RiskItem],
        scenarios: list[ScenarioResult],
        requires_human_review: bool,
    ) -> tuple[str, int, list[str]]:
        score = 0
        reasons: list[str] = []

        evidence_score = 0
        if evidence:
            evidence_score += min(15, len(evidence))
            reasons.append(f"本次检索到 {len(evidence)} 条证据。")
        authoritative = [
            item for item in evidence if item.authority_level in {"A", "B"}
        ]
        if evidence and len(authoritative) / len(evidence) >= 0.7:
            evidence_score += 12
            reasons.append("主要证据来自高权威等级来源。")
        live_items = [
            item for item in evidence if item.source_type.startswith("live_")
        ]
        if live_items:
            evidence_score += 5
            reasons.append(f"包含 {len(live_items)} 条联网检索结果。")
        if evidence and not any(item.is_mock for item in evidence):
            evidence_score += 5
            reasons.append("当前证据不包含 Mock 数据。")
        if len({item.publisher for item in evidence}) >= 4:
            evidence_score += 10
            reasons.append("证据来源具有多样性。")
        score += min(45, evidence_score)

        company_score = 0
        if company.hs_codes:
            company_score += 10
            reasons.append("已提供 HS/ECCN 等产品分类信息。")
        else:
            reasons.append("缺少 HS/ECCN 分类会降低确定性。")
        if company.investment_budget_usd is not None:
            company_score += 8
            reasons.append("已提供投资预算约束。")
        else:
            reasons.append("缺少投资预算会限制情景量化。")
        if company.key_supplier_count is not None:
            company_score += 6
            reasons.append("已提供关键供应商数量。")
        if company.largest_supplier_share is not None:
            company_score += 5
            reasons.append("已提供最大供应商集中度。")
        if company.has_verified_bom:
            company_score += 8
            reasons.append("已确认存在经过核验的 BOM。")
        else:
            reasons.append("缺少经核验 BOM，无法映射物料级风险。")
        score += min(35, company_score)

        verification_score = 0
        if all(
            item.evidence_ids and item.verification_status != "unverified"
            for item in risks
        ):
            verification_score += 10
            reasons.append("全部风险均关联到可追溯证据。")
        if all(item.evidence_ids for item in scenarios):
            verification_score += 10
            reasons.append("全部情景均包含证据引用。")
        score += min(20, verification_score)

        high_risk_count = sum(
            item.severity in {"high", "critical"} for item in risks
        )
        if high_risk_count:
            score -= min(6, high_risk_count)
            reasons.append(f"存在 {high_risk_count} 项高风险，已下调置信度。")
        if requires_human_review:
            score -= 2
            reasons.append("关键结论需要人工复核。")

        score = max(0, min(100, score))
        if score >= 75:
            confidence = "high"
        elif score >= 45:
            confidence = "medium"
        else:
            confidence = "low"
        return confidence, score, reasons[:8]

    @staticmethod
    def _weighted_scenario_score(
        scenario: ScenarioResult,
        company: CompanyInput,
    ) -> float:
        weights = {item.dimension: item.weight for item in company.priorities}
        metric_weights = {
            "cost_score": ("cost_reduction", 1.0),
            "resilience_score": ("supply_chain_resilience", 1.0),
            "geopolitical_risk_score": ("political_stability", 1.0),
            "market_access_score": ("market_access", 1.0),
            "implementation_score": ("compliance", 0.5),
        }
        total_weight = sum(
            weights.get(dimension, 3) * factor
            for dimension, factor in metric_weights.values()
        )
        score = sum(
            getattr(scenario, metric)
            * weights.get(dimension, 3)
            * factor
            / total_weight
            for metric, (dimension, factor) in metric_weights.items()
        )
        return round(score, 1)

    @staticmethod
    def _filter_fields(item: Any, model: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise TypeError("model payload must be an object")
        allowed = set(model.model_fields)
        return {key: value for key, value in item.items() if key in allowed}

    @staticmethod
    def _validate_citations(
        risks: list[RiskItem],
        scenarios: list[ScenarioResult],
        evidence: list[RetrievedEvidence],
    ) -> bool:
        allowed_ids = {item.evidence_id for item in evidence}
        return all(
            item.evidence_ids and set(item.evidence_ids).issubset(allowed_ids)
            for item in [*risks, *scenarios]
        )

    @staticmethod
    def _emit_event(
        callback: EventCallback | None,
        event: dict[str, Any],
    ) -> None:
        if callback:
            callback(event)

    @staticmethod
    def _trace(
        agent: str,
        action: str,
        status: str,
        detail: str,
        started: float,
    ) -> TraceStep:
        return TraceStep(
            step_id=f"TRC-{uuid.uuid4().hex[:8].upper()}",
            agent=agent,
            action=action,
            status=status,
            detail=detail,
            started_at=utc_now(),
            duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
        )


    def _build_intelligence(
        self,
        company: CompanyInput,
        profile: CompanyProfile,
        evidence: list[RetrievedEvidence],
        language: str = "en",
    ) -> dict[str, Any]:
        """Company intelligence from the given inputs plus retrieved evidence.

        Facts the user stated are labelled user_input; anything supported by a
        retrieved source is public_source; everything else is marked as inferred or
        left in information_gaps rather than presented as fact.
        """
        zh = (language or "en").lower() == "zh"
        evidence_ids = [item.evidence_id for item in evidence[:3]]

        def fact(text: str, status: str, ids: list[str] | None = None) -> dict[str, Any]:
            return {"fact": text, "source_ids": list(ids or []), "data_status": status}

        products = ", ".join(company.products) or ("未提供" if zh else "not provided")
        footprint = ", ".join(
            f"{item.country} {item.production_share}%"
            for item in company.production_locations
        ) or ("未提供" if zh else "not provided")
        markets = ", ".join(company.target_markets) or ("未提供" if zh else "not provided")
        drivers = ", ".join(company.restrictions) or ("未提供" if zh else "not provided")

        if zh:
            overview = [
                fact(f"{company.company_name}，主要产品：{products}", "user_input"),
                fact(f"母国：{company.home_country}", "user_input"),
                fact("公司官网、年报或其他权威公司资料中的实体与业务信息", "to_be_confirmed", evidence_ids),
                fact("业务模式与在电池产业链中的具体环节", "to_be_confirmed"),
            ]
            production = [
                fact(f"生产分布：{footprint}", "user_input"),
                fact(f"目标市场：{markets}", "user_input"),
                fact("各基地的实际产能与产能利用率", "to_be_confirmed"),
                fact("各基地承担的环节（研发 / 原材料 / 零部件 / 制造 / 组装 / 出口）", "to_be_confirmed"),
            ]
            supply = [
                fact("关键原材料与零部件的供应来源", "to_be_confirmed"),
                fact("是否存在单一来源或难以替代的供应商", "to_be_confirmed"),
                fact("公开资料对供应链结构的支持有限，需要企业数据核验。", "inferred", evidence_ids),
            ]
            strategic = [
                fact(
                    f"Current Position：{company.company_name} 当前以 {footprint} "
                    f"的布局服务 {markets}。",
                    "user_input",
                ),
                fact("Supply-chain structure and dependencies：关键供应商与物料依赖仍待确认。", "inferred"),
                fact("Market and geopolitical exposure：需要结合政策证据核验关税、原产地和准入暴露。", "inferred"),
                fact(
                    f"Decision tension：{company.decision_question}；驱动因素为 {drivers}。",
                    "user_input",
                ),
            ]
            market_position = [
                fact("公司在目标市场的份额、客户认证和市场地位", "to_be_confirmed"),
            ]
            gaps = [
                "各基地实际产能与利用率",
                "关键原材料与零部件来源",
                "海外设施的股权与运营结构",
                "产品对应的关税分类与原产地规则",
            ]
        else:
            overview = [
                fact(f"{company.company_name} — core products: {products}", "user_input"),
                fact(f"Home country: {company.home_country}", "user_input"),
                fact("Entity and business facts available from authoritative company sources", "to_be_confirmed", evidence_ids),
                fact("Business model and exact position in the battery value chain", "to_be_confirmed"),
            ]
            production = [
                fact(f"Production footprint: {footprint}", "user_input"),
                fact(f"Target markets: {markets}", "user_input"),
                fact("Actual capacity and utilisation per site", "to_be_confirmed"),
                fact("Which activities each site performs (R&D / materials / components / manufacturing / assembly / export)", "to_be_confirmed"),
            ]
            supply = [
                fact("Origins of critical raw materials and components", "to_be_confirmed"),
                fact("Whether any input relies on a single or hard-to-replace supplier", "to_be_confirmed"),
                fact("Public sources give limited visibility on the supply-chain structure; company data is needed to verify it.", "inferred", evidence_ids),
            ]
            strategic = [
                fact(
                    f"Current Position: {company.company_name} operates {footprint} "
                    f"and serves {markets}.",
                    "user_input",
                ),
                fact("Supply-chain structure and dependencies: critical supplier and material dependencies remain to be confirmed.", "inferred"),
                fact("Market and geopolitical exposure: tariff, origin and market-access exposure must be validated against policy evidence.", "inferred"),
                fact(
                    f"Decision tension: {company.decision_question}; decision drivers: {drivers}.",
                    "user_input",
                ),
            ]
            market_position = [
                fact("Market share, customer certifications and competitive position", "to_be_confirmed"),
            ]
            gaps = [
                "Actual production capacity and utilisation by location",
                "Critical raw material and component supplier origins",
                "Ownership and operational structure of overseas facilities",
                "Product-specific tariff classification and rules of origin",
            ]
        return {
            "executive_summary": (
                f"{company.company_name} 的企业画像需基于用户 Baseline、公司实体证据和"
                "政策证据形成，优先解决实体确认、供应链依赖和市场准入问题。"
                if zh
                else f"{company.company_name}'s intelligence profile must combine the "
                "user baseline, company entity evidence and policy evidence, prioritizing "
                "entity confirmation, supply-chain dependencies and market access."
            ),
            "entity": self._coerce_entity(None, company).model_dump(mode="json"),
            "overview": overview,
            "production_footprint": production,
            "supply_chain": supply,
            "strategic_context": strategic,
            "market_position": market_position,
            "information_gaps": gaps,
        }

    @staticmethod
    def _coerce_entity(payload: Any, company: CompanyInput) -> CompanyEntity:
        fallback = CompanyEntity(
            legal_name=company.company_name,
            aliases=[company.company_name],
            headquarters=company.home_country,
            data_status="user_input",
        )
        if not isinstance(payload, dict):
            return fallback
        payload = AgentService._unwrap_dict(payload)
        try:
            entity = CompanyEntity.model_validate(payload)
        except (ValidationError, TypeError, ValueError):
            return fallback
        return entity.model_copy(
            update={
                "legal_name": entity.legal_name or company.company_name,
                "aliases": list(
                    dict.fromkeys(
                        [company.company_name, *entity.aliases]
                    )
                ),
                "headquarters": entity.headquarters or company.home_country,
            }
        )

    @staticmethod
    def _text_of(value: Any) -> str:
        """Flatten one model field to plain text.

        Models sometimes answer with a nested object (`{"narrative": "..."}`)
        where the schema expects a string. Converting that with `str()` leaks
        Python dict syntax into the UI, so the known text keys are unwrapped
        explicitly and anything else becomes an empty string.
        """
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in (
                "fact",
                "narrative",
                "text",
                "summary",
                "statement",
                "content",
                "value",
            ):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            return ""
        if isinstance(value, (int, float)):
            return str(value)
        return ""

    # The four required strategic-context paragraphs are labelled by the backend,
    # so the labels must follow the requested output language instead of leaking
    # the English prompt wording into a Chinese report.
    STRATEGIC_SECTION_LABELS = {
        "en": (
            "Current Position",
            "Supply-chain structure and dependencies",
            "Market and geopolitical exposure",
            "Decision tension",
        ),
        "zh": (
            "公司现状",
            "供应链结构与依赖",
            "市场与地缘政治暴露",
            "决策取舍",
        ),
    }
    STRATEGIC_SECTION_KEYS = (
        "Current Position",
        "current_position",
        "Supply-chain structure and dependencies",
        "supply_chain_structure",
        "Market and geopolitical exposure",
        "market_geopolitical_exposure",
        "Decision tension",
        "decision_tension",
    )

    @classmethod
    def _unwrap_list(cls, value: Any, language: str = "en") -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in (
                "items",
                "facts",
                "entries",
                "results",
                "gaps",
                "value",
            ):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return candidate
            zh = (language or "en").lower() == "zh"
            labels = cls.STRATEGIC_SECTION_LABELS["zh" if zh else "en"]
            separator = "：" if zh else ": "
            strategic_items = []
            for index, key in enumerate(cls.STRATEGIC_SECTION_KEYS):
                if key not in value or not value[key]:
                    continue
                text = cls._text_of(value[key])
                if not text:
                    continue
                strategic_items.append(
                    {"fact": f"{labels[min(index // 2, 3)]}{separator}{text}"}
                )
            if strategic_items:
                return strategic_items
            string_items = [
                {"fact": text}
                for candidate in value.values()
                if (text := cls._text_of(candidate))
            ]
            if string_items:
                return string_items
            for candidate in value.values():
                if isinstance(candidate, list):
                    return candidate
        return []

    @staticmethod
    def _unwrap_dict(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        for key in ("entity", "data", "result", "value"):
            candidate = value.get(key)
            if isinstance(candidate, dict):
                return candidate
        return value

    def _coerce_intelligence(
        self,
        payload: Any,
        company: CompanyInput,
        profile: CompanyProfile,
        evidence: list[RetrievedEvidence],
        language: str = "en",
        entity: CompanyEntity | None = None,
    ) -> tuple[CompanyIntelligence, bool]:
        fallback = self._build_intelligence(company, profile, evidence, language)
        if not isinstance(payload, dict) or not payload:
            return CompanyIntelligence.model_validate(fallback), True
        allowed = {item.evidence_id for item in evidence}
        evidence_by_id = {item.evidence_id: item for item in evidence}
        valid_status = {"user_input", "public_source", "inferred", "to_be_confirmed"}
        sections: dict[str, Any] = {}
        used_fallback = False
        provided_sections = 0
        for key in (
            "overview",
            "production_footprint",
            "supply_chain",
            "strategic_context",
            "market_position",
        ):
            cleaned = []
            for item in self._unwrap_list(payload.get(key), language):
                if not isinstance(item, dict):
                    continue
                nested = item.get("fact")
                if isinstance(nested, dict):
                    item = {**item, **nested}
                text = self._text_of(item.get("fact"))
                if not text:
                    continue
                ids = [
                    value
                    for value in (item.get("source_ids") or [])
                    if value in allowed
                ]
                status = str(item.get("data_status") or "").strip()
                if status not in valid_status:
                    status = "public_source" if ids else "inferred"
                if status == "public_source" and not self._fact_source_supports(
                    text, ids, evidence_by_id
                ):
                    status = "inferred" if ids else "to_be_confirmed"
                confidence = str(item.get("confidence") or "").strip()
                if confidence not in {"low", "medium", "high"}:
                    confidence = (
                        "high"
                        if status == "user_input"
                        else "medium"
                        if status == "public_source"
                        else "low"
                    )
                cleaned.append(
                    {
                        "fact_id": str(
                            item.get("fact_id")
                            or f"FCT-{key.upper()}-{len(cleaned) + 1:03d}"
                        ),
                        "fact": text,
                        "source_ids": ids,
                        "data_status": status,
                        "confidence": confidence,
                        "as_of": str(item.get("as_of") or ""),
                        "derived_from": [
                            str(value)
                            for value in (item.get("derived_from") or [])
                            if str(value).strip()
                        ],
                        "conflict": bool(item.get("conflict")),
                    }
                )
            sections[key] = cleaned or fallback[key]
            if cleaned:
                provided_sections += 1
        if provided_sections == 0:
            used_fallback = True
        gaps = [
            text
            for item in self._unwrap_list(payload.get("information_gaps"), language)
            if (text := self._text_of(item))
        ] or fallback["information_gaps"]
        entity_payload = self._unwrap_dict(payload.get("entity"))
        resolved_entity = self._coerce_entity(
            entity_payload if isinstance(entity_payload, dict) else None,
            company,
        )
        if entity is not None:
            resolved_entity = entity.model_copy(
                update={
                    "aliases": list(
                        dict.fromkeys([*entity.aliases, *resolved_entity.aliases])
                    )
                }
            )
        resolved_entity = resolved_entity.model_copy(
            update={
                "source_ids": [
                    item for item in resolved_entity.source_ids if item in allowed
                ]
            }
        )
        resolved_entity = self._enrich_entity_from_evidence(
            resolved_entity, evidence
        )
        raw_executive_summary = payload.get("executive_summary")
        if isinstance(raw_executive_summary, dict):
            summary_text = str(
                raw_executive_summary.get("summary")
                or raw_executive_summary.get("headline")
                or raw_executive_summary.get("text")
                or ""
            ).strip()
            findings = raw_executive_summary.get("key_findings") or []
            finding_text = " ".join(
                str(item.get("fact") or "")
                for item in findings
                if isinstance(item, dict)
            ).strip()
            raw_executive_summary = " ".join(
                item for item in (summary_text, finding_text) if item
            )
        executive_summary = str(
            raw_executive_summary
            or fallback.get("executive_summary")
            or ""
        ).strip()
        return (
            CompanyIntelligence.model_validate(
                {
                    **sections,
                    "executive_summary": executive_summary,
                    "entity": resolved_entity.model_dump(mode="json"),
                    "information_gaps": gaps,
                }
            ),
            used_fallback,
        )

    @staticmethod
    def _enrich_entity_from_evidence(
        entity: CompanyEntity,
        evidence: list[RetrievedEvidence],
    ) -> CompanyEntity:
        company_evidence = [
            item for item in evidence if item.evidence_scope == "company"
        ]
        if not company_evidence:
            return entity
        content = "\n".join(item.content for item in company_evidence)

        def capture(pattern: str) -> str:
            match = re.search(pattern, content, flags=re.IGNORECASE)
            return match.group(1).strip() if match else ""

        legal_name = capture(r"Legal entity:\s*([^\n]+)")
        headquarters = capture(r"Headquarters:\s*([^\n]+)")
        founded = capture(r"Founded:\s*([^\n]+)")
        exchange = capture(r"Stock exchange:\s*([^\n]+)")
        ticker = capture(r"Ticker:\s*([^\n]+)")
        aliases = capture(r"Aliases:\s*([^\n]+)")
        alias_values = [
            value.strip()
            for value in aliases.split(",")
            if value.strip()
        ]
        return entity.model_copy(
            update={
                "legal_name": legal_name or entity.legal_name,
                "aliases": list(
                    dict.fromkeys([*entity.aliases, *alias_values])
                ),
                "headquarters": entity.headquarters
                if entity.headquarters not in {"", "CN"}
                else headquarters or entity.headquarters,
                "founded_year": entity.founded_year or founded,
                "listing": entity.listing.model_copy(
                    update={
                        "exchange": entity.listing.exchange or exchange,
                        "ticker": entity.listing.ticker or ticker,
                    }
                ),
                "source_ids": list(
                    dict.fromkeys(
                        [
                            *entity.source_ids,
                            *[
                                item.evidence_id
                                for item in company_evidence
                            ],
                        ]
                    )
                ),
                "data_status": "public_source",
            }
        )

    def _fact_source_supports(
        self,
        fact: str,
        source_ids: list[str],
        evidence_by_id: dict[str, RetrievedEvidence],
    ) -> bool:
        if not source_ids:
            return False
        fact_terms = self._terms(fact)
        if not fact_terms:
            return False
        source_text = " ".join(
            evidence_by_id[source_id].content
            for source_id in source_ids
            if source_id in evidence_by_id
        )
        source_terms = self._terms(source_text)
        overlap = fact_terms & source_terms
        numeric_terms = {
            term for term in fact_terms if any(char.isdigit() for char in term)
        }
        return len(overlap) >= 2 and (
            not numeric_terms or numeric_terms.issubset(source_terms)
        )

    def _build_profile(
        self, company: CompanyInput, request_id: str, language: str = "en"
    ) -> CompanyProfile:
        footprint = ", ".join(
            f"{item.country} {item.production_share}%"
            for item in company.production_locations
        )
        markets = ", ".join(company.target_markets)
        # The free-text question is optional in the UI, so fall back to a generic
        # description instead of leaving the profile empty.
        question = company.decision_question.strip() or (
            "the current production layout and how to rebalance it"
        )
        footprint_text = footprint or "not specified"
        markets_text = markets or "not specified"
        if (language or "en").lower() == "zh":
            summary = (
                f"{company.company_name} 当前生产布局为 {footprint_text}，"
                f"主要面向 {markets_text} 市场。核心决策问题是：{question}"
            )
        else:
            summary = (
                f"{company.company_name} currently produces in {footprint_text} "
                f"and serves {markets_text}. The decision under review: {question}."
            )
        return CompanyProfile(
            company_id=f"CMP-{request_id.split('-')[1]}",
            company_name=company.company_name,
            industry=company.industry,
            products=company.products,
            home_country=company.home_country,
            production_footprint=company.production_locations,
            target_markets=company.target_markets,
            decision_question=question,
            time_horizon=company.time_horizon,
            priorities=company.priorities,
            restrictions=company.restrictions,
            summary=summary,
        )

    def _build_heuristic(
        self, company: CompanyInput, evidence: list[Any]
    ) -> dict[str, Any]:
        evidence_ids = [item.evidence_id for item in evidence]
        top_evidence = evidence_ids[:4]
        has_mock_evidence = any(item.is_mock for item in evidence)
        all_mock_evidence = bool(evidence) and all(item.is_mock for item in evidence)
        evidence_uncertainty = (
            "当前检索结果包含 Mock 测试证据，需要真实政策文件和公司成本数据复核。"
            if has_mock_evidence
            else "当前公开证据不包含公司内部数据，关键判断仍需人工核验。"
        )
        restrictions = set(company.restrictions)
        production = {
            location.country: location.production_share
            for location in company.production_locations
        }

        risk_templates: list[tuple[str, str, int, str]] = []
        if "tariff_pressure" in restrictions or "US" in company.target_markets:
            risk_templates.append(
                (
                    "关税与原产地规则变化",
                    "trade_policy",
                    78,
                    "出口市场和原产地认定变化可能推高到岸成本，并改变不同生产基地的相对优势。",
                )
            )
        if "export_controls" in restrictions or company.industry in {
            "semiconductor",
            "optoelectronics",
        }:
            risk_templates.append(
                (
                    "出口管制与客户穿透审查",
                    "export_control",
                    74,
                    "产品、客户及股权关系可能触发许可证、客户筛查或交易限制。",
                )
            )
        if "supplier_dependency" in restrictions or "VN" in production:
            risk_templates.append(
                (
                    "海外供应商生态不足",
                    "supply_chain",
                    66,
                    "关键物料、工程人才或本地配套不足可能降低产能爬坡速度和交付稳定性。",
                )
            )
        risk_templates.append(
            (
                "政策与数据时效性风险",
                "information_quality",
                58,
                "公开资料无法替代逐项法规核验，政策变化可能使建议快速过期。",
            )
        )

        risks = []
        for name, category, probability, impact in risk_templates:
            severity = (
                "critical"
                if probability >= 80
                else "high"
                if probability >= 70
                else "medium"
                if probability >= 55
                else "low"
            )
            risks.append(
                {
                    "risk_id": "RSK-000",
                    "name": name,
                    "category": category,
                    "severity": severity,
                    "probability": probability,
                    "business_impact": impact,
                    "uncertainty": evidence_uncertainty,
                    "evidence_ids": top_evidence[:2],
                }
            )

        weights = {item.dimension: item.weight for item in company.priorities}
        normalized_weights = {
            "cost_reduction": weights.get("cost_reduction", 3),
            "supply_chain_resilience": weights.get("supply_chain_resilience", 3),
            "market_access": weights.get("market_access", 3),
            "political_stability": weights.get("political_stability", 3),
            "compliance": weights.get("compliance", 3),
        }

        scenario_defs = [
            {
                "name": "维持现有海外布局",
                "description": "维持当前生产分布，通过供应商和库存管理降低短期扰动。",
                "cost_score": 76,
                "resilience_score": 52,
                "geopolitical_risk_score": 61,
                "market_access_score": 68,
                "implementation_score": 88,
                "benefits": ["迁移成本最低", "现有客户认证和产能爬坡不中断"],
                "risks": ["对单一海外节点和外部政策依赖仍然较高"],
                "applicable_conditions": ["政策和成本变动仍在企业可承受范围内"],
            },
            {
                "name": "提高中国生产比例",
                "description": "将部分高复杂度或高依赖环节回迁中国，利用成熟供应商生态。",
                "cost_score": 63,
                "resilience_score": 81,
                "geopolitical_risk_score": 55,
                "market_access_score": 49,
                "implementation_score": 58,
                "benefits": ["供应链完整度较高", "工程协同和交付稳定性更好"],
                "risks": ["面向美国等市场时可能承担更高关税与合规成本"],
                "applicable_conditions": ["产品对中国供应链依赖强且出口政策风险可控"],
            },
            {
                "name": "多地区混合布局",
                "description": "按产品和市场拆分生产，以冗余节点换取韧性和市场准入。",
                "cost_score": 48,
                "resilience_score": 86,
                "geopolitical_risk_score": 78,
                "market_access_score": 82,
                "implementation_score": 42,
                "benefits": ["降低单点风险", "可按市场分别优化原产地和合规路径"],
                "risks": ["资本开支和管理复杂度最高", "短期产能爬坡压力较大"],
                "applicable_conditions": ["企业具备中长期投资能力且市场足够分散"],
            },
        ]

        scenarios = []
        metric_weights = {
            "cost_score": ("cost_reduction", 1),
            "resilience_score": ("supply_chain_resilience", 1),
            "geopolitical_risk_score": ("political_stability", 1),
            "market_access_score": ("market_access", 1),
            "implementation_score": ("compliance", 0.5),
        }
        for index, item in enumerate(scenario_defs, start=1):
            total_weight = sum(
                normalized_weights[dimension] * factor
                for dimension, factor in metric_weights.values()
            )
            weighted_score = sum(
                item[metric]
                * normalized_weights[dimension]
                * factor
                / total_weight
                for metric, (dimension, factor) in metric_weights.items()
            )
            scenarios.append(
                {
                    "scenario_id": f"SCN-{index:03d}",
                    "name": item["name"],
                    "description": item["description"],
                    "cost_score": item["cost_score"],
                    "resilience_score": item["resilience_score"],
                    "geopolitical_risk_score": item["geopolitical_risk_score"],
                    "market_access_score": item["market_access_score"],
                    "implementation_score": item["implementation_score"],
                    "weighted_score": round(weighted_score, 1),
                    "benefits": item["benefits"],
                    "risks": item["risks"],
                    "applicable_conditions": item["applicable_conditions"],
                    "evidence_ids": top_evidence[:2],
                }
            )

        recommended = max(scenarios, key=lambda item: item["weighted_score"])
        return {
            "risks": risks,
            "scenarios": scenarios,
            "recommendation": {
                "recommended_scenario_id": recommended["scenario_id"],
                "headline": f"当前权重下优先评估：{recommended['name']}",
                "rationale": (
                    f"该方案的综合加权分为 {recommended['weighted_score']}，"
                    "在成本、韧性、市场准入和实施难度之间相对平衡。"
                ),
                "next_actions": [
                    "补充产品 HS/ECCN 编码、客户结构和关键供应商依赖。",
                    (
                        "用真实政策文件替换当前 Mock 证据并重新运行评估。"
                        if all_mock_evidence
                        else "核对引用来源的现行版本，并在法规更新后重新运行评估。"
                    ),
                    "补充投资预算、产能爬坡周期和固定资产沉没成本。",
                ],
                "confidence": "low",
                "uncertainty": [
                    (
                        "当前数据源为测试数据，不能作为正式决策依据。"
                        if has_mock_evidence
                        else "公开资料缺少公司级成本、产能、BOM 和客户筛查数据。"
                    ),
                    "没有公司的单位成本、产能和真实 BOM 数据。",
                    "政策变化速度和执行力度无法仅由当前信息判断。",
                ],
            },
            "limitations": [
                (
                    "当前分析包含 Mock 证据，仅用于验证产品和 Agent 工作流。"
                    if has_mock_evidence
                    else "本分析基于公开资料和适用性有限的通用证据，不能替代公司级尽调。"
                ),
                "评分是决策辅助，不构成法律、投资或合规意见。",
                "结论必须经过人工复核，高风险事项应由专业顾问确认。",
            ],
        }

    @staticmethod
    def _terms(value: str) -> set[str]:
        normalized = value.lower()
        words = set(re.findall(r"[a-z0-9]+", normalized))
        chinese = set(re.findall(r"[\u4e00-\u9fff]{2,}", normalized))
        return words.union(chinese)


def summarize_evidence_topics(assessment: Assessment) -> list[tuple[str, int]]:
    return Counter(item.topic for item in assessment.evidence).most_common()
