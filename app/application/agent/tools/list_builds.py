"""
Tool: list_builds

Lists available build IDs for character context and optional filters.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedState
from sqlalchemy import select

from app.infrastructure.database.connection import get_session
from app.infrastructure.database.models import BuildModel


@tool
async def list_builds(
    environment: Literal["raid", "mythic_plus", "delves"] | None = None,
    mode: Literal["single", "aoe"] | None = None,
    hero_talent: Literal["slayer", "colossus"] | None = None,
    limit: int = 10,
    char_info: Annotated[object, InjectedState("char_info")] = None,
) -> str:
    """
    List available builds for a class/spec/role with optional filters.
    """
    normalized_class = ""
    normalized_spec = ""
    normalized_role = ""
    if isinstance(char_info, dict):
        normalized_class = str(char_info.get("class", "")).strip().lower()
        normalized_spec = str(char_info.get("spec", "")).strip().lower()
        normalized_role = str(char_info.get("role", "")).strip().lower()
    elif char_info is not None:
        normalized_class = str(getattr(char_info, "wow_class", "")).strip().lower()
        normalized_spec = str(getattr(char_info, "spec", "")).strip().lower()
        normalized_role = str(getattr(char_info, "role", "")).strip().lower()

    if not normalized_class or not normalized_spec or not normalized_role:
        return "No results found."

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
