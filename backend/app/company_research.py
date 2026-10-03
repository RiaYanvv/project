from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .schemas import CompanyInput, RetrievedEvidence


WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
WIKIPEDIA_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


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
                website_item = self._website_evidence(website, company)
                if website_item:
                    items.append(website_item)
        return items

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
                    headers={"User-Agent": "LocusCompanyResearch/1.0"},
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
                    headers={"User-Agent": "LocusCompanyResearch/1.0"},
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
            publication_date=inception or "unknown",
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
                    headers={"User-Agent": "LocusCompanyResearch/1.0"},
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
    ) -> RetrievedEvidence | None:
        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "LocusCompanyResearch/1.0"},
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
        return RetrievedEvidence(
            evidence_id=f"EVD-COMPANY-WEB-{digest}",
            title=f"Official website: {company.company_name}",
            source_type="company_website",
            publisher=str(response.url.host),
            country_region=company.home_country,
            publication_date="unknown",
            url=url,
            authority_level="B",
            topic="company_overview",
            content=text[:8000],
            relevance_score=78,
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
                    headers={"User-Agent": "LocusCompanyResearch/1.0"},
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
