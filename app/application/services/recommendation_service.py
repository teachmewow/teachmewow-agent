"""
Recommendation service — generates follow-up question suggestions
using a lightweight LLM with skill descriptions as context.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.infrastructure.config import get_settings
from app.infrastructure.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
You are a suggestion engine for a World of Warcraft coaching chatbot.
Given the assistant's last message and the chatbot's available capabilities, \
generate exactly 2 short follow-up questions the user is likely to ask next.

Rules:
- Each question must be under 80 characters.
- Write in the SAME language as the assistant message below.
- Prefer questions that map to one of the available capabilities.
- Questions should feel natural, not robotic.
- Do NOT repeat what the assistant already answered.

Available capabilities:
{capabilities}

Character: {wow_class} {spec} ({role})
Active build: {build_context}

Last assistant message:
{assistant_message}

Respond with ONLY a JSON array, no markdown fences:
[{{"text": "...", "skill_hint": "capability-name-or-null"}}, {{"text": "...", "skill_hint": "capability-name-or-null"}}]
"""


class RecommendationService:
    """Generates contextual follow-up suggestions via a lightweight LLM."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        skill_contents: list[dict[str, str]],
    ) -> None:
        self._provider = provider
        self._skill_descriptions = self._build_skill_descriptions(skill_contents)

    @staticmethod
    def _build_skill_descriptions(skill_contents: list[dict[str, str]]) -> str:
        lines = []
        for skill in skill_contents:
            name = skill.get("name", "unknown")
            description = skill.get("description", "")
            lines.append(f"- {name}: {description}")
        return "\n".join(lines) if lines else "- general WoW coaching"

    async def generate(
        self,
        *,
        assistant_message: str,
        char_info: dict[str, str],
        active_build_id: str | None = None,
    ) -> list[dict[str, Any]]:
        settings = get_settings()

        prompt = _PROMPT_TEMPLATE.format(
            capabilities=self._skill_descriptions,
            wow_class=char_info.get("wow_class", "unknown"),
            spec=char_info.get("spec", "unknown"),
            role=char_info.get("role", "unknown"),
            build_context=active_build_id or "none",
            assistant_message=assistant_message[:2000],
        )

        try:
            response = await self._provider.client.responses.create(
                model=settings.openai_recommender_model,
                input=[{"role": "user", "content": prompt}],
                stream=False,
            )

            raw_text = response.output_text.strip()
            recommendations = json.loads(raw_text)

            if not isinstance(recommendations, list):
                logger.warning("Recommender returned non-list: %s", type(recommendations))
                return []

            return [
                {
                    "text": str(rec.get("text", ""))[:80],
                    "skill_hint": rec.get("skill_hint"),
                }
                for rec in recommendations[:2]
                if isinstance(rec, dict) and rec.get("text")
            ]

        except Exception:
            logger.exception("Recommendation generation failed")
            return []


def create_recommendation_service(
    *,
    provider: LLMProvider,
    skill_contents: list[dict[str, str]],
) -> RecommendationService:
    return RecommendationService(
        provider=provider,
        skill_contents=skill_contents,
    )
