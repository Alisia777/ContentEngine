from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web/app/generation-autopilot.js"
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation autopilot contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            MODULE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_unique_safe_media_is_selected_without_guessing_between_candidates() -> None:
    media = json.dumps(
        [
            {
                "public_id": "media-ready",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "WB-1",
                "product_name": "Точный товар",
            },
            {
                "public_id": "media-unverified",
                "identity_verified": False,
                "rights_confirmed": True,
                "sku": "WB-2",
                "product_name": "Другой товар",
            },
        ],
        ensure_ascii=False,
    )
    assert _evaluate(
        f"subject.chooseInitialGenerationMedia({media}, {{ real: true }})"
    ) == "media-ready"
    assert _evaluate(
        f"subject.chooseInitialGenerationMedia({media}, {{ real: false }})"
    ) == ""

    two_safe = json.dumps(
        [
            {
                "id": "one",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "WB-1",
                "product_name": "Один",
            },
            {
                "id": "two",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "WB-2",
                "product_name": "Два",
            },
        ],
        ensure_ascii=False,
    )
    assert _evaluate(
        f"subject.chooseInitialGenerationMedia({two_safe}, {{ real: true }})"
    ) == ""


def test_research_handoff_never_auto_selects_media_from_an_old_product() -> None:
    media = json.dumps(
        [
            {
                "public_id": "old-airfryer",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "AIR-425",
                "product_name": "Аэрогриль MILIO",
            },
            {
                "public_id": "lion-mane",
                "identity_verified": True,
                "rights_confirmed": True,
                "sku": "BAD-LION-001",
                "product_name": "Ежовик гребенчатый",
            },
        ],
        ensure_ascii=False,
    )
    expected = (
        '{ real: true, expectedSku: "BAD-LION-001", '
        'expectedProductName: "Ежовик гребенчатый" }'
    )

    assert _evaluate(
        f"subject.chooseInitialGenerationMedia({media}, {expected})"
    ) == "lion-mane"
    assert _evaluate(
        f"subject.chooseInitialGenerationMedia([{media}[0]], {expected})"
    ) == ""
    assert _evaluate(
        "subject.chooseInitialGenerationMedia(" + media
        + ', { real: true, expectedSku: "BAD-LION-001" })'
    ) == ""

    automatic_start = APP.index("function syncGenerationAutomaticMedia(form)")
    automatic_end = APP.index("function syncGenerationDestination(form)", automatic_start)
    automatic = APP[automatic_start:automatic_end]
    assert automatic.index("const checked =") < automatic.index("if (touched) return")
    assert "const checkedMediaId = chooseInitialGenerationMedia" in automatic
    assert "if (checkedMediaId === checked.value) return checked.value" in automatic
    assert "checked.checked = false" in automatic
    assert "...expectedProduct" in automatic


def test_platform_autopilot_uses_content_specific_defaults_and_respects_manual_choice() -> None:
    expression = """
    [
      subject.resolveGenerationPlatform({
        mode: "real_photo",
        currentPlatform: "instagram",
      }),
      subject.resolveGenerationPlatform({
        mode: "real_seedance",
        currentPlatform: "instagram",
      }),
      subject.resolveGenerationPlatform({
        mode: "real_photo",
        currentPlatform: "tiktok",
        automaticPlatform: "tiktok",
      }),
      subject.resolveGenerationPlatform({
        mode: "real_photo",
        currentPlatform: "telegram",
        automaticPlatform: "tiktok",
      }),
      subject.resolveGenerationPlatform({
        mode: "mock",
        currentPlatform: "vk",
        automaticPlatform: "tiktok",
      }),
    ]
    """
    assert _evaluate(expression) == [
        {"value": "wildberries", "preferred": "wildberries", "automatic": True},
        {"value": "tiktok", "preferred": "tiktok", "automatic": True},
        {"value": "wildberries", "preferred": "wildberries", "automatic": True},
        {"value": "telegram", "preferred": "wildberries", "automatic": False},
        {"value": "vk", "preferred": "", "automatic": False},
    ]


