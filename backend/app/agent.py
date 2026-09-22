from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from typing import Any

from pydantic import ValidationError

from .llm import EventCallback, LLMProvider
from .retrieval import RetrievalProvider
from .schemas import (
    Assessment,
    ChatRequest,
    ChatTurn,
    CompanyInput,
    CompanyProfile,
    Recommendation,
    RetrievalQuery,
    RetrievedEvidence,
    RiskItem,
    ScenarioResult,
    TraceStep,
    utc_now,
)


class AgentService:
    def __init__(self, retrieval: RetrievalProvider, llm: LLMProvider):
        self.retrieval = retrieval
        self.llm = llm

    def run(
        self,
        company: CompanyInput,
        api_key: str | None = None,
        model_name: str | None = None,
        event_callback: EventCallback | None = None,
    ) -> Assessment:
        run_id = uuid.uuid4().hex[:10].upper()
        request_id = f"REQ-{run_id}"
        assessment_id = f"ASM-{run_id}"
        trace: list[TraceStep] = []
        selected_model = model_name or getattr(self.llm, "model", "mock")
        active_llm = self.llm.with_runtime(
            selected_model,
            api_key,
            event_callback,
        )
        if self.llm.mode == "deepseek":
            if not api_key:
                raise ValueError("必须填写自己的 DeepSeek API Key")
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
        profile = self._build_profile(company, request_id)
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
            {"type": "stage", "agent": "ResearchAgent", "status": "started"},
        )
        evidence = self._retrieve(company)
        data_mode = "mock" if all(item.is_mock for item in evidence) else "hybrid"
        trace.append(
            self._trace(
                agent="ResearchAgent",
                action="调用混合检索工具",
                status="completed",
                detail=f"返回 {len(evidence)} 条证据，数据模式为 {data_mode}。",
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

        heuristic = self._build_heuristic(company, evidence)

        step_started = time.perf_counter()
        self._emit_event(
            event_callback,
            {"type": "stage", "agent": "RiskAgent", "status": "started"},
        )
        risk_payload = active_llm.analyze_risks(
            company, evidence, heuristic["risks"]
        )
        risks, risk_fallback = self._coerce_risks(
            risk_payload.get("risks"), heuristic["risks"], evidence
        )
        trace.append(
            self._trace(
                agent="RiskAgent",
                action="识别与验证地缘政治风险",
                status="fallback" if risk_fallback else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if risk_fallback
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
        )
        scenarios, scenario_fallback = self._coerce_scenarios(
            scenario_payload.get("scenarios"),
            heuristic["scenarios"],
            evidence,
            company,
        )
        scenarios = self._rank_scenarios(scenarios)
        trace.append(
            self._trace(
                agent="ScenarioAgent",
                action="模拟迁移方案并重算权重",
                status="fallback" if scenario_fallback else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if scenario_fallback
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
        )
        recommendation, limitations, advisor_fallback = self._coerce_recommendation(
            recommendation_payload,
            heuristic,
            company,
            evidence,
            risks,
            scenarios,
        )
        trace.append(
            self._trace(
                agent="AdvisorAgent",
                action="生成建议与人工复核标记",
                status="fallback" if advisor_fallback else "completed",
                detail=(
                    "模型输出未通过校验，已使用规则基线。"
                    if advisor_fallback
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
        citations_valid = self._validate_citations(risks, scenarios, evidence)
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

        now = utc_now()
        return Assessment(
            assessment_id=assessment_id,
            request_id=request_id,
            created_at=now,
            updated_at=now,
            company_profile=profile,
            evidence=evidence,
            risks=risks,
            scenarios=scenarios,
            recommendation=recommendation,
            trace=trace,
            limitations=limitations,
            model_mode=active_llm.mode,
            model_name=selected_model,
            data_mode=data_mode,
        )

    def chat(self, assessment: Assessment, request: ChatRequest) -> Assessment:
        if self.llm.mode == "deepseek" and not request.api_key:
            raise ValueError("DeepSeek API Key is required for chat")
        user_turn = ChatTurn(role="user", content=request.message, created_at=utc_now())
        step_started = time.perf_counter()
        active_llm = self.llm.with_runtime(
            assessment.model_name,
            request.api_key,
            None,
        )
        action = active_llm.choose_chat_action(assessment, request.message)
        supplemental_evidence: list[RetrievedEvidence] = []
        trace_status = "completed"

        if action.get("action") == "search_evidence":
            query = str(action.get("query") or request.message)[:500]
            supplemental_evidence = self._search_text(query)
            detail = f"ChatAgent 自主调用检索工具，补充 {len(supplemental_evidence)} 条证据。"
            if not supplemental_evidence:
                trace_status = "fallback"
                detail = "ChatAgent 请求检索，但没有获得补充证据。"
        else:
            detail = "ChatAgent 判断现有上下文足够，直接调用模型回答。"

        reply = active_llm.answer_chat(
            assessment,
            request.message,
            supplemental_evidence,
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
                "trace": [*assessment.trace, chat_trace],
                "updated_at": utc_now(),
            }
        )
        return updated

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

    def _retrieve(self, company: CompanyInput):
        query = RetrievalQuery(
            industry=company.industry,
            products=company.products,
            home_country=company.home_country,
            production_countries=[
                location.country for location in company.production_locations
            ],
            target_markets=company.target_markets,
            decision_question=company.decision_question,
            restrictions=company.restrictions,
            limit=10,
        )
        return self.retrieval.search(query)

    def _coerce_risks(
        self,
        payload: Any,
        fallback: list[dict[str, Any]],
        evidence: list[RetrievedEvidence],
    ) -> tuple[list[RiskItem], bool]:
        candidates = payload if isinstance(payload, list) else fallback
        allowed_ids = {item.evidence_id for item in evidence}
        mock_ids = {item.evidence_id for item in evidence if item.is_mock}
        risks: list[RiskItem] = []
        used_fallback = not isinstance(payload, list)

        try:
            for index, item in enumerate(candidates[:8], start=1):
                filtered = self._filter_fields(item, RiskItem)
                filtered["risk_id"] = f"RSK-{index:03d}"
                evidence_ids = [
                    evidence_id
                    for evidence_id in filtered.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                if not evidence_ids:
                    evidence_ids = [item.evidence_id for item in evidence[:2]]
                filtered["evidence_ids"] = evidence_ids
                verification_status = (
                    "unverified"
                    if not evidence_ids
                    else "partial"
                    if set(evidence_ids).issubset(mock_ids)
                    else "verified"
                )
                filtered["verification_status"] = verification_status
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
                evidence_ids = [
                    evidence_id
                    for evidence_id in item.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                risks.append(
                    RiskItem.model_validate(item).model_copy(
                        update={
                            "risk_id": f"RSK-{index:03d}",
                            "evidence_ids": evidence_ids
                            or [evidence_item.evidence_id for evidence_item in evidence[:2]],
                            "verification_status": "partial"
                            if evidence_ids
                            and set(evidence_ids).issubset(mock_ids)
                            else "verified",
                        }
                    )
                )
        return risks, used_fallback

    def _coerce_scenarios(
        self,
        payload: Any,
        fallback: list[dict[str, Any]],
        evidence: list[RetrievedEvidence],
        company: CompanyInput,
    ) -> tuple[list[ScenarioResult], bool]:
        candidates = payload if isinstance(payload, list) else fallback
        allowed_ids = {item.evidence_id for item in evidence}
        scenarios: list[ScenarioResult] = []
        used_fallback = not isinstance(payload, list)

        try:
            for index, item in enumerate(candidates[:5], start=1):
                filtered = self._filter_fields(item, ScenarioResult)
                filtered["scenario_id"] = f"SCN-{index:03d}"
                evidence_ids = [
                    evidence_id
                    for evidence_id in filtered.get("evidence_ids", [])
                    if evidence_id in allowed_ids
                ]
                filtered["evidence_ids"] = evidence_ids or [
                    item.evidence_id for item in evidence[:2]
                ]
                filtered["weighted_score"] = 0
                scenario = ScenarioResult.model_validate(filtered).model_copy(
                    update={"scenario_id": f"SCN-{index:03d}"}
                )
                scenarios.append(
                    scenario.model_copy(
                        update={
                            "weighted_score": self._weighted_scenario_score(
                                scenario, company
                            )
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
                scenario = ScenarioResult.model_validate(item).model_copy(
                    update={
                        "scenario_id": f"SCN-{index:03d}",
                        "evidence_ids": evidence_ids
                        or [evidence_item.evidence_id for evidence_item in evidence[:2]],
                    }
                )
                scenarios.append(
                    scenario.model_copy(
                        update={
                            "weighted_score": self._weighted_scenario_score(
                                scenario, company
                            )
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

        requires_review = (
            any(item.severity in {"high", "critical"} for item in risks)
            or any(item.verification_status == "unverified" for item in risks)
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

    @staticmethod
    def _weighted_scenario_score(
        scenario: ScenarioResult,
        company: CompanyInput,
    ) -> float:
        weights = {item.dimension: item.weight for item in company.priorities}
        metric_weights = {
            "cost_score": ("cost_reduction", 1.0),
            "resilience_score": ("supply_chain_resilience", 1.0),
            "geopolitical_risk_score": ("political_stability", 1.0),
            "market_access_score": ("market_access", 1.0),
            "implementation_score": ("compliance", 0.5),
        }
        total_weight = sum(
            weights.get(dimension, 3) * factor
            for dimension, factor in metric_weights.values()
        )
        score = sum(
            getattr(scenario, metric)
            * weights.get(dimension, 3)
            * factor
            / total_weight
            for metric, (dimension, factor) in metric_weights.items()
        )
        return round(score, 1)

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
    ) -> bool:
        allowed_ids = {item.evidence_id for item in evidence}
        return all(
            item.evidence_ids and set(item.evidence_ids).issubset(allowed_ids)
            for item in [*risks, *scenarios]
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

    def _build_profile(self, company: CompanyInput, request_id: str) -> CompanyProfile:
        footprint = ", ".join(
            f"{item.country} {item.production_share}%"
            for item in company.production_locations
        )
        markets = ", ".join(company.target_markets)
        return CompanyProfile(
            company_id=f"CMP-{request_id.split('-')[1]}",
            company_name=company.company_name,
            industry=company.industry,
            products=company.products,
            home_country=company.home_country,
            production_footprint=company.production_locations,
            target_markets=company.target_markets,
            decision_question=company.decision_question,
            time_horizon=company.time_horizon,
            priorities=company.priorities,
            restrictions=company.restrictions,
            summary=(
                f"{company.company_name} 当前生产布局为 {footprint}，"
                f"主要面向 {markets} 市场。核心决策问题是："
                f"{company.decision_question}"
            ),
        )

    def _build_heuristic(
        self, company: CompanyInput, evidence: list[Any]
    ) -> dict[str, Any]:
        evidence_ids = [item.evidence_id for item in evidence]
        top_evidence = evidence_ids[:4]
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
        risk_templates.append(
            (
                "政策与数据时效性风险",
                "information_quality",
                58,
                "公开资料无法替代逐项法规核验，政策变化可能使建议快速过期。",
            )
        )

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
                    "evidence_ids": top_evidence[:2],
                }
            )

        weights = {item.dimension: item.weight for item in company.priorities}
        normalized_weights = {
            "cost_reduction": weights.get("cost_reduction", 3),
            "supply_chain_resilience": weights.get("supply_chain_resilience", 3),
            "market_access": weights.get("market_access", 3),
            "political_stability": weights.get("political_stability", 3),
            "compliance": weights.get("compliance", 3),
        }

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
                    "evidence_ids": top_evidence[:2],
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
