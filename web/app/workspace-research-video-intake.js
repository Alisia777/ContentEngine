/*
 * ContentEngine · exact social-video research intake.
 *
 * A YouTube page URL is an identity and metadata pointer, not a video file.
 * Never fold it into the generic paid web-search prompt and imply that the
 * provider watched the Short. Full audiovisual learning requires a lawful MP4
 * (or a separately approved media provider) before any paid analysis starts.
 */

import {
  exactYoutubeResearchEvidenceRoute,
  writeExactYoutubeMediaHandoff,
} from "./exact-youtube-media-handoff.js?v=20260826.rebuild-clean.60";
import { writeExactYoutubeResearchDraft } from "./exact-youtube-research-draft.js?v=20260826.rebuild-clean.60";

const ROUTE = "/workspace/research";
const FORM_ID = "product-research-start-form";
const FIELD_ID = "research-training-video-url";
const PANEL_ATTRIBUTE = "data-research-training-video-intake";
const FAILURE_GUARD_ATTRIBUTE = "data-research-youtube-failure-guard";
const RPC_REGISTER_SOURCE = "contentengine_register_exact_youtube_source";
const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/u;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const PENDING_SOURCE_PREFIX = "contentengine.research.youtube.pending.v1";
const YOUTUBE_URL_TOKEN = /https?:\/\/[^\s<>"']+/giu;
const UNATTACHED_YOUTUBE_URL_PATTERN =
  /https?:\/\/(?:[a-z0-9-]+\.)*(?:youtube(?:-nocookie)?\.com|youtu\.be)(?:[/?#:]|$)/iu;
const MARKET_ONLY_TEXT_FIELDS = Object.freeze([
  "category_name",
  "research_focus",
  "competitor_references",
  "known_facts",
]);

export function canonicalResearchVideoUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  let url;
  try {
    url = new URL(raw);
  } catch {
    return "";
  }
  if (url.protocol !== "https:") return "";
  const host = url.hostname.toLowerCase().replace(/\.$/u, "");
  const parts = url.pathname.split("/").filter(Boolean);
  const youtubeHosts = new Set([
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
  ]);
  if (!youtubeHosts.has(host)) return "";
  const candidate = host === "youtu.be"
    ? parts[0]
    : url.pathname === "/watch"
      ? url.searchParams.get("v")
      : ["shorts", "embed", "live"].includes(parts[0] || "")
        ? parts[1]
        : "";
  return YOUTUBE_VIDEO_ID.test(String(candidate || ""))
    ? `https://youtube.com/watch?v=${candidate}`
    : "";
}

/*
 * Kept as a pure compatibility helper for old drafts and tests. The live form
 * deliberately does not call it anymore: competitor_references is text for
 * market research and must never masquerade as ingested video evidence.
 */
export function mergeResearchVideoReference(existing, videoUrl) {
  const canonical = canonicalResearchVideoUrl(videoUrl);
  const lines = String(existing || "")
    .split(/\r?\n/gu)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!canonical) return lines.join("\n");
  const canonicalLines = new Set(
    lines.map((line) => canonicalResearchVideoUrl(line) || line),
  );
  if (!canonicalLines.has(canonical)) lines.unshift(canonical);
  return lines.join("\n");
}

export function containsUnattachedYoutubeUrl(value) {
  return UNATTACHED_YOUTUBE_URL_PATTERN.test(String(value || ""));
}

/*
 * A market-only paid run may keep the creator/channel name as an orientation,
 * but it must not send an unattached YouTube page to web-search as if the
 * provider received frames or audio.  This helper removes YouTube URLs even
 * when they are embedded in a descriptive line and preserves the rest of the
 * human-authored context.
 */
export function stripExactYoutubeReferences(value) {
  return String(value || "")
    .split(/\r?\n/gu)
    .map((line) => line
      .replace(YOUTUBE_URL_TOKEN, (token) => {
        return containsUnattachedYoutubeUrl(token) ? "" : token;
      })
      .replace(/[ \t]{2,}/gu, " ")
      .trim())
    .filter(Boolean)
    .join("\n");
}

function sanitizeMarketOnlyPaidResearch(form) {
  const changed = [];
  MARKET_ONLY_TEXT_FIELDS.forEach((name) => {
    const field = form.elements?.namedItem?.(name);
    if (!field || typeof field.value !== "string") return;
    const sanitized = stripExactYoutubeReferences(field.value);
    if (sanitized === field.value) return;
    field.value = sanitized;
    changed.push(name);
  });
  const marketplace = form.elements?.namedItem?.("marketplace_url");
  if (
    marketplace
    && typeof marketplace.value === "string"
    && containsUnattachedYoutubeUrl(marketplace.value)
  ) {
    marketplace.value = "";
    changed.push("marketplace_url");
  }
  form.dataset.researchVideoMarketOnlySanitized = "true";
  return changed;
}

function routePath() {
  const apiRoute = globalThis.window?.ContentEngineDesktopV4?.route?.();
  if (apiRoute) return apiRoute;
  const raw = String(globalThis.window?.location?.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function routeParams() {
  const raw = String(globalThis.window?.location?.hash || "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  return new URLSearchParams(query);
}

function projectId() {
  const value = String(routeParams().get("project_id") || "")
    .trim()
    .toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

function hashUrl(route, values = {}) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    const normalized = String(value ?? "").trim();
    if (normalized) query.set(key, normalized);
  });
  const suffix = query.toString();
  return `#${route}${suffix ? `?${suffix}` : ""}`;
}

export function researchVideoMediaHash({
  projectId: exactProjectId = projectId(),
  sourceId = "",
  canonicalUrl = "",
  productName = "",
  productSku = "",
} = {}) {
  return hashUrl("/workspace/media", {
    view: "upload",
    project_id: exactProjectId,
    youtube_source: sourceId,
    video_url: canonicalUrl,
    product_name: productName,
    product_sku: productSku,
    return_to: hashUrl(ROUTE, {
      project_id: exactProjectId,
      source_url: canonicalUrl,
    }),
  });
}

function pendingSourceKey() {
  return `${PENDING_SOURCE_PREFIX}:${projectId() || "unscoped"}`;
}

function rememberPendingSource(canonical, sourceId = "") {
  try {
    window.sessionStorage.setItem(pendingSourceKey(), JSON.stringify({
      canonical_url: canonical,
      source_id: sourceId,
      recorded_at: new Date().toISOString(),
      required_input: "lawful_mp4",
      paid_analysis_allowed: false,
    }));
  } catch {
    // Storage failure must never reopen the paid submit path.
  }
}

function readPendingSource() {
  try {
    const raw = window.sessionStorage.getItem(pendingSourceKey());
    if (!raw) return null;
    const value = JSON.parse(raw);
    const canonical = canonicalResearchVideoUrl(value?.canonical_url);
    const sourceId = String(value?.source_id || "").trim().toLowerCase();
    return canonical
      ? { canonical, sourceId: UUID_PATTERN.test(sourceId) ? sourceId : "" }
      : null;
  } catch {
    return null;
  }
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function payloadWithOrganization(api, payload) {
  if (typeof api?.withOrganization === "function") {
    return api.withOrganization(payload);
  }
  if (api?.organizationId) {
    return { organization_id: api.organizationId, ...payload };
  }
  return payload;
}

async function getApi() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  const api = await Promise.resolve(factory());
  if (!api || typeof api.call !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  return api;
}

function idempotencyKey(prefix) {
  const suffix = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`.slice(0, 178);
}

function fieldText(form, names, limit) {
  for (const name of names) {
    const field = form.elements?.namedItem?.(name)
      || form.querySelector?.(`[name="${CSS.escape(name)}"]`);
    const value = String(field?.value || "").replace(/\s+/gu, " ").trim();
    if (value) return value.slice(0, limit);
  }
  return "";
}

function checkedFieldValues(form, name) {
  const selector = `input[name="${name}"]:checked`;
  return [...(form.querySelectorAll?.(selector) || [])]
    .map((field) => String(field?.value || "").trim())
    .filter(Boolean);
}

export function exactYoutubeResearchDraftInput(form) {
  return {
    product_category: fieldText(form, ["product_category"], 60),
    category_name: stripExactYoutubeReferences(
      fieldText(form, ["category_name"], 160),
    ),
    research_focus: stripExactYoutubeReferences(
      fieldText(form, ["research_focus"], 200),
    ),
    marketplace_url: fieldText(form, ["marketplace_url"], 1_000),
    competitor_references: stripExactYoutubeReferences(
      fieldText(form, ["competitor_references"], 650),
    ),
    objective: fieldText(form, ["objective"], 40),
    known_facts: stripExactYoutubeReferences(
      fieldText(form, ["known_facts"], 500),
    ),
    platforms: checkedFieldValues(form, "platforms"),
    source_media_ids: checkedFieldValues(form, "source_media_ids"),
  };
}

export function prepareResearchVideoMediaHandoff({
  storage,
  context = {},
  source = {},
  canonicalUrl = "",
  productName = "",
  productSku = "",
} = {}) {
  const exactProjectId = String(context.project_id || context.projectId || "")
    .trim()
    .toLowerCase();
  const exactSourceId = String(source.id || source.source_id || "")
    .trim()
    .toLowerCase();
  const sourceProjectId = String(source.project_id || exactProjectId)
    .trim()
    .toLowerCase();
  const requestedCanonical = canonicalResearchVideoUrl(canonicalUrl);
  const sourceCanonical = canonicalResearchVideoUrl(source.canonical_url || "");
  const exactCanonical = sourceCanonical || requestedCanonical;
  if (
    !UUID_PATTERN.test(exactProjectId)
    || !UUID_PATTERN.test(exactSourceId)
    || sourceProjectId !== exactProjectId
    || !exactCanonical
    || (requestedCanonical && requestedCanonical !== exactCanonical)
  ) {
    return { ok: false, code: "exact_youtube_media_handoff_scope_invalid" };
  }
  const exactProductName = String(source.product_name || productName || "")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, 300);
  const exactProductSku = String(source.product_sku || productSku || "")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, 160);
  const wrote = writeExactYoutubeMediaHandoff(storage, {
    organization_id: context.organization_id || context.organizationId,
    user_id: context.user_id || context.userId,
    session_id: context.session_id || context.sessionId,
    project_id: exactProjectId,
    source_id: exactSourceId,
    canonical_url: exactCanonical,
    product_name: exactProductName,
    product_sku: exactProductSku,
  });
  if (!wrote) {
    return { ok: false, code: "exact_youtube_media_handoff_storage_invalid" };
  }
  return {
    ok: true,
    code: "ok",
    href: researchVideoMediaHash({
      projectId: exactProjectId,
      sourceId: exactSourceId,
      canonicalUrl: exactCanonical,
      productName: exactProductName,
      productSku: exactProductSku,
    }),
    sourceId: exactSourceId,
    canonicalUrl: exactCanonical,
    productName: exactProductName,
    productSku: exactProductSku,
  };
}

async function registerExactSource(form, canonical) {
  const currentProjectId = projectId();
  const videoId = canonical.slice(-11);
  if (!UUID_PATTERN.test(currentProjectId) || !YOUTUBE_VIDEO_ID.test(videoId)) {
    throw new Error("exact_source_scope_invalid");
  }
  const api = await getApi();
  const response = await api.call(
    RPC_REGISTER_SOURCE,
    payloadWithOrganization(api, {
      project_id: currentProjectId,
      canonical_url: canonical,
      video_id: videoId,
      product_name: fieldText(
        form,
        ["product_name", "title", "name"],
        300,
      ),
      product_sku: fieldText(
        form,
        ["sku", "product_sku", "article"],
        160,
      ),
      idempotency_key: idempotencyKey(`exact-youtube-${videoId}`),
    }),
  );
  const root = response?.data && typeof response.data === "object"
    && !Array.isArray(response.data)
    ? response.data
    : response;
  const source = root?.source;
  if (
    root?.ok !== true
    || root?.version !== "exact-youtube-source-intake-v1"
    || !source
    || !UUID_PATTERN.test(String(source.id || "").toLowerCase())
    || source.project_id !== currentProjectId
    || source.video_id !== videoId
    || source.canonical_url !== canonical
    || source.status !== "awaiting_media"
    || source.media_required !== true
    || !SHA256_PATTERN.test(String(source.source_hash || ""))
    || root?.contract?.registered_in_research !== true
    || root?.contract?.visible_in_ai_center !== true
    || root?.contract?.url_is_video_evidence !== false
    || root?.contract?.paid_analysis_allowed !== false
    || root?.contract?.external_call_started !== false
    || root?.contract?.paid_call_started !== false
  ) {
    throw new Error("exact_source_response_invalid");
  }
  return source;
}

export async function openResearchVideoMediaUpload(
  event,
  form,
  panel,
  input,
  status,
  upload,
) {
  event.preventDefault();
  if (upload.dataset.busy === "true") return;
  const canonical = validateInput(input, status);
  if (!canonical) {
    input.reportValidity();
    input.focus({ preventScroll: true });
    return;
  }
  const productName = fieldText(form, ["product_name", "title", "name"], 300);
  const productSku = fieldText(form, ["sku", "product_sku", "article"], 160);
  if (!productName || !productSku) {
    status.textContent =
      "Сначала укажите точное название товара и SKU — они будут перенесены в загрузку этого MP4.";
    status.dataset.tone = "danger";
    const missing = !productName
      ? form.elements?.namedItem?.("product_name")
      : form.elements?.namedItem?.("sku");
    missing?.focus?.({ preventScroll: true });
    return;
  }
  upload.dataset.busy = "true";
  upload.setAttribute("aria-disabled", "true");
  status.textContent =
    "Сохраняем точный источник без оплаты и готовим связанную форму загрузки MP4…";
  status.dataset.tone = "warning";
  try {
    const source = await registerExactSource(form, canonical);
    const sourceId = String(source.id || "").trim().toLowerCase();
    rememberPendingSource(canonical, sourceId);
    const handoffContext = window.ContentEngineWorkspaceRuntime
      ?.getExactYoutubeHandoffContext?.() || {};
    const prepared = prepareResearchVideoMediaHandoff({
      storage: window.sessionStorage,
      context: handoffContext,
      source,
      canonicalUrl: canonical,
      productName,
      productSku,
    });
    if (!prepared.ok) throw new Error(prepared.code);
    if (!writeExactYoutubeResearchDraft(window.sessionStorage, {
      ...handoffContext,
      project_id: String(source.project_id || projectId()).trim().toLowerCase(),
      source_id: sourceId,
      ...exactYoutubeResearchDraftInput(form),
    })) {
      throw new Error("exact_youtube_research_draft_storage_invalid");
    }
    panel.dataset.sourceId = prepared.sourceId;
    panel.dataset.sourceMode = "awaiting-media";
    upload.href = prepared.href;
    status.textContent =
      "Источник сохранён без оплаты. Открываем форму одного точного MP4 с уже заполненными товаром и SKU.";
    status.dataset.tone = "ready";
    window.location.hash = prepared.href.slice(1);
  } catch {
    upload.removeAttribute("aria-disabled");
    status.textContent =
      "Платный запуск не выполнялся. Не удалось подготовить точную связь с MP4 — обновите Исследования и повторите эту кнопку.";
    status.dataset.tone = "danger";
  } finally {
    delete upload.dataset.busy;
  }
}

function createActions(form, panel, input, status) {
  const actions = el("div", "research-video-intake__actions");
  const upload = el("a", "btn btn-primary", "Перейти в Файлы и загрузить MP4");
  upload.href = hashUrl(ROUTE, { project_id: projectId() });
  upload.dataset.researchVideoUpload = "true";
  upload.addEventListener("click", (event) => {
    void openResearchVideoMediaUpload(
      event,
      form,
      panel,
      input,
      status,
      upload,
    );
  });

  const withoutVideo = el(
    "button",
    "btn btn-secondary",
    "Продолжить исследование рынка без разбора ролика",
  );
  withoutVideo.type = "button";
  withoutVideo.dataset.researchVideoBypass = "true";
  withoutVideo.hidden = true;
  withoutVideo.addEventListener("click", () => {
    input.value = "";
    input.setCustomValidity("");
    panel.dataset.sourceMode = "market-only";
    const sanitizedFields = sanitizeMarketOnlyPaidResearch(form);
    withoutVideo.hidden = true;
    status.textContent =
      sanitizedFields.length
        ? "Ролик и его YouTube-ссылки исключены из платного запроса. Анализ исследует только товар и рынок."
        : "Ролик исключён из этого запуска. Платный анализ исследует только товар и рынок.";
    status.dataset.tone = "neutral";
    form.requestSubmit();
  });

  actions.append(upload, withoutVideo);
  panel.append(actions);
  return { upload, withoutVideo };
}

function createPanel(form) {
  const panel = el("section", "research-video-intake card card-pad");
  panel.setAttribute(PANEL_ATTRIBUTE, "true");
  panel.setAttribute("aria-labelledby", `${FIELD_ID}-title`);

  const heading = el("div", "research-video-intake__heading");
  const mark = el("span", "research-video-intake__mark", "AI");
  mark.setAttribute("aria-hidden", "true");
  const copy = el("div");
  const eyebrow = el("p", "eyebrow", "ОБУЧАЮЩИЙ ВИДЕОИСТОЧНИК");
  const title = el("h2", "", "Ролик, который ИИ должен разобрать");
  title.id = `${FIELD_ID}-title`;
  const intro = el(
    "p",
    "muted",
    "Ссылка фиксирует точный ролик, но не передаёт его видеоряд провайдеру. Для настоящего разбора кадров и речи сначала нужен законно полученный MP4; до этого платный анализ не запускается.",
  );
  copy.append(eyebrow, title, intro);
  heading.append(mark, copy);

  const label = el("label", "field research-video-intake__field");
  const labelText = el("span", "", "Ссылка на YouTube Shorts / видео");
  const input = el("input");
  input.id = FIELD_ID;
  input.type = "url";
  input.inputMode = "url";
  input.autocomplete = "off";
  input.placeholder = "https://www.youtube.com/shorts/…";
  input.setAttribute("aria-describedby", `${FIELD_ID}-hint ${FIELD_ID}-status`);
  const hint = el(
    "small",
    "field-hint",
    "Shorts, youtu.be и watch приводятся к одному ID. Это проверяет идентичность ссылки, но не означает, что ИИ просмотрел видео.",
  );
  hint.id = `${FIELD_ID}-hint`;
  const status = el("small", "research-video-intake__status");
  status.id = `${FIELD_ID}-status`;
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  label.append(labelText, input, hint, status);

  const flow = el("ol", "research-video-intake__flow");
  [
    ["1", "Точный источник", "Портал сохраняет canonical URL и ID без платного вызова."],
    ["2", "Видео как файл", "MP4 даёт кадры и звук; одна страница YouTube этого не даёт."],
    ["3", "ИИ-центр", "После реального разбора появляются выводы и редактируемые сценарии."],
    ["4", "Ваш отбор", "Обучение начинается только после выбора в ИИ-центре."],
  ].forEach(([number, name, description]) => {
    const item = el("li");
    item.append(
      el("span", "research-video-intake__flow-number", number),
      el("strong", "", name),
      el("small", "", description),
    );
    flow.append(item);
  });

  const note = el("p", "research-video-intake__note");
  note.textContent =
    "Защита от повторного списания: URL без доступного видеоматериала никогда не отправляется в общий платный web-search как будто это просмотренный ролик.";
  panel.append(heading, label, flow, note);

  const competitor = form.elements?.competitor_references;
  const anchor = competitor?.closest?.("label") || competitor;
  if (anchor?.parentNode) anchor.parentNode.insertBefore(panel, anchor);
  else form.prepend(panel);
  createActions(form, panel, input, status);
  return panel;
}

function prefillInput(input) {
  const params = routeParams();
  const candidate = params.get("source_url") || params.get("video_url") || "";
  const pending = readPendingSource();
  if (input.value) return;
  input.value = candidate || pending?.canonical || "";
}

function validateInput(input, status) {
  const raw = input.value.trim();
  const canonical = canonicalResearchVideoUrl(raw);
  if (!raw) {
    input.setCustomValidity("");
    status.textContent = "Можно оставить пустым и использовать обычный анализ товара и рынка.";
    status.dataset.tone = "neutral";
    return "";
  }
  if (!canonical) {
    input.setCustomValidity("Вставьте публичную HTTPS-ссылку на YouTube Shorts или видео.");
    status.textContent = "Ссылка не распознана. Нужен публичный YouTube URL с ID ролика.";
    status.dataset.tone = "danger";
    return "";
  }
  input.setCustomValidity("");
  status.textContent =
    `Источник распознан: ${canonical}. Нажатие запуска сохранит его в Исследованиях без оплаты и запросит MP4.`;
  status.dataset.tone = "warning";
  return canonical;
}

function blockUrlOnlySubmit(event, form, panel, input, status, canonical) {
  event.preventDefault();
  event.stopImmediatePropagation();
  rememberPendingSource(canonical);
  panel.dataset.sourceMode = "media-required";
  const bypass = panel.querySelector("[data-research-video-bypass]");
  if (bypass instanceof HTMLButtonElement) bypass.hidden = false;
  status.textContent =
    "Остановлено до списания. Сохраняем точный источник в Исследованиях; для разбора кадров и звука затем нужен MP4.";
  status.dataset.tone = "warning";
  input.focus({ preventScroll: true });
  panel.scrollIntoView({ behavior: "smooth", block: "center" });

  void registerExactSource(form, canonical).then((source) => {
    const sourceId = String(source.id).toLowerCase();
    panel.dataset.sourceId = sourceId;
    panel.dataset.sourceMode = "awaiting-media";
    rememberPendingSource(canonical, sourceId);
    const upload = panel.querySelector("[data-research-video-upload]");
    if (upload instanceof HTMLAnchorElement) {
      upload.href = hashUrl(ROUTE, { project_id: projectId() });
    }
    status.textContent =
      "Шаг 1 выполнен: ролик сохранён в Исследованиях и уже виден в ИИ-центре как источник, ожидающий MP4. Платного вызова не было.";
    status.dataset.tone = "ready";
  }).catch(() => {
    panel.dataset.sourceMode = "registration-failed";
    status.textContent =
      "Платный запуск заблокирован, но сервер не подтвердил сохранение источника. Обновите страницу; повторной оплаты не будет.";
    status.dataset.tone = "danger";
  });
}

function bind(form, panel) {
  if (form.dataset.researchTrainingVideoBound === "true") return;
  form.dataset.researchTrainingVideoBound = "true";
  const input = panel.querySelector(`#${FIELD_ID}`);
  const status = panel.querySelector(`#${FIELD_ID}-status`);
  if (!(input instanceof HTMLInputElement) || !status) return;
  prefillInput(input);
  validateInput(input, status);

  input.addEventListener("input", () => validateInput(input, status));
  input.addEventListener("blur", () => validateInput(input, status));
  form.addEventListener("submit", (event) => {
    if (panel.dataset.sourceMode === "market-only") {
      sanitizeMarketOnlyPaidResearch(form);
    }
    const canonical = validateInput(input, status);
    if (input.value.trim() && !canonical) {
      event.preventDefault();
      event.stopImmediatePropagation();
      input.reportValidity();
      input.focus();
      return;
    }
    if (!canonical || panel.dataset.sourceMode === "market-only") return;
    blockUrlOnlySubmit(event, form, panel, input, status, canonical);
  }, { capture: true });
}

function zeroCitationProviderFailure() {
  const text = String(document.body?.innerText || "")
    .replace(/\s+/gu, " ")
    .toLocaleLowerCase("ru-RU");
  return text.includes("0 цитат")
    && text.includes("результат нельзя использовать")
    && (
      text.includes("провайдер отклонил запрос")
      || text.includes("завершил фоновый запрос без результата")
    );
}

export function exactVideoFailureEvidence(value = {}) {
  const source = value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
  const uuid = (candidate) => {
    const normalized = String(candidate || "").trim().toLowerCase();
    return UUID_PATTERN.test(normalized) ? normalized : "";
  };
  const boundedText = (candidate, limit) => {
    const normalized = String(candidate || "").replace(/\s+/gu, " ").trim();
    return normalized.length <= limit ? normalized : "";
  };
  const normalized = {
    verified: source.verified === true || source.verified === "verified",
    markerSource: String(
      source.markerSource || source.marker_source || "",
    ).trim(),
    sourceId: uuid(source.sourceId || source.source_id),
    attachmentId: uuid(source.attachmentId || source.attachment_id),
    mediaId: uuid(source.mediaId || source.media_id),
    evidenceId: uuid(source.evidenceId || source.evidence_id),
    frameCount: Number(source.frameCount ?? source.frame_count),
    analysisScope: String(
      source.analysisScope || source.analysis_scope || "",
    ).trim().toLowerCase(),
    productName: boundedText(
      source.productName || source.product_name,
      180,
    ),
    productSku: boundedText(source.productSku || source.product_sku, 120),
  };
  return normalized.verified
      && normalized.markerSource === "server_exact_video_binding"
      && normalized.sourceId
      && normalized.attachmentId
      && normalized.mediaId
      && normalized.evidenceId
      && normalized.frameCount === 5
      && normalized.analysisScope === "sampled_frames_only"
    ? normalized
    : null;
}

export function exactVideoTerminalFailure({ evidence, terminalStatus } = {}) {
  const normalizedEvidence = exactVideoFailureEvidence(evidence);
  const normalizedStatus = String(terminalStatus || "").trim().toLowerCase();
  return normalizedEvidence
      && ["failed", "cancelled", "incomplete"].includes(normalizedStatus)
    ? { evidence: normalizedEvidence, terminalStatus: normalizedStatus }
    : null;
}

function exactVideoFailureEvidenceFromPage(root) {
  const marker = root.querySelector(
    '[data-research-exact-video-evidence="verified"]',
  );
  if (!(marker instanceof HTMLElement)) return null;
  return exactVideoFailureEvidence({
    verified: marker.dataset.researchExactVideoEvidence,
    markerSource: marker.dataset.exactVideoMarkerSource,
    sourceId: marker.dataset.exactVideoSourceId,
    attachmentId: marker.dataset.exactVideoAttachmentId,
    mediaId: marker.dataset.exactVideoMediaId,
    evidenceId: marker.dataset.exactVideoEvidenceId,
    frameCount: marker.dataset.exactVideoFrameCount,
    analysisScope: marker.dataset.exactVideoAnalysisScope,
    productName: marker.dataset.exactVideoProductName,
    productSku: marker.dataset.exactVideoProductSku,
  });
}

function guardRejectedZeroCitationRun() {
  const root = document.querySelector("main") || document.body;
  if (!root || root.querySelector(`[${FAILURE_GUARD_ATTRIBUTE}]`)) return;
  const exactEvidence = exactVideoFailureEvidenceFromPage(root);
  const terminalReceipt = root.querySelector(
    '[data-provider-terminal-status="failed"], [data-provider-terminal-status="cancelled"], [data-provider-terminal-status="incomplete"]',
  );
  const exactTerminalFailure = exactVideoTerminalFailure({
    evidence: exactEvidence,
    terminalStatus: terminalReceipt instanceof HTMLElement
      ? terminalReceipt.dataset.providerTerminalStatus
      : "",
  });
  if (!exactTerminalFailure && !zeroCitationProviderFailure()) return;

  const retry = [...root.querySelectorAll("button, a")].find((node) =>
    /подготовить новый платный анализ/iu.test(String(node.textContent || ""))
  );
  if (exactTerminalFailure) {
    if (retry instanceof HTMLButtonElement) {
      retry.disabled = true;
      retry.textContent = "Новый запуск — только с новым evidence";
      retry.title = "Сначала создайте новый одноразовый набор из пяти кадров из уже сохранённого MP4.";
    } else if (retry instanceof HTMLAnchorElement) {
      retry.removeAttribute("href");
      retry.setAttribute("aria-disabled", "true");
      retry.textContent = "Новый запуск — только с новым evidence";
    }

    const guard = el(
      "section",
      "research-youtube-failure-guard card card-pad",
    );
    guard.setAttribute(FAILURE_GUARD_ATTRIBUTE, "true");
    guard.dataset.failureMode = "exact-video-provider-terminal";
    guard.setAttribute("role", "alert");
    guard.append(
      el("p", "eyebrow", "ТОЧНАЯ ПРИЧИНА ЗАФИКСИРОВАНА"),
      el(
        "h2",
        "",
        "Пять кадров проверены и переданы; провайдер завершил запрос с ошибкой",
      ),
      el(
        "p",
        "",
        "Сервер подтвердил привязку исходного MP4 и одноразового evidence-набора из 5 JPEG, затем провайдер принял запрос. Подтверждённые цитаты не были сохранены из-за terminal-ошибки, а не потому, что кадры не передавались. Автоматического повтора и нового списания не было.",
      ),
      el(
        "p",
        "",
        "Повторно загружать MP4 не нужно. Для нового анализа портал заново проверит сохранённые source/attachment/media, создаст новый набор из 5 кадров и только после отдельных подтверждений обработки ИИ и оплаты разрешит новый POST.",
      ),
    );
    const actions = el("div", "research-video-intake__actions");
    const route = exactYoutubeResearchEvidenceRoute({
      projectId: projectId(),
      sourceId: exactTerminalFailure.evidence.sourceId,
      attachmentId: exactTerminalFailure.evidence.attachmentId,
      mediaId: exactTerminalFailure.evidence.mediaId,
      productName: exactTerminalFailure.evidence.productName,
      productSku: exactTerminalFailure.evidence.productSku,
    });
    if (route) {
      const prepare = el(
        "a",
        "btn btn-primary",
        "Создать новый набор из 5 кадров из сохранённого MP4",
      );
      prepare.href = `#${route}`;
      prepare.dataset.researchExactEvidenceRecovery = "true";
      actions.append(prepare);
    }
    const refresh = [...root.querySelectorAll("button, a")].find((node) =>
      /проверить сохранённый статус/iu.test(String(node.textContent || ""))
    );
    if (refresh instanceof HTMLElement) {
      const focusStatus = el(
        "button",
        "btn btn-secondary",
        "Оставить квитанцию и не повторять",
      );
      focusStatus.type = "button";
      focusStatus.addEventListener("click", () =>
        refresh.focus({ preventScroll: true })
      );
      actions.append(focusStatus);
    }
    guard.append(actions);
    const providerControl = [...root.querySelectorAll("section")].find(
      (section) => /контроль платного провайдера/iu.test(
        String(section.textContent || ""),
      ),
    );
    if (providerControl?.parentNode) {
      providerControl.parentNode.insertBefore(guard, providerControl);
    } else {
      root.prepend(guard);
    }
    return;
  }

  if (retry instanceof HTMLButtonElement) {
    retry.disabled = true;
    retry.textContent = "Не повторять: источник не прочитан";
    retry.title = "Повторный платный web-search не превратит URL YouTube в видеоматериал.";
  } else if (retry instanceof HTMLAnchorElement) {
    retry.removeAttribute("href");
    retry.setAttribute("aria-disabled", "true");
    retry.textContent = "Не повторять: источник не прочитан";
  }

  const guard = el("section", "research-youtube-failure-guard card card-pad");
  guard.setAttribute(FAILURE_GUARD_ATTRIBUTE, "true");
  guard.setAttribute("role", "alert");
  guard.append(
    el("p", "eyebrow", "ПРИЧИНА НАЙДЕНА"),
    el("h2", "", "Shorts распознан как ссылка, но не был передан как видео"),
    el(
      "p",
      "",
      "Этот запуск отправил URL в обычный OpenAI web-search. Провайдер не получил кадры и звук, не нашёл подтверждаемую страницу и завершил запрос с нулём цитат. Новый такой же запуск платить не нужно.",
    ),
  );
  const pending = readPendingSource();
  if (pending?.canonical) {
    const code = el("code", "", pending.canonical);
    const source = el("p", "research-youtube-failure-guard__source");
    source.append("Ожидающий источник: ", code);
    guard.append(source);
  }
  const actions = el("div", "research-video-intake__actions");
  const upload = el("a", "btn btn-primary", "Загрузить MP4 для настоящего разбора");
  upload.href = researchVideoMediaHash({
    projectId: projectId(),
    sourceId: pending?.sourceId || "",
    canonicalUrl: pending?.canonical || "",
  });
  const savedStatus = [...root.querySelectorAll("button, a")].find((node) =>
    /проверить сохранённый статус/iu.test(String(node.textContent || ""))
  );
  actions.append(upload);
  if (savedStatus instanceof HTMLElement) {
    const focusStatus = el("button", "btn btn-secondary", "Оставить квитанцию и не повторять");
    focusStatus.type = "button";
    focusStatus.addEventListener("click", () =>
      savedStatus.focus({ preventScroll: true })
    );
    actions.append(focusStatus);
  }
  guard.append(actions);

  const providerControl = [...root.querySelectorAll("section")].find((section) =>
    /контроль платного провайдера/iu.test(String(section.textContent || ""))
  );
  if (providerControl?.parentNode) {
    providerControl.parentNode.insertBefore(guard, providerControl);
  } else {
    root.prepend(guard);
  }
}

function mount() {
  if (routePath() !== ROUTE) return;
  guardRejectedZeroCitationRun();
  const form = document.getElementById(FORM_ID);
  if (!(form instanceof HTMLFormElement)) return;
  let panel = form.querySelector(`[${PANEL_ATTRIBUTE}]`);
  if (!panel) panel = createPanel(form);
  bind(form, panel);
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "research-video-intake",
      mount,
      { priority: 175 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", mount);
  window.addEventListener("hashchange", () => window.queueMicrotask(mount));
  window.queueMicrotask(mount);
}

export const ResearchVideoIntake = Object.freeze({
  mount,
  canonicalize: canonicalResearchVideoUrl,
  merge: mergeResearchVideoReference,
});
