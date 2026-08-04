"""Deterministic recent-versus-baseline structural trend detection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.competitive_intelligence.schema import PublicCreativeObservation, SocialPlatform, StructuralProfile

from .schema import (
    StructuralFeature,
    StructuralSignal,
    TrendCorroboration,
    TrendDirection,
    TrendFreshness,
    TrendHypothesis,
)


class CategoryTrendError(ValueError):
    """A fail-closed category trend input error."""


@dataclass(frozen=True, slots=True)
class ObservationWindows:
    recent: tuple[PublicCreativeObservation, ...]
    baseline: tuple[PublicCreativeObservation, ...]

    @property
    def all(self) -> tuple[PublicCreativeObservation, ...]:
        return self.recent + self.baseline


def structural_signals(profile: StructuralProfile) -> tuple[StructuralSignal, ...]:
    """Project a profile into the only features that category learning may use."""

    candidates = (
        (StructuralFeature.HOOK_TYPE, profile.hook_type.value),
        (StructuralFeature.PACING, profile.pacing.value),
        (StructuralFeature.PROOF_TYPE, profile.proof_type.value),
        (StructuralFeature.CTA_STYLE, profile.cta_style.value),
        (StructuralFeature.SHOT_COUNT_BUCKET, profile.shot_count_bucket),
        (StructuralFeature.PRODUCT_VISIBILITY, profile.product_visibility),
    )
    return tuple(
        StructuralSignal(feature=feature, value=value)
        for feature, value in candidates
        if value != "unknown"
    )


def build_observation_windows(
    observations: Iterable[PublicCreativeObservation],
    *,
    category_key: str,
    platform: SocialPlatform,
    as_of: datetime,
    recent_window_days: int = 7,
    baseline_window_days: int = 28,
) -> ObservationWindows:
    """Select deduplicated eligible observations inside explicit time windows."""

    if not category_key or len(category_key) > 80:
        raise CategoryTrendError("category_key_invalid")
    if as_of.tzinfo is None:
        raise CategoryTrendError("as_of_timezone_required")
    if not 1 <= recent_window_days <= 90:
        raise CategoryTrendError("recent_window_days_invalid")
    if not 1 <= baseline_window_days <= 365:
        raise CategoryTrendError("baseline_window_days_invalid")

    snapshot_at = as_of.astimezone(timezone.utc)
    recent_start = snapshot_at - timedelta(days=recent_window_days)
    baseline_start = recent_start - timedelta(days=baseline_window_days)

    deduplicated: dict[tuple[SocialPlatform, str], PublicCreativeObservation] = {}
    for observation in observations:
        if observation.category_key != category_key or observation.platform is not platform:
            continue
        if not observation.discovery_eligible:
            continue
        fetched_at = observation.fetched_at.astimezone(timezone.utc)
        published_at = observation.published_at.astimezone(timezone.utc)
        if fetched_at > snapshot_at or published_at > snapshot_at or published_at < baseline_start:
            continue
        key = (observation.platform, observation.external_content_id)
        current = deduplicated.get(key)
        if current is None or observation.fetched_at > current.fetched_at:
            deduplicated[key] = observation

    recent: list[PublicCreativeObservation] = []
    baseline: list[PublicCreativeObservation] = []
    for observation in deduplicated.values():
        published_at = observation.published_at.astimezone(timezone.utc)
        if published_at >= recent_start:
            recent.append(observation)
        else:
            baseline.append(observation)

    ordering = lambda item: (item.published_at, item.observation_id)
    recent.sort(key=ordering)
    baseline.sort(key=ordering)
    return ObservationWindows(recent=tuple(recent), baseline=tuple(baseline))


def freshness_for(
    observations: Iterable[PublicCreativeObservation],
    *,
    as_of: datetime,
    recent_window_days: int,
) -> tuple[TrendFreshness, float]:
    if as_of.tzinfo is None:
        raise CategoryTrendError("as_of_timezone_required")
    items = tuple(observations)
    if not items:
        return TrendFreshness.STALE, 0.0
    snapshot_at = as_of.astimezone(timezone.utc)
    latest = max(item.fetched_at.astimezone(timezone.utc) for item in items)
    age_seconds = max(0.0, (snapshot_at - latest).total_seconds())
    horizon_seconds = recent_window_days * 86_400
    score = round(max(0.0, 1.0 - age_seconds / horizon_seconds), 6)
    if score >= 0.75:
        freshness = TrendFreshness.FRESH
    elif score >= 0.40:
        freshness = TrendFreshness.CURRENT
    elif score > 0:
        freshness = TrendFreshness.AGING
    else:
        freshness = TrendFreshness.STALE
    return freshness, score


def _signal_index(
    observations: tuple[PublicCreativeObservation, ...],
) -> tuple[
    dict[StructuralSignal, list[PublicCreativeObservation]],
    dict[StructuralFeature, int],
]:
    indexed: dict[StructuralSignal, list[PublicCreativeObservation]] = defaultdict(list)
    feature_totals: dict[StructuralFeature, int] = defaultdict(int)
    for observation in observations:
        for signal in structural_signals(observation.structural_profile):
            indexed[signal].append(observation)
            feature_totals[signal.feature] += 1
    return indexed, feature_totals


def _corroboration(observations: list[PublicCreativeObservation]) -> TrendCorroboration:
    return TrendCorroboration(
        unique_accounts=len({item.account_key for item in observations}),
        unique_sources=len({item.source_locator_hash for item in observations}),
        unique_providers=len({item.provider_key for item in observations}),
    )


def _direction_for(
    *,
    recent_count: int,
    baseline_count: int,
    recent_share: float,
    baseline_share: float,
    corroboration: TrendCorroboration,
) -> TrendDirection:
    delta = recent_share - baseline_share
    corroborated = recent_count >= 2 and corroboration.sufficient_for_positive_direction
    if baseline_count == 0 and recent_count:
        if corroborated and recent_share >= 0.20:
            return TrendDirection.EMERGING
        return TrendDirection.UNCONFIRMED
    if recent_count == 0 and baseline_count:
        return TrendDirection.DECLINING if baseline_count >= 2 else TrendDirection.UNCONFIRMED
    if baseline_share > 0 and delta >= 0.15 and recent_share >= baseline_share * 1.5:
        return TrendDirection.GROWING if corroborated else TrendDirection.UNCONFIRMED
    if baseline_share > 0 and delta <= -0.15 and recent_share <= baseline_share * 0.67:
        return TrendDirection.DECLINING
    return TrendDirection.STABLE


def _confidence_for(
    *,
    direction: TrendDirection,
    recent_count: int,
    baseline_count: int,
    share_delta: float,
    freshness_score: float,
    corroboration: TrendCorroboration,
) -> float:
    sample_score = min(1.0, (recent_count + baseline_count) / 8)
    corroboration_score = min(
        1.0,
        min(corroboration.unique_accounts, corroboration.unique_sources) / 4,
    )
    if direction is TrendDirection.STABLE:
        effect_score = max(0.0, 1.0 - abs(share_delta) / 0.15)
    else:
        effect_score = min(1.0, abs(share_delta) / 0.50)
    confidence = (
        0.30 * sample_score
        + 0.25 * corroboration_score
        + 0.25 * freshness_score
        + 0.20 * effect_score
    )
    if direction is TrendDirection.UNCONFIRMED:
        confidence = min(confidence, 0.49)
    return round(max(0.0, min(1.0, confidence)), 6)


def analyze_category_trends(
    observations: Iterable[PublicCreativeObservation],
    *,
    category_key: str,
    platform: SocialPlatform,
    as_of: datetime,
    recent_window_days: int = 7,
    baseline_window_days: int = 28,
) -> tuple[TrendHypothesis, ...]:
    """Compare structural prevalence in recent and preceding baseline windows.

    A positive direction is never emitted from one account or one source,
    regardless of its views or posting volume.
    """

    windows = build_observation_windows(
        observations,
        category_key=category_key,
        platform=platform,
        as_of=as_of,
        recent_window_days=recent_window_days,
        baseline_window_days=baseline_window_days,
    )
    recent_index, recent_totals = _signal_index(windows.recent)
    baseline_index, baseline_totals = _signal_index(windows.baseline)
    signals = sorted(
        set(recent_index) | set(baseline_index),
        key=lambda item: (item.feature.value, item.value),
    )

    hypotheses: list[TrendHypothesis] = []
    for signal in signals:
        recent_items = recent_index.get(signal, [])
        baseline_items = baseline_index.get(signal, [])
        recent_count = len(recent_items)
        baseline_count = len(baseline_items)
        recent_total = recent_totals.get(signal.feature, 0)
        baseline_total = baseline_totals.get(signal.feature, 0)
        recent_share = recent_count / recent_total if recent_total else 0.0
        baseline_share = baseline_count / baseline_total if baseline_total else 0.0
        share_delta = recent_share - baseline_share
        corroboration = _corroboration(recent_items)
        direction = _direction_for(
            recent_count=recent_count,
            baseline_count=baseline_count,
            recent_share=recent_share,
            baseline_share=baseline_share,
            corroboration=corroboration,
        )
        freshness, freshness_score = freshness_for(
            recent_items or baseline_items,
            as_of=as_of,
            recent_window_days=recent_window_days,
        )
        confidence = _confidence_for(
            direction=direction,
            recent_count=recent_count,
            baseline_count=baseline_count,
            share_delta=share_delta,
            freshness_score=freshness_score,
            corroboration=corroboration,
        )
        if direction in {TrendDirection.EMERGING, TrendDirection.GROWING}:
            reasons = (
                "recent_share_above_baseline",
                "multi_account_corroboration",
                "multi_source_corroboration",
                "structure_only_no_raw_content",
            )
        elif direction is TrendDirection.UNCONFIRMED:
            reasons = (
                "positive_signal_not_corroborated",
                "collect_independent_sources",
                "structure_only_no_raw_content",
            )
        elif direction is TrendDirection.DECLINING:
            reasons = (
                "recent_share_below_baseline",
                "structure_only_no_raw_content",
            )
        else:
            reasons = (
                "recent_share_near_baseline",
                "structure_only_no_raw_content",
            )
        hypotheses.append(
            TrendHypothesis(
                category_key=category_key,
                platform=platform,
                signal=signal,
                direction=direction,
                freshness=freshness,
                freshness_score=freshness_score,
                confidence=confidence,
                corroboration=corroboration,
                recent_count=recent_count,
                baseline_count=baseline_count,
                recent_share=round(recent_share, 6),
                baseline_share=round(baseline_share, 6),
                share_delta=round(share_delta, 6),
                reason_codes=reasons,
            )
        )

    direction_priority = {
        TrendDirection.EMERGING: 0,
        TrendDirection.GROWING: 1,
        TrendDirection.DECLINING: 2,
        TrendDirection.STABLE: 3,
        TrendDirection.UNCONFIRMED: 4,
    }
    hypotheses.sort(
        key=lambda item: (
            direction_priority[item.direction],
            -item.confidence,
            item.signal.feature.value,
            item.signal.value,
        )
    )
    return tuple(hypotheses)
