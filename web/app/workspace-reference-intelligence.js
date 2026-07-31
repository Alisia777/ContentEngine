/*
 * ContentEngine Reference Intelligence v1.1.
 *
 * References are untrusted creative inputs. This module never submits a
 * business form, never starts a paid generation, and never writes style
 * examples into product facts. Research references enter visual_direction;
 * direct-generation references are returned to the existing safe compiler.
 */

const FUNCTION_NAME = "creator-reference-intelligence";
const SUPABASE_SDK_URL = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm";
const STATE_KEY = "contentengine.reference-intelligence.v2";
const STATE_VERSION = 2;
const PAID_ANALYSIS_ACK = "REFERENCE_ANALYSIS_PAID_V1";
const MAX_SCOPES = 16;
const MAX_URLS = 8;
const MAX_FILES = 4;
const MAX_ASSETS = 16;
const MAX_RAW_TOTAL_BYTES = 80 * 1024 * 1024;
const MAX_IMAGE_BYTES = 12 * 1024 * 1024;
const MAX_PDF_BYTES = 8 * 1024 * 1024;
const MAX_VIDEO_BYTES = 64 * 1024 * 1024;
const MAX_PROVIDER_IMAGE_BYTES = 3 * 1024 * 1024;
const MAX_PROVIDER_TOTAL_BYTES = 12 * 1024 * 1024;
const VIDEO_FRAME_RATIOS = Object.freeze([0.1, 0.35, 0.6, 0.85]);
const START_MARKER = "[РЕФЕРЕНСЫ — ТОЛЬКО СТИЛЬ, НЕ ФАКТЫ О ТОВАРЕ]";
const END_MARKER = "[КОНЕЦ РЕФЕРЕНСОВ]";
const INTENT_START_MARKER = "[СТИЛЬ-РЕФЕРЕНС; НЕ ФАКТЫ]";
const INTENT_END_MARKER = "[КОНЕЦ СТИЛЯ]";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

const runtime = {
  queued: false,
  apiPromise: null,
  panels: new WeakMap(),
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function routePath() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function compact(value, limit = 240) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function normalizeScopePart(value, limit = 180) {
  return compact(value, limit).toLocaleLowerCase("ru-RU");
}

function canonicalPublicHttpsUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    if (
      url.protocol !== "https:" ||
      url.username ||
      url.password ||
      (url.port && url.port !== "443")
    ) return null;
    const host = url.hostname.toLocaleLowerCase("en-US");
    if (
      !host.includes(".") ||
      host === "localhost" ||
      host.endsWith(".localhost") ||
      host.endsWith(".local") ||
      /^\d{1,3}(?:\.\d{1,3}){3}$/u.test(host) ||
      host === "::1" ||
      host.startsWith("[") ||
      host.startsWith("10.") ||
      host.startsWith("192.168.") ||
      /^172\.(1[6-9]|2\d|3[01])\./u.test(host) ||
      /^169\.254\./u.test(host)
    ) return null;
    url.hash = "";
    const sensitiveParams = new Set([
      "token",
      "access_token",
      "auth",
      "authorization",
      "password",
      "secret",
      "signature",
      "sig",
      "api_key",
      "apikey",
      "key",
      "x-amz-signature",
      "x-goog-signature",
    ]);
    for (const key of [...url.searchParams.keys()]) {
      const normalized = key.toLocaleLowerCase("en-US");
      if (sensitiveParams.has(normalized)) return null;
      if (
        normalized.startsWith("utm_") ||
        [
          "gclid",
          "fbclid",
          "yclid",
          "ysclid",
          "_openstat",
          "igshid",
          "mc_cid",
          "mc_eid",
        ].includes(normalized)
      ) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    return url.href;
  } catch {
    return null;
  }
}

function parseUrls(value) {
  const lines = String(value || "")
    .split(/\r?\n/gu)
    .map((line) => line.trim())
    .filter(Boolean);
  const urls = [];
  const invalid = [];
  for (const line of lines) {
    const url = canonicalPublicHttpsUrl(line);
    if (!url) invalid.push(line);
    else if (!urls.includes(url)) urls.push(url);
  }
  return { urls, invalid };
}

function readStore() {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(STATE_KEY) || "{}");
    if (
      parsed?.version !== STATE_VERSION ||
      !parsed.scopes ||
      typeof parsed.scopes !== "object" ||
      Array.isArray(parsed.scopes)
    ) return { version: STATE_VERSION, scopes: {} };
    return parsed;
  } catch {
    return { version: STATE_VERSION, scopes: {} };
  }
}

function writeStore(store) {
  try {
    const scopes = Object.fromEntries(
      Object.entries(store?.scopes || {})
        .sort((left, right) => Number(right[1]?.updatedAt || 0) - Number(left[1]?.updatedAt || 0))
        .slice(0, MAX_SCOPES),
    );
    window.sessionStorage.setItem(STATE_KEY, JSON.stringify({
      version: STATE_VERSION,
      scopes,
    }));
  } catch {
    // Session persistence is a convenience. The current in-memory analysis
    // remains usable even when storage is unavailable.
  }
}

function referenceScope(form, purpose) {
  if (!(form instanceof HTMLFormElement)) return "";
  if (purpose === "research") {
    const researchId = String(form.dataset.researchId || "").trim();
    return researchId ? `research:${researchId}` : "";
  }
  const sku = normalizeScopePart(form.elements.sku?.value, 120);
  const productName = normalizeScopePart(form.elements.product_name?.value, 180);
  const exactMediaId = String(form.dataset.identityMediaId || "").trim();
  if (!sku || !productName || !exactMediaId) return "";
  return `generation:${sku}:${productName}`;
}

