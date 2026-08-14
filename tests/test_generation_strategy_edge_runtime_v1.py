from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "supabase/functions/_shared/generation-strategy-edge-contract.js"
CATALOG = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
EDGE = ROOT / "supabase/functions/creator-generate/index.ts"
WORKER = ROOT / "supabase/functions/creator-background-worker/index.ts"


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy Edge contract tests")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        (directory / CONTRACT.name).write_text(
            CONTRACT.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (directory / CATALOG.name).write_text(
            CATALOG.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (directory / "run.js").write_text(
            f"import * as subject from './{CONTRACT.name}';\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "run.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_create_outcome_classifier_is_total_and_never_implies_retry() -> None:
    result = _evaluate(
        """
        (() => {
          const response = (status, providerTaskId = null) =>
            subject.classifyRunwayRecipeCreateOutcome({kind:'response', status, providerTaskId});
          return {
            submitted: response(200, 'task_abc-123'),
            invalid2xx: response(200, null),
            network: subject.classifyRunwayRecipeCreateOutcome({kind:'network'}),
            statuses: [400,401,402,403,404,405,408,422,425,429,302,500,503]
              .map((status) => [status, response(status)]),
            preDispatch: ['input_signing_failed','input_asset_not_current','signed_url_invalid']
              .map((code) => subject.preDispatchStrategyFailure(code)),
          };
        })()
        """
    )
    assert result["submitted"] == {
        "outcome": "submitted",
        "provider_post_started": True,
        "provider_http_status": 200,
        "provider_task_id": "task_abc-123",
        "failure_code": None,
    }
    for item in (result["invalid2xx"], result["network"]):
        assert item["outcome"] == "ambiguous"
        assert item["provider_post_started"] is True
        assert item["provider_task_id"] is None
        assert item["failure_code"] == "provider_submission_ambiguous"

    by_status = dict(result["statuses"])
    deterministic = {400, 401, 402, 403, 404, 405, 422, 429}
    for status, item in by_status.items():
        if int(status) in deterministic:
            assert item["outcome"] == "rejected"
        else:
            assert item["outcome"] == "ambiguous"
        assert item["provider_post_started"] is True
        assert item["provider_task_id"] is None

    assert {item["failure_code"] for item in result["preDispatch"]} == {
        "input_signing_failed",
        "input_asset_not_current",
        "signed_url_invalid",
    }
    assert all(item["provider_post_started"] is False for item in result["preDispatch"])


def test_preflight_public_projection_strips_prompt_and_spend_authority() -> None:
    result = _evaluate(
        """
        (() => {
          const h = (c) => c.repeat(64);
          const bindingId = '11111111-1111-4111-8111-111111111111';
          const value = {
            ok:true,
            version:'generation-strategy-readiness-record-response-v1',
            replay:false,
            receipt:{
              id:'22222222-2222-4222-8222-222222222222', receipt_hash:h('a'),
              binding_id:bindingId, binding_hash:h('b'),
              strategy_id:'viral_avatar_ugc', recipe:'product_ugc',
              catalog_version:'2026-08-14.v1', recipe_version:'2026-06',
              pricing_version:'runway-recipe-credits-2026-08-14.v1',
              selection_hash:h('c'), price_hash:h('d'),
              spend_confirmation:'RUNWAY_PRODUCT_UGC_8S_720P_AUDIO_USD_3.36',
              strategy_prompt_hash:h('e'), ready:true, failure_code:null,
              checked_at:'2026-08-14T10:00:00.000Z',
              expires_at:'2026-08-14T10:15:00.000Z',
            },
            strategy_prompt:{secret:'must-not-leak'},
            provider_preflight:{
              credential_configured:true, provider_authentication_confirmed:true,
              recipe_catalog_supported:true, recipe_precheck_supported:false,
              recipe_available:null, balance_sufficient:true,
              daily_quota_precheck_supported:false, daily_quota_available:null,
            },
            contract:{
              provider_call_started:false, paid_start_authorized:false,
              receipt_single_use:true, browser_price_authority:false,
              browser_prompt_authority:false,
            },
          };
          const parsed = subject.readGenerationStrategyReadiness(value, {
            bindingId, bindingHash:h('b'), selectionHash:h('c'), priceHash:h('d'),
            spendConfirmation:'RUNWAY_PRODUCT_UGC_8S_720P_AUDIO_USD_3.36',
          });
          return {publicResult:parsed?.publicResult, internalPrompt:parsed?.strategyPrompt};
        })()
        """
    )
    public_result = result["publicResult"]
    assert public_result["version"] == "generation-strategy-preflight-response-v1"
    assert public_result["launch_enabled"] is False
    assert set(public_result["receipt"]) == {
        "id",
        "receipt_hash",
        "binding_id",
        "binding_hash",
        "strategy_id",
        "recipe",
        "catalog_version",
        "recipe_version",
        "pricing_version",
        "selection_hash",
        "price_hash",
        "ready",
        "failure_code",
        "checked_at",
        "expires_at",
    }
    serialized = json.dumps(public_result)
    assert "spend_confirmation" not in serialized
    assert "strategy_prompt_hash" not in serialized
    assert "must-not-leak" not in serialized
    assert result["internalPrompt"] == {"secret": "must-not-leak"}


def test_public_status_reader_requires_every_frozen_nested_keyset() -> None:
    result = _evaluate(
        """
        (() => {
          const clone = (value) => JSON.parse(JSON.stringify(value));
          const ids = {
            project:'11111111-1111-4111-8111-111111111111',
            campaign:'22222222-2222-4222-8222-222222222222',
            job:'33333333-3333-4333-8333-333333333333',
            batch:'44444444-4444-4444-8444-444444444444',
            binding:'55555555-5555-4555-8555-555555555555',
            receipt:'66666666-6666-4666-8666-666666666666',
            source:'77777777-7777-4777-8777-777777777777',
            avatar:'88888888-8888-4888-8888-888888888888',
            product:'99999999-9999-4999-8999-999999999999',
            dispatch:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          };
          const h = (value) => value.repeat(64);
          const base = {
            ok:true, version:'generation-strategy-status-response-v1',
            job:{id:ids.job,batch_id:ids.batch,project_id:ids.project,
              campaign_id:ids.campaign,status:'queued',provider_status:null,
              provider_task_id:null,estimated_cost_minor:192,
              actual_cost_minor:null,currency:'USD',
              created_at:'2026-08-14T08:00:00.000Z',
              updated_at:'2026-08-14T08:00:01.000Z'},
            strategy:{version:'generation-strategy-immutable-execution-v1',
              strategy_id:'viral_avatar_ugc',recipe:'product_ugc',
              catalog_version:'2026-08-14.v1',recipe_version:'2026-06',
              pricing_version:'runway-recipe-credits-2026-08-14.v1',
              binding_id:ids.binding,binding_hash:h('a'),
              receipt_id:ids.receipt,receipt_hash:h('b'),
              selection_hash:h('c'),price_hash:h('d'),
              strategy_prompt_hash:h('e')},
            selection:{version:'2026-08-14.v1',
              strategy_id:'viral_avatar_ugc',recipe_version:'2026-06',
              duration_seconds:4,ratio:'720:1280',audio:false,
              assets:[
                {role:'source_video',media_id:ids.source},
                {role:'avatar_image',media_id:ids.avatar},
                {role:'product_image',media_id:ids.product},
              ],
              attestations:{source_media_rights_confirmed:true,
                transformative_use_confirmed:true,
                product_assets_rights_confirmed:true,
                depicted_people_consent_confirmed:true,
                avatar_likeness_consent_confirmed:true}},
            price:{version:'generation-strategy-price-snapshot-v1',
              strategy_id:'viral_avatar_ugc',provider:'runway',
              recipe:'product_ugc',input_mode:'character_and_product_images',
              duration_seconds:4,resolution:'720p',ratio:'720:1280',
              audio:false,estimated_credits:192,
              estimated_pre_tax_usd_minor:192,estimated_cost_minor:192,
              estimated_cost_usd:'1.92',currency:'USD',
              credit_unit_cost_minor:1,catalog_version:'2026-08-14.v1',
              pricing_version:'runway-recipe-credits-2026-08-14.v1',
              recipe_version:'2026-06',price_hash:h('d')},
            dispatch:null,reconciliation:null,output:null,error:null,
            contract:{recipe_aware:true,legacy_model_catalog_used:false,
              poll_provider_allowed:false,second_post_allowed:false,
              object_names_returned:false,media_hashes_returned:false,
              signed_urls_returned:false,manual_human_review_required:false},
          };
          const read = (value) => subject.readPublicGenerationStrategyStatus(
            value, {projectId:ids.project,generationJobId:ids.job}
          ) !== null;
          const submitted = clone(base);
          submitted.job.status = 'submitted';
          submitted.job.provider_task_id = 'runway-task-001';
          submitted.dispatch = {result_id:ids.dispatch,result_hash:h('f'),
            outcome:'submitted',provider_post_started:true,
            provider_http_status:201,
            recorded_at:'2026-08-14T08:00:02.000Z'};
          submitted.contract.poll_provider_allowed = true;
          const dispatchExtra = clone(submitted);
          dispatchExtra.dispatch.dispatch_token = ids.dispatch;
          const priceExtra = clone(base); priceExtra.price.spend_confirmation = 'secret';
          const selectionExtra = clone(base); selectionExtra.selection.provider_path = '/unsafe';
          const badPoll = clone(base); badPoll.contract.poll_provider_allowed = true;
          const badOutput = clone(base);
          badOutput.output = {media_id:ids.product,mime_type:'video/webm',size_bytes:1};
          return {valid:read(base),submitted:read(submitted),
            dispatchExtra:read(dispatchExtra),priceExtra:read(priceExtra),
            selectionExtra:read(selectionExtra),badPoll:read(badPoll),
            badOutput:read(badOutput)};
        })()
        """
    )
    assert result == {
        "valid": True,
        "submitted": True,
        "dispatchExtra": False,
        "priceExtra": False,
        "selectionExtra": False,
        "badPoll": False,
        "badOutput": False,
    }


def test_edge_actions_are_per_item_and_share_one_dispatch_continuation() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    for action in (
        "strategy_media_probe",
        "strategy_preflight",
        "strategy_start",
        "strategy_status",
        "strategy_reconcile",
    ):
        assert f'"{action}"' in edge
    for rpc in (
        "system_generation_strategy_media_probe_context",
        "system_record_generation_strategy_media_duration",
        "system_record_generation_strategy_readiness",
        "system_claim_generation_strategy_start",
        "system_mark_generation_strategy_dispatch_attempt",
        "system_record_generation_strategy_dispatch_result",
        "system_record_generation_strategy_provider_status",
        "system_generation_strategy_status",
    ):
        assert f'"{rpc}"' in edge
    assert "const continueGenerationStrategyClaim = async (" in edge
    assert edge.count("continueGenerationStrategyClaim({") == 2
    assert "strategy-dispatch-attempt:${identity.claimId}" in edge
    assert "strategy-dispatch-result:${identity.attemptId}" in edge
    assert "generationJobId" in edge
    assert "campaignId" in edge


def test_strategy_payload_parsers_keep_spend_cents_and_exact_start_subset() -> None:
    edge = EDGE.read_text(encoding="utf-8")

    spend_parser = edge.split(
        "function readStrategySpendConfirmation", 1
    )[1].split("function readGenerationStrategyPayload", 1)[0]
    assert "Number(match[5]) * 100 + Number(match[6])" in spend_parser
    assert "Number(match[6]) * 100 + Number(match[7])" not in spend_parser

    start_parser = edge.split(
        "function readGenerationStrategyStartPayload", 1
    )[1].split("function readGenerationStrategyWorkerContext", 1)[0]
    assert 'action: "strategy_preflight"' in start_parser
    for field in (
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
    ):
        assert f"{field}: value.{field}" in start_parser
    assert "...value" not in start_parser
    assert "receipt_id: value.receipt_id" not in start_parser
    assert "campaign_id: value.campaign_id" not in start_parser


def test_worker_uses_exact_claim_ledger_and_dispatch_unknown_never_posts() -> None:
    worker = WORKER.read_text(encoding="utf-8")
    edge = EDGE.read_text(encoding="utf-8")
    assert '"system_claim_generation_strategy_worker_candidates"' in worker
    assert "organization_id: null" in worker
    assert 'phase: "all"' in worker
    assert 'action: "strategy_status"' in worker
    assert "generation_strategy_start_claims" in worker
    assert "!strategyClaimJobIds.has(row.id)" in worker
    assert 'outcome.kind !== "generation" || outcome.strategy' in worker

    unknown = edge.split(
        'if (worker.phase === "dispatch_unknown")', 1
    )[1].split('if (\n        worker.phase === "provider_poll"', 1)[0]
    assert "recordGenerationStrategyDispatchResult(" in unknown
    assert "classifyRunwayRecipeCreateOutcome({" in unknown
    assert "fetchProviderJsonWithDeadline(" not in unknown
    assert "buildGenerationStrategyProviderRequest(" not in unknown
