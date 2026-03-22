"""Build normalization and persistence for the ingestion pipeline.

Responsibilities:
    1. Validate and canonicalize build metadata (environment, scenario, etc.)
    2. Resolve talent-tree snapshots from the Blizzard API
    3. Decode import codes into node selections
    4. Build frontend-ready tree payloads
    5. Upsert normalized builds into PostgreSQL
"""

from __future__ import annotations

import contextlib
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


# ---------------------------------------------------------------------------
# Build ID
# ---------------------------------------------------------------------------


def build_id_from_payload(payload: dict) -> str:
    parts = [
        payload.get("import_code", ""),
        payload.get("wow_spec", ""),
        payload.get("environment", ""),
        payload.get("build_mode", ""),
        payload.get("scenario", ""),
        payload.get("patch", ""),
    ]
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Snapshot resolution
# ---------------------------------------------------------------------------


async def resolve_tree_snapshot(build: dict, client: BlizzardClient) -> dict | None:
    """Resolve a tree snapshot from inline data, file path, or Blizzard API."""
    # 1) Inline snapshot
    if isinstance(build.get("tree_snapshot"), dict):
        return build["tree_snapshot"]

    # 2) File path
    tree_snapshot_path = build.get("tree_snapshot_path")
    if tree_snapshot_path:
        try:
            return json.loads(Path(tree_snapshot_path).read_text(encoding="utf-8"))
        except Exception:
            return None

    # 3) Blizzard API (needs tree_id or tree_snapshot_id)
    tree_id = build.get("tree_snapshot_id") or build.get("tree_id")
    if not tree_id or not client.is_configured():
        return None

    spec_id = build.get("spec_id")
    if isinstance(spec_id, int):
        return await client.fetch_spec_talent_tree(int(tree_id), spec_id)

    resolved_spec_id = await client.resolve_spec_id(
        build.get("wow_class", ""), build.get("wow_spec", "")
    )
    if resolved_spec_id:
        return await client.fetch_spec_talent_tree(int(tree_id), resolved_spec_id)

    return await client.fetch_talent_tree(int(tree_id))


async def resolve_decode_snapshot(
    build: dict,
    client: BlizzardClient,
    *,
    base_snapshot: dict | None = None,
    debug: bool = False,
    strict: bool = False,
) -> dict | None:
    """Resolve a tree snapshot suitable for decoding an import code.

    The decode snapshot needs ``talent_nodes`` (the full flat list used by the
    bit-stream decoder).  Falls back to fetching the class talent tree.
    """
    if isinstance(base_snapshot, dict) and base_snapshot.get("talent_nodes"):
        return base_snapshot

    if not client.is_configured():
        if strict:
            raise RuntimeError("Blizzard client is not configured")
        return base_snapshot

    wow_class = str(build.get("wow_class", "")).strip()
    if not wow_class:
        return base_snapshot

    # Prefer class tree (contains the full flat talent_nodes list)
    class_tree_id = await client.resolve_class_tree_id(wow_class)
    candidate_id = class_tree_id or build.get("tree_snapshot_id") or build.get("tree_id")

    if not candidate_id:
        if strict:
            raise RuntimeError("Unable to resolve tree id for decoding")
        return base_snapshot

    try:
        snapshot = await client.fetch_talent_tree(int(candidate_id))
        if debug:
            logger.info("Decoding using tree_id=%s", candidate_id)
        return snapshot
    except Exception as exc:
        if strict:
            raise RuntimeError(
                f"Failed to fetch tree snapshot for tree_id={candidate_id}"
            ) from exc
        return base_snapshot


