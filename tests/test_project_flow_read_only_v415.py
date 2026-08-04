"""Contracts for the read-only project chooser RPC hotfix."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
PREVIOUS_MIGRATION = MIGRATIONS / "202608040007_project_flow_catalog_hotfix.sql"
MIGRATION = MIGRATIONS / "202608040008_project_flow_read_only.sql"
PGTAP = ROOT / "supabase/tests/project_flow_read_only_test.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(source: str) -> str:
    return re.sub(r"\s+", " ", source.lower()).strip()


def _function(source: str) -> str:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"public\.creator_project_flow\s*\(\s*"
        r"p_payload\s+jsonb\s+default\s+'\{\}'::jsonb\s*\)"
        r"[\s\S]*?\n\$\$;",
        source,
        flags=re.IGNORECASE,
    )
    assert match, "creator_project_flow(jsonb) replacement is missing"
    return match.group(0)


def test_read_only_hotfix_has_one_new_ordered_immutable_migration() -> None:
    versions = [path.name.split("_", 1)[0] for path in MIGRATIONS.glob("*.sql")]

    assert PREVIOUS_MIGRATION.is_file()
    assert MIGRATION.is_file()
    assert versions.count("202608040008") == 1
    assert PREVIOUS_MIGRATION.name < MIGRATION.name

    source = _normalized(_read(MIGRATION))
    assert source.startswith("begin;")
    assert source.endswith("commit;")
    assert "drop function public.creator_project_flow" not in source
    assert not re.search(
        r"alter\s+function\s+public\.creator_project_flow\s*\(\s*jsonb\s*\)"
        r"\s+owner\s+to",
        source,
    )


def test_project_flow_replacement_is_stable_security_definer_and_read_only() -> None:
    function = _normalized(_function(_read(MIGRATION)))

    assert "returns jsonb language plpgsql stable security definer" in function
    assert "set search_path = ''" in function
    assert "user_id := auth.uid();" in function
    assert "if user_id is null then" in function
    assert "message = 'authentication_required'" in function
    assert "from auth.users auth_user" in function
    assert "message = 'verified_email_required'" in function
    assert "from content_factory.profiles profile" in function
    assert "message = 'profile_not_active'" in function

    for write_or_receipt in (
        "current_profile_id",
        "begin_command",
        "finish_command",
    ):
        assert write_or_receipt not in function
    for dml in ("insert", "update", "delete", "merge"):
        assert not re.search(rf"\b{dml}\b", function)


def test_hotfix_only_replaces_mutating_profile_resolution_in_the_flow() -> None:
    previous = _normalized(_function(_read(PREVIOUS_MIGRATION)))
    current = _normalized(_function(_read(MIGRATION)))

    payload_start = "begin p_payload :="
    authentication_start = "user_id :="
    flow_start = "organization_id :="
    assert current[
        current.index(payload_start) : current.index(authentication_start)
    ] == previous[
        previous.index(payload_start) : previous.index(authentication_start)
    ]
    assert current[current.index(flow_start) :] == previous[
        previous.index(flow_start) :
    ]


def test_project_flow_preserves_optional_exact_snapshot_and_light_catalog() -> None:
    function = _normalized(_function(_read(MIGRATION)))

    assert "if nullif(btrim(coalesce(p_payload ->> 'project_id', '')), '') is not null" in function
    assert "content_factory_private.require_workspace_project(" in function
    assert function.count("content_factory_private.project_flow_snapshot(") == 1
    assert "if include_projects then" in function
    assert "from content_factory.workspace_folders project" in function
    assert "project.kind = 'project'" in function
    assert "project.status = 'active'" in function
    assert "order by project.updated_at desc, project.id desc" in function
    assert "'catalog_state', 'summary'" in function
    assert "'catalog_state', 'exact'" in function
    assert "lateral" not in function


def test_project_flow_preserves_public_permissions_and_postgrest_reload() -> None:
    source = _normalized(_read(MIGRATION))

    assert (
        "revoke all on function public.creator_project_flow(jsonb) "
        "from public, anon;"
    ) in source
    assert (
        "grant execute on function public.creator_project_flow(jsonb) "
        "to authenticated;"
    ) in source
    assert "notify pgrst, 'reload schema';" in source


def test_pgtap_exercises_bare_selected_and_non_mutating_calls() -> None:
    source = _normalized(_read(PGTAP))

    assert "select plan(12);" in source
    assert "bare project catalog works without project_id" in source
    assert "selected-project flow still returns the exact project snapshot" in source
    assert "selected project keeps its exact catalog marker" in source
    assert "project catalog and selected flow do not update the profile row" in source
    assert "position( 'current_profile_id' in pg_get_functiondef(" in source
    assert "position( 'auth.uid()' in pg_get_functiondef(" in source
    assert source.endswith("rollback;")
