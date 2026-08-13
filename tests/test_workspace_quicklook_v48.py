from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
BOARD_PATH = APP / "workspace-board-view.js"
FINDER_PATH = APP / "workspace-os-v4-finder.js"
BOARD = BOARD_PATH.read_text(encoding="utf-8")
FINDER = FINDER_PATH.read_text(encoding="utf-8")
BOARD_CSS = (APP / "workspace-board.css").read_text(encoding="utf-8")
FINDER_CSS = (APP / "workspace-os-v4-finder.css").read_text(encoding="utf-8")
FIXTURE = (
    ROOT / "tests" / "fixtures" / "workspace_quicklook_v48_harness.html"
).read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_quicklook_reuses_the_single_drawer_owner_without_business_io() -> None:
    open_quicklook = _between(
        FINDER,
        "async function openQuickLook(",
        "\nfunction closeQuickLook(",
    )
    close_quicklook = _between(
        FINDER,
        "function closeQuickLook(",
        "\nfunction navigateQuickLook(",
    )
    renderer = _between(
        BOARD,
        "function formatQuickLookDuration(",
        "\nfunction itemCardMarkup(",
    )

    assert 'q("[data-workspace-item-drawer]", runtime.board)' in FINDER
    assert 'drawer.classList.add("ce-v4-quicklook-inline")' in open_quicklook
    assert 'board.classList.add("is-quicklook-inline")' in open_quicklook
    assert "selectCard(card);" in open_quicklook
    assert open_quicklook.index("selectCard(card);") < open_quicklook.index(
        "ensureSelectedDrawer(card)"
    )
    assert 'q("video", current.drawer)?.pause?.()' in close_quicklook
    assert 'data-workspace-item-key="${CSS.escape(current.cardKey)}"' in close_quicklook

    for forbidden in (
        "fetch(",
        "getApi",
        "CreatorApi",
        "localStorage",
        "sessionStorage",
        "navigate(",
        "location.hash",
        "startRealGeneration",
        "paid",
        "autoplay",
        "aria-modal",
    ):
        assert forbidden not in renderer

    assert FINDER.count("async function openQuickLook(") == 1
    assert FINDER.count("function closeQuickLook(") == 1
    assert BOARD.count("data-workspace-item-drawer") == 1


