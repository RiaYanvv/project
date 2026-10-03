from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Protocol

from .knowledge import (
    KnowledgeChunk,
    KnowledgeRepository,
    cosine_similarity,
    hashed_embedding,
    tokenize,
)
from .schemas import RetrievalQuery, RetrievedEvidence
from .web_search import WebSearchTool


class RetrievalProvider(Protocol):
    def search(self, query: RetrievalQuery) -> list[RetrievedEvidence]:
        """Return evidence ordered by relevance."""


class MockRetrievalProvider:
    def __init__(self, evidence_path: Path):
        self.evidence_path = evidence_path
        self._records = self._load()

    def _load(self) -> list[RetrievedEvidence]:
        raw = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        return [RetrievedEvidence.model_validate(item) for item in raw]

    def search(self, query: RetrievalQuery) -> list[RetrievedEvidence]:
        query_terms = self._terms(
            " ".join(
                [
                    query.industry,
                    *query.products,
                    query.home_country,
                    *query.production_countries,
                    *query.target_markets,
                    query.decision_question,
                    *query.restrictions,
                ]
            )
        )
        scored: list[RetrievedEvidence] = []

        for record in self._records:
            haystack = self._terms(
                " ".join(
                    [
                        record.title,
                        record.topic,
                        record.content,
                        record.publisher,
                        record.country_region,
                    ]
                )
            )
            overlap = len(query_terms.intersection(haystack))
            topic_bonus = 0
            if record.topic in query.restrictions:
                topic_bonus += 18
            if record.country_region in {
                *query.production_countries,
                *query.target_markets,
                query.home_country,
            }:
                topic_bonus += 12
            authority_bonus = {"A": 12, "B": 8, "C": 4, "D": 0}[
                record.authority_level
            ]
            score = min(
                100,
                record.relevance_score // 2
                + overlap * 7
                + topic_bonus
                + authority_bonus,
            )
            scored.append(record.model_copy(update={"relevance_score": score}))

        scored.sort(key=lambda item: (item.relevance_score, item.authority_level), reverse=True)
        return scored[: query.limit]

    @staticmethod
    def _terms(value: str) -> set[str]:
        normalized = value.lower().replace("_", " ").replace("-", " ")
        return {
            token
            for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", normalized)
            if len(token) >= 2
        }


