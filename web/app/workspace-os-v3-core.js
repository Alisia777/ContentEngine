/*
 * ContentEngine OS v3 core.
 *
 * Shared desktop behaviours for the production loop: Spotlight, product
 * capsules, safe split view, handoff drafts, frame notes, UI undo and an
 * honest multi-tab activity indicator. The module is presentation-only: it
 * does not call business APIs, does not submit forms and never reads secret
 * fields.
 */

const BUILD_ID = "20260731.os3.1";
const UI_STATE_KEY = "contentengine.os-v3.ui.v1";
const RECENT_ENTITY_KEY = "contentengine.os-v3.entities.v1";
const WORK_SNAPSHOT_KEY = "contentengine.os-v3.work-snapshot.v1";
const HANDOFF_PREFIX = "contentengine.os-v3.handoff.v1";
const FRAME_NOTE_PREFIX = "contentengine.os-v3.frame-notes.v1";
const PRESENCE_CHANNEL = "contentengine-os-v3-presence";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const FINE_POINTER = window.matchMedia("(hover: hover) and (pointer: fine)");
const SPRING = "cubic-bezier(0.16, 1, 0.3, 1)";
const SECRET_PATTERN = /password|passcode|otp|token|secret|api[_-]?key|authorization|credential/iu;

const ROUTES = Object.freeze([
  ["/workspace/home", "Обзор", "Главное рабочее пространство"],
  ["/workspace/work", "Моя работа", "Сейчас, жду и дальше"],
  ["/workspace/media", "Материалы", "Finder и Quick Look"],
  ["/workspace/research", "Разбор товара", "Товар, гипотезы и сценарии"],
  ["/workspace/generation", "Генерация", "Новый запуск и очередь"],
  ["/workspace/review", "Проверка", "Качество, риски и решение"],
  ["/workspace/placement", "Публикации", "Подготовка площадки и ссылка"],
  ["/workspace/tasks", "Задачи", "Назначенная работа"],
  ["/workspace/stats", "Результаты", "Публикации и эффект"],
  ["/workspace/payouts", "Выплаты", "Начисления и основания"],
  ["/learn", "Академия", "Обучение и лаборатории"],
]);

const ICONS = Object.freeze({
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  capsule: '<path d="M8 3h8a5 5 0 0 1 0 10H8A5 5 0 0 1 8 3Z"/><path d="m8 13 8-10"/>',
  split: '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M12 4v16"/>',
  handoff: '<path d="M4 12h13"/><path d="m13 7 5 5-5 5"/><path d="M4 5v14"/>',
  refresh: '<path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M6.1 8A7 7 0 0 1 18 6l2 6M4 12l2 6a7 7 0 0 0 11.9-2"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  route: '<rect x="4" y="4" width="16" height="16" rx="4"/><path d="M8 12h8M12 8l4 4-4 4"/>',
  product: '<path d="m4 7 8-4 8 4-8 4-8-4Z"/><path d="M4 7v10l8 4 8-4V7M12 11v10"/>',
  command: '<path d="M9 5H6a3 3 0 1 0 3 3V5Zm6 0h3a3 3 0 1 1-3 3V5ZM9 19H6a3 3 0 1 1 3-3v3Zm6 0h3a3 3 0 1 0-3-3v3Z"/><path d="M9 5h6v14H9z"/>',
  undo: '<path d="M9 7 4 12l5 5"/><path d="M5 12h8a6 6 0 0 1 6 6"/>',
  note: '<path d="M4 4h16v16H4z"/><path d="M8 9h8M8 13h5"/>',
});

