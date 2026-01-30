"""
PostgreSQL implementation of ThreadRepository.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Thread
from app.domain.value_objects import WowClass, WowSpec
from app.infrastructure.database.models import ThreadModel


class ThreadRepositoryImpl:
    """PostgreSQL implementation of ThreadRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: ThreadModel) -> Thread:
        """Convert SQLAlchemy model to domain entity."""
        return Thread(
            id=model.id,
            user_id=model.user_id,
            wow_class=WowClass(model.wow_class),
            wow_spec=WowSpec(model.wow_spec),
            wow_role=model.wow_role,
            title=model.title,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_model(self, entity: Thread) -> ThreadModel:
        """Convert domain entity to SQLAlchemy model."""
        return ThreadModel(
            id=entity.id,
            user_id=entity.user_id,
            wow_class=entity.wow_class.value,
            wow_spec=entity.wow_spec.value,
            wow_role=entity.wow_role,
            title=entity.title,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def save(self, thread: Thread) -> Thread:
        """Save a thread to the database."""
        model = self._to_model(thread)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, thread_id: str) -> Thread | None:
        """Get a thread by ID."""
        result = await self.session.execute(
            select(ThreadModel).where(ThreadModel.id == thread_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_user_id(
        self, user_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Thread]:
        """Get all threads for a user."""
        query = (
            select(ThreadModel)
            .where(ThreadModel.user_id == user_id)
            .order_by(ThreadModel.updated_at.desc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def update(self, thread: Thread) -> Thread:
        """Update an existing thread."""
        result = await self.session.execute(
            select(ThreadModel).where(ThreadModel.id == thread.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Thread {thread.id} not found")

        model.title = thread.title
        model.wow_class = thread.wow_class.value
        model.wow_spec = thread.wow_spec.value
        model.wow_role = thread.wow_role
        model.updated_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def delete(self, thread_id: str) -> bool:
        """Delete a thread by ID."""
        result = await self.session.execute(
            select(ThreadModel).where(ThreadModel.id == thread_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return False

        await self.session.delete(model)
        return True

    async def get_or_create(self, thread: Thread) -> tuple[Thread, bool]:
        """Get an existing thread or create a new one."""
        # Use PostgreSQL upsert
        stmt = (
            insert(ThreadModel)
            .values(
                id=thread.id,
                user_id=thread.user_id,
                wow_class=thread.wow_class.value,
                wow_spec=thread.wow_spec.value,
                wow_role=thread.wow_role,
                title=thread.title,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
            )
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(ThreadModel)
        )

        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            # New thread was created
            return self._to_entity(model), True

        # Thread already existed, fetch it
        existing = await self.get_by_id(thread.id)
        if existing:
            return existing, False

        raise RuntimeError(f"Failed to get or create thread {thread.id}")
