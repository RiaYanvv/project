
# A 当前阶段任务：RAG + Evidence System + Evaluation Pipeline 建设

## Overall Goal（总体目标）

目前 Locus 已经具备基础 Agent workflow，但当前主要问题是：

* Agent 输出依赖用户输入，缺少可靠外部知识支持；
* RAG 检索结果质量不稳定；
* Evidence 没有统一结构，无法追踪来源；
* 缺少系统化 evaluation 方法判断 AI 输出质量。

因此当前阶段目标：

> 建立一个可追踪、可评估、可优化的 Evidence-based RAG System，使 Agent 的 Company Profile、Risk Assessment 和 Scenario Simulation 都基于可靠证据生成。

最终希望达到：

用户输入：

> “CATL 是否应该增加中国生产比例？”

Agent能够：

1. 找到 CATL 企业信息；
2. 找到 EV Battery 行业政策和贸易风险；
3. 找到类似企业案例；
4. 输出风险和scenario；
5. 每条关键结论都有 evidence 支撑。

---

# Task 1 — 完善 Evidence Database Schema（优先级 P0）

## 什么是 Evidence Database？

Evidence Database 是 Agent 的知识来源。

目前 Excel 只是：

```
ID
Title
Source
Date
Summary
```

需要升级为结构化数据，让 Agent 理解：

* 这是什么信息；
* 来自哪里；
* 可信度如何；
* 与什么问题相关。

---

## 要完成：

统一所有数据字段。

建议 schema：

### Basic Information

| Field            | Example                        |
| ---------------- | ------------------------------ |
| evidence_id      | BIS_001                        |
| title            | Expansion of End-User Controls |
| source           | BIS                            |
| url              | xxx                            |
| publication_date | 2025-09-30                     |

---

### Classification

增加：

| Field         | Example        |
| ------------- | -------------- |
| country       | USA            |
| industry      | EV_Battery     |
| topic         | export_control |
| evidence_type | Policy         |
| related_risk  | market_access  |

topic 示例：

```
tariff
export_control
trade_policy
investment_policy
supply_chain
labor
logistics
market_access
regulation
```

industry：

```
EV_Battery
Semiconductor
Electronics
Solar
General_Manufacturing
```

evidence_type：

```
Government Policy
Company Report
Industry Report
News
Trade Data
Case Study
Academic Research
```

---

### Reliability / Authority

增加：

```
authority_level
```

分级：

S：

* Government documents
* Official company filing
* WTO / UN documents

A：

* McKinsey
* IMF
* World Bank
* CSIS

B：

* Industry research

C：

* News / secondary articles

---

### Example:

最终一条数据：

```json
{
"id":"BIS_001",
"title":"Expansion of End User Controls",
"source":"BIS",
"country":"USA",
"industry":"EV_Battery",
"topic":"export_control",
"type":"Policy",
"authority":"S",
"risk":"market_access"
}
```

---

# Task 2 — 建立 Retrieval Evaluation Dataset（优先级 P0）

## 什么是 Retrieval Evaluation？

Retrieval = RAG 从数据库找到相关资料。

测试：

> Agent 找资料的能力是否正确。

不是测试最终回答。

例如：

用户：

> What are CATL overseas factories?

正确检索：

✅ CATL annual report
✅ Hungary factory announcement
✅ Indonesia project

错误：

❌ BYD factory news
❌ Solar industry report

---

## 要完成：

建立：

```
data/evaluation/retrieval_questions.xlsx
```

至少：

## 30个测试问题

分类：

| Category            | Number |
| ------------------- | ------ |
| Company Information | 5      |
| EV Battery Industry | 5      |
| Trade/Tariff Policy | 5      |
| Export Control      | 5      |
| Supply Chain        | 5      |
| Historical Cases    | 5      |

---

## 每个问题格式：

| Field                | Example                           |
| -------------------- | --------------------------------- |
| Question             | What are CATL overseas factories? |
| Category             | Company                           |
| Expected Evidence ID | CASE_CATL_001                     |
| Acceptable Source    | CATL Annual Report                |
| Difficulty           | Medium                            |

---

Example:

Question:

```
What policies affect Chinese EV battery exports to US?
```

Expected evidence:

```
BIS_001
IRA_001
US tariff policy report
```

---

# Task 3 — Retrieval Baseline Evaluation（优先级 P0）

建立测试后，需要先测试当前 RAG。

不要直接修改。

记录当前效果。

## Metrics：

---

## 1. Precision@5

含义：

Top 5检索结果中，有多少真正相关。

Example：

返回：

```
1 CATL Annual Report ✅
2 CATL Hungary Project ✅
3 BYD Expansion ❌
4 Solar Report ❌
5 EV Market Report △
```

