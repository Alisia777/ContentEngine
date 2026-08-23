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
STRATEGY_LABELS = [
    "Добавить ведущего, комментирующего ролик",
    "Заменить товар в исходном ролике",
    "Создать новый ролик по механике референса",
]
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

            def evaluate_value(
                expression: str, *, await_promise: bool = False
            ) -> object:
                evaluated = cdp(
                    "Runtime.evaluate",
                    {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": await_promise,
                    },
                )
                protocol_result = evaluated.get("result", {})
                assert "exceptionDetails" not in protocol_result, evaluated
                return protocol_result.get("result", {}).get("value")

            driver = "window.__generationStrategyTrustedPointerDriver"

            def prepare_pointer(kind: str, value: str = "") -> dict[str, object]:
                prepared = evaluate_value(
                    f"{driver}.preparePointer({json.dumps(kind)}, {json.dumps(value)})",
                    await_promise=True,
                )
                assert isinstance(prepared, dict), prepared
                return prepared

            def pointer_down(prepared: dict[str, object]) -> bool:
                if not prepared.get("ok") or not prepared.get("rendered"):
                    return False
                x = float(prepared["x"])
                y = float(prepared["y"])
                cdp(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mouseMoved",
                        "x": x,
                        "y": y,
                        "button": "none",
                        "buttons": 0,
                        "pointerType": "mouse",
                    },
                )
                cdp(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mousePressed",
                        "x": x,
                        "y": y,
                        "button": "left",
                        "buttons": 1,
                        "clickCount": 1,
                        "pointerType": "mouse",
                    },
                )
                return True

            def pointer_up(prepared: dict[str, object]) -> None:
                cdp(
                    "Input.dispatchMouseEvent",
                    {
                        "type": "mouseReleased",
                        "x": float(prepared["x"]),
                        "y": float(prepared["y"]),
                        "button": "left",
                        "buttons": 0,
                        "clickCount": 1,
                        "pointerType": "mouse",
                    },
                )

            def trusted_click(
                kind: str,
                value: str = "",
                *,
                churn_mounts: int = 0,
            ) -> tuple[dict[str, object], bool, dict[str, object] | None]:
                prepared = prepare_pointer(kind, value)
                dispatched = pointer_down(prepared)
                identity = None
                if churn_mounts:
                    identity_value = evaluate_value(
                        f"{driver}.churnMounts({churn_mounts})",
                        await_promise=True,
                    )
                    assert isinstance(identity_value, dict), identity_value
                    identity = identity_value
                if dispatched:
                    pointer_up(prepared)
                evaluate_value(f"{driver}.settle()", await_promise=True)
                return prepared, dispatched, identity

            clone_info = evaluate_value(
                f"{driver}.cloneAndRemount()", await_promise=True
            )
            assert isinstance(clone_info, dict), clone_info

            mode_step = evaluate_value(
                f'{driver}.goToStep("mode")', await_promise=True
            )
            strategy_prepared, strategy_dispatched, strategy_stability = trusted_click(
                "strategy", "viral_product_swap", churn_mounts=25
            )
            strategy_state = evaluate_value(f"{driver}.state()")
            brief_limit_transition = evaluate_value(
                f"{driver}.briefLimitTransition()", await_promise=True
            )

            media_step = evaluate_value(
                f'{driver}.goToStep("media")', await_promise=True
            )
            checkbox_prepared, checkbox_dispatched, checkbox_stability = trusted_click(
                "attestation", churn_mounts=25
            )
            checkbox_state = evaluate_value(f"{driver}.state()")
            remembered_attestation = evaluate_value(
                f"{driver}.rememberCheckedAttestation()"
            )

            mode_step_again = evaluate_value(
                f'{driver}.goToStep("mode")', await_promise=True
            )
            same_prepared, same_dispatched, _ = trusted_click(
                "strategy", "viral_product_swap"
            )
            same_strategy_state = evaluate_value(f"{driver}.state()")
            attestation_persistence = evaluate_value(
                f"{driver}.attestationPersistence()"
            )

            legacy_before_model = evaluate_value(f"{driver}.seedLegacyIdentity()")
            model_prepared, model_dispatched, model_stability = trusted_click(
                "model", churn_mounts=25
            )
            model_state = evaluate_value(f"{driver}.state()")

            switch_prepared, switch_dispatched, _ = trusted_click(
                "strategy", "viral_rebuild"
            )
            switch_state = evaluate_value(f"{driver}.state()")
            strategy_reset = evaluate_value(f"{driver}.strategyReset()")
            avatar_prepared, avatar_dispatched, _ = trusted_click(
                "strategy", "viral_avatar_ugc"
            )
            avatar_state = evaluate_value(f"{driver}.state()")

            consent_media_step = evaluate_value(
                f'{driver}.goToStep("media")', await_promise=True
            )
            source_right_prepared, source_right_dispatched, _ = trusted_click(
                "attestation"
            )
            before_source_change = evaluate_value(f"{driver}.state()")
            source_prepared, source_dispatched, _ = trusted_click("source")
            after_source_change = evaluate_value(f"{driver}.state()")

            asset_right_prepared, asset_right_dispatched, _ = trusted_click(
                "attestation"
            )
            before_asset_change = evaluate_value(f"{driver}.state()")
            product_media_prepared, product_media_dispatched, _ = trusted_click(
                "product_media"
            )
            after_asset_change = evaluate_value(f"{driver}.state()")
            observer_loop = evaluate_value(
                f"{driver}.observerLoopProbe()", await_promise=True
            )
            finish = evaluate_value(f"{driver}.finish()")

            trusted_pointer_flow = {
                "clone": clone_info,
                "modeStep": mode_step,
                "strategy": {
                    "prepared": strategy_prepared,
                    "dispatched": strategy_dispatched,
                    "stability": strategy_stability,
                    "state": strategy_state,
                },
                "briefLimitTransition": brief_limit_transition,
                "mediaStep": media_step,
                "checkbox": {
                    "prepared": checkbox_prepared,
                    "dispatched": checkbox_dispatched,
                    "stability": checkbox_stability,
                    "state": checkbox_state,
                    "remembered": remembered_attestation,
                },
                "modeStepAgain": mode_step_again,
                "sameStrategy": {
                    "prepared": same_prepared,
                    "dispatched": same_dispatched,
                    "state": same_strategy_state,
                    "attestation": attestation_persistence,
                },
                "model": {
                    "legacyBefore": legacy_before_model,
                    "prepared": model_prepared,
                    "dispatched": model_dispatched,
                    "stability": model_stability,
                    "state": model_state,
                },
                "switchStrategy": {
                    "prepared": switch_prepared,
                    "dispatched": switch_dispatched,
                    "state": switch_state,
                    "reset": strategy_reset,
                },
                "thirdStrategy": {
                    "prepared": avatar_prepared,
                    "dispatched": avatar_dispatched,
                    "state": avatar_state,
                },
                "consentMediaStep": consent_media_step,
                "sourceConsentBoundary": {
                    "rightPrepared": source_right_prepared,
                    "rightDispatched": source_right_dispatched,
                    "beforeChange": before_source_change,
                    "sourcePrepared": source_prepared,
                    "sourceDispatched": source_dispatched,
                    "afterChange": after_source_change,
                },
                "assetConsentBoundary": {
                    "rightPrepared": asset_right_prepared,
                    "rightDispatched": asset_right_dispatched,
                    "beforeChange": before_asset_change,
                    "productMediaPrepared": product_media_prepared,
                    "productMediaDispatched": product_media_dispatched,
                    "afterChange": after_asset_change,
                },
                "observerLoop": observer_loop,
                "finish": finish,
            }

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
            result = evaluated["result"]["result"]["value"]
            result["trustedPointerFlow"] = trusted_pointer_flow
            return result
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
        'from "./generation-strategy-view.js?v=20260823.copy-engines.48"' in SUBJECT
    )
    assert (
        'from "./generation-strategy-assets.js?v=20260823.copy-engines.48"' in SUBJECT
    )
    assert "createGenerationStrategyViewState" in SUBJECT
    assert "reduceGenerationStrategyViewState" in SUBJECT
    assert "GENERATION_STRATEGY_SELECT_ACTION" in SUBJECT
    assert "generationStrategySelection" in SUBJECT
    assert "normalizeGenerationStrategyAssetCandidates" in SUBJECT
    assert "generationStrategyAssetEligibility" in SUBJECT
    assert "generationStrategyAssetCandidates" in SUBJECT
    assert "generationStrategyCatalog" in SUBJECT
    assert "async function loadStrategyCatalog(form)" in SUBJECT
    assert 'runtime.strategyCatalogStatus === "loading"' in SUBJECT
    assert 'runtime.catalogStatus === "loading"' in SUBJECT
    assert 'runtime.strategyAssetStatus === "loading"' in SUBJECT
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
    assert "generationModelCatalog: modelCatalogApi" in HARNESS_SOURCE
    assert "generationStrategyCatalog: strategyCatalogApi" in HARNESS_SOURCE
    assert 'throw new Error("fixture_model_catalog_unavailable")' in HARNESS_SOURCE
    assert "remount < 25" in HARNESS_SOURCE
    assert "generationStrategyAssetCandidates: assetCandidatesApi" in HARNESS_SOURCE
    assert HARNESS_SOURCE.count('id="mock-batch-form"') == 1
    assert "requestSubmit" not in HARNESS_SOURCE
    assert '.click();\n        await settle();' in HARNESS_SOURCE
    assert "cloneNode(true)" in HARNESS_SOURCE
    assert "__generationStrategyTrustedPointerDriver" in HARNESS_SOURCE
    assert 'clone.addEventListener("pointerdown"' in HARNESS_SOURCE
    assert "new MutationObserver" in HARNESS_SOURCE
    assert "observerLoopProbe" in HARNESS_SOURCE
    assert "guided.mount();" in HARNESS_SOURCE


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
    assert initial["labels"] == STRATEGY_LABELS
    assert initial["enabled"] == ["true", "true", "true"]
    assert initial["buttonCount"] == 3
    assert initial["enabledButtonCount"] == 3
    assert initial["catalogStatus"] == "ready"
    assert initial["invalidCatalogCount"] == 0
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
    assert initial["modelAdvisorStatus"] == "error"
    assert initial["modelAdvisorCards"] == 0
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
            # «Дуэт» 22.08.2026: РОВНО ОДИН ассет — комментируемый ролик.
            # Ведущего задаёт запись в библиотеке проекта, а не фотография:
            # личность закреплена у провайдера идентификатором, и в теле
            # запроса медиа нет вовсе. Роль avatar_image была наследством
            # прочтения «замена человека в кадре», которое владелец отменил.
            "roles": ["source_video"],
            "active": [],
            "rights": [*COMMON_RIGHTS, "avatar_likeness_consent_confirmed"],
            # Правка видео идёт от исходника, поэтому умолчание такое же, как у
            # «Копии», — десять секунд вместо прежних пятнадцати.
            "duration": "10",
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
        # 23.08.2026: при выбранной стратегии старый каталог моделей (Runway
        # «как совет») скрыт — движок выбирается в каскаде реестра маршрутов
        # панели «Создания». Карточки остаются в DOM, но человеку не видны.
        assert snapshot["modelAdvisorHidden"] is True
        assert snapshot["modelAdvisorMode"] == "true"
        assert snapshot["modelAdvisorCards"] >= 3
        assert snapshot["recommendedModelCards"] >= 1
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

    trusted = result["trustedPointerFlow"]
    assert trusted["clone"] == {
        "formWasReplaced": True,
        "originalDisconnected": True,
        "staleBoundBeforeMount": "true",
        "boundAfterMount": "true",
        "selectedStrategy": "viral_avatar_ugc",
    }
    assert trusted["modeStep"] == {"moved": True, "step": "mode"}

    strategy_pointer = trusted["strategy"]
    assert strategy_pointer["prepared"]["ok"] is True
    assert strategy_pointer["prepared"]["rendered"] is True
    assert strategy_pointer["prepared"]["disabled"] is False
    assert strategy_pointer["prepared"]["value"] == "viral_product_swap"
    assert strategy_pointer["prepared"]["baselineNodes"] == {
        "strategy": True,
        "model": True,
        "attestation": True,
    }
    assert strategy_pointer["dispatched"] is True
    assert strategy_pointer["stability"] == {
        "pointerSame": True,
        "strategySame": True,
        "modelSame": True,
        "attestationSame": True,
        "pointerConnected": True,
        "strategyConnected": True,
        "modelConnected": True,
        "attestationConnected": True,
    }
    assert strategy_pointer["state"]["selectedStrategy"] == "viral_product_swap"
    assert strategy_pointer["state"]["pressedStrategies"] == [
        "viral_product_swap"
    ]

    brief_limit = trusted["briefLimitTransition"]
    assert brief_limit["ok"] is True
    assert brief_limit["strategyForm"] == "viral_product_swap"
    assert brief_limit["maxLength"] == 800
    assert brief_limit["blocked"] == {
        "length": 801,
        "valid": False,
        "validationMessage": "Сократите инструкцию до 800 знаков для выбранной стратегии.",
    }
    assert brief_limit["recovered"] == {
        "length": 800,
        "valid": True,
        "validationMessage": "",
    }

    assert trusted["mediaStep"] == {"moved": True, "step": "media"}
    checkbox_pointer = trusted["checkbox"]
    assert checkbox_pointer["prepared"]["ok"] is True
    assert checkbox_pointer["prepared"]["rendered"] is True
    assert checkbox_pointer["prepared"]["disabled"] is False
    assert checkbox_pointer["prepared"]["baselineNodes"] == {
        "strategy": True,
        "model": True,
        "attestation": True,
    }
    assert checkbox_pointer["dispatched"] is True
    assert checkbox_pointer["stability"] == {
        "pointerSame": True,
        "strategySame": True,
        "modelSame": True,
        "attestationSame": True,
        "pointerConnected": True,
        "strategyConnected": True,
        "modelConnected": True,
        "attestationConnected": True,
    }
    checked_right_id = checkbox_pointer["prepared"]["value"]
    assert checkbox_pointer["state"]["checkedAttestations"] == [checked_right_id]
    assert checkbox_pointer["remembered"] == {
        "remembered": True,
        "id": checked_right_id,
        "checked": True,
    }

    assert trusted["modeStepAgain"] == {"moved": True, "step": "mode"}
    same_strategy = trusted["sameStrategy"]
    assert same_strategy["prepared"]["ok"] is True
    assert same_strategy["prepared"]["rendered"] is True
    assert same_strategy["prepared"]["disabled"] is False
    assert same_strategy["dispatched"] is True
    assert same_strategy["state"]["selectedStrategy"] == "viral_product_swap"
    assert same_strategy["attestation"]["id"] == checked_right_id
    assert same_strategy["attestation"]["checked"] is True

    model_pointer = trusted["model"]
    assert model_pointer["legacyBefore"] == {
        "mode": "real_seedance",
        "provider": "runway",
        "model": "seedance2_fast",
    }
    assert model_pointer["prepared"]["ok"] is True
    assert model_pointer["prepared"]["rendered"] is True
    assert model_pointer["prepared"]["disabled"] is False
    assert model_pointer["prepared"]["value"] != "runway:seedance2_fast"
    assert model_pointer["prepared"]["baselineNodes"] == {
        "strategy": True,
        "model": True,
        "attestation": True,
    }
    assert model_pointer["dispatched"] is True
    assert model_pointer["stability"] == {
        "pointerSame": True,
        "strategySame": True,
        "modelSame": True,
        "attestationSame": True,
        "pointerConnected": True,
        "strategyConnected": True,
        "modelConnected": True,
        "attestationConnected": True,
    }
    assert model_pointer["state"]["modelAdvisorMode"] == "true"
    assert model_pointer["state"]["enabledModelCount"] == model_pointer["state"][
        "modelCount"
    ]
    assert model_pointer["state"]["modelCount"] >= 3
    assert model_pointer["state"]["checkedModel"] == model_pointer["prepared"][
        "value"
    ]
    assert model_pointer["state"]["checkedModelCardSelected"] is True
    assert model_pointer["state"]["legacy"] == model_pointer["legacyBefore"]
    assert model_pointer["state"]["legacyBlocker"] == ""
    assert model_pointer["state"]["legacyValidationMessage"] == ""

    switch_strategy = trusted["switchStrategy"]
    assert switch_strategy["prepared"]["ok"] is True
    assert switch_strategy["prepared"]["rendered"] is True
    assert switch_strategy["prepared"]["disabled"] is False
    assert switch_strategy["dispatched"] is True
    assert switch_strategy["state"]["selectedStrategy"] == "viral_rebuild"
    assert switch_strategy["state"]["pressedStrategies"] == ["viral_rebuild"]
    assert switch_strategy["reset"]["selectedStrategy"] == "viral_rebuild"
    assert switch_strategy["reset"]["allUnchecked"] is True
    assert switch_strategy["reset"]["attestationCount"] == len(COMMON_RIGHTS)

    third_strategy = trusted["thirdStrategy"]
    assert third_strategy["prepared"]["ok"] is True
    assert third_strategy["prepared"]["rendered"] is True
    assert third_strategy["prepared"]["disabled"] is False
    assert third_strategy["dispatched"] is True
    assert third_strategy["state"]["selectedStrategy"] == "viral_avatar_ugc"
    assert third_strategy["state"]["pressedStrategies"] == ["viral_avatar_ugc"]

    assert trusted["consentMediaStep"] == {"moved": True, "step": "media"}
    source_boundary = trusted["sourceConsentBoundary"]
    assert source_boundary["rightPrepared"]["ok"] is True
    assert source_boundary["rightPrepared"]["rendered"] is True
    assert source_boundary["rightPrepared"]["disabled"] is False
    assert source_boundary["rightDispatched"] is True
    source_right_id = source_boundary["rightPrepared"]["value"]
    assert source_boundary["beforeChange"]["checkedAttestations"] == [
        source_right_id
    ]
    assert source_boundary["beforeChange"]["selectedSourceIds"] == []
    assert source_boundary["sourcePrepared"]["ok"] is True
    assert source_boundary["sourcePrepared"]["rendered"] is True
    assert source_boundary["sourcePrepared"]["disabled"] is False
    assert source_boundary["sourcePrepared"]["value"] in SOURCE_MEDIA_IDS
    assert source_boundary["sourceDispatched"] is True
    assert source_boundary["afterChange"]["selectedSourceIds"] == [
        source_boundary["sourcePrepared"]["value"]
    ]
    assert source_boundary["afterChange"]["checkedAttestations"] == []
    assert source_boundary["afterChange"]["allAttestationsUnchecked"] is True

    asset_boundary = trusted["assetConsentBoundary"]
    assert asset_boundary["rightPrepared"]["ok"] is True
    assert asset_boundary["rightPrepared"]["rendered"] is True
    assert asset_boundary["rightPrepared"]["disabled"] is False
    assert asset_boundary["rightDispatched"] is True
    asset_right_id = asset_boundary["rightPrepared"]["value"]
    assert asset_boundary["beforeChange"]["checkedAttestations"] == [
        asset_right_id
    ]
    assert asset_boundary["beforeChange"]["checkedProductMediaIds"] == [
        PRODUCT_MEDIA_ID
    ]
    assert asset_boundary["productMediaPrepared"]["ok"] is True
    assert asset_boundary["productMediaPrepared"]["rendered"] is True
    assert asset_boundary["productMediaPrepared"]["disabled"] is False
    assert asset_boundary["productMediaPrepared"]["value"] == PRODUCT_MEDIA_ID
    assert asset_boundary["productMediaDispatched"] is True
    assert asset_boundary["afterChange"]["checkedProductMediaIds"] == []
    assert asset_boundary["afterChange"]["checkedAttestations"] == []
    assert asset_boundary["afterChange"]["allAttestationsUnchecked"] is True

    observer_loop = trusted["observerLoop"]
    assert observer_loop["baseline"]["allNodesPresent"] is True
    assert observer_loop["baseline"]["strategyId"] == "viral_avatar_ugc"
    assert observer_loop["baseline"]["modelValue"]
    assert observer_loop["baseline"]["attestationId"] in [
        *COMMON_RIGHTS,
        "avatar_likeness_consent_confirmed",
    ]
    assert 1 <= observer_loop["countAfterSettling"] <= 3
    assert (
        observer_loop["countAfterQuietWindow"]
        == observer_loop["countAfterSettling"]
    )
    assert (
        observer_loop["callbacksAfterQuietWindow"]
        == observer_loop["callbacksAfterSettling"]
    )
    assert (
        observer_loop["scheduledAfterQuietWindow"]
        == observer_loop["scheduledAfterSettling"]
    )
    assert observer_loop["queuedAfterQuietWindow"] is False
    stable_nodes = {
        "strategySame": True,
        "modelSame": True,
        "attestationSame": True,
        "strategyConnected": True,
        "modelConnected": True,
        "attestationConnected": True,
    }
    assert observer_loop["identityAfterSettling"] == stable_nodes
    assert observer_loop["identityAfterQuietWindow"] == stable_nodes

    finish = trusted["finish"]
    pointer_events = finish["trustedPointerEvents"]
    assert pointer_events
    assert all(event["isTrusted"] is True for event in pointer_events)
    click_kinds = [
        event["kind"] for event in pointer_events if event["type"] == "click"
    ]
    assert click_kinds.count("strategy") == 4
    assert click_kinds.count("attestation") == 3
    assert click_kinds.count("model") == 1
    assert click_kinds.count("source") == 1
    assert click_kinds.count("product_media") == 1
    assert [
        event["value"]
        for event in pointer_events
        if event["type"] == "click" and event["kind"] == "strategy"
    ] == [
        "viral_product_swap",
        "viral_product_swap",
        "viral_rebuild",
        "viral_avatar_ugc",
    ]
    assert finish["browserErrors"] == []
    assert finish["nonCatalogApiCalls"] == 0
    assert finish["preflightClicks"] == 0
    assert finish["submitCalls"] == 0

    assert result["modelCatalogCalls"] == 1
    assert result["strategyCatalogCalls"] == 1
    assert result["assetCandidateCalls"] == 1
    assert result["nonCatalogApiCalls"] == 0
    assert result["preflightClicks"] == 0
    assert result["submitCalls"] == 0
    assert result["browserErrors"] == []
    assert result["touchTargetCount"] >= 25
    assert result["minimumTouchTarget"] >= 44
    assert result["geometryChecks"]
    assert all(result["geometryChecks"])
