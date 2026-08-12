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
APP = ROOT / "web/app/app.js"
EDGE = ROOT / "supabase/functions/creator-content-review/index.ts"
MIGRATION = (
    ROOT
    / "supabase/migrations/202607280007_content_review_frame_continuity.sql"
)
EXTENSION_MIGRATION = (
    ROOT
    / "supabase/migrations/202607280009_generated_video_15s_continuity.sql"
)
FALLBACK_MIGRATION = (
    ROOT
    / "supabase/migrations/202608120002_content_review_dense_seek_continuity.sql"
)
PGTAP = ROOT / "supabase/tests/content_review_frame_continuity_test.sql"


def _run_node_module(source: str, *, timeout: int = 10) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for frame-continuity contracts")
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _evaluate_continuity(
    samples: str,
    times: str,
    presented_frames: str,
    duration: float = 1,
    *,
    expect_failure: bool = False,
) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for frame-continuity contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            VIEW.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            f"""
import {{ analyzeVideoContinuitySamples }} from "./subject.mjs";
const samples = {samples};
const times = {times};
const presentedFrames = {presented_frames};
const result = analyzeVideoContinuitySamples(
  samples,
  times,
  presentedFrames,
  {duration},
);
process.stdout.write(JSON.stringify(result));
""",
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
    if expect_failure:
        assert result.returncode != 0
        return {}
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_presented_frame_scan_measures_full_short_video_continuity() -> None:
    result = _evaluate_continuity(
        """Array.from({ length: 6 }, (_, index) => ({
  mean: 80 + index,
  pixels: new Uint8Array([index * 20, index * 20, index * 20, index * 20]),
}))""",
        "[0, 0.2, 0.4, 0.6, 0.8, 1]",
        "[1, 2, 3, 4, 5, 6]",
    )
    assert result["continuity_scan_status"] == "completed"
    assert (
        result["continuity_scan_strategy"]
        == "browser_presented_frames_v1"
    )
    assert result["continuity_scan_callback_count"] == 6
    assert result["continuity_scan_presented_frame_count"] == 6
    assert result["continuity_scan_missed_frame_count"] == 0
    assert result["continuity_scan_coverage_ratio"] == 1
    assert result["continuity_scan_max_gap_seconds"] == 0.2
    assert result["continuity_black_frame_ratio"] == 0
    assert result["continuity_raw_frames_persisted"] is False


def test_presented_frame_scan_detects_brief_black_and_duplicate_runs() -> None:
    result = _evaluate_continuity(
        """[
  { mean: 80, pixels: new Uint8Array([0, 0, 0, 0]) },
  { mean: 80, pixels: new Uint8Array([20, 20, 20, 20]) },
  { mean: 0, pixels: new Uint8Array([40, 40, 40, 40]) },
  { mean: 0, pixels: new Uint8Array([40, 40, 40, 40]) },
  { mean: 80, pixels: new Uint8Array([40, 40, 40, 40]) },
  { mean: 80, pixels: new Uint8Array([80, 80, 80, 80]) },
]""",
        "[0, 0.2, 0.4, 0.6, 0.8, 1]",
        "[10, 11, 12, 13, 14, 15]",
    )
    assert result["continuity_black_frame_ratio"] == pytest.approx(
        2 / 6,
        abs=0.0001,
    )
    assert result["continuity_longest_black_run_seconds"] == 0.4
    assert result["continuity_duplicate_transition_ratio"] == 0.4
    assert result["continuity_longest_duplicate_run_seconds"] == 0.4


def test_presented_frame_scan_rejects_missed_callbacks_and_sparse_coverage() -> None:
    samples = """Array.from({ length: 3 }, (_, index) => ({
  mean: 100,
  pixels: new Uint8Array([index, index, index, index]),
}))"""
    _evaluate_continuity(
        samples,
        "[0, 0.5, 1]",
        "[1, 3, 4]",
        expect_failure=True,
    )
    _evaluate_continuity(
        samples,
        "[0.4, 0.6, 0.8]",
        "[1, 2, 3]",
        expect_failure=True,
    )


