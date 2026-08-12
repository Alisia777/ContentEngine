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
