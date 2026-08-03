from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from app.category_intelligence import (
    DEFAULT_STAGE_ORDER,
    CategoryIntelligenceError,
    ContentStage,
    ResearchAction,
    ResearchReadiness,
    StageArtifactVersion,
    StageCorrectionCode,
    StructuralFeature,
    StructuralSignal,
    TrendDirection,
    TrendFreshness,
    analyze_category_trends,
    assess_category_research,
    correct_stage,
    new_stage_revision_graph,
    record_stage_output,
)
from app.competitive_intelligence import (
    CtaStyle,
    HookType,
    Pacing,
    ProofType,
    PublicContentKind,
    PublicCreativeObservation,
    SocialPlatform,
    SourceRelationship,
    StructuralProfile,
)


AS_OF = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
CATEGORY = "hair_styling"
PLATFORM = SocialPlatform.TIKTOK


def profile(
    hook: HookType = HookType.PROBLEM_FIRST,
    *,
    informative: bool = True,
) -> StructuralProfile:
    if not informative:
        return StructuralProfile()
    return StructuralProfile(
        hook_type=hook,
        pacing=Pacing.FAST,
        proof_type=ProofType.VISUAL_DEMO,
        cta_style=CtaStyle.SOFT_ACTION,
        shot_count_bucket="5_8",
        product_visibility="continuous",
    )


def observation(
    observation_id: str,
    *,
    days_ago: int,
    account: str,
    structure: StructuralProfile | None = None,
    provider: str = "licensed-vendor",
) -> PublicCreativeObservation:
    published_at = AS_OF - timedelta(days=days_ago, hours=12)
    if days_ago <= 7:
        fetched_at = AS_OF - timedelta(hours=1)
    else:
        fetched_at = published_at + timedelta(hours=6)
    return PublicCreativeObservation(
        observation_id=observation_id,
        account_key=account,
        external_content_id=observation_id,
        platform=PLATFORM,
        category_key=CATEGORY,
        published_at=published_at,
        fetched_at=fetched_at,
        source_relationship=SourceRelationship.PUBLIC_COMPETITOR,
        content_kind=PublicContentKind.VIDEO,
        source_locator_hash=hashlib.sha256(f"source:{observation_id}".encode()).hexdigest(),
        provider_key=provider,
        structural_profile=structure if structure is not None else profile(),
        views=1_000,
    )


def baseline_and_recent(
    *,
    baseline_hooks: list[HookType],
    recent_hooks: list[HookType],
) -> list[PublicCreativeObservation]:
    items: list[PublicCreativeObservation] = []
    for index, hook in enumerate(baseline_hooks):
        items.append(
            observation(
                f"baseline-{index}",
                days_ago=10 + index,
                account=f"baseline-account-{index % 3}",
                structure=profile(hook),
            )
        )
    for index, hook in enumerate(recent_hooks):
        items.append(
            observation(
                f"recent-{index}",
                days_ago=index % 4,
                account=f"recent-account-{index % 3}",
                structure=profile(hook),
                provider="youtube-data" if index % 2 else "licensed-vendor",
            )
        )
    return items


def find_hook(hypotheses, hook: HookType):
    return next(
        item
        for item in hypotheses
        if item.signal.feature is StructuralFeature.HOOK_TYPE and item.signal.value == hook.value
    )


def test_new_structure_is_emerging_only_with_independent_corroboration() -> None:
    hypotheses = analyze_category_trends(
        baseline_and_recent(
            baseline_hooks=[HookType.PROBLEM_FIRST] * 4,
            recent_hooks=[HookType.DEMONSTRATION] * 3 + [HookType.PROBLEM_FIRST],
        ),
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )

    emerging = find_hook(hypotheses, HookType.DEMONSTRATION)

    assert emerging.direction is TrendDirection.EMERGING
    assert emerging.freshness is TrendFreshness.FRESH
    assert 0 < emerging.confidence <= 1
    assert emerging.corroboration.unique_accounts == 3
    assert emerging.corroboration.unique_sources == 3
    assert emerging.corroboration.sufficient_for_positive_direction
    assert emerging.baseline_count == 0
    assert emerging.recent_count == 3


