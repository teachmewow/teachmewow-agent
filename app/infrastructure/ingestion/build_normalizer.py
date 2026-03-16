from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from app.infrastructure.blizzard.build_decoder import decode_import_code_nodes
from app.infrastructure.blizzard.client import BlizzardClient
from app.infrastructure.database.connection import get_session
from app.infrastructure.database.models.build_model import BuildModel
from app.infrastructure.ingestion.canonical import (
    CANONICAL_BUILD_MODES,
    CANONICAL_ENVIRONMENTS,
    CANONICAL_SCENARIOS,
    require_canonical_text,
    require_text,
)

ICON_CDN = "https://render.worldofwarcraft.com/icons/56"
logger = logging.getLogger(__name__)

UPDATE_CANDIDATE_FIELDS = [
    "source",
    "import_code",
    "patch",
    "hero_talent",
    "tree_snapshot_id",
    "tree_snapshot_ids",
    "selected_nodes",
    "selections",
    "tree_snapshot",
    "tree_payload",
]


def build_id_from_payload(payload: dict) -> str:
    parts = [
        payload.get("import_code", ""),
        payload.get("wow_spec", ""),
        payload.get("environment", ""),
        payload.get("build_mode", ""),
        payload.get("scenario", ""),
        payload.get("patch", ""),
    ]
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def upsert_builds(builds: list[dict]) -> int:
    allowed_columns = {column.name for column in BuildModel.__table__.columns}
    async with get_session() as session:
        for build in builds:
            filtered = {k: v for k, v in build.items() if k in allowed_columns}
            update_fields = {
                key: filtered[key]
                for key in UPDATE_CANDIDATE_FIELDS
                if key in filtered
            }
            stmt = (
                insert(BuildModel.__table__)
                .values(**filtered)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_=update_fields,
                )
            )
            await session.execute(stmt)
    return len(builds)


def resolve_tree_snapshot(build: dict) -> dict | None:
    if isinstance(build.get("tree_snapshot"), dict):
        return build["tree_snapshot"]
    tree_snapshot_path = build.get("tree_snapshot_path")
    if tree_snapshot_path:
        try:
            return json.loads(Path(tree_snapshot_path).read_text(encoding="utf-8"))
        except Exception:
            return None
    tree_id = build.get("tree_snapshot_id") or build.get("tree_id")
    if tree_id:
        client = BlizzardClient()
        if not client.is_configured():
            return None
        token = client.get_access_token()
        spec_id = build.get("spec_id")
        if isinstance(spec_id, int):
            return client.fetch_spec_talent_tree(int(tree_id), spec_id, token)
        resolved_spec_id = client.resolve_spec_id(
            build.get("wow_class", ""), build.get("wow_spec", "")
        )
        if resolved_spec_id:
            return client.fetch_spec_talent_tree(int(tree_id), resolved_spec_id, token)
        return client.fetch_talent_tree(int(tree_id), token)
    return None


def resolve_tree_snapshot_for_decoding(
    build: dict, debug: bool = False, strict: bool = False
) -> dict | None:
    tree_snapshot = resolve_tree_snapshot(build)
    if isinstance(tree_snapshot, dict) and tree_snapshot.get("talent_nodes"):
        return tree_snapshot
    client = BlizzardClient()
    if not client.is_configured():
        if strict:
            raise RuntimeError("Blizzard client is not configured")
        return tree_snapshot
    tree_id = build.get("tree_snapshot_id") or build.get("tree_id")
    primary_tree_id = _resolve_primary_tree_id(client, build, debug=debug)
    candidate_tree_id = primary_tree_id or tree_id
    if not candidate_tree_id:
        if strict:
            raise RuntimeError("Unable to resolve candidate tree id for decoding")
        return tree_snapshot
    token = client.get_access_token()
    try:
        snapshot = client.fetch_talent_tree(int(candidate_tree_id), token)
        if debug and primary_tree_id:
            logger.info("Decoding using primary tree_id=%s", primary_tree_id)
        return snapshot
    except Exception as exc:
        if strict:
            raise RuntimeError(
                f"Failed to fetch tree snapshot for decoding using tree_id={candidate_tree_id}"
            ) from exc
        return tree_snapshot


