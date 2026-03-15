"""Shared character-info normalization."""

from __future__ import annotations


def normalize_char(char_info: object | None) -> tuple[str, str, str]:
    """Return (wow_class, spec, role) as lowercase stripped strings."""
    if isinstance(char_info, dict):
        return (
            str(char_info.get("class", "")).strip().lower(),
            str(char_info.get("spec", "")).strip().lower(),
            str(char_info.get("role", "")).strip().lower(),
        )
    if char_info is not None:
        return (
            str(getattr(char_info, "wow_class", "")).strip().lower(),
            str(getattr(char_info, "spec", "")).strip().lower(),
            str(getattr(char_info, "role", "")).strip().lower(),
        )
    return ("", "", "")


def normalize_char_dict(char_info: object | None) -> dict[str, str]:
    """Return a dict with keys 'class', 'spec', 'role'."""
    cls, spec, role = normalize_char(char_info)
    return {"class": cls, "spec": spec, "role": role}
