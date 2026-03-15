---
name: build-lookup
description: Find, list, and show WoW builds for the user's class and spec.
---

# Build Lookup Skill

## When to use
- User asks about builds, talents, import codes
- "what build should I use", "show me builds", talent tree requests

## When NOT to use
- Coaching questions about rotation/priority/cooldowns
- General chat, greetings, gameplay tips

## Workflow

1. **Disambiguate first.** If the user's request is vague (e.g. "show me builds",
   "what builds do you have"), ask a short disambiguation question BEFORE calling
   any tool. Examples:
   - "Quer ver todas as builds disponíveis, ou tem preferência? Raid, Mythic+ ou Delves? ST ou AoE?"
   - "Slayer ou Colossus? Ou quer ver as duas?"
   Do NOT call list_builds yet — just ask.

2. **If the user is specific** (e.g. "raid builds", "slayer m+", "all builds"),
   call `list_builds` ONCE with the appropriate filters (or no filters for "all").
   NEVER call list_builds multiple times with different filter combinations.

3. Present results grouped by environment. Show: hero talent, mode, patch.

4. If the user picks a build, use `build_lookup(build_id)` for full details.

5. After showing a build, ask if they want coaching on it.

## Important

- ALWAYS prefer asking over guessing when the request is ambiguous.
- ONE call to list_builds is enough — no filters returns everything.
- Do NOT iterate over filter combinations.
