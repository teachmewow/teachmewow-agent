"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .helix_search import search_helix
from .helix_retrieve import retrieve_helix_context
from .run_knowledge_explorer import run_knowledge_explorer


def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Returns:
        List of tool instances
    """
    return [search_helix, retrieve_helix_context, run_knowledge_explorer]


__all__ = ["search_helix", "retrieve_helix_context", "run_knowledge_explorer", "get_all_tools"]
