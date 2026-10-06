from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.llm import MockLLM
from app.pdf_report import build_assessment_pdf
from app.retrieval import MockRetrievalProvider
from app.schemas import (
    ChatImpact,
    ChatRequest,
    ChatTurn,
    CompanyInput,
    GapUpdate,
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
        return "已记录新增信息，并更新情景分析。"


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

    def test_chat_answer_triggers_scenario_resimulation(self) -> None:
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
        resimulate.assert_called_once()
        self.assertTrue(updated.chat_analysis.scenario_update_required)
        self.assertEqual(
            updated.chat_analysis.profile_patch["site.VN.capacity"],
            "5 GWh/year",
        )

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
