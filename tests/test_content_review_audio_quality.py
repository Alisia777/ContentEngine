from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "web/app/content-review-view.js"
API = ROOT / "web/app/supabase-api.js"
EDGE = ROOT / "supabase/functions/creator-content-review/index.ts"
MIGRATION = (
    ROOT
    / "supabase/migrations/202607260002_content_review_audio_quality_metrics.sql"
)
TRAINING_MIGRATION = (
    ROOT
    / "supabase/migrations/202607260003_content_review_audio_quality_training.sql"
)


def _evaluate_audio(samples: str, *, expected_audio: bool) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for audio quality contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            VIEW.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            """
import { analyzeDecodedAudioBuffer } from "./subject.mjs";
const sampleRate = 8000;
const samples = new Float32Array(sampleRate);
"""
            + samples
            + """
const buffer = {
  numberOfChannels: 1,
  sampleRate,
  length: samples.length,
  duration: 1,
  getChannelData(channel) {
    if (channel !== 0) throw new Error("channel");
    return samples;
  },
};
const result = analyzeDecodedAudioBuffer(buffer, {
  expectedAudio: EXPECTED_AUDIO,
  videoDurationSeconds: 1,
});
process.stdout.write(JSON.stringify(result));
""".replace("EXPECTED_AUDIO", "true" if expected_audio else "false"),
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_local_audio_analyzer_measures_silence_without_claiming_transcription() -> None:
    result = _evaluate_audio("", expected_audio=True)
    assert result["audio_expected"] is True
    assert result["audio_analyzed"] is True
    assert result["audio_analysis_status"] == "completed"
    assert result["audio_duration_seconds"] == 1
    assert result["audio_video_duration_delta_seconds"] == 0
    assert result["audio_peak_dbfs"] == -160
    assert result["audio_rms_dbfs"] == -160
    assert result["audio_silence_ratio"] == 1
    assert result["audio_clipping_ratio"] == 0


def test_local_audio_analyzer_detects_clipping_and_clean_signal() -> None:
    clipped = _evaluate_audio(
        "for (let index = 0; index < samples.length; index += 1) "
        "samples[index] = index % 2 ? 1 : -1;\n",
        expected_audio=True,
    )
    assert clipped["audio_peak_dbfs"] == 0
    assert clipped["audio_rms_dbfs"] == 0
    assert clipped["audio_silence_ratio"] == 0
    assert clipped["audio_clipping_ratio"] == 1

    clean = _evaluate_audio(
        "for (let index = 0; index < samples.length; index += 1) "
        "samples[index] = 0.25 * Math.sin(2 * Math.PI * 440 * index / sampleRate);\n",
        expected_audio=False,
    )
    assert clean["audio_expected"] is False
    assert -15.2 < clean["audio_rms_dbfs"] < -14.9
    assert -12.1 < clean["audio_peak_dbfs"] < -11.9
    assert clean["audio_silence_ratio"] == 0
    assert clean["audio_clipping_ratio"] == 0


def test_audio_measurement_is_bounded_local_and_separate_from_transcription() -> None:
    view = VIEW.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    for marker in (
        "MAX_AUDIO_SOURCE_BYTES = 52_428_800",
        "AUDIO_ANALYSIS_TIMEOUT_MS = 20_000",
        "readResponseArrayBufferBounded",
        "decodeAudioData",
        "audio_analysis_status",
        "audio_silence_ratio",
        "audio_clipping_ratio",
        "raw_video_sent: false",
        'speech_transcription_notice_version: "openai_mp4_v1"',
    ):
        assert marker in view
    assert "validContentReviewTechnicalMetrics" in api
    assert "input_audio" not in view
    assert "input_audio" not in EDGE.read_text(encoding="utf-8")


def test_edge_adds_deterministic_audio_findings_but_keeps_human_speech_gate() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    for finding_code in (
        "TECH.AUDIO_ANALYSIS_UNAVAILABLE",
        "TECH.AUDIO_METADATA_MISSING",
        "TECH.AUDIO_SILENT",
        "TECH.AUDIO_MOSTLY_SILENT",
        "TECH.UNEXPECTED_AUDIO",
        "TECH.AUDIO_CLIPPING",
        "TECH.AUDIO_DURATION_MISMATCH",
        "SCOPE.AUDIO_MANUAL_REVIEW",
    ):
        assert finding_code in edge
    assert "Не выдавай эти числа за транскрипцию" in edge
    assert "подтверждённой расшифровки произнесённых слов нет" in edge
    assert "audioSilenceRatio >= 0.95" in edge
    assert "audioClippingRatio >= 0.05 ? \"blocker\" : \"high\"" in edge
    assert "measuredTechnicalFindingCodes" in edge
    assert "technicalScoreCap" in edge
    assert "overallScoreCap" in edge
    assert "scores: finalScores" in edge
    assert '"TECH.AUDIO_ANALYSIS_UNAVAILABLE"' not in edge[
        edge.index("const measuredTechnicalFindingCodes") :
        edge.index("const measuredTechnicalFindings")
    ]


def test_database_accepts_legacy_evidence_and_bounds_new_audio_metrics() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "valid_content_review_audio_metrics",
        "content_review_evidence_audio_metrics_valid",
        "audio_analyzed",
        "audio_analysis_status",
        "audio_expected",
        "audio_channel_count",
        "audio_sample_rate_hz",
        "audio_duration_seconds",
        "audio_video_duration_delta_seconds",
        "audio_peak_dbfs",
        "audio_rms_dbfs",
        "audio_silence_ratio",
        "audio_clipping_ratio",
        "validate constraint content_review_evidence_audio_metrics_valid",
        "creator_commit_content_review_evidence_without_audio_gate_v1",
        "content_review_evidence_audio_metrics_invalid",
        "audio-prefixed fields cannot bypass the analysis contract",
    ):
        assert marker in (
            migration
            + (
                ROOT / "supabase/tests/content_review_audio_quality_test.sql"
            ).read_text(encoding="utf-8")
        )
    assert "Historical ready evidence" in migration
    assert "between -160 and 0" in migration
    assert "between 0 and 1" in migration


def test_training_explains_audio_measurements_without_overclaiming() -> None:
    migration = TRAINING_MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "full_video_qa",
        "локально измеряет",
        "не расшифровывают слова",
        "97% тишины",
        "course_check_video_quality_succeeded_status",
        "reject_with_timestamps",
        "точные слова",
        "content review audio quality training contract failed",
        "content review audio assessment contract failed",
    ):
        assert marker in migration
