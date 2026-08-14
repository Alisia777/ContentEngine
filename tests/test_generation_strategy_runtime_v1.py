from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_MODULE = ROOT / "web/app/generation-strategy-runtime.js"
RUNTIME_SOURCE = RUNTIME_MODULE.read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy runtime contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "runtime.mjs").write_text(RUNTIME_SOURCE, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as runtime from './runtime.mjs';\n"
            "const clone = (value) => JSON.parse(JSON.stringify(value));\n"
            "const ids = Object.freeze({\n"
            "  organization: '11111111-1111-4111-8111-111111111111',\n"
            "  project: '22222222-2222-4222-8222-222222222222',\n"
            "  spec: '33333333-3333-4333-8333-333333333333',\n"
            "  product: '44444444-4444-4444-8444-444444444444',\n"
            "  sourceMedia: '99999999-9999-4999-8999-999999999999',\n"
            "  avatar: '55555555-5555-4555-8555-555555555555',\n"
            "  productMedia: '66666666-6666-4666-8666-666666666666',\n"
            "  sourceBinding: '77777777-7777-4777-8777-777777777777',\n"
            "  binding: '88888888-8888-4888-8888-888888888888',\n"
            "  receipt: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',\n"
            "  campaign: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',\n"
            "  otherCampaign: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',\n"
            "  job: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',\n"
            "  batch: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',\n"
            "  output: 'ffffffff-ffff-4fff-8fff-ffffffffffff',\n"
            "  dispatch: '12121212-1212-4121-8121-121212121212',\n"
            "  incident: '13131313-1313-4131-8131-131313131313',\n"
            "});\n"
            "const hashes = Object.freeze({\n"
            "  spec: 'a'.repeat(64), source: 'b'.repeat(64), selection: 'c'.repeat(64),\n"
            "  avatar: 'd'.repeat(64), product: 'e'.repeat(64),\n"
            "  snapshot: '1'.repeat(64), binding: '2'.repeat(64), price: '3'.repeat(64),\n"
            "  receipt: '4'.repeat(64), prompt: '5'.repeat(64), dispatch: '6'.repeat(64),\n"
            "});\n"
            "const context = () => ({\n"
            "  organization_id: ids.organization, project_id: ids.project,\n"
            "  spec_id: ids.spec, spec_version: 7, spec_hash: hashes.spec,\n"
            "  generation_strategy: {\n"
            "    version: '2026-08-14.v1', strategy_id: 'viral_avatar_ugc',\n"
            "    recipe_version: '2026-06', duration_seconds: 4, ratio: '720:1280',\n"
            "    audio: false,\n"
            "    assets: [\n"
            "      {role: 'source_video', media_id: ids.sourceMedia},\n"
            "      {role: 'avatar_image', media_id: ids.avatar},\n"
            "      {role: 'product_image', media_id: ids.productMedia},\n"
            "    ],\n"
            "    attestations: {\n"
            "      source_media_rights_confirmed: true,\n"
            "      transformative_use_confirmed: true,\n"
            "      product_assets_rights_confirmed: true,\n"
            "      depicted_people_consent_confirmed: true,\n"
            "      avatar_likeness_consent_confirmed: true,\n"
            "    },\n"
            "  },\n"
            "});\n"
            "const preflightResponse = () => ({\n"
            "  ok: true, version: 'generation-strategy-preflight-response-v1', replay: false,\n"
            "  receipt: {\n"
            "    id: ids.receipt, receipt_hash: hashes.receipt, binding_id: ids.binding,\n"
            "    binding_hash: hashes.binding, strategy_id: 'viral_avatar_ugc',\n"
            "    recipe: 'product_ugc', catalog_version: '2026-08-14.v1',\n"
            "    recipe_version: '2026-06',\n"
            "    pricing_version: 'runway-recipe-credits-2026-08-14.v1',\n"
            "    selection_hash: hashes.selection, price_hash: hashes.price, ready: true,\n"
            "    failure_code: null, checked_at: '2026-08-14T08:01:00.000Z',\n"
            "    expires_at: '2026-08-14T08:06:00.000Z',\n"
            "  },\n"
            "  provider_preflight: {\n"
            "    credential_configured: true, provider_authentication_confirmed: true,\n"
            "    recipe_catalog_supported: true, recipe_precheck_supported: false,\n"
            "    recipe_available: null, balance_sufficient: true,\n"
            "    daily_quota_precheck_supported: false, daily_quota_available: null,\n"
            "  },\n"
            "  launch_enabled: true, contract: {\n"
            "    provider_call_started: false, receipt_single_use: true,\n"
            "    browser_price_authority: false, browser_prompt_authority: false,\n"
            "  },\n"
            "});\n"
            "const refreshedPreflightResponse = () => {\n"
            "  const response = preflightResponse();\n"
            "  response.receipt.id = 'abababab-abab-4bab-8bab-abababababab';\n"
            "  response.receipt.receipt_hash = '7'.repeat(64);\n"
            "  response.receipt.checked_at = '2026-08-14T08:10:00.000Z';\n"
            "  response.receipt.expires_at = '2026-08-14T08:20:00.000Z';\n"
            "  return response;\n"
            "};\n"
            "const statusResponse = (jobStatus = 'submitted', updatedAt = '2026-08-14T08:03:00.000Z') => {\n"
            "  const providerStatuses = new Set(['submitted','processing','succeeded','failed','cancelled']);\n"
            "  const providerStatus = providerStatuses.has(jobStatus) ? jobStatus : null;\n"
            "  const hasProvider = providerStatus !== null;\n"
            "  const response = {\n"
            "    ok: true, version: 'generation-strategy-status-response-v1',\n"
            "    job: {id: ids.job, batch_id: ids.batch, project_id: ids.project,\n"
            "      campaign_id: ids.campaign, status: jobStatus, provider_status: providerStatus,\n"
            "      provider_task_id: hasProvider ? 'runway-task-fixed-001' : null,\n"
            "      estimated_cost_minor: 192, actual_cost_minor: hasProvider ? 192 : null,\n"
            "      currency: 'USD', created_at: '2026-08-14T08:02:00.000Z',\n"
            "      updated_at: updatedAt},\n"
            "    strategy: {version: 'generation-strategy-immutable-execution-v1',\n"
            "      strategy_id: 'viral_avatar_ugc', recipe: 'product_ugc',\n"
            "      catalog_version: '2026-08-14.v1', recipe_version: '2026-06',\n"
            "      pricing_version: 'runway-recipe-credits-2026-08-14.v1',\n"
            "      binding_id: ids.binding, binding_hash: hashes.binding,\n"
            "      receipt_id: ids.receipt, receipt_hash: hashes.receipt,\n"
            "      selection_hash: hashes.selection, price_hash: hashes.price,\n"
            "      strategy_prompt_hash: hashes.prompt},\n"
            "    selection: clone(context().generation_strategy),\n"
            "    price: (() => { const value = clone(bindResponse().price); delete value.spend_confirmation; return value; })(),\n"
            "    dispatch: hasProvider ? {result_id: ids.dispatch, result_hash: hashes.dispatch,\n"
            "      outcome: 'submitted', provider_post_started: true, provider_http_status: 201,\n"
            "      recorded_at: '2026-08-14T08:02:30.000Z'} : null,\n"
            "    reconciliation: null,\n"
            "    output: jobStatus === 'succeeded'\n"
            "      ? {media_id: ids.output, mime_type: 'video/mp4', size_bytes: 4096} : null,\n"
            "    error: ['failed','cancelled'].includes(jobStatus)\n"
            "      ? {code: 'provider_generation_failed', provider_billing_outcome: 'unknown'} : null,\n"
            "    contract: {recipe_aware: true, legacy_model_catalog_used: false,\n"
            "      poll_provider_allowed: ['submitted','processing'].includes(jobStatus),\n"
            "      second_post_allowed: false, object_names_returned: false,\n"
            "      media_hashes_returned: false, signed_urls_returned: false,\n"
            "      manual_human_review_required: jobStatus === 'succeeded'},\n"
            "  };\n"
            "  return response;\n"
            "};\n"
            "const stateThroughBound = () => {\n"
            "  const selected = runtime.reduceGenerationStrategyRuntimeState(\n"
            "    runtime.createGenerationStrategyRuntimeState(),\n"
            "    {type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.select, context: context()},\n"
            "  );\n"
            "  return runtime.reduceGenerationStrategyRuntimeState(selected, {\n"
            "    type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,\n"
            "    fingerprint: selected.fingerprint, context: context(), response: bindResponse(),\n"
            "  });\n"
            "};\n"
            "const stateThroughPreflight = () => {\n"
            "  const bound = stateThroughBound();\n"
            "  return runtime.reduceGenerationStrategyRuntimeState(bound, {\n"
            "    type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightResolved,\n"
            "    fingerprint: bound.fingerprint, response: preflightResponse(),\n"
            "  });\n"
            "};\n"
            "const stateThroughHuman = (campaignId = ids.campaign) => {\n"
            "  const ready = stateThroughPreflight();\n"
            "  return runtime.reduceGenerationStrategyRuntimeState(ready, {\n"
            "    type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.humanConfirmed,\n"
            "    fingerprint: ready.fingerprint, campaign_id: campaignId,\n"
            "    spend_confirmation: bindResponse().price.spend_confirmation, confirmation: true,\n"
            "  });\n"
            "};\n"
            "const stateThroughStartOnce = () => {\n"
            "  const confirmed = stateThroughHuman();\n"
            "  return runtime.reduceGenerationStrategyRuntimeState(confirmed, {\n"
            "    type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested,\n"
            "    fingerprint: confirmed.fingerprint,\n"
            "    start_context_fingerprint: confirmed.start_context_fingerprint,\n"
            "    campaign_id: ids.campaign, idempotency_key: 'strategy.start:fixed-key-1',\n"
            "  });\n"
            "};\n"
            "const bindResponse = () => ({\n"
            "  ok: true, version: 'generation-strategy-resolve-bind-response-v1',\n"
            "  binding: {\n"
            "    id: ids.binding, project_id: ids.project, spec_id: ids.spec,\n"
            "    spec_version: 7, spec_hash: hashes.spec, product_id: ids.product,\n"
            "    strategy_id: 'viral_avatar_ugc', selection_hash: hashes.selection,\n"
            "    source_basis: 'exact_source_video', source_binding_id: ids.sourceBinding,\n"
            "    source_binding_hash: hashes.source,\n"
            "    role_assets: [\n"
            "      {role: 'product_primary', ordinal: 1, media_object_id: ids.productMedia,\n"
            "       sha256: hashes.product, kind: 'product_photo', mime_type: 'image/png',\n"
            "       product_id: ids.product, rights_confirmed: true, likeness_consent: false},\n"
            "      {role: 'creator_avatar', ordinal: 1, media_object_id: ids.avatar,\n"
            "       sha256: hashes.avatar, kind: 'creator_reference', mime_type: 'image/jpeg',\n"
            "       product_id: null, rights_confirmed: true, likeness_consent: true},\n"
            "    ],\n"
            "    strategy_snapshot_hash: hashes.snapshot, binding_hash: hashes.binding,\n"
            "    bound_at: '2026-08-14T08:00:00.000Z',\n"
            "  },\n"
            "  selection: {\n"
            "    catalog_version: '2026-08-14.v1', recipe_version: '2026-06',\n"
            "    pricing_version: 'runway-recipe-credits-2026-08-14.v1',\n"
            "    strategy_id: 'viral_avatar_ugc', recipe: 'product_ugc',\n"
            "    selection_hash: hashes.selection,\n"
            "  },\n"
            "  price: {\n"
            "    version: 'generation-strategy-price-snapshot-v1',\n"
            "    strategy_id: 'viral_avatar_ugc', provider: 'runway', recipe: 'product_ugc',\n"
            "    input_mode: 'character_and_product_images', duration_seconds: 4,\n"
            "    resolution: '720p', ratio: '720:1280', audio: false,\n"
            "    estimated_credits: 192, estimated_pre_tax_usd_minor: 192,\n"
            "    estimated_cost_minor: 192, estimated_cost_usd: '1.92', currency: 'USD',\n"
            "    credit_unit_cost_minor: 1, catalog_version: '2026-08-14.v1',\n"
            "    pricing_version: 'runway-recipe-credits-2026-08-14.v1',\n"
            "    recipe_version: '2026-06',\n"
            "    spend_confirmation: 'RUNWAY_PRODUCT_UGC_4S_720P_SILENT_USD_1.92',\n"
            "    price_hash: hashes.price,\n"
            "  },\n"
            "  contract: {\n"
            "    server_resolved_source_binding: true, server_resolved_media_hashes: true,\n"
            "    browser_hashes_accepted: false, browser_source_binding_accepted: false,\n"
            "    provider_call_started: false, paid_start_integrated: false,\n"
            "    launch_enabled: false,\n"
            "  },\n"
            "});\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_runtime_is_pure_and_has_no_legacy_model_or_side_effect_channel() -> None:
    for forbidden in (
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "fetch(",
        "XMLHttpRequest",
        "Deno.env",
        "process.env",
        "seedance",
        "veo",
        "seedance2_fast",
        "model_identity",
        "/v1/recipes/",
        "RUNWAYML_API_SECRET",
    ):
        assert forbidden not in RUNTIME_SOURCE

    result = _evaluate(
        """
        ({
          exports: Object.keys(runtime).sort(),
          version: runtime.GENERATION_STRATEGY_RUNTIME_VERSION,
          actions: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS,
        })
        """
    )
    assert result["version"] == "2026-08-14.v1"
    assert result["actions"] == {
        "bindResolved": "BIND_RESOLVED",
        "humanConfirmed": "HUMAN_CONFIRMED",
        "invalidate": "INVALIDATE",
        "preflightResolved": "PREFLIGHT_RESOLVED",
        "reset": "RESET",
        "select": "SELECT",
        "startRequested": "START_REQUESTED",
        "startResolved": "START_RESOLVED",
        "statusResolved": "STATUS_RESOLVED",
    }
    assert result["exports"] == [
        "GENERATION_STRATEGY_RUNTIME_ACTIONS",
        "GENERATION_STRATEGY_RUNTIME_VERSION",
        "createGenerationStrategyRuntimeFingerprint",
        "createGenerationStrategyRuntimeState",
        "generationStrategyRuntimeBindRequest",
        "generationStrategyRuntimePreflightRequest",
        "generationStrategyRuntimeProbeRequest",
        "generationStrategyRuntimeSafeProjection",
        "generationStrategyRuntimeStartRequest",
        "generationStrategyRuntimeStatusRequest",
        "invalidateGenerationStrategyRuntimeState",
        "normalizeGenerationStrategyBindResponse",
        "normalizeGenerationStrategyPreflightResponse",
        "normalizeGenerationStrategyProbeResponse",
        "normalizeGenerationStrategyStartResponse",
        "normalizeGenerationStrategyStatusResponse",
        "reduceGenerationStrategyRuntimeState",
    ]


def test_fingerprint_is_canonical_exact_and_does_not_retain_raw_consent() -> None:
    result = _evaluate(
        """
        (() => {
          const first = runtime.createGenerationStrategyRuntimeFingerprint(context());
          const reordered = context();
          reordered.generation_strategy.attestations = {
            avatar_likeness_consent_confirmed: true,
            product_assets_rights_confirmed: true,
            transformative_use_confirmed: true,
            source_media_rights_confirmed: true,
            depicted_people_consent_confirmed: true,
          };
          const second = runtime.createGenerationStrategyRuntimeFingerprint(reordered);
          const changedAssetOrder = context();
          changedAssetOrder.generation_strategy.assets.reverse();
          const third = runtime.createGenerationStrategyRuntimeFingerprint(changedAssetOrder);
          const changedSpec = context(); changedSpec.spec_version = 8;
          const fourth = runtime.createGenerationStrategyRuntimeFingerprint(changedSpec);
          const extra = context(); extra.provider = 'forbidden';
          const invalid = runtime.createGenerationStrategyRuntimeFingerprint(extra);
          const state = runtime.reduceGenerationStrategyRuntimeState(
            runtime.createGenerationStrategyRuntimeState(),
            {type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.select, context: context()},
          );
          const serialized = JSON.stringify(state);
          return {
            first, same: first.fingerprint === second.fingerprint,
            assetOrderChanges: first.fingerprint !== third.fingerprint,
            specChanges: first.fingerprint !== fourth.fingerprint,
            invalid,
            state: {
              phase: state.phase, fingerprint: state.fingerprint,
              frozen: Object.isFrozen(state) && Object.isFrozen(state.identity),
              containsSelection: serialized.includes('generation_strategy') || serialized.includes('attestations'),
              containsSpendConsent: serialized.includes('spend_confirmation') || serialized.includes('confirmation'),
              containsBrowserOutput: serialized.includes('duration_seconds') ||
                serialized.includes('dimension_value') || serialized.includes('audio'),
            },
          };
        })()
        """
    )
    assert result["first"]["ok"] is True
    assert result["first"]["fingerprint"] == hashlib.sha256(
        json.dumps(
            {
                "context": {
                    "generation_strategy": {
                        "assets": [
                            {
                                "media_id": "99999999-9999-4999-8999-999999999999",
                                "role": "source_video",
                            },
                            {
                                "media_id": "55555555-5555-4555-8555-555555555555",
                                "role": "avatar_image",
                            },
                            {
                                "media_id": "66666666-6666-4666-8666-666666666666",
                                "role": "product_image",
                            },
                        ],
                        "attestations": {
                            "avatar_likeness_consent_confirmed": True,
                            "depicted_people_consent_confirmed": True,
                            "product_assets_rights_confirmed": True,
                            "source_media_rights_confirmed": True,
                            "transformative_use_confirmed": True,
                        },
                        "audio": False,
                        "duration_seconds": 4,
                        "ratio": "720:1280",
                        "recipe_version": "2026-06",
                        "strategy_id": "viral_avatar_ugc",
                        "version": "2026-08-14.v1",
                    },
                    "organization_id": "11111111-1111-4111-8111-111111111111",
                    "project_id": "22222222-2222-4222-8222-222222222222",
                    "spec_hash": "a" * 64,
                    "spec_id": "33333333-3333-4333-8333-333333333333",
                    "spec_version": 7,
                },
                "version": "2026-08-14.v1",
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    assert result["same"] is True
    assert result["assetOrderChanges"] is True
    assert result["specChanges"] is True
    assert result["invalid"]["ok"] is False
    assert result["invalid"]["error"] == {
        "code": "object_keys_mismatch",
        "field": "context",
    }
    assert result["state"] == {
        "phase": "selected",
        "fingerprint": result["first"]["fingerprint"],
        "frozen": True,
        "containsSelection": False,
        "containsSpendConsent": False,
        "containsBrowserOutput": False,
    }


def test_bind_request_is_exact_and_carries_no_browser_authority_fields() -> None:
    result = _evaluate(
        """
        (() => {
          const valid = runtime.generationStrategyRuntimeBindRequest(
            context(), 'strategy.bind:fixed-key-1'
          );
          const invalidKey = runtime.generationStrategyRuntimeBindRequest(context(), 'bad key');
          return {
            valid,
            topKeys: Object.keys(valid.request).sort(),
            selectionKeys: Object.keys(valid.request.generation_strategy).sort(),
            hasForbidden: ['actor_id', 'provider', 'recipe', 'provider_path', 'price_hash', 'selection_hash']
              .some((key) => Object.hasOwn(valid.request, key)),
            invalidKey,
          };
        })()
        """
    )
    assert result["valid"]["ok"] is True
    assert result["topKeys"] == sorted(
        [
            "action",
            "organization_id",
            "project_id",
            "spec_id",
            "spec_version",
            "spec_hash",
            "generation_strategy",
            "confirmation",
            "idempotency_key",
        ]
    )
    assert result["selectionKeys"] == sorted(
        [
            "version",
            "strategy_id",
            "recipe_version",
            "duration_seconds",
            "ratio",
            "audio",
            "assets",
            "attestations",
        ]
    )
    assert result["valid"]["request"]["action"] == "strategy_bind"
    assert result["valid"]["request"]["confirmation"] is True
    assert result["hasForbidden"] is False
    assert result["invalidKey"] == {
        "ok": False,
        "fingerprint": None,
        "start_context_fingerprint": None,
        "request": None,
        "error": {"code": "idempotency_key_invalid", "field": "idempotency_key"},
    }


def test_bind_response_normalizer_is_exact_deep_frozen_and_context_bound() -> None:
    result = _evaluate(
        """
        (() => {
          const valid = runtime.normalizeGenerationStrategyBindResponse(bindResponse(), context());
          const extra = bindResponse(); extra.binding.untrusted = true;
          const mismatch = bindResponse(); mismatch.binding.project_id = ids.organization;
          const price = bindResponse(); price.price.estimated_cost_minor = 1;
          const selection = bindResponse(); selection.binding.selection_hash = '9'.repeat(64);
          const contract = bindResponse(); contract.contract.provider_call_started = true;
          const role = bindResponse(); role.binding.role_assets[1].likeness_consent = false;
          const roleSet = bindResponse();
          roleSet.binding.role_assets[1] = {
            ...roleSet.binding.role_assets[1], role: 'style_reference',
            likeness_consent: false,
          };
          const nonCanonical = bindResponse();
          nonCanonical.price.spend_confirmation =
            ` ${nonCanonical.price.spend_confirmation}`;
          const assetIdentity = bindResponse();
          assetIdentity.binding.role_assets[1].media_object_id = ids.sourceBinding;
          const normalize = (value) => runtime.normalizeGenerationStrategyBindResponse(value, context());
          const frozen = (value) => !value || typeof value !== 'object' || (
            Object.isFrozen(value) && Object.values(value).every(frozen)
          );
          return {
            valid: {
              ok: valid.ok, frozen: frozen(valid), id: valid.value?.binding.id,
              priceHash: valid.value?.price.price_hash,
            },
            extra: normalize(extra), mismatch: normalize(mismatch), price: normalize(price),
            selection: normalize(selection), contract: normalize(contract), role: normalize(role),
            roleSet: normalize(roleSet),
            nonCanonical: normalize(nonCanonical),
            assetIdentity: normalize(assetIdentity),
          };
        })()
        """
    )
    assert result["valid"] == {
        "ok": True,
        "frozen": True,
        "id": "88888888-8888-4888-8888-888888888888",
        "priceHash": "3" * 64,
    }
    assert result["extra"]["error"]["code"] == "object_keys_mismatch"
    assert result["mismatch"]["error"]["code"] == "bind_identity_mismatch"
    assert result["price"]["error"]["code"] == "bind_price_mismatch"
    assert result["selection"]["error"]["code"] == "bind_identity_mismatch"
    assert result["contract"]["error"]["code"] == "bind_contract_invalid"
    assert result["role"]["error"]["code"] == "binding_asset_likeness_invalid"
    assert result["roleSet"]["error"]["code"] == "binding_assets_mismatch"
    assert result["nonCanonical"]["error"]["code"] == "text_not_canonical"
    assert result["assetIdentity"]["error"]["code"] == "binding_asset_identity_mismatch"
    assert all(
        result[key]["ok"] is False
        for key in (
            "extra",
            "mismatch",
            "price",
            "selection",
            "contract",
            "role",
            "roleSet",
            "nonCanonical",
            "assetIdentity",
        )
    )


def test_bind_reducer_invalidates_stale_or_mismatched_response_and_resets_exactly() -> None:
    result = _evaluate(
        """
        (() => {
          const initial = runtime.createGenerationStrategyRuntimeState();
          const binding = runtime.reduceGenerationStrategyRuntimeState(initial, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.select,
            context: context(),
          });
          const stale = runtime.reduceGenerationStrategyRuntimeState(binding, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,
            fingerprint: 'f'.repeat(64), context: context(), response: bindResponse(),
          });
          const bound = runtime.reduceGenerationStrategyRuntimeState(binding, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,
            fingerprint: binding.fingerprint, context: context(), response: bindResponse(),
          });
          const repeated = runtime.reduceGenerationStrategyRuntimeState(bound, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,
            fingerprint: binding.fingerprint, context: context(), response: bindResponse(),
          });
          const invalidated = runtime.reduceGenerationStrategyRuntimeState(bound, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.invalidate,
            reason: 'strategy_selection_changed',
          });
          const reset = runtime.reduceGenerationStrategyRuntimeState(invalidated, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.reset,
          });
          const forged = runtime.reduceGenerationStrategyRuntimeState(
            {...bound, spend_consent: true},
            {type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.invalidate,
             reason: 'should_not_survive'},
          );
          const freeze = (value) => {
            if (value && typeof value === 'object') {
              Object.values(value).forEach(freeze); Object.freeze(value);
            }
            return value;
          };
          const forgedNestedState = clone(bound);
          forgedNestedState.bind.price.confirmation = true;
          const forgedNested = runtime.reduceGenerationStrategyRuntimeState(
            freeze(forgedNestedState),
            {type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.invalidate,
             reason: 'should_not_survive'},
          );
          return {
            initial, stale, bound: {phase: bound.phase, hasBind: Boolean(bound.bind)},
            repeated, invalidated, reset, forged, forgedNested,
          };
        })()
        """
    )
    assert result["initial"]["phase"] == "idle"
    assert result["stale"]["phase"] == "invalid"
    assert result["stale"]["error"]["code"] == "runtime_response_stale"
    assert result["stale"]["fingerprint"] is None
    assert result["stale"]["bind"] is None
    assert result["bound"] == {"phase": "bound", "hasBind": True}
    assert result["repeated"]["phase"] == "invalid"
    assert result["repeated"]["bind"] is None
    assert result["invalidated"]["phase"] == "invalid"
    assert result["invalidated"]["error"]["code"] == "strategy_selection_changed"
    assert result["invalidated"]["fingerprint"] is None
    assert result["reset"] == result["initial"]
    assert result["forged"] == result["initial"]
    assert result["forgedNested"] == result["initial"]


@pytest.mark.parametrize(
    "reason",
    (
        "strategy_selection_changed",
        "strategy_assets_changed",
        "approved_spec_changed",
        "project_changed",
        "campaign_changed",
        "server_price_changed",
    ),
)
def test_public_invalidation_clears_every_runtime_authority(reason: str) -> None:
    result = _evaluate(
        f"""
        (() => {{
          const selected = runtime.reduceGenerationStrategyRuntimeState(
            runtime.createGenerationStrategyRuntimeState(),
            {{type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.select, context: context()}},
          );
          const bound = runtime.reduceGenerationStrategyRuntimeState(selected, {{
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,
            fingerprint: selected.fingerprint,
            context: context(),
            response: bindResponse(),
          }});
          const invalidated = runtime.invalidateGenerationStrategyRuntimeState(
            bound,
            {json.dumps(reason)},
          );
          return {{
            phase: invalidated.phase,
            error: invalidated.error,
            fingerprint: invalidated.fingerprint,
            identity: invalidated.identity,
            bind: invalidated.bind,
            preflight: invalidated.preflight,
            start: invalidated.start,
            status: invalidated.status,
            startKey: invalidated.start_attempt_idempotency_key,
          }};
        }})()
        """
    )
    assert result == {
        "phase": "invalid",
        "error": {"code": reason, "field": "context"},
        "fingerprint": None,
        "identity": None,
        "bind": None,
        "preflight": None,
        "start": None,
        "status": None,
        "startKey": None,
    }


def test_all_three_strategy_selections_are_exact_and_swap_requires_server_duration() -> None:
    result = _evaluate(
        """
        (() => {
          const swap = context();
          swap.generation_strategy = {
            version: '2026-08-14.v1', strategy_id: 'viral_product_swap',
            recipe_version: '2026-06', duration_seconds: 10,
            resolution: '1080p', audio: true,
            assets: [
              {role: 'source_video', media_id: ids.sourceMedia, duration_seconds: 10},
              {role: 'original_product_image', media_id: ids.avatar},
              {role: 'new_product_image', media_id: ids.productMedia, view: 'front'},
            ],
            attestations: {
              source_media_rights_confirmed: true,
              transformative_use_confirmed: true,
              product_assets_rights_confirmed: true,
              depicted_people_consent_confirmed: true,
            },
          };
          const rebuild = context();
          rebuild.generation_strategy = {
            version: '2026-08-14.v1', strategy_id: 'viral_rebuild',
            recipe_version: '2026-06', duration_seconds: 10,
            ratio: '1920:1080', audio: false,
            assets: [
              {role: 'source_video', media_id: ids.sourceMedia},
              {role: 'product_image', media_id: ids.productMedia},
              {role: 'style_image', media_id: ids.avatar},
            ],
            attestations: {
              source_media_rights_confirmed: true,
              transformative_use_confirmed: true,
              product_assets_rights_confirmed: true,
              depicted_people_consent_confirmed: true,
            },
          };
          const missingProbe = clone(swap);
          delete missingProbe.generation_strategy.assets[0].duration_seconds;
          const extraAttestation = clone(rebuild);
          extraAttestation.generation_strategy.attestations.unversioned = true;
          const missingSource = context();
          missingSource.generation_strategy.assets.shift();
          const wrongDimension = clone(swap);
          delete wrongDimension.generation_strategy.resolution;
          wrongDimension.generation_strategy.ratio = '720:1280';
          return {
            avatar: runtime.createGenerationStrategyRuntimeFingerprint(context()),
            swap: runtime.createGenerationStrategyRuntimeFingerprint(swap),
            rebuild: runtime.createGenerationStrategyRuntimeFingerprint(rebuild),
            missingProbe: runtime.createGenerationStrategyRuntimeFingerprint(missingProbe),
            extraAttestation: runtime.createGenerationStrategyRuntimeFingerprint(extraAttestation),
            missingSource: runtime.createGenerationStrategyRuntimeFingerprint(missingSource),
            wrongDimension: runtime.createGenerationStrategyRuntimeFingerprint(wrongDimension),
          };
        })()
        """
    )
    assert result["avatar"]["ok"] is True
    assert result["swap"]["ok"] is True
    assert result["rebuild"]["ok"] is True
    assert result["missingProbe"]["error"]["code"] == "asset_duration_required"
    assert result["extraAttestation"]["error"]["code"] == "object_keys_mismatch"
    assert result["missingSource"]["error"]["code"] == "asset_role_count_invalid"
    assert result["wrongDimension"]["error"]["code"] == "selection_dimension_invalid"


def test_probe_builder_and_response_parser_are_exact_and_stateless() -> None:
    result = _evaluate(
        """
        (() => {
          const validRequest = runtime.generationStrategyRuntimeProbeRequest({
            organization_id: ids.organization,
            project_id: ids.project,
            media_id: ids.sourceMedia,
          }, 'strategy.probe:fixed-key-1');
          const extraContext = runtime.generationStrategyRuntimeProbeRequest({
            organization_id: ids.organization,
            project_id: ids.project,
            media_id: ids.sourceMedia,
            duration_seconds: 10,
          }, 'strategy.probe:fixed-key-1');
          const response = {
            ok: true, version: 'generation-strategy-media-probe-response-v1',
            media_id: ids.sourceMedia, duration_seconds: 10.25,
            verified_at: '2026-08-14T07:59:00.000Z', replay: false,
          };
          const validResponse = runtime.normalizeGenerationStrategyProbeResponse(
            response, ids.sourceMedia,
          );
          const extra = clone(response); extra.sha256 = hashes.source;
          const mismatch = clone(response); mismatch.media_id = ids.avatar;
          const browserDuration = clone(response); browserDuration.duration_seconds = '10.25';
          return {
            validRequest, requestKeys: Object.keys(validRequest.request).sort(),
            extraContext,
            validResponse,
            extra: runtime.normalizeGenerationStrategyProbeResponse(extra, ids.sourceMedia),
            mismatch: runtime.normalizeGenerationStrategyProbeResponse(mismatch, ids.sourceMedia),
            browserDuration: runtime.normalizeGenerationStrategyProbeResponse(
              browserDuration, ids.sourceMedia,
            ),
          };
        })()
        """
    )
    assert result["validRequest"]["ok"] is True
    assert result["requestKeys"] == sorted(
        [
            "action",
            "organization_id",
            "project_id",
            "media_id",
            "confirmation",
            "idempotency_key",
        ]
    )
    assert result["validRequest"]["request"]["confirmation"] is True
    assert result["extraContext"]["error"]["code"] == "object_keys_mismatch"
    assert result["validResponse"]["ok"] is True
    assert result["validResponse"]["value"]["duration_seconds"] == 10.25
    assert result["extra"]["error"]["code"] == "object_keys_mismatch"
    assert result["mismatch"]["error"]["code"] == "probe_identity_mismatch"
    assert result["browserDuration"]["error"]["code"] == "number_invalid"


def test_preflight_builder_parser_and_reducer_bind_every_server_hash() -> None:
    result = _evaluate(
        """
        (() => {
          const bound = stateThroughBound();
          const request = runtime.generationStrategyRuntimePreflightRequest(
            bound, 'strategy.preflight:fixed-key-1',
          );
          const valid = runtime.normalizeGenerationStrategyPreflightResponse(
            preflightResponse(), bound,
          );
          const leakedConsent = preflightResponse();
          leakedConsent.receipt.spend_confirmation = bindResponse().price.spend_confirmation;
          const leakedPrompt = preflightResponse();
          leakedPrompt.receipt.strategy_prompt_hash = hashes.prompt;
          const wrongHash = preflightResponse(); wrongHash.receipt.price_hash = '9'.repeat(64);
          const providerNotReady = preflightResponse();
          providerNotReady.provider_preflight.balance_sufficient = false;
          const stale = runtime.reduceGenerationStrategyRuntimeState(bound, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightResolved,
            fingerprint: 'f'.repeat(64), response: preflightResponse(),
          });
          const ready = stateThroughPreflight();
          return {
            request, requestKeys: Object.keys(request.request).sort(),
            valid, validReceiptKeys: Object.keys(valid.value.receipt).sort(),
            leakedConsent: runtime.normalizeGenerationStrategyPreflightResponse(
              leakedConsent, bound,
            ),
            leakedPrompt: runtime.normalizeGenerationStrategyPreflightResponse(
              leakedPrompt, bound,
            ),
            wrongHash: runtime.normalizeGenerationStrategyPreflightResponse(wrongHash, bound),
            providerNotReady: runtime.normalizeGenerationStrategyPreflightResponse(
              providerNotReady, bound,
            ),
            stale, ready: {phase: ready.phase, frozen: Object.isFrozen(ready.preflight)},
          };
        })()
        """
    )
    assert result["request"]["ok"] is True
    assert result["requestKeys"] == sorted(
        [
            "action",
            "organization_id",
            "project_id",
            "spec_id",
            "spec_version",
            "spec_hash",
            "binding_id",
            "binding_hash",
            "selection_hash",
            "price_hash",
            "spend_confirmation",
            "confirmation",
            "idempotency_key",
        ]
    )
    assert result["valid"]["ok"] is True
    assert "spend_confirmation" not in result["validReceiptKeys"]
    assert "strategy_prompt_hash" not in result["validReceiptKeys"]
    assert result["leakedConsent"]["error"]["code"] == "object_keys_mismatch"
    assert result["leakedPrompt"]["error"]["code"] == "object_keys_mismatch"
    assert result["wrongHash"]["error"]["code"] == "preflight_identity_mismatch"
    assert result["providerNotReady"]["error"]["code"] == "provider_preflight_not_ready"
    assert result["stale"]["phase"] == "invalid"
    assert result["stale"]["bind"] is None
    assert result["ready"] == {"phase": "preflight_ready", "frozen": True}


def test_human_confirmed_preflight_refresh_rotates_only_receipt_authority() -> None:
    result = _evaluate(
        """
        (() => {
          const confirmed = stateThroughHuman();
          const priorStartContext = confirmed.start_context_fingerprint;
          const refreshRequest = runtime.generationStrategyRuntimePreflightRequest(
            confirmed, 'strategy.preflight.refresh:fixed-key-1',
          );
          const boundRequest = runtime.generationStrategyRuntimePreflightRequest(
            stateThroughBound(), 'strategy.preflight:fixed-key-1',
          );
          const normalized = runtime.normalizeGenerationStrategyPreflightResponse(
            refreshedPreflightResponse(), confirmed,
          );
          const refreshed = runtime.reduceGenerationStrategyRuntimeState(confirmed, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightResolved,
            fingerprint: confirmed.fingerprint,
            response: refreshedPreflightResponse(),
          });
          const startRequest = runtime.generationStrategyRuntimeStartRequest(
            refreshed, ids.campaign, 'strategy.start:fixed-key-1',
          );
          const staleStart = runtime.reduceGenerationStrategyRuntimeState(refreshed, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested,
            fingerprint: refreshed.fingerprint,
            start_context_fingerprint: priorStartContext,
            campaign_id: ids.campaign,
            idempotency_key: 'strategy.start:fixed-key-1',
          });
          const reserved = runtime.reduceGenerationStrategyRuntimeState(refreshed, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested,
            fingerprint: refreshed.fingerprint,
            start_context_fingerprint: refreshed.start_context_fingerprint,
            campaign_id: ids.campaign,
            idempotency_key: 'strategy.start:fixed-key-1',
          });
          return {
            refreshRequest,
            boundRequest,
            requestKeys: Object.keys(refreshRequest.request || {}).sort(),
            normalized,
            confirmed: {
              fingerprint: confirmed.fingerprint,
              campaign: confirmed.campaign_id,
              receipt: confirmed.preflight.receipt.id,
              startContext: priorStartContext,
            },
            refreshed: {
              phase: refreshed.phase,
              fingerprint: refreshed.fingerprint,
              campaign: refreshed.campaign_id,
              receipt: refreshed.preflight?.receipt.id,
              receiptHash: refreshed.preflight?.receipt.receipt_hash,
              startContext: refreshed.start_context_fingerprint,
              startKey: refreshed.start_attempt_idempotency_key,
              sameBind: refreshed.bind === confirmed.bind,
            },
            startRequest,
            staleStart,
            reserved: {
              phase: reserved.phase,
              key: reserved.start_attempt_idempotency_key,
            },
          };
        })()
        """
    )
    assert result["refreshRequest"]["ok"] is True
    assert result["refreshRequest"]["request"]["action"] == "strategy_preflight"
    assert result["refreshRequest"]["request"]["idempotency_key"] == (
        "strategy.preflight.refresh:fixed-key-1"
    )
    refresh_authority = result["refreshRequest"]["request"] | {
        "idempotency_key": "strategy.preflight:fixed-key-1",
    }
    assert refresh_authority == result["boundRequest"]["request"]
    assert result["refreshRequest"]["start_context_fingerprint"] == result["confirmed"][
        "startContext"
    ]
    assert result["requestKeys"] == sorted(
        [
            "action",
            "organization_id",
            "project_id",
            "spec_id",
            "spec_version",
            "spec_hash",
            "binding_id",
            "binding_hash",
            "selection_hash",
            "price_hash",
            "spend_confirmation",
            "confirmation",
            "idempotency_key",
        ]
    )
    assert result["normalized"]["ok"] is True
    assert result["refreshed"] == {
        "phase": "human_confirmed",
        "fingerprint": result["confirmed"]["fingerprint"],
        "campaign": result["confirmed"]["campaign"],
        "receipt": "abababab-abab-4bab-8bab-abababababab",
        "receiptHash": "7" * 64,
        "startContext": result["refreshed"]["startContext"],
        "startKey": None,
        "sameBind": True,
    }
    assert result["refreshed"]["startContext"] != result["confirmed"]["startContext"]
    assert result["startRequest"]["ok"] is True
    assert result["startRequest"]["request"]["receipt_id"] == result["refreshed"][
        "receipt"
    ]
    assert result["startRequest"]["request"]["idempotency_key"] == (
        "strategy.start:fixed-key-1"
    )
    assert result["staleStart"]["phase"] == "invalid"
    assert result["reserved"] == {
        "phase": "start_once",
        "key": "strategy.start:fixed-key-1",
    }


@pytest.mark.parametrize(
    ("setup", "expected_code"),
    (
        (
            "const response = preflightResponse(); response.replay = true;",
            "preflight_refresh_not_new",
        ),
        (
            "const response = refreshedPreflightResponse(); "
            "response.receipt.id = ids.receipt;",
            "preflight_refresh_not_new",
        ),
        (
            "const response = refreshedPreflightResponse(); "
            "response.receipt.receipt_hash = hashes.receipt;",
            "preflight_refresh_not_new",
        ),
        (
            "const response = refreshedPreflightResponse(); "
            "response.receipt.checked_at = '2026-08-14T08:01:00.000Z';",
            "preflight_refresh_not_new",
        ),
        (
            "const response = refreshedPreflightResponse(); "
            "response.receipt.checked_at = '2026-08-14T08:02:00.000Z'; "
            "response.receipt.expires_at = '2026-08-14T08:06:00.000Z';",
            "preflight_refresh_not_new",
        ),
        (
            "const response = refreshedPreflightResponse(); "
            "response.receipt.binding_hash = '9'.repeat(64);",
            "preflight_identity_mismatch",
        ),
        (
            "const response = refreshedPreflightResponse(); "
            "response.receipt.selection_hash = '9'.repeat(64);",
            "preflight_identity_mismatch",
        ),
        (
            "const response = refreshedPreflightResponse(); "
            "response.receipt.price_hash = '9'.repeat(64);",
            "preflight_identity_mismatch",
        ),
    ),
)
def test_human_confirmed_preflight_refresh_rejects_replay_or_drift(
    setup: str,
    expected_code: str,
) -> None:
    result = _evaluate(
        f"""
        (() => {{
          const confirmed = stateThroughHuman();
          {setup}
          const normalized = runtime.normalizeGenerationStrategyPreflightResponse(
            response, confirmed,
          );
          const candidate = runtime.reduceGenerationStrategyRuntimeState(confirmed, {{
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightResolved,
            fingerprint: confirmed.fingerprint,
            response,
          }});
          return {{normalized, candidate}};
        }})()
        """
    )
    assert result["normalized"]["ok"] is False
    assert result["normalized"]["error"]["code"] == expected_code
    assert result["candidate"]["phase"] == "invalid"
    assert result["candidate"]["error"]["code"] == expected_code
    assert result["candidate"]["campaign_id"] is None
    assert result["candidate"]["preflight"] is None


def test_start_once_and_status_cannot_refresh_preflight() -> None:
    result = _evaluate(
        """
        (() => {
          const startOnce = stateThroughStartOnce();
          const status = runtime.reduceGenerationStrategyRuntimeState(startOnce, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
            fingerprint: startOnce.fingerprint,
            start_context_fingerprint: startOnce.start_context_fingerprint,
            idempotency_key: startOnce.start_attempt_idempotency_key,
            response: statusResponse(),
          });
          const refresh = (state) => runtime.reduceGenerationStrategyRuntimeState(state, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightResolved,
            fingerprint: state.fingerprint,
            response: refreshedPreflightResponse(),
          });
          return {
            originals: {
              startPhase: startOnce.phase,
              startKey: startOnce.start_attempt_idempotency_key,
              statusPhase: status.phase,
              statusJob: status.status.job.id,
            },
            startBuilder: runtime.generationStrategyRuntimePreflightRequest(
              startOnce, 'strategy.preflight.refresh:fixed-key-2',
            ),
            statusBuilder: runtime.generationStrategyRuntimePreflightRequest(
              status, 'strategy.preflight.refresh:fixed-key-3',
            ),
            startNormalizer: runtime.normalizeGenerationStrategyPreflightResponse(
              refreshedPreflightResponse(), startOnce,
            ),
            statusNormalizer: runtime.normalizeGenerationStrategyPreflightResponse(
              refreshedPreflightResponse(), status,
            ),
            startCandidate: refresh(startOnce),
            statusCandidate: refresh(status),
          };
        })()
        """
    )
    assert result["originals"] == {
        "startPhase": "start_once",
        "startKey": "strategy.start:fixed-key-1",
        "statusPhase": "status",
        "statusJob": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    }
    for name in ("startBuilder", "statusBuilder"):
        assert result[name]["ok"] is False
        assert result[name]["error"]["code"] == "preflight_state_invalid"
    for name in ("startNormalizer", "statusNormalizer"):
        assert result[name]["ok"] is False
        assert result[name]["error"]["code"] == "preflight_state_invalid"
    for name in ("startCandidate", "statusCandidate"):
        assert result[name]["phase"] == "invalid"
        assert result[name]["error"]["code"] == "runtime_response_stale"
        assert result[name]["start"] is None
        assert result[name]["status"] is None


def test_human_confirmation_is_campaign_bound_ephemeral_and_start_is_reserved_once() -> None:
    result = _evaluate(
        """
        (() => {
          const ready = stateThroughPreflight();
          const confirmed = stateThroughHuman();
          const otherCampaign = stateThroughHuman(ids.otherCampaign);
          const wrongToken = runtime.reduceGenerationStrategyRuntimeState(ready, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.humanConfirmed,
            fingerprint: ready.fingerprint, campaign_id: ids.campaign,
            spend_confirmation: 'RUNWAY_WRONG_TOKEN', confirmation: true,
          });
          const request = runtime.generationStrategyRuntimeStartRequest(
            confirmed, ids.campaign, 'strategy.start:fixed-key-1',
          );
          const wrongCampaignRequest = runtime.generationStrategyRuntimeStartRequest(
            confirmed, ids.otherCampaign, 'strategy.start:fixed-key-1',
          );
          const reserved = stateThroughStartOnce();
          const secondBuilder = runtime.generationStrategyRuntimeStartRequest(
            reserved, ids.campaign, 'strategy.start:fixed-key-2',
          );
          const repeated = runtime.reduceGenerationStrategyRuntimeState(reserved, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested,
            fingerprint: reserved.fingerprint,
            start_context_fingerprint: reserved.start_context_fingerprint,
            campaign_id: ids.campaign, idempotency_key: 'strategy.start:fixed-key-2',
          });
          const serialized = JSON.stringify(confirmed);
          return {
            confirmed: {
              phase: confirmed.phase,
              campaign: confirmed.campaign_id,
              startFingerprint: confirmed.start_context_fingerprint,
              hasRawSelection: serialized.includes('generation_strategy') ||
                serialized.includes('attestations'),
              hasHumanDecision: Object.hasOwn(confirmed, 'confirmation') ||
                Object.hasOwn(confirmed, 'spend_confirmed'),
              tokenType: typeof confirmed.bind.price.spend_confirmation,
            },
            otherFingerprint: otherCampaign.start_context_fingerprint,
            wrongToken, request, requestKeys: Object.keys(request.request).sort(),
            wrongCampaignRequest,
            reserved: {phase: reserved.phase, key: reserved.start_attempt_idempotency_key},
            secondBuilder, repeated,
          };
        })()
        """
    )
    assert result["confirmed"]["phase"] == "human_confirmed"
    assert result["confirmed"]["campaign"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    assert result["confirmed"]["hasRawSelection"] is False
    assert result["confirmed"]["hasHumanDecision"] is False
    assert result["confirmed"]["tokenType"] == "string"
    assert result["confirmed"]["startFingerprint"] != result["otherFingerprint"]
    assert result["wrongToken"]["phase"] == "invalid"
    assert result["request"]["ok"] is True
    assert result["requestKeys"] == sorted(
        [
            "action",
            "organization_id",
            "project_id",
            "spec_id",
            "spec_version",
            "spec_hash",
            "binding_id",
            "binding_hash",
            "selection_hash",
            "price_hash",
            "spend_confirmation",
            "confirmation",
            "receipt_id",
            "receipt_hash",
            "campaign_id",
            "idempotency_key",
        ]
    )
    assert result["wrongCampaignRequest"]["ok"] is False
    assert result["reserved"] == {
        "phase": "start_once",
        "key": "strategy.start:fixed-key-1",
    }
    assert result["secondBuilder"]["ok"] is False
    assert result["repeated"]["phase"] == "invalid"
    assert result["repeated"]["start_attempt_idempotency_key"] is None


def test_start_status_parser_is_exact_correlated_and_drops_raw_selection() -> None:
    result = _evaluate(
        """
        (() => {
          const reserved = stateThroughStartOnce();
          const valid = runtime.normalizeGenerationStrategyStartResponse(
            statusResponse(), reserved,
          );
          const wrongCampaign = statusResponse(); wrongCampaign.job.campaign_id = ids.otherCampaign;
          const wrongReceipt = statusResponse(); wrongReceipt.strategy.receipt_hash = '9'.repeat(64);
          const wrongPrice = statusResponse(); wrongPrice.price.estimated_credits = 1;
          const extraSelection = statusResponse(); extraSelection.selection.provider = 'runway';
          const leakedSpend = statusResponse();
          leakedSpend.price.spend_confirmation = bindResponse().price.spend_confirmation;
          const started = runtime.reduceGenerationStrategyRuntimeState(reserved, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
            fingerprint: reserved.fingerprint,
            start_context_fingerprint: reserved.start_context_fingerprint,
            idempotency_key: reserved.start_attempt_idempotency_key,
            response: statusResponse(),
          });
          const statusRequest = runtime.generationStrategyRuntimeStatusRequest(started);
          const serialized = JSON.stringify(valid.value);
          return {
            valid: {
              ok: valid.ok, valueKeys: Object.keys(valid.value).sort(),
              containsSelection: serialized.includes('attestations') ||
                serialized.includes('generation_strategy') ||
                Object.hasOwn(valid.value, 'selection'),
              containsSpend: serialized.includes('spend_confirmation'),
            },
            wrongCampaign: runtime.normalizeGenerationStrategyStartResponse(
              wrongCampaign, reserved,
            ),
            wrongReceipt: runtime.normalizeGenerationStrategyStartResponse(wrongReceipt, reserved),
            wrongPrice: runtime.normalizeGenerationStrategyStartResponse(wrongPrice, reserved),
            extraSelection: runtime.normalizeGenerationStrategyStartResponse(
              extraSelection, reserved,
            ),
            leakedSpend: runtime.normalizeGenerationStrategyStartResponse(leakedSpend, reserved),
            started: {phase: started.phase, job: started.status?.job.id},
            statusRequest,
            statusRequestKeys: Object.keys(statusRequest.request || {}).sort(),
          };
        })()
        """
    )
    assert result["valid"]["ok"] is True
    assert result["valid"]["valueKeys"] == sorted(
        [
            "ok",
            "version",
            "job",
            "strategy",
            "price",
            "dispatch",
            "reconciliation",
            "output",
            "error",
            "contract",
        ]
    )
    assert result["valid"]["containsSelection"] is False
    assert result["valid"]["containsSpend"] is False
    assert result["wrongCampaign"]["error"]["code"] == "status_job_identity_mismatch"
    assert result["wrongReceipt"]["error"]["code"] == "status_strategy_mismatch"
    assert result["wrongPrice"]["error"]["code"] == "status_price_mismatch"
    assert result["extraSelection"]["error"]["code"] == "object_keys_mismatch"
    assert result["leakedSpend"]["error"]["code"] == "object_keys_mismatch"
    assert result["started"] == {
        "phase": "status",
        "job": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    }
    assert result["statusRequest"]["ok"] is True
    assert result["statusRequestKeys"] == sorted(
        ["action", "organization_id", "project_id", "generation_job_id"]
    )


def test_status_reducer_is_monotonic_and_mismatched_poll_fails_closed() -> None:
    result = _evaluate(
        """
        (() => {
          const reserved = stateThroughStartOnce();
          const started = runtime.reduceGenerationStrategyRuntimeState(reserved, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
            fingerprint: reserved.fingerprint,
            start_context_fingerprint: reserved.start_context_fingerprint,
            idempotency_key: reserved.start_attempt_idempotency_key,
            response: statusResponse('submitted', '2026-08-14T08:03:00.000Z'),
          });
          const transition = (state, response, jobId = ids.job) =>
            runtime.reduceGenerationStrategyRuntimeState(state, {
              type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.statusResolved,
              fingerprint: state.fingerprint,
              start_context_fingerprint: state.start_context_fingerprint,
              generation_job_id: jobId,
              response,
            });
          const processing = transition(
            started, statusResponse('processing', '2026-08-14T08:04:00.000Z'),
          );
          const succeeded = transition(
            processing, statusResponse('succeeded', '2026-08-14T08:05:00.000Z'),
          );
          const regression = transition(
            processing, statusResponse('submitted', '2026-08-14T08:05:00.000Z'),
          );
          const terminalChange = transition(
            succeeded, statusResponse('processing', '2026-08-14T08:06:00.000Z'),
          );
          const wrongJob = transition(started, statusResponse(), ids.batch);
          const olderClock = transition(
            processing, statusResponse('processing', '2026-08-14T08:03:30.000Z'),
          );
          const changedTaskResponse = statusResponse(
            'processing', '2026-08-14T08:04:00.000Z',
          );
          changedTaskResponse.job.provider_task_id = 'runway-task-other-002';
          const changedTask = transition(started, changedTaskResponse);
          const changedDispatchResponse = statusResponse(
            'processing', '2026-08-14T08:04:00.000Z',
          );
          changedDispatchResponse.dispatch.result_hash = '9'.repeat(64);
          const changedDispatch = transition(started, changedDispatchResponse);
          const incidentResponse = statusResponse(
            'starting', '2026-08-14T08:03:00.000Z',
          );
          incidentResponse.dispatch = {
            result_id: ids.dispatch, result_hash: hashes.dispatch,
            outcome: 'ambiguous', provider_post_started: true,
            provider_http_status: null, recorded_at: '2026-08-14T08:02:30.000Z',
          };
          incidentResponse.reconciliation = {
            required: true, incident_id: ids.incident,
            reason_code: 'provider_create_response_unknown',
            required_at: '2026-08-14T08:02:31.000Z',
          };
          const incidentStarted = runtime.reduceGenerationStrategyRuntimeState(reserved, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
            fingerprint: reserved.fingerprint,
            start_context_fingerprint: reserved.start_context_fingerprint,
            idempotency_key: reserved.start_attempt_idempotency_key,
            response: incidentResponse,
          });
          const droppedIncidentResponse = clone(incidentResponse);
          droppedIncidentResponse.job.updated_at = '2026-08-14T08:04:00.000Z';
          droppedIncidentResponse.reconciliation = null;
          const droppedIncident = transition(incidentStarted, droppedIncidentResponse);
          return {
            started: started.status.job.status,
            processing: processing.status.job.status,
            succeeded: {
              phase: succeeded.phase,
              status: succeeded.status.job.status,
              output: succeeded.status.output.media_id,
            },
            regression, terminalChange, wrongJob, olderClock,
            changedTask, changedDispatch, droppedIncident,
          };
        })()
        """
    )
    assert result["started"] == "submitted"
    assert result["processing"] == "processing"
    assert result["succeeded"] == {
        "phase": "status",
        "status": "succeeded",
        "output": "ffffffff-ffff-4fff-8fff-ffffffffffff",
    }
    for key in (
        "regression",
        "terminalChange",
        "wrongJob",
        "olderClock",
        "changedTask",
        "changedDispatch",
        "droppedIncident",
    ):
        assert result[key]["phase"] == "invalid"
        assert result[key]["status"] is None


def test_safe_projection_is_ui_ready_without_raw_authority_and_campaign_invalidation() -> None:
    result = _evaluate(
        """
        (() => {
          const reserved = stateThroughStartOnce();
          const started = runtime.reduceGenerationStrategyRuntimeState(reserved, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
            fingerprint: reserved.fingerprint,
            start_context_fingerprint: reserved.start_context_fingerprint,
            idempotency_key: reserved.start_attempt_idempotency_key,
            response: statusResponse(),
          });
          const projection = runtime.generationStrategyRuntimeSafeProjection(started);
          const serialized = JSON.stringify(projection);
          const invalidated = runtime.invalidateGenerationStrategyRuntimeState(
            started, 'campaign_changed',
          );
          const secondInitial = runtime.createGenerationStrategyRuntimeState();
          const secondContext = context(); secondContext.project_id = ids.campaign;
          const secondSelected = runtime.reduceGenerationStrategyRuntimeState(
            secondInitial,
            {type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.select, context: secondContext},
          );
          return {
            projection,
            frozen: Object.isFrozen(projection) && Object.isFrozen(projection.price),
            leaked: ['role_assets', 'attestations', 'generation_strategy',
              'strategy_prompt_hash', 'provider_task_id', 'signed_url', 'object_name']
              .some((field) => serialized.includes(field)),
            invalidated,
            independent: {
              firstFingerprint: started.fingerprint,
              secondFingerprint: secondSelected.fingerprint,
              secondPhase: secondSelected.phase,
            },
          };
        })()
        """
    )
    projection = result["projection"]
    assert result["frozen"] is True
    assert result["leaked"] is False
    assert projection["phase"] == "status"
    assert projection["can_poll"] is True
    assert projection["can_start"] is False
    assert projection["price"]["spend_confirmation"].startswith("RUNWAY_PRODUCT_UGC_")
    assert result["invalidated"]["phase"] == "invalid"
    assert result["invalidated"]["campaign_id"] is None
    assert result["invalidated"]["start_context_fingerprint"] is None
    assert result["invalidated"]["status"] is None
    assert result["independent"]["firstFingerprint"] != result["independent"]["secondFingerprint"]
    assert result["independent"]["secondPhase"] == "selected"
