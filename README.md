# Locus — AI Supply Chain Relocation Decision Agent

Locus is an evidence-based decision-support assistant for manufacturing companies that are
re-balancing production between China and other regions under geopolitical uncertainty. It helps a
supply-chain or strategy team compare relocation options — keep the current footprint, increase
China capacity, move production elsewhere, or diversify — and returns an explainable,
source-backed recommendation.

The first target industry is the **EV / battery supply chain**.

---

## Why this exists

Many companies moved production to Vietnam, India, Thailand or Indonesia to reduce tariff exposure.
A large share then found that leaving China does not automatically lower total cost: the mature
supplier ecosystem, engineering talent, logistics density and energy stability are hard to
replicate. Re-evaluating that decision is slow because the relevant information is fragmented
across policy documents, trade data, news and country-level risk reports.

Locus turns that fragmented material into a structured decision: build a company profile, retrieve
evidence, assess risks, simulate scenarios and report the recommendation together with its sources
and its uncertainty.

---

## How it works

```
User input
   |
   v
Company profile
   |
   v
Evidence retrieval (knowledge base + optional web search)
   |
   v
Risk assessment (trade, political, supply chain, regulatory, market access, operational)
   |
   v
Scenario simulation (maintain, increase China production, relocate, hybrid)
   |
   v
AI consultation (add constraints, upload documents, update scenarios)
   |
   v
Final decision report (PDF) and saved decision project
```

The backend agent runs six stages — profile, research, risk, scenario, advisor and verification.
Every stage is written into a trace, LLM output is validated against a strict schema, and a
rule-based fallback keeps the pipeline running when a model response fails validation.

---

## Product surface

* **Home** — product entry point with the consultation call to action.
* **Decision form** — quick assessment plus an optional deeper assessment (site details, supplier
  dependency, investment constraints, decision priorities).
* **Initial assessment** — agent summary, qualitative risk radar, risk detail with linked evidence,
  decision rationale and an explicit uncertainty panel.
* **Scenario simulation** — simulation transition, scenario comparison (overall score, five
  dimensions, confidence), expandable scenario analysis and a preliminary strategic report.
* **AI consultation workspace** — persistent decision-context panel, chat with evidence-grounded
  answers, add information (documents and structured constraints), scenario update, report
  generation.
* **Final decision report** — generation transition, embedded PDF preview returned by the backend,
  download, back to consultation (which marks the report outdated if the analysis changes), and
  end consultation & save decision.
* **My Decisions** — decision projects with two states: *In progress* (resumes at the stage you left
  off) and *Completed* (read-only decision record, plus re-assess and delete).
* **English / 中文** interface switch.

The frontend is plain HTML/CSS/JS with no build step.

---

## Repository layout

Work happens on role branches; this branch (`main`) holds the README.

| Branch | Contents |
| --- | --- |
| `main` | README and project-level notes |
| `docs` | `PRD.md`, `UI.md`, `schema.md`, `backend changes.md`, `profile list.md`, `agent.md`, `schedule.md` |
| `frontend` | The web app: `index.html`, `styles.css`, `refinements.css`, `app.js`, `i18n.js` |
| `backend` | FastAPI service: agent pipeline, retrieval, report generation, streaming API |
| `data` | Source documents (`data/raw/...`) and evidence metadata (`data/metadata/...`) |

`docs/schema.md` defines the shared field naming, ID prefixes, units and null conventions that both
sides of the API follow, and `docs/backend changes.md` tracks everything the frontend still needs
from the backend.

---

## Getting started

### Frontend only (preview mode)

```bash
cd frontend
python3 -m http.server 8123
```

Then open <http://127.0.0.1:8123/>. Without a backend the app runs a local, clearly-labelled preview
assessment so the whole flow can be demonstrated.

### Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

The API runs on <http://127.0.0.1:8000> and the same server also serves the frontend at `/`.
Optional settings are read from a `.env` file at the repository root:

```ini
DEEPSEEK_API_KEY=...        # enables live model calls
LLM_PROVIDER=deepseek       # or "mock" for the rule-based pipeline
WEB_SEARCH_ENABLED=true
```

### Connecting the frontend to the agent

Define the integration globals before `app.js` loads:

```html
<script>
  window.LOCUS_API_BASE = "http://127.0.0.1:8000";
  window.LOCUS_API_KEY  = "your DeepSeek API key";
  window.LOCUS_MODEL    = "deepseek-flash";
</script>
```

---

## API surface (v1)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/api/v1/meta` | Model, retrieval and knowledge-base status |
| `GET` | `/api/v1/evidence` | Evidence lookup by query |
| `POST` | `/api/v1/assessments` | Run the full agent pipeline |
| `POST` | `/api/v1/assessments/stream` | Same pipeline with NDJSON stage events |
| `GET` | `/api/v1/assessments/{id}` | Retrieve a saved assessment |
| `POST` | `/api/v1/assessments/{id}/chat` | Consult on an assessment |
| `GET` | `/api/v1/assessments/{id}/report` | Decision report as PDF |
| `GET` | `/api/v1/assessments/{id}/report/html` | Decision report as HTML |
| `GET` | `/api/v1/schema/assessment` | JSON schema of the assessment contract |

---

## Design principles

* **Evidence-based** — important conclusions carry sources; the evidence library records publisher,
  date, authority level and topic.
* **Explainable** — the interface shows the factors, evidence, assumptions and uncertainty behind an
  assessment. It never exposes model chain-of-thought.
* **Human in the loop** — outputs are decision support, not autonomous decisions; high-severity or
  unverified findings are flagged for human review.
* **No false precision** — risk is expressed as qualitative levels, and scenario scores are labelled
  as AI-generated estimates rather than predictions.

---

## Current status

* The full workflow runs end to end in preview mode: form, assessment, scenario simulation,
  consultation, final report, saved decision project.
* The live Agent path is implemented (FastAPI + DeepSeek, NDJSON streaming, PDF report) and needs the
  backend running with an API key.
* Remaining backend work is tracked in `docs/backend changes.md` — among others: configurable CORS,
  serving raw evidence documents, a scenario re-run endpoint, a structured chat response, document
  upload, report versioning, and the final report content specification.
* Personas, evaluation plan and roadmap are in `docs/PRD.md`.
