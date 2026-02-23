import json
from collections.abc import AsyncGenerator

import pytest

from app.application.agent.orchestrators.observers.base import StreamObserver
from app.application.agent.orchestrators.sse_orchestrator import SSEOrchestrator
from app.application.agent.state_schema import AgentState, CharInfo, StreamEvent


class _Chunk:
    def __init__(self, content: object):
        self.content = content


class _FakeGraph:
    async def astream_events(
        self, state: AgentState, version: str = "v2"
    ) -> AsyncGenerator[dict, None]:
        assert version == "v2"
        # Hidden router classifier output: must never reach user stream or persistence.
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "run_id": "run-router",
            "metadata": {"langgraph_node": "router"},
            "data": {"chunk": _Chunk('{"route":"coach","reason":"hidden"}')},
        }
        yield {
            "event": "on_chat_model_end",
            "name": "ChatOpenAI",
            "run_id": "run-router",
            "metadata": {"langgraph_node": "router"},
            "data": {"output": {"content": '{"route":"coach","reason":"hidden"}'}},
        }

        # User-visible assistant output from the agent node.
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatOpenAI",
            "run_id": "run-agent",
            "metadata": {"langgraph_node": "agent"},
            "data": {"chunk": _Chunk("Hello")},
        }
        yield {
            "event": "on_chat_model_end",
            "name": "ChatOpenAI",
            "run_id": "run-agent",
            "metadata": {"langgraph_node": "agent"},
            "data": {
                "output": {
                    "content": "Hello",
                    "tool_calls": [],
                    "response_metadata": {},
                }
            },
        }


class _EventCollector(StreamObserver):
    def __init__(self) -> None:
        self.events: list[StreamEvent] = []
        self.completed: str | None = None
        self.error: Exception | None = None

    async def on_event(self, event: StreamEvent) -> None:
        self.events.append(event)

    async def on_node_complete(self, node: str, messages: list) -> None:
        return None

    async def on_stream_complete(self, full_response: str) -> None:
        self.completed = full_response

    async def on_error(self, error: Exception) -> None:
        self.error = error


@pytest.mark.asyncio
async def test_orchestrator_filters_hidden_llm_nodes_from_stream_and_persistence() -> None:
    orchestrator = SSEOrchestrator(_FakeGraph())  # type: ignore[arg-type]
    observer = _EventCollector()
    orchestrator.add_observer(observer)

    state = AgentState(
        messages=[],
        thread_id="t-filter",
        user_id="u-filter",
        char_info=CharInfo(**{"class": "warrior", "spec": "arms", "role": "dps"}),
    )
    chunks = [chunk async for chunk in orchestrator.stream(state)]
    full_sse = "".join(chunks)

    assert '{"route":"coach","reason":"hidden"}' not in full_sse
    assert full_sse.count("event: on_chat_model_stream") == 1
    assert "Hello" in full_sse
    assert "event: done" in full_sse

    persisted_ai = [event for event in observer.events if event.event == "persist_ai_message"]
    assert len(persisted_ai) == 1
    assert persisted_ai[0].data["content"] == "Hello"

    payloads = [json.dumps(event.data) for event in persisted_ai]
    assert all("hidden" not in payload for payload in payloads)
    assert observer.error is None
    assert observer.completed == "Hello"

