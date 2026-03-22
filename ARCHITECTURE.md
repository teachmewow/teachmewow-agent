# Architecture

## Purpose
This document is the source of truth for `teachmewow-agent` architecture, layer responsibilities, runtime flow, and execution invariants.

## Layered Responsibilities

### `domain`
- Defines business entities and value objects (`Message`, `Thread`, `ToolCall`, `WowClass`, `WowSpec`, roles).
- Defines repository contracts used by upper layers.
- Contains no infrastructure/framework behavior.

### `application`
- Coordinates use cases and orchestration (`ChatService`, `Orchestrator`, `OrchestratorBuilder`).
- `OrchestratorBuilder` assembles the Orchestrator with provider, tool registry, skills, and tools config.
- `ToolRegistry` maps tool names to typed `ToolHandler` implementations (no if/elif dispatch).
- `ToolExecutor` delegates to the registry with a shared `ToolContext` (char_info, build_info).
- Typed event processing via `match`/`case` on OpenAI SDK types.

### `infrastructure`
- Implements technical integrations (database repositories/models, LLM client, config).
- `OpenAIProvider` wraps `AsyncOpenAI` with optional LangSmith tracing (module-level import check).
- Skills loader reads SKILL.md files from disk for local shell mode.
- Owns persistence and external service wiring.

### `presentation`
- Exposes HTTP API and request/response schemas.
- Accepts client input (`POST /agent/chat`) and returns SSE responses.

## End-To-End Runtime Flow (`POST /agent/chat`)
1. `presentation` validates request payload and forwards to `ChatService`.
2. `application` ensures thread state, persists the new human message, and loads history.
3. `ChatService` converts domain messages to Responses API format and builds the system prompt.
4. `Orchestrator.stream()` executes the tool-call loop and streams typed SSE events.
5. Function calls are dispatched via `ToolRegistry` → `ToolHandler.execute()`.
6. `ChatService` captures the `done` event and persists the AI response.
7. Stream terminates with `done`, or `error` if execution fails.

## Key Components

### OrchestratorBuilder (`app/application/agent/orchestrator_builder.py`)
- Wires provider, tool registry, skills, and tools config.
- Configures web search domain filtering (wowhead.com, icy-veins.com).
- Called once during lifespan startup.

### ToolRegistry (`app/application/agent/tools/registry.py`)
- `ToolHandler` protocol: `name`, `schema`, `execute(args, ctx)`.
- `ToolContext` (Pydantic model): `char_info`, `build_info`.
- Handlers: `ListBuildsHandler`, `BuildLookupHandler`.
- `schemas()` returns all tool schemas for the Responses API.

### Typed Orchestrator (`app/application/agent/orchestrator.py`)
- Uses `match`/`case` on SDK types: `ResponseTextDeltaEvent`, `ResponseFunctionCallArgumentsDeltaEvent`, `ResponseOutputItemAddedEvent`, `ResponseOutputItemDoneEvent`, `ResponseFunctionToolCall`, `ResponseOutputMessage`, etc.
- Shell/skill events handled via string-based fallback (`_is_shell_event`).
- Annotations extracted via `ResponseOutputMessage` → `AnnotationURLCitation`.

## Execution Invariants

### Stream Event Contract
- SSE events: `token`, `tool_call`, `tool_result`, `web_search`, `skill_active`, `annotations`, `done`, `error`.
- All payloads: `data: {"event": "<name>", "data": {...}}\n\n`.
- Stream always emits a terminal event (`done` or `error`).

### Tool Call / Result Linkage
- Function calls use `ResponseFunctionToolCall.call_id` for API matching and `.id` for SSE events.
- Tool results are traced through `ToolRegistry.execute()`.

### Persistence
- Only `done` event text is persisted as an AI message.
- Build context is updated when tool results contain `build_info`.
- Thread-level build info is persisted as `threads.active_build_info` (JSONB).

### Safety Limits
- Max orchestrator iterations: 15.
- Web search filtered to wowhead.com and icy-veins.com only.

## Public Interface Notes
- Primary chat endpoint: `POST /agent/chat`.
- Response transport: `text/event-stream` (SSE).
- External clients should rely on documented SSE semantics, not internal runtime events.

## Deep-Dive References
- Design entrypoint: [docs/DESIGN.md](docs/DESIGN.md)
- Deep-dive index: [docs/design-docs/index.md](docs/design-docs/index.md)
- Streaming details: [docs/design-docs/sse_streaming.md](docs/design-docs/sse_streaming.md)
- Tool execution details: [docs/design-docs/tool_execution.md](docs/design-docs/tool_execution.md)
- Persistence and observers: [docs/design-docs/persistence_and_observers.md](docs/design-docs/persistence_and_observers.md)
