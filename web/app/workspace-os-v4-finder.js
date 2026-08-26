/* ContentEngine Desktop v4 · Finder enhancement for the real workspace board. */

const ROUTE = "/workspace/board";
const STATE_KEY = "contentengine.desktop-v4.finder.v1";
const VIEW_STATE_PREFIX = "contentengine.desktop-v4.finder-view.v2";
const FINDER_QUERY_KEY = "contentengine.desktop-v4.finder-query";
const PROJECT_CONTEXT_KEY = "contentengine.desktop-v4.project";
const PROJECT_QUERY_KEY = "project_id";
const FOLDER_QUERY_KEY = "folder";
const FINDER_VIEWS = new Set(["grid", "list", "columns"]);
const FINDER_VIEW_LABELS = Object.freeze({
  grid: "Сетка",
  list: "Список",
  columns: "Колонки",
});
const FINDER_SORTS = new Set(["created_desc", "created_asc", "name", "type", "status"]);
const FINDER_DATE_FILTERS = new Set(["all", "today", "7d", "30d"]);
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const MOBILE_SIDEBAR = window.matchMedia("(max-width: 760px)");

const runtime = {
  page: null,
  board: null,
  sidebarOpen: false,
  quickLook: null,
  sortedBoard: null,
  sortedValue: "",
  selectedKeys: new Set(),
  selectionAnchorKey: "",
  allowApplicationOpenKey: "",
  batchBusy: false,
  ephemeralView: "grid",
  scopedViews: new Map(),
  state: readState(),
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function finderUsesOverlaySidebar() {
  const width = Math.round(runtime.board?.getBoundingClientRect?.().width || 0);
  return width > 0 ? width <= 760 : MOBILE_SIDEBAR.matches;
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

function normalizedFinderSort(value) {
  const normalized = String(value || "").trim();
  return FINDER_SORTS.has(normalized) ? normalized : "created_desc";
}

function normalizedDateFilter(value) {
  const normalized = String(value || "").trim();
  return FINDER_DATE_FILTERS.has(normalized) ? normalized : "all";
}

function readState() {
  try {
    const value = JSON.parse(window.localStorage.getItem(STATE_KEY) || "{}");
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    // v1 stored `view` globally. Never carry that unscoped preference forward:
    // it could leak one person's folder layout into a different project/session.
    const scopedState = { ...value };
    delete scopedState.view;
    if (Object.hasOwn(value, "view")) {
      try { window.localStorage.setItem(STATE_KEY, JSON.stringify(scopedState)); }
      catch { /* best-effort retirement of the old unscoped preference */ }
    }
    return scopedState;
  } catch {
    return {};
  }
}

function remember(patch) {
  runtime.state = { ...runtime.state, ...patch };
  try { window.localStorage.setItem(STATE_KEY, JSON.stringify(runtime.state)); }
  catch { /* preference is optional */ }
}

function collapsedFolderIds() {
  return new Set(
    (Array.isArray(runtime.state.collapsedFolders) ? runtime.state.collapsedFolders : [])
      .map((value) => String(value || "").trim())
      .filter(Boolean),
  );
}

function rememberCollapsedFolders(collapsed) {
  remember({ collapsedFolders: [...collapsed].sort() });
}

function finderProjectId() {
  const queryId = String(routeFinderQuery().get(PROJECT_QUERY_KEY) || "").trim();
  if (queryId) return queryId;
  const root = q("[data-project-flow-root]");
  const snapshotId = String(root?.dataset.projectId || "").trim();
  if (snapshotId) return snapshotId;
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(PROJECT_CONTEXT_KEY) || "null");
    return String(stored?.id || stored?.project_id || "").trim();
  } catch {
    return "";
  }
}

