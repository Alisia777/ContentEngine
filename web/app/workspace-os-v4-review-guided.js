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
const runtime = { steps: new Map(), boundResults: new WeakSet(), boundRiskGroups: new WeakSet() };

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

function createGuide(result) {
  const guide = create("nav", "ce-v4-review-guide");
  guide.setAttribute("aria-label", "Этапы готовой проверки");
  guide.setAttribute("role", "tablist");
  STEP_META.forEach((meta, index) => {
    const step = index + 1;
    const button = create("button", "ce-v4-review-guide__step");
    button.type = "button";
    button.dataset.ceV4ReviewStepTarget = String(step);
    button.setAttribute("role", "tab");
    button.setAttribute("aria-controls", panelId(result, step));
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
  panel.setAttribute("aria-labelledby", title.id);
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

function showStep(result, requestedStep, { focus = false } = {}) {
  const step = normalizeStep(requestedStep);
  const panels = qa(":scope > .ce-v4-review-panel", result);
  const tabs = qa(":scope > .ce-v4-review-guide > [role='tab']", result);
  if (panels.length !== STEP_COUNT || tabs.length !== STEP_COUNT) return;

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
    tab.setAttribute("aria-current", active ? "step" : "false");
    tab.tabIndex = active ? 0 : -1;
    tab.classList.toggle("is-current", active);
  });

  const id = resultId(result);
  result.dataset.ceV4ReviewResultStep = String(step);
  result.dataset.reviewGuidedStep = String(step);
  runtime.steps.set(id, step);
  writeSession(sessionKey(result), step);

  if (!focus) return;
  const activePanel = panels[step - 1];
  animatePanel(activePanel);
  const heading = q(":scope > .ce-v4-review-panel__intro h3", activePanel);
  heading?.focus?.({ preventScroll: true });
  activePanel.scrollIntoView?.({ behavior: REDUCED_MOTION.matches ? "auto" : "smooth", block: "start" });
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
    showStep(result, control.dataset.ceV4ReviewStepTarget, { focus: true });
  });
}

function mountResult(result) {
  if (!q(":scope > .content-review-result__header", result)
      && !q(":scope > .ce-v4-review-panel .content-review-result__header", result)) return;
  if (!absorbLooseNodes(result)) scaffoldResult(result);
  qa(".content-review-findings", result).forEach((findings) => groupFindings(result, findings));
  bindResult(result);
  showStep(result, rememberedStep(result));
}

function mount() {
  if (currentRoute() !== REVIEW_ROUTE) return;
  qa("article.content-review-result[data-review-result-id]").forEach(mountResult);
}

window.ContentEngineDesktopV4.registerAdapter("review-guided-result", mount, { priority: 160 });
window.ContentEngineDesktopV4ReviewGuided = Object.freeze({ mount, showStep });
