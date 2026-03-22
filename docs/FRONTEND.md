# Frontend Integration Contract

## Scope
This document defines how frontend clients should integrate with `teachmewow-agent`.

## Endpoint Expectations
- Chat endpoint: `POST /agent/chat`
- Transport: HTTP streaming (`text/event-stream`)
- Core request fields:
  - `input`
  - `thread_id`
  - `user_id`
  - `char_info` with `class`, `spec`, `role`

## SSE Envelope
Each SSE message is sent as:

```text
event: <event_name>
data: {"event":"<event_name>","data":{...}}
```

Typical event categories observed by clients:
- model stream updates,
- tool invocation updates,
- completion (`done`),
- failures (`error`).

## Compatibility Notes
- Treat `done` and `error` as terminal events.
- Do not depend on internal persistence events.
- UI should be tolerant to payload evolution and unknown keys.

## Non-Goals
Frontend implementation details, component architecture, and UX concerns are outside this repository.

## Related Docs
- Architecture: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- Streaming deep-dive: [design-docs/sse_streaming.md](design-docs/sse_streaming.md)
