/*
 * ContentEngine OS v3.2 visual QA hotfix.
 *
 * Goals: one screen / one action, one global Dock, no legacy full-screen focus,
 * clean route isolation, practical search/filtering, honest empty states and a
 * lightweight home command surface. Presentation-only: no business API calls,
 * no form submission and no cloning of native controls.
 */

const CLEAN_BUILD = "20260731.os3.2";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const TYPING = "input, textarea, select, [contenteditable='true']";

const ROUTES = Object.freeze([
  { route: "/workspace/home", label: "Сегодня", hint: "Один следующий шаг", icon: "home" },
  { route: "/workspace/work", label: "Моя работа", hint: "Сейчас, жду, дальше", icon: "work" },
  { route: "/workspace/media", label: "Материалы", hint: "Папки, поиск и Quick Look", icon: "media" },
  { route: "/workspace/generation", label: "Создание", hint: "Один запуск по шагам", icon: "generate" },
  { route: "/workspace/review", label: "Проверка", hint: "Один риск и одно решение", icon: "review" },
  { route: "/workspace/tasks", label: "Задачи", hint: "Одна задача на столе", icon: "tasks" },
  { route: "/workspace/placement", label: "Публикации", hint: "Один пост — один маршрут", icon: "publish" },
  { route: "/workspace/stats", label: "Результаты", hint: "Сравнение и вывод", icon: "stats" },
  { route: "/workspace/payouts", label: "Выплаты", hint: "Основание и статус", icon: "money" },
  { route: "/learn", label: "Академия", hint: "Урок и безопасная практика", icon: "learn" },
]);

const ICONS = Object.freeze({
  home: '<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10M9 20v-6h6v6"/>',
  work: '<rect x="3" y="6" width="18" height="14" rx="3"/><path d="M8 6V4h8v2M3 11h18M9 11v2h6v-2"/>',
  media: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 16 3.5-4 3 3 2-2 2.5 3"/><circle cx="8" cy="8.5" r="1.3"/>',
  generate: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><circle cx="12" cy="12" r="3"/>',
  review: '<rect x="5" y="4" width="14" height="17" rx="2.5"/><path d="M9 8h6M9 12h6M9 16h3"/><path d="m14 16 1.5 1.5L19 14"/>',
  tasks: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1.5 1.5L7 4.5M3 12l1.5 1.5L7 10.5M3 18l1.5 1.5L7 16.5"/>',
  publish: '<path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 13v6h14v-6"/>',
  stats: '<path d="M4 20V9M10 20V4M16 20v-7M22 20H2"/>',
  money: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 9h10M7 15h4"/><circle cx="16" cy="14" r="2"/>',
  learn: '<path d="m3 7 9-4 9 4-9 4-9-4Z"/><path d="M6 9v6c3 2 9 2 12 0V9"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  expand: '<path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/><path d="m3 8 6-6M21 8l-6-6M3 16l6 6M21 16l-6 6"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  folder: '<path d="M3 7h7l2 2h9v10H3V7Z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
});

