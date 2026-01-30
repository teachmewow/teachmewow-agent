"""
Database connection configuration using SQLAlchemy.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.infrastructure.config import get_settings

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = MetaData(naming_convention=convention)


# Global engine and session factory (initialized in lifespan)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """
    Get async database URL from settings.
    Converts postgresql:// to postgresql+asyncpg://
    Note: asyncpg doesn't support sslmode in URL, use connect_args instead.
    """
    settings = get_settings()
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def create_engine() -> AsyncEngine:
    """Create SQLAlchemy async engine."""
    url = get_database_url()
    # Disable SSL for local connections (macOS permission issues)
    # Use both URL parameter and connect_args for maximum compatibility
    connect_args = {}
    if "localhost" in url or "127.0.0.1" in url:
        connect_args["ssl"] = False
    
    print(f"Database URL: {url.split('@')[0]}@***")
    if connect_args:
        print(f"Database connection args: {connect_args}")
    
    return create_async_engine(
        url,
        echo=get_settings().debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args if connect_args else {},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create session factory from engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def init_database() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """
    Initialize database engine and session factory.
    Called during application startup.
    """
    global _engine, _session_factory

    _engine = create_engine()
    _session_factory = create_session_factory(_engine)

    return _engine, _session_factory


async def close_database() -> None:
    """
    Close database connections.
    Called during application shutdown.
    """
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the session factory (must be initialized first)."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session as context manager.

    Usage:
        async with get_session() as session:
            # use session
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
