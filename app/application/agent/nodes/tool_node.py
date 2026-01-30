import json

from langgraph.config import get_stream_writer
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from app.application.agent.state_schema import AgentState
from app.domain.entities.message import ToolCall


class ToolNode:
    def __init__(self, tools: list[BaseTool]) -> None:
        self.all_tools_by_name = {tool.name: tool for tool in tools}

    async def __call__(self, state: AgentState, config: RunnableConfig | None = None) -> AgentState:
        """Call the tools with the current state."""
        stream_writer = get_stream_writer()
        
        tool_calls = self._get_tool_calls(state)

        for tool_call in tool_calls:
            tool_call_dict = {
                "tool_name": tool_call.name, 
                "arguments": tool_call.arguments, 
                "tool_call_id": tool_call.id
            }
            stream_writer(
                {
                    "kind": "tool_call", 
                    "data": tool_call_dict
                }
            )

        outputs = []
        for tool_call in tool_calls:
            tool_result = await self._run_tool(tool_call, state, stream_writer)
            outputs.append(tool_result)
        
        return {"messages": outputs}

    def _get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        """Get the tool calls from the state."""
        messages = state.messages
        if not messages:
            raise ValueError("No messages found in input state")
        last_message = messages[-1]
        raw_calls = list(getattr(last_message, "tool_calls", []) or [])
        return [self._normalize_tool_call(call) for call in raw_calls]

    def _normalize_tool_call(self, tool_call: object) -> ToolCall:
        """Normalize tool call into ToolCall dataclass."""
        if isinstance(tool_call, ToolCall):
            return tool_call
        if isinstance(tool_call, dict):
            call_id = tool_call.get("id", "")
            name = tool_call.get("name", "")
            args = tool_call.get("args", {})
            return ToolCall(
                id=call_id,
                name=name,
                arguments=json.dumps(args),
            )
        call_id = getattr(tool_call, "id", "")
        name = getattr(tool_call, "name", "")
        args = getattr(tool_call, "args", {})
        return ToolCall(
            id=call_id,
            name=name,
            arguments=json.dumps(args),
        )

    async def _run_tool(self, tool_call: ToolCall, state: AgentState, stream_writer) -> ToolMessage:
        """Run the tool and return the result."""
        try:
            injected_args = self._inject_context(tool_call.arguments, state)
            tool_result = await self.all_tools_by_name[tool_call.name].arun(injected_args)
            stream_writer(
                {
                    "kind": "tool_result", 
                    "data": {
                        "tool_call_id": tool_call.id, 
                        "content": tool_result, 
                        "is_error": False
                    }
                }
            )
            return ToolMessage(
                content=tool_result,
                name=tool_call.name,
                tool_call_id=tool_call.id
            )
        except Exception as e:
            error_message = f"Error calling tool {tool_call.name}: {e}"
            stream_writer(
                {
                    "kind": "tool_result", 
                    "data": {
                        "tool_call_id": tool_call.id, 
                        "content": error_message, 
                        "is_error": True
                    }
                }
            )
            return ToolMessage(
                content=error_message,
                name=tool_call.name,
                tool_call_id=tool_call.id
            )

    def _inject_context(self, arguments: str, state: AgentState) -> str:
        """Inject class/spec/role into tool call arguments."""
        try:
            parsed = json.loads(arguments) if arguments else {}
        except json.JSONDecodeError:
            return arguments

        if not isinstance(parsed, dict):
            return arguments

        parsed.setdefault("wow_class", state.wow_class)
        parsed.setdefault("wow_spec", state.wow_spec)
        parsed.setdefault("wow_role", state.wow_role)
        return json.dumps(parsed)