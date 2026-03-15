"""Skill: build_lookup — find, list, and show WoW builds."""

from .base import SkillDefinition

build_lookup_skill = SkillDefinition(
    name="build_lookup",
    description="Find, list, and show WoW builds for the user's class/spec",
    when_to_use=(
        "User asks about builds, talents, import codes, "
        "'what build should I use', 'show me builds', talent tree requests"
    ),
    when_not_to_use=(
        "Coaching questions about rotation/priority/cooldowns, "
        "general chat, greetings, gameplay tips"
    ),
    instructions="""\
# Build Lookup Skill

## Workflow
1. Use `list_builds` with any filters the user mentioned (environment, hero_talent, mode).
   If the user didn't specify filters, list all available builds.
2. Present results clearly: build ID, hero talent, environment, mode, patch, source.
3. If the user picks a build or wants details, use `build_lookup(build_id)` to get
   the full talent tree and import code.
4. After showing a build, ask if they want coaching on it (rotation, tips, etc.).

## Response format
- Use clear formatting (bullet points or a small table) for build lists.
- When showing a single build, highlight the hero talent path and import code.
- Tell the user to check the talent tree viewer for the visual tree.
""",
)
