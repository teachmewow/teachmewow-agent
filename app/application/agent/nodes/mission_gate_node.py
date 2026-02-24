from __future__ import annotations

import json
from typing import Literal, Optional

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
    CORE_MISSION_TAGS,
    CoachPlan,
    CoachPlanStatus,
    CoachPlanStepUpdate,
    MissionTag,
)
from app.application.agent.state_schema import AgentState


class MissionStatusItem(BaseModel):
    mission_tag: MissionTag
    status: Literal["done", "missing"]


class MissionGateDecision(BaseModel):
    mission_status: list[MissionStatusItem] = Field(default_factory=list)
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
        config: Optional[RunnableConfig] = None,  # noqa: UP045
    ) -> AgentState:
        if state.route != "coach":
            return {"mission_gate": {}}
        if not state.coach_plan:
            raise RuntimeError("MissionGateNode: missing coach_plan in state")

        plan = CoachPlan.model_validate(state.coach_plan)
        required_missions = _required_mission_tags_from_plan(plan)
        user_text = _last_human_message_text(state.messages)
        evidence_summary = _collect_recent_guide_evidence(state.messages)
        required_missions_text = "\n".join(
            f"- {mission.value}" for mission in required_missions
        )

        structured = self.classifier_model.with_structured_output(MissionGateDecision)
        decision = await structured.ainvoke(
            [
                SystemMessage(
                    content=(
                        "Evaluate if coaching context is sufficient.\n"
                        "Required missions for this user request:\n"
                        f"{required_missions_text}\n"
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
            ],
            config=config,
        )

        mission_status = _normalize_core_mission_status(
            decision.mission_status,
            required_missions=required_missions,
        )
        forced_missing_missions = _forced_missing_core_missions(
            plan,
            mission_status,
            required_missions=required_missions,
        )
        should_ask = bool(decision.should_ask_clarification or forced_missing_missions)
        required_mission_keys = {mission.value for mission in required_missions}
        missing_fields = [
            item
            for item in decision.missing_fields
            if isinstance(item, str) and item in required_mission_keys
        ]
        missing_fields.extend(forced_missing_missions)
        missing_fields = sorted(set(missing_fields))

        updates = _build_gate_updates(
            plan=plan,
            mission_status=mission_status,
            should_ask_clarification=should_ask,
            required_missions=required_missions,
        )
        next_plan = plan.apply_updates(
            updates,
            phase="gate_evaluation",
            should_ask_clarification=should_ask,
            missing_fields=missing_fields,
        )
        public_plan = next_plan.to_public_payload()

        payload = {
            "plan_id": next_plan.plan_id,
            "version": next_plan.version,
            "phase": "gate_evaluation",
            "rationale": decision.reason,
            "updates": [item.model_dump(mode="json") for item in updates],
            "steps": public_plan["steps"],
            "should_ask_clarification": should_ask,
            "missing_fields": missing_fields,
        }
        await adispatch_custom_event("plan_update", payload, config=config)

        gate = {
            "mission_status": mission_status,
            "missing_fields": missing_fields,
            "should_ask_clarification": should_ask,
            "reason": decision.reason,
        }

        if should_ask and not state.clarification_attempted:
            gate_with_prompt = {**gate, "_clarification_prompted": True}
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


def _normalize_core_mission_status(
    raw_status: list[MissionStatusItem],
    *,
    required_missions: tuple[MissionTag, ...] = CORE_MISSION_TAGS,
) -> dict[str, Literal["done", "missing"]]:
    normalized: dict[str, Literal["done", "missing"]] = {
        mission.value: "missing" for mission in required_missions
    }
    seen: set[str] = set()
    for mission_item in raw_status:
        mission_key = mission_item.mission_tag.value
        mission_value = mission_item.status
        if mission_key not in normalized:
            continue
        if mission_key in seen:
            raise RuntimeError(
                f"MissionGateNode: duplicate mission key '{mission_key}' in mission_status"
            )
        seen.add(mission_key)
        if mission_value not in {"done", "missing"}:
            raise RuntimeError(
                f"MissionGateNode: invalid mission status '{mission_value}' for '{mission_key}'"
            )
        normalized[mission_key] = mission_value
    return normalized


def _forced_missing_core_missions(
    plan: CoachPlan,
    mission_status: dict[str, Literal["done", "missing"]],
    *,
    required_missions: tuple[MissionTag, ...] = CORE_MISSION_TAGS,
) -> list[str]:
    missing: list[str] = []
    for mission_tag in required_missions:
        raw_status = mission_status.get(mission_tag.value, "missing")
        if raw_status == "done":
            continue
        if plan.is_mission_completed(mission_tag):
            continue
        missing.append(mission_tag.value)
    return missing


def _build_gate_updates(
    *,
    plan: CoachPlan,
    mission_status: dict[str, Literal["done", "missing"]],
    should_ask_clarification: bool,
    required_missions: tuple[MissionTag, ...] = CORE_MISSION_TAGS,
) -> list[CoachPlanStepUpdate]:
    updates: list[CoachPlanStepUpdate] = []
    for step in plan.steps:
        if step.mission_tag not in required_missions:
            continue

        raw_status = mission_status.get(step.mission_tag.value, "missing")
        if raw_status == "done":
            updates.append(
                CoachPlanStepUpdate(
                    id=step.id,
                    status=CoachPlanStatus.COMPLETED,
                )
            )
            continue

        updates.append(
            CoachPlanStepUpdate(
                id=step.id,
                status=(
                    CoachPlanStatus.BLOCKED
                    if should_ask_clarification
                    else CoachPlanStatus.IN_PROGRESS
                ),
            )
        )
    return updates


def _required_mission_tags_from_plan(plan: CoachPlan) -> tuple[MissionTag, ...]:
    ordered: list[MissionTag] = []
    seen: set[MissionTag] = set()
    for step in plan.steps:
        if not step.is_core:
            continue
        if step.mission_tag in seen:
            continue
        ordered.append(step.mission_tag)
        seen.add(step.mission_tag)
    if not ordered:
        raise RuntimeError("MissionGateNode: coach_plan has no core mission steps")
    return tuple(ordered)
