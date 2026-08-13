import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def _function(name: str, next_name: str) -> str:
    start = APP.index(f"function {name}")
    end = APP.index(f"function {next_name}", start)
    return APP[start:end]


def _top_level_function(name: str) -> str:
    match = re.search(
        rf"(?m)^(?:async\s+)?function\s+{re.escape(name)}\s*\(",
        APP,
    )
    assert match is not None, f"Missing JavaScript function: {name}"
    next_match = re.search(
        r"(?m)^(?:async\s+)?function\s+[A-Za-z_$][\w$]*\s*\(",
        APP[match.end() :],
    )
    end = len(APP) if next_match is None else match.end() + next_match.start()
    return APP[match.start() : end]


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for the paid-start race contract"
    return subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_paid_start_prepares_from_the_enabled_form_snapshot() -> None:
    control = APP[
        APP.index("async function runGenerationSpecControl") :
        APP.index("async function ensurePreparedGenerationSpecForPaidStart")
    ]
    ensure = APP[
        APP.index("async function ensurePreparedGenerationSpecForPaidStart") :
        APP.index("function generationLearningOptOut")
    ]
    submit = APP[
        APP.index("async function submitRealGeneration") :
        APP.index("async function submitMockBatch")
    ]
    assert "preparedPayload: preparedPayloadOverride = null" in control
    assert "preparedPayloadOverride\n    || generationSpecPreparePayload(form)" in control
    assert 'runGenerationSpecControl(form, "prepare", {\n      preparedPayload,' in ensure
    assert 'runGenerationSpecControl(form, "patch", {\n      preparedPayload,' in ensure
    before_ensure = submit[: submit.index("ensurePreparedGenerationSpecForPaidStart(form)")]
    assert "setFormBusy(form, true" not in before_ensure[-250:]


def test_nested_busy_updates_do_not_overwrite_original_control_state() -> None:
    busy = _function("setFormBusy", "withUiTimeout")
    assert 'const wasBusy = form.dataset.busy === "true"' in busy
    assert "if (!wasBusy)" in busy
    assert "if (!submit.dataset.originalLabel)" in busy


def test_free_prepare_failure_restores_content_but_resets_spend_consent() -> None:
    submit = APP[
        APP.index("async function submitRealGeneration") :
        APP.index("async function submitMockBatch")
    ]
    prepare_catch = submit[
        submit.index("ensurePreparedGenerationSpecForPaidStart(form)") :
        submit.index("const brief = String(preparedSpec.compiled_prompt")
    ]
    assert "restoreGenerationLaunchSnapshot(form, launchSnapshot)" in prepare_catch
    assert "form.elements.real_spend_confirmation.checked = false" in prepare_catch


def test_generation_request_context_rejects_every_stale_paid_launch_dimension() -> None:
    script = "\n".join(
        [
            "import assert from 'node:assert/strict';",
            _top_level_function("captureGenerationRequestContext"),
            _top_level_function("generationRequestIdentityIsCurrent"),
            _top_level_function("generationRequestContextIsCurrent"),
            _top_level_function("generationPreflightContextIsCurrent"),
            """
const state = {
  dataEpoch: 7,
  user: { id: "employee-a" },
  route: { path: "/workspace/generation" },
};
let activeProjectId = "project-a";
const sku = { model: "seedance-2-fast", durationSeconds: 8 };
const originalForm = { isConnected: true, sku };
const replacementForm = { isConnected: true, sku: { ...sku } };
let renderedForm = originalForm;
const document = {
  querySelector(selector) {
    assert.equal(selector, "#mock-batch-form");
    return renderedForm;
  },
};
function currentWorkspaceProjectId() { return activeProjectId; }
function generationSkuForForm(form) { return form?.sku || null; }
function generationPreflightKey(value) {
  return value ? `${value.model}:${value.durationSeconds}` : "";
}

const context = captureGenerationRequestContext(originalForm, activeProjectId);
const key = generationPreflightKey(sku);
assert.equal(generationRequestContextIsCurrent(context), true);
assert.equal(generationPreflightContextIsCurrent(context, key), true);

activeProjectId = "project-b";
assert.equal(generationRequestContextIsCurrent(context), false, "project switch");
activeProjectId = "project-a";

renderedForm = replacementForm;
assert.equal(
  generationRequestContextIsCurrent(context),
  false,
  "a replacement form with the same SKU must not inherit the paid request",
);
renderedForm = originalForm;

state.route.path = "/workspace/files";
assert.equal(generationRequestContextIsCurrent(context), false, "route leave");
state.route.path = "/workspace/generation";

state.user.id = "employee-b";
assert.equal(generationRequestContextIsCurrent(context), false, "actor switch");
state.user.id = "employee-a";

state.dataEpoch = 8;
assert.equal(generationRequestContextIsCurrent(context), false, "data epoch change");
state.dataEpoch = 7;

originalForm.sku = { ...sku, durationSeconds: 4 };
assert.equal(generationPreflightContextIsCurrent(context, key), false, "SKU change");
originalForm.sku = sku;

originalForm.isConnected = false;
assert.equal(generationRequestContextIsCurrent(context), false, "detached form");
""",
        ],
    )
    result = _run_node(script)
    assert result.returncode == 0, result.stderr


