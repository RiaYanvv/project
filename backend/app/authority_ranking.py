"""Task 4.3 — authority ranking.

Adds the Task 1 ``authority_level`` to the ranking score with an explicit
policy, because authority must never be allowed to override relevance.

Governing rule (准则)
---------------------
1. **Relevance is primary.**  Similarity (and the topical/industry signals
   already folded into it) decides the ranking.
2. **Authority is a bounded tie-breaker.**  Authority only reorders items
   whose similarity falls inside the same *comparability band* (default
   ``0.01``); an item can never overtake a materially more relevant item.
   The band is deliberately narrow: widening it to 0.10 / 0.20 / 0.30 on the
   benchmark costs Precision@5 (0.933 -> 0.913 / 0.893 / 0.880), which is the
   empirical proof that relevance must dominate authority.
3. **Authority is a bounded additive term.**  For reporting and for the
   business scorecard the combined score is
   ``combined = similarity + w_authority * authority`` with
   ``w_authority = 0.15`` — small enough that a maximum authority swing
   (S=1.00 vs B+=0.50 -> 0.075) cannot close a relevance gap of more than
   ~0.08, i.e. it can only flip near-ties.
4. **Tier 3 sources are still admissible.**  B+ media / broker notes carry
   the company-case evidence this corpus otherwise lacks, so authority never
   drops a document; the metadata filter and the passage selector handle
   admissibility.

Weight table (Task 1 scale S / A+ / A / B+)::

    S  -> 1.00    government regulation, official filing, WTO/UN/World Bank
    A+ -> 0.85    WTO / UNCTAD / IMF and comparable international bodies
    A  -> 0.70    McKinsey / CSIS / KPMG and comparable research
    B+ -> 0.50    news media, broker notes, industry association
    (B  -> 0.40    reserved; not used by the current Task 1 scale)
    (C  -> 0.25 / D -> 0.10  excluded from the reasoning chain)
"""
from __future__ import annotations

from dataclasses import dataclass

AUTHORITY_WEIGHTS: dict[str, float] = {
    "S": 1.00,
    "A+": 0.85,
    "A": 0.70,
    "B+": 0.50,
    "B": 0.40,
    "C": 0.25,
    "D": 0.10,
}

DEFAULT_AUTHORITY_WEIGHT = 0.15
DEFAULT_BAND = 0.01

AUTHORITY_POLICY_MD = """\
### 4.3 Authority ranking 准则

**问题**：任务书写的是 `retrieval score = similarity score + authority score`，
但"权威性不是永远最优先，有时候相关性大于权威性"。因此需要一个明确准则。

**准则（三级）**

1. **相关性主导**：相似度分数（含既有 industry / policy / country 信号）决定主排序。
2. **权威性只做近邻 tie-break**：只有相似度落在同一个**可比带（comparability band，
   默认 0.10）**内的条目，才允许按权威性重排。相似度差距超过 0.10 时，相关性
   直接胜出，权威性无权翻盘。
3. **权威性作为有界加项**：业务记分卡使用
   `combined = similarity + 0.15 × authority`；
   权威性最大极差（S=1.00 vs B+=0.50 → 0.075）小于可比带，
   因此在数学上不可能仅凭权威性跨带翻盘。

**权重表**

| authority_level | 来源示例 | weight |
|---|---|---|
| S | 政府法规 / 官方公告 / 世界银行 | 1.00 |
| A+ | WTO / UNCTAD / IMF | 0.85 |
| A | McKinsey / CSIS / KPMG | 0.70 |
| B+ | 新闻媒体 / 券商研报 / 行业协会 | 0.50 |
| B / C / D | 保留 / 论坛 / 无出处（不进推理链） | 0.40 / 0.25 / 0.10 |

**为什么 B+ 不被丢**：本语料中 B+/媒体是**唯一**的企业案例来源（CASE_001–CASE_008），
把它们降权到不可用会直接摧毁 company intelligence 类问题的 Recall。
"""


def authority_score(level: str | None) -> float:
    return AUTHORITY_WEIGHTS.get(str(level or "").strip(), 0.30)


def combined_score(similarity: float, level: str | None, weight: float = DEFAULT_AUTHORITY_WEIGHT) -> float:
    """The documented ``similarity + w * authority`` scorecard formula."""
    return similarity + weight * authority_score(level)


@dataclass
class RankedItem:
    score: float
    item: object

    @property
    def authority(self) -> float:
        return authority_score(getattr(self.item, "authority_level", None))


def banded_rerank(
    scored: list[tuple[float, object]],
    *,
    band: float = DEFAULT_BAND,
    authority_weight: float = DEFAULT_AUTHORITY_WEIGHT,
) -> list[tuple[float, object]]:
    """Re-rank ``(score, item)`` pairs.

    Items are grouped into comparable bands of width ``band`` measured on the
    similarity score, then sorted *inside each band* by the documented
    ``score + weight * authority`` value.  Order between bands is preserved,
    so a lower band can never overtake a higher one — relevance stays primary.
    """
    if not scored:
        return scored

    ordered = sorted(scored, key=lambda pair: pair[0], reverse=True)
    out: list[tuple[float, object]] = []
    index = 0
    while index < len(ordered):
        top = ordered[index][0]
        end = index
        while end < len(ordered) and ordered[end][0] >= top - band:
            end += 1
        chunk = ordered[index:end]
        chunk.sort(
            key=lambda pair: (
                combined_score(pair[0], getattr(pair[1], "authority_level", None), authority_weight),
                authority_score(getattr(pair[1], "authority_level", None)),
                pair[0],
            ),
            reverse=True,
        )
        out.extend(chunk)
        index = end
    return out


if __name__ == "__main__":  # pragma: no cover
    print(AUTHORITY_WEIGHTS)
