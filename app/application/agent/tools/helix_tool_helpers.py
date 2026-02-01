"""
Shared helpers for Helix tool query resolution and execution.
"""

from __future__ import annotations

from app.application.agent.tools.helix_context_formatter import extract_records


def resolve_search_queries(
    target: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    mode: str | None,
    stance: str | None,
    source_section: str | None,
    patch_context: str | None,
) -> list[tuple[str, dict]]:
    wow_class, wow_spec, wow_role, mode, stance, source_section, patch_context = (
        _normalize_filters(
            wow_class, wow_spec, wow_role, mode, stance, source_section, patch_context
        )
    )
    return _resolve_queries(
        target=target,
        wow_class=wow_class,
        wow_spec=wow_spec,
        wow_role=wow_role,
        mode=mode,
        stance=stance,
        source_section=source_section,
        patch_context=patch_context,
    )


def resolve_context_queries(
    target: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    mode: str | None,
    source_section: str | None,
    patch_context: str | None,
) -> list[tuple[str, dict]]:
    wow_class, wow_spec, wow_role, mode, _, source_section, patch_context = (
        _normalize_filters(
            wow_class, wow_spec, wow_role, mode, None, source_section, patch_context
        )
    )
    normalized = _normalize_mode(mode)
    mode_variants = _expand_mode_variants(mode, normalized)
    if not mode_variants:
        return [
            _build_context_query(
                target=target,
                wow_class=wow_class,
                wow_spec=wow_spec,
                wow_role=wow_role,
                mode=None,
                source_section=source_section,
                patch_context=patch_context,
            )
        ]

    queries: list[tuple[str, dict]] = []
    for candidate in mode_variants:
        queries.append(
            _build_context_query(
                target=target,
                wow_class=wow_class,
                wow_spec=wow_spec,
                wow_role=wow_role,
                mode=candidate,
                source_section=source_section,
                patch_context=patch_context,
            )
        )
    return queries


def run_query_candidates(
    helix_client,
    queries: list[tuple[str, dict]],
    limit: int,
) -> tuple[str, dict, list, bool]:
    last_query: tuple[str, dict] | None = None
    last_result = None
    for query_name, params in queries:
        result = helix_client.query(query_name, params)
        last_query = (query_name, params)
        last_result = result
        if _has_results(result.data):
            records = extract_records(result.data)
            records = records[: max(limit, 0)] if isinstance(records, list) else records
            return query_name, params, records, True
    if last_query is None or last_result is None:
        return "SearchFailed", {}, [], False
    records = extract_records(last_result.data)
    records = records[: max(limit, 0)] if isinstance(records, list) else records
    query_name, params = last_query
    return query_name, params, records, False


def enrich_records_with_neighbors(
    helix_client,
    records: list,
    target: str,
) -> list:
    if not isinstance(records, list):
        return records
    query_name = "FetchClaimNeighbors" if target == "claims" else "FetchProcedureNeighbors"
    for record in records:
        record_id = _get_record_id(record)
        if not record_id:
            continue
        param_key = "claim_id" if target == "claims" else "proc_id"
        result = helix_client.query(query_name, {param_key: record_id})
        neighbor_payload = _extract_neighbor_payload(result.data)
        if not neighbor_payload:
            continue
        _merge_neighbor_payload(record, neighbor_payload, target)
    return records


def _resolve_queries(
    target: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    mode: str | None,
    stance: str | None,
    source_section: str | None,
    patch_context: str | None,
) -> list[tuple[str, dict]]:
    normalized = _normalize_mode(mode)
    mode_variants = _expand_mode_variants(mode, normalized)
    if not mode_variants:
        return [
            _build_query(
                target=target,
                wow_class=wow_class,
                wow_spec=wow_spec,
                wow_role=wow_role,
                mode=None,
                stance=stance,
                source_section=source_section,
                patch_context=patch_context,
            )
        ]

    queries: list[tuple[str, dict]] = []
    for candidate in mode_variants:
        queries.append(
            _build_query(
                target=target,
                wow_class=wow_class,
                wow_spec=wow_spec,
                wow_role=wow_role,
                mode=candidate,
                stance=stance,
                source_section=source_section,
                patch_context=patch_context,
            )
        )
    return queries


def _build_context_query(
    target: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    mode: str | None,
    source_section: str | None,
    patch_context: str | None,
) -> tuple[str, dict]:
    has_tags = bool(wow_class and wow_spec)
    params = {
        "wow_class": wow_class,
        "wow_spec": wow_spec,
        "wow_role": wow_role,
    }

    if target == "procedures":
        if has_tags:
            if mode:
                params["mode"] = mode
                return "SearchProcedureContextByTagsAndMode", params
            if source_section:
                params["source_section"] = source_section
                return "SearchProcedureContextByTagsAndSection", params
            return "SearchProcedureContextByTags", params
        return "SearchProcedureContextByTags", params

    if has_tags:
        if mode:
            params["mode"] = mode
            return "SearchClaimContextByTagsAndMode", params
        if source_section:
            params["source_section"] = source_section
            return "SearchClaimContextByTagsAndSection", params
        if patch_context:
            params["patch_context"] = patch_context
            return "SearchClaimContextByTagsAndPatch", params
        return "SearchClaimContextByTags", params
    return "SearchClaimContextByTags", params


