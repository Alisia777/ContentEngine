from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "web/app/generation-provider-readiness.js"
MODULE = MODULE_PATH.read_text(encoding="utf-8")


def _run_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the readiness v3 contract")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(MODULE, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
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


def test_v3_module_has_no_browser_pricing_or_fixed_model_allowlist() -> None:
    assert "generation-provider-readiness-receipt-v3" in MODULE
    assert "estimated_cost_minor" in MODULE
    assert "spend_confirmation" in MODULE
    assert "automatic_generation" in MODULE
    assert "automatic_spend" in MODULE
    assert "generationCredits" not in MODULE
    for model in (
        "gen4_turbo",
        "seedance2_fast",
        "seedream5_lite",
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
        "veo-3.1-lite-generate-preview",
    ):
        assert model not in MODULE


def test_runway_receipt_requires_exact_identity_versions_and_human_gate() -> None:
    result = _run_module(
        r'''
const nowMs = Date.parse("2026-08-13T12:05:00.000Z");
const receipt = {
  version: "generation-provider-readiness-receipt-v3",
  receipt_id: "fa000000-0000-4000-8000-000000000001",
  receipt_hash: "a".repeat(64),
  organization_id: "fa000000-0000-4000-8000-000000000002",
  checked_by: "fa000000-0000-4000-8000-000000000003",
  provider: "runway",
  model: "gen4.5",
  input_mode: "image",
  duration_seconds: 5,
  format: "9:16",
  resolution: "720p",
  audio: false,
  last_frame: false,
  ready: true,
  estimated_cost_minor: 60,
  estimated_credits: 60,
  credential_configured: true,
  balance_sufficient: true,
  model_available: true,
  daily_quota_available: true,
  failure_code: null,
  catalog_version: "2026-08-13.v1",
  pricing_version: "runway-credits-2026-08-13.v1",
  learning_gate_version: "2026-07-29.v8",
  checked_at: "2026-08-13T12:00:00.000Z",
  expires_at: "2026-08-13T12:15:00.000Z",
  status: "ready",
  fresh: true,
  spend_confirmation: "RUNWAY_GEN4_5_5S_720P_SILENT_USD_0.60",
  automatic_generation: false,
  automatic_spend: false,
};
const options = {
  nowMs,
  organizationId: receipt.organization_id,
  actorId: receipt.checked_by,
  gateVersion: receipt.learning_gate_version,
  catalogVersion: receipt.catalog_version,
  pricingVersion: receipt.pricing_version,
  expectedSelection: {
    provider: "runway",
    model: "gen4.5",
    inputMode: "image",
    durationSeconds: 5,
    ratio: "9:16",
    resolution: "720p",
    audio: false,
    lastFrame: false,
  },
};
return {
  valid: subject.normalizeGenerationProviderPreflight(receipt, options),
  wrongModel: subject.normalizeGenerationProviderPreflight(
    receipt,
    { ...options, expectedSelection: { ...options.expectedSelection, model: "veo3.1_fast" } },
  ),
  wrongActor: subject.normalizeGenerationProviderPreflight(
    receipt,
    { ...options, actorId: "fa000000-0000-4000-8000-000000000004" },
  ),
  stale: subject.normalizeGenerationProviderPreflight(
    { ...receipt, expires_at: "2026-08-13T12:05:00.000Z" },
    options,
  ),
  automatic: subject.normalizeGenerationProviderPreflight(
    { ...receipt, automatic_spend: true },
    options,
  ),
  extra: subject.normalizeGenerationProviderPreflight(
    { ...receipt, raw_response: "forbidden" },
    options,
  ),
};
'''
    )
    assert result["valid"]["provider"] == "runway"
    assert result["valid"]["model"] == "gen4.5"
    assert result["valid"]["estimated_cost_minor"] == 60
    assert result["valid"]["spend_confirmation"].endswith("USD_0.60")
    assert result["wrongModel"] is None
    assert result["wrongActor"] is None
    assert result["stale"] is None
    assert result["automatic"] is None
    assert result["extra"] is None


def test_google_receipt_is_exact_and_never_invents_runway_credits() -> None:
    result = _run_module(
        r'''
const receipt = {
  version: "generation-provider-readiness-receipt-v3",
  receipt_id: "fa000000-0000-4000-8000-000000000011",
  receipt_hash: "b".repeat(64),
  organization_id: "fa000000-0000-4000-8000-000000000012",
  checked_by: "fa000000-0000-4000-8000-000000000013",
  provider: "google",
  model: "veo-3.1-lite-generate-preview",
  input_mode: "image",
  duration_seconds: 8,
  format: "16:9",
  resolution: "1080p",
  audio: true,
  last_frame: true,
  ready: true,
  estimated_cost_minor: 120,
  estimated_credits: null,
  credential_configured: true,
  balance_sufficient: null,
  model_available: true,
  daily_quota_available: null,
  failure_code: null,
  catalog_version: "2026-08-13.v1",
  pricing_version: "google-veo-2026-08-13.v1",
  learning_gate_version: "2026-07-29.v8",
  checked_at: "2026-08-13T12:00:00.000Z",
  expires_at: "2026-08-13T12:15:00.000Z",
  status: "ready",
  fresh: true,
  spend_confirmation: "GOOGLE_VEO3_1_LITE_8S_1080P_AUDIO_USD_1.20",
  automatic_generation: false,
  automatic_spend: false,
};
const valid = subject.normalizeGenerationProviderPreflight(receipt, {
  nowMs: Date.parse("2026-08-13T12:05:00.000Z"),
  organizationId: receipt.organization_id,
  actorId: receipt.checked_by,
  gateVersion: receipt.learning_gate_version,
  catalogVersion: receipt.catalog_version,
  pricingVersion: receipt.pricing_version,
  expectedSelection: {
    provider: receipt.provider,
    model: receipt.model,
    inputMode: receipt.input_mode,
    durationSeconds: receipt.duration_seconds,
    ratio: receipt.format,
    resolution: receipt.resolution,
    audio: receipt.audio,
    lastFrame: receipt.last_frame,
  },
});
return {
  valid,
  fakeCredits: subject.normalizeGenerationProviderPreflight(
    { ...receipt, estimated_credits: 120 },
    { nowMs: Date.parse("2026-08-13T12:05:00.000Z") },
  ),
  duplicateCount: subject.generationProviderReadinessPreflights(
    { provider_readiness: [receipt, { ...receipt }] },
    { nowMs: Date.parse("2026-08-13T12:05:00.000Z") },
  ).length,
};
'''
    )
    assert result["valid"]["provider"] == "google"
    assert result["valid"]["estimated_credits"] is None
    assert result["fakeCredits"] is None
    assert result["duplicateCount"] == 0
