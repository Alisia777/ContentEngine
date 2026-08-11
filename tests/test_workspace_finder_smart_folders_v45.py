from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
BOARD = (APP / "workspace-board-view.js").read_text(encoding="utf-8")
CONTEXT = (APP / "workspace-os-v4-context-trash.js").read_text(encoding="utf-8")
FINDER = (APP / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
FINDER_CSS = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")


def _run_board_contract() -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable Finder contracts")

    contract = r"""
import {
  isWorkspaceSmartFolderId,
  normalizeWorkspaceBoard,
  workspaceBoardMarkup,
} from './subject.mjs';

const raw = {
  capabilities: { manage_folders: true, move_items: true },
  _meta: { has_more: true },
  folders: [
    { id: 'project', name: 'MILIO', kind: 'project', can_edit: true, item_count: 370 },
    { id: 'sources', parent_id: 'project', project_id: 'project', name: 'Исходники', system_role: 'sources', item_count: 145 },
    { id: 'drafts', parent_id: 'project', project_id: 'project', name: 'Черновики', system_role: 'drafts', item_count: 222 },
    { id: 'custom', parent_id: 'project', project_id: 'project', name: 'Ручная подборка', can_edit: true, item_count: 3 },
    { id: 'smart-videos', parent_id: 'project', project_id: 'project', name: 'Обычная папка со старым ID', can_edit: true },
  ],
  items: [
    { id: 'source-1', entity_type: 'media', title: 'Source photo', mime_type: 'image/jpeg', status: 'ready', folder_id: 'sources', artifact_class: 'source', lifecycle_stage: 'sources' },
    { id: 'source-2', entity_type: 'media', title: 'Source video', mime_type: 'video/mp4', status: 'ready', folder_id: 'sources', artifact_class: 'source', lifecycle_stage: 'sources' },
    { id: 'result-1', entity_type: 'media', title: 'Generated photo', mime_type: 'image/png', status: 'ready', folder_id: 'drafts', artifact_class: 'generated_output', lifecycle_stage: 'drafts' },
    { id: 'result-2', entity_type: 'media', title: 'Generated video', mime_type: 'video/mp4', status: 'ready', folder_id: 'drafts', artifact_class: 'generated_output', lifecycle_stage: 'drafts' },
  ],
};

const board = normalizeWorkspaceBoard(raw);
const html = workspaceBoardMarkup(board, {
  selectedFolderId: 'all',
  selectedItemKey: 'media:source-1',
  entityType: 'media',
});
const sourcesHtml = workspaceBoardMarkup(board, {
  selectedFolderId: 'sources',
  entityType: 'media',
});

process.stdout.write(JSON.stringify({
  folders: board.folders.map(({ id, name, systemRole, smart }) => ({ id, name, systemRole, smart: smart === true })),
  smartChecks: [isWorkspaceSmartFolderId('smart-videos'), isWorkspaceSmartFolderId('smart-images')],
  classifications: board.items.map(({ id, artifactClass, lifecycleStage }) => ({ id, artifactClass, lifecycleStage })),
  allKeys: [...html.matchAll(/data-workspace-item-key="([^"]+)"/g)].map((match) => match[1]),
  hasSourceBadge: html.includes('data-artifact-class="source">Источник</span>'),
  hasResultBadge: html.includes('data-artifact-class="generated_output">Результат</span>'),
  hasLifecycleBadge: html.includes('data-lifecycle-stage="drafts">Черновик</span>'),
  hasPartialHeader: html.includes('4 загружено'),
  hasPartialAllCount: /<span>Все файлы<\/span>\s*<small>4\+<\/small>/.test(html),
  hasAuthoritativeSourceCount: /<span>Источники<\/span>\s*<small>145<\/small>/.test(html),
  hasAuthoritativeDraftCount: /<span>Результаты · Черновики<\/span>\s*<small>222<\/small>/.test(html),
  systemMoveTarget: /data-target-folder-id="(?:sources|drafts)"/.test(html),
  systemDropTarget: /data-workspace-drop-folder[^>]*data-folder-id="(?:sources|drafts)"|data-folder-id="(?:sources|drafts)"[^>]*data-workspace-drop-folder/.test(html),
  customDropTarget: /data-workspace-drop-folder[^>]*data-folder-id="custom"|data-folder-id="custom"[^>]*data-workspace-drop-folder/.test(html),
  sourceFilterKeys: [...sourcesHtml.matchAll(/data-workspace-item-key="([^"]+)"/g)].map((match) => match[1]),
}));
"""

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(BOARD, encoding="utf-8")
        (directory / "contract.mjs").write_text(contract, encoding="utf-8")
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )

    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_server_system_folders_replace_page_local_mime_smart_folders() -> None:
    payload = _run_board_contract()
    folders = payload["folders"]

    assert payload["smartChecks"] == [False, False]
    assert not any(folder["smart"] for folder in folders)
    assert {folder["systemRole"] for folder in folders} >= {"sources", "drafts"}
    # A historical smart-looking ID is now just an ordinary server folder.
    assert any(folder["id"] == "smart-videos" for folder in folders)

    assert payload["allKeys"] == [
        "media:result-2",
        "media:result-1",
        "media:source-2",
        "media:source-1",
    ]
    assert payload["sourceFilterKeys"] == ["media:source-2", "media:source-1"]


def test_source_and_result_identity_is_preserved_and_visible() -> None:
    payload = _run_board_contract()
    assert payload["classifications"] == [
        {"id": "result-2", "artifactClass": "generated_output", "lifecycleStage": "drafts"},
        {"id": "result-1", "artifactClass": "generated_output", "lifecycleStage": "drafts"},
        {"id": "source-2", "artifactClass": "source", "lifecycleStage": "sources"},
        {"id": "source-1", "artifactClass": "source", "lifecycleStage": "sources"},
    ]
    assert payload["hasSourceBadge"] is True
    assert payload["hasResultBadge"] is True
    assert payload["hasLifecycleBadge"] is True


def test_pagination_copy_is_honest_and_system_counts_are_authoritative() -> None:
    payload = _run_board_contract()
    assert payload["hasPartialHeader"] is True
    assert payload["hasPartialAllCount"] is True
    assert payload["hasAuthoritativeSourceCount"] is True
    assert payload["hasAuthoritativeDraftCount"] is True


def test_system_roles_are_never_manual_move_or_drop_targets() -> None:
    payload = _run_board_contract()
    assert payload["systemMoveTarget"] is False
    assert payload["systemDropTarget"] is False
    assert payload["customDropTarget"] is True
    assert "!String(row.dataset.systemRole || \"\").trim()" in FINDER


def test_visible_overflow_buttons_open_the_existing_context_menu_safely() -> None:
    for marker in (
        'event.target.closest("[data-ce-v4-context-trigger]")',
        "openContextMenu(target, rect.right, rect.bottom + 4, trigger)",
        'Boolean(String(row.dataset.systemRole || "").trim())',
        "finderOrganizeMode() && !folder.system",
    ):
        assert marker in CONTEXT

    for marker in (
        ".workspace-board__context-trigger",
        ".workspace-board__folder-group-label",
        ".workspace-board__context-hint",
        '.ce-v4-finder-kind[data-kind="source"]',
        '.ce-v4-finder-kind[data-kind="result"]',
    ):
        assert marker in FINDER_CSS
