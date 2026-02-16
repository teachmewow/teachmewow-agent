import sys
import types

sys.modules.setdefault("helix", types.ModuleType("helix"))

from app.application.agent.state_schema import StreamEvent
from app.application.agent.orchestrators.runtime import (
    ChunkAccumulator,
    ChunkFlusher,
    Debouncer,
    EmitPipeline,
    EventContractValidator,
    MapStage,
    NotifyStage,
    ObserverNotifierFacade,
    PersistenceFacade,
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


def test_event_contract_validator_validates_stream_events() -> None:
    validator = EventContractValidator()

    class _Chunk:
        content = "delta"

    validator.validate(
        {
            "event": "on_chat_model_stream",
            "run_id": "run-1",
            "data": {"chunk": _Chunk()},
        }
    )


def test_persistence_facade_builds_ai_and_tool_events() -> None:
    facade = PersistenceFacade()

    class _Chunk:
        def __init__(self, content: str):
            self.content = content

    facade.on_chat_model_stream(
        {"event": "on_chat_model_stream", "run_id": "run-ai"},
        {"chunk": _Chunk("hel")},
    )
    facade.on_chat_model_stream(
        {"event": "on_chat_model_stream", "run_id": "run-ai"},
        {"chunk": _Chunk("lo")},
    )
    ai_event = facade.on_chat_model_end(
        {"event": "on_chat_model_end", "run_id": "run-ai"},
        {
            "output": {
                "content": "hello",
                "tool_calls": [{"id": "call_x", "name": "x", "args": {}}],
            }
        },
    )
    assert ai_event.event == "persist_ai_message"
    assert ai_event.data["content"] == "hello"
    assert ai_event.data["tool_calls"][0]["id"] == "call_x"

    facade.on_tool_start(
        {"event": "on_tool_start", "run_id": "run-tool", "name": "x"},
        {"input": {}},
    )
    tool_event = facade.on_tool_end(
        {"event": "on_tool_end", "run_id": "run-tool"},
        {"output": "ok"},
    )
    assert tool_event.event == "persist_tool_message"
    assert tool_event.data["name"] == "x"
    assert tool_event.data["tool_call_id"] == "call_x"
