"""
Chat API routes.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.presentation.api.dependencies import ChatServiceDep
from app.presentation.schemas import SendMessageRequest

router = APIRouter(prefix="/agent", tags=["chat"])


@router.post("/chat")
async def send_message(
    request: SendMessageRequest,
    chat_service: ChatServiceDep,
) -> StreamingResponse:
    """
    Send a message and stream the response.

    This endpoint accepts a user message and streams the AI response
    using Server-Sent Events (SSE).

    Events emitted:
    - llm_delta: Token-by-token LLM response
    - tool_call: When the agent calls a tool
    - tool_result: Result of a tool execution
    - done: Stream complete
    - error: An error occurred
    """
    return StreamingResponse(
        chat_service.process_message(
            thread_id=request.thread_id,
            user_id=request.user_id,
            input_text=request.input,
            wow_class=request.wow_class,
            wow_spec=request.spec,
            wow_role=request.role,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
