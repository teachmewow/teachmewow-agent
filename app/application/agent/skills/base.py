"""
Skill definition dataclass.

A skill is a reusable bundle of instructions that the orchestrator
can load on demand via the ``load_skill`` tool.  Inspired by the
OpenAI Skills pattern: skills are the middle layer between the
system prompt (always-on behavior) and tools (atomic actions).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    """Immutable skill descriptor registered in the :class:`SkillRegistry`."""

    name: str
    """Short identifier (e.g. ``build_lookup``)."""

    description: str
    """One-line summary shown in the orchestrator's skill catalog."""

    when_to_use: str
    """Positive-example guidance for the orchestrator."""

    when_not_to_use: str
    """Negative-example guidance (critical for routing accuracy)."""

    instructions: str
    """
    Full workflow instructions returned by ``load_skill``.
    This is the equivalent of a SKILL.md file.
    """