def _resolve_primary_tree_id(
    client: BlizzardClient, build: dict, debug: bool = False
) -> int | None:
    wow_class = str(build.get("wow_class", "")).strip()
    wow_spec = str(build.get("wow_spec", "")).strip()
    if not wow_class:
        return None
    class_tree_id = client.resolve_class_tree_id(wow_class)
    if class_tree_id is not None:
        if debug:
            logger.info("Resolved class tree_id=%s from Blizzard API", class_tree_id)
        return class_tree_id
    if not wow_spec:
        return None
    resolved = client.resolve_talent_tree_ids(wow_class, wow_spec)
    if not resolved:
        return None
    first = resolved[0] if isinstance(resolved, list) else None
    tree_id = first.get("id") if isinstance(first, dict) else None
    if debug and tree_id:
        logger.info("Resolved primary tree_id=%s from Blizzard API", tree_id)
    return int(tree_id) if isinstance(tree_id, int) else None


def normalize_build(
    build: dict, defaults: dict, debug: bool = False, strict: bool = False
) -> dict:
    payload = {**defaults, **build}
    payload["environment"] = require_canonical_text(
        payload.get("environment"),
        "environment",
        CANONICAL_ENVIRONMENTS,
    )
    payload["build_mode"] = require_canonical_text(
        payload.get("build_mode") or payload.get("scenario"),
        "build_mode",
        CANONICAL_BUILD_MODES,
    )
    payload["scenario"] = require_canonical_text(
        payload.get("scenario") or payload["build_mode"],
        "scenario",
        CANONICAL_SCENARIOS,
    )
    # Hero talent is permissive — accept any non-empty string
    payload["hero_talent"] = require_text(
        payload.get("hero_talent"),
        "hero_talent",
    )
    import_code = payload.get("import_code", "")
    selections = payload.get("selections") or []
    selected_nodes = payload.get("selected_nodes") or []
    tree_snapshot = resolve_tree_snapshot(payload)
    decode_snapshot = (
        resolve_tree_snapshot_for_decoding(payload, debug=debug, strict=strict) or tree_snapshot
    )
    if strict and not decode_snapshot:
        raise RuntimeError("Strict decoding failed: no snapshot resolved for import_code")
    if tree_snapshot is None:
        tree_snapshot = resolve_tree_snapshot_for_render(
            payload,
            decode_snapshot,
            debug=debug,
        )
    if strict and not tree_snapshot:
        raise RuntimeError("Strict decoding failed: no renderable tree snapshot found")
    snapshot_node_ids = _extract_snapshot_node_ids(tree_snapshot) if tree_snapshot else set()
    selections = _filter_selections(selections, snapshot_node_ids)
    if not selections and not selected_nodes and decode_snapshot and import_code:
        if debug:
            logger.info("Decoding import_code for build=%s", payload.get("id"))
        decoded = decode_import_code_nodes(import_code, decode_snapshot, debug=debug)
        selections = [
            {"nodeId": str(node.node_id), "rank": max(1, node.ranks_purchased or 0)}
            for node in decoded
        ]
        selected_nodes = [selection["nodeId"] for selection in selections]
        if strict and not selections:
            raise RuntimeError("Strict decoding failed: import_code produced no selections")
        if debug:
            logger.info(
                "Decoded selections=%s unique_nodes=%s",
                len(selections),
                len(set(selected_nodes)),
            )
    elif selections:
        selected_nodes = [selection["nodeId"] for selection in selections]
    payload["selected_nodes"] = selected_nodes
    payload["selections"] = selections
    payload["tree_snapshot"] = tree_snapshot
    payload["tree_payload"] = (
        build_tree_payloads(tree_snapshot, selections, debug=debug) if tree_snapshot else None
    )
    inferred_snapshot_ids = _extract_tree_snapshot_ids(tree_snapshot) if tree_snapshot else []
    payload["tree_snapshot_ids"] = payload.get("tree_snapshot_ids") or inferred_snapshot_ids
    payload["tree_snapshot_id"] = str(
        payload.get("tree_snapshot_id")
        or payload.get("tree_id")
        or _pick_default_tree_id(payload["tree_snapshot_ids"])
        or ""
    )
    if strict:
        trees = payload.get("tree_payload", {}).get("trees", []) if payload.get("tree_payload") else []
        if not trees:
            raise RuntimeError("Strict decoding failed: tree_payload.trees is empty")
        if not payload.get("tree_snapshot_id"):
            raise RuntimeError("Strict decoding failed: tree_snapshot_id is empty")
        if not payload.get("tree_snapshot_ids"):
            raise RuntimeError("Strict decoding failed: tree_snapshot_ids is empty")
    payload["id"] = payload.get("id") or build_id_from_payload(payload)
    if debug:
        logger.info(
            "Normalized build id=%s selections=%s trees=%s",
            payload.get("id"),
            len(selections),
            len(payload.get("tree_payload", {}).get("trees", []) or []),
        )
    return payload


