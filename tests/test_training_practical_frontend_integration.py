from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
PRACTICAL_VIEW = (ROOT / "web/app/training-practical-review.js").read_text(encoding="utf-8")


def test_practical_project_is_a_real_gate_not_a_click_through_step() -> None:
    assert "function practicalProjectApproved()" in APP
    assert "practicalProjectApproved() &&" in APP
    assert "if (!practicalProjectApproved())" in APP
    assert 'href="#/learn/practical"' in APP
    assert "Одних кликов и правильных ответов недостаточно" in APP


def test_learner_submission_wires_private_upload_rpc_and_rejected_upload_cleanup() -> None:
    assert "async function submitTrainingPracticalProject(form)" in APP
    assert "readTrainingPracticalSubmission(form)" in APP
    assert "uploadTrainingPracticalObject(" in APP
    assert 'evidence_kind: file ? "private_file" : "https_url"' in APP
    assert "file.size > settings.maxUploadBytes" in APP
    assert "removeTrainingPracticalObject(" in APP
    assert "state.api.savePracticalProject(payload)" in APP
    assert 'form.id === "training-practical-submit-form"' in APP


def test_manager_queue_decision_and_protected_view_are_wired() -> None:
    assert "trainingPracticalReviewQueueMarkup(" in APP
    assert "async function submitTrainingPracticalDecision(form, submitter)" in APP
    assert "readTrainingPracticalDecision(form, submitter)" in APP
    assert "state.api.decidePracticalProject(decision.payload)" in APP
    assert 'form.classList.contains("training-practical-review__form")' in APP
    assert 'action === "open-training-practical-media"' in APP
    assert "signedTrainingPracticalObjectUrls(bucketId, [objectKey], 600)" in APP


def test_manager_review_queue_is_available_before_workspace_unlock() -> None:
    practical_page = APP[
        APP.index("function renderTrainingPracticalProject(") :
        APP.index("function trainingPracticalUploadSettings(")
    ]
    assert "canManageTeam()" in practical_page
    assert "trainingPracticalReviewQueueMarkup" in practical_page
    assert "practicalReviews" in practical_page
    assert 'if (path === "/learn/practical")' in APP


def test_uploaded_file_is_removed_only_before_project_commit() -> None:
    submit = APP[
        APP.index("async function submitTrainingPracticalProject(") :
        APP.index("async function submitTrainingPracticalDecision(")
    ]
    assert "let projectCommitted = false" in submit
    assert submit.index("await state.api.savePracticalProject(payload)") < submit.index(
        "projectCommitted = true"
    )
    assert "uploadedObjectKey && !projectCommitted" in submit


def _practical_review_refresh() -> str:
    return APP[
        APP.index("async function refreshTrainingPracticalReviews(") :
        APP.index("async function openTrainingPracticalMedia(")
    ]


def test_manager_queue_refresh_is_scoped_deduplicated_and_context_bound() -> None:
    refresh = _practical_review_refresh()

    assert 'data-action="refresh-training-practical-reviews"' in PRACTICAL_VIEW
    assert '!canManageTeam()' in refresh
    assert '["/learn/practical", "/workspace/team"].includes(state.route.path)' in refresh
    assert "if (trainingPracticalReviewRefreshPromise)" in refresh
    assert "await trainingPracticalReviewRefreshPromise" in refresh
    assert "trainingPracticalReviewRefreshPromise = state.api.bootstrap({" in refresh
    assert 'refresh_scope: "training_practical_reviews"' in refresh
    assert "session_id: state.sessionId" in refresh
    assert "fresh.profile?.id !== state.bootstrap?.profile?.id" in refresh
    assert "fresh.organization?.id !== state.bootstrap?.organization?.id" in refresh
    assert 'throw new Error("training_practical_refresh_context_changed")' in refresh
    assert refresh.index("training_practical_refresh_context_changed") < refresh.index(
        "state.api.commitBootstrapContext(raw)"
    )
    assert "loadBootstrap()" not in refresh
    assert "render()" not in refresh


def test_manager_queue_refresh_merges_only_reviews_and_preserves_draft_feedback() -> None:
    refresh = _practical_review_refresh()

    assert "state.bootstrap = {" in refresh
    assert "...state.bootstrap" in refresh
    assert "...state.bootstrap.training" in refresh
    assert "practicalReviews: fresh.training.practicalReviews" in refresh
    assert "state.bootstrap = normalizeBootstrap(raw)" not in refresh
    assert 'document.querySelector(".training-practical-queue")' in refresh
    assert 'queue?.querySelectorAll(".training-practical-review__form textarea")' in refresh
    assert 'String(textarea.value || "").trim()' in refresh
    safe_replace = refresh.index("if (queue && !hasUnsentReviewNote)")
    replace_queue = refresh.index("queue.replaceWith(replacement.firstElementChild)")
    preserve_draft = refresh.index("} else if (queue && hasUnsentReviewNote)")
    assert safe_replace < replace_queue < preserve_draft
    assert 'queue.dataset.refreshPending = "true"' in refresh
    assert refresh.index('queue.dataset.refreshPending = "true"') < refresh.index(
        'if (!silent) toast(', preserve_draft
    )


def test_manager_queue_refresh_restores_control_and_has_automatic_triggers() -> None:
    refresh = _practical_review_refresh()

    assert 'control.setAttribute("aria-busy", "true")' in refresh
    assert "trainingPracticalReviewRefreshPromise = null" in refresh
    assert "if (control?.isConnected)" in refresh
    assert "control.disabled = false" in refresh
    assert 'control.removeAttribute("aria-busy")' in refresh
    assert "void refreshTrainingPracticalReviews({ silent: true })" in APP
    assert 'action === "refresh-training-practical-reviews"' in APP


def test_api_limits_practical_objects_to_the_separate_private_bucket() -> None:
    for marker in (
        'savePracticalProject: "creator_save_practical_project"',
        'decidePracticalProject: "creator_decide_practical_project"',
        "uploadTrainingPracticalObject(bucketId, pathPrefix, objectKey, file)",
        "signedTrainingPracticalObjectUrls(bucketId, objectKeys, expiresIn = 600)",
        'bucket !== "contentengine-training"',
        'upsert: false',
    ):
        assert marker in API


def test_source_switching_and_six_step_passport_are_visible() -> None:
    assert 'event.target.matches("[data-training-practical-source]")' in APP
    assert "syncTrainingPracticalSource(form, event.target.value)" in APP
    assert "<div><strong>Пробная работа</strong>" in APP
    assert '${examPassed ? "✓" : 6}' in APP
    assert '"/learn/practical": "Пробная работа"' in APP
