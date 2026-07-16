from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607160004_real_generation_reconciliation.sql"
)
PGTAP_TEST = (
    ROOT
    / "supabase/tests/real_generation_reconciliation_test.sql"
)
EDGE_PATH = ROOT / "supabase/functions/creator-generate/index.ts"
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
PGTAP = PGTAP_TEST.read_text(encoding="utf-8").casefold()
EDGE = EDGE_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
CSS = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _function(name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{name}"
        rf"\s*\(\s*p_payload\s+jsonb[^)]*\)\s*returns\s+jsonb"
        rf"(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, f"missing {name}(jsonb)"
    return match.group("header").casefold(), match.group("body").casefold()


def _edge_between(start: str, end: str) -> str:
    start_at = EDGE.index(start)
    return EDGE[start_at : EDGE.index(end, start_at)]


def test_migration_is_atomic_and_ordered_after_content_review() -> None:
    assert MIGRATION.name == "202607160004_real_generation_reconciliation.sql"
    assert (
        ROOT / "supabase/migrations/202607160003_content_review_pipeline.sql"
    ).exists()
    assert LOWER.startswith("begin;")
    assert LOWER.rstrip().endswith("commit;")


def test_browser_context_is_manager_only_and_system_writes_are_service_only() -> None:
    context_header, context_body = _function(
        "creator_real_generation_reconciliation_context"
    )
    assert "security definer" in context_header
    assert "set search_path = ''" in context_header
    assert "current_profile_id()" in context_body
    assert "resolve_organization(p_payload)" in context_body
    assert "array['owner', 'admin']" in context_body
    assert "real_generation_reconciliation_not_required" in context_body

    assert re.search(
        r"revoke\s+all\s+on\s+function\s+public\."
        r"creator_real_generation_reconciliation_context\(jsonb\)"
        r"\s+from\s+public\s*,\s*anon",
        LOWER,
    )
    assert re.search(
        r"grant\s+execute\s+on\s+function\s+public\."
        r"creator_real_generation_reconciliation_context\(jsonb\)"
        r"\s+to\s+authenticated",
        LOWER,
    )

    for name in (
        "system_mark_real_generation_reconciliation_required",
        "system_reconcile_real_generation",
    ):
        header, _ = _function(name)
        assert "security definer" in header
        assert "set search_path = ''" in header
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+public\.{name}\(jsonb\)"
            rf"\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
            LOWER,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{name}\(jsonb\)"
            rf"\s+to\s+service_role",
            LOWER,
        )


def test_ambiguous_submission_is_durably_marked_without_releasing_spend() -> None:
    _, body = _function(
        "system_mark_real_generation_reconciliation_required"
    )
    for reason in (
        "provider_create_timeout",
        "provider_create_http_unknown",
        "provider_create_response_unknown",
        "provider_create_state_stale",
    ):
        assert reason in body

    assert "for update" in body
    assert "job_row.status <> 'starting'" in body
    assert "job_row.actual_cost_minor <> 0" in body
    assert "starting_at_value > now() - interval '90 seconds'" in body
    assert "'submission_state', 'unknown'" in body
    assert "'reconciliation_required', true" in body
    assert "'reconciliation_incident_id', incident_id_value" in body
    assert "'generation_status', 'starting'" in body
    assert "'automatic_provider_retry_allowed', false" in body
    assert "real_generation_reconciliation_required" in body
    assert "set status = 'failed'" not in body
    assert "set status = 'queued'" not in body
    assert "batch_row.input ->> 'job_id' is distinct from job_row.id::text" in body
    assert "task_row.assignee_id is distinct from job_row.assigned_to" in body


