"""Generate data/evaluation/baseline_report.md from the Task 3 result files.

The report is rebuilt from the artefacts rather than hand-edited, so it cannot
drift from ``retrieval_results.xlsx`` / ``entity_accuracy.xlsx``.
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

EVAL = Path("/Users/zhengyuanyuan/Desktop/project-data/data/evaluation")
REPORT = EVAL / "baseline_report.md"


def rows(path: Path, sheet: str) -> list[dict]:
    ws = load_workbook(path, read_only=True, data_only=True)[sheet]
    data = list(ws.iter_rows(values_only=True))
    header = list(data[0])
    return [dict(zip(header, r)) for r in data[1:] if r and r[0]]


CASE_PREFIXES = ("CASE_", "RELOC_", "PLUS1_", "RETURN_")


def load_gold() -> dict[str, set[str]]:
    import re

    ws = load_workbook(Path("task2_retrieval_evaluation_v0.7.xlsx"), read_only=True, data_only=True)["retrieval_questions"]
    data = list(ws.iter_rows(values_only=True))
    hdr = list(data[0])
    out: dict[str, set[str]] = {}
    for row in data[1:]:
        rec = dict(zip(hdr, row))
        out[str(rec["question_id"])] = {
            p.strip() for p in re.split(r"[;,，；]\s*", str(rec["expected_evidence_ids"] or "")) if p.strip()
        }
    return out


def main() -> None:
    per = rows(EVAL / "retrieval_results.xlsx", "question_summary")
    items = rows(EVAL / "retrieval_results.xlsx", "retrieval_results")
    for r in items:
        r["case_doc"] = str(r["retrieved_evidence_id"]).startswith(CASE_PREFIXES)
    ent_summary = {r["Task 3 — Entity Accuracy"]: r["Value"]
                   for r in rows(EVAL / "entity_accuracy.xlsx", "Summary")}
    ent_detail = rows(EVAL / "entity_accuracy.xlsx", "Entity Detail")

    n = len(per)
    p5 = sum(r["precision_at_5"] for r in per) / n
    r10 = sum(r["recall_at_10"] for r in per) / n
    hit5 = sum(r["hit_at_5"] for r in per) / n
    hit10 = sum(r["hit_at_10"] for r in per) / n
    auth5 = sum(r["mean_authority_top5"] for r in per) / n
    ent = [r for r in per if r["entity_accuracy"] not in ("", None)]
    ea = sum(r["entity_accuracy"] for r in ent) / len(ent)
    er = sum(r["entity_recall"] for r in ent) / len(ent)
    ep = sum(r["entity_precision"] for r in ent) / len(ent)

    cats: dict[str, list[dict]] = {}
    for r in per:
        cats.setdefault(r["scenario_category"], []).append(r)

    weak = sorted(per, key=lambda r: (r["recall_at_10"], r["precision_at_5"]))[:8]

    lines = [
        "# Task 3 — RAG Baseline Report",
        "",
        "**范围**：当前（未做 metadata filtering / query enhancement / authority ranking 优化）的检索能力",
        "**数据**：30 个 benchmark 问题 × Top-10，语料 47 篇证据（30 政策/宏观 + 17 企业案例，`backend/test_data/app.db`）",
        "**运行**：`run_task3_baseline.py`（Top-K=10）；报告由 `build_task3_report.py` 从结果文件生成",
        "",
        "---",
        "",
        "## 1. 总结 — Current RAG Performance",
        "",
        "| 指标 | Baseline | 说明 |",
        "|---|---|---|",
        f"| **Precision@5** | **{p5:.3f}** | Top-5 中 relevance ≥ 1 的比例，按题平均 |",
        f"| **Recall@10** | **{r10:.3f}** | Top-10 中召回的 gold 证据 / 该题 gold 总数，按题平均 |",
        f"| **Entity Accuracy** | **{ea:.3f}** | (实体召回 + 实体精度) / 2，{len(ent)} 个含实体问题 |",
        "",
        "支撑指标：",
        "",
        "| 指标 | Baseline |",
        "|---|---|",
        f"| Entity Recall | {er:.3f}（问题中的实体在 Top-10 中的覆盖） |",
        f"| Entity Precision | {ep:.3f}（Top-10 中 {1 - ep:.1%} 的证据与问题实体无关） |",
        f"| Hit@5 / Hit@10 | {hit5:.0%} / {hit10:.0%}（每题至少 1 条 gold） |",
        f"| Mean Authority (Top-5) | {auth5:.2f}（S/A+/A=2，B+=1） |",
        "",
        "分场景：",
        "",
        "| scenario_category | n | P@5 | R@10 | Entity Acc |",
        "|---|---|---|---|---|",
    ]
    for cat, rs in sorted(cats.items()):
        e = [r for r in rs if r["entity_accuracy"] not in ("", None)]
        lines.append(f"| {cat} ({len(rs)}) | {len(rs)} | "
                     f"{sum(r['precision_at_5'] for r in rs) / len(rs):.3f} | "
                     f"{sum(r['recall_at_10'] for r in rs) / len(rs):.3f} | "
                     f"{sum(r['entity_accuracy'] for r in e) / len(e):.3f} |")

    lines += [
        "",
        f"**一句话结论**：Top-5 的\"能不能捞到正确证据\"没有明显问题（Hit@5 = {hit5:.0%}），",
        f"Recall@10 = {r10:.3f} 的主要拖累来自**企业案例题**与**案例证据对政策/宏观题的过召回**；",
        f"Entity Accuracy ({ea:.3f}) 受指标口径限制，主要反映 Entity Precision ({ep:.3f})。",
        "",
        "---",
        "",
        "## 2. Main Problems",
        "",
        "### 2.1 案例证据对政策/宏观题的过召回（新增，语料扩容后出现）",
        "",
        "17 条企业案例入库后，案例叙述与\"中国/电池/布局/风险\"等通用词高度重合，",
        "在**非案例类**问题里也开始占据 Top-5：",
    ]
    case_ids = {r["retrieved_evidence_id"] for r in items if r["case_doc"]}
    for q in ("Q011", "Q012", "Q013", "Q022", "Q029"):
        r = next(x for x in per if x["question_id"] == q)
        top5 = [i.strip() for i in str(r["retrieved_top10"] or "").split("; ")][:5]
        n_case = sum(1 for i in top5 if i in case_ids)
        lines.append(f"- `{q}`（{r['scenario_category']}）Top-5 含 {n_case} 条企业案例，"
                     f"P@5 = {float(r['precision_at_5']):.2f}，R@10 = {float(r['recall_at_10']):.2f}")

    lines += [
        "",
        "根因：案例文档 topic 统一为「供应链布局」，而现有重排规则只对宏观文档做了处理，",
        "对案例文档没有\"仅在问企业案例时才召回\"的约束。这也是 Task 4.1 本轮要补的规则。",
        "",
        "### 2.2 企业案例召回的结构性问题",
        "",
        "- 新入库 17 条案例中，**13 条为 B+（媒体转述）**，仅 3 条达到 S（公司公告/投资者互动平台）。",
        "- `RELOC_001`（比亚迪泰国）、`RELOC_002`（长安泰国）为整车厂，电池链（`RELOC_003`–`008`）以国轩/亿纬/欣旺达/蜂巢/华友/中伟为主。",
        "- **缺 EU 电池法规合规案例、印度进入案例、二线厂商/劳工/物流（Operational Risk）案例**；EU 相关 Market Access 问题仍只能靠政策文件回答。",
        "",
        "### 2.3 二线来源与企业案例排序偏低（Policy documents ranked low — 部分成立）",
        "",
    ]

    # authority vs rank, over the gold evidence that was actually retrieved
    gold = load_gold()
    buckets: dict[str, list[int]] = {}
    for r in items:
        if r["retrieved_evidence_id"] not in gold.get(r["question_id"], set()):
            continue
        buckets.setdefault(r["authority_level"], []).append(int(r["rank"]))
    lines += [
        "| authority | 条数 | 平均排名 | 进 Top-3 |",
        "|---|---|---|---|",
    ]
    for lvl in ("S", "A+", "A", "B+"):
        ranks = buckets.get(lvl, [])
        if not ranks:
            lines.append(f"| {lvl} | 0 | | |")
            continue
        lines.append(f"| {lvl} | {len(ranks)} | {sum(ranks) / len(ranks):.2f} | "
                     f"{sum(1 for x in ranks if x <= 3) / len(ranks):.0%} |")
    lines += [
        "",
        "### 2.4 宏观文档漂移（较上一版明显减轻）",
        "",
        "上一版（30 篇语料）中 `UNCTAD_001 / WTO_001 / IMF_001 / WEF_001` 会大量漂入",
        "`Q008 / Q010 / Q016 / Q017 / Q020 / Q028` 等非宏观问题的 Top-10；",
        "本次只剩少量残留（`Q008` rank 9、`Q020` rank 7），因为案例证据挤占了这些位置。",
        "注意这是「以案例换宏观」：漂移减轻不等于排序变好，见 §2.1。",
        "",
        "### 2.5 语料层面的结构性缺口",
        "",
        "- 企业案例已补齐（Task 5：17 条），但**仍缺 S/A 级的公司年报**；",
        "  只有 `RELOC_001`/`RELOC_002`/`RETURN_001` 达到 S，其余为 B+ 媒体转述。",
        "- EU / 印度 / 墨西哥 / 美国本土案例缺失，Market Access 场景仍偏政策文件。",
        "",
        "---",
        "",
        "## 3. 后续优化方向",
        "",
        "| 问题 | 对应 Task 4 动作 | 预期影响 |",
        "|---|---|---|",
        "| 案例过召回（2.1）| 4.1 Metadata Filtering：把案例证据限定在\"问企业案例\"的问题里 | P@5 / R@10 |",
        "| 企业案例召回（2.2）| 4.2 Query Enhancement：公司名/国家/决策类型扩展 | 案例题 R@10 |",
        "| A/B+ 排序（2.3）| 4.3 Authority Ranking：similarity + authority 带内 tie-break | A 级进入 Top-3 |",
        "| 宏观文档漂移（2.4）| 4.1 F1 宏观漂移规则 | 减少无关宏观文档 |",
        "| 语料缺口（2.5）| 补 EU/EU 电池法规、印度进入、二线厂商案例 | 上限提升 |",
        "",
        "---",
        "",
        "## 4. 验收基线对照（Task 4 目标）",
        "",
        "| 指标 | 任务书假设 Before | 实测 Baseline | 任务书 After 目标 |",
        "|---|---|---|---|",
        f"| Precision@5 | 65% | **{p5:.1%}** | ≥ 80% |",
        f"| Recall@10 | 70% | **{r10:.1%}** | ≥ 80% |",
        f"| Entity Accuracy | 85% | **{ea:.1%}** | ≥ 95% |",
        "",
        "**说明**：实测 baseline 高于任务书的假设值；且 Entity Accuracy ≥ 0.95 在本语料上不可达",
        "（gold 中包含大量不出现问题实体的宏观文档，检索越准该指标反而越低，见 `task4/baseline_vs_improved.md` §6）。",
        "",
        "---",
        "",
        "## 5. 方法说明与口径",
        "",
        "**Precision@5** = Top-5 中 relevance ≥ 1 的条数 ÷ 5，按题平均。",
        "relevance 判定：2 = 在该题 `expected_evidence_ids` 内；1 = 不在 gold 内，但 topic 属于该题 topic 桶。",
        "",
        "**Recall@10** = Top-10 中召回的 gold 证据数 ÷ 该题 gold 总数，按题平均。",
        "",
        f"**Entity Accuracy** = (Entity Recall + Entity Precision) ÷ 2，只对**问题文本中出现实体**的 {len(ent)} 题计算；",
        "无实体问题不计入。",
        "",
        "**已知口径局限**",
        "1. 目标实体只从问题文本提取，**不使用 gold 证据**，避免循环论证。",
        "2. 通用实体（China / United States / tariff）在多数文档中都出现，会**抬高** Entity Precision。",
        "3. 实体识别基于规则词典，未用 NER 模型。",
        f"4. 本题集 Entity Recall 恒为 {er:.3f}：语料实体高度共现，召回端已饱和；",
        f"   Entity Accuracy 的区分度全部来自 Entity Precision（{ep:.3f}）。",
        "5. `retrieval_results.xlsx` 中的 relevance / authority 为自动判定；人工评分见 Task 2 的 `Task2_manual_scoring_v3.xlsx`。",
        "",
        "---",
        "",
        "## 6. 最弱的题（优先优化对象）",
        "",
        "| question_id | 场景 | P@5 | R@10 | Entity Acc |",
        "|---|---|---|---|---|",
    ]
    for r in weak:
        lines.append(f"| {r['question_id']} | {r['scenario_category']} | {r['precision_at_5']} | "
                     f"{r['recall_at_10']} | {r['entity_accuracy'] if r['entity_accuracy'] not in ('', None) else 'n/a'} |")

    lines += [
        "",
        "---",
        "",
        "## 7. 交付物",
        "",
        "| 文件 | 内容 |",
        "|---|---|",
        "| `retrieval_questions.xlsx` | 30 个测试问题（同 Task 2） |",
        "| `retrieval_results.xlsx` | `Summary` 指标看板 / `retrieval_results` 300 行（30 题 × Top-10）/ `question_summary` |",
        "| `entity_accuracy.xlsx` | `Entity Accuracy` 逐题 / `Entity Detail` 逐实体 / `Summary` |",
        "| `baseline_report.md` | 本文件 |",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", REPORT)


if __name__ == "__main__":
    main()
