from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
EDGE_PATH = ROOT / "supabase/functions/creator-generate/index.ts"
APP_PATH = ROOT / "web/app/app.js"
API_PATH = ROOT / "web/app/supabase-api.js"
READINESS_PATH = ROOT / "web/app/generation-provider-readiness.js"
MIGRATION_PATH = (
    ROOT / "supabase/migrations/202608130002_generation_multimodel_authority.sql"
)

EDGE = EDGE_PATH.read_text(encoding="utf-8")
APP = APP_PATH.read_text(encoding="utf-8")
API = API_PATH.read_text(encoding="utf-8")
READINESS = READINESS_PATH.read_text(encoding="utf-8")
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")


def _top_level_function(source: str, name: str) -> str:
    match = re.search(
        rf"(?m)^(?:async\s+)?function\s+{re.escape(name)}\s*\(",
        source,
    )
    assert match is not None, f"Missing JavaScript function: {name}"
    next_match = re.search(
        r"(?m)^(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\(",
        source[match.end() :],
    )
    end = len(source) if next_match is None else match.end() + next_match.start()
    return source[match.start() : end]


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the readiness v4 contract")
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _run_readiness_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the readiness v4 contract")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(READINESS, encoding="utf-8")
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
            timeout=20,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_edge_v4_preflight_is_exactly_project_and_spec_bound() -> None:
    parser = _top_level_function(EDGE, "readPreflightPayload")
    spec_parser = _top_level_function(EDGE, "readGenerationSpecContext")
    receipt_parser = _top_level_function(EDGE, "parseProviderReadinessReceipt")
    recorder = EDGE[
        EDGE.index("  const recordProviderReadiness = async (") :
        EDGE.index("  const handlePreflight = async (")
    ]
    response = EDGE[
        EDGE.index("  const handlePreflight = async (") :
        EDGE.index("  const preflightPayload = readPreflightPayload(body);")
    ]

    assert '...(requiresSpec ? ["project_id", "generation_spec_context"] : [])' in parser
    assert 'Object.keys(value).length !== allowed.size' in parser
    assert "scope_hash" not in parser
    assert 'new Set(["spec_id", "spec_version", "spec_hash"])' in spec_parser
    assert "isIntegerInRange(value.spec_version, 1, 100_000)" in spec_parser

    for field in ("project_id", "spec_id", "spec_version", "spec_hash"):
        assert field in recorder
        assert field in receipt_parser
        assert field in response
    assert "scope_hash" not in recorder
    assert 'typeof value.scope_hash !== "string"' in receipt_parser
    assert "scope_hash: receipt.scopeHash" in response
    assert "PROVIDER_READINESS_RECEIPT_V4" in receipt_parser
    assert "PROVIDER_READINESS_RECEIPT_V3" in receipt_parser
    assert "specBound" in receipt_parser


def test_edge_maps_only_the_exact_nonbaseline_authority_error() -> None:
    error_parser = _top_level_function(EDGE, "readProviderReadinessRpcErrorCode")
    recorder = EDGE[
        EDGE.index("  const recordProviderReadiness = async (") :
        EDGE.index("  const handlePreflight = async (")
    ]
    preflight = EDGE[
        EDGE.index("  const handlePreflight = async (") :
        EDGE.index("  const preflightPayload = readPreflightPayload(body);")
    ]

    assert 'value.message.trim() === "generation_multimodel_baseline_required"' in error_parser
    assert '"generation_spec_baseline_required"' in error_parser
    assert "readProviderReadinessRpcErrorCode(error)" in recorder
    assert "recordedUnavailable.errorCode" in preflight
    assert "recordedReadiness.errorCode" in preflight
    assert preflight.count("recordedReadiness.errorCode },\n          409") == 1
    assert "generation_spec_baseline_required:" in API
    assert "деньги не списаны" in API.lower()


