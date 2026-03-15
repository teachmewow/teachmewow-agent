"""
Tool: build_lookup

Returns a build payload compatible with the frontend talent tree renderer.
No HelixDB dependency — uses PostgreSQL builds.tree_payload only.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from app.infrastructure.database.connection import get_session
from app.infrastructure.database.models import BuildModel


async def execute_build_lookup(
    build_id: str,
    char_info: object | None = None,
) -> str:
    """Pure function — no LangChain / Helix dependency."""
    normalized_char_info = _normalize_char(char_info)
    if not normalized_char_info:
        return json.dumps({"tool": "build_lookup", "error": "Missing character info."})

    resolved = await _fetch_build(
        build_id=build_id,
        char_info=normalized_char_info,
    )
    if resolved is None:
        return json.dumps({"tool": "build_lookup", "error": f"Build '{build_id}' not found."})

    decoded_nodes = _extract_decoded_nodes(
        resolved.get("selections"), resolved.get("selected_nodes"),
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
            "feedback": (
                "Build returned. Tell user: "
                "'Look at View Talent Tree to see the complete tree.'"
            ),
        },
        ensure_ascii=True,
    )


# -- Also expose the view function for the builds route -------------------

async def fetch_build_view_by_id(
    build_id: str,
    char_info: dict[str, str],
) -> dict[str, Any] | None:
    metadata = await _fetch_build(build_id=build_id, char_info=char_info)
    if metadata is None:
        return None

    tree_payload = _normalize_tree_payload(
        metadata.get("tree_payload"),
        str(metadata.get("tree_snapshot_id") or ""),
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
            "trees": tree_payload.get("trees", []) if tree_payload else [],
        },
    }


# -- internals ------------------------------------------------------------

def _normalize_char(char_info: object | None) -> dict[str, str]:
    if isinstance(char_info, dict):
        return {
            "class": str(char_info.get("class", "")).strip().lower(),
            "spec": str(char_info.get("spec", "")).strip().lower(),
            "role": str(char_info.get("role", "")).strip().lower(),
        }
    if char_info is not None:
        return {
            "class": str(getattr(char_info, "wow_class", "")).strip().lower(),
            "spec": str(getattr(char_info, "spec", "")).strip().lower(),
            "role": str(getattr(char_info, "role", "")).strip().lower(),
        }
    return {}


async def _fetch_build(build_id: str, char_info: dict[str, str]) -> dict[str, Any] | None:
    normalized_class = char_info.get("class", "").strip().lower()
    normalized_spec = char_info.get("spec", "").strip().lower()
    normalized_role = char_info.get("role", "").strip().lower()
    bid = str(build_id or "").strip()
    if not bid:
        return None

    async with get_session() as session:
        query = (
            select(BuildModel)
            .where(BuildModel.id == bid)
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
        "selected_nodes": build.selected_nodes if isinstance(build.selected_nodes, list) else [],
        "selections": build.selections if isinstance(build.selections, list) else [],
        "tree_payload": build.tree_payload,
        "tree_snapshot_id": build.tree_snapshot_id,
        "tree_snapshot_ids": build.tree_snapshot_ids,
        "wow_spec": str(build.wow_spec or normalized_spec),
        "updated_at": build.updated_at,
    }


def _extract_decoded_nodes(
    selections: object | None, selected_nodes: object | None,
) -> list[str]:
    decoded: list[str] = []
    if isinstance(selections, list):
        for entry in selections:
            if not isinstance(entry, dict):
                continue
            nid = str(entry.get("nodeId") or entry.get("node_id") or "").strip()
            if nid:
                decoded.append(nid)
    if not decoded and isinstance(selected_nodes, list):
        decoded = [str(i).strip() for i in selected_nodes if str(i).strip()]
    seen: set[str] = set()
    unique: list[str] = []
    for nid in decoded:
        if nid not in seen:
            seen.add(nid)
            unique.append(nid)
    return unique


def _normalize_tree_payload(tree_payload: object, fallback_tree_id: str | None) -> dict | None:
    if not isinstance(tree_payload, dict):
        return None
    if "trees" in tree_payload and isinstance(tree_payload.get("trees"), list):
        return tree_payload
    if "nodes" in tree_payload:
        tree_id = str(fallback_tree_id or "")
        return {
            "trees": [{
                "kind": "spec",
                "treeId": tree_id,
                "treeName": "",
                "columns": tree_payload.get("columns", 0),
                "rows": tree_payload.get("rows", 0),
                "nodes": tree_payload.get("nodes", []),
                "edges": tree_payload.get("edges", []),
                "selections": tree_payload.get("selections", []),
            }]
        }
    return None


# -- OpenAI function-tool JSON schema -------------------------------------

BUILD_LOOKUP_SCHEMA: dict = {
    "type": "function",
    "name": "build_lookup",
    "description": (
        "Get full details of a specific WoW build by its ID, "
        "including talent tree, import code, and metadata."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "build_id": {
                "type": "string",
                "description": "The build identifier to look up",
            },
        },
        "required": ["build_id"],
        "additionalProperties": False,
    },
}
