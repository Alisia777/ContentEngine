/* ContentEngine Desktop v4 · Finder enhancement for the real workspace board. */

const ROUTE = "/workspace/board";
const STATE_KEY = "contentengine.desktop-v4.finder.v1";
const FINDER_QUERY_KEY = "contentengine.desktop-v4.finder-query";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

const runtime = {
  queued: false,
  page: null,
  board: null,
  quickLook: null,
  movedDrawer: null,
  state: readState(),
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

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function compact(value, limit = 160) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function readState() {
  try {
    const value = JSON.parse(window.localStorage.getItem(STATE_KEY) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function remember(patch) {
  runtime.state = { ...runtime.state, ...patch };
  try { window.localStorage.setItem(STATE_KEY, JSON.stringify(runtime.state)); }
  catch { /* preference is optional */ }
}

function visible(node) {
  if (!(node instanceof Element) || node.hidden) return false;
  const style = window.getComputedStyle(node);
  return style.display !== "none" && style.visibility !== "hidden";
}

function itemKind(card) {
  const type = String(card.dataset.entityType || "").toLowerCase();
  if (type === "task") return { key: "task", label: "Задача" };
  const text = `${card.textContent} ${card.dataset.kind || ""}`.toLocaleLowerCase("ru-RU");
  if (/референс|пример|creator_reference/iu.test(text)) return { key: "reference", label: "Референс" };
  if (/видео|source_video|generated_video|video\//iu.test(text)) return { key: "video", label: "Видео" };
  if (/товар|packshot|product_photo|артикул|sku/iu.test(text)) return { key: "product", label: "Товар" };
  return { key: "unfiled", label: "Без папки" };
}

function cards() {
  return qa(".workspace-board__item", runtime.board);
}

function selectedCard() {
  return cards().find((card) => card.classList.contains("is-selected") || q('[aria-expanded="true"]', card)) || null;
}

function annotateCards() {
  cards().forEach((card) => {
    const kind = itemKind(card);
    card.dataset.ceV4Kind = kind.key;
    if (!q(":scope > .ce-v4-finder-kind", card)) {
      const badge = create("span", "ce-v4-finder-kind", kind.label);
      badge.dataset.kind = kind.key;
      card.append(badge);
    }
    card.tabIndex = -1;
  });
}

function applyView() {
  const view = runtime.state.view === "list" ? "list" : "grid";
  runtime.board.dataset.ceV4FinderView = view;
  qa("[data-ce-v4-finder-view]", runtime.board).forEach((button) => {
    const active = button.dataset.ceV4FinderView === view;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
}

function sortCards(value) {
  const grid = q(".workspace-board__grid", runtime.board);
  if (!grid) return;
  const ordered = cards().sort((left, right) => {
    if (value === "type") {
      const typeDelta = String(left.dataset.ceV4Kind || "").localeCompare(String(right.dataset.ceV4Kind || ""), "ru");
      if (typeDelta) return typeDelta;
    }
    if (value === "status") {
      const leftStatus = compact(q(".workspace-board__status", left)?.textContent, 50);
      const rightStatus = compact(q(".workspace-board__status", right)?.textContent, 50);
      const delta = leftStatus.localeCompare(rightStatus, "ru", { sensitivity: "base" });
      if (delta) return delta;
    }
    const leftTitle = compact(q(".workspace-board__item-copy strong", left)?.textContent, 200);
    const rightTitle = compact(q(".workspace-board__item-copy strong", right)?.textContent, 200);
    return leftTitle.localeCompare(rightTitle, "ru", { sensitivity: "base" });
  });
  ordered.forEach((card) => grid.append(card));
  remember({ sort: value });
}

function filterFolders(query) {
  const needle = query.trim().toLocaleLowerCase("ru-RU");
  qa(".workspace-board__folder-row", runtime.board).forEach((row) => {
    const text = compact(row.textContent, 260).toLocaleLowerCase("ru-RU");
    row.hidden = Boolean(needle && !text.includes(needle));
  });
}

function buildToolbar() {
  const content = q(".workspace-board__content", runtime.board);
  if (!content || q(":scope > .ce-v4-finder-toolbar", content)) return;
  const toolbar = create("header", "ce-v4-finder-toolbar");
  const title = create("div", "ce-v4-finder-toolbar__title");
  title.append(create("small", "", "CONTENTENGINE FINDER"), create("strong", "", "Файлы и задачи"));

  const controls = create("div", "ce-v4-finder-toolbar__controls");
  const sort = create("select", "ce-v4-finder-sort");
  sort.setAttribute("aria-label", "Сортировка объектов");
  [["name", "По имени"], ["type", "По типу"], ["status", "По статусу"]].forEach(([value, label]) => {
    const option = create("option", "", label);
    option.value = value;
    sort.append(option);
  });
  sort.value = runtime.state.sort || "name";
  const grid = create("button", "ce-v4-finder-view");
  grid.type = "button";
  grid.dataset.ceV4FinderView = "grid";
  grid.textContent = "Сетка";
  const list = create("button", "ce-v4-finder-view");
  list.type = "button";
  list.dataset.ceV4FinderView = "list";
  list.textContent = "Список";
  const upload = create("a", "ce-v4-finder-upload", "Добавить материал");
  upload.href = "#/workspace/media";
  controls.append(sort, grid, list, upload);
  toolbar.append(title, controls);
  content.prepend(toolbar);
  toolbar.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-ce-v4-finder-view]") : null;
    if (!button) return;
    remember({ view: button.dataset.ceV4FinderView });
    applyView();
  });
  sort.addEventListener("change", () => sortCards(sort.value));
}

function buildFolderSearch() {
  const sidebar = q(".workspace-board__sidebar", runtime.board);
  if (!sidebar || q(":scope > .ce-v4-folder-search", sidebar)) return;
  const label = create("label", "ce-v4-folder-search");
  const input = create("input");
  input.type = "search";
  input.placeholder = "Найти папку";
  input.setAttribute("aria-label", "Найти папку");
  label.append(input);
  const head = q(".workspace-board__sidebar-head", sidebar);
  head?.after(label);
  input.addEventListener("input", () => filterFolders(input.value));
}

function finderQueryHandoff() {
  let value = "";
  try {
    value = window.sessionStorage.getItem(FINDER_QUERY_KEY) || "";
    window.sessionStorage.removeItem(FINDER_QUERY_KEY);
  } catch { /* optional */ }
  if (!value) return;
  const form = q("#workspace-board-filter-form", runtime.board);
  const input = q('input[name="query"]', form);
  if (!form || !input) return;
  input.value = value;
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

function ensureSelectedDrawer(card) {
  if (!card) return Promise.resolve(q("[data-workspace-item-drawer]", runtime.board));
  const button = q('[data-action="open-workspace-item"]', card);
  if (button && !card.classList.contains("is-selected")) button.click();
  return new Promise((resolve) => {
    let attempts = 0;
    const read = () => {
      const drawer = q("[data-workspace-item-drawer]", runtime.board);
      if (drawer || attempts > 12) return resolve(drawer);
      attempts += 1;
      window.requestAnimationFrame(read);
    };
    read();
  });
}

async function openQuickLook(card = selectedCard() || cards().find(visible)) {
  if (runtime.quickLook || !card) return;
  const drawer = await ensureSelectedDrawer(card);
  if (!drawer) return;
  const placeholder = document.createComment("contentengine-v4-finder-drawer");
  drawer.before(placeholder);
  const backdrop = create("div", "ce-v4-quicklook-backdrop");
  const dialog = create("section", "ce-v4-quicklook");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", compact(q("h2", drawer)?.textContent || "Быстрый просмотр", 100));
  const header = create("header", "ce-v4-quicklook__header");
  const copy = create("div");
  copy.append(create("small", "", "QUICK LOOK"), create("strong", "", compact(q("h2", drawer)?.textContent || "Объект", 100)));
  const close = create("button", "ce-v4-quicklook__close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "Закрыть быстрый просмотр");
  header.append(copy, close);
  const body = create("div", "ce-v4-quicklook__body");
  body.append(drawer);
  dialog.append(header, body);
  backdrop.append(dialog);
  document.body.append(backdrop);
  runtime.quickLook = backdrop;
  runtime.movedDrawer = { drawer, placeholder, card };
  document.body.classList.add("ce-v4-quicklook-open");
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop || (event.target instanceof Element && event.target.closest(".ce-v4-quicklook__close"))) closeQuickLook();
  });
  backdrop.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeQuickLook();
    if (event.key === "ArrowLeft") navigateQuickLook(-1);
    if (event.key === "ArrowRight") navigateQuickLook(1);
  });
  close.focus({ preventScroll: true });
  if (!REDUCED_MOTION.matches && typeof dialog.animate === "function") {
    dialog.animate([{ opacity: 0, transform: "scale(.975) translateY(14px)" }, { opacity: 1, transform: "scale(1) translateY(0)" }], { duration: 360, easing: "cubic-bezier(0.16,1,0.3,1)" });
  }
}

function closeQuickLook({ restoreFocus = true } = {}) {
  const overlay = runtime.quickLook;
  const moved = runtime.movedDrawer;
  if (!overlay) return;
  q("video", overlay)?.pause?.();
  if (moved?.placeholder?.parentNode) moved.placeholder.before(moved.drawer);
  moved?.placeholder?.remove?.();
  overlay.remove();
  runtime.quickLook = null;
  runtime.movedDrawer = null;
  document.body.classList.remove("ce-v4-quicklook-open");
  if (restoreFocus) q('[data-action="open-workspace-item"]', moved?.card)?.focus({ preventScroll: true });
}

function navigateQuickLook(direction) {
  const visibleCards = cards().filter(visible);
  if (!visibleCards.length) return;
  const current = runtime.movedDrawer?.card;
  const index = Math.max(0, visibleCards.indexOf(current));
  const next = visibleCards[(index + direction + visibleCards.length) % visibleCards.length];
  closeQuickLook({ restoreFocus: false });
  window.requestAnimationFrame(() => void openQuickLook(next));
}

function bindBoard() {
  if (runtime.board.dataset.ceV4FinderBound === "true") return;
  runtime.board.dataset.ceV4FinderBound = "true";
  runtime.board.addEventListener("dblclick", (event) => {
    const card = event.target instanceof Element ? event.target.closest(".workspace-board__item") : null;
    if (card && !event.target.closest("button, a, input, select, textarea, video")) void openQuickLook(card);
  });
  runtime.board.addEventListener("keydown", (event) => {
    const editing = event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable='true']");
    if (!editing && event.key === " ") {
      event.preventDefault();
      void openQuickLook();
    }
    if (runtime.quickLook && event.key === "Escape") closeQuickLook();
  });
}

