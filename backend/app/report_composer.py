from __future__ import annotations

from typing import Any

from .schemas import (
    Assessment,
    InformationGap,
    ReportAppendix,
    ReportContent,
    ReportDecisionContext,
    ReportDecisionRisk,
    ReportDimensionScore,
    ReportEvidenceRecord,
    ReportExecutionAction,
    ReportExecutiveBrief,
    ReportScenarioScore,
    ReportStrategicOption,
)


def _clean(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _text(value: object, fallback: str = "") -> str:
    cleaned = _clean(value)
    return cleaned or fallback


def _as_int(value: object, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _items(value: object) -> list[str]:
    if isinstance(value, str):
        text = _clean(value)
        return [text] if text else []
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _clean(item))]


def _dict_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _information_gaps(assessment: Assessment) -> list[InformationGap]:
    intelligence = assessment.company_intelligence
    if intelligence is None:
        return []
    gaps = [
        gap
        for gap in intelligence.information_gaps
        if isinstance(gap, InformationGap)
    ]
    priority_order = {"critical": 0, "important": 1, "optional": 2}
    return sorted(
        gaps,
        key=lambda gap: priority_order.get(gap.priority, 1),
    )


def _evidence_register(assessment: Assessment) -> list[ReportEvidenceRecord]:
    referenced: list[str] = []
    for source in (
        assessment.recommendation.evidence_ids,
        *[item.evidence_ids for item in assessment.risks],
        *[item.evidence_ids for item in assessment.scenarios],
    ):
        referenced.extend(source)
    ordered_ids = list(dict.fromkeys(referenced))
    by_id = {item.evidence_id: item for item in assessment.evidence}
    records: list[ReportEvidenceRecord] = []
    for evidence_id in ordered_ids:
        item = by_id.get(evidence_id)
        if item is None:
            continue
        limitation = ""
        if item.is_mock:
            limitation = "测试/合成资料，不可作为真实政策或公司事实。"
        elif item.verification_status in {"unverified", "contested", "outdated"}:
            limitation = f"来源状态：{item.verification_status}。"
        records.append(
            ReportEvidenceRecord(
                evidence_id=item.evidence_id,
                claim=_clean(item.title),
                source=f"{item.publisher} · {item.source_type}",
                publication_date=item.publication_date,
                url=item.document_url or item.url or "",
                limitation=limitation,
            )
        )
    if records:
        return records[:20]
    for item in assessment.evidence[:12]:
        records.append(
            ReportEvidenceRecord(
                evidence_id=item.evidence_id,
                claim=_clean(item.title),
                source=f"{item.publisher} · {item.source_type}",
                publication_date=item.publication_date,
                url=item.document_url or item.url or "",
                limitation=(
                    "测试/合成资料，不可作为真实政策或公司事实。"
                    if item.is_mock
                    else ""
                ),
            )
        )
    return records


def _scenario_scores(assessment: Assessment) -> list[ReportScenarioScore]:
    scores: list[ReportScenarioScore] = []
    for scenario in assessment.scenarios:
        dimensions: list[ReportDimensionScore] = []
        for breakdown in scenario.score_breakdown:
            band = (
                breakdown.band.value
                if hasattr(breakdown.band, "value")
                else str(breakdown.band)
            )
            dimensions.append(
                ReportDimensionScore(
                    dimension=breakdown.dimension,
                    band=band,
                    score=max(0, min(100, round(float(breakdown.score)))),
                    weight=max(0, min(5, round(float(breakdown.weight)))),
                    reason=_clean(breakdown.reason),
                )
            )
        scores.append(
            ReportScenarioScore(
                scenario_id=scenario.scenario_id,
                name=scenario.name,
                weighted_score=max(
                    0, min(100, round(float(scenario.weighted_score)))
                ),
                rank=0,
                dimensions=dimensions,
            )
        )
    ordered = sorted(
        scores,
        key=lambda item: item.weighted_score,
        reverse=True,
    )
    for index, item in enumerate(ordered, start=1):
        item.rank = index
    return ordered


def _deterministic_options(
    assessment: Assessment,
) -> list[ReportStrategicOption]:
    recommended_id = assessment.recommendation.recommended_scenario_id
    options: list[ReportStrategicOption] = []
    for scenario in assessment.scenarios[:3]:
        status = (
            "recommended"
            if scenario.scenario_id == recommended_id
            else "alternative"
        )
        strongest = max(
            (
                ("成本效率", scenario.cost_score),
                ("供应链韧性", scenario.resilience_score),
                ("地缘政治稳定性", scenario.geopolitical_risk_score),
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
                    f"综合分 {scenario.weighted_score}/100，"
                    f"相对优势集中在{strongest[0]}（{strongest[1]}/100）。"
                ),
            )
        )
    return options


