"""
LLM node for the knowledge explorer flow.
"""

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, BaseMessageChunk, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.application.agent.prompts.knowledge_explorer_prompt import (
    KNOWLEDGE_EXPLORER_SYSTEM_PROMPT,
)
from app.application.agent.state_schema import AgentState


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
        context_payload = {
            "checklist_items": [item.model_dump() for item in state.checklist_items],
            "exploration_context": state.exploration_context,
        }
        return [
            SystemMessage(content=KNOWLEDGE_EXPLORER_SYSTEM_PROMPT),
            *state.messages,
            HumanMessage(content=json.dumps(context_payload)),
        ]

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
