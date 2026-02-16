"""
Build StreamEvent payloads from accumulated chunks.
"""

from __future__ import annotations

from app.application.agent.state_schema import StreamEvent
from app.application.agent.streaming import build_langchain_stream_event

from .chunk_accumulator import ChunkAccumulator


class ChunkFlusher:
    def flush_to_event(self, accumulator: ChunkAccumulator) -> StreamEvent | None:
        buffered = accumulator.consume_buffer()
        if not buffered:
            return None

        if accumulator.llm_event_context:
            return build_langchain_stream_event(
                accumulator.llm_event_context,
                data_override={"chunk": {"content": buffered}},
            )

        return StreamEvent(
            event="on_chat_model_stream",
            data={"payload": {"chunk": {"content": buffered}}},
        )
