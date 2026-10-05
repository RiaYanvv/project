from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .crawler import PublicSourceCrawler
from .knowledge import normalize_text
from .schemas import CompanyInput, RetrievedEvidence


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
WIKIPEDIA_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Company-level facts live on a handful of corporate pages. The links are read
# from the homepage rather than guessed, and only a few are followed, so this
# stays a small fetch rather than a crawler.
#
# Ranking is by company-intelligence value, not URL length: the previous
# length-based sort let short marketing paths such as /kr/business/ess outrank
# /kr/investors/data-business-report, so annual reports were never reached.
SECTION_SCORES: tuple[tuple[int, tuple[str, ...]], ...] = (
    (100, ("annual-report", "annual_report", "business-report", "business_report")),
    (90, ("disclosure", "financial", "earnings")),
    # Note: no bare "ir" here — as a substring it matches "cs-inquiry" and
    # "fair-trade". Investor pages are recognised by a whole path segment below.
    (80, ("investor", "investors")),
    (60, ("report", "newsroom", "announce")),
    (50, ("about", "company", "profile", "overview")),
    (40, ("esg", "sustainability", "sustainab")),
    (10, ("product", "business", "solution", "technology", "careers",
          "service", "marketing", "brand")),
)
# "ir" must match a whole path segment: /kr/esg/fair-trade contains the letters
# "ir" but is not an investor page.
IR_PATH_SEGMENTS = frozenset({"ir", "investor", "investors"})

# Filename hints for the PDFs linked from those pages.
PDF_NAME_SCORES: tuple[tuple[int, str], ...] = (
    (100, "annual_report"),
    (95, "annual report"),
    (95, "annualreport"),
    (90, "business_report"),
    (90, "business report"),
    (80, "financial_statement"),
    (80, "financial statement"),
    (78, "financial_report"),
    (78, "financial report"),
    (70, "earnings"),
    (60, "investor_presentation"),
    (60, "investor presentation"),
    (50, "esg_report"),
    (50, "esg report"),
    (50, "sustainability_report"),
    (50, "sustainability report"),
)

# Guard rails: a handful of the most relevant documents per run, nothing bigger
# than a normal report, and no unbounded text in the prompt.
PDF_LIMIT = 2
PDF_MAX_BYTES = 15 * 1024 * 1024
PDF_MAX_CHARS = 20_000
PDF_MIN_CHARS = 400
PDF_TIMEOUT = 30.0
SECTION_PAGE_LIMIT = 3

# P0.5: one PDF is represented by a few high-value sections rather than by its
# first 20,000 characters (which for a 496-page annual report is the cover and
# table of contents). Snippets stay under the 2,400-character prompt cap so the
# whole snippet reaches the model instead of being cut off.
PDF_SNIPPETS_PER_DOC = 3
PDF_SNIPPET_CHARS = 2_200
PDF_MIN_SNIPPET_CHARS = 200

# Section names map to what Company Intelligence needs: business, manufacturing,
# supply chain, markets and investment/expansion. Korean keywords are included
# because the source annual reports are Korean.
PDF_SECTION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "business",
        (
            "business overview", "our business", "business segment",
            "business model", "core business", "value chain", "product portfolio",
            "main products", "사업의 개요", "사업 개요", "주요 제품", "사업부문",
            "사업의 내용",
        ),
    ),
    (
        "manufacturing",
        (
            "manufacturing", "production capacity", "production facility",
            "plant", "factory", "factories", "production footprint",
            "overseas operation", "생산능력", "생산 설비", "공장", "제조", "생산실적",
        ),
    ),
    (
        "supply_chain",
        (
            "supplier", "raw material", "sourcing", "procurement", "supply chain",
            "원재료", "공급", "조달", "매입",
        ),
    ),
    (
        "markets",
        (
            "target market", "customer", "application", "geographic market",
            "sales by region", "시장", "고객", "판매", "지역별",
        ),
    ),
    (
        "investment",
        (
            "investment", "expansion", "new plant", "joint venture",
            "capacity expansion", "overseas investment", "capital expenditure",
            "투자", "증설", "확장", "합작", "신규 투자",
        ),
    ),
)
PDF_SECTION_ORDER = tuple(name for name, _ in PDF_SECTION_KEYWORDS)

# Total items Company Research may return. Keeping this bounded matters because
# the assessment stores one shared evidence list: company documents must not push
# policy material out of it (P0 acceptance: policy retrieval must keep working).
COMPANY_RESEARCH_BUDGET = 9