def test_one_recorder_preserves_exact_old3_v3_and_adds_spec_only_to_new4() -> None:
    recorder = EDGE[
        EDGE.index("  const recordProviderReadiness = async (") :
        EDGE.index("  const handlePreflight = async (")
    ]
    sql_recorder = MIGRATION[
        MIGRATION.index(
            "create or replace function public.system_record_generation_provider_readiness("
        ) :
        MIGRATION.index(
            "revoke all on function public.system_record_generation_provider_readiness(jsonb)"
        )
    ]

    assert "generationModelRequiresReadinessV4(" in recorder
    assert "project_id: payload.project_id" in recorder
    assert "spec_id: payload.generation_spec_context?.spec_id" in recorder
    assert "scope_hash" not in recorder

    assert "v4_required boolean" in sql_recorder
    assert "if v4_required then" in sql_recorder
    assert "elsif not exists (" in sql_recorder
    assert "membership.status='active'" in sql_recorder
    assert "p_payload ?| array[" in sql_recorder
    assert "'project_id','spec_id','spec_version','spec_hash'" in sql_recorder
    assert "case when v4_required then\n      'generation-provider-readiness-receipt-v4'\n      else 'generation-provider-readiness-receipt-v3' end" in sql_recorder
    assert "if v4_required then\n    receipt_body:=receipt_body || jsonb_build_object(" in sql_recorder
    assert "baseline_claim_value ->> 'scope_hash' else null end" in sql_recorder


def test_browser_api_sends_v4_context_without_client_scope_hash_and_keeps_v3() -> None:
    script = f"""
import assert from 'node:assert/strict';
const {{ CreatorApi }} = await import({json.dumps(API_PATH.as_uri())});
const api = Object.create(CreatorApi.prototype);
const calls = [];
api.invokeRealGeneration = async (action, payload) => {{
  calls.push({{ action, payload }});
  return {{ ok: true }};
}};

const projectId = '11111111-1111-4111-8111-111111111111';
const specId = '22222222-2222-4222-8222-222222222222';
await api.realGenerationPreflight({{
  provider: 'runway',
  model: 'gen4.5',
  input_mode: 'image',
  duration_seconds: 5,
  format: '9:16',
  resolution: '720p',
  audio: false,
  last_frame: false,
  project_id: projectId,
  generation_spec_context: {{
    spec_id: specId,
    spec_version: 7,
    spec_hash: 'a'.repeat(64),
  }},
  scope_hash: 'b'.repeat(64),
}});
await api.realGenerationPreflight({{
  provider: 'runway',
  model: 'gen4_turbo',
  input_mode: 'image',
  duration_seconds: 5,
  format: '9:16',
  resolution: '720p',
  audio: false,
  last_frame: false,
  project_id: projectId,
  generation_spec_context: {{
    spec_id: specId,
    spec_version: 7,
    spec_hash: 'a'.repeat(64),
  }},
  scope_hash: 'b'.repeat(64),
}});

assert.deepEqual(Object.keys(calls[0].payload).sort(), [
  'audio', 'duration_seconds', 'format', 'generation_spec_context',
  'input_mode', 'last_frame', 'model', 'project_id', 'provider', 'resolution',
].sort());
assert.deepEqual(calls[0].payload.generation_spec_context, {{
  spec_id: specId,
  spec_version: 7,
  spec_hash: 'a'.repeat(64),
}});
assert.equal('scope_hash' in calls[0].payload, false);
assert.deepEqual(Object.keys(calls[1].payload).sort(), [
  'audio', 'duration_seconds', 'format', 'input_mode', 'last_frame',
  'model', 'provider', 'resolution',
].sort());
assert.equal('project_id' in calls[1].payload, false);
assert.equal('generation_spec_context' in calls[1].payload, false);
assert.equal('scope_hash' in calls[1].payload, false);
process.stdout.write(JSON.stringify({{ v4: calls[0], v3: calls[1] }}));
"""
    result = _run_node(script)
    assert result["v4"]["payload"]["generation_spec_context"]["spec_version"] == 7
    assert result["v3"]["payload"]["model"] == "gen4_turbo"


