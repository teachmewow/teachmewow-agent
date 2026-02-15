"""
LangGraph state schema for the agent.
"""

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class CharInfo(BaseModel):
    """Strongly-typed character context injected by the frontend."""

    wow_class: str = Field(..., alias="class")
    spec: str
    role: str

    class Config:
        populate_by_name = True

class AgentState(BaseModel):
    """
    State schema for the LangGraph agent.

    This state is isolated per execution - each graph.stream() call
    creates its own state instance.

    Attributes:
        messages: Conversation history (uses add_messages reducer)
        thread_id: ID of the conversation thread (format: uuid_userId)
        user_id: ID of the user
        char_info: WoW class/spec/role context (required)
        active_build_id: Current selected build ID in the thread context.
        candidate_build_ids: Candidate build IDs used for disambiguation.
    """

    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    thread_id: str
    user_id: str
    char_info: CharInfo
    active_build_id: str | None = None
    candidate_build_ids: list[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True


class StreamEvent(BaseModel):
    """
    Event emitted during streaming.
    Used to communicate with the frontend via SSE.

    Minimal envelope for frontend SSE.
    """

    event: str
    data: dict = Field(default_factory=dict)
