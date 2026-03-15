"""
Tool registry — maps tool names to typed handlers with a Pydantic context.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import BaseModel


class ToolContext(BaseModel):
    """Shared context passed to every tool handler."""

    char_info: dict | None = None
    build_info: dict | None = None


class ToolHandler(Protocol):
    """Interface every tool handler must satisfy."""

    name: str
    schema: dict[str, Any]

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> str: ...


class ToolRegistry:
    """Registry of tool handlers, keyed by name."""

    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, handler: ToolHandler) -> None:
        self._handlers[handler.name] = handler

    def get(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolContext) -> str:
        handler = self._handlers.get(name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        return await handler.execute(args, ctx)

    def schemas(self) -> list[dict[str, Any]]:
        return [h.schema for h in self._handlers.values()]
