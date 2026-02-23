import pytest

from app.application.agent.nodes.mission_gate_node import (
    MissionStatusItem,
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
