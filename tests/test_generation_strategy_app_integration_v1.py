from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
GUIDED = (ROOT / "web/app/workspace-os-v4-generation-guided.js").read_text(
    encoding="utf-8"
)


def _top_level_function(source: str, name: str) -> str:
    marker = f"function {name}("
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    quote: str | None = None
    escaped = False
    template_expression_depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if quote == "`" and char == "$" and source[index + 1 : index + 2] == "{":
                template_expression_depth += 1
                continue
            if char == quote and template_expression_depth == 0:
                quote = None
                continue
            if quote == "`" and template_expression_depth:
                if char == "{":
                    template_expression_depth += 1
                elif char == "}":
                    template_expression_depth -= 1
                continue
            continue
        if char in {'"', "'", "`"}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Function {name} is incomplete")


def _source_slice(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _evaluate_repeat(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy repeat contracts")
    repeat_normalizer = _top_level_function(
        APP, "normalizeGenerationStrategyRepeatEnvelope"
    )
    uuid_helper = _top_level_function(APP, "contentReviewUuid")
    script = f"""
{uuid_helper}
{repeat_normalizer}
const jobId = '11111111-1111-4111-8111-111111111111';
const specId = '22222222-2222-4222-8222-222222222222';
const productId = '33333333-3333-4333-8333-333333333333';
const sourceId = '44444444-4444-4444-8444-444444444444';
const avatarId = '55555555-5555-4555-8555-555555555555';
const productMediaId = '66666666-6666-4666-8666-666666666666';
const response = () => ({{
  ok: true,
  version: 'generation-strategy-repeat-response-v1',
  generation_job_id: jobId,
  legacy_strategy_absent: false,
  repeat_data: {{
    version: 'generation-strategy-repeat-data-v2',
    generation_job_id: jobId,
    strategy_id: 'viral_avatar_ugc',
    source_basis: 'exact_source_video',
    spec_strategy_binding_id: '77777777-7777-4777-8777-777777777777',
    spec_id: specId,
    spec_version: 4,
    spec_hash: 'a'.repeat(64),
    product_id: productId,
    job_strategy_snapshot_hash: 'b'.repeat(64),
    live_assets_current: true,
    selection_template: {{
      version: '2026-08-14.v1',
      strategy_id: 'viral_avatar_ugc',
      recipe_version: '2026-06',
      duration_seconds: 8,
      ratio: '720:1280',
      audio: true,
      assets: [
        {{role:'source_video',media_id:sourceId}},
        {{role:'avatar_image',media_id:avatarId}},
        {{role:'product_image',media_id:productMediaId}},
      ],
      attestations: {{
        source_media_rights_confirmed:false,
        transformative_use_confirmed:false,
        product_assets_rights_confirmed:false,
        depicted_people_consent_confirmed:false,
        avatar_likeness_consent_confirmed:false,
      }},
    }},
    price_reference: {{
      display_only:true,
      requires_fresh_server_price:true,
      price_hash:null,
      spend_confirmation:null,
    }},
    strategy_prompt_hash:'c'.repeat(64),
    binding_id:null,
    binding_hash:null,
    readiness_receipt_id:null,
    readiness_receipt_hash:null,
    confirmation:false,
    requires_fresh_binding:true,
    requires_fresh_human_confirmation:true,
    requires_fresh_provider_readiness_receipt:true,
    requires_fresh_price_confirmation:true,
  }},
  contract: {{
    read_only:true,
    legacy_null_preserved:true,
    confirmation_reused:false,
    readiness_receipt_reused:false,
    provider_call_started:false,
    mutation_started:false,
    selection_authority_reused:false,
    media_hash_authority_reused:false,
    attestations_reset:true,
    price_confirmation_reset:true,
  }},
}});
const value = {expression};
process.stdout.write(JSON.stringify(value));
"""
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "repeat.mjs"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_repeat_template_is_exact_and_never_restores_human_confirmations() -> None:
    result = _evaluate_repeat(
        "normalizeGenerationStrategyRepeatEnvelope(response(), jobId)"
    )
    assert result == {
        "strategyId": "viral_avatar_ugc",
        "liveAssetsCurrent": True,
        "values": {
            "generation_strategy_id": "viral_avatar_ugc",
            "generation_strategy_duration_seconds": 8,
            "generation_strategy_ratio": "720:1280",
            "generation_strategy_resolution": "",
            "generation_strategy_audio": "true",
            "generation_strategy_source_video_id":
                "44444444-4444-4444-8444-444444444444",
            "generation_strategy_avatar_media_id":
                "55555555-5555-4555-8555-555555555555",
            "generation_strategy_original_product_media_id": "",
            "generation_strategy_product_media_ids": [
                "66666666-6666-4666-8666-666666666666"
            ],
        },
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "value.repeat_data.selection_template.attestations.source_media_rights_confirmed=true",
        "value.repeat_data.price_reference.price_hash='d'.repeat(64)",
        "value.repeat_data.confirmation=true",
        "value.contract.selection_authority_reused=true",
        "value.repeat_data.selection_template.assets[0].media_id=productMediaId",
    ],
)
def test_repeat_rejects_reused_authority_or_changed_identity(mutation: str) -> None:
    result = _evaluate_repeat(
        f"(()=>{{const value=response(); {mutation}; return "
        "normalizeGenerationStrategyRepeatEnvelope(value,jobId);})()"
    )
    assert result is None


def test_repeat_handler_uses_dedicated_rpc_and_clears_every_paid_authority() -> None:
    handler = _top_level_function(APP, "repeatGenerationStrategyFromArchive")
    for marker in (
        "state.api.generationStrategyRepeatData",
        "normalizeGenerationStrategyRepeatEnvelope",
        "clearAllGenerationPreflightRetries();",
        "state.generationPreflight.entries.clear();",
        "resetGenerationSpecState();",
        'form.elements.real_spend_confirmation.checked = false',
        'form.elements.real_spend_confirmation.value = ""',
        'input.checked = false',
        '"contentengine:generation-restore-strategy"',
    ):
        assert marker in handler
    assert "startRealGeneration" not in handler
    assert "bindGenerationStrategy" not in handler

    click_handler = _source_slice(
        APP,
        "async function handleClick(event)",
        "async function handleSubmit(event)",
    )
    assert 'action === "repeat-generation-strategy"' in click_handler
    assert "repeatGenerationStrategyFromArchive(control.dataset.jobId, control)" in click_handler


def test_guided_restore_waits_for_server_candidates_and_never_restores_rights() -> None:
    restore = _top_level_function(GUIDED, "applyStrategyRestore")
    loader = _source_slice(
        GUIDED,
        "async function loadGenerationStrategyAssets",
        "function replaceStrategyOptions",
    )
    for marker in (
        "runtime.pendingStrategyRestore",
        "runtime.strategyAssetStatus",
        "loadGenerationStrategyAssets(form)",
        'input[data-generation-strategy-attestation]',
        "input.checked = false",
        "generation_strategy_product_media_ids",
    ):
        assert marker in restore
    assert "applyStrategyRestore(form, pendingRestore.values)" in loader


def test_archive_renders_only_frozen_strategy_selection_and_display_price() -> None:
    parser = _top_level_function(APP, "generationStrategyExecutionArchiveDetails")
    markup = _source_slice(
        APP,
        "function generationStrategyArchiveMarkup",
        "function generationBatchDetails",
    )
    for marker in (
        '"generation_strategy_execution_selection"',
        '"generation_strategy_price_reference"',
        'price.display_only !== true',
        'price.requires_fresh_server_price !== true',
        'price.price_hash !== null',
        'price.spend_confirmation !== null',
        'price.provider !== "runway"',
    ):
        assert marker in parser
    assert "state.generationModelCatalog" not in parser
    assert "generationSkuForForm" not in parser
    assert "strategyExecution" in markup
    assert "formatGenerationUsd(execution.estimatedCostMinor)" in markup


def test_strategy_runtime_is_a_separate_branch_before_legacy_mode_and_sku() -> None:
    submit_batch = _top_level_function(APP, "submitGenerationBatch")
    submit_strategy = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function pollGenerationStrategyStatuses",
    )
    assert submit_batch.index("if (strategyId)") < submit_batch.index(
        'const mode = String(values.get("generation_mode")'
    )
    assert "generationStrategySelectionsForForm(form)" in submit_batch
    assert "submitGenerationStrategyExactTen(" in submit_batch
    assert "submitGenerationStrategy(" in submit_batch
    assert "submitRealGeneration(" in submit_batch
    for forbidden in (
        "generationSkuForForm",
        "runGenerationPreflightForPaidStart",
        "startRealGeneration",
        "generation_selection_snapshot",
    ):
        assert forbidden not in submit_strategy
    for required in (
        "generationStrategyRuntimeBindRequest",
        "generationStrategyRuntimePreflightRequest",
        "generationStrategyRuntimeStartRequest",
        "generationStrategyRuntimeStatusRequest",
        "buildGenerationStrategySpecPrepareRequest",
        "buildGenerationStrategySpecApprovalRequest",
        "createGenerationStrategyQueue",
        "planGenerationStrategyQueueFreeWork",
        "planGenerationStrategyQueueSequentialStarts",
        "state.api.bindGenerationStrategy",
        "state.api.preflightGenerationStrategy",
        "requestApi.startGenerationStrategy",
        "requestApi.generationStrategyStatus",
    ):
        assert required in APP


