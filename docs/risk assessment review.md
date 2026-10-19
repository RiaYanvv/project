# Risk Assessment Agent Revision & Scoring Specification

## 0. 本次改动目标

当前 Risk Assessment 已经能够生成较有针对性的企业风险，但仍存在以下问题：

* 风险数量偏多，存在重复；
* `INFORMATION_QUALITY` 被当作业务风险；
* 部分企业级结论超过现有证据能够支持的范围；
* 无证据风险仍可能被标为 HIGH；
* Risk Level 的 HIGH / MEDIUM / LOW 缺乏明确计算逻辑；
* 当前风险判断没有系统地区分：

  * 风险发生可能性；
  * 风险发生后的业务影响；
  * 该公司对该风险的实际暴露程度；
  * 我们对这个判断的可信程度；
  * 该风险对当前战略决策的重要程度；
* 部分结论存在“上游材料来自中国 → 最终产品属于中国原产”这样的过度推导；
* `Financial` 与既有风险 taxonomy 不一致；
* Risk Assessment 与 Company Intelligence 的联系虽然已经开始建立，但需要进一步强制化。

本次目标：

> 将 Risk Assessment Agent 从“行业风险罗列器”升级为“基于 Company Intelligence + External Evidence 的公司特异性风险分析模块”。

---

# 1. Risk Agent 的职责边界

Risk Agent 的任务不是：

* 总结行业趋势；
* 再次生成 Company Profile；
* 重新识别公司身份；
* 给用户推荐最终战略；
* 比较哪个 Scenario 最好；
* 生成最终报告。

Risk Agent 的唯一核心问题：

> **What risks are materially relevant to THIS company under its current decision context?**

因此 Risk Agent 必须首先读取：

```text
Company Intelligence
+
Current Decision Context
+
Relevant External Evidence
```

而不是只读取：

```text
Company Name
+
Generic EV/Battery Evidence
```

---

# 2. Risk Agent 的输入

Risk Agent 必须把 Company Intelligence 作为必填上下文。

至少包含：

```text
company identity
business profile
value-chain role
manufacturing footprint
supply-chain structure
target markets
decision context
constraints
critical information gaps
```

同时接收：

```text
policy evidence
industry evidence
trade evidence
relevant company evidence
```

---

# 3. Risk Generation 的基本逻辑

每个风险必须建立以下链条：

```text
Company-specific Trigger
        ↓
External Mechanism
        ↓
Business Impact
        ↓
Evidence
        ↓
Risk Assessment
        ↓
Decision Relevance
```

---

# 4. 每个 Risk 必须回答 6 个问题

## 4.1 Company-specific Trigger

回答：

> 为什么这个风险与这家公司有关？

必须引用 Company Intelligence 中的具体事实。

例如：

```text
LGES:
- China production share = 25%
- Korea production share = 25%
- Poland production share = 10%
- US is a target market
```

于是：

> US market access risk is relevant because the company targets the US while its disclosed production footprint does not establish a US production base.

不能只写：

> EV battery companies face tariff risk.

---

## 4.2 External Mechanism

回答：

> 什么外部政策、市场或地缘机制会产生这个风险？

例如：

* tariff policy
* customs enforcement
* rules of origin
* export control
* localization requirement
* supplier disruption
* investment policy

必须有对应 evidence。

---

## 4.3 Business Impact

回答：

> 如果这个风险发生，它具体会影响什么？

只能使用有合理机制支持的业务影响：

* Cost
* Lead time
* Production continuity
* Market access
* Compliance burden
* Capacity expansion
* Customer delivery
* Implementation feasibility

禁止没有证据支持的跳跃性结论。

例如：

可以：

> May increase customs verification and compliance burden.

谨慎：

> May increase landed cost or delay clearance.

不能直接写：

> Will cause customers to terminate contracts.

除非存在 company-specific evidence 支持。

---

## 4.4 Evidence

每一个 Material Risk 必须明确：

```text
supporting_evidence_ids
```

并且 Evidence 必须真正支持风险机制。

禁止：

```text
Risk A
→ 自动挂前两条 evidence
```

如果没有合格 evidence：

```text
insufficient_evidence = true
```

---

## 4.5 Uncertainty

每一个风险必须明确：

> What don't we know?

以及：

> What information would change the assessment?

例如：

