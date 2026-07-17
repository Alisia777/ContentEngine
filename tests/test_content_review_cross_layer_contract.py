from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
EDGE = ROOT / "supabase" / "functions" / "creator-content-review" / "index.ts"
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607160003_content_review_pipeline.sql"
)
DURABLE_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607170004_durable_video_content_review.sql"
)
PGTAP = ROOT / "supabase" / "tests" / "content_review_pipeline_test.sql"

RULESET_VERSION = "ru-content-compliance-2026-07-16.1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_content_review_ruleset_and_rpc_names_are_identical_across_layers() -> None:
    edge = _read(EDGE)
    migration = _read(MIGRATION)
    durable_migration = _read(DURABLE_MIGRATION)
    adapter = _read(APP / "supabase-api.js")
    pgtap = _read(PGTAP)

    assert f'const RULESET_VERSION = "{RULESET_VERSION}"' in edge
    assert RULESET_VERSION in migration
    assert RULESET_VERSION in pgtap
    assert "ru-content-compliance-2026-07-16-v1" not in migration
    assert "ru-content-compliance-2026-07-16-v1" not in pgtap

    for rpc_name in (
        "creator_content_review_catalog",
        "creator_start_content_review",
        "creator_content_review_status",
        "creator_decide_content_review",
        "system_claim_content_review",
        "system_complete_content_review",
    ):
        assert rpc_name in migration or rpc_name in durable_migration
        assert rpc_name in pgtap
    for rpc_name in (
        "creator_prepare_content_review_evidence",
        "creator_commit_content_review_evidence",
        "system_begin_content_review_provider_dispatch",
        "system_release_content_review_attempt",
    ):
        assert rpc_name in durable_migration
    for rpc_name in (
        "creator_content_review_catalog",
        "creator_start_content_review",
        "creator_content_review_status",
        "creator_decide_content_review",
    ):
        assert rpc_name in adapter
    for rpc_name in (
        "creator_content_review_status",
        "system_claim_content_review",
        "system_begin_content_review_provider_dispatch",
        "system_release_content_review_attempt",
        "system_complete_content_review",
    ):
        assert rpc_name in edge
    for rpc_name in (
        "creator_prepare_content_review_evidence",
        "creator_commit_content_review_evidence",
    ):
        assert rpc_name in adapter


def test_catalog_request_and_response_use_the_server_contract() -> None:
    adapter = _read(APP / "supabase-api.js")
    view = _read(APP / "content-review-view.js")
    migration = _read(MIGRATION)

    catalog_method = adapter[
        adapter.index("contentReviewCatalog(") :
        adapter.index("async startContentReview(")
    ]
    assert "media_limit: normalizedLimit" in catalog_method
    assert "run_limit: normalizedLimit" in catalog_method
    assert "\n      limit: normalizedLimit" not in catalog_method

    assert '"recent_reviews"' in view
    assert "source.ruleset?.version" in view
    assert "'recent_reviews', runs_value" in migration
    assert "'ruleset', jsonb_build_object(" in migration


def test_start_and_decision_payloads_have_one_canonical_shape() -> None:
    adapter = _read(APP / "supabase-api.js")
    migration = _read(MIGRATION)
    edge = _read(EDGE)

    for field in (
        "media_id",
        "parent_review_id",
        "platform",
        "content_kind",
        "product_category",
        "caption_text",
        "script_text",
        "advertiser_name",
        "erid",
        "technical_metrics",
        "rights_confirmed",
        "claims_verified",
        "ad_label_confirmed",
        "ord_confirmed",
        "audience_over_10000",
        "rkn_registered",
        "people_present",
        "person_consent_confirmed",
        "external_ai_processing_confirmed",
        "ai_generated",
        "ai_disclosure_confirmed",
        "captions_confirmed",
        "mandatory_warning_confirmed",
    ):
        assert field in adapter
        assert field in migration

    for value in (
        "unknown",
        "informational",
        "advertising",
        "cosmetics",
        "baa",
        "sports_food",
        "food",
        "household",
        "apparel",
        "electronics",
        "other",
    ):
        assert value in adapter
        assert value in migration

    assert 'action: "analyze"' in adapter
    assert 'action: "analyze"' in edge
    assert "review_id" in edge
    assert 'new Set(["action", "review_id"])' in edge
    assert 'new Set(["action", "review_id", "frames"])' not in edge

    for field in (
        "review_id",
        "decision",
        "comment",
        "resolved_recommendation_codes",
        "risk_acknowledgements",
        "media_watched_confirmed",
    ):
        assert field in adapter
        assert field in migration


def test_video_review_is_durable_and_paid_dispatch_is_fenced() -> None:
    migration = _read(DURABLE_MIGRATION)
    edge = _read(EDGE)
    worker = _read(
        ROOT
        / "supabase"
        / "functions"
        / "creator-background-worker"
        / "index.ts"
    )

    for marker in (
        "content_review_evidence_sets",
        "content_review_evidence_frames",
        "content_review_attempts",
        "provider_dispatch_started_at",
        "provider_outcome_unknown",
        "content_review_attempts_one_active_uq",
        "content_review_runs_retry_due_idx",
        "system_begin_content_review_provider_dispatch",
        "system_release_content_review_attempt",
    ):
        assert marker in migration

    assert 'MAX_BODY_BYTES = 4_096' in edge
    assert 'body: { action: "analyze", review_id: row.id }' in worker
    assert 'frames: []' not in worker
    assert "attempt.providerIdempotencyKey" in edge
    assert "providerDispatchStarted = true" in edge
    assert "system_begin_content_review_provider_dispatch" in edge
    assert "system_release_content_review_attempt" in edge
    assert "frameBlob.size !== frame.sizeBytes" in edge
    assert "await sha256Hex(frameBytes)" in edge
    assert "isJpeg(frameBytes)" in edge
    assert "DATA_IMAGE_PATTERN" not in edge
    assert "technicalMetrics: capturedEvidence.technical_metrics" in _read(
        APP / "app.js"
    )
    assert "technical_metrics: technicalMetrics" in _read(
        APP / "supabase-api.js"
    )


