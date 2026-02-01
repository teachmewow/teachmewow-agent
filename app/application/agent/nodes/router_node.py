from typing import Literal

from langgraph.graph import END

from app.application.agent.state_schema import AgentState


class RouterNode:
    def __call__(self, state: AgentState) -> Literal["knowledge_explorer", "tools", END]:
        if state.subgraph_status == "idle" and state.route_decision:
            if state.route_decision.subgraph == "knowledge_explorer":
                return "knowledge_explorer"

        if isinstance(state, list):
            ai_message = state[-1]
        elif state.messages:
            ai_message = state.messages[-1]
        else:
            raise ValueError(f"No messages found in state {state}")

        tool_calls = list(getattr(ai_message, "tool_calls", []) or [])
        if tool_calls:
            return "tools"
        return END