```text
Unknown:
- actual US export share
- BOM origin
- supplier concentration
- plant-level capacity

What would change assessment:
- verified US sales share
- plant-level export destination
- BOM sourcing data
```

---

## 4.6 Decision Relevance

回答：

> 这个风险为什么与用户当前的战略决策直接有关？

建议使用：

```text
HIGH
MEDIUM
LOW
```

例如用户正在比较：

> North America expansion vs Asia-centered production

那么：

US market access risk → HIGH decision relevance

某个与当前投资决策没有直接关系的长期宏观趋势 → LOW。

---

# 5. Risk Taxonomy

严格使用以下 6 个一级类别：

```text
TRADE
POLITICAL
SUPPLY_CHAIN
REGULATORY
MARKET_ACCESS
OPERATIONAL
```

不要让 LLM 自由创建新的一级类别。

---

## TRADE

例如：

* tariff exposure
* customs enforcement
* trade restriction
* anti-circumvention exposure

---

## POLITICAL

例如：

* geopolitical tension
* geopolitical fragmentation
* political instability
* policy uncertainty

---

## SUPPLY_CHAIN

例如：

* supplier concentration
* geographic concentration
* raw material dependency
* cross-border dependency
* alternative supplier availability

---

## REGULATORY

例如：

* export control
* local regulation
* compliance requirement
* localization requirement

---

## MARKET_ACCESS

例如：

* tariff-driven market access
* customer/local-content requirement
* subsidy eligibility
* market-specific production requirement

---

## OPERATIONAL

例如：

* labor
* infrastructure
* manufacturing capability
* capacity ramp-up
* implementation difficulty
* capital expenditure / execution risk

---

### Financial

不要作为独立一级类别。

如果是：

* capital expenditure
* cost increase
* financing pressure
* ramp-up cost

归入：

```text
OPERATIONAL
```

---

# 6. `INFORMATION_QUALITY` 必须移出 Risk

`INFORMATION_QUALITY` 不再作为业务风险输出。

例如：

> “公司供应商集中度未知。”

这不是企业本身的 geopolitical / operational risk。

应该进入：

```text
Analysis Confidence
+
Information Gaps
```

或者：

```text
Decision Readiness
```

例如：

> Decision confidence: Low
> Key information gaps: supplier concentration, BOM, plant capacity.

---

# 7. Risk Scoring Framework

Risk Level 不允许由 LLM 直接自由生成。

LLM 负责判断 3 个基础维度：

```text
Likelihood
Impact
Company Exposure
```

每个维度 1–5。

Backend 负责计算最终 Risk Score 和 Risk Level。

---

# 8. Likelihood（发生可能性）

## 1 — Very Low

* 仅存在理论可能；
* 当前没有明确触发条件；
* 没有近期政策/市场信号。

## 2 — Low

* 存在一定可能；
* 有相关历史或政策讨论；
* 但短期触发条件较弱。

## 3 — Medium

* 存在明确风险机制；
* 已有政策/市场信号；
* 但结果存在较大不确定性。

## 4 — High

* 当前已有明确政策/事件/趋势；
* 公司存在明确暴露；
* 风险在当前决策时间窗口内具有现实可能性。

## 5 — Very High

* 已存在明确实施中的政策/事件；
* 触发条件已经或即将发生；
* 公司存在直接且明显的暴露。

---

# 9. Impact（业务影响）

不是简单判断“严重不严重”。

必须具体到业务结果。

## 1 — Minor

只造成：

* 轻微行政成本；
* 小幅流程变化；
* 可轻松吸收。

## 2 — Limited

可能造成：

* 有限成本增加；
* 小幅时间延迟；
* 局部运营调整。

## 3 — Material

可能明显影响：

* 单位成本；
* lead time；
* 某个生产环节；
* 局部市场准入。

## 4 — Significant

可能明显影响：

* 核心生产布局；
* 主要市场供应；
* 重大资本投入；
* 核心客户交付。

## 5 — Critical

可能导致：

* 核心市场无法进入；
* 关键业务中断；
* 重大资产/投资决策失误；
* 重大合规后果。

---

# 10. Company Exposure（企业暴露程度）

这是 Risk Assessment 最重要的企业特异性变量之一。

## 1 — Minimal

公司几乎不受影响。

## 2 — Limited

存在有限暴露，但有较强替代方案。

## 3 — Moderate

企业具有一定直接暴露，但并非高度集中。

