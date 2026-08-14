import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web" / "app" / "generation-model-recommendation.js"
CATALOG = ROOT / "supabase" / "functions" / "_shared" / "generation-model-catalog.js"


def _run_node(body: str):
    script = f"""
import {{
  GENERATION_MODEL_RECOMMENDATION_ACTIONS as ACTIONS,
  recommendGenerationModels as recommend,
  createGenerationModelRecommendationState as createState,
  generationModelRecommendationReducer as reducer,
}} from {json.dumps(MODULE.as_uri())};
{body}
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _fixture_js() -> str:
    return r"""
const catalog = {
  version: "catalog-v1",
  models: [
    {
      provider: "alpha", model: "dialogue", publicLabel: "Dialogue",
      contentKind: "video", lifecycle: "production", enabled: true,
      inputModes: ["text", "image"], supportsReferenceImages: true,
      maxReferenceImages: 3, supportsReferenceVideo: false,
      supportsFirstFrame: true, supportsLastFrame: true,
      supportsGeneratedAudio: true, supportsSpokenDialogue: true,
      allowedDurations: [5, 10], ratios: ["9:16", "16:9"],
      resolutions: ["720p", "1080p"], qualityTier: "balanced",
      speedTier: "normal", bestFor: ["ugc"], pricingVersion: "price-v7",
    },
    {
      provider: "alpha", model: "economy", publicLabel: "Economy",
      contentKind: "video", lifecycle: "production", enabled: true,
      inputModes: ["text", "image"], supportsReferenceImages: true,
      maxReferenceImages: 1, supportsReferenceVideo: false,
      supportsFirstFrame: false, supportsLastFrame: false,
      supportsGeneratedAudio: false, supportsSpokenDialogue: false,
      allowedDurations: [5], ratios: ["9:16"], resolutions: ["720p"],
      qualityTier: "economy", speedTier: "fast", bestFor: ["draft"],
      pricingVersion: "price-v7",
    },
    {
      provider: "beta", model: "premium", publicLabel: "Premium",
      contentKind: "video", lifecycle: "preview", enabled: true,
      inputModes: ["text", "image", "video"], supportsReferenceImages: true,
      maxReferenceImages: 5, supportsReferenceVideo: true,
      supportsFirstFrame: true, supportsLastFrame: true,
      supportsGeneratedAudio: true, supportsSpokenDialogue: true,
      minDurationSeconds: 5, maxDurationSeconds: 12,
      ratios: ["9:16", "16:9"], resolutions: ["720p", "1080p"],
      qualityTier: "premium", speedTier: "slow", bestFor: ["premium_visual"],
      pricingVersion: "price-v7",
    },
    {
      provider: "beta", model: "disabled", publicLabel: "Disabled",
      contentKind: "video", lifecycle: "production", enabled: false,
      disabledReasonCode: "feature_flag_disabled", inputModes: ["image"],
      supportsReferenceImages: true, maxReferenceImages: 5,
      supportsGeneratedAudio: true, supportsSpokenDialogue: true,
      allowedDurations: [5], ratios: ["9:16"], resolutions: ["720p"],
      qualityTier: "balanced", speedTier: "normal", pricingVersion: "price-v7",
    },
  ],
};
const context = {
  contentKind: "video", intent: "ugc", inputMode: "image",
  durationSeconds: 5, ratio: "9:16", resolution: "720p",
  audio: true, spokenDialogue: true, referenceImageCount: 1,
  requestBudgetMinor: 100, currency: "USD",
  estimatedCosts: {
    "alpha:dialogue": { estimatedCostMinor: 60, pricingVersion: "estimate-v9" },
    "alpha:economy": { estimatedCostMinor: 20, pricingVersion: "estimate-v9" },
    "beta:premium": { estimatedCostMinor: 90, pricingVersion: "estimate-v9" },
    "beta:disabled": { estimatedCostMinor: 50, pricingVersion: "estimate-v9" },
  },
  providerReadiness: { alpha: true, beta: true },
  readiness: {
    "alpha:dialogue": { ready: true, freshness: "fresh" },
    "alpha:economy": { ready: true, freshness: "fresh" },
    "beta:premium": { ready: true, freshness: "fresh" },
    "beta:disabled": { ready: true, freshness: "fresh" },
  },
  acceptance: {
    "alpha:dialogue": { status: "accepted", compatible: true },
    "alpha:economy": { status: "accepted", compatible: true },
    "beta:premium": { status: "unproven" },
    "beta:disabled": { status: "accepted", compatible: true },
  },
};
"""


def test_module_is_pure_and_does_not_duplicate_canonical_model_ids():
    source = MODULE.read_text(encoding="utf-8")
    catalog_source = CATALOG.read_text(encoding="utf-8")

    for forbidden in (
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
        "Date.now",
        "Math.random",
    ):
        assert forbidden not in source

    canonical_model_ids = set(re.findall(r'\bmodel:\s*"([^"]+)"', catalog_source))
    assert canonical_model_ids
    assert all(model_id not in source for model_id in canonical_model_ids)

    result = _run_node(
        """
