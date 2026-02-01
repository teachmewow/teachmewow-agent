"""
LLM node for the knowledge explorer flow.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, BaseMessageChunk, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.application.agent.prompts.knowledge_explorer_prompt import (
    KNOWLEDGE_EXPLORER_SYSTEM_PROMPT,
)
from app.application.agent.nodes.explorer_message_utils import get_subgraph_messages
from app.application.agent.state_schema import AgentState, ChecklistItem


class ExplorerAgentNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        messages = self._mount_messages(state)
        response = await self._stream_llm_response(self.model, messages, config)
        return {"messages": [response]}

    def _mount_messages(self, state: AgentState) -> list[BaseMessage]:
        checklist_text = self._format_checklist(state.checklist_items)
        subgraph_messages = get_subgraph_messages(state.messages)
        return [
            SystemMessage(content=KNOWLEDGE_EXPLORER_SYSTEM_PROMPT),
            *subgraph_messages,
            HumanMessage(content=checklist_text),
        ]

    def _format_checklist(self, items: list[ChecklistItem]) -> str:
        if not items:
            return "Checklist: (empty)"
        lines = ["Checklist:"]
        for item in items:
            status = item.status
            line = f"- [{status}] {item.title} (id={item.id})"
            lines.append(line)
            for evidence in item.evidence:
                lines.append(f"  - evidence: {evidence}")
        return "\n".join(lines)

    async def _stream_llm_response(
        self,
        model: BaseChatModel,
        messages: list[BaseMessage],
        config: RunnableConfig | None,
    ) -> BaseMessageChunk:
        response = None
        async for chunk in model.astream(messages, config):
            if response is None:
                response = chunk
            else:
                response += chunk
        return response
