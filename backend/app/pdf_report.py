from __future__ import annotations

import html
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .schemas import Assessment


FONT_NAME = "STSong-Light"

# Report labels follow the language requested for the assessment (UI.md §4).
REPORT_LABELS: dict[str, dict[str, str]] = {
    "zh": {
        "document_title": "供应链迁移决策报告",
        "title": "供应链迁移决策报告",
        "summary": "管理层摘要",
        "profile": "企业画像",
        "risks": "关键风险评估",
        "scenarios": "情景比较",
        "detail": "情景细节与假设",
        "consultation": "咨询洞见",
        "actions": "建议行动",
        "uncertainty": "不确定性与人工复核",
        "evidence": "证据来源",
        "trace": "Agent 执行轨迹",
        "disclaimer": (
            "本报告用于辅助决策，不构成法律、投资或合规意见。"
            "高风险结论必须由企业负责人或专业顾问复核。"
        ),
        "human_review": "需要人工复核",
        "yes": "是",
        "no": "否",
        "no_consultation": "本次咨询没有额外的对话记录。",
        "confidence": "置信度",
        "benefits": "潜在收益",
        "scenario_risks": "潜在风险",
        "assumptions": "关键假设",
        "footprint": "全球生产布局",
        "supply_chain": "供应链结构",
        "gaps": "信息缺口",
        "col_country": "国家",
        "col_facility": "设施",
        "col_role": "角色",
        "col_share": "占比",
        "col_capacity": "产能",
        "col_status": "状态",
        "col_stage": "环节",
        "col_region": "地区",
        "col_company_role": "该公司角色",
        "col_priority": "优先级",
        "col_item": "缺失信息",
        "col_why": "为什么重要",
        "col_action": "建议动作",
        "unknown": "未知",
        "priority_critical": "关键",
        "priority_important": "重要",
        "priority_optional": "可选",
        "stage_raw_material": "原材料",
        "stage_component": "材料/零部件",
        "stage_manufacturing": "制造",
        "stage_downstream": "下游应用",
        "score_breakdown": "五维评分明细",
        "col_dimension": "维度",
        "col_band": "档位",
        "col_score": "分数",
        "col_reason": "评分理由",
        "col_evidence_link": "证据",
        "band_very_favourable": "非常有利",
        "band_favourable": "有利",
        "band_neutral": "中性",
        "band_unfavourable": "不利",
        "band_very_unfavourable": "非常不利",
        "dim_cost_score": "成本影响",
        "dim_resilience_score": "供应链韧性",
        "dim_geopolitical_risk_score": "地缘政治风险",
        "dim_market_access_score": "市场准入",
        "dim_implementation_score": "落地可行性",
    },
    "en": {
        "document_title": "Supply Chain Relocation Decision Report",
        "title": "Supply Chain Relocation Decision Report",
        "summary": "Executive summary",
        "profile": "Company profile",
        "risks": "Key risk assessment",
        "scenarios": "Scenario comparison",
        "detail": "Scenario detail and assumptions",
        "consultation": "Consultation insights",
        "actions": "Recommended next actions",
        "uncertainty": "Uncertainties and human review",
        "evidence": "Evidence sources",
        "trace": "Agent execution trace",
        "disclaimer": (
            "This report supports a decision; it is not legal, investment or "
            "compliance advice. High-risk conclusions must be reviewed by the "
            "responsible manager or an external adviser."
        ),
        "human_review": "Human review required",
        "yes": "yes",
        "no": "no",
        "no_consultation": "No additional consultation turns were recorded.",
        "confidence": "Confidence",
        "benefits": "Potential benefits",
        "scenario_risks": "Potential risks",
        "assumptions": "Key assumptions",
        "footprint": "Global manufacturing footprint",
        "supply_chain": "Supply chain structure",
        "gaps": "Information gaps",
        "col_country": "Country",
        "col_facility": "Facility",
        "col_role": "Role",
        "col_share": "Share",
        "col_capacity": "Capacity",
        "col_status": "Status",
        "col_stage": "Stage",
        "col_region": "Region",
        "col_company_role": "Company role",
        "col_priority": "Priority",
        "col_item": "Missing information",
        "col_why": "Why it matters",
        "col_action": "Recommended action",
        "unknown": "unknown",
        "priority_critical": "Critical",
        "priority_important": "Important",
        "priority_optional": "Optional",
        "stage_raw_material": "Raw materials",
        "stage_component": "Materials / components",
        "stage_manufacturing": "Manufacturing",
        "stage_downstream": "Downstream",
        "score_breakdown": "Five-dimension score breakdown",
        "col_dimension": "Dimension",
        "col_band": "Band",
        "col_score": "Score",
        "col_reason": "Reason",
        "col_evidence_link": "Evidence",
        "band_very_favourable": "Very favourable",
        "band_favourable": "Favourable",
        "band_neutral": "Neutral",
        "band_unfavourable": "Unfavourable",
        "band_very_unfavourable": "Very unfavourable",
        "dim_cost_score": "Cost impact",
        "dim_resilience_score": "Supply-chain resilience",
        "dim_geopolitical_risk_score": "Geopolitical risk",
        "dim_market_access_score": "Market access",
        "dim_implementation_score": "Implementation feasibility",
    },
}


