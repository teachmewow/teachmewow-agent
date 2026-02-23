"""
Utilities for deterministic text extraction from chat model payloads/chunks.
"""

from __future__ import annotations

from collections.abc import Mapping


def normalize_text_content(payload: object) -> str:
    """
    Normalize message/chunk payload content to a plain text string.

    Rules:
    - prefer payload.text when available;
    - fallback to payload.content;
    - list/block payloads are flattened into concatenated text;
    - unsupported structures return empty string (never raise).
    """
    text_value = _read_text_attr(payload)
    if isinstance(text_value, str):
        return text_value
    return _normalize_value(_read_content_field(payload))


def _read_text_attr(payload: object) -> object | None:
    if payload is None:
        return None
    text_attr = getattr(payload, "text", None)
    if callable(text_attr):
        try:
            return text_attr()
        except Exception:
            return None
    return text_attr


def _read_content_field(payload: object) -> object:
    if payload is None:
        return None
    if isinstance(payload, Mapping):
        if "content" in payload:
            return payload.get("content")
        return payload
    if isinstance(payload, (str, int, float, bool, list)):
        return payload
    if hasattr(payload, "content"):
        return payload.content
    return payload


def _normalize_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_normalize_value(item) for item in value]
        return "".join(part for part in parts if part)
    if isinstance(value, Mapping):
        for key in ("text", "value", "content", "output_text"):
            if key not in value:
                continue
            normalized = _normalize_value(value.get(key))
            if normalized:
                return normalized
        return ""
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump()
        except Exception:
            dumped = None
        if dumped is not None:
            return _normalize_value(dumped)
    if hasattr(value, "dict"):
        try:
            dumped = value.dict()
        except Exception:
            dumped = None
        if dumped is not None:
            return _normalize_value(dumped)
    return ""
