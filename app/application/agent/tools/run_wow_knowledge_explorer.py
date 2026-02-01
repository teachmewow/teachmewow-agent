"""
Tool: run_wow_knowledge_explorer

Placeholder tool to route into the knowledge explorer flow.
"""

from langchain_core.tools import tool


@tool
async def run_wow_knowledge_explorer() -> str:
    """
    Placeholder tool that signals entering deep research mode.
    """
    return "Entrando no modo de deep research..."
