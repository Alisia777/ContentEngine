/* ContentEngine Desktop v4 · Finder enhancement for the real workspace board. */

const ROUTE = "/workspace/board";
const STATE_KEY = "contentengine.desktop-v4.finder.v1";
const FINDER_QUERY_KEY = "contentengine.desktop-v4.finder-query";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const MOBILE_SIDEBAR = window.matchMedia("(max-width: 760px)");

const runtime = {
  page: null,
  board: null,
  sidebarOpen: false,
  quickLook: null,
  sortedBoard: null,
  sortedValue: "",
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
  node.dataset.ceV4Owned = "true";
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

function routeView() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return new URLSearchParams(raw.split("?")[1] || "").get("view") || "";
}

function annotateCards() {
  let changed = false;
  cards().forEach((card) => {
    const kind = itemKind(card);
    if (card.dataset.ceV4Kind !== kind.key) {
      card.dataset.ceV4Kind = kind.key;
      changed = true;
    }
    let badge = q(":scope > .ce-v4-finder-kind", card);
    if (!badge) {
      badge = create("span", "ce-v4-finder-kind", kind.label);
      badge.dataset.kind = kind.key;
      card.append(badge);
      changed = true;
    } else {
      if (badge.textContent !== kind.label) badge.textContent = kind.label;
      badge.dataset.kind = kind.key;
    }
    if (card.tabIndex !== -1) {
      card.tabIndex = -1;
      changed = true;
    }
    if (card.dataset.ceV4FinderAnnotated !== "true") {
      card.dataset.ceV4FinderAnnotated = "true";
      changed = true;
    }
  });
  return changed;
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
  const current = qa(":scope > .workspace-board__item", grid);
  if (ordered.some((card, index) => current[index] !== card)) {
    const fragment = document.createDocumentFragment();
    ordered.forEach((card) => fragment.append(card));
    grid.append(fragment);
  }
  runtime.sortedBoard = runtime.board;
  runtime.sortedValue = value;
  if (runtime.state.sort !== value) remember({ sort: value });
}

function filterFolders(query) {
  const needle = query.trim().toLocaleLowerCase("ru-RU");
  qa(".workspace-board__folder-row", runtime.board).forEach((row) => {
    const text = compact(row.textContent, 260).toLocaleLowerCase("ru-RU");
    row.hidden = Boolean(needle && !text.includes(needle));
  });
}

function finderMode() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  const query = new URLSearchParams(raw.split("?")[1] || "");
  return query.get("view") === "organize" ? "organize" : "browse";
}

function applyMode() {
  if (!runtime.board) return;
  const mode = finderMode();
  runtime.board.dataset.ceV4FinderMode = mode;
  document.body.dataset.ceV4FinderMode = mode;
  qa("[data-ce-v4-finder-mode]", runtime.board).forEach((control) => {
    const active = control.dataset.ceV4FinderMode === mode;
    control.classList.toggle("is-active", active);
    control.setAttribute("aria-current", active ? "page" : "false");
  });
}

function sidebarParts() {
  return {
    sidebar: q(".workspace-board__sidebar", runtime.board),
    toggle: q(".ce-v4-finder-sidebar-toggle", runtime.board),
  };
}

function setSidebarOpen(open, { restoreFocus = false } = {}) {
  const { sidebar, toggle } = sidebarParts();
  if (!sidebar) return;
  const next = MOBILE_SIDEBAR.matches && Boolean(open);
  runtime.sidebarOpen = next;
  runtime.board?.classList.toggle("is-sidebar-open", next);
  sidebar.classList.toggle("is-open", next);
  toggle?.setAttribute("aria-expanded", String(next));
  toggle?.setAttribute("aria-label", next ? "Закрыть папки" : "Показать папки");

  if (MOBILE_SIDEBAR.matches) sidebar.setAttribute("aria-hidden", String(!next));
  else sidebar.removeAttribute("aria-hidden");

  if (next) {
    (q(".ce-v4-folder-search input", sidebar) || q("button, a, input, select", sidebar))
      ?.focus({ preventScroll: true });
  } else if (restoreFocus) {
    toggle?.focus({ preventScroll: true });
  }
}