# US exchange filings. SEC requires a User-Agent that names the requester and a
# reachable contact address, and blocks placeholder domains, so the lookup is
# only attempted when SEC_CONTACT_EMAIL is configured. Set it to a real address
# to enable US filing evidence; without it the step is skipped silently.
SEC_CONTACT_EMAIL = os.getenv("SEC_CONTACT_EMAIL", "").strip()
# SEC documents the expected form as "Sample Company AdminContact@example.com";
# a parenthesised User-Agent is rejected as an undeclared automated tool.
SEC_USER_AGENT = f"Locus Research {SEC_CONTACT_EMAIL}"
SEC_COMPANY_SEARCH = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_TICKER_MAP = "https://www.sec.gov/files/company_tickers.json"
# Corporate suffixes accepted after a name prefix, so "Tesla" matches
# "Tesla, Inc." but "Apple" does not match "Apple Hospitality".
SEC_NAME_SUFFIXES = (
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
    "limited", "plc", "holdings", "group", "technologies", "technology",
)
# One download per process; the file is ~800 KB.
_SEC_TICKER_CACHE: dict[str, str] | None = None
RELATED_PAGE_LIMIT = 3
RELATED_PAGE_ATTEMPTS = 6
RELATED_PAGE_TIMEOUT = 12.0
USER_AGENT = (
    "LocusBot/1.0 "
    "(https://github.com/RiaYanvv/project; contact@example.org)"
)


