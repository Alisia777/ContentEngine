from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608100011_exact_youtube_research_evidence_bridge.sql"
)
EDGE_PATH = ROOT / "supabase" / "functions" / "creator-product-research" / "index.ts"
EDGE_TEST_PATH = (
    ROOT / "supabase" / "functions" / "creator-product-research" / "index_test.ts"
)

MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
EDGE = EDGE_PATH.read_text(encoding="utf-8")
EDGE_TEST = EDGE_TEST_PATH.read_text(encoding="utf-8")


def test_exact_video_research_migration_is_parseable_and_ordered() -> None:
    assert MIGRATION_PATH.name > "202608100010_exact_youtube_media_attachment.sql"
    assert len(parse_sql(MIGRATION)) >= 20


def test_binding_is_append_only_and_snapshots_every_authoritative_identity() -> None:
    required = (
        "research_exact_youtube_research_bindings",
        "unique (organization_id, run_id)",
        "unique (organization_id, evidence_set_id)",
        "source_hash_snapshot",
        "attachment_hash_snapshot",
        "media_sha256_snapshot",
        "evidence_manifest_hash_snapshot",
        "category_binding_hash_snapshot",
        "paid_analysis_ack_snapshot",
        "operator_compared_uploaded_media_to_registered_source",
        "sampled_frames_only",
        "exact_youtube_research_binding_append_only",
    )
    for marker in required:
        assert marker in MIGRATION
    # A fresh five-frame evidence set plus a new explicit paid acknowledgement
    # may intentionally retry a failed run for the same immutable source.
    assert "unique (organization_id, source_id)" not in MIGRATION
    assert "unique (organization_id, attachment_id)" not in MIGRATION
    assert "grant all on content_factory.research_exact_youtube_research_bindings" not in MIGRATION


def test_start_consumes_exactly_five_ready_frames_without_review_provider() -> None:
    assert "creator_start_project_research_pre_exact_video_v1" in MIGRATION
    assert "exact_video_evidence_id" in MIGRATION
    assert "evidence.expected_frame_count = 5" in MIGRATION
    assert "evidence.frame_count = 5" in MIGRATION
    assert "evidence.expires_at > clock_timestamp()" in MIGRATION
    assert "set status = 'consumed', consumed_at = clock_timestamp()" in MIGRATION
    assert "'paid_analysis_ack', true" in MIGRATION
    assert "creator_start_content_review(" not in MIGRATION
    assert "system_claim_content_review(" not in MIGRATION
    assert "return content_factory_private\n      .creator_start_project_research_pre_exact_video_v1(p_payload)" in MIGRATION
    assert "result_value := content_factory_private\n    .creator_start_project_research_pre_exact_video_v1(" in MIGRATION


def test_claim_validates_lineage_before_the_paid_claim_boundary() -> None:
    validation = MIGRATION.index("exact_youtube_research_claim_lineage_invalid")
    delegated_claim = MIGRATION.index(
        ".system_claim_product_research_pre_exact_video_v1(p_payload)",
        validation,
    )
    assert validation < delegated_claim
    assert "frame.bucket_id = 'contentengine-private'" in MIGRATION
    assert "frame.mime_type = 'image/jpeg'" in MIGRATION
    assert "evidence.status = 'consumed'" in MIGRATION
    assert "'client_authored_conclusions', false" in MIGRATION
    assert "grant execute on function public.system_claim_product_research(jsonb)\n  to service_role" in MIGRATION


def test_edge_rechecks_private_frame_bytes_before_provider_attempt() -> None:
    markers = (
        "readExactVideoResearchEvidence",
        "EXACT_VIDEO_FRAME_COUNT = 5",
        "MAX_EXACT_VIDEO_TOTAL_FRAME_BYTES = 2_359_296",
        ".storage.from(STORAGE_BUCKET).download(frame.objectName)",
        "frameBlob.size !== frame.sizeBytes",
        "!isJpeg(frameBytes)",
        "(await sha256Hex(frameBytes)) !== frame.sha256",
        "actualTotalFrameBytes !== claim.run.exactVideo.evidenceTotalSizeBytes",
        "jpegDataUrl(frameBytes)",
    )
    for marker in markers:
        assert marker in EDGE
    assert EDGE.index("download(frame.objectName)") < EDGE.index(
        "providerAttemptId = await beginProviderAttempt(model)"
    )


def test_exact_video_is_trusted_sampled_input_not_a_fake_full_video_result() -> None:
    assert "five_hash_verified_sampled_frames_only" in EDGE
    assert 'full_stream_access: false' in EDGE
    assert 'transcript_available: false' in EDGE
    assert 'audio_analyzed: false' in EDGE
    assert "visual_sequence_complete: false" in EDGE
    assert "never as a complete stream" in EDGE
    assert "content_review_provider_used: false" in EDGE
    assert "exact_input_lineage_verified: true" in EDGE


def test_exact_source_does_not_depend_on_youtube_web_search_but_stays_exact() -> None:
    assert 'source.url !== exactVideo.canonicalUrl' in EDGE
    assert 'source.source_type !== "social"' in EDGE
    assert 'source.published_at !== null' in EDGE
    assert 'sourcePublishers.set(source.id, "exact_video_input")' in EDGE
    assert "? { provider_citation_verified: false }" in EDGE
    assert ": { provider_citation_verified: true }" in EDGE
    assert "providerSources.has(exactVideoSourceKey)" not in EDGE
    assert "server-bound exact frames must not depend on brittle YouTube web_search" in EDGE_TEST
    assert "a different YouTube video must not inherit the exact frame lineage" in EDGE_TEST
