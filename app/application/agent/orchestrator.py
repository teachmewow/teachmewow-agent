"""
Orchestrator — drives the agent loop using the OpenAI Responses API.

Replaces the entire LangGraph pipeline with a simple tool-call loop:

    orchestrator <-> tools -> done

Yields SSE-formatted events for the FastAPI streaming response.
"""

from __future__ import annotations

import json
import traceback
from collections.abc import AsyncGenerator
from typing import Any

from langsmith import traceable
from openai import APIStatusError, APITimeoutError
from openai.types.responses import (
    ResponseFunctionCallArgumentsDeltaEvent,
    ResponseFunctionToolCall,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseTextDeltaEvent,
    ResponseWebSearchCallCompletedEvent,
    ResponseWebSearchCallInProgressEvent,
    ResponseWebSearchCallSearchingEvent,
)
from openai.types.responses.response_output_text import AnnotationURLCitation

from app.infrastructure.llm.provider import LLMProvider

from .sse_events import (
    AnnotationsEvent,
    DoneEvent,
    ErrorEvent,
    SkillActiveEvent,
    SSEEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    WebSearchEvent,
)
from .tools.registry import ToolRegistry
from .tools.tool_executor import ToolExecutor


class Orchestrator:
    """
    Stateless orchestrator — one instance is shared across requests.

    Skills are mounted on OpenAI's side via shell tool (local mode)
    with skill_reference. The model discovers and follows them autonomously.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        tools_config: list[dict[str, Any]],
        tool_registry: ToolRegistry,
        reasoning_effort: str = "none",
        skill_contents: list[dict[str, str]] | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._tools_config = tools_config
        self._tool_registry = tool_registry
        self._reasoning_effort = reasoning_effort
        self.skill_contents = skill_contents or []

    @traceable(
        run_type="chain",
        name="orchestrator",
        reduce_fn=lambda chunks: {"sse_events": len(chunks)},
    )
    async def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        system_prompt: str,
        char_info: dict | None = None,
        build_info: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """Run the orchestrator loop, yielding SSE event strings."""
        tool_executor = ToolExecutor(
            registry=self._tool_registry,
            char_info=char_info,
            build_info=build_info,
        )

        input_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        try:
            for _ in range(15):
                acc = _StreamAccumulator()

                response = await self._provider.create_response(
                    model=self._model,
                    input=input_messages,
                    tools=self._tools_config,
                    stream=True,
                    reasoning_effort=self._reasoning_effort,
                )

                async for event in response:
                    if sse := acc.handle_event(event):
                        yield sse.to_sse()

                if not acc.function_calls:
                    if annotations := _extract_annotations(acc.output_items):
                        yield AnnotationsEvent(citations=annotations).to_sse()
                    yield DoneEvent(text=acc.accumulated_text).to_sse()
                    return

                async for sse in self._execute_tools(
                    acc.function_calls, tool_executor, input_messages,
                ):
                    yield sse.to_sse()

            yield ErrorEvent(
                code="MAX_ITERATIONS",
                message="Max tool iterations reached.",
            ).to_sse()

        except Exception as exc:
            traceback.print_exc()
            code, message = _classify_error(exc)
            yield ErrorEvent(code=code, message=message).to_sse()

    async def _execute_tools(
        self,
        function_calls: list[ResponseFunctionToolCall],
        tool_executor: ToolExecutor,
        input_messages: list[dict[str, Any]],
    ) -> AsyncGenerator[SSEEvent, None]:
        """Execute function calls and yield SSE events for each result."""
        for fc in function_calls:
            args = json.loads(fc.arguments) if fc.arguments else {}

            is_error = False
            try:
                result = await tool_executor.execute(fc.name, args)
                _maybe_update_build_context(result, tool_executor)
            except Exception as tool_exc:
                result = json.dumps({"error": str(tool_exc)})
                is_error = True

            # Send full result for list_builds (frontend needs it for cards)
            sse_result = result if fc.name == "list_builds" else result[:500]
            yield ToolResultEvent(
                name=fc.name,
                call_id=fc.id,
                result=sse_result,
                is_error=is_error,
            )

            # Responses API uses call_id for matching
            input_messages.append({
                "type": "function_call",
                "call_id": fc.call_id,
                "name": fc.name,
                "arguments": fc.arguments,
            })
            input_messages.append({
                "type": "function_call_output",
                "call_id": fc.call_id,
                "output": result,
            })


# ---------------------------------------------------------------------------
# Stream accumulator — tracks state for one API response turn
# ---------------------------------------------------------------------------

class _StreamAccumulator:
    """Maps OpenAI SDK events to typed SSE events while tracking iteration state."""

    def __init__(self) -> None:
        self.accumulated_text: str = ""
        self.output_items: list[Any] = []
        self.streaming_fn_calls: dict[str, dict] = {}

    def handle_event(self, event: object) -> SSEEvent | None:
        """Process one SDK event; return an SSE event to yield, or None."""
        match event:
            # -- text delta tokens --
            case ResponseTextDeltaEvent(delta=delta) if delta:
                self.accumulated_text += delta
                return TokenEvent(text=delta)

            # -- function call arguments streaming --
            case ResponseFunctionCallArgumentsDeltaEvent(
                item_id=item_id, delta=delta,
            ) if item_id in self.streaming_fn_calls:
                self.streaming_fn_calls[item_id]["args"] += delta
                return None

            # -- output item added (function_call start) --
            case ResponseOutputItemAddedEvent(item=item) if isinstance(
                item, ResponseFunctionToolCall,
            ):
                self.streaming_fn_calls[item.id] = {
                    "name": item.name,
                    "args": "",
                }
                return ToolCallEvent(name=item.name, call_id=item.id)

            # -- output item done (complete item) --
            case ResponseOutputItemDoneEvent(item=item):
                self.output_items.append(item)
                return None

            # -- web search events --
            case ResponseWebSearchCallInProgressEvent() | ResponseWebSearchCallSearchingEvent():
                return WebSearchEvent(status="searching")
            case ResponseWebSearchCallCompletedEvent():
                return WebSearchEvent(status="completed")

            # -- shell / skill events (string-based fallback) --
            case _ if _is_shell_event(event, "in_progress"):
                return SkillActiveEvent(status="running")
            case _ if _is_shell_event(event, "completed"):
                return SkillActiveEvent(status="completed")

            case _:
                return None

    @property
    def function_calls(self) -> list[ResponseFunctionToolCall]:
        return [
            item for item in self.output_items
            if isinstance(item, ResponseFunctionToolCall)
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify_error(exc: Exception) -> tuple[str, str]:
    """Classify an exception into a semantic error code + raw message.

    The frontend uses the code to render a localised message via i18n.
    """
    msg = str(exc)
    if isinstance(exc, APITimeoutError):
        return "TIMEOUT", msg
    if isinstance(exc, APIStatusError):
        status = exc.status_code
        if status == 429:
            return "RATE_LIMITED", msg
        if status in (500, 502, 503):
            return "SERVICE_UNAVAILABLE", msg
    return "UNKNOWN", msg


def _is_shell_event(event: object, suffix: str) -> bool:
    """Check for shell_call events that don't have dedicated SDK types."""
    etype = getattr(event, "type", "")
    return isinstance(etype, str) and "shell_call" in etype and etype.endswith(suffix)


def _extract_annotations(output_items: list[Any]) -> list[dict]:
    annotations: list[dict] = []
    for item in output_items:
        if not isinstance(item, ResponseOutputMessage):
            continue
        for block in item.content:
            for ann in getattr(block, "annotations", []):
                if isinstance(ann, AnnotationURLCitation):
                    annotations.append({
                        "start_index": ann.start_index,
                        "end_index": ann.end_index,
                        "url": ann.url,
                        "title": ann.title,
                    })
    return annotations


def _maybe_update_build_context(result: str, executor: ToolExecutor) -> None:
    try:
        data = json.loads(result)
        bi = data.get("build_info")
        if isinstance(bi, dict) and bi.get("build_id"):
            executor.update_context(build_info=bi)
    except (json.JSONDecodeError, AttributeError):
        pass
