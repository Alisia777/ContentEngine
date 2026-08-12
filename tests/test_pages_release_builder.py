import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_pages_release import _safe_output, build_release  # noqa: E402


PROJECT_REF = "iyckwryrucqrxwlowxow"
PUBLISHABLE_KEY = "sb_publishable_release_acceptance_1234567890"


def _build(tmp_path: Path, *, edge_function: Path | None = None):
    output = tmp_path / "_site"
    manifest = build_release(
        source_dir=ROOT / "web/app",
        output_dir=output,
        edge_function=edge_function
        or ROOT / "supabase/functions/creator-generate/index.ts",
        project_ref=PROJECT_REF,
        expected_project_ref=PROJECT_REF,
        publishable_key=PUBLISHABLE_KEY,
    )
    return output, manifest


def test_pages_release_is_complete_version_bound_and_deterministic(
    tmp_path: Path,
) -> None:
    output, manifest = _build(tmp_path)

    assert manifest["app_script"] == "./app.js?v=20260812.os4.33"
    assert manifest["learning_gate_version"] == "2026-07-29.v8"
    assert manifest["artifact_file_count"] == len(manifest["sha256"])
    assert "app.js" in manifest["sha256"]
    assert "content-generation-handoff.js" in manifest["sha256"]
    assert "generation-form-readiness.js" in manifest["sha256"]
    assert "generation-form-draft.js" in manifest["sha256"]
    assert "generation-video-reference.js" in manifest["sha256"]
    assert "generation-model-acceptance-view.js" in manifest["sha256"]
    assert "generation-provider-readiness.js" in manifest["sha256"]
    assert "generation-quality-training.js" in manifest["sha256"]
    for workspace_asset in (
        "workspace-action-key.js",
        "workspace-os-v4-loader.js",
        "workspace-os-v4.js",
        "workspace-os-v4-flow.css",
        "workspace-os-v4-finder.js",
        "workspace-os-v4-finder.css",
        "workspace-os-v4-context-trash.js",
        "workspace-os-v4-context-trash.css",
        "workspace-board-view.js",
        "workspace-board.css",
        "content-review-view.js",
        "content-review.css",
    ):
        assert workspace_asset in manifest["sha256"]
    assert "config.example.js" not in manifest["sha256"]
    assert (output / ".nojekyll").is_file()

    written = json.loads(
        (output / "release-manifest.json").read_text(encoding="utf-8")
    )
    assert written == manifest
    config = (output / "config.js").read_text(encoding="utf-8")
    assert f"https://{PROJECT_REF}.supabase.co" in config
    assert PUBLISHABLE_KEY in config
    assert "RUNWAYML_API_SECRET" not in config
    assert "127.0.0.1" not in config


def test_pages_release_rejects_client_edge_gate_mismatch(tmp_path: Path) -> None:
    edge = tmp_path / "creator-generate.ts"
    source = (
        ROOT / "supabase/functions/creator-generate/index.ts"
    ).read_text(encoding="utf-8")
    edge.write_text(
        source.replace("2026-07-29.v8", "2026-07-25.v9", 1),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="client and creator-generate learning gate versions differ",
    ):
        _build(tmp_path / "build", edge_function=edge)


def test_pages_release_never_deletes_source_or_its_ancestors(
    tmp_path: Path,
) -> None:
    source = tmp_path / "workspace/web/app"
    source.mkdir(parents=True)

    for dangerous_output in (
        source,
        source.parent,
        source.parents[1],
        source / "_site",
        Path("/"),
    ):
        with pytest.raises(ValueError, match="output directory"):
            _safe_output(source, dangerous_output)
