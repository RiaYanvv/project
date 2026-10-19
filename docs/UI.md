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
可以先是简单企业画像目录。企业目录不仅是刚刚填写信息的简单罗列，还应该有对企业的agent简短总结和分析。再往下是风险雷达，分板块列出可能风险，板块色区从高风险到低风险颜色渐变。标题简洁说明，下面小字详细说明一下风险，并列出证据，每条证据为链接，点击可以看到数据原文。AI思考过程折叠，但是点击可以看到完整rationale。接下来底部是一个“进行模拟推演”的button，点击再重新接回agent进行模拟，这样可以比较突出特色。
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
│ Evidence （这里的每个evidence在点击是应该可以呈现数据库或网页端原文、PDF之类的文档。内容要么来自data分支中的raw，要么来自search出的网页、数据集。）                                      │
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
当用户点击[ Run Scenario Simulation → ] 之后，有一个短暂的表示开始推演、推演进度的动画。转入结果页面后我希望先把推演结果摆在上面。结果主要就分为维持maintain、back to China、hybrid三类，针对成本、韧性、地缘风险、市场准入等等各类标准以及综合分进行百分制评分，并说明由ai生成及置信度。当用户点击每类推演结果时，出现详细推演结果描述，并列出证据数据。下方生成一份初步报告，包含了profile、risk identify和推演结果等上述信息。最底部button有“继续对话补充信息”，点击后进入LLM交互，聊天初步就携带上述初版报告。接下来等会再聊，这是对推演界面的设计。
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


chat page
咨询页面。这里点击开始聊天后先自动显示从刚刚那份初版报告开始，窗口界面就像一般LLM聊天。而这个报告要作为重要背景贯穿，随着用户给出的信息和展现的偏好不断更新。一开始ai方先给出提示，比如还加入哪些信息可以支持决策。每轮对话后有继续对话/scenario update（点击跳返模拟页面）/结束生成报告三个选项，同时增添增加文件等功能。点击后结束对话，跳转PDF生成页。
# AI Consultation Workspace — Frontend Specification

## 1. Overview

Build the AI Consultation Workspace page for the Supply Chain Relocation Decision Agent.

This page is entered after the user completes the Scenario Simulation stage.

The purpose of this page is not to provide a normal chatbot experience, but to create an interactive decision refinement workspace.

The system should allow users to:

* Continue discussing the initial assessment
* Provide additional business information
* Upload supporting documents
* Modify decision assumptions
* Trigger updated scenario analysis
* Generate the final executive decision report

Core concept:

```
Initial Assessment
        ↓
AI Consultation
        ↓
Information Refinement
        ↓
Scenario Update
        ↓
Final Decision Report
```

---

# 2. Entry State

When the user clicks:

```
Continue AI Consultation →
```

Navigate to:

```
AI Consultation Workspace
```

The chat session should automatically load previous analysis context.

The LLM should NOT start from an empty conversation.

Required context:

* Company Profile
* Current Supply Chain Overview
* Evidence Database
* Risk Assessment
* Scenario Simulation Results
* Initial Strategic Assessment Report

---

# 3. Page Layout

Desktop layout:

```
---------------------------------------------------
| Decision Context Panel | AI Consultation Chat    |
|                        |                         |
| Company Profile        | AI messages             |
| Current Risks          | User messages           |
| Scenario Summary       |                         |
| Updated Information    |                         |
|                        | Action Buttons          |
---------------------------------------------------
```

---

# 4. Left Context Panel

Purpose:

Provide persistent decision context during the conversation.

## Section 1: Company Profile

Display:

* Company name
* Product/business
* Production footprint
* Target markets
* Current decision question

Example:

```
Company:
ABC Battery

Production:
China 30%
Vietnam 70%

Market:
United States

Decision:
Should we increase China production?
```

---

## Section 2: Current Risk Summary

Display identified risks:

Example:

```
Key Risks:

• Tariff exposure
• Supplier dependency
• Export control uncertainty
```

---

## Section 3: Scenario Summary

Display current scenario scores:

Example:

```
Maintain Layout
78/100

Increase China Production
75/100

Hybrid Diversification
86/100
```

---

## Section 4: Updated Information

Display new information provided during consultation.

Example:

```
Updated Information:

+ Vietnam supplier dependency
+ Customer certification constraint
```

---

# 5. Initial AI Message

When entering the page, AI should automatically send a first message.

Example:

```
I have reviewed your company profile, evidence analysis,
risk assessment and scenario simulation.

To improve the assessment, additional information may help:

1. Supplier dependency
2. Cost differences between locations
3. Investment constraints
4. Customer requirements
5. Implementation timeline

You can provide more information or ask questions.
```

Purpose:

Guide users instead of showing an empty chat window.

---

# 6. Chat Interface

The main area should follow enterprise LLM chat design.

