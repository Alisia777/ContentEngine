from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
MIGRATION = ROOT / "supabase" / "migrations" / (
    "202608050006_exact_youtube_source_intake.sql"
)
RESEARCH = APP / "workspace-research-video-intake.js"
AI_CENTER = APP / "workspace-ai-exact-youtube-sources.js"
BOOTSTRAP = APP / "workspace-research-training-bootstrap.js"
SUPABASE_API = APP / "supabase-api.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_exact_source_migration_parses_and_stays_provider_free() -> None:
    pglast = pytest.importorskip("pglast")
    sql = read(MIGRATION)
    statements = pglast.parse_sql(sql)
    assert statements, "exact YouTube source migration must contain valid SQL"
    for marker in (
        "content_factory.research_exact_youtube_sources",
        "contentengine_register_exact_youtube_source",
        "contentengine_exact_youtube_source_queue",
        "exact-youtube-source-intake-v1",
        "exact-youtube-source-queue-v1",
        "registered_in_research",
        "visible_in_ai_center",
        "url_is_video_evidence",
        "requires_lawful_mp4",
        "paid_analysis_allowed",
        "unattached_source_affects_learning",
        "unattached_source_affects_generation",
        "external_call_started",
        "paid_call_started",
    ):
        assert marker in sql
    for forbidden in (
        "net.http",
        "http_post(",
        "openai.com",
        "youtube.com/oembed",
        "yt-dlp",
        "creator_register_exact_youtube_source",
        "creator_exact_youtube_source_queue",
    ):
        assert forbidden not in sql
    assert "status = 'awaiting_media'" in sql
    assert "right(canonical_url, 11) = video_id" in sql
    assert "grant execute" in sql
    assert "to authenticated, service_role" in sql


def test_research_submit_registers_source_before_any_paid_analysis() -> None:
    source = read(RESEARCH)
    submit_handler = source.split(
        'form.addEventListener("submit", (event) => {', 1
    )[1].split("}, { capture: true });", 1)[0]
    for marker in (
        "contentengine_register_exact_youtube_source",
        "registerExactSource",
        "registered_in_research",
        "visible_in_ai_center",
        "paid_analysis_allowed !== false",
        "external_call_started !== false",
        "paid_call_started !== false",
        "Шаг 1 выполнен",
        "Платного вызова не было",
    ):
        assert marker in source
    assert "blockUrlOnlySubmit(" in submit_handler
    assert "mergeResearchVideoReference(" not in submit_handler


def test_ai_center_surfaces_url_only_source_without_calling_it_learning() -> None:
    source = read(AI_CENTER)
    for marker in (
        "exactYoutubeSourceQueue",
        "Видео до обучения",
        "Ждёт MP4",
        "Кадры, монтаж и речь ещё не анализировались",
        "не считается просмотренным видео",
        "unattached_source_affects_learning !== false",
        "unattached_source_affects_generation !== false",
        "Загрузить MP4 и продолжить",
    ):
        assert marker in source
    assert (
        'exactYoutubeSourceQueue: "contentengine_exact_youtube_source_queue"'
        in read(SUPABASE_API)
    )
    assert "workspace-ai-exact-youtube-sources.css" in read(BOOTSTRAP)
    assert "workspace-ai-exact-youtube-sources.js" in read(BOOTSTRAP)


def test_exact_source_browser_modules_are_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    for path in (RESEARCH, AI_CENTER, BOOTSTRAP):
        subprocess.run([node, "--check", str(path)], check=True)
