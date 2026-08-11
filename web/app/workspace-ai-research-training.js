/*
 * ContentEngine · Research -> AI Center -> editable recommendations.
 *
 * This route adapter renders a rich, governed training queue. It never trains
 * on receipt arrival alone: the operator chooses analysis blocks and scenario
 * candidates, can edit every recommendation, and confirms one append-only
 * server decision.
 */

const ROUTE = "/workspace/ai";
const RPC_QUEUE = "contentengine_ai_research_training_queue";
const RPC_DECIDE = "contentengine_decide_ai_research_training";
const ROOT_ATTRIBUTE = "data-ai-research-training-root";
const CATEGORY_KEY = "contentengine.ai-research-training.category";
const PROJECT_CONTEXT_KEY = "contentengine.desktop-v4.project";
const GENERATION_INTENT_PREFIX = "contentengine.ai-research-generation.intent.v1:";
const CATEGORIES = Object.freeze([
  ["cosmetics", "Косметика и уход"],
  ["baa", "БАД"],
  ["sports_food", "Спортивное питание"],
  ["food", "Еда и напитки"],
  ["household", "Товары для дома"],
  ["apparel", "Одежда и аксессуары"],
  ["electronics", "Электроника"],
  ["other", "Другая категория"],
]);
const CATEGORY_SET = new Set(CATEGORIES.map(([value]) => value));
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;

