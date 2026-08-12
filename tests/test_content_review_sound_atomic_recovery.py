from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202608120003_content_review_sound_atomic_recovery.sql"
)
PROJECT_SCOPE_PATH = (
    ROOT / "supabase/migrations/202608040005_project_scoped_workflow.sql"
)
CATALOG_MEDIA_PATH = (
    ROOT / "supabase/migrations/202608100013_content_review_catalog_media_status.sql"
)


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable portal contracts")
    script = (
        f"import * as subject from {json.dumps(path.resolve().as_uri())};\n"
        f"const result = await (async () => {{\n{body}\n}})();\n"
        "process.stdout.write(JSON.stringify(result));\n"
    )
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _function(source: str, declaration: str) -> str:
    start = source.index(declaration)
    body_match = re.search(r"\)\s*\{", source[start:])
    assert body_match, f"Missing JavaScript function body: {declaration}"
    opening = start + body_match.end() - 1
    depth = 0
    quote = ""
    escaped = False
    template_expression_depth = 0
    for index in range(opening, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif quote == "`" and char == "$" and source[index + 1:index + 2] == "{":
                template_expression_depth += 1
            elif char == quote and template_expression_depth == 0:
                quote = ""
            elif quote == "`" and char == "}" and template_expression_depth:
                template_expression_depth -= 1
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"Unclosed JavaScript function: {declaration}")


def _sql_function(source: str, signature: str) -> str:
    start = source.lower().index(signature.lower())
    end = source.lower().index("\nend;\n$$;", start) + len("\nend;\n$$;")
    return source[start:end]


def test_double_normalization_preserves_authoritative_sound_truth() -> None:
    result = _run_module(
        APP_DIR / "content-review-view.js",
        """
        const raw = {
          run: {
            id: "916e8785-1111-4111-8111-111111111111",
            status: "completed",
            media_id: "7d817e00-2222-4222-8222-222222222222",
            input: { platform: "instagram", content_kind: "advertising" },
            media: {
              id: "7d817e00-2222-4222-8222-222222222222",
              kind: "generated_video",
              mime_type: "video/mp4",
              is_video: true,
              status: "ready",
              url: "blob:exact-generated-video",
              audio: true,
            },
            decision: {
              decision: "needs_changes",
              comment: "Русские слова и окончания искажены.",
            },
            sound_assessment: {
              id: "aaaaaaaa-3333-4333-8333-333333333333",
              status: "issues_found",
              audio: true,
              issue_codes: ["slurred_words", "wrong_words"],
              note: "Слова смазаны и заменены.",
            },
            sound_recovery_eligible: false,
          },
        };
        const first = subject.normalizeContentReviewRun(raw);
        const second = subject.normalizeContentReviewRun(first);
        const markup = subject.contentReviewWorkspaceMarkup({
          catalog: { media: [], runs: [first] },
          currentRun: first,
          view: "current",
          canDecide: true,
        });
        return {
          firstStatus: first.soundAssessment?.status || null,
          secondStatus: second.soundAssessment?.status || null,
          secondCodes: second.soundAssessment?.issueCodes || [],
          hasRecordedSummary: markup.includes("Найдены ошибки звука"),
          falselyMissing: markup.includes("Звук: нет отдельной записи"),
          hasRecovery: markup.includes("content-review-sound-recovery-form"),
        };
        """,
    )
    assert result == {
        "firstStatus": "issues_found",
        "secondStatus": "issues_found",
        "secondCodes": ["slurred_words", "wrong_words"],
        "hasRecordedSummary": True,
        "falselyMissing": False,
        "hasRecovery": False,
    }


def test_recovery_is_visible_only_for_missing_generated_video_truth() -> None:
    result = _run_module(
        APP_DIR / "content-review-view.js",
        """
        const base = {
          id: "916e8785-1111-4111-8111-111111111111",
          status: "completed",
          input: { platform: "instagram", contentKind: "advertising" },
          result: {},
          decision: {
            decision: "needs_changes",
            reason: "Русские слова и окончания искажены.",
          },
          media: {
            id: "7d817e00-2222-4222-8222-222222222222",
            kind: "generated_video",
            mimeType: "video/mp4",
            isVideo: true,
            status: "ready",
            url: "blob:exact-generated-video",
            audioExpected: true,
          },
          soundRecoveryEligible: true,
        };
        const render = (run) => subject.contentReviewWorkspaceMarkup({
          catalog: { media: [], runs: [run] },
          currentRun: run,
          view: "current",
          canDecide: true,
        });
        const eligible = render(base);
        const hasAssessment = render({
          ...base,
          soundAssessment: {
            status: "issues_found",
            issueCodes: ["slurred_words", "wrong_words"],
            note: "Слова смазаны и заменены.",
          },
        });
        const image = render({
          ...base,
          media: { ...base.media, kind: "generated_image", isVideo: false },
        });
        return {
          eligibleForm: eligible.includes("content-review-sound-recovery-form"),
          exactMedia: eligible.includes("data-content-review-exact-media"),
          audibleConfirmation: eligible.includes("media_watched_confirmed"),
          soundFields: eligible.includes('name="sound_issue_codes"'),
          immutableCopy: eligible.includes("останется неизменным"),
          existingAssessmentForm: hasAssessment.includes(
            "content-review-sound-recovery-form",
          ),
          imageForm: image.includes("content-review-sound-recovery-form"),
        };
        """,
    )
    assert result == {
        "eligibleForm": True,
        "exactMedia": True,
        "audibleConfirmation": True,
        "soundFields": True,
        "immutableCopy": True,
        "existingAssessmentForm": False,
        "imageForm": False,
    }


