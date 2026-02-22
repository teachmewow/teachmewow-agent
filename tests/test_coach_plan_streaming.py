import json

import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from app.application.agent.models import CORE_STEP_IDS, build_default_coach_plan
from app.application.agent.nodes.coach_plan_node import CoachPlanNode
from app.application.agent.nodes.checklist_updater_node import ChecklistUpdaterNode
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


def test_default_plan_contains_required_core_steps() -> None:
    plan = build_default_coach_plan()
    existing_ids = {step.id for step in plan.steps}
    for step_id in CORE_STEP_IDS:
        assert step_id in existing_ids


@pytest.mark.asyncio
async def test_coach_plan_node_emits_plan_init(monkeypatch) -> None:
    emitted: list[tuple[str, dict]] = []

    async def _fake_dispatch(name: str, payload: dict, config=None) -> None:
        emitted.append((name, payload))

    monkeypatch.setattr(
        "app.application.agent.nodes.coach_plan_node.adispatch_custom_event",
        _fake_dispatch,
    )

    node = CoachPlanNode()
    state = _build_state(route="coach")
    update = await node(state)

    assert emitted
    assert emitted[0][0] == "plan_init"
    assert update["coach_plan"]["plan_id"].startswith("coach-plan-")


class _ChecklistModel:
    def with_structured_output(self, _schema):
        class _Runner:
            async def ainvoke(self, _messages):
                return type(
                    "_Decision",
                    (),
                    {
                        "updates": [
                            type(
                                "_Update",
                                (),
                                {
                                    "id": "core_skills",
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
    updated_steps = update["coach_plan"]["steps"]
    core_step = next(step for step in updated_steps if step["id"] == "core_skills")
    assert core_step["status"] == "completed"