const runtime = {
  queued: false,
  route: routePath(),
  memory: readJson(storage("local"), UI_STATE_KEY, {}),
  commandOverlay: null,
  capsuleOverlay: null,
  splitOverlay: null,
  handoffOverlay: null,
  frameOverlay: null,
  undoBar: null,
  undoTimer: 0,
  movedNodes: [],
  selectedCommand: 0,
  lastFocus: null,
  channel: null,
  tabId: crypto?.randomUUID?.() || `tab-${Date.now()}-${Math.random().toString(16).slice(2)}`,
  peers: new Map(),
  presenceTimer: 0,
  workSnapshot: readJson(storage("session"), WORK_SNAPSHOT_KEY, null),
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

function routeLabel(route = routePath()) {
  return ROUTES.find(([path]) => route === path || (path === "/learn" && route.startsWith("/learn/")))?.[1]
    || compact(q("h1, .review-os-title strong, .generation-os-title strong, .media-finder-title strong")?.textContent, 48)
    || "Рабочее пространство";
}

function storage(kind) {
  try {
    return kind === "session" ? window.sessionStorage : window.localStorage;
  } catch {
    return null;
  }
}

function readJson(target, key, fallback) {
  try {
    const parsed = JSON.parse(target?.getItem(key) || "null");
    return parsed === null || parsed === undefined ? fallback : parsed;
  } catch {
    return fallback;
  }
}

function writeJson(target, key, value) {
  try {
    target?.setItem(key, JSON.stringify(value));
  } catch {
    // Preferences are optional and must never block production work.
  }
}

function remember(patch) {
  runtime.memory = { ...runtime.memory, ...patch };
  writeJson(storage("local"), UI_STATE_KEY, runtime.memory);
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

function icon(name, size = 20) {
  const body = ICONS[name] || ICONS.route;
  return `<svg class="os-v3-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

function elementFrom(markup) {
  const template = document.createElement("template");
  template.innerHTML = markup.trim();
  return template.content.firstElementChild;
}

function visible(element) {
  if (!(element instanceof Element) || element.hidden) return false;
  const style = window.getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden";
}

function safeTextField(field) {
  if (!(field instanceof HTMLInputElement || field instanceof HTMLTextAreaElement || field instanceof HTMLSelectElement)) return false;
  if (field instanceof HTMLInputElement && ["password", "hidden", "file"].includes(field.type)) return false;
  const identity = `${field.name || ""} ${field.id || ""} ${field.autocomplete || ""}`;
  return !SECRET_PATTERN.test(identity);
}

function currentEntity(root = document) {
  const route = routePath();
  const selected = q(
    ".my-work-item.is-selected, .task-card.is-selected, .placement-card.is-selected, .media-card.is-selected, "
      + "[aria-selected='true'].my-work-item, [aria-selected='true'].task-card, [aria-selected='true'].placement-card, "
      + ".generation-os-panel.is-active, .review-os-result-panel.is-active, .academy-v2-panel.is-active",
    root,
  ) || q(".task-card, .placement-card, .my-work-item, .media-card, [data-generation-job-id]", root);

  const scope = selected || root;
  const skuField = qa("input[name='sku'], select[name='sku']", scope).find((field) => safeTextField(field) && String(field.value || "").trim())
    || qa("input[name='sku'], select[name='sku']", root).find((field) => safeTextField(field) && String(field.value || "").trim());
  const productField = qa("input[name='product_name'], textarea[name='product_name']", scope).find((field) => safeTextField(field) && String(field.value || "").trim())
    || qa("input[name='product_name'], textarea[name='product_name']", root).find((field) => safeTextField(field) && String(field.value || "").trim());
  const text = compact(scope?.textContent, 1200);
  const skuMatch = text.match(/(?:SKU|артикул|код товара)\s*[:#№-]?\s*([A-ZА-ЯЁ0-9][A-ZА-ЯЁ0-9._/-]{2,60})/iu);
  const id = String(
    selected?.dataset?.workItemId
      || selected?.dataset?.taskId
      || selected?.dataset?.placementId
      || selected?.dataset?.generationJobId
      || selected?.dataset?.mediaFinderIndex
      || selected?.dataset?.reviewResultStep
      || "",
  ).trim();
  const title = compact(
    q("h1, h2, h3, .my-work-item-copy h3, .media-info > strong, .task-top h3, .placement-top h3, strong", scope)?.textContent
      || productField?.value
      || routeLabel(route),
    140,
  );
  const sku = compact(skuField?.value || skuMatch?.[1] || "", 80);
  const entity = {
    id: id || `${route}:${sku || title}`,
    route,
    type: route.includes("review") ? "review"
      : route.includes("generation") ? "generation"
        : route.includes("placement") ? "placement"
          : route.includes("payout") ? "payout"
            : route.includes("media") ? "media"
              : route.includes("task") ? "task"
                : route.startsWith("/learn") ? "learning"
                  : "workspace",
    title,
    sku,
    productName: compact(productField?.value || title, 160),
    updatedAt: Date.now(),
  };
  persistRecentEntity(entity);
  return entity;
}

function persistRecentEntity(entity) {
  if (!entity?.title) return;
  const recent = readJson(storage("local"), RECENT_ENTITY_KEY, []);
  const list = Array.isArray(recent) ? recent : [];
  const next = [entity, ...list.filter((item) => item?.id !== entity.id)].slice(0, 12);
  writeJson(storage("local"), RECENT_ENTITY_KEY, next);
}

function recentEntities() {
  const recent = readJson(storage("local"), RECENT_ENTITY_KEY, []);
  return Array.isArray(recent) ? recent.filter((item) => item?.title && item?.route).slice(0, 12) : [];
}

function navigate(route) {
  const resolved = String(route || "").startsWith("/") ? route : "/workspace/home";
  window.location.hash = `#${resolved}`;
}

function animateIn(element, keyframes, options = {}) {
  if (!element || REDUCED_MOTION.matches || typeof element.animate !== "function") return null;
  return element.animate(keyframes, { duration: 360, easing: SPRING, fill: "none", ...options });
}

function focusable(root) {
  return qa("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])", root)
    .filter((element) => visible(element));
}

function trapDialog(event, dialog) {
  if (event.key !== "Tab") return;
  const items = focusable(dialog);
  if (!items.length) return;
  const first = items[0];
  const last = items.at(-1);
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function closeOverlay(name, { restoreFocus = true } = {}) {
  const key = `${name}Overlay`;
  const overlay = runtime[key];
  if (!overlay) return;
  overlay.classList.add("is-closing");
  const finish = () => {
    overlay.remove();
    runtime[key] = null;
    document.body.classList.remove(`os-v3-${name}-open`);
    if (restoreFocus) runtime.lastFocus?.focus?.({ preventScroll: true });
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 230);
}

function routeCommands() {
  return ROUTES.map(([route, title, description]) => ({
    id: `route:${route}`,
    title,
    subtitle: description,
    keywords: `${title} ${description} ${route}`.toLocaleLowerCase("ru-RU"),
    icon: "route",
    run: () => navigate(route),
  }));
}

function dynamicCommands() {
  const result = [];
  const selectors = [
    [".my-work-item", "Работа"],
    [".task-card", "Задача"],
    [".placement-card", "Публикация"],
    [".media-card", "Материал"],
    ["[data-generation-job-id]", "Генерация"],
    ["tr[data-payout-id]", "Результат"],
  ];
  selectors.forEach(([selector, type]) => {
    qa(selector).slice(0, 40).forEach((element, index) => {
      const title = compact(q("h2, h3, strong, td", element)?.textContent || element.textContent, 100);
      if (!title) return;
      const subtitle = compact(q("p, small, .badge, td:nth-child(2)", element)?.textContent || type, 90);
      result.push({
        id: `dom:${selector}:${index}:${title}`,
        title,
        subtitle: `${type} · ${subtitle}`,
        keywords: `${title} ${subtitle} ${type}`.toLocaleLowerCase("ru-RU"),
        icon: type === "Материал" ? "product" : "route",
        run: () => {
          element.scrollIntoView({ block: "center", behavior: REDUCED_MOTION.matches ? "auto" : "smooth" });
          element.focus?.({ preventScroll: true });
          element.classList.add("os-v3-command-target");
          window.setTimeout(() => element.classList.remove("os-v3-command-target"), 1000);
        },
      });
    });
  });
  return result;
}

function systemCommands() {
  return [
    {
      id: "system:capsule",
      title: "Открыть рабочую капсулу",
      subtitle: "Товар, задача и весь производственный маршрут",
      keywords: "капсула товар sku объект маршрут",
      icon: "capsule",
      run: openCapsule,
    },
    {
      id: "system:split",
      title: runtime.splitOverlay ? "Закрыть Split View" : "Открыть Split View",
      subtitle: "Два связанных рабочих объекта рядом",
      keywords: "split разделить две панели сравнить",
      icon: "split",
      run: toggleSplitView,
    },
    {
      id: "system:handoff",
      title: "Передать контекст",
      subtitle: "Что сделано, что осталось и где блокер",
      keywords: "передать handoff контекст сотруднику",
      icon: "handoff",
      run: openHandoff,
    },
    {
      id: "system:refresh",
      title: "Обновить текущее пространство",
      subtitle: "Использует штатную кнопку обновления раздела",
      keywords: "обновить refresh синхронизация",
      icon: "refresh",
      run: () => q("[data-action='refresh-section'], [data-action='refresh-my-work'], [data-action='refresh-content-review']")?.click(),
    },
    {
      id: "system:blockers",
      title: "Показать блокеры",
      subtitle: "Открыть Stage Manager и начать с проблем",
      keywords: "мои блокеры проблемы просрочено",
      icon: "route",
      run: () => {
        writeJson(storage("session"), "contentengine.os-v3.work-intent", { lane: "now", filter: "blocked", at: Date.now() });
        navigate("/workspace/work");
      },
    },
    {
      id: "system:academy",
      title: "Открыть Академию",
      subtitle: "Уроки, лаборатории и безопасная практика",
      keywords: "академия обучение урок лаборатория",
      icon: "route",
      run: () => navigate("/learn"),
    },
  ];
}

function commandRecords(query = "") {
  const needle = String(query || "").trim().toLocaleLowerCase("ru-RU");
  const records = [...systemCommands(), ...routeCommands(), ...dynamicCommands()];
  if (!needle) return records.slice(0, 40);
  const tokens = needle.split(/\s+/).filter(Boolean);
  return records
    .map((item) => {
      const haystack = `${item.title} ${item.subtitle} ${item.keywords}`.toLocaleLowerCase("ru-RU");
      const score = tokens.reduce((total, token) => total + (haystack.includes(token) ? 2 : 0) + (item.title.toLocaleLowerCase("ru-RU").startsWith(token) ? 3 : 0), 0);
      return { item, score };
    })
    .filter(({ score }) => score > 0)
    .sort((left, right) => right.score - left.score || left.item.title.localeCompare(right.item.title, "ru"))
    .slice(0, 40)
    .map(({ item }) => item);
}

function renderCommandResults(overlay, records) {
  const list = q("[data-os-v3-command-list]", overlay);
  if (!list) return;
  runtime.selectedCommand = Math.max(0, Math.min(runtime.selectedCommand, Math.max(0, records.length - 1)));
  overlay._commandRecords = records;
  list.innerHTML = records.length ? records.map((item, index) => `
    <button type="button" class="os-v3-command${index === runtime.selectedCommand ? " is-selected" : ""}" data-os-v3-command-index="${index}">
      <span>${icon(item.icon, 19)}</span>
      <span><strong>${escapeMarkup(item.title)}</strong><small>${escapeMarkup(item.subtitle || "")}</small></span>
      <kbd>${index < 9 ? index + 1 : "↵"}</kbd>
    </button>
  `).join("") : '<div class="os-v3-command-empty"><strong>Ничего не найдено</strong><span>Попробуйте товар, статус, раздел или действие.</span></div>';
}

function runCommand(index) {
  const records = runtime.commandOverlay?._commandRecords || [];
  const command = records[Number(index) || 0];
  if (!command) return;
  closeOverlay("command", { restoreFocus: false });
  window.setTimeout(() => command.run?.(), REDUCED_MOTION.matches ? 0 : 80);
}

function openSpotlight() {
  if (runtime.commandOverlay) return;
  runtime.lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const overlay = elementFrom(`
    <div class="os-v3-command-backdrop">
      <section class="os-v3-command-palette" role="dialog" aria-modal="true" aria-labelledby="os-v3-command-title">
        <header>
          <span>${icon("search", 21)}</span>
          <input id="os-v3-command-title" type="search" autocomplete="off" placeholder="Найти товар, задачу, раздел или команду" aria-label="Spotlight ContentEngine" />
          <kbd>Esc</kbd>
        </header>
        <div class="os-v3-command-context"><span>${escapeMarkup(routeLabel())}</span><small>${escapeMarkup(currentEntity().sku || "Текущее пространство")}</small></div>
        <div class="os-v3-command-list" data-os-v3-command-list role="listbox"></div>
        <footer><span><kbd>↑↓</kbd> выбрать</span><span><kbd>Enter</kbd> открыть</span><span><kbd>⌘K</kbd> Spotlight</span></footer>
      </section>
    </div>`);
  runtime.commandOverlay = overlay;
  runtime.selectedCommand = 0;
  document.body.append(overlay);
  document.body.classList.add("os-v3-command-open");
  const input = q("input", overlay);
  renderCommandResults(overlay, commandRecords());
  input.addEventListener("input", () => {
    runtime.selectedCommand = 0;
    renderCommandResults(overlay, commandRecords(input.value));
  });
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closeOverlay("command");
    const button = event.target instanceof Element ? event.target.closest("[data-os-v3-command-index]") : null;
    if (button) runCommand(button.dataset.osV3CommandIndex);
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeOverlay("command");
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const total = overlay._commandRecords?.length || 0;
      if (!total) return;
      runtime.selectedCommand = (runtime.selectedCommand + (event.key === "ArrowDown" ? 1 : -1) + total) % total;
      renderCommandResults(overlay, overlay._commandRecords);
      q(`[data-os-v3-command-index='${runtime.selectedCommand}']`, overlay)?.scrollIntoView({ block: "nearest" });
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      runCommand(runtime.selectedCommand);
      return;
    }
    trapDialog(event, q(".os-v3-command-palette", overlay));
  });
  input.focus({ preventScroll: true });
  animateIn(q(".os-v3-command-palette", overlay), [
    { opacity: 0, transform: "translate3d(0,-18px,0) scale(.97)", filter: "blur(8px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "blur(0)" },
  ]);
}

function capsuleRouteLinks(entity) {
  const links = [
    ["/workspace/research", "Товар"],
    ["/workspace/media", "Материалы"],
    ["/workspace/generation", "Генерация"],
    ["/workspace/review", "Проверка"],
    ["/workspace/placement", "Публикации"],
    ["/workspace/stats", "Результаты"],
    ["/workspace/payouts", "Деньги"],
  ];
  return links.map(([route, label]) => `
    <a href="#${route}" class="${entity.route === route ? "is-active" : ""}"><span>${escapeMarkup(label)}</span></a>
  `).join("");
}

function capsuleCounts() {
  return {
    materials: qa(".media-card").length,
    generations: qa("[data-generation-job-id], .generation-batch-card").length,
    reviews: qa("[data-review-result-id], .content-review-history-item").length,
    placements: qa(".placement-card").length,
    tasks: qa(".task-card, .my-work-item[data-work-item-type='task']").length,
  };
}

function openCapsule(entity = currentEntity()) {
  if (runtime.capsuleOverlay) return;
  runtime.lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const counts = capsuleCounts();
  const recent = recentEntities().filter((item) => item.id !== entity.id).slice(0, 6);
  const overlay = elementFrom(`
    <div class="os-v3-capsule-backdrop">
      <section class="os-v3-capsule" role="dialog" aria-modal="true" aria-labelledby="os-v3-capsule-title">
        <header>
          <div><small>РАБОЧАЯ КАПСУЛА</small><strong id="os-v3-capsule-title">${escapeMarkup(entity.productName || entity.title)}</strong><span>${escapeMarkup(entity.sku || routeLabel(entity.route))}</span></div>
          <button type="button" data-os-v3-capsule-close aria-label="Закрыть">${icon("close", 19)}</button>
        </header>
        <nav class="os-v3-capsule-routes" aria-label="Маршрут объекта">${capsuleRouteLinks(entity)}</nav>
        <div class="os-v3-capsule-body">
          <section class="os-v3-capsule-now">
            <small>СЕЙЧАС</small>
            <h2>${escapeMarkup(entity.title)}</h2>
            <p>Открыто пространство «${escapeMarkup(routeLabel(entity.route))}». Капсула удерживает маршрут объекта, пока вы переключаетесь между этапами производства.</p>
            <div class="os-v3-capsule-facts">
              <span><small>Материалы</small><strong>${counts.materials}</strong></span>
              <span><small>Генерации</small><strong>${counts.generations}</strong></span>
              <span><small>Проверки</small><strong>${counts.reviews}</strong></span>
              <span><small>Публикации</small><strong>${counts.placements}</strong></span>
            </div>
            <div class="os-v3-capsule-actions">
              <button type="button" data-os-v3-capsule-handoff>${icon("handoff", 17)}<span>Передать контекст</span></button>
              <button type="button" data-os-v3-capsule-split>${icon("split", 17)}<span>Split View</span></button>
            </div>
          </section>
          <aside class="os-v3-capsule-recent">
            <small>НЕДАВНИЕ ОБЪЕКТЫ</small>
            ${recent.length ? recent.map((item) => `
              <button type="button" data-os-v3-recent-route="${escapeMarkup(item.route)}" data-os-v3-recent-id="${escapeMarkup(item.id)}">
                <strong>${escapeMarkup(item.productName || item.title)}</strong><span>${escapeMarkup(item.sku || routeLabel(item.route))}</span>
              </button>
            `).join("") : '<p>Недавние объекты появятся после работы с товарами и задачами.</p>'}
          </aside>
        </div>
      </section>
    </div>`);
  runtime.capsuleOverlay = overlay;
  document.body.append(overlay);
  document.body.classList.add("os-v3-capsule-open");
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay || (event.target instanceof Element && event.target.closest("[data-os-v3-capsule-close]"))) closeOverlay("capsule");
    if (event.target instanceof Element && event.target.closest("[data-os-v3-capsule-handoff]")) {
      closeOverlay("capsule", { restoreFocus: false });
      window.setTimeout(() => openHandoff(entity), 70);
    }
    if (event.target instanceof Element && event.target.closest("[data-os-v3-capsule-split]")) {
      closeOverlay("capsule", { restoreFocus: false });
      window.setTimeout(toggleSplitView, 70);
    }
    const recentButton = event.target instanceof Element ? event.target.closest("[data-os-v3-recent-route]") : null;
    if (recentButton) {
      closeOverlay("capsule", { restoreFocus: false });
      navigate(recentButton.dataset.osV3RecentRoute);
    }
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeOverlay("capsule");
    } else trapDialog(event, q(".os-v3-capsule", overlay));
  });
  q("[data-os-v3-capsule-close]", overlay)?.focus({ preventScroll: true });
  animateIn(q(".os-v3-capsule", overlay), [
    { opacity: 0, transform: "translate3d(0,24px,0) scale(.965)", filter: "blur(7px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "blur(0)" },
  ], { duration: 430 });
}

