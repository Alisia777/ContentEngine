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
    # stdlib-only: без pip-зависимостей воркер живёт в образе репо.
    assert "import urllib.request" in WORKER
    assert "requests" not in WORKER.replace("urllib.request", "")
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
