## 1. Product Entry Experience
我希望网址点进去先有一个动画效果，类似于“hi，welcome to use locus”打印机式滚动出现，下面小字“AI-Supply-Chain-Relocation-Decision-Agent”。动画大概持续一秒，然后进入正式网页。正式网页home page主要就是功能入口了，click一个button之后展现问题表单，这里我想分为快捷表单和详细表单，适应不同填写需要。默认快捷表单，填完后会有“add more information”的按钮。然后填写信息后接入agent分析，之后网页跳转。对于UI，我希望采取蓝白色调为主，显示专业性和可靠性。
### 1.1 Splash Screen

When users first enter the website, display a minimal branded splash animation.

Content:

**Locus**

*AI Supply Chain Relocation Decision Agent*

The main greeting should appear with a subtle typewriter / terminal-style text animation:

> Hi, welcome to Locus.

Animation duration: approximately 0.8–1.2 seconds.

Design requirements:

* Minimal and professional
* No excessive visual effects
* Smooth transition to the main homepage
* Support reduced-motion preferences

---

## 2. Home Page

The homepage should function primarily as the product entry point rather than a content-heavy dashboard.

### Main Content

**Locus**

**AI Supply Chain Relocation Decision Agent**

Brief description:

> Evaluate supply chain relocation and diversification options under geopolitical uncertainty.

Primary CTA:

**Start Consultation**

The visual hierarchy should immediately communicate:

1. What the product is
2. What problem it solves
3. How to begin

---

## 3. Consultation Mode Selection

After clicking **Start Consultation**, users should choose between two input modes.

### Quick Assessment

For users who want to start with limited information.

Required information:

* Company Name
* Industry
* Product / Main Business
* Current Production Locations
* Target Markets
* Decision Question

Optional:

* Brief natural-language description
* Additional context

### Detailed Assessment

For users who want a more comprehensive analysis.

Includes all Quick Assessment fields, plus:

* Production Share by Location
* Decision Timeline
* Decision Priorities
* Investment Budget / Constraints
* Non-transferable Assets
* Compliance Constraints
* Supplier Information
* File Upload

The two modes should feel like different levels of information depth, not completely separate workflows.

---

## 4. User Submission & Analysis Transition

After the user submits the form, the frontend sends the structured user input to the backend Agent API according to the project's defined schema.

Before displaying the Initial Assessment, show a brief analysis state.

Example:

> Analyzing your supply chain...

Display the actual processing stages as they become available:

* Understanding company profile
* Gathering relevant evidence
* Assessing geopolitical risks
* Simulating strategic scenarios

Do not display artificial progress percentages. The UI should reflect actual backend processing status where possible.

After the analysis is completed, navigate the user to the Initial Assessment interface.

---

## 5. Visual Design

Primary visual direction:

**Blue + White**

Design goals:

* Professional
* Reliable
* Analytical
* Clean
* Enterprise-oriented

Avoid:

* Excessive gradients
* Heavy animations
* Decorative 3D elements
* Gaming-style interactions
* Excessive use of cards or visual effects

Prioritize clear typography, strong information hierarchy, whitespace, and readability.

┌──────────────────────────────────────────────┐
│ Locus          My Decision  Start New Decision  News │
│                                              │
│                                              │
│          AI Supply Chain Relocation          │
│              Decision Agent
                 （简短介绍）                  │
│                                              │
│   Evaluate supply chain strategies under     │
│        geopolitical uncertainty.              │
│                                              │
│          [ Start New Decision ]              │
│                                              │
└──────────────────────────────────────────────┘
## 6. Home Page Navigation

The home page should provide three primary navigation entries in the top-right area:

### 6.1 History

Purpose:
Allow users to access previously created decision projects.

For the MVP, the history function should be implemented in a lightweight way and should not require a complex authentication system.

The underlying concept should be a **Decision Project**, rather than a simple chat history.

Each project may eventually contain:

* Company Profile
* Evidence
* Risk Assessment
* Scenario Analysis
* Conversation
* Final Decision
* Generated Reports

Example display:

> My Decisions
> Vietnam Production Relocation
> Last updated: Sep 22, 2026

For the first implementation, focus on the UI structure and project persistence mechanism. Enterprise-level authentication and multi-user permissions are outside the MVP scope.

---

### 6.2 Start New Decision

This should be the primary CTA and the most visually prominent navigation element.

Behavior:

* Clicking it opens a new decision workflow.
* The default user experience after entering the product should already be the decision workspace / new decision workflow.
* Starting a new decision should create a clean consultation state without modifying or deleting previous decision projects.

Recommended label:

**Start New Decision**

---

### 6.3 News

Purpose:
Provide access to a future geopolitical and supply-chain news monitoring function.

The planned future functionality includes:

