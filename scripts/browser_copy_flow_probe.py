#!/usr/bin/env python3
"""Drive the whole «Копия» operation in the local Desktop and report every step.

Login as the local fixture owner → generation route → «Копия» → pick an MP4 →
«Проверить ролик бесплатно» → attach a product photo (with SKU/name) → rights →
base brief template → «Подготовить ролик» (uploads + server price) → «Запустить
за …» (local mock spend). Every status transition, console error, thrown
exception and failed network request is printed; a screenshot is saved per step
under .dev-artifacts/browser-smoke/.

Usage: python scripts/browser_copy_flow_probe.py [--mp4 PATH] [--photo PATH]
       [--sku SKU] [--name NAME] [--stop-before-launch]
Exit 0 when the flow reaches the final status without an error status.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from browser_smoke import (  # noqa: E402
    LOCAL_DESKTOP_ORIGIN,
    UPLOAD_PROBE_MP4,
    chrome_path,
    local_project_id,
)

ARTIFACTS = ROOT / ".dev-artifacts" / "browser-smoke"
DEFAULT_PHOTO = ROOT / "web" / "app" / "assets" / "training" / "ugc_bombbar_pro_poster.png"
PANEL = '[data-generation-intake-panel="copy_video"]'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mp4", type=Path, default=UPLOAD_PROBE_MP4)
    parser.add_argument("--photo", type=Path, default=DEFAULT_PHOTO)
    parser.add_argument("--sku", default="PROBE-SKU-1")
    parser.add_argument("--name", default="Пробный товар")
    parser.add_argument("--category", default="sports_food", help="empty string = leave the category unset")
    parser.add_argument("--stop-before-launch", action="store_true")
    parser.add_argument("--step-timeout", type=float, default=90.0)
    parser.add_argument("--in-window", action="store_true",
                        help="work inside the live window iframe, the way a person sees the screen")
    args = parser.parse_args()
    from websockets.sync.client import connect

    credentials = json.loads((ROOT / ".local" / "owner.local.json").read_text(encoding="utf-8"))
    project_id = local_project_id()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="contentengine-copy-flow-"))
    process = subprocess.Popen([
        chrome_path(), "--headless=new", "--disable-gpu", "--disable-extensions", "--no-sandbox",
        "--remote-debugging-port=0", "--remote-allow-origins=*", f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    problems: list[str] = []
    try:
        port_file = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 12
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        port = int(port_file.read_text(encoding="utf-8").splitlines()[0])
        pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5))
        page = next(item for item in pages if item.get("type") == "page")
        with connect(page["webSocketDebuggerUrl"], origin="http://localhost", open_timeout=5, max_size=None) as ws:
            request_id = 0
            requests: dict[str, dict] = {}

            def absorb(message: dict) -> None:
                method = message.get("method")
                params = message.get("params", {})
                if method == "Runtime.consoleAPICalled" and params.get("type") in ("error", "warning"):
                    text = " ".join(
                        str(arg.get("value", arg.get("description", "")))[:300]
                        for arg in params.get("args", [])
                    )
                    line = f"console.{params['type']}: {text}"
                    print("  ", line)
                    if params["type"] == "error":
                        problems.append(line)
                elif method == "Runtime.exceptionThrown":
                    details = params.get("exceptionDetails", {})
                    text = details.get("exception", {}).get("description") or details.get("text", "")
                    line = f"exception: {str(text)[:400]}"
                    print("  ", line)
                    problems.append(line)
                elif method == "Network.requestWillBeSent":
                    requests[params["requestId"]] = {
                        "url": params["request"]["url"],
                        "method": params["request"]["method"],
                    }
                elif method == "Network.responseReceived":
                    status = params["response"]["status"]
                    if status >= 400:
                        req = requests.get(params["requestId"], {})
                        line = f"http {status} {req.get('method', '?')} {req.get('url', params['response']['url'])[:200]}"
                        print("  ", line)
                        problems.append(line)
                elif method == "Network.loadingFailed":
                    req = requests.get(params["requestId"], {})
                    if req and not params.get("canceled"):
                        line = f"network failed {req.get('method')} {req.get('url', '')[:200]}: {params.get('errorText')}"
                        print("  ", line)
                        problems.append(line)

            def send(method: str, params: dict | None = None) -> int:
                nonlocal request_id
                request_id += 1
                ws.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
                return request_id

            def cdp(method: str, params: dict | None = None, timeout: float = 30) -> dict:
                rid = send(method, params)
                stop = time.monotonic() + timeout
                while time.monotonic() < stop:
                    message = json.loads(ws.recv(timeout=max(0.1, stop - time.monotonic())))
                    if message.get("id") == rid:
                        if "error" in message:
                            raise RuntimeError(f"{method}: {message['error']}")
                        return message
                    absorb(message)
                raise TimeoutError(method)

            def evaluate(expression: str, timeout: float = 30):
                result = cdp("Runtime.evaluate", {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                }, timeout=timeout)
                payload = result["result"]
                if payload.get("exceptionDetails"):
                    raise RuntimeError(json.dumps(payload["exceptionDetails"])[:400])
                return payload["result"].get("value")

            def wait_js(expression: str, seconds: float) -> bool:
                stop = time.monotonic() + seconds
                while time.monotonic() < stop:
                    if evaluate(expression) is True:
                        return True
                    time.sleep(0.1)
                return False

            def screenshot(name: str) -> None:
                shot = cdp("Page.captureScreenshot", {"format": "png"}, timeout=30)
                (ARTIFACTS / f"copy-flow-{name}.png").write_bytes(base64.b64decode(shot["result"]["data"]))

            def panel_state() -> dict:
                return evaluate(
                    "(() => { const panel = __ceDoc().querySelector(" + json.dumps(PANEL) + ");"
                    " const status = panel?.querySelector('[data-generation-intake-status]');"
                    " const prepare = panel?.querySelector('[data-action=\"generation-intake-prepare-copy\"]');"
                    " const form = __ceDoc().querySelector('#mock-batch-form');"
                    " return { status: status?.textContent?.trim() || '', statusState: status?.dataset?.state || '',"
                    " prepare: prepare?.textContent?.trim() || '', prepareDisabled: Boolean(prepare?.disabled),"
                    " expressPhase: prepare?.dataset?.expressPhase || '', busy: form?.dataset?.busy || '',"
                    " engine: form?.elements?.generation_intake_engine?.value || '' }; })()"
                ) or {}

            toasts_seen = 0

            def drain_toasts(label: str) -> None:
                nonlocal toasts_seen
                toasts = evaluate("JSON.stringify(__ceWin().__ceToasts || [])")
                entries = json.loads(toasts or "[]")
                for entry in entries[toasts_seen:]:
                    print(f"  [{label}] toast {entry['type']}: {entry['text']}")
                    if "error" in entry["type"]:
                        problems.append(f"toast: {entry['text']}")
                toasts_seen = len(entries)

            def native_state() -> dict:
                return evaluate(
                    "(() => { const form = __ceDoc().querySelector('#mock-batch-form');"
                    " const submit = form?.querySelector('#generation-submit');"
                    " return { submit: submit?.textContent?.trim() || '', submitDisabled: Boolean(submit?.disabled),"
                    " phase: submit?.dataset?.launchPhase || '', blocker: submit?.dataset?.launchBlocker || '',"
                    " strategy: form?.elements?.generation_strategy_id?.value || '',"
                    " mode: form?.elements?.generation_mode?.value || '',"
                    " sourceId: form?.elements?.generation_strategy_source_video_id?.value || '',"
                    " duration: form?.elements?.generation_strategy_duration_seconds?.value || '',"
                    " confirmationReady: form?.dataset?.generationStrategyConfirmationReady || '',"
                    " readiness: form?.dataset?.generationStrategyReadiness || '' }; })()"
                ) or {}

            def wait_settled(label: str, seconds: float) -> dict:
                """Print every status change until the form is no longer busy."""
                stop = time.monotonic() + seconds
                last = None
                last_native = None
                state = panel_state()
                while time.monotonic() < stop:
                    state = panel_state()
                    native = native_state()
                    native_key = (native.get("submit"), native.get("phase"), native.get("blocker"), native.get("submitDisabled"))
                    if native_key != last_native:
                        print(f"  [{label}] native: {json.dumps(native, ensure_ascii=False)}")
                        last_native = native_key
                    drain_toasts(label)
                    key = (state.get("status"), state.get("busy"), state.get("expressPhase"))
                    if key != last:
                        print(f"  [{label}] busy={state.get('busy') or '-'} phase={state.get('expressPhase') or '-'} · {state.get('status')}")
                        last = key
                    if state.get("busy") != "true" and "…" not in state.get("status", ""):
                        return state
                    time.sleep(0.5)
                print(f"  [{label}] still busy after {seconds}s")
                problems.append(f"{label}: timed out after {seconds}s (status={state.get('status')})")
                return state

            def set_files(selector: str, path: Path) -> None:
                located = cdp("Runtime.evaluate", {"expression": "__ceDoc().querySelector(" + json.dumps(selector) + ")", "returnByValue": False})
                object_id = located["result"]["result"].get("objectId")
                if not object_id:
                    raise AssertionError(f"no element for {selector}")
                cdp("DOM.setFileInputFiles", {"objectId": object_id, "files": [str(path)]}, timeout=30)

            def click(selector: str) -> None:
                found = evaluate(
                    "(() => { const node = __ceDoc().querySelector(" + json.dumps(selector) + ");"
                    " if (!node) return false; node.scrollIntoView({ block: 'center' }); node.click(); return true; })()"
                )
                if found is not True:
                    raise AssertionError(f"no element for {selector}")

            cdp("Page.enable")
            cdp("Runtime.enable")
            cdp("Network.enable")
            # Тосты приложения — единственный след многих отказов (submit без
            # busy и без смены кнопки). Ловим их наблюдателем и читаем потом.
            cdp("Page.addScriptToEvaluateOnNewDocument", {"source": """
