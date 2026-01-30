from app.application.agent.state_schema import AgentState
from langgraph.graph import END
from typing import Literal


class RouterNode:
    def __call__(self, state: AgentState) -> Literal["tools", END]:
        if isinstance(state, list):
            ai_message = state[-1]
        elif messages := state.get("messages", []):
            ai_message = messages[-1]
        else:
            raise ValueError(f"No messages found in state {state}")
        
        if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
            return "tools"
        return END