"""
Message entity representing a chat message.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.value_objects import MessageRole


def _utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


@dataclass
class ToolCall:
    """Represents a tool call made by the AI."""

    id: str
    name: str
    arguments: str


@dataclass
class Message:
    """
    Message entity representing a single message in a conversation thread.

    Attributes:
        id: Unique identifier for the message
        thread_id: ID of the thread this message belongs to
        role: Role of the message sender (human, ai, system, tool)
        content: Text content of the message
        timestamp: When the message was created
        tool_calls: List of tool calls (for AI messages)
        tool_call_id: ID of the tool call this message responds to (for tool messages)
        tool_result: Result of a tool execution (for tool messages)
        reasoning: AI reasoning/thinking (if exposed)
        token_count: Number of tokens in the message
    """

    id: str
    thread_id: str
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=_utc_now)
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    tool_result: str | None = None
    reasoning: str | None = None
    token_count: int | None = None

    def is_human(self) -> bool:
        """Check if message is from a human."""
        return self.role == MessageRole.HUMAN

    def is_ai(self) -> bool:
        """Check if message is from AI."""
        return self.role == MessageRole.AI

    def is_tool(self) -> bool:
        """Check if message is a tool response."""
        return self.role == MessageRole.TOOL

    def has_tool_calls(self) -> bool:
        """Check if message contains tool calls."""
        return self.tool_calls is not None and len(self.tool_calls) > 0