Precision:

约：

3/5 = 60%

目标：

> Precision@5 ≥ 80%

---

## 2. Recall@10

含义：

需要的信息，有多少被找到。

Example：

问题需要：

```
CATL Hungary
CATL Indonesia
US battery policy
```

RAG找到：

2/3

Recall:

66%

目标：

> Recall@10 ≥ 80%

---

## 3. Entity Accuracy

测试：

搜索 CATL 是否主要返回 CATL。

目标：

> ≥95%

避免：

输入 CATL

返回：

BYD/Tesla/其他企业。

---

# Task 4 — 优化 Retrieval Pipeline（优先级 P1）

根据 Task 3 结果优化。

重点：

---

## 4.1 Metadata Filtering

让系统根据：

industry

country

topic

过滤。

Example:

用户：

```
EV battery supply chain risk
```

优先：

```
industry=EV_Battery
topic=supply_chain
```

而不是：

```
Semiconductor
Solar
```

---

## 4.2 Query Enhancement

用户输入：

```
CATL risk
```

扩展：

```
CATL
+
EV battery
+
US market
+
tariff
+
export control
+
supply chain
```

提高检索准确率。

---

## 4.3 Authority Ranking

检索结果排序：

S级来源优先。

例如：

BIS regulation

应该高于：

普通新闻。

---

# Task 5 — Historical Case Benchmark（优先级 P0）

## 为什么需要？

Retrieval Evaluation 测：

> 找资料能力。

Historical Case Benchmark 测：

> 整个产品解决真实商业问题的能力。

这是最终 End-to-End Evaluation。

---

## 要完成：

建立：

```
data/evaluation/historical_case_benchmark.xlsx
```

至少：

10个真实案例。

推荐：

* CATL overseas expansion
* Tesla China supply chain
* Apple China+1
* Foxconn India expansion
* Samsung Vietnam manufacturing
* Shein supply chain adjustment
* Nike Vietnam production
* Dawang Metals return to China

---

## 每个案例格式：

| Field             | Example                     |
| ----------------- | --------------------------- |
| Case ID           | CASE_001                    |
| Company           | CATL                        |
| Industry          | EV Battery                  |
| Initial Situation | China + overseas production |
| Decision Problem  | Whether expand overseas     |
| Evidence Sources  | links                       |
| Actual Decision   | Built Hungary factory       |
| Outcome           | Improved EU market access   |
| Key Factors       | regulation, market          |

---

# Task 6 — Risk Assessment Evaluation Dataset（优先级 P1）

测试：

Agent 是否识别关键风险。

建立：

```
risk_assessment_checklist.xlsx
```

Example:

Case:

CATL entering US market

Expected risks:

| Risk                    | Expected |
| ----------------------- | -------- |
| Tariff risk             | YES      |
| Export control          | YES      |
| Supply chain dependency | YES      |
| Labor cost              | Optional |

评价：

* Correct identification
* Missing risks
* False positives

---

# Task 7 — Evidence Citation Evaluation（优先级 P1）

测试：

Agent引用是否可靠。

要求：

每个关键结论：

必须关联：

```
Evidence ID
Source
Date
Authority
```

Example:

Risk:

> US market access risk exists.

Evidence:

```
BIS_001
Source:
BIS

Authority:
S

Date:
2025
```

---

# 最终 Git 文件结构

建议：

```
data/

├── raw/
│
├── processed/
│
├── vector_database/
│
└── evaluation/

    ├── retrieval_questions.xlsx

    ├── retrieval_results.xlsx

    ├── historical_case_benchmark.xlsx

    ├── benchmark_results.xlsx

    ├── risk_assessment_checklist.xlsx

    ├── evidence_quality_test.xlsx

    └── evaluation_report.md
```

---

# 本阶段最终交付标准

完成后：

## Evidence System

✅ 所有数据有统一schema
✅ 有authority等级
✅ 可以追踪source

## Retrieval

✅ 30个evaluation questions
✅ Precision@5 ≥80%
✅ Recall@10 ≥80%
✅ Entity Accuracy ≥95%

## Historical Benchmark

✅ 至少10个真实案例
✅ 有标准答案和评价标准

## Evaluation Report

输出：

```
Before optimization:

Precision@5:
XX%

After optimization:

Precision@5:
XX%

Changes:
1. Added metadata
2. Improved chunking
3. Added ranking
```

---

# 最重要原则

当前不要优先扩大数据量。

优先顺序：

```
数据结构化
    ↓
检索可测试
    ↓
检索优化
    ↓
案例benchmark
    ↓
Agent能力提升
```

目标不是建立最大的知识库，而是建立一个**能够支撑AI供应链决策的可信知识系统**。


