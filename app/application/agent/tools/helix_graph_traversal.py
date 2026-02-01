"""
Tool: helix_graph_traversal

Graph traversal around matched claims/procedures with formatted context output.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client
from app.application.agent.tools.helix_context_formatter import format_graph_context
from app.application.agent.tools.helix_tool_helpers import (
    enrich_records_with_neighbors,
    resolve_context_queries,
    run_query_candidates,
)


@tool
def helix_graph_traversal(
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
    Traverse graph neighbors (abilities/talents/builds/modes) around matches.

    Use when relationships, dependencies, or interactions matter.
    """
    helix_client = get_helix_client()
    queries = resolve_context_queries(
        target=target,
        wow_class=wow_class,
        wow_spec=wow_spec,
        wow_role=wow_role,
        mode=mode,
        source_section=source_section,
        patch_context=patch_context,
    )
    query_name, params, records, _ = run_query_candidates(helix_client, queries, limit)
    records = enrich_records_with_neighbors(helix_client, records, target)
    if stance and isinstance(records, list):
        records = [
            record
            for record in records
            if isinstance(record, dict) and record.get("stance") == stance
        ]
    return format_graph_context(query_name, params, target, records)
