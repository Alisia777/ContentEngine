from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "supabase/functions/_shared/generation-model-catalog.js"
SOURCE = MODULE.read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation model catalog contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(SOURCE, encoding="utf-8")
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


def test_catalog_is_pure_unique_versioned_and_contains_exact_scope() -> None:
    for forbidden in (
        "Deno.env",
        "process.env",
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "fetch(",
        "XMLHttpRequest",
    ):
        assert forbidden not in SOURCE

    result = _evaluate(
        """
        (() => {
          const models = subject.GENERATION_MODEL_CATALOG;
          return {
            version: subject.GENERATION_MODEL_CATALOG_VERSION,
            count: models.length,
            keys: models.map((entry) => `${entry.provider}:${entry.model}`),
            frozen: Object.isFrozen(models) && models.every((entry) => Object.isFrozen(entry)),
          };
        })()
        """
    )
    assert result["version"] == "2026-08-13.v1"
    assert result["count"] == 10
    assert len(result["keys"]) == len(set(result["keys"]))
    assert result["keys"] == [
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
    ]
    assert result["frozen"] is True


def test_public_projection_is_allowlisted_and_flags_are_disabled_by_default() -> None:
    result = _evaluate(
        """
        (() => {
          const base = subject.publicGenerationModelCatalog();
          const enabled = base.models.filter((entry) => entry.enabled).map((entry) => entry.model);
          const disabled = base.models.filter((entry) => !entry.enabled).map((entry) => entry.model);
          const flagged = subject.publicGenerationModelCatalog({featureFlags: {
            [subject.GENERATION_MODEL_FEATURE_FLAGS.runwayPremium]: true,
            [subject.GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true,
          }});
          return {
            version: base.version,
            enabled,
            disabled,
            flaggedEnabled: flagged.models.filter((entry) => entry.enabled).map((entry) => entry.model),
            leaksServer: base.models.some((entry) => Object.hasOwn(entry, "server")),
            leaksFlag: base.models.some((entry) => Object.hasOwn(entry, "featureFlag")),
            allSafe: base.models.every((entry) =>
              !Object.keys(entry).some((key) => /secret|token|authorization|endpoint/i.test(key))
            ),
          };
        })()
        """
    )
    assert result["version"] == "2026-08-13.v1"
    assert result["enabled"] == [
        "seedream5_lite",
        "gen4_turbo",
        "seedance2_fast",
        "gen4.5",
        "seedance2_mini",
        "veo3.1_fast",
        "gemini_omni_flash",
    ]
    assert result["disabled"] == [
        "veo3.1",
        "seedance2",
        "veo-3.1-lite-generate-preview",
    ]
    assert set(result["flaggedEnabled"]) == set(result["enabled"] + result["disabled"])
    assert result["leaksServer"] is False
    assert result["leaksFlag"] is False
    assert result["allSafe"] is True


def test_capability_contract_blocks_fake_common_payloads() -> None:
    result = _evaluate(
        """
        (() => {
          const gen4 = subject.generationModelCatalogEntry("runway", "gen4_turbo");
          const seedance = subject.generationModelCatalogEntry("runway", "seedance2_fast");
          const omni = subject.generationModelCatalogEntry("runway", "gemini_omni_flash");
          const base = {durationSeconds: 5, ratio: "9:16", resolution: "720p"};
          return {
            gen4Text: subject.validateGenerationModelSelection(gen4, {...base, inputMode: "text"}),
            gen4Audio: subject.validateGenerationModelSelection(gen4, {...base, inputMode: "image", audio: true, firstFrame: true}),
            gen4Image: subject.validateGenerationModelSelection(gen4, {...base, inputMode: "image", firstFrame: true}),
            seedanceVideo: subject.validateGenerationModelSelection(seedance, {
              ...base,
              inputMode: "video",
              audio: true,
              spokenDialogue: true,
              referenceVideo: true,
              referenceImageCount: 5,
            }),
            seedanceImageTooMany: subject.validateGenerationModelSelection(seedance, {
              ...base,
              inputMode: "image",
              referenceImageCount: 10,
            }),
            seedanceTextReferenceVideo: subject.validateGenerationModelSelection(seedance, {
              ...base, inputMode: "text", referenceVideo: true,
            }),
            omni1080: subject.validateGenerationModelSelection(omni, {...base, inputMode: "text", resolution: "1080p"}),
          };
        })()
        """
    )
    assert result["gen4Text"]["code"] == "input_mode_unsupported"
    assert result["gen4Audio"]["code"] == "audio_unsupported"
    assert result["gen4Image"]["ok"] is True
    assert result["seedanceVideo"]["ok"] is True
    assert result["seedanceImageTooMany"]["code"] == "reference_image_count_unsupported"
    assert result["seedanceTextReferenceVideo"]["ok"] is True
    assert result["omni1080"]["code"] == "resolution_unsupported"