* Daily collection of relevant geopolitical and supply-chain news
* Filtering by industry and country
* Relevance ranking
* Matching news to users' decision projects
* Potential future notifications for major policy changes

MVP requirement:

* The News section should be reserved in the information architecture and navigation.
* Real-time crawling, ranking, and notification functionality are NOT required for the MVP.
* The News module must not become a dependency of the core consultation workflow.

---

## 7. Home Page Information Architecture

The homepage should remain visually minimal and primarily serve as the entry point to the core decision workflow.

Recommended hierarchy:

1. Brand: **Locus**
2. Top navigation:

   * History
   * Start New Decision
   * News
3. Product positioning:

   * AI Supply Chain Relocation Decision Agent
4. Short product description
5. Primary CTA:

   * Start New Decision

The visual hierarchy should emphasize the decision workflow rather than news or historical projects.

---

## 8. Product Navigation Principle

The product should be structured around **Decision Projects**, not around isolated chat sessions.

Conceptual structure:

User
↓
Decision Project
├── Company Profile
├── Evidence
├── Risk Assessment
├── Scenario Analysis
├── Conversation
└── Final Report

This structure should be reflected in the frontend architecture so that future authentication and persistent project history can be added without redesigning the core workflow.

---

## 9. MVP Scope Boundary

Required for MVP:

* Home page
* Top navigation
* Start New Decision
* Core decision workflow entry
* Basic history/project structure if technically feasible

Reserved for future versions:

* Real-time News crawling
* News relevance ranking
* Personalized news monitoring
* Policy-change notifications
* Full authentication and enterprise workspace permissions

Do not add unnecessary technical complexity for the future News or enterprise account functions during the MVP implementation.



Initial Assessment Page
可以先是简单企业画像目录。再往下是风险雷达，分板块列出可能风险，板块色区从高风险到低风险颜色渐变。标题简洁说明，下面小字详细说明一下风险，并列出证据，每条证据为链接，点击可以看到数据原文。AI思考过程折叠，但是点击可以看到完整rationale。接下来底部是一个“进行模拟推演”的button，点击再重新接回agent进行模拟，这样可以比较突出特色。
┌─────────────────────────────────────────────────┐
│ Initial Supply Chain Assessment                 │
│                                                 │
│ Company Profile                                 │
│ ─────────────────────────────────────────────── │
│ Company   Industry   Production   Markets       │
│ XXX       EV Battery China 30%   US            │
│                     Vietnam 70%                 │
│                                                 │
│ Decision Context                                │
│ Considering whether to increase China capacity │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│ Geopolitical & Supply Chain Risk Overview       │
│                                                 │
│                  Trade ● HIGH                   │
│                       /                         │
│          Political ● ───── ● Supply Chain      │
│             MEDIUM             HIGH             │
│                       \                         │
│                  Regulation ● LOW               │
│                                                 │
├─────────────────────────────────────────────────┤
│ Risk Details                                    │
│                                                 │
│ [HIGH] US Tariff Exposure                       │
│ Short explanation...                            │
│                                                 │
│ Evidence                                       │
│ • USTR — ...                                   │
│ • WTO — ...                                    │
│                                                 │
│ [View rationale ▾]                              │
│                                                 │
│ [MEDIUM] Supplier Dependency                    │
│ ...                                             │
│                                                 │
├─────────────────────────────────────────────────┤
│                                                 │
│        [ Run Scenario Simulation → ]            │
│                                                 │
└─────────────────────────────────────────────────┘

## Initial Assessment Page

### 1. Purpose

The Initial Assessment page is the user's first substantive output after submitting the consultation form.

The page should allow the user to quickly understand:

1. How the system understands the company and its current situation
2. Which geopolitical and supply-chain risks are most relevant
3. What evidence supports each assessment
4. Why the system reached the assessment
5. How to proceed to scenario simulation

The page should prioritize clarity, evidence traceability, and decision relevance over visual complexity.

---

## 2. Page Structure

### Section 1 — Company Profile

Display a concise summary of the company's current situation.

Include:

* Company name
* Industry
* Main products
* Home country
* Current production footprint
* Target markets
* Decision question
* Key decision constraints / priorities when available

Keep this section compact. It should function as a quick context check rather than a detailed company report.

Provide an option such as **View Full Profile** if the information is too long to display directly.

---

### Section 2 — Risk Overview

Display a visual overview of the main risk categories.

Recommended categories may include:

* Trade
* Geopolitical / Political
* Supply Chain
* Regulatory / Compliance
* Market Access
* Operational

Use qualitative risk levels:

* High
* Medium
* Low

Do not imply unsupported numerical precision such as 0–100 risk scores.

The visual may use a radar-style or radial visualization, with visual intensity representing risk severity.

Risk categories should be clickable and linked to their corresponding detailed risk sections.

