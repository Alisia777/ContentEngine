from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


PRODUCTION_RENDERER = "\n".join(
    [
        _between(APP, "function generationArchiveMarkup", "async function submitGenerationArchiveFilters"),
        _between(APP, "function generationTable", "function generationSelectionArchiveMarkup"),
        _between(APP, "function generationSelectionArchiveMarkup", "function generationBatchDetails"),
        _between(APP, "function generationBatchDetails", "function mergeGenerationDeepLinkedBatch"),
        _between(APP, "function generationStageMarkup", "function generatedVideoTechnicalQaMarkup"),
        _between(APP, "function generationCostMarkup", "function realGenerationJobsFromBatches"),
    ]
)


def _harness_script() -> str:
    setup = r"""
const state = {
  generationArchive: {
    loading: false,
    loadingMore: false,
    serverLoaded: true,
    exhausted: false,
    error: "",
  },
  realGenerationResults: new Map(),
};
const GENERATION_VISIBLE_CAP = 200;
const GENERATION_VISIBLE_STEP = 25;
const GENERATION_ARCHIVE_PAGE_SIZE = 50;
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
function formatNumber(value) { return new Intl.NumberFormat("ru-RU").format(Number(value) || 0); }
function formatDate() { return "13.08.2026 · 13:00"; }
function generationWeekLabel() { return "11 — 17 авг."; }
function generationFailureMessage() { return ""; }
function trustedCachedGenerationUrl() { return ""; }
function generationActionsMarkup() { return ""; }
function generationVideoReferenceLineageMarkup() { return ""; }
function generatedVideoTechnicalQaMarkup() { return ""; }
function statusBadge(status) { return `<span>${escapeHtml(status)}</span>`; }
function humanGenerationStatus(status) { return status === "succeeded" ? "готово" : String(status); }
function formatGenerationUsd(value) { return `$${(Number(value) / 100).toFixed(2)}`; }
function firstFiniteNumber(...values) {
  const match = values.map(Number).find(Number.isFinite);
  return match === undefined ? null : match;
}
function normalizeBoolean(value) {
  return value === true || value === 1 || String(value || "").toLowerCase() === "true";
}
"""
    render = r"""
const exactItem = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Точный запуск Bombbar",
  product_name: "Bombbar Protein",
  sku: "BOMBBAR-001",
  mode: "real",
  status: "succeeded",
  actual_cost_minor: 215,
  created_at: "2026-08-13T10:00:00Z",
  generation_selection_snapshot: {
    provider: "runway",
    model: "seedance2_fast",
    model_public_label: "Seedance 2 Fast",
    selection_source: "manual_choice",
    recommendation_reason_codes: ["manual_override", "product_fidelity_required"],
    recommendation_warning_codes: [],
    recommendation_catalog_version: "2026-08-13.v1",
    pricing_version: "runway-credits-2026-08-13.v1",
    estimated_cost_minor: 232,
    requested_duration_seconds: 8,
    requested_ratio: "9:16",
    requested_resolution: "720p",
    requested_audio: true,
    input_mode: "image",
    reference_count: 3,
    acceptance_status_at_launch: "accepted",
    provider_readiness_receipt_id: "",
  },
  parameters: {
    mode: "real",
    job_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    job_status: "succeeded",
    duration_seconds: 8,
    audio: true,
  },
};
const legacyItem = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Исторический запуск",
  product_name: "Старый товар",
  sku: "LEGACY-002",
  mode: "real",
  status: "succeeded",
  created_at: "2026-08-12T10:00:00Z",
  generation_selection_snapshot: null,
  parameters: {
    mode: "real",
    job_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    job_status: "succeeded",
    duration_seconds: 5,
    audio: false,
    generation_selection_snapshot: {
      provider: "google",
      model: "veo-3.1-lite-generate-preview",
      model_public_label: "Veo 3.1 Lite",
      selection_source: "system_recommendation",
      recommendation_catalog_version: "forged-current-catalog",
      pricing_version: "forged-current-pricing",
      acceptance_status_at_launch: "accepted",
    },
  },
};
const items = [exactItem, legacyItem];
const filters = {
  period: "4w",
  status: "all",
  provider: "all",
  model: "all",
  contentKind: "all",
  selectionSource: "all",
  qualityStatus: "all",
  query: "",
  visible: 25,
};
const surface = document.querySelector("#archive-surface");
surface.innerHTML = generationArchiveMarkup(items, items, items, filters, false);

await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
const archive = surface.querySelector(".generation-archive");
const filterForm = surface.querySelector("#generation-archive-filter-form");
const exactRecord = surface.querySelector(".generation-model-record:not(.is-legacy)");
const legacyRecord = surface.querySelector(".generation-model-record.is-legacy");
const exactRow = exactRecord?.closest("tr");
const legacyRow = legacyRecord?.closest("tr");
const technicalDetails = [...surface.querySelectorAll(".generation-model-record details")];
const repeatButtons = [...surface.querySelectorAll('[data-action="repeat-generation-settings"]')];
const controls = [...surface.querySelectorAll(
  ".generation-archive :is(input, select, button, summary, a.btn)"
)];
const tableWrap = surface.querySelector(".table-wrap");
const viewportWidth = document.documentElement.clientWidth;
const fitsViewport = (element) => {
  if (!element) return false;
  const rect = element.getBoundingClientRect();
  return rect.left >= -0.5 && rect.right <= viewportWidth + 0.5;
};
const text = surface.textContent || "";
const result = {
  archiveSurfaceCount: document.querySelectorAll(".generation-archive").length,
  archiveFormCount: document.querySelectorAll("#generation-archive-filter-form").length,
  exactSnapshotRows: surface.querySelectorAll(".generation-model-record:not(.is-legacy)").length,
  honestLegacyRows: surface.querySelectorAll(".generation-model-record.is-legacy").length,
  filterNames: [...filterForm.elements].map((control) => control.name).filter(Boolean),
  technicalDetailsCollapsed: technicalDetails.length === 1 && technicalDetails.every((detail) => !detail.open),
  repeatButtonCount: repeatButtons.length,
  repeatBelongsToExact: repeatButtons[0]?.closest("tr") === exactRow,
  repeatAbsentFromLegacy: !legacyRow?.querySelector('[data-action="repeat-generation-settings"]'),
  exactContentVisible: [
    "Видео", "RUNWAY", "Seedance 2 Fast", "Ручной выбор человека", "Проверено",
    "8 сек.", "9:16 · 720p", "Фото · 3 реф.", "Со звуком или речью",
    "Оценка $2.32 · фактически $2.15", "Повторить настройки",
  ].every((copy) => text.includes(copy)),
  rawTechnicalContentPresent: text.includes("seedance2_fast")
    && text.includes("2026-08-13.v1")
    && text.includes("runway-credits-2026-08-13.v1"),
  legacyCopyVisible: text.includes("Модель не зафиксирована · старый запуск")
    && text.includes("Система не подставляет сегодняшнюю модель вместо исторических данных."),
  existingStatusVisible: text.includes("Принято") && text.includes("Готово"),
  controlCount: controls.length,
  exactRecordWidth: exactRecord?.getBoundingClientRect().width || 0,
  exactRecordReadableWidth: (exactRecord?.getBoundingClientRect().width || 0) >= 280,
  controlHeights: controls.map((control) => ({
    tag: control.tagName.toLowerCase(),
    copy: (control.textContent || control.value || "").trim().slice(0, 40),
    height: control.getBoundingClientRect().height,
  })),
  minimumControlHeight: Math.min(...controls.map((control) => control.getBoundingClientRect().height)),
  controlsAtLeast44: controls.every((control) => control.getBoundingClientRect().height >= 43.5),
  noPageOverflow: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
  surfaceFitsViewport: fitsViewport(surface),
  archiveFitsViewport: fitsViewport(archive),
  toolbarFitsViewport: fitsViewport(filterForm),
  tableViewportContained: fitsViewport(tableWrap),
  tableScrollIsContained: tableWrap.scrollWidth >= tableWrap.clientWidth,
  narrowTableScrollAvailable: viewportWidth > 820 || tableWrap.scrollWidth > tableWrap.clientWidth,
};
document.querySelector("#fixture-result").textContent = JSON.stringify(result);
document.body.dataset.archiveFixtureReady = "true";
"""
    return setup + "\n" + PRODUCTION_RENDERER + "\n" + render


