"""
Graph builder factory for creating the compiled LangGraph agent.
"""

from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.infrastructure.llm import LLMClient

from .state_schema import AgentState
from .nodes.llm_node import LLMNode
from .nodes.tool_node import ToolNode
from .nodes.router_node import RouterNode
from .nodes.explorer_checklist_node import ExplorerChecklistNode
from .nodes.explorer_prepare_node import ExplorerPrepareNode
from .nodes.explorer_agent_node import ExplorerAgentNode
from .nodes.checklist_update_node import ChecklistUpdateNode
from .nodes.explorer_finalize_node import ExplorerFinalizeNode
from .nodes.explorer_routers import ChecklistRouterNode, ExplorerToolRouterNode


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
            self.llm_client.model.bind_tools(self.tools)
            if self.tools
            else self.llm_client.model
        )
        graph.add_node("agent", LLMNode(main_model))
        graph.add_node("tools", ToolNode(self.tools))
        graph.add_node("knowledge_explorer", self._build_knowledge_explorer_subgraph())

        graph.set_entry_point("agent")

        graph.add_conditional_edges(
            "agent",
            RouterNode(),
            {
                "knowledge_explorer": "knowledge_explorer",
                "tools": "tools",
                END: END,
            },
        )
        graph.add_edge("tools", "agent")
        graph.add_edge("knowledge_explorer", "agent")

        return graph

    def _build_knowledge_explorer_subgraph(self) -> CompiledStateGraph:
        graph = StateGraph(AgentState)

        explorer_model = self.llm_client.model.bind_tools(self.tools)
        update_model = self.llm_client.model

        graph.add_node("explorer_checklist", ExplorerChecklistNode(update_model))
        graph.add_node("explorer_prepare", ExplorerPrepareNode())
        graph.add_node("explorer_agent", ExplorerAgentNode(explorer_model))
        graph.add_node("explorer_tools", ToolNode(self.tools))
        graph.add_node("explorer_update", ChecklistUpdateNode(update_model))
        graph.add_node("explorer_finalize", ExplorerFinalizeNode(update_model))

        graph.set_entry_point("explorer_checklist")
        graph.add_edge("explorer_checklist", "explorer_prepare")
        graph.add_edge("explorer_prepare", "explorer_agent")

        graph.add_conditional_edges(
            "explorer_agent",
            ExplorerToolRouterNode(),
            {
                "tools": "explorer_tools",
                "update": "explorer_update",
            },
        )
        graph.add_edge("explorer_tools", "explorer_update")

        graph.add_conditional_edges(
            "explorer_update",
            ChecklistRouterNode(),
            {
                "continue": "explorer_agent",
                "finalize": "explorer_finalize",
            },
        )
        graph.add_edge("explorer_finalize", END)

        return graph.compile()


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
