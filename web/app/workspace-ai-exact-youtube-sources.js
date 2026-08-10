/*
 * ContentEngine · exact YouTube source inbox for AI Center.
 *
 * URL-only rows are visible provenance, not learned evidence. They stay in an
 * explicit awaiting-media state until lawful MP4 evidence is attached and a
 * separate analysis receipt exists.
 */

import { writeExactYoutubeMediaHandoff } from "./exact-youtube-media-handoff.js?v=20260810.exact-video.2";

const ROUTE = "/workspace/ai";
const ROOT_ATTRIBUTE = "data-ai-exact-youtube-sources-root";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

const runtime = {
  root: null,
  loading: false,
  requestKey: "",
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

function projectId() {
  const value = String(routeParams().get("project_id") || "")
    .trim()
    .toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function clean(value, limit = 500) {
  return String(value ?? "").replace(/\s+/gu, " ").trim().slice(0, limit);
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

function formatDate(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "дата не подтверждена";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function ensureRoot() {
  if (runtime.root?.isConnected) return runtime.root;
  const existing = document.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (existing) {
    runtime.root = existing;
    return existing;
  }
  const root = el("section", "ai-exact-youtube-sources card card-pad");
  root.setAttribute(ROOT_ATTRIBUTE, "true");
  root.setAttribute("aria-labelledby", "ai-exact-youtube-sources-title");
  const host = document.querySelector("[data-ai-research-training-root]")
    || document.querySelector("main")
    || document.body;
  if (host.parentNode && host.matches?.("[data-ai-research-training-root]")) {
    host.parentNode.insertBefore(root, host);
  } else {
    host.prepend(root);
  }
  runtime.root = root;
  return root;
}

function workspaceHash(path, values = {}) {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    const normalized = clean(value, 500);
    if (normalized) query.set(key, normalized);
  });
  return `#${path}?${query.toString()}`;
}

export function beginMediaHandoff(source) {
  const context = window.ContentEngineWorkspaceRuntime
    ?.getExactYoutubeHandoffContext?.() || {};
  const currentProjectId = projectId();
  if (String(context.project_id || "").trim().toLowerCase() !== currentProjectId) {
    return false;
  }
  return writeExactYoutubeMediaHandoff(window.sessionStorage, {
    organization_id: context.organization_id,
    user_id: context.user_id,
    session_id: context.session_id,
    project_id: currentProjectId,
    source_id: clean(source?.id, 64).toLowerCase(),
    canonical_url: clean(source?.canonical_url, 300),
    product_name: clean(source?.product_name, 300),
    product_sku: clean(source?.product_sku, 160),
  });
}

function renderHeader(root, sources) {
  const attached = sources.filter(
    (source) => source?.status === "media_attached"
      && source?.analysis_ready === true,
  ).length;
  const restore = sources.filter(
    (source) => source?.status === "media_attached"
      && source?.analysis_ready !== true,
  ).length;
  const awaiting = sources.length - attached - restore;
  const header = el("header", "ai-exact-youtube-sources__head");
  const copy = el("div");
  const eyebrow = el("p", "eyebrow", "ИСТОЧНИКИ ИЗ ИССЛЕДОВАНИЙ");
  const title = el("h2", "", "Видео до обучения");
  title.id = "ai-exact-youtube-sources-title";
  const intro = el(
    "p",
    "muted",
    "Здесь видны точные YouTube-источники ещё до анализа. URL сохраняет происхождение, но не считается просмотренным видео и не влияет на рекомендации без MP4 и отдельной квитанции разбора.",
  );
  copy.append(eyebrow, title, intro);
  const badge = el(
    "span",
    "ai-exact-youtube-sources__count",
    [
      awaiting ? `${awaiting} ждут MP4` : "",
      attached ? `${attached} готовы к разбору` : "",
      restore ? `${restore} требуют проверки файла` : "",
    ].filter(Boolean).join(" · ") || "Очередь пуста",
  );
  header.append(copy, badge);
  root.append(header);
}

function sourceCard(source) {
  const card = el("article", "ai-exact-youtube-source");
  card.dataset.sourceId = clean(source.id, 64);
  const head = el("div", "ai-exact-youtube-source__head");
  const title = el(
    "strong",
    "",
    clean(source.product_name, 180) || `YouTube · ${clean(source.video_id, 20)}`,
  );
  const attachedMediaId = clean(source?.media?.id, 64).toLowerCase();
  const hasAttachment = source?.status === "media_attached";
  const attached = hasAttachment
    && source?.analysis_ready === true
    && UUID_PATTERN.test(attachedMediaId);
  const restore = hasAttachment && !attached;
  const status = el(
    "span",
    "ai-exact-youtube-source__status",
    attached
      ? "MP4 привязан"
      : restore
        ? "Проверьте сохранённый MP4"
        : "Ждёт MP4",
  );
  head.append(title, status);

  const link = el("a", "ai-exact-youtube-source__url", clean(source.canonical_url, 240));
  link.href = clean(source.canonical_url, 300);
  link.target = "_blank";
  link.rel = "noopener noreferrer";

  const explanation = el(
    "p",
    "",
    attached
      ? "MP4 сохранён и связан с точным источником. Разбор пяти контрольных кадров и визуальной механики ещё не выполнен; речь, аудио и полный видеопоток внешнему ИИ не передаются. До отдельной квитанции исследования источник не влияет на рекомендации ИИ."
      : restore
        ? "Связь с MP4 сохранена, но сервер больше не подтверждает готовность файла. Не загружайте другой ролик вместо него: сначала проверьте исходник в Файлах."
        : "Шаг 1 выполнен: точный ролик зарегистрирован. Кадры, монтаж и речь ещё не анализировались. Выбранный путь позже анализирует только пять контрольных JPEG и визуальную механику; речь, аудио и полный поток не передаются. Поэтому источник пока не может обучать ИИ.",
  );
  const meta = el("small", "ai-exact-youtube-source__meta");
  const sku = clean(source.product_sku, 100);
  meta.textContent = [
    sku ? `SKU ${sku}` : "SKU не указан",
    formatDate(source.created_at),
    `ID ${clean(source.video_id, 20)}`,
  ].join(" · ");

  const actions = el("div", "ai-exact-youtube-source__actions");
  const primary = el(
    "a",
    "btn btn-primary btn-small",
    attached
      ? "Подготовить кадры для исследования"
      : restore
        ? "Проверить сохранённый файл"
        : "Загрузить MP4 и продолжить",
  );
  primary.href = attached
    ? workspaceHash("/workspace/review", {
        view: "new",
        media: attachedMediaId,
        project_id: projectId(),
        youtube_source: clean(source.id, 64),
        attachment: clean(source?.attachment?.id, 64),
        product_name: clean(source.product_name, 300),
        product_sku: clean(source.product_sku, 160),
        purpose: "exact_youtube_research",
      })
    : restore
      ? workspaceHash("/workspace/board", {
          project_id: projectId(),
        })
      : workspaceHash("/workspace/media", {
        project_id: projectId(),
        youtube_source: clean(source.id, 64),
        video_url: clean(source.canonical_url, 300),
        product_name: clean(source.product_name, 300),
        product_sku: clean(source.product_sku, 160),
        return_to: workspaceHash("/workspace/ai", {
          project_id: projectId(),
          youtube_source: clean(source.id, 64),
        }),
      });
  if (!attached && !restore) {
    primary.dataset.exactYoutubeQueueUpload = "true";
    primary.addEventListener("click", (event) => {
      if (beginMediaHandoff(source)) return;
      event.preventDefault();
      primary.setAttribute("aria-disabled", "true");
      status.textContent = "Обновите ИИ-центр";
      explanation.textContent =
        "Контекст пользователя, проекта или вкладки изменился. MP4 не выбран и не загружен; обновите ИИ-центр и снова откройте этот источник.";
    });
  }
  const research = el("a", "btn btn-secondary btn-small", "Открыть Исследования");
  research.href = `#/workspace/research?project_id=${encodeURIComponent(projectId())}&source_url=${encodeURIComponent(clean(source.canonical_url, 300))}`;
  actions.append(primary, research);

  card.append(head, link, explanation, meta, actions);
  return card;
}

function render(root, sources) {
  root.replaceChildren();
  renderHeader(root, sources);
  if (!sources.length) {
    const empty = el("div", "ai-exact-youtube-sources__empty");
    empty.append(
      el("strong", "", "Видеоисточников пока нет"),
      el(
        "p",
        "",
        "Добавьте точную ссылку в «Исследованиях». Она сохранится без платного запуска и появится здесь до загрузки MP4.",
      ),
    );
    root.append(empty);
    return;
  }
  const grid = el("div", "ai-exact-youtube-sources__grid");
  sources.forEach((source) => grid.append(sourceCard(source)));
  root.append(grid);
}

function renderError(root) {
  root.replaceChildren();
  renderHeader(root, []);
  const error = el("div", "ai-exact-youtube-sources__empty is-error");
  error.append(
    el("strong", "", "Очередь видеоисточников не загрузилась"),
    el(
      "p",
      "",
      "Это не запускает повторный анализ и не списывает деньги. Обновите ИИ-центр после применения миграции.",
    ),
  );
  root.append(error);
}

async function load() {
  const currentProjectId = projectId();
  if (!currentProjectId || runtime.loading) return;
  const requestKey = `${currentProjectId}:${Date.now()}`;
  runtime.requestKey = requestKey;
  runtime.loading = true;
  const root = ensureRoot();
  root.setAttribute("aria-busy", "true");
  try {
    const api = await getApi();
    if (typeof api.exactYoutubeSourceQueue !== "function") {
      throw new Error("exact_youtube_queue_api_unavailable");
    }
    const response = await api.exactYoutubeSourceQueue({
      projectId: currentProjectId,
      limit: 30,
    });
    if (runtime.requestKey !== requestKey || routePath() !== ROUTE) return;
    const value = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    if (
      value?.ok !== true
      || !new Set([
        "exact-youtube-source-queue-v1",
        "exact-youtube-source-queue-v2",
      ]).has(value?.version)
      || value?.project_id !== currentProjectId
      || !Array.isArray(value?.sources)
      || value?.contract?.url_is_video_evidence !== false
      || value?.contract?.requires_lawful_mp4 !== true
      || value?.contract?.unattached_source_affects_learning !== false
      || value?.contract?.unattached_source_affects_generation !== false
      || value?.contract?.external_call_started !== false
      || value?.contract?.paid_call_started !== false
    ) throw new Error("exact_youtube_queue_invalid");
    render(root, value.sources);
  } catch {
    if (runtime.requestKey === requestKey) renderError(root);
  } finally {
    if (runtime.requestKey === requestKey) {
      runtime.loading = false;
      root.removeAttribute("aria-busy");
    }
  }
}

function mount() {
  if (routePath() !== ROUTE || !projectId()) return;
  ensureRoot();
  void load();
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "ai-exact-youtube-sources",
      mount,
      { priority: 205 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", mount);
  window.addEventListener("hashchange", () => window.queueMicrotask(mount));
  window.queueMicrotask(mount);
}

export const AiExactYoutubeSources = Object.freeze({ mount, load });
