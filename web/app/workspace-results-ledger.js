/*
 * ContentEngine Results OS + Payout Ledger.
 * Re-composes the native metrics/forms/tables into desktop spaces. Derived
 * comparisons and issue summaries are presentation-only and use already
 * rendered data; native server forms remain untouched.
 */

const STATS_ROUTE = "/workspace/stats";
const PAYOUTS_ROUTE = "/workspace/payouts";
const STATE_KEY = "contentengine.results-ledger.v3";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";

const ICONS = Object.freeze({
  overview: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M7 15v-3M12 15V8M17 15v-6"/>',
  compare: '<path d="M4 19V9M10 19V4M16 19v-7M22 19H2"/>',
  snapshot: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/><path d="M12 4V2M12 22v-2M4 12H2M22 12h-2"/>',
  history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v6h6M12 7v5l3 2"/>',
  money: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 9h10M7 15h4"/><circle cx="16" cy="14" r="2"/>',
  issue: '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v5M12 17h.01"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
});

const runtime = {
  queued: false,
  statsPage: null,
  statsShell: null,
  payoutPage: null,
  payoutShell: null,
  memory: readMemory(),
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function routePath() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function icon(name, size = 20) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.overview}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function compact(value, limit = 100) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function readMemory() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STATE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function remember(patch) {
  runtime.memory = { ...runtime.memory, ...patch };
  try { window.localStorage.setItem(STATE_KEY, JSON.stringify(runtime.memory)); } catch { /* optional */ }
}

function parseNumber(value) {
  const normalized = String(value || "").replace(/\s+/g, "").replace(",", ".").replace(/[^\d.-]/g, "");
  const number = Number(normalized);
  return Number.isFinite(number) ? number : 0;
}

function formatDelta(value, suffix = "") {
  const number = Number(value) || 0;
  const sign = number > 0 ? "+" : number < 0 ? "−" : "";
  return `${sign}${Math.abs(number).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}${suffix}`;
}

function createTopbar(kind) {
  const stats = kind === "stats";
  const tabs = stats
    ? [["overview", "Обзор", "overview"], ["compare", "Сравнение", "compare"], ["snapshot", "Снимок", "snapshot"], ["history", "История", "history"]]
    : [["summary", "Сводка", "money"], ["ledger", "Реестр", "history"], ["issues", "Требуют решения", "issue"]];
  return elementFrom(`
    <header class="${stats ? "results-os-topbar" : "payout-ledger-topbar"}">
      <div class="results-ledger-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="results-ledger-title"><small>ContentEngine · ${stats ? "Results" : "Ledger"}</small><strong>${stats ? "Результаты" : "Выплаты"}</strong></div>
      <nav class="results-ledger-tabs" aria-label="${stats ? "Пространства результатов" : "Пространства выплат"}">
        ${tabs.map(([key, label, iconName]) => `<button type="button" data-results-ledger-tab="${key}"><span>${icon(iconName, 16)}</span><small>${label}</small></button>`).join("")}
      </nav>
      <button class="results-ledger-mission" type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 18)}</button>
    </header>`);
}

function createShell(kind) {
  const stats = kind === "stats";
  const panels = stats
    ? [["overview", "Обзор результата"], ["compare", "Сравнение версий"], ["snapshot", "Зафиксировать цифры"], ["history", "История публикаций"]]
    : [["summary", "Сводка выплат"], ["ledger", "Реестр начислений"], ["issues", "Позиции, требующие решения"]];
  return elementFrom(`
    <section class="results-ledger-shell ${stats ? "results-os-shell" : "payout-ledger-shell"}" data-results-ledger-kind="${kind}">
      <header class="results-ledger-hero">
        <div><small>${stats ? "ОТ ПУБЛИКАЦИИ К СЛЕДУЮЩЕЙ ГИПОТЕЗЕ" : "ДЕНЬГИ С ПОНЯТНЫМ ОСНОВАНИЕМ"}</small><h1>${stats ? "Что сработало" : "Прозрачный реестр"}</h1><p>${stats ? "Смотрите не только итоговые цифры: сравнивайте версии и переносите найденное преимущество в следующую генерацию." : "У каждой суммы есть задача, статус, решение и внешний факт выплаты. Банковские реквизиты в кабинете не хранятся."}</p></div>
        <div class="results-ledger-now"><small>СЕЙЧАС</small><strong data-results-ledger-now>${stats ? "Обзор результата" : "Сводка выплат"}</strong><span>${stats ? "Выберите следующий аналитический стол" : "Проверьте позиции, которые ждут решения"}</span></div>
      </header>
      <div class="results-ledger-panels">
        ${panels.map(([key, label]) => `<section class="results-ledger-panel" data-results-ledger-panel="${key}" aria-label="${label}"></section>`).join("")}
      </div>
      <footer class="results-ledger-footer"><button type="button" data-results-ledger-prev>${icon("left", 18)}<span>Назад</span></button><div><small>Пространство</small><strong data-results-ledger-position></strong></div><button type="button" data-results-ledger-next><span>Далее</span>${icon("right", 18)}</button></footer>
    </section>`);
}

