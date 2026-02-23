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
    CoachPlanStepUpdate,
)
from app.application.agent.state_schema import AgentState


class ChecklistUpdateItem(BaseModel):
    id: str
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
        decision = await self._decide_with_retry(
            plan=plan,
            user_text=user_text,
            evidence_summary=evidence_summary,
            config=config,
        )
        updates = _build_validated_updates(plan=plan, items=decision.updates)
        next_plan = plan.apply_updates(updates, phase="tool_iteration")
        public_plan = next_plan.to_public_payload()
        payload = {
            "plan_id": next_plan.plan_id,
            "version": next_plan.version,
            "phase": "tool_iteration",
            "rationale": decision.rationale,
            "updates": [item.model_dump(mode="json") for item in updates],
            "steps": public_plan["steps"],
            "should_ask_clarification": next_plan.should_ask_clarification,
            "missing_fields": next_plan.missing_fields,
        }
        await adispatch_custom_event("plan_update", payload, config=config)
        return {"coach_plan": next_plan.model_dump(mode="json")}

    async def _decide_with_retry(
        self,
        *,
        plan: CoachPlan,
        user_text: str,
        evidence_summary: str,
        config: Optional[RunnableConfig],  # noqa: UP045
    ) -> ChecklistUpdateDecision:
        structured = self.classifier_model.with_structured_output(
            ChecklistUpdateDecision
        )
        feedback: str | None = None
        for attempt in range(2):
            system_prompt = _updater_system_prompt(feedback=feedback)
            decision = await structured.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=(
                            f"user_text={user_text}\n"
                            f"plan_snapshot={plan.model_dump(mode='json')}\n"
                            f"tool_evidence={evidence_summary}"
                        )
                    ),
                ],
                config=config,
            )
            try:
                _build_validated_updates(plan=plan, items=decision.updates)
                return decision
            except Exception as exc:
                if attempt == 1:
                    raise RuntimeError(
                        "ChecklistUpdaterNode: invalid update output after one retry"
                    ) from exc
                feedback = str(exc)
        raise RuntimeError("ChecklistUpdaterNode: failed to produce updates")


def _updater_system_prompt(*, feedback: str | None) -> str:
    retry_line = ""
    if feedback:
        retry_line = (
            "Previous output was invalid. Fix all violations exactly.\n"
            f"Validation error: {feedback}\n"
        )
    return (
        "Update coaching checklist status after the latest tool-backed iteration.\n"
        "Output must follow the structured schema exactly.\n"
        f"{retry_line}"
        "Rules:\n"
        "- Allowed status values: pending, in_progress, completed, blocked.\n"
        "- Only emit updates for existing step ids already in plan_snapshot.\n"
        "- Do not invent step ids.\n"
        "- Keep observations concise and evidence-based."
    )


def _build_validated_updates(
    *,
    plan: CoachPlan,
    items: list[ChecklistUpdateItem],
) -> list[CoachPlanStepUpdate]:
    allowed_step_ids = {step.id for step in plan.steps}
    seen: set[str] = set()
    updates: list[CoachPlanStepUpdate] = []
    for item in items:
        update = CoachPlanStepUpdate(
            id=str(item.id or "").strip(),
            status=item.status,
            observations=item.observations,
        )
        if update.id not in allowed_step_ids:
            raise RuntimeError(
                f"ChecklistUpdaterNode: unknown step id in update '{update.id}'"
            )
        if update.id in seen:
            raise RuntimeError(
                f"ChecklistUpdaterNode: duplicate step id in updates '{update.id}'"
            )
        seen.add(update.id)
        updates.append(update)
    return updates


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

        tool_name = (
            str(parsed.get("tool") or "").strip() if isinstance(parsed, dict) else ""
        )
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

