"""
Tool: get_build

Retrieve build definitions and related talents/abilities.
"""

from __future__ import annotations

from typing import Literal

import json

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client


@tool
def get_build(
    environment: Literal["dg", "raid", "pvp"],
    mode: Literal["aoe", "single", "3x3", "2x2"],
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    limit: int = 3,
) -> str:
    """
    Retrieve build info for an environment/mode and expand with talents/abilities.
    """
    helix_client = get_helix_client()
    normalized_env = _normalize_environment(environment)
    normalized_mode = _normalize_build_mode(mode)
    build_result = helix_client.query(
        "SearchBuildsByFilters",
        {
            "wow_class": wow_class,
            "wow_spec": wow_spec,
            "wow_role": wow_role,
            "environment": normalized_env,
            "build_mode": normalized_mode,
        },
    )
    builds = _extract_records(build_result.data)
    if not builds:
        return "No results found."

    build_blocks: list[dict] = []
    for index, build in enumerate(builds[: max(limit, 0)], start=1):
        build_id = _get(build, "id") or _get(build, "ID")
        name = _get(build, "name", default="Build").strip()
        tree_snapshot_ids = _normalize_tree_snapshot_ids(build)
        selected_nodes = _normalize_selected_nodes(_get(build, "selected_nodes"))
        block = {
            "index": index,
            "name": name,
            "environment": normalized_env,
            "mode": normalized_mode,
            "import_code": _get(build, "import_code"),
            "playstyle": _get(build, "playstyle"),
            "selected_nodes": selected_nodes,
            "tree_snapshot_ids": tree_snapshot_ids,
            "talents": [],
            "abilities": [],
        }
        if build_id:
            relation_result = helix_client.query(
                "FetchBuildRelations", {"build_id": str(build_id)}
            )
            relation_payload = _first_dict(relation_result.data) or {}
            talents = relation_payload.get("talents", [])
            abilities = relation_payload.get("abilities", [])
            block["talents"] = _collect_named(talents)
            block["abilities"] = _collect_named(abilities)
        if tree_snapshot_ids and selected_nodes:
            tree_nodes = _fetch_tree_nodes(helix_client, tree_snapshot_ids)
            block["tree_ascii"] = _render_tree_ascii(tree_nodes, selected_nodes)
        build_blocks.append(block)
    return json.dumps({"builds": build_blocks}, ensure_ascii=True, indent=2)


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


