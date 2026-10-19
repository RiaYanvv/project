# Task 3 — RAG Baseline Report

**范围**：当前（未做 metadata filtering / query enhancement / authority ranking 优化）的检索能力
**数据**：46 个 benchmark 问题 × Top-10，语料 53 篇证据（Task 1 v0.9 政策/宏观/贸易/监管/企业披露/物流/劳工；Task 5 的 17 个案例为 held-out 答案键，不入语料），`backend/test_data/app.db`
**运行**：`run_task3_baseline.py`（Top-K=10）；报告由 `build_task3_report.py` 从结果文件生成

---

## 1. 总结 — Current RAG Performance

| 指标 | Baseline | 说明 |
|---|---|---|
| **Precision@5** | **0.765** | Top-5 中 relevance ≥ 1 的比例，按题平均 |
| **Recall@10** | **0.908** | Top-10 中召回的 gold 证据 / 该题 gold 总数，按题平均 |
| **Entity Accuracy** | **0.994** | 问题中命名实体在 Top-5 中的覆盖率，39 个含实体问题 |

支撑指标：

| 指标 | Baseline |
|---|---|
| Entity Recall | 0.994（问题中的实体在 Top-5 中的覆盖） |
| Entity Precision | 0.887（Top-5 中 11.3% 的条目不提及问题实体；诊断项，不并入 headline） |
| Hit@5 / Hit@10 | 100% / 100%（每题至少 1 条 gold） |
| Mean Authority (Top-5) | 1.88（S/A+/A=2，B+=1） |

分场景：

| scenario_category | n | P@5 | R@10 | Entity Acc |
|---|---|---|---|---|
| Company Intelligence (8) | 8 | 0.775 | 0.917 | 1.000 |
| Market Access (9) | 9 | 0.756 | 0.913 | 0.969 |
| Policy / Trade Risk (16) | 16 | 0.775 | 0.944 | 1.000 |
| Scenario Simulation Support (6) | 6 | 0.800 | 0.829 | 1.000 |
| Supply Chain Risk (7) | 7 | 0.714 | 0.876 | 1.000 |

**一句话结论**：Top-5 的"能不能捞到正确证据"没有明显问题（Hit@5 = 100%），
Recall@10 = 0.908 的主要拖累来自**企业案例题**与**案例证据对政策/宏观题的过召回**；
Entity Accuracy (0.994) 衡量实体覆盖率；Entity Precision (0.887) 单列为诊断项，不并入 headline。

---

## 2. Main Problems

### 2.1 案例证据对政策/宏观题的过召回（新增，语料扩容后出现）

17 条企业案例入库后，案例叙述与"中国/电池/布局/风险"等通用词高度重合，
在**非案例类**问题里也开始占据 Top-5：
- `Q011`（Policy / Trade Risk）Top-5 含 0 条企业案例，P@5 = 1.00，R@10 = 1.00
- `Q012`（Policy / Trade Risk）Top-5 含 0 条企业案例，P@5 = 0.80，R@10 = 0.50
- `Q013`（Policy / Trade Risk）Top-5 含 0 条企业案例，P@5 = 1.00，R@10 = 1.00
- `Q022`（Market Access）Top-5 含 1 条企业案例，P@5 = 0.60，R@10 = 0.75
- `Q029`（Scenario Simulation Support）Top-5 含 0 条企业案例，P@5 = 0.60，R@10 = 0.60

根因：案例文档 topic 统一为「供应链布局」，而现有重排规则只对宏观文档做了处理，
对案例文档没有"仅在问企业案例时才召回"的约束。这也是 Task 4.1 本轮要补的规则。

### 2.2 企业案例召回的结构性问题

- 新入库 17 条案例中，**13 条为 B+（媒体转述）**，仅 3 条达到 S（公司公告/投资者互动平台）。
- `RELOC_001`（比亚迪泰国）、`RELOC_002`（长安泰国）为整车厂，电池链（`RELOC_003`–`008`）以国轩/亿纬/欣旺达/蜂巢/华友/中伟为主。
- **缺 EU 电池法规合规案例、印度进入案例、二线厂商/劳工/物流（Operational Risk）案例**；EU 相关 Market Access 问题仍只能靠政策文件回答。

### 2.3 二线来源与企业案例排序偏低（Policy documents ranked low — 部分成立）

| authority | 条数 | 平均排名 | 进 Top-3 |
|---|---|---|---|
| S | 83 | 2.64 | 75% |
| A+ | 30 | 3.17 | 63% |
| A | 10 | 4.20 | 30% |
| B+ | 19 | 4.21 | 47% |

### 2.4 宏观文档漂移（较上一版明显减轻）

