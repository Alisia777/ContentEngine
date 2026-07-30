/*
 * ContentEngine Media Finder.
 * Re-composes the existing materials page into a Finder-like library and uses
 * only URLs already rendered by the trusted application.
 */

const MEDIA_ROUTE = "/workspace/media";
const STATE_KEY = "contentengine.media-finder.v2";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const QUICK_CLOSE_MS = 220;

const ICONS = Object.freeze({
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  list: '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 14v5h14v-5"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 16 3.5-4 3 3 2-2 2.5 3"/><circle cx="8" cy="8.5" r="1.3"/>',
  video: '<rect x="3" y="5" width="14" height="14" rx="3"/><path d="m17 10 4-2v8l-4-2"/>',
  folder: '<path d="M3 6h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z"/>',
  product: '<path d="m4 7 8-4 8 4-8 4-8-4Z"/><path d="M4 7v10l8 4 8-4V7M12 11v10"/>',
  reference: '<path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="6"/>',
  eye: '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 13v6H5V6h6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
});

const runtime = {
  queued: false,
  page: null,
  grid: null,
  cards: [],
  selected: null,
  quickLook: null,
  upload: null,
  transitionTimer: 0,
  memory: readMemory(),
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function routePath() {
  const raw = String(window.location.hash || "#/workspace/home").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function icon(name, size = 20) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.folder}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function compact(value, limit = 90) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
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

function mediaFacts(card) {
  const name = compact(q(".media-info > strong", card)?.textContent || "Файл", 180);
  const meta = compact(q(".media-info > small", card)?.textContent || "Материал", 220);
  const isVideo = Boolean(q(".media-preview video", card));
  const kindText = meta.toLocaleLowerCase("ru-RU");
  const kind = /упаковк|товар/u.test(kindText)
    ? "product"
    : /пример|референс|желаем/u.test(kindText)
      ? "reference"
      : isVideo ? "video" : "image";
  return {
    name,
    meta,
    isVideo,
    kind,
    searchable: `${name} ${meta}`.toLocaleLowerCase("ru-RU"),
  };
}

function annotateCards() {
  if (!runtime.grid) return;
  runtime.cards = qa(":scope > .media-card", runtime.grid);
  runtime.cards.forEach((card, index) => {
    const facts = mediaFacts(card);
    card.dataset.mediaFinderIndex = String(index);
    card.dataset.mediaFinderName = facts.name;
    card.dataset.mediaFinderMeta = facts.meta;
    card.dataset.mediaFinderType = facts.isVideo ? "video" : "image";
    card.dataset.mediaFinderKind = facts.kind;
    card.dataset.mediaFinderSearch = facts.searchable;
    card.tabIndex = 0;
    card.setAttribute("role", "option");
    card.setAttribute("aria-selected", "false");
    if (!q(".media-finder-quick-button", card)) {
      const button = elementFrom(`<button class="media-finder-quick-button" type="button" aria-label="Быстрый просмотр">${icon("eye", 17)}</button>`);
      q(".media-preview", card)?.append(button);
    }
  });
}

function visibleCards() {
  return runtime.cards.filter((card) => !card.hidden);
}

function selectCard(card, { focus = false } = {}) {
  if (!card || card.hidden) return;
  runtime.cards.forEach((item) => {
    const active = item === card;
    item.classList.toggle("is-selected", active);
    item.setAttribute("aria-selected", String(active));
  });
  runtime.selected = card;
  if (focus) card.focus({ preventScroll: true });
}

function folderMatches(card, folder) {
  if (folder === "all") return true;
  if (folder === "photos") return card.dataset.mediaFinderType === "image";
  if (folder === "videos") return card.dataset.mediaFinderType === "video";
  if (folder === "product") return card.dataset.mediaFinderKind === "product";
  if (folder === "reference") return card.dataset.mediaFinderKind === "reference";
  return true;
}

function sortCards(sort) {
  if (!runtime.grid) return;
  const ordered = [...runtime.cards].sort((left, right) => {
    if (sort === "type") {
      const byType = String(left.dataset.mediaFinderMeta || "").localeCompare(
        String(right.dataset.mediaFinderMeta || ""),
        "ru",
      );
      if (byType) return byType;
    }
    return String(left.dataset.mediaFinderName || "").localeCompare(
      String(right.dataset.mediaFinderName || ""),
      "ru",
      { sensitivity: "base" },
    );
  });
  ordered.forEach((card) => runtime.grid.append(card));
  runtime.cards = ordered;
}

function refreshFolderCounts() {
  qa("[data-media-folder]", runtime.page).forEach((button) => {
    const count = runtime.cards.filter((card) => folderMatches(card, button.dataset.mediaFolder)).length;
    const target = q("b", button);
    if (target) target.textContent = String(count);
  });
}

function applyFilters() {
  if (!runtime.page) return;
  const folder = String(runtime.memory.folder || "all");
  const queryText = String(q("[data-media-search]", runtime.page)?.value || "")
    .trim()
    .toLocaleLowerCase("ru-RU");
  const sort = String(q("[data-media-sort]", runtime.page)?.value || runtime.memory.sort || "name");
  sortCards(sort);
  let shown = 0;
  runtime.cards.forEach((card) => {
    const matches = folderMatches(card, folder)
      && (!queryText || String(card.dataset.mediaFinderSearch || "").includes(queryText));
    card.hidden = !matches;
    if (matches) shown += 1;
  });
  qa("[data-media-folder]", runtime.page).forEach((button) => {
    const active = button.dataset.mediaFolder === folder;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "true" : "false");
  });
  const count = q("[data-media-visible-count]", runtime.page);
  if (count) count.textContent = `${shown} из ${runtime.cards.length}`;
  const empty = q(".media-finder-filter-empty", runtime.page);
  if (empty) empty.hidden = shown > 0;
  if (runtime.selected?.hidden) selectCard(visibleCards()[0]);
  remember({ folder, sort });
}

