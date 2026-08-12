from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/202608120004_operator_self_content_review.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/operator_self_content_review_test.sql"
).read_text(encoding="utf-8")
ASSIGNMENT_SOURCE = (
    ROOT
    / "supabase/migrations/202607270007_generated_media_review_assignment.sql"
).read_text(encoding="utf-8")
REPAIR_SOURCE = (
    ROOT / "supabase/migrations/202607260013_generation_review_repair_loop.sql"
).read_text(encoding="utf-8")
SOUND_SOURCE = (
    ROOT / "supabase/migrations/202608040004_generated_video_sound_release_gate.sql"
).read_text(encoding="utf-8")
PROJECT_SOURCE = (
    ROOT / "supabase/migrations/202608040005_project_scoped_workflow.sql"
).read_text(encoding="utf-8")


def test_operator_self_review_sql_is_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(PGTAP)


def test_exact_predicate_is_fail_closed_and_project_scoped() -> None:
    predicate = MIGRATION[
        MIGRATION.index("qualified_operator_own_content_review_allowed(") :
        MIGRATION.index("$patch_operator_first_assignment$")
    ]
    for token in (
        "actor.role = 'operator'",
        "actor.status = 'active'",
        "generated_media_reviewer_access_allowed(",
        "workspace_project_access_allowed(",
        "review.project_id = p_project_id",
        "review.requested_by = actor.profile_id",
        "media.owner_id = actor.profile_id",
        "media.sha256 = review.media_sha256_snapshot",
        "job.project_id = review.project_id",
        "job.output ->> 'output_media_id' = media.id::text",
        "job.output ->> 'sha256' = media.sha256",
    ):
        assert token in predicate


def test_operator_does_not_enter_general_reviewer_pool() -> None:
    manager_filter = """candidate.role in (
      'owner', 'admin', 'producer', 'reviewer'
    )"""
    existing_assignment = "select assignment.* into existing_assignment_row"
    candidate_query = "select candidate.profile_id"
    assert manager_filter in ASSIGNMENT_SOURCE
    assert existing_assignment in ASSIGNMENT_SOURCE
    assert ASSIGNMENT_SOURCE.index(existing_assignment) < ASSIGNMENT_SOURCE.index(
        candidate_query
    )
    assert candidate_query in MIGRATION  # operator-first patch point
    assert "candidate.role in (\n      'owner', 'admin', 'producer', 'reviewer', 'operator'" not in MIGRATION
    assert "workspace_project_access_allowed(\n      candidate.organization_id" in MIGRATION


def test_decision_context_and_repair_keep_exact_predicate() -> None:
    for token in (
        "operator_self_decision_gates",
        "content_review_media_watch_required",
        "operator_context_independence",
        "generated_image_independent_review_required",
        "generated_video_independent_review_required",
        "operator_self_needs_changes_repair",
    ):
        assert token in MIGRATION
    needs_changes_gate = "if decision_row.decision <> 'needs_changes' then"
    self_independence_gate = "decision_row.decided_by in ("
    assert needs_changes_gate in REPAIR_SOURCE
    assert self_independence_gate in REPAIR_SOURCE
    assert REPAIR_SOURCE.index(needs_changes_gate) < REPAIR_SOURCE.index(
        self_independence_gate
    )
    assert "provider_spend_requires_separate_confirmation" in REPAIR_SOURCE


def test_external_ai_true_and_false_are_typed_not_truthy() -> None:
    for token in (
        "jsonb_typeof(review.input -> ''external_ai_processing_confirmed'') = ''boolean''",
        "jsonb_typeof(review_row.input -> ''external_ai_processing_confirmed'') is distinct from ''boolean''",
        "jsonb_typeof(source_review_row.input -> ''external_ai_processing_confirmed'') is distinct from ''boolean''",
    ):
        assert token in MIGRATION


def test_catalog_and_status_share_existing_assignment_shape() -> None:
    for token in (
        "creator_content_review_catalog_without_repair_actions",
        "creator_review_status_pre_operator_self_v1",
        "'independent_assignment'",
        "'status', coalesce(assignment_row.status, 'unassigned')",
        "'assigned_to_me', assigned_to_me_value",
        "'decision_eligible', decision_eligible_value",
        "revoke all on function public.creator_content_review_status(jsonb)",
        "grant execute on function public.creator_content_review_status(jsonb)",
    ):
        assert token in MIGRATION


def test_backfill_is_bounded_to_exact_qualified_operator_reviews() -> None:
    backfill = MIGRATION[
        MIGRATION.index("$backfill_operator_self_review_assignments$") :
        MIGRATION.index("$verify_operator_self_review_contract$")
    ]
    assert "qualified_operator_own_content_review_allowed(" in backfill
    assert "review.project_id" in backfill
    assert "review.requested_by" in backfill
    assert "not exists (\n        select 1\n        from content_factory.content_review_assignments" in backfill


def test_public_project_sound_and_assignment_topology_is_preserved() -> None:
    # 120004 patches private implementations in place; it does not replace
    # public decision/context project wrappers or their execute grants.
    for signature in (
        "create or replace function public.creator_decide_content_review(",
        "create or replace function public.creator_approve_generated_photo_review_with_context(",
        "create or replace function public.creator_approve_generated_video_review_with_context(",
    ):
        assert signature not in MIGRATION
        assert signature in PROJECT_SOURCE
    for alias in (
        "creator_decide_content_review_pre_project_v47",
        "creator_approve_generated_photo_review_with_context_pre_project_v47",
        "creator_approve_generated_video_review_with_context_pre_project_v47",
    ):
        assert alias in MIGRATION
        assert alias in PROJECT_SOURCE
    assert "creator_decide_content_review_without_sound_release_gate" in SOUND_SOURCE
    assert "creator_approve_generated_video_review_pre_sound_gate_v1" in SOUND_SOURCE
    assert "guard_generated_media_review_assignment_decision" in ASSIGNMENT_SOURCE
    assert "before insert on content_factory.content_review_decisions" in ASSIGNMENT_SOURCE
    assert "from public, anon, authenticated, service_role" in PROJECT_SOURCE


def test_pgtap_has_behavioral_auth_and_public_decision_coverage() -> None:
    assert "select plan(28)" in PGTAP
    for token in (
        "qualified exact operator owns this review lineage",
        "same-project qualified non-participant cannot self review",
        "qualified operator without explicit project ACL cannot self review",
        "revoked waiver is not a current qualification",
        "foreign project cannot reuse exact review lineage",
        "qualified operator is assigned their exact review first",
        "public exact operator decision rejects an unwatched render",
        "exact qualified operator can return their watched render for changes through the public project wrapper",
        "operator self decision remains immutable",
    ):
        assert token in PGTAP
