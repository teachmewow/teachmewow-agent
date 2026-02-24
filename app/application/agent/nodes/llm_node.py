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

from app.application.agent.models import CoachPlan
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
            if state.route == "coach":
                response = self._normalize_coach_response(response)
            response = self._attach_coach_plan(response, state.coach_plan)
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

    def _attach_coach_plan(self, response: AIMessage, coach_plan: object) -> AIMessage:
        if not coach_plan:
            return response
        if not isinstance(coach_plan, dict):
            raise RuntimeError("LLMNode: coach_plan must be a dict")
        try:
            plan = CoachPlan.model_validate(coach_plan)
            public_plan = plan.to_public_payload()
        except Exception as exc:
            raise RuntimeError("LLMNode: coach_plan payload is invalid") from exc
        response_metadata = dict(getattr(response, "response_metadata", {}) or {})
        response_metadata["coach_plan"] = public_plan
        return response.model_copy(update={"response_metadata": response_metadata})

    def _normalize_coach_response(self, response: AIMessage) -> AIMessage:
        content = response.content
        if not isinstance(content, str):
            return response

        normalized = self._normalize_citation_density(content, max_unique_markers=5)
        if normalized == content:
            return response
        return response.model_copy(update={"content": normalized})

    def _normalize_citation_density(self, content: str, max_unique_markers: int) -> str:
        marker_pattern = re.compile(r"\[\[([a-zA-Z0-9_:-]+)\]\]")
        allowed_markers: set[str] = set()
        previous_line_marker: str | None = None
        normalized_lines: list[str] = []

        for line in content.splitlines():
            markers = marker_pattern.findall(line)
            if not markers:
                normalized_lines.append(line)
                previous_line_marker = None
                continue

            chosen_marker: str | None = None
            for marker in markers:
                if marker in allowed_markers:
                    chosen_marker = marker
                    break
                if len(allowed_markers) >= max_unique_markers:
                    continue
                allowed_markers.add(marker)
                chosen_marker = marker
                break

            line_without_markers = marker_pattern.sub("", line)
            line_without_markers = re.sub(r"\s{2,}", " ", line_without_markers).rstrip()

            if chosen_marker and chosen_marker == previous_line_marker:
                chosen_marker = None

            if chosen_marker:
                separator = " " if line_without_markers else ""
                normalized_lines.append(
                    f"{line_without_markers}{separator}[[{chosen_marker}]]"
                )
                previous_line_marker = chosen_marker
            else:
                normalized_lines.append(line_without_markers)
                previous_line_marker = None

        return "\n".join(normalized_lines)