def resolve_tree_snapshot_for_render(
    build: dict,
    decode_snapshot: dict | None,
    debug: bool = False,
) -> dict | None:
    if _is_render_tree_snapshot(decode_snapshot):
        return decode_snapshot

    client = BlizzardClient()
    if not client.is_configured():
        return decode_snapshot

    wow_class = str(build.get("wow_class", "")).strip()
    wow_spec = str(build.get("wow_spec", "")).strip()
    if not wow_class or not wow_spec:
        return decode_snapshot

    spec_id = build.get("spec_id")
    if not isinstance(spec_id, int):
        spec_id = client.resolve_spec_id(wow_class, wow_spec)
    if not isinstance(spec_id, int):
        return decode_snapshot

    tree_ids: list[int] = []
    explicit_tree_id = build.get("tree_snapshot_id") or build.get("tree_id")
    if explicit_tree_id is not None:
        try:
            tree_ids.append(int(explicit_tree_id))
        except (TypeError, ValueError):
            pass

    resolved = client.resolve_talent_tree_ids(wow_class, wow_spec)
    for item in resolved:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("id")
        if raw_id is None:
            continue
        try:
            candidate = int(raw_id)
        except (TypeError, ValueError):
            continue
        if candidate not in tree_ids:
            tree_ids.append(candidate)

    if not tree_ids:
        return decode_snapshot

    token = client.get_access_token()
    fallback_snapshot = decode_snapshot
    for tree_id in tree_ids:
        try:
            snapshot = client.fetch_spec_talent_tree(tree_id, spec_id, token)
        except Exception:
            continue
        if not isinstance(snapshot, dict):
            continue
        if _is_render_tree_snapshot(snapshot):
            if debug:
                logger.info(
                    "Resolved render snapshot using tree_id=%s spec_id=%s",
                    tree_id,
                    spec_id,
                )
            return snapshot
        if fallback_snapshot is None:
            fallback_snapshot = snapshot

    return fallback_snapshot


