PRD

1. Product Overview
   1.1 Background
    我们从reuters报告和McKinsey报告中了解到，许多实行china+1战略布局的企业在此前由于关税和政治风险，尤其是美国对华贸易政策升级后，将供应链生产端转向印度、越南、泰国等东南亚地区。
    目的：
    避免美国对中国商品征收高额关税；
    降低中美贸易摩擦风险；
    建立“China + 1”供应链。
    然而很多企业逐渐意识到，离开中国没有那么容易。中国制造优势并不只是低成本，而是一整套成熟生态，包括：完整供应商网络；熟练产业工人；高效物流；稳定能源供应；大规模生产经验等等。离开中国仅降低关税，却不一定降低生产成本。
    由此，部分企业部分企业开始重新评估此前的供应链迁移决策，并根据成本、供应链韧性、政策环境等因素调整生产布局。，例如Dawang Metals、Target、Shein。而更多企业面临评估回华风险、需要进行供应链布局调整，但信息分散，分析成本高。

   1.2 Product Vision
   一个帮助制造企业在地缘政治不确定环境下进行供应链迁移和布局决策的 AI 咨询助手。
   1.3 Goals
   帮助企业
   ·提供企业自身信息分析
   ·了解当前地缘风险
   ·评估不同生产布局方案（维持东南亚、回迁中国、混合布局）的成本、风险和韧性，并生成可解释的战略建议。
   ·提供相似案例支持
   ·生成PDF报告


2. User Analysis
   2.1 Target Users
   idustries
      Battery / EV Supply Chain
    These industries are selected because they have significant global supply chain exposure, strong China+1 trends, and abundant public data availability.
   Primary User:
     供应链/战略经理
     企业：
     制造业公司
     跨国公司
     考虑重新布局的企业
    Secondary User:
     咨询分析人员
     投资分析人员

   2.2 User Persona
  
| ------------ | -------- |
| Name         | / |
| Role         |  Global Supply Chain Manager    |
| Company Type | Medium-to-large manufacturing company with overseas operations     |
| Background   | 负责公司的全球生产布局和供应链战略。由于关税变化、地缘政治不稳定等原因，公司正在重新评估是否继续扩大海外生产，还是调整生产布局。      |
| Goals        | Understand geopolitical risks affecting supply chain
Compare different relocation strategies
Make evidence-based decisions for management       |
| Pain Points  | 信息碎片化，需要同时查看政府报告、 贸易数据 、新闻等等，高度分散；决策受多种因素影响，困难；咨询报告大多为静态，缺乏真实情景推演    |
| Needs        |   需要一个工具：自动收集相关信息、总结风险、比较不同方案、提供决策支持     |

   2.3 User Scenario
   一家新能源电池企业目前在中国拥有部分生产能力，越南拥有主要海外工厂，产品主要出口美国。近年来由于关税变化、地缘政治不稳定等原因，公司管理层要求供应链部门重新评估生产布局。CEO提出问题：“如果未来美国进一步提高相关产品贸易限制，我们是否应该增加中国生产比例，或者转向其他国家？”
   Alex作为供应链/战略经理通常需要收集政策信息、阅读大量行业报告、咨询专家、制作分析报告。耗时长，信息更新慢。

   Using Our Product
step 1
Alex输入：
Company name
Industry
Current production locations
Target markets
Decision question
......
Step 2
AI自动：
构建Company Profile
检索企业相关资料
收集政策、贸易、新闻证据
Step 3
AI输出：
Initial Assessment:
包括：
current supply chain summary
key risks
relevent cases
possible scenarios
例如：
Scenario A:
Maintain Vietnam production
Scenario B:
Increase China production
Scenario C:
Diversify to other countries
Step 4
Alex继续和AI对话：
补充：
supplier dependency
cost constraints
investment limitation
AI更新分析。
Step 5
最终：
生成：
Executive Decision Report PDF
供管理层讨论。