const runtime = {
  queued: false,
  route: routePath(),
  mission: null,
  zen: null,
  zenPlaceholder: null,
  zenClose: null,
  zenScroll: 0,
  videoObserver: null,
  lastVideo: null,
  taskFilterBound: false,
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

function routeMatches(current, target) {
  return current === target || (target === "/learn" && current.startsWith("/learn/"));
}

function escapeMarkup(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function compact(value, limit = 140) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function icon(name, size = 20) {
  const body = ICONS[name] || ICONS.info;
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function isVisible(element) {
  if (!(element instanceof Element) || element.hidden) return false;
  const style = window.getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden";
}

function routeDescriptor(route = routePath()) {
  return ROUTES.find((item) => routeMatches(route, item.route)) || ROUTES[0];
}

function navigate(route) {
  closeMission({ restoreFocus: false });
  closeZen({ restoreFocus: false, immediate: true });
  window.location.hash = `#${String(route || "/workspace/home")}`;
}

function directChildFor(page, node) {
  let current = node;
  while (current?.parentElement && current.parentElement !== page) current = current.parentElement;
  return current?.parentElement === page ? current : null;
}

function markKeep(page, node) {
  const direct = directChildFor(page, node);
  if (direct) direct.dataset.osCleanKeep = "true";
}

function cleanPageConfig() {
  const path = routePath();
  if (path === "/workspace/review") return [".content-review-page", [".review-os-topbar", ".review-os-workbench"]];
  if (path === "/workspace/generation") return [".generation-desktop-os", [".generation-os-topbar", ".generation-os-workbench"]];
  if (path === "/workspace/media") return [".media-finder-page", [".media-finder-topbar", ".media-finder-shell"]];
  if (path === "/workspace/work") return [".work-stage-page", [".work-stage-topbar", ".work-stage-shell"]];
  if (path === "/workspace/tasks") return [".tasks-desk-page", [".tasks-desk-topbar", ".tasks-desk-shell"]];
  if (path === "/workspace/placement") return [".publishing-os-page, .page-wrap", [".publishing-os-topbar", ".publishing-os-shell"]];
  if (path === "/workspace/stats") return [".results-os-page", [".results-os-topbar", ".results-os-shell"]];
  if (path === "/workspace/payouts") return [".payout-ledger-page", [".payout-ledger-topbar", ".payout-ledger-shell"]];
  if (path.startsWith("/learn")) return [".learning-page", [".academy-os-window", ".academy-course-os-window--v2", ".academy-course-os-window"]];
  return null;
}

function isolateCurrentPage() {
  const config = cleanPageConfig();
  if (!config) return;
  const [pageSelector, keepSelectors] = config;
  const page = q(pageSelector);
  if (!page) return;
  page.classList.add("os-clean-page");
  qa(":scope > [data-os-clean-keep]", page).forEach((node) => delete node.dataset.osCleanKeep);
  keepSelectors.forEach((selector) => qa(selector, page).forEach((node) => markKeep(page, node)));
  qa(":scope > .alert-danger, :scope > .alert-warning", page).forEach((node) => node.dataset.osCleanKeep = "true");
}

function homeSourceFacts(page) {
  const source = q(".home-next-action, [data-workspace-primary], .home-next-step", page);
  const action = q("a[href^='#/'], button[data-action]", source);
  const title = compact(q("h1, h2, h3, strong", source)?.textContent || "Продолжить производственный маршрут", 120);
  const hint = compact(q("p:not(.eyebrow), .muted, small", source)?.textContent || "Откройте следующий этап и завершите одно понятное действие.", 220);
  const href = action instanceof HTMLAnchorElement ? action.getAttribute("href") || "" : "";
  const route = href.startsWith("#/") ? href.slice(1).split("?")[0] : "";
  return { source, action, title, hint, route };
}

function homeMarkup(facts) {
  const selected = ROUTES.findIndex((item) => routeMatches(facts.route, item.route));
  const current = selected >= 0 ? selected : 0;
  return `
    <section class="os-clean-home" data-os-clean-keep="true" data-os-clean-stage="${current}">
      <header class="os-clean-home__top">
        <div><small>CONTENTENGINE · РАБОЧЕЕ МЕСТО</small><strong>Сегодня</strong></div>
        <button type="button" data-os-clean-mission>${icon("grid", 19)}<span>Все столы</span></button>
      </header>
      <main class="os-clean-home__body">
        <section class="os-clean-home__action" aria-labelledby="os-clean-home-title">
          <small>ОДИН ЭКРАН · ОДНО ДЕЙСТВИЕ</small>
          <h1 id="os-clean-home-title">${escapeMarkup(facts.title)}</h1>
          <p data-os-clean-home-hint>${escapeMarkup(facts.hint)}</p>
          <button type="button" data-os-clean-home-primary>${icon("right", 19)}<span>Открыть следующий шаг</span></button>
        </section>
        <aside class="os-clean-home__route" aria-label="Производственный маршрут">
          <header><small>МАРШРУТ</small><strong>7 этапов без свалки</strong></header>
          <nav>
            ${ROUTES.filter((item) => ["/workspace/media", "/workspace/generation", "/workspace/review", "/workspace/tasks", "/workspace/placement", "/workspace/stats", "/workspace/payouts"].includes(item.route)).map((item, index) => `
              <button type="button" data-os-clean-stage-route="${item.route}" data-stage-index="${index}" aria-label="${escapeMarkup(item.label)}">
                <span>${String(index + 1).padStart(2, "0")}</span><strong>${escapeMarkup(item.label)}</strong><small>${escapeMarkup(item.hint)}</small>
              </button>`).join("")}
          </nav>
        </aside>
      </main>
    </section>`;
}

function setupHome() {
  if (routePath() !== "/workspace/home") return;
  const page = q("#workspace-content .page-wrap, #workspace-content, .workspace-main .page-wrap");
  if (!page || q(":scope > .os-clean-home", page)) return;
  const facts = homeSourceFacts(page);
  const home = elementFrom(homeMarkup(facts));
  page.prepend(home);
  page.classList.add("os-clean-home-ready", "os-clean-page");
  qa(":scope > *", page).forEach((node) => {
    if (node === home) node.dataset.osCleanKeep = "true";
  });
  const title = q("#os-clean-home-title", home);
  const hint = q("[data-os-clean-home-hint]", home);
  const primary = q("[data-os-clean-home-primary]", home);
  let selectedRoute = facts.route || "/workspace/work";
  const updateStage = (route) => {
    const descriptor = routeDescriptor(route);
    selectedRoute = descriptor.route;
    title.textContent = descriptor.label;
    hint.textContent = descriptor.hint;
    qa("[data-os-clean-stage-route]", home).forEach((button) => {
      const active = button.dataset.osCleanStageRoute === selectedRoute;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-current", active ? "step" : "false");
    });
    primary.querySelector("span").textContent = `Открыть: ${descriptor.label}`;
  };
  qa("[data-os-clean-stage-route]", home).forEach((button) => {
    button.addEventListener("click", () => updateStage(button.dataset.osCleanStageRoute));
  });
  primary.addEventListener("click", () => {
    if (facts.action && !selectedRoute) facts.action.click();
    else navigate(selectedRoute || facts.route || "/workspace/work");
  });
  q("[data-os-clean-mission]", home)?.addEventListener("click", openMission);
  updateStage(selectedRoute);
}

function missionMarkup() {
  return `
    <div class="os-clean-mission-backdrop">
      <section class="os-clean-mission" role="dialog" aria-modal="true" aria-labelledby="os-clean-mission-title">
        <header>
          <div><small>MISSION CONTROL</small><h1 id="os-clean-mission-title">Рабочие столы</h1><p>Откройте одно направление. Остальные не конкурируют за внимание.</p></div>
          <button type="button" data-os-clean-mission-close aria-label="Закрыть">${icon("close", 20)}</button>
        </header>
        <label class="os-clean-mission__search">${icon("search", 18)}<input type="search" placeholder="Найти стол" autocomplete="off" /></label>
        <div class="os-clean-mission__grid">
          ${ROUTES.map((item, index) => `
            <button type="button" data-os-clean-mission-route="${item.route}" data-keywords="${escapeMarkup(`${item.label} ${item.hint}`.toLocaleLowerCase("ru-RU"))}">
              <span>${icon(item.icon, 24)}</span><small>${String(index + 1).padStart(2, "0")}</small><strong>${escapeMarkup(item.label)}</strong><p>${escapeMarkup(item.hint)}</p>
            </button>`).join("")}
        </div>
      </section>
    </div>`;
}

function openMission(event) {
  event?.preventDefault?.();
  if (runtime.mission) return;
  const overlay = elementFrom(missionMarkup());
  runtime.mission = overlay;
  document.body.append(overlay);
  document.body.classList.add("os-clean-mission-open");
  const input = q("input", overlay);
  const filter = () => {
    const query = String(input.value || "").trim().toLocaleLowerCase("ru-RU");
    qa("[data-os-clean-mission-route]", overlay).forEach((button) => {
      button.hidden = Boolean(query) && !String(button.dataset.keywords || "").includes(query);
    });
  };
  input.addEventListener("input", filter);
  overlay.addEventListener("click", (click) => {
    if (click.target === overlay || (click.target instanceof Element && click.target.closest("[data-os-clean-mission-close]"))) closeMission();
    const button = click.target instanceof Element ? click.target.closest("[data-os-clean-mission-route]") : null;
    if (button) navigate(button.dataset.osCleanMissionRoute);
  });
  q("[data-os-clean-mission-close]", overlay)?.focus({ preventScroll: true });
}

function closeMission({ restoreFocus = true } = {}) {
  const overlay = runtime.mission;
  if (!overlay) return;
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    if (runtime.mission === overlay) runtime.mission = null;
    document.body.classList.remove("os-clean-mission-open");
    if (restoreFocus) q(".ce-mac-dock__mission, [data-os-clean-mission]")?.focus?.({ preventScroll: true });
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 180);
}

function zenSurface() {
  const path = routePath();
  const selectors = path === "/workspace/review" ? [".review-os-workbench"]
    : path === "/workspace/generation" ? [".generation-os-workbench"]
      : path === "/workspace/media" ? [".media-finder-shell"]
        : path === "/workspace/work" ? [".work-stage-shell"]
          : path === "/workspace/tasks" ? [".tasks-desk-shell"]
            : path === "/workspace/placement" ? [".publishing-os-shell"]
              : path === "/workspace/stats" ? [".results-os-shell"]
                : path === "/workspace/payouts" ? [".payout-ledger-shell"]
                  : path.startsWith("/learn") ? [".academy-course-os-window--v2", ".academy-os-window", ".academy-course-os-window"]
                    : [".os-clean-home"];
  return selectors.map((selector) => q(selector)).find((node) => isVisible(node)) || null;
}

function convertFocusButtons() {
  qa("[data-workspace-focus-card], .desk-focus-button").forEach((button) => {
    button.removeAttribute("data-workspace-focus-card");
    button.dataset.osCleanZen = "true";
    button.setAttribute("aria-label", "Развернуть текущее рабочее пространство");
    const label = q(".desk-focus-button__label", button);
    if (label) label.textContent = "Фокус";
  });
}

function rescueLegacyFocus() {
  qa(".workspace-task-focused").forEach((surface) => {
    surface.classList.remove("workspace-task-focused");
    surface.removeAttribute("aria-modal");
    q(":scope > .workspace-focus-chrome", surface)?.remove();
  });
  qa(".workspace-focus-backdrop").forEach((node) => node.remove());
  document.body.classList.remove("workspace-focus-mode");
}

function openZen(surface = zenSurface()) {
  if (!surface || runtime.zen) return;
  rescueLegacyFocus();
  const placeholder = document.createComment("contentengine-os-clean-zen");
  surface.before(placeholder);
  runtime.zen = surface;
  runtime.zenPlaceholder = placeholder;
  runtime.zenScroll = window.scrollY;
  surface.classList.add("os-clean-zen-surface");
  const close = elementFrom(`<button class="os-clean-zen-close" type="button" aria-label="Закрыть фокус">${icon("close", 18)}<span>Вернуться</span></button>`);
  close.addEventListener("click", () => closeZen());
  surface.prepend(close);
  runtime.zenClose = close;
  document.body.append(surface);
  document.body.classList.add("os-clean-zen-open");
  close.focus({ preventScroll: true });
}

function closeZen({ restoreFocus = true, immediate = false } = {}) {
  const surface = runtime.zen;
  if (!surface) return;
  const placeholder = runtime.zenPlaceholder;
  const close = runtime.zenClose;
  const finish = () => {
    close?.remove();
    surface.classList.remove("os-clean-zen-surface");
    if (placeholder?.parentNode) placeholder.before(surface);
    else surface.remove();
    placeholder?.remove?.();
    runtime.zen = null;
    runtime.zenPlaceholder = null;
    runtime.zenClose = null;
    document.body.classList.remove("os-clean-zen-open");
    window.scrollTo({ top: runtime.zenScroll, left: 0, behavior: "auto" });
    if (restoreFocus) q("[data-os-clean-zen]")?.focus?.({ preventScroll: true });
    scheduleMount();
  };
  surface.classList.add("is-closing");
  if (immediate || REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 180);
}

function canonicalDockRoute(anchor) {
  const href = String(anchor.getAttribute("href") || "");
  const route = href.startsWith("#/") ? href.slice(1).split("?")[0].replace(/\/$/, "") : "";
  if (route.startsWith("/learn/")) return "/learn";
  return route;
}

function cleanDock() {
  const glass = q(".ce-mac-dock__glass");
  if (!glass) return;
  q(".os-v3-dock-tools", glass)?.remove();
  qa(".ce-mac-dock__separator", glass).forEach((node) => node.remove());
  const links = qa("a.ce-mac-dock__item", glass);
  const byRoute = new Map();
  links.forEach((link) => {
    const route = canonicalDockRoute(link);
    if (!ROUTES.some((item) => item.route === route) || byRoute.has(route)) {
      link.remove();
      return;
    }
    byRoute.set(route, link);
    link.href = `#${route}`;
    const descriptor = routeDescriptor(route);
    link.setAttribute("aria-label", descriptor.label);
    const tooltip = q(".ce-mac-dock__tooltip", link);
    if (tooltip) tooltip.textContent = descriptor.label;
  });
  const mission = q(".ce-mac-dock__mission", glass) || elementFrom(`<button class="ce-mac-dock__item ce-mac-dock__mission" type="button" aria-label="Все рабочие столы"><span class="ce-mac-dock__tooltip">Все столы</span><span class="ce-mac-dock__icon">${icon("grid", 22)}</span></button>`);
  mission.setAttribute("data-os-clean-mission", "true");
  ROUTES.forEach((item) => {
    const link = byRoute.get(item.route);
    if (link) glass.append(link);
  });
  const separator = elementFrom('<span class="ce-mac-dock__separator os-clean-dock-separator" aria-hidden="true"></span>');
  glass.append(separator, mission);
  let search = q(".os-clean-dock-search", glass);
  if (!search) {
    search = elementFrom(`<button class="ce-mac-dock__item os-clean-dock-search" type="button" aria-label="Поиск"><span class="ce-mac-dock__tooltip">Поиск · ⌘K</span><span class="ce-mac-dock__icon">${icon("search", 22)}</span></button>`);
    search.addEventListener("click", () => window.ContentEngineOSV3?.openSpotlight?.());
  }
  glass.append(search);
}

function taskSource(text) {
  const value = String(text || "").toLocaleLowerCase("ru-RU");
  if (/публикац|размест|ссылка|url/u.test(value)) return "Публикации";
  if (/провер|review|qa|риск/u.test(value)) return "Проверка";
  if (/генерац|ролик|runway|seedance|создать контент/u.test(value)) return "Создание контента";
  if (/выплат|начислен/u.test(value)) return "Выплаты";
  return "Ручная задача";
}

function enhanceTasks() {
  const shell = q(".tasks-desk-shell");
  if (!shell) return;
  const list = q(".tasks-desk-list", shell);
  if (list && !q(".os-clean-task-filter", shell)) {
    const filter = elementFrom(`
      <div class="os-clean-task-filter">
        <label>${icon("search", 16)}<input type="search" placeholder="Найти задачу" autocomplete="off" /></label>
        <select aria-label="Статус задачи"><option value="all">Все</option><option value="active">В работе</option><option value="blocked">Блокеры</option><option value="done">Готовые</option></select>
        <span data-os-clean-task-count></span>
      </div>`);
    list.before(filter);
    const apply = () => {
      const query = String(q("input", filter).value || "").trim().toLocaleLowerCase("ru-RU");
      const status = q("select", filter).value;
      let visible = 0;
      qa(".tasks-desk-list-item", list).forEach((button) => {
        const text = String(button.textContent || "").toLocaleLowerCase("ru-RU");
        const tone = q("i[data-tone]", button)?.dataset.tone || "";
        const matchStatus = status === "all"
          || (status === "blocked" && tone === "danger")
          || (status === "done" && tone === "success")
          || (status === "active" && !["danger", "success"].includes(tone));
        const show = matchStatus && (!query || text.includes(query));
        button.hidden = !show;
        if (show) visible += 1;
      });
      q("[data-os-clean-task-count]", filter).textContent = `${visible} видно`;
      const active = q(".tasks-desk-list-item.is-active", list);
      if (active?.hidden) qa(".tasks-desk-list-item", list).find((item) => !item.hidden)?.click();
    };
    filter.addEventListener("input", apply);
    filter.addEventListener("change", apply);
    apply();
  }
  qa(".tasks-desk-card", shell).forEach((card) => {
    if (q(":scope > .os-clean-task-origin", card)) return;
    const text = compact(card.textContent, 1200);
    const source = taskSource(text);
    const description = compact(q("p:not(.eyebrow), .task-description, .muted", card)?.textContent || "Выполните критерий задачи и используйте штатную кнопку смены статуса.", 190);
    const origin = elementFrom(`
      <aside class="os-clean-task-origin"><small>ИСТОЧНИК ЗАДАЧИ</small><strong>${escapeMarkup(source)}</strong><p>${escapeMarkup(description)}</p></aside>`);
    const header = q(":scope > .task-top, :scope > header", card);
    if (header) header.after(origin);
    else card.prepend(origin);
  });
}

function enhanceMedia() {
  const page = q(".media-finder-page");
  if (!page) return;
  qa(".media-card", page).forEach((card) => {
    if (q(".os-clean-media-kind", card)) return;
    const kind = String(card.dataset.mediaFinderKind || (card.dataset.mediaFinderType === "video" ? "video" : "image"));
    const labels = { product: "Товар", reference: "Референс", video: "Видео", image: "Без папки" };
    const badge = elementFrom(`<span class="os-clean-media-kind" data-kind="${escapeMarkup(kind)}">${escapeMarkup(labels[kind] || "Без папки")}</span>`);
    q(".media-info", card)?.prepend(badge);
  });
  const nav = q(".media-finder-sidebar nav", page);
  if (nav && !q("[data-os-media-folder='uncategorized']", nav)) {
    const button = elementFrom(`<button type="button" data-os-media-folder="uncategorized">${icon("folder", 17)}<span>Без папки</span><b>0</b></button>`);
    nav.append(button);
    const applyUnsorted = () => {
      const active = page.dataset.osMediaCustomFolder === "uncategorized";
      let count = 0;
      qa(".media-card", page).forEach((card) => {
        const match = String(card.dataset.mediaFinderKind || "image") === "image";
        if (match) count += 1;
        if (active) card.hidden = !match;
      });
      q("b", button).textContent = String(count);
      button.classList.toggle("is-active", active);
    };
    button.addEventListener("click", () => {
      page.dataset.osMediaCustomFolder = "uncategorized";
      qa("[data-media-folder]", nav).forEach((item) => item.classList.remove("is-active"));
      applyUnsorted();
    });
    nav.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest("[data-media-folder]")) {
        delete page.dataset.osMediaCustomFolder;
        window.setTimeout(applyUnsorted, 0);
      }
    });
    q("[data-media-search]", page)?.addEventListener("input", () => window.setTimeout(applyUnsorted, 0));
    applyUnsorted();
  }
}

