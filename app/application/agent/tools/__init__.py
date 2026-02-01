"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .get_class_info import get_class_info
from .get_build import get_build


def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Returns:
        List of tool instances
    """
    return [
        get_class_info,
        get_build,
    ]


__all__ = [
    "get_class_info",
    "get_build",
    "get_all_tools",
]
