/*
 * Canonical generation strategy contract.
 *
 * This module is intentionally pure: it does not read environment variables,
 * touch storage, call providers or infer execution readiness. The browser may
 * consume publicGenerationStrategyCatalog(); server code must additionally use
 * validateGenerationStrategyForExecution() with an exact, server-owned runtime
 * capability map before a provider request can be built.
 *
 * Runway recipe and pricing references, verified 2026-08-14:
 * - https://docs.dev.runwayml.com/recipes/product-ugc/
 * - https://docs.dev.runwayml.com/recipes/product-swap/
 * - https://docs.dev.runwayml.com/recipes/product-ad/
 * - https://docs.dev.runwayml.com/guides/pricing/
 */

export const GENERATION_STRATEGY_CATALOG_VERSION = "2026-08-14.v1";
export const RUNWAY_RECIPE_VERSION = "2026-06";
export const RUNWAY_RECIPE_PRICING_VERSION =
  "runway-recipe-credits-2026-08-14.v1";
export const FAL_RECIPE_PRICING_VERSION = "fal-usd-per-run-2026-08-18.v1";
// Посекундная ставка не может жить под именем «за ролик»: имя входит в
// хеш-подпись строки привязки, и совпадение имён означало бы подпись,
// утверждающую не то, что было посчитано.
export const FAL_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-2026-08-18.v1";
// HeyGen считает готовое видео ведущего посекундно. Имя версии называет СПОСОБ
// счёта, а не только провайдера, и входит в хеш-подпись строки подтверждения —
// переиспользовать имя fal нельзя: подпись утверждала бы не тот способ, которым
// посчитаны деньги.
export const HEYGEN_PER_SECOND_PRICING_VERSION =
  "heygen-usd-per-second-2026-08-22.v1";
// Движки «Копии», заведённые 23.08.2026 отдельными строками реестра. У каждого
// СВОЯ версия прайса: пара (provider, pricing_version) — это подпись маршрута
// среди включённых строк (частичный индекс generation_strategy_provider_routes_
// signature_key), по ней же опрос восстанавливает модель оплаченной задачи.
// Два включённых движка fal с одной версией прайса неразличимы для опроса —
// поэтому имя версии называет и способ счёта, и сам движок.
export const FAL_KLING_STANDARD_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-kling-standard-2026-08-23.v1";
export const FAL_HAPPY_HORSE_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-happy-horse-2026-08-23.v1";
export const FAL_SEEDANCE_2_5_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-bytedance-2-5-2026-08-23.v1";
export const FAL_MINIMAX_H3_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-minimax-h3-2026-08-23.v1";
// Движки «Создания» (ролик с нуля по фото товара и описанию механики), тот же
// день. MiniMax и Seedance повторяют версии «Копии»: подпись уникальна внутри
// стратегии, а способ счёта у модели один.
export const FAL_GROK_IMAGINE_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-grok-imagine-2026-08-23.v1";
export const FAL_HAPPY_HORSE_REFERENCE_PER_SECOND_PRICING_VERSION =
  "fal-usd-per-second-happy-horse-reference-2026-08-23.v1";
// «Создание» на Runway (Gen-4 Turbo, 29.08.2026). Официальный API считает
// 5 кредитов за секунду (25/50 кредитов за 5/10 с, 1 кредит = $0.01) — это
// ПОСЕКУНДНАЯ ставка, а не ступени кредитов рецепта. Имя версии называет
// способ счёта и движок: подпись (provider, pricing_version) обязана
// отличать gen4_turbo от aleph2 с его runway-recipe-credits.
export const RUNWAY_GEN4_TURBO_PER_SECOND_PRICING_VERSION =
  "runway-usd-per-second-gen4-turbo-2026-08-29.v1";

// Версия прайса — свойство маршрута, а не константа стратегии: у Runway она
// считается ступенями кредитов, у fal — фиксированной ценой за ролик либо
// ставкой за секунду. Набор повторяет ограничение базы на колонку
// pricing_version, поэтому расшириться он может только вместе с ней.
export const GENERATION_STRATEGY_PRICING_VERSIONS = Object.freeze([
  RUNWAY_RECIPE_PRICING_VERSION,
  FAL_RECIPE_PRICING_VERSION,
  FAL_PER_SECOND_PRICING_VERSION,
  HEYGEN_PER_SECOND_PRICING_VERSION,
  FAL_KLING_STANDARD_PER_SECOND_PRICING_VERSION,
  FAL_HAPPY_HORSE_PER_SECOND_PRICING_VERSION,
  FAL_SEEDANCE_2_5_PER_SECOND_PRICING_VERSION,
  FAL_MINIMAX_H3_PER_SECOND_PRICING_VERSION,
  FAL_GROK_IMAGINE_PER_SECOND_PRICING_VERSION,
  FAL_HAPPY_HORSE_REFERENCE_PER_SECOND_PRICING_VERSION,
  RUNWAY_GEN4_TURBO_PER_SECOND_PRICING_VERSION,
]);

export function isKnownStrategyPricingVersion(value) {
  return typeof value === "string" &&
    GENERATION_STRATEGY_PRICING_VERSIONS.includes(value);
}