function enhanceTableSearch() {
  qa(".results-ledger-shell, .payout-ledger-shell").forEach((shell) => {
    qa(".data-table", shell).forEach((table, index) => {
      const holder = table.closest(".table-wrap, .data-table-wrap") || table;
      if (holder.previousElementSibling?.classList?.contains("os-clean-table-search")) return;
      const toolbar = elementFrom(`<div class="os-clean-table-search"><label>${icon("search", 16)}<input type="search" placeholder="Поиск по реестру" autocomplete="off" /></label><span></span></div>`);
      holder.before(toolbar);
      const rows = qa("tbody tr", table);
      const apply = () => {
        const query = String(q("input", toolbar).value || "").trim().toLocaleLowerCase("ru-RU");
        let shown = 0;
        rows.forEach((row) => {
          const match = !query || String(row.textContent || "").toLocaleLowerCase("ru-RU").includes(query);
          row.hidden = !match;
          if (match) shown += 1;
        });
        q("span", toolbar).textContent = `${shown} из ${rows.length}`;
      };
      toolbar.dataset.tableIndex = String(index);
      toolbar.addEventListener("input", apply);
      apply();
    });
  });
}

function enhanceReviewRisks() {
  qa(".content-review-findings").forEach((container) => {
    if (container.dataset.osCleanRiskNavigator === "true") return;
    const cards = qa(":scope > article, :scope > .card, :scope > .content-review-finding, :scope > .finding-card", container)
      .filter((card) => !card.matches("header"));
    if (cards.length < 4) return;
    container.dataset.osCleanRiskNavigator = "true";
    let index = 0;
    const nav = elementFrom(`
      <div class="os-clean-risk-nav"><button type="button" data-risk-prev>${icon("left", 17)}<span>Назад</span></button><strong data-risk-position></strong><button type="button" data-risk-next><span>Далее</span>${icon("right", 17)}</button></div>`);
    container.prepend(nav);
    const show = (next) => {
      index = Math.max(0, Math.min(cards.length - 1, next));
      cards.forEach((card, cardIndex) => {
        card.hidden = cardIndex !== index;
        card.classList.toggle("is-active", cardIndex === index);
      });
      q("[data-risk-position]", nav).textContent = `Риск ${index + 1} из ${cards.length}`;
      q("[data-risk-prev]", nav).disabled = index <= 0;
      q("[data-risk-next]", nav).disabled = index >= cards.length - 1;
    };
    nav.addEventListener("click", (event) => {
      if (event.target instanceof Element && event.target.closest("[data-risk-prev]")) show(index - 1);
      if (event.target instanceof Element && event.target.closest("[data-risk-next]")) show(index + 1);
    });
    show(0);
  });
}