console.log(JSON.stringify({
  actionValues: Object.values(ACTIONS).sort(),
  frozen: Object.isFrozen(ACTIONS),
}));
"""
    )
    assert result == {
        "actionValues": [
            "accept-recommendation",
            "recommend",
            "select-manual",
            "set-validation",
            "update-catalog",
            "update-context",
        ],
        "frozen": True,
    }


def test_deterministic_filter_rank_reasons_and_alternatives():
    result = _run_node(
        _fixture_js()
        + r"""
const catalogBefore = JSON.stringify(catalog);
const contextBefore = JSON.stringify(context);
const first = recommend(catalog, context);
const second = recommend(catalog, context);
console.log(JSON.stringify({
  same: JSON.stringify(first) === JSON.stringify(second),
  inputsUntouched: catalogBefore === JSON.stringify(catalog) && contextBefore === JSON.stringify(context),
  frozen: Object.isFrozen(first) && Object.isFrozen(first.recommended) && Object.isFrozen(first.alternatives),
  recommended: first.recommended,
  alternatives: first.alternatives.map((entry) => [entry.provider, entry.model, entry.scoreBand]),
  unavailable: Object.fromEntries(first.unavailable.map((entry) => [entry.model, entry.unavailableReasonCodes])),
  catalogVersion: first.catalogVersion,
  pricingVersion: first.pricingVersion,
}));
"""
    )
    assert result["same"] is True
    assert result["inputsUntouched"] is True
    assert result["frozen"] is True
    assert result["recommended"]["provider"] == "alpha"
    assert result["recommended"]["model"] == "dialogue"
    assert result["recommended"]["estimatedCostMinor"] == 60
    assert "intent_declared_best_for" in result["recommended"]["reasonCodes"]
    assert "accepted_output_evidence" in result["recommended"]["reasonCodes"]
    assert result["alternatives"] == [["beta", "premium", "experimental"]]
    assert "audio_unsupported" in result["unavailable"]["economy"]
    assert "spoken_dialogue_unsupported" in result["unavailable"]["economy"]
    assert "feature_flag_disabled" in result["unavailable"]["disabled"]
    assert result["catalogVersion"] == "catalog-v1"
    assert result["pricingVersion"] == "estimate-v9"


def test_all_requested_capability_dimensions_have_explicit_unavailable_reasons():
    result = _run_node(
        r"""
const catalog = { version: "hard-filter", models: [{
  provider: "p", model: "limited", contentKind: "photo", enabled: true,
  lifecycle: "production", inputModes: ["text"], allowedDurations: [4],
  ratios: ["1:1"], resolutions: ["480p"], supportsGeneratedAudio: false,
  supportsSpokenDialogue: false, supportsReferenceImages: false,
  maxReferenceImages: 0, supportsReferenceVideo: false,
  supportsFirstFrame: false, supportsLastFrame: false,
} ] };
const output = recommend(catalog, {
  contentKind: "video", inputMode: "video", durationSeconds: 8,
  ratio: "9:16", resolution: "1080p", audio: true, spokenDialogue: true,
  referenceImageCount: 2, referenceVideo: true, firstFrame: true, lastFrame: true,
  requestBudgetMinor: 50, estimatedCosts: { "p:limited": 10 },
  providerReadiness: { p: true }, readiness: { "p:limited": true },
});
console.log(JSON.stringify(output.unavailable[0].unavailableReasonCodes));
"""
    )
    assert set(result) >= {
        "content_kind_unsupported",
        "input_mode_unsupported",
        "duration_unsupported",
        "ratio_unsupported",
        "resolution_unsupported",
        "audio_unsupported",
        "spoken_dialogue_unsupported",
        "reference_images_unsupported",
        "reference_video_unsupported",
        "first_frame_unsupported",
        "last_frame_unsupported",
    }


def test_server_cost_budget_readiness_and_acceptance_are_advisory_inputs():
    result = _run_node(
        _fixture_js()
        + r"""