def test_product_swap_dispatch_is_exactly_one_and_character_performance_is_closed() -> None:
    submit_batch = _top_level_function(APP, "submitGenerationBatch")
    selections = _top_level_function(APP, "generationStrategySelectionsForForm")

    assert "generationStrategySourceProjectionForForm(form)?.required_count" in selections
    assert "[1, 10].includes(requiredCount)" in selections
    assert "value.length === requiredCount" in selections

    swap_branch = submit_batch.index('strategyId === "viral_product_swap"')
    swap_count = submit_batch.index("sourceProjection.required_count === 1", swap_branch)
    swap_selection_count = submit_batch.index("strategySelections?.length === 1", swap_count)
    swap_submit = submit_batch.index("await submitGenerationStrategy(", swap_selection_count)
    rebuild_branch = submit_batch.index('strategyId === "viral_rebuild"', swap_submit)
    rebuild_count = submit_batch.index("sourceProjection.required_count === 10", rebuild_branch)
    rebuild_selection_count = submit_batch.index(
        "strategySelections?.length === 10", rebuild_count
    )
    rebuild_submit = submit_batch.index(
        "await submitGenerationStrategyExactTen(", rebuild_selection_count
    )
    gated_branch = submit_batch.index('strategyId === "viral_avatar_ugc"', rebuild_submit)
    legacy_branch = submit_batch.index(
        'const mode = String(values.get("generation_mode")', gated_branch
    )

    assert swap_branch < swap_count < swap_selection_count < swap_submit
    assert swap_submit < rebuild_branch < rebuild_count < rebuild_selection_count
    assert rebuild_selection_count < rebuild_submit < gated_branch < legacy_branch
    assert "Character Performance пока закрыт feature gate" in submit_batch
    assert "submitGenerationStrategy(" not in submit_batch[gated_branch:legacy_branch]
    assert "submitGenerationStrategyExactTen(" not in submit_batch[
        gated_branch:legacy_branch
    ]


