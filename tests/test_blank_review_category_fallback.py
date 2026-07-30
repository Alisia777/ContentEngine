from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607300004_blank_review_category_fallback.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.lower()


def test_blank_review_category_fallback_is_parseable() -> None:
    assert parse_sql(MIGRATION)


def test_empty_review_category_falls_back_to_exact_product_category() -> None:
    resolver = LOWER.split(
        "content_factory_private.resolved_content_review_category(", 1
    )[1].split("revoke all", 1)[0]
    assert "nullif(btrim(coalesce($1 ->> 'content_review_category', '')), '')" in resolver
    assert "nullif(btrim(coalesce($1 ->> 'product_category', '')), '')" in resolver


def test_all_live_generation_and_review_boundaries_use_shared_resolver() -> None:
    for signature in (
        "creator_start_content_review_legacy(jsonb)",
        "creator_start_generated_video_review(jsonb)",
        "creator_approve_generated_video_review_with_context(jsonb)",
        "enforce_generated_image_review_input()",
        "guard_video_review_content_approval()",
        "creator_approve_generated_photo_review_with_context(jsonb)",
        "creator_start_real_generation_pre_guard_lineage_v8(jsonb)",
    ):
        assert signature in LOWER
    for guard in (
        "blank_review_category_fallback_pattern_changed",
        "blank_review_category_fallback_contract_invalid",
    ):
        assert guard in LOWER
