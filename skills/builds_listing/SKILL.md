---
name: builds-listing
description: List available WoW builds when no active build is selected.
---

# Builds Listing

## When to trigger
- The conversation has NO active build yet AND the user asks about builds, talents, rotation, or anything class/spec-related.
- NOT when the user is just greeting or making small talk.

## Flow
1. Call `list_builds` once with no filters (returns all builds for the character's class/spec).
2. Do NOT call `build_lookup` — the frontend renders selectable build cards automatically.
3. After the tool returns, respond with a short message:
   - Tell the user how many builds were found.
   - Ask them to **select one from the cards below** to continue.
   - Suggest what they can explore after selecting: rotation/priority, resource management, cooldown usage, openers, Mythic+ vs Raid differences, talent alternatives, etc.

## Only add filters when the user is specific
If the user says "slayer M+" or "raid ST", add those filters. Otherwise no filters.

## NEVER call list_builds more than once per turn.
