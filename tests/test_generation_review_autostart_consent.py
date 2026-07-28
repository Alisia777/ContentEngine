from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase/migrations/202607280006_generation_review_autostart_consent.sql"
).read_text(encoding="utf-8")
PGTAP = (
    ROOT / "supabase/tests/generation_review_autostart_consent_test.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")


def test_review_autostart_consent_sql_is_parseable() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(PGTAP)


def test_consent_is_private_immutable_and_bound_to_the_exact_paid_job() -> None:
    for token in (
        "generation_review_autostart_consents",
        "enable row level security",
        "from public, anon, authenticated",
        "generation_review_autostart_consent_append_only",
        "before update or delete",
        "foreign key (organization_id, generation_job_id)",
        "job_row.requested_by is distinct from user_id",
        "job_row.input ->> 'model' not in",
        "unique (organization_id, generation_job_id)",
    ):
        assert token in MIGRATION


def test_start_and_status_wrappers_preserve_prior_security_chain() -> None:
    for token in (
        "creator_start_real_generation_pre_review_autostart_v11",
        "creator_real_generation_status_pre_review_autostart_v2",
        "security definer",
        "grant execute on function public.creator_start_real_generation(jsonb)",
        "grant execute on function public.creator_real_generation_status(jsonb)",
        "notify pgrst, 'reload schema'",
    ):
        assert token in MIGRATION


def test_consent_is_explicit_versioned_and_never_enables_transcription() -> None:
    start = MIGRATION[
        MIGRATION.index(
            "create or replace function public.creator_start_real_generation("
        ) : MIGRATION.index(
            "create or replace function public.creator_real_generation_status("
        )
    ]
    for token in (
        "p_payload ? 'review_autostart_confirmed'",
        "p_payload ? 'review_autostart_terms_version'",
        "is distinct from 'true'::jsonb",
        "generated-video-qa-autostart-v1",
        "'transcription_requested', false",
        "generation_review_autostart_consent_invalid",
    ):
        assert token in start


def test_browser_recovers_server_consent_and_completed_jobs_after_reentry() -> None:
    for token in (
        "review_autostart_confirmed: true",
        "review_autostart_terms_version:",
        '"generated-video-qa-autostart-v1"',
        "normalizeBoolean(job?.review_autostart_confirmed)",
        "resumeGeneratedVideoQaRecovery",
        "recoveryJobIds",
        "waitForRealGenerationStatus(",
        "GENERATED_VIDEO_QA_RECOVERY_LIMIT",
    ):
        assert token in APP


def test_edge_preserves_and_validates_consent_across_start_and_status() -> None:
    for token in (
        '"review_autostart_confirmed"',
        '"review_autostart_terms_version"',
        "reviewAutostartKeyPresent",
        'value.review_autostart_confirmed !== true',
        '"generated-video-qa-autostart-v1"',
        "reviewAutostartConfirmed",
        "review_autostart_confirmed: job.reviewAutostartConfirmed",
        "startPayload.review_autostart_confirmed === true",
    ):
        assert token in EDGE


def test_pgtap_covers_privacy_append_only_and_wrapper_security() -> None:
    for token in (
        "durable generated-video QA consent table exists",
        "authenticated callers cannot read or forge consent rows",
        "generated-video QA consent is append-only",
        "paid-start wrapper preserves every earlier validation layer",
        "status returns the bounded consent flag without actor identity",
        "authenticated callers cannot bypass either public wrapper",
    ):
        assert token in PGTAP
