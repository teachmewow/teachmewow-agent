"""
Observer facade for stream side effects.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from app.application.agent.state_schema import StreamEvent

from ..observers.base import StreamObserver


class ObserverNotifierFacade:
    def __init__(self) -> None:
        self._observers: list[StreamObserver] = []

    def add(self, observer: StreamObserver) -> None:
        self._observers.append(observer)

    def remove(self, observer: StreamObserver) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    async def notify_event(self, event: StreamEvent) -> None:
        for observer in self._observers:
            await observer.on_event(event)

    async def notify_node_complete(self, node: str, messages: list[BaseMessage]) -> None:
        for observer in self._observers:
            await observer.on_node_complete(node, messages)

    async def notify_complete(self, full_response: str) -> None:
        for observer in self._observers:
            await observer.on_stream_complete(full_response)

    async def notify_error(self, error: Exception) -> None:
        for observer in self._observers:
            await observer.on_error(error)
