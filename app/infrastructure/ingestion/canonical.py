from __future__ import annotations


CANONICAL_ENVIRONMENTS = frozenset({"raid", "mythic_plus", "delves"})
CANONICAL_BUILD_MODES = frozenset({"single", "aoe"})
CANONICAL_SCENARIOS = frozenset({"single", "aoe"})


def require_text(value: object, name: str) -> str:
    if value is None:
        raise ValueError(f"{name} is required")
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def require_canonical_text(value: object, name: str, allowed: frozenset[str]) -> str:
    text = require_text(value, name).lower()
    if text not in allowed:
        options = ", ".join(sorted(allowed))
        raise ValueError(f"{name} must be one of: {options}")
    return text