def test_positive_spike_from_one_account_remains_unconfirmed() -> None:
    observations = [
        observation(
            f"baseline-{index}",
            days_ago=10 + index,
            account=f"baseline-{index}",
            structure=profile(HookType.PROBLEM_FIRST),
        )
        for index in range(4)
    ]
    observations.extend(
        observation(
            f"single-account-{index}",
            days_ago=index,
            account="one-account",
            structure=profile(HookType.CURIOSITY),
        )
        for index in range(3)
    )

    hypothesis = find_hook(
        analyze_category_trends(
            observations,
            category_key=CATEGORY,
            platform=PLATFORM,
            as_of=AS_OF,
        ),
        HookType.CURIOSITY,
    )

    assert hypothesis.direction is TrendDirection.UNCONFIRMED
    assert hypothesis.corroboration.unique_accounts == 1
    assert hypothesis.corroboration.unique_sources == 3
    assert hypothesis.confidence <= 0.49
    assert "collect_independent_sources" in hypothesis.reason_codes


def test_structural_share_growth_is_detected_against_baseline_window() -> None:
    hypotheses = analyze_category_trends(
        baseline_and_recent(
            baseline_hooks=[HookType.RESULT_FIRST] + [HookType.PROBLEM_FIRST] * 5,
            recent_hooks=[HookType.RESULT_FIRST] * 4 + [HookType.PROBLEM_FIRST] * 2,
        ),
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )

    growing = find_hook(hypotheses, HookType.RESULT_FIRST)

    assert growing.direction is TrendDirection.GROWING
    assert growing.recent_share == pytest.approx(4 / 6, abs=1e-6)
    assert growing.baseline_share == pytest.approx(1 / 6, abs=1e-6)
    assert growing.share_delta == pytest.approx(0.5, abs=1e-6)


def test_trend_analysis_is_deterministic_and_input_order_independent() -> None:
    observations = baseline_and_recent(
        baseline_hooks=[HookType.PROBLEM_FIRST] * 4,
        recent_hooks=[HookType.DEMONSTRATION] * 3 + [HookType.PROBLEM_FIRST],
    )

    first = analyze_category_trends(
        observations,
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )
    second = analyze_category_trends(
        reversed(observations),
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )

    assert first == second


def test_empty_research_is_blocked_and_requests_recent_observations() -> None:
    assessment = assess_category_research(
        [],
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )

    assert assessment.coverage.readiness is ResearchReadiness.BLOCKED
    assert assessment.coverage.coverage_score == 0
    assert assessment.next_action.action is ResearchAction.COLLECT_RECENT_OBSERVATIONS
    assert assessment.next_action.target_observation_count == 4


def test_research_requests_independent_sources_before_claiming_readiness() -> None:
    observations = [
        observation(
            f"same-{index}",
            days_ago=index,
            account="same-account",
            structure=profile(HookType.DEMONSTRATION),
        )
        for index in range(4)
    ]

    assessment = assess_category_research(
        observations,
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )

    assert assessment.coverage.readiness is ResearchReadiness.BLOCKED
    assert assessment.next_action.action is ResearchAction.DIVERSIFY_SOURCES


def test_research_requests_structural_tagging_without_raw_content() -> None:
    observations = [
        observation(
            f"recent-unknown-{index}",
            days_ago=index,
            account=f"recent-account-{index % 2}",
            structure=profile(informative=False),
        )
        for index in range(4)
    ]
    observations.extend(
        observation(
            f"baseline-unknown-{index}",
            days_ago=10 + index,
            account=f"baseline-account-{index % 2}",
            structure=profile(informative=False),
        )
        for index in range(4)
    )

    assessment = assess_category_research(
        observations,
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )

    assert assessment.coverage.readiness is ResearchReadiness.PARTIAL
    assert assessment.coverage.informative_observations == 0
    assert assessment.next_action.action is ResearchAction.COMPLETE_STRUCTURAL_TAGGING
    assert "raw_content_not_required" in assessment.next_action.reason_codes


