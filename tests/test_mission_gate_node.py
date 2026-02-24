import pytest

from app.application.agent.models import (
    CoachPlanStatus,
    MissionTag,
    build_default_coach_plan,
)
from app.application.agent.nodes.mission_gate_node import (
    MissionStatusItem,
    _build_gate_updates,
    _build_missing_context_notes,
    _normalize_core_mission_status,
)


def test_normalize_core_mission_status_defaults_missing() -> None:
    normalized = _normalize_core_mission_status(
        [
            MissionStatusItem(mission_tag="core_skills", status="done"),
            MissionStatusItem(mission_tag="tips_and_tricks", status="done"),
        ]
    )

    assert normalized["core_skills"] == "done"
    assert normalized["tips_and_tricks"] == "done"
    assert normalized["build_vs_baseline"] == "missing"
    assert normalized["assumptions_checked"] == "missing"


def test_normalize_core_mission_status_rejects_duplicate_mission() -> None:
    with pytest.raises(RuntimeError, match="duplicate mission key"):
        _normalize_core_mission_status(
            [
                MissionStatusItem(mission_tag="core_skills", status="done"),
                MissionStatusItem(mission_tag="core_skills", status="missing"),
            ]
        )


def test_build_gate_updates_always_completes_steps_and_marks_missing_context() -> None:
    plan = build_default_coach_plan()
    mission_status = {
        "core_skills": "done",
        "build_vs_baseline": "missing",
        "tips_and_tricks": "missing",
        "assumptions_checked": "done",
    }

    updates = _build_gate_updates(
        plan=plan,
        mission_status=mission_status,
        missing_missions=("build_vs_baseline", "tips_and_tricks"),
    )

    assert updates
    assert all(update.status == CoachPlanStatus.COMPLETED for update in updates)

    by_id = {update.id: update for update in updates}
    baseline_step = by_id["build_vs_baseline_split"]
    tips_step = by_id["scenario_tips"]
    assert baseline_step.observations is not None
    assert tips_step.observations is not None


def test_build_missing_context_notes_returns_human_messages() -> None:
    notes = _build_missing_context_notes(
        [
            MissionTag.CORE_SKILLS.value,
            MissionTag.BUILD_VS_BASELINE.value,
        ]
    )

    assert len(notes) == 2
    assert all("Missing context:" in note for note in notes)
