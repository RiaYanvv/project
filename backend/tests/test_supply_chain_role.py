from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.schemas import SUPPLY_CHAIN_ROLE_FALLBACK, SUPPLY_CHAIN_ROLE_VALUES


class SupplyChainRoleTest(unittest.TestCase):
    """The role labels must stay inside the agreed controlled vocabulary."""

    def test_enum_values_pass_through(self) -> None:
        for value in SUPPLY_CHAIN_ROLE_VALUES:
            self.assertEqual(
                AgentService._normalise_supply_chain_role(value), value
            )

    def test_free_text_is_mapped_onto_the_vocabulary(self) -> None:
        cases = {
            "电池与储能系统制造商（电芯、模组、储能系统）": "BATTERY_MANUFACTURING",
            "battery cell manufacturer": "BATTERY_MANUFACTURING",
            "Upstream component supplier": "UPSTREAM_COMPONENT",
            "cathode material producer": "UPSTREAM_COMPONENT",
            "Raw material mining": "UPSTREAM_RAW_MATERIAL",
            "Integrated battery company": "INTEGRATED_BATTERY_COMPANY",
            "Energy storage system provider": "DOWNSTREAM_APPLICATION",
        }
        for text, expected in cases.items():
            self.assertEqual(
                AgentService._normalise_supply_chain_role(text), expected, text
            )

    def test_unrecognised_text_falls_back_instead_of_guessing(self) -> None:
        for text in ("something unrelated", "", None, "???"):
            self.assertEqual(
                AgentService._normalise_supply_chain_role(text),
                SUPPLY_CHAIN_ROLE_FALLBACK,
            )

    def test_string_secondary_is_split_not_iterated_per_character(self) -> None:
        roles = AgentService._normalise_supply_chain_roles(
            "电池回收与材料循环利用；后市场服务与换电解决方案"
        )
        # Iterating the string used to produce one entry per character.
        self.assertTrue(all(len(role) > 1 for role in roles))
        self.assertIn("DOWNSTREAM_APPLICATION", roles)
        self.assertLess(len(roles), 5)

    def test_delimited_and_list_inputs_agree(self) -> None:
        from_string = AgentService._normalise_supply_chain_roles(
            "UPSTREAM_COMPONENT, DOWNSTREAM_APPLICATION"
        )
        from_list = AgentService._normalise_supply_chain_roles(
            ["UPSTREAM_COMPONENT", "DOWNSTREAM_APPLICATION"]
        )
        self.assertEqual(from_string, from_list)

    def test_other_is_not_repeated_in_secondary_roles(self) -> None:
        roles = AgentService._normalise_supply_chain_roles(
            ["OTHER", "DOWNSTREAM_APPLICATION", "OTHER"]
        )
        self.assertEqual(roles, ["DOWNSTREAM_APPLICATION"])

    def test_duplicates_are_removed(self) -> None:
        roles = AgentService._normalise_supply_chain_roles(
            ["BATTERY_MANUFACTURING", "battery cell manufacturer"]
        )
        self.assertEqual(roles, ["BATTERY_MANUFACTURING"])

    def test_string_list_helper_accepts_a_delimited_string(self) -> None:
        self.assertEqual(
            AgentService._coerce_string_list("a; b、c"),
            ["a", "b", "c"],
        )
        self.assertEqual(AgentService._coerce_string_list(None), [])

    def test_string_list_helper_flattens_objects(self) -> None:
        # The model sometimes returns objects where a string list is expected;
        # storing str(dict) leaked Python syntax into the UI before.
        self.assertEqual(
            AgentService._coerce_string_list(
                [{"fact": "supplier names are unknown"}, {"narrative": "no BOM"}]
            ),
            ["supplier names are unknown", "no BOM"],
        )


if __name__ == "__main__":
    unittest.main()
