from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.repository import AssessmentRepository


class _DummyAssessment:
    assessment_id = "ASM-CONCURRENCY"
    created_at = "2026-10-22T00:00:00+00:00"
    updated_at = "2026-10-22T00:00:00+00:00"

    @staticmethod
    def model_dump_json() -> str:
        return "{}"


class SQLiteConcurrencyTest(unittest.TestCase):
    def test_save_succeeds_while_another_connection_is_reading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "app.db"
            repository = AssessmentRepository(database)

            reader = sqlite3.connect(database, timeout=10)
            try:
                reader.execute("BEGIN")
                reader.execute("SELECT COUNT(*) FROM assessments").fetchone()
                repository.save(_DummyAssessment())
            finally:
                reader.rollback()
                reader.close()

            with closing(sqlite3.connect(database)) as connection:
                with connection:
                    mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
                    saved = connection.execute(
                        "SELECT 1 FROM assessments WHERE assessment_id = ?",
                        ("ASM-CONCURRENCY",),
                    ).fetchone()
            self.assertEqual(mode.lower(), "wal")
            self.assertIsNotNone(saved)


if __name__ == "__main__":
    unittest.main()
