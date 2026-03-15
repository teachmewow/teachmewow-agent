"""
Tool: list_builds

Lists available build IDs for character context and optional filters.
"""

from __future__ import annotations

import json

from langsmith import traceable
from sqlalchemy import select

from app.infrastructure.database.connection import get_session
from app.infrastructure.database.models import BuildModel


def _normalize_char(char_info: object | None) -> tuple[str, str, str]:
    if isinstance(char_info, dict):
        return (
            str(char_info.get("class", "")).strip().lower(),
            str(char_info.get("spec", "")).strip().lower(),
            str(char_info.get("role", "")).strip().lower(),
        )
    if char_info is not None:
        return (
            str(getattr(char_info, "wow_class", "")).strip().lower(),
            str(getattr(char_info, "spec", "")).strip().lower(),
            str(getattr(char_info, "role", "")).strip().lower(),
        )
    return ("", "", "")


@traceable(run_type="tool", name="list_builds")
async def execute_list_builds(
    environment: str | None = None,
    mode: str | None = None,
    hero_talent: str | None = None,
    limit: int = 10,
    char_info: object | None = None,
) -> str:
    """Pure function — no LangChain dependency."""
    normalized_class, normalized_spec, normalized_role = _normalize_char(char_info)
    if not normalized_class or not normalized_spec or not normalized_role:
        return json.dumps({"tool": "list_builds", "count": 0, "builds": []})

    query = (
        select(BuildModel)
        .where(BuildModel.wow_class == normalized_class)
        .where(BuildModel.wow_spec == normalized_spec)
        .where(BuildModel.wow_role == normalized_role)
        .order_by(BuildModel.updated_at.desc())
        .limit(max(limit, 1))
    )

    if environment:
        query = query.where(BuildModel.environment == environment)
    if mode:
        query = query.where(BuildModel.build_mode == mode)
    if hero_talent:
        query = query.where(BuildModel.hero_talent == hero_talent)

    async with get_session() as session:
        result = await session.execute(query)
        builds = result.scalars().all()

    payload = {
        "tool": "list_builds",
        "count": len(builds),
        "builds": [
            {
                "build_id": build.id,
                "hero_talent": build.hero_talent or "",
                "environment": build.environment,
                "mode": build.build_mode,
                "scenario": build.scenario,
                "patch": build.patch or "",
                "source": build.source or "",
                "updated_at": build.updated_at.isoformat() if build.updated_at else None,
            }
            for build in builds
        ],
    }
    return json.dumps(payload, ensure_ascii=True)


# -- OpenAI function-tool JSON schema ------------------------------------

LIST_BUILDS_SCHEMA: dict = {
    "type": "function",
    "name": "list_builds",
    "description": (
        "List available WoW builds for the user's class/spec, "
        "optionally filtered by environment, mode, and hero talent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "environment": {
                "type": "string",
                "enum": ["raid", "mythic_plus", "delves"],
                "description": "Filter by game content type",
            },
            "mode": {
                "type": "string",
                "enum": ["single", "aoe"],
                "description": "Filter by single-target or AoE",
            },
            "hero_talent": {
                "type": "string",
                "enum": ["slayer", "colossus"],
                "description": "Filter by hero talent path",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default 10)",
                "default": 10,
            },
        },
        "additionalProperties": False,
    },
}
