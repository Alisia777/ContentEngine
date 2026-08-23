"""Каскад «модель → сложность → время» доходит до сервера и до денег.

Экран «Копии» показывал три движка и исполнял один: цену привязки считала
generation_strategy_recipe_price, а она отвечает только про ДЕЙСТВУЮЩИЙ маршрут
реестра. Выбор был витриной.

Здесь проверяется, что выбор проходит все слои целиком — форма, браузерный
контракт, Edge, SQL — и что каждый слой отказывает, когда выбор неполон. Ни
один слой не имеет права придумать движок по умолчанию: цена, квитанция и
строка подтверждения расхода подписываются вместе, и подставленный движок
означал бы подпись под чужой суммой.
"""

from __future__ import annotations

import re
from pathlib import Path

from pglast import parse_plpgsql, parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase/migrations"
ENGINE_CHOICE = (
    MIGRATIONS / "202608190006_generation_strategy_operator_engine_choice_v1.sql"
)
QUALITY_MODES = (
    MIGRATIONS / "202608190007_generation_strategy_route_quality_modes_v1.sql"
)
SOURCE_DURATION = (
    MIGRATIONS / "202608190008_generation_strategy_source_duration_price_v1.sql"
)
RUNWAY_SOURCE_DURATION = (
    MIGRATIONS
    / "202608210003_generation_strategy_runway_product_swap_source_duration_v1.sql"
)
EDGE = ROOT / "supabase/functions/creator-generate/index.ts"
ADAPTERS = ROOT / "supabase/functions/_shared/generation-recipe-adapters.js"
CATALOG = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
RUNTIME = ROOT / "web/app/generation-strategy-runtime.js"
API = ROOT / "web/app/supabase-api.js"
APP = ROOT / "web/app/app.js"
GUIDED = ROOT / "web/app/workspace-os-v4-generation-guided.js"
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_bind_migration_prices_the_asked_engine_and_keeps_the_old_path() -> None:
    sql = text(ENGINE_CHOICE)

    # Обёртка транзакции — первой строкой файла: загрузчик миграций сверяет её
    # регулярным выражением от начала файла.
    assert sql.startswith("begin;\n")
    assert sql.rstrip().endswith("commit;")

    # Цена спрошенного движка считается маршрутной функцией, а прежний путь —
    # для запроса без движка — остаётся дословно тем же.
    assert "generation_strategy_route_price(" in sql
    assert "generation_strategy_recipe_price(" in sql
    assert "if p_payload ? 'engine' then" in sql
    assert "'idempotency_key', 'engine'" in sql

    # Ключ engine допустим, но НЕ обязателен. Миграция дописывает его ровно в
    # один список — тот, которым проверяются ЛИШНИЕ ключи (p_payload - array).
    # Список обязательных ключей (?&) не патчится вовсе, поэтому запрос без
    # движка остаётся правильным запросом.
    assert sql.count("'idempotency_key', 'engine'") == 1
    assert "if p_payload - array[" in sql
    assert "p_payload ?& array[" not in sql

    # Половина движка — отказ, а не умолчание.
    assert "array['provider', 'model_key']::text[]" in sql
    assert "generation_strategy_resolve_bind_payload_invalid" in sql

    # Квитанция сверяет цену маршрута, названного в снимке, а не действующего.
    assert "route.pricing_version =" in sql
    assert "selection_row.price_snapshot ->> 'provider'" in sql

    # Подпись маршрута однозначна по построению, иначе «маршрут из подписи»
    # перестал бы восстанавливаться, а отправка и опрос разошлись бы.
    assert "generation_strategy_provider_routes_signature_key" in sql
    assert "where enabled" in sql

    # Пределы Kling — те, что принимает провайдер: вход 3–15 секунд, и
    # длительность результата задаёт исходник при посекундной ставке.
    assert "min_duration_seconds = 3" in sql
    assert "max_duration_seconds = 15" in sql

    # Деньги не сдвинулись: проверяется равенство снимку, а не имя провайдера.
    assert "active_route_drifted" in sql
    assert "route_price_drifted" in sql