// Пределы длительности ролика по стратегиям, в целых секундах.
//
// «Дуэт» комментирует чужой ролик целиком, и его длина задана исходником, а не
// вкусом оператора: типичный рекламный ролик длиннее пятнадцати секунд.
// Прежний общий потолок в пятнадцать секунд отвергал бы такой запуск ПОСЛЕ
// резерва денег — то есть оставлял бы повисшую бронь.
//
// Числа обязаны совпадать со строками реестра маршрутов
// (content_factory.generation_strategy_provider_routes: min_duration_seconds,
// max_duration_seconds). Это второе место, где они записаны, и разойтись они
// могут только молча — чистый модуль в базу заглянуть не может. Шаг 6 работы
// превращает их в параметр маршрута вместо второй записи.
export const GENERATION_STRATEGY_DURATION_BOUNDS = Object.freeze({
  viral_avatar_ugc: Object.freeze({ minimum: 3, maximum: 60 }),
  viral_product_swap: Object.freeze({ minimum: 4, maximum: 15 }),
  viral_rebuild: Object.freeze({ minimum: 4, maximum: 15 }),
});

// Незнакомая стратегия не получает предела по умолчанию: отсутствие ответа
// здесь означает отказ у вызывающего, а не «пятнадцать, наверное».
export function generationStrategyDurationBounds(strategyId) {
  if (typeof strategyId !== "string") return null;
  return Object.prototype.hasOwnProperty.call(
      GENERATION_STRATEGY_DURATION_BOUNDS,
      strategyId,
    )
    ? GENERATION_STRATEGY_DURATION_BOUNDS[strategyId]
    : null;
}

// Провайдеры, которым разрешено исполнять стратегию. Тот же набор стоит в
// ограничении базы на колонку provider таблицы квитанций готовности.
export const GENERATION_STRATEGY_PROVIDERS = Object.freeze([
  "runway",
  "fal",
  // Ведущий для «Дуэта». Отдельный ключ и отдельный кошелёк — решение владельца
  // 22.08.2026. Взят ради ПОСТОЯНСТВА личности: аватар создаётся один раз и
  // получает avatar_id на стороне провайдера, поэтому один и тот же человек
  // повторяется во всех роликах проекта по устройству, а не по совпадению.
  "heygen",
]);

export function isKnownStrategyProvider(value) {
  return typeof value === "string" &&
    GENERATION_STRATEGY_PROVIDERS.includes(value);
}

// Модели fal, которые код умеет ИСПОЛНЯТЬ, и форма запроса каждой. У очереди
// fal модель и есть путь: по ней собирается адрес отправки, по ней же — адреса
// статуса и результата. Поэтому модель обязана быть одной и той же на всём
// контуре одного запуска: разойдись адрес отправки с адресом опроса, задача
// ушла бы к одной модели, а забиралась бы у другой — опрос не завершился бы
// никогда, а зарезервированные деньги остались бы висеть.
//
// Это НЕ список того, что можно продавать: продаёт реестр маршрутов в базе.
// Это список того, что мы умеем собрать и разобрать. Реестр хранит ту же
// строку в model_key и provider_path и сверяется с этой картой перед отправкой
// и перед опросом: маршрут, которого код исполнять не умеет, обязан быть
// отказом, а не догадкой — иначе включённая в базе строка молча увела бы
// оплаченный запуск в никуда.
//
// Значение — форма запроса, а не признак «разрешено». Две модели одного
// провайдера просят принципиально разного: Pika меняет НАЗВАННУЮ область по
// фото, Kling правит видео описанием и ссылается на вход как @Video1/@Image1.
// Идентификатор модели у очереди fal — это одновременно адрес отправки, адрес
// статуса и адрес результата. Он обязан быть одной и той же строкой на всём
// контуре запуска, поэтому имя живёт в одном месте, а карты форм на него
// ссылаются. Два рецепта используют одни и те же модели — операция у них одна
// (правка готового видео), различаются только роли входа.
export const FAL_PIKA_SWAPS_MODEL = "fal-ai/pika/v2/pikaswaps";
export const FAL_KLING_O3_PRO_EDIT_MODEL =
  "fal-ai/kling-video/o3/pro/video-to-video/edit";
// Движки «Копии», заведённые 23.08.2026. Схемы входа сверены по OpenAPI
// очереди fal (fal.ai/api/openapi/queue/openapi.json?endpoint_id=…), цены — по
// страницам моделей; всё записано в строках реестра (миграция 202608230020).
//
// Kling O3 Standard — та же форма тела, что у Pro, ставка ниже ($0.126/с).
export const FAL_KLING_O3_STANDARD_EDIT_MODEL =
  "fal-ai/kling-video/o3/standard/video-to-video/edit";
// Happy Horse video-edit — правка готового ролика по описанию с опорой на
// фото товара (@Image1…@Image5), результат той же длины, что вход (потолок
// 15 с), исходный звук сохраняется. $0.14/с при 720p.
export const FAL_HAPPY_HORSE_VIDEO_EDIT_MODEL = "alibaba/happy-horse/video-edit";
// Seedance 2.5 reference-to-video — по заявлению страницы модели правит ролик,
// сохраняя движение и камеру (@Video1, @Image1…). Дорогая: цена по токенам
// считает и входное, и выходное видео, ≈$0.55/с при 720p — см. реестр.
export const FAL_SEEDANCE_2_5_REFERENCE_MODEL =
  "bytedance/seedance-2.5/reference-to-video";