def _extract_records(payload: object) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], dict):
            candidate = payload[0]
            if "builds" in candidate and isinstance(candidate["builds"], list):
                return candidate["builds"]
        return payload
    if isinstance(payload, dict):
        for key in ("builds", "records", "items", "results", "nodes"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
        for value in payload.values():
            if isinstance(value, list):
                return value
        return [payload]
    return [payload]


def _first_dict(payload: object) -> dict | None:
    if payload is None:
        return None
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                return item
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _get(record: dict, key: str, default: object | None = None) -> object | None:
    if isinstance(record, dict) and key in record:
        return record.get(key, default)
    return default


def _collect_named(items: object) -> list[str]:
    if not items:
        return []
    if not isinstance(items, list):
        items = [items]
    parts = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
            parts.append(str(name) if name else str(item))
        else:
            parts.append(str(item))
    return [part for part in parts if part]


def _normalize_tree_snapshot_ids(build: dict) -> list[str]:
    raw_ids = _get(build, "tree_snapshot_ids")
    if isinstance(raw_ids, list):
        return [str(item) for item in raw_ids if str(item).strip()]
    fallback = _get(build, "tree_snapshot_id")
    return _split_csv(str(raw_ids or fallback or ""))


def _normalize_selected_nodes(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return _split_csv(str(value))


def _fetch_tree_nodes(helix_client, tree_ids: list[str]) -> list:
    nodes: list = []
    for tree_id in tree_ids:
        if not tree_id:
            continue
        result = helix_client.query("FetchTalentTreeNodes", {"tree_id": tree_id})
        nodes.extend(_extract_records(result.data))
    return nodes


def _render_tree_ascii(tree_nodes: list, selected_nodes: list[str]) -> str:
    if not tree_nodes or not selected_nodes:
        return ""
    selected_set = {str(item) for item in selected_nodes if str(item).strip()}
    nodes_by_tree: dict[str, list[dict]] = {}
    for node in tree_nodes:
        props = _node_props(node)
        tree_id = str(props.get("tree_id") or "").strip()
        talent_node_id = str(props.get("talent_node_id") or "").strip()
        if not tree_id or not talent_node_id:
            continue
        entry = {
            "talent_node_id": talent_node_id,
            "name": str(props.get("name") or ""),
            "tree_kind": str(props.get("tree_kind") or ""),
            "display_row": _to_int(props.get("display_row"), default=10**9),
            "display_col": _to_int(props.get("display_col"), default=10**9),
            "unlocks": _normalize_list(props.get("unlocks")),
            "locked_by": _normalize_list(props.get("locked_by")),
        }
        nodes_by_tree.setdefault(tree_id, []).append(entry)
    sections: list[str] = []
    for tree_id, entries in sorted(nodes_by_tree.items(), key=lambda item: item[0]):
        index = {entry["talent_node_id"]: entry for entry in entries}
        selected_in_tree = {tid for tid in selected_set if tid in index}
        if not selected_in_tree:
            continue
        included = _collect_ancestors(index, selected_in_tree)
        children_map = _build_children_map(index, included)
        roots = _find_roots(index, included)
        tree_kind = index[next(iter(included))].get("tree_kind")
        header = f"Tree {tree_id}"
        if tree_kind:
            header = f"{header} ({tree_kind})"
        lines = [header]
        for idx, root_id in enumerate(roots):
            is_last = idx == len(roots) - 1
            _render_tree_lines(
                index,
                children_map,
                root_id,
                prefix="",
                is_last=is_last,
                lines=lines,
            )
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _collect_ancestors(index: dict[str, dict], selected: set[str]) -> set[str]:
    included: set[str] = set()
    stack = list(selected)
    while stack:
        node_id = stack.pop()
        if node_id in included:
            continue
        included.add(node_id)
        for parent in index[node_id].get("locked_by", []):
            if parent in index:
                stack.append(parent)
    return included


def _build_children_map(index: dict[str, dict], included: set[str]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {node_id: [] for node_id in included}
    for node_id in included:
        for child_id in index[node_id].get("unlocks", []):
            if child_id in included:
                children[node_id].append(child_id)
    for node_id, child_list in children.items():
        child_list.sort(key=lambda cid: _sort_key(index[cid]))
    return children


def _find_roots(index: dict[str, dict], included: set[str]) -> list[str]:
    roots: list[str] = []
    for node_id in included:
        parents = [pid for pid in index[node_id].get("locked_by", []) if pid in included]
        if not parents:
            roots.append(node_id)
    roots.sort(key=lambda cid: _sort_key(index[cid]))
    return roots


def _render_tree_lines(
    index: dict[str, dict],
    children_map: dict[str, list[str]],
    node_id: str,
    prefix: str,
    is_last: bool,
    lines: list[str],
) -> None:
    connector = "└─ " if is_last else "├─ "
    name = index[node_id].get("name") or f"TalentNode {node_id}"
    lines.append(f"{prefix}{connector}{name}")
    new_prefix = f"{prefix}{'   ' if is_last else '│  '}"
    children = children_map.get(node_id, [])
    for idx, child_id in enumerate(children):
        _render_tree_lines(
            index,
            children_map,
            child_id,
            new_prefix,
            idx == len(children) - 1,
            lines,
        )


def _node_props(node: dict) -> dict:
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            return props
        return node
    return {}


def _normalize_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return _split_csv(str(value))


def _split_csv(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _sort_key(entry: dict) -> tuple[int, int, str]:
    return (
        _to_int(entry.get("display_row"), default=10**9),
        _to_int(entry.get("display_col"), default=10**9),
        str(entry.get("name") or ""),
    )


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