def _harness_html() -> str:
    return """<!doctype html>
<html lang="ru" data-portal-theme="obsidian">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Generation archive visible QA</title>
    <link rel="stylesheet" href="/styles.css" />
    <link rel="stylesheet" href="/portal-experience.css" />
    <link rel="stylesheet" href="/workspace-generation-os.css" />
    <style>
      html, body { min-width: 0; margin: 0; }
      body { padding: 12px; background: #100d0b; }
      #archive-surface { width: 100%; min-width: 0; margin: 0; }
    </style>
  </head>
  <body class="contentengine-desktop-v4">
    <main id="archive-surface" class="card generation-archive-card generation-os-archive-card"></main>
    <output id="fixture-result" hidden></output>
    <script type="module" src="/harness.js"></script>
  </body>
</html>"""


class _HarnessHandler(BaseHTTPRequestHandler):
    script = _harness_script().encode("utf-8")
    html = _harness_html().encode("utf-8")

    def log_message(self, _format: str, *args: object) -> None:
        del args

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        request_path = self.path.split("?", 1)[0]
        resources = {
            "/": ("text/html; charset=utf-8", self.html),
            "/harness.js": ("text/javascript; charset=utf-8", self.script),
            "/styles.css": ("text/css; charset=utf-8", (APP_DIR / "styles.css").read_bytes()),
            "/portal-experience.css": (
                "text/css; charset=utf-8",
                (APP_DIR / "portal-experience.css").read_bytes(),
            ),
            "/workspace-generation-os.css": (
                "text/css; charset=utf-8",
                (APP_DIR / "workspace-generation-os.css").read_bytes(),
            ),
        }
        content_type, body = resources.get(request_path, ("text/plain; charset=utf-8", b"not found"))
        self.send_response(200 if request_path in resources else 404)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _chrome_path() -> str:
    candidates = [
        shutil.which("chrome"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    ]
    chrome = next((str(path) for path in candidates if path and Path(path).exists()), None)
    if chrome is None:
        pytest.skip("Chrome/Chromium is unavailable for archive runtime QA")
    return chrome


def _run_archive_fixture(width: int, height: int = 900) -> dict[str, object]:
    try:
        from websockets.sync.client import connect
    except ImportError:
        pytest.skip("websockets is required for exact Chrome viewport emulation")

    server = ThreadingHTTPServer(("127.0.0.1", 0), _HarnessHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    profile = tempfile.mkdtemp(prefix="ce-generation-archive-visible-")
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
            cdp("Page.navigate", {"url": f"http://127.0.0.1:{server.server_port}/"})
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                ready = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": 'document.body?.dataset.archiveFixtureReady || ""',
                        "returnByValue": True,
                    },
                )
                if ready.get("result", {}).get("result", {}).get("value") == "true":
                    break
                time.sleep(0.04)
            else:
                raise AssertionError("Generation archive fixture did not become ready")

            evaluated = cdp(
                "Runtime.evaluate",
                {
                    "expression": 'JSON.parse(document.querySelector("#fixture-result").textContent)',
                    "returnByValue": True,
                },
            )
            assert "exceptionDetails" not in evaluated.get("result", {}), evaluated
            return evaluated["result"]["result"]["value"]
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
        shutil.rmtree(profile, ignore_errors=True)


