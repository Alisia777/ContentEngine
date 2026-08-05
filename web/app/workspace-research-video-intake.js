/*
 * ContentEngine · exact social-video research intake.
 *
 * A YouTube page URL is an identity and metadata pointer, not a video file.
 * Never fold it into the generic paid web-search prompt and imply that the
 * provider watched the Short. Full audiovisual learning requires a lawful MP4
 * (or a separately approved media provider) before any paid analysis starts.
 */

const ROUTE = "/workspace/research";
const FORM_ID = "product-research-start-form";
const FIELD_ID = "research-training-video-url";
const PANEL_ATTRIBUTE = "data-research-training-video-intake";
const FAILURE_GUARD_ATTRIBUTE = "data-research-youtube-failure-guard";
const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/u;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const PENDING_SOURCE_PREFIX = "contentengine.research.youtube.pending.v1";

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

function filesHash() {
  const currentProjectId = projectId();
  const query = new URLSearchParams();
  if (currentProjectId) query.set("project_id", currentProjectId);
  query.set("youtube_source", "pending_media");
  return `#/workspace/board?${query.toString()}`;
}

function pendingSourceKey() {
  return `${PENDING_SOURCE_PREFIX}:${projectId() || "unscoped"}`;
}

function rememberPendingSource(canonical) {
  try {
    window.sessionStorage.setItem(pendingSourceKey(), JSON.stringify({
      canonical_url: canonical,
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
    return canonical ? { canonical } : null;
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

function createActions(form, panel, input, status) {
  const actions = el("div", "research-video-intake__actions");
  const upload = el("a", "btn btn-primary", "Перейти в Файлы и загрузить MP4");
  upload.href = filesHash();
  upload.dataset.researchVideoUpload = "true";

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
    withoutVideo.hidden = true;
    status.textContent =
      "Ролик исключён из этого запуска. Платный анализ исследует только товар и рынок.";
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
    `Источник распознан: ${canonical}. Для полного разбора загрузите MP4; платный запуск пока заблокирован.`;
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
    "Остановлено до списания: ссылка подтверждает ролик, но не содержит кадры и звук. Загрузите MP4 либо явно продолжите исследование рынка без этого ролика.";
  status.dataset.tone = "danger";
  input.focus({ preventScroll: true });
  panel.scrollIntoView({ behavior: "smooth", block: "center" });
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
  return text.includes("результат нельзя использовать")
    && text.includes("0 цитат")
    && (
      text.includes("провайдер отклонил запрос")
      || text.includes("завершил фоновый запрос без результата")
    );
}

function guardRejectedZeroCitationRun() {
  if (!zeroCitationProviderFailure()) return;
  const root = document.querySelector("main") || document.body;
  if (!root || root.querySelector(`[${FAILURE_GUARD_ATTRIBUTE}]`)) return;

  const retry = [...root.querySelectorAll("button, a")].find((node) =>
    /подготовить новый платный анализ/iu.test(String(node.textContent || ""))
  );
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
  upload.href = filesHash();
  const status = [...root.querySelectorAll("button, a")].find((node) =>
    /проверить сохранённый статус/iu.test(String(node.textContent || ""))
  );
  actions.append(upload);
  if (status instanceof HTMLElement) {
    const focusStatus = el("button", "btn btn-secondary", "Оставить квитанцию и не повторять");
    focusStatus.type = "button";
    focusStatus.addEventListener("click", () => status.focus({ preventScroll: true }));
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