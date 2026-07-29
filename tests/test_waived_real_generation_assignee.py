from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607290007_allow_waived_real_generation_assignee.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.lower()


def test_real_generation_waiver_patch_is_parseable() -> None:
    assert parse_sql(MIGRATION)


def test_both_real_video_generators_accept_exam_or_active_waiver() -> None:
    for token in (
        "creator_start_gen4_turbo_5s(jsonb)",
        "creator_start_seedance2_fast_8s(jsonb)",
        "content_factory_private.training_access_waiver_active(",
        "or exists (",
        "certification.module_code = 'operator_final_exam'",
        "certified_assignee_required",
    ):
        assert token in LOWER


def test_patch_preserves_paid_security_and_role_guards() -> None:
    for token in (
        "real_generation_spend_confirmation_required",
        "payout_role_not_allowed",
        "real_generation_assignee_exam_guard_changed",
        "real_generation_assignee_waiver_patch_failed",
        "real_generation_assignee_waiver_contract_invalid",
    ):
        assert token in LOWER
