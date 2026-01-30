"""
Pydantic schemas for thread API requests and responses.
"""

from pydantic import BaseModel, Field


class ThreadResponse(BaseModel):
    """Response schema for a thread."""

    id: str
    user_id: str
    wow_class: str
    wow_spec: str
    wow_role: str
    title: str | None = None
    created_at: str
    updated_at: str


class CreateThreadRequest(BaseModel):
    """Request schema for creating a thread."""

    thread_id: str = Field(..., description="ID for the new thread (format: uuid_userId)")
    user_id: str = Field(..., description="ID of the user")
    wow_class: str = Field(..., alias="class", description="WoW class context")
    spec: str = Field(..., description="WoW specialization context")
    role: str = Field(..., description="WoW role context")
    title: str | None = Field(default=None, description="Optional title")

    class Config:
        populate_by_name = True
