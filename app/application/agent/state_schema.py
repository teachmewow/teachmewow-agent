"""
LangGraph state schema for the agent.
"""

from typing import Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """
    State schema for the LangGraph agent.

    This state is isolated per execution - each graph.stream() call
    creates its own state instance.

    Attributes:
        messages: Conversation history (uses add_messages reducer)
        thread_id: ID of the conversation thread
        user_id: ID of the user
        wow_class: Optional WoW class context
        wow_spec: Optional WoW spec context
        wow_role: Optional WoW role context (tank, healer, dps)
    """

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    thread_id: str | None = None
    user_id: str | None = None
    wow_class: str | None = None
    wow_spec: str | None = None
    wow_role: str | None = None

    class Config:
        arbitrary_types_allowed = True


class StreamEvent(BaseModel):
    """
    Event emitted during streaming.
    Used to communicate with the frontend via SSE.
    """

    kind: Literal[
        "llm_delta",
        "tool_call",
        "tool_result",
        "node_started",
        "node_finished",
        "done",
        "error",
    ]
    data: dict = Field(default_factory=dict)
