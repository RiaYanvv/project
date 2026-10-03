from __future__ import annotations

import hashlib
import html
import re
from typing import Any

import httpx

from .schemas import RetrievedEvidence


USER_AGENT = (
    "GeopoliticalRiskResearchBot/0.3 "
    "(mailto:risk_a_lab@126.com; public research use)"
)


class WebSearchTool:
    def __init__(self, enabled: bool = True, timeout: float = 25.0):
        self.enabled = enabled
        self.timeout = timeout

    def search(self, query: str, limit: int = 3) -> list[RetrievedEvidence]:
        if not self.enabled or not query.strip():
            return []

        items: list[RetrievedEvidence] = []
        items.extend(self._search_federal_register(query, limit=limit))
        if len(items) < limit:
            items.extend(
                self._search_crossref(query, limit=limit - len(items))
            )

        deduplicated: list[RetrievedEvidence] = []
        seen: set[str] = set()
        for item in items:
            identity = item.url or item.title
            if identity in seen:
                continue
            seen.add(identity)
            deduplicated.append(item)
            if len(deduplicated) >= limit:
                break
        return deduplicated

    def _search_federal_register(
        self, query: str, limit: int
    ) -> list[RetrievedEvidence]:
        params = {
            "per_page": max(1, min(limit, 20)),
            "order": "newest",
            "conditions[term]": query,
        }
        try:
            response = self._get(
                "https://www.federalregister.gov/api/v1/documents.json",
                params=params,
            )
            results = response.json().get("results", [])
        except (httpx.HTTPError, ValueError, TypeError):
            return []

        evidence: list[RetrievedEvidence] = []
        for item in results:
            url = item.get("html_url") or item.get("pdf_url")
            title = str(item.get("title") or "").strip()
            if not url or not title:
                continue
            document_type = str(item.get("type") or "official document")
            abstract = self._clean_html(
                item.get("abstract") or item.get("excerpts") or ""
            )
            agencies = item.get("agencies") or []
            agency_names = ", ".join(
                str(agency.get("name"))
                for agency in agencies
                if isinstance(agency, dict) and agency.get("name")
            )
            content = " ".join(
                part
                for part in [
                    f"Federal Register document type: {document_type}.",
                    f"Agency: {agency_names}." if agency_names else "",
                    abstract,
                ]
                if part
            )
            relevance_score = self._relevance_score(
                f"{title} {abstract} {agency_names}",
                self._english_terms(query),
                source_type="policy",
            )
            if relevance_score < 45:
                continue

            evidence.append(
                self._evidence(
                    title=title,
                    url=url,
                    publisher=agency_names or "US Federal Register",
                    publication_date=str(
                        item.get("publication_date") or "unknown"
                    ),
                    authority_level=(
                        "A"
                        if document_type.lower() in {"rule", "proposed rule"}
                        else "B"
                    ),
                    source_type="live_policy",
                    topic="live_policy",
                    content=content or title,
                    country_region="US",
                    relevance_score=relevance_score,
                )
            )
            if len(evidence) >= limit:
                break
        return evidence

    def _search_crossref(
        self, query: str, limit: int
    ) -> list[RetrievedEvidence]:
        query_terms = self._english_terms(query)
        search_query = " ".join(query_terms[:30]) or query[:250]
        params = {
            "query.bibliographic": search_query,
            "rows": max(1, min(limit, 20)),
            "select": (
                "DOI,title,author,publisher,issued,abstract,"
                "container-title,URL,type"
            ),
        }
        try:
            response = self._get(
                "https://api.crossref.org/works",
                params=params,
            )
            results = response.json().get("message", {}).get("items", [])
        except (httpx.HTTPError, ValueError, TypeError):
            return []

        evidence: list[RetrievedEvidence] = []
        for item in results:
            title = self._first_text(item.get("title"))
            url = item.get("URL")
            if not title or not url:
                continue
            issued = item.get("issued", {}).get("date-parts", [[]])
            publication_date = (
                "-".join(str(part).zfill(2) for part in issued[0])
                if issued and issued[0]
                else "unknown"
            )
            publisher = str(item.get("publisher") or "Crossref")
            authors = self._authors(item.get("author"))
            journal = self._first_text(item.get("container-title"))
            abstract = self._clean_html(item.get("abstract") or "")
            relevance_score = self._relevance_score(
                f"{title} {abstract} {journal} {publisher}",
                query_terms,
                source_type="research",
            )
            if relevance_score < 65:
                continue
            content = " ".join(
                part
                for part in [
                    f"Type: {item.get('type') or 'research work'}.",
                    f"Authors: {authors}." if authors else "",
                    f"Venue: {journal}." if journal else "",
                    abstract,
                ]
                if part
            )
            evidence.append(
                self._evidence(
                    title=title,
                    url=url,
                    publisher=publisher,
                    publication_date=publication_date,
                    authority_level="B",
                    source_type="live_research",
                    topic="live_research",
                    content=content or title,
                    country_region="GLOBAL",
                    relevance_score=relevance_score,
                )
            )
            if len(evidence) >= limit:
                break
        return evidence

    def _get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        ) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response

    @staticmethod
    def _evidence(
        *,
        title: str,
        url: str,
        publisher: str,
        publication_date: str,
        authority_level: str,
        source_type: str,
        topic: str,
        content: str,
        country_region: str,
        relevance_score: int,
    ) -> RetrievedEvidence:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10].upper()
        return RetrievedEvidence(
            evidence_id=f"EVD-WEB-{digest}",
            title=title[:300],
            source_type=source_type,
            publisher=publisher[:200],
            country_region=country_region,
            publication_date=publication_date,
            url=url,
            authority_level=authority_level,  # type: ignore[arg-type]
            topic=topic,
            document_path=None,
            content=content[:3000],
            relevance_score=relevance_score,
            is_mock=False,
            evidence_scope="policy",
        )

    @staticmethod
    def _clean_html(value: Any) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _first_text(value: Any) -> str:
        if isinstance(value, list) and value:
            return str(value[0]).strip()
        return str(value or "").strip()

    @staticmethod
    def _authors(value: Any) -> str:
        if not isinstance(value, list):
            return ""
        names = []
        for author in value[:5]:
            if not isinstance(author, dict):
                continue
            name = " ".join(
                part
                for part in [author.get("given"), author.get("family")]
                if part
            )
            if name:
                names.append(name)
        return ", ".join(names)
    
    @staticmethod
    def _english_terms(query: str) -> list[str]:
        stopwords = {
            "and",
            "are",
            "for",
            "from",
            "into",
            "not",
            "the",
            "this",
            "with",
            "whether",
            "should",
            "could",
            "would",
            "以及",
            "是否",
            "企业",
        }

        terms = [
            token.lower()
            for token in re.findall(
                r"[A-Za-z][A-Za-z0-9-]{2,}",
                query,
            )
            if token.lower() not in stopwords
        ]

        return list(dict.fromkeys(terms))

    @staticmethod
    def _relevance_score(
        content: str,
        query_terms: list[str],
        source_type: str,
    ) -> int:
        normalized = content.lower()

        if not query_terms:
            return 0

        matched_terms = {
            term
            for term in query_terms
            if term in normalized
        }

        overlap_ratio = len(matched_terms) / max(1, len(query_terms))

        policy_terms = {
            "tariff",
            "tariffs",
            "trade",
            "section 301",
            "export control",
            "export controls",
            "restriction",
            "restrictions",
            "sanction",
            "sanctions",
            "anti-dumping",
            "antidumping",
            "countervailing",
            "circumvention",
            "customs",
            "origin",
            "rules of origin",
            "local content",
            "subsidy",
            "subsidies",
            "industrial policy",
            "supply chain",
            "geopolitical",
        }

        industry_terms = {
            "battery",
            "batteries",
            "electric vehicle",
            "electric vehicles",
            "ev",
            "lithium",
            "graphite",
            "nickel",
            "cobalt",
            "critical mineral",
            "critical minerals",
            "automotive",
            "vehicle",
            "vehicles",
        }

        geography_terms = {
            "china",
            "chinese",
            "united states",
            "u.s.",
            "us",
            "vietnam",
            "vietnamese",
            "thailand",
            "malaysia",
            "indonesia",
            "mexico",
            "european union",
            "eu",
        }

        policy_hits = sum(
            1 for term in policy_terms if term in normalized
        )
        industry_hits = sum(
            1 for term in industry_terms if term in normalized
        )
        geography_hits = sum(
            1 for term in geography_terms if term in normalized
        )

        score = 20 + round(overlap_ratio * 35)

        score += min(15, policy_hits * 3)
        score += min(15, industry_hits * 3)
        score += min(10, geography_hits * 2)

        if source_type == "policy":
            score += 5

        if policy_hits and industry_hits:
            score += 8

        if policy_hits and industry_hits and geography_hits:
            score += 7

        if source_type == "research":
            if industry_hits and policy_hits == 0:
                score -= 15

            if policy_hits and industry_hits == 0:
                score -= 8

        return max(0, min(100, score))
