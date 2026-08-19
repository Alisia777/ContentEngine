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
const STRATEGY_AUTHORITY_STRATEGY = "viral_rebuild";
const CHARACTER_PERFORMANCE_FEATURE = "generation_character_performance_v1";
const HANDOFF_VERSION = "generation-intake-mp4-v4";
const DIRECT_MP4_ATTACHMENT_RPC =
  "contentengine_attach_generation_direct_mp4";
const STYLE_HREF = new URL(
  "./generation-strategy-intake-v4.css?v=20260819.cascade.1",
  import.meta.url,
).href;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const MAX_COPY_DURATION = 15;
const MIN_COPY_DURATION = 4;
const MAX_AVATAR_DURATION = 30;
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
const DEFAULT_RECOMMENDATIONS = Object.freeze({
  copy_video: "Сохранить последовательность сцен, движение камеры, темп и монтаж исходного ролика. Заменить только исходный товар на товар с выбранных фото: точно сохранить форму, материал, цвет, упаковку и логотип. Не добавлять новые объекты или надписи.",
  avatar_video: "Сохранить сцены, тайминг, камеру и композицию исходного ролика. Встроить выбранного аватара естественно: согласовать масштаб, свет, тени, взгляд и движения с кадром. Не менять товар и фон без необходимости.",
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
const EXPRESS_FREE_SUBMIT_PHASES = Object.freeze([
  "strategy_product_swap_prepare",
  "strategy_product_swap_spec_review",
  "strategy_product_swap_free_preflight",
]);
const EXPRESS_PREFLIGHT_TIMEOUT_MS = 180_000;
const EXPRESS_POLL_INTERVAL_MS = 400;
const EXPRESS_BLOCKED_POLL_LIMIT = 15;
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
function setStatus(panel, text, state = "neutral") {
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
  });
}

