from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompletionCriterion(BaseModel):
    """One observable, auditable condition for completing a learning step."""

    code: str
    label: str
    satisfied: bool
    evidence_source: Literal["training_attempt", "factory_event"]
    evidence_id: int | None = None
    observed_at: datetime | None = None


class LearningStep(BaseModel):
    code: str
    order: int
    title: str
    purpose: str
    estimated_minutes: int
    status: Literal["completed", "current", "upcoming"]
    progress_percent: int
    module_code: str | None = None
    lesson_title: str | None = None
    action_label: str
    action_href: str
    completion_criteria: list[CompletionCriterion] = Field(default_factory=list)


class NextLearningMove(BaseModel):
    kind: Literal["lesson", "action", "complete"]
    step_code: str | None = None
    title: str
    label: str
    href: str
    module_code: str | None = None
    lesson_title: str | None = None


class NoviceLearningPath(BaseModel):
    user_profile_id: int
    organization_id: int
    role: str
    active_factory_run_id: str | None = None
    steps: list[LearningStep]
    completed_steps: int
    total_steps: int
    satisfied_criteria: int
    total_criteria: int
    progress_percent: int
    is_complete: bool
    next_move: NextLearningMove


class QuizQuestionResult(BaseModel):
    question_id: int
    correct: bool
    explanation: str | None = None


class QuizSubmissionResult(BaseModel):
    module_code: str
    attempt_id: int
    certification_id: int | None = None
    score: float
    passing_threshold: float
    passed: bool
    correct_count: int
    total_count: int
    attempt_created: bool
    certification_created: bool
    question_results: list[QuizQuestionResult] = Field(default_factory=list)
