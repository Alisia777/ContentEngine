from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
VIEW = (ROOT / "web/app/product-research-view.js").read_text(encoding="utf-8")
MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202608100002_workspace_media_classification_and_folders.sql"
)
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")


def _run_view_module(body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable UI contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(VIEW, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
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


def test_research_picker_keeps_only_ready_source_photos_and_deduplicates_sha() -> None:
    result = _run_view_module(
        """
        const sha = "a".repeat(64);
        const media = [
          {
            id: "source-new", title: "Повтор", kind: "product_photo",
            status: "ready", mime_type: "image/jpeg", artifact_class: "source",
            sha256: sha, created_at: "2026-08-10T12:00:00Z",
          },
          {
            id: "source-canonical", title: "Оригинал", kind: "product_photo",
            status: "ready", mime_type: "image/jpeg", artifact_class: "source",
            sha256: sha, created_at: "2026-08-09T12:00:00Z",
          },
          {
            id: "packshot", title: "Этикетка", kind: "packshot",
            status: "ready", mime_type: "image/webp", artifact_class: "source",
            content_hash: "b".repeat(64), created_at: "2026-08-08T12:00:00Z",
          },
          {
            id: "generated-image", kind: "generated_image", status: "ready",
            mime_type: "image/png", artifact_class: "generated_output",
            sha256: "c".repeat(64),
          },
          {
            id: "generated-disguised", kind: "product_photo", status: "ready",
            mime_type: "image/png", artifact_class: "generated_output",
            sha256: "d".repeat(64),
          },
          {
            id: "not-ready", kind: "product_photo", status: "uploading",
            mime_type: "image/png", artifact_class: "source",
            sha256: "e".repeat(64),
          },
          {
            id: "source-video", kind: "source_video", status: "ready",
            mime_type: "video/mp4", artifact_class: "source",
            sha256: "f".repeat(64),
          },
        ];
        const normalized = subject.normalizeProductResearchMediaSources(media);
        const repeated = subject.normalizeProductResearchMediaSources(
          Array.from({ length: 24 }, (_, index) => ({
            id: `live-duplicate-${String(index).padStart(2, "0")}`,
            kind: "product_photo",
            status: "ready",
            mime_type: "image/webp",
            artifact_class: "source",
            sha256: "9".repeat(64),
            created_at: `2026-08-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
          })),
        );
        const html = subject.productResearchInputMarkup({
          media,
          defaults: { sourceMediaIds: ["source-new"] },
        });
        return {
          ids: normalized.map((item) => item.id),
          duplicateCount: normalized.find((item) => item.id === "source-canonical")?.duplicate_count,
          duplicateIds: normalized.find((item) => item.id === "source-canonical")?.duplicate_media_ids,
          canonicalSelected: html.includes('value="source-canonical" checked'),
          duplicateHidden: !html.includes('value="source-new"'),
          generatedHidden: !html.includes('value="generated-image"')
            && !html.includes('value="generated-disguised"'),
          duplicateLabel: html.includes("2 одинаковых файлов объединены"),
          liveDuplicateCards: repeated.length,
          liveDuplicateCount: repeated[0]?.duplicate_count,
        };
        """
    )

    assert result["ids"] == ["packshot", "source-canonical"]
    assert result["duplicateCount"] == 2
    assert set(result["duplicateIds"]) == {"source-new", "source-canonical"}
    assert result["canonicalSelected"] is True
    assert result["duplicateHidden"] is True
    assert result["generatedHidden"] is True
    assert result["duplicateLabel"] is True
    assert result["liveDuplicateCards"] == 1
    assert result["liveDuplicateCount"] == 24


def test_research_app_preparation_is_fail_closed_for_generic_images() -> None:
    start = APP.index("function renderProductResearchSection()")
    end = APP.index("function stopProductResearchPolling", start)
    section = APP[start:end]

    assert 'status === "ready"' in section
    assert '["product_photo", "packshot"].includes(kind)' in section
    assert '["image/jpeg", "image/png", "image/webp"].includes(mimeType)' in section
    assert 'artifactClass === "source"' in section
    assert 'startsWith("image/")' not in section


def test_media_classification_migration_parses_and_keeps_contract_narrow() -> None:
    assert MIGRATION_PATH.is_file()
    parse_sql(MIGRATION)
    lowered = MIGRATION.lower()

    assert "add column if not exists artifact_class" in lowered
    assert "add column if not exists lifecycle_stage" in lowered
    assert "'source', 'generated_output', 'unclassified'" in lowered
    assert "'sources', 'drafts', 'review', 'ready', 'published'" in lowered
    assert "sync_workspace_media_system_location" in lowered
    assert "and not p_workflow_transition" in lowered
    assert "and location.folder_id is null" in lowered
    assert "workspace_folder_scope_matches" in lowered
    assert "'generated_image', 'generated_video'" in lowered
    assert "creator_workspace_browser_pre_media_scope_v418" in lowered
    assert "create or replace function public.creator_workspace_browser" in lowered
    assert (
        ".creator_workspace_browser_pre_media_scope_v418(p_payload)" in lowered
    )
    assert "not root_scope_requested and not generated_image_filter_requested" in lowered
    assert "jsonb_array_length(items_value) > page_size_value" in lowered
    assert "'{_meta,next_cursor}'" in lowered
    assert "workspace_project_memberships" not in lowered
    assert "storage.objects" not in lowered
