# Task 3 — RAG Baseline Report

**范围**：当前（未做 metadata filtering / query enhancement / authority ranking 优化）的检索能力
**数据**：30 个 benchmark 问题 × Top-10，语料 30 篇证据（Task 1 政策/宏观/贸易；Task 5 的 17 个案例为 held-out 答案键，不入语料），`backend/test_data/app.db`
**运行**：`run_task3_baseline.py`（Top-K=10）；报告由 `build_task3_report.py` 从结果文件生成

---

## 1. 总结 — Current RAG Performance

| 指标 | Baseline | 说明 |
|---|---|---|
| **Precision@5** | **0.920** | Top-5 中 relevance ≥ 1 的比例，按题平均 |
| **Recall@10** | **0.893** | Top-10 中召回的 gold 证据 / 该题 gold 总数，按题平均 |
| **Entity Accuracy** | **0.885** | (实体召回 + 实体精度) / 2，24 个含实体问题 |

支撑指标：

| 指标 | Baseline |
|---|---|
| Entity Recall | 1.000（问题中的实体在 Top-10 中的覆盖） |
| Entity Precision | 0.771（Top-10 中 22.9% 的证据与问题实体无关） |
| Hit@5 / Hit@10 | 100% / 100%（每题至少 1 条 gold） |
| Mean Authority (Top-5) | 1.83（S/A+/A=2，B+=1） |

分场景：

| scenario_category | n | P@5 | R@10 | Entity Acc |
|---|---|---|---|---|
| Company Intelligence (5) | 5 | 0.920 | 0.867 | 0.887 |
| Market Access (5) | 5 | 0.960 | 0.917 | 0.900 |
| Policy / Trade Risk (10) | 10 | 0.940 | 0.910 | 0.906 |
| Scenario Simulation Support (5) | 5 | 0.840 | 0.794 | 0.887 |
| Supply Chain Risk (5) | 5 | 0.920 | 0.960 | 0.825 |

**一句话结论**：Top-5 的"能不能捞到正确证据"没有明显问题（Hit@5 = 100%），
Recall@10 = 0.893 的主要拖累来自**企业案例题**与**案例证据对政策/宏观题的过召回**；
Entity Accuracy (0.885) 受指标口径限制，主要反映 Entity Precision (0.771)。

---

## 2. Main Problems

### 2.1 案例证据对政策/宏观题的过召回（新增，语料扩容后出现）

17 条企业案例入库后，案例叙述与"中国/电池/布局/风险"等通用词高度重合，
在**非案例类**问题里也开始占据 Top-5：
- `Q011`（Policy / Trade Risk）Top-5 含 1 条企业案例，P@5 = 0.80，R@10 = 1.00
- `Q012`（Policy / Trade Risk）Top-5 含 1 条企业案例，P@5 = 0.60，R@10 = 0.50
- `Q013`（Policy / Trade Risk）Top-5 含 0 条企业案例，P@5 = 1.00，R@10 = 1.00
- `Q022`（Market Access）Top-5 含 2 条企业案例，P@5 = 0.80，R@10 = 0.75
- `Q029`（Scenario Simulation Support）Top-5 含 1 条企业案例，P@5 = 0.60，R@10 = 0.60

根因：案例文档 topic 统一为「供应链布局」，而现有重排规则只对宏观文档做了处理，
对案例文档没有"仅在问企业案例时才召回"的约束。这也是 Task 4.1 本轮要补的规则。

### 2.2 企业案例召回的结构性问题

- 新入库 17 条案例中，**13 条为 B+（媒体转述）**，仅 3 条达到 S（公司公告/投资者互动平台）。
- `RELOC_001`（比亚迪泰国）、`RELOC_002`（长安泰国）为整车厂，电池链（`RELOC_003`–`008`）以国轩/亿纬/欣旺达/蜂巢/华友/中伟为主。
- **缺 EU 电池法规合规案例、印度进入案例、二线厂商/劳工/物流（Operational Risk）案例**；EU 相关 Market Access 问题仍只能靠政策文件回答。

### 2.3 二线来源与企业案例排序偏低（Policy documents ranked low — 部分成立）

| authority | 条数 | 平均排名 | 进 Top-3 |
|---|---|---|---|
| S | 66 | 2.70 | 74% |
| A+ | 22 | 2.14 | 82% |
| A | 10 | 5.00 | 20% |
| B+ | 21 | 4.05 | 48% |

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
| Precision@5 | 65% | **92.0%** | ≥ 80% |
| Recall@10 | 70% | **89.3%** | ≥ 80% |
| Entity Accuracy | 85% | **88.5%** | ≥ 95% |

**说明**：实测 baseline 高于任务书的假设值；且 Entity Accuracy ≥ 0.95 在本语料上不可达
（gold 中包含大量不出现问题实体的宏观文档，检索越准该指标反而越低，见 `task4/baseline_vs_improved.md` §6）。

---

## 5. 方法说明与口径

**Precision@5** = Top-5 中 relevance ≥ 1 的条数 ÷ 5，按题平均。
relevance 判定：2 = 在该题 `expected_evidence_ids` 内；1 = 不在 gold 内，但 topic 属于该题 topic 桶。

**Recall@10** = Top-10 中召回的 gold 证据数 ÷ 该题 gold 总数，按题平均。

**Entity Accuracy** = (Entity Recall + Entity Precision) ÷ 2，只对**问题文本中出现实体**的 24 题计算；
无实体问题不计入。

**已知口径局限**
1. 目标实体只从问题文本提取，**不使用 gold 证据**，避免循环论证。
2. 通用实体（China / United States / tariff）在多数文档中都出现，会**抬高** Entity Precision。
3. 实体识别基于规则词典，未用 NER 模型。
4. 本题集 Entity Recall 恒为 1.000：语料实体高度共现，召回端已饱和；
   Entity Accuracy 的区分度全部来自 Entity Precision（0.771）。
5. `retrieval_results.xlsx` 中的 relevance / authority 为自动判定；人工评分见 Task 2 的 `Task2_manual_scoring_v3.xlsx`。

---

## 6. 最弱的题（优先优化对象）

| question_id | 场景 | P@5 | R@10 | Entity Acc |
|---|---|---|---|---|
| Q003 | Company Intelligence | 1 | 0.333 | 0.9 |
| Q012 | Policy / Trade Risk | 0.6 | 0.5 | n/a |
| Q030 | Scenario Simulation Support | 1 | 0.571 | 0.95 |
| Q029 | Scenario Simulation Support | 0.6 | 0.6 | n/a |
| Q010 | Policy / Trade Risk | 1 | 0.6 | 0.9 |
| Q022 | Market Access | 0.8 | 0.75 | 0.9 |
| Q026 | Scenario Simulation Support | 0.8 | 0.8 | 0.9 |
| Q018 | Supply Chain Risk | 1 | 0.8 | 0.8 |

---

## 7. 交付物

| 文件 | 内容 |
|---|---|
| `retrieval_questions.xlsx` | 30 个测试问题（同 Task 2） |
| `retrieval_results.xlsx` | `Summary` 指标看板 / `retrieval_results` 300 行（30 题 × Top-10）/ `question_summary` |
| `entity_accuracy.xlsx` | `Entity Accuracy` 逐题 / `Entity Detail` 逐实体 / `Summary` |
| `baseline_report.md` | 本文件 |