async def resolve_render_snapshot(
    build: dict,
    client: BlizzardClient,
    *,
    decode_snapshot: dict | None = None,
    debug: bool = False,
) -> dict | None:
    """Resolve a tree snapshot suitable for frontend rendering.

    The render snapshot needs ``class_talent_nodes`` and ``spec_talent_nodes``
    (the per-spec view with positional data).
    """
    if _is_render_snapshot(decode_snapshot):
        return decode_snapshot

    if not client.is_configured():
        return decode_snapshot

    wow_class = str(build.get("wow_class", "")).strip()
    wow_spec = str(build.get("wow_spec", "")).strip()
    if not wow_class or not wow_spec:
        return decode_snapshot

    spec_id = build.get("spec_id")
    if not isinstance(spec_id, int):
        spec_id = await client.resolve_spec_id(wow_class, wow_spec)
    if not isinstance(spec_id, int):
        return decode_snapshot

    # Collect candidate tree IDs
    tree_ids: list[int] = []
    explicit = build.get("tree_snapshot_id") or build.get("tree_id")
    if explicit is not None:
        with contextlib.suppress(TypeError, ValueError):
            tree_ids.append(int(explicit))

    resolved = await client.resolve_talent_tree_ids(wow_class, wow_spec)
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

    fallback = decode_snapshot
    for tree_id in tree_ids:
        try:
            snapshot = await client.fetch_spec_talent_tree(tree_id, spec_id)
        except Exception:
            continue
        if not isinstance(snapshot, dict):
            continue
        if _is_render_snapshot(snapshot):
            if debug:
                logger.info("Render snapshot via tree_id=%s spec_id=%s", tree_id, spec_id)
            return snapshot
        if fallback is None:
            fallback = snapshot

    return fallback


