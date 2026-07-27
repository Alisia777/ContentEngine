from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607270007_generated_media_review_assignment.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generated_media_review_assignment_test.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/content-review-view.js").read_text(encoding="utf-8")


def test_assignment_sql_and_pgtap_are_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(PGTAP)


def test_assignment_excludes_every_generation_participant() -> None:
    for token in (
        "candidate.profile_id is distinct from review_row.requested_by",
        "candidate.profile_id is distinct from media_row.owner_id",
        "candidate.profile_id is distinct from job_row.requested_by",
        "candidate.profile_id is distinct from job_row.assigned_to",
        "candidate.status = 'active'",
        "'owner', 'admin', 'producer', 'reviewer'",
        "generated_media_reviewer_access_allowed(",
        "count(*) filter (",
        "max(assignment.assigned_at) as last_assigned_at",
        "coalesce(load.open_count, 0)",
        "when 'reviewer' then 1",
        "on conflict (organization_id, review_id) do nothing",
    ):
        assert token in MIGRATION


def test_assignment_is_exact_private_and_immutable() -> None:
    for token in (
        "review_row.status <> 'completed'",
        "review_row.input -> 'ai_generated'",
        "review_row.input ? 'context_amendment'",
        "media_row.sha256 <> review_row.media_sha256_snapshot",
        "job_row.status is distinct from 'succeeded'",
        "job_row.output ->> 'output_media_id'",
        "job_row.output ->> 'sha256'",
        "content_review_assignment_immutable",
        "enable row level security",
        "from public, anon, authenticated, service_role",
    ):
        assert token in MIGRATION


def test_assignment_uses_the_complete_current_training_boundary() -> None:
    access = MIGRATION[
        MIGRATION.index(
            "generated_media_reviewer_access_allowed("
        ):
        MIGRATION.index(
            "generated_media_review_assignment_required("
        )
    ]
    for token in (
        "training_access_waiver_active(",
        "module_code = 'operator_final_exam'",
        "module.module_type = 'course'",
        "attempt.idempotency_key like 'course-check:%'",
        "attempt.answered_count = attempt.question_count",
        "training_practical_gate_satisfied(",
        "organization.status = 'active'",
        "profile.status = 'active'",
    ):
        assert token in access


def test_assignment_is_serialized_and_server_enforced() -> None:
    lock = "pg_catalog.hashtext('generated_media_review_assignment')"
    existing = (
        "select assignment.* into existing_assignment_row"
    )
    candidate = "select candidate.profile_id"
    assert lock in MIGRATION
    assert MIGRATION.index(lock) < MIGRATION.index(existing)
    assert MIGRATION.index(existing) < MIGRATION.index(candidate)
    for token in (
        "generated_media_review_assignment_required(",
        "guard_generated_media_review_assignment_decision",
        "before insert on content_factory.content_review_decisions",
        "independent_reviewer_assignment_required",
        "content_review_assigned_to_another_reviewer",
        "new.decided_by is distinct from assignee_id_value",
        "content_review_context_amendments amendment",
        "amendment.source_review_id",
        "newly qualified teammate",
        "where assignment.id is null",
    ):
        assert token in MIGRATION


def test_catalog_exposes_only_current_user_routing_booleans() -> None:
    wrapper = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_content_review_catalog("
        ):
    ]
    for token in (
        "'independent_assignment'",
        "'assigned_to_me'",
        "'decision_eligible'",
        "'assigned_at'",
        "'completed_at'",
    ):
        assert token in wrapper
    for forbidden in (
        "'assignee_id'",
        "'assignee_name'",
        "'assignee_email'",
    ):
        assert forbidden not in wrapper


def test_home_prioritizes_exact_assigned_review() -> None:
    home = APP[
        APP.index("function homeNextAction("):
        APP.index("function renderHomeSection(")
    ]
    for token in (
        "item.independentAssignment?.status === \"assigned\"",
        "item.independentAssignment.assignedToMe",
        "item.independentAssignment.decisionEligible",
        "`#/workspace/review/${assignedReview.id}`",
        "Назначен независимый QA",
    ):
        assert token in home
    assert home.index("const assignedReview") < home.index("const activeTask")


def test_review_ui_hides_self_review_and_other_reviewer_assignment() -> None:
    for token in (
        "normalizeIndependentAssignment",
        "independentAssignment",
        "independent_reviewer_required",
        "independent_reviewer_assignment_required",
        "independent_review_completed",
        "assigned_to_another_reviewer",
        "Вы участвовали в создании этого результата",
        "Пока нет другого участника с действующим допуском",
        "Независимый QA уже завершён через подтверждение точного контекста",
        "Независимый QA уже назначен другому участнику",
        "Эта независимая проверка назначена вам",
    ):
        assert token in VIEW
