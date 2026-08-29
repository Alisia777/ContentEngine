"""Recovery contracts for uploading into an empty workspace project.

The media catalog is a read request.  Choosing and uploading a new source is a
separate action and must stay available while that catalog is loading or has
failed.  These contracts prevent a catalog outage from turning the first step
of a new project into an empty desktop.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
FINDER = (ROOT / "web/app/workspace-os-v4-finder.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _function(source: str, declaration: str) -> str:
    """Extract a JavaScript function without depending on its neighbour."""

    start = source.index(declaration)
    body_match = re.search(r"\)\s*\{", source[start:])
    assert body_match, f"Missing JavaScript function body: {declaration}"
    opening = start + body_match.end() - 1
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unterminated JavaScript function: {declaration}")


def _run_node(script: str) -> None:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for upload recovery contracts"
    result = subprocess.run(
        [node, "--input-type=module", "-"],
        cwd=ROOT,
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == "ok"


def test_media_picker_is_rendered_before_the_catalog_finishes_loading() -> None:
    """An empty new project must not wait for the read-only catalog RPC."""

    render = _function(APP, "function renderWorkspace(")
    initial_load = render[
        render.index("const initialSectionLoad") : render.index(
            "const contentSignature", render.index("const initialSectionLoad")
        )
    ]

    assert re.search(
        r'(?:section\s*!==\s*["\']media["\']|'
        r'!\[[^\]]*["\']media["\'][^\]]*\]\.includes\(section\))',
        initial_load,
    ), (
        "The media upload action is currently replaced by the full-page initial "
        "skeleton. Exclude media from initialSectionLoad so renderMediaSection "
        "can show its independent picker while the catalog reads in parallel."
    )


def test_empty_loading_refreshing_and_error_states_keep_one_inline_upload_action() -> None:
    media_renderer = _function(APP, "function renderMediaSection(")
    section_body = _function(APP, "function sectionBody(")
    script = f"""
const projectId = "11111111-1111-4111-8111-111111111111";
const state = {{
  route: {{
    path: "/workspace/media",
    query: new URLSearchParams(`view=upload&project_id=${{projectId}}`),
  }},
  sections: {{ media: null }},
}};
const CONFIG = {{ MAX_UPLOAD_BYTES: 50 * 1024 * 1024 }};
const MEDIA_UPLOAD_BATCH_LIMIT = 20;
const LOCAL_QA_MEDIA_FIXTURE_ENABLED = false;
const listFrom = (data, ...keys) => {{
  if (Array.isArray(data)) return data;
  for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
  return [];
}};
const pageHeader = (title, copy, action) => `<header><h1>${{title}}</h1><p>${{copy}}</p>${{action}}</header>`;
const formatBytes = () => "50 МБ";
const escapeHtml = (value) => String(value ?? "");
const mediaCard = () => "";
// Запись 29.08.2026: «Забор видео v2» добавил в renderMediaSection вызов
// videoIntakeCardMarkup(); харнесу карточка забора не важна — глушим заглушкой.
const videoIntakeCardMarkup = () => "";
const emptyState = (_icon, title, message) => `<div class="empty-state"><h3>${{title}}</h3><p>${{message}}</p></div>`;
{section_body}
{media_renderer}

const must = (condition, message) => {{ if (!condition) throw new Error(message); }};
const count = (text, token) => text.split(token).length - 1;
const assertRecoverable = (status, data) => {{
  const sectionState = {{ status, data, error: status === "error" ? new Error("catalog-down") : null }};
  state.sections.media = sectionState;
  const markup = renderMediaSection(sectionState);
  must(markup.includes('id="media-upload-form"'), `${{status}}:picker-missing`);
  must(markup.includes('id="media-file"'), `${{status}}:native-input-missing`);
  must(markup.includes('type="file"'), `${{status}}:file-input-missing`);
  must(markup.includes('data-action="choose-media-upload-files"'), `${{status}}:choose-action-missing`);
  must(count(markup, 'data-primary-action="true"') === 1, `${{status}}:primary-count`);
  must(!markup.includes('role="dialog"'), `${{status}}:dialog-reintroduced`);
  must(!markup.includes("backdrop"), `${{status}}:backdrop-reintroduced`);
  return markup;
}};

const loading = assertRecoverable("loading", null);
must(loading.includes("Загружаем данные"), "loading-status-missing");

const empty = assertRecoverable("ready", {{ media: [] }});
must(empty.includes("Материалов пока нет"), "empty-state-missing");

const refreshing = assertRecoverable("refreshing", {{ media: [] }});
must(refreshing.includes("Обновляем данные"), "refreshing-status-missing");

const failed = assertRecoverable("error", null);
must(failed.includes("Не удалось обновить список файлов"), "catalog-error-not-specific");
must(
  failed.includes("можете выбрать и загрузить"),
  "catalog-error-does-not-explain-upload-recovery",
);
must(failed.includes('data-action="refresh-section"'), "catalog-retry-missing");
must(/class="btn[^\"]*btn-secondary[^\"]*"[^>]*data-action="refresh-section"/u.test(failed), "catalog-retry-not-secondary");
const uploadPanel = failed.slice(
  failed.indexOf('class="card card-pad media-upload-panel"'),
  failed.indexOf("</section>", failed.indexOf('class="card card-pad media-upload-panel"')),
);
must(uploadPanel.includes("Не удалось обновить список файлов"), "catalog-error-hidden-with-library");
must(uploadPanel.includes('data-action="refresh-section"'), "catalog-retry-hidden-with-library");
process.stdout.write("ok");
"""
    _run_node(script)


def test_finder_handoff_and_submit_do_not_depend_on_folder_catalog_or_a_modal() -> None:
    finder_toolbar = _function(FINDER, "function buildToolbar(")
    submit = _function(APP, "async function submitMedia(")
    media_renderer = _function(APP, "function renderMediaSection(")

    assert '"Добавить материал"' in finder_toolbar
    assert 'upload.dataset.action = "finder-upload"' in finder_toolbar
    assert 'upload.dataset.ceV4FinderUpload = "true"' in finder_toolbar
    assert 'if (action === "finder-upload")' in APP
    assert 'navigate("/workspace/media")' in APP
    assert "workspaceProjectHref(rawNormalized)" in _function(APP, "function navigate(")

    assert "const projectId = requireWorkspaceProjectId();" in submit
    assert "await state.api.uploadPrivateObject(objectKey, file)" in submit
    assert "await state.api.registerMedia({" in submit
    assert "project_id: projectId" in submit
    assert "workspaceBrowser" not in submit
    assert "workspace_folders" not in submit
    assert "state.sections.board" not in submit

    assert 'id="media-upload-form"' in media_renderer
    assert 'role="dialog"' not in media_renderer
    assert "backdrop" not in media_renderer
    assert not re.search(
        r'^\s*<script\s+type="module"\s+src="\./workspace-media-finder\.js',
        INDEX,
        flags=re.MULTILINE,
    )
    assert '<!-- <script type="module" src="./workspace-media-finder.js' in INDEX


def test_failed_files_stay_selected_with_an_inline_reason_for_retry() -> None:
    submit = _function(APP, "async function submitMedia(")

    assert "const message = actionErrorMessage(error);" in submit
    assert 'setMediaUploadItemStatus(form, index, "error", message)' in submit
    assert "failed.map((item) => item.file)" in submit
    assert "setMediaInputFiles(" in submit
    assert 'form.dataset.dirty = "true"' in submit
    assert "Неудачные файлы оставлены в очереди для повтора" in submit
