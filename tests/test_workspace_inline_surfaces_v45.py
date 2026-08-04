from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
TRASH = (APP / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
TRASH_CSS = (APP / "workspace-os-v4-context-trash.css").read_text(encoding="utf-8")
FINDER = (APP / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
FINDER_CSS = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_trash_is_an_inline_finder_route_and_dock_never_disappears() -> None:
    for marker in (
        'openWorkspaceRoute("/workspace/board?view=trash")',
        'routeQuery().get("view") === "trash"',
        'const board = q(".workspace-board")',
        'board.append(parts.surface)',
        'board.classList.add("is-trash-view")',
        'runtime.trashDock?.classList.add("is-active")',
        'runtime.trashDock?.setAttribute("aria-current", "page")',
        'button.addEventListener("click", openTrash)',
        'menuAction("Открыть Корзину", "trash", openTrash)',
    ):
        assert marker in TRASH

    for marker in (
        ".workspace-board.is-trash-view > .ce-v4-trash-surface",
        ".ce-v4-trash-surface[data-inline-mode=\"preview\"]",
        ".ce-v4-trash-surface[data-inline-mode=\"confirm\"]",
    ):
        assert marker in TRASH_CSS

    for forbidden in (
        "aria-modal",
        "alertdialog",
        "syncModalInert",
        "trashWindow",
        'toggleAttribute("inert"',
        "ce-v4-trash-backdrop",
        "ce-v4-trash-preview-backdrop",
        "ce-v4-confirm-backdrop",
    ):
        assert forbidden not in TRASH
        assert forbidden not in TRASH_CSS

    assert "body.ce-v4-trash-open .ce-v4-dock" not in TRASH_CSS


def test_preview_restore_and_irreversible_delete_are_inline_states() -> None:
    for marker in (
        'runtime.trashSurface.dataset.inlineMode = "preview"',
        "runtime.trashBody.replaceChildren(panel)",
        "confirmRestoreTrashItems",
        'phrase: "УДАЛИТЬ"',
        'phrase: "ОЧИСТИТЬ"',
        "creator_restore_workspace_items",
        "creator_purge_workspace_items",
        "creator_complete_workspace_storage_cleanup",
        ".storage.from(bucket).remove",
    ):
        assert marker in TRASH

    assert "window.confirm" not in TRASH
    assert "role=\"dialog\"" not in TRASH


def test_finder_quick_look_reuses_the_inline_details_surface() -> None:
    for marker in (
        'drawer.closest(".workspace-board")',
        'drawer.classList.add("ce-v4-quicklook-inline")',
        'board.classList.add("is-quicklook-inline")',
        'current.board?.classList.remove("is-quicklook-inline")',
        ".workspace-board.is-quicklook-inline",
    ):
        assert marker in FINDER or marker in FINDER_CSS

    for forbidden in (
        "aria-modal",
        "ce-v4-quicklook-backdrop",
        "ce-v4-finder-sidebar-backdrop",
        "sidebar.inert",
        "document.body.append(backdrop)",
    ):
        assert forbidden not in FINDER
        assert forbidden not in FINDER_CSS


def test_empty_surface_context_routes_follow_creator_and_trainee_authorization() -> None:
    helper = _between(
        TRASH,
        "function authorizedWorkspaceRoutes()",
        "function createFromFinderMedia(",
    )
    actions = _between(TRASH, "function emptySurfaceActions(", "function contextActions(")
    for route in ("board", "research", "team", "feedback"):
        assert f'workspaceRouteAuthorized("/workspace/{route}")' in actions

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the authorization contract")
    probe = f"""
let declared = "";
const shell = {{ dataset: {{ workspaceAuthorizedRoutes: "", workspaceSection: "home" }} }};
function q(selector) {{ return selector.includes("workspace-shell") ? shell : null; }}
function qa() {{ return []; }}
function routePath() {{ return "/workspace/home"; }}
{helper}
function visible(value) {{
  shell.dataset.workspaceAuthorizedRoutes = value;
  return ["/workspace/board", "/workspace/research", "/workspace/team", "/workspace/feedback"]
    .filter(workspaceRouteAuthorized);
}}
process.stdout.write(JSON.stringify({{
  creator: visible("/workspace/home /workspace/board /workspace/research /workspace/team /workspace/feedback"),
  trainee: visible("/workspace/home /workspace/work /workspace/tasks"),
}}));
"""
    result = subprocess.run(
        [node, "-e", probe],
        check=True,
        capture_output=True,
        text=True,
    )
    visibility = json.loads(result.stdout)
    assert visibility["creator"] == [
        "/workspace/board",
        "/workspace/research",
        "/workspace/team",
        "/workspace/feedback",
    ]
    assert visibility["trainee"] == []


def test_inline_surface_assets_parse_and_css_balances() -> None:
    assert TRASH_CSS.count("{") == TRASH_CSS.count("}")
    assert FINDER_CSS.count("{") == FINDER_CSS.count("}")
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable UI contracts")
    for filename in ("workspace-os-v4-context-trash.js", "workspace-os-v4-finder.js"):
        subprocess.run(
            [node, "--check", str(APP / filename)],
            check=True,
            capture_output=True,
            text=True,
        )
