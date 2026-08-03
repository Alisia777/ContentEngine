from pathlib import Path
import json
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
SPEND = (APP_DIR / "generation-spend-view.js").read_text(encoding="utf-8")
MY_WORK = (APP_DIR / "my-work-view.js").read_text(encoding="utf-8")
RESEARCH = (APP_DIR / "product-research-view.js").read_text(encoding="utf-8")
CORE = (APP_DIR / "workspace-os-v4.js").read_text(encoding="utf-8")
FLOW_CSS = (APP_DIR / "workspace-os-v4-flow.css").read_text(encoding="utf-8")


def _run_module(source: str, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for markup contracts")
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


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_paused_budget_views_keep_save_as_the_only_visual_primary() -> None:
    result = _run_module(
        SPEND,
        """
        const data = {
          ok: true,
          policy: {
            paid_generation_enabled: false,
            daily_limit_minor: 10000,
            monthly_limit_minor: 50000,
            per_request_limit_minor: 2500,
            version: 4,
          },
          usage: {
            day: { remaining_minor: 10000 },
            month: { remaining_minor: 50000 },
          },
          campaigns: [{
            id: "campaign-1",
            name: "Тест товара",
            status: "paused",
            policy: {
              paid_generation_enabled: false,
              daily_limit_minor: 5000,
              monthly_limit_minor: 20000,
              per_request_limit_minor: 1500,
              version: 2,
            },
            usage: {
              day: { remaining_minor: 5000 },
              month: { remaining_minor: 20000 },
            },
          }],
        };
        const policy = subject.managerGenerationSpendMarkup(
          { status: "ready", data },
          { canEdit: true, view: "policy" },
        );
        const campaign = subject.managerGenerationSpendMarkup(
          { status: "ready", data },
          { canEdit: true, view: "campaign", campaignId: "campaign-1" },
        );
        return {
          policyPrimary: (policy.match(/data-primary-action="true"/g) || []).length,
          policySavePrimary: policy.includes('class="btn btn-small" type="submit" name="policy_action" value="save" data-primary-action="true"'),
          policyResumeSecondary: policy.includes('class="btn btn-secondary btn-small" type="submit" name="policy_action" value="resume"'),
          campaignPrimary: (campaign.match(/data-primary-action="true"/g) || []).length,
          campaignSavePrimary: campaign.includes('class="btn btn-small" type="submit" name="campaign_policy_action" value="save" data-primary-action="true"'),
          campaignResumeSecondary: campaign.includes('class="btn btn-secondary btn-small" type="submit" name="campaign_policy_action" value="resume"'),
        };
        """,
    )

    assert result == {
        "policyPrimary": 1,
        "policySavePrimary": True,
        "policyResumeSecondary": True,
        "campaignPrimary": 1,
        "campaignSavePrimary": True,
        "campaignResumeSecondary": True,
    }


def test_work_next_action_and_research_save_are_visually_primary() -> None:
    work = _run_module(
        MY_WORK,
        """
        const html = subject.myWorkWorkspaceMarkup({
          mode: "next",
          work: {
            counts: { total: 1, action_required: 1 },
            items: [{
              item_type: "task",
              id: "task-1",
              status: "todo",
              title: "Снять ролик",
              deep_link: "#/workspace/tasks?item=task-1",
              action_required: true,
            }],
          },
        });
        return {
          primary: (html.match(/data-primary-action="true"/g) || []).length,
          visualPrimary: html.includes('class="btn btn-small my-work-item-action"'),
          mismatchedSecondary: html.includes('class="btn btn-secondary btn-small my-work-item-action" href="#/workspace/tasks?item=task-1&amp;view=next" data-primary-action="true"'),
        };
        """,
    )
    assert work == {
        "primary": 1,
        "visualPrimary": True,
        "mismatchedSecondary": False,
    }

    result = _run_module(
        RESEARCH,
        """
        const html = subject.productResearchResultMarkup({}, { view: "brief" });
        return {
          savePrimary: html.includes('class="btn" type="submit" data-research-submit="save" data-primary-action="true"'),
          saveSecondary: html.includes('class="btn btn-secondary" type="submit" data-research-submit="save" data-primary-action="true"'),
        };
        """,
    )
    assert result == {"savePrimary": True, "saveSecondary": False}
    assert '[data-research-view="brief"] [data-research-submit="approve"]' in FLOW_CSS


def test_notifications_are_an_inline_work_view_without_a_subwindow() -> None:
    result = _run_module(
        MY_WORK,
        """
        const html = subject.myWorkWorkspaceMarkup({
          mode: "notifications",
          notifications: {
            counts: { total: 1, unread: 1 },
            items: [{
              id: "notification-1",
              title: "Ролик готов",
              message: "Можно переходить к проверке",
              severity: "success",
              deep_link: "#/workspace/review?review=review-1",
            }],
          },
        });
        return {
          inline: html.includes('data-work-view="notifications"') && html.includes("data-notification-view"),
          activeRoute: html.includes('href="#/workspace/work?view=notifications" class="is-active" aria-current="page"'),
          item: html.includes("notification-1"),
          markAll: html.includes("mark-all-notifications-read"),
          dialog: html.includes('role="dialog"') || html.includes('aria-modal="true"'),
          backdrop: html.includes("notification-backdrop"),
          drawerTrigger: html.includes("toggle-work-notifications"),
          inert: html.includes("inert"),
        };
        """,
    )
    assert result == {
        "inline": True,
        "activeRoute": True,
        "item": True,
        "markAll": True,
        "dialog": False,
        "backdrop": False,
        "drawerTrigger": False,
        "inert": False,
    }


def test_work_hash_mode_is_deterministic_without_an_app_js_argument() -> None:
    result = _run_module(
        MY_WORK,
        """
        const work = {
          counts: { total: 2, action_required: 2, blockers: 1 },
          items: [
            { item_type: "task", id: "regular", status: "todo", title: "Обычная задача", action_required: true },
            { item_type: "task", id: "blocker", status: "blocked", title: "Снять блокер", action_required: true, blocker: true },
          ],
        };
        const notifications = {
          counts: { total: 1, unread: 1 },
          items: [{ id: "notice", title: "Готово", severity: "success" }],
        };
        globalThis.location = { hash: "#/workspace/work?view=next" };
        const next = subject.myWorkWorkspaceMarkup({ work, notifications });
        globalThis.location.hash = "#/workspace/work?view=notifications";
        const notice = subject.myWorkWorkspaceMarkup({ work, notifications });
        return {
          nextMode: next.includes('data-work-view="next"'),
          nextItems: (next.match(/data-work-item-id=/g) || []).length,
          nextPrimary: (next.match(/data-primary-action="true"/g) || []).length,
          noticeMode: notice.includes('data-work-view="notifications"'),
          noticeItems: (notice.match(/data-work-item-id=/g) || []).length,
          noticeInline: notice.includes("data-notification-view"),
        };
        """,
    )
    assert result == {
        "nextMode": True,
        "nextItems": 1,
        "nextPrimary": 1,
        "noticeMode": True,
        "noticeItems": 0,
        "noticeInline": True,
    }


def test_menubar_has_notification_bell_while_navigation_counts_stay_stable() -> None:
    routes = _between(CORE, "const ROUTES = Object.freeze([", "const SECONDARY_ROUTES")
    secondary = _between(CORE, "const SECONDARY_ROUTES = Object.freeze([", "const ALL_ROUTES")
    menubar = _between(CORE, "function ensureMenubar() {", "function updateClock()")
    tools_keyboard = _between(CORE, "function handleToolsMenuKeydown(event) {", "async function toggleFullscreen()")

    assert routes.count("Object.freeze({ route:") == 6
    assert secondary.count("Object.freeze({ route:") == 7
    assert 'route: "/learn"' not in routes + secondary
    assert 'notifications.dataset.ceV4Notifications = "/workspace/work?view=notifications"' in menubar
    assert 'iconButton("", "Открыть уведомления", "bell")' in menubar
    assert "notificationControl.dataset.ceV4Notifications" in menubar
    assert 'route: "/workspace/work?view=notifications"' not in routes + secondary
    assert 'const ROLE_GATED_SECONDARY_ROUTES = new Set(["/workspace/research", "/workspace/team"])' in CORE
    authorization = _between(CORE, "function secondaryRouteIsAuthorized(route) {", "function createToolsMenuItem(item) {")
    sync = _between(CORE, "function syncToolsMenu() {", "function closeToolsMenu(")
    assert '.workspace-shell[data-workspace-section] .workspace-nav' in authorization
    assert 'String(link.getAttribute("href") || "").split("?")[0] === `#${route}`' in authorization
    assert "SECONDARY_ROUTES.filter((item) => secondaryRouteIsAuthorized(item.route))" in sync
    assert "existing.forEach((link) => link.remove())" in sync
    for key in ("ArrowDown", "ArrowUp", "Home", "End", "Escape"):
        assert key in tools_keyboard
