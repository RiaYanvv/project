# Locus — RAG / Evidence / Evaluation 阶段报告

**范围**：Evidence schema（Task 1）→ 检索评测集（Task 2）→ 基线（Task 3）→ 优化（Task 4）
→ 历史案例基准（Task 5）→ 风险识别（Task 6）→ 引用可靠性（Task 7）。
**语料**：30 篇证据 / 2872 个 chunk（全部为 Task 1 政策·宏观·贸易证据），`backend/test_data/app.db`
**证据库**：`metadata/evidence_battery_EV_screened_v0.7.xlsx`（30 条）；Task 5 的 17 个案例作为 **held-out 答案键**存放在 `evaluation/case_benchmark/`，**不进入 RAG 语料**（避免答案泄漏）

> 本报告由 `build_evaluation_report.py` 从交付物文件生成，数字不会与 xlsx 漂移。

---

## 0. 结论摘要

| # | 任务 | 交付物 | 关键指标 | 达标 |
|---|---|---|---|---|
| 1 | Evidence schema | `evidence_battery_EV_screened_v0.7.xlsx`（+ `evaluation/case_benchmark/evidence_cases_v0.1.xlsx`） | 30 条统一 schema、4 级 authority、来源可追溯 | ✅ |
| 2 | 检索评测集 + 人工评分 | `retrieval_questions.xlsx` / `retrieval_results.xlsx` / `Task2_manual_scoring_v3.xlsx` | Relevance 1.753 / Authority 1.813 / Hit@5 100% | ✅ |
| 3 | 检索基线 | `data/evaluation/retrieval_questions.xlsx` / `retrieval_results.xlsx` / `entity_accuracy.xlsx` + `baseline_report.md` | P@5 0.920、R@10 0.893、EA 0.885 | ✅ / ⚠️EA |
| 4 | 检索优化 | `task4/*.xlsx` + `baseline_vs_improved.md` + `optimized/*` | P@5 0.940、R@10 0.931 | ✅ |
| 5 | 历史案例基准（held-out） | `historical_case_benchmark.xlsx` + `benchmark_results.xlsx` | 17 个真实案例、17/17 已摘出语料 | ✅ |
| 6 | 风险识别 | `risk_assessment_checklist.xlsx` | Recall 0.779 / Precision 0.566 | ⚠️ |
| 7 | 引用可靠性 | `evidence_quality_test.xlsx` | 引用可追溯率 100%、语料元数据完整率 100% | ✅ |

**一句话**：检索层已经可用（基线 P@5 0.920 / R@10 0.893，优化后 0.940 / 0.931，均超任务书 80% 目标）；
**风险识别层仍是短板**——把 Task 5 的 17 个案例从语料摘出（改为 held-out 答案键）后，Risk Recall 由 0.461 升到 0.779，剩余缺口在「按风险维度检索」的策略，而非语料覆盖。

---

## 1. Task 1 — Evidence Database Schema

| 项 | 结果 |
|---|---|
| 证据条数 | Task 1 政策/宏观 30 条（进入 RAG 语料）；Task 5 案例 17 条为 held-out 答案键，**不入语料** |
| 语料文档 / chunk | 30 / 2872（chunk 优化前 30,303） |
| authority 分级 | S / A+ / A / B+（S=政府法规·WTO·UN·官方公告；A+=IMF·UNCTAD；A=CSIS·McKinsey·KPMG；B+=媒体·券商） |
| 分类字段 | industry / topic / evidence_type / related_risk（六类）/ data_status |
| 派生规则 | `backend/app/evidence_metadata.py`，逐字段可审计 |

---

## 2. Task 2 — Retrieval Evaluation Dataset

30 个问题，覆盖 5 类场景（Company Intelligence 5 / Policy·Trade Risk 10 / Supply Chain Risk 5 / Market Access 5 / Scenario Simulation 5）。

人工评分（`Task2_manual_scoring_v3.xlsx`，150 条逐条判定）：

| 指标 | 目标 | 实测 |
|---|---|---|
| Avg Relevance (Top-5) | ≥ 1.5 | **1.753** |
| Avg Authority (Top-5) | ≥ 1.5 | **1.813** |
| Hit@5（≥1 条正确 Evidence） | ≥ 80% | **100%** |
| Avg Coverage (0-2) | 参考 | 1.867 |

---

## 3. Task 3 — Retrieval Baseline

| 指标 | Baseline | 任务书目标 |
|---|---|---|
| Precision@5 | **0.920** | ≥ 0.80 ✅ |
| Recall@10 | **0.893** | ≥ 0.80 ✅ |
| Entity Accuracy | **0.885** | ≥ 0.95 ❌（口径不可达，见下） |
| Hit@5 | 100% | — |

Entity Accuracy ≥ 0.95 在本语料上不可达：该指标分子是「Top-10 中提及问题实体的证据数」，
而 gold 里相当一部分是 UNCTAD / IMF / WTO 这类**不出现问题实体**的宏观文档——检索越准，分数反而越低。
已在 `task4/baseline_vs_improved.md` §6 与 `baseline_report.md` 中作为口径局限说明。

---

## 4. Task 4 — Retrieval Pipeline 优化

| 指标 | Before | After | Delta | 任务书目标 |
|---|---|---|---|---|
| Precision@5 | 0.920 | 0.940 | +0.020 | ≥ 0.80 |
| Recall@10 | 0.893 | 0.931 | +0.038 | ≥ 0.80 |
| Entity Accuracy | 0.885 | 0.874 | -0.012 | ≥ 0.95 |

三个杠杆单独作用（消融）：

