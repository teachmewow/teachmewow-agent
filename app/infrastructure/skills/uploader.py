"""
Skill uploader — uploads SKILL.md bundles to OpenAI and returns skill_ids.

On startup, each skill directory under ``skills/`` is zipped and uploaded
via ``POST /v1/skills``.  The returned ``skill_id`` is stored for use
in ``responses.create`` calls.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI


async def upload_skill(client: AsyncOpenAI, skill_dir: Path) -> dict[str, Any]:
    """
    Upload a skill directory to OpenAI.

    Args:
        client: AsyncOpenAI client instance.
        skill_dir: Path to the skill directory containing SKILL.md.

    Returns:
        dict with ``skill_id``, ``name``, ``version`` from the API response.
    """
    # Build in-memory zip of the skill directory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(skill_dir.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith("."):
                arcname = f"{skill_dir.name}/{file_path.relative_to(skill_dir)}"
                zf.write(file_path, arcname)
    buf.seek(0)

    response = await client.skills.create(
        files=buf,
    )

    skill_id = response.id
    name = getattr(response, "name", skill_dir.name)
    version = getattr(response, "default_version", 1)

    print(f"  Uploaded skill '{name}' -> {skill_id} (v{version})")
    return {"skill_id": skill_id, "name": name, "version": version}


async def upload_all_skills(
    client: AsyncOpenAI,
    skills_root: Path,
) -> list[dict[str, Any]]:
    """
    Upload all skill directories under ``skills_root``.

    Each subdirectory must contain a ``SKILL.md`` file.
    Returns list of skill metadata dicts.
    """
    results: list[dict[str, Any]] = []
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            print(f"  Skipping {skill_dir.name}/ (no SKILL.md)")
            continue
        meta = await upload_skill(client, skill_dir)
        results.append(meta)
    return results
