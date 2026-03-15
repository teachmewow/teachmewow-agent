"""
Tool: list_builds

Lists available build IDs for character context and optional filters.
"""

from __future__ import annotations

import json
from typing import Any

from langsmith import traceable
from sqlalchemy import select

from app.infrastructure.database.connection import get_session
from app.infrastructure.database.models import BuildModel

from ._char_utils import normalize_char
from .registry import ToolContext


@traceable(run_type="tool", name="list_builds")
async def execute_list_builds(
    environment: str | None = None,
    mode: str | None = None,
    hero_talent: str | None = None,
    char_info: object | None = None,
) -> str:
    """Pure function — no LangChain dependency."""
    normalized_class, normalized_spec, normalized_role = normalize_char(char_info)
    if not normalized_class or not normalized_spec or not normalized_role:
        return json.dumps({"tool": "list_builds", "count": 0, "builds": []})

    query = (
        select(BuildModel)
        .where(BuildModel.wow_class == normalized_class)
        .where(BuildModel.wow_spec == normalized_spec)
        .where(BuildModel.wow_role == normalized_role)
        .order_by(BuildModel.updated_at.desc())
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


# -- Handler class for ToolRegistry ----------------------------------------

class ListBuildsHandler:
    name = "list_builds"
    schema: dict[str, Any] = {
        "type": "function",
        "name": "list_builds",
        "description": (
            "Returns ALL builds for the user's class/spec in a single call. "
            "Call with an empty object {} to get everything. "
            "Optional filters narrow results only when the user explicitly asks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "environment": {
                    "type": "string",
                    "description": "Optional: raid, mythic_plus, or delves",
                },
                "mode": {
                    "type": "string",
                    "description": "Optional: single or aoe",
                },
                "hero_talent": {
                    "type": "string",
                    "description": "Optional: e.g. slayer, colossus",
                },
            },
            "additionalProperties": False,
        },
    }

    async def execute(self, args: dict[str, Any], ctx: ToolContext) -> str:
        return await execute_list_builds(
            environment=args.get("environment"),
            mode=args.get("mode"),
            hero_talent=args.get("hero_talent"),
            char_info=ctx.char_info,
        )


LIST_BUILDS_SCHEMA = ListBuildsHandler.schema