def report_labels(assessment: Assessment) -> dict[str, str]:
    return REPORT_LABELS.get(getattr(assessment, "language", "en"), REPORT_LABELS["en"])
NAVY = colors.HexColor("#14324A")
TEAL = colors.HexColor("#087F75")
LIGHT = colors.HexColor("#EEF4F6")
BORDER = colors.HexColor("#D7E0E8")
MUTED = colors.HexColor("#617080")
RED = colors.HexColor("#B42318")
AMBER = colors.HexColor("#B56417")
GREEN = colors.HexColor("#207A4B")


def build_assessment_pdf(assessment: Assessment) -> bytes:
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
    labels = report_labels(assessment)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=f"{assessment.company_profile.company_name} - {labels['document_title']}",
        author="Geopolitical Supply Chain Decision Agent",
    )
    styles = _styles()
    story = [
        Paragraph(labels["title"], styles["Title"]),
        Paragraph(
            html.escape(assessment.company_profile.company_name),
            styles["Subtitle"],
        ),
        Spacer(1, 3 * mm),
        HRFlowable(width="100%", thickness=1, color=BORDER),
        Spacer(1, 5 * mm),
        _metadata_table(assessment, styles),
        Spacer(1, 7 * mm),
        _section(labels["summary"], styles),
        Paragraph(
            html.escape(assessment.company_profile.summary),
            styles["Body"],
        ),
        Paragraph(
            f"<b>{html.escape(assessment.recommendation.headline)}</b>",
            styles["Body"],
        ),
        Paragraph(
            html.escape(assessment.recommendation.rationale),
            styles["Body"],
        ),
        Spacer(1, 5 * mm),
        _section(labels["profile"], styles),
        _profile_table(assessment, styles),
        *_intelligence_sections(assessment, styles, labels),
        Spacer(1, 6 * mm),
        _section(labels["risks"], styles),
        _risk_table(assessment, styles),
        Spacer(1, 6 * mm),
        _section(labels["scenarios"], styles),
        _scenario_table(assessment, styles),
        Spacer(1, 6 * mm),
        _section(labels["detail"], styles),
        *_scenario_detail(assessment, styles, labels),
        Spacer(1, 6 * mm),
        _section(labels["consultation"], styles),
        *_consultation_section(assessment, styles, labels),
        Spacer(1, 6 * mm),
        _section(labels["actions"], styles),
        _bullet_list(assessment.recommendation.next_actions, styles),
        Spacer(1, 5 * mm),
        _section(labels["uncertainty"], styles),
        Paragraph(
            f"{labels['human_review']}: "
            + (labels["yes"] if assessment.recommendation.requires_human_review else labels["no"]),
            styles["Body"],
        ),
        _bullet_list(
            [
                *assessment.recommendation.uncertainty,
                *assessment.limitations,
            ],
            styles,
        ),
        Spacer(1, 8 * mm),
        _section(labels["evidence"], styles),
        _evidence_table(assessment, styles),
        Spacer(1, 6 * mm),
        _section(labels["trace"], styles),
        _trace_table(assessment, styles),
        Spacer(1, 6 * mm),
        Paragraph(labels["disclaimer"], styles["Disclaimer"]),
    ]
    document.build(
        story,
        onFirstPage=_page_footer,
        onLaterPages=_page_footer,
    )
    return buffer.getvalue()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "ChineseTitle",
            parent=base["Title"],
            fontName=FONT_NAME,
            fontSize=22,
            leading=30,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "Subtitle": ParagraphStyle(
            "ChineseSubtitle",
            parent=base["Normal"],
            fontName=FONT_NAME,
            fontSize=12,
            leading=18,
            textColor=MUTED,
        ),
        "Heading": ParagraphStyle(
            "ChineseHeading",
            parent=base["Heading2"],
            fontName=FONT_NAME,
            fontSize=14,
            leading=20,
            textColor=NAVY,
            spaceBefore=2,
            spaceAfter=5,
        ),
        "Body": ParagraphStyle(
            "ChineseBody",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=9.5,
            leading=15,
            textColor=colors.HexColor("#243746"),
            spaceAfter=5,
        ),
        "Small": ParagraphStyle(
            "ChineseSmall",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#32485A"),
        ),
        "Cell": ParagraphStyle(
            "ChineseCell",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=7.7,
            leading=11,
            textColor=colors.HexColor("#243746"),
        ),
        "CellHeader": ParagraphStyle(
            "ChineseCellHeader",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "Disclaimer": ParagraphStyle(
            "ChineseDisclaimer",
            parent=base["BodyText"],
            fontName=FONT_NAME,
            fontSize=8,
            leading=12,
            textColor=MUTED,
        ),
    }


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("BACKGROUND", (0, 0), (0, -1), LIGHT),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def _profile_table(
    assessment: Assessment, styles: dict[str, ParagraphStyle]
) -> Table:
    """Compact company profile block so the report stands on its own."""
    profile = assessment.company_profile
    footprint = (
        ", ".join(
            f"{item.country} {item.production_share}%"
            for item in profile.production_footprint
        )
        or "-"
    )
    rows = [
        ("Company", profile.company_name),
        ("Industry", profile.industry),
        ("Products", ", ".join(profile.products)),
        ("Home country", profile.home_country),
        ("Production footprint", footprint),
        ("Target markets", ", ".join(profile.target_markets) or "-"),
        ("Decision question", profile.decision_question),
        ("Time horizon", profile.time_horizon),
        (
            "Priorities",
            ", ".join(
                f"{item.dimension} (weight {item.weight})"
                for item in profile.priorities
            )
            or "-",
        ),
        ("Restrictions", ", ".join(profile.restrictions) or "-"),
    ]
    data = [
        [
            Paragraph(html.escape(str(key)), styles["CellHeader"]),
            Paragraph(html.escape(str(value)), styles["Cell"]),
        ]
        for key, value in rows
    ]
    table = Table(data, colWidths=[46 * mm, None])
    table.setStyle(_table_style())
    return table