def test_real_generation_reference_bundle_requires_one_product_and_primary() -> None:
    expression = """
    (() => {
      const sameProduct = [
        {id: "front", selected: true, paidReady: true, sku: "SKU-1", productName: "Пароварка"},
        {id: "side", selected: true, paidReady: true, sku: "SKU-1", productName: "Пароварка"},
        {id: "detail", selected: true, paidReady: true, sku: "SKU-1", productName: "Пароварка"},
      ];
      return {
        valid: subject.resolveGenerationMediaSelection(sameProduct, {
          real: true,
          primaryMediaId: "side",
        }),
        mixed: subject.resolveGenerationMediaSelection([
          ...sameProduct,
          {id: "other", selected: true, paidReady: true, sku: "SKU-2", productName: "Чайник"},
        ], {real: true}),
        tooMany: subject.resolveGenerationMediaSelection(
          Array.from({length: 6}, (_, index) => ({
            id: `ref-${index}`,
            selected: true,
            paidReady: true,
            sku: "SKU-1",
            productName: "Пароварка",
          })),
          {real: true},
        ),
      };
    })()
    """
    result = _evaluate(expression)
    assert result["valid"]["valid"] is True
    assert result["valid"]["mediaIds"] == ["side", "front", "detail"]
    assert result["mixed"]["code"] == "mixed_product_references"
    assert result["tooMany"]["code"] == "too_many_references"


def test_destination_autopilot_reuses_only_one_unambiguous_safe_history_value() -> None:
    batches = json.dumps(
        [
            {
                "status": "succeeded",
                "parameters": {
                    "platform": "tiktok",
                    "destination_ref": "@exact-account",
                },
            },
            {
                "status": "processing",
                "input": {
                    "platform": "tiktok",
                    "destination_ref": "@exact-account",
                },
            },
            {
                "status": "failed",
                "parameters": {
                    "platform": "tiktok",
                    "destination_ref": "@ignored-failure",
                },
            },
            {
                "status": "succeeded",
                "parameters": {
                    "platform": "wildberries",
                    "destination_ref": "WB-123",
                },
            },
        ],
        ensure_ascii=False,
    )
    result = _evaluate(
        "subject.resolveGenerationDestination({"
        f"batches: {batches}, platform: 'tiktok'"
        "})"
    )
    assert result == {
        "value": "@exact-account",
        "preferred": "@exact-account",
        "automatic": True,
        "candidateCount": 1,
    }


def test_destination_autopilot_never_guesses_and_preserves_manual_override() -> None:
    batches = json.dumps(
        [
            {
                "status": "mock_ready",
                "parameters": {
                    "platform": "vk",
                    "destination_ref": "@first",
                },
            },
            {
                "status": "succeeded",
                "parameters": {
                    "platform": "vk",
                    "destination_ref": "@second",
                },
            },
        ],
        ensure_ascii=False,
    )
    expression = f"""
    [
      subject.resolveGenerationDestination({{
        batches: {batches},
        platform: "vk",
      }}),
      subject.resolveGenerationDestination({{
        batches: {batches},
        platform: "vk",
        currentDestination: "@manual",
        automaticDestination: "@old-auto",
      }}),
      subject.resolveGenerationDestination({{
        batches: {batches},
        platform: "telegram",
        currentDestination: "@old-auto",
        automaticDestination: "@old-auto",
      }}),
    ]
    """
    assert _evaluate(expression) == [
        {
            "value": "",
            "preferred": "",
            "automatic": False,
            "candidateCount": 2,
        },
        {
            "value": "@manual",
            "preferred": "",
            "automatic": False,
            "candidateCount": 2,
        },
        {
            "value": "",
            "preferred": "",
            "automatic": False,
            "candidateCount": 0,
        },
    ]


def test_learning_fallback_preserves_content_kind_before_cost() -> None:
    expression = """
    [
      subject.resolveGenerationLearningFallback({
        currentMode: "real_seedance",
        candidates: [
          {
            mode: "real_photo",
            available: true,
            generationAllowed: true,
            estimatedMinor: 4,
          },
          {
            mode: "real_gen4",
            available: true,
            generationAllowed: true,
            estimatedMinor: 25,
          },
        ],
      }),
      subject.resolveGenerationLearningFallback({
        currentMode: "real_gen4",
        candidates: [
          {
            mode: "real_photo",
            available: true,
            generationAllowed: true,
            estimatedMinor: 4,
          },
          {
            mode: "real_seedance",
            available: true,
            generationAllowed: true,
            estimatedMinor: 232,
          },
        ],
      }),
    ]
    """
    assert _evaluate(expression) == [
        {
            "mode": "real_gen4",
            "reasonCode": "same_content_kind",
            "accepted": False,
            "estimatedMinor": 25,
        },
        {
            "mode": "real_seedance",
            "reasonCode": "same_content_kind",
            "accepted": False,
            "estimatedMinor": 232,
        },
    ]