function setView(view) {
  const resolved = view === "list" ? "list" : "grid";
  runtime.page?.setAttribute("data-media-view", resolved);
  qa("[data-media-view]", runtime.page).forEach((button) => {
    if (!button.matches("button")) return;
    const active = button.dataset.mediaView === resolved;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  remember({ view: resolved });
}

function quickLookSource(card) {
  const image = q(".media-preview img", card);
  if (image?.src) return { kind: "image", src: image.src };
  const video = q(".media-preview video", card);
  if (video?.src) return { kind: "video", src: video.src };
  const open = q('.media-info a[target="_blank"]', card);
  return open?.href
    ? { kind: card.dataset.mediaFinderType || "image", src: open.href }
    : null;
}

function closeQuickLook({ restoreFocus = true, immediate = false } = {}) {
  const overlay = runtime.quickLook;
  if (!overlay) return Promise.resolve();
  window.clearTimeout(runtime.transitionTimer);
  q("video", overlay)?.pause?.();
  overlay.classList.add("is-closing");
  return new Promise((resolve) => {
    const finish = () => {
      overlay.remove();
      if (runtime.quickLook === overlay) {
        runtime.quickLook = null;
        document.body.classList.remove("media-quicklook-open");
      }
      if (restoreFocus) runtime.selected?.focus?.({ preventScroll: true });
      resolve();
    };
    if (immediate || REDUCED_MOTION.matches) finish();
    else runtime.transitionTimer = window.setTimeout(finish, QUICK_CLOSE_MS);
  });
}

async function quickLookNavigate(direction) {
  const cards = visibleCards();
  if (!cards.length) return;
  const current = Math.max(0, cards.indexOf(runtime.selected));
  const next = cards[(current + direction + cards.length) % cards.length];
  await closeQuickLook({ restoreFocus: false });
  selectCard(next);
  openQuickLook(next);
}

function quickLookAction(source, label, href, { external = false } = {}) {
  if (!href) return null;
  const anchor = elementFrom(`<a>${source || ""}<span>${label}</span></a>`);
  anchor.href = href;
  if (external) {
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
  }
  return anchor;
}

function openQuickLook(card) {
  if (!card || card.hidden || runtime.quickLook) return;
  selectCard(card);
  const source = quickLookSource(card);
  const overlay = elementFrom(`
    <div class="media-quicklook-backdrop">
      <section class="media-quicklook" role="dialog" aria-modal="true" aria-labelledby="media-quicklook-title">
        <header>
          <div><small>QUICK LOOK</small><strong id="media-quicklook-title"></strong></div>
          <button type="button" data-media-quick-close aria-label="Закрыть">${icon("close", 19)}</button>
        </header>
        <div class="media-quicklook__stage"><div class="media-quicklook__empty">Предпросмотр недоступен</div></div>
        <footer>
          <button type="button" data-media-quick-prev aria-label="Предыдущий файл">${icon("left", 18)}</button>
          <div class="media-quicklook__meta"><strong></strong><small></small></div>
          <div class="media-quicklook__actions"></div>
          <button type="button" data-media-quick-next aria-label="Следующий файл">${icon("right", 18)}</button>
        </footer>
      </section>
    </div>`);
  q("#media-quicklook-title", overlay).textContent = card.dataset.mediaFinderName || "Материал";
  q(".media-quicklook__meta strong", overlay).textContent = card.dataset.mediaFinderName || "Материал";
  q(".media-quicklook__meta small", overlay).textContent = card.dataset.mediaFinderMeta || "";

  const stage = q(".media-quicklook__stage", overlay);
  if (source?.src) {
    stage.textContent = "";
    if (source.kind === "video") {
      const video = document.createElement("video");
      video.src = source.src;
      video.controls = true;
      video.playsInline = true;
      video.preload = "metadata";
      stage.append(video);
    } else {
      const image = document.createElement("img");
      image.src = source.src;
      image.alt = card.dataset.mediaFinderName || "Материал";
      stage.append(image);
    }
  }

  const actions = q(".media-quicklook__actions", overlay);
  const open = q('.media-info a[target="_blank"]', card);
  const review = qa(".media-info a", card).find((link) =>
    String(link.getAttribute("href") || "").includes("/workspace/review")
  );
  const openAction = quickLookAction(icon("external", 16), "Открыть отдельно", open?.href, { external: true });
  const reviewAction = quickLookAction("", "Проверить", review?.getAttribute("href"));
  const generateAction = quickLookAction("", "В генерацию", "#/workspace/generation");
  [openAction, reviewAction, generateAction].filter(Boolean).forEach((action) => actions.append(action));

  overlay.addEventListener("click", (event) => {
    if (event.target === overlay || (event.target instanceof Element && event.target.closest("[data-media-quick-close]"))) {
      void closeQuickLook();
      return;
    }
    if (event.target instanceof Element && event.target.closest("[data-media-quick-prev]")) void quickLookNavigate(-1);
    if (event.target instanceof Element && event.target.closest("[data-media-quick-next]")) void quickLookNavigate(1);
  });
  document.body.append(overlay);
  runtime.quickLook = overlay;
  document.body.classList.add("media-quicklook-open");
  q("[data-media-quick-close]", overlay)?.focus({ preventScroll: true });
}

function closeUpload({ restoreFocus = true, immediate = false } = {}) {
  const overlay = runtime.upload;
  if (!overlay) return;
  overlay.classList.add("is-closing");
  const finish = () => {
    const card = q(".media-finder-upload-card", overlay);
    const parking = q("[data-media-upload-parking]", runtime.page);
    if (card && parking) parking.append(card);
    overlay.remove();
    if (runtime.upload === overlay) {
      runtime.upload = null;
      document.body.classList.remove("media-upload-sheet-open");
    }
    if (restoreFocus) q("[data-media-open-upload]", runtime.page)?.focus({ preventScroll: true });
  };
  if (immediate || REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, QUICK_CLOSE_MS);
}

function openUpload() {
  if (runtime.upload || !runtime.page) return;
  const card = q(".media-finder-upload-card", runtime.page);
  if (!card) return;
  const overlay = elementFrom(`
    <div class="media-finder-upload-backdrop">
      <section class="media-finder-upload-sheet" role="dialog" aria-modal="true" aria-labelledby="media-upload-sheet-title">
        <header><div><small>МАТЕРИАЛЫ</small><strong id="media-upload-sheet-title">Добавить исходники</strong></div><button type="button" data-media-upload-close aria-label="Закрыть">${icon("close", 19)}</button></header>
        <div class="media-finder-upload-sheet__body"></div>
      </section>
    </div>`);
  q(".media-finder-upload-sheet__body", overlay).append(card);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay || (event.target instanceof Element && event.target.closest("[data-media-upload-close]"))) {
      closeUpload();
    }
  });
  document.body.append(overlay);
  runtime.upload = overlay;
  document.body.classList.add("media-upload-sheet-open");
  q("[data-media-upload-close]", overlay)?.focus({ preventScroll: true });
}

