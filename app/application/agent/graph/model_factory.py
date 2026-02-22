from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool

from app.infrastructure.llm import LLMClient


@dataclass(frozen=True)
class GraphModels:
    agent_model: Any
    coach_model: Any
    classifier_model: Any


class GraphModelFactory:
    """
    Bind graph-facing models with the available tool surface.
    """

    def __init__(self, llm_client: LLMClient, tools: list[BaseTool]) -> None:
        self._llm_client = llm_client
        self._tools = tools

    def build(self) -> GraphModels:
        return GraphModels(
            agent_model=self._bind_tools(self._llm_client.main_model),
            coach_model=self._bind_tools(self._llm_client.explorer_model),
            classifier_model=self._llm_client.classifier_model,
        )

    def _bind_tools(self, model: Any) -> Any:
        if not self._tools:
            return model
        return model.bind_tools(self._tools)
