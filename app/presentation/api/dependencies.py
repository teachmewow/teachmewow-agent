"""
FastAPI dependencies for dependency injection.
"""

from typing import Annotated

from fastapi import Depends, Request
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services import ChatService, ThreadService, create_chat_service, create_thread_service
from app.infrastructure.database import (
    MessageRepositoryImpl,
    ThreadRepositoryImpl,
    get_session_factory,
)


async def get_db_session() -> AsyncSession:
    """
    Get a database session.

    Yields:
        AsyncSession for database operations
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_graph(request: Request) -> CompiledStateGraph:
    """
    Get the compiled graph from app state.

    Args:
        request: FastAPI request object

    Returns:
        Compiled LangGraph from app.state
    """
    return request.app.state.graph


def get_message_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> MessageRepositoryImpl:
    """Get message repository with injected session."""
    return MessageRepositoryImpl(session)


def get_thread_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> ThreadRepositoryImpl:
    """Get thread repository with injected session."""
    return ThreadRepositoryImpl(session)


def get_chat_service(
    graph: Annotated[CompiledStateGraph, Depends(get_graph)],
    message_repo: Annotated[MessageRepositoryImpl, Depends(get_message_repository)],
    thread_repo: Annotated[ThreadRepositoryImpl, Depends(get_thread_repository)],
) -> ChatService:
    """Get chat service with all dependencies."""
    return create_chat_service(
        graph=graph,
        message_repository=message_repo,
        thread_repository=thread_repo,
    )


def get_thread_service(
    message_repo: Annotated[MessageRepositoryImpl, Depends(get_message_repository)],
    thread_repo: Annotated[ThreadRepositoryImpl, Depends(get_thread_repository)],
) -> ThreadService:
    """Get thread service with all dependencies."""
    return create_thread_service(
        message_repository=message_repo,
        thread_repository=thread_repo,
    )


# Type aliases for cleaner route signatures
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
Graph = Annotated[CompiledStateGraph, Depends(get_graph)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
ThreadServiceDep = Annotated[ThreadService, Depends(get_thread_service)]