def _deterministic_context(assessment: Assessment) -> ReportDecisionContext:
    profile = assessment.company_profile
    risks = sorted(
        assessment.risks,
        key=lambda item: item.risk_score,
        reverse=True,
    )
    footprint = "；".join(
        f"{item.country} {item.production_share}%"
        for item in profile.production_footprint
    )
    position = [
        _clean(profile.summary),
        f"现有生产布局：{footprint}。" if footprint else "",
        (
            f"目标市场：{'、'.join(profile.target_markets)}。"
            if profile.target_markets
            else ""
        ),
    ]
    position = [item for item in position if item]
    if not position:
        position = ["当前供应链结构仍缺少可核验的基地、产能和依赖数据。"]

    risk_rows: list[ReportDecisionRisk] = []
    for risk in risks[:5]:
        risk_rows.append(
            ReportDecisionRisk(
                exposure=_clean(risk.name),
                why_it_matters=(
                    _clean(risk.company_specific_trigger)
                    or _clean(risk.impact_description)
                    or _clean(risk.business_impact)
                ),
                decision_implication=(
                    f"{risk.risk_level}风险，决策相关性：{risk.decision_relevance}。"
                    + (
                        " 影响渠道：" + "、".join(risk.impact_channels) + "。"
                        if risk.impact_channels
                        else ""
                    )
                ),
                severity=risk.severity,
                risk_score=risk.risk_score,
                evidence_ids=list(risk.evidence_ids),
            )
        )
    top_risk = risk_rows[0].exposure if risk_rows else "关键外部政策与执行风险"
    return ReportDecisionContext(
        current_position=position[:3],
        footprint_note=(
            "生产基地与产能数据来自当前管理层输入；未核验的数字仅可用于推演，"
            "不能直接视为可立即使用的产能。"
        ),
        principal_risks=risk_rows,
        implications=(
            "当前决策的核心张力，是在成本效率、区域韧性、市场准入和落地可行性之间"
            f"取舍。其中“{top_risk}”最可能改变方案排序；在相关数据与合规路径完成"
            "核验前，推荐应保持条件性。"
        ),
        supply_chain_context=position,
        relevant_risks=[
            f"{item.exposure}（{item.severity}，{item.risk_score}/125）："
            f"{item.why_it_matters}"
            for item in risk_rows
        ],
        mitigation_effect=[
            "地理分散只能改变生产与供应路径，不能自动消除关税、原产地、合规或"
            "客户认证风险；缓解效果取决于具体规则、产品兼容性和执行条件。"
        ],
    )


def _deterministic_execution(
    assessment: Assessment,
) -> list[ReportExecutionAction]:
    gaps = _information_gaps(assessment)
    priority_map = {
        "critical": "P0",
        "important": "P1",
        "optional": "P2",
    }
    actions: list[ReportExecutionAction] = []
    for gap in gaps[:6]:
        action_text = (
            _clean(gap.recommended_action)
            or f"核实并补充“{gap.item}”，形成可用于情景重算的结论。"
        )
        actions.append(
            ReportExecutionAction(
                priority=priority_map.get(gap.priority, "P1"),
                action=action_text,
                deliverable=f"形成《{gap.item}》核验结论及适用的数据口径。",
                rationale=_clean(gap.why_it_matters)
                or "该信息会直接影响风险暴露、情景评分或推荐条件。",
                owner="待指定",
                timing="下一决策阶段前",
                decision_gate=(
                    f"“{gap.item}”已有可追溯证据或管理层确认，足以判断是否"
                    "需要更新风险与情景比较。"
                ),
                trigger=(
                    f"若“{gap.item}”的核验结果与当前管理层假设不一致，"
                    "重新运行相关情景并保留上一版本。"
                ),
            )
        )
    for action_text in assessment.recommendation.next_actions:
        if len(actions) >= 6:
            break
        clean_action = _clean(action_text)
        if not clean_action or any(
            clean_action in item.action for item in actions
        ):
            continue
        actions.append(
            ReportExecutionAction(
                priority="P1",
                action=clean_action,
                deliverable="形成决策所需的核验结果、责任人和下一检查点。",
                rationale="该行动直接响应推荐方案、主要风险或人工复核要求。",
                owner="待指定",
                timing="与生产布局和合规核验并行",
                decision_gate="行动结果已评审，并明确是否改变方案排序。",
                trigger="结果偏离当前推荐假设，或成本、政策、客户条件发生变化。",
            )
        )
    return actions[:6]


