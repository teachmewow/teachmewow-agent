"""
PostgreSQL implementation of MessageRepository.
"""

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Message, ToolCall
from app.domain.value_objects import MessageRole
from app.infrastructure.database.models import MessageModel


class MessageRepositoryImpl:
    """PostgreSQL implementation of MessageRepository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_entity(self, model: MessageModel) -> Message:
        """Convert SQLAlchemy model to domain entity."""
        tool_calls = None
        if model.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=tc["function"]["arguments"],
                )
                for tc in model.tool_calls
            ]

        return Message(
            id=model.id,
            thread_id=model.thread_id,
            role=MessageRole(model.role),
            content=model.content,
            timestamp=model.timestamp,
            tool_calls=tool_calls,
            tool_call_id=model.tool_call_id,
            tool_result=model.tool_result,
            reasoning=model.reasoning,
            token_count=model.token_count,
        )

    def _to_model(self, entity: Message) -> MessageModel:
        """Convert domain entity to SQLAlchemy model."""
        tool_calls_json = None
        if entity.tool_calls:
            tool_calls_json = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    },
                }
                for tc in entity.tool_calls
            ]

        return MessageModel(
            id=entity.id,
            thread_id=entity.thread_id,
            role=entity.role.value,
            content=entity.content,
            timestamp=entity.timestamp,
            tool_calls=tool_calls_json,
            tool_call_id=entity.tool_call_id,
            tool_result=entity.tool_result,
            reasoning=entity.reasoning,
            token_count=entity.token_count,
        )

    async def save(self, message: Message) -> Message:
        """Save a message to the database."""
        model = self._to_model(message)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return self._to_entity(model)

    async def save_many(self, messages: list[Message]) -> list[Message]:
        """Save multiple messages to the database."""
        models = [self._to_model(msg) for msg in messages]
        self.session.add_all(models)
        await self.session.flush()
        for model in models:
            await self.session.refresh(model)
        return [self._to_entity(model) for model in models]

    async def get_by_id(self, message_id: str) -> Message | None:
        """Get a message by ID."""
        result = await self.session.execute(
            select(MessageModel).where(MessageModel.id == message_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_thread_id(
        self, thread_id: str, limit: int | None = None, offset: int = 0
    ) -> list[Message]:
        """Get all messages for a thread ordered by timestamp."""
        query = (
            select(MessageModel)
            .where(MessageModel.thread_id == thread_id)
            .order_by(MessageModel.timestamp.asc())
            .offset(offset)
        )
        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def delete_by_thread_id(self, thread_id: str) -> int:
        """Delete all messages in a thread."""
        result = await self.session.execute(
            delete(MessageModel).where(MessageModel.thread_id == thread_id)
        )
        return result.rowcount
