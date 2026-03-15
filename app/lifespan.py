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
from app.infrastructure.skills.loader import load_local_skills

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

    # Load skills from disk for local shell mode (no upload needed)
    skill_defs = load_local_skills(SKILLS_ROOT)

    # Tool configuration
    tools_config: list[dict] = [
        {
            "type": "web_search",
            "search_context_size": "medium",
            "user_location": {"type": "approximate", "country": "US"},
        },
        # Shell tool with local skills — no container, reads from disk
        {
            "type": "shell",
            "environment": {
                "type": "local",
                "skills": skill_defs,
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
    app.state.db_engine = engine

    print(f"Model: {settings.openai_main_model}")
    skill_names = [s["name"] for s in skill_defs]
    print(f"Skills (local): {skill_names}")
    print(f"Tools: {[t.get('name', t.get('type', '?')) for t in tools_config]}")
    print("Orchestrator ready")

    yield

    # Shutdown
    print("Shutting down...")
    await close_database()
    print("Database connections closed")
