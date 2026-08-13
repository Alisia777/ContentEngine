"""Focused v4.9.4 regressions for generation AI-context isolation.

These checks deliberately distinguish two similarly-looking paths:

* a project-scoped *passive* draft for another product must be quarantined;
  it is not a selected AI recommendation for the form currently on screen;
* a human's explicit route target remains fail-closed when its product differs
  from the selected, verified media.

The first case is what made a previous Airfryer draft block a new Lion's Mane
product even though none of the Airfryer fields was applied.
"""

from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATION = (
    ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
).read_text(encoding="utf-8")
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_passive_cross_product_working_draft_is_quarantined_not_promoted_to_failed_lineage() -> None:
    """A passive project draft cannot poison a different product's manual form."""

    apply_shared = _between(
        GENERATION,
        "function applySharedWorkingDraft(form, shared)",
        "async function hydrateSharedWorkingDraft",
    )
    passive_start = apply_shared.index("if (passiveProductFailure) {")
    passive_end = apply_shared.index(
        "if (!applyAuthoritativeRecommendationProduct", passive_start
    )
    passive_branch = apply_shared[passive_start:passive_end]

    # The passive Airfryer-vs-Ezhovik condition is informational, while a
    # matching explicit route target must remain synchronously fail-closed.
    assert "quarantinePassiveWorkingDraft" in passive_branch
    assert "return false" in passive_branch
    assert "if (routeTarget)" in passive_branch
    assert "blockRecommendationProductMismatch" in passive_branch
    assert passive_branch.index("if (routeTarget)") < passive_branch.index(
        "quarantinePassiveWorkingDraft"
    )
    explicit_branch, passive_only_branch = passive_branch.split("} else {", 1)
    assert "blockRecommendationProductMismatch" in explicit_branch
    assert "quarantinePassiveWorkingDraft" not in explicit_branch
    assert "quarantinePassiveWorkingDraft" in passive_only_branch
    assert "blockRecommendationProductMismatch" not in passive_only_branch

    quarantine = _between(
        GENERATION,
        "function quarantinePassiveWorkingDraft(",
        "function applySharedWorkingDraft(",
    )
    # Clear only stale AI lineage. Do not write the Ezhovik product, category,
    # or its human brief from a stored Airfryer recommendation.
    for key in (
        "researchRecommendationVerificationRequired",
        "researchRecommendationVerificationState",
        "researchRecommendationVerificationFailure",
        "researchRecommendationVerificationSelectionId",
        "researchRecommendationVerificationPosition",
        "researchRecommendationProductId",
        "researchRecommendationProductCategory",
        "generationAiResearchWorkingSelectionId",
        "generationAiResearchWorkingPosition",
    ):
        assert f"delete form.dataset.{key}" in quarantine
    assert "real_spend_confirmation.checked = false" not in quarantine
    assert ".value =" not in quarantine
    assert "setStatus(" in quarantine
    assert '"neutral"' in quarantine

    # The only branch which can write recommendation product/category/brief
    # starts strictly after this quarantine return.
    assert passive_end < apply_shared.index("applyAuthoritativeRecommendationProduct")
    assert passive_end < apply_shared.index("product_category: formControl")

    # Once quarantine removes the failed lineage, the ordinary manual payload
    # path is allowed to continue after the human supplies valid category/brief.
    prepare = _between(APP, "function generationSpecPreparePayload(form)", "function generationSpecPayloadKey")
    assert 'researchRecommendationVerificationRequired === "true"' in prepare
    assert "return null;" in prepare


