"""
LLM provider abstraction.

Wraps the OpenAI Responses API with LangSmith tracing via ``wrap_openai``.
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

    @property
    def client(self) -> AsyncOpenAI: ...

    async def create_response(
        self,
        *,
        model: str,
        input: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stream: bool = True,
    ) -> Any: ...


# ---------------------------------------------------------------------------
# OpenAI concrete implementation (Responses API + LangSmith tracing)
# ---------------------------------------------------------------------------

class OpenAIProvider:
    """Wraps ``AsyncOpenAI`` with LangSmith tracing and Responses API."""

    def __init__(self, api_key: str, *, enable_tracing: bool = True) -> None:
        raw_client = AsyncOpenAI(api_key=api_key)

        if enable_tracing:
            try:
                from langsmith.wrappers import wrap_openai
                self._client = wrap_openai(raw_client)
                print("LangSmith tracing enabled for OpenAI client")
            except ImportError:
                self._client = raw_client
                print("LangSmith not installed — tracing disabled")
        else:
            self._client = raw_client

    @property
    def client(self) -> AsyncOpenAI:
        return self._client

    async def create_response(
        self,
        *,
        model: str,
        input: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stream: bool = True,
    ) -> Any:
        return await self._client.responses.create(
            model=model,
            input=input,
            tools=tools,
            stream=stream,
        )

    @classmethod
    def from_settings(cls) -> OpenAIProvider:
        settings = get_settings()
        return cls(
            api_key=settings.openai_api_key,
            enable_tracing=not settings.is_production,
        )