def test_learning_fallback_prefers_accepted_then_cheaper_safe_modality() -> None:
    expression = """
    [
      subject.resolveGenerationLearningFallback({
        currentMode: "real_photo",
        candidates: [
          {
            mode: "real_gen4",
            available: true,
            generationAllowed: true,
            accepted: false,
            estimatedMinor: 25,
          },
          {
            mode: "real_seedance",
            available: true,
            generationAllowed: true,
            accepted: true,
            estimatedMinor: 232,
          },
        ],
      }),
      subject.resolveGenerationLearningFallback({
        currentMode: "real_photo",
        candidates: [
          {
            mode: "real_gen4",
            available: true,
            generationAllowed: true,
            estimatedMinor: 25,
          },
          {
            mode: "real_seedance",
            available: true,
            generationAllowed: true,
            estimatedMinor: 232,
          },
        ],
      }),
    ]
    """
    assert _evaluate(expression) == [
        {
            "mode": "real_seedance",
            "reasonCode": "safe_modality_fallback",
            "accepted": True,
            "estimatedMinor": 232,
        },
        {
            "mode": "real_gen4",
            "reasonCode": "safe_modality_fallback",
            "accepted": False,
            "estimatedMinor": 25,
        },
    ]


def test_learning_fallback_fails_closed_for_repair_or_unsafe_candidates() -> None:
    expression = """
    [
      subject.resolveGenerationLearningFallback({
        currentMode: "real_seedance",
        repairActive: true,
        candidates: [{
          mode: "real_gen4",
          available: true,
          generationAllowed: true,
          estimatedMinor: 25,
        }],
      }),
      subject.resolveGenerationLearningFallback({
        currentMode: "real_seedance",
        candidates: [
          {
            mode: "real_gen4",
            available: false,
            generationAllowed: true,
            estimatedMinor: 25,
          },
          {
            mode: "real_photo",
            available: true,
            generationAllowed: false,
            estimatedMinor: 4,
          },
        ],
      }),
    ]
    """
    assert _evaluate(expression) == [None, None]


def test_learning_retry_is_bounded_to_two_automatic_retries() -> None:
    expression = """
    [
      subject.generationLearningRetryDelay(0),
      subject.generationLearningRetryDelay(1),
      subject.generationLearningRetryDelay(2),
      subject.generationLearningRetryDelay(3),
      subject.generationLearningRetryDelay(1.5),
      subject.generationLearningRetryDelay("2"),
    ]
    """
    assert _evaluate(expression) == [None, 1000, 3000, None, None, 3000]


def test_preflight_retry_only_recovers_transient_readiness_failures() -> None:
    expression = """
    [
      subject.generationPreflightRetryDelay({
        attempt: 1,
        errorCode: "provider_request_failed",
      }),
      subject.generationPreflightRetryDelay({
        attempt: 2,
        errorCode: "ui_timeout",
      }),
      subject.generationPreflightRetryDelay({
        attempt: 3,
        errorCode: "provider_request_failed",
      }),
      subject.generationPreflightRetryDelay({
        attempt: 1,
        errorCode: "provider_authentication_failed",
      }),
      subject.generationPreflightRetryDelay({
        attempt: 1,
        errorCode: "provider_credits_unavailable",
      }),
      subject.generationPreflightRetryDelay({
        attempt: 1,
        errorCode: "provider_rate_limited",
      }),
      subject.generationPreflightRetryDelay({
        attempt: 1,
        errorCode: "provider_request_rejected",
      }),
    ]
    """
    assert _evaluate(expression) == [
        1500,
        4000,
        None,
        None,
        None,
        None,
        None,
    ]