def _deterministic_appendix(assessment: Assessment) -> ReportAppendix:
    gaps = _information_gaps(assessment)
    return ReportAppendix(
        evidence=_evidence_register(assessment),
        scenario_scores=_scenario_scores(assessment),
        critical_assumptions=list(
            dict.fromkeys(
                [
                    *assessment.recommendation.uncertainty,
                    *assessment.limitations,
                ]
            )
        )[:12],
        evidence_ids=[item.evidence_id for item in assessment.evidence],
        risk_ids=[item.risk_id for item in assessment.risks],
        information_gaps=[gap.item for gap in gaps],
        assumptions=[
            *assessment.recommendation.uncertainty,
            *assessment.limitations,
        ],
        methodology=[
            "情景评分由后端 rubric 将五档 Band 映射为分数，再按管理层权重加权。",
            "公司画像、风险、情景与推荐均使用同一份结构化 Assessment。",
            "报告合成只筛选、改写和解释已有事实，不新增政策、市场或公司事实。",
            "管理层输入属于未核验估计；公开证据不足时保留 unknown 或信息缺口。",
        ],
    )


def compose_report(assessment: Assessment) -> ReportContent:
    """Deterministic fallback and the factual baseline for report synthesis."""
    recommendation = assessment.recommendation
    best = next(
        (
            item
            for item in assessment.scenarios
            if item.scenario_id == recommendation.recommended_scenario_id
        ),
        assessment.scenarios[0] if assessment.scenarios else None,
    )
    key_reasons: list[str] = []
    if best is not None:
        key_reasons.extend(best.benefits[:2])
        strongest = max(
            (
                ("成本效率", best.cost_score),
                ("供应链韧性", best.resilience_score),
                ("市场准入", best.market_access_score),
                ("实施可行性", best.implementation_score),
            ),
            key=lambda item: item[1],
        )
        key_reasons.append(
            f"{strongest[0]}相对突出（{strongest[1]}/100）"
        )
    key_reasons = list(dict.fromkeys(item for item in key_reasons if item))[:3]
    main_trade_off = (
        best.risks[0]
        if best is not None and best.risks
        else "主要代价仍需补充数据后确认。"
    )
    decision_required = (
        list(recommendation.next_actions[:3])
        or ["确认是否进入下一阶段核验，而非直接批准投资。"]
    )
    if assessment.recommendation.requires_human_review:
        decision_required.append(
            "授权对关键假设、合规路径和成本口径开展人工复核。"
        )

    return ReportContent(
        language=assessment.language,
        executive_brief=ReportExecutiveBrief(
            decision_question=_clean(
                assessment.company_profile.decision_question
            ),
            preliminary_recommendation=_clean(
                recommendation.headline
                or (
                    f"暂推荐 {best.name}，并保留进一步核验条件。"
                    if best is not None
                    else "暂不宜作出确定推荐，需先补充关键数据。"
                )
            ),
            key_reasons=key_reasons,
            main_trade_off=_clean(main_trade_off),
            decision_required=decision_required[:4],
        ),
        decision_context=_deterministic_context(assessment),
        strategic_options=_deterministic_options(assessment),
        execution_plan=_deterministic_execution(assessment),
        appendix=_deterministic_appendix(assessment),
    )