def test_client_recovery_payload_is_exact_and_required() -> None:
    start = API.index("  recoverContentReviewSoundAssessment(")
    end = API.index("\n  restoreProjectPlacement(", start)
    method = API[start:end]
    for token in (
        "RPC.recoverContentReviewSoundAssessment",
        "this.requireContentReviewId(reviewId)",
        "requiredProjectId(projectIdSnake || projectId)",
        "media_watched_confirmed: true",
        "sound_assessment: safeSoundAssessment",
        "{ required: true }",
    ):
        assert token in method
    assert "decision:" not in method
    assert "comment:" not in method


def test_recovery_handler_refreshes_same_review_without_side_effects() -> None:
    handler = _function(
        APP,
        "async function submitContentReviewSoundRecovery(form)",
    )
    for token in (
        "review.record.soundRecoveryEligible !== true",
        "contentReviewExactMediaReady(form)",
        "validateGeneratedVideoSoundAssessment(",
        "review.record.decision.decision",
        "state.api.recoverContentReviewSoundAssessment(",
        "state.api.contentReviewStatus(reviewId, { projectId })",
        "state.api.contentReviewCatalog({ limit: 50, projectId })",
        'track("content_review_sound_assessment_recovered"',
    ):
        assert token in handler
    for forbidden in (
        "decideContentReview(",
        "loadGenerationRepairForReview(",
        "flowHandoff(",
        "generate",
        "provider",
        "spend",
    ):
        assert forbidden not in handler


def test_database_enforces_future_decision_and_sound_atomicity() -> None:
    assert MIGRATION_PATH.exists()
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    lowered = migration.lower()
    for token in (
        "create constraint trigger enforce_generated_video_decision_sound_atomic",
        "after insert on content_factory.content_review_decisions",
        "deferrable initially deferred",
        "content_review_sound_assessment_required",
        "assessment.decision_id = new.id",
        "media.metadata ->> 'kind' = 'generated_video'",
        "media.mime_type = 'video/mp4'",
    ):
        assert token in lowered


def test_recovery_rpc_is_same_actor_project_scoped_and_append_only() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    recovery = _sql_function(
        migration,
        "create or replace function\n  public.creator_recover_content_review_sound_assessment",
    )
    for token in (
        "current_profile_id()",
        "membership_role(",
        "true,",
        "'operator'",
        "require_workspace_project(",
        "review.project_id = project_id_value",
        "decision_row.decided_by is distinct from user_id_value",
        "media_row.status is distinct from 'ready'",
        "media_row.sha256 is distinct from review_row.media_sha256_snapshot",
        "content_review_sound_recovery_media_not_ready",
        "media_watched_confirmed",
        "normalize_content_review_sound_assessment(",
        "record_content_review_sound_assessment(",
        "decision_row.id",
        "'direct_decision'",
    ):
        assert token in recovery
    assert "update content_factory.content_review_decisions" not in recovery.lower()
    assert "delete from content_factory.content_review_decisions" not in recovery.lower()


def test_latest_project_wrappers_are_preserved_then_truth_enriched() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    project_scope = PROJECT_SCOPE_PATH.read_text(encoding="utf-8")
    catalog_media = CATALOG_MEDIA_PATH.read_text(encoding="utf-8")

    assert PROJECT_SCOPE_PATH.name < CATALOG_MEDIA_PATH.name < MIGRATION_PATH.name
    assert "creator_content_review_status_pre_project_v47" in project_scope
    assert "creator_content_review_catalog_pre_project_v47" in project_scope
    assert "creator_content_review_catalog_pre_media_status" in catalog_media

    for token in (
        "alter function public.creator_content_review_status(jsonb)",
        "rename to creator_review_status_pre_sound_truth_v2",
        ".creator_review_status_pre_sound_truth_v2(p_payload)",
        "alter function public.creator_content_review_catalog(jsonb)",
        "rename to creator_review_catalog_pre_sound_truth_v2",
        ".creator_review_catalog_pre_sound_truth_v2(p_payload)",
        "content_review_sound_assessments",
        "sound_assessment_history",
        "sound_recovery_eligible",
    ):
        assert token in migration
