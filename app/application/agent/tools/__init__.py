"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .build_lookup import build_lookup
from .run_wow_knowledge_explorer import run_wow_knowledge_explorer


def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Returns:
        List of tool instances
    """
    return [
        build_lookup,
        run_wow_knowledge_explorer,
    ]


__all__ = [
    "build_lookup",
    "run_wow_knowledge_explorer",
    "get_all_tools",
]