function recoverPublishing() {
  const shell = q(".publishing-os-shell");
  if (!shell) return;
  const cards = qa(".placement-card", shell);
  const visibleCards = cards.filter((card) => !card.hidden && isVisible(card));
  if (cards.length && !visibleCards.length) q("[data-publishing-filter='all']")?.click();
  const queue = q(".publishing-os-queue, .publishing-os-sidebar", shell);
  if (!cards.length && queue && !q(".os-clean-publishing-empty", shell)) {
    const empty = elementFrom(`<div class="os-clean-publishing-empty"><span>${icon("publish", 28)}</span><strong>Публикаций пока нет</strong><p>Сначала завершите проверку одного материала — после этого появится маршрут публикации.</p><a href="#/workspace/review">Открыть проверку</a></div>`);
    q(".publishing-os-stage, .publishing-os-workspace", shell)?.append(empty);
  }
}

function videoGovernor() {
  qa("video").forEach((video) => {
    video.autoplay = false;
    video.loop = false;
    video.removeAttribute("autoplay");
    video.removeAttribute("loop");
    video.playsInline = true;
    if (!video.hasAttribute("preload") || video.preload === "auto") video.preload = "metadata";
    if (!isVisible(video)) video.pause?.();
    if (runtime.videoObserver && video.dataset.osCleanObserved !== "true") {
      video.dataset.osCleanObserved = "true";
      runtime.videoObserver.observe(video);
    }
  });
}

