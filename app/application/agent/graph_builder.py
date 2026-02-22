"""
Graph builder factory for creating the compiled LangGraph agent.
"""

from typing import Any

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import tools_condition

from app.infrastructure.llm import LLMClient

from .nodes.mission_gate_node import MissionGateNode
from .nodes.routing_node import RoutingNode
from .state_schema import AgentState
from .nodes.llm_node import LLMNode
from .nodes.tool_node import ToolNode
from .prompts.coach_prompt import COACH_SYSTEM_PROMPT


class GraphBuilder:
    """
    Factory for building compiled LangGraph agents.

    The builder receives dependencies (LLM client, tools) and produces
    a compiled graph that is stateless and can be shared between requests.
    """

    def __init__(self, llm_client: LLMClient, tools: list[BaseTool]):
        """
        Initialize the graph builder.

        Args:
            llm_client: LLM client for model calls
            tools: List of tools available to the agent
        """
        self.llm_client = llm_client
        self.tools = tools

    def build(self) -> CompiledStateGraph:
        """
        Build and compile the agent graph.

        Returns:
            Compiled StateGraph ready for execution.
            This graph is stateless and can be reused across requests.
        """
        graph = self._build_graph()

        # Compile the graph
        compiled = graph.compile()

        return compiled

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)

        main_model = (
            self.llm_client.main_model.bind_tools(self.tools)
            if self.tools
            else self.llm_client.main_model
        )
        coach_model = (
            self.llm_client.explorer_model.bind_tools(self.tools)
            if self.tools
            else self.llm_client.explorer_model
        )

        graph.add_node("router", RoutingNode(self.llm_client.classifier_model))
        graph.add_node("agent", LLMNode(main_model))
        graph.add_node("coach_agent", LLMNode(coach_model, system_prompt=COACH_SYSTEM_PROMPT))
        graph.add_node("tools", ToolNode(self.tools))
        graph.add_node("mission_gate", MissionGateNode(self.llm_client.classifier_model))

        graph.add_edge(START, "router")
        graph.add_conditional_edges(
            "router",
            _route_from_router,
            {
                "coach": "coach_agent",
                "default": "agent",
            },
        )

        graph.add_conditional_edges(
            "agent",
            tools_condition,
            {
                "tools": "tools",
                END: END,
            },
        )
        graph.add_conditional_edges(
            "coach_agent",
            tools_condition,
            {
                "tools": "tools",
                END: "mission_gate",
            },
        )
        graph.add_conditional_edges(
            "tools",
            _route_after_tools,
            {
                "coach": "coach_agent",
                "default": "agent",
            },
        )
        graph.add_conditional_edges(
            "mission_gate",
            _route_after_mission_gate,
            {
                "clarify": "coach_agent",
                END: END,
            },
        )

        return graph


def create_graph_builder(
    llm_client: LLMClient, tools: list[BaseTool]
) -> GraphBuilder:
    """
    Create a new GraphBuilder instance.

    Args:
        llm_client: LLM client for model calls
        tools: List of tools available to the agent

    Returns:
        Configured GraphBuilder
    """
    return GraphBuilder(llm_client=llm_client, tools=tools)


def _read_state_value(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def _route_from_router(state: Any) -> str:
    route = str(_read_state_value(state, "route", "default") or "default")
    return "coach" if route == "coach" else "default"


def _route_after_tools(state: Any) -> str:
    route = str(_read_state_value(state, "route", "default") or "default")
    return "coach" if route == "coach" else "default"


def _route_after_mission_gate(state: Any) -> str:
    mission_gate = _read_state_value(state, "mission_gate", {})
    if not isinstance(mission_gate, dict):
        return END
    should_clarify = bool(mission_gate.get("_clarification_prompted"))
    return "clarify" if should_clarify else END
