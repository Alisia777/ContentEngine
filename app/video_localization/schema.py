"""Strict planning contracts for owned/licensed video localization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re

from app.competitive_intelligence import SourceRelationship


_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")


class LocalizationMode(StrEnum):
    SUBTITLES = "subtitles"
    DUB_AUDIO = "dub_audio"
    LIP_SYNC = "lip_sync"


class LocalizationProvider(StrEnum):
    INTERNAL_CAPTIONS = "internal_captions"
    ELEVENLABS_DUBBING = "elevenlabs_dubbing"
    HEYGEN_AUDIO = "heygen_audio"
    HEYGEN_LIPSYNC_SPEED = "heygen_lipsync_speed"
    HEYGEN_LIPSYNC_PRECISION = "heygen_lipsync_precision"
    SEEDANCE_BASELINE = "seedance2_fast_baseline"


@dataclass(frozen=True, slots=True)
class VideoSource:
    source_id: str
    sku: str
    category_key: str
    duration_seconds: int
    source_language: str
    source_relationship: SourceRelationship
    rights_confirmed: bool
    qa_approved: bool
    asset_sha256: str
    speech_present: bool = True
    on_screen_text_present: bool = False

    def __post_init__(self) -> None:
        for value, limit, code in (
            (self.source_id, 180, "source_id_invalid"),
            (self.sku, 120, "sku_invalid"),
            (self.category_key, 80, "category_key_invalid"),
        ):
            if not value or len(value) > limit:
                raise ValueError(code)
        if not 1 <= self.duration_seconds <= 3_600:
            raise ValueError("duration_invalid")
        if not _LANGUAGE.fullmatch(self.source_language):
            raise ValueError("source_language_invalid")
        if not _SHA256.fullmatch(self.asset_sha256):
            raise ValueError("asset_sha256_invalid")

    @property
    def exact_localization_eligible(self) -> bool:
        return (
            self.source_relationship in {SourceRelationship.OWNED, SourceRelationship.LICENSED}
            and self.rights_confirmed
            and self.qa_approved
        )


@dataclass(frozen=True, slots=True)
class LocalizationRateCard:
    """Versioned provider-cost snapshot in micro-US-dollars.

    ``internal_captions_microusd_per_minute`` is a conservative budget envelope
    for transcription, translation and rendering, not a vendor invoice.
    """

    snapshot_id: str
    internal_captions_microusd_per_minute: int
    elevenlabs_dubbing_microusd_per_minute: int
    heygen_audio_microusd_per_second: int
    heygen_lipsync_speed_microusd_per_second: int
    heygen_lipsync_precision_microusd_per_second: int
    seedance_baseline_microusd_per_second: int

    def __post_init__(self) -> None:
        if not self.snapshot_id or len(self.snapshot_id) > 120:
            raise ValueError("snapshot_id_invalid")
        for value in (
            self.internal_captions_microusd_per_minute,
            self.elevenlabs_dubbing_microusd_per_minute,
            self.heygen_audio_microusd_per_second,
            self.heygen_lipsync_speed_microusd_per_second,
            self.heygen_lipsync_precision_microusd_per_second,
            self.seedance_baseline_microusd_per_second,
        ):
            if value < 0:
                raise ValueError("negative_rate")


@dataclass(frozen=True, slots=True)
class LocalizationAssignment:
    assignment_id: str
    sequence: int
    wave: int
    source_id: str
    sku: str
    category_key: str
    source_language: str
    target_language: str
    mode: LocalizationMode
    provider: LocalizationProvider
    duration_seconds: int
    estimated_cost_microusd: int
    requires_manual_text_edit: bool = False
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.assignment_id or len(self.assignment_id) > 96:
            raise ValueError("assignment_id_invalid")
        if self.sequence < 1 or self.wave < 1:
            raise ValueError("assignment_position_invalid")
        if not _LANGUAGE.fullmatch(self.source_language):
            raise ValueError("source_language_invalid")
        if not _LANGUAGE.fullmatch(self.target_language):
            raise ValueError("target_language_invalid")
        if self.source_language == self.target_language:
            raise ValueError("target_language_must_differ")
        if self.duration_seconds < 1:
            raise ValueError("duration_invalid")
        if self.estimated_cost_microusd < 0:
            raise ValueError("estimated_cost_invalid")


@dataclass(frozen=True, slots=True)
class ProviderCost:
    provider: LocalizationProvider
    assignment_count: int
    estimated_cost_microusd: int

    def __post_init__(self) -> None:
        if self.assignment_count < 1:
            raise ValueError("assignment_count_invalid")
        if self.estimated_cost_microusd < 0:
            raise ValueError("estimated_cost_invalid")


@dataclass(frozen=True, slots=True)
class LocalizationBatchPlan:
    plan_id: str
    rate_card_snapshot_id: str
    target_count: int
    assignments: tuple[LocalizationAssignment, ...]
    provider_costs: tuple[ProviderCost, ...]
    total_estimated_cost_microusd: int
    full_generation_baseline_microusd: int
    estimated_savings_ratio: float
    qa_gate_after_sequence: int
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.plan_id or len(self.plan_id) > 96:
            raise ValueError("plan_id_invalid")
        if self.target_count != len(self.assignments):
            raise ValueError("target_count_mismatch")
        if self.target_count < 1:
            raise ValueError("target_count_invalid")
        if not 1 <= self.qa_gate_after_sequence <= self.target_count:
            raise ValueError("qa_gate_invalid")
        if self.total_estimated_cost_microusd < 0 or self.full_generation_baseline_microusd < 0:
            raise ValueError("cost_invalid")
        if not 0 <= self.estimated_savings_ratio <= 1:
            raise ValueError("savings_ratio_invalid")
        combinations = {
            (item.source_id, item.target_language, item.mode)
            for item in self.assignments
        }
        if len(combinations) != len(self.assignments):
            raise ValueError("duplicate_assignment")
