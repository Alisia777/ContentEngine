"""«Забрать видео» (контур №1 ТЗ, v1): одна точка входа для исходников.

Ссылка и физический MP4 — разные объекты: регистрация ссылки создаёт источник
проекта существующим контуром research_exact_youtube_sources, файл — отдельный
шаг с человеческим подтверждением совпадения. Другие платформы честно
отклоняются до их отдельного включения (никаких обходов ограничений).
Нормализация URL проверяется настоящим node-прогоном функции из app.js.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
PORTAL = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "interface-system.css").read_text(encoding="utf-8")


def test_video_intake_card_offers_three_ways_in_media_section() -> None:
    assert "videoIntakeCardMarkup()" in PORTAL
    assert "data-video-intake" in PORTAL
    assert "1. Ссылка на ролик" in PORTAL
    assert "2. Файл MP4" in PORTAL
    assert "3. Уже в проекте" in PORTAL
    # Регистрация идёт в СУЩЕСТВУЮЩИЙ контур источников — не во второй.
    assert 'state.api.call("contentengine_register_exact_youtube_source"' in PORTAL
    assert "media-intake-" in PORTAL  # идемпотентный ключ
    # Следующий шаг называется прямо и ведёт в существующие «Источники».
    assert "&tab=sources" in PORTAL
    assert "video-intake-register" in PORTAL
    assert "video-intake-upload" in PORTAL
    # Файл-способ предвыбирает роль исходного видео в действующей форме.
    upload = PORTAL.split("function focusVideoIntakeUpload", 1)[1].split("\n}", 1)[0]
    assert 'kind.value = "source_video"' in upload
    assert ".video-intake-grid" in CSS


def test_copy_origin_link_stamps_file_provenance() -> None:
    """Intake v2 (решение владельца 26.08): ссылка на оригинал прямо в форме
    «Копии». Ссылка регистрируется единым реестром источников; выбранный файл
    получает несмываемый след происхождения (creator_stamp_media_origin_url —
    живая проба в проде: штамп, идемпотентность, отказ на другой URL). Файл
    система не скачивает — его прикладывает человек с галкой подтверждения."""
    intake = (ROOT / "web" / "app" / "generation-strategy-intake-v4.js").read_text(
        encoding="utf-8"
    )
    assert "copyOriginLinkBlock()" in intake
    assert "Оригинал по ссылке (необязательно)" in intake
    assert "normalizeCopyOriginUrl" in intake
    assert 'contentengine_register_exact_youtube_source' in intake
    assert "creator_stamp_media_origin_url" in intake
    # Галка подтверждения обязательна для следа; без неё — только регистрация.
    assert "Поставьте галку подтверждения" in intake
    # Штамп в обеих ветках исходника: существующий media и свежая загрузка.
    assert intake.count("stampCopyOriginOnMedia(") >= 3  # def + 2 вызова
    # Штамп — ценность, но не условие: его ошибка не валит запуск.
    assert "Запуску это не мешает" in intake
    migration = (
        ROOT / "supabase/migrations/202608270002_media_origin_stamp_v1.sql"
    ).read_text(encoding="utf-8")
    assert "media_origin_already_stamped" in migration
    assert "origin_url_canonical" in migration
    assert "media_origin_kind_invalid" in migration
    # Паспорт показывает происхождение у материала-исходника.
    assert "'origin_url'" in migration.replace("''", "'")
    assert "оригинал: " in PORTAL


def test_video_intake_url_normalization_behaves() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for the URL normalization run")
    start = PORTAL.index("const VIDEO_INTAKE_YOUTUBE_ID")
    end = PORTAL.index("function videoIntakeCardMarkup")
    subject = PORTAL[start:end]
    harness = subject + """
const cases = {
  watch: normalizeVideoIntakeUrl("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"),
  short: normalizeVideoIntakeUrl("https://youtu.be/dQw4w9WgXcQ?si=abc"),
  shorts: normalizeVideoIntakeUrl("https://youtube.com/shorts/dQw4w9WgXcQ"),
  mobile: normalizeVideoIntakeUrl("https://m.youtube.com/watch?v=dQw4w9WgXcQ"),
  tiktok: normalizeVideoIntakeUrl("https://www.tiktok.com/@user/video/123"),
  http: normalizeVideoIntakeUrl("http://youtube.com/watch?v=dQw4w9WgXcQ"),
  garbage: normalizeVideoIntakeUrl("не ссылка"),
  badId: normalizeVideoIntakeUrl("https://youtu.be/tooShort"),
};
process.stdout.write(JSON.stringify(cases));
"""
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp) / "run.mjs"
        run.write_text(harness, encoding="utf-8")
        completed = subprocess.run(
            [node, str(run)], capture_output=True, text=True,
            encoding="utf-8", timeout=15, check=False,
        )
    assert completed.returncode == 0, completed.stderr
    verdict = json.loads(completed.stdout)
    canonical = "https://youtube.com/watch?v=dQw4w9WgXcQ"
    for key in ("watch", "short", "shorts", "mobile"):
        assert verdict[key]["canonical"] == canonical, key
        assert verdict[key]["videoId"] == "dQw4w9WgXcQ"
    assert "YouTube" in verdict["tiktok"]["error"]
    assert "https" in verdict["http"]["error"]
    assert verdict["garbage"]["error"]
    assert "11" in verdict["badId"]["error"]