def _intelligence_sections(
    assessment: Assessment,
    styles: dict[str, ParagraphStyle],
    labels: dict[str, str],
) -> list:
    """Company Intelligence detail: footprint, supply chain, gaps.

    The report used to describe the company only through the user's form input.
    These sections render the structured model instead, and are omitted entirely
    for assessments produced before the schema existed.
    """
    intelligence = getattr(assessment, "company_intelligence", None)
    if intelligence is None:
        return []
    blocks: list = []

    def text(value: object) -> str:
        raw = str(value or "").strip()
        return raw or labels["unknown"]

    def table(
        header: list[str], rows: list[list[str]], widths: list[float]
    ) -> Table:
        data = [
            [Paragraph(html.escape(cell), styles["CellHeader"]) for cell in header]
        ] + [
            [Paragraph(html.escape(cell), styles["Cell"]) for cell in row]
            for row in rows
        ]
        built = Table(data, colWidths=[width * mm for width in widths], repeatRows=1)
        built.setStyle(_table_style())
        return built

    sites = intelligence.manufacturing_footprint
    if sites:
        blocks.append(Spacer(1, 5 * mm))
        blocks.append(_section(labels["footprint"], styles))
        blocks.append(
            table(
                [
                    labels["col_country"],
                    labels["col_facility"],
                    labels["col_role"],
                    labels["col_share"],
                    labels["col_capacity"],
                    labels["col_status"],
                ],
                [
                    [
                        text(site.country),
                        text(site.facility),
                        text(site.role),
                        (
                            f"{site.production_share}%"
                            if site.production_share is not None
                            else labels["unknown"]
                        ),
                        text(site.capacity),
                        text(site.status),
                    ]
                    for site in sites
                ],
                [22, 34, 38, 18, 26, 22],
            )
        )

    stages = intelligence.supply_chain_structure
    if stages:
        blocks.append(Spacer(1, 5 * mm))
        blocks.append(_section(labels["supply_chain"], styles))
        blocks.append(
            table(
                [
                    labels["col_stage"],
                    labels["col_region"],
                    labels["col_company_role"],
                    labels["col_share"],
                ],
                [
                    [
                        labels.get(f"stage_{stage.stage}", stage.stage),
                        text(stage.region),
                        text(stage.company_role)
                        + (f" — {stage.description}" if stage.description else ""),
                        text(stage.share),
                    ]
                    for stage in stages
                ],
                [28, 30, 88, 24],
            )
        )

    gaps = list(intelligence.information_gaps)
    if gaps:
        rows = []
        for gap in gaps:
            if isinstance(gap, str):
                rows.append([labels["priority_important"], gap, "", ""])
            else:
                rows.append(
                    [
                        labels.get(f"priority_{gap.priority}", gap.priority),
                        gap.item,
                        gap.why_it_matters,
                        gap.recommended_action,
                    ]
                )
        blocks.append(Spacer(1, 5 * mm))
        blocks.append(_section(labels["gaps"], styles))
        blocks.append(
            table(
                [
                    labels["col_priority"],
                    labels["col_item"],
                    labels["col_why"],
                    labels["col_action"],
                ],
                rows,
                [20, 44, 56, 54],
            )
        )
    return blocks


