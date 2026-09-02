from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import base64
import json
import os
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
SUBJECT = (APP / "workspace-os-v4-generation-guided.js").read_text(encoding="utf-8")
CSS = (APP / "workspace-os-v4-generation-guided.css").read_text(encoding="utf-8")
VISUALS = (APP / "generation-model-visuals-v1.js").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
PORTAL = (APP / "app.js").read_text(encoding="utf-8")
INDEX = (APP / "index.html").read_text(encoding="utf-8")
HARNESS = ROOT / "tests" / "fixtures" / "workspace_generation_model_picker_v1_harness.html"


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
        pytest.skip("Chrome/Chromium is unavailable for model-picker runtime QA")
    return chrome


def _run_fixture(width: int, height: int = 900) -> dict[str, object]:
    try:
        from websockets.sync.client import connect
    except ImportError:
        pytest.skip("websockets is required for exact Chrome viewport emulation")

    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    profile = tempfile.mkdtemp(prefix="ce-generation-model-picker-")
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
                {"url": f"http://127.0.0.1:{server.server_port}/{HARNESS.relative_to(ROOT).as_posix()}"},
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                ready = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": 'document.body?.dataset.fixtureGenerationModelsReady || ""',
                        "returnByValue": True,
                    },
                )
                if ready.get("result", {}).get("result", {}).get("value") == "true":
                    break
                time.sleep(0.04)
            else:
                diagnostic = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": "JSON.stringify(window.__generationFixture?.errors || [])",
                        "returnByValue": True,
                    },
                )
                errors = diagnostic.get("result", {}).get("result", {}).get("value", "[]")
                raise AssertionError(
                    f"Generation model picker fixture did not become ready: {errors}"
                )

            result = cdp(
                "Runtime.evaluate",
                {
                    "expression": 'JSON.parse(document.querySelector("#fixture-result").textContent)',
                    "returnByValue": True,
                },
            )
            assert "exceptionDetails" not in result.get("result", {}), result
            screenshot_directory = os.environ.get(
                "CONTENTENGINE_GENERATION_SCREENSHOT_DIR", ""
            ).strip()
            if screenshot_directory:
                screenshot_path = Path(screenshot_directory)
                screenshot_path.mkdir(parents=True, exist_ok=True)
                capture_options = {
                    "format": "png",
                    "fromSurface": True,
                    "captureBeyondViewport": False,
                }
                overview = cdp("Page.captureScreenshot", capture_options)
                (screenshot_path / f"generation-overview-{width}.png").write_bytes(
                    base64.b64decode(overview["result"]["data"])
                )
                cdp(
                    "Runtime.evaluate",
                    {
                        "expression": "(() => { const advisor=document.querySelector('[data-ce-v4-model-advisor]'); const panel=advisor?.closest('.ce-v4-generation-guided__panel-content'); if(panel) panel.scrollTop=advisor.offsetTop; if(advisor) window.scrollTo(0, window.scrollY + advisor.getBoundingClientRect().top - 12); return new Promise((resolve) => setTimeout(resolve, 120)); })()",
                        "awaitPromise": True,
                    },
                )
                picker = cdp("Page.captureScreenshot", capture_options)
                (screenshot_path / f"generation-model-picker-{width}.png").write_bytes(
                    base64.b64decode(picker["result"]["data"])
                )
            return result["result"]["result"]["value"]
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


def test_picker_reuses_one_form_and_keeps_recommendation_advisory() -> None:
    assert 'from "./generation-model-recommendation.js?v=20260826.rebuild-clean.53"' in SUBJECT
    assert SUBJECT.count("function createModelAdvisor()") == 1
    assert SUBJECT.count('name = "generation_model"') == 1
    assert "modelCanUseExistingLaunch" in SUBJECT
    assert "generationModelCatalog" in SUBJECT
    advisory_actions = SUBJECT[
        SUBJECT.index("function applyModelIdentity(") : SUBJECT.index("function handleFormClick(")
    ]
    assert ".checked = true" not in advisory_actions
    assert "requestSubmit" not in advisory_actions
    assert '.dispatchEvent(new Event("submit"' not in advisory_actions
    assert "contentengine:generation-repeat-settings" in SUBJECT
    assert "fetch(" not in SUBJECT
    assert "localStorage" not in SUBJECT
    assert "sessionStorage.setItem" in SUBJECT  # existing guided-step convenience only
    assert ".ce-v4-model-advisor__grid" in CSS
    assert ".ce-v4-model-card[data-available=\"false\"]" in CSS
    assert ".ce-v4-model-selection-summary" in CSS
    assert "prefers-reduced-motion: reduce" in CSS
    assert "function exposeProviderReadinessControl(form)" in SUBJECT
    assert "sql_authority_parity_pending" in SUBJECT
    assert "premium_model_launch_unsupported" in SUBJECT
    assert "direct_google_disabled" in SUBJECT
    assert "ce-v4-generation-guided__preflight" in CSS
    assert ".ce-v4-generation-guided__preflight {\n  min-height: 44px;" in CSS
    assert "min-height: 44px;\n  min-width: 112px;" in CSS


