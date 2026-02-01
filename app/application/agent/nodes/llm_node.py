from app.application.agent.state_schema import AgentState
from app.application.agent.prompts.system_prompt import AGENT_SYSTEM_PROMPT
from langchain_core.messages import BaseMessageChunk, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from collections.abc import AsyncGenerator
from langchain_core.messages import BaseMessage


class LLMNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(self, state: AgentState, config: RunnableConfig | None = None) -> AgentState:
        """Call the LLM with the current state."""
        chat_history = self.mount_chat_history(state)
        response = await self._stream_llm_response(self.model, chat_history, config)
        return {"messages": [response]}

    def mount_chat_history(self, state: AgentState) -> str:
        """Organize the system prompt based on the state."""
        context_hint = self._build_context_hint(state)
        return [
            SystemMessage(content=AGENT_SYSTEM_PROMPT),
            SystemMessage(content=context_hint),
        ] + state.messages

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
    ) -> AsyncGenerator[BaseMessageChunk]:
        """Stream the LLM response."""
        response = None
        async for chunk in model.astream(messages, config):
            if response is None:
                response = chunk
            else:
                response += chunk
        return response
