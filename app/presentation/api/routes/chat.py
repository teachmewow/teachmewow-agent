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

    Events emitted via SSE:
    - token: LLM streaming tokens
    - tool_call: Function tool invoked
    - tool_result: Function tool completed
    - web_search: Web search status
    - annotations: url_citation list (start_index, end_index, url, title)
    - done: Stream complete
    - error: An error occurred
    """
    return StreamingResponse(
        chat_service.process_message(
            thread_id=request.thread_id,
            user_id=request.user_id,
            input_text=request.input,
            char_info=request.char_info,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
