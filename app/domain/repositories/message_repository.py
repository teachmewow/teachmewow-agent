"""
Message repository interface.
"""

from typing import Protocol

from app.domain.entities import Message


class MessageRepository(Protocol):
    """
    Interface for message persistence operations.
    Implementations should handle database-specific logic.
    """

    async def save(self, message: Message) -> Message:
        """
        Save a message to the repository.

        Args:
            message: The message to save

        Returns:
            The saved message (may include generated fields like id)
        """
        ...

    async def save_many(self, messages: list[Message]) -> list[Message]:
        """
        Save multiple messages to the repository.

        Args:
            messages: List of messages to save

        Returns:
            List of saved messages
        """
        ...

    async def get_by_id(self, message_id: str) -> Message | None:
        """
        Get a message by its ID.

        Args:
            message_id: The message ID

        Returns:
            The message if found, None otherwise
        """
        ...

    async def get_by_thread_id(
        self, thread_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Message]:
        """
        Get all messages for a thread.

        Args:
            thread_id: The thread ID
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of messages ordered by timestamp ascending
        """
        ...

    async def delete_by_thread_id(self, thread_id: str) -> int:
        """
        Delete all messages in a thread.

        Args:
            thread_id: The thread ID

        Returns:
            Number of messages deleted
        """
        ...
