"""
Chain of responsibility for SSE emission.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.application.agent.state_schema import StreamEvent


@dataclass
class EmitContext:
    stream_event: StreamEvent
    flush_before: bool
    emitted: list[str]


class PreFlushStage:
    def __init__(self, flush_fn: Callable[[], Awaitable[str | None]]):
        self._flush_fn = flush_fn

    async def run(self, context: EmitContext) -> EmitContext:
        if not context.flush_before:
            return context
        flushed = await self._flush_fn()
        if flushed:
            context.emitted.append(flushed)
        return context


class MapStage:
    def __init__(self, mapper: Callable[[StreamEvent], StreamEvent]):
        self._mapper = mapper

    async def run(self, context: EmitContext) -> EmitContext:
        context.stream_event = self._mapper(context.stream_event)
        return context


class NotifyStage:
    def __init__(self, notify_fn: Callable[[StreamEvent], Awaitable[None]]):
        self._notify_fn = notify_fn

    async def run(self, context: EmitContext) -> EmitContext:
        await self._notify_fn(context.stream_event)
        return context


class SerializeStage:
    def __init__(self, serializer: Callable[[StreamEvent], str]):
        self._serializer = serializer

    async def run(self, context: EmitContext) -> EmitContext:
        context.emitted.append(self._serializer(context.stream_event))
        return context


class EmitPipeline:
    def __init__(
        self,
        *,
        pre_flush_stage: PreFlushStage,
        map_stage: MapStage,
        notify_stage: NotifyStage,
        serialize_stage: SerializeStage,
    ):
        self._stages = [pre_flush_stage, map_stage, notify_stage, serialize_stage]

    async def emit(self, stream_event: StreamEvent, *, flush_before: bool) -> list[str]:
        context = EmitContext(stream_event=stream_event, flush_before=flush_before, emitted=[])
        for stage in self._stages:
            context = await stage.run(context)
        return context.emitted
