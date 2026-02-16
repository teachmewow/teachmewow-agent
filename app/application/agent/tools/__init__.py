"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .build_lookup import build_lookup
# from .build_reasoning_context import build_reasoning_context
# from .build_rag_lookup import build_rag_lookup
from .list_builds import list_builds


def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Returns:
        List of tool instances
    """
    return [
        list_builds,
        build_lookup,
        # build_rag_lookup,
        # build_reasoning_context,
    ]


__all__ = [
    "list_builds",
    "build_lookup",
    # "build_rag_lookup",
    # "build_reasoning_context",
    "get_all_tools",
]
