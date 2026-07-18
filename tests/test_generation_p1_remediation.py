from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607180002_generation_safety_reconciliation.sql"
).read_text(encoding="utf-8")
GENERATOR = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
WORKER = (
    ROOT / "supabase/functions/creator-background-worker/index.ts"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/seedance2_fast_8s_generation_test.sql"
).read_text(encoding="utf-8")


def test_refunds_are_append_only_compensating_ledger_events() -> None:
    assert "'refunded'" in MIGRATION
    assert "committed_delta_minor = -actual_cost_minor" in MIGRATION
    assert "'provider_task_refunded'" in MIGRATION
    assert "on conflict" not in MIGRATION.split(
        "'provider_task_refunded'", maxsplit=1
    )[1].split("end if;", maxsplit=1)[0]
    assert "generation_spend_ledger_append_only_guard" not in MIGRATION


def test_runway_failure_codes_drive_refundable_vs_non_refundable() -> None:
    assert 'providerFailureCode.startsWith("SAFETY.INPUT.")' in GENERATOR
    assert '"INPUT_PREPROCESSING.SAFETY.TEXT"' in GENERATOR
    assert '"non_refundable"' in GENERATOR
    assert '"refundable"' in GENERATOR
    assert "provider_failure_code" in GENERATOR
    assert "provider_billing_outcome" in MIGRATION


def test_unknown_provider_billing_never_gets_an_optimistic_refund() -> None:
    assert 'providerFailureCode === null\n    ? "unknown"' in GENERATOR
    assert "provider_billing_outcome_unknown" in MIGRATION
    unknown_branch = MIGRATION.split(
        "billing_outcome_value = 'unknown'", maxsplit=1
    )[1].split("elsif billing_outcome_value", maxsplit=1)[0]
    assert "'refunded'" not in unknown_branch


def test_instagram_preflight_runs_before_legacy_start_and_reservation() -> None:
    rejection = MIGRATION.index("paid_generation_platform_not_supported")
    legacy_start = MIGRATION.index(
        "creator_start_real_generation_campaign_v1(\n    p_payload"
    )
    assert rejection < legacy_start
    assert "seedance-instagram-preflight-0001" in PGTAP


def test_stale_starting_watchdog_never_dispatches_creator_generate() -> None:
    assert '.in("status", ["starting", "submitted", "processing"])' in WORKER
    assert "reconcileStaleStartingJobs" in WORKER
    assert 'reason_code: "provider_create_state_stale"' in WORKER
    assert 'row.status === "submitted" || row.status === "processing"' in WORKER
    assert "staleStartingRows" not in WORKER.split(
        "const targets: DispatchTarget[]", maxsplit=1
    )[1].split("if (!(await heartbeatBackgroundWorker", maxsplit=1)[0]
    assert "status in ('starting', 'submitted', 'processing')" in MIGRATION
    assert "reconciliation_unresolved" in MIGRATION


def test_generated_media_and_review_evidence_share_storage_quota() -> None:
    assert "a_media_storage_quota_guard" in MIGRATION
    assert "a_content_review_evidence_storage_quota_guard" in MIGRATION
    assert "content_review_evidence_frames frame" in MIGRATION
    assert "107374182400" in MIGRATION
    assert "media_organization_storage_quota_exceeded" in MIGRATION


def test_paid_generation_reserves_capacity_before_provider_dispatch() -> None:
    assert "generation_storage_reservations" in MIGRATION
    assert "reserved_size_bytes bigint not null default 52428800" in MIGRATION
    assert "d_generation_storage_capacity_reservation" in MIGRATION
    assert "reserve_generation_output_capacity" in MIGRATION
    assert "reservation.status = 'active'" in MIGRATION
    assert "generation_storage_reservation_required" in MIGRATION
    assert "generation_storage_reservation_consume_required" in MIGRATION
    claim = GENERATOR.index("const claim = await claimSystemJob(current.id)")
    provider_post = GENERATOR.index(
        "`${RUNWAY_API_ORIGIN}/v1/image_to_video`", claim
    )
    assert claim < provider_post


def test_terminal_orphan_cleanup_is_durable_and_fail_closed() -> None:
    assert "generation_storage_cleanup_queue" in MIGRATION
    assert "generation_storage_cleanup_enqueue" in MIGRATION
    assert "release_capacity_after_storage_cleanup" in MIGRATION
    assert "terminal_storage_cleaned" in MIGRATION
    assert "status in ('pending', 'processing', 'completed', 'dead_letter')" in MIGRATION
    assert 'STORAGE_CLEANUP_LIMIT = 6' in WORKER
    assert '.from("generation_storage_cleanup_queue")' in WORKER
    assert '.remove([row.object_name])' in WORKER
    assert "Math.min(5, row.attempt_count + 1)" in WORKER
    assert 'status: "pending"' in WORKER
    assert 'last_error_code: "storage_cleanup_failed"' in WORKER
    assert 'status: deadLetter ? "dead_letter" : "pending"' not in WORKER
    assert "storageCleanup.failed > 0" in WORKER


def test_lost_cleanup_completion_remains_recoverable_at_retry_cap() -> None:
    assert "old.attempt_count = 5" in MIGRATION
    assert "new.attempt_count = 5" in MIGRATION
    assert "old.last_error_code is not null" in MIGRATION
    assert "Math.min(5, row.attempt_count + 1)" in WORKER
    assert 'last_error_code: "cleanup_lease_expired"' in WORKER
    assert "Number(value.attempt_count) <= 5" in WORKER
    assert "missing object or a completion-write loss" in WORKER
    assert "model a\n  -- worker crash after Storage accepted the delete" in PGTAP
    assert "lost completion is retried at the capped counter" in PGTAP


def test_health_accounts_for_evidence_retention_and_billing_unknowns() -> None:
    for token in (
        "evidence_bytes",
        "accounted_bytes",
        "retention_policy_days",
        "retention_due_count",
        "manual_review_required",
        "unknown_failure_outcomes",
        "active_reservation_count",
        "active_reserved_bytes",
        "cleanup_pending",
        "cleanup_processing",
        "cleanup_dead_letter",
    ):
        assert token in MIGRATION


def test_pgtap_covers_both_provider_billing_outcomes() -> None:
    assert "INTERNAL.BAD_OUTPUT.01" in PGTAP
    assert "SAFETY.INPUT.TEXT" in PGTAP
    assert "committed_delta_minor = -232" in PGTAP
    assert "event_type = 'refunded'" in PGTAP
    assert "event_type = 'refunded'" in PGTAP.split(
        "SAFETY.INPUT failure", maxsplit=1
    )[0]
