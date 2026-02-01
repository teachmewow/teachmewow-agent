"""
Formatting helpers for Helix tool outputs.
"""

from __future__ import annotations

from typing import Iterable


def format_simple_context(
    query_name: str, params: dict, target: str, records: list | dict
) -> str:
    header = _format_header("HelixContext", query_name, params)
    if not records:
        return f"{header}\nNo results found."

    if not isinstance(records, list):
        records = [records]

    if target == "procedures":
        body = _format_procedures(records)
    else:
        body = _format_claims(records)
    return f"{header}\n{body}"


def format_graph_context(
    query_name: str, params: dict, target: str, records: list | dict
) -> str:
    header = _format_header("HelixGraphContext", query_name, params)
    if not records:
        return f"{header}\nNo results found."

    if not isinstance(records, list):
        records = [records]

    if target == "procedures":
        body = _format_graph_procedures(records)
    else:
        body = _format_graph_claims(records)
    return f"{header}\n{body}"


def format_hybrid_context(
    header: str, direct_context: str, related_context: str
) -> str:
    sections = [header]
    if direct_context:
        sections.append("DirectMatches:")
        sections.append(direct_context)
    if related_context:
        sections.append("RelatedContext:")
        sections.append(related_context)
    return "\n".join(sections)


def format_header(prefix: str, query_name: str, params: dict) -> str:
    return _format_header(prefix, query_name, params)


def extract_records(payload: object) -> list:
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


def _format_header(prefix: str, query_name: str, params: dict) -> str:
    class_tag = params.get("wow_class", "")
    spec_tag = params.get("wow_spec", "")
    role_tag = params.get("wow_role", "")
    filters = []
    for key in ("mode", "stance", "source_section", "patch_context"):
        if params.get(key):
            filters.append(f"{key}={params[key]}")
    filter_text = ", ".join(filters) if filters else "no extra filters"
    return (
        f"{prefix}[{query_name}] "
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


def _format_graph_claims(records: list[dict]) -> str:
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
        related_lines = _format_related_groups(
            [
                ("abilities", _format_named_list(record.get("abilities"))),
                ("talents", _format_named_list(record.get("talents"))),
                ("builds", _format_build_list(record.get("builds"))),
                ("game_modes", _format_named_list(record.get("game_modes"))),
                ("patches", _format_patch_list(record.get("patches"))),
                ("explains", _format_named_list(record.get("explains"))),
                ("recommends", _format_named_list(record.get("recommends"))),
                ("best_for", _format_named_list(record.get("best_for"))),
            ]
        )
        if related_lines:
            lines.extend(related_lines)
    return "\n".join(lines)


def _format_graph_procedures(records: list[dict]) -> str:
    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        title = _get(record, "title", default="Procedure").strip()
        steps = _get(record, "steps") or []
        if isinstance(steps, str):
            steps = [steps]
        step_text = " -> ".join(str(step) for step in steps) if steps else ""
        mode = _get(record, "mode")
        section = _get(record, "source_section")
        lines.append(f"Procedure[{index}]: {title}")
        if step_text:
            lines.append(f"  steps -> {step_text}")
        meta = _join_pairs([("mode", mode), ("section", section)])
        if meta:
            lines.append(f"  meta -> {meta}")
        related_lines = _format_related_groups(
            [
                ("abilities", _format_named_list(record.get("abilities"))),
                ("talents", _format_named_list(record.get("talents"))),
                ("builds", _format_build_list(record.get("builds"))),
                ("game_modes", _format_named_list(record.get("game_modes"))),
            ]
        )
        if related_lines:
            lines.extend(related_lines)
    return "\n".join(lines)


def _format_related_groups(groups: Iterable[tuple[str, str]]) -> list[str]:
    lines: list[str] = []
    for label, value in groups:
        if value:
            lines.append(f"  {label} -> {value}")
    return lines


def _format_named_list(items: object) -> str:
    return _join_named_items(items)


def _format_build_list(items: object) -> str:
    if not items:
        return ""
    if not isinstance(items, list):
        items = [items]
    parts = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or ""
            playstyle = item.get("playstyle") or ""
            if name and playstyle:
                parts.append(f"{name} ({playstyle})")
            elif name:
                parts.append(name)
            elif playstyle:
                parts.append(playstyle)
            else:
                parts.append(str(item))
        else:
            parts.append(str(item))
    return ", ".join(part for part in parts if part)


def _format_patch_list(items: object) -> str:
    if not items:
        return ""
    if not isinstance(items, list):
        items = [items]
    versions = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("patch_version") or item.get("name")
            if value:
                versions.append(str(value))
            else:
                versions.append(str(item))
        else:
            versions.append(str(item))
    return ", ".join(version for version in versions if version)


def _join_named_items(items: object) -> str:
    if not items:
        return ""
    if not isinstance(items, list):
        items = [items]
    parts = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("name")
            if value:
                parts.append(str(value))
            else:
                parts.append(str(item))
        else:
            parts.append(str(item))
    return ", ".join(part for part in parts if part)


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
