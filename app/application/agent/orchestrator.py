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
    ) -> None:
        self._provider = provider
        self._model = model
        self._tools_config = tools_config
        self._tool_registry = tool_registry
        self._reasoning_effort = reasoning_effort

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
        """
        Run the orchestrator loop, yielding SSE event strings.
        """
        tool_executor = ToolExecutor(
            registry=self._tool_registry,
            char_info=char_info,
            build_info=build_info,
        )

        input_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        max_iterations = 15
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                accumulated_text = ""
                output_items: list[Any] = []

                # Track streaming fn calls: item_id -> args_buffer
                streaming_fn_calls: dict[str, dict] = {}

                response = await self._provider.create_response(
                    model=self._model,
                    input=input_messages,
                    tools=self._tools_config,
                    stream=True,
                    reasoning_effort=self._reasoning_effort,
                )

                async for event in response:
                    match event:
                        # -- text delta tokens --
                        case ResponseTextDeltaEvent(delta=delta) if delta:
                            accumulated_text += delta
                            yield _sse("token", {"text": delta})

                        # -- function call arguments streaming --
                        case ResponseFunctionCallArgumentsDeltaEvent(
                            item_id=item_id, delta=delta,
                        ) if item_id in streaming_fn_calls:
                            streaming_fn_calls[item_id]["args"] += delta

                        # -- output item added (function_call start) --
                        case ResponseOutputItemAddedEvent(item=item) if isinstance(
                            item, ResponseFunctionToolCall
                        ):
                            streaming_fn_calls[item.id] = {
                                "name": item.name,
                                "args": "",
                            }
                            yield _sse("tool_call", {
                                "name": item.name,
                                "call_id": item.id,
                            })

                        # -- output item done (complete item) --
                        case ResponseOutputItemDoneEvent(item=item):
                            output_items.append(item)

                        # -- web search events --
                        case ResponseWebSearchCallInProgressEvent() | ResponseWebSearchCallSearchingEvent():
                            yield _sse("web_search", {"status": "searching"})
                        case ResponseWebSearchCallCompletedEvent():
                            yield _sse("web_search", {"status": "completed"})

                        # -- shell / skill events (string-based fallback) --
                        case _ if _is_shell_event(event, "in_progress"):
                            yield _sse("skill_active", {"status": "running"})
                        case _ if _is_shell_event(event, "completed"):
                            yield _sse("skill_active", {"status": "completed"})

                # -- Finished streaming this response turn --

                function_calls = [
                    item for item in output_items
                    if isinstance(item, ResponseFunctionToolCall)
                ]

                if not function_calls:
                    annotations = _extract_annotations(output_items)
                    if annotations:
                        yield _sse("annotations", {"citations": annotations})
                    yield _sse("done", {"text": accumulated_text})
                    return

                # Execute function calls
                for fc in function_calls:
                    args = json.loads(fc.arguments) if fc.arguments else {}

                    result = await tool_executor.execute(fc.name, args)
                    _maybe_update_build_context(result, tool_executor)

                    # SSE uses item id (same as tool_call event)
                    # Send full result for list_builds (frontend needs it for cards)
                    sse_result = result if fc.name == "list_builds" else result[:500]
                    yield _sse("tool_result", {
                        "name": fc.name,
                        "call_id": fc.id,
                        "result": sse_result,
                    })

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

            yield _sse("error", {"message": "Max tool iterations reached."})

        except Exception as exc:
            traceback.print_exc()
            yield _sse("error", {"message": str(exc)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    payload = json.dumps({"event": event, "data": data}, ensure_ascii=True)
    return f"data: {payload}\n\n"


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
