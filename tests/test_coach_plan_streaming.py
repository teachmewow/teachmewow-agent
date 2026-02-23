import json

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from app.application.agent.models import (
    CORE_MISSION_TAGS,
    build_default_coach_plan,
)
from app.application.agent.nodes.checklist_updater_node import ChecklistUpdaterNode
from app.application.agent.nodes.coach_plan_node import CoachPlanNode
from app.application.agent.state_schema import AgentState, CharInfo


def _build_state(*, route: str, coach_plan: dict | None = None) -> AgentState:
    return AgentState(
        messages=[],
        thread_id="t-1",
        user_id="u-1",
        char_info=CharInfo(**{"class": "warrior", "spec": "arms", "role": "dps"}),
        route=route,
        coach_plan=coach_plan or {},
    )


def test_default_plan_contains_required_core_missions() -> None:
    plan = build_default_coach_plan()
    present_missions = {step.mission_tag for step in plan.steps}
    for mission_tag in CORE_MISSION_TAGS:
        assert mission_tag in present_missions


class _PlannerModel:
    def with_structured_output(self, schema):
        class _Runner:
            async def ainvoke(self, _messages, config=None):
                return schema.model_validate(
                    {
                        "title": "Raid ST Coaching Plan",
                        "steps": [
                            {
                                "id": "open_core_priority",
                                "description": "Map core skills and first priorities.",
                                "mission_tag": "core_skills",
                            },
                            {
                                "id": "separate_build_rules",
                                "description": "Separate build-specific vs baseline behavior.",
                                "mission_tag": "build_vs_baseline",
                            },
                            {
                                "id": "collect_practical_tips",
                                "description": "Gather practical execution tips for the scenario.",
                                "mission_tag": "tips_and_tricks",
                            },
                            {
                                "id": "validate_assumptions",
                                "description": "Check assumptions before final guidance.",
                                "mission_tag": "assumptions_checked",
                            },
                        ],
                    }
                )

        return _Runner()


@pytest.mark.asyncio
async def test_coach_plan_node_emits_plan_init(monkeypatch) -> None:
    emitted: list[tuple[str, dict]] = []

    async def _fake_dispatch(name: str, payload: dict, config=None) -> None:
        emitted.append((name, payload))

    monkeypatch.setattr(
        "app.application.agent.nodes.coach_plan_node.adispatch_custom_event",
        _fake_dispatch,
    )

    node = CoachPlanNode(classifier_model=_PlannerModel())
    state = _build_state(route="coach")
    state.messages = [HumanMessage(content="How to play this raid single-target build?")]
    update = await node(state)

    assert emitted
    assert emitted[0][0] == "plan_init"
    assert update["coach_plan"]["plan_id"].startswith("coach-plan-")
    assert "mission_tag" in update["coach_plan"]["steps"][0]
    assert "mission_tag" not in emitted[0][1]["steps"][0]


class _ChecklistModel:
    def with_structured_output(self, _schema):
        class _Runner:
            async def ainvoke(self, _messages, config=None):
                return type(
                    "_Decision",
                    (),
                    {
                        "updates": [
                            type(
                                "_Update",
                                (),
                                {
                                    "id": "core_skills_focus",
                                    "status": "completed",
                                    "observations": "Core priorities collected.",
                                },
                            )()
                        ],
                        "rationale": "Enough evidence for core skills.",
                    },
                )()

        return _Runner()


@pytest.mark.asyncio
async def test_checklist_updater_emits_plan_update(monkeypatch) -> None:
    emitted: list[tuple[str, dict]] = []

    async def _fake_dispatch(name: str, payload: dict, config=None) -> None:
        emitted.append((name, payload))

    monkeypatch.setattr(
        "app.application.agent.nodes.checklist_updater_node.adispatch_custom_event",
        _fake_dispatch,
    )

    plan = build_default_coach_plan().model_dump(mode="json")
    state = _build_state(route="coach", coach_plan=plan)
    state.messages = [
        HumanMessage(content="How should I play this build in raid?"),
        ToolMessage(
            content=json.dumps(
                {
                    "tool": "guide_context_lookup",
                    "citations": [{"citation_id": "source_1"}],
                    "evidence": [{"marker": "[[source_1]]", "text": "Use MS on CD."}],
                }
            ),
            tool_call_id="call-1",
        ),
    ]

    node = ChecklistUpdaterNode(classifier_model=_ChecklistModel())
    update = await node(state)

    assert emitted
    assert emitted[0][0] == "plan_update"
    assert "mission_tag" not in emitted[0][1]["steps"][0]
    updated_steps = update["coach_plan"]["steps"]
    core_step = next(step for step in updated_steps if step["id"] == "core_skills_focus")
    assert core_step["status"] == "completed"
