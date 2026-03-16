"""
Local skill loader — reads SKILL.md files from disk.

Returns both:
- Shell tool metadata (name, description, path) for OpenAI's skill_reference
- Full content for direct injection into the system prompt
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


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter block from markdown content."""
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", text, count=1, flags=re.DOTALL).strip()


def load_local_skills(skills_root: Path) -> list[dict]:
    """
    Build the skills array for ``environment.skills`` in local shell mode.
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


def load_skill_contents(skills_root: Path) -> list[dict[str, str]]:
    """
    Load full skill content for system prompt injection.

    Returns list of {name, description, content} for each skill.
    """
    results: list[dict[str, str]] = []
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        raw = skill_md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(skill_md)
        content = _strip_frontmatter(raw)

        results.append({
            "name": fm.get("name", skill_dir.name),
            "description": fm.get("description", ""),
            "content": content,
        })

    return results