const runtime = {
  root: null,
  category: "other",
  projectId: "",
  loading: false,
  loadToken: 0,
  mutating: false,
  requestKey: "",
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

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function clean(value, limit = 4000) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function list(value, limit = 12) {
  return (Array.isArray(value) ? value : [])
    .slice(0, limit)
    .map((item) => {
      if (typeof item === "string") return clean(item, 600);
      if (!item || typeof item !== "object") return "";
      return clean(
        item.label || item.title || item.name || item.text || item.summary
          || item.claim || item.pain || item.objection || JSON.stringify(item),
        600,
      );
    })
    .filter(Boolean);
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function safeUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function unwrap(value) {
  return object(value?.data || value);
}

function normalizedCategory(value) {
  const category = clean(value, 40).toLowerCase();
  return CATEGORY_SET.has(category) ? category : "";
}

function normalizedProjectId(value) {
  const projectId = clean(value, 80).toLowerCase();
  return UUID_PATTERN.test(projectId) ? projectId : "";
}

export function resolveTrainingProjectId({
  routeValues = [],
  storedValue = "",
} = {}) {
  const explicitValues = Array.isArray(routeValues) ? routeValues : [];
  if (explicitValues.length) {
    return explicitValues.length === 1
      ? normalizedProjectId(explicitValues[0])
      : "";
  }
  return normalizedProjectId(storedValue);
}

function storedTrainingProjectId() {
  try {
    const stored = JSON.parse(
      window.sessionStorage.getItem(PROJECT_CONTEXT_KEY) || "null",
    );
    return normalizedProjectId(stored?.id || stored?.project_id);
  } catch {
    return "";
  }
}

function currentTrainingProjectId() {
  return resolveTrainingProjectId({
    routeValues: routeParams().getAll("project_id"),
    storedValue: storedTrainingProjectId(),
  });
}

export function projectScopedTrainingPayload(payload, projectId) {
  const normalized = normalizedProjectId(projectId);
  if (!normalized) throw new Error("project_id_required");
  return { ...object(payload), project_id: normalized };
}

export function projectScopedTrainingSnapshot(value, expectedProjectId) {
  const projectId = normalizedProjectId(expectedProjectId);
  const source = unwrap(value);
  if (!projectId || normalizedProjectId(source.project_id) !== projectId) {
    return null;
  }
  const exactProjectItems = (items) => (Array.isArray(items) ? items : [])
    .filter((item) => normalizedProjectId(item?.project_id) === projectId);
  return {
    ...source,
    project_id: projectId,
    queue: exactProjectItems(source.queue),
    learned: exactProjectItems(source.learned),
  };
}

function categoryLabel(value) {
  const category = normalizedCategory(value) || "other";
  return CATEGORIES.find(([key]) => key === category)?.[1] || "Другая категория";
}

function routeCategory() {
  const params = routeParams();
  return normalizedCategory(
    params.get("category") || params.get("product_category") || "",
  );
}

function legacyCategoryControlVisible(control) {
  if (!control || control.hidden || control.closest?.("[hidden]")) return false;
  if (control.getAttribute?.("aria-hidden") === "true") return false;
  const style = globalThis.window?.getComputedStyle?.(control);
  return !style || (style.display !== "none" && style.visibility !== "hidden");
}

function selectedLegacyCategory() {
  if (typeof document === "undefined") return "";
  const controls = document.querySelectorAll(
    '.ai-learning-category[aria-pressed="true"][data-category-key]',
  );
  for (const control of controls) {
    if (!legacyCategoryControlVisible(control)) continue;
    const category = normalizedCategory(control.dataset?.categoryKey);
    if (category) return category;
  }
  return "";
}

export function resolveTrainingCategory({
  routeValue = "",
  legacyValue = "",
  selectValue = "",
  storedValue = "",
} = {}) {
  return normalizedCategory(routeValue)
    || normalizedCategory(legacyValue)
    || normalizedCategory(selectValue)
    || normalizedCategory(storedValue)
    || "other";
}

function currentCategory() {
  const explicitRouteCategory = routeCategory();
  const visibleLegacyCategory = selectedLegacyCategory();
  const existing = typeof document === "undefined"
    ? null
    : document.querySelector('[data-ai-category-select]');
  const existingValue = normalizedCategory(existing?.value);
  let storedValue = "";
  try {
    storedValue = window.sessionStorage.getItem(CATEGORY_KEY) || "";
  } catch {
    // Optional route memory.
  }
  return resolveTrainingCategory({
    routeValue: explicitRouteCategory,
    legacyValue: visibleLegacyCategory,
    selectValue: existingValue,
    storedValue,
  });
}

function rememberCategory(category) {
  const normalized = normalizedCategory(category);
  if (!normalized) return;
  try {
    window.sessionStorage.setItem(CATEGORY_KEY, normalized);
  } catch {
    // Optional route memory.
  }
}

export function trainingCategoryHash(category, rawHash = "#/workspace/ai") {
  const normalized = normalizedCategory(category) || "other";
  const raw = String(rawHash || "#/workspace/ai").replace(/^#/, "");
  const separator = raw.indexOf("?");
  const rawPath = separator >= 0 ? raw.slice(0, separator) : raw;
  const rawQuery = separator >= 0 ? raw.slice(separator + 1) : "";
  const path = (`/${rawPath || "workspace/ai"}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || ROUTE;
  const params = new URLSearchParams(rawQuery);
  params.set("category", normalized);
  return `#${path}?${params.toString()}`;
}

export function trainingProjectHash(projectId, rawHash = "#/workspace/ai") {
  const normalized = normalizedProjectId(projectId);
  if (!normalized) throw new Error("project_id_required");
  const raw = String(rawHash || "#/workspace/ai").replace(/^#/, "");
  const separator = raw.indexOf("?");
  const rawPath = separator >= 0 ? raw.slice(0, separator) : raw;
  const rawQuery = separator >= 0 ? raw.slice(separator + 1) : "";
  const path = (`/${rawPath || "workspace/ai"}`)
    .replace(/\/{2,}/gu, "/")
    .replace(/\/$/u, "") || ROUTE;
  const params = new URLSearchParams(rawQuery);
  params.delete("project_id");
  params.set("project_id", normalized);
  return `#${path}?${params.toString()}`;
}

function canonicalizeTrainingRoute(category, projectId) {
  if (typeof window === "undefined") return false;
  const routeProjectValues = routeParams().getAll("project_id");
  if (
    routeProjectValues.length === 1
    && normalizedProjectId(routeProjectValues[0]) === projectId
  ) return false;
  if (routeProjectValues.length) return false;
  const categoryHash = trainingCategoryHash(category, window.location.hash);
  const nextHash = trainingProjectHash(projectId, categoryHash);
  window.history?.replaceState?.(window.history.state, "", nextHash);
  return true;
}

function syncLegacyCategoryButtons(category) {
  if (typeof document === "undefined") return;
  document.querySelectorAll(
    ".ai-learning-category[data-category-key]",
  ).forEach((control) => {
    const selected = normalizedCategory(control.dataset?.categoryKey) === category;
    control.setAttribute("aria-pressed", selected ? "true" : "false");
    control.classList?.toggle("is-active", selected);
  });
}

function syncTrainingCategorySelect(category) {
  const select = runtime.root?.querySelector("[data-training-category]");
  if (select instanceof HTMLSelectElement && select.value !== category) {
    select.value = category;
  }
}

function updateCategoryRoute(category) {
  const nextHash = trainingCategoryHash(category, window.location.hash);
  if (nextHash === window.location.hash) return false;
  window.location.hash = nextHash;
  return true;
}

function restoreProjectScopeAfterLegacyNavigation(category, projectId) {
  if (!projectId || typeof window === "undefined") return;
  const params = routeParams();
  if (params.get("project_id") === projectId && routeCategory() === category) {
    return;
  }
  const nextHash = trainingCategoryHash(category, window.location.hash);
  const separator = nextHash.indexOf("?");
  const path = separator >= 0 ? nextHash.slice(0, separator) : nextHash;
  const nextParams = new URLSearchParams(
    separator >= 0 ? nextHash.slice(separator + 1) : "",
  );
  nextParams.set("project_id", projectId);
  const restoredHash = `${path}?${nextParams.toString()}`;
  window.history?.replaceState?.(window.history.state, "", restoredHash);
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
  if (typeof factory !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  const api = await Promise.resolve(factory());
  if (!api || typeof api.call !== "function") {
    throw new Error("api_runtime_unavailable");
  }
  return api;
}

function idempotencyKey(prefix) {
  const uuid = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${uuid}`.slice(0, 178);
}

function setStatus(root, message, tone = "neutral") {
  const target = root.querySelector("[data-ai-research-training-status]");
  if (!target) return;
  target.textContent = message;
  target.dataset.tone = tone;
}

function addTextList(parent, values, emptyText = "Нет подтверждённых пунктов") {
  const items = list(values);
  if (!items.length) {
    parent.append(el("p", "ai-research-training__empty-copy", emptyText));
    return;
  }
  const ul = el("ul", "ai-research-training__bullets");
  items.forEach((item) => ul.append(el("li", "", item)));
  parent.append(ul);
}

function insightCard({ key, title, description, content }) {
  const label = el("label", "ai-research-training__insight");
  const checkbox = el("input");
  checkbox.type = "checkbox";
  // Analysis blocks are suggestions too; approval requires a human check.
  checkbox.checked = false;
  checkbox.dataset.insightKey = key;
  const body = el("span", "ai-research-training__insight-body");
  const head = el("span", "ai-research-training__insight-title");
  head.append(el("strong", "", title), el("small", "", description));
  const detail = el("span", "ai-research-training__insight-detail");
  if (typeof content === "string") detail.textContent = content;
  else if (content instanceof Node) detail.append(content);
  body.append(head, detail);
  label.append(checkbox, body);
  return label;
}

function categoryInsight(analysis) {
  const category = object(analysis.category_analysis);
  const block = el("span");
  const summary = clean(category.definition || category.summary || category.category_name, 900);
  if (summary) block.append(el("span", "", summary));
  const jobs = list(category.buyer_jobs || category.jobs, 6);
  if (jobs.length) {
    const jobsLine = el("small", "");
    jobsLine.textContent = `Задачи покупателя: ${jobs.join(" · ")}`;
    block.append(jobsLine);
  }
  return insightCard({
    key: "category",
    title: "Категория и покупатель",
    description: "Что человек пытается решить товаром",
    content: block,
  });
}

function competitorInsight(analysis) {
  const competitors = object(analysis.competitor_analysis);
  const block = el("span");
  const reusable = list(
    competitors.reusable_structures || competitors.content_gaps
      || competitors.opportunities,
    6,
  );
  const saturated = list(competitors.saturated_patterns, 4);
  if (reusable.length) {
    const line = el("span");
    line.textContent = `Можно использовать: ${reusable.join(" · ")}`;
    block.append(line);
  }
  if (saturated.length) {
    const line = el("small");
    line.textContent = `Не повторять вслепую: ${saturated.join(" · ")}`;
    block.append(line);
  }
  return insightCard({
    key: "competitors",
    title: "Конкуренты и насыщенные приёмы",
    description: "Структуры для адаптации, а не копирования",
    content: block,
  });
}

function trendInsight(analysis) {
  const trends = object(analysis.trend_analysis);
  const signals = Array.isArray(trends.signals) ? trends.signals.slice(0, 6) : [];
  const block = el("span");
  if (signals.length) {
    const ul = el("ul", "ai-research-training__compact-list");
    signals.forEach((signal) => {
      const source = object(signal);
      const name = clean(source.name || source.signal || source.title, 260);
      const direction = clean(source.direction, 80);
      const use = clean(source.recommended_use || source.use, 240);
      if (!name && !use) return;
      ul.append(el(
        "li",
        "",
        [name, direction && `(${direction})`, use].filter(Boolean).join(" — "),
      ));
    });
    block.append(ul);
  }
  return insightCard({
    key: "trends",
    title: "Тренды и свежие сигналы",
    description: "Только подтверждённые или честно помеченные гипотезы",
    content: block,
  });
}

function briefInsight(brief) {
  const block = el("span");
  const audience = list(brief.audience, 4);
  const pains = list(brief.pains, 4);
  const objections = list(brief.objections, 4);
  const lines = [
    audience.length ? `Аудитория: ${audience.join(" · ")}` : "",
    pains.length ? `Боли: ${pains.join(" · ")}` : "",
    objections.length ? `Возражения: ${objections.join(" · ")}` : "",
  ].filter(Boolean);
  lines.forEach((line, index) => block.append(el(index ? "small" : "span", "", line)));
  return insightCard({
    key: "brief",
    title: "Коммуникационная рамка",
    description: "Аудитория, боли, возражения и доказательства",
    content: block,
  });
}

function shotListText(value) {
  if (typeof value === "string") return value.trim();
  if (!Array.isArray(value)) return "";
  return value.slice(0, 12).map((shot) => {
    if (typeof shot === "string") return shot.trim();
    const source = object(shot);
    const seconds = clean(source.seconds || source.time || source.duration, 60);
    const visual = clean(source.visual || source.shot || source.description, 700);
    const text = clean(source.on_screen_text || source.text, 300);
    return [seconds && `${seconds}:`, visual, text && `Текст: ${text}`]
      .filter(Boolean)
      .join(" ");
  }).filter(Boolean).join("\n");
}

function field(labelText, value, name, { textarea = false, rows = 2 } = {}) {
  const label = el("label", "field ai-research-training__edit-field");
  label.append(el("span", "", labelText));
  const control = el(textarea ? "textarea" : "input");
  control.name = name;
  control.value = String(value || "");
  if (textarea) control.rows = rows;
  control.maxLength = textarea ? 5000 : 1500;
  label.append(control);
  return label;
}

function scenarioCard(scenario, position) {
  const source = object(scenario);
  const card = el("article", "ai-research-training__scenario");
  card.dataset.scenarioPosition = String(position);
  const header = el("header", "ai-research-training__scenario-header");
  const select = el("label", "ai-research-training__scenario-select");
  const checkbox = el("input");
  checkbox.type = "checkbox";
  // Every recommendation is advisory: even position 1 waits for a human choice.
  checkbox.checked = false;
  checkbox.dataset.scenarioSelect = String(position);
  select.append(
    checkbox,
    el("strong", "", `Рекомендация ${position}`),
  );
  const mode = clean(source.recommended_generation_mode, 80);
  header.append(select, el("span", "ai-research-training__scenario-mode", mode || "сценарий"));

  const grid = el("div", "ai-research-training__scenario-grid");
  grid.append(
    field("Название", source.title, "title"),
    field("Хук", source.hook, "hook", { textarea: true, rows: 2 }),
    field(
      "Реплика / сценарий",
      source.spoken_script || source.script,
      "spoken_script",
      { textarea: true, rows: 4 },
    ),
    field(
      "Кадры",
      shotListText(source.shot_list || source.shots),
      "shot_list",
      { textarea: true, rows: 5 },
    ),
    field("Ключевое сообщение", source.goal || source.angle, "key_message", { textarea: true, rows: 2 }),
    field("Визуальное направление", source.angle, "visual_direction", { textarea: true, rows: 2 }),
    field("CTA", source.cta, "cta", { textarea: true, rows: 2 }),
  );
  const evidence = el("div", "ai-research-training__scenario-evidence");
  const proof = list(source.proof_points, 6);
  const risks = list(source.risks, 6);
  if (proof.length) evidence.append(el("p", "", `Доказательства: ${proof.join(" · ")}`));
  if (risks.length) evidence.append(el("p", "", `Ограничения: ${risks.join(" · ")}`));
  card.append(header, grid, evidence);
  return card;
}

function sourceCard(source) {
  const item = object(source);
  const card = el("article", "ai-research-training__source");
  const externalUrl = safeUrl(
    item.source_url || item.preview_url || item.media_url || item.download_url,
  );
  const projectId = clean(item.project_id, 80).toLowerCase();
  const mediaId = clean(item.media_object_id, 80).toLowerCase();
  const projectFileUrl = UUID_PATTERN.test(projectId) && UUID_PATTERN.test(mediaId)
    ? `#/workspace/board?project_id=${encodeURIComponent(projectId)}&folder=all`
    : "";
  const url = externalUrl || projectFileUrl;
  const title = clean(item.title, 300) || "Источник исследования";
  const heading = url ? el("a", "", title) : el("strong", "", title);
  if (url) {
    heading.href = url;
    if (externalUrl) {
      heading.target = "_blank";
      heading.rel = "noopener noreferrer";
    }
  }
  const meta = el("small", "", [
    clean(item.source_type, 80),
    clean(item.trust_level, 80),
    item.media_object_id ? "файл проекта" : "",
  ].filter(Boolean).join(" · "));
  card.append(heading, meta);
  const analysis = object(item.analysis);
  const summary = clean(analysis.summary, 1000);
  if (summary) card.append(el("p", "", summary));
  const signals = list(analysis.structural_signal_keys, 8);
  if (signals.length) card.append(el("small", "", `Сигналы: ${signals.join(" · ")}`));
  if (!summary && externalUrl) {
    card.append(el(
      "p",
      "ai-research-training__source-limit",
      "Ссылка сохранена. Показываем только реально доступный разбор; кадры или расшифровку не выдумываем.",
    ));
  }
  return card;
}

function normalizeLearnedSource(value) {
  const source = object(value);
  const media = object(source.media);
  return {
    ...source,
    title: firstText(
      source.title,
      media.filename,
      source.filename,
      "Источник исследования",
    ),
    media_object_id: firstText(
      source.media_object_id,
      media.media_object_id,
    ),
    project_id: firstText(source.project_id, media.project_id),
    mime_type: firstText(source.mime_type, media.mime_type),
    status: firstText(source.status, media.status),
  };
}

function mergeLearnedSources(source) {
  const candidates = [
    source.source_snapshot,
    source.material_snapshot,
    source.sources,
    source.materials,
    source.material,
  ].flatMap((value) => (Array.isArray(value) ? value : []));
  const merged = new Map();
  candidates.forEach((value, index) => {
    const normalized = normalizeLearnedSource(value);
    const key = firstText(
      normalized.source_id,
      normalized.media_object_id,
      normalized.source_url,
      `${normalized.title}:${index}`,
    );
    const existing = merged.get(key);
    merged.set(key, existing
      ? {
          ...existing,
          ...normalized,
          analysis: {
            ...object(existing.analysis),
            ...object(normalized.analysis),
          },
        }
      : normalized);
  });
  return [...merged.values()].slice(0, 24);
}

function firstText(...values) {
  for (const value of values) {
    if (typeof value === "string" || typeof value === "number") {
      const result = clean(value, 2000);
      if (result) return result;
    }
  }
  return "";
}

function normalizeResearchSummary(value) {
  if (typeof value === "string") {
    return { headline: clean(value, 2000), conclusions: [], limitations: [] };
  }
  const source = object(value);
  return {
    headline: firstText(
      source.executive_summary,
      source.summary,
      source.overview,
      source.result,
      source.conclusion,
    ),
    conclusions: list(
      source.conclusions || source.key_findings || source.findings
        || source.results || source.takeaways,
      12,
    ),
    limitations: list(source.limitations || source.caveats, 8),
  };
}

function normalizeResearchForecast(value) {
  const initial = Array.isArray(value)
    ? value.find((item) => item && typeof item === "object" && !Array.isArray(item))
    : value;
  const source = object(initial);
  const nestedForecast = object(source.forecast);
  const nested = Object.keys(source).length === 1
    && Object.keys(nestedForecast).length
    ? object(source.forecast)
    : source;
  const factors = object(nested.factors);
  const scoreNumber = Number(nested.score);
  const confidenceNumber = Number(nested.confidence);
  const forecast = {
    score: Number.isFinite(scoreNumber) ? scoreNumber : null,
    confidence: Number.isFinite(confidenceNumber) ? confidenceNumber : null,
    summary: firstText(
      nested.summary,
      nested.forecast_summary,
      nested.explanation,
      nested.reason,
    ),
    strengths: list(factors.strengths || nested.strengths, 8),
    risks: list(factors.risks || nested.risks, 8),
    limitations: list(nested.limitations, 8),
  };
  return forecast.score !== null
    || forecast.confidence !== null
    || forecast.summary
    || forecast.strengths.length
    || forecast.risks.length
    || forecast.limitations.length
    ? forecast
    : null;
}

function normalizeLearnedRecommendation(value, index) {
  const source = object(value);
  return {
    position: Number(source.position) || index + 1,
    title: firstText(source.title, `Рекомендация ${index + 1}`),
    platform: clean(source.platform, 80),
    generationMode: clean(
      source.recommended_generation_mode || source.generation_mode,
      80,
    ),
    hook: firstText(source.hook),
    keyMessage: firstText(source.key_message, source.goal, source.angle),
    spokenScript: firstText(source.spoken_script, source.script),
    shotList: shotListText(source.shot_list || source.shots),
    visualDirection: firstText(source.visual_direction, source.angle),
    cta: firstText(source.cta),
    proofPoints: list(source.proof_points, 8),
    avoidClaims: list(source.avoid_claims || source.risks, 8),
  };
}

function safeWorkspaceDeepLink(value) {
  const href = String(value || "").trim();
  return /^#\/workspace\/[a-z0-9/_-]+(?:\?[^\s#]*)?$/iu.test(href)
    ? href
    : "";
}

export function normalizeLearnedResearch(item) {
  const source = object(item);
  const rawSources = mergeLearnedSources(source);
  const rawRecommendations = Array.isArray(source.recommendations)
    ? source.recommendations
    : [];
  const summaryValue = source.research_summary
    ?? source.summary
    ?? object(source.run).summary;
  const forecastValue = source.research_forecast
    ?? source.forecast
    ?? source.forecasts;
  return {
    selectionId: clean(source.selection_id, 80),
    projectId: normalizedProjectId(source.project_id),
    title: clean(source.product_name, 300)
      || clean(source.research_title, 300)
      || "Исследование",
    productSku: clean(source.product_sku, 120),
    category: normalizedCategory(source.product_category),
    decision: source.decision === "approve" ? "approve" : "reject",
    selectedAt: clean(source.selected_at, 80),
    selectedInsights: (Array.isArray(source.selected_insight_keys)
      ? source.selected_insight_keys
      : [])
      .map((value) => clean(value, 80).toLowerCase())
      .filter(Boolean),
    selectedScenarioPositions: (Array.isArray(source.selected_scenario_positions)
      ? source.selected_scenario_positions
      : [])
      .map(Number)
      .filter((value) => Number.isInteger(value) && value >= 1 && value <= 3),
    sources: rawSources,
    analysis: object(source.analysis_snapshot || source.analysis),
    summary: normalizeResearchSummary(summaryValue),
    forecast: normalizeResearchForecast(forecastValue),
    recommendations: rawRecommendations
      .slice(0, 3)
      .map(normalizeLearnedRecommendation),
    operatorNotes: clean(source.operator_notes, 1200),
    deepLink: safeWorkspaceDeepLink(source.deep_link),
  };
}

function learnedSection(title, className = "") {
  const section = el(
    "section",
    `ai-research-training__learned-section${className ? ` ${className}` : ""}`,
  );
  section.append(el("h5", "", title));
  return section;
}

function analysisSnapshotCard(title, value, { summaryKeys = [], listKeys = [] } = {}) {
  const source = object(value);
  const card = el("article", "ai-research-training__snapshot-card");
  card.append(el("strong", "", title));
  const summary = firstText(...summaryKeys.map((key) => source[key]));
  if (summary) card.append(el("p", "", summary));
  const items = [];
  listKeys.forEach(([key, label]) => {
    list(source[key], 6).forEach((item) => items.push(`${label}: ${item}`));
  });
  if (items.length) addTextList(card, items);
  if (!summary && !items.length) {
    card.append(el("p", "ai-research-training__empty-copy", "Сервер не вернул содержимое этого блока."));
  }
  return card;
}

function learnedAnalysisSection(analysis) {
  const section = learnedSection("Выводы ИИ", "ai-research-training__learned-analysis");
  const grid = el("div", "ai-research-training__snapshot-grid");
  grid.append(
    analysisSnapshotCard("Категория и покупатель", analysis.category_analysis, {
      summaryKeys: ["definition", "summary", "category_name"],
      listKeys: [["buyer_jobs", "Задачи"], ["jobs", "Задачи"]],
    }),
    analysisSnapshotCard("Конкуренты", analysis.competitor_analysis, {
      summaryKeys: ["summary", "conclusion"],
      listKeys: [
        ["reusable_structures", "Можно использовать"],
        ["content_gaps", "Пробелы"],
        ["saturated_patterns", "Не копировать"],
      ],
    }),
    analysisSnapshotCard("Тренды", analysis.trend_analysis, {
      summaryKeys: ["summary", "conclusion"],
      listKeys: [["signals", "Сигнал"], ["limitations", "Ограничение"]],
    }),
    analysisSnapshotCard("Итоговая рамка", analysis.creative_brief, {
      summaryKeys: ["summary", "key_message"],
      listKeys: [
        ["audience", "Аудитория"],
        ["pains", "Боли"],
        ["objections", "Возражения"],
        ["facts", "Факты"],
        ["claims", "Ограничения обещаний"],
      ],
    }),
    analysisSnapshotCard("Рекомендованный следующий шаг", analysis.guidance, {
      summaryKeys: ["reason", "recommended_next_step", "summary"],
      listKeys: [["questions", "Проверить"], ["actions", "Действие"]],
    }),
  );
  section.append(grid);
  return section;
}

function generationRecommendationDeepLink(learned, recommendation, intent = "") {
  const selectionId = String(learned?.selectionId || "").trim().toLowerCase();
  const projectId = normalizedProjectId(learned?.projectId);
  const position = Number(recommendation?.position);
  if (
    !projectId
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u
      .test(selectionId)
    || ![1, 2, 3].includes(position)
  ) return "";
  const params = new URLSearchParams({
    project_id: projectId,
    selection_id: selectionId,
    recommendation_position: String(position),
  });
  if (UUID_PATTERN.test(intent)) params.set("recommendation_intent", intent);
  return `#/workspace/generation?${params.toString()}`;
}

function armGenerationRecommendationIntent(learned, recommendation) {
  const selectionId = String(learned?.selectionId || "").trim().toLowerCase();
  const position = Number(recommendation?.position);
  if (
    !UUID_PATTERN.test(selectionId)
    || ![1, 2, 3].includes(position)
    || typeof globalThis.crypto?.randomUUID !== "function"
  ) return "";
  const intent = globalThis.crypto.randomUUID().toLowerCase();
  if (!UUID_PATTERN.test(intent)) return "";
  try {
    globalThis.localStorage?.setItem(
      `${GENERATION_INTENT_PREFIX}${intent}`,
      JSON.stringify({ selectionId, recommendationPosition: position, createdAt: Date.now() }),
    );
    return intent;
  } catch {
    return "";
  }
}

function learnedRecommendationCard(recommendation, learned) {
  const card = el("article", "ai-research-training__learned-recommendation");
  const head = el("header", "");
  head.append(
    el("strong", "", recommendation.title),
    el(
      "small",
      "",
      [recommendation.platform, recommendation.generationMode]
        .filter(Boolean)
        .join(" · ") || `Вариант ${recommendation.position}`,
    ),
  );
  card.append(head);
  [
    ["Хук", recommendation.hook],
    ["Ключевое сообщение", recommendation.keyMessage],
    ["Реплика / сюжет", recommendation.spokenScript],
    ["Кадры", recommendation.shotList],
    ["Визуальное направление", recommendation.visualDirection],
    ["CTA", recommendation.cta],
    ["Доказательства", recommendation.proofPoints.join(" · ")],
    ["Не обещать / учесть", recommendation.avoidClaims.join(" · ")],
  ].forEach(([label, value]) => {
    if (!value) return;
    const line = el("p", "");
    line.append(el("b", "", `${label}: `), document.createTextNode(value));
    card.append(line);
  });
  card.append(el(
    "small",
    "ai-research-training__editable-note",
    "Это сохранённая редактируемая рекомендация. Ссылка передаёт только номер серверного отбора и позицию; категорию и товар «Создать» заново проверит на сервере.",
  ));
  const createHref = generationRecommendationDeepLink(learned, recommendation);
  if (learned?.decision === "approve" && createHref) {
    const action = el(
      "a",
      "btn btn-secondary btn-small",
      "Использовать этот вариант в «Создать»",
    );
    action.href = createHref;
    action.dataset.aiResearchGenerationSelection = learned.selectionId;
    action.dataset.aiResearchGenerationPosition = String(
      recommendation.position,
    );
    action.addEventListener("click", () => {
      const intent = armGenerationRecommendationIntent(learned, recommendation);
      if (intent) {
        action.href = generationRecommendationDeepLink(learned, recommendation, intent);
      }
    });
    card.append(action);
  }
  return card;
}

function receiptCard(item, canDecide) {
  const source = object(item);
  const card = el("details", "ai-research-training__receipt");
  card.open = true;
  card.dataset.receiptId = clean(source.receipt_id, 80);
  card.dataset.receiptHash = clean(source.receipt_hash, 80);
  card.dataset.projectId = normalizedProjectId(source.project_id);

  const summary = el("summary", "ai-research-training__receipt-summary");
  const titleBox = el("span");
  titleBox.append(
    el("strong", "", clean(source.product_name, 300) || "Исследование"),
    el("small", "", [
      clean(source.project_name, 180),
      clean(source.product_sku, 100),
      `${Number(source.source_count) || 0} источников`,
    ].filter(Boolean).join(" · ")),
  );
  const state = el(
    "span",
    "ai-research-training__receipt-state",
    source.review_state === "approved_waiting_for_learning_selection"
      ? "Проверено · выберите знания"
      : "Нужен отбор",
  );
  summary.append(titleBox, state);

  const body = el("div", "ai-research-training__receipt-body");
  const sourcesSection = el("section", "ai-research-training__section");
  sourcesSection.append(el("h4", "", "1. Источники и разбор ролика"));
  const sourcesGrid = el("div", "ai-research-training__sources");
  const sources = Array.isArray(source.sources) ? source.sources : [];
  if (sources.length) sources.slice(0, 12).forEach((entry) => sourcesGrid.append(sourceCard(entry)));
  else sourcesGrid.append(el("p", "ai-research-training__empty-copy", "Источники ещё не прикреплены к завершённому разбору."));
  sourcesSection.append(sourcesGrid);

  const insightSection = el("section", "ai-research-training__section");
  insightSection.append(
    el("h4", "", "2. Что именно взять в обучение"),
    el("p", "muted", "Снимите галочку с блока, который не должен влиять на рекомендации."),
  );
  const insights = el("div", "ai-research-training__insights");
  const analysis = object(source.analysis);
  const brief = object(source.creative_brief);
  insights.append(
    categoryInsight(analysis),
    competitorInsight(analysis),
    trendInsight(analysis),
    briefInsight(brief),
  );
  insightSection.append(insights);

  const scenarioSection = el("section", "ai-research-training__section");
  scenarioSection.append(
    el("h4", "", "3. Рекомендации, которые получит генерация"),
    el("p", "muted", "Отметьте варианты и поправьте текст прямо здесь. Эти правки станут утверждённой версией."),
  );
  const scenarios = el("div", "ai-research-training__scenarios");
  const scenarioItems = Array.isArray(source.scenarios) ? source.scenarios.slice(0, 3) : [];
  if (scenarioItems.length) {
    scenarioItems.forEach((scenario, index) => scenarios.append(scenarioCard(scenario, index + 1)));
  } else {
    scenarios.append(el("p", "ai-research-training__empty-copy", "В исследовании нет пригодных сценариев. Такой результат нельзя обучить как рекомендацию."));
  }
  scenarioSection.append(scenarios);

  const controls = el("footer", "ai-research-training__controls");
  const notes = field("Комментарий к отбору (необязательно)", "", "operator_notes", { textarea: true, rows: 2 });
  notes.classList.add("ai-research-training__notes");
  const confirmation = el("label", "check-row ai-research-training__confirmation");
  const confirmationInput = el("input");
  confirmationInput.type = "checkbox";
  confirmationInput.dataset.trainingConfirmation = "true";
  confirmation.append(
    confirmationInput,
    el("span", "", "Я проверила разбор и понимаю, какие выводы станут рекомендациями ИИ."),
  );
  const actions = el("div", "ai-research-training__actions");
  const reject = el("button", "btn btn-secondary", "Не использовать");
  reject.type = "button";
  reject.dataset.trainingDecision = "reject";
  const approve = el("button", "btn", "Обучить на выбранном и сохранить рекомендации");
  approve.type = "button";
  approve.dataset.trainingDecision = "approve";
  approve.disabled = !canDecide || !scenarioItems.length;
  reject.disabled = !canDecide;
  actions.append(reject, approve);
  controls.append(notes, confirmation, actions);

  body.append(sourcesSection, insightSection, scenarioSection, controls);
  card.append(summary, body);
  return card;
}

function learnedCard(item) {
  const learned = normalizeLearnedResearch(item);
  const card = el("details", "ai-research-training__learned-card");
  card.dataset.selectionId = learned.selectionId;

  const summary = el("summary", "ai-research-training__learned-summary");
  const head = el("span");
  head.append(
    el("strong", "", learned.title),
    el("small", "", [
      learned.productSku,
      learned.category ? categoryLabel(learned.category) : "",
      learned.selectedAt,
    ].filter(Boolean).join(" · ")),
  );
  const state = el(
    "span",
    "ai-research-training__learned-state",
    learned.decision === "approve"
      ? `Используется · ${learned.recommendations.length} рекомендац.`
      : "Отклонено",
  );
  summary.append(head, state);

  const body = el("div", "ai-research-training__learned-body");

  const material = learnedSection("Материал и источники");
  const sourcesGrid = el("div", "ai-research-training__sources");
  if (learned.sources.length) {
    learned.sources.forEach((source) => sourcesGrid.append(sourceCard(source)));
  } else {
    sourcesGrid.append(el(
      "p",
      "ai-research-training__empty-copy",
      "Снимок материалов отсутствует в ответе сервера.",
    ));
  }
  material.append(sourcesGrid);

  const results = learnedSection("Итоги исследования");
  if (learned.summary.headline) results.append(el("p", "", learned.summary.headline));
  if (learned.summary.conclusions.length) {
    results.append(el("strong", "", "Итоговые выводы"));
    addTextList(results, learned.summary.conclusions);
  }
  if (learned.summary.limitations.length) {
    results.append(el("strong", "", "Ограничения"));
    addTextList(results, learned.summary.limitations);
  }
  if (
    !learned.summary.headline
    && !learned.summary.conclusions.length
    && !learned.summary.limitations.length
  ) {
    results.append(el(
      "p",
      "ai-research-training__empty-copy",
      "Общий итог исследования отсутствует в ответе сервера; сохранённые блоки анализа показаны ниже.",
    ));
  }

  if (learned.forecast) {
    const forecast = learnedSection("Прогноз и уверенность");
    const forecastMeta = [
      learned.forecast.score !== null ? `оценка ${learned.forecast.score}` : "",
      learned.forecast.confidence !== null
        ? `уверенность ${Math.round(
          learned.forecast.confidence <= 1
            ? learned.forecast.confidence * 100
            : learned.forecast.confidence,
        )}%`
        : "",
    ].filter(Boolean).join(" · ");
    if (forecastMeta) forecast.append(el("strong", "", forecastMeta));
    if (learned.forecast.summary) forecast.append(el("p", "", learned.forecast.summary));
    if (learned.forecast.strengths.length) {
      forecast.append(el("small", "", `Сильные стороны: ${learned.forecast.strengths.join(" · ")}`));
    }
    if (learned.forecast.risks.length) {
      forecast.append(el("small", "", `Риски: ${learned.forecast.risks.join(" · ")}`));
    }
    if (learned.forecast.limitations.length) {
      forecast.append(el("small", "", `Ограничения: ${learned.forecast.limitations.join(" · ")}`));
    }
    results.append(forecast);
  }

  const selection = learnedSection("Что выбрано для обучения");
  const insightLabels = {
    category: "Категория и покупатель",
    competitors: "Конкуренты",
    trends: "Тренды",
    brief: "Коммуникационная рамка",
  };
  const chips = el("div", "ai-research-training__learned-chips");
  learned.selectedInsights.forEach((key) => {
    chips.append(el("span", "", insightLabels[key] || key));
  });
  learned.selectedScenarioPositions.forEach((position) => {
    chips.append(el("span", "", `Сценарий ${position}`));
  });
  if (chips.childNodes.length) selection.append(chips);
  else selection.append(el("p", "ai-research-training__empty-copy", "Состав отбора не указан."));
  if (learned.operatorNotes) {
    selection.append(el("p", "", `Комментарий: ${learned.operatorNotes}`));
  }

  const recommendations = learnedSection("Сохранённые редактируемые рекомендации");
  const recommendationGrid = el("div", "ai-research-training__learned-recommendations");
  if (learned.recommendations.length) {
    learned.recommendations.forEach((recommendation) => {
      recommendationGrid.append(
        learnedRecommendationCard(recommendation, learned),
      );
    });
  } else {
    recommendationGrid.append(el(
      "p",
      "ai-research-training__empty-copy",
      learned.decision === "approve"
        ? "Сервер не вернул сохранённые рекомендации."
        : "Отклонённое исследование не влияет на рекомендации.",
    ));
  }
  recommendations.append(recommendationGrid);

  body.append(material, results, learnedAnalysisSection(learned.analysis), selection, recommendations);
  if (learned.deepLink) {
    const link = el("a", "btn btn-secondary btn-small", "Открыть исходное исследование");
    link.href = learned.deepLink;
    body.append(link);
  }
  card.append(summary, body);
  return card;
}

function renderSnapshot(root, snapshot, expectedProjectId = runtime.projectId) {
  const source = projectScopedTrainingSnapshot(snapshot, expectedProjectId);
  if (!source) return false;
  const queue = Array.isArray(source.queue) ? source.queue : [];
  const learned = Array.isArray(source.learned) ? source.learned : [];
  const capabilities = object(source.capabilities);
  const selectedCategory = normalizedCategory(source.product_category)
    || normalizedCategory(runtime.category)
    || "other";
  const selectedCategoryLabel = categoryLabel(selectedCategory);
  const queueHost = root.querySelector("[data-ai-research-training-queue]");
  const historyHost = root.querySelector("[data-ai-research-training-history]");
  if (!queueHost || !historyHost) return;
  queueHost.replaceChildren();
  historyHost.replaceChildren();

  if (!queue.length) {
    const empty = el("div", "ai-research-training__empty");
    empty.append(
      el("strong", "", `В категории «${selectedCategoryLabel}» нет исследований для отбора`),
      el("p", "", "Сначала завершите анализ ролика в «Исследованиях». После этого здесь появятся источники, разбор и варианты рекомендаций."),
    );
    const link = el("a", "btn btn-secondary btn-small", "Открыть Исследования");
    link.href = `#/workspace/research?project_id=${encodeURIComponent(source.project_id)}`;
    empty.append(link);
    queueHost.append(empty);
  } else {
    queue.forEach((item) => queueHost.append(receiptCard(item, capabilities.can_decide === true)));
  }

  if (!learned.length) {
    historyHost.append(el(
      "p",
      "ai-research-training__empty-copy",
      `В категории «${selectedCategoryLabel}» пока нет сохранённых отборов.`,
    ));
  } else {
    learned.slice(0, 12).forEach((item) => historyHost.append(learnedCard(item)));
  }

  const oldInbox = document.querySelector(".ai-learning-research-inbox");
  if (oldInbox instanceof HTMLElement) {
    oldInbox.hidden = true;
    oldInbox.dataset.replacedByResearchTraining = "true";
  }
  setStatus(
    root,
    queue.length
      ? `Категория «${selectedCategoryLabel}»: исследований для отбора — ${queue.length}.`
      : `Категория «${selectedCategoryLabel}»: очередь пуста — ждём завершённое исследование.`,
    queue.length ? "ready" : "neutral",
  );
  root.dataset.renderedProjectId = expectedProjectId;
  root.dataset.renderedCategory = selectedCategory;
  return true;
}

function invalidateRenderedTrainingScope(root) {
  if (!(root instanceof HTMLElement)) return;
  root.dataset.renderedProjectId = "";
  root.dataset.renderedCategory = "";
  root.querySelector("[data-ai-research-training-queue]")?.replaceChildren();
  root.querySelector("[data-ai-research-training-history]")?.replaceChildren();
}

function guardRenderedTrainingScopeClick(event) {
  const root = event.currentTarget;
  if (!(root instanceof HTMLElement)) return;
  if (
    routePath() === ROUTE
    && root.dataset.renderedProjectId === currentTrainingProjectId()
    && root.dataset.renderedCategory === currentCategory()
  ) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function prepareTrainingRoot(root) {
  root.dataset.ceV4Owned = "ai-research-training";
  root.setAttribute(ROOT_ATTRIBUTE, "true");
  if (root.dataset.renderedScopeGuardBound !== "true") {
    root.addEventListener("click", guardRenderedTrainingScopeClick, true);
    root.dataset.renderedScopeGuardBound = "true";
  }
  return root;
}

function buildRoot() {
  const root = el("section", "ai-research-training card card-pad");
  prepareTrainingRoot(root);
  const header = el("header", "ai-research-training__header");
  const copy = el("div");
  copy.append(
    el("p", "eyebrow", "ИССЛЕДОВАНИЯ → ОБУЧЕНИЕ → РЕКОМЕНДАЦИИ"),
    el("h2", "", "Разбор исследований для ИИ"),
    el("p", "muted", "Здесь ИИ не «глотает» всё подряд. Вы видите разбор ролика, выбираете полезные выводы, правите рекомендации и только затем допускаете их в создание."),
  );
  const selectLabel = el("label", "field ai-research-training__category");
  selectLabel.append(el("span", "", "Категория обучения"));
  const select = el("select");
  select.dataset.trainingCategory = "true";
  CATEGORIES.forEach(([value, label]) => {
    const option = el("option", "", label);
    option.value = value;
    select.append(option);
  });
  selectLabel.append(select);
  header.append(copy, selectLabel);

  const status = el("p", "ai-research-training__status", "Загружаем очередь…");
  status.dataset.aiResearchTrainingStatus = "true";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  const queue = el("div", "ai-research-training__queue");
  queue.dataset.aiResearchTrainingQueue = "true";
  const historyWrap = el("details", "ai-research-training__history");
  const historySummary = el("summary", "", "Уже отобранные исследования");
  const history = el("div", "ai-research-training__history-grid");
  history.dataset.aiResearchTrainingHistory = "true";
  historyWrap.append(historySummary, history);

  root.append(header, status, queue, historyWrap);
  root.addEventListener("change", handleChange);
  root.addEventListener("click", handleClick);
  return root;
}

function hostForRoot() {
  return document.querySelector(".ai-learning-control-room")
    || document.querySelector(".ai-learning-page")
    || document.querySelector("#workspace-content")
    || document.querySelector("#main-content");
}

function ensureRoot() {
  let root = document.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (root instanceof HTMLElement) return prepareTrainingRoot(root);
  const host = hostForRoot();
  if (!(host instanceof HTMLElement)) return null;
  root = buildRoot();
  const oldInbox = host.querySelector(".ai-learning-research-inbox");
  if (oldInbox?.parentNode) oldInbox.parentNode.insertBefore(root, oldInbox);
  else {
    const header = host.querySelector(":scope > header, .ai-learning-hero");
    if (header?.nextSibling) host.insertBefore(root, header.nextSibling);
    else host.prepend(root);
  }
  return root;
}

function suspendProjectTraining(root) {
  runtime.loadToken += 1;
  runtime.loading = false;
  if (root) {
    root.hidden = false;
    root.dataset.loading = "false";
    root.dataset.projectRequired = "true";
    const queue = root.querySelector("[data-ai-research-training-queue]");
    const history = root.querySelector("[data-ai-research-training-history]");
    queue?.replaceChildren();
    history?.replaceChildren();
    if (queue) {
      const empty = el("div", "ai-research-training__empty");
      empty.append(
        el("strong", "", "Выберите проект для обучения на исследованиях"),
        el("p", "", "Глобальные знания ИИ-центра доступны ниже. Очередь исследований и решения открываются только в контексте выбранного проекта."),
      );
      queue.append(empty);
    }
    setStatus(root, "Проект не выбран — данные исследований не загружаются.", "neutral");
  }
  const oldInbox = document.querySelector(".ai-learning-research-inbox");
  if (oldInbox instanceof HTMLElement) {
    oldInbox.hidden = true;
    oldInbox.dataset.replacedByResearchTraining = "true";
  }
}

async function load(
  root,
  category = runtime.category,
  projectId = runtime.projectId || currentTrainingProjectId(),
) {
  const selectedCategory = normalizedCategory(category) || "other";
  const selectedProjectId = normalizedProjectId(projectId);
  if (!root || routePath() !== ROUTE) return;
  if (!selectedProjectId) return;
  root.hidden = false;
  delete root.dataset.projectRequired;
  const loadToken = ++runtime.loadToken;
  runtime.loading = true;
  root.dataset.loading = "true";
  setStatus(
    root,
    `Загружаем разборы категории «${categoryLabel(selectedCategory)}»…`,
  );
  try {
    const api = await getApi();
    const response = await api.call(
      RPC_QUEUE,
      payloadWithOrganization(api, projectScopedTrainingPayload({
        product_category: selectedCategory,
        limit: 30,
      }, selectedProjectId)),
    );
    if (
      loadToken !== runtime.loadToken
      || routePath() !== ROUTE
      || runtime.category !== selectedCategory
      || runtime.projectId !== selectedProjectId
      || currentTrainingProjectId() !== selectedProjectId
    ) return;
    if (!renderSnapshot(root, response, selectedProjectId)) {
      throw new Error("ai_research_training_project_scope_mismatch");
    }
  } catch (error) {
    if (
      loadToken !== runtime.loadToken
      || runtime.category !== selectedCategory
      || runtime.projectId !== selectedProjectId
      || currentTrainingProjectId() !== selectedProjectId
    ) return;
    console.warn("Research training queue unavailable", error);
    setStatus(
      root,
      `Категория «${categoryLabel(selectedCategory)}»: не удалось загрузить очередь. Миграция/RPC должны быть развёрнуты вместе с интерфейсом.`,
      "danger",
    );
  } finally {
    if (loadToken === runtime.loadToken) {
      runtime.loading = false;
      root.dataset.loading = "false";
    }
  }
}

function selectedInsights(card) {
  return [...card.querySelectorAll("[data-insight-key]:checked")]
    .map((input) => input.dataset.insightKey)
    .filter((value) => ["category", "competitors", "trends", "brief"].includes(value));
}

function selectedScenarios(card) {
  return [...card.querySelectorAll("[data-scenario-select]:checked")]
    .map((input) => Number(input.dataset.scenarioSelect))
    .filter((value) => Number.isInteger(value) && value >= 1 && value <= 3);
}

function scenarioEdits(card, positions) {
  return positions.map((position) => {
    const scenario = card.querySelector(`[data-scenario-position="${position}"]`);
    const read = (name) => String(scenario?.querySelector(`[name="${name}"]`)?.value || "").trim();
    return {
      position,
      title: read("title"),
      hook: read("hook"),
      spoken_script: read("spoken_script"),
      shot_list: read("shot_list"),
      key_message: read("key_message"),
      visual_direction: read("visual_direction"),
      cta: read("cta"),
    };
  });
}

async function decide(card, decision) {
  if (runtime.mutating) return;
  const mutationRoot = runtime.root;
  const projectId = currentTrainingProjectId()
    || normalizedProjectId(routeParams().get("project_id"));
  const category = runtime.category;
  if (
    routePath() !== ROUTE
    || !mutationRoot
    || !projectId
    || runtime.projectId !== projectId
    || normalizedProjectId(card.dataset.projectId) !== projectId
  ) return;
  const confirmation = card.querySelector("[data-training-confirmation]");
  if (!(confirmation instanceof HTMLInputElement) || !confirmation.checked) {
    confirmation?.focus();
    setStatus(runtime.root, "Сначала подтвердите, что вы проверили разбор.", "danger");
    return;
  }
  const insights = decision === "approve" ? selectedInsights(card) : [];
  const positions = decision === "approve" ? selectedScenarios(card) : [];
  if (decision === "approve" && (!insights.length || !positions.length)) {
    setStatus(runtime.root, "Выберите минимум один блок анализа и одну рекомендацию.", "danger");
    return;
  }
  const notes = String(card.querySelector('[name="operator_notes"]')?.value || "").trim();
  runtime.mutating = true;
  mutationRoot.dataset.mutating = "true";
  setStatus(
    runtime.root,
    decision === "approve" ? "Сохраняем выбранное обучение…" : "Отклоняем исследование…",
  );
  try {
    const api = await getApi();
    const response = await api.call(
      RPC_DECIDE,
      payloadWithOrganization(api, projectScopedTrainingPayload({
        product_category: category,
        receipt_id: card.dataset.receiptId,
        receipt_hash: card.dataset.receiptHash,
        decision,
        selected_insight_keys: insights,
        selected_scenario_positions: positions,
        edits: decision === "approve" ? scenarioEdits(card, positions) : [],
        ...(notes ? { operator_notes: notes } : {}),
        confirmation: true,
        idempotency_key: idempotencyKey("research-training"),
      }, projectId)),
    );
    if (
      routePath() !== ROUTE
      || runtime.root !== mutationRoot
      || runtime.category !== category
      || runtime.projectId !== projectId
      || currentTrainingProjectId() !== projectId
    ) return;
    if (!renderSnapshot(mutationRoot, unwrap(response).snapshot || response, projectId)) {
      throw new Error("ai_research_training_project_scope_mismatch");
    }
    setStatus(
      runtime.root,
      decision === "approve"
        ? "Готово: выбранные выводы стали редактируемыми рекомендациями для создания."
        : "Исследование исключено из обучения.",
      "ready",
    );
  } catch (error) {
    if (
      runtime.root !== mutationRoot
      || runtime.projectId !== projectId
      || currentTrainingProjectId() !== projectId
    ) return;
    console.warn("Research training decision failed", error);
    setStatus(
      runtime.root,
      error?.message || "Не удалось сохранить решение. Обновите страницу и повторите.",
      "danger",
    );
  } finally {
    runtime.mutating = false;
    if (mutationRoot?.isConnected) mutationRoot.dataset.mutating = "false";
  }
}

function handleChange(event) {
  const select = event.target.closest?.("[data-training-category]");
  if (!select) return;
  const category = normalizedCategory(select.value);
  if (!category) return;
  const changed = category !== runtime.category;
  runtime.category = category;
  rememberCategory(category);
  syncLegacyCategoryButtons(category);
  updateCategoryRoute(category);
  const projectId = currentTrainingProjectId();
  const requestKey = `${projectId}:${category}:${runtime.root?.isConnected}`;
  if (changed || runtime.requestKey !== requestKey) {
    if (changed) invalidateRenderedTrainingScope(runtime.root);
    runtime.requestKey = requestKey;
    void load(runtime.root, category, projectId);
  }
}

function handleLegacyCategoryClick(event) {
  if (routePath() !== ROUTE) return;
  const control = event.target.closest?.(
    ".ai-learning-category[data-category-key]",
  );
  if (!control || !legacyCategoryControlVisible(control)) return;
  const category = normalizedCategory(control.dataset?.categoryKey);
  if (!category) return;
  const projectId = currentTrainingProjectId();
  const changed = category !== runtime.category;
  runtime.category = category;
  rememberCategory(category);
  syncLegacyCategoryButtons(category);
  syncTrainingCategorySelect(category);
  if (changed && runtime.root?.isConnected) {
    invalidateRenderedTrainingScope(runtime.root);
    runtime.requestKey = `${projectId}:${category}:${runtime.root.isConnected}`;
    void load(runtime.root, category, projectId);
  }
  window.queueMicrotask(() => {
    restoreProjectScopeAfterLegacyNavigation(category, projectId);
  });
}

function handleClick(event) {
  const root = event.currentTarget;
  if (
    routePath() !== ROUTE
    || (
      root instanceof HTMLElement
      && (
        root.dataset.renderedProjectId !== currentTrainingProjectId()
        || root.dataset.renderedCategory !== currentCategory()
      )
    )
  ) {
    event.preventDefault();
    return;
  }
  const button = event.target.closest?.("[data-training-decision]");
  if (!(button instanceof HTMLButtonElement)) return;
  event.preventDefault();
  const card = button.closest("[data-receipt-id]");
  if (!(card instanceof HTMLElement)) return;
  const decision = button.dataset.trainingDecision;
  if (!["approve", "reject"].includes(decision)) return;
  void decide(card, decision);
}

function unmount() {
  runtime.loadToken += 1;
  runtime.loading = false;
  runtime.requestKey = "";
  runtime.root = null;
  runtime.projectId = "";
  document.querySelectorAll(`[${ROOT_ATTRIBUTE}]`).forEach((root) => root.remove());
}

function mount() {
  if (routePath() !== ROUTE) {
    unmount();
    return;
  }
  const previousRoot = runtime.root;
  const previousProjectId = runtime.projectId;
  const previousCategory = runtime.category;
  const root = ensureRoot();
  if (!root) return;
  const category = currentCategory();
  const projectId = currentTrainingProjectId();
  const scopeChanged = previousRoot !== root
    || previousProjectId !== projectId
    || previousCategory !== category;
  runtime.root = root;
  if (projectId) canonicalizeTrainingRoute(category, projectId);
  const requestKey = `${projectId}:${category}:${root.isConnected}`;
  runtime.category = category;
  runtime.projectId = projectId;
  if (scopeChanged) invalidateRenderedTrainingScope(root);
  rememberCategory(category);
  syncLegacyCategoryButtons(category);
  syncTrainingCategorySelect(category);
  if (!projectId) {
    runtime.requestKey = requestKey;
    suspendProjectTraining(root);
    return;
  }
  root.hidden = false;
  if (runtime.requestKey !== requestKey || !root.dataset.loaded) {
    runtime.requestKey = requestKey;
    root.dataset.loaded = "true";
    void load(root, category, projectId);
  }
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
      "ai-research-training",
      mount,
      { priority: 205 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", scheduleMount);
  window.addEventListener("hashchange", scheduleMount);
  document.addEventListener("click", handleLegacyCategoryClick, true);
  window.queueMicrotask(scheduleMount);
}

export const AiResearchTraining = Object.freeze({ mount, load });
