"""«Одобрить и разместить» готовый результат (24.08.2026).

Владелица: «оператор смотрит результат, окает — и должен уже размещать; я лезу
искать результат в файлы; формы опубликовать нет». Готовый generated_video
получает действие прямо на карточке «Файлов»: подтверждение полного просмотра +
выданный аккаунт компании (реестр фазы 0) + ERID создают задачу размещения и
строку placements; финальную ссылку подтверждает существующая задача.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202608240001_strategy_result_publish_v1.sql"
VOLATILE_FIX = ROOT / "supabase/migrations/202608240002_publishing_accounts_volatile_v1.sql"
PGTAP = ROOT / "supabase/tests/strategy_result_publish_v1_test.sql"
API = ROOT / "web/app/supabase-api.js"
APP = ROOT / "web/app/app.js"
BOARD = ROOT / "web/app/workspace-board-view.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_rpc_pair_guards_watch_erid_account_and_idempotency() -> None:
    sql = text(MIGRATION)
    assert "create or replace function public.creator_publishing_accounts(" in sql
    assert "create or replace function public.creator_publish_generation_result(" in sql
    # «Окнул» — это действие: literal true, не молчаливый дефолт формы.
    assert "p_payload -> 'watch_confirmed' is distinct from 'true'::jsonb" in sql
    assert "publish_result_watch_confirmation_required" in sql
    # ERID обязателен и в закрытой форме; органика — явное слово, не пустота.
    assert "erid_value !~ '^[A-Z0-9-]{4,64}$'" in sql
    # Размещается именно результат: kind + job выводится из самого файла.
    assert "publish_result_media_not_generated_video" in sql
    assert "nullif(media_row.metadata ->> 'generation_job_id', '')::uuid" in sql
    # Аккаунт — активный и с включённым размещением; площадка — его.
    assert "publish_result_account_unavailable" in sql
    assert "publish_result_account_posting_disabled" in sql
    # Контур прежний: задача 'placement' + placements(ready) идемпотентно.
    assert "'strategy-placement-task:' || job_id::text" in sql
    assert "on conflict on constraint placements_organization_id_idempotency_key_key" in sql
    # Одобренный результат перестаёт быть черновиком.
    assert "set lifecycle_stage = 'ready', updated_at = now()" in sql
    assert "begin_command" in sql and "finish_command" in sql
    pgtap = text(PGTAP)
    assert "select plan(13);" in pgtap
    # PostgREST исполняет stable-функции в read-only транзакции, а приватные
    # помощники дозаписывают строки — листинг обязан остаться volatile (25006).
    assert (
        "alter function public.creator_publishing_accounts(jsonb) volatile;"
        in text(VOLATILE_FIX)
    )


def test_browser_api_validates_inputs_before_money_adjacent_calls() -> None:
    api = text(API)
    assert 'publishingAccounts: "creator_publishing_accounts",' in api
    assert 'publishGenerationResult: "creator_publish_generation_result",' in api
    assert 'data.version !== "publishing-accounts-v1"' in api
    assert "/^[A-Z0-9-]{4,64}$/.test(erid)" in api
    assert 'input?.watch_confirmed !== true' in api
    # Ключ generation_job_id уходит только когда он известен: пустая строка
    # валит require_uuid на сервере (generation_job_id_invalid) — форма падала.
    assert "...(generationJobId ? { generation_job_id: generationJobId } : {})," in api


def test_the_ready_result_card_offers_publish_and_the_dialog_survives_renders() -> None:
    board = text(BOARD)
    assert 'selectedItem.kind === "generated_video" && selectedItem.status === "ready"' in board
    assert 'data-action="publish-workspace-result"' in board
    app = text(APP)
    assert 'if (action === "publish-workspace-result") {' in app
    assert "async function openPublishResultDialog({ projectId, mediaId, mediaTitle = \"\" })" in app
    # Диалог императивный: перерисовки доски не стирают недописанную форму.
    assert 'dialog.dataset.workspacePublishDialog = "";' in app
    assert "dialog.showModal();" in app
    # Без аккаунтов форма честно ведёт в реестр, а не молчит.
    assert "Владелец заводит их в «Люди → Аккаунты»" in app
    assert 'name="erid" required' in app
    assert 'name="watch_confirmed" required' in app
