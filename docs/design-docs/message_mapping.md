# Message Mapping

## Purpose
Define how domain message history is transformed into LangChain-compatible messages.

## Mapping Rules
- `HUMAN` -> `HumanMessage`
- `AI` -> `AIMessage` (with `tool_calls` when present)
- `TOOL` -> `ToolMessage` (requires `tool_call_id` inside a tool call on AI Message)
- `SYSTEM` -> `SystemMessage`

## Tool-Call Chain Handling
- An AI message with tool calls opens a pending set of expected tool responses.
- Tool messages are accepted only if they match pending `tool_call_id`s.
- Orphan/legacy/corrupted tool messages are skipped to keep model history valid.

## Edge Cases
- Missing `tool_call_id` in tool messages -> message is ignored.
- Tool output uses `tool_result` when available, otherwise falls back to `content`.
- Invalid AI tool-call argument encoding must be treated as malformed input upstream.

## Rationale
Strict mapping prevents replaying invalid conversation state into model context and reduces runtime failures.