---

### Section 3 — Risk Details

Each major risk should use a consistent structure.

Example:

**[HIGH] US Tariff Exposure**

Concise explanation:

> Changes in US trade policy may materially affect the company's export exposure.

**Evidence**

Display source cards or links rather than raw URLs.

Each source should show:

* Source title
* Publisher
* Publication date
* Authority level

Example:

> WTO — Trade Monitoring Database
> Official source · 2026-09-12

Clicking the evidence should open the original source or an available source preview.

---

### Section 4 — Decision Rationale

Do not display hidden model reasoning or chain-of-thought.

Instead, provide a concise and structured explanation of the assessment.

Label:

**Decision Rationale ▾**

When expanded, show:

* Key factors considered
* Main evidence supporting the assessment
* Relevant assumptions
* Important uncertainties

The rationale should explain the conclusion without exposing private chain-of-thought.

---

### Section 5 — Uncertainty

For risks where evidence is incomplete, conflicting, outdated, or dependent on future developments, explicitly display:

**Uncertainty**

Example:

> Future US tariff measures remain uncertain and may materially change the assessment.

This section should be visually distinguishable from factual evidence.

---

## 3. Primary CTA

At the bottom of the page, provide a prominent primary action:

**Run Scenario Simulation →**

Purpose:

Move the user from risk diagnosis to strategic decision simulation.

Clicking the button should trigger the scenario analysis workflow and connect to the existing Agent/backend workflow.

The Initial Assessment page should therefore function as the transition point:

Company Understanding
→ Risk Diagnosis
→ Scenario Simulation

---

## 4. Visual Design

Style:

* Professional B2B
* Blue and white primary palette
* High information clarity
* Strong typography hierarchy
* Minimal animation
* Clean spacing
* Evidence-first presentation

Avoid:

* Excessive cards
* Decorative animations
* Unsupported numerical risk scores
* Large blocks of AI-generated text
* Visual elements that imply false analytical precision


# Scenario Simulation Page — Frontend Specification

## 1. Overview

Build the Scenario Simulation result page for an AI Supply Chain Relocation Decision Agent.

This page is displayed after the user clicks:

```
Run Scenario Simulation →
```

The purpose of this page is to help users compare different supply-chain strategies under geopolitical uncertainty.

The page should emphasize:

* Scenario comparison
* Evidence-based analysis
* Explainability
* Decision support rather than automatic decision making

The system should present AI-generated assessments as strategic analysis, not as guaranteed predictions.

---

# 2. Simulation Loading State

Before showing results, display a short simulation progress animation.

## Requirements

Duration:

* Approximately 2–5 seconds

Design:

* Professional enterprise AI style
* Minimal animation
* Blue/white visual language

Example:

```
Running Scenario Simulation

Analyzing possible supply chain futures...

[████████░░░░] 65%
```

Display progress steps:

```
✓ Reviewing company profile
✓ Analyzing supply-chain structure
✓ Retrieving evidence database
✓ Evaluating geopolitical risks
✓ Comparing relocation scenarios
✓ Generating scenario assessment
```

The loading state should communicate that multiple analysis steps are being performed.

---

# 3. Result Page Layout

After simulation completion, navigate to:

```
Scenario Comparison Dashboard
```

## Page Header

Title:

```
Strategic Scenario Analysis
```

Subtitle:

```
AI-generated assessment based on company profile,
evidence database, risk analysis and user constraints.
```

---

# 4. Scenario Comparison Dashboard

The first visible section should display three scenario cards.

Default scenarios:

## Scenario A

```
Maintain Current Layout
```

Meaning:
Maintain existing production structure.

Example:
China + Vietnam current production distribution.

---

## Scenario B

```
Increase China Production
```

Meaning:
Increase production capacity or operational dependency in China.

Do not use "Back to China" because many companies do not fully relocate.

---

## Scenario C

```
Hybrid Diversification
```

Meaning:
Maintain multiple production locations.

Example:
China + Southeast Asia + other regions.

---

# 5. Scenario Card Design

Each scenario should be displayed as an independent card.

Example:

```
--------------------------------
Hybrid Diversification

Overall Score:
82 / 100

Confidence:
Medium

Cost Impact        75
Supply Resilience  90
Geo Risk           85
Market Access      80
Feasibility        78

View Analysis →
--------------------------------
```

---

# 6. Evaluation Dimensions

Each scenario should be evaluated across five dimensions.

## 6.1 Cost Impact

Measures:

* Manufacturing cost
* Labor cost
* Logistics cost
* Supplier ecosystem impact
* Required investment

---

## 6.2 Supply Chain Resilience

Measures:

* Supplier availability
* Dependency concentration
* Production flexibility
* Ability to absorb disruptions

---

## 6.3 Geopolitical Risk Exposure

