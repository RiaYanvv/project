from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8123",
    "http://127.0.0.1:8123",
)

# The frontend is often opened from a static server or a LAN address, so private
# network origins are allowed by default. Narrow this with CORS_ORIGIN_REGEX.
DEFAULT_CORS_ORIGIN_REGEX = (
    r"^http://(localhost|127\.0\.0\.1|\[::1\]"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?$"
)


def _resolve_path(value: str, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


@dataclass(frozen=True)
class Settings:
    app_env: str
    llm_provider: str
    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str
    llm_required: bool
    database_path: Path
    evidence_path: Path
    web_search_enabled: bool
    data_root: Path
    cors_origins: tuple[str, ...]
    cors_origin_regex: str

    @classmethod
    def from_env(cls) -> "Settings":
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or None
        llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if not llm_provider:
            llm_provider = "deepseek" if deepseek_api_key else "mock"
        raw_origins = os.getenv("CORS_ORIGINS", "")
        cors_origins = (
            tuple(item.strip() for item in raw_origins.split(",") if item.strip())
            if raw_origins.strip()
            else DEFAULT_CORS_ORIGINS
        )
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            llm_provider=llm_provider,
            deepseek_api_key=deepseek_api_key,
            deepseek_base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ).rstrip("/"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            llm_required=os.getenv("LLM_REQUIRED", "true").lower()
            in {"1", "true", "yes", "on"},
            database_path=_resolve_path(
                os.getenv("DATABASE_PATH", ""),
                PROJECT_ROOT / "backend" / "test_data" / "app.db",
            ),
            evidence_path=_resolve_path(
                os.getenv("EVIDENCE_PATH", ""),
                PROJECT_ROOT / "backend" / "test_data" / "mock_evidence.json",
            ),
            web_search_enabled=os.getenv("WEB_SEARCH_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"},
            data_root=_resolve_path(
                os.getenv("DATA_ROOT", ""),
                PROJECT_ROOT / "data",
            ),
            cors_origins=cors_origins,
            cors_origin_regex=os.getenv(
                "CORS_ORIGIN_REGEX", DEFAULT_CORS_ORIGIN_REGEX
            ),
        )
