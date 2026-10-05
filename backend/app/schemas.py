from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CountryCode = Literal["CN", "VN", "ID", "IN", "TH", "MY", "MX", "US", "EU", "ASEAN"]
Language = Literal["en", "zh"]
RiskCategoryKey = Literal[
    "trade",
    "political",
    "supply_chain",
    "regulatory",
    "market_access",
    "operational",
]
RiskLevel = Literal["low", "medium", "high", "critical"]
ConfidenceLevel = Literal["low", "medium", "high"]
Likelihood = Literal["very_low", "low", "medium", "high", "very_high"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductionLocation(StrictModel):
    # A location may be a code the API knows or the readable country the user
    # typed under "Other". Those entries used to be dropped from the structured
    # payload and only survived as free text in `notes`, so the profile, the
    # summary and the scenarios never saw the real country.
    country: str = Field(min_length=1, max_length=100)
    production_share: int = Field(ge=0, le=100)
    capacity_note: str | None = None


class PriorityWeight(StrictModel):
    dimension: Literal[
        "cost_reduction",
        "supply_chain_resilience",
        "market_access",
        "political_stability",
        "compliance",
    ]
    weight: int = Field(ge=0, le=5)


class CompanyInput(StrictModel):
    company_name: str = Field(min_length=1, max_length=200)
    industry: Literal[
        "battery_ev",
        "semiconductor",
        "electronics",
        "optoelectronics",
        "industrial_equipment",
        "other",
    ]
    products: list[str] = Field(min_length=1)
    # Free text rather than a fixed enum: the form offers a list of common
    # countries plus an "Other" entry, and a home base such as "Brazil" must not
    # be rejected. Known country codes still pass through unchanged.
    home_country: str = Field(default="CN", min_length=1, max_length=100)
    production_locations: list[ProductionLocation] = Field(default_factory=list)
    # Same rule as production locations: a market entered under "Other" is kept
    # as the country the user typed instead of being discarded.
    target_markets: list[str] = Field(default_factory=list)
    # The free-text question is optional in the UI (profile list.md); the selected
    # preset is enough when the user does not add their own wording.
    decision_question: str = Field(default="", max_length=1000)
    time_horizon: Literal["within_6_months", "6_18_months", "2_5_years"]
    priorities: list[PriorityWeight] = Field(min_length=1)
    # False when the user never ranked the decision priorities (the ranking lives
    # in the optional Advanced assessment). Scenario scoring then weights every
    # dimension equally instead of falling back to an arbitrary default order.
    priorities_declared: bool = False
    restrictions: list[
        Literal[
            "tariff_pressure",
            "export_controls",
            "sanctions_concerns",
            "local_regulation",
            "supplier_dependency",
            "labor_cost_increase",
            "logistics_problems",
            "geopolitical_uncertainty",
            "market_access",
            "capacity_expansion",
            "other",
            "none",
        ]
    ] = Field(default_factory=list)
    hs_codes: list[str] = Field(default_factory=list)
    investment_budget_usd: int | None = Field(default=None, ge=0)
    key_supplier_count: int | None = Field(default=None, ge=0, le=100000)
    largest_supplier_share: int | None = Field(default=None, ge=0, le=100)
    has_verified_bom: bool = False
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("production_locations")
    @classmethod
    def validate_production_share(
        cls, locations: list[ProductionLocation]
    ) -> list[ProductionLocation]:
        total = sum(location.production_share for location in locations)
        # profile list.md: shares are recommended but not mandatory, so a partial
        # or empty footprint is accepted; only an impossible total is rejected.
        # The form leaves the share blank by default, so requiring exactly 100
        # rejected every submission that did not fill it in.
        if total > 100:
            raise ValueError("production shares cannot exceed 100")
        return locations

    @model_validator(mode="after")
    def validate_priorities(self) -> "CompanyInput":
        dimensions = [priority.dimension for priority in self.priorities]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("priority dimensions must be unique")
        return self


class RetrievalQuery(StrictModel):
    industry: str
    products: list[str]
    company_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    evidence_scope: Literal["all", "company", "policy"] = "all"
    home_country: str
    production_countries: list[str]
    target_markets: list[str]
    decision_question: str
    restrictions: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


class RetrievedEvidence(StrictModel):
    evidence_id: str
    title: str
    source_type: str
    publisher: str
    country_region: str
    publication_date: str
    url: str | None = None
    authority_level: Literal["S", "A+", "A", "B+", "B", "C", "D"]
    topic: str
    document_path: str | None = None
    # Same-origin API path that streams the original document, when one is held
    # locally (data branch) or reachable on the web.
    document_url: str | None = None
    content: str
    relevance_score: int = Field(ge=0, le=100)
    is_mock: bool
    evidence_scope: Literal["company", "policy", "market", "unknown"] = "unknown"
    is_self_reported: bool = False
    # Evidence priority for the profile stage (Company Intelligence revision):
    # 1 = the company's own disclosure, 2 = company-specific reliable reporting,
    # 3 = industry context, 4 = policy/regulatory material.
    source_tier: int = Field(default=4, ge=1, le=4)
    source_tier_reason: str = ""
    # Document provenance for company sources (Company Research P0). Additive
    # with defaults so existing stored assessments keep validating.
    document_format: Literal["html", "pdf", "unknown"] = "unknown"
    document_kind: Literal[
        "annual_report",
        "business_report",
        "esg_report",
        "financial_statement",
        "earnings_release",
        "investor_material",
        "filing",
        "web_page",
        "unknown",
    ] = "unknown"
    # Which part of a long document this evidence came from (P0.5): one PDF is
    # represented by several section snippets, each with its page range.
    section: str = ""
    page_start: int = Field(default=0, ge=0)
    page_end: int = Field(default=0, ge=0)
    language: Literal["ko", "zh", "en", "unknown"] = "unknown"
    fiscal_year: str = ""
    byte_size: int = Field(default=0, ge=0)
    page_count: int = Field(default=0, ge=0)
    retrieved_at: str = ""
    freshness: Literal["current", "aging", "stale", "unknown"] = "unknown"
    verification_status: Literal[
        "verified", "partial", "unverified", "contested", "outdated"
    ] = "unverified"


class CompanyProfile(StrictModel):
    company_id: str
    company_name: str
    industry: str
    products: list[str]
    home_country: str
    production_footprint: list[ProductionLocation]
    target_markets: list[str]
    decision_question: str
    time_horizon: str
    priorities: list[PriorityWeight]
    restrictions: list[str]
    summary: str


class RiskItem(StrictModel):
    risk_id: str
    name: str
    title: str = ""
    category: str
    category_key: RiskCategoryKey | None = None
    severity: RiskLevel
    probability: int = Field(ge=0, le=100)
    business_impact: str
    company_specific_trigger: str = ""
    external_mechanism: str = ""
    impact_channels: list[str] = Field(default_factory=list)
    impact_description: str = ""
    uncertainty: str
    uncertainty_reasons: list[str] = Field(default_factory=list)
    what_would_change_assessment: list[str] = Field(default_factory=list)
    evidence_ids: list[str]
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    evidence_links: list["EvidenceLink"] = Field(default_factory=list)
    verification_status: Literal[
        "verified", "partial", "unverified", "contested", "outdated"
    ] = "unverified"
    likelihood: Likelihood = "medium"
    likelihood_score: int = Field(default=3, ge=1, le=5)
    impact_score: int = Field(default=3, ge=1, le=5)
    company_exposure_score: int = Field(default=3, ge=1, le=5)
    risk_score: int = Field(default=27, ge=1, le=125)
    risk_level: Literal["low", "medium", "high"] = "medium"
    decision_relevance: Literal["low", "medium", "high"] = "medium"
    confidence: ConfidenceLevel = "low"
    likelihood_basis: str = ""
    basis: Literal["evidence", "user_input", "inference"] = "inference"
    insufficient_evidence: bool = False


class EvidenceLink(StrictModel):
    evidence_id: str
    relation: Literal["supports", "context", "contradicts"]
    reason: str = ""


class ScenarioScoreBreakdown(StrictModel):
    dimension: str
    score: float
    weight: float
    contribution: float
    basis: Literal["evidence", "inference"] = "inference"
    evidence_ids: list[str] = Field(default_factory=list)


class ScenarioResult(StrictModel):
    scenario_id: str
    name: str
    description: str
    cost_score: int = Field(ge=0, le=100)
    resilience_score: int = Field(ge=0, le=100)
    geopolitical_risk_score: int = Field(ge=0, le=100)
    market_access_score: int = Field(ge=0, le=100)
    implementation_score: int = Field(ge=0, le=100)
    weighted_score: float = Field(ge=0, le=100)
    confidence: ConfidenceLevel | None = None
    confidence_reasons: list[str] = Field(default_factory=list)
    benefits: list[str]
    risks: list[str]
    applicable_conditions: list[str]
    evidence_ids: list[str]
    dimension_bands: dict[str, str] = Field(default_factory=dict)
    score_breakdown: list[ScenarioScoreBreakdown] = Field(default_factory=list)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    insufficient_evidence: bool = False


class Recommendation(StrictModel):
    recommended_scenario_id: str
    headline: str
    rationale: str
    next_actions: list[str]
    confidence: ConfidenceLevel
    confidence_score: int = Field(default=0, ge=0, le=100)
    confidence_reasons: list[str] = Field(default_factory=list)
    uncertainty: list[str]
    requires_human_review: bool = True
    evidence_ids: list[str] = Field(default_factory=list)


class TraceStep(StrictModel):
    step_id: str
    agent: str
    action: str
    status: Literal["completed", "fallback", "failed"]
    detail: str
    started_at: str
    duration_ms: int = Field(ge=0)


class ChatTurn(StrictModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ChatRequest(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    api_key: str | None = Field(default=None, min_length=10)
    language: Language = "en"


class AssessmentRequest(StrictModel):
    company: CompanyInput
    # Only required when the backend runs in deepseek mode.
    api_key: str | None = Field(default=None, min_length=10)
    llm_model: Literal["deepseek-flash", "deepseek-v4-pro"] = "deepseek-flash"
    language: Language = "en"


class ChatAnalysis(StrictModel):
    """Structured outcome of one consultation turn (UI.md chat page §19)."""

    new_constraints: list[str] = Field(default_factory=list)
    new_preferences: list[str] = Field(default_factory=list)
    scenario_update_required: bool = False
    summary: str = ""


class ScenarioUpdateRequest(StrictModel):
    additional_constraints: list[str] = Field(default_factory=list)
    api_key: str | None = Field(default=None, min_length=10)
    llm_model: Literal["deepseek-flash", "deepseek-v4-pro"] = "deepseek-flash"
    language: Language = "en"


class FactItem(StrictModel):
    """One fact in the company profile, with its own provenance (workflow.md)."""

    fact: str
    fact_id: str = ""
    source_ids: list[str] = Field(default_factory=list)
    data_status: Literal[
        "user_input", "public_source", "inferred", "to_be_confirmed"
    ] = "to_be_confirmed"
    confidence: ConfidenceLevel = "low"
    as_of: str = ""
    derived_from: list[str] = Field(default_factory=list)
    conflict: bool = False


class CompanyListing(StrictModel):
    exchange: str = ""
    ticker: str = ""


class CompanySize(StrictModel):
    revenue_range: str = ""
    employees_range: str = ""
    factories_count: int | None = None


class CompanyEntity(StrictModel):
    legal_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    headquarters: str = ""
    listing: CompanyListing = Field(default_factory=CompanyListing)
    founded_year: str = ""
    size: CompanySize = Field(default_factory=CompanySize)
    source_ids: list[str] = Field(default_factory=list)
    data_status: Literal[
        "user_input", "public_source", "inferred", "to_be_confirmed"
    ] = "to_be_confirmed"


class InformationGap(StrictModel):
    item: str
    priority: Literal["critical", "important", "optional"] = "important"
    why_it_matters: str = ""
    recommended_action: str = ""
    source_ids: list[str] = Field(default_factory=list)


class ManufacturingSite(StrictModel):
    country: str
    facility: str = ""
    role: str = ""
    production_share: int | None = Field(default=None, ge=0, le=100)
    capacity: str = "unknown"
    source_type: Literal[
        "user_input",
        "company_filing",
        "official_website",
        "industry_report",
        "news",
    ] = "user_input"
    status: Literal[
        "verified", "reported", "estimated", "inferred", "unknown"
    ] = "unknown"
    source_ids: list[str] = Field(default_factory=list)


# Controlled vocabulary agreed with the product owner: the role labels must be
# stable for the Risk and Scenario stages, so they are a small fixed set rather
# than a free-text industry classification.
SUPPLY_CHAIN_ROLE_VALUES = (
    "UPSTREAM_RAW_MATERIAL",
    "UPSTREAM_COMPONENT",
    "BATTERY_MANUFACTURING",
    "DOWNSTREAM_APPLICATION",
    "INTEGRATED_BATTERY_COMPANY",
    "OTHER",
)
SUPPLY_CHAIN_ROLE_FALLBACK = "OTHER"


class SupplyChainRole(StrictModel):
    primary: str = SUPPLY_CHAIN_ROLE_FALLBACK
    secondary: list[str] = Field(default_factory=list)
    upstream: list[FactItem] = Field(default_factory=list)
    manufacturing: list[FactItem] = Field(default_factory=list)
    downstream: list[FactItem] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


class SupplyChainStage(StrictModel):
    """One link of the reconstructed supply chain (doc: Supply Chain Structure).

    `share` may only carry a number when `share_basis` shows where it came from;
    an unsourced percentage is replaced with "unknown" during coercion.
    """

    stage: Literal[
        "raw_material", "component", "manufacturing", "downstream"
    ]
    description: str = ""
    region: str = "unknown"
    company_role: str = ""
    share: str = "unknown"
    share_basis: Literal[
        "user_input", "disclosed", "sourced_estimate", "unknown"
    ] = "unknown"
    source_ids: list[str] = Field(default_factory=list)


class EvidenceReference(StrictModel):
    evidence_id: str
    title: str = ""
    publisher: str = ""
    source_type: str = ""
    used_for: list[str] = Field(default_factory=list)


class BusinessProfile(StrictModel):
    model: str = ""
    value_chain_role: str = ""
    products: list[str] = Field(default_factory=list)
    customers: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class DecisionContext(StrictModel):
    objective: str = ""
    drivers: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class CompanyIntelligence(StrictModel):
    executive_summary: str = ""
    entity: CompanyEntity = Field(default_factory=CompanyEntity)
    overview: list[FactItem] = Field(default_factory=list)
    production_footprint: list[FactItem] = Field(default_factory=list)
    supply_chain: list[FactItem] = Field(default_factory=list)
    strategic_context: list[FactItem] = Field(default_factory=list)
    market_position: list[FactItem] = Field(default_factory=list)
    business_profile: BusinessProfile = Field(default_factory=BusinessProfile)
    manufacturing_footprint: list[ManufacturingSite] = Field(default_factory=list)
    supply_chain_role: SupplyChainRole = Field(default_factory=SupplyChainRole)
    supply_chain_structure: list[SupplyChainStage] = Field(default_factory=list)
    decision_context: DecisionContext = Field(default_factory=DecisionContext)
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    information_gaps: list[str | InformationGap] = Field(default_factory=list)


class LLMCallRecord(StrictModel):
    stage: str
    provider: str
    model: str
    latency_ms: int = Field(ge=0)
    attempts: int = Field(ge=0)
    ok: bool
    error: str = ""


class Assessment(StrictModel):
    assessment_id: str
    request_id: str
    created_at: str
    updated_at: str
    contract_version: str = "1.1"
    language: Language = "en"
    company_input: CompanyInput | None = None
    company_profile: CompanyProfile
    company_intelligence: CompanyIntelligence | None = None
    evidence: list[RetrievedEvidence]
    risks: list[RiskItem]
    scenarios: list[ScenarioResult]
    recommendation: Recommendation
    scoring: dict[str, int] = Field(default_factory=dict)
    weighting_mode: Literal["user", "equal"] = "equal"
    chat_analysis: ChatAnalysis | None = None
    chat_history: list[ChatTurn] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    limitations: list[str]
    model_mode: Literal["mock", "deepseek"]
    model_name: str = "mock"
    data_mode: Literal["mock", "live", "hybrid", "rag_only", "unavailable"]
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    degraded: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
