/*
 * ContentEngine Desktop v4 · guided generation.
 *
 * This adapter only re-composes the existing #mock-batch-form. Every original
 * control (including the real submit button) stays inside the same form, so
 * FormData, delegated business handlers, draft persistence and paid-launch
 * safeguards keep their original contract.
 */

const ROUTE = "/workspace/generation";
const SESSION_KEY = "contentengine.desktop.v4.generation-guided.v2";
const STEP_ATTRIBUTE = "data-ce-v4-generation-step";
const SESSION_ATTRIBUTE = "data-ce-v4-generation-session";

const STEPS = Object.freeze([
  {
    key: "mode",
    label: "Режим и бюджет",
    hint: "Выберите, что создать, и проверьте стоимость до любых списаний.",
  },
  {
    key: "product",
    label: "Товар",
    hint: "Укажите точный артикул, название и категорию товара.",
  },
  {
    key: "destination",
    label: "Куда и кому",
    hint: "Выберите площадку, назначение, исполнителя и формат результата.",
  },
  {
    key: "brief",
    label: "Замысел",
    hint: "Опишите один понятный сюжет. Портал добавит технические ограничения сам.",
  },
  {
    key: "media",
    label: "Исходники",
    hint: "Выберите точные фото этого товара и отметьте главное изображение.",
  },
  {
    key: "launch",
    label: "Проверка и запуск",
    hint: "Сверьте короткое резюме и только затем запустите создание.",
  },
]);

const runtime = {
  form: null,
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function element(tagName, className = "", text = "") {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function routePath() {
  const apiRoute = window.ContentEngineDesktopV4?.route?.();
  if (apiRoute) return apiRoute;
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/gu, "/").replace(/\/$/u, "") || "/";
}

function generationSessionContext(form) {
  const raw = String(window.location.hash || "#/workspace/generation").replace(/^#/, "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  const projectId = String(new URLSearchParams(query).get("project_id") || "")
    .trim().toLowerCase();
  const handoffSku = String(form?.dataset?.generationHandoffSku || "")
    .trim().toLowerCase();
  const handoffProductName = String(
    form?.dataset?.generationHandoffProductName || "",
  ).replace(/\s+/gu, " ").trim().toLowerCase();
  return `${projectId}|${handoffSku}|${handoffProductName}`;
}

function readSession(form) {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(SESSION_KEY) || "{}");
    if (
      !value
      || typeof value !== "object"
      || value.context !== generationSessionContext(form)
    ) return {};
    return value;
  } catch {
    return {};
  }
}

function writeSession(form, step, maxVisited) {
  try {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      context: generationSessionContext(form),
      step,
      maxVisited,
      updatedAt: Date.now(),
    }));
  } catch {
    // Session memory is a convenience. The guided form remains usable without it.
  }
}

function stepIndex(value) {
  if (Number.isInteger(value)) return Math.max(0, Math.min(STEPS.length - 1, value));
  const index = STEPS.findIndex((step) => step.key === String(value || ""));
  return index >= 0 ? index : 0;
}

function contains(node, selector) {
  return Boolean(node?.matches?.(selector) || node?.querySelector?.(selector));
}

function classifyNode(node, fallback = "mode") {
  if (!node) return fallback;
  if (
    node.id === "generation-submit"
    || node.id === "generation-readiness"
    || node.id === "generation-spec-card"
    || node.id === "real-generation-confirmation"
    || contains(node, "#generation-submit, #generation-readiness, #generation-spec-card, #real-generation-confirmation, [name=\"real_spend_confirmation\"]")
  ) return "launch";
  if (
    node.id === "generation-draft-status"
    || contains(node, '[name="generation_mode"], [name="duration_seconds"], [name="campaign_id"]')
    || node.matches?.("#generation-duration-field, #generation-mock-explanation, #generation-campaign-field")
  ) return "mode";
  if (
    node.id === "generation-product-identity-note"
    || contains(node, '[name="sku"], [name="product_name"], [name="product_category"]')
  ) return "product";
  if (contains(node, '[name="platform"], [name="destination_ref"], [name="assignee_id"], [name="payout_rub"], [name="count"], [name="format"]')) {
    return "destination";
  }
  if (
    node.id === "generation-brief-assist"
    || node.id === "generation-learning-status"
    || node.id === "generation-repair-status"
    || contains(node, '[name="brief"], #generation-brief-assist, #generation-learning-status, #generation-repair-status')
  ) return "brief";
  if (
    contains(node, '[name="media_id"], [name="primary_media_id"]')
    || contains(node, 'a[href*="/workspace/media"]')
  ) return "media";
  return fallback;
}

