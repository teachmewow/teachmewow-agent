"""
Thread API routes.
"""

from fastapi import APIRouter, HTTPException

from app.presentation.api.dependencies import ThreadServiceDep
from app.presentation.schemas import MessageResponse, ThreadResponse
from app.presentation.serializers import serialize_message, serialize_thread

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def get_thread_messages(
    thread_id: str,
    thread_service: ThreadServiceDep,
    limit: int | None = None,
    offset: int = 0,
) -> list[MessageResponse]:
    """
    Get all messages for a thread.

    Args:
        thread_id: ID of the thread
        limit: Maximum number of messages to return
        offset: Number of messages to skip

    Returns:
        List of messages ordered by timestamp
    """
    messages = await thread_service.get_thread_messages(
        thread_id=thread_id,
        limit=limit,
        offset=offset,
    )
    return [serialize_message(msg) for msg in messages]


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    thread_service: ThreadServiceDep,
) -> ThreadResponse:
    """
    Get a thread by ID.

    Args:
        thread_id: ID of the thread

    Returns:
        Thread details
    """
    thread = await thread_service.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return serialize_thread(thread)


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    thread_service: ThreadServiceDep,
) -> dict:
    """
    Delete a thread and all its messages.

    Args:
        thread_id: ID of the thread

    Returns:
        Success message
    """
    deleted = await thread_service.delete_thread(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "deleted", "thread_id": thread_id}