def test_unresolved_incident_authoritatively_freezes_new_paid_jobs() -> None:
    start = LOWER.index(
        "create or replace function content_factory_private."
        "guard_real_generation_reconciliation_freeze()"
    )
    end = LOWER.index(
        "create or replace function public."
        "system_mark_real_generation_reconciliation_required",
        start,
    )
    freeze = LOWER[start:end]

    assert "security definer" in freeze
    assert "set search_path = ''" in freeze
    assert "real_generation_reconciliation_unresolved" in freeze
    assert "pg_advisory_xact_lock" in freeze
    assert "real_generation_quota:organization" in freeze
    assert "real_generation_reconciliation_required" in freeze
    assert (
        "content_factory_private.real_generation_reconciliation_unresolved("
        in freeze
    )
    assert "before insert or update of mode, allow_real_spend" in freeze
    assert LOWER.count("hashtext('real_generation_quota:organization')") >= 3

    edge_start = EDGE.index(
        "const { data: startData, error: startError }"
    )
    edge_end = EDGE.index("const startJob = readStartJob", edge_start)
    edge_start_error = EDGE[edge_start:edge_end]
    assert (
        'startError.message === "real_generation_reconciliation_required"'
        in edge_start_error
    )
    assert '"real_generation_reconciliation_required"' in edge_start_error
    assert "code === \"generation_rejected\" ? 403 : 409" in edge_start_error

    for token in (
        "real_generation_reconciliation_required",
        "real_generation_reconciliation_task_time_mismatch",
        "real_generation_reconciliation_already_resolved",
        "confirm_no_submission",
        "attach_existing_task",
        "to_jsonb('false'::text)",
        "automatic_provider_retry_used",
        "does not freeze another",
        "cannot release another unresolved incident",
        "leaves no partial generation batch",
        "leaves no partial review task",
    ):
        assert token in PGTAP


def test_unresolved_job_cannot_escape_through_legacy_state_updates() -> None:
    start = LOWER.index(
        "create or replace function content_factory_private."
        "guard_real_generation_reconciliation_transition()"
    )
    end = LOWER.index(
        "create or replace function public."
        "system_mark_real_generation_reconciliation_required",
        start,
    )
    guard = LOWER[start:end]

    for token in (
        "security definer",
        "real_generation_reconciliation_unresolved",
        "new.status = 'starting'",
        "new.actual_cost_minor = 0",
        "is distinct from 'true'::jsonb",
        "content_factory_private.json_hash",
        "membership.role in ('owner', 'admin')",
        "resolution_value = 'attach_existing_task'",
        "new.status = 'submitted'",
        "resolution_value = 'confirm_no_submission'",
        "new.status = 'failed'",
        "real_generation_reconciliation_required",
        "before update on content_factory.generation_jobs",
    ):
        assert token in guard

    for token in (
        "system_update_real_generation",
        "legacy provider updater cannot bypass",
        "leaves the job reconcilable and frozen",
        "malformed unresolved marker cannot be cleared",
        "status surfaces a malformed fail-closed marker as unresolved",
        "reconciliation normalizes the malformed marker",
        "b_generation_jobs_reconciliation_transition_guard",
    ):
        assert token in PGTAP


def test_mark_and_reconcile_take_org_lock_before_job_row_lock() -> None:
    for name in (
        "system_mark_real_generation_reconciliation_required",
        "system_reconcile_real_generation",
    ):
        _, body = _function(name)
        advisory = body.index("pg_advisory_xact_lock")
        row_lock = body.index("for update")
        assert "select job.organization_id into organization_id_value" in body
        assert advisory < row_lock


def test_manual_resolution_is_locked_idempotent_and_revalidates_actor() -> None:
    _, body = _function("system_reconcile_real_generation")
    for token in (
        "for update",
        "membership.status = 'active'",
        "membership.role in ('owner', 'admin')",
        "profile.status = 'active'",
        "real_generation_reconciliation_incident_mismatch",
        "content_factory_private.json_hash",
        "content_factory_private.begin_command",
        "content_factory_private.finish_command",
        "real_generation_reconciliation_already_resolved",
        "real_generation_review_task_invalid",
    ):
        assert token in body

    assert body.count("for update") >= 3
    assert "real_generation_reconciliation_unresolved" in body
    assert "jsonb_set(" in body
    assert "'{reconciliation_required}'" in body
    assert "job_row.output ->> 'reconciliation_incident_id'" in body
    assert "is distinct from incident_id_value::text" in body
    assert "batch_row.input ->> 'job_id' is distinct from job_row.id::text" in body
    assert "task_row.id::text is distinct from job_row.input ->> 'review_task_id'" in body


