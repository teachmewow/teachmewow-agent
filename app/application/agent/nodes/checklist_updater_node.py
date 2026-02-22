from __future__ import annotations

import json
from typing import Optional

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
    CoachPlan,
    CoachPlanStatus,
    CoachPlanStepId,
    CoachPlanStepUpdate,
)
from app.application.agent.state_schema import AgentState


class ChecklistUpdateItem(BaseModel):
    id: CoachPlanStepId
    status: CoachPlanStatus
    observations: str | None = None


class ChecklistUpdateDecision(BaseModel):
    updates: list[ChecklistUpdateItem] = Field(default_factory=list)
    rationale: str = ""


class ChecklistUpdaterNode:
    """
    Applies checklist progress updates after tool-backed coach iterations.
    """

    def __init__(self, classifier_model: BaseChatModel) -> None:
        self.classifier_model = classifier_model

    async def __call__(
        self,
        state: AgentState,
        config: Optional[RunnableConfig] = None,  # noqa: UP045
    ) -> AgentState:
        if state.route != "coach":
            return {}
        if not state.coach_plan:
            raise RuntimeError("ChecklistUpdaterNode: missing coach_plan in state")

        plan = CoachPlan.model_validate(state.coach_plan)
        evidence_summary = _collect_recent_tool_evidence(state.messages)
        user_text = _last_human_message_text(state.messages)

        structured = self.classifier_model.with_structured_output(
            ChecklistUpdateDecision
        )
        decision = await structured.ainvoke(
            [
                SystemMessage(
                    content=(
                        "Update the coaching checklist after tool execution.\n"
                        "Allowed status values: pending, in_progress, completed, blocked.\n"
                        "Only update existing steps and keep output strictly on schema."
                    )
                ),
                HumanMessage(
                    content=(
                        f"user_text={user_text}\n"
                        f"plan_snapshot={plan.model_dump(mode='json')}\n"
                        f"tool_evidence={evidence_summary}"
                    )
                ),
            ]
        )

        updates = [
            CoachPlanStepUpdate(
                id=item.id, status=item.status, observations=item.observations
            )
            for item in decision.updates
        ]
        next_plan = plan.apply_updates(updates, phase="tool_iteration")
        payload = {
            "plan_id": next_plan.plan_id,
            "version": next_plan.version,
            "phase": "tool_iteration",
            "rationale": decision.rationale,
            "updates": [item.model_dump(mode="json") for item in updates],
            "steps": [step.model_dump(mode="json") for step in next_plan.steps],
            "should_ask_clarification": next_plan.should_ask_clarification,
            "missing_fields": next_plan.missing_fields,
        }
        await adispatch_custom_event("plan_update", payload, config=config)
        return {"coach_plan": next_plan.model_dump(mode="json")}


def _last_human_message_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content or "").strip()
    return ""


def _collect_recent_tool_evidence(messages: list[BaseMessage]) -> str:
    rows: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            continue
        raw_text = str(message.content)
        try:
            parsed = json.loads(raw_text)
        except Exception:
            rows.append(raw_text[:240])
            if len(rows) >= 4:
                break
            continue

        tool_name = str(parsed.get("tool") or "").strip() if isinstance(parsed, dict) else ""
        if isinstance(parsed, dict):
            citations = parsed.get("citations")
            evidence = parsed.get("evidence")
            rows.append(
                f"tool={tool_name} citations={len(citations) if isinstance(citations, list) else 0} "
                f"evidence={len(evidence) if isinstance(evidence, list) else 0}"
            )
        if len(rows) >= 4:
            break

    return "\n".join(rows)
