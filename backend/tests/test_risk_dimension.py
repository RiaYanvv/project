from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent import AgentService
from app.llm import MockLLM
from app.risk_dimension import (
    COUNTRY_CN_BY_CODE,
    RISK_DIMENSIONS,
    DimensionContext,
    RiskDimensionRetriever,
    dimension_question,
    normalize_evidence_id,
    risk_retrieval_enabled,
)
from app.schemas import CompanyInput, RetrievalQuery, RetrievedEvidence


def evidence(evidence_id: str, title: str, score: int = 50) -> RetrievedEvidence:
    return RetrievedEvidence(
        evidence_id=evidence_id,
        title=title,
        source_type="Policy",
        publisher="publisher",
        country_region="CN",
        publication_date="2026-01-01",
        authority_level="S",
        topic="policy",
        content=f"{title} content",
        relevance_score=score,
        is_mock=False,
    )


class FakeProvider:
    """Returns a fixed shortlist per risk dimension, keyed by the query text."""

    def __init__(self, by_keyword: dict[str, list[RetrievedEvidence]]) -> None:
        self.by_keyword = by_keyword
        self.queries: list[RetrievalQuery] = []

    def search(self, query: RetrievalQuery) -> list[RetrievedEvidence]:
        self.queries.append(query)
        for risk, keywords in RISK_DIMENSIONS.items():
            if keywords.split()[0] in query.decision_question:
                return list(self.by_keyword.get(risk, []))
        return []


def base_query() -> RetrievalQuery:
    return RetrievalQuery(
        industry="battery_ev",
        products=["question"],
        home_country="CN",
        production_countries=["VN"],
        target_markets=["US"],
        decision_question="question",
        limit=10,
    )


class NormalizeEvidenceIdTest(unittest.TestCase):
    def test_strips_chunk_and_prefix(self) -> None:
        self.assertEqual(normalize_evidence_id("EVD-BIS_001-C0002"), "BIS_001")
        self.assertEqual(normalize_evidence_id("TRD_003"), "TRD_003")
        self.assertEqual(normalize_evidence_id(None), "")


class DimensionContextTest(unittest.TestCase):
    def test_from_company_uses_host_countries_only(self) -> None:
        company = CompanyInput.model_validate(
            {
                "company_name": "示例新能源",
                "industry": "battery_ev",
                "products": ["EV battery"],
                "home_country": "CN",
                "production_locations": [
                    {"country": "CN", "production_share": 40},
                    {"country": "TH", "production_share": 30},
                    {"country": "MY", "production_share": 30},
                ],
                "target_markets": ["US"],
                "decision_question": "是否继续扩产？",
                "time_horizon": "6_18_months",
                "priorities": [{"dimension": "cost_reduction", "weight": 5}],
            }
        )
        context = DimensionContext.from_company(company)
        self.assertEqual(context.company, "示例新能源")
        self.assertEqual(context.host, "泰国 马来西亚")
        self.assertNotIn("中国", context.host)

    def test_every_risk_dimension_has_a_question(self) -> None:
        context = DimensionContext(company="BYD", host="泰国")
        for risk in RISK_DIMENSIONS:
            question = dimension_question(risk, context)
            self.assertTrue(question.startswith("BYD 泰国"))
            self.assertTrue(question.endswith("风险 证据"))


class RiskDimensionRetrieverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = FakeProvider(
            {
                "Trade Risk": [evidence("CASE_002", "反规避裁定"), evidence("NOPE_001", "无关")],
                "Political Risk": [evidence("NOPE_001", "无关")],
                "Supply Chain Risk": [evidence("TRD_003", "中间品贸易流", score=20)],
                "Regulatory Risk": [],
                "Market Access Risk": [evidence("IRS_001", "FEOC 规则")],
                "Operational Risk": [],
            }
        )
        self.registry = {
            "CASE_002": {"related_risk": ["Trade Risk", "Market Access Risk"]},
            "TRD_003": {"related_risk": ["Supply Chain Risk"]},
            "IRS_001": {"related_risk": ["Market Access Risk"]},
            "NOPE_001": {"related_risk": []},
        }
        self.retriever = RiskDimensionRetriever(self.provider, self.registry, per_dimension_k=5)

    def test_only_tag_confirmed_evidence_counts(self) -> None:
        result = self.retriever.retrieve(base_query(), DimensionContext(company="BYD", host="越南"))
        self.assertEqual(
            result.detected_risks,
            frozenset({"Trade Risk", "Supply Chain Risk", "Market Access Risk"}),
        )
        self.assertNotIn("Political Risk", result.detected_risks)
        self.assertNotIn("Regulatory Risk", result.detected_risks)
        self.assertNotIn("Operational Risk", result.detected_risks)

    def test_evidence_carries_the_confirmed_dimensions(self) -> None:
        result = self.retriever.retrieve(base_query(), DimensionContext(company="BYD", host="越南"))
        by_id = {item.evidence_id: item for item in result.items}
        self.assertEqual(by_id["CASE_002"].risk_dimension_confirmed, ("Trade Risk",))
        self.assertEqual(by_id["TRD_003"].risk_dimension_confirmed, ("Supply Chain Risk",))
        # 词面分很低也被保留：相关性由标签背书，不是由词面分背书
        self.assertEqual(by_id["TRD_003"].relevance_score, 20)

    def test_findings_report_source_level_ids(self) -> None:
        chunked = FakeProvider({"Trade Risk": [evidence("EVD-CASE_002-C0007", "分段")]})
        retriever = RiskDimensionRetriever(chunked, self.registry)
        result = retriever.retrieve(base_query())
        self.assertEqual(result.findings["Trade Risk"].evidence_ids, ("CASE_002",))
        # 产品侧仍拿到 chunk 级条目，identity 不被压平
        self.assertEqual(result.items[0].evidence_id, "EVD-CASE_002-C0007")

    def test_missing_registry_fails_closed(self) -> None:
        retriever = RiskDimensionRetriever(self.registry and FakeProvider({}), {})
        result = retriever.retrieve(base_query())
        self.assertEqual(result.detected_risks, frozenset())
        self.assertFalse(result.registry_backed)

    def test_query_keeps_base_constraints(self) -> None:
        self.retriever.retrieve(base_query(), DimensionContext(company="BYD", host="越南"))
        for query in self.provider.queries:
            self.assertEqual(query.industry, "battery_ev")
            self.assertEqual(query.production_countries, ["VN"])
            self.assertEqual(query.limit, 5)

    def test_every_dimension_is_probed_once(self) -> None:
        self.retriever.retrieve(base_query())
        self.assertEqual(len(self.provider.queries), len(RISK_DIMENSIONS))