## 4 — High

企业对该机制存在明显依赖或集中暴露。

## 5 — Direct / Concentrated

该风险直接作用于公司核心：

* 主要产品；
* 主要市场；
* 核心产能；
* 高度集中的供应链；
* 核心战略资产。

---

# 11. Risk Score 计算

Backend 计算：

```text
Risk Score =
Likelihood × Impact × Company Exposure
```

范围：

```text
1–125
```

---

# 12. Risk Level Threshold

第一版采用：

|  Score | Risk Level |
| -----: | ---------- |
|   1–24 | LOW        |
|  25–59 | MEDIUM     |
| 60–125 | HIGH       |

注意：

这只是 MVP 第一版规则。

完成 Historical Case Benchmark 后，应进行 calibration（校准），检查：

* 是否存在大量重大风险被打成 Low；
* 是否大量普通风险被打成 High。

根据真实案例再调整 threshold。

---

# 13. Evidence Sufficiency Gate

Risk Score 不能单独决定最终 Risk Level。

必须经过 Evidence Gate。

---

## Rule 1 — No Evidence

如果：

```text
没有合格 External Evidence
+
没有相关 Company-specific/User evidence
```

则：

```text
insufficient_evidence = true
```

不能生成 HIGH。

---

## Rule 2 — Industry Evidence Only

如果只有：

> 行业层面证据

但缺少：

> company-specific exposure evidence

最高：

```text
MEDIUM
```

并且：

```text
confidence = LOW
```

Example：

> “EV battery companies may rely on Chinese graphite.”

不能直接变成：

> “LGES has High graphite dependency risk.”

---

## Rule 3 — Company + External Evidence

只有同时存在：

```text
Company-specific evidence
+
Relevant external evidence
```

才能支持 HIGH risk。

Example：

```text
Company fact:
LGES has disclosed production / sourcing exposure

+

External mechanism:
US tariff / customs / localization policy

+

Business impact:
US market access / cost

↓

Potential HIGH Risk
```

---

# 14. Confidence 和 Risk Level 分离

必须明确：

> Risk Level ≠ Confidence

例如：

```text
Risk Level:
HIGH

Confidence:
MEDIUM
```

意思是：

> 如果风险机制成立，对公司影响很大；但是由于公司内部数据不足，我们对暴露程度仍存在不确定性。

---

## Confidence

建议：

### HIGH

* Company-specific facts verified；
* External mechanism verified；
* Evidence directly supports assessment。

### MEDIUM

* Main mechanism有可靠证据；
* Company exposure部分依赖用户输入或有限公开信息。

### LOW

* 主要依赖行业证据；
* Company-specific evidence不足；
* 或存在重要 conflicting / unknown information。

---

# 15. 严格禁止的推理

## 15.1 不允许：

> 某材料来自中国 → 最终产品属于中国原产。

正确：

> 中国来源的材料可能增加原产地判定与供应链追溯复杂度；最终原产地需要根据具体产品、加工过程及适用规则逐案确认。

---

## 15.2 不允许：

> 波兰占LGES 10% → 不足以满足欧洲市场需求。

因为不知道：

* 欧洲需求；
* LGES总产能；
* 波兰实际产能；
* 是否有其他欧洲基地。

应该：

> Current evidence is insufficient to determine whether disclosed Poland capacity is sufficient for European demand.

---

## 15.3 不允许：

> 没有美国基地 → LGES对美国市场高度依赖海外出口。

因为40% production footprint仍然未知。

应该：

> The disclosed production footprint does not establish a US manufacturing base; the remaining 40% is unconfirmed and requires verification.

---

## 15.4 不允许：

> 地缘政治风险 → 客户流失。

如果没有客户/合同证据，只能说：

> Potential impact on customer competitiveness / supply continuity.

---

# 16. Risk Deduplication（重复风险合并）

最终输出：

> **4–5 个核心风险**

不要输出7–10个高度重叠的风险。

---

## 推荐合并逻辑

例如：

### Risk A

US customs enforcement

### Risk B

US origin compliance

如果二者都围绕：

> US market access + origin/customs

合并成：

> **US Market Access, Customs & Origin Exposure**

---

### Risk A

Geopolitical fragmentation

### Risk B

China-related material dependency

如果证据机制不同：

不要强行合并。

但如果只是两种说法描述同一暴露，应合并。

---

# 17. Core Risk Selection

