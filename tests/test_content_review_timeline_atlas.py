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
INDEX = ROOT / "web/app/index.html"
EDGE = ROOT / "supabase/functions/creator-content-review/index.ts"
MIGRATION = (
    ROOT
    / "supabase/migrations/202607260008_content_review_timeline_atlas.sql"
)
TRAINING = (
    ROOT
    / "supabase/migrations/202607260009_content_review_timeline_atlas_training.sql"
)
PGTAP = ROOT / "supabase/tests/content_review_timeline_atlas_test.sql"


def _evaluate_atlas(
    times: str,
    duration: float,
    columns: int,
    rows: int,
    *,
    expect_failure: bool = False,
) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for timeline atlas contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(
            VIEW.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (directory / "contract.mjs").write_text(
            f"""
import {{ analyzeTimelineAtlas }} from "./subject.mjs";
const result = analyzeTimelineAtlas(
  {times},
  {duration},
  {columns},
  {rows},
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


def test_short_video_atlas_is_dense_ordered_and_full_duration() -> None:
    result = _evaluate_atlas(
        "Array.from({ length: 24 }, (_, index) => 0.02 + 7.96 * index / 23)",
        8,
        8,
        3,
    )
    assert result == {
        "timeline_atlas_status": "completed",
        "timeline_atlas_version": "dense_full_duration_v1",
        "timeline_atlas_frame_ordinal": 5,
        "timeline_atlas_frame_count": 24,
        "timeline_atlas_first_second": 0.02,
        "timeline_atlas_last_second": 7.98,
        "timeline_atlas_coverage_ratio": 0.995,
        "timeline_atlas_max_gap_seconds": 0.3461,
        "timeline_atlas_sample_rate_fps": 3,
        "timeline_atlas_columns": 8,
        "timeline_atlas_rows": 3,
        "timeline_atlas_order": "row_major_chronological",
        "timeline_atlas_dense_short_video": True,
    }


def test_long_video_atlas_is_honestly_bounded_not_dense() -> None:
    result = _evaluate_atlas(
        "Array.from({ length: 24 }, (_, index) => 0.02 + 29.96 * index / 23)",
        30,
        6,
        4,
    )
    assert result["timeline_atlas_frame_count"] == 24
    assert result["timeline_atlas_coverage_ratio"] > 0.99
    assert result["timeline_atlas_max_gap_seconds"] > 1.3
    assert result["timeline_atlas_dense_short_video"] is False


def test_atlas_rejects_sparse_manifest_or_nonminimal_grid() -> None:
    _evaluate_atlas("[0.02, 1, 2, 3, 4.98]", 5, 5, 1, expect_failure=True)
    _evaluate_atlas(
        "Array.from({ length: 12 }, (_, index) => 0.02 + 4.96 * index / 11)",
        5,
        6,
        3,
        expect_failure=True,
    )


def test_browser_retains_four_frames_and_one_bounded_atlas() -> None:
    view = VIEW.read_text(encoding="utf-8")
    for marker in (
        "TIMELINE_ATLAS_MAX_DIMENSION = 1_280",
        "TIMELINE_ATLAS_DENSE_MAX_GAP_SECONDS = 0.5",
        "captureVideoTemporalEvidence",
        "timelineAtlasLayout",
        "atlasContext.drawImage",
        "encodeCanvasBounded(atlasCanvas)",
        "frames.push(temporalEvidence.atlas)",
        "frames.length !== 5",
        'sampling_strategy: "four_control_frames_plus_timeline_atlas_v1"',
        'timeline_atlas_version: "dense_full_duration_v1"',
        'timeline_atlas_frame_ordinal: 5',
        'timeline_atlas_order: "row_major_chronological"',
    ):
        assert marker in view
    sample_times = view[
        view.index("function sampleTimes") :
        view.index("async function seekVideo")
    ]
    assert "0.82" in sample_times
    assert "duration * 0.9" not in sample_times


def test_browser_and_database_fail_closed_on_atlas_contract() -> None:
    api = API.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    pgtap = PGTAP.read_text(encoding="utf-8")
    for marker in (
        "timelineAtlasValid",
        'value.timeline_atlas_status === "completed"',
        'value.timeline_atlas_version === "dense_full_duration_v1"',
        "Number(value.frame_count) !== 5",
        "sampledAt.length === 5",
    ):
        assert marker in api
    for marker in (
        "valid_content_review_timeline_atlas_metrics",
        "content_review_evidence_timeline_atlas_metrics_valid",
        "creator_commit_content_review_evidence_without_atlas_gate_v3",
        "content_review_evidence_timeline_atlas_metrics_invalid",
        "browser sessions cannot bypass the timeline atlas evidence gate",
        "timeline_atlas_payload",
    ):
        assert marker in migration + pgtap
    assert (
        "validate constraint\n"
        "    content_review_evidence_timeline_atlas_metrics_valid"
    ) in migration


def test_edge_reads_fifth_image_as_atlas_and_caps_missing_evidence() -> None:
    edge = EDGE.read_text(encoding="utf-8")
    for marker in (
        "пятое изображение —",
        "слева направо и сверху",
        "timelineAtlasCompleted",
        "denseShortVideoAtlas",
        "TECH.TIMELINE_ATLAS_INCOMPLETE",
        "TECH.TIMELINE_ATLAS_SPARSE",
        '"TECH.TIMELINE_ATLAS_INCOMPLETE"',
        '"TECH.TIMELINE_ATLAS_SPARSE"',
    ):
        assert marker in edge


def test_training_preserves_full_human_playback_after_atlas() -> None:
    training = TRAINING.read_text(encoding="utf-8")
    for marker in (
        "четыре отдельных контрольных кадра",
        "хронологический атлас из 12–24",
        "слева направо и сверху вниз",
        "не является декодированием каждого",
        "Полностью воспроизвести",
        "content review timeline atlas training contract failed",
        "content review timeline atlas assessment contract failed",
    ):
        assert marker in training


def test_atlas_release_invalidates_old_local_evidence_and_bumps_modules() -> None:
    app = APP.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    assert "./content-review-view.js?v=20260727.11" in app
    assert "./supabase-api.js?v=20260728.4" in app
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 7" in app
    assert "GENERATED_VIDEO_QA_STORAGE_VERSION = 5" in app
    assert "./app.js?v=20260728.8" in index
