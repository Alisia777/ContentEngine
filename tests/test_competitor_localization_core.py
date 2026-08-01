from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app.competitive_intelligence import (
    CreativeAction,
    CtaStyle,
    DiscoveryProvider,
    HookType,
    Pacing,
    ProofType,
    PublicContentKind,
    PublicCreativeObservation,
    SocialPlatform,
    SourceRelationship,
    StructuralProfile,
    build_competitor_action_plan,
    rank_public_creatives,
    select_discovery_provider,
)
from app.video_localization import (
    LocalizationMode,
    LocalizationPlanError,
    LocalizationProvider,
    VideoSource,
    build_localization_batch,
    microusd_to_usd,
)
from scripts.plan_harly_localization_batch import (
    InputContractError,
    _read_payload,
    plan_from_payload,
)


NOW = datetime(2026, 8, 1, 12, tzinfo=timezone.utc)
HASH = "a" * 64


def observation(
    observation_id: str,
    *,
    relationship: SourceRelationship = SourceRelationship.PUBLIC_COMPETITOR,
    rights: bool = False,
    views: int = 10_000,
    likes: int = 500,
    comments: int = 30,
    shares: int = 20,
    age_hours: int = 24,
    profile: StructuralProfile | None = None,
) -> PublicCreativeObservation:
    return PublicCreativeObservation(
        observation_id=observation_id,
        account_key=f"account-{observation_id}",
        external_content_id=f"content-{observation_id}",
        platform=SocialPlatform.TIKTOK,
        category_key="hair_styling",
        published_at=NOW - timedelta(hours=age_hours),
        fetched_at=NOW,
        source_relationship=relationship,
        content_kind=PublicContentKind.VIDEO,
        source_locator_hash=HASH,
        provider_key="licensed-public-data-vendor",
        structural_profile=profile
        or StructuralProfile(
            hook_type=HookType.PROBLEM_FIRST,
            pacing=Pacing.FAST,
            proof_type=ProofType.VISUAL_DEMO,
            cta_style=CtaStyle.SOFT_ACTION,
            shot_count_bucket="5_8",
            product_visibility="continuous",
        ),
        duration_seconds=12,
        follower_count=50_000,
        views=views,
        likes=likes,
        comments=comments,
        shares=shares,
        rights_confirmed=rights,
    )


def source(
    index: int,
    *,
    relationship: SourceRelationship = SourceRelationship.OWNED,
    rights: bool = True,
    qa: bool = True,
    speech: bool = True,
    on_screen_text: bool = False,
    duration: int = 8,
) -> VideoSource:
    return VideoSource(
        source_id=f"harly-{index}",
        sku="HARLY-1",
        category_key="hair_styling",
        duration_seconds=duration,
        source_language="ru",
        source_relationship=relationship,
        rights_confirmed=rights,
        qa_approved=qa,
        asset_sha256=f"{index:064x}"[-64:],
        speech_present=speech,
        on_screen_text_present=on_screen_text,
    )


def test_public_competitor_is_structural_remake_not_exact_copy() -> None:
    plan = build_competitor_action_plan(
        [observation("competitor")],
        category_key="hair_styling",
        platform=SocialPlatform.TIKTOK,
    )

    assert plan.candidates[0].action is CreativeAction.RECREATE_STRUCTURE
    assert "structure_may_be_adapted_not_copied" in plan.candidates[0].reason_codes
    assert "views_are_not_business_outcomes" in plan.candidates[0].reason_codes


def test_owned_source_with_rights_routes_to_localization() -> None:
    candidate = rank_public_creatives(
        [
            observation(
                "owned",
                relationship=SourceRelationship.OWNED,
                rights=True,
            )
        ],
        category_key="hair_styling",
        platform=SocialPlatform.TIKTOK,
    )[0]

    assert candidate.action is CreativeAction.LOCALIZE_OWNED


def test_public_video_without_safe_structure_is_not_used() -> None:
    candidate = rank_public_creatives(
        [observation("unknown", profile=StructuralProfile())],
        category_key="hair_styling",
        platform=SocialPlatform.TIKTOK,
    )[0]

    assert candidate.action is CreativeAction.DO_NOT_USE


def test_discovery_score_uses_velocity_for_review_but_never_claims_sales_winner() -> None:
    fast = observation("fast", views=20_000, age_hours=6, shares=200)
    slow = observation("slow", views=20_000, age_hours=72, shares=5)
    candidates = rank_public_creatives(
        [slow, fast],
        category_key="hair_styling",
        platform=SocialPlatform.TIKTOK,
    )

    assert candidates[0].observation_id == "fast"
    assert all("discovery_signals_only" in item.reason_codes for item in candidates)
    assert all("views_are_not_business_outcomes" in item.reason_codes for item in candidates)


