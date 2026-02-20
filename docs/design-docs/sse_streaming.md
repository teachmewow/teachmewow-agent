# SSE Streaming

## Purpose
Describe stream lifecycle and operational guarantees for SSE responses.

## Lifecycle
1. Graph execution starts with an initial `AgentState`.
2. Runtime events are consumed from LangGraph streaming.
3. Event contracts are validated for critical event kinds.
4. LLM deltas are accumulated and debounced before flush.
5. Tool events are emitted with minimal delay.
6. Buffered content is flushed on completion.
7. Stream ends with `done`, or `error` if an exception occurs.

## Debounce and Flush Semantics
- LLM token chunks are buffered and periodically flushed.
- Flush also occurs before selected events (for ordering correctness).
- Final flush is attempted before terminal completion.

## Behavioral Guarantees
- SSE output uses a stable envelope (`event` + JSON `data`).
- Terminal stream condition is explicit (`done` or `error`).
- Observer notifications happen as normalized events pass through runtime stages.

## Failure Behavior
- Exceptions trigger observer error notification.
- Partial buffered AI responses can still be persisted through error handling paths.
- Error details are surfaced as SSE `error` events.

## Related Docs
- [../FRONTEND.md](../FRONTEND.md)
- [persistence_and_observers.md](persistence_and_observers.md)
