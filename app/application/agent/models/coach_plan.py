from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CoachPlanStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class CoachPlanStepId(StrEnum):
    CORE_SKILLS = "core_skills"
    BUILD_VS_BASELINE = "build_vs_baseline"
    TIPS_AND_TRICKS = "tips_and_tricks"
    ASSUMPTIONS_CHECKED = "assumptions_checked"
    SOURCES_CONFIRMED = "sources_confirmed"
    SCENARIO_SPECIFICS = "scenario_specifics"


CORE_STEP_IDS: tuple[CoachPlanStepId, ...] = (
    CoachPlanStepId.CORE_SKILLS,
    CoachPlanStepId.BUILD_VS_BASELINE,
    CoachPlanStepId.TIPS_AND_TRICKS,
    CoachPlanStepId.ASSUMPTIONS_CHECKED,
)

OPTIONAL_STEP_IDS: tuple[CoachPlanStepId, ...] = (
    CoachPlanStepId.SOURCES_CONFIRMED,
    CoachPlanStepId.SCENARIO_SPECIFICS,
)


class CoachPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: CoachPlanStepId
    description: str
    status: CoachPlanStatus = CoachPlanStatus.PENDING
    is_core: bool
    observations: str | None = None


class CoachPlanStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: CoachPlanStepId
    status: CoachPlanStatus
    observations: str | None = None


class CoachPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    title: str
    steps: list[CoachPlanStep] = Field(default_factory=list)
    version: int = 1
    last_phase: Literal["init", "tool_iteration", "gate_evaluation"] = "init"
    should_ask_clarification: bool | None = None
    missing_fields: list[str] = Field(default_factory=list)

    def apply_updates(
        self,
        updates: list[CoachPlanStepUpdate],
        *,
        phase: Literal["tool_iteration", "gate_evaluation"],
        should_ask_clarification: bool | None = None,
        missing_fields: list[str] | None = None,
    ) -> CoachPlan:
        by_id = {step.id: step.model_copy(deep=True) for step in self.steps}
        for update in updates:
            if update.id not in by_id:
                raise RuntimeError(f"CoachPlan: unknown step id '{update.id}'")
            step = by_id[update.id]
            step.status = update.status
            if update.observations is not None:
                step.observations = update.observations
            by_id[update.id] = step

        return self.model_copy(
            update={
                "steps": [by_id[step.id] for step in self.steps],
                "version": self.version + 1,
                "last_phase": phase,
                "should_ask_clarification": should_ask_clarification,
                "missing_fields": missing_fields or [],
            }
        )

    def all_core_completed(self) -> bool:
        step_by_id = {step.id: step for step in self.steps}
        for step_id in CORE_STEP_IDS:
            step = step_by_id.get(step_id)
            if step is None:
                return False
            if step.status != CoachPlanStatus.COMPLETED:
                return False
        return True


def build_default_coach_plan() -> CoachPlan:
    return CoachPlan(
        plan_id=f"coach-plan-{uuid.uuid4()}",
        title="Build Coaching Analysis Plan",
        steps=[
            CoachPlanStep(
                id=CoachPlanStepId.CORE_SKILLS,
                description="Identify core skills and priorities for the active build.",
                status=CoachPlanStatus.PENDING,
                is_core=True,
            ),
            CoachPlanStep(
                id=CoachPlanStepId.BUILD_VS_BASELINE,
                description="Separate build-specific behavior from baseline Arms behavior.",
                status=CoachPlanStatus.PENDING,
                is_core=True,
            ),
            CoachPlanStep(
                id=CoachPlanStepId.TIPS_AND_TRICKS,
                description="Collect practical tips and tricks for the scenario.",
                status=CoachPlanStatus.PENDING,
                is_core=True,
            ),
            CoachPlanStep(
                id=CoachPlanStepId.ASSUMPTIONS_CHECKED,
                description="Check missing assumptions and ask clarification only if critical.",
                status=CoachPlanStatus.PENDING,
                is_core=True,
            ),
            CoachPlanStep(
                id=CoachPlanStepId.SOURCES_CONFIRMED,
                description="Validate grounded evidence and citation coverage.",
                status=CoachPlanStatus.PENDING,
                is_core=False,
            ),
            CoachPlanStep(
                id=CoachPlanStepId.SCENARIO_SPECIFICS,
                description="Capture scenario specifics (single vs aoe, raid vs mythic_plus).",
                status=CoachPlanStatus.PENDING,
                is_core=False,
            ),
        ],
        version=1,
        last_phase="init",
    )
