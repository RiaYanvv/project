from __future__ import annotations

import io
import sys
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app import main as main_module
from app.llm import DeepSeekLLM, MockLLM
from app.pdf_report import build_assessment_pdf
from app.retrieval import MockRetrievalProvider
from app.repository import AssessmentRepository
from app.schemas import (
    Assessment,
    ChatImpact,
    ChatRequest,
    ChatTurn,
    CompanyInput,
    GapUpdate,
    InformationGap,
)


class RecordingChatLLM(MockLLM):
    def __init__(self, action: dict):
        self.action = action
        self.seen_history: list[int] = []

    def choose_chat_action(
        self,
        assessment,
        message,
        language="en",
        company_intelligence=None,
    ):
        self.seen_history.append(len(assessment.chat_history))
        return dict(self.action)

    def answer_chat(
        self,
        assessment,
        message,
        supplemental_evidence,
        language="en",
        company_intelligence=None,
    ):
        return "已记录新增信息，当前正式评分尚未更新。"


def make_company() -> CompanyInput:
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
            "decision_question": "Should we expand production?",
            "time_horizon": "2_5_years",
            "priorities": [{"dimension": "market_access", "weight": 5}],
            "restrictions": ["tariff_pressure"],
        }
    )


class ScenarioChatClosedLoopTest(unittest.TestCase):
    def make_agent(self, action: dict):
        llm = RecordingChatLLM(action)
        return (
            AgentService(
                retrieval=MockRetrievalProvider(
                    BACKEND_ROOT / "test_data" / "mock_evidence.json"
                ),
                llm=llm,
            ),
            llm,
        )

    def test_chat_can_proactively_ask_for_a_gap(self) -> None:
        agent, _ = self.make_agent(
            {
                "action": "ask_gap",
                "gap_item": "Vietnam plant capacity",
                "question": "请确认越南基地的年产能和主要出口市场。",
                "why_it_matters": "这会改变韧性和市场准入评分。",
                "affected_dimensions": ["resilience", "market_access"],
            }
        )
        assessment = agent.run(make_company())
        updated = agent.chat(
            assessment,
            ChatRequest(message="我们还缺什么信息？", language="zh"),
        )
        self.assertIn("越南基地", updated.chat_history[-1].content)
        self.assertEqual(
            updated.chat_analysis.requested_gap,
            "Vietnam plant capacity",
        )

    def test_chat_opening_asks_only_the_highest_priority_gap(self) -> None:
        agent, _ = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company(), language="zh")
        self.assertIsNotNone(assessment.company_intelligence)
        intelligence = assessment.company_intelligence.model_copy(
            update={
                "information_gaps": [
                    InformationGap(
                        item="可选信息：品牌授权条款",
                        priority="optional",
                    ),
                    InformationGap(
                        item="越南工厂年产能",
                        priority="critical",
                        why_it_matters="这会直接影响供应链韧性评分。",
                        recommended_action="请提供产能数值或公开文件。",
                    ),
                ]
            }
        )
        assessment = assessment.model_copy(
            update={"company_intelligence": intelligence}
        )

        opening = agent.chat_opening(assessment, "zh")

        self.assertEqual(opening.action, "ask_gap")
        self.assertEqual(opening.requested_gap, "越南工厂年产能")
        self.assertIn("越南工厂年产能", opening.message)
        self.assertNotIn("品牌授权条款", opening.message)
        self.assertIn("resilience", opening.affected_dimensions)

    def test_chat_opening_without_history_or_gaps_is_safe(self) -> None:
        agent, _ = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company(), language="zh")
        self.assertIsNotNone(assessment.company_intelligence)
        intelligence = assessment.company_intelligence.model_copy(
            update={"information_gaps": []}
        )
        assessment = assessment.model_copy(
            update={
                "company_intelligence": intelligence,
                "chat_history": [],
            }
        )

        opening = agent.chat_opening(assessment, "zh")

        self.assertEqual(opening.action, "answer")
        self.assertEqual(opening.requested_gap, "")
        self.assertIn("企业画像", opening.message)

    def test_chat_answer_marks_scenario_update_without_resimulating(self) -> None:
        action = {
            "action": "answer",
            "profile_patch": {"site.VN.capacity": "5 GWh/year"},
            "gap_updates": [
                {
                    "gap_item": "Vietnam plant capacity",
                    "status": "resolved",
                    "answer": "5 GWh/year",
                    "source_turn": 1,
                }
            ],
            "affected_dimensions": ["resilience", "market_access"],
            "scenario_update_required": True,
        }
        agent, llm = self.make_agent(action)
        assessment = agent.run(make_company())
        with patch.object(
            agent,
            "resimulate",
            wraps=agent.resimulate,
        ) as resimulate:
            updated = agent.chat(
                assessment,
                ChatRequest(
                    message="越南基地年产能 5 GWh，主要出口美国。",
                    language="zh",
                ),
            )
        resimulate.assert_not_called()
        self.assertTrue(updated.chat_analysis.scenario_update_required)
        self.assertEqual(
            updated.company_intelligence,
            assessment.company_intelligence,
        )
        self.assertEqual(
            updated.chat_analysis.profile_patch["site.VN.capacity"],
            "5 GWh/year",
        )

    def test_context_updates_are_atomic_and_do_not_duplicate_raw_message(self) -> None:
        action = {
            "action": "answer",
            "context_updates": [
                {
                    "entity": "US",
                    "field": "utilization_rate",
                    "value": 0.45,
                    "unit": "ratio",
                    "information_type": "operational_fact",
                    "source_type": "management_estimate",
                    "verification_status": "unverified",
                },
                {
                    "entity": "North America",
                    "field": "demand_growth",
                    "value": "high",
                    "information_type": "demand_forecast",
                    "source_type": "management_estimate",
                    "verification_status": "unverified",
                },
                {
                    "entity": "management",
                    "field": "asian_dependency",
                    "value": "reduce",
                    "information_type": "strategic_preference",
                    "source_type": "user_input",
                    "verification_status": "user_confirmed",
                },
            ],
            "new_constraints": ["补充以下模拟数据，用于进一步分析。"],
            "scenario_update_required": True,
        }
        agent, _ = self.make_agent(action)
        assessment = agent.run(make_company())
        updated = agent.chat(
            assessment,
            ChatRequest(
                message=(
                    "美国工厂利用率45%，北美需求增长较快，"
                    "管理层希望降低亚洲依赖。"
                ),
                language="zh",
            ),
        )

        self.assertEqual(len(updated.context_updates), 3)
        self.assertTrue(
            all(item.update_status == "pending" for item in updated.context_updates)
        )
        self.assertEqual(updated.chat_analysis.new_constraints, [])
        self.assertNotIn(
            "补充以下模拟数据",
            [item.field for item in updated.context_updates],
        )

    def test_context_updates_deduplicate_and_flag_conflicts(self) -> None:
        update = {
            "entity": "KR",
            "field": "production_share",
            "value": 30,
            "unit": "percent",
            "information_type": "correction",
            "source_type": "user_input",
            "verification_status": "user_confirmed",
        }
        agent, _ = self.make_agent(
            {
                "action": "answer",
                "context_updates": [update],
                "scenario_update_required": True,
            }
        )
        assessment = agent.run(make_company())
        first = agent.chat(
            assessment,
            ChatRequest(message="韩国生产占比调整为30%。", language="zh"),
        )
        second = agent.chat(
            first,
            ChatRequest(message="韩国生产占比调整为30%。", language="zh"),
        )

        self.assertEqual(len(first.context_updates), 1)
        self.assertEqual(len(second.context_updates), 1)
        self.assertTrue(first.context_updates[0].conflict)
        self.assertEqual(first.context_updates[0].previous_value, 50)

    def test_context_updates_persist_and_apply_to_scenario_version(self) -> None:
        agent, _ = self.make_agent(
            {
                "action": "answer",
                "context_updates": [
                    {
                        "entity": "US",
                        "field": "utilization_rate",
                        "value": 0.45,
                        "unit": "ratio",
                        "information_type": "operational_estimate",
                        "source_type": "management_estimate",
                        "verification_status": "unverified",
                    }
                ],
                "scenario_update_required": True,
            }
        )
        assessment = agent.run(make_company())
        updated = agent.chat(
            assessment,
            ChatRequest(message="美国基地利用率45%。", language="zh"),
        )
        update_id = updated.context_updates[0].update_id
        restored = Assessment.model_validate_json(updated.model_dump_json())
        self.assertEqual(restored.context_updates[0].update_id, update_id)
        with TemporaryDirectory() as directory:
            repository = AssessmentRepository(Path(directory) / "assessment.db")
            repository.save(restored)
            restored = repository.get(restored.assessment_id)
            self.assertIsNotNone(restored)
            self.assertEqual(
                restored.context_updates[0].update_id,
                update_id,
            )

        rerun = agent.resimulate(
            restored,
            update_ids=[update_id],
            language="zh",
        )

        self.assertEqual(rerun.scenario_version, 2)
        self.assertEqual(rerun.context_updates[0].update_status, "applied")
        self.assertEqual(rerun.context_updates[0].scenario_version, 2)

    def test_context_update_delete_endpoint_removes_the_record(self) -> None:
        agent, _ = self.make_agent(
            {
                "action": "answer",
                "context_updates": [
                    {
                        "entity": "US",
                        "field": "utilization_rate",
                        "value": 0.45,
                        "information_type": "operational_estimate",
                        "source_type": "management_estimate",
                        "verification_status": "unverified",
                    }
                ],
                "scenario_update_required": True,
            }
        )
        assessment = agent.run(make_company())
        updated = agent.chat(
            assessment,
            ChatRequest(message="美国基地利用率45%。", language="zh"),
        )
        update_id = updated.context_updates[0].update_id
        with patch.object(main_module.repository, "get", return_value=updated), patch.object(
            main_module.repository,
            "save",
        ) as save:
            result = main_module.delete_context_update(
                updated.assessment_id,
                update_id,
            )
        save.assert_called_once()
        self.assertEqual(result.context_updates, [])

    def test_second_turn_sees_the_first_turn(self) -> None:
        agent, llm = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company())
        first = agent.chat(
            assessment,
            ChatRequest(message="第一轮问题", language="zh"),
        )
        agent.chat(
            first,
            ChatRequest(message="第二轮问题", language="zh"),
        )
        self.assertEqual(llm.seen_history, [0, 2])

    def test_chat_answer_is_capped_for_consultation_use(self) -> None:
        answer = DeepSeekLLM._bounded_chat_answer("影响。\n" + ("补充分析" * 400))
        self.assertLessEqual(len(answer), 1501)
        self.assertTrue(answer.endswith("…"))

    def test_resimulation_appends_system_change_note(self) -> None:
        agent, _ = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company(), language="zh")
        assessment = assessment.model_copy(
            update={
                "chat_history": [
                    ChatTurn(
                        role="user",
                        content="补充电芯自产比例。",
                        created_at="2026-10-09T00:00:00+00:00",
                    )
                ],
                "chat_analysis": ChatImpact(
                    scenario_update_required=True,
                    summary="补充电芯自产比例。",
                ),
            }
        )

        updated = agent.resimulate(
            assessment,
            additional_constraints=["电池电芯自产比例 78%"],
            language="zh",
        )

        self.assertTrue(updated.chat_analysis.scenario_recalculated)
        self.assertFalse(updated.chat_analysis.scenario_update_required)
        self.assertIn(
            "系统提示",
            updated.chat_analysis.scenario_change_summary,
        )
        self.assertIn("系统提示", updated.chat_history[-1].content)

    def test_pdf_humanises_nested_profile_patch(self) -> None:
        agent, _ = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company(), language="zh")
        assessment = assessment.model_copy(
            update={
                "chat_history": [
                    ChatTurn(
                        role="user",
                        content="电池自产比例 78%。",
                        created_at="2026-10-09T00:00:00+00:00",
                    ),
                    ChatTurn(
                        role="assistant",
                        content="已记录该信息。",
                        created_at="2026-10-09T00:00:01+00:00",
                    ),
                ],
                "chat_analysis": ChatImpact(
                    profile_patch={
                        "supply_chain": (
                            "{'battery_cell_self_production': "
                            "{'self_produced_ratio': 0.78}}"
                        )
                    },
                    scenario_update_required=False,
                ),
            }
        )

        pdf = build_assessment_pdf(assessment)
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf)).pages
        )

        self.assertIn("78%", text)
        self.assertNotIn("battery_cell_self_production", text)
        self.assertNotIn("{'self_produced_ratio'", text)

    def test_pdf_uses_key_whitelist_and_filters_internal_names(self) -> None:
        agent, _ = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company(), language="zh")
        assessment = assessment.model_copy(
            update={
                "chat_history": [
                    ChatTurn(
                        role="assistant",
                        content="已记录补充信息。",
                        created_at="2026-10-09T00:00:00+00:00",
                    )
                ],
                "chat_analysis": ChatImpact(
                    profile_patch={
                        "primary": "BATTERY_CELL",
                        "evaluation_scope": "XPeng Inc.",
                        "scope_caveats": "本轮澄清的是部门职责范围。",
                        "value_chain_role": "oem_integrator",
                    },
                    scenario_update_required=False,
                ),
            }
        )

        pdf = build_assessment_pdf(assessment)
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf)).pages
        )

        self.assertIn("核心角色：电池电芯制造", text)
        self.assertIn("评估范围：XPeng Inc.", text)
        self.assertIn("范围警示：本轮澄清的是部门职责范围。", text)
        self.assertNotIn("primary:", text)
        self.assertNotIn("evaluation_scope:", text)
        self.assertNotIn("scope_caveats:", text)
        self.assertNotIn("value_chain_role", text)
        self.assertNotIn("oem_integrator", text)

    def test_chat_prompt_is_neutral_about_score_state(self) -> None:
        prompt = DeepSeekLLM._chat_answer_system_prompt("zh")
        self.assertIn("只陈述逻辑推演", prompt)
        self.assertIn("严禁声明正式评分是否已经更新", prompt)
        self.assertNotIn("当前正式评分尚未更新", prompt)
        self.assertNotIn("请点击“重新模拟”", prompt)
        self.assertNotIn("分数维持不变", prompt)

    def test_pdf_renders_chat_markdown_and_summary_headers(self) -> None:
        agent, _ = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company(), language="zh")
        assessment = assessment.model_copy(
            update={
                "chat_history": [
                    ChatTurn(
                        role="assistant",
                        content=(
                            "**关键结论**\n\n"
                            "- 成本压力上升\n"
                            "- 供应链韧性下降"
                        ),
                        created_at="2026-10-09T00:00:00+00:00",
                    )
                ]
            }
        )

        pdf = build_assessment_pdf(assessment)
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf)).pages
        )

        self.assertIn("关键结论", text)
        self.assertIn("成本压力上升", text)
        self.assertNotIn("**关键结论**", text)
        self.assertIn("推荐方案", text)
        self.assertIn("主要优势", text)

    def test_pdf_contains_score_breakdown_and_chat_history(self) -> None:
        agent, _ = self.make_agent(
            {"action": "answer", "scenario_update_required": False}
        )
        assessment = agent.run(make_company(), language="zh")
        assessment = assessment.model_copy(
            update={
                "chat_history": [
                    ChatTurn(
                        role="user",
                        content="越南基地产能是多少？",
                        created_at="2026-10-06T00:00:00+00:00",
                    ),
                    ChatTurn(
                        role="assistant",
                        content="请补充越南基地年产能和出口市场。",
                        created_at="2026-10-06T00:00:01+00:00",
                    ),
                ],
                "chat_analysis": ChatImpact(
                    gap_updates=[
                        GapUpdate(
                            gap_item="Vietnam plant capacity",
                            status="partial",
                            answer="用户尚未确认具体产能",
                        )
                    ],
                    scenario_update_required=False,
                ),
            }
        )
        pdf = build_assessment_pdf(assessment)
        text = "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(pdf)).pages
        )
        self.assertIn("五维评分明细", text)
        self.assertIn("越南基地产能是多少", text)
        self.assertIn("请补充越南基地年产能和出口市场", text)


if __name__ == "__main__":
    unittest.main()
