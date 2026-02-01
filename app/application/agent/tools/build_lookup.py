"""
Tool: build_lookup

Returns a build payload compatible with the frontend talent tree renderer.
"""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool
from sqlalchemy import select

from app.infrastructure.database.connection import get_session
from app.infrastructure.database.models import BuildModel
from app.infrastructure.helix.client import get_helix_client


@tool
async def build_lookup(
    environment: Literal["dg", "raid", "pvp"],
    mode: Literal["aoe", "single", "3x3", "2x2"],
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    scenario: str | None = None,
    limit: int = 1,
) -> str:
    """
    Lookup builds and return JSON payload for talent tree rendering.
    """
    normalized_env = _normalize_environment(environment)
    normalized_mode = _normalize_build_mode(mode)
    normalized_scenario = scenario or f"{normalized_env} {normalized_mode}"

    async with get_session() as session:
        query = (
            select(BuildModel)
            .where(BuildModel.wow_class == wow_class)
            .where(BuildModel.wow_spec == wow_spec)
            .where(BuildModel.wow_role == wow_role)
            .where(BuildModel.environment == normalized_env)
            .where(BuildModel.build_mode == normalized_mode)
            .where(BuildModel.scenario == normalized_scenario)
            .order_by(BuildModel.updated_at.desc())
            .limit(max(limit, 1))
        )
        result = await session.execute(query)
        build = result.scalars().first()

    if not build:
        return "No results found."

    tree_payload = build.tree_payload or _build_tree_payload(build)
    output = {
        "tool": "build_lookup",
        "build": {
            "importString": build.import_code,
            "specId": wow_spec,
            "scenario": normalized_scenario,
            "source": build.source or "",
            "updatedAt": build.updated_at.isoformat() if build.updated_at else None,
            "patch": build.patch or "",
            "tree": tree_payload,
        },
    }
    return json.dumps(output, ensure_ascii=True)


def _build_tree_payload(build: BuildModel) -> dict:
    helix_client = get_helix_client()
    tree_id = str(build.tree_snapshot_id or "")
    node_records = []
    if tree_id:
        result = helix_client.query("FetchTalentTreeNodes", {"tree_id": tree_id})
        node_records = _extract_records(result.data)

    nodes = []
    max_col = 0
    max_row = 0
    min_col = None
    min_row = None
    for record in node_records:
        props = _node_props(record)
        display_col = _to_int(props.get("display_col"), default=-1)
        display_row = _to_int(props.get("display_row"), default=-1)
        if display_col >= 0 and display_row >= 0:
            max_col = max(max_col, display_col)
            max_row = max(max_row, display_row)
            min_col = display_col if min_col is None else min(min_col, display_col)
            min_row = display_row if min_row is None else min(min_row, display_row)

    col_offset = 1 if min_col == 0 else 0
    row_offset = 1 if min_row == 0 else 0

    for record in node_records:
        props = _node_props(record)
        talent_node_id = str(props.get("talent_node_id") or "")
        name = str(props.get("name") or "").strip()
        description = str(props.get("description") or "").strip()
        node_type = str(props.get("node_type") or "passive").strip().lower()
        icon = str(props.get("icon") or "inv_misc_questionmark").strip()
        max_rank = _to_int(props.get("max_rank"), default=1)
        display_col = _to_int(props.get("display_col"), default=-1)
        display_row = _to_int(props.get("display_row"), default=-1)

        if not talent_node_id or display_col < 0 or display_row < 0:
            continue

        nodes.append(
            {
                "id": talent_node_id,
                "name": name or f"TalentNode {talent_node_id}",
                "icon": icon,
                "maxRank": max_rank,
                "position": {
                    "column": display_col + col_offset,
                    "row": display_row + row_offset,
                },
                "entry": {
                    "id": talent_node_id,
                    "type": node_type or "passive",
                    "description": description,
                },
                "unlocks": [str(item) for item in props.get("unlocks", []) or []],
            }
        )

    edges = []
    node_lookup = {node["id"] for node in nodes}
    for node in nodes:
        for child_id in node.get("unlocks", []) or []:
            if child_id in node_lookup:
                edges.append({"from": node["id"], "to": child_id})

    selections = _normalize_selections(build.selections, build.selected_nodes)

    return {
        "columns": max_col + col_offset + 1 if max_col >= 0 else 0,
        "rows": max_row + row_offset + 1 if max_row >= 0 else 0,
        "nodes": nodes,
        "edges": edges,
        "selections": selections,
    }


def _normalize_selections(
    selections: object | None, selected_nodes: object | None
) -> list[dict]:
    if isinstance(selections, list) and selections:
        normalized = []
        for entry in selections:
            if isinstance(entry, dict) and entry.get("nodeId"):
                normalized.append(
                    {
                        "nodeId": str(entry.get("nodeId")),
                        "rank": int(entry.get("rank") or 1),
                    }
                )
            elif isinstance(entry, dict) and entry.get("node_id"):
                normalized.append(
                    {
                        "nodeId": str(entry.get("node_id")),
                        "rank": int(entry.get("rank") or 1),
                    }
                )
        if normalized:
            return normalized

    nodes = []
    if isinstance(selected_nodes, list):
        nodes = [str(item) for item in selected_nodes if str(item).strip()]
    return [{"nodeId": node_id, "rank": 1} for node_id in nodes]


def _node_props(node: dict) -> dict:
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            return props
        return node
    return {}


def _extract_records(payload: object) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict):
            candidate = payload[0]
            if "nodes" in candidate and isinstance(candidate["nodes"], list):
                return candidate["nodes"]
        return payload
    if isinstance(payload, dict):
        for key in ("nodes", "records", "items", "results"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        for value in payload.values():
            if isinstance(value, list):
                return value
        return [payload]
    return [payload]


def _normalize_environment(value: str) -> str:
    lowered = str(value).strip().lower()
    if lowered in {"dg", "dungeon", "mythic", "m+"}:
        return "dungeon"
    if lowered in {"raid", "raiding"}:
        return "raid"
    if lowered in {"pvp", "arena", "bg"}:
        return "pvp"
    return lowered or "general"


def _normalize_build_mode(value: str) -> str:
    lowered = str(value).strip().lower()
    if lowered in {"single", "single_target"}:
        return "single"
    if lowered in {"aoe", "cleave"}:
        return "aoe"
    if lowered in {"3x3", "3v3"}:
        return "3x3"
    if lowered in {"2x2", "2v2"}:
        return "2x2"
    return lowered


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
