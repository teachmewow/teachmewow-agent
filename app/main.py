"""
FastAPI application factory.
"""

import warnings

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.config import get_settings
from app.lifespan import lifespan
from app.presentation import builds_router, chat_router, threads_router

# Suppress Pydantic serialization warnings from LangSmith @traceable.
# These fire when LangSmith serializes OpenAI tool configs (web_search, shell)
# that don't match Pydantic's expected types. Harmless but extremely noisy.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="TeachMeWoW Agent API",
        description="AI coaching agent for World of Warcraft",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(chat_router)
    app.include_router(threads_router)
    app.include_router(builds_router)

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
