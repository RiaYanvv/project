from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from .company_research import CompanyResearchTool
from .llm import EventCallback, LLMProvider
from .retrieval import RetrievalProvider
from .schemas import (
    Assessment,
    BusinessProfile,
    ChatAnalysis,
    ChatImpact,
    ChatOpeningResponse,
    ChatRequest,
    ChatTurn,
    CompanyInput,
    CompanyEntity,
    CompanyIntelligence,
    CompanyProfile,
    DecisionContext,
    EvidenceLink,
    EvidenceReference,
    FactItem,
    GapUpdate,
    InformationGap,
    LLMCallRecord,
    ManufacturingSite,
    Recommendation,
    RetrievalQuery,
    RetrievedEvidence,
    RiskItem,
    ScenarioScoreBreakdown,
    ScenarioBand,
    ScenarioDimensionAssessment,
    ScenarioResult,
    SUPPLY_CHAIN_ROLE_FALLBACK,
    SUPPLY_CHAIN_ROLE_VALUES,
    SupplyChainRole,
    SupplyChainStage,
    TraceStep,
    utc_now,
)


class AgentService:
    # Normalised risk taxonomy so the frontend radar does not have to guess from
    # free-text categories (UI.md risk overview).
    RISK_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("trade", ("tariff", "trade", "duty", "customs", "import", "export control", "关税", "贸易")),
        ("political", ("geopolitic", "political", "sanction", "conflict", "地缘", "政治")),
        ("supply_chain", ("supplier", "supply", "ecosystem", "dependency", "logistics", "供应", "供应链")),
        ("regulatory", ("regulat", "compliance", "licence", "license", "law", "policy", "监管", "合规", "政策")),
        ("market_access", ("market access", "customer", "rules of origin", "市场准入", "客户")),
        ("operational", ("operat", "implementation", "workforce", "labor", "labour", "cost", "ramp", "运营", "实施", "成本")),
    )

    def __init__(
        self,
        retrieval: RetrievalProvider,
        llm: LLMProvider,
        company_research: CompanyResearchTool | None = None,
    ):
        self.retrieval = retrieval
        self.llm = llm
        self.company_research = company_research

    @classmethod
    def _risk_category_key(cls, name: str, category: str) -> str:
        text = f"{category} {name}".lower()
        if any(
            token in text
            for token in (
                "financial",
                "financing",
                "capital expenditure",
                "capex",
                "融资",
                "资本开支",
            )
        ):
            return "operational"
        for key, tokens in cls.RISK_CATEGORY_KEYWORDS:
            if any(token in text for token in tokens):
                return key
        return "operational"

    # A risk that no evidence supports must not dominate the risk ranking. The
    # level is capped rather than removed because RiskItem requires a severity.
    SEVERITY_WITHOUT_EVIDENCE_CAP = "medium"
    SEVERITY_ORDER = ("low", "medium", "high", "critical")

    @classmethod
    def _cap_severity_without_evidence(
        cls, severity: Any, has_evidence: bool
    ) -> str:
        value = str(severity or "medium").strip().lower()
        if value not in cls.SEVERITY_ORDER:
            value = "medium"
        if has_evidence:
            return value
        cap = cls.SEVERITY_ORDER.index(cls.SEVERITY_WITHOUT_EVIDENCE_CAP)
        return cls.SEVERITY_ORDER[min(cls.SEVERITY_ORDER.index(value), cap)]

    @staticmethod
    def _consume_llm_result(
        payload: Any,
        stage: str,
        llm: LLMProvider,
    ) -> tuple[Any, LLMCallRecord]:
        if not isinstance(payload, dict):
            return payload, LLMCallRecord(
                stage=stage,
                provider=getattr(llm, "mode", "unknown"),
                model=getattr(llm, "model", "unknown"),
                latency_ms=0,
                attempts=0,
                ok=False,
                error="model payload is not an object",
            )
        data = dict(payload)
        meta = data.pop("__llm_meta__", None)
        if isinstance(meta, dict):
            return data, LLMCallRecord.model_validate(meta)
        return data, LLMCallRecord(
            stage=stage,
            provider=getattr(llm, "mode", "unknown"),
            model=getattr(llm, "model", "unknown"),
            latency_ms=0,
            attempts=0,
            ok=getattr(llm, "mode", "unknown") != "mock",
            error="LLM call metadata missing",
        )

    @staticmethod
    def _scenario_confidence(
        evidence_ids: list[str],
        evidence: list[RetrievedEvidence],
        *,
        scenario: ScenarioResult | None = None,
        risk_degraded: bool = False,
        scenario_degraded: bool = False,
        critical_gap_count: int = 0,
    ) -> tuple[str, list[str]]:
        """Scenario-level confidence derived from the evidence it cites."""
        if scenario is not None:
            # The model may attach evidence to individual rubric dimensions
            # without repeating the same IDs at scenario level. Confidence
            # should still reflect those concrete citations.
            evidence_ids = list(
                dict.fromkeys(
                    [
                        *evidence_ids,
                        *(
                            evidence_id
                            for assessment in scenario.dimension_assessments.values()
                            for evidence_id in assessment.evidence_ids
                        ),
                    ]
                )
            )
        by_id = {item.evidence_id: item for item in evidence}
        items = [by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in by_id]
        reasons: list[str] = []
        max_level = "high"
        if scenario_degraded:
            max_level = "low"
            reasons.append("Capped at LOW: ScenarioAgent used the rule-based fallback.")
        elif risk_degraded:
            max_level = "low"
            reasons.append("Capped at LOW: RiskAgent used the rule-based fallback.")
        if not items:
            return "low", [
                *reasons,
                "No qualifying evidence is linked to this scenario.",
            ]
        company_items = [
            item for item in items if item.evidence_scope == "company"
        ]
        if not company_items:
            max_level = "medium" if max_level == "high" else max_level
            reasons.append(
                "Capped at MEDIUM: no company-specific evidence is linked."
            )
        if critical_gap_count:
            max_level = "medium" if max_level == "high" else max_level
            reasons.append(
                f"Capped at MEDIUM: {critical_gap_count} critical information "
                "gap(s) remain open."
            )
        if scenario is not None and scenario.dimension_assessments:
            sources = {
                item.source
                for item in scenario.dimension_assessments.values()
            }
            if sources == {"inference"}:
                max_level = "low"
                reasons.append(
                    "Capped at LOW: all five dimensions are inferred, not evidence-backed."
                )
        strong = {
            item.authority_level for item in items
        } & {"S", "A+", "A", "B+"}
        mock_only = all(item.is_mock for item in items)
        if len(items) >= 3 and strong and not mock_only:
            candidate, details = "high", [
                f"{len(items)} linked sources: "
                + ", ".join(item.evidence_id for item in items)
                + f" (authority {sorted(strong)[0]})"
            ]
        elif len(items) >= 2:
            candidate, details = "medium", [
                f"{len(items)} linked sources: "
                + ", ".join(item.evidence_id for item in items)
                + (" (test data only)" if mock_only else ", no top-tier authority material")
            ]
        else:
            candidate, details = "low", [
                f"Only one linked source: {items[0].evidence_id}"
            ]
        rank = {"low": 0, "medium": 1, "high": 2}
        final_level = (
            candidate
            if rank[candidate] <= rank[max_level]
            else max_level
        )
        return final_level, [*reasons, *details]

    @staticmethod
    def _resolve_data_mode(evidence: list[RetrievedEvidence]) -> str:
        if not evidence:
            return "unavailable"
        if all(item.is_mock for item in evidence):
            return "mock"
        has_live = any(
            item.source_type.startswith("live_")
            or item.evidence_scope == "company"
            for item in evidence
        )
        has_rag = any(
            not item.is_mock
            and not item.source_type.startswith("live_")
            and item.evidence_scope != "company"
            for item in evidence
        )
        if has_live and has_rag:
            return "hybrid"
        if has_live:
            return "live"
        if has_rag:
            return "rag_only"
        return "unavailable"

    # Evidence priority for the profile stage. The company's own disclosure comes
    # first; policy material belongs to risk and scenario analysis (doc: Profile
    # evidence priority).
    EVIDENCE_TIERS: tuple[tuple[int, tuple[str, ...], str], ...] = (
        (
            1,
            (
                "company_filing",
                "company_announcement",
                "exchange_disclosure",
                "company_registry",
                "company_website",
            ),
            "company's own disclosure",
        ),
        (
            2,
            ("company_media", "company_news", "company_interview"),
            "company-specific reporting",
        ),
        (
            2,
            ("company_profile_public",),
            "public reference summary (not the company's own disclosure)",
        ),
        (
            4,
            ("法规政策", "官方报告", "live_policy", "policy"),
            "policy / regulatory material",
        ),
    )

    @classmethod
    def _evidence_tier(cls, item: RetrievedEvidence) -> tuple[int, str]:
        source_type = str(item.source_type or "").strip()
        for tier, types, reason in cls.EVIDENCE_TIERS:
            if source_type in types:
                return tier, reason
        if item.evidence_scope == "company":
            return 1, "company's own disclosure"
        # Industry context: research reports, trade data, cases, news, encyclopaedia.
        return 3, "industry context"

    @classmethod
    def _enrich_evidence_status(
        cls,
        evidence: list[RetrievedEvidence],
    ) -> list[RetrievedEvidence]:
        now = datetime.now(timezone.utc)
        # Registry and website records describe an entity as it stands today, so
        # they are living references rather than dated documents. Applying the
        # document age rules to them marked the most authoritative company
        # source (a Wikidata record dated by its founding year) as "outdated".
        entity_record_types = {"company_registry", "company_website"}
        enriched: list[RetrievedEvidence] = []
        for item in evidence:
            freshness = "unknown"
            entity_record = item.source_type in entity_record_types
            published = None
            raw_date = (item.publication_date or "").strip()
            for parser in (
                lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")),
                lambda value: datetime.strptime(value[:10], "%Y/%m/%d"),
                lambda value: datetime.strptime(value[:4], "%Y"),
            ):
                try:
                    published = parser(raw_date)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                    break
                except (TypeError, ValueError):
                    continue
            if published is not None and not entity_record:
                age_years = max(0.0, (now - published).days / 365.25)
                freshness = (
                    "current"
                    if age_years <= 1.5
                    else "aging"
                    if age_years <= 4
                    else "stale"
                )
            if item.is_mock:
                verification = "partial"
            elif freshness == "stale" and not entity_record:
                verification = "outdated"
            elif item.authority_level in {"S", "A+", "A"}:
                verification = "verified"
            elif item.authority_level in {"B+", "B"}:
                verification = "partial"
            else:
                verification = "unverified"
            tier, tier_reason = cls._evidence_tier(item)
            enriched.append(
                item.model_copy(
                    update={
                        "freshness": freshness,
                        "verification_status": verification,
                        "source_tier": tier,
                        "source_tier_reason": tier_reason,
                    }
                )
            )
        return enriched

    def run(
        self,
        company: CompanyInput,
        api_key: str | None = None,
        model_name: str | None = None,
        event_callback: EventCallback | None = None,
        language: str = "en",
    ) -> Assessment:
        run_id = uuid.uuid4().hex[:10].upper()
        request_id = f"REQ-{run_id}"
        assessment_id = f"ASM-{run_id}"
        trace: list[TraceStep] = []
        llm_calls: list[LLMCallRecord] = []
        degraded_stages: list[str] = []
        selected_model = model_name or getattr(self.llm, "model", "mock")
        active_llm = self.llm.with_runtime(
            selected_model,
            api_key,
            event_callback,
        )
        if self.llm.mode == "deepseek":
            if not getattr(active_llm, "api_key", None):
                raise ValueError("Backend DeepSeek API Key is not configured")
            self._emit_event(
                event_callback,
                {
                    "type": "status",
                    "agent": "Runtime",
                    "message": "正在验证 API Key 和模型权限",
                },
            )
            if not active_llm.validate_key():
                raise ValueError("DeepSeek API Key 无效或没有模型访问权限")

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "ProfileAgent", "status": "started"},
        )
        profile = self._build_profile(company, request_id, language)
        trace.append(
            self._trace(
                agent="ProfileAgent",
                action="构建结构化企业画像",
                status="completed",
                detail="已标准化企业、生产布局、市场、约束和决策优先级。",
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "ProfileAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "EntityAgent", "status": "started"},
        )
        entity_payload = active_llm.understand_entity(company, language)
        entity_payload, entity_call = self._consume_llm_result(
            entity_payload, "EntityAgent", active_llm
        )
        llm_calls.append(entity_call)
        entity = self._coerce_entity(entity_payload.get("entity"), company)
        entity_degraded = not entity_call.ok
        if entity_degraded:
            degraded_stages.append("EntityAgent")
        trace.append(
            self._trace(
                agent="EntityAgent",
                action="企业实体识别与别名解析",
                status="fallback" if entity_degraded else "completed",
                detail=(
                    f"法律实体：{entity.legal_name or company.company_name}；"
                    f"别名：{', '.join(entity.aliases[:5]) or '未提供'}"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "EntityAgent", "status": "completed"},
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "ResearchAgent", "status": "started"},
        )
        evidence = self._enrich_evidence_status(
            self._retrieve(company, entity.aliases)
        )
        data_mode = self._resolve_data_mode(evidence)
        # Step 0 (Company Intelligence revision): the profile stage must describe
        # the company, not its policy exposure, so it receives company evidence
        # only. The full set is still what downstream risk/scenario stages use.
        company_evidence = self._company_evidence(evidence)
        policy_evidence = self._policy_evidence(evidence)
        # Profile evidence priority (doc §1.2): the company's own disclosure and
        # company-specific reporting first, industry context only as a labelled
        # supplement, policy material not at all.
        primary_evidence = [item for item in evidence if item.source_tier <= 2]
        context_evidence = [item for item in evidence if item.source_tier == 3][:2]
        profile_evidence = (
            primary_evidence + context_evidence or company_evidence or evidence
        )
        trace.append(
            self._trace(
                agent="ResearchAgent",
                action="调用混合检索工具",
                status="completed",
                detail=(
                    f"返回 {len(evidence)} 条证据（公司来源 {len(company_evidence)} 条、"
                    f"政策来源 {len(policy_evidence)} 条；画像阶段使用 "
                    f"{len(profile_evidence)} 条），数据模式为 {data_mode}。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "ResearchAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "IntelligenceAgent", "status": "started"},
        )
        intelligence_payload = active_llm.build_intelligence(
            company, profile, profile_evidence, language
        )
        intelligence_payload, intelligence_call = self._consume_llm_result(
            intelligence_payload, "IntelligenceAgent", active_llm
        )
        llm_calls.append(intelligence_call)
        intelligence, intelligence_fallback = self._coerce_intelligence(
            intelligence_payload,
            company,
            profile,
            # Citations are validated against what this stage actually saw.
            profile_evidence,
            language,
            entity=entity,
        )
        intelligence_degraded = intelligence_fallback or not intelligence_call.ok
        if intelligence_degraded:
            degraded_stages.append("IntelligenceAgent")
        trace.append(
            self._trace(
                agent="IntelligenceAgent",
                action="构建企业情报画像",
                status="fallback" if intelligence_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if intelligence_degraded
                    else f"输出 {len(intelligence.overview)} 条概况事实与 "
                    f"{len(intelligence.information_gaps)} 项待确认信息。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "IntelligenceAgent", "status": "completed"},
        )

        heuristic = self._build_heuristic(company, evidence)
        # The shared company context every downstream stage receives.
        intelligence_brief = self.intelligence_brief(intelligence)

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "RiskAgent", "status": "started"},
        )
        risk_payload = active_llm.analyze_risks(
            company,
            evidence,
            heuristic["risks"],
            language,
            company_intelligence=intelligence_brief,
        )
        risk_payload, risk_call = self._consume_llm_result(
            risk_payload, "RiskAgent", active_llm
        )
        llm_calls.append(risk_call)
        risks, risk_fallback = self._coerce_risks(
            risk_payload.get("risks"),
            heuristic["risks"],
            evidence,
            company,
            intelligence,
        )
        contested_ids = {
            link.evidence_id
            for risk in risks
            if risk.verification_status == "contested"
            for link in risk.evidence_links
        }
        if contested_ids:
            evidence = [
                item.model_copy(update={"verification_status": "contested"})
                if item.evidence_id in contested_ids
                else item
                for item in evidence
            ]
        risk_degraded = risk_fallback or not risk_call.ok
        if risk_degraded:
            degraded_stages.append("RiskAgent")
        trace.append(
            self._trace(
                agent="RiskAgent",
                action="识别与验证地缘政治风险",
                status="fallback" if risk_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if risk_degraded
                    else f"生成并校验 {len(risks)} 条风险。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "RiskAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "ScenarioAgent", "status": "started"},
        )
        scenario_payload = active_llm.simulate_scenarios(
            company,
            evidence,
            [item.model_dump(mode="json") for item in risks],
            heuristic["scenarios"],
            language,
            company_intelligence=intelligence_brief,
        )
        scenario_payload, scenario_call = self._consume_llm_result(
            scenario_payload, "ScenarioAgent", active_llm
        )
        llm_calls.append(scenario_call)
        scenarios, scenario_fallback = self._coerce_scenarios(
            scenario_payload.get("scenarios"),
            heuristic["scenarios"],
            evidence,
            company,
            risk_degraded=risk_degraded,
            scenario_model_ok=scenario_call.ok,
            intelligence=intelligence,
        )
        scenarios = self._rank_scenarios(scenarios)
        scenario_degraded = scenario_fallback or not scenario_call.ok
        if scenario_degraded:
            degraded_stages.append("ScenarioAgent")
        trace.append(
            self._trace(
                agent="ScenarioAgent",
                action="模拟迁移方案并重算权重",
                status="fallback" if scenario_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if scenario_degraded
                    else f"生成并校验 {len(scenarios)} 个情景，并按综合分从高到低编号。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "ScenarioAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "AdvisorAgent", "status": "started"},
        )
        recommendation_payload = active_llm.generate_recommendation(
            company,
            evidence,
            [item.model_dump(mode="json") for item in risks],
            [item.model_dump(mode="json") for item in scenarios],
            {
                "recommendation": heuristic["recommendation"],
                "limitations": heuristic["limitations"],
            },
            language,
            company_intelligence=intelligence_brief,
        )
        recommendation_payload, advisor_call = self._consume_llm_result(
            recommendation_payload, "AdvisorAgent", active_llm
        )
        llm_calls.append(advisor_call)
        recommendation, limitations, advisor_fallback = self._coerce_recommendation(
            recommendation_payload,
            heuristic,
            company,
            evidence,
            risks,
            scenarios,
        )
        advisor_degraded = advisor_fallback or not advisor_call.ok
        if advisor_degraded:
            degraded_stages.append("AdvisorAgent")
        trace.append(
            self._trace(
                agent="AdvisorAgent",
                action="生成建议与人工复核标记",
                status="fallback" if advisor_degraded else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if advisor_degraded
                    else "建议已关联方案、风险和人工复核条件。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "AdvisorAgent",
                "status": "completed",
            },
        )

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "VerificationAgent", "status": "started"},
        )
        citations_valid = self._validate_citations(
            risks, scenarios, evidence, recommendation
        )
        trace.append(
            self._trace(
                agent="VerificationAgent",
                action="校验引用与输出边界",
                status="completed" if citations_valid else "fallback",
                detail=(
                    "全部风险与情景引用均指向本次检索结果。"
                    if citations_valid
                    else "部分引用无效，已替换为可用证据或标记为 unverified。"
                ),
                started=step_started,
            )
        )
        self._emit_event(
            event_callback,
            {
                "type": "stage",
                "agent": "VerificationAgent",
                "status": "completed",
            },
        )

        degraded = bool(degraded_stages)
        if len(scenarios) >= 2:
            score_values = [item.weighted_score for item in scenarios]
            if max(score_values) - min(score_values) < 5:
                limitations = [
                    *limitations,
                    "Scenario scores are highly converged; verify that evidence "
                    "is sufficient to distinguish the strategic options.",
                ]
        if degraded:
            limitations = [
                *limitations,
                "以下阶段未获得有效模型输出，已显式降级为规则基线："
                + ", ".join(dict.fromkeys(degraded_stages)),
            ]

        now = utc_now()
        return Assessment(
            assessment_id=assessment_id,
            request_id=request_id,
            created_at=now,
            updated_at=now,
            language=language if language in {"en", "zh"} else "en",  # type: ignore[arg-type]
            company_input=company,
            # The weights actually used for scenario scoring: the user's ranking
            # when one was given, otherwise equal weights.
            scoring=self._effective_weights(company),
            weighting_mode="user" if company.priorities_declared else "equal",
            company_profile=profile,
            company_intelligence=intelligence,
            evidence=evidence,
            risks=risks,
            scenarios=scenarios,
            recommendation=recommendation,
            trace=trace,
            limitations=limitations,
            model_mode=active_llm.mode,
            model_name=selected_model,
            data_mode=data_mode,
            llm_calls=llm_calls,
            degraded=degraded,
        )

    def chat_opening(
        self,
        assessment: Assessment,
        language: str = "en",
    ) -> ChatOpeningResponse:
        intelligence = assessment.company_intelligence
        gaps = [
            gap
            for gap in (
                intelligence.information_gaps if intelligence else []
            )
            if isinstance(gap, InformationGap)
            and gap.status != "resolved"
        ]
        order = {"critical": 0, "important": 1, "optional": 2}
        gaps.sort(key=lambda gap: order.get(gap.priority, 3))
        if not gaps:
            message = (
                "我已载入当前企业画像、风险和情景结果。"
                "你可以直接提问，或补充供应商、产能、成本、客户和合规约束。"
                if (language or "en").lower() == "zh"
                else "I have loaded the company profile, risks and scenario results. "
                "You can ask a question or add supplier, capacity, cost, customer "
                "or compliance constraints."
            )
            return ChatOpeningResponse(message=message)
        gap = gaps[0]
        dimensions = self._gap_affected_dimensions(gap.item)
        if (language or "en").lower() == "zh":
            message = (
                f"为了把情景推演做得更准确，请先补充一项关键信息：{gap.item}。"
                f"它之所以重要，是因为{gap.why_it_matters or '它会直接影响情景判断'}。"
                f"{gap.recommended_action or '请提供可确认的数值或文件依据。'}"
            )
        else:
            message = (
                f"To improve the scenario simulation, please confirm one key item: "
                f"{gap.item}. This matters because "
                f"{gap.why_it_matters or 'it directly affects the scenario assessment'}. "
                f"{gap.recommended_action or 'Please provide a verifiable value or source.'}"
            )
        return ChatOpeningResponse(
            message=message,
            action="ask_gap",
            requested_gap=gap.item,
            why_it_matters=gap.why_it_matters,
            affected_dimensions=dimensions,
        )

    @staticmethod
    def _gap_affected_dimensions(gap_item: str) -> list[str]:
        text = gap_item.lower()
        dimensions: list[str] = []

        def add(value: str) -> None:
            if value not in dimensions:
                dimensions.append(value)

        if any(token in text for token in ("capacity", "factory", "plant", "产能", "工厂", "基地")):
            add("resilience")
            add("implementation")
        if any(token in text for token in ("supplier", "material", "bom", "供应", "材料", "物料")):
            add("resilience")
            add("cost")
        if any(token in text for token in ("cost", "budget", "成本", "预算")):
            add("cost")
            add("implementation")
        if any(token in text for token in ("customer", "market", "客户", "市场", "准入")):
            add("market_access")
        if any(token in text for token in ("tariff", "policy", "compliance", "关税", "政策", "合规")):
            add("geopolitical_risk")
            add("market_access")
        return dimensions or ["implementation"]

    def chat(self, assessment: Assessment, request: ChatRequest) -> Assessment:
        user_turn = ChatTurn(role="user", content=request.message, created_at=utc_now())
        step_started = time.perf_counter()
        active_llm = self.llm.with_runtime(
            assessment.model_name,
            request.api_key,
            None,
        )
        if self.llm.mode == "deepseek" and not getattr(active_llm, "api_key", None):
            raise ValueError("Backend DeepSeek API Key is not configured")
        language = request.language
        action = active_llm.choose_chat_action(
            assessment,
            request.message,
            language,
            company_intelligence=self.intelligence_brief(
                assessment.company_intelligence
            ),
        )
        action, action_call = self._consume_llm_result(
            action, "ChatActionAgent", active_llm
        )
        chat_calls = [*assessment.llm_calls, action_call]
        supplemental_evidence: list[RetrievedEvidence] = []
        trace_status = "completed" if action_call.ok else "fallback"

        action_name = str(action.get("action") or "answer")
        if action_name == "ask_gap":
            reply = str(
                action.get("question")
                or "请补充当前最关键的信息缺口，以便继续更新风险与情景分析。"
            )
            detail = (
                f"ChatAgent 主动追问信息缺口："
                f"{action.get('gap_item') or '未指定'}"
            )
        elif action_name == "search_evidence":
            query = str(action.get("query") or request.message)[:500]
            supplemental_evidence = self._search_text(query)
            detail = f"ChatAgent 自主调用检索工具，补充 {len(supplemental_evidence)} 条证据。"
            if not supplemental_evidence:
                trace_status = "fallback"
                detail = "ChatAgent 请求检索，但没有获得补充证据。"
        else:
            detail = "ChatAgent 判断现有上下文足够，直接调用模型回答。"

        if action_name != "ask_gap":
            reply = active_llm.answer_chat(
                assessment,
                request.message,
                supplemental_evidence,
                language,
                company_intelligence=self.intelligence_brief(
                    assessment.company_intelligence
                ),
            )
            answer_meta = getattr(active_llm, "last_call_meta", None)
            if isinstance(answer_meta, dict):
                answer_call = LLMCallRecord.model_validate(answer_meta)
                chat_calls.append(answer_call)
                if not answer_call.ok:
                    trace_status = "fallback"
        chat_analysis = self._chat_analysis(
            action, reply, request.message, supplemental_evidence
        )
        chat_trace = self._trace(
            agent="ChatAgent",
            action="选择工具并回答追问",
            status=trace_status,
            detail=detail,
            started=step_started,
        )

        assistant_turn = ChatTurn(role="assistant", content=reply, created_at=utc_now())
        history = [*assessment.chat_history, user_turn, assistant_turn]
        updated = assessment.model_copy(
            update={
                "chat_history": history,
                "chat_analysis": chat_analysis,
                "trace": [
                    *assessment.trace,
                    chat_trace,
                ],
                "llm_calls": chat_calls,
                "degraded": assessment.degraded or any(
                    not item.ok for item in chat_calls
                ),
                "updated_at": utc_now(),
            }
        )
        # Consultation is deliberately descriptive: new information is stored
        # and explained, but the formal scenario scores only change when the
        # user explicitly calls the scenario re-simulation endpoint.
        return updated

    def resimulate(
        self,
        assessment: Assessment,
        additional_constraints: list[str] | None = None,
        api_key: str | None = None,
        model_name: str | None = None,
        language: str = "en",
    ) -> Assessment:
        """Refresh the scenario comparison with constraints from the consultation.

        The company profile, evidence set and risk list are reused, so this is a
        scenario re-run rather than a full re-assessment.
        """
        company = assessment.company_input
        if company is None:
            raise ValueError(
                "this assessment has no stored company input, so scenarios cannot "
                "be re-run"
            )
        selected_model = model_name or getattr(self.llm, "model", "mock")
        active_llm = self.llm.with_runtime(selected_model, api_key, None)
        if self.llm.mode == "deepseek":
            if not getattr(active_llm, "api_key", None):
                raise ValueError("Backend DeepSeek API Key is not configured")
            if not active_llm.validate_key():
                raise ValueError("DeepSeek API Key 无效或没有模型访问权限")

        constraints = [
            item.strip()
            for item in (additional_constraints or [])
            if item and item.strip()
        ]
        if constraints:
            addition = " | ".join(
                f"Consultation input: {item}" for item in constraints
            )
            company = company.model_copy(
                update={"notes": ((company.notes or "") + "\n" + addition).strip()[:4000]}
            )

        heuristic = self._build_heuristic(company, assessment.evidence)
        # A re-run keeps the same company context as the original assessment.
        resim_intelligence = self.intelligence_brief(
            assessment.company_intelligence
        )
        step_started = time.perf_counter()
        scenario_payload = active_llm.simulate_scenarios(
            company,
            assessment.evidence,
            [item.model_dump(mode="json") for item in assessment.risks],
            heuristic["scenarios"],
            language,
            company_intelligence=resim_intelligence,
            revision_context={
                "previous_scenarios": [
                    item.model_dump(mode="json")
                    for item in assessment.scenarios
                ],
                "new_information": constraints,
                "instruction": (
                    "Compare against previous_scenarios and explain the score "
                    "change or non-change for each affected dimension."
                ),
            },
        )
        scenario_payload, scenario_call = self._consume_llm_result(
            scenario_payload, "ScenarioAgent", active_llm
        )
        risk_degraded = any(
            step.agent == "RiskAgent" and step.status == "fallback"
            for step in assessment.trace
        )
        scenarios, scenario_fallback = self._coerce_scenarios(
            scenario_payload.get("scenarios"),
            heuristic["scenarios"],
            assessment.evidence,
            company,
            risk_degraded=risk_degraded,
            scenario_model_ok=scenario_call.ok,
            intelligence=assessment.company_intelligence,
        )
        scenarios = self._rank_scenarios(scenarios)
        recommendation_payload = active_llm.generate_recommendation(
            company,
            assessment.evidence,
            [item.model_dump(mode="json") for item in assessment.risks],
            [item.model_dump(mode="json") for item in scenarios],
            {
                "recommendation": heuristic["recommendation"],
                "limitations": heuristic["limitations"],
            },
            language,
            company_intelligence=resim_intelligence,
        )
        recommendation_payload, advisor_call = self._consume_llm_result(
            recommendation_payload, "AdvisorAgent", active_llm
        )
        resim_calls = [
            *assessment.llm_calls,
            scenario_call,
            advisor_call,
        ]
        recommendation, limitations, _ = self._coerce_recommendation(
            recommendation_payload,
            heuristic,
            company,
            assessment.evidence,
            assessment.risks,
            scenarios,
        )
        trace_step = self._trace(
            agent="ScenarioAgent",
            action="按咨询新增约束重跑情景模拟",
            status=(
                "completed"
                if scenario_call.ok and advisor_call.ok and not scenario_fallback
                else "fallback"
            ),
            detail=(
                f"已纳入 {len(constraints)} 条咨询新增约束并重算权重。"
                if language == "zh"
                else f"Re-ran the scenario comparison with {len(constraints)} "
                "new consultation constraint(s)."
            ),
            started=step_started,
        )
        return assessment.model_copy(
            update={
                "scenarios": scenarios,
                "recommendation": recommendation,
                "limitations": limitations,
                "company_input": company,
                "company_profile": self._build_profile(
                    company, assessment.request_id, language
                ),
                "language": language if language in {"en", "zh"} else assessment.language,
                "trace": [*assessment.trace, trace_step],
                "llm_calls": resim_calls,
                "degraded": assessment.degraded or any(
                    not item.ok for item in resim_calls
                ),
                "updated_at": utc_now(),
            }
        )

    @staticmethod
    def _chat_analysis(
        action: dict[str, Any],
        reply: str,
        message: str,
        supplemental_evidence: list[RetrievedEvidence],
    ) -> ChatImpact:
        """Structured turn outcome for the consultation workspace (UI.md §19)."""

        def as_list(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(item) for item in value if str(item).strip()]
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            return []

        new_constraints = as_list(action.get("new_constraints"))
        new_preferences = as_list(action.get("new_preferences"))
        profile_patch = {
            str(key): str(value)
            for key, value in (action.get("profile_patch") or {}).items()
            if str(key).strip() and str(value).strip()
        } if isinstance(action.get("profile_patch"), dict) else {}
        gap_updates: list[GapUpdate] = []
        for item in action.get("gap_updates") or []:
            if not isinstance(item, dict):
                continue
            gap_item = str(item.get("gap_item") or item.get("gap") or "").strip()
            if not gap_item:
                continue
            try:
                gap_updates.append(GapUpdate.model_validate(item))
            except ValidationError:
                continue
        affected_dimensions = [
            str(item)
            for item in (action.get("affected_dimensions") or [])
            if str(item)
            in {
                "cost",
                "resilience",
                "geopolitical_risk",
                "market_access",
                "implementation",
            }
        ]
        scenario_update_required = bool(action.get("scenario_update_required"))
        if not new_constraints and not new_preferences:
            # Conservative fallback: a substantive message that is not a question
            # is treated as new context worth folding into the next scenario run.
            substantive = len(message.strip()) > 40 and "?" not in message
            if substantive:
                new_constraints = [message.strip()[:400]]
            scenario_update_required = scenario_update_required or substantive
        scenario_update_required = scenario_update_required or bool(
            profile_patch or gap_updates or affected_dimensions
        )
        summary = str(action.get("summary") or "").strip()
        if not summary:
            summary = reply.strip().split("\n", 1)[0][:300]
        return ChatImpact(
            new_constraints=new_constraints,
            new_preferences=new_preferences,
            profile_patch=profile_patch,
            gap_updates=gap_updates,
            affected_dimensions=affected_dimensions,
            requested_gap=str(action.get("gap_item") or ""),
            gap_question=str(action.get("question") or ""),
            scenario_update_required=scenario_update_required,
            summary=summary,
        )

    def _search_text(self, value: str) -> list[RetrievedEvidence]:
        query = RetrievalQuery(
            industry="supply_chain",
            products=[value],
            home_country="CN",
            production_countries=[],
            target_markets=[],
            decision_question=value,
            restrictions=[],
            limit=6,
        )
        return self.retrieval.search(query)

    # Safety net behind the prompt for the controlled role vocabulary. The more
    # specific stages are checked before the generic ones.
    SUPPLY_CHAIN_ROLE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "UPSTREAM_RAW_MATERIAL",
            ("raw material", "mining", "mineral", "lithium", "nickel", "cobalt",
             "graphite", "原材料", "矿产", "锂", "镍", "钴", "石墨"),
        ),
        (
            "UPSTREAM_COMPONENT",
            ("component", "cathode", "anode", "electrolyte", "separator",
             "material supplier", "正极", "负极", "电解液", "隔膜", "零部件",
             "材料供应"),
        ),
        (
            "INTEGRATED_BATTERY_COMPANY",
            ("integrated", "multiple stage", "full value chain", "一体化",
             "全产业链", "多个环节"),
        ),
        (
            "BATTERY_MANUFACTURING",
            ("cell manufactur", "battery manufactur", "module", "pack assembl",
             "电芯", "模组", "电池制造", "电池与储能系统制造"),
        ),
        (
            "DOWNSTREAM_APPLICATION",
            ("ev manufactur", "oem", "energy storage", "integrator", "recycl",
             "application", "整车", "车企", "储能", "回收", "应用"),
        ),
    )

    @classmethod
    def _normalise_supply_chain_role(cls, value: Any) -> str:
        """Map a role onto the controlled vocabulary.

        The prompt asks for the enum values directly; this only rescues free-text
        answers so a stray description cannot leak into downstream prompts.
        """
        text = str(value or "").strip()
        if not text:
            return SUPPLY_CHAIN_ROLE_FALLBACK
        candidate = text.upper().replace("-", "_").replace(" ", "_")
        if candidate in SUPPLY_CHAIN_ROLE_VALUES:
            return candidate
        lowered = text.lower()
        for role, hints in cls.SUPPLY_CHAIN_ROLE_HINTS:
            if any(hint in lowered for hint in hints):
                return role
        return SUPPLY_CHAIN_ROLE_FALLBACK

    @classmethod
    def _normalise_supply_chain_roles(cls, value: Any) -> list[str]:
        """Accepts a list or a delimited string.

        A bare string used to be iterated directly, which turned one description
        into one entry per character.
        """
        roles: list[str] = []
        for item in cls._string_candidates(value):
            role = cls._normalise_supply_chain_role(item)
            if role == SUPPLY_CHAIN_ROLE_FALLBACK or role in roles:
                continue
            roles.append(role)
        return roles

    @staticmethod
    def _string_candidates(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, str):
            return re.split(r"[,;、，；/|]+", value)
        if isinstance(value, (list, tuple, set)):
            candidates: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    candidates.extend(re.split(r"[,;、，；/|]+", item))
                else:
                    candidates.append(item)
            return candidates
        return [value]

    # Doc §6: the profile should surface a few gaps that matter, not a dump.
    GAP_LIMITS = {"critical": 3, "important": 3, "optional": 3}
    # Each evidence view gets its own budget in _retrieve (see the note there).
    COMPANY_EVIDENCE_BUDGET = 9
    POLICY_EVIDENCE_BUDGET = 6
    GAP_ORDER = ("critical", "important", "optional")
    SUPPLY_CHAIN_STAGES = (
        "raw_material",
        "component",
        "manufacturing",
        "downstream",
    )
    # Answers that echo the schema instead of describing the company: a model
    # occasionally emits the field values themselves as "facts".
    SCHEMA_NOISE_VALUES = {
        "user_input",
        "public_source",
        "inferred",
        "to_be_confirmed",
        "low",
        "medium",
        "high",
        "unknown",
        "true",
        "false",
        "none",
        "null",
        "n/a",
    }
    _EVIDENCE_ID_LIST = re.compile(
        r"(evd-[a-z0-9\-]+)(\s*[;,、]\s*evd-[a-z0-9\-]+)*"
    )

    @classmethod
    def _is_schema_noise(cls, text: str) -> bool:
        """True when a "fact" is really a field name or field value."""
        lowered = str(text or "").strip().lower()
        if not lowered:
            return True
        if lowered in cls.SCHEMA_NOISE_VALUES:
            return True
        # A bare list of evidence ids carries no company information.
        return bool(cls._EVIDENCE_ID_LIST.fullmatch(lowered))

    @classmethod
    def _patch_intelligence(
        cls,
        intelligence: CompanyIntelligence | None,
        analysis: ChatImpact,
    ) -> tuple[CompanyIntelligence | None, int]:
        """Fold consultation input into the company model.

        New constraints extend the decision context; stated preferences extend the
        drivers, because a preference such as "we would rather not relocate" is a
        factor driving the decision. Existing entries are never overwritten.
        """
        if intelligence is None:
            return None, 0
        context = intelligence.decision_context
        patch_constraints = [
            f"{key}: {value}"
            for key, value in analysis.profile_patch.items()
        ]
        constraints = list(
            dict.fromkeys(
                [
                    *context.constraints,
                    *analysis.new_constraints,
                    *patch_constraints,
                ]
            )
        )
        drivers = list(
            dict.fromkeys([*context.drivers, *analysis.new_preferences])
        )
        sites = list(intelligence.manufacturing_footprint)
        patched_sites = 0
        for key, value in analysis.profile_patch.items():
            match = re.match(
                r"(?:site\.)?([a-z]{2}|[A-Za-z\u4e00-\u9fff]+)\.(capacity|facility|role)$",
                key,
            )
            if not match:
                continue
            country, field_name = match.groups()
            country_key = cls._country_key(country)
            for index, site in enumerate(sites):
                if cls._country_key(site.country) != country_key:
                    continue
                updates = {field_name: value}
                if field_name == "capacity":
                    updates["status"] = "reported"
                sites[index] = site.model_copy(update=updates)
                patched_sites += 1
                break

        gaps = list(intelligence.information_gaps)
        patched_gaps = 0
        for update in analysis.gap_updates:
            target = re.sub(r"\s+", "", update.gap_item).casefold()
            for index, gap in enumerate(gaps):
                if isinstance(gap, str):
                    gap_text = gap
                    is_struct = False
                else:
                    gap_text = gap.item
                    is_struct = True
                candidate = re.sub(r"\s+", "", gap_text).casefold()
                if target[:40] not in candidate and candidate[:40] not in target:
                    continue
                if is_struct:
                    gaps[index] = gap.model_copy(
                        update={"status": update.status}
                    )
                else:
                    gaps[index] = InformationGap(
                        item=gap_text,
                        status=update.status,
                    )
                patched_gaps += 1
                break

        added = (len(constraints) - len(context.constraints)) + (
            len(drivers) - len(context.drivers)
        ) + patched_sites + patched_gaps
        if added <= 0:
            return intelligence, 0
        return (
            intelligence.model_copy(
                update={
                    "decision_context": context.model_copy(
                        update={"constraints": constraints, "drivers": drivers}
                    ),
                    "manufacturing_footprint": sites,
                    "information_gaps": gaps,
                }
            ),
            added,
        )

    @classmethod
    def _cap_information_gaps(
        cls, gaps: list[InformationGap]
    ) -> list[InformationGap]:
        counts = {priority: 0 for priority in cls.GAP_ORDER}
        kept: list[InformationGap] = []
        seen: set[str] = set()
        for gap in sorted(
            gaps, key=lambda item: cls.GAP_ORDER.index(item.priority)
            if item.priority in cls.GAP_ORDER
            else len(cls.GAP_ORDER)
        ):
            if gap.priority not in cls.GAP_ORDER:
                continue
            key = re.sub(r"\s+", "", gap.item).lower()[:60]
            if not key or key in seen:
                continue
            if counts[gap.priority] >= cls.GAP_LIMITS[gap.priority]:
                continue
            seen.add(key)
            counts[gap.priority] += 1
            kept.append(gap)
        return kept

    @classmethod
    def _coerce_supply_chain_structure(
        cls,
        payload: Any,
        allowed: set[str],
    ) -> list[SupplyChainStage]:
        """One structured entry per supply-chain link.

        A percentage is only kept when it is traceable: user input, a company
        disclosure, or a sourced estimate. Anything else becomes "unknown" so the
        model cannot invent precision (doc §3.4).
        """
        stages: list[SupplyChainStage] = []
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "").strip().lower()
            if stage not in cls.SUPPLY_CHAIN_STAGES:
                continue
            if any(existing.stage == stage for existing in stages):
                continue
            source_ids = [
                value
                for value in (item.get("source_ids") or [])
                if value in allowed
            ]
            basis = str(item.get("share_basis") or "").strip()
            if basis not in {"user_input", "disclosed", "sourced_estimate", "unknown"}:
                basis = "unknown"
            share = str(item.get("share") or "").strip() or "unknown"
            has_digit = any(char.isdigit() for char in share)
            if basis == "unknown":
                share = "unknown"
            elif basis != "user_input" and not source_ids:
                # disclosed / sourced_estimate without a citation is not traceable
                basis = "unknown"
                share = "unknown" if has_digit else share
            stages.append(
                SupplyChainStage(
                    stage=stage,  # type: ignore[arg-type]
                    description=str(item.get("description") or "")[:400],
                    region=str(item.get("region") or "unknown")[:80],
                    company_role=str(item.get("company_role") or "")[:200],
                    share=share[:40],
                    share_basis=basis,  # type: ignore[arg-type]
                    source_ids=source_ids,
                )
            )
        return stages

    @classmethod
    def _coerce_string_list(cls, value: Any) -> list[str]:
        """De-duplicated string list.

        Tolerates a delimited string, and flattens an object to its text instead
        of storing a Python dict literal in a string field.
        """
        items: list[str] = []
        for candidate in cls._string_candidates(value):
            text = (
                cls._text_of(candidate)
                if isinstance(candidate, dict)
                else str(candidate or "").strip()
            )
            if text and text not in items:
                items.append(text)
        return items

    @staticmethod
    def _company_evidence(
        evidence: list[RetrievedEvidence],
    ) -> list[RetrievedEvidence]:
        """Evidence about the company itself (registry, website, filings)."""
        return [item for item in evidence if item.evidence_scope == "company"]

    @staticmethod
    def _policy_evidence(
        evidence: list[RetrievedEvidence],
    ) -> list[RetrievedEvidence]:
        """Everything else: policy, trade and market material used for risk."""
        return [item for item in evidence if item.evidence_scope != "company"]

    def _retrieve(
        self,
        company: CompanyInput,
        aliases: list[str] | None = None,
    ) -> list[RetrievedEvidence]:
        query = RetrievalQuery(
            industry=company.industry,
            products=company.products,
            company_name=company.company_name,
            aliases=list(aliases or []),
            home_country=company.home_country,
            production_countries=[
                location.country for location in company.production_locations
            ],
            target_markets=company.target_markets,
            decision_question=company.decision_question,
            restrictions=company.restrictions,
            limit=10,
        )
        policy_evidence = self.retrieval.search(query)
        company_evidence = (
            self.company_research.search(company, aliases)
            if self.company_research
            else []
        )
        combined: list[RetrievedEvidence] = []
        seen: set[str] = set()

        def add(items: list[RetrievedEvidence], budget: int) -> None:
            added = 0
            for item in items:
                if added >= budget:
                    break
                # One PDF is represented by several section snippets, so the URL
                # alone is no longer a unique identity: keying on the URL dropped
                # every snippet after the first. Section keeps that collapsing
                # for items that genuinely have the same source and no section.
                identity = (item.url or item.evidence_id, item.section)
                if identity in seen:
                    continue
                seen.add(identity)
                combined.append(item)
                added += 1

        # Company documents are far larger than they used to be (annual-report
        # sections), so each view gets its own budget. A single shared 12-item cap
        # meant company evidence pushed policy evidence out entirely, which the
        # risk stage depends on. One store, two views — not two lists.
        add(company_evidence, self.COMPANY_EVIDENCE_BUDGET)
        add(policy_evidence, max(query.limit, self.POLICY_EVIDENCE_BUDGET))
        return combined

    @staticmethod
    def _evidence_keywords(category_key: str) -> set[str]:
        return {
            "trade": {"tariff", "duty", "customs", "origin", "trade"},
            "political": {"geopolitic", "sanction", "political", "conflict"},
            "supply_chain": {
                "supplier",
                "supply chain",
                "lithium",
                "battery",
                "material",
                "logistics",
            },
            "regulatory": {
                "regulation",
                "compliance",
                "export control",
                "licence",
                "license",
                "policy",
            },
            "market_access": {
                "market access",
                "local content",
                "localization",
                "customer",
                "origin",
            },
            "operational": {
                "cost",
                "labor",
                "labour",
                "capacity",
                "implementation",
                "logistics",
            },
        }.get(category_key, set())

    def _select_risk_evidence(
        self,
        candidate_ids: list[str],
        category_key: str,
        evidence: list[RetrievedEvidence],
    ) -> list[EvidenceLink]:
        by_id = {item.evidence_id: item for item in evidence}
        candidate_items = [
            by_id[item_id]
            for item_id in candidate_ids
            if item_id in by_id
        ]
        if not candidate_items:
            candidate_items = list(evidence)
        keywords = self._evidence_keywords(category_key)
        links: list[EvidenceLink] = []
        for item in candidate_items:
            text = f"{item.title} {item.topic} {item.content}".lower()
            topic_hit = bool(keywords) and any(
                keyword in text for keyword in keywords
            )
            if not topic_hit:
                continue
            if item.relevance_score < 45 and item.evidence_scope != "company":
                continue
            if item.verification_status == "outdated":
                continue
            links.append(
                EvidenceLink(
                    evidence_id=item.evidence_id,
                    relation="supports",
                    reason=f"Matched {category_key} topic and relevance threshold.",
                )
            )
            if len(links) >= 3:
                break
        return links

    @staticmethod
    def _detect_contested(
        links: list[EvidenceLink],
        evidence: list[RetrievedEvidence],
    ) -> bool:
        by_id = {item.evidence_id: item for item in evidence}
        texts = {
            link.evidence_id: by_id[link.evidence_id].content.lower()
            for link in links
            if link.evidence_id in by_id
        }
        negative_markers = (
            "not applicable",
            "does not apply",
            "no evidence",
            "not required",
            "不适用",
            "未发现",
            "不需要",
        )
        positive_markers = (
            "requires",
            "must",
            "shall",
            "applicable",
            "要求",
            "适用",
            "必须",
        )
        ids = list(texts)
        for index, left_id in enumerate(ids):
            for right_id in ids[index + 1 :]:
                left = texts[left_id]
                right = texts[right_id]
                if (
                    any(marker in left for marker in negative_markers)
                    and any(marker in right for marker in positive_markers)
                ) or (
                    any(marker in right for marker in negative_markers)
                    and any(marker in left for marker in positive_markers)
                ):
                    return True
        return False

    def _select_scenario_evidence(
        self,
        candidate_ids: list[str],
        evidence: list[RetrievedEvidence],
    ) -> list[EvidenceLink]:
        by_id = {item.evidence_id: item for item in evidence}
        candidates = [
            by_id[item_id]
            for item_id in candidate_ids
            if item_id in by_id
        ]
        if not candidates:
            candidates = list(evidence)
        keywords: set[str] = set()
        for category_key in (
            "trade",
            "supply_chain",
            "regulatory",
            "market_access",
            "operational",
        ):
            keywords.update(self._evidence_keywords(category_key))
        links: list[EvidenceLink] = []
        for item in sorted(
            candidates,
            key=lambda value: value.relevance_score,
            reverse=True,
        ):
            text = f"{item.title} {item.topic} {item.content}".lower()
            if not any(keyword in text for keyword in keywords):
                continue
            if item.relevance_score < 45 and item.evidence_scope != "company":
                continue
            if item.verification_status in {"outdated", "contested"}:
                continue
            links.append(
                EvidenceLink(
                    evidence_id=item.evidence_id,
                    relation="supports" if item.relevance_score >= 65 else "context",
                    reason="Relevant to scenario cost, resilience, access or implementation.",
                )
            )
            if len(links) >= 3:
                break
        return links

    @classmethod
    def _normalize_scenario_band(cls, value: Any) -> str | None:
        if isinstance(value, dict):
            value = value.get("band") or value.get("rating")
        text = str(value or "").strip().lower()
        aliases = {
            "very favourable": "very_favourable",
            "favourable": "favourable",
            "neutral": "neutral",
            "unfavourable": "unfavourable",
            "very unfavourable": "very_unfavourable",
            "very_favorable": "very_favourable",
            "favorable": "favourable",
            "very unfavorable": "very_unfavourable",
            "unfavorable": "unfavourable",
        }
        text = aliases.get(text, text)
        return (
            text
            if text in cls.SCENARIO_BAND_SCORES
            else None
        )

    def _scenario_dimension_assessments(
        self,
        item: dict[str, Any],
        evidence: list[RetrievedEvidence],
    ) -> dict[str, ScenarioDimensionAssessment]:
        raw = item.get("dimension_assessments") or {}
        if not isinstance(raw, dict):
            raw = {}
        allowed_ids = {entry.evidence_id for entry in evidence}
        assessments: dict[str, ScenarioDimensionAssessment] = {}
        for metric, (alias, _, _) in self.SCENARIO_METRIC_CONFIG.items():
            raw_value = (
                raw.get(metric)
                or raw.get(alias)
                or item.get(f"{alias}_band")
            )
            detail = raw_value if isinstance(raw_value, dict) else {}
            band = self._normalize_scenario_band(raw_value)
            if band is None:
                legacy_score = item.get(metric)
                if legacy_score is not None:
                    band = self._score_band(int(legacy_score))
                else:
                    band = "neutral"
            evidence_ids = [
                value
                for value in (detail.get("evidence_ids") or [])
                if value in allowed_ids
            ]
            source = str(detail.get("source") or "").strip().lower()
            if source not in {"evidence", "inference"}:
                source = "evidence" if evidence_ids else "inference"
            if not evidence_ids and source == "evidence":
                source = "inference"
            if not evidence_ids:
                band = "neutral"
            assessments[metric] = ScenarioDimensionAssessment(
                band=band,
                reason=str(detail.get("reason") or ""),
                evidence_ids=evidence_ids,
                source=source,
            )
        return assessments

    @staticmethod
    def _risk_level_from_score(score: int) -> str:
        if score >= 60:
            return "high"
        if score >= 25:
            return "medium"
        return "low"

    @staticmethod
    def _likelihood_label(score: int) -> str:
        return {
            1: "very_low",
            2: "low",
            3: "medium",
            4: "high",
            5: "very_high",
        }.get(score, "medium")

    @staticmethod
    def _decision_relevance_rank(value: str) -> int:
        return {"low": 1, "medium": 2, "high": 3}.get(value, 2)

    @staticmethod
    def _confidence_rank(value: str) -> int:
        return {"low": 1, "medium": 2, "high": 3}.get(value, 1)

    @classmethod
    def _countries_in_text(cls, value: str) -> set[str]:
        text = str(value or "").lower()
        found: set[str] = set()
        for alias, canonical in cls.COUNTRY_ALIASES.items():
            if len(alias) <= 2:
                if re.search(rf"\b{re.escape(alias)}\b", text):
                    found.add(canonical)
            elif alias in text:
                found.add(canonical)
        return found

    @classmethod
    def _has_evidence_backed_company_trigger(
        cls,
        risk: dict[str, Any],
        company: CompanyInput | None,
        intelligence: CompanyIntelligence | None,
    ) -> bool:
        """Whether a policy risk is tied to a sourced company operating fact."""
        if company is None or intelligence is None:
            return False
        trigger = " ".join(
            str(risk.get(field) or "")
            for field in (
                "title",
                "name",
                "company_specific_trigger",
                "impact_description",
            )
        )
        if not trigger.strip():
            return False
        trigger_terms = cls._terms(trigger)
        trigger_countries = cls._countries_in_text(trigger)
        for site in intelligence.manufacturing_footprint:
            if not site.source_ids:
                continue
            site_country = cls._country_key(site.country)
            if site_country and site_country in trigger_countries:
                return True
            site_terms = cls._terms(f"{site.facility} {site.role}")
            if site_terms and len(site_terms & trigger_terms) >= 2:
                return True
        for stage in intelligence.supply_chain_structure:
            if not stage.source_ids:
                continue
            stage_terms = cls._terms(
                f"{stage.description} {stage.company_role} {stage.region}"
            )
            if stage_terms and len(stage_terms & trigger_terms) >= 2:
                return True
        return False

    def _apply_risk_rubric(
        self,
        risk: dict[str, Any],
        links: list[EvidenceLink],
        evidence: list[RetrievedEvidence],
        company: CompanyInput | None,
        intelligence: CompanyIntelligence | None = None,
    ) -> dict[str, Any]:
        by_id = {item.evidence_id: item for item in evidence}
        linked = [
            by_id[link.evidence_id]
            for link in links
            if link.evidence_id in by_id
        ]
        company_evidence = [
            item for item in linked if item.evidence_scope == "company"
        ]
        external_evidence = [
            item for item in linked if item.evidence_scope != "company"
        ]

        likelihood_score = max(
            1, min(5, int(risk.get("likelihood_score") or 3))
        )
        impact_score = max(1, min(5, int(risk.get("impact_score") or 3)))
        exposure_score = max(
            1, min(5, int(risk.get("company_exposure_score") or 3))
        )
        risk_score = likelihood_score * impact_score * exposure_score
        risk_level = self._risk_level_from_score(risk_score)

        insufficient = not linked
        if insufficient:
            risk_level = "low" if risk_level == "low" else "medium"
            confidence = "low"
        elif not company_evidence:
            # Industry/policy evidence alone cannot support a HIGH company risk.
            if self._has_evidence_backed_company_trigger(
                risk, company, intelligence
            ):
                verified = all(
                    item.verification_status == "verified"
                    for item in external_evidence
                )
                confidence = "high" if verified else "medium"
            else:
                risk_level = "low" if risk_level == "low" else "medium"
                confidence = "low"
        elif external_evidence:
            verified = all(
                item.verification_status == "verified"
                for item in [*company_evidence, *external_evidence]
            )
            confidence = "high" if verified else "medium"
        else:
            confidence = "medium"

        if any(item.verification_status == "contested" for item in linked):
            confidence = "low"
            risk_level = "medium" if risk_level == "high" else risk_level
            risk["verification_status"] = "contested"
        elif linked and all(
            item.verification_status == "outdated" for item in linked
        ):
            confidence = "low"
            risk_level = "low"
            risk["verification_status"] = "outdated"

        decision_relevance = str(
            risk.get("decision_relevance") or "medium"
        ).lower()
        if decision_relevance not in {"low", "medium", "high"}:
            decision_relevance = "medium"
        risk.update(
            {
                "title": str(
                    risk.get("title") or risk.get("name") or "Risk"
                ),
                "company_specific_trigger": str(
                    risk.get("company_specific_trigger")
                    or "Company-specific trigger requires verification."
                ),
                "external_mechanism": str(
                    risk.get("external_mechanism") or ""
                ),
                "impact_channels": [
                    str(item)
                    for item in (risk.get("impact_channels") or [])
                    if str(item).strip()
                ],
                "impact_description": str(
                    risk.get("impact_description")
                    or risk.get("business_impact")
                    or ""
                ),
                "likelihood_score": likelihood_score,
                "impact_score": impact_score,
                "company_exposure_score": exposure_score,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "severity": risk_level,
                "probability": likelihood_score * 20,
                "likelihood": self._likelihood_label(likelihood_score),
                "decision_relevance": decision_relevance,
                "confidence": confidence,
                "supporting_evidence_ids": list(
                    dict.fromkeys(
                        [*risk.get("supporting_evidence_ids", []), *[
                            link.evidence_id for link in links
                        ]]
                    )
                ),
                "insufficient_evidence": insufficient,
                "basis": "evidence" if linked else "inference",
                "uncertainty_reasons": [
                    str(item)
                    for item in (risk.get("uncertainty_reasons") or [])
                    if str(item).strip()
                ],
                "what_would_change_assessment": [
                    str(item)
                    for item in (
                        risk.get("what_would_change_assessment") or []
                    )
                    if str(item).strip()
                ],
            }
        )
        return risk

    def _deduplicate_risks(
        self,
        risks: list[RiskItem],
    ) -> list[RiskItem]:
        kept: list[RiskItem] = []
        for risk in risks:
            duplicate_index = None
            risk_terms = self._terms(f"{risk.category_key} {risk.title} {risk.name}")
            for index, existing in enumerate(kept):
                if existing.category_key != risk.category_key:
                    continue
                existing_terms = self._terms(
                    f"{existing.category_key} {existing.title} {existing.name}"
                )
                union = risk_terms | existing_terms
                similarity = (
                    len(risk_terms & existing_terms) / len(union)
                    if union
                    else 0.0
                )
                if similarity >= 0.55:
                    duplicate_index = index
                    break
            if duplicate_index is None:
                kept.append(risk)
                continue
            existing = kept[duplicate_index]
            if (
                risk.risk_score,
                self._decision_relevance_rank(risk.decision_relevance),
                self._confidence_rank(risk.confidence),
            ) > (
                existing.risk_score,
                self._decision_relevance_rank(existing.decision_relevance),
                self._confidence_rank(existing.confidence),
            ):
                kept[duplicate_index] = risk
        return kept

    @classmethod
    def _select_core_risks(
        cls,
        risks: list[RiskItem],
    ) -> list[RiskItem]:
        ranked = sorted(
            risks,
            key=lambda item: (
                cls._decision_relevance_rank(item.decision_relevance),
                item.risk_score,
                cls._confidence_rank(item.confidence),
            ),
            reverse=True,
        )[:5]
        return [
            item.model_copy(update={"risk_id": f"RSK-{index:03d}"})
            for index, item in enumerate(ranked, start=1)
        ]

    def _coerce_risks(
        self,
        payload: Any,
        fallback: list[dict[str, Any]],
        evidence: list[RetrievedEvidence],
        company: CompanyInput | None = None,
        intelligence: CompanyIntelligence | None = None,
    ) -> tuple[list[RiskItem], bool]:
        candidates = payload if isinstance(payload, list) else fallback
        system_risk_markers = (
            "information_quality",
            "data_quality",
            "data quality",
            "资料不足",
            "数据质量",
            "信息质量",
        )
        candidates = [
            item
            for item in candidates
            if isinstance(item, dict)
            and not any(
                marker
                in f"{item.get('name', '')} {item.get('title', '')} "
                f"{item.get('category', '')}".lower()
                for marker in system_risk_markers
            )
        ]
        allowed_ids = {item.evidence_id for item in evidence}
        mock_ids = {item.evidence_id for item in evidence if item.is_mock}
        risks: list[RiskItem] = []
        used_fallback = not isinstance(payload, list)

        try:
            for index, item in enumerate(candidates[:8], start=1):
                filtered = self._filter_fields(item, RiskItem)
                filtered["risk_id"] = f"RSK-{index:03d}"
                filtered["category_key"] = self._risk_category_key(
                    str(filtered.get("name") or ""),
                    str(filtered.get("category") or ""),
                )
                filtered["category"] = str(
                    filtered["category_key"]
                ).upper()
                filtered["title"] = str(
                    filtered.get("title") or filtered.get("name") or "Risk"
                )
                filtered["name"] = str(
                    filtered.get("name") or filtered["title"]
                )
                filtered["business_impact"] = str(
                    filtered.get("business_impact")
                    or filtered.get("impact_description")
                    or ""
                )
                uncertain_reasons = filtered.get("uncertainty_reasons") or []
                filtered["uncertainty"] = str(
                    filtered.get("uncertainty")
                    or (
                        "; ".join(str(item) for item in uncertain_reasons)
                        if isinstance(uncertain_reasons, list)
                        else uncertain_reasons
                    )
                    or "Uncertainty requires validation."
                )
                raw_ids = [
                    evidence_id
                    for evidence_id in (
                        filtered.get("evidence_ids")
                        or filtered.get("supporting_evidence_ids")
                        or []
                    )
                    if evidence_id in allowed_ids
                ]
                links = self._select_risk_evidence(
                    raw_ids,
                    str(filtered["category_key"]),
                    evidence,
                )
                evidence_ids = [link.evidence_id for link in links]
                filtered["evidence_ids"] = evidence_ids
                filtered["evidence_links"] = [
                    link.model_dump(mode="json") for link in links
                ]
                contested = self._detect_contested(links, evidence)
                verification_status = (
                    "contested"
                    if contested
                    else "unverified"
                    if not evidence_ids
                    else "partial"
                    if set(evidence_ids).issubset(mock_ids)
                    else "verified"
                )
                probability = int(filtered.get("probability") or 0)
                filtered["likelihood"] = filtered.get("likelihood") or (
                    "very_high"
                    if probability >= 85
                    else "high"
                    if probability >= 70
                    else "medium"
                    if probability >= 50
                    else "low"
                    if probability >= 25
                    else "very_low"
                )
                filtered["likelihood_basis"] = str(
                    filtered.get("likelihood_basis")
                    or (
                        "Linked evidence and user constraints support this likelihood."
                        if evidence_ids
                        else "No qualifying evidence was linked; likelihood is indicative."
                    )
                )
                filtered["basis"] = "evidence" if evidence_ids else "inference"
                filtered["insufficient_evidence"] = not bool(evidence_ids)
                filtered["severity"] = self._cap_severity_without_evidence(
                    filtered.get("severity"), bool(evidence_ids)
                )
                filtered["verification_status"] = verification_status
                filtered = self._apply_risk_rubric(
                    filtered, links, evidence, company, intelligence
                )
                risks.append(
                    RiskItem.model_validate(filtered).model_copy(
                        update={"risk_id": f"RSK-{index:03d}"}
                    )
                )
        except (ValidationError, TypeError, KeyError, AttributeError):
            used_fallback = True
            risks = []

        if not risks:
            for index, item in enumerate(fallback, start=1):
                category_key = self._risk_category_key(
                    str(item.get("name") or ""),
                    str(item.get("category") or ""),
                )
                links = self._select_risk_evidence(
                    [
                        evidence_id
                        for evidence_id in item.get("evidence_ids", [])
                        if evidence_id in allowed_ids
                    ],
                    category_key,
                    evidence,
                )
                evidence_ids = [link.evidence_id for link in links]
                contested = self._detect_contested(links, evidence)
                item = dict(item)
                item["category"] = category_key.upper()
                item["title"] = str(
                    item.get("title") or item.get("name") or "Risk"
                )
                item["name"] = str(
                    item.get("name") or item["title"]
                )
                item["business_impact"] = str(
                    item.get("business_impact")
                    or item.get("impact_description")
                    or ""
                )
                uncertain_reasons = item.get("uncertainty_reasons") or []
                item["uncertainty"] = str(
                    item.get("uncertainty")
                    or (
                        "; ".join(str(value) for value in uncertain_reasons)
                        if isinstance(uncertain_reasons, list)
                        else uncertain_reasons
                    )
                    or "Uncertainty requires validation."
                )
                risk_payload = self._apply_risk_rubric(
                    item, links, evidence, company, intelligence
                )
                risks.append(
                    RiskItem.model_validate(risk_payload).model_copy(
                        update={
                            "risk_id": f"RSK-{index:03d}",
                            "category_key": category_key,
                            "evidence_ids": evidence_ids,
                            "evidence_links": [
                                link.model_dump(mode="json") for link in links
                            ],
                            "verification_status": (
                                "contested"
                                if contested
                                else "unverified"
                                if not evidence_ids
                                else "partial"
                                if set(evidence_ids).issubset(mock_ids)
                                else "verified"
                            ),
                            "basis": "evidence" if evidence_ids else "inference",
                            "insufficient_evidence": not bool(evidence_ids),
                            "severity": self._cap_severity_without_evidence(
                                item.get("severity"), bool(evidence_ids)
                            ),
                        }
                    )
                )
        risks = self._select_core_risks(
            self._deduplicate_risks(risks)
        )
        return risks, used_fallback

    def _coerce_scenarios(
        self,
        payload: Any,
        fallback: list[dict[str, Any]],
        evidence: list[RetrievedEvidence],
        company: CompanyInput,
        *,
        risk_degraded: bool = False,
        scenario_model_ok: bool = True,
        intelligence: CompanyIntelligence | None = None,
    ) -> tuple[list[ScenarioResult], bool]:
        candidates = payload if isinstance(payload, list) else fallback
        allowed_ids = {item.evidence_id for item in evidence}
        scenarios: list[ScenarioResult] = []
        used_fallback = not isinstance(payload, list)
        critical_gap_count = sum(
            1
            for gap in (intelligence.information_gaps if intelligence else [])
            if (
                isinstance(gap, InformationGap)
                and gap.priority == "critical"
                and gap.status != "resolved"
            )
        )

        try:
            for index, item in enumerate(candidates[:5], start=1):
                filtered = self._filter_fields(item, ScenarioResult)
                filtered["scenario_id"] = f"SCN-{index:03d}"
                evidence_ids = [
                    evidence_id
                    for evidence_id in filtered.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                links = self._select_scenario_evidence(
                    evidence_ids, evidence
                )
                evidence_ids = [link.evidence_id for link in links]
                filtered["evidence_ids"] = evidence_ids
                filtered["evidence_links"] = [
                    link.model_dump(mode="json") for link in links
                ]
                filtered["insufficient_evidence"] = not bool(evidence_ids)
                filtered["weighted_score"] = 0
                assessments = self._scenario_dimension_assessments(
                    item, evidence
                )
                for metric in self.SCENARIO_METRIC_CONFIG:
                    filtered[metric] = self.SCENARIO_BAND_SCORES[
                        assessments[metric].band.value
                    ]
                filtered["dimension_assessments"] = {
                    metric: assessment.model_dump(mode="json")
                    for metric, assessment in assessments.items()
                }
                filtered["dimension_bands"] = {
                    metric: assessment.band
                    for metric, assessment in assessments.items()
                }
                scenario = ScenarioResult.model_validate(filtered).model_copy(
                    update={"scenario_id": f"SCN-{index:03d}"}
                )
                confidence_label, confidence_reasons = self._scenario_confidence(
                    scenario.evidence_ids,
                    evidence,
                    scenario=scenario,
                    risk_degraded=risk_degraded,
                    scenario_degraded=used_fallback or not scenario_model_ok,
                    critical_gap_count=critical_gap_count,
                )
                scenarios.append(
                    scenario.model_copy(
                        update={
                            "weighted_score": self._weighted_scenario_score(
                                scenario, company
                            ),
                            "score_breakdown": self._scenario_score_breakdown(
                                scenario, company
                            ),
                            "confidence": confidence_label,
                            "confidence_reasons": confidence_reasons,
                        }
                    )
                )
        except (ValidationError, TypeError, KeyError, AttributeError):
            used_fallback = True
            scenarios = []

        if len(scenarios) < 2:
            used_fallback = True
            scenarios = []
            for index, item in enumerate(fallback, start=1):
                evidence_ids = [
                    evidence_id
                    for evidence_id in item.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                links = self._select_scenario_evidence(
                    evidence_ids, evidence
                )
                evidence_ids = [link.evidence_id for link in links]
                assessments = self._scenario_dimension_assessments(
                    item, evidence
                )
                scored_item = dict(item)
                for metric in self.SCENARIO_METRIC_CONFIG:
                    scored_item[metric] = self.SCENARIO_BAND_SCORES[
                        assessments[metric].band.value
                    ]
                scored_item["dimension_assessments"] = {
                    metric: assessment.model_dump(mode="json")
                    for metric, assessment in assessments.items()
                }
                scored_item["dimension_bands"] = {
                    metric: assessment.band
                    for metric, assessment in assessments.items()
                }
                scenario = ScenarioResult.model_validate(scored_item).model_copy(
                    update={
                        "scenario_id": f"SCN-{index:03d}",
                        "evidence_ids": evidence_ids,
                        "evidence_links": [
                            link.model_dump(mode="json") for link in links
                        ],
                        "insufficient_evidence": not bool(evidence_ids),
                    }
                )
                confidence_label, confidence_reasons = self._scenario_confidence(
                    scenario.evidence_ids,
                    evidence,
                    scenario=scenario,
                    risk_degraded=risk_degraded,
                    scenario_degraded=True,
                    critical_gap_count=critical_gap_count,
                )
                scenarios.append(
                    scenario.model_copy(
                        update={
                            "weighted_score": self._weighted_scenario_score(
                                scenario, company
                            ),
                            "score_breakdown": self._scenario_score_breakdown(
                                scenario, company
                            ),
                            "confidence": confidence_label,
                            "confidence_reasons": confidence_reasons,
                        }
                    )
                )
        return scenarios, used_fallback

    @staticmethod
    def _rank_scenarios(
        scenarios: list[ScenarioResult],
    ) -> list[ScenarioResult]:
        ranked = sorted(
            scenarios,
            key=lambda item: item.weighted_score,
            reverse=True,
        )
        return [
            item.model_copy(update={"scenario_id": f"SCN-{index:03d}"})
            for index, item in enumerate(ranked, start=1)
        ]

    def _coerce_recommendation(
        self,
        payload: Any,
        heuristic: dict[str, Any],
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[RiskItem],
        scenarios: list[ScenarioResult],
    ) -> tuple[Recommendation, list[str], bool]:
        used_fallback = False
        candidate = (
            payload.get("recommendation")
            if isinstance(payload, dict)
            else heuristic["recommendation"]
        )
        limitations = (
            payload.get("limitations")
            if isinstance(payload, dict)
            and isinstance(payload.get("limitations"), list)
            else heuristic["limitations"]
        )
        try:
            filtered = self._filter_fields(candidate, Recommendation)
            recommendation = Recommendation.model_validate(filtered)
        except (ValidationError, TypeError, KeyError, AttributeError):
            used_fallback = True
            recommendation = Recommendation.model_validate(
                heuristic["recommendation"]
            )

        scenario_ids = {item.scenario_id for item in scenarios}
        if recommendation.recommended_scenario_id not in scenario_ids:
            used_fallback = True
            best = max(scenarios, key=lambda item: item.weighted_score)
            recommendation = recommendation.model_copy(
                update={
                    "recommended_scenario_id": best.scenario_id,
                    "rationale": (
                        f"模型返回的方案编号无效，已调整为综合得分最高的"
                        f"{best.name}。{recommendation.rationale}"
                    ),
                }
            )
        selected_scenario = next(
            (
                item
                for item in scenarios
                if item.scenario_id == recommendation.recommended_scenario_id
            ),
            None,
        )
        if selected_scenario is not None:
            recommendation = recommendation.model_copy(
                update={"evidence_ids": selected_scenario.evidence_ids}
            )

        requires_review = (
            any(item.severity in {"high", "critical"} for item in risks)
            or any(
                item.verification_status in {
                    "unverified",
                    "contested",
                    "outdated",
                }
                for item in risks
            )
        )
        recommendation = recommendation.model_copy(
            update={"requires_human_review": requires_review}
        )
        confidence, confidence_score, confidence_reasons = (
            self._calculate_confidence(
                company,
                evidence,
                risks,
                scenarios,
                requires_review,
            )
        )
        recommendation = recommendation.model_copy(
            update={
                "confidence": confidence,
                "confidence_score": confidence_score,
                "confidence_reasons": confidence_reasons,
            }
        )
        return recommendation, [str(item) for item in limitations], used_fallback

    @staticmethod
    def _calculate_confidence(
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[RiskItem],
        scenarios: list[ScenarioResult],
        requires_human_review: bool,
    ) -> tuple[str, int, list[str]]:
        score = 0
        reasons: list[str] = []

        evidence_score = 0
        if evidence:
            evidence_score += min(15, len(evidence))
            reasons.append(f"本次检索到 {len(evidence)} 条证据。")
        authoritative = [
            item for item in evidence if item.authority_level in {"A", "B"}
        ]
        if evidence and len(authoritative) / len(evidence) >= 0.7:
            evidence_score += 12
            reasons.append("主要证据来自高权威等级来源。")
        live_items = [
            item for item in evidence if item.source_type.startswith("live_")
        ]
        if live_items:
            evidence_score += 5
            reasons.append(f"包含 {len(live_items)} 条联网检索结果。")
        if evidence and not any(item.is_mock for item in evidence):
            evidence_score += 5
            reasons.append("当前证据不包含 Mock 数据。")
        if len({item.publisher for item in evidence}) >= 4:
            evidence_score += 10
            reasons.append("证据来源具有多样性。")
        score += min(45, evidence_score)

        company_score = 0
        if company.hs_codes:
            company_score += 10
            reasons.append("已提供 HS/ECCN 等产品分类信息。")
        else:
            reasons.append("缺少 HS/ECCN 分类会降低确定性。")
        if company.investment_budget_usd is not None:
            company_score += 8
            reasons.append("已提供投资预算约束。")
        else:
            reasons.append("缺少投资预算会限制情景量化。")
        if company.key_supplier_count is not None:
            company_score += 6
            reasons.append("已提供关键供应商数量。")
        if company.largest_supplier_share is not None:
            company_score += 5
            reasons.append("已提供最大供应商集中度。")
        if company.has_verified_bom:
            company_score += 8
            reasons.append("已确认存在经过核验的 BOM。")
        else:
            reasons.append("缺少经核验 BOM，无法映射物料级风险。")
        score += min(35, company_score)

        verification_score = 0
        if all(
            item.evidence_ids and item.verification_status != "unverified"
            for item in risks
        ):
            verification_score += 10
            reasons.append("全部风险均关联到可追溯证据。")
        if all(item.evidence_ids for item in scenarios):
            verification_score += 10
            reasons.append("全部情景均包含证据引用。")
        score += min(20, verification_score)

        high_risk_count = sum(
            item.severity in {"high", "critical"} for item in risks
        )
        if high_risk_count:
            score -= min(6, high_risk_count)
            reasons.append(f"存在 {high_risk_count} 项高风险，已下调置信度。")
        if requires_human_review:
            score -= 2
            reasons.append("关键结论需要人工复核。")

        score = max(0, min(100, score))
        if score >= 75:
            confidence = "high"
        elif score >= 45:
            confidence = "medium"
        else:
            confidence = "low"
        return confidence, score, reasons[:8]

    # Dimensions the scenario score can weight. Declared here so an unranked
    # decision can default to equal weights across all of them.
    SCORING_DIMENSIONS = (
        "cost_reduction",
        "supply_chain_resilience",
        "market_access",
        "political_stability",
        "compliance",
    )
    EQUAL_WEIGHT = 3
    SCENARIO_BAND_SCORES = {
        "very_favourable": 85,
        "favourable": 70,
        "neutral": 55,
        "unfavourable": 35,
        "very_unfavourable": 20,
    }
    SCENARIO_METRIC_CONFIG = {
        "cost_score": ("cost", "cost_reduction", 1.0),
        "resilience_score": (
            "resilience",
            "supply_chain_resilience",
            1.0,
        ),
        "geopolitical_risk_score": (
            "geopolitical_risk",
            "political_stability",
            1.0,
        ),
        "market_access_score": ("market_access", "market_access", 1.0),
        "implementation_score": (
            "implementation",
            "compliance",
            0.5,
        ),
    }

    @classmethod
    def _effective_weights(cls, company: CompanyInput) -> dict[str, int]:
        """Weights used for scenario scoring.

        The priority ranking lives in the optional Advanced assessment. When the
        user never ranked the factors, an arbitrary default order (resilience 5,
        cost 1, ...) must not drive the result — every dimension is weighted the
        same instead. Equal weights are also the fallback when a declared ranking
        would produce a zero total.
        """
        if not company.priorities_declared:
            return {dimension: cls.EQUAL_WEIGHT for dimension in cls.SCORING_DIMENSIONS}
        declared = {item.dimension: item.weight for item in company.priorities}
        weights = {
            dimension: declared.get(dimension, cls.EQUAL_WEIGHT)
            for dimension in cls.SCORING_DIMENSIONS
        }
        if sum(weights.values()) <= 0:
            return {dimension: cls.EQUAL_WEIGHT for dimension in cls.SCORING_DIMENSIONS}
        return weights

    @classmethod
    def _weighted_scenario_score(
        cls,
        scenario: ScenarioResult,
        company: CompanyInput,
    ) -> float:
        weights = cls._effective_weights(company)
        metric_weights = {
            "cost_score": ("cost_reduction", 1.0),
            "resilience_score": ("supply_chain_resilience", 1.0),
            "geopolitical_risk_score": ("political_stability", 1.0),
            "market_access_score": ("market_access", 1.0),
            "implementation_score": ("compliance", 0.5),
        }
        total_weight = sum(
            weights[dimension] * factor
            for dimension, factor in metric_weights.values()
        )
        score = sum(
            getattr(scenario, metric)
            * weights[dimension]
            * factor
            / total_weight
            for metric, (dimension, factor) in metric_weights.items()
        )
        return round(score, 1)

    @staticmethod
    def _score_band(score: int) -> str:
        if score >= 85:
            return "very_favourable"
        if score >= 70:
            return "favourable"
        if score >= 45:
            return "neutral"
        if score >= 30:
            return "unfavourable"
        return "very_unfavourable"

    @staticmethod
    def _scenario_score_breakdown(
        scenario: ScenarioResult,
        company: CompanyInput,
    ) -> list[ScenarioScoreBreakdown]:
        weights = {item.dimension: item.weight for item in company.priorities}
        metric_weights = {
            "cost_score": ("cost_reduction", 1.0),
            "resilience_score": ("supply_chain_resilience", 1.0),
            "geopolitical_risk_score": ("political_stability", 1.0),
            "market_access_score": ("market_access", 1.0),
            "implementation_score": ("compliance", 0.5),
        }
        total = sum(
            weights.get(dimension, 3) * factor
            for dimension, factor in metric_weights.values()
        )
        breakdown = []
        for metric, (dimension, factor) in metric_weights.items():
            weight = weights.get(dimension, 3) * factor
            score = float(getattr(scenario, metric))
            assessment = scenario.dimension_assessments.get(metric)
            basis = assessment.source if assessment else "inference"
            breakdown.append(
                {
                    "dimension": metric,
                    "band": assessment.band if assessment else "neutral",
                    "score": score,
                    "weight": weight,
                    "contribution": round(score * weight / total, 2),
                    "reason": assessment.reason if assessment else "",
                    "source": assessment.source if assessment else "inference",
                    "basis": basis,
                    "evidence_ids": (
                        assessment.evidence_ids
                        if assessment
                        else []
                    ),
                }
            )
        return [
            ScenarioScoreBreakdown.model_validate(item)
            for item in breakdown
        ]

    @staticmethod
    def _filter_fields(item: Any, model: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise TypeError("model payload must be an object")
        allowed = set(model.model_fields)
        return {key: value for key, value in item.items() if key in allowed}

    @staticmethod
    def _validate_citations(
        risks: list[RiskItem],
        scenarios: list[ScenarioResult],
        evidence: list[RetrievedEvidence],
        recommendation: Recommendation | None = None,
    ) -> bool:
        allowed_ids = {item.evidence_id for item in evidence}
        base_valid = all(
            (
                item.insufficient_evidence
                and not item.evidence_ids
            )
            or (
                bool(item.evidence_ids)
                and set(item.evidence_ids).issubset(allowed_ids)
            )
            for item in [*risks, *scenarios]
        )
        if not base_valid or recommendation is None:
            return base_valid
        chosen = next(
            (
                item
                for item in scenarios
                if item.scenario_id == recommendation.recommended_scenario_id
            ),
            None,
        )
        return bool(
            chosen
            and set(recommendation.evidence_ids).issubset(
                set(chosen.evidence_ids)
            )
        )

    @staticmethod
    def _emit_event(
        callback: EventCallback | None,
        event: dict[str, Any],
    ) -> None:
        if callback:
            callback(event)

    @staticmethod
    def _trace(
        agent: str,
        action: str,
        status: str,
        detail: str,
        started: float,
    ) -> TraceStep:
        return TraceStep(
            step_id=f"TRC-{uuid.uuid4().hex[:8].upper()}",
            agent=agent,
            action=action,
            status=status,
            detail=detail,
            started_at=utc_now(),
            duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
        )


    # Company Intelligence is the shared company context for every downstream
    # stage. The full object is large, so prompts receive a bounded projection.
    INTELLIGENCE_BRIEF_LIMITS = {
        "overview": 4,
        "production_footprint": 6,
        "supply_chain": 6,
        "supply_chain_structure": 4,
        "market_position": 4,
        "strategic_context": 2,
        "information_gaps": 5,
        "manufacturing_footprint": 6,
        "evidence_references": 8,
    }
    INTELLIGENCE_BRIEF_FACT_CHARS = 240

    @classmethod
    def intelligence_brief(
        cls, intelligence: CompanyIntelligence | None
    ) -> dict[str, Any]:
        """Compact company context handed to Risk, Scenario, Advisor and Chat."""
        if intelligence is None:
            return {}
        limits = cls.INTELLIGENCE_BRIEF_LIMITS
        chars = cls.INTELLIGENCE_BRIEF_FACT_CHARS

        def facts(items: list[Any], key: str) -> list[dict[str, Any]]:
            collected = []
            for item in (items or [])[: limits.get(key, 4)]:
                text = str(getattr(item, "fact", "") or "").strip()
                if not text:
                    continue
                collected.append(
                    {
                        "fact": text[:chars],
                        "status": getattr(item, "data_status", "") or "",
                        "source_ids": list(getattr(item, "source_ids", []) or []),
                    }
                )
            return collected

        entity = intelligence.entity
        return {
            "executive_summary": (intelligence.executive_summary or "")[:600],
            "identity": {
                "legal_name": entity.legal_name,
                "aliases": entity.aliases[:5],
                "headquarters": entity.headquarters,
                "listing": entity.listing.model_dump(mode="json"),
                "founded_year": entity.founded_year,
                "size": entity.size.model_dump(mode="json"),
            },
            "overview": facts(intelligence.overview, "overview"),
            "production_footprint": facts(
                intelligence.production_footprint, "production_footprint"
            ),
            "supply_chain": facts(intelligence.supply_chain, "supply_chain"),
            "supply_chain_structure": [
                {
                    "stage": item.stage,
                    "description": (item.description or "")[:chars],
                    "region": item.region,
                    "company_role": item.company_role,
                    "share": item.share,
                    "share_basis": item.share_basis,
                }
                for item in (intelligence.supply_chain_structure or [])[
                    : limits["supply_chain_structure"]
                ]
            ],
            "market_position": facts(
                intelligence.market_position, "market_position"
            ),
            "strategic_context": facts(
                intelligence.strategic_context, "strategic_context"
            ),
            "business_profile": intelligence.business_profile.model_dump(
                mode="json"
            ),
            "manufacturing_footprint": [
                item.model_dump(mode="json")
                for item in intelligence.manufacturing_footprint[
                    : limits["manufacturing_footprint"]
                ]
            ],
            "supply_chain_role": intelligence.supply_chain_role.model_dump(
                mode="json"
            ),
            "decision_context": intelligence.decision_context.model_dump(
                mode="json"
            ),
            "evidence_references": [
                item.model_dump(mode="json")
                for item in intelligence.evidence_references[
                    : limits["evidence_references"]
                ]
            ],
            "information_gaps": [
                (
                    {
                        "item": gap.item[:chars],
                        "priority": gap.priority,
                        "why_it_matters": gap.why_it_matters[:chars],
                        "recommended_action": gap.recommended_action[:chars],
                    }
                    if isinstance(gap, InformationGap)
                    else {"item": str(gap)[:chars], "priority": "important"}
                )
                for gap in (intelligence.information_gaps or [])[
                    : limits["information_gaps"]
                ]
            ],
        }

    def _build_intelligence(
        self,
        company: CompanyInput,
        profile: CompanyProfile,
        evidence: list[RetrievedEvidence],
        language: str = "en",
    ) -> dict[str, Any]:
        """Company intelligence from the given inputs plus retrieved evidence.

        Facts the user stated are labelled user_input; anything supported by a
        retrieved source is public_source; everything else is marked as inferred or
        left in information_gaps rather than presented as fact.
        """
        zh = (language or "en").lower() == "zh"
        evidence_ids = [item.evidence_id for item in evidence[:3]]

        def fact(text: str, status: str, ids: list[str] | None = None) -> dict[str, Any]:
            return {"fact": text, "source_ids": list(ids or []), "data_status": status}

        products = ", ".join(company.products) or ("未提供" if zh else "not provided")
        footprint = ", ".join(
            f"{item.country} {item.production_share}%"
            for item in company.production_locations
        ) or ("未提供" if zh else "not provided")
        markets = ", ".join(company.target_markets) or ("未提供" if zh else "not provided")
        drivers = ", ".join(company.restrictions) or ("未提供" if zh else "not provided")

        if zh:
            overview = [
                fact(f"{company.company_name}，主要产品：{products}", "user_input"),
                fact(f"母国：{company.home_country}", "user_input"),
                fact("公司官网、年报或其他权威公司资料中的实体与业务信息", "to_be_confirmed", evidence_ids),
                fact("业务模式与在电池产业链中的具体环节", "to_be_confirmed"),
            ]
            production = [
                fact(f"生产分布：{footprint}", "user_input"),
                fact(f"目标市场：{markets}", "user_input"),
                fact("各基地的实际产能与产能利用率", "to_be_confirmed"),
                fact("各基地承担的环节（研发 / 原材料 / 零部件 / 制造 / 组装 / 出口）", "to_be_confirmed"),
            ]
            supply = [
                fact("关键原材料与零部件的供应来源", "to_be_confirmed"),
                fact("是否存在单一来源或难以替代的供应商", "to_be_confirmed"),
                fact("公开资料对供应链结构的支持有限，需要企业数据核验。", "inferred", evidence_ids),
            ]
            strategic = [
                fact(
                    f"公司现状：{company.company_name} 是一家{products}相关企业；"
                    "具体的业务模式与价值链位置有待公开披露核验。",
                    "user_input",
                ),
                fact("供应链结构与依赖：关键供应商与物料来源仍待确认。", "inferred"),
                fact(
                    "经营结构与布局逻辑：现有公开证据不足以说明该公司的全球生产与"
                    "供应链布局逻辑。",
                    "inferred",
                ),
                fact(
                    "关键未知信息：缺少产能、供应商、客户结构与成本数据，"
                    "进一步分析前需要补齐。",
                    "inferred",
                ),
            ]
            market_position = [
                fact("公司在目标市场的份额、客户认证和市场地位", "to_be_confirmed"),
            ]
            gaps = [
                "各基地实际产能与利用率",
                "关键原材料与零部件来源",
                "海外设施的股权与运营结构",
                "产品对应的关税分类与原产地规则",
            ]
        else:
            overview = [
                fact(f"{company.company_name} — core products: {products}", "user_input"),
                fact(f"Home country: {company.home_country}", "user_input"),
                fact("Entity and business facts available from authoritative company sources", "to_be_confirmed", evidence_ids),
                fact("Business model and exact position in the battery value chain", "to_be_confirmed"),
            ]
            production = [
                fact(f"Production footprint: {footprint}", "user_input"),
                fact(f"Target markets: {markets}", "user_input"),
                fact("Actual capacity and utilisation per site", "to_be_confirmed"),
                fact("Which activities each site performs (R&D / materials / components / manufacturing / assembly / export)", "to_be_confirmed"),
            ]
            supply = [
                fact("Origins of critical raw materials and components", "to_be_confirmed"),
                fact("Whether any input relies on a single or hard-to-replace supplier", "to_be_confirmed"),
                fact("Public sources give limited visibility on the supply-chain structure; company data is needed to verify it.", "inferred", evidence_ids),
            ]
            strategic = [
                fact(
                    f"Current Position: {company.company_name} operates {footprint} "
                    f"and serves {markets}.",
                    "user_input",
                ),
                fact("Supply-chain structure and dependencies: critical supplier and material dependencies remain to be confirmed.", "inferred"),
                fact("Market and customer positioning: target markets, customer structure and certifications remain to be confirmed.", "inferred"),
                fact(
                    f"Decision context and information needs: {company.decision_question}; decision drivers: {drivers}.",
                    "user_input",
                ),
            ]
            market_position = [
                fact("Market share, customer certifications and competitive position", "to_be_confirmed"),
            ]
            gaps = [
                "Actual production capacity and utilisation by location",
                "Critical raw material and component supplier origins",
                "Ownership and operational structure of overseas facilities",
                "Product-specific tariff classification and rules of origin",
            ]
        structured_gaps = [
            {
                "item": gap,
                "priority": "critical" if index < 2 else "important",
                "why_it_matters": (
                    "This information is required to validate the company profile "
                    "and downstream decisions."
                ),
                "recommended_action": (
                    "Obtain the relevant company filing, official document or "
                    "internal data before relying on this conclusion."
                ),
                "source_ids": [],
            }
            for index, gap in enumerate(gaps)
        ]
        return {
            "executive_summary": (
                f"{company.company_name} 的企业画像需基于用户 Baseline、公司实体证据和"
                "政策证据形成，优先解决实体确认、供应链依赖和市场准入问题。"
                if zh
                else f"{company.company_name}'s intelligence profile must combine the "
                "user baseline, company entity evidence and policy evidence, prioritizing "
                "entity confirmation, supply-chain dependencies and market access."
            ),
            "entity": self._coerce_entity(None, company).model_dump(mode="json"),
            "overview": overview,
            "production_footprint": production,
            "supply_chain": supply,
            "strategic_context": strategic,
            "market_position": market_position,
            "business_profile": {
                "model": "",
                "value_chain_role": "",
                "products": company.products,
                "customers": [],
                "source_ids": [],
            },
            "manufacturing_footprint": [
                {
                    "country": location.country,
                    "facility": "",
                    "role": "",
                    "production_share": location.production_share,
                    "capacity": "unknown",
                    "source_type": "user_input",
                    "status": "reported",
                    "source_ids": [],
                }
                for location in company.production_locations
            ],
            "supply_chain_role": {
                "primary": SUPPLY_CHAIN_ROLE_FALLBACK,
                "secondary": [],
                "upstream": [],
                "manufacturing": [],
                "downstream": [],
                "unknown": [
                    "Upstream supplier structure",
                    "Manufacturing site capabilities",
                    "Downstream customer structure",
                ],
            },
            "decision_context": {
                "objective": company.decision_question,
                "drivers": list(company.restrictions),
                "constraints": [],
                "source_ids": [],
            },
            "evidence_references": [
                {
                    "evidence_id": item.evidence_id,
                    "title": item.title,
                    "publisher": item.publisher,
                    "source_type": item.source_type,
                    "used_for": ["company_intelligence"],
                }
                for item in evidence
                if item.evidence_id in set(evidence_ids)
            ],
            "information_gaps": structured_gaps,
        }

    @staticmethod
    def _coerce_entity(payload: Any, company: CompanyInput) -> CompanyEntity:
        fallback = CompanyEntity(
            legal_name=company.company_name,
            aliases=[company.company_name],
            headquarters=company.home_country,
            data_status="user_input",
        )
        if not isinstance(payload, dict):
            return fallback
        payload = AgentService._unwrap_dict(payload)
        try:
            entity = CompanyEntity.model_validate(payload)
        except (ValidationError, TypeError, ValueError):
            return fallback
        return entity.model_copy(
            update={
                "legal_name": entity.legal_name or company.company_name,
                "aliases": list(
                    dict.fromkeys(
                        [company.company_name, *entity.aliases]
                    )
                ),
                "headquarters": entity.headquarters or company.home_country,
            }
        )

    @staticmethod
    def _text_of(value: Any) -> str:
        """Flatten one model field to plain text.

        Models sometimes answer with a nested object (`{"narrative": "..."}`)
        where the schema expects a string. Converting that with `str()` leaks
        Python dict syntax into the UI, so the known text keys are unwrapped
        explicitly and anything else becomes an empty string.
        """
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in (
                "fact",
                "narrative",
                "text",
                "summary",
                "statement",
                "content",
                "value",
            ):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            return ""
        if isinstance(value, (int, float)):
            return str(value)
        return ""

    # The four required strategic-context paragraphs are labelled by the backend,
    # so the labels must follow the requested output language instead of leaking
    # the English prompt wording into a Chinese report.
    STRATEGIC_SECTION_LABELS = {
        "en": (
            "Current Position",
            "Supply-chain structure and dependencies",
            "Market and customer positioning",
            "Decision context and information needs",
        ),
        "zh": (
            "公司现状",
            "供应链结构与依赖",
            "市场与客户定位",
            "决策情境与待补信息",
        ),
    }
    STRATEGIC_SECTION_KEYS = (
        "Current Position",
        "current_position",
        "Supply-chain structure and dependencies",
        "supply_chain_structure",
        "Market and customer positioning",
        "market_customer_positioning",
        "Decision context and information needs",
        "decision_context_information_needs",
        # Backward-compatible labels from the previous intelligence contract.
        "Market and geopolitical exposure",
        "market_geopolitical_exposure",
        "Decision tension",
        "decision_tension",
    )

    @classmethod
    def _unwrap_list(cls, value: Any, language: str = "en") -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in (
                "items",
                "facts",
                "entries",
                "results",
                "gaps",
                "value",
            ):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return candidate
            zh = (language or "en").lower() == "zh"
            labels = cls.STRATEGIC_SECTION_LABELS["zh" if zh else "en"]
            separator = "：" if zh else ": "
            strategic_items = []
            for index, key in enumerate(cls.STRATEGIC_SECTION_KEYS):
                if key not in value or not value[key]:
                    continue
                text = cls._text_of(value[key])
                if not text:
                    continue
                strategic_items.append(
                    {"fact": f"{labels[min(index // 2, 3)]}{separator}{text}"}
                )
            if strategic_items:
                return strategic_items
            string_items = [
                {"fact": text}
                for candidate in value.values()
                if (text := cls._text_of(candidate))
            ]
            if string_items:
                return string_items
            for candidate in value.values():
                if isinstance(candidate, list):
                    return candidate
        return []

    @staticmethod
    def _unwrap_dict(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        for key in ("entity", "data", "result", "value"):
            candidate = value.get(key)
            if isinstance(candidate, dict):
                return candidate
        return value

    def _coerce_intelligence(
        self,
        payload: Any,
        company: CompanyInput,
        profile: CompanyProfile,
        evidence: list[RetrievedEvidence],
        language: str = "en",
        entity: CompanyEntity | None = None,
    ) -> tuple[CompanyIntelligence, bool]:
        fallback = self._build_intelligence(company, profile, evidence, language)
        if not isinstance(payload, dict) or not payload:
            return CompanyIntelligence.model_validate(fallback), True
        allowed = {item.evidence_id for item in evidence}
        evidence_by_id = {item.evidence_id: item for item in evidence}
        valid_status = {"user_input", "public_source", "inferred", "to_be_confirmed"}
        sections: dict[str, Any] = {}
        used_fallback = False
        provided_sections = 0
        for key in (
            "overview",
            "production_footprint",
            "supply_chain",
            "strategic_context",
            "market_position",
        ):
            cleaned = []
            for item in self._unwrap_list(payload.get(key), language):
                # A model that answers a paragraph section with bare strings is
                # still usable; without this the whole section silently fell back
                # to the baseline, which repeats the user's form input.
                if isinstance(item, str):
                    item = {"fact": item}
                if not isinstance(item, dict):
                    continue
                nested = item.get("fact")
                if isinstance(nested, dict):
                    item = {**item, **nested}
                text = self._text_of(item.get("fact"))
                if not text or self._is_schema_noise(text):
                    continue
                ids = [
                    value
                    for value in (item.get("source_ids") or [])
                    if value in allowed
                ]
                status = str(item.get("data_status") or "").strip()
                if status not in valid_status:
                    status = "public_source" if ids else "inferred"
                if status == "public_source" and not self._fact_source_supports(
                    text, ids, evidence_by_id
                ):
                    status = "inferred" if ids else "to_be_confirmed"
                confidence = str(item.get("confidence") or "").strip()
                if confidence not in {"low", "medium", "high"}:
                    confidence = (
                        "high"
                        if status == "user_input"
                        else "medium"
                        if status == "public_source"
                        else "low"
                    )
                cleaned.append(
                    {
                        "fact_id": str(
                            item.get("fact_id")
                            or f"FCT-{key.upper()}-{len(cleaned) + 1:03d}"
                        ),
                        "fact": text,
                        "source_ids": ids,
                        "data_status": status,
                        "confidence": confidence,
                        "as_of": str(item.get("as_of") or ""),
                        "derived_from": [
                            str(value)
                            for value in (item.get("derived_from") or [])
                            if str(value).strip()
                        ],
                        "conflict": bool(item.get("conflict")),
                    }
                )
            sections[key] = cleaned or fallback[key]
            if cleaned:
                provided_sections += 1
        if provided_sections == 0:
            used_fallback = True
        raw_gaps = self._unwrap_list(
            payload.get("information_gaps"), language
        )
        gaps: list[InformationGap] = []
        for item in raw_gaps:
            if isinstance(item, dict):
                text = self._text_of(
                    item.get("item")
                    or item.get("gap")
                    or item.get("fact")
                    or item.get("narrative")
                )
                priority = str(item.get("priority") or "important").lower()
                if priority not in {"critical", "important", "optional"}:
                    priority = "important"
                source_ids = [
                    source_id
                    for source_id in (item.get("source_ids") or [])
                    if source_id in allowed
                ]
                if text:
                    gaps.append(
                        InformationGap(
                            item=text,
                            priority=priority,
                            why_it_matters=str(
                                item.get("why_it_matters") or ""
                            ),
                            recommended_action=str(
                                item.get("recommended_action") or ""
                            ),
                            source_ids=source_ids,
                        )
                    )
            else:
                text = self._text_of(item)
                if text:
                    gaps.append(InformationGap(item=text))
        if not gaps:
            gaps = [
                gap
                if isinstance(gap, InformationGap)
                else InformationGap(item=str(gap))
                for gap in fallback["information_gaps"]
            ]
        # Doc §6: "few and useful" — cap each priority band and drop duplicates.
        gaps = self._cap_information_gaps(gaps)
        entity_payload = self._unwrap_dict(payload.get("entity"))
        resolved_entity = self._coerce_entity(
            entity_payload if isinstance(entity_payload, dict) else None,
            company,
        )
        if entity is not None:
            resolved_entity = entity.model_copy(
                update={
                    "aliases": list(
                        dict.fromkeys([*entity.aliases, *resolved_entity.aliases])
                    )
                }
            )
        resolved_entity = resolved_entity.model_copy(
            update={
                "source_ids": [
                    item for item in resolved_entity.source_ids if item in allowed
                ]
            }
        )
        resolved_entity = self._enrich_entity_from_evidence(
            resolved_entity, evidence
        )
        raw_executive_summary = payload.get("executive_summary")
        if isinstance(raw_executive_summary, dict):
            summary_text = str(
                raw_executive_summary.get("summary")
                or raw_executive_summary.get("headline")
                or raw_executive_summary.get("text")
                or ""
            ).strip()
            findings = raw_executive_summary.get("key_findings") or []
            finding_text = " ".join(
                str(item.get("fact") or "")
                for item in findings
                if isinstance(item, dict)
            ).strip()
            raw_executive_summary = " ".join(
                item for item in (summary_text, finding_text) if item
            )
        executive_summary = str(
            raw_executive_summary
            or fallback.get("executive_summary")
            or ""
        ).strip()

        business_data = self._unwrap_dict(payload.get("business_profile"))
        business_data["source_ids"] = [
            source_id
            for source_id in (business_data.get("source_ids") or [])
            if source_id in allowed
        ]
        try:
            business_profile = BusinessProfile.model_validate(business_data)
        except (ValidationError, TypeError, ValueError):
            business_profile = BusinessProfile.model_validate(
                fallback["business_profile"]
            )

        manufacturing_sites: list[ManufacturingSite] = []
        for item in self._unwrap_list(
            payload.get("manufacturing_footprint"), language
        ):
            if not isinstance(item, dict):
                continue
            filtered = {
                key: value
                for key, value in item.items()
                if key in ManufacturingSite.model_fields
            }
            filtered["source_ids"] = [
                source_id
                for source_id in (filtered.get("source_ids") or [])
                if source_id in allowed
            ]
            try:
                manufacturing_sites.append(
                    ManufacturingSite.model_validate(filtered)
                )
            except (ValidationError, TypeError, ValueError):
                continue
        if not manufacturing_sites:
            manufacturing_sites = [
                ManufacturingSite.model_validate(item)
                for item in fallback["manufacturing_footprint"]
            ]
        # Company Research and Company Intelligence already know bases the form
        # never asked about; this puts them in the same table as the user's own
        # layout without inventing shares or capacity for them.
        manufacturing_sites = self._merge_manufacturing_footprint(
            manufacturing_sites, company, evidence_by_id
        )

        role_data = self._unwrap_dict(payload.get("supply_chain_role"))
        try:
            supply_chain_role = SupplyChainRole(
                # Free-text answers are normalised onto the controlled vocabulary
                # instead of being stored as-is.
                primary=self._normalise_supply_chain_role(role_data.get("primary")),
                secondary=self._normalise_supply_chain_roles(
                    role_data.get("secondary")
                ),
                upstream=self._coerce_fact_list(
                    role_data.get("upstream"),
                    "SC-UPSTREAM",
                    allowed,
                    evidence_by_id,
                    language,
                ),
                manufacturing=self._coerce_fact_list(
                    role_data.get("manufacturing"),
                    "SC-MANUFACTURING",
                    allowed,
                    evidence_by_id,
                    language,
                ),
                downstream=self._coerce_fact_list(
                    role_data.get("downstream"),
                    "SC-DOWNSTREAM",
                    allowed,
                    evidence_by_id,
                    language,
                ),
                unknown=[
                    *self._coerce_string_list(role_data.get("unknown")),
                ],
            )
        except (ValidationError, TypeError, ValueError):
            supply_chain_role = SupplyChainRole.model_validate(
                fallback["supply_chain_role"]
            )

        decision_data = self._unwrap_dict(payload.get("decision_context"))
        # The model sometimes answers with objects where a string list is
        # expected; flatten them rather than failing validation and losing the
        # whole block to the baseline.
        decision_data["drivers"] = self._coerce_string_list(
            decision_data.get("drivers")
        )
        decision_data["constraints"] = self._coerce_string_list(
            decision_data.get("constraints")
        )
        decision_data["source_ids"] = [
            source_id
            for source_id in (decision_data.get("source_ids") or [])
            if source_id in allowed
        ]
        try:
            decision_context = DecisionContext.model_validate(decision_data)
        except (ValidationError, TypeError, ValueError):
            decision_context = DecisionContext.model_validate(
                fallback["decision_context"]
            )

        references: list[EvidenceReference] = []
        for item in self._unwrap_list(
            payload.get("evidence_references"), language
        ):
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("evidence_id") or "")
            source = evidence_by_id.get(evidence_id)
            if source is None:
                continue
            references.append(
                EvidenceReference(
                    evidence_id=evidence_id,
                    title=str(item.get("title") or source.title),
                    publisher=str(item.get("publisher") or source.publisher),
                    source_type=str(
                        item.get("source_type") or source.source_type
                    ),
                    used_for=self._coerce_string_list(item.get("used_for")),
                )
            )
        if not references:
            used_ids = {
                *resolved_entity.source_ids,
                *[
                    source_id
                    for section in sections.values()
                    for fact in section
                    for source_id in (fact.get("source_ids") or [])
                ],
                *[
                    source_id
                    for gap in gaps
                    for source_id in gap.source_ids
                ],
            }
            references = [
                EvidenceReference(
                    evidence_id=source.evidence_id,
                    title=source.title,
                    publisher=source.publisher,
                    source_type=source.source_type,
                    used_for=["company_intelligence"],
                )
                for source in evidence
                if source.evidence_id in used_ids
            ]

        return (
            CompanyIntelligence.model_validate(
                {
                    **sections,
                    "executive_summary": executive_summary,
                    "entity": resolved_entity.model_dump(mode="json"),
                    "business_profile": business_profile.model_dump(mode="json"),
                    "manufacturing_footprint": [
                        item.model_dump(mode="json")
                        for item in manufacturing_sites
                    ],
                    "supply_chain_role": supply_chain_role.model_dump(mode="json"),
                    "supply_chain_structure": [
                        item.model_dump(mode="json")
                        for item in self._coerce_supply_chain_structure(
                            payload.get("supply_chain_structure"), allowed
                        )
                    ],
                    "decision_context": decision_context.model_dump(mode="json"),
                    "evidence_references": [
                        item.model_dump(mode="json") for item in references
                    ],
                    "information_gaps": gaps,
                }
            ),
            used_fallback,
        )

    @staticmethod
    def _enrich_entity_from_evidence(
        entity: CompanyEntity,
        evidence: list[RetrievedEvidence],
    ) -> CompanyEntity:
        company_evidence = [
            item for item in evidence if item.evidence_scope == "company"
        ]
        if not company_evidence:
            return entity
        content = "\n".join(item.content for item in company_evidence)

        def capture(pattern: str) -> str:
            match = re.search(pattern, content, flags=re.IGNORECASE)
            return match.group(1).strip() if match else ""

        legal_name = capture(r"Legal entity:\s*([^\n]+)")
        headquarters = capture(r"Headquarters:\s*([^\n]+)")
        founded = capture(r"Founded:\s*([^\n]+)")
        exchange = capture(r"Stock exchange:\s*([^\n]+)")
        ticker = capture(r"Ticker:\s*([^\n]+)")
        aliases = capture(r"Aliases:\s*([^\n]+)")
        alias_values = [
            value.strip()
            for value in aliases.split(",")
            if value.strip()
        ]
        return entity.model_copy(
            update={
                "legal_name": legal_name or entity.legal_name,
                "aliases": list(
                    dict.fromkeys([*entity.aliases, *alias_values])
                ),
                "headquarters": entity.headquarters
                if entity.headquarters not in {"", "CN"}
                else headquarters or entity.headquarters,
                "founded_year": entity.founded_year or founded,
                "listing": entity.listing.model_copy(
                    update={
                        "exchange": entity.listing.exchange or exchange,
                        "ticker": entity.listing.ticker or ticker,
                    }
                ),
                "source_ids": list(
                    dict.fromkeys(
                        [
                            *entity.source_ids,
                            *[
                                item.evidence_id
                                for item in company_evidence
                            ],
                        ]
                    )
                ),
                "data_status": "public_source",
            }
        )

    # The form may send a country as a code, an English name or a local name
    # ("CN", "China", "中国"). Collapsing them onto one key lets a disclosed base
    # join the user's own row instead of showing the same country twice. Only the
    # comparison is normalised; the displayed value stays whatever the user wrote.
    COUNTRY_ALIASES: dict[str, str] = {
        "cn": "CN", "china": "CN", "中国": "CN",
        "kr": "KR", "korea": "KR", "southkorea": "KR", "韩国": "KR", "대한민국": "KR",
        "us": "US", "usa": "US", "unitedstates": "US", "美国": "US",
        "pl": "PL", "poland": "PL", "波兰": "PL",
        "ca": "CA", "canada": "CA", "加拿大": "CA",
        "jp": "JP", "japan": "JP", "日本": "JP",
        "de": "DE", "germany": "DE", "德国": "DE",
        "hu": "HU", "hungary": "HU", "匈牙利": "HU",
    }

    @classmethod
    def _country_key(cls, country: str) -> str:
        compact = re.sub(
            r"[^a-z0-9\uac00-\ud7af\u4e00-\u9fff]",
            "",
            str(country or "").casefold(),
        )
        if not compact:
            return ""
        return cls.COUNTRY_ALIASES.get(compact, compact)

    def _merge_manufacturing_footprint(
        self,
        sites: list[ManufacturingSite],
        company: CompanyInput,
        evidence_by_id: dict[str, RetrievedEvidence],
    ) -> list[ManufacturingSite]:
        """One table: the user's own layout plus the bases the company discloses.

        The user's countries and shares are the baseline. They are never
        overwritten, and the share the user did not state is never distributed to
        the other countries. A facility name, role or capacity is only taken from
        a row that cites company evidence; a country the user never mentioned is
        only kept when the company's own material names it as a production base,
        and it never receives a percentage.
        """
        merged: dict[str, ManufacturingSite] = {}
        order: list[str] = []
        for location in company.production_locations:
            key = self._country_key(location.country)
            if not key or key in merged:
                continue
            merged[key] = ManufacturingSite(
                country=location.country,
                production_share=location.production_share,
                source_type="user_input",
                status="reported",
            )
            order.append(key)
        for site in sites:
            key = self._country_key(site.country)
            if not key:
                continue
            cited = [
                source_id
                for source_id in site.source_ids
                if source_id in evidence_by_id
            ]
            existing = merged.get(key)
            if existing is None:
                if not cited:
                    # An unsourced country would be an inference, not a disclosure.
                    continue
                merged[key] = site.model_copy(update={"production_share": None})
                order.append(key)
                continue
            if not cited:
                continue
            merged[key] = existing.model_copy(
                update={
                    "facility": site.facility or existing.facility,
                    "role": site.role or existing.role,
                    "capacity": (
                        site.capacity
                        if site.capacity and site.capacity != "unknown"
                        else existing.capacity
                    ),
                    "source_type": (
                        site.source_type
                        if site.source_type != "user_input"
                        else "company_filing"
                    ),
                    "source_ids": cited,
                    "status": site.status or existing.status,
                }
            )
        return [merged[key] for key in order]

    def _fact_source_supports(
        self,
        fact: str,
        source_ids: list[str],
        evidence_by_id: dict[str, RetrievedEvidence],
    ) -> bool:
        """Does the cited material actually state this fact?

        Company disclosures are usually English or Korean while the fact is
        written in the user's language, so a word-by-word comparison only decides
        anything when both sides share a writing system. Across languages the
        check falls back to the anchors that survive translation — figures and
        Latin names — and to whether the cited material is the company's own
        disclosure at all. A translated restatement of a disclosed fact is still
        a disclosed fact; only a claim the cited material cannot carry is
        downgraded.
        """
        if not source_ids:
            return False
        items = [
            evidence_by_id[source_id]
            for source_id in source_ids
            if source_id in evidence_by_id
        ]
        if not items:
            return False
        source_text = " ".join(item.content for item in items)
        if len(source_text.strip()) < 80:
            return False
        fact_terms = self._terms(fact)
        if not fact_terms:
            return False
        source_terms = self._terms(source_text)
        overlap = fact_terms & source_terms
        if self._script_of(fact) != self._script_of(source_text):
            # "국내 공장 및 해외 생산법인에서 제품을 생산" and "通过国内工厂及海外
            # 生产法人生产" are the same sentence in two scripts; only the figures
            # and Latin names can be compared, and a fact that carries none of
            # them rests on the company's own disclosure being the cited source.
            anchors = {term for term in fact_terms if term.isascii()}
            if anchors:
                return bool(anchors & source_terms)
            return all(
                item.evidence_scope == "company" and item.source_tier <= 2
                for item in items
            )
        numeric_terms = {
            term for term in fact_terms if any(char.isdigit() for char in term)
        }
        return len(overlap) >= 2 and (
            not numeric_terms or numeric_terms.issubset(source_terms)
        )

    @staticmethod
    def _script_of(value: str) -> str:
        """Dominant writing system, used to decide if terms are comparable."""
        text = str(value or "")
        counts = {
            "han": len(re.findall(r"[\u4e00-\u9fff]", text)),
            "hangul": len(re.findall(r"[\uac00-\ud7af]", text)),
            "latin": len(re.findall(r"[A-Za-z]", text)),
        }
        script, count = max(counts.items(), key=lambda item: item[1])
        return script if count else "unknown"

    def _coerce_fact_list(
        self,
        value: Any,
        prefix: str,
        allowed: set[str],
        evidence_by_id: dict[str, RetrievedEvidence],
        language: str,
    ) -> list[FactItem]:
        facts: list[FactItem] = []
        for item in self._unwrap_list(value, language):
            if not isinstance(item, dict):
                continue
            nested = item.get("fact")
            if isinstance(nested, dict):
                item = {**item, **nested}
            text = self._text_of(item.get("fact"))
            if not text:
                continue
            ids = [
                source_id
                for source_id in (item.get("source_ids") or [])
                if source_id in allowed
            ]
            status = str(item.get("data_status") or "").strip()
            if status not in {
                "user_input",
                "public_source",
                "inferred",
                "to_be_confirmed",
            }:
                status = "public_source" if ids else "to_be_confirmed"
            if status == "public_source" and not self._fact_source_supports(
                text, ids, evidence_by_id
            ):
                status = "inferred" if ids else "to_be_confirmed"
            facts.append(
                FactItem(
                    fact=text,
                    fact_id=str(
                        item.get("fact_id")
                        or f"FCT-{prefix}-{len(facts) + 1:03d}"
                    ),
                    source_ids=ids,
                    data_status=status,
                    confidence=str(item.get("confidence") or "low"),
                    as_of=str(item.get("as_of") or ""),
                    derived_from=[
                        str(value)
                        for value in (item.get("derived_from") or [])
                        if str(value).strip()
                    ],
                    conflict=bool(item.get("conflict")),
                )
            )
        return facts

    def _build_profile(
        self, company: CompanyInput, request_id: str, language: str = "en"
    ) -> CompanyProfile:
        footprint = ", ".join(
            f"{item.country} {item.production_share}%"
            for item in company.production_locations
        )
        markets = ", ".join(company.target_markets)
        # The free-text question is optional in the UI, so fall back to a generic
        # description instead of leaving the profile empty.
        question = company.decision_question.strip() or (
            "the current production layout and how to rebalance it"
        )
        footprint_text = footprint or "not specified"
        markets_text = markets or "not specified"
        # An unranked decision is reported with equal weights everywhere, so the
        # prompts and the report do not present a default order as the user's.
        priorities = (
            company.priorities
            if company.priorities_declared
            else [
                {"dimension": dimension, "weight": self.EQUAL_WEIGHT}
                for dimension in self.SCORING_DIMENSIONS
            ]
        )
        if (language or "en").lower() == "zh":
            summary = (
                f"{company.company_name} 当前生产布局为 {footprint_text}，"
                f"主要面向 {markets_text} 市场。核心决策问题是：{question}"
            )
        else:
            summary = (
                f"{company.company_name} currently produces in {footprint_text} "
                f"and serves {markets_text}. The decision under review: {question}."
            )
        return CompanyProfile(
            company_id=f"CMP-{request_id.split('-')[1]}",
            company_name=company.company_name,
            industry=company.industry,
            products=company.products,
            home_country=company.home_country,
            production_footprint=company.production_locations,
            target_markets=company.target_markets,
            decision_question=question,
            time_horizon=company.time_horizon,
            priorities=priorities,
            restrictions=company.restrictions,
            summary=summary,
        )

    def _build_heuristic(
        self, company: CompanyInput, evidence: list[Any]
    ) -> dict[str, Any]:
        has_mock_evidence = any(item.is_mock for item in evidence)
        all_mock_evidence = bool(evidence) and all(item.is_mock for item in evidence)
        evidence_uncertainty = (
            "当前检索结果包含 Mock 测试证据，需要真实政策文件和公司成本数据复核。"
            if has_mock_evidence
            else "当前公开证据不包含公司内部数据，关键判断仍需人工核验。"
        )
        restrictions = set(company.restrictions)
        production = {
            location.country: location.production_share
            for location in company.production_locations
        }

        risk_templates: list[tuple[str, str, int, str]] = []
        if "tariff_pressure" in restrictions or "US" in company.target_markets:
            risk_templates.append(
                (
                    "关税与原产地规则变化",
                    "trade_policy",
                    78,
                    "出口市场和原产地认定变化可能推高到岸成本，并改变不同生产基地的相对优势。",
                )
            )
        if "export_controls" in restrictions or company.industry in {
            "semiconductor",
            "optoelectronics",
        }:
            risk_templates.append(
                (
                    "出口管制与客户穿透审查",
                    "export_control",
                    74,
                    "产品、客户及股权关系可能触发许可证、客户筛查或交易限制。",
                )
            )
        if "supplier_dependency" in restrictions or "VN" in production:
            risk_templates.append(
                (
                    "海外供应商生态不足",
                    "supply_chain",
                    66,
                    "关键物料、工程人才或本地配套不足可能降低产能爬坡速度和交付稳定性。",
                )
            )
        minimum_risks = [
            (
                "目标市场准入与本地化要求",
                "market_access",
                62,
                "区域本地化、客户原产地要求和认证门槛可能限制现有供应安排。",
            ),
            (
                "多基地运营与实施复杂度",
                "operational",
                58,
                "多地区布局可能提高资本开支、认证、产能爬坡和组织协调难度。",
            ),
            (
                "供应链集中与替代能力",
                "supply_chain",
                61,
                "关键材料或供应商集中可能影响交付韧性和替代能力。",
            ),
            (
                "出口管制与合规要求",
                "regulatory",
                57,
                "出口、客户筛查或本地合规要求可能增加实施负担。",
            ),
        ]
        existing_categories = {item[1] for item in risk_templates}
        for candidate in minimum_risks:
            if len(risk_templates) >= 4:
                break
            if candidate[1] not in existing_categories:
                risk_templates.append(candidate)
                existing_categories.add(candidate[1])

        risks = []
        for name, category, probability, impact in risk_templates:
            severity = (
                "critical"
                if probability >= 80
                else "high"
                if probability >= 70
                else "medium"
                if probability >= 55
                else "low"
            )
            risks.append(
                {
                    "risk_id": "RSK-000",
                    "name": name,
                    "category": category,
                    "severity": severity,
                    "probability": probability,
                    "business_impact": impact,
                    "uncertainty": evidence_uncertainty,
                    "evidence_ids": [],
                    "basis": "inference",
                    "insufficient_evidence": True,
                }
            )

        # Unranked decisions fall back to equal weights, not a default order.
        normalized_weights = self._effective_weights(company)

        scenario_defs = [
            {
                "name": "维持现有海外布局",
                "description": "维持当前生产分布，通过供应商和库存管理降低短期扰动。",
                "cost_score": 76,
                "resilience_score": 52,
                "geopolitical_risk_score": 61,
                "market_access_score": 68,
                "implementation_score": 88,
                "benefits": ["迁移成本最低", "现有客户认证和产能爬坡不中断"],
                "risks": ["对单一海外节点和外部政策依赖仍然较高"],
                "applicable_conditions": ["政策和成本变动仍在企业可承受范围内"],
            },
            {
                "name": "提高中国生产比例",
                "description": "将部分高复杂度或高依赖环节回迁中国，利用成熟供应商生态。",
                "cost_score": 63,
                "resilience_score": 81,
                "geopolitical_risk_score": 55,
                "market_access_score": 49,
                "implementation_score": 58,
                "benefits": ["供应链完整度较高", "工程协同和交付稳定性更好"],
                "risks": ["面向美国等市场时可能承担更高关税与合规成本"],
                "applicable_conditions": ["产品对中国供应链依赖强且出口政策风险可控"],
            },
            {
                "name": "多地区混合布局",
                "description": "按产品和市场拆分生产，以冗余节点换取韧性和市场准入。",
                "cost_score": 48,
                "resilience_score": 86,
                "geopolitical_risk_score": 78,
                "market_access_score": 82,
                "implementation_score": 42,
                "benefits": ["降低单点风险", "可按市场分别优化原产地和合规路径"],
                "risks": ["资本开支和管理复杂度最高", "短期产能爬坡压力较大"],
                "applicable_conditions": ["企业具备中长期投资能力且市场足够分散"],
            },
        ]

        scenarios = []
        metric_weights = {
            "cost_score": ("cost_reduction", 1),
            "resilience_score": ("supply_chain_resilience", 1),
            "geopolitical_risk_score": ("political_stability", 1),
            "market_access_score": ("market_access", 1),
            "implementation_score": ("compliance", 0.5),
        }
        for index, item in enumerate(scenario_defs, start=1):
            total_weight = sum(
                normalized_weights[dimension] * factor
                for dimension, factor in metric_weights.values()
            )
            weighted_score = sum(
                item[metric]
                * normalized_weights[dimension]
                * factor
                / total_weight
                for metric, (dimension, factor) in metric_weights.items()
            )
            scenarios.append(
                {
                    "scenario_id": f"SCN-{index:03d}",
                    "name": item["name"],
                    "description": item["description"],
                    "cost_score": item["cost_score"],
                    "resilience_score": item["resilience_score"],
                    "geopolitical_risk_score": item["geopolitical_risk_score"],
                    "market_access_score": item["market_access_score"],
                    "implementation_score": item["implementation_score"],
                    "weighted_score": round(weighted_score, 1),
                    "benefits": item["benefits"],
                    "risks": item["risks"],
                    "applicable_conditions": item["applicable_conditions"],
                    "evidence_ids": [],
                    "insufficient_evidence": True,
                }
            )

        recommended = max(scenarios, key=lambda item: item["weighted_score"])
        return {
            "risks": risks,
            "scenarios": scenarios,
            "recommendation": {
                "recommended_scenario_id": recommended["scenario_id"],
                "headline": f"当前权重下优先评估：{recommended['name']}",
                "rationale": (
                    f"该方案的综合加权分为 {recommended['weighted_score']}，"
                    "在成本、韧性、市场准入和实施难度之间相对平衡。"
                ),
                "next_actions": [
                    "补充产品 HS/ECCN 编码、客户结构和关键供应商依赖。",
                    (
                        "用真实政策文件替换当前 Mock 证据并重新运行评估。"
                        if all_mock_evidence
                        else "核对引用来源的现行版本，并在法规更新后重新运行评估。"
                    ),
                    "补充投资预算、产能爬坡周期和固定资产沉没成本。",
                ],
                "confidence": "low",
                "uncertainty": [
                    (
                        "当前数据源为测试数据，不能作为正式决策依据。"
                        if has_mock_evidence
                        else "公开资料缺少公司级成本、产能、BOM 和客户筛查数据。"
                    ),
                    "没有公司的单位成本、产能和真实 BOM 数据。",
                    "政策变化速度和执行力度无法仅由当前信息判断。",
                ],
            },
            "limitations": [
                (
                    "当前分析包含 Mock 证据，仅用于验证产品和 Agent 工作流。"
                    if has_mock_evidence
                    else "本分析基于公开资料和适用性有限的通用证据，不能替代公司级尽调。"
                ),
                "评分是决策辅助，不构成法律、投资或合规意见。",
                "结论必须经过人工复核，高风险事项应由专业顾问确认。",
            ],
        }

    @staticmethod
    def _terms(value: str) -> set[str]:
        normalized = value.lower()
        words = set(re.findall(r"[a-z0-9]+", normalized))
        chinese = set(re.findall(r"[\u4e00-\u9fff]{2,}", normalized))
        return words.union(chinese)


def summarize_evidence_topics(assessment: Assessment) -> list[tuple[str, int]]:
    return Counter(item.topic for item in assessment.evidence).most_common()