function ensureMobileSidebar() {
  const sidebar = q(".workspace-board__sidebar", runtime.board);
  const toolbarControls = q(".ce-v4-finder-toolbar__controls", runtime.board);
  if (!sidebar || !toolbarControls) return;

  if (!sidebar.id) {
    sidebar.id = "contentengine-v4-finder-sidebar";
    sidebar.dataset.ceV4RuntimeId = "true";
  }
  sidebar.setAttribute("role", "navigation");
  sidebar.setAttribute("aria-label", "Папки Finder");

  let toggle = q(".ce-v4-finder-sidebar-toggle", toolbarControls);
  if (!toggle) {
    toggle = create("button", "ce-v4-finder-sidebar-toggle", "Папки");
    toggle.type = "button";
    toggle.setAttribute("aria-controls", sidebar.id);
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Показать папки");
    toolbarControls.prepend(toggle);
    toggle.addEventListener("click", () => setSidebarOpen(!runtime.sidebarOpen, { restoreFocus: runtime.sidebarOpen }));
  }

  let close = q(".ce-v4-finder-sidebar-close", sidebar);
  if (!close) {
    close = create("button", "ce-v4-finder-sidebar-close", "×");
    close.type = "button";
    close.setAttribute("aria-label", "Закрыть папки");
    (q(".workspace-board__sidebar-head", sidebar) || sidebar).append(close);
    close.addEventListener("click", () => setSidebarOpen(false, { restoreFocus: true }));
  }

  setSidebarOpen(runtime.sidebarOpen);
}

function syncInlineDetail() {
  if (!runtime.board) return;
  const drawer = q("[data-workspace-item-drawer]", runtime.board);
  const active = Boolean(drawer && routeView() !== "trash");
  runtime.board.classList.toggle("is-detail-inline", active);
  if (!active || q(":scope > .ce-v4-finder-detail-bar", drawer)) return;

  const bar = create("header", "ce-v4-finder-detail-bar");
  const copy = create("div", "ce-v4-finder-detail-bar__copy");
  copy.append(
    create("small", "", "ФАЙЛЫ · ДЕТАЛИ"),
    create("strong", "", compact(q("h2", drawer)?.textContent || "Объект", 100)),
  );
  const back = create("button", "ce-v4-finder-detail-back", "← Назад к файлам");
  back.type = "button";
  back.addEventListener("click", () => q('[data-action="close-workspace-item"]', drawer)?.click());
  bar.append(copy, back);
  drawer.prepend(bar);
}

function buildToolbar() {
  const content = q(".workspace-board__content", runtime.board);
  if (!content) return;
  if (q(":scope > .ce-v4-finder-toolbar", content)) {
    ensureMobileSidebar();
    return;
  }
  const toolbar = create("header", "ce-v4-finder-toolbar");
  const title = create("div", "ce-v4-finder-toolbar__title");
  title.append(create("small", "", "CONTENTENGINE FINDER"), create("strong", "", "Файлы и задачи"));

  const controls = create("div", "ce-v4-finder-toolbar__controls");
  const browse = create("a", "ce-v4-finder-mode", "Просмотр");
  browse.href = "#/workspace/board?view=browse";
  browse.dataset.ceV4FinderMode = "browse";
  const organize = create("a", "ce-v4-finder-mode", "Организация");
  organize.href = "#/workspace/board?view=organize";
  organize.dataset.ceV4FinderMode = "organize";
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
  controls.append(browse, organize, sort, grid, list, upload);
  toolbar.append(title, controls);
  content.prepend(toolbar);
  toolbar.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-ce-v4-finder-view]") : null;
    if (!button) return;
    remember({ view: button.dataset.ceV4FinderView });
    applyView();
  });
  sort.addEventListener("change", () => sortCards(sort.value));
  ensureMobileSidebar();
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
  if (!card) return;
  if (runtime.quickLook) closeQuickLook({ restoreFocus: false, clearSelection: false });
  setSidebarOpen(false);
  const cardKey = String(card.dataset.workspaceItemKey || "");
  const drawer = await ensureSelectedDrawer(card);
  if (!drawer) return;
  const board = drawer.closest(".workspace-board") || q(".workspace-board");
  if (!board) return;
  const bar = create("header", "ce-v4-quicklook-inline__bar");
  const copy = create("div", "ce-v4-quicklook-inline__title");
  copy.append(
    create("small", "", "ФАЙЛЫ · ПРОСМОТР"),
    create("strong", "", compact(q("h2", drawer)?.textContent || "Объект", 100)),
  );
  const controls = create("div", "ce-v4-quicklook-inline__controls");
  const previous = create("button", "", "← Предыдущий");
  previous.type = "button";
  const next = create("button", "", "Следующий →");
  next.type = "button";
  const close = create("button", "ce-v4-quicklook-inline__close", "Назад к файлам");
  close.type = "button";
  controls.append(previous, next, close);
  bar.append(copy, controls);
  drawer.prepend(bar);
  drawer.classList.add("ce-v4-quicklook-inline");
  board.classList.remove("is-detail-inline");
  board.classList.add("is-quicklook-inline");
  runtime.quickLook = { board, drawer, bar, cardKey };
  previous.addEventListener("click", () => navigateQuickLook(-1));
  next.addEventListener("click", () => navigateQuickLook(1));
  close.addEventListener("click", () => closeQuickLook());
  close.focus({ preventScroll: true });
  if (!REDUCED_MOTION.matches && typeof drawer.animate === "function") {
    drawer.animate(
      [{ opacity: 0, transform: "translate3d(0, 8px, 0)" }, { opacity: 1, transform: "translate3d(0, 0, 0)" }],
      { duration: 190, easing: "cubic-bezier(0.16,1,0.3,1)" },
    );
  }
}