def _is_render_tree_snapshot(snapshot: dict | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    return bool(
        snapshot.get("class_talent_nodes")
        and snapshot.get("spec_talent_nodes")
    )


def build_tree_payloads(
    tree_snapshot: dict, selections: list[dict], debug: bool = False
) -> dict:
    trees: list[dict] = []
    icon_client = BlizzardClient()
    icon_token = ""
    spell_icon_cache: dict[int, str] = {}
    if icon_client.is_configured():
        try:
            icon_token = icon_client.get_access_token()
        except Exception:
            icon_token = ""

    hero_node_ids: set[str] = set()
    hero_trees = tree_snapshot.get("hero_talent_trees") or []
    for hero_tree in hero_trees:
        hero_nodes = (
            hero_tree.get("hero_talent_nodes", []) if isinstance(hero_tree, dict) else []
        )
        for node in hero_nodes or []:
            if isinstance(node, dict) and node.get("id") is not None:
                hero_node_ids.add(str(node.get("id")))

    class_nodes = tree_snapshot.get("class_talent_nodes") or []
    class_tree_id = _extract_tree_id(tree_snapshot.get("class_talent_tree"))
    if class_nodes:
        trees.append(
            _build_tree_payload_from_nodes(
                class_nodes,
                selections,
                kind="class",
                tree_id=class_tree_id,
                icon_client=icon_client,
                icon_token=icon_token,
                spell_icon_cache=spell_icon_cache,
                debug=debug,
            )
        )

    spec_nodes = tree_snapshot.get("spec_talent_nodes") or []
    if hero_node_ids:
        spec_nodes = [
            node
            for node in spec_nodes
            if isinstance(node, dict) and str(node.get("id")) not in hero_node_ids
        ]
    spec_tree_id = _extract_tree_id(tree_snapshot.get("spec_talent_tree"))
    if spec_nodes:
        trees.append(
            _build_tree_payload_from_nodes(
                spec_nodes,
                selections,
                kind="spec",
                tree_id=spec_tree_id,
                icon_client=icon_client,
                icon_token=icon_token,
                spell_icon_cache=spell_icon_cache,
                debug=debug,
            )
        )

    for hero_tree in hero_trees:
        hero_nodes = (
            hero_tree.get("hero_talent_nodes", []) if isinstance(hero_tree, dict) else []
        )
        if not hero_nodes:
            continue
        hero_tree_id = _extract_tree_id(hero_tree)
        trees.append(
            _build_tree_payload_from_nodes(
                hero_nodes,
                selections,
                kind="hero",
                tree_id=hero_tree_id,
                tree_name=str(hero_tree.get("name", "")).strip(),
                icon_client=icon_client,
                icon_token=icon_token,
                spell_icon_cache=spell_icon_cache,
                debug=debug,
            )
        )

    if not trees:
        combined_nodes = collect_raw_talent_nodes(tree_snapshot)
        trees.append(
            _build_tree_payload_from_nodes(
                combined_nodes,
                selections,
                kind="spec",
                tree_id=_extract_tree_id(tree_snapshot),
                icon_client=icon_client,
                icon_token=icon_token,
                spell_icon_cache=spell_icon_cache,
                debug=debug,
            )
        )

    if debug:
        logger.info(
            "Built tree payloads: class=%s spec=%s hero=%s",
            1 if class_nodes else 0,
            1 if spec_nodes else 0,
            len(hero_trees),
        )
    return {"trees": trees}


def _build_tree_payload_from_nodes(
    raw_nodes: list[dict],
    selections: list[dict],
    kind: str,
    tree_id: str | None,
    tree_name: str = "",
    icon_client: BlizzardClient | None = None,
    icon_token: str | None = None,
    spell_icon_cache: dict[int, str] | None = None,
    debug: bool = False,
) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    max_col = 0
    max_row = 0
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            continue
        node_id = str(raw_node.get("id") or "")
        if not node_id:
            continue
        name, description, icon, max_rank, icon_url = extract_node_metadata(
            raw_node, icon_client, icon_token, spell_icon_cache
        )
        display_col = int(raw_node.get("display_col", -1) or -1)
        display_row = int(raw_node.get("display_row", -1) or -1)
        node_type = str(raw_node.get("node_type", {}).get("type", "")).strip().lower()
        unlocks = [
            str(item) for item in raw_node.get("unlocks", []) or [] if item is not None
        ]
        if display_col >= 0 and display_row >= 0:
            max_col = max(max_col, display_col)
            max_row = max(max_row, display_row)
        icon_name = icon or "inv_misc_questionmark"
        resolved_icon_url = icon_url or f"{ICON_CDN}/{icon_name}.jpg"
        nodes.append(
            {
                "id": node_id,
                "name": name or f"TalentNode {node_id}",
                "icon": icon_name,
                "iconUrl": resolved_icon_url,
                "maxRank": max_rank,
                "position": {"column": display_col + 1, "row": display_row + 1},
                "entry": {
                    "id": node_id,
                    "type": node_type or "passive",
                    "description": description,
                },
                "unlocks": unlocks,
            }
        )

    node_ids = {node["id"] for node in nodes}
    for node in nodes:
        for child_id in node.get("unlocks", []) or []:
            if child_id in node_ids:
                edges.append({"from": node["id"], "to": child_id})

    filtered_selections = [
        selection for selection in selections if selection.get("nodeId") in node_ids
    ]

    if debug:
        points_spent = sum(int(selection.get("rank") or 0) for selection in filtered_selections)
        logger.info(
            "Tree kind=%s id=%s nodes=%s selections=%s points=%s",
            kind,
            tree_id or "",
            len(nodes),
            len(filtered_selections),
            points_spent,
        )

    return {
        "kind": kind,
        "treeId": tree_id or "",
        "treeName": tree_name,
        "columns": max_col + 1 if max_col >= 0 else 0,
        "rows": max_row + 1 if max_row >= 0 else 0,
        "nodes": nodes,
        "edges": edges,
        "selections": filtered_selections,
    }


def collect_raw_talent_nodes(snapshot: dict) -> list[dict]:
    nodes: list[dict] = []
    for key in ("talent_nodes", "class_talent_nodes", "spec_talent_nodes"):
        raw_nodes = snapshot.get(key, []) or []
        for node in raw_nodes:
            if isinstance(node, dict):
                nodes.append(node)
    hero_trees = snapshot.get("hero_talent_trees", []) or []
    for hero_tree in hero_trees:
        hero_nodes = (
            hero_tree.get("hero_talent_nodes", []) if isinstance(hero_tree, dict) else []
        )
        for node in hero_nodes or []:
            if isinstance(node, dict):
                nodes.append(node)
    return nodes


def extract_node_metadata(
    raw_node: dict,
    icon_client: BlizzardClient | None = None,
    icon_token: str | None = None,
    spell_icon_cache: dict[int, str] | None = None,
) -> tuple[str, str, str, int, str]:
    ranks = raw_node.get("ranks", []) or []
    max_rank = int(raw_node.get("max_ranks", 0) or len(ranks) or 1)
    if not ranks:
        return "", "", "", max_rank, ""
    primary = ranks[0] if isinstance(ranks, list) else {}
    tooltip = primary.get("tooltip") if isinstance(primary, dict) else None
    if tooltip:
        talent = tooltip.get("talent", {}) or {}
        name = str(talent.get("name", "")).strip()
        description = str(tooltip.get("spell_tooltip", {}).get("description", "")).strip()
        icon = extract_icon_from_tooltip(tooltip)
        icon_url = ""
        if not icon:
            icon_url = _resolve_icon_url_from_tooltip(
                tooltip, icon_client, icon_token, spell_icon_cache
            )
        return name, description, icon, max_rank, icon_url
    choices = primary.get("choice_of_tooltips", []) if isinstance(primary, dict) else []
    names: list[str] = []
    descriptions: list[str] = []
    icons: list[str] = []
    icon_urls: list[str] = []
    for choice in choices:
        talent = choice.get("talent", {}) or {}
        name = str(talent.get("name", "")).strip()
        if name:
            names.append(name)
        icon = extract_icon_from_tooltip(choice)
        if icon:
            icons.append(icon)
        if not icon:
            icon_url = _resolve_icon_url_from_tooltip(
                choice, icon_client, icon_token, spell_icon_cache
            )
            if icon_url:
                icon_urls.append(icon_url)
        desc = str(choice.get("spell_tooltip", {}).get("description", "")).strip()
        if desc and name:
            descriptions.append(f"{name}: {desc}")
    if names:
        combined_name = "Choice: " + " | ".join(names)
        combined_desc = "; ".join(descriptions)
        return (
            combined_name,
            combined_desc,
            (icons[0] if icons else ""),
            max_rank,
            (icon_urls[0] if icon_urls else ""),
        )
    return "", "", "", max_rank, ""


def extract_icon_from_tooltip(tooltip: dict) -> str:
    spell_tooltip = tooltip.get("spell_tooltip", {}) if isinstance(tooltip, dict) else {}
    spell = spell_tooltip.get("spell", {}) if isinstance(spell_tooltip, dict) else {}
    icon = spell.get("icon") if isinstance(spell, dict) else None
    if icon:
        return str(icon)
    talent = tooltip.get("talent", {}) if isinstance(tooltip, dict) else {}
    talent_spell = talent.get("spell", {}) if isinstance(talent, dict) else {}
    icon = talent_spell.get("icon") if isinstance(talent_spell, dict) else None
    return str(icon) if icon else ""


def _resolve_icon_url_from_tooltip(
    tooltip: dict,
    client: BlizzardClient | None,
    token: str | None,
    cache: dict[int, str] | None,
) -> str:
    spell_id = _extract_spell_id(tooltip)
    if not spell_id or not client or not token:
        return ""
    if cache is not None and spell_id in cache:
        return cache[spell_id]
    try:
        media = client.fetch_spell_media(spell_id, token)
    except Exception:
        return ""
    icon_url = _extract_icon_url_from_media(media)
    if cache is not None and icon_url:
        cache[spell_id] = icon_url
    return icon_url


def _extract_spell_id(tooltip: dict) -> int | None:
    spell_tooltip = tooltip.get("spell_tooltip", {}) if isinstance(tooltip, dict) else {}
    spell = spell_tooltip.get("spell", {}) if isinstance(spell_tooltip, dict) else {}
    spell_id = spell.get("id") if isinstance(spell, dict) else None
    if isinstance(spell_id, int):
        return spell_id
    talent = tooltip.get("talent", {}) if isinstance(tooltip, dict) else {}
    talent_spell = talent.get("spell", {}) if isinstance(talent, dict) else {}
    spell_id = talent_spell.get("id") if isinstance(talent_spell, dict) else None
    if isinstance(spell_id, int):
        return spell_id
    return None


def _extract_icon_url_from_media(media: dict) -> str:
    assets = media.get("assets", []) if isinstance(media, dict) else []
    if not isinstance(assets, list):
        return ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("key") == "icon" and asset.get("value"):
            return str(asset.get("value"))
    for asset in assets:
        if isinstance(asset, dict) and asset.get("value"):
            return str(asset.get("value"))
    return ""


def _extract_snapshot_node_ids(snapshot: dict | None) -> set[str]:
    if not isinstance(snapshot, dict):
        return set()
    node_ids: set[str] = set()
    for key in ("talent_nodes", "nodes", "class_talent_nodes", "spec_talent_nodes"):
        nodes = snapshot.get(key) or []
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict) and node.get("id") is not None:
                    node_ids.add(str(node.get("id")))
    hero_trees = snapshot.get("hero_talent_trees") or []
    for hero_tree in hero_trees:
        hero_nodes = hero_tree.get("hero_talent_nodes") if isinstance(hero_tree, dict) else None
        if isinstance(hero_nodes, list):
            for node in hero_nodes:
                if isinstance(node, dict) and node.get("id") is not None:
                    node_ids.add(str(node.get("id")))
    return node_ids