const compatible = {
  ...context, audio: false, spokenDialogue: false, intent: "variant",
  acceptance: {
    "alpha:dialogue": { status: "accepted", compatible: true },
    "alpha:economy": { status: "unproven" },
    "beta:premium": { status: "unproven" },
  },
};
const acceptedWins = recommend(catalog, compatible);
const budgetBlocks = recommend(catalog, { ...compatible, requestBudgetMinor: 50 });
const missingEstimate = recommend(catalog, {
  ...compatible,
  estimatedCosts: { "alpha:economy": 20, "beta:premium": 40 },
});
const notReady = recommend(catalog, {
  ...compatible,
  providerReadiness: { alpha: { ready: false, reasonCode: "provider_maintenance" }, beta: true },
});
console.log(JSON.stringify({
  acceptedWins: acceptedWins.recommended.model,
  budgetWinner: budgetBlocks.recommended.model,
  budgetReason: budgetBlocks.unavailable.find((entry) => entry.model === "dialogue").unavailableReasonCodes,
  missingReason: missingEstimate.unavailable.find((entry) => entry.model === "dialogue").unavailableReasonCodes,
  readinessReason: notReady.unavailable.find((entry) => entry.model === "dialogue").unavailableReasonCodes,
}));
"""
    )
    assert result["acceptedWins"] == "dialogue"
    assert result["budgetWinner"] == "economy"
    assert "budget_exceeded" in result["budgetReason"]
    assert "cost_estimate_required" in result["missingReason"]
    assert "provider_maintenance" in result["readinessReason"]


def test_needs_revalidation_is_stale_evidence_not_an_unproven_model():
    result = _run_node(
        r"""
const base = {
  contentKind: "video", enabled: true, lifecycle: "production",
  inputModes: ["text"], allowedDurations: [5], ratios: ["9:16"],
  resolutions: ["720p"], supportsGeneratedAudio: false,
  supportsSpokenDialogue: false, qualityTier: "balanced", speedTier: "normal",
};
const catalog = {
  version: "acceptance-order-v1",
  models: [
    { ...base, provider: "p", model: "accepted", publicLabel: "Accepted" },
    { ...base, provider: "p", model: "stale", publicLabel: "Needs revalidation" },
    { ...base, provider: "p", model: "unproven", publicLabel: "Unproven" },
  ],
};
const context = {
  contentKind: "video", inputMode: "text", durationSeconds: 5,
  ratio: "9:16", resolution: "720p",
  estimatedCosts: {
    "p:accepted": 30,
    "p:stale": 10,
    "p:unproven": 1,
  },
  providerReadiness: { p: true },
  readiness: { "p:accepted": true, "p:stale": true, "p:unproven": true },
  acceptance: {
    "p:accepted": { status: "accepted", compatible: true },
    "p:stale": { status: "needs_revalidation", compatible: true },
    "p:unproven": { status: "unproven", compatible: true },
  },
};
const output = recommend(catalog, context);
console.log(JSON.stringify({
  order: [output.recommended, ...output.alternatives].map((entry) => entry.model),
  accepted: output.recommended,
  stale: output.alternatives.find((entry) => entry.model === "stale"),
  unproven: output.alternatives.find((entry) => entry.model === "unproven"),
}));
"""
    )
    assert result["order"] == ["accepted", "stale", "unproven"]
    assert "accepted_output_evidence" in result["accepted"]["reasonCodes"]
    assert result["accepted"]["warningCodes"] == []
    assert "accepted_output_evidence" not in result["stale"]["reasonCodes"]
    assert "acceptance_stale" in result["stale"]["warningCodes"]
    assert "model_unproven" not in result["stale"]["warningCodes"]
    assert result["stale"]["scoreBand"] != "experimental"
    assert "model_unproven" in result["unproven"]["warningCodes"]
    assert "acceptance_stale" not in result["unproven"]["warningCodes"]
    assert result["unproven"]["scoreBand"] == "experimental"


def test_manual_lock_survives_recommend_context_and_catalog_updates_until_explicit_accept():
    result = _run_node(
        _fixture_js()
        + r"""