function animateSwap(outgoing, incoming, direction) {
  if (!incoming || REDUCED_MOTION.matches || typeof incoming.animate !== "function") return;
  outgoing?.animate?.([
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
    { opacity: 0, transform: `translate3d(${-direction * 32}px,0,0) scale(.988)` },
  ], { duration: 175, easing: "ease-out" });
  incoming.animate([
    { opacity: 0, transform: `translate3d(${direction * 46}px,0,0) scale(.978)`, filter: "blur(5px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1.003)", filter: "blur(0)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "none" },
  ], { duration: 500, easing: SPRING });
}

function panelOrder(shell) {
  return qa(":scope > .results-ledger-panels > [data-results-ledger-panel]", shell);
}

function setPanel(shell, key, { focus = false } = {}) {
  const panels = panelOrder(shell);
  const next = panels.find((panel) => panel.dataset.resultsLedgerPanel === key) || panels[0];
  if (!next) return;
  const previous = panels.find((panel) => panel.classList.contains("is-active"));
  const previousIndex = Math.max(0, panels.indexOf(previous));
  const nextIndex = Math.max(0, panels.indexOf(next));
  panels.forEach((panel) => {
    const active = panel === next;
    panel.classList.toggle("is-active", active);
    panel.hidden = !active;
    panel.inert = !active;
    panel.setAttribute("aria-hidden", active ? "false" : "true");
  });
  const page = shell.closest(".page-wrap");
  qa("[data-results-ledger-tab]", page).forEach((button) => {
    const active = button.dataset.resultsLedgerTab === next.dataset.resultsLedgerPanel;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "page" : "false");
  });
  q("[data-results-ledger-now]", shell).textContent = next.getAttribute("aria-label") || "Рабочее пространство";
  q("[data-results-ledger-position]", shell).textContent = `${nextIndex + 1} / ${panels.length}`;
  q("[data-results-ledger-prev]", shell).disabled = nextIndex <= 0;
  q("[data-results-ledger-next]", shell).disabled = nextIndex >= panels.length - 1;
  shell.dataset.activePanel = next.dataset.resultsLedgerPanel;
  remember({ [`${shell.dataset.resultsLedgerKind}Panel`]: next.dataset.resultsLedgerPanel });
  if (previous !== next) animateSwap(previous, next, nextIndex >= previousIndex ? 1 : -1);
  if (focus) q("button, a, input, select, textarea, [tabindex]", next)?.focus({ preventScroll: true });
}

