from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608100006_generated_media_lifecycle_folders.sql"
).read_text(encoding="utf-8").lower()


def test_lifecycle_migration_parses_as_postgresql():
    assert parse_sql(MIGRATION)


def test_generated_media_follows_review_decision_and_publication_lifecycle():
    assert "after insert or update of status on content_factory.content_review_runs" in MIGRATION
    assert "new.status in ('queued', 'processing', 'completed')" in MIGRATION
    assert "set lifecycle_stage = 'review'" in MIGRATION
    assert "media.lifecycle_stage in ('drafts', 'ready')" in MIGRATION
    assert "after insert on content_factory.content_review_decisions" in MIGRATION
    assert "when 'approved' then 'ready'" in MIGRATION
    assert "else 'drafts'" in MIGRATION
    assert "after insert or update of status on content_factory.placements" in MIGRATION
    assert "set lifecycle_stage = 'published'" in MIGRATION


def test_transitions_are_exactly_project_scoped_and_generated_only():
    assert MIGRATION.count("media.project_id = new.project_id") >= 3
    assert MIGRATION.count("media.artifact_class = 'generated_output'") >= 4
    assert "job.project_id = new.project_id" in MIGRATION
    assert "review_row.project_id" in MIGRATION
    assert "media.lifecycle_stage <> 'published'" in MIGRATION


def test_late_review_decision_cannot_demote_newer_revision():
    assert "late decision for an older review" in MIGRATION
    assert "later_review.created_at, later_review.id" in MIGRATION
    assert "> (review_row.created_at, review_row.id)" in MIGRATION
    assert "media.lifecycle_stage <> 'published'" in MIGRATION


def test_backfill_derives_state_but_preserves_custom_folders():
    assert "contentengine.media_lifecycle_backfill" in MIGRATION
    assert "when latest_review.decision = 'approved' then 'ready'" in MIGRATION
    assert "placement.status = 'published'" in MIGRATION
    assert "location.folder_id is null" in MIGRATION
    assert "or current_folder.system_role is not null" in MIGRATION
    assert "coalesce(previous_backfill_setting, '')" in MIGRATION
    assert "exception\n  when others then" in MIGRATION


def test_custom_folder_policy_is_explicit_for_backfill_and_runtime():
    # Backfill suppresses workflow-transition relocation and then selects only
    # unfiled/system-filed rows. A later real lifecycle event intentionally
    # routes the output to its canonical system stage.
    assert (
        "workflow_transition\n      and coalesce(\n"
        "        current_setting('contentengine.media_lifecycle_backfill', true),"
        in MIGRATION
    )
    assert "<> 'on'" in MIGRATION
    assert "location.folder_id is null" in MIGRATION
    assert "or current_folder.system_role is not null" in MIGRATION


def test_existing_folder_router_remains_the_single_location_writer():
    assert "sync_workspace_media_system_location(" in MIGRATION
    assert "insert into content_factory.workspace_media_locations" not in MIGRATION


def test_trigger_functions_are_not_publicly_callable():
    for function_name in (
        "route_generated_media_review_lifecycle",
        "route_generated_media_decision_lifecycle",
        "route_published_placement_media_lifecycle",
        "sync_workspace_media_location_trigger",
    ):
        assert (
            f"revoke all on function\n  content_factory_private.{function_name}()"
            in MIGRATION
        )
