from __future__ import annotations

import re
import uuid
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CoachPlanStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class MissionTag(StrEnum):
    CORE_SKILLS = "core_skills"
    BUILD_VS_BASELINE = "build_vs_baseline"
    TIPS_AND_TRICKS = "tips_and_tricks"
    ASSUMPTIONS_CHECKED = "assumptions_checked"
    SOURCES_CONFIRMED = "sources_confirmed"
    SCENARIO_SPECIFICS = "scenario_specifics"


CORE_MISSION_TAGS: tuple[MissionTag, ...] = (
    MissionTag.CORE_SKILLS,
    MissionTag.BUILD_VS_BASELINE,
    MissionTag.TIPS_AND_TRICKS,
    MissionTag.ASSUMPTIONS_CHECKED,
)

OPTIONAL_MISSION_TAGS: tuple[MissionTag, ...] = (
    MissionTag.SOURCES_CONFIRMED,
    MissionTag.SCENARIO_SPECIFICS,
)

MIN_PLAN_STEPS = 2
MAX_PLAN_STEPS = 5
_STEP_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def _validate_step_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("step id is required")
    if normalized.lower() != normalized:
        raise ValueError("step id must be lowercase")
    if not _STEP_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "step id must match regex: ^[a-z0-9][a-z0-9_-]{1,63}$"
        )
    return normalized


class CoachPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    mission_tag: MissionTag
    status: CoachPlanStatus = CoachPlanStatus.PENDING
    is_core: bool
    observations: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_step_id(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("description is required")
        return normalized


class CoachPlanStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: CoachPlanStatus
    observations: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_step_id(value)


class CoachPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    title: str
    steps: list[CoachPlanStep] = Field(default_factory=list)
    version: int = 1
    last_phase: Literal["init", "tool_iteration", "gate_evaluation"] = "init"
    should_ask_clarification: bool | None = None
    missing_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_invariants(self) -> CoachPlan:
        if len(self.steps) < MIN_PLAN_STEPS or len(self.steps) > MAX_PLAN_STEPS:
            raise ValueError(
                f"coach plan must contain between {MIN_PLAN_STEPS} and {MAX_PLAN_STEPS} steps"
            )

        seen_ids: set[str] = set()
        for step in self.steps:
            if step.id in seen_ids:
                raise ValueError(f"duplicate coach plan step id: {step.id}")
            seen_ids.add(step.id)

        available_core_tags = {step.mission_tag for step in self.steps}
        missing_core = [
            tag.value for tag in CORE_MISSION_TAGS if tag not in available_core_tags
        ]
        if missing_core:
            raise ValueError(
                "coach plan must cover all core missions: "
                + ", ".join(sorted(missing_core))
            )

        return self

    def apply_updates(
        self,
        updates: list[CoachPlanStepUpdate],
        *,
        phase: Literal["tool_iteration", "gate_evaluation"],
        should_ask_clarification: bool | None = None,
        missing_fields: list[str] | None = None,
    ) -> CoachPlan:
        by_id: dict[str, CoachPlanStep] = {
            step.id: step.model_copy(deep=True) for step in self.steps
        }
        seen_update_ids: set[str] = set()
        for update in updates:
            if update.id in seen_update_ids:
                raise RuntimeError(
                    f"CoachPlan: duplicate update id '{update.id}' is not allowed"
                )
            seen_update_ids.add(update.id)
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

    def is_mission_completed(self, mission_tag: MissionTag) -> bool:
        return any(
            step.mission_tag == mission_tag and step.status == CoachPlanStatus.COMPLETED
            for step in self.steps
        )

    def all_core_completed(self) -> bool:
        for mission_tag in CORE_MISSION_TAGS:
            if not self.is_mission_completed(mission_tag):
                return False
        return True

    def to_public_payload(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "version": self.version,
            "last_phase": self.last_phase,
            "should_ask_clarification": self.should_ask_clarification,
            "missing_fields": list(self.missing_fields),
            "steps": [
                {
                    "id": step.id,
                    "description": step.description,
                    "status": step.status.value,
                    "is_core": step.is_core,
                    "observations": step.observations,
                }
                for step in self.steps
            ],
        }


class CoachPlanDraftStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    mission_tag: MissionTag

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _validate_step_id(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("description is required")
        return normalized


class CoachPlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    steps: list[CoachPlanDraftStep]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("title is required")
        return normalized

    @model_validator(mode="after")
    def validate_size(self) -> CoachPlanDraft:
        if len(self.steps) < MIN_PLAN_STEPS or len(self.steps) > MAX_PLAN_STEPS:
            raise ValueError(
                f"planner must return between {MIN_PLAN_STEPS} and {MAX_PLAN_STEPS} steps"
            )
        return self

    def to_plan(self) -> CoachPlan:
        return CoachPlan(
            plan_id=f"coach-plan-{uuid.uuid4()}",
            title=self.title,
            steps=[
                CoachPlanStep(
                    id=step.id,
                    description=step.description,
                    mission_tag=step.mission_tag,
                    status=CoachPlanStatus.PENDING,
                    is_core=step.mission_tag in CORE_MISSION_TAGS,
                )
                for step in self.steps
            ],
            version=1,
            last_phase="init",
        )


def build_default_coach_plan() -> CoachPlan:
    return CoachPlanDraft(
        title="Build Coaching Analysis Plan",
        steps=[
            CoachPlanDraftStep(
                id="core_skills_focus",
                description="Identify the build's highest-impact core skills and priorities.",
                mission_tag=MissionTag.CORE_SKILLS,
            ),
            CoachPlanDraftStep(
                id="build_vs_baseline_split",
                description="Separate build-specific behavior from baseline Arms behavior.",
                mission_tag=MissionTag.BUILD_VS_BASELINE,
            ),
            CoachPlanDraftStep(
                id="scenario_tips",
                description="Collect practical tips and tricks for the selected scenario.",
                mission_tag=MissionTag.TIPS_AND_TRICKS,
            ),
            CoachPlanDraftStep(
                id="assumptions_validation",
                description="Validate missing assumptions before final guidance.",
                mission_tag=MissionTag.ASSUMPTIONS_CHECKED,
            ),
        ],
    ).to_plan()