function createTopbar() {
  return elementFrom(`
    <header class="media-finder-topbar">
      <div class="media-finder-window-controls" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="media-finder-title"><small>ContentEngine Finder</small><strong>Материалы</strong></div>
      <label class="media-finder-search">${icon("search", 17)}<input type="search" data-media-search autocomplete="off" placeholder="Поиск по файлам" aria-label="Поиск по материалам" /></label>
      <select class="media-finder-sort" data-media-sort aria-label="Сортировка материалов"><option value="name">По имени</option><option value="type">По типу</option></select>
      <div class="media-finder-view" role="group" aria-label="Вид материалов">
        <button type="button" data-media-view="grid" aria-label="Сетка">${icon("grid", 18)}</button>
        <button type="button" data-media-view="list" aria-label="Список">${icon("list", 18)}</button>
      </div>
      <button class="media-finder-upload" type="button" data-media-open-upload>${icon("upload", 17)}<span>Загрузить</span></button>
      <button class="media-finder-mission" type="button" data-ce-open-mission aria-label="Все рабочие столы">${icon("grid", 18)}</button>
    </header>`);
}

function createFinder() {
  return elementFrom(`
    <section class="media-finder-shell" aria-label="Библиотека материалов">
      <aside class="media-finder-sidebar">
        <div><small>ИЗБРАННОЕ</small><strong>Умные папки</strong></div>
        <nav aria-label="Фильтры материалов">
          <button type="button" data-media-folder="all">${icon("folder", 17)}<span>Все материалы</span><b>0</b></button>
          <button type="button" data-media-folder="photos">${icon("image", 17)}<span>Фото</span><b>0</b></button>
          <button type="button" data-media-folder="videos">${icon("video", 17)}<span>Видео</span><b>0</b></button>
          <button type="button" data-media-folder="product">${icon("product", 17)}<span>Точный товар</span><b>0</b></button>
          <button type="button" data-media-folder="reference">${icon("reference", 17)}<span>Референсы</span><b>0</b></button>
        </nav>
        <div class="media-finder-help"><kbd>Space</kbd><span>быстрый просмотр</span><kbd>Esc</kbd><span>закрыть</span></div>
      </aside>
      <main class="media-finder-library">
        <header><div><small>БИБЛИОТЕКА</small><strong>Файлы команды</strong></div><span data-media-visible-count>0</span></header>
        <div class="media-finder-library__content"></div>
        <div class="media-finder-filter-empty" hidden><strong>Ничего не найдено</strong><p>Очистите поиск или откройте другую умную папку.</p></div>
      </main>
      <div data-media-upload-parking hidden></div>
    </section>`);
}

