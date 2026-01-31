"""
Routers for the knowledge explorer flow.
"""

from typing import Literal

from app.application.agent.state_schema import AgentState


class ExplorerToolRouterNode:
    def __call__(self, state: AgentState) -> Literal["tools", "update"]:
        ai_message = state.messages[-1] if state.messages else None
        if ai_message and getattr(ai_message, "tool_calls", []):
            return "tools"
        return "update"


class ChecklistRouterNode:
    def __call__(self, state: AgentState) -> Literal["continue", "finalize"]:
        for item in state.checklist_items:
            if item.status != "complete":
                return "continue"
        return "finalize"
