/*
 * ContentEngine · AI-first, human-editable research recommendations.
 *
 * Only human-approved research selections are read. The best exact-product
 * recommendation can fill an empty brief automatically; after the first human
 * edit the adapter never overwrites the field. Category-level examples remain
 * visible but require an explicit apply action.
 */

const ROUTE = "/workspace/generation";
const RPC_RECOMMENDATIONS = "creator_generation_research_recommendations";
const ROOT_ATTRIBUTE = "data-generation-research-recommendations";
const STATE_PREFIX = "contentengine.generation.research-recommendation.v1";
const MAX_BRIEF_LENGTH = 1180;

const runtime = {
  form: null,
  root: null,
  apiPromise: null,
  loading: false,
  applying: false,
  loadTimer: 0,
  key: "",
  response: null,
  activeIndex: 0,
  mountQueued: false,
};

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

function clean(value, limit = 4000) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function asList(value, limit = 10) {
  return (Array.isArray(value) ? value : [])
    .slice(0, limit)
    .map((item) => {
      if (typeof item === "string") return clean(item, 500);
      if (!item || typeof item !== "object") return "";
      return clean(
        item.label || item.title || item.name || item.text || item.summary
          || item.claim || item.pain || item.objection || JSON.stringify(item),
        500,
      );
    })
    .filter(Boolean);
}

function shotLines(value) {
  if (typeof value === "string") {
    return value.split(/\r?\n/gu).map((line) => clean(line, 400)).filter(Boolean);
  }
  if (!Array.isArray(value)) return [];
  return value.slice(0, 10).map((shot) => {
    if (typeof shot === "string") return clean(shot, 500);
    const source = object(shot);
    const seconds = clean(source.seconds || source.time || source.duration, 50);
    const visual = clean(source.visual || source.shot || source.description, 500);
    const onScreen = clean(source.on_screen_text || source.text, 250);
    return [seconds && `${seconds}:`, visual, onScreen && `Текст: ${onScreen}`]
      .filter(Boolean)
      .join(" ");
  }).filter(Boolean);
}

function truncateBrief(text, limit = MAX_BRIEF_LENGTH) {
  const value = String(text || "").trim();
  if (value.length <= limit) return value;
  const sliced = value.slice(0, limit - 1);
  const boundary = Math.max(sliced.lastIndexOf("\n"), sliced.lastIndexOf(". "));
  return `${sliced.slice(0, boundary > limit * 0.72 ? boundary : limit - 1).trim()}…`;
}

export function formatResearchRecommendation(item, context = {}) {
  const envelope = object(item);
  const recommendation = object(envelope.recommendation || envelope);
  const productName = clean(context.productName || context.product_name, 260)
    || clean(envelope.source_product_name, 260)
    || "товар";
  const audience = asList(recommendation.target_audience, 4);
  const proof = asList(recommendation.proof_points, 6);
  const avoid = asList(recommendation.avoid_claims, 6);
  const shots = shotLines(recommendation.shot_list);
  const sections = [
    ["ТОВАР", productName],
    ["КОНЦЕПЦИЯ", clean(recommendation.title, 260)],
    ["ХУК", clean(recommendation.hook, 700)],
    ["КЛЮЧЕВОЕ СООБЩЕНИЕ", clean(recommendation.key_message, 900)],
    ["АУДИТОРИЯ", audience.join(" · ")],
    ["РЕПЛИКА / СЮЖЕТ", clean(recommendation.spoken_script, 1800)],
    ["КАДРЫ", shots.join("\n")],
    ["ВИЗУАЛ", clean(recommendation.visual_direction, 1000)],
    ["CTA", clean(recommendation.cta, 700)],
    ["ДОКАЗАТЕЛЬСТВА", proof.join(" · ")],
    ["НЕ ОБЕЩАТЬ / УЧЕСТЬ", avoid.join(" · ")],
  ].filter(([, value]) => value);
  return truncateBrief(
    sections.map(([title, value]) => `${title}:\n${value}`).join("\n\n"),
  );
}

