from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "web/app/generation-spec.js"
APP_PATH = ROOT / "web/app/app.js"
APP = APP_PATH.read_text(encoding="utf-8")


def test_confirmation_review_is_tuple_bound_and_never_dispatches_on_open_or_cancel() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable generation-spec UI contract")
    script = f"""
import * as subject from {json.dumps(MODULE_PATH.as_uri())};

const id = "11111111-1111-4111-8111-111111111111";
const specHash = "a".repeat(64);
const promptHash = "b".repeat(64);
const spokenLine = "Положите продукты, выберите режим — ужин готов без лишних хлопот";
const scope = {{
  primary_media_id: id,
  media_ids: [id],
  platform: "youtube",
  model: "seedance2_fast",
  duration_seconds: 8,
  product_category: "other",
  format: "9:16",
  audio: true,
}};
const rawSpec = {{
  spec_id: id,
  spec_version: 3,
  spec_hash: specHash,
  status: "draft",
  exact_scope: scope,
  editable_intent: "Показать товар и произнести точную реплику",
  compiled_prompt: `Кадр 1. Товар крупным планом.\\nРеплика героя дословно: «${{spokenLine}}»\\nНикаких других реплик.`,
  prompt_hash: promptHash,
  research_provenance: null,
  performance_policy_provenance: null,
  repair_provenance: null,
  outcome_selection_id: null,
  created_at: "2026-08-12T10:00:00.000Z",
  updated_at: "2026-08-12T10:01:00.000Z",
}};
const envelope = subject.normalizeGenerationSpecEnvelope({{
  ok: true,
  version: "generation-spec-control-v1",
  generation_spec: rawSpec,
  history: [rawSpec],
  recommended_next_action: {{
    code: "approve_current_spec",
    action: "approve",
    label: "Проверить и одобрить",
    reason: "Человек должен проверить текущую версию.",
    requires_confirmation: true,
    provider_action: false,
    spend_action: false,
  }},
  automatic_approval: false,
  automatic_spend: false,
  automatic_generation: false,
}});
if (!envelope) throw new Error("fixture envelope did not normalize");
const spec = envelope.generationSpec;
const initialMarkup = subject.generationSpecCardMarkup({{
  status: "ready",
  data: envelope,
  dirty: false,
  saving: false,
  approvalReview: null,
}}, {{ expectedScope: scope }});
const open = subject.generationSpecApprovalReviewDecision({{
  decision: "open",
  spec,
}});
const openMarkup = subject.generationSpecCardMarkup({{
  status: "ready",
  data: envelope,
  dirty: false,
  saving: false,
  approvalReview: open.review,
}}, {{ expectedScope: scope }});
const confirmedReview = subject.generationSpecApprovalReviewState(spec, {{
  confirmed: true,
}});
const confirmedMarkup = subject.generationSpecCardMarkup({{
  status: "ready",
  data: envelope,
  dirty: false,
  saving: false,
  approvalReview: confirmedReview,
}}, {{ expectedScope: scope }});

let rpcCalls = 0;
const dispatched = [];
function dispatch(decision) {{
  if (!decision?.rpcAction) return;
  rpcCalls += 1;
  dispatched.push(decision.rpcAction);
}}
dispatch(open);
const cancel = subject.generationSpecApprovalReviewDecision({{
  decision: "cancel",
  review: open.review,
  spec,
}});
dispatch(cancel);
const callsBeforeExplicitDecision = rpcCalls;
const approve = subject.generationSpecApprovalReviewDecision({{
  decision: "approve",
  review: confirmedReview,
  spec,
  dirty: false,
  confirmed: true,
}});
dispatch(approve);
const revision = subject.generationSpecApprovalReviewDecision({{
  decision: "revision",
  review: confirmedReview,
  spec,
  dirty: false,
}});
dispatch(revision);

const promptChanged = {{ ...spec, prompt_hash: "c".repeat(64) }};
const specChanged = {{ ...spec, spec_hash: "d".repeat(64) }};
const versionChanged = {{ ...spec, spec_version: spec.spec_version + 1 }};
const speechMismatch = {{
  ...spec,
  compiled_prompt: "Кадр с товаром, но без одной дословной реплики.",
}};
const noAudio = {{
  ...spec,
  exact_scope: {{ ...spec.exact_scope, audio: false }},
  compiled_prompt: "Немой продуктовый ролик.",
}};
const staleResults = [promptChanged, specChanged, versionChanged].map((candidate) => (
  subject.generationSpecApprovalReviewDecision({{
    decision: "approve",
    review: confirmedReview,
    spec: candidate,
    dirty: false,
    confirmed: true,
  }})
));
const dirtyResult = subject.generationSpecApprovalReviewDecision({{
  decision: "approve",
  review: confirmedReview,
  spec,
  dirty: true,
  confirmed: true,
}});
const uncheckedResult = subject.generationSpecApprovalReviewDecision({{
  decision: "approve",
  review: open.review,
  spec,
  dirty: false,
  confirmed: false,
}});
const speechMismatchReview = subject.generationSpecApprovalReviewState(
  speechMismatch,
  {{ confirmed: true }},
);
const speechMismatchResult = subject.generationSpecApprovalReviewDecision({{
  decision: "approve",
  review: speechMismatchReview,
  spec: speechMismatch,
  dirty: false,
  confirmed: true,
}});

process.stdout.write(JSON.stringify({{
  initial: {{
    opensReview: initialMarkup.includes('data-generation-spec-control="review"'),
    namesReview: initialMarkup.includes("Открыть и проверить ТЗ"),
    exposesDirectApprove: initialMarkup.includes('data-generation-spec-control="approve"'),
    exposesServerApprovalLabel: initialMarkup.includes("Проверить и одобрить"),
    hasArmedPanel: initialMarkup.includes("data-generation-spec-approval-review"),
  }},
  opened: {{
    ok: open.ok,
    rpcAction: open.rpcAction,
    exactPromptOpen: /generation-spec-card__prompt"\\s+open/.test(openMarkup),
    hasPanel: openMarkup.includes("data-generation-spec-approval-review"),
    exactSpecId: openMarkup.includes(`data-spec-id="${{id}}"`),
    exactSpecVersion: openMarkup.includes('data-spec-version="3"'),
    exactSpecHash: openMarkup.includes(`data-spec-hash="${{specHash}}"`),
    exactPromptHash: openMarkup.includes(`data-prompt-hash="${{promptHash}}"`),
    hasSpokenLine: openMarkup.includes(spokenLine),
    finalDisabled: /data-action="confirm-generation-spec-approval"\\s+disabled/.test(openMarkup),
    hasRevision: openMarkup.includes("На доработку"),
    hasCancel: openMarkup.includes('data-action="cancel-generation-spec-review"'),
  }},
  confirmed: {{
    checkboxChecked: confirmedMarkup.includes("data-generation-spec-approval-confirm checked"),
    finalEnabled: /data-action="confirm-generation-spec-approval"\\s*>/.test(confirmedMarkup),
  }},
  decisions: {{
    callsBeforeExplicitDecision,
    cancelRpc: cancel.rpcAction,
    approve: {{ ok: approve.ok, rpcAction: approve.rpcAction }},
    revision: {{ ok: revision.ok, rpcAction: revision.rpcAction }},
    rpcCalls,
    dispatched,
    staleBlocked: staleResults.every((item) => !item.ok && item.rpcAction === null),
    dirtyBlocked: !dirtyResult.ok && dirtyResult.rpcAction === null,
    uncheckedBlocked: !uncheckedResult.ok && uncheckedResult.rpcAction === null,
    speechMismatchBlocked: !speechMismatchResult.ok && speechMismatchResult.rpcAction === null,
    silentReviewReady: subject.generationSpecSpokenReview(noAudio).ready,
  }},
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload == {
        "initial": {
            "opensReview": True,
            "namesReview": True,
            "exposesDirectApprove": False,
            "exposesServerApprovalLabel": False,
            "hasArmedPanel": False,
        },
        "opened": {
            "ok": True,
            "rpcAction": None,
            "exactPromptOpen": True,
            "hasPanel": True,
            "exactSpecId": True,
            "exactSpecVersion": True,
            "exactSpecHash": True,
            "exactPromptHash": True,
            "hasSpokenLine": True,
            "finalDisabled": True,
            "hasRevision": True,
            "hasCancel": True,
        },
        "confirmed": {
            "checkboxChecked": True,
            "finalEnabled": True,
        },
        "decisions": {
            "callsBeforeExplicitDecision": 0,
            "cancelRpc": None,
            "approve": {"ok": True, "rpcAction": "approve"},
            "revision": {"ok": True, "rpcAction": "reject"},
            "rpcCalls": 2,
            "dispatched": ["approve", "reject"],
            "staleBlocked": True,
            "dirtyBlocked": True,
            "uncheckedBlocked": True,
            "speechMismatchBlocked": True,
            "silentReviewReady": True,
        },
    }


def test_app_routes_confirmation_through_explicit_review_and_rechecks_before_rpc() -> None:
    for token in (
        "approvalReview: null",
        "openGenerationSpecApprovalReview(form)",
        "evaluateGenerationSpecApprovalReview(form, decision)",
        'action === "cancel-generation-spec-review"',
        '"confirm-generation-spec-approval"',
        '"request-generation-spec-revision"',
        "generation_spec_human_review_required",
        "generation_spec_human_review_stale",
        'approvalReview !== state.generationSpec.approvalReview',
        'form.dataset.autoGenerationBrief === spec?.compiled_prompt',
        'clearPriceConfirmation: true',
    ):
        assert token in APP

    review_branch_start = APP.index('if (specAction === "review")')
    review_branch_end = APP.index("control.disabled = true", review_branch_start)
    review_branch = APP[review_branch_start:review_branch_end]
    assert "openGenerationSpecApprovalReview(form)" in review_branch
    assert "runGenerationSpecControl" not in review_branch
    assert "state.api" not in review_branch

    cancel_start = APP.index('if (action === "cancel-generation-spec-review")')
    cancel_end = APP.index(
        'if ([\n    "confirm-generation-spec-approval"', cancel_start
    )
    cancel_branch = APP[cancel_start:cancel_end]
    assert "clearGenerationSpecApprovalReview" in cancel_branch
    assert "runGenerationSpecControl" not in cancel_branch
    assert "state.api" not in cancel_branch

    control_start = APP.index("async function runGenerationSpecControl")
    control_end = APP.index(
        "async function ensurePreparedGenerationSpecForPaidStart", control_start
    )
    control = APP[control_start:control_end]
    assert (
        'action === "approve"\n'
        "    && state.generationSpec.data?.recommendedNextAction?.action"
        ' === "approve"'
    ) in control
    assert "generationSpecApprovalReviewDecision" in control
    exact_recheck = control.index("const exactApprovalDecision")
    rpc = control.index("raw = await state.api.controlGenerationSpec(input)")
    assert exact_recheck < rpc
    assert "evaluateGenerationSpecApprovalReview" in control[exact_recheck:rpc]
    assert (
        '["patch", "reject", "revert", "recompute"].includes(action)'
        in control
    )

    invalidation_start = APP.index("function invalidateGenerationSpec")
    invalidation_end = APP.index("function resetGenerationSpecState", invalidation_start)
    assert "approvalReview = null" in APP[invalidation_start:invalidation_end]
    refresh_start = APP.index("async function refreshGenerationSpec")
    refresh_end = APP.index("function generationSpecResearchId", refresh_start)
    assert "clearGenerationSpecApprovalReview" in APP[refresh_start:refresh_end]
    activity_start = APP.index("function handleFormActivity")
    activity_end = APP.index("function clearWorkspaceDropTargets", activity_start)
    assert "clearGenerationSpecApprovalReview" in APP[activity_start:activity_end]

    review_actions_start = APP.index(
        'if (action === "cancel-generation-spec-review")'
    )
    review_actions_end = APP.index(
        'if (action === "prepare-generation-acceptance")', review_actions_start
    )
    review_actions = APP[review_actions_start:review_actions_end]
    assert "startRealGeneration" not in review_actions
    assert "startProductResearch" not in review_actions


def test_generation_guidance_requires_free_exact_review_before_payment() -> None:
    for obsolete in (
        "отдельное одобрение не требуется",
        "портал сам подготовит и проверит техническое ТЗ",
    ):
        assert obsolete not in APP

    for truthful in (
        "Перед оплатой портал бесплатно подготовит точную версию ТЗ",
        "которую нужно заново проверить и одобрить",
        "Подготовьте бесплатную точную версию ТЗ",
        "отдельно одобрите её перед оплатой",
    ):
        assert truthful in APP


def test_verified_reload_event_restores_runtime_provenance_without_second_rpc() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable reload verification")
    normalize_start = APP.index("function normalizeGenerationResearchPresetEvent")
    normalize_end = APP.index(
        "function handleGenerationResearchPresetApplied", normalize_start
    )
    handler_start = normalize_end
    handler_end = APP.index(
        "function handleGenerationResearchPresetOptOut", handler_start
    )
    normalize_source = APP[normalize_start:normalize_end]
    handler_source = APP[handler_start:handler_end]
    script = f"""
{normalize_source}
{handler_source}

