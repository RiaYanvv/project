from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


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
    database_path: Path
    evidence_path: Path
    web_search_enabled: bool

    @classmethod
    def from_env(cls) -> "Settings":
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY") or None
        llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if not llm_provider:
            llm_provider = "deepseek" if deepseek_api_key else "mock"
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            llm_provider=llm_provider,
            deepseek_api_key=deepseek_api_key,
            deepseek_base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ).rstrip("/"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
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
        )
