from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607240002_training_access_waivers.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _function(schema: str, name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(schema)}\."
        rf"{re.escape(name)}\s*\(.*?\)\s*returns\s+\w+"
        rf"(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"{schema}.{name}"
    return match.group("header").casefold(), match.group("body").casefold()


def test_waiver_migration_is_transactional_and_follows_gate_repair() -> None:
    assert MIGRATION.exists()
    assert (
        ROOT
        / "supabase/migrations/202607240001_repair_practical_membership_gate.sql"
    ).exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")


def test_waiver_migration_can_resume_after_legacy_partial_application() -> None:
    for preserved_function in (
        "content_factory_private.membership_role_pre_training_waiver"
        "(uuid,boolean,text[])",
        "content_factory.storage_access_allowed_pre_training_waiver"
        "(text,text,boolean)",
        "content_factory_private.creator_bootstrap_pre_training_waiver(jsonb)",
    ):
        assert re.search(
            rf"if\s+to_regprocedure\(\s*'{re.escape(preserved_function)}'\s*\)"
            r"\s+is\s+null\s+then",
            LOWER,
        )


def test_waiver_is_explicit_audited_reversible_and_not_a_certificate() -> None:
    table = LOWER.split(
        "create table if not exists content_factory.training_access_waivers", 1
    )[1].split("create index", 1)[0]

    for field in (
        "scope",
        "status",
        "previous_role",
        "granted_role",
        "grant_reason",
        "granted_by",
        "granted_at",
        "revoked_by",
        "revoked_at",
        "revocation_reason",
    ):
        assert field in table
    assert "scope = 'workspace_generation'" in table
    assert "status in ('active', 'revoked')" in table
    assert "training_access_waivers_org_profile_uq" in LOWER
    assert "on content_factory.training_access_waivers (" in LOWER
    assert "enable row level security" in LOWER
    assert (
        "revoke all on content_factory.training_access_waivers\n"
        "  from public, anon, authenticated"
    ) in LOWER

    _, system = _function("public", "system_set_training_access_waiver")
    assert "insert into content_factory.training_access_waivers" in system
    assert "update content_factory.training_access_waivers" in system
    assert "on conflict (organization_id, profile_id)" not in system
    assert "update content_factory.memberships" in system
    assert "'trainee', 'operator'" in system
    assert "training_access_waiver_granted" in system
    assert "training_access_waiver_revoked" in system
    for fabricated_state in (
        "insert into content_factory.training_attempts",
        "insert into content_factory.training_certifications",
        "insert into content_factory.training_practical_projects",
    ):
        assert fabricated_state not in system


def test_only_service_role_can_change_waivers() -> None:
    assert (
        "revoke all on function public.system_set_training_access_waiver(jsonb)\n"
        "  from public, anon, authenticated"
    ) in LOWER
    assert (
        "grant execute on function public.system_set_training_access_waiver(jsonb)\n"
        "  to service_role"
    ) in LOWER

    header, body = _function("public", "system_set_training_access_waiver")
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "membership.role in ('owner', 'admin')" in body
    assert "pg_advisory_xact_lock" in body
    assert "content_factory_private.begin_command" in body
    assert "content_factory_private.finish_command" in body


def test_shared_membership_and_storage_gates_accept_only_active_waiver() -> None:
    _, membership = _function("content_factory_private", "membership_role")
    _, storage = _function("content_factory", "storage_access_allowed")

    assert "training_access_waiver_active(" in membership
    assert "certification_required and not waiver_active" in membership
    assert "allowed_roles" in SQL
    assert "membership_role_pre_training_waiver(" in membership

    assert "training_access_waiver_active(" in storage
    assert "storage_access_allowed_pre_training_waiver(" in storage
    assert "'owner', 'admin', 'producer', 'reviewer', 'operator'" in storage
    assert "p_owner_id = auth.uid()::text" in storage
    assert "drop policy if exists contentengine_private_select" in LOWER
    assert "drop policy if exists contentengine_private_insert" in LOWER
    assert "drop policy if exists contentengine_private_delete" in LOWER


def test_bootstrap_projects_waiver_without_overriding_locked_states() -> None:
    _, bootstrap = _function("public", "creator_bootstrap")

    assert "creator_bootstrap_pre_training_waiver" in bootstrap
    assert "not in ('learning', 'workspace')" in bootstrap
    assert "actor_role <> 'operator'" in bootstrap
    assert "'access_waiver'" in bootstrap
    assert "'workspace_generation'" in bootstrap
    assert "'{state}', '\"workspace\"'::jsonb" in bootstrap
    assert "'{workspace_open}', 'true'::jsonb" in bootstrap
    assert "password_change_required" not in bootstrap
    assert "training_certifications" not in bootstrap
    assert "training_attempts" not in bootstrap


def test_browser_trusts_explicit_waiver_instead_of_fake_completion() -> None:
    assert "const accessWaiverSource =" in APP
    assert 'String(accessWaiverSource.scope || "") === "workspace_generation"' in APP
    assert "function trainingAccessWaiverActive()" in APP
    workspace_gate = APP[
        APP.index("function hasWorkspaceAccess()") :
        APP.index("function prerequisitesComplete()")
    ]
    assert "if (trainingAccessWaiverActive()) return true;" in workspace_gate
    assert workspace_gate.index("trainingAccessWaiverActive()") < workspace_gate.index(
        "trainingCatalogReady()"
    )
    assert "exam.passed = true" not in APP
    assert "app.js?v=20260726.12" in INDEX
