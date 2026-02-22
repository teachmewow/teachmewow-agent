import sys
import types

sys.modules.setdefault("helix", types.ModuleType("helix"))

import pytest

from app.application.agent.orchestrators.observers.db_observer import DatabaseObserver
from app.application.agent.orchestrators.runtime import (
    EventContractValidator,
    EventContractViolationError,
    PersistenceFacade,
)
from app.application.agent.state_schema import StreamEvent
from app.domain import MessageRole


class _InMemoryMessageRepository:
    def __init__(self) -> None:
        self.saved = []

    async def save(self, message):
        self.saved.append(message)
        return message

    async def get_by_id(self, message_id: str):
        for item in self.saved:
            if item.id == message_id:
                return item
        return None


class _InMemoryThreadRepository:
    def __init__(self) -> None:
        self.active_build_id = None
        self.active_build_info = None

    async def set_active_build_id(self, thread_id: str, build_id: str) -> None:
        self.active_build_id = build_id

    async def set_active_build_info(self, thread_id: str, active_build_info: dict | None) -> None:
        self.active_build_info = active_build_info


class _Chunk:
    def __init__(self, content: str):
        self.content = content


class _AIOutput:
    def __init__(self, content: str, tool_calls: list[dict[str, object]] | None = None):
        self.content = content
        self.tool_calls = tool_calls or []


def test_validator_rejects_missing_tool_end_output() -> None:
    validator = EventContractValidator()
    with pytest.raises(EventContractViolationError):
        validator.validate(
            {"event": "on_tool_end", "run_id": "run-1", "data": {}}
        )


def test_persistence_facade_produces_partial_event_on_error() -> None:
    facade = PersistenceFacade()
    facade.on_chat_model_stream(
        {"event": "on_chat_model_stream", "run_id": "run-err"},
        {"chunk": _Chunk("partial")},
    )

    partials = facade.on_error()
    assert len(partials) == 1
    assert partials[0].event == "persist_ai_message"
    assert partials[0].data["is_partial"] is True
    assert partials[0].data["content"] == "partial"


def test_persistence_facade_preserves_tool_call_ids_for_tool_messages() -> None:
    facade = PersistenceFacade()
    facade.on_chat_model_stream(
        {"event": "on_chat_model_stream", "run_id": "run-ai"},
        {"chunk": _Chunk("")},
    )
    ai_event = facade.on_chat_model_end(
        {"event": "on_chat_model_end", "run_id": "run-ai"},
        {
            "output": _AIOutput(
                content="",
                tool_calls=[
                    {"id": "call_123", "name": "list_builds", "args": {"x": 1}}
                ],
            )
        },
    )
    assert ai_event.data["tool_calls"][0]["id"] == "call_123"

    facade.on_tool_start(
        {"event": "on_tool_start", "run_id": "run-tool", "name": "list_builds"},
        {"input": {"x": 1}},
    )
    tool_event = facade.on_tool_end(
        {"event": "on_tool_end", "run_id": "run-tool"},
        {"output": '{"ok": true}'},
    )
    assert tool_event.data["tool_call_id"] == "call_123"


@pytest.mark.asyncio
async def test_database_observer_persists_internal_events() -> None:
    message_repo = _InMemoryMessageRepository()
    thread_repo = _InMemoryThreadRepository()
    observer = DatabaseObserver(
        message_repository=message_repo,
        thread_repository=thread_repo,
        thread_id="thread-1",
    )

    await observer.on_event(
        StreamEvent(
            event="persist_ai_message",
            data={
                "run_id": "run-ai",
                "content": "hello",
                "is_partial": False,
                "tool_calls": [{"id": "call_abc", "name": "build_lookup", "args": {}}],
                "response_metadata": {"citations": [{"citation_id": "source_1"}]},
            },
        )
    )
    await observer.on_event(
        StreamEvent(
            event="persist_tool_message",
            data={
                "run_id": "run-tool",
                "tool_call_id": "call_abc",
                "name": "build_lookup",
                "output": '{"tool":"build_lookup","build_id":"b-123"}',
            },
        )
    )

    assert len(message_repo.saved) == 2
    assert message_repo.saved[0].role == MessageRole.AI
    assert message_repo.saved[1].role == MessageRole.TOOL
    assert message_repo.saved[0].tool_calls is not None
    assert message_repo.saved[0].tool_calls[0].id == "call_abc"
    assert message_repo.saved[0].response_metadata == {
        "citations": [{"citation_id": "source_1"}]
    }
    assert message_repo.saved[1].tool_call_id == "call_abc"
    assert thread_repo.active_build_id == "b-123"
    assert thread_repo.active_build_info is not None
    assert thread_repo.active_build_info.get("build_id") == "b-123"
