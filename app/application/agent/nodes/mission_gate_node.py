from __future__ import annotations

import json
from typing import Literal

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.application.agent.models import (
    CORE_STEP_IDS,
    CoachPlan,
    CoachPlanStatus,
    CoachPlanStepUpdate,
)
from app.application.agent.state_schema import AgentState


class MissionGateDecision(BaseModel):
    mission_status: dict[str, Literal["done", "missing"]] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    should_ask_clarification: bool = False
    reason: str = ""


class MissionGateNode:
    """
    Context sufficiency gate for coaching route.
    """

    def __init__(self, classifier_model: BaseChatModel) -> None:
        self.classifier_model = classifier_model

    async def __call__(
        self,
        state: AgentState,
        config: RunnableConfig | None = None,
    ) -> AgentState:
        if state.route != "coach":
            return {"mission_gate": {}}
        if not state.coach_plan:
            raise RuntimeError("MissionGateNode: missing coach_plan in state")

        plan = CoachPlan.model_validate(state.coach_plan)
        user_text = _last_human_message_text(state.messages)
        evidence_summary = _collect_recent_guide_evidence(state.messages)

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
                        f"evidence_summary={evidence_summary}\n"
                        f"current_plan={plan.model_dump(mode='json')}"
                    )
                ),
            ]
        )

        gate = decision.model_dump(mode="json")
        forced_missing_steps = _forced_missing_core_steps(plan, gate["mission_status"])
        should_ask = bool(gate["should_ask_clarification"] or forced_missing_steps)
        missing_fields = list(gate["missing_fields"])
        missing_fields.extend(forced_missing_steps)
        missing_fields = sorted(set(missing_fields))

        updates = _build_gate_updates(
            mission_status=gate["mission_status"],
            should_ask_clarification=should_ask,
        )
        next_plan = plan.apply_updates(
            updates,
            phase="gate_evaluation",
            should_ask_clarification=should_ask,
            missing_fields=missing_fields,
        )

        payload = {
            "plan_id": next_plan.plan_id,
            "version": next_plan.version,
            "phase": "gate_evaluation",
            "rationale": gate.get("reason", ""),
            "updates": [item.model_dump(mode="json") for item in updates],
            "steps": [step.model_dump(mode="json") for step in next_plan.steps],
            "should_ask_clarification": should_ask,
            "missing_fields": missing_fields,
        }
        await adispatch_custom_event("plan_update", payload, config=config)

        if should_ask and not state.clarification_attempted:
            gate_with_prompt = {
                **gate,
                "should_ask_clarification": True,
                "missing_fields": missing_fields,
                "_clarification_prompted": True,
            }
            return {
                "mission_gate": gate_with_prompt,
                "clarification_attempted": True,
                "coach_plan": next_plan.model_dump(mode="json"),
                "messages": [
                    SystemMessage(
                        content=(
                            "Critical context is missing. Ask exactly one short clarification "
                            "question before continuing."
                        )
                    )
                ],
            }

        gate["should_ask_clarification"] = should_ask
        gate["missing_fields"] = missing_fields
        return {"mission_gate": gate, "coach_plan": next_plan.model_dump(mode="json")}


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


def _forced_missing_core_steps(
    plan: CoachPlan, mission_status: dict[str, str]
) -> list[str]:
    missing: list[str] = []
    for step_id in CORE_STEP_IDS:
        raw_status = mission_status.get(step_id.value)
        if raw_status == "done":
            continue
        current = next((step for step in plan.steps if step.id == step_id), None)
        if current and current.status == CoachPlanStatus.COMPLETED:
            continue
        missing.append(step_id.value)
    return missing


def _build_gate_updates(
    mission_status: dict[str, str],
    *,
    should_ask_clarification: bool,
) -> list[CoachPlanStepUpdate]:
    updates: list[CoachPlanStepUpdate] = []
    for step_id in CORE_STEP_IDS:
        raw_status = mission_status.get(step_id.value)
        if raw_status == "done":
            updates.append(
                CoachPlanStepUpdate(
                    id=step_id,
                    status=CoachPlanStatus.COMPLETED,
                )
            )
            continue
        updates.append(
            CoachPlanStepUpdate(
                id=step_id,
                status=(
                    CoachPlanStatus.BLOCKED
                    if should_ask_clarification
                    else CoachPlanStatus.IN_PROGRESS
                ),
            )
        )
    return updates
