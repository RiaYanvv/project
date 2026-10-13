"""Task 4 — retrieval optimisation layer.

One object that owns the three Task 4 interventions and plugs into
``HybridRetrievalProvider`` through four narrow, opt-in seams:

    expand_terms()   -> 4.2 query enhancement (recall-only candidate expansion)
    filter_chunks()  -> 4.1 metadata filtering (candidate pool)
    adjust_score()   -> 4.1 soft metadata signals (per candidate)
    rerank()         -> 4.3 authority-aware ranking (final ordering)

Every seam is a no-op when the optimizer is absent, so the provider's
existing behaviour (and the Task 2 / Task 3 baselines) is unchanged unless
an optimizer is explicitly attached.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .authority_ranking import DEFAULT_BAND, DEFAULT_AUTHORITY_WEIGHT, banded_rerank
from .metadata_filter import MetadataFilter, parse_filter_spec
from .query_enhancement import expand_terms as _expand_terms


@dataclass
class OptimizationConfig:
    metadata_filter: bool = True
    query_expansion: bool = True
    authority_ranking: bool = True
    band: float = DEFAULT_BAND
    authority_weight: float = DEFAULT_AUTHORITY_WEIGHT


class RetrievalOptimizer:
    def __init__(
        self,
        registry: dict[str, dict] | None = None,
        config: OptimizationConfig | None = None,
    ):
        self.config = config or OptimizationConfig()
        self.metadata_filter = MetadataFilter(registry=registry, enabled=self.config.metadata_filter)
        self._spec_cache: dict[str, object] = {}
        self._lock = threading.Lock()
        # Diagnostics for the evaluation harness: state of the most recent
        # search() call. Diagnostic only — not used for ranking.
        self.last_trace: dict = {}

    # ------------------------------------------------------------------
    def _spec(self, query_text: str, query=None):
        key = query_text or ""
        spec = self._spec_cache.get(key)
        if spec is None:
            company = getattr(query, "company_name", "") or ""
            text = (getattr(query, "decision_question", "") or "") + " " + (query_text or "")
            if company:
                text = f"{company} {text}"
            spec = parse_filter_spec(text)
            if len(self._spec_cache) > 512:
                self._spec_cache.clear()
            self._spec_cache[key] = spec
        return spec

    # ------------------------------------------------------------------
    # 4.2 Query enhancement
    # ------------------------------------------------------------------
    def expand_terms(self, query_text: str, query, base_terms):
        if not self.config.query_expansion:
            return list(base_terms)
        company_hint = getattr(query, "company_name", "") or ""
        try:
            return _expand_terms(query_text, base_terms, company_hint=company_hint)
        except Exception:
            return list(base_terms)

    # ------------------------------------------------------------------
    # 4.1 Metadata filtering
    # ------------------------------------------------------------------
    def filter_chunks(self, chunks, query_text: str, query=None):
        spec = self._spec(query_text, query)
        if not self.config.metadata_filter:
            self.metadata_filter.last_spec = spec
            self.metadata_filter.last_decisions = []
            self.metadata_filter.last_guard_triggered = False
            return chunks
        kept = self.metadata_filter.filter_chunks(chunks, spec=spec, query_text=query_text)
        with self._lock:
            self.last_trace = {
                "spec": spec.as_dict(),
                "pool_before": len(chunks),
                "pool_after": len(kept),
                "recall_guard": self.metadata_filter.last_guard_triggered,
                "decisions": self.metadata_filter.decision_rows(),
            }
        self._current_spec = spec
        return kept

    # ------------------------------------------------------------------
    def adjust_score(self, score: float, chunk, text: str, query_text: str):
        if not self.config.metadata_filter:
            return score
        spec = getattr(self, "_current_spec", None) or self._spec(query_text)
        return self.metadata_filter.adjust_score(score, chunk, spec, text)

    # ------------------------------------------------------------------
    # 4.3 Authority ranking
    # ------------------------------------------------------------------
    def rerank(self, scored):
        if not self.config.authority_ranking:
            return sorted(scored, key=lambda pair: pair[0], reverse=True)
        return banded_rerank(
            scored,
            band=self.config.band,
            authority_weight=self.config.authority_weight,
        )


def build_optimizer_from_env(registry: dict[str, dict] | None = None) -> RetrievalOptimizer | None:
    """Construct an optimizer when RETRIEVAL_OPTIMIZER=1 (default off)."""
    import os

    if os.getenv("RETRIEVAL_OPTIMIZER", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    return RetrievalOptimizer(registry=registry)
