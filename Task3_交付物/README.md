# Task 3 — RAG Baseline Deliverables

评测集：46 题 × Top-10；语料：53 篇 Task 1 证据。Task 5 的 17 个案例为 held-out，不进入语料。

## Baseline

| 指标 | 值 |
|---|---:|
| Precision@5 | 0.765 |
| Recall@10 | 0.908 |
| Entity Accuracy（Entity Recall@5） | 0.994 |
| Hit@5 / Hit@10 | 100% / 100% |

## 文件

| 文件 | 内容 |
|---|---|
| `retrieval_questions.xlsx` | 46 道决策场景检索题；Q044–Q046 为 B4 gold 补齐题 |
| `retrieval_results.xlsx` | 460 行 Top-10 检索结果、逐题 Summary、评分说明 |
| `entity_accuracy.xlsx` | Entity Recall@5 逐题/逐实体诊断，Entity Precision@5 单列 |
| `baseline_report.md` | 当前 RAG 表现、主要问题与优化方向 |

复现：`.venv/bin/python run_task3_baseline.py && .venv/bin/python build_task3_report.py`
