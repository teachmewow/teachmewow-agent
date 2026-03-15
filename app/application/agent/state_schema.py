"""
Agent state schema — simplified for the skills-based orchestrator.
"""

from pydantic import BaseModel, Field


class CharInfo(BaseModel):
    """Strongly-typed character context injected by the frontend."""

    wow_class: str = Field(..., alias="class")
    spec: str
    role: str

    model_config = {"populate_by_name": True}


class BuildInfo(BaseModel):
    """Persisted build context shared across turns."""

    build_id: str
    import_code: str
    wow_class: str
    spec: str
    decoded_nodes: list[str] = Field(default_factory=list)
    hero_talent: str | None = None
    environment: str | None = None
    scenario: str | None = None
    source: str | None = None
    patch: str | None = None


class StreamEvent(BaseModel):
    """
    Event emitted during streaming.
    Used to communicate with the frontend via SSE.
    """

    event: str
    data: dict = Field(default_factory=dict)
