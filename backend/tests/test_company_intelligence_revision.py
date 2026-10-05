from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.company_research import CompanyResearchTool
from app.schemas import InformationGap, RetrievedEvidence


def make_evidence(source_type: str, scope: str = "company") -> RetrievedEvidence:
    return RetrievedEvidence(
        evidence_id="EVD-X",
        title="t",
        source_type=source_type,
        publisher="p",
        country_region="CN",
        publication_date="2026-01-01",
        url=None,
        authority_level="B",
        topic="t",
        document_path=None,
        document_url=None,
        content="c",
        relevance_score=80,
        is_mock=False,
        evidence_scope=scope,  # type: ignore[arg-type]
    )


class EvidenceTierTest(unittest.TestCase):
    """Profile evidence priority (Company Intelligence revision §1.2)."""

    def test_company_disclosure_is_tier_one(self) -> None:
        for source_type in (
            "company_filing",
            "exchange_disclosure",
            "company_announcement",
            "company_website",
            "company_registry",
        ):
            self.assertEqual(
                AgentService._evidence_tier(make_evidence(source_type))[0], 1
            )

    def test_industry_and_policy_are_lower_tiers(self) -> None:
        self.assertEqual(
            AgentService._evidence_tier(make_evidence("研究报告", "policy"))[0], 3
        )
        self.assertEqual(
            AgentService._evidence_tier(make_evidence("法规政策", "policy"))[0], 4
        )
        self.assertEqual(
            AgentService._evidence_tier(make_evidence("live_policy", "policy"))[0], 4
        )

    def test_public_reference_is_not_the_company_disclosure(self) -> None:
        tier, reason = AgentService._evidence_tier(
            make_evidence("company_profile_public")
        )
        self.assertEqual(tier, 2)
        self.assertIn("not the company's own", reason)


class GapCapTest(unittest.TestCase):
    """Doc §6: a few useful gaps, not a dump."""

    def test_each_band_is_capped(self) -> None:
        gaps = [
            InformationGap(item=f"critical {i}", priority="critical")
            for i in range(5)
        ] + [
            InformationGap(item=f"important {i}", priority="important")
            for i in range(4)
        ] + [
            InformationGap(item=f"optional {i}", priority="optional")
            for i in range(3)
        ]
        kept = AgentService._cap_information_gaps(gaps)
        counts = {p: sum(1 for g in kept if g.priority == p) for p in AgentService.GAP_ORDER}
        self.assertEqual(counts, {"critical": 3, "important": 3, "optional": 3})

    def test_duplicates_are_dropped(self) -> None:
        kept = AgentService._cap_information_gaps(
            [
                InformationGap(item="Capacity by site", priority="critical"),
                InformationGap(item="capacity  by   site", priority="critical"),
            ]
        )
        self.assertEqual(len(kept), 1)


class SupplyChainStructureTest(unittest.TestCase):
    """Doc §3.4: no percentage without a traceable basis."""

    def test_unsourced_percentage_becomes_unknown(self) -> None:
        stages = AgentService._coerce_supply_chain_structure(
            [{"stage": "raw_material", "share": "~70%", "share_basis": "unknown"}],
            set(),
        )
        self.assertEqual(stages[0].share, "unknown")

    def test_disclosed_share_needs_a_valid_citation(self) -> None:
        kept = AgentService._coerce_supply_chain_structure(
            [
                {
                    "stage": "component",
                    "share": "30%",
                    "share_basis": "disclosed",
                    "source_ids": ["EVD-OK"],
                }
            ],
            {"EVD-OK"},
        )
        self.assertEqual(kept[0].share, "30%")
        self.assertEqual(kept[0].share_basis, "disclosed")

        dropped = AgentService._coerce_supply_chain_structure(
            [
                {
                    "stage": "component",
                    "share": "30%",
                    "share_basis": "disclosed",
                    "source_ids": ["EVD-NOT-IN-SET"],
                }
            ],
            {"EVD-OK"},
        )
        self.assertEqual(dropped[0].share, "unknown")

    def test_user_input_share_is_kept(self) -> None:
        stages = AgentService._coerce_supply_chain_structure(
            [{"stage": "manufacturing", "share": "40%", "share_basis": "user_input"}],
            set(),
        )
        self.assertEqual(stages[0].share, "40%")

    def test_unknown_stage_and_duplicates_are_dropped(self) -> None:
        stages = AgentService._coerce_supply_chain_structure(
            [
                {"stage": "bogus"},
                {"stage": "component", "description": "first"},
                {"stage": "component", "description": "second"},
            ],
            set(),
        )
        self.assertEqual([s.stage for s in stages], ["component"])
        self.assertEqual(stages[0].description, "first")


class SecCikMatchTest(unittest.TestCase):
    """A wrong CIK would attach another company's filings to this one."""

    MAPPING = {
        "teslainc": "1318605",
        "appleinc": "320193",
        "applehospitalitytrustinc": "999999",
    }

    def test_exact_and_suffixed_names_match(self) -> None:
        self.assertEqual(CompanyResearchTool._match_cik("Tesla", self.MAPPING), "1318605")
        self.assertEqual(
            CompanyResearchTool._match_cik("Tesla, Inc.", self.MAPPING), "1318605"
        )
        self.assertEqual(
            CompanyResearchTool._match_cik("Apple Inc", self.MAPPING), "320193"
        )

    def test_unrelated_company_does_not_match(self) -> None:
        self.assertEqual(CompanyResearchTool._match_cik("Apple", self.MAPPING), "320193")
        self.assertEqual(CompanyResearchTool._match_cik("CATL", self.MAPPING), "")
        self.assertEqual(
            CompanyResearchTool._match_cik("LG Energy Solution", self.MAPPING), ""
        )


class SchemaNoiseTest(unittest.TestCase):
    """A model sometimes emits field names/values where a fact belongs."""

    def test_field_values_are_not_facts(self) -> None:
        for text in ("public_source", "high", "unknown", "False", "", "  "):
            self.assertTrue(AgentService._is_schema_noise(text), text)

    def test_bare_evidence_id_list_is_not_a_fact(self) -> None:
        self.assertTrue(
            AgentService._is_schema_noise("EVD-COMPANY-WEB-1; EVD-COMPANY-WD-2")
        )

    def test_real_company_sentence_is_kept(self) -> None:
        self.assertFalse(
            AgentService._is_schema_noise(
                "CATL is headquartered in Ningde and listed in Shenzhen."
            )
        )


if __name__ == "__main__":
    unittest.main()
