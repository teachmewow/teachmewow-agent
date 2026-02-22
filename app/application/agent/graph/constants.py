from enum import StrEnum


class GraphNodeName(StrEnum):
    ROUTER = "router"
    AGENT = "agent"
    COACH_AGENT = "coach_agent"
    TOOLS = "tools"
    MISSION_GATE = "mission_gate"


class GraphRouteName(StrEnum):
    DEFAULT = "default"
    COACH = "coach"
    CLARIFY = "clarify"