def test_attach_resolution_accepts_only_a_time_bound_verified_provider_task() -> None:
    _, body = _function("system_reconcile_real_generation")
    attach = body[
        body.index("if resolution_value = 'attach_existing_task'") :
    ]
    for token in (
        "'pending', 'throttled', 'running', 'succeeded'",
        "'failed', 'canceled', 'cancelled'",
        "provider_task_created_at_value < starting_at_value - interval '2 minutes'",
        "provider_task_created_at_value > starting_at_value + interval '10 minutes'",
        "provider_task_created_at_value > now() + interval '1 minute'",
        "set status = 'submitted'",
        "actual_cost_minor = job.estimated_cost_minor",
        "'submission_state', 'confirmed_submitted'",
        "'reconciliation_required', false",
        "set status = 'submitted'",
    ):
        assert token in attach

    assert "'provider_task_id', provider_task_id_value" in attach
    assert "'provider_task_created_at', provider_task_created_at_value" in attach
    assert "'provider_status_at_reconciliation', provider_status_value" in attach


def test_no_submission_resolution_waits_and_fails_at_zero_cost() -> None:
    _, body = _function("system_reconcile_real_generation")
    assert (
        "required_at_value > now() - interval '2 minutes'" in body
    )
    assert "real_generation_reconciliation_wait_required" in body
    assert "real_generation_reconciliation_no_submission_invalid" in body
    assert "set status = 'failed'" in body
    assert "actual_cost_minor = 0" in body
    assert "'failure_code', 'provider_submission_not_found'" in body
    assert "'submission_state', 'confirmed_not_submitted'" in body
    assert "set status = 'cancelled'" in body
    assert "'automatic_provider_retry_used', false" in body


def test_status_exposes_incident_but_only_owner_admin_can_resolve_it() -> None:
    _, body = _function("creator_real_generation_status")
    for field in (
        "'submission_state'",
        "'reconciliation_required'",
        "'reconciliation_incident_id'",
        "'reconciliation_required_at'",
        "'reconciliation_reason_code'",
        "'reconciliation_resolution'",
        "'can_reconcile'",
    ):
        assert field in body
    assert "actor_role in ('owner', 'admin')" in body
    assert "job_row.status = 'starting'" in body


def test_edge_marks_every_ambiguous_create_outcome_and_never_reposts() -> None:
    create = _edge_between(
        '`${RUNWAY_API_ORIGIN}/v1/image_to_video`',
        "const submittedPayload",
    )
    assert EDGE.count('`${RUNWAY_API_ORIGIN}/v1/image_to_video`') == 1
    assert create.count("markReconciliationRequired(") == 4
    for reason in (
        "provider_create_timeout",
        "provider_create_http_unknown",
        "provider_create_response_unknown",
    ):
        assert f'"{reason}"' in create
    assert "DEFINITIVE_CREATE_HTTP_STATUSES.has(createResponse.status)" in create
    assert create.count("respondProviderUnavailable(") == 4

    reconciliation = _edge_between(
        "const handleReconciliation",
        "const reconcilePayload",
    )
    assert "/v1/image_to_video" not in reconciliation
    assert 'method: "GET"' in reconciliation


def test_edge_stops_blind_waiting_and_server_verifies_the_manual_task() -> None:
    status = _edge_between("const handleStatus", "const statusPayload")
    assert "STARTING_RECONCILIATION_AFTER_MS = 90_000" in EDGE
    assert "provider_create_state_stale" in status
    assert "markReconciliationRequired(" in status

    reconciliation = _edge_between(
        "const handleReconciliation",
        "const reconcilePayload",
    )
    for token in (
        '`${RUNWAY_API_ORIGIN}/v1/tasks/${payload.provider_task_id}`',
        "parseRunwayTask(providerValue)",
        "providerTask.id !== payload.provider_task_id",
        "RECONCILIATION_TASK_EARLY_SKEW_MS",
        "RECONCILIATION_TASK_LATE_SKEW_MS",
        "generation_reconciliation_task_mismatch",
        "generation_reconciliation_wait_required",
    ):
        assert token in reconciliation
    assert "providerCreatedAt > Date.now() + 60_000" in reconciliation
    assert "systemPayload.provider_task_id = providerTask.id" in reconciliation
    assert (
        "systemPayload.provider_task_created_at = providerTask.createdAt"
        in reconciliation
    )


