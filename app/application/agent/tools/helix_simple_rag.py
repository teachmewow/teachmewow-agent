"""
Tool: helix_simple_rag

Simple tag-based retrieval from HelixDB with formatted context output.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.tools import tool

from app.infrastructure.helix.client import get_helix_client
from app.application.agent.tools.helix_context_formatter import format_simple_context
from app.application.agent.tools.helix_tool_helpers import (
    resolve_search_queries,
    run_query_candidates,
)


@tool
def helix_simple_rag(
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
    Retrieve direct HelixDB matches using tags/filters (no graph expansion).

    Use for straightforward factual or rotation/talent lookups.
    """
    helix_client = get_helix_client()
    queries = resolve_search_queries(
        target=target,
        wow_class=wow_class,
        wow_spec=wow_spec,
        wow_role=wow_role,
        mode=mode,
        stance=stance,
        source_section=source_section,
        patch_context=patch_context,
    )
    query_name, params, records, _ = run_query_candidates(helix_client, queries, limit)
    return format_simple_context(query_name, params, target, records)
