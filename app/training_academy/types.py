from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TrainingCourseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    role: str
    status: str
    summary: str | None = None
    sort_order: int
    learning_path_json: list[str] = Field(default_factory=list)
    checklist_json: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TrainingLessonView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    code: str
    title: str
    body: str
    sort_order: int
    checklist_json: list[str] = Field(default_factory=list)
    examples_json: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TrainingQuizView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    code: str
    title: str
    passing_score: float
    questions_json: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TrainingAttemptResult(BaseModel):
    attempt_id: int
    participant_id: int
    course_id: int
    quiz_id: int | None = None
    score: float
    passed: bool
    status: str
    correct_count: int
    total_count: int
    certification_id: int | None = None
    feedback: list[dict[str, Any]] = Field(default_factory=list)


class TrainingProgressResult(BaseModel):
    participant_id: int
    courses: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    gates: dict[str, dict[str, Any]] = Field(default_factory=dict)
    badges: list[str] = Field(default_factory=list)
