from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


PASS_STATUSES = {"pass", "passed", "ok", "ready", "approved"}
FAIL_STATUSES = {"fail", "failed", "drift", "missing", "generic_ai", "mismatch", "rejected"}
NEEDS_REVIEW_STATUSES = {"needs_review", "pending", "unknown", "manual_review_required"}


class FrameExtractionOutput(BaseModel):
    id: int
    video_job_id: int
    status: str
    frame_paths: list[str] = Field(default_factory=list)
    contact_sheet_path: str | None = None
    duration_seconds: float
    fps: float
    warnings: list[str] = Field(default_factory=list)


class OutputAcceptanceOutput(BaseModel):
    id: int
    video_job_id: int
    ai_production_brief_id: int
    director_prompt_pack_id: int | None = None
    status: str
    product_identity_status: str
    packaging_status: str
    geometry_status: str
    blogger_authenticity_status: str
    scene_match_status: str
    proof_moment_status: str
    cta_status: str
    publishing_readiness: str
    score: float
    blockers: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    contact_sheet_path: str | None = None
    keyframes: list[dict[str, Any]] = Field(default_factory=list)
    reviewer_notes: str | None = None


class OutputQualityResult(BaseModel):
    status: str
    publishing_readiness: str
    score: float
    blockers: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    normalized_statuses: dict[str, str] = Field(default_factory=dict)
