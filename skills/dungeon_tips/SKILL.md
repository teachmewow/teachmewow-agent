---
name: dungeon-tips
description: Provide Mythic+ dungeon tips including dangerous trash, boss mechanics, interrupt priorities, and spec-specific advice. Works with or without a spec selected. Triggers on dungeon names, M+ tips, or "how to do this dungeon".
---

# Dungeon Tips

## When to trigger
User asks about a specific dungeon, M+ tips, mentions a dungeon name, asks about trash packs, boss mechanics, or routes.

## Flow
1. Identify the dungeon name from the user's message.
2. Call `web_search`:
   - With spec context: `{dungeon_name} mythic+ guide {class} {spec} site:wowhead.com`
   - Without spec context: `{dungeon_name} mythic+ guide tips site:wowhead.com`
3. If user asks about a specific boss, do a focused search on that boss.

## Output format
- **Dangerous trash packs** — abilities to interrupt (interrupt priority list)
- **Boss mechanics** — 1-3 bullets per boss, quick-reference style
- **Spec-specific tips** (if spec context available): e.g. "As Arms Warrior, use Spell Reflection on cast X"
- **Route suggestions** if info is available
- Keep it concise and actionable — this is a quick-reference, not an essay.

## Important
- ALWAYS call `web_search` first.
- The M+ dungeon pool changes each season (8 dungeons). Don't assume which dungeons are current — search for it.
- If user asks about a boss, drill down with more detail on that specific boss.