function panelState(panel) {
  if (!runtime.panels.has(panel)) {
    runtime.panels.set(panel, {
      scopeKey: "",
      analysis: null,
      requestId: "",
      signature: "",
      loading: false,
      verifiedUrls: [],
      inputSummary: { urls: 0, assets: 0 },
      applicationBlocked: false,
      hadLocalFiles: false,
    });
  }
  return runtime.panels.get(panel);
}

function scopeSnapshot(panel) {
  const state = panelState(panel);
  return {
    urls: String(q("[data-reference-urls]", panel)?.value || ""),
    note: String(q("[data-reference-note]", panel)?.value || ""),
    analysis: state.analysis,
    requestId: state.requestId,
    signature: state.signature,
    verifiedUrls: state.verifiedUrls,
    inputSummary: state.inputSummary,
    applicationBlocked: state.applicationBlocked,
    hadLocalFiles: state.hadLocalFiles,
    updatedAt: Date.now(),
  };
}

function saveScope(panel) {
  const state = panelState(panel);
  if (!state.scopeKey) return;
  const store = readStore();
  store.scopes[state.scopeKey] = scopeSnapshot(panel);
  writeStore(store);
}

function removeScope(panel) {
  const state = panelState(panel);
  if (!state.scopeKey) return;
  const store = readStore();
  delete store.scopes[state.scopeKey];
  writeStore(store);
}

function friendlyError(error) {
  const code = String(error?.code || error?.message || "");
  const messages = {
    auth_session_required: "Сессия завершилась. Войдите снова и повторите разбор.",
    reference_payload_invalid: "Примеры не прошли проверку. Уменьшите число или размер файлов.",
    request_too_large: "Файлы слишком большие для одного разбора. Оставьте до четырёх самых важных примеров.",
    provider_rate_limited: "Сервис анализа занят. Повторите тот же запрос немного позже.",
    provider_outcome_unknown: "Ответ провайдера не подтверждён. Повтор использует тот же номер запроса.",
    reference_result_invalid: "Примеры разобраны неполно. Система не стала применять сомнительное ТЗ.",
    supabase_config_missing: "Рабочая конфигурация анализа недоступна. Обновите кабинет.",
  };
  return messages[code] || compact(error?.message, 300) || "Не удалось разобрать примеры. Повторите позже.";
}

async function getClient() {
  if (!runtime.apiPromise) {
    runtime.apiPromise = (async () => {
      const config = Object.freeze({ ...(window.CONTENTENGINE_CONFIG || {}) });
      if (!config.SUPABASE_URL || !config.SUPABASE_PUBLISHABLE_KEY) {
        throw new Error("supabase_config_missing");
      }
      const { createClient } = await import(SUPABASE_SDK_URL);
      const client = createClient(
        config.SUPABASE_URL,
        config.SUPABASE_PUBLISHABLE_KEY,
        {
          auth: {
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: false,
          },
        },
      );
      const { data, error } = await client.auth.getSession();
      if (error || !data?.session) {
        const authError = new Error("auth_session_required");
        authError.code = "auth_session_required";
        throw authError;
      }
      return client;
    })().catch((error) => {
      runtime.apiPromise = null;
      throw error;
    });
  }
  return runtime.apiPromise;
}

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")), { once: true });
    reader.addEventListener("error", () => reject(reader.error || new Error("file_read_failed")), { once: true });
    reader.readAsDataURL(file);
  });
}

function waitFor(target, eventName, timeoutMs = 12_000) {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      window.clearTimeout(timer);
      target.removeEventListener(eventName, done);
      target.removeEventListener("error", failed);
    };
    const done = () => {
      cleanup();
      resolve();
    };
    const failed = () => {
      cleanup();
      reject(new Error(`${eventName}_failed`));
    };
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error(`${eventName}_timeout`));
    }, timeoutMs);
    target.addEventListener(eventName, done, { once: true });
    target.addEventListener("error", failed, { once: true });
  });
}

function dataUrlByteSize(value) {
  const payload = String(value || "").split(",", 2)[1] || "";
  const padding = payload.endsWith("==") ? 2 : payload.endsWith("=") ? 1 : 0;
  return Math.max(0, Math.floor(payload.length * 3 / 4) - padding);
}

function canvasDataUrl(source, width, height, maxWidth, quality) {
  const scale = Math.min(1, maxWidth / Math.max(1, width));
  const targetWidth = Math.max(1, Math.round(width * scale));
  const targetHeight = Math.max(1, Math.round(height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) throw new Error("canvas_unavailable");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, targetWidth, targetHeight);
  context.drawImage(source, 0, 0, targetWidth, targetHeight);
  return canvas.toDataURL("image/jpeg", quality);
}

function boundedCanvasDataUrl(source, width, height) {
  const attempts = [
    [1600, 0.84],
    [1440, 0.76],
    [1280, 0.68],
    [960, 0.62],
  ];
  for (const [maxWidth, quality] of attempts) {
    const dataUrl = canvasDataUrl(source, width, height, maxWidth, quality);
    if (dataUrlByteSize(dataUrl) <= MAX_PROVIDER_IMAGE_BYTES) return dataUrl;
  }
  throw new Error("reference_image_encoded_too_large");
}

