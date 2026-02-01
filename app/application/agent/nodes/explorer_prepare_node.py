"""
Prepare node for the knowledge explorer flow.
"""

import re

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from app.application.agent.state_schema import AgentState, ChecklistItem


class ExplorerPrepareNode:
    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        checklist_items = self._normalize_checklist(state.checklist_items)
        current_checklist_id = state.current_checklist_id
        if not current_checklist_id:
            current_checklist_id = self._select_first_pending_id(checklist_items)
        stream_writer = get_stream_writer()
        if checklist_items:
            stream_writer(
                {
                    "kind": "checklist_init",
                    "data": {"items": [item.model_dump() for item in checklist_items]},
                }
            )
        return {
            "checklist_items": checklist_items,
            "current_checklist_id": current_checklist_id,
            "subgraph_status": "running",
        }

    def _normalize_checklist(self, items: list[ChecklistItem]) -> list[ChecklistItem]:
        normalized = []
        for item in items:
            checklist_id = item.id or self._slugify(item.title)
            status = item.status or "pending"
            evidence = list(item.evidence or [])
            normalized.append(
                ChecklistItem(
                    id=checklist_id,
                    title=item.title,
                    status=status,
                    evidence=evidence,
                )
            )
        return normalized

    def _select_first_pending_id(self, items: list[ChecklistItem]) -> str | None:
        for item in items:
            if item.status != "complete":
                return item.id
        return None

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
        return slug or "item"