function splitCandidates() {
  const primary = qa(
    ".review-os-result-panel.is-active video, .review-os-result-panel.is-active img, "
      + ".content-review-decision-preview video, .content-review-decision-preview img, "
      + ".generation-os-panel.is-active video, .generation-os-panel.is-active img, "
      + ".academy-v2-panel.is-active video, .academy-v2-panel.is-active img, "
      + ".media-quicklook__stage video, .media-quicklook__stage img, .publishing-os-preview",
  ).find(visible);
  const secondary = qa(
    ".content-review-decision-form, .review-os-result-panel.is-active .content-review-findings, "
      + ".generation-os-panel.is-active .form-stack, .academy-v2-panel.is-active form, "
      + ".academy-v2-panel.is-active .training-practical-card, .placement-card.is-selected .checklist, "
      + ".placement-card.is-selected form",
  ).find((item) => visible(item) && item !== primary && !item.contains(primary) && !primary?.contains(item));
  return { primary, secondary };
}

function moveIntoSplit(node, target) {
  if (!(node instanceof Element) || !(target instanceof Element)) return false;
  const placeholder = document.createComment("contentengine-os-v3-split-placeholder");
  node.before(placeholder);
  target.append(node);
  runtime.movedNodes.push({ node, placeholder });
  return true;
}

