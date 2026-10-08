from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.llm import MockLLM
from app.schemas import (
    CompanyInput,
    CompanyIntelligence,
    ManufacturingSite,
    RetrievedEvidence,
)


class StaticRetrieval:
    def __init__(self, items):
        self.items = items

    def search(self, query):
        return list(self.items)


def evidence(
    evidence_id: str,
    scope: str,
    content: str,
) -> RetrievedEvidence:
    return RetrievedEvidence(
        evidence_id=evidence_id,
        title="US tariff and origin policy",
        source_type="company_website" if scope == "company" else "official_policy",
        publisher="Test",
        country_region="US",
        publication_date="2026-01-01",
        url=None,
        authority_level="A",
        topic="tariff_pressure",
        document_path=None,
        document_url=None,
        content=content,
        relevance_score=90,
        is_mock=False,
        evidence_scope=scope,  # type: ignore[arg-type]
        freshness="current",
        verification_status="verified",
    )


def company() -> CompanyInput:
    return CompanyInput.model_validate(
        {
            "company_name": "LG Energy Solution",
            "industry": "battery_ev",
            "products": ["battery cells"],
            "home_country": "KR",
            "production_locations": [
                {"country": "KR", "production_share": 50},
                {"country": "PL", "production_share": 50},
            ],
            "target_markets": ["US", "EU"],
            "decision_question": "North America expansion",
            "time_horizon": "2_5_years",
            "priorities": [{"dimension": "market_access", "weight": 5}],
            "restrictions": ["tariff_pressure"],
        }
    )


def risk_payload(
    title: str = "US Market Access, Customs & Origin Exposure",
) -> dict:
    return {
        "title": title,
        "name": title,
        "category": "MARKET_ACCESS",
        "severity": "high",
        "probability": 80,
        "business_impact": "May affect US market access and customs clearance.",
        "company_specific_trigger": "LGES targets the US without a disclosed US base.",
        "external_mechanism": "US customs and rules-of-origin enforcement.",
        "impact_channels": ["market_access", "cost", "lead_time"],
        "impact_description": "May increase customs and compliance burden.",
        "likelihood_score": 4,
        "impact_score": 5,
        "company_exposure_score": 4,
        "decision_relevance": "high",
        "uncertainty": "US export share is unknown.",
        "uncertainty_reasons": ["US export share is unknown"],
        "what_would_change_assessment": ["Verified plant-level export allocation"],
        "supporting_evidence_ids": ["EVD-COMPANY", "EVD-POLICY"],
    }


class RiskAssessmentReviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = AgentService(
            retrieval=StaticRetrieval([]),
            llm=MockLLM(),
        )

    def test_company_and_external_evidence_supports_high(self) -> None:
        items = [
            evidence("EVD-COMPANY", "company", "LGES produces battery cells for US customers."),
            evidence("EVD-POLICY", "policy", "US tariff and origin enforcement applies to battery imports."),
        ]
        risks, _ = self.agent._coerce_risks(
            [risk_payload()], [], items, company()
        )
        self.assertEqual(risks[0].risk_score, 80)
        self.assertEqual(risks[0].risk_level, "high")
        self.assertIn(risks[0].confidence, {"medium", "high"})
        self.assertFalse(risks[0].insufficient_evidence)

    def test_industry_only_evidence_caps_high_risk(self) -> None:
        items = [
            evidence("EVD-POLICY", "policy", "US tariff and origin enforcement applies to battery imports."),
        ]
        risks, _ = self.agent._coerce_risks(
            [risk_payload()], [], items, company()
        )
        self.assertEqual(risks[0].risk_level, "medium")
        self.assertEqual(risks[0].confidence, "low")

    def test_sourced_company_site_can_support_high_policy_exposure(self) -> None:
        items = [
            evidence("EVD-POLICY", "policy", "US tariff and origin enforcement applies to battery imports."),
        ]
        intelligence = CompanyIntelligence(
            manufacturing_footprint=[
                ManufacturingSite(
                    country="CN",
                    facility="LGES Nanjing",
                    role="battery cell manufacturing",
                    source_ids=["EVD-COMPANY"],
                )
            ]
        )
        payload = risk_payload()
        payload["company_specific_trigger"] = (
            "LGES manufactures cells at its Nanjing base in China for export."
        )
        payload["impact_description"] = (
            "China-origin cells exported to the US can face customs and origin enforcement."
        )
        risks, _ = self.agent._coerce_risks(
            [payload], [], items, company(), intelligence
        )
        self.assertEqual(risks[0].risk_level, "high")
        self.assertEqual(risks[0].confidence, "high")

    def test_title_only_model_output_is_not_replaced_by_generic_fallback(self) -> None:
        payload = risk_payload(
            "US customs enforcement and China-origin battery transshipment risk"
        )
        payload.pop("name")
        payload.pop("business_impact")
        payload.pop("uncertainty")
        items = [
            evidence("EVD-POLICY", "policy", "US customs enforcement targets battery transshipment."),
        ]
        risks, used_fallback = self.agent._coerce_risks(
            [payload], [], items, company()
        )
        self.assertFalse(used_fallback)
        self.assertEqual(risks[0].name, payload["title"])
        self.assertEqual(risks[0].title, payload["title"])
        self.assertEqual(
            risks[0].business_impact,
            payload["impact_description"],
        )
        self.assertIn("US export share", risks[0].uncertainty)

    def test_no_evidence_cannot_be_high(self) -> None:
        risks, _ = self.agent._coerce_risks(
            [risk_payload()], [], [], company()
        )
        self.assertTrue(risks[0].insufficient_evidence)
        self.assertNotEqual(risks[0].risk_level, "high")
        self.assertEqual(risks[0].evidence_ids, [])

    def test_duplicate_risks_are_merged(self) -> None:
        items = [
            evidence("EVD-COMPANY", "company", "LGES produces battery cells for US customers."),
            evidence("EVD-POLICY", "policy", "US tariff and origin enforcement applies to battery imports."),
        ]
        risks, _ = self.agent._coerce_risks(
            [
                risk_payload(),
                risk_payload("US customs and origin exposure"),
            ],
            [],
            items,
            company(),
        )
        self.assertEqual(len(risks), 1)

    def test_information_quality_is_not_a_business_risk(self) -> None:
        payload = risk_payload()
        payload["category"] = "INFORMATION_QUALITY"
        payload["title"] = "Information quality"
        risks, _ = self.agent._coerce_risks(
            [payload], [], [], company()
        )
        self.assertEqual(risks, [])

    def test_financial_category_maps_to_operational(self) -> None:
        payload = risk_payload("Capital expenditure overrun")
        payload["category"] = "FINANCIAL"
        risks, _ = self.agent._coerce_risks(
            [payload], [], [], company()
        )
        self.assertEqual(risks[0].category_key, "operational")


if __name__ == "__main__":
    unittest.main()
