from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (APP_DIR / "workspace-desk-drafts.js").read_text(encoding="utf-8")
CSS = (APP_DIR / "workspace-desk-drafts.css").read_text(encoding="utf-8")


def test_draft_assets_load_after_the_desktop_controller() -> None:
    assert './workspace-desk-drafts.css?v=20260730.1' in INDEX
    assert './workspace-desk-drafts.js?v=20260730.1' in INDEX
    assert INDEX.index("./workspace-desks-v2.js") < INDEX.index("./workspace-desk-drafts.js")


def test_drafts_are_tab_memory_only_and_never_call_the_backend() -> None:
    assert "const draftRoutes = new Map()" in SCRIPT
    assert "sessionStorage" not in SCRIPT
    assert "localStorage" not in SCRIPT
    assert "fetch(" not in SCRIPT
    assert "XMLHttpRequest" not in SCRIPT
    assert ".api." not in SCRIPT


def test_secret_and_hidden_fields_are_excluded() -> None:
    for marker in (
        '"password", "hidden", "submit"',
        "DRAFT_SECRET_PATTERN",
        'field.getAttribute("autocomplete") === "one-time-code"',
        'field.closest("[data-no-desk-draft], .workspace-overview")',
    ):
        assert marker in SCRIPT


def test_form_values_and_files_restore_without_serializing_file_objects() -> None:
    for marker in (
        "snapshotField(field, index)",
        "base.files = [...(field.files || [])]",
        'typeof DataTransfer !== "function"',
        "saved.files.forEach((file) => transfer.items.add(file))",
        "field.files = transfer.files",
        "MAX_DRAFT_AGE_MS",
        "workspaceDeskRestoredAt",
    ):
        assert marker in SCRIPT

    assert "JSON.stringify" not in SCRIPT


def test_draft_observer_is_idempotent_and_does_not_rewrite_equal_badges() -> None:
    for marker in (
        "function setIndicatorText(element, text)",
        "if (element.textContent !== text)",
        "form.dataset.workspaceDeskRestoredAt === String(saved.capturedAt)",
        "if (restoreQueued) return",
        "new MutationObserver",
    ):
        assert marker in SCRIPT


def test_draft_state_is_visible_in_current_desk_and_mission_control() -> None:
    for marker in (
        ".workspace-draft-indicator",
        ".workspace-overview-draft",
        ".workspace-draft-live-region",
    ):
        assert marker in CSS
    assert "Черновик ·" in SCRIPT
    assert "data-overview-route" in SCRIPT


def test_draft_javascript_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed in this test environment")
    subprocess.run(
        [node, "--check", str(APP_DIR / "workspace-desk-drafts.js")],
        check=True,
        capture_output=True,
        text=True,
    )
