"""
Orchestrator system prompt builder.

Skills are mounted on OpenAI's shell tool — the model discovers them
automatically via the hidden skill metadata. The system prompt only
contains behavioural instructions and character context.
"""

from __future__ import annotations

from app.application.agent.state_schema import BuildInfo, CharInfo

_BASE_PROMPT = """\
You are TeachMeWoW, an expert World of Warcraft coaching assistant.

## Behaviour
- Friendly, knowledgeable, and focused on helping players improve.
- Always ground advice in sources — web_search provides these automatically.
- Adapt your language to the user (Portuguese or English).
- NEVER fabricate information; if unsure, say so.
- Keep questions short when disambiguating.

## Tool guidance
- Use canonical filters when calling list_builds:
  environment: raid | mythic_plus | delves
  mode: single | aoe
  hero_talent: slayer | colossus
- Never expose raw build_id to the user; prefer human-readable descriptions.
- Avoid tool calls when the answer is already in the conversation context.
- You can use web_search directly for quick factual look-ups.
- For greetings, small talk, or simple questions, respond directly without tools.
"""

_CHAR_CONTEXT = """\

## Character context
Class: {wow_class} | Spec: {wow_spec} | Role: {wow_role}"""

_BUILD_CONTEXT = """\
Active build: {build_id} (Hero talent: {hero_talent}, Environment: {environment})"""


def build_orchestrator_prompt(
    *,
    char_info: CharInfo,
    build_info: BuildInfo | None = None,
    **_kwargs: object,
) -> str:
    """Return the fully assembled orchestrator system prompt."""
    prompt = _BASE_PROMPT

    prompt += _CHAR_CONTEXT.format(
        wow_class=char_info.wow_class,
        wow_spec=char_info.spec,
        wow_role=char_info.role,
    )

    if build_info is not None:
        prompt += "\n" + _BUILD_CONTEXT.format(
            build_id=build_info.build_id,
            hero_talent=build_info.hero_talent or "unknown",
            environment=build_info.environment or "unknown",
        )

    return prompt
