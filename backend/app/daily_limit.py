from __future__ import annotations

import math
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


@dataclass(frozen=True)
class DailyLimitDecision:
    allowed: bool
    limit: int
    used: int
    reset_at: datetime
    retry_after_seconds: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


class DailyAssessmentLimiter:
    """Persist completion attempts per client and Beijing calendar day."""

    def __init__(
        self,
        database_path: str | Path,
        limit: int,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.limit = max(0, int(limit))
        self._now_provider = now_provider or (lambda: datetime.now(BEIJING_TZ))
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_assessment_usage (
                        day_key TEXT NOT NULL,
                        client_key TEXT NOT NULL,
                        used INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (day_key, client_key)
                    )
                    """
                )

    def consume(self, client_key: str) -> DailyLimitDecision:
        now = self._now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=BEIJING_TZ)
        now = now.astimezone(BEIJING_TZ)
        day_key = now.date().isoformat()
        reset_at = datetime.combine(
            now.date() + timedelta(days=1),
            time.min,
            tzinfo=BEIJING_TZ,
        )
        retry_after_seconds = max(
            1,
            math.ceil((reset_at - now).total_seconds()),
        )

        if self.limit <= 0:
            return DailyLimitDecision(
                allowed=True,
                limit=0,
                used=0,
                reset_at=reset_at,
                retry_after_seconds=retry_after_seconds,
            )

        with closing(self._connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO daily_assessment_usage
                        (day_key, client_key, used, updated_at)
                    VALUES (?, ?, 0, ?)
                    """,
                    (day_key, client_key, now.isoformat()),
                )
                used = int(
                    connection.execute(
                        """
                        SELECT used
                        FROM daily_assessment_usage
                        WHERE day_key = ? AND client_key = ?
                        """,
                        (day_key, client_key),
                    ).fetchone()[0]
                )
                if used >= self.limit:
                    connection.commit()
                    return DailyLimitDecision(
                        allowed=False,
                        limit=self.limit,
                        used=used,
                        reset_at=reset_at,
                        retry_after_seconds=retry_after_seconds,
                    )

                used += 1
                connection.execute(
                    """
                    UPDATE daily_assessment_usage
                    SET used = ?, updated_at = ?
                    WHERE day_key = ? AND client_key = ?
                    """,
                    (used, now.isoformat(), day_key, client_key),
                )
                connection.commit()

        return DailyLimitDecision(
            allowed=True,
            limit=self.limit,
            used=used,
            reset_at=reset_at,
            retry_after_seconds=retry_after_seconds,
        )
