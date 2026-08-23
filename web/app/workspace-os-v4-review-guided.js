/* ContentEngine Desktop v4 · guided completed-review result. */

const REVIEW_ROUTE = "/workspace/review";
const STEP_COUNT = 4;
const STEP_META = Object.freeze([
  Object.freeze({ label: "Итог", title: "Поймите результат", copy: "Сначала — только общий балл, статус и вывод проверки." }),
  Object.freeze({ label: "Материал", title: "Сверьте материал", copy: "Посмотрите, из чего сложился итог, и проверьте сильные стороны." }),
  Object.freeze({ label: "Риски", title: "Разберите риски", copy: "Замечания собраны по важности. Откройте только нужную группу." }),
  Object.freeze({ label: "Решение", title: "Примите решение", copy: "Проверьте точный файл и сохраните одно финальное решение." }),
]);

const SEVERITY_META = Object.freeze({
  blocker: Object.freeze({ label: "Блокеры", tone: "danger" }),
  high: Object.freeze({ label: "Высокий риск", tone: "danger" }),
  medium: Object.freeze({ label: "Средний риск", tone: "warning" }),
  low: Object.freeze({ label: "Низкий риск", tone: "neutral" }),
  info: Object.freeze({ label: "Информация", tone: "neutral" }),
  other: Object.freeze({ label: "Прочее", tone: "neutral" }),
});

const SEVERITY_ORDER = Object.freeze(["blocker", "high", "medium", "low", "info", "other"]);
const PRIMARY_ACTION_SELECTOR = '[data-primary-action="true"]';
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const NARROW_REVIEW_GUIDE = window.matchMedia("(max-width: 760px)");
const runtime = {
  steps: new Map(),
  boundResults: new WeakSet(),
  boundRiskGroups: new WeakSet(),
  boundSummaryPosters: new WeakSet(),
};

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

