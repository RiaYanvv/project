"""Task 4.1 — metadata filtering.

Turns a free-text decision question into a structured filter spec and applies
it to the retrieval candidate pool, using the Task 4 schema derived from
Task 1 (``backend/app/evidence_metadata.py``).

Example
-------
    "CATL Vietnam factory risk"
      -> industry: EV_Battery, country: VN, topic: supply_chain,
         risk: Operational Risk

Rule tiers (see ``FILTER_POLICY``):

* HARD  F1 — macro-drift removal.  Evidence whose Task 1 topic is
  对外投资 / 宏观风险 is removed when the question carries no investment /
  macro trigger.  A recall guard re-admits the dropped pool if hard filtering
  would starve the result set.
* SOFT  F2 — industry focus.  ``off_focus`` evidence (cross-industry
  analogue: solar / optical module / metal casting) is demoted; ''core''
  evidence is promoted.  Shipped at 0 on the expanded corpus: every source of
  ``core`` evidence now includes case narratives, so an unconditional boost
  promoted cases over policy evidence.
* SOFT  F3 — geography.  Evidence tied to a different country is demoted.
  Never a hard filter: in this corpus ``country_region`` is the *issuing*
  jurisdiction, not the subject of the case.
* SOFT  F4 — risk alignment.  Evidence whose ``related_risk`` intersects the
  detected risks is promoted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .evidence_metadata import load_registry

# Task 4 spec topic vocabulary.
SPEC_TOPICS = (
    "tariff",
    "export_control",
    "trade_policy",
    "investment_policy",
    "market_access",
    "supply_chain",
    "supplier_dependency",
    "labor",
    "logistics",
    "regulation",
    "localization_policy",
)

# Spec topic -> admissible Task 1 (Chinese) topics for a question of that topic.
# This mirrors the evaluation harness' topical admissibility standard in
# run_task3_baseline.py::TOPIC_MAP; it is asserted equal in run_task4_eval.py.
TOPIC_BUCKETS: dict[str, set[str]] = {
    "supply_chain": {"供应链布局", "贸易流", "原产地与转运"},
    "supplier_dependency": {"供应链布局", "贸易流", "原产地与转运"},
    "export_control": {"出口管制", "出口管制/关税", "原产地与转运"},
    "trade_policy": {"原产地与转运", "反规避", "贸易流", "出口管制/关税", "供应链布局"},
    "investment_policy": {"对外投资", "宏观风险"},
    "market_access": {"原产地与转运", "反规避", "贸易流", "出口管制", "市场准入", "本地化政策"},
    "regulation": {"出口管制", "出口管制/关税", "原产地与转运"},
    "localization_policy": {"本地化政策", "市场准入", "原产地与转运", "供应链布局", "贸易流"},
    "labor": {"劳工", "供应链布局", "宏观风险"},
    "logistics": {"物流", "供应链布局", "贸易流", "原产地与转运"},
    "tariff": {"关税", "出口管制/关税", "原产地与转运", "贸易流"},
}

# Query lexicon: phrase -> spec topic(s).
TOPIC_LEXICON: dict[str, tuple[str, ...]] = {
    "export_control": (
        "出口管制", "出口许可", "管制清单", "实体清单", "限制清单", "受限方",
        "两用物项", "最终用户", "穿透规则", "关联企业规则", "entity list",
        "export control", "dual-use", "end-user", "affiliates rule",
    ),
    "tariff": ("关税", "加征", "301", "232", "tariff", "section 301"),
    "trade_policy": (
        "反规避", "转运", "原产地", "贸易救济", "反倾销", "反补贴", "双反",
        "贸易摩擦", "贸易政策", "circumvention", "transshipment",
        "country of origin", "trade remedy", "anti-dumping",
    ),
    "investment_policy": (
        "对外投资", "境外投资", "投资审查", "跨境投资", "海外投资", "国际投资",
        "投资环境", "投资趋势", "投资决策", "对外投资制度",
        "外资安全审查", "投资安全审查", "外资审查", "安全审查", "外资准入",
        "收购", "并购",
        "地缘经济", "国际组织", "宏观", "全球贸易", "全球经济", "世界经济",
        "贸易环境", "贸易增速", "贸易增长", "全球投资", "跨境",
        "outbound investment", "fdi", "geoeconomic", "global trade",
        "macroeconomic", "international organisation", "international organization",
        "cross-border investment", "foreign investment screening",
        "investment screening", "fdi screening", "foreign direct investment",
    ),
    "market_access": (
        "市场准入", "进入美国市场", "出口美国", "进入欧盟", "客户准入", "合规要求",
        "出口", "export to", "exporting to", "exporting its", "entering the",
        "market access", "compliance requirement",
    ),
    "supply_chain": (
        "供应链", "产能转移", "海外建厂", "海外工厂", "生产基地", "扩产", "产能",
        "布局", "搬迁", "工厂", "建厂", "manufacturer", "manufacturers",
        "manufacturing", "production", "factory", "factories", "plant",
        "relocation", "production footprint", "overseas factory",
        "supply chain", "capacity",
    ),
    "supplier_dependency": (
        "供应依赖", "中间品", "依赖中国", "供应商集中", "地理集中", "国产化",
        "supplier dependence", "intermediate input", "concentration",
    ),
    "regulation": ("法规", "监管", "电池法规", "标准", "battery regulation", "regulatory"),
    "localization_policy": ("本地化", "国产化要求", "local content", "localization"),
    "labor": ("劳工", "用工", "劳动力", "labor"),
    "logistics": ("物流", "运输", "港口", "logistics"),
}

# Query lexicon: phrase -> risk category.
RISK_LEXICON: dict[str, tuple[str, ...]] = {
    "Trade Risk": ("关税", "贸易", "反规避", "转运", "反倾销", "tariff", "trade risk"),
    "Political Risk": ("地缘", "政治", "政策不确定", "geopolitical", "political"),
    "Supply Chain Risk": ("供应链", "供应依赖", "中间品", "产能", "supply chain"),
    "Regulatory Risk": ("监管", "合规", "出口管制", "法规", "compliance", "regulatory"),
    "Market Access Risk": ("市场准入", "准入", "出口美国", "market access"),
    "Operational Risk": ("运营", "人力", "基础设施", "执行风险", "operational", "labor"),
}

COUNTRY_LEXICON: dict[str, str] = {
    "中国": "CN", "大陆": "CN", "国内": "CN", "china": "CN", "chinese": "CN",
    "美国": "US", "对美": "US", "美国市场": "US", "united states": "US", "u.s.": "US", "us ": "US",
    "越南": "VN", "vietnam": "VN",
    "泰国": "TH", "thailand": "TH",
    "马来西亚": "MY", "malaysia": "MY",
    "印尼": "ID", "印度尼西亚": "ID", "indonesia": "ID",
    "印度": "IN", "india": "IN",
    "墨西哥": "MX", "mexico": "MX",
    "柬埔寨": "KH", "cambodia": "KH",
    "欧盟": "EU", "欧洲": "EU", "eu ": "EU", "europe": "EU",
    "东南亚": "SEA", "southeast asia": "SEA",
}

INDUSTRY_LEXICON: dict[str, tuple[str, ...]] = {
    "EV_Battery": (
        "电池", "电芯", "锂电", "动力电池", "battery", "batteries", "ev battery",
        "lithium-ion", "cell",
    ),
    "Battery_Materials": ("正极", "负极", "隔膜", "电解液", "cathode", "anode", "separator"),
    "Energy_Storage": ("储能", "光伏", "太阳能", "energy storage", "solar"),
    "Automotive": ("整车", "汽车", "车企", "automotive", "vehicle maker"),
}

EVIDENCE_TYPE_LEXICON: dict[str, tuple[str, ...]] = {
    "Case Study": ("案例", "实例", "个案", "case"),
    "News": ("报道", "新闻", "媒体", "news", "reported"),
    "Policy": ("政策", "法规", "规定", "行政令", "policy", "regulation"),
    "Trade Data": ("贸易数据", "进出口数据", "trade data", "comtrade"),
}

# Spec topic -> risk categories it implies when the query text names no risk.
IMPLIED_RISK: dict[str, tuple[str, ...]] = {
    "export_control": ("Regulatory Risk", "Market Access Risk"),
    "tariff": ("Trade Risk",),
    "trade_policy": ("Trade Risk", "Market Access Risk"),
    "investment_policy": ("Political Risk", "Regulatory Risk"),
    "market_access": ("Market Access Risk", "Trade Risk"),
    "supply_chain": ("Supply Chain Risk", "Operational Risk"),
    "supplier_dependency": ("Supply Chain Risk",),
    "regulation": ("Regulatory Risk",),
    "labor": ("Operational Risk",),
    "logistics": ("Supply Chain Risk", "Operational Risk"),
    "localization_policy": ("Regulatory Risk", "Market Access Risk"),
}

# Task 1 topics that Task 3 §2.4 identified as "macro drift": they show up in
# unrelated questions because their topical similarity is over-estimated.
MACRO_TOPICS = {"对外投资", "宏观风险"}

FILTER_POLICY = """\
Task 4.1 metadata filter policy
================================
F1 macro-drift rule (default: SOFT demote, optional HARD drop)
    Evidence whose Task 1 topic is 对外投资 / 宏观风险 is demoted when the
    question carries NO investment / macro / global-economy trigger.  These are
    exactly the documents Task 3 §2.4 flagged as drifting into unrelated
    questions (UNCTAD / IMF / WEF / McKinsey recalled for tariff and origin
    questions).
    `macro_policy="drop"` is the shipped default (measured on the expanded
    corpus).  Note the side effect: it lowers the harness' Entity Precision,
    because those macro documents mention the generic entities
    (China / United States) the metric credits as on-target.  A recall guard
    re-admits the dropped pool whenever fewer than `min_pool` chunks would
    survive.