export function shouldAutoApplyResearchRecommendation({
  brief,
  touched,
  canAutoApply,
  recommendation,
}) {
  return !String(brief || "").trim()
    && touched !== true
    && canAutoApply === true
    && Boolean(recommendation);
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function projectId() {
  return clean(routeParams().get("project_id"), 80).toLowerCase();
}

function formContext(form) {
  const read = (name) => String(form.elements?.[name]?.value || "").trim();
  return {
    projectId: projectId(),
    category: clean(read("product_category"), 40).toLowerCase(),
    productName: read("product_name"),
    sku: read("sku"),
    platform: clean(read("platform"), 40).toLowerCase(),
  };
}

function stateKey(context) {
  return [
    STATE_PREFIX,
    context.projectId || "no-project",
    context.category || "no-category",
    clean(context.sku || context.productName, 120).toLowerCase() || "no-product",
  ].join(":");
}

function readState(context) {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(stateKey(context)) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeState(context, patch) {
  try {
    const previous = readState(context);
    window.sessionStorage.setItem(stateKey(context), JSON.stringify({
      ...previous,
      ...patch,
      updatedAt: Date.now(),
    }));
  } catch {
    // Session memory is optional; the textarea itself remains authoritative.
  }
}

function payloadWithOrganization(api, payload) {
  if (typeof api?.withOrganization === "function") return api.withOrganization(payload);
  if (api?.organizationId) return { organization_id: api.organizationId, ...payload };
  return payload;
}

async function getApi() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") throw new Error("api_runtime_unavailable");
  const api = await Promise.resolve(factory());
  if (!api || typeof api.call !== "function") throw new Error("api_runtime_unavailable");
  return api;
}

function briefControl(form = runtime.form) {
  return form?.elements?.brief || form?.querySelector?.('[name="brief"]') || null;
}

function setStatus(message, tone = "neutral") {
  const status = runtime.root?.querySelector("[data-research-recommendation-status]");
  if (!status) return;
  status.textContent = message;
  status.dataset.tone = tone;
}

function selectedEnvelope() {
  const recommendations = Array.isArray(runtime.response?.recommendations)
    ? runtime.response.recommendations
    : [];
  if (!recommendations.length) return null;
  return recommendations[Math.max(0, Math.min(recommendations.length - 1, runtime.activeIndex))] || null;
}

function recommendationWhy(envelope) {
  const recommendation = object(envelope?.recommendation);
  const basis = object(recommendation.learning_basis);
  const selected = asList(basis.selected_insight_keys, 4);
  const labels = {
    category: "категория и покупатель",
    competitors: "приёмы конкурентов",
    trends: "тренды",
    brief: "коммуникационная рамка",
  };
  return selected.length
    ? `Основание: ${selected.map((key) => labels[key] || key).join(" · ")}.`
    : "Основание: выбранное человеком исследование из ИИ-центра.";
}

function applyRecommendation(envelope, { explicit = false } = {}) {
  const control = briefControl();
  if (!(control instanceof HTMLTextAreaElement || control instanceof HTMLInputElement)) return false;
  const context = formContext(runtime.form);
  const text = formatResearchRecommendation(envelope, context);
  if (!text) return false;
  runtime.applying = true;
  control.value = text;
  control.dispatchEvent(new Event("input", { bubbles: true }));
  control.dispatchEvent(new Event("change", { bubbles: true }));
  runtime.applying = false;
  control.dataset.researchRecommendationApplied = clean(envelope.selection_id, 80);
  writeState(context, {
    touched: false,
    lastAppliedText: text,
    selectionId: clean(envelope.selection_id, 80),
    explicit,
  });
  renderRecommendationPanel();
  setStatus(
    explicit
      ? "Рекомендация подставлена. Теперь можно изменить любую строку."
      : "ИИ заполнил замысел из одобренного исследования. Любую строку можно изменить.",
    "ready",
  );
  return true;
}

function markHumanEdit() {
  if (runtime.applying || !runtime.form) return;
  const control = briefControl();
  const context = formContext(runtime.form);
  writeState(context, {
    touched: true,
    lastHumanText: String(control?.value || ""),
  });
  runtime.root?.setAttribute("data-human-edited", "true");
  setStatus("Правки человека сохранены. ИИ больше не перезапишет этот текст автоматически.", "edited");
  renderRecommendationPanel();
}

function optionButton(envelope, index, total) {
  const recommendation = object(envelope.recommendation);
  const button = el("button", "generation-research-recommendations__option");
  button.type = "button";
  button.dataset.recommendationIndex = String(index);
  button.classList.toggle("is-active", index === runtime.activeIndex);
  if (index === runtime.activeIndex) button.setAttribute("aria-current", "true");
  button.append(
    el("span", "generation-research-recommendations__option-number", `${index + 1}/${total}`),
    el("strong", "", clean(recommendation.title, 180) || `Вариант ${index + 1}`),
    el("small", "", envelope.scope_match === "exact_sku"
      ? "Точный SKU"
      : envelope.scope_match === "exact_product"
        ? "Точный товар"
        : "Обучение категории"),
  );
  return button;
}

function renderRecommendationPanel() {
  const root = runtime.root;
  if (!root) return;
  const options = root.querySelector("[data-research-recommendation-options]");
  const preview = root.querySelector("[data-research-recommendation-preview]");
  const actions = root.querySelector("[data-research-recommendation-actions]");
  if (!options || !preview || !actions) return;
  options.replaceChildren();
  preview.replaceChildren();
  actions.replaceChildren();

  const recommendations = Array.isArray(runtime.response?.recommendations)
    ? runtime.response.recommendations
    : [];
  if (!recommendations.length) {
    preview.append(
      el("strong", "", "Пока нет одобренных рекомендаций"),
      el("p", "", "Завершите исследование ролика и выберите полезные выводы в ИИ-центре. После этого здесь появится готовый замысел."),
    );
    const research = el("a", "btn btn-secondary btn-small", "Открыть Исследования");
    research.href = `#/workspace/research?project_id=${encodeURIComponent(projectId())}`;
    const ai = el("a", "btn btn-secondary btn-small", "Открыть ИИ-центр");
    ai.href = "#/workspace/ai";
    actions.append(research, ai);
    return;
  }

  recommendations.forEach((item, index) => options.append(optionButton(item, index, recommendations.length)));
  const envelope = selectedEnvelope();
  const recommendation = object(envelope?.recommendation);
  const previewTitle = el("div", "generation-research-recommendations__preview-title");
  previewTitle.append(
    el("strong", "", clean(recommendation.title, 260) || "Рекомендация"),
    el("span", "generation-research-recommendations__scope", envelope?.can_auto_apply ? "можно автозаполнить" : "нужна адаптация к товару"),
  );
  const hook = clean(recommendation.hook, 700);
  const script = clean(recommendation.spoken_script, 1200);
  preview.append(previewTitle);
  if (hook) preview.append(el("p", "", `Хук: ${hook}`));
  if (script) preview.append(el("p", "muted", `Сюжет: ${script}`));
  preview.append(el("small", "", recommendationWhy(envelope)));

  const context = formContext(runtime.form);
  const state = readState(context);
  const control = briefControl();
  const touched = state.touched === true
    || (String(control?.value || "").trim()
      && String(control?.value || "") !== String(state.lastAppliedText || ""));
  const apply = el(
    "button",
    "btn",
    touched ? "Применить этот вариант вместо моих правок" : "Применить вариант",
  );
  apply.type = "button";
  apply.dataset.applyResearchRecommendation = "true";
  const restore = el("button", "btn btn-secondary", "Вернуть рекомендацию ИИ");
  restore.type = "button";
  restore.dataset.restoreResearchRecommendation = "true";
  restore.hidden = !touched;
  const ai = el("a", "btn btn-secondary", "Изменить обучение в ИИ-центре");
  ai.href = `#/workspace/ai?category=${encodeURIComponent(context.category || "other")}`;
  actions.append(apply, restore, ai);
}

function buildRoot() {
  const root = el("section", "generation-research-recommendations");
  root.setAttribute(ROOT_ATTRIBUTE, "true");
  const header = el("header", "generation-research-recommendations__header");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "РЕКОМЕНДАЦИИ ИИ ИЗ ИССЛЕДОВАНИЙ"),
    el("h4", "", "ИИ предлагает замысел — человек остаётся редактором"),
    el("p", "muted", "Берём только выводы, которые были разобраны и выбраны в ИИ-центре. Пустой замысел заполняется автоматически только для точного товара; после вашей правки текст не перезаписывается."),
  );
  const badge = el("span", "generation-research-recommendations__badge", "AI-first · editable");
  header.append(copy, badge);
  const options = el("div", "generation-research-recommendations__options");
  options.dataset.researchRecommendationOptions = "true";
  const preview = el("div", "generation-research-recommendations__preview");
  preview.dataset.researchRecommendationPreview = "true";
  const status = el("p", "generation-research-recommendations__status", "Выберите товар — загрузим обученные рекомендации.");
  status.dataset.researchRecommendationStatus = "true";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const actions = el("div", "generation-research-recommendations__actions");
  actions.dataset.researchRecommendationActions = "true";
  root.append(header, options, preview, status, actions);
  root.addEventListener("click", handleRootClick);
  return root;
}