const projectId = "4f0fcfa2-7233-4c0c-9e16-2c20e0aae379";
const selectionId = "b979e33c-4ab6-4592-9c13-90eabd1ba712";
const productId = "88a117e4-83a4-4b77-a047-96d1a39b59f7";
const providerFragment = "AIResearchSelection/v1 C=кухня|H=честный тест|CTA=сравнить|P=4л|A=без выдумок";
const appliedFields = [
  "product_category", "platform", "mode", "duration_seconds", "format", "brief",
];
const form = {{
  isConnected: true,
  dataset: {{
    identityProductId: productId,
    researchRecommendationProductId: productId,
    researchRecommendationProductCategory: "household",
    researchRecommendationLineage: "active",
    researchRecommendationSelectionId: selectionId,
    researchRecommendationPosition: "2",
    researchRecommendationAppliedFields: appliedFields.join(","),
    researchRecommendationVerificationRequired: "true",
    researchRecommendationVerificationState: "verified",
    researchRecommendationVerificationSelectionId: selectionId,
    researchRecommendationVerificationPosition: "2",
  }},
  elements: {{ product_category: {{ value: "household" }} }},
}};
const detail = {{
  verification_only: true,
  authoritative_project_id: projectId,
  selection_id: selectionId,
  recommendation_position: 2,
  authoritative_product_id: productId,
  authoritative_product_category: "household",
  preset: {{
    product_category: "household",
    platform: "youtube",
    mode: "real_seedance",
    duration_seconds: 8,
    format: "9:16",
    brief: "Точный сохранённый замысел",
  }},
  applied_fields: appliedFields,
  provider_prompt_fragment_version: "ai-research-provider-fragment-v1",
  provider_prompt_fragment: providerFragment,
  provider_prompt_fragment_hash: "a".repeat(64),
}};
let activeDocumentForm = form;
const document = {{ querySelector: () => activeDocumentForm }};
const eventFor = (overrides = {{}}, dataset = form.dataset, isConnected = true) => {{
  const candidate = dataset === form.dataset && isConnected
    ? form
    : {{ ...form, dataset, isConnected }};
  activeDocumentForm = candidate;
  return {{
    target: {{ closest: () => candidate }},
    detail: {{ ...detail, ...overrides }},
  }};
}};
const state = {{
  route: {{ path: "/workspace/generation" }},
  aiResearchProviderPromptRequestId: 7,
  aiResearchRecommendation: null,
}};
function contentReviewUuid(value) {{
  return /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-8][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/iu
    .test(String(value || ""));
}}
function isWorkspaceProjectId(value) {{ return contentReviewUuid(value); }}
function currentWorkspaceProjectId() {{ return projectId; }}
function generationAiResearchProviderPromptContract(value) {{
  if (
    value?.provider_prompt_fragment_version !== "ai-research-provider-fragment-v1"
    || !String(value?.provider_prompt_fragment || "").startsWith("AIResearchSelection/v1 ")
    || !/^[0-9a-f]{{64}}$/u.test(String(value?.provider_prompt_fragment_hash || ""))
  ) return null;
  return {{
    providerPromptFragmentVersion: value.provider_prompt_fragment_version,
    providerPromptFragment: value.provider_prompt_fragment,
    providerPromptFragmentHash: value.provider_prompt_fragment_hash,
    providerPromptFragmentStatus: "ready",
  }};
}}
function selectedGenerationProductIdentity() {{ return {{ sku: "518413561" }}; }}
let briefSyncs = 0;
let readinessSyncs = 0;
let forbiddenCalls = 0;
function syncAutomaticGenerationBrief() {{ briefSyncs += 1; }}
function syncGenerationFormReadiness() {{ readinessSyncs += 1; }}
function invalidateGenerationSpec() {{ forbiddenCalls += 1; }}
function persistGenerationFormDraft() {{ forbiddenCalls += 1; }}
function hydrateGenerationAiResearchProviderPrompt() {{ forbiddenCalls += 1; }}