def test_preflight_cache_reuses_only_fresh_results_and_never_duplicates_loading() -> None:
    expression = """
    [
      subject.generationPreflightDecision({ status: "loading" }, { now: 5000 }),
      subject.generationPreflightDecision(
        { status: "ready", checkedAt: 4000 },
        { now: 5000, readyTtlMs: 2000 }
      ),
      subject.generationPreflightDecision(
        { status: "ready", checkedAt: 3000 },
        { now: 5000, readyTtlMs: 2000 }
      ),
      subject.generationPreflightDecision(
        { status: "error", checkedAt: 4500 },
        { now: 5000, errorCooldownMs: 1000 }
      ),
      subject.generationPreflightDecision(
        { status: "error", checkedAt: 4500 },
        { force: true, now: 5000, errorCooldownMs: 1000 }
      ),
    ]
    """
    assert _evaluate(expression) == [
        "join",
        "reuse_ready",
        "request",
        "reuse_error",
        "request",
    ]


def test_generation_form_wires_autopilot_with_visible_override_and_cache_busting() -> None:
    assert 'from "./generation-autopilot.js?v=20260826.rebuild-clean.11"' in APP
    assert "chooseInitialGenerationMedia(exactMedia" in APP
    assert (
        "generationMediaOptionMarkup(item, defaultIsReal, automaticMediaId)"
        in APP
    )
    assert "Единственный проверенный исходник выбран главным автоматически" in APP
    assert 'name="primary_media_id"' in APP
    assert "resolveGenerationMediaSelection" in APP
    assert "Cold start категории" in APP
    assert "Сигналы других категорий не применяются" not in APP
    assert "сигналы других категорий не применяются" in APP
    learning_key = APP[
        APP.index("function generationLearningKey")
        : APP.index("function generationProductCategoryLabel")
    ]
    assert "product_category" in learning_key
    assert "function syncGenerationAutomaticMedia(form)" in APP
    assert 'generationForm.dataset.generationMediaSelectionTouched = "true"' in APP
    assert "snapshot.generationMediaSelectionTouched" in APP
    assert "autoGenerationBrief: String(form.dataset.autoGenerationBrief" in APP
    assert "form.dataset.autoGenerationBrief = snapshot.autoGenerationBrief" in APP
    assert "resolveGenerationPlatform({" in APP
    assert "delete generationForm.dataset.autoGenerationPlatform" in APP
    assert "resolveGenerationDestination({" in APP
    assert "function syncGenerationDestination(form)" in APP
    assert (
        "autoGenerationDestination: String(form.dataset.autoGenerationDestination"
        in APP
    )
    assert (
        "form.dataset.autoGenerationDestination = snapshot.autoGenerationDestination"
        in APP
    )
    assert "В истории несколько назначений для этой площадки" in APP
    assert "generationPreflightDecision(previous" in APP
    assert "scheduleAutomaticGenerationPreflight(form)" in APP
    assert 'const generationForm = document.querySelector("#mock-batch-form");' in APP
    assert "if (!repairReady) applyContentGenerationHandoffToForm();" in APP
    assert "syncGenerationModeForm(generationForm);" in APP
    assert "syncGenerationFormReadiness(generationForm);" in APP
    assert './app.js?v=20260826.rebuild-clean.11' in INDEX


def test_rejected_learning_policy_only_recommends_fallback_without_mutating_choice() -> None:
    fallback = APP[
        APP.index("async function prepareGenerationLearningFallback("):
        APP.index("async function loadGenerationLearningPolicy(")
    ]
    loader = APP[
        APP.index("async function loadGenerationLearningPolicy("):
        APP.index("async function ensureGenerationLearningPolicy(")
    ]
    for token in (
        "activeGenerationRepairPolicy(form, identity)",
        "normalizeGenerationModelAcceptance(",
        "activeGenerationCampaigns().find",
        "realGenerationSpendAllowed(mode, item.id)",
        "resolveGenerationPlatform({",
        "state.api.generationLearningPolicy({",
        "normalizeGenerationLearningPolicy(rawPolicy)",
        "resolveGenerationLearningFallback({",
        "state.generationLearning",
        "learning.recovery = {",
        "Ваш выбор не изменён; вызова платного провайдера и списания не было",
    ):
        assert token in fallback
    for forbidden in (
        "realGenerationPreflight",
        "runGenerationPreflight",
        "startRealGeneration",
        "submitRealGeneration",
        "modeSelect.value = candidate.mode",
        "platformInput.value = candidate.platform",
        "form.elements.campaign_id.value = candidate.campaign.id",
        "form.elements.real_spend_confirmation.checked = false",
        "persistGenerationFormDraft(form)",
    ):
        assert forbidden not in fallback
    assert "?.generationAllowed === false" in loader
    assert "await prepareGenerationLearningFallback(" in loader
    assert "ИИ рекомендует другой режим" in APP
    assert "вызова платного провайдера и списания не было" in APP


