"""
Tool: build_rag_lookup

Combines build lookup with guide evidence retrieval from HelixDB.
"""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client

from .build_lookup import build_lookup


@tool
async def build_rag_lookup(
    question: str,
    environment: Literal["dg", "raid", "pvp"],
    mode: Literal["aoe", "single", "3x3", "2x2"],
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    scenario: str | None = None,
) -> str:
    """
    Resolve a build and return guide evidence for Q&A grounding.
    """
    build_result = await build_lookup.ainvoke(
        {
            "environment": environment,
            "mode": mode,
            "wow_class": wow_class,
            "wow_spec": wow_spec,
            "wow_role": wow_role,
            "scenario": scenario,
            "limit": 1,
        }
    )
    if not isinstance(build_result, str) or build_result == "No results found.":
        return "No build context found for the requested filters."

    parsed_build = _safe_parse_json(build_result)
    if not isinstance(parsed_build, dict):
        return "Build was found, but the payload is invalid."

    helix_client = get_helix_client()
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
        "build": parsed_build.get("build", {}),
        "evidence": {
            "claims": claims,
            "procedures": procedures,
        },
    }
    return json.dumps(payload, ensure_ascii=True)


def _safe_parse_json(value: str) -> dict | None:
    try:
        parsed = json.loads(value)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


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
