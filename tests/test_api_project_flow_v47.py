"""Focused contract checks for the server-owned project flow v4.7."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/202608040004_project_scoped_workflow.sql"
).read_text(encoding="utf-8")
FOLDER_MIGRATION = (
    ROOT / "supabase/migrations/202607160001_workspace_folders.sql"
).read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")


def _sql_function_from(source: str, name: str) -> str:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+"
        rf"(?:public|content_factory_private)\.{re.escape(name)}\b",
        source,
        flags=re.IGNORECASE,
    )
    assert match, f"missing SQL function: {name}"
    next_function = re.search(
        r"\ncreate\s+or\s+replace\s+function\s+",
        source[match.end() :],
        flags=re.IGNORECASE,
    )
    end = len(source) if next_function is None else match.end() + next_function.start()
    return source[match.start() : end]


def _sql_function(name: str) -> str:
    return _sql_function_from(MIGRATION, name)


def _run_api(body: str) -> dict:
    """Execute focused CreatorApi calls against an in-memory RPC recorder."""

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the CreatorApi contract")
    with tempfile.TemporaryDirectory() as temporary_directory:
        workdir = Path(temporary_directory)
        (workdir / "subject.mjs").write_text(API, encoding="utf-8")
        (workdir / "contract.mjs").write_text(
            """
            import { CreatorApi } from "./subject.mjs";
            globalThis.window = {
              sessionStorage: {
                values: new Map(),
                getItem(key) { return this.values.get(key) || null; },
                setItem(key, value) { this.values.set(key, value); },
              },
            };
            const calls = [];
            const supabase = {
              schema: () => ({
                rpc: async (name, args) => {
                  calls.push([name, args.p_payload]);
                  return { data: { ok: true }, error: null };
                },
              }),
            };
            const api = new CreatorApi(supabase, {
              RPC_SCHEMA: "public",
              STORAGE_BUCKET: "private",
            });
            api.organizationId = "00000000-0000-4000-8000-000000000001";
            """
            + f"const result = await (async () => {{\n{body}\n}})();\n"
            + "process.stdout.write(JSON.stringify({ result, calls }));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_schema_has_explicit_projects_and_nullable_immutable_lineage() -> None:
    assert "kind in ('project', 'folder')" in MIGRATION
    assert "workspace_folder_kind_immutable" in MIGRATION
    for table in (
        "media_objects",
        "generation_batches",
        "generation_jobs",
        "creator_tasks",
        "content_review_runs",
        "placements",
    ):
        assert re.search(
            rf"alter\s+table\s+content_factory\.{table}\s+"
            rf"add\s+column\s+if\s+not\s+exists\s+project_id\s+uuid",
            MIGRATION,
            flags=re.IGNORECASE,
        )
        assert re.search(
            rf"{table}[^;]*foreign\s+key\s*\(organization_id,\s*project_id\)",
            MIGRATION,
            flags=re.IGNORECASE | re.DOTALL,
        )
    assert "project_id_immutable" in MIGRATION
    assert "project_lineage_mismatch" in MIGRATION
    assert "project_id uuid not null" not in MIGRATION
    assert "cannot be established without guessing" in MIGRATION
    assert MIGRATION.count("scope.project_count = 1") >= 4
    assert "ambiguous/unscoped task stays legacy NULL" in MIGRATION


def test_project_creation_is_atomic_and_has_stable_default_folder_roles() -> None:
    function = _sql_function("creator_create_workspace_project")
    assert "begin_command" in function and "finish_command" in function
    assert "kind, system_role" in function
    for role, label in (
        ("sources", "Исходники"),
        ("drafts", "Черновики"),
        ("review", "На проверке"),
        ("ready", "Готово"),
        ("published", "Опубликовано"),
    ):
        assert f"('{role}', '{label}'" in function
    assert "project-default-folders-v1" in function
    assert "'project', flow_value -> 'project'" in function
    assert "'next_action', flow_value -> 'next_action'" in function


def test_project_boundary_survives_folder_moves_and_finder_defaults_to_all() -> None:
    folder_guard = _sql_function("guard_workspace_project_kind")
    browser = _sql_function("creator_workspace_browser")
    assert "workspace_cross_project_folder_move_forbidden" in folder_guard
    assert "old_project_id is distinct from parent_project_id" in folder_guard
    assert "workspace_project_not_empty" in folder_guard
    for table in (
        "media_objects",
        "generation_batches",
        "generation_jobs",
        "creator_tasks",
        "content_review_runs",
        "product_research_runs",
        "creative_brief_drafts",
        "placements",
    ):
        assert f"content_factory.{table}" in folder_guard
    assert re.search(
        r"before\s+insert\s+or\s+update\s+of\s+"
        r"name,\s*color_token,\s*kind,\s*system_role,\s*parent_id,\s*status",
        MIGRATION,
        flags=re.IGNORECASE,
    )
    assert "all project objects" in browser
    assert "inner_payload := p_payload - 'project_id' - 'folder_id'" in browser
    assert "folder_id_value := project_id_value" not in browser
    assert "'kind', folder_row.kind" in browser
    assert "'system_role', folder_row.system_role" in browser
    assert browser.count("'can_edit'") >= 2
    assert re.search(
        r"'can_edit',\s*folder_row\.system_role\s+is\s+null\s+and",
        browser,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"'can_edit',\s*folder\.system_role\s+is\s+null\s+and",
        browser,
        flags=re.IGNORECASE,
    )


def test_system_folder_identity_and_status_need_the_controlled_archive_context() -> None:
    guard = _sql_function("guard_workspace_project_kind")
    system_guard = guard[
        guard.index("if old.system_role is not null then") :
        guard.index("if old.kind = 'project'", guard.index("if old.system_role is not null then"))
    ]

    for immutable_field in (
        "new.name is distinct from old.name",
        "new.color_token is distinct from old.color_token",
        "new.system_role is distinct from old.system_role",
        "new.parent_id is distinct from old.parent_id",
    ):
        assert immutable_field in system_guard
    assert "workspace_system_folder_identity_immutable" in system_guard
    assert "new.status is distinct from old.status" in system_guard
    assert "current_setting('contentengine.project_archive_id', true)" in system_guard
    assert "exception when invalid_text_representation" in system_guard
    assert "old.status = 'active'" in system_guard
    assert "new.status = 'archived'" in system_guard
    assert "old.parent_id = archive_context_id" in system_guard
    assert "workspace_system_folder_status_immutable" in system_guard


def test_project_archive_is_recursive_versioned_idempotent_and_context_scoped() -> None:
    archive = _sql_function("creator_archive_workspace_project")

    for field in (
        "'organization_id'",
        "'idempotency_key'",
        "'project_id'",
        "'expected_version'",
    ):
        assert field in archive
    assert "workspace_project_archive_payload_invalid" in archive
    assert "array['owner', 'admin', 'producer']" in archive
    assert "require_uuid(p_payload, 'project_id')" in archive
    assert "workspace_project_version_invalid" in archive
    assert "begin_command" in archive and "finish_command" in archive
    assert "if replay_value is not null then return replay_value" in archive
    assert "hashtext('workspace_structure')" in archive
    assert "project_row.kind <> 'project'" in archive
    assert "project_row.status <> 'active'" in archive
    assert "project_row.version <> expected_version_value" in archive
    assert "current_setting(" in archive
    assert "'contentengine.project_archive_id', true" in archive
    assert "project_id_value::text, true" in archive
    assert archive.count("coalesce(previous_archive_context, ''), true") == 2
    assert "with recursive project_tree as" in archive
    assert "order by project_tree.depth desc" in archive
    descendant_update = archive.index("update content_factory.workspace_folders folder")
    project_update = archive.index("update content_factory.workspace_folders project")
    assert descendant_update < project_update
    assert "workspace_project_archived" in archive
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+"
        r"public\.creator_archive_workspace_project\(jsonb\)\s+from\s+public,\s*anon",
        archive,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.creator_archive_workspace_project\(jsonb\)\s+to\s+authenticated",
        archive,
        flags=re.IGNORECASE,
    )


def test_every_project_archive_requires_the_dedicated_command_context() -> None:
    guard = _sql_function("guard_workspace_project_kind")
    project_start = guard.index(
        "if old.kind = 'project' and old.status = 'active'"
    )
    project_end = guard.index("if new.kind = 'project' then", project_start)
    project_archive_guard = guard[project_start:project_end]

    assert "new.status = 'archived'" in project_archive_guard
    assert "current_setting('contentengine.project_archive_id', true)" in project_archive_guard
    assert "exception when invalid_text_representation" in project_archive_guard
    assert "archive_context_id is distinct from old.id" in project_archive_guard
    assert "workspace_project_archive_command_required" in project_archive_guard
    assert project_archive_guard.index("workspace_project_archive_command_required") < (
        project_archive_guard.index("content_factory.media_objects")
    )

    generic_update = _sql_function_from(
        FOLDER_MIGRATION, "creator_update_workspace_folder"
    )
    assert "archive_value := (p_payload ->> 'archive')::boolean" in generic_update
    assert "status = case when archive_value then 'archived'" in generic_update
    assert "contentengine.project_archive_id" not in generic_update
    assert "set_config(" not in generic_update

    trigger = re.search(
        r"create\s+trigger\s+guard_workspace_project_kind[\s\S]*?"
        r"before\s+insert\s+or\s+update\s+of[\s\S]*?status[\s\S]*?"
        r"on\s+content_factory\.workspace_folders",
        MIGRATION,
        flags=re.IGNORECASE,
    )
    assert trigger, "the generic folder UPDATE must cross the project archive guard"


def test_research_backfill_never_infers_from_only_the_scoped_subset() -> None:
    backfill_start = MIGRATION.index("with research_scope as (")
    backfill_end = MIGRATION.index(
        "update content_factory.creative_brief_drafts", backfill_start
    )
    backfill = MIGRATION[backfill_start:backfill_end]

    assert "left join content_factory.media_objects" in backfill
    assert "count(*) as source_count" in backfill
    assert "count(media.project_id) as scoped_source_count" in backfill
    assert "scope.source_count = scope.scoped_source_count" in backfill
    assert "scope.project_count = 1" in backfill
    assert "where media.project_id is not null" not in backfill


def test_project_flow_is_truth_based_and_returns_one_exact_next_action() -> None:
    snapshot = _sql_function("project_flow_snapshot")
    public_flow = _sql_function("creator_project_flow")
    for table in (
        "media_objects",
        "generation_jobs",
        "content_review_runs",
        "content_review_decisions",
        "placements",
        "metric_snapshots",
    ):
        assert f"content_factory.{table}" in snapshot
    for state in ("done", "current", "blocked", "too_early"):
        assert f"'{state}'" in snapshot
    for stage in ("files", "generation", "review", "placement", "stats"):
        assert f"'{stage}'" in snapshot
    assert "next_action" in snapshot
    assert "entity_type" in snapshot and "entity_id" in snapshot
    assert "latest_review_decision = 'needs_changes'" in snapshot
    assert "latest_placement_status <> 'published'" in snapshot
    assert "latest_placement_metric_count = 0" in snapshot
    assert "unreviewed_media_id" in snapshot
    assert "unplaced_review_id" in snapshot
    assert "child.parent_review_id = review.id" in snapshot
    assert snapshot.index("elsif latest_placement_id is null") < snapshot.index(
        "elsif latest_placement_metric_count = 0"
    )
    assert "placement_owned_by_teammate" in snapshot
    assert "max(task.updated_at)" in snapshot
    assert "max(decision.created_at)" in snapshot
    assert "projects" in public_flow and "stages" in public_flow
    assert "next_action" in public_flow and "counts" in public_flow


def test_terminal_placement_never_blocks_a_replacement_or_newer_publication() -> None:
    snapshot = _sql_function("project_flow_snapshot")
    review_lookup = snapshot[
        snapshot.index("into unplaced_review_id") : snapshot.index(
            "into placement_count"
        )
    ]
    placement_lookup = snapshot[
        snapshot.index("into latest_placement_id") : snapshot.index(
            "if latest_placement_id is not null"
        )
    ]

    assert "placement.status not in ('failed', 'cancelled')" in review_lookup
    assert "placement.status not in ('failed', 'cancelled')" in placement_lookup
    assert "when placement.status <> 'published' then 0" in placement_lookup
    assert "approved_placement_missing" in snapshot


def test_terminal_review_and_generation_states_return_real_recovery_actions() -> None:
    snapshot = _sql_function("project_flow_snapshot")
    unreviewed_lookup = snapshot[
        snapshot.index("into unreviewed_media_id") : snapshot.index(
            "into generated_count"
        )
    ]
    review_lookup = snapshot[
        snapshot.index("into latest_review_id") : snapshot.index(
            "into unplaced_review_id"
        )
    ]

    assert "review.status not in ('cancelled', 'failed')" in unreviewed_lookup
    assert "review.status <> 'failed'" in review_lookup
    assert "replacement_review" in review_lookup
    assert "replacement_media" in review_lookup
    assert "failed_job_source_media_id" in snapshot
    assert "latest_job_input ->> 'input_media_id'" in snapshot
    assert "latest_job_status in ('failed', 'cancelled')" in snapshot
    assert "'code', case" in snapshot and "else 'retry_generation'" in snapshot
    assert "'&view=create&media=' || failed_job_source_media_id::text" in snapshot
    assert "'&view=history&job=' || latest_job_id::text" in snapshot
    assert "latest_review_decision = 'needs_changes'" in snapshot
    assert "'&view=create&review=' || latest_review_id::text" in snapshot
    assert "latest_review_decision = 'rejected'" in snapshot
    assert "'code', 'replace_rejected_content'" in snapshot
    assert "'&view=create&media=' || source_media_id::text" in snapshot


def test_project_flow_exposes_one_deterministic_task_inside_its_origin_stage() -> None:
    snapshot = _sql_function("project_flow_snapshot")

    assert "actionable_task_id" in snapshot
    assert "task.project_id = p_project_id" in snapshot
    assert "task.status in (" in snapshot
    assert "when 'blocked' then 0" in snapshot
    assert "task.priority asc" in snapshot
    assert "task.due_at asc nulls last" in snapshot
    assert "task.updated_at asc" in snapshot
    assert "task.id asc" in snapshot
    assert "when 'video_review' then 'review'" in snapshot
    assert "when 'placement' then 'placement'" in snapshot
    assert "when 'metrics' then 'stats'" in snapshot
    assert "actionable_task_stage = active_stage" in snapshot
    assert "'/workspace/tasks?project_id='" in snapshot
    assert "'&view=next&origin_stage='" in snapshot
    assert "'&item=' || actionable_task_id::text" in snapshot
    assert "'entity_type', 'creator_task'" in snapshot
    assert "'project_id', p_project_id" in snapshot

    section = _sql_function("creator_workspace_section")
    assert "project_task_cursor_unsupported" in section
    assert section.index("project_task_cursor_unsupported") < section.index(
        "result_value :="
    )


def test_product_research_rpc_surface_is_explicitly_project_scoped() -> None:
    rpc_start = API.index("const RPC = Object.freeze({")
    rpc_block = API[rpc_start : API.index("});", rpc_start)]
    expected = {
        "startProductResearch": "creator_start_project_research",
        "productResearchStatus": "creator_project_research_status",
        "saveCreativeBriefDraft": "creator_save_project_creative_brief_draft",
        "approveCreativeBrief": "creator_approve_project_creative_brief",
    }
    for api_name, rpc_name in expected.items():
        assert f'{api_name}: "{rpc_name}"' in rpc_block

    for method_name in (
        "startProductResearch",
        "productResearchStatus",
        "saveCreativeBriefDraft",
        "approveCreativeBrief",
    ):
        method = re.search(
            rf"\n  (?:async\s+)?{re.escape(method_name)}\(",
            API,
        )
        assert method, f"missing CreatorApi method: {method_name}"
        next_method = re.search(
            r"\n  (?:async\s+)?[A-Za-z_$][\w$]*\(",
            API[method.end() :],
        )
        assert next_method, f"missing method boundary after: {method_name}"
        body = API[method.start() : method.end() + next_method.start()]
        assert "requiredProjectId(" in body
        assert "project_id" in body

    for function_name in expected.values():
        wrapper = _sql_function(function_name)
        assert "p_payload, 'project_id'" in wrapper
        assert "require_workspace_project" in wrapper
        assert "require_project_entity" in wrapper
        assert "'project_id', project_id_value" in wrapper
        assert f"revoke all on function public.{function_name}(jsonb)" in MIGRATION
        assert f"grant execute on function public.{function_name}(jsonb)" in MIGRATION

    start_wrapper = _sql_function("creator_start_project_research")
    assert "source_media_ids" in start_wrapper
    assert "'media', media_id_value" in start_wrapper
    assert "'project-v47:'" in start_wrapper
    approve_wrapper = _sql_function("creator_approve_project_creative_brief")
    assert "task.project_id = project_id_value" in approve_wrapper


def test_public_project_wrapper_fails_closed_when_project_id_is_missing() -> None:
    dispatcher = _sql_function("call_project_scoped_v47")
    missing_start = dispatcher.index("if not (p_payload ? 'project_id') then")
    missing_end = dispatcher.index("project_id_value :=", missing_start)
    missing_branch = dispatcher[missing_start:missing_end]

    assert "message = 'project_id_required'" in missing_branch
    assert "call_jsonb_function(" not in missing_branch


def test_nested_generation_policy_calls_inherit_only_the_validated_project_context() -> None:
    bridge = _sql_function("project_payload_from_context_v47")
    dispatcher = _sql_function("call_project_scoped_v47")
    repair = _sql_function("creator_generation_repair_policy")
    learning = _sql_function("creator_generation_learning_policy")

    assert "if p_payload ? 'project_id'" in bridge
    assert "current_setting('contentengine.project_id', true)" in bridge
    assert "message = 'project_id_required'" in bridge
    assert "context_value::uuid" in bridge
    assert "jsonb_build_object('project_id', context_project_id)" in bridge
    assert "set_config('contentengine.project_id', project_id_value::text, true)" in dispatcher
    assert "project_payload_from_context_v47(p_payload)" in repair
    assert "project_payload_from_context_v47(p_payload)" in learning
    assert "'review', 'review_id'" in repair
    assert "'media', 'media_id'" in learning
    assert (
        "content_factory_private.project_payload_from_context_v47(jsonb)"
        in MIGRATION
    )


def test_all_server_routes_use_canonical_project_id_query() -> None:
    snapshot = _sql_function("project_flow_snapshot")
    assert "?project_id=" in snapshot
    assert "&project_id=" not in snapshot
    assert not re.search(r"[?&]project=", snapshot)
    for exact_key in ("job=", "review=", "placement=", "media="):
        assert exact_key in snapshot


def test_project_scoped_reads_and_mutations_preserve_legacy_calls() -> None:
    for function_name in (
        "creator_workspace_browser",
        "creator_workspace_section",
        "creator_my_work",
        "creator_content_review_catalog",
    ):
        function = _sql_function(function_name)
        assert "project_id" in function
        assert "not (p_payload ? 'project_id')" in function
        assert "pre_project_v47" in function
    mutation_dispatch = _sql_function("call_project_scoped_v47")
    assert "not (p_payload ? 'project_id')" in mutation_dispatch
    assert "require_project_entity" in mutation_dispatch
    assert "project_media_scope_mismatch" in mutation_dispatch
    assert "p_payload - 'project_id'" in mutation_dispatch
    assert "creator_register_media_pre_project_v47" in mutation_dispatch
    assert "result_value #>> '{media,id}'" in mutation_dispatch
    assert "previous_project_setting" in mutation_dispatch
    assert mutation_dispatch.count("coalesce(previous_project_setting, '')") == 2


def test_project_reads_scope_before_or_across_legacy_limits() -> None:
    browser = _sql_function("creator_workspace_browser")
    section_scan = _sql_function("project_workspace_collection_v47")
    my_work = _sql_function("creator_my_work")
    catalog_base = _sql_function(
        "creator_content_review_catalog_without_assignments"
    )
    catalog = _sql_function("creator_content_review_catalog")

    assert "until this project has a full page" in browser
    assert "scan_result #> '{_meta,next_cursor}'" in browser
    assert "project_has_more" in browser and "project_next_cursor" in browser
    assert "creator_workspace_section_pre_project_v47" in section_scan
    assert "jsonb_build_object(p_cursor_key, last_cursor)" in section_scan
    assert "all_project_items" in my_work
    assert "from jsonb_array_elements(all_project_items)" in my_work
    assert "limit page_size_value + 1" in my_work

    media_scope = "media.project_id = project_id_value"
    review_scope = "review.project_id = project_id_value"
    assert catalog_base.index(media_scope) < catalog_base.index(
        "limit media_limit_value"
    )
    assert catalog_base.index(review_scope) < catalog_base.index(
        "limit run_limit_value"
    )
    assert "set_config(" in catalog
    assert catalog.count("coalesce(previous_project_setting, '')") == 2


def test_api_exposes_project_flow_and_optional_project_scope() -> None:
    assert 'projectFlow: "creator_project_flow"' in API
    assert 'createProject: "creator_create_workspace_project"' in API
    assert re.search(r"projectFlow\(\{\s*projectId\s*=", API)
    assert re.search(r"createProject\(\{\s*name,\s*colorToken", API)
    assert "optionalProjectId" in API
    for method in (
        "workspaceSection",
        "workspaceBrowser",
        "myWork",
        "contentReviewCatalog",
        "startContentReview",
        "decideContentReview",
        "createMockBatch",
        "startRealGeneration",
        "recordMetric",
        "confirmPlacement",
        "registerMedia",
    ):
        start = API.index(f"{method}(")
        window = API[start : start + 8_000]
        assert "project_id" in window, f"{method} drops project_id"


def test_archive_and_restore_api_calls_send_one_explicit_project_boundary() -> None:
    assert 'archiveProject: "creator_archive_workspace_project"' in API
    assert 'restoreProjectPlacement: "creator_restore_project_placement"' in API

    archive_method = API[API.index("archiveProject(") : API.index("requestWorkspaceAccess(")]
    assert "requiredProjectId(projectId)" in archive_method
    assert "Number.isInteger(normalizedVersion)" in archive_method
    assert "workspace_project_version_invalid" in archive_method
    assert "project_id: normalizedProjectId" in archive_method
    assert "expected_version: normalizedVersion" in archive_method
    assert "this.mutate(RPC.archiveProject" in archive_method

    restore_start = API.index("restoreProjectPlacement(")
    restore_method = API[restore_start : restore_start + 700]
    assert "this.requireContentReviewId(reviewId)" in restore_method
    assert "requiredProjectId(projectIdSnake || projectId)" in restore_method
    assert "this.mutate(RPC.restoreProjectPlacement" in restore_method

    payload = _run_api(
        """
        const projectId = "11111111-1111-4111-8111-111111111111";
        const reviewId = "22222222-2222-4222-8222-222222222222";
        await api.archiveProject(projectId, 7);
        await api.restoreProjectPlacement(reviewId, { projectId });
        let invalidVersion = "";
        let missingProject = "";
        try { await api.archiveProject(projectId, 0); }
        catch (error) { invalidVersion = error.code; }
        try { await api.restoreProjectPlacement(reviewId); }
        catch (error) { missingProject = error.code; }
        return { invalidVersion, missingProject };
        """
    )
    assert payload["result"]["invalidVersion"] == "workspace_project_version_invalid"
    assert payload["result"]["missingProject"] == "project_id_required"
    assert [call[0] for call in payload["calls"]] == [
        "creator_archive_workspace_project",
        "creator_restore_project_placement",
    ]
    archive_payload = payload["calls"][0][1]
    restore_payload = payload["calls"][1][1]
    assert archive_payload["project_id"] == "11111111-1111-4111-8111-111111111111"
    assert archive_payload["expected_version"] == 7
    assert restore_payload["project_id"] == archive_payload["project_id"]
    assert restore_payload["review_id"] == "22222222-2222-4222-8222-222222222222"
    for request in (archive_payload, restore_payload):
        assert request["organization_id"] == "00000000-0000-4000-8000-000000000001"
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            request["idempotency_key"],
            flags=re.IGNORECASE,
        )


def test_private_project_helpers_are_not_callable_from_postgrest_roles() -> None:
    assert "notify pgrst, 'reload schema'" in MIGRATION
    for signature in (
        "workspace_project_for_folder(uuid, uuid)",
        "merge_project_lineage(uuid, uuid)",
        "require_workspace_project(uuid, uuid)",
        "project_flow_snapshot(uuid, uuid, uuid, text)",
        "require_project_entity(uuid, uuid, text, uuid)",
    ):
        pattern = (
            rf"revoke\s+all\s+on\s+function\s+"
            rf"content_factory_private\.{re.escape(signature)}\s+"
            rf"from\s+public,\s*anon,\s*authenticated"
        )
        assert re.search(pattern, MIGRATION, flags=re.IGNORECASE)


def test_generation_start_status_and_archive_accept_project_scope() -> None:
    assert re.search(r'type CommonStartPayload = \{[^}]*project_id: string', EDGE, re.DOTALL)
    assert not re.search(
        r'type CommonStartPayload = \{[^}]*project_id\?: string',
        EDGE,
        re.DOTALL,
    )
    assert re.search(r'type StatusPayload = \{[^}]*project_id: string', EDGE, re.DOTALL)
    assert not re.search(
        r'type StatusPayload = \{[^}]*project_id\?: string',
        EDGE,
        re.DOTALL,
    )
    assert 'Object.hasOwn(value, "project_id")' not in EDGE
    assert '...(projectId ? { project_id: projectId } : {})' not in EDGE
    assert '.eq("project_id", projectId)' in EDGE
    assert "project_id: projectId" in EDGE
    assert re.search(
        r'"creator_generation_learning_policy",\s*\{\s*p_payload:\s*\{'
        r'[^}]*project_id:\s*startPayload\.project_id',
        EDGE,
        re.DOTALL,
    )
    assert re.search(
        r'"creator_generation_repair_policy",\s*\{\s*p_payload:\s*\{'
        r'[^}]*project_id:\s*startPayload\.project_id',
        EDGE,
        re.DOTALL,
    )
    assert re.search(
        r'realGenerationStatus\(jobId,\s*\{[^}]*projectId', API, re.DOTALL
    )
    assert re.search(
        r'invokeRealGeneration\("status",\s*\{[^}]*project_id', API, re.DOTALL
    )

    archive = _sql_function("creator_generation_archive")
    assert "'organization_id', 'project_id', 'period'" in archive
    assert "require_workspace_project" in archive
    assert "batch.project_id = project_id_value" in archive
    assert archive.index("batch.project_id = project_id_value") < archive.index(
        "limit page_size + 1"
    )
    archive_api = API[API.index("generationArchive(options") :]
    archive_api = archive_api[: archive_api.index("workspaceBrowser(options")]
    assert "requiredProjectId" in archive_api and "payload.project_id" in archive_api

    status = _sql_function("creator_real_generation_status")
    assert "creator_real_generation_status_pre_project_v47" in status
    assert "'job', 'job_id'" in status


def test_workspace_access_request_is_durable_idempotent_and_never_self_grants() -> None:
    assert "create table if not exists content_factory.workspace_access_requests" in MIGRATION
    assert "workspace_access_requests_pending_uq" in MIGRATION
    assert "where status = 'pending'" in MIGRATION
    assert re.search(
        r"alter table content_factory\.workspace_access_requests enable row level security",
        MIGRATION,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"revoke all on content_factory\.workspace_access_requests\s+"
        r"from public, anon, authenticated",
        MIGRATION,
        flags=re.IGNORECASE,
    )

    request = _sql_function("creator_request_workspace_access")
    assert "membership_role(" in request and "organization_id, true, null" in request
    assert "actor_role <> 'trainee'" in request
    assert "begin_command" in request and "finish_command" in request
    assert "workspace_access_request:" in request and "pg_advisory_xact_lock" in request
    assert "membership.role in ('owner', 'admin')" in request
    assert "'responsible_manager'" in request
    for field in ("'name'", "'email'", "'status'"):
        assert field in request
    assert "workspace_access_requested" in request
    assert not re.search(
        r"\b(?:insert\s+into|update)\s+content_factory\.(?:memberships|training_access_waivers)",
        request,
        flags=re.IGNORECASE,
    )
    assert 'requestWorkspaceAccess: "creator_request_workspace_access"' in API
    assert re.search(
        r"requestWorkspaceAccess\(\)\s*\{\s*"
        r"return this\.mutate\(RPC\.requestWorkspaceAccess, \{\}\)",
        API,
    )


def test_project_operations_deny_training_and_view_only_roles_before_data_access() -> None:
    operational_roles = "array['owner', 'admin', 'producer', 'reviewer', 'operator']"
    for function_name in (
        "creator_workspace_section",
        "creator_generation_archive",
        "creator_project_placement",
    ):
        function = _sql_function(function_name)
        assert operational_roles in function
        membership = function[
            function.index("membership_role(") :
            function.index(");", function.index("membership_role(")) + 2
        ]
        assert "'trainee'" not in membership
        assert "'viewer'" not in membership

    project_media = _sql_function("creator_project_media")
    assert "surface_value not in ('generation', 'review')" in project_media
    generation_branch = project_media[
        project_media.index("if surface_value = 'review' then") :
        project_media.index("team_scope :=", project_media.index("if surface_value = 'review' then"))
    ]
    assert generation_branch.count(operational_roles) == 2
    assert "'trainee'" not in generation_branch
    assert "'viewer'" not in generation_branch

    request = _sql_function("creator_request_workspace_access")
    request_membership = request[
        request.index("membership_role(") :
        request.index(");", request.index("membership_role(")) + 2
    ]
    assert "organization_id, true, null" in request_membership
    assert "if actor_role <> 'trainee'" in request
    assert "workspace_access_request_role_not_allowed" in request
    assert "workspace_access_already_open" in request
    assert request.index("membership_role(") < request.index("begin_command(")


def test_exact_project_placement_rpc_preserves_visibility_and_latest_metrics() -> None:
    function = _sql_function("creator_project_placement")

    assert "current_profile_id()" in function
    assert "resolve_organization(p_payload)" in function
    assert "membership_role(" in function
    assert "require_workspace_project(" in function
    assert "require_project_entity(" in function
    assert "'placement', placement_id_value" in function
    assert "'owner', 'admin', 'producer', 'reviewer'" in function
    assert "team_scope or placement.assigned_to = user_id" in function
    assert "project_placement_not_visible" in function
    assert "snapshot.observed_at desc" in function
    assert "snapshot.created_at desc" in function
    assert "snapshot.id desc" in function
    assert "click.accepted_for_human_kpi" in function
    assert "greatest(" in function and "tracked_clicks" in function
    for key in (
        "'placement'",
        "'publication'",
        "'publication_option'",
        "'latest_metric'",
    ):
        assert key in function
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+"
        r"public\.creator_project_placement\(jsonb\)\s+from\s+public,\s*anon",
        function,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.creator_project_placement\(jsonb\)\s+to\s+authenticated",
        function,
        flags=re.IGNORECASE,
    )

    assert 'projectPlacement: "creator_project_placement"' in API
    method_start = API.index("projectPlacement(")
    method = API[method_start : method_start + 1_500]
    assert "isUuid(normalizedPlacementId)" in method
    assert "requiredProjectId(projectIdSnake || projectId)" in method
    assert "placement_id: normalizedPlacementId" in method
    assert "this.call(RPC.projectPlacement" in method


def test_missing_approved_placement_routes_to_the_exact_review_recovery_action() -> None:
    snapshot = _sql_function("project_flow_snapshot")
    recovery_start = snapshot.index("elsif unplaced_review_id is not null then")
    recovery_end = snapshot.index("elsif latest_placement_id is null then", recovery_start)
    recovery = snapshot[recovery_start:recovery_end]

    assert "entity_id_value := unplaced_review_id" in recovery
    assert "'/workspace/review?project_id=' || p_project_id::text" in recovery
    assert "'&view=current&review=' || unplaced_review_id::text" in recovery
    assert "'&action=restore-placement'" in recovery
    assert "'code', 'restore_placement'" in recovery
    assert "'stage', 'placement'" in recovery
    assert "'entity_type', 'content_review_run'" in recovery
    assert "'entity_id', entity_id_value" in recovery
    assert "'project_id', p_project_id" in recovery


def test_restore_placement_revalidates_immutable_approval_and_exact_project_lineage() -> None:
    restore = _sql_function("creator_restore_project_placement")

    assert "restore_project_placement_payload_invalid" in restore
    for field in (
        "'organization_id'",
        "'idempotency_key'",
        "'project_id'",
        "'review_id'",
    ):
        assert field in restore
    assert "require_uuid(p_payload, 'project_id')" in restore
    assert "require_uuid(p_payload, 'review_id')" in restore
    assert "require_project_entity(" in restore
    assert "organization_id, project_id_value, 'review', review_id_value" in restore
    assert "'project_id', project_id_value" in restore
    assert "'review_id', review_id_value" in restore
    assert "begin_command" in restore
    assert "if replay_value is not null then return replay_value" in restore
    assert "hashtext('restore-placement:' || review_id_value::text)" in restore

    assert "review.project_id = project_id_value" in restore
    assert "review_row.status <> 'completed'" in restore
    assert "review_row.completion_hash is null" in restore
    assert "decision.decision = 'approved'" in restore
    assert "not decision_row.media_watched_confirmed" in restore
    assert "decision_row.review_completion_hash <> review_row.completion_hash" in restore
    assert "decision_row.media_sha256_snapshot <> review_row.media_sha256_snapshot" in restore
    assert "media.project_id = project_id_value" in restore
    assert "media.status = 'ready'" in restore
    assert "media_row.sha256 <> review_row.media_sha256_snapshot" in restore

    existing_start = restore.index("if previous_placement_row.id is not null then")
    existing_end = restore.index("end if;", existing_start)
    existing = restore[existing_start:existing_end]
    assert "'restored', false" in existing
    assert "'placement_id', previous_placement_row.id" in existing
    assert "finish_command" in existing
    assert "placement.status not in ('failed', 'cancelled')" in restore

    assert "task.project_id = project_id_value" in restore
    assert "task.task_type = 'video_review'" in restore
    assert "job.project_id = project_id_value" in restore
    assert "job.status = 'succeeded'" in restore
    assert "job_row.output ->> 'output_media_id' is distinct from media_row.id::text" in restore
    assert "platform_value not in (" in restore
    for platform in ("instagram", "tiktok", "youtube", "vk", "telegram", "wildberries"):
        assert f"'{platform}'" in restore
    assert "length(destination_value) not between 2 and 240" in restore
    assert "assignee_id_value is null" in restore
    assert "content_review_placement_assignee_unavailable" in restore
    assert "product_id_value is null" in restore
    assert "content_review_placement_product_inactive" in restore
    assert "select count(*)::integer + 1 into placement_attempt" in restore

    task_insert = restore[
        restore.index("insert into content_factory.creator_tasks") :
        restore.index("placement_request :=", restore.index("insert into content_factory.creator_tasks"))
    ]
    placement_insert = restore[
        restore.index("insert into content_factory.placements") :
        restore.index("result_value :=", restore.index("insert into content_factory.placements"))
    ]
    assert "idempotency_key, project_id" in task_insert
    assert "project_id_value" in task_insert
    assert "metadata, project_id" in placement_insert
    assert "project_id_value" in placement_insert
    assert "'restored', true" in restore
    assert "project_placement_restored" in restore
    assert restore.count("finish_command") >= 2
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+"
        r"public\.creator_restore_project_placement\(jsonb\)\s+from\s+public,\s*anon",
        restore,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.creator_restore_project_placement\(jsonb\)\s+to\s+authenticated",
        restore,
        flags=re.IGNORECASE,
    )


def test_restore_placement_checks_exact_review_visibility_before_idempotency() -> None:
    restore = _sql_function("creator_restore_project_placement")
    begin_command = restore.index("replay_value := content_factory_private.begin_command")
    pre_command = restore[:begin_command]

    assert re.search(r"\bactor_role\s+text\s*;", pre_command)
    assert re.search(r"\bmanager_scope\s+boolean\s*;", pre_command)
    assert re.search(
        r"actor_role\s*:=\s*content_factory_private\.membership_role\(",
        pre_command,
    )
    assert re.search(
        r"manager_scope\s*:=\s*actor_role\s*=\s*any\s*\(\s*array\["
        r"\s*'owner',\s*'admin',\s*'producer',\s*'reviewer'\s*\]\s*\)",
        pre_command,
    )

    for exact_scope in (
        "review.organization_id = organization_id",
        "review.id = review_id_value",
        "review.project_id = project_id_value",
        "media.organization_id = review.organization_id",
        "media.id = review.media_object_id",
    ):
        assert exact_scope in pre_command
    assert "manager_scope" in pre_command
    assert "review.requested_by = user_id" in pre_command
    assert "media.owner_id = user_id" in pre_command
    assert re.search(
        r"(?:review_task|task)\.assignee_id\s*=\s*user_id",
        pre_command,
    )
    assert re.search(
        r"(?:review_task|task)\.id\s*=\s*media\.task_id",
        pre_command,
    )
    assert "content_review_not_visible" in pre_command
    assert pre_command.index("content_review_not_visible") > pre_command.index(
        "review.id = review_id_value"
    )


def test_restore_placement_only_uses_active_operational_assignee_and_product() -> None:
    restore = _sql_function("creator_restore_project_placement")
    validation_start = restore.index("platform_value :=")
    insert_start = restore.index("insert into content_factory.creator_tasks")
    assignment = restore[validation_start:insert_start]

    assert "assignee_id_value := coalesce(" not in assignment
    for candidate in (
        "previous_placement_row.assigned_to",
        "review_task_row.assignee_id",
        "media_row.owner_id",
    ):
        assert candidate in assignment
    assert "content_factory.memberships" in assignment
    assert "content_factory.profiles" in assignment
    assert re.search(
        r"membership\.organization_id\s*=\s*organization_id",
        assignment,
    )
    assert re.search(
        r"membership\.profile_id\s*=\s*(?:candidate\.)?profile_id",
        assignment,
    )
    assert "membership.status = 'active'" in assignment
    assert "profile.status = 'active'" in assignment
    assert re.search(
        r"membership\.role\s+(?:in\s*\(|=\s*any\s*\(\s*array\[)"
        r"[\s\S]*?'owner'[\s\S]*?'admin'[\s\S]*?'producer'"
        r"[\s\S]*?'reviewer'[\s\S]*?'operator'",
        assignment,
    )
    assert "'trainee'" not in assignment
    assert "'viewer'" not in assignment

    assert "content_factory.products" in assignment
    assert re.search(
        r"product\.organization_id\s*=\s*organization_id",
        assignment,
    )
    assert re.search(
        r"product\.id\s*=\s*(?:product_id_value|coalesce\s*\()",
        assignment,
    )
    assert "product.status = 'active'" in assignment
    assert assignment.index("membership.status = 'active'") < assignment.index(
        "content_review_placement_assignee_unavailable"
    )
    assert assignment.index("product.status = 'active'") < assignment.index(
        "content_review_placement_product_inactive"
    )
    assert assignment.index("content_review_placement_assignee_unavailable") < (
        assignment.index("from content_factory.products")
    )


def test_research_notification_branch_uses_its_entity_not_an_undefined_review_id() -> None:
    scope = _sql_function("notification_entity_scope_v47")
    research_start = scope.index("when 'product_research' then")
    research_end = scope.index("else", research_start)
    research = scope[research_start:research_end]

    assert "research.id = entity_id_value" in research
    assert "'#/workspace/research?project_id='" in research
    assert "'&view=evidence&run='" in research
    assert "entity_id_value::text" in research
    assert "review_id_value" not in research


def test_exact_project_media_rpc_matches_generation_and_review_visibility() -> None:
    function = _sql_function("creator_project_media")

    assert "current_profile_id()" in function
    assert "resolve_organization(p_payload)" in function
    assert "surface_value not in ('generation', 'review')" in function
    assert "membership_role(" in function
    assert "require_workspace_project(" in function
    assert "require_project_entity(" in function
    assert "'media', media_id_value" in function
    assert "media.project_id = project_id_value" in function
    assert "media.status = 'ready'" in function
    assert "team_scope" in function
    assert "media.owner_id = user_id" in function
    assert "surface_value = 'review' and task.assignee_id = user_id" in function
    assert "'image/jpeg', 'image/png', 'image/webp', 'video/mp4'" in function
    assert "'identity_verified'" in function
    assert "product.status = 'active'" in function
    assert "project_media_not_visible" in function
    for key in ("'project_id'", "'media_id'", "'surface'", "'media'"):
        assert key in function
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+"
        r"public\.creator_project_media\(jsonb\)\s+from\s+public,\s*anon",
        function,
        flags=re.IGNORECASE,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.creator_project_media\(jsonb\)\s+to\s+authenticated",
        function,
        flags=re.IGNORECASE,
    )

    assert 'projectMedia: "creator_project_media"' in API
    method_start = API.index("projectMedia(")
    method = API[method_start : method_start + 1_800]
    assert "isUuid(normalizedMediaId)" in method
    assert '["generation", "review"].includes(normalizedSurface)' in method
    assert "requiredProjectId(projectIdSnake || projectId)" in method
    assert "media_id: normalizedMediaId" in method
    assert "surface: normalizedSurface" in method
    assert "this.call(RPC.projectMedia" in method
