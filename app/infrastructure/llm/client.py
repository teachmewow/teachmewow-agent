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

    def __init__(
        self,
        main_model: ChatOpenAI,
        explorer_model: ChatOpenAI,
        classifier_model: ChatOpenAI,
    ):
        self._main_model = main_model
        self._explorer_model = explorer_model
        self._classifier_model = classifier_model

    @classmethod
    def from_settings(cls) -> "LLMClient":
        """
        Create LLMClient from application settings.

        Returns:
            Configured LLMClient instance
        """
        settings = get_settings()
        main_model = cls._build_model(
            api_key=settings.openai_api_key,
            model_name=settings.openai_main_model or settings.openai_model,
        )
        explorer_model = cls._build_model(
            api_key=settings.openai_api_key,
            model_name=settings.openai_explorer_model or settings.openai_model,
            reasoning_effort=settings.openai_explorer_reasoning_effort,
            reasoning_summary=settings.openai_explorer_reasoning_summary,
        )
        classifier_model = cls._build_model(
            api_key=settings.openai_api_key,
            model_name=settings.openai_classifier_model or settings.openai_model,
            temperature=0.2,
        )
        return cls(
            main_model=main_model,
            explorer_model=explorer_model,
            classifier_model=classifier_model,
        )

    @property
    def main_model(self) -> ChatOpenAI:
        """Get the model used by the main agent."""
        return self._main_model

    @property
    def explorer_model(self) -> ChatOpenAI:
        """Get the model used by the knowledge explorer."""
        return self._explorer_model

    @property
    def classifier_model(self) -> ChatOpenAI:
        """Get the model used by classifiers/routers."""
        return self._classifier_model

    def with_temperature(self, temperature: float) -> "LLMClient":
        """
        Create a new client with different temperature.

        Args:
            temperature: Temperature value (0-2)

        Returns:
            New LLMClient with updated temperature
        """
        main_model = self._clone_model(self._main_model, temperature)
        explorer_model = self._clone_model(self._explorer_model, temperature)
        classifier_model = self._clone_model(self._classifier_model, temperature)
        return LLMClient(
            main_model=main_model,
            explorer_model=explorer_model,
            classifier_model=classifier_model,
        )

    @staticmethod
    def _build_model(
        api_key: str,
        model_name: str,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        reasoning_summary: str | None = None,
    ) -> ChatOpenAI:
        extra_args = {}
        if reasoning_effort is not None or reasoning_summary is not None:
            reasoning = {}
            if reasoning_effort is not None:
                reasoning["effort"] = reasoning_effort
            if reasoning_summary is not None:
                reasoning["summary"] = reasoning_summary
            extra_args["reasoning"] = reasoning
        return ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=temperature,
            streaming=True,
            **extra_args,
        )

    @staticmethod
    def _clone_model(model: ChatOpenAI, temperature: float) -> ChatOpenAI:
        return ChatOpenAI(
            api_key=model.openai_api_key,
            model=model.model_name,
            temperature=temperature,
            streaming=True,
        )
