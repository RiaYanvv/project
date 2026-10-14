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

4. **`industry` 字段过粗 —— 已在 v0.9.1 修复。** 原先 30 条里 27 条是 `General_Manufacturing`，
   只有 `MOFCOM_002`、`TRD_001` 不同。现在全部 49 行的 `industry` 改由
   `backend/app/evidence_metadata.py::build_meta()` 统一派生（与 Task 4 元数据过滤同源）：
   `EV_Battery` 32 / `Electronics_Manufacturing` 6 / `Energy_Storage` 4 / `Automotive` 4 /
   `Battery_Materials` 2 / `General_Manufacturing` 1。

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

# 附录 A — v0.8 语料（2026-10-14）

## A.1 变更

Task 1 证据库由 30 条扩到 **36 条**（`evidence_battery_EV_screened_v0.8.xlsx`）：

- 新增 4 条欧盟法规原文（`EU_001` 电池法规 / `EU_002` CRMA / `EU_003` 对华 BEV 反补贴税 / `EU_004` 外资审查框架）；
- 新增 2 条美国法规原文（`UST_001` Section 301 关税调整 / `IRS_001` IRA 清洁车辆抵免 FEOC 规则）；
- 全部为 S 级、原文落盘 `data/raw/policy/*.html`、URL 可回溯。

入库结果：**36 documents / 5,772 chunks**（v0.7 为 30 / 2,872）。authority 分布变为 `S`×20、`A+`×7、`A`×3、`B+`×6。

## A.2 v0.8 暴露出的新分块问题：长文档占位

v0.7 的 chunk 修复解决的是“**同一文档内**的重复/噪声”，但没有解决“**跨文档**的体量不均”：

| 文档 | 字符数 | chunk 数 | 说明 |
| --- | ---: | ---: | --- |
| `EU_003` | 950,498 | 1,171 | 344 页 OJ 全文（含 1,500 余条 recital），有效内容只有第 1–3 条 |
| `UNCTAD_001` | 618,911 | 826 | 世界投资报告全文 |
| `IRS_001` | 487,026 | 578 | Federal Register 全文 |
| `EU_001` | 421,391 | 528 | 欧盟电池法规全文 |
| … | | | 语料中位数：38 chunk |
| `FR_001` / `MOFCOM_002` | <1,000 | 1 | 数据库/短公告 |

后果（实测）：单篇 `EU_003` 在 800 条的候选短名单里能占 **343/800**；`EU_001` 在“电池材料企业受限方筛查”
一题里占 **507/800**。短小但真正相关的文档（如 3–8 chunk 的企业案例）根本进不了排序阶段。
v0.8 语料下 P@5 一度由 0.920 掉到 **0.853**。

## A.3 修复（在检索层，不动原文）

保留原文完整入库（可追溯性优先），改为在检索阶段做体量矫正：

1. `KnowledgeRepository.search_candidates(per_source_limit=…)`：候选短名单加**每文档配额**
   （`RETRIEVAL_PER_SOURCE_CANDIDATES`，默认 80），并相应加深 SQL 取数深度，
   保证长文档不能吃光名额。`backend/app/retrieval.py` 两个取数点都传入该配额。
2. `HybridRetrievalProvider`：来源评分加 **BM25 式长度归一**
   （`RETRIEVAL_LENGTH_NORM`，默认 0.10），按 `log10(1 + n_chunks / 语料中位数)` 温和降权。

## A.4 修复效果（同一批 30 题、同一套代码）

| 配置 | Precision@5 | Recall@10 | Entity Accuracy |
| --- | ---: | ---: | ---: |
| v0.8 语料，未修复 | 0.853 | 0.886 | 0.915 |
| v0.8 语料，仅每文档配额 | 0.860 | 0.893 | 0.917 |
| v0.8 语料，仅长度归一 | 0.907 | 0.893 | 0.910 |
| **v0.8 语料，两者都开（默认）** | **0.913** | **0.893** | **0.921** |

同口径对照（同代码、不同语料）：v0.7 → 0.907 / 0.898 / 0.894；v0.8 → 0.913 / 0.893 / 0.921。
即 **v0.8 语料在相同检索口径下优于 v0.7**。

## A.5 复现命令

```bash
.venv/bin/python backend/scripts/ingest_dataset.py \
  --data-root /Users/zhengyuanyuan/Desktop/project-data/data \
  --excel metadata/evidence_battery_EV_screened_v0.8.xlsx
.venv/bin/python run_task2_eval_v2.py
.venv/bin/python run_task3_baseline.py && .venv/bin/python build_task3_report.py
```

环境变量可调：`RETRIEVAL_LENGTH_NORM`（默认 0.10）、`RETRIEVAL_PER_SOURCE_CANDIDATES`（默认 80）。
设为 0 即关闭对应矫正，用于复现“未修复”基线。

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

（单元格为 P@5 / R@10，网格在 v0.9 的 40 题集上测得。）γ=0.10 / pc=80 仍是最优组合，默认参数不变；在加入 EU 题后的 43 题集上，默认参数实测 P@5 0.777 / R@10 0.921 / EA 0.933。

## A.3 第 4 条建议（`industry` 字段过粗）—— 已在 v0.9.1 修复

原先 `task1_annotations.industry` 沿用 v0.7 粗口径（政策类统一写 `General_Manufacturing`，30 条里 27 条如此）。
v0.9.1 起不再手工填写：49 行的 `industry` 全部改由 `backend/app/evidence_metadata.py::build_meta()` 派生，
**与 Task 4 元数据过滤使用的值完全同源**，因此 xlsx 里读到的 industry 一定等于过滤层看到的 industry。

派生分布：`EV_Battery` 32 / `Electronics_Manufacturing` 6 / `Energy_Storage` 4 / `Automotive` 4 /
`Battery_Materials` 2 / `General_Manufacturing` 1。其中 `EV_Battery` 是"EV 电池焦点范围"的通用标签，
不总是某个细分环节（细分由 `sources.related_industries` 承载）。

同时修正 `sources.related_industries` 两处错标：`TRD_001`（HS 870380 整车 + 850760 锂电池）由
`◆电子/光电` 改为 `动力电池`；`MOFCOM_002` 由 `◆随产业` 改为 `电池材料`。两次修正都能在
`task1_status` 的 "v0.9 industry correction" 行追溯（派生规则见 `DERIVATION_RULES`，逐字段可审计）。

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
