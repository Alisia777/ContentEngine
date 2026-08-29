from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web/app/app.js"
API = ROOT / "web/app/supabase-api.js"
EDGE = ROOT / "supabase/functions/creator-generate/index.ts"
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608200003_generation_reconciliation_fal_provider_v1.sql"
)


def _slice(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


def _run_node(script: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser contract tests")
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "reconciliation-contract.mjs"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout


def test_append_only_sql_binds_confirmation_to_signed_route_and_rejects_null() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert MIGRATION.name.startswith("202608200003_")
    assert "generation_strategy_reconciliation_confirmation_allowed" in sql
    for required_type in (
        "jsonb_typeof(p_payload -> 'version') <> 'string'",
        "jsonb_typeof(p_payload -> 'resolution') <> 'string'",
        "jsonb_typeof(p_payload -> 'external_evidence_hash') <> 'string'",
        "jsonb_typeof(p_payload -> 'confirmation') <> 'string'",
        "jsonb_typeof(p_payload -> 'idempotency_key') <> 'string'",
    ):
        assert required_type in sql
    assert "receipt.id = claim_row.readiness_receipt_id" in sql
    assert "receipt.receipt_hash = claim_row.receipt_hash" in sql
    assert "receipt_row.provider is distinct from job_row.provider" in sql
    assert "provider_status_value is null" in sql
    assert "FAL_REQUEST_ID_VERIFIED" in sql
    assert "FAL_NO_REQUEST_VERIFIED" in sql
    assert "RUNWAY_TASK_ID_VERIFIED" in sql
    assert "RUNWAY_NO_TASK_VERIFIED" in sql
    assert "fal_request_epoch_ms_value" in sql
    assert "starting_at_value - interval ''2 minutes''" in sql
    assert "starting_at_value + interval ''10 minutes''" in sql


def test_edge_reconcile_is_route_aware_and_keeps_runway_get_unchanged() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    parser = _slice(
        edge,
        "function readGenerationStrategyReconcilePayload",
        "function readStrategySpendConfirmation",
    )
    handler = _slice(
        edge,
        "const handleGenerationStrategyReconciliation",
        "const strategyStartPayload",
    )

    for token in (
        "FAL_REQUEST_ID_VERIFIED",
        "FAL_NO_REQUEST_VERIFIED",
        "RUNWAY_TASK_ID_VERIFIED",
        "RUNWAY_NO_TASK_VERIFIED",
    ):
        assert token in parser
        assert token in handler
    assert "loadGenerationStrategyJobRoute" in handler
    # Маршрут проверяется на пустоту ОТДЕЛЬНО, до разбора провайдера. Раньше
    # это выражалось косвенно — `route?.provider` давал null-подтверждение и
    # тот же 409, — но связь была видна только человеку, и весь остаток ветки
    # читался как «маршрут может быть пустым».
    assert "if (route === null) {" in handler
    assert 'route.provider === "fal"' in handler
    assert 'route.provider === "runway"' in handler
    assert "expectedConfirmation === null" in handler
    assert "strategyReconciliationActorAllowed" in handler
    assert handler.index("strategyReconciliationActorAllowed") < handler.index(
        "fetchProviderJsonWithDeadline"
    )
    assert "`${RUNWAY_API_ORIGIN}/v1/tasks/${payload.provider_task_id}`" in handler
    assert "const createdAt = falRequestCreatedAt(requestId)" in handler
    assert "falQueueUrlCandidates" in handler


def test_browser_unknown_provider_has_no_reconciliation_form_or_runway_fallback() -> None:
    app = APP.read_text(encoding="utf-8")
    function_source = _slice(
        app,
        "function generationActionsMarkup(details)",
        "function generationCostMarkup(details)",
    )
    # Запись 29.08.2026: харнесс сдвинут ОСОЗНАННО — generationActionsMarkup
    # теперь дописывает ссылку «Открыть паспорт» через внешнюю
    # generationPassportLinkMarkup; тесту паспорт не нужен, поэтому подаём
    # заглушку () => ''.
    script = f"""
import assert from 'node:assert/strict';
const factory = new Function(
  'escapeHtml',
  'generationPassportLinkMarkup',
  {json.dumps(function_source + '; return generationActionsMarkup;')}
);
const render = factory((value) => String(value), () => '');
const base = {{
  jobId: '44444444-4444-4444-8444-444444444444',
  reconciliationRequired: true,
  canReconcile: true,
  reconciliationIncidentId: '55555555-5555-4555-8555-555555555555',
  strategy: true,
}};
const unknown = render({{...base, provider: 'future-provider'}});
assert.match(unknown, /Сервис сверки не подтверждён/u);
assert.doesNotMatch(unknown, /generation-reconciliation-form/u);
assert.doesNotMatch(unknown, /Runway/u);
const fal = render({{...base, provider: 'fal'}});
assert.match(fal, /generation-reconciliation-form/u);
assert.match(fal, /data-provider="fal"/u);
    assert.match(fal, /fal request ID \\(UUIDv7\\)/u);
assert.doesNotMatch(fal, /Runway task ID/u);
const runway = render({{...base, provider: 'runway'}});
assert.match(runway, /data-provider="runway"/u);
assert.match(runway, /Runway task ID/u);
"""
    _run_node(script)


def test_strategy_api_emits_exact_runway_and_fal_confirmations() -> None:
    script = (
        "import assert from 'node:assert/strict';\n"
        + "const { CreatorApi } = await import("
        + json.dumps(API.as_uri())
        + ");\n"
        + r"""
globalThis.window = {
  sessionStorage: { getItem() { return null; }, setItem() {} },
};
const actor = '11111111-1111-4111-8111-111111111111';
const organization = '22222222-2222-4222-8222-222222222222';
const project = '33333333-3333-4333-8333-333333333333';
const job = '44444444-4444-4444-8444-444444444444';
const dispatch = '55555555-5555-4555-8555-555555555555';
const incident = '66666666-6666-4666-8666-666666666666';
const response = {
  ok: true, version: 'generation-strategy-status-response-v1',
  job: {}, strategy: {}, selection: {}, price: {}, dispatch: {},
  reconciliation: {}, output: null, error: null, contract: {},
};
const calls = [];
const supabase = {
  schema() { return { rpc() {} }; },
  auth: { async getSession() {
    return { data: { session: {
      access_token: 'token', user: { id: actor },
    } }, error: null };
  } },
  functions: { async invoke(name, options) {
    assert.equal(name, 'creator-generate');
    calls.push(options.body);
    return { data: structuredClone(response), error: null };
  } },
};
const api = new CreatorApi(supabase, {
  RPC_SCHEMA: 'public', STORAGE_BUCKET: 'media', REAL_GENERATION_ENABLED: true,
});
api.organizationId = organization;
const base = {
  project_id: project,
  dispatch_result_id: dispatch,
  incident_id: incident,
  evidence_reference: 'Provider dashboard, full checked interval',
  reason: 'Проверены точные модель, товар и время запуска в панели провайдера.',
};

await api.reconcileGenerationStrategy(job, {
  ...base, provider: 'runway', resolution: 'attach_existing_task',
  provider_task_id: 'runway-task-77',
});
assert.equal(calls[0].confirmation, 'RUNWAY_TASK_ID_VERIFIED');
assert.equal(calls[0].provider_task_id, 'runway-task-77');

await api.reconcileGenerationStrategy(job, {
  ...base, provider: 'runway', resolution: 'confirm_no_submission',
});
assert.equal(calls[1].confirmation, 'RUNWAY_NO_TASK_VERIFIED');
assert.ok(!('provider_task_id' in calls[1]));

const falRequest = '01912345-6789-7abc-8def-0123456789ab';
await api.reconcileGenerationStrategy(job, {
  ...base, provider: 'fal', resolution: 'attach_existing_task',
  provider_task_id: falRequest,
});
assert.equal(calls[2].confirmation, 'FAL_REQUEST_ID_VERIFIED');
assert.equal(calls[2].provider_task_id, falRequest);

await api.reconcileGenerationStrategy(job, {
  ...base, provider: 'fal', resolution: 'confirm_no_submission',
});
assert.equal(calls[3].confirmation, 'FAL_NO_REQUEST_VERIFIED');
assert.ok(!('provider_task_id' in calls[3]));

assert.throws(
  () => api.reconcileGenerationStrategy(job, {
    ...base, provider: 'future-provider', resolution: 'confirm_no_submission',
  }),
  (error) => error?.code === 'generation_reconciliation_provider_invalid',
);
assert.throws(
  () => api.reconcileGenerationStrategy(job, {
    ...base, provider: 'fal', resolution: 'attach_existing_task',
    provider_task_id: 'runway-task-77',
  }),
  (error) => error?.code === 'generation_reconciliation_task_id_invalid',
);
assert.equal(calls.length, 4);
"""
    )
    _run_node(script)


def test_strategy_reconciliation_forbidden_has_an_exact_friendly_message() -> None:
    api = API.read_text(encoding="utf-8")
    assert (
        "generation_strategy_reconciliation_forbidden: "
        '"Ручную сверку запуска стратегии может выполнить только владелец '
        'или администратор команды."'
    ) in api
