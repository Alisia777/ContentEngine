/*
 * ContentEngine · three operator-specific generation routes.
 *
 * Copy and Avatar prepare project-scoped source artifacts. They do not own
 * pricing, budget reservations, provider calls, polling, or reconciliation.
 * The existing creator-generate strategy runtime remains the only paid
 * authority. Strategy keeps the full six-step native constructor.
 */

const ROUTE = "/workspace/generation";
const PAID_AUTHORITY = "creator-generate";
const COPY_AUTHORITY_STRATEGY = "viral_product_swap";
const AVATAR_AUTHORITY_STRATEGY = "viral_avatar_ugc";
const STRATEGY_AUTHORITY_STRATEGY = "viral_rebuild";
// Какой стратегии принадлежит панель маршрута. Каскад спрашивает маршруты у
// ТОЙ стратегии, чью панель рисует: раньше он был прибит к «Копии» литералом, и
// для любого другого маршрута показал бы чужие движки и чужую цену.
const ROUTE_AUTHORITY_STRATEGY = Object.freeze({
  copy_video: COPY_AUTHORITY_STRATEGY,
  avatar_video: AVATAR_AUTHORITY_STRATEGY,
  strategy_video: STRATEGY_AUTHORITY_STRATEGY,
});
const CHARACTER_PERFORMANCE_FEATURE = "generation_character_performance_v1";
const HANDOFF_VERSION = "generation-intake-mp4-v4";
const DIRECT_MP4_ATTACHMENT_RPC =
  "contentengine_attach_generation_direct_mp4";
const STYLE_HREF = new URL(
  "./generation-strategy-intake-v4.css?v=20260826.rebuild-clean.60",
  import.meta.url,
).href;
// Советчик ИИ-центра по движку грузится отдельно и лениво: экран обязан
// работать и без него (тогда по умолчанию встаёт отметка реестра). Когда
// модуль подъехал, открытый каскад перерисовывается уже с советом.
let adviseGenerationEngine = null;
const ENGINE_ADVISOR_READY = import(
  "./generation-engine-advisor.js?v=20260826.rebuild-clean.60"
).then((module) => {
  if (typeof module?.adviseGenerationEngine === "function") {
    adviseGenerationEngine = module.adviseGenerationEngine;
    for (const [strategyId, context] of engineRenderContexts.entries()) {
      // «Создание» получает совет тем же колбэком: раньше перерисовывалась
      // только «Копия», и note стратегии застревал в «не советует» до
      // следующего события (дыра первого рендера, 26.08.2026).
      if (
        ![COPY_AUTHORITY_STRATEGY, STRATEGY_AUTHORITY_STRATEGY].includes(strategyId)
        || !context?.section
      ) continue;
      try {
        renderEngineChoice(context.form, context.state, context.section, strategyId);
      } catch {
        // Перерисовка с советом — вспомогательная: без неё каскад остаётся
        // в прежнем, рабочем состоянии.
      }
    }
  }
  return adviseGenerationEngine;
}).catch(() => null);
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const MAX_COPY_DURATION = 15;
const MIN_COPY_DURATION = 4;
const MAX_AVATAR_DURATION = 60;
const MAX_STRATEGY_FILES = 10;
const MAX_MP4_BYTES = 32 * 1024 * 1024;
const MAX_IMAGE_BYTES = 16 * 1024 * 1024;
const MIN_PRODUCT_IMAGES = 1;
const MAX_PRODUCT_IMAGES = 5;
const STORYBOARD_FRAME_COUNT = 8;
const BRIEF_LIMIT = 800;
const PRODUCT_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);
const MEDIA_KIND_MIME_CONTRACT = Object.freeze({
  product_photo: Object.freeze({
    allowed: PRODUCT_IMAGE_TYPES,
    expected: "изображение JPG, PNG или WEBP",
  }),
  packshot: Object.freeze({
    allowed: PRODUCT_IMAGE_TYPES,
    expected: "изображение JPG, PNG или WEBP",
  }),
  creator_reference: Object.freeze({
    allowed: PRODUCT_IMAGE_TYPES,
    expected: "изображение JPG, PNG или WEBP",
  }),
  source_video: Object.freeze({
    allowed: new Set(["video/mp4"]),
    expected: "видео MP4",
  }),
});
// Локальные тексты ниже — только стартовые заготовки интерфейса. Они не
// получены из ИИ-центра, не несут его lineage и попадают в brief лишь после
// явного нажатия человека.
const DEFAULT_BRIEF_TEMPLATES = Object.freeze({
  copy_video: "Сохранить последовательность сцен, движение камеры, темп и монтаж исходного ролика. Заменить только исходный товар на товар с выбранных фото: точно сохранить форму, материал, цвет, упаковку и логотип. Не добавлять новые объекты или надписи.",
  // «Дуэт»: этот текст ведущий ПРОИЗНЕСЁТ ВСЛУХ за деньги — это речь, а не
  // задание модели. Шаблон — пример реплики, которую надо переписать под
  // ролик.
  avatar_video: "Смотрите, как он держит товар — обратите внимание на этот момент. Именно так это и работает в жизни: быстро, без лишних движений. Дальше самое интересное.",
  // «Создание»: ролик собирается с нуля по фото товара — заготовка описывает
  // продающий каркас, оператор правит под свой товар.
  strategy_video: "Создать продающий вертикальный ролик о товаре с фото: показать товар крупно с первой секунды, подчеркнуть главную пользу, показать товар в использовании и закончить призывом забрать свой. Товар — точная копия фото: форма, цвет, фурнитура и логотип без изменений. Не добавлять чужие бренды и надписи.",
});
// Экспресс-«Копия»: одна консолидированная галка прав текстуально покрывает
// четыре юридически раздельных подтверждения мастера. Клик по ней ставит все
// четыре настоящих чекбокса через их обычные change-события; серверный
// контракт не меняется, недоступное подтверждение честно показывается.
const COPY_ATTESTATION_IDS = Object.freeze([
  "source_media_rights_confirmed",
  "transformative_use_confirmed",
  "product_assets_rights_confirmed",
  "depicted_people_consent_confirmed",
]);
const COPY_ATTESTATION_LABELS = Object.freeze({
  source_media_rights_confirmed: "право на исходный ролик (референс)",
  transformative_use_confirmed: "переработка: переносится только механика",
  product_assets_rights_confirmed: "права на изображения товара",
  depicted_people_consent_confirmed: "согласие людей в кадре или их отсутствие",
});
// «Показать цену» проходит только бесплатные фазы действующего мастера:
// подготовка точного ТЗ, его одобрение и бесплатный preflight с ценой.
// Платная фаза требует отдельного человеческого клика «Запустить за $X».
// Бесплатные фазы очереди «Создания»: тот же цикл (подготовка ТЗ → одобрение
// → бесплатный preflight с ценой), только именами exact-контура.
const REBUILD_FREE_SUBMIT_PHASES = Object.freeze([
  "strategy_exact_10_prepare",
  "strategy_exact_10_spec_review",
  "strategy_exact_10_free_preflight",
]);
const EXPRESS_FREE_SUBMIT_PHASES = Object.freeze([
  "strategy_product_swap_prepare",
  "strategy_product_swap_spec_review",
  "strategy_product_swap_free_preflight",
]);
const EXPRESS_PREFLIGHT_TIMEOUT_MS = 180_000;
const EXPRESS_POLL_INTERVAL_MS = 400;
const EXPRESS_BLOCKED_POLL_LIMIT = 15;
// Каталог и выбранная стратегия дорисовывают четыре нативных attestation
// асинхронно. Compact-гейт ждёт их ограниченное число опросов, но никогда не
// подменяет legacy-checkbox или собственную единую галку серверным контрактом.
const EXPRESS_ATTESTATION_RENDER_POLL_LIMIT = 12;
// Клик по кнопке мастера обязан двигать его шаг. Если после EXPRESS_STALLED_POLL_LIMIT
// нажатий подряд ничего не изменилось (шаг, блокировка, занятость и подпись
// подтверждения те же), продолжать бессмысленно: мастер нас не слышит. Молчать
// три минуты до таймаута — это и есть тот самый невидимый отказ.
const EXPRESS_STALLED_POLL_LIMIT = 12;
const NEW_CAMPAIGN_ROUTE_HASH = "#/workspace/team?view=new-campaign";
// Отдельный полноэкранный маршрут «Скопировать ролик»:
// #/workspace/generation?view=copy. Пользователь видит только пять блоков
// сверху вниз (ролик, фото, замысел, права, цена); скрытый #mock-batch-form
// продолжает работать движком, но шаги 01–06, «Что нужно сделать?», «Режим и
// бюджет» и модельные карточки на этом экране не показываются.
const COPY_VIEW_QUERY = "copy";
// Выбор фото переживает любую перерисовку: media_id выбранных фото хранятся в
// sessionStorage по проекту, а ещё не зарегистрированные файлы — в очереди в
// памяти модуля (File нельзя сериализовать в sessionStorage).
const COPY_PHOTO_STORAGE_PREFIX = "generation-copy-photos-v1:";
const pendingCopyProductFiles = new Map();
const BRIEF_ROUTES = Object.freeze([
  "copy_video",
  "avatar_video",
  "strategy_video",
]);
// В DOM остаётся ровно одно нативное поле `brief`: его читает существующий
// creator-generate contract. Значение и provenance при этом принадлежат не
// полю вообще, а конкретному маршруту. Map переживает patch-render формы в
// пределах текущей вкладки и не превращает Copy/Avatar/Strategy в один общий
// черновик.
const routeBriefDraftsMemory = new Map();
const BRIEF_CONTROL_DATASET_KEYS = Object.freeze([
  "researchRecommendationApplied",
  "researchRecommendationField",
  "researchRecommendationEdited",
  "generationIntakeOperatorOwned",
]);
const BRIEF_FORM_DATASET_KEYS = Object.freeze([
  "generationAiResearchWorkingSelectionId",
  "generationAiResearchWorkingPosition",
  "researchRecommendationLineage",
  "researchRecommendationSelectionId",
  "researchRecommendationPosition",
  "researchRecommendationAppliedFields",
  "researchRecommendationProductId",
  "researchRecommendationProductCategory",
  "researchRecommendationVerificationRequired",
  "researchRecommendationVerificationState",
  "researchRecommendationVerificationFailure",
  "researchRecommendationVerificationSelectionId",
  "researchRecommendationVerificationPosition",
  "researchRecommendationProviderFragmentStatus",
  "researchRecommendationProviderFragmentVersion",
  "researchRecommendationProviderFragmentHash",
  "researchRecommendationAutoApplyDisabled",
]);
// Грабля владельца: перерисовка страницы сбрасывает значения select.
// Экспресс-панель хранит свои значения по проекту и восстанавливает их
// при каждом повторном монтировании.
const expressDefaultsMemory = new Map();
const formStates = new WeakMap();
let mountQueued = false;

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function cleanText(value, limit = 1_200) {
  return String(value || "")
    .replace(/[\u0000-\u001f\u007f]/gu, " ")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, limit);
}

function routePath() {
  const managed = window.ContentEngineDesktopV4?.route?.();
  if (managed) return managed;
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function routeParams() {
  const raw = String(window.location.hash || "");
  return new URLSearchParams(raw.includes("?") ? raw.split("?").slice(1).join("?") : "");
}

function projectId() {
  const value = String(routeParams().get("project_id") || "")
    .trim()
    .toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

function copyViewActive() {
  return routePath() === ROUTE
    && routeParams().get("view") === COPY_VIEW_QUERY;
}

function ensureStyle() {
  const alreadyLoaded = [...(document.styleSheets || [])].some(
    (sheet) => sheet.href === STYLE_HREF,
  );
  if (
    alreadyLoaded
    || q(`link[data-generation-intake-v4-style="${CSS.escape(STYLE_HREF)}"]`)
  ) {
    return;
  }
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_HREF;
  link.dataset.generationIntakeV4Style = STYLE_HREF;
  document.head.append(link);
}

function ensureHidden(form, name) {
  const existing = form.elements?.namedItem?.(name);
  if (existing instanceof HTMLInputElement) return existing;
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = name;
  input.dataset.generationIntakeV4Hidden = "";
  form.append(input);
  return input;
}

function setHidden(form, name, value) {
  const input = ensureHidden(form, name);
  input.value = typeof value === "string" ? value : JSON.stringify(value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function ensureContractFields(form) {
  [
    "generation_intake_version",
    "generation_intake_route",
    "generation_intake_source_media_id",
    "generation_intake_source_duration_seconds",
    "generation_intake_original_product_media_id",
    "generation_intake_avatar_media_id",
    "generation_intake_avatar_mode",
    "generation_intake_product_media_ids",
    "generation_intake_reference_media_ids",
    "generation_intake_source_url",
    "generation_intake_description",
    "generation_intake_model",
    "generation_intake_audio",
    "generation_intake_recommendation_source",
    "generation_strategy_prefill_assets",
    // Движок каскада в виде «провайдер:модель». Поле формы, а не переменная
    // модуля: привязку собирает app.js, и читать он обязан то же самое, что
    // видит человек на экране.
    "generation_intake_engine",
  ].forEach((name) => ensureHidden(form, name));
}

function field(title, hint, control) {
  const label = el("label", "generation-intake-v4__field");
  label.append(
    el("span", "generation-intake-v4__label", title),
    control,
    el("small", "generation-intake-v4__hint", hint),
  );
  return label;
}

function optionalSourceUrl() {
  const input = document.createElement("input");
  input.type = "url";
  input.inputMode = "url";
  input.autocomplete = "url";
  input.placeholder = "Ссылка на публикацию — необязательно";
  input.dataset.generationIntakeField = "source_url";
  return field(
    "Источник публикации — по желанию",
    "Ссылка хранится как происхождение ролика. Система анализирует загруженный MP4, а не страницу соцсети.",
    input,
  );
}

function mp4Input({ multiple = false } = {}) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "video/mp4,.mp4";
  input.multiple = multiple;
  input.dataset.generationIntakeMp4 = multiple ? "strategy" : "single";
  return input;
}

function statusNode() {
  const node = el("div", "generation-intake-v4__status");
  node.dataset.generationIntakeStatus = "";
  node.setAttribute("role", "status");
  node.setAttribute("aria-live", "polite");
  return node;
}

// Панель могла быть перерисована мастером, пока длилась асинхронная работа:
// узел на руках у вызывающего кода отсоединяется, и сообщение уходит в пустоту.
// Поэтому текст пишется и в удерживаемый узел, и в живую панель того же
// маршрута — человек всегда видит ответ формы, а не тишину.
function setStatus(
  panel,
  text,
  state = "neutral",
  { expressPriceResult = "" } = {},
) {
  const route = String(panel?.dataset?.generationIntakePanel || "");
  const targets = new Set();
  const held = q("[data-generation-intake-status]", panel);
  if (held) targets.add(held);
  if (route) {
    qa(`[data-generation-intake-panel="${CSS.escape(route)}"]`).forEach((node) => {
      const live = q("[data-generation-intake-status]", node);
      if (live) targets.add(live);
    });
  }
  targets.forEach((status) => {
    if (status.dataset.state !== state) status.dataset.state = state;
    if (status.textContent !== text) status.textContent = text;
    if (expressPriceResult) {
      status.dataset.expressPriceResult = expressPriceResult;
    } else {
      delete status.dataset.expressPriceResult;
    }
  });
}

function fileSizeLabel(bytes) {
  const size = Number(bytes);
  if (!Number.isFinite(size) || size <= 0) return "";
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} МБ`;
  return `${Math.max(1, Math.round(size / 1024))} КБ`;
}

// Сводка выбранного исходника в зоне выбора файла: имя, размер и то, что с
// ним сейчас происходит. Пустой текст прячет строку — зона снова «пустая».
function setSourceFileSummary(panel, text, state = "neutral") {
  const route = String(panel?.dataset?.generationIntakePanel || "");
  const targets = new Set();
  const held = q("[data-generation-intake-source-file]", panel);
  if (held) targets.add(held);
  if (route) {
    qa(`[data-generation-intake-panel="${CSS.escape(route)}"]`).forEach((node) => {
      const live = q("[data-generation-intake-source-file]", node);
      if (live) targets.add(live);
    });
  }
  targets.forEach((node) => {
    if (node.textContent !== text) node.textContent = text;
    if (node.dataset.state !== state) node.dataset.state = state;
    if (node.hidden !== !text) node.hidden = !text;
    const drop = node.closest(".gi-drop");
    if (drop && drop.dataset.hasFile !== String(Boolean(text))) {
      drop.dataset.hasFile = String(Boolean(text));
    }
  });
}

function sourceFileLead(file) {
  const size = fileSizeLabel(file?.size);
  return `«${cleanText(file?.name, 80) || "файл"}»${size ? ` · ${size}` : ""}`;
}

const VISUAL_ICON_PATHS = Object.freeze({
  swap: Object.freeze([
    "M7 7h9.5a3.5 3.5 0 0 1 0 7H8",
    "m10 4 3 3-3 3",
    "m8 10-3-3 3-3",
  ]),
  avatar: Object.freeze([
    "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
    "M5 21a7 7 0 0 1 14 0",
    "M18 6.5h2.5M19.25 5.25v2.5",
  ]),
  strategy: Object.freeze([
    "m12 3 1.15 3.1L16 7.5l-2.85 1.4L12 12l-1.15-3.1L8 7.5l2.85-1.4L12 3Z",
    "m6 13 .8 2.2L9 16l-2.2.8L6 19l-.8-2.2L3 16l2.2-.8L6 13Z",
    "m18 12 .8 2.2L21 15l-2.2.8L18 18l-.8-2.2L15 15l2.2-.8L18 12Z",
  ]),
  pika: Object.freeze([
    "M5 8.5h10.5a3 3 0 1 1 0 6H9",
    "m7 5 3 3-3 3",
    "M12 4.5h5.5M15 2l2.5 2.5L15 7",
  ]),
  kling: Object.freeze([
    "M12 3v3M12 18v3M3 12h3M18 12h3",
    "M6.3 6.3 8.4 8.4M15.6 15.6l2.1 2.1M17.7 6.3l-2.1 2.1M8.4 15.6l-2.1 2.1",
    "M15.5 12a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0Z",
  ]),
  runway: Object.freeze([
    "M4 16c2.5-5.5 5.2-8 8-8 3.2 0 5.7 2.2 8 8",
    "M6.5 17.5h11",
    "M9 13.5h6",
  ]),
  model: Object.freeze([
    "M8 4h8l4 8-4 8H8l-4-8 4-8Z",
    "M9 12h6M12 9v6",
  ]),
});

const STRATEGY_VISUALS = Object.freeze({
  copy_video: Object.freeze({
    art: "swap",
    image: "./assets/content-factory-strategy-copy-v1.png",
    label: "Замена товара",
    timing: "5 этапов · 5–7 мин",
    result: "Товар заменён, механика сохранена",
  }),
  avatar_video: Object.freeze({
    art: "avatar",
    image: "./assets/content-factory-strategy-avatar-v1.png",
    label: "Цифровой герой",
    timing: "4 этапа · 5–6 мин",
    result: "Герой встроен в исходную сцену",
  }),
  strategy_video: Object.freeze({
    art: "strategy",
    image: "./assets/content-factory-strategy-builder-v1.png",
    label: "Сценарий с нуля",
    timing: "6 этапов · 10–15 мин",
    result: "Сценарий, модель и бюджет собраны",
  }),
});

// Provider names remain readable text in the card. These generated scenes are
// deliberately decorative: they give each engine a recognizable visual
// character without pretending to be a provider logo or replacing the exact
// price, duration and input conditions shown beside them.
const MODEL_VISUALS = Object.freeze({
  pika: Object.freeze({
    image: "./assets/content-factory-model-pika-v1.png",
    focal: "50% 50%",
    motion: "transform",
  }),
  kling: Object.freeze({
    image: "./assets/content-factory-model-kling-v1.png",
    focal: "50% 48%",
    motion: "orbit",
  }),
  runway: Object.freeze({
    image: "./assets/content-factory-model-runway-v1.png",
    focal: "50% 50%",
    motion: "panels",
  }),
  happyhorse: Object.freeze({
    image: "./assets/content-factory-model-happyhorse-v1.png",
    focal: "50% 50%",
    motion: "edit",
  }),
  seedance: Object.freeze({
    image: "./assets/content-factory-model-family-seedance-v1.png",
    focal: "66% 48%",
    motion: "flow",
  }),
  minimax: Object.freeze({
    image: "./assets/content-factory-model-minimax-v1.png",
    focal: "50% 50%",
    motion: "timeline",
  }),
  grok: Object.freeze({
    image: "./assets/content-factory-model-grok-v1.png",
    focal: "50% 50%",
    motion: "signals",
  }),
  heygen: Object.freeze({
    image: "./assets/content-factory-model-heygen-v1.png",
    focal: "50% 50%",
    motion: "avatar",
  }),
  model: Object.freeze({ motion: "workspace" }),
});

function visualArtNode(visual, className = "gi-visual-art") {
  const key = Object.hasOwn(VISUAL_ICON_PATHS, visual) ? visual : "model";
  const art = el("span", className);
  art.dataset.visual = key;
  art.setAttribute("aria-hidden", "true");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  VISUAL_ICON_PATHS[key].forEach((pathData) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", pathData);
    svg.append(path);
  });
  art.append(svg);
  return art;
}

function routeSceneNode(visual) {
  const scene = el("span", "generation-intake-v4__route-scene");
  scene.dataset.visual = visual.art;
  scene.setAttribute("aria-hidden", "true");
  const image = document.createElement("img");
  image.className = "generation-intake-v4__route-scene-image";
  image.src = new URL(visual.image, import.meta.url).href;
  image.alt = "";
  image.loading = "eager";
  image.decoding = "async";
  image.draggable = false;
  const motion = el("span", "generation-intake-v4__route-motion");
  motion.append(
    el("span", "generation-intake-v4__route-motion-layer generation-intake-v4__route-motion-layer--signal"),
    el("span", "generation-intake-v4__route-motion-layer generation-intake-v4__route-motion-layer--scan"),
    el("span", "generation-intake-v4__route-motion-layer generation-intake-v4__route-motion-layer--dust"),
  );
  scene.append(image, motion);
  return scene;
}

function modelVisualNode(visualKey) {
  const key = Object.hasOwn(MODEL_VISUALS, visualKey) ? visualKey : "model";
  const asset = MODEL_VISUALS[key];
  const scene = el("span", "gi-model-choice__visual");
  scene.dataset.visual = key;
  scene.dataset.image = asset.image ? "true" : "false";
  scene.dataset.motion = asset.motion;
  scene.setAttribute("aria-hidden", "true");
  if (asset.image) {
    scene.style.setProperty("--model-focal", asset.focal);
    const image = document.createElement("img");
    image.className = "gi-model-choice__image";
    image.src = new URL(asset.image, import.meta.url).href;
    image.alt = "";
    image.loading = "eager";
    image.decoding = "async";
    image.draggable = false;
    scene.append(image);
  }
  const motion = el("span", "gi-model-choice__motion");
  motion.append(
    el("span", "gi-model-choice__motion-layer gi-model-choice__motion-layer--one"),
    el("span", "gi-model-choice__motion-layer gi-model-choice__motion-layer--two"),
    el("span", "gi-model-choice__motion-layer gi-model-choice__motion-layer--three"),
    el("span", "gi-model-choice__motion-layer gi-model-choice__motion-layer--four"),
  );
  scene.append(motion);
  return scene;
}

function humanAuthorityStrip() {
  const strip = el("div", "generation-intake-v4__authority");
  strip.dataset.generationIntakeHumanAuthority = "";
  [
    ["ai", "ИИ-центр", "Рекомендует черновик"],
    ["human", "Человек", "Правит под задачу"],
    ["confirm", "Подтверждение", "Фиксирует решение"],
  ].forEach(([state, title, detail], index) => {
    const item = el("span", "generation-intake-v4__authority-step");
    item.dataset.state = state;
    item.append(
      el("span", "generation-intake-v4__authority-number", String(index + 1)),
      (() => {
        const copy = el("span", "generation-intake-v4__authority-copy");
        copy.append(el("strong", "", title), el("small", "", detail));
        return copy;
      })(),
    );
    strip.append(item);
  });
  return strip;
}

function routeButton(id, number, title, summary) {
  const button = el("button", "generation-intake-v4__route");
  button.type = "button";
  button.dataset.generationIntakeRoute = id;
  const visual = STRATEGY_VISUALS[id] || STRATEGY_VISUALS.strategy_video;
  button.dataset.visual = visual.art;
  button.setAttribute("aria-pressed", "false");
  const scene = routeSceneNode(visual);
  scene.append(el("span", "generation-intake-v4__route-number", number));
  button.append(
    scene,
    (() => {
      const copy = el("span", "generation-intake-v4__route-copy");
      copy.append(
        el("span", "generation-intake-v4__route-kicker", visual.label),
        el("strong", "", title),
        el("small", "", summary),
        (() => {
          const facts = el("span", "generation-intake-v4__route-facts");
          facts.append(
            el("span", "", visual.timing),
            el("span", "", visual.result),
          );
          return facts;
        })(),
      );
      return copy;
    })(),
    el("span", "generation-intake-v4__route-selected", "Выбран"),
  );
  return button;
}

function routeHeader(eyebrow, title, description, badge) {
  const header = el("header", "generation-intake-v4__panel-head");
  const copy = el("div");
  copy.append(el("p", "eyebrow", eyebrow), el("h3", "", title), el("p", "", description));
  header.append(copy, el("span", "badge", badge));
  return header;
}

function sourceChooser(route, heading = "Исходный ролик *") {
  const box = el("section", "generation-intake-v4__source");
  box.dataset.generationIntakeSource = route;
  box.dataset.sourceTab = "upload";
  const input = mp4Input();
  input.id = `generation-intake-${route}-mp4`;
  const label = el("label", "generation-intake-v4__drop gi-drop");
  label.htmlFor = input.id;
  // Выбранный файл называется ПРЯМО в зоне выбора. Строка состояния и кнопка
  // «Разобрать MP4» у длинной панели живут далеко внизу, и после выбора файла
  // человек видел ту же пустую рамку — «ролик не загружается». Сводка стоит
  // там, куда он только что кликнул.
  const summary = el("div", "gi-drop__file");
  summary.dataset.generationIntakeSourceFile = route;
  summary.hidden = true;
  label.append(
    el("strong", "", "Перетащите MP4 сюда или выберите файл"),
    el("span", "", "Формат и длительность проверим автоматически"),
    summary,
    input,
  );
  const select = document.createElement("select");
  select.dataset.generationIntakeExistingVideo = route;
  // Роль исходника нужна привязке (bindRoleAsset): она ищет контрол с этой
  // ролью и опцией нужного медиа. Раньше роль была только у скрытого
  // легаси-селекта мастера, который на экране «Копия» остаётся пустым, —
  // поэтому привязка не находила ролик, который человек уже выбрал ЗДЕСЬ, и
  // писала «материалы загружены, но не привязались автоматически». Этот селект
  // и есть выбор исходника на экране копии; роль просто называет вещь своим
  // именем.
  select.dataset.generationStrategyRole = "source_video";
  select.append(new Option("Не выбран файл проекта", ""));
  const projectField = field(
    "MP4 из файлов проекта",
    "В списке только видеоматериалы этого проекта, которые распознаны однозначно.",
    select,
  );
  // Два входа в один и тот же выбор: загрузка нового файла и уже принятые
  // ролики проекта. Оба узла остаются в DOM — вкладка только показывает нужный.
  const tabs = el("div", "gi-tabs");
  [
    ["upload", "Загрузить MP4"],
    ["project", "Выбрать из проекта"],
  ].forEach(([tab, text]) => {
    const button = el("button", "gi-tab", text);
    button.type = "button";
    button.dataset.sourceTab = tab;
    button.addEventListener("click", () => {
      box.dataset.sourceTab = tab;
      qa("[data-source-tab]", tabs).forEach((node) => {
        node.dataset.state = node.dataset.sourceTab === tab ? "active" : "idle";
      });
    });
    tabs.append(button);
  });
  qa("[data-source-tab]", tabs)[0].dataset.state = "active";
  qa("[data-source-tab]", tabs)[1].dataset.state = "idle";
  if (heading) box.append(el("h4", "", heading));
  box.append(tabs, label, projectField);
  return box;
}

function storyboardNode() {
  const section = el("section", "generation-intake-v4__storyboard");
  section.hidden = true;
  section.dataset.generationIntakeStoryboard = "";
  section.append(
    el("h4", "", "Кадры исходного ролика"),
    el(
      "p",
      "muted tiny",
      "Система выберет наиболее читаемый кадр товара. Нажмите другой кадр, если товар лучше виден там.",
    ),
    el("div", "generation-intake-v4__frames"),
  );
  return section;
}

function imageInput({ multiple = false, purpose = "product" } = {}) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp";
  input.multiple = multiple;
  input.dataset.generationIntakeImage = purpose;
  return input;
}

// Кадр исходного товара собирает декодер браузера: сначала из локального
// файла, потом из скачанного ролика проекта. Там, где декодер молчит —
// перекрытое окно, сборка без проприетарных кодеков, корпоративная политика —
// отваливаются обе ветки сразу, и маршрут «Копия» упирается в тупик: снимок
// кадра требует контракт спецификации. Поэтому у человека есть прямой способ
// дать кадр самому, не завися от декодера вовсе.
function originalFrameSlot() {
  const section = el("section", "generation-intake-v4__original-frame");
  section.dataset.generationIntakeOriginalFrame = "";
  section.hidden = true;
  const input = imageInput({ multiple: false, purpose: "original_frame" });
  input.id = "generation-intake-copy-original-frame";
  const upload = el(
    "label",
    "generation-intake-v4__drop generation-intake-v4__drop--compact",
  );
  upload.htmlFor = input.id;
  upload.append(
    el("strong", "", "Кадр исходного товара — один файл"),
    el(
      "span",
      "",
      "JPG, PNG или WEBP · стоп-кадр этого же ролика, где виден заменяемый товар",
    ),
    input,
  );
  const status = el("p", "generation-intake-v4__selection-count", "");
  status.dataset.generationIntakeOriginalFrameStatus = "";
  section.append(
    el(
      "p",
      "gi-card__hint",
      "Браузер не собрал раскадровку этого ролика. Приложите стоп-кадр исходного товара сами — без него подготовка не дойдёт до цены.",
    ),
    upload,
    status,
  );
  return section;
}

function productSlot() {
  const section = el("section", "generation-intake-v4__product");
  section.dataset.generationIntakeProductSlot = "";
  const input = imageInput({ multiple: true, purpose: "product" });
  input.id = "generation-intake-copy-product-images";
  const upload = el("label", "generation-intake-v4__drop generation-intake-v4__drop--compact");
  upload.htmlFor = input.id;
  upload.append(
    el("strong", "", "Загрузить фото товара — до 5 файлов"),
    el("span", "", "JPG, PNG или WEBP · один товар с разных ракурсов"),
    input,
  );
  const count = el("p", "generation-intake-v4__selection-count", `Сейчас: 0 из ${MAX_PRODUCT_IMAGES}`);
  count.dataset.generationIntakeProductCount = "";
  // Очередь файлов, ещё не зарегистрированных в проекте. Она переживает
  // перерисовку формы — иначе выбор терялся, — но из-за этого поле загрузки
  // может выглядеть пустым, пока файлы всё ещё считаются. Значит очередь
  // обязана быть видимой и снимаемой: невидимое, что нельзя убрать, читается
  // как «форма не даёт удалить фото».
  const pending = el("p", "generation-intake-v4__selection-count", "");
  pending.dataset.generationIntakePendingFiles = "";
  pending.hidden = true;
  const pendingClear = el("button", "gi-link-button", "Убрать файлы из очереди");
  pendingClear.type = "button";
  pendingClear.dataset.generationIntakePendingClear = "";
  pendingClear.hidden = true;
  section.append(
    el("p", "gi-card__hint", `Добавьте 1–${MAX_PRODUCT_IMAGES} фото одного товара — новые файлы или уже проверенные фотографии проекта.`),
    // Правило выстрадано боевым запуском 29.08: модерация видео-провайдера
    // (ByteDance) отклоняет фото с людьми и наложениями камеры, задача умирает
    // через секунды ПОСЛЕ резерва денег. Дешевле сказать это до загрузки.
    el(
      "p",
      "gi-card__hint",
      "Только чистые фото: без рук и лиц в кадре, без вотермарок камеры и "
        + "штампов даты — такие снимки модерация нейросети отклоняет, и "
        + "запуск обрывается.",
    ),
    upload,
    count,
    pending,
    pendingClear,
    el("div", "generation-intake-v4__product-items"),
  );
  return section;
}

function executionControls() {
  const section = el("section", "generation-intake-v4__execution");
  const model = document.createElement("select");
  model.dataset.generationIntakeField = "model";
  model.dataset.generationIntakeServerOwned = "";
  model.setAttribute("aria-readonly", "true");
  model.append(new Option(
    "Runway · Product Swap (серверный recipe)",
    "runway:product_swap",
  ));
  model.value = "runway:product_swap";
  model.disabled = true;
  const audio = document.createElement("select");
  audio.dataset.generationIntakeField = "audio";
  audio.required = true;
  audio.append(
    new Option("Выберите звук", ""),
    new Option("Со звуком", "true"),
    new Option("Без звука", "false"),
  );
  // Автоматика экспресс-формы: «Без звука» по умолчанию, без вопросов.
  audio.value = "false";
  section.append(
    field(
      "Модель генерации видео",
      "Product Swap использует подтверждённый серверный recipe. Другую модель нельзя подставить так, чтобы незаметно изменить цену или платный запуск провайдера.",
      model,
    ),
    field(
      "Звук",
      "Экспресс-режим по умолчанию готовит результат без звука. Значение можно изменить здесь до запуска.",
      audio,
    ),
  );
  return section;
}

// Compact keeps the native campaign select as the paid authority, but exposes
// a dedicated mirror before price/preflight.  Giving the mirror a different
// name is deliberate: two `campaign_id` controls would turn
// `form.elements.campaign_id` into a RadioNodeList and break the exact start
// contract in app.js.
// Подпись «нет активной кампании» со ссылкой на её создание. Одна на обе
// экспресс-панели: платный запуск без кампании честно невозможен и у «Дуэта».
function campaignNoteBlock() {
  const campaignNote = el("p", "generation-intake-v4__campaign-note");
  campaignNote.dataset.generationIntakeCampaignNote = "";
  campaignNote.hidden = true;
  const campaignLink = el("a", "", "Создать кампанию");
  campaignLink.href = NEW_CAMPAIGN_ROUTE_HASH;
  const campaignMessage = el(
    "span",
    "",
    "В проекте нет активной кампании, поэтому платный запуск честно невозможен. ",
  );
  campaignMessage.dataset.generationIntakeCampaignNoteText = "";
  campaignNote.append(
    campaignMessage,
    campaignLink,
    el("span", "", " и вернитесь в эту форму."),
  );
  return campaignNote;
}

function compactCampaignChoice() {
  const section = el("section", "gi-card generation-intake-v4__campaign");
  section.dataset.generationIntakeCampaignCard = "";
  const select = document.createElement("select");
  select.dataset.generationIntakeCampaignSelect = "";
  select.setAttribute("aria-label", "Кампания и её бюджет");
  select.append(new Option("Кампании загружаются…", ""));
  select.disabled = true;
  const hint = el(
    "p",
    "gi-card__hint generation-intake-v4__campaign-hint",
    "Кампания выбирается до бесплатной проверки цены. Смена кампании аннулирует прежнюю цену и подтверждение списания.",
  );
  hint.dataset.generationIntakeCampaignHint = "";
  section.append(
    el("h4", "gi-card__title", "Кампания и бюджет"),
    field(
      "Куда отнести расход *",
      "Платный запуск будет привязан ровно к выбранной здесь активной кампании.",
      select,
    ),
    hint,
  );
  return section;
}

function recommendationSlot(route) {
  const section = el("section", "generation-intake-v4__recommendation");
  section.dataset.generationIntakeRecommendation = route;
  const header = el("div", "generation-intake-v4__recommendation-head");
  header.append(
    el("h4", "", route === "copy_video"
      ? "Стартовая заготовка: что сохранить и как заменить"
      : route === "strategy_video"
        ? "Стартовая заготовка: каким будет ролик с нуля"
        : "Стартовая заготовка для ролика с аватаром"),
    (() => {
      const badge = el("span", "badge", "Базовый шаблон");
      badge.dataset.generationIntakeRecommendationSource = "";
      return badge;
    })(),
  );
  const slot = el("div", "generation-intake-v4__recommendation-field");
  slot.dataset.generationIntakeBriefSlot = route;
  const fallback = el("div", "generation-intake-v4__recommendation-fallback");
  fallback.dataset.generationIntakeRecommendationFallback = route;
  fallback.append(
    el("small", "", "Локальный шаблон, не рекомендация ИИ-центра."),
    el("p", "", DEFAULT_BRIEF_TEMPLATES[route]),
    (() => {
      const button = el("button", "btn btn-secondary", "Вставить базовый шаблон");
      button.type = "button";
      button.dataset.action = "generation-intake-apply-recommendation";
      button.dataset.route = route;
      return button;
    })(),
  );
  const meta = el("small", "generation-intake-v4__recommendation-meta", `0 / ${BRIEF_LIMIT}`);
  meta.dataset.generationIntakeBriefMeta = route;
  const rule = el(
    "p",
    "generation-intake-v4__recommendation-rule",
    "Рекомендация приходит из ИИ-центра как редактируемый черновик. Автозапуска нет: человек проверяет, правит и подтверждает финальную версию.",
  );
  section.append(header, rule, humanAuthorityStrip(), slot, fallback, meta);
  return section;
}

function rightsConfirmation(route) {
  const label = el("label", "generation-intake-v4__confirmation");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.dataset.generationIntakeRights = route;
  label.append(
    input,
    el(
      "span",
      "",
      route === "avatar_video"
        ? "У команды есть право использовать исходный ролик."
        : "Подтверждаю все права одним действием: у команды есть право использовать исходный ролик как референс; мы переносим только механику — это переработка без чужого бренда, музыки, голоса и точных кадров; права на изображения товара подтверждены; согласия людей в кадре получены — либо людей в кадре нет.",
    ),
  );
  return label;
}

// Ведущие проекта и раскладка врезки. Кэш по проекту: список меняется редко, а
// перерисовок панели много.
const duetPresenterCache = new Map();
// Проекты, у которых список ведущих уже ПРОЧИТАН с сервера. Пустой кэш до
// ответа — не «ведущих нет», а «ещё не знаем»: раскрывать сценарий заведения и
// дёргать каталог HeyGen по нему нельзя.
const duetPresentersLoaded = new Set();

const DUET_CORNERS = Object.freeze([
  ["bottom_left", "Слева внизу"],
  ["bottom_right", "Справа внизу"],
  ["top_left", "Слева вверху"],
  ["top_right", "Справа вверху"],
]);
const DUET_SHAPES = Object.freeze([
  ["cutout", "Вырезом"],
  ["window", "Окном с подложкой"],
]);
// Те же пределы, что в базе и в сборщике. Меньше пятой части ширины кадра
// ведущего не разглядеть на телефоне, больше половины — он закрывает то, что
// комментирует.
const DUET_WIDTH_MIN = 20;
const DUET_WIDTH_MAX = 50;

/*
 * Выбор ведущего для дуэта.
 *
 * Форма отдаёт НАШ идентификатор ведущего, а не его личность у провайдера:
 * avatar_id живёт на сервере и в браузер не приходит вовсе. Подменить, кто
 * будет говорить в оплаченном ролике, из формы невозможно.
 */
/*
 * Товар, под которым оформляется дуэт.
 *
 * У «Копии» товар называют ЗАГРУЖЕННЫЕ ФОТОГРАФИИ: артикул и название вводят
 * при загрузке, и сервер выводит товар из медиа-объекта. У дуэта фотографий
 * товара нет вовсе — он комментирует чужой ролик, — поэтому товар приходится
 * называть отдельно.
 *
 * Зачем он тут вообще: под товар считается бюджет и по нему фильтруется архив.
 * Без товара запуск выпал бы из обоих разрезов — деньги ушли бы, а в товарном
 * учёте их бы не было.
 */
/*
 * Разбор ролика для речи ведущего. «Дуэту» разбор механики референса нужен
 * (миграция 202608220006): модель ведущего исходное видео не получает, и всё,
 * что он скажет о ролике, приходит текстом. Поля и пределы — те же, что у
 * нативного редактора мастера (единый список из guided); значения уходят в
 * черновик механики выбранного исходника после привязки.
 */
function duetMechanicsCard() {
  const section = el("section", "gi-card generation-intake-v4__duet-mechanics");
  section.dataset.generationIntakeDuetMechanics = "";
  section.append(
    el("h4", "gi-card__title", "Разбор ролика для речи ведущего"),
    el(
      "p",
      "gi-card__hint",
      "Ведущий видит ролик только вашими словами: что цепляет, из каких шагов он состоит, как снят и чем заканчивается. Это материал его комментария.",
    ),
  );
  const grid = el("div", "generation-intake-v4__duet-mechanics-grid");
  grid.dataset.generationIntakeDuetMechanicsGrid = "";
  section.append(grid);
  return section;
}

// Предел речи ведущего по длительности исходника: та же формула, что у
// серверного снимка prompt — least(duration × 15, 1500). Длительность берётся
// целыми секундами вверх, как её считает цена маршрута.
function duetSpeechLimit(state) {
  const seconds = Number(state?.routes?.avatar_video?.durationSeconds);
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  const whole = Math.ceil(seconds);
  return { seconds: whole, limit: Math.min(whole * 15, 1500) };
}

function duetMechanicsFields() {
  const fields = window.ContentEngineGenerationGuidedV4
    ?.getStrategyMechanicsFields?.();
  return Array.isArray(fields) ? fields : [];
}

function ensureDuetMechanicsInputs(state) {
  const panel = panelFor(state, "avatar_video");
  const grid = panel
    ? q("[data-generation-intake-duet-mechanics-grid]", panel)
    : null;
  if (!(grid instanceof HTMLElement) || grid.childElementCount) return;
  const fields = duetMechanicsFields();
  if (!fields.length) return;
  grid.append(...fields.map((spec) => {
    const control = document.createElement("textarea");
    control.rows = spec.multiline ? 4 : 2;
    control.maxLength = spec.max;
    control.dataset.generationIntakeDuetMechanics = spec.key;
    control.setAttribute("aria-label", spec.label);
    return field(spec.label, spec.hint, control);
  }));
}

function duetMechanicsFromForm(state) {
  const panel = panelFor(state, "avatar_video");
  const values = {};
  qa("textarea[data-generation-intake-duet-mechanics]", panel).forEach((control) => {
    values[control.dataset.generationIntakeDuetMechanics] = String(control.value || "");
  });
  return values;
}

// Та же проверка, что у контракта ТЗ (normalizeMechanics в spec.js), только
// раньше и словами: пустое или короткое поле называется по имени до того, как
// что-либо загружено.
function duetMechanicsProblem(state) {
  const fields = duetMechanicsFields();
  if (!fields.length) return "Поля разбора ролика ещё не загрузились. Обновите страницу (F5).";
  const values = duetMechanicsFromForm(state);
  for (const field of fields) {
    const value = String(values[field.key] || "").trim();
    if (field.key === "beat_sequence") {
      const beats = value.split(/\r?\n/u).map((line) => line.trim()).filter(Boolean);
      if (beats.length < 2 || beats.length > 6) {
        return "«Последовательность битов»: напишите от 2 до 6 шагов, по одному в строке.";
      }
      if (beats.some((beat) => beat.length < 12 || beat.length > 120)) {
        return "«Последовательность битов»: каждый шаг — от 12 до 120 знаков.";
      }
      if (new Set(beats).size !== beats.length) {
        return "«Последовательность битов»: шаги не должны повторяться.";
      }
      continue;
    }
    if (value.length < field.min || value.length > field.max) {
      return `«${field.label}»: от ${field.min} до ${field.max} знаков, сейчас ${value.length}.`;
    }
  }
  return "";
}

function duetProductChooser() {
  const section = el("fieldset", "generation-intake-v4__presenter");
  section.dataset.generationIntakeDuetProduct = "";
  section.append(el("legend", "", "Товар, для которого делаем дуэт *"));

  const select = document.createElement("select");
  select.name = "generation_intake_duet_product_id";
  select.dataset.generationIntakeDuetProductSelect = "";
  select.setAttribute("aria-label", "Товар, под которым оформляется запуск");
  select.append(new Option("Загружаем товары проекта…", ""));
  select.disabled = true;

  const note = el("p", "generation-intake-v4__hint");
  note.dataset.generationIntakeDuetProductNote = "";
  setNodeText(
    note,
    "Ролик комментируют чужой, а бюджет и архив считаются по вашему товару — поэтому его называем отдельно.",
  );

  // Категория товара нигде не хранится у товара — она едет в ТЗ из формы и
  // нужна AI-проверке результата. У «Дуэта» с готовым товаром её раньше было
  // просто негде указать, и подготовка падала на request.product_category.
  const category = document.createElement("select");
  category.dataset.generationIntakeDuetCategory = "";
  category.setAttribute("aria-label", "Категория товара для AI-проверки");
  category.append(new Option("Выберите категорию", ""));
  const categoryField = field(
    "Категория товара *",
    "Нужна AI-проверке готового ролика: для БАД включатся дополнительные предупреждения.",
    category,
  );
  categoryField.dataset.generationIntakeDuetCategoryField = "";

  section.append(select, note, categoryField);
  return section;
}

// Список категорий — ровно тот, что в нативном поле формы: два источника
// одного словаря разошлись бы. Значение зеркалится в натив в обе стороны.
function ensureDuetCategoryControl(form, state) {
  const panel = panelFor(state, "avatar_video");
  const own = panel ? q("[data-generation-intake-duet-category]", panel) : null;
  const native = form?.elements?.product_category;
  if (!(own instanceof HTMLSelectElement) || !(native instanceof HTMLSelectElement)) return;
  const options = [...native.options].map((option) => ({
    label: option.value ? option.textContent : "Выберите категорию",
    value: option.value,
  }));
  syncSelectOptions(own, options.length ? options : [{ label: "Выберите категорию", value: "" }]);
  const nativeValue = String(native.value || "");
  if (nativeValue && own.value !== nativeValue) assignSelectValue(own, nativeValue);
}

/*
 * Перечень товаров выводится из страницы ассетов, а не спрашивается отдельно:
 * товар в проекте появляется вместе со своей первой фотографией, и отдельного
 * списка товаров не существует.
 */
// Список <select> перестраивается ТОЛЬКО при смене набора вариантов. Панель
// перерисовывается на каждую мутацию формы, а рабочий стол перемонтирует
// адаптеры на каждую мутацию дерева: безусловный replaceChildren рождал
// мутацию → перемонтирование → replaceChildren… — вкладка зависала с
// процессором на 100 % сразу после выбора MP4.
function syncSelectOptions(select, options) {
  const stamp = JSON.stringify(options);
  if (select.dataset.optionsStamp === stamp) return false;
  select.dataset.optionsStamp = stamp;
  select.replaceChildren(
    ...options.map(({ label, value }) => new Option(label, value)),
  );
  return true;
}

function assignSelectValue(select, value) {
  const next = String(value ?? "");
  if (select.value !== next) select.value = next;
}

function renderDuetProducts(form, state) {
  const panel = panelFor(state, "avatar_video");
  const section = panel ? q("[data-generation-intake-duet-product]", panel) : null;
  if (!section) return;
  const select = q("[data-generation-intake-duet-product-select]", section);
  const note = q("[data-generation-intake-duet-product-note]", section);
  if (!(select instanceof HTMLSelectElement)) return;

  const products = window.ContentEngineGenerationGuidedV4
    ?.getProjectProducts?.() || [];
  const previous = String(select.value || "");

  if (!products.length) {
    syncSelectOptions(select, [
      { label: "В проекте ещё нет заведённых товаров", value: "" },
    ]);
    if (!select.disabled) select.disabled = true;
    if (note) {
      setNodeText(
        note,
        "Товар заводится вместе с первой своей фотографией — загрузите её на экране «Скопировать ролик», и он появится здесь.",
      );
    }
    return;
  }

  if (select.disabled) select.disabled = false;
  syncSelectOptions(select, [
    { label: "Выберите товар", value: "" },
    ...products.map((product) => ({
      label: product.sku
        ? `${product.product_name} · ${product.sku}`
        : product.product_name,
      value: product.product_id,
    })),
  ]);
  if (products.some((product) => product.product_id === previous)) {
    assignSelectValue(select, previous);
  }
  if (note) {
    setNodeText(
      note,
      "Ролик комментируют чужой, а бюджет и архив считаются по вашему товару — поэтому его называем отдельно.",
    );
  }
}

/*
 * Товар дуэта для наряда. Пустое значение возвращается как пустая строка, а не
 * подставляется «первым попавшимся»: угаданный товар списал бы деньги в чужой
 * бюджет, и заметили бы это только при сверке.
 */
function duetProductIdFromForm(state) {
  const panel = panelFor(state, "avatar_video");
  const select = panel
    ? q("[data-generation-intake-duet-product-select]", panel)
    : null;
  return select instanceof HTMLSelectElement
    ? String(select.value || "").trim().toLowerCase()
    : "";
}

function duetPresenterChooser() {
  const section = el("fieldset", "generation-intake-v4__presenter");
  section.dataset.generationIntakeDuetPresenter = "";
  section.append(el("legend", "", "Ведущий дуэта *"));

  const select = document.createElement("select");
  select.name = "generation_intake_duet_presenter_id";
  select.dataset.generationIntakeDuetPresenterSelect = "";
  select.setAttribute("aria-label", "Ведущий, который комментирует ролик");
  select.append(new Option("Загружаем ведущих проекта…", ""));
  select.disabled = true;

  const note = el("p", "generation-intake-v4__hint");
  note.dataset.generationIntakeDuetPresenterNote = "";
  setNodeText(
    note,
    "Ведущий заводится один раз на проект и остаётся тем же во всех роликах — на этом и держится узнаваемость.",
  );

  // Пока ведущего нет, выключенный select «ещё не заведён» только путал:
  // вместо него — одна строка и раскрытый сценарий заведения ниже.
  const empty = el("p", "generation-intake-v4__presenter-empty");
  empty.dataset.generationIntakeDuetPresenterEmpty = "";
  empty.hidden = true;
  setNodeText(
    empty,
    "Ведущего в проекте ещё нет. Заведите его один раз — ниже, за четыре шага.",
  );

  section.append(select, empty, note, duetLayoutControls(), duetPresenterRegistration());
  return section;
}

/*
 * Регистрация ведущего прямо из формы. Личности берутся из кабинета
 * провайдера (каталог читает сервер, ключ в браузер не приходит): оператор
 * выбирает фото-аватар или видеоаватар и голос, даёт имя — и ведущий
 * становится ведущим проекта. Дальше он тот же во всех роликах.
 */
function presenterStep(number, title, hint, ...controls) {
  const step = el("section", "generation-intake-v4__presenter-step");
  step.dataset.generationIntakeDuetStep = String(number);
  const head = el("h5", "", `${number}. ${title}`);
  step.append(head);
  if (hint) step.append(el("p", "generation-intake-v4__hint", hint));
  step.append(...controls);
  return step;
}

// Вид ведущего решает, нужно ли согласие. Живой человек (сотрудник, актёр,
// блогер — и тем более известное лицо) может стать ведущим только с его
// согласием на внешность и голос; оно записывается один раз вместе с ведущим
// (кто подтвердил и когда), и запуск без него сервер не пропустит. Выдуманный
// персонаж согласия не требует.
const DUET_LIKENESS_KINDS = Object.freeze([
  ["synthetic", "Выдуманный персонаж", "Сгенерированная личность из каталога HeyGen, живого человека за ней нет."],
  ["real_person", "Живой человек", "Аватар снят с реального человека — нужно его согласие на внешность и голос."],
]);

function duetPresenterRegistration() {
  const details = document.createElement("details");
  details.className = "generation-intake-v4__presenter-register";
  details.dataset.generationIntakeDuetRegister = "";
  const summary = document.createElement("summary");
  summary.dataset.generationIntakeDuetRegisterSummary = "";
  setNodeText(summary, "Завести ведущего проекта");
  details.append(summary);

  const hint = el("p", "generation-intake-v4__hint");
  setNodeText(
    hint,
    "Личность и голос берутся из вашего кабинета HeyGen (Avatars → Photo Avatar или Instant Avatar; Voices). Новая личность создаётся там, а не здесь; после создания нажмите «Обновить каталог». Ведущий регистрируется один раз на проект и остаётся тем же во всех роликах.",
  );

  const load = document.createElement("button");
  load.type = "button";
  load.className = "generation-intake-v4__secondary";
  load.dataset.action = "generation-intake-duet-catalog";
  setNodeText(load, "Показать личности и голоса");

  const catalogStatus = el("p", "generation-intake-v4__hint");
  catalogStatus.dataset.generationIntakeDuetCatalogStatus = "";

  const presenter = document.createElement("select");
  presenter.name = "generation_intake_duet_catalog_presenter";
  presenter.dataset.generationIntakeDuetCatalogPresenter = "";
  presenter.setAttribute("aria-label", "Личность ведущего из кабинета провайдера");
  presenter.append(new Option("Сначала загрузите каталог", ""));
  presenter.disabled = true;

  // Превью выбранной личности: человек видит, КОГО заводит, а не только имя.
  const preview = document.createElement("img");
  preview.className = "generation-intake-v4__presenter-preview";
  preview.dataset.generationIntakeDuetCatalogPreview = "";
  preview.alt = "Превью выбранной личности";
  preview.hidden = true;
  preview.loading = "lazy";

  const voice = document.createElement("select");
  voice.name = "generation_intake_duet_catalog_voice";
  voice.dataset.generationIntakeDuetCatalogVoice = "";
  voice.setAttribute("aria-label", "Голос ведущего");
  voice.append(new Option("Сначала загрузите каталог", ""));
  voice.disabled = true;

  // Нет подходящей личности — персонаж собирается по описанию прямо отсюда:
  // сервер просит HeyGen сгенерировать фото-аватар (кредиты кабинета HeyGen,
  // не деньги завода), и готовый образ встаёт в список выше. Это всегда
  // выдуманный персонаж — живого человека за ним нет.
  const generate = document.createElement("details");
  generate.className = "generation-intake-v4__presenter-generate";
  generate.dataset.generationIntakeDuetGenerate = "";
  const generateSummary = document.createElement("summary");
  setNodeText(generateSummary, "Нет подходящей личности? Создать персонажа по описанию");
  const generatePrompt = document.createElement("textarea");
  generatePrompt.name = "generation_intake_duet_generate_prompt";
  generatePrompt.dataset.generationIntakeDuetGeneratePrompt = "";
  generatePrompt.rows = 4;
  generatePrompt.maxLength = 1000;
  generatePrompt.placeholder = "Кто это и как выглядит: возраст, лицо, одежда, обстановка, свет. Например: добродушный мужчина лет пятидесяти с густыми усами, в кепке и фартуке, с шампуром в руке, на фоне мангала, тёплый вечерний свет.";
  generatePrompt.setAttribute("aria-label", "Описание персонажа для генерации");
  const generateButton = document.createElement("button");
  generateButton.type = "button";
  generateButton.className = "btn btn-secondary";
  generateButton.dataset.action = "generation-intake-duet-generate";
  setNodeText(generateButton, "Создать персонажа");
  const generateStatus = el("p", "generation-intake-v4__hint");
  generateStatus.dataset.generationIntakeDuetGenerateStatus = "";
  generate.append(
    generateSummary,
    el("p", "generation-intake-v4__hint", "Образ генерирует HeyGen по вашему описанию (1–3 минуты, списываются кредиты кабинета HeyGen). Имя возьмётся из шага 3 — заполните его заранее. Готовый персонаж появится в списке личностей и будет выбран."),
    labelled("Описание", generatePrompt),
    generateButton,
    generateStatus,
  );

  const name = document.createElement("input");
  name.type = "text";
  name.name = "generation_intake_duet_presenter_name";
  name.dataset.generationIntakeDuetPresenterName = "";
  name.maxLength = 80;
  name.placeholder = "Как зовут ведущего в проекте";
  name.setAttribute("aria-label", "Имя ведущего в проекте");

  const likeness = el("div", "generation-intake-v4__presenter-likeness");
  DUET_LIKENESS_KINDS.forEach(([value, title, description], index) => {
    const option = el("label", "generation-intake-v4__presenter-likeness-option");
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "generation_intake_duet_likeness_kind";
    radio.value = value;
    radio.checked = index === 0;
    radio.dataset.generationIntakeDuetLikenessKind = value;
    option.append(radio, el("strong", "", title), el("span", "generation-intake-v4__hint", description));
    likeness.append(option);
  });
  const consent = el("label", "generation-intake-v4__presenter-consent");
  consent.dataset.generationIntakeDuetLikenessConsentRow = "";
  consent.hidden = true;
  const consentBox = document.createElement("input");
  consentBox.type = "checkbox";
  consentBox.name = "generation_intake_duet_likeness_consent";
  consentBox.dataset.generationIntakeDuetLikenessConsent = "";
  consent.append(
    consentBox,
    el(
      "span",
      "",
      "Подтверждаю: у компании есть письменное согласие этого человека на использование его внешности и голоса в наших роликах. Запись согласия — кто подтвердил и когда — сохраняется вместе с ведущим.",
    ),
  );

  const register = document.createElement("button");
  register.type = "button";
  register.className = "btn btn-primary";
  register.dataset.action = "generation-intake-duet-register";
  register.disabled = true;
  setNodeText(register, "Зарегистрировать ведущего");

  const status = el("p", "generation-intake-v4__hint");
  status.dataset.generationIntakeDuetRegisterStatus = "";

  details.append(
    hint,
    presenterStep(1, "Каталог кабинета HeyGen", "", load, catalogStatus),
    presenterStep(2, "Личность и голос", "", labelled("Личность", presenter), preview, generate, labelled("Голос", voice)),
    presenterStep(3, "Имя в проекте", "Так ведущий будет называться в списках и архиве.", labelled("Имя", name)),
    presenterStep(4, "Кто это", "", likeness, consent),
    register,
    status,
  );
  // Раскрытый сценарий сам читает каталог: один клик меньше, а повторная
  // кнопка остаётся для обновления после создания личности в HeyGen.
  details.addEventListener("toggle", () => {
    if (!details.open || details.dataset.catalogLoaded === "true") return;
    const form = details.closest("form");
    const state = form ? formStates.get(form) : null;
    if (form && state) void loadDuetPresenterCatalog(form, state);
  });
  return details;
}

// Подпись личности до перечитывания каталога: хранится на самом select, потому
// что его options перестраиваются целиком.
function previousLabel(select, value) {
  let remembered = {};
  try {
    remembered = select.dataset.rememberedLabels ? JSON.parse(select.dataset.rememberedLabels) : {};
  } catch {
    remembered = {};
  }
  return String(remembered[value] || "").replace(/ · (фото-аватар|видеоаватар)$/u, "");
}

function rememberPresenterLabel(select, value, label, preview = "") {
  if (!(select instanceof HTMLSelectElement) || !value) return;
  if (preview) select.dataset.rememberedPreview = `${value}|${preview}`;
  let remembered = {};
  try {
    remembered = select.dataset.rememberedLabels ? JSON.parse(select.dataset.rememberedLabels) : {};
  } catch {
    remembered = {};
  }
  remembered[value] = label;
  select.dataset.rememberedLabels = JSON.stringify(remembered);
}

function syncDuetLikenessConsent(block) {
  const kind = q('[data-generation-intake-duet-likeness-kind="real_person"]', block);
  const row = q("[data-generation-intake-duet-likeness-consent-row]", block);
  if (!(row instanceof HTMLElement)) return;
  const real = kind instanceof HTMLInputElement && kind.checked;
  if (row.hidden === real) row.hidden = !real;
}

function syncDuetCatalogPreview(block) {
  const presenterSelect = q("[data-generation-intake-duet-catalog-presenter]", block);
  const preview = q("[data-generation-intake-duet-catalog-preview]", block);
  if (!(presenterSelect instanceof HTMLSelectElement) || !(preview instanceof HTMLImageElement)) return;
  const url = String(presenterSelect.selectedOptions?.[0]?.dataset?.preview || "");
  if (url) {
    if (preview.getAttribute("src") !== url) preview.src = url;
    if (preview.hidden) preview.hidden = false;
  } else {
    if (preview.getAttribute("src")) preview.removeAttribute("src");
    if (!preview.hidden) preview.hidden = true;
  }
}

async function loadDuetPresenterCatalog(form, state) {
  const panel = panelFor(state, "avatar_video");
  const block = panel ? q("[data-generation-intake-duet-register]", panel) : null;
  if (!block) return;
  const presenterSelect = q("[data-generation-intake-duet-catalog-presenter]", block);
  const voiceSelect = q("[data-generation-intake-duet-catalog-voice]", block);
  const register = q('[data-action="generation-intake-duet-register"]', block);
  const load = q('[data-action="generation-intake-duet-catalog"]', block);
  const status = q("[data-generation-intake-duet-catalog-status]", block)
    || q("[data-generation-intake-duet-register-status]", block);
  if (!(presenterSelect instanceof HTMLSelectElement) || !(voiceSelect instanceof HTMLSelectElement)) return;
  setNodeText(status, "Читаем каталог кабинета HeyGen…");
  try {
    const api = await apiRuntime();
    const catalog = await api.duetPresenterCatalog();
    block.dataset.catalogLoaded = "true";
    if (load) setNodeText(load, "Обновить каталог");
    const previouslySelected = String(presenterSelect.value || "");
    presenterSelect.replaceChildren(new Option("Выберите личность", ""));
    catalog.presenters.forEach((item) => {
      const label = `${cleanText(item.name, 60)} · ${item.kind === "avatar" ? "видеоаватар" : "фото-аватар"}`;
      const option = new Option(label, item.id);
      option.dataset.kind = item.kind;
      if (item.preview_image_url) option.dataset.preview = item.preview_image_url;
      presenterSelect.append(option);
    });
    // Выбранная до перечитывания личность (в том числе только что созданный
    // персонаж, которого каталог ещё не показывает) остаётся выбранной.
    if (previouslySelected && ![...presenterSelect.options].some((option) => option.value === previouslySelected)) {
      const keep = new Option(`${cleanText(previousLabel(presenterSelect, previouslySelected), 60) || "Новый персонаж"} · фото-аватар`, previouslySelected);
      keep.dataset.kind = "talking_photo";
      const rememberedPreview = String(presenterSelect.dataset.rememberedPreview || "");
      if (rememberedPreview.startsWith(`${previouslySelected}|`)) {
        keep.dataset.preview = rememberedPreview.slice(previouslySelected.length + 1);
      }
      presenterSelect.append(keep);
    }
    if (previouslySelected) presenterSelect.value = previouslySelected;
    syncDuetCatalogPreview(block);
    voiceSelect.replaceChildren(new Option("Выберите голос", ""));
    catalog.voices.forEach((item) => {
      const meta = [item.language, item.gender].filter(Boolean).join(", ");
      voiceSelect.append(new Option(
        `${cleanText(item.name, 60)}${meta ? ` · ${meta}` : ""}`,
        item.id,
      ));
    });
    presenterSelect.disabled = catalog.presenters.length === 0;
    voiceSelect.disabled = catalog.voices.length === 0;
    if (register instanceof HTMLButtonElement) {
      register.disabled = !(catalog.presenters.length && catalog.voices.length);
    }
    setNodeText(
      status,
      catalog.presenters.length
        ? `Каталог прочитан: личностей ${catalog.presenters.length}, голосов ${catalog.voices.length}. Выберите их на шаге 2.`
        : "В кабинете HeyGen нет ни одной личности. Создайте там фото-аватар или Instant Avatar и нажмите «Обновить каталог».",
    );
  } catch (error) {
    const code = String(error?.code || "");
    setNodeText(
      status,
      code === "duet_provider_key_missing"
        ? "Ключ HeyGen не настроен на сервере (секрет HEYGEN_API_KEY) — без него каталог не прочитать. Выбор ведущего откроется сразу после настройки ключа."
        : `Каталог HeyGen сейчас недоступен: ${cleanText(error?.message, 120) || "ошибка сервера"}. Нажмите «Показать личности и голоса» ещё раз.`,
    );
  }
}

const DUET_GENERATION_POLL_MS = 5_000;
const DUET_GENERATION_DEADLINE_MS = 6 * 60_000;

// Персонаж по описанию: запрос → опрос готовности → образ в списке личностей.
// Кнопка заблокирована на время работы: повторный клик создал бы второго
// персонажа и второй раз списал бы кредиты.
async function generateDuetPresenterFromDescription(form, state) {
  const panel = panelFor(state, "avatar_video");
  const block = panel ? q("[data-generation-intake-duet-register]", panel) : null;
  if (!block) return;
  const promptInput = q("[data-generation-intake-duet-generate-prompt]", block);
  const nameInput = q("[data-generation-intake-duet-presenter-name]", block);
  const button = q('[data-action="generation-intake-duet-generate"]', block);
  const status = q("[data-generation-intake-duet-generate-status]", block);
  const presenterSelect = q("[data-generation-intake-duet-catalog-presenter]", block);
  const prompt = promptInput instanceof HTMLTextAreaElement ? cleanText(promptInput.value, 1000) : "";
  const displayName = nameInput instanceof HTMLInputElement ? cleanText(nameInput.value, 80) : "";
  if (prompt.length < 10) {
    setNodeText(status, "Опишите персонажа хотя бы одной фразой (от 10 знаков).");
    return;
  }
  if (displayName.length < 2) {
    setNodeText(status, "Сначала дайте персонажу имя на шаге 3 — под ним он появится в HeyGen и в проекте.");
    nameInput?.focus?.();
    return;
  }
  if (button instanceof HTMLButtonElement) {
    if (button.disabled) return;
    button.disabled = true;
  }
  try {
    const api = await apiRuntime();
    setNodeText(status, "Просим HeyGen собрать персонажа…");
    const started = await api.duetPresenterGenerate({ name: displayName, prompt, aspectRatio: "9:16" });
    const deadline = Date.now() + DUET_GENERATION_DEADLINE_MS;
    let result = null;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, DUET_GENERATION_POLL_MS));
      result = await api.duetPresenterGenerationStatus(started.lookId);
      if (result.status === "completed" || result.status === "failed") break;
      setNodeText(
        status,
        `HeyGen рисует «${displayName}»… (${Math.round((Date.now() - (deadline - DUET_GENERATION_DEADLINE_MS)) / 1000)} с)`,
      );
    }
    if (!result || result.status !== "completed" || !result.presenter) {
      setNodeText(
        status,
        result?.status === "failed"
          ? `HeyGen не смог собрать персонажа${result.errorMessage ? `: ${result.errorMessage}` : "."} Измените описание и попробуйте снова.`
          : "HeyGen ещё не закончил. Нажмите «Обновить каталог» через минуту — готовый персонаж появится в списке личностей.",
      );
      return;
    }
    if (presenterSelect instanceof HTMLSelectElement) {
      const existing = [...presenterSelect.options].find((option) => option.value === result.presenter.id);
      const option = existing || new Option(
        `${cleanText(result.presenter.name || displayName, 60)} · ${result.presenter.kind === "avatar" ? "видеоаватар" : "фото-аватар"}`,
        result.presenter.id,
      );
      option.dataset.kind = result.presenter.kind;
      if (result.presenter.preview_image_url) option.dataset.preview = result.presenter.preview_image_url;
      if (!existing) presenterSelect.append(option);
      rememberPresenterLabel(presenterSelect, result.presenter.id, option.textContent, result.presenter.preview_image_url || "");
      presenterSelect.disabled = false;
      presenterSelect.value = result.presenter.id;
      syncDuetCatalogPreview(block);
    }
    const register = q('[data-action="generation-intake-duet-register"]', block);
    let voiceSelect = q("[data-generation-intake-duet-catalog-voice]", block);
    // Голоса берутся из каталога; если он ещё не прочитан (или не прочитался),
    // читаем его сейчас — иначе персонаж есть, а голос выбрать негде. Каталог
    // перестраивает список личностей, поэтому выбранный персонаж возвращается
    // в него после чтения.
    if (!(voiceSelect instanceof HTMLSelectElement) || voiceSelect.disabled) {
      setNodeText(status, `Персонаж «${displayName}» готов. Читаем голоса из каталога HeyGen…`);
      await loadDuetPresenterCatalog(form, state);
      voiceSelect = q("[data-generation-intake-duet-catalog-voice]", block);
      if (presenterSelect instanceof HTMLSelectElement) {
        let option = [...presenterSelect.options].find((entry) => entry.value === result.presenter.id);
        if (!option) {
          option = new Option(`${cleanText(result.presenter.name || displayName, 60)} · фото-аватар`, result.presenter.id);
          option.dataset.kind = result.presenter.kind;
          if (result.presenter.preview_image_url) option.dataset.preview = result.presenter.preview_image_url;
          presenterSelect.append(option);
        }
        rememberPresenterLabel(presenterSelect, result.presenter.id, option.textContent, result.presenter.preview_image_url || "");
        if (result.presenter.preview_image_url) option.dataset.preview = result.presenter.preview_image_url;
        presenterSelect.disabled = false;
        presenterSelect.value = result.presenter.id;
        syncDuetCatalogPreview(block);
      }
    }
    const voicesReady = voiceSelect instanceof HTMLSelectElement && !voiceSelect.disabled;
    if (register instanceof HTMLButtonElement && voicesReady) register.disabled = false;
    setNodeText(
      status,
      voicesReady
        ? `Персонаж «${displayName}» готов и выбран${result.presenter.catalog_confirmed ? "" : " (каталог HeyGen ещё не показал его — это нормально)"}. Выберите голос ниже и зарегистрируйте ведущего как выдуманного персонажа.`
        : `Персонаж «${displayName}» готов и выбран, но каталог голосов HeyGen не прочитался. Нажмите «Показать личности и голоса» в шаге 1 и затем выберите голос.`,
    );
    const generateDetails = block.querySelector("[data-generation-intake-duet-generate]");
    if (generateDetails instanceof HTMLDetailsElement) generateDetails.open = false;
  } catch (error) {
    const hint = cleanText(error?.hint, 200);
    setNodeText(
      status,
      `${cleanText(error?.message, 160) || "Не удалось создать персонажа."}${hint ? ` HeyGen: ${hint}` : ""}`,
    );
  } finally {
    if (button instanceof HTMLButtonElement) button.disabled = false;
  }
}

async function registerDuetPresenterFromForm(form, state) {
  const panel = panelFor(state, "avatar_video");
  const block = panel ? q("[data-generation-intake-duet-register]", panel) : null;
  if (!block) return;
  const presenterSelect = q("[data-generation-intake-duet-catalog-presenter]", block);
  const voiceSelect = q("[data-generation-intake-duet-catalog-voice]", block);
  const nameInput = q("[data-generation-intake-duet-presenter-name]", block);
  const status = q("[data-generation-intake-duet-register-status]", block);
  const presenterId = presenterSelect instanceof HTMLSelectElement
    ? String(presenterSelect.value || "").trim()
    : "";
  const kind = presenterSelect instanceof HTMLSelectElement
    ? String(presenterSelect.selectedOptions?.[0]?.dataset?.kind || "talking_photo")
    : "talking_photo";
  const voiceId = voiceSelect instanceof HTMLSelectElement
    ? String(voiceSelect.value || "").trim()
    : "";
  const displayName = nameInput instanceof HTMLInputElement
    ? cleanText(nameInput.value, 80)
    : "";
  const likenessKind = q('[data-generation-intake-duet-likeness-kind="real_person"]', block)?.checked
    ? "real_person"
    : "synthetic";
  const consentBox = q("[data-generation-intake-duet-likeness-consent]", block);
  const likenessConsentConfirmed = consentBox instanceof HTMLInputElement && consentBox.checked;
  if (!presenterId || !voiceId) {
    setNodeText(status, "Шаг 2: выберите личность и голос.");
    return;
  }
  if (displayName.length < 2) {
    setNodeText(status, "Шаг 3: дайте ведущему имя — хотя бы два знака.");
    return;
  }
  if (likenessKind === "real_person" && !likenessConsentConfirmed) {
    setNodeText(
      status,
      "Шаг 4: живого человека нельзя завести без его согласия на внешность и голос — поставьте подтверждение или выберите «Выдуманный персонаж».",
    );
    return;
  }
  setNodeText(status, "Регистрируем ведущего…");
  try {
    const api = await apiRuntime();
    const presenter = await api.registerDuetPresenter(projectId(), {
      displayName,
      providerAvatarId: presenterId,
      providerAvatarKind: kind,
      providerVoiceId: voiceId,
      isDefault: true,
      likenessKind,
      likenessConsentConfirmed,
    });
    duetPresenterCache.delete(projectId());
    duetPresentersLoaded.delete(projectId());
    await ensureDuetPresenters(form, state);
    const select = q("[data-generation-intake-duet-presenter-select]", panel);
    if (select instanceof HTMLSelectElement && presenter?.id) {
      select.value = String(presenter.id);
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
    setNodeText(status, `Ведущий «${displayName}» зарегистрирован и выбран.`);
    const details = block.closest("details");
    if (details instanceof HTMLDetailsElement) details.open = false;
  } catch (error) {
    const code = String(error?.code || error?.message || "");
    setNodeText(
      status,
      code === "duet_presenter_likeness_consent_required"
        ? "Сервер отказал: для живого человека нужно записанное согласие. Поставьте подтверждение на шаге 4."
        : `Не удалось зарегистрировать ведущего: ${cleanText(error?.message, 160) || "ошибка сервера"}.`,
    );
  }
}

/*
 * Раскладка врезки. Значения приходят от выбранного ведущего и служат
 * умолчанием; здесь их можно переопределить для конкретного ролика.
 */
function duetLayoutControls() {
  const layout = el("div", "generation-intake-v4__presenter-layout");
  layout.dataset.generationIntakeDuetLayout = "";

  const corner = document.createElement("select");
  corner.name = "generation_intake_duet_corner";
  corner.dataset.generationIntakeDuetCorner = "";
  corner.setAttribute("aria-label", "Где встанет ведущий");
  DUET_CORNERS.forEach(([value, title]) => corner.append(new Option(title, value)));

  const shape = document.createElement("select");
  shape.name = "generation_intake_duet_shape";
  shape.dataset.generationIntakeDuetShape = "";
  shape.setAttribute("aria-label", "Вид врезки");
  DUET_SHAPES.forEach(([value, title]) => shape.append(new Option(title, value)));

  const width = document.createElement("input");
  width.type = "range";
  width.name = "generation_intake_duet_width";
  width.dataset.generationIntakeDuetWidth = "";
  width.min = String(DUET_WIDTH_MIN);
  width.max = String(DUET_WIDTH_MAX);
  width.step = "1";
  width.value = "34";
  width.setAttribute("aria-label", "Размер ведущего в кадре");

  const widthValue = el("span", "generation-intake-v4__presenter-width");
  widthValue.dataset.generationIntakeDuetWidthValue = "";
  setNodeText(widthValue, "34% ширины кадра");

  layout.append(
    labelled("Где", corner),
    labelled("Вид", shape),
    labelled("Размер", width, widthValue),
  );
  return layout;
}

function labelled(title, control, extra = null) {
  const label = el("label", "generation-intake-v4__presenter-field");
  label.append(el("span", "", title), control);
  if (extra) label.append(extra);
  return label;
}

async function ensureDuetPresenters(form, state) {
  const projectIdValue = projectId();
  if (!projectIdValue) return [];
  if (duetPresenterCache.has(projectIdValue)) {
    return duetPresenterCache.get(projectIdValue);
  }
  // Пустой список кладётся в кэш тоже: без ведущего дуэт не запустить, и
  // спрашивать об этом сервер на каждой перерисовке незачем.
  duetPresenterCache.set(projectIdValue, []);
  try {
    const api = await apiRuntime();
    const presenters = await api.duetPresenters(projectIdValue);
    duetPresenterCache.set(projectIdValue, presenters);
    duetPresentersLoaded.add(projectIdValue);
  } catch {
    // Отказ списка не ломает форму: панель скажет, что ведущего нет, а запуск
    // и без того упрётся в серверную проверку.
    duetPresenterCache.set(projectIdValue, []);
  }
  renderDuetPresenters(form, state);
  return duetPresenterCache.get(projectIdValue);
}

function renderDuetPresenters(form, state) {
  const panel = panelFor(state, "avatar_video");
  const section = panel
    ? q("[data-generation-intake-duet-presenter]", panel)
    : null;
  if (!section) return;
  const select = q("[data-generation-intake-duet-presenter-select]", section);
  const note = q("[data-generation-intake-duet-presenter-note]", section);
  const layout = q("[data-generation-intake-duet-layout]", section);
  if (!(select instanceof HTMLSelectElement)) return;

  const presenters = duetPresenterCache.get(projectId()) || [];
  const previous = String(select.value || "");

  const empty = q("[data-generation-intake-duet-presenter-empty]", section);
  const register = q("[data-generation-intake-duet-register]", section);
  const registerSummary = q("[data-generation-intake-duet-register-summary]", section);
  if (!presenters.length) {
    syncSelectOptions(select, [
      { label: "Ведущий проекта ещё не заведён", value: "" },
    ]);
    if (!select.disabled) select.disabled = true;
    if (!select.hidden) select.hidden = true;
    if (empty instanceof HTMLElement && empty.hidden) empty.hidden = false;
    if (layout instanceof HTMLElement && !layout.hidden) layout.hidden = true;
    if (note && !note.hidden) note.hidden = true;
    // Сценарий заведения раскрыт сам: человеку не нужно догадываться, что
    // под свёрнутой строкой прячется единственный путь дальше.
    if (
      register instanceof HTMLDetailsElement
      && duetPresentersLoaded.has(projectId())
      && register.dataset.autoOpened !== "true"
    ) {
      register.dataset.autoOpened = "true";
      register.open = true;
    }
    if (registerSummary) setNodeText(registerSummary, "Завести ведущего проекта");
    return;
  }

  if (select.disabled) select.disabled = false;
  if (select.hidden) select.hidden = false;
  if (empty instanceof HTMLElement && !empty.hidden) empty.hidden = true;
  if (note && note.hidden) note.hidden = false;
  if (registerSummary) setNodeText(registerSummary, "Сменить или добавить ведущего");
  if (layout instanceof HTMLElement && layout.hidden) layout.hidden = false;
  syncSelectOptions(select, presenters.map((presenter) => ({
    label: `${cleanText(presenter.display_name, 60)}${
      presenter.is_default ? " · по умолчанию" : ""
    }`,
    value: String(presenter.id || ""),
  })));
  const restored = presenters.some((presenter) => String(presenter.id) === previous)
    ? previous
    : String(
      (presenters.find((presenter) => presenter.is_default) || presenters[0]).id,
    );
  assignSelectValue(select, restored);
  // Раскладка ведущего — умолчание для ЭТОГО ролика, и подставляется она при
  // смене ведущего, а не на каждой перерисовке: иначе угол и форма, которые
  // оператор выставил под конкретный ролик, откатывались бы сами собой.
  if (select.dataset.layoutPresenter !== restored) {
    select.dataset.layoutPresenter = restored;
    applyDuetPresenterLayout(section, presenters, restored);
  }
  if (note) {
    setNodeText(
      note,
      "Ведущий остаётся тем же во всех роликах проекта — на этом и держится узнаваемость. Раскладку ниже можно поменять для конкретного ролика.",
    );
  }
}

/*
 * Раскладка выбранного ведущего становится умолчанием формы. Это и есть смысл
 * хранить её у него: «наша Аня всегда слева внизу вырезом» задаётся один раз, а
 * не выставляется заново при каждом запуске.
 */
function applyDuetPresenterLayout(section, presenters, presenterId) {
  const presenter = presenters.find(
    (candidate) => String(candidate.id) === String(presenterId),
  );
  if (!presenter) return;
  const corner = q("[data-generation-intake-duet-corner]", section);
  const shape = q("[data-generation-intake-duet-shape]", section);
  const width = q("[data-generation-intake-duet-width]", section);
  if (corner instanceof HTMLSelectElement && presenter.overlay_corner) {
    corner.value = String(presenter.overlay_corner);
  }
  if (shape instanceof HTMLSelectElement && presenter.overlay_shape) {
    shape.value = String(presenter.overlay_shape);
  }
  if (width instanceof HTMLInputElement && presenter.overlay_width_percent) {
    width.value = String(presenter.overlay_width_percent);
  }
  syncDuetWidthLabel(section);
}

function syncDuetWidthLabel(section) {
  const width = q("[data-generation-intake-duet-width]", section);
  const value = q("[data-generation-intake-duet-width-value]", section);
  if (!(width instanceof HTMLInputElement) || !value) return;
  setNodeText(value, `${width.value}% ширины кадра`);
}

/*
 * Раскладка для наряда. Читается из формы, а не из записи ведущего: оператор
 * мог переопределить её для этого ролика.
 */
function duetPresenterIdFromForm(state) {
  const panel = panelFor(state, "avatar_video");
  const select = panel
    ? q("[data-generation-intake-duet-presenter-select]", panel)
    : null;
  const value = select instanceof HTMLSelectElement
    ? String(select.value || "").trim().toLowerCase()
    : "";
  // Пустая строка вместо мусора: сервер отвергнет и то и другое, но пустое
  // значение читается как «ведущий не выбран», а мусор — как ошибка формы.
  return UUID_PATTERN.test(value) ? value : "";
}

function duetLayoutFromForm(state) {
  const panel = panelFor(state, "avatar_video");
  const section = panel
    ? q("[data-generation-intake-duet-presenter]", panel)
    : null;
  if (!section) return null;
  const corner = q("[data-generation-intake-duet-corner]", section);
  const shape = q("[data-generation-intake-duet-shape]", section);
  const width = q("[data-generation-intake-duet-width]", section);
  const widthPercent = Number.parseInt(
    width instanceof HTMLInputElement ? width.value : "",
    10,
  );
  return {
    corner: corner instanceof HTMLSelectElement ? corner.value : "",
    shape: shape instanceof HTMLSelectElement ? shape.value : "",
    // Значение за пределами не отправляется вовсе: сборщик его всё равно
    // отвергнет, но уже после того, как за ведущего заплачено.
    widthPercent: Number.isInteger(widthPercent)
        && widthPercent >= DUET_WIDTH_MIN
        && widthPercent <= DUET_WIDTH_MAX
      ? widthPercent
      : null,
  };
}

function avatarIdentityChooser() {
  const section = el("fieldset", "generation-intake-v4__avatar");
  section.append(el("legend", "", "Как задать аватара *"));
  const choices = el("div", "generation-intake-v4__avatar-choices");
  [
    ["photo", "Фото аватара"],
    ["description", "Описание аватара"],
  ].forEach(([value, title], index) => {
    const label = el("label", "generation-intake-v4__choice");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "generation_intake_avatar_input_mode";
    input.value = value;
    input.dataset.generationIntakeAvatarMode = value;
    input.checked = index === 0;
    label.append(input, el("span", "", title));
    choices.append(label);
  });

  const photoPanel = el("div", "generation-intake-v4__avatar-mode");
  photoPanel.dataset.generationIntakeAvatarModePanel = "photo";
  const photo = imageInput({ purpose: "avatar" });
  photo.id = "generation-intake-avatar-image";
  const upload = el("label", "generation-intake-v4__drop generation-intake-v4__drop--compact");
  upload.htmlFor = photo.id;
  upload.append(
    el("strong", "", "Загрузить одно фото аватара"),
    el("span", "", "Лицо хорошо видно · JPG, PNG или WEBP"),
    photo,
  );
  const existing = document.createElement("select");
  existing.dataset.generationIntakeExistingAvatar = "";
  existing.append(new Option("Не выбрано фото из проекта", ""));
  const consent = el("label", "generation-intake-v4__confirmation");
  const consentInput = document.createElement("input");
  consentInput.type = "checkbox";
  consentInput.dataset.generationIntakeAvatarConsent = "";
  consent.append(
    consentInput,
    el("span", "", "Есть согласие на использование внешности и создание этого видео."),
  );
  photoPanel.append(
    upload,
    field(
      "Или выбрать фото из проекта",
      "Подходят только доступные текущему проекту creator reference или фотографии с подтверждёнными правами.",
      existing,
    ),
    consent,
  );

  const descriptionPanel = el("div", "generation-intake-v4__avatar-mode");
  descriptionPanel.dataset.generationIntakeAvatarModePanel = "description";
  descriptionPanel.hidden = true;
  const wishes = document.createElement("textarea");
  wishes.rows = 5;
  wishes.maxLength = 1_200;
  wishes.placeholder = "Например: уверенная девушка 25–30 лет, тёмные волосы, лаконичная одежда, спокойная живая мимика…";
  wishes.dataset.generationIntakeField = "avatar_wishes";
  descriptionPanel.append(field(
    "Описание аватара",
    "Внешность, возрастной образ, одежда и характер. Технический промпт не нужен.",
    wishes,
  ));

  section.append(choices, photoPanel, descriptionPanel);
  return section;
}

const PRODUCT_CATEGORY_OPTIONS = Object.freeze([
  ["", "Выберите один раз"],
  ["cosmetics", "Косметика и уход"],
  ["baa", "БАД — зарегистрированный БАД"],
  ["sports_food", "Протеин и спортивное питание"],
  ["food", "Еда и напитки"],
  ["household", "Товары для дома"],
  ["apparel", "Одежда и аксессуары"],
  ["electronics", "Электроника"],
  ["other", "Другая категория"],
]);

function productIdentityFields() {
  const wrap = el("div", "generation-intake-v4__identity");
  wrap.dataset.generationIntakeIdentity = "";
  const sku = el("input");
  sku.type = "text";
  sku.maxLength = 120;
  sku.autocomplete = "off";
  sku.placeholder = "Например: BB-GRANOLA-40";
  sku.dataset.generationIntakeField = "sku";
  const name = el("input");
  name.type = "text";
  name.maxLength = 180;
  name.autocomplete = "off";
  name.placeholder = "Например: Батончик Bombbar 40 г";
  name.dataset.generationIntakeField = "product_name";
  const category = el("select");
  category.dataset.generationIntakeField = "product_category";
  category.replaceChildren(...PRODUCT_CATEGORY_OPTIONS.map(
    ([value, label]) => new Option(label, value),
  ));
  const skuField = field(
    "Артикул (SKU) вашего товара",
    "Нужен при загрузке новых фотографий: они привяжутся к точному товару.",
    sku,
  );
  skuField.dataset.generationIntakeIdentityItem = "sku";
  const nameField = field(
    "Название товара",
    "Как в карточке товара. Вместе с артикулом делает фото пригодными для запуска.",
    name,
  );
  nameField.dataset.generationIntakeIdentityItem = "product_name";
  const categoryField = field(
    "Категория товара",
    "Нужна серверному ТЗ: определяет правила безопасности и допустимые обещания.",
    category,
  );
  categoryField.dataset.generationIntakeIdentityItem = "product_category";
  wrap.append(skuField, nameField, categoryField);
  return wrap;
}

function identityInput(state, fieldName) {
  return q(
    `[data-generation-intake-identity] [data-generation-intake-field="${CSS.escape(fieldName)}"]`,
    state.shell,
  );
}

function prefillIdentityFields(form, state) {
  ["sku", "product_name", "product_category"].forEach((fieldName) => {
    const target = identityInput(state, fieldName);
    const source = form.elements?.[fieldName];
    if (
      !(target instanceof HTMLInputElement)
      && !(target instanceof HTMLSelectElement)
    ) return;
    const value = String(source?.value || "");
    if (value && !target.value) target.value = value;
  });
}

function syncIdentityToForm(form, fieldName, value) {
  const control = form.elements?.[fieldName];
  if (
    !(control instanceof HTMLInputElement)
    && !(control instanceof HTMLTextAreaElement)
    && !(control instanceof HTMLSelectElement)
  ) return;
  if (control.value === value) return;
  control.value = value;
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
}

// Что оператор просит сохранить из исходника. Каждый чип — один код механики,
// который уходит в поле preserve наряда; звук дополнительно ведёт служебный
// селект, чтобы цена и рецепт считались от того же выбора.
const COPY_PRESERVE_CHIPS = Object.freeze([
  { code: "actions", label: "Движение", on: true },
  { code: "editing", label: "Монтаж", on: true },
  { code: "camera", label: "Ракурсы", on: true },
  { code: "timing", label: "Темп", on: true },
  { code: "audio", label: "Звук", on: false },
]);

function copyPreserveChips() {
  const section = el("section", "gi-card");
  section.dataset.giStep = "3";
  const row = el("div", "gi-chips");
  row.dataset.generationIntakePreserve = "";
  COPY_PRESERVE_CHIPS.forEach(({ code, label, on }) => {
    const chip = el("label", "gi-chip");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.dataset.generationIntakePreserveCode = code;
    input.checked = on;
    chip.append(input, el("span", "", label));
    row.append(chip);
  });
  section.append(
    el("h4", "gi-card__title", "3. Что нужно сохранить?"),
    row,
    el("p", "gi-card__hint", "Выберите главное — остальное система подстроит сама."),
  );
  return section;
}

function selectedPreserveCodes(panel) {
  const codes = qa("[data-generation-intake-preserve-code]", panel)
    .filter((input) => input.checked)
    .map((input) => String(input.dataset.generationIntakePreserveCode || ""));
  // Без единого выбранного признака копировать нечего: держим механику
  // движения как минимальную опору, иначе рецепт останется без указаний.
  return codes.length ? codes : ["actions"];
}

// Каскад выбора движка: три ступени одна под другой — уровень, модели этого
// уровня, допустимая длительность выбранной модели. Всё содержимое приходит из
// реестра маршрутов (catalog.strategyProviderRoutes); браузер ничего не
// достраивает. Прежний одиночный ряд «Генератор 1/2/3» стал второй ступенью:
// два конкурирующих переключателя движка на экране недопустимы.
const TIER_ORDER = Object.freeze(["cheap", "medium", "premium"]);
const TIER_LABELS = Object.freeze({
  cheap: "Дёшево",
  medium: "Средне",
  premium: "Дорого",
});

const PROVIDER_LABELS = Object.freeze({
  fal: "fal.ai",
  runway: "Runway",
  google: "Google",
});

// Идентификатор вида fal-ai/... человеку показывать нельзя. Для сверенных
// маршрутов имя задано точно; незнакомая модель получает аккуратный разбор
// model_key, а не пустое место.
const MODEL_PUBLIC_LABELS = Object.freeze({
  "fal:fal-ai/pika/v2/pikaswaps": "Pika Swaps",
  "runway:aleph2": "Runway Aleph",
  "fal:fal-ai/kling-video/o3/pro/video-to-video/edit": "Kling O3 Pro",
  // Движки «Копии», заведённые 23.08.2026 (миграция 202608230020).
  "fal:fal-ai/kling-video/o3/standard/video-to-video/edit": "Kling O3 Standard",
  "fal:alibaba/happy-horse/video-edit": "Happy Horse Edit",
  "fal:bytedance/seedance-2.5/reference-to-video": "Seedance 2.5",
  "fal:minimax/h3/reference-to-video": "MiniMax H3",
  // Движки «Создания» (миграция 202608230021).
  "fal:xai/grok-imagine-video/reference-to-video": "Grok Imagine",
  "fal:alibaba/happy-horse/reference-to-video": "Happy Horse",
  // «Создание» на Runway (29.08.2026): настоящий image_to_video, а не
  // несуществующий рецепт.
  "runway:gen4_turbo": "Runway Gen-4 Turbo",
});

// Что движок делает с роликом — словами человека. Приходит из реестра
// (engine_family); незнакомое семейство не получает описания вместо честного
// молчания.
const ENGINE_FAMILY_LABELS = Object.freeze({
  edit: "правит кадр исходника",
  regenerate: "пересобирает ролик по референсу",
  overlay: "накладывает поверх нетронутого ролика",
});

function engineId(route) {
  return `${String(route?.provider || "")}:${String(route?.model_key || "")}`;
}

function providerPublicLabel(provider) {
  const key = String(provider || "").trim().toLowerCase();
  return PROVIDER_LABELS[key] || cleanText(provider, 24) || "провайдер";
}

function tierPublicLabel(tier) {
  const key = String(tier || "").trim().toLowerCase();
  return TIER_LABELS[key] || cleanText(tier, 24) || "Уровень";
}

// Запасное имя модели: из model_key убирается вендорный префикс и версии,
// остаток разбивается на слова. «fal-ai/kling-video/o3/pro/…» читается как
// «Kling Video O3 Pro» — длинно, но это имя, а не идентификатор.
function fallbackModelLabel(modelKey) {
  const words = String(modelKey || "")
    .split("/")
    .filter((part) => part && !/^(fal-ai|fal|runway|google|v\d+(\.\d+)?)$/iu.test(part))
    .join(" ")
    .split(/[-_\s]+/u)
    .filter(Boolean)
    .map((word) => (/^\p{Ll}/u.test(word)
      ? word[0].toUpperCase() + word.slice(1)
      : word));
  return words.slice(0, 4).join(" ").slice(0, 40).trim() || "Модель без имени";
}

function modelPublicLabel(route) {
  return MODEL_PUBLIC_LABELS[engineId(route)]
    || fallbackModelLabel(route?.model_key);
}

function usdFromMinor(minor) {
  return `$${(Number(minor) / 100).toFixed(2)}`;
}

// Цена маршрута словами. Реестр знает три вида прайса, и там, где ставки нет
// (ступени кредитов Runway), сумма НЕ придумывается: её назовёт сервер
// бесплатной проверкой.
function routePriceNote(engine) {
  if (engine?.priceKind === "usd_minor_per_run" && engine.priceRateMinor) {
    return `${usdFromMinor(engine.priceRateMinor)} за ролик целиком`;
  }
  if (engine?.priceKind === "usd_minor_per_second" && engine.priceRateMinor) {
    return `${usdFromMinor(engine.priceRateMinor)} за секунду`;
  }
  if (engine?.priceKind === "runway_credit_tiers") return "по ступеням кредитов";
  return "цену назовёт сервер";
}

function engineVisualKey(engine) {
  const id = String(engine?.id || "").toLowerCase();
  if (id.includes("pika")) return "pika";
  if (id.includes("kling")) return "kling";
  if (id.includes("runway") || id.includes("aleph")) return "runway";
  if (id.includes("happy-horse")) return "happyhorse";
  if (id.includes("seedance")) return "seedance";
  if (id.includes("minimax")) return "minimax";
  if (id.includes("grok")) return "grok";
  if (id.includes("heygen")) return "heygen";
  return "model";
}

// Профиль входа движка из реестра (input_profile): сколько фото он возьмёт,
// какой исходник ему нужен, останется ли звук. Ничего не достраивается: про
// движок без профиля экран говорит ровно то, что знает.
function engineInputNote(engine) {
  const profile = engine?.inputProfile;
  if (!profile) return "";
  const parts = [];
  const family = ENGINE_FAMILY_LABELS[engine.engineFamily];
  if (family) parts.push(family);
  const images = Number(profile.images?.max);
  if (Number.isFinite(images)) {
    parts.push(images === 0
      ? "фото товара не принимает"
      : images === 1
        ? "одно фото товара"
        : `до ${images} фото товара`);
  }
  const minSide = Number(profile.video?.min_short_side_px);
  if (Number.isFinite(minSide) && minSide > 0) {
    parts.push(`исходник от ${minSide}px по короткой стороне`);
  }
  if (profile.keeps_source_audio === true) parts.push("звук исходника сохраняется");
  else if (profile.keeps_source_audio === false) parts.push("звук исходника не сохраняется");
  return parts.join(" · ");
}

// Решётка секунд движка — свойство модели, как форма тела запроса: у Runway
// Gen-4 Turbo параметр duration принимает РОВНО 5 или 10. Окно min/max
// реестра дискретность не выражает; та же решётка стоит в цене маршрута
// (gen4_turbo_duration_lattice) и в адаптере отправки — три слоя обязаны
// двигаться вместе.
const ENGINE_DURATION_CHOICES = Object.freeze({
  "runway:gen4_turbo": Object.freeze([5, 10]),
});

function engineDurationLattice(engine) {
  const lattice = ENGINE_DURATION_CHOICES[String(engine?.id || "")];
  return Array.isArray(lattice) ? lattice : null;
}

function engineDurationNote(engine) {
  const minimum = Number(engine?.minDurationSeconds);
  const maximum = Number(engine?.maxDurationSeconds);
  const hasWindow = Number.isFinite(minimum)
    && Number.isFinite(maximum)
    && minimum > 0
    && maximum >= minimum;
  if (engine?.durationSource === "source_video") {
    return hasWindow
      ? `как в MP4 · допустимо ${minimum}–${maximum} с`
      : "как в проверенном MP4";
  }
  if (!hasWindow) return "диапазон подтвердит сервер";
  const lattice = engineDurationLattice(engine);
  if (lattice) return `${lattice.join(" или ")} с`;
  return minimum === maximum ? `${minimum} с` : `${minimum}–${maximum} с`;
}

// Факты о запуске для совета ИИ-центра. Берётся только то, что уже известно
// экрану: измеренная сервером длительность исходника, сколько фото товара
// отмечено, категория и замысел. Неизвестное остаётся null — советчик не
// достраивает факты.
function copyEngineFacts(form, state) {
  let sourceDurationSeconds = null;
  try {
    sourceDurationSeconds = verifiedSourceDurationSeconds(form);
  } catch {
    sourceDurationSeconds = null;
  }
  let productImageCount = 0;
  try {
    productImageCount = orderedCheckedProductInputs(form).length;
  } catch {
    productImageCount = 0;
  }
  return {
    sourceDurationSeconds,
    sourceShortSidePx: null,
    productImageCount,
    productCategory: String(
      identityInput(state, "product_category")?.value
      || form?.elements?.product_category?.value
      || "",
    ).trim(),
    brief: String(form?.elements?.brief?.value || "").trim(),
    budgetMinorPerRun: null,
  };
}

// Факты для «Создания»: исходник провайдеру не уходит, поэтому его длина не
// важна; важны фото товара, категория, замысел и выбранная длительность.
function rebuildEngineFacts(form, state) {
  let productImageCount = 0;
  try {
    productImageCount = orderedCheckedProductInputs(form).length;
  } catch {
    productImageCount = 0;
  }
  const requested = Number(form?.elements?.generation_strategy_duration_seconds?.value);
  return {
    sourceDurationSeconds: null,
    requestedDurationSeconds: Number.isFinite(requested) && requested > 0 ? requested : null,
    sourceShortSidePx: null,
    productImageCount,
    productCategory: String(
      identityInput(state, "product_category")?.value
      || form?.elements?.product_category?.value
      || "",
    ).trim(),
    brief: String(form?.elements?.brief?.value || "").trim(),
    budgetMinorPerRun: null,
  };
}

// Подпись под каскадом: что советует ИИ-центр и почему, и что исполнится на
// самом деле. Совет и исполнение называются отдельно всегда — даже когда они
// совпадают, чтобы человек видел, что выбор остаётся за ним.
function engineAdviceNote(
  selectedEngine,
  advisedEngine,
  advice,
  { advised = true, engineCount = 0 } = {},
) {
  if (!selectedEngine?.enabled) {
    return "Эта модель пока недоступна — выберите другую, иначе запуск выполнит маршрут по умолчанию.";
  }
  // У стратегии без советчика («Дуэт») честная подпись: совета нет, выбор —
  // умолчание реестра или человека. Раньше здесь печаталось «ИИ-центр
  // советует…» по флагу таблицы.
  if (!advised) {
    return engineCount <= 1
      ? `Исполнит «${selectedEngine.label}» — единственный движок этой стратегии; ИИ-центр здесь не советует.`
      : `Исполнит «${selectedEngine.label}» — умолчание реестра или ваш выбор; ИИ-центр для этой стратегии не советует.`;
  }
  const reasons = Array.isArray(advice?.reasons) && advice.reasons.length
    ? `: ${advice.reasons.slice(0, 3).join("; ")}`
    : "";
  const excluded = Array.isArray(advice?.excluded) && advice.excluded.length
    ? ` Отсеяно: ${advice.excluded.slice(0, 2).map((item) => (
      `${engineLabelById(item.engineId)} — ${item.reason}`
    )).join("; ")}.`
    : "";
  if (!advisedEngine) {
    return `ИИ-центру нечего посоветовать для этого запуска${reasons}. Исполнит «${selectedEngine.label}» — выбор человека.${excluded}`;
  }
  if (advisedEngine.id === selectedEngine.id) {
    return `ИИ-центр советует «${selectedEngine.label}»${reasons}. Исполнит «${selectedEngine.label}»; человек может выбрать другую модель до бесплатной проверки.${excluded}`;
  }
  return `ИИ-центр советует «${advisedEngine.label}»${reasons}. Исполнит «${selectedEngine.label}» — выбор человека важнее совета. Точную сумму подтвердит сервер.${excluded}`;
}

function engineLabelById(engineId) {
  const [provider, ...rest] = String(engineId || "").split(":");
  return modelPublicLabel({ provider, model_key: rest.join(":") });
}

function engineConditionNote(engine) {
  if (!engine?.enabled) return "маршрут временно недоступен";
  const input = engineInputNote(engine);
  if (input) {
    return engine.durationSource === "source_video"
      ? `${input} · нужен MP4 с серверной проверкой длительности`
      : input;
  }
  if (engine.durationSource === "source_video") {
    return "нужен MP4 с серверной проверкой длительности";
  }
  const modes = Array.isArray(engine.qualityModes) ? engine.qualityModes.length : 0;
  if (modes > 1) return `${modes} режима качества на выбор`;
  if (modes === 1) return "качество задаёт маршрут";
  return "условия подтвердит бесплатная проверка";
}

function chipRow(name, kind) {
  const row = el("div", "gi-chips gi-chips--radio");
  row.dataset.generationIntakeChoice = kind;
  row.dataset.choiceName = name;
  return row;
}

// Панель слушает собственные мутации, поэтому ряд перерисовывается только при
// смене отпечатка: безусловный replaceChildren уводит наблюдатель в цикл и
// вешает вкладку намертво.
function renderChoiceChips(row, options, selectedValue) {
  const name = row.dataset.choiceName;
  const kind = String(row.dataset.generationIntakeChoice || "");
  const stamp = JSON.stringify([selectedValue || "", options]);
  if (row.dataset.stamp === stamp) return;
  row.dataset.stamp = stamp;
  row.replaceChildren(...options.map((option) => {
    const chip = el("label", "gi-chip gi-chip--choice");
    if (kind === "model") chip.classList.add("gi-model-choice");
    if (option.recommended) chip.dataset.recommended = "true";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = name;
    input.value = option.value;
    input.checked = option.value === selectedValue;
    // Недоступный движок показывается, но не выбирается: экран не умалчивает
    // о нём и не даёт выбрать то, что сервер выполнить не сможет.
    if (option.disabled) {
      input.disabled = true;
      chip.dataset.disabled = "true";
    }
    const body = el("span", "gi-chip__body");
    if (kind === "model") {
      const visual = option.visual || "model";
      chip.dataset.visual = visual;
      const copy = el("span", "gi-model-choice__copy");
      const head = el("span", "gi-model-choice__head");
      head.append(el("span", "gi-model-choice__provider", option.provider || "Модель"));
      if (option.recommended) {
        head.append(el("span", "gi-chip__badge", "ИИ-центр рекомендует"));
      }
      copy.append(head, el("span", "gi-chip__title", option.title));
      const facts = el("span", "gi-model-choice__facts");
      [
        ["Цена", option.price || option.note],
        ["Длина", option.duration],
        ["Условия", option.condition],
      ].forEach(([label, value]) => {
        if (!value) return;
        const fact = el("span", "gi-model-choice__fact");
        fact.append(
          el("span", "gi-model-choice__fact-label", label),
          el("span", "gi-model-choice__fact-value", value),
        );
        facts.append(fact);
      });
      body.append(
        modelVisualNode(visual),
        copy,
        facts,
      );
      chip.append(
        input,
        body,
        el(
          "span",
          "gi-model-choice__selector",
          input.checked ? "Выбрано" : "Выбрать модель",
        ),
      );
    } else {
      if (option.recommended) body.append(el("span", "gi-chip__badge", "Советуем"));
      body.append(el("span", "gi-chip__title", option.title));
      if (option.note) body.append(el("span", "gi-chip__note", option.note));
      chip.append(input, body);
    }
    return chip;
  }));
}

function cascadeStep(kind, ordinal, title, name, extraRowClass = "") {
  const block = el("div", "gi-choice-block gi-cascade__step");
  block.dataset.generationIntakeChoiceBlock = kind;
  const head = el("h5", "gi-card__subtitle");
  head.append(
    el("span", "gi-cascade__ordinal", ordinal),
    el("span", "", title),
  );
  const row = chipRow(name, kind);
  if (extraRowClass) row.classList.add(extraRowClass);
  block.append(head, row);
  return block;
}

// Карточка каскада. Имя нейтральное: её рисует не только «Копия».
// Радиокнопки панелей живут в ОДНОЙ форме, поэтому имена у каждой панели
// свои: иначе выбор «Дуэта» снимал бы отметку с модели «Копии» и наоборот —
// браузер держит в одной группе одну отмеченную кнопку.
function engineCascadeCard(route = "copy_video") {
  const section = el("section", "gi-card gi-cascade");
  const nameSuffix = route === "copy_video" ? "" : `__${route}`;
  section.dataset.giStep = "engine";
  section.dataset.generationIntakeEngine = "";
  section.hidden = true;

  const durationStep = cascadeStep(
    "duration",
    "3",
    "Длительность ролика",
    "generation_intake_duration",
    "gi-chips--compact",
  );
  const qualityStep = cascadeStep(
    "quality",
    "2",
    "Сложность",
    "generation_intake_quality",
  );
  const qualityNotice = el("p", "gi-cascade__notice", "");
  qualityNotice.dataset.generationIntakeQualityNotice = "";
  qualityNotice.hidden = true;
  qualityStep.append(qualityNotice);
  const durationNotice = el("p", "gi-cascade__notice", "");
  durationNotice.dataset.generationIntakeDurationNotice = "";
  durationNotice.hidden = true;
  durationStep.append(durationNotice);

  const price = el("p", "gi-card__hint gi-cascade__price", "");
  price.dataset.generationIntakePriceLine = "";
  const routeNote = el("p", "gi-card__hint", "");
  routeNote.dataset.generationIntakeRouteNote = "";

  // Простой режим (решение владельца 28.08): вместо витрины моделей — ползунок
  // «Быстрее ↔ Качественнее». Он ничего не решает сам: двигая его, человек
  // кликает те же радио-чипы модели, так что советчик, цена и резерв денег
  // работают как раньше. Точный список моделей остаётся под спойлером.
  const slider = el("div", "gi-engine-slider");
  slider.dataset.generationIntakeEngineSlider = "";
  slider.hidden = true;
  const scale = el("div", "gi-engine-slider__scale");
  scale.append(
    el("span", "", "Быстрее и дешевле"),
    el("span", "", "Качественнее и дороже"),
  );
  const engineRange = document.createElement("input");
  engineRange.type = "range";
  engineRange.min = "0";
  engineRange.step = "1";
  engineRange.dataset.generationIntakeEngineRange = "";
  engineRange.setAttribute("aria-label", "Баланс скорости и качества генерации");
  const engineCaption = el("p", "gi-engine-slider__caption", "");
  engineCaption.dataset.generationIntakeEngineSliderCaption = "";
  const engineAdvice = el("p", "muted tiny", "");
  engineAdvice.dataset.generationIntakeEngineSliderAdvice = "";
  engineAdvice.hidden = true;
  engineRange.addEventListener("input", () => {
    const ids = String(engineRange.dataset.engineIds || "").split("|").filter(Boolean);
    const targetId = ids[Number(engineRange.value)] || "";
    if (!targetId) return;
    const radio = qa(
      'input[type="radio"]',
      q('[data-generation-intake-choice="model"]', section) || section,
    ).find((input) => input.value === targetId && !input.disabled);
    if (radio && !radio.checked) radio.click();
  });
  slider.append(scale, engineRange, engineCaption, engineAdvice);

  const modelStep = cascadeStep("model", "1", "Модель", "generation_intake_generator");
  const manual = document.createElement("details");
  manual.className = "gi-engine-manual";
  manual.dataset.generationIntakeChoiceBlock = "manual";
  const manualSummary = document.createElement("summary");
  manualSummary.textContent = "Выбрать модель вручную — весь список с ценами";
  manual.append(manualSummary, modelStep);

  // Второй ползунок — длительность: те же секунды-чипы, только компактнее.
  const durationSlider = el("div", "gi-engine-slider gi-engine-slider--duration");
  durationSlider.dataset.generationIntakeDurationSlider = "";
  durationSlider.hidden = true;
  const durationRange = document.createElement("input");
  durationRange.type = "range";
  durationRange.step = "1";
  durationRange.dataset.generationIntakeDurationRange = "";
  durationRange.setAttribute("aria-label", "Длительность ролика в секундах");
  const durationCaption = el("p", "gi-engine-slider__caption", "");
  durationCaption.dataset.generationIntakeDurationSliderCaption = "";
  durationRange.addEventListener("input", () => {
    const radio = qa(
      'input[type="radio"]',
      q('[data-generation-intake-choice="duration"]', section) || section,
    ).find((input) => input.value === String(durationRange.value) && !input.disabled);
    if (radio && !radio.checked) {
      radio.click();
      return;
    }
    // Чипы секунд могли перестроиться под другой движок в момент движения —
    // клик по несуществующему radio молча терялся, и выбранная длительность
    // «слетала» обратно к авто-подстановке (боевой скрин 29.08: 15 → 8).
    // Пишем значение напрямую в поле мастера: каскад его уважает.
    if (!radio) {
      const host = section.closest("form");
      const seconds = Number(durationRange.value);
      if (host && Number.isFinite(seconds)) {
        applyCopyDuration(host, seconds);
      }
    }
  });
  durationSlider.append(durationRange, durationCaption);
  durationStep.insertBefore(durationSlider, durationStep.children[1] || null);

  section.append(
    el("h4", "gi-card__title", "Чем генерируем, как сложно и как долго"),
    slider,
    manual,
    qualityStep,
    durationStep,
    price,
    routeNote,
  );
  if (nameSuffix) {
    qa("[data-choice-name]", section).forEach((row) => {
      row.dataset.choiceName = `${row.dataset.choiceName}${nameSuffix}`;
    });
  }
  return section;
}

// Оригинал по ссылке (intake v2, контур №1): человек кидает YouTube-ссылку
// прямо в форме «Копии». Ссылка регистрируется в едином реестре источников
// проекта, а выбранный ниже MP4 получает несмываемый след происхождения в
// метаданных (creator_stamp_media_origin_url) — паспорт покажет «оригинал»
// у исходника. Файл система не скачивает (ТЗ 3.3): его прикладывает человек
// и галкой подтверждает, что это тот же ролик.
const copyOriginState = {
  canonical: "",
  videoId: "",
  sourceId: "",
  confirmed: false,
};

function normalizeCopyOriginUrl(raw) {
  const text = String(raw || "").trim();
  if (!text) return { error: "Вставьте ссылку на оригинал." };
  let url;
  try {
    url = new URL(text);
  } catch {
    return { error: "Это не похоже на ссылку." };
  }
  if (url.protocol !== "https:") return { error: "Нужна https-ссылка." };
  const host = url.hostname.toLowerCase()
    .replace(/^www\./u, "")
    .replace(/^m\./u, "");
  let videoId = "";
  if (host === "youtu.be") {
    videoId = url.pathname.slice(1).split("/")[0] || "";
  } else if (host === "youtube.com" || host === "youtube-nocookie.com") {
    if (url.pathname === "/watch") videoId = url.searchParams.get("v") || "";
    else if (
      url.pathname.startsWith("/shorts/")
      || url.pathname.startsWith("/embed/")
      || url.pathname.startsWith("/live/")
    ) videoId = url.pathname.split("/")[2] || "";
  } else {
    return { error: "Пока поддерживается только YouTube." };
  }
  videoId = String(videoId).trim();
  if (!/^[A-Za-z0-9_-]{11}$/u.test(videoId)) {
    return { error: "В ссылке не нашёлся код ролика YouTube (11 символов)." };
  }
  return { videoId, canonical: `https://youtube.com/watch?v=${videoId}` };
}

function copyOriginLinkBlock() {
  const details = document.createElement("details");
  details.className = "gi-origin-link";
  details.dataset.generationIntakeCopyOrigin = "";
  const summary = document.createElement("summary");
  summary.textContent = "Оригинал по ссылке (необязательно)";
  const hint = el(
    "p",
    "muted tiny",
    "Если исходник взят из публичного ролика — вставьте ссылку: она зарегистрируется источником проекта, а файл получит след происхождения. Сам файл система не скачивает — его прикладываете вы.",
  );
  const row = el("div", "gi-origin-link__row");
  const input = document.createElement("input");
  input.type = "url";
  input.placeholder = "https://youtu.be/…";
  input.dataset.generationIntakeCopyOriginUrl = "";
  const bindButton = el("button", "btn btn-small", "Привязать ссылку");
  bindButton.type = "button";
  bindButton.dataset.action = "generation-intake-copy-origin";
  row.append(input, bindButton);
  const confirmLabel = el("label", "gi-origin-link__confirm");
  const confirmBox = document.createElement("input");
  confirmBox.type = "checkbox";
  confirmBox.dataset.generationIntakeCopyOriginConfirm = "";
  confirmLabel.append(
    confirmBox,
    el(
      "span",
      "tiny",
      " Подтверждаю: файл, который я прикладываю, — этот же ролик, и права на переработку есть.",
    ),
  );
  const status = el("p", "muted tiny", "");
  status.dataset.generationIntakeCopyOriginStatus = "";
  details.append(summary, hint, row, confirmLabel, status);
  return details;
}

async function bindCopyOriginLink(form) {
  const shell = form?.closest?.("body") || document;
  const input = q("[data-generation-intake-copy-origin-url]", shell);
  const confirm = q("[data-generation-intake-copy-origin-confirm]", shell);
  const status = q("[data-generation-intake-copy-origin-status]", shell);
  if (!(input instanceof HTMLInputElement)) return;
  const normalized = normalizeCopyOriginUrl(input.value);
  if (normalized.error) {
    if (status) setNodeText(status, normalized.error);
    return;
  }
  if (!(confirm instanceof HTMLInputElement) || !confirm.checked) {
    if (status) {
      setNodeText(
        status,
        "Поставьте галку подтверждения: без неё след происхождения не ставится.",
      );
    }
    return;
  }
  if (status) setNodeText(status, `Регистрируем ${normalized.canonical}…`);
  try {
    const api = await apiRuntime();
    let sourceId = "";
    try {
      const registered = await api.call(
        "contentengine_register_exact_youtube_source",
        {
          organization_id: String(api.organizationId || ""),
          project_id: projectId(),
          canonical_url: normalized.canonical,
          video_id: normalized.videoId,
          idempotency_key:
            `copy-origin-${projectId()}-${normalized.videoId}`.slice(0, 180),
        },
      );
      sourceId = String(
        registered?.source?.id || registered?.data?.source?.id || "",
      );
    } catch {
      // Источник уже зарегистрирован ранее — след ссылкой всё равно ставим.
    }
    copyOriginState.canonical = normalized.canonical;
    copyOriginState.videoId = normalized.videoId;
    copyOriginState.sourceId = sourceId;
    copyOriginState.confirmed = true;
    if (status) {
      setNodeText(
        status,
        `Ссылка привязана: ${normalized.canonical}. Файл, который вы выберете, получит этот след происхождения при загрузке.`,
      );
    }
  } catch {
    if (status) {
      setNodeText(status, "Не получилось зарегистрировать ссылку. Попробуйте ещё раз.");
    }
  }
}

// Штамп происхождения на исходнике «Копии». Ошибка штампа не валит запуск:
// след — ценность, но не условие генерации.
async function stampCopyOriginOnMedia(api, mediaId) {
  if (!copyOriginState.confirmed || !copyOriginState.canonical) return;
  try {
    await api.call("creator_stamp_media_origin_url", {
      organization_id: String(api.organizationId || ""),
      project_id: projectId(),
      media_id: mediaId,
      canonical_url: copyOriginState.canonical,
      video_id: copyOriginState.videoId,
      ...(copyOriginState.sourceId
        ? { source_id: copyOriginState.sourceId }
        : {}),
    });
  } catch {
    const status = q("[data-generation-intake-copy-origin-status]");
    if (status) {
      setNodeText(
        status,
        "След происхождения не записался (файл уже мог быть привязан к другой ссылке). Запуску это не мешает.",
      );
    }
  }
}

// Гипотеза запуска (контур №3): оператор выбирает утверждённую гипотезу, и
// момент bind вписывает её точную версию в манифест происхождения — паспорт
// заполняет «Зачем создан», а гипотеза копит «Запуски». Выбор необязателен.
// Кэш по проекту; DOM обновляется только по отпечатку (панели под
// MutationObserver — безусловные записи замкнули бы цикл).
const hypothesisPickerState = {
  projectId: "",
  status: "idle",
  items: [],
  selectedId: "",
  assignedId: "",
  autoAppliedFor: "",
};

function hypothesisPickerCard(route) {
  const card = el("section", "gi-card");
  card.dataset.generationIntakeHypothesisCard = route;
  card.hidden = true;
  const title = el("h4", "gi-card__title", "Гипотеза запуска");
  const hint = el(
    "p",
    "muted tiny",
    "Необязательно. Выбранная гипотеза впишется в манифест этого запуска: паспорт ролика покажет «Зачем создан», а гипотеза соберёт свои запуски и метрики.",
  );
  const select = document.createElement("select");
  select.dataset.generationIntakeHypothesis = route;
  const status = el("p", "muted tiny", "");
  status.dataset.generationIntakeHypothesisStatus = route;
  // Формулировка выбранной гипотезы — прямо в форме: исполнитель должен
  // понимать «если — то — потому что», а не просто видеть код (27.08).
  const statement = el("p", "muted tiny gi-hypothesis-statement", "");
  statement.dataset.generationIntakeHypothesisStatement = route;
  statement.hidden = true;
  const open = document.createElement("a");
  open.dataset.generationIntakeHypothesisLink = route;
  open.className = "tiny";
  open.textContent = "Открыть гипотезу — источники, варианты и обсуждение";
  open.hidden = true;
  select.addEventListener("change", () => {
    void commitHypothesisSelection(select, status);
  });
  card.append(title, hint, select, status, statement, open);
  return card;
}

async function commitHypothesisSelection(select, status) {
  const hypothesisId = String(select.value || "");
  const chosen = hypothesisPickerState.items.find(
    (item) => item.id === hypothesisId,
  );
  setNodeText(status, "Сохраняем выбор…");
  try {
    const api = await apiRuntime();
    await api.call("creator_select_content_hypothesis", {
      organization_id: String(api.organizationId || ""),
      project_id: projectId(),
      ...(hypothesisId ? { hypothesis_id: hypothesisId } : {}),
    });
    hypothesisPickerState.selectedId = hypothesisId;
    setNodeText(
      status,
      chosen
        ? `Следующий запуск привяжется к ${chosen.code} (утверждённая версия v${chosen.approvedVersion}).`
        : "Запуск пойдёт без гипотезы.",
    );
    const card = select.closest("[data-generation-intake-hypothesis-card]");
    const statement = card
      ? q("[data-generation-intake-hypothesis-statement]", card)
      : null;
    if (statement instanceof HTMLElement) {
      statement.hidden = !chosen || !chosen.statement;
      if (chosen && chosen.statement) {
        setNodeText(statement, `Проверяем: ${chosen.statement}`);
      }
    }
    const open = card
      ? q("[data-generation-intake-hypothesis-link]", card)
      : null;
    if (open instanceof HTMLAnchorElement) {
      open.hidden = !chosen;
      if (chosen) {
        open.href = `#/workspace/hypotheses?project_id=${encodeURIComponent(projectId())}&hypothesis=${encodeURIComponent(chosen.id)}`;
      }
    }
  } catch {
    setNodeText(status, "Выбор не сохранился. Попробуйте ещё раз.");
  }
}

async function ensureHypothesisPicker(form, state) {
  const currentProjectId = projectId();
  if (!currentProjectId) return;
  if (
    hypothesisPickerState.projectId !== currentProjectId
    && hypothesisPickerState.status !== "loading"
  ) {
    hypothesisPickerState.projectId = currentProjectId;
    hypothesisPickerState.status = "loading";
    try {
      const api = await apiRuntime();
      const data = await api.call("creator_content_hypotheses", {
        organization_id: String(api.organizationId || ""),
        project_id: currentProjectId,
      });
      const rows = Array.isArray(data?.hypotheses) ? data.hypotheses : [];
      hypothesisPickerState.items = rows
        .filter((row) => row?.approved && row.approved.id)
        .map((row) => ({
          id: String(row.id),
          code: String(row.code || ""),
          title: String(row.title || ""),
          approvedVersion: Number(row.approved.version || 0),
          statement: String(row.approved.statement || ""),
        }));
      hypothesisPickerState.selectedId = String(
        data?.operator_selection?.hypothesis_id || "",
      );
      hypothesisPickerState.assignedId = String(
        data?.assigned?.hypothesis_id || "",
      );
      hypothesisPickerState.status = "ready";
      // Закреплённая за оператором гипотеза подставляется сама — один раз на
      // проект и только когда у него нет собственного выбора. Явный выбор
      // человека (включая «Без гипотезы» после этого) не перекрывается.
      if (
        !hypothesisPickerState.selectedId
        && hypothesisPickerState.assignedId
        && hypothesisPickerState.autoAppliedFor !== currentProjectId
        && hypothesisPickerState.items.some(
          (item) => item.id === hypothesisPickerState.assignedId,
        )
      ) {
        hypothesisPickerState.autoAppliedFor = currentProjectId;
        try {
          const autoApi = await apiRuntime();
          await autoApi.call("creator_select_content_hypothesis", {
            organization_id: String(autoApi.organizationId || ""),
            project_id: currentProjectId,
            hypothesis_id: hypothesisPickerState.assignedId,
          });
          hypothesisPickerState.selectedId = hypothesisPickerState.assignedId;
        } catch {
          // Автоподстановка — удобство, не обязанность: молча остаёмся без
          // выбора, человек выберет руками.
        }
      }
    } catch {
      hypothesisPickerState.status = "error";
    }
  }
  renderHypothesisPickers(state);
}

function renderHypothesisPickers(state) {
  const shell = state?.shell;
  if (!shell) return;
  const fingerprint = JSON.stringify([
    hypothesisPickerState.items.map((item) => item.id),
    hypothesisPickerState.selectedId,
    hypothesisPickerState.status,
  ]);
  qa("[data-generation-intake-hypothesis-card]", shell).forEach((card) => {
    const select = q("select[data-generation-intake-hypothesis]", card);
    if (!(select instanceof HTMLSelectElement)) return;
    // Карточка видима и без утверждённых гипотез: пункт должен находиться,
    // а пустота — объяснять себя (фидбек владельца 27.08: «не видела этого
    // пункта»). Прячемся только до первого ответа сервера.
    const settled = hypothesisPickerState.status === "ready"
      || hypothesisPickerState.status === "error";
    const empty = !hypothesisPickerState.items.length;
    if (card.hidden !== !settled) card.hidden = !settled;
    if (!settled) return;
    if (card.dataset.hypothesisFingerprint === fingerprint) return;
    card.dataset.hypothesisFingerprint = fingerprint;
    const status = q(
      "[data-generation-intake-hypothesis-status]",
      card,
    );
    const statement = q(
      "[data-generation-intake-hypothesis-statement]",
      card,
    );
    const open = q("[data-generation-intake-hypothesis-link]", card);
    if (select.hidden !== empty) select.hidden = empty;
    if (empty) {
      if (status) {
        setNodeText(
          status,
          hypothesisPickerState.status === "error"
            ? "Список гипотез не загрузился — запуск пойдёт без гипотезы. Обновите страницу, чтобы попробовать ещё раз."
            : "Утверждённых гипотез в проекте пока нет — запуск пойдёт без гипотезы. Их создают и утверждают в папке «Гипотезы» (∴ в Dock).",
        );
      }
      if (statement instanceof HTMLElement) statement.hidden = true;
      if (open instanceof HTMLElement) open.hidden = true;
      return;
    }
    select.replaceChildren(
      new Option("Без гипотезы", ""),
      ...hypothesisPickerState.items.map((item) =>
        new Option(`${item.code} · ${item.title} (v${item.approvedVersion})`, item.id)
      ),
    );
    select.value = hypothesisPickerState.selectedId;
    const chosen = hypothesisPickerState.items.find(
      (item) => item.id === hypothesisPickerState.selectedId,
    );
    if (status) {
      setNodeText(
        status,
        chosen
          ? `Следующий запуск привяжется к ${chosen.code} (утверждённая версия v${chosen.approvedVersion})${
            chosen.id === hypothesisPickerState.assignedId
              ? " — назначена вам"
              : ""
          }.`
          : "Запуск пойдёт без гипотезы.",
      );
    }
    if (statement instanceof HTMLElement) {
      statement.hidden = !chosen || !chosen.statement;
      if (chosen && chosen.statement) {
        setNodeText(statement, `Проверяем: ${chosen.statement}`);
      }
    }
    if (open instanceof HTMLAnchorElement) {
      open.hidden = !chosen;
      if (chosen) {
        open.href = `#/workspace/hypotheses?project_id=${encodeURIComponent(projectId())}&hypothesis=${encodeURIComponent(chosen.id)}`;
      }
    }
  });
}

function copyChecklistRow(key, label) {
  const row = el("li", "gi-check");
  row.dataset.generationIntakeCheck = key;
  row.append(
    el("span", "gi-check__label", label),
    el("span", "gi-check__value", "—"),
    el("span", "gi-check__dot"),
  );
  return row;
}

function copyRail(actions, status) {
  const rail = el("aside", "gi-rail");

  const previewCard = el("section", "gi-rail__card");
  const preview = el("div", "gi-preview");
  preview.dataset.generationIntakePreview = "";
  preview.append(el("p", "gi-preview__empty", "Ролик появится здесь после выбора файла"));
  previewCard.append(el("h4", "gi-rail__title", "Предпросмотр"), preview);

  const frameCard = el("section", "gi-rail__card");
  frameCard.dataset.generationIntakeKeyframeCard = "";
  frameCard.hidden = true;
  const frame = el("div", "gi-keyframe");
  frame.dataset.generationIntakeKeyframe = "";
  frameCard.append(el("h4", "gi-rail__title", "Ключевой кадр"), frame);

  const checkCard = el("section", "gi-rail__card");
  const list = el("ul", "gi-checklist");
  list.append(
    copyChecklistRow("source", "Исходник"),
    copyChecklistRow("product", "Товар"),
    copyChecklistRow("brief", "Сценарий копирования"),
  );
  checkCard.append(list);

  rail.append(previewCard, frameCard, checkCard, status, actions);
  return rail;
}

function copyPanel() {
  const panel = el("section", "generation-intake-v4__panel gi-copy");
  panel.dataset.generationIntakePanel = "copy_video";
  panel.hidden = true;
  const actions = el("div", "gi-rail__actions");
  const prepare = el("button", "btn btn-primary gi-rail__primary", "Подготовить ролик");
  prepare.type = "button";
  prepare.dataset.action = "generation-intake-prepare-copy";
  prepare.dataset.expressPhase = "idle";
  prepare.disabled = true;
  const analyze = el("button", "btn btn-secondary gi-rail__secondary", "Проверить ролик бесплатно");
  analyze.type = "button";
  analyze.dataset.action = "generation-intake-analyze-copy";
  actions.append(prepare, analyze);
  // Идентичность товара спрашивается только когда её нельзя определить по
  // выбранным фото; иначе блок остаётся скрытым (см. refreshIdentityVisibility).
  const identity = productIdentityFields();
  identity.hidden = true;
  // Кампания, звук, формат и модель выбираются автоматически «под капотом».
  // Контролы остаются в DOM, чтобы все существующие предохранители работали.
  const autoDefaults = el("div", "generation-intake-v4__auto-defaults");
  autoDefaults.dataset.generationIntakeAutoDefaults = "";
  autoDefaults.hidden = true;
  autoDefaults.append(executionControls());
  const campaignNote = campaignNoteBlock();
  const screenLinks = el("p", "generation-intake-v4__screen-links");
  const screenLink = el("a", "generation-intake-v4__screen-link", "Открыть «Копию» отдельным экраном");
  screenLink.dataset.generationIntakeCopyScreenLink = "";
  const backLink = el("a", "generation-intake-v4__screen-link", "← Все способы создания");
  backLink.dataset.generationIntakeCopyBackLink = "";
  backLink.hidden = true;
  screenLinks.append(screenLink, backLink);
  const head = el("header", "gi-copy__head");
  head.append(
    el("h3", "gi-copy__title", "Стратегия: Копирование ролика"),
    el(
      "p",
      "gi-copy__lede",
      "Загрузите исходный ролик, добавьте фото товара и кратко опишите, что важно сохранить.",
    ),
    screenLinks,
  );

  const sourceCard = el("section", "gi-card");
  sourceCard.dataset.giStep = "1";
  sourceCard.append(
    el("h4", "gi-card__title", "1. Исходный ролик"),
    sourceChooser("copy_video", null),
    copyOriginLinkBlock(),
    storyboardNode(),
    originalFrameSlot(),
  );

  const productCard = el("section", "gi-card");
  productCard.dataset.giStep = "2";
  productCard.append(
    el("h4", "gi-card__title", "2. Ваш товар"),
    (() => {
      const home = el("div", "");
      home.dataset.generationIntakeProductSlotHome = "";
      return home;
    })(),
    productSlot(),
    identity,
  );

  const briefCard = el("section", "gi-card");
  briefCard.dataset.giStep = "4";
  briefCard.append(
    el("h4", "gi-card__title", "4. Комментарий"),
    recommendationSlot("copy_video"),
  );

  const main = el("div", "gi-copy__main");
  main.append(
    sourceCard,
    productCard,
    copyPreserveChips(),
    compactCampaignChoice(),
    engineCascadeCard(),
    briefCard,
    hypothesisPickerCard("copy_video"),
    rightsConfirmation("copy_video"),
    campaignNote,
    autoDefaults,
  );

  const grid = el("div", "gi-copy__grid");
  grid.append(main, copyRail(actions, statusNode()));
  panel.append(head, grid);
  return panel;
}

// Панель «Дуэта» длинная (механика — семь полей), а строка состояния и кнопки
// стояли в самом её конце: выбрав файл вверху, человек не видел ни «MP4
// выбран», ни «Разобрать MP4». Подвал липнет к нижнему краю окна.
function duetFooter(status, actions) {
  const footer = el("div", "generation-intake-v4__footer");
  footer.dataset.generationIntakeFooter = "avatar_video";
  footer.append(status, actions);
  return footer;
}

function avatarPanel() {
  const panel = el("section", "generation-intake-v4__panel");
  panel.dataset.generationIntakePanel = "avatar_video";
  panel.hidden = true;
  const actions = el("div", "generation-intake-v4__actions");
  const analyze = el("button", "btn", "Разобрать MP4");
  analyze.type = "button";
  analyze.dataset.action = "generation-intake-analyze-avatar";
  // Та же двухфазная кнопка, что у «Копии»: idle → бесплатная подготовка и
  // серверная цена, priced → «Запустить за $X» явным человеческим кликом.
  const prepare = el("button", "btn btn-primary", "Подготовить дуэт");
  prepare.type = "button";
  prepare.dataset.action = "generation-intake-prepare-avatar";
  prepare.dataset.expressPhase = "idle";
  prepare.disabled = true;
  actions.append(analyze, prepare);
  panel.append(
    routeHeader(
      "ОТДЕЛЬНАЯ ФОРМА",
      "Дуэт с ведущим",
      "Исходный ролик остаётся нетронутым; ведущий проекта комментирует его из угла кадра.",
      "Дуэт",
    ),
    sourceChooser("avatar_video"),
    duetProductChooser(),
    duetPresenterChooser(),
    duetMechanicsCard(),
    // Тот же каскад «модель → сложность → длительность», что и у «Копии»: с
    // 21.08.2026 «Аватар» — такая же правка готового ролика и ездит теми же
    // движками. Карточка скрыта, пока реестр не отдаст маршруты этой стратегии,
    // поэтому появление формы ничего не обещает раньше времени.
    engineCascadeCard("avatar_video"),
    compactCampaignChoice(),
    recommendationSlot("avatar_video"),
    hypothesisPickerCard("avatar_video"),
    rightsConfirmation("avatar_video"),
    el(
      "p",
      "generation-intake-v4__gate-note",
      "Текст ниже — речь ведущего: он произнесёт её вслух. Длина дуэта равна длине речи; если речь короче ролика, ролик обрежется на её конце.",
    ),
    campaignNoteBlock(),
    duetFooter(statusNode(), actions),
  );
  return panel;
}

function strategyPanel() {
  const panel = el("section", "generation-intake-v4__panel gi-copy generation-intake-v4__panel--strategy");
  panel.dataset.generationIntakePanel = "strategy_video";
  panel.hidden = true;

  const actions = el("div", "gi-rail__actions");
  const proceed = el("button", "btn btn-primary gi-rail__primary", "Подготовить ролик");
  proceed.type = "button";
  proceed.dataset.action = "generation-intake-continue-strategy";
  proceed.dataset.expressPhase = "idle";
  actions.append(proceed);

  const head = el("header", "gi-copy__head");
  head.append(
    el("h3", "gi-copy__title", "Стратегия: Создание с нуля"),
    el("p", "gi-copy__lede", "Ролик собирается по фото товара и вашему замыслу — исходное видео не нужно. Та же форма, что у «Копии», только без загрузки MP4."),
  );

  // «1. Ваш товар» — сюда переезжает ЕДИНСТВЕННЫЙ product-слот «Копии» вместе
  // с блоком идентичности (см. relocateProductSlot): вторые экземпляры дали бы
  // дубль id поля загрузки и слепые data-селекторы идентичности.
  const productCard = el("section", "gi-card");
  productCard.dataset.giStep = "1";
  const productHost = el("div", "");
  productHost.dataset.generationIntakeStrategyProductHost = "";
  productCard.append(el("h4", "gi-card__title", "1. Ваш товар"), productHost);

  const briefCard = el("section", "gi-card");
  briefCard.dataset.giStep = "3";
  briefCard.append(
    el("h4", "gi-card__title", "3. Комментарий"),
    recommendationSlot("strategy_video"),
  );

  const rights = rightsConfirmation("strategy_video");
  const rightsNote = el(
    "p",
    "muted tiny",
    "Галка разом проставляет четыре юридических подтверждения мастера — их видно в технических деталях и можно снять по отдельности.",
  );

  // Выбор ИИ — шаг «2», сразу под фото товара: в боевой раскладке карточка
  // стояла после «Комментария» и кампании, ниже первого экрана, и владелица её
  // не находила («нету выбора ИИ», скрины 25–26.08). Карточка видима с первой
  // отрисовки: до ответа реестра она держит собственную строку загрузки, а не
  // hidden-заглушку — исчезнуть молча ей больше не из чего.
  const engines = engineCascadeCard("strategy_video");
  engines.hidden = false;
  engines.dataset.giStep = "2";
  const enginesTitle = q(".gi-card__title", engines);
  if (enginesTitle) enginesTitle.textContent = "2. Выбор ИИ";
  const enginesLoading = el("div", "muted tiny", "Каталог движков загружается…");
  enginesLoading.dataset.generationIntakeEngineEmpty = "";
  if (enginesTitle) enginesTitle.after(enginesLoading);
  qa("[data-generation-intake-choice-block]", engines).forEach((block) => {
    block.hidden = true;
  });
  const engineHint = el(
    "p",
    "muted tiny",
    "Здесь движки «фото → видео» — все, которые умеют собрать ролик из фотографий. Kling-редакторы и Pika правят готовое видео, поэтому живут в «Копии».",
  );

  const tech = document.createElement("details");
  tech.className = "gi-card generation-intake-v4__strategy-tech";
  tech.dataset.generationIntakeStrategyTech = "";
  const techSummary = document.createElement("summary");
  techSummary.textContent = "Технические детали: референс механики, точное ТЗ и запуск";
  const host = el("div", "generation-intake-v4__strategy-host");
  host.dataset.generationIntakeStrategyHost = "";
  tech.append(techSummary, host);

  const main = el("div", "gi-copy__main");
  main.append(
    productCard,
    engines,
    engineHint,
    briefCard,
    hypothesisPickerCard("strategy_video"),
    compactCampaignChoice(),
    rights,
    rightsNote,
    el(
      "p",
      "muted tiny",
      "Механика ролика заполнена стандартной заготовкой; референс выбирается автоматически. Точное ТЗ вы прочитаете и одобрите перед оплатой.",
    ),
    tech,
  );

  const rail = el("aside", "gi-rail");
  const checkCard = el("section", "gi-rail__card");
  const list = el("ul", "gi-checklist");
  list.append(
    copyChecklistRow("product", "Товар"),
    copyChecklistRow("brief", "Сценарий"),
    copyChecklistRow("rights", "Права"),
  );
  checkCard.append(list);
  rail.append(checkCard, statusNode(), actions);

  const grid = el("div", "gi-copy__grid");
  grid.append(main, rail);
  panel.append(head, grid);
  return panel;
}

// Чеклист «Создания»: те же строки-состояния, что у «Копии», но по своей
// тройке (товар/сценарий/права). Записи только при изменении — панель
// наблюдается MutationObserver'ом, безусловная запись замкнула бы цикл.
function renderStrategyChecklist(form, state) {
  const panel = panelFor(state, "strategy_video");
  if (!panel) return;
  const setRow = (key, ready, text) => {
    const row = q(`[data-generation-intake-check="${key}"]`, panel);
    if (!row) return;
    const value = q(".gi-check__value", row);
    const nextState = ready ? "ready" : "empty";
    if (row.dataset.state !== nextState) row.dataset.state = nextState;
    if (value && value.textContent !== text) value.textContent = text;
  };
  const photos = productSelectionCount(form, panel);
  setRow(
    "product",
    photos >= MIN_PRODUCT_IMAGES && photos <= MAX_PRODUCT_IMAGES,
    photos ? `${photos} фото` : "—",
  );
  const brief = String(form?.elements?.brief?.value || "").trim();
  setRow("brief", Boolean(brief), brief ? "Заполнен" : "—");
  const rightsBox = q('[data-generation-intake-rights="strategy_video"]', panel);
  const rightsReady = rightsBox instanceof HTMLInputElement && rightsBox.checked;
  setRow("rights", rightsReady, rightsReady ? "Подтверждены" : "—");
}

// Кнопка «Создания» зеркалит живой #generation-submit мастера: когда тот
// дозрел до «Запустить … · $X», метка и фаза переезжают на кнопку панели.
// Ссылки на мастера не удерживаются (форма перерисовывается целиком), записи
// только при изменении — иначе MutationObserver замкнёт микрозадачный цикл.
function syncStrategyLaunchButton(form, state) {
  const panel = panelFor(state, "strategy_video");
  const button = panel
    ? q('[data-action="generation-intake-continue-strategy"]', panel)
    : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const submit = q("#generation-submit", form);
  const label = String(submit?.textContent || "").trim();
  const priced = Boolean(submit)
    && !submit.disabled
    && /^Запустить/u.test(label);
  const nextLabel = priced ? label : "Подготовить ролик";
  const nextPhase = priced ? "priced" : "idle";
  if (button.dataset.expressPhase !== nextPhase) {
    button.dataset.expressPhase = nextPhase;
  }
  if (button.textContent !== nextLabel) button.textContent = nextLabel;
}

// Product-слот «Копии» — один на форму: при входе на «Создание» он переезжает
// в карточку «1. Ваш товар» стратегии, при возврате — назад в «Копию».
function relocateProductSlot(state, route) {
  const slot = q("[data-generation-intake-product-slot]", state?.shell);
  if (!(slot instanceof HTMLElement)) return;
  // Блок идентичности товара (SKU/название/категория) — сосед слота и тоже
  // один на форму: едет вместе с ним. На «Создании» он всегда видим: новые
  // фото требуют артикул, а логика видимости «Копии» сюда не дотягивается.
  const identity = q("[data-generation-intake-identity]", state?.shell);
  if (route === "strategy_video") {
    const host = q("[data-generation-intake-strategy-product-host]", state.shell);
    if (host instanceof HTMLElement) {
      if (slot.parentElement !== host) host.append(slot);
      if (identity instanceof HTMLElement) {
        if (identity.parentElement !== host) host.append(identity);
        identity.hidden = false;
      }
    }
    return;
  }
  const copyPanelNode = q('[data-generation-intake-panel="copy_video"]', state?.shell);
  const marker = q("[data-generation-intake-product-slot-home]", copyPanelNode || state?.shell);
  if (marker instanceof HTMLElement && slot.previousElementSibling !== marker) {
    marker.after(slot);
  }
  if (identity instanceof HTMLElement && slot.nextElementSibling !== identity) {
    slot.after(identity);
  }
}

function placeGuidedShell(form, state, route = state?.route) {
  const host = q("[data-generation-intake-strategy-host]", state?.shell);
  const guidedShell = q("[data-ce-v4-generation-guided-shell]", form);
  if (!(host instanceof HTMLElement) || !(guidedShell instanceof HTMLElement)) return;
  if (route === "strategy_video") {
    if (guidedShell.parentElement !== host) host.append(guidedShell);
    guidedShell.dataset.ceV4GenerationPurpose = "from-zero";
    return;
  }
  // Compact modules still use the same native hidden fields as their paid
  // authority. Move the constructor out before the inactive strategy panel is
  // disabled, otherwise those canonical fields would be disabled with it.
  if (guidedShell.parentElement !== form) state.shell.after(guidedShell);
  delete guidedShell.dataset.ceV4GenerationPurpose;
}

function ensureStrategyAuthority(form, state) {
  if (state?.route !== "strategy_video" || state.strategyAuthorityRequested !== true) return;
  const current = String(form.elements?.generation_strategy_id?.value || "").trim();
  if (current === STRATEGY_AUTHORITY_STRATEGY) return;
  if (!selectStrategy(form, STRATEGY_AUTHORITY_STRATEGY)) return;
  void window.ContentEngineGenerationGuidedV4?.refreshStrategyAssets?.(form);
}

function shellNode() {
  const shell = el("section", "generation-intake-v4");
  shell.dataset.generationIntakeV4 = "";
  const header = el("header", "generation-intake-v4__head");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "СОЗДАНИЕ ВИДЕО"),
    el("h2", "", "Что нужно сделать?"),
    el("p", "", "У каждого способа своя форма и свой производственный маршрут."),
  );
  header.append(copy, el("span", "badge", "3 маршрута"));
  const routes = el("div", "generation-intake-v4__routes");
  routes.setAttribute("role", "group");
  routes.setAttribute("aria-label", "Способ создания видео");
  routes.append(
    routeButton("copy_video", "01", "Скопировать ролик", "MP4 + фото вашего товара"),
    routeButton("avatar_video", "02", "Сделать с аватаром", "Пожелания + MP4"),
    routeButton("strategy_video", "03", "Видео по стратегии", "Полный конструктор и до 10 исходников"),
  );
  const panels = el("div", "generation-intake-v4__panels");
  panels.append(copyPanel(), avatarPanel(), strategyPanel());
  shell.append(header, routes, panels);
  return shell;
}

function collectProductNodes(form) {
  const seen = new Set();
  return qa('input[name="media_id"]', form)
    .filter((input) => {
      const container = input.closest("label, article, li, [data-media-card]") || input;
      const mime = String(
        input.dataset.mimeType
        || container.dataset.mimeType
        || container.getAttribute?.("data-mime-type")
        || "",
      ).toLowerCase();
      const text = cleanText(container.textContent, 240);
      return !mime.startsWith("video/") && !/\bmp4\b|исходное видео/iu.test(text);
    })
    // В карточке товара checkbox и radio «Главное фото» — одна неделимая
    // сущность. Перенос одного ближайшего label оставлял radio в старом
    // fieldset: визуально фото было выбрано, но primary_media_id становился
    // недоступен handoff и synthetic-карточку уже нельзя было корректно
    // заменить серверной. Если есть штатная карточка, переносим именно её.
    .map((input) => (
      input.closest(".generation-media-option")
      || input.closest("label, article, li")
      || input.parentElement
    ))
    .filter((node) => {
      if (!node || seen.has(node)) return false;
      seen.add(node);
      return true;
    });
}

function moveProductNodes(form, state, active) {
  const slot = q(".generation-intake-v4__product-items", state.shell);
  if (!slot) return;
  if (active) {
    const tracked = new Set(state.productNodes.map(({ node }) => node));
    collectProductNodes(form).forEach((node) => {
      if (!tracked.has(node)) {
        const marker = document.createComment("generation-intake-v4-product-origin");
        node.before(marker);
        state.productNodes.push({ node, marker });
      }
    });
    state.productNodes.forEach(({ node }) => {
      if (node.parentElement !== slot) slot.append(node);
    });
    if (!state.productNodes.length && !q("[data-generation-intake-empty-product]", slot)) {
      const warning = el("div", "alert alert-warning", "В проекте пока нет доступных фотографий товара.");
      warning.dataset.generationIntakeEmptyProduct = "";
      slot.append(warning);
    }
    return;
  }
  state.productNodes.forEach(({ node, marker }) => {
    if (marker.isConnected && node.previousSibling !== marker) marker.after(node);
  });
}

function mediaIdFromNode(node) {
  const candidates = [
    node?.dataset?.mediaId,
    node?.value,
    node?.getAttribute?.("data-id"),
    q?.call ? null : null,
  ];
  for (const raw of candidates) {
    const value = String(raw || "").trim().toLowerCase();
    if (UUID_PATTERN.test(value)) return value;
  }
  const input = node?.querySelector?.('input[value]');
  const value = String(input?.value || "").trim().toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

function collectProjectVideos(form) {
  const result = new Map();
  const candidates = qa(
    '[data-media-id], input[name="media_id"], [data-generation-media-id]',
    form,
  );
  candidates.forEach((node) => {
    const mediaId = mediaIdFromNode(node);
    if (!mediaId) return;
    const container = node.closest?.("label, article, li, [data-media-card]") || node;
    const text = cleanText(container.textContent, 180);
    const mime = String(
      node.dataset?.mimeType
      || container.dataset?.mimeType
      || container.getAttribute?.("data-mime-type")
      || "",
    ).toLowerCase();
    const videoLike = mime.startsWith("video/") || /\bmp4\b|видео|ролик/iu.test(text);
    if (!videoLike) return;
    result.set(mediaId, text || `Видео ${mediaId.slice(0, 8)}`);
  });
  return [...result.entries()].map(([id, label]) => ({ id, label }));
}

function collectProjectImages(form) {
  const result = new Map();
  qa('input[name="media_id"], [data-media-id]', form).forEach((node) => {
    const mediaId = mediaIdFromNode(node);
    if (!mediaId) return;
    const container = node.closest?.("label, article, li, [data-media-card]") || node;
    const mime = String(
      node.dataset?.mimeType
      || container.dataset?.mimeType
      || container.getAttribute?.("data-mime-type")
      || "",
    ).toLowerCase();
    const text = cleanText(container.textContent, 180);
    if (mime.startsWith("video/") || /\bmp4\b|исходное видео/iu.test(text)) return;
    result.set(mediaId, text || `Фото ${mediaId.slice(0, 8)}`);
  });
  return [...result.entries()].map(([id, label]) => ({ id, label }));
}

// Источник правды о серверных MP4 — пикер guided-мастера: его чекбоксы
// `input[data-generation-strategy-source-toggle]` несут точный media_id, а
// подпись карточки честно сообщает «сервером проверен». Легаси-селект
// generation_strategy_source_video_id мёртв (hidden+disabled, один
// плейсхолдер) и остаётся только запасным вариантом.
function collectPickerVideos(form) {
  const result = [];
  qa("input[data-generation-strategy-source-toggle]", form).forEach((input) => {
    const id = String(
      input.dataset?.generationStrategySourceToggle || input.value || "",
    ).trim().toLowerCase();
    if (!UUID_PATTERN.test(id)) return;
    const card = input.closest("label, article, li, [data-media-card]")
      || input.parentElement;
    const caption = cleanText(card?.textContent, 240);
    const label = cleanText(q("strong", card)?.textContent, 120)
      || cleanText(caption, 120)
      || `Видео ${id.slice(0, 8)}`;
    result.push({
      id,
      label,
      verified: /сервером проверен/iu.test(caption),
    });
  });
  return result;
}

// Исходники проекта панель спрашивает у сервера САМА. Раньше она собирала их
// только из разметки, которую рисует мастер, а мастер рисует карточки лишь
// после выбора стратегии — выбора, который намеренно откладывается до кнопки
// «Подготовить…» (см. комментарий в setRoute: он необратим). Получалось
// замкнутое кольцо: список пуст, пока не начата подготовка, а подготовку
// нельзя начать без выбранного исходника. Своя загрузка это кольцо разрывает и
// ничего не активирует: чтение кандидатов не выбирает стратегию и не трогает
// деньги.
const copySourceVideoCache = { status: "idle", videos: [] };

// Добавляет ролик в список исходников, если его там ещё нет. Нужна ровно для
// свежезагруженных файлов: сервер уже знает про них, а список — ещё нет.
// Значение при этом не выбирается — выбор остаётся действием человека либо
// привязки, которая идёт следом.
function ensureSourceOption(form, mediaId, filename, durationSeconds = null) {
  const id = String(mediaId || "").trim().toLowerCase();
  if (!UUID_PATTERN.test(id)) return false;
  const label = cleanText(filename, 120) || "Загруженный ролик";
  const verifiedDuration = Number(durationSeconds);
  const duration = Number.isFinite(verifiedDuration) && verifiedDuration > 0
    ? Math.ceil(verifiedDuration)
    : null;
  let added = false;
  qa("[data-generation-intake-existing-video]", form).forEach((select) => {
    if (!(select instanceof HTMLSelectElement)) return;
    if ([...select.options].some((option) => option.value === id)) return;
    select.append(new Option(label, id));
    added = true;
  });
  const cachedIndex = copySourceVideoCache.videos.findIndex((video) => video.id === id);
  if (cachedIndex < 0 && (added || duration !== null)) {
    copySourceVideoCache.videos = [
      ...copySourceVideoCache.videos,
      {
        id,
        label,
        verified: duration !== null,
        durationSeconds: duration,
      },
    ];
  } else if (cachedIndex >= 0 && duration !== null) {
    copySourceVideoCache.videos = copySourceVideoCache.videos.map((video, index) => (
      index === cachedIndex
        ? { ...video, verified: true, durationSeconds: duration }
        : video
    ));
  }
  return added;
}

// Свежий стоп-кадр уже прошёл uploadProjectMedia/registerMedia как
// creator_reference, но refreshStrategyAssets может ожидать более ранний
// запрос и вернуть список, снятый до регистрации. Временная option не объявляет
// asset eligible и не подтверждает права: она лишь даёт существующему bind
// передать exact UUID дальше, где роль и права снова проверяет сервер.
function ensureOriginalProductOption(form, mediaId) {
  const id = String(mediaId || "").trim().toLowerCase();
  const select = form?.elements?.generation_strategy_original_product_media_id;
  if (!UUID_PATTERN.test(id) || !(select instanceof HTMLSelectElement)) return null;
  const existing = [...select.options].find((option) => option.value === id);
  if (existing) return existing;
  const option = new Option("Кадр исходного товара · загружен только что", id);
  option.dataset.generationIntakeSynthetic = "true";
  select.append(option);
  return option;
}

async function ensureCopySourceVideos() {
  if (copySourceVideoCache.status !== "idle") return;
  copySourceVideoCache.status = "loading";
  try {
    const api = await apiRuntime();
    const response = await api.generationStrategyAssetCandidates({
      projectId: projectId(),
      kind: "source_video",
      pageSize: 100,
    });
    const payload = response?.data ?? response;
    const assets = Array.isArray(payload?.assets) ? payload.assets : [];
    copySourceVideoCache.videos = assets
      .map((asset) => ({
        id: String(asset?.id || "").trim().toLowerCase(),
        filename: cleanText(asset?.filename, 120),
        durationSeconds: Number(asset?.duration_seconds),
      }))
      .filter((asset) => UUID_PATTERN.test(asset.id) && asset.filename)
      .map((asset) => ({
        id: asset.id,
        // Подпись повторяет ту, что рисует мастер: человек не должен видеть
        // два разных названия одного файла на одном экране.
        label: Number.isFinite(asset.durationSeconds) && asset.durationSeconds > 0
          ? `${asset.filename} · сервером проверен`
          : asset.filename,
        verified: Number.isFinite(asset.durationSeconds) && asset.durationSeconds > 0,
        // Длительность приходит вместе со списком и дальше задаёт ступень
        // «Длительность»: измеренная сервером величина — та же, которую он
        // потребует при привязке.
        durationSeconds: Number.isFinite(asset.durationSeconds)
          && asset.durationSeconds > 0
          ? asset.durationSeconds
          : null,
      }));
    copySourceVideoCache.status = "ready";
  } catch {
    // Отказ списка не ломает форму: остаётся загрузка файла с диска.
    copySourceVideoCache.videos = [];
    copySourceVideoCache.status = "error";
  }
  // Список исходников общий для всех маршрутов, поэтому годится контекст любой
  // смонтированной панели: берём первый живой.
  const context = [...engineRenderContexts.values()]
    .find((entry) => entry?.form?.isConnected && entry?.state);
  if (context) refreshVideoSelects(context.form, context.state);
}

function refreshVideoSelects(form, state) {
  const nativeSource = form.elements?.generation_strategy_source_video_id;
  const nativeVideos = nativeSource instanceof HTMLSelectElement
    ? [...nativeSource.options]
      .map((option) => ({
        id: String(option.value || "").trim().toLowerCase(),
        label: cleanText(option.textContent, 180),
      }))
      .filter(({ id }) => UUID_PATTERN.test(id))
    : [];
  const pickerVideos = collectPickerVideos(form);
  // Проверенные сервером ролики идут первыми, помечаются и выбираются по
  // умолчанию на экране копии.
  const verifiedIds = new Set([
    ...nativeVideos.map(({ id }) => id),
    ...pickerVideos.filter(({ verified }) => verified).map(({ id }) => id),
    ...copySourceVideoCache.videos
      .filter(({ verified }) => verified).map(({ id }) => id),
  ]);
  // Пока мастер не нарисовал карточки, свой список — единственный источник.
  // Запрос уходит один раз за загрузку страницы и только когда показывать
  // действительно нечего.
  if (!collectProjectVideos(form).length && !nativeVideos.length
      && !pickerVideos.length && !copySourceVideoCache.videos.length) {
    void ensureCopySourceVideos();
  }
  const videos = [...new Map([
    ...collectProjectVideos(form),
    ...nativeVideos,
    ...pickerVideos,
    ...copySourceVideoCache.videos,
  ].map((item) => [item.id, item])).values()]
    .map((item) => ({
      ...item,
      verified: verifiedIds.has(item.id),
      label: verifiedIds.has(item.id) && !/сервером проверен/iu.test(item.label)
        ? `${item.label} · сервером проверен`
        : item.label,
    }))
    .sort((left, right) => Number(right.verified) - Number(left.verified));
  qa("[data-generation-intake-existing-video]", state.shell).forEach((select) => {
    const current = select.value;
    const desired = [
      { id: "", label: "Не выбран файл проекта" },
      ...videos,
    ];
    const options = [...select.options];
    const unchanged = options.length === desired.length
      && desired.every(({ id, label }, index) => (
        options[index]?.value === id && options[index]?.text === label
      ));
    if (!unchanged) {
      select.replaceChildren(...desired.map(({ id, label }) => new Option(label, id)));
    }
    if (videos.some(({ id }) => id === current) && select.value !== current) {
      select.value = current;
    }
    if (
      copyViewActive()
      && select.dataset.generationIntakeExistingVideo === "copy_video"
      && !select.value
      && !selectedFile(panelFor(state, "copy_video"))
    ) {
      const firstVerified = videos.find(({ verified }) => verified);
      if (firstVerified) select.value = firstVerified.id;
    }
  });
}

function refreshAvatarSelect(form, state) {
  const select = q("[data-generation-intake-existing-avatar]", state.shell);
  if (!(select instanceof HTMLSelectElement)) return;
  const nativeAvatar = form.elements?.generation_strategy_avatar_media_id;
  const nativeImages = nativeAvatar instanceof HTMLSelectElement
    ? [...nativeAvatar.options]
      .map((option) => ({
        id: String(option.value || "").trim().toLowerCase(),
        label: cleanText(option.textContent, 180),
      }))
      .filter(({ id }) => UUID_PATTERN.test(id))
    : [];
  const images = [...new Map([
    ...collectProjectImages(form),
    ...nativeImages,
  ].map((item) => [item.id, item])).values()];
  const current = select.value;
  const desired = [
    { id: "", label: "Не выбрано фото из проекта" },
    ...images,
  ];
  const unchanged = select.options.length === desired.length
    && desired.every(({ id, label }, index) => (
      select.options[index]?.value === id
      && select.options[index]?.text === label
    ));
  if (!unchanged) {
    select.replaceChildren(...desired.map(({ id, label }) => new Option(label, id)));
  }
  if (images.some(({ id }) => id === current)) select.value = current;
}

// While a request is in flight setFormBusy disables every control and records
// its previous state in dataset.wasDisabled. Reading `:not(:disabled)` during
// that window sees zero photos and the route reports "Сейчас: 0" for a form the
// operator filled correctly, so the busy snapshot decides which are really off.
function checkedProductInputs(form) {
  const productRoot = q(".generation-intake-v4__product-items", form);
  const busyLocked = form?.dataset?.busy === "true";
  // В compact-режиме карточки находятся в productRoot. После
  // openNativeLaunch обычный маршрут возвращает РОВНО ТЕ ЖЕ узлы в нативный
  // fieldset, поэтому productRoot законно становится пустым. Считываем оба
  // положения и дедуплицируем объекты: это сохраняет счётчик, click-order и
  // handoff, не создавая второй выбор материалов.
  const inputs = [...new Set([
    ...qa('input[name="media_id"]:checked', productRoot),
    ...qa('input[name="media_id"]:checked', form),
  ])];
  return inputs.filter((input) => (
    busyLocked ? input.dataset.wasDisabled !== "true" : !input.disabled
  ));
}

function productSelectionOrder(input) {
  const order = Number(input?.dataset?.generationIntakeSelectionOrder);
  return Number.isSafeInteger(order) && order > 0 ? order : null;
}

// DOM-порядок карточек задаёт каталог, а не человек. Для Product Swap порядок
// кликов семантичен: первое фото становится primary для Pika, первые четыре
// уходят в Kling. Ранжированные кликом/восстановлением фото идут первыми;
// старые отмеченные карточки без ранга остаются стабильны в DOM-порядке.
function orderedProductInputs(inputs) {
  return inputs
    .map((input, domIndex) => ({
      input,
      domIndex,
      order: productSelectionOrder(input),
    }))
    .sort((left, right) => {
      if (left.order !== null && right.order !== null) {
        return left.order - right.order || left.domIndex - right.domIndex;
      }
      if (left.order !== null) return -1;
      if (right.order !== null) return 1;
      return left.domIndex - right.domIndex;
    })
    .map(({ input }) => input);
}

function orderedCheckedProductInputs(form) {
  return orderedProductInputs(checkedProductInputs(form));
}

function setProductSelectionOrder(input, order) {
  if (!input?.dataset) return;
  if (Number.isSafeInteger(order) && order > 0) {
    input.dataset.generationIntakeSelectionOrder = String(order);
  } else {
    delete input.dataset.generationIntakeSelectionOrder;
  }
}

function rememberProductSelectionChange(form, input) {
  if (!input?.checked) {
    setProductSelectionOrder(input, null);
    return;
  }
  if (productSelectionOrder(input) !== null) return;
  const nextOrder = checkedProductInputs(form).reduce(
    (highest, candidate) => Math.max(
      highest,
      productSelectionOrder(candidate) || 0,
    ),
    0,
  ) + 1;
  setProductSelectionOrder(input, nextOrder);
}

// Нативный checkbox сначала испускает input, затем change. Между ними общий
// app.js может изменить DOM, а MutationObserver — запланировать mount/restore.
// Сохраняем checked-state уже на input, чтобы restore никогда не увидел старые
// пять ID и не вернул только что снятую человеком галку. Programmatic change
// по-прежнему проходит через тот же helper из change-listener ниже.
function captureProductSelectionChange(form, input) {
  rememberProductSelectionChange(form, input);
  persistCopyPhotoSelection(form);
}

function selectedProductMediaIds(form) {
  const result = [];
  const seen = new Set();
  orderedCheckedProductInputs(form).forEach((input) => {
    const id = String(input.value || "").trim().toLowerCase();
    if (!UUID_PATTERN.test(id) || seen.has(id)) return;
    seen.add(id);
    result.push(id);
  });
  return result.slice(0, MAX_PRODUCT_IMAGES + 1);
}

function selectedProductFiles(panel) {
  const input = q('input[data-generation-intake-image="product"]', panel);
  const live = [...(input?.files || [])];
  // Очередь ещё не зарегистрированных файлов: выбор не теряется, даже если
  // перерисовка сбросила file-инпут (главная жалоба владелицы).
  const pending = pendingCopyProductFiles.get(projectId()) || [];
  const seen = new Set(live.map((file) => `${file.name}:${file.size}`));
  return [
    ...live,
    ...pending.filter((file) => !seen.has(`${file.name}:${file.size}`)),
  ];
}

function selectedAvatarFile(panel) {
  const input = q('input[data-generation-intake-image="avatar"]', panel);
  return input?.files?.[0] instanceof File ? input.files[0] : null;
}

function selectedAvatarMediaId(panel) {
  const value = String(
    q("[data-generation-intake-existing-avatar]", panel)?.value || "",
  ).trim().toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

function avatarInputMode(panel) {
  return String(
    q('input[data-generation-intake-avatar-mode]:checked', panel)?.value
    || "photo",
  );
}

function productSelectionCount(form, panel) {
  return selectedProductMediaIds(form).length + selectedProductFiles(panel).length;
}

function refreshProductSelectionCount(form, state) {
  pruneSyntheticProductOptions(form);
  // Product-слот один на форму и ПЕРЕЕЗЖАЕТ между «Копией» и «Созданием»
  // (relocateProductSlot). Жёсткий поиск в панели «Копии» на маршруте
  // «Создания» не находил счётчик и обрывал ВЕСЬ каскад обновлений — каскад
  // движков стратегии, её чеклист и кнопка не перерисовывались вовсе
  // (боевой скрин 25.08 22:28: «выбор ИИ» отсутствует). Ищем слот по shell и
  // считаем файлы в той панели, где он стоит сейчас.
  const slotNode = q("[data-generation-intake-product-slot]", state?.shell);
  const panel = slotNode?.closest?.("[data-generation-intake-panel]")
    || panelFor(state, "copy_video");
  const target = q("[data-generation-intake-product-count]", state?.shell)
    || q("[data-generation-intake-product-count]", panel);
  if (!target) return;
  // Грабля владельца: счётчик обязан живо считать ВМЕСТЕ выбранные файлы из
  // input и отмеченные готовые фото, а при переборе — объяснять, как исправить.
  const count = productSelectionCount(form, panel);
  setNodeText(
    target,
    count > MAX_PRODUCT_IMAGES
      ? `Сейчас: ${count} из ${MAX_PRODUCT_IMAGES} — лишние. Снимите галочки с готовых фото или очистите поле загрузки файлов.`
      : `Сейчас: ${count} из ${MAX_PRODUCT_IMAGES}`,
  );
  target.dataset.state = count >= MIN_PRODUCT_IMAGES && count <= MAX_PRODUCT_IMAGES
    ? "ready"
    : count > MAX_PRODUCT_IMAGES
      ? "error"
      : "neutral";
  const conflict = productSkuConflict(form);
  if (conflict) {
    target.dataset.state = "error";
    setNodeText(
      target,
      `Сейчас: ${count} из ${MAX_PRODUCT_IMAGES} — фото разных товаров. Оставьте SKU ${conflict.keep} и снимите: ${conflict.removeLabels.join(", ")}.`,
    );
  }
  // Очередь показывается только когда в ней что-то есть: пустая строка про
  // «0 файлов в очереди» была бы шумом, а невидимая непустая очередь —
  // фотографиями, которые считаются и которых человек не видит.
  const queued = selectedProductFiles(panel);
  const pendingLine = q("[data-generation-intake-pending-files]", panel);
  const pendingClear = q("[data-generation-intake-pending-clear]", panel);
  if (pendingLine) {
    setNodeText(
      pendingLine,
      queued.length
        ? `Файлы в очереди на регистрацию (${queued.length}): ${
          queued.map((file) => cleanText(file.name, 40)).join(", ")
        }`
        : "",
    );
    if (pendingLine.hidden === Boolean(queued.length)) {
      pendingLine.hidden = !queued.length;
    }
  }
  if (pendingClear && pendingClear.hidden === Boolean(queued.length)) {
    pendingClear.hidden = !queued.length;
  }
  refreshCopyChecklist(form, state);
  void ensureHypothesisPicker(form, state);
  refreshEngineChoice(form, state, "copy_video");
  refreshEngineChoice(form, state, "avatar_video");
  refreshEngineChoice(form, state, "strategy_video");
  renderStrategyChecklist(form, state);
  syncStrategyLaunchButton(form, state);
  // Ведущие грузятся один раз на проект и кэшируются: список меняется редко, а
  // перерисовок панели много.
  void ensureDuetPresenters(form, state);
  renderDuetPresenters(form, state);
  renderDuetProducts(form, state);
  ensureDuetCategoryControl(form, state);
  ensureDuetMechanicsInputs(state);
}

// Каскад «Чем генерируем и как долго» рисуется только по тому, что реально
// отдал реестр маршрутов: нет маршрутов — нет и карточки. Оператор никогда не
// выбирает то, чего не существует.
let engineChoiceBusy = false;

// Одна строка реестра в том виде, в котором её читает экран. Ставки, уровень и
// пределы длительности берутся как есть; отсутствующее поле остаётся null и
// ниже честно заменяется окном самого мастера, а не выдуманным числом.
// Маршруты приходят из мастера, но в незаполненной форме он каталог ещё не
// загружал — и карточка оставалась пустой без единого объяснения. Поэтому у
// экрана есть собственная загрузка: он спрашивает каталог сам, один раз, и
// перерисовывается, когда ответ пришёл. Мастер остаётся первичным источником:
// как только он загрузит каталог, берутся его данные.
// Кэш и контекст перерисовки живут ПО СТРАТЕГИЯМ, а не в одиночных переменных:
// каскад теперь рисуется не только у «Копии», и общий кэш означал бы, что
// маршруты одной стратегии показываются на панели другой. Это не косметика —
// движок доезжает до цены, и подмена показала бы человеку не ту сумму.
const engineRouteCaches = new Map();
const engineRenderContexts = new Map();

function engineRouteCache(strategyId) {
  if (!engineRouteCaches.has(strategyId)) {
    engineRouteCaches.set(strategyId, { status: "idle", routes: [] });
  }
  return engineRouteCaches.get(strategyId);
}

function guidedEngineRoutes(strategyId) {
  const routes = window.ContentEngineGenerationGuidedV4
    ?.getStrategyProviderRoutes?.(strategyId);
  return Array.isArray(routes) ? routes : [];
}

async function ensureEngineRoutes(strategyId) {
  const cache = engineRouteCache(strategyId);
  if (cache.status !== "idle") return;
  if (guidedEngineRoutes(strategyId).length) return;
  cache.status = "loading";
  try {
    const api = await apiRuntime();
    const response = await api.generationStrategyCatalog({
      organizationId: api.organizationId,
      projectId: projectId(),
    });
    const catalog = response?.catalog ?? response;
    const routes = catalog?.strategyProviderRoutes?.[strategyId];
    cache.routes = Array.isArray(routes) ? routes : [];
    cache.status = "ready";
  } catch {
    // Отказ каталога не должен ломать форму: карточка просто не появится, а
    // запуск по-прежнему идёт по действующему маршруту реестра.
    cache.routes = [];
    cache.status = "error";
  }
  const context = engineRenderContexts.get(strategyId);
  if (context?.section?.isConnected) {
    renderEngineChoice(context.form, context.state, context.section, strategyId);
  }
}

function engineRoutesFor(strategyId) {
  const guided = guidedEngineRoutes(strategyId);
  const routes = guided.length ? guided : engineRouteCache(strategyId).routes;
  return (Array.isArray(routes) ? routes : [])
    .filter((route) => (
      route
      && typeof route === "object"
      && String(route.provider || "").trim()
      && String(route.model_key || "").trim()
    ))
    .map((route) => ({
      id: engineId(route),
      provider: String(route.provider),
      label: modelPublicLabel(route),
      tier: String(route.tier || "").trim().toLowerCase(),
      priceKind: String(route.price_kind || "").trim(),
      priceRateMinor: Number.isFinite(Number(route.price_rate_minor))
        && Number(route.price_rate_minor) > 0
        ? Number(route.price_rate_minor)
        : null,
      minDurationSeconds: Number.isFinite(Number(route.min_duration_seconds))
        ? Number(route.min_duration_seconds)
        : null,
      maxDurationSeconds: Number.isFinite(Number(route.max_duration_seconds))
        ? Number(route.max_duration_seconds)
        : null,
      // Кто задаёт длительность. Правка видео отдаёт ролик длиной с исходник:
      // параметра длительности у таких моделей нет вовсе, и там, где секунда
      // стоит денег, выбор оператора означал бы резерв под чужой ролик.
      durationSource: route.duration_source === "source_video"
        ? "source_video"
        : "operator_choice",
      // Уровни качества движка. Ничего не достраиваем: движок, про режимы
      // которого сервер молчит, показывает одну ступень «как есть» — выдумать
      // разрешение значило бы обещать результат, которого не будет.
      qualityModes: Array.isArray(route.quality_modes)
        ? route.quality_modes
          .filter((mode) => (
            mode
            && typeof mode === "object"
            && String(mode.code || "").trim()
            && String(mode.label || "").trim()
            && ["720p", "1080p"].includes(String(mode.resolution || "").trim())
          ))
          .map((mode) => ({
            code: String(mode.code).trim(),
            label: String(mode.label).trim(),
            resolution: String(mode.resolution).trim(),
          }))
        : [],
      // Семейство и профиль входа движка — новые свойства реестра
      // (202608230020). Старый сервер их не отдаёт; тогда экран просто не
      // объясняет движок, а не выдумывает объяснение.
      engineFamily: ["edit", "regenerate", "overlay"].includes(route.engine_family)
        ? route.engine_family
        : null,
      inputProfile: route.input_profile && typeof route.input_profile === "object"
        ? route.input_profile
        : null,
      recommended: route.recommended === true,
      enabled: route.enabled === true,
    }));
}

// Порядок уровней задан ценой, а не алфавитом: сначала дешёвые. Неизвестный
// уровень не прячется — он встаёт последним под своим именем.
function orderedTiers(engines) {
  const tiers = [...new Set(engines.map((engine) => engine.tier))];
  const known = TIER_ORDER.filter((tier) => tiers.includes(tier));
  const unknown = tiers.filter((tier) => !TIER_ORDER.includes(tier)).sort();
  return [...known, ...unknown];
}

function wizardDurationControl(form) {
  const control = form?.elements?.generation_strategy_duration_seconds;
  return control instanceof HTMLInputElement ? control : null;
}

// Длительность исходника, ИЗМЕРЕННАЯ СЕРВЕРОМ во время бесплатной проверки
// MP4. Берётся из проекции выбранных исходников — там лежит именно серверный
// факт, а не браузерный замер: сервер потребует совпадения с ним, и показать
// человеку своё число значило бы подвести его под отказ.
//
// Округление ВВЕРХ: провайдер не умеет отдать ролик короче исходника, а резерв
// не имеет права быть меньше списания.
function verifiedSourceDurationSeconds(form) {
  // Источников серверной длительности два, и оба — один и тот же факт,
  // положенный в разные места: проекция выбранных исходников и список
  // исходников мастера, где длительность приезжает в data-атрибуте опции.
  // Экран «Копии» доходит до маршрута обоими путями (файл только что загружен
  // либо исходник выбран из проекта), поэтому спрашиваются оба: если знать
  // длительность можно, показывать вместо неё список секунд нельзя.
  const projection = window.ContentEngineGenerationGuidedV4
    ?.getStrategySourcePickerProjection?.(form);
  const selected = Array.isArray(projection?.selected)
    ? projection.selected
    : [];
  if (selected.length === 1) {
    const seconds = Number(selected[0]?.duration_seconds);
    if (Number.isFinite(seconds) && seconds > 0) return Math.ceil(seconds);
  }
  const control = form?.elements?.generation_strategy_source_video_id;
  const option = control instanceof HTMLSelectElement
    ? control.selectedOptions?.[0] || null
    : null;
  if (option?.dataset?.serverDurationVerified === "true") {
    const seconds = Number(option.dataset.durationSeconds);
    if (Number.isFinite(seconds) && seconds > 0) return Math.ceil(seconds);
  }
  // Третий источник — тот самый ролик, который выбран ЗДЕСЬ, в панели. Список
  // приходит с сервера вместе с измеренными длительностями, поэтому величина
  // остаётся серверной, а не браузерной.
  const panelSelect = q("[data-generation-intake-existing-video]", form);
  const panelValue = panelSelect instanceof HTMLSelectElement
    ? String(panelSelect.value || "").trim().toLowerCase()
    : "";
  if (UUID_PATTERN.test(panelValue)) {
    const video = copySourceVideoCache.videos
      .find((item) => item.id === panelValue);
    if (Number.isFinite(video?.durationSeconds) && video.durationSeconds > 0) {
      return Math.ceil(video.durationSeconds);
    }
  }
  return null;
}

// Окно, которое разрешает сам мастер: его min/max приходят из серверных
// output_rules стратегии. Значение вне этого окна сервер не подпишет, поэтому
// оно всегда участвует в пересечении.
function wizardDurationWindow(form) {
  const control = wizardDurationControl(form);
  const min = Number(control?.min);
  const max = Number(control?.max);
  return {
    min: Number.isFinite(min) && min > 0 ? Math.ceil(min) : MIN_COPY_DURATION,
    max: Number.isFinite(max) && max > 0 ? Math.floor(max) : MAX_COPY_DURATION,
  };
}

// Тайминги модели: пересечение пределов её строки реестра с окном мастера.
// Пока каталог не отдаёт min/max маршрута, честно остаётся одно окно мастера —
// это видно в подписи, и ни одна цифра не берётся из воздуха.
function engineDurationWindow(engine, form) {
  const wizard = wizardDurationWindow(form);
  const hasRegistryWindow = Number.isFinite(engine?.minDurationSeconds)
    && Number.isFinite(engine?.maxDurationSeconds)
    && engine.minDurationSeconds >= 1
    && engine.maxDurationSeconds >= engine.minDurationSeconds;
  return {
    min: hasRegistryWindow
      ? Math.max(wizard.min, Math.ceil(engine.minDurationSeconds))
      : wizard.min,
    max: hasRegistryWindow
      ? Math.min(wizard.max, Math.floor(engine.maxDurationSeconds))
      : wizard.max,
    fromRegistry: hasRegistryWindow,
  };
}

// Программная запись поля платного контекста.
//
// Движок и кампания входят в подпись цены, поэтому их смена обязана пройти
// через путь инвалидации в app.js: он слушает input/change по имени поля и
// сбрасывает и галку подтверждения траты, и её значение. Присваивание без
// события этот путь минует — и подтверждение остаётся от прежней конфигурации,
// то есть человек платит не за то, что подтверждал.
//
// Событие шлётся ТОЛЬКО при фактической смене значения, и это не оптимизация.
// Восстановление того же выбора после перерисовки — не изменение: панель
// слушает собственные мутации, и безусловная запись увела бы наблюдатель в
// цикл, а цену сбрасывала бы на ровном месте. Ровно та же семантика, что у
// applyCopyDuration и applyCopyResolution ниже.
function assignPaidContextValue(field, value) {
  const editable = field instanceof HTMLInputElement
    || field instanceof HTMLSelectElement;
  if (!editable || field.disabled) return false;
  const next = String(value ?? "");
  if (field.value === next) return false;
  field.value = next;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

// Длительность живёт там же, где её держит форма, — в
// generation_strategy_duration_seconds. Каскад её только выставляет, поэтому
// в подписанный выбор она попадает прежним путём (selection.duration_seconds).
function applyCopyDuration(form, seconds) {
  const control = wizardDurationControl(form);
  if (!control || control.disabled) return false;
  const next = String(seconds);
  if (control.value === next) return false;
  control.value = next;
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

// Compact -> guided is a real state handoff, not a second duration choice.
// Carry the same server measurement twice (top-level convenience + exact
// source asset) and accept it only when both copies agree with the same UUID.
// A malformed/stale session value therefore cannot silently rewrite output.
function handoffSourceDurationSeconds(handoff) {
  const sourceMediaId = String(handoff?.source_media_id || "")
    .trim().toLowerCase();
  if (!UUID_PATTERN.test(sourceMediaId) || !Array.isArray(handoff?.assets)) {
    return null;
  }
  const source = handoff.assets.find((asset) => (
    asset?.role === "source_video"
    && String(asset?.media_id || "").trim().toLowerCase() === sourceMediaId
  ));
  const topLevel = Number(handoff.source_duration_seconds);
  const assetLevel = Number(source?.duration_seconds);
  if (
    !Number.isFinite(topLevel)
    || !Number.isFinite(assetLevel)
    || topLevel <= 0
    || Math.ceil(topLevel) !== Math.ceil(assetLevel)
  ) return null;
  return Math.ceil(topLevel);
}

function applyHandoffSourceDuration(form, handoff) {
  const seconds = handoffSourceDurationSeconds(handoff);
  const control = wizardDurationControl(form);
  if (seconds === null || !control || control.disabled) return false;
  const minimum = Number(control.min);
  const maximum = Number(control.max);
  if (
    (Number.isFinite(minimum) && minimum > 0 && seconds < minimum)
    || (Number.isFinite(maximum) && maximum > 0 && seconds > maximum)
  ) return false;
  return applyCopyDuration(form, seconds) || control.value === String(seconds);
}

// Сложность выражена разрешением, и живёт оно там же, где его держит мастер, —
// в generation_strategy_resolution. Каскад его только выставляет, поэтому в
// подписанный выбор оно попадает прежним путём (selection.resolution) и тем же
// путём участвует в цене: маршрутный расчёт принимает разрешение отдельным
// аргументом. Значение, которого нет в списке мастера, не навязывается: сервер
// такой выбор всё равно не подпишет, и молчаливая подстановка обернулась бы
// отказом без объяснения.
function applyCopyResolution(form, resolution) {
  const control = form?.elements?.generation_strategy_resolution;
  if (!(control instanceof HTMLSelectElement) || control.disabled) return false;
  const next = String(resolution || "");
  if (!next || control.value === next) return false;
  if (![...control.options].some((option) => option.value === next)) return false;
  control.value = next;
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
}

// Есть ли у «Аватара» фотография прямо сейчас. Нужна не для красоты: обе модели
// fal требуют хотя бы одну ссылку на изображение — у Pika поле image_url
// обязательно, а ссылки @ImageN у Kling должны на что-то указывать. Режим
// «Описание аватара» исполняет только Runway Aleph, который принимает текст.
//
// Без этой проверки движок fal можно было бы выбрать в режиме описания: деньги
// зарезервировались бы, а сборка запроса упала бы уже после резерва — тем самым
// отказом, который выглядит как случайный сбой провайдера.
// Гашение движков, которым нечем работать без фотографии аватара. Вынесено
// отдельно, потому что это решение о доступности, а не оформление: его надо
// уметь проверить без DOM.
//
// Признак берётся по провайдеру: обе модели fal требуют ссылку на изображение
// (у Pika image_url обязателен, у Kling ссылки @ImageN должны на что-то
// указывать), а Runway Aleph принимает только текст. По-хорошему это свойство
// маршрута и должно приходить из реестра — тогда новый движок добавлялся бы
// строкой, а не правкой этой функции.
function withAvatarPhotoGate(engines, photoMissing) {
  if (!photoMissing) return engines;
  return engines.map((engine) => (
    engine.provider === "fal"
      ? { ...engine, enabled: false, unavailableReason: "нужна фотография аватара" }
      : engine
  ));
}

function avatarPhotoAvailable(state) {
  const panel = panelFor(state, "avatar_video");
  if (!panel) return false;
  if (avatarInputMode(panel) !== "photo") return false;
  return Boolean(selectedAvatarFile(panel) || selectedAvatarMediaId(panel));
}

// Состояние каскада — СВОЁ у каждой стратегии. Раньше слот был один
// (`state.copyEngine`) на все панели: «Дуэт», рисуясь последним, оставлял в нём
// `heygen:…`, память экспресс-панели запоминала его как движок «Копии» и при
// следующем монтировании писала в поле формы; «Копия» своего движка там не
// находила, ставила свой — change — монтирование — и так до зависания вкладки.
// «Копия» по-прежнему живёт в `state.copyEngine` (его читают память формы и
// обработчики), остальные стратегии — в `state.engineCascades[strategyId]`.
function cascadeStateFor(state, strategyId) {
  if (strategyId === COPY_AUTHORITY_STRATEGY) return state?.copyEngine || null;
  return state?.engineCascades?.[strategyId] || null;
}

function storeCascadeState(state, strategyId, value) {
  if (!state) return;
  if (strategyId === COPY_AUTHORITY_STRATEGY) {
    state.copyEngine = value;
    return;
  }
  if (!state.engineCascades) state.engineCascades = {};
  state.engineCascades[strategyId] = value;
}

// Панель, в которой произошло событие каскада, и её стратегия. Радиокнопки
// трёх панелей носят одно имя, поэтому различать их можно только по панели.
function cascadeEventRoute(target) {
  const panel = target?.closest?.("[data-generation-intake-panel]");
  const route = panel?.dataset?.generationIntakePanel || "copy_video";
  return ROUTE_AUTHORITY_STRATEGY[route] ? route : "copy_video";
}

// Синхронизация ползунков с состоянием каскада. Ползунок — зеркало выбора:
// DOM трогается только при смене отпечатка (панели под MutationObserver), и
// программное обновление value не рождает input-событий — цикла нет.
function syncCascadeSliders(section, context) {
  const {
    orderedEngines, selectedEngine, advisedEngine, durations, chosen,
    measuredSeconds,
  } = context;
  const wrap = q("[data-generation-intake-engine-slider]", section);
  const range = q("[data-generation-intake-engine-range]", section);
  if (wrap && range instanceof HTMLInputElement) {
    const usable = orderedEngines.filter((engine) => engine.enabled);
    if (usable.length < 2) {
      // Один движок — двигать нечего: остаётся ручной список с его подписями.
      if (!wrap.hidden) wrap.hidden = true;
    } else {
      if (wrap.hidden) wrap.hidden = false;
      const ids = usable.map((engine) => engine.id).join("|");
      const index = Math.max(
        0,
        usable.findIndex((engine) => engine.id === selectedEngine?.id),
      );
      const advisedId = advisedEngine?.id || "";
      const stamp = JSON.stringify([ids, index, advisedId]);
      if (range.dataset.stamp !== stamp) {
        range.dataset.stamp = stamp;
        range.dataset.engineIds = ids;
        range.max = String(usable.length - 1);
        range.value = String(index);
        const current = usable[index];
        const caption = q(
          "[data-generation-intake-engine-slider-caption]",
          section,
        );
        if (caption && current) {
          setNodeText(
            caption,
            `${current.label} · ${tierPublicLabel(current.tier)} · ${routePriceNote(current)}${
              current.id === advisedId ? " · ИИ-центр советует" : ""
            }`,
          );
        }
        const adviceLine = q(
          "[data-generation-intake-engine-slider-advice]",
          section,
        );
        if (adviceLine instanceof HTMLElement) {
          const showAdvice = Boolean(advisedId) && advisedId !== current?.id;
          if (showAdvice) {
            setNodeText(
              adviceLine,
              `Совет ИИ-центра под этот запуск: «${advisedEngine.label}».`,
            );
          }
          if (adviceLine.hidden === showAdvice) adviceLine.hidden = !showAdvice;
        }
      }
    }
  }
  const durationWrap = q("[data-generation-intake-duration-slider]", section);
  const durationRange = q("[data-generation-intake-duration-range]", section);
  const durationChips = q(
    '[data-generation-intake-choice="duration"]',
    section,
  );
  if (durationWrap && durationRange instanceof HTMLInputElement) {
    // Ползунок секунд — только когда секунды выбираются подряд; у маршрутов
    // «длина от исходника» и пустых окон остаются прежние подписи-чипы.
    const continuous = durations.length > 1
      && durations[durations.length - 1] - durations[0] === durations.length - 1;
    if (!continuous) {
      if (!durationWrap.hidden) durationWrap.hidden = true;
      if (durationChips instanceof HTMLElement && durationChips.hidden) {
        durationChips.hidden = false;
      }
    } else {
      if (durationWrap.hidden) durationWrap.hidden = false;
      if (durationChips instanceof HTMLElement && !durationChips.hidden) {
        durationChips.hidden = true;
      }
      const stamp = JSON.stringify([durations[0], durations.length, chosen]);
      if (durationRange.dataset.stamp !== stamp) {
        durationRange.dataset.stamp = stamp;
        durationRange.min = String(durations[0]);
        durationRange.max = String(durations[durations.length - 1]);
        if (chosen !== null) durationRange.value = String(chosen);
        const caption = q(
          "[data-generation-intake-duration-slider-caption]",
          section,
        );
        if (caption) {
          setNodeText(
            caption,
            chosen === null
              ? ""
              : `${chosen} с${measuredSeconds === chosen ? " — как в исходнике" : ""}`,
          );
        }
      }
    }
  }
}

function refreshEngineChoice(form, state, routeKey = "copy_video") {
  const strategyId = ROUTE_AUTHORITY_STRATEGY[routeKey];
  if (!strategyId) return;
  const panel = panelFor(state, routeKey);
  const section = panel ? q("[data-generation-intake-engine]", panel) : null;
  if (!section || engineChoiceBusy) return;
  engineChoiceBusy = true;
  try {
    renderEngineChoice(form, state, section, strategyId);
  } finally {
    engineChoiceBusy = false;
  }
}

function renderEngineChoice(form, state, section, strategyId) {
  engineRenderContexts.set(strategyId, { form, state, section });
  // Общие поля мастера (длительность, разрешение, движок) пишет только панель
  // АКТИВНОГО маршрута: остальные панели рисуются, но чужой платный контекст
  // не трогают. Иначе перерисовка всех трёх панелей заводит пинг-понг записей:
  // скрытая «Копия» утверждала длительность СВОЕГО исходника (8 с) поверх 15 с
  // «Создания», change будил sync-проходы, те — MutationObserver → mount →
  // снова запись; ~700 затираний в секунду на боевом прогоне 29.08.
  //
  // Второе слагаемое гейта — стратегия, выбранная В ФОРМЕ: после handoff в
  // конструктор generation_strategy_id держит чужую стратегию, а state.route
  // может остаться копийным — активная по маршруту панель всё равно не пишет
  // в чужую привязку. При пустом id (обычное редактирование компакт-панелей)
  // запись сохраняется.
  const routeActive = ROUTE_AUTHORITY_STRATEGY[state?.route] === strategyId;
  const formStrategyId = String(
    form?.elements?.generation_strategy_id?.value || "",
  ).trim();
  const writesShared = routeActive
    && (!formStrategyId || formStrategyId === strategyId);
  // Модель, которой нечего показать, недоступна — и сказать об этом надо ЗДЕСЬ,
  // на экране выбора, а не отказом после резервирования денег.
  const photoMissing = strategyId === AVATAR_AUTHORITY_STRATEGY
    && !avatarPhotoAvailable(state);
  const engines = withAvatarPhotoGate(engineRoutesFor(strategyId), photoMissing);
  if (!engines.length) {
    // Пустой каскад больше не исчезает молча («нету выбора ИИ», боевые скрины
    // 25–26.08): карточка остаётся и называет своё состояние, а отказ каталога
    // получает кнопку повтора — прежний кэш ошибки был вечным до перезагрузки.
    const cache = engineRouteCache(strategyId);
    if (section.hidden) section.hidden = false;
    let notice = q("[data-generation-intake-engine-empty]", section);
    if (!notice) {
      notice = el("div", "muted tiny");
      notice.dataset.generationIntakeEngineEmpty = "";
      section.prepend(notice);
    }
    const retry = cache.status === "error";
    const message = retry
      ? "Каталог движков не загрузился. "
      : "Каталог движков загружается…";
    if (notice.dataset.state !== cache.status) {
      notice.dataset.state = cache.status;
      notice.textContent = message;
      if (retry) {
        const button = el("button", "gi-link-button", "Повторить загрузку");
        button.type = "button";
        button.dataset.action = "generation-intake-retry-engines";
        button.dataset.strategyId = strategyId;
        notice.append(button);
      }
    }
    qa("[data-generation-intake-choice-block]", section).forEach((block) => {
      if (!block.hidden) block.hidden = true;
    });
    void ensureEngineRoutes(strategyId);
    return;
  }
  const emptyNotice = q("[data-generation-intake-engine-empty]", section);
  if (emptyNotice) emptyNotice.remove();
  qa("[data-generation-intake-choice-block]", section).forEach((block) => {
    if (block.hidden) block.hidden = false;
  });
  const cascade = cascadeStateFor(state, strategyId)
    || { modelId: "", qualityCode: "", durationNotice: "" };

  // ИИ-центр: совет по движку под ЭТОТ запуск — по фактам об исходнике,
  // товаре и замысле, а не по глобальной отметке «по умолчанию» в реестре.
  // Отметка реестра остаётся запасным ответом, когда советчику нечего сказать.
  // «Копия» и «Создание» получают совет; «Дуэт» — нет: у него один движок,
  // ведущий, и советовать там нечего.
  const advice = (strategyId === COPY_AUTHORITY_STRATEGY
      || strategyId === STRATEGY_AUTHORITY_STRATEGY)
      && typeof adviseGenerationEngine === "function"
    ? adviseGenerationEngine({
      routes: engines,
      facts: strategyId === COPY_AUTHORITY_STRATEGY
        ? copyEngineFacts(form, state)
        : rebuildEngineFacts(form, state),
    })
    : null;
  const advisedEngine = advice?.engineId
    ? engines.find((engine) => engine.id === advice.engineId && engine.enabled) || null
    : null;

  // Ступень 1 — сами движки, подряд и от дешёвого к дорогому. Уровень цены не
  // отдельная ступень, а подпись: человек выбирает не «дёшево», а модель,
  // и цена — её свойство, а не самостоятельный вопрос.
  const tierOrder = orderedTiers(engines);
  const orderedEngines = [...engines].sort((left, right) => {
    const byTier = tierOrder.indexOf(left.tier) - tierOrder.indexOf(right.tier);
    if (byTier !== 0) return byTier;
    return Number(right.recommended) - Number(left.recommended);
  });
  // Порядок старшинства: явный выбор человека → совет ИИ-центра → отметка
  // реестра → первый включённый. Выбор, который сделал не человек, а прошлый
  // совет, не закрепляется: изменились факты — изменится и совет.
  const humanChoice = cascade.humanChoice === true
    ? orderedEngines.find((engine) => engine.id === cascade.modelId && engine.enabled)
    : null;
  const selectedEngine = humanChoice
    || advisedEngine
    || orderedEngines.find((engine) => engine.id === cascade.modelId && engine.enabled)
    || orderedEngines.find((engine) => engine.recommended && engine.enabled)
    || orderedEngines.find((engine) => engine.enabled)
    || orderedEngines[0];
  // Отметка «ИИ-центр рекомендует» ставится только по совету советчика.
  // Флаг `recommended` реестра — умолчание маршрута, а не решение ИИ: печатать
  // его как совет значило бы выдавать умолчание за анализ («Дуэт» с одним
  // движком получал такую подпись ни за что).
  const advisedId = advisedEngine?.id || "";
  renderChoiceChips(
    q('[data-generation-intake-choice="model"]', section),
    orderedEngines.map((engine) => ({
      value: engine.id,
      title: engine.label,
      note: `${tierPublicLabel(engine.tier)} · ${providerPublicLabel(engine.provider)} · ${routePriceNote(engine)}${
        engine.enabled
          ? ""
          : ` · ${engine.unavailableReason || "пока недоступна"}`
      }`,
      provider: `${tierPublicLabel(engine.tier)} · ${providerPublicLabel(engine.provider)}`,
      price: routePriceNote(engine),
      duration: engineDurationNote(engine),
      condition: engineConditionNote(engine),
      visual: engineVisualKey(engine),
      recommended: engine.id === advisedId,
      disabled: !engine.enabled,
    })),
    selectedEngine?.id,
  );

  if (!selectedEngine) {
    // При непустом каталоге сюда не попасть (fallback берёт первый маршрут),
    // но и этот путь не имеет права прятать карточку: список моделей уже
    // нарисован выше, а «каскад не исчезает молча» — контракт экрана.
    if (section.hidden) section.hidden = false;
    return;
  }

  // Ступень 2 — сложность: уровни качества выбранной модели из реестра. Там,
  // где разрешение задаёт исходник, режим один — и подпись говорит об этом
  // прямо, вместо переключателя, который ничего не переключает.
  const qualityModes = Array.isArray(selectedEngine.qualityModes)
    ? selectedEngine.qualityModes
    : [];
  const selectedQuality = qualityModes.find((mode) => mode.code === cascade.qualityCode)
    || qualityModes[0]
    || null;
  renderChoiceChips(
    q('[data-generation-intake-choice="quality"]', section),
    qualityModes.map((mode) => ({
      value: mode.code,
      title: mode.label,
      note: mode.resolution,
      disabled: qualityModes.length < 2,
    })),
    selectedQuality?.code || "",
  );
  if (selectedQuality && writesShared) {
    applyCopyResolution(form, selectedQuality.resolution);
  }
  const qualityNotice = q("[data-generation-intake-quality-notice]", section);
  if (qualityNotice) {
    setNodeText(
      qualityNotice,
      !qualityModes.length
        ? "Реестр пока не отдаёт уровни этой модели — сервер выполнит запуск в разрешении по умолчанию."
        : qualityModes.length < 2
        ? `У «${selectedEngine.label}» разрешение результата задаёт исходник, выбирать нечего.`
        : `«${selectedEngine.label}» умеет ${qualityModes.length} уровня: чем выше, тем дороже.`,
    );
    if (qualityNotice.hidden) qualityNotice.hidden = false;
  }

  // Ступень 3 — тайминги выбранной модели. Несовместимое значение не остаётся
  // молча неверным: оно приводится к ближайшему допустимому, и об этом говорят
  // вслух.
  //
  // У правки видео длительности как выбора не существует: модель отдаёт ролик
  // длиной с исходник. Показывать там список секунд значило бы обещать выбор,
  // которого нет, а у посекундной ставки — ещё и зарезервировать деньги под
  // чужой ролик. Поэтому список сжимается до одного значения — длины
  // исходника, ИЗМЕРЕННОЙ СЕРВЕРОМ (та же величина, которую сервер потребует
  // при привязке; браузерный замер сюда не годится, он про другой файл).
  const durationWindow = engineDurationWindow(selectedEngine, form);
  // Длина загруженного ролика меряется один раз и нужна обоим видам маршрутов:
  // одному она задаёт длительность целиком, другому — подсказывает разумное
  // значение. Поэтому спрашивается всегда, а не только там, где обязательна.
  const measuredSeconds = verifiedSourceDurationSeconds(form);
  const bySource = selectedEngine.durationSource === "source_video";
  const sourceFits = measuredSeconds !== null
    && measuredSeconds >= durationWindow.min
    && measuredSeconds <= durationWindow.max;
  const sourceSeconds = bySource && sourceFits ? measuredSeconds : null;
  const durations = [];
  if (sourceSeconds !== null) {
    durations.push(sourceSeconds);
  } else if (!bySource) {
    // Решётка секунд модели: промежуточные значения (у Gen-4 Turbo — 6–9)
    // провайдер отверг бы уже ПОСЛЕ резерва, а цена откажет им до резерва.
    // Список чипов обязан совпадать с тем, что подпишет цена.
    const lattice = engineDurationLattice(selectedEngine);
    for (
      let seconds = durationWindow.min;
      seconds <= durationWindow.max;
      seconds += 1
    ) {
      if (lattice === null || lattice.includes(seconds)) {
        durations.push(seconds);
      }
    }
  }
  // Модели, которые взяли бы этот ролик целиком. Нужны, когда выбранная не
  // берёт: человеку показывают не тупик, а выход.
  const fittingEngines = measuredSeconds === null ? [] : engines.filter((engine) => (
    engine.enabled
    && engine.id !== selectedEngine.id
    && Number.isFinite(engine.minDurationSeconds)
    && Number.isFinite(engine.maxDurationSeconds)
    && measuredSeconds >= engine.minDurationSeconds
    && measuredSeconds <= engine.maxDurationSeconds
  ));
  // У маршрута, где длительность задаёт исходник, список секунд не строится
  // вовсе, пока длительность не измерена сервером. Показать выбор было бы
  // обманом дважды: выбрать всё равно нельзя, а у посекундной ставки
  // выбранная цифра ещё и назвала бы цену за чужой ролик.
  const control = wizardDurationControl(form);
  const current = Number(control?.value);
  let chosen = durations.includes(current) ? current : null;
  let notice = String(cascade.durationNotice || "");
  if (durations.length && chosen === null) {
    // Значение по умолчанию берётся у ролика, а не у середины окна: человек
    // копирует конкретный ролик, и его длина — самый осмысленный ответ из
    // возможных. К окну модели она всё равно приводится.
    chosen = sourceFits && durations.includes(measuredSeconds)
      ? measuredSeconds
      : Number.isFinite(current) && current > 0
      ? Math.min(durationWindow.max, Math.max(durationWindow.min, Math.round(current)))
      : durations[0];
    // Приведение к окну может дать значение, которого нет в списке (между 5
    // и 10 у Gen-4 Turbo пусто) — берётся ближайшая допустимая ступень, а не
    // молчаливо неверная.
    if (!durations.includes(chosen)) {
      chosen = durations.reduce((best, seconds) => (
        Math.abs(seconds - chosen) < Math.abs(best - chosen) ? seconds : best
      ), durations[0]);
    }
    if (
      Number.isFinite(current) && current > 0 && current !== chosen
      && writesShared && applyCopyDuration(form, chosen)
    ) {
      // Причина замены называется честно: у маршрута с длительностью от
      // исходника дело не в «недопустимом окне», а в том, что выбора нет
      // вовсе — и прежнее значение осталось от другого ролика или движка.
      notice = bySource
        ? `Длительность задаёт исходник: ${chosen} с. Прежнее значение ${current} с заменено.`
        : `${current} с не подходит для «${selectedEngine.label}»: допустимо `
          + `${durationWindow.min}–${durationWindow.max} с. Оставили ${chosen} с.`;
    } else if (writesShared) {
      applyCopyDuration(form, chosen);
    }
  }
  renderChoiceChips(
    q('[data-generation-intake-choice="duration"]', section),
    durations.map((seconds) => ({
      value: String(seconds),
      title: `${seconds} с`,
      // Длина ролика подписана прямо на варианте: так видно, какой из них
      // «как в исходнике», а какой — сознательное отклонение от него.
      ...(measuredSeconds === seconds ? { note: "как в исходнике" } : {}),
      // Единственное значение показывается, но не выбирается: это факт
      // исходника, а не решение оператора.
      disabled: !control || control.disabled || sourceSeconds !== null,
    })),
    chosen === null ? "" : String(chosen),
  );
  syncCascadeSliders(section, {
    orderedEngines,
    selectedEngine,
    advisedEngine,
    durations,
    chosen,
    measuredSeconds,
  });
  const durationNotice = q("[data-generation-intake-duration-notice]", section);
  if (durationNotice) {
    const fittingNames = fittingEngines.map((engine) => `«${engine.label}»`).join(", ");
    setNodeText(
      durationNotice,
      notice || (sourceSeconds !== null
        ? `«${selectedEngine.label}» отдаёт ролик длиной с исходник: ${sourceSeconds} с, проверено сервером. Выбирать здесь нечего.`
        // Ролик длиннее (или короче) того, что берёт выбранная модель. Это не
        // тупик: другие модели могут его взять, и они названы поимённо.
        : bySource && measuredSeconds !== null
        ? `Ролик длится ${measuredSeconds} с, а «${selectedEngine.label}» принимает ${durationWindow.min}–${durationWindow.max} с.${
          fittingNames ? ` Такой ролик возьмут: ${fittingNames}.` : " Другой подходящей модели сейчас нет — укоротите исходник."
        }`
        : bySource
        ? "Длительность задаёт исходник, но сервер её ещё не измерил — сделайте бесплатную проверку MP4."
        : durations.length
        ? `${
          durationWindow.fromRegistry
            ? `«${selectedEngine.label}» принимает ${durationWindow.min}–${durationWindow.max} с.`
            : `Реестр пока не отдаёт пределы этой модели, поэтому показано окно стратегии: ${durationWindow.min}–${durationWindow.max} с.`
        }${
          measuredSeconds !== null && sourceFits
            ? ` Ролик длится ${measuredSeconds} с — это значение и подставлено.`
            : measuredSeconds !== null
            ? ` Ролик длится ${measuredSeconds} с, в это окно он не помещается — выберите длительность вручную.`
            : ""
        }`
        : "Совместимой длительности у этой модели нет — выберите другую."),
    );
    if (durationNotice.hidden) durationNotice.hidden = false;
    const noticeState = notice ? "warning" : "neutral";
    if (durationNotice.dataset.state !== noticeState) {
      durationNotice.dataset.state = noticeState;
    }
  }

  // Цена ориентировочная: за ролик целиком, посекундно или по ступеням
  // кредитов. Окончательную сумму всё равно подтверждает сервер.
  const priceLine = q("[data-generation-intake-price-line]", section);
  const seconds = chosen === null ? null : chosen;
  setNodeText(
    priceLine,
    selectedEngine?.priceKind === "usd_minor_per_run" && selectedEngine.priceRateMinor
      ? `Этот ролик: ${usdFromMinor(selectedEngine.priceRateMinor)} за ролик целиком, длительность на цену не влияет.`
      : selectedEngine?.priceKind === "usd_minor_per_second"
        && selectedEngine.priceRateMinor && seconds !== null
      ? `Этот ролик: ${seconds} с × ${usdFromMinor(selectedEngine.priceRateMinor)} = ${usdFromMinor(seconds * selectedEngine.priceRateMinor)}.`
      : "Точную сумму подтвердит сервер бесплатной проверкой — деньги при этом не списываются.",
  );

  // Выбранный движок уходит в привязку отдельным полем и подписывается
  // сервером вместе с ценой. Поле формы пишется только при смене значения:
  // панель слушает собственные мутации, и безусловная запись увела бы
  // наблюдатель в цикл.
  // Поле движка ОДНО на всю форму, а панелей с каскадом несколько («Копия»,
  // «Дуэт», «Создание»), и перерисовываются они все разом. Пишет поле только
  // панель АКТИВНОГО маршрута: иначе две панели по очереди ставили бы свои
  // значения, каждая запись рождала change, наблюдатель перерисовывал панели
  // снова — и вкладка зависала в бесконечном пинг-понге.
  if (writesShared) {
    assignPaidContextValue(
      form?.elements?.generation_intake_engine,
      selectedEngine?.enabled ? selectedEngine.id : "",
    );
  }

  // Честность про исполнение: запуск идёт выбранной моделью, а отметка
  // «Советуем» остаётся подсказкой, а не приговором. Про недоступную модель
  // говорим прямо — иначе человек ждал бы от выбора того, чего не будет.
  const activeEngine = engines.find((engine) => engine.id === advisedId && engine.enabled)
    || null;
  setNodeText(
    q("[data-generation-intake-route-note]", section),
    engineAdviceNote(selectedEngine, activeEngine, advice, {
      advised: advice !== null,
      engineCount: engines.filter((engine) => engine.enabled).length,
    }),
  );

  storeCascadeState(state, strategyId, {
    modelId: selectedEngine?.id || "",
    qualityCode: selectedQuality?.code || "",
    durationNotice: notice,
    humanChoice: cascade.humanChoice === true && humanChoice !== null,
    advisedId,
  });
  if (section.hidden) section.hidden = false;
}

let copyChecklistBusy = false;

function refreshCopyChecklist(form, state) {
  const panel = panelFor(state, "copy_video");
  if (!panel || copyChecklistBusy) return;
  // Панель наблюдает за собственными мутациями и вызывает обновление в ответ.
  // Запись ниже обязана быть однопроходной, иначе наблюдатель зациклится.
  copyChecklistBusy = true;
  try {
    renderCopyChecklist(form, state, panel);
  } finally {
    copyChecklistBusy = false;
  }
}

function renderCopyChecklist(form, state, panel) {
  const route = state.routes?.copy_video || {};
  const setRow = (key, value, ready) => {
    const row = q(`[data-generation-intake-check="${key}"]`, panel);
    if (!row) return;
    setNodeText(q(".gi-check__value", row), value);
    const next = ready ? "ready" : "empty";
    if (row.dataset.state !== next) row.dataset.state = next;
  };

  const localFile = selectedFile(panel);
  const existing = selectedExistingVideo(panel);
  const sourceName = localFile?.name
    || (existing
      ? cleanText(
        q(`[data-generation-intake-existing-video="copy_video"] option:checked`, panel)?.textContent,
        60,
      )
      : "");
  const duration = Number(route.durationSeconds);
  setRow(
    "source",
    sourceName
      ? (Number.isFinite(duration) && duration > 0
        ? `${sourceName.slice(0, 22)} · ${duration.toFixed(1)} с`
        : sourceName.slice(0, 28))
      : "Не выбран",
    Boolean(sourceName),
  );

  const photos = productSelectionCount(form, panel);
  setRow(
    "product",
    photos ? `${photos} фото` : "0 фото",
    photos >= MIN_PRODUCT_IMAGES && photos <= MAX_PRODUCT_IMAGES,
  );

  const brief = currentRecommendation(form);
  setRow("brief", brief ? "Задан" : "Не задан", Boolean(brief));

  // Перерисовываем только по смене отпечатка: панель слушает собственные
  // мутации, и безусловная замена узлов уводит наблюдатель в бесконечный круг.
  const preview = q("[data-generation-intake-preview]", panel);
  if (preview) {
    const stamp = localFile
      ? `file:${localFile.name}:${localFile.size}:${localFile.lastModified}`
      : sourceName
        ? `media:${sourceName}:${Number.isFinite(duration) ? duration.toFixed(1) : ""}`
        : "empty";
    if (preview.dataset.stamp !== stamp) {
      if (preview.dataset.objectUrl) {
        URL.revokeObjectURL(preview.dataset.objectUrl);
        delete preview.dataset.objectUrl;
      }
      if (localFile) {
        const objectUrl = URL.createObjectURL(localFile);
        const video = document.createElement("video");
        video.src = objectUrl;
        video.controls = true;
        video.playsInline = true;
        video.preload = "metadata";
        preview.replaceChildren(video);
        preview.dataset.objectUrl = objectUrl;
      } else if (sourceName) {
        preview.replaceChildren(
          el("p", "gi-preview__name", sourceName.slice(0, 44)),
          el(
            "p",
            "gi-preview__empty",
            Number.isFinite(duration) && duration > 0
              ? `Файл проекта · ${duration.toFixed(1)} с · проверен сервером`
              : "Файл проекта · длительность проверим при подготовке",
          ),
        );
      } else {
        preview.replaceChildren(
          el("p", "gi-preview__empty", "Ролик появится здесь после выбора файла"),
        );
      }
      preview.dataset.stamp = stamp;
    }
  }

  const frameCard = q("[data-generation-intake-keyframe-card]", panel);
  const frameBox = q("[data-generation-intake-keyframe]", panel);
  const frame = route.storyboard?.frames?.find(
    (item) => item.index === route.selectedFrameIndex,
  );
  if (frameCard && frameBox) {
    const stamp = frame?.preview ? `frame:${route.selectedFrameIndex}` : "none";
    if (frameBox.dataset.stamp !== stamp) {
      if (frame?.preview) {
        const image = document.createElement("img");
        image.src = frame.preview;
        image.alt = "Кадр исходного ролика с товаром";
        frameBox.replaceChildren(image);
        frameCard.hidden = false;
      } else {
        frameBox.replaceChildren();
        frameCard.hidden = true;
      }
      frameBox.dataset.stamp = stamp;
    }
  }
}

function selectedProductIdentityFromCheckboxes(form) {
  for (const input of orderedCheckedProductInputs(form)) {
    const sku = cleanText(input.dataset?.mediaSku, 120);
    const productName = cleanText(input.dataset?.mediaProductName, 180);
    if (sku && productName) return { sku, product_name: productName };
  }
  return null;
}

function refreshIdentityVisibility(form, state) {
  // Файловый инпут товара один на форму и ПЕРЕЕЗЖАЕТ вместе со слотом в
  // панель «Создания» (relocateProductSlot). Смотреть очередь файлов надо в
  // активной панели: взгляд только в «Копию» прятал поля SKU/названия на
  // «Создании», и человек упирался в подсказку без самих полей (29.08).
  const panel = panelFor(
    state,
    state?.route === "strategy_video" ? "strategy_video" : "copy_video",
  ) || panelFor(state, "copy_video");
  const wrap = q("[data-generation-intake-identity]", state.shell);
  if (!panel || !wrap) return;
  const derived = selectedProductIdentityFromCheckboxes(form);
  if (derived) {
    // Идентичность товара уже подтверждена на выбранных фото — не спрашиваем снова.
    [["sku", derived.sku], ["product_name", derived.product_name]].forEach(
      ([fieldName, value]) => {
        const control = identityInput(state, fieldName);
        if (control instanceof HTMLInputElement && control.value !== value) {
          control.value = value;
        }
        syncIdentityToForm(form, fieldName, value);
      },
    );
  }
  const filesPending = selectedProductFiles(panel).length > 0;
  // SKU и название спрашиваются ТОЛЬКО при загрузке совершенно новых фото,
  // у которых нет идентичности товара.
  const needIdentityFields = filesPending && !derived;
  const categoryNode = q(
    '[data-generation-intake-identity-item="product_category"]',
    wrap,
  );
  const categoryKnown = Boolean(
    String(form.elements?.product_category?.value || "").trim()
    || String(identityInput(state, "product_category")?.value || "").trim(),
  );
  // Категория показывается только если неизвестна; однажды показанный select
  // не прячется от собственного выбора, чтобы его можно было поправить.
  const showCategory = !categoryKnown
    || (categoryNode instanceof HTMLElement && categoryNode.hidden === false);
  let visible = false;
  [
    ["sku", needIdentityFields],
    ["product_name", needIdentityFields],
    ["product_category", showCategory],
  ].forEach(([itemName, show]) => {
    const node = q(
      `[data-generation-intake-identity-item="${CSS.escape(itemName)}"]`,
      wrap,
    );
    if (node instanceof HTMLElement) node.hidden = !show;
    if (show) visible = true;
  });
  wrap.hidden = !visible;
}

// Смешение SKU на выбранных фото — одна честная ошибка с точным списком,
// какие фото снять. Товар определяется автоматически из оставшихся.
function productSkuConflict(form) {
  const groups = new Map();
  checkedProductInputs(form).forEach((input) => {
    const sku = cleanText(input.dataset?.mediaSku, 120);
    if (!sku) return;
    const container = input.closest("label, article, li, [data-media-card]") || input;
    const label = cleanText(
      q("strong", container)?.textContent || container.textContent,
      80,
    ) || String(input.value || "").slice(0, 8);
    if (!groups.has(sku)) groups.set(sku, []);
    groups.get(sku).push(label);
  });
  if (groups.size <= 1) return null;
  const ranked = [...groups.entries()]
    .sort((left, right) => right[1].length - left[1].length);
  return {
    keep: ranked[0][0],
    removeSkus: ranked.slice(1).map(([sku]) => sku),
    removeLabels: ranked.slice(1).flatMap(([, labels]) => labels),
  };
}

function copyPhotoStorageKey() {
  return `${COPY_PHOTO_STORAGE_PREFIX}${projectId()}`;
}

function persistCopyPhotoSelection(form) {
  try {
    const entries = orderedCheckedProductInputs(form)
      .map((input) => ({
        id: String(input.value || "").trim().toLowerCase(),
        sku: cleanText(input.dataset?.mediaSku, 120),
        product_name: cleanText(input.dataset?.mediaProductName, 180),
        label: cleanText(
          q("strong", input.closest("label") || input.parentElement)?.textContent,
          120,
        ),
      }))
      .filter((entry) => UUID_PATTERN.test(entry.id))
      .slice(0, MAX_PRODUCT_IMAGES);
    sessionStorage.setItem(copyPhotoStorageKey(), JSON.stringify(entries));
  } catch {
    // Персист выбора — вспомогательный и никогда не блокирует форму.
  }
}

function restoreCopyPhotoSelection(form, state) {
  let entries = [];
  try {
    entries = JSON.parse(sessionStorage.getItem(copyPhotoStorageKey()) || "[]");
  } catch {
    entries = [];
  }
  if (!Array.isArray(entries) || !entries.length) return;
  entries.slice(0, MAX_PRODUCT_IMAGES).forEach((entry, index) => {
    const id = String(entry?.id || "").trim().toLowerCase();
    if (!UUID_PATTERN.test(id)) return;
    const existing = existingMediaCheckbox(form, id);
    if (existing instanceof HTMLInputElement) {
      setProductSelectionOrder(existing, index + 1);
      if (!existing.disabled && !existing.checked) {
        existing.checked = true;
        existing.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return;
    }
    const sku = cleanText(entry?.sku, 120);
    const productName = cleanText(entry?.product_name, 180);
    const restored = ensureProductCheckbox(
      form,
      state,
      id,
      sku && productName ? { sku, product_name: productName } : null,
      cleanText(entry?.label, 120),
    );
    setProductSelectionOrder(restored, index + 1);
  });
  // ensureProductCheckbox может породить change до назначения восстановленного
  // ранга. Финальная запись канонизирует массив ровно в сохранённом порядке.
  persistCopyPhotoSelection(form);
  refreshProductSelectionCount(form, state);
}

// Требование владелицы: файлы регистрируются на сервере СРАЗУ при выборе
// (тем же creator_register_media, что и подготовка), появляются выбранными
// чипами из серверного списка, а file-инпут очищается — «грузить второй раз»
// больше не нужно. Пока не хватает прав или идентичности, файлы честно ждут
// в очереди и не теряются.
async function registerSelectedProductPhotos(form, state) {
  const panel = panelFor(state, "copy_video");
  if (!panel) return;
  const input = q('input[data-generation-intake-image="product"]', panel);
  const project = projectId();
  const queue = pendingCopyProductFiles.get(project) || [];
  const fresh = [...(input?.files || [])];
  if (input instanceof HTMLInputElement && fresh.length) input.value = "";
  const known = new Set(queue.map((file) => `${file.name}:${file.size}`));
  fresh.forEach((file) => {
    const key = `${file.name}:${file.size}`;
    if (!known.has(key)) {
      known.add(key);
      queue.push(file);
    }
  });
  pendingCopyProductFiles.set(project, queue);
  refreshProductSelectionCount(form, state);
  refreshIdentityVisibility(form, state);
  if (!queue.length || state.productUploadBusy) return;
  const rights = q('[data-generation-intake-rights="copy_video"]', panel)?.checked === true;
  const identity = selectedProductIdentityFromCheckboxes(form)
    || currentProductIdentity(form);
  const blockers = [];
  if (!rights) blockers.push("поставьте единую галку прав");
  if (!identity) blockers.push("заполните артикул и название товара");
  if (blockers.length) {
    setStatus(
      panel,
      `Фото не потеряются: ${queue.length} в очереди. Чтобы зарегистрировать их в проекте, ${blockers.join(" и ")} — регистрация продолжится автоматически.`,
      "neutral",
    );
    return;
  }
  state.productUploadBusy = true;
  let registeredAny = false;
  const dropMessages = {
    image_required: "Файл не похож на фотографию.",
    image_too_large: "Фотография больше 16 МБ.",
    image_type_invalid: "Поддерживаются только JPG, PNG и WEBP.",
    image_signature_invalid: "Расширение файла не совпадает с его содержимым.",
    image_dimensions_too_small: "Фотография должна быть не меньше 256×256 пикселей.",
  };
  try {
    while (queue.length) {
      const file = queue[0];
      setStatus(panel, `Регистрируем фото «${cleanText(file.name, 60)}» в проекте…`, "busy");
      try {
        await assertImage(file);
      } catch (imageError) {
        queue.shift();
        pendingCopyProductFiles.set(project, queue);
        const rejection = imageError?.message === "media_kind_mime_mismatch"
          ? mediaKindMimeMismatchMessage(imageError, file.name)
          : `«${cleanText(file.name, 60)}»: ${dropMessages[imageError?.message] || "файл не прошёл проверку."}`;
        setStatus(
          panel,
          `${rejection} Остальные файлы в очереди не потеряны (${queue.length}).`,
          "error",
        );
        continue;
      }
      const mediaId = await uploadProjectMedia(file, "product_photo", identity);
      const registered = ensureProductCheckbox(form, state, mediaId, identity, file.name);
      attachProductFilePreview(registered, file);
      queue.shift();
      pendingCopyProductFiles.set(project, queue);
      persistCopyPhotoSelection(form);
      refreshProductSelectionCount(form, state);
      setStatus(
        panel,
        "Фото зарегистрированы в проекте и выбраны. Загружать их повторно не нужно — выбор переживает перерисовку.",
        "ready",
      );
      registeredAny = true;
    }
    // Список товаров «Дуэта» выводится из страницы ассетов мастера; без её
    // перечитывания только что заведённый товар появлялся там лишь после
    // перезагрузки страницы.
    if (registeredAny) {
      await window.ContentEngineGenerationGuidedV4?.refreshStrategyAssets?.(form);
      renderDuetProducts(form, state);
    }
  } catch (error) {
    console.warn("Copy product photo registration failed", error);
    setStatus(
      panel,
      `Не удалось зарегистрировать фото — платных действий не было. Файлы ждут в очереди (${queue.length}) и не потеряны; повторите позже.`,
      "error",
    );
  } finally {
    state.productUploadBusy = false;
    refreshProductSelectionCount(form, state);
    refreshIdentityVisibility(form, state);
  }
}

// На отдельном экране копии стратегия движка выбирается сразу при
// монтировании — тем же способом, каким это делает «Показать цену»
// (selectStrategy по нативной кнопке SELECT). Без этого guided не загружает
// серверные кандидаты пикера, и селект «Исходный ролик» остаётся пустым.
// Это бесплатный шаг: привязка, цена и платный запуск остаются за своими
// кнопками. Кнопки каталога появляются асинхронно, поэтому вызов повторяется
// из mount при каждом пересинке, пока стратегия не выбрана.
function ensureCopyEngineStrategy(form) {
  if (!copyViewActive()) return;
  const current = String(
    form.elements?.generation_strategy_id?.value || "",
  ).trim();
  if (current === COPY_AUTHORITY_STRATEGY) return;
  if (!selectStrategy(form, COPY_AUTHORITY_STRATEGY)) return;
  void window.ContentEngineGenerationGuidedV4?.refreshStrategyAssets?.(form);
}

function generationViewHref(view) {
  const id = projectId();
  return `#/workspace/generation?view=${view}${id ? `&project_id=${id}` : ""}`;
}

function syncCopyScreenChrome(state) {
  const panel = panelFor(state, "copy_video");
  if (!panel) return;
  const copyScreen = copyViewActive();
  const screenLink = q("[data-generation-intake-copy-screen-link]", panel);
  const backLink = q("[data-generation-intake-copy-back-link]", panel);
  if (screenLink instanceof HTMLAnchorElement) {
    screenLink.href = generationViewHref(COPY_VIEW_QUERY);
    screenLink.hidden = copyScreen;
  }
  if (backLink instanceof HTMLAnchorElement) {
    backLink.href = generationViewHref("create");
    backLink.hidden = !copyScreen;
  }
  // На отдельном экране авто-разбор MP4 встроен в «Показать цену», поэтому
  // кнопка не ждёт отдельного клика «Разобрать MP4».
  const button = priceButtonFor(panel);
  if (copyScreen && button instanceof HTMLButtonElement && !state.busy) {
    const form = state.shell?.closest?.("form");
    button.disabled = expressPaidAuthorityLocked(form);
  }
}

async function sha256Hex(blob) {
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

// Browser `accept` is only a chooser hint and can be bypassed by drag/drop or
// automation. The kind↔MIME contract therefore runs again immediately before
// upload and registration. A mismatch throws before apiRuntime, Storage or RPC
// are touched and carries enough safe detail for an exact operator message.
function assertMediaKindMime(file, kind) {
  const contract = MEDIA_KIND_MIME_CONTRACT[String(kind || "")];
  const mime = String(file?.type || "").trim().toLowerCase();
  if (
    contract
    && file instanceof File
    && contract.allowed.has(mime)
  ) return true;
  const failure = new Error("media_kind_mime_mismatch");
  failure.filename = cleanText(file?.name, 120) || "файл без имени";
  failure.mime = cleanText(mime, 120) || "MIME не указан";
  failure.expectedClass = contract?.expected || "поддерживаемый медиакласс";
  failure.kind = String(kind || "");
  throw failure;
}

function mediaKindMimeMismatchMessage(error, fallbackFilename = "") {
  const filename = cleanText(
    error?.filename || fallbackFilename,
    120,
  ) || "файл без имени";
  const expected = cleanText(error?.expectedClass, 120)
    || "поддерживаемый медиакласс";
  const received = cleanText(error?.mime, 120) || "MIME не указан";
  return `«${filename}» не принят: ожидалось ${expected}, получено ${received}. Файл не загружен и не зарегистрирован.`;
}

async function assertImage(file) {
  assertMediaKindMime(file, "product_photo");
  if (!(file instanceof File) || file.size < 32) throw new Error("image_required");
  if (file.size > MAX_IMAGE_BYTES) throw new Error("image_too_large");
  if (!PRODUCT_IMAGE_TYPES.has(String(file.type || "").toLowerCase())) {
    throw new Error("image_type_invalid");
  }
  const head = new Uint8Array(await file.slice(0, 16).arrayBuffer());
  const jpeg = head[0] === 0xff && head[1] === 0xd8 && head[2] === 0xff;
  const png = head[0] === 0x89 && head[1] === 0x50 && head[2] === 0x4e
    && head[3] === 0x47;
  const riff = new TextDecoder("latin1").decode(head.slice(0, 4)) === "RIFF";
  const webp = new TextDecoder("latin1").decode(head.slice(8, 12)) === "WEBP";
  if (!(jpeg || png || (riff && webp))) throw new Error("image_signature_invalid");
  const bitmap = await createImageBitmap(file);
  const dimensions = { width: bitmap.width, height: bitmap.height };
  bitmap.close();
  if (dimensions.width < 256 || dimensions.height < 256) {
    throw new Error("image_dimensions_too_small");
  }
  return dimensions;
}

async function assertMp4(file, maximumDuration) {
  assertMediaKindMime(file, "source_video");
  if (!(file instanceof File) || file.size < 32) throw new Error("mp4_required");
  if (file.size > MAX_MP4_BYTES) throw new Error("mp4_too_large");
  const head = new Uint8Array(await file.slice(0, 64).arrayBuffer());
  const signature = new TextDecoder("latin1").decode(head);
  if (!signature.includes("ftyp")) throw new Error("mp4_signature_invalid");
  // Длительность меряет и сервер, и он тут власть. Браузерный замер — только
  // удобство: он позволяет отказать раньше и назвать точные секунды. Поэтому
  // неудача замера НЕ должна закрывать человеку дорогу: бывают сборки браузера
  // и способы подстановки файла, где метаданные не читаются, хотя сам файл
  // исправен. В таком случае идём дальше без длительности и даём решать серверу.
  let metadata = null;
  try {
    metadata = await videoMetadata(file);
  } catch {
    metadata = null;
  }
  if (metadata === null) {
    return { duration: null, sha256: await sha256Hex(file), size: file.size };
  }
  if (!Number.isFinite(metadata.duration) || metadata.duration <= 0) {
    return { ...metadata, duration: null, sha256: await sha256Hex(file), size: file.size };
  }
  if (metadata.duration > maximumDuration + 0.05) {
    // Отказ по длительности обязан назвать измеренное число: человеку нужно
    // знать, на сколько именно резать ролик.
    const failure = new Error("mp4_duration_too_long");
    failure.durationSeconds = metadata.duration;
    failure.maximumSeconds = maximumDuration;
    throw failure;
  }
  return { ...metadata, sha256: await sha256Hex(file), size: file.size };
}

function videoMetadata(file) {
  return new Promise((resolve, reject) => {
    const video = document.createElement("video");
    const url = URL.createObjectURL(file);
    const done = (value, error = null) => {
      URL.revokeObjectURL(url);
      video.removeAttribute("src");
      video.load();
      if (error) reject(error);
      else resolve(value);
    };
    const timer = setTimeout(() => done(null, new Error("mp4_metadata_timeout")), 15_000);
    video.preload = "metadata";
    video.muted = true;
    video.onloadedmetadata = () => {
      clearTimeout(timer);
      done({
        duration: Number(video.duration),
        width: Number(video.videoWidth),
        height: Number(video.videoHeight),
      });
    };
    video.onerror = () => {
      clearTimeout(timer);
      done(null, new Error("mp4_metadata_invalid"));
    };
    video.src = url;
  });
}

function seekVideo(video, time) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("mp4_seek_timeout")), 8_000);
    const finish = () => {
      clearTimeout(timer);
      video.removeEventListener("seeked", finish);
      resolve();
    };
    video.addEventListener("seeked", finish, { once: true });
    video.currentTime = Math.max(0, Math.min(time, Math.max(0, video.duration - 0.04)));
  });
}

function frameScore(context, width, height) {
  const sampleWidth = Math.min(160, width);
  const sampleHeight = Math.max(1, Math.round(sampleWidth * height / width));
  const canvas = document.createElement("canvas");
  canvas.width = sampleWidth;
  canvas.height = sampleHeight;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(context.canvas, 0, 0, sampleWidth, sampleHeight);
  const data = ctx.getImageData(0, 0, sampleWidth, sampleHeight).data;
  let sum = 0;
  let sumSquares = 0;
  let edges = 0;
  let previous = 0;
  const count = data.length / 4;
  for (let index = 0; index < data.length; index += 4) {
    const luminance = data[index] * 0.2126 + data[index + 1] * 0.7152 + data[index + 2] * 0.0722;
    sum += luminance;
    sumSquares += luminance * luminance;
    if (index && Math.abs(luminance - previous) > 28) edges += 1;
    previous = luminance;
  }
  const mean = sum / count;
  const variance = Math.max(0, sumSquares / count - mean * mean);
  const exposurePenalty = Math.abs(mean - 128) * 0.35;
  return variance + edges * 4 - exposurePenalty;
}

async function captureStoryboard(file, count = STORYBOARD_FRAME_COUNT) {
  const video = document.createElement("video");
  const url = URL.createObjectURL(file);
  video.src = url;
  video.muted = true;
  video.playsInline = true;
  // Без предела ожидание метаданных может не завершиться никогда: тогда кнопка
  // «висит» без единого сообщения. Лучше честно упасть и дать вызывающему
  // решить, обязательна ли раскадровка.
  await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error("mp4_storyboard_timeout")),
      12_000,
    );
    video.onloadedmetadata = () => { clearTimeout(timer); resolve(); };
    video.onerror = () => {
      clearTimeout(timer);
      reject(new Error("mp4_storyboard_invalid"));
    };
  });
  const width = Math.max(2, video.videoWidth);
  const height = Math.max(2, video.videoHeight);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const frames = [];
  for (let index = 0; index < count; index += 1) {
    const time = Math.min(
      Math.max(0, video.duration - 0.05),
      video.duration * ((index + 0.5) / count),
    );
    await seekVideo(video, time);
    context.drawImage(video, 0, 0, width, height);
    const preview = canvas.toDataURL("image/jpeg", 0.78);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
    if (!(blob instanceof Blob)) throw new Error("mp4_frame_encode_failed");
    frames.push({
      index,
      time,
      preview,
      blob,
      width,
      height,
      score: frameScore(context, width, height),
    });
  }
  URL.revokeObjectURL(url);
  video.removeAttribute("src");
  video.load();
  frames.sort((left, right) => right.score - left.score);
  const recommendedIndex = frames[0]?.index ?? 0;
  frames.sort((left, right) => left.index - right.index);
  return { frames, recommendedIndex, duration: video.duration || 0, width, height };
}

function renderStoryboard(panel, storyboard, state) {
  const section = q("[data-generation-intake-storyboard]", panel);
  const grid = q(".generation-intake-v4__frames", section);
  if (!section || !grid) return;
  section.hidden = false;
  // Карточка кадров пустует до разбора ролика: отметка снимает её со сцены,
  // пока показывать нечего, и возвращает вместе с первыми кадрами.
  section.dataset.hasFrames = storyboard.frames.length ? "true" : "false";
  q("[data-generation-intake-frame-note]", section)?.remove();
  grid.replaceChildren();
  storyboard.frames.forEach((frame) => {
    const button = el("button", "generation-intake-v4__frame");
    button.type = "button";
    button.dataset.frameIndex = String(frame.index);
    button.setAttribute("aria-pressed", String(frame.index === state.selectedFrameIndex));
    if (frame.index === storyboard.recommendedIndex) {
      button.dataset.recommended = "true";
    }
    const image = document.createElement("img");
    image.src = frame.preview;
    image.alt = `Кадр на ${frame.time.toFixed(1)} секунде`;
    button.append(
      image,
      el("span", "", `${frame.time.toFixed(1)} с`),
      frame.index === storyboard.recommendedIndex
        ? el("small", "", "Рекомендуем")
        : document.createTextNode(""),
    );
    grid.append(button);
  });
}

function selectedFile(panel) {
  const input = q('input[data-generation-intake-mp4="single"]', panel);
  return input?.files?.[0] instanceof File ? input.files[0] : null;
}

function selectedExistingVideo(panel) {
  const select = q("[data-generation-intake-existing-video]", panel);
  const value = String(select?.value || "").trim().toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

async function apiRuntime() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") throw new Error("workspace_api_unavailable");
  const api = await Promise.resolve(factory());
  if (!api) throw new Error("workspace_api_unavailable");
  return api;
}

function findUuid(value, depth = 0) {
  if (depth > 5 || value == null) return "";
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return UUID_PATTERN.test(normalized) ? normalized : "";
  }
  if (Array.isArray(value)) {
    for (const child of value) {
      const found = findUuid(child, depth + 1);
      if (found) return found;
    }
    return "";
  }
  if (typeof value === "object") {
    for (const key of ["media_id", "id", "mediaId"]) {
      const found = findUuid(value[key], depth + 1);
      if (found) return found;
    }
    for (const child of Object.values(value)) {
      const found = findUuid(child, depth + 1);
      if (found) return found;
    }
  }
  return "";
}

function safeFilename(value, fallback) {
  const normalized = String(value || fallback)
    .normalize("NFKD")
    .replace(/[^A-Za-z0-9._-]+/gu, "-")
    .replace(/-+/gu, "-")
    .replace(/^-|-$/gu, "")
    .slice(0, 96);
  return normalized || fallback;
}

function privateObjectKey(api, file, kind) {
  const prefix = String(api?.storagePrefix || "");
  if (!prefix || !prefix.endsWith("/") || prefix.includes("..")) {
    throw new Error("private_upload_prefix_unavailable");
  }
  const month = new Date().toISOString().slice(0, 7);
  const token = crypto.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const fallback = kind === "source_video" ? "source.mp4" : "reference.jpg";
  const name = safeFilename(file.name, fallback);
  return `${prefix}uploads/${month}/${token}-${name}`;
}

function withOrganization(api, payload) {
  return typeof api?.withOrganization === "function"
    ? api.withOrganization(payload)
    : payload;
}

function normalizeDirectMp4Attachment(response, mediaId) {
  const root = response?.data && typeof response.data === "object"
    ? response.data
    : response;
  const attachmentMediaId = String(root?.attachment?.media_id || "")
    .trim()
    .toLowerCase();
  if (
    root?.ok !== true
    || root?.version !== "generation-direct-mp4-attachment-v1"
    || attachmentMediaId !== mediaId
    || !UUID_PATTERN.test(String(root?.attachment?.id || "").toLowerCase())
    || root?.contract?.registered_media_reused !== true
    || root?.contract?.provider_call_started !== false
    || root?.contract?.paid_call_started !== false
  ) {
    throw new Error("direct_mp4_attachment_response_invalid");
  }
  return root;
}

async function attachDirectMp4(api, mediaId) {
  if (typeof api?.call !== "function") {
    throw new Error("direct_mp4_attachment_unavailable");
  }
  const response = await api.call(
    DIRECT_MP4_ATTACHMENT_RPC,
    withOrganization(api, {
      project_id: projectId(),
      media_id: mediaId,
      idempotency_key: `generation-direct-mp4-${mediaId}`,
    }),
  );
  return normalizeDirectMp4Attachment(response, mediaId);
}

async function registerUploadedMedia(
  api,
  file,
  objectKey,
  kind,
  sha256,
  productIdentity = null,
) {
  assertMediaKindMime(file, kind);
  if (typeof api.registerMedia !== "function") {
    throw new Error("register_media_unavailable");
  }
  const response = await api.registerMedia({
    projectId: projectId(),
    bucket: String(api.storageBucket || "contentengine-private"),
    object_key: objectKey,
    original_filename: file.name,
    mime_type: file.type,
    size_bytes: file.size,
    sha256,
    kind,
    ...(productIdentity || {}),
    rights_confirmed: true,
  });
  const mediaId = findUuid(response);
  if (!mediaId) throw new Error("register_media_response_invalid");
  return mediaId;
}

// Приложенный человеком кадр регистрируется тем же creator_reference, что и
// кадр раскадровки: дальше по конвейеру между ними разницы нет, и спецификация
// получает ровно тот же вид ассета.
async function registerCopyOriginalFrame(state, file) {
  const panel = panelFor(state, "copy_video");
  const slot = panel ? q("[data-generation-intake-original-frame]", panel) : null;
  const status = slot
    ? q("[data-generation-intake-original-frame-status]", slot)
    : null;
  if (status) status.textContent = "Загружаем кадр исходного товара…";
  try {
    const mediaId = await uploadProjectMedia(file, "creator_reference");
    state.routes.copy_video = {
      ...state.routes.copy_video,
      originalFrameMediaId: mediaId,
    };
    if (status) {
      status.textContent =
        `Кадр принят: ${file.name}. Нажмите «Подготовить ролик».`;
    }
  } catch (error) {
    if (status) {
      status.textContent = error?.message === "media_kind_mime_mismatch"
        ? mediaKindMimeMismatchMessage(error, file?.name)
        : "Кадр не загрузился. Попробуйте ещё раз или выберите другой файл.";
    }
    console.warn("Original product frame upload failed", error);
  }
}

async function uploadProjectMedia(file, kind, productIdentity = null) {
  // Must precede apiRuntime/object-key/hash work: a cross-kind file performs
  // zero upload and zero registration calls.
  assertMediaKindMime(file, kind);
  const api = await apiRuntime();
  if (typeof api.uploadPrivateObject !== "function") {
    throw new Error("private_upload_unavailable");
  }
  const sha256 = await sha256Hex(file);
  const objectKey = privateObjectKey(api, file, kind);
  await api.uploadPrivateObject(objectKey, file);
  let mediaId = "";
  try {
    mediaId = await registerUploadedMedia(
      api,
      file,
      objectKey,
      kind,
      sha256,
      productIdentity,
    );
  } catch (error) {
    if (typeof api.removePrivateObject === "function") {
      await Promise.resolve(api.removePrivateObject(objectKey)).catch(() => {});
    }
    throw error;
  }
  if (kind === "source_video") await attachDirectMp4(api, mediaId);
  return mediaId;
}

function panelFor(state, route) {
  if (!state?.shell) return null;
  return q(`[data-generation-intake-panel="${CSS.escape(route)}"]`, state.shell);
}

function routeBusyActionButtons(state, route, action) {
  const panel = panelFor(state, route);
  const actionButtons = action
    ? qa(`[data-action="${CSS.escape(action)}"]`, panel)
    : [];
  return [
    ...actionButtons,
    ...qa("[data-generation-intake-route]", state.shell),
  ].filter((button) => button instanceof HTMLButtonElement);
}

function lockBusyButton(button) {
  if (button.dataset.generationIntakeBusyManaged !== "true") {
    button.dataset.generationIntakeBusyPreviousDisabled = String(button.disabled);
    button.dataset.generationIntakeBusyPreviousAriaDisabled =
      button.getAttribute("aria-disabled") ?? "__missing__";
    button.dataset.generationIntakeBusyManaged = "true";
  }
  button.disabled = true;
  button.setAttribute("aria-disabled", "true");
}

function unlockBusyButton(button) {
  if (button.dataset.generationIntakeBusyManaged !== "true") return;
  button.disabled = button.dataset.generationIntakeBusyPreviousDisabled === "true";
  const previousAriaDisabled =
    button.dataset.generationIntakeBusyPreviousAriaDisabled;
  if (previousAriaDisabled === "__missing__") button.removeAttribute("aria-disabled");
  else button.setAttribute("aria-disabled", previousAriaDisabled || "false");
  delete button.dataset.generationIntakeBusyPreviousDisabled;
  delete button.dataset.generationIntakeBusyPreviousAriaDisabled;
  delete button.dataset.generationIntakeBusyManaged;
}

function syncRouteBusyUi(state) {
  if (!state?.shell) return;
  const busy = state.busy === true;
  const route = BRIEF_ROUTES.includes(state.busyRoute)
    ? state.busyRoute
    : state.route;
  qa("[data-generation-intake-panel]", state.shell).forEach((panel) => {
    const active = busy && panel.dataset.generationIntakePanel === route;
    if (active) panel.setAttribute("aria-busy", "true");
    else panel.removeAttribute("aria-busy");
  });
  if (busy) {
    state.shell.setAttribute("aria-busy", "true");
    state.shell.dataset.generationIntakeBusyRoute = route;
    routeBusyActionButtons(state, route, state.busyAction).forEach(lockBusyButton);
    return;
  }
  state.shell.removeAttribute("aria-busy");
  delete state.shell.dataset.generationIntakeBusyRoute;
  qa('[data-generation-intake-busy-managed="true"]', state.shell)
    .forEach(unlockBusyButton);
}

function reportRouteBusy(state, requestedRoute = state?.route) {
  if (!state) return false;
  syncRouteBusyUi(state);
  const runningRoute = BRIEF_ROUTES.includes(state.busyRoute)
    ? state.busyRoute
    : requestedRoute;
  const panel = panelFor(state, runningRoute) || panelFor(state, requestedRoute);
  if (panel) {
    setStatus(
      panel,
      "Операция уже выполняется. Дождитесь её завершения — повторный запуск заблокирован.",
      "busy",
    );
  }
  return false;
}

function beginRouteBusy(state, route, action, message) {
  if (!state) return false;
  if (state.busy) return reportRouteBusy(state, route);
  state.busy = true;
  state.busyRoute = route;
  state.busyAction = action;
  syncRouteBusyUi(state);
  const panel = panelFor(state, route);
  if (panel && message) setStatus(panel, message, "busy");
  return true;
}

function adoptRouteBusy(state, route = "copy_video", action = "generation-intake-prepare-copy") {
  if (!state) return false;
  state.busy = true;
  state.busyRoute = route;
  state.busyAction = action;
  syncRouteBusyUi(state);
  return true;
}

function finishRouteBusy(state) {
  if (!state) return;
  state.busy = false;
  state.busyRoute = "";
  state.busyAction = "";
  syncRouteBusyUi(state);
  if (state.route === "copy_video") syncExpressPriceButton(state);
}

function currentSourceUrl(panel) {
  return cleanText(q('[data-generation-intake-field="source_url"]', panel)?.value, 1_000);
}

function currentDescription(panel) {
  return cleanText(q('[data-generation-intake-field="description"]', panel)?.value, 1_200);
}

function currentAvatarWishes(panel) {
  return cleanText(q('[data-generation-intake-field="avatar_wishes"]', panel)?.value, 1_200);
}

function briefDatasetSnapshot(dataset, keys) {
  return Object.fromEntries(
    keys
      .filter((key) => dataset && Object.hasOwn(dataset, key))
      .map((key) => [key, String(dataset[key] || "")]),
  );
}

function restoreBriefDataset(dataset, keys, snapshot = {}) {
  if (!dataset) return;
  keys.forEach((key) => {
    if (Object.hasOwn(snapshot, key)) dataset[key] = String(snapshot[key] || "");
    else delete dataset[key];
  });
}

function blankBriefDraft() {
  return {
    value: "",
    controlDataset: {},
    formDataset: {},
  };
}

function readBriefDraft(form, brief) {
  if (!(brief instanceof HTMLTextAreaElement)) return blankBriefDraft();
  return {
    // Не trim и не slice: переключение маршрута не имеет права незаметно
    // переписать пользовательский черновик. Ограничения проверяются штатным
    // preflight каждого маршрута.
    value: String(brief.value || ""),
    controlDataset: briefDatasetSnapshot(
      brief.dataset,
      BRIEF_CONTROL_DATASET_KEYS,
    ),
    formDataset: briefDatasetSnapshot(
      form?.dataset,
      BRIEF_FORM_DATASET_KEYS,
    ),
  };
}

function cloneBriefDraft(draft) {
  return {
    value: String(draft?.value || ""),
    controlDataset: { ...(draft?.controlDataset || {}) },
    formDataset: { ...(draft?.formDataset || {}) },
  };
}

function cloneRouteBriefDrafts(drafts = {}) {
  return Object.fromEntries(BRIEF_ROUTES.map((route) => [
    route,
    cloneBriefDraft(drafts[route]),
  ]));
}

function routeBriefDraftMemoryKey() {
  return projectId() || "unscoped-project";
}

function declaredBriefRoute(form) {
  const route = String(
    form?.dataset?.generationIntakeV4Route
      || form?.elements?.generation_intake_route?.value
      || "",
  );
  return BRIEF_ROUTES.includes(route) ? route : "copy_video";
}

function initialRouteBriefDrafts(form, brief) {
  const key = routeBriefDraftMemoryKey();
  const saved = routeBriefDraftsMemory.get(key);
  if (saved) return cloneRouteBriefDrafts(saved);
  const drafts = cloneRouteBriefDrafts();
  const owner = declaredBriefRoute(form);
  drafts[owner] = readBriefDraft(form, brief);
  routeBriefDraftsMemory.set(key, cloneRouteBriefDrafts(drafts));
  return drafts;
}

function rememberRouteBriefDrafts(state) {
  if (!state?.briefDrafts) return;
  routeBriefDraftsMemory.set(
    state.briefDraftMemoryKey || routeBriefDraftMemoryKey(),
    cloneRouteBriefDrafts(state.briefDrafts),
  );
}

function captureBriefDraft(form, state, route = state?.briefRoute || state?.route) {
  if (!state || !BRIEF_ROUTES.includes(route)) return false;
  const brief = form?.elements?.brief;
  if (!(brief instanceof HTMLTextAreaElement)) return false;
  state.briefDrafts[route] = readBriefDraft(form, brief);
  state.briefRoute = route;
  rememberRouteBriefDrafts(state);
  return true;
}

function restoreBriefDraft(form, state, route) {
  if (!state || !BRIEF_ROUTES.includes(route)) return false;
  const brief = form?.elements?.brief;
  if (!(brief instanceof HTMLTextAreaElement)) return false;
  const draft = cloneBriefDraft(state.briefDrafts?.[route]);
  state.briefDrafts[route] = draft;
  brief.value = draft.value;
  restoreBriefDataset(
    brief.dataset,
    BRIEF_CONTROL_DATASET_KEYS,
    draft.controlDataset,
  );
  restoreBriefDataset(
    form.dataset,
    BRIEF_FORM_DATASET_KEYS,
    draft.formDataset,
  );
  // app.js keeps this exact mirror for spec fingerprints and draft recovery.
  // Update it without a synthetic input event: a route switch is not a human
  // edit and must not forge `researchRecommendationEdited` in the AI Centre.
  form.dataset.generationScenarioIntent = draft.value.trim().slice(0, 1_200);
  delete form.dataset.autoGenerationPreflightKey;
  state.briefRoute = route;
  return true;
}

function scheduleBriefDraftCapture(form, state) {
  queueMicrotask(() => {
    if (!formStates.has(form) || formStates.get(form) !== state) return;
    captureBriefDraft(form, state);
  });
}

function currentRecommendation(form) {
  return cleanText(form.elements?.brief?.value, 1_200);
}

function markBriefAsOperatorOwned(form, brief) {
  if (!form?.dataset || !brief?.dataset) return;
  delete brief.dataset.researchRecommendationApplied;
  delete brief.dataset.researchRecommendationField;
  delete brief.dataset.researchRecommendationEdited;
  brief.dataset.generationIntakeOperatorOwned = "true";
  const remainingAppliedFields = String(
    form.dataset.researchRecommendationAppliedFields || "",
  )
    .split(",")
    .map((field) => field.trim())
    .filter((field) => field && field !== "brief");
  if (remainingAppliedFields.length) {
    form.dataset.researchRecommendationAppliedFields = remainingAppliedFields.join(",");
  } else {
    delete form.dataset.researchRecommendationAppliedFields;
  }
}

function recommendationSource(form) {
  const brief = form.elements?.brief;
  const active = form.dataset.researchRecommendationLineage === "active";
  const verified = form.dataset.researchRecommendationVerificationState === "verified";
  const applied = Boolean(brief?.dataset?.researchRecommendationApplied);
  const edited = brief?.dataset?.researchRecommendationEdited === "true";
  const operatorOwned = brief?.dataset?.generationIntakeOperatorOwned === "true";
  if (operatorOwned && !applied) return currentRecommendation(form) ? "operator" : "empty";
  if (active && verified && applied) return edited ? "ai_center_edited" : "ai_center";
  if (active || applied) return "ai_center_unverified";
  return currentRecommendation(form) ? "operator" : "empty";
}

function currentRequestedModel(panel) {
  return cleanText(
    q('[data-generation-intake-field="model"]', panel)?.value,
    160,
  );
}

function currentAudio(panel) {
  // Чип «Звук» — единственный видимый переключатель звука; служебный селект
  // остаётся источником правды для цены и рецепта, поэтому ведём его следом.
  const chip = q('[data-generation-intake-preserve-code="audio"]', panel);
  const control = q('[data-generation-intake-field="audio"]', panel);
  if (chip instanceof HTMLInputElement && control instanceof HTMLSelectElement) {
    const wanted = chip.checked ? "true" : "false";
    if (control.value !== wanted) {
      control.value = wanted;
      control.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  const value = String(control?.value || "");
  return value === "true" ? true : value === "false" ? false : null;
}

function currentProductIdentity(form) {
  const sku = cleanText(form.elements?.sku?.value, 120);
  const productName = cleanText(form.elements?.product_name?.value, 180);
  return sku && productName ? { sku, product_name: productName } : null;
}

// Категория берётся из нативного поля, а если панель ещё не успела её туда
// перенести — из собственного селекта блока идентичности; в этом случае она
// переносится в форму здесь же, чтобы reportValidity() и ТЗ видели одно и то же.
function currentProductCategory(form, state) {
  const native = cleanText(form?.elements?.product_category?.value, 64);
  if (native) return native;
  const own = cleanText(identityInput(state, "product_category")?.value, 64);
  if (own) {
    syncIdentityToForm(form, "product_category", own);
    return cleanText(form?.elements?.product_category?.value, 64) || own;
  }
  return "";
}

function revealIdentityCategory(state) {
  const block = q("[data-generation-intake-identity]", state?.shell);
  if (block instanceof HTMLElement && block.hidden) block.hidden = false;
  const item = q(
    '[data-generation-intake-identity-item="product_category"]',
    state?.shell,
  );
  if (item instanceof HTMLElement && item.hidden) item.hidden = false;
}

function refreshModelSelects(form, state) {
  qa('[data-generation-intake-field="model"]', state.shell).forEach((select) => {
    const desired = [{
      value: "runway:product_swap",
      label: "Runway · Product Swap (серверный recipe)",
    }];
    const unchanged = select.options.length === desired.length
      && desired.every((item, index) => (
        select.options[index]?.value === item.value
        && select.options[index]?.text === item.label
      ));
    if (!unchanged) {
      select.replaceChildren(...desired.map(
        (item) => new Option(item.label, item.value),
      ));
    }
    select.value = desired[0].value;
    select.disabled = true;
    state.requestedModel = desired[0].value;
  });
}

function moveSharedBrief(form, state, route) {
  if (!(state.briefField instanceof HTMLElement) || !state.briefOrigin) return;
  if (route === "strategy_video") {
    // С 26.08 у «Создания» свой слот в панели (клон «Копии»): замысел живёт
    // там. Возврат в мастер остаётся запасным путём, если слот не найден.
    const strategySlot = q(
      '[data-generation-intake-brief-slot="strategy_video"]',
      state.shell,
    );
    if (strategySlot instanceof HTMLElement) {
      if (state.briefField.parentElement !== strategySlot) {
        strategySlot.append(state.briefField);
      }
      return;
    }
    if (state.briefField.previousSibling !== state.briefOrigin) {
      state.briefOrigin.after(state.briefField);
    }
    const label = q("#generation-brief-label", state.briefField);
    const hint = q("#generation-brief-hint", state.briefField);
    setNodeText(label, state.briefOriginal?.label || "Замысел нового ролика");
    setNodeText(hint, state.briefOriginal?.hint || "Опишите задачу для генерации.");
    if (state.briefControl instanceof HTMLTextAreaElement) {
      state.briefControl.placeholder = state.briefOriginal?.placeholder || "";
      if (
        Number.isInteger(state.briefOriginal?.maxLength)
        && state.briefOriginal.maxLength >= 0
      ) {
        state.briefControl.maxLength = state.briefOriginal.maxLength;
      }
    }
    return;
  }
  const slot = q(
    `[data-generation-intake-brief-slot="${CSS.escape(route)}"]`,
    state.shell,
  );
  if (slot && state.briefField.parentElement !== slot) slot.append(state.briefField);
}

function setNodeText(node, value) {
  if (node && node.textContent !== value) node.textContent = value;
}

function refreshRecommendationUi(form, state) {
  const route = state.route;
  // «Создание» держит замысел в шаге «Замысел» полного мастера — слота панели у
  // него нет, но бейдж происхождения рекомендации считается и для него.
  if (!DEFAULT_BRIEF_TEMPLATES[route] && route !== "strategy_video") return;
  moveSharedBrief(form, state, route);
  const brief = form.elements?.brief;
  if (!(brief instanceof HTMLTextAreaElement)) return;
  if (brief.dataset.researchRecommendationApplied) {
    delete brief.dataset.generationIntakeOperatorOwned;
  }
  const label = q("#generation-brief-label", state.briefField);
  const hint = q("#generation-brief-hint", state.briefField);
  // Три стратегии — три смысла одного поля: у «Копии» замысел говорит, что
  // сохранить и как заменить; у «Дуэта» это речь ведущего; у «Создания» —
  // концепция нового ролика. Рекомендация ИИ-центра собирается под каждый.
  const briefCopy = route === "copy_video"
    ? {
      label: "Что сохранить и как заменить товар",
      hint: "Это единый редактируемый замысел проекта. Рекомендация ИИ-центра (что сохранить из разобранных роликов, что не обещать) появляется здесь же и не перезаписывает ваши правки.",
      placeholder: "Напишите инструкцию своими словами или вставьте базовый шаблон ниже.",
    }
    : route === "avatar_video"
      ? {
        label: "Речь ведущего",
        hint: "Ведущий произнесёт этот текст вслух. Рекомендация ИИ-центра подставляет реплику из разбора; её можно переписать — предел по длине ролика показан под полем.",
        placeholder: "Что скажет ведущий — или вставьте реплику из рекомендации ниже.",
      }
      : {
        label: "Концепция нового ролика",
        hint: "Замысел нового ролика по механике референсов. Рекомендация ИИ-центра (хук, сообщение, кадры, CTA) появляется здесь же и не перезаписывает ваши правки.",
        placeholder: "Опишите, каким должен быть новый ролик, или примените рекомендацию ИИ-центра.",
      };
  if (label) setNodeText(label, briefCopy.label);
  if (hint) setNodeText(hint, briefCopy.hint);
  brief.placeholder = briefCopy.placeholder;
  brief.maxLength = BRIEF_LIMIT;
  const value = String(brief.value || "");
  const source = recommendationSource(form);
  const isUneditedBaseTemplate = source === "operator"
    && value === DEFAULT_BRIEF_TEMPLATES[route];
  const badge = q(
    `[data-generation-intake-recommendation="${CSS.escape(route)}"] [data-generation-intake-recommendation-source]`,
    state.shell,
  );
  if (badge) {
    badge.dataset.source = source;
    setNodeText(badge, source === "ai_center"
      ? "Из ИИ‑центра"
      : source === "ai_center_edited"
        ? "ИИ‑центр + ваша правка"
        : source === "ai_center_unverified"
          ? "ИИ‑черновик требует проверки"
          : isUneditedBaseTemplate
            ? "Базовый шаблон · проверьте"
            : value
              ? "Ваш текст"
              : "Базовый шаблон");
  }
  const fallback = q(
    `[data-generation-intake-recommendation-fallback="${CSS.escape(route)}"]`,
    state.shell,
  );
  if (fallback) fallback.hidden = Boolean(value);
  const meta = q(
    `[data-generation-intake-brief-meta="${CSS.escape(route)}"]`,
    state.shell,
  );
  if (meta) {
    // У «Дуэта» текст — речь ведущего, и сервер принимает её только если она
    // укладывается в ролик: ≈15 знаков на секунду, не больше 1500
    // (generation_strategy_prompt_snapshot). Предел показывается здесь же,
    // а не всплывает отказом после загрузки.
    const speech = route === "avatar_video" ? duetSpeechLimit(state) : null;
    const limit = speech?.limit || BRIEF_LIMIT;
    const over = value.length > limit;
    meta.dataset.state = over ? "error" : "neutral";
    setNodeText(meta, over
      ? `${value.length} / ${limit} · текст не обрезан: сократите его${speech ? ` — ролик ${speech.seconds} с вмещает около ${limit} знаков речи` : " перед preflight"}${
        value.includes(String.fromCharCode(10)) && speech
          ? ". В поле несколько строк — ведущий произнесёт ВСЁ подряд; оставьте одну реплику"
          : ""
      }`
      : speech
        ? `${value.length} / ${limit} · ролик ${speech.seconds} с вмещает около ${limit} знаков речи`
        : `${value.length} / ${BRIEF_LIMIT}`);
  }
}

function syncAvatarMode(panel) {
  const active = avatarInputMode(panel);
  qa("[data-generation-intake-avatar-mode-panel]", panel).forEach((node) => {
    const selected = node.dataset.generationIntakeAvatarModePanel === active;
    node.hidden = !selected;
    qa("input, select, textarea", node).forEach((control) => {
      control.disabled = !selected;
    });
  });
}

function setPanelControlsActive(panel, active) {
  qa("input, select, textarea", panel)
    .filter((control) => control.name !== "media_id")
    .forEach((control) => {
      if (control.hasAttribute("data-generation-intake-server-owned")) {
        control.disabled = true;
      } else {
        control.disabled = !active;
      }
    });
  if (active && panel.dataset.generationIntakePanel === "avatar_video") {
    syncAvatarMode(panel);
  }
}

function clearSpendConfirmation(form, { notify = true } = {}) {
  const confirmation = form.elements?.real_spend_confirmation;
  if (!(confirmation instanceof HTMLInputElement)) return;
  const changed = confirmation.checked || Boolean(confirmation.value);
  confirmation.checked = false;
  confirmation.value = "";
  if (changed && notify) {
    confirmation.dispatchEvent(new Event("input", { bubbles: true }));
    confirmation.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

function applyCompactPreferences(form, handoff) {
  const audio = form.elements?.generation_strategy_audio;
  if (audio instanceof HTMLSelectElement && typeof handoff.audio === "boolean") {
    audio.value = String(handoff.audio);
    audio.dispatchEvent(new Event("input", { bubbles: true }));
    audio.dispatchEvent(new Event("change", { bubbles: true }));
  }
  applyAutoOutputDefaults(form);
  // requested_model is advisory metadata only. Product Swap's provider/recipe
  // remains server-owned and must never be switched through the generic model UI.
}

// Формат выбирается автоматически: вертикаль 9:16 для ratio-стратегий и первое
// доступное серверное разрешение для Product Swap. Серверные правила не
// подменяются — значения берутся только из вариантов, которые дал каталог.
function applyAutoOutputDefaults(form) {
  const resolution = form.elements?.generation_strategy_resolution;
  if (
    resolution instanceof HTMLSelectElement
    && !resolution.disabled
    && !resolution.value
  ) {
    const first = [...resolution.options].find((option) => option.value);
    if (first) {
      resolution.value = first.value;
      resolution.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  const ratio = form.elements?.generation_strategy_ratio;
  if (ratio instanceof HTMLSelectElement && !ratio.disabled && !ratio.value) {
    const vertical = [...ratio.options].find(
      (option) => option.value === "720:1280" || option.value === "1080:1920",
    ) || [...ratio.options].find((option) => option.value);
    if (vertical) {
      ratio.value = vertical.value;
      ratio.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
}

function wizardAttestationInput(form, attestationId) {
  return q(
    `#generation-strategy-assets input[data-generation-strategy-attestation="${CSS.escape(attestationId)}"]`,
    form,
  );
}

// Одна галка прав ставит все четыре настоящих подтверждения мастера через их
// обычные change-события. Fail-closed: возвращается список подтверждений,
// которые не удалось поставить, — их придётся отметить вручную.
function applyConsolidatedRights(form, panel) {
  const consolidated = q("[data-generation-intake-rights]", panel);
  // У «Дуэта» к четырём подтверждениям «Копии» добавляется согласие на
  // внешность ведущего: единая галка панели покрывает и его.
  const attestationIds = panel?.dataset?.generationIntakePanel === "avatar_video"
    ? [...COPY_ATTESTATION_IDS, "avatar_likeness_consent_confirmed"]
    : [...COPY_ATTESTATION_IDS];
  if (!(consolidated instanceof HTMLInputElement) || !consolidated.checked) {
    return attestationIds;
  }
  const missing = [];
  attestationIds.forEach((attestationId) => {
    const input = wizardAttestationInput(form, attestationId);
    if (!(input instanceof HTMLInputElement) || input.disabled) {
      missing.push(attestationId);
      return;
    }
    if (!input.checked) {
      input.checked = true;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (input.checked !== true) missing.push(attestationId);
  });
  return missing;
}

function approvePendingSpecVersions(form) {
  qa('input[name="generation_strategy_spec_approval"]', form).forEach((input) => {
    if (input instanceof HTMLInputElement && !input.checked && !input.disabled) {
      input.click();
    }
  });
}

function normalizedCampaignId(value) {
  const id = String(value || "").trim().toLowerCase();
  return UUID_PATTERN.test(id) ? id : "";
}

function availableCampaignOptions(form) {
  const campaign = form?.elements?.campaign_id;
  const options = campaign instanceof HTMLSelectElement
    ? [...campaign.options].filter((option) => (
      Boolean(normalizedCampaignId(option.value)) && !option.disabled
    ))
    : [];
  return { campaign, options };
}

// `campaign_explicit` distinguishes a human choice from a safe initial
// default.  If an explicit campaign disappears or is disabled, falling back
// to another valid budget would silently charge the wrong campaign; that case
// must remain unresolved until the person chooses again.  A fallback is only
// allowed when there has never been a human campaign choice.
function resolveExpressCampaign(form) {
  const { campaign, options } = availableCampaignOptions(form);
  const saved = expressDefaultsMemory.get(projectId()) || {};
  const explicit = saved.campaign_explicit === true;
  const savedId = normalizedCampaignId(saved.campaign_id);
  const currentId = normalizedCampaignId(campaign?.value);
  const optionById = new Map(options.map((option) => [
    normalizedCampaignId(option.value),
    option,
  ]));
  let target = null;
  if (explicit) {
    target = optionById.get(savedId) || null;
  } else {
    target = optionById.get(savedId)
      || optionById.get(currentId)
      || options[options.length - 1]
      || null;
  }
  return {
    campaign,
    options,
    id: normalizedCampaignId(target?.value),
    explicit,
    invalidExplicit: explicit && !target,
  };
}

function rememberExpressCampaign(id, { explicit }) {
  const key = projectId();
  const previous = expressDefaultsMemory.get(key) || {};
  expressDefaultsMemory.set(key, {
    ...previous,
    campaign_id: normalizedCampaignId(id),
    campaign_explicit: explicit === true,
  });
}

function setCampaignNote(panel, resolution) {
  const note = q("[data-generation-intake-campaign-note]", panel);
  const message = q("[data-generation-intake-campaign-note-text]", panel);
  if (message) {
    setNodeText(
      message,
      resolution.invalidExplicit
        ? "Выбранная кампания стала недоступна. Выберите другую активную кампанию выше или "
        : "В проекте нет активной кампании, поэтому платный запуск честно невозможен. ",
    );
  }
  if (note instanceof HTMLElement) {
    note.hidden = Boolean(resolution.id) || (
      !resolution.invalidExplicit && resolution.options.length > 0
    );
  }
}

// Rebuild the visible compact mirror from the native campaign catalog.  The
// native `campaign_id` remains the only field submitted to app.js; the mirror
// merely lets the person make that exact choice before price/preflight.
function syncCompactCampaignControl(form, state, route = null) {
  const panel = state
    ? panelFor(state, route || expressRoute(state))
    : null;
  const mirror = panel
    ? q("[data-generation-intake-campaign-select]", panel)
    : null;
  const hint = panel
    ? q("[data-generation-intake-campaign-hint]", panel)
    : null;
  const resolution = resolveExpressCampaign(form);
  if (resolution.campaign instanceof HTMLSelectElement) {
    // Restoring the same human choice after a render is not a change and stays
    // event-free — that was the original intent here. But when the resolver
    // lands on a DIFFERENT campaign (the previous one became unavailable and the
    // selection falls back to empty), the paid context really did change, and
    // the spend confirmation has to see it. assignPaidContextValue keeps both:
    // silent on restore, loud on an actual change.
    assignPaidContextValue(resolution.campaign, resolution.id);
  }
  setCampaignNote(panel, resolution);
  if (!(mirror instanceof HTMLSelectElement)) return resolution;

  const options = [];
  if (!resolution.options.length) {
    options.push(new Option("Нет активной кампании", ""));
  } else if (resolution.invalidExplicit) {
    options.push(new Option(
      "Ранее выбранная кампания недоступна — выберите другую",
      "",
    ));
  }
  resolution.options.forEach((option) => {
    options.push(new Option(
      cleanText(option.textContent || option.text || "Кампания", 180),
      normalizedCampaignId(option.value),
    ));
  });
  // This function is called from mount(), while the intake observer watches
  // childList mutations across the whole document. Replacing identical option
  // nodes on every mount would therefore schedule another mount forever and
  // eventually crash the browser renderer. Reconcile only when the catalogue
  // really changed; keeping the current nodes also preserves the live choice.
  const optionsUnchanged = mirror.options.length === options.length
    && options.every((option, index) => {
      const current = mirror.options[index];
      return current?.value === option.value
        && String(current?.textContent || current?.text || "") === option.text
        && current?.disabled === option.disabled;
    });
  if (!optionsUnchanged) mirror.replaceChildren(...options);
  mirror.value = resolution.id;
  mirror.disabled = !resolution.options.length
    || expressPaidAuthorityLocked(form);
  mirror.dataset.selectionState = resolution.invalidExplicit
    ? "invalid"
    : resolution.explicit
      ? "explicit"
      : "default";
  if (hint) {
    setNodeText(
      hint,
      resolution.invalidExplicit
        ? "Выбранная кампания больше не активна. Цена, токен и подтверждение списания недействительны — выберите другую кампанию."
        : resolution.id
          ? "Именно эта кампания будет сверена ещё раз перед платным запуском. Её смена потребует новой бесплатной цены."
          : "Создайте или включите кампанию. Бесплатную подготовку можно продолжить, но платный запуск останется заблокирован.",
    );
  }
  if (
    state?.express?.phase === "priced"
    && state.express.campaign_id !== resolution.id
  ) {
    invalidateExpressPriceForCommittedInput(form, state, mirror);
  }
  return resolution;
}

function commitCompactCampaignSelection(form, state, mirror) {
  if (!(mirror instanceof HTMLSelectElement)) return "";
  const requestedId = normalizedCampaignId(mirror.value);
  const { campaign, options } = availableCampaignOptions(form);
  const accepted = options.some(
    (option) => normalizedCampaignId(option.value) === requestedId,
  ) ? requestedId : "";
  // Even a malformed/now-stale choice is remembered as explicit-empty: this
  // prevents a concurrent render from substituting a different valid budget.
  rememberExpressCampaign(accepted, { explicit: true });
  invalidateExpressPriceForCommittedInput(form, state, mirror);
  if (campaign instanceof HTMLSelectElement) {
    const changed = campaign.value !== accepted;
    campaign.value = accepted;
    if (changed) {
      campaign.dataset.generationIntakeCampaignMirrorSync = "true";
      campaign.dispatchEvent(new Event("input", { bubbles: true }));
      campaign.dispatchEvent(new Event("change", { bubbles: true }));
      delete campaign.dataset.generationIntakeCampaignMirrorSync;
    }
  }
  syncCompactCampaignControl(form, state);
  return accepted;
}

// Resolve the exact live choice. An explicit invalid choice fails closed;
// only a never-chosen/default context may adopt a valid fallback.
function autoSelectCampaign(form, panel, state = null) {
  const resolution = syncCompactCampaignControl(form, state);
  setCampaignNote(panel, resolution);
  if (!resolution.id) return "";
  if (!resolution.explicit) {
    rememberExpressCampaign(resolution.id, { explicit: false });
  }
  return resolution.id;
}

function expressCampaignMatchesPrice(form, express, campaignId) {
  const campaign = form?.elements?.campaign_id;
  return campaign instanceof HTMLSelectElement
    && !campaign.disabled
    && Boolean(campaignId)
    && normalizedCampaignId(campaign.value) === campaignId
    && normalizedCampaignId(express?.campaign_id) === campaignId;
}

function serverPriceLabel(form) {
  const text = String(q("#real-generation-price", form)?.textContent || "");
  const match = text.match(/\$\s?\d[\d\s.,]*/u);
  return match ? match[0].replace(/\s+/gu, "").replace(/[.,]$/u, "") : "";
}

function waitMs(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

// Мастер живёт в разметке, которую app.js перерисовывает целиком: узлы
// #mock-batch-form и #generation-submit заменяются новыми объектами. Ссылку на
// них нельзя брать один раз и держать весь цикл — отсоединённая кнопка молча
// принимает click() и не отправляет форму. Живые узлы берутся заново на каждом
// опросе.
function liveGenerationForm(form) {
  const live = document.querySelector("#mock-batch-form");
  return live instanceof HTMLFormElement ? live : form;
}

// Любой await внутри handoff/preflight может совпасть с patch-render app.js.
// В таком случае старые form/state/panel остаются валидными JS-объектами, но
// уже не управляют видимой кнопкой. Контекст принимается только от живой формы;
// fallback разрешён лишь пока объект формы действительно тот же самый.
function liveCopyLaunchContext(
  initialForm,
  fallbackState = null,
  fallbackPanel = null,
  {
    busy = false,
    busyRoute = null,
    busyAction = null,
    route: explicitRoute = null,
  } = {},
) {
  const form = liveGenerationForm(initialForm);
  if (!formStates.has(form)) mount(form);
  const state = formStates.get(form)
    || (form === initialForm ? fallbackState : null);
  const route = explicitRoute || expressRoute(state || fallbackState);
  const panel = state
    ? panelFor(state, route)
    : form === initialForm
    ? fallbackPanel
    : null;
  if (busy && state) {
    adoptRouteBusy(
      state,
      busyRoute || route,
      busyAction || expressPrepareAction(route),
    );
  }
  return { form, state, panel };
}

// Отпечаток видимого состояния мастера. Пока он меняется, бесплатная проверка
// движется; замерший отпечаток при нажатой кнопке означает, что клики уходят
// в никуда.
function preflightSignature(form, submitButton) {
  return [
    form.dataset.generationStrategyConfirmationReady || "",
    form.dataset.busy || "",
    submitButton.dataset.launchPhase || "",
    submitButton.dataset.launchBlocker || "",
    submitButton.disabled ? "off" : "on",
    cleanText(submitButton.textContent, 120),
  ].join("|");
}

// «Показать цену» гоняет действующий мастер по его же бесплатным фазам:
// точное ТЗ → одобрение версии → бесплатный preflight с серверной ценой.
// Провайдер не вызывается, деньги не списываются; платный старт остаётся за
// отдельным человеческим кликом.
// Человеческие имена невалидных полей формы: когда мастер молчит из-за
// reportValidity(), человек должен прочитать, КАКОЕ поле держит форму, а не
// «обновите страницу». Имя берётся из label поля; для служебных полей — словарь.
const INVALID_FIELD_LABELS = Object.freeze({
  campaign_id: "Кампания (карточка «Кампания и бюджет»)",
  brief: "Замысел/речь",
  generation_strategy_audio: "Звук результата",
  product_category: "Категория товара",
  destination_ref: "Направление публикации",
});

function invalidControlSummary(form) {
  try {
    const names = [];
    for (const control of form.elements) {
      if (typeof control.checkValidity !== "function" || control.checkValidity()) continue;
      const name = String(control.name || control.id || "");
      let label = INVALID_FIELD_LABELS[name] || "";
      if (!label && control.id) {
        label = cleanText(
          form.querySelector(`label[for="${CSS.escape(control.id)}"]`)?.textContent,
          60,
        );
      }
      if (!label) {
        label = cleanText(
          control.closest("label, .field")?.querySelector("span, strong")?.textContent,
          60,
        );
      }
      names.push(label || name || control.tagName.toLowerCase());
      if (names.length >= 3) break;
    }
    return [...new Set(names)];
  } catch {
    return [];
  }
}

async function driveStrategyPreflight(initialForm, panel, options = {}) {
  const {
    freePhases = EXPRESS_FREE_SUBMIT_PHASES,
    requireSourceDuration = true,
    strategyId = null,
    routeKey = null,
    busyAction = null,
  } = options;
  const startedAt = Date.now();
  const deadline = startedAt + EXPRESS_PREFLIGHT_TIMEOUT_MS;
  let blockedPolls = 0;
  let stalledPolls = 0;
  let attestationRenderPolls = 0;
  let durationControlPolls = 0;
  let lastSignature = "";
  let lastReportedStep = "";
  while (Date.now() < deadline) {
    // Preflight сам перерисовывает guided-мастер. Каждая новая compact-shell
    // сразу наследует busy=true: второй клик «Подготовить ролик» не может
    // запустить параллельную подготовку на новом state.
    const context = liveCopyLaunchContext(
      initialForm,
      null,
      panel,
      { busy: true, route: routeKey, busyRoute: routeKey, busyAction },
    );
    const { form } = context;
    if (!context.state || !context.panel) {
      throw new Error("express_live_context_missing");
    }
    const submitButton = q("#generation-submit", form);
    if (!(submitButton instanceof HTMLButtonElement)) {
      throw new Error("express_submit_missing");
    }
    // Отказ сервера на одном из бесплатных шагов мастер записывает на форму.
    // Повторять нажатие бессмысленно — причина названа, и её надо показать.
    const failureAt = Number(form.dataset.generationStrategyLastFailureAt || 0);
    const failureText = String(form.dataset.generationStrategyLastFailure || "");
    if (failureAt >= startedAt && failureText) {
      const rejected = new Error("express_preflight_rejected");
      rejected.serverMessage = failureText;
      rejected.step = cleanText(submitButton.textContent, 120);
      throw rejected;
    }
    // У свежего локального MP4 handoff ещё не знает серверную длительность:
    // она появляется только после бесплатной probe-кнопки ниже. Как только
    // guided вернул этот факт, заменяем catalog default ДО любой spec/preflight
    // кнопки и ждём новый render. Цена за 10 с никогда не может пережить
    // серверно подтверждённый исходник длиной 5 с.
    const sourceDuration = requireSourceDuration
      ? verifiedSourceDurationSeconds(form)
      : null;
    // Native setFormBusy временно disabled все контролы, включая уже принятые
    // 5 секунд. Busy — это ожидание текущей бесплатной операции, а не отказ
    // длительности; до любых disabled/readiness выводов ждём её завершения.
    if (form.dataset.busy === "true") {
      blockedPolls = 0;
      stalledPolls = 0;
      await waitMs(EXPRESS_POLL_INTERVAL_MS);
      continue;
    }
    if (sourceDuration !== null) {
      const durationControl = wizardDurationControl(form);
      // input/change может синхронно patch-render'ить форму. Точный value на
      // временно disabled контроле уже является корректным состоянием: disabled
      // здесь означает native busy, а не отказ принять длительность. Если же
      // нового контрола ещё нет или его value пока старый и он заблокирован,
      // ждём bounded число опросов вместо ошибки по detached DOM.
      const durationMatches = durationControl?.value === String(sourceDuration);
      if (!durationControl || (!durationMatches && durationControl.disabled)) {
        durationControlPolls += 1;
        if (durationControlPolls >= EXPRESS_BLOCKED_POLL_LIMIT) {
          throw new Error("express_source_duration_unavailable");
        }
        await waitMs(EXPRESS_POLL_INTERVAL_MS);
        continue;
      }
      durationControlPolls = 0;
      if (!durationMatches) {
        const window = wizardDurationWindow(form);
        if (sourceDuration < window.min || sourceDuration > window.max) {
          throw new Error("express_source_duration_incompatible");
        }
        applyCopyDuration(form, sourceDuration);
        setStatus(
          context.panel,
          `Сервер измерил исходник: ${sourceDuration} с. Пересчитываем ТЗ и цену именно для этой длительности…`,
          "busy",
        );
        await waitMs(EXPRESS_POLL_INTERVAL_MS);
        continue;
      }
    }
    if (form.dataset.generationStrategyConfirmationReady === "true") {
      if (requireSourceDuration && sourceDuration === null) {
        // Даже если stale DOM сохранил readiness от прежнего ролика, платная
        // цена без длительности exact выбранного MP4 не принимается.
        throw new Error("express_source_duration_unverified");
      }
      return serverPriceLabel(form);
    }
    const signature = preflightSignature(form, submitButton);
    if (signature !== lastSignature) {
      stalledPolls = 0;
      lastSignature = signature;
    }
    const rightsPanel = context.panel;
    const missingAttestations = applyConsolidatedRights(form, rightsPanel);
    if (missingAttestations.length) {
      attestationRenderPolls += 1;
      if (attestationRenderPolls < EXPRESS_ATTESTATION_RENDER_POLL_LIMIT) {
        // Каталог мог завершить загрузку уже после openNativeLaunch. Повторно
        // нажимаем только безопасный SELECT стратегии; платный submit здесь не
        // трогаем. Как только guided создаст реальные четыре checkbox, обычный
        // applyConsolidatedRights поставит их через change-события.
        selectStrategy(
          form,
          strategyId || ROUTE_AUTHORITY_STRATEGY[expressRoute(context.state)],
        );
        setStatus(
          rightsPanel,
          "Подключаем нативные подтверждения прав… Провайдер не запускается и деньги не списываются.",
          "busy",
        );
        await waitMs(EXPRESS_POLL_INTERVAL_MS);
        continue;
      }
      const failure = new Error("express_attestations_unavailable");
      failure.missingAttestations = missingAttestations;
      throw failure;
    }
    attestationRenderPolls = 0;
    approvePendingSpecVersions(form);
    applyAutoOutputDefaults(form);
    const probe = q('[data-action="probe-generation-strategy-media"]', form);
    const phase = String(submitButton.dataset.launchPhase || "");
    // Человек видит шаг, на котором мастер сейчас находится: молчаливого
    // ожидания без единой строки на экране больше нет.
    const step = cleanText(submitButton.textContent, 120);
    if (step && step !== lastReportedStep) {
      lastReportedStep = step;
      setStatus(
        rightsPanel,
        `Бесплатная проверка идёт: «${step}». Провайдер не запускается и деньги не списываются…`,
        "busy",
      );
    }
    if (probe instanceof HTMLButtonElement && !probe.hidden && !probe.disabled) {
      blockedPolls = 0;
      stalledPolls += 1;
      if (stalledPolls >= EXPRESS_STALLED_POLL_LIMIT) {
        const failure = new Error("express_preflight_stalled");
        failure.step = step;
        failure.invalidFields = invalidControlSummary(form);
        throw failure;
      }
      probe.click();
      await waitMs(EXPRESS_POLL_INTERVAL_MS);
    } else if (
      !submitButton.disabled
      && freePhases.includes(phase)
    ) {
      blockedPolls = 0;
      stalledPolls += 1;
      if (stalledPolls >= EXPRESS_STALLED_POLL_LIMIT) {
        const failure = new Error("express_preflight_stalled");
        failure.step = step;
        failure.invalidFields = invalidControlSummary(form);
        throw failure;
      }
      submitButton.click();
      await waitMs(EXPRESS_POLL_INTERVAL_MS);
    } else if (submitButton.disabled && submitButton.dataset.launchBlocker) {
      blockedPolls += 1;
      if (blockedPolls >= EXPRESS_BLOCKED_POLL_LIMIT) {
        const failure = new Error("express_preflight_blocked");
        failure.blocker = cleanText(submitButton.dataset.launchBlocker, 300);
        throw failure;
      }
    } else {
      // Кнопка не нажимается и причины не называет: это тоже отказ, и он
      // обязан стать видимым, а не растянуться до таймаута.
      stalledPolls += 1;
      if (stalledPolls >= EXPRESS_STALLED_POLL_LIMIT) {
        const failure = new Error("express_preflight_stalled");
        failure.step = step;
        failure.invalidFields = invalidControlSummary(form);
        throw failure;
      }
    }
    await waitMs(EXPRESS_POLL_INTERVAL_MS);
  }
  throw new Error("express_preflight_timeout");
}

// Экспресс-путь («Подготовить» → бесплатные шаги мастера → «Запустить за $X»)
// с 23.08.2026 общий для «Копии» и «Дуэта»: у обоих один исходник и один
// результат, и оба ведут нативный мастер из своей панели. Маршрут берётся из
// активной панели, а не из литерала «Копии».
const EXPRESS_ROUTES = Object.freeze(["copy_video", "avatar_video"]);

function expressRoute(state) {
  return state?.route === "avatar_video" ? "avatar_video" : "copy_video";
}

function expressPrepareAction(route) {
  return route === "avatar_video"
    ? "generation-intake-prepare-avatar"
    : "generation-intake-prepare-copy";
}

function expressIdleLabel(route) {
  return route === "avatar_video" ? "Подготовить дуэт" : "Подготовить ролик";
}

function priceButtonFor(panel) {
  return q(
    '[data-action="generation-intake-prepare-copy"], [data-action="generation-intake-prepare-avatar"]',
    panel,
  );
}

function expressPaidAuthorityLocked(form) {
  if (!form) return false;
  if (form?.dataset?.generationStrategyPaidLocked === "true") return true;
  const nativeSubmit = q("#generation-submit", form);
  return nativeSubmit?.dataset?.launchPhase ===
    "strategy_product_swap_paid_locked";
}

// Двухфазная кнопка: «Показать цену» после бесплатного preflight превращается
// в «Запустить за $X». Платный старт происходит только по этому явному клику.
function syncExpressPriceButton(state) {
  const activeRoute = expressRoute(state);
  EXPRESS_ROUTES.forEach((route) => {
    syncExpressPriceButtonFor(state, route, route === activeRoute);
  });
}

function syncExpressPriceButtonFor(state, route, active) {
  const panel = panelFor(state, route);
  const button = panel ? priceButtonFor(panel) : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const form = state.shell?.closest?.("form");
  const paidAuthorityLocked = expressPaidAuthorityLocked(form);
  if (paidAuthorityLocked) {
    if (button.dataset.expressPaidAuthorityLocked !== "true") {
      button.dataset.expressDisabledBeforePaidLock = String(button.disabled);
    }
    button.dataset.expressPaidAuthorityLocked = "true";
    button.dataset.expressPhase = "locked";
    button.disabled = true;
    button.title = "Одноразовая квитанция уже зарезервирована или использована. Создайте новый контекст и заново пройдите бесплатную проверку цены.";
    state.express = {
      ...state.express,
      phase: "idle",
      price: "",
      spend_confirmation: "",
      campaign_id: "",
    };
    setNodeText(button, "Этот запуск уже использован");
    return;
  }
  if (button.dataset.expressPaidAuthorityLocked === "true") {
    button.disabled = button.dataset.expressDisabledBeforePaidLock === "true";
    delete button.dataset.expressPaidAuthorityLocked;
    delete button.dataset.expressDisabledBeforePaidLock;
    button.title = "";
  }
  // Цена принадлежит активной панели: кнопка неактивного маршрута всегда
  // в исходном состоянии, иначе «Дуэт» показал бы цену «Копии».
  const priced = active && state.express?.phase === "priced" && state.express.price;
  button.dataset.expressPhase = priced ? "priced" : "idle";
  // Replacement-shell starts with the prepare action disabled. Once the exact
  // server price is present, finishing the busy phase must restore the explicit
  // human launch click instead of leaving a silent, permanently disabled CTA.
  if (priced && !state.busy) button.disabled = false;
  setNodeText(
    button,
    priced ? `Запустить за ${state.express.price}` : expressIdleLabel(route),
  );
}

function setExpressPricePhase(
  state,
  price,
  spendConfirmation,
  campaignId = "",
) {
  state.express = {
    ...state.express,
    phase: price ? "priced" : "idle",
    price: price || "",
    spend_confirmation: price ? String(spendConfirmation || "") : "",
    campaign_id: price
      ? String(campaignId || "").trim().toLowerCase()
      : "",
  };
  syncExpressPriceButton(state);
}

function resetExpressPrice(state) {
  if (state.express?.phase !== "priced") return;
  setExpressPricePhase(state, "", "");
}

function resetExpressAuthorityForStrategyRepeat(form, state) {
  setExpressPricePhase(state, "", "");
  clearSpendConfirmation(form, { notify: false });
  return syncCompactCampaignControl(form, state);
}

function resetExpressPriceStatus(form, state) {
  const panel = panelFor(state, expressRoute(state));
  const status = panel ? q("[data-generation-intake-status]", panel) : null;
  const result = String(status?.dataset?.expressPriceResult || "");
  if (!result || status?.dataset?.state === "error") return false;
  const campaignMissing = result === "campaign_missing"
    && !String(form?.elements?.campaign_id?.value || "").trim();
  setStatus(
    panel,
    campaignMissing
      ? "Параметры изменились, поэтому предыдущая цена больше не действует. Нажмите «Подготовить ролик» для новой бесплатной проверки. Для запуска по-прежнему нужна активная кампания."
      : "Параметры изменились, поэтому предыдущая цена больше не действует. Нажмите «Подготовить ролик», чтобы бесплатно получить новую точную цену.",
    campaignMissing ? "warning" : "neutral",
  );
  return true;
}

// Любое изменение exact paid-контекста делает прежнюю цену чужой. Compact
// controls живут в своей sibling shell, native strategy/campaign controls — в
// остальной форме; обе области перечислены намеренно. Чекбокс свежего
// real_spend_confirmation исключён: он подтверждает уже рассчитанную цену, а
// не меняет её контекст.
function expressPaidContextInput(form, state, target) {
  if (!target || target.name === "real_spend_confirmation") return false;
  const panel = panelFor(state, "copy_video");
  if (
    panel?.contains?.(target)
    && target.matches?.("input, select, textarea")
  ) return true;
  const name = String(target.name || "");
  return name === "campaign_id"
    || name === "media_id"
    || name === "primary_media_id"
    || name === "brief"
    || name === "sku"
    || name === "product_name"
    || name === "product_category"
    || name === "platform"
    || name === "destination_ref"
    || name === "generation_mode"
    || name === "generation_intake_engine"
    || ["generator", "quality", "duration"].some(
      (part) => name === `generation_intake_${part}`,
    )
    || name.startsWith("generation_strategy_");
}

function invalidateExpressPriceForCommittedInput(form, state, target) {
  if (!expressPaidContextInput(form, state, target)) return false;
  const confirmation = form?.elements?.real_spend_confirmation;
  const stale = state.express?.phase === "priced"
    || Boolean(state.express?.price)
    || Boolean(state.express?.spend_confirmation)
    || Boolean(confirmation?.checked)
    || Boolean(confirmation?.value);
  if (stale) {
    // Clear the compact authorization first so a synchronous native re-render
    // cannot carry the old CTA forward, then remove its paired form token.
    setExpressPricePhase(state, "", "");
    // This runs inside the committed context event. Dispatching a nested
    // confirmation event here could patch-render the form before the original
    // engine/media/prompt event reaches the app; the original event will do the
    // authoritative readiness invalidation itself.
    clearSpendConfirmation(form, { notify: false });
  }
  const statusReset = resetExpressPriceStatus(form, state);
  return stale || statusReset;
}

function rememberExpressDefaults(state) {
  const panel = panelFor(state, "copy_video");
  if (!panel) return;
  const key = projectId();
  const previous = expressDefaultsMemory.get(key) || {};
  const liveCampaignId = normalizedCampaignId(
    state.shell?.closest?.("form")?.elements?.campaign_id?.value,
  );
  expressDefaultsMemory.set(key, {
    audio: String(q('[data-generation-intake-field="audio"]', panel)?.value || ""),
    sku: String(identityInput(state, "sku")?.value || ""),
    product_name: String(identityInput(state, "product_name")?.value || ""),
    product_category: String(identityInput(state, "product_category")?.value || ""),
    rights: q('[data-generation-intake-rights="copy_video"]', panel)?.checked === true,
    engine: String(
      state.copyEngine?.modelId
      || state.shell?.closest?.("form")?.elements?.generation_intake_engine?.value
      || "",
    ),
    quality: String(state.copyEngine?.qualityCode || ""),
    // Unrelated edits must not replace an explicit-but-temporarily-unavailable
    // campaign with the native form's freshly rendered default.
    campaign_id: previous.campaign_explicit === true
      ? normalizedCampaignId(previous.campaign_id)
      : liveCampaignId,
    campaign_explicit: previous.campaign_explicit === true,
  });
}

// `input` испускается сразу после фактического переключения checkbox/radio и
// раньше `change`. app.js может patch-render'ить форму между этими событиями;
// поэтому именно здесь фиксируется уже совершённый человеческий выбор. Это не
// ставит согласие само: pointerdown/click без checked input сюда не попадает.
function captureExpressCommittedInput(form, state, target) {
  const patch = {};
  const rights = target?.closest?.('[data-generation-intake-rights="copy_video"]');
  if (rights instanceof HTMLInputElement) patch.rights = rights.checked === true;
  const engine = target?.closest?.(
    '[data-generation-intake-choice-block="model"] input[type="radio"]',
  );
  const engineInStrategyPanel = Boolean(
    engine?.closest?.('[data-generation-intake-panel="strategy_video"]'),
  );
  if (engine instanceof HTMLInputElement && engine.checked && !engineInStrategyPanel) {
    patch.engine = String(engine.value || "");
    patch.quality = "";
    state.copyEngine = {
      ...(state.copyEngine || {}),
      modelId: patch.engine,
      qualityCode: "",
      durationNotice: "",
      // Человек выбрал сам: совет ИИ-центра больше не перекрывает этот выбор,
      // пока человек не выберет снова.
      humanChoice: true,
    };
  }
  const quality = target?.closest?.(
    '[data-generation-intake-choice-block="quality"] input[type="radio"]',
  );
  if (quality instanceof HTMLInputElement && quality.checked) {
    patch.quality = String(quality.value || "");
    state.copyEngine = {
      ...(state.copyEngine || {}),
      qualityCode: patch.quality,
      durationNotice: "",
    };
  }
  if (target === form?.elements?.campaign_id) {
    const previous = expressDefaultsMemory.get(projectId()) || {};
    patch.campaign_id = String(target.value || "").trim().toLowerCase();
    patch.campaign_explicit = previous.campaign_explicit === true
      || target?.isTrusted === true;
  }
  const compactCampaign = target?.closest?.(
    "[data-generation-intake-campaign-select]",
  );
  if (
    compactCampaign
    && compactCampaign.dataset?.generationIntakeCampaignSelect !== undefined
  ) {
    patch.campaign_id = String(compactCampaign.value || "").trim().toLowerCase();
    patch.campaign_explicit = true;
  }
  if (!Object.keys(patch).length) return false;
  const key = projectId();
  expressDefaultsMemory.set(key, {
    ...(expressDefaultsMemory.get(key) || {}),
    ...patch,
  });
  return true;
}

function applyExpressDefaults(form, state) {
  const panel = panelFor(state, "copy_video");
  if (!panel) return;
  const saved = expressDefaultsMemory.get(projectId()) || null;
  // Перерисовка страницы сбрасывает select: звук восстанавливается из памяти
  // экспресс-панели, по умолчанию — «Без звука».
  const audio = q('[data-generation-intake-field="audio"]', panel);
  if (
    audio instanceof HTMLSelectElement
    && audio.value !== "true"
    && audio.value !== "false"
  ) {
    audio.value = saved?.audio === "true" ? "true" : "false";
  }
  if (!saved) return;
  if (saved.engine) {
    state.copyEngine = {
      ...(state.copyEngine || {}),
      modelId: saved.engine,
      qualityCode: saved.quality || "",
      durationNotice: "",
      humanChoice: true,
    };
    assignPaidContextValue(
      form.elements?.generation_intake_engine,
      saved.engine,
    );
  }
  const campaign = form.elements?.campaign_id;
  if (
    campaign instanceof HTMLSelectElement
    && (saved.campaign_id || saved.campaign_explicit === true)
  ) {
    const option = [...campaign.options].find((candidate) => (
      candidate.value === saved.campaign_id && !candidate.disabled
    ));
    // Восстановление того же выбора событий не даёт, а вот подстановка другой
    // кампании (или сброс в пустую, когда прежняя стала недоступна) — это смена
    // платного контекста, и подтверждение траты обязано её увидеть.
    if (option) assignPaidContextValue(campaign, option.value);
    else if (saved.campaign_explicit === true) assignPaidContextValue(campaign, "");
  }
  [
    ["sku", saved.sku],
    ["product_name", saved.product_name],
    ["product_category", saved.product_category],
  ].forEach(([fieldName, value]) => {
    if (!value) return;
    const control = identityInput(state, fieldName);
    if (
      (control instanceof HTMLInputElement || control instanceof HTMLSelectElement)
      && !control.value
    ) {
      control.value = value;
      syncIdentityToForm(form, fieldName, value);
    }
  });
  const rights = q('[data-generation-intake-rights="copy_video"]', panel);
  if (rights instanceof HTMLInputElement && saved.rights && !rights.checked) {
    rights.checked = true;
  }
}

function persistHandoff(form, handoff) {
  setHidden(form, "generation_intake_version", HANDOFF_VERSION);
  setHidden(form, "generation_intake_route", handoff.route);
  setHidden(form, "generation_intake_source_media_id", handoff.source_media_id || "");
  setHidden(
    form,
    "generation_intake_source_duration_seconds",
    Number.isSafeInteger(handoff.source_duration_seconds)
      ? String(handoff.source_duration_seconds)
      : "",
  );
  setHidden(form, "generation_intake_original_product_media_id", handoff.original_product_media_id || "");
  setHidden(form, "generation_intake_avatar_media_id", handoff.avatar_media_id || "");
  setHidden(form, "generation_intake_avatar_mode", handoff.avatar_mode || "");
  setHidden(form, "generation_intake_product_media_ids", handoff.product_media_ids || []);
  setHidden(form, "generation_intake_reference_media_ids", handoff.reference_media_ids || []);
  setHidden(form, "generation_intake_source_url", handoff.source_url || "");
  setHidden(form, "generation_intake_description", handoff.description || "");
  setHidden(form, "generation_intake_model", handoff.requested_model || "");
  setHidden(form, "generation_intake_audio", typeof handoff.audio === "boolean" ? String(handoff.audio) : "");
  setHidden(form, "generation_intake_recommendation_source", handoff.recommendation_source || "");
  setHidden(form, "generation_strategy_prefill_assets", handoff.assets || []);
  try {
    sessionStorage.setItem(
      `${HANDOFF_VERSION}:${projectId()}`,
      JSON.stringify({ ...handoff, saved_at: new Date().toISOString() }),
    );
  } catch {
    // Session persistence is optional and never authorizes a paid launch.
  }
  window.dispatchEvent(new CustomEvent("contentengine:generation-strategy-handoff", {
    detail: handoff,
  }));
}

const ASSET_ROLE_LABELS = Object.freeze({
  source_video: "исходный MP4",
  original_product_image: "кадр исходного товара",
  new_product_image: "фото нового товара",
  avatar_image: "фото аватара",
});

function strategyButton(form, strategyId) {
  return q(
    `[data-generation-strategy-action="SELECT"]`
      + `[data-strategy-id="${CSS.escape(strategyId)}"]`,
    form,
  );
}

function selectStrategy(form, strategyId) {
  const button = strategyButton(form, strategyId);
  if (!(button instanceof HTMLButtonElement) || button.disabled) return false;
  button.click();
  return true;
}

function existingMediaCheckbox(form, mediaId) {
  return q(`input[name="media_id"][value="${CSS.escape(mediaId)}"]`, form);
}

// Нативная карточка товара всегда содержит пару media_id + primary_media_id.
// Карточка свежезарегистрированного фото раньше содержала только checkbox, и
// первый handoff не мог назначить «Главное фото» до следующей перерисовки
// серверного каталога. Создаём тот же radio только внутри нашей synthetic-
// карточки и только когда её paid-ready атрибуты и идентичность полны. Если
// хотя бы одно условие не выполнено, openNativeLaunch останется fail-closed.
function ensureSyntheticProductPrimary(input) {
  if (!(input instanceof HTMLInputElement) || input.name !== "media_id") {
    return null;
  }
  const mediaId = String(input.value || "").trim().toLowerCase();
  const option = input.closest("[data-generation-intake-synthetic]");
  if (
    !UUID_PATTERN.test(mediaId)
    || input.disabled
    || !(option instanceof HTMLElement)
    || option.dataset.paidReady !== "true"
    || input.dataset.mediaIdentityVerified !== "true"
    || input.dataset.mediaRightsConfirmed !== "true"
    || !cleanText(input.dataset.mediaSku, 120)
    || !cleanText(input.dataset.mediaProductName, 180)
  ) {
    return null;
  }
  const existing = qa('input[name="primary_media_id"]', option).find(
    (radio) => String(radio.value || "").trim().toLowerCase() === mediaId,
  );
  if (existing instanceof HTMLInputElement) {
    return existing.disabled ? null : existing;
  }
  const primaryLabel = el("label", "generation-media-option__primary");
  // До выбора Product Swap обычный app.js тоже прячет этот control. Его
  // делегированный change-handler покажет radio после выбора стратегии.
  primaryLabel.hidden = true;
  const primary = el("input");
  primary.type = "radio";
  primary.name = "primary_media_id";
  primary.value = mediaId;
  primaryLabel.append(primary, el("span", "", "Главное фото"));
  option.append(primaryLabel);
  return primary;
}

function ensureProductCheckbox(form, state, mediaId, identity, filename) {
  const existing = existingMediaCheckbox(form, mediaId);
  if (existing instanceof HTMLInputElement) {
    ensureSyntheticProductPrimary(existing);
    if (!existing.disabled && !existing.checked) {
      existing.checked = true;
      existing.dispatchEvent(new Event("change", { bubbles: true }));
    }
    return existing;
  }
  // Фото уже зарегистрировано на сервере (registerMedia с sku/названием и
  // подтверждёнными правами), но список материалов app.js ещё не обновился.
  // Локальная карточка честно отражает серверное состояние; при следующем
  // обновлении раздела её заменит серверная (см. pruneSyntheticProductOptions),
  // а привязка всё равно перепроверяется сервером на bind/preflight.
  const slot = q(".generation-intake-v4__product-items", state.shell);
  const host = slot
    || existingMediaCheckbox(form, "")?.closest?.(".options")
    || q(".generation-intake-v4__panels", state.shell)
    || form;
  const option = el("div", "option generation-media-option");
  option.dataset.paidReady = "true";
  option.dataset.generationIntakeSynthetic = "true";
  const label = el("label", "generation-media-option__select");
  const input = el("input");
  input.type = "checkbox";
  input.name = "media_id";
  input.value = mediaId;
  input.checked = true;
  input.dataset.mediaIdentityVerified = "true";
  input.dataset.mediaRightsConfirmed = "true";
  input.dataset.mediaSku = identity?.sku || "";
  input.dataset.mediaProductName = identity?.product_name || "";
  const text = el("span");
  const caption = [identity?.sku, identity?.product_name]
    .filter(Boolean).join(" · ");
  text.append(
    el("strong", "", cleanText(filename, 120) || "Новое фото товара"),
    document.createElement("br"),
    el("small", "muted", `фото товара${caption ? ` · ${caption}` : ""} · загружено только что`),
  );
  label.append(input, text);
  option.append(label);
  ensureSyntheticProductPrimary(input);
  host.append(option);
  input.dispatchEvent(new Event("change", { bubbles: true }));
  return input;
}

function attachProductFilePreview(input, file) {
  if (!(input instanceof HTMLInputElement) || !(file instanceof File)) return;
  if (!String(file.type || "").toLowerCase().startsWith("image/")) return;
  const option = input.closest(".generation-media-option");
  const label = option?.querySelector?.(".generation-media-option__select");
  if (!(label instanceof HTMLLabelElement)) return;
  label.querySelector(".generation-media-option__thumbnail")?.remove();
  const previewUrl = URL.createObjectURL(file);
  const image = document.createElement("img");
  image.className = "generation-media-option__thumbnail";
  image.src = previewUrl;
  image.alt = cleanText(file.name, 120) || "Новое фото товара";
  const release = () => URL.revokeObjectURL(previewUrl);
  image.addEventListener("load", release, { once: true });
  image.addEventListener("error", release, { once: true });
  input.after(image);
}

function pruneSyntheticProductOptions(form) {
  qa('[data-generation-intake-synthetic] input[name="media_id"]', form)
    .forEach((input) => {
      const value = String(input.value || "");
      const real = qa(
        `input[name="media_id"][value="${CSS.escape(value)}"]`,
        form,
      ).find((candidate) => (
        candidate !== input
        && !candidate.closest("[data-generation-intake-synthetic]")
      ));
      if (!real) return;
      const restoredOrder = productSelectionOrder(input);
      if (restoredOrder !== null && productSelectionOrder(real) === null) {
        setProductSelectionOrder(real, restoredOrder);
      }
      if (input.checked && !real.disabled && !real.checked) {
        real.checked = true;
        real.dispatchEvent(new Event("change", { bubbles: true }));
      }
      input.closest("[data-generation-intake-synthetic]")?.remove();
    });
}

function bindRoleAsset(form, role, mediaId, selectionOrder = null) {
  const escapedRole = CSS.escape(role);
  const escapedMedia = CSS.escape(mediaId);
  const selectors = [
    `[data-generation-strategy-role="${escapedRole}"] input[value="${escapedMedia}"]`,
    `[data-generation-strategy-role="${escapedRole}"] option[value="${escapedMedia}"]`,
    `input[data-generation-strategy-role="${escapedRole}"][value="${escapedMedia}"]`,
    `input[name*="${escapedRole}"][value="${escapedMedia}"]`,
    `option[data-generation-strategy-role="${escapedRole}"][value="${escapedMedia}"]`,
    `input[name="generation_strategy_source_selection"][value="${escapedMedia}"]`,
    ...(role === "new_product_image" || role === "product_image"
      ? [`input[name="media_id"][value="${escapedMedia}"]`]
      : []),
  ];
  let changed = false;
  selectors.forEach((selector) => {
    qa(selector, form).forEach((control) => {
      if (control instanceof HTMLOptionElement) {
        control.selected = true;
        control.parentElement?.dispatchEvent(new Event("change", { bubbles: true }));
      } else if (control instanceof HTMLInputElement) {
        if (
          ["new_product_image", "product_image"].includes(role)
          && Number.isSafeInteger(selectionOrder)
          && selectionOrder > 0
          && control.name === "media_id"
        ) {
          setProductSelectionOrder(control, selectionOrder);
        }
        if (
          control.name === "generation_strategy_source_selection"
          && !control.checked
        ) {
          control.click();
        } else {
          control.checked = true;
          control.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
      changed = true;
    });
  });
  return changed;
}

function bindHandoffAsset(form, handoff, asset) {
  const role = String(asset?.role || "");
  const mediaId = String(asset?.media_id || "").trim().toLowerCase();
  const productIds = Array.isArray(handoff?.product_media_ids)
    ? handoff.product_media_ids.map((value) => String(value || "").trim().toLowerCase())
    : [];
  const productIndex = ["new_product_image", "product_image"].includes(role)
    ? productIds.indexOf(mediaId)
    : -1;
  return bindRoleAsset(
    form,
    role,
    mediaId,
    productIndex < 0 ? null : productIndex + 1,
  );
}

function bindHandoffPrimaryProduct(form, handoff) {
  const mediaId = String(handoff?.product_media_ids?.[0] || "")
    .trim().toLowerCase();
  if (!UUID_PATTERN.test(mediaId)) return false;
  const primary = qa('input[name="primary_media_id"]', form).find(
    (radio) => String(radio.value || "").trim().toLowerCase() === mediaId,
  );
  if (!(primary instanceof HTMLInputElement) || primary.disabled) return false;
  qa('input[name="primary_media_id"]', form).forEach((radio) => {
    radio.checked = radio === primary;
  });
  primary.dispatchEvent(new Event("input", { bubbles: true }));
  primary.dispatchEvent(new Event("change", { bubbles: true }));
  return primary.checked === true;
}

async function openNativeLaunch(initialForm, handoff) {
  // На отдельном экране копии движок остаётся невидимым: режим не
  // переключается в "full", пять блоков не разъезжаются по шагам мастера.
  // «Дуэт» с 23.08.2026 ведёт мастер так же — из своей панели: раньше он
  // выбрасывал человека в полный конструктор с чужими подписями «Product Swap»,
  // пятью скрытыми галками прав и потерянным выбором исходника.
  const copyScreen = copyViewActive();
  const compactFlow = copyScreen || handoff.route === "avatar_video";
  const materialize = (form) => {
    // Только что загруженный ролик/кадр уже зарегистрирован в проекте, но
    // refresh мог вернуть список, снятый до регистрации. Временные option
    // переносят exact UUID; eligibility и права всё равно проверит сервер.
    const handoffSource = handoff.assets.find(
      ({ role }) => role === "source_video",
    );
    if (handoffSource) {
      ensureSourceOption(
        form,
        handoffSource.media_id,
        "",
        handoffSource.duration_seconds,
      );
      // registerMedia + direct-MP4 attachment already succeeded before this
      // handoff. Materialize the exact UUID in the authoritative source picker
      // too; the compatibility select alone must never count as a selection.
      window.ContentEngineGenerationGuidedV4
        ?.materializeRegisteredSource?.(form, {
          media_id: handoffSource.media_id,
          filename: "Загруженный ролик",
          duration_seconds: handoffSource.duration_seconds ?? null,
        });
    }
    const handoffOriginalProduct = handoff.assets.find(
      ({ role }) => role === "original_product_image",
    );
    if (handoffOriginalProduct) {
      ensureOriginalProductOption(form, handoffOriginalProduct.media_id);
    }
  };
  const activate = (form, { persist = false } = {}) => {
    // app.js вправе patch-render'ить #mock-batch-form, пока refresh ждёт
    // сервер. Старый DOM всё ещё принимает click(), но нативная форма его уже
    // не читает. Монтируем/настраиваем именно живой объект и повторяем handoff.
    if (!formStates.has(form)) mount(form);
    const state = formStates.get(form);
    if (state) {
      state.phase = "review";
      // Новый state создаётся с busy=false. Handoff ещё идёт, поэтому такая
      // shell иначе разрешила бы второй параллельный prepare по тому же клику.
      adoptRouteBusy(state, handoff.route, expressPrepareAction(handoff.route));
    }
    ensureContractFields(form);
    form.dataset.generationIntakeV4Mode = copyScreen
      ? "copy"
      : compactFlow
        ? "compact"
        : "full";
    form.dataset.generationIntakeV4Phase = "review";
    form.dataset.generationIntakeV4Route = handoff.route;
    if (!compactFlow && state) {
      captureBriefDraft(form, state, state.briefRoute || handoff.route);
      restoreBriefDraft(form, state, "strategy_video");
      moveProductNodes(form, state, false);
      moveSharedBrief(form, state, "strategy_video");
    }
    if (persist) persistHandoff(form, handoff);
    selectStrategy(form, handoff.strategy_id);
    applyCompactPreferences(form, handoff);
    materialize(form);
    if (!compactFlow && state) captureBriefDraft(form, state, "strategy_video");
    return state;
  };
  const refreshAssets = async (form) => {
    await window.ContentEngineGenerationGuidedV4
      ?.refreshStrategyAssets?.(form);
  };

  let form = initialForm;
  let state = activate(form, { persist: true });
  await refreshAssets(form);
  // A refresh may patch the form more than once (loading -> ready). Adopt at
  // most three successive live objects; every adoption replays only free UI
  // binding and never calls provider/start.
  for (let adoption = 0; adoption < 3; adoption += 1) {
    const live = liveGenerationForm(form);
    if (live === form) break;
    form = live;
    state = activate(form, { persist: true });
    await refreshAssets(form);
  }
  let missing = [];
  let stable = false;
  // Кандидаты и сама форма дорисовываются асинхронно. Важен не только первый
  // успешный bind: input/change от duration/primary тоже может вызвать
  // patch-render уже ПОСЛЕ missing=[]. Поэтому каждая итерация начинает с
  // adoption живой формы, повторяет ВЕСЬ handoff и завершается event-loop yield
  // с проверкой, что объект формы не сменился. Вернуть missing от detached A и
  // live form B без ассетов теперь невозможно.
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const live = liveGenerationForm(form);
    if (live !== form) {
      form = live;
      state = activate(form, { persist: true });
      await refreshAssets(form);
    }
    materialize(form);
    missing = handoff.assets.filter(
      (asset) => !bindHandoffAsset(form, handoff, asset),
    );
    const handoffSource = handoff.assets.find(
      ({ role }) => role === "source_video",
    );
    const sourceProjection = window.ContentEngineGenerationGuidedV4
      ?.getStrategySourcePickerProjection?.(form);
    const exactSourceBound = Boolean(
      handoffSource
      && sourceProjection?.selected_count === 1
      && sourceProjection.selected?.[0]?.source_media_id
        === String(handoffSource.media_id || "").trim().toLowerCase()
    );
    if (
      handoffSource
      && !exactSourceBound
      && !missing.some(({ role }) => role === "source_video")
    ) {
      missing.push({ role: "source_video" });
    }
    // SELECT стратегии ставит server default (сейчас 10 с). Для уже
    // проверенного project MP4 возвращаем exact секунды после каждого rebind;
    // fresh upload получит их после бесплатного probe в preflight.
    applyHandoffSourceDuration(form, handoff);
    if (state) refreshProductSelectionCount(form, state);
    // Серверное ТЗ требует «Главное фото» (primary_media_id); компактная форма
    // выбирает ПЕРВОЕ фото click-order handoff на каждом новом DOM.
    const primaryBound = bindHandoffPrimaryProduct(form, handoff);
    if (
      Array.isArray(handoff.product_media_ids)
      && handoff.product_media_ids.length
      && !primaryBound
      && !missing.some(({ role }) => role === "new_product_image")
    ) {
      missing.push({ role: "new_product_image" });
    }

    // MutationObserver/microtasks, вызванные событиями выше, получают шанс
    // заменить форму до того, как мы объявим handoff устойчивым.
    await waitMs(0);
    if (liveGenerationForm(form) === form) {
      if (!missing.length || attempt === 7) {
        stable = true;
        break;
      }
      // Ассеты ещё не дорисованы. До пяти секунд ждём каталог короткими
      // шагами; на следующей итерации binding выполняется целиком заново.
      await waitMs(700);
    }
  }
  if (!stable || liveGenerationForm(form) !== form) {
    throw new Error("express_native_handoff_unstable");
  }
  if (!compactFlow) {
    q('[data-ce-v4-generation-target="media"]', form)?.click?.();
    requestAnimationFrame(() => {
      q(".generation-strategy-view", form)?.scrollIntoView?.({
        behavior: "smooth",
        block: "start",
      });
    });
  }
  const context = liveCopyLaunchContext(form, state, null, { busy: true });
  if (context.form !== form || !context.state || !context.panel) {
    throw new Error("express_native_handoff_unstable");
  }
  return {
    missingRoles: missing.map(({ role }) => role),
    form: context.form,
    state: context.state,
    panel: context.panel,
  };
}

function frameAsFile(frame, route) {
  return new File(
    [frame.blob],
    `${route}-original-product-${frame.time.toFixed(2).replace(".", "-")}.jpg`,
    { type: "image/jpeg", lastModified: Date.now() },
  );
}

function secondsLabel(value) {
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds > 0 ? `${seconds.toFixed(1)} с` : "";
}

// Отказ по длительности называет и факт, и предел, и следующее действие:
// «слишком длинный файл» без цифр человек читать не обязан.
function durationTooLongMessage(durationSeconds, limitSeconds) {
  const measured = secondsLabel(durationSeconds);
  return measured
    ? `Ролик длиннее допустимого: в файле ${measured}, предел ${limitSeconds} с. Файл не принят — обрежьте его до ${limitSeconds} с или выберите другой MP4. Ничего не загружено и не оплачено.`
    : `Ролик длиннее допустимых ${limitSeconds} секунд. Файл не принят — обрежьте его или выберите другой MP4. Ничего не загружено и не оплачено.`;
}

function durationTooShortMessage(durationSeconds) {
  const measured = secondsLabel(durationSeconds);
  return measured
    ? `Ролик короче допустимого: в файле ${measured}, нужно не меньше ${MIN_COPY_DURATION} с. Файл не принят — выберите более длинный MP4.`
    : `Для Product Swap нужен ролик не короче ${MIN_COPY_DURATION} секунд. Файл не принят — выберите более длинный MP4.`;
}

// Текст статуса должен называть кнопку, которая действительно есть на текущем
// экране. У compact Copy это «Проверить ролик бесплатно», у Avatar —
// «Разобрать MP4», а отдельный экран Copy ведёт через основную кнопку цены.
// Чтение подписи из DOM не даёт подсказкам снова разойтись с интерфейсом.
function selectedSourceNextStep(panel, route) {
  const action = copyViewActive() && route === "copy_video"
    ? "generation-intake-prepare-copy"
    : route === "copy_video"
    ? "generation-intake-analyze-copy"
    : "generation-intake-analyze-avatar";
  const fallback = route === "copy_video"
    ? copyViewActive() ? "Подготовить ролик" : "Проверить ролик бесплатно"
    : "Разобрать MP4";
  const button = q(`[data-action="${action}"]`, panel);
  return `«${cleanText(button?.textContent, 80) || fallback}»`;
}

// Проверка длительности сразу после выбора файла: раньше несоответствие
// вскрывалось только при подготовке, и выбранный ролик отвергался молча.
async function reportSelectedSourceDuration(state, route, input) {
  const panel = panelFor(state, route);
  const file = input?.files?.[0];
  if (!panel || !(file instanceof File)) return;
  const limit = route === "copy_video" ? MAX_COPY_DURATION : MAX_AVATAR_DURATION;
  const nextStep = selectedSourceNextStep(panel, route);
  const unreadable = `Браузер не смог измерить длительность этого файла. Нажмите ${nextStep} — форма проверит файл ещё раз и назовёт точную причину.`;
  let metadata = null;
  try {
    metadata = await videoMetadata(file);
  } catch {
    // Пока читались метаданные, человек мог выбрать другой файл.
    if (input.files?.[0] === file) {
      setStatus(panel, unreadable, "warning");
      setSourceFileSummary(panel, `${sourceFileLead(file)} — длительность измерит сервер`, "warning");
    }
    return;
  }
  if (input.files?.[0] !== file) return;
  const seconds = Number(metadata?.duration);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    setStatus(panel, unreadable, "warning");
    setSourceFileSummary(panel, `${sourceFileLead(file)} — длительность измерит сервер`, "warning");
    return;
  }
  const routeState = state.routes?.[route];
  if (routeState) routeState.durationSeconds = seconds;
  // Предел речи «Дуэта» зависит от длины ролика: подпись под текстом
  // обновляется сразу, как только длительность измерена.
  if (route === "avatar_video") {
    const form = state.shell?.closest?.("form");
    if (form) refreshRecommendationUi(form, state);
  }
  if (seconds > limit + 0.05) {
    setStatus(panel, durationTooLongMessage(seconds, limit), "error");
    setSourceFileSummary(
      panel,
      `${sourceFileLead(file)} · ${secondsLabel(seconds)} — длиннее предела ${limit} с, файл не принят`,
      "error",
    );
    return;
  }
  if (route === "copy_video" && seconds < MIN_COPY_DURATION - 0.05) {
    setStatus(panel, durationTooShortMessage(seconds), "error");
    setSourceFileSummary(
      panel,
      `${sourceFileLead(file)} · ${secondsLabel(seconds)} — короче ${MIN_COPY_DURATION} с, файл не принят`,
      "error",
    );
    return;
  }
  setSourceFileSummary(
    panel,
    `${sourceFileLead(file)} · ${secondsLabel(seconds)} — выбран. Дальше: ${nextStep}`,
    "ready",
  );
  setStatus(
    panel,
    copyViewActive() && route === "copy_video"
      ? `MP4 выбран · ${secondsLabel(seconds)} из допустимых ${limit} с. Нажмите ${nextStep} — разбор и бесплатная проверка выполнятся автоматически.`
      : `MP4 выбран · ${secondsLabel(seconds)} из допустимых ${limit} с. Нажмите ${nextStep}.`,
    "ready",
  );
}

async function analyzeRoute(form, route) {
  const state = formStates.get(form);
  const panel = panelFor(state, route);
  if (!state || !panel) return;
  if (state.busy) {
    reportRouteBusy(state, route);
    return;
  }
  const file = selectedFile(panel);
  const existingMediaId = selectedExistingVideo(panel);
  if (!file && !existingMediaId) {
    setStatus(panel, "Выберите MP4 или ролик из файлов проекта.", "error");
    return;
  }
  if (!file && existingMediaId) {
    state.routes[route] = {
      ...state.routes[route],
      sourceMediaId: existingMediaId,
      sourceFile: null,
      metadata: null,
      storyboard: null,
      selectedFrameIndex: null,
    };
    setStatus(
      panel,
      route === "copy_video"
        ? "Ролик проекта выбран. Кадр исходного товара подберётся автоматически при «Показать цену»: из готовых кадров проекта или серверного разбора."
        : "Ролик проекта выбран и готов к подготовке Character Performance.",
      "ready",
    );
    q(`[data-action="generation-intake-prepare-${route === "copy_video" ? "copy" : "avatar"}"]`, panel).disabled = false;
    return;
  }
  const busyAction = route === "copy_video"
    ? "generation-intake-analyze-copy"
    : "generation-intake-analyze-avatar";
  beginRouteBusy(
    state,
    route,
    busyAction,
    "Проверяем MP4 и собираем storyboard…",
  );
  try {
    const maximum = route === "copy_video" ? MAX_COPY_DURATION : MAX_AVATAR_DURATION;
    const metadata = await assertMp4(file, maximum);
    // Длительность может быть неизвестна: браузер не всегда отдаёт метаданные,
    // хотя файл исправен. Неизвестное — это не «ноль секунд», поэтому нижнюю
    // границу проверяем только когда есть что проверять. Точную длительность
    // всё равно меряет сервер, и отказ придёт от него, а не от догадки.
    if (
      route === "copy_video"
      && Number.isFinite(metadata.duration)
      && metadata.duration < MIN_COPY_DURATION - 0.05
    ) {
      const failure = new Error("mp4_duration_too_short");
      failure.durationSeconds = metadata.duration;
      throw failure;
    }
    // Раскадровка — вспомогательный предпросмотр, а не условие запуска.
    // Если браузер не смог её собрать, это не повод останавливать человека:
    // исходник уходит на сервер, и разбор делает он.
    let storyboard = null;
    if (route === "copy_video") {
      try {
        storyboard = await captureStoryboard(file);
      } catch {
        storyboard = null;
      }
    }
    state.routes[route] = {
      ...state.routes[route],
      sourceFile: file,
      sourceMediaId: "",
      metadata,
      durationSeconds: metadata.duration,
      storyboard,
      selectedFrameIndex: storyboard?.recommendedIndex ?? null,
    };
    if (storyboard) renderStoryboard(panel, storyboard, state.routes[route]);
    // Раскадровки нет — значит и кадра исходного товара автоматика не даст.
    // Блок ручного кадра открывается сразу, а не после отказа подготовки:
    // человек должен узнать о недостающем шаге до того, как упрётся в него.
    const frameSlot = q("[data-generation-intake-original-frame]", panel);
    if (frameSlot instanceof HTMLElement) frameSlot.hidden = Boolean(storyboard);
    q(`[data-action="generation-intake-prepare-${route === "copy_video" ? "copy" : "avatar"}"]`, panel).disabled = false;
    // assertMp4 намеренно возвращает duration = null там, где браузер не смог
    // прочитать метаданные: замер браузера — удобство, а власть у серверного.
    // Строка статуса обязана это выдержать. Раньше она звала
    // metadata.duration.toFixed(1) без проверки, падала на null внутри общего
    // try и выходила наружу как «Не удалось разобрать MP4. Попробуйте другой
    // файл» — совет сменить исправный файл, из-за которого маршрут закрывался
    // целиком. Ширины и высоты в таком ответе нет вовсе, поэтому проверяются
    // все три числа, а не одна длительность.
    const measured = Number.isFinite(metadata.duration)
      && Number.isFinite(metadata.width)
      && Number.isFinite(metadata.height)
      ? `${metadata.duration.toFixed(1)} с · ${metadata.width}×${metadata.height}`
      : "Длительность и размер измерит сервер при подготовке";
    // Раскадровка собирается тем же декодером, поэтому там, где нет замера,
    // обычно нет и кадров. Обещать «предложенный кадр», которого не собрали,
    // значит отправить человека искать несуществующий элемент.
    const storyboardNote = storyboard
      ? ` · ${STORYBOARD_FRAME_COUNT} кадров. Проверьте предложенный кадр исходного товара и нажмите «Показать цену».`
      : ". Раскадровку браузер не собрал — нажмите «Показать цену», кадр исходного товара подберёт сервер.";
    setStatus(
      panel,
      route === "copy_video"
        ? `${measured}${storyboardNote}`
        : `${measured}. Исходный ролик готов. Выберите товар и ведущего и нажмите «Подготовить дуэт».`,
      "ready",
    );
    setSourceFileSummary(panel, `${sourceFileLead(file)} · ${measured} — разобран`, "success");
  } catch (error) {
    const limit = route === "copy_video" ? MAX_COPY_DURATION : MAX_AVATAR_DURATION;
    const messages = {
      media_kind_mime_mismatch: mediaKindMimeMismatchMessage(error, file?.name),
      mp4_required: "Нужен настоящий MP4-файл.",
      mp4_too_large: "MP4 больше 32 МБ.",
      mp4_signature_invalid: "Файл не содержит корректную MP4/ISO-BMFF сигнатуру.",
      mp4_duration_too_long: durationTooLongMessage(error?.durationSeconds, limit),
      mp4_duration_too_short: durationTooShortMessage(error?.durationSeconds),
      mp4_duration_invalid: "Не удалось измерить длительность ролика. Выберите другой MP4 — этот файл не принят.",
      mp4_metadata_invalid: "Браузер не смог прочитать этот файл как видео. Выберите другой MP4 — этот файл не принят.",
      mp4_metadata_timeout: "Файл читается слишком долго и не принят. Выберите другой MP4 или пересохраните этот.",
    };
    setStatus(panel, messages[error?.message] || "Не удалось разобрать MP4. Попробуйте другой файл.", "error");
    setSourceFileSummary(panel, `${sourceFileLead(file)} — не принят, причина в строке состояния`, "error");
  } finally {
    finishRouteBusy(state);
  }
}

async function ensureSourceMedia(routeState) {
  if (UUID_PATTERN.test(routeState.sourceMediaId || "")) {
    const api = await apiRuntime();
    await attachDirectMp4(api, routeState.sourceMediaId);
    await stampCopyOriginOnMedia(api, routeState.sourceMediaId);
    return routeState.sourceMediaId;
  }
  if (!(routeState.sourceFile instanceof File)) {
    throw new Error("source_media_required");
  }
  routeState.sourceMediaId = await uploadProjectMedia(
    routeState.sourceFile,
    "source_video",
  );
  await stampCopyOriginOnMedia(await apiRuntime(), routeState.sourceMediaId);
  return routeState.sourceMediaId;
}

// Гейт кадра исходного товара выполнен, если нативный селект мастера уже
// содержит валидный uuid — неважно, кто его установил: кадр локального
// разбора, ручной выбор или существующий creator_reference.
function wizardOriginalProductMediaId(form) {
  const value = String(
    form.elements?.generation_strategy_original_product_media_id?.value || "",
  ).trim().toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

// Человек должен видеть, какой кадр выбран, даже когда локальных кадров нет.
function showChosenFrameNote(panel, text) {
  const section = q("[data-generation-intake-storyboard]", panel);
  if (!section) return;
  section.hidden = false;
  let note = q("[data-generation-intake-frame-note]", section);
  if (!note) {
    note = el("p", "generation-intake-v4__frame-note");
    note.dataset.generationIntakeFrameNote = "";
    section.append(note);
  }
  setNodeText(note, text);
}

function noteChosenFrame(form, panel, mediaId) {
  const select = form.elements?.generation_strategy_original_product_media_id;
  const option = select instanceof HTMLSelectElement
    ? [...select.options].find((item) => (
      String(item.value || "").trim().toLowerCase() === mediaId
    ))
    : null;
  showChosenFrameNote(
    panel,
    `Кадр исходного товара выбран: ${option ? cleanText(option.textContent, 120) : `кадр ${mediaId.slice(0, 8)}`}. Сменить можно в полном конструкторе.`,
  );
}

// Серверный ролик без кадра: сначала берём существующие original-product
// кадры проекта из нативного селекта мастера и автоматически выбираем первый.
function adoptExistingOriginalProductFrame(form, panel) {
  const select = form.elements?.generation_strategy_original_product_media_id;
  if (!(select instanceof HTMLSelectElement)) return "";
  const option = [...select.options].find((item) => (
    UUID_PATTERN.test(String(item.value || "").trim().toLowerCase())
  ));
  if (!option) return "";
  const mediaId = String(option.value).trim().toLowerCase();
  if (select.value !== option.value) {
    select.value = option.value;
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }
  noteChosenFrame(form, panel, mediaId);
  return mediaId;
}

function findMediaObjectKey(payload, mediaId, depth = 0) {
  if (depth > 6 || !payload || typeof payload !== "object") return "";
  if (Array.isArray(payload)) {
    for (const item of payload) {
      const found = findMediaObjectKey(item, mediaId, depth + 1);
      if (found) return found;
    }
    return "";
  }
  const id = String(
    payload.id || payload.media_id || payload.public_id || "",
  ).trim().toLowerCase();
  const objectKey = String(
    payload.object_name || payload.objectName || payload.object_key || "",
  ).trim();
  if (id === mediaId && objectKey) return objectKey;
  for (const value of Object.values(payload)) {
    const found = findMediaObjectKey(value, mediaId, depth + 1);
    if (found) return found;
  }
  return "";
}

// Селект кадров пуст: серверный разбор без новых контрактов — скачиваем
// подтверждённый MP4 из защищённого хранилища (downloadPrivateObject, как в
// разборе полного флоу) и прогоняем существующий storyboard с автолучшим
// кадром. Ничего не запускается и не оплачивается.
async function serverStoryboardForCopy(state, panel, sourceMediaId) {
  const api = await apiRuntime();
  if (
    typeof api.contentReviewCatalog !== "function"
    || typeof api.downloadPrivateObject !== "function"
  ) {
    throw new Error("server_frame_analysis_unavailable");
  }
  setStatus(panel, "Готовых кадров товара нет — запускаем серверный разбор ролика…", "busy");
  const catalog = await api.contentReviewCatalog({
    projectId: projectId(),
    limit: 50,
  });
  const objectKey = findMediaObjectKey(catalog?.data ?? catalog, sourceMediaId);
  if (!objectKey) throw new Error("server_frame_media_unresolved");
  const blob = await api.downloadPrivateObject(objectKey);
  const file = new File(
    [blob],
    `server-${sourceMediaId.slice(0, 8)}.mp4`,
    { type: "video/mp4" },
  );
  const storyboard = await captureStoryboard(file);
  const routeState = {
    ...state.routes.copy_video,
    storyboard,
    selectedFrameIndex: storyboard.recommendedIndex,
  };
  state.routes.copy_video = routeState;
  renderStoryboard(panel, storyboard, routeState);
  return routeState;
}

// Вторая фаза кнопки цены: явный человеческий клик «Запустить за $X».
// Он и есть подтверждение цены — клик ставит настоящий чекбокс подтверждения
// списания и жмёт действующую кнопку запуска мастера. Серверный контракт
// (spend_confirmation + campaign_id + start) не обходится.
async function startExpressLaunch(initialForm) {
  const initialState = formStates.get(initialForm);
  const initialRoute = expressRoute(initialState);
  const initialPanel = initialState ? panelFor(initialState, initialRoute) : null;
  const initialContext = liveCopyLaunchContext(
    initialForm,
    initialState,
    initialPanel,
  );
  let { form, state, panel } = initialContext;
  if (!state || !panel) return;
  const route = expressRoute(state);
  if (state.busy) {
    reportRouteBusy(state, route);
    return;
  }
  const express = { ...(state.express || {}) };
  if (express.phase !== "priced") {
    if (route === "avatar_video") void prepareAvatar(form);
    else void prepareCopy(form);
    return;
  }
  beginRouteBusy(
    state,
    route,
    expressPrepareAction(route),
    "Проверяем цену и подтверждение перед единственным платным запуском…",
  );
  try {
    // Мастер мог быть перерисован после получения цены: и подтверждение
    // списания, и кнопка запуска берутся из живой формы, иначе клик уйдёт в
    // отсоединённый узел и платный старт молча не случится.
    const campaignId = autoSelectCampaign(form, panel, state);
    if (!campaignId) {
      setExpressPricePhase(state, "", "");
      setStatus(
        panel,
        "Платный запуск невозможен: выбранная кампания недоступна или не выбрана. Выберите активную кампанию выше и заново получите цену.",
        "error",
      );
      return;
    }
    const confirmation = form.elements?.real_spend_confirmation;
    if (
      form.dataset.generationStrategyConfirmationReady !== "true"
      || !(confirmation instanceof HTMLInputElement)
      || confirmation.disabled
      || !express.spend_confirmation
      || confirmation.value !== express.spend_confirmation
      || !express.price
      || serverPriceLabel(form) !== express.price
      || !expressCampaignMatchesPrice(form, express, campaignId)
    ) {
      setExpressPricePhase(state, "", "");
      setStatus(
        panel,
        "Серверная цена устарела или контекст изменился. Нажмите «Показать цену» ещё раз — это бесплатно.",
        "warning",
      );
      return;
    }
    if (!confirmation.checked) confirmation.click();
    // change/input могут сразу patch-render'ить мастер. Нельзя продолжать с
    // checkbox и submitButton, захваченными до человеческого подтверждения.
    await waitMs(0);
    const confirmedContext = liveCopyLaunchContext(
      form,
      state,
      panel,
      { busy: true },
    );
    form = confirmedContext.form;
    state = confirmedContext.state;
    panel = confirmedContext.panel;
    const liveConfirmation = form?.elements?.real_spend_confirmation;
    const liveCampaignId = state && panel
      ? autoSelectCampaign(form, panel, state)
      : "";
    const submitButton = q("#generation-submit", form);
    if (
      !state
      || !panel
      || form.dataset.generationStrategyConfirmationReady !== "true"
      || !(liveConfirmation instanceof HTMLInputElement)
      || liveConfirmation.disabled
      || liveConfirmation.checked !== true
      || liveConfirmation.value !== express.spend_confirmation
      || serverPriceLabel(form) !== express.price
      || liveCampaignId !== express.campaign_id
      || !expressCampaignMatchesPrice(form, express, liveCampaignId)
    ) {
      if (state) setExpressPricePhase(state, "", "");
      setStatus(
        panel,
        "Цена или подтверждение изменились после клика. Ничего не запущено; нажмите «Подготовить ролик» ещё раз.",
        "error",
      );
      return;
    }
    if (!(submitButton instanceof HTMLButtonElement) || submitButton.disabled) {
      setStatus(
        panel,
        cleanText(submitButton?.dataset?.launchBlocker, 300)
          || "Мастер ещё не готов к платному запуску. Проверьте шаг «Исходники».",
        "error",
      );
      return;
    }
    setStatus(
      panel,
      `Отправляем один платный Product Swap за ${express.price}. Ваш клик и был подтверждением цены.`,
      "busy",
    );
    submitButton.click();
    // Нативный submit синхронно ставит data-busy до первого provider await.
    // Если этого не произошло, клик не был принят и compact-кнопка не должна
    // делать вид, что платный запуск начался.
    if (form.dataset.busy !== "true") {
      setStatus(
        panel,
        "Мастер не принял платный запуск. Ничего не отправлено; проверьте сообщение в шаге «Исходники» и заново подтвердите цену.",
        "error",
      );
      return;
    }
    // Задача создана мастером асинхронно; как только он опубликует её id на
    // форме, панель начнёт следить за ней и скажет, когда ролик будет готов.
    // Раньше статус «Отправляем…» застывал навсегда, хотя задача успевала
    // завершиться и файл лежал в проекте.
    void watchExpressLaunchJob(form, expressRoute(state), express.price);
  } finally {
    finishRouteBusy(initialState);
    finishRouteBusy(state);
    const finalContext = liveCopyLaunchContext(form, state, panel);
    finishRouteBusy(finalContext.state);
  }
}

const EXPRESS_JOB_WATCH_INTERVAL_MS = 10_000;
const EXPRESS_JOB_WATCH_DEADLINE_MS = 20 * 60_000;
const EXPRESS_JOB_TERMINAL_STATUSES = Object.freeze({
  succeeded: "succeeded",
  failed: "failed",
  cancelled: "cancelled",
});

// Наблюдение за оплаченной задачей из компактной панели. Бесплатный статус
// (действие "status") опрашивается, пока задача не станет терминальной; провайдера
// при этом опрашивает только сервер. Паникующих сообщений нет: не дождались —
// говорим, где смотреть, а не «что-то сломалось».
async function watchExpressLaunchJob(initialForm, route, price) {
  // Вне настоящего DOM (исполняемые контракты гоняют панель в Node) наблюдать
  // не за чем — и падать с ReferenceError тоже нельзя.
  const doc = initialForm?.ownerDocument
    || (typeof document === "undefined" ? null : document);
  if (!doc) return;
  let jobId = "";
  const deadline = Date.now() + EXPRESS_JOB_WATCH_DEADLINE_MS;
  // id публикуется мастером после ответа сервера — ждём его недолго.
  for (let attempt = 0; attempt < 120 && !jobId; attempt += 1) {
    await waitMs(500);
    const form = doc.querySelector("#mock-batch-form");
    jobId = String(form?.dataset?.generationStrategyLastJobId || "").trim();
  }
  const describe = (form) => {
    const state = form ? formStates.get(form) : null;
    return { form, state, panel: state ? panelFor(state, route) : null };
  };
  if (!jobId) {
    const { panel } = describe(doc.querySelector("#mock-batch-form"));
    if (panel) {
      setStatus(
        panel,
        `Платный запуск за ${price} отправлен. Ход задачи виден во вкладке «Запуски и готовые файлы»; готовый ролик появится там же.`,
        "busy",
      );
    }
    return;
  }
  let lastShown = "";
  while (Date.now() < deadline) {
    let jobStatus = "";
    try {
      const api = await apiRuntime();
      // Задачи стратегий читает ТОЛЬКО strategy_status: легаси-действие
      // «status» на них отвечает 503 job_read_failed — наблюдатель 24.08
      // молотил им каждые десять секунд и не узнал даже о завершённой задаче.
      const organizationId = String(api.organizationId || "").trim().toLowerCase();
      const data = await api.generationStrategyStatus({
        action: "strategy_status",
        organization_id: organizationId,
        project_id: projectId(),
        generation_job_id: jobId,
      });
      jobStatus = String(data?.job?.status || "").trim();
    } catch {
      jobStatus = "";
    }
    const { panel } = describe(doc.querySelector("#mock-batch-form"));
    if (!panel) return;
    if (jobStatus === EXPRESS_JOB_TERMINAL_STATUSES.succeeded) {
      setStatus(
        panel,
        `Готово! Ролик за ${price} собран и сохранён в проекте: откройте вкладку «Запуски и готовые файлы» (он же — в «Материалах», kind generated_video). Можно готовить следующий запуск.`,
        "success",
      );
      return;
    }
    if (
      jobStatus === EXPRESS_JOB_TERMINAL_STATUSES.failed
      || jobStatus === EXPRESS_JOB_TERMINAL_STATUSES.cancelled
    ) {
      setStatus(
        panel,
        jobStatus === "failed"
          ? "Провайдер не смог собрать этот ролик — задача закрыта со статусом «failed», резерв денег снят или заморожен до сверки автоматически. Нажмите «Подготовить ролик» ещё раз (можно выбрать другой движок в «Чем генерируем») — материалы сохранены."
          : `Платная задача завершилась со статусом «${jobStatus}». Деньги защищены серверной сверкой: откройте «Запуски и готовые файлы», там точная причина и дальнейшие шаги.`,
        "error",
      );
      return;
    }
    if (jobStatus && jobStatus !== lastShown) {
      lastShown = jobStatus;
      setStatus(
        panel,
        `Задача за ${price} выполняется у провайдера (статус: ${jobStatus}). Это занимает несколько минут; готовый ролик сам появится в «Запусках и готовых файлах».`,
        "busy",
      );
    }
    await waitMs(EXPRESS_JOB_WATCH_INTERVAL_MS);
  }
  const { panel } = describe(doc.querySelector("#mock-batch-form"));
  if (panel) {
    setStatus(
      panel,
      "Задача ещё выполняется. Готовый ролик появится во вкладке «Запуски и готовые файлы» — панель можно закрыть, запуск не потеряется.",
      "busy",
    );
  }
}

// «Создание с нуля»: одна кнопка ведёт всю цепочку. Панель — копия «Копии»
// без блока видео; референс механики (провайдеру он не уходит) выбирается
// автоматически из роликов проекта, права проставляются единой галкой, дальше
// решает действующий мастер: подготовка ТЗ, человеческое одобрение, точная
// цена и явный платный клик — всё в «технических деталях» этой же панели.
// Платный клик «Создания»: как startExpressLaunch, но контуром очереди —
// человек уже видел точную цену на кнопке; здесь ставится мастерский чекбокс
// подтверждения и нажимается нативный submit. Любое расхождение цены мастер
// отвергнет сам (confirmation.value сверяется с ревизией очереди).
async function startStrategyPricedLaunch(initialForm, initialState) {
  const live = liveCopyLaunchContext(initialForm, initialState, null, {
    route: "strategy_video",
  });
  const { form, state } = live;
  const panel = live.panel;
  if (!form || !state || !panel) return;
  if (state.busy) {
    reportRouteBusy(state, state.busyRoute || "strategy_video");
    return;
  }
  const submit = q("#generation-submit", form);
  const confirmation = form.elements?.real_spend_confirmation;
  if (
    !(submit instanceof HTMLButtonElement)
    || !(confirmation instanceof HTMLInputElement)
    || form.dataset.generationStrategyConfirmationReady !== "true"
  ) {
    setStatus(panel, "Цена устарела — нажмите «Подготовить ролик» ещё раз.", "error");
    syncStrategyLaunchButton(form, state);
    return;
  }
  if (!confirmation.checked) confirmation.click();
  await waitMs(0);
  const liveSubmit = q("#generation-submit", form);
  if (liveSubmit instanceof HTMLButtonElement && !liveSubmit.disabled) {
    liveSubmit.click();
    setStatus(
      panel,
      "Платный запуск подтверждён. Статус появится в «Процессах», результат — в «Проверке».",
      "busy",
    );
  } else {
    setStatus(
      panel,
      String(liveSubmit?.dataset?.launchBlocker || "Мастер не принял запуск — проверьте технические детали."),
      "error",
    );
  }
  syncStrategyLaunchButton(form, state);
}

async function continueStrategyFromZero(form) {
  const state = formStates.get(form);
  const panel = panelFor(state, "strategy_video");
  if (!state || !panel) return;
  if (state.busy) {
    reportRouteBusy(state, state.busyRoute || "strategy_video");
    return;
  }
  const files = selectedProductFiles(panel);
  const selectedIds = selectedProductMediaIds(form);
  if (!files.length && !selectedIds.length) {
    setStatus(panel, "Добавьте или отметьте хотя бы одно фото товара.", "error");
    return;
  }
  const rightsBox = q('[data-generation-intake-rights="strategy_video"]', panel);
  if (!(rightsBox instanceof HTMLInputElement) || !rightsBox.checked) {
    setStatus(
      panel,
      "Поставьте единую галку прав: она разом подтверждает референс, переработку, изображения товара и согласия людей.",
      "error",
    );
    return;
  }
  applyConsolidatedRights(form, panel);
  const identity = currentProductIdentity(form);
  if (files.length && !identity) {
    // Поля живут в карточке «1. Ваш товар» — показать, довести и поставить
    // курсор. Прежняя подсказка отправляла в «технические детали», где этих
    // полей давно нет (боевой скрин 29.08: человек искал и не находил).
    const identityBlock = q("[data-generation-intake-identity]", state.shell);
    if (identityBlock instanceof HTMLElement) {
      identityBlock.hidden = false;
      ["sku", "product_name"].forEach((itemName) => {
        const item = q(
          `[data-generation-intake-identity-item="${CSS.escape(itemName)}"]`,
          identityBlock,
        );
        if (item instanceof HTMLElement) item.hidden = false;
      });
      identityBlock.scrollIntoView({ behavior: "smooth", block: "center" });
      const skuControl = q("input", identityBlock);
      if (skuControl instanceof HTMLElement) {
        skuControl.focus({ preventScroll: true });
      }
    }
    setStatus(
      panel,
      "Заполните артикул и название товара — поля открылись в карточке «1. Ваш товар», над категорией.",
      "error",
    );
    return;
  }
  try {
    if (files.length) {
      setStatus(panel, "Загружаем фото товара…", "busy");
      for (const file of files) {
        await assertImage(file);
        const mediaId = await uploadProjectMedia(file, "product_photo", identity);
        ensureProductCheckbox(form, state, mediaId, identity, file.name);
        const box = q(`input[name="media_id"][value="${CSS.escape(mediaId)}"]`, form);
        if (box instanceof HTMLInputElement && !box.checked) {
          box.checked = true;
          box.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
      pendingCopyProductFiles.delete(projectId());
      const fileInput = q('input[data-generation-intake-image="product"]', panel);
      if (fileInput instanceof HTMLInputElement) fileInput.value = "";
      refreshProductSelectionCount(form, state);
    }
    const toggles = qa("input[data-generation-strategy-source-toggle]", form);
    if (toggles.length && !toggles.some((input) => input.checked)) {
      toggles.find((input) => !input.disabled)?.click();
    }
    // Дальше — ровно копийный бесплатный цикл: драйвер сам жмёт подготовку
    // ТЗ, одобряет версии, снимает бесплатный preflight и возвращает точную
    // цену. Провайдер не вызывается, деньги не списываются.
    setStatus(panel, "Бесплатная проверка: ТЗ, одобрение и точная цена…", "busy");
    beginRouteBusy(
      state,
      "strategy_video",
      "generation-intake-continue-strategy",
      "Готовим точное ТЗ и цену…",
    );
    try {
      const price = await driveStrategyPreflight(form, panel, {
        freePhases: REBUILD_FREE_SUBMIT_PHASES,
        requireSourceDuration: false,
        strategyId: STRATEGY_AUTHORITY_STRATEGY,
        routeKey: "strategy_video",
        busyAction: "generation-intake-continue-strategy",
      });
      const live = liveCopyLaunchContext(form, state, panel, {
        route: "strategy_video",
      });
      if (live.state) syncStrategyLaunchButton(live.form, live.state);
      setStatus(
        live.panel || panel,
        price
          ? `Точная цена: ${price}. Деньги не списаны — кнопка «Запустить» и есть подтверждение.`
          : "Бесплатная проверка завершена. Проверьте технические детали ниже.",
        price ? "ready" : "neutral",
      );
    } finally {
      const live = liveCopyLaunchContext(form, state, panel, {
        route: "strategy_video",
      });
      if (live.state) finishRouteBusy(live.state);
      if (state !== live.state) finishRouteBusy(state);
    }
  } catch (error) {
    // Сырой машинный код в статусе («express_preflight_blocked» без причины,
    // боевой скрин 29.08) — не ответ человеку: причина лежит в error.blocker
    // и обязана печататься рядом с кодом.
    const fromZeroMessages = {
      express_preflight_blocked: `Мастер заблокирован: ${
        error?.blocker || "причина не названа"
      } Ничего не запущено и не оплачено.`,
      express_preflight_stalled: `Мастер не отвечает${
        error?.step ? `: шаг «${error.step}» не сдвигается` : ""
      }.${
        error?.invalidFields?.length
          ? ` Форму держит незаполненное поле: ${error.invalidFields.join(", ")}.`
          : ""
      } Ничего не запущено и не оплачено.`,
      express_preflight_rejected: `Сервер отказал на шаге «${
        error?.step || "бесплатная проверка"
      }»: ${error?.serverMessage || ""} Ничего не запущено и не оплачено.`,
      express_preflight_timeout:
        "Бесплатная проверка не завершилась за отведённое время. Ничего не списано — нажмите «Подготовить ролик» ещё раз.",
      express_attestations_unavailable:
        "Нативные подтверждения прав не подключились. Обновите страницу (F5) и повторите подготовку.",
    };
    setStatus(
      panel,
      fromZeroMessages[error?.message]
        || (error instanceof Error && error.message
          ? error.message
          : "Не удалось продолжить. Попробуйте ещё раз."),
      "error",
    );
  }
}

async function prepareCopy(form) {
  const state = formStates.get(form);
  let route = state?.routes.copy_video;
  const panel = panelFor(state, "copy_video");
  if (!state || !route || !panel) return;
  if (state.busy) {
    reportRouteBusy(state, "copy_video");
    return;
  }
  // Эти ссылки обновляются после каждого async-этапа, который может заменить
  // #mock-batch-form. До handoff они совпадают с исходными; после него только
  // active* разрешено менять видимую shell и её двухфазную кнопку.
  let activeForm = form;
  let activeState = state;
  let activePanel = panel;
  if (
    !route.sourceFile
    && !route.sourceMediaId
    && (selectedFile(panel) || selectedExistingVideo(panel))
  ) {
    // Авто-разбор встроен в «Показать цену»: отдельный клик «Разобрать MP4»
    // не обязателен — бесплатная проверка нового MP4 выполняется здесь же.
    await analyzeRoute(form, "copy_video");
    route = state.routes.copy_video;
    if (!route.sourceFile && !route.sourceMediaId) return;
  }
  const existingProductMediaIds = selectedProductMediaIds(form);
  const productFiles = selectedProductFiles(panel);
  const productCount = existingProductMediaIds.length + productFiles.length;
  const recommendation = currentRecommendation(form);
  const audio = currentAudio(panel);
  const rights = q('[data-generation-intake-rights="copy_video"]', panel)?.checked === true;
  const productIdentity = currentProductIdentity(form);
  if (productCount < MIN_PRODUCT_IMAGES || productCount > MAX_PRODUCT_IMAGES) {
    setStatus(
      panel,
      productCount > MAX_PRODUCT_IMAGES
        ? `Выбрано слишком много: ${productCount}. Максимум ${MAX_PRODUCT_IMAGES} — снимите галочки с готовых фото или очистите поле загрузки файлов, и счётчик придёт в норму.`
        : `Нужно выбрать от ${MIN_PRODUCT_IMAGES} до ${MAX_PRODUCT_IMAGES} фотографий одного товара. Сейчас: ${productCount}.`,
      "error",
    );
    return;
  }
  const skuConflict = productSkuConflict(form);
  if (skuConflict) {
    setStatus(
      panel,
      `Выбраны фото разных товаров. Оставьте один SKU (${skuConflict.keep}) и снимите фото: ${skuConflict.removeLabels.join(", ")} (SKU ${skuConflict.removeSkus.join(", ")}).`,
      "error",
    );
    return;
  }
  if (!rights) {
    setStatus(
      panel,
      "Поставьте единую галку прав: она разом подтверждает референс, переработку, изображения товара и согласия людей в кадре.",
      "error",
    );
    return;
  }
  if (!recommendation) {
    setStatus(panel, "Добавьте инструкцию или явно вставьте базовый шаблон.", "error");
    return;
  }
  if (recommendation.length > BRIEF_LIMIT) {
    setStatus(panel, `Сократите инструкцию до ${BRIEF_LIMIT} символов. Текст не был обрезан.`, "error");
    return;
  }
  if (audio === null) {
    setStatus(panel, "Явно выберите: со звуком или без звука.", "error");
    return;
  }
  if (productFiles.length && !productIdentity) {
    setStatus(
      panel,
      "Для новых фотографий товара нужны точные артикул и название текущего товара. Заполните поля «Артикул (SKU) вашего товара» и «Название товара» в этой форме.",
      "error",
    );
    return;
  }
  // Категория товара уходит в серверное ТЗ (правила безопасности и допустимые
  // обещания) и у нативной формы обязательна. Без неё мастер молча не проходил
  // reportValidity() и через 12 нажатий сдавался с «мастер не отвечает».
  // Спрашиваем здесь и вслух — до загрузки файлов.
  if (!currentProductCategory(form, state)) {
    revealIdentityCategory(state);
    setStatus(
      panel,
      "Выберите «Категория товара» в этой форме: она нужна серверному ТЗ (правила безопасности для косметики, БАД, еды и т. д.).",
      "error",
    );
    identityInput(state, "product_category")?.focus?.({ preventScroll: true });
    return;
  }
  beginRouteBusy(
    state,
    "copy_video",
    "generation-intake-prepare-copy",
    "Проверяем фотографии, загружаем MP4 и готовим кадр исходного товара…",
  );
  try {
    const fileHashes = [];
    for (const file of productFiles) {
      await assertImage(file);
      fileHashes.push(await sha256Hex(file));
    }
    if (new Set(fileHashes).size !== fileHashes.length) {
      throw new Error("duplicate_product_images");
    }
    const sourceMediaId = await ensureSourceMedia(route);
    const uploadedProductMediaIds = [];
    for (let index = 0; index < productFiles.length; index += 1) {
      setStatus(
        panel,
        `Загружаем фото товара ${index + 1} из ${productFiles.length}…`,
        "busy",
      );
      uploadedProductMediaIds.push(await uploadProjectMedia(
        productFiles[index],
        "product_photo",
        productIdentity,
      ));
    }
    uploadedProductMediaIds.forEach((mediaId, index) => {
      const registered = ensureProductCheckbox(
        form,
        state,
        mediaId,
        productIdentity,
        productFiles[index]?.name,
      );
      attachProductFilePreview(registered, productFiles[index]);
    });
    if (uploadedProductMediaIds.length) {
      pendingCopyProductFiles.delete(projectId());
      const productInput = q('input[data-generation-intake-image="product"]', panel);
      if (productInput instanceof HTMLInputElement) productInput.value = "";
      persistCopyPhotoSelection(form);
      refreshProductSelectionCount(form, state);
    }
    const productMediaIds = [
      ...existingProductMediaIds,
      ...uploadedProductMediaIds,
    ];
    // Лестница кадра исходного товара: (1) уже выбранный в мастере uuid,
    // (2) кадр локального разбора, (3) первый готовый кадр проекта из
    // нативного селекта, (4) серверный разбор скачанного MP4. Только если всё
    // мимо — честное сообщение с одной конкретной инструкцией.
    let originalProductMediaId = wizardOriginalProductMediaId(form);
    // Кадр, приложенный человеком, идёт сразу за выбором мастера: он точнее
    // любой автоматики и остаётся единственным доступным там, где браузерный
    // декодер молчит и обе автоматические ветки ниже заведомо пусты.
    if (!originalProductMediaId && route.originalFrameMediaId) {
      originalProductMediaId = route.originalFrameMediaId;
    }
    if (
      !originalProductMediaId
      && route.storyboard
      && Number.isInteger(route.selectedFrameIndex)
    ) {
      const frame = route.storyboard.frames.find((item) => item.index === route.selectedFrameIndex);
      if (frame) {
        originalProductMediaId = await uploadProjectMedia(
          frameAsFile(frame, "copy"),
          "creator_reference",
        );
      }
    }
    if (!originalProductMediaId) {
      originalProductMediaId = adoptExistingOriginalProductFrame(form, panel);
    }
    if (!originalProductMediaId && route.sourceMediaId) {
      try {
        route = await serverStoryboardForCopy(state, panel, route.sourceMediaId);
        const frame = route.storyboard?.frames.find(
          (item) => item.index === route.selectedFrameIndex,
        );
        if (frame) {
          originalProductMediaId = await uploadProjectMedia(
            frameAsFile(frame, "copy"),
            "creator_reference",
          );
        }
      } catch (frameError) {
        console.warn("Server frame analysis for copy failed", frameError);
      }
    }
    if (
      originalProductMediaId
      && !(route.storyboard && Number.isInteger(route.selectedFrameIndex))
    ) {
      noteChosenFrame(form, panel, originalProductMediaId);
    }
    const sourceDurationSeconds = verifiedSourceDurationSeconds(form);
    const assets = [
      {
        role: "source_video",
        media_id: sourceMediaId,
        ...(sourceDurationSeconds === null
          ? {}
          : { duration_seconds: sourceDurationSeconds }),
      },
      ...(originalProductMediaId
        ? [{ role: "original_product_image", media_id: originalProductMediaId }]
        : []),
      ...productMediaIds.map((mediaId) => ({
        role: "new_product_image",
        media_id: mediaId,
      })),
    ];
    const handoff = {
      version: HANDOFF_VERSION,
      route: "copy_video",
      paid_authority: PAID_AUTHORITY,
      strategy_id: COPY_AUTHORITY_STRATEGY,
      source_media_id: sourceMediaId,
      source_duration_seconds: sourceDurationSeconds,
      original_product_media_id: originalProductMediaId,
      product_media_ids: productMediaIds,
      reference_media_ids: [],
      source_url: currentSourceUrl(panel),
      description: recommendation,
      recommendation_source: recommendationSource(form),
      requested_model: currentRequestedModel(panel),
      audio,
      preserve: selectedPreserveCodes(panel),
      replace: ["product"],
      assets,
      launch_enabled: Boolean(originalProductMediaId),
    };
    persistHandoff(form, handoff);
    const launch = await openNativeLaunch(activeForm, handoff);
    activeForm = launch.form;
    activeState = launch.state;
    activePanel = launch.panel;
    if (!activeState || !activePanel) {
      throw new Error("express_live_context_missing");
    }
    const missingRoles = launch.missingRoles;
    const missingLabels = [...new Set(missingRoles || [])]
      .map((role) => ASSET_ROLE_LABELS[role] || role);
    if (missingLabels.length) {
      setStatus(
        activePanel,
        `Материалы загружены, но не привязались автоматически: ${missingLabels.join(", ")}. Отметьте их вручную в шаге «Исходники» — без этого запуск заблокирован.`,
        "warning",
      );
      return;
    }
    if (!originalProductMediaId) {
      // Прежний совет «загрузите локальный MP4» отправлял человека делать то,
      // что он только что сделал: обе автоматические ветки идут через один и
      // тот же декодер, и повтор загрузки их не оживляет. Открываем ручной
      // кадр и говорим про него прямо.
      const frameSlot = q("[data-generation-intake-original-frame]", activePanel);
      if (frameSlot instanceof HTMLElement) frameSlot.hidden = false;
      setStatus(
        activePanel,
        "Браузер не смог собрать кадр исходного товара — ни из выбранного файла, ни из ролика проекта. Приложите стоп-кадр сами в блоке «Кадр исходного товара» под исходником, и подготовка дойдёт до цены.",
        "warning",
      );
      return;
    }
    setStatus(
      activePanel,
      "Материалы привязаны. Бесплатно получаем точную серверную цену — провайдер не запускается и деньги не списываются…",
      "busy",
    );
    const price = await driveStrategyPreflight(activeForm, activePanel);
    // Мастер мог быть перерисован за время бесплатной проверки: подпись
    // списания, state, панель и кампания читаются из одного живого контекста,
    // а не из смеси нового DOM и отсоединённой compact-shell.
    const pricedContext = liveCopyLaunchContext(
      activeForm,
      activeState,
      activePanel,
      { busy: true },
    );
    if (!pricedContext.state || !pricedContext.panel) {
      throw new Error("express_live_context_missing");
    }
    activeForm = pricedContext.form;
    activeState = pricedContext.state;
    activePanel = pricedContext.panel;
    const spendConfirmation = String(
      activeForm.elements?.real_spend_confirmation?.value || "",
    );
    const campaignId = autoSelectCampaign(
      activeForm,
      activePanel,
      activeState,
    );
    if (!price) {
      setExpressPricePhase(activeState, "", "");
      setStatus(
        activePanel,
        "Сервер подтвердил готовность, но цена не отобразилась. Проверьте цену в мастере ниже перед запуском.",
        "warning",
        { expressPriceResult: "price_missing" },
      );
    } else if (!campaignId) {
      // A server token without its exact campaign is not reusable authority.
      // Keep the informational price visible, but discard compact price/token
      // and the native confirmation until a campaign is chosen and re-priced.
      setExpressPricePhase(activeState, "", "");
      clearSpendConfirmation(activeForm, { notify: false });
      setStatus(
        activePanel,
        `Точная цена: ${price}, деньги не списаны. Выбранная кампания недоступна или не выбрана: выберите активную выше и заново получите цену.`,
        "warning",
        { expressPriceResult: "campaign_missing" },
      );
    } else {
      setExpressPricePhase(
        activeState,
        price,
        spendConfirmation,
        campaignId,
      );
      setStatus(
        activePanel,
        `Точная цена: ${price}. Деньги не списаны. Кнопка «Запустить за ${price}» и есть подтверждение цены — запуск случится только после вашего клика.`,
        "success",
        { expressPriceResult: "priced" },
      );
    }
  } catch (error) {
    console.warn("Copy Product Swap preparation failed", error);
    // Ошибка тоже должна появиться на текущей shell. Если replacement успел
    // случиться между последним await и catch, забираем его state/panel сейчас.
    const failureContext = liveCopyLaunchContext(
      activeForm,
      activeState,
      activePanel,
      { busy: true },
    );
    if (failureContext.state && failureContext.panel) {
      activeForm = failureContext.form;
      activeState = failureContext.state;
      activePanel = failureContext.panel;
    }
    if (error?.message === "express_attestations_unavailable") {
      const labels = (error.missingAttestations || [])
        .map((id) => COPY_ATTESTATION_LABELS[id] || id);
      setStatus(
        activePanel,
        `Не удалось автоматически проставить подтверждения прав: ${labels.join(", ")}. Отметьте их вручную в шаге «Исходники» — без них запуск честно заблокирован.`,
        "error",
      );
      return;
    }
    if (error?.message === "express_preflight_blocked") {
      setStatus(
        activePanel,
        `Бесплатная проверка остановилась: ${error.blocker || "мастер сообщил о блокировке"} Деньги не списаны.`,
        "error",
      );
      return;
    }
    if (error?.message === "express_preflight_timeout") {
      setStatus(
        activePanel,
        "Сервер долго готовит цену. Ничего не списано; нажмите «Показать цену» ещё раз.",
        "error",
      );
      return;
    }
    if (error?.message === "express_preflight_rejected") {
      setStatus(
        activePanel,
        `Сервер отказал на шаге «${error.step || "бесплатная проверка"}»: ${error.serverMessage} Ничего не запущено и не оплачено. Устраните причину и нажмите «Подготовить ролик» ещё раз — выбранные материалы сохранены.`,
        "error",
      );
      return;
    }
    if (error?.message === "express_preflight_stalled") {
      setStatus(
        activePanel,
        `Мастер не отвечает на бесплатную проверку${error.step ? `: шаг «${error.step}» не сдвигается` : ""}.${
          error.invalidFields?.length
            ? ` Форму держит незаполненное поле: ${error.invalidFields.join(", ")}.`
            : ""
        } Ничего не запущено и не оплачено. Заполните поле и нажмите «Подготовить ролик» ещё раз — материалы сохранены.`,
        "error",
      );
      return;
    }
    if (error?.message === "express_submit_missing") {
      setStatus(
        activePanel,
        "Кнопка запуска мастера не найдена на странице. Ничего не запущено и не оплачено. Обновите страницу (F5) и повторите подготовку.",
        "error",
      );
      return;
    }
    const messages = {
      duplicate_product_images: "Удалите повторяющиеся фотографии товара: нужны разные ракурсы.",
      image_required: "Выберите корректные фотографии товара.",
      image_too_large: "Одна из фотографий больше 16 МБ.",
      image_type_invalid: "Поддерживаются только JPG, PNG и WEBP.",
      image_signature_invalid: "Расширение одной из фотографий не совпадает с её содержимым.",
      image_dimensions_too_small: "Фотография должна быть не меньше 256×256 пикселей.",
      source_media_required: "Сначала выберите и разберите исходный MP4.",
      express_live_context_missing: "Форма обновилась во время подготовки. Ничего не запущено и не оплачено; нажмите «Подготовить ролик» ещё раз — выбранные материалы сохранены.",
      express_native_handoff_unstable: "Форма продолжила обновляться во время привязки материалов. Ничего не запущено и не оплачено; выбранные материалы сохранены — нажмите «Подготовить ролик» ещё раз.",
      express_source_duration_unavailable: "Нативная форма не приняла серверную длительность исходника. Ничего не запущено и не оплачено; обновите страницу и повторите подготовку.",
      express_source_duration_incompatible: "Длительность исходника не входит в допустимый диапазон выбранной модели. Ничего не запущено и не оплачено; выберите другую модель или укоротите ролик.",
      express_source_duration_unverified: "Сервер ещё не подтвердил длительность выбранного MP4. Ничего не запущено и не оплачено; повторите бесплатную подготовку.",
    };
    setStatus(
      activePanel,
      error?.message === "media_kind_mime_mismatch"
        ? mediaKindMimeMismatchMessage(error)
        : messages[error?.message] || "Не удалось подготовить материалы. Ничего не запущено и не оплачено.",
      "error",
    );
  } finally {
    // Снимаем lock и с исходной shell, и с принятой replacement-shell. Ещё
    // один render мог произойти уже после catch, поэтому проверяем live state
    // последний раз; фазу/цену это не сбрасывает.
    finishRouteBusy(state);
    finishRouteBusy(activeState);
    const finalContext = liveCopyLaunchContext(
      activeForm,
      activeState,
      activePanel,
    );
    finishRouteBusy(finalContext.state);
  }
}

async function prepareAvatar(form) {
  const state = formStates.get(form);
  const route = state?.routes.avatar_video;
  const panel = panelFor(state, "avatar_video");
  if (!state || !route || !panel) return;
  if (state.busy) {
    reportRouteBusy(state, "avatar_video");
    return;
  }
  // С 23.08.2026 у «Дуэта» нет фото и описания аватара: ведущий — это
  // зарегистрированная личность проекта, а его внешность живёт у провайдера.
  const avatarWishes = "";
  const avatarFile = null;
  const existingAvatarMediaId = "";
  const mode = "presenter";
  const recommendation = currentRecommendation(form);
  const rights = q('[data-generation-intake-rights="avatar_video"]', panel)?.checked === true;
  if (!duetPresenterIdFromForm(state)) {
    setStatus(panel, "Выберите ведущего проекта — или заведите его ниже, из каталога HeyGen.", "error");
    return;
  }
  if (!rights) {
    setStatus(panel, "Подтвердите право использовать исходный ролик.", "error");
    return;
  }
  if (!recommendation) {
    setStatus(panel, "Добавьте инструкцию или явно вставьте базовый шаблон.", "error");
    return;
  }
  if (recommendation.length > BRIEF_LIMIT) {
    setStatus(panel, `Сократите инструкцию до ${BRIEF_LIMIT} символов. Текст не был обрезан.`, "error");
    return;
  }
  const speech = duetSpeechLimit(state);
  if (speech && recommendation.length > speech.limit) {
    setStatus(
      panel,
      `Речь ведущего длиннее ролика: ${recommendation.length} знаков, а ролик ${speech.seconds} с вмещает около ${speech.limit} (≈15 знаков в секунду). Сократите текст — он произносится вслух за деньги.`,
      "error",
    );
    form.elements?.brief?.focus?.({ preventScroll: true });
    return;
  }
  // Товар называется отдельно и угадыванию не подлежит: подставленный «первый
  // попавшийся» списал бы деньги в чужой бюджет, и заметили бы это при сверке.
  if (!duetProductIdFromForm(state)) {
    setStatus(
      panel,
      "Выберите товар, для которого делаете дуэт: по нему считаются бюджет и архив.",
      "error",
    );
    return;
  }
  const mechanicsProblem = duetMechanicsProblem(state);
  if (mechanicsProblem) {
    setStatus(panel, `Разбор ролика для речи ведущего: ${mechanicsProblem}`, "error");
    return;
  }
  // Категория обязательна контракту ТЗ (request.product_category) и нужна
  // AI-проверке; без неё сервер отверг бы подготовку — спрашиваем до неё.
  const duetCategory = q("[data-generation-intake-duet-category]", panel);
  if (duetCategory instanceof HTMLSelectElement && duetCategory.value) {
    const nativeCategory = form.elements?.product_category;
    if (nativeCategory instanceof HTMLSelectElement && nativeCategory.value !== duetCategory.value) {
      assignPaidContextValue(nativeCategory, duetCategory.value);
    }
  }
  if (!cleanText(form.elements?.product_category?.value, 64)) {
    setStatus(
      panel,
      "Выберите категорию товара (поле под списком товаров): она уходит в ТЗ и AI-проверку готового ролика.",
      "error",
    );
    duetCategory?.focus?.({ preventScroll: false });
    return;
  }
  const duetMechanics = duetMechanicsFromForm(state);
  beginRouteBusy(
    state,
    "avatar_video",
    "generation-intake-prepare-avatar",
    "Проверяем материалы дуэта и сохраняем подготовку…",
  );
  try {
    const sourceMediaId = await ensureSourceMedia(route);
    // Фото аватара у «Дуэта» нет: личность живёт у провайдера.
    const avatarMediaId = existingAvatarMediaId;
    const handoff = {
      version: HANDOFF_VERSION,
      route: "avatar_video",
      paid_authority: PAID_AUTHORITY,
      // Настоящий идентификатор стратегии вместо выдуманного. До 22.08.2026
      // здесь стояло "character_performance" — значение, которого нет в реестре
      // стратегий базы: форма собирала данные, писала их в скрытые поля и
      // рапортовала успех, ни разу не обратившись к серверу.
      strategy_id: AVATAR_AUTHORITY_STRATEGY,
      source_media_id: sourceMediaId,
      original_product_media_id: "",
      avatar_media_id: avatarMediaId,
      avatar_mode: mode,
      // Ведущий и раскладка врезки. В наряд уходит НАШ идентификатор ведущего:
      // личность у провайдера живёт на сервере и в браузер не приходит вовсе,
      // поэтому подменить, кто будет говорить в оплаченном ролике, отсюда
      // нельзя. Раскладка читается из формы, а не из записи ведущего: оператор
      // мог переопределить её для этого ролика.
      duet_presenter_id: duetPresenterIdFromForm(state),
      duet_layout: duetLayoutFromForm(state),
      // Звук дуэта — речь ведущего у провайдера; отдельной озвучки результата
      // нет, и цена маршрута считается с audio=false. Контракт выбора требует
      // явный boolean, иначе мастер молчит на «Заполните ассеты».
      audio: false,
      // Товар, под которым оформляется запуск. У дуэта его не из чего вывести:
      // фотографий товара в нём нет. Без товара запуск выпал бы и из бюджета,
      // и из архива по товару — деньги ушли бы мимо учёта.
      product_id: duetProductIdFromForm(state),
      product_media_ids: [],
      reference_media_ids: avatarMediaId ? [avatarMediaId] : [],
      source_url: currentSourceUrl(panel),
      description: recommendation,
      recommendation_source: recommendationSource(form),
      avatar_wishes: avatarWishes,
      assets: [
        { role: "source_video", media_id: sourceMediaId },
        ...(avatarMediaId
          ? [{ role: "avatar_image", media_id: avatarMediaId }]
          : []),
      ],
      provider_feature_flag: CHARACTER_PERFORMANCE_FEATURE,
      // Платный старт закрыт не этим полем, а тем, что все маршруты «Аватара» в
      // реестре выключены: серверная политика не находит действующего маршрута
      // и отвечает блокером provider_route_not_allowed, а расчёт готовности в
      // браузере по той же причине держит модуль заблокированным. Поле осталось
      // как честная отметка «этот handoff не про запуск».
      // Запуск открыт ровно тогда, когда выбран ведущий: без него сервер
      // отвергнет привязку, а маршрут дуэта с 23.08.2026 включён.
      launch_enabled: Boolean(duetPresenterIdFromForm(state)),
    };
    persistHandoff(form, handoff);
    // Дальше — тот же путь, что у «Копии»: подготовка доходит до сервера, а не
    // заканчивается зелёной надписью над скрытыми полями. Провайдера здесь не
    // вызывают и денег не тратят: это бесплатная привязка ассетов и подготовка
    // ТЗ, после которой человек отдельно нажмёт «Показать цену».
    const launch = await openNativeLaunch(form, handoff);
    let activeForm = launch.form;
    let activeState = launch.state;
    let activePanel = launch.panel;
    if (!activeState || !activePanel) throw new Error("express_live_context_missing");
    const missingLabels = [...new Set(launch.missingRoles || [])]
      .map((role) => ASSET_ROLE_LABELS[role] || role);
    if (missingLabels.length) {
      setStatus(
        activePanel,
        `Материалы загружены, но не привязались автоматически: ${missingLabels.join(", ")}. Отметьте их вручную в шаге «Исходники» — без этого запуск заблокирован.`,
        "warning",
      );
      return;
    }
    // Разбор ролика становится черновиком механики привязанного исходника:
    // его прочитают ТЗ (mechanics_summary) и нативные textarea мастера.
    const mechanicsApplied = window.ContentEngineGenerationGuidedV4
      ?.setStrategyMechanicsDraft?.(activeForm, sourceMediaId, duetMechanics);
    if (mechanicsApplied !== true) throw new Error("express_mechanics_unbound");
    // Кампания бесплатным шагам не нужна (выключенное поле не валидируется);
    // она подбирается и проверяется на шаге цены, как у «Копии». Здесь только
    // подтягиваем умолчание в зеркало «Кампания и бюджет», не блокируя путь.
    autoSelectCampaign(activeForm, activePanel, activeState);
    // Дальше — ровно путь «Копии»: бесплатные шаги мастера (проверка MP4,
    // точное ТЗ, одобрение, проверка сервиса и цены) проходят отсюда, и кнопка
    // панели становится «Запустить за $X». Провайдер не вызывается, деньги не
    // списываются до явного клика человека.
    setStatus(
      activePanel,
      "Исходник, товар и ведущий привязаны. Бесплатно получаем точную серверную цену — провайдер не запускается и деньги не списываются…",
      "busy",
    );
    const price = await driveStrategyPreflight(activeForm, activePanel);
    const pricedContext = liveCopyLaunchContext(
      activeForm,
      activeState,
      activePanel,
      { busy: true },
    );
    if (!pricedContext.state || !pricedContext.panel) {
      throw new Error("express_live_context_missing");
    }
    activeForm = pricedContext.form;
    activeState = pricedContext.state;
    activePanel = pricedContext.panel;
    const spendConfirmation = String(
      activeForm.elements?.real_spend_confirmation?.value || "",
    );
    const campaignId = autoSelectCampaign(activeForm, activePanel, activeState);
    if (!price) {
      setExpressPricePhase(activeState, "", "");
      setStatus(
        activePanel,
        "Сервер подтвердил готовность, но цена не отобразилась. Нажмите «Подготовить дуэт» ещё раз — это бесплатно.",
        "warning",
        { expressPriceResult: "price_missing" },
      );
    } else if (!campaignId) {
      setExpressPricePhase(activeState, "", "");
      clearSpendConfirmation(activeForm, { notify: false });
      setStatus(
        activePanel,
        `Точная цена: ${price}, деньги не списаны. Выбранная кампания недоступна или не выбрана: выберите активную выше и заново получите цену.`,
        "warning",
        { expressPriceResult: "campaign_missing" },
      );
    } else {
      setExpressPricePhase(activeState, price, spendConfirmation, campaignId);
      setStatus(
        activePanel,
        `Точная цена: ${price}. Деньги не списаны. Кнопка «Запустить за ${price}» и есть подтверждение цены — запуск случится только после вашего клика.`,
        "success",
        { expressPriceResult: "priced" },
      );
    }
  } catch (error) {
    console.warn("Avatar preparation failed", error);
    const failureContext = liveCopyLaunchContext(form, state, panel);
    const failurePanel = failureContext.panel || panel;
    if (failureContext.state) setExpressPricePhase(failureContext.state, "", "");
    const messages = {
      source_media_required: "Сначала выберите и разберите исходный MP4.",
      express_preflight_rejected: `Сервер отказал на шаге «${error?.step || "бесплатная проверка"}»: ${error?.serverMessage || ""} Ничего не запущено и не оплачено. Устраните причину и нажмите «Подготовить дуэт» ещё раз.`,
      express_preflight_stalled: `Мастер не отвечает на бесплатную проверку${error?.step ? `: шаг «${error.step}» не сдвигается` : ""}.${
        error?.invalidFields?.length
          ? ` Форму держит незаполненное поле: ${error.invalidFields.join(", ")}.`
          : ""
      } Ничего не запущено и не оплачено. Заполните поле и нажмите «Подготовить дуэт» ещё раз — материалы сохранены.`,
      express_preflight_blocked: `Мастер заблокирован: ${error?.blocker || "причина не названа"}. Ничего не запущено и не оплачено.`,
      express_source_duration_incompatible: "Длительность исходника не подходит выбранному движку. Выберите другой MP4 или движок.",
      express_attestations_unavailable: "Нативные подтверждения прав не подключились. Обновите страницу (F5) и повторите подготовку.",
      express_preflight_timeout: "Бесплатная проверка не завершилась за отведённое время. Ничего не запущено и не оплачено. Повторите подготовку.",
      express_mechanics_unbound: "Разбор ролика не передался мастеру. Обновите страницу (F5) и повторите подготовку — материалы сохранены.",
    };
    setStatus(
      failurePanel,
      error?.message === "media_kind_mime_mismatch"
        ? mediaKindMimeMismatchMessage(error)
        : messages[error?.message] || "Не удалось сохранить подготовку дуэта. Ничего не запущено и не оплачено.",
      "error",
    );
  } finally {
    // Handoff и бесплатная проверка могли заменить shell: снимаем busy и с
    // исходного state, и с живого — иначе новая панель осталась бы запертой.
    finishRouteBusy(state);
    const finalContext = liveCopyLaunchContext(form, state, panel);
    finishRouteBusy(finalContext.state);
    if (finalContext.state) syncExpressPriceButton(finalContext.state);
  }
}

async function uploadStrategySources(form) {
  const state = formStates.get(form);
  const panel = panelFor(state, "strategy_video");
  const input = q('input[data-generation-intake-mp4="strategy"]', panel);
  const files = [...(input?.files || [])];
  if (!state || !panel) return;
  if (state.busy) {
    reportRouteBusy(state, "strategy_video");
    return;
  }
  if (!files.length) {
    setStatus(panel, "Выберите один или несколько MP4.", "error");
    return;
  }
  if (files.length > MAX_STRATEGY_FILES) {
    setStatus(panel, `Можно добавить не больше ${MAX_STRATEGY_FILES} MP4 за один раз.`, "error");
    return;
  }
  beginRouteBusy(
    state,
    "strategy_video",
    "generation-intake-upload-strategy",
    `Готовим к загрузке ${files.length} MP4…`,
  );
  const mediaIds = [];
  try {
    for (let index = 0; index < files.length; index += 1) {
      setStatus(panel, `Проверяем и загружаем ${index + 1} из ${files.length}…`, "busy");
      await assertMp4(files[index], 120);
      mediaIds.push(await uploadProjectMedia(files[index], "source_video"));
    }
    const handoff = {
      version: HANDOFF_VERSION,
      route: "strategy_video",
      paid_authority: PAID_AUTHORITY,
      source_media_id: mediaIds[0] || "",
      original_product_media_id: "",
      product_media_ids: [],
      reference_media_ids: mediaIds,
      source_url: "",
      description: "",
      assets: mediaIds.map((mediaId) => ({ role: "source_video", media_id: mediaId })),
      launch_enabled: false,
    };
    persistHandoff(form, handoff);
    await window.ContentEngineGenerationGuidedV4
      ?.refreshStrategyAssets?.(form);
    mediaIds.forEach((mediaId) => {
      bindRoleAsset(form, "source_video", mediaId);
    });
    setStatus(
      panel,
      `${mediaIds.length} MP4 добавлено в проект и отмечено как исходники. Стратегия не выбрана: выберите подходящий маршрут вручную в полном конструкторе, затем пройдите бесплатную проверку длительности.`,
      "success",
    );
    input.value = "";
    q('[data-ce-v4-generation-target="media"]', form)?.click?.();
    refreshVideoSelects(form, state);
  } catch (error) {
    console.warn("Strategy MP4 upload failed", error);
    setStatus(
      panel,
      error?.message === "media_kind_mime_mismatch"
        ? mediaKindMimeMismatchMessage(error)
        : "Загрузка остановлена. Уже добавленные исходники остаются в проекте; платный запуск не выполнялся.",
      "error",
    );
  } finally {
    finishRouteBusy(state);
  }
}

// «Дуэт» выведен из витрины (03.09): единственный маршрут heygen выключен в
// реестре, сервер платный старт не подпишет. Форма обязана говорить это ДО
// подготовки, а не отказом после неё. Гейт срабатывает только на явном
// «маршруты отданы и все выключены»: пустой или не загруженный реестр не
// блокирует (правило guided-слоя — отсутствие реестра не приговор).
function duetRoutesAllDisabled() {
  const raw = guidedEngineRoutes("avatar_video");
  const routes = raw.length ? raw : engineRouteCache("avatar_video").routes;
  return Array.isArray(routes)
    && routes.length > 0
    && !routes.some((route) => route?.enabled === true);
}

function syncDuetAvailabilityGate(state) {
  const panel = state.shell?.querySelector?.(
    '[data-generation-intake-panel="avatar_video"]',
  );
  if (!panel) return;
  if (!guidedEngineRoutes("avatar_video").length
    && engineRouteCache("avatar_video").status === "idle") {
    ensureEngineRoutes("avatar_video").then(() => {
      if (panel.isConnected) syncDuetAvailabilityGate(state);
    });
  }
  const gated = duetRoutesAllDisabled();
  let note = panel.querySelector("[data-duet-route-gate]");
  if (gated && !note) {
    note = el("div", "generation-intake-v4__gate-note");
    note.dataset.duetRouteGate = "true";
    note.append(
      el("strong", "", "Формат «Дуэт» в подготовке. "),
      el(
        "span",
        "",
        "Маршрут генерации выключен: формат не прошёл боевую перепроверку "
          + "после обновления интеграции. «Копия» и «Создание» работают в "
          + "обычном режиме.",
      ),
    );
    panel.prepend(note);
  } else if (!gated && note) {
    note.remove();
  }
  // При гейте кнопки глушатся принудительно; без гейта их состоянием
  // управляет собственная логика формы (prepare и так disabled до цены).
  if (gated) {
    ["generation-intake-analyze-avatar", "generation-intake-prepare-avatar"]
      .forEach((action) => {
        const control = panel.querySelector(`[data-action="${action}"]`);
        if (control) control.disabled = true;
      });
  }
}

function setRoute(form, state, route) {
  if (!DEFAULT_BRIEF_TEMPLATES[route] && route !== "strategy_video") return;
  if (state.busy && state.busyRoute && state.busyRoute !== route) {
    reportRouteBusy(state, state.busyRoute);
    return;
  }
  if (state.briefDraftReady === false) {
    // initialRouteBriefDrafts уже принял решение, какому маршруту принадлежит
    // значение нового DOM. Не перетираем сохранённый черновик stale-значением
    // формы, которую app.js только что пересоздал.
    state.briefDraftReady = true;
  } else {
    captureBriefDraft(form, state, state.briefRoute || state.route);
  }
  // Цена и одноразовое подтверждение принадлежат маршруту, на котором их
  // получили: смена панели их снимает, чтобы «Дуэт» не запустился по цене
  // «Копии» (и наоборот).
  if (state.route !== route) setExpressPricePhase(state, "", "");
  state.route = route;
  state.phase = "edit";
  form.dataset.generationIntakeV4Route = route;
  form.dataset.generationIntakeV4Phase = "edit";
  placeGuidedShell(form, state, route);
  clearSpendConfirmation(form);
  qa("[data-generation-intake-route]", state.shell).forEach((button) => {
    const selected = button.dataset.generationIntakeRoute === route;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  qa("[data-generation-intake-panel]", state.shell).forEach((panel) => {
    const selected = panel.dataset.generationIntakePanel === route;
    panel.hidden = !selected;
    panel.setAttribute("aria-hidden", String(!selected));
  });
  relocateProductSlot(state, route);
  const compact = route !== "strategy_video";
  form.dataset.generationIntakeV4Mode = copyViewActive()
    ? "copy"
    : compact
      ? "compact"
      : "strategy";
  restoreBriefDraft(form, state, route);
  // Карточки фото товара живут в видимом слоте и у «Копии», и у «Создания»:
  // прежний copy_video-only оставлял чекбоксы «Создания» внутри закрытого
  // details «Технические детали» — required-логика их считала, а человек
  // отметить не мог (невидимые чекбоксы, боевой прогон 29.08).
  moveProductNodes(
    form,
    state,
    route === "copy_video" || route === "strategy_video",
  );
  moveSharedBrief(form, state, route);
  qa("[data-generation-intake-panel]", state.shell).forEach((panel) => {
    setPanelControlsActive(panel, panel.dataset.generationIntakePanel === route);
  });
  ensureStrategyAuthority(form, state);
  // Переключение вкладки и загрузка исходников не выбирают стратегию. Точное
  // решение остаётся отдельным человеческим действием в полном конструкторе;
  // compact Copy передаёт свой route только после явной подготовки.
  if (route === "copy_video") {
    prefillIdentityFields(form, state);
    applyExpressDefaults(form, state);
    refreshIdentityVisibility(form, state);
    syncCompactCampaignControl(form, state);
    syncExpressPriceButton(state);
    syncCopyScreenChrome(state);
  } else if (route === "avatar_video") {
    // У «Дуэта» карточка «Кампания и бюджет» такая же, но синхронизация зеркала
    // запускалась только на «Копии» — и select вечно говорил «Кампании
    // загружаются…», а нативное required-поле кампании оставалось пустым.
    syncCompactCampaignControl(form, state);
    syncExpressPriceButton(state);
    syncDuetAvailabilityGate(state);
  }
  if (route === "strategy_video") {
    syncCompactCampaignControl(form, state, "strategy_video");
    syncStrategyLaunchButton(form, state);
    // Поля SKU/названия обязаны появляться при новых фото и на «Создании»,
    // не только по change-событию инпута — рендер-цикл держит их честными.
    refreshIdentityVisibility(form, state);
  }
  refreshVideoSelects(form, state);
  refreshAvatarSelect(form, state);
  refreshModelSelects(form, state);
  refreshProductSelectionCount(form, state);
  refreshRecommendationUi(form, state);
}

function bind(form, state) {
  state.shell.addEventListener("click", (event) => {
    const routeButtonNode = event.target.closest?.("[data-generation-intake-route]");
    if (routeButtonNode) {
      const nextRoute = routeButtonNode.dataset.generationIntakeRoute;
      state.strategyAuthorityRequested = nextRoute === "strategy_video";
      setRoute(form, state, nextRoute);
      return;
    }
    // Очередь файлов снимается целиком и только по прямому действию человека:
    // это единственное место, где её видно, и единственное, где её можно
    // убрать. Само поле загрузки тоже очищается — иначе тот же файл вернулся
    // бы в очередь на ближайшей регистрации.
    if (event.target.closest?.("[data-generation-intake-pending-clear]")) {
      const panel = panelFor(state, "copy_video");
      pendingCopyProductFiles.delete(projectId());
      const fileInput = q('input[data-generation-intake-image="product"]', panel);
      if (fileInput instanceof HTMLInputElement) fileInput.value = "";
      refreshProductSelectionCount(form, state);
      setStatus(
        panel,
        "Файлы убраны из очереди. Уже зарегистрированные фотографии проекта остались — снимите с них галочки, если они лишние.",
        "neutral",
      );
      return;
    }
    const action = event.target.closest?.("[data-action]")?.dataset.action;
    if (action === "generation-intake-analyze-copy") void analyzeRoute(form, "copy_video");
    if (action === "generation-intake-analyze-avatar") void analyzeRoute(form, "avatar_video");
    if (action === "generation-intake-copy-origin") {
      void bindCopyOriginLink(form);
    }
    if (action === "generation-intake-continue-strategy") {
      const trigger = event.target.closest?.("[data-action]");
      if (trigger?.dataset.expressPhase === "priced") {
        void startStrategyPricedLaunch(form, state);
      } else {
        void continueStrategyFromZero(form);
      }
    }
    if (action === "generation-intake-prepare-copy") {
      // Двухфазная кнопка цены: idle → бесплатная подготовка и цена,
      // priced → явный платный запуск «Запустить за $X».
      const trigger = event.target.closest?.("[data-action]");
      if (trigger?.dataset.expressPhase === "priced") void startExpressLaunch(form);
      else void prepareCopy(form);
    }
    if (action === "generation-intake-prepare-avatar") {
      const trigger = event.target.closest?.("[data-action]");
      if (trigger?.dataset.expressPhase === "priced") void startExpressLaunch(form);
      else void prepareAvatar(form);
    }
    if (action === "generation-intake-duet-catalog") {
      void loadDuetPresenterCatalog(form, formStates.get(form));
    }
    if (action === "generation-intake-duet-generate") {
      void generateDuetPresenterFromDescription(form, formStates.get(form));
    }
    if (action === "generation-intake-duet-register") {
      void registerDuetPresenterFromForm(form, formStates.get(form));
    }
    if (action === "generation-intake-upload-strategy") void uploadStrategySources(form);
    if (action === "generation-intake-retry-engines") {
      const strategyId = String(
        event.target.closest?.("[data-strategy-id]")?.dataset.strategyId || "",
      );
      const cache = strategyId ? engineRouteCache(strategyId) : null;
      if (cache) {
        cache.status = "idle";
        cache.routes = [];
        void ensureEngineRoutes(strategyId);
      }
      return;
    }
    if (action === "generation-intake-apply-recommendation") {
      const route = String(event.target.closest?.("[data-route]")?.dataset.route || state.route);
      const brief = form.elements?.brief;
      if (
        brief instanceof HTMLTextAreaElement
        && !String(brief.value || "").trim()
        && DEFAULT_BRIEF_TEMPLATES[route]
      ) {
        // Этот локальный шаблон становится рабочим текстом только по прямому
        // действию человека и не получает provenance ИИ-центра.
        markBriefAsOperatorOwned(form, brief);
        brief.value = DEFAULT_BRIEF_TEMPLATES[route];
        brief.dispatchEvent(new Event("input", { bubbles: true }));
        brief.dispatchEvent(new Event("change", { bubbles: true }));
        refreshRecommendationUi(form, state);
      }
    }
    const frameButton = event.target.closest?.("[data-frame-index]");
    if (frameButton) {
      const route = state.route;
      const routeState = state.routes[route];
      if (!routeState?.storyboard) return;
      routeState.selectedFrameIndex = Number(frameButton.dataset.frameIndex);
      // Свежий человеческий выбор кадра важнее зафиксированного в мастере:
      // сбрасываем селект, чтобы «Показать цену» взяла именно этот кадр.
      const originalSelect = form.elements?.generation_strategy_original_product_media_id;
      if (originalSelect instanceof HTMLSelectElement && originalSelect.value) {
        originalSelect.value = "";
        originalSelect.dispatchEvent(new Event("change", { bubbles: true }));
      }
      renderStoryboard(panelFor(state, route), routeState.storyboard, routeState);
    }
  });

  state.shell.addEventListener("change", (event) => {
    // The mirror commits on `input`, before a native campaign event can
    // patch-render the form. Its following `change` must not commit twice.
    if (event.target.closest?.("[data-generation-intake-campaign-select]")) {
      return;
    }
    // Единая галка «Создания» разом ставит четыре подтверждения мастера —
    // ровно как экспресс-«Копия», только сразу по клику.
    if (event.target.closest?.('[data-generation-intake-rights="strategy_video"]')) {
      applyConsolidatedRights(form, panelFor(state, "strategy_video"));
    }
    // A committed context change must invalidate the previous paid phase before
    // any downstream handler can patch-render the native form. In particular,
    // engine radios can replace this shell between `input` and `change`.
    captureExpressCommittedInput(form, state, event.target);
    invalidateExpressPriceForCommittedInput(form, state, event.target);
    const input = event.target.closest?.('input[data-generation-intake-mp4="single"]');
    if (input) {
      const route = input.closest("[data-generation-intake-panel]")?.dataset.generationIntakePanel;
      if (route && state.routes[route]) {
        const existing = q(
          `[data-generation-intake-existing-video="${CSS.escape(route)}"]`,
          panelFor(state, route),
        );
        if (input.files?.length && existing instanceof HTMLSelectElement) {
          existing.value = "";
        }
        state.routes[route] = {
          sourceFile: null,
          sourceMediaId: "",
          metadata: null,
          storyboard: null,
          selectedFrameIndex: null,
        };
        const prepareAction = route === "copy_video"
          ? "generation-intake-prepare-copy"
          : "generation-intake-prepare-avatar";
        q(`[data-action="${prepareAction}"]`, panelFor(state, route)).disabled = true;
        const storyboard = q("[data-generation-intake-storyboard]", panelFor(state, route));
        if (storyboard) storyboard.hidden = true;
        setStatus(
          panelFor(state, route),
          input.files?.length
            ? "MP4 выбран. Проверяем длительность…"
            : "Выберите исходный MP4.",
          "neutral",
        );
        setSourceFileSummary(
          panelFor(state, route),
          input.files?.length
            ? `${sourceFileLead(input.files[0])} — проверяем длительность…`
            : "",
          "busy",
        );
        // Длительность проверяется сразу: слишком длинный ролик обязан получить
        // видимый отказ с цифрами, а не молча остаться в поле.
        if (input.files?.length) {
          void reportSelectedSourceDuration(state, route, input);
        }
      }
    }

    const registerBlock = event.target.closest?.("[data-generation-intake-duet-register]");
    if (registerBlock instanceof HTMLElement) {
      syncDuetCatalogPreview(registerBlock);
      syncDuetLikenessConsent(registerBlock);
    }

    const duetCategory = event.target.closest?.("[data-generation-intake-duet-category]");
    if (duetCategory instanceof HTMLSelectElement) {
      const native = form.elements?.product_category;
      if (native instanceof HTMLSelectElement && native.value !== duetCategory.value) {
        assignPaidContextValue(native, duetCategory.value);
      }
    }

    const existingVideo = event.target.closest?.("[data-generation-intake-existing-video]");
    if (existingVideo instanceof HTMLSelectElement) {
      // Другой ролик — другая длительность, поэтому прежнее предупреждение
      // о длительности снимается: оно относилось к предыдущему исходнику и
      // после смены читалось бы как утверждение о новом.
      const route = existingVideo.dataset.generationIntakeExistingVideo;
      const routeStrategy = ROUTE_AUTHORITY_STRATEGY[route];
      if (routeStrategy) {
        storeCascadeState(state, routeStrategy, {
          ...(cascadeStateFor(state, routeStrategy) || {}),
          durationNotice: "",
        });
      }
      const panel = panelFor(state, route);
      const fileInput = q('input[data-generation-intake-mp4="single"]', panel);
      if (existingVideo.value && fileInput instanceof HTMLInputElement) {
        fileInput.value = "";
        setSourceFileSummary(panel, "");
      }
      if (route && state.routes[route]) {
        state.routes[route] = {
          sourceFile: null,
          sourceMediaId: "",
          metadata: null,
          storyboard: null,
          selectedFrameIndex: null,
        };
        const prepareAction = route === "copy_video"
          ? "generation-intake-prepare-copy"
          : "generation-intake-prepare-avatar";
        q(`[data-action="${prepareAction}"]`, panel).disabled = true;
        const storyboard = q("[data-generation-intake-storyboard]", panel);
        if (storyboard) storyboard.hidden = true;
        setStatus(
          panel,
          existingVideo.value
            ? copyViewActive() && route === "copy_video"
              ? `Ролик проекта выбран. Нажмите ${selectedSourceNextStep(panel, route)} — проверка выполнится автоматически.`
              : `Ролик проекта выбран. Нажмите ${selectedSourceNextStep(panel, route)}.`
            : "Выберите исходный MP4.",
          "neutral",
        );
      }
    }

    const productFileInput = event.target.closest?.('[data-generation-intake-image="product"]');
    const productCheckbox = event.target.closest?.('input[name="media_id"]');
    if (productCheckbox) captureProductSelectionChange(form, productCheckbox);
    if (productFileInput || productCheckbox) {
      refreshProductSelectionCount(form, state);
      refreshIdentityVisibility(form, state);
    }
    // Выбранные файлы сразу уходят в серверную регистрацию и очередь;
    // отмеченные чипы персистятся в sessionStorage по проекту.
    if (productFileInput) void registerSelectedProductPhotos(form, state);
    const originalFrameInput = event.target.closest?.(
      '[data-generation-intake-image="original_frame"]',
    );
    if (
      originalFrameInput instanceof HTMLInputElement
      && originalFrameInput.files?.length
    ) {
      void registerCopyOriginalFrame(state, originalFrameInput.files[0]);
    }
    if (productCheckbox) persistCopyPhotoSelection(form);
    const rightsToggle = event.target.closest?.('[data-generation-intake-rights="copy_video"]');
    if (rightsToggle instanceof HTMLInputElement && rightsToggle.checked) {
      void registerSelectedProductPhotos(form, state);
    }
    if (
      ["sku", "product_name"].includes(
        String(event.target?.dataset?.generationIntakeField || ""),
      )
    ) {
      void registerSelectedProductPhotos(form, state);
    }

    const avatarMode = event.target.closest?.("[data-generation-intake-avatar-mode]");
    if (avatarMode) syncAvatarMode(panelFor(state, "avatar_video"));

    const avatarFile = event.target.closest?.('[data-generation-intake-image="avatar"]');
    if (avatarFile instanceof HTMLInputElement && avatarFile.files?.length) {
      const select = q("[data-generation-intake-existing-avatar]", panelFor(state, "avatar_video"));
      if (select instanceof HTMLSelectElement) select.value = "";
    }
    const existingAvatar = event.target.closest?.("[data-generation-intake-existing-avatar]");
    if (existingAvatar instanceof HTMLSelectElement && existingAvatar.value) {
      const file = q('[data-generation-intake-image="avatar"]', panelFor(state, "avatar_video"));
      if (file instanceof HTMLInputElement) file.value = "";
    }

    const model = event.target.closest?.('[data-generation-intake-field="model"]');
    if (model instanceof HTMLSelectElement) state.requestedModel = model.value;

    // Каскад «модель → сложность → время». Смена модели снимает и уровень
    // качества, и прежнее предупреждение о длительности: у другой модели свои
    // режимы и свои пределы, и оставлять от прошлого выбора нечего.
    const engineChoice = event.target.closest?.(
      'input[name^="generation_intake_generator"]',
    );
    if (engineChoice instanceof HTMLInputElement && engineChoice.checked) {
      const cascadeRoute = cascadeEventRoute(event.target);
      storeCascadeState(state, ROUTE_AUTHORITY_STRATEGY[cascadeRoute], {
        modelId: String(engineChoice.value || ""),
        qualityCode: "",
        durationNotice: "",
        // Человек выбрал сам: совет ИИ-центра больше не перекрывает выбор
        // при перерисовке (раньше флаг ставила только «Копия», и на
        // «Создании» выбранный движок откатывался к рекомендованному).
        humanChoice: true,
      });
      refreshEngineChoice(form, state, cascadeRoute);
    }
    const qualityChoice = event.target.closest?.(
      'input[name^="generation_intake_quality"]',
    );
    if (qualityChoice instanceof HTMLInputElement && qualityChoice.checked) {
      const cascadeRoute = cascadeEventRoute(event.target);
      const cascadeStrategy = ROUTE_AUTHORITY_STRATEGY[cascadeRoute];
      storeCascadeState(state, cascadeStrategy, {
        ...(cascadeStateFor(state, cascadeStrategy) || {}),
        qualityCode: String(qualityChoice.value || ""),
        durationNotice: "",
      });
      refreshEngineChoice(form, state, cascadeRoute);
    }
    // Смена ведущего подтягивает ЕГО раскладку: у каждого своя привычная
    // посадка в кадре, и подставлять чужую было бы сюрпризом.
    const presenterChoice = event.target.closest?.(
      "[data-generation-intake-duet-presenter-select]",
    );
    if (presenterChoice instanceof HTMLSelectElement) {
      const section = presenterChoice.closest(
        "[data-generation-intake-duet-presenter]",
      );
      if (section) {
        applyDuetPresenterLayout(
          section,
          duetPresenterCache.get(projectId()) || [],
          presenterChoice.value,
        );
      }
    }
    const widthChoice = event.target.closest?.(
      "[data-generation-intake-duet-width]",
    );
    if (widthChoice instanceof HTMLInputElement) {
      const section = widthChoice.closest("[data-generation-intake-duet-presenter]");
      if (section) syncDuetWidthLabel(section);
    }
    const durationChoice = event.target.closest?.(
      'input[name^="generation_intake_duration"]',
    );
    if (durationChoice instanceof HTMLInputElement && durationChoice.checked) {
      const cascadeRoute = cascadeEventRoute(event.target);
      const cascadeStrategy = ROUTE_AUTHORITY_STRATEGY[cascadeRoute];
      storeCascadeState(state, cascadeStrategy, {
        ...(cascadeStateFor(state, cascadeStrategy) || {}),
        durationNotice: "",
      });
      applyCopyDuration(form, Number(durationChoice.value));
      refreshEngineChoice(form, state, cascadeRoute);
    }

    if (event.target === form.elements?.brief) {
      refreshRecommendationUi(form, state);
      scheduleBriefDraftCapture(form, state);
    }

    const copyPanelNode = panelFor(state, "copy_video");
    if (copyPanelNode?.contains?.(event.target)) {
      // Любое изменение контекста возвращает кнопку к «Показать цену»:
      // старая серверная цена не выдаётся за актуальную.
      resetExpressPrice(state);
      rememberExpressDefaults(state);
      syncCopyScreenChrome(state);
    }
  });

  state.shell.addEventListener("input", (event) => {
    const campaignMirror = event.target.closest?.(
      "[data-generation-intake-campaign-select]",
    );
    if (campaignMirror instanceof HTMLSelectElement) {
      // This records the human choice and clears price/token/confirmation
      // before dispatching the authoritative native campaign_id events.
      commitCompactCampaignSelection(form, state, campaignMirror);
      return;
    }
    // Capture happens on the compact shell before the event reaches form/app.js
    // and can trigger a patch-render. A checked rights box or selected engine
    // therefore survives replacement even when the later `change` is lost.
    captureExpressCommittedInput(form, state, event.target);
    const productCheckbox = event.target.closest?.('input[name="media_id"]');
    if (productCheckbox) captureProductSelectionChange(form, productCheckbox);
    invalidateExpressPriceForCommittedInput(form, state, event.target);
    if (event.target === form.elements?.brief) {
      refreshRecommendationUi(form, state);
      scheduleBriefDraftCapture(form, state);
    }
    const identityField = event.target?.dataset?.generationIntakeField;
    if (identityField === "sku" || identityField === "product_name") {
      syncIdentityToForm(
        form,
        identityField,
        cleanText(event.target.value, identityField === "sku" ? 120 : 180),
      );
    }
    if (identityField === "product_category") {
      syncIdentityToForm(form, "product_category", String(event.target.value || ""));
    }
    if (identityField) rememberExpressDefaults(state);
  });

  // Кампания находится в native sibling, а не внутри state.shell. Сохраняем её
  // на раннем input той же формы; spend confirmation намеренно не сохраняется.
  form.addEventListener("input", (event) => {
    if (event.target === form.elements?.brief) {
      refreshRecommendationUi(form, state);
      scheduleBriefDraftCapture(form, state);
    }
    if (event.target === form.elements?.campaign_id) {
      captureExpressCommittedInput(form, state, event.target);
    }
    if (!state.shell.contains(event.target)) {
      invalidateExpressPriceForCommittedInput(form, state, event.target);
    }
  });
  form.addEventListener("change", (event) => {
    if (event.target === form.elements?.brief) {
      refreshRecommendationUi(form, state);
      scheduleBriefDraftCapture(form, state);
    }
    if (event.target === form.elements?.campaign_id) {
      captureExpressCommittedInput(form, state, event.target);
    }
    if (!state.shell.contains(event.target)) {
      invalidateExpressPriceForCommittedInput(form, state, event.target);
    }
  });
  form.addEventListener("contentengine:generation-restore-strategy", () => {
    // Repeat restores only a selection template. It may keep the operator's
    // current campaign choice available, but never the previous price, token,
    // checkbox or compact paid CTA.
    resetExpressAuthorityForStrategyRepeat(form, state);
  });
}

function mount(form) {
  if (!(form instanceof HTMLFormElement)) return;
  const existing = formStates.get(form);
  if (existing?.shell?.isConnected) {
    // Внешний модуль ИИ-центра может применить/уточнить рекомендацию между
    // render-событиями. Сначала фиксируем живой маршрут, затем обновляем UI.
    captureBriefDraft(form, existing, existing.briefRoute || existing.route);
    if (existing.shell.parentElement !== form) form.prepend(existing.shell);
    placeGuidedShell(form, existing, existing.route);
    ensureStrategyAuthority(form, existing);
    refreshVideoSelects(form, existing);
    refreshAvatarSelect(form, existing);
    refreshModelSelects(form, existing);
    refreshProductSelectionCount(form, existing);
    if (["compact", "copy"].includes(form.dataset.generationIntakeV4Mode)) {
      refreshRecommendationUi(form, existing);
      if (existing.route === "copy_video") {
        moveProductNodes(form, existing, true);
        // Грабля: перерисовка сбрасывает select-значения. Повторное
        // монтирование восстанавливает звук/категорию и фазу кнопки цены.
        applyExpressDefaults(form, existing);
        refreshIdentityVisibility(form, existing);
        syncCompactCampaignControl(form, existing);
        syncExpressPriceButton(existing);
      } else if (existing.route === "avatar_video") {
        syncCompactCampaignControl(form, existing);
        syncExpressPriceButton(existing);
      }
    } else if (existing.route === "strategy_video") {
      moveSharedBrief(form, existing, "strategy_video");
      // Перерисовка каталога app.js создаёт серверные карточки фото у их
      // маркеров в закрытом details конструктора — возвращаем их в видимый
      // слот, как copy-ветка выше. (Фазы review на этом маршруте не бывает:
      // экспресс-handoff повторного запуска всегда идёт компактным route.)
      relocateProductSlot(existing, "strategy_video");
      moveProductNodes(form, existing, true);
      refreshRecommendationUi(form, existing);
      syncCompactCampaignControl(form, existing, "strategy_video");
      syncStrategyLaunchButton(form, existing);
    } else if (existing.phase === "review") {
      moveProductNodes(form, existing, false);
      moveSharedBrief(form, existing, "strategy_video");
    }
    syncRouteBusyUi(existing);
    if (copyViewActive()) {
      if (
        existing.route !== "copy_video"
        || form.dataset.generationIntakeV4Mode !== "copy"
      ) {
        setRoute(form, existing, "copy_video");
      }
      // Кандидаты пикера грузятся асинхронно: каждый пересинк добирает
      // стратегию движка и заново наполняет селект исходников.
      ensureCopyEngineStrategy(form);
      // Санити-требование: перерисовка/переход не теряет выбор фото.
      restoreCopyPhotoSelection(form, existing);
      syncCopyScreenChrome(existing);
    } else if (
      form.dataset.generationIntakeV4Mode === "copy"
      && existing.phase !== "review"
    ) {
      setRoute(form, existing, existing.route);
    }
    return;
  }
  ensureStyle();
  ensureContractFields(form);
  q("[data-generation-intake-v2]", form)?.remove();
  q("[data-generation-intake-v3]", form)?.remove();
  const shell = shellNode();
  const guidedShell = q("[data-ce-v4-generation-guided-shell]", form);
  if (guidedShell?.parentElement === form) guidedShell.before(shell);
  else form.prepend(shell);
  const briefControl = form.elements?.brief;
  const briefField = briefControl instanceof HTMLTextAreaElement
    ? briefControl.closest("label.field") || briefControl.parentElement
    : null;
  const briefOrigin = document.createComment("generation-intake-v4-brief-origin");
  if (briefField instanceof HTMLElement) briefField.before(briefOrigin);
  const state = {
    shell,
    route: "copy_video",
    phase: "edit",
    busy: false,
    busyRoute: "",
    busyAction: "",
    productUploadBusy: false,
    requestedModel: "",
    // Set only by the operator clicking the outer “Видео по стратегии” card.
    // A mount or programmatic default must never masquerade as human choice.
    strategyAuthorityRequested: false,
    // Выбор каскада «Копии»: уровень, модель и последнее объяснение того,
    // почему длительность была приведена к допустимой.
    copyEngine: { modelId: "", qualityCode: "", durationNotice: "" },
    // Каскады остальных стратегий («Дуэт», «Создание») — по ключу стратегии.
    engineCascades: {},
    express: {
      phase: "idle",
      price: "",
      spend_confirmation: "",
      campaign_id: "",
    },
    productNodes: [],
    briefControl,
    briefField,
    briefDraftMemoryKey: routeBriefDraftMemoryKey(),
    briefDrafts: initialRouteBriefDrafts(form, briefControl),
    briefRoute: declaredBriefRoute(form),
    briefDraftReady: false,
    briefOrigin: briefField instanceof HTMLElement ? briefOrigin : null,
    briefOriginal: briefField instanceof HTMLElement
      ? {
        label: q("#generation-brief-label", briefField)?.textContent || "",
        hint: q("#generation-brief-hint", briefField)?.textContent || "",
        placeholder: briefControl?.placeholder || "",
        maxLength: briefControl?.maxLength,
      }
      : null,
    routes: {
      copy_video: {
        sourceFile: null,
        sourceMediaId: "",
        metadata: null,
        storyboard: null,
        selectedFrameIndex: null,
      },
      avatar_video: {
        sourceFile: null,
        sourceMediaId: "",
        metadata: null,
        storyboard: null,
        selectedFrameIndex: null,
      },
    },
  };
  formStates.set(form, state);
  form.dataset.generationIntakeV4Bound = HANDOFF_VERSION;
  bind(form, state);
  placeGuidedShell(form, state, state.route);
  setRoute(form, state, "copy_video");
  if (copyViewActive()) {
    ensureCopyEngineStrategy(form);
    restoreCopyPhotoSelection(form, state);
  }
  syncCopyScreenChrome(state);
}

// Что наблюдаем и зачем это выделено в функцию: наблюдатель нужно снимать на
// время перерисовки и ставить обратно, поэтому набор опций должен быть один и
// тот же в обоих случаях.
const MOUNT_OBSERVER_OPTIONS = Object.freeze({
  childList: true,
  attributes: true,
  attributeFilter: Object.freeze([
    "data-generation-strategy-paid-locked",
    "data-launch-phase",
  ]),
  subtree: true,
});

let mountObserver = null;

function observeMountTriggers() {
  mountObserver?.observe(document.documentElement, MOUNT_OBSERVER_OPTIONS);
}

function scheduleMount() {
  if (mountQueued) return;
  mountQueued = true;
  queueMicrotask(() => {
    mountQueued = false;
    if (routePath() !== ROUTE) return;
    const form = q("#mock-batch-form");
    if (!form) return;
    // Наблюдатель снимается на время перерисовки. Оба атрибута, за которыми он
    // следит, пишутся БЕЗУСЛОВНО при каждой синхронизации готовности, а во
    // время платного запуска поллер статусов зовёт её раз в пять секунд. Пока
    // наблюдатель подключён, любой не-идемпотентный участок mount замыкает цикл
    // в микрозадачах — не в кадрах, — и вкладка встаёт намертво. Панель «Копия»
    // на этом уже дважды вешала браузер, флага mountQueued для защиты не хватает:
    // он снимается ДО mount, поэтому мутации самой перерисовки ставят следующую
    // микрозадачу.
    mountObserver?.disconnect();
    try {
      mount(form);
    } finally {
      observeMountTriggers();
    }
  });
}

window.addEventListener("hashchange", scheduleMount);
window.addEventListener("contentengine:rendered", scheduleMount);
window.addEventListener("contentengine:generation-research-preset-applied", scheduleMount);
window.addEventListener("contentengine:generation-research-preset-opt-out", scheduleMount);
mountObserver = new MutationObserver(scheduleMount);
observeMountTriggers();
scheduleMount();

export {
  HANDOFF_VERSION,
  MAX_STRATEGY_FILES,
  PAID_AUTHORITY,
  COPY_AUTHORITY_STRATEGY,
  assertMediaKindMime,
  mediaKindMimeMismatchMessage,
  uploadProjectMedia,
  assertMp4,
  captureStoryboard,
  applyHandoffSourceDuration,
  applyConsolidatedRights,
  bindHandoffPrimaryProduct,
  captureProductSelectionChange,
  ensureProductCheckbox,
  ensureOriginalProductOption,
  handoffSourceDurationSeconds,
  rememberProductSelectionChange,
  selectedProductMediaIds,
  expressPaidAuthorityLocked,
  resolveExpressCampaign,
  syncCompactCampaignControl,
  commitCompactCampaignSelection,
  expressCampaignMatchesPrice,
  resetExpressAuthorityForStrategyRepeat,
  syncExpressPriceButton,
};