def test_quality_modes_migration_describes_only_real_choices() -> None:
    sql = text(QUALITY_MODES)

    assert sql.startswith("begin;\n")
    assert sql.rstrip().endswith("commit;")

    # Режим — код, надпись и разрешение. Проверка формы живёт в immutable
    # функции: подзапросы в check Postgres не принимает.
    assert "generation_strategy_quality_modes_valid" in sql
    assert "immutable" in sql
    assert "generation_strategy_provider_routes_quality_check" in sql

    # У Runway выбор есть и он стоит разных денег, у маршрутов fal разрешение
    # задаёт исходник — там один честный режим вместо переключателя-обманки.
    assert "'Как в исходнике'" in sql
    assert "'Стандарт'" in sql
    assert "'Максимум'" in sql
    assert "quality_mode_price_drifted" in sql

    # Каталог отдаёт режимы браузеру.
    assert "''quality_modes'', route.quality_modes," in sql
    assert "catalog_quality_modes_mismatch" in sql


def test_edge_accepts_the_engine_and_forwards_it_untouched() -> None:
    edge = text(EDGE)

    parser = edge.split("function readGenerationStrategyBindPayload", 1)[1].split(
        "function readGenerationStrategyMediaProbePayload", 1
    )[0]
    # Два набора ключей, а не один необязательный: форма запроса проверяется
    # точным совпадением.
    assert "const withEngine = isRecord(value) && Object.hasOwn(value, \"engine\")" in parser
    assert "readGenerationStrategyEngineChoice(" in parser
    assert "if (withEngine && engine === null) return null;" in parser

    choice = edge.split("function readGenerationStrategyEngineChoice", 1)[1].split(
        "function readGenerationStrategyBindPayload", 1
    )[0]
    assert 'hasExactKeys(value, ["provider", "model_key"] as const)' in choice
    assert "isKnownStrategyProvider(provider)" in choice

    handler = edge.split(
        "  const strategyBindPayload = readGenerationStrategyBindPayload(body);", 1
    )[1].split("  const strategyMediaProbePayload =", 1)[0]
    # Ключ уходит в SQL только когда он есть: база отличает «не выбран» от
    # «выбран» по наличию поля.
    assert "strategyBindPayload.engine === undefined" in handler
    assert "engine: strategyBindPayload.engine" in handler

    # Каталог пропускает новые поля маршрута, но не пропускает неизвестные.
    routes = edge.split("function generationStrategyProviderRoutesValid", 1)[1].split(
        "function readGenerationStrategyCatalogPolicy", 1
    )[0]
    assert "generationStrategyRouteDurationsValid(route)" in routes
    assert "generationStrategyRouteQualityModesValid(route)" in routes
    assert '"quality_modes",' in routes


