from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "web/app/supabase-api.js"
API = API_PATH.read_text(encoding="utf-8")


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy API bridge tests")
    return subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_named_bridge_methods_use_only_the_existing_edge_transport() -> None:
    for method, action in (
        ("probeGenerationStrategyMedia", "strategy_media_probe"),
        ("preflightGenerationStrategy", "strategy_preflight"),
        ("startGenerationStrategy", "strategy_start"),
        ("generationStrategyStatus", "strategy_status"),
    ):
        start = API.index(f"  {method}(request = {{}})")
        end = API.index("\n  }", start) + len("\n  }")
        block = API[start:end]
        assert f'this.invokeRealGeneration("{action}", request)' in block
        assert "fetch(" not in block
        assert "supabase.functions.invoke" not in block

    assert "GENERATION_STRATEGY_EDGE_ACTIONS" in API
    for action in (
        "strategy_media_probe",
        "strategy_bind",
        "strategy_preflight",
        "strategy_start",
        "strategy_status",
    ):
        assert f'"{action}"' in API


def test_exact_runtime_requests_preserve_idempotency_and_public_shapes() -> None:
    script = f"""
import assert from 'node:assert/strict';
const {{ CreatorApi }} = await import({json.dumps(API_PATH.as_uri())});
globalThis.window = {{
  sessionStorage: {{
    getItem() {{ return null; }},
    setItem() {{ throw new Error('runtime-owned keys must not touch session storage'); }},
  }},
}};

const ids = {{
  actor: '11111111-1111-4111-8111-111111111111',
  organization: '22222222-2222-4222-8222-222222222222',
  project: '33333333-3333-4333-8333-333333333333',
  media: '44444444-4444-4444-8444-444444444444',
  spec: '55555555-5555-4555-8555-555555555555',
  binding: '66666666-6666-4666-8666-666666666666',
  receipt: '77777777-7777-4777-8777-777777777777',
  campaign: '88888888-8888-4888-8888-888888888888',
  job: '99999999-9999-4999-8999-999999999999',
}};
const hash = (character) => character.repeat(64);
const responses = {{
  strategy_media_probe: {{
    ok: true,
    version: 'generation-strategy-media-probe-response-v1',
    media_id: ids.media,
    duration_seconds: 8,
    verified_at: '2026-08-14T12:00:00.000Z',
    replay: false,
  }},
  strategy_bind: {{
    ok: true,
    version: 'generation-strategy-resolve-bind-response-v1',
    binding: {{}}, selection: {{}}, price: {{}}, contract: {{}},
  }},
  strategy_preflight: {{
    ok: true,
    version: 'generation-strategy-preflight-response-v1',
    replay: false,
    receipt: {{}}, provider_preflight: {{}}, launch_enabled: true, contract: {{}},
  }},
  strategy_start: {{
    ok: true,
    version: 'generation-strategy-status-response-v1',
    job: {{}}, strategy: {{}}, selection: {{}}, price: {{}}, dispatch: null,
    reconciliation: null, output: null, error: null, contract: {{}},
  }},
  strategy_status: {{
    ok: true,
    version: 'generation-strategy-status-response-v1',
    job: {{}}, strategy: {{}}, selection: {{}}, price: {{}}, dispatch: {{}},
    reconciliation: null, output: null,
    error: {{code: 'provider_failed', provider_billing_outcome: 'unknown'}},
    contract: {{}},
  }},
}};
const bodies = [];
const supabase = {{
  schema() {{ return {{ rpc() {{ throw new Error('RPC is not used'); }} }}; }},
  auth: {{
    async getSession() {{
      return {{
        data: {{session: {{access_token: 'access-token', user: {{id: ids.actor}}}}}},
        error: null,
      }};
    }},
  }},
  functions: {{
    async invoke(name, options) {{
      assert.equal(name, 'creator-generate');
      bodies.push(options.body);
      return {{data: structuredClone(responses[options.body.action]), error: null}};
    }},
  }},
}};
const api = new CreatorApi(supabase, {{
  RPC_SCHEMA: 'public', STORAGE_BUCKET: 'media', REAL_GENERATION_ENABLED: true,
}});
api.organizationId = ids.organization;

const probe = {{
  action: 'strategy_media_probe', organization_id: ids.organization,
  project_id: ids.project, media_id: ids.media, confirmation: true,
  idempotency_key: 'probe:44444444-4444-4444-8444-444444444444',
}};
const bind = {{
  action: 'strategy_bind', organization_id: ids.organization,
  project_id: ids.project, spec_id: ids.spec, spec_version: 7,
  spec_hash: hash('a'), generation_strategy: {{}}, confirmation: true,
  idempotency_key: 'bind:55555555-5555-4555-8555-555555555555',
}};
const preflight = {{
  action: 'strategy_preflight', organization_id: ids.organization,
  project_id: ids.project, spec_id: ids.spec, spec_version: 7,
  spec_hash: hash('a'), binding_id: ids.binding, binding_hash: hash('b'),
  selection_hash: hash('c'), price_hash: hash('d'),
  spend_confirmation: 'RUNWAY_PRODUCT_UGC_8S_720P_SILENT_USD_12.00',
  confirmation: true,
  idempotency_key: 'preflight:66666666-6666-4666-8666-666666666666',
}};
const status = {{
  action: 'strategy_status', organization_id: ids.organization,
  project_id: ids.project, generation_job_id: ids.job,
}};

assert.deepEqual(await api.probeGenerationStrategyMedia(probe), responses.strategy_media_probe);
assert.deepEqual(await api.bindGenerationStrategy(bind), responses.strategy_bind);
assert.deepEqual(await api.preflightGenerationStrategy(preflight), responses.strategy_preflight);
assert.deepEqual(await api.generationStrategyStatus(status), responses.strategy_status);
assert.deepEqual(bodies, [probe, bind, preflight, status]);
assert.deepEqual(api.mutationKeys, {{}});
"""
    result = _run_node(script)
    assert result.returncode == 0, result.stderr


