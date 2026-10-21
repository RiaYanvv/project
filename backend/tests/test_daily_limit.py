from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.daily_limit import DailyAssessmentLimiter


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


class DailyAssessmentLimiterTest(unittest.TestCase):
    def test_daily_limit_resets_at_beijing_midnight(self) -> None:
        current = [datetime(2026, 10, 21, 23, 59, 58, tzinfo=BEIJING_TZ)]
        with tempfile.TemporaryDirectory() as directory:
            limiter = DailyAssessmentLimiter(
                Path(directory) / "usage.db",
                2,
                now_provider=lambda: current[0],
            )

            first = limiter.consume("203.0.113.8")
            second = limiter.consume("203.0.113.8")
            blocked = limiter.consume("203.0.113.8")

            self.assertTrue(first.allowed)
            self.assertEqual(first.remaining, 1)
            self.assertTrue(second.allowed)
            self.assertEqual(second.remaining, 0)
            self.assertFalse(blocked.allowed)
            self.assertEqual(blocked.used, 2)
            self.assertEqual(blocked.retry_after_seconds, 2)
            self.assertEqual(
                blocked.reset_at.isoformat(),
                "2026-10-22T00:00:00+08:00",
            )

            current[0] += timedelta(seconds=2)
            reset = limiter.consume("203.0.113.8")
            self.assertTrue(reset.allowed)
            self.assertEqual(reset.used, 1)

    def test_daily_limit_is_independent_per_client(self) -> None:
        now = datetime(2026, 10, 21, 12, 0, tzinfo=BEIJING_TZ)
        with tempfile.TemporaryDirectory() as directory:
            limiter = DailyAssessmentLimiter(
                Path(directory) / "usage.db",
                1,
                now_provider=lambda: now,
            )
            self.assertTrue(limiter.consume("198.51.100.1").allowed)
            self.assertFalse(limiter.consume("198.51.100.1").allowed)
            self.assertTrue(limiter.consume("198.51.100.2").allowed)

    def test_fifteenth_assessment_is_allowed_and_sixteenth_is_blocked(
        self,
    ) -> None:
        now = datetime(2026, 10, 21, 9, 0, tzinfo=BEIJING_TZ)
        with tempfile.TemporaryDirectory() as directory:
            limiter = DailyAssessmentLimiter(
                Path(directory) / "usage.db",
                15,
                now_provider=lambda: now,
            )
            decisions = [limiter.consume("192.0.2.15") for _ in range(16)]

            self.assertTrue(all(item.allowed for item in decisions[:15]))
            self.assertEqual(decisions[14].used, 15)
            self.assertEqual(decisions[14].remaining, 0)
            self.assertFalse(decisions[15].allowed)
            self.assertEqual(decisions[15].used, 15)


if __name__ == "__main__":
    unittest.main()