最终，Alex可以减少调查时间、理解风险、比较选择、形成有逻辑的战略决策。产品功能可以合理嵌入工作流程。

3. Problem Definition
痛点1:Fragmented information。政策、新闻、贸易数据分散。企业需要大量人工研究。
痛点2:Complex trade-off analysis。没有单一最优答案。需要综合成本、风险大量因素进行复杂决策。
痛点3:Lack of scenario simulation。传统报告无法动态回答。

4. Product Solution
    User Journey
    Input Company Information
        ↓
Build Company Profile
        ↓
Collect Evidence & Analyze Risks
        ↓
Generate Initial Assessment & Scenarios
        ↓
Interactive AI Consultation & Refinement
        ↓
Generate Final Decision Report
   

5. Functional Requirements
   5.1 Company Profile Generation
   Purpose
建立企业基础画像，为后续分析提供context。
User Input
初始描述：一句话描述 + 基础信息。（需要提示词,提醒用户输入产业、生产链、销售地、痛点）
e.g.我们是一家新能源汽车电池企业，目前70%的生产在越南，主要出口美国。由于美国政策变化以及越南供应链不足，我们考虑是否扩大中国生产比例。

用户输入表单（示例）：
Required Information

Company
Industry
Production location
Market
Decision question


Optional Information

Capacity
Documents
Supplier information

AI Output
Company Profile:
business overview
supply chain footprint
market exposure
Priority:
P0
   5.2 Evidence-based Research
   Purpose
收集可靠信息。
Input:
Company Profile
Sources:
uploaded documents
reports
news
trade data
Output:
Evidence Database
包含：
source
date
authority level
relevance
Priority:
P0
   
   5.3 Evidence system
   Purpose
建立统一的证据管理与可信度机制，为风险分析、情景推演和最终建议提供可追溯的事实依据。
Function
系统对 Research 阶段获取的信息进行整理、筛选与分级，并根据来源权威性、时效性和与企业场景的相关性评估证据可信度。关键分析结论均关联对应证据，同时标注信息存在的不确定性。
Output
结构化 Evidence Library，包括：
Evidence content
Source
Publication date
Authority level
Relevance
Related conclusion
   5.4 Risk Assessment
   Purpose
基于企业画像和已验证的证据信息，识别与当前供应链布局及决策相关的主要风险。
Function
Agent 从贸易、政策、地缘政治、供应链依赖、市场准入等维度分析信息，并判断这些风险对该企业当前业务和供应链布局的具体影响。
Output
形成企业专属的 Risk Assessment，包括：
Major risks
Risk severity
Potential business impact
Supporting evidence
Key uncertainties
   5.5 Scenario Simulation
   Purpose
模拟不同供应链布局方案下可能产生的影响，帮助用户比较不同决策路径及其权衡关系。
Function
根据企业当前情况、识别出的风险以及用户设定的决策约束，生成若干可行 Scenario，并从成本、供应链韧性、地缘政治风险、市场准入和实施难度等维度进行比较。
典型 Scenario 包括：
Maintain current layout
Increase production in China
Relocate production
Adopt a hybrid strategy
Output
Scenario Comparison，展示各方案的：
Potential benefits
Potential risks
Key trade-offs
Applicable conditions
并形成基于当前信息的 preliminary assessment。
   5.6 AI Consultation
   Purpose
通过与用户的持续对话补充关键信息、澄清决策偏好，并在新的信息和条件下不断完善分析。
Function
用户可以在初步分析后继续提供：
Additional information
Business constraints
New concerns
Decision preferences
LLM 根据对话内容重新审视已有分析，必要时调用 Research / Analysis 能力获取或验证新的信息，并动态更新 Scenario 与 assessment。
Output
经过多轮互动后形成更加完整的：
Updated risk assessment
Refined scenario comparison
Decision considerations
Final decision
The system supports human decision-making rather than replacing human judgment.
   5.7 Report Generation
   Purpose