function restoreSplitNodes() {
  runtime.movedNodes.splice(0).reverse().forEach(({ node, placeholder }) => {
    if (placeholder?.parentNode && node) placeholder.before(node);
    placeholder?.remove?.();
  });
}

function splitContextMarkup(entity) {
  return `
    <div class="os-v3-split-fallback">
      <small>КОНТЕКСТ</small>
      <h2>${escapeMarkup(entity.title)}</h2>
      <p>${escapeMarkup(entity.sku ? `Точный товар: ${entity.sku}` : `Пространство: ${routeLabel(entity.route)}`)}</p>
      <ol>
        <li>Сверьте текущий объект и критерий готовности.</li>
        <li>Зафиксируйте блокер или решение до перехода дальше.</li>
        <li>Используйте «Передать контекст», если работу продолжит другой человек.</li>
      </ol>
      <button type="button" data-os-v3-split-handoff>${icon("handoff", 17)}<span>Передать контекст</span></button>
    </div>`;
}

function openSplitView() {
  if (runtime.splitOverlay) return;
  const entity = currentEntity();
  const { primary, secondary } = splitCandidates();
  runtime.lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const overlay = elementFrom(`
    <div class="os-v3-split-backdrop">
      <section class="os-v3-split" role="dialog" aria-modal="true" aria-labelledby="os-v3-split-title">
        <header>
          <div><small>SPLIT VIEW</small><strong id="os-v3-split-title">${escapeMarkup(entity.title)}</strong></div>
          <div class="os-v3-split-ratio" role="group" aria-label="Ширина основной панели">
            <button type="button" data-os-v3-split-ratio="58">58 / 42</button>
            <button type="button" data-os-v3-split-ratio="68">68 / 32</button>
            <button type="button" data-os-v3-split-ratio="50">50 / 50</button>
          </div>
          <button type="button" data-os-v3-split-close aria-label="Закрыть">${icon("close", 19)}</button>
        </header>
        <div class="os-v3-split-body">
          <section class="os-v3-split-primary" aria-label="Основной рабочий объект"></section>
          <div class="os-v3-split-divider" aria-hidden="true"></div>
          <aside class="os-v3-split-secondary" aria-label="Контекст"></aside>
        </div>
      </section>
    </div>`);
  runtime.splitOverlay = overlay;
  document.body.append(overlay);
  document.body.classList.add("os-v3-split-open");
  const primaryTarget = q(".os-v3-split-primary", overlay);
  const secondaryTarget = q(".os-v3-split-secondary", overlay);
  const primaryMoved = moveIntoSplit(primary, primaryTarget);
  const secondaryMoved = moveIntoSplit(secondary, secondaryTarget);
  if (!primaryMoved) primaryTarget.innerHTML = splitContextMarkup(entity);
  if (!secondaryMoved) secondaryTarget.innerHTML = splitContextMarkup(entity);
  const ratio = Math.max(45, Math.min(75, Number(runtime.memory.splitRatio) || 64));
  overlay.style.setProperty("--os-v3-split-primary", `${ratio}%`);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay || (event.target instanceof Element && event.target.closest("[data-os-v3-split-close]"))) closeSplitView();
    const ratioButton = event.target instanceof Element ? event.target.closest("[data-os-v3-split-ratio]") : null;
    if (ratioButton) {
      const next = Math.max(45, Math.min(75, Number(ratioButton.dataset.osV3SplitRatio) || 64));
      overlay.style.setProperty("--os-v3-split-primary", `${next}%`);
      remember({ splitRatio: next });
    }
    if (event.target instanceof Element && event.target.closest("[data-os-v3-split-handoff]")) openHandoff(entity);
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeSplitView();
    } else trapDialog(event, q(".os-v3-split", overlay));
  });
  q("[data-os-v3-split-close]", overlay)?.focus({ preventScroll: true });
  animateIn(q(".os-v3-split", overlay), [
    { opacity: 0, transform: "translate3d(0,18px,0) scale(.975)", filter: "blur(6px)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)", filter: "blur(0)" },
  ], { duration: 430 });
}

