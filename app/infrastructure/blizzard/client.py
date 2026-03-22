"""Async Blizzard API client with connection pooling and TTL caching."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.infrastructure.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache primitives
# ---------------------------------------------------------------------------

DEFAULT_TTL: float = 3600.0  # 1 hour


@dataclass(slots=True)
class _CacheEntry:
    value: Any
    expires_at: float


class _TTLCache:
    """Simple in-memory TTL cache with lazy eviction."""

    __slots__ = ("_store", "_default_ttl")

    def __init__(self, default_ttl: float = DEFAULT_TTL) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._store[key] = _CacheEntry(
            value=value,
            expires_at=time.monotonic() + (ttl if ttl is not None else self._default_ttl),
        )

    def clear(self) -> None:
        self._store.clear()

    def evict_expired(self) -> int:
        """Remove all expired entries. Returns count of evicted items."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._store)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

_BASE_URLS: dict[str, str] = {
    "us": "https://us.api.blizzard.com",
    "eu": "https://eu.api.blizzard.com",
    "kr": "https://kr.api.blizzard.com",
    "tw": "https://tw.api.blizzard.com",
}

_OAUTH_URLS: dict[str, str] = {
    "us": "https://us.battle.net/oauth/token",
    "eu": "https://eu.battle.net/oauth/token",
    "kr": "https://kr.battle.net/oauth/token",
    "tw": "https://tw.battle.net/oauth/token",
}


@dataclass
class ResolvedSpec:
    """Pre-resolved identifiers for a class/spec pair."""

    spec_id: int
    class_tree_id: int
    spec_tree_ids: list[dict] = field(default_factory=list)
    hero_tree_ids: list[dict] = field(default_factory=list)


