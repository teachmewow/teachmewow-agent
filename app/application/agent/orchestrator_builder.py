"""
OrchestratorBuilder — assembles the Orchestrator with all dependencies.

Centralizes tool registry setup, tools config, and provider wiring.
"""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.config import Settings, get_settings
from app.infrastructure.llm.provider import OpenAIProvider
from app.infrastructure.skills.loader import load_local_skills, load_skill_contents

from .orchestrator import Orchestrator
from .tools.build_lookup import BuildLookupHandler
from .tools.list_builds import ListBuildsHandler
from .tools.registry import ToolRegistry

SKILLS_ROOT = Path(__file__).resolve().parents[3] / "skills"


class OrchestratorBuilder:
    """Builds a fully wired Orchestrator instance."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def build(self) -> Orchestrator:
        provider = OpenAIProvider.from_settings()
        skill_defs = load_local_skills(SKILLS_ROOT)
        skill_contents = load_skill_contents(SKILLS_ROOT)
        tool_registry = self._build_tool_registry()
        tools_config = self._build_tools_config(skill_defs, tool_registry)

        return Orchestrator(
            provider=provider,
            model=self._settings.openai_main_model,
            tools_config=tools_config,
            tool_registry=tool_registry,
            reasoning_effort=self._settings.openai_reasoning_effort,
            skill_contents=skill_contents,
        )

    @staticmethod
    def _build_tool_registry() -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(ListBuildsHandler())
        registry.register(BuildLookupHandler())
        return registry

    def _build_tools_config(
        self,
        skill_defs: list[dict],
        registry: ToolRegistry,
    ) -> list[dict]:
        return [
            {
                "type": "web_search",
                "search_context_size": self._settings.openai_search_context_size,
                "filters": {"allowed_domains": ["wowhead.com", "icy-veins.com"]},
                "user_location": {"type": "approximate", "country": "US"},
            },
            {
                "type": "shell",
                "environment": {
                    "type": "local",
                    "skills": skill_defs,
                },
            },
            *registry.schemas(),
        ]
