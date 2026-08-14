from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW = (ROOT / "web/app/workspace-board-view.js").read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
EXACT_SOURCE = (ROOT / "web/app/workspace-ai-exact-youtube-sources.js").read_text(
    encoding="utf-8"
)
OPERATOR_MIGRATION = (
    ROOT / "supabase/migrations/202608120008_operator_project_research_ai.sql"
).read_text(encoding="utf-8")
BOARD_CSS = (ROOT / "web/app/workspace-board.css").read_text(encoding="utf-8")
FINDER_CSS = (ROOT / "web/app/workspace-os-v4-finder.css").read_text(encoding="utf-8")


def _run_contract() -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable Files UI contracts")

    contract = r"""
import {
  normalizeWorkspaceBoard,
  workspaceBoardMarkup,
  workspaceBoardPaginationState,
} from './subject.mjs';

const sourceId = '11111111-1111-4111-8111-111111111111';
const resultId = '22222222-2222-4222-8222-222222222222';
const runId = '33333333-3333-4333-8333-333333333333';
const receiptId = '44444444-4444-4444-8444-444444444444';
const ownerId = '55555555-5555-4555-8555-555555555555';
const employeeId = '66666666-6666-4666-8666-666666666666';
const board = normalizeWorkspaceBoard({
  capabilities: {
    manage_folders: false,
    move_items: true,
    research_artifacts: { read_only: true, scope: 'own' },
  },
  folders: [
    { id: 'sources', name: 'Исходники', system_role: 'sources' },
    { id: 'drafts', name: 'Черновики', system_role: 'drafts' },
  ],
  items: [
    {
      id: sourceId, entity_type: 'media', title: 'Фото товара', status: 'ready',
      folder_id: 'sources', artifact_class: 'source', lifecycle_stage: 'sources',
      owner_id: ownerId, owner_name: 'Мария',
      can_move: false,
    },
    {
      id: resultId, entity_type: 'media', title: 'Созданный ролик', status: 'ready',
      folder_id: 'drafts', artifact_class: 'generated_output', lifecycle_stage: 'drafts',
      can_move: true,
    },
  ],
  research_artifacts: [
    {
      id: runId,
      entity_type: 'research',
      status: 'completed',
      created_by: employeeId,
      created_by_name: 'Иван',
      read_only: true,
      can_move: false,
      deep_link: `#/workspace/research?project_id=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa&run=${runId}`,
      ai_receipt: {
        receipt_id: receiptId,
        status: 'pending',
        deep_link: `#/workspace/ai?project_id=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa&category=food&receipt=${receiptId}`,
      },
    },
  ],
});

const render = (provenanceFilter, selectedFolderId = 'all', selectedItemKey = '') =>
  workspaceBoardMarkup(board, {
    provenanceFilter,
    selectedFolderId,
    selectedItemKey,
    entityType: 'media',
  });
const keys = (html) => [...html.matchAll(/data-workspace-item-key="([^"]+)"/g)]
  .map((match) => match[1]);
const allHtml = render('all');
const sourceHtml = render('source');
const researchHtml = render('research', 'all', `research:${runId}`);
const generatedHtml = render('generated_output');
const rootHtml = render('research', 'root');
const landingHtml = workspaceBoardMarkup(board, {
  landingOverview: true,
  selectedFolderId: 'all',
  entityType: 'all',
  provenanceFilter: 'all',
});
const sourceDetailHtml = workspaceBoardMarkup(board, {
  selectedFolderId: 'all',
  selectedItemKey: `media:${sourceId}`,
  entityType: 'all',
  provenanceFilter: 'all',
  viewerProfileId: ownerId,
  viewerName: 'Мария',
});

process.stdout.write(JSON.stringify({
  capability: board.capabilities.researchArtifacts,
  entityTypes: board.entityTypes,
  itemFacts: board.items.map(({ id, entityType, movable, readOnly }) => ({ id, entityType, movable, readOnly })),
  allKeys: keys(allHtml),
  sourceKeys: keys(sourceHtml),
  researchKeys: keys(researchHtml),
  generatedKeys: keys(generatedHtml),
  rootKeys: keys(rootHtml),
  filterLabels: ['Источники', 'Исследования', 'Результаты'].every((label) => allHtml.includes(`>${label}</option>`)),
  researchHasNoMove: !researchHtml.includes('data-workspace-drag-item')
    && !researchHtml.includes('data-ce-v4-select-item'),
  researchJournalCopy: researchHtml.includes('Отдельный журнал исследования'),
  exactResearchLink: researchHtml.includes(`href="#/workspace/research?project_id=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa&amp;run=${runId}"`),
  exactReceiptLink: researchHtml.includes(`href="#/workspace/ai?project_id=aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa&amp;category=food&amp;receipt=${receiptId}"`),
  neutralReceiptLabel: researchHtml.includes('Открыть квитанцию в ИИ-центре')
    && !researchHtml.includes('Открыть свою квитанцию'),
  creators: board.items.map(({ id, creatorId, creatorName }) => ({ id, creatorId, creatorName })),
  ownSourceAttribution: sourceDetailHtml.includes('<dt>Загрузил</dt>')
    && sourceDetailHtml.includes('Мария (вы)'),
  projectResearchAttribution: researchHtml.includes('<dt>Создал</dt>')
    && researchHtml.includes('Иван'),
  landingOverview: landingHtml.includes('data-overview-kind="source"')
    && landingHtml.includes('data-overview-kind="research"')
    && landingHtml.includes('data-overview-kind="generated_output"')
    && landingHtml.includes('Исследования')
    && landingHtml.includes('не является папкой')
    && !landingHtml.includes('class="workspace-board__grid"'),
  honestAllCount: /<span>Все файлы<\/span>\s*<small>3<\/small>/.test(landingHtml),
  stalePagination: workspaceBoardPaginationState({
    has_more: true,
    next_cursor: { updated_at: '2026-08-12T12:00:00Z', id: sourceId },
  }),
  exactPagination: workspaceBoardPaginationState({
    has_more: true,
    next_cursor: { updated_at: '2026-08-12T12:00:00Z', id: sourceId },
  }, true),
}));
"""

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(VIEW, encoding="utf-8")
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


