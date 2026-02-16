"""
Default strategy implementations for LangGraph stream events.
"""

from __future__ import annotations

from .base import StreamEventStrategy, StreamOrchestratorActions


class ChatModelStartStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        return []


class ChatModelStreamStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        sse = await actions.handle_llm_chunk(event, event_data, stream_state)
        return [sse] if sse else []


class ChatModelEndStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        return []


class IgnoreEventStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        return []


class ToolStartStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        return await actions.emit_tool_call_event(event, stream_state)


class ToolEndStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        return await actions.emit_tool_result_event(event, event_data, stream_state)


class ChainStartStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        return []


class ChainEndStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        if not event_name:
            return []
        await actions.handle_chain_end(event_data, event_name, stream_state)
        return []


class DefaultPassThroughStrategy:
    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state,
        actions: StreamOrchestratorActions,
    ) -> list[str]:
        if not event_kind:
            return []
        return await actions.emit_langchain_event(event, stream_state)


def create_default_strategy_registry() -> dict[str, StreamEventStrategy]:
    return {
        "on_chat_model_start": ChatModelStartStrategy(),
        "on_chat_model_stream": ChatModelStreamStrategy(),
        "on_chat_model_end": ChatModelEndStrategy(),
        "on_chain_stream": IgnoreEventStrategy(),
        "on_tool_start": ToolStartStrategy(),
        "on_tool_end": ToolEndStrategy(),
        "on_chain_start": ChainStartStrategy(),
        "on_chain_end": ChainEndStrategy(),
        # Custom chunks are intentionally ignored. Tool events must come from
        # on_tool_start/on_tool_end to keep a single source of truth.
        "custom": IgnoreEventStrategy(),
    }
