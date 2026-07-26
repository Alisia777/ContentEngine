from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607270001_generation_repair_review_lineage.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
ADAPTER = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_repair_review_parent_is_derived_from_immutable_signal() -> None:
    resolver = MIGRATION[
        MIGRATION.index("generation_repair_review_lineage(") :
        MIGRATION.index(
            "revoke all on function\n"
            "  content_factory_private.generation_repair_review_lineage"
        )
    ]
    for token in (
        "generation_repair_signals",
        "signal_row.source_review_id",
        "signal_row.source_generation_job_id",
        "signal_row.source_review_completion_hash",
        "signal_row.source_media_sha256",
        "decision_row.decision <> 'needs_changes'",
        "not decision_row.media_watched_confirmed",
        "source_job_row.input ->> 'model'",
        "source_job_row.input ->> 'platform'",
        "source_job_row.input ->> 'destination_ref'",
        "generation_repair_review_lineage_invalid",
    ):
        assert token in resolver


def test_every_repair_review_insert_forces_exact_source_parent() -> None:
    for token in (
        "generation_repair_review_lineage_guard",
        "before insert on content_factory.content_review_runs",
        "new.parent_review_id := (lineage ->> 'source_review_id')::uuid",
        "generation_repair_review_job_mismatch",
    ):
        assert token in MIGRATION


def test_public_start_overrides_client_parent_before_legacy_validation() -> None:
    wrapper = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_start_content_review"
        ) :
    ]
    for token in (
        "creator_start_content_review_pre_repair_lineage_v1",
        "'{parent_review_id}'",
        "lineage ->> 'source_review_id'",
        "generation_repair_review_lineage_not_bound",
        "'repair_lineage'",
    ):
        assert token in wrapper
    parent_binding = wrapper.index("'{parent_review_id}'")
    legacy_call = wrapper.index(
        ".creator_start_content_review_pre_repair_lineage_v1"
    )
    assert parent_binding < legacy_call


def test_portal_only_uses_context_compatible_history_as_fallback() -> None:
    history = APP[
        APP.index("const completedRuns = catalog.runs.filter") :
        APP.index("stopContentReviewPolling()", APP.index(
            "const completedRuns = catalog.runs.filter"
        ))
    ]
    for token in (
        "item.input?.platform === input.platform",
        "item.input?.productCategory === input.product_category",
        "item.input?.contentKind === input.content_kind",
    ):
        assert token in history
    assert '"repair_source"' in APP
    assert "raw?.repair_lineage" in APP


def test_lineage_failures_have_safe_recovery_copy() -> None:
    for code in (
        "generation_repair_review_lineage_invalid",
        "generation_repair_review_job_mismatch",
        "generation_repair_review_lineage_not_bound",
    ):
        assert code in ADAPTER
