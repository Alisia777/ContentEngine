from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240003_repair_training_waiver_membership_gate.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()


def test_repair_is_transactional_and_follows_the_waiver_migration() -> None:
    assert MIGRATION.exists()
    assert (
        ROOT
        / "supabase/migrations/202607240002_training_access_waivers.sql"
    ).exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")


def test_renamed_pre_waiver_gate_uses_stable_positional_arguments() -> None:
    assert (
        "create or replace function\n"
        "  content_factory_private.membership_role_pre_training_waiver("
    ) in LOWER
    assert "#variable_conflict use_variable" in LOWER
    assert "target_organization_id uuid := $1" in LOWER
    assert "certification_required boolean := $2" in LOWER
    assert "role_allowlist text[] := $3" in LOWER
    assert "pg_catalog.to_regprocedure(" in LOWER
    assert "membership_role_pre_practical_gate(" in LOWER
    assert "training_practical_gate_satisfied(" in LOWER
    assert "practical_gate_dependency_incomplete" in LOWER
    assert "where membership.organization_id = target_organization_id" in LOWER
    assert "where certification.organization_id = target_organization_id" in LOWER
    assert "final_exam_required" in LOWER
    assert "refreshed_courses_required" in LOWER
    assert "membership_role.organization_id" not in LOWER.split(
        "do $training_waiver_membership_gate_repair_contract$", 1
    )[0]


def test_repair_preserves_private_boundary_and_checks_installed_wrapper() -> None:
    assert (
        "revoke all on function\n"
        "  content_factory_private.membership_role_pre_training_waiver(\n"
        "    uuid, boolean, text[]\n"
        "  )\n"
        "  from public, anon, authenticated"
    ) in LOWER
    assert "pg_get_functiondef(" in LOWER
    assert "membership_role_pre_training_waiver(" in LOWER
    assert "training_access_waiver_active(" in LOWER
    assert "private_pre_training_waiver_gate_is_browser_callable" in LOWER
