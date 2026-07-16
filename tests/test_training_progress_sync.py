from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
INTERACTIVE = (
    ROOT / "web" / "app" / "training-interactive.js"
).read_text(encoding="utf-8")
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607160005_operational_workspace_foundation.sql"
).read_text(encoding="utf-8")


def test_walkthrough_markup_exposes_stable_server_validated_identifiers() -> None:
    assert 'data-training-frame-id="${escapeHtml(frame.id)}"' in INTERACTIVE
    assert (
        'data-training-duration-seconds="${walkthrough.durationSeconds}"'
        in INTERACTIVE
    )
    assert "walkthrough.value ->> 'id' = walkthrough_id_value" in MIGRATION
    assert "training_current_frame_unknown" in MIGRATION


def test_course_restores_server_progress_after_local_fast_path() -> None:
    local_restore = APP.index("restoreTrainingWalkthroughState(course.code)")
    server_restore = APP.index("restoreServerTrainingWalkthroughState(course.code)")
    assert local_restore < server_restore
    assert "state.api.trainingProgress(moduleCode)" in APP
    assert "applyServerTrainingProgress(progress)" in APP
    assert "current_frame_id" in APP
    assert "position_seconds" in APP
    assert "completed_frame_ids" in APP


def test_walkthrough_changes_use_a_serialized_coalescing_save_queue() -> None:
    assert "scheduleServerTrainingWalkthroughProgress(root)" in APP
    assert "state.trainingProgress.saveTimers" in APP
    assert "state.trainingProgress.saveQueues" in APP
    assert "mergeTrainingProgressPayload" in APP
    assert "drainTrainingProgressSaveQueue" in APP
    assert "queue.inFlight" in APP
    assert "queue.latestPayload" in APP
    assert "state.api.saveTrainingProgress(requestPayload)" in APP
    expected_version = APP.index(
        "if (current?.version) requestPayload.expected_version = current.version"
    )
    save_call = APP.index("state.api.saveTrainingProgress(requestPayload)")
    assert expected_version < save_call
    assert "training_progress_version_conflict" in APP
    assert "refreshTrainingProgressVersion(queue)" in APP
    assert "conflictRetries >= 2" in APP
    assert "error?.serverCode || error?.code" in APP
    assert "this.serverCode =" in API
    assert "payload.expected_version = expectedVersion" in API


def test_server_restore_never_rolls_back_newer_local_walkthrough_state() -> None:
    assert "Math.max(localIndex, serverIndex)" in APP
    assert (
        "video.currentTime = Math.max(Number(video.currentTime) || 0, serverPosition)"
        in APP
    )
    assert "!queue?.inFlight && !queue?.latestPayload" in APP


def test_logout_cancels_pending_training_progress_work() -> None:
    clear = APP.split("function clearAuthenticatedState()", 1)[1]
    assert "window.clearTimeout(timer)" in clear
    assert "state.trainingProgress.items.clear()" in clear
    assert "state.trainingProgress.loadedModules.clear()" in clear
    assert "state.trainingProgress.saveTimers.clear()" in clear
    assert "state.trainingProgress.saveQueues.clear()" in clear
