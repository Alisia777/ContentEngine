from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607300003_allow_waived_content_review_operator.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.lower()


def test_content_review_operator_waiver_patch_is_parseable() -> None:
    assert parse_sql(MIGRATION)


def test_content_review_accepts_active_waiver_or_valid_exam() -> None:
    for token in (
        "creator_start_content_review_legacy(jsonb)",
        "content_factory_private.training_access_waiver_active(",
        "certification.module_code = ''operator_final_exam''",
        "content_review_certification_required",
    ):
        assert token in LOWER


def test_patch_preserves_durable_and_repair_wrappers() -> None:
    for token in (
        "creator_start_content_review_pre_repair_lineage_v1(jsonb)",
        "creator_start_content_review_legacy",
        "creator_start_content_review_pre_repair_lineage_v1",
        "content_review_operator_exam_guard_changed",
        "content_review_operator_waiver_patch_failed",
        "content_review_operator_waiver_contract_invalid",
    ):
        assert token in LOWER
