"""
Base observer interface for the SSE orchestrator.
"""

from typing import Protocol

from app.application.agent.state_schema import StreamEvent


class StreamObserver(Protocol):
    """
    Observer interface for stream events.

    Observers are notified of each event processed by the SSE orchestrator.
    This allows for side effects like database persistence, logging, etc.
    without coupling the orchestrator to specific implementations.
    """

    async def on_event(self, event: StreamEvent) -> None:
        """
        Called when a stream event is processed.

        Args:
            event: The stream event that was processed
        """
        ...

    async def on_stream_complete(self, full_response: str) -> None:
        """
        Called when the stream is complete.

        Args:
            full_response: The complete accumulated response text
        """
        ...

    async def on_error(self, error: Exception) -> None:
        """
        Called when an error occurs during streaming.

        Args:
            error: The exception that occurred
        """
        ...
