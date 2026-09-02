"""Гейт «Дуэта»: страховка формы + история выключения/включения маршрута.

03.09 маршрут heygen выключался (202609030004) и в тот же день включён
обратно решением владельца (202609030005): «Дуэт» — одна из трёх стратегий
витрины. Гейт формы остаётся в коде как страховка: срабатывает ТОЛЬКО
когда реестр отдал маршруты и все выключены; при живом маршруте заглушки
нет. Стратегия всегда остаётся в каталоге («ровно три стратегии»).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/202609030004_duet_route_disabled_v1.sql"
).read_text(encoding="utf-8")
REENABLE = (
    ROOT / "supabase/migrations/202609030005_duet_route_reenabled_v1.sql"
).read_text(encoding="utf-8")
INTAKE = (
    ROOT / "web/app/generation-strategy-intake-v4.js"
).read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")


def test_migration_disables_single_route_and_keeps_guard() -> None:
    assert "set enabled = false" in MIGRATION
    assert "strategy_id = 'viral_avatar_ugc'" in MIGRATION
    assert "provider = 'heygen'" in MIGRATION
    # Проверка поведением: гвард платного старта и отсутствие живых маршрутов.
    assert "generation_strategy_executable_route_exists" in MIGRATION
    assert "duet_route_still_enabled" in MIGRATION
    assert "generation_strategy_no_executable_route" in MIGRATION
    # Стратегию из каталога не удаляем — только маршрут.
    assert "delete" not in MIGRATION.lower()
    # Финальное состояние: маршрут включён обратно (решение владельца),
    # verify поведением подтверждает живой executable-маршрут.
    assert "set enabled = true" in REENABLE
    assert "strategy_id = 'viral_avatar_ugc'" in REENABLE
    assert "duet_route_still_disabled" in REENABLE
    assert REENABLE.index("202609030005") > 0


def test_intake_panel_gates_duet_honestly() -> None:
    # Гейт срабатывает только на явном «маршруты отданы и все выключены».
    gate = INTAKE.split("function duetRoutesAllDisabled()", 1)[1]
    gate = gate.split("function setRoute(", 1)[0]
    assert "routes.length > 0" in gate
    assert "route?.enabled === true" in gate
    assert "data-duet-route-gate" in gate
    assert "Формат «Дуэт» в подготовке" in gate
    # Кнопки глушатся принудительно только при гейте; без гейта их
    # состоянием управляет собственная логика формы.
    assert "generation-intake-analyze-avatar" in gate
    assert "generation-intake-prepare-avatar" in gate
    # Вызов в ветке переключения на «Дуэт» (setRoute, else-if).
    avatar_branch = INTAKE.split(
        '} else if (route === "avatar_video") {', 1
    )[1][:600]
    assert "syncDuetAvailabilityGate(state)" in avatar_branch


def test_catalog_contract_still_three_strategies() -> None:
    # Контракт каталога требует ровно три стратегии — скрытие «Дуэта»
    # реализовано маршрутом, а не выпиливанием стратегии.
    assert "catalog.strategies.length !== 3" in API
