/*
 * ContentEngine · exact YouTube source inbox for AI Center.
 *
 * URL-only rows are visible provenance, not learned evidence. They stay in an
 * explicit awaiting-media state until lawful MP4 evidence is attached and a
 * separate analysis receipt exists.
 */

import { writeExactYoutubeMediaHandoff } from "./exact-youtube-media-handoff.js?v=20260826.rebuild-clean.60";

const ROUTE = "/workspace/ai";
const ROOT_ATTRIBUTE = "data-ai-exact-youtube-sources-root";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

const runtime = {
  root: null,
  loading: false,
  pendingLoad: false,
  loadToken: 0,
  loadedRoot: null,
  loadedProjectId: "",
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

function exactYoutubeProjectScopeAllowed() {
  const shell = typeof document === "undefined"
    ? null
    : document.querySelector(".workspace-shell");
  // Real browsers always expose documentElement. A document-less adapter
  // harness may exercise pure lifecycle behavior without a workspace shell.
  if (!shell && typeof document !== "undefined" && !document.documentElement) {
    return true;
  }
  return shell?.dataset?.aiExactYoutubeSourceScope === "project";
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

function guardRenderedProjectClick(event) {
  const root = event.currentTarget;
  const link = event.target.closest?.("a[href]");
  if (!(root instanceof HTMLElement) || !link) return;
  if (
    routePath() === ROUTE
    && root.dataset.renderedProjectId === projectId()
  ) return;
  event.preventDefault();
  event.stopImmediatePropagation();
}

function prepareRoot(root) {
  root.dataset.ceV4Owned = "ai-exact-youtube-sources";
  root.setAttribute(ROOT_ATTRIBUTE, "true");
  root.setAttribute("aria-labelledby", "ai-exact-youtube-sources-title");
  if (root.dataset.renderedProjectGuardBound !== "true") {
    root.addEventListener("click", guardRenderedProjectClick, true);
    root.dataset.renderedProjectGuardBound = "true";
  }
  return root;
}

function ensureRoot() {
  if (runtime.root?.isConnected) return prepareRoot(runtime.root);
  const existing = document.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (existing) {
    runtime.root = prepareRoot(existing);
    return runtime.root;
  }
  const root = el("section", "ai-exact-youtube-sources card card-pad");
  prepareRoot(root);
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
  if (routePath() !== ROUTE) return false;
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

function mediaReady(source) {
  const value = typeof source?.media_ready === "boolean"
    ? source.media_ready
    : source?.analysis_ready;
  return value === true;
}

function researchLifecycle(source) {
  const value = source?.research_lifecycle;
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : null;
}

function hasEffectiveRecommendations(source) {
  return researchLifecycle(source)?.effective
    ?.has_approved_recommendations === true;
}

function exactResearchHash(source) {
  const latest = researchLifecycle(source)?.latest;
  const runId = clean(latest?.run_id, 64).toLowerCase();
  if (UUID_PATTERN.test(runId)) {
    return workspaceHash("/workspace/research", {
      project_id: projectId(),
      run: runId,
    });
  }
  return workspaceHash("/workspace/research", {
    project_id: projectId(),
    source_url: clean(source?.canonical_url, 300),
  });
}

function aiLearningHash(source) {
  const latest = researchLifecycle(source)?.latest;
  return workspaceHash("/workspace/ai", {
    project_id: projectId(),
    category: clean(latest?.product_category, 40).toLowerCase(),
    receipt: clean(latest?.receipt_id, 64).toLowerCase(),
  });
}

function exactReviewHash(source, attachedMediaId) {
  return workspaceHash("/workspace/review", {
    view: "new",
    media: attachedMediaId,
    project_id: projectId(),
    youtube_source: clean(source.id, 64),
    attachment: clean(source?.attachment?.id, 64),
    product_name: clean(source.product_name, 300),
    product_sku: clean(source.product_sku, 160),
    purpose: "exact_youtube_research",
  });
}

// «Что произойдёт при нажатии» — расшифровка каждой кнопки карточки простыми
// словами (фидбек владельца 27.08: «что такое создать рекомендации, что такое
// открыть исследование»). Ключ — точная подпись кнопки.
const ACTION_HINTS = Object.freeze({
  "Создать с рекомендациями": "откроется форма «Создать», выводы и сценарии этого разбора уже подставлены в запуск.",
  "Открыть исследование": "откроется сам разбор ролика: факты, сценарии и решения человека.",
  "Открыть Исследования": "откроется раздел разборов этого проекта.",
  "Подготовить кадры для исследования": "выберете пять контрольных кадров из MP4 — без них разбор не начинается.",
  "Отобрать для обучения": "отметите полезные выводы и сценарии — только они станут рекомендациями для запусков.",
  "Открыть текущий запуск": "откроется сохранённый запуск разбора и его статус.",
  "Проверить исследование": "откроется сохранённый запуск — там видно, на чём он остановился.",
  "Открыть завершённый запуск": "откроется готовый результат разбора.",
  "Открыть ИИ-центр": "вернётесь к категориям обучения ИИ.",
  "Загрузить MP4 и продолжить": "выберете файл ролика — он привяжется к этому источнику для разбора.",
  "Проверить сохранённый файл": "откроются файлы проекта на сохранённом MP4 этого источника.",
});

export function lifecyclePresentation(source, attachedMediaId) {
  const lifecycle = researchLifecycle(source);
  const state = clean(lifecycle?.state, 80);
  const effective = hasEffectiveRecommendations(source);
  const researchHref = exactResearchHash(source);
  const aiHref = aiLearningHash(source);
  const generationHref = workspaceHash("/workspace/generation", {
    project_id: projectId(),
  });

  if (effective) {
    const latestSuffix = state === "analysis_failed"
      ? " Последний повтор исследования не завершён, но ранее одобренный отбор остаётся действующим."
      : state === "excluded"
        ? " Последний результат исключён, но ранее одобренный отбор остаётся действующим."
        : "";
    return {
      status: latestSuffix
        ? "Рекомендации ИИ готовы · проверьте последний запуск"
        : "Рекомендации ИИ готовы",
      explanation:
        `Исследование завершено, а выбранные человеком выводы и сценарии уже доступны в «Создать».${latestSuffix} Новый анализ этого видео для применения рекомендаций не нужен.`,
      primaryLabel: "Создать с рекомендациями",
      primaryHref: generationHref,
      secondaryLabel: "Открыть исследование",
      secondaryHref: researchHref,
    };
  }

  if (state === "not_started") {
    return {
      status: "MP4 готов · исследование не начато",
      explanation:
        "MP4 сохранён и связан с точным источником. Кадры, монтаж и визуальная механика ещё не анализировались; речь, аудио и полный видеопоток внешнему ИИ не передаются. Подготовка пяти контрольных кадров сама по себе не запускает платное исследование.",
      primaryLabel: "Подготовить кадры для исследования",
      primaryHref: exactReviewHash(source, attachedMediaId),
      secondaryLabel: "Открыть Исследования",
      secondaryHref: researchHref,
    };
  }
  if (state === "analysis_in_progress") {
    return {
      status: "Исследование выполняется",
      explanation:
        "Для этого точного MP4 уже создано исследование. Его текущий запуск ещё выполняется; ИИ‑центр только показывает сохранённый сервером статус и не создаёт новый платный вызов.",
      primaryLabel: "Открыть текущий запуск",
      primaryHref: researchHref,
      secondaryLabel: "Открыть ИИ‑центр",
      secondaryHref: aiHref,
    };
  }
  if (state === "analysis_failed") {
    return {
      status: "Исследование требует внимания",
      explanation:
        "Последний запуск не завершился. Откройте сохранённое исследование и проверьте его ошибку; повторный платный запуск отсюда не создаётся.",
      primaryLabel: "Проверить исследование",
      primaryHref: researchHref,
      secondaryLabel: "Открыть ИИ‑центр",
      secondaryHref: aiHref,
    };
  }
  if (state === "completed_without_ai_receipt") {
    return {
      status: "Исследование завершено · нужна синхронизация",
      explanation:
        "Исследование уже завершено, но его серверная квитанция для ИИ‑центра не найдена. Новый платный запуск не нужен: откройте сохранённый результат и проверьте синхронизацию.",
      primaryLabel: "Открыть завершённый запуск",
      primaryHref: researchHref,
      secondaryLabel: "Открыть ИИ‑центр",
      secondaryHref: aiHref,
    };
  }
  if (state === "awaiting_learning_selection") {
    return {
      status: "Исследование завершено · нужен отбор",
      explanation:
        "Результат исследования уже получен. Чтобы он влиял на новые генерации, в ИИ‑центре выберите минимум один вывод и один сценарий, подтвердите отбор и нажмите «Обучить на выбранном и сохранить рекомендации».",
      primaryLabel: "Отобрать для обучения",
      primaryHref: aiHref,
      secondaryLabel: "Открыть исследование",
      secondaryHref: researchHref,
    };
  }
  if (state === "recommendations_ready") {
    return {
      status: "Рекомендации ИИ готовы",
      explanation:
        "Исследование завершено, а выбранные человеком выводы и сценарии уже доступны в «Создать». Новый анализ этого видео для применения рекомендаций не нужен.",
      primaryLabel: "Создать с рекомендациями",
      primaryHref: generationHref,
      secondaryLabel: "Открыть исследование",
      secondaryHref: researchHref,
    };
  }
  if (state === "excluded") {
    return {
      status: "Не включено в обучение",
      explanation:
        "Исследование сохранено, но этот результат был исключён человеком и не влияет на рекомендации для новых генераций. При необходимости откройте исходный запуск; новый платный анализ отсюда не начинается.",
      primaryLabel: "Открыть исследование",
      primaryHref: researchHref,
      secondaryLabel: "Открыть ИИ‑центр",
      secondaryHref: aiHref,
    };
  }

  // Rolling-deploy fallback: the older queue v2 knows that MP4 is ready but
  // cannot prove whether Product Research already completed.  Never claim
  // that analysis is absent and never route straight into another paid flow.
  return {
    status: "MP4 готов · статус исследования уточняется",
    explanation:
      "MP4 сохранён и связан с точным источником. Эта версия ответа ещё не передала жизненный цикл исследования, поэтому ИИ‑центр не делает вывод, выполнен анализ или нет, и не запускает новый вызов.",
    primaryLabel: "Открыть Исследования",
    primaryHref: researchHref,
    secondaryLabel: "",
    secondaryHref: "",
  };
}

function renderHeader(root, sources) {
  const awaiting = sources.filter(
    (source) => source?.status !== "media_attached",
  ).length;
  const restore = sources.filter(
    (source) => source?.status === "media_attached" && !mediaReady(source),
  ).length;
  const readyMedia = sources.filter(
    (source) => source?.status === "media_attached" && mediaReady(source),
  );
  const recommendations = readyMedia.filter((source) => (
    hasEffectiveRecommendations(source)
    || researchLifecycle(source)?.state === "recommendations_ready"
  )).length;
  const selection = readyMedia.filter((source) => (
    !hasEffectiveRecommendations(source)
    && researchLifecycle(source)?.state === "awaiting_learning_selection"
  )).length;
  const running = readyMedia.filter((source) => (
    !hasEffectiveRecommendations(source)
    && researchLifecycle(source)?.state === "analysis_in_progress"
  )).length;
  const attention = readyMedia.filter((source) => (
    !hasEffectiveRecommendations(source)
    && new Set([
      "analysis_failed",
      "completed_without_ai_receipt",
    ]).has(researchLifecycle(source)?.state)
  )).length;
  const excluded = readyMedia.filter((source) => (
    !hasEffectiveRecommendations(source)
    && researchLifecycle(source)?.state === "excluded"
  )).length;
  const notStarted = readyMedia.filter((source) => (
    !hasEffectiveRecommendations(source)
    && researchLifecycle(source)?.state === "not_started"
  )).length;
  const unknown = readyMedia.length
    - recommendations - selection - running - attention - excluded
    - notStarted;
  const header = el("header", "ai-exact-youtube-sources__head");
  const copy = el("div");
  const eyebrow = el("p", "eyebrow", "ИСТОЧНИКИ ИЗ ИССЛЕДОВАНИЙ");
  const title = el("h2", "", "Видео до обучения");
  title.id = "ai-exact-youtube-sources-title";
  const intro = el(
    "p",
    "muted",
    "Здесь виден полный путь точного YouTube‑источника: MP4, исследование, человеческий отбор и готовые рекомендации. Готовность файла и завершение исследования показаны отдельно; одна лишь ссылка не считается просмотренным видео.",
  );
  copy.append(eyebrow, title, intro);
  const badge = el(
    "span",
    "ai-exact-youtube-sources__count",
    [
      awaiting ? `${awaiting} ждут MP4` : "",
      notStarted ? `${notStarted} ещё не исследованы` : "",
      running ? `${running} исследуются` : "",
      selection ? `${selection} ждут отбора` : "",
      recommendations ? `${recommendations} с рекомендациями` : "",
      excluded ? `${excluded} исключены` : "",
      attention ? `${attention} требуют внимания` : "",
      unknown ? `${unknown} уточняют статус` : "",
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
    && mediaReady(source)
    && UUID_PATTERN.test(attachedMediaId);
  const restore = hasAttachment && !attached;
  const presentation = attached
    ? lifecyclePresentation(source, attachedMediaId)
    : restore
      ? {
          status: "Проверьте сохранённый MP4",
          explanation:
            "Связь с MP4 сохранена, но сервер больше не подтверждает готовность файла. Не загружайте другой ролик вместо него: сначала проверьте исходник в Файлах.",
          primaryLabel: "Проверить сохранённый файл",
          primaryHref: workspaceHash("/workspace/board", {
            project_id: projectId(),
            media: attachedMediaId,
          }),
          secondaryLabel: "Открыть Исследования",
          secondaryHref: exactResearchHash(source),
        }
      : {
          status: "Ждёт MP4",
          explanation:
            "Шаг 1 выполнен: точный ролик зарегистрирован. Кадры, монтаж и речь ещё не анализировались. Выбранный путь позже анализирует только пять контрольных JPEG и визуальную механику; речь, аудио и полный поток не передаются. Поэтому источник пока не может обучать ИИ.",
          primaryLabel: "Загрузить MP4 и продолжить",
          primaryHref: workspaceHash("/workspace/media", {
            project_id: projectId(),
            youtube_source: clean(source.id, 64),
            video_url: clean(source.canonical_url, 300),
            product_name: clean(source.product_name, 300),
            product_sku: clean(source.product_sku, 160),
            return_to: workspaceHash("/workspace/ai", {
              project_id: projectId(),
              youtube_source: clean(source.id, 64),
            }),
          }),
          secondaryLabel: "Открыть Исследования",
          secondaryHref: exactResearchHash(source),
        };
  const status = el(
    "span",
    "ai-exact-youtube-source__status",
    presentation.status,
  );
  head.append(title, status);

  const link = el("a", "ai-exact-youtube-source__url", clean(source.canonical_url, 240));
  link.href = clean(source.canonical_url, 300);
  link.target = "_blank";
  link.rel = "noopener noreferrer";

  const explanation = el(
    "p",
    "",
    presentation.explanation,
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
    presentation.primaryLabel,
  );
  primary.href = presentation.primaryHref;
  const primaryHint = ACTION_HINTS[presentation.primaryLabel] || "";
  if (primaryHint) primary.title = primaryHint;
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
  actions.append(primary);
  let secondaryHint = "";
  if (
    presentation.secondaryLabel
    && presentation.secondaryHref
    && presentation.secondaryHref !== presentation.primaryHref
  ) {
    const secondary = el(
      "a",
      "btn btn-secondary btn-small",
      presentation.secondaryLabel,
    );
    secondary.href = presentation.secondaryHref;
    secondaryHint = ACTION_HINTS[presentation.secondaryLabel] || "";
    if (secondaryHint) secondary.title = secondaryHint;
    actions.append(secondary);
  }

  card.append(head, link, explanation, meta, actions);
  const hintParts = [
    primaryHint ? `«${presentation.primaryLabel}» — ${primaryHint}` : "",
    secondaryHint ? `«${presentation.secondaryLabel}» — ${secondaryHint}` : "",
  ].filter(Boolean);
  if (hintParts.length) {
    card.append(el("small", "ai-exact-youtube-source__hints", hintParts.join(" ")));
  }
  return card;
}

function render(root, sources, renderedProjectId) {
  root.replaceChildren();
  root.dataset.renderedProjectId = renderedProjectId;
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
  if (
    routePath() !== ROUTE
    || !currentProjectId
    || !exactYoutubeProjectScopeAllowed()
  ) return;
  if (runtime.loading) {
    runtime.pendingLoad = true;
    return;
  }
  const loadToken = ++runtime.loadToken;
  runtime.loading = true;
  runtime.pendingLoad = false;
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
    if (
      runtime.loadToken !== loadToken
      || routePath() !== ROUTE
      || projectId() !== currentProjectId
      || runtime.root !== root
      || !root.isConnected
      || !exactYoutubeProjectScopeAllowed()
    ) return;
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
    render(root, value.sources, currentProjectId);
  } catch {
    if (
      runtime.loadToken === loadToken
      && routePath() === ROUTE
      && projectId() === currentProjectId
      && runtime.root === root
      && root.isConnected
      && exactYoutubeProjectScopeAllowed()
    ) renderError(root);
  } finally {
    if (runtime.loadToken === loadToken) {
      runtime.loading = false;
      if (root.isConnected) root.removeAttribute("aria-busy");
      const pendingLoad = runtime.pendingLoad;
      runtime.pendingLoad = false;
      if (
        pendingLoad
        && routePath() === ROUTE
        && projectId()
        && exactYoutubeProjectScopeAllowed()
      ) void load();
    }
  }
}

function unmount() {
  runtime.loadToken += 1;
  runtime.loading = false;
  runtime.pendingLoad = false;
  runtime.root = null;
  runtime.loadedRoot = null;
  runtime.loadedProjectId = "";
  document.querySelectorAll(`[${ROOT_ATTRIBUTE}]`).forEach((root) => root.remove());
}

function mount({ force = false } = {}) {
  const currentProjectId = projectId();
  if (
    routePath() !== ROUTE
    || !currentProjectId
    || !exactYoutubeProjectScopeAllowed()
  ) {
    unmount();
    return;
  }
  const root = ensureRoot();
  const scopeChanged = runtime.loadedRoot !== root
    || runtime.loadedProjectId !== currentProjectId;
  if (
    !force
    && !scopeChanged
  ) return;
  runtime.loadedRoot = root;
  runtime.loadedProjectId = currentProjectId;
  if (scopeChanged) {
    root.dataset.renderedProjectId = "";
    root.replaceChildren();
  }
  void load();
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "ai-exact-youtube-sources",
      () => mount(),
      { priority: 205 },
    );
  }
  window.addEventListener(
    "contentengine:v4-route-ready",
    () => mount(),
  );
  window.addEventListener(
    "contentengine:workspace-capabilities-ready",
    () => mount({ force: true }),
  );
  window.addEventListener(
    "hashchange",
    () => window.queueMicrotask(() => mount()),
  );
  window.queueMicrotask(() => mount());
}

export const AiExactYoutubeSources = Object.freeze({ mount, load });