function createStepPanel(step, index) {
  const panel = element("section", "ce-v4-generation-guided__panel");
  panel.id = `ce-v4-generation-panel-${step.key}`;
  panel.dataset.ceV4GenerationPanel = step.key;
  panel.setAttribute("role", "region");
  panel.setAttribute("aria-labelledby", `${panel.id}-title`);

  const heading = element("h3", "ce-v4-generation-guided__panel-title", `${index + 1}. ${step.label}`);
  heading.id = `${panel.id}-title`;
  heading.tabIndex = -1;
  const hint = element("p", "ce-v4-generation-guided__panel-hint", step.hint);
  const error = element("p", "ce-v4-generation-guided__error");
  error.dataset.ceV4GenerationError = "";
  error.setAttribute("role", "alert");
  error.hidden = true;
  const content = element("div", "ce-v4-generation-guided__panel-content");
  content.dataset.ceV4GenerationContent = step.key;

  panel.append(heading, hint, error, content);
  return panel;
}

function createSummary() {
  const summary = element("div", "ce-v4-generation-guided__summary");
  summary.dataset.ceV4GenerationSummary = "";
  const intro = element("p", "ce-v4-generation-guided__summary-intro", "Проверьте пять строк. Если всё верно — запускайте.");
  const list = element("dl", "ce-v4-generation-guided__summary-list");
  [
    ["mode", "Результат"],
    ["product", "Товар"],
    ["destination", "Назначение"],
    ["brief", "Замысел"],
    ["media", "Исходники"],
  ].forEach(([key, label]) => {
    const row = element("div", "ce-v4-generation-guided__summary-row");
    row.append(
      element("dt", "", label),
      element("dd", "", "Не заполнено"),
    );
    row.querySelector("dd").dataset.ceV4GenerationSummaryValue = key;
    list.append(row);
  });
  const status = element("p", "ce-v4-generation-guided__launch-status");
  status.dataset.ceV4GenerationLaunchStatus = "";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  summary.append(intro, list, status);
  return summary;
}

function createShell(form) {
  const shell = element("section", "ce-v4-generation-guided");
  shell.dataset.ceV4GenerationGuidedShell = "";

  const intro = element("header", "ce-v4-generation-guided__intro");
  const introCopy = element("div", "ce-v4-generation-guided__intro-copy");
  introCopy.append(
    element("p", "ce-v4-generation-guided__eyebrow", "НОВЫЙ ЗАПУСК"),
    element("h2", "", "Один экран — одно решение"),
    element("p", "", "Заполните текущий шаг и нажмите «Далее». Остальные настройки пока не отвлекают."),
  );
  const position = element("span", "ce-v4-generation-guided__position", `Шаг 1 из ${STEPS.length}`);
  position.dataset.ceV4GenerationPosition = "";
  position.setAttribute("aria-live", "polite");
  intro.append(introCopy, position);

  const nav = element("nav", "ce-v4-generation-guided__steps");
  nav.setAttribute("aria-label", "Этапы нового запуска");
  const stepList = element("ol");
  STEPS.forEach((step, index) => {
    const item = element("li");
    const button = element("button", "ce-v4-generation-guided__step");
    button.type = "button";
    button.dataset.ceV4GenerationTarget = step.key;
    button.setAttribute("aria-controls", `ce-v4-generation-panel-${step.key}`);
    button.setAttribute("aria-label", `${index + 1}. ${step.label}`);
    button.append(
      element("span", "ce-v4-generation-guided__step-number", String(index + 1).padStart(2, "0")),
      element("strong", "", step.label),
    );
    item.append(button);
    stepList.append(item);
  });
  nav.append(stepList);

  const meter = element("div", "ce-v4-generation-guided__meter");
  meter.setAttribute("aria-hidden", "true");
  meter.append(element("span"));

  const viewport = element("div", "ce-v4-generation-guided__viewport");
  viewport.dataset.ceV4GenerationViewport = "";
  STEPS.forEach((step, index) => viewport.append(createStepPanel(step, index)));
  q('[data-ce-v4-generation-content="launch"]', viewport)?.append(createSummary());

  const footer = element("footer", "ce-v4-generation-guided__actions");
  const back = element("button", "btn btn-secondary ce-v4-generation-guided__back", "Назад");
  back.type = "button";
  back.dataset.ceV4GenerationBack = "";
  const actionHint = element("span", "ce-v4-generation-guided__action-hint", "Заполните только поля этого шага");
  actionHint.dataset.ceV4GenerationActionHint = "";
  const next = element("button", "btn ce-v4-generation-guided__next", "Далее");
  next.type = "button";
  next.dataset.ceV4GenerationNext = "";
  footer.append(back, actionHint, next);

  shell.append(intro, nav, meter, viewport, footer);
  form.prepend(shell);
  return shell;
}

