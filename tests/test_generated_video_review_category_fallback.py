from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608170002_generated_video_review_category_fallback.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.lower()


def test_generated_video_review_category_fallback_is_parseable() -> None:
    assert parse_sql(MIGRATION)


def test_patch_targets_the_installed_review_start_stage() -> None:
    assert (
        "content_factory_private."
        "creator_start_generated_video_review_pre_project_v47(jsonb)"
        in MIGRATION
    )
    assert (
        "category_value := content_factory_private."
        "resolved_content_review_category(product_row.metadata);"
        in MIGRATION
    )


def test_fallback_binds_only_the_immutable_allowlisted_job_input_category() -> None:
    assert "job_row.input ->> 'product_category'" in MIGRATION
    assert "'paid_generation_job_input'" in MIGRATION
    assert "'content_review_category_generation_job_id', job_row.id" in MIGRATION
    assert "'ru-content-compliance-2026-07-16.1'" in MIGRATION
    for allowlist_line in (
        "'cosmetics', 'baa', 'sports_food', 'food', 'household'",
        "'apparel', 'electronics', 'other'",
    ):
        assert allowlist_line in MIGRATION
    assert "content_review_category_bound_from_generation" in MIGRATION
    assert "'generation-input-review-category:' || job_row.id::text" in MIGRATION


def test_guard_and_verify_markers_hard_fail_on_drift() -> None:
    for marker in (
        "generated_video_review_category_fallback_pattern_changed",
        "generated_video_review_category_fallback_patch_failed",
        "generated_video_review_category_fallback_contract_invalid",
    ):
        assert marker in LOWER
    assert "generated_video_review_category_required" in LOWER
    assert "creator_approve_generated_video_review_pre_sound_gate_v1" in LOWER
    assert "resolved_content_review_category" in LOWER
    assert "notify pgrst, 'reload schema';" in LOWER
