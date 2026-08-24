from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "web/app/generation-spec.js"
MODULE = MODULE_PATH.read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
INDEX = (ROOT / "web/app/index.html").read_text(encoding="utf-8")


def test_generation_spec_normalizer_is_exact_and_fail_closed() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable generation-spec contract")
    script = f"""
import * as subject from {json.dumps(MODULE_PATH.as_uri())};
const id = "11111111-1111-4111-8111-111111111111";
const hash = "a".repeat(64);
const promptHash = "b".repeat(64);
const scope = {{
  primary_media_id: id,
  media_ids: [id],
  platform: "youtube",
  model: "gen4_turbo",
  duration_seconds: 5,
  product_category: "other",
  format: "9:16",
  audio: false,
}};
const spec = {{
  spec_id: id,
  spec_version: 2,
  spec_hash: hash,
  status: "approved",
  exact_scope: scope,
  editable_intent: "Показать товар крупным планом",
  compiled_prompt: "Точный проверенный prompt",
  prompt_hash: promptHash,
  research_provenance: null,
  performance_policy_provenance: null,
  repair_provenance: null,
  outcome_selection_id: null,
  created_at: "2026-08-03T10:00:00.000Z",
  updated_at: "2026-08-03T10:01:00.000Z",
  approved_at: "2026-08-03T10:01:00.000Z",
}};
const oldSpec = {{
  ...spec,
  spec_version: 1,
  spec_hash: "c".repeat(64),
  status: "superseded",
  updated_at: "2026-08-03T10:00:30.000Z",
}};
delete oldSpec.approved_at;
const envelope = {{
  ok: true,
  version: "generation-spec-control-v1",
  generation_spec: spec,
  history: [spec, oldSpec],
  recommended_next_action: {{
    code: "confirm_spend_separately",
    action: "confirm_spend",
    label: "Проверить цену",
    reason: "ТЗ утверждено, оплата подтверждается отдельно.",
    requires_confirmation: true,
    provider_action: false,
    spend_action: false,
  }},
  automatic_approval: false,
  automatic_spend: false,
  automatic_generation: false,
}};
const valid = subject.normalizeGenerationSpecEnvelope(envelope, {{
  expectedScope: scope,
}});
const withExtra = subject.normalizeGenerationSpecEnvelope({{
  ...envelope,
  head_event_hash: hash,
}});
const missingAudio = subject.normalizeGenerationSpecEnvelope({{
  ...envelope,
  generation_spec: {{
    ...spec,
    exact_scope: Object.fromEntries(
      Object.entries(scope).filter(([key]) => key !== "audio"),
    ),
  }},
}});
const historyAsEvent = subject.normalizeGenerationSpecEnvelope({{
  ...envelope,
  history: [{{ event_id: id, action: "approve" }}],
}});
const duplicateHistory = subject.normalizeGenerationSpecEnvelope({{
  ...envelope,
  history: [spec, spec],
}});
const unorderedHistory = subject.normalizeGenerationSpecEnvelope({{
  ...envelope,
  history: [oldSpec, spec],
}});
process.stdout.write(JSON.stringify({{
  valid: Boolean(valid),
  context: subject.approvedGenerationSpecContext(valid, {{
    expectedScope: scope,
    dirty: false,
  }}),
  dirtyContext: subject.approvedGenerationSpecContext(valid, {{
    expectedScope: scope,
    dirty: true,
  }}),
  withExtra: Boolean(withExtra),
  missingAudio: Boolean(missingAudio),
  historyAsEvent: Boolean(historyAsEvent),
  duplicateHistory: Boolean(duplicateHistory),
  unorderedHistory: Boolean(unorderedHistory),
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
        "valid": True,
        "context": {
            "spec_id": "11111111-1111-4111-8111-111111111111",
            "spec_version": 2,
            "spec_hash": "a" * 64,
        },
        "dirtyContext": None,
        "withExtra": False,
        "missingAudio": False,
        "historyAsEvent": False,
        "duplicateHistory": False,
        "unorderedHistory": False,
    }


def test_paid_flow_prepares_then_requires_separate_human_approval() -> None:
    for token in (
            'from "./generation-spec.js?v=20260823.copy-engines.63"',
        "approvedGenerationSpecContext",
        "generationSpecCardMarkup",
        "currentGenerationSpecContext(form)",
        "currentApprovedGenerationSpecContext(form)",
        "generationSpecApproved",
        '"prepare", "patch", "approve", "reject", "revert", "recompute"',
        "research_provenance: generationSpecResearchProvenance(identity)",
        "performance_policy_provenance:",
        "generation_spec_context: generationSpecContext",
        "project_id: projectId",
        "project_id: requireWorkspaceProjectId()",
        "project_id: preparedPayload.project_id",
        "resetGenerationSpecState();",
    ):
        assert token in APP
    readiness = APP.index("${generationReadinessMarkup(initialGenerationReadiness)}")
    card = APP.index("${generationSpecCardMarkup({", readiness)
    assert readiness < card
    assert "hidden: true" not in APP[card : card + 180]
    assert "firstElementChild.hidden = true" not in APP
    assert "без вызова провайдера и списания" in MODULE
    helper_start = APP.index("async function ensurePreparedGenerationSpecForPaidStart")
    helper_end = APP.index("function generationLearningOptOut", helper_start)
    helper = APP[helper_start:helper_end]
    assert 'runGenerationSpecControl(form, "prepare", {' in helper
    assert 'runGenerationSpecControl(form, "patch", {' in helper
    assert helper.count("preparedPayload,") >= 2
    assert 'runGenerationSpecControl(form, "approve")' not in helper
    assert "await refreshGenerationSpec(form, { force: true })" in helper
    submit = APP.index("async function submitRealGeneration")
    approval_gate = APP.index(
        "if (!currentApprovedGenerationSpecContext(form))", submit
    )
    automatic_prepare = APP.index(
        "await ensurePreparedGenerationSpecForPaidStart(form)", submit
    )
    explicit_review = APP.index(
        "openGenerationSpecApprovalReview(form)", automatic_prepare
    )
    preflight = APP.index("runGenerationPreflightForPaidStart", automatic_prepare)
    paid_start = APP.index("state.api.startRealGeneration(payload)", preflight)
    assert submit < approval_gate < automatic_prepare < explicit_review < preflight < paid_start
    guarded_flow = APP[approval_gate:preflight]
    assert "if (!launchSpecPreparation.approvedContext)" in guarded_flow
    assert "платный запуск не выполнялся" in guarded_flow
    assert "return;" in guarded_flow
    assert "generationSpecContext = prepared.approvedContext" in APP[explicit_review:preflight]
    assert "generationSpecContext = prepared.context" not in APP[explicit_review:paid_start]
    assert APP[submit:paid_start].count("state.api.startRealGeneration(payload)") == 0
    assert "head_event_hash" not in APP
    assert "head_event_hash" not in API


def test_strategy_selection_routes_away_from_legacy_generation_spec() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable generation-spec routing")
    script = f"""
