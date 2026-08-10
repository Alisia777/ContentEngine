import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
CSS = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")


def _function(name: str, next_name: str) -> str:
    start = APP.index(f"function {name}")
    end = APP.index(f"function {next_name}", start)
    return APP[start:end]


def test_active_paid_jobs_poll_every_seven_seconds_across_visible_workspace_routes() -> None:
    assert "const REAL_GENERATION_POLL_INTERVAL_MS = 7_000" in APP
    assert "REAL_GENERATION_ACTIVE_STATUSES.has(details.status)" in APP

    events = _function("bindGlobalEvents", "normalizeGenerationResearchPresetEvent")
    jobs = _function("realGenerationJobsFromBatches", "realGenerationReconciliationJobsFromBatches")
    schedule = _function("scheduleRealGenerationPolling", "runRealGenerationPolling")
    polling = _function("runRealGenerationPolling", "requestRealGenerationStatus")
    assert events.count("scheduleRealGenerationPolling(250)") >= 2
    assert "details.real" in jobs
    assert "state.realGenerationResults.entries()" in jobs
    assert "cachedProjectId !== projectId" in jobs
    assert "normalizeBoolean(job.reconciliation_required)" in jobs
    assert "REAL_GENERATION_ACTIVE_STATUSES.has(status)" in jobs
    assert 'document.visibilityState !== "visible"' in schedule
    assert 'state.route.path !== "/workspace/generation"' not in schedule
    assert 'state.route.path !== "/workspace/generation"' not in polling
    assert 'if (state.route.path !== "/workspace/generation") stopRealGenerationPolling();' not in APP
    assert "waitForRealGenerationStatus" in polling
    assert "startRealGeneration" not in polling
    assert "Promise.allSettled" in polling


def test_cached_files_reread_registered_output_after_background_real_generation_success() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the paid-generation UI contract"
    invalidate = _function(
        "invalidateGeneratedMediaWorkspaceCaches",
        "applyRealGenerationResult",
    )
    apply_result = _function(
        "applyRealGenerationResult",
        "applyRealGenerationStatusError",
    )
    script = f"{invalidate}\n{apply_result}\n" + r"""
const projectId = "11111111-1111-4111-8111-111111111111";
const jobId = "22222222-2222-4222-8222-222222222222";
const outputMediaId = "33333333-3333-4333-8333-333333333333";
const state = {
  route: { path: "/workspace/board" },
  dataEpoch: 7,
  user: { id: "user-1" },
  session: { access_token: "test" },
  sections: {
    board: { requestId: 4, status: "ready", data: { media: [] }, error: null },
    media: { requestId: 2, status: "ready", data: { media: [] }, error: null },
    review: { requestId: 3, status: "ready", data: { runs: [] }, error: null },
    generation: {
      data: {
        batches: [{
          mode: "real",
          status: "queued",
          parameters: { mode: "real", job_id: jobId, job_status: "queued" },
        }],
      },
    },
  },
  realGenerationResults: new Map([[
    jobId,
    { projectId, job: { id: jobId, status: "queued", model: "seedream5_lite" } },
  ]]),
};
const window = { queueMicrotask };
let filesRereads = 0;
let spendRefreshes = 0;

function currentWorkspaceProjectId() { return projectId; }
function isTrustedGenerationDownload() { return false; }
function normalizeBoolean(value) { return value === true; }
function contentReviewUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(String(value || ""));
}
function patchGenerationBatch(id, job) {
  const batch = state.sections.generation.data.batches.find(
    (item) => item.parameters.job_id === id,
  );
  batch.status = job.status;
  batch.parameters.job_status = job.status;
  batch.parameters.output_media_id = job.output_media_id;
}
function loadGenerationSpendOverview() { spendRefreshes += 1; return Promise.resolve(); }
function toast() {}
function generationFailureMessage() { return "failed"; }
function scheduleGeneratedVideoTechnicalQa() {}
function render() {}
async function loadSection(section, options) {
  if (section !== "board" || options?.silent !== true) throw new Error("unexpected reread");
  filesRereads += 1;
  const target = state.sections[section];
  const requestId = target.requestId + 1;
  target.requestId = requestId;
  target.status = target.data ? "refreshing" : "loading";
  await Promise.resolve();
  if (requestId !== target.requestId) return;
  target.data = { media: [{ id: outputMediaId }] };
  target.status = "ready";
}

const succeededResult = {
  job: {
    id: jobId,
    project_id: projectId,
    status: "succeeded",
    model: "seedream5_lite",
    output_media_id: outputMediaId,
  },
};
applyRealGenerationResult(jobId, succeededResult, { source: "auto", projectId });
applyRealGenerationResult(jobId, succeededResult, { source: "auto", projectId });

await new Promise((resolve) => setTimeout(resolve, 0));
console.log(JSON.stringify({
  filesRereads,
  spendRefreshes,
  boardStatus: state.sections.board.status,
  mediaStatus: state.sections.media.status,
  reviewStatus: state.sections.review.status,
  outputVisible: state.sections.board.data.media.some((item) => item.id === outputMediaId),
}));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "filesRereads": 1,
        "spendRefreshes": 1,
        "boardStatus": "ready",
        "mediaStatus": "idle",
        "reviewStatus": "idle",
        "outputVisible": True,
    }


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


def test_failed_jobs_are_visually_distinguishable_and_manual_intent_is_preserved() -> None:
    assert "details.jobId.slice(0, 8)" in APP
    assert "formatDate(item.created_at, true)" in APP
    assert "Ваш замысел ролика" in APP
    assert "Ваш замысел кадра" in APP
    assert "Ваш замысел анимации" in APP
    assert "не меняя сюжет" in APP
    assert "Проверить мой замысел и подготовить ТЗ" not in APP
    assert "Портал сам подготовит техническое ТЗ при запуске" in APP
    assert 'textarea name="brief" rows="8"' in APP
    assert "Ваш замысел сохранён" in APP
    assert "Портал сохранит ваш замысел" in APP
    assert "form.elements.brief.value = spec.editable_intent" in APP
    assert "form.elements.brief.value = spec.compiled_prompt" not in APP


def test_paid_generation_has_five_explicit_progress_stages() -> None:
    for label in ("Принято", "В очереди", "Создаётся", "Сохраняется", "Готово"):
        assert label in APP
    assert "repeat(5, minmax(86px, 1fr))" in CSS
    assert ".generation-stage" in CSS
    assert ".generation-cost" in CSS


def test_ready_video_has_inline_preview_and_fresh_download_actions() -> None:
    for token in (
        'data-output-action="preview"',
        'data-output-action="download"',
        "generation-result-preview",
        "downloadGenerationOutput",
        "trustedCachedGenerationUrl",
    ):
        assert token in APP
    assert 'data-output-action="open"' not in APP
    assert "openGenerationWaitingWindow" not in APP
    assert "window.open" not in APP
    assert "state.api.realGenerationStatus" in APP
    assert "link.download" in APP
    assert "await fetch(url" in APP
    assert "URL.createObjectURL" in APP
    assert "URL.revokeObjectURL" in APP
    download = APP[
        APP.index("async function downloadGenerationOutput") :
        APP.index("function canDecideContentReview")
    ]
    assert 'link.target = "_blank"' not in download
    assert ".generation-result-preview video" in CSS


def test_second_variant_restores_fields_but_requires_new_price_confirmation() -> None:
    restore = _function("restoreRealGenerationDraft", "downloadGenerationOutput")
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
