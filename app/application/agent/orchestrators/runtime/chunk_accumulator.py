"""
Chunk accumulation state for streamed LLM responses.
"""

from __future__ import annotations

from dataclasses import dataclass

from .content_normalizer import normalize_text_content


@dataclass
class ChunkAccumulator:
    full_response: str = ""
    chunk_buffer: str = ""
    llm_event_context: dict | None = None

    def append(self, *, content: object, event_context: dict) -> str:
        normalized = normalize_text_content(content)
        if not normalized:
            return ""
        self.full_response += normalized
        self.chunk_buffer += normalized
        self.llm_event_context = event_context
        return normalized

    def consume_buffer(self) -> str:
        content = self.chunk_buffer
        self.chunk_buffer = ""
        return content
