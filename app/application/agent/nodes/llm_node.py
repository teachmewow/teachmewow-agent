from app.application.agent.state_schema import AgentState
from langchain_core.messages import BaseMessageChunk, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from collections.abc import AsyncGenerator
from langchain_core.messages import BaseMessage


AGENT_SYSTEM_PROMPT = """
You are an expert World of Warcraft coach. You help players improve their gameplay by providing advice on:
- Class and specialization mechanics
- Optimal rotations and ability usage
- Gear choices and stat priorities
- Raid and dungeon strategies
- PvP tactics and arena compositions
"""

class LLMNode:
    def __init__(self, model: BaseChatModel) -> None:
        self.model = model

    async def __call__(self, state: AgentState, config: dict) -> AgentState:
        """Call the LLM with the current state."""
        chat_history = self.mount_chat_history(state)
        response = await self._stream_llm_response(self.model, chat_history, config)
        return {"messages": [response]}

    def mount_chat_history(self, state: AgentState) -> str:
        """Organize the system prompt based on the state."""
        return [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + state.messages
    
    async def _stream_llm_response(
        self,
        model: BaseChatModel,
        messages: list[BaseMessage],
        config: dict,
    ) -> AsyncGenerator[BaseMessageChunk]:
        """Stream the LLM response."""
        response = None
        async for chunk in model.astream(messages, config):
            if response is None:
                response = chunk
            else:
                response += chunk
        return response