def test_model_visuals_are_local_presentation_only_and_cover_the_catalog() -> None:
    assert 'from "./generation-model-visuals-v1.js?v=20260826.rebuild-clean.53"' in SUBJECT
    assert "function modelVisualNode(" in SUBJECT
    assert "ce-v4-model-card__visual--featured" in SUBJECT
    assert "ce-v4-model-card__image" in CSS
    assert ".ce-v4-model-card[data-available=\"false\"] .ce-v4-model-card__image" in CSS
    assert "@media (prefers-reduced-motion: reduce)" in CSS
    assert VISUALS.count('family: "') == 10
    assert VISUALS.count("content-factory-model-family-") == 5
    assert "http://" not in VISUALS
    assert "https://" not in VISUALS
    for identity in (
        "runway:seedream5_lite",
        "runway:gen4_turbo",
        "runway:seedance2_fast",
        "runway:gen4.5",
        "runway:seedance2_mini",
        "runway:veo3.1_fast",
        "runway:gemini_omni_flash",
        "runway:veo3.1",
        "runway:seedance2",
        "google:veo-3.1-lite-generate-preview",
    ):
        assert f'"{identity}"' in VISUALS


def test_real_generation_route_loads_guided_adapter_into_the_single_portal_form() -> None:
    assert 'route === "/workspace/generation"' in LOADER
    assert "workspace-os-v4-generation-guided.css" in LOADER
    assert "workspace-os-v4-generation-guided.js" in LOADER
    assert PORTAL.count('id="mock-batch-form"') == 1
    assert "function renderGenerationSection(" in PORTAL
    assert 'form.id === "mock-batch-form"' in PORTAL
    assert "await submitGenerationBatch(form)" in PORTAL
    assert "workspace-os-v4-loader.js" in INDEX