def test_paid_preflight_drops_a_result_after_same_sku_form_replacement() -> None:
    script = "\n".join(
        [
            "import assert from 'node:assert/strict';",
            _top_level_function("captureGenerationRequestContext"),
            _top_level_function("generationRequestIdentityIsCurrent"),
            _top_level_function("generationRequestContextIsCurrent"),
            _top_level_function("generationPreflightContextIsCurrent"),
            _top_level_function("runGenerationPreflight"),
            """
const REAL_GENERATION_SOFT_TIMEOUT_MS = 30_000;
const GENERATION_PREFLIGHT_READY_TTL_MS = 30_000;
const GENERATION_PREFLIGHT_ERROR_COOLDOWN_MS = 1_000;
let resolveProvider;
const providerResult = new Promise((resolve) => { resolveProvider = resolve; });
let providerCalls = 0;
const state = {
  dataEpoch: 3,
  user: { id: "employee-a" },
  route: { path: "/workspace/generation" },
  api: {
    realGenerationPreflight() {
      providerCalls += 1;
      return providerResult;
    },
  },
  generationPreflight: { entries: new Map(), requestId: 0 },
};
let activeProjectId = "project-a";
const sku = { model: "seedance-2-fast", durationSeconds: 8 };
const originalForm = { isConnected: true, sku };
const replacementForm = { isConnected: true, sku: { ...sku } };
let renderedForm = originalForm;
const document = {
  querySelector(selector) {
    assert.equal(selector, "#mock-batch-form");
    return renderedForm;
  },
};
const uiForms = [];
function currentWorkspaceProjectId() { return activeProjectId; }
function generationSkuForForm(form) { return form?.sku || null; }
function generationPreflightKey(value) {
  return value ? `${value.model}:${value.durationSeconds}` : "";
}
function generationPreflightDecision() { return "refresh"; }
function clearGenerationPreflightRetry() {}
function syncGenerationPreflightUi(form) { uiForms.push(form); }
function syncCurrentGenerationPreflightUi() {}
function validateGenerationPreflight() { return { ready: true }; }
function withUiTimeout(promise) { return promise; }
function actionErrorMessage(error) { return String(error?.message || error); }
function generationPreflightErrorCode() { return "provider_preflight_failed"; }
function generationPreflightRetryDelay() { return null; }
function queueGenerationPreflightRetry() {
  throw new Error("a stale preflight must never enter retry scheduling");
}

const key = generationPreflightKey(sku);
const pending = runGenerationPreflight(originalForm, { force: true });
await Promise.resolve();
assert.equal(providerCalls, 1);
renderedForm = replacementForm;
resolveProvider({ preflight: { ready: true } });
const outcome = await pending;

assert.deepEqual(outcome, { ok: false, stale: true });
assert.equal(state.generationPreflight.entries.has(key), false);
assert.deepEqual(uiForms, [originalForm]);
""",
        ],
    )
    result = _run_node(script)
    assert result.returncode == 0, result.stderr


