"""
Chunk accumulation state for streamed LLM responses.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChunkAccumulator:
    full_response: str = ""
    chunk_buffer: str = ""
    llm_event_context: dict | None = None

    def append(self, *, content: str, event_context: dict) -> None:
        self.full_response += content
        self.chunk_buffer += content
        self.llm_event_context = event_context

    def consume_buffer(self) -> str:
        content = self.chunk_buffer
        self.chunk_buffer = ""
        return content