function setupVideoGovernor() {
  if (!runtime.videoObserver && typeof IntersectionObserver === "function") {
    runtime.videoObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting || entry.intersectionRatio < 0.15) entry.target.pause?.();
      });
    }, { threshold: [0, 0.15, 0.6] });
  }
  videoGovernor();
}

function removeBrokenSplitEntryPoints() {
  q(".os-v3-dock-tools")?.remove();
  qa("[data-os-v3-capsule-split]").forEach((button) => button.remove());
  qa(".os-v3-command-palette button").forEach((button) => {
    if (/split view|два связанных рабочих объекта/iu.test(button.textContent || "")) button.remove();
  });
}

function mount() {
  document.documentElement.dataset.contentengineClean = "v3-2";
  document.body.classList.add("contentengine-os-clean");
  const route = routePath();
  if (runtime.route !== route) {
    runtime.route = route;
    closeMission({ restoreFocus: false });
    closeZen({ restoreFocus: false, immediate: true });
  }
  rescueLegacyFocus();
  setupHome();
  isolateCurrentPage();
  convertFocusButtons();
  cleanDock();
  enhanceTasks();
  enhanceMedia();
  enhanceTableSearch();
  enhanceReviewRisks();
  recoverPublishing();
  setupVideoGovernor();
  removeBrokenSplitEntryPoints();
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;
  if (target.closest("[data-os-clean-zen]")) {
    event.preventDefault();
    event.stopImmediatePropagation();
    openZen();
    return;
  }
  if (target.closest("[data-ce-open-mission], .ce-mac-dock__mission, [data-os-clean-mission]")) {
    event.preventDefault();
    openMission(event);
  }
}, true);

