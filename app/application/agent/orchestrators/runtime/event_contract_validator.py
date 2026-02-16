"""
Strict runtime contract validation for LangGraph stream events.
"""

from __future__ import annotations


class EventContractViolationError(RuntimeError):
    """Raised when an event violates the expected streaming contract."""


class EventContractValidator:
    def validate(self, event: dict) -> None:
        event_kind = str(event["event"])
        event_data = event.get("data")
        if not isinstance(event_data, dict):
            raise EventContractViolationError(
                f"{event_kind}: expected data to be a dict"
            )

        if event_kind == "on_chat_model_stream":
            run_id = event.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise EventContractViolationError(
                    "on_chat_model_stream: missing run_id"
                )
            chunk = event_data.get("chunk")
            if chunk is None or not hasattr(chunk, "content"):
                raise EventContractViolationError(
                    "on_chat_model_stream: missing chunk.content"
                )
            return

        if event_kind == "on_chat_model_end":
            run_id = event.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise EventContractViolationError("on_chat_model_end: missing run_id")
            output = event_data.get("output")
            if output is None:
                raise EventContractViolationError(
                    "on_chat_model_end: missing output payload"
                )
            return

        if event_kind == "on_tool_start":
            run_id = event.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise EventContractViolationError("on_tool_start: missing run_id")
            name = event.get("name")
            if not isinstance(name, str) or not name:
                raise EventContractViolationError("on_tool_start: missing tool name")
            return

        if event_kind == "on_tool_end":
            run_id = event.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise EventContractViolationError("on_tool_end: missing run_id")
            if "output" not in event_data:
                raise EventContractViolationError("on_tool_end: missing output")
            return
