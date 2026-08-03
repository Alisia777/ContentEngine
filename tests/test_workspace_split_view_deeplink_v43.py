from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
FLOW_CSS = (APP_DIR / "workspace-os-v4-flow.css").read_text(encoding="utf-8")
FINDER = (APP_DIR / "workspace-os-v4-finder.js").read_text(encoding="utf-8")
FINDER_CSS = (APP_DIR / "workspace-os-v4-finder.css").read_text(encoding="utf-8")
MY_WORK = (APP_DIR / "my-work-view.js").read_text(encoding="utf-8")
RESEARCH = (APP_DIR / "product-research-view.js").read_text(encoding="utf-8")
SPEND = (APP_DIR / "generation-spend-view.js").read_text(encoding="utf-8")
PRACTICAL_REVIEW = (APP_DIR / "training-practical-review.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _flat(source: str) -> str:
    return re.sub(r"\s+", " ", source).strip()


def _run_module(source: str, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser markup contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        workdir = Path(temporary_directory)
        (workdir / "subject.mjs").write_text(source, encoding="utf-8")
        (workdir / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_work_views_make_next_literal_one_screen_one_primary_action() -> None:
    result = _run_module(
        MY_WORK,
        """
        const work = {
          counts: { total: 2, task: 2, action_required: 2, blockers: 1 },
          items: [
            {
              item_type: "task",
              id: "8a825c4f-7927-4af5-8c55-4ed18c7c8761",
              status: "todo",
              title: "Обычная задача",
              deep_link: "#/workspace/tasks?item=8a825c4f-7927-4af5-8c55-4ed18c7c8761",
              action_required: true,
            },
            {
              item_type: "task",
              id: "b7390192-6e97-4c68-a0e1-bfc2acb9751b",
              status: "blocked",
              title: "Снять блокер",
              deep_link: "#/workspace/tasks?item=b7390192-6e97-4c68-a0e1-bfc2acb9751b",
              action_required: true,
              blocker: true,
            },
          ],
        };
        const inspect = (mode) => {
          const html = subject.myWorkWorkspaceMarkup({ work, mode });
          return {
            mode: html.match(/data-work-view="([^"]+)"/)?.[1] || "",
            items: (html.match(/data-work-item-id=/g) || []).length,
            primary: (html.match(/data-primary-action="true"/g) || []).length,
          };
        };
        return { next: inspect("next"), queue: inspect("queue"), views: inspect("views") };
        """,
    )

    assert result == {
        "next": {"mode": "next", "items": 1, "primary": 1},
        "queue": {"mode": "queue", "items": 2, "primary": 0},
        "views": {"mode": "views", "items": 0, "primary": 0},
    }

    for selector in (
        '[data-work-view="next"] :is(',
        ".my-work-hero-actions",
        ".my-work-summary",
        ".my-work-sidebar",
        ".my-work-filter",
        '[data-work-view="queue"] .my-work-sidebar',
        '[data-work-view="views"] :is(.my-work-summary, .my-work-main)',
    ):
        assert selector in FLOW_CSS


def test_feedback_new_and_history_are_mutually_exclusive_action_views() -> None:
    feedback = _between(
        APP,
        "function renderFeedbackSection(",
        "function renderTeamSection(",
    )
    assert 'const feedbackView = requestedView === "history" ? "history" : "new"' in feedback
    assert 'const activePanel = feedbackView === "new" ?' in feedback
    assert 'data-feedback-view="${feedbackView}"' in feedback
    assert 'workspaceActionSwitch("feedback-action-switch"' in feedback
    assert 'items.map(feedbackCard)' in feedback
    assert feedback.count('data-primary-action="true"') == 1
    assert feedback.count("${activePanel}") == 1


def test_research_views_hide_every_competing_primary_action() -> None:
    render = _between(
        RESEARCH,
        "export function productResearchResultMarkup(",
        "export function readProductResearchBrief(",
    )
    route = _between(
        APP,
        "function renderProductResearchSection(",
        "function stopProductResearchPolling(",
    )
    assert '["evidence", "corrections", "brief", "approve", "handoff"].includes(view)' in render
    assert 'data-research-view="${researchView}"' in render
    assert "view: researchView" in route
    assert render.count('data-research-submit="save" data-primary-action="true"') == 1
    assert render.count('data-research-submit="approve" data-primary-action="true"') == 1

    for marker in (
        '[data-research-view="evidence"] :is(',
        ".product-research-brief",
        '[data-research-view="brief"] [data-research-submit="approve"]',
        '[data-research-view="corrections"] [data-research-submit="approve"]',
        '[data-research-view="approve"] [data-research-submit="save"]',
        '[data-research-view="handoff"] :is(',
    ):
        assert marker in FLOW_CSS


def test_finder_browse_and_organize_do_not_mix_action_surfaces() -> None:
    mode = _between(FINDER, "function finderMode()", "function sidebarParts()")
    toolbar = _between(FINDER, "function buildToolbar()", "function buildFolderSearch()")
    assert 'query.get("view") === "organize" ? "organize" : "browse"' in mode
    assert 'runtime.board.dataset.ceV4FinderMode = mode' in mode
    assert 'document.body.dataset.ceV4FinderMode = mode' in mode
    assert 'control.setAttribute("aria-current", active ? "page" : "false")' in mode
    assert toolbar.count("#/workspace/board?view=browse") == 1
    assert toolbar.count("#/workspace/board?view=organize") == 1

    assert 'body[data-ce-v4-finder-mode="browse"] :is(' in FINDER_CSS
    browse_rule = _between(
        FINDER_CSS,
        'body[data-ce-v4-finder-mode="browse"] :is(',
        'body.ce-v4-finder-route .workspace-board__filters',
    )
    assert ".workspace-board__folder-management" in browse_rule
    assert ".workspace-board__move-panel" in browse_rule
    assert ".workspace-board__drag-handle" in browse_rule
    assert 'body[data-ce-v4-finder-mode="organize"] .workspace-board__drawer-actions' in browse_rule
    assert "display: none !important" in browse_rule

    drag_handlers = _between(APP, "function workspaceBoardOrganizeMode()", "function setMediaInputFiles(")
    assert 'state.route.query.get("view") === "organize"' in drag_handlers
    assert drag_handlers.count("workspaceBoardOrganizeMode()") >= 4
    assert "event.preventDefault();" in drag_handlers


@pytest.mark.parametrize(
    ("function_name", "function_end", "id_name", "requested_name", "next_name", "fallback"),
    (
        (
            "renderTasksSection",
            "function taskQueueCard",
            "requestedTaskId",
            "requestedTask",
            "nextTask",
            "actionableItems",
        ),
        (
            "renderPlacementSection",
            "function placementHistoryCard",
            "requestedPlacementId",
            "requestedPlacement",
            "nextPlacement",
            "actionableItems",
        ),
        (
            "renderPayoutsSection",
            "function payoutsTable",
            "requestedPayoutId",
            "requestedPayout",
            "nextPayout",
            "actionablePayouts",
        ),
    ),
)
def test_valid_requested_uuid_never_falls_back_to_another_list_record(
    function_name: str,
    function_end: str,
    id_name: str,
    requested_name: str,
    next_name: str,
    fallback: str,
) -> None:
    renderer = _flat(
        _between(APP, f"function {function_name}(", function_end)
    )
    assert (
        f"const {requested_name} = {id_name} ? items.find(" in renderer
        and f") || null : null; const {next_name} = {id_name} ? {requested_name} : {fallback}[0] || null;"
        in renderer
    )
    assert f"{id_name} &&" in renderer


def test_generation_and_content_review_fetch_and_render_only_the_requested_uuid() -> None:
    loader = _between(APP, "async function loadSection(", "function beginMyWorkNotificationFetch(")
    generation = _between(APP, "function renderGenerationSection(", "function generationArchiveMarkup(")
    review = _between(APP, "function renderContentReviewSection(", "function selectPendingContentReviewMedia(")

    for marker in (
        'state.api.realGenerationStatus(routeGenerationJobId)',
        'String(deepLinkJob?.id || "") === routeGenerationJobId',
        "mergeGenerationDeepLinkedBatch(",
        'state.api.contentReviewStatus(routeReviewId)',
        "normalizedRouteRecord.id === routeReviewId",
        "state.contentReview.record = routeReviewId",
        "? routeRecord",
    ):
        assert marker in loader

    assert "const routeFilteredBatches = routeJobId" in generation
    assert "? batches.filter(" in generation
    assert ": filteredBatches" in generation
    assert "const exactReviewMissing = Boolean(" in review
    assert 'String(state.contentReview.record?.id || "") !== routeReviewId' in review
    assert "не подменил" in review
    assert re.search(
        r"else if\s*\(\s*!routeReviewId\s*&&\s*!state\.contentReview\.record\s*\)",
        review,
    )


def test_team_campaign_and_practical_review_details_are_exact_and_fail_closed() -> None:
    team = _between(APP, "function renderTeamSection(", "function managerDashboardSectionMarkup(")
    campaign = _between(SPEND, "function campaignSpendMarkup(", "function generationCampaignPolicyForm(")
    practical = _between(
        PRACTICAL_REVIEW,
        "export function trainingPracticalReviewQueueMarkup(",
        "export function syncTrainingPracticalSource(",
    )

    assert 'safeWorkspaceRouteEntityId("campaign")' in team
    assert 'safeWorkspaceRouteEntityId("review")' in team
    assert 'teamView === "review"' in team
    assert 'requestedPracticalReviewId = safeWorkspaceRouteEntityId("review")' in team
    assert "{ interactive: true, reviewId: requestedPracticalReviewId }" in _flat(team)
    assert "const requestedReviewId = cleanUuid(options.reviewId)" in practical
    assert "const visibleReviews = requestedReviewId" in practical
    assert "? reviews.filter((item) => item.id === requestedReviewId)" in practical
    assert ": reviews" in practical
    assert "reviews[0]" not in practical
    assert "#/workspace/team?view=review&amp;review=" in practical
    assert practical.count('data-primary-action="true"') == 1

    assert "const selectedCampaign = campaigns.find(" in campaign
    assert ") || null" in campaign
    assert "mode === \"campaign\" && selectedCampaign" in campaign
    assert "mode === \"campaign\" && !selectedCampaign" in campaign
    assert "campaigns[0]" not in campaign


def test_team_practical_review_detail_never_substitutes_a_neighbor() -> None:
    result = _run_module(
        PRACTICAL_REVIEW,
        """
        const first = "1ba8f48a-402b-44ab-8f8f-28d3ee62d36a";
        const second = "8ac6e390-b190-4bbb-87cf-24fce2779c3d";
        const missing = "dcb24f26-eceb-4089-89ca-574fd86ff19d";
        const reviews = [first, second].map((id, index) => ({
          id,
          status: "submitted",
          learner_name: `Участник ${index + 1}`,
          media_id: "84b173a2-7f99-45a8-a918-981a372f06a2",
          original_filename: `review-${index + 1}.mp4`,
          mime_type: "video/mp4",
        }));
        const inspect = (reviewId) => {
          const html = subject.trainingPracticalReviewQueueMarkup(
            reviews,
            { interactive: true, reviewId },
          );
          return {
            rows: (html.match(/<article class="training-practical-review"/g) || []).length,
            primary: (html.match(/data-primary-action="true"/g) || []).length,
            first: html.includes(first),
            second: html.includes(second),
            missingCopy: html.includes("не найдена"),
          };
        };
        return { exact: inspect(second), missing: inspect(missing) };
        """,
    )

    assert result == {
        "exact": {
            "rows": 1,
            "primary": 1,
            "first": False,
            "second": True,
            "missingCopy": False,
        },
        "missing": {
            "rows": 0,
            "primary": 0,
            "first": False,
            "second": False,
            "missingCopy": True,
        },
    }


def test_deep_link_focus_supports_only_real_uuid_parameters() -> None:
    target = _between(APP, "function workspaceDeepLinkTarget(", "function scheduleWorkspaceDeepLinkFocus(")
    validator = _between(APP, "function safeWorkspaceRouteEntityId(", "function workspaceDeepLinkTarget(")

    assert "getAll(parameterName)" in validator
    assert "values.length !== 1" in validator
    assert "[0-9a-f]{8}-[0-9a-f]{4}" in validator
    assert 'work: ["item"' not in target

    for marker in (
        'tasks: ["item"',
        'generation: ["job"',
        'review: ["review"',
        'placement: ["placement"',
        'payouts: ["payout"',
        'safeWorkspaceRouteEntityId("campaign")',
        'safeWorkspaceRouteEntityId("review")',
        "data-campaign-id",
        "data-practical-review-id",
    ):
        assert marker in target
