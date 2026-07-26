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
    / "supabase/migrations/202607260004_content_review_temporal_scan_metrics.sql"
)
TRAINING_MIGRATION = (
    ROOT
    / "supabase/migrations/202607260005_content_review_temporal_scan_training.sql"
)
PGTAP = ROOT / "supabase/tests/content_review_temporal_scan_test.sql"


def _evaluate_temporal(
    samples: str,
    times: str,
    duration: float = 5,
    *,
    expect_failure: bool = False,
) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for temporal scan contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            VIEW.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            f"""
import {{ analyzeTemporalVideoSamples }} from "./subject.mjs";
const samples = {samples};
const times = {times};
const result = analyzeTemporalVideoSamples(samples, times, {duration});
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


def test_dense_temporal_scan_measures_full_duration_motion() -> None:
    result = _evaluate_temporal(
        """Array.from({ length: 12 }, (_, index) => ({
  mean: 80 + index,
  pixels: new Uint8Array([index * 10, index * 10, index * 10, index * 10]),
}))""",
        "Array.from({ length: 12 }, (_, index) => 0.02 + 4.96 * index / 11)",
    )
    assert result["temporal_scan_status"] == "completed"
    assert result["temporal_scan_strategy"] == "uniform_full_duration_v1"
    assert result["temporal_scan_frame_count"] == 12
    assert result["temporal_scan_first_second"] == 0.02
    assert result["temporal_scan_last_second"] == 4.98
    assert result["temporal_scan_coverage_ratio"] == 0.992
    assert result["temporal_black_frame_ratio"] == 0
    assert result["temporal_frozen_transition_ratio"] == 0
    assert 0.039 < result["temporal_mean_frame_difference"] < 0.04


def test_dense_temporal_scan_detects_brief_black_and_frozen_sections() -> None:
    result = _evaluate_temporal(
        """Array.from({ length: 12 }, (_, index) => ({
  mean: index === 6 ? 0 : 100,
  pixels: new Uint8Array(index === 6 ? [0, 0, 0, 0] : [100, 100, 100, 100]),
}))""",
        "Array.from({ length: 12 }, (_, index) => 0.02 + 4.96 * index / 11)",
    )
    assert result["temporal_black_frame_ratio"] == 0.0833
    assert result["temporal_frozen_transition_ratio"] == 0.8182
    assert result["temporal_mean_frame_difference"] > 0.07


def test_temporal_scan_rejects_sparse_or_narrow_coverage() -> None:
    samples = """Array.from({ length: 12 }, () => ({
  mean: 100,
  pixels: new Uint8Array([100, 100, 100, 100]),
}))"""
    _evaluate_temporal(
        "Array.from({ length: 5 }, () => ({ mean: 100, pixels: new Uint8Array([100]) }))",
        "[0.02, 1, 2, 3, 4.98]",
        expect_failure=True,
    )
    _evaluate_temporal(
        samples,
        "Array.from({ length: 12 }, (_, index) => 2 + index / 11)",
        expect_failure=True,
    )


def test_temporal_scan_is_bounded_local_and_not_added_to_external_frames() -> None:
    view = VIEW.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    for marker in (
        "MIN_TEMPORAL_SCAN_FRAMES = 12",
        "MAX_TEMPORAL_SCAN_FRAMES = 24",
        "TEMPORAL_SCAN_FRAMES_PER_SECOND = 4",
        "TEMPORAL_SCAN_TIMEOUT_MS = 30_000",
        "captureVideoTemporalMetrics",
        "analyzeTemporalVideoSamples",
        'temporal_scan_status: "completed"',
        'temporal_scan_strategy: "uniform_full_duration_v1"',
        "temporal_black_frame_ratio",
        "temporal_frozen_transition_ratio",
        "temporal_mean_frame_difference",
    ):
        assert marker in view
    temporal_capture = view[
        view.index("async function captureVideoTemporalMetrics") :
        view.index("async function captureVideoAudioMetrics")
    ]
    assert "encodeCanvasBounded" not in temporal_capture
    assert "frames.push" not in temporal_capture
    assert 'value.temporal_scan_status === "completed"' in api
    assert "value.temporal_scan_frame_count >= 12" in api
    assert "value.temporal_scan_frame_count <= 24" in api
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 4" in app
    assert "GENERATED_VIDEO_QA_STORAGE_VERSION = 3" in app


def test_edge_uses_temporal_scan_for_findings_and_quality_score_caps() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    for marker in (
        "TECH.TEMPORAL_SCAN_INCOMPLETE",
        "TECH.BLACK_FRAME_TRANSIENT",
        "TECH.BLACK_FRAMES",
        "TECH.FROZEN_VIDEO",
        "temporal_scan_coverage_ratio",
        "temporal_black_frame_ratio",
        "temporal_frozen_transition_ratio",
        "measuredTechnicalFindingCodes",
        "technicalScoreCap",
        "overallScoreCap",
    ):
        assert marker in edge
    measured_codes = edge[
        edge.index("const measuredTechnicalFindingCodes") :
        edge.index("const measuredTechnicalFindings")
    ]
    assert '"TECH.BLACK_FRAME_TRANSIENT"' in measured_codes
    assert '"TECH.FROZEN_VIDEO"' in measured_codes
    assert '"TECH.TEMPORAL_SCAN_INCOMPLETE"' not in measured_codes


def test_database_temporal_metrics_are_immutable_bounded_and_non_bypassable() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    pgtap = PGTAP.read_text(encoding="utf-8")
    for marker in (
        "valid_content_review_temporal_metrics",
        "content_review_evidence_temporal_metrics_valid",
        "uniform_full_duration_v1",
        "between 12 and 24",
        "between 0.9 and 1",
        "creator_commit_content_review_evidence_without_temporal_gate_v2",
        "content_review_evidence_temporal_metrics_invalid",
        "browser sessions cannot bypass the temporal evidence gate",
    ):
        assert marker in migration + pgtap
    assert "validate constraint content_review_evidence_temporal_metrics_valid" in migration
    assert "temporal_frame_payload" in pgtap


def test_training_preserves_full_human_playback_after_dense_scan() -> None:
    migration = TRAINING_MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "от 12 до 24 равномерных точек",
        "не является покадровым декодированием",
        "course_check_video_quality_full_qa",
        "24 равномерные точки таймлайна",
        "full_playback",
        "Полностью воспроизвести",
        "content review temporal scan training contract failed",
        "content review temporal assessment contract failed",
    ):
        assert marker in migration