document.addEventListener("keydown", (event) => {
  const target = event.target instanceof Element ? event.target : null;
  if (target?.closest(TYPING)) return;
  if (event.key === "Escape") {
    if (runtime.zen) {
      event.preventDefault();
      event.stopImmediatePropagation();
      closeZen();
      return;
    }
    if (runtime.mission) {
      event.preventDefault();
      closeMission();
      return;
    }
  }
  if (event.key.toLocaleLowerCase("ru-RU") === "f" && !event.metaKey && !event.ctrlKey && !event.altKey) {
    const surface = zenSurface();
    if (surface) {
      event.preventDefault();
      event.stopImmediatePropagation();
      openZen(surface);
    }
  }
  if (event.altKey && event.shiftKey && event.key.toLocaleLowerCase("ru-RU") === "s") {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);

document.addEventListener("play", (event) => {
  const video = event.target;
  if (!(video instanceof HTMLVideoElement)) return;
  qa("video").forEach((candidate) => {
    if (candidate !== video && !candidate.paused) candidate.pause();
  });
  runtime.lastVideo = video;
}, true);

new MutationObserver(scheduleMount).observe(q("#app") || document.body, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount, { passive: true });
window.addEventListener("pageshow", scheduleMount, { passive: true });
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();

window.ContentEngineVisualQA = Object.freeze({
  build: CLEAN_BUILD,
  openMission,
  openZen,
  closeZen,
  scheduleMount,
});