function closeQuickLook({ restoreFocus = true, clearSelection = true } = {}) {
  const current = runtime.quickLook;
  if (!current) return;
  q("video", current.drawer)?.pause?.();
  current.bar?.remove();
  current.drawer?.classList.remove("ce-v4-quicklook-inline");
  current.board?.classList.remove("is-quicklook-inline");
  runtime.quickLook = null;
  if (clearSelection) q('[data-action="close-workspace-item"]', current.drawer)?.click();
  if (restoreFocus) {
    window.requestAnimationFrame(() => {
      q(`[data-workspace-item-key="${CSS.escape(current.cardKey)}"] [data-action="open-workspace-item"]`)
        ?.focus({ preventScroll: true });
    });
  }
}

function navigateQuickLook(direction) {
  const availableCards = cards();
  if (!availableCards.length) return;
  const currentKey = runtime.quickLook?.cardKey || "";
  const index = Math.max(0, availableCards.findIndex((card) => card.dataset.workspaceItemKey === currentKey));
  const next = availableCards[(index + direction + availableCards.length) % availableCards.length];
  closeQuickLook({ restoreFocus: false, clearSelection: false });
  window.requestAnimationFrame(() => void openQuickLook(next));
}

function quickLookCardFromTarget(target) {
  if (!(target instanceof Element)) return null;
  if (target.closest(
    "input, textarea, select, a[href], [data-ce-v4-context-trigger], [data-workspace-drag-item], "
      + "button:not([data-action='open-workspace-item'])",
  )) return null;
  return target.closest(".workspace-board__item");
}

function handleBoardDoubleClick(event) {
  const card = quickLookCardFromTarget(event.target);
  if (!card) return;
  event.preventDefault();
  void openQuickLook(card);
}

function handleBoardQuickLookKeydown(event) {
  if (event.key !== "Enter" && event.key !== " ") return;
  const card = quickLookCardFromTarget(event.target);
  if (!card) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  void openQuickLook(card);
}

function handleBoardFolderSelection(event) {
  if (!MOBILE_SIDEBAR.matches || !(event.target instanceof Element)) return;
  if (!event.target.closest(".workspace-board__folder-button")) return;
  window.requestAnimationFrame(() => setSidebarOpen(false));
}

function bindBoard() {
  if (runtime.board.dataset.ceV4FinderBound === "true") return;
  runtime.board.dataset.ceV4FinderBound = "true";
  runtime.board.addEventListener("dblclick", handleBoardDoubleClick);
  runtime.board.addEventListener("keydown", handleBoardQuickLookKeydown, true);
  runtime.board.addEventListener("click", handleBoardFolderSelection);
}

function mount() {
  if (routePath() !== ROUTE) {
    setSidebarOpen(false);
    closeQuickLook({ restoreFocus: false, clearSelection: false });
    runtime.page = null;
    runtime.board = null;
    document.body.classList.remove("ce-v4-finder-route");
    delete document.body.dataset.ceV4FinderMode;
    return;
  }
  const board = q(".workspace-board");
  if (!board) return;
  if (routeView() === "trash") closeQuickLook({ restoreFocus: false, clearSelection: false });
  runtime.board = board;
  runtime.page = board.closest(".page-wrap") || board.parentElement;
  document.body.classList.add("ce-v4-finder-route");
  board.dataset.ceV4Surface = "true";
  syncInlineDetail();
  annotateCards();
  buildToolbar();
  buildFolderSearch();
  applyMode();
  applyView();
  const sortValue = q(".ce-v4-finder-sort", board)?.value || runtime.state.sort || "name";
  sortCards(sortValue);
  filterFolders(q(".ce-v4-folder-search input", board)?.value || "");
  bindBoard();
  finderQueryHandoff();
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && runtime.sidebarOpen) {
    event.preventDefault();
    setSidebarOpen(false, { restoreFocus: true });
    return;
  }
  if (!runtime.quickLook) return;
  if (event.key === "Escape") { event.preventDefault(); closeQuickLook(); }
  if (event.key === "ArrowLeft") { event.preventDefault(); navigateQuickLook(-1); }
  if (event.key === "ArrowRight") { event.preventDefault(); navigateQuickLook(1); }
}, true);

const handleSidebarViewport = () => setSidebarOpen(false);
if (typeof MOBILE_SIDEBAR.addEventListener === "function") {
  MOBILE_SIDEBAR.addEventListener("change", handleSidebarViewport);
} else {
  MOBILE_SIDEBAR.addListener?.(handleSidebarViewport);
}

window.ContentEngineDesktopV4.registerAdapter("finder-board", mount, { priority: 100 });

window.ContentEngineFinderV4 = Object.freeze({
  openQuickLook,
  closeQuickLook,
  schedule: () => window.ContentEngineDesktopV4.requestMount(),
});
