from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/creator-content-review/index.ts"
VIEW = ROOT / "web/app/content-review-view.js"
APP = ROOT / "web/app/app.js"
MIGRATION = (
    ROOT
    / "supabase/migrations/202607260006_content_review_speech_script_agreement.sql"
)
TRAINING = (
    ROOT
    / "supabase/migrations/202607260007_content_review_speech_training.sql"
)
PGTAP = ROOT / "supabase/tests/content_review_speech_agreement_test.sql"


def test_transcription_is_explicit_bounded_and_versioned() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    view = VIEW.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    for marker in (
        'OPENAI_TRANSCRIPTIONS_URL =',
        '"https://api.openai.com/v1/audio/transcriptions"',
        "MAX_TRANSCRIPTION_MEDIA_BYTES = 25_000_000",
        "MAX_TRANSCRIPTION_DURATION_SECONDS = 90",
        'return configured === "gpt-4o-mini-transcribe"',
        ': "gpt-4o-transcribe"',
        '"external_ai_processing_confirmed"',
        "speech_transcription_notice_version",
        '"openai_mp4_v1"',
        'transcriptionBody.append("response_format", "json")',
        'transcriptionBody.append("include[]", "logprobs")',
    ):
        assert marker in edge
    assert "Исходный MP4 передаётся в OpenAI Transcriptions только" in view
    assert "полный текст расшифровки не сохраняется" in view
    assert 'speech_transcription_notice_version: "openai_mp4_v1"' in view
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 8" in app
    assert "GENERATED_VIDEO_QA_STORAGE_VERSION = 6" in app


def test_transcription_shares_the_irreversible_dispatch_fence() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    dispatch = edge.index("const dispatchState = await beginProviderDispatch(attempt)")
    marker = edge.index("providerDispatchStarted = true", dispatch)
    transcription_post = edge.index("transcriptionPromise = fetchWithTimeout(", marker)
    assert dispatch < marker < transcription_post
    assert '"idempotency-key":' in edge[transcription_post : transcription_post + 900]
    assert '"X-Client-Request-Id": `${attempt.id}-transcription`' in edge
    assert "Another browser/worker invocation owns the irreversible provider POST" in edge


def test_script_comparison_is_deterministic_and_does_not_prompt_bias_asr() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    for marker in (
        "normalizedSpeechWords",
        "tokenEditDistance",
        "tokenLcsLength",
        "coverageRatio",
        "precisionRatio",
        "similarityRatio",
        "wordErrorRate",
        '"SPEECH.SCRIPT_MISMATCH"',
        '"SPEECH.SCRIPT_VARIATION"',
        '"SPEECH.SCRIPT_MATCH"',
        "const clarityScoreCap = speechMismatch",
        "const speechOverallScoreCap = speechMismatch",
    ):
        assert marker in edge
    transcription_form = edge[
        edge.index("const transcriptionBody = new FormData()") :
        edge.index("transcriptionPromise = fetchWithTimeout(")
    ]
    assert 'append("prompt"' not in transcription_form
    assert "MAX_TRANSCRIPT_EXCERPT_CHARACTERS = 1_200" in edge
    assert "transcript.slice(0, MAX_TRANSCRIPT_EXCERPT_CHARACTERS)" in edge
    assert "transcriptSha256: await sha256Hex(transcriptBytes)" in edge


def test_generated_spoken_line_and_private_result_contract_are_server_owned() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    pgtap = PGTAP.read_text(encoding="utf-8")
    for marker in (
        "generated_video_spoken_script",
        "Реплика героя дословно:",
        "bind_generated_video_spoken_script",
        "spoken_script_source",
        "generation_job_prompt_v1",
        "validate_content_review_result_without_speech_v4",
        "content_review_speech_analysis_invalid",
        "gpt-4o-transcribe",
        "transcript_sha256",
        "transcript_excerpt",
        "word_error_rate",
        "completed transcription cannot exist without explicit consent",
        "browser sessions cannot bypass the speech-result validator",
    ):
        assert marker in migration + pgtap


def test_training_preserves_consent_privacy_and_human_playback() -> None:
    training = TRAINING.read_text(encoding="utf-8")
    for marker in (
        "OpenAI Transcriptions",
        "25 МБ",
        "90 секунд",
        "Полная расшифровка не сохраняется",
        "92% сходства",
        "Полностью воспроизвести",
        "content review speech training contract failed",
        "content review speech assessment contract failed",
    ):
        assert marker in training
