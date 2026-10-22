from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AssessmentJob:
    job_id: str
    status: str
    stage_agent: str
    stage_status: str
    message: str
    assessment_id: str
    error: str
    created_at: str
    updated_at: str


class AssessmentJobStore:
    """Small durable state machine for assessments that outlive a request."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assessment_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    stage_agent TEXT NOT NULL DEFAULT '',
                    stage_status TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    assessment_id TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def mark_interrupted(self) -> int:
        """Fail jobs that belonged to a previous server process.

        The service runs a single uvicorn worker. A queued/running row at import
        time therefore has no live worker behind it after a restart.
        """
        now = _utc_now()
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE assessment_jobs
                SET status = 'failed',
                    stage_status = 'failed',
                    message = 'The server restarted before this assessment finished.',
                    error = 'The server restarted before this assessment finished. Please run it again.',
                    updated_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
        return int(cursor.rowcount or 0)

    def create(self, job_id: str) -> AssessmentJob:
        now = _utc_now()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO assessment_jobs (
                    job_id, status, stage_agent, stage_status, message,
                    assessment_id, error, created_at, updated_at
                ) VALUES (?, 'queued', '', '', 'Assessment queued.', '', '', ?, ?)
                """,
                (job_id, now, now),
            )
        job = self.get(job_id)
        if job is None:
            raise RuntimeError("assessment job could not be created")
        return job

    def get(self, job_id: str) -> AssessmentJob | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM assessment_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return self._from_row(row) if row is not None else None

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        stage_agent: str | None = None,
        stage_status: str | None = None,
        message: str | None = None,
        assessment_id: str | None = None,
        error: str | None = None,
    ) -> AssessmentJob | None:
        assignments = ["updated_at = ?"]
        values: list[str] = [_utc_now()]
        for column, value in (
            ("status", status),
            ("stage_agent", stage_agent),
            ("stage_status", stage_status),
            ("message", message),
            ("assessment_id", assessment_id),
            ("error", error),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(str(value))
        values.append(job_id)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                f"UPDATE assessment_jobs SET {', '.join(assignments)} WHERE job_id = ?",
                values,
            )
        return self.get(job_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> AssessmentJob:
        return AssessmentJob(
            job_id=str(row["job_id"]),
            status=str(row["status"]),
            stage_agent=str(row["stage_agent"]),
            stage_status=str(row["stage_status"]),
            message=str(row["message"]),
            assessment_id=str(row["assessment_id"]),
            error=str(row["error"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