def test_dense_seek_grid_is_exact_bounded_and_uses_canonical_duration() -> None:
    view = VIEW.read_text(encoding="utf-8")
    capture = view[
        view.index("async function captureVideoEvidence") :
        view.index("async function captureVideoTemporalEvidence")
    ]
    validation_at = capture.index("const sourceDuration = Number(video.duration)")
    canonical_at = capture.index("const duration = round(sourceDuration, 3)")
    continuity_at = capture.index("captureVideoContinuityMetrics(")
    payload_at = capture.index("duration_seconds: round(duration, 3)")
    assert validation_at < canonical_at < continuity_at < payload_at
    assert "captureVideoContinuityMetrics(\n      video,\n      duration," in capture

    module_url = VIEW.resolve().as_uri()
    result = _run_node_module(
        f"""
import {{ denseSeekContinuityTargets }} from {json.dumps(module_url)};
const exact = denseSeekContinuityTargets(8.08);
const roundedBelow = denseSeekContinuityTargets(
  Math.round(8.0001 * 1000) / 1000
);
const roundedAbove = denseSeekContinuityTargets(
  Math.round(8.0006 * 1000) / 1000
);
process.stdout.write(JSON.stringify({{
  count: exact.length,
  first: exact[0],
  last: exact.at(-1),
  monotonic: exact.every((value, index) =>
    index === 0 || value > exact[index - 1]
  ),
  maxGap: Math.max(
    exact[0],
    8.08 - exact.at(-1),
    ...exact.slice(1).map((value, index) => value - exact[index]),
  ),
  roundedBelowCount: roundedBelow.length,
  roundedAboveCount: roundedAbove.length,
}}));
"""
    )
    assert result["count"] == 82
    assert result["first"] == pytest.approx(0.01)
    assert result["last"] == pytest.approx(8.07)
    assert result["monotonic"] is True
    assert result["maxGap"] <= 0.125
    assert result["roundedBelowCount"] == 81
    assert result["roundedAboveCount"] == 82


def test_dense_seek_analyzer_is_honest_and_v1_reliability_is_classified() -> None:
    module_url = VIEW.resolve().as_uri()
    result = _run_node_module(
        f"""
import {{
  analyzeDenseSeekContinuitySamples,
  analyzeVideoContinuitySamples,
  continuityDenseSeekFallbackReason,
  denseSeekContinuityTargets,
}} from {json.dumps(module_url)};
const duration = 8.08;
const times = denseSeekContinuityTargets(duration);
const samples = times.map((_, index) => ({{
  mean: 80,
  pixels: new Uint8Array([index % 251, index % 251, index % 251, index % 251]),
}}));
const dense = analyzeDenseSeekContinuitySamples(
  samples,
  times,
  duration,
  "rvfc_missed_frames",
);
const smallSamples = Array.from({{ length: 4 }}, (_, index) => ({{
  mean: 80,
  pixels: new Uint8Array([index, index, index, index]),
}}));
function reason(times, frames) {{
  try {{
    analyzeVideoContinuitySamples(smallSamples, times, frames, 1);
    return "none";
  }} catch (error) {{
    return continuityDenseSeekFallbackReason(error);
  }}
}}
process.stdout.write(JSON.stringify({{
  dense,
  denseKeys: Object.keys(dense).sort(),
  invalidReason: (() => {{
    try {{
      analyzeDenseSeekContinuitySamples(
        samples, times, duration, "decode_error"
      );
      return false;
    }} catch {{ return true; }}
  }})(),
  invalidDrift: (() => {{
    try {{
      const drifted = [...times];
      drifted[10] += 0.021;
      analyzeDenseSeekContinuitySamples(
        samples, drifted, duration, "rvfc_unavailable"
      );
      return false;
    }} catch {{ return true; }}
  }})(),
  invalidCount: (() => {{
    try {{
      analyzeDenseSeekContinuitySamples(
        samples.slice(0, -1),
        times.slice(0, -1),
        duration,
        "rvfc_unavailable",
      );
      return false;
    }} catch {{ return true; }}
  }})(),
  missedReason: reason([0, 0.33, 0.66, 1], [1, 2, 4, 5]),
  coverageReason: reason([0.3, 0.4, 0.5, 0.6], [1, 2, 3, 4]),
  maxGapReason: reason([0, 0.1, 0.9, 1], [1, 2, 3, 4]),
  corruptReason: reason([0, 0.5, 0.4, 1], [1, 2, 3, 4]),
  arbitraryReason: continuityDenseSeekFallbackReason(new Error("decode")),
}}));
"""
    )
    dense = result["dense"]
    assert dense["continuity_scan_strategy"] == "browser_dense_seek_v2"
    assert dense["continuity_scan_sample_count"] == 82
    assert dense["continuity_scan_target_fps"] == 10
    assert dense["continuity_scan_fallback_reason"] == "rvfc_missed_frames"
    assert dense["continuity_scan_coverage_ratio"] >= 0.98
    assert dense["continuity_scan_max_gap_seconds"] <= 0.125
    assert "continuity_scan_callback_count" not in result["denseKeys"]
    assert "continuity_scan_presented_frame_count" not in result["denseKeys"]
    assert "continuity_scan_missed_frame_count" not in result["denseKeys"]
    assert dense["continuity_raw_frames_persisted"] is False
    assert result["invalidReason"] is True
    assert result["invalidDrift"] is True
    assert result["invalidCount"] is True
    assert result["missedReason"] == "rvfc_missed_frames"
    assert result["coverageReason"] == "rvfc_coverage_unreliable"
    assert result["maxGapReason"] == "rvfc_max_gap_unreliable"
    assert result["corruptReason"] == ""
    assert result["arbitraryReason"] == ""