将完整的咨询过程和最终决策结果整理为可直接用于企业内部沟通与决策的正式报告。
Function
在用户完成决策后，系统整合企业信息、研究证据、风险分析、Scenario 比较以及对话中形成的最终判断，生成结构化报告。
Output
PDF Decision Report，包括：
Executive Summary
Company Profile
Current Supply Chain Situation
Risk Assessment
Scenario Comparison
Final Decision / Recommendation
Evidence Sources
Uncertainties & Limitations

6. AI System Workflow
User Input
                    |
                    ↓
          Decision Understanding
                    |
                    ↓
          Company Profile Builder
                    |
                    ↓
        Knowledge Acquisition Layer
     ┌──────────┼───────────┐
     ↓          ↓           ↓
 Documents   Web Search   Data Sources
                    |
                    ↓
            Evidence Database
                    |
                    ↓
          Risk Analysis Module
                    |
                    ↓
        Scenario Simulation Module
                    |
                    ↓
          AI Consultant Chat Loop
                    |
                    ↓
           Final Decision Report
                    |
                    ↓
                  PDF

7. Output Design
1、Initial Assessment Report
包括：
Company Overview
Current Situation
Key Risks
Scenario Comparison
Preliminary Recommendation
Evidence
Uncertainty

Final Decision Report
PDF：
结构：
Executive Summary
Company Profile
Risk Assessment
Scenario Comparison
Recommendation
Evidence

8. Non-functional Requirements
1、Accuracy
重要结论必须附来源。
2、Explainability。展示：evidence和uncertainty

9. Evaluation Plan
# Locus Evaluation Plan v1.0

## 1. Evaluation Objective

Locus 的 Evaluation 不以“模型是否给出了历史案例中当时企业最终选择的答案”为唯一标准。

产品目标是评估：

> Locus 是否能够基于真实企业信息、可靠外部证据和用户约束，对 EV / Battery Supply Chain Relocation & Diversification Decision 提供可追溯、合理、符合约束、能够解释不确定性的决策支持。

因此 Evaluation 重点评估六种能力：

1. Evidence Retrieval：能否找到正确且相关的证据；
2. Factuality & Citation：公司事实和分析结论是否有依据；
3. Risk Assessment：能否识别与该公司的决策真正相关的关键风险；
4. Scenario Analysis：能否基于证据和用户 priorities 进行有依据的情景比较；
5. Consultation：用户补充信息后，系统能否正确更新 decision state；
6. Final Report：最终报告是否忠实于前面的分析，并保持证据可追溯。

---

# 2. Evaluation Principle

### Principle 1 — Evidence First

任何重要的事实、风险判断、scenario 判断和 recommendation 都必须：

* 有 supporting evidence；或
* 明确标记为 inference；或
* 明确标记为 insufficient evidence / to be confirmed。

禁止通过“看起来合理”代替证据。

### Principle 2 — Historical Outcome Is Not the Gold Answer

历史案例中的真实企业最终选择只作为参考。

例如：

某企业历史上最终选择“撤出中国”。

Locus 不会因为回答：

> “Hybrid diversification may be preferable under these constraints”

就被判错。

真正判断的是：

* 是否识别了关键事实；
* 是否识别了主要风险；
* 是否理解了企业当时的约束；
* 是否覆盖了主要 trade-offs；
* 是否有证据支持；
* 是否存在明显事实错误。

### Principle 3 — No AI Evaluating AI as the Sole Judge

LLM-as-Judge 可以辅助，但不能作为唯一 Evaluation。

最终核心指标采用：

> Human Rubric + Evidence Verification + Automated Validation

LLM-as-Judge 只作为辅助分析工具。

### Principle 4 — Separate Development and Test

任何用于优化 Retrieval / Prompt / Agent 的案例，不得直接作为最终 Benchmark。

