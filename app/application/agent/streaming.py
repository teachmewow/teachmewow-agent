"""
Streaming utilities for adapting LangGraph events to SSE format.
"""

import json
from collections.abc import Mapping

from .state_schema import StreamEvent


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
            "data": event.data,
        }
    )
    return f"event: {event.event}\ndata: {data}\n\n"


def build_langchain_stream_event(
    event: dict, data_override: dict | None = None
) -> StreamEvent:
    """Build a StreamEvent envelope from a LangChain astream_events payload."""
    payload = data_override if data_override is not None else event.get("data", {})
    return StreamEvent(
        event=event.get("event", ""),
        data={
            "name": event.get("name"),
            "run_id": event.get("run_id"),
            "parent_ids": event.get("parent_ids") or [],
            "metadata": event.get("metadata") or {},
            "tags": event.get("tags") or [],
            "payload": _sanitize_for_json(payload),
        },
    )


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
