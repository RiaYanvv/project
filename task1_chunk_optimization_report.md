# Task 1 — Evidence / Chunk 优化报告

日期：2026-10-08
对象：`backend/test_data/app.db` 知识库 + `ingest_dataset.py` / `knowledge.py`
备份：`backend/test_data/app.db.before_chunk_fix_20261008_213729`（284 MB，可回滚）

---

## 1. 结论

Task 1 的 evidence 表和 task2 的题都没问题，出问题的是**evidence → RAG chunk 这一步**。
修复后 chunk 数 **30,303 → 2,872（-90%）**，HTML 噪声、结构体转储、重复摘要全部清零，
task2 检索质量**无回退**（Hit@3 / Hit@5 仍 100%）。DB 体积 **284 MB → 42.5 MB**。

## 2. 根因（修复前实测）

| 问题 | 数量 | 占比 | 说明 |
| --- | --- | --- | --- |
| 结构体转储 chunk | 22,416 | 74.0% | `ITA_001` 合并筛查清单被按 950 字符硬切，2.5 万个近似重复片段淹没索引 |
| 含原始 HTML | 1,071 | 3.5% | `CASE_001/004/006/007/008/010`、`MOFCOM_002`，chunk 里是 `<!DOCTYPE>`/`<style>`/`<meta>` |
| 近重复 chunk | 5,849 | 19.3% | 前 200 字符相同；主要来自 `ITA_001` 与同一篇文章的多份副本 |
| 低信息量 chunk | 7,184 | 23.7% | 去重后不足 40 token 的样板文本 |
| 摘要字段重复 | 29 | — | `Key finding` 与 `Content summary` 内容完全相同，重复进正文 |

附带发现两个工程 bug：

- `load_metadata()` 读的是**工作簿当前激活的 sheet**。一旦用 Excel 点开过 `task1_review_20` 页签，
  入库就会读到 20 行评测表（没有 `document_path`），**直接灌进去 0 条**。已改为优先读 `evidence`/`sources`。
- `chunk_text()` 在 `ingest_document()` 里拿到的是已经被 `normalize_text()` 压成单行的文本，
  段落/标题结构全部丢失，只能按句号硬切。

## 3. 已做的修复

代码改动（3 个文件）：

1. `backend/app/knowledge.py`
   - `chunk_text()` 重写为**结构感知**分块：先按空行/段落切块，再按目标长度合并，超长块才做句子切分；
     同一文档内前 400 字符相同的 chunk 视为重复丢弃。
   - `ingest_document()` 改为从**原始文本**（保留换行）分块，存储文本仍用归一化版本，hash/统计不受影响。
2. `backend/scripts/ingest_dataset.py`
   - `read_json_gz()`：批量记录型数据源（`ITA_001` / `FR_001`）不再逐条转 chunk，改为
     “能力描述 + 去重后、上限 600 个实体名”的紧凑索引（26 + 1 chunk）。
   - `build_document()`：去掉空字段与重复的 `Content summary`（与 `Key finding` 相同则丢弃）。
   - `load_metadata()`：固定读 `sources` sheet，避免被 Excel 激活页签带偏。
3. 重灌 + `VACUUM` 收缩数据库。

## 4. 修复前后对比

| 指标 | 修复前 | 修复后 |
| --- | --- | --- |
| chunk 总数 | 30,303 | 2,872 |
| 含 HTML 的 chunk | 1,071 | 0 |
| `--- RECORD ---` 转储 chunk | 22,416 | 0 |
| 重复 summary 字段 | 29 | 0 |
| 低信息量 chunk | 7,184 | 252 |
| 近重复 chunk | 5,849 | 179 |
| 数据库体积 | 284 MB | 42.5 MB |
| task2 Hit@1 / Hit@3 / Hit@5 | 90% / 100% / 100% | 90% / 100% / 100% |
| task2 MRR | 0.9500 | 0.9444 |

真实文档的 chunk 数基本不变（如 `BIS_001` 137→132、`WEF_001` 395→405），
变化只集中在被污染的来源上。

## 5. 仍需你/队友决策的 Task 1 数据问题

这些属于**标注口径**问题，不是分块能修的：

1. **`CASE_004` / `CASE_005` / `CASE_006` 是同一篇文章。**
   三个 HTML 文件的 `<title>` 都是《【国盛通信】光——新一轮产能释放的前夜》，抽取正文 SHA 完全相同。
   但它们被标成三家不同公司的案例（中际旭创 / 新易盛 / 天孚通信）。
   后果：Q001 的 Top-5 里有 3 个名额被同一篇文章占掉。
   建议：合并为一条 evidence，或在 task1 里补 `parent_evidence_id` / 多公司共源标记。
2. **evidence 粒度 ≠ 页面粒度。**
   `CASE_004` 的 claim 是“中际旭创泰国工厂产能与国内齐平”，但入库的是整篇行业周报
   （含大量无关新闻、荐股名单）。检索命中的是泛泛的行业内容，不是那条具体事实。
   建议：task1 增加 `evidence_excerpt`（支撑该结论的原文片段/页码），入库时以 excerpt 为主、全文为辅。