def test_v4_receipts_for_two_specs_do_not_collide_or_cross_validate() -> None:
    result = _run_readiness_module(
        r'''
const base = {
  version: "generation-provider-readiness-receipt-v4",
  receipt_id: "10000000-0000-4000-8000-000000000001",
  receipt_hash: "1".repeat(64),
  organization_id: "10000000-0000-4000-8000-000000000002",
  checked_by: "10000000-0000-4000-8000-000000000003",
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
  project_id: "10000000-0000-4000-8000-000000000004",
  spec_id: "10000000-0000-4000-8000-000000000005",
  spec_version: 7,
  spec_hash: "a".repeat(64),
  scope_hash: "b".repeat(64),
};
const second = {
  ...base,
  receipt_id: "10000000-0000-4000-8000-000000000006",
  receipt_hash: "2".repeat(64),
  spec_id: "10000000-0000-4000-8000-000000000007",
  spec_version: 8,
  spec_hash: "c".repeat(64),
  scope_hash: "d".repeat(64),
};
const options = {
  nowMs: Date.parse("2026-08-13T12:05:00.000Z"),
  organizationId: base.organization_id,
  actorId: base.checked_by,
  gateVersion: base.learning_gate_version,
};
const receipts = subject.generationProviderReadinessPreflights(
  { provider_readiness: [base, second] },
  options,
);
const exactFirst = subject.normalizeGenerationProviderPreflight(base, {
  ...options,
  requiredVersion: "generation-provider-readiness-receipt-v4",
  projectId: base.project_id,
  generationSpecContext: {
    specId: base.spec_id,
    specVersion: base.spec_version,
    specHash: base.spec_hash,
  },
});
const crossed = subject.normalizeGenerationProviderPreflight(base, {
  ...options,
  requiredVersion: "generation-provider-readiness-receipt-v4",
  projectId: second.project_id,
  generationSpecContext: {
    specId: second.spec_id,
    specVersion: second.spec_version,
    specHash: second.spec_hash,
  },
});
const legacy = { ...base };
for (const key of ["project_id", "spec_id", "spec_version", "spec_hash", "scope_hash"]) {
  delete legacy[key];
}
legacy.version = "generation-provider-readiness-receipt-v3";
return {
  count: receipts.length,
  specIds: receipts.map((item) => item.spec_id).sort(),
  exactFirst,
  crossed,
  legacyRejectedForV4: subject.normalizeGenerationProviderPreflight(legacy, {
    ...options,
    requiredVersion: "generation-provider-readiness-receipt-v4",
  }),
};
'''
    )
    assert result["count"] == 2
    assert result["specIds"] == [
        "10000000-0000-4000-8000-000000000005",
        "10000000-0000-4000-8000-000000000007",
    ]
    assert result["exactFirst"]["scope_hash"] == "b" * 64
    assert result["crossed"] is None
    assert result["legacyRejectedForV4"] is None


def test_new4_submit_is_an_explicit_two_action_flow() -> None:
    submit = _top_level_function(APP, "submitRealGeneration")
    gate = submit.index("generationReadinessRequiresV4(generationSku)")
    prepare = submit.index(
        "await ensureGenerationV4ReadinessContext(form, launchContext)", gate
    )
    free_preflight = submit.index("await runGenerationPreflight(form, {", prepare)
    clear_consent = submit.index(
        "form.elements.real_spend_confirmation.checked = false", free_preflight
    )
    separate_decision = submit.index(
        "отдельно подтвердите её и снова нажмите запуск", clear_consent
    )
    campaign = submit.index("const campaignId =", separate_decision)
    paid_transport = submit.index("state.api.startRealGeneration(payload)", campaign)

    assert gate < prepare < free_preflight < clear_consent < separate_decision < campaign
    assert "state.api.startRealGeneration" not in submit[gate:campaign]
    assert "return;" in submit[separate_decision:campaign]
    assert campaign < paid_transport

    readiness = _top_level_function(APP, "generationFormReadiness")
    assert "readinessV4NeedsReceipt ||" not in readiness
    assert "form?.elements?.real_spend_confirmation?.checked === true" in readiness
    sync = _top_level_function(APP, "syncGenerationFormReadiness")
    assert 'submit.dataset.launchPhase = readinessV4NeedsReceipt ? "preflight" : "paid";' in sync
    assert "Подготовить ТЗ и проверить цену бесплатно" in sync
    preflight_copy = sync[
        sync.index("readinessV4NeedsReceipt") :
        sync.index("sku && !spendAllowed")
    ]
    assert "estimatedUsd" not in preflight_copy