def test_server_cost_estimates_use_one_versioned_formula_per_entry() -> None:
    result = _evaluate(
        """
        (() => {
          const get = (provider, model) => subject.generationModelCatalogEntry(provider, model);
          const flags = {
            [subject.GENERATION_MODEL_FEATURE_FLAGS.runwayPremium]: true,
            [subject.GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true,
          };
          return {
            photo: subject.estimateGenerationModelCostMinor(get("runway", "seedream5_lite"), {
              inputMode: "image", durationSeconds: 0, ratio: "1:1", resolution: "2K", referenceImageCount: 1,
            }),
            gen4: subject.estimateGenerationModelCostMinor(get("runway", "gen4_turbo"), {
              inputMode: "image", durationSeconds: 8, ratio: "9:16", resolution: "720p", firstFrame: true,
            }),
            miniMinimum: subject.estimateGenerationModelCostMinor(get("runway", "seedance2_mini"), {
              inputMode: "text", durationSeconds: 4, ratio: "9:16", resolution: "720p", audio: true,
            }),
            veoFastAudio: subject.estimateGenerationModelCostMinor(get("runway", "veo3.1_fast"), {
              inputMode: "image", durationSeconds: 8, ratio: "9:16", resolution: "720p", audio: true, firstFrame: true,
            }),
            veoFastSilent: subject.estimateGenerationModelCostMinor(get("runway", "veo3.1_fast"), {
              inputMode: "text", durationSeconds: 8, ratio: "16:9", resolution: "720p", audio: false,
            }),
            omniImage: subject.estimateGenerationModelCostMinor(get("runway", "gemini_omni_flash"), {
              inputMode: "image", durationSeconds: 5, ratio: "9:16", resolution: "720p", firstFrame: true,
            }),
            omniVideo: subject.estimateGenerationModelCostMinor(get("runway", "gemini_omni_flash"), {
              inputMode: "video", durationSeconds: 5, ratio: "9:16", resolution: "720p",
              referenceVideo: true, referenceImageCount: 2, inputVideoDurationSeconds: 7,
            }),
            seedance4k: subject.estimateGenerationModelCostMinor(get("runway", "seedance2"), {
              inputMode: "text", durationSeconds: 4, ratio: "9:16", resolution: "4K", audio: true,
            }, {featureFlags: flags}),
            google720: subject.estimateGenerationModelCostMinor(get("google", "veo-3.1-lite-generate-preview"), {
              inputMode: "text", durationSeconds: 8, ratio: "9:16", resolution: "720p", audio: true,
            }, {featureFlags: flags}),
            google1080: subject.estimateGenerationModelCostMinor(get("google", "veo-3.1-lite-generate-preview"), {
              inputMode: "image", durationSeconds: 8, ratio: "16:9", resolution: "1080p", audio: true, firstFrame: true,
            }, {featureFlags: flags}),
          };
        })()
        """
    )
    assert result["photo"]["estimatedCostMinor"] == 4
    assert result["gen4"]["estimatedCostMinor"] == 40
    assert result["miniMinimum"]["estimatedCostMinor"] == 64
    assert result["veoFastAudio"]["estimatedCostMinor"] == 120
    assert result["veoFastSilent"]["estimatedCostMinor"] == 80
    assert result["omniImage"]["estimatedCostMinor"] == 51
    assert result["omniVideo"]["estimatedCostMinor"] == 79
    assert result["seedance4k"]["estimatedCostMinor"] == 600
    assert result["google720"]["estimatedCostMinor"] == 40
    assert result["google1080"]["estimatedCostMinor"] == 64
    assert result["photo"]["pricingVersion"] == "runway-credits-2026-08-13.v1"
    assert result["google720"]["pricingVersion"] == "google-veo-2026-08-13.v1"


