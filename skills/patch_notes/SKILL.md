---
name: patch-notes
description: Summarize recent WoW patch notes, hotfixes, buffs, and nerfs. Works without a spec selected. Triggers on "patch notes", "what changed", "nerfs", "buffs", "was my spec nerfed", or "hotfix".
---

# Patch Notes

## When to trigger
User asks "what changed?", "patch notes", "nerfs", "buffs", "was my spec nerfed?", "hotfix", or anything about recent game changes.

## Flow
1. Call `web_search`:
   - With spec: `wow patch notes {class} {spec} site:wowhead.com`
   - Without spec: `wow latest patch notes hotfix site:wowhead.com`
2. Wowhead has the best hotfix coverage. Icy-veins is a good fallback.

## Output format
- **Most relevant changes** — summarized, not raw copy-paste
- **Spec-specific impact** (if spec context): highlight buffs/nerfs that affect the user directly
- **Recent hotfixes** — Blizzard ships hotfixes every week, web search picks up the latest
- **Impact context**: e.g. "This 5% Mortal Strike nerf reduces ~2% overall DPS, still tier A"

## Important
- ALWAYS call `web_search` first — patch data changes frequently.
- Hotfixes can happen multiple times per week. Always search for the latest.
- Be factual about impact — don't catastrophize small nerfs or overhype small buffs.
