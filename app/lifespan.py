"""
FastAPI lifespan events for application startup and shutdown.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.application.agent.orchestrator import Orchestrator
from app.application.agent.tools.build_lookup import BUILD_LOOKUP_SCHEMA
from app.application.agent.tools.list_builds import LIST_BUILDS_SCHEMA
from app.infrastructure import close_database, init_database
from app.infrastructure.config import get_settings
from app.infrastructure.llm.provider import OpenAIProvider
from app.infrastructure.skills import upload_all_skills

SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    print("Starting up...")

    # Database
    engine, session_factory = await init_database()
    print(f"Database initialized: {engine.url}")

    # LLM provider (OpenAI Responses API + LangSmith tracing)
    settings = get_settings()
    provider = OpenAIProvider.from_settings()

    # Upload skills to OpenAI
    print("Uploading skills...")
    skill_metas = await upload_all_skills(settings.openai_api_key, SKILLS_ROOT)
    skill_refs = [
        {
            "skill_id": m["skill_id"],
            "name": m["name"],
            "description": m["description"],
            "path": m["path"],
        }
        for m in skill_metas
    ]

    # Tool configuration for the Responses API
    tools_config = [
        {
            "type": "web_search",
            "search_context_size": "medium",
            "user_location": {"type": "approximate", "country": "US"},
        },
        # Shell tool with skills — local mode (no container overhead)
        {
            "type": "shell",
            "environment": {
                "type": "local",
                "skills": skill_refs,
            },
        },
        LIST_BUILDS_SCHEMA,
        BUILD_LOOKUP_SCHEMA,
    ]

    # Orchestrator
    orchestrator = Orchestrator(
        provider=provider,
        model=settings.openai_main_model,
        tools_config=tools_config,
        reasoning_effort=settings.openai_reasoning_effort,
    )

    # Store in app state
    app.state.orchestrator = orchestrator
    app.state.skill_metas = skill_metas
    app.state.db_engine = engine

    print(f"Model: {settings.openai_main_model}")
    print(f"Skills uploaded: {[m['name'] for m in skill_metas]}")
    print(f"Tools: {[t.get('name', t.get('type', '?')) for t in tools_config]}")
    print("Orchestrator ready")

    yield

    # Shutdown
    print("Shutting down...")
    await close_database()
    print("Database connections closed")
