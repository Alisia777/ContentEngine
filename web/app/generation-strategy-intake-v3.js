import {
  GENERATION_INTAKE_STRATEGIES,
  GENERATION_INTAKE_STRATEGY_IDS,
  GENERATION_INTAKE_VERSION,
  canonicalGenerationIntakeSourceUrl,
  createGenerationIntakeDraft,
  generationIntakeInternalBrief,
  generationIntakeStrategy,
  generationIntakeStrategyForAuthority,
  validateGenerationIntakeDraft,
} from "./generation-strategy-intake-contract-v2.js?v=20260814.intake2.2";

/*
 * Three genuinely separate generation forms.
 * Compact routes only prepare immutable source/input records. They never call
 * a provider, reserve budget, or reuse the full-strategy paid submit.
 */

const ROUTE = "/workspace/generation";
const RPC_SOURCE = "contentengine_register_exact_youtube_source";
const RPC_INTAKE = "creator_save_generation_intake_v2";
const SESSION_PREFIX = "contentengine.generation.intake-v2";
const STYLE_HREF = new URL(
  "./generation-strategy-intake-v3.css?v=20260814.intake3.1",
  import.meta.url,
).href;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256 = /^[0-9a-f]{64}$/u;
const runtime = new WeakMap();
let queued = false;

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function routePath() {
  const apiRoute = window.ContentEngineDesktopV4?.route?.();
  if (apiRoute) return apiRoute;
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function params() {
  const hash = String(window.location.hash || "");
  return new URLSearchParams(hash.includes("?") ? hash.slice(hash.indexOf("?") + 1) : "");
}

function projectId() {
  const id = String(params().get("project_id") || "").trim().toLowerCase();
  return UUID.test(id) ? id : "";
}

function hashUrl(route, values = {}) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    const text = String(value ?? "").trim();
    if (text) query.set(key, text);
  });
  return `#${route}${query.size ? `?${query}` : ""}`;
}

