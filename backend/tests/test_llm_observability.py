from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.llm import DeepSeekLLM


class LLMObservabilityTest(unittest.TestCase):
    def test_failed_call_is_explicitly_marked(self) -> None:
        llm = DeepSeekLLM(
            api_key="sk-test-invalid-key",
            base_url="http://127.0.0.1:1",
            model="deepseek-flash",
        )
        result = llm._call_json(
            stage="TestAgent",
            system="Return JSON.",
            payload={"task": "test"},
            fallback={"value": "rule-baseline"},
        )
        meta = result["__llm_meta__"]
        self.assertFalse(meta["ok"])
        self.assertGreaterEqual(meta["attempts"], 1)
        self.assertEqual(result["value"], "rule-baseline")
        self.assertIn("error", meta)


if __name__ == "__main__":
    unittest.main()