def test_paid_strategy_start_requires_one_bound_actor_context_and_keeps_key() -> None:
    script = f"""
import assert from 'node:assert/strict';
const {{ CreatorApi }} = await import({json.dumps(API_PATH.as_uri())});
const storageWrites = [];
globalThis.window = {{
  sessionStorage: {{
    getItem() {{ return null; }},
    setItem(key, value) {{ storageWrites.push([key, value]); }},
  }},
}};
const actor = '11111111-1111-4111-8111-111111111111';
const organization = '22222222-2222-4222-8222-222222222222';
const project = '33333333-3333-4333-8333-333333333333';
const spec = '44444444-4444-4444-8444-444444444444';
const binding = '55555555-5555-4555-8555-555555555555';
const receipt = '66666666-6666-4666-8666-666666666666';
const campaign = '77777777-7777-4777-8777-777777777777';
const hash = (character) => character.repeat(64);
const calls = [];
const response = {{
  ok: true, version: 'generation-strategy-status-response-v1',
  job: {{}}, strategy: {{}}, selection: {{}}, price: {{}}, dispatch: null,
  reconciliation: null, output: null, error: null, contract: {{}},
}};
const supabase = {{
  schema() {{ return {{rpc() {{}}}}; }},
  auth: {{async getSession() {{
    return {{data: {{session: {{access_token: 'token', user: {{id: actor}}}}}}, error: null}};
  }}}},
  functions: {{async invoke(_name, options) {{
    calls.push(options.body);
    return {{data: structuredClone(response), error: null}};
  }}}},
}};
const api = new CreatorApi(supabase, {{
  RPC_SCHEMA: 'public', STORAGE_BUCKET: 'media', REAL_GENERATION_ENABLED: true,
}});
api.organizationId = organization;
const request = {{
  action: 'strategy_start', organization_id: organization,
  project_id: project, spec_id: spec, spec_version: 9, spec_hash: hash('a'),
  binding_id: binding, binding_hash: hash('b'), selection_hash: hash('c'),
  price_hash: hash('d'),
  spend_confirmation: 'RUNWAY_PRODUCT_AD_9S_1080P_AUDIO_USD_99.00',
  confirmation: true, receipt_id: receipt, receipt_hash: hash('e'),
  campaign_id: campaign,
  idempotency_key: 'start:77777777-7777-4777-8777-777777777777',
}};

await assert.rejects(
  api.startGenerationStrategy(request),
  (error) => error?.code === 'auth_session_changed',
);
assert.equal(calls.length, 0);

let current = true;
api.bindRealGenerationClientContext(request, {{
  expectedActorId: actor,
  isContextCurrent: () => current,
}});
assert.deepEqual(await api.startGenerationStrategy(request), response);
assert.equal(calls.length, 1);
assert.deepEqual(calls[0], request);
assert.equal(calls[0].idempotency_key, request.idempotency_key);
assert.deepEqual(api.mutationKeys, {{}});
assert.deepEqual(storageWrites, []);

await assert.rejects(
  api.startGenerationStrategy(request),
  (error) => error?.code === 'auth_session_changed',
);
assert.equal(calls.length, 1);
"""
    result = _run_node(script)
    assert result.returncode == 0, result.stderr


