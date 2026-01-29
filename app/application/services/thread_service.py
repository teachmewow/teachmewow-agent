"""
Thread service - manages conversation threads.
"""

from app.domain import Message, Thread
from app.domain.repositories import MessageRepository, ThreadRepository


class ThreadService:
    """
    Service for managing conversation threads.
    """

    def __init__(
        self,
        message_repository: MessageRepository,
        thread_repository: ThreadRepository,
    ):
        """
        Initialize the thread service.

        Args:
            message_repository: Repository for message persistence
            thread_repository: Repository for thread persistence
        """
        self.message_repository = message_repository
        self.thread_repository = thread_repository

    async def get_thread(self, thread_id: str) -> Thread | None:
        """
        Get a thread by ID.

        Args:
            thread_id: The thread ID

        Returns:
            The thread if found, None otherwise
        """
        return await self.thread_repository.get_by_id(thread_id)

    async def get_thread_messages(
        self, thread_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Message]:
        """
        Get all messages for a thread.

        Args:
            thread_id: The thread ID
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of messages ordered by timestamp
        """
        return await self.message_repository.get_by_thread_id(
            thread_id, limit=limit, offset=offset
        )

    async def get_user_threads(
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
        return await self.thread_repository.get_by_user_id(
            user_id, limit=limit, offset=offset
        )

    async def delete_thread(self, thread_id: str) -> bool:
        """
        Delete a thread and all its messages.

        Args:
            thread_id: The thread ID

        Returns:
            True if deleted, False if not found
        """
        # Delete messages first (cascade should handle this, but explicit is better)
        await self.message_repository.delete_by_thread_id(thread_id)
        return await self.thread_repository.delete(thread_id)


def create_thread_service(
    message_repository: MessageRepository,
    thread_repository: ThreadRepository,
) -> ThreadService:
    """
    Create a new ThreadService instance.

    Args:
        message_repository: Repository for messages
        thread_repository: Repository for threads

    Returns:
        Configured ThreadService
    """
    return ThreadService(
        message_repository=message_repository,
        thread_repository=thread_repository,
    )
