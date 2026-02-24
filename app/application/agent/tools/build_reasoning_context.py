"""
Tool: build_reasoning_context

Returns compact, grounded context to explain how to play a selected build.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client

from .build_lookup import fetch_build_view_by_id


@tool
async def build_reasoning_context(
    question: str,
    char_info: dict[str, str],
    build_id: str | None = None,
    active_build_id: str | None = None,
    max_context_items: int = 6,
) -> str:
    """
    Return compact reasoning evidence for how to play a selected build.
    """
    selected_build_id = str(build_id or active_build_id or "").strip()
    if not selected_build_id:
        return "No active build selected."

    resolved = await fetch_build_view_by_id(build_id=selected_build_id, char_info=char_info)
    if resolved is None:
        return "No build context found for the selected build."

    helix_client = get_helix_client()
    wow_class = str(char_info.get("class", "")).strip().lower()
    wow_spec = str(char_info.get("spec", "")).strip().lower()
    wow_role = str(char_info.get("role", "")).strip().lower()
    capped = max(1, min(max_context_items, 12))

    claims = _query(
        helix_client,
        "SearchClaimChunksByText",
        {
            "text": question,
            "candidate_limit": 30,
            "result_limit": capped,
            "wow_class": wow_class,
            "wow_spec": wow_spec,
            "wow_role": wow_role,
        },
    )
    procedures = _query(
        helix_client,
        "SearchProcedureChunksByText",
        {
            "text": question,
            "candidate_limit": 30,
            "result_limit": capped,
            "wow_class": wow_class,
            "wow_spec": wow_spec,
            "wow_role": wow_role,
        },
    )

    payload = {
        "tool": "build_reasoning_context",
        "build_id": resolved["build_id"],
        "scenario": resolved["scenario"],
        "hero_talent": resolved["hero_talent"],
        "evidence_budget": capped,
        "evidence": {
            "claims": claims[:capped],
            "procedures": procedures[:capped],
        },
    }
    return json.dumps(payload, ensure_ascii=True)


def _query(helix_client, query_name: str, params: dict) -> list[dict]:
    try:
        result = helix_client.query(query_name, params)
    except Exception:
        return []
    data = getattr(result, "data", None)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("results", "items", "records", "nodes"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [data]
    return []