Requirements:

* User message bubbles
* AI response bubbles
* Markdown rendering
* Table rendering
* Evidence link rendering
* Expandable explanation sections

The style should be:

* Professional
* Enterprise-oriented
* Consulting assistant style

Avoid:

* Casual chatbot appearance
* Entertainment-style UI

---

# 7. AI Response Structure

AI responses should support structured outputs.

Example:

```
Updated Assessment

Based on your additional information:

Risk Change:
Supplier dependency risk increased.

Scenario Impact:

Hybrid strategy becomes more attractive because...

Evidence:

- McKinsey Report
- Trade data source

Uncertainty:

Limited company-specific supplier data available.
```

---

# 8. Analysis Explanation

Do NOT display model chain-of-thought.

Instead provide an expandable section:

```
Why this assessment?
```

When expanded:

Display:

* Factors considered
* Evidence used
* Key assumptions
* Uncertainty explanation

Example:

```
Factors considered:

1. Existing supplier ecosystem
2. Tariff exposure
3. Relocation difficulty

Key assumption:

US tariff policy remains unchanged.
```

---

# 9. Add Information Function

Add a button:

```
+ Add Information
```

Purpose:

Allow users to provide additional decision-relevant information.

Supported inputs:

## File Upload

Support:

* PDF
* DOCX
* XLSX
* CSV

Examples:

* Annual reports
* Supply chain data
* Supplier lists
* Factory information
* Internal risk assessments

## Manual Information Addition

Categories:

```
Add supplier information

Add factory information

Update production share

Add cost information

Add customer requirements
```

---

# 10. Post-upload Flow

After uploading information:

Show:

```
New information received.

Would you like to update the scenario analysis?
```

Options:

```
Review First

Update Scenario
```

---

# 11. Bottom Action Bar

After each AI response, display three main actions.

Layout:

```
[Continue Consultation]

[Update Scenario Analysis]

[Generate Final Report]
```

---

# 12. Continue Consultation

Default action.

Behavior:

* Keep current chat session
* Allow further questions
* Maintain previous context

---

# 13. Update Scenario Analysis

Purpose:

Re-run scenario simulation based on updated information.

Button:

```
Update Scenario Analysis →
```

Flow:

```
Current Conversation Context

+
New User Information

        ↓

Scenario Simulation Engine

        ↓

Updated Scenario Results
```

---

# 14. Scenario Update Loading State

Display:

```
Updating Scenario Analysis...

Analyzing:

✓ New business constraints
✓ Updated risk factors
✓ Additional evidence
✓ User preferences
```

---

# 15. Updated Scenario Result

After update, return to Scenario Simulation page.

Show comparison:

Before:

```
Hybrid:
82/100
```

After:

```
Hybrid:
86/100 ↑
```

Explain:

```
Reason:

Vietnam supplier dependency increases the value
of China integration.
```

---

# 16. Generate Final Report

Button:

```
Generate Final Report →
```

Before generation show confirmation modal.

Example:

```
Generate final decision report?

The report will include:

✓ Company Profile
✓ Evidence Analysis
✓ Risk Assessment
✓ Scenario Comparison
✓ Consultation Insights
✓ Final Strategic Considerations
```

Button:

```
Confirm and Generate
```

---

# 17. Report Generation Flow

After confirmation:

```
End Consultation

        ↓

Compile:

- Initial Assessment
- Updated Analysis
- Conversation Insights
- Scenario Results
- Evidence

        ↓

Generate PDF Report
```

Navigate to:

```
Executive Decision Report Page
```

---

# 18. Frontend State Management Requirements

The frontend should maintain:

```json
{
  "company_profile": {},
  "risk_assessment": {},
  "scenario_results": {},
  "conversation_history": [],
  "uploaded_documents": [],
  "updated_constraints": [],
  "user_preferences": []
}
```

---

# 19. Backend API Expectations

The chat API should not only return text.

Expected response:

```json
{
  "message": "",

  "context_update": {
    "new_constraints": [],
    "new_preferences": []
  },

  "scenario_update_required": false,

  "updated_analysis": {}
}
```

The frontend should be able to:

* Update context panel
* Refresh scenario summary
* Display new evidence
* Trigger scenario update workflow

---

# 20. UI Style

Maintain consistency with previous pages.

Theme:

* White background
* Blue primary color
* Professional enterprise AI style

Components:

* Chat bubbles
* Context cards
* Expandable evidence sections
* Upload area
* Action buttons
* Progress indicators

The final experience should feel like:

"AI strategy consultant workspace"

not:

"general chatbot".


# Final Decision Report Page — Frontend Specification

## 1. Overview

Build the Final Decision Report page, which is entered after the user chooses:

**Generate Final Report →**

The purpose of this page is to:

