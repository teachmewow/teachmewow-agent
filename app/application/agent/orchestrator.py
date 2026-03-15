"""
Orchestrator — drives the agent loop using the OpenAI Responses API.

Replaces the entire LangGraph pipeline with a simple tool-call loop:

    orchestrator ←→ tools → done

Yields SSE-formatted events for the FastAPI streaming response.
"""

from __future__ import annotations

import json
import traceback
from collections.abc import AsyncGenerator
from typing import Any

from app.infrastructure.llm.provider import LLMProvider

from .skills import SkillRegistry
from .tools.tool_executor import ToolExecutor


class Orchestrator:
    """
    Stateless orchestrator — one instance is shared across requests.
    Per-request state is passed via ``stream()``.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        tools_config: list[dict[str, Any]],
        skill_registry: SkillRegistry,
    ) -> None:
        self._provider = provider
        self._model = model
        self._tools_config = tools_config
        self._skill_registry = skill_registry

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

        The loop:
        1. Send conversation + system prompt to the Responses API.
        2. Stream tokens to the client.
        3. If the response contains function calls, execute them and loop.
        4. If no function calls, emit annotations + done and exit.
        """
        tool_executor = ToolExecutor(
            skill_registry=self._skill_registry,
            char_info=char_info,
            build_info=build_info,
        )

        # Build the input array for the Responses API
        input_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        max_iterations = 15  # safety limit
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                accumulated_text = ""
                output_items: list[dict] = []
                current_fn_calls: dict[str, dict] = {}  # call_id -> {name, args_buffer}

                response = await self._provider.create_response(
                    model=self._model,
                    input=input_messages,
                    tools=self._tools_config,
                    stream=True,
                )

                async for event in response:
                    event_type = getattr(event, "type", "")

                    # -- text delta tokens --
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", "")
                        if delta:
                            accumulated_text += delta
                            yield _sse("token", {"text": delta})

                    # -- function call arguments streaming --
                    elif event_type == "response.function_call_arguments.delta":
                        call_id = getattr(event, "item_id", None)
                        delta = getattr(event, "delta", "")
                        if call_id and call_id in current_fn_calls:
                            current_fn_calls[call_id]["args_buffer"] += delta

                    # -- output item added (function_call or message) --
                    elif event_type == "response.output_item.added":
                        item = getattr(event, "item", None)
                        if item and getattr(item, "type", "") == "function_call":
                            call_id = getattr(item, "id", "") or getattr(item, "call_id", "")
                            fn_name = getattr(item, "name", "")
                            current_fn_calls[call_id] = {
                                "name": fn_name,
                                "args_buffer": "",
                            }
                            yield _sse("tool_call", {"name": fn_name, "call_id": call_id})

                    # -- output item done --
                    elif event_type == "response.output_item.done":
                        item = getattr(event, "item", None)
                        if item:
                            output_items.append(_item_to_dict(item))

                    # -- web search events --
                    elif event_type == "response.web_search_call.in_progress":
                        yield _sse("web_search", {"status": "searching"})
                    elif event_type == "response.web_search_call.completed":
                        yield _sse("web_search", {"status": "completed"})

                # -- Finished streaming this response turn --

                # Collect function calls from output_items
                function_calls = [
                    item for item in output_items
                    if item.get("type") == "function_call"
                ]

                if not function_calls:
                    # No function calls — final response.
                    # Extract annotations from the output items.
                    annotations = _extract_annotations(output_items)
                    if annotations:
                        yield _sse("annotations", {"citations": annotations})
                    yield _sse("done", {
                        "text": accumulated_text,
                    })
                    return

                # Execute function calls and add results to conversation
                for fc in function_calls:
                    call_id = fc.get("call_id", fc.get("id", ""))
                    fn_name = fc.get("name", "")
                    args_raw = fc.get("arguments", "{}")

                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except json.JSONDecodeError:
                        args = {}

                    result = await tool_executor.execute(fn_name, args)

                    # Check if build_lookup returned build_info — update context
                    _maybe_update_build_context(result, tool_executor)

                    yield _sse("tool_result", {
                        "name": fn_name,
                        "call_id": call_id,
                        "result": result[:500],  # truncated for SSE
                    })

                    # Append the function call + result to input for next turn
                    input_messages.append({
                        "type": "function_call",
                        "call_id": call_id,
                        "name": fn_name,
                        "arguments": args_raw if isinstance(args_raw, str) else json.dumps(args_raw),
                    })
                    input_messages.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": result,
                    })

            # Exceeded max iterations
            yield _sse("error", {"message": "Max tool iterations reached."})

        except Exception as exc:
            traceback.print_exc()
            yield _sse("error", {"message": str(exc)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(event: str, data: dict) -> str:
    """Format a server-sent event string."""
    payload = json.dumps({"event": event, "data": data}, ensure_ascii=True)
    return f"data: {payload}\n\n"


def _item_to_dict(item: Any) -> dict:
    """Convert a Responses API output item to a plain dict."""
    if isinstance(item, dict):
        return item
    result: dict[str, Any] = {"type": getattr(item, "type", "unknown")}
    for attr in ("id", "call_id", "name", "arguments", "content", "text", "status"):
        val = getattr(item, attr, None)
        if val is not None:
            result[attr] = val
    # Handle nested content (message items)
    content = getattr(item, "content", None)
    if isinstance(content, list):
        result["content"] = []
        for c in content:
            if hasattr(c, "text"):
                c_dict: dict[str, Any] = {"type": getattr(c, "type", "text"), "text": c.text}
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
    """Pull url_citation annotations from message output items."""
    annotations: list[dict] = []
    for item in output_items:
        if item.get("type") != "message":
            continue
        for content_block in item.get("content", []):
            for ann in content_block.get("annotations", []):
                if ann.get("type") == "url_citation":
                    annotations.append({
                        "start_index": ann.get("start_index"),
                        "end_index": ann.get("end_index"),
                        "url": ann.get("url", ""),
                        "title": ann.get("title", ""),
                    })
    return annotations


def _maybe_update_build_context(result: str, executor: ToolExecutor) -> None:
    """If a tool returned build_info, update the executor's context."""
    try:
        data = json.loads(result)
        bi = data.get("build_info")
        if isinstance(bi, dict) and bi.get("build_id"):
            executor.update_context(build_info=bi)
    except (json.JSONDecodeError, AttributeError):
        pass
