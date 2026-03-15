"""
FastAPI lifespan events for application startup and shutdown.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.agent.orchestrator_builder import OrchestratorBuilder
from app.infrastructure import close_database, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    engine, _ = await init_database()
    orchestrator = OrchestratorBuilder().build()
    app.state.orchestrator = orchestrator
    app.state.db_engine = engine
    print("Orchestrator ready")
    yield
    await close_database()
