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
} from "./generation-strategy-intake-contract-v2.js?v=20260826.rebuild-clean.60";

/*
 * Three separate operator forms for one generation workspace.
 *
 * Copy and Avatar only register immutable preparation input. They never call a
 * provider, reserve money, choose a paid model, or reuse the legacy submit.
 * Strategy keeps the existing full generation-spec and paid-launch authority.
 */

const ROUTE = "/workspace/generation";
const RPC_SOURCE = "contentengine_register_exact_youtube_source";
const RPC_INTAKE = "contentengine_save_generation_intake_v2";
const SESSION_PREFIX = "contentengine.generation.intake-v2";
const STYLE_HREF = new URL(
  "./generation-strategy-intake-v3.css?v=20260826.rebuild-clean.60",
  import.meta.url,
).href;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

const formStates = new WeakMap();
let mountQueued = false;

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function node(tagName, className = "", text = "") {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function routePath() {
  const managed = window.ContentEngineDesktopV4?.route?.();
  if (managed) return managed;
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function routeParams() {
  const hash = String(window.location.hash || "");
  const query = hash.includes("?") ? hash.slice(hash.indexOf("?") + 1) : "";
  return new URLSearchParams(query);
}

function currentProjectId() {
  const value = String(routeParams().get("project_id") || "")
    .trim()
    .toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

function hashUrl(route, values = {}) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, raw]) => {
    const value = String(raw ?? "").trim();
    if (value) query.set(key, value);
  });
  return `#${route}${query.size ? `?${query.toString()}` : ""}`;
}

function ensureStyle() {
  if (document.querySelector(
    `link[data-generation-intake-v3-style="${CSS.escape(STYLE_HREF)}"]`,
  )) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_HREF;
  link.dataset.generationIntakeV3Style = STYLE_HREF;
  document.head.append(link);
}

function ensureHidden(form, name) {
  const existing = form.elements?.namedItem?.(name);
  if (existing instanceof HTMLInputElement) return existing;
  const input = document.createElement("input");
  input.type = "hidden";
  input.name = name;
  input.dataset.generationIntakeV2 = "true";
  form.append(input);
  return input;
}

function ensureHiddenContract(form) {
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
  ].forEach((name) => ensureHidden(form, name));
}

function sessionKey() {
  return `${SESSION_PREFIX}:${currentProjectId() || "unscoped"}`;
}

function readSession() {
  try {
    const value = JSON.parse(sessionStorage.getItem(sessionKey()) || "null");
    return value && typeof value === "object" && !Array.isArray(value)
      ? value
      : null;
  } catch {
    return null;
  }
}

function writeSession(value) {
  try {
    sessionStorage.setItem(sessionKey(), JSON.stringify({
      ...value,
      saved_at: new Date().toISOString(),
    }));
  } catch {
    // Session memory is optional and never authorizes a provider call.
  }
}

