/*
 * ContentEngine · terminal research failure recovery.
 *
 * A failed paid request is already terminal, so the user must be able to leave
 * that receipt, open the real upload screen, or start a fresh research form.
 * This adapter fixes the route handoff without deleting the audit receipt and
 * without starting any provider or paid operation.
 */

import { productResearchInputMarkup } from "./product-research-view.js?v=20260826.rebuild-clean.60";
import {
  readExactYoutubeMediaHandoff,
  writeExactYoutubeMediaHandoff,
} from "./exact-youtube-media-handoff.js?v=20260826.rebuild-clean.60";
import {
  clearExactYoutubeResearchDraft,
  exactYoutubeResearchHydration,
  readExactYoutubeResearchDraft,
} from "./exact-youtube-research-draft.js?v=20260826.rebuild-clean.60";

const RESEARCH_ROUTE = "/workspace/research";
const MEDIA_ROUTE = "/workspace/media";
const AI_ROUTE = "/workspace/ai";
const REVIEW_ROUTE = "/workspace/review";
const FAILURE_GUARD_SELECTOR = "[data-research-youtube-failure-guard]";
const RECOVERY_ROOT_ATTRIBUTE = "data-research-failure-recovery-root";
const MEDIA_HANDOFF_ATTRIBUTE = "data-youtube-media-handoff";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const PENDING_SOURCE_PREFIX = "contentengine.research.youtube.pending.v1";
const runtime = {
  queued: false,
  flushQueued: false,
  exactDraftRetryKey: "",
  exactDraftRetryCount: 0,
  exactDraftRetryTimer: 0,
  recoveryPendingSource: null,
  recoveryRenderKey: "",
};
const EXACT_DRAFT_RETRY_LIMIT = 12;
const EXACT_DRAFT_RETRY_DELAY_MS = 250;

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

