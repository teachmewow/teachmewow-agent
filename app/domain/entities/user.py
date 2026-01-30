"""
User entity representing a user of the system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


@dataclass
class User:
    """
    User entity representing a user.

    Attributes:
        id: Unique identifier for the user (UUID from frontend)
        created_at: When the user was first seen
    """

    id: str
    created_at: datetime = field(default_factory=_utc_now)
