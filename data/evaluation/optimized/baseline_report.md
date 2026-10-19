# Task 3 — RAG Baseline Report（After：已接入 Task 4 优化层）

**范围**：在 `run_task3_baseline.py` 的同一套口径下，接入 `RetrievalOptimizer`
（4.1 metadata filtering + 4.2 query enhancement + 4.3 authority ranking）后重跑。
**数据**：46 个 benchmark 问题 × Top-10，语料 53 篇证据（Task 1 v0.9.2；Task 5 的 17 个案例为 held-out 答案键，不入语料）
**运行**：`run_task4_eval.py`（Top-K=10）

## 1. Current RAG Performance（After）

| 指标 | Before | After | Delta |
|---|---|---|---|
| Precision@5 | 0.765 | 0.817 | +0.052 |
| Recall@10 | 0.908 | 0.913 | +0.005 |
| Entity Accuracy | 0.994 | 1.000 | +0.006 |
| Entity Recall | 0.994 | 1.000 | +0.006 |
| Entity Precision | 0.887 | 0.882 | -0.005 |
| Hit@5 | 1.000 | 1.000 | +0.000 |
| Mean Authority (Top-5) | 1.878 | 1.896 | +0.017 |

分场景（After）：

| scenario_category | n | P@5 | R@10 | Entity Acc |
|---|---|---|---|---|
| Company Intelligence | 8 | 0.85 | 0.833 | 1.0 |
| Market Access | 9 | 0.8 | 0.876 | 1.0 |
| Policy / Trade Risk | 16 | 0.825 | 1.0 | 1.0 |
| Scenario Simulation Support | 6 | 0.8 | 0.829 | 1.0 |
| Supply Chain Risk | 7 | 0.8 | 0.924 | 1.0 |

## 2. Main Problems（相对 baseline 的变化）

* 宏观文档漂移（原 §2.4）已处理：无投资/宏观意图的问题不再召回 UNCTAD / IMF / WEF / McKinsey，
  Recall@10 由 0.908 变为 0.913（+0.005）。
* Entity Recall 仍为 1.000（1 题因查询增强替换证据而少覆盖 1 个实体）。
* 企业案例召回：Q003 R@10 由 0.333 提升到 0.333。
* v0.9.1 补了 `investment_policy` 词表缺口：题面写「外资安全审查 / 收购当地资产」时不触发投资意图，
  F1 宏观漂移规则会把 `EU_004`（对外投资）压出 Top-10（Q043 一度 R@10 = 0.500）；补入「外资安全审查 /
  安全审查 / 收购 / 并购 / foreign investment screening」后，Q043 的 `EU_002`+`EU_004` 回到 Top-2。
* 语料中的案例型证据是 `CASE_001`–`CASE_010`（金属铸造 / 光模块 / 光伏类比 + BIS 穿透规则案例）；
  Task 5 的 17 个真实迁移案例是 **held-out 答案键**，不入语料。
* Entity Accuracy 仍受指标口径限制（见 `task4/baseline_vs_improved.md` §6）。

## 3. 后续优化方向

1. 把 Entity Accuracy 换成「gold 覆盖率 + 相关性加权精度」口径（语料已补齐案例，可以重新评估该指标）。
2. 把 `ENTITY` 口径的评测换成「gold 覆盖率 + 相关性加权精度」，避免宏观文档刷高 Entity Precision。
3. 上线 LLM 版 query enhancement（`task4/query_expansion_prompt.md`），替代规则版。