from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "supabase/functions/_shared/generation-model-catalog.js"
SNAPSHOT = ROOT / "supabase/functions/_shared/generation-selection-snapshot.js"
CATALOG_SOURCE = CATALOG.read_text(encoding="utf-8")
SNAPSHOT_SOURCE = SNAPSHOT.read_text(encoding="utf-8")

PRELUDE = r"""
const flags = {
  [catalog.GENERATION_MODEL_FEATURE_FLAGS.runwayPremium]: true,
  [catalog.GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true,
};
const get = (provider, model) => catalog.generationModelCatalogEntry(provider, model);
const select = (provider, model, value) => {
  const result = catalog.validateGenerationModelSelection(
    get(provider, model), value, {featureFlags: flags},
  );
  if (!result.ok) throw new Error(`fixture_selection:${result.code}`);
  return result;
};
const receipt = "123e4567-e89b-42d3-a456-426614174000";
const launch = (entry, patch = {}) => ({
  selectionSource: "system_recommendation",
  recommendationReasonCodes: ["content_kind_match", "provider_model_ready"],
  recommendationWarningCodes: [],
  recommendationCatalogVersion: catalog.GENERATION_MODEL_CATALOG_VERSION,
  pricingVersion: entry.pricingVersion,
  estimatedCostMinor: 120,
  acceptanceStatusAtLaunch: "accepted",
  providerReadinessReceiptId: receipt,
  ...patch,
});
const attempt = (callback) => {
  try { return {ok:true,value:callback()}; }
  catch (error) { return {ok:false,code:error?.code||"",message:error?.message||""}; }
};
"""


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for selection snapshot contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        (directory / "generation-model-catalog.js").write_text(
            CATALOG_SOURCE, encoding="utf-8"
        )
        (directory / "generation-selection-snapshot.js").write_text(
            SNAPSHOT_SOURCE, encoding="utf-8"
        )
        (directory / "contract.js").write_text(
            "import * as catalog from './generation-model-catalog.js';\n"
            "import * as subject from './generation-selection-snapshot.js';\n"
            f"{PRELUDE}\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_module_is_pure_and_has_bounded_exports() -> None:
    for forbidden in (
        "Deno.env",
        "process.env",
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "document.",
        "window.",
        "WebSocket",
        "setTimeout(",
    ):
        assert forbidden not in SNAPSHOT_SOURCE

    result = _evaluate("Object.keys(subject).sort()")
    assert result == [
        "GENERATION_ACCEPTANCE_STATUSES",
        "GENERATION_SELECTION_SNAPSHOT_FIELDS",
        "GENERATION_SELECTION_SOURCES",
        "GenerationSelectionSnapshotError",
        "createGenerationSelectionSnapshot",
        "generationSelectionSnapshotHasReceiptId",
        "readGenerationSelectionSnapshot",
    ]


def test_create_returns_exact_deep_frozen_section_12_snapshot() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("runway", "veo3.1_fast");
          const selection = select("runway", "veo3.1_fast", {
            inputMode:"image",durationSeconds:8,ratio:"9:16",resolution:"1080p",
            audio:true,spokenDialogue:true,firstFrame:true,lastFrame:true,
          });
          const snapshot = subject.createGenerationSelectionSnapshot(
            entry, selection, launch(entry),
          );
          return {
            snapshot,
            keys:Object.keys(snapshot),
            frozen:Object.isFrozen(snapshot) &&
              Object.isFrozen(snapshot.recommendation_reason_codes) &&
              Object.isFrozen(snapshot.recommendation_warning_codes),
          };
        })()
        """
    )
    assert result["keys"] == [
        "provider",
        "model",
        "model_public_label",
        "selection_source",
        "recommendation_reason_codes",
        "recommendation_warning_codes",
        "recommendation_catalog_version",
        "pricing_version",
        "estimated_cost_minor",
        "requested_duration_seconds",
        "requested_ratio",
        "requested_resolution",
        "requested_audio",
        "input_mode",
        "reference_count",
        "acceptance_status_at_launch",
        "provider_readiness_receipt_id",
    ]
    assert result["snapshot"] == {
        "provider": "runway",
        "model": "veo3.1_fast",
        "model_public_label": "Veo 3.1 Fast",
        "selection_source": "system_recommendation",
        "recommendation_reason_codes": [
            "content_kind_match",
            "provider_model_ready",
        ],
        "recommendation_warning_codes": [],
        "recommendation_catalog_version": "2026-08-13.v1",
        "pricing_version": "runway-credits-2026-08-13.v1",
        "estimated_cost_minor": 120,
        "requested_duration_seconds": 8,
        "requested_ratio": "9:16",
        "requested_resolution": "1080p",
        "requested_audio": True,
        "input_mode": "image",
        "reference_count": 0,
        "acceptance_status_at_launch": "accepted",
        "provider_readiness_receipt_id": "123e4567-e89b-42d3-a456-426614174000",
    }
    assert result["frozen"] is True


def test_every_selection_source_and_acceptance_state_is_explicit() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("runway", "seedance2_fast");
          const selected = select("runway", "seedance2_fast", {
            inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",
            audio:true,spokenDialogue:true,referenceImageCount:2,referenceVideo:true,
          });
          const rows = [];
          for (const source of subject.GENERATION_SELECTION_SOURCES) {
            for (const acceptance of subject.GENERATION_ACCEPTANCE_STATUSES) {
              const snapshot = subject.createGenerationSelectionSnapshot(
                entry, selected, launch(entry, {
                  selectionSource:source,
                  acceptanceStatusAtLaunch:acceptance,
                  estimatedCostMinor:145,
                }),
              );
              rows.push([snapshot.selection_source,snapshot.acceptance_status_at_launch]);
            }
          }
          return rows;
        })()
        """
    )
    assert len(result) == 15
    assert {row[0] for row in result} == {
        "system_recommendation",
        "research_recommendation",
        "performance_recommendation",
        "manual_choice",
        "alternative_after_block",
    }
    assert {row[1] for row in result} == {
        "accepted",
        "needs_revalidation",
        "unproven",
    }


