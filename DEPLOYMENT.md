# GeoRisk Deployment

## Public demo

- Frontend: https://georisk-locus.netlify.app
- Backend API: https://georisk-agent.onrender.com
- Backend health check: https://georisk-agent.onrender.com/health
- Backend API documentation: https://georisk-agent.onrender.com/docs

The Netlify URL is the page to open and share with users. The Render URL is the
FastAPI service used by that page; it is not the main user-facing site.

## Architecture

```text
Browser
  -> Netlify static frontend
  -> FastAPI backend on Render
  -> SQLite RAG index built from data/ in this repository
  -> DeepSeek API using a Render environment secret
```

The API key is stored only in the Render service environment variable
`DEEPSEEK_API_KEY`. It is not stored in GitHub, Netlify, the Docker image or the
submission package.

## Use the demo

1. Open https://georisk-locus.netlify.app.
2. Start a new decision and complete the company profile.
3. Submit the assessment and wait for the evidence, risk and scenario stages.
4. Review scenarios, open the history drawer, use consultation, and generate the
   PDF report.

The Render free instance can sleep after inactivity. The first request may take
about 50 seconds to wake it. Run one small assessment before a live demo to warm
the service.

## Rebuild the backend database locally

```bash
python backend/scripts/ingest_dataset.py \
  --data-root data \
  --excel metadata/evidence_battery_EV_screened_v0.9.xlsx
```

## Deploy the backend

Render builds the backend from `Dockerfile` on the main delivery branch. The
image copies `backend/`, `data/`, and `frontend/`, then rebuilds the SQLite
index during the build.

Required Render environment variables are listed in `render.yaml`. Set the
secret value of `DEEPSEEK_API_KEY` in the Render dashboard; never commit it.

## Deploy the frontend

The frontend is a static folder. `runtime-config.js` is included in the
repository and points production traffic at the Render service. The browser key
is a placeholder because the real model credential remains on Render:

```js
window.LOCUS_API_BASE = "https://georisk-agent.onrender.com";
window.LOCUS_API_KEY = "server-managed";
window.LOCUS_MODEL = "deepseek-flash";
```

Then deploy the `frontend/` directory to Netlify.

The page automatically retries a sleeping Render instance for up to 90 seconds
before reporting the Agent as unavailable. A scheduled GitHub Action also calls
`/health` every ten minutes to keep the free instance warm.
