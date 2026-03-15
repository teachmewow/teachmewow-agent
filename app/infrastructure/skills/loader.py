"""
Local skill loader — reads SKILL.md frontmatter from disk and builds
the skills array for the local shell environment.

No upload needed. The model reads SKILL.md via the shell tool at runtime.
"""

from __future__ import annotations

import re
from pathlib import Path


def _parse_frontmatter(skill_md: Path) -> dict[str, str]:
    """Extract YAML frontmatter fields from a SKILL.md file."""
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def load_local_skills(skills_root: Path) -> list[dict]:
    """
    Build the skills array for ``environment.skills`` in local shell mode.

    Each skill is defined by: name, description, path.
    The model uses the path to read SKILL.md via shell at runtime.
    """
    skills: list[dict] = []
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        fm = _parse_frontmatter(skill_md)
        name = fm.get("name", skill_dir.name)
        description = fm.get("description", "")

        skills.append({
            "name": name,
            "description": description,
            "path": str(skill_dir.resolve()),
        })
        print(f"  Loaded skill '{name}' from {skill_dir.name}/")

    return skills
