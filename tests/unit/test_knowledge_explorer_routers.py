from langchain_core.messages import AIMessage

from app.application.agent.state_schema import AgentState, ChecklistItem
from app.application.agent.nodes.explorer_routers import (
    ChecklistRouterNode,
    ExplorerToolRouterNode,
)


def _base_state() -> AgentState:
    return AgentState(
        messages=[],
        thread_id="thread-1",
        user_id="user-1",
        wow_class="mage",
        wow_spec="frost",
        wow_role="dps",
    )


def test_checklist_router_continue_when_pending() -> None:
    state = _base_state()
    state.checklist_items = [ChecklistItem(id="a", title="Item A", status="pending")]
    router = ChecklistRouterNode()
    assert router(state) == "continue"


def test_checklist_router_finalize_when_complete() -> None:
    state = _base_state()
    state.checklist_items = [ChecklistItem(id="a", title="Item A", status="complete")]
    router = ChecklistRouterNode()
    assert router(state) == "finalize"


def test_explorer_tool_router_detects_tool_calls() -> None:
    message = AIMessage(content="", tool_calls=[{"name": "get_class_info", "args": {}}])
    state = _base_state()
    state.messages = [message]
    router = ExplorerToolRouterNode()
    assert router(state) == "tools"


def test_explorer_tool_router_no_tool_calls() -> None:
    message = AIMessage(content="ok")
    state = _base_state()
    state.messages = [message]
    router = ExplorerToolRouterNode()
    assert router(state) == "update"
