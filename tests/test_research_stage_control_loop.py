from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase/migrations/202608030014_research_stage_control_loop.sql"
)
PGTAP_PATH = ROOT / "supabase/tests/research_stage_control_loop_test.sql"
API_PATH = ROOT / "web/app/supabase-api.js"
APP_PATH = ROOT / "web/app/app.js"
VIEW_PATH = ROOT / "web/app/product-research-view.js"
EDGE_PATH = ROOT / "supabase/functions/creator-product-research/index.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _compact(source: str) -> str:
    return re.sub(r"\s+", " ", source.casefold()).strip()


def _sql_function(source: str, qualified_name: str) -> str:
    header = re.compile(
        rf"\bcreate\s+(?:or\s+replace\s+)?function\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        re.IGNORECASE,
    )
    match = header.search(source)
    assert match is not None, f"SQL function {qualified_name} is missing"
    next_function = re.search(
        r"\bcreate\s+(?:or\s+replace\s+)?function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_function is None else match.end() + next_function.start()
    return source[match.start() : end]


def _sql_table(source: str, qualified_name: str) -> str:
    header = re.compile(
        rf"\bcreate\s+table\s+if\s+not\s+exists\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        re.IGNORECASE,
    )
    match = header.search(source)
    assert match is not None, f"SQL table {qualified_name} is missing"
    next_table = re.search(
        r"\bcreate\s+table\s+if\s+not\s+exists\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_table is None else match.end() + next_table.start()
    return source[match.start() : end]


def _class_method(source: str, name: str) -> str:
    header = re.compile(
        rf"^\s{{2}}(?:async\s+)?{re.escape(name)}\s*\(", re.MULTILINE
    )
    match = header.search(source)
    assert match is not None, f"CreatorApi.{name} is missing"
    next_method = re.search(
        r"^\s{2}(?:async\s+)?[A-Za-z_$][\w$]*\s*\(",
        source[match.end() :],
        re.MULTILINE,
    )
    end = len(source) if next_method is None else match.end() + next_method.start()
    return source[match.start() : end]


def _top_level_function(source: str, name: str) -> str:
    header = re.compile(
        rf"^(?:export\s+)?(?:async\s+)?function\s+{re.escape(name)}\s*\(",
        re.MULTILINE,
    )
    match = header.search(source)
    assert match is not None, f"JavaScript function {name} is missing"
    next_function = re.search(
        r"^(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\(",
        source[match.end() :],
        re.MULTILINE,
    )
    end = len(source) if next_function is None else match.end() + next_function.start()
    return source[match.start() : end]


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable stage-control contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(_read(path), encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_stage_control_migration_and_pgtap_parse_as_postgresql() -> None:
    try:
        from pglast import parse_sql
    except ImportError:
        pytest.skip("pglast is required for the PostgreSQL syntax contract")

    migration = parse_sql(_read(MIGRATION_PATH))
    pgtap = parse_sql(_read(PGTAP_PATH))
    assert len(migration) >= 65
    assert len(pgtap) >= 60


def test_stage_artifact_identity_includes_exact_input_snapshot() -> None:
    sql = _read(MIGRATION_PATH)
    compact = _compact(sql)
    capture = _compact(
        _sql_function(sql, "content_factory_private.capture_research_stage_draft")
    )

    assert compact.startswith("begin;")
    assert compact.endswith("commit;")
    assert "add column if not exists input_dependencies jsonb" in compact
    assert "add column if not exists input_dependency_hash text" in compact
    assert re.search(
        r"unique\s*\(\s*organization_id, run_id, stage, content_hash, "
        r"input_dependency_hash\s*\)",
        compact,
    )
    assert "'evidence', evidence_payload" in capture
    assert "'upstream_artifacts', upstream_payload" in capture
    assert "input_dependency_hash" in capture
    assert "control_action_value <> 'recompute_completed'" in capture
    assert "artifact.input_dependency_hash = dependency_hash_value" in capture


def test_control_rpc_is_exact_idempotent_and_invalidates_downstream() -> None:
    sql = _read(MIGRATION_PATH)
    control = _compact(_sql_function(sql, "public.creator_control_research_stage"))

    for required in (
        "expected_head_event_id",
        "expected_artifact_id",
        "expected_content_hash",
        "expected_branch_revision_hash",
        "confirmation",
        "idempotency_key",
    ):
        assert required in control
    assert "array['owner', 'admin', 'producer']" in control
    assert "action_value not in ( 'patch', 'reject', 'revert', 'fork', 'recompute', 'cancel' )" in control
    assert "research_stage_branch_revision_hash(" in control
    assert "research_stage_branch_revision_stale" in control
    assert "p_payload -> 'confirmation' is distinct from 'true'::jsonb" in control
    assert "research_stage_head_stale" in control
    assert "begin_command(" in control and "finish_command(" in control
    assert "pg_advisory_xact_lock" in control
    assert "research_stage_run_locked" in control
    assert "create_research_stage_user_input(" in control
    assert "'dependency_refresh'" in control
    assert "'stale_dependency'" in control
    assert "'recompute_cancelled'" in control
    assert "research_stage_rank(head.stage) >" in control
    assert "write_research_stage_head_event(" in control
    assert "delete from content_factory.research_stage" not in control
    assert "update content_factory.research_stage_artifacts" not in control


def test_recompute_is_explicit_single_attempt_and_never_silently_retries() -> None:
    sql = _read(MIGRATION_PATH)
    edge = _read(EDGE_PATH)
    control = _compact(_sql_function(sql, "public.creator_control_research_stage"))
    request_table = _compact(
        _sql_table(sql, "content_factory.research_stage_recompute_requests")
    )
    claim = _compact(_sql_function(sql, "public.system_claim_product_research"))
    apply = _compact(
        _sql_function(sql, "public.system_apply_research_stage_recompute")
    )

    assert "research_stage_recompute_main_branch_required" in control
    assert "stage_value = 'sources'" in control
    assert "p_payload -> 'paid_analysis_ack' is distinct from 'true'::jsonb" in control
    assert control.count("creator_start_product_research(") == 1
    assert "'max_provider_attempts', 1" in control
    assert "'automatic_provider_action', false" in control
    assert "'automatic_spend', false" in control
    assert "where status in ('queued', 'processing')" in _compact(sql)
    assert "check (max_provider_attempts = 1)" in request_table
    assert "provider_attempt_count between 0 and 1" in request_table
    assert "octet_length(input_snapshot::text) <= 76800" in request_table
    assert "octet_length(input_snapshot_value::text) > 76800" in control

    assert "recompute_context" in claim
    assert "schema_version', 'research-stage-recompute-context-v1'" in claim
    assert "provider_attempt_count = 1" in claim
    assert "for update" in apply
    assert "request_row.status in ('completed', 'failed', 'superseded')" in apply
    assert "child_run_row.status in ('queued', 'processing')" in apply
    assert "head_changed_during_recompute" in apply
    assert "event.request_hash <> request_row.request_hash" in apply
    assert "'child_source_copy_invalid'" in apply
    assert "jsonb_agg(root_source.id order by selected.ordinal)" in apply
    assert "'recompute_completed'" in apply
    assert "creator_start_product_research(" not in apply
    assert "fetch(" not in apply
    assert "const MAX_RECOMPUTE_CONTEXT_BYTES = 98_304" in edge
    assert "research-stage-recompute-context-v1" in edge
    assert "not factual evidence" in _compact(edge)


def test_status_is_tenant_bounded_compact_and_advisory_only() -> None:
    sql = _read(MIGRATION_PATH)
    status = _compact(
        _sql_function(sql, "public.creator_research_stage_control_status")
    )

    assert "resolve_organization(" in status
    assert "array['owner', 'admin', 'producer', 'reviewer']" in status
    assert "history_limit_value not between 1 and 100" in status
    assert "limit history_limit_value" in status
    assert "event.organization_id = organization_id_value" in status
    assert "event.run_id = run_id_value" in status
    assert "event.branch_id = branch_id_value" in status
    assert "'version', 'research-stage-control-v2'" in status
    assert "'allowed_actions'" in status
    assert "'recommended_next_action'" in status
    assert "'earliest_problem_stage'" in status
    assert "current_draft_origin_value = 'human'" in status
    assert "current_draft_status_value = 'draft'" in status
    assert "exact_snapshot_count = 7" in status
    assert "current_draft_id_value = approved_draft_id_value" in status
    assert "'approved_snapshot_mismatch'" in status
    assert "'ai_revision_needs_human_snapshot'" in status
    assert "'save_human_review_snapshot'" in status
    for snapshot_field in (
        "'current_draft_id'",
        "'current_draft_origin'",
        "'current_draft_status'",
        "'exact_snapshot_stage_count'",
        "'approved_draft_id'",
    ):
        assert snapshot_field in status
    for safe_flag in (
        "'automatic_provider_action', false",
        "'automatic_spend', false",
        "'automatic_generation', false",
        "'automatic_publication', false",
    ):
        assert safe_flag in status
    for forbidden in (
        "creator_start_product_research",
        "creator-product-research",
        "generation_jobs",
        "fetch(",
        "http.",
        "net.",
    ):
        assert forbidden not in status


def test_approval_rechecks_exact_seven_head_snapshot_fail_closed() -> None:
    sql = _read(MIGRATION_PATH)
    readiness = _compact(
        _sql_function(
            sql, "content_factory_private.assert_research_stage_draft_ready"
        )
    )
    approval = _compact(_sql_function(sql, "public.creator_approve_creative_brief"))

    assert "head.current_draft_id = draft_id_value" in readiness
    assert "head.state = 'rejected'" in readiness
    assert "head.state <> 'current'" in readiness
    assert "head_count <> 7 or stale_count > 0" in readiness
    assert "binding.artifact_id = head.artifact_id" in readiness
    assert "binding.dependency_hash = head.dependency_hash" in readiness
    assert "artifact.input_dependency_hash = binding.dependency_hash" in readiness
    assert "exact_count <> 7" in readiness
    assert "request.status in ('queued', 'processing')" in readiness
    for failure in (
        "research_stage_rejected",
        "research_stage_dependencies_stale",
        "research_stage_snapshot_mismatch",
        "research_stage_recompute_pending",
    ):
        assert failure in readiness

    assert "assert_research_stage_draft_ready(" in approval
    assert "creator_approve_creative_brief_pre_stage_control_v2" in approval
    assert _compact(sql).count("guard_research_stage_control_approval") >= 4


def test_sql_privileges_keep_control_writers_behind_narrow_rpc_seams() -> None:
    sql = _compact(_read(MIGRATION_PATH))

    for table in (
        "research_stage_branches",
        "research_stage_head_events",
        "research_stage_heads",
        "research_stage_recompute_requests",
    ):
        assert f"alter table content_factory.{table} enable row level security" in sql
        assert re.search(
            rf"revoke all on content_factory\.{table} "
            rf"from public, anon, authenticated, service_role",
            sql,
        )
    for rpc in (
        "creator_control_research_stage",
        "creator_research_stage_control_status",
    ):
        assert re.search(
            rf"revoke all on function public\.{rpc}\s*\(jsonb\) "
            rf"from public, anon, authenticated, service_role",
            sql,
        )
        assert re.search(
            rf"grant execute on function public\.{rpc}\s*\(jsonb\) "
            rf"to authenticated",
            sql,
        )
    assert re.search(
        r"grant execute on function "
        r"public\.system_apply_research_stage_recompute\s*\(jsonb\) "
        r"to service_role",
        sql,
    )
    assert not re.search(
        r"grant execute on function "
        r"public\.system_apply_research_stage_recompute\s*\(jsonb\) "
        r"to (?:authenticated|anon|public)",
        sql,
    )


def test_portal_exposes_stage_control_only_through_lazy_corrections_view() -> None:
    api = _read(API_PATH)
    app = _read(APP_PATH)
    view = _read(VIEW_PATH)
    product_status = _class_method(api, "productResearchStatus")
    status_method = _class_method(api, "researchStageControlStatus")
    control_method = _class_method(api, "controlResearchStage")
    cancel_handler = _top_level_function(app, "submitProductResearchStageCancel")
    mutation_handler = _top_level_function(app, "submitProductResearchStageControl")

    assert 'researchStageControlStatus: "creator_research_stage_control_status"' in api
    assert 'controlResearchStage: "creator_control_research_stage"' in api
    assert "RPC.researchStageControlStatus" in status_method
    assert "this.call(" in status_method
    assert "history_limit" in status_method and "branch_id" in status_method
    assert "requiredProjectId(" in status_method
    assert "project_id: projectId" in status_method
    assert "RPC.controlResearchStage" in control_method
    assert "this.mutate(" in control_method
    assert "requiredProjectId(" in control_method
    assert "project_id: projectId" in control_method
    for exact_field in (
        "expected_head_event_id",
        "expected_artifact_id",
        "expected_content_hash",
        "expected_branch_revision_hash",
        "confirmation",
    ):
        assert exact_field in control_method
    assert "recompute_request" in control_method
    assert control_method.count("invokeProductResearch(") == 1
    assert "researchRecomputeInvocations" in control_method
    assert "retry" not in control_method.casefold()
    assert "RPC.researchStageControlStatus" not in product_status

    for exact_token in (
        "expected_head_event_id",
        "expected_artifact_id",
        "expected_content_hash",
        "expected_branch_revision_hash",
    ):
        assert exact_token in cancel_handler
        assert exact_token in mutation_handler
    assert 'action: "cancel"' in cancel_handler
    assert 'active.canCancel !== true' in cancel_handler
    assert 'head.allowedActions.includes("cancel")' in cancel_handler
    assert "control.selectedBranch.branchRevisionHash" in cancel_handler
    assert "invokeProductResearch" not in cancel_handler
    assert "resumeResearchStageRecompute" not in cancel_handler
    assert "retry" not in cancel_handler.casefold()
    assert 'form.classList.contains("product-research-stage-cancel-form")' in app
    assert 'active.cancelReason === "branch_changed_after_prepare"' in app

    assert "normalizeResearchStageControl" in view
    assert "researchStageControlMarkup" in view
    for guidance_key in (
        "branch_comparison",
        "compare_read_only_branch_with_main",
        "invoke_saved_recompute_or_cancel",
        "cancel_expired_recompute_without_retry",
        "wait_for_active_provider_lease_without_retry",
        "discard_superseded_recompute_without_retry",
        "start_new_research_and_preserve_approved_snapshot",
        "fork_read_only_snapshot_or_start_new_research",
        "start_new_research_or_fork_read_only_snapshot",
        "branch_changed_after_prepare",
    ):
        assert guidance_key in view
    for obsolete_promise in (
        "fork_for_new_revision",
        "fork_for_controlled_revision",
        "compare_branch_with_main",
        "branch_ready",
    ):
        assert obsolete_promise not in view
    assert "Возобновите этот же запуск либо отмените его" in view
    assert "Отмените сохранённый пересчёт без повторной попытки провайдера" in view
    assert "Ждите и проверяйте статус — не запускайте повтор" in view
    assert "Завершите сохранённый запрос как superseded" in view
    assert "stageControl" in app
    assert 'researchView === "corrections"' in app
    assert 'research.record?.approved === true' in app
    assert "generationHandoffAllowed" in app
    assert "researchStageControlStatus" in app
    assert "productResearchStatus" in app
    assert app.count("researchStageControlStatus(") < app.count("productResearchStatus(")


def test_stage_control_view_rejects_unsafe_envelopes_and_escapes_payload() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const runId = "20000000-0000-4000-8000-000000000001";
        const branchRevisionHash = "c".repeat(64);
        const base = {
          ok: true,
          version: "research-stage-control-v2",
          organization_id: "10000000-0000-4000-8000-000000000001",
          run_id: runId,
          selected_branch: {
            branch_id: "30000000-0000-4000-8000-000000000001",
            branch_key: "main",
            branch_revision_hash: branchRevisionHash,
            parent_branch_id: null,
            reason: "Baseline branch",
            created_at: "2026-08-03T10:00:00Z",
          },
          branches: [{
            branch_id: "30000000-0000-4000-8000-000000000001",
            branch_key: "main",
            parent_branch_id: null,
            reason: "Baseline branch",
            created_at: "2026-08-03T10:00:00Z",
            is_selected: true,
            head_count: 1,
            problem_count: 0,
          }],
          heads: [{
            stage: "category",
            state: "current",
            head_event_id: "40000000-0000-4000-8000-000000000001",
            artifact_id: "50000000-0000-4000-8000-000000000001",
            artifact_version: 1,
            parent_artifact_id: null,
            content_hash: "a".repeat(64),
            dependency_hash: "b".repeat(64),
            artifact_input_dependency_hash: "b".repeat(64),
            stale_due_to_artifact_ids: [],
            current_draft_id: "60000000-0000-4000-8000-000000000001",
            payload: { category_name: "<script>unsafe payload</script>" },
            evidence_count: 1,
            artifact_origin: "ai",
            artifact_created_at: "2026-08-03T10:00:00Z",
            updated_at: "2026-08-03T10:00:00Z",
            allowed_actions: ["patch", "fork", "recompute"],
          }],
          history: [],
          history_limit: 30,
          history_has_more: false,
          active_recompute: null,
          guidance: {
            status: "ready_for_review",
            recommended_next_action: "review_and_approve_current_draft",
            earliest_problem_stage: null,
            earliest_problem_state: null,
            affected_stages: [],
            approval_allowed: false,
            generation_handoff_allowed: false,
            current_draft_id: "60000000-0000-4000-8000-000000000001",
            current_draft_origin: "human",
            current_draft_status: "draft",
            exact_snapshot_stage_count: 1,
            approved_draft_id: null,
            recompute_requires_paid_confirmation: true,
            automatic_provider_action: false,
            automatic_spend: false,
            automatic_generation: false,
            automatic_publication: false,
            branch_count: 1,
          },
        };
        const valid = subject.normalizeResearchStageControl(base, runId);
        const markup = subject.researchStageControlMarkup(valid);
        const guidanceMarkup = (recommendedNextAction, status) =>
          subject.researchStageControlMarkup(
            subject.normalizeResearchStageControl({
              ...base,
              guidance: {
                ...base.guidance,
                status,
                recommended_next_action: recommendedNextAction,
              },
            }, runId),
          );
        const approvedMismatchMarkup = guidanceMarkup(
          "start_new_research_and_preserve_approved_snapshot",
          "approved_snapshot_mismatch",
        );
        const approvedLockedMarkup = guidanceMarkup(
          "fork_read_only_snapshot_or_start_new_research",
          "approved_locked",
        );
        const noneditableMarkup = guidanceMarkup(
          "start_new_research_or_fork_read_only_snapshot",
          "current_draft_not_editable",
        );
        const requestId = "70000000-0000-4000-8000-000000000001";
        const childRunId = "80000000-0000-4000-8000-000000000001";
        const active = {
          ...base,
          heads: base.heads.map((head) => ({
            ...head,
            allowed_actions: ["cancel"],
          })),
          active_recompute: {
            request_id: requestId,
            child_run_id: childRunId,
            stage: "category",
            status: "queued",
            paid_analysis_ack: true,
            provider_key: "openai_web_search",
            adapter_version: "research-stage-recompute-v1",
            max_provider_attempts: 1,
            provider_attempt_count: 0,
            expected_branch_revision_hash: branchRevisionHash,
            automatic_provider_action: false,
            lease_expires_at: null,
            can_cancel: true,
            cancel_reason: "saved_before_provider_claim",
            invoke: { action: "analyze", research_id: childRunId },
          },
        };
        const validActive = subject.normalizeResearchStageControl(active, runId);
        const activeMarkup = subject.researchStageControlMarkup(validActive);
        const processing = {
          ...active,
          heads: base.heads.map((head) => ({
            ...head,
            allowed_actions: [],
          })),
          active_recompute: {
            ...active.active_recompute,
            status: "processing",
            provider_attempt_count: 1,
            lease_expires_at: "2026-08-03T10:05:00Z",
            can_cancel: false,
            cancel_reason: "provider_attempt_lease_active",
            invoke: null,
          },
        };
        const validProcessing = subject.normalizeResearchStageControl(
          processing, runId,
        );
        const processingMarkup = subject.researchStageControlMarkup(
          validProcessing,
        );
        const queuedGuidance = subject.normalizeResearchStageControl({
          ...active,
          guidance: {
            ...base.guidance,
            status: "recompute_pending",
            recommended_next_action: "invoke_saved_recompute_or_cancel",
          },
        }, runId);
        const queuedGuidanceMarkup = subject.researchStageControlMarkup(
          queuedGuidance,
        );
        const expired = subject.normalizeResearchStageControl({
          ...processing,
          heads: active.heads,
          active_recompute: {
            ...processing.active_recompute,
            can_cancel: true,
            cancel_reason: "processing_lease_expired",
          },
          guidance: {
            ...base.guidance,
            status: "recompute_pending",
            recommended_next_action:
              "cancel_expired_recompute_without_retry",
          },
        }, runId);
        const expiredMarkup = subject.researchStageControlMarkup(expired);
        const activeLeaseGuidance = subject.normalizeResearchStageControl({
          ...processing,
          guidance: {
            ...base.guidance,
            status: "recompute_pending",
            recommended_next_action:
              "wait_for_active_provider_lease_without_retry",
          },
        }, runId);
        const activeLeaseMarkup = subject.researchStageControlMarkup(
          activeLeaseGuidance,
        );
        const branchChanged = subject.normalizeResearchStageControl({
          ...processing,
          heads: active.heads,
          active_recompute: {
            ...processing.active_recompute,
            can_cancel: true,
            cancel_reason: "branch_changed_after_prepare",
          },
          guidance: {
            ...base.guidance,
            status: "recompute_pending",
            recommended_next_action:
              "discard_superseded_recompute_without_retry",
          },
        }, runId);
        const branchChangedMarkup = subject.researchStageControlMarkup(
          branchChanged,
        );
        const queuedBranchChanged = subject.normalizeResearchStageControl({
          ...active,
          active_recompute: {
            ...active.active_recompute,
            cancel_reason: "branch_changed_after_prepare",
            invoke: null,
          },
          guidance: {
            ...base.guidance,
            status: "recompute_pending",
            recommended_next_action:
              "discard_superseded_recompute_without_retry",
          },
        }, runId);
        const queuedBranchChangedMarkup = subject.researchStageControlMarkup(
          queuedBranchChanged,
        );
        const queuedBranchChangedWithInvoke =
          subject.normalizeResearchStageControl({
            ...active,
            active_recompute: {
              ...active.active_recompute,
              cancel_reason: "branch_changed_after_prepare",
            },
          }, runId);
        const processingWithInvoke = subject.normalizeResearchStageControl({
          ...processing,
          active_recompute: {
            ...processing.active_recompute,
            invoke: { action: "analyze", research_id: childRunId },
          },
        }, runId);
        const wrongActiveBranchHash = subject.normalizeResearchStageControl({
          ...active,
          active_recompute: {
            ...active.active_recompute,
            expected_branch_revision_hash: "not-a-hash",
          },
        }, runId);
        const activeWithoutCancelAction = subject.normalizeResearchStageControl({
          ...active,
          heads: base.heads,
        }, runId);
        const comparison = {
          ...base,
          selected_branch: {
            ...base.selected_branch,
            branch_key: "comparison-angle",
          },
          branches: base.branches.map((branch) => ({
            ...branch,
            branch_key: "comparison-angle",
          })),
        };
        const validComparison = subject.normalizeResearchStageControl(
          comparison, runId,
        );
        const comparisonMarkup = subject.researchStageControlMarkup(
          validComparison,
        );
        const comparisonGuidance = subject.normalizeResearchStageControl({
          ...comparison,
          guidance: {
            ...base.guidance,
            status: "branch_comparison",
            recommended_next_action: "compare_read_only_branch_with_main",
          },
        }, runId);
        const comparisonGuidanceMarkup = subject.researchStageControlMarkup(
          comparisonGuidance,
        );
        const unsafeFlags = subject.normalizeResearchStageControl({
          ...base,
          guidance: { ...base.guidance, automatic_spend: true },
        }, runId);
        const missingChild = subject.normalizeResearchStageControl({
          ...active,
          active_recompute: { ...active.active_recompute, child_run_id: null },
        }, runId);
        const wrongInvoke = subject.normalizeResearchStageControl({
          ...active,
          active_recompute: {
            ...active.active_recompute,
            invoke: { action: "analyze", research_id: runId },
          },
        }, runId);
        const wrongRun = subject.normalizeResearchStageControl(base,
          "20000000-0000-4000-8000-000000000099");
        const wrongBranchHash = subject.normalizeResearchStageControl({
          ...base,
          selected_branch: {
            ...base.selected_branch,
            branch_revision_hash: "not-a-hash",
          },
        }, runId);
        return {
          valid: valid.available,
          branchRevisionHash: valid.selectedBranch?.branchRevisionHash,
          active: validActive.available,
          activeChild: validActive.activeRecompute?.childRunId,
          activeLease: validActive.activeRecompute?.leaseExpiresAt,
          activeCanCancel: validActive.activeRecompute?.canCancel,
          activeCancelReason: validActive.activeRecompute?.cancelReason,
          activeExpectedBranchHash:
            validActive.activeRecompute?.expectedBranchRevisionHash,
          processing: validProcessing.available,
          processingLease: validProcessing.activeRecompute?.leaseExpiresAt,
          processingCanCancel: validProcessing.activeRecompute?.canCancel,
          processingExpectedBranchHash:
            validProcessing.activeRecompute?.expectedBranchRevisionHash,
          processingWithInvoke: processingWithInvoke.available,
          wrongActiveBranchHash: wrongActiveBranchHash.available,
          activeWithoutCancelAction: activeWithoutCancelAction.available,
          mainRecomputeVisible: markup.includes(
            'data-stage-control-action="recompute"',
          ),
          activeRecomputeHidden: !activeMarkup.includes(
            'data-stage-control-action="recompute"',
          ),
          activeCancelVisible: activeMarkup.includes(
            'data-stage-control-action="cancel"',
          ),
          queuedGuidanceExact:
            queuedGuidanceMarkup.includes("Возобновите этот же запуск либо отмените его")
            && queuedGuidanceMarkup.includes(
              'data-action="resume-research-stage-recompute"',
            )
            && queuedGuidanceMarkup.includes(
              'data-stage-control-action="cancel"',
            ),
          expiredGuidanceExact:
            expiredMarkup.includes("Отмените сохранённый пересчёт без повторной попытки провайдера")
            && expiredMarkup.includes('data-stage-control-action="cancel"')
            && !expiredMarkup.includes(
              'data-action="resume-research-stage-recompute"',
            ),
          activeLeaseGuidanceExact:
            activeLeaseMarkup.includes("Ждите и проверяйте статус — не запускайте повтор")
            && !activeLeaseMarkup.includes(
              'data-stage-control-action="cancel"',
            )
            && !activeLeaseMarkup.includes(
              'data-action="resume-research-stage-recompute"',
            ),
          supersededGuidanceExact:
            branchChangedMarkup.includes(
              "Завершите сохранённый запрос как superseded",
            )
            && branchChangedMarkup.includes("Завершить как superseded")
            && branchChangedMarkup.includes(
              "без нового spend или retry",
            ),
          queuedSupersededCannotResume:
            queuedBranchChangedMarkup.includes("Завершить как superseded")
            && queuedBranchChangedMarkup.includes(
              'data-stage-control-action="cancel"',
            )
            && !queuedBranchChangedMarkup.includes(
              'data-action="resume-research-stage-recompute"',
            ),
          queuedSupersededWithInvoke:
            queuedBranchChangedWithInvoke.available,
          processingCancelHidden: !processingMarkup.includes(
            'data-stage-control-action="cancel"',
          ),
          approvedGuidanceExact:
            approvedMismatchMarkup.includes(
              "Утверждённый main-снимок остаётся неизменным",
            )
            && approvedLockedMarkup.includes(
              "ветку только для сравнения снимка",
            )
            && noneditableMarkup.includes(
              "ветку создавайте только как снимок для чтения",
            ),
          comparison: validComparison.available,
          comparisonReadOnly: comparisonMarkup.includes(
            "Ветка сравнения — только чтение.",
          ) && comparisonMarkup.includes("readonly"),
          comparisonHasNoMutation: !comparisonMarkup.includes(
            "data-stage-control-action=",
          ),
          comparisonMakesNoMergePromise:
            !comparisonMarkup.toLowerCase().includes("merge")
            && !comparisonMarkup.toLowerCase().includes("promote")
            && comparisonMarkup.includes("нельзя править, пересчитывать, утверждать или переносить обратно"),
          comparisonGuidanceExact:
            comparisonGuidanceMarkup.includes(
              "ветка сравнения · только чтение",
            )
            && comparisonGuidanceMarkup.includes(
              "переноса или автоматической замены результата нет",
            ),
          unsafeFlags: unsafeFlags.available,
          missingChild: missingChild.available,
          wrongInvoke: wrongInvoke.available,
          wrongRun: wrongRun.available,
          wrongBranchHash: wrongBranchHash.available,
          escaped: markup.includes("&lt;script&gt;unsafe payload&lt;/script&gt;")
            && !markup.includes("<script>unsafe payload</script>"),
          payloadNotInData: !markup.includes('data-payload='),
          exactData: markup.includes('data-head-event-id="40000000-0000-4000-8000-000000000001"')
            && markup.includes('data-artifact-id="50000000-0000-4000-8000-000000000001"')
            && markup.includes(`data-content-hash="${"a".repeat(64)}"`)
            && markup.includes(`data-branch-revision-hash="${branchRevisionHash}"`),
        };
        """,
    )

    assert result == {
        "valid": True,
        "branchRevisionHash": "c" * 64,
        "active": True,
        "activeChild": "80000000-0000-4000-8000-000000000001",
        "activeLease": "",
        "activeCanCancel": True,
        "activeCancelReason": "saved_before_provider_claim",
        "activeExpectedBranchHash": "c" * 64,
        "processing": True,
        "processingLease": "2026-08-03T10:05:00Z",
        "processingCanCancel": False,
        "processingExpectedBranchHash": "c" * 64,
        "processingWithInvoke": False,
        "wrongActiveBranchHash": False,
        "activeWithoutCancelAction": False,
        "mainRecomputeVisible": True,
        "activeRecomputeHidden": True,
        "activeCancelVisible": True,
        "queuedGuidanceExact": True,
        "expiredGuidanceExact": True,
        "activeLeaseGuidanceExact": True,
        "supersededGuidanceExact": True,
        "queuedSupersededCannotResume": True,
        "queuedSupersededWithInvoke": False,
        "processingCancelHidden": True,
        "approvedGuidanceExact": True,
        "comparison": True,
        "comparisonReadOnly": True,
        "comparisonHasNoMutation": True,
        "comparisonMakesNoMergePromise": True,
        "comparisonGuidanceExact": True,
        "unsafeFlags": False,
        "missingChild": False,
        "wrongInvoke": False,
        "wrongRun": False,
        "wrongBranchHash": False,
        "escaped": True,
        "payloadNotInData": True,
        "exactData": True,
    }


def test_api_sends_branch_revision_for_every_action_and_cancel_never_invokes_edge() -> None:
    result = _run_module(
        API_PATH,
        """
        const runId = "20000000-0000-4000-8000-000000000001";
        const projectId = "90000000-0000-4000-8000-000000000001";
        const branchId = "30000000-0000-4000-8000-000000000001";
        const branchRevisionHash = "c".repeat(64);
        const eventId = "40000000-0000-4000-8000-000000000001";
        const artifactId = "50000000-0000-4000-8000-000000000001";
        const requestId = "70000000-0000-4000-8000-000000000001";
        const childRunId = "80000000-0000-4000-8000-000000000001";
        const calls = [];
        const api = Object.create(subject.CreatorApi.prototype);
        api.organizationId = "10000000-0000-4000-8000-000000000001";
        api.researchRecomputeInvocations = new Set();
        api.call = async (rpc, payload) => {
          calls.push({ kind: "call", rpc, payload });
          return { ok: true };
        };
        api.mutate = async (rpc, payload) => {
          calls.push({ kind: "mutate", rpc, payload });
          return {
            ok: true,
            action: payload.action,
            recompute_request: payload.action === "recompute" ? {
              request_id: requestId,
              child_run_id: childRunId,
              status: "queued",
              paid_analysis_ack: true,
              provider_key: "openai_web_search",
              adapter_version: "research-stage-recompute-v1",
              max_provider_attempts: 1,
              automatic_provider_action: false,
              invoke: {
                action: "analyze",
                research_id: childRunId,
                project_id: projectId,
              },
            } : null,
          };
        };
        api.invokeProductResearch = async (payload) => {
          calls.push({ kind: "invoke", payload });
          return { accepted: true };
        };
        await api.researchStageControlStatus(runId, {
          project_id: projectId,
          branch_id: branchId,
          history_limit: 30,
        });
        const common = {
          project_id: projectId,
          branch_id: branchId,
          stage: "category",
          expected_head_event_id: eventId,
          expected_artifact_id: artifactId,
          expected_content_hash: "a".repeat(64),
          expected_branch_revision_hash: branchRevisionHash,
          confirmation: true,
          reason: "Exercise exact browser stage contract",
        };
        await api.controlResearchStage(runId, {
          ...common,
          action: "patch",
          replacement: { category_name: "Corrected category" },
          user_input: "Use the corrected category boundary",
        });
        await api.controlResearchStage(runId, {
          ...common,
          action: "reject",
        });
        await api.controlResearchStage(runId, {
          ...common,
          action: "revert",
          target_artifact_id: "50000000-0000-4000-8000-000000000099",
        });
        await api.controlResearchStage(runId, {
          ...common,
          action: "fork",
          new_branch_key: "comparison-angle",
        });
        const first = await api.controlResearchStage(runId, {
          ...common,
          action: "recompute",
          user_input: "Re-check the category with fresh public evidence",
          paid_analysis_ack: true,
        });
        const replay = await api.controlResearchStage(runId, {
          ...common,
          action: "recompute",
          user_input: "Re-check the category with fresh public evidence",
          paid_analysis_ack: true,
        });
        await api.controlResearchStage(runId, {
          ...common,
          action: "cancel",
        });
        const rejected = [];
        for (const candidate of [
          { ...common, action: "patch", replacement: {}, user_input: "ok", confirmation: false },
          { ...common, action: "recompute", user_input: "Re-check evidence", paid_analysis_ack: false },
          { ...common, action: "recompute", stage: "sources", user_input: "Re-check evidence", paid_analysis_ack: true },
          { ...common, action: "cancel", expected_branch_revision_hash: "bad" },
        ]) {
          try { await api.controlResearchStage(runId, candidate); }
          catch (error) { rejected.push(error.code); }
        }
        return {
          calls,
          firstAccepted: first.analysis_request?.accepted,
          replaySkipped: replay.analysis_request?.skipped,
          replayReason: replay.analysis_request?.reason,
          rejected,
        };
        """,
    )

    status_calls = [item for item in result["calls"] if item["kind"] == "call"]
    mutate_calls = [item for item in result["calls"] if item["kind"] == "mutate"]
    invoke_calls = [item for item in result["calls"] if item["kind"] == "invoke"]
    assert status_calls == [{
        "kind": "call",
        "rpc": "creator_research_stage_control_status",
        "payload": {
            "run_id": "20000000-0000-4000-8000-000000000001",
            "project_id": "90000000-0000-4000-8000-000000000001",
            "branch_id": "30000000-0000-4000-8000-000000000001",
            "history_limit": 30,
            "organization_id": "10000000-0000-4000-8000-000000000001",
        },
    }]
    assert [item["payload"]["action"] for item in mutate_calls] == [
        "patch", "reject", "revert", "fork", "recompute", "recompute", "cancel"
    ]
    assert all(item["payload"]["confirmation"] is True for item in mutate_calls)
    assert all(
        item["payload"]["expected_branch_revision_hash"] == "c" * 64
        for item in mutate_calls
    )
    assert invoke_calls == [{
        "kind": "invoke",
        "payload": {
            "action": "analyze",
            "research_id": "80000000-0000-4000-8000-000000000001",
            "project_id": "90000000-0000-4000-8000-000000000001",
        },
    }]
    assert result["firstAccepted"] is True
    assert result["replaySkipped"] is True
    assert result["replayReason"] == "recompute_invoke_already_attempted"
    assert result["rejected"] == [
        "research_stage_control_invalid",
        "research_stage_recompute_invalid",
        "research_stage_recompute_invalid",
        "research_stage_control_invalid",
    ]
