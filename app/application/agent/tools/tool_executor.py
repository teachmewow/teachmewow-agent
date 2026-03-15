"""
Tool executor — dispatches function-tool calls from the Responses API
to the correct Python handler.
"""

from __future__ import annotations

import json
from typing import Any


class ToolExecutor:
    """
    Maps function-tool names to handlers and executes them.

    Each handler receives ``**kwargs`` parsed from the tool-call arguments
    and returns a JSON string.
    """

    def __init__(
        self,
        *,
        char_info: dict | None = None,
        build_info: dict | None = None,
    ) -> None:
        self._char_info = char_info
        self._build_info = build_info

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Route a function call to its handler and return the result string."""
        if tool_name == "list_builds":
            return await self._exec_list_builds(arguments)

        if tool_name == "build_lookup":
            return await self._exec_build_lookup(arguments)

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # -- delegates --------------------------------------------------------

    async def _exec_list_builds(self, args: dict) -> str:
        from app.application.agent.tools.list_builds import execute_list_builds

        return await execute_list_builds(
            environment=args.get("environment"),
            mode=args.get("mode"),
            hero_talent=args.get("hero_talent"),
            limit=args.get("limit", 10),
            char_info=self._char_info,
        )

    async def _exec_build_lookup(self, args: dict) -> str:
        from app.application.agent.tools.build_lookup import execute_build_lookup

        return await execute_build_lookup(
            build_id=args.get("build_id", ""),
            char_info=self._char_info,
        )

    # -- context update ---------------------------------------------------

    def update_context(
        self,
        *,
        char_info: dict | None = None,
        build_info: dict | None = None,
    ) -> None:
        if char_info is not None:
            self._char_info = char_info
        if build_info is not None:
            self._build_info = build_info
