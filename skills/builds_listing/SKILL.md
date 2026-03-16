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
2. The frontend renders selectable build cards automatically — you MUST NOT repeat, describe, or list the builds yourself.
3. Respond with a **short** message (2-3 sentences max).

## WRONG response (NEVER do this)
```
Aqui estão as builds disponíveis pra Warrior Arms (DPS):
Raid (Single Target) — Slayer
Raid (Multi/AoE) — Colossus
Mythic+ (AoE) — Slayer
Selecione uma build...
```

## CORRECT response (do this)
```
Encontrei 5 builds disponíveis para Arms Warrior — selecione uma nos cards abaixo! Depois posso te ajudar com rotação, cooldowns, openers ou diferenças entre M+ e Raid.
```

## Critical rules
- **NEVER list, enumerate, or describe individual builds in your text.** The UI cards already show them.
- NEVER call `list_builds` more than once per turn.
- Only add filters when the user is specific (e.g. "slayer M+", "raid ST").
