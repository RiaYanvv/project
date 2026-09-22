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
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title=f"{assessment.company_profile.company_name} - 供应链迁移决策报告",
        author="Geopolitical Supply Chain Decision Agent",
    )
    styles = _styles()
    story = [
        Paragraph("供应链迁移决策初步报告", styles["Title"]),
        Paragraph(
            html.escape(assessment.company_profile.company_name),
            styles["Subtitle"],
        ),
        Spacer(1, 3 * mm),
        HRFlowable(width="100%", thickness=1, color=BORDER),
        Spacer(1, 5 * mm),
        _metadata_table(assessment, styles),
        Spacer(1, 7 * mm),
        _section("管理层摘要", styles),
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
        _section("主要风险", styles),
        _risk_table(assessment, styles),
        Spacer(1, 6 * mm),
        _section("情景比较", styles),
        _scenario_table(assessment, styles),
        Spacer(1, 6 * mm),
        _section("建议行动", styles),
        _bullet_list(assessment.recommendation.next_actions, styles),
        Spacer(1, 5 * mm),
        _section("不确定性与人工复核", styles),
        Paragraph(
            "需要人工复核："
            + ("是" if assessment.recommendation.requires_human_review else "否"),
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
        _section("证据链", styles),
        _evidence_table(assessment, styles),
        Spacer(1, 6 * mm),
        _section("Agent 执行轨迹", styles),
        _trace_table(assessment, styles),
        Spacer(1, 6 * mm),
        Paragraph(
            "本报告用于辅助决策，不构成法律、投资或合规意见。"
            "高风险结论必须由企业负责人或专业顾问复核。",
            styles["Disclaimer"],
        ),
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