def test_quicklook_normalizer_and_renderer_keep_exact_optional_records() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for executable Quick Look contracts")
    module_url = BOARD_PATH.as_uri()
    probe = f"""
const mod = await import({json.dumps(module_url)});
const raw = {{
  capabilities: {{ move_items: false, research_artifacts: {{ read_only: true, scope: "project" }} }},
  items: [
    {{
      id: "video-1", entity_type: "media", title: "Video", mime_type: "video/mp4",
      artifact_class: "source", source_identity: "exact-source", duration_seconds: 61.5,
      version_count: 2, product_id: "product-1", product_name: "Product", task_id: "task-1"
    }},
    {{
      id: "research-1", entity_type: "research", title: "Research", status: "done",
      evidence_summary: "Exact evidence", selected_conclusions: ["Keep"],
      rejected_conclusions: ["Reject"], next_action: "Human decides",
      ai_receipt: {{ receipt_id: "receipt-1", status: "learned" }},
      disposition: {{ disposition_id: "decision-1", status: "edited" }}
    }},
    {{
      id: "generated-1", entity_type: "media", title: "Generated", mime_type: "video/mp4",
      artifact_class: "generated_output", actual_cost_minor: 90, currency: "USD",
      generation_selection_snapshot: {{
        provider: "runway", model: "gen4_turbo", model_public_label: "Runway Gen-4 Turbo",
        selection_source: "manual_choice", estimated_cost_minor: 100, currency: "USD",
        input_mode: "image", reference_count: 2
      }},
      review_history: [{{ status: "Accepted", reviewed_at: "2026-08-12T10:00:00Z" }}],
      publication_history: [{{ status: "Published", published_at: "2026-08-12T11:00:00Z" }}]
    }},
    {{
      id: "legacy-1", entity_type: "media", title: "Legacy", mime_type: "video/mp4",
      artifact_class: "generated_output"
    }}
  ]
}};
const board = mod.normalizeWorkspaceBoard(raw);
const render = (key) => mod.workspaceBoardMarkup(board, {{
  selectedFolderId: "all", selectedItemKey: key, entityType: "all", provenanceFilter: "all"
}});
process.stdout.write(JSON.stringify({{
  video: render("media:video-1"),
  research: render("research:research-1"),
  generated: render("media:generated-1"),
  legacy: render("media:legacy-1"),
  videoRecord: board.items.find((item) => item.key === "media:video-1"),
  generatedRecord: board.items.find((item) => item.key === "media:generated-1")
}}));
"""
    completed = subprocess.run(
        [node, "--input-type=module", "-e", probe],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    result = json.loads(completed.stdout)

    assert "exact-source" in result["video"]
    assert "1 мин. 1,5 сек." in result["video"]
    assert "Версий" in result["video"]
    assert "Product" in result["video"]
    assert "Задача" in result["video"]
    assert result["videoRecord"]["versionCount"] == 2

    for marker in (
        "Exact evidence",
        "Принятые выводы",
        "Keep",
        "Отклонённые выводы",
        "Reject",
        "Human decides",
        "Решение человека",
    ):
        assert marker in result["research"]

    for marker in (
        "Runway Gen-4 Turbo",
        "gen4_turbo",
        "Ручной выбор человека",
        "1,00 $",
        "0,90 $",
        "Accepted",
        "Published",
    ):
        assert marker in result["generated"]
    assert result["generatedRecord"]["generationQuickLook"]["model"] == "gen4_turbo"

    assert "Модель, стоимость и входы не переданы" in result["legacy"]
    assert "Runway Gen-4 Turbo" not in result["legacy"]
    assert "gen4_turbo" not in result["legacy"]
    assert "0 мин. ед." not in result["legacy"]
    assert "0 сек." not in result["legacy"]


def test_quicklook_fixture_covers_selection_keyboard_safety_and_all_content_types() -> None:
    for marker in (
        "spaceIgnoredInsideControl",
        "singleClickSelectsWithoutOpen",
        "doubleClickOpensOnce",
        "enterOpensOnce",
        "videoMetadataExact",
        "imageMetadataExact",
        "researchMetadataExact",
        "generatedMetadataExact",
        "legacyDoesNotInventModel",
        "visibleToolbarButton",
        "quickLookNoRouteMutation",
        "closeRestoresFocusAndSelection",
        "singleInlineOwner",
        "videoDoesNotAutoplay",
        "noApiOrPaidSideEffect",
        "noSignedUrlPersistence",
        "lowerObjectUnchanged",
        "noHorizontalOverflow",
        "controlsMeetTouchTarget",
    ):
        assert marker in FIXTURE

    assert "#/workspace/research?" in FIXTURE
    assert "#/workspace/ai?" in FIXTURE
    assert "window.ContentEngineFinderV4.closeQuickLook()" in FIXTURE


def test_quicklook_assets_parse_and_css_remains_balanced() -> None:
    assert BOARD_CSS.count("{") == BOARD_CSS.count("}")
    assert FINDER_CSS.count("{") == FINDER_CSS.count("}")
    assert ".workspace-board__quicklook-section" in BOARD_CSS
    assert ".workspace-board__quicklook-unavailable" in BOARD_CSS
    assert ".workspace-board__quicklook-sections" in FINDER_CSS
    assert "min-height: 44px" in _between(
        FINDER_CSS,
        ".ce-v4-quicklook-inline__controls button {",
        "\n.ce-v4-quicklook-inline__controls button:hover",
    )

    node = shutil.which("node")
    if not node:
        return
    for path in (BOARD_PATH, FINDER_PATH):
        completed = subprocess.run(
            [node, "--check", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
