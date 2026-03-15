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
        """Short catalog listing skill names and descriptions."""
        if not self._skills:
            return "No skills available."

        lines = ["Available skills:"]
        for skill in self._skills.values():
            lines.append(f"- {skill.name}: {skill.description}")
            lines.append(f"  Use when: {skill.when_to_use}")
            lines.append(f"  Don't use when: {skill.when_not_to_use}")
        return "\n".join(lines)

    def instructions_for_system_prompt(self) -> str:
        """
        Return full skill instructions for injection into the system prompt.

        Each skill's complete workflow is included so the model can follow
        the right one based on user intent — no tool call needed.
        """
        if not self._skills:
            return ""

        sections: list[str] = []
        for skill in self._skills.values():
            section = (
                f"## Skill: {skill.name}\n"
                f"**Use when:** {skill.when_to_use}\n"
                f"**Don't use when:** {skill.when_not_to_use}\n\n"
                f"{skill.instructions}"
            )
            sections.append(section)
        return "\n\n---\n\n".join(sections)