def test_create_requires_canonical_identity_and_current_version_parity() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("runway", "gen4_turbo");
          const selected = select("runway", "gen4_turbo", {
            inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",firstFrame:true,
          });
          return {
            clone:attempt(() => subject.createGenerationSelectionSnapshot({...entry},selected,launch(entry))),
            extraSelection:attempt(() => subject.createGenerationSelectionSnapshot(entry,{...selected,cost:25},launch(entry))),
            staleSelection:attempt(() => subject.createGenerationSelectionSnapshot(entry,{...selected,catalogVersion:"old"},launch(entry))),
            staleCatalog:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{recommendationCatalogVersion:"old"}))),
            stalePricing:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{pricingVersion:"old"}))),
            extraLaunch:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,{...launch(entry),secret:"never"})),
          };
        })()
        """
    )
    assert result["clone"]["code"] == "catalog_entry_not_canonical"
    assert result["extraSelection"]["code"] == "selection_not_exact"
    assert result["staleSelection"]["code"] == "selection_binding_invalid"
    assert result["staleCatalog"]["code"] == "version_parity_invalid"
    assert result["stalePricing"]["code"] == "version_parity_invalid"
    assert result["extraLaunch"]["code"] == "launch_metadata_not_exact"


def test_read_treats_only_nullish_values_as_legacy_absent() -> None:
    result = _evaluate(
        r"""
        (() => {
          const legacyNull = subject.readGenerationSelectionSnapshot(null);
          const legacyUndefined = subject.readGenerationSelectionSnapshot(undefined);
          const malformed = [
            {}, "", false, 0, [],
            {provider:"runway"},
          ].map((value) => attempt(() => subject.readGenerationSelectionSnapshot(value)));
          return {
            legacyNull,
            legacyUndefined,
            frozen:Object.isFrozen(legacyNull),
            malformed,
          };
        })()
        """
    )
    expected = {"state": "legacy_absent", "snapshot": None}
    assert result["legacyNull"] == expected
    assert result["legacyUndefined"] == expected
    assert result["frozen"] is True
    assert [row["code"] for row in result["malformed"]] == [
        "snapshot_not_exact",
    ] * 6


def test_blank_receipt_is_honest_absence_and_never_looks_like_paid_authority() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("runway", "gen4.5");
          const selected = select("runway", "gen4.5", {
            inputMode:"text",durationSeconds:6,ratio:"16:9",resolution:"720p",
          });
          const without = subject.createGenerationSelectionSnapshot(
            entry,selected,launch(entry,{providerReadinessReceiptId:""}),
          );
          const withReceipt = subject.createGenerationSelectionSnapshot(
            entry,selected,launch(entry),
          );
          return {
            without,
            absent:subject.generationSelectionSnapshotHasReceiptId(without),
            present:subject.generationSelectionSnapshotHasReceiptId(withReceipt),
            legacy:subject.generationSelectionSnapshotHasReceiptId(null),
          };
        })()
        """
    )
    assert result["without"]["provider_readiness_receipt_id"] == ""
    assert result["absent"] is False
    assert result["present"] is True
    assert result["legacy"] is False


