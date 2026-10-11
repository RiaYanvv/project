from __future__ import annotations

from .schemas import (
    Assessment,
    InformationGap,
    ReportAppendix,
    ReportContent,
    ReportDecisionContext,
    ReportExecutionAction,
    ReportExecutiveBrief,
    ReportStrategicOption,
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def compose_report(assessment: Assessment) -> ReportContent:
    """Compose a management report from existing structured analysis only."""
    profile = assessment.company_profile
    recommendation = assessment.recommendation
    recommended_id = recommendation.recommended_scenario_id
    best = next(
        (
            item
            for item in assessment.scenarios
            if item.scenario_id == recommended_id
        ),
        assessment.scenarios[0] if assessment.scenarios else None,
    )
    risks = sorted(
        assessment.risks,
        key=lambda item: item.risk_score,
        reverse=True,
    )
    key_reasons = []
    if best is not None:
        key_reasons.extend(best.benefits[:2])
        for metric, label in (
            ("cost_score", "成本"),
            ("resilience_score", "供应链韧性"),
            ("market_access_score", "市场准入"),
            ("implementation_score", "实施可行性"),
        ):
            key_reasons.append(
                f"{label}评分为 {getattr(best, metric)}/100"
            )
    key_reasons = list(dict.fromkeys(item for item in key_reasons if item))[:3]
    main_trade_off = (
        best.risks[0]
        if best is not None and best.risks
        else ("主要代价仍需补充数据后确认" if assessment.language == "zh" else "The main trade-off requires confirmation.")
    )
    decision_required = [
        *recommendation.next_actions[:4],
        *(
            [f"确认信息缺口：{gap.item}" for gap in assessment.company_intelligence.information_gaps if isinstance(gap, InformationGap)]
            if assessment.company_intelligence
            else []
        ),
    ][:5]

    context = ReportDecisionContext()
    context.supply_chain_context = [
        _clean(profile.summary),
        "生产布局：" + "；".join(
            f"{item.country} {item.production_share}%"
            for item in profile.production_footprint
        ),
        "目标市场：" + "、".join(profile.target_markets),
    ]
    context.supply_chain_context = [
        item for item in context.supply_chain_context if item and not item.endswith("：")
    ]
    context.relevant_risks = [
        f"{item.name}（{item.severity}，{item.risk_score}/125）：{_clean(item.business_impact)}"
        for item in risks[:5]
    ]
    context.mitigation_effect = [
        "战略选项需优先降低已识别的贸易、合规、供应商集中和市场准入风险；"
        "具体缓解效果由其成本、韧性、市场准入和落地可行性评分及适用条件共同决定。"
    ] if assessment.language == "zh" else [
        "The strategic options should reduce the identified trade, compliance, supplier-concentration and market-access risks; mitigation depends on each option's cost, resilience, market-access and feasibility conditions."
    ]

    options: list[ReportStrategicOption] = []
    for scenario in assessment.scenarios[:3]:
        status = (
            "recommended"
            if scenario.scenario_id == recommended_id
            else "alternative"
        )
        strongest = max(
            (
                ("成本", scenario.cost_score),
                ("供应链韧性", scenario.resilience_score),
                ("地缘政治稳定", scenario.geopolitical_risk_score),
                ("市场准入", scenario.market_access_score),
                ("实施可行性", scenario.implementation_score),
            ),
            key=lambda item: item[1],
        )
        options.append(
            ReportStrategicOption(
                scenario_id=scenario.scenario_id,
                name=scenario.name,
                recommendation_status=status,
                summary=_clean(scenario.description),
                expected_benefits=list(scenario.benefits),
                main_costs=list(scenario.risks[:2]),
                key_risks=list(scenario.risks),
                execution_conditions=list(scenario.applicable_conditions),
                fit_assessment=(
                    f"该方案综合分 {scenario.weighted_score}/100，"
                    f"相对优势集中在{strongest[0]}（{strongest[1]}/100）。"
                ),
            )
        )

    gaps = (
        assessment.company_intelligence.information_gaps
        if assessment.company_intelligence
        else []
    )
    execution_plan: list[ReportExecutionAction] = []
    for gap in gaps:
        if not isinstance(gap, InformationGap):
            continue
        execution_plan.append(
            ReportExecutionAction(
                action=gap.recommended_action or f"核实并补充：{gap.item}",
                rationale=gap.why_it_matters or "该信息会影响评分与推荐条件。",
                owner="待指定",
                timing="下一决策阶段前",
                decision_gate="关键信息完成核验并重新运行情景推演",
                trigger="该信息与当前假设不一致，或政策/成本条件发生变化",
            )
        )
    for action in recommendation.next_actions[:5]:
        execution_plan.append(
            ReportExecutionAction(
                action=_clean(action),
                rationale="该行动直接响应推荐方案、主要风险或人工复核要求。",
                owner="待指定",
                timing="下一决策周期",
                decision_gate="行动结果已提交评审并更新决策上下文",
                trigger="结果偏离当前推荐假设时重新评估",
            )
        )

    return ReportContent(
        language=assessment.language,
        executive_brief=ReportExecutiveBrief(
            decision_question=_clean(profile.decision_question),
            preliminary_recommendation=_clean(
                recommendation.headline
                or (
                    f"暂推荐 {best.name}"
                    if best is not None
                    else "暂不适合作出确定推荐"
                )
            ),
            key_reasons=key_reasons,
            main_trade_off=_clean(main_trade_off),
            decision_required=decision_required,
        ),
        decision_context=context,
        strategic_options=options,
        execution_plan=execution_plan[:10],
        appendix=ReportAppendix(
            evidence_ids=[item.evidence_id for item in assessment.evidence],
            risk_ids=[item.risk_id for item in assessment.risks],
            information_gaps=[
                gap.item if isinstance(gap, InformationGap) else str(gap)
                for gap in gaps
            ],
            assumptions=[
                *recommendation.uncertainty,
                *assessment.limitations,
            ],
            methodology=[
                "公司画像、证据检索、风险评估、情景推演、咨询更新和报告合成使用同一份结构化 Assessment。",
                "报告合成只筛选和编辑既有事实，不新增政策、市场或公司事实。",
            ],
        ),
    )

