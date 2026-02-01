from langchain_core.messages import AIMessage
from langgraph.graph import END

from app.application.agent.nodes.router_node import RouterNode
from app.application.agent.state_schema import AgentState


def _base_state() -> AgentState:
    return AgentState(
        messages=[],
        thread_id="thread-1",
        user_id="user-1",
        wow_class="mage",
        wow_spec="frost",
        wow_role="dps",
    )


def test_router_routes_to_explorer_entry_for_placeholder() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "run_wow_knowledge_explorer", "args": {}}],
    )
    state = _base_state()
    state.messages = [message]
    router = RouterNode()
    assert router(state) == "explorer_entry"


def test_router_routes_to_tools_for_other_calls() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "build_lookup", "args": {}}],
    )
    state = _base_state()
    state.messages = [message]
    router = RouterNode()
    assert router(state) == "tools"


def test_router_routes_to_end_with_no_calls() -> None:
    message = AIMessage(content="ok")
    state = _base_state()
    state.messages = [message]
    router = RouterNode()
    assert router(state) == END
