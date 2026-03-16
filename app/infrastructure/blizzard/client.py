from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request


_token_cache: tuple[str, float] | None = None  # (token, expires_at)


class BlizzardClient:
    def __init__(self, region: str = "us", locale: str = "en_US") -> None:
        self.region = region
        self.locale = locale
        self.client_id = os.getenv("BLIZZARD_CLIENT_ID", "")
        self.client_secret = os.getenv("BLIZZARD_CLIENT_SECRET", "")
        self._logger = logging.getLogger(__name__)

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def get_access_token(self) -> str:
        global _token_cache
        if _token_cache is not None:
            token, expires_at = _token_cache
            if time.monotonic() < expires_at:
                return token

        if not self.is_configured():
            raise RuntimeError("Blizzard credentials not configured")
        token_url = f"https://{self.region}.battle.net/oauth/token"
        auth = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        headers = {
            "Authorization": f"Basic {base64.b64encode(auth).decode('utf-8')}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8")
        request = urllib.request.Request(token_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = payload.get("access_token", "")
        if not token:
            self._logger.warning("Blizzard token request returned no access_token.")
        else:
            expires_in = int(payload.get("expires_in", 3600))
            _token_cache = (token, time.monotonic() + expires_in - 60)
        return token

    def fetch_talent_tree(self, tree_id: int, token: str) -> dict:
        namespace = f"static-{self.region}"
        url = (
            f"https://{self.region}.api.blizzard.com/data/wow/talent-tree/"
            f"{tree_id}?namespace={namespace}&locale={self.locale}"
        )
        return self._fetch_json(url, token)

    def fetch_spec_talent_tree(self, tree_id: int, spec_id: int, token: str) -> dict:
        namespace = f"static-{self.region}"
        url = (
            f"https://{self.region}.api.blizzard.com/data/wow/talent-tree/"
            f"{tree_id}/playable-specialization/{spec_id}"
            f"?namespace={namespace}&locale={self.locale}"
        )
        return self._fetch_json(url, token)

    def fetch_playable_spec_index(self, token: str) -> dict:
        namespace = f"static-{self.region}"
        url = (
            f"https://{self.region}.api.blizzard.com/data/wow/playable-specialization/"
            f"index?namespace={namespace}&locale={self.locale}"
        )
        return self._fetch_json(url, token)

    def fetch_playable_spec(self, spec_id: int, token: str) -> dict:
        namespace = f"static-{self.region}"
        url = (
            f"https://{self.region}.api.blizzard.com/data/wow/playable-specialization/"
            f"{spec_id}?namespace={namespace}&locale={self.locale}"
        )
        return self._fetch_json(url, token)

    def fetch_spell_media(self, spell_id: int, token: str) -> dict:
        namespace = f"static-{self.region}"
        url = (
            f"https://{self.region}.api.blizzard.com/data/wow/media/spell/"
            f"{spell_id}?namespace={namespace}&locale={self.locale}"
        )
        return self._fetch_json(url, token)

    def fetch_talent_tree_index(self, token: str) -> dict:
        namespace = f"static-{self.region}"
        url = (
            f"https://{self.region}.api.blizzard.com/data/wow/talent-tree/"
            f"index?namespace={namespace}&locale={self.locale}"
        )
        return self._fetch_json(url, token)

    def resolve_talent_tree_ids(self, wow_class: str, wow_spec: str) -> list[dict]:
        self._logger.info(
            "Resolving talent trees for class=%s spec=%s",
            wow_class,
            wow_spec,
        )
        token = self.get_access_token()
        if not token:
            self._logger.warning("Blizzard access token is empty; cannot resolve tree ids.")
            return []
        index = self.fetch_playable_spec_index(token)
        specs = index.get("character_specializations") or index.get("playable_specializations") or []
        tree_index = None
        target_class = wow_class.strip().lower()
        target_spec = wow_spec.strip().lower()
        if not specs:
            self._logger.warning("Playable specialization index is empty.")
            return []
        for spec in specs:
            spec_id = spec.get("id")
            if not isinstance(spec_id, int):
                continue
            detail = self.fetch_playable_spec(spec_id, token)
            spec_name = str(detail.get("name", "")).strip().lower()
            class_name = (
                str(detail.get("playable_class", {}).get("name", "")).strip().lower()
            )
            if spec_name != target_spec or class_name != target_class:
                continue
            trees = detail.get("talent_trees", []) or []
            if trees:
                self._logger.info(
                    "Matched spec id=%s name=%s class=%s; trees=%s",
                    spec_id,
                    spec_name,
                    class_name,
                    [tree.get("id") for tree in trees if isinstance(tree, dict)],
                )
                if tree_index is None:
                    tree_index = self.fetch_talent_tree_index(token)
                hero_matches = _match_hero_trees(
                    self, tree_index.get("hero_talent_trees") or [], target_class, target_spec, token
                )
                return _merge_tree_lists(trees, hero_matches)
            break
        self._logger.warning("No matching spec found in Blizzard API index.")
        if tree_index is None:
            tree_index = self.fetch_talent_tree_index(token)
        spec_trees = tree_index.get("spec_talent_trees") or []
        class_trees = tree_index.get("class_talent_trees") or []
        hero_trees = tree_index.get("hero_talent_trees") or []
        self._logger.info(
            "Talent tree index sizes spec=%s class=%s hero=%s",
            len(spec_trees),
            len(class_trees),
            len(hero_trees),
        )
        matched: list[dict] = []
        for tree in spec_trees:
            name = str(tree.get("name", "")).strip().lower()
            if name and target_spec in name:
                matched.append(tree)
        for tree in class_trees:
            name = str(tree.get("name", "")).strip().lower()
            if name and target_class in name:
                matched.append(tree)
        hero_matches = _match_hero_trees(self, hero_trees, target_class, target_spec, token)
        matched.extend(hero_matches)
        if matched:
            extracted = [
                {"id": _extract_tree_id(tree), "name": tree.get("name", "")}
                for tree in matched
                if _extract_tree_id(tree) is not None
            ]
            self._logger.info(
                "Matched trees from index: %s",
                [tree.get("id") for tree in extracted if isinstance(tree, dict)],
            )
            return extracted
        self._logger.warning("No matching trees found in talent tree index.")
        return []

    def resolve_class_tree_id(self, wow_class: str) -> int | None:
        token = self.get_access_token()
        if not token:
            self._logger.warning("Blizzard access token is empty; cannot resolve class tree id.")
            return None
        index = self.fetch_talent_tree_index(token)
        class_trees = index.get("class_talent_trees") or []
        target_class = wow_class.strip().lower()
        for tree in class_trees:
            name = str(tree.get("name", "")).strip().lower()
            if name and target_class in name:
                tree_id = _extract_tree_id(tree)
                if tree_id is not None:
                    return tree_id
        return None

    def resolve_spec_id(self, wow_class: str, wow_spec: str) -> int | None:
        token = self.get_access_token()
        if not token:
            self._logger.warning("Blizzard access token is empty; cannot resolve spec id.")
            return None
        index = self.fetch_playable_spec_index(token)
        specs = index.get("character_specializations") or index.get("playable_specializations") or []
        target_class = wow_class.strip().lower()
        target_spec = wow_spec.strip().lower()
        for spec in specs:
            spec_id = spec.get("id")
            if not isinstance(spec_id, int):
                continue
            detail = self.fetch_playable_spec(spec_id, token)
            spec_name = str(detail.get("name", "")).strip().lower()
            class_name = (
                str(detail.get("playable_class", {}).get("name", "")).strip().lower()
            )
            if spec_name == target_spec and class_name == target_class:
                return spec_id
        return None

    def _fetch_json(self, url: str, token: str) -> dict:
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            raise


def _extract_tree_id(tree: dict) -> int | None:
    href = tree.get("key", {}).get("href", "")
    if not href:
        return None
    try:
        parts = href.split("/talent-tree/")[1]
        tree_id_str = parts.split("/")[0]
        return int(tree_id_str)
    except Exception:
        return None


def _match_hero_trees(
    client: BlizzardClient,
    hero_trees: list[dict],
    target_class: str,
    target_spec: str,
    token: str,
) -> list[dict]:
    matches: list[dict] = []
    for tree in hero_trees:
        tree_id = _extract_tree_id(tree)
        if tree_id is None:
            continue
        detail = client.fetch_talent_tree(tree_id, token)
        if not detail:
            continue
        class_name = str(detail.get("playable_class", {}).get("name", "")).strip().lower()
        spec_entries = detail.get("playable_specializations") or []
        spec_names = [
            str(spec.get("name", "")).strip().lower()
            for spec in spec_entries
            if isinstance(spec, dict)
        ]
        spec_names = [name for name in spec_names if name]
        if class_name and class_name != target_class:
            continue
        if spec_names and target_spec not in spec_names:
            continue
        matches.append(tree)
    return matches


def _merge_tree_lists(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged: list[dict] = list(primary)
    seen = {_extract_tree_id(tree) for tree in merged if isinstance(tree, dict)}
    for tree in secondary:
        tree_id = _extract_tree_id(tree)
        if tree_id is None or tree_id in seen:
            continue
        merged.append(tree)
        seen.add(tree_id)
    return merged
