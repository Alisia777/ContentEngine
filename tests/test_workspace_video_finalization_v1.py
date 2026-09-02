"""«Финализация» готового ролика: наряд локального воркера (TTS + плашки).

Пины источников: реестр RPC, метод API мимо mutate (идемпотентность на
сервере — одно активное задание на ролик), кнопка на карточке готового
платного ролика архива, императивный диалог без скрытых required-полей,
переводы именованных отказов и словарь голосов, сквозной для UI/RPC/воркера.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
MIGRATION = (
    ROOT / "supabase/migrations/202609020001_video_finalization_queue_v1.sql"
).read_text(encoding="utf-8")
JOB_LOOKUP = (
    ROOT / "supabase/migrations/202609020002_video_finalization_job_lookup_v1.sql"
).read_text(encoding="utf-8")


def test_rpc_registry_and_api_method_shape() -> None:
    assert 'enqueueVideoFinalization: "creator_enqueue_video_finalization",' in API
    method = API.split("async enqueueVideoFinalization(input)", 1)[1].split(
        "\n  }\n", 1
    )[0]
    # Идемпотентность серверная (partial-индекс очереди): лишний
    # idempotency_key в строгом payload — отказ, метод идёт мимо mutate().
    assert "idempotency_key" not in method
    assert "this.mutate(" not in method
    assert "this.call(RPC.enqueueVideoFinalization" in method
    assert 'data.version !== "video-finalization-enqueue-v1"' in method
    assert "text.length > 80" in method
    assert "narration.length > 300" in method
    # Ролик называется media_id ИЛИ нарядом генерации (архив стратегий не
    # отдаёт output_media_id) — сервер требует ровно один из ключей.
    assert "(!mediaId && !generationJobId)" in method
    assert "generation_job_id: generationJobId" in method
    # Словарь голосов сквозной: форма, метод, plpgsql-whitelist и
    # FINALIZE_VOICES воркера обязаны называть одни и те же значения.
    for voice in (
        "minimax_lovely_girl", "minimax_lively_girl", "minimax_calm_woman",
        "minimax_wise_woman", "minimax_deep_voice_man",
        "minimax_friendly_person", "edge_svetlana", "edge_dmitry",
    ):
        assert f'"{voice}"' in method, voice
    # Тайминги плашек: либо не заданы (авто), либо три честные пары.
    assert "caption_windows" in method
    assert "pair[1] > pair[0]" in method
    # Третья итерация: раскладка и звук — опциональные словари.
    assert "caption_positions" in method
    assert '["top", "bottom"].includes(slot)' in method
    assert '["small", "medium", "large"].includes(fontScale)' in method
    assert '["replace", "duck"].includes(audioMode)' in method


def test_archive_card_offers_finalization_for_ready_video_only() -> None:
    markup = APP.split("function generationFinalizationMarkup(details)", 1)[1]
    markup = markup.split("function generationActionsMarkup", 1)[0]
    assert 'data-action="open-video-finalization"' in markup
    assert "data-media-id=" in markup
    # Фото не финализируем; кнопка только на завершённом запуске.
    assert "details.photo" in markup
    assert '"succeeded", "completed"' in markup
    # Кнопка включена в общий блок действий карточки.
    assert (
        "generationPassportLinkMarkup(details) + generationFinalizationMarkup(details)"
        in APP
    )


def test_strategy_record_offers_finalization_by_job_id() -> None:
    # Карточка стратегии в архиве не несёт output_media_id — кнопка живёт
    # рядом с «Повторить стратегию» и называет ролик нарядом генерации.
    record = APP.split('data-action="repeat-generation-strategy"', 1)[1]
    record = record.split("<small>", 1)[0]
    assert 'data-action="open-video-finalization"' in record
    assert 'data-generation-job-id="${escapeHtml(details.jobId)}"' in record
    assert '"succeeded", "completed"' in record


def test_click_branch_requires_active_project() -> None:
    click = APP.split('if (action === "open-video-finalization") {', 1)[1]
    assert "requireWorkspaceProjectId()" in click[:300]
    assert "openVideoFinalizationDialog({" in click[:600]


def test_dialog_has_no_hidden_required_fields_and_clean_names() -> None:
    dialog = APP.split("function openVideoFinalizationDialog(", 1)[1].split(
        "function openPublishingScheduleDialog(", 1
    )[0]
    names = set(re.findall(r'name="([A-Za-z_][\w-]*)"', dialog))
    assert names == {
        "caption_top",
        "caption_top_from",
        "caption_top_to",
        "caption_top_position",
        "caption_mid",
        "caption_mid_from",
        "caption_mid_to",
        "caption_mid_position",
        "caption_bottom",
        "caption_bottom_from",
        "caption_bottom_to",
        "caption_bottom_position",
        "narration_text",
        "narration_voice",
        "font_scale",
        "audio_mode",
    }
    # Мина reportValidity: в диалоге нет условно скрываемых required-полей.
    assert "hidden" not in dialog
    assert "form.reportValidity()" in dialog


def test_named_refusals_translated() -> None:
    for code in (
        "video_finalization_payload_invalid",
        "video_finalization_media_not_found",
        "video_finalization_kind_not_generated_video",
        "video_finalization_voice_invalid",
        "video_finalization_too_short",
        "video_finalization_caption_positions_invalid",
        "video_finalization_font_scale_invalid",
        "video_finalization_audio_mode_invalid",
    ):
        assert f"{code}:" in API, code


def test_migration_contract_matches_ui() -> None:
    # Голоса и версия ответа зафиксированы в plpgsql той же строкой.
    assert "('minimax_lovely_girl', 'edge_svetlana')" in MIGRATION
    assert "'video-finalization-enqueue-v1'" in MIGRATION
    assert "'finalize_video'" in MIGRATION
    assert "system_complete_video_finalization" in MIGRATION
    # Ролик короче 5 секунд отклоняется до очереди.
    assert "video_finalization_too_short" in MIGRATION
    # Верификация поведения присутствует.
    assert "ПРОВЕРКА ПОВЕДЕНИЕМ" in MIGRATION
    # Поиск по наряду генерации: ровно один из media_id/generation_job_id.
    assert "generation_job_id" in JOB_LOOKUP
    assert "video_finalization_media_reference_invalid" in JOB_LOOKUP
    assert (
        "(p_payload ? 'media_id') = (p_payload ? 'generation_job_id')"
        in JOB_LOOKUP
    )
    # Вторая итерация: восемь голосов и настраиваемые окна плашек.
    voices_migration = (
        ROOT
        / "supabase/migrations/202609020003_video_finalization_voices_timings_v1.sql"
    ).read_text(encoding="utf-8")
    for voice in (
        "minimax_lively_girl", "minimax_calm_woman", "minimax_wise_woman",
        "minimax_deep_voice_man", "minimax_friendly_person", "edge_dmitry",
    ):
        assert voice in voices_migration, voice
    assert "video_finalization_caption_windows_invalid" in voices_migration
    assert "jsonb_array_length(windows_value) <> 3" in voices_migration
    # Воркер знает те же голоса и берёт окна из params как абсолютные секунды.
    worker = (ROOT / "scripts/media_preparation_worker.py").read_text(
        encoding="utf-8"
    )
    assert "FINALIZE_VOICES" in worker
    for voice in ("Lively_Girl", "Calm_Woman", "Wise_Woman", "Deep_Voice_Man",
                  "Friendly_Person", "ru-RU-DmitryNeural"):
        assert voice in worker, voice
    assert "caption_windows_from_params" in worker
    assert "finalize_caption_windows_invalid" in worker
    # Третья итерация: раскладка (позиции/шрифт) и режим звука сквозные
    # с миграцией 0004 и селектами диалога.
    layout_migration = (
        ROOT
        / "supabase/migrations/202609020004_video_finalization_layout_audio_v1.sql"
    ).read_text(encoding="utf-8")
    for guard in (
        "video_finalization_caption_positions_invalid",
        "video_finalization_font_scale_invalid",
        "video_finalization_audio_mode_invalid",
        "jsonb_array_length(positions_value) <> 3",
        "('small', 'medium', 'large')",
        "('replace', 'duck')",
    ):
        assert guard in layout_migration, guard
    assert "caption_positions_from_params" in worker
    assert "FINALIZE_FONT_SCALES" in worker
    for scale in ('"small"', '"medium"', '"large"'):
        assert scale in worker, scale
    assert "amix=inputs=2" in worker  # duck: родная дорожка тихо под голосом
