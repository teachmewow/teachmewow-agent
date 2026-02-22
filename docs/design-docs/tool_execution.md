# Tool Execution

## Purpose
Explain tool event lifecycle, payload handling, and extension rules.

## Lifecycle
1. Tool start event is received with run metadata.
2. Tool call id is resolved (direct payload or pending model tool call mapping).
3. Tool end event provides output payload.
4. Output is normalized and emitted as a persistence event.

## Payload Normalization
- Tool output may arrive as plain values, structured dicts, or objects with `content`.
- Runtime normalizes output into string payloads for persistence and downstream consumption.
- `build_lookup` output is parsed to persist `active_build_id` and `active_build_info`.
- `guide_context_lookup` output carries deterministic `citations` used by AI response metadata.

## Extension Rules
When adding a new tool:
- keep tool names stable and explicit,
- ensure tool start/end events remain linkable through run id + tool call id,
- return deterministic, serializable outputs,
- document tool-specific output shape if clients depend on it.
- prefer canonical enum values in tool args (no alias values for persisted filters).

## Failure Modes
- Missing tool start for a tool end event is a runtime contract error.
- Missing tool-call mapping is treated as an invariant violation.
