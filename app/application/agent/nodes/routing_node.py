from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from app.application.agent.prompts.route_prompt import ROUTING_SYSTEM_PROMPT
from app.application.agent.state_schema import AgentState, RoutingDecision


class RoutingNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        routing_model = self.model.with_structured_output(RoutingDecision)
        messages = [SystemMessage(content=ROUTING_SYSTEM_PROMPT), *state.messages]
        decision = await routing_model.ainvoke(messages, config)
        if isinstance(decision, dict):
            decision = RoutingDecision(**decision)
        return {
            "route_decision": decision,
            "checklist_items": list(decision.checklist),
        }