function closeSplitView() {
  const overlay = runtime.splitOverlay;
  if (!overlay) return;
  overlay.classList.add("is-closing");
  const finish = () => {
    restoreSplitNodes();
    overlay.remove();
    runtime.splitOverlay = null;
    document.body.classList.remove("os-v3-split-open");
    runtime.lastFocus?.focus?.({ preventScroll: true });
  };
  if (REDUCED_MOTION.matches) finish();
  else window.setTimeout(finish, 250);
}

function toggleSplitView() {
  if (runtime.splitOverlay) closeSplitView();
  else openSplitView();
}

function handoffKey(entity) {
  return `${HANDOFF_PREFIX}:${compact(entity?.id || entity?.route || "workspace", 140)}`;
}

function handoffText(entity, values) {
  const lines = [
    `Передача: ${entity.productName || entity.title}`,
    entity.sku ? `Товар: ${entity.sku}` : "",
    `Пространство: ${routeLabel(entity.route)}`,
    values.owner ? `Следующий: ${values.owner}` : "",
    values.done ? `Что сделано: ${values.done}` : "",
    values.left ? `Что осталось: ${values.left}` : "",
    values.blocker ? `Блокер: ${values.blocker}` : "",
    `Ссылка: ${window.location.href.split("#")[0]}#${entity.route}`,
  ];
  return lines.filter(Boolean).join("\n");
}

function nearestWorkTextarea() {
  return qa(
    ".content-review-decision-form textarea[name='reason'], .task-card.is-selected textarea, "
      + ".placement-card.is-selected textarea, .generation-os-panel.is-active textarea[name='brief'], "
      + "textarea[name='notes'], textarea[name='description']",
  ).find((field) => safeTextField(field) && visible(field));
}

