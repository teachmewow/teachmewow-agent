"""
Meta-tool: load_skill

Returns the full instructions of a registered skill so the orchestrator
can follow its workflow.  This is the bridge between the orchestrator's
autonomous decision-making and the structured skill procedures.
"""

from __future__ import annotations

import json

from app.application.agent.skills import SkillRegistry


def load_skill(
    skill_name: str,
    *,
    registry: SkillRegistry,
    char_info: dict | None = None,
    build_info: dict | None = None,
) -> str:
    """Execute the ``load_skill`` function tool."""
    skill = registry.get(skill_name)
    if skill is None:
        available = ", ".join(registry.all_names()) or "none"
        return json.dumps({
            "error": f"Unknown skill '{skill_name}'. Available: {available}",
        })

    context_parts: list[str] = [skill.instructions]

    if char_info:
        wow_class = char_info.get("class") or char_info.get("wow_class") or ""
        spec = char_info.get("spec") or ""
        role = char_info.get("role") or ""
        context_parts.append(
            f"\n## Current character\nClass: {wow_class}, Spec: {spec}, Role: {role}"
        )

    if build_info:
        build_id = build_info.get("build_id") or ""
        hero = build_info.get("hero_talent") or ""
        env = build_info.get("environment") or ""
        context_parts.append(
            f"Active build: {build_id} (Hero: {hero}, Env: {env})"
        )

    return json.dumps({
        "skill": skill.name,
        "instructions": "\n".join(context_parts),
    })


# -- OpenAI function-tool JSON schema ------------------------------------

LOAD_SKILL_SCHEMA: dict = {
    "type": "function",
    "name": "load_skill",
    "description": (
        "Load a skill's full workflow instructions. "
        "Call this when a user request matches one of the available skills."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Name of the skill to load (e.g. build_lookup, build_coaching)",
            },
        },
        "required": ["skill_name"],
        "additionalProperties": False,
    },
}
