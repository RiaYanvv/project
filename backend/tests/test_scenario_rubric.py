from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.llm import MockLLM
from app.schemas import CompanyInput, RetrievedEvidence


class StaticRetrieval:
    def __init__(self, items):
        self.items = items

    def search(self, query):
        return list(self.items)


def company() -> CompanyInput:
    return CompanyInput.model_validate(
        {
            "company_name": "Test Battery",
            "industry": "battery_ev",
            "products": ["battery cells"],
            "home_country": "KR",
            "production_locations": [
                {"country": "KR", "production_share": 50},
                {"country": "PL", "production_share": 50},
            ],
            "target_markets": ["US", "EU"],
            "decision_question": "expand production",
            "time_horizon": "2_5_years",
            "priorities": [
                {"dimension": "market_access", "weight": 5},
                {"dimension": "supply_chain_resilience", "weight": 4},
                {"dimension": "cost_reduction", "weight": 3},
                {"dimension": "political_stability", "weight": 4},
                {"dimension": "compliance", "weight": 3},
            ],
            "priorities_declared": True,
            "restrictions": ["tariff_pressure"],
        }
    )


def evidence() -> RetrievedEvidence:
    return RetrievedEvidence(
        evidence_id="EVD-1",
        title="US battery tariff and origin policy",
        source_type="official_policy",
        publisher="US Government",
        country_region="US",
        publication_date="2026-01-01",
        url=None,
        authority_level="A",
        topic="tariff_pressure",
        document_path=None,
        document_url=None,
        content="US tariff and rules-of-origin requirements affect battery market access.",
        relevance_score=90,
        is_mock=False,
        evidence_scope="policy",
        freshness="current",
        verification_status="verified",
    )


def scenario_payload(include_evidence: bool = True) -> dict:
    return {
        "name": "Hybrid diversification",
        "description": "Add a regional manufacturing node.",
        "dimension_assessments": {
            "cost": {
                "band": "favourable",
                "reason": "Regional access can reduce tariff exposure.",
                "evidence_ids": ["EVD-1"] if include_evidence else [],
                "source": "evidence" if include_evidence else "inference",
            },
            "resilience": {
                "band": "very_favourable",
                "reason": "Multiple nodes reduce single-point dependency.",
                "evidence_ids": ["EVD-1"] if include_evidence else [],
                "source": "evidence" if include_evidence else "inference",
            },
            "geopolitical_risk": {
                "band": "neutral",
                "reason": "Net geopolitical effect remains uncertain.",
                "evidence_ids": [],
                "source": "inference",
            },
            "market_access": {
                "band": "favourable",
                "reason": "Closer to the target market.",
                "evidence_ids": ["EVD-1"] if include_evidence else [],
                "source": "evidence" if include_evidence else "inference",
            },
            "implementation": {
                "band": "unfavourable",
                "reason": "Certification and ramp-up take time.",
                "evidence_ids": [],
                "source": "inference",
            },
        },
        "benefits": ["Market access"],
        "risks": ["Execution complexity"],
        "applicable_conditions": ["Budget is available"],
        "evidence_ids": ["EVD-1"] if include_evidence else [],
    }


class ScenarioRubricTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = AgentService(
            retrieval=StaticRetrieval([]),
            llm=MockLLM(),
        )

    def test_bands_are_mapped_by_backend(self) -> None:
        second = scenario_payload()
        second["name"] = "Maintain current layout"
        scenarios, _ = self.agent._coerce_scenarios(
            [scenario_payload(), second], [], [evidence()], company()
        )
        scenario = scenarios[0]
        self.assertEqual(scenario.cost_score, 70)
        self.assertEqual(scenario.resilience_score, 85)
        self.assertEqual(scenario.market_access_score, 70)
        # No qualifying evidence for this dimension forces Neutral (55).
        self.assertEqual(scenario.implementation_score, 55)
        self.assertEqual(scenario.score_breakdown[1].band, "very_favourable")

    def test_no_evidence_forces_neutral(self) -> None:
        second = scenario_payload(include_evidence=False)
        second["name"] = "Maintain current layout"
        scenarios, _ = self.agent._coerce_scenarios(
            [
                scenario_payload(include_evidence=False),
                second,
            ],
            [],
            [],
            company(),
        )
        scenario = scenarios[0]
        self.assertTrue(
            all(
                item.band == "neutral"
                for item in scenario.dimension_assessments.values()
            )
        )
        self.assertTrue(
            all(
                item.source == "inference"
                for item in scenario.dimension_assessments.values()
            )
        )

    def test_weighted_score_is_calculated_from_scores_and_priorities(self) -> None:
        second = scenario_payload()
        second["name"] = "Maintain current layout"
        scenarios, _ = self.agent._coerce_scenarios(
            [scenario_payload(), second], [], [evidence()], company()
        )
        scenario = scenarios[0]
        weighted = AgentService._weighted_scenario_score(
            scenario, company()
        )
        self.assertEqual(scenario.weighted_score, weighted)
        self.assertGreater(scenario.weighted_score, 0)

    def test_scenario_confidence_uses_dimension_sources_and_global_gates(self) -> None:
        evidence_ids = ["EVD-1", "EVD-2", "EVD-3"]
        company_evidence = [
            evidence().model_copy(
                update={
                    "evidence_id": evidence_id,
                    "source_type": "company_filing",
                    "evidence_scope": "company",
                }
            )
            for evidence_id in evidence_ids
        ]
        first = scenario_payload()
        first["evidence_ids"] = []
        for assessment in first["dimension_assessments"].values():
            assessment["evidence_ids"] = evidence_ids
            assessment["source"] = "evidence"
        second = scenario_payload()
        second["name"] = "Maintain current layout"
        second["evidence_ids"] = []
        for assessment in second["dimension_assessments"].values():
            assessment["evidence_ids"] = evidence_ids
            assessment["source"] = "evidence"

        scenarios, _ = self.agent._coerce_scenarios(
            [first, second],
            [],
            company_evidence,
            company(),
        )
        scenario = scenarios[0]

        # Evidence attached only to rubric dimensions must still count.
        self.assertEqual(scenario.confidence, "high")
        gated, reasons = AgentService._scenario_confidence(
            scenario.evidence_ids,
            company_evidence,
            scenario=scenario,
            risk_degraded=True,
        )
        self.assertEqual(gated, "low")
        self.assertTrue(any("RiskAgent" in reason for reason in reasons))

    def test_structured_scenario_reason_is_cleaned_without_fallback(self) -> None:
        first = scenario_payload()
        first["dimension_assessments"]["cost"]["reason"] = {
            "summary": "新增信息提高成本压力",
            "raw": {"unexpected": "value"},
        }
        second = scenario_payload()
        second["name"] = "Maintain current layout"
        scenarios, used_fallback = self.agent._coerce_scenarios(
            [first, second],
            [],
            [evidence()],
            company(),
        )
        self.assertFalse(used_fallback)
        reason = scenarios[0].dimension_assessments["cost_score"].reason
        self.assertNotIn("{", reason)
        self.assertNotIn("unexpected", reason)


if __name__ == "__main__":
    unittest.main()
