from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Protocol

import httpx

from .schemas import Assessment, CompanyInput, CompanyProfile, RetrievedEvidence


logger = logging.getLogger(__name__)
EventCallback = Callable[[dict[str, Any]], None]

# Every stage previously forced Chinese output. The UI is bilingual (English /
# 中文), so the requested language now drives all user-facing model text.
LANGUAGE_PREFIX = {
    "en": (
        "Think and write in English. Every user-facing string (names, categories, "
        "descriptions, impacts, uncertainty, benefits, risks, recommendations) must "
        "be written in English. "
    ),
    "zh": "请全程使用中文进行深度思考和最终输出。面向用户的文字一律使用简体中文。",
}


def language_prefix(language: str | None) -> str:
    return LANGUAGE_PREFIX.get((language or "en").lower(), LANGUAGE_PREFIX["en"])


class LLMProvider(Protocol):
    mode: str

    def with_runtime(
        self,
        model: str,
        api_key: str | None,
        event_callback: EventCallback | None = None,
    ) -> "LLMProvider":
        ...

    def validate_key(self) -> bool:
        ...

    def build_intelligence(
        self,
        company: CompanyInput,
        profile: CompanyProfile,
        evidence: list[RetrievedEvidence],
        language: str = "en",
    ) -> dict[str, Any]:
        ...

    def understand_entity(
        self,
        company: CompanyInput,
        language: str = "en",
    ) -> dict[str, Any]:
        ...

    def analyze_risks(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        baseline: list[dict[str, Any]],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def simulate_scenarios(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def generate_recommendation(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
        baseline: dict[str, Any],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def choose_chat_action(
        self,
        assessment: Assessment,
        message: str,
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def answer_chat(
        self,
        assessment: Assessment,
        message: str,
        supplemental_evidence: list[RetrievedEvidence],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> str:
        ...


class MockLLM:
    mode = "mock"

    def with_runtime(
        self,
        model: str,
        api_key: str | None,
        event_callback: EventCallback | None = None,
    ) -> "MockLLM":
        return self

    def validate_key(self) -> bool:
        return True

    def build_intelligence(
        self,
        company: CompanyInput,
        profile: CompanyProfile,
        evidence: list[RetrievedEvidence],
        language: str = "en",
    ) -> dict[str, Any]:
        return {}

    def understand_entity(
        self,
        company: CompanyInput,
        language: str = "en",
    ) -> dict[str, Any]:
        return {"entity": {}}

    def analyze_risks(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        baseline: list[dict[str, Any]],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"risks": baseline}

    def simulate_scenarios(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"scenarios": baseline}

    def generate_recommendation(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
        baseline: dict[str, Any],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return baseline

    def choose_chat_action(
        self,
        assessment: Assessment,
        message: str,
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"action": "answer"}

    def answer_chat(
        self,
        assessment: Assessment,
        message: str,
        supplemental_evidence: list[RetrievedEvidence],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> str:
        zh = (language or "en").lower() == "zh"
        normalized = message.lower()
        if any(term in normalized for term in ("cost", "budget", "成本", "投资", "预算")):
            return (
                "成本约束已纳入重新评估。下一轮应补充投资预算上限、当地固定资产"
                "沉没成本，以及中国与现有海外基地的单位成本差。"
                if zh
                else "The cost constraint is now part of the assessment. Useful next inputs: "
                "the investment ceiling, the sunk cost of existing assets, and the unit-cost "
                "gap between China and the current overseas sites."
            )
        if any(term in normalized for term in ("time", "时间", "期限")):
            return (
                "决策时间会改变可行方案，建议补充产能爬坡和审批周期。"
                if zh
                else "Timing changes which options stay feasible; adding capacity ramp-up and "
                "approval lead times would sharpen the comparison."
            )
        if any(
            term in normalized
            for term in ("tariff", "关税", "export", "出口管制", "管制")
        ):
            return (
                "政策风险已提升为重点观察项。建议补充产品 HS/ECCN 编码、"
                "客户所在地和关键供应商。"
                if zh
                else "Policy exposure has moved up the watch list. Adding HS/ECCN codes, "
                "customer locations and critical suppliers would make this assessment "
                "company specific."
            )
        if supplemental_evidence:
            return (
                "已调用证据检索工具，并找到补充材料。请继续提供具体约束以便细化分析。"
                if zh
                else "I searched the evidence base and found additional material. Give me the "
                "specific constraint you care about and I will fold it into the analysis."
            )
        return (
            "信息已记录。当前回答基于现有证据，补充约束后可重新运行评估。"
            if zh
            else "Noted. This answer is based on the evidence already retrieved; add a concrete "
            "constraint and the scenario analysis can be re-run."
        )


class DeepSeekLLM:
    mode = "deepseek"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        event_callback: EventCallback | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.event_callback = event_callback
        self.last_call_meta: dict[str, Any] | None = None

    def with_runtime(
        self,
        model: str,
        api_key: str | None,
        event_callback: EventCallback | None = None,
    ) -> "DeepSeekLLM":
        return DeepSeekLLM(
            # A server-side key configured in .env is authoritative. This keeps
            # the shared backend on DeepSeek even when a browser supplies no key
            # or still contains a stale frontend placeholder.
            api_key=self.api_key or api_key,
            base_url=self.base_url,
            model=model or self.model,
            event_callback=event_callback,
        )

    def validate_key(self) -> bool:
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def build_intelligence(
        self,
        company: CompanyInput,
        profile: CompanyProfile,
        evidence: list[RetrievedEvidence],
        language: str = "en",
    ) -> dict[str, Any]:
        return self._call_json(
            stage="IntelligenceAgent",
            system=(
                language_prefix(language)
                + "你是企业情报分析师。只返回 JSON，顶层键必须为 executive_summary, "
                "entity, overview, production_footprint, supply_chain, "
                "strategic_context, market_position, business_profile, "
                "manufacturing_footprint, supply_chain_role, decision_context, "
                "supply_chain_structure, evidence_references, information_gaps。"
                "所有面向用户的文字（包括段落小标题）必须使用目标语言。"
                "证据分级：每条 evidence 带 source_tier。tier 1 是公司自身披露"
                "（年报、公告、交易所披露、官网、注册信息），tier 2 是公司专项可靠"
                "报道，tier 3 是行业背景，tier 4 是政策法规。公司事实只能来自 "
                "tier 1/2；tier 3 只能作为行业背景，并且必须明确说明这是行业层面"
                "而非该公司的情况；不得把 tier 4 的政策材料写成公司事实。"
                "本阶段是给这家公司建模，不是写行业报告：如果某项内容对任何电池"
                "企业都成立，就不要写进公司事实，应放入行业背景或 information_gaps。"
                "事实数组每项包含 fact_id, fact, source_ids, data_status, "
                "confidence, as_of, derived_from, conflict；source_ids 只能引用"
                "输入中的 evidence_id。data_status 只能是 user_input, "
                "public_source, inferred, to_be_confirmed。"
                "data_status 只看证据是否直接陈述了这条事实：证据原文写明的事实"
                "（即使被翻译成目标语言，例如年报里的营收、营业利润、工厂所在地、"
                "生产与销售结构、投资与合资）就是 public_source，不要因为句子是归纳"
                "语气或与原文措辞不同就降级；只有由多条事实综合出的结论、或证据没有"
                "写到的情况才用 inferred；仅来自用户表单的用 user_input。"
                "fact 必须是一个字符串，不要返回对象。"
                "不要把字段名或字段取值（例如 public_source、high、unknown、"
                "EVD-... 编号列表）当作 fact 输出；每条 fact 必须是关于这家公司的一句话。"
                "public_source 只允许承载具体公司事实，而且 source_ids 必须来自"
                "原文中包含该事实要素的公司证据；不得写“检索到 N 条资料”。"
                "用户输入是 Baseline，不能被公开推断覆盖；冲突时保留两方并置 "
                "conflict=true。"
                "避免重复：用户表单是原始输入，不是企业画像。不要在多个 section 里"
                "反复抄写公司名、生产比例、目标市场、决策问题、优先级或限制条件。"
                "overview 只写公司身份与业务；生产比例只出现在 manufacturing_footprint；"
                "目标市场只出现在 business_profile；用户决策问题只在 decision_context "
                "出现一次。"
                "strategic_context 必须恰好覆盖四段：公司现状、供应链结构与依赖、"
                "经营结构与布局逻辑、关键未知信息。段落标题必须使用目标语言"
                "（中文输出用中文标题，英文输出用英文标题），不得直接照抄英文小标题。"
                "每段至少引用 2 条公司事实；无法确认就明确写 unknown，不能只复述表单。"
                "第三段只描述这家公司为什么形成现在的生产和供应链结构，必须由已验证"
                "的公司事实支撑；不要写关税、出口管制、原产地风险、风险等级或方案优劣。"
                "strategic_context 的每一项同样必须是事实对象（含 fact, source_ids, "
                "data_status），每项一段；不要返回纯字符串数组。"
                "本阶段只描述企业在供应链中的位置与已知事实，不做任何风险判断："
                "不评估风险、不给严重程度、不建议是否迁移、不比较方案优劣——"
                "这些属于后续的风险评估与情景模拟阶段。"
                "business_profile 包含 model, value_chain_role, products, "
                "customers, source_ids。manufacturing_footprint 每项包含 country, "
                "facility, role, production_share, capacity, source_type, status, "
                "source_ids；production_share 未知时用 null，capacity 未知时写 unknown。"
                "manufacturing_footprint 必须为用户的每一个生产国家保留一行，country "
                "原样沿用用户写法的国家名称，production_share 原样保留用户给出的数字，"
                "source_type=user_input；如果公司披露（tier 1/2）确认该国家有生产基地，"
                "就在这一行补上 facility（证据原文中的工厂、城市或园区名称，例如南京、"
                "梧仓、清州、密歇根、弗罗茨瓦夫），并把 source_type 改为 company_filing、"
                "填上 source_ids、status=reported，同一个国家不要出现两行。公司披露确认"
                "但用户未列出的生产国家（例如波兰、加拿大）可以新增一行，production_share "
                "必须为 null。不得把用户给出的比例扩展成完整分布，不得为任何国家推算占比，"
                "不得估算 capacity、分基地产能或 role：无法确认时 capacity=unknown、"
                "facility/role 留空字符串。"
                "supply_chain_role 包含 primary, secondary, upstream, manufacturing, "
                "downstream, unknown；除 primary/secondary/unknown 外均为 FactItem 数组。"
                "primary 与 secondary 只能从以下受控词表中取值，必须原样输出大写英文"
                "枚举，不得输出中文说明或整句描述：UPSTREAM_RAW_MATERIAL（原材料与矿产："
                "锂、镍、钴、石墨等）、UPSTREAM_COMPONENT（电池材料与零部件：正极、"
                "负极、电解液、隔膜等）、BATTERY_MANUFACTURING（电芯、模组、电池包制造）、"
                "DOWNSTREAM_APPLICATION（整车厂、储能系统、回收等下游应用）、"
                "INTEGRATED_BATTERY_COMPANY（横跨多个环节的一体化企业）、"
                "OTHER（无法确认）。primary 必须有值；无法确认时用 OTHER，不得推断。"
                "secondary 是枚举值数组，可为空数组，同样不得写解释性文字。"
                "supply_chain_structure 是本阶段最重要的补充：按 "
                "raw_material → component → manufacturing → downstream 逐环节重建"
                "该公司的供应链，至少覆盖 3 个环节。每项包含 stage, description, "
                "region, company_role, share, share_basis, source_ids。region 填已知"
                "的地理依赖（无法确认写 unknown）；company_role 填该公司在这个环节"
                "的角色；share 是近似比重，只有来自用户输入、公司披露或有明确来源的"
                "估计时才能写数字，否则必须写 unknown，并用 share_basis 标注 "
                "user_input / disclosed / sourced_estimate / unknown。"
                "绝对不要自己估算一个百分比。"
                "decision_context 包含 objective, drivers, constraints, source_ids。"
                "decision_context 只写 2-3 句综合判断（用户为什么评估、已知约束是"
                "什么），不要逐项复述表单字段。"
                "evidence_references 每项包含 evidence_id, title, publisher, "
                "source_type, used_for；只能引用输入 evidence_id。"
                "information_gaps 必须是对象数组，每项包含 item, priority, "
                "why_it_matters, recommended_action, source_ids；priority 只能是 "
                "critical, important, optional。不要返回字符串数组。"
                "information_gaps 要少而有用：critical 最多 3 条、important 最多 3 条、"
                "optional 最多 3 条；同一件事不要拆成多条。"
                "产能、产能利用率、客户名单、供应商名单、单位成本、订单积压等"
                "无法确认的信息必须进入 information_gaps。"
            ),
            payload={
                "task": "构建企业情报画像：企业概况、全球生产布局、供应链结构、战略情境与信息缺口",
                "company": company.model_dump(mode="json"),
                "profile": profile.model_dump(mode="json"),
                "evidence": self._evidence_payload(evidence),
            },
            fallback={},
        )

    def understand_entity(
        self,
        company: CompanyInput,
        language: str = "en",
    ) -> dict[str, Any]:
        return self._call_json(
            stage="EntityAgent",
            system=(
                language_prefix(language)
                + "你是企业实体消歧节点。只返回 JSON，顶层键必须为 entity。"
                "entity 必须包含 legal_name, aliases, headquarters, listing, "
                "founded_year, size, source_ids, data_status。"
                "listing 包含 exchange, ticker；size 包含 revenue_range, "
                "employees_range, factories_count。"
                "用户提供的公司名称和母国是 Baseline，不得因公开资料无法核实"
                "而否定它。aliases 用于后续公司检索，可包含英文名、中文名、"
                "简称和常见别名；无法确认的字段留空并标 to_be_confirmed。"
            ),
            payload={
                "task": "识别企业实体并生成检索别名",
                "company": company.model_dump(mode="json"),
            },
            fallback={"entity": {}},
        )

    def analyze_risks(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        baseline: list[dict[str, Any]],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._call_json(
            stage="RiskAgent",
            system=(
                language_prefix(language)
                + "你是供应链地缘政治风险分析师。只返回 JSON，顶层键必须为 risks。"
                "最终只保留 4-5 个核心风险，不要输出高度重叠的风险。"
                "每条风险必须包含 title, category, company_specific_trigger, "
                "external_mechanism, impact_channels, impact_description, "
                "likelihood_score, impact_score, company_exposure_score, "
                "decision_relevance, uncertainty_reasons, "
                "what_would_change_assessment, supporting_evidence_ids。"
                "likelihood_score / impact_score / company_exposure_score 必须是 "
                "1-5 整数；decision_relevance 只能是 low/medium/high。"
                "category 只能使用 TRADE, POLITICAL, SUPPLY_CHAIN, REGULATORY, "
                "MARKET_ACCESS, OPERATIONAL；Financial/CapEx 归入 OPERATIONAL。"
                "company_specific_trigger 必须引用 company_intelligence 中的具体"
                "公司事实，不能只写行业级判断。external_mechanism 必须说明政策、"
                "贸易、供应链或运营机制。"
                "impact_channels 从中选择：cost, lead_time, production_continuity, "
                "market_access, compliance_burden, capacity_expansion, "
                "customer_delivery, implementation_feasibility。"
                "supporting_evidence_ids 只能引用输入中的 evidence_id；没有合格证据"
                "时返回空数组并设置 insufficient_evidence=true。"
                "不得输出 INFORMATION_QUALITY 或资料质量类风险，这些属于信息缺口。"
                "必须以 company_intelligence 中的公司事实为前提，写出这家公司的风险："
                "结合其生产基地、供应链角色与目标市场说明暴露路径；不得只给行业级结论"
                "（例如“电池企业面临关税风险”应改写为结合该公司具体基地与原产地的判断）。"
                "公司事实取自 company_evidence，政策暴露取自 policy_evidence。"
                "不得把 Mock 证据描述为真实事实。"
            ),
            payload={
                "task": "识别企业供应链迁移决策最相关的风险",
                "company": company.model_dump(mode="json"),
                # Required company context: the risk must be this company's risk,
                # not a generic industry statement.
                "company_intelligence": company_intelligence or {},
                **self._split_evidence_payload(evidence),
                "deterministic_baseline": baseline,
            },
            fallback={"risks": baseline},
        )

    def simulate_scenarios(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._call_json(
            stage="ScenarioAgent",
            system=(
                language_prefix(language)
                + "你是供应链情景模拟专家。只返回 JSON，顶层键必须为 scenarios，"
                "并给出恰好三个方案。每个方案必须包含 name, description, "
                "dimension_assessments, benefits, risks, applicable_conditions, "
                "evidence_ids。"
                "dimension_assessments 必须包含 cost, resilience, geopolitical_risk, "
                "market_access, implementation 五个维度；每项包含 band, reason, "
                "evidence_ids, source。"
                "band 只能是 very_favourable, favourable, neutral, unfavourable, "
                "very_unfavourable；source 只能是 evidence 或 inference。"
                "档位定义：very_favourable=证据明确支持且无重大不确定性；"
                "favourable=证据支持但存在可控不确定性；"
                "neutral=证据不足或无法区分优劣；"
                "unfavourable=证据明确指向成本、风险或实施压力上升；"
                "very_unfavourable=证据明确指向重大暴露或不可行。"
                "不要输出 0-100 分数，最终分数由后端 rubric 映射。"
                "有证据支持时 source=evidence，并在 evidence_ids 中引用证据；"
                "证据不足时使用 neutral + inference，不得凭感觉给高分或低分。"
                "evidence_ids 只能引用输入中的 evidence_id。"
                "情景必须结合 company_intelligence 中的现有生产基地、供应链角色与"
                "目标市场来描述，而不是给通用方案；不同公司的同一方案应体现其自身布局。"
            ),
            payload={
                "task": "比较维持海外布局、提高中国生产比例和混合布局",
                "company": company.model_dump(mode="json"),
                "company_intelligence": company_intelligence or {},
                "risks": risks,
                **self._split_evidence_payload(evidence),
                "deterministic_baseline": baseline,
            },
            fallback={"scenarios": baseline},
        )

    def generate_recommendation(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        scenarios: list[dict[str, Any]],
        baseline: dict[str, Any],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._call_json(
            stage="AdvisorAgent",
            system=(
                language_prefix(language)
                + "你是企业战略顾问。只返回 JSON，顶层键必须为 recommendation 和 "
                "limitations。recommendation 必须包含 recommended_scenario_id, "
                "headline, rationale, next_actions, confidence, uncertainty, "
                "requires_human_review。recommended_scenario_id 必须来自输入方案。"
                "confidence 只能是 low, medium, high。"
                "如果存在 critical/high 风险或证据不足，requires_human_review 必须为 true。"
                "建议必须落在该公司自身情况上（company_intelligence 的生产基地、"
                "供应链角色、目标市场与信息缺口），不得给与该企业无关的通用建议。"
            ),
            payload={
                "task": "生成审慎、可追溯的初步建议",
                "company": company.model_dump(mode="json"),
                "company_intelligence": company_intelligence or {},
                "risks": risks,
                "scenarios": scenarios,
                **self._split_evidence_payload(evidence),
                "deterministic_baseline": baseline,
            },
            fallback=baseline,
        )

    def choose_chat_action(
        self,
        assessment: Assessment,
        message: str,
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._call_json(
            stage="ChatAgent",
            system=(
                language_prefix(language)
                + "你是 Agent 的决策器。只返回 JSON。若回答需要补充检索，返回 "
                '{"action":"search_evidence","query":"检索词"}；'
                '若现有证据足够，返回 {"action":"answer"}；'
                '若存在 critical/important 且未解决的 information gap，返回 '
                '{"action":"ask_gap","gap_item":"...","question":"...",'
                '"why_it_matters":"...",'
                '"affected_dimensions":["cost|resilience|geopolitical_risk|market_access|implementation"]}。'
                "如果用户本轮提供了缺口信息，返回 answer，并输出 "
                "profile_patch、gap_updates（gap_item/status/answer）、"
                "affected_dimensions 和 scenario_update_required。"
                "判断前先看 company_intelligence 中这家公司是谁及其 open gaps。"
                "不要直接回答普通问题，只选择下一步动作。"
            ),
            payload={
                "company_intelligence": company_intelligence or {},
                "company": assessment.company_profile.model_dump(mode="json"),
                "user_message": message,
                "open_information_gaps": [
                    (
                        gap.model_dump(mode="json")
                        if not isinstance(gap, str)
                        else {"item": gap, "priority": "important", "status": "open"}
                    )
                    for gap in (
                        assessment.company_intelligence.information_gaps
                        if assessment.company_intelligence
                        else []
                    )
                    if (
                        not isinstance(gap, str)
                        and gap.status != "resolved"
                    ) or isinstance(gap, str)
                ],
                "chat_history": [
                    turn.model_dump(mode="json")
                    for turn in assessment.chat_history[-10:]
                ],
                "current_risks": [
                    item.model_dump(mode="json") for item in assessment.risks
                ],
            },
            fallback={"action": "answer"},
        )

    def answer_chat(
        self,
        assessment: Assessment,
        message: str,
        supplemental_evidence: list[RetrievedEvidence],
        language: str = "en",
        company_intelligence: dict[str, Any] | None = None,
    ) -> str:
        result = self._call_json(
            stage="ChatAgent",
            system=(
                language_prefix(language)
                + "你是供应链决策顾问。只返回 JSON，顶层键为 answer，"
                "answer 必须是字符串。"
                "回答必须基于已有评估和证据，明确不确定性，不得编造来源。"
                "回答要先结合 company_intelligence 中这家公司的业务模式、供应链角色、"
                "生产基地与待补信息，再给结论。"
                "若新增信息改变判断，要说明影响；对高风险事项建议人工复核。"
            ),
            payload={
                "company_intelligence": company_intelligence or {},
                "company": assessment.company_profile.model_dump(mode="json"),
                "current_assessment": {
                    "risks": [
                        item.model_dump(mode="json") for item in assessment.risks
                    ],
                    "scenarios": [
                        item.model_dump(mode="json") for item in assessment.scenarios
                    ],
                    "recommendation": assessment.recommendation.model_dump(mode="json"),
                },
                "existing_evidence": self._evidence_payload(assessment.evidence),
                "supplemental_evidence": self._evidence_payload(
                    supplemental_evidence
                ),
                "chat_history": [
                    turn.model_dump(mode="json")
                    for turn in assessment.chat_history[-10:]
                ],
                "user_message": message,
            },
            fallback={"answer": "当前模型未能生成回答，请稍后重试。"},
        )
        answer = result.get("answer")
        if isinstance(answer, dict):
            sections = [
                answer.get("direct_answer"),
                answer.get("retrieval_note"),
            ]
            reasoning = answer.get("reasoning")
            if isinstance(reasoning, list):
                sections.extend(str(item) for item in reasoning[:3])
            normalized = "\n\n".join(
                str(item).strip() for item in sections if item
            )
            if normalized:
                return normalized
        if not isinstance(answer, str) or not answer.strip():
            return "当前模型未能生成有效回答，请稍后重试。"
        return answer.strip()

    def _call_json(
        self,
        stage: str,
        system: str,
        payload: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        request_payload = {
            "model": self.model,
            "temperature": 0.15,
            "stream": bool(self.event_callback),
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
        }
        last_error: Exception | None = None
        started = time.perf_counter()
        attempts = 0
        for attempt in range(3):
            attempts += 1
            try:
                if self.event_callback:
                    content = self._stream_completion(
                        stage=stage,
                        request_payload=request_payload,
                    )
                else:
                    with httpx.Client(timeout=240.0) as client:
                        response = client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._headers(),
                            json=request_payload,
                        )
                        response.raise_for_status()
                    content = response.json()["choices"][0]["message"]["content"]
                result = self._parse_json_content(content)
                if not isinstance(result, dict):
                    raise TypeError("model JSON is not an object")
                meta = {
                    "stage": stage,
                    "provider": self.mode,
                    "model": self.model,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "attempts": attempts,
                    "ok": True,
                    "error": "",
                }
                self.last_call_meta = meta
                result["__llm_meta__"] = meta
                return result
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                last_error = exc
                if attempt < 2:
                    self._emit(
                        {
                            "type": "status",
                            "agent": stage,
                            "message": f"网络波动，正在重试（{attempt + 2}/3）",
                        }
                    )
                    time.sleep(1.0 + attempt)

        logger.warning("DeepSeek JSON call failed after retries: %s", last_error)
        result = dict(fallback)
        meta = {
            "stage": stage,
            "provider": self.mode,
            "model": self.model,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "attempts": attempts,
            "ok": False,
            "error": f"{type(last_error).__name__}: {last_error}",
        }
        self.last_call_meta = meta
        result["__llm_meta__"] = meta
        return result

    def _stream_completion(
        self,
        stage: str,
        request_payload: dict[str, Any],
    ) -> str:
        content_parts: list[str] = []
        with httpx.Client(timeout=240.0) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=request_payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = line[6:] if line.startswith("data: ") else line
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    reasoning = delta.get("reasoning_content")
                    if isinstance(reasoning, str) and reasoning:
                        self._emit(
                            {
                                "type": "reasoning",
                                "agent": stage,
                                "delta": reasoning,
                            }
                        )
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        content_parts.append(content)
        return "".join(content_parts)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }

    def _emit(self, event: dict[str, Any]) -> None:
        if not self.event_callback:
            return
        try:
            self.event_callback(event)
        except Exception:
            logger.debug("event callback failed", exc_info=True)

    @staticmethod
    def _parse_json_content(content: Any) -> dict[str, Any]:
        if not isinstance(content, str):
            raise TypeError("model content is not a string")
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            result = json.loads(cleaned[start : end + 1])
        if not isinstance(result, dict):
            raise TypeError("model JSON is not an object")
        return result

    @staticmethod
    def _evidence_payload(
        evidence: list[RetrievedEvidence],
    ) -> list[dict[str, Any]]:
        return [
            {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "content": item.content[:2400],
                "publisher": item.publisher,
                "publication_date": item.publication_date,
                "authority_level": item.authority_level,
                "url": item.url,
                "topic": item.topic,
                "is_mock": item.is_mock,
                # Profile evidence priority (Company Intelligence revision).
                "source_tier": item.source_tier,
            }
            for item in evidence
        ]

    @classmethod
    def _split_evidence_payload(
        cls,
        evidence: list[RetrievedEvidence],
    ) -> dict[str, list[dict[str, Any]]]:
        """Company evidence and policy/risk evidence are labelled separately.

        Both come from the same retrieval run, but downstream prompts must use
        company material for company-specific claims and policy material for
        exposure. The total token cost is unchanged.
        """
        return {
            "company_evidence": cls._evidence_payload(
                [item for item in evidence if item.evidence_scope == "company"]
            ),
            "policy_evidence": cls._evidence_payload(
                [item for item in evidence if item.evidence_scope != "company"]
            ),
        }