def test_ready_category_proactively_routes_trends_to_human_review() -> None:
    assessment = assess_category_research(
        baseline_and_recent(
            baseline_hooks=[HookType.PROBLEM_FIRST] * 4,
            recent_hooks=[HookType.DEMONSTRATION] * 3 + [HookType.PROBLEM_FIRST],
        ),
        category_key=CATEGORY,
        platform=PLATFORM,
        as_of=AS_OF,
    )

    assert assessment.coverage.readiness is ResearchReadiness.READY
    assert assessment.coverage.coverage_score > 0.8
    assert assessment.next_action.action is ResearchAction.REVIEW_CORROBORATED_TRENDS
    assert "trend_is_hypothesis_not_winner" in assessment.next_action.reason_codes


def full_stage_graph():
    graph = new_stage_revision_graph()
    for stage in DEFAULT_STAGE_ORDER:
        graph = record_stage_output(graph, stage=stage, structural_profile=profile())
    return graph


@pytest.mark.parametrize("stage", DEFAULT_STAGE_ORDER)
def test_correcting_any_stage_appends_version_and_stales_only_downstream(stage: ContentStage) -> None:
    original = full_stage_graph()
    revised = correct_stage(
        original,
        stage=stage,
        correction_codes=(StageCorrectionCode.STRUCTURE_RESELECTED,),
        structural_profile=profile(HookType.RESULT_FIRST),
    )
    changed_index = DEFAULT_STAGE_ORDER.index(stage)

    assert len(revised.versions) == len(original.versions) + 1
    assert original.state_for(stage).current_version_id != revised.state_for(stage).current_version_id
    assert not revised.state_for(stage).stale
    for index, candidate in enumerate(DEFAULT_STAGE_ORDER):
        if index > changed_index:
            assert revised.state_for(candidate).stale
            assert revised.state_for(candidate).stale_due_to_version_id == revised.state_for(stage).current_version_id
        else:
            assert not revised.state_for(candidate).stale


def test_stage_revision_preserves_old_versions_and_parent_lineage() -> None:
    original = full_stage_graph()
    old_research = original.current_version_for(ContentStage.CATEGORY_RESEARCH)
    original_versions = original.versions

    revised = correct_stage(
        original,
        stage=ContentStage.CATEGORY_RESEARCH,
        correction_codes=(StageCorrectionCode.SOURCE_COVERAGE_UPDATED,),
        structural_profile=profile(HookType.DEMONSTRATION),
    )
    new_research = revised.current_version_for(ContentStage.CATEGORY_RESEARCH)

    assert old_research is not None and new_research is not None
    assert original.versions == original_versions
    assert revised.versions[: len(original_versions)] == original_versions
    assert revised.versions[DEFAULT_STAGE_ORDER.index(ContentStage.CATEGORY_RESEARCH)] is old_research
    assert new_research.parent_version_id == old_research.version_id
    assert new_research.revision_number == 2
    assert original.state_for(ContentStage.CREATIVE_BRIEF).stale is False
    assert revised.state_for(ContentStage.CREATIVE_BRIEF).stale is True


def test_same_stage_correction_from_same_snapshot_is_deterministic() -> None:
    original = full_stage_graph()
    kwargs = {
        "stage": ContentStage.SCRIPT,
        "correction_codes": (StageCorrectionCode.SCRIPT_STRUCTURE_UPDATED,),
        "structural_profile": profile(HookType.COMPARISON),
    }

    assert correct_stage(original, **kwargs) == correct_stage(original, **kwargs)


def test_learning_contract_has_no_raw_caption_or_url_fields() -> None:
    version_fields = {item.name for item in fields(StageArtifactVersion)}

    assert "caption" not in version_fields
    assert "url" not in version_fields
    with pytest.raises(ValueError, match="structural_signal_value_invalid"):
        StructuralSignal(
            feature=StructuralFeature.HOOK_TYPE,
            value="paste-the-caption-here",
        )

    graph = record_stage_output(
        new_stage_revision_graph(),
        stage=ContentStage.SOURCE_DISCOVERY,
        structural_profile=profile(),
    )
    with pytest.raises(CategoryIntelligenceError, match="correction_codes_invalid"):
        correct_stage(
            graph,
            stage=ContentStage.SOURCE_DISCOVERY,
            correction_codes=("raw_feedback",),  # type: ignore[arg-type]
        )
