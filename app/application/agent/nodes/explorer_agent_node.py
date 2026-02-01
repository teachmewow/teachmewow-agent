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
        checklist_text = self._format_current_item(
            state.checklist_items, state.current_checklist_id
        )
        context_hint = self._build_context_hint(state)
        subgraph_messages = get_subgraph_messages(state.messages)
        return [
            SystemMessage(content=KNOWLEDGE_EXPLORER_SYSTEM_PROMPT),
            SystemMessage(content=context_hint),
            *subgraph_messages,
            HumanMessage(content=checklist_text),
        ]

    def _format_current_item(
        self, items: list[ChecklistItem], current_id: str | None
    ) -> str:
        if not items:
            return "Current checklist item: (none)"
        current = self._find_current_item(items, current_id)
        if not current:
            return "Current checklist item: (none)"
        lines = [
            "Current checklist item:",
            f"- [{current.status}] {current.title} (id={current.id})",
        ]
        for evidence in current.evidence:
            lines.append(f"  - evidence: {evidence}")
        return "\n".join(lines)

    def _find_current_item(
        self, items: list[ChecklistItem], current_id: str | None
    ) -> ChecklistItem | None:
        if current_id:
            for item in items:
                if item.id == current_id:
                    return item
        for item in items:
            if item.status != "complete":
                return item
        return None

    def _build_context_hint(self, state: AgentState) -> str:
        return (
            "O usuário esta fazendo perguntas sobre spec, class, role "
            f"baseado noq veio da requisicao. "
            f"wow_class={state.wow_class}, wow_spec={state.wow_spec}, "
            f"wow_role={state.wow_role}."
        )

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
