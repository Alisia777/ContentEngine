from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607240006_allow_waived_mock_generation_assignee.sql"
).read_text(encoding="utf-8")
LOWER = MIGRATION.lower()


def test_mock_generation_accepts_a_real_exam_or_an_active_waiver() -> None:
    assert "content_factory_private.training_access_waiver_active(" in LOWER
    assert "or exists (" in LOWER
    assert "module.module_type = 'exam'" in LOWER
    assert "certified_assignee_required" in LOWER


def test_surgical_patch_fails_closed_if_the_installed_guard_changed() -> None:
    for marker in (
        "creator_create_mock_batch_missing",
        "creator_create_mock_batch_exam_guard_changed",
        "creator_create_mock_batch_waiver_guard_already_present",
        "creator_create_mock_batch_waiver_patch_failed",
    ):
        assert marker in LOWER


def test_mock_generation_security_and_spend_guards_are_preserved() -> None:
    assert "security definer" in LOWER
    assert "set search_path = ''" in LOWER
    assert "mock_only_required" in LOWER
    assert "has_function_privilege(" in LOWER
    assert "'authenticated'" in LOWER
