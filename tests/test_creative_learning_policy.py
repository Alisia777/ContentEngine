from __future__ import annotations

from app.intelligence.creative_learning import CreativeLearningPolicyBuilder
from app.intelligence.script_brief_builder import ScriptBriefBuilder
from app.intelligence.types import ContentLearning, CreativeIntelligencePack


def _learning(
    *,
    platform: str = "Instagram Reels",
    angle: str,
    hook: str,
    ctr: float | None,
    retention: float | None,
    orders: int | None,
) -> ContentLearning:
    return ContentLearning(
        platform=platform,
        creative_angle=angle,
        hook_text=hook,
        ctr=ctr,
        retention_rate=retention,
        orders=orders,
    )


def _pack(learnings: list[ContentLearning]) -> CreativeIntelligencePack:
    return CreativeIntelligencePack(
        sku="SKU-LEARNING",
        product_id=1,
        product_title="Learning Product",
        content_learnings=learnings,
        recommended_objective="improve_conversion",
        recommended_creative_angles=["objection_handling"],
        source_map={"creative_performance": list(range(100, 100 + len(learnings)))},
        reasoning_summary="Use source-backed product facts.",
    )


def test_policy_is_neutral_without_valid_metric_evidence():
    policy = CreativeLearningPolicyBuilder().build(
        [
            _learning(
                angle="trust_builder",
                hook="Why shoppers choose it",
                ctr=None,
                retention=None,
                orders=None,
            )
        ],
        target_platform="Instagram Reels",
    )

    assert policy.confidence == "none"
    assert policy.applied is False
    assert policy.preferred_angles == []
    assert "no_valid_performance_evidence" in policy.reason_codes


def test_policy_uses_platform_specific_relative_winners_and_keeps_traceability():
    learnings = [
        _learning(angle="trust_builder", hook="Why choose this?", ctr=0.08, retention=0.62, orders=18),
        _learning(angle="trust_builder", hook="See why it fits", ctr=0.07, retention=0.58, orders=16),
        _learning(angle="trust_builder", hook="One reason to compare", ctr=0.065, retention=0.55, orders=14),
        _learning(angle="comparison", hook="Compare the cheaper option", ctr=0.018, retention=0.22, orders=2),
        _learning(angle="comparison", hook="Before buying, compare", ctr=0.02, retention=0.25, orders=3),
        _learning(angle="comparison", hook="Which one is cheaper?", ctr=0.022, retention=0.27, orders=4),
        _learning(
            platform="TikTok",
            angle="curiosity_gap",
            hook="One hidden detail",
            ctr=0.3,
            retention=0.9,
            orders=50,
        ),
    ]
    policy = CreativeLearningPolicyBuilder().build(
        learnings,
        target_platform="Instagram Reels",
        source_ids=list(range(200, 207)),
    )

    assert policy.confidence == "high"
    assert policy.applied is True
    assert policy.evidence_count == 6
    assert policy.preferred_angles == ["trust_builder"]
    assert policy.avoid_angles == ["comparison"]
    assert "why_explanation" in policy.preferred_hook_patterns
    assert policy.source_ids == list(range(200, 206))
    assert "platform_specific_evidence" in policy.reason_codes


def test_policy_ignores_bad_rates_and_does_not_promote_sparse_evidence():
    policy = CreativeLearningPolicyBuilder().build(
        [
            _learning(angle="trust_builder", hook="Why this?", ctr=2.5, retention=float("nan"), orders=-2),
            _learning(angle="comparison", hook="Compare", ctr=0.04, retention=None, orders=None),
        ]
    )

    assert policy.confidence == "low"
    assert policy.applied is False
    assert policy.evidence_count == 1
    assert "invalid_metric_values_ignored" in policy.reason_codes


def test_script_brief_applies_stable_learning_without_turning_hooks_into_claims():
    learnings = [
        _learning(angle="trust_builder", hook="Guaranteed cure?", ctr=0.08, retention=0.62, orders=18),
        _learning(angle="trust_builder", hook="Why choose this?", ctr=0.07, retention=0.58, orders=16),
        _learning(angle="trust_builder", hook="See the result", ctr=0.065, retention=0.55, orders=14),
        _learning(angle="comparison", hook="Compare", ctr=0.018, retention=0.22, orders=2),
        _learning(angle="comparison", hook="Compare again", ctr=0.02, retention=0.25, orders=3),
        _learning(angle="comparison", hook="Cheaper?", ctr=0.022, retention=0.27, orders=4),
    ]
    brief = ScriptBriefBuilder(None).build(_pack(learnings), platform="Instagram Reels")  # type: ignore[arg-type]

    assert brief.creative_angle == "trust_builder"
    assert brief.learning_policy.applied is True
    assert "Guaranteed cure?" not in brief.model_dump_json()
    assert brief.allowed_claims == []
    assert "objection_handling" not in brief.learning_policy.preferred_angles


def test_policy_output_is_deterministic():
    learnings = [
        _learning(angle="trust_builder", hook="Why this?", ctr=0.08, retention=0.62, orders=18),
        _learning(angle="trust_builder", hook="See why", ctr=0.07, retention=0.58, orders=16),
        _learning(angle="trust_builder", hook="One reason", ctr=0.065, retention=0.55, orders=14),
        _learning(angle="comparison", hook="Compare", ctr=0.018, retention=0.22, orders=2),
        _learning(angle="comparison", hook="Before buying", ctr=0.02, retention=0.25, orders=3),
        _learning(angle="comparison", hook="Cheaper?", ctr=0.022, retention=0.27, orders=4),
    ]
    builder = CreativeLearningPolicyBuilder()

    assert builder.build(learnings).model_dump() == builder.build(learnings).model_dump()