def test_dispatch_and_poll_agree_on_one_model_from_the_signed_receipt() -> None:
    edge = text(EDGE)

    dispatch = edge.split("const continueGenerationStrategyClaim = async (", 1)[1].split(
        "const generationStrategyOutputObjectName = async (", 1
    )[0]
    # Отправка спрашивает маршрут там же, где его потом спросит опрос.
    assert "loadGenerationStrategyJobRoute(" in dispatch
    assert "dispatchRoute.provider !== routeProvider" in dispatch
    assert "dispatchRoute.modelKey," in dispatch

    builder = edge.split("export function buildGenerationStrategyProviderRequest", 1)[
        1
    ].split("function readGenerationStrategyDispatchAttempt", 1)[0]
    # Форма запроса — свойство модели: у одного провайдера их уже две. Чистая
    # компиляция теперь живёт рядом с adapter, чтобы её можно было исполнить в
    # contract-тесте вместе с фактическим provider body.
    adapters = text(ADAPTERS)
    assert "buildFalProductSwapSelection({" in builder
    assert 'falStrategyRequestShape("product_swap", input.modelKey)' in adapters
    # Форм тел стало больше двух (23.08.2026): диспетчер по форме — один
    # switch, у каждой формы своё указание и свой сборщик тела.
    assert "function buildFalProductSwapBody(shape, selection, assets)" in adapters
    assert 'case "kling_prompt_edit":' in adapters
    assert 'case "happy_horse_video_edit":' in adapters
    assert 'case "seedance_reference_edit":' in adapters
    assert 'case "minimax_reference_regenerate":' in adapters
    assert "@Video1" in adapters
    assert "@Image1" in adapters or '"@Image"' in adapters
    # Чистый prompt compiler получает только подписанную сервером категорию и
    # productInfo; свободный комментарий не может напрямую назначить область.
    assert "buildFalProductSwapSelection({" in builder
    assert "productCategory: routeProductCategory" in builder
    assert "productInfo: context.productInfo" in builder


def test_kling_request_body_matches_the_provider_schema() -> None:
    adapters = text(ADAPTERS)
    catalog = text(CATALOG)

    kling = adapters.split("function buildFalKlingProductSwap", 1)[1].split(
        "export function buildFalRecipeRequest", 1
    )[0]
    # Схема модели: описание, исходное видео, до четырёх изображений, звук.
    assert "prompt: selection.promptText" in kling
    assert "video_url: source.uri" in kling
    assert "image_urls: images" in kling
    assert "keep_audio: true" in kling
    assert "FAL_KLING_MAX_IMAGES" in kling

    # Модель приходит снаружи и проверяется на исполнимость.
    request = adapters.split("export function buildFalRecipeRequest", 1)[1].split(
        "export function buildRunwayRecipeRequest", 1
    )[0]
    assert "modelKey," in request
    assert 'fail("fal_model_unsupported")' in request
    assert "endpointPath: modelKey," in request

    assert "export function falStrategyRequestShape(recipe, modelKey)" in catalog
    assert '"pika_region_swap"' in catalog
    assert '"kling_prompt_edit"' in catalog


def test_browser_carries_the_choice_without_inventing_one() -> None:
    runtime = text(RUNTIME)
    api = text(API)
    app = text(APP)
    guided = text(GUIDED)
    intake = text(INTAKE)

    # Контекст с движком и без него — оба правильные; движок входит в отпечаток,
    # поэтому смена движка считается другой привязкой, а не подменой исполнителя
    # у уже подписанной.
    assert "const CONTEXT_KEYS_WITH_ENGINE" in runtime
    assert "normalizeRuntimeEngine(" in runtime
    assert "context.engine === undefined ? {} : { engine: context.engine }" in runtime

    # Клиентский контракт: отдельный набор ключей и проверка формы движка.
    assert "strategy_bind_engine: Object.freeze([" in api
    assert 'hasExactObjectKeys(request.engine, ["provider", "model_key"])' in api

    # Источник выбора один — поле формы, которое видит человек.
    assert "getStrategyEngineChoice?.()" in app
    assert "getStrategyEngineChoice(form = runtime.form)" in guided
    assert "generation_intake_engine" in guided
    assert "generation_intake_engine" in intake

    # Чужое, пустое или выключенное значение превращается в «движок не выбран»,
    # а не уходит в привязку: сервер посчитает действующий маршрут, как считал
    # до каскада, вместо отказа на ровном месте.
    choice = guided.split("getStrategyEngineChoice(form = runtime.form)", 1)[1].split(
        "refreshStrategyAssets(", 1
    )[0]
    assert "route?.enabled === true" in choice
    assert "return null" in choice


