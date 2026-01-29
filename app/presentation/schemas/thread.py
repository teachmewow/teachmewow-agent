"""
Pydantic schemas for thread API requests and responses.
"""

from pydantic import BaseModel, Field


class ThreadResponse(BaseModel):
    """Response schema for a thread."""

    id: str
    user_id: str
    title: str | None = None
    wow_class: str | None = None
    wow_spec: str | None = None
    wow_role: str | None = None
    created_at: str
    updated_at: str


class CreateThreadRequest(BaseModel):
    """Request schema for creating a thread."""

    thread_id: str = Field(..., description="ID for the new thread")
    user_id: str = Field(..., description="ID of the user")
    title: str | None = Field(default=None, description="Optional title")
    wow_class: str | None = Field(
        default=None, alias="class", description="WoW class context"
    )
    spec: str | None = Field(default=None, description="WoW specialization context")
    role: str | None = Field(default=None, description="WoW role context")

    class Config:
        populate_by_name = True
