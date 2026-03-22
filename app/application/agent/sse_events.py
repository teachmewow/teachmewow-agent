"""Typed SSE event models — one model per event in the streaming contract.

Each model maps to exactly one SSE event type sent to the frontend.
The base class provides `to_sse()` for wire-format serialization.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel


class SSEEvent(BaseModel):
    """Base for all SSE events. Subclasses define `event` as a Literal."""

    event: str

    def to_sse(self) -> str:
        """Serialize to SSE wire format: `data: {"event": ..., "data": ...}\n\n`."""
        payload = json.dumps(
            {"event": self.event, "data": self._data()},
            ensure_ascii=True,
        )
        return f"data: {payload}\n\n"

    def _data(self) -> dict[str, Any]:
        return self.model_dump(exclude={"event"})


class TokenEvent(SSEEvent):
    event: Literal["token"] = "token"
    text: str


class ToolCallEvent(SSEEvent):
    event: Literal["tool_call"] = "tool_call"
    name: str
    call_id: str


class ToolResultEvent(SSEEvent):
    event: Literal["tool_result"] = "tool_result"
    name: str
    call_id: str
    result: str
    is_error: bool = False


class WebSearchEvent(SSEEvent):
    event: Literal["web_search"] = "web_search"
    status: str


class SkillActiveEvent(SSEEvent):
    event: Literal["skill_active"] = "skill_active"
    status: str


class AnnotationsEvent(SSEEvent):
    event: Literal["annotations"] = "annotations"
    citations: list[dict[str, Any]]


class DoneEvent(SSEEvent):
    event: Literal["done"] = "done"
    text: str


class ErrorEvent(SSEEvent):
    event: Literal["error"] = "error"
    code: str
    message: str