async function imageAsset(file, id) {
  if (file.size > MAX_IMAGE_BYTES) {
    throw new Error(`Файл «${file.name}» больше 12 МБ.`);
  }
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.decoding = "async";
    image.src = objectUrl;
    await image.decode();
    return {
      id,
      name: file.name,
      kind: "image",
      mime_type: "image/jpeg",
      data_url: boundedCanvasDataUrl(
        image,
        image.naturalWidth,
        image.naturalHeight,
      ),
    };
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

async function seekVideo(video, seconds) {
  const clamped = Math.max(
    0,
    Math.min(seconds, Math.max(0, video.duration - 0.05)),
  );
  if (Math.abs(video.currentTime - clamped) < 0.03) return;
  const pending = waitFor(video, "seeked", 8_000);
  video.currentTime = clamped;
  await pending;
}

async function videoAssets(file, fileIndex) {
  if (file.size > MAX_VIDEO_BYTES) {
    throw new Error(`Видео «${file.name}» больше 64 МБ.`);
  }
  const objectUrl = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "metadata";
  video.muted = true;
  video.playsInline = true;
  video.src = objectUrl;
  try {
    if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
      await waitFor(video, "loadedmetadata", 15_000);
    }
    if (
      !Number.isFinite(video.duration) ||
      video.duration <= 0 ||
      !video.videoWidth ||
      !video.videoHeight
    ) throw new Error("video_metadata_invalid");
    const frames = [];
    for (let index = 0; index < VIDEO_FRAME_RATIOS.length; index += 1) {
      await seekVideo(video, video.duration * VIDEO_FRAME_RATIOS[index]);
      frames.push({
        id: `video:${fileIndex}:frame:${index + 1}`,
        name: `${file.name} · кадр ${index + 1}`,
        kind: "video_frame",
        mime_type: "image/jpeg",
        frame_seconds: Number(video.currentTime.toFixed(2)),
        data_url: boundedCanvasDataUrl(
          video,
          video.videoWidth,
          video.videoHeight,
        ),
      });
    }
    return frames;
  } finally {
    video.pause();
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(objectUrl);
  }
}

