from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.company_research import (
    PDF_LIMIT,
    CompanyResearchTool,
)


class SectionRankingTest(unittest.TestCase):
    """Pages are ranked by company-intelligence value, not URL length."""

    def test_document_pages_outrank_landing_pages(self) -> None:
        score = CompanyResearchTool._section_score
        annual = score("https://x.com/kr/investors/data-business-report")
        disclosure = score("https://x.com/kr/investors/investors-disclosure")
        investor = score("https://x.com/kr/investors/stock-graph-recent")
        about = score("https://x.com/kr/about/company")
        esg = score("https://x.com/kr/esg/fair-trade")
        product = score("https://x.com/kr/business/ess")
        self.assertGreater(annual, disclosure)
        self.assertGreater(disclosure, investor)
        self.assertGreater(investor, about)
        self.assertGreater(about, esg)
        self.assertGreater(esg, product)

    def test_ir_is_matched_as_a_path_segment_not_a_substring(self) -> None:
        score = CompanyResearchTool._section_score
        # "cs-inquiry" contains "ir" and must not be treated as an investor page.
        self.assertEqual(score("https://x.com/kr/etc/cs-inquiry"), 0)
        # "fair-trade" contains "ir" too; it is an ESG page, not IR.
        self.assertEqual(score("https://x.com/kr/esg/fair-trade"), 40)
        self.assertGreaterEqual(score("https://x.com/kr/ir/overview"), 80)

    def test_ranking_puts_the_annual_report_page_first(self) -> None:
        links = [
            "https://x.com/kr/business/ess",
            "https://x.com/kr/esg/fair-trade",
            "https://x.com/kr/investors/stock-graph-recent",
            "https://x.com/kr/investors/data-business-report",
            "https://x.com/kr/etc/cs-inquiry",
        ]
        ranked = CompanyResearchTool._rank_section_links(links)
        self.assertEqual(
            ranked[0], "https://x.com/kr/investors/data-business-report"
        )
        self.assertEqual(ranked[-1], "https://x.com/kr/etc/cs-inquiry")


class PdfLinkRankingTest(unittest.TestCase):
    def test_annual_report_beats_other_documents(self) -> None:
        links = [
            "https://x.com/upload/LG_Energy_Solution_2025_ESG_Report_EN.pdf",
            "https://x.com/upload/FY25_LGES_FinancialStatement.pdf",
            "https://x.com/upload/2025_LGES_Annual_Report.pdf",
        ]
        self.assertEqual(
            CompanyResearchTool._rank_pdf_links(links)[0],
            "https://x.com/upload/2025_LGES_Annual_Report.pdf",
        )

    def test_unrelated_and_non_pdf_links_are_ignored(self) -> None:
        links = [
            "https://x.com/upload/product-brochure.pdf",
            "https://x.com/kr/investors/data-business-report",
        ]
        self.assertEqual(CompanyResearchTool._rank_pdf_links(links), [])

    def test_limit_is_respected(self) -> None:
        links = [
            f"https://x.com/upload/{year}_LGES_Annual_Report.pdf"
            for year in (2025, 2024, 2023, 2022)
        ]
        self.assertEqual(len(CompanyResearchTool._rank_pdf_links(links)), PDF_LIMIT)

    def test_document_kind_and_fiscal_year(self) -> None:
        kind = CompanyResearchTool._document_kind
        self.assertEqual(kind("https://x.com/a/2025_LGES_Annual_Report.pdf"), "annual_report")
        self.assertEqual(kind("https://x.com/a/2023_LGES_Business_Report.pdf"), "business_report")
        self.assertEqual(kind("https://x.com/a/FY25_LGES_FinancialStatement.pdf"), "financial_statement")
        self.assertEqual(kind("https://x.com/a/2025_ESG_Report_EN.pdf"), "esg_report")
        self.assertEqual(
            CompanyResearchTool._fiscal_year("https://x.com/a/2025_LGES_Annual_Report.pdf"),
            "2025",
        )


class PdfDetectionTest(unittest.TestCase):
    """A PDF must never be parsed as HTML."""

    def test_detection_by_content_type_and_suffix(self) -> None:
        is_pdf = CompanyResearchTool._is_pdf
        self.assertTrue(is_pdf("https://x.com/a.pdf", "text/html"))
        self.assertTrue(is_pdf("https://x.com/download?id=7", "application/pdf"))
        self.assertFalse(is_pdf("https://x.com/kr/investors", "text/html"))

    def test_raw_pdf_source_is_detected_and_rejected(self) -> None:
        looks = CompanyResearchTool._looks_like_pdf_source
        # The exact shape that reached _page_evidence before this change.
        self.assertTrue(
            looks("%PDF-1.7 4 0 obj (Identity) endobj 5 0 obj << /Filter /FlateDecode")
        )
        self.assertTrue(looks("  %PDF-1.7 %���� 1 0 obj < >/Metadata 678 0 R"))

    def test_extracted_document_text_is_not_flagged(self) -> None:
        self.assertFalse(
            CompanyResearchTool._looks_like_pdf_source(
                "사 업 보 고 서 (제 6 기) 사업연도 2025년 01월 01일 부터 2025년 12월 31일 까지 "
                "회 사 명 :주식회사 엘지에너지솔루션"
            )
        )