def _is_render_snapshot(snapshot: dict | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    return bool(snapshot.get("class_talent_nodes") and snapshot.get("spec_talent_nodes"))


# ---------------------------------------------------------------------------
# Import code decoding → selections
# ---------------------------------------------------------------------------


def _decode_selections(
    import_code: str,
    decode_snapshot: dict | None,
    *,
    debug: bool = False,
) -> tuple[list[dict], list[str]]:
    """Decode an import code into (selections, selected_node_ids)."""
    if not import_code or not decode_snapshot:
        return [], []
    decoded = decode_import_code_nodes(import_code, decode_snapshot, debug=debug)
    selections = [
        {"nodeId": str(node.node_id), "rank": max(1, node.ranks_purchased or 0)}
        for node in decoded
    ]
    selected_nodes = [s["nodeId"] for s in selections]
    return selections, selected_nodes


# ---------------------------------------------------------------------------
# Tree payloads (frontend rendering)
# ---------------------------------------------------------------------------


def build_tree_payloads(
    tree_snapshot: dict,
    selections: list[dict],
    client: BlizzardClient | None = None,
    *,
    spell_icon_cache: dict[int, str] | None = None,
    debug: bool = False,
) -> dict:
    """Build the frontend-ready tree payload from a render snapshot."""
    trees: list[dict] = []

    hero_node_ids: set[str] = set()
    hero_trees = tree_snapshot.get("hero_talent_trees") or []
    for hero_tree in hero_trees:
        for node in (hero_tree.get("hero_talent_nodes") or []) if isinstance(hero_tree, dict) else []:
            if isinstance(node, dict) and node.get("id") is not None:
                hero_node_ids.add(str(node["id"]))

    class_nodes = tree_snapshot.get("class_talent_nodes") or []
    class_tree_id = _extract_tree_id_from_snapshot_key(tree_snapshot.get("class_talent_tree"))
    if class_nodes:
        trees.append(
            _build_tree_payload(class_nodes, selections, kind="class", tree_id=class_tree_id, debug=debug)
        )

    spec_nodes = tree_snapshot.get("spec_talent_nodes") or []
    if hero_node_ids:
        spec_nodes = [
            n for n in spec_nodes
            if isinstance(n, dict) and str(n.get("id")) not in hero_node_ids
        ]
    spec_tree_id = _extract_tree_id_from_snapshot_key(tree_snapshot.get("spec_talent_tree"))
    if spec_nodes:
        trees.append(
            _build_tree_payload(spec_nodes, selections, kind="spec", tree_id=spec_tree_id, debug=debug)
        )

    for hero_tree in hero_trees:
        hero_nodes = hero_tree.get("hero_talent_nodes") or [] if isinstance(hero_tree, dict) else []
        if not hero_nodes:
            continue
        hero_tree_id = _extract_tree_id_from_snapshot_key(hero_tree)
        trees.append(
            _build_tree_payload(
                hero_nodes,
                selections,
                kind="hero",
                tree_id=hero_tree_id,
                tree_name=str(hero_tree.get("name", "")).strip(),
                debug=debug,
            )
        )

    if not trees:
        combined = _collect_raw_nodes(tree_snapshot)
        trees.append(
            _build_tree_payload(
                combined,
                selections,
                kind="spec",
                tree_id=_extract_tree_id_from_snapshot_key(tree_snapshot),
                debug=debug,
            )
        )

    return {"trees": trees}


def _build_tree_payload(
    raw_nodes: list[dict],
    selections: list[dict],
    *,
    kind: str,
    tree_id: str | None = None,
    tree_name: str = "",
    debug: bool = False,
) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    max_col = 0
    max_row = 0

    for raw in raw_nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "")
        if not node_id:
            continue

        name, description, icon, max_rank, icon_url = _extract_node_metadata(raw)
        display_col = int(raw.get("display_col", -1) or -1)
        display_row = int(raw.get("display_row", -1) or -1)
        node_type = str(raw.get("node_type", {}).get("type", "")).strip().lower()
        unlocks = [str(u) for u in (raw.get("unlocks") or []) if u is not None]

        if display_col >= 0 and display_row >= 0:
            max_col = max(max_col, display_col)
            max_row = max(max_row, display_row)

        icon_name = icon or "inv_misc_questionmark"
        resolved_icon_url = icon_url or f"{ICON_CDN}/{icon_name}.jpg"

        nodes.append({
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
        })

    node_ids = {n["id"] for n in nodes}
    for node in nodes:
        for child_id in node.get("unlocks") or []:
            if child_id in node_ids:
                edges.append({"from": node["id"], "to": child_id})

    filtered_selections = [s for s in selections if s.get("nodeId") in node_ids]

    if debug:
        points = sum(int(s.get("rank") or 0) for s in filtered_selections)
        logger.info(
            "Tree kind=%s id=%s nodes=%s selections=%s points=%s",
            kind, tree_id or "", len(nodes), len(filtered_selections), points,
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


# ---------------------------------------------------------------------------
# Node metadata extraction
# ---------------------------------------------------------------------------


def _extract_node_metadata(raw_node: dict) -> tuple[str, str, str, int, str]:
    """Extract (name, description, icon, max_rank, icon_url) from a raw node."""
    ranks = raw_node.get("ranks") or []
    max_rank = int(raw_node.get("max_ranks", 0) or len(ranks) or 1)
    if not ranks:
        return "", "", "", max_rank, ""

    primary = ranks[0] if isinstance(ranks, list) else {}
    tooltip = primary.get("tooltip") if isinstance(primary, dict) else None

    if tooltip:
        talent = tooltip.get("talent", {}) or {}
        name = str(talent.get("name", "")).strip()
        description = str(tooltip.get("spell_tooltip", {}).get("description", "")).strip()
        icon = _extract_icon_from_tooltip(tooltip)
        icon_url = ""
        if not icon:
            icon_url = _resolve_icon_url_from_tooltip(tooltip)
        return name, description, icon, max_rank, icon_url

    # Choice node
    choices = primary.get("choice_of_tooltips", []) if isinstance(primary, dict) else []
    names: list[str] = []
    descriptions: list[str] = []
    icons: list[str] = []
    icon_urls: list[str] = []
    for choice in choices:
        talent = choice.get("talent", {}) or {}
        cname = str(talent.get("name", "")).strip()
        if cname:
            names.append(cname)
        cicon = _extract_icon_from_tooltip(choice)
        if cicon:
            icons.append(cicon)
        elif not cicon:
            url = _resolve_icon_url_from_tooltip(choice)
            if url:
                icon_urls.append(url)
        desc = str(choice.get("spell_tooltip", {}).get("description", "")).strip()
        if desc and cname:
            descriptions.append(f"{cname}: {desc}")

    if names:
        return (
            "Choice: " + " | ".join(names),
            "; ".join(descriptions),
            icons[0] if icons else "",
            max_rank,
            icon_urls[0] if icon_urls else "",
        )
    return "", "", "", max_rank, ""


def _extract_icon_from_tooltip(tooltip: dict) -> str:
    spell_tooltip = tooltip.get("spell_tooltip", {}) if isinstance(tooltip, dict) else {}
    spell = spell_tooltip.get("spell", {}) if isinstance(spell_tooltip, dict) else {}
    icon = spell.get("icon") if isinstance(spell, dict) else None
    if icon:
        return str(icon)
    talent = tooltip.get("talent", {}) if isinstance(tooltip, dict) else {}
    talent_spell = talent.get("spell", {}) if isinstance(talent, dict) else {}
    icon = talent_spell.get("icon") if isinstance(talent_spell, dict) else None
    return str(icon) if icon else ""


def _resolve_icon_url_from_tooltip(tooltip: dict) -> str:
    """Extract icon URL from tooltip spell media assets (no HTTP — cached data only)."""
    spell_id = _extract_spell_id(tooltip)
    if not spell_id:
        return ""
    # Icon URL resolution without HTTP is limited to pre-cached assets
    return ""


def _extract_spell_id(tooltip: dict) -> int | None:
    spell_tooltip = tooltip.get("spell_tooltip", {}) if isinstance(tooltip, dict) else {}
    spell = spell_tooltip.get("spell", {}) if isinstance(spell_tooltip, dict) else {}
    spell_id = spell.get("id") if isinstance(spell, dict) else None
    if isinstance(spell_id, int):
        return spell_id
    talent = tooltip.get("talent", {}) if isinstance(tooltip, dict) else {}
    talent_spell = talent.get("spell", {}) if isinstance(talent, dict) else {}
    spell_id = talent_spell.get("id") if isinstance(talent_spell, dict) else None
    return spell_id if isinstance(spell_id, int) else None


# ---------------------------------------------------------------------------
# Snapshot utilities
# ---------------------------------------------------------------------------


def _extract_snapshot_node_ids(snapshot: dict | None) -> set[str]:
    if not isinstance(snapshot, dict):
        return set()
    node_ids: set[str] = set()
    for key in ("talent_nodes", "nodes", "class_talent_nodes", "spec_talent_nodes"):
        for node in snapshot.get(key) or []:
            if isinstance(node, dict) and node.get("id") is not None:
                node_ids.add(str(node["id"]))
    for hero_tree in snapshot.get("hero_talent_trees") or []:
        for node in (hero_tree.get("hero_talent_nodes") or []) if isinstance(hero_tree, dict) else []:
            if isinstance(node, dict) and node.get("id") is not None:
                node_ids.add(str(node["id"]))
    return node_ids


def _filter_selections(selections: list[dict], node_ids: set[str]) -> list[dict]:
    if not selections or not node_ids:
        return selections
    return [
        {"nodeId": str(s.get("nodeId") or s.get("node_id")), "rank": int(s.get("rank") or 1)}
        for s in selections
        if isinstance(s, dict) and str(s.get("nodeId") or s.get("node_id") or "") in node_ids
    ]


def _extract_tree_id_from_snapshot_key(tree_entry: dict | None) -> str | None:
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
    class_tree_id = _extract_tree_id_from_snapshot_key(snapshot.get("class_talent_tree"))
    if class_tree_id:
        entries.append({"id": class_tree_id, "kind": "class"})
    spec_tree_id = _extract_tree_id_from_snapshot_key(snapshot.get("spec_talent_tree"))
    if spec_tree_id:
        entries.append({"id": spec_tree_id, "kind": "spec"})
    for hero_tree in snapshot.get("hero_talent_trees") or []:
        htid = _extract_tree_id_from_snapshot_key(hero_tree)
        if htid:
            entries.append({"id": htid, "kind": "hero", "name": str(hero_tree.get("name", "")).strip()})
    return entries


def _pick_default_tree_id(ids: list[dict] | None) -> str | None:
    if not ids:
        return None
    for entry in ids:
        if isinstance(entry, dict) and entry.get("kind") == "spec":
            tid = entry.get("id")
            if tid:
                return str(tid)
    first = ids[0]
    return str(first["id"]) if isinstance(first, dict) and first.get("id") else None


def _collect_raw_nodes(snapshot: dict) -> list[dict]:
    nodes: list[dict] = []
    for key in ("talent_nodes", "class_talent_nodes", "spec_talent_nodes"):
        for node in snapshot.get(key) or []:
            if isinstance(node, dict):
                nodes.append(node)
    for hero_tree in snapshot.get("hero_talent_trees") or []:
        for node in (hero_tree.get("hero_talent_nodes") or []) if isinstance(hero_tree, dict) else []:
            if isinstance(node, dict):
                nodes.append(node)
    return nodes


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------


async def normalize_build(
    build: dict,
    defaults: dict,
    client: BlizzardClient,
    *,
    debug: bool = False,
    strict: bool = False,
) -> dict:
    """Normalize a single build entry into a fully resolved dict ready for DB upsert.

    Steps:
        1. Merge defaults, validate canonical fields
        2. Resolve tree snapshots (decode + render)
        3. Decode import code → selections
        4. Build frontend tree payloads
        5. Generate build ID
    """
    payload = {**defaults, **build}

    # -- Canonical validation ------------------------------------------------
    payload["environment"] = require_canonical_text(
        payload.get("environment"), "environment", CANONICAL_ENVIRONMENTS,
    )
    payload["build_mode"] = require_canonical_text(
        payload.get("build_mode") or payload.get("scenario"), "build_mode", CANONICAL_BUILD_MODES,
    )
    payload["scenario"] = require_canonical_text(
        payload.get("scenario") or payload["build_mode"], "scenario", CANONICAL_SCENARIOS,
    )
    payload["hero_talent"] = require_text(payload.get("hero_talent"), "hero_talent")

    import_code = payload.get("import_code", "")
    selections = payload.get("selections") or []
    selected_nodes = payload.get("selected_nodes") or []

    # -- Snapshot resolution -------------------------------------------------
    tree_snapshot = await resolve_tree_snapshot(payload, client)
    decode_snapshot = await resolve_decode_snapshot(
        payload, client, base_snapshot=tree_snapshot, debug=debug, strict=strict,
    )
    if strict and not decode_snapshot:
        raise RuntimeError("Strict: no decode snapshot resolved")

    if tree_snapshot is None:
        tree_snapshot = await resolve_render_snapshot(
            payload, client, decode_snapshot=decode_snapshot, debug=debug,
        )
    if strict and not tree_snapshot:
        raise RuntimeError("Strict: no render snapshot resolved")

    # -- Decode import code --------------------------------------------------
    snapshot_node_ids = _extract_snapshot_node_ids(tree_snapshot)
    selections = _filter_selections(selections, snapshot_node_ids)

    if not selections and not selected_nodes and decode_snapshot and import_code:
        if debug:
            logger.info("Decoding import_code for build=%s", payload.get("id"))
        selections, selected_nodes = _decode_selections(
            import_code, decode_snapshot, debug=debug,
        )
        if strict and not selections:
            raise RuntimeError("Strict: import_code produced no selections")

    # -- Tree payloads -------------------------------------------------------
    tree_payload: dict | None = None
    if tree_snapshot:
        tree_payload = build_tree_payloads(tree_snapshot, selections, client, debug=debug)

    # -- IDs and metadata ----------------------------------------------------
    tree_snapshot_ids = _extract_tree_snapshot_ids(tree_snapshot) if tree_snapshot else []
    default_tree_id = _pick_default_tree_id(tree_snapshot_ids)

    payload.update({
        "id": payload.get("id") or build_id_from_payload(payload),
        "tree_snapshot_id": default_tree_id,
        "tree_snapshot_ids": tree_snapshot_ids or None,
        "selected_nodes": selected_nodes or [s["nodeId"] for s in selections],
        "selections": selections,
        "tree_snapshot": tree_snapshot,
        "tree_payload": tree_payload,
    })

    return payload