def test_new4_runtime_first_action_is_free_and_second_explicit_action_starts_once() -> None:
    # This exercises the dormant path after an authoritative future policy
    # opt-in. Current SQL keeps new4 visible and launch-disabled; this test does
    # not widen or assert that policy.
    submit = _top_level_function(APP, "submitRealGeneration")
    paid_preflight = _top_level_function(APP, "runGenerationPreflightForPaidStart")
    invalidator = _top_level_function(APP, "invalidateGenerationSpec")
    script = "\n".join(
        [
            "import assert from 'node:assert/strict';",
            r'''
class FormData {
  constructor(form) { this.form = form; }
  get(name) {
    if (name === "real_spend_confirmation") {
      const control = this.form.elements.real_spend_confirmation;
      return control.checked ? control.value : null;
    }
    return this.form.values[name] ?? null;
  }
}
''',
            invalidator,
            paid_preflight,
            submit,
            r'''
const RECEIPT_VERSION = "generation-provider-readiness-receipt-v4";
const receipt = {
  version: RECEIPT_VERSION,
  receipt_id: "30000000-0000-4000-8000-000000000001",
  receipt_hash: "a".repeat(64),
  spend_confirmation: "RUNWAY_GEN4_5_5S_720P_SILENT_USD_0.60",
  estimated_cost_minor: 60,
};
const baseSku = {
  readinessVersion: "v4",
  provider: "runway",
  model: "gen4.5",
  inputMode: "image",
  durationSeconds: 5,
  format: "9:16",
  resolution: "720p",
  audio: false,
  lastFrame: false,
  contentKind: "video",
  promptMaxLength: 1200,
  pricingVersion: "runway-credits-2026-08-13.v1",
  catalogVersion: "2026-08-13.v1",
  projectId: "30000000-0000-4000-8000-000000000002",
  generationSpecContext: {
    spec_id: "30000000-0000-4000-8000-000000000003",
    spec_version: 4,
    spec_hash: "b".repeat(64),
  },
};
const form = {
  isConnected: true,
  dataset: {},
  values: {
    campaign_id: "campaign-a",
    sku: "SKU-1",
    product_name: "Product",
    product_category: "other",
    count: "1",
    brief: "One exact product video",
    platform: "instagram",
    destination_ref: "brand-account",
    payout_rub: "0",
  },
  elements: {
    real_spend_confirmation: { value: "", checked: false, disabled: true },
    brief: { focus() {} },
  },
};
let activeProjectId = baseSku.projectId;
let preflightTransport = 0;
let startTransport = 0;
let resetCount = 0;
const toasts = [];
const state = {
  dataEpoch: 9,
  user: { id: "30000000-0000-4000-8000-000000000004" },
  route: { path: "/workspace/generation" },
  realGenerationStartInFlight: false,
  realGenerationStartRequestId: 0,
  realGenerationStartNotice: "",
  generationPreflight: { entries: new Map(), requestId: 0 },
  generationSpec: {
    dirty: false,
    error: "",
    aiResearchBinding: null,
    videoReferenceBinding: null,
    approvalReview: null,
  },
  generationSpend: { data: {} },
  contentGenerationHandoff: null,
  realGenerationDrafts: new Map(),
  sections: {
    generation: { status: "idle" },
    placement: { status: "idle" },
    tasks: { status: "idle" },
  },
  api: {
    bindRealGenerationClientContext() {},
    async startRealGeneration() {
      startTransport += 1;
      return { job: { id: "30000000-0000-4000-8000-000000000005", status: "queued" } };
    },
  },
};
const REAL_GENERATION_ENABLED = true;
const REAL_GENERATION_SOFT_TIMEOUT_MS = 30_000;
const MAX_REAL_GENERATION_REFERENCES = 5;

function requireWorkspaceProjectId() { return activeProjectId; }
function captureGenerationRequestContext() {
  return { form, projectId: activeProjectId, userId: state.user.id };
}
function generationRequestIdentityIsCurrent(context) {
  return context.projectId === activeProjectId && context.userId === state.user.id;
}
function generationRequestContextIsCurrent(context) {
  return generationRequestIdentityIsCurrent(context) && context.form === form && form.isConnected;
}
function captureGenerationLaunchSnapshot() { return { exact: true }; }
function restoreGenerationLaunchSnapshot() { return true; }
function generationPreflightKey() { return `v4:${activeProjectId}`; }
function generationSkuForForm() {
  const current = state.generationPreflight.entries.get(generationPreflightKey());
  const exactReceipt = current?.status === "ready" ? current.preflight : null;
  return {
    ...baseSku,
    projectId: activeProjectId,
    preflight: exactReceipt,
    confirmation: exactReceipt?.spend_confirmation || "",
    estimatedMinor: exactReceipt?.estimated_cost_minor ?? null,
    estimatedCredits: exactReceipt ? 60 : null,
    estimatedUsd: exactReceipt ? "0.60" : null,
    providerReadinessReceiptId: exactReceipt?.receipt_id || "",
    providerReadinessReceiptHash: exactReceipt?.receipt_hash || "",
  };
}
function generationReadinessRequiresV4() { return true; }
function setFormBusy(target, busy) { target.dataset.busy = busy ? "true" : "false"; }
async function ensureGenerationV4ReadinessContext() { return generationSkuForForm(form); }
async function runGenerationPreflight() {
  preflightTransport += 1;
  state.generationPreflight.entries.set(generationPreflightKey(), {
    status: "ready",
    preflight: { ...receipt },
  });
  return { ok: true, preflight: { ...receipt } };
}
function syncGenerationModeForm() {
  const sku = generationSkuForForm(form);
  form.elements.real_spend_confirmation.value = sku.confirmation;
  form.elements.real_spend_confirmation.disabled = !sku.confirmation;
}
function toast(message) { toasts.push(message); }
function generationSpendAllowsMinor() { return true; }
function normalizeGenerationSpendOverview() { return {}; }
async function loadGenerationSpendOverview() {}
function renderWorkspace() {}
function selectedGenerationProductIdentity() {
  return { mediaIds: ["30000000-0000-4000-8000-000000000006"] };
}
function syncAutomaticGenerationBrief() { return { ready: true }; }
function generationPromptInspection() { return { ready: true }; }
function generationLearningContext() { return { source: "baseline" }; }
function generationLearningOptOut() { return false; }
function canManageTeam() { return false; }
async function ensurePreparedGenerationSpecForPaidStart() {
  return {
    context: { ...baseSku.generationSpecContext },
    spec: { compiled_prompt: "Exact server compiled prompt" },
    generationReferenceContext: null,
  };
}
function generationRepairContext() { return null; }
function generationSpecExactScope() { return { exact: true }; }
function generationSelectionSnapshot() {
  return { estimated_cost_minor: 60 };
}
function realGenerationDraftFromPayload() { return { draft: true }; }
function validateGenerationPreflight(value) { return value.preflight ?? value; }
async function withSoftTimeoutResult(promise) {
  return { timedOut: false, result: await promise };
}
function registerGenerationReviewAutostart() { return true; }
function applyRealGenerationResult() {}
function track() {}
function resetGenerationSpecState() { resetCount += 1; }
function clearContentGenerationHandoff() {}
function clearGenerationRepair() {}
function persistGenerationFormDraft() {}
function render() {}
function scheduleRealGenerationPolling() {}
function generationFailureMessage(code) { return String(code || "failed"); }
function actionErrorMessage(error) { return String(error?.message || error); }
function clearGenerationPreflightRetry() {}
function syncGenerationSpecUi() {}

await submitRealGeneration(form, new FormData(form), "real_gen4");
assert.equal(preflightTransport, 1, "first explicit action performs one free preflight");
assert.equal(startTransport, 0, "first explicit action never starts a paid job");
assert.equal(form.elements.real_spend_confirmation.disabled, false);
assert.equal(form.elements.real_spend_confirmation.checked, false);
assert.ok(toasts.at(-1).includes("отдельно подтвердите"));

form.elements.real_spend_confirmation.checked = true;
await submitRealGeneration(form, new FormData(form), "real_gen4");
assert.equal(preflightTransport, 1, "confirmed launch reuses the exact receipt");
assert.equal(startTransport, 1, "second explicit matching action starts exactly once");
assert.equal(form.elements.real_spend_confirmation.checked, false);
assert.equal(resetCount, 1);

for (const mutation of ["spec", "media", "model"]) {
  state.generationPreflight.entries.set(generationPreflightKey(), {
    status: "ready",
    preflight: { ...receipt },
  });
  form.elements.real_spend_confirmation.value = receipt.spend_confirmation;
  form.elements.real_spend_confirmation.checked = true;
  invalidateGenerationSpec(form, mutation);
  const paidBefore = startTransport;
  await submitRealGeneration(form, new FormData(form), "real_gen4");
  assert.equal(startTransport, paidBefore, `${mutation} mutation must not start transport`);
  assert.equal(form.elements.real_spend_confirmation.checked, false);
}

activeProjectId = "30000000-0000-4000-8000-000000000007";
state.generationPreflight.entries.clear();
form.elements.real_spend_confirmation.checked = false;
const paidBeforeProjectSwitch = startTransport;
await submitRealGeneration(form, new FormData(form), "real_gen4");
assert.equal(startTransport, paidBeforeProjectSwitch, "project switch must require its own v4 receipt");

process.stdout.write(JSON.stringify({
  preflightTransport,
  startTransport,
  consentChecked: form.elements.real_spend_confirmation.checked,
}));
''',
        ]
    )
    result = _run_node(script)
    assert result["preflightTransport"] == 5
    assert result["startTransport"] == 1
    assert result["consentChecked"] is False