def _filter_selections(selections: list[dict], node_ids: set[str]) -> list[dict]:
    if not selections or not node_ids:
        return selections
    filtered = []
    for selection in selections:
        if not isinstance(selection, dict):
            continue
        node_id = selection.get("nodeId") or selection.get("node_id")
        if node_id is None:
            continue
        node_id_str = str(node_id)
        if node_id_str in node_ids:
            filtered.append(
                {
                    "nodeId": node_id_str,
                    "rank": int(selection.get("rank") or 1),
                }
            )
    return filtered


def _extract_tree_id(tree_entry: dict | None) -> str | None:
    if not isinstance(tree_entry, dict):
        return None
    tree_id = tree_entry.get("id")
    if isinstance(tree_id, int):
        return str(tree_id)
    if isinstance(tree_id, str) and tree_id.strip():
        return tree_id.strip()
    href = tree_entry.get("key", {}).get("href", "")
    if isinstance(href, str) and "/talent-tree/" in href:
        try:
            return href.split("/talent-tree/")[1].split("/")[0]
        except Exception:
            return None
    return None


def _extract_tree_snapshot_ids(snapshot: dict) -> list[dict]:
    if not isinstance(snapshot, dict):
        return []
    entries: list[dict] = []
    class_tree_id = _extract_tree_id(snapshot.get("class_talent_tree"))
    if class_tree_id:
        entries.append({"id": class_tree_id, "kind": "class"})
    spec_tree_id = _extract_tree_id(snapshot.get("spec_talent_tree"))
    if spec_tree_id:
        entries.append({"id": spec_tree_id, "kind": "spec"})
    for hero_tree in snapshot.get("hero_talent_trees", []) or []:
        tree_id = _extract_tree_id(hero_tree)
        if tree_id:
            entries.append(
                {
                    "id": tree_id,
                    "kind": "hero",
                    "name": str(hero_tree.get("name", "")).strip(),
                }
            )
    return entries


def _pick_default_tree_id(tree_snapshot_ids: list[dict] | None) -> str | None:
    if not tree_snapshot_ids:
        return None
    for entry in tree_snapshot_ids:
        if isinstance(entry, dict) and entry.get("kind") == "spec":
            tree_id = entry.get("id")
            if tree_id:
                return str(tree_id)
    first = tree_snapshot_ids[0]
    if isinstance(first, dict):
        tree_id = first.get("id")
        if tree_id:
            return str(tree_id)
    return None