def test_files_ui_separates_source_research_and_generated_without_fake_folders() -> None:
    result = _run_contract()

    assert result["capability"] == {"readOnly": True, "scope": "own"}
    assert result["entityTypes"] == ["media", "task"]
    assert result["filterLabels"] is True
    assert result["sourceKeys"] == ["media:11111111-1111-4111-8111-111111111111"]
    assert result["researchKeys"] == ["research:33333333-3333-4333-8333-333333333333"]
    assert result["generatedKeys"] == ["media:22222222-2222-4222-8222-222222222222"]
    assert result["rootKeys"] == []
    assert result["researchJournalCopy"] is True
    submit_filters = APP[
        APP.index("async function submitWorkspaceBoardFilters(") :
        APP.index("async function archiveWorkspaceBoardFolder(")
    ]
    assert '["all", "media", "task"].includes(' in submit_filters
    assert '? requestedEntityType : "all"' in submit_filters
    assert '["media", "task"]' in VIEW


def test_files_ui_honors_server_item_move_rights_and_exact_research_links() -> None:
    result = _run_contract()
    by_id = {item["id"]: item for item in result["itemFacts"]}

    assert by_id["11111111-1111-4111-8111-111111111111"]["movable"] is False
    assert by_id["22222222-2222-4222-8222-222222222222"]["movable"] is True
    assert by_id["33333333-3333-4333-8333-333333333333"] == {
        "id": "33333333-3333-4333-8333-333333333333",
        "entityType": "research",
        "movable": False,
        "readOnly": True,
    }
    assert result["researchHasNoMove"] is True
    assert result["exactResearchLink"] is True
    assert result["exactReceiptLink"] is True
    assert result["neutralReceiptLabel"] is True
    assert result["ownSourceAttribution"] is True
    assert result["projectResearchAttribution"] is True
    creators = {item["id"]: item for item in result["creators"]}
    assert creators["11111111-1111-4111-8111-111111111111"] == {
        "id": "11111111-1111-4111-8111-111111111111",
        "creatorId": "55555555-5555-4555-8555-555555555555",
        "creatorName": "Мария",
    }
    assert creators["33333333-3333-4333-8333-333333333333"] == {
        "id": "33333333-3333-4333-8333-333333333333",
        "creatorId": "66666666-6666-4666-8666-666666666666",
        "creatorName": "Иван",
    }
    assert result["stalePagination"] == {
        "hasMore": True,
        "nextCursor": {
            "updated_at": "2026-08-12T12:00:00Z",
            "id": "11111111-1111-4111-8111-111111111111",
        },
    }
    assert result["exactPagination"] == {"hasMore": False, "nextCursor": None}


