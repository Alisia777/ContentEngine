/*
 * ContentEngine · exact social-video research intake.
 *
 * Adds one explicit source field to the existing paid research form. The value
 * is folded into the existing competitor/reference payload before the mature
 * submit handler runs, so billing, idempotency, category binding and provider
 * safeguards remain owned by the original workflow.
 */

const ROUTE = "/workspace/research";
const FORM_ID = "product-research-start-form";
const FIELD_ID = "research-training-video-url";
const PANEL_ATTRIBUTE = "data-research-training-video-intake";
const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/u;

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

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function createPanel(form) {
  const panel = el("section", "research-video-intake card card-pad");
  panel.setAttribute(PANEL_ATTRIBUTE, "true");
  panel.setAttribute("aria-labelledby", `${FIELD_ID}-title`);

  const heading = el("div", "research-video-intake__heading");
  const mark = el("span", "research-video-intake__mark", "AI");
  mark.setAttribute("aria-hidden", "true");
  const copy = el("div");
  const eyebrow = el("p", "eyebrow", "ОБУЧАЮЩИЙ ИСТОЧНИК");
  const title = el("h2", "", "Ролик, который ИИ должен разобрать");
  title.id = `${FIELD_ID}-title`;
  const intro = el(
    "p",
    "muted",
    "Портал добавит точную ссылку в исследование, сохранит разбор во входящих ИИ-центра и только после вашего отбора превратит выводы в рекомендации.",
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
    "Поддерживаются публичные HTTPS-ссылки YouTube. Портал приводит Shorts, youtu.be и watch к одному источнику, чтобы один ролик не дублировался.",
  );
  hint.id = `${FIELD_ID}-hint`;
  const status = el("small", "research-video-intake__status");
  status.id = `${FIELD_ID}-status`;
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  label.append(labelText, input, hint, status);

  const flow = el("ol", "research-video-intake__flow");
  [
    ["1", "Исследования", "Ролик проходит тот же платный анализ и проверку источника."],
    ["2", "ИИ-центр", "Появляются разбор, ограничения, тренды и варианты сценариев."],
    ["3", "Ваш отбор", "Вы отмечаете полезные выводы и редактируете рекомендации."],
    ["4", "Создание", "ИИ подставляет готовый замысел; человек может изменить всё."],
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
  note.textContent = "Важно: сам факт загрузки не обучает ИИ молча. Обучение начинается только после выбора в ИИ-центре.";
  panel.append(heading, label, flow, note);

  const competitor = form.elements?.competitor_references;
  const anchor = competitor?.closest?.("label") || competitor;
  if (anchor?.parentNode) anchor.parentNode.insertBefore(panel, anchor);
  else form.prepend(panel);
  return panel;
}

function prefillInput(input) {
  const params = routeParams();
  const candidate = params.get("source_url") || params.get("video_url") || "";
  if (!candidate || input.value) return;
  input.value = candidate;
}

function validateInput(input, status) {
  const raw = input.value.trim();
  const canonical = canonicalResearchVideoUrl(raw);
  if (!raw) {
    input.setCustomValidity("");
    status.textContent = "Можно оставить пустым и использовать обычный анализ рынка.";
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
  status.textContent = `Источник распознан: ${canonical}`;
  status.dataset.tone = "ready";
  return canonical;
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
    if (!canonical) return;
    const references = form.elements?.competitor_references;
    if (!(references instanceof HTMLTextAreaElement)) return;
    references.value = mergeResearchVideoReference(references.value, canonical);
    references.dispatchEvent(new Event("input", { bubbles: true }));
    panel.dataset.boundSource = canonical;
    status.textContent = "Ролик добавлен в источники запуска. После завершения откройте ИИ-центр и выберите, чему учиться.";
    status.dataset.tone = "ready";
  }, { capture: true });
}

function mount() {
  if (routePath() !== ROUTE) return;
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
