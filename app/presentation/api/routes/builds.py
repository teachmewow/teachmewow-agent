"""
Build API routes.
"""

from fastapi import APIRouter, HTTPException

from app.application.agent.tools.build_lookup import fetch_build_view_by_id
from app.presentation.schemas.chat import CharInfoRequest

router = APIRouter(prefix="/builds", tags=["builds"])


@router.get("/{build_id}")
async def get_build_by_id(
    build_id: str,
    wow_class: str,
    spec: str,
    role: str,
) -> dict:
    char_info = CharInfoRequest(**{"class": wow_class, "spec": spec, "role": role})
    payload = await fetch_build_view_by_id(
        build_id=build_id,
        char_info={
            "class": char_info.wow_class,
            "spec": char_info.spec,
            "role": char_info.role,
        },
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return {
        "tool": "build_lookup",
        "build_id": payload["build_id"],
        "hero_talent": payload["hero_talent"],
        "scenario": payload["scenario"],
        "patch": payload["patch"],
        "source": payload["source"],
        "build": payload["build"],
    }
