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
SUBJECT = (APP / "workspace-os-v4-generation-guided.js").read_text(encoding="utf-8")
CSS = (APP / "workspace-os-v4-generation-guided.css").read_text(encoding="utf-8")
PORTAL = (APP / "app.js").read_text(encoding="utf-8")
HARNESS = ROOT / "tests" / "fixtures" / "workspace_generation_strategy_v1_harness.html"
HARNESS_SOURCE = HARNESS.read_text(encoding="utf-8")

STRATEGY_IDS = ["viral_avatar_ugc", "viral_product_swap", "viral_rebuild"]
COMMON_RIGHTS = [
    "source_media_rights_confirmed",
    "transformative_use_confirmed",
    "product_assets_rights_confirmed",
    "depicted_people_consent_confirmed",
]
PRODUCT_MEDIA_ID = "44444444-4444-4444-8444-444444444444"
SOURCE_MEDIA_IDS = [
    f"10000000-0000-4000-8000-{index:012d}" for index in range(1, 11)
]


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
        pytest.skip("Chrome/Chromium is unavailable for generation-strategy runtime QA")
    return chrome


def _run_fixture(width: int, height: int = 960) -> dict[str, object]:
    try:
        from websockets.sync.client import connect
    except ImportError:
        pytest.skip("websockets is required for exact Chrome viewport emulation")

    handler = partial(_QuietHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    profile = tempfile.mkdtemp(prefix="ce-generation-strategy-v1-")
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
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
            pages = json.load(response)
        page = next(
            item
            for item in pages
            if item.get("type") == "page" and item.get("url") == "about:blank"
        )

        with connect(
            page["webSocketDebuggerUrl"], origin="http://localhost", open_timeout=5
        ) as websocket:
            request_id = 0

            def cdp(
                method: str, params: dict[str, object] | None = None
            ) -> dict[str, object]:
                nonlocal request_id
                request_id += 1
                websocket.send(
                    json.dumps(
                        {"id": request_id, "method": method, "params": params or {}}
                    )
                )
                while True:
                    response = json.loads(websocket.recv())
                    if response.get("id") == request_id:
                        return response

            cdp(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            cdp(
                "Page.navigate",
                {
                    "url": (
                        f"http://127.0.0.1:{server.server_port}/"
                        f"{HARNESS.relative_to(ROOT).as_posix()}"
                    )
                },
            )
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                ready = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": (
                            'document.body?.dataset.fixtureGenerationStrategiesReady || ""'
                        ),
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
                        "expression": (
                            "JSON.stringify(window.__generationStrategyFixture || {})"
                        ),
                        "returnByValue": True,
                    },
                )
                details = diagnostic.get("result", {}).get("result", {}).get(
                    "value", "{}"
                )
                raise AssertionError(
                    f"Generation strategy fixture did not become ready: {details}"
                )

            evaluated = cdp(
                "Runtime.evaluate",
                {
                    "expression": (
                        'JSON.parse(document.querySelector("#fixture-result").textContent)'
                    ),
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


def test_strategy_harness_is_server_catalog_driven_and_uses_the_portal_form() -> None:
    assert (
        'from "./generation-strategy-view.js?v=20260814.os4.41"' in SUBJECT
    )
    assert (
        'from "./generation-strategy-assets.js?v=20260814.os4.41"' in SUBJECT
    )
    assert "createGenerationStrategyViewState" in SUBJECT
    assert "reduceGenerationStrategyViewState" in SUBJECT
    assert "GENERATION_STRATEGY_SELECT_ACTION" in SUBJECT
    assert "generationStrategySelection" in SUBJECT
    assert "normalizeGenerationStrategyAssetCandidates" in SUBJECT
    assert "generationStrategyAssetEligibility" in SUBJECT
    assert "generationStrategyAssetCandidates" in SUBJECT
    assert 'model.model === "seedance2_fast"' not in SUBJECT
    assert "const proxyModel" not in SUBJECT
    assert 'node.id === "generation-strategy-assets"' in SUBJECT
    assert "input.checked = attestations" not in SUBJECT
    assert (
        'qa("#generation-strategy-assets input[data-generation-strategy-attestation]", form)'
        in SUBJECT
    )
    assert PORTAL.count('id="mock-batch-form"') == 1
    assert 'id="generation-strategy-assets"' in PORTAL
    assert "data-generation-strategy-source-picker" in PORTAL
    assert "data-generation-strategy-source-reviews" in PORTAL
    assert '.generation-strategy-card > button {' in CSS
    assert ".generation-strategy-attestation {\n  min-height: 44px;" in CSS

    assert "generation-strategy-catalog.js" in HARNESS_SOURCE
    assert "publicGenerationStrategyCatalog({ executionCapabilities })" in HARNESS_SOURCE
    assert "strategyCatalogVersion: enabledStrategies.version" in HARNESS_SOURCE
    assert "strategyRecipeVersion: enabledStrategies.recipe_version" in HARNESS_SOURCE
    assert "strategyPricingVersion: enabledStrategies.pricing_version" in HARNESS_SOURCE
    assert "generationStrategyAssetCandidates: assetCandidatesApi" in HARNESS_SOURCE
    assert HARNESS_SOURCE.count('id="mock-batch-form"') == 1
    assert "requestSubmit" not in HARNESS_SOURCE
    assert '.click();\n        await settle();' in HARNESS_SOURCE


@pytest.mark.parametrize("width", [1280, 390, 320])
def test_three_strategy_picker_runtime_contract_and_geometry(width: int) -> None:
    result = _run_fixture(width)

    assert result["catalogProjection"] == {
        "version": "2026-08-14.v1",
        "recipeVersion": "2026-06",
        "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
        "exactThreeRows": True,
        "ids": STRATEGY_IDS,
        "enabled": [True, True, True],
    }

    initial = result["initial"]
    assert initial["cards"] == STRATEGY_IDS
    assert initial["selectedCards"] == []
    assert initial["pressedCards"] == []
    assert initial["selectedSummary"] == {
        "ok": False,
        "code": "strategy_not_selected",
        "summary": None,
    }
    assert initial["mode"] == ""
    assert initial["dryRunSelected"] is False
    assert initial["originalModePreserved"] is True
    assert initial["modelAdvisorHidden"] is False
    assert initial["fieldsetHidden"] is True
    assert initial["rootFits"] is True

    disabled = result["disabledAttempt"]
    assert disabled["disabledCount"] == 3
    assert disabled["selectedCards"] == []
    assert disabled["pressedCards"] == []
    assert disabled["summary"] == {
        "ok": False,
        "code": "strategy_not_selected",
        "summary": None,
    }
    assert disabled["mode"] == ""

    snapshots = {snapshot["id"]: snapshot for snapshot in result["strategySnapshots"]}
    assert list(snapshots) == STRATEGY_IDS
    expected = {
        "viral_avatar_ugc": {
            "roles": ["source_video", "avatar_image", "product_image"],
            "active": ["avatar_image"],
            "rights": [*COMMON_RIGHTS, "avatar_likeness_consent_confirmed"],
            "duration": "15",
        },
        "viral_product_swap": {
            "roles": [
                "source_video",
                "original_product_image",
                "new_product_image",
            ],
            "active": ["original_product_image"],
            "rights": COMMON_RIGHTS,
            "duration": "10",
        },
        "viral_rebuild": {
            "roles": ["source_video", "product_image", "style_image"],
            "active": [],
            "rights": COMMON_RIGHTS,
            "duration": "10",
        },
    }
    for strategy_id, contract in expected.items():
        snapshot = snapshots[strategy_id]
        assert snapshot["summaryId"] == strategy_id
        assert snapshot["selectedCards"] == [strategy_id]
        assert snapshot["pressedCards"] == [strategy_id]
        assert [item["role"] for item in snapshot["summaryRoles"]] == contract["roles"]
        assert [item["role"] for item in snapshot["activeRoleFields"]] == contract[
            "active"
        ]
        assert all(item["required"] for item in snapshot["activeRoleFields"])
        assert not any(item["disabled"] for item in snapshot["activeRoleFields"])
        assert not any(item["value"] for item in snapshot["activeRoleFields"])
        assert snapshot["summaryRights"] == contract["rights"]
        assert [item["id"] for item in snapshot["rights"]] == contract["rights"]
        assert all(item["required"] for item in snapshot["rights"])
        assert not any(item["checked"] for item in snapshot["rights"])
        assert snapshot["fieldsetOpen"] is True
        assert snapshot["fieldsetRendered"] is True
        assert snapshot["outputOpen"] is True
        assert snapshot["audioValue"] == ""
        assert snapshot["audioRequired"] is True
        assert snapshot["durationValue"] == contract["duration"]
        assert snapshot["productMediaIds"] == [PRODUCT_MEDIA_ID]
        assert snapshot["modelAdvisorHidden"] is False
        assert snapshot["modelAdvisorMode"] == "true"
        assert snapshot["modelAdvisorCards"] >= 3
        assert snapshot["recommendedModelCards"] >= 1
        assert snapshot["actionableModelCards"] == 0
        assert snapshot["recommendationApplyDisabled"] is True
        assert snapshot["nativeModeHidden"] is True
        assert snapshot["nativeModeDisabled"] is True
        assert snapshot["nativeModeRequired"] is False
        assert snapshot["validatedSelection"] is None

    gate = result["attestationGate"]
    assert gate["beforeFinalAttestation"] is None
    assert gate["exactTenSelectionCount"] == 10
    assert gate["sourcePickerSelectedCount"] == 10
    assert gate["mechanicsEditorCount"] == 10
    assert gate["exactTenSourceOrder"] == SOURCE_MEDIA_IDS
    assert gate["afterFinalAttestation"]["strategy_id"] == "viral_rebuild"
    assert gate["afterFinalAttestation"]["audio"] is False
    assert gate["nativeFormValid"] is True
    assert [item["role"] for item in gate["afterFinalAttestation"]["assets"]] == [
        "source_video",
        "product_image",
    ]
    assert all(gate["afterFinalAttestation"]["attestations"].values())

    switching = result["switchingInvalidation"]
    assert switching == {
        "selectedCards": ["viral_avatar_ugc"],
        "paymentUnchecked": True,
        "preflightKeyCleared": True,
        "audioBlank": True,
        "rightsUnchecked": True,
        "validatedSelection": None,
    }

    assert result["catalogCalls"] == 1
    assert result["assetCandidateCalls"] == 1
    assert result["nonCatalogApiCalls"] == 0
    assert result["preflightClicks"] == 0
    assert result["submitCalls"] == 0
    assert result["browserErrors"] == []
    assert result["touchTargetCount"] >= 25
    assert result["minimumTouchTarget"] >= 44
    assert result["geometryChecks"]
    assert all(result["geometryChecks"])