def _scenario_detail(
    assessment: Assessment,
    styles: dict[str, ParagraphStyle],
    labels: dict[str, str],
) -> list:
    """Per-scenario benefits, risks and assumptions (report depth)."""
    blocks: list = []
    for item in assessment.scenarios:
        blocks.append(
            Paragraph(
                f"<b>{html.escape(item.name)}</b> — {html.escape(item.description)}",
                styles["Body"],
            )
        )
        if item.dimension_assessments:
            evidence_by_id = {
                evidence.evidence_id: evidence
                for evidence in assessment.evidence
            }

            def evidence_cell(evidence_ids: list[str]) -> Paragraph:
                labels_for_ids = []
                for evidence_id in evidence_ids:
                    evidence = evidence_by_id.get(evidence_id)
                    if evidence is None:
                        labels_for_ids.append(html.escape(evidence_id))
                        continue
                    link = evidence.document_url or evidence.url
                    if link:
                        labels_for_ids.append(
                            f"<a href='{html.escape(link)}'>"
                            f"{html.escape(evidence_id)}</a>"
                        )
                    else:
                        labels_for_ids.append(html.escape(evidence_id))
                return Paragraph(
                    "<br/>".join(labels_for_ids) or labels["unknown"],
                    styles["Cell"],
                )

            breakdown_by_metric = {
                entry.dimension: entry
                for entry in item.score_breakdown
            }
            rows = [
                [
                    Paragraph(labels["col_dimension"], styles["CellHeader"]),
                    Paragraph(labels["col_band"], styles["CellHeader"]),
                    Paragraph(labels["col_score"], styles["CellHeader"]),
                    Paragraph(labels["col_reason"], styles["CellHeader"]),
                    Paragraph(
                        labels["col_evidence_link"], styles["CellHeader"]
                    ),
                ]
            ]
            for metric in (
                "cost_score",
                "resilience_score",
                "geopolitical_risk_score",
                "market_access_score",
                "implementation_score",
            ):
                dimension = item.dimension_assessments.get(metric)
                breakdown = breakdown_by_metric.get(metric)
                if dimension is None:
                    continue
                band_value = (
                    dimension.band.value
                    if hasattr(dimension.band, "value")
                    else str(dimension.band)
                )
                rows.append(
                    [
                        Paragraph(
                            labels.get(
                                f"dim_{metric}",
                                metric,
                            ),
                            styles["Cell"],
                        ),
                        Paragraph(
                            labels.get(
                                f"band_{band_value}",
                                band_value,
                            ),
                            styles["Cell"],
                        ),
                        Paragraph(
                            str(breakdown.score if breakdown else ""),
                            styles["Cell"],
                        ),
                        Paragraph(
                            html.escape(dimension.reason or ""),
                            styles["Cell"],
                        ),
                        evidence_cell(dimension.evidence_ids),
                    ]
                )
            table = Table(
                rows,
                colWidths=[27 * mm, 22 * mm, 14 * mm, 68 * mm, 38 * mm],
                repeatRows=1,
            )
            table.setStyle(_table_style())
            blocks.append(
                Paragraph(
                    f"<b>{html.escape(labels['score_breakdown'])}</b>",
                    styles["Body"],
                )
            )
            blocks.append(table)
        if item.benefits:
            blocks.append(
                Paragraph(f"<b>{html.escape(labels['benefits'])}</b>", styles["Body"])
            )
            blocks.append(_bullet_list(item.benefits, styles))
        if item.risks:
            blocks.append(
                Paragraph(
                    f"<b>{html.escape(labels['scenario_risks'])}</b>", styles["Body"]
                )
            )
            blocks.append(_bullet_list(item.risks, styles))
        if item.applicable_conditions:
            blocks.append(
                Paragraph(f"<b>{html.escape(labels['assumptions'])}</b>", styles["Body"])
            )
            blocks.append(_bullet_list(item.applicable_conditions, styles))
        confidence = item.confidence or "low"
        blocks.append(
            Paragraph(
                f"<b>{html.escape(labels['confidence'])}</b>: {html.escape(confidence)}"
                + (
                    f" — {html.escape('; '.join(item.confidence_reasons))}"
                    if item.confidence_reasons
                    else ""
                ),
                styles["Small"],
            )
        )
        blocks.append(Spacer(1, 4 * mm))
    return blocks


