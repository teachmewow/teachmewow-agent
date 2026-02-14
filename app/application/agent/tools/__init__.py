"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .build_lookup import build_lookup
from .build_rag_lookup import build_rag_lookup


def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Returns:
        List of tool instances
    """
    return [
        build_lookup,
        build_rag_lookup,
    ]


__all__ = [
    "build_lookup",
    "build_rag_lookup",
    "get_all_tools",
]
