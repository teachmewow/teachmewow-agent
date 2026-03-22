"""
LLM provider abstraction.

Wraps the OpenAI Responses API with optional LangSmith tracing via ``wrap_openai``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from openai import AsyncOpenAI

from app.infrastructure.config import get_settings

try:
    from langsmith.wrappers import wrap_openai

    _HAS_LANGSMITH = True
except ImportError:
    _HAS_LANGSMITH = False

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
        reasoning_effort: str | None = None,
    ) -> Any: ...


# ---------------------------------------------------------------------------
# OpenAI concrete implementation (Responses API + LangSmith tracing)
# ---------------------------------------------------------------------------

class OpenAIProvider:
    """Wraps ``AsyncOpenAI`` with LangSmith tracing and Responses API."""

    def __init__(self, api_key: str, *, enable_tracing: bool = True) -> None:
        raw_client = AsyncOpenAI(api_key=api_key)
        if enable_tracing and _HAS_LANGSMITH:
            self._client = wrap_openai(raw_client)
            print("LangSmith tracing enabled for OpenAI client")
        else:
            self._client = raw_client
            if enable_tracing and not _HAS_LANGSMITH:
                print("LangSmith not installed — tracing disabled")

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
        reasoning_effort: str | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "input": input,
            "tools": tools,
            "stream": stream,
        }
        if reasoning_effort and reasoning_effort != "none":
            kwargs["reasoning"] = {"effort": reasoning_effort}
        return await self._client.responses.create(**kwargs)

    @classmethod
    def from_settings(cls) -> OpenAIProvider:
        settings = get_settings()
        return cls(
            api_key=settings.openai_api_key,
            enable_tracing=not settings.is_production,
        )