最终测试集必须在开发阶段冻结，并且在正式测试前不得用于：

* RAG ingestion；
* retrieval tuning；
* prompt tuning；
* hard-coded rules；
* case-specific prompt engineering。

---

# 3. Evaluation Dataset

## 3.1 Historical Case Benchmark

以现有 `CASE_001–CASE_010` 为第一版基础。

建议最终形成：

> 10–14 个真实企业历史案例

优先覆盖：

* China → Southeast Asia；
* China +1；
* Southeast Asia → China / partial return；
* diversification；
* new manufacturing site；
* tariff / trade-policy driven decisions；
* geopolitical-risk driven decisions。

每个 Case 至少记录：

| Field               | 内容                                   |
| ------------------- | ------------------------------------ |
| case_id             | CASE-xxx                             |
| company             | 企业名称                                 |
| industry            | EV / Battery / related manufacturing |
| original_footprint  | 原生产布局                                |
| decision_trigger    | 为什么需要做决策                             |
| target_market       | 主要市场                                 |
| key_constraints     | 预算、资产、时间、监管等                         |
| major_known_risks   | 历史上可识别的主要风险                          |
| historical_decision | 企业实际采取的行动                            |
| outcome             | 后续结果                                 |
| evidence_ids        | 支撑案例事实的来源                            |

### Dataset Split

第一版建议：

* **Development Set：7–9 cases**
* **Held-out Test Set：3–5 cases**

如果能增加到 12–14 个案例：

* Development：8–9
* Held-out：4–5

Held-out Test Set 在最终测试前冻结。

---

# 4. Retrieval Evaluation Set

Historical cases 之外，建立独立的 Retrieval Questions。

目标不是测试“最终答案对不对”，而是测试：

> 系统能否找到回答这个问题真正需要的证据。

建议第一版：

> 30–50 个 retrieval questions

每个问题人工标注：

* Required Evidence；
* Acceptable Evidence；
* Irrelevant Evidence；
* Source Authority；
* Topic；
* Country / jurisdiction；
* Freshness requirement。

### Question Categories

至少覆盖：

1. Company Facts
2. Tariff / Trade
3. Rules of Origin
4. Export Controls
5. Investment / FDI Policy
6. Supply Chain Dependency
7. Logistics / Infrastructure
8. EV / Battery Industry Policy
9. Historical Cases

---

# 5. Evaluation Pipeline

最终统一采用以下流程：

```text
             ┌─────────────────┐
             │ Evaluation Cases │
             └────────┬────────┘
                      ↓
            ┌──────────────────┐
            │ Frozen Benchmark │
            └────────┬─────────┘
                     ↓
             Run Locus System
                     ↓
      ┌──────────────┼───────────────┐
      ↓              ↓               ↓
 Retrieval       Analysis        UX / State
 Evaluation      Evaluation       Evaluation
      ↓              ↓               ↓
 Evidence        Risk / Scenario   Consultation
 Quality         / Recommendation  / Report
      └──────────────┼───────────────┘
                     ↓
              Human Evaluation
                     ↓
              Error Analysis
                     ↓
            Final Metrics / Report
```

---

# 6. Layer 1 — Retrieval Evaluation

## 6.1 Main Metrics

### A. Precision@5

Top 5 retrieved evidence 中，有多少是真正相关的。

目标：

> **≥ 80%**

### B. Recall@10

需要的关键 evidence 中，有多少能够被 Top 10 找到。

目标：

> **≥ 80%**

### C. Top-1 Critical Mismatch Rate

Top-1 出现明显行业错误 / 公司错误 / 国家错误的比例。

例如：

CATL + Battery query

却返回：

Solar PV circumvention ruling。

目标：

> **≤ 10%**

理想：

> **≤ 5%**

### D. Company Entity Accuracy

当检索用于 Company Intelligence 时：

> 用于支持公司事实的 evidence 必须属于正确企业。