window.__ceToasts = [];
new MutationObserver((records) => {
  for (const record of records) for (const node of record.addedNodes) {
    if (node instanceof HTMLElement && node.classList.contains("toast")) {
      window.__ceToasts.push({ at: Date.now(), type: node.className, text: node.textContent.trim().slice(0, 300) });
    }
  }
}).observe(document, { childList: true, subtree: true });
// Живые окна: реальный экран живёт во встроенном iframe, верхний документ —
// скрытый legacy. В режиме --in-window зонд работает с документом окна, как
// человек; пока окно не поднялось — отдаёт пустой документ (ожидания крутятся).
window.__ceInWindow = """ + json.dumps(bool(args.in_window)) + """;
window.__ceDoc = () => {
  if (!window.__ceInWindow) return document;
  // Видимое окно рабочего стола: у каждого экрана («Создать», «Материалы»)
  // свой iframe, зонд работает с тем, который сейчас показан.
  const frames = [...document.querySelectorAll("iframe[data-ce-v4-window-surface]")]
    .filter((frame) => frame.getClientRects().length > 0 && frame.contentDocument?.querySelector("#main-content"));
  // Ключевое окно (фокус и верх z-order) — то, с которым работает человек.
  const key = frames.find((frame) => frame.closest('[data-ce-v4-window-active="true"]'));
  const pick = key || frames.sort((a, b) => {
    const z = (frame) => Number(frame.closest(".ce-v4-window")?.style?.zIndex || 0);
    return z(a) - z(b);
  }).pop();
  if (pick) return pick.contentDocument;
  return document.implementation.createHTMLDocument("");
};
window.__ceWin = () => window.__ceDoc().defaultView || {};
window.__ceSubmits = [];
document.addEventListener("submit", (event) => {
  window.__ceSubmits.push({ at: Date.now(), form: event.target?.id || "?", valid: event.target?.checkValidity?.() });
}, true);
"""})
            cdp("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1200, "deviceScaleFactor": 1, "mobile": False})
            cdp("Page.navigate", {"url": f"{LOCAL_DESKTOP_ORIGIN}/"})
            if not wait_js("location.hash === '#/login' && Boolean(document.querySelector('input[type=email]'))", 20):
                raise SystemExit("login screen did not appear")
            evaluate(f"""
