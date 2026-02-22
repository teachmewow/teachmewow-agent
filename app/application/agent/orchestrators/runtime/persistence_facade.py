"""
Facade for event-driven persistence message assembly.
"""

from __future__ import annotations

from app.application.agent.state_schema import StreamEvent

from .ai_message_assembler import AIMessageAssembler
from .tool_result_assembler import ToolResultAssembler


class PersistenceFacade:
    def __init__(self) -> None:
        self._ai = AIMessageAssembler()
        self._tool = ToolResultAssembler()
        self._pending_tool_calls: list[dict[str, object]] = []

    def on_chat_model_stream(self, event: dict, event_data: dict) -> None:
        run_id = str(event["run_id"])
        chunk = event_data["chunk"]
        content = self._read_content(chunk)
        self._ai.append_delta(run_id=run_id, content=content)

    def on_chat_model_end(self, event: dict, event_data: dict) -> StreamEvent:
        run_id = str(event["run_id"])
        output = event_data["output"]
        final_content = self._read_content(output)
        tool_calls = self._read_tool_calls(output)
        response_metadata = self._read_response_metadata(output)
        self._pending_tool_calls = list(tool_calls)
        assembled = self._ai.complete(run_id=run_id, final_content=final_content)
        return StreamEvent(
            event="persist_ai_message",
            data={
                "run_id": assembled.run_id,
                "content": assembled.content,
                "is_partial": assembled.is_partial,
                "tool_calls": tool_calls,
                "response_metadata": response_metadata,
            },
        )

    def on_tool_start(self, event: dict, event_data: dict) -> None:
        run_id = str(event["run_id"])
        tool_name = str(event["name"])
        tool_call_id = self._resolve_tool_call_id(event_data=event_data, tool_name=tool_name)
        self._tool.register_start(
            run_id=run_id, tool_name=tool_name, tool_call_id=tool_call_id
        )

    def on_tool_end(self, event: dict, event_data: dict) -> StreamEvent:
        run_id = str(event["run_id"])
        assembled = self._tool.complete(run_id=run_id, output=event_data["output"])
        return StreamEvent(
            event="persist_tool_message",
            data={
                "run_id": assembled.run_id,
                "tool_call_id": assembled.tool_call_id,
                "name": assembled.name,
                "output": assembled.output,
            },
        )

    def on_error(self) -> list[StreamEvent]:
        partial_events: list[StreamEvent] = []
        for partial in self._ai.flush_partials():
            partial_events.append(
                StreamEvent(
                    event="persist_ai_message",
                    data={
                        "run_id": partial.run_id,
                        "content": partial.content,
                        "is_partial": True,
                    },
                )
            )
        return partial_events

    def assert_no_pending(self) -> None:
        if self._ai.has_pending():
            raise RuntimeError(
                "PersistenceFacade: stream finished with pending AI buffers"
            )

    def _read_content(self, payload: object) -> str:
        if hasattr(payload, "content"):
            return str(payload.content)
        if isinstance(payload, dict) and "content" in payload:
            return str(payload["content"])
        raise RuntimeError("PersistenceFacade: payload missing content")

    def _read_tool_calls(self, payload: object) -> list[dict[str, object]]:
        tool_calls: object = []
        if hasattr(payload, "tool_calls"):
            tool_calls = payload.tool_calls
        elif isinstance(payload, dict):
            tool_calls = payload.get("tool_calls", [])
        if not isinstance(tool_calls, list):
            raise RuntimeError("PersistenceFacade: output.tool_calls must be a list")

        normalized: list[dict[str, object]] = []
        for item in tool_calls:
            if not isinstance(item, dict):
                raise RuntimeError("PersistenceFacade: tool call must be a dict")
            tool_call_id = str(item["id"])
            tool_name = str(item["name"])
            tool_args = item.get("args", {})
            normalized.append({"id": tool_call_id, "name": tool_name, "args": tool_args})
        return normalized

    def _read_response_metadata(self, payload: object) -> dict | None:
        metadata: object = None
        if hasattr(payload, "response_metadata"):
            metadata = payload.response_metadata
        elif isinstance(payload, dict):
            metadata = payload.get("response_metadata")
        if not isinstance(metadata, dict):
            return None
        return metadata

    def _resolve_tool_call_id(self, *, event_data: dict, tool_name: str) -> str:
        if "tool_call_id" in event_data:
            return str(event_data["tool_call_id"])

        for idx, pending in enumerate(self._pending_tool_calls):
            if str(pending["name"]) == tool_name:
                matched = self._pending_tool_calls.pop(idx)
                return str(matched["id"])

        raise RuntimeError(
            f"PersistenceFacade: missing tool_call_id mapping for tool '{tool_name}'"
        )