Measures:

* Tariff exposure
* Export control risk
* Political uncertainty
* Regulatory exposure

Higher score means lower exposure.

---

## 6.4 Market Access

Measures:

* Export accessibility
* Tariff implications
* Rules of origin
* Customer requirements
* Regional trade agreements

---

## 6.5 Implementation Feasibility

Measures:

* Required investment
* Timeline
* Existing assets
* Supplier migration difficulty
* Operational complexity

---

# 7. Overall Score

The overall score should NOT be a simple average.

It should consider user priorities collected during onboarding.

Example:

User priority:

```
Supply Chain Resilience > Cost
```

The scoring system should increase the weight of resilience.

Display:

```
Overall Score:
82 / 100

Confidence:
Medium

Based on:
- Evidence availability
- Data completeness
- Scenario assumptions
```

Add disclaimer:

```
Scores are AI-generated estimates based on available evidence and assumptions.
They are not predictions of future outcomes.
```

---

# 8. Scenario Detail View

When users click:

```
View Analysis →
```

Open detailed scenario analysis.

Each scenario should contain:

---

## 8.1 Scenario Overview

Explain:

* What this strategy means
* Expected supply-chain configuration

Example:

```
Increase China production from 30% to 60%
while maintaining Vietnam export capacity.
```

---

## 8.2 Potential Benefits

Display:

* Strategic advantages
* Operational benefits

Example:

```
- Stronger supplier ecosystem
- Lower coordination complexity
- Faster manufacturing scaling
```

---

## 8.3 Potential Risks

Display:

* Main disadvantages
* Risk exposure

Example:

```
- Higher tariff exposure for US exports
- Export control uncertainty
```

---

## 8.4 Key Assumptions

Important section.

Example:

```
Assumption:
US tariff policy remains unchanged.
```

Purpose:
Show uncertainty behind scenario analysis.

---

## 8.5 Evidence Support

Every important conclusion should have linked evidence.

Display:

```
Conclusion:
China provides a mature battery supply-chain ecosystem.

Evidence:
McKinsey Report 2025

Source:
[link]

Confidence:
High
```

Evidence should include:

* Source name
* Date
* Authority level
* Link
* Related conclusion

---

# 9. Analysis Explanation

Do NOT display internal AI chain-of-thought.

Instead create a collapsible section:

```
Why this assessment?
```

When expanded:

Display:

* Main factors considered
* Evidence used
* Logical explanation
* Key assumptions

Example:

```
This scenario receives a higher resilience score because:

1. China has a mature battery supplier ecosystem.
2. Existing production capacity reduces relocation difficulty.
3. However, US tariff exposure remains a concern.
```

---

# 10. Initial Strategic Assessment Report

After scenario comparison, generate a preliminary report section.

Title:

```
Initial Strategic Assessment
```

Structure:

```
1. Executive Summary

2. Company Profile

3. Current Supply Chain Overview

4. Key Risks Identified

5. Scenario Comparison

6. Evidence & Assumptions

7. Questions for Further Analysis
```

---

# 11. Continue AI Consultation

At the bottom of the page add primary CTA:

```
Continue AI Consultation →
```

Purpose:

Allow users to provide additional information and refine analysis.

When clicked:

Navigate to LLM chat interface.

The chat session should automatically include previous context:

* Company Profile
* Evidence Database
* Risk Assessment
* Scenario Results
* Initial Assessment Report

User should not need to repeat previous information.

---

# 12. UI Style Requirements

Overall style:

Professional enterprise AI product.

Color:

Primary:

* White
* Blue

Style keywords:

* Reliable
* Analytical
* Professional
* Data-driven

Avoid:

* Futuristic excessive animation
* Gaming style
* Overly colorful dashboards

Recommended components:

* Cards
* Charts
* Progress indicators
* Expandable evidence sections
* Score visualization

---

# 13. Data Interface Requirement

Frontend should be designed around backend API response.

Expected scenario object:

```json
{
  "scenario_name": "Hybrid Diversification",
  "overall_score": 82,
  "confidence": "Medium",
  "scores": {
    "cost": 75,
    "resilience": 90,
    "geopolitical_risk": 85,
    "market_access": 80,
    "feasibility": 78
  },
  "summary": "",
  "benefits": [],
  "risks": [],
  "assumptions": [],
  "evidence": []
}
```

Frontend should support rendering multiple scenarios dynamically.

Do not hard-code only three scenarios.

```
```

Simulation Result

│
├── Scenario Comparison Dashboard
│
│     Maintain
│     Increase China Production
│     Hybrid
│
├── Detailed Scenario Analysis（点击展开）
│
│     Benefits
│     Risks
│     Score explanation
│     Evidence
│     Assumptions
│
├── Initial Strategic Assessment
│
└── Continue AI Consultation


