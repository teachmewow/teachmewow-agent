"""
Recommendation request/response schemas.
"""

from pydantic import BaseModel, Field

from .chat import CharInfoRequest


class RecommendationRequest(BaseModel):
    """Request body for POST /agent/recommendations."""

    assistant_message: str = Field(..., description="Last AI response text")
    char_info: CharInfoRequest = Field(..., description="Character context")
    active_build_id: str | None = Field(
        default=None, description="Currently selected build ID"
    )


class Recommendation(BaseModel):
    """A single follow-up question suggestion."""

    text: str = Field(..., description="The suggested follow-up question")
    skill_hint: str | None = Field(
        default=None, description="Suggested skill name, if applicable"
    )


class RecommendationResponse(BaseModel):
    """Response body for POST /agent/recommendations."""

    recommendations: list[Recommendation]
