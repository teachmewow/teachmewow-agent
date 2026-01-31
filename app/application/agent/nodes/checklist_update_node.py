"""
Checklist update node for the knowledge explorer flow.
"""

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.application.agent.prompts.checklist_update_prompt import (
    CHECKLIST_UPDATE_SYSTEM_PROMPT,
)
from app.application.agent.state_schema import AgentState, ChecklistItem


class ChecklistUpdate(BaseModel):
    items: list[ChecklistItem] = Field(default_factory=list)
    context_update: str = ""


class ChecklistUpdateNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        update_model = self.model.with_structured_output(ChecklistUpdate)
        messages = self._mount_messages(state)
        update = await update_model.ainvoke(messages, config)

        previous_by_id = {item.id: item for item in state.checklist_items}
        updated_items = update.items or state.checklist_items
        self._emit_checklist_updates(previous_by_id, updated_items)

        exploration_context = state.exploration_context
        if update.context_update:
            exploration_context = self._append_context(
                exploration_context, update.context_update
            )

        return {
            "checklist_items": updated_items,
            "exploration_context": exploration_context,
        }

    def _mount_messages(self, state: AgentState) -> list[BaseMessage]:
        tool_messages = self._get_recent_tool_messages(state)
        payload = {
            "checklist_items": [item.model_dump() for item in state.checklist_items],
            "tool_results": [
                {"name": msg.name, "content": msg.content} for msg in tool_messages
            ],
            "exploration_context": state.exploration_context,
        }
        return [
            SystemMessage(content=CHECKLIST_UPDATE_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(payload)),
        ]

    def _get_recent_tool_messages(self, state: AgentState) -> list[ToolMessage]:
        tool_messages = [msg for msg in state.messages if isinstance(msg, ToolMessage)]
        return tool_messages[-4:]

    def _emit_checklist_updates(
        self, previous: dict[str, ChecklistItem], updated: list[ChecklistItem]
    ) -> None:
        stream_writer = get_stream_writer()
        for item in updated:
            previous_item = previous.get(item.id)
            if not previous_item:
                stream_writer(
                    {
                        "kind": "checklist_update",
                        "data": {"item": item.model_dump(), "previous_status": None},
                    }
                )
                continue

            if (
                previous_item.status != item.status
                or previous_item.evidence != item.evidence
            ):
                stream_writer(
                    {
                        "kind": "checklist_update",
                        "data": {
                            "item": item.model_dump(),
                            "previous_status": previous_item.status,
                        },
                    }
                )

    def _append_context(self, current: str, update: str) -> str:
        if not current:
            return update
        return f"{current}\n{update}"
