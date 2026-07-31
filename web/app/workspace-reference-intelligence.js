/*
 * ContentEngine Reference Intelligence v1.
 *
 * Accepts public reference links and local example files, parses only reusable
 * creative patterns, and inserts a compact style-only block into the existing
 * research or generation brief. It never treats examples as product evidence.
 */

const FUNCTION_NAME = "creator-reference-intelligence";
const SUPABASE_SDK_URL = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm";
const MAX_URLS = 8;
const MAX_FILES = 4;
const MAX_RAW_TOTAL_BYTES = 80 * 1024 * 1024;
const MAX_IMAGE_BYTES = 12 * 1024 * 1024;
const MAX_PDF_BYTES = 8 * 1024 * 1024;
const MAX_VIDEO_BYTES = 64 * 1024 * 1024;
const VIDEO_FRAME_RATIOS = [0.1, 0.35, 0.6, 0.85];
const START_MARKER = "[РЕФЕРЕНСЫ — ТОЛЬКО СТИЛЬ, НЕ ФАКТЫ О ТОВАРЕ]";
const END_MARKER = "[КОНЕЦ РЕФЕРЕНСОВ]";
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
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function compact(value, limit = 240) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function publicHttpsUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return null;
    const host = url.hostname.toLocaleLowerCase("en-US");
    if (!host.includes(".") || host === "localhost" || host.endsWith(".localhost") || host.endsWith(".local")) return null;
    if (/^\d{1,3}(?:\.\d{1,3}){3}$/u.test(host) || host === "::1" || host.startsWith("[")) return null;
    if (host.startsWith("10.") || host.startsWith("192.168.") || /^172\.(1[6-9]|2\d|3[01])\./u.test(host) || /^169\.254\./u.test(host)) return null;
    url.hash = "";
    return url.href;
  } catch {
    return null;
  }
}

function parseUrls(value) {
  const lines = String(value || "").split(/[\n,]+/u).map((line) => line.trim()).filter(Boolean);
  const urls = [];
  const invalid = [];
  for (const line of lines) {
    const url = publicHttpsUrl(line);
    if (!url) invalid.push(line);
    else if (!urls.includes(url)) urls.push(url);
  }
  return { urls, invalid };
}

function friendlyError(error) {
  const code = String(error?.code || error?.message || "");
  const messages = {
    auth_session_required: "Сессия завершилась. Войдите снова и повторите разбор.",
    reference_payload_invalid: "Примеры не прошли проверку. Уменьшите число или размер файлов.",
    request_too_large: "Файлы слишком большие для одного разбора. Оставьте до четырёх самых важных примеров.",
    provider_rate_limited: "Сервис анализа занят. Повторите тот же запрос немного позже.",
    provider_outcome_unknown: "Ответ провайдера не подтверждён. Повтор использует тот же номер запроса и не создаёт новую версию ТЗ.",
    reference_result_invalid: "Примеры разобраны неполно. Система не стала вставлять сомнительное ТЗ.",
  };
  return messages[code] || compact(error?.message, 300) || "Не удалось разобрать примеры. Повторите позже.";
}

async function getClient() {
  if (!runtime.apiPromise) {
    runtime.apiPromise = (async () => {
      const config = Object.freeze({ ...(window.CONTENTENGINE_CONFIG || {}) });
      if (!config.SUPABASE_URL || !config.SUPABASE_PUBLISHABLE_KEY) throw new Error("supabase_config_missing");
      const { createClient } = await import(SUPABASE_SDK_URL);
      const client = createClient(config.SUPABASE_URL, config.SUPABASE_PUBLISHABLE_KEY, {
        auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false },
      });
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

async function imageElement(file) {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.decoding = "async";
    image.src = url;
    await image.decode();
    return image;
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }
}

function canvasDataUrl(source, width, height, maxWidth = 1600, quality = 0.86) {
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

async function imageAsset(file, id) {
  if (file.size > MAX_IMAGE_BYTES) throw new Error(`Файл «${file.name}» больше 12 МБ.`);
  const image = await imageElement(file);
  return {
    id,
    name: file.name,
    kind: "image",
    mime_type: "image/jpeg",
    data_url: canvasDataUrl(image, image.naturalWidth, image.naturalHeight),
  };
}

function waitFor(target, eventName, timeoutMs = 12_000) {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error(`${eventName}_timeout`));
    }, timeoutMs);
    const done = () => { cleanup(); resolve(); };
    const failed = () => { cleanup(); reject(new Error(`${eventName}_failed`)); };
    const cleanup = () => {
      window.clearTimeout(timer);
      target.removeEventListener(eventName, done);
      target.removeEventListener("error", failed);
    };
    target.addEventListener(eventName, done, { once: true });
    target.addEventListener("error", failed, { once: true });
  });
}

