from __future__ import annotations

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.runnables import RunnableConfig

from app.application.agent.models import build_default_coach_plan
from app.application.agent.state_schema import AgentState


class CoachPlanNode:
    """
    Initializes a per-response coaching checklist and streams plan_init.
    """

    async def __call__(
        self,
        state: AgentState,
        config: RunnableConfig | None = None,
    ) -> AgentState:
        if state.route != "coach":
            return {}

        plan = build_default_coach_plan()
        payload = plan.model_dump(mode="json")
        await adispatch_custom_event("plan_init", payload, config=config)
        return {"coach_plan": payload}
