"""
Thread entity representing a conversation thread.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.value_objects import WowClass, WowSpec


@dataclass
class Thread:
    """
    Thread entity representing a conversation thread.

    Attributes:
        id: Unique identifier for the thread
        user_id: ID of the user who owns this thread
        title: Optional title for the thread
        wow_class: Optional WoW class context for the conversation
        wow_spec: Optional WoW spec context for the conversation
        wow_role: Optional role (tank, healer, dps) context
        created_at: When the thread was created
        updated_at: When the thread was last updated
    """

    id: str
    user_id: str
    title: str | None = None
    wow_class: WowClass | None = None
    wow_spec: WowSpec | None = None
    wow_role: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def has_context(self) -> bool:
        """Check if thread has WoW context set."""
        return self.wow_class is not None or self.wow_spec is not None

    def get_context_summary(self) -> str:
        """Get a summary of the WoW context."""
        parts = []
        if self.wow_spec:
            parts.append(f"Spec: {self.wow_spec.value}")
        if self.wow_class:
            parts.append(f"Class: {self.wow_class.value}")
        if self.wow_role:
            parts.append(f"Role: {self.wow_role}")
        return ", ".join(parts) if parts else "No context"