def test_provider_selection_keeps_tiktok_product_boundary() -> None:
    owner = select_discovery_provider(
        platform=SocialPlatform.TIKTOK,
        arbitrary_public_accounts=False,
        subject_authorized=True,
    )
    competitor = select_discovery_provider(
        platform=SocialPlatform.TIKTOK,
        arbitrary_public_accounts=True,
        commercial_product_use=True,
    )
    research = select_discovery_provider(
        platform=SocialPlatform.TIKTOK,
        arbitrary_public_accounts=True,
        commercial_product_use=False,
        research_approved=True,
    )

    assert owner.provider is DiscoveryProvider.TIKTOK_DISPLAY_API
    assert competitor.provider is DiscoveryProvider.LICENSED_PUBLIC_DATA_VENDOR
    assert research.provider is DiscoveryProvider.TIKTOK_RESEARCH_API
    assert not research.commercial_product_use


def test_youtube_uses_official_public_metadata_api() -> None:
    provider = select_discovery_provider(
        platform=SocialPlatform.YOUTUBE,
        arbitrary_public_accounts=True,
    )
    assert provider.provider is DiscoveryProvider.YOUTUBE_DATA_API


def test_harly_five_sources_times_two_modes_builds_exactly_ten() -> None:
    plan = build_localization_batch(
        [source(index) for index in range(1, 6)],
        target_languages=["en"],
        modes=[LocalizationMode.SUBTITLES, LocalizationMode.DUB_AUDIO],
        target_count=10,
    )

    assert len(plan.assignments) == 10
    assert {item.wave for item in plan.assignments[:2]} == {1}
    assert {item.wave for item in plan.assignments[2:]} == {2}
    assert plan.qa_gate_after_sequence == 2
    assert sum(item.mode is LocalizationMode.SUBTITLES for item in plan.assignments) == 5
    assert sum(item.mode is LocalizationMode.DUB_AUDIO for item in plan.assignments) == 5
    assert len({item.assignment_id for item in plan.assignments}) == 10
    assert plan.total_estimated_cost_microusd == 366_670
    assert plan.full_generation_baseline_microusd == 23_200_000
    assert microusd_to_usd(plan.total_estimated_cost_microusd) == "0.3667"
    assert plan.estimated_savings_ratio > 0.98


def test_harly_plan_is_deterministic() -> None:
    sources = [source(index) for index in range(1, 6)]
    first = build_localization_batch(
        sources,
        target_languages=["en"],
        target_count=10,
    )
    second = build_localization_batch(
        sources,
        target_languages=["en"],
        target_count=10,
    )

    assert first.plan_id == second.plan_id
    assert first.assignments == second.assignments


def test_competitor_video_cannot_enter_exact_localization_batch() -> None:
    with pytest.raises(LocalizationPlanError, match="source_not_owned"):
        build_localization_batch(
            [source(1, relationship=SourceRelationship.PUBLIC_COMPETITOR)],
            target_languages=["en", "de"],
            target_count=2,
        )


def test_dubbing_is_skipped_when_source_has_no_speech() -> None:
    with pytest.raises(LocalizationPlanError, match="speech_modes_unavailable"):
        build_localization_batch(
            [source(1, speech=False)],
            target_languages=["en"],
            modes=[LocalizationMode.SUBTITLES, LocalizationMode.DUB_AUDIO],
            target_count=2,
        )


def test_on_screen_text_requires_manual_edit() -> None:
    plan = build_localization_batch(
        [source(1, on_screen_text=True)],
        target_languages=["en"],
        modes=[LocalizationMode.SUBTITLES],
        target_count=1,
        qa_gate_after_sequence=1,
    )

    assert plan.assignments[0].requires_manual_text_edit
    assert "on_screen_text_requires_manual_edit" in plan.assignments[0].reason_codes


def test_heygen_lipsync_is_explicit_premium_override() -> None:
    plan = build_localization_batch(
        [source(1)],
        target_languages=["en"],
        modes=[LocalizationMode.LIP_SYNC],
        target_count=1,
        qa_gate_after_sequence=1,
        provider_overrides={
            LocalizationMode.LIP_SYNC: LocalizationProvider.HEYGEN_LIPSYNC_PRECISION,
        },
    )

    assert plan.assignments[0].provider is LocalizationProvider.HEYGEN_LIPSYNC_PRECISION
    assert plan.assignments[0].estimated_cost_microusd == 533_600


def test_cli_payload_rejects_raw_urls_and_captions(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"sources": [], "source_url": "https://example.test"}),
        encoding="utf-8",
    )

    with pytest.raises(InputContractError, match="forbidden_key"):
        _read_payload(path)


def test_cli_dry_run_returns_costs_without_provider_call() -> None:
    payload = {
        "target_count": 2,
        "qa_gate_after_sequence": 1,
        "target_languages": ["en"],
        "modes": ["subtitles", "dub_audio"],
        "sources": [
            {
                "source_id": "harly-1",
                "sku": "HARLY-1",
                "category_key": "hair_styling",
                "duration_seconds": 8,
                "source_language": "ru",
                "source_relationship": "owned",
                "rights_confirmed": True,
                "qa_approved": True,
                "asset_sha256": "1" * 64,
                "speech_present": True,
                "on_screen_text_present": False,
            }
        ],
    }

    result = plan_from_payload(payload)

    assert result["dry_run"] is True
    assert result["provider_calls_started"] is False
    assert result["target_count"] == 2
    assert result["total_estimated_cost_usd"] == "0.0733"