function mount() {
  if (routePath() !== ROUTE) {
    closeQuickLook({ restoreFocus: false });
    runtime.page = null;
    runtime.board = null;
    document.body.classList.remove("ce-v4-finder-route");
    return;
  }
  const board = q(".workspace-board");
  if (!board) return;
  runtime.board = board;
  runtime.page = board.closest(".page-wrap") || board.parentElement;
  document.body.classList.add("ce-v4-finder-route");
  board.dataset.ceV4Surface = "true";
  annotateCards();
  buildToolbar();
  buildFolderSearch();
  applyView();
  sortCards(q(".ce-v4-finder-sort", board)?.value || runtime.state.sort || "name");
  bindBoard();
  finderQueryHandoff();
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => { runtime.queued = false; mount(); });
}

new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
document.addEventListener("keydown", (event) => {
  if (!runtime.quickLook) return;
  if (event.key === "Escape") { event.preventDefault(); closeQuickLook(); }
  if (event.key === "ArrowLeft") { event.preventDefault(); navigateQuickLook(-1); }
  if (event.key === "ArrowRight") { event.preventDefault(); navigateQuickLook(1); }
}, true);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
else schedule();

window.ContentEngineFinderV4 = Object.freeze({ openQuickLook, closeQuickLook, schedule });
