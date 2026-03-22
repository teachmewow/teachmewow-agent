# Design

## Purpose
This file is the entrypoint for design documentation in `teachmewow-agent`.

## Agent-First Documentation Principles
- Keep `AGENTS.md` as a routing layer only; move technical specifics to architecture or deep dives.
- Prefer progressive disclosure: start at index docs, then drill into focused implementation docs.
- Make decisions and invariants explicit enough for another agent/engineer to execute safely.
- Keep docs evaluation-friendly with clear expected behavior and terminal conditions.

## When To Create or Update a Design Doc
Create or update a design doc when changes affect one or more of the following:
- runtime behavior or architectural boundaries,
- stream/event contracts,
- persistence semantics,
- public API expectations,
- non-trivial tradeoffs that future maintainers must understand.

## Design Record Template
Use this lightweight structure for each design note:

```md
# <Title>

## Context
What problem or constraint exists?

## Decision
What was chosen and why?

## Alternatives
What options were considered and why were they rejected?

## Consequences
What becomes easier/harder after this decision?
```

## Navigation
- Architecture source of truth: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- Deep-dive index: [design-docs/index.md](design-docs/index.md)