def test_client_api_accepts_exact_v2_and_rejects_mixed_or_forged_v2() -> None:
    module_url = API.resolve().as_uri()
    result = _run_node_module(
        f"""
import {{ validContentReviewTechnicalMetrics }} from {json.dumps(module_url)};
const metrics = {{
  source_type: "video",
  frame_count: 5,
  duration_seconds: 8.08,
  sampled_at_seconds: [0.2, 1, 2, 5.76, 8.07],
  audio_expected: null,
  audio_analyzed: false,
  audio_analysis_status: "unavailable",
  speech_transcription_notice_version: "openai_mp4_v1",
  temporal_scan_status: "completed",
  temporal_scan_strategy: "uniform_full_duration_v1",
  temporal_scan_frame_count: 24,
  temporal_scan_first_second: 0.01,
  temporal_scan_last_second: 8.07,
  temporal_scan_coverage_ratio: 0.9975,
  temporal_black_frame_ratio: 0,
  temporal_frozen_transition_ratio: 0.02,
  temporal_mean_frame_difference: 0.08,
  timeline_atlas_status: "completed",
  timeline_atlas_version: "dense_full_duration_v1",
  timeline_atlas_frame_ordinal: 5,
  timeline_atlas_frame_count: 24,
  timeline_atlas_first_second: 0.01,
  timeline_atlas_last_second: 8.07,
  timeline_atlas_coverage_ratio: 0.9975,
  timeline_atlas_max_gap_seconds: 0.3504,
  timeline_atlas_sample_rate_fps: 2.9703,
  timeline_atlas_columns: 8,
  timeline_atlas_rows: 3,
  timeline_atlas_order: "row_major_chronological",
  timeline_atlas_dense_short_video: true,
  continuity_scan_status: "completed",
  continuity_scan_strategy: "browser_dense_seek_v2",
  continuity_scan_sample_count: 82,
  continuity_scan_target_fps: 10,
  continuity_scan_target_max_drift_seconds: 0,
  continuity_scan_fallback_reason: "rvfc_unavailable",
  continuity_scan_first_second: 0.01,
  continuity_scan_last_second: 8.07,
  continuity_scan_coverage_ratio: 0.9975,
  continuity_scan_max_gap_seconds: 0.0995,
  continuity_black_frame_ratio: 0,
  continuity_longest_black_run_seconds: 0,
  continuity_duplicate_transition_ratio: 0.02,
  continuity_longest_duplicate_run_seconds: 0.0995,
  continuity_mean_frame_difference: 0.08,
  continuity_raw_frames_persisted: false,
}};
process.stdout.write(JSON.stringify({{
  valid: validContentReviewTechnicalMetrics(metrics),
  mixed: validContentReviewTechnicalMetrics({{
    ...metrics,
    continuity_scan_missed_frame_count: 0,
  }}),
  forgedCount: validContentReviewTechnicalMetrics({{
    ...metrics,
    continuity_scan_sample_count: 81,
  }}),
  spacedStrategy: validContentReviewTechnicalMetrics({{
    ...metrics,
    continuity_scan_strategy: " browser_dense_seek_v2 ",
  }}),
  spacedReason: validContentReviewTechnicalMetrics({{
    ...metrics,
    continuity_scan_fallback_reason: " rvfc_unavailable ",
  }}),
  nullStatus: validContentReviewTechnicalMetrics({{
    ...metrics,
    continuity_scan_status: null,
  }}),
}}));
"""
    )
    assert result == {
        "valid": True,
        "mixed": False,
        "forgedCount": False,
        "spacedStrategy": False,
        "spacedReason": False,
        "nullStatus": False,
    }


