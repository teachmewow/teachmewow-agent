from __future__ import annotations

from typing import Optional

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.application.agent.models import CoachPlan, CoachPlanDraft
from app.application.agent.state_schema import AgentState


class CoachPlanNode:
    """
    Builds a contextual coaching checklist and emits plan_init.

    Planner policy:
    - dynamic step ids are allowed;
    - plan size must remain concise;
    - all core mission tags must be covered.
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

        user_text = _last_human_message_text(state.messages)
        if not user_text:
            raise RuntimeError("CoachPlanNode: missing user message for coach planning")

        plan = await self._build_plan_with_retry(
            user_text=user_text,
            state=state,
            config=config,
        )
        await adispatch_custom_event("plan_init", plan.to_public_payload(), config=config)
        return {"coach_plan": plan.model_dump(mode="json")}

    async def _build_plan_with_retry(
        self,
        *,
        user_text: str,
        state: AgentState,
        config: Optional[RunnableConfig],  # noqa: UP045
    ) -> CoachPlan:
        structured = self.classifier_model.with_structured_output(CoachPlanDraft)
        feedback: str | None = None

        for attempt in range(2):
            system_prompt = _planner_system_prompt(retry_feedback=feedback)
            try:
                draft = await structured.ainvoke(
                    [
                        SystemMessage(content=system_prompt),
                        HumanMessage(
                            content=(
                                f"user_text={user_text}\n"
                                f"char_class={state.char_info.wow_class}\n"
                                f"char_spec={state.char_info.spec}\n"
                                f"char_role={state.char_info.role}\n"
                                f"active_build_id={state.active_build_id or 'none'}\n"
                                f"build_context={_build_context_summary(state)}\n"
                                f"guide_catalog={_ingested_guide_catalog()}"
                            )
                        ),
                    ],
                    config=config,
                )
                return draft.to_plan()
            except Exception as exc:
                if attempt == 1:
                    raise RuntimeError(
                        "CoachPlanNode: planner output invalid after one retry"
                    ) from exc
                feedback = str(exc)[:800]

        raise RuntimeError("CoachPlanNode: failed to produce plan")


def _last_human_message_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if message.type == "human":
            return str(message.content or "").strip()
    return ""


def _build_context_summary(state: AgentState) -> str:
    build_info = state.build_info
    if build_info is None:
        return "none"

    if isinstance(build_info, dict):
        return (
            f"hero_talent={build_info.get('hero_talent')}; "
            f"environment={build_info.get('environment')}; "
            f"scenario={build_info.get('scenario')}; "
            f"decoded_nodes={len(build_info.get('decoded_nodes') or [])}"
        )

    return (
        f"hero_talent={getattr(build_info, 'hero_talent', None)}; "
        f"environment={getattr(build_info, 'environment', None)}; "
        f"scenario={getattr(build_info, 'scenario', None)}; "
        f"decoded_nodes={len(getattr(build_info, 'decoded_nodes', []) or [])}"
    )


def _planner_system_prompt(*, retry_feedback: str | None) -> str:
    retry_line = ""
    if retry_feedback:
        retry_line = (
            "Previous output was invalid. Fix all violations exactly.\n"
            f"Validation error: {retry_feedback}\n"
        )

    return (
        "Create a concise coaching checklist for this user request.\n"
        "Output must follow the structured schema exactly.\n"
        f"{retry_line}"
        "Hard rules:\n"
        "- Return between 2 and 4 steps.\n"
        "- Step IDs must be lowercase snake/kebab style (a-z, 0-9, _, -).\n"
        "- IDs must be unique.\n"
        "- Each step must map to one mission_tag.\n"
        "- Title must be <= 56 chars.\n"
        "- Each step description must be <= 90 chars.\n"
        "- Step descriptions must be terse and action-oriented.\n"
        "- Choose only mission_tags relevant to the LAST user request.\n"
        "- At least one core mission_tag is required.\n"
        "- Do not force all core mission tags when not needed.\n"
        "- For straightforward opener/priority requests, prefer 2-3 steps.\n"
        "- Include assumptions_checked only if critical context is missing.\n"
        "- Include build_vs_baseline only if user asked comparison/why/build delta.\n"
        "- Optional mission tags are allowed when relevant:\n"
        "  sources_confirmed, scenario_specifics.\n"
        "- Keep plan steps at source-backed work level (not tactical answer text).\n"
        "- Only use topics that exist in guide_catalog.\n"
        "- Do not mention abilities not grounded by guide_catalog.\n"
        "- Avoid tactical detail in the plan card; keep details for final answer."
    )


def _ingested_guide_catalog() -> str:
    return (
        "Available ingested sources for warrior/arms:\n"
        "- icy_arms_rotation_cooldowns: opener, single/execute/multi rotation, cooldown usage.\n"
        "- icy_arms_builds_talents: build presets and hero talent differences.\n"
        "- icy_arms_midnight_changes: patch-level changes.\n"
        "- icy_arms_stat_priority: stats and optimization baseline.\n"
        "- icy_arms_mplus_tips: mythic+ specific guidance.\n"
        "Not ingested for this MVP: gear bis, gems/enchants/consumables, spell summary."
    )
