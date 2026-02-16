"""
SSE Orchestrator for managing graph execution and streaming with debouncing.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Awaitable, Callable

from langgraph.graph.state import CompiledStateGraph

from langchain_core.messages import BaseMessage

from app.application.agent.state_schema import AgentState, StreamEvent
from app.application.agent.streaming import (
    build_langchain_stream_event,
    format_sse_event,
)

from .observers.base import StreamObserver
from .strategies import (
    DefaultPassThroughStrategy,
    StreamEventStrategy,
    create_default_strategy_registry,
)


# Debounce interval for LLM chunks (in seconds)
DEBOUNCE_INTERVAL_MS = 50
DEBOUNCE_INTERVAL_S = DEBOUNCE_INTERVAL_MS / 1000
logger = logging.getLogger(__name__)


@dataclass
class _StreamState:
    full_response: str
    chunk_buffer: str
    last_flush_time: float
    total_message_count: int
    llm_event_context: dict | None
    seen_message_keys: set[str]


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
        self._default_strategy: StreamEventStrategy = DefaultPassThroughStrategy()
        self._event_strategies = create_default_strategy_registry()
        self._pre_emit_chain: list[
            Callable[[_StreamState, bool], Awaitable[str | None]]
        ] = [self._flush_before_emit]
        self._post_emit_chain: list[
            Callable[[StreamEvent], Awaitable[None]]
        ] = [self._notify_stage]

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

    async def _notify_node_complete(
        self, node: str, messages: list[BaseMessage]
    ) -> None:
        """Notify all observers that a node completed with new messages."""
        for observer in self._observers:
            await observer.on_node_complete(node, messages)

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
        stream_state = _StreamState(
            full_response="",
            chunk_buffer="",
            last_flush_time=self._now(),
            total_message_count=len(state.messages),
            llm_event_context=None,
            seen_message_keys=self._build_seen_message_keys(state.messages),
        )

        try:
            async for event in self.graph.astream_events(state, version="v2"):
                event_kind = str(event.get("event") or "")
                raw_event_data = event.get("data", {})
                event_data = raw_event_data if isinstance(raw_event_data, dict) else {}
                event_name = str(event.get("name") or "")
                strategy = self._event_strategies.get(event_kind, self._default_strategy)
                emitted = await strategy.handle(
                    event=event,
                    event_kind=event_kind,
                    event_data=event_data,
                    event_name=event_name,
                    stream_state=stream_state,
                    actions=self,
                )
                for sse in emitted:
                    yield sse

            # Flush any remaining chunks in buffer
            flush_sse = await self._flush_chunk_buffer(stream_state)
            if flush_sse:
                yield flush_sse

            # Notify observers that streaming is complete
            await self._notify_complete(stream_state.full_response)

            # Emit done event
            done_event = StreamEvent(
                event="done", data={"payload": {"finish_reason": "done"}}
            )
            await self._notify_observers(done_event)
            yield format_sse_event(done_event)

        except Exception as e:
            logger.exception(
                "SSE stream failed: thread_id=%s user_id=%s error=%s",
                state.thread_id,
                state.user_id,
                e,
            )
            # Notify observers of error
            await self._notify_error(e)

            # Emit error event
            error_event = StreamEvent(event="error", data={"payload": {"error": str(e)}})
            yield format_sse_event(error_event)

    def _now(self) -> float:
        return asyncio.get_event_loop().time()

    async def _handle_llm_chunk(
        self, event: dict, event_data: dict, stream_state: _StreamState
    ) -> str | None:
        chunk = event_data.get("chunk")
        if not (chunk and hasattr(chunk, "content") and chunk.content):
            return None
        stream_state.llm_event_context = event

        stream_state.full_response += chunk.content
        stream_state.chunk_buffer += chunk.content

        if not self._should_flush(stream_state):
            return None

        return await self._flush_chunk_buffer(stream_state)

    def _should_flush(self, stream_state: _StreamState) -> bool:
        return self._now() - stream_state.last_flush_time >= DEBOUNCE_INTERVAL_S

    async def _flush_chunk_buffer(self, stream_state: _StreamState) -> str | None:
        if not stream_state.chunk_buffer:
            return None

        if stream_state.llm_event_context:
            stream_event = build_langchain_stream_event(
                stream_state.llm_event_context,
                data_override={"chunk": {"content": stream_state.chunk_buffer}},
            )
        else:
            stream_event = StreamEvent(
                event="on_chat_model_stream",
                data={"chunk": {"content": stream_state.chunk_buffer}},
            )
        await self._notify_observers(stream_event)
        stream_state.chunk_buffer = ""
        stream_state.last_flush_time = self._now()
        return format_sse_event(stream_event)

    async def _emit_tool_result(self, event: dict, event_data: dict) -> StreamEvent:
        output = event_data.get("output", "")
        if isinstance(output, dict) and "content" in output:
            output = output.get("content", "")
        elif hasattr(output, "content"):
            output = getattr(output, "content", "")
        if output is not event_data.get("output"):
            event = {**event, "data": {**event_data, "output": output}}
        return build_langchain_stream_event(event)

    async def _handle_chain_end(
        self, event_data: dict, node: str, stream_state: _StreamState
    ) -> None:
        new_messages, updated_count = self._extract_new_messages(
            event_data, stream_state.total_message_count, stream_state.seen_message_keys
        )
        stream_state.total_message_count = updated_count
        if new_messages:
            await self._notify_node_complete(node, new_messages)

    async def handle_chain_end(
        self, event_data: dict, node: str, stream_state: _StreamState
    ) -> None:
        await self._handle_chain_end(event_data, node, stream_state)

    async def emit_langchain_event(
        self, event: dict, stream_state: _StreamState, *, flush_before: bool = False
    ) -> list[str]:
        stream_event = build_langchain_stream_event(event)
        return await self._emit_stream_event(
            stream_event, stream_state, flush_before=flush_before
        )

    async def emit_tool_call_event(
        self, event: dict, stream_state: _StreamState
    ) -> list[str]:
        stream_event = build_langchain_stream_event(event)
        return await self._emit_stream_event(stream_event, stream_state, flush_before=True)

    async def emit_tool_result_event(
        self, event: dict, event_data: dict, stream_state: _StreamState
    ) -> list[str]:
        stream_event = await self._emit_tool_result(event, event_data)
        return await self._emit_stream_event(stream_event, stream_state, flush_before=False)

    async def handle_llm_chunk(
        self, event: dict, event_data: dict, stream_state: _StreamState
    ) -> str | None:
        return await self._handle_llm_chunk(event, event_data, stream_state)

    async def _flush_before_emit(
        self, stream_state: _StreamState, flush_before: bool
    ) -> str | None:
        if not flush_before:
            return None
        return await self._flush_chunk_buffer(stream_state)

    async def _notify_stage(self, stream_event: StreamEvent) -> None:
        await self._notify_observers(stream_event)

    async def _emit_stream_event(
        self, stream_event: StreamEvent, stream_state: _StreamState, *, flush_before: bool
    ) -> list[str]:
        emitted: list[str] = []
        for stage in self._pre_emit_chain:
            flushed = await stage(stream_state, flush_before)
            if flushed:
                emitted.append(flushed)

        for stage in self._post_emit_chain:
            await stage(stream_event)

        emitted.append(format_sse_event(stream_event))
        return emitted

    def _extract_new_messages(
        self,
        event_data: dict,
        total_message_count: int,
        seen_message_keys: set[str],
    ) -> tuple[list[BaseMessage], int]:
        """
        Extract new messages produced by a node from LangGraph event data.

        Handles both cases:
        - output contains full message history
        - output contains only new messages
        """
        messages = self._get_messages_from_event_data(event_data)
        if not messages:
            return [], total_message_count

        # Keep count-based branch for performance when stream is monotonic,
        # then filter by seen message keys to guarantee "save only new".
        candidate_messages: list[BaseMessage]
        if len(messages) > total_message_count:
            candidate_messages = messages[total_message_count:]
            updated_count = len(messages)
        else:
            # Some LangGraph nodes emit delta payloads or branch-local snapshots
            # with non-monotonic lengths; treat as candidates and filter by key.
            candidate_messages = messages
            updated_count = max(total_message_count, len(messages))

        new_messages: list[BaseMessage] = []
        for message in candidate_messages:
            key = self._message_key(message)
            if not key:
                continue
            if key in seen_message_keys:
                continue
            seen_message_keys.add(key)
            new_messages.append(message)

        return new_messages, updated_count

    def _build_seen_message_keys(self, messages: list[BaseMessage]) -> set[str]:
        keys: set[str] = set()
        for message in messages:
            key = self._message_key(message)
            if key:
                keys.add(key)
        return keys

    def _message_key(self, message: BaseMessage) -> str | None:
        message_type = getattr(message, "type", None) or message.__class__.__name__
        message_id = getattr(message, "id", None)
        if isinstance(message_id, str) and message_id:
            return f"{message_type}:{message_id}"

        if message_type == "tool":
            tool_call_id = getattr(message, "tool_call_id", None)
            if isinstance(tool_call_id, str) and tool_call_id:
                return f"tool_call:{tool_call_id}"

        content = getattr(message, "content", "")
        tool_calls = getattr(message, "tool_calls", None)
        return f"{message_type}:{content}:{tool_calls}"

    def _get_messages_from_event_data(self, event_data: dict) -> list[BaseMessage]:
        """
        Try to extract messages from LangGraph event data.

        Looks for messages in common locations for LangGraph events.
        """
        for key in ("output", "state", "result"):
            container = event_data.get(key)
            if isinstance(container, dict) and "messages" in container:
                messages = container.get("messages", [])
                if isinstance(messages, list):
                    return messages

        if "messages" in event_data and isinstance(event_data["messages"], list):
            return event_data["messages"]

        return []
