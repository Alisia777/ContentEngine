/*
 * ContentEngine Desktop · UI Bug Check-In.
 *
 * Presentation-only diagnostics. The module never calls an API, submits a
 * business form, reads credentials/cookies or serializes page content. It
 * captures only technical geometry, build/route/browser facts and text entered
 * explicitly into the report form. Access: Mission Control utility card or
 * Cmd/Ctrl + Shift + B. No new Dock item.
 */

const BUILD = "20260803.os4.2.1";
const DRAFT_PREFIX = "contentengine.ui-bug-checkin.v1";
const MAX_RUNTIME_ERRORS = 20;
const MAX_DESCRIPTOR_EXAMPLES = 8;
const runtime = {
  overlay: null,
  previousFocus: null,
  diagnostics: null,
  screenshot: null,
  screenshotUrl: "",
  errors: [],
  missionTimers: new Set(),
};

const SEVERITY_WEIGHT = Object.freeze({ P0: 4, P1: 3, P2: 2, P3: 1 });
const DUPLICATE_CHROME = [
  ".ce-mac-dock",
  ".workspace-task-dock",
  ".workspace-deckbar",
  ".learning-command-bar",
  ".workspace-contextbar",
  ".workspace-context-bar",
].join(",");
const LOCAL_CHROME = [
  ".review-os-topbar",
  ".generation-os-topbar",
  ".media-finder-topbar",
  ".work-stage-topbar",
  ".tasks-desk-topbar",
  ".publishing-os-topbar",
  ".results-os-topbar",
  ".payout-ledger-topbar",
  ".academy-os-topbar",
  ".academy-v2-topbar",
  ".generation-os-step-dock",
  ".review-os-step-dock",
  ".review-result-dock",
  ".academy-v2-dock",
  ".academy-os-dock",
  ".publishing-os-dock",
  ".work-stage-tabs",
  ".tasks-desk-tabs",
  ".results-os-tabs",
  ".payout-ledger-tabs",
].join(",");

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/g, "/")
    .replace(/\/$/, "") || "/";
}

function isVisible(node) {
  if (!(node instanceof Element) || node.hidden) return false;
  const style = window.getComputedStyle(node);
  if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
  const rect = node.getBoundingClientRect();
  return rect.width > 0.5 && rect.height > 0.5;
}

function visible(selector, root = document) {
  return qa(selector, root).filter(isVisible);
}

function safeStorage() {
  try { return window.sessionStorage; }
  catch { return null; }
}

function draftKey(route = routePath()) {
  return `${DRAFT_PREFIX}:${route}`;
}

function readDraft() {
  try {
    const value = JSON.parse(safeStorage()?.getItem(draftKey()) || "null");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function writeDraft(value) {
  try { safeStorage()?.setItem(draftKey(), JSON.stringify(value)); }
  catch { /* Draft persistence is optional. */ }
}

function clearDraft() {
  try { safeStorage()?.removeItem(draftKey()); }
  catch { /* Optional. */ }
}

function compact(value, limit = 180) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function sanitizeRuntimeMessage(value) {
  return compact(value, 360)
    .replace(/https?:\/\/[^\s)\]}]+/giu, "[url]")
    .replace(/\b(?:eyJ[A-Za-z0-9._-]{20,}|sb_(?:secret|publishable)_[A-Za-z0-9._-]+)\b/gu, "[redacted]")
    .replace(/[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}/gu, "[email]");
}

function captureRuntimeError(event) {
  let message = "";
  let kind = "error";
  if (event instanceof PromiseRejectionEvent) {
    kind = "unhandledrejection";
    message = event.reason instanceof Error ? event.reason.message : String(event.reason || "Promise rejected");
  } else if (event.target instanceof HTMLScriptElement || event.target instanceof HTMLLinkElement) {
    kind = "resource_error";
    const source = event.target instanceof HTMLScriptElement ? event.target.src : event.target.href;
    try { message = new URL(source, window.location.href).pathname.split("/").at(-1) || "resource"; }
    catch { message = "resource"; }
  } else {
    message = event.error instanceof Error ? event.error.message : String(event.message || "Runtime error");
  }
  runtime.errors.push({
    kind,
    message: sanitizeRuntimeMessage(message),
    at: new Date().toISOString(),
  });
  if (runtime.errors.length > MAX_RUNTIME_ERRORS) runtime.errors.splice(0, runtime.errors.length - MAX_RUNTIME_ERRORS);
}

