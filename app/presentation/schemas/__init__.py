"""
API schemas module.
"""

from .chat import MessageResponse, SendMessageRequest
from .recommendation import (
    Recommendation,
    RecommendationRequest,
    RecommendationResponse,
)
from .thread import CreateThreadRequest, ThreadResponse

__all__ = [
    "SendMessageRequest",
    "MessageResponse",
    "CreateThreadRequest",
    "ThreadResponse",
    "RecommendationRequest",
    "RecommendationResponse",
    "Recommendation",
]
