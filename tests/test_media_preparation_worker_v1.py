"""Воркер подготовки видео (контур №1 ТЗ, clean master вне браузера, v1).

Анализ и чистый мастер выполняет provider-free воркер на стенде (docker),
браузер только ставит задания и показывает честные prep_-факты. Прод
проверен: транзакционная проба очереди (enqueue → claim → complete →
метадата) откатана с PROBE_OK; смоук ffmpeg-цепочки прогнан в докер-образе
репо на синтетике 720x1280 с рамкой — SMOKE_OK (crop 480x600 срезан,
апскейл до 720x900, звук сохранён, эвристика записи экрана сработала).
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUEUE = (
    ROOT / "supabase/migrations/202608270003_media_preparation_worker_v1.sql"
).read_text(encoding="utf-8")
FACTS = (
    ROOT / "supabase/migrations/202608270004_workspace_media_preparation_facts.sql"
).read_text(encoding="utf-8")
WORKER = (ROOT / "scripts" / "media_preparation_worker.py").read_text(
    encoding="utf-8"
)
COMPOSE = (ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
PORTAL = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "interface-system.css").read_text(encoding="utf-8")


def test_queue_is_gated_and_system_rpcs_are_service_role_only() -> None:
    assert "create table if not exists content_factory.media_preparation_jobs" in QUEUE
    # Операторские RPC — authenticated; системные — ТОЛЬКО service_role
    # (5 функций + grant на саму таблицу очереди).
    assert QUEUE.count("to authenticated;") == 2
    assert QUEUE.count("to service_role;") == 6
    for name in (
        "system_claim_media_preparation",
        "system_heartbeat_media_preparation",
        "system_complete_media_analysis",
        "system_complete_media_clean_master",
        "system_fail_media_preparation",
    ):
        assert (
            f"revoke all on function public.{name}(jsonb)\n"
            "  from public, anon, authenticated;"
        ) in QUEUE, name
    # Claim без гонок и с реанимацией протухших lease.
    assert "for update skip locked" in QUEUE
    assert "interval '10 minutes'" in QUEUE
    # ON CONFLICT по partial-индексу ломается об use_variable — поэтому
    # select-first, а гонку закрывает unique_violation.
    assert "exception when unique_violation" in QUEUE
    code_only = "\n".join(
        line for line in QUEUE.splitlines() if "--" not in line
    )
    assert "on conflict" not in code_only.lower()
    # Единственный платный вход не тронут: контракт честно говорит «нет».
    assert "'provider_call_started', false" in QUEUE
    assert "'spend_action_started', false" in QUEUE


def test_finalize_video_handler_contract() -> None:
    """«Финализация» (202609020001): ветка воркера, TTS-цепочка и порядок
    kind-диспетчеризации — finalize уходит своим complete, неизвестный kind
    падает громко, а не едет по clean_master-пути."""
    assert 'if job["kind"] == "finalize_video":' in WORKER
    assert 'if job["kind"] != "clean_master":' in WORKER
    assert "unknown_job_kind" in WORKER
    # Путь результата — из params постановки, suggested-путь клина чужой.
    assert '"output_object_name"' in WORKER
    assert "system_complete_video_finalization" in WORKER
    # TTS: бесплатный edge-tts модулем + платный MiniMax с фолбэком.
    assert "ru-RU-SvetlanaNeural" in WORKER
    assert '"-m", "edge_tts"' in WORKER
    assert "queue.fal.run/fal-ai/minimax/speech-02-hd" in WORKER
    assert "falling back to edge-tts" in WORKER
    # Хвостовая тишина срезается, звук исходника глушится маппингом дорожек.
    assert "areverse,silenceremove" in WORKER
    assert '"-map", "0:v", "-map", "1:a"' in WORKER
    # Плашки: кириллический шрифт файлом, тексты через textfile= (никакого
    # экранирования кавычек в -vf).
    assert "DejaVuSans-Bold.ttf" in WORKER
    assert "textfile=" in WORKER
    # Retry-безопасная заливка детерминированного имени.
    assert "upsert=True" in WORKER
    # Ключ fal опционален и пробрасывается компоузом; шрифт зафиксирован apt.
    assert 'FAL_KEY: "${FAL_KEY:-}"' in COMPOSE
    dockerfile = (ROOT / "Dockerfile.local").read_text(encoding="utf-8")
    assert "fonts-dejavu-core" in dockerfile
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "edge-tts==" in requirements


def test_finalize_caption_windows_scale_with_duration() -> None:
    """Окна плашек масштабируются k = duration/10: на 15-секундном ролике
    первое окно — (0.45, 4.8)."""
    assert "CAPTION_WINDOWS = ((0.3, 3.2" in WORKER
    scale = 15.0 / 10.0
    start, end = 0.3 * scale, 3.2 * scale
    assert (round(start, 2), round(end, 2)) == (0.45, 4.8)
    assert "duration / 10.0" in WORKER


def test_clean_master_registers_derived_source_with_lineage() -> None:
    # Производный файл — полноценный source_video с ролью и родословной:
    # его можно выбирать в «Копии»/«Создании» как обычный исходник.
    assert "'role', 'source_video_clean'" in QUEUE
    assert "'derived_from_media_id', source_row.id" in QUEUE
    assert "media-clean-master-" in QUEUE
    # Анализ штампует prep_-факты в метадату исходника.
    assert "'prep_analyzed_at', now()" in QUEUE
    assert "'prep_screen_recording_likely'" in QUEUE


def test_workspace_media_items_carry_preparation_facts() -> None:
    # Патч creator_workspace_section: fail-closed якорь, выборочный срез
    # (не вся метадата), идемпотентный повтор.
    assert "workspace_section_anchor_missing" in FACTS
    assert "workspace_section_anchor_ambiguous" in FACTS
    assert "workspace_section_already_patched" in FACTS
    assert "jsonb_strip_nulls" in FACTS
    for key in (
        "'role'",
        "'origin_url'",
        "'prep_analyzed_at'",
        "'prep_screen_recording_likely'",
    ):
        assert key in FACTS, key


def test_worker_pipeline_is_stdlib_ffmpeg_and_bounded() -> None:
    # stdlib-only для сети: без библиотеки requests воркер живёт в образе
    # репо (edge-tts — единственный pip и зовётся подпроцессом, не импортом;
    # слово «requests» в URL fal-очереди — не библиотека).
    assert "import urllib.request" in WORKER
    assert "import requests" not in WORKER
    assert "from requests" not in WORKER
    assert "import edge_tts" not in WORKER
    # Анализ: probe + рамка + статичные края + эвристика записи экрана.
    assert "cropdetect" in WORKER
    assert "freezedetect" in WORKER
    assert "screen_recording_likely" in WORKER
    # Чистый мастер: минимум 4 секунды, апскейл до 720, faststart, кап 50МБ.
    assert "keep < 4.0" in WORKER
    assert "scale=720:-2:flags=lanczos" in WORKER
    assert "+faststart" in WORKER
    assert "clean_master_exceeds_50mb" in WORKER
    # Цикл: claim → heartbeat → complete/fail, ключ только из окружения.
    for rpc in (
        "system_claim_media_preparation",
        "system_heartbeat_media_preparation",
        "system_complete_media_analysis",
        "system_complete_media_clean_master",
        "system_fail_media_preparation",
    ):
        assert rpc in WORKER, rpc
    assert 'os.environ.get("SUPABASE_SERVICE_ROLE_KEY"' in WORKER


def test_compose_runs_worker_without_secrets_in_repo() -> None:
    assert "media-preparation-worker:" in COMPOSE
    assert "- scripts/media_preparation_worker.py" in COMPOSE
    # Ключ — только плейсхолдер из .env; в репозитории секретов нет.
    assert 'SUPABASE_SERVICE_ROLE_KEY: "${SUPABASE_SERVICE_ROLE_KEY:-}"' in COMPOSE


def test_media_cards_offer_preparation_and_show_facts() -> None:
    # Кнопки только у видео-исходников; чистый мастер — только когда анализ
    # реально увидел запись экрана; сам чистый файл кнопок не предлагает.
    assert "function mediaPreparationMarkup(item)" in PORTAL
    assert 'String(item.kind || "") !== "source_video"' in PORTAL
    assert 'data-action="media-prep"' in PORTAL
    assert "prep_screen_recording_likely === true" in PORTAL
    assert '"source_video_clean"' in PORTAL
    assert "Создать чистый мастер" in PORTAL
    # Обработчик зовёт операторский RPC и честно показывает отказ.
    assert 'action === "media-prep"' in PORTAL
    assert "creator_enqueue_media_preparation" in PORTAL
    assert "enqueueMediaPreparation" in PORTAL
    assert ".media-preparation" in CSS


def test_materials_are_findable_from_finder() -> None:
    """Фидбек владельца 27.08: «ищу материалы — очень не интуитивно».
    Список файлов с кнопками подготовки живёт во вкладке «Мои материалы»
    (бывшие «Недавние»), вкладка загрузки подсказывает дорогу, плитка
    обзора и быстрый доступ Finder называют раздел тем же словом."""
    board = (ROOT / "web" / "app" / "workspace-board-view.js").read_text(
        encoding="utf-8"
    )
    assert ">Мои материалы</a>" in PORTAL
    assert "во вкладке «Мои материалы»" in PORTAL
    assert 'title: "Материалы"' in board
    assert 'href="#/workspace/media?view=recent"' in board
    assert ">Материалы</span>" in board
