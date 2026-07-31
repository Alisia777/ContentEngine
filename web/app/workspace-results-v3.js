/*
 * ContentEngine OS v3 production loop.
 * Re-composes Publishing, Tasks, My Work, Results and Payouts using existing
 * application DOM. Native forms, links and server-driven actions remain the
 * authoritative controls.
 */

const core = window.ContentEngineOSV3;
if (!core) throw new Error("ContentEngineOSV3 core must load before production loop");

const {
  q, qa, elementFrom, icon, compact, escapeMarkup, routePath, remember,
  readMemory, animateIn, reducedMotion, enableSplit, pushUndo, registerAdapter,
  registerCommand, openObjectCapsule,
} = core;

const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const runtime = {
  publishingPage: null,
  taskPage: null,
  workPage: null,
  statsPage: null,
  payoutsPage: null,
};

function directChildren(node) {
  return [...(node?.children || [])];
}

function statusCopy(node) {
  return compact(q(".status-badge, .badge, .my-work-status, .my-work-overdue", node)?.textContent || "", 80);
}

function titleCopy(node) {
  return compact(q("h1, h2, h3, strong", node)?.textContent || "Рабочий объект", 140);
}

function isEditableTarget(event) {
  const target = event.target instanceof Element ? event.target : null;
  return Boolean(target?.closest("input, textarea, select, button, a, video, audio, [contenteditable='true']"));
}

