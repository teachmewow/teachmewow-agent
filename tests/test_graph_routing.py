import sys
import types

import pytest

sys.modules.setdefault("helix", types.ModuleType("helix"))

from app.application.agent.graph.route_policy import (
    route_after_mission_gate,
    route_after_tools,
    route_from_router,
)


def test_route_from_router_defaults_when_not_coach() -> None:
    assert route_from_router({"route": "default"}) == "default"


def test_route_from_router_rejects_unknown_route() -> None:
    with pytest.raises(ValueError):
        route_from_router({"route": "other"})


def test_route_from_router_selects_coach() -> None:
    assert route_from_router({"route": "coach"}) == "coach"
    assert route_after_tools({"route": "coach"}) == "coach"


def test_route_after_mission_gate_only_retries_when_prompted() -> None:
    assert route_after_mission_gate({"mission_gate": {}}) == "__end__"
    assert (
        route_after_mission_gate(
            {"mission_gate": {"_clarification_prompted": True}}
        )
        == "clarify"
    )


def test_route_after_mission_gate_rejects_invalid_prompt_flag() -> None:
    with pytest.raises(TypeError):
        route_after_mission_gate({"mission_gate": {"_clarification_prompted": "yes"}})
