"""
Tool: retrieve_helix_context

Retrieve HelixDB results and format a readable context string.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client
from app.application.agent.tools.helix_search import _build_query


@tool
def retrieve_helix_context(
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
    Retrieve HelixDB results and return a formatted context string.

    Use this tool to convert structured Helix nodes into readable text
    so the model can understand relationships without raw HelixQL.
    """
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
    helix_client = get_helix_client()
    result = helix_client.query(query_name, params)
    records = _extract_records(result.data)
    records = records[: max(limit, 0)] if isinstance(records, list) else records
    return _format_context(query_name, params, target, records)


def _format_context(
    query_name: str, params: dict, target: str, records: list | dict
) -> str:
    header = _format_header(query_name, params)
    if not records:
        return f"{header}\nNo results found."

    if not isinstance(records, list):
        records = [records]

    if target == "procedures":
        body = _format_procedures(records)
    else:
        body = _format_claims(records)
    return f"{header}\n{body}"


def _format_header(query_name: str, params: dict) -> str:
    class_tag = params.get("wow_class", "")
    spec_tag = params.get("wow_spec", "")
    role_tag = params.get("wow_role", "")
    filters = []
    for key in ("mode", "stance", "source_section", "patch_context"):
        if params.get(key):
            filters.append(f"{key}={params[key]}")
    filter_text = ", ".join(filters) if filters else "no extra filters"
    return (
        f"HelixContext[{query_name}] "
        f"tags=({class_tag}/{spec_tag}/{role_tag}) "
        f"filters=({filter_text})"
    )


def _format_claims(records: list[dict]) -> str:
    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        text = _get(record, "text", default="").strip()
        stance = _get(record, "stance")
        mode = _get(record, "mode")
        patch = _get(record, "patch_context")
        section = _get(record, "source_section")
        rationale = _get(record, "rationale_types")
        deps = _get(record, "dependencies")
        lines.append(f"Claim[{index}]: {text}")
        meta = _join_pairs(
            [
                ("stance", stance),
                ("mode", mode),
                ("patch", patch),
                ("section", section),
            ]
        )
        if meta:
            lines.append(f"  meta -> {meta}")
        evidence = _join_pairs(
            [
                ("rationale_types", rationale),
                ("dependencies", deps),
            ]
        )
        if evidence:
            lines.append(f"  evidence -> {evidence}")
    return "\n".join(lines)


def _format_procedures(records: list[dict]) -> str:
    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        title = _get(record, "title", default="Procedure").strip()
        steps = _get(record, "steps") or []
        if isinstance(steps, str):
            steps = [steps]
        step_text = " -> ".join(str(step) for step in steps) if steps else ""
        mode = _get(record, "mode")
        section = _get(record, "source_section")
        patch = _get(record, "patch_context")
        lines.append(f"Procedure[{index}]: {title}")
        if step_text:
            lines.append(f"  steps -> {step_text}")
        meta = _join_pairs(
            [
                ("mode", mode),
                ("section", section),
                ("patch", patch),
            ]
        )
        if meta:
            lines.append(f"  meta -> {meta}")
    return "\n".join(lines)


def _extract_records(payload: object) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "records", "items", "results", "nodes"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        for value in payload.values():
            if isinstance(value, list):
                return value
        return [payload]
    return [payload]


def _get(record: dict, key: str, default: object | None = None) -> object | None:
    if isinstance(record, dict) and key in record:
        return record.get(key, default)
    return default


def _join_pairs(pairs: list[tuple[str, object | None]]) -> str:
    parts = []
    for key, value in pairs:
        if value is None or value == "":
            continue
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item is not None)
        parts.append(f"{key}={value}")
    return ", ".join(parts)
