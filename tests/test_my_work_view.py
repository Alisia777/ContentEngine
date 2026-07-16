from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = (ROOT / "web" / "app" / "my-work-view.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "my-work.css").read_text(encoding="utf-8")
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
CATALOG = (ROOT / "web" / "app" / "catalog.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "app" / "index.html").read_text(encoding="utf-8")


def _run_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required")
    with tempfile.TemporaryDirectory() as temporary_directory:
        workdir = Path(temporary_directory)
        (workdir / "subject.mjs").write_text(MODULE, encoding="utf-8")
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


def test_my_work_normalizes_server_counts_items_and_cursor() -> None:
    result = _run_module(
        """
        return subject.normalizeMyWork({
          counts: { total: 7, task: 2, action_required: 3, blockers: 2, overdue: 1 },
          items: [{
            item_type: "generation",
            id: "job-1",
            status: "processing",
            title: "Ролик Bombbar",
            deep_link: "#/workspace/generation",
            amount_minor: 23200,
            currency: "RUB",
            action_required: true,
            blocker: true,
          }],
          next_cursor: { updated_at: "2026-07-16T10:00:00Z", item_type: "generation", id: "job-1" },
        });
        """
    )

    assert result["counts"]["total"] == 7
    assert result["counts"]["actionRequired"] == 3
    assert result["counts"]["blockers"] == 2
    assert result["items"][0]["itemType"] == "generation"
    assert result["items"][0]["deepLink"] == "#/workspace/generation"
    assert result["items"][0]["actionRequired"] is True
    assert result["items"][0]["blocker"] is True
    assert result["nextCursor"]["id"] == "job-1"


def test_my_work_rejects_external_deep_links_and_unknown_filter_types() -> None:
    result = _run_module(
        """
        const work = subject.normalizeMyWork({
          items: [{
            item_type: "task",
            id: "task-1",
            status: "todo",
            title: "Работа",
            deep_link: "https://evil.example/phish",
          }],
        });
        const filters = subject.normalizeMyWorkFilters({
          query: "  товар  ",
          item_types: ["task", "unknown", "task"],
          statuses: ["blocked", "blocked"],
        });
        return { work, filters };
        """
    )

    assert result["work"]["items"][0]["deepLink"] == "#/workspace/tasks"
    assert result["filters"] == {
        "query": "товар",
        "itemTypes": ["task"],
        "statuses": ["blocked"],
    }


def test_notification_center_has_unread_actions_and_safe_links() -> None:
    result = _run_module(
        """
        const normalized = subject.normalizeNotifications({
          counts: { total: 2, unread: 1 },
          items: [
            { id: "n1", title: "Видео готово", severity: "success", deep_link: "#/workspace/generation", created_at: "2026-07-16T10:00:00Z" },
            { id: "n2", title: "Небезопасная ссылка", severity: "error", deep_link: "javascript:alert(1)", read_at: "2026-07-16T11:00:00Z" },
          ],
        });
        const html = subject.notificationCenterMarkup(normalized, { open: true });
        return {
          unread: normalized.counts.unread,
          safe: normalized.items[0].deepLink,
          unsafe: normalized.items[1].deepLink,
          errorTone: normalized.items[1].severity,
          hasMarkAll: html.includes("mark-all-notifications-read"),
          hasDialog: html.includes('role="dialog"'),
        };
        """
    )

    assert result == {
        "unread": 1,
        "safe": "#/workspace/generation",
        "unsafe": "",
        "errorTone": "danger",
        "hasMarkAll": True,
        "hasDialog": True,
    }


def test_my_work_css_is_theme_aware_responsive_and_reduced_motion_safe() -> None:
    assert "var(--portal-surface)" in CSS
    assert "var(--portal-primary)" in CSS
    assert ".my-work-layout" in CSS
    assert ".notification-drawer" in CSS
    assert '[data-deep-link-focused="true"]' in CSS
    assert "@media (max-width: 700px)" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS


def test_my_work_is_a_first_class_simple_workspace_route() -> None:
    assert '["work", "Моя работа", "●"]' in CATALOG
    simple_block = CATALOG.split(
        "export const SIMPLE_WORKSPACE_TAB_KEYS", 1
    )[1].split("]);", 1)[0]
    assert '"work"' in simple_block
    assert 'work: renderMyWorkSection' in APP
    assert 'state.api.myWork(myWorkRequestOptions(state.myWork.filters))' in APP
    assert 'from "./my-work-view.js?v=20260716.4"' in APP
    assert './my-work.css?v=20260716.4' in INDEX


def test_my_work_wires_saved_views_notifications_and_keyset_pagination() -> None:
    for marker in (
        'action === "toggle-work-notifications"',
        'action === "mark-all-notifications-read"',
        'action === "apply-my-work-view"',
        'action === "delete-my-work-view"',
        'action === "load-more-my-work"',
        'form.id === "my-work-filter-form"',
        'form.id === "save-my-work-view-form"',
        "state.api.markNotificationsRead",
        "state.api.markAllNotificationsRead",
        "state.api.savedWorkViews",
        "current.nextCursor",
        'is_default: makeDefault',
        'safeWorkspaceRouteEntityId("review")',
        "state.api.contentReviewStatus(routeReviewId)",
        "scheduleWorkspaceDeepLinkFocus(section)",
        'data-task-id="${escapeHtml(item.id || item.task_id || "")}"',
        'data-placement-id="${escapeHtml(item.id || item.placement_id || "")}"',
        'data-payout-id="${escapeHtml(item.id || item.payout_id || "")}"',
    ):
        assert marker in APP

    submit_saved = APP.split("async function submitSavedMyWorkView", 1)[1].split(
        "\nfunction handleChange", 1
    )[0]
    assert 'action: "set_default"' not in submit_saved


def test_awaiting_decision_is_rendered_as_an_actionable_filter_and_status() -> None:
    result = _run_module(
        """
        const html = subject.myWorkWorkspaceMarkup({
          work: {
            counts: { total: 1, review: 1, action_required: 1 },
            items: [{
              item_type: "review",
              id: "review-1",
              status: "awaiting_decision",
              title: "Проверка ролика",
              deep_link: "#/workspace/review",
              action_required: true,
            }],
          },
          filters: { statuses: ["awaiting_decision"] },
        });
        return {
          hasStatus: html.includes("Нужно решение"),
          hasFilter: html.includes('value="awaiting_decision"'),
          hasAction: html.includes("Принять решение"),
          hasIdentity: html.includes('data-work-item-id="review-1"'),
        };
        """
    )

    assert result == {
        "hasStatus": True,
        "hasFilter": True,
        "hasAction": True,
        "hasIdentity": True,
    }


def test_my_work_items_are_focusable_for_safe_deep_links() -> None:
    result = _run_module(
        """
        return subject.myWorkWorkspaceMarkup({
          work: {
            counts: { total: 1, task: 1 },
            items: [{
              item_type: "task",
              id: "task-1",
              status: "todo",
              title: "Снять ролик",
            }],
          },
        });
        """
    )

    assert 'data-work-item-id="task-1"' in result
    assert 'tabindex="-1"' in result


def test_notification_reads_invalidate_stale_fetches() -> None:
    assert "notificationsRequestId" in APP
    assert "notificationsMutationEpoch" in APP
    assert "beginMyWorkNotificationFetch()" in APP
    assert "myWorkNotificationFetchIsCurrent(notificationFetch)" in APP
    assert "myWorkNotificationFetchIsCurrent(request)" in APP
    mark_read = APP.split(
        "async function markMyWorkNotificationsRead(notificationIds)", 1
    )[1].split("async function loadMoreMyWork()", 1)[0]
    assert mark_read.count("state.myWork.notificationsMutationEpoch += 1") >= 2
    assert "state.myWork.notificationsRequestId += 1" in mark_read