// MiniMax H3 reference-to-video — ПЕРЕСБОРКА: исходник служит референсом
// движения (Video 1), товар берётся с фото (Image 1…). Длительность выбирает
// оператор (5–15 с), $0.06/с при 768P. Для «Копии» это второй эшелон, для
// «Создания» — кандидат в основные.
export const FAL_MINIMAX_H3_REFERENCE_MODEL = "minimax/h3/reference-to-video";
// Движки «Создания»: ролик собирается с нуля по фото товара и описанию
// механики референса — сам ролик-референс провайдеру не уходит (каталог:
// forwarded_to_provider = false). Поэтому здесь только модели «фото → видео».
// Grok Imagine — до 7 фото (@Image1…), 1–10 с, 480p/720p, $0.07/с при 720p.
export const FAL_GROK_IMAGINE_REFERENCE_MODEL =
  "xai/grok-imagine-video/reference-to-video";
// Happy Horse reference-to-video — 1–9 фото (character1…), 3–15 с, $0.14/с
// при 720p. Не путать с video-edit той же модели: там вход — видео.
export const FAL_HAPPY_HORSE_REFERENCE_MODEL =
  "alibaba/happy-horse/reference-to-video";
// Kling O3 Standard image-to-video — «фото → видео» для «Создания»: стартовый
// кадр задаёт ОДНО фото товара, сцену описывает prompt. 3–15 с; $0.084/с без
// звука и $0.112/с со звуком (fal.ai/models/fal-ai/kling-video/o3/standard/
// image-to-video, 26.08.2026). Кадр наследует пропорции стартового фото —
// параметра aspect_ratio у модели нет.
export const FAL_KLING_O3_STANDARD_I2V_MODEL =
  "fal-ai/kling-video/o3/standard/image-to-video";

export const FAL_STRATEGY_MODEL_SHAPES = Object.freeze({
  product_swap: Object.freeze({
    [FAL_PIKA_SWAPS_MODEL]: "pika_region_swap",
    [FAL_KLING_O3_PRO_EDIT_MODEL]: "kling_prompt_edit",
    [FAL_KLING_O3_STANDARD_EDIT_MODEL]: "kling_prompt_edit",
    [FAL_HAPPY_HORSE_VIDEO_EDIT_MODEL]: "happy_horse_video_edit",
    [FAL_SEEDANCE_2_5_REFERENCE_MODEL]: "seedance_reference_edit",
    [FAL_MINIMAX_H3_REFERENCE_MODEL]: "minimax_reference_regenerate",
  }),
  // «Аватар» с 21.08.2026 — такая же правка готового ролика, только заменяется
  // человек, а не товар. Формы запроса те же самые: Pika меняет НАЗВАННУЮ
  // область по одному фото, Kling правит описанием и ссылается на вход как
  // @Video1/@Image1. Модели те же, потому что операция та же.
  //
  // ВАЖНО про режим «Описание аватара»: у Pika поле image_url обязательно, а у
  // Kling ссылки @ImageN в указании должны на что-то указывать. Значит без
  // фотографии обе модели неисполнимы, и описание остаётся маршруту Runway
  // Aleph, который принимает только текст. Это ограничение моделей, и экран
  // обязан его показывать, а не выяснять отказом после резерва.
  product_ugc: Object.freeze({
    [FAL_PIKA_SWAPS_MODEL]: "pika_region_swap",
    [FAL_KLING_O3_PRO_EDIT_MODEL]: "kling_prompt_edit",
  }),
  // «Создание»: те же модели MiniMax и Seedance, но в форме «только фото» —
  // без референсного видео, длительность и кадр выбирает оператор.
  product_ad: Object.freeze({
    [FAL_MINIMAX_H3_REFERENCE_MODEL]: "minimax_images_regenerate",
    [FAL_KLING_O3_STANDARD_I2V_MODEL]: "kling_image_regenerate",
    [FAL_GROK_IMAGINE_REFERENCE_MODEL]: "grok_images_regenerate",
    [FAL_HAPPY_HORSE_REFERENCE_MODEL]: "happy_horse_images_regenerate",
    [FAL_SEEDANCE_2_5_REFERENCE_MODEL]: "seedance_images_regenerate",
  }),
});

// Сколько изображений товара принимает каждая форма тела. Это пределы самих
// моделей (схемы входа fal), а не наша осторожность: у Pika ровно одно фото,
// у Kling — четыре вместе с элементами, у Happy Horse — пять, у MiniMax
// первые пять бесплатны (дальше $0.08 за фото), у Seedance лимит в тридцать
// упирается в длину указания — каждое фото надо назвать по имени @ImageN.
export const FAL_SHAPE_IMAGE_LIMITS = Object.freeze({
  pika_region_swap: 1,
  kling_prompt_edit: 4,
  happy_horse_video_edit: 5,
  seedance_reference_edit: 6,
  minimax_reference_regenerate: 5,
  // «Создание»: Grok берёт до 7 (и берёт $0.002 за каждое), Happy Horse — до
  // 9, но в указании каждое фото называется по имени, поэтому пять.
  minimax_images_regenerate: 5,
  // Kling image-to-video принимает ровно один стартовый кадр.
  kling_image_regenerate: 1,
  grok_images_regenerate: 5,
  happy_horse_images_regenerate: 5,
  seedance_images_regenerate: 6,
});

