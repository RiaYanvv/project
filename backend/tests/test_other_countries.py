from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.schemas import CompanyInput


def make_company(**overrides):
    payload = {
        "company_name": "Test Co",
        "industry": "battery_ev",
        "products": ["battery cells"],
        "home_country": "CN",
        "time_horizon": "6_18_months",
        "priorities": [{"dimension": "supply_chain_resilience", "weight": 3}],
    }
    payload.update(overrides)
    return CompanyInput.model_validate(payload)


class OtherCountryTest(unittest.TestCase):
    """profile list.md: a country typed under "Other" must reach the analysis."""

    def setUp(self) -> None:
        self.agent = AgentService(retrieval=None, llm=None)  # type: ignore[arg-type]

    def test_production_location_keeps_the_typed_country(self) -> None:
        company = make_company(
            production_locations=[
                {"country": "CN", "production_share": 70},
                {"country": "Germany", "production_share": 30},
            ]
        )
        countries = [item.country for item in company.production_locations]
        self.assertEqual(countries, ["CN", "Germany"])

    def test_target_market_keeps_the_typed_country(self) -> None:
        company = make_company(target_markets=["US", "Hungary"])
        self.assertEqual(company.target_markets, ["US", "Hungary"])

    def test_profile_summary_uses_the_typed_country(self) -> None:
        company = make_company(
            production_locations=[{"country": "Germany", "production_share": 40}],
            target_markets=["Brazil"],
        )
        profile = self.agent._build_profile(company, "REQ-TEST", "en")
        self.assertIn("Germany", profile.summary)
        self.assertIn("Brazil", profile.summary)
        self.assertEqual(profile.production_footprint[0].country, "Germany")
        self.assertEqual(profile.target_markets, ["Brazil"])

    def test_known_codes_still_pass_through_unchanged(self) -> None:
        company = make_company(
            production_locations=[{"country": "VN", "production_share": 100}],
            target_markets=["EU"],
        )
        self.assertEqual(company.production_locations[0].country, "VN")
        self.assertEqual(company.target_markets, ["EU"])


if __name__ == "__main__":
    unittest.main()
