# Sample Output

The exact result depends on the current evidence index, model output, and user
clarifications. A successful assessment returns the following decision package.

## Company profile

- Company: Xiaopeng Motors
- Footprint: China 70%, Vietnam 30%
- Target markets: United States, EU, China
- Decision: relocate part of PACK and vehicle assembly to Southeast Asia
- Budget: USD 75 million
- Time horizon: 6 to 18 months

## Risk assessment

The risk section returns evidence-linked findings across trade policy,
geopolitical exposure, supply-chain dependency, regulatory compliance, market
access, and implementation feasibility. Each finding includes severity,
description, uncertainty, verification status, and linked evidence IDs.

## Scenario comparison

The scenario section compares options such as:

- Maintain the current footprint.
- Increase production in China.
- Relocate or diversify into Vietnam, Thailand, Mexico, or another location.

Each scenario contains:

- Overall score and confidence.
- Cost impact, supply-chain resilience, geopolitical risk, market access, and
  implementation feasibility.
- A five-band assessment for each dimension.
- Reasons and evidence IDs for each score.
- Assumptions, risks, and conditions.

Illustrative comparison:

| Scenario | Overall | Confidence | Main trade-off |
| --- | ---: | --- | --- |
| Diversified overseas PACK and assembly | 55 | Medium | Better market access, weaker cost and execution |
| Increase China production | 47 | Medium | Strong cost position, higher geopolitical concentration |
| Maintain current overseas footprint | 45 | Medium | Limited disruption, unresolved origin and capacity evidence |

These values are illustrative and must not be treated as the output of a live
run.

## Consultation

The consultation response extracts any new constraint into a structured update,
identifies the affected dimensions, and marks whether a scenario re-simulation
is required. Updates remain attached to the decision project and can create a
new scenario version.

## Final report

The PDF report contains:

1. Executive Decision Brief
2. Decision Context
3. Strategic Options
4. Execution Plan and Decision Gates
5. Appendix with evidence, detailed risk findings, and score breakdowns

The report also records assumptions, uncertainty, evidence sources, and the
scenario version used.
