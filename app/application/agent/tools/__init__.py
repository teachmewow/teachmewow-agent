"""
Agent tools module.
"""

from langchain_core.tools import BaseTool

from .get_spec_info import get_spec_info


def get_all_tools() -> list[BaseTool]:
    """
    Get all available tools for the agent.

    Returns:
        List of tool instances
    """
    return [get_spec_info]


__all__ = ["get_spec_info", "get_all_tools"]
