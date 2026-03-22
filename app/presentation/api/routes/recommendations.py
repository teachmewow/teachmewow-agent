"""
Recommendation route — generates follow-up question suggestions.
"""

from fastapi import APIRouter

from app.presentation.api.dependencies import RecommendationServiceDep
from app.presentation.schemas.recommendation import (
    Recommendation,
    RecommendationRequest,
    RecommendationResponse,
)

router = APIRouter(prefix="/agent", tags=["recommendations"])


@router.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    service: RecommendationServiceDep,
) -> RecommendationResponse:
    """Generate follow-up question suggestions based on conversation context."""
    raw = await service.generate(
        assistant_message=request.assistant_message,
        char_info={
            "wow_class": request.char_info.wow_class,
            "spec": request.char_info.spec,
            "role": request.char_info.role,
        },
        active_build_id=request.active_build_id,
    )
    return RecommendationResponse(
        recommendations=[Recommendation(**r) for r in raw],
    )