function springSwap(outgoing, incoming, direction = 1) {
  if (!incoming || reducedMotion() || typeof incoming.animate !== "function") return;
  outgoing?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 26}px,0,0) scale(.985)` },
  ], { duration: 170, easing: "ease-out" });
  incoming.animate([
    { opacity: 0, transform: `translate3d(${direction * 38}px,0,0) scale(.98)`, filter: "blur(4px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.003)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 460, easing: SPRING });
}

function parseMetricNumber(value) {
  const normalized = String(value || "").replace(/[^0-9,.-]+/g, "").replace(",", ".");
  const number = Number(normalized);
  return Number.isFinite(number) ? number : 0;
}

function statsRows(table) {
  return qa("tbody tr", table).map((row, index) => {
    const cells = qa("td", row);
    return {
      row,
      index,
      title: compact(cells[0]?.querySelector("strong")?.textContent || cells[0]?.textContent || `Публикация ${index + 1}`, 120),
      platform: compact(cells[1]?.textContent || "—", 40),
      views: parseMetricNumber(cells[2]?.textContent),
      clicks: parseMetricNumber(cells[3]?.textContent),
      orders: parseMetricNumber(cells[4]?.textContent),
      revenue: parseMetricNumber(cells[5]?.textContent),
      source: compact(cells[6]?.textContent || "", 40),
      observed: compact(cells[7]?.textContent || "", 60),
      href: cells[0]?.querySelector("a")?.getAttribute("href") || "",
    };
  });
}

function resultStoryCard(item, previous) {
  const ctr = item.views > 0 ? item.clicks / item.views * 100 : 0;
  const conversion = item.clicks > 0 ? item.orders / item.clicks * 100 : 0;
  const deltaViews = previous ? item.views - previous.views : null;
  const deltaOrders = previous ? item.orders - previous.orders : null;
  return `
    <article class="results-story-card" data-results-story-index="${item.index}">
      <header><div><small>${escapeMarkup(item.platform)}</small><strong>${escapeMarkup(item.title)}</strong></div><span>${escapeMarkup(item.observed || "Последний снимок")}</span></header>
      <div class="results-story-card__metrics">
        <div><small>Просмотры</small><strong>${item.views.toLocaleString("ru-RU")}</strong>${deltaViews !== null ? `<i class="${deltaViews >= 0 ? "up" : "down"}">${deltaViews >= 0 ? "+" : ""}${deltaViews.toLocaleString("ru-RU")}</i>` : ""}</div>
        <div><small>CTR</small><strong>${ctr.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%</strong></div>
        <div><small>Заказы</small><strong>${item.orders.toLocaleString("ru-RU")}</strong>${deltaOrders !== null ? `<i class="${deltaOrders >= 0 ? "up" : "down"}">${deltaOrders >= 0 ? "+" : ""}${deltaOrders.toLocaleString("ru-RU")}</i>` : ""}</div>
        <div><small>Конверсия</small><strong>${conversion.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%</strong></div>
      </div>
      <div class="results-story-card__insight">
        <span>${icon(ctr >= 2 ? "stats" : "warning", 18)}</span>
        <p>${ctr >= 2 ? "Контент приводит измеримый трафик. Сравните первый кадр и CTA с соседними версиями." : "CTR ниже рабочего ориентира. Проверьте первый кадр, ясность оффера и соответствие площадке."}</p>
      </div>
      <footer><span>Источник: ${escapeMarkup(item.source || "ручной снимок")}</span>${item.href ? `<a href="${escapeMarkup(item.href)}" target="_blank" rel="noopener noreferrer">Открыть пост</a>` : ""}</footer>
    </article>`;
}

function mountStats() {
  if (routePath() !== "/workspace/stats") {
    document.body.classList.remove("contentengine-results-story-open");
    runtime.statsPage = null;
    return;
  }
  const table = q(".data-table");
  const page = table?.closest?.(".page-wrap");
  if (!page) return;
  runtime.statsPage = page;
  document.body.classList.add("contentengine-results-story-open");
  if (page.dataset.resultsStoryReady === "true") return;
  page.dataset.resultsStoryReady = "true";
  page.classList.add("results-story-page");
  const sections = qa(":scope > section.card", page);
  const snapshot = sections.find((section) => q("#manual-metric-form", section));
  const raw = sections.find((section) => q("table", section));
  const metrics = q(":scope > .metrics-grid", page);
  const topbar = elementFrom(`
    <header class="results-story-topbar"><div class="results-story-controls" aria-hidden="true"><i></i><i></i><i></i></div><div><small>ContentEngine · Results</small><strong>История контента</strong></div><nav><button type="button" data-results-mode="story" class="is-active">История</button><button type="button" data-results-mode="snapshot">Новый снимок</button><button type="button" data-results-mode="raw">Данные</button></nav><button type="button" data-ce-open-mission>${icon("grid", 17)}</button></header>`);
  const windowNode = elementFrom('<section class="results-story-window"><div data-results-space="story"></div><div data-results-space="snapshot" hidden></div><div data-results-space="raw" hidden></div></section>');
  const anchor = q(":scope > .workspace-page-intro", page) || page.firstElementChild;
  anchor?.after?.(topbar, windowNode);
  const story = q('[data-results-space="story"]', windowNode);
  if (metrics) story.append(metrics);
  const items = statsRows(table);
  const groups = new Map();
  items.forEach((item) => {
    const key = `${item.title}::${item.platform}`;
    const list = groups.get(key) || [];
    list.push(item);
    groups.set(key, list);
  });
  const storyGrid = elementFrom('<div class="results-story-grid"></div>');
  for (const group of groups.values()) {
    group.forEach((item, index) => storyGrid.insertAdjacentHTML("beforeend", resultStoryCard(item, group[index + 1] || null)));
  }
  story.append(storyGrid);
  if (snapshot) q('[data-results-space="snapshot"]', windowNode).append(snapshot);
  if (raw) q('[data-results-space="raw"]', windowNode).append(raw);
  let mode = String(readMemory().resultsMode || "story");
  const setMode = (next) => {
    mode = ["story", "snapshot", "raw"].includes(next) ? next : "story";
    remember({ resultsMode: mode });
    qa("[data-results-space]", windowNode).forEach((space) => {
      const active = space.dataset.resultsSpace === mode;
      space.hidden = !active;
      space.inert = !active;
    });
    qa("[data-results-mode]", topbar).forEach((button) => button.classList.toggle("is-active", button.dataset.resultsMode === mode));
  };
  topbar.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-results-mode]") : null;
    if (button) setMode(button.dataset.resultsMode);
  });
  setMode(mode);
  animateIn(windowNode);
}

registerCommand({ id: "results", title: "Открыть историю результатов", subtitle: "Просмотры, переходы, заказы и версии", icon: "stats", keywords: "результаты метрики", run() { window.location.hash = "/workspace/stats"; } });
registerAdapter("results-story-v3", mountStats);
