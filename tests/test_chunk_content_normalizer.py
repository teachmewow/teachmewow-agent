from app.application.agent.orchestrators.runtime import ChunkAccumulator
from app.application.agent.orchestrators.runtime.content_normalizer import (
    normalize_text_content,
)


def test_normalize_text_content_from_plain_string() -> None:
    assert normalize_text_content("hello") == "hello"


def test_normalize_text_content_from_empty_list_content() -> None:
    payload = {"content": []}
    assert normalize_text_content(payload) == ""


def test_normalize_text_content_from_block_list() -> None:
    payload = {
        "content": [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": {"value": " world"}},
        ]
    }
    assert normalize_text_content(payload) == "Hello world"


def test_normalize_text_content_prefers_text_attr() -> None:
    class _Chunk:
        content = [{"type": "text", "text": "ignored"}]

        @property
        def text(self) -> str:
            return "preferred"

    assert normalize_text_content(_Chunk()) == "preferred"


def test_chunk_accumulator_ignores_non_text_chunks_without_crash() -> None:
    accumulator = ChunkAccumulator()
    appended = accumulator.append(content=[], event_context={"event": "on_chat_model_stream"})
    assert appended == ""
    assert accumulator.full_response == ""
    assert accumulator.chunk_buffer == ""

