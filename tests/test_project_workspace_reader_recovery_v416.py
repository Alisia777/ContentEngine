"""Contracts for the direct selected-project Finder/media reader recovery."""

from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
PREVIOUS = MIGRATIONS / "202608040008_project_flow_read_only.sql"
PROJECT_SCOPE = MIGRATIONS / "202608040005_project_scoped_workflow.sql"
MIGRATION = MIGRATIONS / "202608040009_project_workspace_reader_recovery.sql"
PGTAP = ROOT / "supabase/tests/project_workspace_reader_recovery_test.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(source: str) -> str:
    return re.sub(r"\s+", " ", source.lower()).strip()


def _function(source: str, schema: str, name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+{re.escape(schema)}\."
        rf"{re.escape(name)}\s*\([\s\S]*?\n\$\$;",
        source,
        flags=re.IGNORECASE,
    )
    assert match, f"missing {schema}.{name}"
    return match.group(0)


def test_reader_recovery_is_one_ordered_immutable_migration() -> None:
    versions = [path.name.split("_", 1)[0] for path in MIGRATIONS.glob("*.sql")]
    source = _normalized(_read(MIGRATION))

    assert PREVIOUS.is_file()
    assert MIGRATION.is_file()
    assert PREVIOUS.name < MIGRATION.name
    assert versions.count("202608040009") == 1
    assert source.startswith("begin;")
    assert source.endswith("commit;")
    assert "drop function public.creator_workspace_browser" not in source
    assert "drop function public.creator_workspace_section" not in source
    assert not re.search(r"\bowner\s+to\b", source)


def test_previous_reader_defect_is_the_post_limit_organization_scan() -> None:
    source = _read(PROJECT_SCOPE)
    browser = _normalized(
        _function(source, "public", "creator_workspace_browser")
    )
    collection = _normalized(_function(
        source,
        "content_factory_private",
        "project_workspace_collection_v47",
    ))

    assert "creator_workspace_browser_pre_project_v47" in browser
    assert "loop scan_items :=" in browser
    assert "media.project_id = project_id_value" in browser
    assert browser.index("creator_workspace_browser_pre_project_v47") < browser.index(
        "media.project_id = project_id_value"
    )
    assert "creator_workspace_section_pre_project_v47" in collection
    assert "scan_pages >= 20" in collection


def test_finder_is_direct_project_indexed_and_has_no_profile_write() -> None:
    function = _normalized(
        _function(_read(MIGRATION), "public", "creator_workspace_browser")
    )

    assert "returns jsonb language plpgsql stable security definer" in function
    assert "set search_path = ''" in function
    assert "user_id := auth.uid();" in function
    assert "message = 'authentication_required'" in function
    assert "message = 'verified_email_required'" in function
    assert "message = 'profile_not_active'" in function
    assert "content_factory_private.require_workspace_project(" in function
    assert "media.project_id = project_id_value" in function
    assert "task.project_id = project_id_value" in function
    assert "limit page_size + 1" in function
    assert "current_profile_id" not in function
    assert "creator_workspace_browser_pre_project_v47" not in function
    assert "creator_workspace_section_pre_project_v47" not in function
    for dml in ("insert into", "update content_factory", "delete from", "merge into"):
        assert dml not in function


def test_direct_project_media_keysets_have_manager_and_operator_indexes() -> None:
    source = _normalized(_read(MIGRATION))

    assert (
        "create index if not exists media_objects_project_created_page_idx "
        "on content_factory.media_objects ( organization_id, project_id, "
        "created_at desc, id desc ) where project_id is not null and "
        "status <> 'deleted';"
    ) in source
    assert (
        "create index if not exists media_objects_project_owner_created_page_idx "
        "on content_factory.media_objects ( organization_id, project_id, "
        "owner_id, created_at desc, id desc ) where project_id is not null and "
        "status <> 'deleted';"
    ) in source


