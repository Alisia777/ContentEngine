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

    create = _run_module(
        SPEND,
        """
        const data = {
          ok: true,
          policy: {
            paid_generation_enabled: true,
            daily_limit_minor: 10000,
            monthly_limit_minor: 50000,
            per_request_limit_minor: 2500,
            version: 4,
          },
          usage: {
            day: { remaining_minor: 10000 },
            month: { remaining_minor: 50000 },
          },
          campaigns: [],
        };
        const html = subject.managerGenerationSpendMarkup(
          { status: "ready", data },
          { canEdit: true, view: "new-campaign" },
        );
        return {
          primary: (html.match(/data-primary-action="true"/g) || []).length,
          createPrimary: html.includes('id="generation-campaign-create-form"')
            && html.includes('type="submit" data-primary-action="true">Создать кампанию</button>'),
        };
        """,
    )
    assert create == {"primary": 1, "createPrimary": True}


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
          filterSecondary: html.includes('<button class="btn btn-secondary" type="submit">Найти</button>'),
        };
        """,
    )
    assert work == {
        "primary": 1,
        "visualPrimary": True,
        "mismatchedSecondary": False,
        "filterSecondary": True,
    }

    delete_confirmation = _run_module(
        MY_WORK,
        """
        const html = subject.myWorkWorkspaceMarkup({
          mode: "next",
          savedViews: [{ id: "view-1", name: "Срочные", version: 2 }],
          pendingDeleteViewId: "view-1",
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
          deletePrimary: html.includes('class="btn btn-danger btn-small my-work-view-confirm__delete"')
            && html.includes('data-action="confirm-delete-my-work-view" data-primary-action="true"'),
          itemSecondary: html.includes('class="btn btn-secondary btn-small my-work-item-action"'),
        };
        """,
    )
    assert delete_confirmation == {
        "primary": 1,
        "deletePrimary": True,
        "itemSecondary": True,
    }

    result = _run_module(
        RESEARCH,
        """
        const html = subject.productResearchResultMarkup({}, { view: "brief" });
        return {
          savePrimary: html.includes('class="btn" type="submit" data-research-submit="save" data-primary-action="true"'),
          saveSecondary: html.includes('class="btn btn-secondary" type="submit" data-research-submit="save"'),
          primaryCount: (html.match(/data-primary-action="true"/g) || []).length,
        };
        """,
    )
    assert result == {"savePrimary": False, "saveSecondary": True, "primaryCount": 1}
    assert '[data-research-view="brief"] [data-research-submit="approve"]' in FLOW_CSS

    research_states = _run_module(
        RESEARCH,
        """
        const start = subject.productResearchInputMarkup();
        const approved = subject.productResearchResultMarkup(
          { taskIds: ["task-1"] },
          { view: "handoff" },
        );
        const tasks = subject.productResearchResultMarkup(
          { id: "run-1", draftId: "draft-1", taskIds: ["task-1"] },
          {
            view: "handoff",
            stageControl: {
              available: true,
              runId: "run-1",
              guidance: {
                currentDraftId: "draft-1",
                generationHandoffAllowed: true,
              },
            },
          },
        );
        return {
          startPrimary: (start.match(/data-primary-action="true"/g) || []).length,
          approvedPrimary: (approved.match(/data-primary-action="true"/g) || []).length,
          approvedDisabledSecondary: approved.includes('class="btn btn-secondary" type="submit" data-research-submit="approve"'),
          tasksPrimary: (tasks.match(/data-primary-action="true"/g) || []).length,
          tasksLinkPrimary: tasks.includes('href="#/workspace/tasks" data-primary-action="true"'),
        };
        """,
    )
    assert research_states == {
        "startPrimary": 1,
        "approvedPrimary": 1,
        "approvedDisabledSecondary": True,
        "tasksPrimary": 1,
        "tasksLinkPrimary": True,
    }


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


def test_dock_promotes_research_and_ai_while_tools_stay_compact_and_gated() -> None:
    routes = _between(CORE, "const ROUTES = Object.freeze([", "const SECONDARY_ROUTES")
    secondary = _between(CORE, "const SECONDARY_ROUTES = Object.freeze([", "const CONTEXT_ROUTES")
    context = _between(CORE, "const CONTEXT_ROUTES = Object.freeze([", "const ALL_ROUTES")
    menubar = _between(CORE, "function ensureMenubar() {", "function updateClock()")
    tools_keyboard = _between(CORE, "function handleToolsMenuKeydown(event) {", "async function toggleFullscreen()")

    assert routes.count("Object.freeze({ route:") == 8
    assert secondary.count("Object.freeze({ route:") == 2
    assert context.count("Object.freeze({ route:") == 2
    assert re.findall(r'route: "([^"]+)"', routes) == [
        "/workspace/home",
        "/workspace/board",
        "/workspace/generation",
        "/workspace/review",
        "/workspace/placement",
        "/workspace/stats",
        "/workspace/research",
        "/workspace/ai",
    ]
    assert re.findall(r'route: "([^"]+)"', secondary) == [
        "/workspace/team",
        "/workspace/feedback",
    ]
    assert re.findall(r'route: "([^"]+)"', context) == [
        "/workspace/tasks",
        "/workspace/work",
    ]
    assert 'route: "/learn"' not in routes + secondary
    assert 'notifications.dataset.ceV4Notifications = "/workspace/work?view=notifications"' in menubar
    assert 'iconButton("", "Открыть уведомления", "bell")' in menubar
    assert "notificationControl.dataset.ceV4Notifications" in menubar
    assert 'route: "/workspace/work?view=notifications"' not in routes + secondary
    assert 'const ROLE_GATED_ROUTES = new Set(["/workspace/research", "/workspace/ai", "/workspace/team"])' in CORE
    authorization = _between(CORE, "function routeIsAuthorized(route) {", "function authorizedRoutes(routes) {")
    sync = _between(CORE, "function syncToolsMenu() {", "function closeToolsMenu(")
    dock_sync = _between(CORE, "function syncDockAccess() {", "function ensureDock() {")
    mission = _between(CORE, "function openMission() {", "function spotlightRecords(")
    spotlight = _between(CORE, "function spotlightRecords(", "function renderSpotlight(")
    shortcuts = _between(CORE, "function handleKeydown(event) {", "function handleScroll() {")
    observer = _between(CORE, "function observeWorkspace() {", "function runMount() {")
    assert "shell?.dataset.workspaceAuthorizedRoutes" in authorization
    assert "if (declaredRoutes.length) return declaredRoutes.includes(route)" in authorization
    assert 'const navigation = q(".workspace-nav", shell)' in authorization
    assert 'String(link.getAttribute("href") || "").split("?")[0] === `#${route}`' in authorization
    assert "authorizedRoutes(SECONDARY_ROUTES)" in sync
    assert "existing.forEach((link) => link.remove())" in sync
    assert "authorizedRoutes(ROUTES)" in dock_sync
    assert "link.hidden = !authorized" in dock_sync
    assert 'link.setAttribute("aria-hidden", "true")' in dock_sync
    assert "authorizedRoutes(ROUTES).forEach" in mission
    assert "authorizedRoutes(ALL_ROUTES).map" in spotlight
    assert "authorizedRoutes(ROUTES)[Number(event.code.slice(-1)) - 1]" in shortcuts
    assert 'attributeFilter: ["data-workspace-authorized-routes"]' in observer
    for key in ("ArrowDown", "ArrowUp", "Home", "End", "Escape"):
        assert key in tools_keyboard


def test_dock_access_matrix_updates_without_recreating_the_dock() -> None:
    routes = _between(CORE, "const ROUTES = Object.freeze([", "const SECONDARY_ROUTES")
    gate = re.search(r"const ROLE_GATED_ROUTES = new Set\([^;]+;", CORE)
    authorization = _between(CORE, "function routeIsAuthorized(route) {", "function createToolsMenuItem(item) {")
    dock_sync = _between(CORE, "function syncDockAccess() {", "function ensureDock() {")
    assert gate is not None

    probe = f"""
{routes}
{gate.group(0)}
const shell = {{ dataset: {{ workspaceAuthorizedRoutes: "" }} }};
const links = ROUTES.map((item) => ({{
  dataset: {{ ceV4Route: item.route }},
  hidden: false,
  attributes: {{}},
  tooltip: {{ textContent: "" }},
  setAttribute(name, value) {{ this.attributes[name] = String(value); }},
  removeAttribute(name) {{ delete this.attributes[name]; }},
}}));
const runtime = {{ dock: {{}} }};
function q(selector, root) {{
  if (selector.includes("workspace-shell")) return shell;
  if (selector === ".ce-v4-dock__tooltip") return root?.tooltip || null;
  return null;
}}
function qa(selector) {{
  if (selector === "[data-ce-v4-route]") return links;
  return [];
}}
{authorization}
{dock_sync}
function snapshot(declaredRoutes) {{
  shell.dataset.workspaceAuthorizedRoutes = declaredRoutes.join(" ");
  syncDockAccess();
  return links.map((link) => ({{
    route: link.dataset.ceV4Route,
    hidden: link.hidden,
    ariaHidden: link.attributes["aria-hidden"] || "",
    label: link.attributes["aria-label"] || "",
  }}));
}}
const base = ["home", "board", "generation", "review", "placement", "stats"]
  .map((route) => `/workspace/${{route}}`);
process.stdout.write(JSON.stringify({{
  owner: snapshot([...base, "/workspace/research", "/workspace/ai", "/workspace/team"]),
  reviewer: snapshot([...base, "/workspace/ai"]),
  creator: snapshot(base),
}}));
"""
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the Dock access contract")
    result = subprocess.run(
        [node, "-e", probe],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    matrix = json.loads(result.stdout)

    owner_visible = [item for item in matrix["owner"] if not item["hidden"]]
    assert [item["route"] for item in owner_visible][-2:] == [
        "/workspace/research",
        "/workspace/ai",
    ]
    assert owner_visible[-2]["label"].endswith("⌥7")
    assert owner_visible[-1]["label"].endswith("⌥8")

    reviewer = {item["route"]: item for item in matrix["reviewer"]}
    assert reviewer["/workspace/research"]["hidden"] is True
    assert reviewer["/workspace/research"]["ariaHidden"] == "true"
    assert reviewer["/workspace/ai"]["hidden"] is False
    assert reviewer["/workspace/ai"]["label"].endswith("⌥7")

    creator = {item["route"]: item for item in matrix["creator"]}
    assert creator["/workspace/research"]["hidden"] is True
    assert creator["/workspace/ai"]["hidden"] is True


def test_research_and_team_expose_small_action_hierarchies() -> None:
    research = _between(APP, "function renderProductResearchSection() {", "function stopProductResearchPolling()")
    team = _between(APP, "function renderTeamSection(sectionState) {", "function managerDashboardSectionMarkup()")

    assert 'workspaceSequenceSwitch("research-action-sequence"' in research
    assert 'workspaceActionSwitch("research-action-switch"' not in research
    for view in ("evidence", "corrections", "brief", "approve", "handoff"):
        assert f'view: "{view}"' in research

    assert 'const teamGroup = ["invite", "access", "members"]' in team
    assert "const teamContextActions = teamGroup === \"people\"" in team
    assert 'workspaceActionSwitch("team-action-switch team-action-switch--groups"' in team
    assert 'workspaceActionSwitch("team-action-switch team-action-switch--context"' not in team
    assert '"team-action-switch team-action-switch--context"' in team
    for view in ("people", "reviews", "spend", "health"):
        assert f'view: "{view}"' in team

    assert ".workspace-action-sequence" in FLOW_CSS
    assert ".team-action-switch.team-action-switch--groups" in FLOW_CSS
    assert ".team-action-switch--context" in FLOW_CSS
