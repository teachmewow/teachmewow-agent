from __future__ import annotations

import inspect
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
        accepted_args: set[str] = set()
        args_schema = getattr(tool, "args_schema", None) if tool else None
        if args_schema is not None and hasattr(args_schema, "model_fields"):
            accepted_args.update(args_schema.model_fields.keys())
        if tool is not None:
            for attr in ("func", "coroutine"):
                callable_obj = getattr(tool, attr, None)
                if callable(callable_obj):
                    accepted_args.update(inspect.signature(callable_obj).parameters.keys())

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
        build_info = (
            state.get("build_info")
            if isinstance(state, dict)
            else getattr(state, "build_info", None)
        )
        if build_info is None:
            serialized_build_info: dict[str, Any] | None = None
        elif isinstance(build_info, dict):
            serialized_build_info = build_info
        else:
            serialized_build_info = {
                "build_id": getattr(build_info, "build_id", ""),
                "import_code": getattr(build_info, "import_code", ""),
                "wow_class": getattr(build_info, "wow_class", ""),
                "spec": getattr(build_info, "spec", ""),
                "decoded_nodes": list(getattr(build_info, "decoded_nodes", []) or []),
                "hero_talent": getattr(build_info, "hero_talent", None),
                "environment": getattr(build_info, "environment", None),
                "scenario": getattr(build_info, "scenario", None),
                "source": getattr(build_info, "source", None),
                "patch": getattr(build_info, "patch", None),
            }
        if not active_build_id and serialized_build_info:
            active_build_id = str(serialized_build_info.get("build_id") or "") or None
        if thread_id:
            values["thread_id"] = thread_id
        if active_build_id:
            values["active_build_id"] = active_build_id
        if serialized_build_info:
            values["build_info"] = serialized_build_info

        injected_args = dict(args)
        for key, value in values.items():
            if not value:
                continue
            if key in accepted_args or key in injected_args:
                injected_args[key] = value

        if injected_args == args:
            return request

        updated_call = {**request.tool_call, "args": injected_args}
        return request.override(tool_call=updated_call)
