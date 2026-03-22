---
name: build-coaching
description: Coach on rotation, priorities, cooldowns, openers, and optimization when an "Active build" section exists in the system prompt. Takes priority over builds-listing when a build is selected.
---

# Build Coaching

## When to trigger
- The system prompt contains an "Active build" section — this means the user selected a build from the UI.
- The user asks anything about how to play, rotation, priorities, talents, cooldowns, openers, or gameplay.
- This skill takes priority over builds-listing when an active build exists.

## Prerequisites
An active build MUST be selected (check system prompt for "Active build" section).
If no active build, tell the user to select one first.

## Flow
1. ALWAYS call `web_search` before responding — NEVER fabricate advice.
2. Use the source guide URL from the active build context to target your search.
3. Include class, spec, hero talent, and content type in the query.
4. Synthesize into clear, actionable advice. Numbered lists for rotations.
5. Source citations come automatically from web_search.
6. Suggest what to explore next.

## Important
- NEVER respond without calling web_search first.
- If info is insufficient, say so honestly.
- Mythic+ and Raid rotations differ — always clarify which context.
