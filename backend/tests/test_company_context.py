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
    FactItem,
    RetrievedEvidence,
)


def make_evidence(
    evidence_id: str,
    scope: str,
    title: str = "test",
) -> RetrievedEvidence:
    return RetrievedEvidence(
        evidence_id=evidence_id,
        title=title,
        source_type="company_website" if scope == "company" else "法规政策",
        publisher="test",
        country_region="CN",
        publication_date="2026-01-01",
        url=None,
        authority_level="B",
        topic="test",
        document_path=None,
        document_url=None,
        content="test content",
        relevance_score=80,
        is_mock=False,
        evidence_scope=scope,  # type: ignore[arg-type]
    )


def make_company() -> CompanyInput:
    return CompanyInput.model_validate(
        {
            "company_name": "CATL",
            "industry": "battery_ev",
            "products": ["battery cells"],
            "home_country": "CN",
            "production_locations": [{"country": "CN", "production_share": 100}],
            "target_markets": ["US"],
            "decision_question": "expand overseas or stay in China",
            "time_horizon": "6_18_months",
            "priorities": [{"dimension": "supply_chain_resilience", "weight": 3}],
        }
    )


class StaticRetrieval:
    def __init__(self, items):
        self.items = items

    def search(self, query):
        return list(self.items)


class RecordingLLM(MockLLM):
    """Records what each downstream stage received, then uses the baseline."""

    def __init__(self):
        self.calls: dict[str, dict] = {}

    def build_intelligence(self, company, profile, evidence, language="en"):
        self.calls["build_intelligence"] = {"evidence": list(evidence)}
        return {}

    def analyze_risks(self, company, evidence, baseline, language="en", company_intelligence=None):
        self.calls["analyze_risks"] = {"company_intelligence": company_intelligence}
        return {"risks": baseline}

    def simulate_scenarios(self, company, evidence, risks, baseline, language="en", company_intelligence=None):
        self.calls["simulate_scenarios"] = {"company_intelligence": company_intelligence}
        return {"scenarios": baseline}

    def generate_recommendation(self, company, evidence, risks, scenarios, baseline, language="en", company_intelligence=None):
        self.calls["generate_recommendation"] = {"company_intelligence": company_intelligence}
        return baseline


class CompanyContextTest(unittest.TestCase):
    def test_evidence_split_by_scope(self) -> None:
        evidence = [
            make_evidence("EVD-A", "company"),
            make_evidence("EVD-B", "policy"),
            make_evidence("EVD-C", "market"),
        ]
        self.assertEqual(
            [item.evidence_id for item in AgentService._company_evidence(evidence)],
            ["EVD-A"],
        )
        self.assertEqual(
            [item.evidence_id for item in AgentService._policy_evidence(evidence)],
            ["EVD-B", "EVD-C"],
        )

    def test_profile_stage_receives_company_evidence_only(self) -> None:
        llm = RecordingLLM()
        agent = AgentService(
            retrieval=StaticRetrieval(
                [make_evidence("EVD-CO", "company"), make_evidence("EVD-POL", "policy")]
            ),
            llm=llm,
        )
        agent.run(make_company())
        seen = [item.evidence_id for item in llm.calls["build_intelligence"]["evidence"]]
        self.assertEqual(seen, ["EVD-CO"])

    def test_profile_stage_falls_back_when_no_company_evidence(self) -> None:
        # A failed company lookup must not leave the profile with nothing.
        llm = RecordingLLM()
        agent = AgentService(
            retrieval=StaticRetrieval([make_evidence("EVD-POL", "policy")]),
            llm=llm,
        )
        agent.run(make_company())
        seen = [item.evidence_id for item in llm.calls["build_intelligence"]["evidence"]]
        self.assertEqual(seen, ["EVD-POL"])

    def test_every_downstream_stage_receives_company_intelligence(self) -> None:
        llm = RecordingLLM()
        agent = AgentService(
            retrieval=StaticRetrieval(
                [make_evidence("EVD-CO", "company"), make_evidence("EVD-POL", "policy")]
            ),
            llm=llm,
        )
        agent.run(make_company())
        for stage in (
            "analyze_risks",
            "simulate_scenarios",
            "generate_recommendation",
        ):
            brief = llm.calls[stage]["company_intelligence"]
            self.assertTrue(brief, f"{stage} did not receive company intelligence")
            self.assertIn("identity", brief)
            self.assertIn("information_gaps", brief)

    def test_brief_is_bounded(self) -> None:
        intelligence = CompanyIntelligence(
            executive_summary="x" * 2000,
            overview=[FactItem(fact=f"fact {i}") for i in range(20)],
            information_gaps=[f"gap {i}" for i in range(20)],
        )
        brief = AgentService.intelligence_brief(intelligence)
        self.assertEqual(len(brief["overview"]), 4)
        self.assertEqual(len(brief["information_gaps"]), 5)
        self.assertLessEqual(len(brief["executive_summary"]), 600)

    def test_brief_of_missing_intelligence_is_empty(self) -> None:
        self.assertEqual(AgentService.intelligence_brief(None), {})


if __name__ == "__main__":
    unittest.main()
