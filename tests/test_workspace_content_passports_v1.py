"""«Паспорта роликов» (контур №2 ТЗ 26.08): Dock-приложение и read-модель.

Владелец: «отдельная вкладка в доке, куда человек нажимает — и это срез:
исходники, результат, задание, статистика, гипотеза, деньги». Контракты:
одна server-owned read-модель (два read-only RPC), приложение в доке между
«Результатами» и «Процессами», экран не умирает молча при отказе загрузки,
формулы считаются только из числителей и знаменателей сервера, ноль в
знаменателе — честный отказ, а не NaN.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CORE = (APP / "workspace-os-v4.js").read_text(encoding="utf-8")
CONTRACT = (APP / "workspace-dock-contract.js").read_text(encoding="utf-8")
REGISTRY = (APP / "workspace-command-registry.js").read_text(encoding="utf-8")
CATALOG = (APP / "catalog.js").read_text(encoding="utf-8")
PORTAL = (APP / "app.js").read_text(encoding="utf-8")
API = (APP / "supabase-api.js").read_text(encoding="utf-8")
LOADER = (APP / "workspace-os-v4-loader.js").read_text(encoding="utf-8")
MODULE = (APP / "workspace-content-passports.js").read_text(encoding="utf-8")
SPRITE = (APP / "assets" / "workspace_dock_icon_sprite_v4_7_1.svg").read_text(
    encoding="utf-8"
)
MIGRATION = (
    ROOT / "supabase/migrations/202608260003_content_result_passport_v1.sql"
).read_text(encoding="utf-8")


def test_passports_app_is_registered_across_the_shell() -> None:
    assert 'route: "/workspace/passports"' in CORE
    assert '"passports",' in CORE  # canonical dock order
    assert 'key: "passports"' in CORE
    assert '"/workspace/passports",' in CORE  # project-required routes
    assert 'id="ce-dock-passports"' in SPRITE
    assert 'key: "passports", kind: "app", appId: "passports"' in CONTRACT
    assert "passports: []" in REGISTRY
    assert '["passports", "Паспорта", "◪"]' in CATALOG
    assert '"passports",' in CATALOG  # simple navigation keys


def test_passports_screen_mounts_without_server_section_loader() -> None:
    # Секция не ходит в creator_workspace_section: у паспорта своя read-модель,
    # и её вызывает модуль экрана сам — данные не двоятся.
    assert "passports: renderPassportsSection," in PORTAL
    assert '["research", "passports"].includes(key)' in PORTAL
    assert '["research", "passports"].includes(section)' in PORTAL
    assert "data-content-passports-root" in PORTAL
    loader_entry = LOADER.split("passports: Object.freeze({", 1)[1].split("})", 1)[0]
    assert "/workspace/passports" in loader_entry
    assert "workspace-content-passports.js" in loader_entry


def test_passport_read_model_is_single_and_read_only() -> None:
    assert 'contentPassportRegistry: "creator_content_passport_registry"' in API
    assert 'contentResultPassport: "creator_content_result_passport"' in API
    assert 'data.version !== "content-passport-registry-v1"' in API
    assert 'data.version !== "content-result-passport-v1"' in API
    lowered = MIGRATION.lower()
    for verb in ("insert into", "update content_factory", "delete from"):
        assert verb not in lowered
    assert lowered.count("security definer") == 2
    assert lowered.count("stable") >= 2
    assert "grant execute on function public.creator_content_passport_registry" in MIGRATION
    assert "grant execute on function public.creator_content_result_passport" in MIGRATION
    assert "require_workspace_project_access" in MIGRATION
    # Метрики отдаются числителями и знаменателями; зрелость — только по
    # правилу 72 часов от публикации.
    assert "'views', snapshot.views" in MIGRATION
    assert "interval '72 hours'" in MIGRATION
    assert "'preliminary_metrics', preliminary_value" in MIGRATION


def test_passport_screen_never_dies_silently_and_formulas_refuse_zero() -> None:
    # Отказ загрузки — видимый статус с кнопкой повтора (урок каскада 26.08).
    assert "Паспорта не загрузились" in MODULE
    assert "content-passports-retry" in MODULE
    # Ноль в знаменателе — «Недостаточно данных», никаких NaN и Infinity.
    ratio = MODULE.split("function ratioLine", 1)[1].split("\n}", 1)[0]
    assert "base <= 0" in ratio
    assert "Недостаточно данных" in ratio
    # Деление выполняется только после guard'а по знаменателю: в ветке с
    # процентом guard уже отработал, отдельного «NaN-фильтра» не существует.
    assert ratio.index("base <= 0") < ratio.index("toFixed")
    # Идемпотентный mount: повторный проход при неизменном ключе — ноль работы;
    # собственного MutationObserver у модуля нет (правило адаптеров v4).
    assert "runtime.loadedKey === loadKey" in MODULE
    assert "MutationObserver" not in MODULE
    assert 'registerAdapter(\n      "content-passports"' in MODULE
    # Легаси честно называется легаси, гипотеза не выдумывается.
    assert "Гипотеза не была указана" in MODULE
    assert "Legacy-результат" in MODULE
