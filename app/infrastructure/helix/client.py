from __future__ import annotations

from functools import lru_cache
from typing import Any

import helix

from app.domain.entities.helix_query_result import HelixQueryResult
from app.infrastructure.config.settings import get_settings


class HelixQueryClient:
    def __init__(self, client: helix.Client) -> None:
        self._client = client

    def query(self, query_name: str, params: dict[str, Any] | None = None) -> HelixQueryResult:
        payload = params or {}
        result = self._client.query(query_name, payload)
        return HelixQueryResult(query_name=query_name, data=result)


@lru_cache
def get_helix_client() -> HelixQueryClient:
    settings = get_settings()
    if settings.helix_api_endpoint:
        client = helix.Client(
            api_endpoint=settings.helix_api_endpoint,
            api_key=settings.helix_api_key,
            verbose=settings.helix_verbose,
        )
    else:
        client = helix.Client(
            local=settings.helix_local,
            port=settings.helix_port,
            verbose=settings.helix_verbose,
        )
    return HelixQueryClient(client)
