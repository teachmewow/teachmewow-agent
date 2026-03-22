---
name: gear-setup
description: Recommend gems, enchants, consumables, and stat priority for the current spec. Requires an active build or character context. Triggers on questions about gear, stats, enchants, gems, consumables, or "what to use".
---

# Gear Setup

## When to trigger
User asks about gear, stats, enchants, gems, consumables, flask, food, potions, stat priority, "what to enchant", "what gems", "what consumables", or "what stats should I prioritize".

## Prerequisite
Needs character context (class/spec). If a build is active, tailor advice to that build's environment (Raid vs M+).

## Flow
1. Call `web_search` with query: `{class} {spec} gems enchants consumables {patch} site:icy-veins.com`
2. If active build exists and has an environment, add it: `{class} {spec} {environment} stat priority`
3. Synthesize into structured output.

## Output format
- **Stat priority** (e.g. "Strength > Haste > Critical Strike > Versatility > Mastery")
- **Gems** (e.g. "Masterful Emerald in all sockets")
- **Enchants** by slot: weapon, chest, cloak, bracers, legs, boots, ring
- **Consumables**: flask, food, combat potion, weapon enhancement
- If the active build has an environment context, note any differences between Raid and M+ stat weights.

## Important
- ALWAYS call `web_search` first — never fabricate stat weights or enchant names.
- Stat priority can differ between Raid and M+ — clarify which context.
- If info is outdated or insufficient, say so honestly.
