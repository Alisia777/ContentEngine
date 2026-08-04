from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")
HANDOFF = (APP_DIR / "content-generation-handoff.js").read_text(
    encoding="utf-8"
)
EDGE = (
    ROOT / "supabase/functions/creator-generate/index.ts"
).read_text(encoding="utf-8")
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202608040004_generated_video_sound_release_gate.sql"
)
PROJECT_MIGRATION_PATH = (
    ROOT / "supabase/migrations/202608040005_project_scoped_workflow.sql"
)


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable portal contracts")
    source_url = path.resolve().as_uri()
    script = (
        f"import * as subject from {json.dumps(source_url)};\n"
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


def test_seedance_exact_russian_line_always_carries_diction_guard() -> None:
    result = _run_module(
        APP_DIR / "content-generation-handoff.js",
        """
        const compiled = subject.compileSafeGenerationBrief({
          mode: "real_seedance",
          productName: "Пароварка QEEP",
          sku: "QEEP-STEAM-1",
          scenarioIntent: "Герой говорит: «Товарищи. Вот. Пароварка.»",
          durationSeconds: 12,
          productCategory: "household",
        });
        return {
          ready: compiled.ready,
          spokenWords: compiled.spokenWords,
          exactLineCount: compiled.prompt.split(
            "Реплика героя дословно: «Товарищи. Вот. Пароварка.»",
          ).length - 1,
          hasGuard: compiled.prompt.includes(
            subject.SEEDANCE_RUSSIAN_DICTION_GUARD,
          ),
          guardCount: compiled.prompt.split(
            subject.SEEDANCE_RUSSIAN_DICTION_GUARD,
          ).length - 1,
        };
        """,
    )
    assert result == {
        "ready": True,
        "spokenWords": 3,
        "exactLineCount": 1,
        "hasGuard": True,
        "guardCount": 1,
    }
    assert "SEEDANCE_RUSSIAN_DICTION_GUARD" in EDGE
    assert "russian_diction_guard_missing" in HANDOFF
    assert "!payload.brief.includes(SEEDANCE_RUSSIAN_DICTION_GUARD)" in EDGE


def test_sound_assessment_is_a_separate_fail_closed_decision() -> None:
    result = _run_module(
        APP_DIR / "content-review-view.js",
        """
        const clear = {
          status: "clear",
          issueCodes: [],
          spokenScriptHeardExactlyConfirmed: true,
          dictionClearConfirmed: true,
          voiceStyleConfirmed: true,
          audioSyncConfirmed: true,
          silenceExpectedConfirmed: false,
          note: "",
        };
        const issues = {
          ...clear,
          status: "issues_found",
          issueCodes: ["slurred_words", "foreign_accent"],
          spokenScriptHeardExactlyConfirmed: false,
          dictionClearConfirmed: false,
          note: "Слышно: товарищки воть пароваркаа",
        };
        return {
          clearApproval: subject.validateGeneratedVideoSoundAssessment(
            clear, { audioExpected: true, decision: "approved" },
          ),
          missingDiction: subject.validateGeneratedVideoSoundAssessment(
            { ...clear, dictionClearConfirmed: false },
            { audioExpected: true, decision: "approved" },
          ),
          issueApproval: subject.validateGeneratedVideoSoundAssessment(
            issues, { audioExpected: true, decision: "approved" },
          ),
          issueRepair: subject.validateGeneratedVideoSoundAssessment(
            issues, { audioExpected: true, decision: "needs_changes" },
          ),
          silent: subject.validateGeneratedVideoSoundAssessment(
            {
              status: "silent_expected",
              issueCodes: [],
              silenceExpectedConfirmed: true,
            },
            { audioExpected: false, decision: "approved" },
          ),
          unexpectedSilentAudio: subject.validateGeneratedVideoSoundAssessment(
            {
              status: "issues_found",
              issueCodes: ["unexpected_audio", "noise_clipping"],
              silenceExpectedConfirmed: false,
              note: "На 00:04 появилась чужая речь",
            },
            { audioExpected: false, decision: "needs_changes" },
          ),
          unexpectedSilentAudioApproval: subject.validateGeneratedVideoSoundAssessment(
            {
              status: "issues_found",
              issueCodes: ["unexpected_audio"],
              silenceExpectedConfirmed: false,
              note: "Слышна неожиданная речь",
            },
            { audioExpected: false, decision: "approved" },
          ),
        };
        """,
    )
    assert result["clearApproval"] == {
        "valid": True,
        "code": "sound_clear_confirmed",
    }
    assert result["missingDiction"] == {
        "valid": False,
        "code": "sound_clear_confirmation_required",
    }
    assert result["issueApproval"] == {
        "valid": False,
        "code": "sound_issues_block_approval",
    }
    assert result["issueRepair"] == {
        "valid": True,
        "code": "sound_issues_recorded",
    }
    assert result["silent"] == {
        "valid": True,
        "code": "sound_silent_confirmed",
    }
    assert result["unexpectedSilentAudio"] == {
        "valid": True,
        "code": "sound_issues_recorded",
    }
    assert result["unexpectedSilentAudioApproval"] == {
        "valid": False,
        "code": "sound_issues_block_approval",
    }


def test_portal_records_diction_errors_and_requires_audible_full_playback() -> None:
    for token in (
        'name="sound_status"',
        'name="sound_issue_codes"',
        '"spoken_script_heard_exactly_confirmed"',
        '"diction_clear_confirmed"',
        '"voice_style_confirmed"',
        '"audio_sync_confirmed"',
        'name="sound_note"',
        '"unexpected_audio"',
        "Найдены ошибки звука",
        "неизменяемую историю QA",
    ):
        assert token in VIEW
    for token in (
        "contentReviewAudibleComplete",
        "media.muted",
        "media.volume <= 0",
        "media.playbackRate > 1.1",
        'media.addEventListener("seeking"',
        "validateGeneratedVideoSoundAssessment",
        "sound_issue_codes",
        "Рендер готов · звук не принят",
    ):
        assert token in APP
    for token in (
        "normalizeGeneratedVideoSoundAssessment",
        "audio: value.audio === true",
        "sound_assessment: safeSoundAssessment",
    ):
        assert token in API


def test_database_gate_is_append_only_and_cannot_be_bypassed_by_api() -> None:
    assert MIGRATION_PATH.exists(), "sound release gate migration must be added"
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    for token in (
        "content_review_sound_assessments",
        "generated-video-sound-v1",
        "content_review_sound_assessment_immutable",
        "content_review_sound_assessment_required",
        "content_review_sound_issues_block_approval",
        "creator_decide_content_review",
        "creator_approve_generated_video_review_with_context",
        "creator_content_review_status",
        "creator_content_review_catalog",
    ):
        assert token in migration
    assert "before update or delete" in migration.lower()
    assert "grant execute" in migration.lower()


def test_project_scope_wraps_the_preserved_sound_gate_in_migration_order() -> None:
    assert MIGRATION_PATH.name < PROJECT_MIGRATION_PATH.name
    project_migration = PROJECT_MIGRATION_PATH.read_text(encoding="utf-8")

    for alias in (
        "creator_decide_content_review_pre_project_v47",
        "creator_approve_generated_video_review_with_context_pre_project_v47",
        "creator_content_review_status_pre_project_v47",
        "creator_content_review_catalog_pre_project_v47",
    ):
        assert alias in project_migration

    assert "creator_approve_generated_video_review_pre_sound_gate_v1" in (
        project_migration
    )
    assert (
        "project_payload_from_context_v47(p_payload)" in project_migration
    )
