from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607300005_bind_waived_generated_review_category.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.lower()


def test_waived_generated_review_category_is_parseable() -> None:
    assert parse_sql(MIGRATION)


def test_binding_requires_exact_paid_job_category_and_active_waiver() -> None:
    for token in (
        "generated_media_value",
        "actor_role = 'operator'",
        "content_factory_private.training_access_waiver_active(",
        "generation_job_row.input ->> 'product_category'",
        "p_payload ->> 'product_category'",
        "product_category_value = lower(btrim(coalesce(",
    ):
        assert token in LOWER


def test_binding_is_persisted_and_audited_without_removing_safe_failure() -> None:
    for token in (
        "content_review_category_confirmation_basis",
        "audited_training_waiver_generation_job",
        "content_review_category_generation_job_id",
        "content_review_category_bound_from_generation",
        "content_review_product_category_unverified",
        "waived_generated_review_category_contract_invalid",
    ):
        assert token in LOWER