def test_bridge_rejects_scope_drift_extra_keys_and_non_public_envelopes() -> None:
    script = f"""
import assert from 'node:assert/strict';
const {{ CreatorApi }} = await import({json.dumps(API_PATH.as_uri())});
globalThis.window = {{sessionStorage: {{getItem() {{return null;}}, setItem() {{}}}}}};
const actor = '11111111-1111-4111-8111-111111111111';
const organization = '22222222-2222-4222-8222-222222222222';
const project = '33333333-3333-4333-8333-333333333333';
const media = '44444444-4444-4444-8444-444444444444';
let response = {{
  ok: true, version: 'generation-strategy-media-probe-response-v1',
  media_id: media, duration_seconds: 8,
  verified_at: '2026-08-14T12:00:00.000Z', replay: false,
}};
const calls = [];
const supabase = {{
  schema() {{ return {{rpc() {{}}}}; }},
  auth: {{async getSession() {{
    return {{data: {{session: {{access_token: 'token', user: {{id: actor}}}}}}, error: null}};
  }}}},
  functions: {{async invoke(_name, options) {{
    calls.push(options.body);
    return {{data: structuredClone(response), error: null}};
  }}}},
}};
const api = new CreatorApi(supabase, {{
  RPC_SCHEMA: 'public', STORAGE_BUCKET: 'media', REAL_GENERATION_ENABLED: true,
}});
api.organizationId = organization;
const exact = {{
  action: 'strategy_media_probe', organization_id: organization,
  project_id: project, media_id: media, confirmation: true,
  idempotency_key: 'probe:44444444-4444-4444-8444-444444444444',
}};

await assert.rejects(
  api.probeGenerationStrategyMedia({{...exact, organization_id: project}}),
  (error) => error?.code === 'generation_strategy_request_invalid',
);
await assert.rejects(
  api.probeGenerationStrategyMedia({{...exact, signed_url: 'https://forbidden.invalid'}}),
  (error) => error?.code === 'generation_strategy_request_invalid',
);
assert.equal(calls.length, 0);

response = {{...response, signed_url: 'https://forbidden.invalid'}};
await assert.rejects(
  api.probeGenerationStrategyMedia(exact),
  (error) => error?.code === 'generation_strategy_response_invalid',
);
assert.equal(calls.length, 1);

response = {{ok: false, code: 'generation_strategy_binding_invalid'}};
await assert.rejects(
  api.probeGenerationStrategyMedia(exact),
  (error) => error?.code === 'generation_strategy_binding_invalid',
);
assert.equal(calls.length, 2);
"""
    result = _run_node(script)
    assert result.returncode == 0, result.stderr
