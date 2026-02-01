"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .helix_simple_rag import helix_simple_rag
from .helix_graph_traversal import helix_graph_traversal
from .helix_hybrid_rag_edges import helix_hybrid_rag_edges
from .run_knowledge_explorer import run_knowledge_explorer


def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Returns:
        List of tool instances
    """
    return [
        helix_simple_rag,
        helix_graph_traversal,
        helix_hybrid_rag_edges,
        run_knowledge_explorer,
    ]


__all__ = [
    "helix_simple_rag",
    "helix_graph_traversal",
    "helix_hybrid_rag_edges",
    "run_knowledge_explorer",
    "get_all_tools",
]
