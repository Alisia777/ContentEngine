from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")
CONFIG = (ROOT / "web/app/config.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")
QUEUE_MODULE = ROOT / "web/app/media-upload-queue.js"


def _between(start: str, end: str) -> str:
    start_index = APP.index(start)
    return APP[start_index:APP.index(end, start_index)]


def test_media_picker_accepts_a_real_multi_file_batch() -> None:
    markup = _between("function renderMediaSection", "function mediaCard")

    assert 'id="media-file"' in markup
    assert " multiple required" in markup
    assert 'type="button" data-upload-zone data-action="choose-media-upload-files"' in markup
    assert 'class="upload-zone__input"' in markup
    assert "Выбрать файлы" in markup
    assert "перетащите их сюда" in markup
    assert 'id="selected-file-summary"' in markup
    assert "MAX_MEDIA_BATCH_FILES: 20" in CONFIG
    assert "config.js?v=20260826.rebuild-clean.48" in INDEX


def test_media_picker_button_opens_the_native_multi_file_chooser_synchronously() -> None:
    click = _between("async function handleClick", "async function handleSubmit")

    assert 'if (action === "choose-media-upload-files")' in click
    assert "input.click();" in click
    chooser_branch = click[
        click.index('if (action === "choose-media-upload-files")'):
        click.index('if (action === "remove-media-upload-file")')
    ]
    assert "await " not in chooser_branch
    assert "input.disabled" in chooser_branch
    assert 'form.dataset.busy === "true"' in chooser_branch
    assert ".upload-zone__input" in STYLES
    assert ".upload-zone:hover:not(:disabled)" in STYLES


def test_drop_merges_every_file_instead_of_taking_only_the_first() -> None:
    drop = _between("async function handleDrop", "function handleDragEnd")

    assert "Array.from(event.dataTransfer?.files || [])" in drop
    assert "mergeMediaFileSelection(" in drop
    assert "const input = form?.elements?.file;" in drop
    assert "setMediaInputFiles(input, selection.files)" in drop
    assert "files?.[0]" not in drop
    assert "MEDIA_UPLOAD_BATCH_LIMIT" in drop


def test_batch_upload_has_bounded_parallelism_and_per_file_recovery() -> None:
    submit = _between("async function submitMedia(form)", "async function track")

    assert "Array.from(form.elements.file?.files || [])" in submit
    assert "MEDIA_UPLOAD_CONCURRENCY" in submit
    assert "await Promise.all(" in submit
    assert "setMediaUploadItemStatus(form, index" in submit
    assert "await fileSha256(file)" in submit
    assert "await state.api.uploadPrivateObject(objectKey, file)" in submit
    assert "await state.api.registerMedia({" in submit
    assert "await state.api.removePrivateObject(objectKey)" in submit
    assert "failed.map((item) => item.file)" in submit
    assert "Неудачные файлы оставлены в очереди для повтора" in submit
    assert 'await track("media_uploaded"' not in submit
    assert 'await track("media_batch_uploaded"' not in submit


def test_optional_telemetry_never_holds_the_upload_form_busy() -> None:
    track = _between("async function track(", "function validateConfig")

    assert "const capture = state.api.captureEvent({" in track
    assert "Promise.resolve(capture).catch(() => {});" in track
    assert "await state.api.captureEvent({" not in track


def test_media_upload_busy_state_cannot_leave_a_replaced_form_locked() -> None:
    restore = _between("function restoreDirtyWorkspaceForms", "function workspaceNavLinkMarkup")
    submit = _between("async function submitMedia(form)", "async function track")

    assert "state.mediaUploadInFlight" in restore
    assert "state.mediaUploadInFlight = true;" in submit
    assert "state.mediaUploadInFlight = false;" in submit
    assert 'document.querySelector("#media-upload-form")' in submit
    assert "if (currentForm) setFormBusy(currentForm, false);" in submit


def test_batch_selection_and_worker_limit_are_executable() -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable upload contracts"
    source = f"""
const subject = await import({json.dumps(QUEUE_MODULE.as_uri())});
const file = (name, size, type, lastModified = 1) => ({{
  name, size, type, lastModified,
}});
const current = [file("front.jpg", 100, "image/jpeg")];
const added = [
  file("front.jpg", 100, "image/jpeg"),
  file("angle.png", 200, "image/png", 2),
  file("demo.mp4", 300, "video/mp4", 3),
  file("extra.webp", 400, "image/webp", 4),
];
const selection = subject.mergeMediaFileSelection(current, added, 3);
process.stdout.write(JSON.stringify({{
  names: selection.files.map((item) => item.name),
  skipped: selection.skipped,
  workers: subject.mediaUploadWorkerCount(12, 3),
  valid: subject.mediaFileValidationError(
    file("demo.mp4", 300, "video/mp4"),
    500,
  ),
  tooLarge: subject.mediaFileValidationError(
    file("demo.mp4", 600, "video/mp4"),
    500,
  ),
  wrongType: subject.mediaFileValidationError(
    file("notes.txt", 20, "text/plain"),
    500,
  ),
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    payload = json.loads(result.stdout)

    assert payload["names"] == ["front.jpg", "angle.png", "demo.mp4"]
    assert payload["skipped"] == 2
    assert payload["workers"] == 3
    assert payload["valid"] == ""
    assert payload["tooLarge"] == "Файл больше допустимого размера."
    assert payload["wrongType"] == "Нужен JPG, PNG, WEBP или MP4."


def test_upload_queue_is_usable_on_mobile_and_exposes_each_result() -> None:
    assert ".media-upload-queue__item" in STYLES
    assert '.media-upload-queue__item[data-upload-state="success"]' in STYLES
    assert '.media-upload-queue__item[data-upload-state="error"]' in STYLES
    assert "@media (max-width: 560px)" in STYLES
    assert 'data-action="remove-media-upload-file"' in APP
    assert 'aria-label="Очередь загрузки"' in APP
    assert 'aria-live="polite"' in APP
