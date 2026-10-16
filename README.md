# EV Battery Supply-Chain Risk Agent

面向「正在实施 China+1 / 生产布局调整」的 EV 电池与材料制造企业的 AI 决策助手。
本仓库是**代码与评估流水线**；证据语料与评估产物在独立的 `data` 分支／工作区
（`project-data`）中，避免把 10 GB 级原始文件放进代码历史。

## 目录结构

| 路径 | 内容 |
|---|---|
| `backend/app/` | 产品服务：FastAPI、检索层（混合检索 + metadata filter + query enhancement + authority ranking）、报告生成 |
| `backend/scripts/` | 数据工程脚本：`ingest_dataset.py`（入库）、`build_case_corpus.py`（Task 5 案例语料）、`check_case_leakage.py`（案例泄漏审计） |
| `backend/tests/` | pytest 回归测试 |
| `run_task2_eval_v2.py` | Task 2/3 检索评估（唯一现行版本） |
| `run_task3_baseline.py` | Task 3 基线报告（Precision@5 / Recall@10 / Entity Accuracy） |
| `run_task4_eval.py` | Task 4 三项优化（metadata filtering / query enhancement / authority ranking） |
| `run_task67_eval.py` | Task 6 风险识别 + Task 7 引用可追溯性 |
| `build_*.py` | 生成交付物与 `evaluation_report.md` |
| `Task2_交付物/`、`Task4_交付物/` | 打包好的交付快照 |
| `archive/task2_dev/` | Task 2 检索开发期的历史脚本与中间结果（仅留档，不参与交付） |

## 评估流水线

```bash
# 1. 证据入库（Task 1 语料）
.venv/bin/python backend/scripts/ingest_dataset.py \
  --data-root ../project-data/data \
  --excel metadata/evidence_battery_EV_screened_v0.9.xlsx

# 2. Task 2/3：检索基线
.venv/bin/python run_task2_eval_v2.py
.venv/bin/python run_task3_baseline.py

# 3. Task 4：优化层（需 RETRIEVAL_OPTIMIZER=1）
.venv/bin/python run_task4_eval.py

# 4. Task 6/7：风险识别 + 引用可靠性
.venv/bin/python run_task67_eval.py

# 5. 汇总报告
.venv/bin/python build_evaluation_report.py

# 回归测试
.venv/bin/python -m pytest backend/tests -q
```

评估产物写入 `project-data/data/evaluation/`，索引数据库为 `backend/test_data/app.db`
（`*.db` 已在 `.gitignore` 中排除，按需重新生成）。

## 当前基线

| 指标 | 值 | 目标 |
|---|---|---|
| Precision@5 | 0.800（优化后） | ≥ 0.80 |
| Recall@10 | 0.925（优化后） | ≥ 0.80 |
| Entity Accuracy | 0.935 | ≥ 0.95（现行口径下不可达，见评估报告） |
| Task 6 风险召回 | 0.799 | 待优化（需按风险维度多次检索） |
| Task 7 引用可追溯率 | 100% | ✅ |

## 说明

- Task 5 的 17 个历史案例是 **held-out 评估答案键**，只存放在 `project-data/data/evaluation/case_benchmark/`，
  不进入检索语料；`backend/scripts/check_case_leakage.py` 用于持续校验隔离性。
- 详细结论、缺口与优化优先级见 `project-data/data/evaluation/evaluation_report.md`。
