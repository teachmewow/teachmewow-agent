from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode as BaseToolNode


class ToolNode(BaseToolNode):
    def __init__(self, tools: list[BaseTool]) -> None:
        super().__init__(tools, awrap_tool_call=self._awrap_tool_call)

    async def _awrap_tool_call(
        self, request: Any, execute
    ):
        updated_request = self._inject_context(request)
        return await execute(updated_request)

    def _inject_context(self, request: Any) -> Any:
        args = request.tool_call.get("args")
        if not isinstance(args, dict):
            return request

        tool = request.tool
        fields = {}
        args_schema = getattr(tool, "args_schema", None) if tool else None
        if args_schema is not None and hasattr(args_schema, "model_fields"):
            fields = args_schema.model_fields

        state = request.state
        char_info = (
            state.get("char_info")
            if isinstance(state, dict)
            else getattr(state, "char_info", None)
        )
        if char_info is None:
            values: dict[str, Any] = {}
        elif isinstance(char_info, dict):
            values = {"char_info": char_info}
        else:
            values = {
                "char_info": {
                    "class": getattr(char_info, "wow_class", ""),
                    "spec": getattr(char_info, "spec", ""),
                    "role": getattr(char_info, "role", ""),
                }
            }

        thread_id = state.get("thread_id") if isinstance(state, dict) else getattr(state, "thread_id", None)
        active_build_id = (
            state.get("active_build_id")
            if isinstance(state, dict)
            else getattr(state, "active_build_id", None)
        )
        if thread_id:
            values["thread_id"] = thread_id
        if active_build_id:
            values["active_build_id"] = active_build_id

        injected_args = dict(args)
        for key, value in values.items():
            if not value:
                continue
            if key in fields or key in injected_args:
                injected_args[key] = value

        if injected_args == args:
            return request

        updated_call = {**request.tool_call, "args": injected_args}
        return request.override(tool_call=updated_call)