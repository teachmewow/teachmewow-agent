"""
Streaming utilities for adapting LangGraph events to SSE format.
"""

import json
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
        """Emit an LLM token delta event."""
        self.emit(
            StreamEvent(
                kind="llm_delta",
                data={"content": content, "message_id": message_id},
            )
        )

    def emit_tool_call(
        self, tool_call_id: str, tool_name: str, arguments: str
    ) -> None:
        """Emit a tool call event."""
        self.emit(
            StreamEvent(
                kind="tool_call",
                data={
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
            )
        )

    def emit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Emit a tool result event."""
        self.emit(
            StreamEvent(
                kind="tool_result",
                data={"tool_call_id": tool_call_id, "result": result},
            )
        )

    def emit_node_started(self, node_name: str) -> None:
        """Emit a node started event."""
        self.emit(
            StreamEvent(
                kind="node_started",
                data={"node": node_name},
            )
        )

    def emit_node_finished(self, node_name: str) -> None:
        """Emit a node finished event."""
        self.emit(
            StreamEvent(
                kind="node_finished",
                data={"node": node_name},
            )
        )

    def emit_done(self) -> None:
        """Emit a done event."""
        self.emit(StreamEvent(kind="done", data={}))

    def emit_error(self, error: str) -> None:
        """Emit an error event."""
        self.emit(StreamEvent(kind="error", data={"error": error}))

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
    data = json.dumps({"kind": event.kind, **event.data})
    return f"event: {event.kind}\ndata: {data}\n\n"


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
    try:
        # Stream the graph execution
        async for event in graph.astream_events(state, version="v2"):
            event_kind = event.get("event")
            event_data = event.get("data", {})
            event_name = event.get("name", "")

            # Handle different event types
            if event_kind == "on_chat_model_stream":
                # LLM token streaming
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    stream_handler.emit_llm_delta(chunk.content)
                    yield format_sse_event(
                        StreamEvent(kind="llm_delta", data={"content": chunk.content})
                    )

            elif event_kind == "on_tool_start":
                # Tool execution started
                tool_input = event_data.get("input", {})
                stream_handler.emit_tool_call(
                    tool_call_id=event.get("run_id", ""),
                    tool_name=event_name,
                    arguments=json.dumps(tool_input),
                )
                yield format_sse_event(
                    StreamEvent(
                        kind="tool_call",
                        data={
                            "tool_call_id": event.get("run_id", ""),
                            "tool_name": event_name,
                            "arguments": json.dumps(tool_input),
                        },
                    )
                )

            elif event_kind == "on_tool_end":
                # Tool execution finished
                output = event_data.get("output", "")
                stream_handler.emit_tool_result(
                    tool_call_id=event.get("run_id", ""),
                    result=str(output),
                )
                yield format_sse_event(
                    StreamEvent(
                        kind="tool_result",
                        data={
                            "tool_call_id": event.get("run_id", ""),
                            "result": str(output),
                        },
                    )
                )

            elif event_kind == "on_chain_start" and event_name:
                stream_handler.emit_node_started(event_name)

            elif event_kind == "on_chain_end" and event_name:
                stream_handler.emit_node_finished(event_name)

        # Emit done event
        stream_handler.emit_done()
        yield format_sse_event(StreamEvent(kind="done", data={}))

    except Exception as e:
        stream_handler.emit_error(str(e))
        yield format_sse_event(StreamEvent(kind="error", data={"error": str(e)}))
