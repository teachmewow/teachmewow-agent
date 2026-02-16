"""
Tool: build_rag_lookup

Combines build lookup with guide evidence retrieval from HelixDB.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client

from .build_lookup import fetch_build_view_by_id


@tool
async def build_rag_lookup(
    question: str,
    build_id: str,
    char_info: dict[str, str],
) -> str:
    """
    Resolve a build and return guide evidence for Q&A grounding.
    """
    resolved = await fetch_build_view_by_id(build_id=build_id, char_info=char_info)
    if resolved is None:
        return "No build context found for the requested filters."

    helix_client = get_helix_client()
    wow_class = str(char_info.get("class", "")).strip().lower()
    wow_spec = str(char_info.get("spec", "")).strip().lower()
    wow_role = str(char_info.get("role", "")).strip().lower()
    claims = _query_helix(
        helix_client=helix_client,
        query_name="SearchClaimChunksByText",
        params={
            "text": question,
            "candidate_limit": 30,
            "result_limit": 5,
            "wow_class": str(wow_class or "").strip().lower(),
            "wow_spec": str(wow_spec or "").strip().lower(),
            "wow_role": str(wow_role or "").strip().lower(),
        },
    )
    procedures = _query_helix(
        helix_client=helix_client,
        query_name="SearchProcedureChunksByText",
        params={
            "text": question,
            "candidate_limit": 30,
            "result_limit": 5,
            "wow_class": str(wow_class or "").strip().lower(),
            "wow_spec": str(wow_spec or "").strip().lower(),
            "wow_role": str(wow_role or "").strip().lower(),
        },
    )

    payload = {
        "tool": "build_rag_lookup",
        "build_id": resolved["build_id"],
        "build": resolved.get("build", {}),
        "evidence": {
            "claims": claims,
            "procedures": procedures,
        },
    }
    return json.dumps(payload, ensure_ascii=True)


def _query_helix(helix_client, query_name: str, params: dict) -> list[dict]:
    try:
        result = helix_client.query(query_name, params)
    except Exception:
        return []
    return _flatten_records(getattr(result, "data", None))


def _flatten_records(payload: object) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        flattened: list[dict] = []
        for item in payload:
            if isinstance(item, dict):
                flattened.append(item)
        return flattened
    if isinstance(payload, dict):
        for key in ("results", "items", "records", "nodes"):
            value = payload.get(key)
            if isinstance(value, list):
                return [v for v in value if isinstance(v, dict)]
        return [payload]
    return []