def test_finder_preserves_payload_folder_cursor_and_visibility_guards() -> None:
    function = _normalized(
        _function(_read(MIGRATION), "public", "creator_workspace_browser")
    )

    for code in (
        "workspace_browser_payload_invalid",
        "project_id_required",
        "workspace_folder_not_found",
        "workspace_folder_project_mismatch",
        "workspace_page_size_invalid",
        "workspace_search_invalid",
        "workspace_entity_types_invalid",
        "workspace_media_kinds_invalid",
        "workspace_task_statuses_invalid",
        "workspace_cursor_invalid",
    ):
        assert f"message = '{code}'" in function
    assert "folder_id_value is null or location.folder_id is not distinct from folder_id_value" in function
    assert "manager_scope or media.owner_id = user_id" in function
    assert "manager_scope or task.assignee_id = user_id" in function
    assert "content_factory_private.workspace_project_for_folder(" in function
    assert "'project_id', project_id_value" in function
    assert "'kind', folder.kind" in function
    assert "'system_role', folder.system_role" in function
    assert "folder_manage_scope and folder.system_role is null" in function


def test_project_media_branch_bypasses_legacy_collection_for_empty_and_populated_projects() -> None:
    function = _normalized(
        _function(_read(MIGRATION), "public", "creator_workspace_section")
    )

    assert "returns jsonb language plpgsql volatile security definer" in function
    direct_start = function.index("user_id := auth.uid();")
    direct_query = function.index("from content_factory.media_objects candidate")
    legacy_branch = function.index(
        "return content_factory_private.creator_workspace_section_pre_project_reader_recovery_v416"
    )
    assert legacy_branch < direct_start < direct_query
    assert "if section_value <> 'media' or not (p_payload ? 'project_id') then" in function
    assert "candidate.project_id = project_id_value" in function
    assert function.index("candidate.project_id = project_id_value") < function.index(
        "limit page_size_value"
    )
    assert "project_workspace_collection_v47" not in function
    assert "creator_workspace_section_pre_project_v47" not in function
    assert "current_profile_id" not in function


def test_project_media_preserves_auth_scope_cursor_and_response_shape() -> None:
    function = _normalized(
        _function(_read(MIGRATION), "public", "creator_workspace_section")
    )

    assert "content_factory_private.membership_role(" in function
    assert "content_factory_private.require_workspace_project(" in function
    assert "content_factory_private.validate_workspace_cursor(" in function
    assert "array['media_items']" in function
    assert "candidate.organization_id = organization_id" in function
    assert "team_scope or candidate.owner_id = user_id" in function
    assert "candidate.status <> 'deleted'" in function
    assert "'media', media_value" in function
    assert "'project_id', project_id_value" in function
    assert "'cursor_mode', 'keyset_at_id'" in function


def test_private_legacy_multiplexer_is_not_browser_callable() -> None:
    source = _normalized(_read(MIGRATION))

    assert (
        "revoke all on function content_factory_private."
        "creator_workspace_section_pre_project_reader_recovery_v416( jsonb ) "
        "from public, anon, authenticated;"
    ) in source
    assert (
        "grant execute on function public.creator_workspace_browser(jsonb) "
        "to authenticated;"
    ) in source
    assert (
        "grant execute on function public.creator_workspace_section(jsonb) "
        "to authenticated;"
    ) in source
    assert source.count("notify pgrst, 'reload schema';") == 1


def test_pgtap_traps_legacy_reader_and_proves_empty_project_isolation() -> None:
    source = _normalized(_read(PGTAP))

    assert "select plan(18);" in source
    assert "empty selected-project finder returns without scanning neighbor history" in source
    assert "workspace_folder_project_mismatch" in source
    assert "legacy_reader_called" in source
    assert "empty project media bypasses the trapped legacy reader" in source
    assert "populated project media is returned without the trapped legacy reader" in source
    assert "media result preserves the exact selected project identity" in source
    assert "finder and media reads do not update the profile row" in source
    assert source.endswith("rollback;")