async function seekVideo(video, seconds) {
  const clamped = Math.max(0, Math.min(seconds, Math.max(0, video.duration - 0.05)));
  if (Math.abs(video.currentTime - clamped) < 0.03) return;
  const pending = waitFor(video, "seeked", 8_000);
  video.currentTime = clamped;
  await pending;
}

async function videoAssets(file, fileIndex) {
  if (file.size > MAX_VIDEO_BYTES) throw new Error(`Видео «${file.name}» больше 64 МБ.`);
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "metadata";
  video.muted = true;
  video.playsInline = true;
  video.src = url;
  try {
    if (video.readyState < HTMLMediaElement.HAVE_METADATA) await waitFor(video, "loadedmetadata", 15_000);
    if (!Number.isFinite(video.duration) || video.duration <= 0 || !video.videoWidth || !video.videoHeight) throw new Error("video_metadata_invalid");
    const frames = [];
    for (let index = 0; index < VIDEO_FRAME_RATIOS.length; index += 1) {
      const seconds = Math.max(0, video.duration * VIDEO_FRAME_RATIOS[index]);
      await seekVideo(video, seconds);
      frames.push({
        id: `video:${fileIndex}:frame:${index + 1}`,
        name: `${file.name} · кадр ${index + 1}`,
        kind: "video_frame",
        mime_type: "image/jpeg",
        frame_seconds: Number(video.currentTime.toFixed(2)),
        data_url: canvasDataUrl(video, video.videoWidth, video.videoHeight, 1280, 0.82),
      });
    }
    return frames;
  } finally {
    video.pause();
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(url);
  }
}

