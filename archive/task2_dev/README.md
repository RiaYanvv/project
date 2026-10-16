# Task 2 retrieval dev archive

这些文件是 Task 2 检索评估在开发迭代过程中的**历史版本**，仅作留档，不参与交付，
也不被任何现行脚本引用（`build_evaluation_report.py` 只引用 `run_task2_eval_v2.py`）。

## 现行（保留在仓库根目录）

| 用途 | 文件 |
|---|---|
| Task 2 检索评估（唯一现行版本） | `run_task2_eval_v2.py` |
| Task 2 金标准问题集 | `task2_retrieval_evaluation_v0.7.xlsx` |
| Task 2 / 3 交付物 | `retrieval_questions.xlsx`、`retrieval_results.xlsx`、`Task2_manual_scoring_v3.xlsx` |
| Task 3 基线 | `run_task3_baseline.py` |
| Task 4 优化 | `run_task4_eval.py` |
| Task 6/7 | `run_task67_eval.py` |
| 报告生成 | `build_evaluation_report.py`、`build_task3_report.py` |

## 归档内容

- `run_task2_eval*.py`（除 v2 外的 21 个迭代版本）
- `run_task2_baseline.py` 及其输出 `task2_baseline_*`
- `task2_retrieval_*.csv/json` 中间结果（30 组）
- `retrieval_results_task2_v0.9.xlsx`（31 题的旧快照，现行为 43 题）
- `task2_*_revision_proposal*.xlsx`（问题集修订过程稿）
- `local_backups/`：`*.bak_*` 与 Excel 锁文件（本机备份，已被 `.gitignore` 排除）

需要用旧版本复跑时，从本目录取用即可；不要再把它们放回根目录。
