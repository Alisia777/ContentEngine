from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase/migrations/202608030011_research_youtube_live_ingestion.sql"
)
PGTAP_PATH = ROOT / "supabase/tests/research_youtube_live_ingestion_test.sql"
VIEW_PATH = ROOT / "web/app/product-research-view.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sql_function(source: str, qualified_name: str) -> str:
    header = re.compile(
        rf"\bcreate\s+(?:or\s+replace\s+)?function\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        re.IGNORECASE,
    )
    match = header.search(source)
    assert match is not None, f"SQL function {qualified_name} is missing"
    next_function = re.search(
        r"\bcreate\s+(?:or\s+replace\s+)?function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_function is None else match.end() + next_function.start()
    return source[match.start() : end]


def _sql_table(source: str, qualified_name: str) -> str:
    header = re.compile(
        rf"\bcreate\s+table\s+if\s+not\s+exists\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        re.IGNORECASE,
    )
    match = header.search(source)
    assert match is not None, f"SQL table {qualified_name} is missing"
    next_table = re.search(
        r"\bcreate\s+table\s+if\s+not\s+exists\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_table is None else match.end() + next_table.start()
    return source[match.start() : end]


def _compact(source: str) -> str:
    return re.sub(r"\s+", " ", source.casefold()).strip()


def _run_view_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable YouTube UI contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            _read(VIEW_PATH), encoding="utf-8"
        )
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
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_youtube_migration_and_pgtap_parse_as_postgresql() -> None:
    try:
        from pglast import parse_sql
    except ImportError:
        pytest.skip("pglast is required for the PostgreSQL syntax contract")

    assert len(parse_sql(_read(MIGRATION_PATH))) >= 40
    assert len(parse_sql(_read(PGTAP_PATH))) >= 40


def test_global_kill_switch_is_seeded_disabled_and_is_the_only_rollout_path() -> None:
    sql = _read(MIGRATION_PATH)
    compact = _compact(sql)
    global_state = _compact(
        _sql_function(
            sql, "content_factory_private.research_youtube_global_state"
        )
    )
    global_gate = _compact(
        _sql_function(
            sql, "content_factory_private.research_youtube_global_gate"
        )
    )

    assert re.search(
        r"insert into content_factory\.research_youtube_global_rollout_decisions"
        r" .*? values \( .*? 'disabled'",
        compact,
    )
    assert "coalesce((" in global_state and "), 'disabled')" in global_state
    assert "global_state in ('canary_enabled', 'controlled_rollout')" in global_gate
    assert "global_state = 'controlled_rollout'" in global_gate
    assert not re.search(
        r"\b(?:insert\s+into|update|delete\s+from|merge\s+into)\s+"
        r"content_factory\.research_provider_catalog\b",
        sql,
        re.IGNORECASE,
    )


def test_creator_claim_is_exact_requester_and_role_bounded() -> None:
    sql = _read(MIGRATION_PATH)
    creator_claim = _compact(
        _sql_function(sql, "public.creator_claim_research_youtube_ingestion")
    )
    private_claim = _compact(
        _sql_function(
            sql, "content_factory_private.claim_research_youtube_ingestion"
        )
    )
    expiry = _compact(
        _sql_function(
            sql, "content_factory_private.expire_research_youtube_ingestion"
        )
    )
    begin_transport = _compact(
        _sql_function(sql, "public.system_begin_research_youtube_transport")
    )

    assert "requested_by_value <> user_id" in creator_claim
    assert "array['owner', 'admin', 'producer']" in creator_claim
    assert "membership.status = 'active'" in creator_claim
    assert "'invoke_authorized', true" in creator_claim
    assert "research_youtube_invoke_not_authorized" in creator_claim

    assert "for update" in private_claim
    assert "category_binding_stale" in private_claim
    assert "retention_control_unavailable" in private_claim
    assert "rollout_gate_closed" in private_claim
    assert private_claim.index("category_binding_stale") < private_claim.index(
        "retention_control_unavailable"
    ) < private_claim.index("rollout_gate_closed")
    assert private_claim.count("transition_time + interval '5 minutes'") == 2
    assert "set status = 'failed'" in private_claim

    assert "ingestion.status = 'processing'" in expiry
    assert "ingestion.lease_expires_at <= completed_time" in expiry
    assert "ingestion_lease_expired" in expiry
    assert "no provider retry was attempted" in expiry
    assert "insert into content_factory.research_youtube_transport_attempts" not in expiry
    assert "if lease_expired_value then return jsonb_build_object(" in begin_transport
    assert "'external_call_allowed', false" in begin_transport
    assert begin_transport.index("if lease_expired_value then") < begin_transport.index(
        "research_youtube_ingestion_not_processing"
    )


def test_canary_plan_and_both_endpoint_receipts_are_exact() -> None:
    sql = _read(MIGRATION_PATH)
    ingestion_table = _compact(
        _sql_table(sql, "content_factory.research_youtube_ingestion_runs")
    )
    completion = _compact(
        _sql_function(sql, "public.system_complete_research_youtube_ingestion")
    )
    global_rollout = _compact(
        _sql_function(
            sql, "public.system_decide_research_youtube_global_rollout"
        )
    )
    organization_rollout = _compact(
        _sql_function(sql, "public.creator_decide_research_youtube_rollout")
    )
    refresh_gate = _compact(
        _sql_function(
            sql, "content_factory_private.research_youtube_refresh_gate"
        )
    )

    assert (
        "mode = 'manual_canary' and max_results = 1 "
        "and max_http_requests = 2 and max_quota_units = 2"
    ) in ingestion_table
    assert "search_item_count_value <> 1" in completion
    assert "videos_item_count_value <> 1" in completion
    assert "jsonb_array_length(observations_value) <> 0" in completion
    assert "canary_value ->> 'request_kind' <> 'videos.list'" in completion

    for definition in (global_rollout, organization_rollout, refresh_gate):
        assert "request_kind = 'search.list'" in definition
        assert "request_kind = 'videos.list'" in definition
        assert definition.count("status = 'ready'") >= 2
        assert definition.count("item_count = 1") >= 2
    assert "research_youtube_global_canary_required" in global_rollout


def test_success_completion_binds_search_and_videos_summaries_to_receipts() -> None:
    sql = _read(MIGRATION_PATH)
    completion = _compact(
        _sql_function(sql, "public.system_complete_research_youtube_ingestion")
    )

    assert "search_receipt.response_hash <> search_response_hash_value" in completion
    assert "search_receipt.item_count <> search_item_count_value" in completion
    assert "detail_receipt.response_hash <> videos_response_hash_value" in completion
    assert "detail_receipt.item_count <> videos_item_count_value" in completion
    assert "research_youtube_video_receipt_mismatch" in completion
    assert "canary_value ->> 'response_hash' <> videos_response_hash_value" in completion
    assert "canary_checked_at_value <> detail_receipt.checked_at" in completion
    assert "replay_completed_value := true" in completion
    assert "observation.observation_hash = observation_hash_value" in completion
    assert completion.index("replay_completed_value := true") < completion.index(
        "detail_receipt.response_hash <> videos_response_hash_value"
    )


def test_pacific_quota_window_and_all_three_caps_are_enforced_before_insert() -> None:
    sql = _read(MIGRATION_PATH)
    quota_window = _compact(
        _sql_function(
            sql, "content_factory_private.research_youtube_quota_window"
        )
    )
    begin_transport = _compact(
        _sql_function(sql, "public.system_begin_research_youtube_transport")
    )

    assert quota_window.count("america/los_angeles") == 3
    assert "transport.started_at >= quota_starts_at_value" in begin_transport
    assert "transport.started_at < quota_ends_at_value" in begin_transport
    assert "global_started_value >= 90" in begin_transport
    assert "organization_started_value >= 20" in begin_transport
    assert "requester_started_value >= 10" in begin_transport
    assert begin_transport.index("global_started_value >= 90") < begin_transport.index(
        "insert into content_factory.research_youtube_transport_attempts"
    )
    assert "pg_advisory_xact_lock" in begin_transport
    assert "request_hash_value, quota_now_value" in begin_transport


def test_latest_retention_heartbeat_and_complete_purge_are_required() -> None:
    sql = _read(MIGRATION_PATH)
    retention_table = _compact(
        _sql_table(sql, "content_factory.research_youtube_retention_receipts")
    )
    retention_ready = _compact(
        _sql_function(
            sql, "content_factory_private.research_youtube_retention_ready"
        )
    )
    purge = _compact(
        _sql_function(sql, "public.system_purge_expired_youtube_api_data")
    )

    assert "between 0 and 5000" in retention_table
    assert "overdue_remaining_count >= 0" in retention_table
    assert "order by receipt.purged_at desc, receipt.id desc limit 1" in retention_ready
    assert "receipt.overdue_remaining_count = 0" in retention_ready
    assert "clock_timestamp() - interval '2 hours'" in retention_ready
    assert "job.schedule = '17 * * * *'" in retention_ready

    for table in (
        "research_youtube_candidate_decisions",
        "research_youtube_video_observations",
        "research_youtube_transport_receipts",
        "research_youtube_transport_attempts",
    ):
        assert f"delete from content_factory.{table}" in purge
    assert "overdue_remaining_count_value" in purge
    assert "observation_deleted_count_value integer := 0" in purge
    assert "candidate_deleted_count_value integer := 0" in purge
    assert "receipt_deleted_count_value integer := 0" in purge
    assert "attempt_deleted_count_value integer := 0" in purge
    assert "insert into content_factory.research_youtube_retention_receipts" in purge


def test_raw_observations_have_no_generic_candidate_or_delta_contract() -> None:
    sql = _read(MIGRATION_PATH)
    observations = _compact(
        _sql_table(sql, "content_factory.research_youtube_video_observations")
    )
    decisions = _compact(
        _sql_table(sql, "content_factory.research_youtube_candidate_decisions")
    )
    status = _compact(
        _sql_function(sql, "public.creator_research_youtube_status")
    )
    decide = _compact(
        _sql_function(sql, "public.creator_decide_research_youtube_candidate")
    )

    assert "candidate_key" not in observations
    assert "candidate_key" not in decisions
    assert "observation_id uuid not null" in decisions
    assert "observation_hash text not null" in decisions
    assert "decided_at timestamptz not null default clock_timestamp()" in decisions
    for forbidden in (
        "candidate_key",
        "view_delta",
        "like_delta",
        "comment_delta",
        "growth_delta",
    ):
        assert forbidden not in status
        assert forbidden not in decide
    assert "begin_command" not in decide
    assert "finish_command" not in decide
    assert "command_receipt" not in decide


def test_retention_expiry_is_a_valid_terminal_summary_and_guides_a_new_request() -> None:
    sql = _read(MIGRATION_PATH)
    status = _compact(
        _sql_function(sql, "public.creator_research_youtube_status")
    )
    assert (
        "when api_data_retention_expired_value then "
        "'request_new_ingestion_after_retention'"
    ) in status
    assert status.index("when ingestion_row.status = 'failed'") < status.index(
        "when api_data_retention_expired_value"
    ) < status.index("when ingestion_row.mode = 'manual_canary'")
    assert "receipt.cutoff_at >= ingestion_row.requested_at + interval '29 days'" in status

    result = _run_view_module(
        r'''
        const ids = {
          run: "10000000-0000-4000-8000-000000000001",
          product: "10000000-0000-4000-8000-000000000002",
          binding: "10000000-0000-4000-8000-000000000003",
          category: "10000000-0000-4000-8000-000000000004",
          ingestion: "10000000-0000-4000-8000-000000000005",
          searchTransport: "10000000-0000-4000-8000-000000000006",
          detailTransport: "10000000-0000-4000-8000-000000000007",
          searchReceipt: "10000000-0000-4000-8000-000000000008",
          detailReceipt: "10000000-0000-4000-8000-000000000009",
        };
        const quota = {
          provider_day: "2026-08-03",
          provider_timezone: "America/Los_Angeles",
          resets_at: "2026-08-04T07:00:00.000Z",
          organization_search_requests_started: 1,
          organization_search_requests_cap: 20,
          organization_video_detail_requests_started: 1,
          organization_video_detail_requests_cap: 20,
          monetary_cost_rub: 0,
        };
        const overviewIngestion = {
          ingestion_id: ids.ingestion,
          status: "completed",
          mode: "manual_canary",
          binding_id: ids.binding,
          market_category_id: ids.category,
          query_text: "test category",
          region_code: "RU",
          relevance_language: "ru",
          published_after: null,
          max_results: 1,
          max_http_requests: 2,
          max_quota_units: 2,
          quota_units_started: 2,
          requested_at: "2026-08-03T10:00:00.000Z",
          claimed_at: "2026-08-03T10:00:01.000Z",
          lease_expires_at: "2026-08-03T10:05:01.000Z",
          completed_at: "2026-08-03T10:00:04.000Z",
          error_code: null,
        };
        const overview = {
          ok: true,
          version: "research-youtube-live-ingestion-v1",
          run_id: ids.run,
          product_id: ids.product,
          global_rollout_state: "controlled_rollout",
          current_binding: {
            binding_id: ids.binding,
            binding_version: 1,
            market_category_id: ids.category,
            canonical_name: "Test category",
            category_status: "active",
          },
          can_request_canary: true,
          can_request_refresh: false,
          can_decide_rollout: true,
          can_decide_candidates: true,
          ingestions: [overviewIngestion],
          rollout: null,
          quota,
          retention: {
            retention_days: 29,
            provider_policy_limit_days: 30,
            physical_purge_schedule_ready: true,
          },
          guidance: {
            status: "canary_required",
            recommended_next_step: "review_canary_and_enable_refresh",
            manual_external_action_required: true,
            automatic_retry_allowed: false,
            automatic_fallback_allowed: false,
            generation_consumption: "forbidden",
          },
        };
        function latest(retained, retentionExpired = !retained) {
          const transports = retained ? [
            {
              transport_id: ids.searchTransport,
              request_ordinal: 1,
              request_kind: "search.list",
              quota_bucket: "search_queries",
              quota_units: 1,
              request_hash: "a".repeat(64),
              started_at: "2026-08-03T10:00:01.000Z",
              receipt: {
                receipt_id: ids.searchReceipt,
                status: "ready",
                failure_code: null,
                response_hash: "b".repeat(64),
                item_count: 1,
                checked_at: "2026-08-03T10:00:00.000Z",
              },
            },
            {
              transport_id: ids.detailTransport,
              request_ordinal: 2,
              request_kind: "videos.list",
              quota_bucket: "default",
              quota_units: 1,
              request_hash: "c".repeat(64),
              started_at: "2026-08-03T10:00:02.000Z",
              receipt: {
                receipt_id: ids.detailReceipt,
                status: "ready",
                failure_code: null,
                response_hash: "d".repeat(64),
                item_count: 1,
                checked_at: "2026-08-03T10:00:00.000Z",
              },
            },
          ] : [];
          return {
            ok: true,
            version: "research-youtube-live-ingestion-v1",
            ingestion: {
              id: ids.ingestion,
              status: "completed",
              mode: "manual_canary",
              run_id: ids.run,
              product_id: ids.product,
              binding_id: ids.binding,
              market_category_id: ids.category,
              provider_key: "youtube_data_api_v3",
              adapter_version: "youtube-data-api-v3-public-metadata-v1",
              query_text: "test category",
              region_code: "RU",
              relevance_language: "ru",
              published_after: null,
              max_results: 1,
              max_http_requests: 2,
              max_quota_units: 2,
              quota_units_started: 2,
              request_hash: "e".repeat(64),
              requested_at: "2026-08-03T10:00:00.000Z",
              claimed_at: "2026-08-03T10:00:01.000Z",
              lease_expires_at: "2026-08-03T10:05:01.000Z",
              completed_at: "2026-08-03T10:00:04.000Z",
              error_code: null,
              error_message: null,
              current_binding: true,
            },
            transports,
            observations: [],
            candidate_decisions: [],
            global_rollout_state: "controlled_rollout",
            rollout: null,
            quota,
            retention: {
              retention_days: 29,
              provider_policy_limit_days: 30,
              physical_purge_schedule_ready: true,
              api_data_present: retained,
              api_data_retention_expired: retentionExpired,
            },
            guidance: {
              status: "completed",
              recommended_next_step: retentionExpired
                ? "request_new_ingestion_after_retention"
                : "review_canary_and_decide_rollout",
              automatic_retry_allowed: false,
              automatic_fallback_allowed: false,
              generation_consumption: "forbidden",
              candidate_confirmation_required: true,
            },
          };
        }
        function inspect(retained, retentionExpired = !retained) {
          const normalized = subject.normalizeResearchYoutube({
            overview,
            overviewUnavailable: false,
            latest: latest(retained, retentionExpired),
            latestUnavailable: false,
          });
          const markup = subject.researchYoutubeMarkup(normalized);
          const enableButton = markup.match(
            /<button[^>]*data-youtube-decision="enable_category_refresh"[^>]*>/u,
          )?.[0] || "";
          return {
            available: normalized.available,
            latestAvailable: normalized.latestAvailable,
            latestInvalid: normalized.latestInvalid,
            observations: normalized.latest?.observations.length ?? -1,
            requestVisible: markup.includes('id="product-research-youtube-request-form"'),
            expiredCopy: markup.includes("API-доказательства удалены по retention"),
            rolloutEnabled: Boolean(enableButton) && !enableButton.includes("disabled"),
          };
        }
        return {
          retained: inspect(true, false),
          expired: inspect(false, true),
          corrupt: inspect(false, false),
        };
        '''
    )
    assert result == {
        "retained": {
            "available": True,
            "latestAvailable": True,
            "latestInvalid": False,
            "observations": 0,
            "requestVisible": True,
            "expiredCopy": False,
            "rolloutEnabled": True,
        },
        "expired": {
            "available": True,
            "latestAvailable": True,
            "latestInvalid": False,
            "observations": 0,
            "requestVisible": True,
            "expiredCopy": True,
            "rolloutEnabled": False,
        },
        "corrupt": {
            "available": True,
            "latestAvailable": False,
            "latestInvalid": True,
            "observations": -1,
            "requestVisible": False,
            "expiredCopy": False,
            "rolloutEnabled": False,
        },
    }


def test_all_youtube_ledgers_are_rls_protected_and_rpc_grants_are_split() -> None:
    compact = _compact(_read(MIGRATION_PATH))
    tables = (
        "research_youtube_global_rollout_decisions",
        "research_youtube_rollout_decisions",
        "research_youtube_ingestion_runs",
        "research_youtube_transport_attempts",
        "research_youtube_transport_receipts",
        "research_youtube_video_observations",
        "research_youtube_candidate_decisions",
        "research_youtube_retention_receipts",
    )
    for table in tables:
        assert f"alter table content_factory.{table} enable row level security" in compact
        assert (
            f"revoke all on table content_factory.{table} "
            "from public, anon, authenticated, service_role"
        ) in compact

    assert (
        "grant execute on function public.creator_claim_research_youtube_ingestion(jsonb) "
        "to authenticated"
    ) in compact
    assert (
        "grant execute on function public.system_claim_research_youtube_ingestion(jsonb) "
        "to service_role"
    ) in compact
    assert (
        "grant execute on function public.system_purge_expired_youtube_api_data(jsonb) "
        "to service_role"
    ) in compact
    assert not re.search(r"\b(?:http|net)\s*\.", compact)
    assert "fetch(" not in compact
