"""
SSE Orchestrator for managing graph execution and streaming with debouncing.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from app.application.agent.state_schema import AgentState, StreamEvent
from app.application.agent.streaming import (
    build_langchain_stream_event,
    format_sse_event,
)

from .observers.base import StreamObserver
from .runtime import (
    ChunkAccumulator,
    ChunkFlusher,
    Debouncer,
    EmitPipeline,
    MapStage,
    NodeMessageTracker,
    NotifyStage,
    ObserverNotifierFacade,
    PreFlushStage,
    SerializeStage,
)
from .strategies import (
    DefaultPassThroughStrategy,
    StreamEventStrategy,
    create_default_strategy_registry,
)


# Debounce interval for LLM chunks (in seconds)
DEBOUNCE_INTERVAL_MS = 50
DEBOUNCE_INTERVAL_S = DEBOUNCE_INTERVAL_MS / 1000
logger = logging.getLogger(__name__)


@dataclass
class _RuntimeState:
    accumulator: ChunkAccumulator
    tracker: NodeMessageTracker
    last_flush_time: float


class SSEOrchestrator:
    """
    Orchestrates graph execution with SSE streaming and debouncing.

    Features:
    - Debouncing of 50ms for LLM chunks to optimize network usage
    - Bypass (immediate delivery) for tool call/result events
    - Observer pattern for extensible side effects (e.g., DB persistence)
    """

    def __init__(self, graph: CompiledStateGraph):
        """
        Initialize the SSE orchestrator.

        Args:
            graph: Compiled LangGraph agent
        """
        self.graph = graph
        self._notifier = ObserverNotifierFacade()
        self._debouncer = Debouncer(interval_s=DEBOUNCE_INTERVAL_S, now_fn=self._now)
        self._flusher = ChunkFlusher()
        self._default_strategy: StreamEventStrategy = DefaultPassThroughStrategy()
        self._event_strategies = create_default_strategy_registry()

    def add_observer(self, observer: StreamObserver) -> None:
        """
        Add an observer to receive stream events.

        Args:
            observer: Observer implementing StreamObserver protocol
        """
        self._notifier.add(observer)

    def remove_observer(self, observer: StreamObserver) -> None:
        """
        Remove an observer.

        Args:
            observer: Observer to remove
        """
        self._notifier.remove(observer)

    async def stream(self, state: AgentState) -> AsyncGenerator[str, None]:
        """
        Execute the graph and stream SSE events with debouncing.

        LLM chunks are debounced at 50ms intervals to optimize network.
        Tool events are delivered immediately (bypass debounce).

        Args:
            state: Initial agent state

        Yields:
            SSE-formatted event strings
        """
        runtime_state = _RuntimeState(
            accumulator=ChunkAccumulator(),
            tracker=NodeMessageTracker(state.messages),
            last_flush_time=self._now(),
        )
        emit_pipeline = self._build_emit_pipeline(runtime_state)

        try:
            async for event in self.graph.astream_events(state, version="v2"):
                event_kind = str(event.get("event") or "")
                raw_event_data = event.get("data", {})
                event_data = raw_event_data if isinstance(raw_event_data, dict) else {}
                event_name = str(event.get("name") or "")
                strategy = self._event_strategies.get(event_kind, self._default_strategy)
                emitted = await strategy.handle(
                    event=event,
                    event_kind=event_kind,
                    event_data=event_data,
                    event_name=event_name,
                    stream_state=runtime_state,
                    actions=self,
                )
                for sse in emitted:
                    yield sse

            # Flush any remaining chunks in buffer
            flush_sse = await self._flush_accumulator(runtime_state, emit_pipeline)
            if flush_sse:
                yield flush_sse

            # Notify observers that streaming is complete
            await self._notifier.notify_complete(runtime_state.accumulator.full_response)

            # Emit done event
            done_event = StreamEvent(
                event="done", data={"payload": {"finish_reason": "done"}}
            )
            emitted_done = await emit_pipeline.emit(done_event, flush_before=False)
            for sse in emitted_done:
                yield sse

        except Exception as e:
            logger.exception(
                "SSE stream failed: thread_id=%s user_id=%s error=%s",
                state.thread_id,
                state.user_id,
                e,
            )
            # Notify observers of error
            await self._notifier.notify_error(e)

            # Emit error event
            error_event = StreamEvent(event="error", data={"payload": {"error": str(e)}})
            yield format_sse_event(error_event)

    def _now(self) -> float:
        return asyncio.get_event_loop().time()

    async def _process_llm_stream_chunk(
        self, event: dict, event_data: dict, runtime_state: _RuntimeState
    ) -> list[str]:
        chunk = event_data.get("chunk")
        if not (chunk and hasattr(chunk, "content") and chunk.content):
            return []

        runtime_state.accumulator.append(content=chunk.content, event_context=event)

        if not self._debouncer.should_flush(runtime_state.last_flush_time):
            return []

        emit_pipeline = self._build_emit_pipeline(runtime_state)
        flushed = await self._flush_accumulator(runtime_state, emit_pipeline)
        return [flushed] if flushed else []

    async def _emit_tool_result(self, event: dict, event_data: dict) -> StreamEvent:
        output = event_data.get("output", "")
        if isinstance(output, dict) and "content" in output:
            output = output.get("content", "")
        elif hasattr(output, "content"):
            output = getattr(output, "content", "")
        if output is not event_data.get("output"):
            event = {**event, "data": {**event_data, "output": output}}
        return build_langchain_stream_event(event)

    async def _process_chain_end(
        self, event_data: dict, node: str, runtime_state: _RuntimeState
    ) -> None:
        new_messages = runtime_state.tracker.extract_new_messages(event_data)
        if new_messages:
            await self._notifier.notify_node_complete(node, new_messages)

    async def emit_generic_event(
        self, event: dict, stream_state: _RuntimeState, *, flush_before: bool = False
    ) -> list[str]:
        emit_pipeline = self._build_emit_pipeline(stream_state)
        stream_event = build_langchain_stream_event(event)
        return await emit_pipeline.emit(stream_event, flush_before=flush_before)

    async def emit_tool_start_event(
        self, event: dict, stream_state: _RuntimeState
    ) -> list[str]:
        emit_pipeline = self._build_emit_pipeline(stream_state)
        stream_event = build_langchain_stream_event(event)
        return await emit_pipeline.emit(stream_event, flush_before=True)

    async def emit_tool_end_event(
        self, event: dict, event_data: dict, stream_state: _RuntimeState
    ) -> list[str]:
        emit_pipeline = self._build_emit_pipeline(stream_state)
        stream_event = await self._emit_tool_result(event, event_data)
        return await emit_pipeline.emit(stream_event, flush_before=False)

    async def process_llm_stream_chunk(
        self, event: dict, event_data: dict, stream_state: _RuntimeState
    ) -> list[str]:
        return await self._process_llm_stream_chunk(event, event_data, stream_state)

    async def process_chain_end(
        self, event_data: dict, node: str, stream_state: _RuntimeState
    ) -> None:
        await self._process_chain_end(event_data, node, stream_state)

    def _build_emit_pipeline(self, runtime_state: _RuntimeState) -> EmitPipeline:
        return EmitPipeline(
            pre_flush_stage=PreFlushStage(
                flush_fn=lambda: self._flush_accumulator(
                    runtime_state, pipeline=None
                )
            ),
            map_stage=MapStage(mapper=self._map_stream_event),
            notify_stage=NotifyStage(notify_fn=self._notifier.notify_event),
            serialize_stage=SerializeStage(serializer=format_sse_event),
        )

    def _map_stream_event(self, stream_event: StreamEvent) -> StreamEvent:
        return stream_event

    async def _flush_accumulator(
        self, runtime_state: _RuntimeState, pipeline: EmitPipeline | None
    ) -> str | None:
        stream_event = self._flusher.flush_to_event(runtime_state.accumulator)
        if stream_event is None:
            return None

        runtime_state.last_flush_time = self._debouncer.mark_flushed()
        active_pipeline = pipeline or self._build_emit_pipeline(runtime_state)
        emitted = await active_pipeline.emit(stream_event, flush_before=False)
        if not emitted:
            return None
        return emitted[-1]
