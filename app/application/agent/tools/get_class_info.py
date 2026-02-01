"""
Tool: get_class_info

RAG-first semantic retrieval for class/spec/role with always-on rerank.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client


@tool
def get_class_info(
    user_query: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    limit: int = 10,
) -> str:
    """
    Retrieve class/spec/role info using vector search + rerank.
    """
    helix_client = get_helix_client()
    candidate_limit = max(50, limit * 5)
    claim_result = helix_client.query(
        "SearchClaimChunksByText",
        {
            "text": user_query,
            "candidate_limit": candidate_limit,
            "result_limit": limit,
            "wow_class": wow_class,
            "wow_spec": wow_spec,
            "wow_role": wow_role,
        },
    )
    proc_result = helix_client.query(
        "SearchProcedureChunksByText",
        {
            "text": user_query,
            "candidate_limit": candidate_limit,
            "result_limit": limit,
            "wow_class": wow_class,
            "wow_spec": wow_spec,
            "wow_role": wow_role,
        },
    )

    claims = _extract_records(claim_result.data)
    procedures = _extract_records(proc_result.data)
    if not claims and not procedures:
        return "No results found."

    evidence_blocks = []
    evidence_blocks.extend(_build_claim_blocks(claims))
    evidence_blocks.extend(_build_procedure_blocks(procedures))
    return json.dumps({"evidence_blocks": evidence_blocks}, ensure_ascii=True, indent=2)


def _extract_records(payload: object) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict):
            candidate = payload[0]
            if "claims" in candidate and isinstance(candidate["claims"], list):
                return candidate["claims"]
            if "procs" in candidate and isinstance(candidate["procs"], list):
                return candidate["procs"]
        return payload
    if isinstance(payload, dict):
        for key in ("claims", "procs", "data", "records", "items", "results", "nodes"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        for value in payload.values():
            if isinstance(value, list):
                return value
        return [payload]
    return [payload]


def _build_claim_blocks(records: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    for record in records:
        blocks.append(
            {
                "type": "claim",
                "text": _get(record, "text", default="").strip(),
                "mode": _get(record, "mode"),
                "scenario": _get(record, "scenario"),
                "source_section": _get(record, "source_section"),
            }
        )
    return blocks


def _build_procedure_blocks(records: list[dict]) -> list[dict]:
    blocks: list[dict] = []
    for record in records:
        steps = _get(record, "steps") or []
        if isinstance(steps, str):
            steps = [steps]
        blocks.append(
            {
                "type": "procedure",
                "title": _get(record, "title", default="Procedure").strip(),
                "steps": steps,
                "mode": _get(record, "mode"),
                "scenario": _get(record, "scenario"),
                "source_section": _get(record, "source_section"),
            }
        )
    return blocks


def _get(record: dict, key: str, default: object | None = None) -> object | None:
    if isinstance(record, dict) and key in record:
        return record.get(key, default)
    return default


