"""
Finalize node for the knowledge explorer flow.
"""

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from app.application.agent.prompts.explorer_summary_prompt import (
    EXPLORER_SUMMARY_SYSTEM_PROMPT,
)
from app.application.agent.state_schema import AgentState


class ExplorerFinalizeNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        summary = await self._build_summary(state, config)
        stream_writer = get_stream_writer()
        stream_writer(
            {
                "kind": "checklist_complete",
                "data": {
                    "items": [item.model_dump() for item in state.checklist_items],
                    "summary": summary.content if summary else "",
                },
            }
        )
        messages = [summary] if summary else []
        return {
            "messages": messages,
            "subgraph_status": "complete",
        }

    async def _build_summary(
        self, state: AgentState, config: RunnableConfig | None
    ) -> AIMessage | None:
        payload = {
            "checklist_items": [item.model_dump() for item in state.checklist_items],
        }
        messages = [
            SystemMessage(content=EXPLORER_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=json.dumps(payload)),
        ]
        response = await self.model.ainvoke(messages, config)
        if isinstance(response, AIMessage):
            return response
        return AIMessage(content=str(response))
