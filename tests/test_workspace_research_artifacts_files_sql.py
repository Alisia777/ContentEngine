from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608120009_workspace_research_artifacts_files.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.lower()


def _sql_function(declaration: str) -> str:
    start = LOWER.index(declaration.lower())
    body_start = LOWER.index("as $$", start)
    end = LOWER.index("\n$$;", body_start)
    return SQL[start : end + 4]


def test_migration_parses_and_is_ordered_after_operator_research_scope() -> None:
    assert MIGRATION.name > "202608120008_operator_project_research_ai.sql"
    assert len(parse_sql(SQL)) >= 15
    assert "notify pgrst, 'reload schema';" in LOWER
    assert LOWER.rindex("notify pgrst") < LOWER.rindex("commit;")


def test_research_projection_is_exact_project_read_only_and_content_free() -> None:
    projection = _sql_function(
        "create or replace function\n"
        "  content_factory_private.workspace_research_artifacts_projection("
    ).lower()
    assert "workspace_project_access_allowed" in projection
    assert "qualified_operator_project_research_allowed" in projection
    assert "qualified_operator_own_ai_research_receipt_allowed" in projection
    assert "run.created_by = p_profile_id" in projection
    assert "binding.bound_by = p_profile_id" in projection
    assert "run.project_id = p_project_id" in projection
    assert "limit 50" in projection
    for ledger in (
        "product_research_runs",
        "ai_research_evidence_receipts",
        "ai_research_evidence_dispositions",
        "ai_research_learning_selections",
    ):
        assert ledger in projection
    for forbidden in (
        "summary",
        "analysis_snapshot",
        "source_snapshot",
        "recommendations",
        "operator_notes",
        "folder_id",
    ):
        assert forbidden not in projection
    for mutation in (" insert ", " update ", " delete ", " merge ", " truncate "):
        assert mutation not in f" {projection} "
    assert "'read_only', true" in projection
    assert "'can_move', false" in projection
    assert projection.count("&receipt=") == 3
    assert projection.count("&category=") == 3
    assert "receipt.product_category as receipt_product_category" in projection
    assert "&research_receipt=" not in projection


def test_artifact_class_filter_is_strict_and_precedes_union_pagination() -> None:
    browser = _sql_function(
        "create or replace function public.creator_workspace_browser("
    ).lower()
    assert "'artifact_classes'" in browser
    assert "workspace_artifact_classes_invalid" in browser
    assert "not between 1 and 3" in browser
    assert "count(distinct item.value #>> '{}')" in browser
    for artifact_class in ("source", "generated_output", "unclassified"):
        assert f"'{artifact_class}'" in browser
    predicate = "media.artifact_class = any(artifact_classes_value)"
    assert predicate in browser
    assert browser.index(predicate) < browser.index("union all")
    assert browser.index(predicate) < browser.index("candidates as materialized")


def test_move_authority_matches_the_preserved_mature_manager_and_operator_rules() -> None:
    browser = _sql_function(
        "create or replace function public.creator_workspace_browser("
    ).lower()
    assert "array['owner', 'admin', 'producer', 'reviewer']" in browser
    assert (
        "'can_move', item_move_manager_scope\n"
        "          or coalesce(media.owner_id = user_id, false)"
    ) in browser
    assert (
        "'can_move', item_move_manager_scope\n"
        "          or coalesce(task.assignee_id = user_id, false)"
    ) in browser
    assert "'move_items', true" in browser


def test_research_is_a_separate_projection_not_a_fake_media_or_folder_item() -> None:
    browser = _sql_function(
        "create or replace function public.creator_workspace_browser("
    ).lower()
    assert "'research_artifacts', research_artifacts_value" in browser
    assert "workspace_research_artifacts_projection" in browser
    assert "array['media', 'task']::text[]" in browser
    visible_items = browser[
        browser.index("with visible_items as (") :
        browser.index("candidates as materialized")
    ]
    assert "'research'::text as entity_type" not in visible_items


def test_latest_files_reader_contract_fields_and_gates_are_preserved() -> None:
    browser = _sql_function(
        "create or replace function public.creator_workspace_browser("
    ).lower()
    for gate in (
        "authentication_required",
        "verified_email_required",
        "profile_not_active",
        "membership_role",
        "require_workspace_project_access",
        "workspace_folder_project_mismatch",
        "workspace_page_size_invalid",
        "workspace_cursor_invalid",
    ):
        assert gate in browser
    for key in (
        "'ok'",
        "'project_id'",
        "'current_folder_id'",
        "'current_folder'",
        "'folders'",
        "'items'",
        "'manage_folders'",
        "'move_items'",
        "'shared_project_read'",
        "'page_size'",
        "'cap'",
        "'has_more'",
        "'next_cursor'",
        "'cursor_mode'",
        "'artifact_class'",
        "'lifecycle_stage'",
        "'location_version'",
    ):
        assert key in browser


def test_files_deep_link_reader_preserves_existing_surfaces_and_exact_acl() -> None:
    wrapper = _sql_function(
        "create or replace function public.creator_project_media("
    ).lower()
    assert "creator_project_media_pre_files_v438(p_payload)" in wrapper
    assert "if surface_value <> 'files'" in wrapper
    assert "to_jsonb('generation'::text)" in wrapper
    assert "require_workspace_project_access" in wrapper
    assert "workspace_project_for_folder" in wrapper
    assert "'folder_id', folder_id_value" in wrapper
    assert "'workspace_item_key', 'media:' || media_id_value::text" in wrapper
    assert "actor_role in ('owner', 'admin', 'producer', 'reviewer')" in wrapper
    assert "coalesce(media_value ->> 'owner_id' = user_id::text, false)" in wrapper
    assert (
        "creator_project_media_pre_files_v438(jsonb)\n"
        "  from public, anon, authenticated, service_role"
    ) in LOWER


def test_public_topology_remains_authenticated_only() -> None:
    for rpc in ("creator_workspace_browser", "creator_project_media"):
        assert (
            f"revoke all on function public.{rpc}(jsonb)\n"
            "  from public, anon, service_role;"
        ) in LOWER
        assert (
            f"grant execute on function public.{rpc}(jsonb)\n"
            "  to authenticated;"
        ) in LOWER
