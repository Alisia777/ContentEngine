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
    assert 'from "./generation-autopilot.js?v=20260727.7"' in APP
    assert "chooseInitialGenerationMedia(exactMedia" in APP
    assert (
        "generationMediaOptionMarkup(item, defaultIsReal, automaticMediaId)"
        in APP
    )
    assert "Единственный проверенный исходник выбран автоматически" in APP
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
    assert './app.js?v=20260728.11' in INDEX


def test_rejected_learning_policy_prepares_fallback_without_provider_contact() -> None:
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
        "form.dataset.autoGenerationPreflightModel = candidate.sku.model",
        "syncAutomaticGenerationBrief(form, { force: true, identity })",
        "state.generationLearning",
        "learning.recovery = {",
        "persistGenerationFormDraft(form)",
        "Проверки Runway и списания не было",
    ):
        assert token in fallback
    assert fallback.count(
        "form.elements.real_spend_confirmation.checked = false"
    ) >= 2
    for forbidden in (
        "realGenerationPreflight",
        "runGenerationPreflight",
        "startRealGeneration",
        "submitRealGeneration",
    ):
        assert forbidden not in fallback
    assert "?.generationAllowed === false" in loader
    assert "await prepareGenerationLearningFallback(" in loader
    assert "Модель заменена автоматически" in APP
    assert "Runway не вызывался, списания не было" in APP


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
    assert "после трёх безопасных попыток" in APP
    assert "сам повторит бесплатную проверку" in APP