function createComparison(table) {
  const rows = qa("tbody tr", table).map((row, index) => {
    const cells = qa("td", row);
    return {
      row,
      index,
      title: compact(cells[0]?.textContent || `Публикация ${index + 1}`, 100),
      platform: compact(cells[1]?.textContent || "—", 40),
      views: parseNumber(cells[2]?.textContent),
      clicks: parseNumber(cells[3]?.textContent),
      orders: parseNumber(cells[4]?.textContent),
      revenue: parseNumber(cells[5]?.textContent),
    };
  }).filter((item) => item.title);
  const selected = [...rows].sort((a, b) => b.views - a.views).slice(0, 2);
  if (!selected.length) return elementFrom('<div class="results-ledger-empty"><strong>Сравнивать пока нечего</strong><p>После двух публикаций здесь появится честное сравнение версий.</p></div>');
  const base = selected[1] || selected[0];
  const best = selected[0];
  const viewDelta = best.views - base.views;
  const clickDelta = best.clicks - base.clicks;
  const orderDelta = best.orders - base.orders;
  const revenueDelta = best.revenue - base.revenue;
  const ctrBest = best.views ? (best.clicks / best.views) * 100 : 0;
  const ctrBase = base.views ? (base.clicks / base.views) * 100 : 0;
  return elementFrom(`
    <div class="results-os-comparison">
      <header><small>СРАВНЕНИЕ ДОСТУПНЫХ СНИМКОВ</small><h2>${escapeMarkup(best.title)}</h2><p>Сравнение строится только по уже сохранённым снимкам. Оно не подменяет источник данных и не придумывает причинность.</p></header>
      <div class="results-os-versions">
        ${selected.map((item, index) => `<article class="${index === 0 ? "is-leading" : ""}"><small>${index === 0 ? "ЛИДИРУЕТ" : "БАЗА"}</small><strong>${escapeMarkup(item.title)}</strong><span>${escapeMarkup(item.platform)}</span><dl><div><dt>Просмотры</dt><dd>${item.views.toLocaleString("ru-RU")}</dd></div><div><dt>Переходы</dt><dd>${item.clicks.toLocaleString("ru-RU")}</dd></div><div><dt>Заказы</dt><dd>${item.orders.toLocaleString("ru-RU")}</dd></div><div><dt>CTR</dt><dd>${(item.views ? (item.clicks / item.views) * 100 : 0).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%</dd></div></dl></article>`).join("")}
      </div>
      <section class="results-os-delta"><div><small>Просмотры</small><strong>${formatDelta(viewDelta)}</strong></div><div><small>Переходы</small><strong>${formatDelta(clickDelta)}</strong></div><div><small>Заказы</small><strong>${formatDelta(orderDelta)}</strong></div><div><small>CTR</small><strong>${formatDelta(ctrBest - ctrBase, " п.п.")}</strong></div><div><small>Выручка</small><strong>${formatDelta(revenueDelta, " ₽")}</strong></div></section>
      <aside><strong>Что переносим дальше</strong><p>Проверьте hook, раннее появление товара, площадку и CTA. Цифры показывают разницу, но решение о причине принимает человек.</p><a href="#/workspace/generation">Открыть следующую генерацию →</a></aside>
    </div>`);
}

function payoutIssues(table) {
  const rows = qa("tbody tr", table);
  const issues = rows.map((row, index) => {
    const cells = qa("td", row);
    const text = compact(row.textContent, 500);
    const tone = /отклон|ошиб|спор/iu.test(text) ? "danger" : /ожида|pending|одобрено|решение/iu.test(text) ? "warning" : "neutral";
    return { row, index, title: compact(cells[0]?.textContent || `Начисление ${index + 1}`, 120), amount: compact(cells[1]?.textContent || "—", 50), status: compact(cells[2]?.textContent || "—", 70), tone };
  }).filter((item) => item.tone !== "neutral");
  const wrapper = elementFrom('<div class="payout-ledger-issues"></div>');
  wrapper.innerHTML = issues.length ? `
    <header><small>ТРЕБУЮТ РЕШЕНИЯ</small><h2>${issues.length} позиций</h2><p>Откройте строку в реестре и используйте штатную форму решения. Этот список ничего не меняет сам.</p></header>
    <div>${issues.map((item) => `<button type="button" data-payout-issue-index="${item.index}" data-tone="${item.tone}"><span>${icon("issue", 18)}</span><span><strong>${escapeMarkup(item.title)}</strong><small>${escapeMarkup(item.status)}</small></span><b>${escapeMarkup(item.amount)}</b></button>`).join("")}</div>`
    : '<div class="results-ledger-empty"><strong>Спорных позиций нет</strong><p>Все видимые начисления либо завершены, либо не требуют действия.</p></div>';
  wrapper.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-payout-issue-index]") : null;
    if (!button) return;
    const row = rows[Number(button.dataset.payoutIssueIndex) || 0];
    setPanel(runtime.payoutShell, "ledger");
    window.setTimeout(() => {
      row?.scrollIntoView({ block: "center", behavior: REDUCED_MOTION.matches ? "auto" : "smooth" });
      row?.focus?.({ preventScroll: true });
      row?.classList.add("results-ledger-target");
      window.setTimeout(() => row?.classList.remove("results-ledger-target"), 1100);
    }, REDUCED_MOTION.matches ? 0 : 220);
  });
  return wrapper;
}

function wireShell(page, shell, topbar) {
  topbar.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-results-ledger-tab]") : null;
    if (button) setPanel(shell, button.dataset.resultsLedgerTab, { focus: true });
  });
  q(".results-ledger-footer", shell).addEventListener("click", (event) => {
    const panels = panelOrder(shell);
    const current = panels.findIndex((panel) => panel.classList.contains("is-active"));
    if (event.target instanceof Element && event.target.closest("[data-results-ledger-prev]") && current > 0) setPanel(shell, panels[current - 1].dataset.resultsLedgerPanel, { focus: true });
    if (event.target instanceof Element && event.target.closest("[data-results-ledger-next]") && current < panels.length - 1) setPanel(shell, panels[current + 1].dataset.resultsLedgerPanel, { focus: true });
  });
}

