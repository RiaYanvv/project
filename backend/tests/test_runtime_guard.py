from __future__ import annotations

import unittest
from unittest.mock import patch

from app.runtime_guard import SlidingWindowLimiter


class RuntimeGuardTest(unittest.TestCase):
    def test_limit_is_enforced_for_the_window(self) -> None:
        limiter = SlidingWindowLimiter()
        with patch("app.runtime_guard.time.monotonic", side_effect=[1, 2, 3, 4]):
            self.assertTrue(limiter.allow("1.2.3.4", 2, 60))
            self.assertTrue(limiter.allow("1.2.3.4", 2, 60))
            self.assertFalse(limiter.allow("1.2.3.4", 2, 60))

    def test_limit_is_independent_per_key(self) -> None:
        limiter = SlidingWindowLimiter()
        self.assertTrue(limiter.allow("one", 1, 60))
        self.assertTrue(limiter.allow("two", 1, 60))


if __name__ == "__main__":
    unittest.main()
