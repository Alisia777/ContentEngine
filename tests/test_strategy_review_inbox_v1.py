"""Очередь проверки роликов и вкладка «Команда → Аккаунты» (24.08.2026).

Владелица: «форма проверить — туда чтобы падали ролики-черновики; я как
оператор вижу свои ролики: либо отвергнуть, либо принять и разместить; как
админ вижу все ролики. В команде — вкладка по аккаунтам и подключениям».
Черновики стратегий сами появляются в «Проверке контента»; отказ уводит файл
в «Корзину» с причиной, принятие открывает существующий диалог размещения.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/202608240003_strategy_review_inbox_v1.sql"
PGTAP = ROOT / "supabase/tests/strategy_review_inbox_v1_test.sql"
API = ROOT / "web/app/supabase-api.js"
APP = ROOT / "web/app/app.js"
REVIEW_VIEW = ROOT / "web/app/content-review-view.js"
REVIEW_CSS = ROOT / "web/app/content-review.css"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_the_catalog_carries_lifecycle_facts_and_reject_reuses_the_trash_contour() -> None:
    sql = text(MIGRATION)
    # Очередь строится из того же каталога проверок — без второго источника.
    assert "'lifecycle_stage', media.lifecycle_stage," in sql
    assert "'artifact_class', media.artifact_class," in sql
    assert "'owner_name', coalesce(owner_profile.display_name, owner_profile.email)" in sql
    # Отказ — решение после просмотра, с обязательной причиной.
    assert "create or replace function public.creator_reject_generation_result(" in sql
    assert "p_payload -> 'watch_confirmed' is distinct from 'true'::jsonb" in sql
    assert "reject_result_watch_confirmation_required" in sql
    assert "'reason', 5, 500" in sql
    assert "reject_result_media_not_generated_video" in sql
    assert "reject_result_media_already_published" in sql
    # Оператор отвергает только свои; менеджерская область — как в корзине.
    assert "reject_result_scope_denied" in sql
    assert "manager_scope or media_row.owner_id = actor_id" in sql
    # Файл уезжает в существующую «Корзину», а не в новый механизм.
    assert "perform public.workspace_trash_items(jsonb_build_object(" in sql
    assert "'strategy-reject-trash:' || media_id::text" in sql
    assert "'rejection', jsonb_build_object(" in sql
    assert "begin_command" in sql and "finish_command" in sql
    # Витрина аккаунтов — управленческая и без регистрационных реквизитов.
    assert "create or replace function public.creator_team_accounts(" in sql
    assert "team_accounts_role_denied" in sql
    assert "registration_email_alias" not in sql
    assert "registration_phone_ref" not in sql
    assert "'custodian_name', coalesce(custodian.display_name, custodian.email)" in sql
    assert "'placements_published'" in sql
    pgtap = text(PGTAP)
    assert "select plan(15);" in pgtap


def test_browser_api_guards_reason_and_watch_before_the_server_call() -> None:
    api = text(API)
    assert 'rejectGenerationResult: "creator_reject_generation_result",' in api
    assert 'teamAccounts: "creator_team_accounts",' in api
    assert "reject_result_reason_invalid" in api
    assert "reject_result_watch_confirmation_required" in api
    assert 'data.version !== "team-accounts-v1"' in api


def test_drafts_fall_into_the_review_inbox_with_both_decisions() -> None:
    app = text(APP)
    # Очередь видна прямо на «Проверке контента» и строится из каталога.
    assert "function strategyReviewInboxMarkup(catalog)" in app
    assert '&& item.lifecycleStage === "drafts"' in app
    assert "${strategyReviewInboxMarkup(catalog)}" in app
    # Оба решения — с карточки: разместить или отвергнуть.
    assert 'data-action="publish-workspace-result"' in app
    assert 'data-action="reject-workspace-result"' in app
    assert "function openRejectResultDialog({ projectId, mediaId, mediaTitle = \"\" })" in app
    assert 'name="reason" required minlength="5"' in app
    assert 'name="watch_confirmed" required' in app
    # После решения обновляется именно текущий раздел, включая «Проверку».
    assert 'state.route.path === "/workspace/review" ? "review" : "board"' in app
    view = text(REVIEW_VIEW)
    assert "lifecycleStage: text(raw.lifecycle_stage || raw.lifecycleStage, 40).toLowerCase()," in view
    assert "ownerName: text(raw.owner_name || raw.ownerName, 200)," in view
    css = text(REVIEW_CSS)
    assert ".strategy-review-card" in css


def test_the_results_screen_opens_with_the_funnel_head() -> None:
    """«Не хватает главного экрана: создали → смотрим → размещаем → собираем
    статистику». Хвост воронки (публикации и метрики) в «Результатах» уже жил;
    голова — серверные счётчики этапов из тех же таблиц, что и сами разделы."""
    funnel_sql = text(ROOT / "supabase/migrations/202608240004_results_funnel_v1.sql")
    assert "create or replace function public.creator_results_funnel(" in funnel_sql
    assert "'awaiting_review', media_counts.awaiting_review," in funnel_sql
    assert "'placement_in_progress', placement_counts.placement_in_progress," in funnel_sql
    assert "media.metadata ->> 'kind' = 'generated_video'" in funnel_sql
    api = text(API)
    assert 'resultsFunnel: "creator_results_funnel",' in api
    assert 'data.version !== "results-funnel-v1"' in api
    app = text(APP)
    assert "function resultsFunnelMarkup()" in app
    assert "${resultsFunnelMarkup()}" in app
    assert "async function loadResultsFunnel({ silent = false } = {})" in app
    # Каждый этап ведёт в свой раздел — воронка кликабельна, а не декоративна.
    assert '{ key: "awaiting_review", label: "Ждут проверки", hint: "черновики", href: "#/workspace/review" }' in app


def test_supabase_api_is_imported_as_exactly_one_module_instance() -> None:
    """Разные ?v= на supabase-api.js создают два экземпляра модуля: патч
    алиасов «Корзины» ложился на чужой прототип, и заявки уходили старым
    именем creator_workspace_trash_browser — бесконечный шторм 404 в проде."""
    stamps = set()
    for path in (ROOT / "web" / "app").glob("*.js"):
        stamps.update(re.findall(
            r'from "\./supabase-api\.js\?v=([^"]+)"',
            path.read_text(encoding="utf-8"),
        ))
    assert len(stamps) == 1, f"supabase-api.js imported with mixed stamps: {sorted(stamps)}"


def test_the_team_section_gains_the_accounts_tab_with_connections() -> None:
    app = text(APP)
    assert '{ view: "accounts", href: "#/workspace/team?view=accounts", label: "Аккаунты" },' in app
    assert "function teamAccountsPanelMarkup()" in app
    assert "async function loadTeamAccounts({ silent = false } = {})" in app
    assert "TEAM_ACCOUNT_CONNECTION_LABELS" in app
    # Пустой реестр честно ведёт в админку, а не молчит.
    assert "Реестр аккаунтов пуст" in app