def test_files_ui_styles_research_as_a_distinct_read_only_artifact() -> None:
    for css in (BOARD_CSS, FINDER_CSS):
        assert '.workspace-board__item[data-entity-type="research"]' in css
    assert ".workspace-board__research-links" in BOARD_CSS


def test_files_ui_lands_on_semantic_overview_and_counts_the_visible_universe() -> None:
    result = _run_contract()
    click_owner = APP[
        APP.index("async function handleClick(") : APP.index("async function handleSubmit(")
    ]
    paid_research_submit = APP[
        APP.index("async function submitProductResearchStart(") : APP.index(
            "async function submitProductResearchMarketCategory("
        )
    ]

    assert result["landingOverview"] is True
    assert result["honestAllCount"] is True
    assert 'landingOverview: Boolean(' in APP
    assert 'action === "select-workspace-provenance"' in click_owner
    assert 'action === "select-workspace-provenance"' not in paid_research_submit
    assert click_owner.index('action === "select-workspace-folder"') < click_owner.index(
        'action === "select-workspace-provenance"'
    ) < click_owner.index('action === "open-workspace-item"')
    assert 'action: "select-workspace-provenance"' in VIEW
    assert '.workspace-board__overview-grid' in BOARD_CSS
    assert 'grid-template-columns: minmax(0, 1fr);' in BOARD_CSS


def test_files_api_and_route_use_exact_server_media_identity() -> None:
    workspace_browser = API[API.index("  workspaceBrowser(options"): API.index("  createWorkspaceFolder(")]
    project_media = API[API.index("  projectMedia("): API.index("  projectPlacement(")]
    load_section = APP[APP.index("async function loadSection("): APP.index("function beginMyWorkNotificationFetch(")]
    exact_media = APP[APP.index("function exactProjectMediaDeepLinkRecord("): APP.index("function mergeProjectMediaDeepLink(")]
    merge_media = APP[APP.index("function mergeProjectMediaDeepLink("): APP.index("function prependExactPlacementItem(")]

    assert 'options.artifact_classes' in workspace_browser
    assert 'new Set(["source", "generated_output", "unclassified"])' in workspace_browser
    assert 'payload.artifact_classes' in workspace_browser
    assert '["generation", "review", "files"]' in project_media
    assert '["generation", "review", "board"].includes(section)' in load_section
    assert 'section === "board" ? "files" : section' in load_section
    assert 'exactMedia?.workspace_item_key || `media:${routeMediaId}`' in load_section
    assert 'if (section === "board" && exactMediaRecord)' in load_section
    assert 'state.workspaceBoard.query = ""' in load_section
    assert 'state.workspaceBoard.hasMore = false' in load_section
    assert 'state.workspaceBoard.nextCursor = null' in load_section
    assert 'acceptedWorkspaceMediaDeepLink = true' in load_section
    assert 'workspaceBoardPaginationState(' in load_section
    assert load_section.index('acceptedWorkspaceMediaDeepLink = true') < load_section.index(
        'workspaceBoardPaginationState('
    )
    assert '["generation", "review", "files"].includes(normalizedSurface)' in exact_media
    assert 'normalizedSurface === "files" ? "items" : "media"' in merge_media
    assert 'resultProjectId !== normalizedProjectId' in exact_media
    assert 'exactMediaId !== normalizedMediaId' in exact_media
    assert 'return null' in exact_media


def test_exact_youtube_restore_link_targets_the_attached_media_not_the_source_ledger() -> None:
    assert "media: attachedMediaId" in EXACT_SOURCE
    assert "youtube_source: clean(source.id, 64)" in EXACT_SOURCE
    assert "'&media=' || media.id::text" in OPERATOR_MIGRATION
    assert "'&youtube_source=' || source.id::text$old_exact_files_link$" in OPERATOR_MIGRATION
