import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
BOARD = (APP_DIR / "workspace-board-view.js").read_text(encoding="utf-8")


def test_review_is_one_action_surface_with_a_four_step_wizard() -> None:
    for marker in (
        'data-content-review-wizard data-review-step="1"',
        'data-review-wizard-panel="1"',
        'data-review-wizard-panel="2"',
        'data-review-wizard-panel="3"',
        'data-review-wizard-panel="4"',
        'data-action="content-review-wizard-step"',
        "hydrateContentReviewWizard",
        "setContentReviewWizardStep",
        "content-review:wizard-step",
        "syncContentReviewWizardMediaCount",
        'form.addEventListener("change"',
        'const owner = form.closest("#main-content")',
        "owner.scrollTo",
        "form.scrollIntoView",
    ):
        assert marker in VIEW

    assert "hydrateContentReviewWizard," in APP
    assert 'hydrateContentReviewWizard(document.querySelector("#content-review-form"))' in APP
    assert "view: reviewView" in APP
    assert 'reviewStep: String(form.dataset.reviewStep || "")' in APP
    assert "form.dataset.reviewStep = snapshot.reviewStep" in APP


def test_review_view_replaces_the_central_action_instead_of_stacking_panels() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
globalThis.window = {{ location: {{ href: "https://portal.test/" }} }};
const subject = await import({json.dumps(module_url)});
const catalog = {{ media: [], runs: [] }};
const fresh = subject.contentReviewWorkspaceMarkup({{ catalog, view: "new" }});
const current = subject.contentReviewWorkspaceMarkup({{ catalog, view: "current" }});
const history = subject.contentReviewWorkspaceMarkup({{ catalog, view: "history" }});
if (!fresh.includes('id="content-review-form"')) throw new Error("new form missing");
if (fresh.includes('class="content-review-output"')) throw new Error("result stacked beside form");
if (!current.includes('class="content-review-output"')) throw new Error("current result missing");
if (current.includes('id="content-review-form"')) throw new Error("form stacked beside result");
if (!history.includes('class="content-review-history"')) throw new Error("history missing");
if (history.includes('id="content-review-form"')) throw new Error("form stacked beside history");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_files_default_to_all_and_smart_folders_never_reach_folder_rpcs() -> None:
    assert 'entityType: "all"' in APP
    assert "!isWorkspaceSmartFolderId(folderId)" in APP
    assert "!isWorkspaceSmartFolderId(rawParentId)" not in APP
    assert "isWorkspaceSmartFolderId(rawParentId)" in APP
    assert "isWorkspaceSmartFolderId(destination)" in APP
    assert "SMART_FOLDER_DEFINITIONS" in BOARD
    assert 'normalizedEntityType(options.entityType, "media")' in BOARD


def test_folder_archive_confirmation_is_inline_not_a_browser_subwindow() -> None:
    archive = APP[
        APP.index("async function archiveWorkspaceBoardFolder"):
        APP.index("async function moveWorkspaceBoardItem")
    ]
    assert "window.confirm" not in archive
    assert "pendingArchiveFolderId" in archive
    assert 'data-action="confirm-archive-workspace-folder"' in BOARD
    assert 'data-action="cancel-archive-workspace-folder"' in BOARD
