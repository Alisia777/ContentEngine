from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
CSS = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _function(name: str, next_name: str) -> str:
    start = APP.index(f"function {name}")
    end = APP.index(f"function {next_name}", start)
    return APP[start:end]


def test_active_paid_jobs_poll_every_seven_seconds_only_in_visible_generation_view() -> None:
    assert "const REAL_GENERATION_POLL_INTERVAL_MS = 7_000" in APP
    assert 'document.visibilityState !== "visible"' in APP
    assert 'state.route.path !== "/workspace/generation"' in APP
    assert "REAL_GENERATION_ACTIVE_STATUSES.has(details.status)" in APP

    polling = _function("runRealGenerationPolling", "requestRealGenerationStatus")
    assert "waitForRealGenerationStatus" in polling
    assert "startRealGeneration" not in polling
    assert "Promise.allSettled" in polling


def test_status_requests_have_a_soft_timeout_and_are_reused_while_still_running() -> None:
    request = _function("requestRealGenerationStatus", "waitForRealGenerationStatus")
    assert "state.realGenerationStatusRequests.get" in request
    assert "if (existing?.promise) return existing.promise" in request
    assert "state.api.realGenerationStatus" in request

    timeout = _function("withSoftTimeoutResult", "applyRealGenerationResult")
    assert "Promise.race" in timeout
    assert "timedOut: true" in timeout
    assert "AbortController" not in timeout


def test_ambiguous_start_is_never_automatically_repeated() -> None:
    submit = APP[APP.index("async function submitRealGeneration"):APP.index("async function submitMockBatch")]
    assert "const startRequest = state.api.startRealGeneration(payload)" in submit
    assert submit.count("state.api.startRealGeneration(payload)") == 1
    assert "result = await startRequest" in submit
    assert "не создавайте дубликат" in submit
    assert "real_spend_confirmation.checked = false" in submit


def test_queue_explains_stages_reconciliation_cost_and_safe_failures() -> None:
    for token in (
        "generation-stage",
        "generation-reconcile-warning",
        "generation-failure",
        "estimated_cost_minor",
        "actual_cost_minor",
        "failure_code",
        "provider_credits_unavailable",
        "output_upload_failed",
    ):
        assert token in APP
    assert "Не запускайте видео повторно" in APP


def test_paid_generation_has_five_explicit_progress_stages() -> None:
    for label in ("Принято", "В очереди", "Создаётся", "Сохраняется", "Готово"):
        assert label in APP
    assert "repeat(5, minmax(86px, 1fr))" in CSS
    assert ".generation-stage" in CSS
    assert ".generation-cost" in CSS


def test_ready_video_has_preview_and_fresh_open_download_actions() -> None:
    for token in (
        'data-output-action="preview"',
        'data-output-action="download"',
        'data-output-action="open"',
        "generation-result-preview",
        "downloadGenerationOutput",
        "openGenerationWaitingWindow",
        "trustedCachedGenerationUrl",
    ):
        assert token in APP
    assert "state.api.realGenerationStatus" in APP
    assert "link.download" in APP
    assert ".generation-result-preview video" in CSS


def test_second_variant_restores_fields_but_requires_new_price_confirmation() -> None:
    restore = _function("restoreRealGenerationDraft", "openGenerationWaitingWindow")
    assert "draft.media_ids.includes" in restore
    assert "form.elements.real_spend_confirmation.checked = false" in restore
    assert "real_spend_confirmation.checked = true" not in restore
    assert 'data-action="repeat-real-generation"' in APP
    assert ".generation-repeat-panel" in CSS


def test_adapter_preserves_only_structured_edge_job_for_reconciliation() -> None:
    constructor = API[API.index("export class CreatorApiError"):API.index("export class CreatorApi {")]
    assert 'this.job = details.job && typeof details.job === "object"' in constructor
    assert "? { ...details.job }" in constructor
    assert "provider_error" not in constructor
