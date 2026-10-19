from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.schemas import CompanyInput, ScenarioResult


def make_company(**overrides):
    payload = {
        "company_name": "Test Co",
        "industry": "battery_ev",
        "products": ["battery cells"],
        "home_country": "CN",
        "time_horizon": "6_18_months",
        "priorities": [
            {"dimension": "supply_chain_resilience", "weight": 5},
            {"dimension": "cost_reduction", "weight": 1},
        ],
    }
    payload.update(overrides)
    return CompanyInput.model_validate(payload)


def make_scenario() -> ScenarioResult:
    return ScenarioResult.model_validate(
        {
            "scenario_id": "SCN-001",
            "name": "Test scenario",
            "description": "d",
            "cost_score": 40,
            "resilience_score": 80,
            "geopolitical_risk_score": 60,
            "market_access_score": 70,
            "implementation_score": 50,
            "weighted_score": 0,
            "benefits": [],
            "risks": [],
            "applicable_conditions": [],
            "evidence_ids": [],
        }
    )


class WeightingTest(unittest.TestCase):
    def test_unranked_decision_weights_every_dimension_equally(self) -> None:
        company = make_company(priorities_declared=False)
        weights = AgentService._effective_weights(company)
        self.assertEqual(len(set(weights.values())), 1)
        self.assertEqual(set(weights), set(AgentService.SCORING_DIMENSIONS))

    def test_declared_ranking_is_respected(self) -> None:
        company = make_company(priorities_declared=True)
        weights = AgentService._effective_weights(company)
        self.assertEqual(weights["supply_chain_resilience"], 5)
        self.assertEqual(weights["cost_reduction"], 1)

    def test_unranked_score_equals_the_equal_weight_average(self) -> None:
        company = make_company(priorities_declared=False)
        scenario = make_scenario()
        # Four dimensions count 1x, implementation counts 0.5x.
        total = 3 * 4 + 3 * 0.5
        expected = round(
            (40 * 3 + 80 * 3 + 60 * 3 + 70 * 3 + 50 * 3 * 0.5) / total, 1
        )
        self.assertEqual(
            AgentService._weighted_scenario_score(scenario, company), expected
        )

    def test_declared_ranking_changes_the_score(self) -> None:
        scenario = make_scenario()
        unranked = AgentService._weighted_scenario_score(
            scenario, make_company(priorities_declared=False)
        )
        ranked = AgentService._weighted_scenario_score(
            scenario, make_company(priorities_declared=True)
        )
        self.assertNotEqual(unranked, ranked)

    def test_falls_back_to_equal_weights_when_every_weight_is_zero(self) -> None:
        company = make_company(
            priorities_declared=True,
            priorities=[
                {"dimension": dimension, "weight": 0}
                for dimension in AgentService.SCORING_DIMENSIONS
            ],
        )
        weights = AgentService._effective_weights(company)
        self.assertEqual(set(weights.values()), {AgentService.EQUAL_WEIGHT})

    def test_home_country_accepts_a_country_outside_the_enum(self) -> None:
        company = make_company(home_country="Brazil")
        self.assertEqual(company.home_country, "Brazil")


if __name__ == "__main__":
    unittest.main()
