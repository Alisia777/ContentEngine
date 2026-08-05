from pathlib import Path
import re

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608050001_solo_owner_content_review.sql"
).read_text(encoding="utf-8")
PIPELINE_MIGRATION = (
    ROOT / "supabase" / "migrations" / "202607160003_content_review_pipeline.sql"
).read_text(encoding="utf-8")
ASSIGNMENT_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607270007_generated_media_review_assignment.sql"
).read_text(encoding="utf-8")


def test_solo_owner_review_migration_parses() -> None:
    assert parse_sql(MIGRATION)


def test_solo_owner_exception_is_narrow_and_preserves_review_gates() -> None:
    assert "solo_owner_content_review_allowed" in MIGRATION
    assert "actor.role = 'owner'" in MIGRATION
    assert "actor.status = 'active'" in MIGRATION
    assert "candidate.profile_id is distinct from p_profile_id" in MIGRATION
    assert "generated_media_reviewer_access_allowed" in MIGRATION
    assert "not exists (" in MIGRATION
    assert "media_watched_confirmed" not in MIGRATION
    assert "risk_acknowledgements" not in MIGRATION
    assert "sound_assessment" not in MIGRATION


def test_assignment_decision_and_catalog_share_one_permission_predicate() -> None:
    assert (
        "content_factory_private.assign_generated_media_review(uuid,uuid)"
        in MIGRATION
    )
    assert (
        "creator_decide_content_review_without_sound_release_gate(jsonb)"
        in MIGRATION
    )
    assert (
        "creator_content_review_catalog_without_repair_actions(jsonb)"
        in MIGRATION
    )
    assert MIGRATION.count("solo_owner_content_review_allowed(") >= 5
    assert "solo_owner_assignment_patch_target_missing" in MIGRATION
    assert "solo_owner_decision_patch_target_missing" in MIGRATION
    assert "solo_owner_catalog_patch_target_missing" in MIGRATION


def test_dynamic_patch_targets_match_the_installed_function_bodies() -> None:
    old_blocks = re.findall(
        r"old_text constant text := \$old\$(.*?)\$old\$;",
        MIGRATION,
        flags=re.DOTALL,
    )
    assert len(old_blocks) == 3
    assert old_blocks[0] in ASSIGNMENT_MIGRATION
    assert old_blocks[1] in PIPELINE_MIGRATION
    assert old_blocks[2] in ASSIGNMENT_MIGRATION


def test_existing_unassigned_reviews_are_retried_without_touching_decisions() -> None:
    assert "for review_row in" in MIGRATION
    assert "review.status = 'completed'" in MIGRATION
    assert "content_review_decisions decision" in MIGRATION
    assert "perform content_factory_private.assign_generated_media_review" in MIGRATION
    assert "insert into content_factory.content_review_decisions" not in MIGRATION
