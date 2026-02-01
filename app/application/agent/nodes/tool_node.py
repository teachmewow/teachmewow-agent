from __future__ import annotations

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode as BaseToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest


class ToolNode(BaseToolNode):
    def __init__(self, tools: list[BaseTool]) -> None:
        super().__init__(tools, awrap_tool_call=self._awrap_tool_call)

    async def _awrap_tool_call(
        self, request: ToolCallRequest, execute
    ) -> ToolMessage:
        updated_request = self._inject_context(request)
        result = await execute(updated_request)
        if isinstance(result, ToolMessage) and request.tool_call["name"] == "build_lookup":
            if getattr(result, "status", None) != "error":
                stream_writer = getattr(request.runtime, "stream_writer", None)
                if stream_writer:
                    stream_writer(
                        {
                            "kind": "tool_result",
                            "data": {
                                "tool_call_id": request.tool_call["id"],
                                "tool_name": request.tool_call["name"],
                                "content": result.content,
                                "is_error": False,
                            },
                        }
                    )
            result.content = (
                'Build recuperada, mande o usuario olhar para o que esta em "View Result".'
            )
        return result

    def _inject_context(self, request: ToolCallRequest) -> ToolCallRequest:
        args = request.tool_call.get("args")
        if not isinstance(args, dict):
            return request

        tool = request.tool
        fields = {}
        args_schema = getattr(tool, "args_schema", None) if tool else None
        if args_schema is not None and hasattr(args_schema, "model_fields"):
            fields = args_schema.model_fields

        state = request.state
        values = {
            "wow_class": state.get("wow_class")
            if isinstance(state, dict)
            else getattr(state, "wow_class", None),
            "wow_spec": state.get("wow_spec")
            if isinstance(state, dict)
            else getattr(state, "wow_spec", None),
            "wow_role": state.get("wow_role")
            if isinstance(state, dict)
            else getattr(state, "wow_role", None),
        }

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