def test_single_product_swap_uses_approved_strategy_spec_and_one_creator_runtime() -> None:
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategy(",
        "async function pollGenerationStrategyStatuses",
    )

    for marker in (
        'sourceProjection?.strategy_id !== "viral_product_swap"',
        "sourceProjection.required_count !== 1",
        "sourceProjection.all_selected_ready !== true",
        'selection?.strategy_id !== "viral_product_swap"',
        "prepareGenerationStrategySpecs(form, [currentEntry], projectId)",
        "approveGenerationStrategySpecs(form, [currentEntry], projectId)",
        "generationStrategyRuntimeContextForApprovedSpec(",
        "specRecord?.approvedContext || null",
        "requestApi.bindGenerationStrategy(bindPlan.request)",
        "requestApi.preflightGenerationStrategy(",
        "requestApi.startGenerationStrategy(startPlan.request)",
        "requestApi.bindRealGenerationClientContext(startPlan.request",
        "generationRequestContextIsCurrent(requestContext)",
        "state.api === requestApi",
        "!REAL_GENERATION_ENABLED",
    ):
        assert marker in submit

    for forbidden in (
        "currentApprovedGenerationSpecContext",
        "ensurePreparedGenerationSpecForPaidStart",
        "generationStrategyRuntimeContext(",
        "generationSkuForForm",
        "startRealGeneration",
    ):
        assert forbidden not in submit

    built = submit.index("generationStrategyRuntimeStartRequest(")
    reserved = submit.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested", built
    )
    transported = submit.index(
        "requestApi.startGenerationStrategy(startPlan.request)", reserved
    )
    verified = submit.index("const verified = reduceGenerationStrategyRuntimeState(")
    committed = submit.index("setGenerationStrategyRuntime(sourceMediaId, runtimeState)", verified)
    assert built < reserved < transported < verified < committed
    assert submit.count("requestApi.startGenerationStrategy(startPlan.request)") == 1


