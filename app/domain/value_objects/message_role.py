"""
Message role enum for chat messages.
"""

from enum import StrEnum


class MessageRole(StrEnum):
    """Role of a message in a conversation."""

    HUMAN = "human"
    AI = "ai"
    SYSTEM = "system"
    TOOL = "tool"
