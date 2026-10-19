# Vector Database

任务书要求的 `data/vector_database/` 目录。**实际的向量/全文索引不放在 Git 里**，
这里只保留说明，避免 100MB+ 的二进制随仓库膨胀。

## 索引实际在哪

运行时索引是一个 SQLite 文件（含 FTS5 全文索引 + 向量列）：

```
backend/test_data/app.db          # 由 DATABASE_PATH 覆盖，默认即此路径
```

它被 `.gitignore` 的 `*.db` 规则排除，**不会出现在 GitHub 上**，
克隆仓库后需要本地重建（下方命令）。

当前规模（v0.9.2，2026-10-16 重建）：

| 项 | 值 |
|---|---|
| 语料文档 | 53 篇（Task 1 evidence，不含 Task 5 的 held-out 案例） |
| chunk | 14,957 |
| 表 | `knowledge_documents` / `knowledge_chunks` / `knowledge_chunks_fts*` |

## 重建

在仓库根目录执行（`--excel` 是相对 `--data-root` 的路径）：

```bash
.venv/bin/python backend/scripts/ingest_dataset.py \
    --data-root data \
    --excel metadata/evidence_battery_EV_screened_v0.9.xlsx
```

整合交付分支已将数据放在仓库根目录的 `data/`。

## 注意

- 重建后核对 `knowledge_documents` 计数应为 53。