def test_single_product_swap_paid_review_uses_only_server_confirmation() -> None:
    readiness = _source_slice(
        APP,
        "function syncGenerationStrategySingleFormReadiness",
        "function syncGenerationStrategyFormReadiness",
    )
    unsupported = _top_level_function(
        APP, "syncUnsupportedGenerationStrategyFormReadiness"
    )
    reset = _source_slice(
        APP,
        "function resetGenerationStrategyQueueState",
        "function generationStrategyQueueProjection",
    )

    for marker in (
        'sourceProjection?.strategy_id === "viral_product_swap"',
        "sourceProjection.required_count === 1",
        "sourceProjection.selected_count === 1",
        "sourceProjection.exact_required_selected === true",
        "sourceProjection.all_selected_ready === true",
        'selections[0]?.selection?.strategy_id === "viral_product_swap"',
        "generationStrategyReceiptIsFresh(runtimeState)",
        "runtimeProjection.readiness.launch_enabled === true",
        "runtimeProjection.price.spend_confirmation",
        "confirmation.value === runtimeProjection?.price?.spend_confirmation",
        "REAL_GENERATION_ENABLED",
    ):
        assert marker in readiness
    assert "GENERATION_STRATEGY_EXACT_10" not in readiness
    assert 'strategyId === "viral_avatar_ugc"' in unsupported
    assert "Character Performance пока закрыт feature gate" in unsupported
    assert "generationStrategyHasPaidAuthority()" in reset


def test_single_expired_receipt_refresh_preserves_binding_and_other_paid_authority() -> None:
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategy(",
        "async function pollGenerationStrategyStatuses",
    )

    assert "generationStrategySingleHasOtherPaidAuthority(sourceMediaId)" in submit
    assert "createGenerationStrategyRuntimeFingerprint(context)" in submit
    selected = submit.index('if (runtimeState.phase === "selected")')
    bind_key = submit.index("generationStrategyRequestIdempotencyKey(", selected)
    bind_call = submit.index("requestApi.bindGenerationStrategy(bindPlan.request)")
    refresh = submit.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightRefreshRequested"
    )
    preflight = submit.index("requestApi.preflightGenerationStrategy(", refresh)
    assert selected < bind_key < bind_call < refresh < preflight
    assert "createGenerationStrategyRuntimeFingerprint(liveContext)" in submit
    assert "liveRuntime === expectedRuntime" in submit
    assert 'refreshRequested.phase !== "bound"' in submit
    assert "refreshRequested.bind?.binding?.id !== runtimeState.bind?.binding?.id" in submit
    assert "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.reset" not in submit
    assert "state.generationStrategyRequestKeys.delete(key)" not in submit


