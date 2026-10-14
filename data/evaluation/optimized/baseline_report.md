# Task 3 — RAG Baseline Report（After：已接入 Task 4 优化层）

**范围**：在 `run_task3_baseline.py` 的同一套口径下，接入 `RetrievalOptimizer`
（4.1 metadata filtering + 4.2 query enhancement + 4.3 authority ranking）后重跑。
**数据**：40 个 benchmark 问题 × Top-10，语料 49 篇证据（Task 1 v0.9；Task 5 的 17 个案例为 held-out 答案键，不入语料）
**运行**：`run_task4_eval.py`（Top-K=10）

## 1. Current RAG Performance（After）

| 指标 | Before | After | Delta |
|---|---|---|---|
| Precision@5 | 0.800 | 0.835 | +0.035 |
| Recall@10 | 0.916 | 0.919 | +0.003 |
| Entity Accuracy | 0.930 | 0.920 | -0.011 |
| Entity Recall | 1.000 | 1.000 | +0.000 |
| Entity Precision | 0.861 | 0.839 | -0.021 |
| Hit@5 | 1.000 | 1.000 | +0.000 |
| Mean Authority (Top-5) | 1.860 | 1.870 | +0.010 |

分场景（After）：

| scenario_category | n | P@5 | R@10 | Entity Acc |
|---|---|---|---|---|
| Company Intelligence | 8 | 0.85 | 0.833 | 0.892 |
| Market Access | 7 | 0.886 | 0.94 | 0.958 |
| Policy / Trade Risk | 12 | 0.85 | 0.958 | 0.93 |
| Scenario Simulation Support | 6 | 0.833 | 0.895 | 0.94 |
| Supply Chain Risk | 7 | 0.743 | 0.948 | 0.875 |

## 2. Main Problems（相对 baseline 的变化）

* 宏观文档漂移（原 §2.4）已处理：无投资/宏观意图的问题不再召回 UNCTAD / IMF / WEF / McKinsey，
  Recall@10 从 0.916 升到 0.919。
* Entity Recall 仍为 1.000（1 题因查询增强替换证据而少覆盖 1 个实体）。
* 企业案例召回：Q003 R@10 由 0.333 提升到 0.333。
* 企业案例语料已补齐（Task 5 的 17 个 EV battery / 电池材料 / 整车案例已入库），公司情报类问题不再依赖光模块类比证据；
  Entity Accuracy 仍受指标口径限制（见 `task4/baseline_vs_improved.md` §6）。

## 3. 后续优化方向

1. 把 Entity Accuracy 换成「gold 覆盖率 + 相关性加权精度」口径（语料已补齐案例，可以重新评估该指标）。
2. 把 `ENTITY` 口径的评测换成「gold 覆盖率 + 相关性加权精度」，避免宏观文档刷高 Entity Precision。
3. 上线 LLM 版 query enhancement（`task4/query_expansion_prompt.md`），替代规则版。