def _consultation_section(
    assessment: Assessment,
    styles: dict[str, ParagraphStyle],
    labels: dict[str, str],
) -> list:
    """What the consultation added and how it changed the analysis."""
    turns = assessment.chat_history[-8:]
    if not turns:
        return [Paragraph(labels["no_consultation"], styles["Body"])]
    role_labels = (
        {"user": "用户", "assistant": "Agent"}
        if assessment.language == "zh"
        else {"user": "User", "assistant": "Agent"}
    )
    rows = [
        [
            Paragraph("角色", styles["CellHeader"]),
            Paragraph("对话内容", styles["CellHeader"]),
        ]
    ]
    rows.extend(
        [
            Paragraph(
                html.escape(role_labels.get(turn.role, turn.role)),
                styles["Cell"],
            ),
            Paragraph(html.escape(turn.content[:1200]), styles["Cell"]),
        ]
        for turn in turns
    )
    table = Table(rows, colWidths=[22 * mm, 147 * mm], repeatRows=1)
    table.setStyle(_table_style())
    blocks: list = [table]
    analysis = assessment.chat_analysis
    if analysis is not None:
        if analysis.gap_question:
            blocks.append(
                Paragraph(
                    html.escape(
                        f"Agent 追问：{analysis.gap_question}"
                    ),
                    styles["Small"],
                )
            )
        added = [*analysis.new_constraints, *analysis.new_preferences]
        added.extend(
            f"{key}: {value}"
            for key, value in analysis.profile_patch.items()
        )
        if added:
            blocks.append(_bullet_list(added, styles))
        if analysis.gap_updates:
            blocks.append(
                _bullet_list(
                    [
                        f"{update.gap_item}: {update.status} — {update.answer}"
                        for update in analysis.gap_updates
                    ],
                    styles,
                )
            )
        if analysis.scenario_update_required:
            blocks.append(
                Paragraph(
                    html.escape(
                        "新增信息会影响情景评分，建议重新运行情景模拟。"
                        if assessment.language == "zh"
                        else "This input changes scenario scores, so the scenario "
                        "analysis should be re-run."
                    ),
                    styles["Small"],
                )
            )
    return blocks