const valid = normalizeGenerationResearchPresetEvent(eventFor());
const wrongProject = normalizeGenerationResearchPresetEvent(eventFor({{
  authoritative_project_id: "11111111-1111-4111-8111-111111111111",
}}));
const wrongProduct = normalizeGenerationResearchPresetEvent(eventFor({{
  authoritative_product_id: "22222222-2222-4222-8222-222222222222",
}}));
const wrongCategory = normalizeGenerationResearchPresetEvent(eventFor({{
  authoritative_product_category: "electronics",
}}));
const pending = normalizeGenerationResearchPresetEvent(eventFor({{}}, {{
  ...form.dataset,
  researchRecommendationVerificationState: "pending",
}}));
const wrongFields = normalizeGenerationResearchPresetEvent(eventFor({{
  applied_fields: ["brief"],
}}));
const badProvider = normalizeGenerationResearchPresetEvent(eventFor({{
  provider_prompt_fragment_hash: "A".repeat(64),
}}));
const detached = normalizeGenerationResearchPresetEvent(
  eventFor({{}}, form.dataset, false),
);

handleGenerationResearchPresetApplied(eventFor());
console.log(JSON.stringify({{
  valid: Boolean(valid?.verificationOnly && valid?.providerPromptContract),
  invalids: [
    wrongProject, wrongProduct, wrongCategory, pending, wrongFields, badProvider,
    detached,
  ],
  stateSelection: state.aiResearchRecommendation,
  requestId: state.aiResearchProviderPromptRequestId,
  briefSyncs,
  readinessSyncs,
  forbiddenCalls,
  providerStatus: form.dataset.researchRecommendationProviderFragmentStatus,
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["invalids"] == [None] * 7
    assert payload["stateSelection"]["projectId"] == (
        "4f0fcfa2-7233-4c0c-9e16-2c20e0aae379"
    )
    assert payload["stateSelection"]["selectionId"] == (
        "b979e33c-4ab6-4592-9c13-90eabd1ba712"
    )
    assert payload["stateSelection"]["productId"] == (
        "88a117e4-83a4-4b77-a047-96d1a39b59f7"
    )
    assert payload["stateSelection"]["providerPromptFragment"]
    assert payload["requestId"] == 8
    assert payload["briefSyncs"] == 1
    assert payload["readinessSyncs"] == 1
    assert payload["forbiddenCalls"] == 0
    assert payload["providerStatus"] == "ready"


def test_price_confirmation_survives_its_own_event_but_not_form_mutation() -> None:
    activity_start = APP.index("function handleFormActivity")
    activity_end = APP.index("function clearWorkspaceDropTargets", activity_start)
    activity = APP[activity_start:activity_end]
    assert 'event.target.name === "real_spend_confirmation"' in activity
    assert "clearPriceConfirmation: !priceConfirmationChanged" in activity
    assert "if (!priceConfirmationChanged) scheduleGenerationFormDraftSave(form)" in activity

    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable price confirmation")
    clear_start = APP.index("function clearGenerationSpecApprovalReview")
    clear_end = APP.index("function generationSpecApprovalReviewDirty", clear_start)
    clear_source = APP[clear_start:clear_end]
    script = f"""
{clear_source}

const state = {{ generationSpec: {{ approvalReview: null }} }};
const checkbox = {{ name: "real_spend_confirmation", checked: true }};
const form = {{ elements: {{ real_spend_confirmation: checkbox }} }};
function applyActivity(target) {{
  const priceConfirmationChanged = target.name === "real_spend_confirmation";
  clearGenerationSpecApprovalReview(form, {{
    render: false,
    clearPriceConfirmation: !priceConfirmationChanged,
  }});
}}
applyActivity(checkbox);
const afterOwnEvent = checkbox.checked;
applyActivity({{ name: "brief" }});
const afterBriefMutation = checkbox.checked;

checkbox.checked = true;
state.generationSpec.approvalReview = {{ key: "exact-review" }};
applyActivity(checkbox);
const ownEventClearsReview = state.generationSpec.approvalReview === null;
const ownEventKeepsPrice = checkbox.checked;

console.log(JSON.stringify({{
  afterOwnEvent,
  afterBriefMutation,
  ownEventClearsReview,
  ownEventKeepsPrice,
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert json.loads(result.stdout) == {
        "afterOwnEvent": True,
        "afterBriefMutation": False,
        "ownEventClearsReview": True,
        "ownEventKeepsPrice": True,
    }


def test_generation_spec_confirmation_sources_are_valid_javascript() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for syntax checks")
    for path in (MODULE_PATH, APP_PATH):
        subprocess.run(
            [node, "--check", str(path)],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
