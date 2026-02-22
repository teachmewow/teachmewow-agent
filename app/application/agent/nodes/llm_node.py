import json
import re
from collections.abc import AsyncGenerator

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    BaseMessageChunk,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig

from app.application.agent.prompts.system_prompt import AGENT_SYSTEM_PROMPT
from app.application.agent.state_schema import AgentState


class LLMNode:
    def __init__(self, model: BaseChatModel, system_prompt: str = AGENT_SYSTEM_PROMPT) -> None:
        self.model = model
        self.system_prompt = system_prompt

    async def __call__(self, state: AgentState, config: RunnableConfig | None = None) -> AgentState:
        """Call the LLM with the current state."""
        chat_history = self.mount_chat_history(state)
        response = await self._stream_llm_response(self.model, chat_history, config)
        if isinstance(response, AIMessage) and not response.tool_calls:
            citations = self._collect_citations(state.messages)
            if citations:
                response = self._attach_citations(response, citations)
        return {"messages": [response]}

    def mount_chat_history(self, state: AgentState) -> str:
        """Organize the system prompt based on the state."""
        context_hint = self._build_context_hint(state)
        return [
            SystemMessage(content=self.system_prompt),
            SystemMessage(content=context_hint),
        ] + state.messages

    def _build_context_hint(self, state: AgentState) -> str:
        char_info = state.char_info
        build_info = state.build_info
        build_hint = "none"
        if build_info is not None:
            if isinstance(build_info, dict):
                build_hint = (
                    f"build_id={build_info.get('build_id')}; "
                    f"hero_talent={build_info.get('hero_talent')}; "
                    f"scenario={build_info.get('scenario')}; "
                    f"decoded_nodes={len(build_info.get('decoded_nodes') or [])}"
                )
            else:
                build_hint = (
                    f"build_id={getattr(build_info, 'build_id', None)}; "
                    f"hero_talent={getattr(build_info, 'hero_talent', None)}; "
                    f"scenario={getattr(build_info, 'scenario', None)}; "
                    f"decoded_nodes={len(getattr(build_info, 'decoded_nodes', []) or [])}"
                )
        return (
            "O usuário esta fazendo perguntas sobre WoW com contexto fixo da sessão. "
            f"class={char_info.wow_class}, spec={char_info.spec}, role={char_info.role}. "
            f"active_build_id={state.active_build_id or 'none'}; "
            f"candidate_build_ids={state.candidate_build_ids}; "
            f"build_info={build_hint}."
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

    def _collect_citations(self, messages: list[BaseMessage]) -> dict[str, dict]:
        by_id: dict[str, dict] = {}
        for message in messages:
            if not isinstance(message, ToolMessage):
                continue
            try:
                payload = json.loads(str(message.content))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("tool") or "") != "guide_context_lookup":
                continue
            citations = payload.get("citations")
            if not isinstance(citations, list):
                continue
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                citation_id = str(citation.get("citation_id") or "").strip()
                if not citation_id:
                    continue
                by_id[citation_id] = citation
        return by_id

    def _attach_citations(self, response: AIMessage, citations: dict[str, dict]) -> AIMessage:
        content = str(response.content or "")
        marker_matches = re.findall(r"\[\[([a-zA-Z0-9_:-]+)\]\]", content)
        selected: list[dict] = []
        seen: set[str] = set()
        for marker in marker_matches:
            citation = citations.get(marker)
            if not citation:
                continue
            citation_id = str(citation.get("citation_id") or marker)
            if citation_id in seen:
                continue
            seen.add(citation_id)
            selected.append(citation)

        if not selected:
            # Fallback: if model forgot explicit markers, keep top citations for rehydration.
            selected = list(citations.values())[:3]

        response_metadata = dict(getattr(response, "response_metadata", {}) or {})
        response_metadata["citations"] = selected
        return response.model_copy(update={"response_metadata": response_metadata})
