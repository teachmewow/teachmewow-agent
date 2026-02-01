"""
Entry node for the knowledge explorer flow.
"""

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_stream_writer

from app.application.agent.state_schema import AgentState


class ExplorerEntryNode:
    def __init__(self, content: str) -> None:
        self.content = content

    async def __call__(
        self, state: AgentState, config: RunnableConfig | None = None
    ) -> AgentState:
        if isinstance(state, list):
            ai_message = state[-1]
        elif state.messages:
            ai_message = state.messages[-1]
        else:
            raise ValueError(f"No messages found in state {state}")

        tool_calls = list(getattr(ai_message, "tool_calls", []) or [])
        if not tool_calls:
            raise ValueError("No tool calls found for explorer entry.")

        tool_call = None
        for call in tool_calls:
            call_name = call.get("name") if isinstance(call, dict) else call.name
            if call_name == "run_wow_knowledge_explorer":
                tool_call = call
                break
        if tool_call is None:
            tool_call = tool_calls[0]
        tool_call_id = (
            tool_call.get("id") if isinstance(tool_call, dict) else tool_call.id
        )
        tool_call_name = (
            tool_call.get("name") if isinstance(tool_call, dict) else tool_call.name
        )
        stream_writer = get_stream_writer()
        stream_writer(
            {
                "kind": "tool_result",
                "data": {
                    "tool_call_id": tool_call_id,
                    "content": self.content,
                    "is_error": False,
                },
            }
        )

        return {
            "messages": [
                ToolMessage(
                    content=self.content,
                    name=tool_call_name,
                    tool_call_id=tool_call_id,
                )
            ]
        }
