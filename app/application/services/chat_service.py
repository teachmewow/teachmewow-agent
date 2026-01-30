"""
Chat service - orchestrates agent execution and message persistence.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langgraph.graph.state import CompiledStateGraph

from app.domain import Message, MessageRole, Thread, WowClass, WowSpec
from app.domain.repositories import MessageRepository, ThreadRepository

from ..agent import (
    AgentState,
    DatabaseObserver,
    MessageMapper,
    SSEOrchestrator,
)


class ChatService:
    """
    Service for handling chat interactions.

    Coordinates between the agent graph and repositories to:
    - Process user messages
    - Execute the agent via SSEOrchestrator
    - Stream responses with debouncing
    - Persist messages via observers
    """

    def __init__(
        self,
        graph: CompiledStateGraph,
        message_repository: MessageRepository,
        thread_repository: ThreadRepository,
    ):
        """
        Initialize the chat service.

        Args:
            graph: Compiled LangGraph agent (singleton)
            message_repository: Repository for message persistence
            thread_repository: Repository for thread persistence
        """
        self.graph = graph
        self.message_repository = message_repository
        self.thread_repository = thread_repository
        self._orchestrator = SSEOrchestrator(graph)

    async def process_message(
        self,
        thread_id: str,
        user_id: str,
        input_text: str,
        wow_class: str,
        wow_spec: str,
        wow_role: str,
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message and stream the response.

        Uses SSEOrchestrator for streaming with debouncing and
        DatabaseObserver for automatic message persistence.

        Args:
            thread_id: ID of the conversation thread (format: uuid_userId)
            user_id: ID of the user
            input_text: User's message text
            wow_class: WoW class context (required)
            wow_spec: WoW spec context (required)
            wow_role: WoW role context (required)

        Yields:
            SSE-formatted event strings
        """
        # Ensure thread exists
        thread = Thread(
            id=thread_id,
            user_id=user_id,
            wow_class=WowClass(wow_class),
            wow_spec=WowSpec(wow_spec),
            wow_role=wow_role,
        )
        await self.thread_repository.get_or_create(thread)

        # Save user message first and capture timestamp
        user_timestamp = datetime.now(timezone.utc)
        user_message = Message(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            role=MessageRole.HUMAN,
            content=input_text,
            timestamp=user_timestamp,
        )
        await self.message_repository.save(user_message)

        # Load conversation history up to and including the just-saved message
        history = await self.message_repository.get_up_to_timestamp(
            thread_id, user_timestamp
        )

        # Convert domain messages to LangChain messages using the mapper
        messages = MessageMapper.to_langchain_messages(history)

        # Create initial state
        state = AgentState(
            messages=messages,
            thread_id=thread_id,
            user_id=user_id,
            wow_class=wow_class,
            wow_spec=wow_spec,
            wow_role=wow_role,
        )

        # Set up database observer for automatic AI message persistence
        db_observer = DatabaseObserver(
            message_repository=self.message_repository,
            thread_id=thread_id,
        )
        self._orchestrator.add_observer(db_observer)

        try:
            # Stream via orchestrator (handles debouncing and observer notifications)
            async for event in self._orchestrator.stream(state):
                yield event
        finally:
            # Clean up observer
            self._orchestrator.remove_observer(db_observer)


def create_chat_service(
    graph: CompiledStateGraph,
    message_repository: MessageRepository,
    thread_repository: ThreadRepository,
) -> ChatService:
    """
    Create a new ChatService instance.

    Args:
        graph: Compiled LangGraph agent
        message_repository: Repository for messages
        thread_repository: Repository for threads

    Returns:
        Configured ChatService
    """
    return ChatService(
        graph=graph,
        message_repository=message_repository,
        thread_repository=thread_repository,
    )