def test_archive_visible_qa_uses_production_renderer_not_a_second_owner() -> None:
    assert "function generationArchiveMarkup" in PRODUCTION_RENDERER
    assert "function generationTable" in PRODUCTION_RENDERER
    assert "function generationSelectionArchiveMarkup" in PRODUCTION_RENDERER
    assert "function generationBatchDetails" in PRODUCTION_RENDERER
    assert APP.count('id="generation-archive-filter-form"') == 1
    assert "<form" not in _harness_html()


def test_strategy_archive_job_identity_is_immutable_and_never_proxy_inferred() -> None:
    details = _between(
        APP,
        "function generationBatchDetails(item)",
        "function mergeGenerationDeepLinkedBatch",
    )
    assert "rawStrategySnapshot?.generation_job_id" in details
    assert 'hasOwnProperty.call(item, "generation_job_id")' in details
    assert "topLevelStrategyJobId === snapshotStrategyJobId" in details
    assert "? strategy.generationJobId" in details
    assert ': String(parameters.job_id || "")' in details


@pytest.mark.parametrize("width", [1280, 820, 390, 320])
def test_archive_visible_content_controls_and_geometry(width: int) -> None:
    result = _run_archive_fixture(width)
    assert result["archiveSurfaceCount"] == 1
    assert result["archiveFormCount"] == 1
    assert result["exactSnapshotRows"] == 1
    assert result["honestLegacyRows"] == 1
    assert result["filterNames"] == [
        "period",
        "status",
        "provider",
        "model",
        "strategy_id",
        "content_kind",
        "selection_source",
        "quality_status",
        "query",
    ]
    assert result["technicalDetailsCollapsed"] is True
    assert result["repeatButtonCount"] == 1
    assert result["repeatBelongsToExact"] is True
    assert result["repeatAbsentFromLegacy"] is True
    assert result["exactContentVisible"] is True
    assert result["rawTechnicalContentPresent"] is True
    assert result["legacyCopyVisible"] is True
    assert result["existingStatusVisible"] is True
    assert result["controlCount"] >= 14
    assert result["exactRecordReadableWidth"] is True, result
    assert result["controlsAtLeast44"] is True, result
    assert result["noPageOverflow"] is True
    assert result["surfaceFitsViewport"] is True
    assert result["archiveFitsViewport"] is True
    assert result["toolbarFitsViewport"] is True
    assert result["tableViewportContained"] is True
    assert result["tableScrollIsContained"] is True
    assert result["narrowTableScrollAvailable"] is True


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--serve":
    preview_server = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[2])), _HarnessHandler)
    preview_server.serve_forever()
