---
name: meta-tierlist
description: Show current spec tier list rankings and meta viability. Works without a spec selected. Triggers on "tier list", "meta", "what's strong", "best dps", "best healer", "is my spec good", or "what's viable".
---

# Meta Tier List

## When to trigger
User asks "is my spec good?", "tier list", "meta", "what's strong", "best dps/healer/tank", "what's viable", or anything about spec rankings.

## Flow
1. Determine content type from context: M+ or Raid (default to M+ if unclear).
2. Determine role if mentioned (DPS, healer, tank) or show all roles.
3. Call `web_search`: `mythic+ tier list {role} {patch} site:icy-veins.com`
   - Alternative: `raid tier list {role} {patch} site:icy-veins.com`
4. If user has an active spec, highlight their spec's position.

## Output format
- Rankings with tiers (S/A/B/C) and brief reasoning
- If user has a spec: highlight position, strengths/weaknesses, and comparison
- Differentiate M+ vs Raid rankings (they are often very different)
- ALWAYS include disclaimer: "Every spec is viable up to +12-15. Tier lists matter more in very high keys or mythic prog."

## Important
- ALWAYS call `web_search` first — tier lists change every patch/hotfix.
- Archon.gg and icy-veins.com are canonical sources for tier data.
- Be encouraging — don't make players feel bad about their spec choice.
