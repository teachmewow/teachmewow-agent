"""
User entity representing a user of the system.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """
    User entity representing a user.

    Attributes:
        id: Unique identifier for the user (UUID from frontend)
        created_at: When the user was first seen
    """

    id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
