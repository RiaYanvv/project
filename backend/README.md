# Locus Backend

FastAPI service for the Locus supply-chain decision workflow.

## Responsibilities

- Company-profile normalization and clarification.
- Evidence retrieval over the SQLite RAG index.
- Risk assessment across six dimensions.
- Scenario generation, scoring, confidence caps, and versioning.
- Consultation chat with structured context updates.
- Executive report composition and PDF rendering.

## Install

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

## Build the index

```powershell
.\.venv\Scripts\python.exe backend\scripts\ingest_dataset.py `
  --data-root data `
  --excel metadata/evidence_battery_EV_screened_v0.9.xlsx
```

## Run

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The API is available at `http://127.0.0.1:8000`, with OpenAPI documentation at
`http://127.0.0.1:8000/docs`. When `../frontend/index.html` exists, the backend
also serves the product page at `/`.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

## Configuration

All runtime settings are documented in `.env.example` and implemented in
`app/config.py`. Do not place a real API key in this directory.
