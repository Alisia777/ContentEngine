#!/usr/bin/env python3
"""Headless Chrome smoke for the real Desktop generation route.

The small diagnostic workbench remains covered, but the release evidence comes
from the authenticated ``#/workspace/generation`` screen and its real
``#mock-batch-form`` integration.
"""

from __future__ import annotations

import argparse
import base64
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
# 8767 — РАБОЧИЙ портал оператора (прод-Supabase, контейнер local-web).
# Зонды обязаны ездить только по песочнице: 8768, контейнер sandbox-web,
# раздаёт .local/site с локальным Supabase.
LOCAL_DESKTOP_ORIGIN = "http://127.0.0.1:8768"
UPLOAD_PROBE_MP4 = ROOT / "web" / "app" / "assets" / "training" / "ugc_bloody_peel_8s.mp4"
LOGIN_READY_TIMEOUT_SECONDS = 30


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        del args


def chrome_path() -> str:
    candidates = [
        shutil.which("chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise SystemExit("Chrome/Chromium is required for dev-browser-smoke")


def normalized_project_id(value: str) -> str:
    try:
        return str(UUID(str(value or "").strip()))
    except (ValueError, TypeError, AttributeError) as error:
        raise SystemExit("A valid local workspace project UUID is required") from error


def local_project_id() -> str:
    path = ROOT / ".local" / "project.local.json"
    if not path.is_file():
        raise SystemExit("Local workspace project was not provisioned")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("Local workspace project file is invalid") from error
    if not isinstance(payload, dict) or set(payload) != {"project_id"}:
        raise SystemExit("Local workspace project file must contain only project_id")
    return normalized_project_id(str(payload.get("project_id") or ""))


def generated_desktop_is_live(site: Path) -> bool:
    config_path = site / "config.js"
    index_path = site / "index.html"
    if not config_path.is_file() or not index_path.is_file():
        return False
    expected = config_path.read_bytes()
    expected_index = index_path.read_bytes()
    if len(expected) > 1_048_576 or len(expected_index) > 1_048_576:
        return False
    try:
        with urllib.request.urlopen(
            f"{LOCAL_DESKTOP_ORIGIN}/config.js",
            timeout=2,
        ) as response:
            body = response.read(1_048_577)
        with urllib.request.urlopen(
            f"{LOCAL_DESKTOP_ORIGIN}/",
            timeout=2,
        ) as response:
            index_body = response.read(1_048_577)
    except (OSError, urllib.error.URLError):
        return False
    return body == expected and index_body == expected_index


def smoke(
    site: Path,
    output: Path,
    project_id: str,
    finder_project_id: str = "",
) -> list[dict[str, str]]:
    try:
        from websockets.sync.client import connect
    except ImportError as error:
        raise SystemExit("websockets is required for dev-browser-smoke") from error
    project_id = normalized_project_id(project_id)
    finder_project_id = (
        normalized_project_id(finder_project_id) if finder_project_id else ""
    )
    output.mkdir(parents=True, exist_ok=True)
    server: ThreadingHTTPServer | None = None
    if not generated_desktop_is_live(site):
        try:
            server = ThreadingHTTPServer(
                ("127.0.0.1", 8767),
                lambda *args, **kwargs: QuietHandler(
                    *args, directory=str(site), **kwargs
                ),
            )
        except OSError as error:
            raise SystemExit(
                "Port 8767 is occupied, but the generated local Desktop is unavailable"
            ) from error
        threading.Thread(target=server.serve_forever, daemon=True).start()
    profiles_root = ROOT / ".dev-artifacts" / "browser-smoke" / "profiles"
    profiles_root.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(
        prefix="contentengine-browser-smoke-",
        dir=profiles_root,
    ))
    process: subprocess.Popen[bytes] | None = None
    results: list[dict[str, str]] = []
    try:
        process = subprocess.Popen([
            chrome_path(), "--headless=new", "--disable-gpu", "--disable-extensions", "--no-sandbox",
            "--remote-debugging-port=0", "--remote-allow-origins=*", f"--user-data-dir={profile}", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        port_file = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 12
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not port_file.exists():
            raise SystemExit("Chrome DevTools did not become ready")
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
        page = next(item for item in pages if item.get("type") == "page")
        # max_size=None: снимок всей страницы больше мегабайта по умолчанию,
        # и без снятия предела websocket рвётся на первом же скриншоте.
        with connect(
            page["webSocketDebuggerUrl"],
            origin="http://localhost",
            open_timeout=5,
            max_size=None,
        ) as websocket:
            request_id = 0
            console_events: list[dict[str, object]] = []
            network_events: list[dict[str, object]] = []

            def cdp(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
                nonlocal request_id
                request_id += 1
                websocket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
                while True:
                    response = json.loads(websocket.recv())
                    if response.get("id") == request_id:
                        if "error" in response:
                            raise RuntimeError(str(response["error"]))
                        return response
                    event_method = response.get("method")
                    if event_method in {
                        "Runtime.consoleAPICalled",
                        "Runtime.exceptionThrown",
                    }:
                        console_events.append(response)
                    elif event_method == "Network.loadingFailed":
                        network_events.append({
                            "method": event_method,
                            "errorText": response.get("params", {}).get("errorText"),
                            "type": response.get("params", {}).get("type"),
                        })
                    elif event_method == "Network.responseReceived":
                        network_response = response.get("params", {}).get("response", {})
                        network_events.append({
                            "method": event_method,
                            "url": network_response.get("url"),
                            "status": network_response.get("status"),
                            "mimeType": network_response.get("mimeType"),
                        })

            def desktop_login_diagnostics() -> dict[str, object]:
                evaluated = cdp("Runtime.evaluate", {
                    "expression": """
JSON.stringify({
  href: location.href,
  hash: location.hash,
  readyState: document.readyState,
  title: document.title,
  emailInput: Boolean(document.querySelector('input[type=email]')),
  passwordInput: Boolean(document.querySelector('input[type=password]')),
  bootFailure: Boolean(document.querySelector('.boot-screen--failed')),
  mainText: (document.querySelector('#main-content')?.textContent || '').trim().slice(0, 1_000),
  appText: (document.querySelector('#app')?.textContent || '').trim().slice(0, 1_000),
  moduleResources: performance.getEntriesByType('resource')
    .filter((entry) => entry.name.includes('supabase') || entry.name.includes('app.js'))
    .map((entry) => ({ name: entry.name, duration: Math.round(entry.duration), transferSize: entry.transferSize })),
})
""",
                    "returnByValue": True,
                })
                raw = evaluated.get("result", {}).get("result", {}).get("value")
                try:
                    diagnostic = json.loads(raw) if isinstance(raw, str) else {"probe": raw}
                except json.JSONDecodeError:
                    diagnostic = {"probe": raw}
                diagnostic["console_events"] = console_events[-12:]
                diagnostic["network_events"] = network_events[-24:]
                return diagnostic

            cdp("Page.enable")
            cdp("Runtime.enable")
            cdp("Network.enable")
            cdp("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            desktop_url = f"{LOCAL_DESKTOP_ORIGIN}/"
            cdp("Page.navigate", {"url": desktop_url})
            deadline = time.monotonic() + LOGIN_READY_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                evaluated = cdp("Runtime.evaluate", {
                    "expression": (
                        "location.hash === '#/login' "
                        "&& Boolean(document.querySelector('input[type=email]')) "
                        "&& !Boolean(document.querySelector('.boot-screen--failed')) "
                        "&& !document.body.textContent.includes('Не удалось запустить рабочее пространство')"
                    ),
                    "returnByValue": True,
                })
                if evaluated["result"]["result"].get("value") is True:
                    break
                time.sleep(0.08)
            else:
                diagnostic_path = output / "desktop-login-timeout.png"
                screenshot = cdp("Page.captureScreenshot", {
                    "format": "png", "captureBeyondViewport": True,
                })
                diagnostic_path.write_bytes(base64.b64decode(screenshot["result"]["data"]))
                raise AssertionError(
                    "Desktop did not reach the local login screen within "
                    f"{LOGIN_READY_TIMEOUT_SECONDS}s; screenshot={diagnostic_path}; "
                    f"diagnostics={json.dumps(desktop_login_diagnostics(), ensure_ascii=False)}"
                )

            credentials_file = ROOT / ".local" / "owner.local.json"
            if not credentials_file.is_file():
                raise AssertionError("Local owner credentials were not provisioned")
            credentials = json.loads(credentials_file.read_text(encoding="utf-8"))
            cdp("Runtime.evaluate", {
                "expression": f"""
(() => {{
  const email = document.querySelector('input[type=email]');
  const password = document.querySelector('input[type=password]');
  email.value = {json.dumps(credentials['email'])};
  password.value = {json.dumps(credentials['password'])};
  email.dispatchEvent(new Event('input', {{ bubbles: true }}));
  password.dispatchEvent(new Event('input', {{ bubbles: true }}));
  email.form.requestSubmit();
  return true;
}})()
""",
                "returnByValue": True,
            })
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                evaluated = cdp("Runtime.evaluate", {
                    "expression": (
                        "location.hash.startsWith('#/workspace/') "
                        "&& Boolean(document.querySelector('#main-content')) "
                        "&& !document.body.textContent.includes('Не удалось запустить рабочее пространство')"
                    ),
                    "returnByValue": True,
                })
                if evaluated["result"]["result"].get("value") is True:
                    break
                time.sleep(0.1)
            else:
                # Та же диагностика, что у экрана входа: без снимка и консоли
                # отказ «не дошёл до рабочего пространства» нечем разбирать.
                screenshot = cdp("Page.captureScreenshot", {"format": "png"})
                diagnostic_path = output / "desktop-workspace-timeout.png"
                diagnostic_path.write_bytes(base64.b64decode(screenshot["result"]["data"]))
                raise AssertionError(
                    "Desktop local owner did not reach the workspace; "
                    f"screenshot={diagnostic_path}; "
                    f"diagnostics={json.dumps(desktop_login_diagnostics(), ensure_ascii=False)}"
                )
            desktop_screenshot = cdp("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            desktop_path = output / "desktop-local.png"
            desktop_path.write_bytes(base64.b64decode(desktop_screenshot["result"]["data"]))
            results.append({"route": "desktop", "url": desktop_url, "screenshot": str(desktop_path)})

            generation_url = (
                f"{LOCAL_DESKTOP_ORIGIN}/#/workspace/generation"
                f"?project_id={project_id}"
            )
            cdp("Page.navigate", {"url": generation_url})
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                evaluated = cdp("Runtime.evaluate", {
                    "expression": (
                        "Boolean(document.querySelector('#mock-batch-form')) "
                        "&& Boolean(document.querySelector('[data-generation-intake-v4]')) "
                        "&& document.querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound "
                        "&& !document.body.textContent.includes('Не удалось запустить рабочее пространство')"
                    ),
                    "returnByValue": True,
                })
                if evaluated["result"]["result"].get("value") is True:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError("Real Desktop generation form did not render")

            route_evidence = (
                (
                    "copy_video",
                    "copy-product-swap.png",
                    {
                        "mode": "compact",
                        "sourceSingle": True,
                        "copyProduct": True,
                        "audioExplicit": True,
                        "serverOwnedModel": True,
                        "briefInPanel": True,
                        "rights": True,
                        "guidedHidden": True,
                    },
                ),
                (
                    "avatar_video",
                    "avatar-duet.png",
                    {
                        "mode": "compact",
                        "sourceSingle": True,
                        # «Дуэт» с 23.08.2026: ведущий проекта вместо фото/описания
                        # аватара; регистрация ведущего — прямо в панели.
                        "avatarPhoto": False,
                        "avatarModeCount": 0,
                        "avatarDescription": False,
                        "avatarConsent": False,
                        "duetPresenter": True,
                        "duetRegister": True,
                        "briefInPanel": True,
                        # Заглушки «платный Character Performance закрыт» больше
                        # нет: подпись панели говорит о речи ведущего.
                        "featureGate": False,
                        "speechNote": True,
                        "guidedHidden": True,
                    },
                ),
                (
                    "strategy_video",
                    "strategy-viral-rebuild.png",
                    {
                        # «Создание» с 22–23.08: режим панели назван по
                        # стратегии, исходники берутся из проверенных MP4
                        # проекта (ровно десять), а не отдельной загрузкой.
                        "mode": "strategy",
                        "strategyUpload": False,
                        "guidedStepCount": 6,
                        "strategyCatalogReady": True,
                        "strategyButtonCount": 3,
                        "guidedHidden": False,
                    },
                ),
            )
            for route, filename, expected in route_evidence:
                cdp("Runtime.evaluate", {
                    "expression": (
                        "document.querySelector('[data-generation-intake-route="
                        f'\\"{route}\\"'
                        "]')?.click()"
                    ),
                    "returnByValue": True,
                })
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    evaluated = cdp("Runtime.evaluate", {
                        "expression": (
                            "document.querySelector('#mock-batch-form')?.dataset."
                            f"generationIntakeV4Route === {json.dumps(route)}"
                        ),
                        "returnByValue": True,
                    })
                    if evaluated["result"]["result"].get("value") is True:
                        break
                    time.sleep(0.05)
                else:
                    raise AssertionError(f"Real generation route did not switch: {route}")

                evidence_expression = f"""
(() => {{
  const form = document.querySelector('#mock-batch-form');
  const panel = form?.querySelector('[data-generation-intake-panel={json.dumps(route)}]');
  const guided = form?.querySelector('[data-ce-v4-generation-guided-shell]');
  const audio = panel?.querySelector('[data-generation-intake-field="audio"]');
  const config = window.CONTENTENGINE_CONFIG || {{}};
  return JSON.stringify({{
    route: form?.dataset.generationIntakeV4Route || '',
    mode: form?.dataset.generationIntakeV4Mode || '',
    activePanel: Boolean(panel && !panel.hidden && panel.getAttribute('aria-hidden') === 'false'),
    selectedRouteCount: form?.querySelectorAll('[data-generation-intake-route][aria-pressed="true"]').length || 0,
    failClosed: config.REAL_GENERATION_ENABLED === false
      && config.ALLOW_REAL_SPEND === false
      && config.CREATOR_GENERATE_MOCK_ONLY === true,
    noObjectRequired: !form?.textContent.includes('object_required'),
    sourceSingle: Boolean(panel?.querySelector('input[data-generation-intake-mp4="single"][accept*="video/mp4"]')),
    copyProduct: Boolean(panel?.querySelector('input[data-generation-intake-image="product"][multiple]')),
    audioExplicit: Boolean(audio?.required && audio.querySelector('option[value="true"]') && audio.querySelector('option[value="false"]')),
    serverOwnedModel: Boolean(panel?.querySelector('[data-generation-intake-server-owned][disabled]')),
    briefInPanel: Boolean(panel?.querySelector('textarea[name="brief"]')),
    rights: Boolean(panel?.querySelector('[data-generation-intake-rights="copy_video"]')),
    avatarPhoto: Boolean(panel?.querySelector('input[data-generation-intake-image="avatar"]')),
    avatarModeCount: panel?.querySelectorAll('input[data-generation-intake-avatar-mode]').length || 0,
    avatarDescription: Boolean(panel?.querySelector('[data-generation-intake-field="avatar_wishes"]')),
    avatarConsent: Boolean(panel?.querySelector('[data-generation-intake-avatar-consent]')),
    duetPresenter: Boolean(panel?.querySelector('[data-generation-intake-duet-presenter-select]')),
    duetRegister: Boolean(panel?.querySelector('[data-generation-intake-duet-register]')),
    featureGate: Boolean(panel?.querySelector('.generation-intake-v4__gate-note')?.textContent.includes('provider-adapter')),
    speechNote: Boolean(panel?.querySelector('.generation-intake-v4__gate-note')?.textContent.includes('речь ведущего')),
    strategyUpload: Boolean(panel?.querySelector('input[data-generation-intake-mp4="strategy"][multiple]')),
    guidedStepCount: form?.querySelectorAll('[data-ce-v4-generation-target]').length || 0,
    strategyCatalogReady: form?.querySelector('[data-generation-strategy-status]')?.dataset.generationStrategyStatus === 'ready',
    strategyButtonCount: form?.querySelectorAll('[data-generation-strategy-action="SELECT"]').length || 0,
    guidedHidden: !guided || getComputedStyle(guided).display === 'none',
  }});
}})()
"""
                evaluated = cdp("Runtime.evaluate", {
                    "expression": evidence_expression,
                    "returnByValue": True,
                })
                evidence = json.loads(evaluated["result"]["result"]["value"])
                common_expected = {
                    "route": route,
                    "activePanel": True,
                    "selectedRouteCount": 1,
                    "failClosed": True,
                    "noObjectRequired": True,
                }
                for key, value in {**common_expected, **expected}.items():
                    if evidence.get(key) != value:
                        raise AssertionError(
                            f"Real generation route evidence mismatch for {route}: "
                            f"{key}={evidence.get(key)!r}, expected {value!r}; {evidence}"
                        )
                cdp("Runtime.evaluate", {
                    "expression": f"""
(() => {{
  const form = document.querySelector('#mock-batch-form');
  const target = {json.dumps(route)} === 'strategy_video'
    ? form?.querySelector('[data-ce-v4-generation-guided-shell]')
    : form?.querySelector('[data-generation-intake-panel={json.dumps(route)}]');
  target?.scrollIntoView({{ block: 'start', inline: 'nearest' }});
  return Boolean(target);
}})()
""",
                    "returnByValue": True,
                })
                time.sleep(0.12)
                screenshot = cdp("Page.captureScreenshot", {
                    "format": "png",
                    "captureBeyondViewport": False,
                    "fromSurface": True,
                })
                path = output / filename
                path.write_bytes(base64.b64decode(screenshot["result"]["data"]))
                results.append({
                    "route": route,
                    "url": generation_url,
                    "screenshot": str(path),
                    "mode": str(evidence["mode"]),
                })

                if route == "copy_video" and UPLOAD_PROBE_MP4.is_file():
                    # Живая загрузка MP4 в «Копию» с пульсом главного потока.
                    # 23.08.2026 выбор файла вешал вкладку (вентиляторы на
                    # полную): цикл перерисовок. Снимок экрана и пульс каждые
                    # полсекунды — отказ называет секунду, на которой поток
                    # перестал отвечать.
                    located = cdp("Runtime.evaluate", {
                        "expression": (
                            "document.querySelector('[data-generation-intake-panel=\"copy_video\"] "
                            "input[data-generation-intake-mp4=\"single\"]')"
                        ),
                        "returnByValue": False,
                    })
                    object_id = located["result"]["result"].get("objectId")
                    if not object_id:
                        raise AssertionError("Copy panel has no single MP4 input")
                    websocket.send(json.dumps({
                        "id": 900001,
                        "method": "DOM.setFileInputFiles",
                        "params": {"objectId": object_id, "files": [str(UPLOAD_PROBE_MP4)]},
                    }))
                    # Ответ на setFileInputFiles может прийти после событий страницы.
                    set_deadline = time.monotonic() + 10
                    while time.monotonic() < set_deadline:
                        message = json.loads(websocket.recv())
                        if message.get("id") == 900001:
                            if "error" in message:
                                raise AssertionError(f"setFileInputFiles failed: {message['error']}")
                            break
                    heartbeat_started = time.monotonic()
                    stalled_at = None
                    last_status = ""
                    while time.monotonic() - heartbeat_started < 12:
                        pulse_started = time.monotonic()
                        try:
                            pulse = cdp("Runtime.evaluate", {
                                "expression": (
                                    "JSON.stringify({ status: document.querySelector('[data-generation-intake-panel=\"copy_video\"] "
                                    ".generation-intake-v4__status')?.textContent || '' })"
                                ),
                                "returnByValue": True,
                                "timeout": 3000,
                            })
                            last_status = str(pulse["result"]["result"].get("value", ""))
                        except Exception:
                            stalled_at = round(time.monotonic() - heartbeat_started, 1)
                            break
                        if time.monotonic() - pulse_started > 3:
                            stalled_at = round(time.monotonic() - heartbeat_started, 1)
                            break
                        time.sleep(0.5)
                    if stalled_at is not None:
                        raise AssertionError(
                            f"Copy panel main thread stalled {stalled_at}s after selecting an MP4; "
                            f"last status={last_status}"
                        )
                    results.append({
                        "route": "copy_video_upload_probe",
                        "status": last_status,
                        "file": str(UPLOAD_PROBE_MP4),
                    })

            if finder_project_id:
                finder_url = (
                    f"{LOCAL_DESKTOP_ORIGIN}/#/workspace/board"
                    f"?project_id={finder_project_id}&folder=all&view=browse"
                )
                cdp("Page.navigate", {"url": finder_url})
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    evaluated = cdp("Runtime.evaluate", {
                        "expression": (
                            "Boolean(document.querySelector('[data-action=\"finder-mode\"]')) "
                            "&& Boolean(document.querySelector('[data-action=\"finder-view\"]')) "
                            "&& Boolean(document.querySelector('[data-action=\"finder-upload\"]'))"
                        ),
                        "returnByValue": True,
                    })
                    if evaluated["result"]["result"].get("value") is True:
                        break
                    time.sleep(0.1)
                else:
                    raise AssertionError("Finder controls did not render")

                cdp("Runtime.evaluate", {
                    "expression": "document.querySelector('[data-ce-v4-finder-mode=\"organize\"]').click()",
                    "returnByValue": True,
                })
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    evaluated = cdp("Runtime.evaluate", {
                        "expression": (
                            "location.hash.includes('view=organize') "
                            "&& document.querySelector('[data-ce-v4-finder-control-status]')?.textContent.includes('Организация')"
                        ),
                        "returnByValue": True,
                    })
                    if evaluated["result"]["result"].get("value") is True:
                        break
                    time.sleep(0.08)
                else:
                    raise AssertionError("Finder organize control did not switch the route")

                cdp("Runtime.evaluate", {
                    "expression": "document.querySelector('[data-ce-v4-finder-view=\"list\"]').click()",
                    "returnByValue": True,
                })
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    evaluated = cdp("Runtime.evaluate", {
                        "expression": (
                            "document.querySelector('.workspace-board')?.dataset.ceV4FinderView === 'list' "
                            "&& document.querySelector('[data-ce-v4-finder-control-status]')?.textContent.includes('вид «Список»')"
                        ),
                        "returnByValue": True,
                    })
                    if evaluated["result"]["result"].get("value") is True:
                        break
                    time.sleep(0.08)
                else:
                    raise AssertionError("Finder list control did not switch the layout")

                finder_screenshot = cdp("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                finder_path = output / "finder-controls-local.png"
                finder_path.write_bytes(base64.b64decode(finder_screenshot["result"]["data"]))

                cdp("Runtime.evaluate", {
                    "expression": "document.querySelector('[data-action=\"finder-upload\"]').click()",
                    "returnByValue": True,
                })
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    evaluated = cdp("Runtime.evaluate", {
                        "expression": (
                            "location.hash.startsWith('#/workspace/media') "
                            "&& document.body.textContent.includes('Точные фото или видео')"
                        ),
                        "returnByValue": True,
                    })
                    if evaluated["result"]["result"].get("value") is True:
                        break
                    time.sleep(0.08)
                else:
                    raise AssertionError("Finder upload control did not open the media route")
                results.append({
                    "route": "finder-controls",
                    "url": finder_url,
                    "screenshot": str(finder_path),
                })

            for route in ("copy", "avatar", "strategy"):
                url = f"{LOCAL_DESKTOP_ORIGIN}/workbench/#/{route}"
                cdp("Page.navigate", {"url": url})
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    evaluated = cdp("Runtime.evaluate", {"expression": f"document.body.dataset.route === '{route}' && Boolean(document.querySelector('[data-smoke-route=\"{route}\"]'))", "returnByValue": True})
                    if evaluated["result"]["result"].get("value") is True:
                        break
                    time.sleep(0.08)
                else:
                    raise AssertionError(f"route did not render: {route}")
                errors = cdp("Runtime.evaluate", {"expression": "JSON.stringify({spend:document.querySelector('#spend-gate')?.textContent, title:document.querySelector('h2')?.textContent})", "returnByValue": True})
                state = json.loads(errors["result"]["result"]["value"])
                if state["spend"] != "Real spend: blocked" or not state["title"]:
                    raise AssertionError(f"unsafe or incomplete route: {route}: {state}")
                screenshot = cdp("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                path = output / f"diagnostic-{route}.png"
                path.write_bytes(base64.b64decode(screenshot["result"]["data"]))
                results.append({"route": f"diagnostic-{route}", "url": url, "screenshot": str(path)})
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        if server is not None:
            server.shutdown()
        if profile.resolve(strict=False).parent == profiles_root.resolve(strict=False):
            shutil.rmtree(profile, ignore_errors=True)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, default=ROOT / ".local" / "site")
    parser.add_argument("--output", type=Path, default=ROOT / ".dev-artifacts" / "browser-smoke")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--finder-project-id", default="")
    args = parser.parse_args()
    project_id = normalized_project_id(args.project_id) if args.project_id else local_project_id()
    finder_project_id = (
        normalized_project_id(args.finder_project_id)
        if args.finder_project_id
        else project_id
    )
    print(json.dumps(
        smoke(args.site, args.output, project_id, finder_project_id),
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
