/*
 * ContentEngine · «Паспорта роликов» (/workspace/passports).
 *
 * Одна server-owned read-модель: список — creator_content_passport_registry,
 * срез одного ролика — creator_content_result_passport. Модуль ничего не
 * пишет, провайдера не зовёт, денег не трогает. Отказ загрузки не прячет
 * экран: карточка называет состояние и даёт «Повторить» (урок каскада
 * движков 26.08). Формулы метрик считаются здесь и только из числителей и
 * знаменателей сервера; нулевой знаменатель — «Недостаточно данных», никаких
 * NaN и Infinity. Deep-link: #/workspace/passports?media=<uuid>.
 */

const ROUTE = "/workspace/passports";
const ROOT_ATTRIBUTE = "data-content-passports-root";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;

const runtime = {
  loading: false,
  loadToken: 0,
  loadedKey: "",
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

function routeUuid(name) {
  const value = String(routeParams().get(name) || "").trim().toLowerCase();
  return UUID_PATTERN.test(value) ? value : "";
}

async function getApi() {
  const factory = globalThis.window?.ContentEngineWorkspaceRuntime?.getApi;
  if (typeof factory !== "function") return null;
  try {
    return (await Promise.resolve(factory())) || null;
  } catch {
    return null;
  }
}

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function moneyMinor(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  return `$${(amount / 100).toFixed(2)}`;
}

function intText(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString("ru-RU") : "—";
}

function dateTimeText(value) {
  if (!value) return "—";
  const stamp = new Date(String(value));
  return Number.isNaN(stamp.valueOf())
    ? "—"
    : stamp.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

// Формула с явными числителем и знаменателем. Ноль в знаменателе — честный
// отказ от процента, а не NaN: так требует контракт паспорта.
function ratioLine(label, numerator, denominator, { perMille = false } = {}) {
  const row = el("div", "content-passport__formula");
  row.append(el("strong", "", label));
  const numeric = Number(numerator);
  const base = Number(denominator);
  if (!Number.isFinite(numeric) || !Number.isFinite(base) || base <= 0) {
    row.append(el("span", "muted", "Недостаточно данных для расчёта"));
    return row;
  }
  const value = perMille
    ? `${((numeric / base) * 1000).toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽ / 1000`
    : `${((numeric / base) * 100).toFixed(1)}%`;
  row.append(
    el("span", "content-passport__formula-value", value),
    el(
      "span",
      "muted tiny",
      `${intText(numerator)} / ${intText(denominator)}`,
    ),
  );
  return row;
}

function statusLine(root, text, state = "info") {
  let status = root.querySelector("[data-content-passports-status]");
  if (!status) {
    status = el("p", "muted");
    status.dataset.contentPassportsStatus = "";
    root.prepend(status);
  }
  status.dataset.state = state;
  status.textContent = text;
  if (state === "error") {
    const retry = el("button", "btn btn-small", "Повторить");
    retry.type = "button";
    retry.dataset.action = "content-passports-retry";
    status.append(" ", retry);
  }
  return status;
}

function passportCard(entry) {
  const card = el("article", "content-passport-card");
  card.dataset.contentPassportCard = String(entry.media_id || "");

  const title = el(
    "h3",
    "content-passport-card__title",
    String(entry.original_filename || "Ролик"),
  );
  const product = entry.product
    ? `${entry.product.title || ""}${entry.product.sku ? ` · ${entry.product.sku}` : ""}`
    : "Товар не привязан";
  const facts = el("p", "muted tiny");
  facts.textContent = [
    product,
    entry.strategy_id ? String(entry.strategy_id) : "",
    entry.model ? String(entry.model) : "",
    Number.isFinite(Number(entry.actual_cost_minor))
      ? moneyMinor(entry.actual_cost_minor)
      : "",
    dateTimeText(entry.created_at),
  ].filter(Boolean).join(" · ");

  const metricsLine = el("p", "tiny");
  const latest = entry.latest_metrics;
  if (latest && typeof latest === "object") {
    metricsLine.textContent =
      `Просмотры ${intText(latest.views)} · клики ${intText(latest.clicks)}`
      + ` · заказы ${intText(latest.orders)}`;
  } else {
    metricsLine.className = "muted tiny";
    metricsLine.textContent = Number(entry.published_count) > 0
      ? "Метрики ещё не сняты"
      : "Публикаций пока нет";
  }

  const open = el("button", "btn btn-small", "Открыть паспорт");
  open.type = "button";
  open.dataset.action = "content-passports-open";
  open.dataset.mediaId = String(entry.media_id || "");

  card.append(title, facts, metricsLine, open);
  return card;
}

function sectionBlock(title) {
  const block = el("section", "content-passport__section");
  block.append(el("h3", "content-passport__section-title", title));
  return block;
}

function keyValue(label, value) {
  const row = el("div", "content-passport__row");
  row.append(el("span", "muted", label), el("span", "", value || "—"));
  return row;
}

function renderPassport(root, passport) {
  const view = el("div", "content-passport");
  view.dataset.contentPassportView = String(passport.media?.id || "");

  const back = el("button", "btn btn-small", "← Ко всем паспортам");
  back.type = "button";
  back.dataset.action = "content-passports-back";
  view.append(back);

  const media = passport.media || {};
  const head = sectionBlock("Ролик");
  head.append(
    keyValue("Файл", String(media.original_filename || media.id || "—")),
    keyValue(
      "Параметры",
      [
        media.duration_seconds ? `${media.duration_seconds} с` : "",
        media.resolution || "",
        media.ratio || "",
        media.audio === true ? "со звуком" : media.audio === false ? "без звука" : "",
      ].filter(Boolean).join(" · ") || "—",
    ),
    keyValue("Создан", dateTimeText(media.created_at)),
    keyValue("SHA-256", String(media.sha256 || "—").slice(0, 16) + "…"),
  );
  view.append(head);

  const why = sectionBlock("Зачем создан");
  if (passport.hypothesis) {
    why.append(keyValue("Гипотеза", String(passport.hypothesis.code || "")));
  } else {
    why.append(el(
      "p",
      "muted",
      "Гипотеза не была указана. Legacy-результат: запуск создан до появления папки «Гипотезы».",
    ));
  }
  const product = passport.product;
  why.append(keyValue(
    "Продукт",
    product ? `${product.title || ""}${product.sku ? ` · ${product.sku}` : ""}` : "—",
  ));
  view.append(why);

  const madeOf = sectionBlock("Из чего создан");
  const sources = Array.isArray(passport.sources) ? passport.sources : [];
  sources.forEach((source) => {
    if (source?.canonical_url) {
      madeOf.append(keyValue("Источник", String(source.canonical_url)));
    }
  });
  const assets = Array.isArray(passport.assets) ? passport.assets : [];
  if (assets.length) {
    assets.forEach((asset) => {
      madeOf.append(keyValue(
        String(asset.role || "материал"),
        `${asset.original_filename || asset.media_object_id || ""}`
        + ` · sha ${String(asset.sha256 || "").slice(0, 10)}…`,
      ));
    });
  } else if (!sources.length) {
    madeOf.append(el("p", "muted", "Список материалов запуска недоступен для этого legacy-наряда."));
  }
  view.append(madeOf);

  const brief = passport.brief;
  const briefBlock = sectionBlock("Задание (ТЗ)");
  if (brief) {
    briefBlock.append(
      keyValue("Версия", `v${brief.spec_version}`),
      keyValue("Платформа", String(brief.platform || "—")),
      keyValue("Утверждено", dateTimeText(brief.created_at)),
    );
    if (brief.compiled_prompt) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Точный текст задания";
      const pre = el("pre", "content-passport__prompt");
      pre.textContent = String(brief.compiled_prompt)
        + (brief.compiled_prompt_truncated ? "\n… (обрезано для экрана)" : "");
      details.append(summary, pre);
      briefBlock.append(details);
    }
  } else {
    briefBlock.append(el("p", "muted", "Версия ТЗ не сохранилась: legacy-запуск."));
  }
  view.append(briefBlock);

  const execution = passport.execution || {};
  const production = sectionBlock("Производство");
  production.append(
    keyValue("Стратегия", String(execution.strategy_id || "—")),
    keyValue("Движок", [execution.provider, execution.model].filter(Boolean).join(" · ") || "—"),
    keyValue("Оценка цены", moneyMinor(execution.estimated_cost_minor)),
    keyValue("Списано фактически", moneyMinor(execution.actual_cost_minor)),
    keyValue("Статус наряда", String(execution.job_status || "—")),
  );
  view.append(production);

  const placements = Array.isArray(passport.placements) ? passport.placements : [];
  const placementsBlock = sectionBlock("Публикации");
  if (placements.length) {
    placements.forEach((placement) => {
      placementsBlock.append(keyValue(
        String(placement.platform || "площадка"),
        `${placement.status || ""} · ${dateTimeText(placement.published_at)}`
        + (placement.final_url ? ` · ${placement.final_url}` : ""),
      ));
    });
  } else {
    placementsBlock.append(el("p", "muted", "Ролик ещё не размещался."));
  }
  view.append(placementsBlock);

  const metricsBlock = sectionBlock("Статистика");
  const metricGroups = Array.isArray(passport.metrics) ? passport.metrics : [];
  const withSnapshots = metricGroups.filter(
    (group) => Array.isArray(group?.snapshots) && group.snapshots.length,
  );
  if (withSnapshots.length) {
    if (passport._meta?.preliminary_metrics) {
      metricsBlock.append(el(
        "p",
        "muted tiny",
        "Часть снимков предварительная: с публикации ещё не прошло 72 часа.",
      ));
    }
    withSnapshots.forEach((group) => {
      const snapshots = group.snapshots;
      const latest = snapshots[snapshots.length - 1];
      metricsBlock.append(el(
        "p",
        "tiny",
        `Размещение ${String(group.placement_id || "").slice(0, 8)}…`
        + ` · снимок ${dateTimeText(latest.observed_at)}`
        + ` · ${latest.mature ? "зрелый" : "предварительный"}`,
      ));
      metricsBlock.append(
        ratioLine("CTR", latest.clicks, latest.views),
        ratioLine("Конверсия из клика в заказ", latest.orders, latest.clicks),
        ratioLine("Конверсия из просмотра в заказ", latest.orders, latest.views),
        ratioLine("Выручка на 1000 просмотров", latest.revenue_minor / 100, latest.views, { perMille: true }),
      );
    });
  } else {
    metricsBlock.append(el("p", "muted", "Снимков статистики пока нет."));
  }
  view.append(metricsBlock);

  const timeline = Array.isArray(passport.timeline) ? passport.timeline : [];
  const history = sectionBlock("История");
  if (timeline.length) {
    const list = el("ol", "content-passport__timeline");
    timeline.forEach((entry) => {
      const item = el("li", "");
      const label = entry.kind === "placement"
        ? `Опубликован (${entry.platform || "площадка"})`
        : entry.kind === "metric"
          ? "Получен снимок метрик"
          : String(entry.event || "событие");
      item.textContent = `${dateTimeText(entry.occurred_at)} — ${label}`;
      list.append(item);
    });
    history.append(list);
  } else {
    history.append(el("p", "muted", "События этого наряда не записывались."));
  }
  view.append(history);

  root.replaceChildren(view);
}

function renderRegistry(root, registry) {
  const wrap = el("div", "content-passports-list");
  wrap.dataset.contentPassportsList = "";
  const passports = Array.isArray(registry.passports) ? registry.passports : [];
  if (!passports.length) {
    wrap.append(el(
      "p",
      "muted",
      "Готовых роликов в проекте пока нет — паспорт появляется у каждого результата генерации.",
    ));
  } else {
    passports.forEach((entry) => wrap.append(passportCard(entry)));
  }
  root.replaceChildren(wrap);
}

async function load({ force = false } = {}) {
  if (routePath() !== ROUTE) return;
  const root = document.querySelector(`[${ROOT_ATTRIBUTE}]`);
  if (!(root instanceof HTMLElement)) return;
  const projectId = routeUuid("project_id");
  const mediaId = routeUuid("media");
  const loadKey = `${projectId}:${mediaId}`;
  if (!force && runtime.loadedKey === loadKey && root.dataset.contentPassportsReady === "true") {
    return;
  }
  if (runtime.loading) return;
  if (!projectId) {
    statusLine(root, "Выберите проект: паспорта живут внутри проекта.", "info");
    return;
  }
  runtime.loading = true;
  const token = runtime.loadToken + 1;
  runtime.loadToken = token;
  statusLine(
    root,
    mediaId ? "Паспорт загружается…" : "Паспорта загружаются…",
    "busy",
  );
  try {
    const api = await getApi();
    if (!api) throw new Error("workspace_api_unavailable");
    if (mediaId) {
      const passport = await api.contentResultPassport({ projectId, mediaId });
      if (runtime.loadToken !== token || routePath() !== ROUTE) return;
      renderPassport(root, passport);
    } else {
      const registry = await api.contentPassportRegistry({ projectId });
      if (runtime.loadToken !== token || routePath() !== ROUTE) return;
      renderRegistry(root, registry);
    }
    root.dataset.contentPassportsReady = "true";
    runtime.loadedKey = loadKey;
  } catch (error) {
    if (runtime.loadToken !== token) return;
    root.dataset.contentPassportsReady = "";
    runtime.loadedKey = "";
    statusLine(
      root,
      error instanceof Error && error.message && error.message !== "workspace_api_unavailable"
        ? `Паспорта не загрузились: ${error.message}`
        : "Паспорта не загрузились.",
      "error",
    );
  } finally {
    runtime.loading = false;
  }
}

function setRouteMedia(mediaId) {
  const raw = String(globalThis.window?.location?.hash || "");
  const path = raw.split("?")[0] || `#${ROUTE}`;
  const params = routeParams();
  if (mediaId) params.set("media", mediaId);
  else params.delete("media");
  const query = params.toString();
  globalThis.window.location.hash = query ? `${path}?${query}` : path;
}

function handleClick(event) {
  const target = event.target instanceof Element
    ? event.target.closest("[data-action]")
    : null;
  if (!target) return;
  const action = target.dataset.action || "";
  if (action === "content-passports-open") {
    const mediaId = String(target.dataset.mediaId || "");
    if (UUID_PATTERN.test(mediaId)) setRouteMedia(mediaId);
  } else if (action === "content-passports-back") {
    setRouteMedia("");
  } else if (action === "content-passports-retry") {
    void load({ force: true });
  }
}

function mount() {
  if (routePath() !== ROUTE) return;
  void load();
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (window.ContentEngineDesktopV4?.registerAdapter) {
    window.ContentEngineDesktopV4.registerAdapter(
      "content-passports",
      () => mount(),
      { priority: 230 },
    );
  }
  window.addEventListener("contentengine:v4-route-ready", () => mount());
  window.addEventListener(
    "hashchange",
    () => window.queueMicrotask(() => {
      // Смена media/project в query обязана перерисовать экран: ключ
      // загрузки включает обе части, поэтому просто перезапускаем load.
      void load();
    }),
  );
  document.addEventListener("click", handleClick);
  window.queueMicrotask(() => mount());
}

export const ContentPassports = Object.freeze({ mount, load });