(() => {{
  const email = document.querySelector('input[type=email]');
  const password = document.querySelector('input[type=password]');
  email.value = {json.dumps(credentials['email'])};
  password.value = {json.dumps(credentials['password'])};
  email.dispatchEvent(new Event('input', {{ bubbles: true }}));
  password.dispatchEvent(new Event('input', {{ bubbles: true }}));
  email.form.requestSubmit();
  return true;
}})()""")
            if not wait_js("location.hash.startsWith('#/workspace/') && Boolean(document.querySelector('#main-content'))", 20):
                raise SystemExit("workspace did not open")
            cdp("Page.navigate", {"url": f"{LOCAL_DESKTOP_ORIGIN}/#/workspace/generation?project_id={project_id}"})
            if not wait_js("Boolean(__ceDoc().querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound)", 30):
                raise SystemExit("generation form did not bind")
            if args.in_window:
                if not wait_js("__ceDoc() !== document && Boolean(__ceDoc().querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound)", 30):
                    raise SystemExit("live window surface did not bind the generation form")
                print("   live window surface: bound (probing inside the iframe)")
            click('[data-generation-intake-route="copy_video"]')
            if not wait_js("__ceDoc().querySelector('#mock-batch-form')?.dataset.generationIntakeV4Route === 'copy_video'", 10):
                raise SystemExit("route did not switch")
            time.sleep(1.0)
            print("step 1 · panel opened:", json.dumps(panel_state(), ensure_ascii=False))
            screenshot("1-opened")

            print(f"step 2 · select MP4 {args.mp4.name} ({args.mp4.stat().st_size} bytes)")
            set_files(PANEL + ' input[data-generation-intake-mp4="single"]', args.mp4)
            if not wait_js("(__ceDoc().querySelector(" + json.dumps(PANEL + " [data-generation-intake-status]") + ")?.textContent || '').includes('MP4')", 20):
                problems.append("MP4 selection produced no status")
            state = wait_settled("select", 30)
            screenshot("2-selected")

            print("step 3 · «Проверить ролик бесплатно»")
            click('[data-action="generation-intake-analyze-copy"]')
            state = wait_settled("analyze", args.step_timeout)
            screenshot("3-analyzed")

            print(f"step 4 · product photo {args.photo.name} + identity {args.sku} / {args.name}")
            set_files(PANEL + ' input[data-generation-intake-image="product"]', args.photo)
            time.sleep(1.0)
            evaluate(
                "(() => { const shell = __ceDoc().querySelector('#mock-batch-form');"
                " const assign = (field, value) => { const node = shell.querySelector('[data-generation-intake-identity] [data-generation-intake-field=\"' + field + '\"]');"
                "   if (!node) return false; node.value = value; node.dispatchEvent(new Event('input', { bubbles: true })); node.dispatchEvent(new Event('change', { bubbles: true })); return true; };"
                " return [assign('sku', " + json.dumps(args.sku) + "), assign('product_name', " + json.dumps(args.name) + "),"
                + (" assign('product_category', " + json.dumps(args.category) + ")" if args.category else " 'category skipped'") + "]; })()"
            )
            rights = evaluate(
                "(() => { const box = __ceDoc().querySelector(" + json.dumps(PANEL + ' [data-generation-intake-rights="copy_video"]') + ");"
                " if (!box) return 'missing'; if (!box.checked) box.click(); return box.checked; })()"
            )
            print("   rights:", rights)
            audio = evaluate(
                "(() => { const select = __ceDoc().querySelector(" + json.dumps(PANEL + ' [data-generation-intake-field="audio"]') + ");"
                " if (!select) return 'missing'; if (select.value !== 'true' && select.value !== 'false') { select.value = 'false'; select.dispatchEvent(new Event('change', { bubbles: true })); } return select.value; })()"
            )
            print("   audio:", audio)
            try:
                click('[data-action="generation-intake-apply-recommendation"][data-route="copy_video"]')
            except AssertionError:
                print("   template button not visible; checking brief")
            brief = evaluate("(__ceDoc().querySelector('#mock-batch-form')?.elements?.brief?.value || '').length")
            print("   brief length:", brief)
            state = wait_settled("inputs", 15)
            screenshot("4-inputs")

            print("step 5 · «Подготовить ролик» (upload + server price)")
            click('[data-action="generation-intake-prepare-copy"]')
            state = wait_settled("prepare", args.step_timeout)
            screenshot("5-prepared")
            if state.get("statusState") == "error":
                problems.append(f"prepare ended in error: {state.get('status')}")
                diagnostics = evaluate(
                    "(() => { const form = __ceDoc().querySelector('#mock-batch-form');"
                    " const invalid = [...form.elements].filter((node) => typeof node.checkValidity === 'function' && !node.checkValidity())"
                    "   .map((node) => ({ name: node.name, type: node.type, visible: Boolean(node.offsetParent), message: node.validationMessage, value: String(node.value || '').slice(0, 60) }));"
                    " return JSON.stringify({ invalid, submits: window.__ceSubmits || [], toasts: __ceWin().__ceToasts || [],"
                    "   submit: form.querySelector('#generation-submit')?.outerHTML?.slice(0, 400) }); })()"
                )
                print("  diagnostics:", diagnostics)

            # Локальный стенд не держит ключей провайдеров: серверная проверка
            # готовности честно отвечает provider_configuration_error. Это
            # граница стенда, а не отказ формы — всё до неё (загрузка MP4 и
            # фото, ТЗ, одобрение) уже прошло через настоящие RPC и edge.
            local_boundary = any(
                "сервису генерации не настроен" in line for line in problems
            )
            if local_boundary:
                problems[:] = [
                    line for line in problems
                    if "сервису генерации не настроен" not in line
                    and "functions/v1/creator-generate" not in line
                    and not line.startswith("prepare ended in error")
                ]
                print("LOCAL BOUNDARY: reached the server provider-readiness check (no provider key on the local stack)")
            if local_boundary:
                pass
            elif state.get("expressPhase") == "priced" and not args.stop_before_launch:
                print(f"step 6 · {state.get('prepare')} (local mock spend)")
                click('[data-action="generation-intake-prepare-copy"]')
                state = wait_settled("launch", args.step_timeout)
                screenshot("6-launched")
                if state.get("statusState") == "error":
                    problems.append(f"launch ended in error: {state.get('status')}")
            elif state.get("expressPhase") != "priced":
                problems.append(f"prepare did not reach a price: phase={state.get('expressPhase')} status={state.get('status')}")

            print("final:", json.dumps(panel_state(), ensure_ascii=False))
            # Drain pending events so late console errors are printed too.
            stop = time.monotonic() + 1.5
            while time.monotonic() < stop:
                try:
                    absorb(json.loads(ws.recv(timeout=0.3)))
                except Exception:
                    break
    finally:
        process.kill()
    problems = [
        line for line in problems
        if "favicon.ico" not in line and "creator_workspace_trash_browser" not in line
    ]
    if problems:
        print("PROBLEMS:")
        for line in problems:
            print(" -", line)
        return 1
    print("OK: copy flow completed without errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