3. **`authority_level` 分级 —— 已定稿**（以 `evidence_battery_EV_screened_v0.7_rebuilt.xlsx` 为准）：
   `S / A+ / A / B+`。原始 spec 的 S/A/B/C 作废：媒体类归入 `B+`。
   标准文件中的取值分布：`S`×14、`A+`×7、`A`×3、`B+`×6。

   打分映射（供 task2 的 Authority 0/1/2 对齐）：

   | authority_level | 含义（示例） | task2 Authority 分 |
   | --- | --- | --- |
   | `S` | 政府法规 / 官方文件 / 官方数据库（BIS、国务院、ITA） | 2 |
   | `A+` | 国际组织（WTO、UN、IMF、UNCTAD、WEF） | 2 |
   | `A` | 研究机构 / 咨询公司（McKinsey、CSIS、KPMG） | 2 |
   | `B+` | 主流媒体 / 二手转载（Reuters、腾讯新闻、C114） | 1 |

4. **`industry` 字段过粗。** 30 条里 27 条是 `General_Manufacturing`，只有 `MOFCOM_002`、`TRD_001` 不同。
   若要支撑 EV battery 场景，建议对政策/报告类补 `EV_Battery` / `Battery_Materials` 的适用标注。

## 6. 未处理 / 已知事项

- `pytest backend/tests` 有 1 个既有失败：`test_review_regressions.py::test_solar_chunk_does_not_pass_battery_gate`。
  已在 HEAD 版 `knowledge.py` 上复现，确认与本次改动无关，来自未提交的 `retrieval.py` 重构。
- `CASE_004/005/006` 的重复正文未做自动去重（会影响 evidence↔citation 映射），留待第 5.1 条决策后处理。

## 7. 复现命令

```bash
# 重新入库（会覆盖 app.db，建议先备份）
.venv/bin/python backend/scripts/ingest_dataset.py \
  --data-root /Users/zhengyuanyuan/Desktop/project-data/data \
  --excel metadata/evidence_battery_EV_screened_v0.7.xlsx

# task2 检索回归
.venv/bin/python run_task2_baseline.py
```

---

# 附录 A：v0.9 语料扩容实测（2026-10-14）

## A.1 分词/检索层对照（v0.8 → v0.9，同一套代码）

| 语料 | 文档 | chunk | P@5（Q001–Q030） | R@10（Q001–Q030） | Entity Accuracy | Hit@5 |
|---|---|---|---|---|---|---|
| v0.8 | 36 | 5,772 | 0.913 | 0.893 | 0.921 | 100% |
| v0.9 | 49 | 14,303 | 0.873 | 0.887 | 0.931 | 100% |

v0.9 新增 13 篇，其中 5 份一线年报（TSLA/NIO/XPEV/LI/ALB）合计约 4,732 chunk，
占新语料 1/3。它们把 P@5 拉低约 0.04：年报的通用段落（公司概况、财务附注）与政策类查询存在词面重叠，
会挤占 Top-5 名额。**这是可量化的长文档稀释，不是入库错误**。

## A.2 参数网格（确认默认值仍最优）

γ = `RETRIEVAL_LENGTH_NORM`，`pc` = `RETRIEVAL_PER_SOURCE_CANDIDATES`；40 题口径：

| γ \ pc | 40 | 80 | 160 |
|---|---|---|---|
| 0.00 | 0.780 / 0.893 | 0.775 / 0.893 | 0.785 / 0.893 |
| 0.05 | 0.785 / 0.911 | 0.785 / 0.911 | 0.780 / 0.911 |
| **0.10** | **0.800 / 0.915** | **0.800 / 0.915** | **0.800 / 0.915** |
| 0.15 | 0.790 / 0.895 | 0.795 / 0.895 | 0.790 / 0.915 |
| 0.25 | 0.780 / 0.895 | 0.780 / 0.895 | 0.770 / 0.895 |

（单元格为 P@5 / R@10。）γ=0.10 / pc=80 仍是最优组合，默认参数不变。

## A.3 尚未处理的第 4 条建议（`industry` 字段过粗）

v0.9 新增证据已在 `sources.related_industries` 使用细粒度标签（`整车/汽车`、`电池材料`、`动力电池`），
`backend/app/evidence_metadata.py::INDUSTRY_BY_TAG` 会把它派生为 `Automotive` / `Battery_Materials` / `EV_Battery`，
**Task 4 元数据过滤用的就是这个派生值**。

但 `task1_annotations` 这一"人读视图"仍沿用 v0.7 的粗口径（政策类统一写 `General_Manufacturing`，
仅 `MOFCOM_002`/`TRD_001` 例外），本次**刻意没有改动既有 36 行**，以免与你已复核过的内容产生差异。
若需要，可用一条命令按 `related_industries` 重新派生全部 49 行的 `industry` 列（派生规则已写在
`DERIVATION_RULES`，可逐字段审计）。

## A.4 复现命令（v0.9）

```bash
.venv/bin/python backend/scripts/ingest_dataset.py \
  --data-root /Users/zhengyuanyuan/Desktop/project-data/data \
  --excel metadata/evidence_battery_EV_screened_v0.9.xlsx
.venv/bin/python run_task2_eval_v2.py
.venv/bin/python run_task3_baseline.py && .venv/bin/python build_task3_report.py
.venv/bin/python run_task4_eval.py
.venv/bin/python run_task67_eval.py
.venv/bin/python build_task2_manual_scoring.py   # -> ~/Downloads
cp ~/Downloads/Task2_manual_scoring_v3.xlsx .
.venv/bin/python fill_task2_manual_scoring.py
.venv/bin/python build_evaluation_report.py
```
