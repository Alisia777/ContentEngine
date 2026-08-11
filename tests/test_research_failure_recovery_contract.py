from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
RECOVERY = APP / "workspace-research-failure-recovery.js"
BOOTSTRAP = APP / "workspace-research-training-bootstrap.js"
INDEX = APP / "index.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_failed_research_can_be_closed_and_replaced_with_a_fresh_form() -> None:
    source = read(RECOVERY)
    assert (
        'from "./product-research-view.js?v=20260811.os4.29"'
        in source
    )
    for marker in (
        "data-research-youtube-failure-guard",
        "Закрыть ошибочный запуск",
        "Начать заново без ролика",
        "recovery: \"1\"",
        "productResearchInputMarkup",
        "Ошибочный результат больше не блокирует работу",
        "Предыдущий terminal-failure закрыт",
        "clearPendingSource",
        "Повторного платного запуска нет",
        'guard.dataset.failureMode === "exact-video-provider-terminal"',
        "must never rewrite recovery into another upload or generic paid form",
    ):
        assert marker in source
    assert "savedStatus.focus" not in source


def test_mp4_handoff_opens_the_real_media_upload_form() -> None:
    source = read(RECOVERY)
    for marker in (
        'const MEDIA_ROUTE = "/workspace/media"',
        'document.getElementById("media-upload-form")',
        'form.querySelector(\'input[type="file"]\')',
        'input.accept = "video/mp4,.mp4"',
        "input.multiple = false",
        "Выбрать MP4",
        "Загрузить MP4 и продолжить",
        "Сначала выберите один MP4",
        "workspace/board",
        "youtube_source",
    ):
        assert marker in source
    assert "#/workspace/board?" not in source


def test_recovery_module_is_loaded_on_every_handoff_route() -> None:
    bootstrap = read(BOOTSTRAP)
    index = read(INDEX)
    for marker in (
        'route === "/workspace/research"',
        'route === "/workspace/media"',
        'route === "/workspace/review"',
        'route === "/workspace/ai"',
        "workspace-research-failure-recovery.css",
        "workspace-research-failure-recovery.js",
        'const BUILD = "20260810.research.30"',
    ):
        assert marker in bootstrap
    assert (
        "workspace-research-training-bootstrap.js?"
        "v=20260811.exact-source-lifecycle.1"
        in index
    )


def test_recovery_hashes_point_to_real_routes() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = """
      const mod = await import('./web/app/workspace-research-failure-recovery.js');
      const projectId = '11111111-1111-4111-8111-111111111111';
      const sourceId = '22222222-2222-4222-8222-222222222222';
      const upload = mod.mediaHandoffHash({
        projectId,
        sourceId,
        canonicalUrl: 'https://youtube.com/watch?v=CXssfXBVInw'
      });
      const fresh = mod.freshResearchHash(projectId);
      process.stdout.write(JSON.stringify({ upload, fresh }));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    value = json.loads(result.stdout)
    assert value["upload"].startswith("#/workspace/media?")
    assert "youtube_source=22222222-2222-4222-8222-222222222222" in value["upload"]
    assert value["fresh"] == (
        "#/workspace/research?project_id="
        "11111111-1111-4111-8111-111111111111&recovery=1"
    )


def test_new_browser_modules_are_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    for path in (RECOVERY, BOOTSTRAP):
        subprocess.run([node, "--check", str(path)], check=True)
