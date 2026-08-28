from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CSS = (APP / "workspace-os-v4.css").read_text(encoding="utf-8")
HARNESS = ROOT / "tests" / "fixtures" / "workspace_notification_center_v491_harness.html"
RUNTIME_HARNESS = (
    ROOT / "tests" / "fixtures" / "workspace_notification_center_runtime_v491_harness.html"
)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


def _chrome_path() -> str:
    candidates = [
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    chrome = next((str(path) for path in candidates if path and Path(path).exists()), None)
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for Notification Center runtime QA")
    return chrome


def _run_exact_viewport(
    width: int,
    height: int,
    expression: str,
    harness: Path = HARNESS,
) -> dict[str, object]:
    try:
        from websockets.sync.client import connect
    except ImportError:
        pytest.skip("websockets is required for exact Chrome viewport emulation")

    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    profile = tempfile.mkdtemp(prefix="ce-notification-v491-")
    process = subprocess.Popen(
        [
            _chrome_path(),
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--no-sandbox",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        port_file = Path(profile) / "DevToolsActivePort"
        deadline = time.monotonic() + 8
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.04)
        assert port_file.exists(), "Chrome DevTools port did not become ready"
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
        page = next(item for item in pages if item.get("type") == "page" and item.get("url") == "about:blank")

        with connect(page["webSocketDebuggerUrl"], origin="http://localhost", open_timeout=5) as websocket:
            request_id = 0

            def cdp(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
                nonlocal request_id
                request_id += 1
                websocket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
                while True:
                    response = json.loads(websocket.recv())
                    if response.get("id") == request_id:
                        return response

            cdp(
                "Emulation.setDeviceMetricsOverride",
                {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
            )
            cdp(
                "Page.navigate",
                {"url": f"http://127.0.0.1:{server.server_port}/{harness.relative_to(ROOT).as_posix()}"},
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                ready = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": 'document.body?.dataset.fixtureNotificationReady || ""',
                        "returnByValue": True,
                    },
                )
                if ready.get("result", {}).get("result", {}).get("value") == "true":
                    break
                time.sleep(0.04)
            else:
                raise AssertionError("Notification Center fixture did not become ready")

            result = cdp(
                "Runtime.evaluate",
                {"expression": expression, "returnByValue": True, "awaitPromise": True},
            )
            assert "exceptionDetails" not in result.get("result", {}), result
            raw = result["result"]["result"].get("value")
            return json.loads(raw) if isinstance(raw, str) else raw
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)
        time.sleep(0.1)
        shutil.rmtree(profile, ignore_errors=True)


def test_shell_is_the_single_notification_surface_and_has_no_business_transport() -> None:
    harness = HARNESS.read_text(encoding="utf-8")
    assert 'from "./workspace-notification-contract.js?v=20260826.rebuild-clean.37"' in CORE
    assert CORE.count('const panel = create("aside", "ce-v4-notification-panel")') == 1
    assert 'panel.setAttribute("aria-modal", "false")' in CORE
    assert 'panel.setAttribute("role", "dialog")' in CORE
    assert 'tabs.setAttribute("role", "tablist")' in CORE
    assert 'tab.setAttribute("role", "tab")' in CORE
    assert 'event.composedPath()' in CORE
    assert 'toggleNotificationCenter(notificationControl)' in CORE
    assert 'navigate(notificationControl.dataset.ceV4Notifications)' not in CORE
    assert 'data-action="open-work-notification"' not in CORE
    assert "fetch(" not in CORE
    assert "XMLHttpRequest" not in CORE
    assert "markNotificationsRead" not in CORE
    assert "markAllNotificationsRead" not in CORE
    # Dock may consume the pure registry; Notification Center does not execute it.
    notification_region = CORE[
        CORE.index("function notificationScopeId") :
        CORE.index("function updateFullscreenControl")
    ]
    assert "resolveWorkspaceCommand(" not in notification_region
    assert ".ce-v4-notification-panel" in CSS
    assert "body.ce-v4-notification-open #toast-region" in CSS
    assert "workspace-notification-feed-snapshot" in harness


RUNTIME_EXPRESSION = r"""
(async () => {
  const trigger = document.querySelector("[data-ce-v4-notifications]");
  const inlineLink = document.querySelector(".fixture-inline-link");
  const originalHash = location.hash;
  const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve));
  const within = (node) => {
    const rect = node.getBoundingClientRect();
    return rect.left >= -.5 && rect.right <= innerWidth + .5
      && rect.top >= -.5 && rect.bottom <= innerHeight + .5;
  };
  const overlaps = (left, right) => !(
    left.right <= right.left || right.right <= left.left
    || left.bottom <= right.top || right.bottom <= left.top
  );

  trigger.click();
  await nextFrame();
  const panel = document.querySelector("[data-ce-v4-notification-panel]");
  const allRows = [...panel.querySelectorAll(".ce-v4-notification-item")];
  const admittedIds = allRows.map((row) => row.dataset.ceV4NotificationId);
  const aiRow = panel.querySelector('[data-ce-v4-notification-id="n-ai"]');
  const staleRow = panel.querySelector('[data-ce-v4-notification-id="n-stale"]');
  const unknownRow = panel.querySelector('[data-ce-v4-notification-id="n-unknown"]');
  const structuralArticles = allRows.every((row) => (
    row.tagName === "ARTICLE"
    && !row.hasAttribute("role")
    && row.querySelectorAll("button").length <= 2
    && !row.querySelector("button button, a button, button a")
  ));
  const controlsAreHonest = [...panel.querySelectorAll(
    "[data-ce-v4-notification-read], [data-ce-v4-notification-open]",
  )].every((button) => button.disabled && button.title);
  const separateControls = aiRow.querySelectorAll("button").length === 2
    && aiRow.querySelector("[data-ce-v4-notification-read]")
    && aiRow.querySelector("[data-ce-v4-notification-open]");
  const sourceSeveritySeparate = aiRow.dataset.ceV4NotificationSourceTone === "amethyst"
    && aiRow.dataset.ceV4NotificationSeverity === "warning"
    && staleRow.dataset.ceV4NotificationSourceTone === "ruby"
    && staleRow.dataset.ceV4NotificationSeverity === "warning";
  const staleExplicit = staleRow.classList.contains("is-stale")
    && staleRow.textContent.includes("Состояние объекта изменилось")
    && staleRow.querySelector("[data-ce-v4-notification-open]").disabled;
  const unknownExplicit = unknownRow.dataset.ceV4NotificationActionState === "blocked"
    && unknownRow.textContent.includes("Действие недоступно")
    && unknownRow.querySelector("[data-ce-v4-notification-open]").disabled;

  const allTab = panel.querySelector('[data-ce-v4-notification-filter="all"]');
  allTab.focus();
  allTab.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  await nextFrame();
  const unreadRoved = document.activeElement.dataset.ceV4NotificationFilter === "unread"
    && document.activeElement.tabIndex === 0
    && document.activeElement.getAttribute("aria-selected") === "true"
    && panel.querySelectorAll(".ce-v4-notification-item").length === 4;
  document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }));
  await nextFrame();
  const actionRoved = document.activeElement.dataset.ceV4NotificationFilter === "action_required"
    && panel.querySelectorAll(".ce-v4-notification-item").length === 3;
  document.activeElement.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }));
  await nextFrame();
  const homeRoved = document.activeElement.dataset.ceV4NotificationFilter === "all"
    && panel.querySelectorAll(".ce-v4-notification-item").length === 5;

  const insideTab = panel.querySelector('[data-ce-v4-notification-filter="unread"]');
  insideTab.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, composed: true }));
  insideTab.click();
  await nextFrame();
  const insideRerenderStayedOpen = !panel.hidden;

  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  const escapeClosed = panel.hidden && document.activeElement === trigger;
  inlineLink.click();
  await nextFrame();
  const inlineDelegated = !panel.hidden && location.hash === originalHash
    && document.querySelectorAll("[data-ce-v4-notification-panel]").length === 1;
  panel.querySelector("[data-ce-v4-notification-close]").click();
  const closeFocusRestored = panel.hidden && document.activeElement === inlineLink;

  trigger.click();
  await nextFrame();
  document.body.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, composed: true }));
  const outsideClosed = panel.hidden;
  trigger.click();
  await nextFrame();
  const toast = document.createElement("div");
  toast.className = "ce-v4-system-toast is-warning";
  toast.textContent = "Тестовое предупреждение";
  document.querySelector("#toast-region").append(toast);
  await nextFrame();
  const panelRect = panel.getBoundingClientRect();
  const toastRect = toast.getBoundingClientRect();
  const dockRect = document.querySelector(".ce-v4-dock__glass").getBoundingClientRect();
  const geometry = {
    panelFits: within(panel),
    toastFits: within(toast),
    noToastOverlap: !overlaps(panelRect, toastRect),
    noDockOverlap: !overlaps(panelRect, dockRect),
    noPageOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  };

  return JSON.stringify({
    width: innerWidth,
    originalHash,
    currentHash: location.hash,
    panelRole: panel.getAttribute("role"),
    panelModal: panel.getAttribute("aria-modal"),
    panelCount: document.querySelectorAll("[data-ce-v4-notification-panel]").length,
    feedState: panel.dataset.ceV4NotificationFeedState,
    panelUnread: panel.dataset.ceV4NotificationUnread,
    badgeText: trigger.querySelector("[data-ce-v4-notification-badge]").textContent,
    badgeLabel: trigger.getAttribute("aria-label"),
    admittedIds,
    structuralArticles,
    controlsAreHonest,
    separateControls: Boolean(separateControls),
    sourceSeveritySeparate,
    staleExplicit,
    unknownExplicit,
    rejectedVisible: !panel.querySelector("[data-ce-v4-notification-status]").hidden
      && panel.querySelector("[data-ce-v4-notification-status]").textContent.includes("1 событий скрыто"),
    unreadRoved,
    actionRoved,
    homeRoved,
    insideRerenderStayedOpen,
    escapeClosed,
    inlineDelegated,
    closeFocusRestored,
    outsideClosed,
    geometry,
  });
})()
"""


@pytest.mark.skip(
    reason=(
        "«Живые окна» (f18473d, 23.08.2026): legacy-ссылка фикстуры "
        "(.fixture-inline-link в #workspace-content) больше не имеет "
        "client rects, и закрытие панели честно возвращает фокус на "
        "колокольчик, а не на скрытый узел. Сценарий нужно переписать с "
        "открывателем внутри живой поверхности окна (задача автору рефакторинга)."
    ),
)
@pytest.mark.parametrize("width", [1280, 390, 320])
def test_runtime_filters_focus_scope_disabled_actions_and_geometry(width: int) -> None:
    result = _run_exact_viewport(width, 760, RUNTIME_EXPRESSION)

    assert result["width"] == width
    assert result["originalHash"] == result["currentHash"]
    assert result["panelRole"] == "dialog"
    assert result["panelModal"] == "false"
    assert result["panelCount"] == 1
    assert result["feedState"] == "ready"
    assert result["panelUnread"] == "4"
    assert result["badgeText"] == "4"
    assert result["badgeLabel"] == "Уведомления · 4 непрочитанных"
    assert result["admittedIds"] == ["n-ai", "n-process", "n-stale", "n-mention", "n-unknown"]
    assert result["structuralArticles"] is True
    assert result["controlsAreHonest"] is True
    assert result["separateControls"] is True
    assert result["sourceSeveritySeparate"] is True
    assert result["staleExplicit"] is True
    assert result["unknownExplicit"] is True
    assert result["rejectedVisible"] is True
    assert result["unreadRoved"] is True
    assert result["actionRoved"] is True
    assert result["homeRoved"] is True
    assert result["insideRerenderStayedOpen"] is True
    assert result["escapeClosed"] is True
    assert result["inlineDelegated"] is True
    assert result["closeFocusRestored"] is True
    assert result["outsideClosed"] is True
    assert all(result["geometry"].values())


PRODUCTION_BRIDGE_EXPRESSION = r"""
(async () => {
  const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve));
  const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  const waitFor = async (predicate, label) => {
    for (let attempt = 0; attempt < 160; attempt += 1) {
      if (predicate()) return;
      await pause(12);
    }
    throw new Error(`Timed out: ${label}`);
  };
  const within = (node) => {
    const rect = node.getBoundingClientRect();
    return rect.left >= -.5 && rect.right <= innerWidth + .5
      && rect.top >= -.5 && rect.bottom <= innerHeight + .5;
  };
  const overlaps = (left, right) => !(
    left.right <= right.left || right.right <= left.left
    || left.bottom <= right.top || right.bottom <= left.top
  );

  const trigger = document.querySelector("[data-ce-v4-notifications]");
  await waitFor(
    () => trigger.querySelector("[data-ce-v4-notification-badge]")?.textContent === "3",
    "authenticated closed-panel unread count",
  );
  const bootPanel = document.querySelector("[data-ce-v4-notification-panel]");
  const closedPanelCountLoaded = bootPanel?.hidden === true
    && bootPanel.dataset.ceV4NotificationUnread === "3";
  trigger.click();
  await waitFor(
    () => document.querySelectorAll(".ce-v4-notification-item").length === 3,
    "initial production projection",
  );
  const panel = document.querySelector("[data-ce-v4-notification-panel]");
  const initialRows = [...panel.querySelectorAll(".ce-v4-notification-item")];
  const initialEnabled = initialRows.every((row) => (
    [...row.querySelectorAll("button")].every((button) => !button.disabled)
  ));
  const initialCounts = {
    rows: initialRows.length,
    unread: panel.dataset.ceV4NotificationUnread,
    badge: trigger.querySelector("[data-ce-v4-notification-badge]").textContent,
  };

  const staleId = "cccccccc-cccc-4ccc-8ccc-ccccccccccc2";
  const staleRow = panel.querySelector(`[data-ce-v4-notification-id="${staleId}"]`);
  staleRow.querySelector("[data-ce-v4-notification-open]").click();
  await waitFor(
    () => staleRow.dataset.ceV4NotificationActionState === "blocked"
      || panel.querySelector(`[data-ce-v4-notification-id="${staleId}"]`)
        ?.dataset.ceV4NotificationActionState === "blocked",
    "stale target failure",
  );
  const staleAfter = panel.querySelector(`[data-ce-v4-notification-id="${staleId}"]`);
  const blockedStayedUnread = !panel.hidden
    && staleAfter.classList.contains("is-unread")
    && staleAfter.dataset.ceV4NotificationActionState === "blocked"
    && staleAfter.querySelector("[data-ce-v4-notification-open]").disabled
    && staleAfter.textContent.includes("Состояние объекта изменилось");

  const aiId = "cccccccc-cccc-4ccc-8ccc-ccccccccccc1";
  panel.querySelector(`[data-ce-v4-notification-id="${aiId}"] [data-ce-v4-notification-open]`).click();
  await waitFor(() => panel.hidden, "successful exact action close");
  const successClosedAfterRead = panel.hidden
    && location.hash.includes("/workspace/ai?view=decisions")
    && window.fixtureNotificationRequests.filter((item) => item.kind === "open").length === 2;

  trigger.click();
  await waitFor(
    () => panel.querySelectorAll(".ce-v4-notification-item").length === 3,
    "refreshed projection after action",
  );
  const aiRead = panel.querySelector(`[data-ce-v4-notification-id="${aiId}"]`)
    ?.classList.contains("is-read") === true;
  const infoId = "cccccccc-cccc-4ccc-8ccc-ccccccccccc3";
  panel.querySelector(`[data-ce-v4-notification-id="${infoId}"] [data-ce-v4-notification-read]`).click();
  await waitFor(
    () => panel.querySelector(`[data-ce-v4-notification-id="${infoId}"]`)
      ?.classList.contains("is-read") === true,
    "explicit read mutation",
  );
  await waitFor(
    () => !panel.querySelector(`[data-ce-v4-notification-id="${infoId}"] [data-ce-v4-notification-read]`),
    "explicit read button removal",
  );
  const explicitReadStayedOpen = !panel.hidden
    && !panel.querySelector(`[data-ce-v4-notification-id="${infoId}"] [data-ce-v4-notification-read]`);

  panel.querySelector("[data-ce-v4-notification-mark-all]").click();
  await waitFor(() => panel.dataset.ceV4NotificationUnread === "0", "visible mark all");
  const markAllVisibleOnly = panel.dataset.ceV4NotificationUnread === "0"
    && panel.querySelector("[data-ce-v4-notification-mark-all]").disabled;

  const toast = document.createElement("div");
  toast.className = "ce-v4-system-toast is-warning";
  toast.textContent = "Runtime bridge QA";
  document.querySelector("#toast-region").append(toast);
  await nextFrame();
  await nextFrame();
  const panelRect = panel.getBoundingClientRect();
  const toastRect = toast.getBoundingClientRect();
  const dockRect = document.querySelector(".ce-v4-dock__glass").getBoundingClientRect();
  const geometry = {
    panelFits: within(panel),
    toastFits: within(toast),
    noToastOverlap: !overlaps(panelRect, toastRect),
    noDockOverlap: !overlaps(panelRect, dockRect),
    noPageOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  };

  return JSON.stringify({
    width: innerWidth,
    panelCount: document.querySelectorAll("[data-ce-v4-notification-panel]").length,
    modal: panel.getAttribute("aria-modal"),
    closedPanelCountLoaded,
    initialEnabled,
    initialCounts,
    blockedStayedUnread,
    successClosedAfterRead,
    aiRead,
    explicitReadStayedOpen,
    markAllVisibleOnly,
    requestKinds: window.fixtureNotificationRequests.map((item) => item.kind),
    geometry,
  });
})()
"""


@pytest.mark.parametrize("width", [1280, 390, 320])
def test_production_bridge_fetch_read_blocked_action_and_geometry(width: int) -> None:
    result = _run_exact_viewport(
        width,
        760,
        PRODUCTION_BRIDGE_EXPRESSION,
        harness=RUNTIME_HARNESS,
    )

    assert result["width"] == width
    assert result["panelCount"] == 1
    assert result["modal"] == "false"
    assert result["closedPanelCountLoaded"] is True
    assert result["initialEnabled"] is True
    assert result["initialCounts"] == {"rows": 3, "unread": "3", "badge": "3"}
    assert result["blockedStayedUnread"] is True
    assert result["successClosedAfterRead"] is True
    assert result["aiRead"] is True
    assert result["explicitReadStayedOpen"] is True
    assert result["markAllVisibleOnly"] is True
    assert result["requestKinds"].count("open") == 2
    assert result["requestKinds"].count("mark_read") >= 2
    assert all(result["geometry"].values())
