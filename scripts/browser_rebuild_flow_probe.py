#!/usr/bin/env python3
"""Drive «Создание» (viral_rebuild) in the local Desktop and report every step.

Login as the local fixture owner → make ten distinct MP4s from one source
(a trailing `free` box keeps them playable but changes the sha256) → upload them
as source videos through «Материалы» → drive the native constructor: source
picker (exactly ten), free duration probe, mechanics for each source (through
the guided API), product photo + primary, attestations, output defaults, brief,
then the free steps (spec ×10 → approvals → assets/price) until the server
answers. Everything is printed; screenshots land in .dev-artifacts/browser-smoke/.

Usage: python scripts/browser_rebuild_flow_probe.py [--mp4 PATH] [--photo PATH]
Exit 0 when the flow reaches the provider-readiness boundary or a price.
"""

from __future__ import annotations

import argparse
import base64
import json
import struct
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
PANEL = '[data-generation-intake-panel="strategy_video"]'
COPY = '[data-generation-intake-panel="copy_video"]'
MECHANICS = {
    "hook": "Первые две секунды: крупный план гриля с шипящим мясом и вопрос «почему все так жарят?»",
    "beat_sequence": "Крупный план огня и мяса на решётке\nРуки переворачивают стейк щипцами\nПоказ готового блюда на тарелке сверху",
    "pacing": "Быстрые склейки по 1–2 секунды, ускорение к финалу",
    "camera_language": "Ручная камера, наезд на решётку, верхний ракурс в конце",
    "composition": "Гриль в центре кадра, товар крупно в последней трети",
    "audio_pattern": "Шипение мяса, короткая фраза за кадром, без музыки",
    "cta_pattern": "Финальный кадр с тарелкой и призывом попробовать дома",
}