def test_explicit_cross_product_recommendation_stays_fail_closed() -> None:
    """Quarantine must never weaken validation for an explicit AI selection."""

    load = _between(
        GENERATION,
        "async function loadRecommendations(form, context)",
        "function scheduleLoad(",
    )
    explicit_target = load[load.index("if (target) {") : load.index("const state = readState(context);")]
    assert "explicitResearchRecommendationForTarget" in explicit_target
    assert "recommendationProductIdentityMatches(form, exactTarget)" in explicit_target
    assert "blockRecommendationProductMismatch(form, exactTarget)" in explicit_target
    assert 'throw new Error("generation_research_recommendation_product_mismatch")' in explicit_target

    apply = _between(
        GENERATION,
        "function applyRecommendation(envelope, { explicit = false } = {})",
        "function markHumanEdit(",
    )
    assert "researchRecommendationVerificationState !== \"verified\"" in apply
    assert "blockRecommendationProductMismatch(runtime.form, envelope)" in apply

    hydration = _between(
        GENERATION,
        "export function captureGenerationResearchWorkingDraftHydration(form)",
        "export function generationResearchWorkingDraftHydrationUnchanged",
    )
    # A click while the shared project draft is still loading changes this
    # exact snapshot, so the late passive draft cannot erase the pending human
    # choice or its one-shot authorization.
    for token in (
        "workingSelectionId",
        "workingPosition",
        "verificationRequired",
        "verificationState",
        "verificationSelectionId",
        "verificationPosition",
        "verificationFailure",
        "explicitApplyTargetKey",
    ):
        assert token in hydration


def test_first_recommendation_is_visible_read_only_before_any_apply() -> None:
    """A user sees AI output immediately, but no field/provider side effect occurs."""

    render = _between(
        GENERATION,
        "function renderRecommendationPanel()",
        "function buildRoot()",
    )
    # The first card is a preview candidate only. `activeIndex` stays -1 until
    # a human chooses a card or presses the explicit apply button.
    assert "const previewEnvelope = selectedEnvelope() || recommendations[0];" in render
    assert "if (!previewEnvelope)" in render
    assert "const envelope = previewEnvelope;" in render
    assert "runtime.activeIndex = 0" not in render

    load = _between(
        GENERATION,
        "async function loadRecommendations(form, context)",
        "function scheduleLoad(",
    )
    automatic_apply = load[
        load.index("const explicitApplyRequested") : load.index("} catch (error)")
    ]
    compact_automatic_apply = " ".join(automatic_apply.split())
    assert "selected && target && explicitApplyRequested" in compact_automatic_apply
    assert "applyRecommendation(selected, { explicit: true })" in automatic_apply
    assert "applyRecommendation(defaultPreview" not in automatic_apply


def test_learning_basis_conclusions_are_bounded_visible_and_never_an_implicit_provider_call() -> None:
    """Selected research conclusions need a readable, safe handoff to the editor."""

    render = _between(
        GENERATION,
        "function renderRecommendationPanel()",
        "function buildRoot()",
    )
    conclusions = _between(
        GENERATION,
        "function researchRecommendationConclusionLines(",
        "function renderRecommendationPanel()",
    )

    assert "learning_basis" in conclusions
    assert "MAX_RESEARCH_CONCLUSION_LINES" in conclusions
    assert "MAX_RESEARCH_CONCLUSION_LENGTH" in conclusions
    assert "slice(0, MAX_RESEARCH_CONCLUSION_LINES)" in conclusions
    assert "clean(" in conclusions
    assert "researchRecommendationConclusionLines(envelope)" in render
    assert "Выводы ИИ" in render
    assert "data-research-recommendation-conclusions" in render

    # Rendering may only create DOM nodes. A paid/provider action must remain
    # behind the existing explicit generation action, never behind preview.
    assert "applyRecommendation(" not in conclusions
    assert "getApi(" not in conclusions
    assert "provider" not in conclusions.lower()


