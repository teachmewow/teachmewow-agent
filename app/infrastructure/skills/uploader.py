"""
Skill uploader — uploads SKILL.md bundles to OpenAI via REST API.

The Skills API (POST /v1/skills) is not yet in the Python SDK,
so we use httpx directly for the multipart upload.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import httpx

SKILLS_API_URL = "https://api.openai.com/v1/skills"


async def upload_skill(api_key: str, skill_dir: Path) -> dict[str, Any]:
    """
    Upload a skill directory to OpenAI.

    Zips the directory contents and sends via POST /v1/skills.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(skill_dir.rglob("*")):
            if file_path.is_file() and not file_path.name.startswith("."):
                arcname = f"{skill_dir.name}/{file_path.relative_to(skill_dir)}"
                zf.write(file_path, arcname)
    buf.seek(0)

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            SKILLS_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"files": (f"{skill_dir.name}.zip", buf, "application/zip")},
        )
        resp.raise_for_status()

    data = resp.json()
    skill_id = data.get("id", "")
    name = data.get("name", skill_dir.name)
    version = data.get("default_version", 1)

    print(f"  Uploaded skill '{name}' -> {skill_id} (v{version})")
    return {"skill_id": skill_id, "name": name, "version": version}


async def upload_all_skills(
    api_key: str,
    skills_root: Path,
) -> list[dict[str, Any]]:
    """
    Upload all skill directories under ``skills_root``.
    Each subdirectory must contain a SKILL.md file.
    """
    results: list[dict[str, Any]] = []
    for skill_dir in sorted(skills_root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            print(f"  Skipping {skill_dir.name}/ (no SKILL.md)")
            continue
        try:
            meta = await upload_skill(api_key, skill_dir)
            results.append(meta)
        except httpx.HTTPStatusError as e:
            print(f"  Failed to upload {skill_dir.name}: {e.response.status_code} {e.response.text[:200]}")
        except Exception as e:
            print(f"  Failed to upload {skill_dir.name}: {e}")
    return results