async function fileAssets(files) {
  const selected = [...files];
  if (selected.length > MAX_FILES) {
    throw new Error(`Можно разобрать не больше ${MAX_FILES} файлов за один раз.`);
  }
  if (selected.reduce((sum, file) => sum + file.size, 0) > MAX_RAW_TOTAL_BYTES) {
    throw new Error("Общий размер выбранных файлов превышает 80 МБ.");
  }
  const assets = [];
  for (let index = 0; index < selected.length; index += 1) {
    const file = selected[index];
    if (["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      assets.push(await imageAsset(file, `asset:${index + 1}`));
    } else if (file.type === "application/pdf") {
      if (file.size > MAX_PDF_BYTES) {
        throw new Error(`PDF «${file.name}» больше 8 МБ.`);
      }
      assets.push({
        id: `asset:${index + 1}`,
        name: file.name,
        kind: "pdf",
        mime_type: "application/pdf",
        data_url: await readAsDataUrl(file),
      });
    } else if (file.type === "video/mp4") {
      assets.push(...await videoAssets(file, index + 1));
    } else {
      throw new Error(
        `Формат «${file.name}» не поддерживается. Используйте JPG, PNG, WebP, PDF или MP4.`,
      );
    }
  }
  if (assets.length > MAX_ASSETS) {
    throw new Error("Из выбранных файлов получилось слишком много кадров.");
  }
  const totalBytes = assets.reduce(
    (sum, asset) => sum + dataUrlByteSize(asset.data_url),
    0,
  );
  if (totalBytes > MAX_PROVIDER_TOTAL_BYTES) {
    throw new Error("Подготовленные примеры превышают 12 МБ. Оставьте меньше файлов.");
  }
  return assets;
}

function setStatus(panel, message, tone = "idle") {
  const node = q("[data-reference-status]", panel);
  if (!node) return;
  node.textContent = message;
  node.dataset.tone = tone;
}

function setScopeLabel(panel, value, tone = "idle") {
  const node = q("[data-reference-scope]", panel);
  if (!node) return;
  node.textContent = value;
  node.dataset.tone = tone;
}

function updateFileSummary(panel) {
  const input = q("[data-reference-files-input]", panel);
  const summary = q("[data-reference-files]", panel);
  if (!summary) return;
  const files = [...(input?.files || [])];
  summary.textContent = files.length
    ? files
      .map((file) => `${file.name} · ${(file.size / 1_048_576).toFixed(1)} МБ`)
      .join("; ")
    : "Файлы не выбраны. После перезагрузки локальные файлы нужно выбрать снова.";
}

function resultHasUnverifiedUrls(state) {
  return Number(state.inputSummary?.urls || 0) > state.verifiedUrls.length;
}

function updateApplyState(form, panel) {
  const state = panelState(panel);
  const apply = q("[data-reference-apply]", panel);
  const analyzeButton = q("[data-reference-analyze]", panel);
  const scopeKey = referenceScope(form, panel.dataset.referencePurpose);
  if (analyzeButton) analyzeButton.disabled = state.loading || !scopeKey;
  if (apply) {
    apply.disabled = Boolean(
      state.loading ||
      !scopeKey ||
      !state.analysis ||
      state.applicationBlocked ||
      resultHasUnverifiedUrls(state),
    );
  }
}

function renderAnalysis(panel, response) {
  const analysis = response?.analysis;
  const result = q("[data-reference-result]", panel);
  if (!result || !analysis) return;
  result.replaceChildren();
  const summary = create("article", "ce-reference-intelligence__summary");
  summary.append(
    create("small", "", "ВЫЖИМКА"),
    create("p", "", analysis.summary),
  );
  const dna = create("div", "ce-reference-intelligence__dna");
  const fields = [
    ["Хук", analysis.creative_dna?.hook],
    ["Темп", analysis.creative_dna?.pacing],
    ["Композиция", analysis.creative_dna?.composition],
    ["Камера", analysis.creative_dna?.camera],
    ["Монтаж", analysis.creative_dna?.editing],
    ["Голос", analysis.creative_dna?.voice],
    ["CTA", analysis.creative_dna?.cta],
  ];
  fields.forEach(([label, value]) => {
    const row = create("article");
    row.append(
      create("small", "", label),
      create("p", "", String(value || "—")),
    );
    dna.append(row);
  });
  const guard = create("article", "ce-reference-intelligence__guard");
  guard.append(create("small", "", "НЕ КОПИРОВАТЬ"));
  const list = create("ul");
  (analysis.creative_dna?.do_not_copy || [])
    .slice(0, 6)
    .forEach((item) => list.append(create("li", "", item)));
  guard.append(list);
  const verification = create("p", "ce-reference-intelligence__verification");
  const totalUrls = Number(response.input_summary?.urls || 0);
  const verified = Array.isArray(response.verified_urls)
    ? response.verified_urls.length
    : 0;
  verification.textContent = totalUrls
    ? `Ссылок: ${totalUrls}; подтверждено точными provider-citations: ${verified}. Неподтверждённая ссылка не может попасть в ТЗ.`
    : `Файловых представлений разобрано: ${Number(response.input_summary?.assets || 0)}.`;
  const limitations = create("article", "ce-reference-intelligence__limitations");
  limitations.append(create("small", "", "ОГРАНИЧЕНИЯ РАЗБОРА"));
  const limitationsList = create("ul");
  (analysis.limitations || [])
    .slice(0, 6)
    .forEach((item) => limitationsList.append(create("li", "", item)));
  limitations.append(limitationsList);
  result.append(summary, dna, guard, limitations, verification);
  result.hidden = false;
  if (!REDUCED_MOTION.matches && typeof result.animate === "function") {
    result.animate(
      [
        { opacity: 0, transform: "translateY(8px)" },
        { opacity: 1, transform: "translateY(0)" },
      ],
      { duration: 280, easing: "cubic-bezier(.16,1,.3,1)" },
    );
  }
}

function restoreScope(form, panel) {
  const state = panelState(panel);
  const nextScope = referenceScope(form, panel.dataset.referencePurpose);
  if (state.scopeKey === nextScope) {
    updateApplyState(form, panel);
    return;
  }
  if (state.scopeKey) saveScope(panel);
  state.scopeKey = nextScope;
  state.analysis = null;
  state.requestId = "";
  state.signature = "";
  state.verifiedUrls = [];
  state.inputSummary = { urls: 0, assets: 0 };
  state.applicationBlocked = false;
  state.hadLocalFiles = false;
  const urls = q("[data-reference-urls]", panel);
  const note = q("[data-reference-note]", panel);
  const files = q("[data-reference-files-input]", panel);
  const result = q("[data-reference-result]", panel);
  if (files) files.value = "";
  if (result) {
    result.replaceChildren();
    result.hidden = true;
  }
  if (!nextScope) {
    if (urls) urls.value = "";
    if (note) note.value = "";
    setScopeLabel(panel, "Сначала выберите точный товар", "warning");
    setStatus(
      panel,
      panel.dataset.referencePurpose === "generation"
        ? "Референсы привязываются к конкретному SKU и не сохраняются в общий черновик."
        : "Откройте редактируемое ТЗ после завершения анализа товара.",
      "idle",
    );
    updateFileSummary(panel);
    updateApplyState(form, panel);
    return;
  }
  const record = readStore().scopes[nextScope] || null;
  if (urls) urls.value = String(record?.urls || "");
  if (note) note.value = String(record?.note || "");
  if (record?.analysis) {
    state.analysis = record.analysis;
    state.requestId = String(record.requestId || "");
    state.signature = String(record.signature || "");
    state.verifiedUrls = Array.isArray(record.verifiedUrls)
      ? record.verifiedUrls
      : [];
    state.inputSummary = record.inputSummary || { urls: 0, assets: 0 };
    state.applicationBlocked = record.applicationBlocked === true;
    state.hadLocalFiles = record.hadLocalFiles === true;
    renderAnalysis(panel, {
      analysis: state.analysis,
      verified_urls: state.verifiedUrls,
      input_summary: state.inputSummary,
    });
  }
  const scopeLabel = panel.dataset.referencePurpose === "research"
    ? `ТЗ исследования · ${nextScope.slice("research:".length, "research:".length + 8)}`
    : `SKU · ${compact(form.elements.sku?.value, 54)}`;
  setScopeLabel(panel, scopeLabel, "ready");
  if (state.analysis) {
    setStatus(
      panel,
      state.applicationBlocked || resultHasUnverifiedUrls(state)
        ? "Разбор сохранён, но применить его нельзя: не все URL подтверждены. Добавьте файл/скрин или удалите недоступную ссылку."
        : state.hadLocalFiles
          ? "Разбор восстановлен для этого товара. Локальные файлы не хранятся; для нового анализа выберите их снова."
          : "Разбор восстановлен для этого товара. Проверьте выжимку перед применением.",
      state.applicationBlocked || resultHasUnverifiedUrls(state)
        ? "error"
        : "ready",
    );
  } else {
    setStatus(panel, "Добавьте хотя бы одну ссылку или файл.");
  }
  updateFileSummary(panel);
  updateApplyState(form, panel);
}

function buildPanel(form, purpose) {
  const panel = create("section", "ce-reference-intelligence");
  panel.dataset.referencePurpose = purpose;
  const header = create("header", "ce-reference-intelligence__header");
  const title = create("div");
  title.append(
    create("small", "", "REFERENCE INTELLIGENCE"),
    create("strong", "", "Примеры для безопасного ТЗ"),
    create(
      "p",
      "",
      purpose === "research"
        ? "Референс попадёт только в поле «Визуальный стиль» редактируемого ТЗ. Он никогда не станет подтверждённым фактом о товаре."
        : "Пример сначала превращается в короткое стилевое указание, затем штатный компилятор заново собирает и проверяет provider-prompt.",
    ),
  );
  const badges = create("div", "ce-reference-intelligence__badges");
  badges.append(
    create("span", "ce-reference-intelligence__safety", "Не источник фактов"),
    create("span", "ce-reference-intelligence__safety", "Не обучает модель"),
    create("span", "ce-reference-intelligence__scope", "Определяем товар…"),
  );
  q(".ce-reference-intelligence__scope", badges).dataset.referenceScope = "true";
  header.append(title, badges);

  const grid = create("div", "ce-reference-intelligence__grid");
  const urlLabel = create("label", "field ce-reference-intelligence__urls");
  urlLabel.append(create("span", "", "Ссылки на примеры · по одной в строке"));
  const urls = create("textarea");
  urls.rows = 4;
  urls.maxLength = 16_384;
  urls.placeholder = "https://…\nhttps://…";
  urls.dataset.referenceUrls = "true";
  urlLabel.append(
    urls,
    create("small", "field-hint", `До ${MAX_URLS} публичных HTTPS-ссылок. Ссылки с tracking-параметрами очищаются.`),
  );

  const fileLabel = create("label", "field ce-reference-intelligence__files");
  fileLabel.append(create("span", "", "Локальные файлы-примеры"));
  const files = create("input");
  files.type = "file";
  files.multiple = true;
  files.accept = "image/jpeg,image/png,image/webp,application/pdf,video/mp4";
  files.dataset.referenceFilesInput = "true";
  const fileSummary = create(
    "small",
    "ce-reference-intelligence__file-summary",
    "Файлы не выбраны. После перезагрузки локальные файлы нужно выбрать снова.",
  );
  fileSummary.dataset.referenceFiles = "true";
  fileLabel.append(
    files,
    create(
      "small",
      "field-hint",
      "До 4 файлов: JPG, PNG, WebP, PDF или MP4. Из MP4 локально извлекаются 4 кадра; сам ролик не сохраняется как датасет.",
    ),
    fileSummary,
  );
  grid.append(urlLabel, fileLabel);

  const noteLabel = create("label", "field");
  noteLabel.append(create("span", "", "Что взять по форме и что точно не копировать"));
  const note = create("textarea");
  note.rows = 3;
  note.maxLength = 2_000;
  note.placeholder = "Например: взять быстрый хук и крупный план; не копировать лицо, упаковку, музыку, текст и обещания.";
  note.dataset.referenceNote = "true";
  noteLabel.append(note);

  const paidAck = create("label", "check-row ce-reference-intelligence__paid-ack");
  const paidAckInput = create("input");
  paidAckInput.type = "checkbox";
  paidAckInput.value = PAID_ANALYSIS_ACK;
  paidAckInput.dataset.referencePaidAck = "true";
  const paidAckCopy = create("span");
  paidAckCopy.append(
    create("strong", "", "Запускаю отдельный платный ИИ-разбор примеров"),
    document.createElement("br"),
    create(
      "small",
      "",
      "Используются модель анализа и web search. Галочка не сохраняется; применение готовой выжимки и запуск Runway — отдельные действия.",
    ),
  );
  paidAck.append(paidAckInput, paidAckCopy);

  const actions = create("div", "ce-reference-intelligence__actions");
  const analyzeButton = create("button", "btn btn-secondary btn-small", "Разобрать примеры");
  analyzeButton.type = "button";
  analyzeButton.dataset.referenceAnalyze = "true";
  const applyButton = create(
    "button",
    "btn btn-small",
    purpose === "research"
      ? "Добавить в визуальный стиль"
      : "Подготовить безопасное ТЗ",
  );
  applyButton.type = "button";
  applyButton.disabled = true;
  applyButton.dataset.referenceApply = "true";
  const clearButton = create("button", "btn btn-ghost btn-small", "Очистить черновик примеров");
  clearButton.type = "button";
  clearButton.dataset.referenceClear = "true";
  actions.append(analyzeButton, applyButton, clearButton);

  const status = create(
    "p",
    "ce-reference-intelligence__status",
    "Определяем товарный контекст…",
  );
  status.dataset.referenceStatus = "true";
  status.setAttribute("role", "status");
  const result = create("div", "ce-reference-intelligence__result");
  result.dataset.referenceResult = "true";
  result.hidden = true;
  panel.append(header, grid, noteLabel, paidAck, actions, status, result);

  const saveDraft = () => {
    restoreScope(form, panel);
    saveScope(panel);
  };
  urls.addEventListener("input", saveDraft);
  note.addEventListener("input", saveDraft);
  files.addEventListener("change", () => {
    updateFileSummary(panel);
    saveDraft();
  });
  panel.addEventListener("click", (event) => {
    void handlePanelClick(event, form, panel);
  });
  form.addEventListener("input", () => window.queueMicrotask(() => restoreScope(form, panel)));
  form.addEventListener("change", () => window.queueMicrotask(() => restoreScope(form, panel)));
  window.queueMicrotask(() => restoreScope(form, panel));
  return panel;
}

async function analyze(form, panel) {
  const state = panelState(panel);
  restoreScope(form, panel);
  if (state.loading || !state.scopeKey) return;
  const parsed = parseUrls(q("[data-reference-urls]", panel)?.value || "");
  if (parsed.invalid.length) {
    setStatus(
      panel,
      `Укажите по одной полной HTTPS-ссылке в строке: ${compact(parsed.invalid.join(", "), 180)}`,
      "error",
    );
    return;
  }
  if (parsed.urls.length > MAX_URLS) {
    setStatus(panel, `Оставьте не больше ${MAX_URLS} ссылок.`, "error");
    return;
  }
  const files = [...(q("[data-reference-files-input]", panel)?.files || [])];
  if (!parsed.urls.length && !files.length) {
    setStatus(panel, "Добавьте хотя бы одну ссылку или файл.", "error");
    return;
  }
  const note = String(q("[data-reference-note]", panel)?.value || "").trim();
  const signature = JSON.stringify({
    scope: state.scopeKey,
    purpose: panel.dataset.referencePurpose,
    urls: parsed.urls,
    note,
    files: files.map((file) => [
      file.name,
      file.size,
      file.type,
      file.lastModified,
    ]),
  });
  if (state.signature === signature && state.analysis) {
    renderAnalysis(panel, {
      analysis: state.analysis,
      verified_urls: state.verifiedUrls,
      input_summary: state.inputSummary,
    });
    setStatus(panel, "Используем уже готовый разбор этих же вводных без нового платного запроса.", "ready");
    updateApplyState(form, panel);
    return;
  }
  const paidAck = q("[data-reference-paid-ack]", panel);
  if (!(paidAck instanceof HTMLInputElement) || !paidAck.checked) {
    setStatus(
      panel,
      "Подтвердите отдельный платный ИИ-разбор примеров. Это не запускает Runway и не создаёт контент.",
      "error",
    );
    paidAck?.focus({ preventScroll: true });
    return;
  }
  const sameRequest = state.signature === signature && Boolean(state.requestId);
  state.signature = signature;
  if (!sameRequest) state.requestId = crypto.randomUUID();
  state.analysis = null;
  state.verifiedUrls = [];
  state.inputSummary = { urls: 0, assets: 0 };
  state.applicationBlocked = false;
  state.hadLocalFiles = files.length > 0;
  state.loading = true;
  updateApplyState(form, panel);
  setStatus(
    panel,
    files.some((file) => file.type === "video/mp4")
      ? "Локально извлекаем кадры и разбираем примеры…"
      : "Разбираем примеры…",
    "loading",
  );
  try {
    const assets = await fileAssets(files);
    const client = await getClient();
    const { data: sessionData, error: sessionError } = await client.auth.getSession();
    if (sessionError || !sessionData?.session) {
      const authError = new Error("auth_session_required");
      authError.code = "auth_session_required";
      throw authError;
    }
    const { data, error } = await client.functions.invoke(FUNCTION_NAME, {
      body: {
        request_id: state.requestId,
        purpose: panel.dataset.referencePurpose,
        reference_urls: parsed.urls,
        reference_note: note,
        paid_analysis_ack: PAID_ANALYSIS_ACK,
        assets,
      },
      headers: {
        Authorization: `Bearer ${sessionData.session.access_token}`,
      },
    });
    if (error) {
      const failure = new Error(error.message || "reference_request_failed");
      failure.code = error.code || data?.code || "reference_request_failed";
      throw failure;
    }
    if (!data?.ok || !data.analysis) {
      const failure = new Error(data?.code || "reference_result_invalid");
      failure.code = data?.code || "reference_result_invalid";
      throw failure;
    }
    state.analysis = data.analysis;
    state.verifiedUrls = Array.isArray(data.verified_urls)
      ? data.verified_urls
      : [];
    state.inputSummary = data.input_summary || {
      urls: parsed.urls.length,
      assets: assets.length,
    };
    state.applicationBlocked = parsed.urls.length > state.verifiedUrls.length;
    renderAnalysis(panel, data);
    saveScope(panel);
    setStatus(
      panel,
      state.applicationBlocked
        ? "Разбор готов, но не все ссылки подтверждены точными citations. Загрузите файл/скрин или удалите недоступную ссылку — в ТЗ она не попадёт."
        : "Разбор готов. Проверьте выжимку и примените её отдельной кнопкой.",
      state.applicationBlocked ? "error" : "ready",
    );
  } catch (error) {
    state.analysis = null;
    setStatus(panel, friendlyError(error), "error");
    saveScope(panel);
  } finally {
    state.loading = false;
    const paidAck = q("[data-reference-paid-ack]", panel);
    if (paidAck instanceof HTMLInputElement) paidAck.checked = false;
    updateApplyState(form, panel);
  }
}

function stripMarkedBlock(value, startMarker, endMarker) {
  const text = String(value || "");
  const start = text.indexOf(startMarker);
  if (start < 0) return text.trim();
  const end = text.indexOf(endMarker, start);
  if (end < 0) return text.slice(0, start).trim();
  return `${text.slice(0, start)}${text.slice(end + endMarker.length)}`.trim();
}

function referenceBlock(analysis, maximum) {
  const guard = (analysis.creative_dna?.do_not_copy || [])
    .slice(0, 4)
    .join("; ");
  const guardLine = guard
    ? `Не копировать: ${guard}`
    : "Не копировать чужие товар, бренд, лицо, текст, музыку и claims.";
  const reserved = START_MARKER.length + END_MARKER.length + guardLine.length + 12;
  const core = compact(
    analysis.concise_instruction,
    Math.max(80, maximum - reserved),
  );
  return `${START_MARKER}\n${core}\n${compact(guardLine, 300)}\n${END_MARKER}`;
}

function dispatchFieldChange(target) {
  target.dispatchEvent(new Event("input", { bubbles: true }));
  target.dispatchEvent(new Event("change", { bubbles: true }));
}

function applyToResearchBrief(form, panel) {
  const state = panelState(panel);
  const target = form.elements.visual_direction;
  if (!(target instanceof HTMLTextAreaElement) || target.disabled) {
    setStatus(
      panel,
      "Редактируемое поле «Визуальный стиль» недоступно. Утверждённое ТЗ незаметно менять нельзя.",
      "error",
    );
    return false;
  }
  const base = stripMarkedBlock(target.value, START_MARKER, END_MARKER);
  const maxLength = Number(target.maxLength) > 0 ? Number(target.maxLength) : 1_800;
  const available = maxLength - base.length - (base ? 2 : 0);
  if (available < 220) {
    setStatus(
      panel,
      "В поле «Визуальный стиль» почти не осталось места. Сократите собственный текст — он имеет приоритет.",
      "error",
    );
    target.focus({ preventScroll: true });
    return false;
  }
  const block = referenceBlock(state.analysis, available);
  target.value = `${base}${base ? "\n\n" : ""}${block}`;
  dispatchFieldChange(target);
  target.dataset.referenceIntelligenceApplied = "true";
  setStatus(
    panel,
    "Добавлено только в «Визуальный стиль». Сохраните и утвердите ТЗ штатными кнопками — задачи автоматически не создавались.",
    "applied",
  );
  target.focus({ preventScroll: true });
  return true;
}

function generationHasApprovedHandoff(form) {
  return Boolean(
    form.closest(".generation-launch-card")?.querySelector("#generation-handoff-panel") ||
    document.querySelector("#generation-handoff-panel"),
  );
}

function looksCompiledPrompt(value) {
  const text = String(value || "");
  return text.includes("Точный товар:") &&
    text.includes("Сохрани форму, цвет, упаковку, этикетку и пропорции") &&
    text.includes("Не добавляй новые свойства, результаты, медицинские обещания");
}

function referenceIntent(analysis) {
  const core = compact(analysis.concise_instruction, 108);
  return `${INTENT_START_MARKER} ${core} ${INTENT_END_MARKER}`;
}

async function waitForEnabledButton(button, timeoutMs = 6_000) {
  const startedAt = Date.now();
  while (button?.isConnected && button.disabled && Date.now() - startedAt < timeoutMs) {
    await new Promise((resolve) => window.setTimeout(resolve, 120));
  }
  return Boolean(button?.isConnected && !button.disabled);
}

async function applyToGenerationCompiler(form, panel) {
  const state = panelState(panel);
  if (generationHasApprovedHandoff(form)) {
    setStatus(
      panel,
      "Этот запуск связан с утверждённым исследованием. Добавьте пример в поле «Визуальный стиль» раздела «Разбор товара» до утверждения — прямое изменение утверждённого сценария заблокировано.",
      "error",
    );
    return false;
  }
  const brief = form.elements.brief;
  const compileButton = form.querySelector(
    '[data-action="restore-auto-generation-brief"]',
  );
  if (!(brief instanceof HTMLTextAreaElement) || !compileButton) {
    setStatus(panel, "Штатный компилятор ТЗ не найден. Обновите рабочее место.", "error");
    return false;
  }
  const currentBrief = String(brief.value || "").trim();
  const storedIntent = String(form.dataset.generationScenarioIntent || "").trim();
  const rawBase = storedIntent || (looksCompiledPrompt(currentBrief) ? "" : currentBrief);
  const baseIntent = stripMarkedBlock(
    rawBase,
    INTENT_START_MARKER,
    INTENT_END_MARKER,
  );
  if (baseIntent.length > 240) {
    setStatus(
      panel,
      "Ваш исходный замысел длиннее 240 символов. Сократите его перед добавлением референса — система не станет тихо обрезать вашу идею ради примера.",
      "error",
    );
    brief.focus({ preventScroll: true });
    return false;
  }
  const styleIntent = referenceIntent(state.analysis);
  const composedIntent = [baseIntent, styleIntent].filter(Boolean).join(" ");
  if (composedIntent.length > 400) {
    setStatus(
      panel,
      "Замысел и стилевой референс вместе не помещаются в безопасный лимит компилятора. Сократите собственный текст или комментарий к примеру.",
      "error",
    );
    return false;
  }
  const rollback = {
    brief: brief.value,
    scenarioIntent: form.dataset.generationScenarioIntent,
    autoBrief: form.dataset.autoGenerationBrief,
  };
  brief.value = composedIntent;
  form.dataset.generationScenarioIntent = composedIntent;
  delete form.dataset.autoGenerationBrief;
  dispatchFieldChange(brief);
  const ready = await waitForEnabledButton(compileButton);
  if (!ready) {
    brief.value = rollback.brief;
    if (rollback.scenarioIntent === undefined) {
      delete form.dataset.generationScenarioIntent;
    } else {
      form.dataset.generationScenarioIntent = rollback.scenarioIntent;
    }
    if (rollback.autoBrief === undefined) {
      delete form.dataset.autoGenerationBrief;
    } else {
      form.dataset.autoGenerationBrief = rollback.autoBrief;
    }
    dispatchFieldChange(brief);
    setStatus(
      panel,
      "Компилятор ещё не готов: выберите проверенный товар и дождитесь бесплатной проверки обученного ТЗ.",
      "error",
    );
    return false;
  }
  compileButton.click();
  await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
  await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
  const compiled = String(brief.value || "");
  const probe = compact(state.analysis.concise_instruction, 42).replace(/…$/u, "");
  const accepted = looksCompiledPrompt(compiled) &&
    String(form.dataset.autoGenerationBrief || "") === compiled &&
    (!probe || compiled.includes(probe));
  if (!accepted) {
    brief.value = rollback.brief;
    if (rollback.scenarioIntent === undefined) {
      delete form.dataset.generationScenarioIntent;
    } else {
      form.dataset.generationScenarioIntent = rollback.scenarioIntent;
    }
    if (rollback.autoBrief === undefined) {
      delete form.dataset.autoGenerationBrief;
    } else {
      form.dataset.autoGenerationBrief = rollback.autoBrief;
    }
    dispatchFieldChange(brief);
    setStatus(
      panel,
      "Штатный компилятор не подтвердил включение референса. Платный запуск не изменён; обновите форму и повторите.",
      "error",
    );
    return false;
  }
  setStatus(
    panel,
    "Референс прошёл через штатный компилятор. Проверьте итоговое ТЗ; Runway и оплата не запускались.",
    "applied",
  );
  brief.focus({ preventScroll: true });
  return true;
}

async function applyReference(form, panel) {
  const state = panelState(panel);
  restoreScope(form, panel);
  if (
    !state.scopeKey ||
    !state.analysis ||
    state.applicationBlocked ||
    resultHasUnverifiedUrls(state)
  ) {
    setStatus(
      panel,
      "Сначала получите полный разбор без неподтверждённых ссылок.",
      "error",
    );
    return;
  }
  const applied = panel.dataset.referencePurpose === "research"
    ? applyToResearchBrief(form, panel)
    : await applyToGenerationCompiler(form, panel);
  if (applied) saveScope(panel);
}

function clearPanel(form, panel) {
  removeScope(panel);
  const state = panelState(panel);
  state.analysis = null;
  state.requestId = "";
  state.signature = "";
  state.verifiedUrls = [];
  state.inputSummary = { urls: 0, assets: 0 };
  state.applicationBlocked = false;
  state.hadLocalFiles = false;
  q("[data-reference-urls]", panel).value = "";
  q("[data-reference-note]", panel).value = "";
  q("[data-reference-files-input]", panel).value = "";
  const result = q("[data-reference-result]", panel);
  result.replaceChildren();
  result.hidden = true;
  updateFileSummary(panel);
  setStatus(panel, "Черновик примеров очищен. Уже применённое ТЗ меняется только в своём штатном поле.");
  updateApplyState(form, panel);
}

async function handlePanelClick(event, form, panel) {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("[data-reference-analyze]")) {
    await analyze(form, panel);
  } else if (target?.closest("[data-reference-apply]")) {
    await applyReference(form, panel);
  } else if (target?.closest("[data-reference-clear]")) {
    clearPanel(form, panel);
  }
}

function mountResearch() {
  if (routePath() !== "/workspace/research") return;
  const form = q("#product-research-brief-form");
  if (!form || q(".ce-reference-intelligence", form)) return;
  const target = form.elements.visual_direction;
  if (!(target instanceof HTMLTextAreaElement) || target.disabled) return;
  const panel = buildPanel(form, "research");
  target.closest(".field")?.after(panel);
}

function mountGeneration() {
  if (routePath() !== "/workspace/generation") return;
  const form = q("#mock-batch-form");
  if (!form || q(".ce-reference-intelligence", form)) return;
  const panel = buildPanel(form, "generation");
  const assist = q("#generation-brief-assist", form);
  assist?.after(panel);
}

function mount() {
  mountResearch();
  mountGeneration();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

new MutationObserver(schedule).observe(
  q("#app") || document.documentElement,
  { childList: true, subtree: true },
);

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest('[data-action="logout"]')) {
    try {
      window.sessionStorage.removeItem(STATE_KEY);
    } catch {
      // Authentication cleanup must continue even if storage is unavailable.
    }
  }
}, { capture: true });

window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", schedule, { once: true });
} else {
  schedule();
}

window.ContentEngineReferenceIntelligence = Object.freeze({ schedule });
