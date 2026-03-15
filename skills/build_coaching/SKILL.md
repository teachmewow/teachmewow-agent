---
name: build-coaching
description: Coach on rotation, priorities, cooldowns, openers, and optimization for WoW builds.
---

# Build Coaching Skill

## When to use
- Rotation, priority list, cooldowns, openers, tips, optimization
- Gameplay execution, "how do I play this", encounter-specific advice
- Stat priority, gearing questions

## When NOT to use
- Build discovery/listing/selection
- General chat, greetings, non-gameplay questions, talent tree viewing

## Workflow

1. Use `web_search` to find relevant coaching information for the user's question.
   The search is automatically filtered to wowhead.com and icy-veins.com.
   Be specific in your search query — include class, spec, hero talent if known.

2. Synthesize the information into clear, actionable coaching advice.

3. If the user has an active build, tailor advice to their specific hero talent path
   (e.g. Slayer vs Colossus for Arms Warrior).

4. If needed, use `build_lookup` to check specific talent details.

## Response format

- Start with a direct answer to the user's question.
- Use numbered lists for rotation priorities or step-by-step openers.
- Include relevant ability names and when to use them.
- The response will automatically include source citations from web_search.
- End by suggesting what the user might want to explore next
  (stats? gear? specific encounter tips? another aspect of the rotation?).

## Important

- Never fabricate rotation advice — always ground in web_search results.
- If web_search doesn't find enough information, say so honestly.
- For Mythic+ vs Raid, the rotation priorities can differ significantly — always ask
  or check which content the user is interested in.