def test_edge_requires_explicit_confirmation_and_returns_only_safe_state() -> None:
    reader = _edge_between(
        "function readReconcilePayload",
        "function rpcPayload",
    )
    assert '"RUNWAY_TASK_ID_VERIFIED"' in reader
    assert '"RUNWAY_NO_TASK_VERIFIED"' in reader
    assert "isBoundedText(value.evidence_reference, 8, 500)" in reader
    assert "isBoundedText(value.reason, 20, 1_000)" in reader

    for field in (
        "submission_state",
        "reconciliation_required",
        "reconciliation_incident_id",
        "reconciliation_required_at",
        "reconciliation_reason_code",
        "reconciliation_resolution",
        "can_reconcile",
    ):
        assert field in EDGE
    assert '"system_reconcile_real_generation"' in EDGE
    assert '"creator_real_generation_reconciliation_context"' in EDGE
    assert "providerValue.error" not in EDGE
    assert "providerValue.failure" not in EDGE


def test_browser_adapter_validates_and_idempotently_sends_manual_resolution() -> None:
    start = API.index("  reconcileRealGeneration(jobId, details = {})")
    end = API.index("  async invokeRealGeneration", start)
    reconcile = API[start:end]
    for token in (
        "generation_reconciliation_incident_invalid",
        "generation_reconciliation_resolution_invalid",
        "generation_reconciliation_evidence_invalid",
        "generation_reconciliation_task_id_invalid",
        '"RUNWAY_TASK_ID_VERIFIED"',
        '"RUNWAY_NO_TASK_VERIFIED"',
        'this.invokeRealGeneration("reconcile"',
    ):
        assert token in reconcile
    assert 'new Set(["start", "status", "reconcile"])' in API
    assert 'const idempotencyKey = action !== "status"' in API
    assert "this.mutationKeys[fingerprint] || crypto.randomUUID()" in API
    assert "real_generation_reconciliation_required" in API


def test_portal_stops_polling_and_hides_repeat_while_incident_is_open() -> None:
    polling_start = APP.index("function realGenerationJobsFromBatches")
    polling_end = APP.index("function stopRealGenerationPolling", polling_start)
    polling = APP[polling_start:polling_end]
    assert "&& !details.reconciliationRequired" in polling
    assert "realGenerationReconciliationJobsFromBatches" in polling

    repeat_start = APP.index("function canRepeatRealGeneration")
    repeat_end = APP.index("function stopRealGenerationPolling", repeat_start)
    repeat = APP[repeat_start:repeat_end]
    assert "!details.reconciliationRequired" in repeat
    assert '"succeeded", "completed", "failed", "cancelled"' in repeat
    assert "canRepeatRealGeneration(state.lastRealGenerationJobId)" in APP


def test_portal_requires_explicit_evidence_before_manual_resolution() -> None:
    actions_start = APP.index("function generationActionsMarkup")
    actions_end = APP.index("function generationCostMarkup", actions_start)
    actions = APP[actions_start:actions_end]
    for token in (
        'class="generation-reconciliation-form"',
        'name="provider_task_id"',
        'name="evidence_reference"',
        'name="reason"',
        'name="manual_confirmation"',
        'value="attach_existing_task"',
        'value="confirm_no_submission"',
        "портал не повторяет платный POST автоматически",
    ):
        assert token in actions

    submit_start = APP.index(
        "async function submitRealGenerationReconciliation"
    )
    submit_end = APP.index(
        "async function submitRealGeneration(form",
        submit_start,
    )
    submit = APP[submit_start:submit_end]
    assert '["owner", "admin"]' in submit
    assert 'values.get("manual_confirmation") !== "confirmed"' in submit
    assert "state.api.reconcileRealGeneration" in submit
    assert "applyRealGenerationResult" in submit
    assert "scheduleRealGenerationPolling(500)" in submit

    for selector in (
        ".generation-reconciliation-readonly",
        ".generation-reconciliation-form",
        ".generation-reconciliation-confirmation",
        ".generation-reconciliation-note",
    ):
        assert selector in CSS