* Present the final AI-generated decision report
* Allow the user to preview the report before leaving the consultation
* Download the generated PDF
* Return to the previous consultation if further refinement is needed
* Save the completed consultation as a persistent Decision Project in My Decisions

The page represents the final stage of the core product workflow.

---

# 2. Report Generation Transition

After the user confirms:

**Generate Final Report**

display a short transition / loading state before showing the report.

Example:

> Preparing your Executive Decision Report...

Progress steps may include:

* ✓ Finalizing company profile
* ✓ Consolidating risk assessment
* ✓ Updating scenario analysis
* ✓ Integrating consultation insights
* ✓ Preparing evidence references
* ✓ Generating final report

Requirements:

* Short and minimal animation
* Blue/white visual language
* Professional enterprise style
* No artificial progress percentage unless actual backend progress is available

---

# 3. Final Report Page Layout

Recommended layout:

```text
-------------------------------------------------
| Locus                                         |
| Final Decision Report                         |
|                                               |
|             [ PDF Preview ]                   |
|                                               |
|                                               |
|                                               |
| Download PDF                                  |
|                                               |
| [ Download Report ]                           |
|                                               |
| [ Back to Consultation ]                      |
|                                               |
| [ End Consultation & Save Decision ]          |
-------------------------------------------------
```

The PDF report itself should be the primary content of the page.

---

# 4. PDF Preview

Display the generated PDF directly within the page.

Preferred behavior:

* Embedded PDF viewer or browser-native PDF preview
* Scrollable
* Readable at desktop and mobile widths where possible
* Allow users to inspect the complete report before downloading

The report should include the final information from the entire consultation process.

Expected report sections:

1. Executive Summary
2. Company Profile
3. Current Supply Chain Situation
4. Key Risk Assessment
5. Scenario Comparison
6. Consultation Insights
7. Final Decision / Recommendation
8. Evidence Sources
9. Uncertainties & Limitations

The frontend should not generate or rewrite the report content itself. It should display the PDF returned by the backend report-generation service.

---

# 5. Download Function

Display a clear primary action below the preview:

**Download PDF**

The download should use the report file or report URL returned by the backend.

Optional metadata:

* Report title
* Generation date
* Decision Project name

---

# 6. Back to Consultation

Provide a secondary action:

**Back to Consultation**

Behavior:

* Return to the previous AI Consultation page
* Preserve the entire consultation state
* Do not delete or regenerate the current report automatically
* Allow the user to continue modifying the decision analysis

Example:

```text
[ ← Back to Consultation ]
```

If the user makes additional changes after returning, the final report should be considered outdated until regenerated.

---

# 7. End Consultation & Save Decision

Provide a final primary action:

**End Consultation & Save Decision**

Purpose:

Finalize the current Decision Project and save the complete consultation state to My Decisions.

Before saving, display a confirmation modal:

```text
Save this decision project?

The following will be saved:
✓ Company Profile
✓ Evidence
✓ Risk Assessment
✓ Scenario Analysis
✓ Consultation History
✓ Final Decision
✓ Generated PDF Report
```

Actions:

**Save & Return Home**

**Cancel**

---

# 8. Decision Project Persistence

Once the user confirms:

**Save & Return Home**

save the current Decision Project.

The saved project should contain at minimum:

```text
decision_project_id
project_name
company_profile
production_footprint
target_markets
decision_question
decision_constraints
evidence
risk_assessment
scenario_results
conversation_history
final_decision
report_id
report_url
created_at
updated_at
status
```

Suggested project status:

```text
ACTIVE
COMPLETED
```

For a consultation that reaches the final report stage, use:

```text
COMPLETED
```

---

# 9. Return to Home

After the project is successfully saved:

Navigate to Home.

The new project should immediately appear in:

**My Decisions / History**

Example:

```text
My Decisions

Vietnam Production Strategy
EV Battery
Completed
Updated: Sep 24, 2026
```

Clicking the project later should reopen its Decision Project workspace.

---

# 10. Product State Logic

The complete flow should be:

```text
AI Consultation
       ↓
Generate Final Report
       ↓
Report Generation Transition
       ↓
Final Decision Report
       ↓
 ┌─────────────────────────────┐
 │                             │
 ↓                             ↓
Back to Consultation      End & Save Decision
 │                             │
 ↓                             ↓
Continue Analysis          Save Project
                               ↓
                           Home / My Decisions
```

---

# 11. Report Versioning

If the user returns to the consultation and changes the analysis, the previously generated PDF should not be silently overwritten.

The system should treat the newly generated report as a new version.

Example:

```text
Report v1
Report v2
```

The latest report should be marked as the current version.

This is important for future Decision Project history.

---

# 12. UI Style

Maintain the existing product design language:

* White background
* Blue primary color
* Clean enterprise layout
* High readability
* Minimal animation
* Clear hierarchy