def test_engine_change_revokes_cached_price_and_runtime_without_rewriting_spec() -> None:
    app = text(APP)

    activity = app.split("function handleFormActivity(event)", 1)[1].split(
        "function handleGenerationGuidedStepCommitted", 1
    )[0]
    readiness = app.split(
        "function syncGenerationStrategySingleFormReadiness", 1
    )[1].split("function syncGenerationStrategyFormReadiness", 1)[0]
    paid_lock = app.split("function syncGenerationStrategyPaidControlLock", 1)[
        1
    ].split("function syncUnsupportedGenerationStrategyFormReadiness", 1)[0]

    # The compact cascade uses generation_intake_engine, not the broader
    # generation_strategy_* prefix. It must enter the same invalidation path,
    # while preserving the already approved prompt/spec: only binding, receipt
    # and price depend on the chosen engine.
    assert 'event.target.name === "generation_intake_engine"' in activity
    assert "strategyEngineChanged" in activity
    assert "clearSpecs: !strategyEngineChanged" in activity
    assert 'form.dataset.generationStrategyConfirmationReady = "false"' in activity
    assert "state.generationStrategyRuntimes.clear()" in app

    # Readiness also checks the live fingerprint. Even if a future caller
    # changes the field without the normal UI event, an old receipt cannot make
    # the paid confirmation ready for a different engine.
    assert "currentRuntimeFingerprint" in readiness
    assert "runtimeFingerprintCurrent" in readiness
    assert (
        "runtimeState.fingerprint === currentRuntimeFingerprint.fingerprint"
        in readiness
    )
    assert "const receiptFresh = runtimeFingerprintCurrent" in readiness

    # Once paid authority exists, the visible cascade is immutable just like
    # the other signed inputs.
    for control in (
        "generation_intake_generator",
        "generation_intake_quality",
        "generation_intake_duration",
    ):
        # Префикс, а не точное имя: радиокнопки «Дуэта» носят суффикс панели.
        assert f'[name^="{control}"]' in paid_lock


def test_per_second_route_reserves_the_duration_it_will_actually_pay() -> None:
    """Ставка за секунду обязана считаться по длине исходника, а не по выбору.

    Правка видео отдаёт ролик длиной с вход: параметра длительности у таких
    моделей нет вовсе. Пять выбранных секунд на двенадцатисекундном исходнике
    означали бы резерв 85 центов против счёта на 204 — разницу не вернёт никто,
    потому что снимок цены внутренне непротиворечив, он просто описывает не тот
    ролик.
    """
    sql = text(SOURCE_DURATION)

    assert sql.startswith("begin;\n")
    assert sql.rstrip().endswith("commit;")

    # Свойство маршрута: кто задаёт длительность. Значение по умолчанию
    # описывает прежнее поведение, поэтому ни одна существующая строка не
    # меняется молча.
    assert "duration_source text not null" in sql
    assert "default 'operator_choice'" in sql
    assert "check (duration_source in ('operator_choice', 'source_video'))" in sql

    # Требование включается там, где секунда стоит денег, и опирается на
    # СЕРВЕРНОЕ измерение, а не на заявленную длительность.
    assert "route_price_kind = ''usd_minor_per_second''" in sql
    assert "generation_strategy_media_durations" in sql
    assert "ceil(measured_seconds)::integer" in sql
    assert "generation_strategy_source_duration_mismatch" in sql

    # Порядок в цепочке проверяется, а не предполагается: патчить нечего, пока
    # привязка не научена принимать движок.
    assert "engine_choice_migration_missing" in sql

    # Деньги не сдвинулись, и свойство проставлено ровно правке видео.
    assert "active_route_drifted" in sql
    assert "duration_source_drifted" in sql

    # Отказ доезжает до человека понятным: 422 и текст, а не общий 503.
    edge = text(EDGE)
    codes = edge.split(
        "const GENERATION_STRATEGY_BIND_VALIDATION_ERROR_CODES = new Set([", 1
    )[1].split("]);", 1)[0]
    assert '"generation_strategy_source_duration_mismatch"' in codes
    assert "generation_strategy_source_duration_mismatch:" in text(API)

    # Экран показывает серверный факт, а не свой замер, и не даёт его выбирать.
    intake = text(INTAKE)
    assert "function verifiedSourceDurationSeconds(form)" in intake
    assert "getStrategySourcePickerProjection?.(form)" in intake
    assert "Math.ceil(seconds)" in intake
    assert 'selectedEngine.durationSource === "source_video"' in intake
    assert "disabled: !control || control.disabled || sourceSeconds !== null" in intake


