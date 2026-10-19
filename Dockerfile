FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LLM_PROVIDER=deepseek
ENV LLM_REQUIRED=true
ENV WEB_SEARCH_ENABLED=false

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY data /app/data
COPY frontend /app/frontend

# The indexed SQLite RAG database is intentionally not committed to Git.
# Rebuild it from the data checked into this repository during the image build.
RUN cd /app/backend \
    && DATABASE_PATH=/app/backend/test_data/app.db \
       WEB_SEARCH_ENABLED=false \
       python scripts/ingest_dataset.py \
       --data-root /app/data \
       --excel metadata/evidence_battery_EV_screened_v0.9.xlsx

ENV DATABASE_PATH=/app/backend/test_data/app.db
ENV EVIDENCE_PATH=/app/backend/test_data/mock_evidence.json
ENV APP_ENV=production

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
