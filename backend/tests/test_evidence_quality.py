from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.schemas import RetrievedEvidence


def make_evidence(
    evidence_id: str,
    source_type: str,
    authority: str = "B+",
    publication_date: str = "2011",
) -> RetrievedEvidence:
    return RetrievedEvidence(
        evidence_id=evidence_id,
        title="test record",
        source_type=source_type,
        publisher="test",
        country_region="CN",
        publication_date=publication_date,
        url=None,
        authority_level=authority,
        topic="company_entity",
        document_path=None,
        document_url=None,
        content="test content",
        relevance_score=90,
        is_mock=False,
        evidence_scope="company",
    )


class EvidenceQualityTest(unittest.TestCase):
    def setUp(self) -> None:
        # Only helper methods are exercised, so the collaborators are not needed.
        self.agent = AgentService(retrieval=None, llm=None)  # type: ignore[arg-type]

    def test_severity_is_capped_when_nothing_supports_the_risk(self) -> None:
        self.assertEqual(
            AgentService._cap_severity_without_evidence("critical", False), "medium"
        )
        self.assertEqual(
            AgentService._cap_severity_without_evidence("high", False), "medium"
        )
        # A lower level is never raised by the cap.
        self.assertEqual(
            AgentService._cap_severity_without_evidence("low", False), "low"
        )

    def test_severity_is_untouched_when_evidence_exists(self) -> None:
        self.assertEqual(
            AgentService._cap_severity_without_evidence("critical", True), "critical"
        )

    def test_risk_coercion_applies_the_cap_without_evidence(self) -> None:
        risks, _ = self.agent._coerce_risks(
            [
                {
                    "name": "Unsupported critical claim",
                    "category": "trade",
                    "severity": "critical",
                    "probability": 95,
                    "business_impact": "impact",
                    "uncertainty": "uncertainty",
                    "evidence_ids": ["EVD-DOES-NOT-EXIST"],
                }
            ],
            [],
            [],
        )
        self.assertEqual(len(risks), 1)
        self.assertTrue(risks[0].insufficient_evidence)
        self.assertEqual(risks[0].severity, "medium")

    def test_company_registry_record_is_not_marked_outdated(self) -> None:
        enriched = AgentService._enrich_evidence_status(
            [make_evidence("EVD-COMPANY-WD-Q1", "company_registry")]
        )
        record = enriched[0]
        # A registry record is a living reference, so the founding year must not
        # be read as a publication date and turn the source "outdated".
        self.assertEqual(record.freshness, "unknown")
        self.assertNotEqual(record.verification_status, "outdated")

    def test_aged_policy_document_is_still_marked_outdated(self) -> None:
        enriched = AgentService._enrich_evidence_status(
            [make_evidence("EVD-OLD-001", "法规政策", publication_date="2012-01-01")]
        )
        record = enriched[0]
        self.assertEqual(record.freshness, "stale")
        self.assertEqual(record.verification_status, "outdated")


if __name__ == "__main__":
    unittest.main()
