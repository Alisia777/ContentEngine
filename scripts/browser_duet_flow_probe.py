#!/usr/bin/env python3
"""Drive the whole «Дуэт» operation in the local Desktop and report every step.

Login as the local fixture owner → register a project product through the
«Копия» panel (photo + SKU/name/category) → register a presenter through the
live API client (the local stack has no HeyGen key, so the catalog button is
skipped) → «Дуэт»: MP4, product, rights, base template → «Подготовить ролик»
(handoff into the native constructor) → drive the native wizard's free steps
(probe MP4 → spec → approval → assets/price) until the server answers.

Usage: python scripts/browser_duet_flow_probe.py [--mp4 PATH] [--photo PATH]
Exit 0 when the flow reaches the server provider-readiness boundary or a price.
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
COPY = '[data-generation-intake-panel="copy_video"]'
DUET = '[data-generation-intake-panel="avatar_video"]'
FREE_PHASES = (
    "strategy_product_swap_prepare",
    "strategy_product_swap_spec_review",
    "strategy_product_swap_free_preflight",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mp4", type=Path, default=UPLOAD_PROBE_MP4)
    parser.add_argument("--photo", type=Path, default=DEFAULT_PHOTO)
    parser.add_argument("--sku", default="PROBE-DUET-1")
    parser.add_argument("--name", default="Пробный товар дуэта")
    parser.add_argument("--category", default="sports_food")
    parser.add_argument("--step-timeout", type=float, default=90.0)
    parser.add_argument("--in-window", action="store_true",
                        help="work inside the live window iframe, the way a person sees the screen")
    args = parser.parse_args()
    from websockets.sync.client import connect

    credentials = json.loads((ROOT / ".local" / "owner.local.json").read_text(encoding="utf-8"))
    project_id = local_project_id()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="contentengine-duet-flow-"))
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
                    if "creator_prepare_generation_strategy_spec" in params["request"]["url"]:
                        (ARTIFACTS / "duet-flow-spec-request.json").write_text(
                            params["request"].get("postData") or "", encoding="utf-8",
                        )
                    if "functions/v1/creator-generate" in params["request"]["url"]:
                        post = params["request"].get("postData") or ""
                        if '"strategy_bind"' in post:
                            (ARTIFACTS / "duet-flow-bind-request.json").write_text(post, encoding="utf-8")
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
                    raise RuntimeError(json.dumps(payload["exceptionDetails"], ensure_ascii=False)[:600])
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
                (ARTIFACTS / f"duet-flow-{name}.png").write_bytes(base64.b64decode(shot["result"]["data"]))

            toasts_seen = 0

            def drain_toasts(label: str) -> None:
                nonlocal toasts_seen
                entries = json.loads(evaluate("JSON.stringify(__ceWin().__ceToasts || [])") or "[]")
                for entry in entries[toasts_seen:]:
                    print(f"  [{label}] toast {entry['type']}: {entry['text']}")
                    if "error" in entry["type"]:
                        problems.append(f"toast: {entry['text']}")
                toasts_seen = len(entries)

            def panel_state(panel: str) -> dict:
                return evaluate(
                    "(() => { const panel = __ceDoc().querySelector(" + json.dumps(panel) + ");"
                    " const status = panel?.querySelector('[data-generation-intake-status]');"
                    " const form = __ceDoc().querySelector('#mock-batch-form');"
                    " const submit = form?.querySelector('#generation-submit');"
                    " return { status: status?.textContent?.trim() || '', statusState: status?.dataset?.state || '',"
                    " mode: form?.dataset?.generationIntakeV4Mode || '', route: form?.dataset?.generationIntakeV4Route || '',"
                    " busy: form?.dataset?.busy || '', strategy: form?.elements?.generation_strategy_id?.value || '',"
                    " submit: submit?.textContent?.trim() || '', submitDisabled: Boolean(submit?.disabled),"
                    " phase: submit?.dataset?.launchPhase || '', blocker: submit?.dataset?.launchBlocker || '',"
                    " duration: form?.elements?.generation_strategy_duration_seconds?.value || '',"
                    " engine: form?.elements?.generation_intake_engine?.value || '',"
                    " presenter: form?.elements?.duet_presenter_id?.value || '',"
                    " intakeBusy: form?.querySelector('[data-generation-intake-v4]')?.getAttribute('aria-busy') || '' }; })()"
                ) or {}

            def wait_settled(label: str, panel: str, seconds: float) -> dict:
                stop = time.monotonic() + seconds
                last = None
                state = panel_state(panel)
                while time.monotonic() < stop:
                    state = panel_state(panel)
                    drain_toasts(label)
                    key = (state.get("status"), state.get("busy"), state.get("phase"), state.get("submit"), state.get("mode"))
                    if key != last:
                        print(
                            f"  [{label}] mode={state.get('mode') or '-'} busy={state.get('busy') or '-'}"
                            f" native=«{state.get('submit')}» phase={state.get('phase') or '-'}"
                            f"{' blocker=' + state['blocker'] if state.get('blocker') else ''} · {state.get('status')}"
                        )
                        last = key
                    if (
                        state.get("busy") != "true"
                        and state.get("intakeBusy") != "true"
                        and "…" not in state.get("status", "")
                    ):
                        return state
                    time.sleep(0.5)
                problems.append(f"{label}: timed out after {seconds}s (status={state.get('status')})")
                return state

            def set_files(selector: str, path: Path) -> None:
                located = cdp("Runtime.evaluate", {"expression": "__ceDoc().querySelector(" + json.dumps(selector) + ")", "returnByValue": False})
                object_id = located["result"]["result"].get("objectId")
                if not object_id:
                    raise AssertionError(f"no element for {selector}")
                cdp("DOM.setFileInputFiles", {"objectId": object_id, "files": [str(path)]}, timeout=30)

            def click(selector: str) -> bool:
                return evaluate(
                    "(() => { const node = __ceDoc().querySelector(" + json.dumps(selector) + ");"
                    " if (!node) return false; node.scrollIntoView({ block: 'center' }); node.click(); return true; })()"
                ) is True

            cdp("Page.enable")
            cdp("Runtime.enable")
            cdp("Network.enable")
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
"""})
            cdp("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1300, "deviceScaleFactor": 1, "mobile": False})
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

            print("step 0 · register a presenter through the live API (no HeyGen catalog on the local stack)")
            if not wait_js("Boolean(window.ContentEngineWorkspaceRuntime?.getApi?.()?.organizationId)", 20):
                raise SystemExit("API client has no organization yet")
            registered = evaluate(
                "(async () => { const api = window.ContentEngineWorkspaceRuntime.getApi();"
                " try { const presenters = await api.duetPresenters(" + json.dumps(project_id) + ");"
                "   if (presenters.length) return { ok: true, existing: presenters.length };"
                "   const presenter = await api.registerDuetPresenter(" + json.dumps(project_id) + ", {"
                "     displayName: 'Пробный ведущий', providerAvatarId: 'probe_avatar_1', providerVoiceId: 'probe_voice_1',"
                "     providerAvatarKind: 'talking_photo', isDefault: true });"
                "   return { ok: true, id: presenter?.id || presenter }; }"
                " catch (error) { return { ok: false, error: String(error?.message || error) }; } })()"
            )
            print("   presenter:", json.dumps(registered, ensure_ascii=False))
            if not registered or registered.get("ok") is not True:
                problems.append(f"presenter registration failed: {registered}")

            cdp("Page.navigate", {"url": f"{LOCAL_DESKTOP_ORIGIN}/#/workspace/generation?project_id={project_id}"})
            if not wait_js("Boolean(__ceDoc().querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound)", 30):
                raise SystemExit("generation form did not bind")
            if args.in_window:
                if not wait_js("__ceDoc() !== document && Boolean(__ceDoc().querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound)", 30):
                    raise SystemExit("live window surface did not bind the generation form")
                print("   live window surface: bound (probing inside the iframe)")

            print(f"step 1 · register a product through «Копия» ({args.photo.name}, {args.sku})")
            click('[data-generation-intake-route="copy_video"]')
            wait_js("__ceDoc().querySelector('#mock-batch-form')?.dataset.generationIntakeV4Route === 'copy_video'", 10)
            time.sleep(1.0)
            # Регистрация фото идёт только после единой галки прав: без неё
            # очередь ждёт, и на чистой базе у «Дуэта» не было бы товара.
            rights_ticked = evaluate(
                "(() => { const box = __ceDoc().querySelector(" + json.dumps(COPY + ' [data-generation-intake-rights="copy_video"]') + ");"
                " if (box && !box.checked) box.click(); return Boolean(box?.checked); })()"
            )
            print("   rights ticked:", rights_ticked)
            set_files(COPY + ' input[data-generation-intake-image="product"]', args.photo)
            time.sleep(1.0)
            evaluate(
                "(() => { const shell = __ceDoc().querySelector('#mock-batch-form');"
                " const assign = (field, value) => { const node = shell.querySelector('[data-generation-intake-identity] [data-generation-intake-field=\"' + field + '\"]');"
                "   if (!node) return false; node.value = value; node.dispatchEvent(new Event('input', { bubbles: true })); node.dispatchEvent(new Event('change', { bubbles: true })); return true; };"
                " return [assign('sku', " + json.dumps(args.sku) + "), assign('product_name', " + json.dumps(args.name) + "), assign('product_category', " + json.dumps(args.category) + ")]; })()"
            )
            # Регистрация стартует асинхронно после заполнения полей: ждём её
            # исхода, иначе следующий клик по «Дуэту» упрётся в занятый маршрут.
            wait_js(
                "(() => { const s = __ceDoc().querySelector(" + json.dumps(COPY + " [data-generation-intake-status]") + ");"
                " return Boolean(s) && (s.textContent.includes('зарегистрированы') || s.dataset.state === 'error'); })()",
                45,
            )
            state = wait_settled("product", COPY, 30)
            screenshot("1-product")

            print(f"step 2 · «Дуэт»: MP4 {args.mp4.name}")
            click('[data-generation-intake-route="avatar_video"]')
            if not wait_js("__ceDoc().querySelector('#mock-batch-form')?.dataset.generationIntakeV4Route === 'avatar_video'", 10):
                diagnostics = evaluate(
                    "(() => { const form = __ceDoc().querySelector('#mock-batch-form');"
                    " const buttons = [...__ceDoc().querySelectorAll('[data-generation-intake-route]')].map((b) => ({"
                    "   route: b.dataset.generationIntakeRoute, tag: b.tagName, disabled: Boolean(b.disabled), pressed: b.getAttribute('aria-pressed'),"
                    "   visible: Boolean(b.offsetParent), text: (b.textContent || '').trim().slice(0, 60) }));"
                    " return JSON.stringify({ dataset: { ...form?.dataset }, buttons }).slice(0, 2500); })()"
                )
                print("   route diagnostics:", diagnostics)
                raise SystemExit("duet route did not open")
            time.sleep(1.5)
            presenter_options = evaluate(
                "JSON.stringify([...__ceDoc().querySelectorAll(" + json.dumps(DUET + " [data-generation-intake-duet-presenter-select] option") + ")].map((o) => [o.value, o.textContent]))"
            )
            product_options = evaluate(
                "JSON.stringify([...__ceDoc().querySelectorAll(" + json.dumps(DUET + " [data-generation-intake-duet-product-select] option") + ")].map((o) => [o.value, o.textContent]))"
            )
            print("   presenter options:", presenter_options)
            print("   product options:", product_options)
            set_files(DUET + ' input[data-generation-intake-mp4="single"]', args.mp4)
            state = wait_settled("mp4", DUET, 30)
            summary = evaluate(
                "(() => { const n = __ceDoc().querySelector(" + json.dumps(DUET + " [data-generation-intake-source-file]") + ");"
                " return n ? { text: n.textContent, state: n.dataset.state, hidden: n.hidden } : null; })()"
            )
            print("   dropzone summary:", json.dumps(summary, ensure_ascii=False))
            if not summary or summary.get("hidden") or "выбран" not in str(summary.get("text")):
                problems.append(f"dropzone does not name the chosen MP4: {summary}")
            print("   «Разобрать MP4»")
            click('[data-action="generation-intake-analyze-avatar"]')
            state = wait_settled("analyze", DUET, args.step_timeout)
            screenshot("2-mp4")

            print("step 3 · product, rights, template")
            chosen_product = evaluate(
                "(() => { const select = __ceDoc().querySelector(" + json.dumps(DUET + " [data-generation-intake-duet-product-select]") + ");"
                " if (!select) return 'missing'; const option = [...select.options].find((o) => o.value); if (!option) return 'no products';"
                " select.value = option.value; select.dispatchEvent(new Event('change', { bubbles: true })); return option.textContent; })()"
            )
            print("   product:", chosen_product)
            rights = evaluate(
                "(() => { const box = __ceDoc().querySelector(" + json.dumps(DUET + ' [data-generation-intake-rights="avatar_video"]') + ");"
                " if (!box) return 'missing'; if (!box.checked) box.click(); return box.checked; })()"
            )
            print("   rights:", rights)
            if not click('[data-action="generation-intake-apply-recommendation"][data-route="avatar_video"]'):
                print("   template button not visible")
            mechanics = {
                "hook": "Первые две секунды: крупный план гриля с шипящим мясом и вопрос «почему все так жарят?»",
                "beat_sequence": "Крупный план огня и мяса на решётке" + chr(10) + "Руки переворачивают стейк щипцами" + chr(10) + "Показ готового блюда на тарелке сверху",
                "pacing": "Быстрые склейки по 1–2 секунды, ускорение к финалу",
                "camera_language": "Ручная камера, наезд на решётку, верхний ракурс в конце",
                "composition": "Гриль в центре кадра, товар крупно в последней трети",
                "audio_pattern": "Шипение мяса, короткая фраза за кадром, без музыки",
                "cta_pattern": "Финальный кадр с тарелкой и призывом попробовать дома",
            }
            filled = evaluate(
                "(() => { const values = " + json.dumps(mechanics, ensure_ascii=False) + ";"
                " const boxes = [...__ceDoc().querySelectorAll(" + json.dumps(DUET + " textarea[data-generation-intake-duet-mechanics]") + ")];"
                " boxes.forEach((box) => { const key = box.dataset.generationIntakeDuetMechanics; if (values[key]) { box.value = values[key]; box.dispatchEvent(new Event('input', { bubbles: true })); } });"
                " return boxes.length; })()"
            )
            print("   mechanics fields filled:", filled)
            # Речь ведущего обязана уложиться в ролик (≈15 знаков/с): для 5 с — до 90.
            evaluate(
                "(() => { const brief = __ceDoc().querySelector('#mock-batch-form')?.elements?.brief; if (!brief) return false;"
                " brief.value = 'Смотрите, как он переворачивает стейк: вот так жарят дома без хлопот.';"
                " brief.dispatchEvent(new Event('input', { bubbles: true })); brief.dispatchEvent(new Event('change', { bubbles: true })); return true; })()"
            )
            brief = evaluate("(__ceDoc().querySelector('#mock-batch-form')?.elements?.brief?.value || '').length")
            meta = evaluate("__ceDoc().querySelector('[data-generation-intake-brief-meta=\"avatar_video\"]')?.textContent || ''")
            print("   brief length:", brief, "·", meta)
            state = wait_settled("inputs", DUET, 15)
            screenshot("3-inputs")

            print("step 4 · «Подготовить ролик» (handoff into the native constructor)")
            click('[data-action="generation-intake-prepare-avatar"]')
            state = wait_settled("prepare", DUET, args.step_timeout)
            screenshot("4-prepared")
            if state.get("statusState") in ("error", "warning"):
                problems.append(f"prepare ended in {state.get('statusState')}: {state.get('status')}")
                picker = evaluate(
                    "(() => { const form = __ceDoc().querySelector('#mock-batch-form');"
                    " const inputs = [...form.querySelectorAll('input[name=generation_strategy_source_selection]')]"
                    "   .map((i) => ({ value: i.value, checked: i.checked, disabled: i.disabled }));"
                    " const projection = __ceWin().ContentEngineGenerationGuidedV4?.getStrategySourcePickerProjection?.(form);"
                    " return JSON.stringify({ inputs, projection }, null, 0).slice(0, 1500); })()"
                )
                print("  picker:", picker)

            print("step 5 · drive the native wizard's free steps")
            boundary = False
            for attempt in range(1, 16):
                state = panel_state(DUET)
                approvals = evaluate(
                    "(() => { const boxes = [...__ceDoc().querySelectorAll('#mock-batch-form input[name=\"generation_strategy_spec_approval\"]')];"
                    " const pending = boxes.filter((box) => !box.checked && !box.disabled); pending.forEach((box) => box.click()); return [boxes.length, pending.length]; })()"
                )
                if approvals and approvals[1]:
                    print(f"   approved spec versions: {approvals[1]} of {approvals[0]}")
                    wait_settled(f"approve{attempt}", DUET, 20)
                    continue
                if state.get("busy") == "true":
                    wait_settled(f"busy{attempt}", DUET, args.step_timeout)
                    continue
                if state.get("phase") in FREE_PHASES and not state.get("submitDisabled"):
                    print(f"   click native «{state.get('submit')}» (phase {state.get('phase')})")
                    failure_before = evaluate("__ceDoc().querySelector('#mock-batch-form')?.dataset?.generationStrategyLastFailureAt || ''")
                    click("#generation-submit")
                    time.sleep(0.8)
                    wait_settled(f"native{attempt}", DUET, args.step_timeout)
                    failure_after = evaluate("__ceDoc().querySelector('#mock-batch-form')?.dataset?.generationStrategyLastFailureAt || ''")
                    if failure_after and failure_after != failure_before:
                        reason = evaluate("__ceDoc().querySelector('#mock-batch-form')?.dataset?.generationStrategyLastFailure || ''")
                        print(f"   server refused: {reason}")
                        boundary = "сервису генерации не настроен" in str(reason)
                        if not boundary:
                            problems.append(f"native step refused: {reason}")
                        break
                    continue
                if state.get("phase") == "strategy_product_swap_paid_review":
                    print(f"   reached paid review: «{state.get('submit')}»")
                    break
                print(f"   native button idle: «{state.get('submit')}» phase={state.get('phase')} blocker={state.get('blocker')}")
                invalid = evaluate(
                    "JSON.stringify([...__ceDoc().querySelector('#mock-batch-form').elements].filter((n) => typeof n.checkValidity === 'function' && !n.checkValidity())"
                    ".map((n) => ({ name: n.name, visible: Boolean(n.offsetParent), message: n.validationMessage })))"
                )
                print("   invalid controls:", invalid)
                problems.append(f"native wizard stuck: «{state.get('submit')}» blocker={state.get('blocker')}")
                break
            screenshot("5-native")
            print("final:", json.dumps(panel_state(DUET), ensure_ascii=False))
            if boundary:
                problems[:] = [
                    line for line in problems
                    if "сервису генерации не настроен" not in line and "functions/v1/creator-generate" not in line
                ]
                print("LOCAL BOUNDARY: reached the server provider-readiness check (no provider key on the local stack)")
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
    print("OK: duet flow completed without errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