def test_quality_and_compliance_are_independent_and_video_is_human_gated() -> None:
    edge = _read(EDGE)
    migration = _read(MIGRATION)
    view = _read(APP / "content-review-view.js")

    for result_key in (
        "overall_score",
        "scores",
        "compliance_status",
        "blockers_count",
        "warnings_count",
        "strengths",
        "findings",
        "recommendations",
        "comparison",
    ):
        assert result_key in edge
        assert result_key in migration

    assert "Высокий quality score никогда не отменяет blocker" in edge
    assert "'block', 'human_review', 'pass_with_warnings'" in migration
    assert "SCOPE.AUDIO_MANUAL_REVIEW" in edge
    assert "raw_video_sent: false" in _read(APP / "app.js")
    assert "media_watched_confirmed" in view
    assert "content_review_media_watch_required" in migration
    assert "high_risk_content_requires_independent_review" in migration


def test_legal_sources_and_release_gate_are_durable_not_cosmetic() -> None:
    edge = _read(EDGE)
    view = _read(APP / "content-review-view.js")
    migration = _read(MIGRATION)

    source_keys = (
        "ad_law_38fz",
        "ad_definition_1087",
        "restricted_resources_72fz",
        "erid_order_68",
        "ord_rules_974",
        "publisher_registry_238",
        "personal_data_152fz",
        "image_rights_152_1",
        "cosmetics_tr_ts_009",
        "food_label_tr_ts_022",
        "youtube_synthetic",
    )
    for source_key in source_keys:
        assert source_key in edge
        assert source_key in view

    for rule_code in (
        "AD.MARKING.ERID",
        "CLAIM.THERAPEUTIC_NONMEDICAL",
        "RIGHTS.MEDIA",
        "YOUTUBE.AI_DISCLOSURE",
        "BAA.DISCLAIMER",
    ):
        assert rule_code in edge

    assert "!~*" in migration
    assert "guard_video_review_content_approval" in migration
    assert "content_review_approval_evidence_required" in migration
    assert "decision.media_watched_confirmed" in migration
    assert "creator_payouts" in migration
    assert "'pending'" in migration
    assert "'placement'" in migration
    assert "content-review-placement-task:" in migration
    assert "content-review-placement:" in migration
    assert (
        "on conflict on constraint placements_organization_id_task_id_key"
        in migration
    )


def test_release_context_queue_risks_and_publication_url_fail_closed() -> None:
    edge = _read(EDGE)
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)

    for marker in (
        "generated_video_review_context_invalid",
        "generated_video_product_context_invalid",
        "product_category_verified",
        "product_category_source",
        "generation_job_id",
        "queued_dispatch_expired",
        "risk_acknowledgement_unknown",
        "resolved_recommendation_code_unknown",
        "high_risk_content_requires_independent_review",
        "placement_url_matches_platform",
        "final_url_platform_mismatch",
        "media_stale_before_review",
    ):
        assert marker in migration
    for marker in (
        "product_category_verified",
        "product_category_source",
        "generation_job_id",
        "queued_dispatch_expired",
        "risk_acknowledgement_unknown",
        "resolved_recommendation_code_unknown",
        "high_risk_content_requires_independent_review",
        "final_url_platform_mismatch",
        "media_stale_before_review",
    ):
        assert marker in pgtap

    assert "AD.CLASSIFICATION_CONFLICT" in edge
    assert "ad_probability: adProbability" in edge
    assert "SCOPE.BROWSER_FRAMES_ADVISORY" in edge
    assert "external_ai_processing_basis_required" in edge
    assert 'stringInput(claim.run.input, "people_present") !== "no"' in edge
    assert "length(final_url_value) not between 12 and 2000" in migration
    assert "{3,1992}" not in migration


def test_completion_and_compliance_revalidate_trusted_evidence() -> None:
    migration = _read(MIGRATION)
    pgtap = _read(PGTAP)
    completion = migration[
        migration.index("create or replace function public.system_complete_content_review") :
        migration.index(
            "create or replace function content_factory_private.placement_url_matches_platform"
        )
    ]

    for marker in (
        "content_review_warning_count_invalid",
        "content_review_compliance_status_invalid",
        "processing_lease_expired",
        "media_stale_during_review",
        "parent_content_review_product_mismatch",
    ):
        assert marker in migration
        assert marker in pgtap

    assert "item ->> 'severity' in ('high', 'medium')" in migration
    assert "for update;" in completion
    assert "review_row.lease_expires_at <= now()" in completion
    assert "media_row.sha256 is distinct from review_row.media_sha256_snapshot" in completion
    assert "without browser status polling" in pgtap
    assert "staleness takes precedence over a provider failure" in pgtap
    assert "replayed idempotently" in pgtap