function currentRoute() {
  const apiRoute = window.ContentEngineDesktopV4?.route?.();
  if (apiRoute) return apiRoute;
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function resultId(result) {
  return String(result?.dataset?.reviewResultId || "selected-result");
}

function stableToken(value) {
  let hash = 2166136261;
  for (const character of String(value || "")) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function sessionKey(result, suffix = "step") {
  return `contentengine.desktop-v4.review-result.${resultId(result)}.${suffix}`;
}

function readSession(key) {
  try { return window.sessionStorage.getItem(key); }
  catch { return null; }
}

function writeSession(key, value) {
  try { window.sessionStorage.setItem(key, String(value)); }
  catch { /* Session storage can be unavailable in strict browser modes. */ }
}

function normalizeStep(value) {
  const step = Number(value);
  return Number.isInteger(step) && step >= 1 && step <= STEP_COUNT ? step : 1;
}

function rememberedStep(result) {
  const id = resultId(result);
  return normalizeStep(
    result.dataset.ceV4ReviewResultStep
      || runtime.steps.get(id)
      || readSession(sessionKey(result)),
  );
}

function severityOf(finding) {
  return SEVERITY_ORDER.find((severity) => finding.classList.contains(`is-${severity}`)) || "other";
}

function rememberOpenRiskGroup(result, groups) {
  const open = q("details[open]", groups);
  writeSession(sessionKey(result, "risk-group"), open?.dataset.ceV4ReviewSeverity || "none");
}

function bindRiskGroups(result, list) {
  if (runtime.boundRiskGroups.has(list)) return;
  runtime.boundRiskGroups.add(list);
  list.addEventListener("toggle", (event) => {
    const opened = event.target instanceof HTMLDetailsElement ? event.target : null;
    if (opened?.open) {
      qa(":scope > details[open]", list).forEach((details) => {
        if (details !== opened) details.open = false;
      });
    }
    window.queueMicrotask(() => rememberOpenRiskGroup(result, list));
  }, true);
}

function groupFindings(result, findings) {
  const list = q(".content-review-finding-list", findings);
  if (!list) return;
  if (list.dataset.ceV4ReviewRiskGroups === "true") {
    bindRiskGroups(result, list);
    return;
  }
  const cards = qa(":scope > .content-review-finding", list);
  if (!cards.length) return;

  const groups = new Map();
  cards.forEach((card) => {
    const severity = severityOf(card);
    if (!groups.has(severity)) groups.set(severity, []);
    groups.get(severity).push(card);
  });

  list.dataset.ceV4ReviewRiskGroups = "true";
  list.classList.add("ce-v4-review-risk-groups");
  const remembered = readSession(sessionKey(result, "risk-group"));
  let firstGroup = "";

  SEVERITY_ORDER.forEach((severity) => {
    const items = groups.get(severity) || [];
    if (!items.length) return;
    if (!firstGroup) firstGroup = severity;
    const meta = SEVERITY_META[severity];
    const details = create("details", `ce-v4-review-risk-group is-${meta.tone}`);
    details.dataset.ceV4ReviewSeverity = severity;

    const summary = create("summary");
    const summaryCopy = create("span", "ce-v4-review-risk-group__label");
    summaryCopy.append(create("strong", "", meta.label), create("small", "", "Открыть замечания"));
    summary.append(
      create("span", "ce-v4-review-risk-group__count", String(items.length)),
      summaryCopy,
      create("span", "ce-v4-review-risk-group__chevron", "⌄"),
    );

    const body = create("div", "ce-v4-review-risk-group__body");
    items.forEach((item) => body.append(item));
    details.append(summary, body);
    list.append(details);
  });

  const initialOpen = remembered === null ? firstGroup : remembered;
  if (initialOpen && initialOpen !== "none") {
    q(`details[data-ce-v4-review-severity="${initialOpen}"]`, list)?.setAttribute("open", "");
  }

  bindRiskGroups(result, list);
}

function classifyNode(node, index, headerIndex, riskIndex, decisionIndex) {
  if (node.matches(".content-review-result__header, .content-review-score-grid")) return 1;
  if (node.matches(".content-review-readonly-preview, .content-review-breakdown, .content-review-comparison, .content-review-strengths")) return 2;
  if (node.matches(".content-review-findings, .content-review-recommendations")) return 3;
  if (node.matches(".content-review-decision-form, .content-review-decision, .content-review-ruleset")) return 4;
  if (node.matches(".content-review-message")) return index < headerIndex ? 1 : 4;
  if (decisionIndex >= 0 && index >= decisionIndex) return 4;
  if (riskIndex >= 0 && index >= riskIndex) return 3;
  return headerIndex >= 0 && index > headerIndex ? 2 : 1;
}

function panelId(result, step) {
  return `ce-v4-review-result-${stableToken(resultId(result))}-panel-${step}`;
}

function tabId(result, step) {
  return `${panelId(result, step)}-tab`;
}

function createGuide(result) {
  const guide = create("nav", "ce-v4-review-guide");
  guide.setAttribute("aria-label", "Этапы готовой проверки");
  guide.setAttribute("role", "tablist");
  guide.setAttribute("aria-orientation", "horizontal");
  STEP_META.forEach((meta, index) => {
    const step = index + 1;
    const button = create("button", "ce-v4-review-guide__step");
    button.type = "button";
    button.id = tabId(result, step);
    button.dataset.ceV4ReviewStepTarget = String(step);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", panelId(result, step));
    button.setAttribute("aria-selected", "false");
    button.tabIndex = -1;
    button.append(create("span", "", String(step)), create("strong", "", meta.label));
    guide.append(button);
  });
  return guide;
}

function createPanel(result, step) {
  const meta = STEP_META[step - 1];
  const panel = create("section", "ce-v4-review-panel");
  panel.id = panelId(result, step);
  panel.dataset.ceV4ReviewResultPanel = String(step);
  panel.dataset.reviewGuidedPanel = String(step);
  panel.setAttribute("role", "tabpanel");

  const intro = create("header", "ce-v4-review-panel__intro");
  const eyebrow = create("p", "", `Шаг ${step} из ${STEP_COUNT}`);
  const title = create("h3", "", meta.title);
  title.id = `${panel.id}-title`;
  title.tabIndex = -1;
  intro.append(eyebrow, title, create("span", "", meta.copy));
  panel.setAttribute("aria-labelledby", tabId(result, step));
  panel.append(intro);
  return panel;
}

function appendPanelActions(panel, step) {
  const actions = create("footer", "ce-v4-review-panel__actions");
  if (step > 1) {
    const previous = create("button", "btn btn-secondary ce-v4-review-previous", "← Назад");
    previous.type = "button";
    previous.dataset.ceV4ReviewStepTarget = String(step - 1);
    actions.append(previous);
  }
  if (step < STEP_COUNT) {
    const nextMeta = STEP_META[step];
    const next = create("button", "btn ce-v4-review-next", `Дальше: ${nextMeta.label.toLocaleLowerCase("ru-RU")} →`);
    next.type = "button";
    next.dataset.ceV4ReviewStepTarget = String(step + 1);
    actions.append(next);
  } else {
    const hint = create("p", "ce-v4-review-panel__decision-hint", "Сохраните решение существующей кнопкой формы. Если решение уже принято, здесь останется его неизменяемая запись.");
    actions.prepend(hint);
  }
  panel.append(actions);
}

function scaffoldResult(result) {
  const original = [...result.children];
  const headerIndex = original.findIndex((node) => node.matches?.(".content-review-result__header"));
  const riskIndex = original.findIndex((node) => node.matches?.(".content-review-findings, .content-review-recommendations"));
  const decisionIndex = original.findIndex((node) => node.matches?.(".content-review-decision-form, .content-review-decision, .content-review-ruleset"));
  const guide = createGuide(result);
  const panels = Array.from({ length: STEP_COUNT }, (_, index) => createPanel(result, index + 1));

  original.forEach((node, index) => {
    const step = classifyNode(node, index, headerIndex, riskIndex, decisionIndex);
    panels[step - 1].append(node);
  });

  panels.forEach((panel, index) => appendPanelActions(panel, index + 1));
  result.append(guide, ...panels);
  result.dataset.ceV4ReviewGuided = "true";
  result.dataset.ceV4ReviewResultSession = `review-${stableToken(resultId(result))}`;
}

function absorbLooseNodes(result) {
  const guide = q(":scope > .ce-v4-review-guide", result);
  const panels = qa(":scope > .ce-v4-review-panel", result);
  if (!guide || panels.length !== STEP_COUNT) return false;
  const loose = [...result.children].filter((node) => node !== guide && !panels.includes(node));
  if (!loose.length) return true;
  const headerIndex = loose.findIndex((node) => node.matches?.(".content-review-result__header"));
  const riskIndex = loose.findIndex((node) => node.matches?.(".content-review-findings, .content-review-recommendations"));
  const decisionIndex = loose.findIndex((node) => node.matches?.(".content-review-decision-form, .content-review-decision, .content-review-ruleset"));
  loose.forEach((node, index) => {
    const target = panels[classifyNode(node, index, headerIndex, riskIndex, decisionIndex) - 1];
    const actions = q(":scope > .ce-v4-review-panel__actions", target);
    target.insertBefore(node, actions || null);
  });
  return true;
}

function animatePanel(panel) {
  if (REDUCED_MOTION.matches) return;
  panel.classList.remove("is-entering");
  window.requestAnimationFrame(() => panel.classList.add("is-entering"));
  panel.addEventListener("animationend", () => panel.classList.remove("is-entering"), { once: true });
}

function enforceOnePrimaryAction(panel, step) {
  const actions = qa(":scope .btn", panel);
  const primary = step < STEP_COUNT
    ? q(":scope > .ce-v4-review-panel__actions .ce-v4-review-next", panel)
    : q(".content-review-decision-actions > .btn:not(.btn-secondary):not(.btn-ghost)", panel);

  actions.forEach((action) => {
    const selected = action === primary;
    if (selected) action.setAttribute("data-primary-action", "true");
    else action.removeAttribute("data-primary-action");
    action.toggleAttribute("data-ce-v4-review-secondary", !selected && !action.classList.contains("btn-secondary") && !action.classList.contains("btn-ghost"));
  });

  const primaryActions = qa(PRIMARY_ACTION_SELECTOR, panel); // Contract: primaryActions.length must never exceed one.
  primaryActions.slice(1).forEach((action) => action.removeAttribute("data-primary-action"));
}

function alignActiveTab(tab) {
  if (!tab || !NARROW_REVIEW_GUIDE.matches) return;
  window.requestAnimationFrame(() => {
    tab.scrollIntoView?.({
      behavior: REDUCED_MOTION.matches ? "auto" : "smooth",
      block: "nearest",
      inline: "center",
    });
  });
}

function showStep(result, requestedStep, { focus = false, focusTab = false } = {}) {
  const step = normalizeStep(requestedStep);
  const panels = qa(":scope > .ce-v4-review-panel", result);
  const tabs = qa(":scope > .ce-v4-review-guide > [role='tab']", result);
  if (panels.length !== STEP_COUNT || tabs.length !== STEP_COUNT) return;
  const focusedPanel = panels.find((panel) => panel.contains(document.activeElement));
  const focusedTab = tabs.find((tab) => tab === document.activeElement);

  panels.forEach((panel, index) => {
    const active = index + 1 === step;
    enforceOnePrimaryAction(panel, index + 1);
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", active ? "false" : "true");
    panel.classList.toggle("is-current", active);
    if (active) {
      panel.removeAttribute("inert");
      if ("inert" in panel) panel.inert = false;
    } else {
      panel.setAttribute("inert", "");
      if ("inert" in panel) panel.inert = true;
    }
  });

  tabs.forEach((tab, index) => {
    const active = index + 1 === step;
    tab.setAttribute("aria-selected", active ? "true" : "false");
    if (active) tab.setAttribute("aria-current", "step");
    else tab.removeAttribute("aria-current");
    tab.tabIndex = active ? 0 : -1;
    tab.classList.toggle("is-current", active);
  });

  const id = resultId(result);
  result.dataset.ceV4ReviewResultStep = String(step);
  result.dataset.reviewGuidedStep = String(step);
  runtime.steps.set(id, step);
  writeSession(sessionKey(result), step);

  const activePanel = panels[step - 1];
  const activeTab = tabs[step - 1];
  alignActiveTab(activeTab);
  if (focusTab
      || (focusedTab && focusedTab !== activeTab)
      || (focusedPanel && focusedPanel !== activePanel && !focus)) {
    activeTab.focus?.({ preventScroll: true });
  }
  if (!focus) return;
  animatePanel(activePanel);
  const heading = q(":scope > .ce-v4-review-panel__intro h3", activePanel);
  heading?.focus?.({ preventScroll: true });
  activePanel.scrollIntoView?.({ behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block: "start" });
}

function handleGuideKeydown(result, event) {
  if (event.altKey || event.ctrlKey || event.metaKey) return;
  const tab = event.target instanceof Element
    ? event.target.closest(".ce-v4-review-guide > [role='tab'][data-ce-v4-review-step-target]")
    : null;
  const guide = tab?.parentElement;
  if (!tab || !guide || guide.parentElement !== result) return;

  const tabs = qa(":scope > [role='tab']", guide);
  const currentIndex = tabs.indexOf(tab);
  if (currentIndex < 0) return;

  let nextIndex = currentIndex;
  if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
  else if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
  else if (event.key === "Home") nextIndex = 0;
  else if (event.key === "End") nextIndex = tabs.length - 1;
  else return;

  event.preventDefault();
  event.stopPropagation();
  showStep(result, tabs[nextIndex].dataset.ceV4ReviewStepTarget, { focusTab: true });
}

function bindResult(result) {
  if (runtime.boundResults.has(result)) return;
  runtime.boundResults.add(result);
  result.dataset.ceV4ReviewGuidedBound = "true";
  result.addEventListener("click", (event) => {
    const control = event.target instanceof Element
      ? event.target.closest("[data-ce-v4-review-step-target]")
      : null;
    if (!control || !result.contains(control)) return;
    event.preventDefault();
    const isTab = control.getAttribute("role") === "tab";
    showStep(result, control.dataset.ceV4ReviewStepTarget, {
      focus: !isTab,
      focusTab: isTab,
    });
  });
  result.addEventListener("keydown", (event) => handleGuideKeydown(result, event));
}

function updateSummaryPosterState(poster, state, label) {
  poster.dataset.summaryPosterState = state;
  const stateLabel = q("[data-content-review-summary-poster-label]", poster);
  if (stateLabel && label) stateLabel.textContent = label;
  const canvas = q(".content-review-summary-poster__canvas", poster);
  if (state !== "ready" && canvas instanceof HTMLCanvasElement) {
    canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  }
}

function paintSummaryPoster(poster, media) {
  const canvas = q(".content-review-summary-poster__canvas", poster);
  if (!(canvas instanceof HTMLCanvasElement)) return false;
  const sourceWidth = media instanceof HTMLVideoElement
    ? Number(media.videoWidth)
    : media instanceof HTMLImageElement
      ? Number(media.naturalWidth)
      : 0;
  const sourceHeight = media instanceof HTMLVideoElement
    ? Number(media.videoHeight)
    : media instanceof HTMLImageElement
      ? Number(media.naturalHeight)
      : 0;
  if (!(sourceWidth > 0 && sourceHeight > 0)) return false;

  const context = canvas.getContext("2d", { alpha: false });
  if (!context) return false;
  const targetWidth = 640;
  const targetHeight = 360;
  if (canvas.width !== targetWidth) canvas.width = targetWidth;
  if (canvas.height !== targetHeight) canvas.height = targetHeight;
  const scale = Math.max(targetWidth / sourceWidth, targetHeight / sourceHeight);
  const drawWidth = sourceWidth * scale;
  const drawHeight = sourceHeight * scale;
  const offsetX = (targetWidth - drawWidth) / 2;
  const offsetY = (targetHeight - drawHeight) / 2;
  try {
    context.fillStyle = "#07111f";
    context.fillRect(0, 0, targetWidth, targetHeight);
    context.drawImage(media, offsetX, offsetY, drawWidth, drawHeight);
  } catch {
    updateSummaryPosterState(poster, "unavailable", "Кадр защищённого файла откроется на шаге «Решение»");
    return false;
  }
  updateSummaryPosterState(
    poster,
    "ready",
    media instanceof HTMLVideoElement
      ? "Ключевой кадр · точный player ниже по маршруту"
      : "Миниатюра · точный файл ниже по маршруту",
  );
  return true;
}

function bindSummaryPoster(result) {
  const poster = q("[data-content-review-summary-poster]", result);
  if (!poster || runtime.boundSummaryPosters.has(poster)) return;
  runtime.boundSummaryPosters.add(poster);
  poster.dataset.summaryPosterBound = "true";

  const media = q("[data-content-review-exact-media]", result)
    || q(".content-review-readonly-preview .content-review-decision-preview__media", result);
  if (!(media instanceof HTMLVideoElement) && !(media instanceof HTMLImageElement)) {
    updateSummaryPosterState(poster, "unavailable", "Точный файл откроется после обновления проверки");
    return;
  }

  const onReady = () => paintSummaryPoster(poster, media);
  const onLoading = () => updateSummaryPosterState(
    poster,
    "loading",
    media instanceof HTMLVideoElement
      ? "Готовим ключевой кадр из точного player"
      : "Готовим миниатюру точного файла",
  );
  const onError = () => updateSummaryPosterState(
    poster,
    "unavailable",
    "Защищённый файл обновите перед решением",
  );

  media.addEventListener("error", onError);
  if (media instanceof HTMLVideoElement) {
    media.addEventListener("loadstart", onLoading);
    media.addEventListener("emptied", onLoading);
    media.addEventListener("loadeddata", onReady);
    media.addEventListener("canplay", onReady);
    media.addEventListener("seeked", onReady);
    if (media.readyState >= 2) onReady();
    else onLoading();
    return;
  }

  media.addEventListener("load", onReady);
  if (media.complete && media.naturalWidth > 0) onReady();
  else onLoading();
}

function mountResult(result) {
  if (!q(":scope > .content-review-result__header", result)
      && !q(":scope > .ce-v4-review-panel .content-review-result__header", result)) return;
  if (!absorbLooseNodes(result)) scaffoldResult(result);
  qa(".content-review-findings", result).forEach((findings) => groupFindings(result, findings));
  bindSummaryPoster(result);
  bindResult(result);
  showStep(result, rememberedStep(result));
}

function mount() {
  if (currentRoute() !== REVIEW_ROUTE) return;
  qa("article.content-review-result[data-review-result-id]").forEach(mountResult);
}

window.ContentEngineDesktopV4.registerAdapter("review-guided-result", mount, { priority: 160 });
window.ContentEngineDesktopV4ReviewGuided = Object.freeze({ mount, showStep });
