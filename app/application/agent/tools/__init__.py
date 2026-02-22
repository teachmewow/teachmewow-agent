"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .build_lookup import build_lookup
from .guide_context_lookup import guide_context_lookup
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
        guide_context_lookup,
    ]


__all__ = [
    "list_builds",
    "build_lookup",
    "guide_context_lookup",
    "get_all_tools",
]
