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


def test_router_routes_to_knowledge_explorer() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "run_knowledge_explorer", "args": {}}],
    )
    state = _base_state()
    state.messages = [message]
    router = RouterNode()
    assert router(state) == "knowledge_explorer"


def test_router_routes_to_tools_for_other_calls() -> None:
    message = AIMessage(
        content="",
        tool_calls=[{"name": "search_helix", "args": {}}],
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