@pytest.mark.parametrize("width", [1280, 390, 320])
def test_picker_runtime_manual_lock_and_geometry(width: int) -> None:
    result = _run_fixture(width)
    assert result["modelCount"] == 10
    assert result["executableCount"] == 7
    assert result["advisorCount"] == 1
    assert result["formCount"] == 1
    assert result["originalModePreserved"] is True
    assert result["pendingRepeatPaymentUnchecked"] is True
    assert "Gen-4 Turbo" in result["pendingRepeatSummary"]
    assert "8 сек. · 16:9 · 720p" in result["pendingRepeatSummary"]
    assert result["selectedBefore"] == "runway:gen4_turbo"
    assert result["selectedAfterManual"] == "runway:seedance2_fast"
    assert result["selectedAfterContextChange"] == "runway:seedance2_fast"
    assert result["legacyModeAfterManual"] == "real_seedance"
    assert result["seedancePromptLimit"] == 3500
    assert result["seedanceModelForm"] == "runway:seedance2_fast"
    assert result["recommendationModelBeforeApply"] == "seedance2_fast"
    assert result["comparisonBeforeApply"] is False
    assert result["whyRecommendationAvailable"] is True
    assert result["appliedRecommendationSelection"] == "runway:seedance2_fast"
    assert result["appliedRecommendationMode"] == "real_seedance"
    assert result["appliedRecommendationPaymentUnchecked"] is True
    assert result["repeatSelection"] == "runway:gen4.5"
    assert result["repeatMode"] == "real_gen4"
    assert result["repeatBlocked"] is False
    assert result["repeatModeValidation"] == ""
    assert "Gen-4.5" in result["repeatSummary"]
    assert "Выбор зафиксирован" in result["repeatSummary"]
    assert result["repeatPaymentUnchecked"] is True
    assert result["repeatResolution"] == "720p"
    assert result["repeatAudio"] == "false"
    assert result["recoveredSelection"] == "runway:gen4_turbo"
    assert result["recoveredModeValidation"] == ""
    assert result["supportedRepeatSelection"] == "runway:seedance2_fast"
    assert result["supportedRepeatMode"] == "real_seedance"
    assert result["supportedRepeatModeValidation"] == ""
    assert "Seedance 2 Fast" in result["supportedRepeatSummary"]
    assert "8 сек. · 9:16 · 720p" in result["supportedRepeatSummary"]
    assert "генерируемый звук" in result["supportedRepeatSummary"]
    assert "фото" in result["supportedRepeatSummary"]
    assert result["supportedRepeatPaymentUnchecked"] is True
    assert result["veoSilentProxyMode"] == "real_gen4"
    assert result["veoExactProvider"] == "runway"
    assert result["veoExactModel"] == "veo3.1_fast"
    assert result["veoPromptLimit"] == 1000
    assert result["veoModelForm"] == "runway:veo3.1_fast"
    assert result["exactSettingsInsideOwnerForm"] is True
    assert result["ratioStillSubmitted"] is True
    assert result["exactAudioStillSubmitted"] is True
    assert "Показаны только сочетания" in result["capabilityStatus"]
    assert result["emptyPremiumFilterExplained"] is True
    assert result["experimentalFilterPressed"] is True
    assert result["experimentalCardsShown"] == 7
    assert "Ваш выбор" in result["manualCopy"]
    assert "Технический подбор модели" in result["recommendationCopy"]
    assert result["newModelVisible"] is True
    assert result["newModelDisabled"] is False
    assert "из одного исходного кадра" in result["geminiExecutableFit"]
    assert "2K" in result["seedreamExecutableOutput"]
    assert "1:1" in result["seedreamExecutableOutput"]
    assert "3K" not in result["seedreamExecutableOutput"]
    assert result["providerCount"] == 2
    assert result["defaultVisibleModelCount"] <= 4
    assert result["defaultFilterPressed"] is True
    assert result["contentKindChoiceCount"] == 2
    assert result["numberedHeadingCount"] == 5
    assert result["filterCount"] == 6
    assert result["selectionSummaryCount"] == 1
    assert result["nativeRadioCount"] == 10
    assert result["modelVisualCount"] == 10
    assert result["modelVisualImageCount"] == 10
    assert result["modelVisualFamilyCount"] == 5
    assert result["modelVisualsLocal"] is True
    assert result["modelVisualsDecorative"] is True
    assert result["recommendationVisualCount"] == 1
    assert result["exactModelVisualCount"] == 1
    assert result["exactModelVisualFamily"] == "veo"
    assert result["exactModelVisualTone"] == "gold"
    assert result["technicalDetailsCollapsed"] is True
    assert result["disabledCardsKeyboardReachable"] is True
    assert result["completeCardCopy"] is True
    assert result["paymentStillUnchecked"] is True
    assert result["freePreflightVisible"] is True
    assert "бесплат" in result["preflightPhaseCopy"].lower()
    assert "не запустится" in result["preflightPhaseCopy"].lower()
    assert "платный запуск" in result["paidPhaseCopy"].lower()
    assert result["finalStepActive"] is True
    assert result["finalPreflightActuallyVisible"] is True
    assert result["finalSubmitActuallyVisible"] is True
    assert "Google" in result["googleDisabledReasonCopy"]
    assert "сравнения" in result["premiumDisabledReasonCopy"]
    assert result["apiCalls"] == 1
    assert result["submitCalls"] == 0
    assert result["browserErrors"] == []
    assert result["rootFits"] is True
    assert result["formFits"] is True
    assert result["advisorFits"] is True
    if width <= 760:
        assert result["mobileInteractiveTargetCount"] >= 10
        assert result["mobileInteractiveTargetMinHeight"] >= 44


def test_picker_module_parses_when_node_is_available() -> None:
    node = shutil.which("node")
    if not node:
        return
    completed = subprocess.run(
        [node, "--check", str(APP / "workspace-os-v4-generation-guided.js")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
