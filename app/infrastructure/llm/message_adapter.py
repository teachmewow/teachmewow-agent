"""Adapter: domain Message objects -> OpenAI Responses API input format."""

from app.domain import Message, MessageRole


def to_responses_api_messages(messages: list[Message]) -> list[dict]:
    """Convert domain Message objects to Responses API input format.

    Filters out TOOL messages — the Responses API manages tool-call flow
    internally and does not replay them as conversation history.
    """
    result: list[dict] = []
    for msg in messages:
        if msg.role == MessageRole.HUMAN:
            result.append({"role": "user", "content": msg.content or ""})
        elif msg.role == MessageRole.AI:
            result.append({"role": "assistant", "content": msg.content or ""})
        elif msg.role == MessageRole.SYSTEM:
            result.append({"role": "system", "content": msg.content or ""})
    return result