function ensureRoot(form) {
  let root = form.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (root instanceof HTMLElement) return root;
  root = buildRoot();
  const guidedHost = form.querySelector('[data-ce-v4-generation-content="brief"]');
  const assist = form.querySelector("#generation-brief-assist");
  const control = briefControl(form);
  if (guidedHost) guidedHost.prepend(root);
  else if (assist?.parentNode) assist.parentNode.insertBefore(root, assist);
  else if (control?.parentNode) control.parentNode.insertBefore(root, control);
  else form.prepend(root);
  return root;
}

function updateGuidedHint(form) {
  const panel = form.querySelector('[data-ce-v4-generation-panel="brief"]');
  const hint = panel?.querySelector(".ce-v4-generation-guided__panel-hint");
  if (hint) {
    hint.textContent = "ИИ предложит готовый замысел из одобренных исследований и правил ИИ-центра. Вы можете изменить любую строку.";
  }
  const actionHint = form.querySelector("[data-ce-v4-generation-action-hint]");
  if (actionHint && form.dataset.ceV4GenerationStep === "brief") {
    actionHint.textContent = "Рекомендация уже подготовлена — проверьте и поправьте её при необходимости";
  }
}

function recommendationKey(context) {
  return [context.projectId, context.category, context.sku, context.productName, context.platform]
    .map((value) => clean(value, 180).toLowerCase())
    .join("|");
}

