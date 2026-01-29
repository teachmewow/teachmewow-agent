"""
Serializers for converting domain entities to API schemas.
"""

from app.domain import Message, Thread
from app.presentation.schemas import MessageResponse, ThreadResponse


def serialize_message(message: Message) -> MessageResponse:
    """
    Convert a Message entity to MessageResponse schema.

    Args:
        message: Domain message entity

    Returns:
        MessageResponse schema
    """
    tool_calls_data = None
    if message.tool_calls:
        tool_calls_data = [
            {
                "id": tc.id,
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments,
                },
            }
            for tc in message.tool_calls
        ]

    return MessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        role=message.role.value,
        content=message.content,
        timestamp=message.timestamp.isoformat(),
        tool_calls=tool_calls_data,
        tool_call_id=message.tool_call_id,
        tool_result=message.tool_result,
        reasoning=message.reasoning,
        token_count=message.token_count,
    )


def serialize_thread(thread: Thread) -> ThreadResponse:
    """
    Convert a Thread entity to ThreadResponse schema.

    Args:
        thread: Domain thread entity

    Returns:
        ThreadResponse schema
    """
    return ThreadResponse(
        id=thread.id,
        user_id=thread.user_id,
        title=thread.title,
        wow_class=thread.wow_class.value if thread.wow_class else None,
        wow_spec=thread.wow_spec.value if thread.wow_spec else None,
        wow_role=thread.wow_role,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
    )