def test_status_poll_validates_off_copy_before_preserving_paid_state() -> None:
    poll = _top_level_function(APP, "pollGenerationStrategyStatuses")

    reduced = poll.index("const candidate = reduceGenerationStrategyRuntimeState(")
    guarded = poll.index('if (candidate?.phase !== "status")', reduced)
    queue_reduced = poll.index("const updated = updateGenerationStrategyQueueRow(", guarded)
    queue_committed = poll.index("state.generationStrategyQueue = updated.queue", queue_reduced)
    single_committed = poll.index("setGenerationStrategyRuntime(sourceMediaId, candidate)")
    assert reduced < guarded < queue_reduced < queue_committed
    assert guarded < single_committed
    assert "applyGenerationStrategyQueueRow(sourceMediaId, action)" not in poll
    assert "Последнее подтверждённое состояние и блокировка сохранены" in poll
    assert "повторный POST запрещён" in poll


def test_paid_strategy_reserves_runtime_start_before_network_and_never_rekeys() -> None:
    submit_strategy = _source_slice(
        APP,
        "async function startGenerationStrategyQueueSequentially",
        "function handleGenerationStrategySourcesChanged",
    )
    built = submit_strategy.index("generationStrategyRuntimeStartRequest(")
    reserved = submit_strategy.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested"
    )
    transported = submit_strategy.index(
        "requestApi.startGenerationStrategy(startPlan.request)"
    )
    assert built < reserved < transported
    assert "crypto.randomUUID()" not in submit_strategy
    assert "startPlan.request" in submit_strategy
    assert "bindRealGenerationClientContext(startPlan.request" in submit_strategy
    assert "generationRequestContextIsCurrent(requestContext)" in submit_strategy
    assert "state.api === requestApi" in submit_strategy
    assert 'currentRuntime?.phase === "start_once"' in submit_strategy
    assert "currentRuntime.start_context_fingerprint === reserved.start_context_fingerprint" in submit_strategy
    verified = submit_strategy.index("reduceGenerationStrategyRuntimeState(")
    committed = submit_strategy.index(
        "applyGenerationStrategyQueueRow(sourceMediaId, resolvedAction)"
    )
    assert transported < verified < committed


def test_exact_ten_paid_gate_requires_fresh_receipts_and_real_generation() -> None:
    confirmation = _top_level_function(
        APP, "confirmGenerationStrategyQueueForPaidStart"
    )
    sequential = _source_slice(
        APP,
        "async function startGenerationStrategyQueueSequentially",
        "function handleGenerationStrategySourcesChanged",
    )
    readiness = _source_slice(
        APP,
        "function syncGenerationStrategyFormReadiness",
        "async function probeSelectedGenerationStrategyMedia",
    )
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function submitGenerationStrategy(form,",
    )
    assert "!REAL_GENERATION_ENABLED" in confirmation
    assert "generationStrategyQueueReceiptsAreFresh" in confirmation
    assert "let confirmedQueue = state.generationStrategyQueue" in confirmation
    assert "state.generationStrategyQueue = confirmedQueue" in confirmation
    assert "!REAL_GENERATION_ENABLED" in sequential
    assert "generationStrategyReceiptIsFresh" in sequential
    assert sequential.index("generationStrategyReceiptIsFresh") < sequential.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested"
    )
    assert "receiptWindowReady" in readiness
    assert "&& REAL_GENERATION_ENABLED" in readiness
    assert "Обновить 10 точных цен" in readiness
    assert "resetGenerationStrategyQueueState({ clearSpecs: false })" not in submit
    assert "generationStrategyQueueReviewPreflightRefreshTargets()" in submit
    assert "refreshGenerationStrategyQueuePreflights(" in submit
    assert "state.generationStrategyQueueReview = refreshedReview.review" in submit
    assert "prepareGenerationStrategyQueueFree(form, selections, projectId)" in submit


