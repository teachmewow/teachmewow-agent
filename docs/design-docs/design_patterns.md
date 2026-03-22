# Design Patterns

## Purpose
Document recurring architectural patterns used in `teachmewow-agent` and their boundaries.

## Layered Architecture
- Use when defining clear business/application/infrastructure/presentation boundaries.
- Avoid when logic would be duplicated only to satisfy layer purity with no practical gain.

## Mapper Pattern
- Use for explicit translation between domain entities and external/internal protocol types.
- Current example: domain `Message` to LangChain message types.
- Avoid leaking mapping rules across services.

## Strategy Registry
- Use for event-specific runtime behavior selection.
- Current example: stream event strategies keyed by event kind.
- Avoid ad-hoc `if/else` growth for heterogeneous event behavior.

## Observer Pattern
- Use to attach side effects (persistence, analytics, audit) without coupling them to orchestration core.
- Current example: stream observer notifications and DB observer persistence.
- Avoid embedding side effects directly in orchestration loops.

## Emit Pipeline Stages
- Use staged processing for stream emission (`pre-flush`, `map`, `notify`, `serialize`).
- Enables composability and focused testing per stage.
- Avoid collapsing all stream responsibilities into one method.