function routeButton(id, number, title, summary) {
  const button = el("button", "generation-intake-v4__route");
  button.type = "button";
  button.dataset.generationIntakeRoute = id;
  button.setAttribute("aria-pressed", "false");
  button.append(
    el("span", "generation-intake-v4__route-number", number),
    (() => {
      const copy = el("span", "generation-intake-v4__route-copy");
      copy.append(el("strong", "", title), el("small", "", summary));
      return copy;
    })(),
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
  label.append(
    el("strong", "", "Перетащите MP4 сюда или выберите файл"),
    el("span", "", "Формат и длительность проверим автоматически"),
    input,
  );
  const select = document.createElement("select");
  select.dataset.generationIntakeExistingVideo = route;
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
  section.append(
    el("p", "gi-card__hint", `Добавьте 1–${MAX_PRODUCT_IMAGES} фото одного товара — новые файлы или уже проверенные фотографии проекта.`),
    upload,
    count,
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

function recommendationSlot(route) {
  const section = el("section", "generation-intake-v4__recommendation");
  section.dataset.generationIntakeRecommendation = route;
  const header = el("div", "generation-intake-v4__recommendation-head");
  header.append(
    el("h4", "", route === "copy_video"
      ? "Рекомендация: что сохранить и как заменить"
      : "Рекомендация для ролика с аватаром"),
    (() => {
      const badge = el("span", "badge", "Можно исправить");
      badge.dataset.generationIntakeRecommendationSource = "";
      return badge;
    })(),
  );
  const slot = el("div", "generation-intake-v4__recommendation-field");
  slot.dataset.generationIntakeBriefSlot = route;
  const fallback = el("div", "generation-intake-v4__recommendation-fallback");
  fallback.dataset.generationIntakeRecommendationFallback = route;
  fallback.append(
    el("p", "", DEFAULT_RECOMMENDATIONS[route]),
    (() => {
      const button = el("button", "btn btn-secondary", "Использовать эту рекомендацию");
      button.type = "button";
      button.dataset.action = "generation-intake-apply-recommendation";
      button.dataset.route = route;
      return button;
    })(),
  );
  const meta = el("small", "generation-intake-v4__recommendation-meta", `0 / ${BRIEF_LIMIT}`);
  meta.dataset.generationIntakeBriefMeta = route;
  section.append(header, slot, fallback, meta);
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
      route === "copy_video"
        ? "Подтверждаю все права одним действием: у команды есть право использовать исходный ролик как референс; мы переносим только механику — это переработка без чужого бренда, музыки, голоса и точных кадров; права на изображения товара подтверждены; согласия людей в кадре получены — либо людей в кадре нет."
        : "У команды есть право использовать исходный ролик.",
    ),
  );
  return label;
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

// Цена уровня: самая дешёвая известная ставка среди его моделей. Если ставки
// нет ни у одной — говорим об этом прямо, а не показываем ноль.
function tierPriceNote(engines) {
  const perRun = engines
    .filter((engine) => engine.priceKind === "usd_minor_per_run" && engine.priceRateMinor)
    .map((engine) => engine.priceRateMinor);
  const perSecond = engines
    .filter((engine) => engine.priceKind === "usd_minor_per_second" && engine.priceRateMinor)
    .map((engine) => engine.priceRateMinor);
  const parts = [];
  if (perRun.length) parts.push(`от ${usdFromMinor(Math.min(...perRun))} за ролик`);
  if (perSecond.length) {
    parts.push(`от ${usdFromMinor(Math.min(...perSecond))} за секунду`);
  }
  if (parts.length) return parts.join(" · ");
  return engines.some((engine) => engine.priceKind === "runway_credit_tiers")
    ? "по ступеням кредитов"
    : "цену назовёт сервер";
}

// Количество моделей уровня по-русски: «2 модели», но «5 моделей».
function modelCountLabel(count) {
  const tail = count % 100;
  const last = count % 10;
  const word = tail >= 11 && tail <= 14
    ? "моделей"
    : last === 1
    ? "модель"
    : last >= 2 && last <= 4
    ? "модели"
    : "моделей";
  return `${count} ${word}`;
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
  const stamp = JSON.stringify([selectedValue || "", options]);
  if (row.dataset.stamp === stamp) return;
  row.dataset.stamp = stamp;
  row.replaceChildren(...options.map((option) => {
    const chip = el("label", "gi-chip gi-chip--choice");
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
    if (option.recommended) body.append(el("span", "gi-chip__badge", "Советуем"));
    body.append(el("span", "gi-chip__title", option.title));
    if (option.note) body.append(el("span", "gi-chip__note", option.note));
    chip.append(input, body);
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

function copyEngineChoice() {
  const section = el("section", "gi-card gi-cascade");
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
  const durationNotice = el("p", "gi-cascade__notice", "");
  durationNotice.dataset.generationIntakeDurationNotice = "";
  durationNotice.hidden = true;
  durationStep.append(durationNotice);

  const price = el("p", "gi-card__hint gi-cascade__price", "");
  price.dataset.generationIntakePriceLine = "";
  const routeNote = el("p", "gi-card__hint", "");
  routeNote.dataset.generationIntakeRouteNote = "";

  section.append(
    el("h4", "gi-card__title", "Чем генерируем и как долго"),
    cascadeStep("tier", "1", "Уровень", "generation_intake_tier"),
    cascadeStep("model", "2", "Модель", "generation_intake_generator"),
    durationStep,
    price,
    routeNote,
  );
  return section;
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
  const campaignNote = el("p", "generation-intake-v4__campaign-note");
  campaignNote.dataset.generationIntakeCampaignNote = "";
  campaignNote.hidden = true;
  const campaignLink = el("a", "", "Создать кампанию");
  campaignLink.href = NEW_CAMPAIGN_ROUTE_HASH;
  campaignNote.append(
    el("span", "", "В проекте нет активной кампании, поэтому платный запуск честно невозможен. "),
    campaignLink,
    el("span", "", " и вернитесь в эту форму."),
  );
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
    storyboardNode(),
  );

  const productCard = el("section", "gi-card");
  productCard.dataset.giStep = "2";
  productCard.append(
    el("h4", "gi-card__title", "2. Ваш товар"),
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
    copyEngineChoice(),
    briefCard,
    rightsConfirmation("copy_video"),
    campaignNote,
    autoDefaults,
  );

  const grid = el("div", "gi-copy__grid");
  grid.append(main, copyRail(actions, statusNode()));
  panel.append(head, grid);
  return panel;
}

function avatarPanel() {
  const panel = el("section", "generation-intake-v4__panel");
  panel.dataset.generationIntakePanel = "avatar_video";
  panel.hidden = true;
  const actions = el("div", "generation-intake-v4__actions");
  const analyze = el("button", "btn", "Разобрать MP4");
  analyze.type = "button";
  analyze.dataset.action = "generation-intake-analyze-avatar";
  const prepare = el("button", "btn btn-primary", "Подготовить аватара");
  prepare.type = "button";
  prepare.dataset.action = "generation-intake-prepare-avatar";
  prepare.disabled = true;
  actions.append(analyze, prepare);
  panel.append(
    routeHeader(
      "ОТДЕЛЬНАЯ ФОРМА",
      "Сделать с аватаром",
      "Добавляем аватара из фотографии или описания в выбранный исходный MP4.",
      "Character Performance",
    ),
    sourceChooser("avatar_video"),
    avatarIdentityChooser(),
    recommendationSlot("avatar_video"),
    rightsConfirmation("avatar_video"),
    el(
      "p",
      "generation-intake-v4__gate-note",
      "Форма и mock-подготовка работают локально. Платный Character Performance останется закрыт до подтверждения точного provider-adapter — он не подменяется Product UGC.",
    ),
    statusNode(),
    actions,
  );
  return panel;
}

function strategyPanel() {
  const panel = el("section", "generation-intake-v4__panel generation-intake-v4__panel--strategy");
  panel.dataset.generationIntakePanel = "strategy_video";
  panel.hidden = true;
  const input = mp4Input({ multiple: true });
  input.id = "generation-intake-strategy-mp4";
  const upload = el("button", "btn btn-secondary", "Добавить исходники в проект");
  upload.type = "button";
  upload.dataset.action = "generation-intake-upload-strategy";
  const actions = el("div", "generation-intake-v4__actions");
  actions.append(upload);
  panel.append(
    routeHeader(
      "ПОЛНЫЙ КОНСТРУКТОР",
      "Создать видео по стратегии",
      "Товар, площадка, сценарий, исходники, рекомендованная модель, длительность, звук и бюджет.",
      "До 10 MP4",
    ),
    field(
      "Дополнительные видео-исходники — по желанию",
      "Выберите до 10 MP4. После загрузки они появятся среди материалов проекта и будут доступны полному конструктору.",
      input,
    ),
    statusNode(),
    actions,
    el(
      "p",
      "generation-intake-v4__full-note",
      "Ниже остаётся действующая шестишаговая форма. Ничего из её функций не удалено.",
    ),
  );
  return panel;
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
    .map((input) => input.closest("label, article, li") || input.parentElement)
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
  ]);
  const videos = [...new Map([
    ...collectProjectVideos(form),
    ...nativeVideos,
    ...pickerVideos,
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
  return qa('input[name="media_id"]:checked', productRoot).filter((input) => (
    busyLocked ? input.dataset.wasDisabled !== "true" : !input.disabled
  ));
}

function selectedProductMediaIds(form) {
  const result = [];
  const seen = new Set();
  checkedProductInputs(form).forEach((input) => {
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
  const panel = panelFor(state, "copy_video");
  const target = q("[data-generation-intake-product-count]", panel);
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
  refreshCopyChecklist(form, state);
  refreshEngineChoice(form, state);
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
const copyEngineRouteCache = { status: "idle", routes: [] };
let copyEngineRenderContext = null;

function guidedCopyEngineRoutes() {
  const routes = window.ContentEngineGenerationGuidedV4
    ?.getStrategyProviderRoutes?.(COPY_AUTHORITY_STRATEGY);
  return Array.isArray(routes) ? routes : [];
}

async function ensureCopyEngineRoutes() {
  if (copyEngineRouteCache.status !== "idle") return;
  if (guidedCopyEngineRoutes().length) return;
  copyEngineRouteCache.status = "loading";
  try {
    const api = await apiRuntime();
    const response = await api.generationStrategyCatalog({
      organizationId: api.organizationId,
      projectId: projectId(),
    });
    const catalog = response?.catalog ?? response;
    const routes = catalog?.strategyProviderRoutes?.[COPY_AUTHORITY_STRATEGY];
    copyEngineRouteCache.routes = Array.isArray(routes) ? routes : [];
    copyEngineRouteCache.status = "ready";
  } catch {
    // Отказ каталога не должен ломать форму: карточка просто не появится, а
    // запуск по-прежнему идёт по действующему маршруту реестра.
    copyEngineRouteCache.routes = [];
    copyEngineRouteCache.status = "error";
  }
  const context = copyEngineRenderContext;
  if (context?.section?.isConnected) {
    renderEngineChoice(context.form, context.state, context.section);
  }
}

function copyEngineRoutes() {
  const guided = guidedCopyEngineRoutes();
  const routes = guided.length ? guided : copyEngineRouteCache.routes;
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

function refreshEngineChoice(form, state) {
  const panel = panelFor(state, "copy_video");
  const section = panel ? q("[data-generation-intake-engine]", panel) : null;
  if (!section || engineChoiceBusy) return;
  engineChoiceBusy = true;
  try {
    renderEngineChoice(form, state, section);
  } finally {
    engineChoiceBusy = false;
  }
}

function renderEngineChoice(form, state, section) {
  copyEngineRenderContext = { form, state, section };
  const engines = copyEngineRoutes();
  if (!engines.length) {
    // Пока маршрутов нет, карточка скрыта целиком: три пустых пронумерованных
    // ряда молчат хуже, чем их отсутствие. Загрузку запускаем здесь же.
    if (!section.hidden) section.hidden = true;
    void ensureCopyEngineRoutes();
    return;
  }
  const cascade = state.copyEngine || { tier: "", modelId: "", durationNotice: "" };

  // Ступень 1 — уровень. Смена уровня снимает выбранную модель: список моделей
  // ниже перерисовывается, и старый идентификатор в нём больше не значится.
  const tiers = orderedTiers(engines);
  const fallbackEngine = engines.find((engine) => engine.recommended && engine.enabled)
    || engines.find((engine) => engine.enabled)
    || engines[0];
  const selectedTier = tiers.includes(cascade.tier)
    ? cascade.tier
    : fallbackEngine.tier;
  renderChoiceChips(
    q('[data-generation-intake-choice="tier"]', section),
    tiers.map((tier) => {
      const tierEngines = engines.filter((engine) => engine.tier === tier);
      return {
        value: tier,
        title: tierPublicLabel(tier),
        note: `${tierPriceNote(tierEngines)} · ${modelCountLabel(tierEngines.length)}`,
        recommended: tierEngines.some((engine) => engine.recommended),
        disabled: !tierEngines.some((engine) => engine.enabled),
      };
    }),
    selectedTier,
  );

  // Ступень 2 — модели выбранного уровня, человеческими именами и с ценой.
  const tierEngines = engines.filter((engine) => engine.tier === selectedTier);
  const selectedEngine = tierEngines.find((engine) => engine.id === cascade.modelId)
    || tierEngines.find((engine) => engine.recommended && engine.enabled)
    || tierEngines.find((engine) => engine.enabled)
    || tierEngines[0];
  renderChoiceChips(
    q('[data-generation-intake-choice="model"]', section),
    tierEngines.map((engine) => ({
      value: engine.id,
      title: engine.label,
      note: `${providerPublicLabel(engine.provider)} · ${routePriceNote(engine)}${
        engine.enabled ? "" : " · пока недоступна"
      }`,
      recommended: engine.recommended,
      disabled: !engine.enabled,
    })),
    selectedEngine?.id,
  );

  if (!selectedEngine) {
    if (!section.hidden) section.hidden = true;
    return;
  }

  // Ступень 3 — тайминги выбранной модели. Несовместимое значение не остаётся
  // молча неверным: оно приводится к ближайшему допустимому, и об этом говорят
  // вслух.
  const durationWindow = engineDurationWindow(selectedEngine, form);
  const durations = [];
  for (
    let seconds = durationWindow.min;
    seconds <= durationWindow.max;
    seconds += 1
  ) durations.push(seconds);
  const control = wizardDurationControl(form);
  const current = Number(control?.value);
  let chosen = durations.includes(current) ? current : null;
  let notice = String(cascade.durationNotice || "");
  if (durations.length && chosen === null) {
    chosen = Number.isFinite(current) && current > 0
      ? Math.min(durationWindow.max, Math.max(durationWindow.min, Math.round(current)))
      : durations[0];
    if (Number.isFinite(current) && current > 0 && applyCopyDuration(form, chosen)) {
      notice = `${current} с не подходит для «${selectedEngine.label}»: допустимо `
        + `${durationWindow.min}–${durationWindow.max} с. Оставили ${chosen} с.`;
    } else {
      applyCopyDuration(form, chosen);
    }
  }
  renderChoiceChips(
    q('[data-generation-intake-choice="duration"]', section),
    durations.map((seconds) => ({
      value: String(seconds),
      title: `${seconds} с`,
      disabled: !control || control.disabled,
    })),
    chosen === null ? "" : String(chosen),
  );
  const durationNotice = q("[data-generation-intake-duration-notice]", section);
  if (durationNotice) {
    setNodeText(
      durationNotice,
      notice || (durations.length
        ? durationWindow.fromRegistry
          ? `«${selectedEngine.label}» принимает ${durationWindow.min}–${durationWindow.max} с.`
          : `Реестр пока не отдаёт пределы этой модели, поэтому показано окно стратегии: ${durationWindow.min}–${durationWindow.max} с.`
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

  // Честность про исполнение: маршрут запуска берётся из реестра по отметке
  // «Советуем», и выбор модели его пока не переключает. Умолчать об этом
  // значило бы показать выбор, которого нет.
  const activeEngine = engines.find((engine) => engine.recommended && engine.enabled);
  setNodeText(
    q("[data-generation-intake-route-note]", section),
    !activeEngine
      ? "Действующий маршрут реестра не отмечен — запуск подтвердит сервер."
      : selectedEngine && selectedEngine.id !== activeEngine.id
      ? `Исполняет пока «${activeEngine.label}» — действующий маршрут реестра. Ваш выбор модели меняет тайминги и оценку цены, но не переключает запуск.`
      : `Исполняет «${activeEngine.label}» — действующий маршрут реестра.`,
  );

  state.copyEngine = {
    tier: selectedTier,
    modelId: selectedEngine?.id || "",
    durationNotice: notice,
  };
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
  for (const input of checkedProductInputs(form)) {
    const sku = cleanText(input.dataset?.mediaSku, 120);
    const productName = cleanText(input.dataset?.mediaProductName, 180);
    if (sku && productName) return { sku, product_name: productName };
  }
  return null;
}

function refreshIdentityVisibility(form, state) {
  const panel = panelFor(state, "copy_video");
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
    const entries = checkedProductInputs(form)
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
  entries.slice(0, MAX_PRODUCT_IMAGES).forEach((entry) => {
    const id = String(entry?.id || "").trim().toLowerCase();
    if (!UUID_PATTERN.test(id)) return;
    const existing = existingMediaCheckbox(form, id);
    if (existing instanceof HTMLInputElement) {
      if (!existing.disabled && !existing.checked) {
        existing.checked = true;
        existing.dispatchEvent(new Event("change", { bubbles: true }));
      }
      return;
    }
    const sku = cleanText(entry?.sku, 120);
    const productName = cleanText(entry?.product_name, 180);
    ensureProductCheckbox(
      form,
      state,
      id,
      sku && productName ? { sku, product_name: productName } : null,
      cleanText(entry?.label, 120),
    );
  });
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
        setStatus(
          panel,
          `«${cleanText(file.name, 60)}»: ${dropMessages[imageError?.message] || "файл не прошёл проверку."} Остальные файлы в очереди не потеряны (${queue.length}).`,
          "error",
        );
        continue;
      }
      const mediaId = await uploadProjectMedia(file, "product_photo", identity);
      ensureProductCheckbox(form, state, mediaId, identity, file.name);
      queue.shift();
      pendingCopyProductFiles.set(project, queue);
      persistCopyPhotoSelection(form);
      refreshProductSelectionCount(form, state);
      setStatus(
        panel,
        "Фото зарегистрированы в проекте и выбраны. Загружать их повторно не нужно — выбор переживает перерисовку.",
        "ready",
      );
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
    button.disabled = false;
  }
}

async function sha256Hex(blob) {
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function assertImage(file) {
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

async function uploadProjectMedia(file, kind, productIdentity = null) {
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
  return q(`[data-generation-intake-panel="${CSS.escape(route)}"]`, state.shell);
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

function currentRecommendation(form) {
  return cleanText(form.elements?.brief?.value, 1_200);
}

function recommendationSource(form) {
  const brief = form.elements?.brief;
  const active = form.dataset.researchRecommendationLineage === "active";
  const verified = form.dataset.researchRecommendationVerificationState === "verified";
  const applied = Boolean(brief?.dataset?.researchRecommendationApplied);
  const edited = brief?.dataset?.researchRecommendationEdited === "true";
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
  if (!DEFAULT_RECOMMENDATIONS[route]) return;
  moveSharedBrief(form, state, route);
  const brief = form.elements?.brief;
  if (!(brief instanceof HTMLTextAreaElement)) return;
  const label = q("#generation-brief-label", state.briefField);
  const hint = q("#generation-brief-hint", state.briefField);
  if (label) {
    setNodeText(label, route === "copy_video"
      ? "Что сохранить и как заменить товар"
      : "Как встроить аватара в ролик");
  }
  if (hint) {
    setNodeText(
      hint,
      "Это единый редактируемый замысел проекта. Проверенная рекомендация ИИ‑центра появляется здесь же и не перезаписывает ваши правки.",
    );
  }
  brief.placeholder = "Напишите свою рекомендацию или примените базовый вариант ниже.";
  brief.maxLength = BRIEF_LIMIT;
  const value = String(brief.value || "");
  const source = recommendationSource(form);
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
          : value
            ? "Ваш текст"
            : "Базовая рекомендация");
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
    meta.dataset.state = value.length > BRIEF_LIMIT ? "error" : "neutral";
    setNodeText(meta, value.length > BRIEF_LIMIT
      ? `${value.length} / ${BRIEF_LIMIT} · текст не обрезан: сократите его перед preflight`
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

function clearSpendConfirmation(form) {
  const confirmation = form.elements?.real_spend_confirmation;
  if (!(confirmation instanceof HTMLInputElement)) return;
  const changed = confirmation.checked || Boolean(confirmation.value);
  confirmation.checked = false;
  confirmation.value = "";
  if (changed) {
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
  const consolidated = q('[data-generation-intake-rights="copy_video"]', panel);
  if (!(consolidated instanceof HTMLInputElement) || !consolidated.checked) {
    return [...COPY_ATTESTATION_IDS];
  }
  const missing = [];
  COPY_ATTESTATION_IDS.forEach((attestationId) => {
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

// Кампания выбирается автоматически: единственная или последняя активная.
// Если активных кампаний нет — честное сообщение со ссылкой на создание.
function autoSelectCampaign(form, panel) {
  const note = q("[data-generation-intake-campaign-note]", panel);
  const campaign = form.elements?.campaign_id;
  const options = campaign instanceof HTMLSelectElement
    ? [...campaign.options].filter((option) => (
      UUID_PATTERN.test(String(option.value || "").trim().toLowerCase())
    ))
    : [];
  if (!options.length) {
    if (note instanceof HTMLElement) note.hidden = false;
    return "";
  }
  if (note instanceof HTMLElement) note.hidden = true;
  const target = options[options.length - 1];
  if (campaign.value !== target.value) {
    campaign.value = target.value;
    campaign.dispatchEvent(new Event("input", { bubbles: true }));
    campaign.dispatchEvent(new Event("change", { bubbles: true }));
  }
  return String(target.value).trim().toLowerCase();
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
async function driveStrategyPreflight(initialForm, panel) {
  const deadline = Date.now() + EXPRESS_PREFLIGHT_TIMEOUT_MS;
  let blockedPolls = 0;
  let stalledPolls = 0;
  let lastSignature = "";
  let lastReportedStep = "";
  while (Date.now() < deadline) {
    const form = liveGenerationForm(initialForm);
    const submitButton = q("#generation-submit", form);
    if (!(submitButton instanceof HTMLButtonElement)) {
      throw new Error("express_submit_missing");
    }
    if (form.dataset.generationStrategyConfirmationReady === "true") {
      return serverPriceLabel(form);
    }
    const signature = preflightSignature(form, submitButton);
    if (signature !== lastSignature) {
      stalledPolls = 0;
      lastSignature = signature;
    }
    if (form.dataset.busy === "true") {
      blockedPolls = 0;
      stalledPolls = 0;
      await waitMs(EXPRESS_POLL_INTERVAL_MS);
      continue;
    }
    const missingAttestations = applyConsolidatedRights(form, panel);
    if (missingAttestations.length) {
      const failure = new Error("express_attestations_unavailable");
      failure.missingAttestations = missingAttestations;
      throw failure;
    }
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
        panel,
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
        throw failure;
      }
      probe.click();
      await waitMs(EXPRESS_POLL_INTERVAL_MS);
    } else if (
      !submitButton.disabled
      && EXPRESS_FREE_SUBMIT_PHASES.includes(phase)
    ) {
      blockedPolls = 0;
      stalledPolls += 1;
      if (stalledPolls >= EXPRESS_STALLED_POLL_LIMIT) {
        const failure = new Error("express_preflight_stalled");
        failure.step = step;
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
        throw failure;
      }
    }
    await waitMs(EXPRESS_POLL_INTERVAL_MS);
  }
  throw new Error("express_preflight_timeout");
}

function priceButtonFor(panel) {
  return q('[data-action="generation-intake-prepare-copy"]', panel);
}

// Двухфазная кнопка: «Показать цену» после бесплатного preflight превращается
// в «Запустить за $X». Платный старт происходит только по этому явному клику.
function syncExpressPriceButton(state) {
  const panel = panelFor(state, "copy_video");
  const button = panel ? priceButtonFor(panel) : null;
  if (!(button instanceof HTMLButtonElement)) return;
  const priced = state.express?.phase === "priced" && state.express.price;
  button.dataset.expressPhase = priced ? "priced" : "idle";
  setNodeText(
    button,
    priced ? `Запустить за ${state.express.price}` : "Подготовить ролик",
  );
}

function setExpressPricePhase(state, price, spendConfirmation) {
  state.express = {
    ...state.express,
    phase: price ? "priced" : "idle",
    price: price || "",
    spend_confirmation: price ? String(spendConfirmation || "") : "",
  };
  syncExpressPriceButton(state);
}

function resetExpressPrice(state) {
  if (state.express?.phase !== "priced") return;
  setExpressPricePhase(state, "", "");
}

function rememberExpressDefaults(state) {
  const panel = panelFor(state, "copy_video");
  if (!panel) return;
  expressDefaultsMemory.set(projectId(), {
    audio: String(q('[data-generation-intake-field="audio"]', panel)?.value || ""),
    sku: String(identityInput(state, "sku")?.value || ""),
    product_name: String(identityInput(state, "product_name")?.value || ""),
    product_category: String(identityInput(state, "product_category")?.value || ""),
    rights: q('[data-generation-intake-rights="copy_video"]', panel)?.checked === true,
  });
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

// Владелец просил предзаполненный текст «что надо сделать»: пустой замысел
// сразу получает базовую рекомендацию, правки человека не перезаписываются.
function prefillCopyRecommendation(form, state) {
  const brief = form.elements?.brief;
  if (!(brief instanceof HTMLTextAreaElement)) return;
  if (String(brief.value || "").trim()) return;
  if (state.express?.recommendationPrefilled) return;
  state.express = { ...state.express, recommendationPrefilled: true };
  brief.value = DEFAULT_RECOMMENDATIONS.copy_video;
  brief.dispatchEvent(new Event("input", { bubbles: true }));
  brief.dispatchEvent(new Event("change", { bubbles: true }));
}

function persistHandoff(form, handoff) {
  setHidden(form, "generation_intake_version", HANDOFF_VERSION);
  setHidden(form, "generation_intake_route", handoff.route);
  setHidden(form, "generation_intake_source_media_id", handoff.source_media_id || "");
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

function ensureProductCheckbox(form, state, mediaId, identity, filename) {
  const existing = existingMediaCheckbox(form, mediaId);
  if (existing instanceof HTMLInputElement) {
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
  host.append(option);
  input.dispatchEvent(new Event("change", { bubbles: true }));
  return input;
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
      if (input.checked && !real.disabled && !real.checked) {
        real.checked = true;
        real.dispatchEvent(new Event("change", { bubbles: true }));
      }
      input.closest("[data-generation-intake-synthetic]")?.remove();
    });
}

function bindRoleAsset(form, role, mediaId) {
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

async function openNativeLaunch(form, handoff) {
  const state = formStates.get(form);
  if (state) state.phase = "review";
  // На отдельном экране копии движок остаётся невидимым: режим не
  // переключается в "full", пять блоков не разъезжаются по шагам мастера.
  const copyScreen = copyViewActive();
  form.dataset.generationIntakeV4Mode = copyScreen ? "copy" : "full";
  form.dataset.generationIntakeV4Phase = "review";
  form.dataset.generationIntakeV4Route = handoff.route;
  if (!copyScreen) {
    moveProductNodes(form, state, false);
    moveSharedBrief(form, state, "strategy_video");
  }
  selectStrategy(form, handoff.strategy_id);
  await window.ContentEngineGenerationGuidedV4
    ?.refreshStrategyAssets?.(form);
  applyCompactPreferences(form, handoff);
  let missing = handoff.assets.filter(
    ({ role, media_id: mediaId }) => !bindRoleAsset(form, role, mediaId),
  );
  if (missing.length) {
    // Кандидаты могли дорисоваться асинхронно после refreshStrategyAssets —
    // одна повторная попытка с небольшой паузой.
    await new Promise((resolve) => { setTimeout(resolve, 700); });
    missing = missing.filter(
      ({ role, media_id: mediaId }) => !bindRoleAsset(form, role, mediaId),
    );
  }
  // Серверное ТЗ требует «Главное фото» (primary_media_id); компактная форма
  // выбирает его автоматически — первое фото нового товара.
  const firstProduct = handoff.assets.find(
    ({ role }) => role === "new_product_image",
  );
  if (firstProduct) {
    const primary = qa('input[name="primary_media_id"]', form).find(
      (radio) => radio.value === firstProduct.media_id,
    );
    if (primary && !primary.checked && !primary.disabled) primary.click();
  }
  if (!copyScreen) {
    q('[data-ce-v4-generation-target="media"]', form)?.click?.();
    requestAnimationFrame(() => {
      q(".generation-strategy-view", form)?.scrollIntoView?.({
        behavior: "smooth",
        block: "start",
      });
    });
  }
  return missing.map(({ role }) => role);
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

// Проверка длительности сразу после выбора файла: раньше несоответствие
// вскрывалось только при подготовке, и выбранный ролик отвергался молча.
async function reportSelectedSourceDuration(state, route, input) {
  const panel = panelFor(state, route);
  const file = input?.files?.[0];
  if (!panel || !(file instanceof File)) return;
  const limit = route === "copy_video" ? MAX_COPY_DURATION : MAX_AVATAR_DURATION;
  const nextStep = copyViewActive() && route === "copy_video"
    ? "«Подготовить ролик»"
    : "«Разобрать MP4»";
  const unreadable = `Браузер не смог измерить длительность этого файла. Нажмите ${nextStep} — форма проверит файл ещё раз и назовёт точную причину.`;
  let metadata = null;
  try {
    metadata = await videoMetadata(file);
  } catch {
    // Пока читались метаданные, человек мог выбрать другой файл.
    if (input.files?.[0] === file) setStatus(panel, unreadable, "warning");
    return;
  }
  if (input.files?.[0] !== file) return;
  const seconds = Number(metadata?.duration);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    setStatus(panel, unreadable, "warning");
    return;
  }
  const routeState = state.routes?.[route];
  if (routeState) routeState.durationSeconds = seconds;
  if (seconds > limit + 0.05) {
    setStatus(panel, durationTooLongMessage(seconds, limit), "error");
    return;
  }
  if (route === "copy_video" && seconds < MIN_COPY_DURATION - 0.05) {
    setStatus(panel, durationTooShortMessage(seconds), "error");
    return;
  }
  setStatus(
    panel,
    copyViewActive() && route === "copy_video"
      ? `MP4 выбран · ${secondsLabel(seconds)} из допустимых ${limit} с. Нажмите «Подготовить ролик» — разбор и бесплатная проверка выполнятся автоматически.`
      : `MP4 выбран · ${secondsLabel(seconds)} из допустимых ${limit} с. Нажмите «Разобрать MP4».`,
    "ready",
  );
}

async function analyzeRoute(form, route) {
  const state = formStates.get(form);
  const panel = panelFor(state, route);
  if (!state || !panel || state.busy) return;
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
  state.busy = true;
  setStatus(panel, "Проверяем MP4 и собираем storyboard…", "busy");
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
    q(`[data-action="generation-intake-prepare-${route === "copy_video" ? "copy" : "avatar"}"]`, panel).disabled = false;
    setStatus(
      panel,
      route === "copy_video"
        ? `${metadata.duration.toFixed(1)} с · ${metadata.width}×${metadata.height} · ${STORYBOARD_FRAME_COUNT} кадров. Проверьте предложенный кадр исходного товара и нажмите «Показать цену».`
        : `${metadata.duration.toFixed(1)} с · ${metadata.width}×${metadata.height}. Исходный ролик готов; теперь задайте аватара фотографией или описанием.`,
      "ready",
    );
  } catch (error) {
    const limit = route === "copy_video" ? MAX_COPY_DURATION : MAX_AVATAR_DURATION;
    const messages = {
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
  } finally {
    state.busy = false;
  }
}

async function ensureSourceMedia(routeState) {
  if (UUID_PATTERN.test(routeState.sourceMediaId || "")) {
    const api = await apiRuntime();
    await attachDirectMp4(api, routeState.sourceMediaId);
    return routeState.sourceMediaId;
  }
  if (!(routeState.sourceFile instanceof File)) {
    throw new Error("source_media_required");
  }
  routeState.sourceMediaId = await uploadProjectMedia(
    routeState.sourceFile,
    "source_video",
  );
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
  const state = formStates.get(initialForm);
  const panel = panelFor(state, "copy_video");
  if (!state || !panel || state.busy) return;
  const express = state.express || {};
  if (express.phase !== "priced") {
    void prepareCopy(initialForm);
    return;
  }
  state.busy = true;
  try {
    // Мастер мог быть перерисован после получения цены: и подтверждение
    // списания, и кнопка запуска берутся из живой формы, иначе клик уйдёт в
    // отсоединённый узел и платный старт молча не случится.
    const form = liveGenerationForm(initialForm);
    const campaignId = autoSelectCampaign(form, panel);
    if (!campaignId) {
      setStatus(
        panel,
        "Платный запуск невозможен: в проекте нет активной кампании. Создайте её по ссылке выше и вернитесь.",
        "error",
      );
      return;
    }
    const confirmation = form.elements?.real_spend_confirmation;
    const submitButton = q("#generation-submit", form);
    if (
      form.dataset.generationStrategyConfirmationReady !== "true"
      || !(confirmation instanceof HTMLInputElement)
      || confirmation.disabled
      || !confirmation.value
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
    if (confirmation.checked !== true) {
      setStatus(
        panel,
        "Не удалось поставить подтверждение списания. Отметьте его вручную в мастере ниже.",
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
  } finally {
    state.busy = false;
  }
}

async function prepareCopy(form) {
  const state = formStates.get(form);
  let route = state?.routes.copy_video;
  const panel = panelFor(state, "copy_video");
  if (!state || !route || !panel || state.busy) return;
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
    setStatus(panel, "Добавьте рекомендацию или явно примените предложенный базовый вариант.", "error");
    return;
  }
  if (recommendation.length > BRIEF_LIMIT) {
    setStatus(panel, `Сократите рекомендацию до ${BRIEF_LIMIT} символов. Текст не был обрезан.`, "error");
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
  state.busy = true;
  setStatus(panel, "Проверяем фотографии, загружаем MP4 и готовим кадр исходного товара…", "busy");
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
      ensureProductCheckbox(
        form,
        state,
        mediaId,
        productIdentity,
        productFiles[index]?.name,
      );
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
    const assets = [
      { role: "source_video", media_id: sourceMediaId },
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
    const missingRoles = await openNativeLaunch(form, handoff);
    const missingLabels = [...new Set(missingRoles || [])]
      .map((role) => ASSET_ROLE_LABELS[role] || role);
    if (missingLabels.length) {
      setStatus(
        panel,
        `Материалы загружены, но не привязались автоматически: ${missingLabels.join(", ")}. Отметьте их вручную в шаге «Исходники» — без этого запуск заблокирован.`,
        "warning",
      );
      return;
    }
    if (!originalProductMediaId) {
      setStatus(
        panel,
        "Не удалось получить кадр исходного товара автоматически. Один шаг: загрузите локальный MP4 этого ролика — форма сама выберет лучший кадр и доведёт до цены.",
        "warning",
      );
      return;
    }
    setStatus(
      panel,
      "Материалы привязаны. Бесплатно получаем точную серверную цену — провайдер не запускается и деньги не списываются…",
      "busy",
    );
    const price = await driveStrategyPreflight(form, panel);
    // Мастер мог быть перерисован за время бесплатной проверки: подпись
    // списания и кампания читаются из живой формы, а не из устаревшего узла.
    const pricedForm = liveGenerationForm(form);
    const spendConfirmation = String(
      pricedForm.elements?.real_spend_confirmation?.value || "",
    );
    const campaignId = autoSelectCampaign(pricedForm, panel);
    setExpressPricePhase(state, price, spendConfirmation);
    if (!price) {
      setStatus(
        panel,
        "Сервер подтвердил готовность, но цена не отобразилась. Проверьте цену в мастере ниже перед запуском.",
        "warning",
      );
    } else if (!campaignId) {
      setStatus(
        panel,
        `Точная цена: ${price}, деньги не списаны. Для запуска нужна активная кампания — создайте её по ссылке выше.`,
        "warning",
      );
    } else {
      setStatus(
        panel,
        `Точная цена: ${price}. Деньги не списаны. Кнопка «Запустить за ${price}» и есть подтверждение цены — запуск случится только после вашего клика.`,
        "success",
      );
    }
  } catch (error) {
    console.warn("Copy Product Swap preparation failed", error);
    if (error?.message === "express_attestations_unavailable") {
      const labels = (error.missingAttestations || [])
        .map((id) => COPY_ATTESTATION_LABELS[id] || id);
      setStatus(
        panel,
        `Не удалось автоматически проставить подтверждения прав: ${labels.join(", ")}. Отметьте их вручную в шаге «Исходники» — без них запуск честно заблокирован.`,
        "error",
      );
      return;
    }
    if (error?.message === "express_preflight_blocked") {
      setStatus(
        panel,
        `Бесплатная проверка остановилась: ${error.blocker || "мастер сообщил о блокировке"} Деньги не списаны.`,
        "error",
      );
      return;
    }
    if (error?.message === "express_preflight_timeout") {
      setStatus(
        panel,
        "Сервер долго готовит цену. Ничего не списано; нажмите «Показать цену» ещё раз.",
        "error",
      );
      return;
    }
    if (error?.message === "express_preflight_stalled") {
      setStatus(
        panel,
        `Мастер не отвечает на бесплатную проверку${error.step ? `: шаг «${error.step}» не сдвигается` : ""}. Ничего не запущено и не оплачено. Обновите страницу (F5) и нажмите «Подготовить ролик» ещё раз — выбранные материалы сохранены.`,
        "error",
      );
      return;
    }
    if (error?.message === "express_submit_missing") {
      setStatus(
        panel,
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
    };
    setStatus(
      panel,
      messages[error?.message] || "Не удалось подготовить материалы. Ничего не запущено и не оплачено.",
      "error",
    );
  } finally {
    state.busy = false;
  }
}

async function prepareAvatar(form) {
  const state = formStates.get(form);
  const route = state?.routes.avatar_video;
  const panel = panelFor(state, "avatar_video");
  if (!state || !route || !panel || state.busy) return;
  const mode = avatarInputMode(panel);
  const avatarWishes = mode === "description" ? currentAvatarWishes(panel) : "";
  const avatarFile = mode === "photo" ? selectedAvatarFile(panel) : null;
  const existingAvatarMediaId = mode === "photo" ? selectedAvatarMediaId(panel) : "";
  const recommendation = currentRecommendation(form);
  const rights = q('[data-generation-intake-rights="avatar_video"]', panel)?.checked === true;
  const likenessConsent = q("[data-generation-intake-avatar-consent]", panel)?.checked === true;
  if (!rights) {
    setStatus(panel, "Подтвердите право использовать исходный ролик.", "error");
    return;
  }
  if (!recommendation) {
    setStatus(panel, "Добавьте рекомендацию или явно примените предложенный базовый вариант.", "error");
    return;
  }
  if (recommendation.length > BRIEF_LIMIT) {
    setStatus(panel, `Сократите рекомендацию до ${BRIEF_LIMIT} символов. Текст не был обрезан.`, "error");
    return;
  }
  if (mode === "photo" && Boolean(avatarFile) === Boolean(existingAvatarMediaId)) {
    setStatus(panel, "Выберите ровно одно фото аватара: новое или уже сохранённое в проекте.", "error");
    return;
  }
  if (mode === "photo" && !likenessConsent) {
    setStatus(panel, "Подтвердите согласие на использование внешности.", "error");
    return;
  }
  if (mode === "description" && avatarWishes.length < 10) {
    setStatus(panel, "Опишите аватара хотя бы одним понятным предложением.", "error");
    return;
  }
  state.busy = true;
  setStatus(panel, "Проверяем аватара и сохраняем подготовку…", "busy");
  try {
    if (avatarFile) await assertImage(avatarFile);
    const sourceMediaId = await ensureSourceMedia(route);
    const avatarMediaId = avatarFile
      ? await uploadProjectMedia(avatarFile, "creator_reference")
      : existingAvatarMediaId;
    const handoff = {
      version: HANDOFF_VERSION,
      route: "avatar_video",
      paid_authority: PAID_AUTHORITY,
      strategy_id: "character_performance",
      source_media_id: sourceMediaId,
      original_product_media_id: "",
      avatar_media_id: avatarMediaId,
      avatar_mode: mode,
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
      launch_enabled: false,
    };
    persistHandoff(form, handoff);
    setStatus(
      panel,
      "MP4 и пожелания сохранены. Character Performance не подменяется Product UGC: платная стадия станет доступна только после включения отдельного provider-adapter.",
      "success",
    );
  } catch (error) {
    console.warn("Avatar preparation failed", error);
    const messages = {
      image_required: "Выберите корректное фото аватара.",
      image_too_large: "Фото аватара больше 16 МБ.",
      image_type_invalid: "Фото аватара должно быть JPG, PNG или WEBP.",
      image_signature_invalid: "Расширение фото не совпадает с его содержимым.",
      image_dimensions_too_small: "Фото аватара должно быть не меньше 256×256 пикселей.",
      source_media_required: "Сначала выберите и разберите исходный MP4.",
    };
    setStatus(
      panel,
      messages[error?.message] || "Не удалось сохранить подготовку аватара. Ничего не запущено и не оплачено.",
      "error",
    );
  } finally {
    state.busy = false;
  }
}

async function uploadStrategySources(form) {
  const state = formStates.get(form);
  const panel = panelFor(state, "strategy_video");
  const input = q('input[data-generation-intake-mp4="strategy"]', panel);
  const files = [...(input?.files || [])];
  if (!state || !panel || state.busy) return;
  if (!files.length) {
    setStatus(panel, "Выберите один или несколько MP4.", "error");
    return;
  }
  if (files.length > MAX_STRATEGY_FILES) {
    setStatus(panel, `Можно добавить не больше ${MAX_STRATEGY_FILES} MP4 за один раз.`, "error");
    return;
  }
  state.busy = true;
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
      strategy_id: STRATEGY_AUTHORITY_STRATEGY,
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
    selectStrategy(form, STRATEGY_AUTHORITY_STRATEGY);
    await window.ContentEngineGenerationGuidedV4
      ?.refreshStrategyAssets?.(form);
    mediaIds.forEach((mediaId) => {
      bindRoleAsset(form, "source_video", mediaId);
    });
    setStatus(
      panel,
      `${mediaIds.length} MP4 добавлено в проект и выбрано в полном конструкторе. Бесплатная проверка длительности остаётся обязательной перед запуском.`,
      "success",
    );
    input.value = "";
    q('[data-ce-v4-generation-target="media"]', form)?.click?.();
    refreshVideoSelects(form, state);
  } catch (error) {
    console.warn("Strategy MP4 upload failed", error);
    setStatus(panel, "Загрузка остановлена. Уже добавленные исходники остаются в проекте; платный запуск не выполнялся.", "error");
  } finally {
    state.busy = false;
  }
}

function setRoute(form, state, route) {
  if (!DEFAULT_RECOMMENDATIONS[route] && route !== "strategy_video") return;
  state.route = route;
  state.phase = "edit";
  form.dataset.generationIntakeV4Route = route;
  form.dataset.generationIntakeV4Phase = "edit";
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
  const compact = route !== "strategy_video";
  form.dataset.generationIntakeV4Mode = copyViewActive()
    ? "copy"
    : compact
      ? "compact"
      : "full";
  moveProductNodes(form, state, route === "copy_video");
  moveSharedBrief(form, state, route);
  qa("[data-generation-intake-panel]", state.shell).forEach((panel) => {
    setPanelControlsActive(panel, panel.dataset.generationIntakePanel === route);
  });
  // Переключение вкладки маршрута не выбирает стратегию: выбор необратим и
  // происходит только по кнопкам «Подготовить…» (openNativeLaunch) или
  // загрузки исходников стратегии. Так dry-run остаётся доступным, а платная
  // стратегия не активируется случайным кликом по вкладке.
  if (route === "copy_video") {
    prefillIdentityFields(form, state);
    applyExpressDefaults(form, state);
    prefillCopyRecommendation(form, state);
    refreshIdentityVisibility(form, state);
    syncExpressPriceButton(state);
    syncCopyScreenChrome(state);
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
      setRoute(form, state, routeButtonNode.dataset.generationIntakeRoute);
      return;
    }
    const action = event.target.closest?.("[data-action]")?.dataset.action;
    if (action === "generation-intake-analyze-copy") void analyzeRoute(form, "copy_video");
    if (action === "generation-intake-analyze-avatar") void analyzeRoute(form, "avatar_video");
    if (action === "generation-intake-prepare-copy") {
      // Двухфазная кнопка цены: idle → бесплатная подготовка и цена,
      // priced → явный платный запуск «Запустить за $X».
      const trigger = event.target.closest?.("[data-action]");
      if (trigger?.dataset.expressPhase === "priced") void startExpressLaunch(form);
      else void prepareCopy(form);
    }
    if (action === "generation-intake-prepare-avatar") void prepareAvatar(form);
    if (action === "generation-intake-upload-strategy") void uploadStrategySources(form);
    if (action === "generation-intake-apply-recommendation") {
      const route = String(event.target.closest?.("[data-route]")?.dataset.route || state.route);
      const brief = form.elements?.brief;
      if (
        brief instanceof HTMLTextAreaElement
        && !String(brief.value || "").trim()
        && DEFAULT_RECOMMENDATIONS[route]
      ) {
        brief.value = DEFAULT_RECOMMENDATIONS[route];
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
        // Длительность проверяется сразу: слишком длинный ролик обязан получить
        // видимый отказ с цифрами, а не молча остаться в поле.
        if (input.files?.length) {
          void reportSelectedSourceDuration(state, route, input);
        }
      }
    }

    const existingVideo = event.target.closest?.("[data-generation-intake-existing-video]");
    if (existingVideo instanceof HTMLSelectElement) {
      const route = existingVideo.dataset.generationIntakeExistingVideo;
      const panel = panelFor(state, route);
      const fileInput = q('input[data-generation-intake-mp4="single"]', panel);
      if (existingVideo.value && fileInput instanceof HTMLInputElement) fileInput.value = "";
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
              ? "Ролик проекта выбран. Нажмите «Показать цену» — проверка выполнится автоматически."
              : "Ролик проекта выбран. Нажмите «Разобрать MP4»."
            : "Выберите исходный MP4.",
          "neutral",
        );
      }
    }

    const productFileInput = event.target.closest?.('[data-generation-intake-image="product"]');
    const productCheckbox = event.target.closest?.('input[name="media_id"]');
    if (productFileInput || productCheckbox) {
      refreshProductSelectionCount(form, state);
      refreshIdentityVisibility(form, state);
    }
    // Выбранные файлы сразу уходят в серверную регистрацию и очередь;
    // отмеченные чипы персистятся в sessionStorage по проекту.
    if (productFileInput) void registerSelectedProductPhotos(form, state);
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

    // Каскад «уровень → модель → тайминги». Смена уровня снимает модель, смена
    // модели снимает прежнее предупреждение о длительности: каждая ступень
    // перерисовывает следующую, а не оставляет её от прошлого выбора.
    const tierChoice = event.target.closest?.('input[name="generation_intake_tier"]');
    if (tierChoice instanceof HTMLInputElement && tierChoice.checked) {
      state.copyEngine = {
        tier: String(tierChoice.value || ""),
        modelId: "",
        durationNotice: "",
      };
      refreshEngineChoice(form, state);
    }
    const engineChoice = event.target.closest?.(
      'input[name="generation_intake_generator"]',
    );
    if (engineChoice instanceof HTMLInputElement && engineChoice.checked) {
      state.copyEngine = {
        ...(state.copyEngine || {}),
        modelId: String(engineChoice.value || ""),
        durationNotice: "",
      };
      refreshEngineChoice(form, state);
    }
    const durationChoice = event.target.closest?.(
      'input[name="generation_intake_duration"]',
    );
    if (durationChoice instanceof HTMLInputElement && durationChoice.checked) {
      state.copyEngine = { ...(state.copyEngine || {}), durationNotice: "" };
      applyCopyDuration(form, Number(durationChoice.value));
      refreshEngineChoice(form, state);
    }

    if (event.target === form.elements?.brief) refreshRecommendationUi(form, state);

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
    if (event.target === form.elements?.brief) refreshRecommendationUi(form, state);
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
}

function mount(form) {
  if (!(form instanceof HTMLFormElement)) return;
  const existing = formStates.get(form);
  if (existing?.shell?.isConnected) {
    if (existing.shell.parentElement !== form) {
      const guidedShell = q("[data-ce-v4-generation-guided-shell]", form);
      if (guidedShell?.parentElement === form) guidedShell.before(existing.shell);
      else form.prepend(existing.shell);
    }
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
        syncExpressPriceButton(existing);
      }
    } else if (existing.phase === "review") {
      moveProductNodes(form, existing, false);
      moveSharedBrief(form, existing, "strategy_video");
    }
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
    productUploadBusy: false,
    requestedModel: "",
    // Выбор каскада «Копии»: уровень, модель и последнее объяснение того,
    // почему длительность была приведена к допустимой.
    copyEngine: { tier: "", modelId: "", durationNotice: "" },
    express: {
      phase: "idle",
      price: "",
      spend_confirmation: "",
      recommendationPrefilled: false,
    },
    productNodes: [],
    briefControl,
    briefField,
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
  setRoute(form, state, "copy_video");
  if (copyViewActive()) {
    ensureCopyEngineStrategy(form);
    restoreCopyPhotoSelection(form, state);
  }
  syncCopyScreenChrome(state);
}

function scheduleMount() {
  if (mountQueued) return;
  mountQueued = true;
  queueMicrotask(() => {
    mountQueued = false;
    if (routePath() !== ROUTE) return;
    const form = q("#mock-batch-form");
    if (form) mount(form);
  });
}

window.addEventListener("hashchange", scheduleMount);
window.addEventListener("contentengine:rendered", scheduleMount);
window.addEventListener("contentengine:generation-research-preset-applied", scheduleMount);
window.addEventListener("contentengine:generation-research-preset-opt-out", scheduleMount);
new MutationObserver(scheduleMount).observe(document.documentElement, {
  childList: true,
  subtree: true,
});
scheduleMount();

export {
  HANDOFF_VERSION,
  MAX_STRATEGY_FILES,
  PAID_AUTHORITY,
  COPY_AUTHORITY_STRATEGY,
  assertMp4,
  captureStoryboard,
  selectedProductMediaIds,
};
