from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608040013_research_category_learning_readiness.sql"
)
WORKER = ROOT / "supabase/functions/creator-background-worker/index.ts"
INGESTION = ROOT / "supabase/functions/creator-research-ingestion/index.ts"
CRON = ROOT / "scripts/configure_supabase_background_cron.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function(source: str, qualified_name: str) -> str:
    match = re.search(
        rf"\bcreate\s+(?:or\s+replace\s+)?function\s+"
        rf"{re.escape(qualified_name)}\s*\(",
        source,
        re.IGNORECASE,
    )
    assert match is not None, qualified_name
    next_match = re.search(
        r"\bcreate\s+(?:or\s+replace\s+)?function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_match is None else match.end() + next_match.start()
    return source[match.start() : end]


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def test_bulk_rpc_preclaims_new_automatic_refreshes_and_never_requeues() -> None:
    sql = _read(MIGRATION)
    claim = _compact(
        _function(sql, "public.system_claim_due_research_youtube_collection")
    )

    assert "limit_value not between 1 and 6" in claim
    assert "content_factory_private.expire_research_youtube_ingestion" in claim
    assert "public.system_propose_due_research_source_collection" in claim
    assert "content_factory_private.claim_research_youtube_ingestion" in claim
    assert "intent.capability = 'automatic_youtube_enqueue'" in claim
    assert "intent.automatic_enqueue_supported" in claim
    assert "ingestion.mode = 'category_refresh'" in claim
    assert "ingestion.status = 'queued'" in claim
    assert "'status', claim_value -> 'ingestion' ->> 'status'" in claim
    assert "'external_call_started', false" in claim
    assert "'automatic_retry_started', false" in claim
    assert "status = 'queued'" not in claim.split(
        "content_factory_private.claim_research_youtube_ingestion", 1
    )[1]

    compact_sql = _compact(sql)
    assert (
        "grant execute on function "
        "public.system_claim_due_research_youtube_collection(jsonb) "
        "to service_role"
    ) in compact_sql
    assert not re.search(
        r"grant execute on function public\.system_claim_due_research_youtube_collection"
        r"\(jsonb\) to (?:authenticated|anon|public)",
        compact_sql,
    )


def test_internal_edge_reads_only_a_live_preclaimed_auto_link() -> None:
    sql = _read(MIGRATION)
    read_rpc = _compact(
        _function(sql, "public.system_read_automatic_research_youtube_ingestion")
    )
    begin_rpc = _compact(
        _function(
            sql, "public.system_begin_automatic_research_youtube_transport"
        )
    )
    edge = _read(INGESTION)

    assert "intent.capability = 'automatic_youtube_enqueue'" in read_rpc
    assert "intent.automatic_enqueue_supported" in read_rpc
    assert "ingestion.mode = 'category_refresh'" in read_rpc
    assert "if ingestion_row.status <> 'processing'" in read_rpc
    assert "research_automatic_youtube_not_processing" in read_rpc
    assert "research_automatic_youtube_dispatch_allowed" in read_rpc
    assert "research_automatic_youtube_lease_expired" in read_rpc
    assert "'automatic_dispatch_authorized', true" in read_rpc
    assert "claim_research_youtube_ingestion(" not in read_rpc
    assert "pg_advisory_xact_lock" in begin_rpc
    assert "research_automatic_youtube_dispatch_allowed" in begin_rpc
    assert "public.system_begin_research_youtube_transport(p_payload)" in begin_rpc
    assert begin_rpc.index("research_automatic_youtube_dispatch_allowed") < (
        begin_rpc.index("public.system_begin_research_youtube_transport")
    )

    read_call = edge.index('"system_read_automatic_research_youtube_ingestion"')
    provider_execution = edge.index("executeYoutubeIngestion(", read_call)
    assert read_call < provider_execution
    assert "const rpcName = internalWorker" in edge
    assert 'claim.status !== "processing"' in edge
    assert 'claim?.ingestion.mode !== "category_refresh"' in edge
    assert "leaseExpiresAt <= now" in edge
    assert '"system_begin_automatic_research_youtube_transport"' in edge
    assert "isInternalWorkerAuthorized(request)" in edge
    assert "isInternalWorkerRequest(request)" in edge


def test_worker_claims_before_one_fixed_edge_dispatch_with_shared_cap() -> None:
    worker = _read(WORKER)
    claim = worker.index('"system_claim_due_research_youtube_collection"')
    dispatch = worker.index("const outcomes = await Promise.all")

    assert claim < dispatch
    assert 'functionName: "creator-research-ingestion"' in worker
    assert 'body: { action: "ingest", ingestion_id: row.ingestionId }' in worker
    assert "generation + research + review + youtube > MAX_TOTAL_DISPATCHES" in worker
    assert "system_claim_automatic_research_youtube_ingestion" not in worker
    assert '.from("research_youtube_ingestion_runs")' not in worker
    assert "youtubeCollection.ingestions.map" in worker
    assert "external_call_started" in worker
    assert "automatic_retry_started" in worker

    cron = _read(CRON)
    assert '"youtube_limit": 1' in cron