function currentProjectId() {
  const value = String(routeParams().get("project_id") || "")
    .trim()
    .toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

export function researchRecoveryPaidContext({
  projectId,
  workspaceRole,
  projectFlow,
} = {}) {
  const normalizedProjectId = String(projectId || "").trim().toLowerCase();
  const role = String(workspaceRole || "").trim().toLowerCase();
  if (
    UUID_PATTERN.test(normalizedProjectId)
    && ["owner", "admin", "producer"].includes(role)
  ) {
    return {
      allowed: true,
      exactPaidAuthorizationRequired: false,
      paidTariff: null,
      scope: "project",
    };
  }

  const flow = objectValue(projectFlow);
  const capabilities = objectValue(objectValue(flow.capabilities).product_research);
  const researchContext = objectValue(flow.research_context);
  const paidTariff = objectValue(researchContext.paid_tariff);
  const operatorOwnAllowed = Boolean(
    role === "operator"
    && UUID_PATTERN.test(normalizedProjectId)
    && String(flow.project_id || "").trim().toLowerCase() === normalizedProjectId
    && capabilities.can_open === true
    && capabilities.can_start_paid_own === true
    && capabilities.can_read_own === true
    && capabilities.run_scope === "own",
  );
  return {
    allowed: operatorOwnAllowed,
    exactPaidAuthorizationRequired: true,
    paidTariff: operatorOwnAllowed && Object.keys(paidTariff).length
      ? paidTariff
      : null,
    scope: operatorOwnAllowed ? "own" : "none",
  };
}

function embeddedProjectFlowSnapshot() {
  const node = document.getElementById("workspace-project-flow-snapshot");
  try {
    return objectValue(JSON.parse(String(node?.textContent || "{}")));
  } catch {
    return {};
  }
}

function currentResearchRecoveryPaidContext(target, projectId) {
  const shell = target?.closest?.(".workspace-shell[data-workspace-role]");
  return researchRecoveryPaidContext({
    projectId,
    workspaceRole: shell?.dataset?.workspaceRole,
    projectFlow: embeddedProjectFlowSnapshot(),
  });
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

function pendingSourceKey(projectId = currentProjectId()) {
  return `${PENDING_SOURCE_PREFIX}:${projectId || "unscoped"}`;
}

function readPendingSource() {
  try {
    const raw = window.sessionStorage.getItem(pendingSourceKey());
    if (!raw) return null;
    const value = JSON.parse(raw);
    const sourceId = String(value?.source_id || "").trim().toLowerCase();
    const canonicalUrl = String(value?.canonical_url || "").trim();
    return {
      sourceId: UUID_PATTERN.test(sourceId) ? sourceId : "",
      canonicalUrl: /^https:\/\/youtube[.]com\/watch[?]v=[A-Za-z0-9_-]{11}$/u
          .test(canonicalUrl)
        ? canonicalUrl
        : "",
    };
  } catch {
    return null;
  }
}

function clearPendingSource() {
  try {
    window.sessionStorage.removeItem(pendingSourceKey());
  } catch {
    // A storage failure must not keep the terminal receipt locked on screen.
  }
}

function rememberUploadHandoff(
  sourceId,
  canonicalUrl,
  productName = "",
  productSku = "",
) {
  const context = window.ContentEngineWorkspaceRuntime
    ?.getExactYoutubeHandoffContext?.() || {};
  return writeExactYoutubeMediaHandoff(window.sessionStorage, {
    organization_id: context.organization_id,
    user_id: context.user_id,
    session_id: context.session_id,
    project_id: currentProjectId(),
    source_id: sourceId,
    canonical_url: canonicalUrl,
    product_name: productName,
    product_sku: productSku,
  });
}

function currentUploadHandoff(sourceId) {
  const context = window.ContentEngineWorkspaceRuntime
    ?.getExactYoutubeHandoffContext?.() || {};
  return readExactYoutubeMediaHandoff(window.sessionStorage, {
    organization_id: context.organization_id,
    user_id: context.user_id,
    session_id: context.session_id,
    project_id: currentProjectId(),
    source_id: sourceId,
  });
}

function currentExactResearchDraft(sourceId) {
  const context = window.ContentEngineWorkspaceRuntime
    ?.getExactYoutubeHandoffContext?.() || {};
  return readExactYoutubeResearchDraft(window.sessionStorage, {
    organization_id: context.organization_id,
    user_id: context.user_id,
    session_id: context.session_id,
    project_id: currentProjectId(),
    source_id: sourceId,
  });
}

function exactResearchFormControl(form, name) {
  return form.elements?.namedItem?.(name) || null;
}

function ensureExactResearchCategoryPlaceholder(select) {
  if (!(select instanceof HTMLSelectElement)) return;
  if (select.querySelector('option[value=""]')) return;
  const option = document.createElement("option");
  option.value = "";
  option.textContent = "Выберите категорию";
  option.disabled = true;
  select.prepend(option);
}

function clearExactResearchAcknowledgements(form) {
  for (const name of [
    "media_matches_registered_source",
    "external_ai_processing_ack",
    "paid_analysis_ack",
    "human_review_ack",
  ]) {
    const acknowledgement = exactResearchFormControl(form, name);
    if (acknowledgement instanceof HTMLInputElement) {
      acknowledgement.checked = false;
    }
  }
}

function stopExactResearchDraftRetry() {
  if (runtime.exactDraftRetryTimer) {
    window.clearTimeout(runtime.exactDraftRetryTimer);
  }
  runtime.exactDraftRetryKey = "";
  runtime.exactDraftRetryCount = 0;
  runtime.exactDraftRetryTimer = 0;
}

function scheduleExactResearchDraftRetry(form, sourceId) {
  const retryKey = `${currentProjectId()}:${sourceId}`;
  if (runtime.exactDraftRetryKey !== retryKey) {
    stopExactResearchDraftRetry();
    runtime.exactDraftRetryKey = retryKey;
  }
  if (
    runtime.exactDraftRetryTimer
    || runtime.exactDraftRetryCount >= EXACT_DRAFT_RETRY_LIMIT
  ) return;
  runtime.exactDraftRetryCount += 1;
  form.dataset.exactResearchDraftRetry = String(runtime.exactDraftRetryCount);
  runtime.exactDraftRetryTimer = window.setTimeout(() => {
    runtime.exactDraftRetryTimer = 0;
    hydrateExactYoutubeResearchDraft();
  }, EXACT_DRAFT_RETRY_DELAY_MS);
}

export function hydrateExactYoutubeResearchDraft() {
  if (routePath() !== REVIEW_ROUTE) return false;
  const params = routeParams();
  if (params.get("purpose") !== "exact_youtube_research") return false;
  const sourceId = String(params.get("youtube_source") || "")
    .trim()
    .toLowerCase();
  const form = document.getElementById("exact-youtube-research-evidence-form");
  if (!(form instanceof HTMLFormElement) || !UUID_PATTERN.test(sourceId)) {
    return false;
  }
  if (form.dataset.exactResearchDraftHydrated === "true") return true;

  const category = exactResearchFormControl(form, "product_category");
  ensureExactResearchCategoryPlaceholder(category);
  clearExactResearchAcknowledgements(form);
  const stored = currentExactResearchDraft(sourceId);
  if (stored.code === "draft_context_invalid") {
    if (category instanceof HTMLSelectElement) category.value = "";
    scheduleExactResearchDraftRetry(form, sourceId);
    return false;
  }
  stopExactResearchDraftRetry();
  form.dataset.exactResearchDraftHydrated = "true";
  if (!stored.ok) {
    if (category instanceof HTMLSelectElement) category.value = "";
    return true;
  }

  const photoRadios = [...form.querySelectorAll(
    'input[type="radio"][name="source_media_id"]',
  )].filter((input) => input instanceof HTMLInputElement);
  const baseObjective = String(
    exactResearchFormControl(form, "objective")?.value || "",
  ).trim();
  const hydration = exactYoutubeResearchHydration(
    stored.draft,
    photoRadios.map((input) => input.value),
    baseObjective,
  );

  if (category instanceof HTMLSelectElement) {
    const validCategory = [...category.options].some(
      (option) => option.value === hydration.productCategory,
    );
    category.value = validCategory ? hydration.productCategory : "";
  }
  const marketplace = exactResearchFormControl(form, "marketplace_url");
  if (marketplace instanceof HTMLInputElement && hydration.marketplaceUrl) {
    marketplace.value = hydration.marketplaceUrl;
  }
  const objective = exactResearchFormControl(form, "objective");
  if (objective instanceof HTMLTextAreaElement && hydration.objective) {
    objective.value = hydration.objective;
  }
  if (hydration.platforms.length) {
    const selected = new Set(hydration.platforms);
    form.querySelectorAll('input[type="checkbox"][name="platforms"]')
      .forEach((input) => {
        if (input instanceof HTMLInputElement) {
          input.checked = selected.has(input.value);
        }
      });
  }
  if (hydration.sourceMediaId) {
    const selectedPhoto = photoRadios.find(
      (input) => input.value === hydration.sourceMediaId,
    );
    if (selectedPhoto) selectedPhoto.checked = true;
  }

  return true;
}

function clearCompletedExactResearchDraft() {
  if (routePath() !== RESEARCH_ROUTE) return;
  const researchId = String(routeParams().get("research_id") || "")
    .trim()
    .toLowerCase();
  if (UUID_PATTERN.test(researchId)) {
    clearExactYoutubeResearchDraft(window.sessionStorage);
  }
}

function bindUploadHandoffLink(
  link,
  {
    sourceId = "",
    canonicalUrl = "",
    productName = "",
    productSku = "",
  } = {},
) {
  if (!(link instanceof HTMLAnchorElement) || link.dataset.handoffBound === "true") {
    return;
  }
  link.dataset.handoffBound = "true";
  link.addEventListener("click", (event) => {
    if (rememberUploadHandoff(
      sourceId,
      canonicalUrl,
      productName,
      productSku,
    )) return;
    event.preventDefault();
    link.setAttribute("aria-disabled", "true");
    link.title = "Контекст пользователя, проекта или вкладки изменился. Обновите экран.";
  });
}

function findAction(root, pattern) {
  return [...root.querySelectorAll("button, a")].find((node) =>
    pattern.test(String(node.textContent || "").trim())
  ) || null;
}

function sourceIdFromHref(value) {
  const raw = String(value || "");
  const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
  const id = String(new URLSearchParams(query).get("youtube_source") || "")
    .trim()
    .toLowerCase();
  return UUID_PATTERN.test(id) ? id : "";
}

export function mediaHandoffHash({
  projectId = currentProjectId(),
  sourceId = "",
  canonicalUrl = "",
  productName = "",
  productSku = "",
} = {}) {
  return hashUrl(MEDIA_ROUTE, {
    project_id: projectId,
    youtube_source: sourceId || "pending_media",
    video_url: canonicalUrl,
    product_name: productName,
    product_sku: productSku,
    return_to: hashUrl(RESEARCH_ROUTE, {
      project_id: projectId,
      recovery: "1",
    }),
  });
}

export function freshResearchHash(projectId = currentProjectId()) {
  return hashUrl(RESEARCH_ROUTE, {
    project_id: projectId,
    recovery: "1",
  });
}

function researchState() {
  const storeState = globalThis.window?.ContentEngineWorkspace?.store?.getState?.();
  return storeState?.productResearch
    || globalThis.window?.__ContentEngineLastWorkspaceState?.productResearch
    || null;
}

function normalizedResearchRecord() {
  const value = researchState();
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value.run && typeof value.run === "object" && !Array.isArray(value.run)
    ? { ...value, ...value.run }
    : value;
}

function researchDefaults() {
  const record = normalizedResearchRecord();
  const input = record.researchInput && typeof record.researchInput === "object"
    ? record.researchInput
    : record.input && typeof record.input === "object"
      ? record.input
      : {};
  return {
    productName: String(
      record.productName || record.product_name || record.product?.name || "",
    ).trim(),
    sku: String(record.sku || record.product?.sku || "").trim(),
    productCategory: String(
      input.productCategory || input.product_category || "",
    ).trim(),
    marketplaceUrl: String(
      input.marketplaceUrl || input.marketplace_url || "",
    ).trim(),
    platforms: Array.isArray(input.platforms) ? input.platforms : [],
    objective: String(input.objective || "").trim(),
    researchFocus: String(
      input.researchFocus || input.research_focus || "",
    ).trim(),
    knownFacts: String(input.knownFacts || input.known_facts || "").trim(),
    competitorReferences: "",
    sourceMediaIds: [],
  };
}

function researchTarget() {
  return document.querySelector(".research-view")
    || document.querySelector(".research-result")
    || document.querySelector("#workspace-content");
}

function scheduleDesktopFlush() {
  if (runtime.flushQueued) return;
  runtime.flushQueued = true;
  window.queueMicrotask(async () => {
    runtime.flushQueued = false;
    try {
      await window.ContentEngineDesktopV4?.flush?.();
    } catch {
      // The fresh form remains usable through the app's delegated handlers.
    }
  });
}

function recoveryBannerMarkup(projectId, pending, defaults = {}) {
  const uploadHref = mediaHandoffHash({
    projectId,
    sourceId: pending?.sourceId || "",
    canonicalUrl: pending?.canonicalUrl || "",
    productName: defaults.productName || "",
    productSku: defaults.sku || "",
  });
  return `
    <section class="research-failure-recovery-card card card-pad" role="status">
      <p class="eyebrow">ЗАПУСК ЗАКРЫТ</p>
      <h1>Ошибочный результат больше не блокирует работу</h1>
      <p>Квитанция сохранена в истории, но этот завершённый запрос убран с рабочего экрана. Повторного платного запуска нет.</p>
      <div class="research-failure-recovery-actions">
        <a class="btn btn-primary" href="${uploadHref}" data-research-recovery-upload>Загрузить MP4 и продолжить разбор ролика</a>
        <a class="btn btn-secondary" href="#product-research-start-form">Начать новое исследование без этого ролика</a>
      </div>
      <small>Ниже открыт обычный новый запуск. Ссылка Shorts в него не подставляется автоматически.</small>
    </section>`;
}

function renderFreshResearch() {
  if (routePath() !== RESEARCH_ROUTE || routeParams().get("recovery") !== "1") {
    runtime.recoveryPendingSource = null;
    runtime.recoveryRenderKey = "";
    return false;
  }
  const target = researchTarget();
  if (!(target instanceof HTMLElement)) return false;
  const projectId = currentProjectId();
  const paidContext = currentResearchRecoveryPaidContext(target, projectId);
  const renderKey = JSON.stringify({
    projectId,
    role: String(
      target.closest?.(".workspace-shell[data-workspace-role]")
        ?.dataset?.workspaceRole || "",
    ).trim().toLowerCase(),
    allowed: paidContext.allowed,
    exactPaidAuthorizationRequired: paidContext.exactPaidAuthorizationRequired,
    paidTariff: paidContext.paidTariff,
  });
  target.querySelectorAll(FAILURE_GUARD_SELECTOR).forEach((node) => node.remove());
  if (
    target.getAttribute(RECOVERY_ROOT_ATTRIBUTE) === "true"
    && runtime.recoveryRenderKey === renderKey
  ) return true;

  const pending = runtime.recoveryPendingSource || readPendingSource();
  runtime.recoveryPendingSource = pending;
  clearPendingSource();
  const defaults = researchDefaults();
  target.setAttribute(RECOVERY_ROOT_ATTRIBUTE, "true");
  runtime.recoveryRenderKey = renderKey;
  target.innerHTML = `${recoveryBannerMarkup(projectId, pending, defaults)}${
    productResearchInputMarkup({
      media: [],
      mediaLoading: false,
      notice:
        paidContext.allowed
          ? "Предыдущий terminal-failure закрыт. Заполните новый запуск либо сначала загрузите MP4. Платный запуск потребует нового ручного подтверждения."
          : "Предыдущий terminal-failure закрыт. Новый платный запуск заблокирован до получения свежего серверного допуска и тарифа.",
      defaults,
      paidTariff: paidContext.paidTariff,
      exactPaidAuthorizationRequired:
        paidContext.exactPaidAuthorizationRequired,
    })
  }`;
  target.querySelectorAll(FAILURE_GUARD_SELECTOR).forEach((node) => node.remove());
  bindUploadHandoffLink(
    target.querySelector("[data-research-recovery-upload]"),
    {
      sourceId: pending?.sourceId || "",
      canonicalUrl: pending?.canonicalUrl || "",
      productName: defaults.productName || "",
      productSku: defaults.sku || "",
    },
  );
  scheduleDesktopFlush();
  window.queueMicrotask(() => {
    target.querySelector(".research-failure-recovery-card")?.scrollIntoView?.({
      block: "start",
      behavior: "smooth",
    });
  });
  return true;
}

function repairFailureGuard() {
  if (routePath() !== RESEARCH_ROUTE || routeParams().get("recovery") === "1") {
    return;
  }
  const guard = document.querySelector(FAILURE_GUARD_SELECTOR);
  if (!(guard instanceof HTMLElement) || guard.dataset.recoveryPatched === "true") {
    return;
  }
  guard.dataset.recoveryPatched = "true";
  if (guard.dataset.failureMode === "exact-video-provider-terminal") {
    // The server-derived exact binding already points at the saved MP4.
    // Keep the intake adapter's fresh five-frame route intact: this branch
    // must never rewrite recovery into another upload or generic paid form.
    return;
  }

  const pending = readPendingSource();
  const upload = findAction(guard, /загрузить\s+mp4/iu);
  const sourceId = pending?.sourceId
    || sourceIdFromHref(upload?.getAttribute?.("href"));
  const canonicalUrl = pending?.canonicalUrl || "";
  const defaults = researchDefaults();
  if (upload instanceof HTMLAnchorElement) {
    upload.href = mediaHandoffHash({
      sourceId,
      canonicalUrl,
      productName: defaults.productName,
      productSku: defaults.sku,
    });
    upload.textContent = "Загрузить MP4 и продолжить";
    upload.dataset.researchRecoveryUpload = "true";
    bindUploadHandoffLink(upload, {
      sourceId,
      canonicalUrl,
      productName: defaults.productName,
      productSku: defaults.sku,
    });
  }

  const oldSecondary = findAction(
    guard,
    /оставить квитанцию|сохранить квитанцию|не повторять/iu,
  );
  if (oldSecondary instanceof HTMLElement) {
    const close = document.createElement("button");
    close.type = "button";
    close.className = oldSecondary.className || "btn btn-secondary";
    close.textContent = "Закрыть ошибочный запуск";
    close.dataset.researchRecoveryClose = "true";
    close.addEventListener("click", () => {
      clearPendingSource();
      window.location.hash = freshResearchHash();
      schedule();
    });
    oldSecondary.replaceWith(close);
  }

  const actions = upload?.parentElement;
  if (actions && !actions.querySelector("[data-research-recovery-fresh]")) {
    const fresh = document.createElement("button");
    fresh.type = "button";
    fresh.className = "btn btn-secondary";
    fresh.dataset.researchRecoveryFresh = "true";
    fresh.textContent = "Начать заново без ролика";
    fresh.addEventListener("click", () => {
      clearPendingSource();
      window.location.hash = freshResearchHash();
      schedule();
    });
    actions.append(fresh);
  }
}

function mediaStatus(panel, text, tone = "neutral") {
  const target = panel.querySelector("[data-youtube-media-status]");
  if (!target) return;
  target.textContent = text;
  target.dataset.tone = tone;
}

function mountMediaHandoff() {
  if (routePath() !== MEDIA_ROUTE) return;
  const params = routeParams();
  const sourceId = String(params.get("youtube_source") || "")
    .trim()
    .toLowerCase();
  if (!sourceId) return;
  const form = document.getElementById("media-upload-form");
  if (!(form instanceof HTMLFormElement)) return;
  const container = form.closest(".media-upload-panel") || form.parentElement;
  if (!(container instanceof HTMLElement)) return;
  let panel = container.querySelector(`[${MEDIA_HANDOFF_ATTRIBUTE}]`);
  if (!panel) {
    panel = document.createElement("section");
    panel.className = "youtube-media-handoff card card-pad";
    panel.setAttribute(MEDIA_HANDOFF_ATTRIBUTE, "true");
    panel.innerHTML = `
      <p class="eyebrow">ВОССТАНОВЛЕНИЕ ИССЛЕДОВАНИЯ</p>
      <h2>Загрузите именно MP4 ролика</h2>
      <p>Это настоящий экран загрузки. После выбора файла используйте штатную кнопку «Загрузить файлы в защищённую папку» ниже.</p>
      <p class="youtube-media-handoff__source"><strong>Точный источник:</strong> <code data-youtube-media-source></code></p>
      <label class="acknowledgement youtube-media-handoff__match">
        <input name="media_matches_registered_source" type="checkbox" form="media-upload-form" required />
        <span>Подтверждаю: выбранный MP4 — это тот же ролик, что зарегистрированная ссылка YouTube, а не другое видео по теме.</span>
      </label>
      <div class="youtube-media-handoff__actions">
        <button class="btn btn-primary" type="button" data-youtube-media-choose>Выбрать MP4</button>
        <a class="btn btn-secondary" data-youtube-media-back>Вернуться в Исследования</a>
      </div>
      <small data-youtube-media-status role="status" aria-live="polite">Файл ещё не выбран.</small>`;
    container.insertBefore(panel, form);
  }

  const back = panel.querySelector("[data-youtube-media-back]");
  if (back instanceof HTMLAnchorElement) {
    back.href = String(params.get("return_to") || "") || freshResearchHash();
  }
  const input = form.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) {
    mediaStatus(panel, "Форма загрузки ещё не готова. Обновите экран Файлы.", "danger");
    return;
  }
  if (!UUID_PATTERN.test(sourceId) || !currentProjectId()) {
    input.disabled = true;
    mediaStatus(
      panel,
      "Ссылка загрузки не содержит точный источник и проект. Вернитесь в ИИ-центр и откройте видео заново.",
      "danger",
    );
    return;
  }
  const initialHandoff = currentUploadHandoff(sourceId);
  if (!initialHandoff.ok) {
    input.disabled = true;
    mediaStatus(
      panel,
      initialHandoff.code === "handoff_expired"
        ? "Контекст загрузки истёк. Вернитесь в ИИ-центр и снова нажмите «Загрузить MP4» у нужного источника."
        : "Эта ссылка не была открыта из текущей вкладки ИИ-центра либо относится к другому пользователю, проекту или источнику. Откройте видеоисточник заново.",
      "danger",
    );
    return;
  }
  const sourceSnapshot = initialHandoff.handoff || {};
  const sourceLabel = panel.querySelector("[data-youtube-media-source]");
  if (sourceLabel) {
    sourceLabel.textContent = String(sourceSnapshot.canonical_url || "").trim();
  }
  [
    ["product_name", sourceSnapshot.product_name],
    ["sku", sourceSnapshot.product_sku],
  ].forEach(([name, value]) => {
    const field = form.elements.namedItem(name);
    const exactValue = String(value || "").trim();
    if (!(field instanceof HTMLInputElement) || !exactValue) return;
    field.value = exactValue;
    field.readOnly = true;
    field.dataset.exactYoutubeIdentity = "true";
  });
  const savedMediaId = String(
    initialHandoff.handoff?.progress?.media_id || "",
  ).trim().toLowerCase();
  input.accept = "video/mp4,.mp4";
  input.multiple = false;
  const kind = form.elements.namedItem("kind");
  if (kind instanceof HTMLSelectElement) {
    kind.value = "source_video";
    [...kind.options].forEach((option) => {
      option.disabled = option.value !== "source_video";
    });
    kind.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const choose = panel.querySelector("[data-youtube-media-choose]");
  if (choose instanceof HTMLButtonElement && choose.dataset.bound !== "true") {
    choose.dataset.bound = "true";
    choose.addEventListener("click", () => input.click());
  }
  if (input.dataset.youtubeHandoffBound !== "true") {
    input.dataset.youtubeHandoffBound = "true";
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (!file) {
        mediaStatus(panel, "Файл ещё не выбран.", "neutral");
        return;
      }
      const mp4 = file.type === "video/mp4"
        || file.name.toLowerCase().endsWith(".mp4");
      if (!mp4) {
        input.value = "";
        mediaStatus(panel, "Нужен MP4, а не изображение или другой формат.", "danger");
        return;
      }
      if (!currentUploadHandoff(sourceId).ok) {
        input.value = "";
        mediaStatus(
          panel,
          "Сессия загрузки изменилась. Вернитесь в ИИ-центр и откройте источник заново.",
          "danger",
        );
        return;
      }
      mediaStatus(
        panel,
        `Выбран ${file.name}. Теперь нажмите штатную кнопку загрузки ниже.`,
        "ready",
      );
    });
    form.addEventListener("submit", (event) => {
      const file = input.files?.[0];
      const mp4 = file && (
        file.type === "video/mp4" || file.name.toLowerCase().endsWith(".mp4")
      );
      const registeredRetry = UUID_PATTERN.test(String(
        currentUploadHandoff(sourceId)?.handoff?.progress?.media_id || "",
      ).trim().toLowerCase());
      if (!mp4 && !registeredRetry) {
        event.preventDefault();
        event.stopImmediatePropagation();
        mediaStatus(panel, "Сначала выберите один MP4 для этого источника.", "danger");
        input.focus();
        return;
      }
      const matchConfirmed = form.elements
        .namedItem("media_matches_registered_source");
      if (!(matchConfirmed instanceof HTMLInputElement) || !matchConfirmed.checked) {
        event.preventDefault();
        event.stopImmediatePropagation();
        mediaStatus(
          panel,
          "Подтвердите, что MP4 является именно зарегистрированным YouTube-роликом. Другой референс нужно зарегистрировать отдельно.",
          "danger",
        );
        matchConfirmed?.focus?.();
        return;
      }
      mediaStatus(
        panel,
        registeredRetry && !mp4
          ? "Повторяем только привязку уже сохранённого MP4 — новая загрузка не выполняется…"
          : "MP4 передан штатному загрузчику…",
        "ready",
      );
    }, { capture: true });
  }
  if (UUID_PATTERN.test(savedMediaId)) {
    input.required = false;
    mediaStatus(
      panel,
      "MP4 уже сохранён. Повторно подтвердите соответствие ролику и права, затем нажмите штатную кнопку — новая загрузка не выполняется.",
      "ready",
    );
  }
}