// Как форма называет вход в указании. Kling, Happy Horse и Seedance ссылаются
// на изображения как @Image1, а на видео — как @Video1 (у Happy Horse видео
// одно и без имени); MiniMax — «Image 1», «Video 1», без @; Pika область
// называется словами, ссылок нет.
export const FAL_SHAPE_PROMPT_STYLES = Object.freeze({
  pika_region_swap: "region",
  kling_prompt_edit: "at_refs",
  happy_horse_video_edit: "at_refs",
  seedance_reference_edit: "at_refs",
  minimax_reference_regenerate: "named_refs",
  minimax_images_regenerate: "named_refs",
  // Kling i2v не знает @-ссылок: указание говорит о «стартовом кадре».
  kling_image_regenerate: "start_frame",
  grok_images_regenerate: "at_refs",
  // Happy Horse reference-to-video называет фото «character1», «character2»…
  happy_horse_images_regenerate: "character_refs",
  seedance_images_regenerate: "at_refs",
});

// Форма запроса модели или null, если такой модели этот код не исполняет.
export function falStrategyRequestShape(recipe, modelKey) {
  if (typeof recipe !== "string" || typeof modelKey !== "string") return null;
  const shapes = FAL_STRATEGY_MODEL_SHAPES[recipe];
  if (!shapes || !Object.hasOwn(shapes, modelKey)) return null;
  return shapes[modelKey];
}

export const GENERATION_STRATEGY_IDS = Object.freeze({
  avatarUgc: "viral_avatar_ugc",
  productSwap: "viral_product_swap",
  rebuild: "viral_rebuild",
});

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ZERO_UUID = "00000000-0000-0000-0000-000000000000";
const TOP_LEVEL_SELECTION_FIELDS = Object.freeze([
  "version",
  "strategy_id",
  "recipe_version",
  "duration_seconds",
  "ratio",
  "resolution",
  "audio",
  "assets",
  "attestations",
]);
const EXECUTION_CAPABILITY_FIELDS = Object.freeze([
  "enabled",
  "catalog_version",
  "strategy_id",
  "provider",
  "recipe",
  "recipe_version",
  "provider_path",
  "pricing_version",
]);

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) {
    return value;
  }
  for (const child of Object.values(value)) deepFreeze(child);
  return Object.freeze(value);
}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function failure(code, field, message) {
  return Object.freeze({ ok: false, code, field, message });
}

function success(value = {}) {
  return deepFreeze({ ok: true, ...value });
}

function assetRole(value) {
  return deepFreeze({
    allowed_views: [],
    duration_required: false,
    min_duration_seconds: null,
    max_duration_seconds: null,
    ...value,
  });
}

function attestation(id, public_label) {
  return Object.freeze({ id, public_label });
}

function pricing(base_720p, base_1080p) {
  return deepFreeze({
    kind: "base_at_4_seconds_plus_per_additional_second",
    unit: "runway_credit",
    usd_cents_per_credit: 1,
    base_duration_seconds: 4,
    tiers: {
      "720p": {
        base_credits: base_720p,
        additional_credits_per_second: 36,
      },
      "1080p": {
        base_credits: base_1080p,
        additional_credits_per_second: 40,
      },
    },
  });
}

const COMMON_ATTESTATIONS = Object.freeze([
  attestation(
    "source_media_rights_confirmed",
    "У меня есть права использовать исходный ролик как референс.",
  ),
  attestation(
    "transformative_use_confirmed",
    "Права на исходный ролик разрешают его переработку для нового рекламного материала.",
  ),
  attestation(
    "product_assets_rights_confirmed",
    "У меня есть права использовать изображения товара.",
  ),
  attestation(
    "depicted_people_consent_confirmed",
    "Для всех узнаваемых людей есть согласие на такое использование, либо людей в исходниках нет.",
  ),
]);