def test_paid_start_rechecks_exact_context_at_every_paid_boundary() -> None:
    submit = _top_level_function("submitRealGeneration")
    assert "captureGenerationRequestContext(form, projectId)" in submit

    spec_call = submit.index("await ensurePreparedGenerationSpecForPaidStart(form)")
    preflight_call = submit.index(
        "await runGenerationPreflightForPaidStart(",
        spec_call,
    )
    provider_call = submit.index("state.api.startRealGeneration(payload)", preflight_call)
    guard = "if (!paidLaunchIsCurrent()) return;"
    guard_positions = [match.start() for match in re.finditer(re.escape(guard), submit)]

    assert any(spec_call < position < preflight_call for position in guard_positions)
    after_preflight = [
        position for position in guard_positions
        if preflight_call < position < provider_call
    ]
    assert len(after_preflight) >= 2
    last_guard = after_preflight[-1]
    assert "await " not in submit[last_guard:provider_call]

    finalizer = submit[submit.index("} finally {") :]
    assert 'document.querySelector("#mock-batch-form")' not in finalizer
    assert "paidLaunchIsCurrent()" in finalizer
    assert "const renderedForm = launchContext.form;" in finalizer
    assert "paidLaunchIdentityIsCurrent()" in finalizer
    assert "state.realGenerationStartRequestId === startRequestId" in finalizer
    assert "scheduleRealGenerationPolling(500)" in finalizer


def test_late_paid_success_never_persists_or_resets_a_replaced_form() -> None:
    submit = _top_level_function("submitRealGeneration")
    timeout = submit.index("if (firstWait.timedOut)")
    result_guard = submit.index("if (!paidLaunchIdentityIsCurrent()) return;", timeout)
    success = submit[result_guard : submit.index("} catch (error) {", result_guard)]

    assert "const launchFormStillCurrent = paidLaunchIsCurrent();" in success
    assert success.count("persistGenerationFormDraft(form, { manual: true })") == 1
    guarded_persistence = re.search(
        r"if \(launchFormStillCurrent\) \{(?P<body>[\s\S]*?)\n\s*\}",
        success[success.index("clearContentGenerationHandoff") - 60 :],
    )
    assert guarded_persistence is not None
    guarded_body = guarded_persistence.group("body")
    assert "clearContentGenerationHandoff()" in guarded_body
    assert "clearGenerationRepair()" in guarded_body
    assert "persistGenerationFormDraft(form, { manual: true })" in guarded_body
    assert "if (launchFormStillCurrent) resetGenerationSpecState();" in success

    failure = submit[
        submit.index("} catch (error) {", result_guard) : submit.index("} finally {")
    ]
    assert "providerStartAttempted && paidLaunchIsCurrent()" in failure
    assert "resetGenerationSpecState();" in failure


def test_paid_preflight_is_owned_by_the_original_form_and_route() -> None:
    preflight = _top_level_function("runGenerationPreflight")
    capture = re.search(
        r"const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
        r"captureGenerationRequestContext\(form(?:,\s*[^)]*)?\);",
        preflight,
    )
    assert capture is not None
    context_name = capture.group("name")
    assert preflight.count(
        f"generationPreflightContextIsCurrent({context_name}, key)",
    ) >= 2
    assert "generationSkuForForm(currentForm)" not in preflight
    finalizer = preflight[preflight.index("} finally {") :]
    assert "generationPreflightContextIsCurrent(" in finalizer
    assert context_name in finalizer
    assert "state.generationPreflight.entries.delete(key)" in finalizer
    assert "syncCurrentGenerationPreflightUi(key)" not in finalizer


def test_paid_api_rechecks_the_captured_actor_before_edge_transport() -> None:
    start = API[
        API.index("  startRealGeneration(batch)") :
        API.index("  realGenerationPreflight(")
    ]
    invoke = API[
        API.index("  async invokeRealGeneration(action, payload = {})") :
        API.index("  recordMetric(snapshot)")
    ]

    assert "takeRealGenerationClientContext(batch)" in start
    assert "bindRealGenerationClientContext(invocationPayload, clientContext)" in start
    assert 'invokeRealGeneration("start", invocationPayload)' in start
    assert "takeRealGenerationClientContext(payload)" in invoke
    mismatch = invoke.index("if (expectedActorId && actorId !== expectedActorId)")
    context_check = invoke.index('typeof isContextCurrent === "function"')
    key_write = invoke.index("writeMutationKeys(this.mutationKeys)")
    edge_invoke = invoke.index("this.supabase.functions.invoke")
    assert mismatch < context_check < key_write < edge_invoke
    scoped_payload = invoke[
        invoke.index("const scopedPayload =") : invoke.index("const fingerprint =")
    ]
    assert "...payload" in scoped_payload


