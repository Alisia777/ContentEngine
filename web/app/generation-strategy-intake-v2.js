import {
  GENERATION_INTAKE_STRATEGIES,
  GENERATION_INTAKE_STRATEGY_IDS,
  GENERATION_INTAKE_VERSION,
  canonicalGenerationIntakeSourceUrl,
  createGenerationIntakeDraft,
  generationIntakeInternalBrief,
  generationIntakeStrategy,
  generationIntakeStrategyForLegacy,
  validateGenerationIntakeDraft,
} from "./generation-strategy-intake-contract-v2.js?v=20260814.intake2.1";

/*
 * ContentEngine · three separate generation intakes.
 *
 * The old universal form remains the authority for the full strategy route.
 * Copy and Avatar are compact preparation flows: they register one exact video
 * source and hand off lawful media attachment before any provider or paid call.
 * No API key, provider payload, price receipt, or automatic paid fallback is
 * ever created in this browser adapter.
 */

const ROUTE = "/workspace/generation";
const RPC_REGISTER_SOURCE = "contentengine_register_exact_youtube_source";
const RPC_SAVE_INTAKE = "creator_save_generation_intake_v2";
const BOUND_ATTRIBUTE = "data-generation-intake-v2-bound";
const SESSION_PREFIX = "contentengine.generation.intake-v2";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

const states = new WeakMap();
let scheduled = false;

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
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || "/";
}

