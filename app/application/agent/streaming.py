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
    """Build a compact StreamEvent envelope for frontend rendering."""
    event_kind = str(event.get("event", ""))
    stream_event_name = _normalize_stream_event_name(
        event_kind=event_kind, event_name=str(event.get("name") or "")
    )
    payload = data_override if data_override is not None else event.get("data", {})
    compact_payload = _extract_relevant_payload(event_kind, payload)
    return StreamEvent(
        event=stream_event_name,
        data={
            "name": event.get("name"),
            "run_id": event.get("run_id"),
            "payload": _sanitize_for_json(compact_payload),
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


def _extract_relevant_payload(event_kind: str, payload: object) -> object:
    if not isinstance(payload, Mapping):
        return payload

    if event_kind == "on_chat_model_stream":
        chunk = payload.get("chunk")
        content = getattr(chunk, "content", None) if chunk is not None else None
        if isinstance(chunk, Mapping):
            content = chunk.get("content")
        return {"chunk": {"content": content or ""}}

    if event_kind == "on_tool_start":
        return {"input": payload.get("input", {})}

    if event_kind == "on_tool_end":
        return {"output": payload.get("output", "")}

    if event_kind in {"done", "error"}:
        return payload

    if event_kind == "on_custom_event":
        return payload

    return {}


def _normalize_stream_event_name(*, event_kind: str, event_name: str) -> str:
    if event_kind != "on_custom_event":
        return event_kind
    if event_name in {"plan_init", "plan_update"}:
        return event_name
    return event_kind
