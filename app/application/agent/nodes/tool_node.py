from langgraph.config import get_stream_writer
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from app.application.agent.state_schema import AgentState
from app.domain.entities.message import ToolCall


class ToolNode:
    def __init__(self, tools: list[BaseTool]) -> None:
        self.stream_writer = get_stream_writer()
        self.all_tools_by_name = {tool.name: tool for tool in tools}

    async def __call__(self, state: AgentState, config: dict) -> AgentState:
        """Call the tools with the current state."""
        
        tool_calls = self._get_tool_calls(state)

        for tool_call in tool_calls:
            tool_call_dict = {
                "tool_name": tool_call.name, 
                "arguments": tool_call.arguments, 
                "tool_call_id": tool_call.id
            }
            self.stream_writer(
                {
                    "kind": "tool_call", 
                    "data": tool_call_dict
                }
            )

        outputs = []
        for tool_call in tool_calls:
            tool_result = await self._run_tool(tool_call)
            outputs.append(tool_result)
        
        return {"messages": outputs}

    def _get_tool_calls(self, state: AgentState) -> list[ToolCall]:
        """Get the tool calls from the state."""
        if messages := state.get("messages", []):
            return messages.tool_calls
        else:
            raise ValueError("No messages found in input state")

    async def _run_tool(self, tool_call: ToolCall) -> ToolMessage:
        """Run the tool and return the result."""
        try:
            tool_result = await self.all_tools_by_name[tool_call.name].arun(tool_call.arguments)
            self.stream_writer(
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
            self.stream_writer(
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