| variant | metadata_filter | query_expansion | authority_ranking | P@5 | R@10 | Entity Accuracy |
|---|---|---|---|---|---|---|
| baseline | False | False | False | 0.920 | 0.893 | 0.885 |
| filter_only | True | False | False | 0.927 | 0.904 | 0.892 |
| expansion_only | False | True | False | 0.920 | 0.908 | 0.878 |
| authority_only | False | False | True | 0.900 | 0.893 | 0.892 |
| full | True | True | True | 0.940 | 0.931 | 0.874 |

---

## 5. Task 5 — Historical Case Benchmark

共 **17 个真实案例**（任务书要求 ≥10），28 条来源文章。

**定位**：这 17 个案例是评测用的 **held-out 答案键**，刻意不进入 RAG 语料——否则检索会直接把「标准答案」（案例文档本身）捞回来，指标虚高。因此本节不计算「案例文档召回」。

| 验收项 | 结果 |
|---|---|
| 案例类型 | China → Southeast Asia relocation 8 / China + 1 5 / Reconsideration·Return 4 |
| 决策触发 | 6/6 全覆盖（tariff / geopolitical / cost / supplier / market_access / regulation） |
| 背景→决策→结果 | 4 段齐全，100% |
| 真实性 | 全部来自公开报道或公司公告，逐条绑定 `related_evidence_ids` |
| 是否进入 RAG 语料 | **否**（17/17 held-out） |
| 语料规模（复核） | 30 篇，全部为 Task 1 证据 |
| 案例风险召回（基线 / 优化） | 0.779 / 0.779（详见 Task 6） |

案例文档已从 `data/raw/case/` 迁出到 `data/evaluation/case_benchmark/case/*.md`，`ingest_dataset.py` 不再扫描该目录。

---

## 6. Task 6 — Risk Assessment Evaluation

| 指标 | Baseline | 说明 |
|---|---|---|
| Risk Recall | **0.779** | 期望风险中被证据链覆盖的比例 |
| Risk Precision | **0.566** | 识别出的风险中属于期望风险的比例 |
| Missing risks | 13 次 | 期望风险未被覆盖 |
| False positives | 28 次 | 非该题风险却被识别 |

三级诊断（定位差距在哪一层）：

| 层级 | 含义 | 值 |
|---|---|---|
| L1 语料可表征 | 语料里有标注该类风险的证据 | 1.000 |
| L2 检索可取回 | 按风险维度逐条检索时的覆盖 | 0.966 |
| L3 现行流程 | 单次检索（现行产品行为） | 0.779 |

**根因**：现行单次检索在「公司决策」类问题上把 Top-5 交给公司/案例类文档，
而这些文档的 `related_risk` 集中在 Supply Chain / Operational；Trade / Market Access / Regulatory / Political
四个维度要按维度单独提问才取得到（L2 0.966 vs L3 0.779，见 `By Risk Category` sheet）。
把 benchmark 案例从语料摘出后 L3 已由 0.461 升到 0.779——此前最大的干扰项就是案例文档占位。

---

## 7. Task 7 — Evidence Citation Evaluation

| 指标 | 值 | 目标 |
|---|---|---|
| 引用行数（案例 × 风险 × 支撑证据） | 170 | — |
| 四级可追溯（ID + Source + Date + Authority） | **100%** | 100% |
| 语料文档元数据完整率 | **100%** | 100% |
| 无证据支撑的关键结论 | 0 | 0 |

`Conclusion Audit` sheet 逐条审计了案例的决策与结果四段结论，全部可回溯到 `Evidence Index` 的源文章。
本测试校验**引用链的结构完整性**，不校验引用内容是否真的支持结论（需要 LLM 判定，超出本阶段范围）。

---

## 8. 交付物清单（`data/evaluation/`）

| 文件 | 对应任务 |
|---|---|
| `retrieval_questions.xlsx` | Task 2 |
| `retrieval_results.xlsx` | Task 2 / 3 |
| `entity_accuracy.xlsx` | Task 3 |
| `baseline_report.md` | Task 3 |
| `task4/*.xlsx`、`optimized/*` | Task 4 |
| `historical_case_benchmark.xlsx`、`benchmark_results.xlsx` | Task 5 |
| `risk_assessment_checklist.xlsx` | Task 6 |
| `evidence_quality_test.xlsx` | Task 7 |
| `evaluation_report.md` | 本文件 |

## 9. 已知缺口与下一步

| 优先级 | 事项 |
|---|---|
| P0 | **按风险维度多次检索**：现行单次检索 Risk Recall 0.779，按维度逐条检索的上界 0.966，缺口在检索策略 |
| P1 | 风险层改为**按风险维度多次检索**，而不是一次检索出一组证据 |
| P1 | 补齐 EU 电池法规合规、印度进入、二线厂商/劳工/物流案例（当前 17 个案例全是一线 OEM 与大型材料厂） |
| P2 | Entity Accuracy 换口径（gold 覆盖率 + 相关性加权精度），才能作为可用指标 |
| P2 | 引用内容正确性校验（LLM 判定），把 Task 7 从结构校验升级为语义校验 |

## 10. 复现

```bash
.venv/bin/python backend/scripts/build_case_corpus.py            # Task 5 案例 -> held-out 基准（不入语料）
.venv/bin/python backend/scripts/ingest_dataset.py \
    --data-root ../project-data/data --excel metadata/evidence_battery_EV_screened_v0.7.xlsx
.venv/bin/python run_task2_eval_v2.py                           # Task 2
.venv/bin/python run_task3_baseline.py && .venv/bin/python build_task3_report.py   # Task 3
.venv/bin/python run_task4_eval.py                              # Task 4
.venv/bin/python build_case_database.py                          # Task 5
.venv/bin/python run_task67_eval.py                             # Task 6 / 7
.venv/bin/python build_evaluation_report.py                      # 本报告
```
