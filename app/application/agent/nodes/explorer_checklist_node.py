"""
Checklist builder for the knowledge explorer flow.
"""

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from app.application.agent.prompts.route_prompt import ROUTING_SYSTEM_PROMPT
from app.application.agent.nodes.explorer_message_utils import (
    build_explorer_start_marker,
    has_explorer_start_marker,
)
from app.application.agent.state_schema import AgentState, ChecklistItem, RoutingDecision


class ExplorerChecklistNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        if state.checklist_items:
            return {}

        tool_ack = self._acknowledge_run_knowledge_explorer(state)

        extracted = self._extract_checklist_from_tool_call(state)
        if extracted:
            update = {"checklist_items": extracted}
            if not has_explorer_start_marker(state.messages):
                update["messages"] = update.get("messages", [])
                update["messages"].append(build_explorer_start_marker())
            if tool_ack:
                update["messages"] = tool_ack + update.get("messages", [])
            return update

        routing_model = self.model.with_structured_output(RoutingDecision)
        messages = [SystemMessage(content=ROUTING_SYSTEM_PROMPT), *state.messages]
        decision = await routing_model.ainvoke(messages, config)
        if isinstance(decision, dict):
            decision = RoutingDecision(**decision)
        update: dict = {
            "route_decision": decision,
            "checklist_items": list(decision.checklist),
        }
        if not has_explorer_start_marker(state.messages):
            update["messages"] = [build_explorer_start_marker()]
        return update

    def _acknowledge_run_knowledge_explorer(
        self, state: AgentState
    ) -> list[ToolMessage]:
        last_message = state.messages[-1] if state.messages else None
        tool_calls = list(getattr(last_message, "tool_calls", []) or [])
        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name != "run_knowledge_explorer":
                continue
            call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
            if not call_id:
                return []
            for message in state.messages:
                if isinstance(message, ToolMessage) and message.tool_call_id == call_id:
                    return []
            return [
                ToolMessage(
                    content="knowledge_explorer_requested",
                    name="run_knowledge_explorer",
                    tool_call_id=call_id,
                )
            ]
        return []

    def _extract_checklist_from_tool_call(
        self, state: AgentState
    ) -> list[ChecklistItem]:
        last_message = state.messages[-1] if state.messages else None
        tool_calls = list(getattr(last_message, "tool_calls", []) or [])
        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name != "run_knowledge_explorer":
                continue
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            checklist_raw = args.get("checklist", []) if isinstance(args, dict) else []
            checklist_items = []
            for item in checklist_raw:
                if isinstance(item, ChecklistItem):
                    checklist_items.append(item)
                elif isinstance(item, dict):
                    checklist_items.append(ChecklistItem(**item))
            if checklist_items:
                return checklist_items
        return []
