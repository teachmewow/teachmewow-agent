"""
Checklist builder for the knowledge explorer flow.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.application.agent.prompts.explorer_checklist_prompt import (
    EXPLORER_CHECKLIST_PROMPT,
)
from app.application.agent.nodes.explorer_message_utils import (
    build_explorer_start_marker,
    has_explorer_start_marker,
)
from app.application.agent.state_schema import AgentState, ChecklistItem


class ExplorerChecklistOutput(BaseModel):
    checklist: list[ChecklistItem] = Field(default_factory=list)


class ExplorerChecklistNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        if state.checklist_items:
            if has_explorer_start_marker(state.messages):
                return {}
            return {"messages": [build_explorer_start_marker()]}

        checklist_model = self.model.with_structured_output(ExplorerChecklistOutput)
        messages = [SystemMessage(content=EXPLORER_CHECKLIST_PROMPT), *state.messages]
        output = await checklist_model.ainvoke(messages, config)
        if isinstance(output, dict):
            output = ExplorerChecklistOutput(**output)
        update: dict = {
            "checklist_items": list(output.checklist),
        }
        if not has_explorer_start_marker(state.messages):
            update["messages"] = [build_explorer_start_marker()]
        return update

