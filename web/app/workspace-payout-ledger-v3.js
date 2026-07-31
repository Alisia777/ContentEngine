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

function payoutRowStatus(row) {
  const text = statusCopy(row).toLocaleLowerCase("ru-RU");
  if (/выплач/u.test(text)) return "paid";
  if (/одобр/u.test(text)) return "approved";
  if (/отклон/u.test(text)) return "rejected";
  return "pending";
}

function mountPayouts() {
  if (routePath() !== "/workspace/payouts") {
    document.body.classList.remove("contentengine-payout-ledger-open");
    runtime.payoutsPage = null;
    return;
  }
  const table = q(".data-table");
  const page = table?.closest?.(".page-wrap");
  if (!page) return;
  runtime.payoutsPage = page;
  document.body.classList.add("contentengine-payout-ledger-open");
  if (page.dataset.payoutLedgerReady === "true") return;
  page.dataset.payoutLedgerReady = "true";
  page.classList.add("payout-ledger-page");
  const metrics = q(":scope > .metrics-grid", page);
  const ledgerSection = table.closest("section.card");
  const topbar = elementFrom(`
    <header class="payout-ledger-topbar"><div class="payout-ledger-controls" aria-hidden="true"><i></i><i></i><i></i></div><div><small>ContentEngine · Ledger</small><strong>Выплаты и основания</strong></div><nav><button type="button" data-payout-filter="all" class="is-active">Все</button><button type="button" data-payout-filter="pending">Проверка</button><button type="button" data-payout-filter="approved">Одобрено</button><button type="button" data-payout-filter="paid">Выплачено</button></nav><button type="button" data-ce-open-mission>${icon("grid", 17)}</button></header>`);
  const windowNode = elementFrom(`
    <section class="payout-ledger-window">
      <aside class="payout-ledger-flow"><header><small>ПРОЗРАЧНЫЙ МАРШРУТ</small><strong>От задачи до выплаты</strong></header><ol><li class="is-done"><span>1</span><div><strong>Задача выполнена</strong><small>Есть проверяемый результат</small></div></li><li><span>2</span><div><strong>Начисление создано</strong><small>Основание и сумма сохранены</small></div></li><li><span>3</span><div><strong>Решение руководителя</strong><small>Одобрено или отклонено с причиной</small></div></li><li><span>4</span><div><strong>Внешний перевод</strong><small>Номер оплаты фиксирует факт</small></div></li></ol></aside>
      <main class="payout-ledger-main"></main>
    </section>`);
  const anchor = q(":scope > .workspace-page-intro", page) || page.firstElementChild;
  anchor?.after?.(topbar, windowNode);
  if (metrics) q(".payout-ledger-main", windowNode).append(metrics);
  q(".payout-ledger-main", windowNode).append(ledgerSection);
  const rows = qa("tbody tr", table);
  rows.forEach((row) => {
    const status = payoutRowStatus(row);
    row.dataset.payoutLedgerStatus = status;
    row.classList.add("payout-ledger-row");
  });
  let filter = String(readMemory().payoutFilter || "all");
  const setFilter = (next) => {
    filter = ["all", "pending", "approved", "paid", "rejected"].includes(next) ? next : "all";
    remember({ payoutFilter: filter });
    rows.forEach((row) => row.hidden = filter !== "all" && row.dataset.payoutLedgerStatus !== filter);
    qa("[data-payout-filter]", topbar).forEach((button) => button.classList.toggle("is-active", button.dataset.payoutFilter === filter));
  };
  topbar.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-payout-filter]") : null;
    if (button) setFilter(button.dataset.payoutFilter);
  });
  setFilter(filter);
  enableSplit(windowNode, q(".payout-ledger-flow", windowNode), q(".payout-ledger-main", windowNode), "payout-ledger");
  animateIn(windowNode);
}

registerCommand({ id: "payouts", title: "Открыть Ledger выплат", subtitle: "Основание → решение → перевод", icon: "money", keywords: "деньги выплаты начисления", run() { window.location.hash = "/workspace/payouts"; } });
registerAdapter("payout-ledger-v3", mountPayouts);