function panelFor(form, key) {
  return q(`[data-ce-v4-generation-panel="${key}"]`, form);
}

function contentFor(form, key) {
  return q(`[data-ce-v4-generation-content="${key}"]`, form);
}

function organizeOriginalNodes(form, shell, originalNodes, submit) {
  let currentKey = "mode";
  originalNodes.forEach((node) => {
    if (node === shell || node === submit) return;
    currentKey = classifyNode(node, currentKey);
    (contentFor(form, currentKey) || contentFor(form, "mode"))?.append(node);
  });
  const footer = q(".ce-v4-generation-guided__actions", shell);
  if (submit && footer) {
    submit.classList.add("ce-v4-generation-guided__submit");
    footer.append(submit);
  }
}

function adoptDirectChildren(form, shell) {
  const loose = [...form.children].filter((node) => node !== shell);
  loose.forEach((node) => {
    if (node.id === "generation-submit") {
      const current = q("#generation-submit", shell);
      node.classList.add("ce-v4-generation-guided__submit");
      if (current && current !== node) current.replaceWith(node);
      else q(".ce-v4-generation-guided__actions", shell)?.append(node);
      return;
    }
    const key = classifyNode(node, "brief");
    (contentFor(form, key) || contentFor(form, "brief"))?.append(node);
  });
}

function panelControls(panel) {
  return qa("input, select, textarea", panel).filter((control) => {
    if (control.disabled || control.type === "hidden") return false;
    let ancestor = control;
    while (ancestor && ancestor !== panel) {
      if (ancestor.hidden) return false;
      ancestor = ancestor.parentElement;
    }
    return true;
  });
}

function modeIsReal(form) {
  return String(form.elements?.generation_mode?.value || "mock") !== "mock";
}

function firstInvalidControl(panel) {
  return panelControls(panel).find((control) => (
    typeof control.checkValidity === "function" && !control.checkValidity()
  )) || null;
}

function mediaSelectionValid(form, panel) {
  const available = qa('input[name="media_id"]:not(:disabled)', panel);
  return available.length > 0 && available.some((control) => control.checked);
}

function requiredTextControl(form, name) {
  const control = form?.elements?.[name];
  if (!(control instanceof HTMLInputElement || control instanceof HTMLTextAreaElement)) {
    return null;
  }
  return String(control.value || "").trim() ? null : control;
}

function controlLabel(control) {
  const label = control.closest("label");
  return String(
    q(":scope > span", label)?.textContent
    || control.getAttribute("aria-label")
    || control.name
    || "обязательное поле",
  ).replace(/\s*\*\s*$/u, "").trim();
}

function clearPanelError(panel) {
  const error = q("[data-ce-v4-generation-error]", panel);
  if (!error) return;
  error.hidden = true;
  error.textContent = "";
}

