"""
Tool: search_helix

Search HelixDB for structured WoW knowledge.
Use for claims (facts, recommendations) or procedures (step-by-step).
"""

from __future__ import annotations

import json

from typing import Literal

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client


@tool
def search_helix(
    user_query: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    target: Literal["claims", "procedures"] = "claims",
    mode: str | None = None,
    stance: str | None = None,
    source_section: str | None = None,
    patch_context: str | None = None,
    limit: int = 10,
) -> str:
    """
    Search HelixDB for WoW knowledge filtered by class/spec/role.

    Use cases:
    - target="claims" for recommendations or facts.
    - target="procedures" for step-by-step rotations or priorities.

    Optional filters:
    - mode: game mode (e.g. mythic_plus, raid, pvp, dungeon)
    - stance: recommendation stance (recommended/optional/avoid/unknown)
    - source_section: section name (rotation, talents, stats, gear, etc.)
    - patch_context: patch or version string
    """
    try:
        helix_client = get_helix_client()
        query_name, params = _build_query(
            target=target,
            wow_class=wow_class,
            wow_spec=wow_spec,
            wow_role=wow_role,
            mode=mode,
            stance=stance,
            source_section=source_section,
            patch_context=patch_context,
        )
        result = helix_client.query(query_name, params)
        return json.dumps(result.data, ensure_ascii=True)
    except Exception as exc:
        return f"Helix search error: {exc}"


def _build_query(
    target: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    mode: str | None,
    stance: str | None,
    source_section: str | None,
    patch_context: str | None,
) -> tuple[str, dict]:
    has_tags = bool(wow_class and wow_spec)
    params = {
        "wow_class": wow_class,
        "wow_spec": wow_spec,
        "wow_role": wow_role,
    }

    if target == "procedures":
        if has_tags:
            if mode:
                params["mode"] = mode
                return "SearchProceduresByTagsAndMode", params
            if source_section:
                params["source_section"] = source_section
                return "SearchProceduresByTagsAndSection", params
            return "SearchProceduresByTags", params
        return "SearchProceduresByRole", {"wow_role": wow_role}

    if has_tags:
        if mode:
            params["mode"] = mode
            return "SearchClaimsByTagsAndMode", params
        if stance:
            params["stance"] = stance
            return "SearchClaimsByTagsAndStance", params
        if source_section:
            params["source_section"] = source_section
            return "SearchClaimsByTagsAndSection", params
        if patch_context:
            params["patch_context"] = patch_context
            return "SearchClaimsByTagsAndPatch", params
        return "SearchClaimsByTags", params
    return "SearchClaimsByRole", {"wow_role": wow_role}