async function fileAssets(files) {
  const selected = [...files];
  if (selected.length > MAX_FILES) throw new Error(`Можно разобрать не больше ${MAX_FILES} файлов за один раз.`);
  if (selected.reduce((sum, file) => sum + file.size, 0) > MAX_RAW_TOTAL_BYTES) throw new Error("Общий размер выбранных файлов превышает 80 МБ.");
  const assets = [];
  for (let index = 0; index < selected.length; index += 1) {
    const file = selected[index];
    if (["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      assets.push(await imageAsset(file, `asset:${index + 1}`));
    } else if (file.type === "application/pdf") {
      if (file.size > MAX_PDF_BYTES) throw new Error(`PDF «${file.name}» больше 8 МБ.`);
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
      throw new Error(`Формат «${file.name}» не поддерживается. Используйте JPG, PNG, WebP, PDF или MP4.`);
    }
  }
  return assets;
}

function panelState(panel) {
  if (!runtime.panels.has(panel)) {
    runtime.panels.set(panel, {
      analysis: null,
      requestId: "",
      signature: "",
      loading: false,
      verifiedUrls: [],
    });
  }
  return runtime.panels.get(panel);
}

function setStatus(panel, message, tone = "idle") {
  const node = q("[data-reference-status]", panel);
  if (!node) return;
  node.textContent = message;
  node.dataset.tone = tone;
}

function updateFileSummary(panel) {
  const input = q('input[type="file"]', panel);
  const summary = q("[data-reference-files]", panel);
  if (!summary) return;
  const files = [...(input?.files || [])];
  summary.textContent = files.length
    ? files.map((file) => `${file.name} · ${(file.size / 1_048_576).toFixed(1)} МБ`).join("; ")
    : "Файлы не выбраны";
}

function buildPanel(form, purpose) {
  const panel = create("section", "ce-reference-intelligence");
  panel.dataset.referencePurpose = purpose;
  const header = create("header", "ce-reference-intelligence__header");
  const title = create("div");
  title.append(
    create("small", "", "REFERENCE INTELLIGENCE"),
    create("strong", "", "Примеры для ТЗ"),
    create("p", "", "Добавьте ссылки, изображения, PDF или MP4. Система возьмёт только хук, темп, композицию и подачу — не чужой товар, текст или обещания."),
  );
  const safety = create("span", "ce-reference-intelligence__safety", "Не источник фактов");
  header.append(title, safety);

  const grid = create("div", "ce-reference-intelligence__grid");
  const urlLabel = create("label", "field ce-reference-intelligence__urls");
  urlLabel.append(create("span", "", "Ссылки на примеры · по одной в строке"));
  const urls = create("textarea");
  urls.rows = 4;
  urls.maxLength = 16_384;
  urls.placeholder = "https://…\nhttps://…";
  urls.dataset.referenceUrls = "true";
  urlLabel.append(urls, create("small", "field-hint", `До ${MAX_URLS} публичных HTTPS-ссылок.`));

  const fileLabel = create("label", "field ce-reference-intelligence__files");
  fileLabel.append(create("span", "", "Файлы-примеры"));
  const files = create("input");
  files.type = "file";
  files.multiple = true;
  files.accept = "image/jpeg,image/png,image/webp,application/pdf,video/mp4";
  files.dataset.referenceFilesInput = "true";
  fileLabel.append(files, create("small", "field-hint", "До 4 файлов: JPG, PNG, WebP, PDF или MP4. Из видео локально извлекаются четыре кадра; сам ролик никуда не сохраняется."), create("small", "ce-reference-intelligence__file-summary", "Файлы не выбраны"));
  q(".ce-reference-intelligence__file-summary", fileLabel).dataset.referenceFiles = "true";
  grid.append(urlLabel, fileLabel);

  const noteLabel = create("label", "field");
  noteLabel.append(create("span", "", "Что именно нравится или что точно не копировать"));
  const note = create("textarea");
  note.rows = 3;
  note.maxLength = 2_000;
  note.placeholder = "Например: взять быстрый хук и крупный план товара; не копировать лицо, музыку, текст и упаковку.";
  note.dataset.referenceNote = "true";
  noteLabel.append(note);

  const actions = create("div", "ce-reference-intelligence__actions");
  const analyze = create("button", "btn btn-secondary btn-small", "Разобрать примеры");
  analyze.type = "button";
  analyze.dataset.referenceAnalyze = "true";
  const apply = create("button", "btn btn-small", purpose === "research" ? "Вставить в вводные ТЗ" : "Вставить в замысел");
  apply.type = "button";
  apply.disabled = true;
  apply.dataset.referenceApply = "true";
  const clear = create("button", "btn btn-ghost btn-small", "Очистить");
  clear.type = "button";
  clear.dataset.referenceClear = "true";
  actions.append(analyze, apply, clear);

  const status = create("p", "ce-reference-intelligence__status", "Добавьте хотя бы одну ссылку или файл.");
  status.dataset.referenceStatus = "true";
  status.setAttribute("role", "status");
  const result = create("div", "ce-reference-intelligence__result");
  result.dataset.referenceResult = "true";
  result.hidden = true;
  panel.append(header, grid, noteLabel, actions, status, result);

  files.addEventListener("change", () => updateFileSummary(panel));
  panel.addEventListener("click", (event) => handlePanelClick(event, form, panel));
  return panel;
}

function renderAnalysis(panel, response) {
  const analysis = response?.analysis;
  const result = q("[data-reference-result]", panel);
  if (!result || !analysis) return;
  result.replaceChildren();
  const summary = create("article", "ce-reference-intelligence__summary");
  summary.append(create("small", "", "ВЫЖИМКА"), create("p", "", analysis.summary));
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
    row.append(create("small", "", label), create("p", "", String(value || "—")));
    dna.append(row);
  });
  const guard = create("article", "ce-reference-intelligence__guard");
  guard.append(create("small", "", "НЕ КОПИРОВАТЬ"));
  const list = create("ul");
  (analysis.creative_dna?.do_not_copy || []).slice(0, 6).forEach((item) => list.append(create("li", "", item)));
  guard.append(list);
  const verification = create("p", "ce-reference-intelligence__verification");
  const totalUrls = Number(response.input_summary?.urls || 0);
  const verified = Array.isArray(response.verified_urls) ? response.verified_urls.length : 0;
  verification.textContent = totalUrls
    ? `Ссылок добавлено: ${totalUrls}; подтверждены цитатами web-search: ${verified}. Для остальных вывод ограничен доступной страницей/описанием.`
    : `Файлов разобрано: ${Number(response.input_summary?.assets || 0)}.`;
  result.append(summary, dna, guard, verification);
  result.hidden = false;
  if (!REDUCED_MOTION.matches && typeof result.animate === "function") {
    result.animate([{ opacity: 0, transform: "translateY(8px)" }, { opacity: 1, transform: "translateY(0)" }], { duration: 280, easing: "cubic-bezier(.16,1,.3,1)" });
  }
}