function setFolderUrl(folderId, { replace = false, projectId: projectOverride = "" } = {}) {
  const raw = String(window.location.hash || "#/workspace/board").replace(/^#/, "");
  const [path, queryString = ""] = raw.split("?");
  if ((`/${path || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") !== ROUTE) return;
  const query = new URLSearchParams(queryString);
  const projectId = String(projectOverride || finderProjectId()).trim();
  if (projectId) query.set("project_id", projectId);
  query.set("folder", String(folderId || "all"));
  const destination = `${path}${query.size ? `?${query.toString()}` : ""}`;
  const nextHash = `#${destination}`;
  if (nextHash === window.location.hash) return;
  if (replace) {
    window.location.replace(nextHash);
    return;
  }
  const navigate = window.ContentEngineDesktopV4?.navigate;
  if (typeof navigate === "function") {
    navigate(destination, { preserveProject: false });
    return;
  }
  window.location.hash = nextHash;
}

function visible(node) {
  if (!(node instanceof Element) || node.hidden) return false;
  const style = window.getComputedStyle(node);
  return style.display !== "none" && style.visibility !== "hidden";
}

function itemKind(card) {
  const type = String(card.dataset.entityType || "").toLowerCase();
  if (type === "task") return { key: "task", label: "Задача" };
  if (type === "research") return { key: "research", label: "Исследование" };
  const artifactClass = String(card.dataset.artifactClass || "").toLowerCase();
  if (artifactClass === "source") return { key: "source", label: "Источник" };
  if (artifactClass === "generated_output") return { key: "result", label: "Результат" };
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
  return cards().find((card) => runtime.selectedKeys.has(finderCardKey(card)))
    || cards().find((card) => card.classList.contains("is-selected") || q('[aria-expanded="true"]', card))
    || null;
}

function finderCardKey(card) {
  return String(card?.dataset?.workspaceItemKey || "").trim();
}

function dockFileDescriptor(card = selectedCard()) {
  const objectId = String(card?.dataset?.entityId || "").trim().toLowerCase();
  const projectId = String(finderProjectId() || "").trim().toLowerCase();
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
  if (card?.dataset?.entityType !== "media" || !uuid.test(objectId) || !uuid.test(projectId)) return null;
  return Object.freeze({
    objectId,
    projectId,
    labelOverride: compact(q(".workspace-board__item-copy strong", card)?.textContent || "Файл", 160),
  });
}

function selectedItems() {
  return cards()
    .filter((card) => runtime.selectedKeys.has(finderCardKey(card)))
    .map((card) => ({
      type: String(card.dataset.entityType || ""),
      id: String(card.dataset.entityId || ""),
      kind: String(card.dataset.entityKind || card.dataset.kind || ""),
      title: compact(q(".workspace-board__item-copy strong", card)?.textContent || "Объект", 160),
      folderId: String(card.dataset.folderId || "root"),
      source: "finder",
      node: card,
    }))
    .filter((item) => item.id && ["media", "task"].includes(item.type));
}

function selectionCards() {
  return cards().filter((card) => visible(card));
}

function ensureBatchToolbar() {
  const content = q(".workspace-board__content", runtime.board);
  if (!content) return null;
  let toolbar = q(":scope > [data-ce-v4-finder-batch]", content);
  if (toolbar) return toolbar;

  toolbar = create("section", "ce-v4-finder-batch");
  toolbar.dataset.ceV4FinderBatch = "true";
  toolbar.hidden = true;
  toolbar.setAttribute("aria-label", "Действия с выбранными объектами");

  const summary = create("strong", "ce-v4-finder-batch__summary", "Выбрано: 0");
  summary.dataset.ceV4BatchSummary = "true";
  const destination = create("select", "ce-v4-finder-batch__destination");
  destination.dataset.ceV4BatchDestination = "true";
  destination.setAttribute("aria-label", "Папка назначения");
  const placeholder = create("option", "", "Куда переместить…");
  placeholder.value = "";
  destination.append(placeholder);

  const destinations = qa(".workspace-board__folder-row[data-folder-id]", runtime.board)
    .filter((row) => (
      row.dataset.folderId !== "all"
      && !String(row.dataset.systemRole || "").trim()
      && (row.dataset.systemFolder !== "true" || row.dataset.folderId === "root")
    ));
  const seen = new Set();
  destinations.forEach((row) => {
    const id = String(row.dataset.folderId || "");
    if (!id || seen.has(id)) return;
    seen.add(id);
    const option = create("option", "", compact(q(".workspace-board__folder-button > span:nth-child(2)", row)?.textContent || id, 100));
    option.value = id;
    destination.append(option);
  });

  const move = create("button", "ce-v4-finder-batch__move", "Переместить");
  move.type = "button";
  move.dataset.ceV4BatchMove = "true";
  const trash = create("button", "ce-v4-finder-batch__trash", "В Корзину");
  trash.type = "button";
  trash.dataset.ceV4BatchTrash = "true";
  const clear = create("button", "ce-v4-finder-batch__clear", "Снять выбор");
  clear.type = "button";
  clear.dataset.ceV4BatchClear = "true";
  const status = create("span", "ce-v4-finder-batch__status");
  status.dataset.ceV4BatchStatus = "true";
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  toolbar.append(summary, destination, move, trash, clear, status);

  const anchor = q(".workspace-board__breadcrumb", content)
    || q("#workspace-board-filter-form", content)
    || content.firstElementChild;
  if (anchor) anchor.insertAdjacentElement("afterend", toolbar);
  else content.prepend(toolbar);
  return toolbar;
}

function setBatchStatus(message, tone = "") {
  const status = q("[data-ce-v4-batch-status]", runtime.board);
  if (!status) return;
  status.textContent = String(message || "");
  status.dataset.tone = tone;
}

function syncSelectionDom() {
  if (!runtime.board) return;
  const currentKeys = new Set(cards().map(finderCardKey).filter(Boolean));
  [...runtime.selectedKeys].forEach((key) => {
    if (!currentKeys.has(key)) runtime.selectedKeys.delete(key);
  });
  cards().forEach((card) => {
    const key = finderCardKey(card);
    const selected = Boolean(key && runtime.selectedKeys.has(key));
    card.classList.toggle("is-multi-selected", selected);
    card.dataset.selected = String(selected);
    card.setAttribute("aria-selected", String(selected));
    const button = q("[data-ce-v4-select-item]", card);
    button?.setAttribute("aria-pressed", String(selected));
    if (button) {
      const title = compact(q(".workspace-board__item-copy strong", card)?.textContent || "объект", 100);
      button.setAttribute("aria-label", `${selected ? "Снять выбор" : "Выбрать"}: ${title}`);
      button.title = selected ? "Снять выбор" : "Выбрать для группового действия";
    }
  });
  syncQuickLookControl();
  syncColumnsProjection();
  const toolbar = ensureBatchToolbar();
  if (!toolbar) return;
  const count = runtime.selectedKeys.size;
  toolbar.hidden = count === 0;
  q("[data-ce-v4-batch-summary]", toolbar).textContent = `Выбрано: ${count}`;
  qa("button, select", toolbar).forEach((control) => { control.disabled = runtime.batchBusy; });
}

function clearSelection({ restoreFocus = false } = {}) {
  const anchor = runtime.selectionAnchorKey;
  runtime.selectedKeys.clear();
  runtime.selectionAnchorKey = "";
  setBatchStatus("");
  syncSelectionDom();
  if (restoreFocus && anchor) {
    q(`[data-workspace-item-key="${CSS.escape(anchor)}"] [data-ce-v4-select-item]`, runtime.board)
      ?.focus({ preventScroll: true });
  }
}

function selectCard(card, event = {}) {
  const key = finderCardKey(card);
  if (!key) return;
  const available = selectionCards();
  const additive = Boolean(event.ctrlKey || event.metaKey);
  if (event.shiftKey) {
    const anchorIndex = available.findIndex((item) => finderCardKey(item) === runtime.selectionAnchorKey);
    const targetIndex = available.indexOf(card);
    if (!additive) runtime.selectedKeys.clear();
    if (anchorIndex >= 0 && targetIndex >= 0) {
      const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex];
      available.slice(start, end + 1).forEach((item) => runtime.selectedKeys.add(finderCardKey(item)));
    } else {
      runtime.selectedKeys.add(key);
    }
  } else if (additive || event.fromSelectionControl) {
    if (runtime.selectedKeys.has(key)) runtime.selectedKeys.delete(key);
    else runtime.selectedKeys.add(key);
    runtime.selectionAnchorKey = key;
  } else {
    runtime.selectedKeys.clear();
    runtime.selectedKeys.add(key);
    runtime.selectionAnchorKey = key;
  }
  if (!runtime.selectionAnchorKey) runtime.selectionAnchorKey = key;
  syncSelectionDom();
}

function finderCardTitle(card) {
  return compact(q(".workspace-board__item-copy strong", card)?.textContent || "Объект", 140);
}

function finderCardCreatedTimestamp(card) {
  const timestamp = Date.parse(String(card?.dataset?.createdAt || ""));
  return Number.isFinite(timestamp) ? timestamp : null;
}

function finderCardSubtitle(card) {
  return compact(
    q(".workspace-board__item-copy > span", card)?.textContent
      || q(".workspace-board__status", card)?.textContent
      || "",
    180,
  );
}

function finderFolderTitle(folderId) {
  const id = String(folderId || "all").trim() || "all";
  const row = q(`.workspace-board__folder-row[data-folder-id="${CSS.escape(id)}"]`, runtime.board);
  return compact(
    q(".workspace-board__folder-button > span:nth-child(2)", row)?.textContent
      || row?.textContent
      || (id === "all" ? "Все объекты" : id === "root" ? "Без папки" : "Текущая папка"),
    100,
  );
}

function finderColumnHeading(kicker, title) {
  const heading = create("header", "ce-v4-finder-column__heading");
  heading.append(
    create("small", "", kicker),
    create("strong", "", title),
  );
  return heading;
}

function finderColumnRow(label, value, className = "") {
  const row = create("div", `ce-v4-finder-column__row ${className}`.trim());
  row.append(create("small", "", label), create("strong", "", value));
  return row;
}

function finderCardPreviewSource(card) {
  const image = q(".workspace-board__item-preview img", card);
  const candidate = String(image?.currentSrc || image?.getAttribute("src") || "").trim();
  if (!candidate) return "";
  try {
    const parsed = new URL(candidate, window.location.href);
    const localHttp = parsed.protocol === "http:" && parsed.origin === window.location.origin;
    return parsed.protocol === "https:" || parsed.protocol === "blob:" || localHttp
      ? parsed.href
      : "";
  } catch {
    return "";
  }
}

function finderColumnVisual(card, kind) {
  const visual = create("figure", "ce-v4-finder-column__visual");
  visual.dataset.kind = kind.key;
  const source = finderCardPreviewSource(card);
  if (source) {
    const image = create("img", "ce-v4-finder-column__image");
    image.src = source;
    image.alt = "";
    image.loading = "lazy";
    image.decoding = "async";
    visual.append(image);
  } else {
    const glyph = create("span", "ce-v4-finder-column__glyph", kind.key === "video" ? "▶" : kind.key === "research" ? "✦" : "◇");
    glyph.dataset.kind = kind.key;
    visual.append(glyph);
  }
  visual.append(create("figcaption", "ce-v4-finder-column__visual-label", kind.label));
  return visual;
}

function ensureColumnsProjection() {
  const grid = q(".workspace-board__grid", runtime.board);
  if (!grid) return null;
  let hierarchy = q(":scope > [data-ce-v4-finder-column='hierarchy']", grid);
  let preview = q(":scope > [data-ce-v4-finder-column='preview']", grid);
  if (!hierarchy) {
    hierarchy = create("section", "ce-v4-finder-column ce-v4-finder-column--hierarchy");
    hierarchy.dataset.ceV4FinderColumn = "hierarchy";
    hierarchy.setAttribute("role", "presentation");
    hierarchy.setAttribute("aria-hidden", "true");
    grid.append(hierarchy);
  }
  if (!preview) {
    preview = create("aside", "ce-v4-finder-column ce-v4-finder-column--preview");
    preview.dataset.ceV4FinderColumn = "preview";
    preview.setAttribute("role", "presentation");
    preview.setAttribute("aria-hidden", "true");
    grid.append(preview);
  }
  return { grid, hierarchy, preview };
}

function removeColumnsProjection() {
  qa("[data-ce-v4-finder-column]", runtime.board).forEach((column) => column.remove());
}

function syncQuickLookControl() {
  const button = q("[data-ce-v4-finder-quicklook]", runtime.board);
  if (!button) return;
  const card = selectedCard();
  button.disabled = !card;
  button.setAttribute("aria-disabled", String(!card));
  button.title = card
    ? `Быстрый просмотр: ${finderCardTitle(card)}`
    : "Сначала выберите объект";
}

function syncColumnsProjection() {
  if (!runtime.board || currentFinderView() !== "columns") return;
  const projection = ensureColumnsProjection();
  if (!projection) return;
  const { grid, hierarchy, preview } = projection;
  // A sparse folder still needs a readable column canvas. Extra implicit rows
  // are visual space only; they never imply or manufacture child objects.
  const rowCount = Math.max(6, cards().length);
  hierarchy.style.gridRow = `1 / span ${rowCount}`;
  preview.style.gridRow = `1 / span ${rowCount}`;

  const card = selectedCard();
  const currentFolderId = finderFolderId();
  const currentFolderTitle = finderFolderTitle(currentFolderId);
  const hierarchyPanel = create("div", "ce-v4-finder-column__panel");
  hierarchyPanel.append(
    finderColumnHeading("ИЕРАРХИЯ", currentFolderTitle),
    finderColumnRow("Текущая папка", currentFolderTitle, "is-folder"),
  );
  if (card) {
    const itemFolderId = String(card.dataset.folderId || currentFolderId || "root");
    hierarchyPanel.append(
      create("span", "ce-v4-finder-column__connector", "↓"),
      finderColumnRow(itemKind(card).label, finderCardTitle(card), "is-current"),
      finderColumnRow("Расположение", finderFolderTitle(itemFolderId)),
    );
  } else {
    hierarchyPanel.append(create(
      "p",
      "ce-v4-finder-column__empty",
      "Выберите объект в первой колонке — его положение появится здесь.",
    ));
  }
  hierarchy.replaceChildren(hierarchyPanel);

  const previewPanel = create("div", "ce-v4-finder-column__panel ce-v4-finder-column__panel--preview");
  if (!card) {
    previewPanel.append(
      finderColumnHeading("ПРЕДПРОСМОТР", "Объект не выбран"),
      create("p", "ce-v4-finder-column__empty", "Один клик выбирает объект. Space открывает Quick Look без смены маршрута."),
    );
  } else {
    const kind = itemKind(card);
    const status = compact(q(".workspace-board__status", card)?.textContent || "—", 80);
    previewPanel.append(
      finderColumnHeading("ПРЕДПРОСМОТР", finderCardTitle(card)),
      finderColumnVisual(card, kind),
      finderCardSubtitle(card)
        ? create("p", "ce-v4-finder-column__summary", finderCardSubtitle(card))
        : create("p", "ce-v4-finder-column__summary", "Метаданные объекта доступны без открытия нового маршрута."),
      finderColumnRow("Тип", kind.label),
      finderColumnRow("Статус", status),
      finderColumnRow("Доступ", card.dataset.readOnly === "true" ? "Только чтение" : "По правам проекта"),
      create("p", "ce-v4-finder-column__hint", "Enter — открыть · Space — Quick Look"),
    );
  }
  preview.replaceChildren(previewPanel);
  // Sorting may move canonical cards. Keep only the runtime projection after
  // them; never move or replace a business-owned item node.
  if (grid.lastElementChild !== preview || preview.previousElementSibling !== hierarchy) {
    grid.append(hierarchy, preview);
  }
}

function refreshFinderBoard() {
  q("#workspace-board-filter-form", runtime.board)
    ?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

async function moveSelectedItems(destinationFolderId = "") {
  const items = selectedItems();
  const destination = String(
    destinationFolderId || q("[data-ce-v4-batch-destination]", runtime.board)?.value || "",
  );
  if (!items.length) return;
  if (!destination) {
    setBatchStatus("Выберите папку назначения.", "error");
    q("[data-ce-v4-batch-destination]", runtime.board)?.focus({ preventScroll: true });
    return;
  }
  const api = window.ContentEngineWorkspaceRuntime?.getApi?.();
  if (!api?.moveWorkspaceItems) {
    setBatchStatus("Перемещение сейчас недоступно.", "error");
    return;
  }
  runtime.batchBusy = true;
  setBatchStatus("Перемещаем…");
  syncSelectionDom();
  try {
    await api.moveWorkspaceItems(
      items.map(({ type, id }) => ({ type, id })),
      destination === "root" ? null : destination,
      { projectId: finderProjectId() },
    );
    clearSelection();
    refreshFinderBoard();
  } catch (error) {
    setBatchStatus(error?.message || "Не удалось переместить выбранные объекты.", "error");
  } finally {
    runtime.batchBusy = false;
    syncSelectionDom();
  }
}

async function trashSelectedItems() {
  const items = selectedItems();
  if (!items.length || !window.ContentEngineTrashV4?.trash) return;
  runtime.batchBusy = true;
  setBatchStatus("Перемещаем в Корзину…");
  syncSelectionDom();
  try {
    await window.ContentEngineTrashV4.trash(items);
    clearSelection();
  } catch (error) {
    setBatchStatus(error?.message || "Не удалось переместить выбранные объекты в Корзину.", "error");
  } finally {
    runtime.batchBusy = false;
    syncSelectionDom();
  }
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
  const view = currentFinderView();
  runtime.board.dataset.ceV4FinderView = view;
  qa("[data-ce-v4-finder-view]", runtime.board).forEach((button) => {
    const active = button.dataset.ceV4FinderView === view;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (view === "columns") syncColumnsProjection();
  else removeColumnsProjection();
  syncQuickLookControl();
  syncFinderControlStatus();
}

function sortCards(value) {
  const grid = q(".workspace-board__grid", runtime.board);
  if (!grid) return;
  const normalizedValue = normalizedFinderSort(value);
  const ordered = cards().sort((left, right) => {
    if (normalizedValue === "created_desc" || normalizedValue === "created_asc") {
      const leftCreatedAt = finderCardCreatedTimestamp(left);
      const rightCreatedAt = finderCardCreatedTimestamp(right);
      if (leftCreatedAt === null && rightCreatedAt !== null) return 1;
      if (leftCreatedAt !== null && rightCreatedAt === null) return -1;
      if (leftCreatedAt !== null && rightCreatedAt !== null && leftCreatedAt !== rightCreatedAt) {
        return normalizedValue === "created_desc"
          ? rightCreatedAt - leftCreatedAt
          : leftCreatedAt - rightCreatedAt;
      }
    }
    if (normalizedValue === "type") {
      const typeDelta = String(left.dataset.ceV4Kind || "").localeCompare(String(right.dataset.ceV4Kind || ""), "ru");
      if (typeDelta) return typeDelta;
    }
    if (normalizedValue === "status") {
      const leftStatus = compact(q(".workspace-board__status", left)?.textContent, 50);
      const rightStatus = compact(q(".workspace-board__status", right)?.textContent, 50);
      const delta = leftStatus.localeCompare(rightStatus, "ru", { sensitivity: "base" });
      if (delta) return delta;
    }
    const titleDelta = finderCardTitle(left).localeCompare(finderCardTitle(right), "ru", { sensitivity: "base" });
    return titleDelta || finderCardKey(left).localeCompare(finderCardKey(right), "ru");
  });
  const current = qa(":scope > .workspace-board__item", grid);
  if (ordered.some((card, index) => current[index] !== card)) {
    const fragment = document.createDocumentFragment();
    ordered.forEach((card) => fragment.append(card));
    grid.append(fragment);
  }
  runtime.sortedBoard = runtime.board;
  runtime.sortedValue = normalizedValue;
  if (runtime.state.sort !== normalizedValue) remember({ sort: normalizedValue });
  if (currentFinderView() === "columns") syncColumnsProjection();
}

function dateFilterCutoff(value, now = new Date()) {
  const normalizedValue = normalizedDateFilter(value);
  if (normalizedValue === "all") return null;
  const cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = normalizedValue === "today" ? 0 : normalizedValue === "7d" ? 6 : 29;
  cutoff.setDate(cutoff.getDate() - days);
  return cutoff.getTime();
}

function applyDateFilter(value) {
  if (!runtime.board) return;
  const normalizedValue = normalizedDateFilter(value);
  const cutoff = dateFilterCutoff(normalizedValue);
  const visibleKeys = new Set();
  cards().forEach((card) => {
    const createdAt = finderCardCreatedTimestamp(card);
    const matches = cutoff === null || (createdAt !== null && createdAt >= cutoff);
    card.hidden = !matches;
    if (matches) visibleKeys.add(finderCardKey(card));
  });
  [...runtime.selectedKeys].forEach((key) => {
    if (!visibleKeys.has(key)) runtime.selectedKeys.delete(key);
  });
  const control = q(".ce-v4-finder-date-filter", runtime.board);
  if (control && control.value !== normalizedValue) control.value = normalizedValue;
  if (runtime.state.dateFilter !== normalizedValue) remember({ dateFilter: normalizedValue });
  syncSelectionDom();
  syncFinderControlStatus();
}

function filterFolders(query) {
  const needle = query.trim().toLocaleLowerCase("ru-RU");
  qa(".workspace-board__folder-row", runtime.board).forEach((row) => {
    const text = compact(row.textContent, 260).toLocaleLowerCase("ru-RU");
    row.hidden = Boolean(needle && !text.includes(needle));
  });
}

function applyFolderTreeState() {
  if (!runtime.board) return;
  const collapsed = collapsedFolderIds();
  qa("[data-folder-branch]", runtime.board).forEach((branch) => {
    const folderId = String(branch.dataset.folderBranch || "");
    const hidden = collapsed.has(folderId);
    branch.hidden = hidden;
    const row = q(`.workspace-board__folder-row[data-folder-id="${CSS.escape(folderId)}"]`, runtime.board);
    row?.classList.toggle("is-collapsed", hidden);
    const toggle = q(`[data-folder-toggle="${CSS.escape(folderId)}"]`, row);
    toggle?.setAttribute("aria-expanded", String(!hidden));
    if (toggle) {
      const name = compact(q(".workspace-board__folder-button > span:nth-child(2)", row)?.textContent || "папку", 80);
      toggle.setAttribute("aria-label", `${hidden ? "Развернуть" : "Свернуть"} папку «${name}»`);
    }
  });
}

function revealFolderAncestors(row) {
  if (!(row instanceof Element)) return;
  const collapsed = collapsedFolderIds();
  let changed = false;
  let branch = row.parentElement?.closest?.("[data-folder-branch]");
  while (branch) {
    const folderId = String(branch.dataset.folderBranch || "");
    if (collapsed.delete(folderId)) changed = true;
    branch = branch.parentElement?.closest?.("[data-folder-branch]");
  }
  if (changed) rememberCollapsedFolders(collapsed);
  applyFolderTreeState();
}

function toggleFolderBranch(folderId) {
  const id = String(folderId || "").trim();
  if (!id) return;
  const collapsed = collapsedFolderIds();
  if (collapsed.has(id)) collapsed.delete(id);
  else collapsed.add(id);
  rememberCollapsedFolders(collapsed);
  applyFolderTreeState();
}

function finderMode() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  const query = new URLSearchParams(raw.split("?")[1] || "");
  return query.get("view") === "organize" || query.get("create") === "project"
    ? "organize"
    : "browse";
}

function syncFinderControlStatus() {
  if (!runtime.board) return;
  const mode = finderMode();
  const viewLabel = FINDER_VIEW_LABELS[currentFinderView()] || FINDER_VIEW_LABELS.grid;
  const modeLabel = mode === "organize" ? "Организация" : "Просмотр";
  const allCards = cards();
  const dateFilter = normalizedDateFilter(
    q(".ce-v4-finder-date-filter", runtime.board)?.value || runtime.state.dateFilter,
  );
  const periodStatus = dateFilter === "all"
    ? ""
    : ` · ${allCards.filter((card) => !card.hidden).length} из ${allCards.length} загруженных`;
  const statusText = `${modeLabel} · вид «${viewLabel}»${periodStatus}`;
  const status = q("[data-ce-v4-finder-control-status]", runtime.board);
  if (status && status.textContent !== statusText) status.textContent = statusText;

  const empty = q(".workspace-board__empty", runtime.board);
  if (!empty) return;
  let hint = q(":scope > [data-ce-v4-finder-empty-mode]", empty);
  if (!hint) {
    hint = create("p", "ce-v4-finder-empty-mode");
    hint.dataset.ceV4FinderEmptyMode = "true";
    empty.append(hint);
  }
  const hintText = mode === "organize"
    ? `Организация включена · вид «${viewLabel}». Добавьте материал — затем его можно будет раскладывать по папкам.`
    : `Просмотр · вид «${viewLabel}».`;
  if (hint.textContent !== hintText) hint.textContent = hintText;
}

function applyMode() {
  if (!runtime.board) return;
  const mode = finderMode();
  runtime.board.dataset.ceV4FinderMode = mode;
  document.body.dataset.ceV4FinderMode = mode;
  qa("[data-ce-v4-finder-mode]", runtime.board).forEach((control) => {
    const active = control.dataset.ceV4FinderMode === mode;
    control.classList.toggle("is-active", active);
    control.setAttribute("aria-pressed", String(active));
  });
  syncFinderControlStatus();
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
  const compact = finderUsesOverlaySidebar();
  const next = compact && Boolean(open);
  runtime.sidebarOpen = next;
  runtime.board?.classList.toggle("is-sidebar-open", next);
  sidebar.classList.toggle("is-open", next);
  toggle?.setAttribute("aria-expanded", String(next));
  toggle?.setAttribute("aria-label", next ? "Закрыть папки" : "Показать папки");

  if (compact) sidebar.setAttribute("aria-hidden", String(!next));
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
  const existing = q(":scope > .ce-v4-finder-toolbar", content);
  if (existing) {
    ensureMobileSidebar();
    return;
  }
  const toolbar = create("header", "ce-v4-finder-toolbar");
  const title = create("div", "ce-v4-finder-toolbar__title");
  const controlStatus = create("span", "ce-v4-finder-control-status");
  controlStatus.dataset.ceV4FinderControlStatus = "true";
  controlStatus.setAttribute("role", "status");
  controlStatus.setAttribute("aria-live", "polite");
  title.append(create("small", "", "CONTENTENGINE FINDER"), create("strong", "", "Файлы и папки"), controlStatus);

  const controls = create("div", "ce-v4-finder-toolbar__controls");
  const browse = create("button", "ce-v4-finder-mode", "Просмотр");
  browse.type = "button";
  browse.dataset.action = "finder-mode";
  browse.dataset.ceV4FinderMode = "browse";
  const organize = create("button", "ce-v4-finder-mode", "Организация");
  organize.type = "button";
  organize.dataset.action = "finder-mode";
  organize.dataset.ceV4FinderMode = "organize";
  const sort = create("select", "ce-v4-finder-sort");
  sort.dataset.action = "finder-sort";
  sort.setAttribute("aria-label", "Сортировка объектов");
  [["created_desc", "Сначала новые"], ["created_asc", "Сначала старые"], ["name", "По имени"], ["type", "По типу"], ["status", "По статусу"]].forEach(([value, label]) => {
    const option = create("option", "", label);
    option.value = value;
    sort.append(option);
  });
  sort.value = normalizedFinderSort(runtime.state.sort);
  const dateFilter = create("select", "ce-v4-finder-date-filter");
  dateFilter.dataset.action = "finder-date-filter";
  dateFilter.setAttribute("aria-label", "Период среди загруженных объектов");
  dateFilter.title = "Фильтр применяется к загруженным объектам";
  [["all", "Все даты"], ["today", "Сегодня"], ["7d", "7 дней"], ["30d", "30 дней"]].forEach(([value, label]) => {
    const option = create("option", "", label);
    option.value = value;
    dateFilter.append(option);
  });
  dateFilter.value = normalizedDateFilter(runtime.state.dateFilter);
  const grid = create("button", "ce-v4-finder-view");
  grid.type = "button";
  grid.dataset.action = "finder-view";
  grid.dataset.ceV4FinderView = "grid";
  grid.textContent = "Сетка";
  const list = create("button", "ce-v4-finder-view");
  list.type = "button";
  list.dataset.action = "finder-view";
  list.dataset.ceV4FinderView = "list";
  list.textContent = "Список";
  const columns = create("button", "ce-v4-finder-view");
  columns.type = "button";
  columns.dataset.action = "finder-view";
  columns.dataset.ceV4FinderView = "columns";
  columns.textContent = "Колонки";
  const quickLook = create("button", "ce-v4-finder-quicklook", "Быстрый просмотр");
  quickLook.type = "button";
  quickLook.dataset.action = "finder-quicklook";
  quickLook.dataset.ceV4FinderQuicklook = "true";
  quickLook.disabled = true;
  quickLook.setAttribute("aria-disabled", "true");
  const upload = create("button", "ce-v4-finder-upload", "Добавить материал");
  upload.type = "button";
  upload.dataset.action = "finder-upload";
  upload.dataset.ceV4FinderUpload = "true";
  controls.append(browse, organize, sort, dateFilter, grid, list, columns, quickLook, upload);
  toolbar.append(title, controls);
  content.prepend(toolbar);
  ensureMobileSidebar();
}

function buildFolderSearch() {
  const input = q('#workspace-board-filter-form input[name="query"]', runtime.board);
  if (!input || input.dataset.ceV4FolderSearchBound === "true") return;
  input.dataset.ceV4FolderSearchBound = "true";
  input.placeholder = "Найти проект, папку, SKU или файл";
  input.setAttribute("aria-label", "Найти проект, папку, SKU или файл");
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

function routeFinderQuery() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return new URLSearchParams(raw.split("?")[1] || "");
}

function rememberProjectRow(row) {
  if (!(row instanceof HTMLElement) || row.dataset.systemFolder === "true") return;
  const depth = Number(row.style.getPropertyValue("--workspace-folder-depth") || 0);
  if (depth !== 0) return;
  const id = String(row.dataset.folderId || "");
  const name = compact(q(".workspace-board__folder-button > span:nth-child(2)", row)?.textContent || "Проект", 80);
  if (!id) return;
  try { window.sessionStorage.setItem(PROJECT_CONTEXT_KEY, JSON.stringify({ id, name })); }
  catch { /* project context is a navigation convenience */ }
}

function applyRouteFolder() {
  const query = routeFinderQuery();
  const folderId = String(query.get("folder") || "").trim();
  if (folderId) {
    const row = q(`.workspace-board__folder-row[data-folder-id="${CSS.escape(folderId)}"]`, runtime.board);
    if (row) {
      revealFolderAncestors(row);
      rememberProjectRow(row);
      if (!row.classList.contains("is-selected")) {
        q(".workspace-board__folder-button", row)?.click();
        return;
      }
    }
  }
  if (query.get("create") === "project") {
    const input = q("#workspace-folder-create-form input[name='folder_name']", runtime.board);
    if (input instanceof HTMLElement) {
      q("#workspace-folder-create-form", runtime.board)?.scrollIntoView({ block: "nearest", behavior: "auto" });
      input.focus({ preventScroll: true });
    }
  }
}

function ensureSelectedDrawer(card) {
  if (!card) return Promise.resolve(q("[data-workspace-item-drawer]", runtime.board));
  const button = q('[data-action="open-workspace-item"]', card);
  if (button && !card.classList.contains("is-selected")) requestApplicationOpen(card);
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

function normalizedFinderView(value) {
  const view = String(value || "").trim().toLowerCase();
  return FINDER_VIEWS.has(view) ? view : "grid";
}

function finderFolderId() {
  const queryId = String(routeFinderQuery().get(FOLDER_QUERY_KEY) || "").trim();
  if (queryId) return queryId;
  return String(
    q(".workspace-board__folder-row.is-selected[data-folder-id]", runtime.board)?.dataset.folderId
      || "all",
  ).trim() || "all";
}

function finderViewPreferenceKey() {
  // Only route/loaded-DOM project identity is suitable for persistence. The
  // sessionStorage project convenience can be stale after a user/project switch.
  const queryProjectId = String(routeFinderQuery().get(PROJECT_QUERY_KEY) || "").trim();
  const loadedProjectId = String(q("[data-project-flow-root]")?.dataset.projectId || "").trim();
  const projectId = queryProjectId || loadedProjectId;
  if (!projectId) return "";
  return `${VIEW_STATE_PREFIX}.${encodeURIComponent(projectId)}.${encodeURIComponent(finderFolderId())}`;
}

function currentFinderView() {
  const preferenceKey = finderViewPreferenceKey();
  if (!preferenceKey) return normalizedFinderView(runtime.ephemeralView);
  if (runtime.scopedViews.has(preferenceKey)) {
    return normalizedFinderView(runtime.scopedViews.get(preferenceKey));
  }
  let view = "grid";
  try { view = normalizedFinderView(window.localStorage.getItem(preferenceKey)); }
  catch { /* scoped preference is optional */ }
  runtime.scopedViews.set(preferenceKey, view);
  return view;
}

function rememberFinderView(value) {
  const view = normalizedFinderView(value);
  const preferenceKey = finderViewPreferenceKey();
  if (!preferenceKey) {
    runtime.ephemeralView = view;
    return view;
  }
  runtime.scopedViews.set(preferenceKey, view);
  try { window.localStorage.setItem(preferenceKey, view); }
  catch { /* scoped preference is optional */ }
  return view;
}

function requestApplicationOpen(card) {
  const trigger = q('[data-action="open-workspace-item"]', card);
  const key = finderCardKey(card);
  if (!trigger || !key) return false;
  runtime.allowApplicationOpenKey = key;
  trigger.click();
  runtime.allowApplicationOpenKey = "";
  return true;
}

function openCanonicalCard(card = selectedCard()) {
  if (!card) return false;
  selectCard(card);
  setSidebarOpen(false);
  return requestApplicationOpen(card);
}

async function openQuickLook(card = selectedCard() || cards().find(visible)) {
  if (!card) return;
  if (runtime.quickLook) closeQuickLook({ restoreFocus: false, closeDetail: false });
  // Quick Look follows the canonical Finder selection. This updates classes
  // only; the business-owned collection and object remain untouched.
  selectCard(card);
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
  const previous = create("button", "ce-v4-quicklook-inline__previous", "← Предыдущий");
  previous.type = "button";
  const next = create("button", "ce-v4-quicklook-inline__next", "Следующий →");
  next.type = "button";
  const pin = create("button", "ce-v4-quicklook-inline__pin", "Закрепить в Dock");
  pin.type = "button";
  pin.dataset.ceV4QuicklookPinDock = "true";
  pin.hidden = !dockFileDescriptor(card);
  const close = create("button", "ce-v4-quicklook-inline__close", "Назад к файлам");
  close.type = "button";
  controls.append(previous, next, pin, close);
  bar.append(copy, controls);
  drawer.prepend(bar);
  drawer.classList.add("ce-v4-quicklook-inline");
  board.classList.remove("is-detail-inline");
  board.classList.add("is-quicklook-inline");
  runtime.quickLook = { board, drawer, bar, cardKey };
  previous.addEventListener("click", () => navigateQuickLook(-1));
  next.addEventListener("click", () => navigateQuickLook(1));
  pin.addEventListener("click", () => {
    const descriptor = dockFileDescriptor(card);
    if (descriptor) window.ContentEngineDesktopV4?.pinDockFileShortcut?.(descriptor);
  });
  close.addEventListener("click", () => closeQuickLook());
  close.focus({ preventScroll: true });
  if (!REDUCED_MOTION.matches && typeof drawer.animate === "function") {
    drawer.animate(
      [{ opacity: 0, transform: "translate3d(0, 8px, 0)" }, { opacity: 1, transform: "translate3d(0, 0, 0)" }],
      { duration: 190, easing: "cubic-bezier(0.16,1,0.3,1)" },
    );
  }
}

function closeQuickLook({ restoreFocus = true, closeDetail = true } = {}) {
  const current = runtime.quickLook;
  if (!current) return;
  q("video", current.drawer)?.pause?.();
  current.bar?.remove();
  current.drawer?.classList.remove("ce-v4-quicklook-inline");
  current.board?.classList.remove("is-quicklook-inline");
  runtime.quickLook = null;
  if (closeDetail) q('[data-action="close-workspace-item"]', current.drawer)?.click();
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
  closeQuickLook({ restoreFocus: false, closeDetail: false });
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
  event.stopImmediatePropagation();
  openCanonicalCard(card);
}

function handleBoardSelectionClick(event) {
  if (!(event.target instanceof Element)) return;
  const action = event.target.closest(
    "[data-ce-v4-batch-move], [data-ce-v4-batch-trash], [data-ce-v4-batch-clear]",
  );
  if (action) {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (action.matches("[data-ce-v4-batch-move]")) void moveSelectedItems();
    if (action.matches("[data-ce-v4-batch-trash]")) void trashSelectedItems();
    if (action.matches("[data-ce-v4-batch-clear]")) clearSelection({ restoreFocus: true });
    return;
  }

  const selectionControl = event.target.closest("[data-ce-v4-select-item]");
  const card = event.target.closest(".workspace-board__item");
  const modifierSelection = Boolean(card && (event.ctrlKey || event.metaKey || event.shiftKey));
  if (card && (selectionControl || modifierSelection)) {
    event.preventDefault();
    event.stopImmediatePropagation();
    selectCard(card, {
      ctrlKey: event.ctrlKey,
      metaKey: event.metaKey,
      shiftKey: event.shiftKey,
      fromSelectionControl: Boolean(selectionControl),
    });
    return;
  }

  if (
    runtime.selectedKeys.size
    && event.target.closest(".workspace-board__grid")
    && !card
  ) clearSelection();
}

function handleBoardSelectionKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "a") {
    if (!(event.target instanceof Element) || !event.target.closest(".workspace-board__grid")) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    selectionCards().forEach((card) => runtime.selectedKeys.add(finderCardKey(card)));
    runtime.selectionAnchorKey = finderCardKey(selectionCards()[0]);
    syncSelectionDom();
  }
}

function handleBoardFolderSelection(event) {
  if (!(event.target instanceof Element)) return;
  const provenance = event.target.closest('[data-action="select-workspace-provenance"]');
  if (provenance) {
    setFolderUrl("all");
    if (finderUsesOverlaySidebar()) window.requestAnimationFrame(() => setSidebarOpen(false));
    return;
  }
  const toggle = event.target.closest("[data-folder-toggle]");
  if (toggle) {
    event.preventDefault();
    event.stopImmediatePropagation();
    toggleFolderBranch(toggle.dataset.folderToggle);
    return;
  }
  const button = event.target.closest('[data-action="select-workspace-folder"]');
  if (!button) return;
  const folderId = String(button.dataset.folderId || "all");
  const row = q(`.workspace-board__folder-row[data-folder-id="${CSS.escape(folderId)}"]`, runtime.board);
  revealFolderAncestors(row);
  rememberProjectRow(row);
  const projectId = String(button.dataset.projectId || row?.dataset.projectId || "").trim();
  setFolderUrl(folderId, { projectId });
  if (finderUsesOverlaySidebar()) window.requestAnimationFrame(() => setSidebarOpen(false));
}

function handleBoardItemSelection(event) {
  if (!(event.target instanceof Element)) return;
  const trigger = event.target.closest('[data-action="open-workspace-item"]');
  const card = trigger?.closest(".workspace-board__item");
  if (!card) return;
  const cardKey = finderCardKey(card);
  if (runtime.allowApplicationOpenKey && runtime.allowApplicationOpenKey === cardKey) return;
  // Finder owns selection. The application's document handler only receives a
  // synthetic, explicitly allowed open command from Enter/double-click/QL.
  event.preventDefault();
  event.stopImmediatePropagation();
  selectCard(card, {
    ctrlKey: event.ctrlKey,
    metaKey: event.metaKey,
    shiftKey: event.shiftKey,
  });
}

function handleFinderViewControl(event) {
  if (!(event.target instanceof Element)) return;
  const control = event.target.closest(
    ".ce-v4-finder-view[data-ce-v4-finder-view]",
  );
  if (!(control instanceof HTMLButtonElement) || !runtime.board?.contains(control)) return;
  event.preventDefault();
  // Finder owns this state transition. Do not let the application-level
  // action bridge apply the same view a second time.
  event.stopPropagation();
  rememberFinderView(control.dataset.ceV4FinderView);
  applyView();
}

function handleFinderSortControl(event) {
  const control = event.target;
  if (!(control instanceof HTMLSelectElement)) return;
  if (control.matches(".ce-v4-finder-date-filter")) {
    event.stopPropagation();
    applyDateFilter(control.value);
    return;
  }
  if (!control.matches(".ce-v4-finder-sort")) return;
  event.stopPropagation();
  sortCards(control.value);
}

function bindBoard() {
  if (runtime.board.dataset.ceV4FinderBound === "true") return;
  runtime.board.dataset.ceV4FinderBound = "true";
  runtime.board.addEventListener("click", handleFinderViewControl);
  runtime.board.addEventListener("change", handleFinderSortControl);
  runtime.board.addEventListener("dblclick", handleBoardDoubleClick);
  runtime.board.addEventListener("click", handleBoardSelectionClick);
  runtime.board.addEventListener("keydown", handleBoardSelectionKeydown, true);
  runtime.board.addEventListener("click", handleBoardItemSelection);
  runtime.board.addEventListener("click", handleBoardFolderSelection);
}

function mount() {
  if (routePath() !== ROUTE) {
    setSidebarOpen(false);
    closeQuickLook({ restoreFocus: false, closeDetail: false });
    runtime.page = null;
    runtime.board = null;
    document.body.classList.remove("ce-v4-finder-route");
    delete document.body.dataset.ceV4FinderMode;
    return;
  }
  const board = q(".workspace-board");
  if (!board) return;
  if (routeView() === "trash") closeQuickLook({ restoreFocus: false, closeDetail: false });
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
  const sortValue = q(".ce-v4-finder-sort", board)?.value || runtime.state.sort || "created_desc";
  sortCards(sortValue);
  const dateFilterValue = q(".ce-v4-finder-date-filter", board)?.value || runtime.state.dateFilter || "all";
  applyDateFilter(dateFilterValue);
  filterFolders(q('#workspace-board-filter-form input[name="query"]', board)?.value || "");
  bindBoard();
  applyFolderTreeState();
  syncSelectionDom();
  finderQueryHandoff();
  applyRouteFolder();
}

document.addEventListener("keydown", (event) => {
  if (routePath() !== ROUTE) return;
  if (runtime.quickLook) {
    if (event.key === "Escape") { event.preventDefault(); event.stopImmediatePropagation(); closeQuickLook(); }
    if (event.key === "ArrowLeft") { event.preventDefault(); event.stopImmediatePropagation(); navigateQuickLook(-1); }
    if (event.key === "ArrowRight") { event.preventDefault(); event.stopImmediatePropagation(); navigateQuickLook(1); }
    return;
  }
  if (event.key === "Escape" && runtime.sidebarOpen) {
    event.preventDefault();
    event.stopImmediatePropagation();
    setSidebarOpen(false, { restoreFocus: true });
    return;
  }
  if (event.key === "Escape" && runtime.selectedKeys.size) {
    event.preventDefault();
    event.stopImmediatePropagation();
    clearSelection({ restoreFocus: true });
    return;
  }
  const target = event.target instanceof Element ? event.target : null;
  if (!target || !runtime.board?.contains(target)) return;
  if (target.closest("input, textarea, select, [contenteditable='true']")) return;
  const focusedControl = target.closest("button, a[href]");
  if (focusedControl && !focusedControl.matches('[data-action="open-workspace-item"]')) return;
  const current = selectedCard();
  if ((event.key === " " || event.key === "Enter") && current) {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.key === " ") void openQuickLook(current);
    else openCanonicalCard(current);
    return;
  }
  if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
  const available = selectionCards();
  if (!available.length) return;
  const currentIndex = Math.max(0, available.indexOf(current));
  // Columns keeps its two projected panes read-only: all arrows therefore move
  // the canonical selection in the first pane, never dispatch an implicit open.
  const movesBackward = ["ArrowLeft", "ArrowUp"];
  const nextIndex = event.key === "Home"
    ? 0
    : event.key === "End"
      ? available.length - 1
      : Math.max(0, Math.min(
        available.length - 1,
        currentIndex + (movesBackward.includes(event.key) ? -1 : 1),
      ));
  const next = available[nextIndex];
  event.preventDefault();
  event.stopImmediatePropagation();
  selectCard(next);
  q('[data-action="open-workspace-item"]', next)?.focus({ preventScroll: true });
  next.scrollIntoView?.({ block: "nearest", inline: "nearest", behavior: "auto" });
}, true);

window.addEventListener("popstate", () => {
  if (routePath() !== ROUTE) return;
  window.ContentEngineDesktopV4.requestMount();
});

const handleSidebarViewport = () => setSidebarOpen(false);
if (typeof MOBILE_SIDEBAR.addEventListener === "function") {
  MOBILE_SIDEBAR.addEventListener("change", handleSidebarViewport);
} else {
  MOBILE_SIDEBAR.addListener?.(handleSidebarViewport);
}

document.addEventListener("contentengine:workspace-window-geometry", handleSidebarViewport);

window.ContentEngineDesktopV4.registerAdapter("finder-board", mount, { priority: 100 });

window.ContentEngineFinderV4 = Object.freeze({
  openQuickLook,
  closeQuickLook,
  openSelected: (control = null) => {
    const board = control instanceof Element ? control.closest(".workspace-board") : null;
    if (board) runtime.board = board;
    return openQuickLook(selectedCard());
  },
  setView: (value, control = null) => {
    rememberFinderView(value);
    const settle = () => {
      const board = control instanceof Element && control.isConnected
        ? control.closest(".workspace-board")
        : q(".workspace-board");
      if (!board || routePath() !== ROUTE) return;
      runtime.board = board;
      applyView();
    };
    settle();
    window.requestAnimationFrame(settle);
  },
  setSort: (value, control = null) => {
    const board = control instanceof Element ? control.closest(".workspace-board") : null;
    if (board) runtime.board = board;
    sortCards(value);
  },
  selectedItems,
  clearSelection,
  moveSelection: (folderId) => moveSelectedItems(folderId),
  trashSelection: trashSelectedItems,
  focusBatchMove: () => q("[data-ce-v4-batch-destination]", runtime.board)?.focus({ preventScroll: true }),
  schedule: () => window.ContentEngineDesktopV4.requestMount(),
  selectedObjectId: () => dockFileDescriptor(selectedCard())?.objectId || "",
  quickLookObjectId: () => {
    const card = runtime.quickLook?.cardKey
      ? cards().find((item) => finderCardKey(item) === runtime.quickLook.cardKey)
      : null;
    return dockFileDescriptor(card)?.objectId || "";
  },
});
