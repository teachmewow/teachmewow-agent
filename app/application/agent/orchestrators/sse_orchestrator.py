"""
SSE Orchestrator for managing graph execution and streaming with debouncing.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from app.application.agent.state_schema import AgentState, StreamEvent
from app.application.agent.streaming import format_sse_event

from .observers.base import StreamObserver


# Debounce interval for LLM chunks (in seconds)
DEBOUNCE_INTERVAL_MS = 50
DEBOUNCE_INTERVAL_S = DEBOUNCE_INTERVAL_MS / 1000


class SSEOrchestrator:
    """
    Orchestrates graph execution with SSE streaming and debouncing.

    Features:
    - Debouncing of 50ms for LLM chunks to optimize network usage
    - Bypass (immediate delivery) for tool call/result events
    - Observer pattern for extensible side effects (e.g., DB persistence)
    """

    def __init__(self, graph: CompiledStateGraph):
        """
        Initialize the SSE orchestrator.

        Args:
            graph: Compiled LangGraph agent
        """
        self.graph = graph
        self._observers: list[StreamObserver] = []

    def add_observer(self, observer: StreamObserver) -> None:
        """
        Add an observer to receive stream events.

        Args:
            observer: Observer implementing StreamObserver protocol
        """
        self._observers.append(observer)

    def remove_observer(self, observer: StreamObserver) -> None:
        """
        Remove an observer.

        Args:
            observer: Observer to remove
        """
        if observer in self._observers:
            self._observers.remove(observer)

    async def _notify_observers(self, event: StreamEvent) -> None:
        """Notify all observers of an event."""
        for observer in self._observers:
            await observer.on_event(event)

    async def _notify_complete(self, full_response: str) -> None:
        """Notify all observers that streaming is complete."""
        for observer in self._observers:
            await observer.on_stream_complete(full_response)

    async def _notify_error(self, error: Exception) -> None:
        """Notify all observers of an error."""
        for observer in self._observers:
            await observer.on_error(error)

    async def stream(self, state: AgentState) -> AsyncGenerator[str, None]:
        """
        Execute the graph and stream SSE events with debouncing.

        LLM chunks are debounced at 50ms intervals to optimize network.
        Tool events are delivered immediately (bypass debounce).

        Args:
            state: Initial agent state

        Yields:
            SSE-formatted event strings
        """
        full_response = ""
        chunk_buffer = ""
        last_flush_time = asyncio.get_event_loop().time()

        try:
            async for event in self.graph.astream_events(state, version="v2"):
                event_kind = event.get("event")
                event_data = event.get("data", {})
                event_name = event.get("name", "")

                if event_kind == "on_chat_model_stream":
                    # LLM chunk - apply debouncing
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        chunk_buffer += chunk.content

                        # Check if we should flush the buffer
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_flush_time >= DEBOUNCE_INTERVAL_S:
                            if chunk_buffer:
                                stream_event = StreamEvent(
                                    kind="llm_delta",
                                    data={"content": chunk_buffer},
                                )
                                await self._notify_observers(stream_event)
                                yield format_sse_event(stream_event)
                                chunk_buffer = ""
                                last_flush_time = current_time

                elif event_kind == "on_tool_start":
                    # Tool call - bypass debounce, deliver immediately
                    # First flush any pending chunks
                    if chunk_buffer:
                        stream_event = StreamEvent(
                            kind="llm_delta",
                            data={"content": chunk_buffer},
                        )
                        await self._notify_observers(stream_event)
                        yield format_sse_event(stream_event)
                        chunk_buffer = ""
                        last_flush_time = asyncio.get_event_loop().time()

                    # Emit tool call event
                    tool_input = event_data.get("input", {})
                    stream_event = StreamEvent(
                        kind="tool_call",
                        data={
                            "tool_call_id": event.get("run_id", ""),
                            "tool_name": event_name,
                            "arguments": json.dumps(tool_input),
                        },
                    )
                    await self._notify_observers(stream_event)
                    yield format_sse_event(stream_event)

                elif event_kind == "on_tool_end":
                    # Tool result - bypass debounce, deliver immediately
                    output = event_data.get("output", "")
                    stream_event = StreamEvent(
                        kind="tool_result",
                        data={
                            "tool_call_id": event.get("run_id", ""),
                            "result": str(output),
                        },
                    )
                    await self._notify_observers(stream_event)
                    yield format_sse_event(stream_event)

            # Flush any remaining chunks in buffer
            if chunk_buffer:
                stream_event = StreamEvent(
                    kind="llm_delta",
                    data={"content": chunk_buffer},
                )
                await self._notify_observers(stream_event)
                yield format_sse_event(stream_event)

            # Notify observers that streaming is complete
            await self._notify_complete(full_response)

            # Emit done event
            done_event = StreamEvent(kind="done", data={})
            await self._notify_observers(done_event)
            yield format_sse_event(done_event)

        except Exception as e:
            # Notify observers of error
            await self._notify_error(e)

            # Emit error event
            error_event = StreamEvent(kind="error", data={"error": str(e)})
            yield format_sse_event(error_event)
