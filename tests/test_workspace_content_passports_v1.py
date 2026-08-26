"""«Паспорта роликов» (контур №2 ТЗ 26.08): Dock-приложение и read-модель.

Владелец: «отдельная вкладка в доке, куда человек нажимает — и это срез:
исходники, результат, задание, статистика, гипотеза, деньги». Контракты:
одна server-owned read-модель (два read-only RPC), приложение в доке между
«Результатами» и «Процессами», загрузка и рендер — в СЕКЦИОННОМ контуре
app.js (боевой урок 26.08: отдельный сателлитный модуль во встроенном окне
доезжал не всегда, и экран вечно «загружался»), отказ виден и даёт
«Повторить», формулы считаются только из числителей и знаменателей сервера,
ноль в знаменателе — честный отказ, а не NaN.
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


def test_passports_load_and_render_live_in_the_portal_section_loop() -> None:
    # Загрузка — стандартный loadSection: никакой зависимости от доставки
    # отдельного скрипта. Сателлитного модуля не существует вовсе.
    assert not (APP / "workspace-content-passports.js").exists()
    assert "passports: renderPassportsSection," in PORTAL
    assert 'section === "passports"' in PORTAL
    assert "state.api.contentPassportRegistry({ projectId })" in PORTAL
    assert "state.api.contentResultPassport({" in PORTAL
    loader_entry = LOADER.split("passports: Object.freeze({", 1)[1].split("})", 1)[0]
    assert "/workspace/passports" in loader_entry
    assert "workspace-content-passports.css" in loader_entry
    assert "modules: []" in loader_entry
    assert "workspace-content-passports.js" not in LOADER
    # Deep-link сменился — данные устарели и перезагружаются, прошлый срез
    # не выдаётся за текущий.
    assert "data.key !== passportSectionKey()" in PORTAL
    # «Открыть паспорт» доступен из архива генераций тем же deep-link.
    assert "generationPassportLinkMarkup" in PORTAL
    assert "data-generation-passport-link" in PORTAL


def test_passport_read_model_is_single_and_read_only() -> None:
    assert 'contentPassportRegistry: "creator_content_passport_registry"' in API
    assert 'contentResultPassport: "creator_content_result_passport"' in API
    assert 'data.version !== "content-passport-registry-v1"' in API
    assert 'data.version !== "content-result-passport-v1"' in API
    lowered = MIGRATION.lower()
    for verb in ("insert into", "update content_factory", "delete from"):
        assert verb not in lowered
    assert lowered.count("security definer") == 2
    # Волатильность — боевой урок 26.08 21:09: current_profile_id() пишет
    # профиль при каждом вызове, а не-volatile RPC исполняется PostgREST в
    # read-only транзакции («cannot execute INSERT in a read-only
    # transaction»). Обе функции обязаны быть volatile (202608260004).
    volatility_fix = (
        ROOT / "supabase/migrations/202608260004_content_passport_volatile_v1.sql"
    ).read_text(encoding="utf-8")
    assert (
        "alter function public.creator_content_passport_registry(jsonb) volatile"
        in volatility_fix
    )
    assert (
        "alter function public.creator_content_result_passport(jsonb) volatile"
        in volatility_fix
    )
    assert "grant execute on function public.creator_content_passport_registry" in MIGRATION
    assert "grant execute on function public.creator_content_result_passport" in MIGRATION
    assert "require_workspace_project_access" in MIGRATION
    # Метрики отдаются числителями и знаменателями; зрелость — только по
    # правилу 72 часов от публикации.
    assert "'views', snapshot.views" in MIGRATION
    assert "interval '72 hours'" in MIGRATION
    assert "'preliminary_metrics', preliminary_value" in MIGRATION


def test_passport_screen_shows_failures_and_formulas_refuse_zero() -> None:
    # Отказ загрузки — видимая карточка со стандартной кнопкой повтора секции.
    assert "Паспорта не загрузились" in PORTAL
    assert 'data-action="refresh-section" data-section="passports"' in PORTAL
    # Ноль в знаменателе — «Недостаточно данных»; деление — только после
    # guard'а по знаменателю.
    ratio = PORTAL.split("function passportRatioMarkup", 1)[1].split("\n}", 1)[0]
    assert "base <= 0" in ratio
    assert "Недостаточно данных" in ratio
    assert ratio.index("base <= 0") < ratio.index("toFixed")
    # Легаси честно называется легаси, гипотеза не выдумывается.
    assert "Гипотеза не была указана" in PORTAL
    assert "Legacy-результат" in PORTAL
