"""
Streaming utilities for adapting LangGraph events to SSE format.
"""

import json
from types import SimpleNamespace
from collections.abc import Mapping
from collections.abc import AsyncGenerator
from typing import Any

from .state_schema import StreamEvent


class StreamHandler:
    """
    Handler for streaming events from LangGraph to SSE.

    This handler is created per-request and is isolated from other requests.
    It adapts LangGraph streaming events to the SSE format expected by the frontend.
    """

    def __init__(self):
        self._events: list[StreamEvent] = []

    def emit(self, event: StreamEvent) -> None:
        """
        Emit a streaming event.

        Args:
            event: The event to emit
        """
        self._events.append(event)

    def emit_llm_delta(self, content: str, message_id: str | None = None) -> None:
        """Emit an LLM token delta event (on_chat_model_stream)."""
        data = {"chunk": {"content": content}}
        if message_id:
            data["message_id"] = message_id
        self.emit(StreamEvent(event="on_chat_model_stream", data=data))

    def emit_tool_call(
        self, tool_call_id: str, tool_name: str, arguments: str
    ) -> None:
        """Emit a tool call event (on_tool_start)."""
        tool_input = _try_parse_json(arguments)
        self.emit(
            StreamEvent(
                event="on_tool_start",
                name=tool_name,
                run_id=tool_call_id,
                data={"input": tool_input},
            )
        )

    def emit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Emit a tool result event (on_tool_end)."""
        self.emit(
            StreamEvent(
                event="on_tool_end",
                run_id=tool_call_id,
                data={"output": result},
            )
        )

    def emit_node_started(self, node_name: str) -> None:
        """Emit a node started event (on_chain_start)."""
        self.emit(StreamEvent(event="on_chain_start", name=node_name, data={}))

    def emit_node_finished(self, node_name: str) -> None:
        """Emit a node finished event (on_chain_end)."""
        self.emit(StreamEvent(event="on_chain_end", name=node_name, data={}))

    def emit_done(self) -> None:
        """Emit a done event."""
        self.emit(StreamEvent(event="done", data={}))

    def emit_error(self, error: str) -> None:
        """Emit an error event."""
        self.emit(StreamEvent(event="error", data={"error": error}))

    def get_events(self) -> list[StreamEvent]:
        """Get all emitted events."""
        return self._events.copy()

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()


def create_stream_handler() -> StreamHandler:
    """
    Create a new stream handler for a request.

    Returns:
        A new StreamHandler instance (isolated per request)
    """
    return StreamHandler()


def format_sse_event(event: StreamEvent) -> str:
    """
    Format a StreamEvent as an SSE message.

    Args:
        event: The event to format

    Returns:
        Formatted SSE message string
    """
    data = _safe_json_dumps(
        {
            "event": event.event,
            "name": event.name,
            "run_id": event.run_id,
            "parent_ids": event.parent_ids,
            "metadata": event.metadata,
            "tags": event.tags,
            "data": event.data,
        }
    )
    return f"event: {event.event}\ndata: {data}\n\n"


def build_langchain_stream_event(
    event: dict, data_override: dict | None = None
) -> StreamEvent:
    """Build a StreamEvent envelope from a LangChain astream_events payload."""
    data = data_override if data_override is not None else event.get("data", {})
    return StreamEvent(
        event=event.get("event", ""),
        name=event.get("name", ""),
        run_id=event.get("run_id", ""),
        parent_ids=event.get("parent_ids") or [],
        metadata=event.get("metadata") or {},
        tags=event.get("tags") or [],
        data=_sanitize_for_json(data),
    )


def _try_parse_json(raw: str) -> object:
    custom_tool_result_ids: set[str] = set()
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _safe_json_dumps(payload: object) -> str:
    return json.dumps(payload, default=str)


def _sanitize_for_json(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]
    if isinstance(value, Mapping):
        return {str(k): _sanitize_for_json(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        return _sanitize_for_json(value.model_dump())
    if hasattr(value, "dict"):
        try:
            return _sanitize_for_json(value.dict())
        except Exception:
            return str(value)
    return str(value)


async def stream_graph_events(
    graph: Any,
    state: Any,
    stream_handler: StreamHandler,
) -> AsyncGenerator[str, None]:
    """
    Stream events from a LangGraph execution as SSE.

    This function executes the graph and yields SSE-formatted events
    for consumption by the frontend.

    Args:
        graph: The compiled LangGraph
        state: Initial state for the graph
        stream_handler: Handler for emitting events

    Yields:
        SSE-formatted event strings
    """
    custom_tool_result_ids: set[str] = set()
    try:
        # Stream the graph execution
        async for event in graph.astream_events(state, version="v2"):
            event_kind = event.get("event")
            event_data = event.get("data", {})
            event_name = event.get("name", "")

            if event_kind == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                content = getattr(chunk, "content", None) if chunk else None
                if content:
                    stream_handler.emit_llm_delta(content)
                    yield format_sse_event(
                        build_langchain_stream_event(
                            event, data_override={"chunk": {"content": content}}
                        )
                    )
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
                            stream_handler.emit_llm_delta(content)
                            yield format_sse_event(
                                build_langchain_stream_event(chat_event)
                            )
                    continue


            if event_kind == "on_tool_start":
                tool_input = event_data.get("input", {})
                stream_handler.emit_tool_call(
                    tool_call_id=event.get("run_id", ""),
                    tool_name=event_name,
                    arguments=json.dumps(tool_input),
                )
                yield format_sse_event(build_langchain_stream_event(event))
                continue

            if event_kind == "on_tool_end":
                if event.get("run_id") in custom_tool_result_ids:
                    continue
                output = event_data.get("output", "")
                if isinstance(output, dict) and "content" in output:
                    output = output.get("content", "")
                elif hasattr(output, "content"):
                    output = getattr(output, "content", "")
                stream_handler.emit_tool_result(
                    tool_call_id=event.get("run_id", ""),
                    result=str(output),
                )
                yield format_sse_event(build_langchain_stream_event(event))
                continue

            if event_kind == "on_chain_start" and event_name:
                stream_handler.emit_node_started(event_name)
                yield format_sse_event(build_langchain_stream_event(event))
                continue

            if event_kind == "on_chain_end" and event_name:
                stream_handler.emit_node_finished(event_name)
                yield format_sse_event(build_langchain_stream_event(event))
                continue

            if event_kind == "custom":
                custom_kind = event_data.get("kind")
                custom_data = event_data.get("data", {})
                if custom_kind in {"tool_call", "tool_result"}:
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
                        yield format_sse_event(build_langchain_stream_event(tool_event))
                        continue
                    custom_tool_result_ids.add(custom_data.get("tool_call_id", ""))
                    tool_event = {
                        "event": "on_tool_end",
                        "name": custom_data.get("tool_name", "tool"),
                        "run_id": custom_data.get("tool_call_id", ""),
                        "data": {"output": custom_data.get("content", "")},
                    }
                    yield format_sse_event(build_langchain_stream_event(tool_event))
                    continue

                yield format_sse_event(build_langchain_stream_event(event))
                continue

            # Default passthrough for any other event
            yield format_sse_event(build_langchain_stream_event(event))

        stream_handler.emit_done()
        yield format_sse_event(StreamEvent(event="done", data={}))

    except Exception as e:
        stream_handler.emit_error(str(e))
        yield format_sse_event(StreamEvent(event="error", data={"error": str(e)}))