class RiskRetrievalToggleTest(unittest.TestCase):
    def test_default_is_on_and_can_be_disabled(self) -> None:
        original = os.environ.pop("RISK_DIMENSION_RETRIEVAL", None)
        try:
            self.assertTrue(risk_retrieval_enabled())
            os.environ["RISK_DIMENSION_RETRIEVAL"] = "0"
            self.assertFalse(risk_retrieval_enabled())
        finally:
            if original is None:
                os.environ.pop("RISK_DIMENSION_RETRIEVAL", None)
            else:
                os.environ["RISK_DIMENSION_RETRIEVAL"] = original


class AgentDimensionEvidenceTest(unittest.TestCase):
    def test_agent_merges_dimension_evidence_into_the_risk_view(self) -> None:
        provider = FakeProvider(
            {
                "Trade Risk": [evidence("CASE_002", "反规避裁定")],
                "Regulatory Risk": [evidence("BIS_002", "关联企业规则暂停")],
            }
        )
        retriever = RiskDimensionRetriever(
            provider,
            {
                "CASE_002": {"related_risk": ["Trade Risk"]},
                "BIS_002": {"related_risk": ["Regulatory Risk"]},
            },
        )
        agent = AgentService(
            retrieval=provider, llm=MockLLM(), risk_dimension=retriever
        )
        company = CompanyInput.model_validate(
            {
                "company_name": "BYD",
                "industry": "battery_ev",
                "products": ["EV battery"],
                "home_country": "CN",
                "production_locations": [{"country": "TH", "production_share": 100}],
                "target_markets": ["US"],
                "decision_question": "是否将产能转移至泰国？",
                "time_horizon": "6_18_months",
                "priorities": [{"dimension": "cost_reduction", "weight": 5}],
            }
        )
        items = agent._dimension_evidence(base_query(), company)
        self.assertEqual({item.evidence_id for item in items}, {"CASE_002", "BIS_002"})
        self.assertTrue(all(item.risk_dimension_confirmed for item in items))

    def test_dimension_provider_bypasses_the_task4_optimizer(self) -> None:
        import tempfile

        from app.knowledge import KnowledgeRepository
        from app.retrieval import HybridRetrievalProvider
        from app.retrieval_optimizer import OptimizationConfig, RetrievalOptimizer

        with tempfile.TemporaryDirectory() as tmp:
            repository = KnowledgeRepository(Path(tmp) / "kb.db")
            optimizer = RetrievalOptimizer(
                registry={}, config=OptimizationConfig(True, True, True)
            )
            optimized = HybridRetrievalProvider(
                repository=repository, optimizer=optimizer
            )
            agent = AgentService(retrieval=optimized, llm=MockLLM())
            self.assertIs(optimized.optimizer, optimizer)
            dimension_provider = agent._dimension_provider()
            self.assertIsNone(dimension_provider.optimizer)
            self.assertIs(dimension_provider.repository, repository)

            # 没有优化层时按原样返回，不额外包一层
            plain = HybridRetrievalProvider(repository=repository)
            self.assertIs(
                AgentService(retrieval=plain, llm=MockLLM())._dimension_provider(), plain
            )
            # 非 HybridRetrievalProvider（测试替身）也不受影响
            fake = FakeProvider({})
            self.assertIs(
                AgentService(retrieval=fake, llm=MockLLM())._dimension_provider(), fake
            )

    def test_agent_skips_dimension_evidence_when_toggle_is_off(self) -> None:
        provider = FakeProvider({"Trade Risk": [evidence("CASE_002", "反规避裁定")]})
        retriever = RiskDimensionRetriever(
            provider, {"CASE_002": {"related_risk": ["Trade Risk"]}}
        )
        agent = AgentService(retrieval=provider, llm=MockLLM(), risk_dimension=retriever)
        company = CompanyInput.model_validate(
            {
                "company_name": "BYD",
                "industry": "battery_ev",
                "products": ["EV battery"],
                "home_country": "CN",
                "production_locations": [{"country": "TH", "production_share": 100}],
                "target_markets": ["US"],
                "decision_question": "是否将产能转移至泰国？",
                "time_horizon": "6_18_months",
                "priorities": [{"dimension": "cost_reduction", "weight": 5}],
            }
        )
        os.environ["RISK_DIMENSION_RETRIEVAL"] = "0"
        try:
            self.assertEqual(agent._dimension_evidence(base_query(), company), [])
        finally:
            os.environ.pop("RISK_DIMENSION_RETRIEVAL", None)


if __name__ == "__main__":
    unittest.main()