def _build_query(
    target: str,
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    mode: str | None,
    stance: str | None,
    source_section: str | None,
    patch_context: str | None,
) -> tuple[str, dict]:
    has_tags = bool(wow_class and wow_spec)
    params = {
        "wow_class": wow_class,
        "wow_spec": wow_spec,
        "wow_role": wow_role,
    }

    if target == "procedures":
        if has_tags:
            if mode:
                params["mode"] = mode
                return "SearchProceduresByTagsAndMode", params
            if source_section:
                params["source_section"] = source_section
                return "SearchProceduresByTagsAndSection", params
            return "SearchProceduresByTags", params
        return "SearchProceduresByRole", {"wow_role": wow_role}

    if has_tags:
        if mode:
            params["mode"] = mode
            return "SearchClaimsByTagsAndMode", params
        if stance:
            params["stance"] = stance
            return "SearchClaimsByTagsAndStance", params
        if source_section:
            params["source_section"] = source_section
            return "SearchClaimsByTagsAndSection", params
        if patch_context:
            params["patch_context"] = patch_context
            return "SearchClaimsByTagsAndPatch", params
        return "SearchClaimsByTags", params
    return "SearchClaimsByRole", {"wow_role": wow_role}


def _normalize_mode(mode: str | None) -> str | None:
    if not mode:
        return None
    lowered = str(mode).strip().lower()
    if not lowered:
        return None
    if "raid" in lowered or "raiding" in lowered:
        return "raid"
    if "pvp" in lowered or "arena" in lowered or "bg" in lowered:
        return "pvp"
    if "mythic" in lowered or "m+" in lowered or "dungeon" in lowered:
        return "dungeon"
    if "pve" in lowered or "overall" in lowered or "general" in lowered:
        return "general"
    return None


def _expand_mode_variants(mode: str | None, normalized: str | None) -> list[str]:
    if not mode and not normalized:
        return []
    if normalized == "dungeon":
        return ["dungeon", "M+", "mythic_plus"]
    if normalized == "raid":
        return ["raid", "raiding"]
    if normalized == "pvp":
        return ["pvp"]
    if normalized == "general":
        return ["general", "pve", "overall"]
    if mode:
        return [mode]
    return []


def _has_results(payload: object) -> bool:
    if payload is None:
        return False
    if isinstance(payload, list):
        if not payload:
            return False
        if len(payload) == 1 and isinstance(payload[0], dict):
            candidate = payload[0]
            if "claims" in candidate and not candidate.get("claims"):
                return False
            if "procs" in candidate and not candidate.get("procs"):
                return False
        return True
    if isinstance(payload, dict):
        for key in ("claims", "procs", "records", "results", "items", "nodes", "data"):
            if key in payload:
                return bool(payload.get(key))
        return True
    return True


def _normalize_filters(
    wow_class: str,
    wow_spec: str,
    wow_role: str,
    mode: str | None,
    stance: str | None,
    source_section: str | None,
    patch_context: str | None,
) -> tuple[str, str, str, str | None, str | None, str | None, str | None]:
    return (
        _normalize_value(wow_class),
        _normalize_value(wow_spec),
        _normalize_value(wow_role),
        _normalize_optional_value(mode),
        _normalize_optional_value(stance),
        _normalize_optional_value(source_section),
        _normalize_optional_value(patch_context),
    )


def _normalize_value(value: str) -> str:
    return str(value).strip().lower()


def _normalize_optional_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _get_record_id(record: object) -> str | None:
    if isinstance(record, dict):
        value = record.get("id") or record.get("ID")
        if value:
            return str(value)
    return None


def _extract_neighbor_payload(payload: object) -> dict | None:
    if payload is None:
        return None
    if isinstance(payload, list):
        if not payload:
            return None
        if isinstance(payload[0], dict):
            return payload[0]
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _merge_neighbor_payload(record: dict, payload: dict, target: str) -> None:
    if target == "claims":
        record["abilities"] = payload.get("abilities", record.get("abilities", []))
        record["talents"] = payload.get("talents", record.get("talents", []))
        record["builds"] = payload.get("builds", record.get("builds", []))
        record["game_modes"] = payload.get("game_modes", record.get("game_modes", []))
        record["patches"] = payload.get("patches", record.get("patches", []))
        record["explains"] = payload.get("explains", record.get("explains", []))
        record["recommends"] = payload.get("recommends", record.get("recommends", []))
        record["best_for"] = payload.get("best_for", record.get("best_for", []))
    else:
        record["abilities"] = payload.get("abilities", record.get("abilities", []))
        record["talents"] = payload.get("talents", record.get("talents", []))
        record["builds"] = payload.get("builds", record.get("builds", []))
        record["game_modes"] = payload.get("game_modes", record.get("game_modes", []))