def make_variants(source: Path, count: int, directory: Path) -> list[Path]:
    """Ten playable copies with distinct sha256: a trailing ISO BMFF `free` box."""
    data = source.read_bytes()
    variants = []
    for index in range(count):
        payload = f"contentengine-probe-variant-{index:02d}".encode("ascii")
        box = struct.pack(">I4s", 8 + len(payload), b"free") + payload
        target = directory / f"{source.stem}-v{index:02d}.mp4"
        target.write_bytes(data + box)
        variants.append(target)
    return variants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mp4", type=Path, default=UPLOAD_PROBE_MP4)
    parser.add_argument("--photo", type=Path, default=DEFAULT_PHOTO)
    parser.add_argument("--step-timeout", type=float, default=120.0)
    args = parser.parse_args()
    from websockets.sync.client import connect

    credentials = json.loads((ROOT / ".local" / "owner.local.json").read_text(encoding="utf-8"))
    project_id = local_project_id()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="contentengine-rebuild-flow-"))
    variants = make_variants(args.mp4, 10, work)
    profile = work / "profile"
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
                    text = " ".join(str(arg.get("value", arg.get("description", "")))[:300] for arg in params.get("args", []))
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
                    requests[params["requestId"]] = {"url": params["request"]["url"], "method": params["request"]["method"]}
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
                result = cdp("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True}, timeout=timeout)
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
                (ARTIFACTS / f"rebuild-flow-{name}.png").write_bytes(base64.b64decode(shot["result"]["data"]))

            toasts_seen = 0

            def drain_toasts(label: str) -> None:
                nonlocal toasts_seen
                entries = json.loads(evaluate("JSON.stringify(window.__ceToasts || [])") or "[]")
                for entry in entries[toasts_seen:]:
                    print(f"  [{label}] toast {entry['type']}: {entry['text']}")
                    if "error" in entry["type"]:
                        problems.append(f"toast: {entry['text']}")
                toasts_seen = len(entries)

            def native_state() -> dict:
                return evaluate(
                    "(() => { const form = document.querySelector('#mock-batch-form');"
                    " const submit = form?.querySelector('#generation-submit');"
                    " const status = document.querySelector(" + json.dumps(PANEL + " [data-generation-intake-status]") + ");"
                    " const projection = window.ContentEngineGenerationGuidedV4?.getStrategySourcePickerProjection?.(form);"
                    " return { status: status?.textContent?.trim() || '', busy: form?.dataset?.busy || '',"
                    " strategy: form?.elements?.generation_strategy_id?.value || '',"
                    " submit: submit?.textContent?.trim() || '', submitDisabled: Boolean(submit?.disabled),"
                    " phase: submit?.dataset?.launchPhase || '', blocker: submit?.dataset?.launchBlocker || '',"
                    " selected: projection?.selected_count ?? null, ready: projection?.all_selected_ready ?? null,"
                    " probeRequired: (projection?.probe_required_source_ids || []).length,"
                    " intakeBusy: form?.querySelector('[data-generation-intake-v4]')?.getAttribute('aria-busy') || '' }; })()"
                ) or {}

            def wait_settled(label: str, seconds: float) -> dict:
                stop = time.monotonic() + seconds
                last = None
                state = native_state()
                while time.monotonic() < stop:
                    state = native_state()
                    drain_toasts(label)
                    key = (state.get("status"), state.get("busy"), state.get("phase"), state.get("submit"), state.get("selected"), state.get("blocker"))
                    if key != last:
                        print(
                            f"  [{label}] busy={state.get('busy') or '-'} sel={state.get('selected')} ready={state.get('ready')}"
                            f" probe={state.get('probeRequired')} native=«{state.get('submit')}» phase={state.get('phase') or '-'}"
                            f"{' blocker=' + state['blocker'] if state.get('blocker') else ''} · {state.get('status')}"
                        )
                        last = key
                    if state.get("busy") != "true" and state.get("intakeBusy") != "true" and "…" not in state.get("status", ""):
                        return state
                    time.sleep(0.5)
                problems.append(f"{label}: timed out after {seconds}s")
                return state

            def set_files(selector: str, paths: list[Path]) -> None:
                located = cdp("Runtime.evaluate", {"expression": "document.querySelector(" + json.dumps(selector) + ")", "returnByValue": False})
                object_id = located["result"]["result"].get("objectId")
                if not object_id:
                    raise AssertionError(f"no element for {selector}")
                cdp("DOM.setFileInputFiles", {"objectId": object_id, "files": [str(path) for path in paths]}, timeout=60)

            def click(selector: str) -> bool:
                return evaluate(
                    "(() => { const node = document.querySelector(" + json.dumps(selector) + ");"
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
"""})
            cdp("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1400, "deviceScaleFactor": 1, "mobile": False})
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
            if not wait_js("Boolean(document.querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound)", 30):
                raise SystemExit("generation form did not bind")

            print(f"step 1 · «Материалы»: upload 10 MP4 variants of {args.mp4.name} as source_video")
            cdp("Page.navigate", {"url": f"{LOCAL_DESKTOP_ORIGIN}/#/workspace/media?project_id={project_id}"})
            if not wait_js("Boolean(document.querySelector('#media-upload-form #media-file'))", 30):
                raise SystemExit("materials upload form did not appear")
            time.sleep(0.5)
            set_files("#media-upload-form #media-file", variants)
            time.sleep(0.5)
            prepared = evaluate(
                "(() => { const form = document.querySelector('#media-upload-form'); if (!form) return 'missing';"
                " const kind = form.elements.kind; kind.value = 'source_video'; kind.dispatchEvent(new Event('change', { bubbles: true }));"
                " const rights = form.elements.rights_confirmed; if (rights && !rights.checked) rights.click();"
                " return { files: form.elements.file?.files?.length, kind: kind.value, rights: rights?.checked,"
                "   invalid: [...form.elements].filter((n) => typeof n.checkValidity === 'function' && !n.checkValidity()).map((n) => n.name) }; })()"
            )
            print("   upload form:", json.dumps(prepared, ensure_ascii=False))
            evaluate("document.querySelector('#media-upload-form').requestSubmit(); true")
            stop = time.monotonic() + args.step_timeout * 2
            last = None
            while time.monotonic() < stop:
                drain_toasts("materials")
                count = evaluate(
                    "(() => { const form = document.querySelector('#media-upload-form'); const busy = form?.dataset?.busy || '';"
                    " const cards = document.querySelectorAll('.media-grid .media-card, .media-grid [data-media-id]').length;"
                    " const summary = document.querySelector('#selected-file-summary')?.textContent?.trim() || '';"
                    " return { busy, cards, summary: summary.slice(0, 120) }; })()"
                )
                key = json.dumps(count, ensure_ascii=False)
                if key != last:
                    print("   materials:", key)
                    last = key
                if count and count.get("busy") != "true" and toasts_seen:
                    break
                time.sleep(1.0)
            screenshot("1-materials")

            print("step 2 · generation → «Видео по стратегии» → viral_rebuild")
            cdp("Page.navigate", {"url": f"{LOCAL_DESKTOP_ORIGIN}/#/workspace/generation?project_id={project_id}"})
            if not wait_js("Boolean(document.querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound)", 30):
                raise SystemExit("generation form did not bind")
            click('[data-generation-intake-route="strategy_video"]')
            if not wait_js("document.querySelector('#mock-batch-form')?.elements?.generation_strategy_id?.value === 'viral_rebuild'", 20):
                problems.append("strategy did not switch to viral_rebuild")
            time.sleep(1.5)
            state = wait_settled("open", 30)
            screenshot("2-opened")

            print("step 3 · source picker: exactly ten selected, free duration probe")
            for attempt in range(1, 30):
                state = native_state()
                if state.get("selected") == 10 and state.get("ready") is True:
                    break
                if state.get("probeRequired"):
                    print(f"   probe required for {state['probeRequired']} sources → click «{state.get('submit')}»")
                    click('[data-action="probe-generation-strategy-media"]') or click("#generation-submit")
                    wait_settled(f"probe{attempt}", args.step_timeout)
                    continue
                if (state.get("selected") or 0) < 10:
                    # Пикер перерисовывается после каждого клика: отмечаем по одному
                    # и ждём новый DOM, иначе клики уходят в отсоединённые узлы.
                    picked = evaluate(
                        "(() => { const box = [...document.querySelectorAll('#mock-batch-form input[name=generation_strategy_source_selection]')]"
                        "   .find((b) => !b.checked && !b.disabled); if (!box) return null; box.click(); return box.value; })()"
                    )
                    if picked is None:
                        print("   no selectable source left")
                        break
                    time.sleep(0.4)
                    continue
                break
            state = native_state()
            print("   picker:", json.dumps({k: state[k] for k in ("selected", "ready", "probeRequired", "submit", "blocker")}, ensure_ascii=False))
            screenshot("3-sources")

            print("step 4 · mechanics for every selected source, product photo, attestations, output, brief")
            sources = evaluate(
                "JSON.stringify((window.ContentEngineGenerationGuidedV4?.getStrategySourcePickerProjection?.(document.querySelector('#mock-batch-form'))?.selected || []).map((s) => s.source_media_id))"
            )
            source_ids = json.loads(sources or "[]")
            applied = evaluate(
                "(() => { const form = document.querySelector('#mock-batch-form'); const ids = " + json.dumps(source_ids) + ";"
                " return ids.map((id) => window.ContentEngineGenerationGuidedV4?.setStrategyMechanicsDraft?.(form, id, " + json.dumps(MECHANICS, ensure_ascii=False) + ")); })()"
            )
            print(f"   mechanics applied: {applied}")
            product = evaluate(
                "(() => { const form = document.querySelector('#mock-batch-form');"
                " const boxes = [...form.querySelectorAll('input[name=media_id]')].filter((b) => !b.disabled);"
                " if (!boxes.length) return 'no product photos'; const box = boxes[0]; if (!box.checked) box.click();"
                " const primary = form.querySelector('input[name=primary_media_id][value=\"' + box.value + '\"]'); if (primary && !primary.checked) primary.click();"
                " return { photos: boxes.length, picked: box.value, primary: Boolean(primary) }; })()"
            )
            print("   product:", json.dumps(product, ensure_ascii=False))
            attest = evaluate(
                "(() => { const boxes = [...document.querySelectorAll('#generation-strategy-assets input[data-generation-strategy-attestation]')];"
                " boxes.forEach((b) => { if (!b.checked && !b.disabled) b.click(); }); return boxes.map((b) => [b.dataset.generationStrategyAttestation, b.checked]); })()"
            )
            print("   attestations:", attest)
            output = evaluate(
                "(() => { const form = document.querySelector('#mock-batch-form'); const out = {};"
                " for (const name of ['generation_strategy_audio', 'generation_strategy_ratio', 'generation_strategy_resolution']) {"
                "   const select = form.elements[name]; if (!(select instanceof HTMLSelectElement) || select.disabled) { out[name] = 'n/a'; continue; }"
                "   if (!select.value) { const option = [...select.options].find((o) => o.value && !o.disabled && (name !== 'generation_strategy_audio' || o.value === 'false')) || [...select.options].find((o) => o.value && !o.disabled);"
                "     if (option) { select.value = option.value; select.dispatchEvent(new Event('change', { bubbles: true })); } }"
                "   out[name] = select.value; } return out; })()"
            )
            print("   output:", json.dumps(output))
            category = evaluate(
                "(() => { const select = document.querySelector('#mock-batch-form')?.elements?.product_category; if (!select) return 'missing';"
                " if (!select.value) { select.value = 'sports_food'; select.dispatchEvent(new Event('change', { bubbles: true })); } return select.value; })()"
            )
            print("   product_category:", category)
            brief = evaluate(
                "(() => { const brief = document.querySelector('#mock-batch-form')?.elements?.brief; if (!brief) return 'missing';"
                " if (!brief.value.trim()) { brief.value = 'Новый рекламный ролик про домашний гриль: быстро, честно, с крупными планами мяса и финальной тарелкой.';"
                "   brief.dispatchEvent(new Event('input', { bubbles: true })); brief.dispatchEvent(new Event('change', { bubbles: true })); } return brief.value.length; })()"
            )
            print("   brief length:", brief)
            state = wait_settled("inputs", 20)
            invalid = evaluate(
                "JSON.stringify([...document.querySelector('#mock-batch-form').elements].filter((n) => typeof n.checkValidity === 'function' && !n.checkValidity())"
                ".map((n) => ({ name: n.name, visible: Boolean(n.offsetParent), message: n.validationMessage })))"
            )
            print("   invalid controls:", invalid)
            screenshot("4-inputs")

            print("step 5 · free steps of the native wizard")
            boundary = False
            for attempt in range(1, 40):
                state = native_state()
                approvals = evaluate(
                    "(() => { const boxes = [...document.querySelectorAll('#mock-batch-form input[name=generation_strategy_spec_approval]')];"
                    " const pending = boxes.filter((box) => !box.checked && !box.disabled); pending.forEach((box) => box.click()); return [boxes.length, pending.length]; })()"
                )
                if approvals and approvals[1]:
                    print(f"   approved spec versions: {approvals[1]} of {approvals[0]}")
                    wait_settled(f"approve{attempt}", 30)
                    continue
                if state.get("busy") == "true":
                    wait_settled(f"busy{attempt}", args.step_timeout)
                    continue
                if not state.get("submitDisabled") and state.get("phase") not in ("strategy_product_swap_paid_review", "strategy_rebuild_paid_review"):
                    print(f"   click native «{state.get('submit')}» (phase {state.get('phase')})")
                    before = evaluate("document.querySelector('#mock-batch-form')?.dataset?.generationStrategyLastFailureAt || ''")
                    click("#generation-submit")
                    time.sleep(0.8)
                    after_state = wait_settled(f"native{attempt}", args.step_timeout)
                    after = evaluate("document.querySelector('#mock-batch-form')?.dataset?.generationStrategyLastFailureAt || ''")
                    if after and after != before:
                        reason = evaluate("document.querySelector('#mock-batch-form')?.dataset?.generationStrategyLastFailure || ''")
                        print(f"   server refused: {reason}")
                        boundary = "сервису генерации не настроен" in str(reason)
                        if not boundary:
                            problems.append(f"native step refused: {reason}")
                        break
                    if any("сервису генерации не настроен" in line for line in problems):
                        boundary = True
                        print("   queue preflight reached the provider-readiness check")
                        break
                    if after_state.get("submit") == state.get("submit") and after_state.get("phase") == state.get("phase"):
                        print("   native button did not move; stopping")
                        invalid = evaluate(
                            "JSON.stringify([...document.querySelector('#mock-batch-form').elements].filter((n) => typeof n.checkValidity === 'function' && !n.checkValidity())"
                            ".map((n) => ({ name: n.name, visible: Boolean(n.offsetParent), message: n.validationMessage })))"
                        )
                        print("   invalid controls:", invalid)
                        problems.append(f"native wizard stuck at «{state.get('submit')}»")
                        break
                    continue
                if "paid_review" in str(state.get("phase")):
                    print(f"   reached paid review: «{state.get('submit')}»")
                    break
                print(f"   native button idle: «{state.get('submit')}» phase={state.get('phase')} blocker={state.get('blocker')}")
                problems.append(f"native wizard blocked: {state.get('blocker')}")
                break
            screenshot("5-native")
            print("final:", json.dumps(native_state(), ensure_ascii=False))
            if boundary:
                problems[:] = [
                    line for line in problems
                    if "сервису генерации не настроен" not in line and "functions/v1/creator-generate" not in line
                    and "Очередь не продвинулась" not in line
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
    problems = [line for line in problems if "favicon.ico" not in line and "creator_workspace_trash_browser" not in line]
    if problems:
        print("PROBLEMS:")
        for line in problems:
            print(" -", line)
        return 1
    print("OK: rebuild flow completed without errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