class BlizzardClient:
    """Async Blizzard API client with connection pooling and response caching.

    Usage::

        async with BlizzardClient() as client:
            trees = await client.resolve_talent_tree_ids("warrior", "fury")
    """

    def __init__(
        self,
        region: str = "us",
        locale: str = "en_US",
        *,
        cache_ttl: float = DEFAULT_TTL,
    ) -> None:
        settings = get_settings()
        self.region = region
        self.locale = locale
        self.client_id: str = settings.blizzard_client_id or ""
        self.client_secret: str = settings.blizzard_client_secret or ""
        self._base_url = _BASE_URLS.get(region, _BASE_URLS["us"])
        self._oauth_url = _OAUTH_URLS.get(region, _OAUTH_URLS["us"])
        self._namespace = f"static-{region}"

        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(20.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0,
            ),
            headers={"Accept": "application/json"},
        )

        self._cache = _TTLCache(default_ttl=cache_ttl)
        self._token: str | None = None
        self._token_expires: float = 0.0
        self._token_lock = asyncio.Lock()

    # -- Lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        await self._http.aclose()
        self._cache.clear()

    async def __aenter__(self) -> BlizzardClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- Configuration -------------------------------------------------------

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    # -- Authentication ------------------------------------------------------

    async def get_access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires:
            return self._token

        async with self._token_lock:
            # Double-check after acquiring lock
            if self._token and time.monotonic() < self._token_expires:
                return self._token

            if not self.is_configured():
                raise RuntimeError("Blizzard credentials not configured")

            response = await self._http.post(
                self._oauth_url,
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()
            payload = response.json()

            token = payload.get("access_token", "")
            if not token:
                raise RuntimeError("Blizzard token request returned no access_token")

            expires_in = int(payload.get("expires_in", 3600))
            self._token = token
            self._token_expires = time.monotonic() + expires_in - 60
            return token

    # -- Low-level API methods (cached) --------------------------------------

    async def _get_json(self, path: str, *, ttl: float | None = None) -> dict:
        """GET a Blizzard API path with Bearer auth and caching."""
        cached = self._cache.get(path)
        if cached is not None:
            return cached

        token = await self.get_access_token()
        response = await self._http.get(
            path,
            params={"namespace": self._namespace, "locale": self.locale},
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 404:
            return {}
        response.raise_for_status()

        data: dict = response.json()
        self._cache.set(path, data, ttl)
        return data

    async def fetch_playable_spec_index(self) -> dict:
        return await self._get_json("/data/wow/playable-specialization/index")

    async def fetch_playable_spec(self, spec_id: int) -> dict:
        return await self._get_json(f"/data/wow/playable-specialization/{spec_id}")

    async def fetch_talent_tree_index(self) -> dict:
        return await self._get_json("/data/wow/talent-tree/index")

    async def fetch_talent_tree(self, tree_id: int) -> dict:
        return await self._get_json(f"/data/wow/talent-tree/{tree_id}")

    async def fetch_spec_talent_tree(self, tree_id: int, spec_id: int) -> dict:
        return await self._get_json(
            f"/data/wow/talent-tree/{tree_id}/playable-specialization/{spec_id}"
        )

    async def fetch_spell_media(self, spell_id: int) -> dict:
        return await self._get_json(
            f"/data/wow/media/spell/{spell_id}",
            ttl=86400.0,  # icons rarely change — cache 24h
        )

    # -- High-level resolvers ------------------------------------------------

    async def resolve_spec_id(self, wow_class: str, wow_spec: str) -> int | None:
        """Find the playable-specialization ID for a class/spec pair."""
        target_class = wow_class.strip().lower()
        target_spec = wow_spec.strip().lower()

        index = await self.fetch_playable_spec_index()
        specs = (
            index.get("character_specializations")
            or index.get("playable_specializations")
            or []
        )

        for spec in specs:
            spec_id = spec.get("id")
            if not isinstance(spec_id, int):
                continue
            detail = await self.fetch_playable_spec(spec_id)
            spec_name = str(detail.get("name", "")).strip().lower()
            class_name = (
                str(detail.get("playable_class", {}).get("name", "")).strip().lower()
            )
            if spec_name == target_spec and class_name == target_class:
                return spec_id

        return None

    async def resolve_class_tree_id(self, wow_class: str) -> int | None:
        """Find the class talent tree ID by class name."""
        target = wow_class.strip().lower()
        target_normalized = target.replace("-", " ")
        index = await self.fetch_talent_tree_index()

        for tree in index.get("class_talent_trees") or []:
            name = str(tree.get("name", "")).strip().lower()
            if name and name in (target, target_normalized):
                tree_id = _extract_tree_id(tree)
                if tree_id is not None:
                    return tree_id

        return None

    async def resolve_talent_tree_ids(
        self, wow_class: str, wow_spec: str
    ) -> list[dict]:
        """Resolve all talent tree entries (class, spec, hero) for a class/spec.

        Returns a list of ``{"id": int, "name": str}`` dicts.
        """
        target_class = wow_class.strip().lower()
        target_spec = wow_spec.strip().lower()

        # 1) Try the primary path: playable spec → talent_trees
        matched = await self._resolve_via_playable_spec(target_class, target_spec)
        if matched:
            return matched

        logger.info(
            "Playable-spec path returned no trees for %s/%s; using index fallback.",
            target_class,
            target_spec,
        )

        # 2) Fallback: talent tree index
        return await self._resolve_via_tree_index(target_class, target_spec)

    async def resolve_spec(self, wow_class: str, wow_spec: str) -> ResolvedSpec | None:
        """One-shot resolution of all identifiers needed for ingestion."""
        spec_id = await self.resolve_spec_id(wow_class, wow_spec)
        if spec_id is None:
            return None

        class_tree_id = await self.resolve_class_tree_id(wow_class) or 0
        trees = await self.resolve_talent_tree_ids(wow_class, wow_spec)

        spec_trees = [t for t in trees if t.get("id") == class_tree_id]
        hero_trees = [t for t in trees if t.get("id") != class_tree_id]

        return ResolvedSpec(
            spec_id=spec_id,
            class_tree_id=class_tree_id,
            spec_tree_ids=spec_trees or trees[:1],
            hero_tree_ids=hero_trees,
        )

    # -- Internal resolution strategies --------------------------------------

    async def _resolve_via_playable_spec(
        self, target_class: str, target_spec: str
    ) -> list[dict]:
        """Try resolving trees from the playable-specialization detail endpoint."""
        index = await self.fetch_playable_spec_index()
        specs = (
            index.get("character_specializations")
            or index.get("playable_specializations")
            or []
        )

        for spec in specs:
            spec_id = spec.get("id")
            if not isinstance(spec_id, int):
                continue
            detail = await self.fetch_playable_spec(spec_id)
            spec_name = str(detail.get("name", "")).strip().lower()
            class_name = (
                str(detail.get("playable_class", {}).get("name", "")).strip().lower()
            )
            if spec_name != target_spec or class_name != target_class:
                continue

            trees = detail.get("talent_trees") or []
            if not trees:
                return []  # Matched spec but no trees — fall to index path

            hero_matches = await self._match_hero_trees(target_class, target_spec)
            return _merge_tree_lists(trees, hero_matches)

        return []

    async def _resolve_via_tree_index(
        self, target_class: str, target_spec: str
    ) -> list[dict]:
        """Fallback: find trees by name from the talent-tree index."""
        index = await self.fetch_talent_tree_index()
        spec_trees = index.get("spec_talent_trees") or []
        class_trees = index.get("class_talent_trees") or []
        target_class_normalized = target_class.replace("-", " ")

        matched: list[dict] = []

        for tree in spec_trees:
            name = str(tree.get("name", "")).strip().lower()
            if name == target_spec:
                matched.append(tree)

        for tree in class_trees:
            name = str(tree.get("name", "")).strip().lower()
            if name in (target_class, target_class_normalized):
                matched.append(tree)

        hero_matches = await self._match_hero_trees(target_class, target_spec)
        matched.extend(hero_matches)

        return [
            {"id": _extract_tree_id(tree), "name": tree.get("name", "")}
            for tree in matched
            if _extract_tree_id(tree) is not None
        ]

    async def _match_hero_trees(
        self, target_class: str, target_spec: str
    ) -> list[dict]:
        """Find hero talent trees that belong to a specific class AND spec."""
        index = await self.fetch_talent_tree_index()
        hero_trees = index.get("hero_talent_trees") or []
        matches: list[dict] = []
        target_class_normalized = target_class.replace("-", " ")

        for tree in hero_trees:
            tree_id = _extract_tree_id(tree)
            if tree_id is None:
                continue

            detail = await self.fetch_talent_tree(tree_id)
            if not detail:
                continue

            # Filter by class
            class_name = (
                str(detail.get("playable_class", {}).get("name", "")).strip().lower()
            )
            if class_name and class_name != target_class and class_name != target_class_normalized:
                continue

            # Filter by spec
            spec_entries = detail.get("playable_specializations") or []
            spec_names = [
                str(s.get("name", "")).strip().lower()
                for s in spec_entries
                if isinstance(s, dict)
            ]
            if spec_names and target_spec not in spec_names:
                continue

            # Skip if BOTH class and spec are unknown — can't confirm relevance
            if not class_name and not spec_names:
                continue

            matches.append(tree)

        return matches


# ---------------------------------------------------------------------------
# Helpers (module-level, stateless)
# ---------------------------------------------------------------------------


def _extract_tree_id(tree: dict) -> int | None:
    """Extract numeric tree ID from a Blizzard tree entry dict."""
    raw_id = tree.get("id")
    if isinstance(raw_id, int):
        return raw_id

    href = tree.get("key", {}).get("href", "")
    if not href or "/talent-tree/" not in href:
        return None
    try:
        segment = href.split("/talent-tree/")[1].split("/")[0].split("?")[0]
        return int(segment)
    except (IndexError, ValueError):
        return None


def _merge_tree_lists(primary: list[dict], secondary: list[dict]) -> list[dict]:
    """Merge two tree lists, deduplicating by tree ID."""
    merged = list(primary)
    seen = {_extract_tree_id(t) for t in merged}
    for tree in secondary:
        tree_id = _extract_tree_id(tree)
        if tree_id is not None and tree_id not in seen:
            merged.append(tree)
            seen.add(tree_id)
    return merged
