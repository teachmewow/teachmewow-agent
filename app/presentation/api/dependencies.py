"""
FastAPI dependencies for dependency injection.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.agent.orchestrator import Orchestrator
from app.application.agent.skills import SkillRegistry
from app.application.services import (
    ChatService,
    ThreadService,
    create_chat_service,
    create_thread_service,
)
from app.infrastructure.database import (
    MessageRepositoryImpl,
    ThreadRepositoryImpl,
    get_session_factory,
)


async def get_db_session() -> AsyncSession:
    """Get a database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            if not session.sync_session.is_active:
                await session.rollback()
                return
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_orchestrator(request: Request) -> Orchestrator:
    """Get the orchestrator from app state."""
    return request.app.state.orchestrator


def get_skill_registry(request: Request) -> SkillRegistry:
    """Get the skill registry from app state."""
    return request.app.state.skill_registry


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
    orchestrator: Annotated[Orchestrator, Depends(get_orchestrator)],
    skill_registry: Annotated[SkillRegistry, Depends(get_skill_registry)],
    message_repo: Annotated[MessageRepositoryImpl, Depends(get_message_repository)],
    thread_repo: Annotated[ThreadRepositoryImpl, Depends(get_thread_repository)],
) -> ChatService:
    """Get chat service with all dependencies."""
    return create_chat_service(
        orchestrator=orchestrator,
        skill_registry=skill_registry,
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
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
ThreadServiceDep = Annotated[ThreadService, Depends(get_thread_service)]