def test_paid_resume_refreshes_only_unstarted_receipts_before_more_starts() -> None:
    targets = _top_level_function(
        APP, "generationStrategyQueuePreflightRefreshTargets"
    )
    refresh = _source_slice(
        APP,
        "async function refreshGenerationStrategyQueuePreflights",
        "function confirmGenerationStrategyQueueForPaidStart",
    )
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function submitGenerationStrategy(form,",
    )
    readiness = _source_slice(
        APP,
        "function syncGenerationStrategyFormReadiness",
        "async function probeSelectedGenerationStrategyMedia",
    )

    assert 'runtimeState?.phase !== "human_confirmed"' in targets
    assert "generationStrategyReceiptWindowMs(remaining)" in targets
    assert "remaining -= 1" in targets

    for marker in (
        '"preflight_refresh"',
        "oldReceipt.receipt_hash",
        "generationStrategyRuntimePreflightRequest(",
        "requestApi.preflightGenerationStrategy(operation.plan.request)",
        "Promise.allSettled",
        "generationRequestContextIsCurrent(requestContext)",
        "state.generationStrategyQueueSourceRevision !== sourceRevision",
        "live?.phase !== operation.priorPhase",
        "reduceGenerationStrategyRuntimeState(",
        "operation.requestState",
        'const expectedPhase = paidRefresh',
        'verified.phase !== expectedPhase',
        "verified.start_context_fingerprint === live.start_context_fingerprint",
        "applyGenerationStrategyQueueRow(",
        "clearGenerationStrategyRequestIdempotencyKey(operation.idempotency.key)",
    ):
        assert marker in refresh
    verified = refresh.index("const verified = reduceGenerationStrategyRuntimeState(")
    committed = refresh.index("applyGenerationStrategyQueueRow(", verified)
    assert verified < committed
    assert "GENERATION_STRATEGY_RUNTIME_ACTIONS.humanConfirmed" not in refresh
    assert "startGenerationStrategy" not in refresh

    paid_branch = submit.index("if (generationStrategyQueueHasPaidAuthority())")
    plan = submit.index("planGenerationStrategyQueueSequentialStarts(", paid_branch)
    ready_gate = submit.index('paidPlan.plan.state !== "ready"', plan)
    refresh_gate = submit.index(
        "if (generationStrategyQueuePaidReceiptsNeedRefresh())",
        ready_gate,
    )
    refresh_call = submit.index(
        "await refreshGenerationStrategyQueuePreflights(",
        refresh_gate,
    )
    paid_start = submit.index(
        "await startGenerationStrategyQueueSequentially(",
        refresh_call,
    )
    assert paid_branch < plan < ready_gate < refresh_gate < refresh_call < paid_start
    assert "ТЗ, ассеты, кампания и уже созданные job-ID сохранены" in submit
    assert "провайдер не запускался" in submit
    assert "Обновить проверки оставшихся роликов бесплатно" in readiness


def test_exact_ten_resume_and_spec_review_recovery_are_explicit() -> None:
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function submitGenerationStrategy(form,",
    )
    approvals = _source_slice(
        APP,
        "async function approveGenerationStrategySpecs",
        "async function prepareGenerationStrategyQueueFree",
    )
    review = _source_slice(
        APP,
        "function generationStrategySpecMechanicsMarkup",
        "function generationStrategySpecReviewMarkup",
    )
    paid_branch = submit.index("if (generationStrategyQueueHasPaidAuthority())")
    aggregate_branch = submit.index("const currentReview = state.generationStrategyQueue")
    assert paid_branch < aggregate_branch
    assert "planGenerationStrategyQueueSequentialStarts" in submit
    assert "startGenerationStrategyQueueSequentially" in submit
    assert "Promise.allSettled" in approvals
    assert 'result.status === "fulfilled"' in approvals
    assert "if (rejected) throw rejected.reason" in approvals
    for marker in (
        "selection.assets.map",
        "selection.attestations",
        "scope.platform",
        "scope.product_category",
        "scope.asset_snapshot.map",
        "scope.source",
        "scope.strategy_id",
        "scope.input_mode",
        "scope.reference_video",
        "scope.spoken_dialogue",
        "avatar_likeness_consent_confirmed",
    ):
        assert marker in review
    for forbidden in ("object_name", "signed_url", "sha256", "price_hash"):
        assert forbidden not in review
    assert 'goToStep?.("media")' in submit
    assert 'goToStep?.("launch")' in submit
    review_rows = _source_slice(
        APP,
        "function generationStrategySpecReviewMarkup",
        "function syncGenerationStrategySpecReviewUi",
    )
    assert "aria-labelledby" in review_rows
    assert "для ролика ${entry.position} из 10" in review_rows
    assert "Я прочитал(а) версию ролика ${entry.position} из 10" in review_rows