def test_spec_media_model_and_project_mutations_revoke_v4_receipt_and_consent() -> None:
    invalidator = _top_level_function(APP, "invalidateGenerationSpec")
    resetter = _top_level_function(APP, "resetGenerationSpecState")
    assert 'entry?.preflight?.version ===\n      "generation-provider-readiness-receipt-v4"' in invalidator
    assert "state.generationPreflight.entries.delete(key)" in invalidator
    assert "form.elements.real_spend_confirmation.checked = false" in invalidator
    assert "state.generationPreflight.entries.delete(key)" in resetter

    change_handler = _top_level_function(APP, "handleChange")
    for field in ("media_id", "primary_media_id", "generation_mode"):
        assert f'"{field}"' in change_handler
    assert "invalidateGenerationSpec(" in change_handler

    input_handler = _top_level_function(APP, "handleFormActivity")
    for field in (
        "generation_provider",
        "generation_model_id",
        "generation_input_mode",
        "generation_resolution",
        "generation_audio",
        "generation_last_frame",
    ):
        assert f'"{field}"' in input_handler
    assert "exactGenerationSettingChanged" in input_handler
    assert "invalidateGenerationSpec(" in input_handler

    project_switch = APP[
        APP.index("state.generationLearning.enabledKey = \"\";") :
        APP.index("state.accessCenter.requestId += 1;")
    ]
    assert "resetGenerationSpecState();" in project_switch
    assert "state.generationPreflight.entries.clear();" in project_switch

    script = "\n".join(
        [
            "import assert from 'node:assert/strict';",
            invalidator,
            r'''
const v4 = "generation-provider-readiness-receipt-v4";
const v3 = "generation-provider-readiness-receipt-v3";
const cleared = [];
const state = {
  generationSpec: {
    dirty: false,
    error: "",
    aiResearchBinding: { id: 1 },
    videoReferenceBinding: { id: 2 },
    approvalReview: { id: 3 },
  },
  generationPreflight: {
    entries: new Map([
      ["v4-spec-a", { preflight: { version: v4 } }],
      ["legacy-v3", { preflight: { version: v3 } }],
    ]),
  },
};
const form = {
  dataset: { autoGenerationPreflightKey: "v4-spec-a" },
  elements: { real_spend_confirmation: { checked: true } },
};
function clearGenerationPreflightRetry(entry) { cleared.push(entry.preflight.version); }
function syncGenerationSpecUi(value) { assert.equal(value, form); }
invalidateGenerationSpec(form, "changed");
assert.deepEqual([...state.generationPreflight.entries.keys()], ["legacy-v3"]);
assert.deepEqual(cleared, [v4]);
assert.equal(form.elements.real_spend_confirmation.checked, false);
assert.equal("autoGenerationPreflightKey" in form.dataset, false);
assert.equal(state.generationSpec.dirty, true);
assert.equal(state.generationSpec.error, "changed");
process.stdout.write(JSON.stringify({ startTransport: 0, remaining: [...state.generationPreflight.entries.keys()] }));
''',
        ]
    )
    result = _run_node(script)
    assert result == {"startTransport": 0, "remaining": ["legacy-v3"]}


def test_new4_catalog_policy_false_is_visible_but_never_launchable() -> None:
    catalog = EDGE[
        EDGE.index("  const modelCatalogPayload = readModelCatalogPayload(body);") :
        EDGE.index("  const readCurrentStatus = async (")
    ]
    assert "const launchEnabled = entry.enabled && executionSupported &&" in catalog
    assert "policy?.launchEnabled === true" in catalog
    assert '? policy?.disabledReasonCode || "launch_route_pending"' in catalog
    assert "executionSupported," in catalog
    assert "launchEnabled," in catalog
    assert "disabledReasonCode," in catalog
    policy_parser = _top_level_function(EDGE, "readGenerationProviderPolicy")
    assert '"disabled_reason_code"' in policy_parser
    assert "(value.launch_enabled && disabledReasonCode !== null)" in policy_parser
    for reason in (
        "sql_authority_parity_pending",
        "premium_model_launch_unsupported",
        "direct_google_disabled",
        "organization_feature_disabled",
    ):
        assert f"then '{reason}'" in MIGRATION