The PDF preview should dominate the page.

Do not add unnecessary dashboard elements to this page.

The primary goal is to let the user:

1. Review the final report
2. Download it
3. Save the completed decision project



# My Decisions — Decision Project State Specification
关于my decison的状态应该分为这两项：已经完成（即已经生成PDF、确认结束咨询）点进去只能看到关键决策流程点，以及重新决策按钮。如果进行重新决策，那么从intial assessment page开始；
未完成的决策（比如停止在推演等页面），点进去之后就是正常最后一步的页面，可以继续往下执行。
以及新增一个删除历史记录的功能。
## 1. Concept

My Decisions should manage **Decision Projects**, not individual chat sessions.

Each Decision Project represents one complete supply-chain strategic decision workflow.

A project should have exactly two user-facing states:

* **In Progress**
* **Completed**

---

## 2. In Progress

### Definition

A Decision Project is considered **In Progress** when the user has started the consultation process but has not confirmed the final report and ended the consultation.

Possible stages include:

* User Input
* Initial Assessment
* Scenario Simulation
* AI Consultation
* Report Generation / Preview

### Behavior

When the user opens an In Progress project from My Decisions:

> Resume the project from the latest completed stage.

Do not restart the workflow.

Example:

```text
Input
  ↓
Initial Assessment
  ↓
Scenario Simulation
  ↓
AI Consultation ← User left here
```

Opening the project again should return directly to:

**AI Consultation**

The project should preserve all relevant state:

* User input
* Company Profile
* Evidence
* Risk Assessment
* Scenario Results
* Conversation History
* Uploaded Documents
* Updated Constraints
* User Preferences
* Current Stage

Primary action:

**Resume Decision →**

---

## 3. Completed

### Definition

A project becomes **Completed** only when:

1. The final PDF has been generated
2. The user explicitly confirms:
   **End Consultation & Save Decision**

### Behavior

A Completed project should become a historical decision record.

Opening the project should NOT return to the previous chat session.

Instead, show a read-only **Decision Overview**.

Display the key decision process:

### Company Situation

* Company
* Product
* Production footprint
* Target markets

### Initial Assessment

* Major identified risks
* Initial assessment

### Scenario Analysis

* Scenarios considered
* Major trade-offs

### Consultation Summary

* Important information added during consultation
* Important constraints / preference changes

### Final Decision

* Final user decision
* Final recommendation / considerations
* Final report

Do not show the full conversation by default.

The main purpose of the Completed view is to provide a concise historical record of how the decision was reached.

---

## 4. Re-assessment

Completed projects should provide:

**Re-assess Decision →**

Clicking this should NOT modify the original completed project.

Instead:

```text
Completed Decision
        ↓
Create New Assessment
        ↓
Initial Assessment
        ↓
New Scenario Simulation
        ↓
New AI Consultation
        ↓
New Final Report
```

The new project should preserve a reference to the original project:

```text
parent_decision_project_id
```

This allows future version/history tracking.

The original decision remains unchanged.

---

## 5. Decision Project Data Model

Each project should include:

```json
{
  "decision_project_id": "DP-001",
  "status": "IN_PROGRESS",
  "current_stage": "AI_CONSULTATION",

  "company_profile": {},
  "user_input": {},
  "evidence": [],
  "risk_assessment": {},
  "scenario_results": {},
  "conversation_history": [],
  "uploaded_documents": [],

  "final_decision": null,
  "report_id": null,

  "parent_decision_project_id": null,

  "created_at": "",
  "updated_at": ""
}
```

---

## 6. Status Values

Only use:

```text
IN_PROGRESS
COMPLETED
```

Do not create additional user-facing status categories unless required later.

---

## 7. Current Stage Values

Use:

```text
INPUT
INITIAL_ASSESSMENT
SCENARIO_SIMULATION
AI_CONSULTATION
REPORT_GENERATION
COMPLETED
```

`current_stage` determines where an In Progress project should resume.

---

## 8. My Decisions UI

Recommended structure:

```text
My Decisions

[ + Start New Decision ]

IN PROGRESS
────────────────────────
Vietnam Production Strategy
EV Battery
Last updated: Sep 24, 2026
Current stage: AI Consultation

[ Resume → ]


COMPLETED
────────────────────────
China–Vietnam Supply Chain Strategy
EV Battery
Completed: Sep 22, 2026

Final Decision:
Hybrid Diversification

[ View Decision ]
[ Re-assess → ]
```

Completed projects should be visually distinct from In Progress projects.

---

## 9. Product Principle

The system must clearly distinguish:

**Resume** from **Re-assess**.

* **Resume** = continue an unfinished decision project from the latest stage.
* **Re-assess** = create a new decision analysis based on a completed historical decision.

Never overwrite a completed decision when creating a reassessment.
