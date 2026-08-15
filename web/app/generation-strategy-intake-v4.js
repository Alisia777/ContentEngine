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
  "./generation-strategy-intake-v4.css?v=20260815.mp4.6",
  import.meta.url,
).href;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const MAX_COPY_DURATION = 15;
const MIN_COPY_DURATION = 4;
const MAX_AVATAR_DURATION = 30;
const MAX_STRATEGY_FILES = 10;
const MAX_MP4_BYTES = 32 * 1024 * 1024;
const STORYBOARD_FRAME_COUNT = 8;
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
    "generation_intake_product_media_ids",
    "generation_intake_reference_media_ids",
    "generation_intake_source_url",
    "generation_intake_description",
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

function descriptionField(route) {
  const textarea = document.createElement("textarea");
  textarea.rows = 4;
  textarea.maxLength = 1_200;
  textarea.placeholder = route === "copy_video"
    ? "Оставьте пустым для максимально близкого повторения механики ролика."
    : "Можно уточнить голос, характер, одежду или ограничения.";
  textarea.dataset.generationIntakeField = "description";
  return field(
    "Дополнительное описание — по желанию",
    route === "copy_video"
      ? "По умолчанию сохраняются действия, ракурсы, темп, монтаж и исходный звук; меняется товар."
      : "Основные движения и темп берутся из MP4.",
    textarea,
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

function setStatus(panel, text, state = "neutral") {
  const status = q("[data-generation-intake-status]", panel);
  if (!status) return;
  status.dataset.state = state;
  status.textContent = text;
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

function sourceChooser(route) {
  const box = el("section", "generation-intake-v4__source");
  box.dataset.generationIntakeSource = route;
  const input = mp4Input();
  input.id = `generation-intake-${route}-mp4`;
  const label = el("label", "generation-intake-v4__drop");
  label.htmlFor = input.id;
  label.append(
    el("strong", "", "Загрузить MP4"),
    el("span", "", "или выберите уже загруженный ролик проекта ниже"),
    input,
  );
  const select = document.createElement("select");
  select.dataset.generationIntakeExistingVideo = route;
  select.append(new Option("Не выбран файл проекта", ""));
  box.append(
    el("h4", "", "Исходный ролик *"),
    label,
    field(
      "MP4 из файлов проекта",
      "В списке показываются только видеоматериалы текущего проекта, которые удаётся однозначно распознать в интерфейсе.",
      select,
    ),
  );
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

function productSlot() {
  const section = el("section", "generation-intake-v4__product");
  section.dataset.generationIntakeProductSlot = "";
  section.append(
    el("h4", "", "Фото вашего товара *"),
    el(
      "p",
      "muted tiny",
      "Можно выбрать до 10 точных ракурсов одного товара. Они передаются как newProductImages Product Swap.",
    ),
    el("div", "generation-intake-v4__product-items"),
  );
  return section;
}

function copyPanel() {
  const panel = el("section", "generation-intake-v4__panel");
  panel.dataset.generationIntakePanel = "copy_video";
  panel.hidden = true;
  const actions = el("div", "generation-intake-v4__actions");
  const analyze = el("button", "btn", "Разобрать MP4");
  analyze.type = "button";
  analyze.dataset.action = "generation-intake-analyze-copy";
  const prepare = el("button", "btn btn-primary", "Подготовить Product Swap");
  prepare.type = "button";
  prepare.dataset.action = "generation-intake-prepare-copy";
  prepare.disabled = true;
  actions.append(analyze, prepare);
  panel.append(
    routeHeader(
      "ОТДЕЛЬНАЯ ФОРМА",
      "Скопировать ролик",
      "Повторяем механику исходного MP4 и заменяем товар на ваш.",
      "Product Swap",
    ),
    sourceChooser("copy_video"),
    productSlot(),
    optionalSourceUrl(),
    descriptionField("copy_video"),
    storyboardNode(),
    statusNode(),
    actions,
  );
  return panel;
}

function avatarPanel() {
  const panel = el("section", "generation-intake-v4__panel");
  panel.dataset.generationIntakePanel = "avatar_video";
  panel.hidden = true;
  const wishes = document.createElement("textarea");
  wishes.rows = 5;
  wishes.maxLength = 1_200;
  wishes.required = true;
  wishes.placeholder = "Например: уверенная девушка 25–30 лет, тёмные волосы, чёрный лаконичный образ, спокойная живая мимика…";
  wishes.dataset.generationIntakeField = "avatar_wishes";
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
      "Создаём героя по описанию и переносим на него движения исходного MP4.",
      "Character Performance",
    ),
    field(
      "Каким должен быть аватар *",
      "Внешность, возрастной образ, одежда, настроение и манера движения. Технический промпт не нужен.",
      wishes,
    ),
    sourceChooser("avatar_video"),
    optionalSourceUrl(),
    descriptionField("avatar_video"),
    storyboardNode(),
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
    .filter((input) => !String(input.dataset.mimeType || "").startsWith("video/"))
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
    if (!state.productNodes.length) {
      collectProductNodes(form).forEach((node) => {
        const marker = document.createComment("generation-intake-v4-product-origin");
        node.before(marker);
        state.productNodes.push({ node, marker });
      });
    }
    state.productNodes.forEach(({ node }) => slot.append(node));
    if (!state.productNodes.length && !q("[data-generation-intake-empty-product]", slot)) {
      const warning = el("div", "alert alert-warning", "В проекте пока нет доступных фотографий товара.");
      warning.dataset.generationIntakeEmptyProduct = "";
      slot.append(warning);
    }
    return;
  }
  state.productNodes.forEach(({ node, marker }) => {
    if (marker.isConnected) marker.replaceWith(node);
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

function refreshVideoSelects(form, state) {
  const videos = collectProjectVideos(form);
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
  });
}

function selectedProductMediaIds(form) {
  const result = [];
  const seen = new Set();
  const productRoot = q(".generation-intake-v4__product-items", form);
  qa('input[name="media_id"]:checked:not(:disabled)', productRoot).forEach((input) => {
    const id = String(input.value || "").trim().toLowerCase();
    if (!UUID_PATTERN.test(id) || seen.has(id)) return;
    seen.add(id);
    result.push(id);
  });
  return result.slice(0, 10);
}

async function sha256Hex(blob) {
  const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function assertMp4(file, maximumDuration) {
  if (!(file instanceof File) || file.size < 32) throw new Error("mp4_required");
  if (file.size > MAX_MP4_BYTES) throw new Error("mp4_too_large");
  const head = new Uint8Array(await file.slice(0, 64).arrayBuffer());
  const signature = new TextDecoder("latin1").decode(head);
  if (!signature.includes("ftyp")) throw new Error("mp4_signature_invalid");
  const metadata = await videoMetadata(file);
  if (!Number.isFinite(metadata.duration) || metadata.duration <= 0) {
    throw new Error("mp4_duration_invalid");
  }
  if (metadata.duration > maximumDuration + 0.05) throw new Error("mp4_duration_too_long");
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
  await new Promise((resolve, reject) => {
    video.onloadedmetadata = resolve;
    video.onerror = () => reject(new Error("mp4_storyboard_invalid"));
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

async function registerUploadedMedia(api, file, objectKey, kind, sha256) {
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
    rights_confirmed: true,
  });
  const mediaId = findUuid(response);
  if (!mediaId) throw new Error("register_media_response_invalid");
  return mediaId;
}

async function uploadProjectMedia(file, kind) {
  const api = await apiRuntime();
  if (typeof api.uploadPrivateObject !== "function") {
    throw new Error("private_upload_unavailable");
  }
  const sha256 = await sha256Hex(file);
  const objectKey = privateObjectKey(api, file, kind);
  await api.uploadPrivateObject(objectKey, file);
  let mediaId = "";
  try {
    mediaId = await registerUploadedMedia(api, file, objectKey, kind, sha256);
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

function persistHandoff(form, handoff) {
  setHidden(form, "generation_intake_version", HANDOFF_VERSION);
  setHidden(form, "generation_intake_route", handoff.route);
  setHidden(form, "generation_intake_source_media_id", handoff.source_media_id || "");
  setHidden(form, "generation_intake_original_product_media_id", handoff.original_product_media_id || "");
  setHidden(form, "generation_intake_product_media_ids", handoff.product_media_ids || []);
  setHidden(form, "generation_intake_reference_media_ids", handoff.reference_media_ids || []);
  setHidden(form, "generation_intake_source_url", handoff.source_url || "");
  setHidden(form, "generation_intake_description", handoff.description || "");
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
  form.dataset.generationIntakeV4Mode = "full";
  selectStrategy(form, handoff.strategy_id);
  await window.ContentEngineGenerationGuidedV4
    ?.refreshStrategyAssets?.(form);
  handoff.assets.forEach(({ role, media_id: mediaId }) => {
    bindRoleAsset(form, role, mediaId);
  });
  q('[data-ce-v4-generation-target="media"]', form)?.click?.();
  requestAnimationFrame(() => {
    q(".generation-strategy-view", form)?.scrollIntoView?.({
      behavior: "smooth",
      block: "start",
    });
  });
}

function frameAsFile(frame, route) {
  return new File(
    [frame.blob],
    `${route}-original-product-${frame.time.toFixed(2).replace(".", "-")}.jpg`,
    { type: "image/jpeg", lastModified: Date.now() },
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
        ? "Ролик проекта выбран. Для автоматического извлечения кадра товара загрузите локальный MP4 или выберите original-product image в полном Product Swap."
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
    if (route === "copy_video" && metadata.duration < MIN_COPY_DURATION - 0.05) {
      throw new Error("mp4_duration_too_short");
    }
    const storyboard = await captureStoryboard(file);
    state.routes[route] = {
      ...state.routes[route],
      sourceFile: file,
      sourceMediaId: "",
      metadata,
      storyboard,
      selectedFrameIndex: storyboard.recommendedIndex,
    };
    renderStoryboard(panel, storyboard, state.routes[route]);
    q(`[data-action="generation-intake-prepare-${route === "copy_video" ? "copy" : "avatar"}"]`, panel).disabled = false;
    setStatus(
      panel,
      `${metadata.duration.toFixed(1)} с · ${metadata.width}×${metadata.height} · ${STORYBOARD_FRAME_COUNT} кадров. Выберите лучший кадр товара и продолжайте.`,
      "ready",
    );
  } catch (error) {
    const messages = {
      mp4_required: "Нужен настоящий MP4-файл.",
      mp4_too_large: "MP4 больше 32 МБ.",
      mp4_signature_invalid: "Файл не содержит корректную MP4/ISO-BMFF сигнатуру.",
      mp4_duration_too_long: `Ролик длиннее допустимых ${route === "copy_video" ? MAX_COPY_DURATION : MAX_AVATAR_DURATION} секунд.`,
      mp4_duration_too_short: `Для Product Swap нужен ролик не короче ${MIN_COPY_DURATION} секунд.`,
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

async function prepareCopy(form) {
  const state = formStates.get(form);
  const route = state?.routes.copy_video;
  const panel = panelFor(state, "copy_video");
  if (!state || !route || !panel || state.busy) return;
  const productMediaIds = selectedProductMediaIds(form);
  if (!productMediaIds.length) {
    setStatus(panel, "Выберите хотя бы одно точное фото вашего товара.", "error");
    return;
  }
  state.busy = true;
  setStatus(panel, "Загружаем MP4 и готовим original-product reference…", "busy");
  try {
    const sourceMediaId = await ensureSourceMedia(route);
    let originalProductMediaId = "";
    if (route.storyboard && Number.isInteger(route.selectedFrameIndex)) {
      const frame = route.storyboard.frames.find((item) => item.index === route.selectedFrameIndex);
      if (frame) {
        originalProductMediaId = await uploadProjectMedia(
          frameAsFile(frame, "copy"),
          "creator_reference",
        );
      }
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
      description: currentDescription(panel),
      preserve: ["actions", "camera", "timing", "editing", "audio"],
      replace: ["product"],
      assets,
      launch_enabled: Boolean(originalProductMediaId),
    };
    persistHandoff(form, handoff);
    if (originalProductMediaId) {
      setStatus(
        panel,
        "Product Swap подготовлен. Проверьте привязанные материалы, стоимость и запустите через действующий creator-generate.",
        "success",
      );
      await openNativeLaunch(form, handoff);
    } else {
      setStatus(
        panel,
        "MP4 и товар загружены. В полном Product Swap выберите отдельное фото исходного товара — без него платный запуск заблокирован.",
        "warning",
      );
      await openNativeLaunch(form, handoff);
    }
  } catch (error) {
    console.warn("Copy Product Swap preparation failed", error);
    setStatus(panel, "Не удалось подготовить материалы. Ничего не запущено и не оплачено.", "error");
  } finally {
    state.busy = false;
  }
}

async function prepareAvatar(form) {
  const state = formStates.get(form);
  const route = state?.routes.avatar_video;
  const panel = panelFor(state, "avatar_video");
  if (!state || !route || !panel || state.busy) return;
  const avatarWishes = currentAvatarWishes(panel);
  if (avatarWishes.length < 10) {
    setStatus(panel, "Опишите аватара хотя бы одним понятным предложением.", "error");
    return;
  }
  state.busy = true;
  setStatus(panel, "Сохраняем MP4 и подготовку аватара…", "busy");
  try {
    const sourceMediaId = await ensureSourceMedia(route);
    const handoff = {
      version: HANDOFF_VERSION,
      route: "avatar_video",
      paid_authority: PAID_AUTHORITY,
      strategy_id: "character_performance",
      source_media_id: sourceMediaId,
      original_product_media_id: "",
      product_media_ids: [],
      reference_media_ids: [],
      source_url: currentSourceUrl(panel),
      description: currentDescription(panel),
      avatar_wishes: avatarWishes,
      assets: [{ role: "source_video", media_id: sourceMediaId }],
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
    setStatus(panel, "Не удалось сохранить подготовку аватара. Ничего не запущено и не оплачено.", "error");
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
  state.route = route;
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
  form.dataset.generationIntakeV4Mode = compact ? "compact" : "full";
  moveProductNodes(form, state, route === "copy_video");
  if (route === "strategy_video") {
    selectStrategy(form, STRATEGY_AUTHORITY_STRATEGY);
  }
  refreshVideoSelects(form, state);
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
    if (action === "generation-intake-prepare-copy") void prepareCopy(form);
    if (action === "generation-intake-prepare-avatar") void prepareAvatar(form);
    if (action === "generation-intake-upload-strategy") void uploadStrategySources(form);
    const frameButton = event.target.closest?.("[data-frame-index]");
    if (frameButton) {
      const route = state.route;
      const routeState = state.routes[route];
      if (!routeState?.storyboard) return;
      routeState.selectedFrameIndex = Number(frameButton.dataset.frameIndex);
      renderStoryboard(panelFor(state, route), routeState.storyboard, routeState);
    }
  });

  state.shell.addEventListener("change", (event) => {
    const input = event.target.closest?.('input[data-generation-intake-mp4="single"]');
    if (input) {
      const route = input.closest("[data-generation-intake-panel]")?.dataset.generationIntakePanel;
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
        q(`[data-action="${prepareAction}"]`, panelFor(state, route)).disabled = true;
        q("[data-generation-intake-storyboard]", panelFor(state, route)).hidden = true;
        setStatus(panelFor(state, route), "MP4 выбран. Нажмите «Разобрать MP4».", "neutral");
      }
    }
  });
}

function mount(form) {
  if (!(form instanceof HTMLFormElement)) return;
  const existing = formStates.get(form);
  if (existing?.shell?.isConnected) {
    refreshVideoSelects(form, existing);
    return;
  }
  ensureStyle();
  ensureContractFields(form);
  q("[data-generation-intake-v2]", form)?.remove();
  q("[data-generation-intake-v3]", form)?.remove();
  const shell = shellNode();
  const strategyView = q(".generation-strategy-view", form);
  const modePanel = q('[data-ce-v4-generation-panel="mode"]', form) || strategyView?.parentElement || form;
  if (strategyView) strategyView.before(shell);
  else modePanel.prepend(shell);
  const state = {
    shell,
    route: "copy_video",
    busy: false,
    productNodes: [],
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