def test_paid_api_actor_mismatch_never_invokes_edge_or_writes_a_key() -> None:
    actor_a = "11111111-1111-4111-8111-111111111111"
    actor_b = "22222222-2222-4222-8222-222222222222"
    organization_id = "33333333-3333-4333-8333-333333333333"
    script = f"""
import assert from 'node:assert/strict';
const {{ CreatorApi }} = await import({json.dumps((ROOT / "web/app/supabase-api.js").as_uri())});
const stored = [];
globalThis.window = {{
  sessionStorage: {{
    getItem() {{ return null; }},
    setItem(key, value) {{ stored.push([key, value]); }},
  }},
}};

let actorId = {json.dumps(actor_b)};
let contextCurrent = true;
const edgeBodies = [];
const api = Object.create(CreatorApi.prototype);
api.organizationId = {json.dumps(organization_id)};
api.mutationKeys = {{}};
api.supabase = {{
  auth: {{
    async getSession() {{
      return {{
        data: {{ session: {{ access_token: 'token', user: {{ id: actorId }} }} }},
        error: null,
      }};
    }},
  }},
  functions: {{
    async invoke(_name, request) {{
      edgeBodies.push(request.body);
      return {{
        data: {{
          job: {{
            id: '44444444-4444-4444-8444-444444444444',
            status: 'queued',
          }},
        }},
        error: null,
      }};
    }},
  }},
}};

await assert.rejects(
  (() => {{
    const payload = {{
      project_id: '55555555-5555-4555-8555-555555555555',
    }};
    api.bindRealGenerationClientContext(payload, {{
      expectedActorId: {json.dumps(actor_a)},
      isContextCurrent: () => contextCurrent,
    }});
    return api.invokeRealGeneration('start', payload);
  }})(),
  (error) => error?.code === 'auth_session_changed',
);
assert.equal(edgeBodies.length, 0);
assert.deepEqual(api.mutationKeys, {{}});
assert.deepEqual(stored, []);

actorId = {json.dumps(actor_a)};
contextCurrent = false;
await assert.rejects(
  (() => {{
    const payload = {{
      project_id: '55555555-5555-4555-8555-555555555555',
    }};
    api.bindRealGenerationClientContext(payload, {{
      expectedActorId: {json.dumps(actor_a)},
      isContextCurrent: () => contextCurrent,
    }});
    return api.invokeRealGeneration('start', payload);
  }})(),
  (error) => error?.code === 'real_generation_context_changed',
);
assert.equal(edgeBodies.length, 0);
assert.deepEqual(api.mutationKeys, {{}});
assert.deepEqual(stored, []);

contextCurrent = true;
const matchingPayload = {{
  project_id: '55555555-5555-4555-8555-555555555555',
}};
api.bindRealGenerationClientContext(matchingPayload, {{
  expectedActorId: {json.dumps(actor_a)},
  isContextCurrent: () => contextCurrent,
}});
const result = await api.invokeRealGeneration('start', matchingPayload);
assert.equal(result.job.status, 'queued');
assert.equal(edgeBodies.length, 1);
assert.equal('expectedActorId' in edgeBodies[0], false);
"""
    result = _run_node(script)
    assert result.returncode == 0, result.stderr


def test_generation_spec_reads_validate_only_the_exact_reference_object() -> None:
    for method, next_method in (
        ("generationSpecStatus", "prepareGenerationSpec"),
        ("generationSpecEffectivePolicy", "savePracticalProject"),
    ):
        block = API[
            API.index(f"  {method}(") :
            API.index(f"  {next_method}(", API.index(f"  {method}("))
        ]
        assert "normalizeGenerationSpecReference({" in block
        assert "spec_id: context.spec_id" in block
        assert "spec_version: context.spec_version" in block
        assert "spec_hash: context.spec_hash" in block
        assert "normalizeGenerationSpecReference(context)" not in block


def test_generation_spec_response_uses_an_exact_expected_reference() -> None:
    refresh = APP[
        APP.index("async function refreshGenerationSpec") :
        APP.index("function generationSpecResearchId")
    ]
    assert "const expectedContext = {" in refresh
    assert "project_id: requireWorkspaceProjectId(),\n    ...expectedContext," in refresh
    assert "expectedContext,\n    });" in refresh
    assert "expectedContext: context" not in refresh
