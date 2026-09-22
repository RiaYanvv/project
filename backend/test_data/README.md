# Backend Data

This directory contains public-source configuration, synthetic test evidence,
and ingestion reports used by the backend test and development workflow.

Do not put any of the following here:

- User-generated private data.
- Company-confidential data.
- API keys or credentials.
- Runtime databases.
- Personal assessment records.

The runtime SQLite database is `app.db` and is excluded from Git.

If the team decides that no data files should be published, keep this README and
regenerate the ingestion index locally with:

```powershell
.\.venv\Scripts\python.exe backend\scripts\ingest_sources.py
```