class CompanyResearchTool:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def search(
        self,
        company: CompanyInput,
        aliases: list[str] | None = None,
    ) -> list[RetrievedEvidence]:
        names = list(
            dict.fromkeys(
                [
                    company.company_name,
                    *self._known_aliases(company.company_name),
                    *(aliases or []),
                ]
            )
        )
        items: list[RetrievedEvidence] = []
        entity = None
        for name in names[:3]:
            entity = self._find_wikidata_entity(name, company.industry)
            if entity:
                break
        if entity:
            wikidata_item = self._wikidata_evidence(entity, company)
            if wikidata_item:
                items.append(wikidata_item)
            wikipedia_item = self._wikipedia_evidence(
                str(entity.get("label") or company.company_name),
                company,
            )
            if wikipedia_item:
                items.append(wikipedia_item)
            website = self._official_website(entity)
            if website:
                items.extend(self._official_site_evidence(website, company))
            items.extend(self._sec_filing_evidence(company))
        if not items:
            # Wikidata is the preferred entry point, but a single upstream failure
            # used to leave the profile with no company evidence at all. Falling
            # back to Wikipedia by name keeps the stage useful.
            for name in names[:3]:
                wikipedia_item = self._wikipedia_evidence(name, company)
                if wikipedia_item:
                    items.append(wikipedia_item)
                    break
        # Identity first, then the annual-report / ESG sections, then the public
        # pages. The stable sort keeps the original order inside each group.
        ordered = sorted(items, key=self._company_item_priority)
        return ordered[:COMPANY_RESEARCH_BUDGET]

    @staticmethod
    def _company_item_priority(item: RetrievedEvidence) -> int:
        """Order company evidence by how much it tells us about the company."""
        if item.document_format == "pdf":
            return 0
        if item.source_type in {
            "company_registry",
            "company_profile_public",
            "exchange_disclosure",
        }:
            return 1
        return 2

    def _official_site_evidence(
        self,
        base_url: str,
        company: CompanyInput,
        limit: int = SECTION_PAGE_LIMIT,
    ) -> list[RetrievedEvidence]:
        """Homepage, the highest-value sections, and the PDFs they link to.

        Guessing paths such as /about does not work on most corporate sites —
        they 404 or block — so the section links are read from the homepage.
        """
        homepage = self._fetch_page(base_url)
        if homepage is None:
            return []
        final_url, text, links = homepage
        items: list[RetrievedEvidence] = []
        pdf_links: list[str] = [url for url in links if self._is_pdf(url, "")]
        if len(text) >= 120:
            items.append(self._page_evidence(final_url, company, text, "home"))
        for url in self._rank_section_links(links):
            if len(items) > limit:
                break
            fetched = self._fetch_page(
                url, timeout=min(self.timeout, RELATED_PAGE_TIMEOUT)
            )
            if fetched is None:
                continue
            page_url, page_text, page_links = fetched
            if len(page_text) < 120:
                continue
            label = page_url.rstrip("/").rsplit("/", 1)[-1] or "page"
            items.append(self._page_evidence(page_url, company, page_text, label[:24]))
            # Annual reports and filings are linked from these pages, one hop
            # below the homepage.
            pdf_links.extend(
                link for link in page_links if self._is_pdf(link, "")
            )
        covered: set[str] = set()
        for pdf_url in self._select_pdf_links(pdf_links):
            documents = self._pdf_section_evidence(
                pdf_url, company, exclude_sections=covered
            )
            covered.update(item.section for item in documents)
            items.extend(documents)
        return items

    def _sec_filing_evidence(
        self, company: CompanyInput
    ) -> list[RetrievedEvidence]:
        """Recent US exchange filings, when the company is an SEC registrant.

        The company is first resolved to a CIK through the official ticker map.
        SEC's company-search Atom feed returns its company names as
        "ARRAY(0x...)" (a bug on their side), so matching on that feed picked the
        wrong registrant; the ticker map has clean names. Without a confident
        match nothing is returned, because another company's filings would be
        worse than none.
        """
        if not SEC_CONTACT_EMAIL:
            return []
        cik = self._sec_cik(company.company_name)
        if not cik:
            return []
        try:
            with httpx.Client(
                timeout=min(self.timeout, RELATED_PAGE_TIMEOUT),
                follow_redirects=True,
                headers={"User-Agent": SEC_USER_AGENT},
            ) as client:
                response = client.get(
                    SEC_COMPANY_SEARCH,
                    params={
                        "action": "getcompany",
                        "CIK": cik,
                        "type": "",
                        "dateb": "",
                        "owner": "include",
                        "count": "5",
                        "output": "atom",
                    },
                )
                response.raise_for_status()
            # html.parser is always available; the optional lxml XML parser is not
            # installed in this environment.
            document = BeautifulSoup(response.text, "html.parser")
        except Exception:  # noqa: BLE001 - research must never break the run
            return []
        items: list[RetrievedEvidence] = []
        for entry in document.find_all("entry")[:3]:
            link = entry.find("link")
            href = str(link.get("href") or "") if link else ""
            text = entry.get_text(" ", strip=True)
            if not href or not text:
                continue
            digest = hashlib.sha1(href.encode("utf-8")).hexdigest()[:10].upper()
            # "20\d\d" avoids matching the accession number (e.g. 8280-26-06).
            dated = re.search(r"20\d{2}-\d{2}-\d{2}", text)
            filed = dated.group(0) if dated else "unknown"
            accession = re.search(r"\d{10}-\d{2}-\d{6}", text)
            label = (
                f"{accession.group(0)} ({filed})"
                if accession
                else f"filed {filed}"
            )
            items.append(
                RetrievedEvidence(
                    evidence_id=f"EVD-COMPANY-SEC-{digest}",
                    title=f"SEC filing: {label}",
                    source_type="exchange_disclosure",
                    publisher="US SEC EDGAR",
                    country_region="US",
                    publication_date=filed,
                    url=href,
                    authority_level="A",
                    topic="company_filing",
                    content=(
                        f"{text[:400]} Filed with the US Securities and Exchange "
                        f"Commission. Source: {href}"
                    ),
                    relevance_score=90,
                    is_mock=False,
                    evidence_scope="company",
                )
            )
        return items

    @staticmethod
    def _sec_cik(company_name: str) -> str:
        """Resolve a company name to a CIK, or "" when the match is not clear."""
        global _SEC_TICKER_CACHE
        if not SEC_CONTACT_EMAIL:
            return ""
        if _SEC_TICKER_CACHE is None:
            try:
                with httpx.Client(
                    timeout=RELATED_PAGE_TIMEOUT,
                    follow_redirects=True,
                    headers={"User-Agent": SEC_USER_AGENT},
                ) as client:
                    response = client.get(SEC_TICKER_MAP)
                    response.raise_for_status()
                rows = response.json().values()
            except Exception:  # noqa: BLE001 - optional source
                return ""
            _SEC_TICKER_CACHE = {}
            for row in rows:
                title = str(row.get("title") or "")
                cik = str(row.get("cik_str") or "")
                normalized = re.sub(r"[^a-z0-9]", "", title.lower())
                if normalized and cik:
                    _SEC_TICKER_CACHE[normalized] = cik
        wanted = re.sub(r"[^a-z0-9]", "", (company_name or "").lower())
        return CompanyResearchTool._match_cik(wanted, _SEC_TICKER_CACHE)

    @staticmethod
    def _match_cik(wanted: str, mapping: dict[str, str]) -> str:
        """Conservative name → CIK match over normalised company names."""
        wanted = re.sub(r"[^a-z0-9]", "", (wanted or "").lower())
        if not wanted:
            return ""
        if wanted in mapping:
            return mapping[wanted]
        # "tesla" -> "teslainc" is accepted; "apple" -> "applehospitality" is not.
        for normalized, cik in mapping.items():
            if not normalized.startswith(wanted):
                continue
            remainder = normalized[len(wanted):]
            if any(suffix.startswith(remainder) for suffix in SEC_NAME_SUFFIXES):
                return cik
        return ""

    @classmethod
    def _section_score(cls, url: str) -> int:
        """Company-intelligence value of a page URL (higher is better)."""
        segments = [
            segment for segment in urlparse(url).path.lower().split("/") if segment
        ]
        haystack = " ".join(segments)
        score = 0
        for value, keywords in SECTION_SCORES:
            if any(keyword in haystack for keyword in keywords):
                score = max(score, value)
        # A page under an investor path is at least investor-grade, but document
        # endpoints such as .../data-business-report still score higher above.
        if IR_PATH_SEGMENTS & set(segments):
            score = max(score, 80)
        return score

    @classmethod
    def _rank_section_links(cls, links: list[str]) -> list[str]:
        """Prefer the pages most likely to carry company-level facts."""
        return sorted(
            dict.fromkeys(links),
            key=lambda url: (-cls._section_score(url), len(url)),
        )[:RELATED_PAGE_ATTEMPTS]

    @staticmethod
    def _pdf_name_score(url: str) -> int:
        name = urlparse(url).path.rsplit("/", 1)[-1].lower()
        name = re.sub(r"%20|[-_+]", " ", name)
        for score, hint in PDF_NAME_SCORES:
            if hint in name:
                return score
        return 0

    @classmethod
    def _rank_pdf_links(cls, links: list[str], limit: int = PDF_LIMIT) -> list[str]:
        """Only clearly named company documents, best first."""
        ranked = [
            (cls._pdf_name_score(url), url)
            for url in dict.fromkeys(links)
            # A filename hint alone is not enough: an HTML path such as
            # /investors/data-business-report also contains "business report".
            if cls._is_pdf(url, "") and cls._pdf_name_score(url) > 0
        ]
        ranked.sort(key=lambda item: (-item[0], len(item[1])))
        return [url for _, url in ranked[:limit]]

    @staticmethod
    def _document_kind(url: str) -> str:
        name = urlparse(url).path.rsplit("/", 1)[-1].lower()
        name = re.sub(r"%20|[-_+]", " ", name)
        if "annual report" in name or "annualreport" in name:
            return "annual_report"
        if "business report" in name:
            return "business_report"
        if "esg" in name or "sustainability" in name:
            return "esg_report"
        if "financial" in name:
            return "financial_statement"
        if "earnings" in name or "script" in name:
            return "earnings_release"
        return "investor_material"

    @staticmethod
    def _fiscal_year(url: str) -> str:
        match = re.search(r"(20\d{2})", urlparse(url).path)
        return match.group(1) if match else ""

    @staticmethod
    def _pdf_pages(payload: bytes) -> list[str]:
        """Per-page text, so a snippet can say which page it came from.

        pypdf stays the parser (same call as PublicSourceCrawler._extract_pdf);
        this only keeps the page boundaries that _extract_pdf joins away.
        """
        reader = PdfReader(io.BytesIO(payload))
        return [
            normalize_text(page.extract_text() or "") for page in reader.pages
        ]

    @staticmethod
    def _detect_language(text: str) -> str:
        sample = (text or "")[:4000]
        counts = {
            "ko": len(re.findall(r"[\uac00-\ud7af]", sample)),
            "zh": len(re.findall(r"[\u4e00-\u9fff]", sample)),
            "en": len(re.findall(r"[A-Za-z]", sample)),
        }
        best = max(counts, key=lambda key: counts[key])
        return best if counts[best] > 0 else "unknown"

    @classmethod
    def _select_pdf_links(
        cls, links: list[str], limit: int = PDF_LIMIT
    ) -> list[str]:
        """Pick complementary documents, not two copies of the same report.

        Two editions of the same (often non-English) annual report give the model
        little new material, so the first slot is an annual/business report and
        the second prefers English-marked or differently-typed material (ESG,
        investor, earnings, financial statement).
        """
        ranked = cls._rank_pdf_links(links, limit=len(links) or 1)
        if not ranked:
            return []
        primary_kinds = {"annual_report", "business_report"}
        primary = next(
            (url for url in ranked if cls._document_kind(url) in primary_kinds),
            ranked[0],
        )
        selected = [primary]
        if limit <= 1:
            return selected
        others = [
            url
            for url in ranked
            if url != primary and cls._document_kind(url) not in primary_kinds
        ]
        if others:
            # Prefer material that is marked English, so the second document
            # usually adds readable content rather than another Korean edition.
            others.sort(
                key=lambda url: (
                    -cls._english_hint(url),
                    -cls._pdf_name_score(url),
                    len(url),
                )
            )
            secondary = others[0]
        else:
            secondary = next((url for url in ranked if url != primary), None)
        if secondary:
            selected.append(secondary)
        return selected

    @staticmethod
    def _english_hint(url: str) -> int:
        name = unquote(urlparse(url).path.rsplit("/", 1)[-1]).lower()
        return 1 if ("_en" in name or "-en" in name or "english" in name) else 0

    def _fetch_page(
        self, url: str, timeout: float | None = None
    ) -> tuple[str, str, list[str]] | None:
        """Fetch an HTML page.

        Returns None for anything that is not HTML — in particular for PDFs,
        which are handled by _pdf_evidence. Parsing a PDF as HTML yielded 2.9M
        characters of "%PDF-1.7 ... /FlateDecode" that passed the length check and
        would have been stored as evidence content.
        """
        try:
            with httpx.Client(
                timeout=timeout or self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            if self._is_pdf(str(response.url), content_type):
                return None
            if content_type and not self._is_html(content_type):
                return None
            soup = BeautifulSoup(response.text, "html.parser")
            # Read the links before stripping navigation, or the section links
            # would be removed with it.
            links = self._internal_links(soup, str(response.url))
            for element in soup(
                ["script", "style", "noscript", "svg", "nav", "footer"]
            ):
                element.decompose()
            text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        return str(response.url), text, links

    @staticmethod
    def _is_pdf(url: str, content_type: str) -> bool:
        return content_type == "application/pdf" or urlparse(url).path.lower().endswith(
            ".pdf"
        )

    @staticmethod
    def _is_html(content_type: str) -> bool:
        return content_type.startswith("text/") or content_type in {
            "application/xhtml+xml",
        }

    @staticmethod
    def _looks_like_pdf_source(text: str) -> bool:
        """Guard against raw PDF bytes ever reaching evidence content."""
        head = text.lstrip()[:200]
        if head.startswith("%PDF"):
            return True
        return "/FlateDecode" in head or ("obj" in head and "endobj" in head)

    @staticmethod
    def _page_section_scores(page_text: str) -> dict[str, int]:
        """Keyword score per section for one page (longer phrases weigh more).

        Matching is space and punctuation insensitive: PDF extraction renders some
        Korean headings with a space between every character ("사 업 보 고 서"),
        so a plain substring test misses "사업의 내용" and friends.
        """
        lowered = page_text.lower()
        compact = re.sub(r"[^0-9a-z\uac00-\ud7af\u4e00-\u9fff]+", "", lowered)
        scores: dict[str, int] = {}
        for name, keywords in PDF_SECTION_KEYWORDS:
            hits = [
                keyword
                for keyword in keywords
                if keyword in lowered
                or re.sub(r"[^0-9a-z\uac00-\ud7af\u4e00-\u9fff]+", "", keyword)
                in compact
            ]
            if hits:
                scores[name] = sum(len(keyword) for keyword in hits)
        return scores

    @staticmethod
    def _is_front_matter(page_text: str) -> bool:
        """Cover and table-of-contents pages are not company intelligence.

        A contents page lists every section name, so it scores highly on keyword
        matching while saying nothing about the company.
        """
        stripped = page_text.strip()
        if len(stripped) < 60:
            return True
        lowered = stripped.lower()
        if "table of contents" in lowered or "목차" in lowered.replace(" ", ""):
            return True
        return len(re.findall(r"\.{3,}", stripped)) >= 5

    @staticmethod
    def _is_numeric_table(page_text: str) -> bool:
        """Skip financial tables masquerading as narrative sections.

        "투자" appears on 155 pages of the LGES report, including related-party
        investment tables whose extracted text is a jumble of company names and
        figures. Real narrative pages run at a digit ratio around 0.02-0.13 while
        those tables sit above 0.3.
        """
        body = re.sub(r"\s+", "", page_text)
        if not body:
            return True
        return sum(char.isdigit() for char in body) / len(body) > 0.25

    # Suffixes that signal an appendix listing affiliates rather than a narrative
    # section. "투자" matched a page whose only hits were inside entity names such
    # as "LG Chem (China) Investment Co.,Ltd.".
    ENTITY_SUFFIX_PATTERN = re.compile(
        r"(?:co\.,?\s*ltd|ltd\.?|inc\.?|gmbh|sp\.\s*z\s*o\.?o|pvt\.?|s\.a\.|corp\.?|limited)",
        re.IGNORECASE,
    )

    @classmethod
    def _is_entity_list(cls, page_text: str) -> bool:
        return len(cls.ENTITY_SUFFIX_PATTERN.findall(page_text)) >= 4

    @classmethod
    def _select_sections(
        cls,
        pages: list[str],
        limit: int = PDF_SNIPPETS_PER_DOC,
        exclude: set[str] | None = None,
    ) -> list[tuple[str, int]]:
        """Pick (section, page index) pairs covering the valuable sections.

        Each page is scored against the section keyword sets; the best page per
        section wins, one section per physical page, and sections with no match
        are skipped rather than filled with the document's opening pages.
        `exclude` carries the sections a previous document already covered, so
        two annual reports widen the coverage instead of repeating each other.
        """
        skip = exclude or set()
        per_page = [cls._page_section_scores(page) for page in pages]
        chosen: list[tuple[str, int]] = []
        used_pages: set[int] = set()
        for section in PDF_SECTION_ORDER:
            if section in skip:
                continue
            best_page = None
            best_score = 0
            for index, scores in enumerate(per_page):
                if index in used_pages or index == 0:
                    continue
                if (
                    cls._is_front_matter(pages[index])
                    or cls._is_numeric_table(pages[index])
                    or cls._is_entity_list(pages[index])
                ):
                    continue
                score = scores.get(section, 0)
                if score > best_score:
                    best_score = score
                    best_page = index
            if best_page is not None:
                chosen.append((section, best_page))
                used_pages.add(best_page)
            if len(chosen) >= limit:
                break
        return chosen

    def _pdf_section_evidence(
        self,
        url: str,
        company: CompanyInput,
        exclude_sections: set[str] | None = None,
    ) -> list[RetrievedEvidence]:
        """Download a company PDF and return one evidence item per valuable section.

        Reuses PublicSourceCrawler._extract_pdf (pypdf) rather than adding another
        parser. Every failure path returns [] so nothing is written: a failed or
        unparseable document must not become evidence, and raw PDF bytes must
        never be stored as content.
        """
        try:
            with httpx.Client(
                timeout=PDF_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
            content_type = (
                response.headers.get("content-type", "").split(";")[0].strip().lower()
            )
            final_url = str(response.url)
            payload = response.content
        except (httpx.HTTPError, ValueError, TypeError):
            return []
        if not self._is_pdf(final_url, content_type):
            return []
        if not payload or len(payload) > PDF_MAX_BYTES:
            return []
        try:
            pages = self._pdf_pages(payload)
        except Exception:  # noqa: BLE001 - a broken PDF must not break the run
            try:
                # Fall back to the shared whole-document extractor.
                pages = [PublicSourceCrawler._extract_pdf(payload)]
            except Exception:  # noqa: BLE001 - optional source
                return []
        pages = [page for page in pages if page.strip()]
        full_text = "\n".join(pages)
        if not full_text or len(full_text.strip()) < PDF_MIN_CHARS:
            return []
        if self._looks_like_pdf_source(full_text):
            return []
        page_count = len(pages)
        language = self._detect_language(full_text)
        kind = self._document_kind(final_url)
        digest = hashlib.sha1(final_url.encode("utf-8")).hexdigest()[:10].upper()
        name = urlparse(final_url).path.rsplit("/", 1)[-1] or final_url
        retrieved_at = datetime.now(timezone.utc).isoformat()
        evidence: list[RetrievedEvidence] = []
        for section, index in self._select_sections(pages, exclude=exclude_sections):
            snippet = pages[index][:PDF_SNIPPET_CHARS].strip()
            if len(snippet) < PDF_MIN_SNIPPET_CHARS:
                continue
            evidence.append(
                RetrievedEvidence(
                    evidence_id=f"EVD-COMPANY-DOC-{digest}-P{index + 1}",
                    title=(
                        f"{company.company_name} — {unquote(name)} "
                        f"· {section} (p.{index + 1})"
                    ),
                    source_type="company_filing",
                    publisher=urlparse(final_url).netloc,
                    country_region=company.home_country,
                    publication_date="unknown",
                    url=final_url,
                    authority_level="A",
                    topic=f"company_{section}",
                    content=snippet,
                    relevance_score=92,
                    is_mock=False,
                    evidence_scope="company",
                    document_format="pdf",
                    document_kind=kind,
                    section=section,
                    page_start=index + 1,
                    page_end=index + 1,
                    language=language,  # type: ignore[arg-type]
                    fiscal_year=self._fiscal_year(final_url),
                    byte_size=len(payload),
                    page_count=page_count,
                    retrieved_at=retrieved_at,
                )
            )
        return evidence

    @staticmethod
    def _internal_links(soup: BeautifulSoup, current_url: str) -> list[str]:
        parsed = urlparse(current_url)
        found: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            absolute = urljoin(current_url, href).split("#")[0].rstrip("/")
            if urlparse(absolute).netloc != parsed.netloc:
                continue
            if absolute == current_url.rstrip("/") or absolute in seen:
                continue
            seen.add(absolute)
            found.append(absolute)
        return found

    @staticmethod
    def _page_evidence(
        url: str,
        company: CompanyInput,
        text: str,
        label: str = "home",
    ) -> RetrievedEvidence:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10].upper()
        return RetrievedEvidence(
            evidence_id=f"EVD-COMPANY-WEB-{digest}",
            title=f"Official website ({label}): {company.company_name}",
            source_type="company_website",
            publisher=urlparse(url).netloc,
            country_region=company.home_country,
            publication_date="unknown",
            url=url,
            authority_level="B",
            topic="company_overview" if label == "home" else f"company_{label}",
            content=text[:8000],
            relevance_score=78 if label == "home" else 72,
            is_mock=False,
            evidence_scope="company",
            is_self_reported=True,
            document_format="html",
            document_kind="web_page",
            byte_size=len(text),
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )
    def _find_wikidata_entity(
        self,
        name: str,
        industry: str,
    ) -> dict[str, Any] | None:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(
                    WIKIDATA_API,
                    params={
                        "action": "wbsearchentities",
                        "search": name,
                        "language": "en",
                        "uselang": "en",
                        "format": "json",
                        "limit": 5,
                    },
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                results = response.json().get("search") or []
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        if not results:
            return None
        industry_terms = {
            "battery_ev": ("battery", "electric vehicle", "ev", "lithium"),
            "semiconductor": ("semiconductor", "chip", "electronics"),
            "electronics": ("electronics", "technology", "manufacturer"),
            "industrial_equipment": ("industrial", "equipment", "manufacturer"),
        }.get(industry, ("company", "manufacturer", "technology"))

        def candidate_score(candidate: dict[str, Any]) -> int:
            text = " ".join(
                [
                    str(candidate.get("label") or ""),
                    str(candidate.get("description") or ""),
                    " ".join(str(item) for item in candidate.get("aliases") or []),
                ]
            ).lower()
            score = 0
            if any(term in text for term in industry_terms):
                score += 20
            if any(term in text for term in ("company", "manufacturer", "corporation")):
                score += 8
            if any(term in text for term in ("peptide", "protein", "enzyme", "gene")):
                score -= 100
            return score

        best = max(results, key=candidate_score)
        if candidate_score(best) <= 0:
            return None
        entity_id = str(best.get("id") or "")
        if not entity_id:
            return None
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(
                    WIKIDATA_ENTITY.format(entity_id=entity_id),
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                payload = response.json()
            entity = payload.get("entities", {}).get(entity_id) or {}
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        return {
            "id": entity_id,
            "label": self._first_language_value(entity.get("labels"))
            or best.get("label"),
            "description": self._first_language_value(entity.get("descriptions"))
            or best.get("description"),
            "aliases": [
                item.get("value", "")
                for item in (entity.get("aliases", {}).get("en") or [])
                if item.get("value")
            ],
            "claims": entity.get("claims") or {},
        }

    @staticmethod
    def _known_aliases(company_name: str) -> list[str]:
        normalized = company_name.lower().replace(" ", "")
        aliases: dict[str, list[str]] = {
            "catl": [
                "Contemporary Amperex Technology",
                "Contemporary Amperex Technology Co. Limited",
                "宁德时代",
            ],
            "小鹏": ["XPeng", "Xpeng Motors", "广州小鹏汽车科技有限公司"],
            "xpeng": ["XPeng", "小鹏汽车"],
            "byd": ["BYD Company", "比亚迪股份有限公司"],
            "比亚迪": ["BYD", "BYD Company"],
        }
        for token, values in aliases.items():
            if token in normalized:
                return values
        return []

    def _wikidata_evidence(
        self,
        entity: dict[str, Any],
        company: CompanyInput,
    ) -> RetrievedEvidence | None:
        claims = entity.get("claims") or {}
        related_ids = [
            self._claim_entity_id(claims, property_id)
            for property_id in ("P159", "P17", "P414")
        ]
        labels = self._entity_labels([item for item in related_ids if item])
        headquarters = labels.get(self._claim_entity_id(claims, "P159"), "")
        country = labels.get(self._claim_entity_id(claims, "P17"), "")
        exchange = labels.get(self._claim_entity_id(claims, "P414"), "")
        website = self._claim_string(claims, "P856")
        ticker = self._claim_string(claims, "P249")
        inception = self._claim_time(claims, "P571")
        employees = self._claim_amount(claims, "P1128")
        content = "\n".join(
            line
            for line in [
                f"Legal entity: {entity.get('label') or company.company_name}",
                f"Description: {entity.get('description') or ''}",
                "Aliases: " + ", ".join(entity.get("aliases") or []),
                f"Headquarters: {headquarters}",
                f"Country: {country}",
                f"Founded: {inception}",
                f"Stock exchange: {exchange}",
                f"Ticker: {ticker}",
                f"Employees: {employees}",
                f"Official website: {website}",
            ]
            if line.split(": ", 1)[-1].strip()
        )
        return RetrievedEvidence(
            evidence_id=f"EVD-COMPANY-WD-{entity['id']}",
            title=f"Wikidata entity: {entity.get('label') or company.company_name}",
            source_type="company_registry",
            publisher="Wikidata",
            country_region=country or company.home_country,
            # The Wikidata inception value is the company's founding year, not a
            # publication date; using it here made the record look stale. The
            # founding year is still carried in the content and the entity.
            publication_date="unknown",
            url=f"https://www.wikidata.org/wiki/{entity['id']}",
            authority_level="B+",
            topic="company_entity",
            content=content,
            relevance_score=96,
            is_mock=False,
            evidence_scope="company",
        )

    def _wikipedia_evidence(
        self,
        title: str,
        company: CompanyInput,
    ) -> RetrievedEvidence | None:
        safe_title = title.strip().replace(" ", "_")
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(
                    WIKIPEDIA_SUMMARY.format(title=safe_title),
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        extract = str(payload.get("extract") or "").strip()
        if len(extract) < 80:
            return None
        digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:10].upper()
        return RetrievedEvidence(
            evidence_id=f"EVD-COMPANY-WP-{digest}",
            title=f"Wikipedia overview: {payload.get('title') or title}",
            source_type="company_profile_public",
            publisher="Wikipedia",
            country_region=company.home_country,
            publication_date="unknown",
            url=(payload.get("content_urls", {}).get("desktop", {}) or {}).get("page"),
            authority_level="C",
            topic="company_overview",
            content=extract,
            relevance_score=82,
            is_mock=False,
            evidence_scope="company",
        )

    def _official_website(self, entity: dict[str, Any]) -> str:
        return self._claim_string(entity.get("claims") or {}, "P856")

    def _website_evidence(
        self,
        url: str,
        company: CompanyInput,
        page_label: str = "",
        timeout: float | None = None,
    ) -> RetrievedEvidence | None:
        try:
            with httpx.Client(
                timeout=timeout or self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
                element.decompose()
            text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        if len(text) < 120:
            return None
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10].upper()
        label = page_label or "home"
        return RetrievedEvidence(
            evidence_id=f"EVD-COMPANY-WEB-{digest}",
            title=f"Official website ({label}): {company.company_name}",
            source_type="company_website",
            publisher=str(response.url.host),
            country_region=company.home_country,
            publication_date="unknown",
            url=url,
            authority_level="B",
            topic="company_overview" if not page_label else f"company_{page_label}",
            content=text[:8000],
            relevance_score=78 if not page_label else 72,
            is_mock=False,
            evidence_scope="company",
            is_self_reported=True,
        )

    def _entity_labels(self, entity_ids: list[str]) -> dict[str, str]:
        ids = list(dict.fromkeys(item for item in entity_ids if item))
        if not ids:
            return {}
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(
                    WIKIDATA_API,
                    params={
                        "action": "wbgetentities",
                        "ids": "|".join(ids),
                        "props": "labels",
                        "languages": "en|zh",
                        "format": "json",
                    },
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                entities = response.json().get("entities") or {}
        except (httpx.HTTPError, ValueError, TypeError):
            return {}
        return {
            entity_id: self._first_language_value(item.get("labels")) or ""
            for entity_id, item in entities.items()
        }

    @staticmethod
    def _first_language_value(values: Any) -> str:
        if not isinstance(values, dict):
            return ""
        for language in ("en", "zh", "zh-cn"):
            value = values.get(language)
            if isinstance(value, dict) and value.get("value"):
                return str(value["value"])
        for value in values.values():
            if isinstance(value, dict) and value.get("value"):
                return str(value["value"])
        return ""

    @staticmethod
    def _claim_entity_id(claims: dict[str, Any], property_id: str) -> str:
        values = claims.get(property_id) or []
        if not values:
            return ""
        mainsnak = values[0].get("mainsnak") or {}
        value = mainsnak.get("datavalue", {}).get("value", {})
        return str(value.get("id") or "") if isinstance(value, dict) else ""

    @staticmethod
    def _claim_string(claims: dict[str, Any], property_id: str) -> str:
        values = claims.get(property_id) or []
        if not values:
            return ""
        mainsnak = values[0].get("mainsnak") or {}
        value = mainsnak.get("datavalue", {}).get("value", "")
        return str(value or "")

    @staticmethod
    def _claim_time(claims: dict[str, Any], property_id: str) -> str:
        value = CompanyResearchTool._claim_string(claims, property_id)
        match = re.search(r"([+-]\d{4,})", value)
        return match.group(1).lstrip("+") if match else value

    @staticmethod
    def _claim_amount(claims: dict[str, Any], property_id: str) -> str:
        values = claims.get(property_id) or []
        if not values:
            return ""
        value = values[0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(value, dict):
            return str(value.get("amount") or "").lstrip("+")
        return ""
