"""
Database observer for persisting messages during streaming.
"""

import uuid
from datetime import datetime, timezone

from app.application.agent.state_schema import StreamEvent
from app.domain import Message, MessageRole
from app.domain.repositories import MessageRepository


class DatabaseObserver:
    """
    Observer that persists AI messages to the database.

    This observer listens to stream events and saves the AI response
    to the database when the stream completes.
    """

    def __init__(
        self,
        message_repository: MessageRepository,
        thread_id: str,
    ):
        """
        Initialize the database observer.

        Args:
            message_repository: Repository for message persistence
            thread_id: ID of the conversation thread
        """
        self.message_repository = message_repository
        self.thread_id = thread_id

    async def on_event(self, event: StreamEvent) -> None:
        """
        Called when a stream event is processed.

        Currently a no-op - we wait for the complete response.
        Future enhancement: could save tool calls/results as they happen.

        Args:
            event: The stream event that was processed
        """
        # For now, we don't do anything on individual events
        # Could be extended to save tool calls/results in real-time
        pass

    async def on_stream_complete(self, full_response: str) -> None:
        """
        Called when the stream is complete.

        Saves the AI response to the database.

        Args:
            full_response: The complete accumulated response text
        """
        if not full_response:
            return

        ai_message = Message(
            id=str(uuid.uuid4()),
            thread_id=self.thread_id,
            role=MessageRole.AI,
            content=full_response,
            timestamp=datetime.now(timezone.utc),
        )
        await self.message_repository.save(ai_message)

    async def on_error(self, error: Exception) -> None:
        """
        Called when an error occurs during streaming.

        Could be extended to log errors or save partial responses.

        Args:
            error: The exception that occurred
        """
        # Could log the error or save partial response
        pass
