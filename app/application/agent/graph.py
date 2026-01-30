"""
LangGraph agent definition.
Defines the graph structure with nodes and edges.
"""

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from app.infrastructure.llm import LLMClient

from .state_schema import AgentState
from .nodes.llm_node import LLMNode
from .nodes.tool_node import ToolNode
from .nodes.router_node import RouterNode


def create_agent_graph(llm_client: LLMClient, tools: list[BaseTool]) -> StateGraph:
    """
    Create the LangGraph agent graph.

    Args:
        llm_client: The LLM client to use
        tools: List of tools available to the agent

    Returns:
        Configured StateGraph (not compiled)
    """
    # Create the graph
    graph = StateGraph(AgentState)

    # Bind tools to the model so it can emit tool calls
    model = llm_client.model.bind_tools(tools) if tools else llm_client.model
    # Add nodes
    graph.add_node("agent", LLMNode(model))
    graph.add_node("tools", ToolNode(tools))

    # Set entry point: START -> agent
    graph.set_entry_point("agent")

    # Add edges
    graph.add_conditional_edges(
        "agent",
        RouterNode(),
        {
            "tools": "tools",
            END: END,
        },
    )
    graph.add_edge("tools", "agent")

    return graph
