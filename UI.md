## 1. Product Entry Experience

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