function insertIntoWorkField(text) {
  const field = nearestWorkTextarea();
  if (!field) return false;
  const current = String(field.value || "").trim();
  field.value = current ? `${current}\n\n${text}` : text;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
  field.closest("form")?.setAttribute("data-dirty", "true");
  field.focus({ preventScroll: true });
  return true;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function openHandoff(entity = currentEntity()) {
  if (runtime.handoffOverlay) return;
  runtime.lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const saved = readJson(storage("local"), handoffKey(entity), {});
  const overlay = elementFrom(`
    <div class="os-v3-handoff-backdrop">
      <section class="os-v3-handoff" role="dialog" aria-modal="true" aria-labelledby="os-v3-handoff-title">
        <header><div><small>ПЕРЕДАЧА КОНТЕКСТА</small><strong id="os-v3-handoff-title">${escapeMarkup(entity.title)}</strong></div><button type="button" data-os-v3-handoff-close aria-label="Закрыть">${icon("close", 19)}</button></header>
        <form class="os-v3-handoff-form" novalidate>
          <label><span>Кому дальше</span><input name="owner" maxlength="120" value="${escapeMarkup(saved.owner || "")}" placeholder="Имя или роль" /></label>
          <label><span>Что уже сделано</span><textarea name="done" maxlength="1200" placeholder="Коротко и по фактам">${escapeMarkup(saved.done || "")}</textarea></label>
          <label><span>Что осталось</span><textarea name="left" maxlength="1200" placeholder="Следующее проверяемое действие">${escapeMarkup(saved.left || "")}</textarea></label>
          <label><span>Блокер</span><textarea name="blocker" maxlength="900" placeholder="Нет файла, ждём ответ, нужна правка…">${escapeMarkup(saved.blocker || "")}</textarea></label>
          <p class="os-v3-handoff-status" role="status" aria-live="polite">Черновик остаётся только в этом браузере, пока вы не вставите его в рабочую форму или не скопируете.</p>
          <footer>
            <button type="button" data-os-v3-handoff-save>Сохранить черновик</button>
            <button type="button" data-os-v3-handoff-insert>Вставить в рабочее поле</button>
            <button type="submit">Скопировать передачу</button>
          </footer>
        </form>
      </section>
    </div>`);
  runtime.handoffOverlay = overlay;
  document.body.append(overlay);
  document.body.classList.add("os-v3-handoff-open");
  const form = q("form", overlay);
  const values = () => Object.fromEntries(new FormData(form).entries());
  const status = q(".os-v3-handoff-status", overlay);
  const save = () => {
    writeJson(storage("local"), handoffKey(entity), values());
    status.textContent = "Черновик передачи сохранён в этом браузере.";
  };
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay || (event.target instanceof Element && event.target.closest("[data-os-v3-handoff-close]"))) closeOverlay("handoff");
    if (event.target instanceof Element && event.target.closest("[data-os-v3-handoff-save]")) save();
    if (event.target instanceof Element && event.target.closest("[data-os-v3-handoff-insert]")) {
      const text = handoffText(entity, values());
      save();
      if (insertIntoWorkField(text)) {
        status.textContent = "Передача вставлена в рабочее поле. Она сохранится сервером только после штатной отправки формы.";
        pushUndo("Передача добавлена в рабочее поле", () => {
          const field = nearestWorkTextarea();
          if (!field) return;
          field.value = String(field.value || "").replace(`\n\n${text}`, "").replace(text, "");
          field.dispatchEvent(new Event("input", { bubbles: true }));
        });
      } else status.textContent = "На этом экране нет подходящего рабочего поля. Скопируйте передачу.";
    }
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = handoffText(entity, values());
    save();
    const copied = await copyText(text);
    status.textContent = copied ? "Передача скопирована." : "Буфер обмена недоступен. Используйте вставку в рабочее поле.";
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeOverlay("handoff");
    } else trapDialog(event, q(".os-v3-handoff", overlay));
  });
  q("input", overlay)?.focus({ preventScroll: true });
  animateIn(q(".os-v3-handoff", overlay), [
    { opacity: 0, transform: "translate3d(22px,0,0) scale(.98)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
  ]);
}

function frameNoteKey() {
  const reviewId = String(
    q("[data-review-result-id]")?.dataset.reviewResultId
      || q("[data-content-review-id]")?.dataset.contentReviewId
      || q(".content-review-decision-form")?.dataset.reviewId
      || currentEntity().id,
  );
  return `${FRAME_NOTE_PREFIX}:${compact(reviewId, 140)}`;
}

function frameNotes() {
  const notes = readJson(storage("local"), frameNoteKey(), []);
  return Array.isArray(notes) ? notes.slice(0, 40) : [];
}

function renderFrameNoteList(root) {
  const list = q("[data-os-v3-frame-note-list]", root || document);
  if (!list) return;
  const notes = frameNotes();
  list.innerHTML = notes.length ? notes.map((item, index) => `
    <button type="button" data-os-v3-frame-note-index="${index}"><strong>${escapeMarkup(item.mark)}</strong><span>${escapeMarkup(item.text)}</span></button>
  `).join("") : "<p>Комментариев к кадрам пока нет.</p>";
}

