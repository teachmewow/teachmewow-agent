"""
Tool: guide_context_lookup

Retrieves guide chunks from Helix guide-v2 queries with deterministic citation metadata.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedState

from app.infrastructure.helix.client import get_helix_client


@tool
async def guide_context_lookup(
    question: str,
    source_id: str | None = None,
    result_limit: int = 6,
    char_info: Annotated[object, InjectedState("char_info")] = None,
    build_info: Annotated[object, InjectedState("build_info")] = None,
) -> str:
    """
    Fetch guide evidence for coaching responses.
    """
    normalized_question = str(question or "").strip()
    if not normalized_question:
        return "No results found."

    wow_class, wow_spec, wow_role = _normalize_char_info(char_info)
    if not wow_class or not wow_spec:
        return "No results found."

    capped_limit = max(1, min(int(result_limit or 1), 12))
    normalized_source = str(source_id or "").strip().lower() or None

    helix_client = get_helix_client()
    query_name = (
        "SearchGuideChunksByTextAndSource"
        if normalized_source
        else "SearchGuideChunksByText"
    )
    params: dict[str, Any] = {
        "text": normalized_question,
        "candidate_limit": max(30, capped_limit * 6),
        "result_limit": capped_limit,
        "wow_class": wow_class,
        "wow_spec": wow_spec,
        "wow_role": wow_role,
    }
    if normalized_source:
        params["source_id"] = normalized_source

    try:
        result = helix_client.query(query_name, params)
    except Exception:
        return "No results found."

    chunks = _extract_chunk_records(result.data)[:capped_limit]
    citations = []
    evidence = []
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        marker = _build_marker(chunk_id)
        heading_path = chunk.get("heading_path")
        if not isinstance(heading_path, list):
            heading_path = []
        heading_title = " > ".join(str(item) for item in heading_path if str(item).strip())
        snippet = str(chunk.get("content") or "").strip()
        citation = {
            "citation_id": marker,
            "source_doc_id": str(chunk.get("source_id") or ""),
            "source_title": heading_title or str(chunk.get("source_id") or ""),
            "span_ref": chunk_id,
            "snippet": snippet[:600],
            "source_url": str(chunk.get("source_url") or ""),
        }
        citations.append(citation)
        evidence.append(
            {
                "marker": marker,
                "chunk_id": chunk_id,
                "source_id": str(chunk.get("source_id") or ""),
                "heading_path": heading_path,
                "text": snippet,
            }
        )

    payload = {
        "tool": "guide_context_lookup",
        "question": normalized_question,
        "source_id": normalized_source,
        "result_limit": capped_limit,
        "active_build_id": _extract_build_id(build_info),
        "chunks": chunks,
        "evidence": evidence,
        "citations": citations,
        "response_metadata": {"citations": citations},
    }
    return json.dumps(payload, ensure_ascii=True)


def _normalize_char_info(char_info: object | None) -> tuple[str, str, str]:
    if isinstance(char_info, dict):
        wow_class = str(char_info.get("class", "")).strip().lower()
        wow_spec = str(char_info.get("spec", "")).strip().lower()
        wow_role = str(char_info.get("role", "")).strip().lower()
        return wow_class, wow_spec, wow_role or "dps"

    if char_info is None:
        return "", "", ""

    wow_class = str(getattr(char_info, "wow_class", "")).strip().lower()
    wow_spec = str(getattr(char_info, "spec", "")).strip().lower()
    wow_role = str(getattr(char_info, "role", "")).strip().lower()
    return wow_class, wow_spec, wow_role or "dps"


def _extract_build_id(build_info: object | None) -> str | None:
    if isinstance(build_info, dict):
        build_id = str(build_info.get("build_id") or "").strip()
        return build_id or None
    if build_info is None:
        return None
    build_id = str(getattr(build_info, "build_id", "")).strip()
    return build_id or None


def _build_marker(chunk_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(chunk_id).strip().lower()).strip("_")
    if not normalized:
        return "source_unknown"
    return f"source_{normalized}"


def _extract_chunk_records(payload: object) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        records: list[dict] = []
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("chunks"), list):
                for chunk in item.get("chunks", []):
                    if isinstance(chunk, dict):
                        records.append(chunk)
                continue
            if isinstance(item, dict):
                records.append(item)
        return records
    if isinstance(payload, dict):
        if isinstance(payload.get("chunks"), list):
            return [chunk for chunk in payload["chunks"] if isinstance(chunk, dict)]
        return [payload]
    return []