def _section(title: str, styles: dict[str, ParagraphStyle]) -> KeepTogether:
    return KeepTogether(
        [
            Paragraph(html.escape(title), styles["Heading"]),
            HRFlowable(width="100%", thickness=0.6, color=BORDER),
            Spacer(1, 2 * mm),
        ]
    )


def _metadata_table(
    assessment: Assessment, styles: dict[str, ParagraphStyle]
) -> Table:
    data = [
        [
            Paragraph("评估编号", styles["CellHeader"]),
            Paragraph("模型模式", styles["CellHeader"]),
            Paragraph("数据模式", styles["CellHeader"]),
            Paragraph("人工复核", styles["CellHeader"]),
        ],
        [
            Paragraph(assessment.assessment_id, styles["Cell"]),
            Paragraph(assessment.model_mode, styles["Cell"]),
            Paragraph(assessment.data_mode, styles["Cell"]),
            Paragraph(
                "需要" if assessment.recommendation.requires_human_review else "不需要",
                styles["Cell"],
            ),
        ],
    ]
    table = Table(data, colWidths=[45 * mm, 34 * mm, 34 * mm, 34 * mm])
    table.setStyle(_table_style())
    return table


def _risk_table(
    assessment: Assessment, styles: dict[str, ParagraphStyle]
) -> Table:
    rows = [
        [
            Paragraph("风险", styles["CellHeader"]),
            Paragraph("等级/概率", styles["CellHeader"]),
            Paragraph("业务影响", styles["CellHeader"]),
            Paragraph("证据", styles["CellHeader"]),
        ]
    ]
    for item in assessment.risks:
        rows.append(
            [
                Paragraph(html.escape(item.name), styles["Cell"]),
                Paragraph(
                    f"{html.escape(item.severity)} / {item.probability}%",
                    styles["Cell"],
                ),
                Paragraph(html.escape(item.business_impact), styles["Cell"]),
                Paragraph(
                    html.escape(", ".join(item.evidence_ids)),
                    styles["Cell"],
                ),
            ]
        )
    table = Table(rows, colWidths=[35 * mm, 24 * mm, 67 * mm, 43 * mm])
    table.setStyle(_table_style())
    return table


