# Reproduction Materials

This document maps the implementation to the workflow, prompts, configuration,
data, and evaluation artifacts needed to reproduce the system.

## 1. Runtime configuration

| File | Purpose |
| --- | --- |
| `.env.example` | Safe environment-variable template with no credentials |
| `backend/app/config.py` | Reads environment variables and resolves paths |
| `backend/requirements.txt` | Python dependencies |
| `render.yaml` | Render deployment configuration and variable names |
| `Dockerfile` | Reproducible backend image and RAG index build |
| `DEPLOYMENT.md` | Frontend and backend deployment steps |

Local mode uses `LLM_PROVIDER=mock`. Live mode uses `LLM_PROVIDER=deepseek` and
reads `DEEPSEEK_API_KEY` from the server environment. The repository does not
contain a live API key.

`ASSESSMENT_RATE_LIMIT_PER_DAY` defaults to `10`. The daily assessment counter
resets at midnight in Beijing time (UTC+8).

## 2. Workflow and scoring rules

| File | Purpose |
| --- | --- |
| `docs/workflow.md` | End-to-end phases, output contracts, rubric, confidence rules, and report structure |
| `docs/agent.md` | Agent-stage summary and runtime responsibilities |
| `docs/schema.md` | Shared IDs, null conventions, units, and API field naming |
| `docs/profile list.md` | Company-profile intake fields and decision context |

## 3. Prompt locations

Prompts are versioned with the source that executes them.

| Area | Source file |
| --- | --- |
| Profile extraction and workflow orchestration | `backend/app/agent.py` |
| Company research and entity resolution | `backend/app/company_research.py` |
| DeepSeek client and chat response handling | `backend/app/llm.py` |
| Scenario scoring, rubric, and confidence | `backend/app/agent.py` |
| Report synthesis | `backend/app/report_composer.py` |
| PDF rendering | `backend/app/pdf_report.py` |

The canonical workflow and scoring intent lives in `docs/workflow.md`. The code
must be treated as the executable prompt definition when the two differ.

## 4. Evidence data

| Path | Purpose |
| --- | --- |
| `data/metadata/evidence_battery_EV_screened_v0.9.xlsx` | Indexed evidence metadata |
| `data/metadata/evidence_metadata_v0.1.json` | Structured metadata snapshot |
| `data/raw/policy/` | Policy and regulation source documents |
| `data/raw/company/` | Public company filings |
| `data/raw/reports/` | Industry and multilateral reports |
| `data/raw/trade/` | Trade data |
| `data/raw/cases/`, `data/raw/news/` | Historical context and public news sources |

Rebuild the SQLite index from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\scripts\ingest_dataset.py `
  --data-root data `
  --excel metadata/evidence_battery_EV_screened_v0.9.xlsx
```

## 5. Tests

Backend regression tests:

```powershell
$env:LLM_PROVIDER = "mock"
$env:LLM_REQUIRED = "false"
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

## 6. Reproduce a local assessment

1. Install dependencies and copy `.env.example` to `.env`.
2. Set `LLM_PROVIDER=mock` for a credential-free run.
3. Build the RAG index.
4. Start `uvicorn app.main:app` from `backend/`.
5. Open `http://127.0.0.1:8000`.
6. Enter the sample from `docs/examples/sample-input.json`.
7. Run the assessment, inspect risks, compare scenarios, open consultation, and
   generate the PDF.

The output shape is documented in `docs/examples/sample-output.md`.

## 7. Security check

Before publishing:

```powershell
git grep -I -l -E "sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}" HEAD
```

Also confirm that `.env`, `*.db`, user uploads, and local logs are untracked.
If a credential ever entered Git history, rotate it and remove it from history;
deleting the current file alone does not invalidate the credential.
