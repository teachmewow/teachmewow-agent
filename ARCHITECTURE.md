# Architecture

## Purpose
This document is the source of truth for `teachmewow-agent` architecture, layer responsibilities, runtime flow, and execution invariants.

## Layered Responsibilities

### `domain`
- Defines business entities and value objects (`Message`, `Thread`, `ToolCall`, `WowClass`, `WowSpec`, roles).
- Defines repository contracts used by upper layers.
- Contains no infrastructure/framework behavior.

### `application`
- Coordinates use cases and orchestration (`ChatService`, graph nodes, mapper, orchestrator).
- Translates domain history to LLM-compatible state via `MessageMapper`.
- Runs streaming orchestration and dispatches observer side effects.

### `infrastructure`
- Implements technical integrations (database repositories/models, LLM client, Helix client, config).
- Owns persistence and external service wiring.

### `presentation`
- Exposes HTTP API and request/response schemas.
- Accepts client input (`POST /agent/chat`) and returns SSE responses.

## End-To-End Runtime Flow (`POST /agent/chat`)
1. `presentation` validates request payload and forwards to `ChatService`.
2. `application` ensures thread state, persists the new human message, and loads history.
3. `MessageMapper` converts domain messages to LangChain messages.
4. `SSEOrchestrator` executes the compiled graph and streams normalized SSE events.
5. Runtime components (`PersistenceFacade`, notifier, emit pipeline) emit internal persistence events.
6. `DatabaseObserver` persists AI/tool outputs and thread state side effects.
7. Stream terminates with `done`, or `error` if execution fails.

## Execution Invariants

### Stream Event Contract Integrity
- Supported runtime events are validated before persistence-sensitive handling.
- `on_chat_model_stream` and `on_chat_model_end` must include `run_id` and expected payload fields.
- `on_tool_start` and `on_tool_end` must include `run_id`; tool end must include output.

### Tool Call / Result Linkage
- Tool persistence requires a valid `tool_call_id` mapping.
- Tool results must be traceable to an earlier tool start for the same execution path.
- Orphan or malformed tool history is ignored during message mapping to prevent invalid context replay.

### Persistence and Error Guarantees
- AI/tool persistence is event-driven through observer notifications.
- Partial AI output may be persisted on failures when buffered content exists.
- Duplicate writes are guarded by per-run / per-tool-call idempotency checks.
- Stream always emits a terminal event (`done` or `error`).

## Public Interface Notes
- Primary chat endpoint: `POST /agent/chat`.
- Response transport: `text/event-stream` (SSE).
- External clients should rely on documented SSE semantics, not internal runtime events.

## Deep-Dive References
- Design entrypoint: [docs/DESIGN.md](docs/DESIGN.md)
- Deep-dive index: [docs/design-docs/index.md](docs/design-docs/index.md)
- Streaming details: [docs/design-docs/sse_streaming.md](docs/design-docs/sse_streaming.md)
- Message mapping details: [docs/design-docs/message_mapping.md](docs/design-docs/message_mapping.md)
- Tool execution details: [docs/design-docs/tool_execution.md](docs/design-docs/tool_execution.md)
- Persistence and observers: [docs/design-docs/persistence_and_observers.md](docs/design-docs/persistence_and_observers.md)