const RAW_CATALOG = [
  {
    strategy_id: GENERATION_STRATEGY_IDS.avatarUgc,
    public_label: "Добавить ведущего, комментирующего ролик",
    public_summary:
      "Оставляет исходный ролик нетронутым и врезает в кадр вашего ведущего, который проговаривает подготовленный текст о происходящем.",
    // Решение владельца 22.08.2026: это ДУЭТ, а не замена человека в кадре.
    // Исходный ролик НЕ переписывается вовсе — он остаётся подложкой, а
    // провайдер делает только говорящего ведущего. Соединение происходит у нас,
    // локальным ffmpeg, поэтому исходник провайдеру не уходит.
    //
    // Ранняя редакция (21.08.2026) считала стратегию правкой ролика через
    // video-to-video и отправляла исходник провайдеру. Это было прочтением
    // «аватара» как замены человека, и владелец его отменил.
    transformation_kind: "duet_presenter_overlay_preserve_source",
    source_reference_mode: "local_underlay_not_provider_input",
    preservation_notice:
      "Исходный ролик не изменяется ни одним кадром: ведущий врезается поверх него отдельным слоем. Ведущий — синтезированная говорящая голова, и её мимика не повторяет живого человека.",
    human_review_required: true,
    provider: "runway",
    recipe: "product_ugc",
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    // У «Дуэта» РОВНО ОДИН ассет, и это не упрощение ради простоты.
    //
    // Ведущего задаёт не фотография, а запись в библиотеке ведущих проекта:
    // личность закреплена у провайдера идентификатором avatar_id. Фотография
    // используется ОДИН раз, при заведении ведущего, и к запуску отношения не
    // имеет — в теле запроса к HeyGen медиа нет вовсе.
    //
    // Роль avatar_image здесь была наследством прежнего понимания, когда
    // «Аватар» считался заменой человека в кадре и ездил на Kling с ракурсами.
    // Под дуэт она не значит ничего, и держать её значило бы обещать выбор,
    // которого нет.
    asset_roles: [
      assetRole({
        role: "source_video",
        public_label: "Ролик, который комментируем",
        media_kind: "video",
        min_count: 1,
        max_count: 1,
        // Провайдеру исходник НЕ уходит: он делает только говорящего ведущего.
        // Ролик остаётся у нас подложкой для сборки и источником длительности,
        // по которой считается посекундная цена.
        forwarded_to_provider: false,
        provider_field: null,
        duration_required: true,
        min_duration_seconds: 1.8,
        max_duration_seconds: 60,
      }),
    ],
    required_attestations: [
      ...COMMON_ATTESTATIONS,
      attestation(
        "avatar_likeness_consent_confirmed",
        "Есть явное согласие на использование внешности выбранного аватара.",
      ),
    ],
    output_rules: {
      // 3–60 секунд, как в строке реестра маршрута heygen и как разрешён сам
      // исходник выше. Прежние 4–15 были остатком от общей формы и делали
      // заявленный маршрут недостижимым: панель принимала ролик на 24 секунды,
      // а выбрать длительность было нельзя ни одну — пересечение окон давало
      // пустой список.
      duration: { min_seconds: 3, max_seconds: 60, default_seconds: 10 },
      // Кадр задаёт исходник, а не список: правка видео не меняет соотношение
      // сторон. Ровно так же устроена «Копия» — измерение идёт разрешением.
      dimension_field: "resolution",
      ratios: [],
      resolutions: ["720p", "1080p"],
      resolution_by_ratio: {},
      audio: { required_explicit_boolean: true, provider_default: true },
    },
    server: {
      // У Runway нет эндпоинтов /v1/recipes/* — проверено по фильтру Request
      // History и записано в миграции 202608170006 после того, как на этом
      // умерла платная отправка «Копии». «Аватар» уходит на тот же настоящий
      // video_to_video (Gen-4 Aleph), что и «Копия».
      provider_path: "/v1/video_to_video",
      pricing: pricing(192, 208),
    },
  },
  {
    strategy_id: GENERATION_STRATEGY_IDS.productSwap,
    public_label: "Заменить товар в исходном ролике",
    public_summary:
      "Заменяет показанный товар на ваш и сохраняет механику исходной сцены в пределах возможностей Product Swap.",
    transformation_kind: "product_swap_preserve_scene",
    source_reference_mode: "provider_reference_video",
    preservation_notice:
      "Рецепт сохраняет движение камеры, свет и композицию, но не гарантирует пиксельную идентичность; лучше всего работают товары сходной формы и назначения.",
    human_review_required: true,
    provider: "runway",
    recipe: "product_swap",
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    asset_roles: [
      assetRole({
        role: "source_video",
        public_label: "Исходный ролик с заменяемым товаром",
        media_kind: "video",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: true,
        provider_field: "referenceVideo",
        duration_required: true,
        min_duration_seconds: 1.8,
        max_duration_seconds: 15,
      }),
      assetRole({
        role: "original_product_image",
        public_label: "Фото исходного товара",
        media_kind: "image",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: true,
        provider_field: "originalProductImage",
      }),
      assetRole({
        role: "new_product_image",
        public_label: "Фото вашего товара",
        media_kind: "image",
        min_count: 1,
        max_count: 10,
        forwarded_to_provider: true,
        provider_field: "newProductImages",
        allowed_views: ["front", "side", "back"],
      }),
    ],
    required_attestations: COMMON_ATTESTATIONS,
    output_rules: {
      duration: { min_seconds: 4, max_seconds: 15, default_seconds: 10 },
      dimension_field: "resolution",
      ratios: [],
      resolutions: ["720p", "1080p"],
      resolution_by_ratio: {},
      audio: { required_explicit_boolean: true, provider_default: true },
    },
    server: {
      // Runway has no /v1/recipes/* endpoints (verified in the live Request
      // History filter). Product Swap runs on the real video_to_video API
      // (Gen-4 Aleph): edit the confirmed source MP4 by prompt with image
      // references. Pricing stays the internal spend-contour authority.
      provider_path: "/v1/video_to_video",
      pricing: pricing(212, 228),
    },
  },
  {
    strategy_id: GENERATION_STRATEGY_IDS.rebuild,
    public_label: "Создать новый ролик по механике референса",
    public_summary:
      "Создаёт рекламный ролик с нуля из фотографий вашего товара и описания механики или стиля референса.",
    transformation_kind: "new_product_ad_remake",
    source_reference_mode: "mechanics_and_style_only_not_provider_input",
    preservation_notice:
      "Это новый Product Ad: исходные кадры, актёр, движение и монтаж не переносятся как есть.",
    human_review_required: true,
    provider: "runway",
    recipe: "product_ad",
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    asset_roles: [
      assetRole({
        role: "source_video",
        public_label: "Ролик-референс механики и стиля",
        media_kind: "video",
        min_count: 1,
        max_count: 1,
        forwarded_to_provider: false,
        provider_field: null,
      }),
      assetRole({
        role: "product_image",
        public_label: "Фото вашего товара",
        media_kind: "image",
        min_count: 1,
        max_count: 10,
        forwarded_to_provider: true,
        provider_field: "productImages",
      }),
      assetRole({
        role: "style_image",
        public_label: "Дополнительный стилевой референс",
        media_kind: "image",
        min_count: 0,
        max_count: 4,
        forwarded_to_provider: true,
        provider_field: "styleImages",
      }),
    ],
    required_attestations: COMMON_ATTESTATIONS,
    output_rules: {
      duration: { min_seconds: 4, max_seconds: 15, default_seconds: 10 },
      dimension_field: "ratio",
      ratios: [
        "1280:720",
        "720:1280",
        "960:960",
        "834:1112",
        "1920:1080",
        "1080:1920",
        "1440:1440",
        "1248:1664",
      ],
      resolutions: ["720p", "1080p"],
      resolution_by_ratio: {
        "1280:720": "720p",
        "720:1280": "720p",
        "960:960": "720p",
        "834:1112": "720p",
        "1920:1080": "1080p",
        "1080:1920": "1080p",
        "1440:1440": "1080p",
        "1248:1664": "1080p",
      },
      audio: { required_explicit_boolean: true, provider_default: false },
    },
    server: {
      provider_path: "/v1/recipes/product_ad",
      pricing: pricing(200, 216),
    },
  },
];

