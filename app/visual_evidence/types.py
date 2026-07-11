from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VisualEvidencePolicy(BaseModel):
    """Explicit thresholds for evidence derived from real extracted frames."""

    min_frame_count: int = Field(default=2, ge=2, le=30)
    min_short_side_px: int = Field(default=720, ge=64, le=4320)
    min_long_side_px: int = Field(default=1280, ge=64, le=7680)
    perceptual_duplicate_distance: int = Field(default=3, ge=0, le=64)
    min_unique_frame_ratio: float = Field(default=0.60, gt=0, le=1)
    max_freeze_run_ratio: float = Field(default=0.60, gt=0, le=1)
    min_freeze_run_frames: int = Field(default=3, ge=2, le=30)
    ocr_required: bool = False
    ocr_language: str = Field(default="rus+eng", min_length=2, max_length=80)
    ocr_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    min_ocr_token_length: int = Field(default=2, ge=1, le=20)
    required_token_match_ratio: Literal[1.0] = 1.0
    max_ocr_tokens: int = Field(default=96, ge=1, le=512)


class ReferenceTextInput(BaseModel):
    """Trusted reference supplied by ProductAsset metadata or operator input.

    The service never downloads ``asset_path``. It may only inspect a local file.
    ``declared_text`` and ``required_tokens`` must be values supplied by the caller;
    they are not inferred from a filename or URL.
    """

    source_kind: Literal["product_asset", "product_input", "operator_input"]
    source_ref: str = Field(min_length=1, max_length=240)
    required_tokens: list[str] = Field(default_factory=list, max_length=96)
    declared_text: str | None = Field(default=None, max_length=4000)
    asset_path: str | None = Field(default=None, max_length=1000)


class FrameVisualEvidence(BaseModel):
    index: int = Field(ge=1)
    path: str
    decoded: bool = False
    image_format: str | None = None
    width: int | None = None
    height: int | None = None
    short_side_px: int | None = None
    long_side_px: int | None = None
    sha256: str | None = None
    perceptual_hash: str | None = None
    blockers: list[str] = Field(default_factory=list)


class OCRVisualEvidence(BaseModel):
    required: bool = False
    status: Literal[
        "not_required",
        "passed",
        "blocked",
    ] = "not_required"
    backend: str | None = None
    tool_available: bool | None = None
    reference_source_refs: list[str] = Field(default_factory=list)
    expected_tokens: list[str] = Field(default_factory=list)
    observed_tokens: list[str] = Field(default_factory=list)
    matched_tokens: list[str] = Field(default_factory=list)
    missing_tokens: list[str] = Field(default_factory=list)
    token_match_ratio: float | None = Field(default=None, ge=0, le=1)
    processed_frame_count: int = Field(default=0, ge=0)
    blockers: list[str] = Field(default_factory=list)


class VisualEvidenceReport(BaseModel):
    status: Literal["passed", "blocked"] = "blocked"
    frame_count: int = Field(default=0, ge=0)
    decoded_frame_count: int = Field(default=0, ge=0)
    unique_frame_count: int = Field(default=0, ge=0)
    unique_frame_ratio: float | None = Field(default=None, ge=0, le=1)
    longest_duplicate_run: int = Field(default=0, ge=0)
    freeze_run_ratio: float | None = Field(default=None, ge=0, le=1)
    minimum_short_side_observed_px: int | None = Field(default=None, ge=0)
    minimum_long_side_observed_px: int | None = Field(default=None, ge=0)
    policy: VisualEvidencePolicy
    frames: list[FrameVisualEvidence] = Field(default_factory=list)
    ocr: OCRVisualEvidence
    blockers: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