function showPanelError(panel, message) {
  const error = q("[data-ce-v4-generation-error]", panel);
  if (!error) return;
  error.textContent = message;
  error.hidden = false;
}

function panelValidity(form, index) {
  const step = STEPS[index];
  const panel = panelFor(form, step.key);
  if (!panel) return { valid: true, panel: null, control: null, message: "" };
  if (step.key === "product") {
    const missingProduct = requiredTextControl(form, "sku")
      || requiredTextControl(form, "product_name");
    if (missingProduct) {
      return {
        valid: false,
        panel,
        control: missingProduct,
        message: missingProduct.name === "sku"
          ? "Укажите точный артикул товара — одного названия недостаточно."
          : "Укажите точное название товара — одного артикула недостаточно.",
      };
    }
  }
  if (step.key === "brief" && modeIsReal(form)) {
    const missingBrief = requiredTextControl(form, "brief");
    if (missingBrief) {
      return {
        valid: false,
        panel,
        control: missingBrief,
        message: "Опишите замысел ролика. Пустое описание нельзя отправить в платную генерацию.",
      };
    }
  }
  const invalid = firstInvalidControl(panel);
  if (invalid) {
    return {
      valid: false,
      panel,
      control: invalid,
      message: `Заполните поле «${controlLabel(invalid)}».`,
    };
  }
  if (step.key === "media" && !mediaSelectionValid(form, panel)) {
    return {
      valid: false,
      panel,
      control: q('input[name="media_id"]:not(:disabled), a[href*="/workspace/media"]', panel),
      message: "Выберите хотя бы один точный исходник товара. Без него нельзя создать ни dry-run задачу, ни платный результат.",
    };
  }
  return { valid: true, panel, control: null, message: "" };
}

function firstInvalidStepBefore(form, requestedIndex) {
  const boundary = Math.max(0, Math.min(STEPS.length - 1, stepIndex(requestedIndex)));
  for (let index = 0; index < boundary; index += 1) {
    if (!panelValidity(form, index).valid) return index;
  }
  return -1;
}