def _scenario_table(
    assessment: Assessment, styles: dict[str, ParagraphStyle]
) -> Table:
    rows = [
        [
            Paragraph("方案", styles["CellHeader"]),
            Paragraph("综合分", styles["CellHeader"]),
            Paragraph("关键权衡", styles["CellHeader"]),
        ]
    ]
    recommended_id = assessment.recommendation.recommended_scenario_id
    for item in assessment.scenarios:
        marker = "（推荐）" if item.scenario_id == recommended_id else ""
        tradeoffs = "；".join([*item.benefits[:1], *item.risks[:1]])
        rows.append(
            [
                Paragraph(
                    f"{html.escape(item.name)}{marker}<br/>"
                    f"<font color='#617080'>{html.escape(item.description)}</font>",
                    styles["Cell"],
                ),
                Paragraph(str(item.weighted_score), styles["Cell"]),
                Paragraph(html.escape(tradeoffs), styles["Cell"]),
            ]
        )
    table = Table(rows, colWidths=[65 * mm, 20 * mm, 84 * mm])
    table.setStyle(_table_style())
    return table


def _evidence_table(
    assessment: Assessment, styles: dict[str, ParagraphStyle]
) -> Table:
    rows = [
        [
            Paragraph("证据编号", styles["CellHeader"]),
            Paragraph("来源", styles["CellHeader"]),
            Paragraph("内容摘要", styles["CellHeader"]),
            Paragraph("链接", styles["CellHeader"]),
        ]
    ]
    for item in assessment.evidence[:20]:
        title = item.title
        if item.is_mock:
            title = f"[MOCK] {title}"
        rows.append(
            [
                Paragraph(html.escape(item.evidence_id), styles["Cell"]),
                Paragraph(
                    f"{html.escape(item.publisher)}<br/>"
                    f"{html.escape(item.publication_date)} · {item.authority_level}",
                    styles["Cell"],
                ),
                Paragraph(
                    f"<b>{html.escape(title)}</b><br/>"
                    f"{html.escape(item.content[:320])}",
                    styles["Cell"],
                ),
                Paragraph(
                    html.escape(item.url or "本地资料"),
                    styles["Cell"],
                ),
            ]
        )
    table = Table(rows, colWidths=[29 * mm, 35 * mm, 82 * mm, 23 * mm])
    table.setStyle(_table_style())
    return table


def _trace_table(
    assessment: Assessment, styles: dict[str, ParagraphStyle]
) -> Table:
    rows = [
        [
            Paragraph("Agent", styles["CellHeader"]),
            Paragraph("动作", styles["CellHeader"]),
            Paragraph("状态", styles["CellHeader"]),
            Paragraph("说明", styles["CellHeader"]),
        ]
    ]
    for item in assessment.trace:
        rows.append(
            [
                Paragraph(html.escape(item.agent), styles["Cell"]),
                Paragraph(html.escape(item.action), styles["Cell"]),
                Paragraph(
                    f"{html.escape(item.status)} / {item.duration_ms} ms",
                    styles["Cell"],
                ),
                Paragraph(html.escape(item.detail), styles["Cell"]),
            ]
        )
    table = Table(rows, colWidths=[29 * mm, 36 * mm, 30 * mm, 74 * mm])
    table.setStyle(_table_style())
    return table


def _bullet_list(
    items: list[str], styles: dict[str, ParagraphStyle]
) -> Table:
    rows = [
        [
            Paragraph("•", styles["Cell"]),
            Paragraph(html.escape(str(item)), styles["Cell"]),
        ]
        for item in items
    ]
    table = Table(rows, colWidths=[5 * mm, 164 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("REPEATROWS", (0, 0), (-1, 0)),
        ]
    )


def _page_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont(FONT_NAME, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        18 * mm,
        9 * mm,
        "AI+地缘政治风险高校挑战赛 · 供应链迁移决策 Agent",
    )
    canvas.drawRightString(
        A4[0] - 18 * mm,
        9 * mm,
        f"第 {document.page} 页",
    )
    canvas.restoreState()
