# Persistence and Observers

## Purpose
Describe how stream-time side effects are decoupled from orchestration and persisted safely.

## Observer Responsibilities
- Receive normalized runtime events.
- Persist AI and tool messages using repository contracts.
- Keep stream orchestration independent from persistence implementation details.

## Persistence Boundaries
- AI message persistence is triggered by normalized AI completion events.
- Tool message persistence is triggered by normalized tool completion events.
- Thread side effects (for example active build updates) are derived from persisted tool output.

## Idempotency and Safety
- AI runs are deduplicated by run id.
- Tool messages are deduplicated by `tool_call_id`.
- Failed tool persistence rolls back local dedup tracking for retry safety.

## Partial-Save Behavior
- If streaming fails, buffered AI partials can be emitted as persistence events.
- This preserves useful progress while still signaling stream failure.

## Related Docs
- [sse_streaming.md](sse_streaming.md)
- [tool_execution.md](tool_execution.md)