def test_mechanics_edit_invalidates_only_its_exact_queue_row() -> None:
    activity = _source_slice(
        APP,
        "function handleFormActivity",
        "function handleGenerationGuidedStepCommitted",
    )
    invalidator = _top_level_function(
        APP, "invalidateGenerationStrategyQueueSource"
    )
    ensure_queue = _source_slice(
        APP,
        "function ensureGenerationStrategyQueue",
        "function syncGenerationStrategyQueueUi",
    )
    assert "event.target.dataset?.generationStrategySourceMediaId" in activity
    assert 'startsWith("generation_strategy_mechanics_")' in activity
    assert "invalidateGenerationStrategyQueueSource(" in activity
    assert "state.generationStrategySpecs.delete(sourceMediaId)" in invalidator
    assert "state.generationStrategySpecRequestKeys.delete(sourceMediaId)" in invalidator
    assert "invalidateGenerationStrategyQueueRow(" in invalidator
    assert 'runtimeState?.phase !== "invalid"' in ensure_queue
    assert "GENERATION_STRATEGY_RUNTIME_ACTIONS.reset" in ensure_queue
    assert "GENERATION_STRATEGY_RUNTIME_ACTIONS.select" in ensure_queue


def test_asset_refresh_invalidates_only_when_selected_source_authority_changes() -> None:
    loader = _source_slice(
        GUIDED,
        "async function loadGenerationStrategyAssets",
        "function replaceStrategyOptions",
    )
    assert 'form.dataset.generationStrategyPaidLocked === "true"' in loader
    assert "const selectedAuthorityBefore = JSON.stringify" in loader
    assert "nextSourceProjection?.selected" in loader
    assert '"contentengine:generation-strategy-sources-changed"' in loader
    assert loader.index("nextSourceProjection?.selected") < loader.index(
        '"contentengine:generation-strategy-sources-changed"'
    )


def test_strategy_probe_is_free_explicit_and_refreshes_server_candidates() -> None:
    probe = _source_slice(
        APP,
        "async function probeSelectedGenerationStrategyMedia",
        "async function submitGenerationStrategyExactTen",
    )
    for marker in (
        "generationStrategyRuntimeProbeRequest",
        "state.api.probeGenerationStrategyMedia(plan.request)",
        "normalizeGenerationStrategyProbeResponse",
        "refreshStrategyAssets",
    ):
        assert marker in probe
    for forbidden in (
        "startGenerationStrategy",
        "bindGenerationStrategy",
        "preflightGenerationStrategy",
    ):
        assert forbidden not in probe
    assert 'data-action="probe-generation-strategy-media"' in APP


def test_strategy_disables_blank_required_legacy_mode_without_model_proxy() -> None:
    visibility = _top_level_function(GUIDED, "syncLegacyModelVisibility")
    assert "modeControl.disabled = strategySelected" in visibility
    assert "modeControl.required = !strategySelected" in visibility
    assert 'model.model === "seedance2_fast"' not in GUIDED
    assert "const proxyModel" not in GUIDED
    assert 'advisor.dataset.strategyAdvisoryOnly = strategySelected ? "true" : "false"' in visibility