let state = createState({ catalogSnapshot: catalog, context });
const initiallyRecommended = state.selection;
state = reducer(state, { type: ACTIONS.SELECT_MANUAL, selection: { provider: "beta", model: "premium" } });
const afterManual = { selection: state.selection, lock: state.manualLock, source: state.selectionSource };
state = reducer(state, { type: ACTIONS.UPDATE_CONTEXT, patch: { speedPreference: "fast" } });
const afterContext = state.selection;
const catalogV2 = { ...catalog, version: "catalog-v2", models: catalog.models.filter((entry) => entry.model !== "premium") };
state = reducer(state, { type: ACTIONS.UPDATE_CATALOG, catalogSnapshot: catalogV2 });
const afterCatalog = {
  selection: state.selection,
  lock: state.manualLock,
  blocked: state.selectionStatus.blocked,
  reasons: state.selectionStatus.reasonCodes,
  recommended: state.recommendation.recommended,
};
state = reducer(state, { type: ACTIONS.RECOMMEND });
const afterRecommend = state.selection;
state = reducer(state, { type: ACTIONS.ACCEPT_RECOMMENDATION });
console.log(JSON.stringify({
  initiallyRecommended,
  afterManual,
  afterContext,
  afterCatalog,
  afterRecommend,
  afterAccept: { selection: state.selection, lock: state.manualLock, source: state.selectionSource },
}));
"""
    )
    assert result["initiallyRecommended"]["model"] == "dialogue"
    assert result["afterManual"] == {
        "selection": {"provider": "beta", "model": "premium"},
        "lock": True,
        "source": "manual",
    }
    assert result["afterContext"]["model"] == "premium"
    assert result["afterCatalog"]["selection"]["model"] == "premium"
    assert result["afterCatalog"]["lock"] is True
    assert result["afterCatalog"]["blocked"] is True
    assert result["afterCatalog"]["reasons"] == ["model_not_in_catalog"]
    assert result["afterCatalog"]["recommended"]["model"] == "dialogue"
    assert result["afterRecommend"]["model"] == "premium"
    assert result["afterAccept"] == {
        "selection": {"provider": "alpha", "model": "dialogue", "publicLabel": "Dialogue"},
        "lock": True,
        "source": "accepted_recommendation",
    }


def test_provider_model_input_duration_ratio_resolution_and_audio_changes_stale_all_validation():
    result = _run_node(
        _fixture_js()
        + r"""
const fresh = {
  preflight: { status: "fresh", receipt: "preflight-1" },
  cost: { status: "fresh", confirmation: "cost-1" },
  spec: { status: "fresh", revision: "spec-1" },
};
let manual = createState({ catalogSnapshot: catalog, context, validation: fresh });
manual = reducer(manual, {
  type: ACTIONS.SELECT_MANUAL,
  selection: { provider: "beta", model: "premium" },
});
let scoped = createState({ catalogSnapshot: catalog, context, validation: fresh });
scoped = reducer(scoped, {
  type: ACTIONS.UPDATE_CONTEXT,
  patch: {
    inputMode: "video", durationSeconds: 10, ratio: "16:9",
    resolution: "1080p", audio: false,
  },
});
let adviceOnly = createState({ catalogSnapshot: catalog, context, validation: fresh });
adviceOnly = reducer(adviceOnly, {
  type: ACTIONS.UPDATE_CONTEXT,
  patch: { qualityPreference: "premium", speedPreference: "slow", intent: "premium_visual" },
});
console.log(JSON.stringify({
  manual: manual.validation,
  scoped: scoped.validation,
  adviceOnly: adviceOnly.validation,
}));
"""
    )
    for section in (result["manual"], result["scoped"]):
        assert section["preflight"]["status"] == "stale"
        assert section["cost"]["status"] == "stale"
        assert section["spec"]["status"] == "stale"
    assert set(result["manual"]["staleReasonCodes"]) == {"provider_changed", "model_changed"}
    assert set(result["scoped"]["staleReasonCodes"]) == {
        "input_changed",
        "duration_changed",
        "ratio_changed",
        "resolution_changed",
        "audio_changed",
        "provider_changed",
        "model_changed",
    }
    assert result["adviceOnly"]["preflight"]["status"] == "fresh"
    assert result["adviceOnly"]["cost"]["status"] == "fresh"
    assert result["adviceOnly"]["spec"]["status"] == "fresh"


def test_invalid_manual_selection_is_visible_and_blocked_without_fallback():
    result = _run_node(
        _fixture_js()
        + r"""