def test_quarantine_and_conclusion_contract_execute_without_field_or_confirmation_mutation() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const control = {{ dataset: {{ researchRecommendationApplied: 'old' }} }};
      const form = {{
        dataset: {{
          researchRecommendationVerificationRequired: 'true',
          researchRecommendationVerificationState: 'failed',
          researchRecommendationVerificationFailure: 'product_mismatch',
          researchRecommendationProductId: '88a117e4-83a4-4b77-a047-96d1a39b59f7',
          generationAiResearchWorkingSelectionId: 'b979e33c-4ab6-4592-9c13-90eabd1ba712',
          generationAiResearchWorkingPosition: '2',
          identityProductId: '3da51d8d-cf54-47aa-9d8f-8d910387d2c4',
        }},
        elements: {{
          product_name: {{ value: 'Ежовик' }},
          sku: {{ value: 'WB TEST 2' }},
          product_category: {{ value: 'baa' }},
          platform: {{ value: 'youtube' }},
          real_spend_confirmation: {{ checked: true }},
        }},
        querySelectorAll: () => [control],
      }};
      const before = JSON.stringify({{
        product: form.elements.product_name.value,
        sku: form.elements.sku.value,
        category: form.elements.product_category.value,
        confirmed: form.elements.real_spend_confirmation.checked,
      }});
      const quarantined = mod.quarantinePassiveWorkingDraft(form, {{
        selection_id: 'b979e33c-4ab6-4592-9c13-90eabd1ba712',
        recommendation_position: 2,
        source_product_name: 'Аэрогриль MILIO',
      }});
      const after = JSON.stringify({{
        product: form.elements.product_name.value,
        sku: form.elements.sku.value,
        category: form.elements.product_category.value,
        confirmed: form.elements.real_spend_confirmation.checked,
      }});
      const lines = mod.researchRecommendationConclusionLines({{
        recommendation: {{ learning_basis: {{
          selected_insight_keys: ['category', 'trends', 'brief'],
          category_analysis: {{
            definition: 'Покупателю важно понятное объяснение продукта.',
            buyer_jobs: ['Понять способ применения'],
            source_ids: ['secret-source-id'],
          }},
          trend_analysis: {{ signals: [{{
            signal: 'Растёт формат честной демонстрации.',
            evidence: 'Повторяется в проверенных источниках.',
            source_ids: ['nested-secret-source-id'],
            internal_note: 'do-not-render-internal-note',
          }}] }},
          creative_brief: {{
            audience: ['Покупатели, сравнивающие состав'],
            facts: ['Не обещать медицинский результат'],
          }},
        }} }},
      }});
      console.log(JSON.stringify({{
        quarantined, before, after, dataset: form.dataset,
        controlDataset: control.dataset, lines,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value["quarantined"] is True
    assert value["before"] == value["after"]
    assert value["dataset"]["identityProductId"].startswith("3da51d8d")
    assert "researchRecommendationVerificationRequired" not in value["dataset"]
    assert "generationAiResearchWorkingSelectionId" not in value["dataset"]
    assert value["controlDataset"] == {}
    assert 3 <= len(value["lines"]) <= 6
    assert any("Покупателю" in line for line in value["lines"])
    assert any("демонстрации" in line for line in value["lines"])
    assert all("secret-source-id" not in line for line in value["lines"])
    assert all("nested-secret-source-id" not in line for line in value["lines"])
    assert all("do-not-render-internal-note" not in line for line in value["lines"])


def test_pending_explicit_choice_invalidates_inflight_shared_draft_hydration() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const form = {{
        dataset: {{ generationUserEditRevision: '0' }},
        elements: {{}},
      }};
      const before = mod.captureGenerationResearchWorkingDraftHydration(form);
      form.dataset.generationAiResearchWorkingSelectionId =
        'b979e33c-4ab6-4592-9c13-90eabd1ba712';
      form.dataset.generationAiResearchWorkingPosition = '2';
      form.dataset.researchRecommendationVerificationRequired = 'true';
      form.dataset.researchRecommendationVerificationState = 'pending';
      form.dataset.researchRecommendationVerificationSelectionId =
        'b979e33c-4ab6-4592-9c13-90eabd1ba712';
      form.dataset.researchRecommendationVerificationPosition = '2';
      console.log(JSON.stringify({{
        unchanged: mod.generationResearchWorkingDraftHydrationUnchanged(form, before),
        before,
        after: mod.captureGenerationResearchWorkingDraftHydration(form),
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value["unchanged"] is False
    assert value["before"] != value["after"]