function routeParams() {
  const raw = String(window.location.hash || "");
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

function sessionKey() {
  return `${SESSION_PREFIX}:${projectId() || "unscoped"}`;
}

function readSession() {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(sessionKey()) || "null");
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

function writeSession(value) {
  try {
    window.sessionStorage.setItem(sessionKey(), JSON.stringify({
      ...value,
      saved_at: new Date().toISOString(),
    }));
  } catch {
    // Draft persistence is a convenience. The form stays usable without it.
  }
}

function idempotencyKey(prefix) {
  const suffix = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${suffix}`.slice(0, 178);
}

function fieldText(form, name, limit) {
  const field = form.elements?.namedItem?.(name)
    || form.querySelector?.(`[name="${CSS.escape(name)}"]`);
  return String(field?.value || "")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, limit);
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
  if (typeof factory !== "function") throw new Error("api_runtime_unavailable");
  const api = await Promise.resolve(factory());
  if (!api || typeof api.call !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  return api;
}

function ensureHidden(form, name) {
  let input = form.elements?.namedItem?.(name);
  if (input instanceof HTMLInputElement) return input;
  input = document.createElement("input");
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
    "generation_intake_legacy_strategy_id",
    "generation_intake_source_url",
    "generation_intake_source_id",
    "generation_intake_avatar_wishes",
    "generation_intake_description",
    "generation_intake_state",
    "generation_intake_server_id",
  ].forEach((name) => ensureHidden(form, name));
}

function selectedProductMediaIds(form) {
  return qa('input[name="media_id"]:checked:not(:disabled)', form)
    .map((input) => String(input.value || "").trim().toLowerCase())
    .filter((id) => UUID_PATTERN.test(id));
}

function currentDraft(form, strategyId = null) {
  const state = states.get(form);
  const strategy = generationIntakeStrategy(
    strategyId || state?.strategyId || "",
  );
  if (!strategy) return null;
  const shell = state?.shell;
  const panel = q(
    `[data-generation-intake-panel="${CSS.escape(strategy.strategy_id)}"]`,
    shell,
  );
  const sourceUrl = canonicalGenerationIntakeSourceUrl(
    q('[data-generation-intake-field="source_url"]', panel)?.value,
  );
  const hiddenSourceUrl = String(
    form.elements?.generation_intake_source_url?.value || "",
  );
  const hiddenSourceId = sourceUrl && sourceUrl === hiddenSourceUrl
    ? String(form.elements?.generation_intake_source_id?.value || "")
    : "";
  return createGenerationIntakeDraft(strategy.strategy_id, {
    source_url: sourceUrl,
    source_id: hiddenSourceId,
    avatar_wishes: q(
      '[data-generation-intake-field="avatar_wishes"]',
      panel,
    )?.value,
    description: q(
      '[data-generation-intake-field="description"]',
      panel,
    )?.value,
    product_media_ids: selectedProductMediaIds(form),
  });
}

function storeDraft(form) {
  const state = states.get(form);
  const draft = currentDraft(form);
  if (!state || !draft) return;
  ensureHiddenContract(form);
  form.elements.generation_intake_version.value = GENERATION_INTAKE_VERSION;
  form.elements.generation_intake_strategy_id.value = draft.strategy_id;
  form.elements.generation_intake_legacy_strategy_id.value = draft.legacy_strategy_id;
  form.elements.generation_intake_source_url.value = draft.source_url;
  if (!draft.source_url) form.elements.generation_intake_source_id.value = "";
  form.elements.generation_intake_avatar_wishes.value = draft.avatar_wishes;
  form.elements.generation_intake_description.value = draft.description;
  const validation = validateGenerationIntakeDraft(draft);
  form.elements.generation_intake_state.value = validation.ok
    ? "operator_input_ready"
    : "operator_input_incomplete";
  const internalBrief = generationIntakeInternalBrief(draft);
  const brief = form.elements?.namedItem?.("brief");
  if (
    internalBrief
    && brief instanceof HTMLTextAreaElement
    && state.strategyId !== GENERATION_INTAKE_STRATEGY_IDS.strategy
  ) {
    brief.value = internalBrief;
    brief.dispatchEvent(new Event("input", { bubbles: true }));
  }
  writeSession({
    strategy_id: draft.strategy_id,
    source_url: draft.source_url,
    source_id: draft.source_id,
    avatar_wishes: draft.avatar_wishes,
    description: draft.description,
    product_media_ids: draft.product_media_ids,
  });
  renderState(form);
}

function strategyCard(strategy) {
  const button = element("button", "generation-intake-v2__strategy");
  button.type = "button";
  button.dataset.generationIntakeStrategy = strategy.strategy_id;
  button.setAttribute("aria-pressed", "false");
  button.append(
    element("span", "generation-intake-v2__strategy-number"),
    element("span", "generation-intake-v2__strategy-copy"),
  );
  q(".generation-intake-v2__strategy-number", button).textContent = String(
    GENERATION_INTAKE_STRATEGIES.indexOf(strategy) + 1,
  ).padStart(2, "0");
  const copy = q(".generation-intake-v2__strategy-copy", button);
  copy.append(
    element("strong", "", strategy.public_label),
    element("small", "", strategy.public_summary),
  );
  return button;
}

function fieldLabel(title, hint = "") {
  const label = element("label", "field generation-intake-v2__field");
  label.append(element("span", "", title));
  if (hint) label.append(element("small", "field-hint", hint));
  return label;
}

function createSourceField() {
  const label = fieldLabel(
    "Ссылка на ролик *",
    "YouTube или Shorts. Ссылка фиксирует точный референс; перед анализом система попросит прикрепить законный MP4.",
  );
  const input = document.createElement("input");
  input.type = "url";
  input.inputMode = "url";
  input.autocomplete = "url";
  input.placeholder = "https://youtube.com/shorts/…";
  input.dataset.generationIntakeField = "source_url";
  label.insertBefore(input, q("small", label));
  return label;
}

function createAvatarWishesField() {
  const label = fieldLabel(
    "Каким должен быть аватар *",
    "Опишите внешность, возрастной образ, стиль, одежду, настроение и манеру движения. Не нужно писать технический промпт.",
  );
  const textarea = document.createElement("textarea");
  textarea.rows = 5;
  textarea.maxLength = 1_200;
  textarea.placeholder = "Например: уверенная девушка 25–30 лет, тёмные волосы, минималистичный чёрный образ, спокойная живая мимика…";
  textarea.dataset.generationIntakeField = "avatar_wishes";
  label.insertBefore(textarea, q("small", label));
  return label;
}

function createDescriptionField(copy) {
  const label = fieldLabel(
    "Описание — по желанию",
    copy,
  );
  const textarea = document.createElement("textarea");
  textarea.rows = 4;
  textarea.maxLength = 1_200;
  textarea.placeholder = "Можно оставить пустым — система возьмёт механику ролика без дополнительных изменений.";
  textarea.dataset.generationIntakeField = "description";
  label.insertBefore(textarea, q("small", label));
  return label;
}

function compactPanel(strategy) {
  const section = element("section", "generation-intake-v2__panel");
  section.dataset.generationIntakePanel = strategy.strategy_id;
  section.hidden = true;
  const header = element("header", "generation-intake-v2__panel-head");
  header.append(
    element("div", ""),
    element("span", "badge badge-warning", "Черновик подготовки"),
  );
  const headerCopy = q("div", header);
  headerCopy.append(
    element("p", "eyebrow", "ОТДЕЛЬНАЯ ФОРМА"),
    element("h3", "", strategy.public_label),
    element("p", "", strategy.promise),
  );
  const body = element("div", "generation-intake-v2__panel-body");
  if (strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.avatar) {
    body.append(createAvatarWishesField());
  }
  body.append(createSourceField());
  if (strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy) {
    const product = element("section", "generation-intake-v2__product");
    product.dataset.generationIntakeProductSlot = "";
    product.append(
      element("h4", "", "Фото вашего товара *"),
      element("p", "muted tiny", "Выберите точный товар. Фото исходного товара из ролика система должна получить сама при разборе, а не спрашивать у вас."),
      element("div", "generation-intake-v2__product-slot"),
    );
    body.append(product);
  }
  body.append(createDescriptionField(
    strategy.strategy_id === GENERATION_INTAKE_STRATEGY_IDS.copy
      ? "Укажите только отличия от исходника. Пусто = копировать механику без дополнительных правок."
      : "Можно добавить голос, характер или отдельное ограничение. Пусто = следовать референсу и пожеланию к аватару.",
  ));
  const status = element("div", "generation-intake-v2__status");
  status.dataset.generationIntakeStatus = "";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const actions = element("div", "generation-intake-v2__actions");
  const register = element("button", "btn", "Продолжить к разбору ролика");
  register.type = "button";
  register.dataset.action = "prepare-generation-intake-source";
  const upload = element("a", "btn btn-secondary", "Прикрепить MP4");
  upload.dataset.generationIntakeUpload = "";
  upload.hidden = true;
  actions.append(register, upload);
  section.append(header, body, status, actions);
  return section;
}

function fullPanel(strategy) {
  const section = element("section", "generation-intake-v2__panel generation-intake-v2__panel--full");
  section.dataset.generationIntakePanel = strategy.strategy_id;
  section.hidden = true;
  section.append(
    element("p", "eyebrow", "ПОЛНЫЙ КОНСТРУКТОР"),
    element("h3", "", strategy.public_label),
    element("p", "", strategy.promise),
    element(
      "div",
      "generation-intake-v2__full-note",
      "Ниже остаётся полный рабочий маршрут: товар → площадка → замысел → исходники → модель → бюджет → проверка и запуск.",
    ),
  );
  return section;
}

function buildShell() {
  const shell = element("section", "generation-intake-v2");
  shell.dataset.generationIntakeV2 = "";
  shell.setAttribute("aria-labelledby", "generation-intake-v2-title");
  const header = element("header", "generation-intake-v2__header");
  const copy = element("div", "");
  copy.append(
    element("p", "eyebrow", "СОЗДАНИЕ ВИДЕО"),
    element("h2", "", "Сначала выберите, что именно нужно сделать"),
    element("p", "", "У каждого способа своя форма. Никаких лишних полей из другой задачи."),
  );
  q("h2", copy).id = "generation-intake-v2-title";
  header.append(copy, element("span", "badge", "3 отдельных маршрута"));
  const strategies = element("div", "generation-intake-v2__strategies");
  strategies.setAttribute("role", "group");
  strategies.setAttribute("aria-label", "Способ создания видео");
  GENERATION_INTAKE_STRATEGIES.forEach((strategy) => {
    strategies.append(strategyCard(strategy));
  });
  const panels = element("div", "generation-intake-v2__panels");
  GENERATION_INTAKE_STRATEGIES.forEach((strategy) => {
    panels.append(strategy.form_kind === "compact"
      ? compactPanel(strategy)
      : fullPanel(strategy));
  });
  const globalStatus = element("p", "generation-intake-v2__global-status");
  globalStatus.dataset.generationIntakeGlobalStatus = "";
  globalStatus.setAttribute("role", "status");
  shell.append(header, strategies, panels, globalStatus);
  return shell;
}

function legacySelectionButton(form, legacyStrategyId) {
  return q(
    `[data-generation-strategy-action="SELECT"][data-strategy-id="${CSS.escape(legacyStrategyId)}"]`,
    form,
  );
}

function selectLegacyStrategy(form, strategy) {
  const button = legacySelectionButton(form, strategy.legacy_strategy_id);
  if (!(button instanceof HTMLButtonElement) || button.disabled) return false;
  button.click();
  return true;
}

function locateProductMediaNodes(form) {
  const result = [];
  const seen = new Set();
  qa('input[name="media_id"]', form).forEach((input) => {
    const node = input.closest("label, article, li") || input.parentElement;
    if (!node || seen.has(node)) return;
    seen.add(node);
    result.push(node);
  });
  return result;
}

function moveProductMedia(form, state, intoCompact) {
  const slot = q("[data-generation-intake-product-slot] .generation-intake-v2__product-slot", state.shell);
  if (!slot) return;
  if (intoCompact) {
    const nodes = state.productNodes.length
      ? state.productNodes.map((entry) => entry.node)
      : locateProductMediaNodes(form);
    if (!state.productNodes.length) {
      nodes.forEach((node) => {
        const placeholder = document.createComment("generation-intake-v2-product-placeholder");
        node.before(placeholder);
        state.productNodes.push({ node, placeholder });
      });
    }
    state.productNodes.forEach(({ node }) => slot.append(node));
    if (!state.productNodes.length && !q("[data-generation-intake-empty-product]", slot)) {
      const empty = element("div", "alert alert-warning");
      empty.dataset.generationIntakeEmptyProduct = "";
      empty.textContent = "В проекте пока нет доступного фото товара. Добавьте его в «Файлы», затем вернитесь сюда.";
      const link = element("a", "btn btn-secondary btn-small", "Открыть файлы");
      link.href = hashUrl("/workspace/media", {
        view: "upload",
        project_id: projectId(),
        return_to: window.location.hash,
      });
      slot.append(empty, link);
    }
    return;
  }
  state.productNodes.forEach(({ node, placeholder }) => {
    if (placeholder.isConnected) placeholder.replaceWith(node);
  });
}

function updateCompactChrome(form, state, compact) {
  form.dataset.generationIntakeDisplay = compact ? "compact" : "full";
  const legacyView = q(".generation-strategy-view", form);
  if (legacyView) {
    legacyView.dataset.generationIntakeLegacy = "true";
    legacyView.setAttribute("aria-hidden", "true");
    qa("button, input, select, textarea, a", legacyView).forEach((control) => {
      control.tabIndex = -1;
    });
  }
  if (compact) {
    const modeTarget = q('[data-ce-v4-generation-target="mode"]', form);
    modeTarget?.click?.();
  }
  moveProductMedia(
    form,
    state,
    compact && state.strategyId === GENERATION_INTAKE_STRATEGY_IDS.copy,
  );
}

function uploadHref(source, canonicalUrl) {
  return hashUrl("/workspace/media", {
    view: "upload",
    project_id: projectId(),
    youtube_source: source?.id,
    video_url: canonicalUrl,
    product_name: source?.product_name,
    product_sku: source?.product_sku,
    return_to: hashUrl(ROUTE, {
      project_id: projectId(),
      intake: "v2",
      source_url: canonicalUrl,
    }),
  });
}

function statusCopy(validation, draft) {
  if (!validation.ok) {
    const first = validation.errors[0]?.code;
    const copy = {
      source_url_required: "Добавьте корректную ссылку YouTube или Shorts.",
      product_media_required: "Выберите хотя бы одно точное фото вашего товара.",
      avatar_wishes_required: "Опишите аватара хотя бы одним понятным предложением.",
    };
    return { state: "incomplete", text: copy[first] || "Заполните обязательные поля этой формы." };
  }
  if (!draft.source_id) {
    return {
      state: "ready-to-register",
      text: "Ввод готов. Следующий шаг бесплатный: зарегистрировать точный ролик и прикрепить MP4 для реального разбора кадров и звука.",
    };
  }
  return {
    state: "awaiting-media",
    text: "Ссылка зафиксирована. Прикрепите исходный MP4; до этого ни анализ, ни платная генерация не запускаются.",
  };
}

function renderState(form) {
  const state = states.get(form);
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
  updateCompactChrome(form, state, compact);
  const draft = currentDraft(form);
  const validation = draft ? validateGenerationIntakeDraft(draft) : { ok: false, errors: [] };
  const presentation = statusCopy(validation, draft || {});
  const panel = q(
    `[data-generation-intake-panel="${CSS.escape(strategy.strategy_id)}"]`,
    state.shell,
  );
  const status = q("[data-generation-intake-status]", panel);
  if (status) {
    status.dataset.state = presentation.state;
    status.textContent = presentation.text;
  }
  const register = q('[data-action="prepare-generation-intake-source"]', panel);
  if (register instanceof HTMLButtonElement) {
    register.disabled = !draft?.source_url || state.registering;
    register.textContent = state.registering
      ? "Фиксируем ролик…"
      : draft?.source_id
        ? "Обновить подготовку"
        : "Продолжить к разбору ролика";
  }
  const upload = q("[data-generation-intake-upload]", panel);
  if (upload instanceof HTMLAnchorElement) {
    upload.hidden = !draft?.source_id;
    upload.href = draft?.source_id
      ? uploadHref({
        id: draft.source_id,
        product_name: fieldText(form, "product_name", 300),
        product_sku: fieldText(form, "sku", 160),
      }, draft.source_url)
      : "";
  }
  q("[data-generation-intake-global-status]", state.shell).textContent = compact
    ? "Компактная форма не запускает оплату. Сначала источник проходит подготовку и только потом открывается точный платный запуск."
    : "Полный конструктор использует существующие бюджетные, provider-preflight и QA-защиты.";
}

function restoreDraft(form, state, session) {
  if (!session) return;
  const strategy = generationIntakeStrategy(session.strategy_id);
  if (!strategy) return;
  state.strategyId = strategy.strategy_id;
  const panel = q(
    `[data-generation-intake-panel="${CSS.escape(strategy.strategy_id)}"]`,
    state.shell,
  );
  const source = q('[data-generation-intake-field="source_url"]', panel);
  const wishes = q('[data-generation-intake-field="avatar_wishes"]', panel);
  const description = q('[data-generation-intake-field="description"]', panel);
  if (source) source.value = String(session.source_url || "");
  if (wishes) wishes.value = String(session.avatar_wishes || "");
  if (description) description.value = String(session.description || "");
  ensureHiddenContract(form);
  form.elements.generation_intake_source_url.value = String(session.source_url || "");
  form.elements.generation_intake_source_id.value = UUID_PATTERN.test(
    String(session.source_id || ""),
  ) ? String(session.source_id).toLowerCase() : "";
  selectLegacyStrategy(form, strategy);
}

function savedIntakeResponse(value, draft, source) {
  const root = value?.data && typeof value.data === "object" && !Array.isArray(value.data)
    ? value.data
    : value;
  const intake = root?.intake;
  if (
    root?.ok !== true
    || root?.version !== GENERATION_INTAKE_VERSION
    || !intake
    || !UUID_PATTERN.test(String(intake.id || "").toLowerCase())
    || intake.project_id !== projectId()
    || intake.source_id !== source.id
    || intake.strategy_id !== draft.strategy_id
    || intake.legacy_strategy_id !== draft.legacy_strategy_id
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

async function saveCompactIntake(api, form, state, draft, source) {
  if (!state.intakeIdempotencyKey) {
    state.intakeIdempotencyKey = idempotencyKey(
      `generation-intake-v2-${draft.strategy_id}`,
    );
  }
  const response = await api.call(
    RPC_SAVE_INTAKE,
    payloadWithOrganization(api, {
      project_id: projectId(),
      source_id: source.id,
      strategy_id: draft.strategy_id,
      avatar_wishes: draft.avatar_wishes,
      description: draft.description,
      product_media_ids: draft.product_media_ids,
      idempotency_key: state.intakeIdempotencyKey,
    }),
  );
  const intake = savedIntakeResponse(response, draft, source);
  if (!intake) throw new Error("generation_intake_v2_response_invalid");
  ensureHiddenContract(form);
  form.elements.generation_intake_server_id.value = String(intake.id).toLowerCase();
  form.elements.generation_intake_state.value = String(intake.status || "awaiting_source_media");
  return intake;
}

function sourceResponse(value, canonicalUrl) {
  const root = value?.data && typeof value.data === "object" && !Array.isArray(value.data)
    ? value.data
    : value;
  const source = root?.source;
  const currentProjectId = projectId();
  const videoId = canonicalUrl.slice(-11);
  if (
    root?.ok !== true
    || root?.version !== "exact-youtube-source-intake-v1"
    || !source
    || !UUID_PATTERN.test(String(source.id || "").toLowerCase())
    || source.project_id !== currentProjectId
    || source.video_id !== videoId
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

async function registerSource(form) {
  const state = states.get(form);
  const draft = currentDraft(form);
  if (!state || !draft?.source_url || state.registering) return;
  if (!projectId()) {
    state.error = "Откройте создание из конкретного проекта.";
    renderState(form);
    return;
  }
  state.registering = true;
  state.error = "";
  renderState(form);
  try {
    const api = await getApi();
    const videoId = draft.source_url.slice(-11);
    const response = await api.call(
      RPC_REGISTER_SOURCE,
      payloadWithOrganization(api, {
        project_id: projectId(),
        canonical_url: draft.source_url,
        video_id: videoId,
        product_name: fieldText(form, "product_name", 300),
        product_sku: fieldText(form, "sku", 160),
        idempotency_key: idempotencyKey(`generation-intake-${videoId}`),
      }),
    );
    const source = sourceResponse(response, draft.source_url);
    if (!source) throw new Error("exact_source_response_invalid");
    ensureHiddenContract(form);
    form.elements.generation_intake_source_url.value = draft.source_url;
    form.elements.generation_intake_source_id.value = String(source.id).toLowerCase();
    const exactDraft = createGenerationIntakeDraft(draft.strategy_id, {
      ...draft,
      source_id: source.id,
    });
    await saveCompactIntake(api, form, state, exactDraft, source);
    storeDraft(form);
    const panel = q(
      `[data-generation-intake-panel="${CSS.escape(state.strategyId)}"]`,
      state.shell,
    );
    const upload = q("[data-generation-intake-upload]", panel);
    if (upload instanceof HTMLAnchorElement) {
      upload.hidden = false;
      upload.href = uploadHref(source, draft.source_url);
      upload.focus({ preventScroll: false });
    }
  } catch (error) {
    state.error = String(error?.message || "source_registration_failed");
    const panel = q(
      `[data-generation-intake-panel="${CSS.escape(state.strategyId)}"]`,
      state.shell,
    );
    const status = q("[data-generation-intake-status]", panel);
    if (status) {
      status.dataset.state = "error";
      status.textContent = "Не удалось зафиксировать ролик. Ничего не списано. Проверьте ссылку и повторите.";
    }
  } finally {
    state.registering = false;
    renderState(form);
  }
}

function bind(form, state) {
  state.shell.addEventListener("click", (event) => {
    const strategyButton = event.target.closest?.("[data-generation-intake-strategy]");
    if (strategyButton) {
      const strategy = generationIntakeStrategy(
        strategyButton.dataset.generationIntakeStrategy,
      );
      if (!strategy) return;
      state.strategyId = strategy.strategy_id;
      selectLegacyStrategy(form, strategy);
      storeDraft(form);
      return;
    }
    if (event.target.closest?.('[data-action="prepare-generation-intake-source"]')) {
      registerSource(form);
    }
  });
  state.shell.addEventListener("input", (event) => {
    if (!event.target.closest?.("[data-generation-intake-field]")) return;
    state.intakeIdempotencyKey = "";
    const source = event.target.matches?.('[data-generation-intake-field="source_url"]');
    if (source) {
      ensureHiddenContract(form);
      const canonical = canonicalGenerationIntakeSourceUrl(event.target.value);
      if (canonical !== form.elements.generation_intake_source_url.value) {
        form.elements.generation_intake_source_id.value = "";
      }
    }
    storeDraft(form);
  });
  form.addEventListener("change", (event) => {
    if (event.target.matches?.('input[name="media_id"]')) {
      state.intakeIdempotencyKey = "";
      storeDraft(form);
    }
  });
  form.addEventListener("submit", (event) => {
    const strategy = generationIntakeStrategy(state.strategyId);
    if (!strategy || strategy.form_kind !== "compact") return;
    // Compact routes are preparation flows. Never let the legacy paid submit
    // reinterpret their optional fields as the universal full form.
    event.preventDefault();
    event.stopImmediatePropagation();
    const draft = currentDraft(form);
    const validation = validateGenerationIntakeDraft(draft);
    if (!validation.ok) {
      renderState(form);
      q('[data-generation-intake-field="source_url"]', state.shell)?.focus();
      return;
    }
    registerSource(form);
  }, true);
}

function mountForm(form) {
  if (!(form instanceof HTMLFormElement)) return;
  const existing = states.get(form);
  if (existing && existing.shell.isConnected) {
    renderState(form);
    return;
  }
  const legacyView = q(".generation-strategy-view", form);
  const modePanel = q('[data-ce-v4-generation-panel="mode"]', form)
    || legacyView?.parentElement
    || form;
  if (!legacyView || !modePanel) return;
  const shell = buildShell();
  legacyView.before(shell);
  legacyView.dataset.generationIntakeLegacy = "true";
  legacyView.setAttribute("aria-hidden", "true");
  qa("button, input, select, textarea, a", legacyView).forEach((control) => {
    control.tabIndex = -1;
  });
  ensureHiddenContract(form);
  const state = {
    shell,
    strategyId: "",
    productNodes: [],
    registering: false,
    intakeIdempotencyKey: "",
    error: "",
  };
  states.set(form, state);
  form.setAttribute(BOUND_ATTRIBUTE, GENERATION_INTAKE_VERSION);
  bind(form, state);

  const session = readSession();
  const legacyId = String(form.elements?.generation_strategy_id?.value || "");
  const fromLegacy = generationIntakeStrategyForLegacy(legacyId);
  if (session?.strategy_id) restoreDraft(form, state, session);
  else if (fromLegacy) state.strategyId = fromLegacy.strategy_id;
  renderState(form);
}

function mount() {
  scheduled = false;
  if (routePath() !== ROUTE) return;
  const form = q("#mock-batch-form");
  if (form) mountForm(form);
}

function scheduleMount() {
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(mount);
}

window.addEventListener("hashchange", scheduleMount);
window.addEventListener("contentengine:rendered", scheduleMount);
new MutationObserver(scheduleMount).observe(document.documentElement, {
  childList: true,
  subtree: true,
});
scheduleMount();
