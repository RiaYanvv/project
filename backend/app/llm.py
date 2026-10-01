from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Protocol

import httpx

from .schemas import Assessment, CompanyInput, RetrievedEvidence


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

    def analyze_risks(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        baseline: list[dict[str, Any]],
        language: str = "en",
    ) -> dict[str, Any]:
        ...

    def simulate_scenarios(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        language: str = "en",
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
    ) -> dict[str, Any]:
        ...

    def choose_chat_action(
        self,
        assessment: Assessment,
        message: str,
        language: str = "en",
    ) -> dict[str, Any]:
        ...

    def answer_chat(
        self,
        assessment: Assessment,
        message: str,
        supplemental_evidence: list[RetrievedEvidence],
        language: str = "en",
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

    def analyze_risks(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        baseline: list[dict[str, Any]],
        language: str = "en",
    ) -> dict[str, Any]:
        return {"risks": baseline}

    def simulate_scenarios(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        risks: list[dict[str, Any]],
        baseline: list[dict[str, Any]],
        language: str = "en",
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
    ) -> dict[str, Any]:
        return baseline

    def choose_chat_action(
        self,
        assessment: Assessment,
        message: str,
        language: str = "en",
    ) -> dict[str, Any]:
        return {"action": "answer"}

    def answer_chat(
        self,
        assessment: Assessment,
        message: str,
        supplemental_evidence: list[RetrievedEvidence],
        language: str = "en",
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

    def with_runtime(
        self,
        model: str,
        api_key: str | None,
        event_callback: EventCallback | None = None,
    ) -> "DeepSeekLLM":
        return DeepSeekLLM(
            api_key=api_key or self.api_key,
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

    def analyze_risks(
        self,
        company: CompanyInput,
        evidence: list[RetrievedEvidence],
        baseline: list[dict[str, Any]],
        language: str = "en",
    ) -> dict[str, Any]:
        return self._call_json(
            stage="RiskAgent",
            system=(
                language_prefix(language)
                + "你是供应链地缘政治风险分析师。只返回 JSON，顶层键必须为 risks。"
                "每条风险必须包含 name, category, severity, probability, "
                "business_impact, uncertainty, evidence_ids。severity 只能是 "
                "low, medium, high, critical；probability 是 0-100 整数。"
                "evidence_ids 只能引用输入中的 evidence_id。"
                "不得把 Mock 证据描述为真实事实。"
            ),
            payload={
                "task": "识别企业供应链迁移决策最相关的风险",
                "company": company.model_dump(mode="json"),
                "evidence": self._evidence_payload(evidence),
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
    ) -> dict[str, Any]:
        return self._call_json(
            stage="ScenarioAgent",
            system=(
                language_prefix(language)
                + "你是供应链情景模拟专家。只返回 JSON，顶层键必须为 scenarios，"
                "并给出恰好三个方案。每个方案必须包含 name, description, "
                "cost_score, resilience_score, geopolitical_risk_score, "
                "market_access_score, implementation_score, benefits, risks, "
                "applicable_conditions, evidence_ids。"
                "所有 score 是 0-100 整数，数值越高代表该维度表现越好。"
                "evidence_ids 只能引用输入中的 evidence_id。"
            ),
            payload={
                "task": "比较维持海外布局、提高中国生产比例和混合布局",
                "company": company.model_dump(mode="json"),
                "risks": risks,
                "evidence": self._evidence_payload(evidence),
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
            ),
            payload={
                "task": "生成审慎、可追溯的初步建议",
                "company": company.model_dump(mode="json"),
                "risks": risks,
                "scenarios": scenarios,
                "evidence": self._evidence_payload(evidence),
                "deterministic_baseline": baseline,
            },
            fallback=baseline,
        )

    def choose_chat_action(
        self,
        assessment: Assessment,
        message: str,
        language: str = "en",
    ) -> dict[str, Any]:
        return self._call_json(
            stage="ChatAgent",
            system=(
                "请全程使用中文进行思考。"
                "你是 Agent 的决策器。只返回 JSON。若回答需要补充检索，返回 "
                '{"action":"search_evidence","query":"检索词"}；'
                '若现有证据足够，返回 {"action":"answer"}。'
                "不要直接回答问题，只选择下一步动作。"
            ),
            payload={
                "company": assessment.company_profile.model_dump(mode="json"),
                "user_message": message,
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
    ) -> str:
        result = self._call_json(
            stage="ChatAgent",
            system=(
                language_prefix(language)
                + "你是供应链决策顾问。只返回 JSON，顶层键为 answer，"
                "answer 必须是字符串。"
                "回答必须基于已有评估和证据，明确不确定性，不得编造来源。"
                "若新增信息改变判断，要说明影响；对高风险事项建议人工复核。"
            ),
            payload={
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
        for attempt in range(3):
            try:
                if self.event_callback:
                    content = self._stream_completion(
                        stage=stage,
                        request_payload=request_payload,
                    )
                else:
                    with httpx.Client(timeout=90.0) as client:
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
        return fallback

    def _stream_completion(
        self,
        stage: str,
        request_payload: dict[str, Any],
    ) -> str:
        content_parts: list[str] = []
        with httpx.Client(timeout=120.0) as client:
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
            }
            for item in evidence
        ]
