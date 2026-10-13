"""Task 4.2 — query enhancement.

Turns one decision question into a small set of recall-oriented sub-queries
and expansion terms.  Two consumers:

* ``expand_terms()`` feeds the retrieval provider's *recall-only* candidate
  expansion (the same seam the existing intent rules use), so it can add
  candidates without disturbing document ranking.
* ``expansion_variants()`` is the human-readable expansion shown in
  ``query_before_after.xlsx`` and produced by the LLM prompt in
  ``query_expansion_prompt.md``.

The rules are deliberately conservative: an expansion only fires when the
question actually carries the trigger, so an unrelated question is never
diluted with off-topic sub-queries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Trigger vocabulary
# --------------------------------------------------------------------------
COMPANY_LEXICON: dict[str, tuple[str, ...]] = {
    "CATL": ("catl", "宁德时代"),
    "BYD": ("byd", "比亚迪"),
    "Gotion": ("gotion", "国轩高科", "国轩"),
    "EVE Energy": ("eve energy", "亿纬锂能", "亿纬"),
    "Sunwoda": ("sunwoda", "欣旺达"),
    "SVOLT": ("svolt", "蜂巢能源", "蜂巢"),
    "Huayou": ("huayou", "华友钴业", "华友"),
    "CNGR": ("cngr", "中伟股份", "中伟"),
    "Semcorp": ("semcorp", "恩捷股份", "恩捷"),
    "Foxconn": ("foxconn", "富士康", "鸿海"),
    "Samsung SDI": ("samsung sdi", "三星sdi", "三星SDI"),
    "JinkoSolar": ("jinkosolar", "晶科"),
    "LONGi": ("longi", "隆基"),
    "Innolight": ("innolight", "中际旭创"),
    "Eoptolink": ("eoptolink", "新易盛"),
    "Changan": ("changan", "长安汽车", "长安"),
}

TOPIC_TRIGGERS: dict[str, tuple[str, ...]] = {
    "relocation": (
        "转移", "搬迁", "海外建厂", "海外工厂", "东南亚", "扩产", "生产基地",
        "relocation", "relocate", "overseas", "southeast asia", "expatriate",
    ),
    "production_decision": (
        "扩产", "扩建", "增加产能", "是否扩产", "建厂", "产能规划",
        "expand production", "production expansion", "capacity expansion",
        "should we expand", "expand capacity",
    ),
    "return": ("回流", "撤回", "放弃海外建厂", "回迁", "reconsideration", "reshoring", "back to china"),
    "china_plus_one": ("china+1", "china plus one", "多地区", "分散布局", "dual sourcing", "alternative site"),
    "origin": (
        "原产地", "转运", "反规避", "规避", "贸易救济", "双反", "反倾销",
        "circumvention", "transshipment", "country of origin", "substantial transformation",
        "trade remedy", "anti-dumping",
    ),
    "export_control": ("出口管制", "实体清单", "受限方", "两用物项", "穿透", "entity list", "dual-use", "export control"),
    "tariff": ("关税", "tariff", "加征", "301", "232"),
    "supply_chain": (
        "供应链", "中间品", "供应商", "产能", "生产", "制造", "工厂",
        "supply chain", "intermediate input", "supplier", "production",
        "manufacturing", "factory", "plant", "capacity",
    ),
    "china": ("中国", "国内", "本土生产", "china", "domestic production"),
    "market_access": ("市场准入", "准入", "客户", "market access", "compliance"),
    "battery": ("电池", "电芯", "锂电", "battery", "ev", "cell", "lithium"),
    "eu": ("欧盟", "欧洲", "eu", "europe"),
    "us": ("美国", "对美", "united states", "u.s."),
}

# rule name -> (sub-query templates, recall terms)
EXPANSION_RULES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "company_footprint": (
        ("{company} production footprint", "{company} overseas factories", "{company} 产能布局"),
        ("{company}", "production footprint", "overseas factory", "产能布局", "海外基地"),
    ),
    "relocation": (
        ("China manufacturing relocation to Southeast Asia", "海外建厂 产能转移 东南亚"),
        ("产能转移", "海外建厂", "生产基地", "relocation", "overseas production", "southeast asia"),
    ),
    "production_decision": (
        ("{company} production footprint China", "中国产能布局 是否扩产"),
        ("产能布局", "扩产", "production footprint", "capacity expansion", "manufacturing base"),
    ),
    "return": (
        ("companies returning production to China", "订单转移海外后回流 案例"),
        ("回流", "放弃海外建厂", "reshoring", "back to china", "撤出东南亚"),
    ),
    "china_plus_one": (
        ("China+1 strategy dual production base", "China plus one 多地区布局"),
        ("china+1", "china plus one", "多地区布局", "分散生产", "dual production"),
    ),
    "origin": (
        ("country of origin transshipment enforcement", "反规避 原产地 转运 认定"),
        ("原产地", "转运", "反规避", "circumvention", "transshipment", "country of origin",
         "substantial transformation", "customs enforcement"),
    ),
    "export_control": (
        ("US export controls entity list battery", "出口管制 实体清单 关联企业"),
        ("出口管制", "实体清单", "两用物项", "entity list", "export control", "affiliates rule"),
    ),
    "tariff": (
        ("US tariff risk on Chinese EV batteries", "对华关税 电池 加征"),
        ("关税", "tariff", "加征关税", "section 301"),
    ),
    "supply_chain": (
        ("China EV battery supply chain dependency", "电池 供应链 中间品 依赖"),
        ("供应链", "中间品", "供应商依赖", "supply chain", "intermediate inputs",
         "supplier dependence", "geographic concentration"),
    ),
    "market_access": (
        ("market access requirements for EV battery imports", "市场准入 合规要求"),
        ("市场准入", "合规", "market access", "regional requirement", "customer access"),
    ),
    "eu_regulation": (
        ("EU battery regulation compliance", "欧盟电池法规 合规"),
        ("欧盟电池法规", "eu battery regulation", "battery passport", "carbon footprint"),
    ),
    "battery_sector": (
        ("EV battery manufacturing ecosystem", "动力电池 产业链"),
        ("动力电池", "电池材料", "battery cell", "lithium-ion", "cathode", "anode"),
    ),
    "battery": (
        ("EV battery manufacturing ecosystem", "动力电池 产业链"),
        ("动力电池", "电池材料", "battery", "lithium-ion"),
    ),
    "china": (
        ("China EV battery manufacturing ecosystem", "中国 电池 产业链 产能"),
        ("中国", "国内生产", "china", "domestic production", "manufacturing ecosystem"),
    ),
    "us_market": (
        ("US tariff risk on Chinese EV batteries", "美国市场 准入 关税 电池"),
        ("美国市场", "关税", "us tariff", "market access", "customs enforcement"),
    ),
}

DEFAULT_TERMS: tuple[str, ...] = ()

# Keep the expansion bounded: an unbounded term list floods the FTS candidate
# pool with marginal chunks and slows ranking without adding recall.
MAX_VARIANTS = 8
MAX_TERMS = 28

# Rules added as generic "coverage angles" rather than by a direct trigger.
COVERAGE_RULES = frozenset({"us_market", "eu_regulation", "battery_sector", "battery"})


@dataclass
class QueryExpansion:
    original: str
    variants: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "original_query": self.original,
            "expanded_query": " ; ".join(self.variants),
            "expansion_terms": "; ".join(self.terms),
            "rules_fired": "; ".join(self.rules),
            "detected_company": "; ".join(self.companies),
            "variant_count": len(self.variants),
        }


def detect_companies(text: str) -> list[str]:
    low = text.lower()
    out: list[str] = []
    for name, aliases in COMPANY_LEXICON.items():
        if any(alias.lower() in low for alias in aliases):
            out.append(name)
    return out


def _fired_rules(text: str) -> list[str]:
    low = text.lower()
    rules: list[str] = []
    for rule, triggers in TOPIC_TRIGGERS.items():
        if rule in ("us",):
            if any(t in low for t in triggers):
                rules.append("us_market")
            continue
        if rule == "eu":
            if any(t in low for t in triggers):
                rules.append("eu_regulation")
            continue
        if any(t in low for t in triggers):
            rules.append(rule)
    if any(t in low for t in TOPIC_TRIGGERS["us"]):
        rules.append("us_market")
    # China is implied whenever relocation / origin / supply-chain is in play.
    if any(r in rules for r in ("relocation", "return", "origin", "supply_chain",
                                "china_plus_one", "production_decision", "china")):
        rules.append("china_plus_one")
        rules.append("china")
    # Standard comparison angles: a China decision is always read against the
    # US and EU access regimes, so add them as coverage sub-queries.
    if any(r in rules for r in ("relocation", "return", "china_plus_one",
                                "production_decision", "supply_chain", "market_access")):
        rules.append("us_market")
        rules.append("eu_regulation")
    if "china" in rules or "battery" in rules or "production_decision" in rules:
        rules.append("battery_sector")
        rules.append("battery")
    if "supply_chain" in rules or "china" in rules:
        rules.append("supply_chain")
    seen, ordered = set(), []
    for rule in rules:
        if rule not in seen and rule in EXPANSION_RULES:
            seen.add(rule)
            ordered.append(rule)
    return ordered


def expand_query(
    query_text: str,
    *,
    company_hint: str = "",
    include_coverage_angles: bool = True,
) -> QueryExpansion:
    """Rule-based expansion of a single decision question."""
    text = query_text or ""
    companies = detect_companies(text)
    if company_hint and company_hint not in companies:
        companies = [company_hint] + companies

    rules = _fired_rules(text)
    if not include_coverage_angles:
        rules = [r for r in rules if r not in COVERAGE_RULES]
    if companies and "company_footprint" not in rules:
        rules.insert(0, "company_footprint")

    variant_templates: list[str] = []
    terms: list[str] = []
    for rule in rules:
        templates, rule_terms = EXPANSION_RULES.get(rule, ((), ()))
        variant_templates.extend(templates)
        terms.extend(rule_terms)

    variants: list[str] = []
    for template in variant_templates:
        if "{company}" in template:
            for company in companies:
                variants.append(template.replace("{company}", company))
        else:
            variants.append(template)

    if not variants:
        variants = [" ".join(re.findall(r"[\u4e00-\u9fff]{2,}|\w+", text))[:120]]

    expanded_terms: list[str] = []
    for term in terms:
        if "{company}" in term:
            expanded_terms.extend(term.replace("{company}", c) for c in companies)
        else:
            expanded_terms.append(term)

    seen_v, dedup_v = set(), []
    for v in variants:
        if v not in seen_v:
            seen_v.add(v)
            dedup_v.append(v)
    seen_t, dedup_t = set(), []
    for t in expanded_terms:
        if t not in seen_t:
            seen_t.add(t)
            dedup_t.append(t)

    return QueryExpansion(
        original=text,
        variants=dedup_v[:MAX_VARIANTS],
        terms=dedup_t[:MAX_TERMS],
        rules=rules,
        companies=companies,
    )


def expand_terms(
    query_text: str,
    base_terms=(),
    company_hint: str = "",
    include_coverage_angles: bool = False,
) -> list[str]:
    """Recall-only expansion terms, appended to the provider's base terms.

    ``include_coverage_angles`` defaults to False at retrieval time: the broad
    coverage sub-queries are useful in the LLM prompt and in the deliverable,
    but on a 30-document corpus they dilute recall with generic candidates.
    """
    expansion = expand_query(
        query_text,
        company_hint=company_hint,
        include_coverage_angles=include_coverage_angles,
    )
    out = list(base_terms)
    for term in expansion.terms:
        if term not in out:
            out.append(term)
    return out


LLM_PROMPT_TEMPLATE = """\
# Task 4.2 — Query Enhancement Prompt