def merge_report_payload(
    base: ReportContent,
    candidate: object,
) -> ReportContent:
    """Merge model-written prose onto the deterministic report facts.

    Scenario IDs, scores, evidence IDs and legacy fallback fields remain anchored
    to the backend-computed report.
    """
    if not isinstance(candidate, dict):
        return base
    data = base.model_dump(mode="json")
    allowed_evidence_ids = {
        item["evidence_id"]
        for item in data["appendix"]["evidence"]
        if item.get("evidence_id")
    }

    brief = candidate.get("executive_brief")
    if isinstance(brief, dict):
        for key in (
            "decision_question",
            "preliminary_recommendation",
            "main_trade_off",
        ):
            if _clean(brief.get(key)):
                data["executive_brief"][key] = _clean(brief.get(key))
        for key in ("key_reasons", "decision_required"):
            values = _items(brief.get(key))
            if values:
                data["executive_brief"][key] = values[:5]

    context = candidate.get("decision_context")
    if isinstance(context, dict):
        for key in ("footprint_note", "implications"):
            if _clean(context.get(key)):
                data["decision_context"][key] = _clean(context.get(key))
        positions = _items(context.get("current_position"))
        if positions:
            data["decision_context"]["current_position"] = positions[:3]
            data["decision_context"]["supply_chain_context"] = positions[:3]
        risks: list[dict[str, Any]] = []
        for row in _dict_rows(context.get("principal_risks"))[:5]:
            exposure = _clean(row.get("exposure") or row.get("risk"))
            if not exposure:
                continue
            risks.append(
                {
                    "exposure": exposure,
                    "why_it_matters": _clean(
                        row.get("why_it_matters") or row.get("why")
                    ),
                    "decision_implication": _clean(
                        row.get("decision_implication")
                        or row.get("implication")
                    ),
                    "severity": _clean(row.get("severity")),
                    "risk_score": max(
                        0, min(125, _as_int(row.get("risk_score")))
                    ),
                    "evidence_ids": [
                        evidence_id
                        for evidence_id in _items(row.get("evidence_ids"))
                        if evidence_id in allowed_evidence_ids
                    ],
                }
            )
        if risks:
            data["decision_context"]["principal_risks"] = risks

    options = _dict_rows(candidate.get("strategic_options"))
    if options:
        base_options = {
            item.get("scenario_id") or item.get("name"): item
            for item in data["strategic_options"]
        }
        for row in options:
            key = _clean(row.get("scenario_id") or row.get("name"))
            target = base_options.get(key)
            if target is None:
                continue
            for field in ("summary", "fit_assessment"):
                if _clean(row.get(field)):
                    target[field] = _clean(row.get(field))
            for field in (
                "expected_benefits",
                "main_costs",
                "key_risks",
                "execution_conditions",
            ):
                values = _items(row.get(field))
                if values:
                    target[field] = values

    plan = _dict_rows(candidate.get("execution_plan"))
    if plan:
        cleaned_plan: list[dict[str, Any]] = []
        for row in plan[:6]:
            action = _clean(row.get("action") or row.get("deliverable"))
            if not action:
                continue
            cleaned_plan.append(
                {
                    "priority": _clean(row.get("priority")) or "P1",
                    "action": action,
                    "deliverable": _clean(row.get("deliverable")),
                    "rationale": _clean(row.get("rationale")),
                    "owner": _clean(row.get("owner")) or "待指定",
                    "timing": _clean(row.get("timing")),
                    "decision_gate": _clean(row.get("decision_gate")),
                    "trigger": _clean(row.get("trigger")),
                }
            )
        if cleaned_plan:
            data["execution_plan"] = cleaned_plan

    appendix = candidate.get("appendix")
    if isinstance(appendix, dict):
        evidence_rows: list[dict[str, Any]] = []
        for row in _dict_rows(appendix.get("evidence"))[:20]:
            evidence_id = _clean(row.get("evidence_id"))
            if not evidence_id or evidence_id not in allowed_evidence_ids:
                continue
            evidence_rows.append(
                {
                    "evidence_id": evidence_id,
                    "claim": _clean(row.get("claim")),
                    "source": _clean(row.get("source")),
                    "publication_date": _clean(row.get("publication_date")),
                    "url": _clean(row.get("url")),
                    "limitation": _clean(row.get("limitation")),
                }
            )
        if evidence_rows:
            data["appendix"]["evidence"] = evidence_rows

        base_scores = {
            item["scenario_id"]: item
            for item in data["appendix"]["scenario_scores"]
        }
        scenario_rows: list[dict[str, Any]] = []
        for row in _dict_rows(appendix.get("scenario_scores"))[:4]:
            scenario_id = _clean(row.get("scenario_id"))
            base_score = base_scores.get(scenario_id)
            if base_score is None:
                continue
            dimensions: list[dict[str, Any]] = []
            for dimension in _dict_rows(row.get("dimensions"))[:5]:
                dimension_name = _clean(dimension.get("dimension"))
                if not dimension_name:
                    continue
                dimensions.append(
                    {
                        "dimension": dimension_name,
                        "band": _clean(dimension.get("band")),
                        "score": max(
                            0, min(100, _as_int(dimension.get("score")))
                        ),
                        "weight": max(
                            0, min(5, _as_int(dimension.get("weight")))
                        ),
                        "reason": _clean(dimension.get("reason")),
                    }
                )
            if dimensions:
                base_score["dimensions"] = dimensions
            if _clean(row.get("name")):
                base_score["name"] = _clean(row.get("name"))
            scenario_rows.append(base_score)
        if scenario_rows:
            data["appendix"]["scenario_scores"] = scenario_rows

        for field in (
            "critical_assumptions",
            "information_gaps",
            "methodology",
        ):
            values = _items(appendix.get(field))
            if values:
                data["appendix"][field] = values[:12]
        if data["appendix"].get("critical_assumptions"):
            data["appendix"]["assumptions"] = data["appendix"][
                "critical_assumptions"
            ]

    try:
        return ReportContent.model_validate(data)
    except Exception:
        return base
