"""
Tool: search_helix

Searches HelixDB for claims/procedures filtered by class/spec/role.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client


@tool
def search_helix(
    user_query: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    limit: int = 10,
) -> str:
    """
    Search HelixDB for claims/procedures filtered by tags.

    Args:
        user_query: Natural language user query
        wow_class: WoW class context
        wow_spec: WoW spec context
        wow_role: WoW role context
        limit: Max results to return
    """
    try:
        helix_client = get_helix_client()
        if wow_class and wow_spec:
            result = helix_client.query(
                "SearchClaimsByTags",
                {
                    "wow_class": wow_class,
                    "wow_spec": wow_spec,
                    "wow_role": wow_role,
                },
            )
        else:
            result = helix_client.query(
                "SearchClaimsByRole",
                {
                    "wow_role": wow_role,
                },
            )
        return json.dumps(result.data, ensure_ascii=True)
    except Exception as exc:
        return f"Helix search error: {exc}"
