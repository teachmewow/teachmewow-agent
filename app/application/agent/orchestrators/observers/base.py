"""
Base observer interface for the SSE orchestrator.
"""

from typing import Protocol

from langchain_core.messages import BaseMessage

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

    async def on_node_complete(self, node: str, messages: list[BaseMessage]) -> None:
        """
        Called when a node completes and produces new messages.

        Args:
            node: The node name that completed
            messages: New messages produced by the node
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