def test_learning_lookup_times_out_and_recovers_without_provider_contact() -> None:
    retry = APP[
        APP.index("function clearGenerationLearningRetry("):
        APP.index("async function prepareGenerationLearningFallback(")
    ]
    loader = APP[
        APP.index("async function loadGenerationLearningPolicy("):
        APP.index("async function ensureGenerationLearningPolicy(")
    ]
    for token in (
        "generationLearningRetryDelay(learning.retryAttempt)",
        "requestEpoch !== state.dataEpoch",
        "requestUserId !== state.user?.id",
        "generationLearningKey(form, identity) !== key",
        "automaticRetry: true",
        "window.clearTimeout(learning.retryTimer)",
        "window.setTimeout(() =>",
    ):
        assert token in retry
    for token in (
        "{ force = false, automaticRetry = false }",
        '["loading", "ready", "error"].includes(learning.status)',
        "continueRetrySeries",
        "learning.retryAttempt += 1",
        "await withUiTimeout(",
        '"generation_learning_policy_timeout"',
        "scheduleGenerationLearningRetry(key)",
        "clearGenerationLearningRetry()",
    ):
        assert token in loader
    for forbidden in (
        "realGenerationPreflight",
        "runGenerationPreflight",
        "startRealGeneration",
        "submitRealGeneration",
    ):
        assert forbidden not in retry
    assert "после трёх попыток" in APP
    assert "сам повторит бесплатную проверку" in APP


def test_paid_submit_recovers_same_generation_form_after_safe_rerender() -> None:
    assert "function generationFormForLearningKey(key, fallback = null)" in APP
    ensure = APP[
        APP.index("async function ensureGenerationLearningPolicy("):
        APP.index("function automaticGenerationBriefCandidate(")
    ]
    submit = APP[
        APP.index("async function submitRealGeneration(form, values, mode)"):
        APP.index("async function submitMockBatch(")
    ]
    assert "const activeForm = generationFormForLearningKey(key, form)" in ensure
    assert "captureGenerationLaunchSnapshot(form, values)" in submit
    assert "restoreGenerationLaunchSnapshot(form, launchSnapshot)" in submit
    assert "await ensureGenerationLearningPolicy(" not in submit
    assert "Learning is advisory" in submit


def test_paid_learning_keeps_selected_identity_while_form_is_busy() -> None:
    selection = APP[
        APP.index("function generationMediaSelectionFromForm("):
        APP.index("function selectedGenerationProductIdentity(")
    ]
    assert 'form.dataset.busy === "true"' in selection
    assert 'input.dataset.wasDisabled === "false"' in selection
    assert "disabled: Boolean(" in selection
    submit = APP[
        APP.index("async function submitRealGeneration(form, values, mode)"):
        APP.index("async function submitMockBatch(")
    ]
    assert "captureGenerationLaunchSnapshot(form, values)" in submit
    assert "restoreGenerationLaunchSnapshot(form, launchSnapshot)" in submit
    assert "await ensureGenerationLearningPolicy(" not in submit


def test_generation_advice_is_opt_in_and_never_blocks_submit() -> None:
    safety = APP[
        APP.index("function generationPaidSafetyState(form)"):
        APP.index("function syncGenerationFormReadiness(form)")
    ]
    readiness = APP[
        APP.index("function syncGenerationFormReadiness(form)"):
        APP.index("function applyContentGenerationHandoffToForm(")
    ]
    active_policy = APP[
        APP.index("function activeGenerationLearningPolicy("):
        APP.index("function generationCreativeAngleLabel(")
    ]
    assert 'state.generationLearning.enabledKey !== key' in active_policy
    assert 'stateName = "advice"' in safety
    assert "learningGenerationAllowed\n      &&" not in safety
    assert "const blocker = !readiness.ready" in readiness
    assert "Этот вариант остановлен проверкой качества" not in readiness
    assert "Применить совет" in APP
    assert "Не использовать совет" in APP
