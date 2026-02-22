from __future__ import annotations

import json
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from app.application.agent.state_schema import AgentState


class MissionGateDecision(BaseModel):
    mission_status: dict[str, Literal["done", "missing"]] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    should_ask_clarification: bool = False
    reason: str = ""


class MissionGateNode:
    """
    Lightweight context sufficiency gate for coaching route.
    """

    def __init__(self, classifier_model: BaseChatModel) -> None:
        self.classifier_model = classifier_model

    async def __call__(self, state: AgentState, config=None) -> AgentState:
        if state.route != "coach":
            return {"mission_gate": {}}

        user_text = _last_human_message_text(state.messages)
        evidence_summary = _collect_recent_guide_evidence(state.messages)
        fallback = _fallback_gate(evidence_summary)

        try:
            structured = self.classifier_model.with_structured_output(MissionGateDecision)
            decision = await structured.ainvoke(
                [
                    SystemMessage(
                        content=(
                            "Evaluate if coaching context is sufficient.\n"
                            "Missions:\n"
                            "- core_skills\n"
                            "- build_vs_baseline\n"
                            "- tips_and_tricks\n"
                            "- assumptions_checked\n"
                            "Return strict JSON using schema fields only."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"user_text={user_text}\n"
                            f"active_build_present={state.build_info is not None or bool(state.active_build_id)}\n"
                            f"evidence_summary={evidence_summary}"
                        )
                    ),
                ]
            )
            gate = decision.model_dump()
            if (
                gate.get("should_ask_clarification")
                and not state.clarification_attempted
            ):
                gate_with_prompt = dict(gate)
                gate_with_prompt["_clarification_prompted"] = True
                return {
                    "mission_gate": gate_with_prompt,
                    "clarification_attempted": True,
                    "messages": [
                        SystemMessage(
                            content=(
                                "Critical context is missing. Ask exactly one short clarification "
                                "question before continuing."
                            )
                        )
                    ],
                }
            return {"mission_gate": gate}
        except Exception:
            if fallback.get("should_ask_clarification") and not state.clarification_attempted:
                fallback_with_prompt = dict(fallback)
                fallback_with_prompt["_clarification_prompted"] = True
                return {
                    "mission_gate": fallback_with_prompt,
                    "clarification_attempted": True,
                    "messages": [
                        SystemMessage(
                            content=(
                                "Critical context is missing. Ask exactly one short clarification "
                                "question before continuing."
                            )
                        )
                    ],
                }
            return {"mission_gate": fallback}


def _last_human_message_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content or "").strip()
    return ""


def _collect_recent_guide_evidence(messages: list[BaseMessage]) -> str:
    collected: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            continue
        try:
            parsed = json.loads(str(message.content))
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        if parsed.get("tool") != "guide_context_lookup":
            continue
        evidence = parsed.get("evidence")
        if isinstance(evidence, list):
            for item in evidence[:4]:
                if not isinstance(item, dict):
                    continue
                marker = str(item.get("marker") or "").strip()
                source_id = str(item.get("source_id") or "").strip()
                text = str(item.get("text") or "").strip()
                if text:
                    collected.append(f"{marker}|{source_id}|{text[:180]}")
        if len(collected) >= 8:
            break
    return "\n".join(collected)


def _fallback_gate(evidence_summary: str) -> dict:
    has_evidence = bool(evidence_summary.strip())
    status = "done" if has_evidence else "missing"
    return {
        "mission_status": {
            "core_skills": status,
            "build_vs_baseline": status,
            "tips_and_tricks": status,
            "assumptions_checked": status,
        },
        "missing_fields": [] if has_evidence else ["guide_evidence"],
        "should_ask_clarification": not has_evidence,
        "reason": "fallback_gate_no_classifier" if not has_evidence else "fallback_gate_with_evidence",
    }