function browserFacts() {
  const ua = String(navigator.userAgent || "");
  let browser = "Unknown";
  if (/Edg\//u.test(ua)) browser = "Edge";
  else if (/CriOS\//u.test(ua)) browser = "Chrome iOS";
  else if (/FxiOS\//u.test(ua)) browser = "Firefox iOS";
  else if (/Chrome\//u.test(ua)) browser = "Chrome";
  else if (/Firefox\//u.test(ua)) browser = "Firefox";
  else if (/Safari\//u.test(ua) && /Version\//u.test(ua)) browser = "Safari";
  const mobile = /Mobile|Android|iPhone|iPad/iu.test(ua);
  return {
    browser,
    mobile,
    platform: compact(navigator.userAgentData?.platform || navigator.platform || "unknown", 80),
    language: compact(navigator.language || "unknown", 35),
  };
}

function buildId() {
  return String(
    window.CONTENTENGINE_BUILD?.id
      || q('meta[name="contentengine-build"]')?.getAttribute("content")
      || window.ContentEngineDesktopV4Loader?.build
      || BUILD,
  );
}

function descriptor(node) {
  if (!(node instanceof Element)) return "unknown";
  const tag = node.tagName.toLocaleLowerCase("en-US");
  const id = /^[A-Za-z][A-Za-z0-9_-]{0,80}$/u.test(node.id || "") ? `#${node.id}` : "";
  const classes = [...node.classList]
    .filter((value) => /^[A-Za-z][A-Za-z0-9_-]{0,60}$/u.test(value))
    .slice(0, 4)
    .map((value) => `.${value}`)
    .join("");
  return `${tag}${id}${classes}`;
}

function currentPage() {
  return visible(
    ".workspace-main .page-wrap, .workspace-main .learning-page, #main-content > .page-wrap, #main-content > .learning-page",
  ).at(-1) || q(".workspace-main") || q("#main-content") || document.body;
}

function activeSurface() {
  const preferred = visible('[data-ce-v4-primary-surface="true"], [data-ce-v4-surface="true"]');
  return preferred.at(-1) || currentPage();
}

function addIssue(issues, severity, code, title, detail, examples = []) {
  issues.push({
    severity,
    code,
    title,
    detail,
    examples: examples.slice(0, MAX_DESCRIPTOR_EXAMPLES),
  });
}

function scanTinyControls(surface, issues) {
  const candidates = visible("button, input, select, textarea, [role='button'], [role='tab'], a", surface)
    .filter((node) => !node.closest(".ce-ui-checkin-backdrop"))
    .slice(0, 1_500);
  const tiny = candidates.filter((node) => {
    const rect = node.getBoundingClientRect();
    return (rect.height > 0 && rect.height < 40) || (rect.width > 0 && rect.width < 32);
  });
  if (tiny.length) {
    addIssue(
      issues,
      tiny.length > 8 ? "P1" : "P2",
      "controls_below_touch_floor",
      "Есть слишком мелкие управляющие элементы",
      `${tiny.length} видимых контролов меньше 40 px по высоте или 32 px по ширине.`,
      tiny.map(descriptor),
    );
  }
  return { scanned: candidates.length, tiny: tiny.length };
}

function scanTinyText(surface, issues) {
  const candidates = visible("button, a, label, small, p, span, strong, th, td", surface)
    .filter((node) => !node.closest(".ce-ui-checkin-backdrop"))
    .filter((node) => compact(node.textContent, 12).length > 0)
    .slice(0, 1_800);
  const tiny = candidates.filter((node) => Number.parseFloat(window.getComputedStyle(node).fontSize || "0") < 12);
  if (tiny.length) {
    addIssue(
      issues,
      tiny.length > 20 ? "P1" : "P2",
      "text_below_readability_floor",
      "Есть текст меньше 12 px",
      `${tiny.length} видимых текстовых элементов ниже минимального вторичного кегля.`,
      tiny.map(descriptor),
    );
  }
  return { scanned: candidates.length, tiny: tiny.length };
}

function scanFixedPanels(surface, issues) {
  const candidates = visible(LOCAL_CHROME, surface);
  const fixed = candidates.filter((node) => {
    const style = window.getComputedStyle(node);
    return style.position === "fixed" || style.position === "sticky" && node.getBoundingClientRect().height > 96;
  });
  if (fixed.length) {
    addIssue(
      issues,
      "P1",
      "local_chrome_floats_over_workspace",
      "Локальная панель может перекрывать рабочий стол",
      `${fixed.length} локальных панелей остаются fixed или чрезмерно крупными sticky-элементами.`,
      fixed.map(descriptor),
    );
  }
  return { visible: candidates.length, fixed: fixed.length };
}

function scanSurfaceContent(surface, issues) {
  const rect = surface.getBoundingClientRect();
  const textLength = compact(surface.textContent, 4_000).length;
  const meaningful = visible("button, input, textarea, select, img, video, canvas, table, article, section", surface)
    .filter((node) => node !== surface)
    .length;
  if (rect.width > 300 && rect.height > 300 && textLength < 20 && meaningful < 2) {
    addIssue(
      issues,
      "P0",
      "empty_or_black_surface",
      "Активный рабочий стол выглядит пустым",
      "Большая видимая поверхность почти не содержит текста, контролов или медиа.",
      [descriptor(surface)],
    );
  }
  const overflow = Math.max(0, surface.scrollWidth - surface.clientWidth);
  if (overflow > 3) {
    addIssue(
      issues,
      overflow > 80 ? "P1" : "P2",
      "horizontal_surface_overflow",
      "Рабочий стол шире окна",
      `Горизонтальное переполнение активной поверхности: ${Math.round(overflow)} px.`,
      [descriptor(surface)],
    );
  }
  return {
    descriptor: descriptor(surface),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    text_length: textLength,
    meaningful_nodes: meaningful,
    horizontal_overflow_px: Math.round(overflow),
  };
}

function diagnose() {
  const issues = [];
  const surface = activeSurface();
  const globalDocks = visible(".ce-v4-dock");
  const menubars = visible(".ce-v4-menubar");
  const duplicateChrome = visible(DUPLICATE_CHROME);
  const primaryContextbars = visible('[data-ce-v4-contextbar="primary"]');
  const primarySurfaces = visible('[data-ce-v4-primary-surface="true"]');

  if (globalDocks.length !== 1) {
    addIssue(
      issues,
      "P0",
      "global_dock_count_invalid",
      "Нарушен единый системный Dock",
      `Ожидался один Dock, найдено: ${globalDocks.length}.`,
      globalDocks.map(descriptor),
    );
  }
  if (menubars.length !== 1) {
    addIssue(
      issues,
      "P0",
      "global_menubar_count_invalid",
      "Нарушена единая системная строка",
      `Ожидалась одна системная строка, найдено: ${menubars.length}.`,
      menubars.map(descriptor),
    );
  }
  if (duplicateChrome.length) {
    addIssue(
      issues,
      "P0",
      "duplicate_global_chrome_visible",
      "Поверх Desktop виден старый слой навигации",
      `Найдено конфликтующих legacy-панелей: ${duplicateChrome.length}.`,
      duplicateChrome.map(descriptor),
    );
  }
  if (primaryContextbars.length > 1) {
    addIssue(
      issues,
      "P1",
      "multiple_contextbars_visible",
      "Одновременно видны несколько локальных меню",
      `Primary contextual bars: ${primaryContextbars.length}.`,
      primaryContextbars.map(descriptor),
    );
  }
  if (primarySurfaces.length > 1) {
    addIssue(
      issues,
      "P0",
      "multiple_primary_surfaces_visible",
      "Одновременно активны несколько рабочих поверхностей",
      `Primary surfaces: ${primarySurfaces.length}.`,
      primarySurfaces.map(descriptor),
    );
  }

  const documentOverflow = Math.max(0, document.documentElement.scrollWidth - window.innerWidth);
  if (documentOverflow > 3) {
    addIssue(
      issues,
      documentOverflow > 80 ? "P1" : "P2",
      "document_horizontal_overflow",
      "Страница имеет горизонтальное переполнение",
      `Документ шире viewport на ${Math.round(documentOverflow)} px.`,
      [descriptor(document.documentElement)],
    );
  }

  const controlScan = scanTinyControls(surface, issues);
  const textScan = scanTinyText(surface, issues);
  const localChromeScan = scanFixedPanels(surface, issues);
  const surfaceScan = scanSurfaceContent(surface, issues);
  const browser = browserFacts();
  const severity = issues.reduce(
    (current, issue) => SEVERITY_WEIGHT[issue.severity] > SEVERITY_WEIGHT[current] ? issue.severity : current,
    "P3",
  );

  return Object.freeze({
    schema_version: "contentengine_ui_bug_checkin.v1",
    captured_at: new Date().toISOString(),
    build: buildId(),
    route: routePath(),
    browser,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
      device_pixel_ratio: window.devicePixelRatio || 1,
      orientation: window.screen?.orientation?.type || "unknown",
    },
    environment: {
      online: navigator.onLine,
      reduced_motion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      dark_scheme: window.matchMedia("(prefers-color-scheme: dark)").matches,
      touch_points: navigator.maxTouchPoints || 0,
      font_status: document.fonts?.status || "unknown",
    },
    chrome: {
      global_docks: globalDocks.length,
      global_menubars: menubars.length,
      duplicate_legacy_chrome: duplicateChrome.length,
      primary_contextbars: primaryContextbars.length,
      primary_surfaces: primarySurfaces.length,
    },
    scans: {
      controls: controlScan,
      text: textScan,
      local_chrome: localChromeScan,
      surface: surfaceScan,
      document_horizontal_overflow_px: Math.round(documentOverflow),
    },
    runtime_errors: runtime.errors.slice(-MAX_RUNTIME_ERRORS),
    suggested_severity: severity,
    issues,
  });
}

function missionIcon() {
  const api = window.ContentEngineDesktopV4;
  if (typeof api?.icon === "function") return api.icon("check", 22);
  return create("span", "ce-ui-checkin-card__fallback", "QA");
}

function ensureMissionEntry() {
  const grid = q(".ce-v4-mission__grid");
  if (!grid || q("[data-ce-ui-checkin]", grid)) return;
  const button = create("button", "ce-v4-mission-card ce-ui-checkin-card");
  button.type = "button";
  button.dataset.ceUiCheckin = "true";
  button.dataset.search = "ошибка баг чек ин интерфейс диагностика qa bug report";
  button.append(create("span", "ce-v4-mission-card__number", "QA"));
  const copy = create("span");
  const tile = create("span", "ce-v4-mission-card__icon");
  tile.append(missionIcon());
  copy.append(
    tile,
    create("strong", "", "Чек‑ин ошибок"),
    create("small", "", "Снять build, маршрут, геометрию и воспроизведение"),
  );
  button.append(copy, window.ContentEngineDesktopV4?.icon?.("right", 18) || create("span", "", "→"));
  grid.append(button);
}

function scheduleMissionEntry() {
  runtime.missionTimers.forEach((timer) => window.clearTimeout(timer));
  runtime.missionTimers.clear();
  [0, 70, 180].forEach((delay) => {
    const timer = window.setTimeout(() => {
      runtime.missionTimers.delete(timer);
      ensureMissionEntry();
    }, delay);
    runtime.missionTimers.add(timer);
  });
}

function closeMissionIfOpen() {
  q(".ce-v4-mission [data-ce-v4-close]")?.click?.();
}

function field(labelText, control, hint = "") {
  const label = create("label", "ce-ui-checkin-field");
  label.append(create("strong", "", labelText));
  if (hint) label.append(create("small", "", hint));
  label.append(control);
  return label;
}

function makeInput(type = "text") {
  const input = create("input");
  input.type = type;
  return input;
}

function makeTextarea(rows = 4) {
  const area = create("textarea");
  area.rows = rows;
  return area;
}

function severityOptions(select) {
  [
    ["P0", "P0 · блокирует работу / чёрный экран"],
    ["P1", "P1 · ломает основной сценарий"],
    ["P2", "P2 · мешает, но есть обход"],
    ["P3", "P3 · косметика / улучшение"],
  ].forEach(([value, label]) => {
    const option = create("option", "", label);
    option.value = value;
    select.append(option);
  });
}

function issueCard(issue) {
  const card = create("article", "ce-ui-checkin-issue");
  card.dataset.severity = issue.severity;
  const head = create("header");
  head.append(create("b", "", issue.severity), create("strong", "", issue.title));
  card.append(head, create("p", "", issue.detail));
  if (issue.examples.length) card.append(create("code", "", issue.examples.join(" · ")));
  return card;
}

function statusMessage(dialog, message, tone = "neutral") {
  const status = q("[data-ce-ui-checkin-status]", dialog);
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
}

function formDraft(dialog) {
  return {
    severity: q('[name="severity"]', dialog)?.value || "P3",
    summary: q('[name="summary"]', dialog)?.value || "",
    steps: q('[name="steps"]', dialog)?.value || "",
    expected: q('[name="expected"]', dialog)?.value || "",
    actual: q('[name="actual"]', dialog)?.value || "",
  };
}

function reportObject(dialog) {
  const draft = formDraft(dialog);
  return {
    schema_version: "contentengine_ui_bug_report.v1",
    severity: draft.severity,
    summary: compact(draft.summary, 240),
    reproduction_steps: String(draft.steps || "").trim().slice(0, 5_000),
    expected: String(draft.expected || "").trim().slice(0, 3_000),
    actual: String(draft.actual || "").trim().slice(0, 3_000),
    screenshot: runtime.screenshot
      ? {
          type: runtime.screenshot.type,
          size_bytes: runtime.screenshot.size,
          width: runtime.screenshot.width,
          height: runtime.screenshot.height,
        }
      : null,
    diagnostics: runtime.diagnostics || diagnose(),
  };
}

function markdownReport(report) {
  const diagnostics = report.diagnostics;
  const issues = diagnostics.issues.length
    ? diagnostics.issues.map((issue) => `- **${issue.severity} · ${issue.code}:** ${issue.detail}`).join("\n")
    : "- Автоматические UI-аномалии не найдены; требуется ручное воспроизведение.";
  const errors = diagnostics.runtime_errors.length
    ? diagnostics.runtime_errors.map((item) => `- ${item.kind}: ${item.message}`).join("\n")
    : "- Нет захваченных runtime errors.";
  return [
    "# ContentEngine UI Bug Check-In",
    "",
    `**Severity:** ${report.severity}`,
    `**Summary:** ${report.summary || "не заполнено"}`,
    `**Build:** ${diagnostics.build}`,
    `**Route:** \`${diagnostics.route}\``,
    `**Browser:** ${diagnostics.browser.browser} · ${diagnostics.browser.platform}`,
    `**Viewport:** ${diagnostics.viewport.width}×${diagnostics.viewport.height} · DPR ${diagnostics.viewport.device_pixel_ratio}`,
    "",
    "## Как воспроизвести",
    report.reproduction_steps || "Не заполнено",
    "",
    "## Ожидалось",
    report.expected || "Не заполнено",
    "",
    "## Получилось",
    report.actual || "Не заполнено",
    "",
    "## Автоматическая диагностика",
    issues,
    "",
    "## Runtime errors",
    errors,
    "",
    "## Screenshot",
    report.screenshot
      ? `${report.screenshot.type}, ${report.screenshot.width || "?"}×${report.screenshot.height || "?"}, ${report.screenshot.size_bytes} bytes`
      : "Не приложен.",
  ].join("\n");
}

async function copyReport(dialog) {
  const report = reportObject(dialog);
  const text = markdownReport(report);
  try {
    await navigator.clipboard.writeText(text);
    statusMessage(dialog, "Отчёт скопирован. Добавьте скриншот к задаче отдельно.", "success");
  } catch {
    const fallback = create("textarea");
    fallback.value = text;
    fallback.setAttribute("aria-hidden", "true");
    fallback.style.position = "fixed";
    fallback.style.opacity = "0";
    document.body.append(fallback);
    fallback.select();
    const copied = document.execCommand?.("copy") === true;
    fallback.remove();
    statusMessage(dialog, copied ? "Отчёт скопирован." : "Не удалось скопировать — выгрузите JSON.", copied ? "success" : "warning");
  }
}

function downloadReport(dialog) {
  const report = reportObject(dialog);
  const blob = new Blob([`${JSON.stringify(report, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = create("a");
  anchor.href = url;
  anchor.download = `contentengine-ui-bug-${report.severity}-${Date.now()}.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
  statusMessage(dialog, "Диагностика выгружена в JSON.", "success");
}

function clearScreenshot() {
  if (runtime.screenshotUrl) URL.revokeObjectURL(runtime.screenshotUrl);
  runtime.screenshotUrl = "";
  runtime.screenshot = null;
}

function readScreenshot(file, preview, dialog) {
  clearScreenshot();
  preview.replaceChildren();
  if (!(file instanceof File)) return;
  if (!file.type.startsWith("image/") || file.size > 12_000_000) {
    statusMessage(dialog, "Скриншот должен быть изображением до 12 МБ.", "warning");
    return;
  }
  const url = URL.createObjectURL(file);
  runtime.screenshotUrl = url;
  const image = create("img");
  image.alt = "Локальный предпросмотр скриншота";
  image.addEventListener("load", () => {
    runtime.screenshot = {
      type: file.type,
      size: file.size,
      width: image.naturalWidth,
      height: image.naturalHeight,
    };
  }, { once: true });
  image.src = url;
  preview.append(image, create("small", "", "Файл не отправляется автоматически; он используется только для локального предпросмотра."));
}

function renderDiagnostics(dialog) {
  const host = q("[data-ce-ui-checkin-diagnostics]", dialog);
  if (!host) return;
  host.replaceChildren();
  const value = runtime.diagnostics || diagnose();
  const summary = create("header", "ce-ui-checkin-diagnostics__summary");
  summary.append(
    create("strong", "", value.issues.length ? `${value.issues.length} сигналов` : "Автоматических аномалий нет"),
    create("small", "", `${value.build} · ${value.route} · ${value.browser.browser} · ${value.viewport.width}×${value.viewport.height}`),
  );
  host.append(summary);
  if (value.issues.length) value.issues.forEach((issue) => host.append(issueCard(issue)));
  else host.append(create("p", "ce-ui-checkin-empty", "Опишите ручной сценарий: автоматическая геометрическая проверка не видит смысловой ошибки сама."));
}

function rerunDiagnostics(dialog) {
  runtime.diagnostics = diagnose();
  const select = q('[name="severity"]', dialog);
  if (select && !q('[name="summary"]', dialog)?.value) select.value = runtime.diagnostics.suggested_severity;
  renderDiagnostics(dialog);
  statusMessage(dialog, "Диагностика обновлена на текущем экране.", "success");
}

function closeCheckin() {
  const overlay = runtime.overlay;
  if (!overlay) return;
  writeDraft(formDraft(overlay));
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    runtime.overlay = null;
    document.body.classList.remove("ce-ui-checkin-open");
    clearScreenshot();
    if (runtime.previousFocus instanceof HTMLElement) runtime.previousFocus.focus({ preventScroll: true });
    runtime.previousFocus = null;
  };
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) finish();
  else window.setTimeout(finish, 170);
}

function openCheckin() {
  if (runtime.overlay) return;
  closeMissionIfOpen();
  runtime.previousFocus = document.activeElement;
  runtime.diagnostics = diagnose();
  const draft = readDraft();

  const backdrop = create("div", "ce-ui-checkin-backdrop");
  const dialog = create("section", "ce-ui-checkin");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", "Чек-ин ошибки интерфейса");

  const header = create("header", "ce-ui-checkin__header");
  const title = create("div", "ce-ui-checkin__title");
  title.append(
    create("small", "", "UI BUG CHECK‑IN"),
    create("h1", "", "Зафиксировать ошибку без гадания"),
    create("p", "", "Build, маршрут, браузер и геометрия уже сняты. Добавьте только человеческое воспроизведение."),
  );
  const close = create("button", "ce-ui-checkin__close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Закрыть чек-ин");
  header.append(title, close);

  const body = create("div", "ce-ui-checkin__body");
  const form = create("form", "ce-ui-checkin-form");
  form.addEventListener("submit", (event) => event.preventDefault());

  const severity = create("select");
  severity.name = "severity";
  severityOptions(severity);
  severity.value = draft.severity || runtime.diagnostics.suggested_severity;

  const summary = makeInput();
  summary.name = "summary";
  summary.maxLength = 240;
  summary.placeholder = "Например: в Создании прыгает локальное меню при выборе этапа";
  summary.value = draft.summary || "";

  const steps = makeTextarea(5);
  steps.name = "steps";
  steps.maxLength = 5_000;
  steps.placeholder = "1. Открыть…\n2. Нажать…\n3. Получить…";
  steps.value = draft.steps || "";

  const expected = makeTextarea(3);
  expected.name = "expected";
  expected.maxLength = 3_000;
  expected.placeholder = "Как должен вести себя один рабочий стол";
  expected.value = draft.expected || "";

  const actual = makeTextarea(3);
  actual.name = "actual";
  actual.maxLength = 3_000;
  actual.placeholder = "Что произошло фактически";
  actual.value = draft.actual || "";

  const screenshot = makeInput("file");
  screenshot.accept = "image/png,image/jpeg,image/webp";
  const preview = create("div", "ce-ui-checkin-preview");
  screenshot.addEventListener("change", () => readScreenshot(screenshot.files?.[0], preview, dialog));

  form.append(
    field("Приоритет", severity, "P0 — работать невозможно; P1 — сломан основной сценарий."),
    field("Коротко", summary),
    field("Как воспроизвести", steps),
    field("Ожидалось", expected),
    field("Получилось", actual),
    field("Скриншот", screenshot, "До 12 МБ. Файл остаётся локальным, пока вы сами его не приложите."),
    preview,
  );

  const diagnostics = create("aside", "ce-ui-checkin-diagnostics");
  diagnostics.dataset.ceUiCheckinDiagnostics = "true";
  body.append(form, diagnostics);

  const footer = create("footer", "ce-ui-checkin__footer");
  const status = create("span", "ce-ui-checkin__status", "Ничего не отправляется автоматически.");
  status.dataset.ceUiCheckinStatus = "true";
  const actions = create("div", "ce-ui-checkin__actions");
  const rerun = create("button", "", "Проверить снова");
  rerun.type = "button";
  rerun.dataset.action = "rerun";
  const copy = create("button", "is-primary", "Скопировать отчёт");
  copy.type = "button";
  copy.dataset.action = "copy";
  const download = create("button", "", "Скачать JSON");
  download.type = "button";
  download.dataset.action = "download";
  const reset = create("button", "is-quiet", "Очистить черновик");
  reset.type = "button";
  reset.dataset.action = "reset";
  actions.append(rerun, copy, download, reset);
  footer.append(status, actions);

  dialog.append(header, body, footer);
  backdrop.append(dialog);
  document.body.append(backdrop);
  runtime.overlay = backdrop;
  document.body.classList.add("ce-ui-checkin-open");
  renderDiagnostics(dialog);

  dialog.addEventListener("input", () => writeDraft(formDraft(dialog)));
  dialog.addEventListener("change", () => writeDraft(formDraft(dialog)));
  dialog.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest(".ce-ui-checkin__close")) closeCheckin();
    const action = target?.closest("[data-action]")?.dataset.action;
    if (action === "rerun") rerunDiagnostics(dialog);
    if (action === "copy") void copyReport(dialog);
    if (action === "download") downloadReport(dialog);
    if (action === "reset") {
      clearDraft();
      q('[name="summary"]', dialog).value = "";
      q('[name="steps"]', dialog).value = "";
      q('[name="expected"]', dialog).value = "";
      q('[name="actual"]', dialog).value = "";
      q('[name="severity"]', dialog).value = runtime.diagnostics.suggested_severity;
      statusMessage(dialog, "Черновик очищен.", "success");
    }
  });
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeCheckin(); });
  backdrop.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); closeCheckin(); }
  });
  window.setTimeout(() => summary.focus({ preventScroll: true }), 0);
}

function handleDocumentClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("[data-ce-v4-mission]")) scheduleMissionEntry();
  if (target?.closest("[data-ce-ui-checkin]")) {
    event.preventDefault();
    event.stopPropagation();
    openCheckin();
  }
}

function handleKeydown(event) {
  if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLocaleLowerCase("en-US") === "b") {
    if (event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable='true']")) return;
    event.preventDefault();
    openCheckin();
  }
}

window.addEventListener("error", captureRuntimeError, true);
window.addEventListener("unhandledrejection", captureRuntimeError);
document.addEventListener("click", handleDocumentClick, true);
document.addEventListener("keydown", handleKeydown, true);
window.addEventListener("contentengine:v4-route-ready", () => {
  if (runtime.overlay) rerunDiagnostics(q(".ce-ui-checkin", runtime.overlay));
});
window.addEventListener("pageshow", scheduleMissionEntry, { passive: true });

window.ContentEngineUiBugCheckin = Object.freeze({
  build: BUILD,
  open: openCheckin,
  close: closeCheckin,
  diagnose,
  report: () => runtime.overlay ? reportObject(q(".ce-ui-checkin", runtime.overlay)) : { diagnostics: diagnose() },
});
