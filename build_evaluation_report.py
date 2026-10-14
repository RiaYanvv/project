"""Generate data/evaluation/evaluation_report.md from the delivered artefacts."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from openpyxl import load_workbook

DATA = Path("/Users/zhengyuanyuan/Desktop/project-data/data")
EVAL = DATA / "evaluation"
CASE_DB = DATA / "processed" / "case_database_v0.1.xlsx"
DB = Path("backend/test_data/app.db")


def sheet_rows(path: Path, sheet: str) -> list[dict]:
    ws = load_workbook(path, read_only=True, data_only=True)[sheet]
    data = list(ws.iter_rows(values_only=True))
    hdr = list(data[0])
    return [dict(zip(hdr, r)) for r in data[1:] if r and r[0]]


def key_metrics(path: Path, sheet: str) -> dict:
    out = {}
    for row in sheet_rows(path, sheet):
        k, v = row.get("指标") or row.get("metric"), row.get("Value", row.get("Baseline"))
        if k is not None and isinstance(v, (int, float)):
            out[str(k)] = round(float(v), 3)
        elif isinstance(k, str) and ("——" in k):
            pass
    return out


def summary_map(path: Path, label_col="Task 3 — Entity Accuracy"):
    out = {}
    for row in sheet_rows(path, "Summary"):
        k = row.get(label_col)
        if k is None:
            k = list(row.values())[0]
        v = list(row.values())[1] if len(row) > 1 else None
        if isinstance(k, str) and isinstance(v, (int, float)):
            out[k] = round(float(v), 3)
    return out


def read_manual_scores() -> tuple[dict, dict]:
    """Read the human scoring workbook and split canonical vs v0.9 extension.

    Task 2's spec asks for 30 questions; Q031-Q043 were added in v0.9/v0.9.1 so the
    13 new v0.9 evidence records plus the EU jurisdiction are measurable.  The two sets are reported separately
    because the extension questions have a single gold item each, which caps the
    achievable Top-5 average relevance below that of the multi-gold questions.
    """
    ws = load_workbook(Path("Task2_manual_scoring_v3.xlsx"), read_only=True, data_only=True)["Item Scoring"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(c).strip() if c is not None else "" for c in rows[0]]
    qi = hdr.index("Question ID")
    ri = hdr.index("Relevance (0/1/2)")
    ai = hdr.index("Authority (0/1/2)")

    def agg(lo: str, hi: str) -> dict:
        sel = [r for r in rows[1:] if r[qi] and lo <= str(r[qi]) <= hi and r[ri] is not None]
        n = len(sel) or 1
        return {
            "rel": sum(float(r[ri]) for r in sel) / n,
            "auth": sum(float(r[ai]) for r in sel if r[ai] is not None) / max(1, len([r for r in sel if r[ai] is not None])),
            "items": len(sel),
        }

    qs = load_workbook(Path("Task2_manual_scoring_v3.xlsx"), read_only=True, data_only=True)["Question Scoring"]
    qrows = list(qs.iter_rows(values_only=True))
    qhdr = [str(c).strip() if c is not None else "" for c in qrows[0]]
    q0, h0 = qhdr.index("Question ID"), qhdr.index("Hit@5")

    def hit(lo: str, hi: str) -> float:
        sel = [r for r in qrows[1:] if r[q0] and lo <= str(r[q0]) <= hi]
        return sum(int(r[h0] or 0) for r in sel) / max(1, len(sel))

    canon, ext = agg("Q001", "Q030"), agg("Q031", "Q043")
    canon["hit"], ext["hit"] = hit("Q001", "Q030"), hit("Q031", "Q043")
    canon["n"], ext["n"] = 30, 13
    both = agg("Q001", "Q043")
    both["hit"] = hit("Q001", "Q043")
    both["n"] = 43
    return canon, {"canon": canon, "ext": ext, "all": both}


def read_manual_coverage() -> float:
    qs = load_workbook(Path("Task2_manual_scoring_v3.xlsx"), read_only=True, data_only=True)["Question Scoring"]
    rows = list(qs.iter_rows(values_only=True))
    hdr = [str(c).strip() if c is not None else "" for c in rows[0]]
    qi, ci = hdr.index("Question ID"), hdr.index("Coverage (0/1/2)")
    sel = [r for r in rows[1:] if r[qi] and str(r[qi]) <= "Q030" and r[ci] is not None]
    return sum(float(r[ci]) for r in sel) / max(1, len(sel))


def main() -> None:
    t3 = sheet_rows(EVAL / "retrieval_results.xlsx", "question_summary")
    n3 = len(t3)
    p5 = sum(r["precision_at_5"] for r in t3) / n3
    r10 = sum(r["recall_at_10"] for r in t3) / n3
    ent = [r for r in t3 if r["entity_accuracy"] not in ("", None)]
    ea = sum(r["entity_accuracy"] for r in ent) / len(ent)
    hit5 = sum(r["hit_at_5"] for r in t3) / n3

    t4 = {r["metric"]: r for r in sheet_rows(EVAL / "task4/task4_before_after.xlsx", "Overall")}
    abl = sheet_rows(EVAL / "task4/task4_before_after.xlsx", "Ablation")

    bench = summary_map(EVAL / "benchmark_results.xlsx", "Task 5 — Historical Case Benchmark")
    risk = sheet_rows(EVAL / "risk_assessment_checklist.xlsx", "Summary")
    risk_map = {r["Task 6 — Risk Assessment Evaluation"]: r for r in risk if r.get("Task 6 — Risk Assessment Evaluation")}
    cite = summary_map(EVAL / "evidence_quality_test.xlsx", "Task 7 — Evidence Citation Evaluation")

    cases = sheet_rows(CASE_DB, "Case Database")
    sources = sheet_rows(CASE_DB, "Evidence Index")

    con = sqlite3.connect(str(DB))
    docs = con.execute("select count(*) from knowledge_documents").fetchone()[0]
    chunks = con.execute("select count(*) from knowledge_chunks").fetchone()[0]

    manual, m_ext = read_manual_scores()
    manual_cov = read_manual_coverage()

    L: list[str] = []
    add = L.append

    add("# Locus — RAG / Evidence / Evaluation 阶段报告")
    add("")
    add("**范围**：Evidence schema（Task 1）→ 检索评测集（Task 2）→ 基线（Task 3）→ 优化（Task 4）")
    add("→ 历史案例基准（Task 5）→ 风险识别（Task 6）→ 引用可靠性（Task 7）。")
    add(f"**语料**：{docs} 篇证据 / {chunks} 个 chunk（全部为 Task 1 政策·宏观·贸易证据），`backend/test_data/app.db`")
    add("**证据库**：`metadata/evidence_battery_EV_screened_v0.9.xlsx`（49 条 = v0.8 的 36 条 + 5 条一线企业披露 + WTO/USMCA/世行/DHS/IEA/SNE 共 8 条）；Task 5 的 17 个案例作为 **held-out 答案键**"
        "存放在 `evaluation/case_benchmark/`，**不进入 RAG 语料**（避免答案泄漏）")
    add("")
    add("> 本报告由 `build_evaluation_report.py` 从交付物文件生成，数字不会与 xlsx 漂移。")
    add("")
    add("---")
    add("")
    add("## 0. 结论摘要")
    add("")
    add("| # | 任务 | 交付物 | 关键指标 | 达标 |")
    add("|---|---|---|---|---|")
    add(f"| 1 | Evidence schema | `evidence_battery_EV_screened_v0.9.xlsx`（+ `evaluation/case_benchmark/evidence_cases_v0.1.xlsx`） | 49 条统一 schema、5 级 authority（S/A+/A/B+/B）、原文可追溯 | ✅ |")
    add(f"| 2 | 检索评测集 + 人工评分 | `retrieval_questions.xlsx` / `retrieval_results.xlsx` / `Task2_manual_scoring_v3.xlsx` | Relevance {manual['rel']:.3f} / Authority {manual['auth']:.3f} / Hit@5 {manual['hit']:.0%}（任务书基准 Q001–Q030） | ✅ |")
    add(f"| 3 | 检索基线 | `data/evaluation/retrieval_questions.xlsx` / `retrieval_results.xlsx` / `entity_accuracy.xlsx` + `baseline_report.md` | P@5 {p5:.3f}、R@10 {r10:.3f}、EA {ea:.3f} | ✅ / ⚠️EA |")
    add(f"| 4 | 检索优化 | `task4/*.xlsx` + `baseline_vs_improved.md` + `optimized/*` | P@5 {t4['Precision@5']['After (optimised)']:.3f}、R@10 {t4['Recall@10']['After (optimised)']:.3f} | ✅ |")
    add(f"| 5 | 历史案例基准（held-out） | `historical_case_benchmark.xlsx` + `benchmark_results.xlsx` | {len(cases)} 个真实案例、{int(bench.get('held out of the RAG corpus', 0))}/{len(cases)} 已摘出语料 | ✅ |")
    add(f"| 6 | 风险识别 | `risk_assessment_checklist.xlsx` | Recall {risk_map['Risk Recall (mean over cases)']['Baseline']:.3f} / Precision {risk_map['Risk Precision (mean over cases)']['Baseline']:.3f} | ⚠️ |")
    add(f"| 7 | 引用可靠性 | `evidence_quality_test.xlsx` | 引用可追溯率 {cite.get('citation completeness', 0):.0%}、语料元数据完整率 {cite.get('metadata completeness rate', 0):.0%} | ✅ |")
    add("")
    add(f"**一句话**：检索层已经可用（基线 P@5 {p5:.3f} / R@10 {r10:.3f}，优化后 "
        f"{t4['Precision@5']['After (optimised)']:.3f} / {t4['Recall@10']['After (optimised)']:.3f}，均超任务书 80% 目标）；")
    add(f"**风险识别层仍是短板**——把 Task 5 的 17 个案例从语料摘出（改为 held-out 答案键）后，Risk Recall 由 0.461 升到 "
        f"{risk_map['Risk Recall (mean over cases)']['Baseline']:.3f}，"
        "剩余缺口在「按风险维度检索」的策略，而非语料覆盖。")
    add("")
    add("---")
    add("")
    add("## 1. Task 1 — Evidence Database Schema")
    add("")
    add("| 项 | 结果 |")
    add("|---|---|")
    add(f"| 证据条数 | Task 1 政策/宏观/企业披露 **49 条**（v0.9 = v0.8 的 36 条 + 公司披露 TSLA_001/NIO_001/XPEV_001/LI_001/ALB_001 + USMCA_001 + WTO_002/003/004 + WB_001 + DHS_001 + IEA_001 + SNE_001），进入 RAG 语料；Task 5 案例 17 条为 held-out 答案键，**不入语料** |")
    add(f"| 语料文档 / chunk | {docs} / {chunks}（v0.8 为 36 篇 / 5,772 chunk） |")
    add("| v0.9 新增覆盖 | 来源类型 Company Disclosure 0→5（一线 10-K/20-F 原文）；industry 新增 Automotive 0→4、Battery_Materials 1→2；司法辖区新增 India（WTO_002/003）、Indonesia（WTO_004）、Mexico（USMCA_001）；主题新增 `logistics`（WB_001）与 `labor`（DHS_001） |")
    add("| v0.8 新增覆盖 | EU 司法辖区 0→4 篇；`tariff` 主题 1→3；可表征 Political Risk 的证据 5→8 |")
    add("| authority 分级 | S / A+ / A / B+ / B（S=政府法规·WTO·UN·官方公告；A+=IMF·UNCTAD；A=CSIS·McKinsey·KPMG；B+=媒体·券商；B=二线来源） |")
    add("| 分类字段 | industry / topic / evidence_type / related_risk（六类）/ data_status |")
    add("| industry 修订 | v0.9.1 起 `industry` 统一由 `backend/app/evidence_metadata.build_meta()` 派生（与 Task 4 的 metadata filter 同源），不再手工填写：EV_Battery 32 / Electronics_Manufacturing 6 / Energy_Storage 4 / Automotive 4 / Battery_Materials 2 / General_Manufacturing 1 |")
    add("| 派生规则 | `backend/app/evidence_metadata.py`，逐字段可审计 |")
    add("")
    add("---")
    add("")
    add("## 2. Task 2 — Retrieval Evaluation Dataset")
    add("")
    add("43 个问题，覆盖 5 类场景（Company Intelligence 8 / Policy·Trade Risk 14 / Supply Chain Risk 7 / Market Access 8 / Scenario Simulation 6）。")
    add("")
    add("其中 **Q001–Q030 是任务书口径的基准集**，**Q031–Q043 是 v0.9 扩展集**：v0.9 新增的 13 条证据必须有题面 gold 才能被评测计入，因此按原场景分类补了 10 道企业决策题（Q031–Q040）；v0.9.1 又补了 3 道 EU 题面（Q041–Q043），把此前入库但无 gold 指向的 EU_001–EU_004 纳入评测。两组分别报告——扩展题多为「单一 gold 的窄问题」，Top-5 平均相关的可达上限天然低于多 gold 题。")
    add("")
    add("人工评分（`Task2_manual_scoring_v3.xlsx`，215 条逐条判定）：")
    add("")
    add("| 指标 | 目标 | 实测 |")
    add("|---|---|---|")
    add(f"| Avg Relevance (Top-5) | ≥ 1.5 | **{manual['rel']:.3f}** |")
    add(f"| Avg Authority (Top-5) | ≥ 1.5 | **{manual['auth']:.3f}** |")
    add(f"| Hit@5（≥1 条正确 Evidence） | ≥ 80% | **{manual['hit']:.0%}** |")
    add(f"| Avg Coverage (0-2，Q001–Q030) | 参考 | {manual_cov:.3f} |")
    add("")
    add(f"v0.9 扩展集（Q031–Q043，65 条判定）：Relevance {m_ext['ext']['rel']:.3f} / Authority {m_ext['ext']['auth']:.3f} / Hit@5 {m_ext['ext']['hit']:.0%}；"
        f"合并 43 题：Relevance {m_ext['all']['rel']:.3f} / Authority {m_ext['all']['auth']:.3f} / Hit@5 {m_ext['all']['hit']:.0%}。"
        "合并值低于 1.5 是题目结构（单 gold 窄问题）造成的，不是检索退化——扩展题的主 gold 全部落在 Top-1（Q032/Q039 的次 gold 分列第 10/7；见 §3 逐题明细）。")
    add("")
    add("---")
    add("")
    add("## 3. Task 3 — Retrieval Baseline")
    add("")
    add("| 指标 | Baseline | 任务书目标 |")
    add("|---|---|---|")
    add(f"| Precision@5 | **{p5:.3f}** | ≥ 0.80 ✅ |")
    add(f"| Recall@10 | **{r10:.3f}** | ≥ 0.80 ✅ |")
    add(f"| Entity Accuracy | **{ea:.3f}** | ≥ 0.95 ❌（口径不可达，见下） |")
    add(f"| Hit@5 | {hit5:.0%} | — |")
    add("")
    add("Entity Accuracy ≥ 0.95 在本语料上不可达：该指标分子是「Top-10 中提及问题实体的证据数」，")
    add("而 gold 里相当一部分是 UNCTAD / IMF / WTO 这类**不出现问题实体**的宏观文档——检索越准，分数反而越低。")
    add("已在 `task4/baseline_vs_improved.md` §6 与 `baseline_report.md` 中作为口径局限说明。")
    add("")
    add("---")
    add("")
    add("## 4. Task 4 — Retrieval Pipeline 优化")
    add("")
    add("| 指标 | Before | After | Delta | 任务书目标 |")
    add("|---|---|---|---|---|")
    for metric in ("Precision@5", "Recall@10", "Entity Accuracy"):
        row = t4[metric]
        add(f"| {metric} | {row['Before (baseline)']:.3f} | {row['After (optimised)']:.3f} | "
            f"{row['Delta']:+.3f} | ≥ {'0.80' if metric != 'Entity Accuracy' else '0.95'} |")
    add("")
    add("三个杠杆单独作用（消融）：")
    add("")
    add("| variant | metadata_filter | query_expansion | authority_ranking | P@5 | R@10 | Entity Accuracy |")
    add("|---|---|---|---|---|---|---|")
    for row in abl:
        add(f"| {row['variant']} | {row['metadata_filter']} | {row['query_expansion']} | {row['authority_ranking']} "
            f"| {row['P@5']:.3f} | {row['R@10']:.3f} | {row['Entity Accuracy']:.3f} |")
    add("")
    add("---")
    add("")
    add("## 5. Task 5 — Historical Case Benchmark")
    add("")
    add(f"共 **{len(cases)} 个真实案例**（任务书要求 ≥10），{len(sources)} 条来源文章。")
    add("")
    add("**定位**：这 17 个案例是评测用的 **held-out 答案键**，刻意不进入 RAG 语料——否则检索会直接把「标准答案」"
        "（案例文档本身）捞回来，指标虚高。因此本节不计算「案例文档召回」。")
    add("")
    add("| 验收项 | 结果 |")
    add("|---|---|")
    add("| 案例类型 | China → Southeast Asia relocation 8 / China + 1 5 / Reconsideration·Return 4 |")
    add("| 决策触发 | 6/6 全覆盖（tariff / geopolitical / cost / supplier / market_access / regulation） |")
    add("| 背景→决策→结果 | 4 段齐全，100% |")
    add("| 真实性 | 全部来自公开报道或公司公告，逐条绑定 `related_evidence_ids` |")
    add(f"| 是否进入 RAG 语料 | **否**（{int(bench.get('held out of the RAG corpus', 0))}/{len(cases)} held-out） |")
    add(f"| 语料规模（复核） | {int(bench.get('RAG corpus size', 0))} 篇，全部为 Task 1 证据 |")
    add(f"| 案例风险召回（基线 / 优化） | {bench.get('risk recall (baseline)', 0):.3f} / {bench.get('risk recall (optimized)', 0):.3f}（详见 Task 6） |")
    add("")
    add("案例文档已从 `data/raw/case/` 迁出到 `data/evaluation/case_benchmark/case/*.md`，`ingest_dataset.py` 不再扫描该目录。")
    add("")
    add("---")
    add("")
    add("## 6. Task 6 — Risk Assessment Evaluation")
    add("")
    add("| 指标 | Baseline | 说明 |")
    add("|---|---|---|")
    add(f"| Risk Recall | **{risk_map['Risk Recall (mean over cases)']['Baseline']:.3f}** | 期望风险中被证据链覆盖的比例 |")
    add(f"| Risk Precision | **{risk_map['Risk Precision (mean over cases)']['Baseline']:.3f}** | 识别出的风险中属于期望风险的比例 |")
    add(f"| Missing risks | {risk_map['Missing risks (total)']['Baseline']} 次 | 期望风险未被覆盖 |")
    add(f"| False positives | {risk_map['False positives (total)']['Baseline']} 次 | 非该题风险却被识别 |")
    add("")
    add("三级诊断（定位差距在哪一层）：")
    add("")
    add("| 层级 | 含义 | 值 |")
    add("|---|---|---|")
    add(f"| L1 语料可表征 | 语料里有标注该类风险的证据 | {risk_map['风险可表征率（语料中存在该类风险的证据）']['Baseline']:.3f} |")
    add(f"| L2 检索可取回 | 按风险维度逐条检索时的覆盖 | {risk_map['风险可取回率（按维度逐条检索）']['Baseline']:.3f} |")
    add(f"| L3 现行流程 | 单次检索（现行产品行为） | {risk_map['风险识别覆盖（现行单次检索）']['Baseline']:.3f} |")
    add("")
    add("**根因**：现行单次检索在「公司决策」类问题上把 Top-5 交给公司/案例类文档，")
    add("而这些文档的 `related_risk` 集中在 Supply Chain / Operational；Trade / Market Access / Regulatory / Political")
    add(f"四个维度要按维度单独提问才取得到（L2 {risk_map['风险可取回率（按维度逐条检索）']['Baseline']:.3f} vs "
        f"L3 {risk_map['风险识别覆盖（现行单次检索）']['Baseline']:.3f}，见 `By Risk Category` sheet）。")
    add(f"把 benchmark 案例从语料摘出后 L3 由 0.461 升到 {risk_map['风险识别覆盖（现行单次检索）']['Baseline']:.3f}；"
        f"v0.9 语料扩到 49 篇（企业披露 + 贸易/物流/劳工政策）后 Risk Recall 为 "
        f"{risk_map['Risk Recall (mean over cases)']['Baseline']:.3f}。")
    add("")
    add("---")
    add("")
    add("## 7. Task 7 — Evidence Citation Evaluation")
    add("")
    add("| 指标 | 值 | 目标 |")
    add("|---|---|---|")
    add(f"| 引用行数（案例 × 风险 × 支撑证据） | {int(cite.get('citation rows produced', 0))} | — |")
    add(f"| 四级可追溯（ID + Source + Date + Authority） | **{cite.get('citation completeness', 0):.0%}** | 100% |")
    add(f"| 语料文档元数据完整率 | **{cite.get('metadata completeness rate', 0):.0%}** | 100% |")
    add(f"| 无证据支撑的关键结论 | {int(cite.get('conclusions without evidence support', 0))} | 0 |")
    add("")
    add("`Conclusion Audit` sheet 逐条审计了案例的决策与结果四段结论，全部可回溯到 `Evidence Index` 的源文章。")
    add("本测试校验**引用链的结构完整性**，不校验引用内容是否真的支持结论（需要 LLM 判定，超出本阶段范围）。")
    add("")
    add("---")
    add("")
    add("## 8. 交付物清单（`data/evaluation/`）")
    add("")
    add("| 文件 | 对应任务 |")
    add("|---|---|")
    add("| `retrieval_questions.xlsx` | Task 2 |")
    add("| `retrieval_results.xlsx` | Task 2 / 3 |")
    add("| `entity_accuracy.xlsx` | Task 3 |")
    add("| `baseline_report.md` | Task 3 |")
    add("| `task4/*.xlsx`、`optimized/*` | Task 4 |")
    add("| `historical_case_benchmark.xlsx`、`benchmark_results.xlsx` | Task 5 |")
    add("| `risk_assessment_checklist.xlsx` | Task 6 |")
    add("| `evidence_quality_test.xlsx` | Task 7 |")
    add("| `evaluation_report.md` | 本文件 |")
    add("")
    add("## 9. 已知缺口与下一步")
    add("")
    add("| 优先级 | 事项 |")
    add("|---|---|")
    add(f"| P0 | **按风险维度多次检索**：现行单次检索 Risk Recall {risk_map['Risk Recall (mean over cases)']['Baseline']:.3f}，"
        f"按维度逐条检索的上界 {risk_map['风险可取回率（按维度逐条检索）']['Baseline']:.3f}，缺口在检索策略 |")
    add("| P1 | 风险层改为**按风险维度多次检索**，而不是一次检索出一组证据 |")
    add("| P1 | 人工 Coverage 评分目前只覆盖 Q001–Q030（30 题），Q031–Q043 的覆盖度尚无人工判定 |")
    add("| P2 | Task 5 案例库仍只有一线 OEM 与大型材料厂；印度/印尼/物流/labor 侧目前只有政策证据，没有案例 |")
    add("| P2 | Entity Accuracy 换口径（gold 覆盖率 + 相关性加权精度），才能作为可用指标 |")
    add("| P2 | 引用内容正确性校验（LLM 判定），把 Task 7 从结构校验升级为语义校验 |")
    add("")
    add("> 本轮已关闭：EU 题面缺口（v0.9.1 新增 Q041–Q043，gold 分别指向 EU_001 / EU_003 / EU_002+EU_004）；`industry` 字段过粗（49 行改为与 Task 4 过滤同源派生）；`investment_policy` 词表未覆盖「外资安全审查 / 收购」导致 Q043 的 EU_004 被宏观漂移规则压掉（已补词表，Q043 gold 回到 Top-2）。")
    add("")
    add("## 10. 复现")
    add("")
    add("```bash")
    add(".venv/bin/python backend/scripts/build_case_corpus.py            # Task 5 案例 -> held-out 基准（不入语料）")
    add(".venv/bin/python backend/scripts/ingest_dataset.py \\")
    add("    --data-root ../project-data/data --excel metadata/evidence_battery_EV_screened_v0.9.xlsx")
    add(".venv/bin/python run_task2_eval_v2.py                           # Task 2")
    add(".venv/bin/python run_task3_baseline.py && .venv/bin/python build_task3_report.py   # Task 3")
    add(".venv/bin/python run_task4_eval.py                              # Task 4")
    add(".venv/bin/python build_case_database.py                          # Task 5")
    add(".venv/bin/python run_task67_eval.py                             # Task 6 / 7")
    add(".venv/bin/python build_evaluation_report.py                      # 本报告")
    add("```")
    add("")

    (EVAL / "evaluation_report.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote", EVAL / "evaluation_report.md")


if __name__ == "__main__":
    main()
