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
from app.retrieval import HybridRetrievalProvider
from app.schemas import RetrievalQuery


class ReviewRegressionTest(unittest.TestCase):
    def test_solar_chunk_does_not_pass_battery_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = KnowledgeRepository(Path(directory) / "test.db")
            repository.ingest_document(
                KnowledgeDocument(
                    source_id="SOLAR-001",
                    title="Solar cell anti-circumvention decision",
                    source_type="official_policy",
                    publisher="Test Authority",
                    country_region="US",
                    publication_date="2026-01-01",
                    url="https://example.org/solar",
                    authority_level="A",
                    topic="tariff_pressure",
                    document_path=None,
                    content=(
                        "Photovoltaic solar cells and silicon wafers were found "
                        "to circumvent anti-dumping duties."
                    ),
                )
            )
            retrieval = HybridRetrievalProvider(repository=repository)
            results = retrieval.search(
                RetrievalQuery(
                    industry="battery_ev",
                    products=["EV battery", "solar cells"],
                    home_country="CN",
                    production_countries=["CN"],
                    target_markets=["US"],
                    decision_question="US tariff and anti-circumvention exposure",
                    restrictions=["tariff_pressure"],
                    limit=5,
                )
            )
        self.assertFalse(
            any("SOLAR-001" in item.evidence_id for item in results)
        )

    def test_missing_evidence_is_not_backfilled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = AgentService(
                retrieval=HybridRetrievalProvider(
                    KnowledgeRepository(Path(directory) / "empty.db")
                ),
                llm=MockLLM(),
            )
        risks, _ = agent._coerce_risks(
            [
                {
                    "name": "Unverified tariff risk",
                    "category": "trade_policy",
                    "severity": "medium",
                    "probability": 55,
                    "business_impact": "Potential cost increase.",
                    "uncertainty": "No evidence linked.",
                    "evidence_ids": [],
                }
            ],
            [],
            [],
        )
        self.assertEqual(risks[0].evidence_ids, [])
        self.assertTrue(risks[0].insufficient_evidence)
        self.assertEqual(risks[0].verification_status, "unverified")


if __name__ == "__main__":
    unittest.main()