function clearRouteState() {
  window.clearTimeout(runtime.transitionTimer);
  runtime.quickLook?.remove();
  runtime.upload?.remove();
  runtime.quickLook = null;
  runtime.upload = null;
  runtime.page = null;
  runtime.grid = null;
  runtime.cards = [];
  runtime.selected = null;
  document.body.classList.remove(
    "contentengine-media-finder-open",
    "media-quicklook-open",
    "media-upload-sheet-open",
  );
}

function mountFinder() {
  if (routePath() !== MEDIA_ROUTE) {
    clearRouteState();
    return;
  }
  const form = q("#media-upload-form");
  const page = form?.closest?.(".page-wrap");
  if (!page) return;
  if (page.dataset.mediaFinderReady === "true") {
    runtime.page = page;
    document.body.classList.add("contentengine-media-finder-open");
    return;
  }

  page.dataset.mediaFinderReady = "true";
  page.classList.add("media-finder-page");
  document.body.classList.add("contentengine-media-finder-open");
  runtime.page = page;

  const layout = q(":scope > .split-grid-media", page);
  const uploadCard = form.closest("section.card");
  const library = qa(":scope > section", layout)
    .find((section) => section !== uploadCard)
    || q(".media-grid", page)?.parentElement;
  const topbar = createTopbar();
  const finder = createFinder();
  const anchor = q(":scope > .page-header", page) || layout || page.firstElementChild;
  anchor?.after?.(topbar, finder);

  if (uploadCard) {
    uploadCard.classList.add("media-finder-upload-card");
    q("[data-media-upload-parking]", finder).append(uploadCard);
  }
  if (library) {
    library.classList.add("media-finder-native-library");
    q(".media-finder-library__content", finder).append(library);
  }
  layout?.remove();

  runtime.grid = q(".media-grid", finder);
  if (!runtime.grid) return;
  annotateCards();
  refreshFolderCounts();

  const search = q("[data-media-search]", topbar);
  const sort = q("[data-media-sort]", topbar);
  search.value = String(runtime.memory.query || "");
  sort.value = String(runtime.memory.sort || "name");
  search.addEventListener("input", () => {
    remember({ query: search.value });
    applyFilters();
  });
  sort.addEventListener("change", applyFilters);

  topbar.addEventListener("click", (event) => {
    if (!(event.target instanceof Element)) return;
    const view = event.target.closest("[data-media-view]");
    if (view) setView(view.dataset.mediaView);
    if (event.target.closest("[data-media-open-upload]")) openUpload();
  });

  q(".media-finder-sidebar", finder)?.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-media-folder]") : null;
    if (!button) return;
    remember({ folder: button.dataset.mediaFolder });
    applyFilters();
  });

  runtime.grid.addEventListener("click", (event) => {
    const card = event.target instanceof Element ? event.target.closest(".media-card") : null;
    if (!card || card.hidden) return;
    if (event.target instanceof Element && event.target.closest("a, video, .btn")) return;
    selectCard(card);
    if (event.target instanceof Element && event.target.closest(".media-finder-quick-button")) openQuickLook(card);
  });
  runtime.grid.addEventListener("dblclick", (event) => {
    const card = event.target instanceof Element ? event.target.closest(".media-card") : null;
    if (card && !(event.target instanceof Element && event.target.closest("a, video, .btn"))) {
      openQuickLook(card);
    }
  });

  setView(String(runtime.memory.view || "grid"));
  applyFilters();
  selectCard(visibleCards()[0]);
}

function handleKeydown(event) {
  if (runtime.quickLook) {
    if (event.key === "Escape") {
      event.preventDefault();
      void closeQuickLook();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      void quickLookNavigate(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      void quickLookNavigate(1);
    }
    return;
  }
  if (runtime.upload) {
    if (event.key === "Escape") {
      event.preventDefault();
      closeUpload();
    }
    return;
  }
  if (!runtime.page || routePath() !== MEDIA_ROUTE) return;
  const target = event.target instanceof Element ? event.target : null;
  if (event.key === " " && target?.closest?.(".media-card")) {
    event.preventDefault();
    openQuickLook(target.closest(".media-card"));
  }
  if (event.key === "Escape" && q("[data-media-search]", runtime.page)?.value) {
    const search = q("[data-media-search]", runtime.page);
    search.value = "";
    remember({ query: "" });
    applyFilters();
    search.focus();
  }
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mountFinder();
  });
}

new MutationObserver(scheduleMount).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("keydown", handleKeydown);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
