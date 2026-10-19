from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from .schemas import Assessment


class AssessmentRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assessments (
                    assessment_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, assessment: Assessment) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO assessments (
                    assessment_id, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(assessment_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    assessment.assessment_id,
                    assessment.model_dump_json(),
                    assessment.created_at,
                    assessment.updated_at,
                ),
            )

    def get(self, assessment_id: str) -> Assessment | None:
        with closing(self._connect()) as connection, connection:
            row = connection.execute(
                "SELECT payload_json FROM assessments WHERE assessment_id = ?",
                (assessment_id,),
            ).fetchone()
        if row is None:
            return None
        return Assessment.model_validate_json(row["payload_json"])
