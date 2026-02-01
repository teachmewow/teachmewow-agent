from typing import Literal

from langgraph.graph import END

from app.application.agent.state_schema import AgentState


class RouterNode:
    def __call__(
        self, state: AgentState
    ) -> Literal["explorer_entry", "tools", END]:
        if isinstance(state, list):
            ai_message = state[-1]
        elif state.messages:
            ai_message = state.messages[-1]
        else:
            raise ValueError(f"No messages found in state {state}")

        tool_calls = list(getattr(ai_message, "tool_calls", []) or [])
        if not tool_calls:
            return END

        if any(
            (call.get("name") if isinstance(call, dict) else call.name)
            == "run_wow_knowledge_explorer"
            for call in tool_calls
        ):
            return "explorer_entry"

        return "tools"