你是一个供应链风险情报检索助手。用户会用一个**决策问题**提问，而不是关键词。
你的任务：把这个问题改写为 **4–8 条彼此互补的检索子查询 + 一组召回关键词**，
覆盖"企业事实 / 政策法规 / 供应链 / 市场准入 / 情景对比"五类视角。

## 硬性要求

1. 不要回答用户问题，只产出检索用的子查询。
2. 子查询必须**具体**（含公司名、国家、政策工具、工序），不要复述原问题。
3. 中英混合：中文子查询用于中文语料，英文子查询用于英文法规/报告。
4. 不要编造政策名称、数字或不在问题中出现的事实。
5. 输出严格 JSON，不要解释。

## 输出格式

```json
{
  "original_query": "<原问题>",
  "detected": {
    "company": ["<公司名，可空>"],
    "countries": ["<CN/US/VN/TH/MY/EU ...>"],
    "industry": "EV_Battery",
    "topics": ["tariff|export_control|trade_policy|investment_policy|market_access|supply_chain|supplier_dependency|regulation|localization_policy"],
    "risks": ["Trade Risk|Political Risk|Supply Chain Risk|Regulatory Risk|Market Access Risk|Operational Risk"]
  },
  "sub_queries": [
    "<company> production footprint",
    "<company> overseas factories",
    "China EV battery supply chain",
    "US tariff risk on Chinese EV batteries",
    "EU battery regulation compliance",
    "China+1 strategy dual production base"
  ],
  "expansion_terms": ["<用于 BM25/FTS 的召回词>"]
}
```