class HybridRetrievalProvider:
    def __init__(
        self,
        repository: KnowledgeRepository,
        fallback: RetrievalProvider | None = None,
        web_search: WebSearchTool | None = None,
        web_search_limit: int = 3,
    ):
        self.repository = repository
        self.fallback = fallback
        self.web_search = web_search
        self.web_search_limit = web_search_limit

    def search(self, query: RetrievalQuery) -> list[RetrievedEvidence]:
        query_text = self._query_text(query)
        query_tokens = tokenize(query_text)
        repository_ready = bool(self.repository.stats().get("ready"))
        chunks = self.repository.search_candidates(query_tokens, limit=800)
        if not chunks and not repository_ready:
            if self.fallback is None:
                raise RuntimeError(
                    "RAG knowledge base is empty or unavailable. "
                    "Run backend/scripts/ingest_dataset.py before starting the Agent."
                )
            return self.fallback.search(query)

        query_embedding = hashed_embedding(query_text)
        token_counts = [Counter(tokenize(chunk.content)) for chunk in chunks]
        document_frequency = Counter()
        for counts in token_counts:
            document_frequency.update(counts.keys())

        bm25_scores = [
            self._bm25(
                query_tokens=query_tokens,
                document_tokens=counts,
                document_frequency=document_frequency,
                document_count=len(chunks),
                average_length=sum(sum(item.values()) for item in token_counts)
                / max(1, len(token_counts)),
            )
            for counts in token_counts
        ]
        max_bm25 = max(bm25_scores, default=0.0) or 1.0
        country_terms = {
            *query.production_countries,
            *query.target_markets,
            query.home_country,
        }

        authority_scores = {
            "S": 1.0,
            "A+": 0.85,
            "A": 0.70,
            "B+": 0.50,
            "B": 0.40,
            "C": 0.25,
            "D": 0.10,
        }

        # Query-specific concepts used for direct relevance reranking.
        industry_concepts = {
            "battery_ev": {
                "battery",
                "batteries",
                "electric vehicle",
                "electric vehicles",
                "ev",
                "lithium",
                "cell",
                "cells",
                "cathode",
                "anode",
                "850760",
                "870380",
            },
            "semiconductor": {
                "semiconductor",
                "semiconductors",
                "chip",
                "chips",
                "integrated circuit",
                "wafer",
            },
            "electronics": {
                "electronics",
                "electronic",
                "components",
            },
            "optoelectronics": {
                "optoelectronics",
                "photonics",
                "optical",
            },
            "industrial_equipment": {
                "industrial equipment",
                "machinery",
                "machine",
            },
        }

        restriction_concepts = {
            "tariff_pressure": {
                "tariff",
                "tariffs",
                "section 301",
                "section 232",
                "trade remedy",
                "customs",
                "duty",
                "duties",
                "circumvention",
                "anti-circumvention",
                "origin",
                "rules of origin",
                "transshipment",
            },
            "export_controls": {
                "export control",
                "export controls",
                "entity list",
                "license",
                "licensing",
            },
            "sanctions_concerns": {
                "sanction",
                "sanctions",
                "restricted party",
            },
            "local_regulation": {
                "local content",
                "localization",
                "domestic content",
            },
            "supplier_dependency": {
                "supplier",
                "supply chain",
                "dependency",
                "concentration",
            },
            "labor_cost_increase": {
                "labor cost",
                "labour cost",
                "wage",
                "wages",
            },
            "logistics_problems": {
                "logistics",
                "shipping",
                "freight",
                "port",
                "transport",
            },
        }

        country_aliases = {
            "CN": {"china", "chinese"},
            "US": {"united states", "u.s.", "u.s", "american", "america"},
            "VN": {"vietnam", "vietnamese"},
            "TH": {"thailand", "thai"},
            "MY": {"malaysia", "malaysian"},
            "MX": {"mexico", "mexican"},
            "IN": {"india", "indian"},
            "ID": {"indonesia", "indonesian"},
            "EU": {"european union", "eu"},
        }

        garbage_patterns = (
            "these cookies allow us",
            "cookie policy",
            "privacy policy",
            "accept all cookies",
            "manage cookies",
            "javascript is disabled",
            "enable javascript",
            "_msttexthash",
            "_msthidden",
            "_msthash",
            "skip to main content",
        )

        wanted_industry = industry_concepts.get(query.industry, set())

        wanted_policy: set[str] = set()
        for restriction in query.restrictions:
            wanted_policy.update(
                restriction_concepts.get(restriction, set())
            )

        wanted_countries: set[str] = set()
        for country in country_terms:
            wanted_countries.update(
                country_aliases.get(country, {country.lower()})
            )

        scored: list[tuple[float, KnowledgeChunk]] = []

        for chunk, bm25_score, token_count in zip(
            chunks, bm25_scores, token_counts
        ):
            document_length = sum(token_count.values())

            if document_length < 5:
                continue

            text = " ".join(
                [
                    chunk.title or "",
                    chunk.topic or "",
                    chunk.content or "",
                    chunk.publisher or "",
                    chunk.country_region or "",
                ]
            ).lower()

            # Reject obvious HTML/UI/cookie garbage.
            if any(pattern in text for pattern in garbage_patterns):
                continue

            if query.industry == "battery_ev":
                battery_terms = (
                    "battery",
                    "batteries",
                    "lithium",
                    "battery cell",
                    "battery cells",
                    "lithium-ion cell",
                    "cathode",
                    "anode",
                    "electric vehicle",
                    "ev battery",
                )
                solar_pattern = re.compile(
                    r"\b(solar|photovoltaic|silicon wafer|solar panel)\b",
                    flags=re.IGNORECASE,
                )
                if solar_pattern.search(text) and not any(
                    term in text for term in battery_terms
                ):
                    continue

            vector_score = max(
                0.0,
                cosine_similarity(query_embedding, chunk.embedding),
            )

            lexical = bm25_score / max_bm25
            authority = authority_scores.get(
                chunk.authority_level,
                0.30,
            )

            industry_hits = sum(
                1 for term in wanted_industry if term in text
            )
            policy_hits = sum(
                1 for term in wanted_policy if term in text
            )
            country_hits = sum(
                1 for term in wanted_countries if term in text
            )

            industry_match = min(1.0, industry_hits / 2)
            policy_match = min(1.0, policy_hits / 2)
            country_match = min(1.0, country_hits / 2)

            topic_match = (
                1.0
                if chunk.topic in query.restrictions
                else 0.0
            )

            # Direct decision relevance should dominate authority.
            final_score = (
                0.30 * lexical
                + 0.18 * vector_score
                + 0.12 * authority
                + 0.16 * industry_match
                + 0.14 * policy_match
                + 0.07 * country_match
                + 0.03 * topic_match
            )

            # Strong bonus when evidence simultaneously matches
            # industry + policy.
            if industry_hits and policy_hits:
                final_score += 0.10

            # Strongest signal for cross-border policy questions:
            # industry + policy + relevant geography.
            if industry_hits and policy_hits and country_hits:
                final_score += 0.08

            # Penalize generic high-authority material that does not
            # directly match the decision problem.
            if wanted_industry and industry_hits == 0:
                final_score -= 0.12

            if wanted_policy and policy_hits == 0:
                final_score -= 0.10

            # A document that matches neither industry nor policy
            # should almost never occupy a scarce Top-K slot.
            if (
                wanted_industry
                and wanted_policy
                and industry_hits == 0
                and policy_hits == 0
            ):
                final_score -= 0.15

            scored.append((max(0.0, final_score), chunk))

        scored.sort(
            key=lambda item: (
                item[0],
                authority_scores.get(
                    item[1].authority_level,
                    0.30,
                ),
            ),
            reverse=True,
        )

        selected: list[RetrievedEvidence] = []
        source_counts: Counter[str] = Counter()
        live_budget = self.web_search_limit if self.web_search else 0
        local_limit = max(1, query.limit - live_budget)

        for raw_score, chunk in scored:
            if source_counts[chunk.source_id] >= 1:
                continue

            selected.append(
                RetrievedEvidence(
                    evidence_id=f"EVD-{chunk.chunk_id}",
                    title=f"{chunk.title} - {chunk.content[:72]}...",
                    source_type=chunk.source_type,
                    publisher=chunk.publisher,
                    country_region=chunk.country_region,
                    publication_date=chunk.publication_date,
                    url=chunk.url,
                    authority_level=chunk.authority_level,  # type: ignore[arg-type]
                    topic=chunk.topic,
                    document_path=chunk.document_path,
                    document_url=f"/api/v1/evidence/EVD-{chunk.chunk_id}/document",
                    content=chunk.content,
                    relevance_score=max(
                        1, min(100, round(raw_score * 100))
                    ),
                    is_mock=chunk.is_mock,
                    evidence_scope="policy",
                )
            )

            source_counts[chunk.source_id] += 1

            if len(selected) >= local_limit:
                break

        if self.web_search and live_budget:
            web_items = self.web_search.search(
                self._web_query_text(query),
                limit=min(
                    live_budget,
                    query.limit - len(selected),
                ),
            )
            selected.extend(web_items)

        return selected[: query.limit]

    @staticmethod
    def _query_text(query: RetrievalQuery) -> str:
        return " ".join(
            [
                query.industry,
                *query.products,
                query.company_name,
                *query.aliases,
                query.home_country,
                *query.production_countries,
                *query.target_markets,
                query.decision_question,
                *query.restrictions,
            ]
        )

    @staticmethod
    def _web_query_text(query: RetrievalQuery) -> str:
        restriction_terms = {
            "tariff_pressure": "tariffs trade policy",
            "export_controls": "export controls",
            "sanctions_concerns": "sanctions compliance",
            "local_regulation": "local content regulation",
            "supplier_dependency": "supply chain resilience",
            "labor_cost_increase": "manufacturing labor costs",
            "logistics_problems": "logistics disruption",
        }
        industry_terms = {
            "battery_ev": "battery electric vehicle supply chain",
            "semiconductor": "semiconductor supply chain",
            "electronics": "electronics supply chain",
            "optoelectronics": "optoelectronics supply chain",
            "industrial_equipment": "industrial equipment supply chain",
        }
        country_terms = {
            "CN": "China",
            "VN": "Vietnam",
            "US": "United States",
            "EU": "European Union",
            "ID": "Indonesia",
            "IN": "India",
            "TH": "Thailand",
            "MY": "Malaysia",
            "MX": "Mexico",
        }
        parts = [
            restriction_terms.get(restriction)
            for restriction in query.restrictions
            if restriction_terms.get(restriction)
        ]
        company_terms = [
            query.company_name,
            *query.aliases,
        ]
        if any(company_terms):
            parts.append(" ".join(dict.fromkeys(company_terms)))
        parts.append(
            industry_terms.get(
                query.industry,
                f"{query.industry.replace('_', ' ')} supply chain",
            )
        )
        parts.extend(
            country_terms.get(country, country)
            for country in [
                query.home_country,
                *query.production_countries,
                *query.target_markets,
            ]
        )
        parts.append("geopolitical risk trade policy")
        return " ".join(dict.fromkeys(part for part in parts if part))

    @staticmethod
    def _bm25(
        query_tokens: list[str],
        document_tokens: Counter[str],
        document_frequency: Counter[str],
        document_count: int,
        average_length: float,
    ) -> float:
        k1 = 1.5
        b = 0.75
        document_length = sum(document_tokens.values())
        score = 0.0
        for token in query_tokens:
            frequency = document_tokens.get(token, 0)
            if not frequency:
                continue
            df = document_frequency.get(token, 0)
            idf = math.log(1 + (document_count - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (
                1 - b + b * document_length / max(1.0, average_length)
            )
            score += idf * frequency * (k1 + 1) / denominator
        return score
