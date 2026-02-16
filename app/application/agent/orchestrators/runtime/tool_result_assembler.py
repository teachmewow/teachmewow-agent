"""
Assemble tool results from tool start/end events.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AssembledToolResult:
    run_id: str
    tool_call_id: str
    name: str
    output: str


class ToolResultAssembler:
    def __init__(self) -> None:
        self._starts_by_run_id: dict[str, tuple[str, str]] = {}

    def register_start(self, run_id: str, tool_name: str, tool_call_id: str) -> None:
        self._starts_by_run_id[run_id] = (tool_name, tool_call_id)

    def complete(self, run_id: str, output: object) -> AssembledToolResult:
        if run_id not in self._starts_by_run_id:
            raise RuntimeError(
                f"ToolResultAssembler: missing tool start for run_id={run_id}"
            )
        name, tool_call_id = self._starts_by_run_id.pop(run_id)
        if isinstance(output, dict) and "content" in output:
            output = output.get("content", "")
        elif hasattr(output, "content"):
            output = getattr(output, "content", "")
        return AssembledToolResult(
            run_id=run_id,
            tool_call_id=tool_call_id,
            name=name,
            output=str(output),
        )
