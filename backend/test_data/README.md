# Backend Data

This directory contains public-source configuration, synthetic test evidence,
and ingestion reports used by the backend test and development workflow.

Do not put any of the following here:

- User-generated private data.
- Company-confidential data.
- API keys or credentials.
- Runtime databases.
- Personal assessment records.

The runtime SQLite database is `app.db` and is excluded from Git. Rebuild the
index from `data/` with `backend/scripts/ingest_dataset.py`.

