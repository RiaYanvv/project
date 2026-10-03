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


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductionLocation(StrictModel):
    country: CountryCode
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
    home_country: CountryCode = "CN"
    production_locations: list[ProductionLocation] = Field(default_factory=list)
    target_markets: list[CountryCode] = Field(default_factory=list)
    # The free-text question is optional in the UI (profile list.md); the selected
    # preset is enough when the user does not add their own wording.
    decision_question: str = Field(default="", max_length=1000)
    time_horizon: Literal["within_6_months", "6_18_months", "2_5_years"]
    priorities: list[PriorityWeight] = Field(min_length=1)
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
        # profile list.md: shares are requested but not mandatory, so a partial
        # or empty footprint is accepted; only an impossible total is rejected.
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
    category: str
    category_key: RiskCategoryKey | None = None
    severity: RiskLevel
    probability: int = Field(ge=0, le=100)
    business_impact: str
    uncertainty: str
    evidence_ids: list[str]
    verification_status: Literal["verified", "partial", "unverified"] = "unverified"


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


class CompanyIntelligence(StrictModel):
    executive_summary: str = ""
    entity: CompanyEntity = Field(default_factory=CompanyEntity)
    overview: list[FactItem] = Field(default_factory=list)
    production_footprint: list[FactItem] = Field(default_factory=list)
    supply_chain: list[FactItem] = Field(default_factory=list)
    strategic_context: list[FactItem] = Field(default_factory=list)
    market_position: list[FactItem] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)


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
    contract_version: str = "1.0"
    language: Language = "en"
    company_input: CompanyInput | None = None
    company_profile: CompanyProfile
    company_intelligence: CompanyIntelligence | None = None
    evidence: list[RetrievedEvidence]
    risks: list[RiskItem]
    scenarios: list[ScenarioResult]
    recommendation: Recommendation
    scoring: dict[str, int] = Field(default_factory=dict)
    chat_analysis: ChatAnalysis | None = None
    chat_history: list[ChatTurn] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    limitations: list[str]
    model_mode: Literal["mock", "deepseek"]
    model_name: str = "mock"
    data_mode: Literal["mock", "live", "hybrid"]
    llm_calls: list[LLMCallRecord] = Field(default_factory=list)
    degraded: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
