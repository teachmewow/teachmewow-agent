---
name: affix-strategy
description: Show current weekly M+ affixes and strategies for dealing with them. Works without a spec selected. Triggers on "affixes", "affix this week", "what affixes", or specific affix names.
---

# Affix Strategy

## When to trigger
User asks "what are the affixes?", "affix this week", "how to deal with [affix name]", or mentions affixes.

## Flow
1. Call `web_search`: `mythic+ affixes this week wow` or `{affix_name} strategy tips mythic+ site:icy-veins.com`
2. Affix rotation is weekly — web search always returns current week data.

## Output format
- **Active affixes** — name + brief description of each effect
- **General strategies** per affix
- **Spec-specific tips** (if spec context): e.g. "Fortified week = big pulls are more dangerous, save CDs for trash"
- How the affixes interact with each other this week

## Important
- ALWAYS call `web_search` first — affixes change weekly.
- Affixes scale with key level. Mention which key levels each affix activates at if relevant.
