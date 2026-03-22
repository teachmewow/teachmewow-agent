---
name: raid-guide
description: Provide raid boss guides with mechanics, phase breakdowns, and role-specific tips. Works without a spec selected. Triggers on boss names, raid names, "how to kill", "tactics", or "boss guide".
---

# Raid Guide

## When to trigger
User asks about a raid boss, mechanics, "how to kill X", "tactics for Y", or mentions a raid or boss name.

## Flow
1. Identify the boss and/or raid name from the user's message.
2. Call `web_search`:
   - With spec: `{boss_name} {raid_name} guide {difficulty} {class} {spec} site:icy-veins.com`
   - Without spec: `{boss_name} {raid_name} guide {difficulty} site:icy-veins.com`
3. Default difficulty to Heroic unless user specifies otherwise.

## Output format
- **Overview** — 1-2 sentences on what the boss does
- **Mechanics by phase** — numbered, with ability names
- **Role tips**: tank swap timing, healer CD assignments, DPS check moments
- **Spec-specific tips** (if spec context): e.g. "As Arms, save Bladestorm for add phase"
- Keep it actionable — players read this before a pull, not as a novel.

## Important
- ALWAYS call `web_search` first.
- Know the current raid tier of the season. If unsure, search for it.
- If user asks about a specific mechanic, drill down on that mechanic.
