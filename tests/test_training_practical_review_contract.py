from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607190001_training_practical_review.sql"
)
SQL = MIGRATION.read_text(encoding="utf-8")
LOWER = SQL.casefold()
PGTAP = (
    ROOT / "supabase/tests/training_practical_review_test.sql"
).read_text(encoding="utf-8").casefold()
CREATOR_FACTORY = (
    ROOT / "supabase/tests/creator_factory_test.sql"
).read_text(encoding="utf-8").casefold()


def _public_function(name: str) -> tuple[str, str]:
    match = re.search(
        rf"create\s+or\s+replace\s+function\s+public\.{re.escape(name)}"
        rf"\s*\(.*?\)\s*returns\s+jsonb(?P<header>.*?)as\s+\$\$"
        rf"(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, name
    return match.group("header").casefold(), match.group("body").casefold()


def test_forward_migration_is_transactional_and_ordered_after_mastery_v4() -> None:
    assert MIGRATION.exists()
    assert (ROOT / "supabase/migrations/202607180007_training_mastery_v4.sql").exists()
    assert SQL.lstrip().casefold().startswith("begin;")
    assert SQL.rstrip().casefold().endswith("commit;")


def test_receipt_is_bounded_and_contains_no_raw_media_or_secret_payload() -> None:
    table = LOWER.split(
        "create table content_factory.training_practical_projects", 1
    )[1].split("create index", 1)[0]

    for field in (
        "evidence_kind",
        "evidence_url",
        "file_metadata",
        "learner_note",
        "review_note",
        "submission_revision",
        "submitted_at",
        "reviewed_at",
    ):
        assert field in table
    for prohibited in ("bytea", "raw_payload", "provider_payload", "access_token"):
        assert prohibited not in table
    assert "length(evidence_url) between 12 and 2000" in table
    assert "length(learner_note) <= 2000" in table
    assert "length(btrim(review_note)) between 1 and 4000" in table
    assert "file_metadata - array[" in table
    assert "token|signature|password|secret|api[_-]?key" in table


def test_rls_is_read_scoped_and_mutations_are_rpc_only() -> None:
    table_security = LOWER.split(
        "alter table content_factory.training_practical_projects enable row level security",
        1,
    )[1].split(
        "insert into storage.buckets",
        1,
    )[0]
    assert (
        "alter table content_factory.training_practical_projects enable row level security"
        in LOWER
    )
    assert "create policy training_practical_projects_select_scoped" in LOWER
    assert "profile_id = (select auth.uid())" in LOWER
    assert "manager.role in ('owner', 'admin')" in LOWER
    assert (
        "revoke all on content_factory.training_practical_projects\n"
        "  from public, anon, authenticated"
    ) in LOWER
    assert (
        "grant select on content_factory.training_practical_projects to authenticated"
        not in LOWER
    )
    assert "for insert\nto authenticated" not in table_security
    assert "for update\nto authenticated" not in table_security


def test_review_history_is_append_only_and_does_not_duplicate_evidence() -> None:
    history = LOWER.split(
        "create table content_factory.training_practical_review_decisions", 1
    )[1].split("create index", 1)[0]

    for field in (
        "project_id",
        "submission_revision",
        "decision",
        "review_note",
        "evidence_fingerprint",
        "reviewed_by",
        "reviewed_at",
    ):
        assert field in history
    for prohibited in (
        "evidence_url",
        "storage_object_id",
        "storage_object_name",
        "file_metadata",
        "learner_note",
    ):
        assert prohibited not in history
    assert "unique (organization_id, project_id, submission_revision)" in history
    assert "evidence_fingerprint ~ '^[0-9a-f]{64}$'" in history
    assert (
        "alter table content_factory.training_practical_review_decisions\n"
        "  enable row level security"
    ) in LOWER
    assert (
        "revoke all on content_factory.training_practical_review_decisions\n"
        "  from public, anon, authenticated"
    ) in LOWER
    assert (
        "grant select on content_factory.training_practical_review_decisions "
        "to authenticated"
    ) not in LOWER


def test_pre_exam_video_upload_uses_a_separate_private_storage_lane() -> None:
    assert "'contentengine-training'" in LOWER
    assert "false,\n  52428800" in LOWER
    assert "contentengine_training_select" in LOWER
    assert "contentengine_training_insert" in LOWER
    assert "contentengine_training_delete" in LOWER
    assert "split_part(storage.objects.name, '/', 3) = 'practical'" in LOWER
    assert "bucket_id = 'contentengine-training'" in LOWER
    assert "practical_project_storage_object_invalid" in LOWER
    assert "storage_object.metadata" in LOWER
    assert "storage_metadata_value ->> 'size'" in LOWER
    assert "storage_metadata_value ->> 'mimetype'" in LOWER


def test_practical_course_gate_pins_all_four_active_passed_certificates() -> None:
    gate = LOWER.split(
        "content_factory_private.training_practical_courses_complete(", 1
    )[1].split("$$;", 1)[0]

    for module_code in (
        "factory_basics",
        "video_quality",
        "publishing_funnel",
        "security_wb",
    ):
        assert f"'{module_code}'" in gate
    assert "count(distinct certification.module_code) = 4" in gate
    assert "module.module_type = 'course'" in gate
    assert "module.is_active" in gate
    assert "certification.status = 'passed'" in gate
    assert "certification.expires_at > now()" in gate
    assert (
        "revoke all on function\n"
        "  content_factory_private.training_practical_courses_complete(uuid, uuid)"
    ) in LOWER


def test_submit_rpc_has_state_machine_validation_and_idempotency() -> None:
    header, body = _public_function("creator_save_practical_project")
    assert "security definer" in header
    assert "set search_path = ''" in header
    assert "practical_project_payload_invalid" in body
    assert "practical_project_evidence_url_invalid" in body
    assert "practical_project_file_metadata_invalid" in body
    assert "practical_project_version_conflict" in body
    assert "rights_confirmed_value" in body
    assert "self_check_codes_value" in body
    assert "content_factory_private.begin_command" in body
    assert "pg_advisory_xact_lock" in body
    assert "practical_project_already_approved" in body
    assert "practical_project_review_pending" in body
    assert "action_value = 'submit'" in body
    assert "content_factory_private.training_practical_courses_complete(" in body
    assert "required_courses_incomplete" in body
    assert "training_practical_project_submitted" in body
    assert "content_factory_private.finish_command" in body


def test_manager_decision_is_role_scoped_audited_and_requires_feedback() -> None:
    header, body = _public_function("creator_decide_practical_project")
    assert "security definer" in header
    assert "array['owner', 'admin']" in body
    assert "decision_value not in ('approve', 'request_changes')" in body
    assert "length(review_note_value) not between 10 and 4000" in body
    assert "practical_project_media_watch_required" in body
    assert "expected_version_value" in body
    assert "project_row.status <> 'submitted'" in body
    assert "practical_project_self_review_not_allowed" in body
    assert "if project_row.profile_id = user_id then" in body
    assert "actor_role <> 'owner'" not in body
    assert "content_factory_private.training_practical_courses_complete(" in body
    assert "project_row.profile_id" in body
    assert "required_courses_incomplete" in body
    assert "project_row.evidence_kind <> 'uploaded_file'" in body
    assert "practical_project_private_file_required" in body
    assert "insert into content_factory.training_practical_review_decisions" in body
    assert "content_factory_private.json_hash(jsonb_build_object(" in body
    history_insert = body.split(
        "insert into content_factory.training_practical_review_decisions", 1
    )[1].split("update content_factory.training_practical_projects", 1)[0]
    assert "review_note_value" in history_insert
    assert "project_row.submission_revision" in history_insert
    assert "project_row.evidence_url" in history_insert
    assert "training_practical_project_approved" in body
    assert "training_practical_project_changes_requested" in body
    event_call = body.split("content_factory_private.emit_event", 1)[1]
    for sensitive in ("evidence_url_value", "file_metadata_value", "review_note_value"):
        assert sensitive not in event_call


def test_old_certificates_receive_explicit_approved_grandfather_receipts() -> None:
    grandfather = LOWER.split(
        "insert into content_factory.training_practical_projects", 1
    )[1].split("create or replace function public.creator_save", 1)[0]
    assert "from content_factory.training_certifications certification" in grandfather
    assert "certification.module_code = 'operator_final_exam'" in grandfather
    assert "certification.status = 'passed'" in grandfather
    assert "'approved'" in grandfather
    assert "'grandfathered'" in grandfather
    assert "on conflict (organization_id, profile_id) do nothing" in grandfather
    assert "missing_grandfathered" in LOWER


def test_exam_workspace_and_storage_share_the_approval_boundary() -> None:
    _, exam = _public_function("creator_submit_exam")
    _, bootstrap = _public_function("creator_bootstrap")

    assert "practical_project_approval_required" in exam
    assert "creator_submit_exam_pre_practical_gate" in exam
    assert exam.index("practical_project_approval_required") < exam.index(
        "creator_submit_exam_pre_practical_gate"
    )
    assert "training_practical_projects" in bootstrap
    assert "'practical_project', practical_project" in bootstrap
    assert "'practical_reviews', practical_reviews" in bootstrap
    assert "'learner_name'" in bootstrap and "'learner_email'" in bootstrap
    assert "'practical_upload'" in bootstrap
    assert "limit 50" in bootstrap
    assert "'{workspace_open}', 'false'::jsonb" in bootstrap
    assert "'{learning,exam,available}', 'false'::jsonb" in bootstrap
    assert "practical_project_approval_required" in bootstrap

    assert "membership_role_pre_practical_gate" in LOWER
    assert "storage_access_allowed_pre_practical_gate" in LOWER
    assert "training_practical_gate_satisfied" in LOWER
    assert LOWER.count(
        "content_factory_private.training_practical_gate_satisfied("
    ) >= 5
    assert "drop policy if exists contentengine_private_select" in LOWER
    assert "drop policy if exists contentengine_private_insert" in LOWER
    assert "drop policy if exists contentengine_private_delete" in LOWER


def test_database_workflow_and_legacy_fixture_cover_the_new_gate() -> None:
    for marker in (
        "practical_project_approval_required",
        "creator_save_practical_project",
        "creator_decide_practical_project",
        "changes_requested",
        "uploaded_file",
        "required_courses_incomplete",
        "practical_project_private_file_required",
        "approval rechecks all four learner certificates",
        "owner cannot approve their own practical submission",
        "audit events never copy evidence urls",
    ):
        assert marker in PGTAP

    submit = CREATOR_FACTORY.index("creator_save_practical_project")
    approve = CREATOR_FACTORY.index("creator_decide_practical_project", submit)
    exam = CREATOR_FACTORY.index("creator_submit_exam", approve)
    assert submit < approve < exam
    assert "48,\n  'all browser rpcs expose exactly p_payload jsonb'" in CREATOR_FACTORY
    assert "48,\n  'authenticated can execute all creator rpcs'" in CREATOR_FACTORY
