"""
Tool: run_knowledge_explorer

Use this tool to trigger a deep exploration subgraph
when the request requires multi-step research.
"""

from pydantic import BaseModel, Field
from langchain_core.tools import tool

from app.application.agent.state_schema import ChecklistItem


class RunKnowledgeExplorerInput(BaseModel):
    question: str = Field(..., description="Original user question.")
    checklist: list[ChecklistItem] = Field(
        default_factory=list,
        description=(
            "Checklist items to explore (3-6 items prefered). "
            "Each item must include id, title, status, evidence."
        ),
    )


@tool(args_schema=RunKnowledgeExplorerInput)
def run_knowledge_explorer(question: str, checklist: list[ChecklistItem]) -> str:
    """
    Trigger a deep exploration subgraph for WoW knowledge.

    Use when the answer requires external knowledge gathering
    and you need to complete a checklist before responding.
    """
    return "knowledge_explorer_requested"