function openFrameNote(media) {
  if (runtime.frameOverlay || !(media instanceof HTMLVideoElement || media instanceof HTMLImageElement)) return;
  runtime.lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const mark = media instanceof HTMLVideoElement
    ? `${Math.floor((media.currentTime || 0) / 60).toString().padStart(2, "0")}:${Math.floor((media.currentTime || 0) % 60).toString().padStart(2, "0")}`
    : "Кадр";
  const overlay = elementFrom(`
    <div class="os-v3-frame-backdrop">
      <section class="os-v3-frame" role="dialog" aria-modal="true" aria-labelledby="os-v3-frame-title">
        <header><div><small>КОММЕНТАРИЙ К КАДРУ</small><strong id="os-v3-frame-title">${escapeMarkup(mark)}</strong></div><button type="button" data-os-v3-frame-close aria-label="Закрыть">${icon("close", 18)}</button></header>
        <form>
          <label><span>Что нужно исправить или проверить</span><textarea name="note" required minlength="2" maxlength="700" autofocus></textarea></label>
          <p role="status" aria-live="polite">Комментарий попадёт в поле решения и сохранится вместе с ним после штатной отправки.</p>
          <footer><button type="button" data-os-v3-frame-copy>Скопировать</button><button type="submit">Добавить к решению</button></footer>
        </form>
      </section>
    </div>`);
  runtime.frameOverlay = overlay;
  document.body.append(overlay);
  document.body.classList.add("os-v3-frame-open");
  const form = q("form", overlay);
  const status = q("[role='status']", overlay);
  const build = () => `[${mark}] ${compact(new FormData(form).get("note"), 700)}`;
  overlay.addEventListener("click", async (event) => {
    if (event.target === overlay || (event.target instanceof Element && event.target.closest("[data-os-v3-frame-close]"))) closeOverlay("frame");
    if (event.target instanceof Element && event.target.closest("[data-os-v3-frame-copy]")) {
      status.textContent = await copyText(build()) ? "Комментарий скопирован." : "Буфер обмена недоступен.";
    }
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const text = compact(new FormData(form).get("note"), 700);
    const line = `[${mark}] ${text}`;
    const notes = frameNotes();
    writeJson(storage("local"), frameNoteKey(), [{ mark, text, at: Date.now() }, ...notes].slice(0, 40));
    if (insertIntoWorkField(line)) {
      closeOverlay("frame");
      renderFrameNoteList();
    } else status.textContent = "Поле решения пока недоступно. Скопируйте комментарий и вставьте его после появления формы.";
  });
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeOverlay("frame");
    } else trapDialog(event, q(".os-v3-frame", overlay));
  });
  q("textarea", overlay)?.focus({ preventScroll: true });
}

function mountFrameNotes() {
  if (routePath() !== "/workspace/review") return;
  const media = qa("[data-content-review-exact-media], .content-review-decision-preview video, .content-review-decision-preview img")
    .find((item) => item instanceof HTMLVideoElement || item instanceof HTMLImageElement);
  if (!media) return;
  const host = media.closest(".content-review-decision-preview, .content-review-decision-form, .review-os-result-panel") || media.parentElement;
  if (!host || q(".os-v3-frame-tools", host)) return;
  const tools = elementFrom(`
    <aside class="os-v3-frame-tools">
      <button type="button" data-os-v3-add-frame-note>${icon("note", 17)}<span>Комментарий к кадру</span></button>
      <div data-os-v3-frame-note-list></div>
    </aside>`);
  host.append(tools);
  tools.addEventListener("click", (event) => {
    if (event.target instanceof Element && event.target.closest("[data-os-v3-add-frame-note]")) openFrameNote(media);
    const noteButton = event.target instanceof Element ? event.target.closest("[data-os-v3-frame-note-index]") : null;
    if (noteButton && media instanceof HTMLVideoElement) {
      const note = frameNotes()[Number(noteButton.dataset.osV3FrameNoteIndex) || 0];
      const parts = String(note?.mark || "").split(":").map(Number);
      if (parts.length === 2 && parts.every(Number.isFinite)) media.currentTime = parts[0] * 60 + parts[1];
    }
  });
  renderFrameNoteList(tools);
}

function pushUndo(message, undo, timeout = 10000) {
  if (runtime.undoBar) runtime.undoBar.remove();
  if (runtime.undoTimer) window.clearTimeout(runtime.undoTimer);
  const bar = elementFrom(`
    <aside class="os-v3-undo" role="status" aria-live="polite">
      <span>${icon("undo", 17)}<strong>${escapeMarkup(message)}</strong></span>
      <button type="button">Отменить · ${Math.round(timeout / 1000)} сек.</button>
    </aside>`);
  runtime.undoBar = bar;
  document.body.append(bar);
  const close = () => {
    if (runtime.undoBar === bar) runtime.undoBar = null;
    bar.remove();
  };
  bar.addEventListener("click", () => {
    try { undo?.(); } finally { close(); }
  });
  runtime.undoTimer = window.setTimeout(close, timeout);
  animateIn(bar, [
    { opacity: 0, transform: "translate3d(0,18px,0) scale(.96)" },
    { opacity: 1, transform: "translate3d(0,0,0) scale(1)" },
  ], { duration: 300 });
}

function mountDockTools() {
  const glass = q(".ce-mac-dock__glass");
  if (!glass || q("[data-os-v3-dock-tools]", glass)) return;
  const tools = elementFrom(`
    <span class="os-v3-dock-tools" data-os-v3-dock-tools>
      <span class="ce-mac-dock__separator" aria-hidden="true"></span>
      <button class="ce-mac-dock__item os-v3-dock-tool" type="button" data-os-v3-action="spotlight" aria-label="Spotlight">
        <span class="ce-mac-dock__tooltip">Spotlight · ⌘K</span><span class="ce-mac-dock__icon">${icon("search", 22)}</span>
      </button>
      <button class="ce-mac-dock__item os-v3-dock-tool" type="button" data-os-v3-action="capsule" aria-label="Рабочая капсула">
        <span class="ce-mac-dock__tooltip">Рабочая капсула</span><span class="ce-mac-dock__icon">${icon("capsule", 22)}</span>
      </button>
      <button class="ce-mac-dock__item os-v3-dock-tool" type="button" data-os-v3-action="split" aria-label="Split View">
        <span class="ce-mac-dock__tooltip">Split View</span><span class="ce-mac-dock__icon">${icon("split", 22)}</span>
      </button>
    </span>`);
  glass.append(tools);
  tools.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-os-v3-action]") : null;
    if (!button) return;
    if (button.dataset.osV3Action === "spotlight") openSpotlight();
    if (button.dataset.osV3Action === "capsule") openCapsule();
    if (button.dataset.osV3Action === "split") toggleSplitView();
  });
}

function workSnapshot() {
  return runtime.workSnapshot || readJson(storage("session"), WORK_SNAPSHOT_KEY, null) || {
    now: 0,
    waiting: 0,
    next: 0,
    blockers: 0,
    drafts: qa(".workspace-draft-indicator, .workspace-overview-draft").length,
  };
}

