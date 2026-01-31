from typing import Literal

from langgraph.graph import END

from app.application.agent.state_schema import AgentState


class RouterNode:
    def __call__(self, state: AgentState) -> Literal["knowledge_explorer", "tools", END]:
        if isinstance(state, list):
            ai_message = state[-1]
        elif state.messages:
            ai_message = state.messages[-1]
        else:
            raise ValueError(f"No messages found in state {state}")
        
        tool_calls = list(getattr(ai_message, "tool_calls", []) or [])
        if any(self._is_knowledge_explorer_call(call) for call in tool_calls):
            return "knowledge_explorer"
        if tool_calls:
            return "tools"
        return END

    def _is_knowledge_explorer_call(self, tool_call: object) -> bool:
        if isinstance(tool_call, dict):
            return tool_call.get("name") == "run_knowledge_explorer"
        return getattr(tool_call, "name", None) == "run_knowledge_explorer"