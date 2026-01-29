"""
Thread repository interface.
"""

from typing import Protocol

from app.domain.entities import Thread


class ThreadRepository(Protocol):
    """
    Interface for thread persistence operations.
    Implementations should handle database-specific logic.
    """

    async def save(self, thread: Thread) -> Thread:
        """
        Save a thread to the repository.

        Args:
            thread: The thread to save

        Returns:
            The saved thread
        """
        ...

    async def get_by_id(self, thread_id: str) -> Thread | None:
        """
        Get a thread by its ID.

        Args:
            thread_id: The thread ID

        Returns:
            The thread if found, None otherwise
        """
        ...

    async def get_by_user_id(
        self, user_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Thread]:
        """
        Get all threads for a user.

        Args:
            user_id: The user ID
            limit: Maximum number of threads to return
            offset: Number of threads to skip

        Returns:
            List of threads ordered by updated_at descending
        """
        ...

    async def update(self, thread: Thread) -> Thread:
        """
        Update an existing thread.

        Args:
            thread: The thread to update

        Returns:
            The updated thread
        """
        ...

    async def delete(self, thread_id: str) -> bool:
        """
        Delete a thread by ID.

        Args:
            thread_id: The thread ID

        Returns:
            True if deleted, False if not found
        """
        ...

    async def get_or_create(self, thread: Thread) -> tuple[Thread, bool]:
        """
        Get an existing thread or create a new one.

        Args:
            thread: The thread to get or create

        Returns:
            Tuple of (thread, created) where created is True if new
        """
        ...