## Few-shot

输入：
```
Company: CATL
Question: Should we expand production in China?
```

输出：
```json
{
  "original_query": "Should we expand production in China?",
  "detected": {
    "company": ["CATL"],
    "countries": ["CN"],
    "industry": "EV_Battery",
    "topics": ["supply_chain", "trade_policy"],
    "risks": ["Supply Chain Risk", "Trade Risk"]
  },
  "sub_queries": [
    "CATL production footprint",
    "CATL overseas factories",
    "China EV battery supply chain",
    "US tariff risk on Chinese EV batteries",
    "EU battery regulation compliance",
    "China+1 strategy dual production base"
  ],
  "expansion_terms": ["CATL", "产能布局", "海外基地", "供应链", "中间品", "关税", "China+1"]
}
```

## 运行时说明

本仓库当前使用**规则版**实现（`backend/app/query_enhancement.py::expand_query`），
上述 prompt 是 LLM 版的上线方案；两者输出结构一致，可无痛替换。
规则版覆盖的触发词见 `TOPIC_TRIGGERS`，子查询模板见 `EXPANSION_RULES`。
"""


def write_prompt(path) -> None:
    from pathlib import Path

    Path(path).write_text(LLM_PROMPT_TEMPLATE, encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    for q in (
        "Should we expand production in China?",
        "我们正在评估把部分产能转移到泰国。现有企业案例显示，哪些中国制造企业已经在泰国建设或扩充产能？",
    ):
        print(q)
        print("   ", expand_query(q).as_dict())
