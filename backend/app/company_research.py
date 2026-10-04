from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .schemas import CompanyInput, RetrievedEvidence


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
WIKIPEDIA_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

# Company-level facts live on a handful of corporate pages. The links are read
# from the homepage rather than guessed, and only a few are followed, so this
# stays a small fetch rather than a crawler.
SECTION_TERMS = (
    "about", "company", "profile", "overview", "corporate",
    "product", "business", "solution", "technology", "brand",
    "sustainab", "esg", "investor", "responsib",
)
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
        if not items:
            # Wikidata is the preferred entry point, but a single upstream failure
            # used to leave the profile with no company evidence at all. Falling
            # back to Wikipedia by name keeps the stage useful.
            for name in names[:3]:
                wikipedia_item = self._wikipedia_evidence(name, company)
                if wikipedia_item:
                    items.append(wikipedia_item)
                    break
        return items

    def _official_site_evidence(
        self,
        base_url: str,
        company: CompanyInput,
        limit: int = RELATED_PAGE_LIMIT,
    ) -> list[RetrievedEvidence]:
        """Homepage plus a few real internal pages discovered from its links.

        Guessing paths such as /about does not work on most corporate sites —
        they 404 or block — so the section links are read from the homepage.
        """
        homepage = self._fetch_page(base_url)
        if homepage is None:
            return []
        final_url, text, links = homepage
        items: list[RetrievedEvidence] = []
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
            page_url, page_text, _ = fetched
            if len(page_text) < 120:
                continue
            label = page_url.rstrip("/").rsplit("/", 1)[-1] or "page"
            items.append(self._page_evidence(page_url, company, page_text, label[:24]))
        return items[: limit + 1]

    def _rank_section_links(self, links: list[str]) -> list[str]:
        """Prefer the links most likely to carry company-level facts."""

        def score(url: str) -> tuple[int, int]:
            lowered = url.lower()
            matched = not any(term in lowered for term in SECTION_TERMS)
            return (matched, len(url))

        return sorted(dict.fromkeys(links), key=score)[:RELATED_PAGE_ATTEMPTS]

    def _fetch_page(
        self, url: str, timeout: float | None = None
    ) -> tuple[str, str, list[str]] | None:
        try:
            with httpx.Client(
                timeout=timeout or self.timeout,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
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