class SectionSelectionTest(unittest.TestCase):
    """P0.5: pick the pages that actually describe the company."""

    TOC = (
        "목 차 【 대표이사 등의 확인 】 I. 회사의 개요 1. 회사의 개요 2. 회사의 연혁 "
        "II. 사업의 내용 1. 사업의 개요 2. 주요 제품 및 서비스 "
        "........................... 1 ........................... 4"
    )
    BUSINESS = (
        "II. 사업의 내용 1. 사업의 개요 당사는 지속 가능한 미래를 위한 배터리 기술 개발을 "
        "핵심 전략으로 삼고 EV, ESS, IT 기기용 배터리를 생산하고 있습니다."
    )
    FACTORY = (
        "3) 생산능력, 생산실적 및 가동률 사업부문 품목 사업소 생산 능력 생산 실적 평균 가동률 "
        "에너지솔루션 EV용 배터리, ESS용 배터리 생산 공장 가동률"
    )
    INVEST = (
        "4) 투자 현황 및 신규 투자 계획 해외 투자와 증설, 합작 투자 계획을 설명합니다. "
        "capacity expansion overseas investment"
    )

    def test_korean_headings_match_even_when_spaced(self) -> None:
        # PDF extraction renders some headings with a space between characters.
        spaced = "3) 생 산 능 력, 생산실적 및 가동률"
        self.assertGreater(
            CompanyResearchTool._page_section_scores(spaced).get("manufacturing", 0), 0
        )

    def test_front_matter_is_detected(self) -> None:
        self.assertTrue(CompanyResearchTool._is_front_matter(self.TOC))
        self.assertFalse(CompanyResearchTool._is_front_matter(self.BUSINESS))

    def test_table_of_contents_is_not_selected(self) -> None:
        pages = [self.TOC, self.BUSINESS, self.FACTORY]
        chosen = CompanyResearchTool._select_sections(pages)
        self.assertIn(("business", 1), chosen)
        self.assertNotIn(1, [index for _, index in chosen if index == 0])

    def test_sections_are_not_repeated_across_documents(self) -> None:
        pages = [self.TOC, self.BUSINESS, self.FACTORY, self.INVEST]
        first = CompanyResearchTool._select_sections(pages)
        covered = {section for section, _ in first}
        second = CompanyResearchTool._select_sections(pages, exclude=covered)
        self.assertFalse(covered & {section for section, _ in second})

    def test_language_detection(self) -> None:
        detect = CompanyResearchTool._detect_language
        self.assertEqual(detect("사업보고서 제 6 기 회사의 개요"), "ko")
        self.assertEqual(detect("Annual report business overview"), "en")
        self.assertEqual(detect("年度报告 公司概况 主要产品"), "zh")
        self.assertEqual(detect("12345 %%%"), "unknown")


class DocumentComplementTest(unittest.TestCase):
    """Two annual reports must not both be the same document type."""

    LINKS = [
        "https://x.com/a/2025_LGES_Annual_Report.pdf",
        "https://x.com/a/2024_LGES_Annual_Report[0].pdf",
        "https://x.com/a/LG_Energy_Solution_2025_ESG_Report_EN[2].pdf",
        "https://x.com/a/FY25_LGES_FinancialStatement.pdf",
    ]

    def test_secondary_document_prefers_other_types(self) -> None:
        selected = CompanyResearchTool._select_pdf_links(self.LINKS)
        self.assertIn("2025_LGES_Annual_Report.pdf", selected[0])
        kinds = {CompanyResearchTool._document_kind(url) for url in selected}
        self.assertNotEqual(kinds, {"annual_report"})

    def test_english_document_is_preferred_for_the_second_slot(self) -> None:
        self.assertEqual(
            CompanyResearchTool._english_hint(
                "https://x.com/a/LG_Energy_Solution_2025_ESG_Report_EN[2].pdf"
            ),
            1,
        )
        self.assertEqual(
            CompanyResearchTool._english_hint("https://x.com/a/2025_LGES_Annual_Report.pdf"),
            0,
        )

    def test_falls_back_to_a_second_annual_report(self) -> None:
        links = [
            "https://x.com/a/2025_LGES_Annual_Report.pdf",
            "https://x.com/a/2024_LGES_Annual_Report.pdf",
        ]
        selected = CompanyResearchTool._select_pdf_links(links)
        self.assertEqual(len(selected), 2)


if __name__ == "__main__":
    unittest.main()
