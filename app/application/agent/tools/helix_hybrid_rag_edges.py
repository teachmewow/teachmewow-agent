"""
Tool: helix_hybrid_rag_edges

Combine direct matches with graph traversal context.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client
from app.application.agent.tools.helix_context_formatter import (
    format_graph_context,
    format_hybrid_context,
    format_header,
    format_simple_context,
)
from app.application.agent.tools.helix_tool_helpers import (
    enrich_records_with_neighbors,
    resolve_context_queries,
    resolve_search_queries,
    run_query_candidates,
)


@tool
def helix_hybrid_rag_edges(
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
    Combine direct matches with expanded graph context.

    Use when the answer is multi-part or ambiguity suggests extra context.
    """
    helix_client = get_helix_client()
    search_queries = resolve_search_queries(
        target=target,
        wow_class=wow_class,
        wow_spec=wow_spec,
        wow_role=wow_role,
        mode=mode,
        stance=stance,
        source_section=source_section,
        patch_context=patch_context,
    )
    search_name, search_params, search_records, _ = run_query_candidates(
        helix_client, search_queries, limit
    )
    direct_context = format_simple_context(
        search_name, search_params, target, search_records
    )

    context_queries = resolve_context_queries(
        target=target,
        wow_class=wow_class,
        wow_spec=wow_spec,
        wow_role=wow_role,
        mode=mode,
        source_section=source_section,
        patch_context=patch_context,
    )
    context_name, context_params, context_records, _ = run_query_candidates(
        helix_client, context_queries, limit
    )
    context_records = enrich_records_with_neighbors(
        helix_client, context_records, target
    )
    if stance and isinstance(context_records, list):
        context_records = [
            record
            for record in context_records
            if isinstance(record, dict) and record.get("stance") == stance
        ]
    related_context = format_graph_context(
        context_name, context_params, target, context_records
    )

    header = format_header("HelixHybridContext", "Combined", search_params)
    return format_hybrid_context(header, direct_context, related_context)
