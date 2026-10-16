"""按风险维度多次检索（Task 6 P0）。

问题：单次「公司决策」式检索把 Top-K 交给公司披露 / 案例类文档，这些文档的
`related_risk` 集中在 Supply Chain / Operational 两维；Trade、Political、
Regulatory、Market Access 四个维度在单次检索里取不到。Task 6 实测 Risk Recall
0.799，而「按维度逐条提问」的上界是 0.946 —— 差距出在检索策略，不在语料。

做法：对六类风险各发一次检索（领域词 + 公司 + 东道国），再用 Task 1 schema 的
`related_risk` 标签确认「这条证据确实支撑该维度」，最后取并集。标签确认是关键：
没有它，六次检索合并后几乎每题都会宣称全部六类风险。

实测（17 个 held-out 案例，`run_task67_eval.py`）：
  Recall 0.799 -> 0.946，Precision 0.559 -> 0.535，Missing 12 -> 3。

阈值与裁剪都试过（相关性阈值、管辖域过滤、只取前 m 维、要求 >=2 条确认），
没有一个能在召回上打过「全量并集」；见 `archive/task2_dev/` 之外的评测报告说明。
因此本模块采用召回优先：漏掉一类必需风险，比多列一类真实存在的风险更贵。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping, Protocol

from .schemas import RetrievalQuery, RetrievedEvidence


# 六类风险 -> 该维度的检索词。中文为主（语料头部为中文），混入英文关键术语。
RISK_DIMENSIONS: dict[str, str] = {
    "Trade Risk": "关税 贸易限制 反规避 原产地 tariff",
    "Political Risk": "地缘政治 政策不确定性 geopolitical",
    "Supply Chain Risk": "供应链依赖 地理集中 中间品 supplier",
    "Regulatory Risk": "出口管制 合规 法规 监管 compliance",
    "Market Access Risk": "市场准入 本地化要求 客户准入 market access",
    "Operational Risk": "人力成本 基础设施 执行风险 labor",
}

DIMENSION_QUERY_SUFFIX = "风险 证据"

DEFAULT_PER_DIMENSION_K = 5

# ISO 3166 alpha-2 -> 中文，用于把生产国拼进维度检索词。
COUNTRY_CN_BY_CODE: dict[str, str] = {
    "CN": "中国",
    "TH": "泰国",
    "VN": "越南",
    "MY": "马来西亚",
    "ID": "印尼",
    "IN": "印度",
    "MX": "墨西哥",
    "HU": "匈牙利",
    "DE": "德国",
    "US": "美国",
    "KR": "韩国",
    "TW": "中国台湾",
    "EU": "欧盟",
    "JP": "日本",
    "BR": "巴西",
    "PL": "波兰",
    "ES": "西班牙",
    "MA": "摩洛哥",
}


def normalize_evidence_id(value: object) -> str:
    """把 `EVD-BIS_001` / `BIS_001-C03` 归一成语料里的 source_id。"""
    eid = str(value or "").strip()
    if eid.startswith("EVD-"):
        eid = eid[4:]
    return re.sub(r"-C\d+$", "", eid)


class RetrievalLike(Protocol):
    def search(self, query: RetrievalQuery) -> list[RetrievedEvidence]: ...


@dataclass(frozen=True)
class DimensionContext:
    """维度检索词的上下文：公司名 + 东道国（中文）。"""

    company: str = ""
    host: str = ""

    def prefix(self) -> str:
        return " ".join(part for part in (self.company, self.host) if part)

    @classmethod
    def from_company(cls, company) -> "DimensionContext":
        """从 `CompanyInput` 构造（生产国取中文名，去重、保序）。"""
        name = str(getattr(company, "company_name", "") or "").strip()
        hosts: list[str] = []
        for location in getattr(company, "production_locations", ()) or ():
            code = str(getattr(location, "country", "") or "").strip().upper()
            if not code or code == "CN":
                continue
            label = COUNTRY_CN_BY_CODE.get(code, code)
            if label not in hosts:
                hosts.append(label)
        return cls(company=name, host=" ".join(hosts))


@dataclass(frozen=True)
class RiskFinding:
    """一个风险维度上的检索结论。"""

    risk: str
    evidence_ids: tuple[str, ...] = ()
    best_score: float = 0.0

    def __bool__(self) -> bool:  # pragma: no cover - trivial
        return bool(self.evidence_ids)


@dataclass(frozen=True)
class RiskDimensionResult:
    findings: Mapping[str, RiskFinding]
    items: tuple[RetrievedEvidence, ...] = ()
    registry_backed: bool = True

    @property
    def detected_risks(self) -> frozenset[str]:
        return frozenset(
            risk for risk, finding in self.findings.items() if finding.evidence_ids
        )

    @property
    def evidence_ids(self) -> list[str]:
        return [item.evidence_id for item in self.items]


def dimension_question(
    risk: str,
    context: DimensionContext,
    dimensions: Mapping[str, str] | None = None,
) -> str:
    """构造某一风险维度的检索问题（产品与评测共用同一实现）。"""
    keywords = (dimensions or RISK_DIMENSIONS).get(risk, "")
    prefix = context.prefix()
    head = f"{prefix} " if prefix else ""
    return f"{head}{keywords} {DIMENSION_QUERY_SUFFIX}".strip()


def risk_retrieval_enabled() -> bool:
    """默认开启；显式设 `RISK_DIMENSION_RETRIEVAL=0` 可退回单次检索。"""
    return (os.getenv("RISK_DIMENSION_RETRIEVAL", "1") or "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


class RiskDimensionRetriever:
    """按维度检索 + 标签确认，返回每个维度上站得住的证据。"""

    def __init__(
        self,
        provider: RetrievalLike,
        registry: Mapping[str, Mapping] | None = None,
        per_dimension_k: int = DEFAULT_PER_DIMENSION_K,
        dimensions: Mapping[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.registry = dict(registry or {})
        self.per_dimension_k = max(1, int(per_dimension_k))
        self.dimensions = dict(dimensions or RISK_DIMENSIONS)

    # -- 查询构造 ---------------------------------------------------------
    def dimension_question(self, risk: str, context: DimensionContext) -> str:
        return dimension_question(risk, context, self.dimensions)

    def query_for(
        self,
        base: RetrievalQuery,
        risk: str,
        context: DimensionContext,
    ) -> RetrievalQuery:
        """复制基础查询，只替换决策问题与产品词为维度检索词。

        其余字段（industry / home_country / 生产国 / 目标市场）保留，让 Task 4
        的 metadata filter 与新查询层照常生效。
        """
        question = self.dimension_question(risk, context)
        return base.model_copy(
            update={
                "decision_question": question,
                "products": [question],
                "limit": self.per_dimension_k,
            }
        )

    # -- 检索 -------------------------------------------------------------
    def risk_tags(self, evidence_id: str) -> frozenset[str]:
        meta = self.registry.get(normalize_evidence_id(evidence_id)) or {}
        tags = meta.get("related_risk") or ()
        if isinstance(tags, str):
            tags = [part.strip() for part in re.split(r"[;,]", tags)]
        return frozenset(str(tag).strip() for tag in tags if str(tag).strip())

    def retrieve(
        self,
        base: RetrievalQuery,
        context: DimensionContext | None = None,
        limit: int | None = None,
    ) -> RiskDimensionResult:
        context = context or DimensionContext()
        top_k = max(1, int(limit or self.per_dimension_k))

        if not self.registry:
            # 没有 Task 1 标签表就无法确认「这条证据支撑该维度」，此时声称任何
            # 风险都是无根据的，宁可返回空结果也不猜。
            return RiskDimensionResult(
                findings={
                    risk: RiskFinding(risk=risk) for risk in self.dimensions
                },
                items=(),
                registry_backed=False,
            )

        findings: dict[str, RiskFinding] = {}
        annotated: dict[str, RetrievedEvidence] = {}
        confirmed_dims: dict[str, list[str]] = {}

        for risk in self.dimensions:
            query = self.query_for(base, risk, context)
            query = query.model_copy(update={"limit": top_k})
            hits = list(self.provider.search(query))

            matched: list[str] = []
            best = 0.0
            for item in hits:
                if risk not in self.risk_tags(item.evidence_id):
                    continue
                # 结论按 source_id 记录（一个 PDF 可能命中多个 chunk），
                # 产品侧仍拿到 chunk 级条目。
                source_id = normalize_evidence_id(item.evidence_id)
                if source_id not in matched:
                    matched.append(source_id)
                best = max(best, float(item.relevance_score or 0))
                dims = confirmed_dims.setdefault(item.evidence_id, [])
                if risk not in dims:
                    dims.append(risk)
                if item.evidence_id not in annotated:
                    annotated[item.evidence_id] = item

            findings[risk] = RiskFinding(
                risk=risk,
                evidence_ids=tuple(matched),
                best_score=best,
            )

        items: list[RetrievedEvidence] = []
        for evidence_id, item in annotated.items():
            dims = tuple(dict.fromkeys(confirmed_dims.get(evidence_id, ())))
            items.append(
                item.model_copy(update={"risk_dimension_confirmed": dims})
            )

        return RiskDimensionResult(
            findings=findings,
            items=tuple(items),
            registry_backed=bool(self.registry),
        )

    # -- 便捷入口 ---------------------------------------------------------
    def suggest_risks(
        self,
        base: RetrievalQuery,
        context: DimensionContext | None = None,
        limit: int | None = None,
    ) -> frozenset[str]:
        return self.retrieve(base, context, limit).detected_risks