async function loadRecommendations(form, context) {
  if (runtime.loading || routePath() !== ROUTE) return;
  const key = recommendationKey(context);
  if (!context.projectId || !context.category) {
    runtime.response = { recommendations: [] };
    renderRecommendationPanel();
    setStatus("Сначала выберите проект и категорию товара.");
    return;
  }
  runtime.loading = true;
  runtime.root.dataset.loading = "true";
  setStatus("ИИ-центр подбирает рекомендации из одобренных исследований…");
  try {
    const api = await getApi();
    const response = await api.call(
      RPC_RECOMMENDATIONS,
      payloadWithOrganization(api, {
        project_id: context.projectId,
        product_category: context.category,
        product_name: context.productName,
        sku: context.sku,
        platform: context.platform,
        limit: 3,
      }),
    );
    if (routePath() !== ROUTE || recommendationKey(formContext(form)) !== key) return;
    const source = object(response?.data || response);
    runtime.response = source;
    runtime.activeIndex = 0;
    renderRecommendationPanel();

    const first = Array.isArray(source.recommendations) ? source.recommendations[0] : null;
    const control = briefControl(form);
    const state = readState(context);
    const touched = state.touched === true
      || (String(control?.value || "").trim()
        && String(control?.value || "") !== String(state.lastAppliedText || ""));
    if (shouldAutoApplyResearchRecommendation({
      brief: control?.value,
      touched,
      canAutoApply: first?.can_auto_apply === true,
      recommendation: first,
    })) {
      applyRecommendation(first, { explicit: false });
    } else if (first) {
      setStatus(
        touched
          ? "Рекомендации обновлены, но ваши правки сохранены без изменений."
          : first.can_auto_apply
            ? "Рекомендация готова. Примените её или продолжайте со своим текстом."
            : "Есть обученные идеи категории. Выберите вариант и адаптируйте его к товару.",
        touched ? "edited" : "ready",
      );
    } else {
      setStatus("Нет одобренных рекомендаций для этого проекта и категории.");
    }
  } catch (error) {
    console.warn("Generation research recommendations unavailable", error);
    runtime.response = { recommendations: [] };
    renderRecommendationPanel();
    setStatus(
      "Рекомендации временно недоступны. Ручной замысел сохранён и запуск не блокируется.",
      "danger",
    );
  } finally {
    runtime.loading = false;
    runtime.root.dataset.loading = "false";
  }
}

