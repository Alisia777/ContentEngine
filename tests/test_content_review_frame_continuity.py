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
PGTAP = ROOT / "supabase/tests/content_review_frame_continuity_test.sql"


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
        'continuity_scan_strategy: "browser_presented_frames_v1"',
        "continuity_longest_black_run_seconds",
        "continuity_longest_duplicate_run_seconds",
        "continuity_raw_frames_persisted: false",
    ):
        assert marker in view
    assert "value.continuity_scan_status === \"completed\"" in api
    assert "value.continuity_raw_frames_persisted === false" in api
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 8" in app
    assert "GENERATED_VIDEO_QA_STORAGE_VERSION = 6" in app


def test_edge_uses_continuity_aggregates_for_deterministic_findings() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    for marker in (
        "TECH.CONTINUITY_SCAN_INCOMPLETE",
        "TECH.BLACK_FRAME_TRANSIENT",
        "TECH.FROZEN_SEGMENT",
        "continuity_scan_callback_count",
        "continuity_black_frame_ratio",
        "continuity_longest_black_run_seconds",
        "continuity_longest_duplicate_run_seconds",
        "continuity_raw_frames_persisted",
    ):
        assert marker in edge


def test_database_continuity_metrics_are_bounded_and_non_bypassable() -> None:
    migration = (
        MIGRATION.read_text(encoding="utf-8")
        + EXTENSION_MIGRATION.read_text(encoding="utf-8")
    )
    pgtap = PGTAP.read_text(encoding="utf-8")
    for marker in (
        "valid_content_review_continuity_metrics",
        "content_review_evidence_continuity_metrics_valid",
        "browser_presented_frames_v1",
        "between 2 and 3600",
        "between 0.8 and 1",
        "continuity_raw_frames_persisted",
        "creator_commit_content_review_evidence_without_continuity_gate_v4",
        "content_review_evidence_continuity_metrics_invalid",
        "browser sessions cannot bypass the continuity evidence gate",
    ):
        assert marker in migration + pgtap
    assert (
        "validate constraint content_review_evidence_continuity_metrics_valid"
        in migration
    )
    assert "continuity_raw_frame_payload" in pgtap
