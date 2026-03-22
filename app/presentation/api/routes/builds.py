"""Build API routes."""

import json
import logging
from collections.abc import AsyncGenerator

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.application.agent.tools.build_lookup import fetch_build_view_by_id
from app.infrastructure.blizzard.client import BlizzardClient
from app.infrastructure.ingestion.build_normalizer import normalize_build, upsert_builds
from app.presentation.schemas.builds import IngestPayload, IngestResult
from app.presentation.schemas.chat import CharInfoRequest

router = APIRouter(prefix="/builds", tags=["builds"])
logger = logging.getLogger(__name__)


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
        "environment": payload["environment"],
        "scenario": payload["scenario"],
        "patch": payload["patch"],
        "source": payload["source"],
        "import_code": payload["import_code"],
        "decoded_nodes": [
            str(entry.get("nodeId") or "").strip()
            for entry in (payload.get("selections") or [])
            if isinstance(entry, dict) and str(entry.get("nodeId") or "").strip()
        ],
        "build_info": {
            "build_id": payload["build_id"],
            "import_code": payload["import_code"],
            "wow_class": char_info.wow_class,
            "spec": char_info.spec,
            "decoded_nodes": [
                str(entry.get("nodeId") or "").strip()
                for entry in (payload.get("selections") or [])
                if isinstance(entry, dict) and str(entry.get("nodeId") or "").strip()
            ],
            "hero_talent": payload["hero_talent"],
            "environment": payload["environment"],
            "scenario": payload["scenario"],
            "source": payload["source"],
            "patch": payload["patch"],
        },
        "build": payload["build"],
    }


# ---------------------------------------------------------------------------
# Ingest: batch (non-streaming)
# ---------------------------------------------------------------------------


async def _process_ingest(payload: IngestPayload) -> IngestResult:
    """Normalize all builds sharing a single BlizzardClient (connection pool + cache)."""
    errors: list[str] = []
    all_normalized: list[dict] = []

    async with BlizzardClient() as client:
        for spec_entry in payload.specs:
            defaults = {
                "wow_class": spec_entry.wow_class,
                "wow_spec": spec_entry.wow_spec,
                "wow_role": spec_entry.wow_role,
                "source": spec_entry.source,
                "patch": payload.patch,
            }
            for build_entry in spec_entry.builds:
                build_dict = {
                    "id": build_entry.id,
                    "environment": build_entry.environment,
                    "scenario": build_entry.scenario,
                    "hero_talent": build_entry.hero_talent,
                    "import_code": build_entry.import_code,
                    "build_mode": build_entry.build_mode or build_entry.scenario,
                }
                try:
                    normalized = await normalize_build(build_dict, defaults, client)
                    all_normalized.append(normalized)
                except Exception as exc:
                    detail = str(exc) or f"{type(exc).__name__} (no message)"
                    msg = f"Failed to normalize build {build_entry.id}: {detail}"
                    logger.warning(msg)
                    errors.append(msg)

    ingested = 0
    if all_normalized:
        try:
            ingested = await upsert_builds(all_normalized)
        except Exception as exc:
            msg = f"Failed to upsert builds: {exc}"
            logger.error(msg)
            errors.append(msg)

    return IngestResult(
        ingested=ingested,
        specs_processed=len(payload.specs),
        errors=errors,
    )


@router.post("/ingest")
async def ingest_builds(payload: IngestPayload) -> IngestResult:
    """
    Accept JSON with builds. For each build:
    1. Fetch tree snapshot from Blizzard API
    2. Decode import_code -> selected nodes
    3. Generate tree_payload for the frontend
    4. Upsert into PostgreSQL
    """
    return await _process_ingest(payload)


@router.post("/ingest/yaml")
async def ingest_builds_yaml(request: Request) -> IngestResult:
    """Same as /ingest but accepts YAML body (Content-Type: text/yaml)."""
    body = await request.body()
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    try:
        payload = IngestPayload(**data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Validation error: {exc}") from exc
    return await _process_ingest(payload)


# ---------------------------------------------------------------------------
# Ingest: streaming (SSE progress)
# ---------------------------------------------------------------------------


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _count_total_builds(payload: IngestPayload) -> int:
    return sum(len(spec.builds) for spec in payload.specs)


async def _process_ingest_stream(payload: IngestPayload) -> AsyncGenerator[str, None]:
    total = _count_total_builds(payload)
    current = 0
    errors: list[str] = []
    all_normalized: list[dict] = []

    yield _sse_event({"type": "start", "total": total})

    async with BlizzardClient() as client:
        for spec_entry in payload.specs:
            defaults = {
                "wow_class": spec_entry.wow_class,
                "wow_spec": spec_entry.wow_spec,
                "wow_role": spec_entry.wow_role,
                "source": spec_entry.source,
                "patch": payload.patch,
            }
            for build_entry in spec_entry.builds:
                current += 1
                pct = round(current / total * 100) if total else 100
                yield _sse_event({
                    "type": "progress",
                    "current": current,
                    "total": total,
                    "pct": pct,
                    "build_id": build_entry.id,
                    "status": "normalizing",
                })

                build_dict = {
                    "id": build_entry.id,
                    "environment": build_entry.environment,
                    "scenario": build_entry.scenario,
                    "hero_talent": build_entry.hero_talent,
                    "import_code": build_entry.import_code,
                    "build_mode": build_entry.build_mode or build_entry.scenario,
                }
                try:
                    normalized = await normalize_build(build_dict, defaults, client)
                    all_normalized.append(normalized)
                    yield _sse_event({
                        "type": "progress",
                        "current": current,
                        "total": total,
                        "pct": pct,
                        "build_id": build_entry.id,
                        "status": "done",
                    })
                except Exception as exc:
                    msg = f"Failed to normalize build {build_entry.id}: {exc}"
                    logger.warning(msg)
                    errors.append(msg)
                    yield _sse_event({
                        "type": "progress",
                        "current": current,
                        "total": total,
                        "pct": pct,
                        "build_id": build_entry.id,
                        "status": "error",
                        "error": msg,
                    })

    if all_normalized:
        yield _sse_event({"type": "upserting", "count": len(all_normalized)})
        try:
            await upsert_builds(all_normalized)
        except Exception as exc:
            msg = f"Failed to upsert builds: {exc}"
            logger.error(msg)
            errors.append(msg)

    yield _sse_event({
        "type": "result",
        "ingested": len(all_normalized),
        "specs_processed": len(payload.specs),
        "errors": errors,
    })


@router.post("/ingest/stream")
async def ingest_builds_stream(payload: IngestPayload) -> StreamingResponse:
    """Same as /ingest but streams SSE progress events."""
    return StreamingResponse(
        _process_ingest_stream(payload),
        media_type="text/event-stream",
    )


@router.post("/ingest/yaml/stream")
async def ingest_builds_yaml_stream(request: Request) -> StreamingResponse:
    """Same as /ingest/yaml but streams SSE progress events."""
    body = await request.body()
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc
    try:
        payload = IngestPayload(**data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Validation error: {exc}") from exc
    return StreamingResponse(
        _process_ingest_stream(payload),
        media_type="text/event-stream",
    )