function scheduleLoad() {
  window.clearTimeout(runtime.loadTimer);
  runtime.loadTimer = window.setTimeout(() => {
    if (!runtime.form?.isConnected) return;
    const context = formContext(runtime.form);
    const key = recommendationKey(context);
    if (key === runtime.key && runtime.response) return;
    runtime.key = key;
    void loadRecommendations(runtime.form, context);
  }, 180);
}

function handleRootClick(event) {
  const option = event.target.closest?.("[data-recommendation-index]");
  if (option) {
    event.preventDefault();
    runtime.activeIndex = Number(option.dataset.recommendationIndex) || 0;
    renderRecommendationPanel();
    return;
  }
  if (event.target.closest?.("[data-apply-research-recommendation]")) {
    event.preventDefault();
    applyRecommendation(selectedEnvelope(), { explicit: true });
    return;
  }
  if (event.target.closest?.("[data-restore-research-recommendation]")) {
    event.preventDefault();
    applyRecommendation(selectedEnvelope(), { explicit: true });
  }
}

function bindForm(form) {
  if (form.dataset.researchRecommendationsBound === "true") return;
  form.dataset.researchRecommendationsBound = "true";
  form.addEventListener("input", (event) => {
    if (event.target === briefControl(form)) {
      markHumanEdit();
      return;
    }
    if (["product_name", "sku"].includes(event.target?.name)) scheduleLoad();
  });
  form.addEventListener("change", (event) => {
    if (["product_category", "platform", "product_name", "sku"].includes(event.target?.name)) {
      scheduleLoad();
    }
  });
}

function mount() {
  if (routePath() !== ROUTE) {
    runtime.form = null;
    runtime.root = null;
    return;
  }
  const form = document.querySelector("#mock-batch-form");
  if (!(form instanceof HTMLFormElement)) return;
  runtime.form = form;
  runtime.root = ensureRoot(form);
  bindForm(form);
  updateGuidedHint(form);
  const context = formContext(form);
  const state = readState(context);
  const control = briefControl(form);
  if (
    String(control?.value || "").trim()
    && String(control?.value || "") !== String(state.lastAppliedText || "")
  ) {
    writeState(context, { touched: true });
  }
  scheduleLoad();
}

function scheduleMount() {
  if (runtime.mountQueued) return;
  runtime.mountQueued = true;
  window.queueMicrotask(() => {
    runtime.mountQueued = false;
    mount();
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "generation-research-recommendations",
      mount,
      { priority: 220 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", scheduleMount);
  window.addEventListener("hashchange", scheduleMount);
  window.queueMicrotask(scheduleMount);
}

export const GenerationResearchRecommendations = Object.freeze({
  mount,
  format: formatResearchRecommendation,
  shouldAutoApply: shouldAutoApplyResearchRecommendation,
});
