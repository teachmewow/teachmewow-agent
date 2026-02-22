from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition

from .constants import GraphNodeName, GraphRouteName
from .node_factory import GraphNodes
from .route_policy import (
    route_after_mission_gate,
    route_after_tools,
    route_from_router,
)


def wire_graph(graph: StateGraph, nodes: GraphNodes) -> None:
    _add_nodes(graph, nodes)
    _add_edges(graph)


def _add_nodes(graph: StateGraph, nodes: GraphNodes) -> None:
    graph.add_node(GraphNodeName.ROUTER.value, nodes.router)
    graph.add_node(GraphNodeName.COACH_PLAN.value, nodes.coach_plan)
    graph.add_node(GraphNodeName.AGENT.value, nodes.agent)
    graph.add_node(GraphNodeName.COACH_AGENT.value, nodes.coach_agent)
    graph.add_node(GraphNodeName.TOOLS.value, nodes.tools)
    graph.add_node(GraphNodeName.CHECKLIST_UPDATER.value, nodes.checklist_updater)
    graph.add_node(GraphNodeName.MISSION_GATE.value, nodes.mission_gate)


def _add_edges(graph: StateGraph) -> None:
    graph.add_edge(START, GraphNodeName.ROUTER.value)

    graph.add_conditional_edges(
        GraphNodeName.ROUTER.value,
        route_from_router,
        {
            GraphRouteName.COACH.value: GraphNodeName.COACH_PLAN.value,
            GraphRouteName.DEFAULT.value: GraphNodeName.AGENT.value,
        },
    )
    graph.add_edge(GraphNodeName.COACH_PLAN.value, GraphNodeName.COACH_AGENT.value)

    graph.add_conditional_edges(
        GraphNodeName.AGENT.value,
        tools_condition,
        {
            "tools": GraphNodeName.TOOLS.value,
            END: END,
        },
    )
    graph.add_conditional_edges(
        GraphNodeName.COACH_AGENT.value,
        tools_condition,
        {
            "tools": GraphNodeName.TOOLS.value,
            END: GraphNodeName.MISSION_GATE.value,
        },
    )
    graph.add_conditional_edges(
        GraphNodeName.TOOLS.value,
        route_after_tools,
        {
            GraphRouteName.COACH.value: GraphNodeName.CHECKLIST_UPDATER.value,
            GraphRouteName.DEFAULT.value: GraphNodeName.AGENT.value,
        },
    )
    graph.add_edge(
        GraphNodeName.CHECKLIST_UPDATER.value, GraphNodeName.COACH_AGENT.value
    )
    graph.add_conditional_edges(
        GraphNodeName.MISSION_GATE.value,
        route_after_mission_gate,
        {
            GraphRouteName.CLARIFY.value: GraphNodeName.COACH_AGENT.value,
            END: END,
        },
    )
