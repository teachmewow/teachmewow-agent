from enum import StrEnum


class GraphNodeName(StrEnum):
    ROUTER = "router"
    COACH_PLAN = "coach_plan"
    AGENT = "agent"
    COACH_AGENT = "coach_agent"
    TOOLS = "tools"
    CHECKLIST_UPDATER = "checklist_updater"
    MISSION_GATE = "mission_gate"


class GraphRouteName(StrEnum):
    DEFAULT = "default"
    COACH = "coach"
    CLARIFY = "clarify"