export const GENERATION_STRATEGY_CATALOG = deepFreeze(RAW_CATALOG);

export function generationStrategyCatalogEntry(strategyId) {
  return (
    GENERATION_STRATEGY_CATALOG.find(
      (entry) => entry.strategy_id === String(strategyId || ""),
    ) || null
  );
}

function validateOutputSelection(entry, value) {
  if (!Number.isInteger(value?.duration_seconds)) {
    return failure(
      "duration_invalid",
      "duration_seconds",
      "duration_seconds must be an integer",
    );
  }
  const duration = entry.output_rules.duration;
  if (
    value.duration_seconds < duration.min_seconds ||
    value.duration_seconds > duration.max_seconds
  ) {
    return failure(
      "duration_unsupported",
      "duration_seconds",
      `duration_seconds must be between ${duration.min_seconds} and ${duration.max_seconds}`,
    );
  }
  if (typeof value.audio !== "boolean") {
    return failure(
      "audio_invalid",
      "audio",
      "audio must be an explicit boolean",
    );
  }

  if (entry.output_rules.dimension_field === "ratio") {
    if (hasOwn(value, "resolution")) {
      return failure(
        "dimension_field_forbidden",
        "resolution",
        "this strategy derives resolution from ratio",
      );
    }
    if (!entry.output_rules.ratios.includes(value.ratio)) {
      return failure("ratio_unsupported", "ratio", "ratio is not supported");
    }
    return success({
      duration_seconds: value.duration_seconds,
      ratio: value.ratio,
      resolution: entry.output_rules.resolution_by_ratio[value.ratio],
      audio: value.audio,
    });
  }

  if (hasOwn(value, "ratio")) {
    return failure(
      "dimension_field_forbidden",
      "ratio",
      "this strategy uses resolution and preserves the source composition",
    );
  }
  if (!entry.output_rules.resolutions.includes(value.resolution)) {
    return failure(
      "resolution_unsupported",
      "resolution",
      "resolution is not supported",
    );
  }
  return success({
    duration_seconds: value.duration_seconds,
    ratio: null,
    resolution: value.resolution,
    audio: value.audio,
  });
}