function repairAiCenterLinks() {
  if (routePath() !== AI_ROUTE) return;
  document.querySelectorAll([
    'a[href*="/workspace/board"][href*="youtube_source="]',
    'a[href*="/workspace/media"][href*="youtube_source="]',
  ].join(","))
    .forEach((link) => {
      if (!(link instanceof HTMLAnchorElement)) return;
      if (link.dataset.exactYoutubeQueueUpload === "true") return;
      const raw = link.getAttribute("href") || "";
      const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
      const params = new URLSearchParams(query);
      link.href = mediaHandoffHash({
        projectId: params.get("project_id") || currentProjectId(),
        sourceId: params.get("youtube_source") || "",
        canonicalUrl: params.get("video_url") || "",
        productName: params.get("product_name") || "",
        productSku: params.get("product_sku") || "",
      });
      link.textContent = "Загрузить MP4 и продолжить";
      link.dataset.exactYoutubeUploadFixed = "true";
      bindUploadHandoffLink(link, {
        sourceId: params.get("youtube_source") || "",
        canonicalUrl: params.get("video_url") || "",
        productName: params.get("product_name") || "",
        productSku: params.get("product_sku") || "",
      });
    });
}

function mount() {
  clearCompletedExactResearchDraft();
  if (renderFreshResearch()) return;
  repairFailureGuard();
  mountMediaHandoff();
  hydrateExactYoutubeResearchDraft();
  repairAiCenterLinks();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.queueMicrotask(() => {
    runtime.queued = false;
    mount();
  });
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "research-terminal-failure-recovery",
      mount,
      { priority: 400 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", schedule);
  window.addEventListener("hashchange", schedule);
  window.addEventListener("contentengine:workspace-rendered", schedule);
  window.queueMicrotask(schedule);
}

export const ResearchFailureRecovery = Object.freeze({
  mount,
  mediaHandoffHash,
  freshResearchHash,
  hydrateExactYoutubeResearchDraft,
});
