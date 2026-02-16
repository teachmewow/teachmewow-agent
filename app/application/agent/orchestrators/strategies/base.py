"""
Strategy contracts for SSE event handling.
"""

from __future__ import annotations

from typing import Any, Protocol


class StreamOrchestratorActions(Protocol):
    """Actions exposed by SSEOrchestrator to event strategies."""

    async def emit_generic_event(
        self, event: dict, stream_state: Any, *, flush_before: bool = False
    ) -> list[str]: ...

    async def emit_tool_start_event(
        self, event: dict, stream_state: Any
    ) -> list[str]: ...

    async def emit_tool_end_event(
        self, event: dict, event_data: dict, stream_state: Any
    ) -> list[str]: ...

    async def process_llm_stream_chunk(
        self, event: dict, event_data: dict, stream_state: Any
    ) -> list[str]: ...

    async def process_chain_end(
        self, event_data: dict, node: str, stream_state: Any
    ) -> None: ...


class StreamEventStrategy(Protocol):
    """Protocol implemented by stream event strategies."""

    async def handle(
        self,
        *,
        event: dict,
        event_kind: str,
        event_data: dict,
        event_name: str,
        stream_state: Any,
        actions: StreamOrchestratorActions,
    ) -> list[str]: ...
