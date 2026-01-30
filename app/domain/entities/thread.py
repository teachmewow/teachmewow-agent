"""
Thread entity representing a conversation thread.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.value_objects import WowClass, WowSpec


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


@dataclass
class Thread:
    """
    Thread entity representing a conversation thread.

    Attributes:
        id: Unique identifier for the thread (format: uuid_userId)
        user_id: ID of the user who owns this thread
        wow_class: WoW class context for the conversation (required)
        wow_spec: WoW spec context for the conversation (required)
        wow_role: Role (tank, healer, dps) context (required)
        title: Optional title for the thread
        created_at: When the thread was created
        updated_at: When the thread was last updated
    """

    id: str
    user_id: str
    wow_class: WowClass
    wow_spec: WowSpec
    wow_role: str
    title: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def get_context_summary(self) -> str:
        """Get a summary of the WoW context."""
        return f"Spec: {self.wow_spec.value}, Class: {self.wow_class.value}, Role: {self.wow_role}"
