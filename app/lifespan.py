"""
FastAPI lifespan events for application startup and shutdown.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.agent.orchestrator import Orchestrator
from app.application.agent.skills import SkillRegistry
from app.application.agent.skills.build_coaching import build_coaching_skill
from app.application.agent.skills.build_lookup import build_lookup_skill
from app.application.agent.tools.build_lookup import BUILD_LOOKUP_SCHEMA
from app.application.agent.tools.list_builds import LIST_BUILDS_SCHEMA
from app.application.agent.tools.load_skill import LOAD_SKILL_SCHEMA
from app.infrastructure import close_database, init_database
from app.infrastructure.config import get_settings
from app.infrastructure.llm.provider import OpenAIProvider


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    print("Starting up...")

    # Database
    engine, session_factory = await init_database()
    print(f"Database initialized: {engine.url}")

    # LLM provider (OpenAI Responses API)
    settings = get_settings()
    provider = OpenAIProvider.from_settings()

    # Skill registry
    skill_registry = SkillRegistry()
    skill_registry.register(build_lookup_skill)
    skill_registry.register(build_coaching_skill)

    # Tool configuration for the Responses API
    tools_config = [
        # Native web_search — domain-filtered
        {
            "type": "web_search",
            "search_context_size": "medium",
            "user_location": {"type": "approximate", "country": "US"},
        },
        # Our function tools
        LOAD_SKILL_SCHEMA,
        LIST_BUILDS_SCHEMA,
        BUILD_LOOKUP_SCHEMA,
    ]

    # Orchestrator (stateless singleton)
    orchestrator = Orchestrator(
        provider=provider,
        model=settings.openai_main_model,
        tools_config=tools_config,
        skill_registry=skill_registry,
    )

    # Store in app state
    app.state.orchestrator = orchestrator
    app.state.skill_registry = skill_registry
    app.state.db_engine = engine

    print(f"Model: {settings.openai_main_model}")
    print(f"Skills: {skill_registry.all_names()}")
    print(f"Tools: {[t.get('name', t.get('type', '?')) for t in tools_config]}")
    print("Orchestrator ready")

    yield

    # Shutdown
    print("Shutting down...")
    await close_database()
    print("Database connections closed")