目标：

> **100%**

因为公司实体搞错属于 critical error。

---

# 7. Layer 2 — Evidence & Factuality Evaluation

这是 Locus 最重要的 Evaluation 层之一。

## 7.1 Citation Correctness

随机抽取系统输出中的重要 factual claims。

人工检查：

> citation 是否真的支持该 claim？

目标：

> **≥ 90%**

## 7.2 Unsupported Material Claim Rate

重要事实没有 evidence，也没有标记 inference。

目标：

> **≤ 5%**

重大 hallucination：

> **0**

## 7.3 Fact Status Accuracy

检查系统是否正确区分：

* user_input
* public_source
* inferred
* to_be_confirmed

目标：

> **≥ 90%**

特别要求：

不能把：

> “AI 根据已有事实推测”

写成：

> “公开资料已经证明”。

---

# 8. Layer 3 — Risk Assessment Evaluation

历史案例不直接提供唯一“正确风险列表”。

因此采用：

> Expert Checklist Coverage

每个 Case 预先制作：

> Major Risk Checklist

例如：

* tariff exposure；
* rules-of-origin exposure；
* export-control exposure；
* supplier dependency；
* market-access risk；
* implementation risk。

不是要求 Locus 必须生成完全相同的文字，而是检查是否覆盖主要机制。

## 8.1 Major Risk Coverage

目标：

> **≥ 80%**

## 8.2 Unsupported High/Critical Risk

没有充分 evidence 却被判为：

> High / Critical

目标：

> **0**

## 8.3 Evidence Relevance

Risk 引用的 evidence 是否真的支持该 risk。

目标：

> **≥ 90%**

## 8.4 Uncertainty Disclosure

当证据不足、公司信息缺失或政策尚未确定时，系统是否明确说明不确定性。

目标：

> **≥ 90%**

---

# 9. Layer 4 — Scenario Simulation Evaluation

Scenario 不评价“是否选中了历史答案”。

重点评价：

> 推导是否合理。

## 9.1 Constraint Adherence

Scenario 是否真正考虑了：

* budget；
* timeline；
* non-transferable assets；
* target markets；
* compliance constraints；
* user priorities。

目标：

> **≥ 90%**

## 9.2 Evidence-supported Rationale

每一个 scenario dimension：

* 有 evidence；或
* 明确标记 inference。

目标：

> **≥ 90%**

## 9.3 Score Calculation Correctness

LLM 只负责：

> band + rationale + evidence

Backend 负责：

> band → numeric score → weighted score

因此：

> 后端 score calculation

目标：

> **100%**

这是自动化测试，不依赖人工判断。

## 9.4 Trade-off Coverage

是否同时讨论：

* cost；
* resilience；
* geopolitical exposure；
* market access；
* implementation feasibility。

目标：

> **≥ 80%**

---

# 10. Layer 5 — Recommendation Evaluation

Recommendation 不评价“是不是历史企业最后做的那个选择”。

评价：

### A. Evidence Support

Recommendation 是否能够追溯到：

> Scenario + Risk + Evidence。

目标：

> **≥ 90%**

### B. Constraint Consistency

Recommendation 是否违反用户明确约束。

目标：

> **100%**

例如：

用户预算只有 10M USD，

系统却直接建议建设一个超出用户预算的完整新工厂，

属于 critical error。

### C. Uncertainty / Conditionality

Recommendation 是否说明：

> 什么情况下这个判断成立；
> 什么信息变化后结论可能改变。

目标：

> **≥ 80%**

---

# 11. Layer 6 — Consultation Evaluation

这一层测试：

> AI 是否真的能“连续咨询”，而不是每次重新回答。

设计一个 3–5 turn benchmark。

例如：

### Turn 1

User：

> 我们计划在 Vietnam 保留 40% production。

### Turn 2

User：

> 但我们的主要客户在美国。

### Turn 3

User：

