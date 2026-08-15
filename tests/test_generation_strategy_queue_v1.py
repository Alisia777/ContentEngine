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
QUEUE_MODULE = ROOT / "web/app/generation-strategy-queue.js"
RUNTIME_SOURCE = RUNTIME_MODULE.read_text(encoding="utf-8")
QUEUE_SOURCE = QUEUE_MODULE.read_text(encoding="utf-8")


JS_FIXTURE = r"""
import * as runtime from './generation-strategy-runtime.js';
import * as queueContract from './generation-strategy-queue.js';

const clone = (value) => JSON.parse(JSON.stringify(value));
const uuid = (kind, index) => {
  const head = (kind * 1000 + index + 1).toString(16).padStart(8, '0');
  const tail = (kind * 100 + index + 1).toString(16).padStart(12, '0');
  return `${head}-0000-4000-8000-${tail}`;
};
const hash = (kind, index) =>
  (kind * 1000 + index + 1).toString(16).padStart(64, '0');
const sourceId = (index) => uuid(10, index);
const campaignId = uuid(90, 0);

const makeEntries = (count = 10) => Array.from({length: count}, (_, index) => ({
  source_media_id: sourceId(index),
  idempotency_keys: {
    probe: `strategy.probe:row-${index + 1}`,
    bind: `strategy.bind:row-${index + 1}`,
    preflight: `strategy.preflight:row-${index + 1}`,
    start: `strategy.start:row-${index + 1}`,
  },
}));

const context = (index) => ({
  organization_id: uuid(1, 0),
  project_id: uuid(2, 0),
  spec_id: uuid(3, 0),
  spec_version: 7,
  spec_hash: hash(3, 0),
  generation_strategy: {
    version: '2026-08-14.v1',
    strategy_id: 'viral_avatar_ugc',
    recipe_version: '2026-06',
    duration_seconds: 4,
    ratio: '720:1280',
    audio: false,
    assets: [
      {role: 'source_video', media_id: sourceId(index)},
      {role: 'avatar_image', media_id: uuid(20, index)},
      {role: 'product_image', media_id: uuid(30, index)},
    ],
    attestations: {
      source_media_rights_confirmed: true,
      transformative_use_confirmed: true,
      product_assets_rights_confirmed: true,
      depicted_people_consent_confirmed: true,
      avatar_likeness_consent_confirmed: true,
    },
  },
});

const bindResponse = (index) => ({
  ok: true,
  version: 'generation-strategy-resolve-bind-response-v1',
  binding: {
    id: uuid(40, index),
    project_id: uuid(2, 0),
    spec_id: uuid(3, 0),
    spec_version: 7,
    spec_hash: hash(3, 0),
    product_id: uuid(4, 0),
    strategy_id: 'viral_avatar_ugc',
    selection_hash: hash(40, index),
    source_basis: 'exact_source_video',
    source_binding_id: uuid(41, index),
    source_binding_hash: hash(41, index),
    role_assets: [
      {
        role: 'product_primary', ordinal: 1,
        media_object_id: uuid(30, index), sha256: hash(30, index),
        kind: 'product_photo', mime_type: 'image/png',
        product_id: uuid(4, 0), rights_confirmed: true,
        likeness_consent: false,
      },
      {
        role: 'creator_avatar', ordinal: 1,
        media_object_id: uuid(20, index), sha256: hash(20, index),
        kind: 'creator_reference', mime_type: 'image/jpeg',
        product_id: null, rights_confirmed: true,
        likeness_consent: true,
      },
    ],
    strategy_snapshot_hash: hash(42, index),
    binding_hash: hash(43, index),
    bound_at: '2026-08-14T08:00:00.000Z',
  },
  selection: {
    catalog_version: '2026-08-14.v1',
    recipe_version: '2026-06',
    pricing_version: 'runway-recipe-credits-2026-08-14.v1',
    strategy_id: 'viral_avatar_ugc',
    recipe: 'product_ugc',
    selection_hash: hash(40, index),
  },
  price: {
    version: 'generation-strategy-price-snapshot-v1',
    strategy_id: 'viral_avatar_ugc',
    provider: 'runway',
    recipe: 'product_ugc',
    input_mode: 'character_and_product_images',
    duration_seconds: 4,
    resolution: '720p',
    ratio: '720:1280',
    audio: false,
    estimated_credits: 192,
    estimated_pre_tax_usd_minor: 192,
    estimated_cost_minor: 192,
    estimated_cost_usd: '1.92',
    currency: 'USD',
    credit_unit_cost_minor: 1,
    catalog_version: '2026-08-14.v1',
    pricing_version: 'runway-recipe-credits-2026-08-14.v1',
    recipe_version: '2026-06',
    spend_confirmation: 'RUNWAY_PRODUCT_UGC_4S_720P_SILENT_USD_1.92',
    price_hash: hash(44, index),
  },
  contract: {
    server_resolved_source_binding: true,
    server_resolved_media_hashes: true,
    browser_hashes_accepted: false,
    browser_source_binding_accepted: false,
    provider_call_started: false,
    paid_start_integrated: false,
    launch_enabled: false,
  },
});

const preflightResponse = (index) => ({
  ok: true,
  version: 'generation-strategy-preflight-response-v1',
  replay: false,
  receipt: {
    id: uuid(50, index),
    receipt_hash: hash(50, index),
    binding_id: uuid(40, index),
    binding_hash: hash(43, index),
    strategy_id: 'viral_avatar_ugc',
    recipe: 'product_ugc',
    catalog_version: '2026-08-14.v1',
    recipe_version: '2026-06',
    pricing_version: 'runway-recipe-credits-2026-08-14.v1',
    selection_hash: hash(40, index),
    price_hash: hash(44, index),
    ready: true,
    failure_code: null,
    checked_at: '2026-08-14T08:01:00.000Z',
    expires_at: '2026-08-14T08:06:00.000Z',
  },
  provider_preflight: {
    credential_configured: true,
    provider_authentication_confirmed: true,
    recipe_catalog_supported: true,
    recipe_precheck_supported: false,
    recipe_available: null,
    balance_sufficient: true,
    daily_quota_precheck_supported: false,
    daily_quota_available: null,
  },
  launch_enabled: true,
  contract: {
    provider_call_started: false,
    receipt_single_use: true,
    browser_price_authority: false,
    browser_prompt_authority: false,
  },
});

const statusResponse = (index, jobStatus = 'failed') => {
  const terminalSuccess = jobStatus === 'succeeded';
  const terminalFailure = ['failed', 'cancelled'].includes(jobStatus);
  const hasProviderTask = [
    'submitted', 'processing', 'succeeded', 'failed', 'cancelled',
  ].includes(jobStatus);
  const price = clone(bindResponse(index).price);
  delete price.spend_confirmation;
  return {
    ok: true,
    version: 'generation-strategy-status-response-v1',
    job: {
      id: uuid(60, index),
      batch_id: uuid(61, index),
      project_id: uuid(2, 0),
      campaign_id: campaignId,
      status: jobStatus,
      provider_status: hasProviderTask ? jobStatus : null,
      provider_task_id: hasProviderTask ? `runway-task-${index + 1}` : null,
      estimated_cost_minor: 192,
      actual_cost_minor: hasProviderTask ? 192 : null,
      currency: 'USD',
      created_at: '2026-08-14T08:02:00.000Z',
      updated_at: '2026-08-14T08:03:00.000Z',
    },
    strategy: {
      version: 'generation-strategy-immutable-execution-v1',
      strategy_id: 'viral_avatar_ugc',
      recipe: 'product_ugc',
      catalog_version: '2026-08-14.v1',
      recipe_version: '2026-06',
      pricing_version: 'runway-recipe-credits-2026-08-14.v1',
      binding_id: uuid(40, index),
      binding_hash: hash(43, index),
      receipt_id: uuid(50, index),
      receipt_hash: hash(50, index),
      selection_hash: hash(40, index),
      price_hash: hash(44, index),
      strategy_prompt_hash: hash(62, index),
    },
    selection: context(index).generation_strategy,
    price,
    dispatch: hasProviderTask ? {
      result_id: uuid(63, index),
      result_hash: hash(63, index),
      outcome: 'submitted',
      provider_post_started: true,
      provider_http_status: 201,
      recorded_at: '2026-08-14T08:02:30.000Z',
    } : null,
    reconciliation: null,
    output: terminalSuccess ? {
      media_id: uuid(64, index), mime_type: 'video/mp4', size_bytes: 4096,
    } : null,
    error: terminalFailure ? {
      code: 'provider_generation_failed', provider_billing_outcome: 'unknown',
    } : null,
    contract: {
      recipe_aware: true,
      legacy_model_catalog_used: false,
      poll_provider_allowed: ['submitted', 'processing'].includes(jobStatus),
      second_post_allowed: false,
      object_names_returned: false,
      media_hashes_returned: false,
      signed_urls_returned: false,
      manual_human_review_required: terminalSuccess,
    },
  };
};

const reconciliationRequiredResponse = (index) => {
  const response = statusResponse(index, 'starting');
  response.dispatch = {
    result_id: uuid(63, index),
    result_hash: hash(63, index),
    outcome: 'ambiguous',
    provider_post_started: true,
    provider_http_status: null,
    recorded_at: '2026-08-14T08:02:30.000Z',
  };
  response.reconciliation = {
    required: true,
    incident_id: uuid(65, index),
    reason_code: 'provider_create_response_unknown',
    required_at: '2026-08-14T08:02:31.000Z',
  };
  return response;
};

const mustCreate = (entries = makeEntries()) => {
  const result = queueContract.createGenerationStrategyQueue(entries);
  if (!result.ok) throw new Error(JSON.stringify(result.error));
  return result.queue;
};
const update = (queue, index, action) => {
  const result = queueContract.updateGenerationStrategyQueueRow(
    queue, sourceId(index), action,
  );
  if (!result.ok) throw new Error(JSON.stringify(result.error));
  return result.queue;
};
const selectAll = (initial = mustCreate()) => {
  let queue = initial;
  for (let index = 0; index < 10; index += 1) {
    queue = update(queue, index, {
      type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.select,
      context: context(index),
    });
  }
  return queue;
};
const bindAll = (selected = selectAll()) => {
  let queue = selected;
  for (let index = 0; index < 10; index += 1) {
    const state = queue.rows.get(sourceId(index)).runtime_state;
    queue = update(queue, index, {
      type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,
      fingerprint: state.fingerprint,
      context: context(index),
      response: bindResponse(index),
    });
  }
  return queue;
};
const readyAll = (bound = bindAll()) => {
  let queue = bound;
  for (let index = 0; index < 10; index += 1) {
    const state = queue.rows.get(sourceId(index)).runtime_state;
    queue = update(queue, index, {
      type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightResolved,
      fingerprint: state.fingerprint,
      response: preflightResponse(index),
    });
  }
  return queue;
};
const confirmAll = (ready = readyAll()) => {
  let queue = ready;
  for (let index = 0; index < 10; index += 1) {
    const state = queue.rows.get(sourceId(index)).runtime_state;
    queue = update(queue, index, {
      type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.humanConfirmed,
      fingerprint: state.fingerprint,
      campaign_id: campaignId,
      spend_confirmation: bindResponse(index).price.spend_confirmation,
      confirmation: true,
    });
  }
  return queue;
};
const reserveStart = (queue, index) => {
  const row = queue.rows.get(sourceId(index));
  const state = row.runtime_state;
  return update(queue, index, {
    type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested,
    fingerprint: state.fingerprint,
    start_context_fingerprint: state.start_context_fingerprint,
    campaign_id: state.campaign_id,
    idempotency_key: row.idempotency_keys.start,
  });
};
const resolveStart = (queue, index, jobStatus = 'failed') => {
  const row = queue.rows.get(sourceId(index));
  const state = row.runtime_state;
  return update(queue, index, {
    type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
    fingerprint: state.fingerprint,
    start_context_fingerprint: state.start_context_fingerprint,
    idempotency_key: row.idempotency_keys.start,
    response: statusResponse(index, jobStatus),
  });
};
"""


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy queue contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text('{"type":"module"}', encoding="utf-8")
        (directory / "generation-strategy-runtime.js").write_text(
            RUNTIME_SOURCE,
            encoding="utf-8",
        )
        (directory / "generation-strategy-queue.js").write_text(
            QUEUE_SOURCE,
            encoding="utf-8",
        )
        (directory / "contract.js").write_text(
            JS_FIXTURE
            + f"\nconst result = {expression};\n"
            + "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [node, "contract.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_queue_imports_frozen_runtime_and_is_pure_planning_only() -> None:
    canonical_runtime = RUNTIME_MODULE.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(canonical_runtime).hexdigest() == (
        "70387d40a78f9fd4ec5401fbe3ca558f8969afc7bfc12511c743e653ba961ced"
    )
    assert (
        'from "./generation-strategy-runtime.js?v=20260814.os4.41";'
        in QUEUE_SOURCE
    )
    for forbidden in (
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "fetch(",
        "XMLHttpRequest",
        "Date.",
        "Date(",
        "Math.random",
        "crypto.",
        "setTimeout",
        "setInterval",
        "seedance",
        "veo",
        "source_media_ids",
        "contentGenerationHandoff",
    ):
        assert forbidden not in QUEUE_SOURCE

    result = _evaluate(
        """
        ({
          exports: Object.keys(queueContract).sort(),
          version: queueContract.GENERATION_STRATEGY_QUEUE_VERSION,
          size: queueContract.GENERATION_STRATEGY_QUEUE_SIZE,
          free: queueContract.GENERATION_STRATEGY_QUEUE_FREE_MAX_CONCURRENCY,
          paid: queueContract.GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY,
        })
        """
    )
    assert result == {
        "exports": sorted(
            [
                "GENERATION_STRATEGY_QUEUE_FREE_MAX_CONCURRENCY",
                "GENERATION_STRATEGY_QUEUE_PAID_MAX_CONCURRENCY",
                "GENERATION_STRATEGY_QUEUE_SIZE",
                "GENERATION_STRATEGY_QUEUE_VERSION",
                "advanceGenerationStrategyQueueSequentialStarts",
                "createGenerationStrategyQueue",
                "generationStrategyQueueAggregateReview",
                "generationStrategyQueueSafeProjection",
                "invalidateGenerationStrategyQueueRow",
                "planGenerationStrategyQueueFreeWork",
                "planGenerationStrategyQueueSequentialStarts",
                "updateGenerationStrategyQueueRow",
            ]
        ),
        "version": "2026-08-14.v1",
        "size": 10,
        "free": 3,
        "paid": 1,
    }


@pytest.mark.parametrize("count", [0, 9, 11])
def test_creation_rejects_any_count_other_than_exactly_ten(count: int) -> None:
    result = _evaluate(
        f"queueContract.createGenerationStrategyQueue(makeEntries({count}))"
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "queue_size_invalid"


def test_creation_rejects_bad_or_duplicate_ids_and_any_duplicate_request_key() -> None:
    result = _evaluate(
        """
        (() => {
          const badId = makeEntries(); badId[4].source_media_id = 'not-a-uuid';
          const duplicateId = makeEntries();
          duplicateId[7].source_media_id = duplicateId[2].source_media_id;
          const sameRowKey = makeEntries();
          sameRowKey[0].idempotency_keys.start = sameRowKey[0].idempotency_keys.bind;
          const crossRowKey = makeEntries();
          crossRowKey[9].idempotency_keys.probe =
            crossRowKey[1].idempotency_keys.preflight;
          return {
            badId: queueContract.createGenerationStrategyQueue(badId),
            duplicateId: queueContract.createGenerationStrategyQueue(duplicateId),
            sameRowKey: queueContract.createGenerationStrategyQueue(sameRowKey),
            crossRowKey: queueContract.createGenerationStrategyQueue(crossRowKey),
          };
        })()
        """
    )
    assert result["badId"]["error"]["code"] == "uuid_invalid"
    assert result["duplicateId"]["error"]["code"] == "source_media_id_duplicate"
    assert result["sameRowKey"]["error"]["code"] == "idempotency_key_duplicate"
    assert result["crossRowKey"]["error"]["code"] == "idempotency_key_duplicate"


def test_creation_preserves_order_and_rows_have_independent_states_and_keys() -> None:
    result = _evaluate(
        """
        (() => {
          const queue = mustCreate();
          const rows = [...queue.rows.values()];
          let mutationRejected = false;
          try { queue.rows.set(sourceId(0), rows[1]); } catch { mutationRejected = true; }
          const selected = selectAll(queue);
          const selectedRows = [...selected.rows.values()];
          return {
            order: queue.source_order,
            mapOrder: [...queue.rows.keys()],
            phases: rows.map((row) => row.runtime_state.phase),
            uniqueStateObjects: new Set(rows.map((row) => row.runtime_state)).size,
            uniqueKeys: new Set(rows.flatMap((row) =>
              Object.values(row.idempotency_keys))).size,
            mutationRejected,
            selectedPhases: selectedRows.map((row) => row.runtime_state.phase),
            uniqueFingerprints: new Set(selectedRows.map((row) =>
              row.runtime_state.fingerprint)).size,
          };
        })()
        """
    )
    expected_order = _evaluate("makeEntries().map((entry) => entry.source_media_id)")
    assert result["order"] == expected_order
    assert result["mapOrder"] == expected_order
    assert result["phases"] == ["idle"] * 10
    assert result["uniqueStateObjects"] == 10
    assert result["uniqueKeys"] == 40
    assert result["mutationRejected"] is True
    assert result["selectedPhases"] == ["selected"] * 10
    assert result["uniqueFingerprints"] == 10


def test_source_or_row_drift_invalidates_only_that_row() -> None:
    result = _evaluate(
        """
        (() => {
          const selected = selectAll();
          const wrongContext = context(0);
          wrongContext.generation_strategy.assets[0].media_id = sourceId(1);
          const drifted = update(selected, 0, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.bindResolved,
            fingerprint: selected.rows.get(sourceId(0)).runtime_state.fingerprint,
            context: wrongContext,
            response: bindResponse(0),
          });
          const explicitlyInvalidated = queueContract.invalidateGenerationStrategyQueueRow(
            selected, sourceId(4), 'campaign_changed',
          ).queue;
          return {
            driftedPhases: [...drifted.rows.values()].map((row) =>
              row.runtime_state.phase),
            driftedRevision: drifted.revision,
            explicitPhases: [...explicitlyInvalidated.rows.values()].map((row) =>
              row.runtime_state.phase),
            explicitRevision: explicitlyInvalidated.revision,
          };
        })()
        """
    )
    assert result["driftedPhases"] == ["invalid"] + ["selected"] * 9
    assert result["driftedRevision"] == 11
    assert result["explicitPhases"] == ["selected"] * 4 + ["invalid"] + ["selected"] * 5
    assert result["explicitRevision"] == 11


def test_safe_projection_and_aggregate_review_are_redacted_display_only() -> None:
    result = _evaluate(
        """
        (() => {
          const ready = readyAll();
          const safe = queueContract.generationStrategyQueueSafeProjection(ready);
          const first = queueContract.generationStrategyQueueAggregateReview(ready).review;
          const same = queueContract.generationStrategyQueueAggregateReview(
            ready, first,
          ).review;
          const invalidated = queueContract.invalidateGenerationStrategyQueueRow(
            ready, sourceId(3), 'asset_changed',
          ).queue;
          const changed = queueContract.generationStrategyQueueAggregateReview(
            invalidated, first,
          ).review;
          return {
            safeSerialized: JSON.stringify(safe),
            reviewSerialized: JSON.stringify(first),
            safePhases: safe.rows.map((row) => row.runtime.phase),
            first,
            sameCurrent: same.prior_review_current,
            changed: {
              ready: changed.ready,
              serverPriced: changed.server_priced,
              total: changed.total_estimated_cost_minor,
              priorCurrent: changed.prior_review_current,
              phases: changed.rows.map((row) => row.runtime.phase),
            },
            underlyingPhases: [...ready.rows.values()].map((row) =>
              row.runtime_state.phase),
          };
        })()
        """
    )
    for serialized_key in ("safeSerialized", "reviewSerialized"):
        serialized = result[serialized_key]
        assert "idempotency" not in serialized
        assert "strategy.probe:" not in serialized
        assert "strategy.start:" not in serialized
        assert "spend_confirmation" not in serialized
        assert "RUNWAY_PRODUCT_UGC" not in serialized
        assert "attestations" not in serialized
        assert "generation_strategy" not in serialized

    review = result["first"]
    assert result["safePhases"] == ["preflight_ready"] * 10
    assert review["display_only"] is True
    assert review["confirmation"] is False
    assert review["prior_review_current"] is False
    assert review["ready"] is True
    assert review["server_priced"] is True
    assert review["row_count"] == 10
    assert review["currency"] == "USD"
    assert review["total_estimated_cost_minor"] == 1920
    assert result["sameCurrent"] is True
    assert result["changed"] == {
        "ready": False,
        "serverPriced": False,
        "total": None,
        "priorCurrent": False,
        "phases": ["preflight_ready"] * 3
        + ["invalid"]
        + ["preflight_ready"] * 6,
    }
    assert result["underlyingPhases"] == ["preflight_ready"] * 10


def test_free_work_plan_is_ordered_descriptor_only_and_hard_capped_at_three() -> None:
    result = _evaluate(
        """
        (() => {
          const idle = mustCreate();
          const probeIds = idle.source_order;
          const probes = queueContract.planGenerationStrategyQueueFreeWork(
            idle, probeIds, 3,
          );
          const selected = selectAll(idle);
          const binds = queueContract.planGenerationStrategyQueueFreeWork(
            selected, [], 2,
          );
          const bound = bindAll(selected);
          const preflights = queueContract.planGenerationStrategyQueueFreeWork(
            bound, [], 3,
          );
          const tooWide = queueContract.planGenerationStrategyQueueFreeWork(
            idle, probeIds, 4,
          );
          return {
            probes, binds, preflights, tooWide,
            serialized: JSON.stringify({
              probes: probes.plan,
              binds: binds.plan,
              preflights: preflights.plan,
            }),
          };
        })()
        """
    )
    assert result["probes"]["ok"] is True
    assert result["probes"]["plan"]["max_concurrency"] == 3
    assert result["probes"]["plan"]["paid_start_allowed"] is False
    assert [item["work"] for item in result["probes"]["plan"]["items"]] == [
        "probe",
        "probe",
        "probe",
    ]
    assert [item["work"] for item in result["binds"]["plan"]["items"]] == [
        "bind",
        "bind",
    ]
    assert [item["work"] for item in result["preflights"]["plan"]["items"]] == [
        "preflight",
        "preflight",
        "preflight",
    ]
    assert len(
        {
            item["idempotency_key"]
            for plan_name in ("probes", "binds", "preflights")
            for item in result[plan_name]["plan"]["items"]
        }
    ) == 8
    assert result["tooWide"]["ok"] is False
    assert result["tooWide"]["error"]["code"] == "free_concurrency_invalid"
    assert "generation_strategy" not in result["serialized"]
    assert "attestations" not in result["serialized"]
    assert "assets" not in result["serialized"]
    assert "spec_id" not in result["serialized"]
    assert set(result["probes"]["plan"]["items"][0]) == {
        "source_media_id",
        "work",
        "runtime_fingerprint",
        "idempotency_key",
    }


def test_paid_start_plan_is_sequential_and_advances_only_after_safe_resolution() -> None:
    result = _evaluate(
        """
        (() => {
          const confirmed = confirmAll();
          const initial = queueContract.planGenerationStrategyQueueSequentialStarts(
            confirmed,
          );
          const premature = queueContract.advanceGenerationStrategyQueueSequentialStarts(
            confirmed, initial.plan,
          );
          const reserved = reserveStart(confirmed, 0);
          const blocked = queueContract.planGenerationStrategyQueueSequentialStarts(
            reserved,
          );
          const blockedAdvance =
            queueContract.advanceGenerationStrategyQueueSequentialStarts(
              reserved, initial.plan,
            );
          const failed = resolveStart(reserved, 0, 'failed');
          const advanced = queueContract.advanceGenerationStrategyQueueSequentialStarts(
            failed, initial.plan,
          );
          const invalidSecond = queueContract.invalidateGenerationStrategyQueueRow(
            failed, sourceId(1), 'source_changed',
          ).queue;
          const skipped = queueContract.planGenerationStrategyQueueSequentialStarts(
            invalidSecond,
          );
          return {
            initial, premature, blocked, blockedAdvance, advanced, skipped,
            confirmedCampaigns: new Set([...confirmed.rows.values()].map((row) =>
              row.runtime_state.campaign_id)).size,
            confirmedStartContexts: new Set([...confirmed.rows.values()].map((row) =>
              row.runtime_state.start_context_fingerprint)).size,
            phasesAfterFailure: [...failed.rows.values()].map((row) =>
              row.runtime_state.phase),
            statusesAfterFailure: [...failed.rows.values()].map((row) =>
              row.runtime_state.status?.job?.status || null),
          };
        })()
        """
    )
    initial = result["initial"]["plan"]
    assert initial["max_concurrency"] == 1
    assert initial["state"] == "ready"
    assert initial["next"]["source_media_id"].endswith("0000000003e9")
    assert initial["next"]["idempotency_key"] == "strategy.start:row-1"
    assert result["premature"]["plan"]["blocker"] == "previous_start_not_reserved"
    assert result["blocked"]["plan"]["blocker"] == "start_once_in_flight"
    assert result["blockedAdvance"]["plan"]["blocker"] == "start_once_in_flight"
    assert result["advanced"]["plan"]["state"] == "ready"
    assert result["advanced"]["plan"]["next"]["idempotency_key"] == (
        "strategy.start:row-2"
    )
    assert result["skipped"]["plan"]["state"] == "ready"
    assert result["skipped"]["plan"]["next"]["idempotency_key"] == (
        "strategy.start:row-3"
    )
    assert result["confirmedCampaigns"] == 1
    assert result["confirmedStartContexts"] == 10
    assert result["phasesAfterFailure"] == ["status"] + ["human_confirmed"] * 9
    assert result["statusesAfterFailure"] == ["failed"] + [None] * 9


def test_safe_nonterminal_status_advances_polling_independently_but_ambiguity_halts() -> None:
    result = _evaluate(
        """
        (() => {
          const confirmed = confirmAll();
          const reserved = reserveStart(confirmed, 0);
          const submitted = resolveStart(reserved, 0, 'submitted');
          const afterSubmitted =
            queueContract.planGenerationStrategyQueueSequentialStarts(submitted);
          const submittedState = submitted.rows.get(sourceId(0)).runtime_state;
          const untouchedSecond = submitted.rows.get(sourceId(1)).runtime_state;
          const processing = update(submitted, 0, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.statusResolved,
            fingerprint: submittedState.fingerprint,
            start_context_fingerprint: submittedState.start_context_fingerprint,
            generation_job_id: submittedState.status.job.id,
            response: statusResponse(0, 'processing'),
          });
          const afterProcessing =
            queueContract.planGenerationStrategyQueueSequentialStarts(processing);
          const safe = queueContract.generationStrategyQueueSafeProjection(processing);

          const ambiguousReserved = reserveStart(confirmAll(), 0);
          const ambiguousState = ambiguousReserved.rows.get(sourceId(0)).runtime_state;
          const ambiguous = update(ambiguousReserved, 0, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
            fingerprint: ambiguousState.fingerprint,
            start_context_fingerprint: ambiguousState.start_context_fingerprint,
            idempotency_key: ambiguousReserved.rows.get(sourceId(0))
              .idempotency_keys.start,
            response: reconciliationRequiredResponse(0),
          });
          const halted =
            queueContract.planGenerationStrategyQueueSequentialStarts(ambiguous);

          const laterReserved = reserveStart(confirmAll(), 5);
          const laterState = laterReserved.rows.get(sourceId(5)).runtime_state;
          const laterAmbiguous = update(laterReserved, 5, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startResolved,
            fingerprint: laterState.fingerprint,
            start_context_fingerprint: laterState.start_context_fingerprint,
            idempotency_key: laterReserved.rows.get(sourceId(5))
              .idempotency_keys.start,
            response: reconciliationRequiredResponse(5),
          });
          const globallyHalted =
            queueContract.planGenerationStrategyQueueSequentialStarts(
              laterAmbiguous,
            );
          return {
            afterSubmitted,
            afterProcessing,
            halted,
            globallyHalted,
            firstCanPoll: safe.rows[0].runtime.can_poll,
            secondPhase: safe.rows[1].runtime.phase,
            secondStateUntouched: untouchedSecond ===
              processing.rows.get(sourceId(1)).runtime_state,
            ambiguousStatus: ambiguous.rows.get(sourceId(0))
              .runtime_state.status,
            ambiguousSourceId: sourceId(0),
            laterAmbiguousSourceId: sourceId(5),
          };
        })()
        """
    )
    for plan_name in ("afterSubmitted", "afterProcessing"):
        plan = result[plan_name]["plan"]
        assert plan["state"] == "ready"
        assert plan["max_concurrency"] == 1
        assert plan["next"]["idempotency_key"] == "strategy.start:row-2"
    assert result["firstCanPoll"] is True
    assert result["secondPhase"] == "human_confirmed"
    assert result["secondStateUntouched"] is True
    assert result["halted"]["plan"] == {
        "version": "2026-08-14.v1",
        "max_concurrency": 1,
        "state": "blocked",
        "blocker": "reconciliation_required",
        "blocking_source_media_id": result["ambiguousSourceId"],
        "next": None,
    }
    assert result["ambiguousStatus"]["dispatch"]["outcome"] == "ambiguous"
    assert result["ambiguousStatus"]["reconciliation"]["required"] is True
    assert result["globallyHalted"]["plan"]["blocker"] == "reconciliation_required"
    assert result["globallyHalted"]["plan"]["blocking_source_media_id"] == (
        result["laterAmbiguousSourceId"]
    )


def test_wrong_start_key_invalidates_only_target_and_never_reserves_another_row() -> None:
    result = _evaluate(
        """
        (() => {
          const confirmed = confirmAll();
          const first = confirmed.rows.get(sourceId(0)).runtime_state;
          const wrong = update(confirmed, 0, {
            type: runtime.GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested,
            fingerprint: first.fingerprint,
            start_context_fingerprint: first.start_context_fingerprint,
            campaign_id: first.campaign_id,
            idempotency_key: confirmed.rows.get(sourceId(1)).idempotency_keys.start,
          });
          const plan = queueContract.planGenerationStrategyQueueSequentialStarts(wrong);
          return {
            phases: [...wrong.rows.values()].map((row) => row.runtime_state.phase),
            plan,
          };
        })()
        """
    )
    assert result["phases"] == ["invalid"] + ["human_confirmed"] * 9
    assert result["plan"]["plan"]["state"] == "ready"
    assert result["plan"]["plan"]["next"]["idempotency_key"] == (
        "strategy.start:row-2"
    )
