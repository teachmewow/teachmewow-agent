from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langgraph.graph import END

from .constants import GraphRouteName


def route_from_router(state: Any) -> str:
    return _read_route(state).value


def route_after_tools(state: Any) -> str:
    return _read_route(state).value


def route_after_mission_gate(state: Any) -> str:
    mission_gate = _read_required_mapping(state, "mission_gate")
    should_clarify = mission_gate.get("_clarification_prompted")
    if should_clarify is None:
        return END
    if not isinstance(should_clarify, bool):
        raise TypeError("mission_gate._clarification_prompted must be a boolean")
    return GraphRouteName.CLARIFY.value if should_clarify else END


def _read_route(state: Any) -> GraphRouteName:
    raw_route = _read_required_value(state, "route")
    if not isinstance(raw_route, str):
        raise TypeError("route must be a string")
    try:
        return GraphRouteName(raw_route)
    except ValueError as exc:
        raise ValueError(
            f"invalid route value '{raw_route}', expected one of: "
            f"{GraphRouteName.DEFAULT.value}, {GraphRouteName.COACH.value}"
        ) from exc


def _read_required_mapping(state: Any, key: str) -> Mapping[str, Any]:
    value = _read_required_value(state, key)
    if not isinstance(value, Mapping):
        raise TypeError(f"{key} must be a mapping")
    return value


def _read_required_value(state: Any, key: str) -> Any:
    if isinstance(state, Mapping):
        if key not in state:
            raise KeyError(f"missing required state key: {key}")
        return state[key]
    if hasattr(state, key):
        return getattr(state, key)
    raise TypeError(f"state does not expose required key '{key}'")