function compact(value, limit = 92) {
  const text = String(value || "").replace(/\s+/gu, " ").trim();
  if (!text) return "Не заполнено";
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function selectLabel(control) {
  if (!(control instanceof HTMLSelectElement)) return "";
  return control.selectedOptions?.[0]?.textContent?.trim() || control.value || "";
}

function summaryValues(form) {
  const mode = form.elements?.generation_mode;
  const sku = compact(form.elements?.sku?.value, 36);
  const productName = compact(form.elements?.product_name?.value, 54);
  const platform = selectLabel(form.elements?.platform);
  const destination = compact(form.elements?.destination_ref?.value, 54);
  const brief = compact(form.elements?.brief?.value, 110);
  const mediaCount = qa('input[name="media_id"]:checked:not(:disabled)', form).length;
  return {
    mode: compact(selectLabel(mode), 90),
    product: productName === "Не заполнено" && sku === "Не заполнено"
      ? "Не заполнено"
      : [productName, sku].filter((value) => value !== "Не заполнено").join(" · "),
    destination: [platform, destination].filter((value) => value && value !== "Не заполнено").join(" · ") || "Не заполнено",
    brief,
    media: mediaCount ? `${mediaCount} ${mediaCount === 1 ? "исходник" : "исходника"}` : "Не выбраны",
  };
}

function syncSummary(form) {
  const values = summaryValues(form);
  Object.entries(values).forEach(([key, value]) => {
    const target = q(`[data-ce-v4-generation-summary-value="${key}"]`, form);
    if (target) target.textContent = value;
  });
  const submit = q("#generation-submit", form);
  const status = q("[data-ce-v4-generation-launch-status]", form);
  if (status) {
    const ready = submit && !submit.disabled && form.dataset.busy !== "true";
    const busy = form.dataset.busy === "true";
    const rawBlocker = String(submit?.dataset.launchBlocker || "").trim();
    const blocker = rawBlocker ? compact(rawBlocker, 240) : "";
    status.dataset.state = ready ? "ready" : busy ? "working" : "pending";
    status.textContent = ready
      ? modeIsReal(form)
        ? "Всё готово. Одно нажатие подготовит техническое ТЗ и отправит ровно один платный результат на создание."
        : "Готов только dry-run: он создаст задачи, но не создаст видео или другой медиафайл. Для ролика вернитесь в «Режим и бюджет» и выберите платный видеорежим."
      : busy
        ? "Портал проверяет техническое ТЗ. Не нажимайте запуск повторно."
        : blocker || "Заполните обязательное поле текущего шага.";
  }
}

function syncCompletion(form) {
  const current = stepIndex(form.dataset.ceV4GenerationStep);
  STEPS.forEach((step, index) => {
    const button = q(`[data-ce-v4-generation-target="${step.key}"]`, form);
    if (!button) return;
    const complete = index < STEPS.length - 1
      ? panelValidity(form, index).valid
      : Boolean(q("#generation-submit", form) && !q("#generation-submit", form).disabled);
    button.classList.toggle("is-complete", complete);
    if (index === current) button.classList.remove("is-complete");
  });
}

function scheduleSync(form) {
  window.queueMicrotask(() => {
    if (!form.isConnected) return;
    syncSummary(form);
    syncCompletion(form);
  });
  window.requestAnimationFrame(() => {
    if (!form.isConnected) return;
    syncSummary(form);
    syncCompletion(form);
  });
}

function setStep(form, requestedIndex, { focus = false } = {}) {
  const index = stepIndex(requestedIndex);
  const maxVisited = Math.max(
    index,
    Number(form.dataset.ceV4GenerationMaxVisited) || 0,
  );
  form.setAttribute(STEP_ATTRIBUTE, STEPS[index].key);
  form.dataset.ceV4GenerationMaxVisited = String(maxVisited);

  STEPS.forEach((step, panelIndex) => {
    const active = panelIndex === index;
    const panel = panelFor(form, step.key);
    if (panel) {
      panel.hidden = !active;
      panel.inert = !active;
      panel.setAttribute("aria-hidden", active ? "false" : "true");
    }
    const button = q(`[data-ce-v4-generation-target="${step.key}"]`, form);
    if (button) {
      button.disabled = panelIndex > maxVisited;
      if (active) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    }
  });

  const position = q("[data-ce-v4-generation-position]", form);
  if (position) position.textContent = `Шаг ${index + 1} из ${STEPS.length}`;
  const meter = q(".ce-v4-generation-guided__meter > span", form);
  if (meter) meter.style.width = `${((index + 1) / STEPS.length) * 100}%`;

  const back = q("[data-ce-v4-generation-back]", form);
  const next = q("[data-ce-v4-generation-next]", form);
  const submit = q("#generation-submit", form);
  if (back) back.hidden = index === 0;
  if (next) next.hidden = index === STEPS.length - 1;
  if (submit) {
    submit.hidden = index !== STEPS.length - 1;
    submit.setAttribute("aria-hidden", index === STEPS.length - 1 ? "false" : "true");
  }
  const actionHint = q("[data-ce-v4-generation-action-hint]", form);
  if (actionHint) {
    actionHint.textContent = index === STEPS.length - 1
      ? "Запуск доступен только после всех обязательных проверок"
      : STEPS[index].hint;
  }

  writeSession(form, STEPS[index].key, maxVisited);
  syncSummary(form);
  syncCompletion(form);

  if (focus) {
    const panel = panelFor(form, STEPS[index].key);
    panel?.scrollTo?.({ top: 0, behavior: "auto" });
    q(".ce-v4-generation-guided__panel-title", panel)?.focus({ preventScroll: true });
  }
}

function reportInvalid(form, result, index) {
  setStep(form, index, { focus: false });
  if (result.panel) showPanelError(result.panel, result.message);
  window.requestAnimationFrame(() => {
    if (!form.isConnected) return;
    if (result.control instanceof HTMLElement) {
      result.control.focus({ preventScroll: false });
      result.control.reportValidity?.();
    } else {
      q(".ce-v4-generation-guided__panel-title", result.panel)?.focus({ preventScroll: true });
    }
  });
}

function moveTo(form, requestedIndex) {
  const current = stepIndex(form.dataset.ceV4GenerationStep);
  const target = stepIndex(requestedIndex);
  if (target > current) {
    for (let index = current; index < target; index += 1) {
      const result = panelValidity(form, index);
      if (!result.valid) {
        reportInvalid(form, result, index);
        return false;
      }
      clearPanelError(result.panel);
    }
    form.dispatchEvent(new CustomEvent(
      "contentengine:generation-guided-step-committed",
      {
        bubbles: true,
        detail: {
          from: STEPS[current].key,
          to: STEPS[target].key,
        },
      },
    ));
  }
  setStep(form, target, { focus: true });
  return true;
}

function handleFormClick(event) {
  if (!(event.target instanceof Element)) return;
  const form = event.currentTarget;
  const stepButton = event.target.closest("[data-ce-v4-generation-target]");
  if (stepButton) {
    event.preventDefault();
    moveTo(form, stepIndex(stepButton.dataset.ceV4GenerationTarget));
    return;
  }
  if (event.target.closest("[data-ce-v4-generation-back]")) {
    event.preventDefault();
    moveTo(form, stepIndex(form.dataset.ceV4GenerationStep) - 1);
    return;
  }
  if (event.target.closest("[data-ce-v4-generation-next]")) {
    event.preventDefault();
    moveTo(form, stepIndex(form.dataset.ceV4GenerationStep) + 1);
  }
}

function handleFormEdit(event) {
  const form = event.currentTarget;
  const panel = event.target instanceof Element
    ? event.target.closest("[data-ce-v4-generation-panel]")
    : null;
  clearPanelError(panel);
  scheduleSync(form);
}

function bindForm(form) {
  if (form.dataset.ceV4GenerationGuidedBound === "true") return;
  form.dataset.ceV4GenerationGuidedBound = "true";
  form.addEventListener("click", handleFormClick);
  form.addEventListener("input", handleFormEdit);
  form.addEventListener("change", handleFormEdit);
}

function setupForm(form) {
  let shell = q(":scope > [data-ce-v4-generation-guided-shell]", form);
  if (!shell) {
    const originalNodes = [...form.children];
    const submit = originalNodes.find((node) => node.id === "generation-submit")
      || q("#generation-submit", form);
    shell = createShell(form);
    organizeOriginalNodes(form, shell, originalNodes, submit);
    form.dataset.ceV4GenerationGuided = "true";
    form.setAttribute(SESSION_ATTRIBUTE, SESSION_KEY);
  } else {
    adoptDirectChildren(form, shell);
  }

  bindForm(form);
  const saved = readSession(form);
  const initial = form.dataset.ceV4GenerationStep || saved.step || STEPS[0].key;
  const requestedIndex = stepIndex(initial);
  const invalidIndex = firstInvalidStepBefore(form, requestedIndex);
  const restoredIndex = invalidIndex >= 0 ? invalidIndex : requestedIndex;
  const restoredMax = Math.max(
    restoredIndex,
    Math.min(
      invalidIndex >= 0 ? invalidIndex : STEPS.length - 1,
      Number(form.dataset.ceV4GenerationMaxVisited || saved.maxVisited) || 0,
    ),
  );
  form.dataset.ceV4GenerationMaxVisited = String(restoredMax);
  setStep(form, restoredIndex);
  scheduleSync(form);
  return shell;
}

function mount() {
  if (routePath() !== ROUTE) {
    document.body.classList.remove("ce-v4-generation-guided-route");
    runtime.form = null;
    return;
  }
  const form = q("#mock-batch-form");
  if (!form) return;
  runtime.form = form;
  document.body.classList.add("ce-v4-generation-guided-route");
  setupForm(form);
}

window.ContentEngineDesktopV4.registerAdapter("generation-guided", mount, { priority: 180 });

window.ContentEngineGenerationGuidedV4 = Object.freeze({
  mount,
  steps: STEPS,
  goToStep(value) {
    if (!runtime.form?.isConnected) return false;
    return moveTo(runtime.form, stepIndex(value));
  },
});
