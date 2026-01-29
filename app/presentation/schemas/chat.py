"""
Pydantic schemas for chat API requests and responses.
"""

from pydantic import BaseModel, Field


class SendMessageRequest(BaseModel):
    """Request schema for sending a message."""

    input: str = Field(..., description="The user's message text")
    thread_id: str = Field(..., description="ID of the conversation thread")
    user_id: str = Field(..., description="ID of the user")
    graph_id: str = Field(default="agent", description="ID of the graph to use")
    streaming: bool = Field(default=True, description="Whether to stream the response")

    # Optional WoW context
    wow_class: str | None = Field(
        default=None, alias="class", description="WoW class context"
    )
    spec: str | None = Field(default=None, description="WoW specialization context")
    role: str | None = Field(default=None, description="WoW role context (tank/healer/dps)")

    class Config:
        populate_by_name = True


class MessageResponse(BaseModel):
    """Response schema for a single message."""

    id: str
    thread_id: str
    role: str
    content: str
    timestamp: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    tool_result: str | None = None
    reasoning: str | None = None
    token_count: int | None = None
