/*
 * ContentEngine · terminal research failure recovery.
 *
 * A failed paid request is already terminal, so the user must be able to leave
 * that receipt, open the real upload screen, or start a fresh research form.
 * This adapter fixes the route handoff without deleting the audit receipt and
 * without starting any provider or paid operation.
 */

import { productResearchInputMarkup } from "./product-research-view.js?v=20260810.os4.23";

const RESEARCH_ROUTE = "/workspace/research";
const MEDIA_ROUTE = "/workspace/media";
const AI_ROUTE = "/workspace/ai";
const FAILURE_GUARD_SELECTOR = "[data-research-youtube-failure-guard]";
const RECOVERY_ROOT_ATTRIBUTE = "data-research-failure-recovery-root";
const MEDIA_HANDOFF_ATTRIBUTE = "data-youtube-media-handoff";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const PENDING_SOURCE_PREFIX = "contentengine.research.youtube.pending.v1";
const runtime = {
  queued: false,
  flushQueued: false,
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

function currentProjectId() {
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

function rememberUploadHandoff(sourceId, canonicalUrl) {
  try {
    window.sessionStorage.setItem(
      "contentengine.research.youtube.upload-handoff.v1",
      JSON.stringify({
        project_id: currentProjectId(),
        source_id: sourceId,
        canonical_url: canonicalUrl,
        requested_at: new Date().toISOString(),
      }),
    );
  } catch {
    // The URL still carries the recovery context.
  }
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
} = {}) {
  return hashUrl(MEDIA_ROUTE, {
    project_id: projectId,
    youtube_source: sourceId || "pending_media",
    video_url: canonicalUrl,
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

function recoveryBannerMarkup(projectId, pending) {
  const uploadHref = mediaHandoffHash({
    projectId,
    sourceId: pending?.sourceId || "",
    canonicalUrl: pending?.canonicalUrl || "",
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
    return false;
  }
  const target = researchTarget();
  if (!(target instanceof HTMLElement)) return false;
  clearPendingSource();
  target.querySelectorAll(FAILURE_GUARD_SELECTOR).forEach((node) => node.remove());
  if (target.getAttribute(RECOVERY_ROOT_ATTRIBUTE) === "true") return true;

  const projectId = currentProjectId();
  const pending = readPendingSource();
  target.setAttribute(RECOVERY_ROOT_ATTRIBUTE, "true");
  target.innerHTML = `${recoveryBannerMarkup(projectId, pending)}${
    productResearchInputMarkup({
      media: [],
      mediaLoading: false,
      notice:
        "Предыдущий terminal-failure закрыт. Заполните новый запуск либо сначала загрузите MP4.",
      defaults: researchDefaults(),
    })
  }`;
  target.querySelectorAll(FAILURE_GUARD_SELECTOR).forEach((node) => node.remove());
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

  const pending = readPendingSource();
  const upload = findAction(guard, /загрузить\s+mp4/iu);
  const sourceId = pending?.sourceId
    || sourceIdFromHref(upload?.getAttribute?.("href"));
  const canonicalUrl = pending?.canonicalUrl || "";
  if (upload instanceof HTMLAnchorElement) {
    upload.href = mediaHandoffHash({ sourceId, canonicalUrl });
    upload.textContent = "Загрузить MP4 и продолжить";
    upload.dataset.researchRecoveryUpload = "true";
    upload.addEventListener("click", () => {
      rememberUploadHandoff(sourceId, canonicalUrl);
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
  const sourceId = String(params.get("youtube_source") || "").trim();
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
      <div class="youtube-media-handoff__actions">
        <button class="btn btn-primary" type="button" data-youtube-media-choose>Выбрать MP4</button>
        <a class="btn btn-secondary" data-youtube-media-back>Вернуться в Исследования</a>
      </div>
      <small data-youtube-media-status role="status" aria-live="polite">Файл ещё не выбран.</small>`;
    container.insertBefore(panel, form);
  }

  const canonicalUrl = String(params.get("video_url") || "").trim();
  const back = panel.querySelector("[data-youtube-media-back]");
  if (back instanceof HTMLAnchorElement) {
    back.href = String(params.get("return_to") || "") || freshResearchHash();
  }
  const input = form.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) {
    mediaStatus(panel, "Форма загрузки ещё не готова. Обновите экран Файлы.", "danger");
    return;
  }
  input.accept = "video/mp4,.mp4";
  input.multiple = false;

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
      rememberUploadHandoff(
        UUID_PATTERN.test(sourceId.toLowerCase()) ? sourceId.toLowerCase() : "",
        canonicalUrl,
      );
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
      if (!mp4) {
        event.preventDefault();
        event.stopImmediatePropagation();
        mediaStatus(panel, "Сначала выберите один MP4 для этого источника.", "danger");
        input.focus();
        return;
      }
      mediaStatus(panel, "MP4 передан штатному загрузчику…", "ready");
    }, { capture: true });
  }
}

function repairAiCenterLinks() {
  if (routePath() !== AI_ROUTE) return;
  document.querySelectorAll('a[href*="/workspace/board"][href*="youtube_source="]')
    .forEach((link) => {
      if (!(link instanceof HTMLAnchorElement)) return;
      const raw = link.getAttribute("href") || "";
      const query = raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "";
      const params = new URLSearchParams(query);
      link.href = mediaHandoffHash({
        projectId: params.get("project_id") || currentProjectId(),
        sourceId: params.get("youtube_source") || "",
      });
      link.textContent = "Загрузить MP4 и продолжить";
      link.dataset.exactYoutubeUploadFixed = "true";
    });
}

function mount() {
  if (renderFreshResearch()) return;
  repairFailureGuard();
  mountMediaHandoff();
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
});