上一版（30 篇语料）中 `UNCTAD_001 / WTO_001 / IMF_001 / WEF_001` 会大量漂入
`Q008 / Q010 / Q016 / Q017 / Q020 / Q028` 等非宏观问题的 Top-10；
本次只剩少量残留（`Q008` rank 9、`Q020` rank 7），因为案例证据挤占了这些位置。
注意这是「以案例换宏观」：漂移减轻不等于排序变好，见 §2.1。

### 2.5 语料层面的结构性缺口

- 企业案例已补齐（Task 5：17 条），但**仍缺 S/A 级的公司年报**；
  只有 `RELOC_001`/`RELOC_002`/`RETURN_001` 达到 S，其余为 B+ 媒体转述。
- EU / 印度 / 墨西哥 / 美国本土案例缺失，Market Access 场景仍偏政策文件。

---

## 3. 后续优化方向

| 问题 | 对应 Task 4 动作 | 预期影响 |
|---|---|---|
| 案例过召回（2.1）| 4.1 Metadata Filtering：把案例证据限定在"问企业案例"的问题里 | P@5 / R@10 |
| 企业案例召回（2.2）| 4.2 Query Enhancement：公司名/国家/决策类型扩展 | 案例题 R@10 |
| A/B+ 排序（2.3）| 4.3 Authority Ranking：similarity + authority 带内 tie-break | A 级进入 Top-3 |
| 宏观文档漂移（2.4）| 4.1 F1 宏观漂移规则 | 减少无关宏观文档 |
| 语料缺口（2.5）| 补 EU/EU 电池法规、印度进入、二线厂商案例 | 上限提升 |

---

## 4. 验收基线对照（Task 4 目标）

| 指标 | 任务书假设 Before | 实测 Baseline | 任务书 After 目标 |
|---|---|---|---|
| Precision@5 | 65% | **76.5%** | ≥ 80% |
| Recall@10 | 70% | **90.8%** | ≥ 80% |
| Entity Accuracy | 85% | **99.4%** | ≥ 95% |

**说明**：实测 baseline 高于任务书的假设值；修订后的 Entity Accuracy（实体覆盖率）已超过 95% 目标。
Entity Precision 作为独立诊断项报告，避免与 Precision@5 / Relevance 重复计分（见 `task4/baseline_vs_improved.md` §6）。

---

## 5. 方法说明与口径

**Precision@5** = Top-5 中 relevance ≥ 1 的条数 ÷ 5，按题平均。
relevance 判定：2 = 在该题 `expected_evidence_ids` 内；1 = 不在 gold 内，但 topic 属于该题 topic 桶。

**Recall@10** = Top-10 中召回的 gold 证据数 ÷ 该题 gold 总数，按题平均。

**Entity Accuracy** = **Entity Recall@5**：问题文本中出现实体在 Top-5 中被覆盖的比例，只对**问题文本中出现实体**的 39 题计算；
无实体问题不计入。

**Entity Precision@5** = Top-5 中提及问题实体的条目占比，作为诊断项单独报告；
不并入 Entity Accuracy，避免与 Precision@5 / Relevance 对集合精度重复计分。

**已知口径局限**
1. 目标实体只从问题文本提取，**不使用 gold 证据**，避免循环论证。
2. 通用实体（China / United States / tariff）在多数文档中都出现，会**抬高** Entity Precision。
3. 实体识别基于规则词典，未用 NER 模型。
4. 本题集 Entity Recall 为 0.994：仅 1 个实体落在 Top-5 之外；
   Top-5 集合纯度由 Entity Precision（0.887）与 Precision@5 分别报告。
5. `retrieval_results.xlsx` 中的 relevance / authority 为自动判定；人工评分见 Task 2 的 `Task2_manual_scoring_v4.xlsx`。

---

## 6. 最弱的题（优先优化对象）

| question_id | 场景 | P@5 | R@10 | Entity Acc |
|---|---|---|---|---|
| Q003 | Company Intelligence | 1 | 0.333 | 1 |
| Q012 | Policy / Trade Risk | 0.8 | 0.5 | n/a |
| Q030 | Scenario Simulation Support | 0.8 | 0.571 | 1 |
| Q029 | Scenario Simulation Support | 0.6 | 0.6 | n/a |
| Q010 | Policy / Trade Risk | 0.8 | 0.6 | 1 |
| Q016 | Supply Chain Risk | 0.6 | 0.667 | 1 |
| Q019 | Supply Chain Risk | 1 | 0.667 | n/a |
| Q022 | Market Access | 0.6 | 0.75 | 1 |

---

## 7. 交付物

| 文件 | 内容 |
|---|---|
| `retrieval_questions.xlsx` | 46 个测试问题（同 Task 2） |
| `retrieval_results.xlsx` | `Summary` 指标看板 / `retrieval_results` 460 行（46 题 × Top-10）/ `question_summary` |
| `entity_accuracy.xlsx` | `Entity Accuracy` 逐题 / `Entity Detail` 逐实体 / `Summary` |
| `baseline_report.md` | 本文件 |
