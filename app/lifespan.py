"""
FastAPI lifespan events for application startup and shutdown.
Manages initialization of the graph singleton and database connections.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.agent import GraphBuilder, get_all_tools
from app.infrastructure import LLMClient, close_database, init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan events.

    On startup:
    - Initialize database connections
    - Build the LangGraph agent (singleton)

    On shutdown:
    - Close database connections
    """
    # Startup
    print("Starting up...")

    # Initialize database
    engine, session_factory = await init_database()
    print(f"Database initialized: {engine.url}")

    # Build the graph singleton
    llm_client = LLMClient.from_settings()
    tools = get_all_tools()
    graph_builder = GraphBuilder(llm_client=llm_client, tools=tools)
    graph = graph_builder.build()

    # Store in app state for access in routes
    app.state.graph = graph
    app.state.llm_client = llm_client
    app.state.db_engine = engine

    print("Graph built and ready")
    print(f"Tools available: {[t.name for t in tools]}")

    yield

    # Shutdown
    print("Shutting down...")
    await close_database()
    print("Database connections closed")
