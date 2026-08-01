"""Deterministic Harly-style localization batch planning and cost previews."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
import math

from .schema import (
    LocalizationAssignment,
    LocalizationBatchPlan,
    LocalizationMode,
    LocalizationProvider,
    LocalizationRateCard,
    ProviderCost,
    VideoSource,
)


class LocalizationPlanError(ValueError):
    """A fail-closed localization planning error."""


DEFAULT_PROVIDER_BY_MODE: Mapping[LocalizationMode, LocalizationProvider] = {
    LocalizationMode.SUBTITLES: LocalizationProvider.INTERNAL_CAPTIONS,
    LocalizationMode.DUB_AUDIO: LocalizationProvider.ELEVENLABS_DUBBING,
    LocalizationMode.LIP_SYNC: LocalizationProvider.HEYGEN_LIPSYNC_SPEED,
}


def default_rate_card_2026_08_01() -> LocalizationRateCard:
    """Return the audited cost snapshot used for dry-run comparisons.

    Values are micro-USD. The subtitle rate is an internal budget envelope;
    other values mirror the public provider rate snapshot documented in
    ``docs/HARLY_10X_LOCALIZATION_V1.md``.
    """

    return LocalizationRateCard(
        snapshot_id="2026-08-01.public-provider-rate-card.v1",
        internal_captions_microusd_per_minute=50_000,
        elevenlabs_dubbing_microusd_per_minute=500_000,
        heygen_audio_microusd_per_second=33_300,
        heygen_lipsync_speed_microusd_per_second=33_300,
        heygen_lipsync_precision_microusd_per_second=66_700,
        seedance_baseline_microusd_per_second=290_000,
    )


def _validate_language(value: str) -> str:
    language = str(value or "").strip().lower()
    if not language:
        raise LocalizationPlanError("target_language_required")
    if len(language) > 35 or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
        for character in language
    ):
        raise LocalizationPlanError("target_language_invalid")
    pieces = language.split("-")
    if not 2 <= len(pieces[0]) <= 3 or not all(
        2 <= len(piece) <= 8 for piece in pieces[1:]
    ):
        raise LocalizationPlanError("target_language_invalid")
    return language


def _provider_cost(
    provider: LocalizationProvider,
    *,
    duration_seconds: int,
    rate_card: LocalizationRateCard,
) -> int:
    if provider is LocalizationProvider.INTERNAL_CAPTIONS:
        return math.ceil(
            duration_seconds
            * rate_card.internal_captions_microusd_per_minute
            / 60
        )
    if provider is LocalizationProvider.ELEVENLABS_DUBBING:
        return math.ceil(
            duration_seconds
            * rate_card.elevenlabs_dubbing_microusd_per_minute
            / 60
        )
    if provider is LocalizationProvider.HEYGEN_AUDIO:
        return duration_seconds * rate_card.heygen_audio_microusd_per_second
    if provider is LocalizationProvider.HEYGEN_LIPSYNC_SPEED:
        return duration_seconds * rate_card.heygen_lipsync_speed_microusd_per_second
    if provider is LocalizationProvider.HEYGEN_LIPSYNC_PRECISION:
        return duration_seconds * rate_card.heygen_lipsync_precision_microusd_per_second
    if provider is LocalizationProvider.SEEDANCE_BASELINE:
        return duration_seconds * rate_card.seedance_baseline_microusd_per_second
    raise LocalizationPlanError("provider_not_supported")


def _provider_for(
    mode: LocalizationMode,
    overrides: Mapping[LocalizationMode, LocalizationProvider],
) -> LocalizationProvider:
    provider = overrides.get(mode, DEFAULT_PROVIDER_BY_MODE[mode])
    valid = {
        LocalizationMode.SUBTITLES: {LocalizationProvider.INTERNAL_CAPTIONS},
        LocalizationMode.DUB_AUDIO: {
            LocalizationProvider.ELEVENLABS_DUBBING,
            LocalizationProvider.HEYGEN_AUDIO,
        },
        LocalizationMode.LIP_SYNC: {
            LocalizationProvider.HEYGEN_LIPSYNC_SPEED,
            LocalizationProvider.HEYGEN_LIPSYNC_PRECISION,
        },
    }
    if provider not in valid[mode]:
        raise LocalizationPlanError("provider_mode_mismatch")
    return provider


def _stable_id(prefix: str, payload: object, *, length: int = 24) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"{prefix}-{digest[:length]}"


def build_localization_batch(
    sources: Sequence[VideoSource] | Iterable[VideoSource],
    *,
    target_languages: Sequence[str],
    modes: Sequence[LocalizationMode] = (
        LocalizationMode.SUBTITLES,
        LocalizationMode.DUB_AUDIO,
    ),
    target_count: int = 10,
    provider_overrides: Mapping[LocalizationMode, LocalizationProvider] | None = None,
    rate_card: LocalizationRateCard | None = None,
    qa_gate_after_sequence: int = 2,
) -> LocalizationBatchPlan:
    """Build a unique, rights-safe localization batch with a hard QA wave.

    The Harly pilot is expected to use five owned/licensed sources, one target
    language and two modes (subtitles + dubbing), yielding exactly ten outputs.
    No paid provider is called by this function.
    """

    source_list = list(sources)
    if not 1 <= target_count <= 100:
        raise LocalizationPlanError("target_count_invalid")
    if not source_list:
        raise LocalizationPlanError("sources_required")
    if len({item.source_id for item in source_list}) != len(source_list):
        raise LocalizationPlanError("duplicate_source_id")
    if not modes:
        raise LocalizationPlanError("modes_required")
    if len(set(modes)) != len(modes):
        raise LocalizationPlanError("duplicate_mode")

    languages = tuple(dict.fromkeys(_validate_language(item) for item in target_languages))
    if not languages:
        raise LocalizationPlanError("target_languages_required")

    for source in source_list:
        if not source.exact_localization_eligible:
            raise LocalizationPlanError(
                f"source_not_owned_licensed_or_approved:{source.source_id}"
            )

    overrides = dict(provider_overrides or {})
    selected_rate_card = rate_card or default_rate_card_2026_08_01()

    combinations: list[tuple[VideoSource, str, LocalizationMode, LocalizationProvider]] = []
    skipped_speech_modes = 0
    for source in source_list:
        for language in languages:
            if language == source.source_language:
                continue
            for mode in modes:
                if (
                    mode in {LocalizationMode.DUB_AUDIO, LocalizationMode.LIP_SYNC}
                    and not source.speech_present
                ):
                    skipped_speech_modes += 1
                    continue
                combinations.append(
                    (source, language, mode, _provider_for(mode, overrides))
                )

    if len(combinations) < target_count:
        detail = (
            "speech_modes_unavailable"
            if skipped_speech_modes
            else "unique_combinations_missing"
        )
        raise LocalizationPlanError(
            f"not_enough_unique_localization_combinations:{detail}:"
            f"{len(combinations)}/{target_count}"
        )

    selected = combinations[:target_count]
    if not 1 <= qa_gate_after_sequence <= target_count:
        raise LocalizationPlanError("qa_gate_invalid")

    assignments: list[LocalizationAssignment] = []
    for index, (source, language, mode, provider) in enumerate(selected, start=1):
        reasons = [
            "owned_or_licensed_source",
            "rights_and_source_qa_confirmed",
            "provider_cost_preview_only",
        ]
        if source.on_screen_text_present:
            reasons.append("on_screen_text_requires_manual_edit")
        if index == qa_gate_after_sequence:
            reasons.append("human_qa_gate_after_this_assignment")
        assignments.append(
            LocalizationAssignment(
                assignment_id=_stable_id(
                    "loc",
                    {
                        "source_id": source.source_id,
                        "asset_sha256": source.asset_sha256,
                        "target_language": language,
                        "mode": mode.value,
                        "provider": provider.value,
                        "rate_card": selected_rate_card.snapshot_id,
                    },
                ),
                sequence=index,
                wave=1 if index <= qa_gate_after_sequence else 2,
                source_id=source.source_id,
                sku=source.sku,
                category_key=source.category_key,
                source_language=source.source_language,
                target_language=language,
                mode=mode,
                provider=provider,
                duration_seconds=source.duration_seconds,
                estimated_cost_microusd=_provider_cost(
                    provider,
                    duration_seconds=source.duration_seconds,
                    rate_card=selected_rate_card,
                ),
                requires_manual_text_edit=source.on_screen_text_present,
                reason_codes=tuple(reasons),
            )
        )

    total = sum(item.estimated_cost_microusd for item in assignments)
    baseline = sum(
        _provider_cost(
            LocalizationProvider.SEEDANCE_BASELINE,
            duration_seconds=item.duration_seconds,
            rate_card=selected_rate_card,
        )
        for item in assignments
    )
    savings = 0.0 if baseline <= 0 else max(0.0, min(1.0, 1 - total / baseline))

    provider_counts = Counter(item.provider for item in assignments)
    provider_totals = Counter()
    for item in assignments:
        provider_totals[item.provider] += item.estimated_cost_microusd
    provider_costs = tuple(
        ProviderCost(
            provider=provider,
            assignment_count=provider_counts[provider],
            estimated_cost_microusd=provider_totals[provider],
        )
        for provider in sorted(provider_counts, key=lambda item: item.value)
    )

    plan_basis = {
        "rate_card": selected_rate_card.snapshot_id,
        "target_count": target_count,
        "qa_gate": qa_gate_after_sequence,
        "assignments": [item.assignment_id for item in assignments],
    }
    reason_codes = [
        (
            "ten_output_localization_batch"
            if target_count == 10
            else "bounded_localization_batch"
        ),
        "first_wave_requires_human_qa",
        "full_generation_is_cost_baseline_only",
        "provider_calls_not_started",
    ]
    if any(item.requires_manual_text_edit for item in assignments):
        reason_codes.append("manual_on_screen_text_work_present")

    return LocalizationBatchPlan(
        plan_id=_stable_id("localization-plan", plan_basis, length=32),
        rate_card_snapshot_id=selected_rate_card.snapshot_id,
        target_count=target_count,
        assignments=tuple(assignments),
        provider_costs=provider_costs,
        total_estimated_cost_microusd=total,
        full_generation_baseline_microusd=baseline,
        estimated_savings_ratio=round(savings, 8),
        qa_gate_after_sequence=qa_gate_after_sequence,
        reason_codes=tuple(reason_codes),
    )


def microusd_to_usd(value: int) -> str:
    if value < 0:
        raise LocalizationPlanError("cost_invalid")
    return f"{value / 1_000_000:.4f}"
