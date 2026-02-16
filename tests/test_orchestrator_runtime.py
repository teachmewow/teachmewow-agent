import sys
import types

sys.modules.setdefault("helix", types.ModuleType("helix"))

from langchain_core.messages import AIMessage, ToolMessage

from app.application.agent.state_schema import StreamEvent
from app.application.agent.orchestrators.runtime import (
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


def test_debouncer_should_flush_after_interval() -> None:
    timestamps = iter([10.0, 10.04, 10.06])
    debouncer = Debouncer(interval_s=0.05, now_fn=lambda: next(timestamps))

    assert debouncer.should_flush(10.0) is False
    assert debouncer.should_flush(10.0) is False
    assert debouncer.should_flush(10.0) is True


def test_chunk_flusher_builds_stream_event_from_context() -> None:
    accumulator = ChunkAccumulator()
    accumulator.append(
        content="hello",
        event_context={"event": "on_chat_model_stream", "name": "ChatOpenAI", "data": {}},
    )
    flusher = ChunkFlusher()

    event = flusher.flush_to_event(accumulator)

    assert event is not None
    assert event.event == "on_chat_model_stream"
    assert event.data.get("payload", {}).get("chunk", {}).get("content") == "hello"


def test_node_message_tracker_deduplicates_messages() -> None:
    initial_ai = AIMessage(content="init", id="ai-1")
    tracker = NodeMessageTracker([initial_ai])

    new_ai = AIMessage(content="new", id="ai-2")
    duplicate_ai = AIMessage(content="init", id="ai-1")
    event_data = {"output": {"messages": [initial_ai, new_ai, duplicate_ai]}}

    first = tracker.extract_new_messages(event_data)
    second = tracker.extract_new_messages(event_data)

    assert len(first) == 1
    assert getattr(first[0], "id", "") == "ai-2"
    assert second == []


async def test_emit_pipeline_runs_stages_in_order() -> None:
    notifier = ObserverNotifierFacade()
    observed: list[StreamEvent] = []

    class _Observer:
        async def on_event(self, event: StreamEvent) -> None:
            observed.append(event)

        async def on_node_complete(self, node: str, messages: list) -> None:
            return None

        async def on_stream_complete(self, full_response: str) -> None:
            return None

        async def on_error(self, error: Exception) -> None:
            return None

    notifier.add(_Observer())
    preflush_called = {"count": 0}

    async def flush_fn() -> str | None:
        preflush_called["count"] += 1
        return "event: on_chat_model_stream\ndata: {}\n\n"

    pipeline = EmitPipeline(
        pre_flush_stage=PreFlushStage(flush_fn=flush_fn),
        map_stage=MapStage(mapper=lambda event: event),
        notify_stage=NotifyStage(notify_fn=notifier.notify_event),
        serialize_stage=SerializeStage(
            serializer=lambda event: f"event: {event.event}\ndata: {event.data}\n\n"
        ),
    )

    event = StreamEvent(event="done", data={"payload": {"finish_reason": "done"}})
    emitted = await pipeline.emit(event, flush_before=True)

    assert preflush_called["count"] == 1
    assert len(observed) == 1
    assert observed[0].event == "done"
    assert len(emitted) == 2


def test_node_message_tracker_handles_tool_message_key() -> None:
    initial = ToolMessage(content="x", tool_call_id="call-1")
    tracker = NodeMessageTracker([initial])
    event_data = {"messages": [ToolMessage(content="x", tool_call_id="call-1")]}

    assert tracker.extract_new_messages(event_data) == []