function ensureStyle() {
  if (document.querySelector(`link[data-generation-intake-v3-style="${CSS.escape(STYLE_HREF)}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_HREF;
  link.dataset.generationIntakeV3Style = STYLE_HREF;
  document.head.append(link);
}

function hidden(form, name) {
  let input = form.elements?.namedItem?.(name);
  if (input instanceof HTMLInputElement) return input;
  input = document.createElement("input");
  input.type = "hidden";
  input.name = name;
  input.dataset.generationIntakeV2 = "true";
  form.append(input);
  return input;
}

function ensureContract(form) {
  [
    "generation_intake_version",
    "generation_intake_strategy_id",
    "generation_intake_preparation_recipe",
    "generation_intake_authority_strategy_id",
    "generation_intake_source_url",
    "generation_intake_source_id",
    "generation_intake_avatar_wishes",
    "generation_intake_description",
    "generation_intake_state",
    "generation_intake_server_id",
    "generation_intake_next_action",
  ].forEach((name) => hidden(form, name));
}

function sessionKey() {
  return `${SESSION_PREFIX}:${projectId() || "unscoped"}`;
}

function readSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(sessionKey()) || "null");
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

function saveSession(value) {
  try {
    sessionStorage.setItem(sessionKey(), JSON.stringify({
      ...value,
      saved_at: new Date().toISOString(),
    }));
  } catch {
    // Optional convenience only.
  }
}

function idempotency(prefix) {
  const suffix = crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  return `${prefix}-${suffix}`.slice(0, 178);
}

async function api() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") throw new Error("api_runtime_unavailable");
  const value = await Promise.resolve(factory());
  if (!value || typeof value.call !== "function") throw new Error("api_runtime_unavailable");
  return value;
}

function withOrg(client, payload) {
  if (typeof client.withOrganization === "function") return client.withOrganization(payload);
  return client.organizationId ? { organization_id: client.organizationId, ...payload } : payload;
}

function cleanField(form, name, limit) {
  const field = form.elements?.namedItem?.(name);
  return String(field?.value || "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function selectedMedia(form) {
  return qa('input[name="media_id"]:checked:not(:disabled)', form)
    .map((input) => String(input.value || "").trim().toLowerCase())
    .filter((id) => UUID.test(id));
}

function currentDraft(form) {
  const state = runtime.get(form);
  const strategy = generationIntakeStrategy(state?.strategyId);
  if (!strategy) return null;
  const panel = q(`[data-generation-intake-panel="${CSS.escape(strategy.strategy_id)}"]`, state.shell);
  const sourceUrl = canonicalGenerationIntakeSourceUrl(
    q('[data-generation-intake-field="source_url"]', panel)?.value,
  );
  const registeredUrl = String(form.elements.generation_intake_source_url?.value || "");
  const sourceId = sourceUrl && sourceUrl === registeredUrl
    ? String(form.elements.generation_intake_source_id?.value || "")
    : "";
  return createGenerationIntakeDraft(strategy.strategy_id, {
    source_url: sourceUrl,
    source_id: sourceId,
    avatar_wishes: q('[data-generation-intake-field="avatar_wishes"]', panel)?.value,
    description: q('[data-generation-intake-field="description"]', panel)?.value,
    product_media_ids: strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
      ? selectedMedia(form)
      : [],
  });
}

function persistDraft(form) {
  const state = runtime.get(form);
  const draft = currentDraft(form);
  if (!state || !draft) return;
  ensureContract(form);
  form.elements.generation_intake_version.value = draft.version;
  form.elements.generation_intake_strategy_id.value = draft.strategy_id;
  form.elements.generation_intake_preparation_recipe.value = draft.preparation_recipe;
  form.elements.generation_intake_authority_strategy_id.value = draft.authority_strategy_id || "";
  form.elements.generation_intake_source_url.value = draft.source_url;
  form.elements.generation_intake_avatar_wishes.value = draft.avatar_wishes;
  form.elements.generation_intake_description.value = draft.description;
  const validation = validateGenerationIntakeDraft(draft);
  form.elements.generation_intake_state.value = validation.ok
    ? "operator_input_ready"
    : "operator_input_incomplete";
  const brief = form.elements?.namedItem?.("brief");
  const compiled = generationIntakeInternalBrief(draft);
  if (compiled && brief instanceof HTMLTextAreaElement && state.strategyId !== GENERATION_INTAKE_STRATEGY_IDS.strategy) {
    brief.value = compiled;
    brief.dispatchEvent(new Event("input", { bubbles: true }));
  }
  saveSession({
    strategy_id: draft.strategy_id,
    source_url: draft.source_url,
    source_id: draft.source_id,
    avatar_wishes: draft.avatar_wishes,
    description: draft.description,
    server_id: form.elements.generation_intake_server_id.value,
    next_action: form.elements.generation_intake_next_action.value,
    source_media_attached: state.sourceMediaAttached,
  });
  render(form);
}

function label(title, hint, control) {
  const node = el("label", "field generation-intake-v2__field");
  node.append(el("span", "", title), control, el("small", "field-hint", hint));
  return node;
}

function sourceField() {
  const input = document.createElement("input");
  input.type = "url";
  input.inputMode = "url";
  input.autocomplete = "url";
  input.placeholder = "https://youtube.com/shorts/…";
  input.dataset.generationIntakeField = "source_url";
  return label(
    "Ссылка на ролик *",
    "Ссылка фиксирует точный ролик. Для реального разбора кадров и звука затем потребуется законный MP4.",
    input,
  );
}

function textareaField(name, title, hint, placeholder, required = false) {
  const textarea = document.createElement("textarea");
  textarea.rows = name === "avatar_wishes" ? 5 : 4;
  textarea.maxLength = 1200;
  textarea.placeholder = placeholder;
  textarea.dataset.generationIntakeField = name;
  textarea.required = required;
  return label(title, hint, textarea);
}

function strategyButton(strategy, index) {
  const button = el("button", "generation-intake-v2__strategy");
  button.type = "button";
  button.dataset.generationIntakeStrategy = strategy.strategy_id;
  button.setAttribute("aria-pressed", "false");
  const number = el("span", "generation-intake-v2__strategy-number", String(index + 1).padStart(2, "0"));
  const copy = el("span", "generation-intake-v2__strategy-copy");
  copy.append(el("strong", "", strategy.public_label), el("small", "", strategy.public_summary));
  button.append(number, copy);
  return button;
}

function compactPanel(strategy) {
  const panel = el("section", "generation-intake-v2__panel");
  panel.dataset.generationIntakePanel = strategy.strategy_id;
  panel.hidden = true;
  const head = el("header", "generation-intake-v2__panel-head");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "ОТДЕЛЬНАЯ ФОРМА"),
    el("h3", "", strategy.public_label),
    el("p", "", strategy.promise),
  );
  head.append(copy, el("span", "badge badge-warning", "Подготовка без списаний"));
  const body = el("div", "generation-intake-v2__panel-body");
  if (strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.avatar) {
    body.append(textareaField(
      "avatar_wishes",
      "Каким должен быть аватар *",
      "Внешность, возрастной образ, стиль, одежда, настроение и манера движения. Технический промпт не нужен.",
      "Например: уверенная девушка 25–30 лет, тёмные волосы, лаконичный чёрный образ, живая спокойная мимика…",
      true,
    ));
  }
  body.append(sourceField());
  if (strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy) {
    const product = el("section", "generation-intake-v2__product");
    product.dataset.generationIntakeProductSlot = "";
    product.append(
      el("h4", "", "Фото вашего товара *"),
      el("p", "muted tiny", "Выберите точный товар. Изображение исходного товара из ролика система извлекает сама после разбора MP4."),
      el("div", "generation-intake-v2__product-slot"),
    );
    body.append(product);
  }
  body.append(textareaField(
    "description",
    "Описание — по желанию",
    strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
      ? "Оставьте пустым, чтобы максимально близко повторить механику исходника без дополнительных изменений."
      : "Можно уточнить голос, характер или ограничение. Остальное система берёт из ролика и пожелания к аватару.",
    "Можно оставить пустым.",
  ));
  const status = el("div", "generation-intake-v2__status");
  status.dataset.generationIntakeStatus = "";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const actions = el("div", "generation-intake-v2__actions");
  const save = el("button", "btn", "Продолжить к разбору ролика");
  save.type = "button";
  save.dataset.action = "save-generation-intake";
  const upload = el("a", "btn btn-secondary", "Прикрепить MP4");
  upload.dataset.generationIntakeUpload = "";
  upload.hidden = true;
  actions.append(save, upload);
  panel.append(head, body, status, actions);
  return panel;
}

function fullPanel(strategy) {
  const panel = el("section", "generation-intake-v2__panel generation-intake-v2__panel--full");
  panel.dataset.generationIntakePanel = strategy.strategy_id;
  panel.hidden = true;
  panel.append(
    el("p", "eyebrow", "ПОЛНЫЙ КОНСТРУКТОР"),
    el("h3", "", strategy.public_label),
    el("p", "", strategy.promise),
    el("div", "generation-intake-v2__full-note", "Ниже остаётся полный маршрут: товар → площадка → замысел → исходники → модель → бюджет → проверка и запуск."),
  );
  return panel;
}

function buildShell() {
  const shell = el("section", "generation-intake-v2");
  shell.dataset.generationIntakeV2 = "";
  const header = el("header", "generation-intake-v2__header");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "СОЗДАНИЕ ВИДЕО"),
    el("h2", "", "Сначала выберите, что именно нужно сделать"),
    el("p", "", "У каждого способа своя форма. Никаких лишних полей из другой задачи."),
  );
  header.append(copy, el("span", "badge", "3 отдельных маршрута"));
  const nav = el("div", "generation-intake-v2__strategies");
  nav.setAttribute("role", "group");
  nav.setAttribute("aria-label", "Способ создания видео");
  GENERATION_INTAKE_STRATEGIES.forEach((strategy, index) => nav.append(strategyButton(strategy, index)));
  const panels = el("div", "generation-intake-v2__panels");
  GENERATION_INTAKE_STRATEGIES.forEach((strategy) => {
    panels.append(strategy.form_kind === "compact" ? compactPanel(strategy) : fullPanel(strategy));
  });
  const global = el("p", "generation-intake-v2__global-status");
  global.dataset.generationIntakeGlobalStatus = "";
  global.setAttribute("role", "status");
  shell.append(header, nav, panels, global);
  return shell;
}

function authorityButton(form, strategy) {
  if (strategy?.form_kind !== "full" || !strategy.authority_strategy_id) return null;
  return q(
    `[data-generation-strategy-action="SELECT"][data-strategy-id="${CSS.escape(strategy.authority_strategy_id)}"]`,
    form,
  );
}

function selectFullAuthority(form, strategy) {
  const button = authorityButton(form, strategy);
  if (!(button instanceof HTMLButtonElement) || button.disabled) return false;
  button.click();
  return true;
}

function mediaNodes(form) {
  const seen = new Set();
  return qa('input[name="media_id"]', form)
    .map((input) => input.closest("label, article, li") || input.parentElement)
    .filter((node) => node && !seen.has(node) && seen.add(node));
}

function moveProductMedia(form, state, active) {
  const slot = q(".generation-intake-v2__product-slot", state.shell);
  if (!slot) return;
  if (active) {
    if (!state.productNodes.length) {
      mediaNodes(form).forEach((node) => {
        const marker = document.createComment("generation-intake-product-origin");
        node.before(marker);
        state.productNodes.push({ node, marker });
      });
    }
    state.productNodes.forEach(({ node }) => slot.append(node));
    if (!state.productNodes.length && !q("[data-generation-intake-no-product]", slot)) {
      const warning = el("div", "alert alert-warning", "В проекте пока нет доступного фото товара.");
      warning.dataset.generationIntakeNoProduct = "";
      const link = el("a", "btn btn-secondary btn-small", "Добавить фото");
      link.href = hashUrl("/workspace/media", {
        view: "upload",
        project_id: projectId(),
        return_to: window.location.hash,
      });
      slot.append(warning, link);
    }
    return;
  }
  state.productNodes.forEach(({ node, marker }) => {
    if (marker.isConnected) marker.replaceWith(node);
  });
}

function uploadHref(sourceId, sourceUrl) {
  return hashUrl("/workspace/media", {
    view: "upload",
    project_id: projectId(),
    youtube_source: sourceId,
    video_url: sourceUrl,
    return_to: hashUrl(ROUTE, { project_id: projectId(), intake: "v2", source_url: sourceUrl }),
  });
}

function presentation(validation, draft, state) {
  if (state.errorMessage) return { kind: "error", text: state.errorMessage };
  if (!validation.ok) {
    const code = validation.errors[0]?.code;
    return {
      kind: "incomplete",
      text: {
        source_url_required: "Добавьте корректную ссылку YouTube или Shorts.",
        product_media_required: "Выберите хотя бы одно точное фото вашего товара.",
        avatar_wishes_required: "Опишите аватара хотя бы одним понятным предложением.",
      }[code] || "Заполните обязательные поля этой формы.",
    };
  }
  if (!draft.source_id) {
    return { kind: "ready-to-register", text: "Ввод готов. Следующий шаг бесплатный: зарегистрировать ролик и прикрепить MP4 для реального разбора." };
  }
  if (state.dirty) {
    return { kind: "ready-to-register", text: "Поля изменились. Сохраните новую точную подготовку; ничего не будет оплачено автоматически." };
  }
  if (state.nextAction === "prepare_internal_references") {
    return {
      kind: "source-ready",
      text: draft.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
        ? "Ролик и ваш товар зафиксированы. Следующий внутренний этап — анализ и извлечение исходного товара для Product Swap."
        : "Ролик и аватар зафиксированы. Следующий внутренний этап — character reference и перенос движения.",
    };
  }
  return { kind: "awaiting-media", text: "Ссылка зафиксирована. Прикрепите MP4; до этого анализ и платная генерация заблокированы." };
}

function render(form) {
  const state = runtime.get(form);
  if (!state) return;
  const strategy = generationIntakeStrategy(state.strategyId);
  qa("[data-generation-intake-strategy]", state.shell).forEach((button) => {
    const active = button.dataset.generationIntakeStrategy === state.strategyId;
    button.classList.toggle("is-selected", active);
    button.setAttribute("aria-pressed", String(active));
  });
  qa("[data-generation-intake-panel]", state.shell).forEach((panel) => {
    const active = panel.dataset.generationIntakePanel === state.strategyId;
    panel.hidden = !active;
    panel.setAttribute("aria-hidden", String(!active));
  });
  if (!strategy) {
    q("[data-generation-intake-global-status]", state.shell).textContent = "Выберите один из трёх способов создания.";
    return;
  }
  const compact = strategy.form_kind === "compact";
  form.dataset.generationIntakeDisplay = compact ? "compact" : "full";
  if (compact) q('[data-ce-v4-generation-target="mode"]', form)?.click?.();
  moveProductMedia(form, state, compact && strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy);
  const draft = currentDraft(form);
  const validation = validateGenerationIntakeDraft(draft);
  const panel = q(`[data-generation-intake-panel="${CSS.escape(strategy.strategy_id)}"]`, state.shell);
  const status = q("[data-generation-intake-status]", panel);
  const view = presentation(validation, draft, state);
  if (status) {
    status.dataset.state = view.kind;
    status.textContent = view.text;
  }
  const save = q('[data-action="save-generation-intake"]', panel);
  if (save instanceof HTMLButtonElement) {
    save.disabled = !validation.ok || state.saving;
    save.textContent = state.saving
      ? "Сохраняем подготовку…"
      : state.nextAction === "prepare_internal_references"
        ? "Обновить безопасный статус"
        : draft.source_id
          ? "Проверить прикреплённый MP4"
          : "Продолжить к разбору ролика";
  }
  const upload = q("[data-generation-intake-upload]", panel);
  if (upload instanceof HTMLAnchorElement) {
    upload.hidden = !draft.source_id || state.sourceMediaAttached;
    upload.href = draft.source_id ? uploadHref(draft.source_id, draft.source_url) : "";
  }
  q("[data-generation-intake-global-status]", state.shell).textContent = compact
    ? "Компактная форма только готовит источник и ввод. Оплата, выбор модели и provider call здесь невозможны."
    : "Полный конструктор сохраняет существующие budget, preflight, generation-spec и QA-защиты.";
}

function validSource(response, sourceUrl) {
  const root = response?.data && typeof response.data === "object" ? response.data : response;
  const source = root?.source;
  if (
    root?.ok !== true
    || root?.version !== "exact-youtube-source-intake-v1"
    || !source
    || !UUID.test(String(source.id || ""))
    || source.project_id !== projectId()
    || source.canonical_url !== sourceUrl
    || source.status !== "awaiting_media"
    || source.media_required !== true
    || !SHA256.test(String(source.source_hash || ""))
    || root?.contract?.url_is_video_evidence !== false
    || root?.contract?.requires_lawful_mp4 !== true
    || root?.contract?.paid_analysis_allowed !== false
    || root?.contract?.external_call_started !== false
    || root?.contract?.paid_call_started !== false
  ) return null;
  return source;
}

function validIntake(response, draft, source) {
  const root = response?.data && typeof response.data === "object" ? response.data : response;
  const intake = root?.intake;
  if (
    root?.ok !== true
    || root?.version !== GENERATION_INTAKE_VERSION
    || !intake
    || !UUID.test(String(intake.id || ""))
    || intake.project_id !== projectId()
    || intake.source_id !== source.id
    || intake.strategy_id !== draft.strategy_id
    || intake.preparation_recipe !== draft.preparation_recipe
    || !SHA256.test(String(intake.input_hash || ""))
    || root?.contract?.separate_operator_form !== true
    || root?.contract?.provider_call_started !== false
    || root?.contract?.paid_call_started !== false
    || root?.contract?.budget_reserved !== false
    || root?.contract?.browser_price_authority !== false
    || root?.contract?.browser_provider_authority !== false
    || root?.contract?.human_review_required !== true
  ) return null;
  return intake;
}

async function saveCompact(form) {
  const state = runtime.get(form);
  const draft = currentDraft(form);
  const validation = validateGenerationIntakeDraft(draft);
  if (!state || state.saving || !validation.ok) return;
  if (!projectId()) {
    state.errorMessage = "Откройте создание из конкретного проекта. Ничего не списано.";
    render(form);
    return;
  }
  state.saving = true;
  state.errorMessage = "";
  render(form);
  try {
    const client = await api();
    const videoId = draft.source_url.slice(-11);
    const sourceResponse = await client.call(RPC_SOURCE, withOrg(client, {
      project_id: projectId(),
      canonical_url: draft.source_url,
      video_id: videoId,
      product_name: cleanField(form, "product_name", 300),
      product_sku: cleanField(form, "sku", 160),
      idempotency_key: idempotency(`generation-intake-source-${videoId}`),
    }));
    const source = validSource(sourceResponse, draft.source_url);
    if (!source) throw new Error("exact_source_response_invalid");
    form.elements.generation_intake_source_url.value = draft.source_url;
    form.elements.generation_intake_source_id.value = source.id;
    const exactDraft = createGenerationIntakeDraft(draft.strategy_id, { ...draft, source_id: source.id });
    if (!state.idempotencyKey || state.dirty) {
      state.idempotencyKey = idempotency(`generation-intake-${draft.strategy_id}`);
    }
    const intakeResponse = await client.call(RPC_INTAKE, withOrg(client, {
      project_id: projectId(),
      source_id: source.id,
      strategy_id: exactDraft.strategy_id,
      avatar_wishes: exactDraft.avatar_wishes,
      description: exactDraft.description,
      product_media_ids: exactDraft.product_media_ids,
      idempotency_key: state.idempotencyKey,
    }));
    const intake = validIntake(intakeResponse, exactDraft, source);
    if (!intake) throw new Error("generation_intake_response_invalid");
    form.elements.generation_intake_server_id.value = intake.id;
    form.elements.generation_intake_state.value = intake.status;
    form.elements.generation_intake_next_action.value = intake.next_action;
    state.nextAction = intake.next_action;
    state.sourceMediaAttached = intake.source_media_attached === true;
    state.dirty = false;
    persistDraft(form);
  } catch (error) {
    state.errorMessage = "Не удалось сохранить подготовку. Ничего не списано. Проверьте ссылку и выбранные данные.";
    console.warn("Generation intake v2 preparation failed", error);
  } finally {
    state.saving = false;
    render(form);
  }
}

function resetSavedState(form, state, { sourceChanged = false } = {}) {
  state.errorMessage = "";
  state.dirty = true;
  state.idempotencyKey = "";
  state.nextAction = "";
  form.elements.generation_intake_server_id.value = "";
  form.elements.generation_intake_next_action.value = "";
  if (sourceChanged) {
    state.sourceMediaAttached = false;
    form.elements.generation_intake_source_id.value = "";
  }
}

function restore(form, state) {
  const saved = readSession();
  if (!saved) return;
  const strategy = generationIntakeStrategy(saved.strategy_id);
  if (!strategy) return;
  state.strategyId = strategy.strategy_id;
  const panel = q(`[data-generation-intake-panel="${CSS.escape(strategy.strategy_id)}"]`, state.shell);
  const source = q('[data-generation-intake-field="source_url"]', panel);
  const wishes = q('[data-generation-intake-field="avatar_wishes"]', panel);
  const description = q('[data-generation-intake-field="description"]', panel);
  if (source) source.value = String(saved.source_url || "");
  if (wishes) wishes.value = String(saved.avatar_wishes || "");
  if (description) description.value = String(saved.description || "");
  form.elements.generation_intake_source_url.value = String(saved.source_url || "");
  form.elements.generation_intake_source_id.value = UUID.test(String(saved.source_id || "")) ? saved.source_id : "";
  form.elements.generation_intake_server_id.value = UUID.test(String(saved.server_id || "")) ? saved.server_id : "";
  form.elements.generation_intake_next_action.value = String(saved.next_action || "");
  state.nextAction = String(saved.next_action || "");
  state.sourceMediaAttached = saved.source_media_attached === true;
  if (strategy.form_kind === "full") selectFullAuthority(form, strategy);
}

function bind(form, state) {
  state.shell.addEventListener("click", (event) => {
    const route = event.target.closest?.("[data-generation-intake-strategy]");
    if (route) {
      const strategy = generationIntakeStrategy(route.dataset.generationIntakeStrategy);
      if (!strategy) return;
      state.strategyId = strategy.strategy_id;
      state.sourceMediaAttached = false;
      resetSavedState(form, state, { sourceChanged: true });
      if (strategy.form_kind === "full") selectFullAuthority(form, strategy);
      persistDraft(form);
      return;
    }
    if (event.target.closest?.('[data-action="save-generation-intake"]')) void saveCompact(form);
  });
  state.shell.addEventListener("input", (event) => {
    if (!event.target.closest?.("[data-generation-intake-field]")) return;
    const sourceChanged = event.target.matches?.('[data-generation-intake-field="source_url"]')
      && canonicalGenerationIntakeSourceUrl(event.target.value)
        !== String(form.elements.generation_intake_source_url.value || "");
    resetSavedState(form, state, { sourceChanged });
    persistDraft(form);
  });
  form.addEventListener("change", (event) => {
    if (!event.target.matches?.('input[name="media_id"]')) return;
    resetSavedState(form, state);
    persistDraft(form);
  });
  state.shell.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing || event.target instanceof HTMLTextAreaElement) return;
    const strategy = generationIntakeStrategy(state.strategyId);
    if (strategy?.form_kind !== "compact") return;
    event.preventDefault();
    void saveCompact(form);
  });
  form.addEventListener("submit", (event) => {
    const strategy = generationIntakeStrategy(state.strategyId);
    if (strategy?.form_kind !== "compact") return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void saveCompact(form);
  }, true);
}

function mount(form) {
  if (!(form instanceof HTMLFormElement)) return;
  const existing = runtime.get(form);
  if (existing?.shell?.isConnected) {
    render(form);
    return;
  }
  ensureStyle();
  ensureContract(form);
  const legacy = q(".generation-strategy-view", form);
  const modePanel = q('[data-ce-v4-generation-panel="mode"]', form) || legacy?.parentElement || form;
  const shell = buildShell();
  if (legacy) {
    legacy.before(shell);
    legacy.dataset.generationIntakeLegacy = "true";
    legacy.setAttribute("aria-hidden", "true");
    qa("button, input, select, textarea, a", legacy).forEach((control) => { control.tabIndex = -1; });
  } else {
    modePanel.prepend(shell);
  }
  const state = {
    shell,
    strategyId: "",
    productNodes: [],
    saving: false,
    dirty: false,
    sourceMediaAttached: false,
    nextAction: "",
    idempotencyKey: "",
    errorMessage: "",
  };
  runtime.set(form, state);
  form.dataset.generationIntakeV2Bound = GENERATION_INTAKE_VERSION;
  bind(form, state);
  restore(form, state);
  if (!state.strategyId) {
    const authority = String(form.elements?.generation_strategy_id?.value || "");
    const mapped = generationIntakeStrategyForAuthority(authority);
    if (mapped) state.strategyId = mapped.strategy_id;
  }
  render(form);
}

function schedule() {
  if (queued) return;
  queued = true;
  queueMicrotask(() => {
    queued = false;
    if (routePath() !== ROUTE) return;
    const form = q("#mock-batch-form");
    if (form) mount(form);
  });
}

window.addEventListener("hashchange", schedule);
window.addEventListener("contentengine:rendered", schedule);
new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
schedule();
