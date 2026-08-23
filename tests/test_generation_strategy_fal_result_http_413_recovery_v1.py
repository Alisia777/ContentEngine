from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from pglast import parse_sql
import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202608210002_generation_strategy_fal_result_http_413_recovery_v1.sql"
)
PGTAP = (
    ROOT
    / "supabase/tests/generation_strategy_fal_result_http_413_recovery_test.sql"
)
INCIDENT_PGTAP = (
    ROOT
    / "supabase/incidents/generation_strategy_fal_result_http_413_exact_incident_test.sql"
)
ROLLBACK_ENVELOPE_BUILDER = ROOT / "scripts/build_rollback_only_413_envelope.py"
# Архив инцидента живёт в репозитории: .dev-artifacts/ в .gitignore, и тест,
# читавший его оттуда, был зелёным только на машине, где инцидент разбирали.
ROLLBACK_INVARIANTS = (
    ROOT
    / "supabase/incidents/generation_strategy_fal_result_http_413_post_invariants_readonly.sql"
)
CONTRACT = ROOT / "supabase/functions/_shared/generation-strategy-edge-contract.js"
EDGE = ROOT / "supabase/functions/creator-generate/index.ts"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _evaluate_contract(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for fal recovery contract tests")
    catalog = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        for source in (CONTRACT, catalog):
            (directory / source.name).write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
        (directory / "run.js").write_text(
            f"import * as subject from './{CONTRACT.name}';\n"
            f"const result = await ({expression});\n"
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


def test_new_migration_and_pgtap_are_valid_append_only_sql() -> None:
    migration = _source(MIGRATION)
    pgtap = _source(PGTAP)
    incident_pgtap = _source(INCIDENT_PGTAP)

    assert parse_sql(migration)
    assert parse_sql(pgtap)
    assert parse_sql(incident_pgtap)
    assert migration.startswith("begin;\n")
    assert migration.rstrip().endswith("commit;")
    assert pgtap.startswith("begin;\n")
    assert pgtap.rstrip().endswith("rollback;")
    assert incident_pgtap.startswith("begin;\n")
    assert incident_pgtap.rstrip().endswith("rollback;")
    assert len(list((ROOT / "supabase/migrations").glob("202608210002_*.sql"))) == 1

    # The already-applied 200005/200006 migrations are history, not edit targets.
    assert "202608200005" not in MIGRATION.name
    assert "202608200006" not in MIGRATION.name


def test_constraint_reapply_is_safe_and_only_adds_reviewed_413_recovery() -> None:
    source = _source(MIGRATION)

    assert "generation_strategy_provider_status_transition_v2_check" in source
    assert "generation_strategy_provider_status_transition_v3_check" in source
    assert source.count("add constraint generation_strategy_provider_status_transition_v3_check") == 1
    assert "execute $ddl$" in source
    assert source.index("execute $ddl$") < source.index(
        "$replace_fal_result_recovery_transition$;"
    )
    assert "if v2_count_value = 0 and v3_count_value = 1 then" in source
    assert "if v2_count_value <> 1 or v3_count_value <> 0 then" in source
    assert "provider_result_route_recovery_transition_cardinality_invalid" in source
    assert "return;" in source.split(
        "$replace_fal_result_recovery_transition$;", 1
    )[0]
    verify = source.split("do $verify_fal_result_route_recovery$", 1)[1]
    assert "v2_count_value <> 0" in verify
    assert "v3_count_value <> 1" in verify

    constraint = source.split("execute $ddl$", 1)[1].split("$ddl$;", 1)[0]
    for invariant in (
        "previous_status = 'failed'",
        "provider_status = 'succeeded'",
        "strategy-result-recovery:%",
        "generation-strategy-provider-result-recovery-v1",
        "provider_result_http_405",
        "provider_result_http_413",
    ):
        assert invariant in constraint
    assert "provider_result_http_401" not in constraint


def test_rpc_patch_binds_confirmation_to_latest_immutable_failure_code() -> None:
    source = _source(MIGRATION)

    for confirmation in (
        "FAL_RESULT_HTTP_405_RECOVERY_VERIFIED",
        "FAL_RESULT_HTTP_413_RECOVERY_VERIFIED",
    ):
        assert confirmation in source
    for failure_code in (
        "provider_result_http_405",
        "provider_result_http_413",
    ):
        assert failure_code in source

    assert "latest_event_row.failure_code is null" in source
    assert (
        "latest_event_row.failure_code not in (\n"
        "       'provider_result_http_405', 'provider_result_http_413'"
        in source
    )
    assert (
        "(job_row.output ->> 'failure_code') is distinct from\n"
        "       latest_event_row.failure_code"
        in source
    )
    assert (
        "(job_row.output ->> 'provider_failure_code') is distinct from\n"
        "       latest_event_row.failure_code"
        in source
    )
    assert (
        "(task_row.result ->> 'failure_code') is distinct from\n"
        "       latest_event_row.failure_code"
        in source
    )
    assert source.count(
        "'recovered_failure_code', latest_event_row.failure_code"
    ) >= 2
    assert (
        "(job_row.input #>> '{strategy_execution,strategy_id}')\n"
        "       is distinct from receipt_row.strategy_id"
        in source
    )


def test_replay_is_code_and_confirmation_bound_not_merely_idempotent() -> None:
    source = _source(MIGRATION)
    replay = source.split("$replacement$       or not (", 1)[1].split(
        "$replacement$", 1
    )[0]

    assert "event_row.output_snapshot ->> 'recovered_failure_code'" in replay
    assert "provider_result_http_405" in replay
    assert "provider_result_http_413" in replay
    assert "FAL_RESULT_HTTP_405_RECOVERY_VERIFIED" in replay
    assert "FAL_RESULT_HTTP_413_RECOVERY_VERIFIED" in replay
    assert "input_payload ->> 'confirmation'" in replay


def test_recovery_writer_stays_get_only_append_only_and_ledger_immutable() -> None:
    source = _source(MIGRATION).casefold()
    edge = _source(EDGE)
    poll = edge.split("const pollGenerationStrategyProvider = async (", 1)[1]
    poll = poll.split("// Diagnostic probe:", 1)[0]

    assert 'method: "post"' not in poll.casefold()
    assert "method: 'post'" not in poll.casefold()
    assert 'method: "get"' in poll.casefold()
    assert "system_recover_generation_strategy_provider_result" in poll
    assert "provider_result_http_${providerrefusedstatus}" not in poll.casefold()
    assert 'recoveryexit("result_get_refused")' in poll.casefold()
    assert 'recoveryexit("result_routes_exhausted")' in poll.casefold()

    # The migration only patches the pre-existing writer and verifies that it
    # still contains no spend DML. It never invokes the writer or a provider.
    assert "select public.system_recover_generation_strategy_provider_result(" not in source
    assert "http_post" not in source
    assert "net.http" not in source
    assert "pg_net" not in source
    assert "fetch(" not in source
    assert "ledger_hash_after_value is distinct from ledger_hash_before_value" in source
    assert "update content_factory.generation_strategy_provider_status_events" in source
    assert "position(" in source


def test_exact_provider_response_url_precedes_bare_fallbacks() -> None:
    contract = _source(CONTRACT)
    fetcher = contract.split("export async function fetchFalQueueResult({", 1)[1]
    fetcher = fetcher.split("export function falStrategyProviderStatus", 1)[0]

    exact = 'pushCandidate("provider_response_exact", statusResultUrl);'
    bare = 'pushCandidate("provider_response_bare", statusBareResultUrl);'
    synthesized = "for (let index = 0; index < resultUrls.length; index += 1)"
    assert exact in fetcher and bare in fetcher and synthesized in fetcher
    assert fetcher.index(exact) < fetcher.index(bare) < fetcher.index(synthesized)
    assert "pathname.endsWith(`/requests/${requestId}/response`)" in contract
    assert "attempt.status === 413" in fetcher
    assert 'candidateClass: candidate.candidateClass' in fetcher
    assert 'outcome: "redirect"' not in fetcher
    assert '? "redirect"' in fetcher
    assert "url: normalized" in fetcher
    # URL is used only to perform the read; returned diagnostics are a closed
    # class/outcome/status triple and cannot carry provider payloads or keys.
    returned = fetcher.split("attempts.push({", 1)[1]
    assert "candidateClass" in returned
    assert "outcome" in returned
    assert "status" in returned


def test_official_stored_output_fallback_is_exact_and_identity_bound() -> None:
    result = _evaluate_contract(
        """
        (() => {
          const modelKey = "fal-ai/pika/v2/pikaswaps";
          const requestId = "01a0232c-2253-7553-a95f-316eec7bffe7";
          const validPayload = {
            items: [{
              request_id: requestId,
              endpoint_id: modelKey,
              status_code: 200,
              json_output: {video: {url: "https://v3.fal.media/grill.mp4"}},
            }],
            has_more: false,
            next_cursor: null,
          };
          return {
            url: subject.falModelRequestPayloadUrl(modelKey, requestId),
            invalidModelUrl: subject.falModelRequestPayloadUrl(
              "attacker/model", requestId
            ),
            invalidRequestUrl: subject.falModelRequestPayloadUrl(
              modelKey, "not-a-fal-request"
            ),
            valid: subject.readFalModelRequestOutput(
              validPayload, modelKey, requestId, 200
            ),
            http201: subject.readFalModelRequestOutput(
              validPayload, modelKey, requestId, 201
            ),
            non200: subject.readFalModelRequestOutput({items: [{
              ...validPayload.items[0], status_code: 413,
            }], has_more: false, next_cursor: null}, modelKey, requestId, 200),
            wrongRequest: subject.readFalModelRequestOutput({...validPayload, items: [{
              ...validPayload.items[0], request_id:
                "01a0232c-2253-7553-a95f-316eec7bffe8",
            }]}, modelKey, requestId, 200),
            wrongModel: subject.readFalModelRequestOutput({...validPayload, items: [{
              ...validPayload.items[0], endpoint_id: "fal-ai/pika",
            }]}, modelKey, requestId, 200),
            multiple: subject.readFalModelRequestOutput({...validPayload, items: [
              validPayload.items[0], validPayload.items[0],
            ]}, modelKey, requestId, 200),
            hasMore: subject.readFalModelRequestOutput({
              ...validPayload, has_more: true,
            }, modelKey, requestId, 200),
            nextCursor: subject.readFalModelRequestOutput({
              ...validPayload, next_cursor: "Mg==",
            }, modelKey, requestId, 200),
          };
        })()
        """
    )

    assert result == {
        "url": (
            "https://api.fal.ai/v1/models/requests/by-endpoint?"
            "endpoint_id=fal-ai%2Fpika%2Fv2%2Fpikaswaps&"
            "request_id=01a0232c-2253-7553-a95f-316eec7bffe7&"
            "expand=payloads&limit=2"
        ),
        "invalidModelUrl": None,
        "invalidRequestUrl": None,
        "valid": {
            "statusCode": 200,
            "output": {"video": {"url": "https://v3.fal.media/grill.mp4"}},
        },
        "http201": None,
        "non200": None,
        "wrongRequest": None,
        "wrongModel": None,
        "multiple": None,
        "hasMore": None,
        "nextCursor": None,
    }


def test_stored_output_fallback_is_recovery_only_get_and_evidence_bound() -> None:
    edge = _source(EDGE)
    poll = edge.split("const pollGenerationStrategyProvider = async (", 1)[1]
    fallback = poll.split(
        "// Recovery only: fal's documented model-request Platform API", 1
    )[1].split("const videoUrl = readFalResultVideoUrl", 1)[0]

    assert "if (recoveryMode && falModelKey !== null)" in fallback
    assert "falModelRequestPayloadUrl(" in fallback
    assert "readFalModelRequestOutput(" in fallback
    assert 'method: "GET"' in fallback
    assert 'redirect: "manual"' in fallback
    assert 'accept: "application/json"' in fallback
    assert "authorization: `Key ${secret}`" in fallback
    assert 'method: "POST"' not in fallback
    assert "payloadResponse.status !== 200" in fallback
    assert "stored_result_shape_invalid" in fallback
    evidence = poll.split("const evidenceHash = await sha256Hex", 1)[1].split(
        "let output:", 1
    )[0]
    assert "stored_result: falStoredResultEvidence" in evidence
    assert 'version: "fal-model-request-payload-v1"' in poll


def test_pgtap_covers_413_confirmation_replay_money_and_no_repost() -> None:
    pgtap = _source(PGTAP)
    for contract in (
        "FAL_RESULT_HTTP_413_RECOVERY_VERIFIED",
        "provider_result_http_413",
        "replay rechecks",
        "generation_spend_ledger",
        "ledger unchanged",
        "service-role only",
        "unreviewed result HTTP code",
        "append",
    ):
        assert contract in pgtap


def test_exact_incident_runtime_pgtap_executes_fresh_replay_and_rolls_back() -> None:
    source = _source(INCIDENT_PGTAP)

    for identity in (
        "88504197-4f6a-4159-9797-6f89cba92db9",
        "01a0232c-2253-7553-a95f-316eec7bffe7",
        "provider_result_http_413",
        "FAL_RESULT_HTTP_413_RECOVERY_VERIFIED",
        "FAL_RESULT_HTTP_405_RECOVERY_VERIFIED",
    ):
        assert identity in source
    assert source.count(
        "select public.system_recover_generation_strategy_provider_result("
    ) == 2
    assert "perform public.system_recover_generation_strategy_provider_result(" in source
    assert "fresh_response -> 'replay' = 'false'::jsonb" in source
    assert "replay_response -> 'replay' = 'true'::jsonb" in source
    assert "ledger_hash_before = ledger_hash_after" in source
    assert "ledger_hash_after = ledger_hash_after_replay" in source
    assert "event_count_after_replay = event_count_after" in source
    assert "dispatch_count_after_replay = dispatch_count_before" in source
    assert "task.result ->> 'review_mode' = 'manual_human_review'" in source
    for fail_hard_guard in (
        "exact_incident_413_fail_hard_wrong_confirmation",
        "exact_incident_413_fail_hard_fresh_receipt",
        "exact_incident_413_fail_hard_replay_receipt",
        "exact_incident_413_fail_hard_ledger_changed",
        "exact_incident_413_fail_hard_cardinality",
        "exact_incident_413_fail_hard_recovered_event_projection",
        "exact_incident_413_fail_hard_original_failure_changed",
        "exact_incident_413_fail_hard_job_batch_task_projection",
        "exact_incident_413_fail_hard_media_projection",
    ):
        assert fail_hard_guard in source
    assert "is not true then" in source
    assert source.rstrip().endswith("rollback;")


def test_rollback_only_builder_and_read_audit_are_fail_closed() -> None:
    builder = _source(ROLLBACK_ENVELOPE_BUILDER)
    audit = _source(ROLLBACK_INVARIANTS)

    assert '"begin;"' in builder
    assert '"rollback;"' in builder
    assert "set local lock_timeout = '5s';" in builder
    assert "set local statement_timeout = '120s';" in builder
    assert "set local idle_in_transaction_session_timeout = '120s';" in builder
    assert "inner top-level commit remains" in builder
    assert "rollback cardinality invalid" in builder
    assert "forbidden network/dispatch primitive" in builder
    assert "incident_body.casefold().count" in builder

    assert parse_sql(audit)
    assert "insert " not in audit.casefold()
    assert "update " not in audit.casefold()
    assert "delete " not in audit.casefold()
    assert "migration_202608210002_count" in audit
    for invariant in (
        "migration_history",
        "job",
        "events",
        "ledger",
        "dispatch",
        "media",
        "storage",
        "task",
        "batch",
    ):
        assert f"'{invariant}'" in audit
