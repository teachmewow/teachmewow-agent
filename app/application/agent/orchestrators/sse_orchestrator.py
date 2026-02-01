"""
SSE Orchestrator for managing graph execution and streaming with debouncing.
"""

import asyncio
import json
from types import SimpleNamespace
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from langchain_core.messages import BaseMessage

from app.application.agent.state_schema import AgentState, StreamEvent
from app.application.agent.streaming import (
    build_langchain_stream_event,
    format_sse_event,
)

from .observers.base import StreamObserver


# Debounce interval for LLM chunks (in seconds)
DEBOUNCE_INTERVAL_MS = 50
DEBOUNCE_INTERVAL_S = DEBOUNCE_INTERVAL_MS / 1000


@dataclass
class _StreamState:
    full_response: str
    chunk_buffer: str
    last_flush_time: float
    total_message_count: int
    llm_event_context: dict | None


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
        )

        custom_tool_result_ids: set[str] = set()
        try:
            async for event in self.graph.astream_events(state, version="v2"):
                event_kind = event.get("event")
                event_data = event.get("data", {})
                event_name = event.get("name", "")

                if event_kind == "on_chat_model_start":
                    yield format_sse_event(build_langchain_stream_event(event))
                    continue

                if event_kind == "on_chat_model_stream":
                    sse = await self._handle_llm_chunk(event, event_data, stream_state)
                    if sse:
                        yield sse
                    continue

                if event_kind == "on_chat_model_end":
                    yield format_sse_event(build_langchain_stream_event(event))
                    continue

                if event_kind == "on_chain_stream":
                    chunk = event_data.get("chunk")
                    messages = None
                    if isinstance(chunk, dict):
                        messages = chunk.get("messages")
                        if messages is None:
                            for value in chunk.values():
                                if isinstance(value, dict) and "messages" in value:
                                    messages = value.get("messages")
                                    break
                    elif hasattr(chunk, "messages"):
                        messages = chunk.messages

                    if messages:
                        flush_sse = await self._flush_chunk_buffer(stream_state)
                        if flush_sse:
                            yield flush_sse
                        for message in messages:
                            content = (
                                message.get("content")
                                if isinstance(message, dict)
                                else getattr(message, "content", None)
                            )
                            if content:
                                chat_event = {
                                    "event": "on_chat_model_stream",
                                    "name": event_name,
                                    "run_id": event.get("run_id", ""),
                                    "data": {
                                        "chunk": SimpleNamespace(content=content)
                                    },
                                }
                                sse = await self._handle_llm_chunk(
                                    chat_event, chat_event["data"], stream_state
                                )
                                if sse:
                                    yield sse
                        continue

                if event_kind == "on_tool_start":
                    flush_sse = await self._flush_chunk_buffer(stream_state)
                    if flush_sse:
                        yield flush_sse
                    yield await self._emit_tool_call(event, event_data, event_name)
                    continue

                if event_kind == "on_tool_end":
                    if event.get("run_id") in custom_tool_result_ids:
                        continue
                    yield await self._emit_tool_result(event, event_data)
                    continue

                if event_kind == "custom":
                    custom_kind = event_data.get("kind")
                    custom_data = event_data.get("data", {})
                    if custom_kind in {"tool_call", "tool_result"}:
                        flush_sse = await self._flush_chunk_buffer(stream_state)
                        if flush_sse:
                            yield flush_sse
                        if custom_kind == "tool_call":
                            tool_name = custom_data.get("tool_name", "tool")
                            arguments = custom_data.get("arguments", "")
                            try:
                                tool_input = json.loads(arguments)
                            except Exception:
                                tool_input = arguments
                            tool_event = {
                                "event": "on_tool_start",
                                "name": tool_name,
                                "run_id": custom_data.get("tool_call_id", ""),
                                "data": {"input": tool_input},
                            }
                            yield await self._emit_tool_call(tool_event, tool_event["data"], tool_name)
                            continue
                        custom_tool_result_ids.add(custom_data.get("tool_call_id", ""))
                        tool_event = {
                            "event": "on_tool_end",
                            "name": custom_data.get("tool_name", "tool"),
                            "run_id": custom_data.get("tool_call_id", ""),
                            "data": {"output": custom_data.get("content", "")},
                        }
                        yield await self._emit_tool_result(tool_event, tool_event["data"])
                        continue

                    flush_sse = await self._flush_chunk_buffer(stream_state)
                    if flush_sse:
                        yield flush_sse
                    stream_event = build_langchain_stream_event(event)
                    await self._notify_observers(stream_event)
                    yield format_sse_event(stream_event)
                    continue

                if event_kind == "on_chain_start" and event_name:
                    yield format_sse_event(build_langchain_stream_event(event))
                    continue

                if event_kind == "on_chain_end" and event_name:
                    await self._handle_chain_end(event_data, event_name, stream_state)
                    yield format_sse_event(build_langchain_stream_event(event))
                    continue

                if event_kind:
                    yield format_sse_event(build_langchain_stream_event(event))

            # Flush any remaining chunks in buffer
            flush_sse = await self._flush_chunk_buffer(stream_state)
            if flush_sse:
                yield flush_sse

            # Notify observers that streaming is complete
            await self._notify_complete(stream_state.full_response)

            # Emit done event
            done_event = StreamEvent(event="done", data={})
            await self._notify_observers(done_event)
            yield format_sse_event(done_event)

        except Exception as e:
            # Notify observers of error
            await self._notify_error(e)

            # Emit error event
            error_event = StreamEvent(event="error", data={"error": str(e)})
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

    async def _emit_tool_call(
        self, event: dict, event_data: dict, event_name: str
    ) -> str:
        stream_event = build_langchain_stream_event(event)
        await self._notify_observers(stream_event)
        return format_sse_event(stream_event)

    async def _emit_tool_result(self, event: dict, event_data: dict) -> str:
        output = event_data.get("output", "")
        if isinstance(output, dict) and "content" in output:
            output = output.get("content", "")
        elif hasattr(output, "content"):
            output = getattr(output, "content", "")
        if output is not event_data.get("output"):
            event = {**event, "data": {**event_data, "output": output}}
        stream_event = build_langchain_stream_event(event)
        await self._notify_observers(stream_event)
        return format_sse_event(stream_event)

    async def _handle_chain_end(
        self, event_data: dict, node: str, stream_state: _StreamState
    ) -> None:
        new_messages, updated_count = self._extract_new_messages(
            event_data, stream_state.total_message_count
        )
        stream_state.total_message_count = updated_count
        if new_messages:
            await self._notify_node_complete(node, new_messages)

    def _extract_new_messages(
        self, event_data: dict, total_message_count: int
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

        if len(messages) > total_message_count:
            new_messages = messages[total_message_count:]
            return new_messages, len(messages)

        # If messages length is not greater, assume it's already a delta
        return messages, total_message_count + len(messages)

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