def test_prompt_only_runway_route_requires_exact_source_duration_fail_closed() -> None:
    """Aleph cannot accept duration, so its signed price must follow the MP4."""
    sql = text(RUNWAY_SOURCE_DURATION)

    assert sql.startswith("begin;\n")
    assert sql.rstrip().endswith("commit;")
    assert len(parse_sql(sql)) >= 20
    do_bodies = re.findall(
        r"do \$([a-z0-9_]+)\$(.*?)\$\1\$;",
        sql,
        flags=re.DOTALL | re.IGNORECASE,
    )
    assert {name for name, _body in do_bodies} == {
        "runway_product_swap_route_exact",
        "runway_source_duration_bind",
        "runway_source_duration_claim",
        "runway_source_duration_dispatch",
        "source_duration_semantic_proof",
        "runway_source_duration_verify",
    }
    for _name, body in do_bodies:
        parse_plpgsql(
            "CREATE FUNCTION migration_probe() RETURNS void AS $outer$"
            f"{body}"
            "$outer$ LANGUAGE plpgsql;"
        )

    def text_constant(name: str) -> str:
        return sql.split(f"{name} constant text := $f$", 1)[1].split(
            "$f$;", 1
        )[0]

    # DO-body parsing does not parse the generated function fragments stored
    # in text constants, so compile those independently as nested PL/pgSQL.
    bind_generated = text_constant("block_replacement")
    parse_plpgsql(
        "CREATE FUNCTION bind_probe() RETURNS void AS $outer$ BEGIN\n"
        f"{bind_generated}\n"
        "END; $outer$ LANGUAGE plpgsql;"
    )
    generated_declarations = (
        " DECLARE route_duration_source text; source_media_id_value uuid; "
        "measured_seconds numeric; receipt_row record; "
        "organization_id_value uuid; asset_context_value jsonb; "
        "strategy_duration_value integer; expected_asset_count_value integer; "
        "pre_dispatch_failure_code_value text;"
    )
    claim_generated = text_constant("claim_replacement").split(
        "  claim_hash_value :=", 1
    )[0]
    dispatch_generated = text_constant("guard_replacement")
    for name, generated in (
        ("claim", claim_generated),
        ("dispatch", dispatch_generated),
    ):
        parse_plpgsql(
            f"CREATE FUNCTION {name}_probe() RETURNS void AS $outer$"
            f"{generated_declarations} BEGIN\n{generated}\n"
            "END; $outer$ LANGUAGE plpgsql;"
        )

    # Only the Product Swap Aleph route changes. All legacy route properties
    # are snapshotted and compared after the exact-key update.
    assert "contentengine.runway_source_duration_legacy_before" in sql
    assert "legacy_route_duration_drifted" in sql
    assert "lock table content_factory.generation_strategy_provider_routes" in sql
    assert "in share row exclusive mode" in sql
    assert "route.strategy_id = 'viral_product_swap'" in sql
    assert "route.provider = 'runway'" in sql
    assert "route.model_key = 'aleph2'" in sql
    assert "route.provider_path = '/v1/video_to_video'" in sql
    assert "route.poll_kind = 'runway_task'" in sql
    assert "route.enabled = true" in sql
    assert "route.verified_rate_at is not null" in sql
    assert "route.price_rate_minor is null" in sql
    assert "set duration_source = 'source_video'" in sql
    assert "runway_product_swap_route_not_exact" in sql

    # The bind gate now follows the route capability instead of a pricing
    # accident. This covers per-run Pika, per-second Kling, and credit-tier
    # Runway while leaving operator-controlled legacy routes unchanged.
    assert "generation_strategy_source_duration_matches(" in sql
    assert "select route.duration_source into route_duration_source" in sql
    assert "if route_duration_source = 'source_video' then" in sql
    assert "generation_strategy_source_duration_mismatch" in sql
    assert "block_replacement" in sql
    assert sql.count("strategy_id = 'viral_product_swap'") >= 4
    # Three executable guards, three replay guards and three final verifiers.
    assert sql.count("and route_duration_source is null") == 9
    assert "source_duration_v2_null_guard_missing" in sql
    assert "source_duration_claim_v2_null_guard_missing" in sql
    assert "source_duration_dispatch_v2_null_guard_missing" in sql

    # Engine is optional for legacy callers. Product Swap without it resolves
    # the one enabled recommended registry route and cannot skip measurement;
    # strategies without registry routes retain their legacy duration mode.
    bind_patch = sql.split("do $runway_source_duration_bind$", 1)[1].split(
        "$runway_source_duration_bind$;", 1
    )[0]
    assert "if p_payload ? 'engine' then" in bind_patch
    assert "else\n      select route.duration_source" in bind_patch
    assert "route.recommended" in bind_patch
    assert "strategy with no registry route keeps its legacy" in bind_patch

    # Cutover is closed twice after bind: an old readiness receipt is rejected
    # at claim, and an already-created queued claim is terminalized by the last
    # DB authorization before provider POST. Existing claim replay stays before
    # the inserted claim_hash anchor and is not duplicated.
    assert "source_duration_claim_v2" in sql
    assert "generation_job_failure_proven_unpaid" in sql
    assert "public.system_claim_generation_strategy_start(jsonb)" in sql
    assert "claim_hash_value := content_factory_private.json_hash" in sql
    assert "source_duration_dispatch_v2: final authority before provider POST" in sql
    assert "public.system_mark_generation_strategy_dispatch_attempt(jsonb)" in sql
    assert "pre_dispatch_failure_code_value := 'input_asset_not_current'" in sql
    assert "where item.value ->> 'role' = 'source_video'" in sql
    assert "receipt_row.strategy_id = 'viral_product_swap'" in sql

    # The migration executes semantic self-tests: exact ceil matches pass,
    # mismatches/missing probes fail, and legacy operator_choice remains valid.
    assert "when 'operator_choice' then true" in sql
    assert "else false" in sql
    for proof in (
        "source_duration_exact_match_broken",
        "source_duration_ceil_match_broken",
        "source_duration_mismatch_not_closed",
        "source_duration_missing_probe_not_closed",
        "operator_choice_legacy_broken",
    ):
        assert proof in sql

    # Pricing authority is not changed by the duration-source repair.
    assert "RUNWAY_PRODUCT_SWAP_12S_720P_SILENT_USD_5.00" in sql
    assert "RUNWAY_PRODUCT_SWAP_15S_720P_SILENT_USD_6.08" in sql
    assert "{12s,estimated_cost_minor}' is distinct from '500'" in sql
    assert "{15s,estimated_cost_minor}' is distinct from '608'" in sql
    assert "runway_route_price_drifted" in sql

    # The executable provider adapter contract pins why the route must use the
    # source duration: Aleph's exact body has no duration field.
    adapters = text(ADAPTERS)
    product_swap = adapters.split("function buildProductSwap", 1)[1].split(
        "function buildProductAd", 1
    )[0]
    assert "videoUri: source.uri" in product_swap
    assert "promptText: selection.promptText" in product_swap
    assert "targetAspectRatio: PRODUCT_SWAP_ALEPH_RATIO" in product_swap
    assert "duration:" not in product_swap