function mountStats() {
  if (routePath() !== STATS_ROUTE) {
    document.body.classList.remove("contentengine-results-os-open");
    runtime.statsPage = null;
    runtime.statsShell = null;
    return;
  }
  const form = q("#manual-metric-form");
  const page = form?.closest?.(".page-wrap") || q(".page-wrap");
  const metrics = q(":scope > .metrics-grid", page);
  const table = q(".data-table", page);
  if (!page || !metrics) return;
  document.body.classList.add("contentengine-results-os-open");
  runtime.statsPage = page;
  if (page.dataset.resultsOsReady === "true") return;
  page.dataset.resultsOsReady = "true";
  page.classList.add("results-os-page");
  const topbar = createTopbar("stats");
  const shell = createShell("stats");
  runtime.statsShell = shell;
  const anchor = q(":scope > .page-header", page) || page.firstElementChild;
  anchor?.after?.(topbar, shell);
  const overview = q("[data-results-ledger-panel='overview']", shell);
  const compare = q("[data-results-ledger-panel='compare']", shell);
  const snapshot = q("[data-results-ledger-panel='snapshot']", shell);
  const history = q("[data-results-ledger-panel='history']", shell);
  metrics.classList.add("results-os-native-metrics");
  overview.append(metrics);
  const snapshotCard = form?.closest("section.card");
  if (snapshotCard) snapshot.append(snapshotCard);
  const historyCard = qa(":scope > section.card", page).find((card) => card !== snapshotCard && q(".data-table", card));
  if (historyCard) history.append(historyCard);
  compare.append(table ? createComparison(table) : elementFrom('<div class="results-ledger-empty"><strong>Сравнивать пока нечего</strong><p>Нужны сохранённые результаты публикаций.</p></div>'));
  wireShell(page, shell, topbar);
  setPanel(shell, String(runtime.memory.statsPanel || "overview"));
}

function mountPayouts() {
  if (routePath() !== PAYOUTS_ROUTE) {
    document.body.classList.remove("contentengine-payout-ledger-open");
    runtime.payoutPage = null;
    runtime.payoutShell = null;
    return;
  }
  const page = q(".page-wrap");
  const metrics = q(":scope > .metrics-grid", page);
  const table = q(".data-table", page);
  const ledgerCard = table?.closest("section.card");
  if (!page || !metrics || !ledgerCard) return;
  document.body.classList.add("contentengine-payout-ledger-open");
  runtime.payoutPage = page;
  if (page.dataset.payoutLedgerReady === "true") return;
  page.dataset.payoutLedgerReady = "true";
  page.classList.add("payout-ledger-page");
  const topbar = createTopbar("payouts");
  const shell = createShell("payouts");
  runtime.payoutShell = shell;
  const anchor = q(":scope > .page-header", page) || page.firstElementChild;
  anchor?.after?.(topbar, shell);
  q("[data-results-ledger-panel='summary']", shell).append(metrics);
  q("[data-results-ledger-panel='ledger']", shell).append(ledgerCard);
  q("[data-results-ledger-panel='issues']", shell).append(payoutIssues(table));
  wireShell(page, shell, topbar);
  setPanel(shell, String(runtime.memory.payoutsPanel || "summary"));
}

function handleKeydown(event) {
  const route = routePath();
  const shell = route === STATS_ROUTE ? runtime.statsShell : route === PAYOUTS_ROUTE ? runtime.payoutShell : null;
  if (!shell || !event.altKey || event.shiftKey) return;
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest("input, textarea, select, [contenteditable='true']")) return;
  const panels = panelOrder(shell);
  const current = panels.findIndex((panel) => panel.classList.contains("is-active"));
  if (event.key === "ArrowLeft" && current > 0) {
    event.preventDefault();
    setPanel(shell, panels[current - 1].dataset.resultsLedgerPanel, { focus: true });
  }
  if (event.key === "ArrowRight" && current < panels.length - 1) {
    event.preventDefault();
    setPanel(shell, panels[current + 1].dataset.resultsLedgerPanel, { focus: true });
  }
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mountStats();
    mountPayouts();
  });
}

new MutationObserver(scheduleMount).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("keydown", handleKeydown);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
