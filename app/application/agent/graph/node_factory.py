from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import BaseTool

from app.application.agent.nodes.checklist_updater_node import ChecklistUpdaterNode
from app.application.agent.nodes.coach_plan_node import CoachPlanNode
from app.application.agent.nodes.llm_node import LLMNode
from app.application.agent.nodes.mission_gate_node import MissionGateNode
from app.application.agent.nodes.routing_node import RoutingNode
from app.application.agent.nodes.tool_node import ToolNode
from app.application.agent.prompts.coach_prompt import COACH_SYSTEM_PROMPT

from .model_factory import GraphModels


@dataclass(frozen=True)
class GraphNodes:
    router: RoutingNode
    coach_plan: CoachPlanNode
    agent: LLMNode
    coach_agent: LLMNode
    tools: ToolNode
    checklist_updater: ChecklistUpdaterNode
    mission_gate: MissionGateNode


class GraphNodeFactory:
    """
    Create graph nodes from pre-bound models and shared dependencies.
    """

    def __init__(self, models: GraphModels, tools: list[BaseTool]) -> None:
        self._models = models
        self._tools = tools

    def build(self) -> GraphNodes:
        return GraphNodes(
            router=RoutingNode(self._models.classifier_model),
            coach_plan=CoachPlanNode(self._models.classifier_model),
            agent=LLMNode(self._models.agent_model),
            coach_agent=LLMNode(
                self._models.coach_model,
                system_prompt=COACH_SYSTEM_PROMPT,
            ),
            tools=ToolNode(self._tools),
            checklist_updater=ChecklistUpdaterNode(self._models.classifier_model),
            mission_gate=MissionGateNode(self._models.classifier_model),
        )