系统可以先生成候选风险，然后经过：

```text
Generate
↓
Deduplicate
↓
Score
↓
Evidence Gate
↓
Decision Relevance
↓
Select top 4–5
```

最终排序原则：

```text
Decision Relevance
+
Risk Score
+
Evidence Confidence
```

不要只按照 Risk Score 排名。

---

# 18. Required Risk Output Schema

建议最终结构：

```json
{
  "risk_id": "RSK-001",
  "title": "US Market Access, Customs & Origin Exposure",
  "category": "MARKET_ACCESS",

  "company_specific_trigger": "...",

  "external_mechanism": "...",

  "business_impact": [
    "market_access",
    "cost",
    "lead_time"
  ],

  "impact_description": "...",

  "likelihood": 4,
  "impact": 5,
  "company_exposure": 4,

  "risk_score": 80,
  "risk_level": "HIGH",

  "decision_relevance": "HIGH",

  "confidence": "MEDIUM",

  "supporting_evidence_ids": [
    "EVD-WH-001",
    "EVD-WH-002"
  ],

  "uncertainty": [
    "Actual US export share is unknown",
    "BOM origin is unverified"
  ],

  "what_would_change_assessment": [
    "Verified plant-level export allocation",
    "Verified BOM origin"
  ],

  "insufficient_evidence": false
}
```

---

# 19. LLM 与 Backend 的职责分工

## LLM负责：

* 识别候选风险；
* 判断 Company-specific trigger；
* 判断 external mechanism；
* 分析 business impact；
* 选择 evidence；
* 判断 likelihood；
* 判断 impact；
* 判断 company exposure；
* 给出 uncertainty；
* 判断 decision relevance。

---

## Backend负责：

* evidence whitelist；
* evidence sufficiency gate；
* score calculation；
* Risk Level mapping；
* High-risk restriction；
* risk deduplication；
* max 4–5 core risks；
* schema validation；
* contradictions / invalid fields validation。

---

# 20. Acceptance Tests

至少运行以下三组案例。

## Case 1 — CATL

检查：

Risk 是否体现：

* China-centered manufacturing；
* overseas expansion；
* US/EU market exposure；
* company-specific supply chain structure。

不能只是：

> Chinese EV battery companies face tariff risk.

---

## Case 2 — LG Energy Solution

至少检查：

* Korea headquarters；
* China production；
* Poland / Europe；
* North America decision context；
* supplier information gaps。

---

## Case 3 — Information-poor Generic EV Battery Company

检查：

如果只有：

```text
EV battery
China 30%
US market
```

没有供应商/BOM/产能数据：

系统必须：

* 明确 unknown；
* 不得猜测；
* 不得产生 unsupported High Risk；
* Confidence 应下降。

---

# 21. 当前 LGES 输出的目标示例

对于目前这个案例：

### Risk 1

**US Market Access, Customs & Origin Exposure**

Likelihood: 4
Impact: 5
Exposure: 4

Score:

```text
4 × 5 × 4 = 80
```

Level:

> HIGH

Confidence:

> MEDIUM

---

### Risk 2

**China-linked Supply Chain / Localization Exposure**

Likelihood: 3
Impact: 4
Exposure: 3

Score:

```text
3 × 4 × 3 = 36
```

Level:

> MEDIUM

Confidence:

> LOW–MEDIUM

因为供应商/BOM未验证。

---

### Risk 3

**Overseas Expansion Execution Risk**

Likelihood: 3
Impact: 4
Exposure: 3

Score:

```text
3 × 4 × 3 = 36
```

Level:

> MEDIUM

但这需要真正相关的 evidence，而不能拿 UNCTAD / WEF 直接证明 LGES 会出现资本开支超支。

---

# 22. Final Product Principle

Risk Assessment 的目标不是：

> 找出最多风险。

而是：

> **识别对当前公司、当前时间窗口、当前战略决策最重要的 4–5 个风险，并让用户能够看到“为什么这个风险适用于我”。**

最终每一个 Risk 都应该形成：

```text
Company
   ↓
Company-specific Trigger
   ↓
External Mechanism
   ↓
Business Impact
   ↓
Evidence
   ↓
Likelihood × Impact × Exposure
   ↓
Risk Level
   ↓
Confidence
   ↓
Decision Relevance
```

这是本次 Risk Assessment Agent 的核心设计。