async function analyze(form, panel) {
  const state = panelState(panel);
  if (state.loading) return;
  const parsed = parseUrls(q("[data-reference-urls]", panel)?.value || "");
  if (parsed.invalid.length) {
    setStatus(panel, `Проверьте ссылки: ${compact(parsed.invalid.join(", "), 180)}`, "error");
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
    purpose: panel.dataset.referencePurpose,
    urls: parsed.urls,
    note,
    files: files.map((file) => [file.name, file.size, file.type, file.lastModified]),
  });
  if (state.signature !== signature) {
    state.signature = signature;
    state.requestId = crypto.randomUUID();
    state.analysis = null;
  }
  state.loading = true;
  q("[data-reference-analyze]", panel).disabled = true;
  q("[data-reference-apply]", panel).disabled = true;
  setStatus(panel, files.some((file) => file.type === "video/mp4") ? "Извлекаем кадры и разбираем примеры…" : "Разбираем примеры…", "loading");
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
        assets,
      },
      headers: { Authorization: `Bearer ${sessionData.session.access_token}` },
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
    state.verifiedUrls = data.verified_urls || [];
    renderAnalysis(panel, data);
    q("[data-reference-apply]", panel).disabled = false;
    setStatus(panel, "Разбор готов. Проверьте выжимку и вставьте её в ТЗ отдельной кнопкой.", "ready");
  } catch (error) {
    setStatus(panel, friendlyError(error), "error");
  } finally {
    state.loading = false;
    q("[data-reference-analyze]", panel).disabled = false;
  }
}

function stripReferenceBlock(value) {
  const text = String(value || "");
  const start = text.indexOf(START_MARKER);
  if (start < 0) return text.trim();
  const end = text.indexOf(END_MARKER, start);
  if (end < 0) return text.slice(0, start).trim();
  return `${text.slice(0, start)}${text.slice(end + END_MARKER.length)}`.trim();
}

function referenceBlock(analysis, maximum) {
  const guard = (analysis.creative_dna?.do_not_copy || []).slice(0, 4).join("; ");
  const core = compact(analysis.concise_instruction, Math.max(80, maximum - START_MARKER.length - END_MARKER.length - 40));
  const guardLine = guard ? `Не копировать: ${guard}` : "Не копировать чужие товар, бренд, лицо, текст, музыку и claims.";
  return `${START_MARKER}\n${core}\n${compact(guardLine, 300)}\n${END_MARKER}`;
}

function applyToBrief(form, panel) {
  const state = panelState(panel);
  const analysis = state.analysis;
  if (!analysis) return;
  const target = panel.dataset.referencePurpose === "research"
    ? form.elements.known_facts
    : form.elements.brief;
  if (!(target instanceof HTMLTextAreaElement)) {
    setStatus(panel, "Поле ТЗ не найдено. Обновите рабочее место.", "error");
    return;
  }
  const base = stripReferenceBlock(target.value);
  const maxLength = Number(target.maxLength) > 0 ? Number(target.maxLength) : 1_200;
  const available = maxLength - base.length - (base ? 2 : 0);
  if (available < 180) {
    setStatus(panel, "В ТЗ почти не осталось места. Сократите собственный текст — он имеет приоритет над референсами.", "error");
    target.focus({ preventScroll: true });
    return;
  }
  const block = referenceBlock(analysis, available);
  target.value = `${base}${base ? "\n\n" : ""}${block}`.slice(0, maxLength);
  target.dispatchEvent(new Event("input", { bubbles: true }));
  target.dispatchEvent(new Event("change", { bubbles: true }));
  target.dataset.referenceIntelligenceApplied = "true";
  setStatus(panel, "Вставлено в ТЗ. Референсы помечены как стиль и не считаются фактами о товаре.", "applied");
  target.focus({ preventScroll: true });
}

function clearPanel(panel) {
  q("[data-reference-urls]", panel).value = "";
  q("[data-reference-note]", panel).value = "";
  q("[data-reference-files-input]", panel).value = "";
  q("[data-reference-result]", panel).replaceChildren();
  q("[data-reference-result]", panel).hidden = true;
  q("[data-reference-apply]", panel).disabled = true;
  runtime.panels.delete(panel);
  updateFileSummary(panel);
  setStatus(panel, "Добавьте хотя бы одну ссылку или файл.");
}

function handlePanelClick(event, form, panel) {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("[data-reference-analyze]")) void analyze(form, panel);
  if (target?.closest("[data-reference-apply]")) applyToBrief(form, panel);
  if (target?.closest("[data-reference-clear]")) clearPanel(panel);
}

function mountResearch() {
  if (routePath() !== "/workspace/research") return;
  const form = q("#product-research-start-form");
  if (!form || q(":scope > .ce-reference-intelligence", form)) return;
  const panel = buildPanel(form, "research");
  const submit = q('button[type="submit"]', form);
  submit?.before(panel);
}

function mountGeneration() {
  if (routePath() !== "/workspace/generation") return;
  const form = q("#mock-batch-form");
  if (!form || q(":scope > .ce-reference-intelligence", form)) return;
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

new MutationObserver(schedule).observe(q("#app") || document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
else schedule();

window.ContentEngineReferenceIntelligence = Object.freeze({ schedule });
