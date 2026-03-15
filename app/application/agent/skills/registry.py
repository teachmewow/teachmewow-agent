"""
Skill registry — holds all registered skills and generates the
catalog string injected into the orchestrator's system prompt.
"""

from __future__ import annotations

from .base import SkillDefinition


class SkillRegistry:
    """Thread-safe (read-only after startup) registry of skills."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    # -- mutators (called at startup only) ----------------------------------

    def register(self, skill: SkillDefinition) -> None:
        self._skills[skill.name] = skill

    # -- accessors ----------------------------------------------------------

    def get(self, name: str) -> SkillDefinition | None:
        return self._skills.get(name)

    def all_names(self) -> list[str]:
        return list(self._skills.keys())

    def catalog_for_system_prompt(self) -> str:
        """
        Return a formatted skill catalog suitable for injection into
        the orchestrator's system prompt.

        Example output::

            Available skills:
            - build_lookup: Find, list, and show WoW builds
              Use when: user asks about builds, talents, import codes
              Don't use when: coaching questions, rotation, general chat
            - build_coaching: Coach on rotation, priorities, cooldowns
              ...
        """
        if not self._skills:
            return "No skills available."

        lines = ["Available skills:"]
        for skill in self._skills.values():
            lines.append(f"- {skill.name}: {skill.description}")
            lines.append(f"  Use when: {skill.when_to_use}")
            lines.append(f"  Don't use when: {skill.when_not_to_use}")
        return "\n".join(lines)