let state = createState({ catalogSnapshot: catalog, context });
state = reducer(state, {
  type: ACTIONS.SELECT_MANUAL,
  selection: { provider: "human-provider", model: "human-choice", publicLabel: "My explicit choice" },
});
const selectedBefore = state.selection;
state = reducer(state, { type: ACTIONS.RECOMMEND, contextPatch: { qualityPreference: "premium" } });
console.log(JSON.stringify({
  selectedBefore,
  selectedAfter: state.selection,
  recommended: state.recommendation.recommended,
  lock: state.manualLock,
  blocked: state.selectionStatus.blocked,
  explanation: state.selectionStatus.reasonCodes,
}));
"""
    )
    assert result["selectedAfter"] == result["selectedBefore"]
    assert result["selectedAfter"] == {
        "provider": "human-provider",
        "model": "human-choice",
        "publicLabel": "My explicit choice",
    }
    assert result["recommended"]["model"] == "dialogue"
    assert result["lock"] is True
    assert result["blocked"] is True
    assert result["explanation"] == ["model_not_in_catalog"]


def test_accepts_exact_public_catalog_projection_field_names_without_a_client_catalog_copy():
    result = _run_node(
        f"""
const {{ publicGenerationModelCatalog }} = await import({json.dumps(CATALOG.as_uri())});
const publicCatalog = publicGenerationModelCatalog();
const photo = publicCatalog.models.find((entry) => entry.contentKind === "photo" && entry.enabled);
const key = `${{photo.provider}}:${{photo.model}}`;
const ratio = photo.allowedRatios[0];
const resolution = photo.allowedResolutions[0];
const context = {{
  contentKind: "photo", inputMode: "text", durationSeconds: 0,
  ratio, resolution, requestBudgetMinor: 100,
  estimatedCosts: {{ [key]: {{ estimatedCostMinor: 40, pricingVersion: "server-estimate-v1" }} }},
  providerReadiness: {{ [photo.provider]: true }}, readiness: {{ [key]: true }},
  acceptance: {{ [key]: {{ status: "accepted", compatible: true }} }},
}};
const direct = recommend(publicCatalog, context);
const state = createState({{ catalogSnapshot: publicCatalog, context }});
const overBudget = reducer(state, {{ type: ACTIONS.UPDATE_CONTEXT, patch: {{ requestBudgetMinor: 30 }} }});
console.log(JSON.stringify({{
  publicModelCount: publicCatalog.models.length,
  selected: direct.recommended && [direct.recommended.provider, direct.recommended.model],
  stateSelected: state.selection && [state.selection.provider, state.selection.model],
  ratioAccepted: direct.unavailable.find((entry) => entry.model === photo.model)?.unavailableReasonCodes || [],
  overBudgetSelection: overBudget.selection,
  overBudgetReason: overBudget.recommendation.unavailable.find((entry) => entry.model === photo.model)?.unavailableReasonCodes || [],
}}));
"""
    )
    assert result["publicModelCount"] > 1
    assert result["selected"] == result["stateSelected"]
    assert result["selected"] is not None
    assert result["ratioAccepted"] == []
    assert result["overBudgetSelection"] is None
    assert "budget_exceeded" in result["overBudgetReason"]
