"""
Tool executor — dispatches function-tool calls via the ToolRegistry.
"""

from __future__ import annotations

from typing import Any

from langsmith import traceable

from .registry import ToolContext, ToolRegistry


class ToolExecutor:
    """
    Dispatches function-tool calls through the ToolRegistry.
    """

    def __init__(
        self,
        *,
        registry: ToolRegistry,
        char_info: dict | None = None,
        build_info: dict | None = None,
    ) -> None:
        self._registry = registry
        self._ctx = ToolContext(char_info=char_info, build_info=build_info)

    @traceable(run_type="tool", name="tool_dispatch")
    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Route a function call to its handler and return the result string."""
        return await self._registry.execute(tool_name, arguments, self._ctx)

    def update_context(
        self,
        *,
        char_info: dict | None = None,
        build_info: dict | None = None,
    ) -> None:
        if char_info is not None:
            self._ctx.char_info = char_info
        if build_info is not None:
            self._ctx.build_info = build_info
