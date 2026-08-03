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
  folders: [
    { id: 'real-folder', name: 'Кампания', can_edit: true },
    { id: 'smart-videos', name: 'Server collision', can_edit: true },
  ],
  items: [
    { id: 'video-1', entity_type: 'media', title: 'Video', mime_type: 'video/mp4', status: 'ready', folder_id: 'smart-videos' },
    { id: 'image-1', entity_type: 'media', title: 'Image', mime_type: 'image/jpeg', status: 'ready' },
    { id: 'work-1', entity_type: 'task', title: 'Work', status: 'in_progress' },
    { id: 'review-1', entity_type: 'task', title: 'Review', status: 'review' },
    { id: 'publish-1', entity_type: 'placement', title: 'Publish', status: 'ready' },
    { id: 'published-1', entity_type: 'publication', title: 'Published', status: 'published' },
  ],
};

const board = normalizeWorkspaceBoard(raw);
const keysFor = (folderId, entityType = 'all') => {
  const html = workspaceBoardMarkup(board, { selectedFolderId: folderId, entityType });
  return [...html.matchAll(/data-workspace-item-key="([^"]+)"/g)].map((match) => match[1]);
};
const defaultHtml = workspaceBoardMarkup(board);
const smartHtml = workspaceBoardMarkup(board, { selectedFolderId: 'smart-videos', entityType: 'all' });
const selectedHtml = workspaceBoardMarkup(board, {
  selectedFolderId: 'all',
  selectedItemKey: 'media:video-1',
  entityType: 'media',
});

process.stdout.write(JSON.stringify({
  folders: board.folders.map(({ id, name, smart, editable }) => ({ id, name, smart: smart === true, editable })),
  smartChecks: [isWorkspaceSmartFolderId('smart-videos'), isWorkspaceSmartFolderId('real-folder')],
  videoFolderReference: board.items.find((item) => item.id === 'video-1')?.folderId ?? null,
  filters: {
    videos: keysFor('smart-videos'),
    images: keysFor('smart-images'),
    work: keysFor('smart-in-work'),
    review: keysFor('smart-review'),
    publish: keysFor('smart-to-publish'),
    published: keysFor('smart-published'),
  },
  defaultKeys: [...defaultHtml.matchAll(/data-workspace-item-key="([^"]+)"/g)].map((match) => match[1]),
  hasContextHint: defaultHtml.includes('ПКМ или ⋯ — быстрые действия'),
  contextTriggerCount: (defaultHtml.match(/data-ce-v4-context-trigger=/g) || []).length,
  moveHasSmartTarget: /data-target-folder-id="smart-/.test(selectedHtml),
  smartDropTarget: /data-workspace-drop-folder[^>]*data-folder-id="smart-|data-folder-id="smart-[^"]+"[^>]*data-workspace-drop-folder/.test(defaultHtml),
  smartCreateUsesRoot: /name="parent_folder_id" value="root"/.test(smartHtml),
  smartEditIsHidden: /id="workspace-folder-edit-form"[\s\S]*?hidden aria-hidden="true"/.test(smartHtml),
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


def test_smart_folders_are_always_available_and_filter_locally() -> None:
    payload = _run_board_contract()
    folders = payload["folders"]
    assert [folder["id"] for folder in folders[:6]] == [
        "smart-videos",
        "smart-images",
        "smart-in-work",
        "smart-review",
        "smart-to-publish",
        "smart-published",
    ]
    assert [folder["name"] for folder in folders[:6]] == [
        "Видео",
        "Изображения и исходники",
        "В работе",
        "На проверке",
        "К публикации",
        "Опубликовано",
    ]
    assert all(folder["smart"] and not folder["editable"] for folder in folders[:6])
    assert folders[6]["id"] == "real-folder"

    assert payload["smartChecks"] == [True, False]
    assert payload["videoFolderReference"] is None
    assert payload["filters"] == {
        "videos": ["media:video-1"],
        "images": ["media:image-1"],
        "work": ["task:work-1"],
        "review": ["task:review-1"],
        "publish": ["placement:publish-1"],
        "published": ["publication:published-1"],
    }


def test_finder_defaults_to_files_and_never_offers_smart_move_targets() -> None:
    payload = _run_board_contract()
    assert payload["defaultKeys"] == ["media:image-1", "media:video-1"]
    assert payload["moveHasSmartTarget"] is False
    assert payload["smartDropTarget"] is False
    assert payload["smartCreateUsesRoot"] is True
    assert payload["smartEditIsHidden"] is True


def test_visible_overflow_buttons_open_the_existing_context_menu_safely() -> None:
    payload = _run_board_contract()
    assert payload["hasContextHint"] is True
    assert payload["contextTriggerCount"] >= 10

    for marker in (
        'event.target.closest("[data-ce-v4-context-trigger]")',
        "openContextMenu(target, rect.right, rect.bottom + 4, trigger)",
        "system: row.dataset.systemFolder === \"true\"",
        "finderOrganizeMode() && !folder.system",
    ):
        assert marker in CONTEXT

    for marker in (
        ".workspace-board__context-trigger",
        ".workspace-board__folder-group-label",
        ".workspace-board__context-hint",
    ):
        assert marker in FINDER_CSS