import {{ generationSpecPreparationRoute }} from {json.dumps(MODULE_PATH.as_uri())};
process.stdout.write(JSON.stringify({{
  legacy: generationSpecPreparationRoute(""),
  productSwap: generationSpecPreparationRoute("viral_product_swap"),
}}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["legacy"]["legacyAllowed"] is True
    assert payload["legacy"]["prepareRpc"] == "creator_prepare_generation_spec"
    assert payload["productSwap"]["kind"] == "strategy_v2"
    assert payload["productSwap"]["legacyAllowed"] is False
    assert (
        payload["productSwap"]["prepareRpc"]
        == "creator_prepare_generation_strategy_spec"
    )
    assert payload["productSwap"]["code"] == "generation_strategy_spec_route_required"
    for guarded_function in (
        "function generationSpecPreparationFailure",
        "function syncGenerationSpecUi",
        "async function refreshGenerationSpec",
        "async function runGenerationSpecControl",
    ):
        start = APP.index(guarded_function)
        assert "generationSpecPreparationRoute(" in APP[start : start + 1_600]


def test_api_exposes_free_generation_spec_control_and_strict_paid_context() -> None:
    for rpc in (
        "creator_prepare_generation_spec",
        "creator_control_generation_spec",
        "creator_generation_spec_status",
        "creator_generation_spec_effective_policy",
    ):
        assert rpc in API
    for token in (
        '"format",',
        '"audio",',
        "normalizeGenerationSpecLearningContext",
        "normalizeGenerationSpecRepairContext",
        '"spec_id", "spec_version", "spec_hash"',
        "generation_spec_context: generationSpecContext",
        "project_id: requiredProjectId(context.project_id || context.projectId)",
        "project_id: requiredProjectId(input.project_id || input.projectId)",
    ):
        assert token in API
    assert API.count(
        "project_id: requiredProjectId(context.project_id || context.projectId)"
    ) >= 2
    assert API.count(
        "project_id: requiredProjectId(input.project_id || input.projectId)"
    ) >= 2


def test_edge_revalidates_exact_effective_policy_before_paid_start() -> None:
    start_parser = EDGE[
        EDGE.index("function readStartPayload") :
        EDGE.index("function readPreflightPayload")
    ]
    assert '"generation_spec_context"' in start_parser
    assert "readGenerationSpecContext(value.generation_spec_context)" in start_parser
    assert '"generation-spec-effective-policy-v1"' in EDGE
    assert 'value.status !== "approved_current"' in EDGE
    assert '"automatic_approval"' in EDGE
    assert '"automatic_spend"' in EDGE
    assert '"automatic_generation"' in EDGE
    assert '"project_id"' in EDGE
    assert "!isUuid(value.project_id)" in EDGE
    policy_call = EDGE.index('"creator_generation_spec_effective_policy"')
    paid_rpc = EDGE.index('"creator_start_real_generation"', policy_call)
    assert policy_call < paid_rpc
    policy_boundary = EDGE[policy_call:paid_rpc]
    assert "project_id: startPayload.project_id" in policy_boundary
    assert "effectiveGenerationPolicy.projectId !== startPayload.project_id" in policy_boundary
    for token in (
        "generation_spec_scope_binding_invalid",
        "generation_spec_prompt_binding_invalid",
        "generation_spec_policy_binding_invalid",
        "await sha256Hex(new TextEncoder().encode(startPayload.brief))",
    ):
        assert token in EDGE


def test_edge_allows_only_receipted_category_research_to_precede_live_learning() -> None:
    helper_start = EDGE.index(
        "function generationApprovedResearchCategoryRuleIsBound"
    )
    helper_end = EDGE.index(
        "function generationRepairPromptRequirements", helper_start
    )
    helper = EDGE[helper_start:helper_end]
    assert 'context.source !== "approved_research"' in helper
    assert "/researchcategoryrule\\//giu" in helper
    assert "reservedTokens.length !== 1" in helper
    assert "ResearchCategoryRule\\/v2 category_maturity=" in helper
    assert "categoryMaturities.has(match[1])" in helper
    assert "structuralSignals.has(match[3])" in helper
    assert "match[4] === context.creative_angle" in helper
    assert 'context.hook_patterns[0] || "none"' in helper

    policy_call = EDGE.index('"creator_generation_spec_effective_policy"')
    live_learning_call = EDGE.index(
        '"creator_generation_learning_policy"', policy_call
    )
    precedence = EDGE.index(
        "const approvedResearchCategoryPrecedence", live_learning_call
    )
    rejection = EDGE.index(
        'code: "generation_learning_policy_required"', precedence
    )
    assert policy_call < live_learning_call < precedence < rejection
    assert "!approvedResearchCategoryPrecedence" in EDGE[precedence:rejection]
    assert "head_event_hash" not in EDGE


def test_edge_maps_generation_spec_sql_errors_explicitly() -> None:
    validation_422 = {
        "project_id_required",
        "workspace_project_not_found",
        "generation_spec_context_invalid",
        "generation_spec_effective_payload_invalid",
        "generation_spec_prepare_payload_invalid",
        "generation_spec_control_payload_invalid",
        "generation_spec_control_version_invalid",
        "generation_spec_status_payload_invalid",
        "generation_spec_exact_scope_invalid",
        "generation_spec_editable_intent_invalid",
        "generation_spec_prompt_invalid",
        "generation_spec_learning_context_invalid",
        "generation_spec_baseline_learning_invalid",
        "generation_spec_research_provenance_invalid",
        "generation_spec_performance_provenance_invalid",
        "generation_spec_repair_provenance_invalid",
        "generation_spec_patch_invalid",
        "generation_spec_revert_invalid",
        "generation_spec_not_found",
        "generation_spec_primary_media_invalid",
        "generation_spec_reference_bundle_invalid",
    }
    conflicts_409 = {
        "generation_spec_project_scope_mismatch",
        "generation_spec_research_category_rule_stale",
        "generation_spec_approval_required",
        "generation_spec_approval_state_invalid",
        "generation_spec_stale",
        "generation_spec_head_invalid",
        "generation_spec_media_stale",
        "generation_spec_request_mismatch",
        "generation_spec_job_binding_invalid",
        "generation_spec_job_identity_immutable",
        "generation_spec_learning_binding_invalid",
        "generation_spec_repair_binding_invalid",
        "generation_spec_outcome_binding_invalid",
        "generation_spec_provider_start_stale",
        "generation_spec_research_learning_mismatch",
        "generation_spec_research_provenance_stale",
        "generation_spec_performance_learning_mismatch",
        "generation_spec_performance_policy_stale",
        "generation_spec_repair_policy_stale",
        "generation_spec_outcome_selection_stale",
        "generation_spec_outcome_apply_revalidation_required",
        "generation_spec_policy_blocked",
        "generation_spec_previous_version_invalid",
        "generation_spec_version_sequence_invalid",
        "generation_spec_revert_target_invalid",
        "idempotency_key_conflict",
    }
    for code in validation_422 | conflicts_409:
        assert f'"{code}"' in EDGE
    for code in (
        "project_context_invalid",
        "generation_spec_ledger_append_only",
        "research_outcome_generation_assignment_binding_invalid",
        "research_outcome_generation_assignment_invalid",
    ):
        assert f'"{code}"' in EDGE
    assert 'code: "generation_spec_state_conflict"' in EDGE
    assert "generationSpecError.status" in EDGE


def test_edge_accepts_only_atomic_terminal_stale_claim_as_non_retryable() -> None:
    failure_codes = EDGE[
        EDGE.index("const FAILURE_CODES") : EDGE.index(
            "const BUDGET_ERROR_CODES"
        )
    ]
    assert '"generation_spec_provider_start_stale"' in failure_codes
    status_parser = EDGE[
        EDGE.index("function readStatusJob") : EDGE.index(
            "function nullableString"
        )
    ]
    assert "FAILURE_CODES.has(failureCode)" in status_parser

    parser = EDGE[
        EDGE.index("function readTerminalClaimErrorCode") :
        EDGE.index("function budgetErrorHttpStatus")
    ]
    for token in (
        '"ok"',
        '"claimed"',
        '"terminal"',
        '"code"',
        '"retryable"',
        '"job"',
        '"batch_id"',
        '"failure_code"',
        'value.ok !== false',
        'value.claimed !== false',
        'value.terminal !== true',
        'value.retryable !== false',
        'job.id !== jobId',
        'job.status !== "failed"',
        "readGenerationProvider(job.provider) === null",
        'job.failure_code !== code',
        'code !== "generation_spec_provider_start_stale"',
    ):
        assert token in parser
    assert parser.count("Object.keys(") == 2

    claim_start = EDGE.index("const claimSystemJob = async")
    claim_end = EDGE.index("const markReconciliationRequired", claim_start)
    claim = EDGE[claim_start:claim_end]
    raw_error = claim.index(
        'claimCode === "generation_spec_provider_start_stale"'
    )
    raw_error_unavailable = claim.index(
        'return { outcome: "unavailable" };', raw_error
    )
    terminal_parse = claim.index(
        "readTerminalClaimErrorCode(data, jobId)", raw_error_unavailable
    )
    terminal_result = claim.index(
        'outcome: "terminal_rejected"', terminal_parse
    )
    success_parse = claim.index("data.ok !== true", terminal_result)
    assert raw_error < raw_error_unavailable < terminal_parse < terminal_result
    assert terminal_result < success_parse
    assert 'code: "generation_spec_claim_terminalization_failed"' in claim

    handler_start = EDGE.index("const claim = await claimSystemJob(current.id)")
    provider_post = EDGE.index(
        "createResponse = await fetchProviderJsonWithDeadline(", handler_start
    )
    handler = EDGE[handler_start:provider_post]
    terminal_handler = handler.index(
        'claim.outcome === "terminal_rejected"'
    )
    unavailable_handler = handler.index(
        'claim.outcome !== "claimed"', terminal_handler
    )
    assert terminal_handler < unavailable_handler
    assert "terminal: true" in handler[terminal_handler:unavailable_handler]
    assert "retryable: false" in handler[terminal_handler:unavailable_handler]
    assert "409" in handler[terminal_handler:unavailable_handler]


def test_generation_spec_cache_versions_are_published_consistently() -> None:
    assert './supabase-api.js?v=20260823.copy-engines.63' in APP
    assert './app.js?v=20260823.copy-engines.63' in INDEX
    # Один и тот же ?v= на supabase-api.js во ВСЕХ импортёрах: разный штамп
    # создаёт второй экземпляр модуля, и патч алиасов Корзины ложится на чужой
    # прототип (24.08 — шторм 404 creator_workspace_trash_browser в проде).
    for name in (
        "workspace-os-v4-context-trash.js",
        "workspace-os-v4-trash-rpc-alias.js",
    ):
        source = (ROOT / "web/app" / name).read_text(encoding="utf-8")
        assert './supabase-api.js?v=20260823.copy-engines.63' in source
