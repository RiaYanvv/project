from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.knowledge import KnowledgeDocument, KnowledgeRepository
from app.llm import MockLLM
from app.retrieval import HybridRetrievalProvider, MockRetrievalProvider
from app.schemas import ChatRequest, CompanyInput, RetrievalQuery


class AgentServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        retrieval = MockRetrievalProvider(
            BACKEND_ROOT / "test_data" / "mock_evidence.json"
        )
        self.agent = AgentService(retrieval=retrieval, llm=MockLLM())
        self.company = CompanyInput.model_validate(
            {
                "company_name": "示例新能源科技",
                "industry": "battery_ev",
                "products": ["EV battery cells"],
                "home_country": "CN",
                "production_locations": [
                    {"country": "CN", "production_share": 35},
                    {"country": "VN", "production_share": 65},
                ],
                "target_markets": ["US", "EU"],
                "decision_question": "是否应提高中国生产比例？",
                "time_horizon": "6_18_months",
                "priorities": [
                    {"dimension": "cost_reduction", "weight": 3},
                    {"dimension": "supply_chain_resilience", "weight": 5},
                    {"dimension": "market_access", "weight": 4},
                    {"dimension": "political_stability", "weight": 4},
                    {"dimension": "compliance", "weight": 5},
                ],
                "restrictions": [
                    "tariff_pressure",
                    "supplier_dependency",
                    "export_controls",
                ],
            }
        )

    def test_run_returns_complete_contract(self) -> None:
        assessment = self.agent.run(self.company)
        self.assertTrue(assessment.assessment_id.startswith("ASM-"))
        self.assertGreaterEqual(len(assessment.evidence), 3)
        self.assertGreaterEqual(len(assessment.risks), 3)
        self.assertEqual(len(assessment.scenarios), 3)
        scores = [scenario.weighted_score for scenario in assessment.scenarios]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(
            [scenario.scenario_id for scenario in assessment.scenarios],
            ["SCN-001", "SCN-002", "SCN-003"],
        )
        self.assertIn(
            assessment.recommendation.recommended_scenario_id,
            {scenario.scenario_id for scenario in assessment.scenarios},
        )
        self.assertTrue(assessment.evidence[0].is_mock)

    def test_chat_preserves_history(self) -> None:
        assessment = self.agent.run(self.company)
        updated = self.agent.chat(
            assessment,
            ChatRequest(message="我们的投资预算上限是 5000 万美元。"),
        )
        self.assertEqual(len(updated.chat_history), 2)
        self.assertEqual(updated.chat_history[0].role, "user")
        self.assertEqual(updated.chat_history[1].role, "assistant")

    def test_production_share_only_rejects_impossible_totals(self) -> None:
        """profile list.md: shares are recommended but not mandatory.

        A partial or empty footprint must be accepted, because the form leaves
        the share blank by default. Only a total above 100% is impossible.
        """
        payload = self.company.model_dump(mode="json")
        payload["production_locations"] = [
            {"country": "CN", "production_share": 70},
            {"country": "VN", "production_share": 40},
        ]
        with self.assertRaises(ValueError):
            CompanyInput.model_validate(payload)

        payload["production_locations"] = [
            {"country": "CN", "production_share": 40},
            {"country": "VN", "production_share": 40},
        ]
        accepted = CompanyInput.model_validate(payload)
        self.assertEqual(len(accepted.production_locations), 2)

        # The form's default row carries no share at all.
        payload["production_locations"] = [
            {"country": "CN", "production_share": 0}
        ]
        self.assertEqual(
            len(CompanyInput.model_validate(payload).production_locations), 1
        )

        payload["production_locations"] = []
        self.assertEqual(
            CompanyInput.model_validate(payload).production_locations, []
        )

    def test_hybrid_retrieval_uses_indexed_public_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = KnowledgeRepository(Path(directory) / "test.db")
            repository.ingest_document(
                KnowledgeDocument(
                    source_id="TEST-001",
                    title="Export control guidance",
                    source_type="official_policy",
                    publisher="Test Authority",
                    country_region="US",
                    publication_date="2026-01-01",
                    url="https://example.org/export-controls",
                    authority_level="A",
                    topic="export_controls",
                    document_path=None,
                    content=(
                        "The export control rule requires customer screening, "
                        "product classification, and a license before shipment."
                    ),
                )
            )
            retrieval = HybridRetrievalProvider(
                repository=repository,
                fallback=MockRetrievalProvider(
                    BACKEND_ROOT / "test_data" / "mock_evidence.json"
                ),
                web_search=None,
            )
            results = retrieval.search(
                RetrievalQuery(
                    industry="semiconductor",
                    products=["inspection equipment"],
                    home_country="CN",
                    production_countries=["CN"],
                    target_markets=["US"],
                    decision_question="Does the customer require export screening?",
                    restrictions=["export_controls"],
                    limit=3,
                )
            )

        self.assertTrue(results)
        self.assertEqual(results[0].evidence_id, "EVD-TEST-001-C0000")
        self.assertFalse(results[0].is_mock)


if __name__ == "__main__":
    unittest.main()