function validateAssets(entry, assets) {
  if (!Array.isArray(assets)) {
    return failure("assets_invalid", "assets", "assets must be an array");
  }
  const roles = new Map(entry.asset_roles.map((role) => [role.role, role]));
  const counts = new Map(entry.asset_roles.map((role) => [role.role, 0]));
  const mediaIds = new Set();

  for (let index = 0; index < assets.length; index += 1) {
    const asset = assets[index];
    const field = `assets[${index}]`;
    if (!isPlainObject(asset)) {
      return failure("asset_invalid", field, "each asset must be an object");
    }
    const role = roles.get(asset.role);
    if (!role) {
      return failure(
        "asset_role_unknown",
        `${field}.role`,
        "asset role is unknown",
      );
    }
    const allowedFields = ["role", "media_id"];
    if (role.media_kind === "video") allowedFields.push("duration_seconds");
    if (role.allowed_views.length > 0) allowedFields.push("view");
    const unknownField = Object.keys(asset).find(
      (key) => !allowedFields.includes(key),
    );
    if (unknownField) {
      return failure(
        "asset_field_unknown",
        `${field}.${unknownField}`,
        "asset contains an unsupported field",
      );
    }
    if (
      typeof asset.media_id !== "string" ||
      !UUID_PATTERN.test(asset.media_id) ||
      asset.media_id.toLowerCase() === ZERO_UUID
    ) {
      return failure(
        "asset_media_id_invalid",
        `${field}.media_id`,
        "media_id must be a non-zero UUID",
      );
    }
    const normalizedMediaId = asset.media_id.toLowerCase();
    if (mediaIds.has(normalizedMediaId)) {
      return failure(
        "asset_media_id_duplicate",
        `${field}.media_id`,
        "the same media_id cannot satisfy more than one asset slot",
      );
    }
    mediaIds.add(normalizedMediaId);

    if (role.media_kind === "video") {
      if (role.duration_required && !hasOwn(asset, "duration_seconds")) {
        return failure(
          "asset_duration_required",
          `${field}.duration_seconds`,
          "duration_seconds is required for this video role",
        );
      }
      if (hasOwn(asset, "duration_seconds")) {
        if (
          typeof asset.duration_seconds !== "number" ||
          !Number.isFinite(asset.duration_seconds) ||
          asset.duration_seconds <= 0
        ) {
          return failure(
            "asset_duration_invalid",
            `${field}.duration_seconds`,
            "video duration_seconds must be a positive finite number",
          );
        }
        if (
          role.min_duration_seconds !== null &&
          asset.duration_seconds < role.min_duration_seconds
        ) {
          return failure(
            "asset_duration_unsupported",
            `${field}.duration_seconds`,
            `video duration_seconds must be at least ${role.min_duration_seconds}`,
          );
        }
        if (
          role.max_duration_seconds !== null &&
          asset.duration_seconds > role.max_duration_seconds
        ) {
          return failure(
            "asset_duration_unsupported",
            `${field}.duration_seconds`,
            `video duration_seconds must be at most ${role.max_duration_seconds}`,
          );
        }
      }
    }

    if (hasOwn(asset, "view") && !role.allowed_views.includes(asset.view)) {
      return failure(
        "asset_view_unsupported",
        `${field}.view`,
        "asset view is not supported",
      );
    }
    counts.set(role.role, counts.get(role.role) + 1);
  }

  for (const role of entry.asset_roles) {
    const count = counts.get(role.role);
    if (count < role.min_count || count > role.max_count) {
      return failure(
        "asset_role_count_invalid",
        `assets.${role.role}`,
        `${role.role} requires ${role.min_count}..${role.max_count} assets`,
      );
    }
  }
  return success({ asset_count: assets.length });
}

function validateAttestations(entry, attestations) {
  if (!isPlainObject(attestations)) {
    return failure(
      "attestations_invalid",
      "attestations",
      "attestations must be an object",
    );
  }
  const required = entry.required_attestations.map((item) => item.id);
  const unknownField = Object.keys(attestations).find(
    (key) => !required.includes(key),
  );
  if (unknownField) {
    return failure(
      "attestation_unknown",
      `attestations.${unknownField}`,
      "attestation is not part of this versioned contract",
    );
  }
  for (const id of required) {
    if (attestations[id] !== true) {
      return failure(
        "attestation_required",
        `attestations.${id}`,
        "every required rights attestation must be exactly true",
      );
    }
  }
  return success({ attestation_count: required.length });
}

export function estimateGenerationStrategyCredits(strategyId, output) {
  const entry = generationStrategyCatalogEntry(strategyId);
  if (!entry) {
    return failure("strategy_unknown", "strategy_id", "strategy_id is unknown");
  }
  if (!isPlainObject(output)) {
    return failure("output_invalid", "output", "output must be an object");
  }
  const validated = validateOutputSelection(entry, output);
  if (!validated.ok) return validated;
  const tier = entry.server.pricing.tiers[validated.resolution];
  const additionalSeconds = validated.duration_seconds -
    entry.server.pricing.base_duration_seconds;
  const estimatedCredits = tier.base_credits +
    tier.additional_credits_per_second * additionalSeconds;
  return success({
    strategy_id: entry.strategy_id,
    provider: entry.provider,
    recipe: entry.recipe,
    pricing_version: entry.pricing_version,
    resolution: validated.resolution,
    duration_seconds: validated.duration_seconds,
    estimated_credits: estimatedCredits,
    estimated_pre_tax_usd_minor: estimatedCredits,
    currency: "USD",
  });
}

export function validateGenerationStrategySelection(selection) {
  if (!isPlainObject(selection)) {
    return failure(
      "selection_invalid",
      "generation_strategy",
      "generation_strategy must be an object",
    );
  }
  const unknownField = Object.keys(selection).find(
    (key) => !TOP_LEVEL_SELECTION_FIELDS.includes(key),
  );
  if (unknownField) {
    return failure(
      "selection_field_unknown",
      unknownField,
      "generation_strategy contains an unsupported field",
    );
  }
  if (selection.version !== GENERATION_STRATEGY_CATALOG_VERSION) {
    return failure(
      "catalog_version_mismatch",
      "version",
      "generation strategy catalog version does not match",
    );
  }
  const entry = generationStrategyCatalogEntry(selection.strategy_id);
  if (!entry) {
    return failure("strategy_unknown", "strategy_id", "strategy_id is unknown");
  }
  if (selection.recipe_version !== entry.recipe_version) {
    return failure(
      "recipe_version_mismatch",
      "recipe_version",
      "recipe_version does not match the catalog",
    );
  }
  const output = validateOutputSelection(entry, selection);
  if (!output.ok) return output;
  const assets = validateAssets(entry, selection.assets);
  if (!assets.ok) return assets;
  const attestations = validateAttestations(entry, selection.attestations);
  if (!attestations.ok) return attestations;
  const cost = estimateGenerationStrategyCredits(entry.strategy_id, selection);
  if (!cost.ok) return cost;
  return success({
    strategy_id: entry.strategy_id,
    provider: entry.provider,
    recipe: entry.recipe,
    recipe_version: entry.recipe_version,
    output: {
      duration_seconds: output.duration_seconds,
      ratio: output.ratio,
      resolution: output.resolution,
      audio: output.audio,
    },
    estimated_credits: cost.estimated_credits,
    estimated_pre_tax_usd_minor: cost.estimated_pre_tax_usd_minor,
    pricing_version: cost.pricing_version,
  });
}

