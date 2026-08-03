from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608030005_selected_training_waiver_roles.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()


def _function(name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{re.escape(name)}"
        r"\s*\(.*?\)\s*returns\s+jsonb(?P<header>.*?)"
        r"as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, name
    return match.group("header").casefold(), match.group("body").casefold()


def test_selected_role_extension_is_new_transactional_migration() -> None:
    assert MIGRATION.exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")
    assert "202607240002_training_access_waivers.sql" not in MIGRATION.name


def test_role_transition_preserves_owner_and_remembers_viewer() -> None:
    assert "previous_role in ('viewer', 'trainee', 'operator', 'owner')" in LOWER
    assert "granted_role in ('operator', 'owner')" in LOWER
    assert "granted_role = 'owner'" in LOWER
    assert "previous_role = 'owner'" in LOWER
    assert "granted_role = 'operator'" in LOWER
    assert "previous_role in ('viewer', 'trainee', 'operator')" in LOWER


def test_final_bootstrap_accepts_only_operator_or_preserved_owner_waivers() -> None:
    header, bootstrap = _function("creator_bootstrap")
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "creator_bootstrap_pre_training_waiver" in bootstrap
    assert "not in ('learning', 'workspace')" in bootstrap
    assert "actor_role not in ('operator', 'owner')" in bootstrap
    assert "training_access_waiver_active(" in bootstrap
    assert "'{state}', '\"workspace\"'::jsonb" in bootstrap
    assert "'{workspace_open}', 'true'::jsonb" in bootstrap
    assert "'access_waiver'" in bootstrap
    assert "training_certifications" not in bootstrap
    assert "training_attempts" not in bootstrap


def test_batch_grant_is_exact_atomic_audited_and_role_safe() -> None:
    header, batch = _function("system_grant_training_access_waiver_batch")
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "jsonb_array_length(targets_value) <> 3" in batch
    assert "pg_advisory_xact_lock" in batch
    assert "content_factory_private.begin_command" in batch
    assert "content_factory_private.finish_command" in batch
    assert "membership.role in ('owner', 'admin')" in batch
    assert "membership_row.role in ('viewer', 'trainee', 'operator')" in batch
    assert "when membership_row.role = 'owner'" in batch
    assert "update content_factory.memberships" in batch
    assert "insert into content_factory.training_access_waivers" in batch
    assert "training_access_waiver_granted" in batch
    assert "membership_role_changed_for_training_waiver" in batch
    for fabricated_state in (
        "training_certifications",
        "training_attempts",
        "training_practical_projects",
    ):
        assert fabricated_state not in batch


def test_batch_grant_is_service_role_only() -> None:
    assert (
        "revoke all on function\n"
        "  public.system_grant_training_access_waiver_batch(jsonb)\n"
        "  from public, anon, authenticated"
    ) in LOWER
    assert (
        "grant execute on function\n"
        "  public.system_grant_training_access_waiver_batch(jsonb)\n"
        "  to service_role"
    ) in LOWER
