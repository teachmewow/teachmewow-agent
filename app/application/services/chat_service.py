"""
Chat service - orchestrates agent execution and message persistence.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.domain import Message, MessageRole, Thread, WowClass, WowSpec
from app.domain.repositories import MessageRepository, ThreadRepository

from ..agent import AgentState, format_sse_event, StreamEvent


class ChatService:
    """
    Service for handling chat interactions.

    Coordinates between the agent graph and repositories to:
    - Process user messages
    - Execute the agent
    - Stream responses
    - Persist messages
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

    async def process_message(
        self,
        thread_id: str,
        user_id: str,
        input_text: str,
        wow_class: str | None = None,
        wow_spec: str | None = None,
        wow_role: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message and stream the response.

        Args:
            thread_id: ID of the conversation thread
            user_id: ID of the user
            input_text: User's message text
            wow_class: Optional WoW class context
            wow_spec: Optional WoW spec context
            wow_role: Optional WoW role context

        Yields:
            SSE-formatted event strings
        """
        # Ensure thread exists
        thread = Thread(
            id=thread_id,
            user_id=user_id,
            wow_class=WowClass(wow_class) if wow_class else None,
            wow_spec=WowSpec(wow_spec) if wow_spec else None,
            wow_role=wow_role,
        )
        await self.thread_repository.get_or_create(thread)

        # Save user message
        user_message = Message(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            role=MessageRole.HUMAN,
            content=input_text,
            timestamp=datetime.utcnow(),
        )
        await self.message_repository.save(user_message)

        # Load conversation history
        history = await self.message_repository.get_by_thread_id(thread_id)

        # Convert to LangChain messages
        messages = []
        for msg in history:
            if msg.role == MessageRole.HUMAN:
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.AI:
                messages.append(AIMessage(content=msg.content))

        # Create initial state
        state = AgentState(
            messages=messages,
            thread_id=thread_id,
            user_id=user_id,
            wow_class=wow_class,
            wow_spec=wow_spec,
            wow_role=wow_role,
        )

        # Stream the graph execution
        full_response = ""
        try:
            async for event in self.graph.astream_events(state, version="v2"):
                event_kind = event.get("event")
                event_data = event.get("data", {})
                event_name = event.get("name", "")

                if event_kind == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        full_response += chunk.content
                        yield format_sse_event(
                            StreamEvent(
                                kind="llm_delta", data={"content": chunk.content}
                            )
                        )

                elif event_kind == "on_tool_start":
                    tool_input = event_data.get("input", {})
                    import json

                    yield format_sse_event(
                        StreamEvent(
                            kind="tool_call",
                            data={
                                "tool_call_id": event.get("run_id", ""),
                                "tool_name": event_name,
                                "arguments": json.dumps(tool_input),
                            },
                        )
                    )

                elif event_kind == "on_tool_end":
                    output = event_data.get("output", "")
                    yield format_sse_event(
                        StreamEvent(
                            kind="tool_result",
                            data={
                                "tool_call_id": event.get("run_id", ""),
                                "result": str(output),
                            },
                        )
                    )

            # Save AI response
            if full_response:
                ai_message = Message(
                    id=str(uuid.uuid4()),
                    thread_id=thread_id,
                    role=MessageRole.AI,
                    content=full_response,
                    timestamp=datetime.utcnow(),
                )
                await self.message_repository.save(ai_message)

            # Emit done event
            yield format_sse_event(StreamEvent(kind="done", data={}))

        except Exception as e:
            yield format_sse_event(
                StreamEvent(kind="error", data={"error": str(e)})
            )


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
