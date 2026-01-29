"""
LLM client wrapper using LangChain ChatOpenAI.
"""

from langchain_openai import ChatOpenAI

from app.infrastructure.config import get_settings


class LLMClient:
    """
    Wrapper around LangChain ChatOpenAI.
    Provides a consistent interface for LLM interactions.
    """

    def __init__(self, model: ChatOpenAI):
        self._model = model

    @classmethod
    def from_settings(cls) -> "LLMClient":
        """
        Create LLMClient from application settings.

        Returns:
            Configured LLMClient instance
        """
        settings = get_settings()
        model = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=0.7,
            streaming=True,
        )
        return cls(model=model)

    @property
    def model(self) -> ChatOpenAI:
        """Get the underlying ChatOpenAI model."""
        return self._model

    def with_temperature(self, temperature: float) -> "LLMClient":
        """
        Create a new client with different temperature.

        Args:
            temperature: Temperature value (0-2)

        Returns:
            New LLMClient with updated temperature
        """
        new_model = ChatOpenAI(
            api_key=self._model.openai_api_key,
            model=self._model.model_name,
            temperature=temperature,
            streaming=True,
        )
        return LLMClient(model=new_model)
