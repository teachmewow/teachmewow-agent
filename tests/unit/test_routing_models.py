from app.application.agent.state_schema import AgentState, ChecklistItem, RoutingDecision


def test_routing_decision_defaults() -> None:
    decision = RoutingDecision()
    assert decision.subgraph == "none"
    assert decision.checklist == []


def test_agent_state_defaults() -> None:
    state = AgentState(
        messages=[],
        thread_id="thread-1",
        user_id="user-1",
        wow_class="mage",
        wow_spec="frost",
        wow_role="dps",
    )
    assert state.route_decision is None
    assert state.checklist_items == []
    assert state.subgraph_status == "idle"


def test_checklist_item_defaults() -> None:
    item = ChecklistItem(id="test", title="Test item")
    assert item.status == "pending"
    assert item.evidence == []
