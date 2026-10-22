from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.jobs import AssessmentJobStore


class AssessmentJobStoreTest(unittest.TestCase):
    def test_job_state_is_durable_between_connections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "app.db"
            store = AssessmentJobStore(database)
            store.create("JOB-1")

            store.update(
                "JOB-1",
                status="running",
                stage_agent="ResearchAgent",
                stage_status="started",
                message="Searching evidence.",
            )
            reopened = AssessmentJobStore(database)
            job = reopened.get("JOB-1")

            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job.status, "running")
            self.assertEqual(job.stage_agent, "ResearchAgent")
            self.assertEqual(job.stage_status, "started")

    def test_server_restart_fails_only_unfinished_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AssessmentJobStore(Path(directory) / "app.db")
            store.create("JOB-RUNNING")
            store.update("JOB-RUNNING", status="running")
            store.create("JOB-COMPLETE")
            store.update(
                "JOB-COMPLETE",
                status="completed",
                assessment_id="ASM-1",
            )

            interrupted = store.mark_interrupted()

            self.assertEqual(interrupted, 1)
            running = store.get("JOB-RUNNING")
            complete = store.get("JOB-COMPLETE")
            self.assertEqual(running.status, "failed")
            self.assertIn("restarted", running.error)
            self.assertEqual(complete.status, "completed")
            self.assertEqual(complete.assessment_id, "ASM-1")


if __name__ == "__main__":
    unittest.main()