> 预算只能增加 10%。

### Turn 4

User：

> 我们还有两个核心资产不能搬。

测试系统是否正确：

1. 记住前面的信息；
2. 更新 constraints；
3. 判断哪些风险受到影响；
4. 触发 scenario update；
5. scenario change 是否符合新增信息。

### Consultation Metrics

Memory Accuracy：

> **≥ 90%**

New Information Classification：

> **≥ 90%**

Scenario Update Trigger Accuracy：

> **≥ 90%**

---

# 12. Layer 7 — Final Report Evaluation

报告不是新的分析入口。

必须是：

> Assessment → Report

而不是重新进行一遍 research。

## 12.1 Citation Validity

报告所有 Evidence ID：

> 必须真实存在。

目标：

> **100%**

## 12.2 Fact Consistency

报告中的事实不得与 Assessment 冲突。

目标：

> **≥ 95%**

## 12.3 Unsupported New Fact Rate

报告不得凭空产生新的重要事实。

目标：

> **0 critical unsupported facts**

## 12.4 Structure Completeness

至少包含：

1. Executive Summary
2. Company Profile
3. Current Supply Chain Situation
4. Key Risks
5. Scenario Comparison
6. Recommendation / Decision Considerations
7. Evidence
8. Uncertainties and Information Gaps

目标：

> **100%**

---

# 13. Human Evaluation Rubric

核心人工评价不使用复杂数学，而使用：

> 0 / 1 / 2

### 0 — Incorrect

明显错误、无关、没有依据或违反约束。

### 1 — Partially Correct

方向基本合理，但存在遗漏、证据不足或解释不完整。

### 2 — Strong

事实正确、证据充分、逻辑合理，并且与用户约束一致。

人工评估对象：

* Company Intelligence；
* Risk Assessment；
* Scenario Analysis；
* Recommendation；
* Consultation update。

建议：

> 至少 2 名人工 evaluator

条件允许时加入第 3 名 evaluator。

Evaluator 在评分时：

> 不知道这是哪个版本的模型 / prompt。

---

# 14. Evaluation Gates

最终不建议只看一个 Overall Score。

设置必须通过的硬门槛。

## Gate 1 — Factuality

* Critical hallucination = 0
* Company entity accuracy = 100%
* Citation validity ≥ 90%

## Gate 2 — Evidence

* Retrieval Precision@5 ≥ 80%
* Retrieval Recall@10 ≥ 80%
* Top-1 critical mismatch ≤ 10%

## Gate 3 — Risk

* Major risk coverage ≥ 80%
* Unsupported High/Critical risk = 0

## Gate 4 — Scenario

* Constraint adherence ≥ 90%
* Evidence-supported rationale ≥ 90%
* Backend scoring correctness = 100%

## Gate 5 — Consultation

* Memory accuracy ≥ 90%
* Correct state update ≥ 90%

## Gate 6 — Report

* Citation validity = 100%
* No critical unsupported new fact

**任何 Critical Error 都可以使该 Case 判定为 Fail，即使其他分数很高。**

---

# 15. Overall Evaluation Score

为了比赛展示，可以额外计算一个内部 Overall Score。

注意：

> Overall Score 只用于展示产品 Evaluation 结果，不替代上述硬门槛。

建议：

| Dimension             |   Weight |
| --------------------- | -------: |
| Retrieval & Evidence  |      20% |
| Factuality & Citation |      20% |
| Risk Assessment       |      15% |
| Scenario Analysis     |      20% |
| Recommendation        |      10% |
| Consultation          |      10% |
| Report / UX           |       5% |
| **Total**             | **100%** |

评分结果可以表示为：

> Overall Evaluation Score: XX / 100

但最终报告中必须同时展示：

> Critical Error Rate
> Evidence Accuracy
> Risk Coverage
> Scenario Constraint Adherence

避免“总分很高，但存在严重 hallucination”的情况。

---

