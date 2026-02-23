"""
Tool: build_lookup

Returns a build payload compatible with the frontend talent tree renderer.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt.tool_node import InjectedState
from sqlalchemy import select

from app.infrastructure.database.connection import get_session
from app.infrastructure.database.models import BuildModel
from app.infrastructure.helix.client import get_helix_client


@tool
async def build_lookup(
    build_id: str,
    char_info: Annotated[object, InjectedState("char_info")] = None,
) -> str:
    """
    Resolve build metadata by stable build_id.
    """
    normalized_char_info: dict[str, str] = {}
    if isinstance(char_info, dict):
        normalized_char_info = {
            "class": str(char_info.get("class", "")),
            "spec": str(char_info.get("spec", "")),
            "role": str(char_info.get("role", "")),
        }
    elif char_info is not None:
        normalized_char_info = {
            "class": str(getattr(char_info, "wow_class", "")),
            "spec": str(getattr(char_info, "spec", "")),
            "role": str(getattr(char_info, "role", "")),
        }

    if not normalized_char_info:
        return "No results found."

    resolved = await fetch_build_metadata_by_id(
        build_id=build_id,
        char_info=normalized_char_info,
    )
    if resolved is None:
        return "No results found."

    decoded_nodes = _extract_decoded_nodes_from_context(
        resolved.get("selections"), resolved.get("selected_nodes")
    )

    return json.dumps(
        {
            "tool": "build_lookup",
            "build_id": resolved["build_id"],
            "hero_talent": resolved["hero_talent"],
            "scenario": resolved["scenario"],
            "environment": resolved["environment"],
            "patch": resolved["patch"],
            "source": resolved["source"],
            "import_code": resolved["import_code"],
            "decoded_nodes": decoded_nodes,
            "build_info": {
                "build_id": resolved["build_id"],
                "import_code": resolved["import_code"],
                "wow_class": normalized_char_info.get("class", ""),
                "spec": normalized_char_info.get("spec", ""),
                "decoded_nodes": decoded_nodes,
                "hero_talent": resolved["hero_talent"],
                "environment": resolved["environment"],
                "scenario": resolved["scenario"],
                "source": resolved["source"],
                "patch": resolved["patch"],
            },
            "citations": [],
            "response_metadata": {"citations": []},
            "feedback": (
                "Build returned. Tell user: "
                "'Look at View Talent Tree to see the complete tree.'"
            ),
        },
        ensure_ascii=True,
    )


async def fetch_build_metadata_by_id(
    build_id: str,
    char_info: dict[str, str],
) -> dict[str, Any] | None:
    normalized_class = str(char_info.get("class", "")).strip().lower()
    normalized_spec = str(char_info.get("spec", "")).strip().lower()
    normalized_role = str(char_info.get("role", "")).strip().lower()
    normalized_build_id = str(build_id or "").strip()
    if not normalized_build_id:
        return None

    async with get_session() as session:
        query = (
            select(BuildModel)
            .where(BuildModel.id == normalized_build_id)
            .where(BuildModel.wow_class == normalized_class)
            .where(BuildModel.wow_spec == normalized_spec)
            .where(BuildModel.wow_role == normalized_role)
            .limit(1)
        )
        result = await session.execute(query)
        build = result.scalars().first()

    if not build:
        return None

    return {
        "build_id": build.id,
        "import_code": build.import_code,
        "hero_talent": str(build.hero_talent or ""),
        "environment": str(build.environment or ""),
        "scenario": str(build.scenario or ""),
        "source": str(build.source or ""),
        "patch": str(build.patch or ""),
        "selected_nodes": build.selected_nodes
        if isinstance(build.selected_nodes, list)
        else [],
        "selections": build.selections if isinstance(build.selections, list) else [],
        "tree_payload": build.tree_payload,
        "tree_snapshot_id": build.tree_snapshot_id,
        "tree_snapshot_ids": build.tree_snapshot_ids,
        "wow_spec": str(build.wow_spec or normalized_spec),
        "updated_at": build.updated_at,
    }


async def fetch_build_view_by_id(
    build_id: str,
    char_info: dict[str, str],
) -> dict[str, Any] | None:
    metadata = await fetch_build_metadata_by_id(build_id=build_id, char_info=char_info)
    if metadata is None:
        return None

    tree_payload = _normalize_tree_payload(
        metadata.get("tree_payload"),
        str(metadata.get("tree_snapshot_id") or ""),
    )
    if tree_payload is None:
        tree_payload = _build_tree_payload(
            metadata.get("selections"),
            metadata.get("selected_nodes"),
            metadata.get("tree_snapshot_ids"),
            metadata.get("tree_snapshot_id"),
        )

    return {
        "build_id": metadata["build_id"],
        "import_code": metadata["import_code"],
        "hero_talent": metadata["hero_talent"],
        "environment": metadata["environment"],
        "scenario": metadata["scenario"],
        "source": metadata["source"],
        "patch": metadata["patch"],
        "selected_nodes": metadata["selected_nodes"],
        "selections": metadata["selections"],
        "build": {
            "importString": metadata["import_code"],
            "specId": metadata["wow_spec"],
            "scenario": metadata["scenario"],
            "source": metadata["source"],
            "updatedAt": (
                metadata["updated_at"].isoformat() if metadata["updated_at"] else None
            ),
            "patch": metadata["patch"],
            "trees": tree_payload.get("trees", []),
        },
    }


def _extract_decoded_nodes_from_context(
    selections: object | None, selected_nodes: object | None
) -> list[str]:
    decoded_nodes: list[str] = []
    if isinstance(selections, list):
        for entry in selections:
            if not isinstance(entry, dict):
                continue
            node_id = str(entry.get("nodeId") or entry.get("node_id") or "").strip()
            if node_id:
                decoded_nodes.append(node_id)
    if not decoded_nodes and isinstance(selected_nodes, list):
        decoded_nodes = [
            str(item).strip() for item in selected_nodes if str(item).strip()
        ]

    # Preserve order and drop duplicates.
    unique_nodes: list[str] = []
    seen: set[str] = set()
    for node_id in decoded_nodes:
        if node_id in seen:
            continue
        seen.add(node_id)
        unique_nodes.append(node_id)
    return unique_nodes


def _build_tree_payload(
    selections_payload: object | None,
    selected_nodes_payload: object | None,
    tree_snapshot_ids_payload: object | None,
    tree_snapshot_id_payload: object | None,
) -> dict:
    helix_client = get_helix_client()
    selections = _normalize_selections(selections_payload, selected_nodes_payload)
    tree_entries = _coerce_tree_entries(tree_snapshot_ids_payload, tree_snapshot_id_payload)
    trees: list[dict] = []
    for entry in tree_entries:
        tree_id = entry.get("id", "")
        if not tree_id:
            continue
        result = helix_client.query("FetchTalentTreeNodes", {"tree_id": tree_id})
        node_records = _extract_records(result.data)
        trees.append(
            _build_tree_payload_from_records(
                node_records,
                selections,
                kind=entry.get("kind", "spec"),
                tree_id=str(tree_id),
                tree_name=entry.get("name", ""),
            )
        )

    return {"trees": trees}


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


def _build_tree_payload_from_records(
    node_records: list,
    selections: list[dict],
    kind: str,
    tree_id: str,
    tree_name: str = "",
) -> dict:
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

        icon_name = icon or "inv_misc_questionmark"
        nodes.append(
            {
                "id": talent_node_id,
                "name": name or f"TalentNode {talent_node_id}",
                "icon": icon_name,
                "iconUrl": f"https://render.worldofwarcraft.com/icons/56/{icon_name}.jpg",
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

    filtered_selections = [
        selection for selection in selections if selection.get("nodeId") in node_lookup
    ]

    return {
        "kind": kind,
        "treeId": tree_id,
        "treeName": tree_name,
        "columns": max_col + col_offset + 1 if max_col >= 0 else 0,
        "rows": max_row + row_offset + 1 if max_row >= 0 else 0,
        "nodes": nodes,
        "edges": edges,
        "selections": filtered_selections,
    }


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


def _normalize_tree_payload(tree_payload: object, fallback_tree_id: str | None) -> dict | None:
    if not isinstance(tree_payload, dict):
        return None
    if "trees" in tree_payload and isinstance(tree_payload.get("trees"), list):
        return tree_payload
    if "nodes" in tree_payload:
        tree_id = str(fallback_tree_id or "")
        return {
            "trees": [
                {
                    "kind": "spec",
                    "treeId": tree_id,
                    "treeName": "",
                    "columns": tree_payload.get("columns", 0),
                    "rows": tree_payload.get("rows", 0),
                    "nodes": tree_payload.get("nodes", []),
                    "edges": tree_payload.get("edges", []),
                    "selections": tree_payload.get("selections", []),
                }
            ]
        }
    return None


def _coerce_tree_entries(
    tree_snapshot_ids: object | None, fallback_tree_id: object | None
) -> list[dict]:
    entries: list[dict] = []
    if isinstance(tree_snapshot_ids, list):
        for entry in tree_snapshot_ids:
            if isinstance(entry, dict) and entry.get("id"):
                entries.append(
                    {
                        "id": str(entry.get("id")),
                        "kind": str(entry.get("kind") or "spec"),
                        "name": str(entry.get("name") or ""),
                    }
                )
            elif isinstance(entry, str):
                entries.append({"id": entry, "kind": "spec", "name": ""})
    if not entries and fallback_tree_id:
        entries.append({"id": str(fallback_tree_id), "kind": "spec", "name": ""})
    return entries


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
