# Task 4 — Retrieval Optimisation Deliverables

评测集：46 题 × Top-10；语料：53 篇证据。Before/After 均由同一个 `run_task3_baseline.py` writer 计算。

## 结果

| 指标 | Before | After | 任务书目标 |
|---|---:|---:|---:|
| Precision@5 | 0.765 | **0.817** | ≥ 0.80 |
| Recall@10 | 0.908 | **0.913** | ≥ 0.80 |
| Entity Accuracy（Entity Recall@5） | 0.994 | **1.000** | ≥ 0.95 |

## 文件

| 文件 | 内容 |
|---|---|
| `metadata_filter_test.xlsx` | 4.1 元数据过滤：检测字段、before/after pool、drop log、策略 |
| `query_before_after.xlsx` | 4.2 Query enhancement：46 题原始查询、扩展查询、触发规则 |
| `query_expansion_prompt.md` | 4.2 LLM 版 query enhancement prompt |
| `authority_ranking_test.xlsx` | 4.3 Authority ranking：权重、gold 排名变化、示例 |
| `task4_before_after.xlsx` | 总表与消融实验 |
| `baseline_vs_improved.md` | 结论、被否配置、逐项解释与复现命令 |

## 代码

- `backend/app/retrieval_optimizer.py`：三个优化杠杆的统一接入层
- `backend/app/evidence_metadata.py`：Task 1 schema → 检索 metadata
- `backend/app/metadata_filter.py`：4.1 过滤规则
- `backend/app/query_enhancement.py`：4.2 查询增强
- `backend/app/authority_ranking.py`：4.3 权威性 banded re-ranking

## 复现

```bash
.venv/bin/python run_task4_eval.py
```

相关数据写入 `project-data/data/evaluation/task4/` 与 `optimized/`。