def test_generated_video_dense_seek_ui_reports_timeline_points_truthfully() -> None:
    app = APP.read_text(encoding="utf-8")
    start = app.index("function generatedVideoTechnicalQaMarkup(details)")
    end = app.index("function generationActionsMarkup(details)", start)
    function_source = app[start:end]
    result = _run_node_module(
        f"""
const mediaId = "a1200000-0000-4000-8000-000000000001";
let prepared = null;
const entry = {{
  status: "capturing",
  captureStage: "continuity_dense_seek",
  completedFrames: 58,
  totalFrames: 82,
  error: "",
}};
const state = {{ generatedVideoQa: {{ entries: new Map([[mediaId, entry]]) }} }};
function contentReviewUuid() {{ return true; }}
function restoreGeneratedVideoQaEvidence() {{}}
function generatedVideoQaEvidenceForMedia() {{ return prepared; }}
function escapeHtml(value) {{ return String(value); }}
{function_source}
const progress = generatedVideoTechnicalQaMarkup({{
  photo: false,
  status: "succeeded",
  outputMediaId: mediaId,
  jobId: "job-1",
}});
entry.status = "ready";
entry.evidence = {{
  technicalMetrics: {{
    frame_count: 5,
    temporal_scan_frame_count: 24,
    timeline_atlas_status: "completed",
    continuity_scan_status: "completed",
    continuity_scan_strategy: "browser_dense_seek_v2",
    continuity_scan_sample_count: 82,
    audio_analysis_status: "unavailable",
  }},
}};
const ready = generatedVideoTechnicalQaMarkup({{
  photo: false,
  status: "succeeded",
  outputMediaId: mediaId,
  jobId: "job-1",
}});
process.stdout.write(JSON.stringify({{ progress, ready }}));
"""
    )
    assert "Плотно считываем точки таймлайна локально: 58 из 82" in result["progress"]
    assert "проигрываем короткий MP4 по кадрам" not in result["progress"]
    assert "82 равномерных точек таймлайна" in result["ready"]
    assert "82 показанных кадров" not in result["ready"]


def test_browser_capture_is_local_bounded_and_not_persisted_as_frames() -> None:
    view = VIEW.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    for marker in (
        "CONTINUITY_SCAN_MAX_DURATION_SECONDS = 15",
        "CONTINUITY_SCAN_MAX_FRAMES = 3_600",
        "requestVideoFrameCallback",
        "captureVideoContinuityMetrics",
        "analyzeVideoContinuitySamples",
        "analyzeDenseSeekContinuitySamples",
        'continuity_scan_strategy: "browser_dense_seek_v2"',
        'continuity_scan_strategy: "browser_presented_frames_v1"',
        "continuity_longest_black_run_seconds",
        "continuity_longest_duplicate_run_seconds",
        "continuity_raw_frames_persisted: false",
    ):
        assert marker in view
    assert "value.continuity_scan_status === \"completed\"" in api
    assert "value.continuity_raw_frames_persisted === false" in api
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 10" in app
    assert "GENERATED_VIDEO_QA_STORAGE_VERSION = 6" in app


def test_edge_uses_continuity_aggregates_for_deterministic_findings() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    for marker in (
        "TECH.CONTINUITY_SCAN_INCOMPLETE",
        "TECH.BLACK_FRAME_TRANSIENT",
        "TECH.FROZEN_SEGMENT",
        "continuity_scan_callback_count",
        "continuity_scan_sample_count",
        "browser_dense_seek_v2",
        "continuity_black_frame_ratio",
        "continuity_longest_black_run_seconds",
        "continuity_longest_duplicate_run_seconds",
        "continuity_raw_frames_persisted",
    ):
        assert marker in edge
    assert "Локальные временные наблюдения дают оценку" in edge
    deterministic = edge[
        edge.index("const continuityDenseSeekV2") :
        edge.index("if (audioExpected === true && !audioAnalyzed)")
    ]
    assert "Покадровый локальный контроль измерил" not in deterministic
    assert "соседние кадры идут непрерывно" not in deterministic


def test_database_continuity_metrics_are_bounded_and_non_bypassable() -> None:
    migration = (
        MIGRATION.read_text(encoding="utf-8")
        + EXTENSION_MIGRATION.read_text(encoding="utf-8")
        + FALLBACK_MIGRATION.read_text(encoding="utf-8")
    )
    pgtap = PGTAP.read_text(encoding="utf-8")
    for marker in (
        "valid_content_review_continuity_metrics",
        "content_review_evidence_continuity_metrics_valid",
        "browser_presented_frames_v1",
        "browser_dense_seek_v2",
        "between 2 and 3600",
        "between 0.8 and 1",
        "continuity_raw_frames_persisted",
        "creator_commit_content_review_evidence_without_continuity_gate_v4",
        "content_review_evidence_continuity_metrics_invalid",
        "is distinct from expected_status",
        "creator_commit_content_review_evidence_pre_project_v47",
        "browser sessions cannot bypass the continuity evidence gate",
    ):
        assert marker in migration + pgtap
    assert (
        "validate constraint content_review_evidence_continuity_metrics_valid"
        in migration
    )
    assert "continuity_raw_frame_payload" in pgtap
