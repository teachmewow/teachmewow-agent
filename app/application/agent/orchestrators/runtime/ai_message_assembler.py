"""
Assemble AI messages from stream deltas and end events.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AssembledAIMessage:
    run_id: str
    content: str
    is_partial: bool


class AIMessageAssembler:
    def __init__(self) -> None:
        self._buffers: dict[str, list[str]] = {}

    def append_delta(self, run_id: str, content: str) -> None:
        if run_id not in self._buffers:
            self._buffers[run_id] = []
        self._buffers[run_id].append(content)

    def complete(self, run_id: str, final_content: str | None = None) -> AssembledAIMessage:
        if run_id not in self._buffers:
            raise RuntimeError(
                f"AIMessageAssembler: missing stream start for run_id={run_id}"
            )
        buffered = "".join(self._buffers.pop(run_id))
        content = final_content if final_content is not None else buffered
        return AssembledAIMessage(run_id=run_id, content=content, is_partial=False)

    def flush_partials(self) -> list[AssembledAIMessage]:
        partials: list[AssembledAIMessage] = []
        for run_id, parts in self._buffers.items():
            content = "".join(parts)
            if not content:
                continue
            partials.append(
                AssembledAIMessage(run_id=run_id, content=content, is_partial=True)
            )
        self._buffers.clear()
        return partials

    def has_pending(self) -> bool:
        return bool(self._buffers)
