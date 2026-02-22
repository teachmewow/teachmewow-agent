import sys
import types

sys.modules.setdefault("helix", types.ModuleType("helix"))

from app.application.agent.graph_builder import (
    _route_after_mission_gate,
    _route_after_tools,
    _route_from_router,
)


def test_route_from_router_defaults_when_not_coach() -> None:
    assert _route_from_router({"route": "default"}) == "default"
    assert _route_from_router({"route": "other"}) == "default"


def test_route_from_router_selects_coach() -> None:
    assert _route_from_router({"route": "coach"}) == "coach"
    assert _route_after_tools({"route": "coach"}) == "coach"


def test_route_after_mission_gate_only_retries_when_prompted() -> None:
    assert _route_after_mission_gate({"mission_gate": {}}) == "__end__"
    assert (
        _route_after_mission_gate(
            {"mission_gate": {"_clarification_prompted": True}}
        )
        == "clarify"
    )
