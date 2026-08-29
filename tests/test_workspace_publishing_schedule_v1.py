"""«Запланировать публикацию»: постановка размещения в очередь фазы 1.

Пины источников: реестр RPC, метод API без mutate-идемпотентности (строгий
список ключей payload на сервере), кнопка на карточке размещения, диалог с
предпросмотром автоподписи маркировки и именованные отказы enqueue.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_rpc_registry_and_api_method_shape() -> None:
    assert 'enqueuePublishingJob: "creator_enqueue_publishing_job",' in API
    method = API.split("async enqueuePublishingJob(input)", 1)[1].split(
        "\n  }\n", 1
    )[0]
    # Идемпотентность живёт на сервере (unique organization_id+placement_id):
    # лишний idempotency_key в payload — отказ
    # publishing_enqueue_payload_invalid, поэтому метод обязан идти мимо
    # mutate().
    assert "idempotency_key" not in method
    assert "this.mutate(" not in method
    assert "this.call(RPC.enqueuePublishingJob" in method
    assert 'data.version !== "publishing-enqueue-v1"' in method
    # ORGANIC не несёт рекламных реквизитов: сервер отвечает отказом
    # publishing_enqueue_organic_with_advertiser на любой из трёх ключей.
    assert 'if (erid !== "ORGANIC") {' in method
    organic_gate = method.split('if (erid !== "ORGANIC") {', 1)[1]
    advertising_only = organic_gate.split("const caption", 1)[0]
    for key in (
        "payload.advertiser",
        "payload.ord_provider",
        "payload.contract_ref",
    ):
        assert key in advertising_only, key


def test_placement_card_offers_schedule_button_for_actionable_only() -> None:
    card = APP.split("function placementCard(item)", 1)[1].split(
        "const STATS_PAGE_SIZES", 1
    )[0]
    assert 'data-action="open-publishing-schedule"' in card
    # Кнопка живёт только в ветке открытых размещений (ready/scheduled).
    before_button = card.split('data-action="open-publishing-schedule"', 1)[0]
    assert "${actionable ? `" in before_button
    # Карточка проговаривает уже назначенное время.
    assert "formatDate(item.scheduled_at, true)" in card


def test_dialog_mirrors_server_marking_line_and_organic_rules() -> None:
    dialog = APP.split("function openPublishingScheduleDialog(", 1)[1].split(
        "async function moveWorkspaceBoardItem", 1
    )[0]
    # Предпросмотр обязан совпадать с серверной сборкой 202608290006:
    # 'Реклама. ' || advertiser || '. erid: ' || erid.
    assert "`Автоподпись: Реклама. ${advertiser}. erid: ${erid}`" in dialog
    # Для органики подпись обязательна (publishing_enqueue_caption_required),
    # для рекламы обязательны ERID и рекламодатель.
    assert "form.elements.caption.required = organic" in dialog
    assert "field.required = !organic" in dialog
    assert 'erid: organic ? "ORGANIC" :' in dialog
    # Время уходит на сервер абсолютным ISO-штампом.
    assert "scheduledDate.toISOString()" in dialog
    # Клик открывает диалог только из активного проекта.
    click = APP.split('if (action === "open-publishing-schedule") {', 1)[1]
    assert "requireWorkspaceProjectId()" in click[:300]
    assert "openPublishingScheduleDialog({" in click[:600]


def test_named_refusals_translated_and_scheduled_badge_known() -> None:
    for code in (
        "publishing_enqueue_placement_not_open",
        "publishing_enqueue_account_missing",
        "publishing_enqueue_account_not_assigned",
        "publishing_enqueue_scheduled_at_out_of_range",
        "publishing_enqueue_erid_invalid",
        "publishing_enqueue_organic_with_advertiser",
        "publishing_enqueue_caption_required",
    ):
        assert f"{code}:" in API, code
    # После постановки в очередь placement переходит в status=scheduled —
    # бейдж обязан знать метку, а не печатать сырой статус.
    badge = APP.split("function statusBadge(status)", 1)[1].split("}\n", 1)[0]
    assert 'scheduled: "Запланировано",' in badge


def test_dialog_field_names_stay_clear_of_dom_clobbering() -> None:
    dialog = APP.split("function openPublishingScheduleDialog(", 1)[1].split(
        "async function moveWorkspaceBoardItem", 1
    )[0]
    names = set(re.findall(r'name="([A-Za-z_][\w-]*)"', dialog))
    assert names == {
        "scheduled_at",
        "marking_mode",
        "erid",
        "advertiser",
        "ord_provider",
        "contract_ref",
        "caption",
        "hashtags",
    }