function exactExecutionCapability(entry, capabilities) {
  const capability = isPlainObject(capabilities)
    ? capabilities[entry.strategy_id]
    : null;
  if (!isPlainObject(capability)) return false;
  const keys = Object.keys(capability).sort();
  const expectedKeys = [...EXECUTION_CAPABILITY_FIELDS].sort();
  if (
    keys.length !== expectedKeys.length ||
    keys.some((key, index) => key !== expectedKeys[index])
  ) {
    return false;
  }
  return (
    capability.enabled === true &&
    capability.catalog_version === GENERATION_STRATEGY_CATALOG_VERSION &&
    capability.strategy_id === entry.strategy_id &&
    capability.provider === entry.provider &&
    capability.recipe === entry.recipe &&
    capability.recipe_version === entry.recipe_version &&
    capability.provider_path === entry.server.provider_path &&
    // Версия прайса приходит от действующего маршрута, а не из статического
    // описания стратегии: у Runway и у fal она разная, и сверять её с
    // константой каталога значило бы гасить стратегию при смене движка.
    isKnownStrategyPricingVersion(capability.pricing_version)
  );
}

export function generationStrategyExecutionEnabled(
  strategyId,
  capabilities = {},
) {
  const entry = generationStrategyCatalogEntry(strategyId);
  return Boolean(entry && exactExecutionCapability(entry, capabilities));
}

export function validateGenerationStrategyForExecution(
  selection,
  { executionCapabilities = {} } = {},
) {
  const validated = validateGenerationStrategySelection(selection);
  if (!validated.ok) return validated;
  const entry = generationStrategyCatalogEntry(validated.strategy_id);
  if (!exactExecutionCapability(entry, executionCapabilities)) {
    return failure(
      "strategy_execution_not_enabled",
      "strategy_id",
      "the exact server-side strategy route is not enabled",
    );
  }
  return success({
    ...validated,
    provider_path: entry.server.provider_path,
  });
}

function publicAssetRole(role) {
  return {
    role: role.role,
    public_label: role.public_label,
    media_kind: role.media_kind,
    min_count: role.min_count,
    max_count: role.max_count,
    source_use: role.forwarded_to_provider
      ? "provider_input"
      : "mechanics_or_style_reference_only",
    allowed_views: [...role.allowed_views],
    duration_required: role.duration_required,
    min_duration_seconds: role.min_duration_seconds,
    max_duration_seconds: role.max_duration_seconds,
  };
}

function publicPricing(entry) {
  const pricingValue = entry.server.pricing;
  return {
    pricing_version: entry.pricing_version,
    kind: pricingValue.kind,
    unit: pricingValue.unit,
    usd_cents_per_credit: pricingValue.usd_cents_per_credit,
    base_duration_seconds: pricingValue.base_duration_seconds,
    tiers: {
      "720p": { ...pricingValue.tiers["720p"] },
      "1080p": { ...pricingValue.tiers["1080p"] },
    },
  };
}

export function publicGenerationStrategyCatalog(
  { executionCapabilities = {} } = {},
) {
  return deepFreeze({
    version: GENERATION_STRATEGY_CATALOG_VERSION,
    recipe_version: RUNWAY_RECIPE_VERSION,
    pricing_version: RUNWAY_RECIPE_PRICING_VERSION,
    strategies: GENERATION_STRATEGY_CATALOG.map((entry) => {
      const enabled = exactExecutionCapability(entry, executionCapabilities);
      return {
        strategy_id: entry.strategy_id,
        public_label: entry.public_label,
        public_summary: entry.public_summary,
        transformation_kind: entry.transformation_kind,
        source_reference_mode: entry.source_reference_mode,
        preservation_notice: entry.preservation_notice,
        human_review_required: entry.human_review_required,
        provider: entry.provider,
        recipe: entry.recipe,
        recipe_version: entry.recipe_version,
        asset_roles: entry.asset_roles.map(publicAssetRole),
        required_attestations: entry.required_attestations.map((item) => ({
          id: item.id,
          public_label: item.public_label,
        })),
        output_rules: {
          duration: { ...entry.output_rules.duration },
          dimension_field: entry.output_rules.dimension_field,
          ratios: [...entry.output_rules.ratios],
          resolutions: [...entry.output_rules.resolutions],
          audio: { ...entry.output_rules.audio },
        },
        pricing: publicPricing(entry),
        enabled,
        disabled_reason: enabled ? null : "strategy_route_not_verified",
      };
    }),
  });
}
