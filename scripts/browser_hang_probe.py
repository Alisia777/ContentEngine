#!/usr/bin/env python3
"""Catch a frozen main thread in the Desktop generation form and print its stack.

Reproduces: login as the local fixture owner, open the generation route, pick
a route (default «Копия»), select an MP4 through CDP, wait, then interrupt the
page with Debugger.pause. A JS loop that blocks the main thread cannot be
observed with Runtime.evaluate (it never returns); Debugger.pause is delivered
as an interrupt and yields the call frames of whatever is spinning.

Usage: python scripts/browser_hang_probe.py [--route copy_video] [--wait 4]
"""

from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", default="copy_video")
    parser.add_argument("--wait", type=float, default=4.0)
    parser.add_argument("--mp4", type=Path, default=UPLOAD_PROBE_MP4)
    args = parser.parse_args()
    from websockets.sync.client import connect

    credentials = json.loads((ROOT / ".local" / "owner.local.json").read_text(encoding="utf-8"))
    project_id = local_project_id()
    profile = Path(tempfile.mkdtemp(prefix="contentengine-hang-probe-"))
    process = subprocess.Popen([
        chrome_path(), "--headless=new", "--disable-gpu", "--disable-extensions", "--no-sandbox",
        "--remote-debugging-port=0", "--remote-allow-origins=*", f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
            events: list[dict] = []

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
                        return message
                    events.append(message)
                raise TimeoutError(method)

            def wait_js(expression: str, seconds: float) -> bool:
                stop = time.monotonic() + seconds
                while time.monotonic() < stop:
                    result = cdp("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    if result["result"]["result"].get("value") is True:
                        return True
                    time.sleep(0.1)
                return False

            cdp("Page.enable")
            cdp("Runtime.enable")
            cdp("Debugger.enable")
            cdp("Emulation.setDeviceMetricsOverride", {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False})
            cdp("Page.navigate", {"url": f"{LOCAL_DESKTOP_ORIGIN}/"})
            if not wait_js("location.hash === '#/login' && Boolean(document.querySelector('input[type=email]'))", 20):
                raise SystemExit("login screen did not appear")
            cdp("Runtime.evaluate", {"expression": f"""
(() => {{
  const email = document.querySelector('input[type=email]');
  const password = document.querySelector('input[type=password]');
  email.value = {json.dumps(credentials['email'])};
  password.value = {json.dumps(credentials['password'])};
  email.dispatchEvent(new Event('input', {{ bubbles: true }}));
  password.dispatchEvent(new Event('input', {{ bubbles: true }}));
  email.form.requestSubmit();
  return true;
}})()""", "returnByValue": True})
            if not wait_js("location.hash.startsWith('#/workspace/') && Boolean(document.querySelector('#main-content'))", 20):
                raise SystemExit("workspace did not open")
            cdp("Page.navigate", {"url": f"{LOCAL_DESKTOP_ORIGIN}/#/workspace/generation?project_id={project_id}"})
            if not wait_js("Boolean(document.querySelector('#mock-batch-form')?.dataset.generationIntakeV4Bound)", 30):
                raise SystemExit("generation form did not bind")
            route_selector = "[data-generation-intake-route=" + json.dumps(args.route) + "]"
            cdp("Runtime.evaluate", {"expression": "document.querySelector(" + json.dumps(route_selector) + ")?.click()", "returnByValue": True})
            if not wait_js(f"document.querySelector('#mock-batch-form')?.dataset.generationIntakeV4Route === {json.dumps(args.route)}", 10):
                raise SystemExit("route did not switch")
            time.sleep(1.0)
            input_selector = (
                "[data-generation-intake-panel=" + json.dumps(args.route) + "] "
                + "input[data-generation-intake-mp4=\"single\"]"
            )
            located = cdp("Runtime.evaluate", {
                "expression": "document.querySelector(" + json.dumps(input_selector) + ")",
                "returnByValue": False,
            })
            object_id = located["result"]["result"].get("objectId")
            if not object_id:
                raise SystemExit("no single MP4 input in the panel")
            # Журнал синтетических input/change: кто и с каким значением дёргает
            # поля формы во время зависания. Читается потом из паузы отладчика.
            hooks = cdp("Runtime.evaluate", {"expression": """
(() => {
  window.__ceDispatchLog = [];
  const original = EventTarget.prototype.dispatchEvent;
  EventTarget.prototype.dispatchEvent = function (event) {
    if (event && (event.type === "change" || event.type === "input")) {
      const log = window.__ceDispatchLog;
      log.push({
        name: this?.name || this?.id || this?.tagName || "?",
        value: String(this?.value ?? "").slice(0, 40),
        type: event.type,
        stack: String(new Error().stack || "").split(String.fromCharCode(10)).slice(2, 7)
          .map((line) => line.trim().replace(/^at /, "").replace(/[?]v=[^:)]+/, "")).join(" < "),
      });
      if (log.length > 60) log.shift();
    }
    return original.call(this, event);
  };
  // Журнал requestAnimationFrame: кто планирует перемонтирование рабочего стола.
  window.__ceRafLog = [];
  const originalRaf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (callback) => {
    const log = window.__ceRafLog;
    log.push({
      callback: callback?.name || "<anon>",
      stack: String(new Error().stack || "").split(String.fromCharCode(10)).slice(2, 8)
        .map((line) => line.trim().replace(/^at /, "").replace(/[?]v=[^:)]+/, "").replace(/https?:[^ )]*[/]/, "")).join(" < "),
    });
    if (log.length > 40) log.shift();
    return originalRaf(callback);
  };
  // Журнал мутаций дерева: какие узлы добавляются/удаляются на каждом
  // перемонтировании рабочего стола (его наблюдатель слушает childList).
  window.__ceMutationLog = [];
  const describe = (node) => {
    if (!node) return "?";
    if (node.nodeType === 3) return `#text(${String(node.textContent || "").trim().slice(0, 30)})`;
    const tag = String(node.tagName || node.nodeName || "?").toLowerCase();
    const id = node.id ? `#${node.id}` : "";
    const cls = node.classList?.length ? `.${[...node.classList].slice(0, 3).join(".")}` : "";
    const data = node.dataset ? Object.keys(node.dataset).slice(0, 3).map((key) => `[${key}]`).join("") : "";
    return `${tag}${id}${cls}${data}`;
  };
  new MutationObserver((records) => {
    for (const record of records) {
      const log = window.__ceMutationLog;
      log.push({
        target: describe(record.target),
        added: [...record.addedNodes].map(describe).slice(0, 4).join(","),
        removed: [...record.removedNodes].map(describe).slice(0, 4).join(","),
      });
      if (log.length > 80) log.shift();
    }
  }).observe(document.querySelector("#app") || document.documentElement, { childList: true, subtree: true });
  return true;
})()""", "returnByValue": True})
            print("hooks installed:", json.dumps(hooks.get("result", {}))[:600])
            send("DOM.setFileInputFiles", {"objectId": object_id, "files": [str(args.mp4)]})
            print(f"file selected; waiting {args.wait}s before interrupting")
            time.sleep(args.wait)
            # Сначала — мягкая попытка прочитать строку статуса панели: если
            # поток свободен, она вернётся сразу и скажет, что экран думает о
            # файле; если висит — evaluate не вернётся, и ниже его прервёт пауза.
            try:
                status_probe = cdp("Runtime.evaluate", {
                    "expression": (
                        "JSON.stringify({ status: document.querySelector("
                        + json.dumps("[data-generation-intake-panel=" + json.dumps(args.route) + "] .generation-intake-v4__status")
                        + ")?.textContent || '', checklist: [...document.querySelectorAll("
                        + json.dumps("[data-generation-intake-panel=" + json.dumps(args.route) + "] .gi-check")
                        + ")].map((node) => node.textContent.trim().replace(/\s+/g, ' ')) })"
                    ),
                    "returnByValue": True,
                }, timeout=4)
                print("panel status:", status_probe.get("result", {}).get("result", {}).get("value"))
            except TimeoutError:
                print("panel status: main thread did not answer within 4s")
            pause_id = send("Debugger.pause")
            stop = time.monotonic() + 15
            paused = None
            while time.monotonic() < stop:
                try:
                    message = json.loads(ws.recv(timeout=stop - time.monotonic()))
                except Exception:
                    break
                if message.get("method") == "Debugger.paused":
                    paused = message["params"]
                    break
                events.append(message)
            if paused is None:
                print("IDLE: Debugger.pause found nothing running within 15s")
                return 0
            script_urls = {}
            for message in events:
                if message.get("method") == "Debugger.scriptParsed":
                    script_urls[message["params"].get("scriptId")] = message["params"].get("url", "")
            samples = 0
            busy_samples = 0
            while paused is not None and samples < 8:
                samples += 1
                frames = paused.get("callFrames", [])
                if any(
                    LOCAL_DESKTOP_ORIGIN in (frame.get("url", "") or script_urls.get(frame.get("location", {}).get("scriptId"), ""))
                    for frame in frames
                ):
                    busy_samples += 1
                print(f"--- sample {samples}: reason={paused.get('reason')} frames={len(frames)}")
                for frame in frames[:12]:
                    loc = frame.get("location", {})
                    url = frame.get("url", "") or script_urls.get(loc.get("scriptId"), "")
                    print(f"  {frame.get('functionName') or '<anon>'}  {url.rsplit('/', 1)[-1]}:{loc.get('lineNumber', 0) + 1}:{loc.get('columnNumber', 0) + 1}")
                if frames:
                    probe_expression = (
                        "(() => { const f = document.querySelector('#mock-batch-form'); "
                        "return JSON.stringify({ engine: f?.elements?.generation_intake_engine?.value, "
                        "duration: f?.elements?.generation_strategy_duration_seconds?.value, "
                        "route: f?.dataset?.generationIntakeV4Route, step: f?.dataset?.ceV4GenerationStep, "
                        "busy: f?.dataset?.busy, strategy: f?.elements?.generation_strategy_id?.value, "
                        "resolution: f?.elements?.generation_strategy_resolution?.value, "
                        "ratio: f?.elements?.generation_strategy_ratio?.value, "
                        "launch: f?.elements?.generation_launch_enabled?.value }); })()"
                    )
                    evaluated = cdp("Debugger.evaluateOnCallFrame", {
                        "callFrameId": frames[0]["callFrameId"],
                        "expression": probe_expression,
                        "returnByValue": True,
                    })
                    print("  state:", evaluated.get("result", {}).get("result", {}).get("value"))
                    if samples in (1, 4):
                        dispatch_log = cdp("Debugger.evaluateOnCallFrame", {
                            "callFrameId": frames[0]["callFrameId"],
                            "expression": "JSON.stringify((window.__ceDispatchLog || []).slice(-24))",
                            "returnByValue": True,
                        })
                        entries = json.loads(dispatch_log.get("result", {}).get("result", {}).get("value") or "[]")
                        print(f"  dispatch log: {len(entries)} entries")
                        for entry in entries:
                            print(f"  dispatch {entry['type']:6} {entry['name']}={entry['value']!r}  <- {entry['stack']}")
                        mutation_log = cdp("Debugger.evaluateOnCallFrame", {
                            "callFrameId": frames[0]["callFrameId"],
                            "expression": "JSON.stringify((window.__ceMutationLog || []).slice(-40))",
                            "returnByValue": True,
                        })
                        raf_log = cdp("Debugger.evaluateOnCallFrame", {
                            "callFrameId": frames[0]["callFrameId"],
                            "expression": "JSON.stringify((window.__ceRafLog || []).slice(-16))",
                            "returnByValue": True,
                        })
                        for entry in json.loads(raf_log.get("result", {}).get("result", {}).get("value") or "[]"):
                            print(f"  raf {entry['callback']}  <- {entry['stack']}")
                        mutations = json.loads(mutation_log.get("result", {}).get("result", {}).get("value") or "[]")
                        print(f"  mutation log: {len(mutations)} entries")
                        for entry in mutations:
                            print(f"  mutation @{entry['target']}  +[{entry['added']}]  -[{entry['removed']}]")
                send("Debugger.resume")
                time.sleep(0.3)
                send("Debugger.pause")
                paused = None
                stop = time.monotonic() + 10
                while time.monotonic() < stop:
                    try:
                        message = json.loads(ws.recv(timeout=stop - time.monotonic()))
                    except Exception:
                        break
                    if message.get("method") == "Debugger.paused":
                        paused = message["params"]
                        break
            verdict = "BUSY" if busy_samples >= 3 else "IDLE"
            print(f"{verdict}: {busy_samples}/{samples} samples caught the page's own scripts on the main thread")
            return 1 if verdict == "BUSY" else 0
    finally:
        process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
