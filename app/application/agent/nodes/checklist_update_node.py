"""
Checklist update node for the knowledge explorer flow.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer
from pydantic import BaseModel, Field

from app.application.agent.prompts.checklist_update_prompt import (
    CHECKLIST_UPDATE_SYSTEM_PROMPT,
)
from app.application.agent.nodes.explorer_message_utils import get_subgraph_messages
from app.application.agent.state_schema import AgentState, ChecklistItem


class ChecklistUpdate(BaseModel):
    items: list[ChecklistItem] = Field(default_factory=list)


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
        if self._should_mark_no_results(state):
            updated_items = self._mark_no_results(updated_items)
        self._emit_checklist_updates(previous_by_id, updated_items)

        return {
            "checklist_items": updated_items,
        }

    def _mount_messages(self, state: AgentState) -> list[BaseMessage]:
        subgraph_messages = get_subgraph_messages(state.messages)
        payload = {
            "checklist_items": [item.model_dump() for item in state.checklist_items],
            "messages": self._serialize_messages(subgraph_messages),
        }
        return [
            SystemMessage(content=CHECKLIST_UPDATE_SYSTEM_PROMPT),
            HumanMessage(content=self._format_payload(payload)),
        ]

    def _serialize_messages(self, messages: list[BaseMessage]) -> list[dict]:
        serialized = []
        for message in messages:
            entry = {
                "type": message.type,
                "name": getattr(message, "name", None),
                "content": message.content,
            }
            if isinstance(message, ToolMessage):
                entry["tool_call_id"] = message.tool_call_id
            serialized.append(entry)
        return serialized

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

    def _format_payload(self, payload: dict) -> str:
        lines = ["Checklist update payload:"]
        lines.append("Checklist items:")
        for item in payload.get("checklist_items", []):
            lines.append(f"- {item.get('id')}: {item.get('title')} ({item.get('status')})")
        lines.append("Messages:")
        for message in payload.get("messages", []):
            lines.append(
                f"- {message.get('type')}:{message.get('name') or ''} {message.get('content')}"
            )
        return "\n".join(lines)

    def _should_mark_no_results(self, state: AgentState) -> bool:
        subgraph_messages = get_subgraph_messages(state.messages)
        tool_messages = [msg for msg in subgraph_messages if isinstance(msg, ToolMessage)]
        if not tool_messages:
            return False
        return all(
            isinstance(msg.content, str) and "No results found" in msg.content
            for msg in tool_messages
        )

    def _mark_no_results(self, items: list[ChecklistItem]) -> list[ChecklistItem]:
        updated = []
        for item in items:
            if item.status in ("complete", "failed"):
                updated.append(item)
                continue
            evidence = list(item.evidence)
            evidence.append("No results found for the requested filters.")
            updated.append(
                ChecklistItem(
                    id=item.id,
                    title=item.title,
                    status="complete",
                    evidence=evidence,
                )
            )
        return updated