F2 (SOFT) topic admissibility
    Demote evidence whose Task 1 topic is outside the admissible bucket of the
    detected query topics.  NEVER dropped: gold evidence can legitimately sit
    outside the bucket - the solar anti-circumvention cases are gold for
    supply-chain questions, and the optical-module cases are this corpus'
    only China+1 company cases.
F3 (SOFT) industry focus
    off_focus evidence (solar / optical module / metal casting analogue)
    is demoted; core EV-battery evidence is promoted.
F4 (SOFT) geography
    Evidence matching the detected target geography is promoted; evidence whose
    issuing jurisdiction is disjoint is demoted.  Never dropped: in this corpus
    `country_region` is the *issuer*, not the subject of the case.
F5 (SOFT) risk alignment
    Evidence whose related_risk intersects the detected risks is promoted.
F6 (SOFT) evidence type
    Evidence whose Task 1 source_type maps to the type the question asks for
    (案例 -> Case Study/News, 政策 -> Policy, 数据 -> Trade Data) is promoted.

Design note (why F1 is narrow and F2 is soft)
---------------------------------------------
An earlier revision hard-filtered on the full topic-admissibility bucket.
It raised Precision@5 but cut Recall@10 sharply (to ~0.72), because a large
share of gold evidence sits outside the bucket its own question's topic
implies (Q003's gold is the solar anti-circumvention case, and the
optical-module cases are still gold for the China+1 questions).  Filtering
must therefore only remove evidence that is *structurally* unrelated, and
merely demote evidence that is *topically* marginal.
"""


@dataclass
class FilterSpec:
    industry: str = "EV_Battery"
    countries: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    evidence_types: tuple[str, ...] = ()
    raw_query: str = ""
    triggers: dict[str, list[str]] = field(default_factory=dict)

    @property
    def admissible_topics(self) -> set[str]:
        allowed: set[str] = set()
        for topic in self.topics:
            allowed |= TOPIC_BUCKETS.get(topic, set())
        return allowed

    @property
    def analogue_intent(self) -> bool:
        """True when the question explicitly asks for a cross-industry analogue."""
        low = (self.raw_query or "").lower()
        return any(
            term in low
            for term in ("反规避", "规避", "光伏", "太阳能", "组件", "光模块",
                         "circumvention", "solar", "photovoltaic")
        )

    @property
    def macro_intent(self) -> bool:
        """True when the question is about investment / macro / global trade."""
        return "investment_policy" in self.topics

    def as_dict(self) -> dict:
        return {
            "industry": self.industry,
            "country": "/".join(self.countries),
            "topic": "/".join(self.topics),
            "risk": "/".join(self.risks),
            "evidence_type": "/".join(self.evidence_types),
            "admissible_topics": "/".join(sorted(self.admissible_topics)),
        }


def _match(lexicon: dict[str, tuple[str, ...]], text: str) -> tuple[list[str], dict[str, list[str]]]:
    hits: list[str] = []
    triggers: dict[str, list[str]] = {}
    for key, phrases in lexicon.items():
        found = [p for p in phrases if p in text]
        if found:
            hits.append(key)
            triggers[key] = found
    return hits, triggers


def detect_topics(text: str) -> tuple[list[str], dict[str, list[str]]]:
    return _match(TOPIC_LEXICON, text.lower())


def detect_risks(text: str) -> tuple[list[str], dict[str, list[str]]]:
    return _match(RISK_LEXICON, text.lower())


def detect_countries(text: str) -> list[str]:
    low = text.lower()
    out: list[str] = []
    for phrase, code in COUNTRY_LEXICON.items():
        if phrase in low and code not in out:
            out.append(code)
    return out


def detect_industry(text: str) -> tuple[str | None, dict[str, list[str]]]:
    hits, triggers = _match(INDUSTRY_LEXICON, text.lower())
    return (hits[0] if hits else None), triggers


def detect_evidence_types(text: str) -> list[str]:
    hits, _ = _match(EVIDENCE_TYPE_LEXICON, text.lower())
    return hits


def parse_filter_spec(
    query_text: str,
    *,
    default_industry: str = "EV_Battery",
    default_country: str | None = None,
) -> FilterSpec:
    """Parse a free-text decision question into a structured filter spec."""
    text = query_text or ""
    topics, topic_triggers = detect_topics(text)
    risks, risk_triggers = detect_risks(text)
    industry, industry_triggers = detect_industry(text)
    countries = detect_countries(text)
    if not countries and default_country:
        countries = [default_country]
    implied: list[str] = []
    for topic in topics:
        for risk in IMPLIED_RISK.get(topic, ()):
            if risk not in risks and risk not in implied:
                implied.append(risk)
    risks = list(risks) + implied
    triggers = {**topic_triggers, **risk_triggers, **industry_triggers}
    return FilterSpec(
        industry=industry or default_industry,
        countries=tuple(countries),
        topics=tuple(topics),
        risks=tuple(risks),
        evidence_types=tuple(detect_evidence_types(text)),
        raw_query=text,
        triggers=triggers,
    )


@dataclass
class FilterDecision:
    evidence_id: str
    kept: bool
    reason: str
    topic: str
    topics: tuple[str, ...]

    def as_row(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "action": "keep" if self.kept else "drop",
            "rule": self.reason,
            "evidence_topic": self.topic,
            "evidence_topics": "; ".join(self.topics),
        }


class MetadataFilter:
    """Applies a :class:`FilterSpec` to a retrieval candidate pool."""

    def __init__(
        self,
        registry: dict[str, dict] | None = None,
        *,
        enabled: bool = True,
        min_pool: int = 60,
        industry_demote: float = 0.0,
        industry_boost: float = 0.0,
        country_demote: float = 0.02,
        # Corpus-tuned defaults (re-tuned 2026-10-12 after the Task 5 case
        # corpus was ingested; see task4_before_after.xlsx "Ablation").
        # topic_demote / industry_demote / industry_boost / global_demote all
        # default to 0: on the expanded corpus every soft boost or demotion of
        # *whole evidence types* moved Precision@5 and Recall@10 in opposite
        # directions, because the corpus now holds on-domain battery cases as
        # well as the cross-industry analogues that are still in the gold sets.
        # The surviving signals are F1 (macro-drift removal) and F4
        # (country_demote), which is the only pair that beats the baseline on
        # both Precision@5 and Recall@10.
        topic_demote: float = 0.0,
        macro_policy: str = "drop",
        macro_demote: float = 0.12,
        country_boost: float = 0.0,
        type_boost: float = 0.0,
        global_demote: float = 0.0,
        off_focus_policy: str = "keep",
        risk_boost: float = 0.03,
        authority_boost: float = 0.04,
    ):
        self.registry = registry if registry is not None else load_registry()
        self.enabled = enabled and bool(self.registry)
        self.min_pool = min_pool
        self.industry_demote = industry_demote
        self.industry_boost = industry_boost
        self.country_demote = country_demote
        self.topic_demote = topic_demote
        self.macro_policy = macro_policy
        self.macro_demote = macro_demote
        self.country_boost = country_boost
        self.type_boost = type_boost
        self.global_demote = global_demote
        self.off_focus_policy = off_focus_policy
        self.risk_boost = risk_boost
        self.authority_boost = authority_boost
        self.last_spec: FilterSpec | None = None
        self.last_decisions: list[FilterDecision] = []
        self.last_guard_triggered = False

    # ------------------------------------------------------------------
    def meta_for(self, evidence_id: str) -> dict | None:
        if not evidence_id:
            return None
        return self.registry.get(str(evidence_id).strip())

    def spec_for(self, query_text: str, **kwargs) -> FilterSpec:
        return parse_filter_spec(query_text, **kwargs)

    # ------------------------------------------------------------------
    def filter_chunks(self, chunks, spec: FilterSpec | None = None, query_text: str = ""):
        """Apply F1 (macro drift, hard) with a recall guard. Returns the kept pool."""
        self.last_spec = spec
        self.last_decisions = []
        self.last_guard_triggered = False
        if not self.enabled or spec is None or not chunks:
            return chunks

        allowed = spec.admissible_topics
        if allowed and not spec.macro_intent:
            allowed = allowed | MACRO_TOPICS

        kept, dropped = [], []
        for chunk in chunks:
            meta = self.meta_for(getattr(chunk, "source_id", ""))
            if meta is None:
                kept.append(chunk)
                continue
            topic = meta.get("topic_cn", "")
            if (
                self.off_focus_policy == "drop_unless_analogue"
                and meta.get("industry_scope") == "off_focus"
                and not spec.analogue_intent
            ):
                self.last_decisions.append(
                    FilterDecision(
                        evidence_id=meta["evidence_id"],
                        kept=False,
                        reason="F1b:off-focus-industry",
                        topic=topic,
                        topics=tuple(meta.get("topics", ())),
                    )
                )
                dropped.append(chunk)
                continue
            # F1: macro-drift evidence. "drop" removes it outright; the
            # default "demote" only pushes it down (see adjust_score).  A hard
            # drop measurably lowers the harness' Entity Precision because those
            # macro documents mention generic entities (China / United States)
            # that the metric credits as on-target.
            ok = (
                self.macro_policy != "drop"
                or spec.macro_intent
                or topic not in MACRO_TOPICS
            )
            self.last_decisions.append(
                FilterDecision(
                    evidence_id=meta["evidence_id"],
                    kept=ok,
                    reason="keep" if ok else "F1:macro-drift",
                    topic=topic,
                    topics=tuple(meta.get("topics", ())),
                )
            )
            (kept if ok else dropped).append(chunk)

        guard = len(kept) < self.min_pool and bool(dropped)
        self.last_guard_triggered = guard
        if guard:
            for decision in self.last_decisions:
                if not decision.kept:
                    decision.kept = True
                    decision.reason = "F1:re-admitted-by-recall-guard"
            return list(chunks)
        return kept

    # ------------------------------------------------------------------
    def adjust_score(self, score: float, chunk, spec: FilterSpec | None, text: str = "") -> float:
        """Apply F2/F3/F4 soft adjustments to a candidate's final score."""
        if not self.enabled or spec is None:
            return score
        meta = self.meta_for(getattr(chunk, "source_id", ""))
        if meta is None:
            return score

        topic_cn = meta.get("topic_cn")
        if (
            self.macro_policy == "demote"
            and not spec.macro_intent
            and topic_cn in MACRO_TOPICS
        ):
            score -= self.macro_demote

        allowed = spec.admissible_topics
        if allowed and meta.get("topic_cn") not in allowed:
            if not (spec.macro_intent and meta.get("topic_cn") in MACRO_TOPICS):
                score -= self.topic_demote

        if spec.industry == "EV_Battery":
            scope = meta.get("industry_scope")
            if scope == "off_focus":
                score -= self.industry_demote
            elif scope == "core":
                score += self.industry_boost

        targets = set(spec.countries)
        if targets:
            evidence_countries = set(meta.get("countries", ()))
            if targets & evidence_countries:
                score += self.country_boost
            elif "Global" in evidence_countries:
                # Global-jurisdiction report recalled for a country-specific
                # question.  Task 3 §2.4 "宏观文档漂移".
                score -= self.global_demote
            elif evidence_countries:
                score -= self.country_demote

        if spec.evidence_types and meta.get("evidence_type") in spec.evidence_types:
            score += self.type_boost

        if spec.risks and set(meta.get("related_risk", ())) & set(spec.risks):
            score += self.risk_boost

        return score

    # ------------------------------------------------------------------
    def decision_rows(self) -> list[dict]:
        rows: list[dict] = []
        seen: set[str] = set()
        for decision in self.last_decisions:
            if decision.evidence_id in seen:
                continue
            seen.add(decision.evidence_id)
            rows.append(decision.as_row())
        return rows


if __name__ == "__main__":  # pragma: no cover
    for q in (
        "CATL Vietnam factory risk",
        "What US policies may affect Chinese EV battery manufacturers exporting to the US?",
        "如果管理层想了解中国企业在马来西亚布局以降低地缘风险的公开案例？",
    ):
        spec = parse_filter_spec(q)
        print(q)
        print("   ", spec.as_dict())
