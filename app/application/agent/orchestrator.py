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

from app.infrastructure.llm.provider import LLMProvider

from .tools.tool_executor import ToolExecutor


class Orchestrator:
    """
    Stateless orchestrator — one instance is shared across requests.
    Per-request state is passed via ``stream()``.

    Skills are mounted on OpenAI's side (via shell tool + skill_reference).
    The model discovers and follows them autonomously.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        tools_config: list[dict[str, Any]],
        skill_registry: Any = None,  # kept for compat, unused
    ) -> None:
        self._provider = provider
        self._model = model
        self._tools_config = tools_config

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
                output_items: list[dict] = []

                # Track streaming fn calls: item_id -> {name, args_buffer}
                streaming_fn_calls: dict[str, dict] = {}

                response = await self._provider.create_response(
                    model=self._model,
                    input=input_messages,
                    tools=self._tools_config,
                    stream=True,
                )

                async for event in response:
                    etype = getattr(event, "type", "")

                    # -- text delta tokens --
                    if etype == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            accumulated_text += delta
                            yield _sse("token", {"text": delta})

                    # -- function call arguments streaming --
                    elif etype == "response.function_call_arguments.delta":
                        item_id = getattr(event, "item_id", None)
                        delta = getattr(event, "delta", "")
                        if item_id and item_id in streaming_fn_calls:
                            streaming_fn_calls[item_id]["args"] += delta

                    # -- output item added (function_call start) --
                    elif etype == "response.output_item.added":
                        item = getattr(event, "item", None)
                        if item and getattr(item, "type", "") == "function_call":
                            item_id = getattr(item, "id", "")
                            fn_name = getattr(item, "name", "")
                            streaming_fn_calls[item_id] = {
                                "name": fn_name,
                                "args": "",
                            }
                            yield _sse("tool_call", {
                                "name": fn_name,
                                "call_id": item_id,
                            })

                    # -- output item done (complete item with all fields) --
                    elif etype == "response.output_item.done":
                        item = getattr(event, "item", None)
                        if item:
                            output_items.append(_item_to_dict(item))

                    # -- web search events --
                    elif etype == "response.web_search_call.in_progress":
                        yield _sse("web_search", {"status": "searching"})
                    elif etype == "response.web_search_call.completed":
                        yield _sse("web_search", {"status": "completed"})

                    # -- shell call events (skill activation via shell) --
                    elif etype == "response.shell_call.in_progress":
                        yield _sse("skill_active", {"status": "running"})
                    elif etype == "response.shell_call.completed":
                        yield _sse("skill_active", {"status": "completed"})

                # -- Finished streaming this response turn --

                function_calls = [
                    item for item in output_items
                    if item.get("type") == "function_call"
                ]

                if not function_calls:
                    annotations = _extract_annotations(output_items)
                    if annotations:
                        yield _sse("annotations", {"citations": annotations})
                    yield _sse("done", {"text": accumulated_text})
                    return

                # Execute function calls.
                # The Responses API uses `call_id` for function_call_output,
                # but the SSE `tool_call` event used `id` (item_id).
                # We need to map id -> call_id for the API, and use id
                # consistently in SSE events.
                for fc in function_calls:
                    item_id = fc.get("id", "")
                    api_call_id = fc.get("call_id", item_id)
                    fn_name = fc.get("name", "")
                    args_raw = fc.get("arguments", "{}")

                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except json.JSONDecodeError:
                        args = {}

                    result = await tool_executor.execute(fn_name, args)
                    _maybe_update_build_context(result, tool_executor)

                    # SSE uses item_id (same as tool_call event)
                    yield _sse("tool_result", {
                        "name": fn_name,
                        "call_id": item_id,
                        "result": result[:500],
                    })

                    # Responses API uses call_id for matching
                    input_messages.append({
                        "type": "function_call",
                        "call_id": api_call_id,
                        "name": fn_name,
                        "arguments": (
                            args_raw if isinstance(args_raw, str)
                            else json.dumps(args_raw)
                        ),
                    })
                    input_messages.append({
                        "type": "function_call_output",
                        "call_id": api_call_id,
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


def _item_to_dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    result: dict[str, Any] = {"type": getattr(item, "type", "unknown")}
    for attr in ("id", "call_id", "name", "arguments", "content", "text", "status"):
        val = getattr(item, attr, None)
        if val is not None:
            result[attr] = val
    content = getattr(item, "content", None)
    if isinstance(content, list):
        result["content"] = []
        for c in content:
            if hasattr(c, "text"):
                c_dict: dict[str, Any] = {
                    "type": getattr(c, "type", "text"),
                    "text": c.text,
                }
                annotations = getattr(c, "annotations", None)
                if annotations:
                    c_dict["annotations"] = [
                        {
                            "type": getattr(a, "type", ""),
                            "start_index": getattr(a, "start_index", None),
                            "end_index": getattr(a, "end_index", None),
                            "url": getattr(a, "url", ""),
                            "title": getattr(a, "title", ""),
                        }
                        for a in annotations
                    ]
                result["content"].append(c_dict)
    return result


def _extract_annotations(output_items: list[dict]) -> list[dict]:
    annotations: list[dict] = []
    for item in output_items:
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            for ann in block.get("annotations", []):
                if ann.get("type") == "url_citation":
                    annotations.append({
                        "start_index": ann.get("start_index"),
                        "end_index": ann.get("end_index"),
                        "url": ann.get("url", ""),
                        "title": ann.get("title", ""),
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