def test_read_preserves_historical_versions_but_checks_catalog_identity_and_label() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("google", "veo-3.1-lite-generate-preview");
          const selected = select("google", "veo-3.1-lite-generate-preview", {
            inputMode:"text",durationSeconds:4,ratio:"16:9",resolution:"720p",audio:true,
          });
          const current = subject.createGenerationSelectionSnapshot(
            entry,selected,launch(entry,{estimatedCostMinor:20,acceptanceStatusAtLaunch:"unproven"}),
          );
          const historical = {
            ...current,
            recommendation_catalog_version:"2025-12-01.v4",
            pricing_version:"google-veo-2025-12.v9",
            requested_duration_seconds:30,
            requested_ratio:"2:1",
            requested_resolution:"1440p",
            reference_count:14,
          };
          return {
            historical:subject.readGenerationSelectionSnapshot(historical),
            unknown:attempt(() => subject.readGenerationSelectionSnapshot({...historical,model:"retired-model"})),
            label:attempt(() => subject.readGenerationSelectionSnapshot({...historical,model_public_label:"Inferred label"})),
          };
        })()
        """
    )
    assert result["historical"]["state"] == "present"
    assert result["historical"]["snapshot"]["recommendation_catalog_version"] == (
        "2025-12-01.v4"
    )
    assert result["historical"]["snapshot"]["pricing_version"] == (
        "google-veo-2025-12.v9"
    )
    assert result["historical"]["snapshot"]["requested_duration_seconds"] == 30
    assert result["historical"]["snapshot"]["requested_ratio"] == "2:1"
    assert result["historical"]["snapshot"]["requested_resolution"] == "1440p"
    assert result["historical"]["snapshot"]["reference_count"] == 14
    assert result["unknown"]["code"] == "catalog_identity_unknown"
    assert result["label"]["code"] == "model_public_label_mismatch"


def test_every_canonical_model_can_create_an_exact_current_snapshot() -> None:
    result = _evaluate(
        r"""
        (() => {
          const fixtures = [
            ["runway","seedream5_lite",{inputMode:"text",durationSeconds:0,ratio:"1:1",resolution:"2K"}],
            ["runway","gen4_turbo",{inputMode:"image",durationSeconds:5,ratio:"9:16",resolution:"720p",firstFrame:true}],
            ["runway","seedance2_fast",{inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true}],
            ["runway","gen4.5",{inputMode:"text",durationSeconds:6,ratio:"16:9",resolution:"720p"}],
            ["runway","seedance2_mini",{inputMode:"video",durationSeconds:6,ratio:"9:16",resolution:"720p",audio:true,referenceVideo:true}],
            ["runway","veo3.1_fast",{inputMode:"text",durationSeconds:6,ratio:"16:9",resolution:"720p",audio:true}],
            ["runway","gemini_omni_flash",{inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"720p",audio:true}],
            ["runway","veo3.1",{inputMode:"text",durationSeconds:8,ratio:"16:9",resolution:"1080p",audio:true}],
            ["runway","seedance2",{inputMode:"text",durationSeconds:5,ratio:"16:9",resolution:"1080p",audio:true}],
            ["google","veo-3.1-lite-generate-preview",{inputMode:"text",durationSeconds:4,ratio:"16:9",resolution:"720p",audio:true}],
          ];
          return fixtures.map(([provider,model,value]) => {
            const entry=get(provider,model);
            const selected=select(provider,model,value);
            const snapshot=subject.createGenerationSelectionSnapshot(
              entry,selected,launch(entry,{estimatedCostMinor:0,acceptanceStatusAtLaunch:"unproven"}),
            );
            return `${snapshot.provider}:${snapshot.model}`;
          });
        })()
        """
    )
    assert result == [
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


def test_strict_allowlist_bounds_codes_cost_receipt_and_capabilities() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("runway", "seedream5_lite");
          const selected = select("runway", "seedream5_lite", {
            inputMode:"image",durationSeconds:0,ratio:"1:1",resolution:"2K",referenceImageCount:1,
          });
          const tooManyCodes = Array.from({length:33},(_,index)=>`reason_${index}`);
          return {
            source:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{selectionSource:"automatic"}))),
            acceptance:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{acceptanceStatusAtLaunch:"verified_by_magic"}))),
            duplicateCodes:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{recommendationReasonCodes:["same","same"]}))),
            unsafeCode:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{recommendationReasonCodes:["https://private.example/?token=secret"]}))),
            tooManyCodes:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{recommendationReasonCodes:tooManyCodes}))),
            fractionalCost:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{estimatedCostMinor:4.2}))),
            negativeCost:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{estimatedCostMinor:-1}))),
            badReceipt:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{providerReadinessReceiptId:"receipt-or-url"}))),
            audioForgery:attempt(() => subject.createGenerationSelectionSnapshot(
              entry,{...selected,audio:true},launch(entry,{estimatedCostMinor:4}),
            )),
            referenceForgery:attempt(() => subject.readGenerationSelectionSnapshot({
              ...subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{estimatedCostMinor:4})),
              reference_count:65,
            })),
          };
        })()
        """
    )
    assert result["source"]["code"] == "selection_source_invalid"
    assert result["acceptance"]["code"] == "acceptance_status_invalid"
    assert result["duplicateCodes"]["code"] == "recommendation_reason_codes_invalid"
    assert result["unsafeCode"]["code"] == "recommendation_reason_codes_invalid"
    assert result["tooManyCodes"]["code"] == "recommendation_reason_codes_invalid"
    assert result["fractionalCost"]["code"] == "estimated_cost_invalid"
    assert result["negativeCost"]["code"] == "estimated_cost_invalid"
    assert result["badReceipt"]["code"] == "readiness_receipt_id_invalid"
    assert result["audioForgery"]["code"] == "selection_capability_invalid"
    assert result["referenceForgery"]["code"] == "reference_count_invalid"


def test_sensitive_and_oversized_metadata_is_rejected_without_echoing_value() -> None:
    result = _evaluate(
        r"""
        (() => {
          const entry = get("runway", "gen4.5");
          const selected = select("runway", "gen4.5", {
            inputMode:"text",durationSeconds:6,ratio:"16:9",resolution:"720p",
          });
          const secret = "DO_NOT_ECHO_PRIVATE_TOKEN";
          const attempts = {
            secret:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,{...launch(entry),authorization:`Bearer ${secret}`})),
            url:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{recommendationWarningCodes:[`https://private.example/?token=${secret}`]}))),
            huge:attempt(() => subject.createGenerationSelectionSnapshot(entry,selected,launch(entry,{recommendationWarningCodes:["x".repeat(65)]}))),
          };
          return {attempts,leaked:JSON.stringify(attempts).includes(secret)};
        })()
        """
    )
    assert result["leaked"] is False
    assert result["attempts"]["secret"]["code"] == "launch_metadata_not_exact"
    assert result["attempts"]["url"]["code"] == "recommendation_warning_codes_invalid"
    assert result["attempts"]["huge"]["code"] == "recommendation_warning_codes_invalid"
