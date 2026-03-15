"""
LLM provider abstraction.

Abstracts the LLM API so the orchestrator references a protocol,
not a concrete SDK.  The first concrete implementation wraps the
OpenAI *Responses API* (required for native ``web_search`` tool).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from openai import AsyncOpenAI

from app.infrastructure.config import get_settings

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMProvider(Protocol):
    """Provider-agnostic interface consumed by the orchestrator."""

    async def create_response(
        self,
        *,
        model: str,
        input: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stream: bool = True,
    ) -> Any: ...


# ---------------------------------------------------------------------------
# OpenAI concrete implementation (Responses API)
# ---------------------------------------------------------------------------

class OpenAIProvider:
    """Wraps ``AsyncOpenAI`` and delegates to the Responses API."""

    def __init__(self, api_key: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key)

    async def create_response(
        self,
        *,
        model: str,
        input: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stream: bool = True,
    ) -> Any:
        return await self.client.responses.create(
            model=model,
            input=input,
            tools=tools,
            stream=stream,
        )

    # Convenience -----------------------------------------------------------

    @classmethod
    def from_settings(cls) -> OpenAIProvider:
        settings = get_settings()
        return cls(api_key=settings.openai_api_key)