def test_disabled_models_cannot_be_costed_without_exact_feature_flag() -> None:
    result = _evaluate(
        """
        (() => {
          const premium = subject.generationModelCatalogEntry("runway", "veo3.1");
          const google = subject.generationModelCatalogEntry("google", "veo-3.1-lite-generate-preview");
          return {
            premium: subject.estimateGenerationModelCostMinor(premium, {
              inputMode: "text", durationSeconds: 8, ratio: "16:9", resolution: "720p", audio: true,
            }),
            google: subject.estimateGenerationModelCostMinor(google, {
              inputMode: "text", durationSeconds: 8, ratio: "16:9", resolution: "720p", audio: true,
            }),
          };
        })()
        """
    )
    assert result["premium"]["code"] == "model_disabled_by_organization"
    assert result["google"]["code"] == "model_disabled_by_organization"


def test_exact_provider_dimensions_and_public_input_modes_share_one_source() -> None:
    result = _evaluate(
        """
        (() => {
          const seedream = subject.generationModelCatalogEntry("runway", "seedream5_lite");
          const seedance = subject.generationModelCatalogEntry("runway", "seedance2_fast");
          const google = subject.generationModelCatalogEntry("google", "veo-3.1-lite-generate-preview");
          const publicCatalog = subject.publicGenerationModelCatalog({featureFlags: {
            [subject.GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true,
          }});
          return {
            seedream21x9: seedream.server.providerRatios["3K"]["21:9"],
            seedancePortrait: seedance.server.providerRatios["720p"]["9:16"],
            googlePortrait: google.server.providerRatios["1080p"]["9:16"],
            seedancePromptLimit: seedance.promptLimit,
            publicSeedance: publicCatalog.models.find((entry) => entry.model === "seedance2_fast"),
            publicGoogle: publicCatalog.models.find((entry) => entry.provider === "google"),
            google1080Six: subject.validateGenerationModelSelection(google, {
              inputMode: "text", durationSeconds: 6, ratio: "16:9", resolution: "1080p", audio: true,
            }, {featureFlags: {[subject.GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true}}),
            googleLastFrameSix: subject.validateGenerationModelSelection(google, {
              inputMode: "image", durationSeconds: 6, ratio: "16:9", resolution: "720p", audio: true,
              firstFrame: true, lastFrame: true,
            }, {featureFlags: {[subject.GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true}}),
          };
        })()
        """
    )
    assert result["seedream21x9"] == "4704:2016"
    assert result["seedancePortrait"] == "720:1280"
    assert result["googlePortrait"] == "9:16"
    assert result["seedancePromptLimit"] == 3500
    assert result["publicSeedance"]["inputCapabilities"]["text"]["maxReferenceImages"] == 9
    assert result["publicSeedance"]["inputCapabilities"]["image"]["supportsLastFrame"] is True
    assert "server" not in result["publicSeedance"]
    assert result["publicGoogle"]["inputCapabilities"]["image"]["supportsLastFrame"] is True
    assert result["publicGoogle"]["inputCapabilities"]["image"]["lastFrameDurationSeconds"] == 8
    assert result["google1080Six"]["code"] == "duration_resolution_unsupported"
    assert result["googleLastFrameSix"]["code"] == "last_frame_duration_unsupported"
