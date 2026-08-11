from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607250004_independent_quality_learning.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
HANDOFF = (ROOT / "web/app/content-generation-handoff.js").read_text(
    encoding="utf-8"
)
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def test_quality_layer_preserves_performance_as_the_highest_priority() -> None:
    for token in (
        "set schema content_factory_private",
        "rename to creator_generation_learning_policy_exploration_v2",
        ".creator_generation_learning_policy_exploration_v2(p_payload)",
        "if base_policy ->> 'selection_mode' = 'performance' then",
        "return base_policy;",
        "'performance_evidence_has_priority', true",
        "'version', 'generation-learning-v3'",
        "content_factory_private.json_hash(policy_without_hash)",
        "notify pgrst, 'reload schema'",
    ):
        assert token in MIGRATION


def test_quality_evidence_is_generated_independent_and_product_bound() -> None:
    for token in (
        "job.status = 'succeeded'",
        "job.mode = 'real'",
        "media.id::text = job.output ->> 'output_media_id'",
        "media.product_id = job.product_id",
        "'generated_video', 'generated_image'",
        "decision.review_completion_hash = review.completion_hash",
        "decision.media_sha256_snapshot =",
        "decision.decided_by <> job.requested_by",
        "decision.decided_by <> job.assigned_to",
        "signal.product_id = product_id_value",
        "signal.platform = platform_value",
        "signal.model = model_value",
        "limit 100",
        "limit 50",
    ):
        assert token in MIGRATION


def test_quality_policy_requires_competing_repeated_stable_results() -> None:
    for token in (
        "having count(*) >= 3",
        "quality_evidence_count >= 6",
        "quality_angle_count >= 2",
        "preferred_score_value < 0.75",
        "preferred_score_value - coalesce(second_score_value, 1) < 0.12",
        "'approval_weight', 0.50",
        "'review_score_weight', 0.35",
        "'blocker_free_weight', 0.15",
        "'stable_independent_quality_signal'",
    ):
        assert token in MIGRATION


def test_quality_learning_never_reuses_review_copy_or_claims() -> None:
    policy_body = MIGRATION[
        MIGRATION.index("create or replace function public.creator_generation_learning_policy"):
        MIGRATION.rindex("commit;")
    ]
    for forbidden in (
        "decision.comment",
        "review.result -> 'findings'",
        "review.result -> 'recommendations'",
        "review.result -> 'strengths'",
    ):
        assert forbidden not in policy_body
    for token in (
        "'raw_review_copy_never_learned', true",
        "'human_decision_is_independent', true",
        "preferred_hook_patterns",
        "selected_hook_patterns",
    ):
        assert token in policy_body


def test_portal_explains_quality_before_business_performance() -> None:
    for token in (
        '"quality"',
        "Совет ИИ применён по вашему выбору",
        "независимо проверенных вариантов",
        "реальные метрики публикаций получат приоритет",
    ):
        assert token in APP or token in HANDOFF
    assert 'source: "performance_learning"' in APP
    assert '"creator_generation_learning_policy"' in EDGE
    assert "./content-generation-handoff.js?v=20260811.os4.28" in APP
    assert "./app.js?v=20260811.os4.28" in INDEX