function mountMissionSummary() {
  const overview = q(".workspace-overview, .workspace-overview__dialog, .workspace-overview-backdrop");
  if (!overview || q(".os-v3-mission-summary", overview)) return;
  const snapshot = workSnapshot();
  const summary = elementFrom(`
    <section class="os-v3-mission-summary" aria-label="Оперативное внимание">
      <div><small>ОПЕРАТИВНОЕ ВНИМАНИЕ</small><strong>ContentEngine Mission Control</strong></div>
      <div class="os-v3-mission-metrics">
        <button type="button" data-os-v3-mission-lane="now"><small>Сейчас</small><strong>${Number(snapshot.now || 0)}</strong></button>
        <button type="button" data-os-v3-mission-lane="waiting"><small>Жду</small><strong>${Number(snapshot.waiting || 0)}</strong></button>
        <button type="button" data-os-v3-mission-lane="next"><small>Дальше</small><strong>${Number(snapshot.next || 0)}</strong></button>
        <button type="button" data-os-v3-mission-lane="blocked"><small>Блокеры</small><strong>${Number(snapshot.blockers || 0)}</strong></button>
        <button type="button" data-os-v3-mission-lane="drafts"><small>Черновики</small><strong>${Number(snapshot.drafts || 0)}</strong></button>
      </div>
    </section>`);
  const dialog = q(".workspace-overview__dialog, .workspace-overview", overview) || overview;
  dialog.prepend(summary);
  summary.addEventListener("click", (event) => {
    const button = event.target instanceof Element ? event.target.closest("[data-os-v3-mission-lane]") : null;
    if (!button) return;
    writeJson(storage("session"), "contentengine.os-v3.work-intent", { lane: button.dataset.osV3MissionLane, at: Date.now() });
    q("[data-workspace-overview-close], .workspace-overview__close")?.click();
    navigate("/workspace/work");
  });
}

function setupPresence() {
  if (runtime.channel || typeof BroadcastChannel !== "function") return;
  runtime.channel = new BroadcastChannel(PRESENCE_CHANNEL);
  runtime.channel.addEventListener("message", (event) => {
    const message = event.data;
    if (!message || message.tabId === runtime.tabId || !message.tabId) return;
    if (message.type === "leave") runtime.peers.delete(message.tabId);
    else runtime.peers.set(message.tabId, { route: message.route, entity: message.entity, at: Number(message.at) || Date.now() });
    renderPresenceChip();
  });
  const send = (type = "presence") => {
    runtime.channel?.postMessage({
      type,
      tabId: runtime.tabId,
      route: routePath(),
      entity: currentEntity(),
      at: Date.now(),
    });
  };
  send();
  runtime.presenceTimer = window.setInterval(() => {
    const now = Date.now();
    [...runtime.peers.entries()].forEach(([id, peer]) => {
      if (now - peer.at > 35000) runtime.peers.delete(id);
    });
    send();
    renderPresenceChip();
  }, 12000);
  window.addEventListener("beforeunload", () => send("leave"));
}

function renderPresenceChip() {
  const topbar = q(".review-os-topbar, .generation-os-topbar, .media-finder-topbar, .academy-os-topbar, .academy-course-os-topbar, .publishing-os-topbar, .work-stage-topbar, .results-os-topbar, .payout-ledger-topbar, .tasks-desk-topbar");
  if (!topbar) return;
  let chip = q(".os-v3-presence-chip", topbar);
  const matching = [...runtime.peers.values()].filter((peer) => peer.route === routePath());
  if (!matching.length) {
    chip?.remove();
    return;
  }
  if (!chip) {
    chip = elementFrom('<span class="os-v3-presence-chip" title="Другие вкладки этого же браузера открыли то же пространство"><i></i><span></span></span>');
    topbar.append(chip);
  }
  q("span", chip).textContent = `Открыто в ${matching.length + 1} окнах`;
}

function handleGlobalKeydown(event) {
  if ((event.metaKey || event.ctrlKey) && !event.altKey && event.key.toLocaleLowerCase() === "k") {
    event.preventDefault();
    event.stopImmediatePropagation();
    if (runtime.commandOverlay) closeOverlay("command");
    else openSpotlight();
    return;
  }
  if (event.altKey && !event.metaKey && !event.ctrlKey && event.code === "Space") {
    event.preventDefault();
    if (!runtime.capsuleOverlay) openCapsule();
    return;
  }
  if (event.altKey && event.shiftKey && event.key.toLocaleLowerCase() === "s") {
    event.preventDefault();
    toggleSplitView();
    return;
  }
  if (event.key === "Escape") {
    if (runtime.commandOverlay) closeOverlay("command");
    else if (runtime.capsuleOverlay) closeOverlay("capsule");
    else if (runtime.handoffOverlay) closeOverlay("handoff");
    else if (runtime.frameOverlay) closeOverlay("frame");
    else if (runtime.splitOverlay) closeSplitView();
  }
}

function scheduleMount() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

function mount() {
  document.documentElement.dataset.contentengineOs = "v3";
  document.body.classList.add("contentengine-os-v3");
  if (runtime.route !== routePath()) {
    runtime.route = routePath();
    if (runtime.splitOverlay) closeSplitView();
    runtime.channel?.postMessage({ type: "presence", tabId: runtime.tabId, route: runtime.route, entity: currentEntity(), at: Date.now() });
  }
  mountDockTools();
  mountMissionSummary();
  mountFrameNotes();
  renderPresenceChip();
}

window.addEventListener("contentengine:os-v3-work-snapshot", (event) => {
  runtime.workSnapshot = event.detail || null;
  writeJson(storage("session"), WORK_SNAPSHOT_KEY, runtime.workSnapshot);
  scheduleMount();
});

new MutationObserver(scheduleMount).observe(document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", scheduleMount);
document.addEventListener("keydown", handleGlobalKeydown, true);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", scheduleMount, { once: true });
else scheduleMount();
setupPresence();

window.ContentEngineOSV3 = Object.freeze({
  build: BUILD_ID,
  openSpotlight,
  openCapsule,
  toggleSplitView,
  openHandoff,
  pushUndo,
  currentEntity,
  scheduleMount,
});