function newIdempotencyKey(prefix) {
  const suffix = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`.slice(0, 178);
}

async function workspaceApi() {
  const factory = window.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") throw new Error("api_runtime_unavailable");
  const value = await Promise.resolve(factory());
  if (!value || typeof value.call !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  return value;
}

function withOrganization(client, payload) {
  if (typeof client.withOrganization === "function") {
    return client.withOrganization(payload);
  }
  return client.organizationId
    ? { organization_id: client.organizationId, ...payload }
    : payload;
}

function cleanFormText(form, name, maxLength) {
  const field = form.elements?.namedItem?.(name);
  return String(field?.value || "")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, maxLength);
}

function selectedProductMediaIds(form) {
  return qa('input[name="media_id"]:checked:not(:disabled)', form)
    .map((input) => String(input.value || "").trim().toLowerCase())
    .filter((id) => UUID_PATTERN.test(id));
}

function panelFor(state, strategyId) {
  return q(
    `[data-generation-intake-panel="${CSS.escape(strategyId)}"]`,
    state.shell,
  );
}

function buildCurrentDraft(form) {
  const state = formStates.get(form);
  const strategy = generationIntakeStrategy(state?.strategyId);
  if (!state || !strategy) return null;
  const panel = panelFor(state, strategy.strategy_id);
  const canonicalSourceUrl = canonicalGenerationIntakeSourceUrl(
    q('[data-generation-intake-field="source_url"]', panel)?.value,
  );
  const registeredSourceUrl = String(
    form.elements.generation_intake_source_url?.value || "",
  );
  const registeredSourceId = canonicalSourceUrl
    && canonicalSourceUrl === registeredSourceUrl
    ? String(form.elements.generation_intake_source_id?.value || "")
    : "";

  return createGenerationIntakeDraft(strategy.strategy_id, {
    source_url: canonicalSourceUrl,
    source_id: registeredSourceId,
    avatar_wishes: q(
      '[data-generation-intake-field="avatar_wishes"]',
      panel,
    )?.value,
    description: q(
      '[data-generation-intake-field="description"]',
      panel,
    )?.value,
    product_media_ids:
      strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
        ? selectedProductMediaIds(form)
        : [],
  });
}

function syncDraftToForm(form) {
  const state = formStates.get(form);
  const draft = buildCurrentDraft(form);
  if (!state || !draft) return;

  ensureHiddenContract(form);
  form.elements.generation_intake_version.value = draft.version;
  form.elements.generation_intake_strategy_id.value = draft.strategy_id;
  form.elements.generation_intake_preparation_recipe.value =
    draft.preparation_recipe;
  form.elements.generation_intake_authority_strategy_id.value =
    draft.authority_strategy_id || "";
  form.elements.generation_intake_source_url.value = draft.source_url;
  form.elements.generation_intake_avatar_wishes.value = draft.avatar_wishes;
  form.elements.generation_intake_description.value = draft.description;

  const validation = validateGenerationIntakeDraft(draft);
  form.elements.generation_intake_state.value = validation.ok
    ? "operator_input_ready"
    : "operator_input_incomplete";

  const compiledBrief = generationIntakeInternalBrief(draft);
  const brief = form.elements?.namedItem?.("brief");
  if (
    compiledBrief
    && brief instanceof HTMLTextAreaElement
    && draft.strategy_id !== GENERATION_INTAKE_STRATEGY_IDS.strategy
  ) {
    brief.value = compiledBrief;
    brief.dispatchEvent(new Event("input", { bubbles: true }));
  }

  writeSession({
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

function fieldLabel(title, hint, control) {
  const label = node("label", "field generation-intake-v2__field");
  label.append(
    node("span", "", title),
    control,
    node("small", "field-hint", hint),
  );
  return label;
}

function sourceUrlField() {
  const input = document.createElement("input");
  input.type = "url";
  input.inputMode = "url";
  input.autocomplete = "url";
  input.placeholder = "https://youtube.com/shorts/…";
  input.dataset.generationIntakeField = "source_url";
  return fieldLabel(
    "Ссылка на ролик *",
    "Ссылка фиксирует точный ролик. Для разбора кадров и звука затем нужен законный MP4.",
    input,
  );
}

function textareaField({
  name,
  title,
  hint,
  placeholder,
  required = false,
  rows = 4,
}) {
  const textarea = document.createElement("textarea");
  textarea.rows = rows;
  textarea.maxLength = 1_200;
  textarea.placeholder = placeholder;
  textarea.required = required;
  textarea.dataset.generationIntakeField = name;
  return fieldLabel(title, hint, textarea);
}

function strategyCard(strategy, index) {
  const button = node("button", "generation-intake-v2__strategy");
  button.type = "button";
  button.dataset.generationIntakeStrategy = strategy.strategy_id;
  button.setAttribute("aria-pressed", "false");

  const copy = node("span", "generation-intake-v2__strategy-copy");
  copy.append(
    node("strong", "", strategy.public_label),
    node("small", "", strategy.public_summary),
  );
  button.append(
    node(
      "span",
      "generation-intake-v2__strategy-number",
      String(index + 1).padStart(2, "0"),
    ),
    copy,
  );
  return button;
}

function compactPanel(strategy) {
  const panel = node("section", "generation-intake-v2__panel");
  panel.dataset.generationIntakePanel = strategy.strategy_id;
  panel.hidden = true;

  const header = node("header", "generation-intake-v2__panel-head");
  const headerCopy = node("div");
  headerCopy.append(
    node("p", "eyebrow", "ОТДЕЛЬНАЯ ФОРМА"),
    node("h3", "", strategy.public_label),
    node("p", "", strategy.promise),
  );
  header.append(
    headerCopy,
    node("span", "badge badge-warning", "Подготовка без списаний"),
  );

  const body = node("div", "generation-intake-v2__panel-body");
  if (strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.avatar) {
    body.append(textareaField({
      name: "avatar_wishes",
      title: "Каким должен быть аватар *",
      hint:
        "Опишите внешность, возрастной образ, стиль, одежду, настроение и манеру движения. Технический промпт не нужен.",
      placeholder:
        "Например: уверенная девушка 25–30 лет, тёмные волосы, лаконичный чёрный образ, живая спокойная мимика…",
      required: true,
      rows: 5,
    }));
  }
  body.append(sourceUrlField());

  if (strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy) {
    const product = node("section", "generation-intake-v2__product");
    product.dataset.generationIntakeProductSlot = "";
    product.append(
      node("h4", "", "Фото вашего товара *"),
      node(
        "p",
        "muted tiny",
        "Выберите точный товар. Изображение исходного товара из ролика система извлекает сама после разбора MP4.",
      ),
      node("div", "generation-intake-v2__product-slot"),
    );
    body.append(product);
  }

  body.append(textareaField({
    name: "description",
    title: "Описание — по желанию",
    hint:
      strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
        ? "Оставьте пустым, чтобы максимально близко повторить механику исходника без дополнительных изменений."
        : "Можно уточнить голос, характер или ограничение. Остальное система берёт из ролика и пожелания к аватару.",
    placeholder: "Можно оставить пустым.",
  }));

  const status = node("div", "generation-intake-v2__status");
  status.dataset.generationIntakeStatus = "";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  const actions = node("div", "generation-intake-v2__actions");
  const save = node("button", "btn", "Продолжить к разбору ролика");
  save.type = "button";
  save.dataset.action = "save-generation-intake";
  const upload = node("a", "btn btn-secondary", "Прикрепить MP4");
  upload.dataset.generationIntakeUpload = "";
  upload.hidden = true;
  actions.append(save, upload);

  panel.append(header, body, status, actions);
  return panel;
}

function fullStrategyPanel(strategy) {
  const panel = node(
    "section",
    "generation-intake-v2__panel generation-intake-v2__panel--full",
  );
  panel.dataset.generationIntakePanel = strategy.strategy_id;
  panel.hidden = true;
  panel.append(
    node("p", "eyebrow", "ПОЛНЫЙ КОНСТРУКТОР"),
    node("h3", "", strategy.public_label),
    node("p", "", strategy.promise),
    node(
      "div",
      "generation-intake-v2__full-note",
      "Ниже остаётся полный маршрут: товар → площадка → замысел → исходники → модель → бюджет → проверка и запуск.",
    ),
  );
  return panel;
}

function buildShell() {
  const shell = node("section", "generation-intake-v2");
  shell.dataset.generationIntakeV2 = "";

  const header = node("header", "generation-intake-v2__header");
  const headerCopy = node("div");
  headerCopy.append(
    node("p", "eyebrow", "СОЗДАНИЕ ВИДЕО"),
    node("h2", "", "Сначала выберите, что именно нужно сделать"),
    node(
      "p",
      "",
      "У каждого способа своя форма. Никаких лишних полей из другой задачи.",
    ),
  );
  header.append(headerCopy, node("span", "badge", "3 отдельных маршрута"));

  const strategyList = node("div", "generation-intake-v2__strategies");
  strategyList.setAttribute("role", "group");
  strategyList.setAttribute("aria-label", "Способ создания видео");
  GENERATION_INTAKE_STRATEGIES.forEach((strategy, index) => {
    strategyList.append(strategyCard(strategy, index));
  });

  const panels = node("div", "generation-intake-v2__panels");
  GENERATION_INTAKE_STRATEGIES.forEach((strategy) => {
    panels.append(
      strategy.form_kind === "compact"
        ? compactPanel(strategy)
        : fullStrategyPanel(strategy),
    );
  });

  const globalStatus = node("p", "generation-intake-v2__global-status");
  globalStatus.dataset.generationIntakeGlobalStatus = "";
  globalStatus.setAttribute("role", "status");
  shell.append(header, strategyList, panels, globalStatus);
  return shell;
}

function legacyAuthorityButton(form, strategy) {
  if (strategy?.form_kind !== "full" || !strategy.authority_strategy_id) {
    return null;
  }
  return q(
    `[data-generation-strategy-action="SELECT"]`
      + `[data-strategy-id="${CSS.escape(strategy.authority_strategy_id)}"]`,
    form,
  );
}

function selectFullStrategyAuthority(form, strategy) {
  const button = legacyAuthorityButton(form, strategy);
  if (!(button instanceof HTMLButtonElement) || button.disabled) return false;
  button.click();
  return true;
}

function collectProductMediaNodes(form) {
  const seen = new Set();
  return qa('input[name="media_id"]', form)
    .map((input) => input.closest("label, article, li") || input.parentElement)
    .filter((item) => {
      if (!item || seen.has(item)) return false;
      seen.add(item);
      return true;
    });
}

function moveProductMedia(form, state, intoCopyForm) {
  const slot = q(".generation-intake-v2__product-slot", state.shell);
  if (!slot) return;

  if (intoCopyForm) {
    if (!state.productNodes.length) {
      collectProductMediaNodes(form).forEach((item) => {
        const marker = document.createComment("generation-intake-product-origin");
        item.before(marker);
        state.productNodes.push({ item, marker });
      });
    }
    state.productNodes.forEach(({ item }) => slot.append(item));
    if (!state.productNodes.length && !q("[data-generation-intake-no-product]", slot)) {
      const warning = node(
        "div",
        "alert alert-warning",
        "В проекте пока нет доступного фото товара.",
      );
      warning.dataset.generationIntakeNoProduct = "";
      const link = node("a", "btn btn-secondary btn-small", "Добавить фото");
      link.href = hashUrl("/workspace/media", {
        view: "upload",
        project_id: currentProjectId(),
        return_to: window.location.hash,
      });
      slot.append(warning, link);
    }
    return;
  }

  state.productNodes.forEach(({ item, marker }) => {
    if (marker.isConnected) marker.replaceWith(item);
  });
}

function uploadHref(sourceId, sourceUrl) {
  return hashUrl("/workspace/media", {
    view: "upload",
    project_id: currentProjectId(),
    youtube_source: sourceId,
    video_url: sourceUrl,
    return_to: hashUrl(ROUTE, {
      project_id: currentProjectId(),
      intake: "v2",
      source_url: sourceUrl,
    }),
  });
}

function resetSavedPreparation(form, state, { sourceChanged = false } = {}) {
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

function statusPresentation(validation, draft, state) {
  if (state.errorMessage) {
    return { state: "error", text: state.errorMessage };
  }
  if (!validation.ok) {
    const firstCode = validation.errors[0]?.code;
    const messages = {
      source_url_required: "Добавьте корректную ссылку YouTube или Shorts.",
      product_media_required: "Выберите хотя бы одно точное фото вашего товара.",
      avatar_wishes_required:
        "Опишите аватара хотя бы одним понятным предложением.",
    };
    return {
      state: "incomplete",
      text: messages[firstCode] || "Заполните обязательные поля этой формы.",
    };
  }
  if (!draft.source_id) {
    return {
      state: "ready-to-register",
      text:
        "Ввод готов. Следующий шаг бесплатный: зарегистрировать ролик и прикрепить MP4 для реального разбора.",
    };
  }
  if (state.dirty) {
    return {
      state: "ready-to-register",
      text:
        "Поля изменились. Сохраните новую точную подготовку; ничего не будет оплачено автоматически.",
    };
  }
  if (state.nextAction === "prepare_internal_references") {
    return {
      state: "source-ready",
      text:
        draft.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
          ? "Ролик и ваш товар зафиксированы. Далее система готовит анализ и исходный товар для Product Swap."
          : "Ролик и пожелания к аватару зафиксированы. Далее система готовит character reference и перенос движения.",
    };
  }
  return {
    state: "awaiting-media",
    text:
      "Ссылка зафиксирована. Прикрепите MP4; до этого анализ и платная генерация заблокированы.",
  };
}

function render(form) {
  const state = formStates.get(form);
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
    q("[data-generation-intake-global-status]", state.shell).textContent =
      "Выберите один из трёх способов создания.";
    return;
  }

  const compact = strategy.form_kind === "compact";
  form.dataset.generationIntakeDisplay = compact ? "compact" : "full";
  if (compact) q('[data-ce-v4-generation-target="mode"]', form)?.click?.();
  moveProductMedia(
    form,
    state,
    compact && strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy,
  );

  const draft = buildCurrentDraft(form);
  const validation = validateGenerationIntakeDraft(draft);
  const panel = panelFor(state, strategy.strategy_id);
  const status = q("[data-generation-intake-status]", panel);
  const presentation = statusPresentation(validation, draft, state);
  if (status) {
    status.dataset.state = presentation.state;
    status.textContent = presentation.text;
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
    upload.href = draft.source_id
      ? uploadHref(draft.source_id, draft.source_url)
      : "";
  }

  q("[data-generation-intake-global-status]", state.shell).textContent =
    compact
      ? "Компактная форма только готовит источник и ввод. Оплата, выбор модели и provider call здесь невозможны."
      : "Полный конструктор сохраняет существующие budget, preflight, generation-spec и QA-защиты.";
}

function normalizeSourceResponse(response, canonicalUrl) {
  const root = response?.data && typeof response.data === "object"
    ? response.data
    : response;
  const source = root?.source;
  if (
    root?.ok !== true
    || root?.version !== "exact-youtube-source-intake-v1"
    || !source
    || !UUID_PATTERN.test(String(source.id || ""))
    || source.project_id !== currentProjectId()
    || source.canonical_url !== canonicalUrl
    || source.status !== "awaiting_media"
    || source.media_required !== true
    || !SHA256_PATTERN.test(String(source.source_hash || ""))
    || root?.contract?.url_is_video_evidence !== false
    || root?.contract?.requires_lawful_mp4 !== true
    || root?.contract?.paid_analysis_allowed !== false
    || root?.contract?.external_call_started !== false
    || root?.contract?.paid_call_started !== false
  ) return null;
  return source;
}

function normalizeIntakeResponse(response, draft, source) {
  const root = response?.data && typeof response.data === "object"
    ? response.data
    : response;
  const intake = root?.intake;
  if (
    root?.ok !== true
    || root?.version !== GENERATION_INTAKE_VERSION
    || !intake
    || !UUID_PATTERN.test(String(intake.id || ""))
    || intake.project_id !== currentProjectId()
    || intake.source_id !== source.id
    || intake.strategy_id !== draft.strategy_id
    || intake.preparation_recipe !== draft.preparation_recipe
    || !SHA256_PATTERN.test(String(intake.input_hash || ""))
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

async function saveCompactPreparation(form) {
  const state = formStates.get(form);
  const draft = buildCurrentDraft(form);
  const validation = validateGenerationIntakeDraft(draft);
  if (!state || state.saving || !validation.ok) return;

  if (!currentProjectId()) {
    state.errorMessage =
      "Откройте создание из конкретного проекта. Ничего не списано.";
    render(form);
    return;
  }

  state.saving = true;
  state.errorMessage = "";
  render(form);
  try {
    const client = await workspaceApi();
    const videoId = draft.source_url.slice(-11);
    const sourceResponse = await client.call(
      RPC_SOURCE,
      withOrganization(client, {
        project_id: currentProjectId(),
        canonical_url: draft.source_url,
        video_id: videoId,
        product_name: cleanFormText(form, "product_name", 300),
        product_sku: cleanFormText(form, "sku", 160),
        idempotency_key: newIdempotencyKey(
          `generation-intake-source-${videoId}`,
        ),
      }),
    );
    const source = normalizeSourceResponse(sourceResponse, draft.source_url);
    if (!source) throw new Error("exact_source_response_invalid");

    form.elements.generation_intake_source_url.value = draft.source_url;
    form.elements.generation_intake_source_id.value = source.id;
    const exactDraft = createGenerationIntakeDraft(draft.strategy_id, {
      ...draft,
      source_id: source.id,
    });
    if (!state.idempotencyKey || state.dirty) {
      state.idempotencyKey = newIdempotencyKey(
        `generation-intake-${draft.strategy_id}`,
      );
    }

    const intakeResponse = await client.call(
      RPC_INTAKE,
      withOrganization(client, {
        project_id: currentProjectId(),
        source_id: source.id,
        strategy_id: exactDraft.strategy_id,
        avatar_wishes: exactDraft.avatar_wishes,
        description: exactDraft.description,
        product_media_ids: exactDraft.product_media_ids,
        idempotency_key: state.idempotencyKey,
      }),
    );
    const intake = normalizeIntakeResponse(intakeResponse, exactDraft, source);
    if (!intake) throw new Error("generation_intake_response_invalid");

    form.elements.generation_intake_server_id.value = intake.id;
    form.elements.generation_intake_state.value = intake.status;
    form.elements.generation_intake_next_action.value = intake.next_action;
    state.nextAction = intake.next_action;
    state.sourceMediaAttached = intake.source_media_attached === true;
    state.dirty = false;
    syncDraftToForm(form);
  } catch (error) {
    state.errorMessage =
      "Не удалось сохранить подготовку. Ничего не списано. Проверьте ссылку и выбранные данные.";
    console.warn("Generation intake v2 preparation failed", error);
  } finally {
    state.saving = false;
    render(form);
  }
}

function restoreSession(form, state) {
  const saved = readSession();
  if (!saved) return;
  const strategy = generationIntakeStrategy(saved.strategy_id);
  if (!strategy) return;

  state.strategyId = strategy.strategy_id;
  state.nextAction = String(saved.next_action || "");
  state.sourceMediaAttached = saved.source_media_attached === true;
  const panel = panelFor(state, strategy.strategy_id);
  const source = q('[data-generation-intake-field="source_url"]', panel);
  const wishes = q('[data-generation-intake-field="avatar_wishes"]', panel);
  const description = q('[data-generation-intake-field="description"]', panel);
  if (source) source.value = String(saved.source_url || "");
  if (wishes) wishes.value = String(saved.avatar_wishes || "");
  if (description) description.value = String(saved.description || "");

  form.elements.generation_intake_source_url.value = String(
    saved.source_url || "",
  );
  form.elements.generation_intake_source_id.value = UUID_PATTERN.test(
    String(saved.source_id || ""),
  ) ? saved.source_id : "";
  form.elements.generation_intake_server_id.value = UUID_PATTERN.test(
    String(saved.server_id || ""),
  ) ? saved.server_id : "";
  form.elements.generation_intake_next_action.value = state.nextAction;

  if (strategy.form_kind === "full") {
    selectFullStrategyAuthority(form, strategy);
  }
}

function bind(form, state) {
  state.shell.addEventListener("click", (event) => {
    const strategyButton = event.target.closest?.(
      "[data-generation-intake-strategy]",
    );
    if (strategyButton) {
      const strategy = generationIntakeStrategy(
        strategyButton.dataset.generationIntakeStrategy,
      );
      if (!strategy) return;
      state.strategyId = strategy.strategy_id;
      state.sourceMediaAttached = false;
      resetSavedPreparation(form, state, { sourceChanged: true });
      if (strategy.form_kind === "full") {
        selectFullStrategyAuthority(form, strategy);
      }
      syncDraftToForm(form);
      return;
    }

    if (event.target.closest?.('[data-action="save-generation-intake"]')) {
      void saveCompactPreparation(form);
    }
  });

  state.shell.addEventListener("input", (event) => {
    if (!event.target.closest?.("[data-generation-intake-field]")) return;
    const sourceChanged = event.target.matches?.(
      '[data-generation-intake-field="source_url"]',
    ) && canonicalGenerationIntakeSourceUrl(event.target.value)
      !== String(form.elements.generation_intake_source_url.value || "");
    resetSavedPreparation(form, state, { sourceChanged });
    syncDraftToForm(form);
  });

  form.addEventListener("change", (event) => {
    if (!event.target.matches?.('input[name="media_id"]')) return;
    resetSavedPreparation(form, state);
    syncDraftToForm(form);
  });

  state.shell.addEventListener("keydown", (event) => {
    if (
      event.key !== "Enter"
      || event.shiftKey
      || event.isComposing
      || event.target instanceof HTMLTextAreaElement
    ) return;
    const strategy = generationIntakeStrategy(state.strategyId);
    if (strategy?.form_kind !== "compact") return;
    event.preventDefault();
    void saveCompactPreparation(form);
  });

  form.addEventListener("submit", (event) => {
    const strategy = generationIntakeStrategy(state.strategyId);
    if (strategy?.form_kind !== "compact") return;
    event.preventDefault();
    event.stopImmediatePropagation();
    void saveCompactPreparation(form);
  }, true);
}

function mountForm(form) {
  if (!(form instanceof HTMLFormElement)) return;
  const existing = formStates.get(form);
  if (existing?.shell?.isConnected) {
    render(form);
    return;
  }

  ensureStyle();
  ensureHiddenContract(form);
  const legacyStrategyView = q(".generation-strategy-view", form);
  const modePanel = q('[data-ce-v4-generation-panel="mode"]', form)
    || legacyStrategyView?.parentElement
    || form;
  const shell = buildShell();

  if (legacyStrategyView) {
    legacyStrategyView.before(shell);
    legacyStrategyView.dataset.generationIntakeLegacy = "true";
    legacyStrategyView.setAttribute("aria-hidden", "true");
    qa("button, input, select, textarea, a", legacyStrategyView).forEach(
      (control) => { control.tabIndex = -1; },
    );
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
  formStates.set(form, state);
  form.dataset.generationIntakeV2Bound = GENERATION_INTAKE_VERSION;
  bind(form, state);
  restoreSession(form, state);

  if (!state.strategyId) {
    const currentAuthority = String(
      form.elements?.generation_strategy_id?.value || "",
    );
    const mapped = generationIntakeStrategyForAuthority(currentAuthority);
    if (mapped) state.strategyId = mapped.strategy_id;
  }
  render(form);
}

function scheduleMount() {
  if (mountQueued) return;
  mountQueued = true;
  queueMicrotask(() => {
    mountQueued = false;
    if (routePath() !== ROUTE) return;
    const form = q("#mock-batch-form");
    if (form) mountForm(form);
  });
}

window.addEventListener("hashchange", scheduleMount);
window.addEventListener("contentengine:rendered", scheduleMount);
new MutationObserver(scheduleMount).observe(document.documentElement, {
  childList: true,
  subtree: true,
});
scheduleMount();
