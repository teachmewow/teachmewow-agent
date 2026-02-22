"""
Chat service - orchestrates agent execution and message persistence.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from langgraph.graph.state import CompiledStateGraph

from app.domain import Message, MessageRole, Thread, WowClass, WowSpec
from app.domain.repositories import MessageRepository, ThreadRepository

from ..agent import AgentState, DatabaseObserver, MessageMapper, SSEOrchestrator
from ..agent.state_schema import BuildInfo, CharInfo


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
        char_info: CharInfo,
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message and stream the response.

        Uses SSEOrchestrator for streaming with debouncing and
        DatabaseObserver for automatic message persistence.

        Args:
            thread_id: ID of the conversation thread (format: uuid_userId)
            user_id: ID of the user
            input_text: User's message text
            char_info: WoW class/spec/role context (required)

        Yields:
            SSE-formatted event strings
        """
        # Ensure thread exists
        normalized_char_info = CharInfo(
            **{
                "class": char_info.wow_class,
                "spec": char_info.spec,
                "role": char_info.role,
            }
        )
        thread = Thread(
            id=thread_id,
            user_id=user_id,
            wow_class=WowClass(normalized_char_info.wow_class),
            wow_spec=WowSpec(normalized_char_info.spec),
            wow_role=normalized_char_info.role,
        )
        persisted_thread, _ = await self.thread_repository.get_or_create(thread)

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

        persisted_build_info = None
        if isinstance(persisted_thread.active_build_info, dict):
            try:
                persisted_build_info = BuildInfo.model_validate(
                    persisted_thread.active_build_info
                )
            except Exception:
                persisted_build_info = None

        # Create initial state
        state = AgentState(
            messages=messages,
            thread_id=thread_id,
            user_id=user_id,
            char_info=normalized_char_info,
            active_build_id=(
                persisted_thread.active_build_id
                or (
                    str(persisted_thread.active_build_info.get("build_id") or "")
                    if isinstance(persisted_thread.active_build_info, dict)
                    else None
                )
            ),
            build_info=persisted_build_info,
            coach_plan=(
                persisted_thread.coaching_state
                if isinstance(persisted_thread.coaching_state, dict)
                else {}
            ),
        )

        # Set up database observer for automatic AI message persistence
        db_observer = DatabaseObserver(
            message_repository=self.message_repository,
            thread_repository=self.thread_repository,
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
