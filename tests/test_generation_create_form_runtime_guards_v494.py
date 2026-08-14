"""Regression contracts for the live paid-generation create form (v4.9.4).

The generation page receives harmless background updates while an operator is
editing it. Those updates must neither hide the real reason a free spec cannot
be prepared nor recreate a live form and accidentally replay its paid consent.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "web" / "app" / "app.js"
APP = APP_PATH.read_text(encoding="utf-8")
DRAFT = (ROOT / "web" / "app" / "generation-form-draft.js").read_text(
    encoding="utf-8"
)


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _node_json(source: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable generation contracts")
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_generation_spec_preparation_failure_exposes_exact_non_generic_blockers() -> None:
    """The operator gets an actionable reason before any paid route is reached."""

    failure = _between(
        APP,
        "function generationSpecPreparationFailure(form, compiled = null)",
        "function generationSpecPayloadKey",
    )
    outcomes = _node_json(
        f"""
        function selectedGenerationProductIdentity() {{ return {{ productId: "media" }}; }}
        function generationVideoReferenceForForm() {{
          return {{ present: true, ready: false, code: "generation_video_reference_mechanics_invalid" }};
        }}
        {failure}
        const form = ({{
          dataset: {{}},
          elements: {{
            sku: {{ value: "BAD-LION-001" }},
            product_name: {{ value: "Ежовик гребенчатый" }},
            product_category: {{ value: "" }},
            brief: {{ value: "Показать товар в кадре" }},
          }},
        }});
        const provider = generationSpecPreparationFailure({{
          ...form,
          dataset: {{ researchRecommendationVerificationFailure: "provider_prompt_fragment_unverified" }},
        }});
        const category = generationSpecPreparationFailure(form);
        form.elements.product_category.value = "baa";
        const reference = generationSpecPreparationFailure(form);
        process.stdout.write(JSON.stringify({{provider, category, reference}}));
        """
    )

    assert outcomes["provider"]["code"] == "provider_prompt_fragment_unverified"
    assert outcomes["category"]["code"] == "generation_product_category_required"
    assert outcomes["reference"]["code"] == "generation_video_reference_mechanics_invalid"
    for outcome in outcomes.values():
        assert outcome["code"] != "generation_spec_prepare_unavailable"
        assert outcome["message"]

    # Both free prepare/patch and the paid-start guard surface the same typed
    # error. This forbids the old generic “safe spec was not built” message.
    click = _between(APP, "if ([\"prepare\", \"patch\"].includes(specAction))", "const requestedTargetVersion")
    assert "generationSpecPreparationFailure(form, compiled)" in click
    assert "new CreatorApiError(failure.message, { code: failure.code })" in click
    paid = _between(
        APP,
        "async function ensurePreparedGenerationSpecForPaidStart(form)",
        "function generationLearningOptOut",
    )
    assert "const failure = generationSpecPreparationFailure(form);" in paid
    assert "new CreatorApiError(\n      failure.message," in paid


def test_app_hydrator_defers_when_an_explicit_ai_choice_arrives_inflight() -> None:
    """The app-level server draft read cannot erase a later explicit click."""

    fingerprint = _between(
        APP,
        "function generationAiResearchHydrationSelectionFingerprint(form)",
        "function generationAiResearchSessionPrefix",
    )
    restore = _between(
        APP,
        "async function restoreGenerationFormDraft(form)",
        "function clearGenerationFormDraft",
    )
    outcomes = _node_json(
        f"""
        {fingerprint}
        const form = {{ dataset: {{}} }};
        const before = generationAiResearchHydrationSelectionFingerprint(form);
        const delayedRead = Promise.resolve().then(() => ({{ draft: {{}} }}));
        form.dataset.generationAiResearchWorkingSelectionId =
          "b979e33c-4ab6-4592-9c13-90eabd1ba712";
        form.dataset.generationAiResearchWorkingPosition = "2";
        form.dataset.researchRecommendationVerificationRequired = "true";
        form.dataset.researchRecommendationVerificationState = "pending";
        form.dataset.researchRecommendationVerificationSelectionId =
          "b979e33c-4ab6-4592-9c13-90eabd1ba712";
        form.dataset.researchRecommendationVerificationPosition = "2";
        await delayedRead;
        const after = generationAiResearchHydrationSelectionFingerprint(form);
        process.stdout.write(JSON.stringify({{ changed: before !== after }}));
        """
    )
    assert outcomes == {"changed": True}
    assert "const selectionFingerprintAtStart" in restore
    assert "const selectionChangedSinceStart" in restore
    edit_guard = restore.index("if (userEditedSinceStart())")
    guard = restore.index("if (selectionChangedSinceStart())")
    assert edit_guard < guard
    assert guard < restore.index("applyGenerationAiResearchWorkingDraft(form, shared)")
    assert "&& !selectionChangedSinceStart()" in restore
    assert "const deferred = edited || selectionChanged;" in restore


def test_background_spend_and_status_updates_do_not_full_render_a_live_create_form() -> None:
    """Polling must preserve dirty, focused, and busy creator inputs verbatim."""

    spend = _between(
        APP,
        "async function loadGenerationSpendOverview({ silent = false, force = false } = {})",
        "function syncGenerationModelAcceptanceUi",
    )
    assert "renderGenerationBackgroundUpdate();" in spend
    final = spend[spend.index("finally {") :]
    generation_render = final[
        final.index('if (state.route.path === "/workspace/generation")') : final.index(
            "} else {\n        render();"
        )
    ]
    assert "renderGenerationBackgroundUpdate();" in generation_render
    assert "render();" not in generation_render

    background = _between(
        APP,
        "function renderGenerationBackgroundUpdate()",
        "function syncGenerationModelAcceptanceUi",
    )
    # Protected states use patch-only DOM updates; full `render()` would replace
    # the form controls and is forbidden from the background helper.
    for token in (
        '"#mock-batch-form"',
        'form.dataset.dirty === "true"',
        'form.dataset.busy === "true"',
        "form.contains(document.activeElement)",
    ):
        assert token in background
    protected_path = background[
        background.index("const protectActiveForm") : background.index(
            "if (!protectActiveForm)"
        )
    ]
    assert "render();" not in protected_path
    unprotected_path = background[background.index("if (!protectActiveForm)") :]
    assert "render();" in unprotected_path
    assert "syncGenerationSpendSnapshotUi(form);" in background
    assert "syncGenerationModeForm(form);" not in background
    assert "syncGenerationFormReadiness(form);" in background
    assert "syncGenerationArchiveCardUi();" in background

    archive_sync = _between(
        APP,
        "function syncGenerationArchiveCardUi()",
        "function generationArchiveMarkup",
    )
    assert 'document.querySelector("[data-generation-archive-card]")' in archive_sync
    assert 'current.querySelector("form[data-dirty], form[data-busy=\'true\']")' in archive_sync
    assert "current.contains(document.activeElement)" in archive_sync
    assert "generationArchiveCardMarkup().trim()" in archive_sync
    assert "current.replaceWith(next);" in archive_sync
    assert 'document.querySelector("#mock-batch-form")' not in archive_sync
    assert ".elements" not in archive_sync

    result = _between(
        APP,
        "function applyRealGenerationResult(jobId, result, options = {})",
        "function applyRealGenerationStatusError",
    )
    status_error = _between(
        APP,
        "function applyRealGenerationStatusError(jobId, error)",
        "function markGenerationStatusStillRunning",
    )
    still_running = _between(
        APP,
        "function markGenerationStatusStillRunning(jobId)",
        "function patchGenerationBatch",
    )
    for handler in (result, status_error, still_running):
        assert "renderGenerationBackgroundUpdate()" in handler
        assert "if (state.route.path === \"/workspace/generation\") render();" not in handler

    runtime = _node_json(
        f"""
        let fullRenders = 0;
        let spendSyncs = 0;
        let readinessSyncs = 0;
        let archiveSyncs = 0;
        const state = {{ route: {{ path: "/workspace/generation", query: new URLSearchParams() }} }};
        const form = {{
          isConnected: true,
          dataset: {{ dirty: "true" }},
          contains: () => true,
        }};
        const document = {{
          activeElement: {{}},
          querySelector: (selector) => selector === "#mock-batch-form" ? form : null,
        }};
        const render = () => fullRenders += 1;
        const syncGenerationSpendSnapshotUi = () => spendSyncs += 1;
        const syncGenerationFormReadiness = () => readinessSyncs += 1;
        const syncGenerationArchiveCardUi = () => archiveSyncs += 1;
        {background}
        const returned = renderGenerationBackgroundUpdate();
        process.stdout.write(JSON.stringify({{
          returned, fullRenders, spendSyncs, readinessSyncs, archiveSyncs,
        }}));
        """
    )
    assert runtime == {
        "returned": False,
        "fullRenders": 0,
        "spendSyncs": 1,
        "readinessSyncs": 1,
        "archiveSyncs": 1,
    }

    archive_runtime = _node_json(
        f"""
        const next = {{ kind: "new-archive" }};
        const current = {{
          replaced: null,
          querySelector: () => null,
          contains: () => false,
          replaceWith(value) {{ this.replaced = value; }},
        }};
        const wrapper = {{ innerHTML: "", firstElementChild: next }};
        const document = {{
          querySelector: (selector) => selector === "[data-generation-archive-card]" ? current : null,
          createElement: () => wrapper,
          activeElement: {{}},
        }};
        const generationArchiveCardMarkup = () => "<section></section>";
        {archive_sync}
        const result = syncGenerationArchiveCardUi();
        process.stdout.write(JSON.stringify({{ result, replaced: current.replaced === next }}));
        """
    )
    assert archive_runtime == {"result": True, "replaced": True}


def test_real_spend_consent_is_memory_only_and_restored_only_for_exact_fingerprint() -> None:
    """A re-render never turns a paid checkbox back on for a changed launch."""

    fingerprint = _between(
        APP,
        "function generationSpendConsentFingerprint(form)",
        "function generationSpecPreparationFailure",
    )
    # Every priced-launch input is part of the fingerprint. Any product, spec,
    # reference, media, mode/token change changes the JSON equality check.
    for token in (
        "organization_id",
        "actor_id",
        "project_id",
        "product_id",
        "sku",
        "product_name",
        "product_category",
        "generation_mode",
        "duration_seconds",
        "format",
        "platform",
        "destination_ref",
        "campaign_id",
        "brief",
        "confirmation_value",
        "media_ids",
        "primary_media_id",
        "reference_url",
        "reference_mechanics",
        "reference_access_confirmed",
        "reference_transform_confirmed",
        "spec_id",
        "spec_version",
        "spec_hash",
    ):
        assert token in fingerprint
    assert "sessionStorage" not in fingerprint
    assert "localStorage" not in fingerprint

    capture = _between(APP, "function captureDirtyWorkspaceForms(container)", "function restoreDirtyWorkspaceForms")
    restore = _between(APP, "function restoreDirtyWorkspaceForms(container, snapshots)", "function workspaceNavLinkMarkup")
    # The generic field replay explicitly skips the payment checkbox. The only
    # restoration path below requires an in-memory snapshot and strict equality.
    assert 'if (field.name === "real_spend_confirmation") return;' in restore
    assert "savedConfirmation?.checked === true" in restore
    assert "snapshot.generationSpendConsentFingerprint" in restore
    assert "snapshot.generationSpendConsentFingerprint === fingerprint" in restore
    assert "if (confirmation) confirmation.checked = restoreSpendConsent;" in restore
    assert "generationSpendConsentFingerprint" in capture

    # No durable generation-form draft stores the checkbox or its fingerprint.
    assert "real_spend_confirmation" not in DRAFT
    assert "generationSpendConsentFingerprint" not in DRAFT
    assert "sessionStorage" not in capture
    assert "localStorage" not in capture
    assert "sessionStorage" not in restore
    assert "localStorage" not in restore


def test_real_spend_fingerprint_changes_with_actor_product_concept_media_and_spec() -> None:
    """A checkbox decision cannot cross any meaningful paid-launch boundary."""

    fingerprint = _between(
        APP,
        "function generationSpendConsentFingerprint(form)",
        "function generationSpecPreparationFailure",
    )
    outcomes = _node_json(
        f"""
        let projectId = "11111111-1111-4111-8111-111111111111";
        const state = {{
          api: {{ organizationId: "22222222-2222-4222-8222-222222222222" }},
          bootstrap: {{ organization: {{ id: "22222222-2222-4222-8222-222222222222" }} }},
          user: {{ id: "33333333-3333-4333-8333-333333333333" }},
          generationSpec: {{ data: {{ generationSpec: {{
            spec_id: "44444444-4444-4444-8444-444444444444",
            spec_version: 1,
            spec_hash: "a".repeat(64),
          }} }} }},
        }};
        const currentWorkspaceProjectId = () => projectId;
        const contentReviewUuid = (value) => /^[0-9a-f-]{{36}}$/u.test(value);
        {fingerprint}
        const fields = {{
          sku: {{ value: "BAD-001" }},
          product_name: {{ value: "Ежовик" }},
          product_category: {{ value: "baa" }},
          generation_mode: {{ value: "runway_gen4_turbo" }},
          duration_seconds: {{ value: "5" }},
          format: {{ value: "9:16" }},
          platform: {{ value: "youtube" }},
          destination_ref: {{ value: "channel" }},
          campaign_id: {{ value: "55555555-5555-4555-8555-555555555555" }},
          brief: {{ value: "Показать текстуру продукта" }},
          real_spend_confirmation: {{ value: "CONFIRM-5-USD" }},
          generation_reference_url: {{ value: "https://youtu.be/example" }},
          generation_reference_mechanics: {{ value: "Крупный план и поворот упаковки" }},
          generation_reference_source_access_confirmed: {{ checked: true }},
          generation_reference_transformative_use_confirmed: {{ checked: true }},
          generation_strategy_id: {{ value: "viral_product_swap" }},
          generation_strategy_version: {{ value: "2026-08-14.v1" }},
          generation_strategy_recipe_version: {{ value: "2026-06" }},
          generation_strategy_source_basis: {{ value: "exact_source_video" }},
          generation_strategy_duration_seconds: {{ value: "10" }},
          generation_strategy_ratio: {{ value: "" }},
          generation_strategy_resolution: {{ value: "1080p" }},
          generation_strategy_audio: {{ value: "true" }},
          generation_strategy_source_video_id: {{ value: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" }},
          generation_strategy_avatar_media_id: {{ value: "" }},
          generation_strategy_original_product_media_id: {{ value: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" }},
        }};
        const media = [{{ value: "66666666-6666-4666-8666-666666666666" }}];
        const attestations = [{{
          dataset: {{ generationStrategyAttestation: "transformative_use_confirmed" }},
          checked: true,
        }}];
        const primary = {{ value: media[0].value }};
        const form = {{
          dataset: {{ identityProductId: "77777777-7777-4777-8777-777777777777" }},
          elements: fields,
          querySelectorAll: (selector) => selector.includes("generation-strategy")
            ? attestations
            : media,
          querySelector: () => primary,
        }};
        const baseline = generationSpendConsentFingerprint(form);
        const changed = {{}};
        const mutate = (name, action, undo) => {{
          action();
          changed[name] = generationSpendConsentFingerprint(form) !== baseline;
          undo();
        }};
        mutate("actor", () => state.user.id = "88888888-8888-4888-8888-888888888888", () => state.user.id = "33333333-3333-4333-8333-333333333333");
        mutate("product", () => fields.product_name.value = "Аэрогриль", () => fields.product_name.value = "Ежовик");
        mutate("concept", () => fields.brief.value = "Другой замысел", () => fields.brief.value = "Показать текстуру продукта");
        mutate("media", () => media[0].value = "99999999-9999-4999-8999-999999999999", () => media[0].value = "66666666-6666-4666-8666-666666666666");
        mutate("token", () => fields.real_spend_confirmation.value = "OTHER", () => fields.real_spend_confirmation.value = "CONFIRM-5-USD");
        mutate("spec", () => state.generationSpec.data.generationSpec.spec_version = 2, () => state.generationSpec.data.generationSpec.spec_version = 1);
        mutate("strategy", () => fields.generation_strategy_id.value = "viral_rebuild", () => fields.generation_strategy_id.value = "viral_product_swap");
        mutate("strategy_output", () => fields.generation_strategy_resolution.value = "720p", () => fields.generation_strategy_resolution.value = "1080p");
        mutate("strategy_source", () => fields.generation_strategy_source_video_id.value = "cccccccc-cccc-4ccc-8ccc-cccccccccccc", () => fields.generation_strategy_source_video_id.value = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
        mutate("strategy_attestation", () => attestations[0].checked = false, () => attestations[0].checked = true);
        process.stdout.write(JSON.stringify(changed));
        """
    )
    assert outcomes
    assert all(outcomes.values()), outcomes
