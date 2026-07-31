import { CreatorApi } from "./supabase-api.js?v=20260729.2";

/*
 * ContentEngine Desktop v4 · Context menus and Trash.
 *
 * Business mutations remain narrow server RPCs. The UI never deletes an item
 * directly: first it moves the record to reversible Trash, then a separately
 * confirmed purge keeps the audit tombstone and requests private Storage
 * cleanup.
 */

const SUPABASE_SDK_URL = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm";
const FINDER_QUERY_KEY = "contentengine.desktop-v4.finder-query";
const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");
const FINE_POINTER = window.matchMedia("(hover: hover) and (pointer: fine)");
const SVG_NS = "http://www.w3.org/2000/svg";
const TRASH_PAGE_SIZE = 72;

const RPC = Object.freeze({
  browser: "creator_workspace_trash_browser",
  trash: "creator_trash_workspace_items",
  restore: "creator_restore_workspace_items",
  purge: "creator_purge_workspace_items",
  cleanupComplete: "creator_complete_workspace_storage_cleanup",
});

const ICONS = Object.freeze({
  trash: ["M4 7h16", "M9 3h6l1 4H8l1-4Z", "m6 10-1 7m5-7v7m5-7 1 7", "M6 7l1 14h10l1-14"],
  open: ["M5 4h6l2 2h6v14H5z", "M8 11h8M12 7v8"],
  eye: ["M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6S2.5 12 2.5 12Z", "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z"],
  copy: ["M8 8h11v11H8z", "M5 16H4V4h12v1"],
  folder: ["M3 6h7l2 2h9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z"],
  plus: ["M12 5v14M5 12h14"],
  rename: ["m4 20 4.5-1 10-10-3.5-3.5-10 10L4 20Z", "m13 5 3.5 3.5"],
  refresh: ["M20 7v5h-5", "M4 17v-5h5", "M6.1 8A7 7 0 0 1 19 10M17.9 16A7 7 0 0 1 5 14"],
  grid: ["M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"],
  list: ["M8 6h13M8 12h13M8 18h13", "M3 6h1M3 12h1M3 18h1"],
  upload: ["M12 3v12", "m7 8 5-5 5 5", "M5 13v6h14v-6"],
  restore: ["M4 8V3m0 0h5M4 3l4 4", "M5 14a7 7 0 1 0 2-7"],
  remove: ["M4 7h16", "M9 3h6l1 4H8l1-4Z", "M7 7l1 14h8l1-14"],
  info: ["M12 11v6", "M12 7h.01", "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z"],
  search: ["M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z", "m16 16 4 4"],
  close: ["m6 6 12 12M18 6 6 18"],
  warning: ["M12 3 2.5 20h19L12 3Z", "M12 9v5M12 18h.01"],
  check: ["m5 12 4 4L19 6"],
});

const runtime = {
  queued: false,
  apiPromise: null,
  api: null,
  menu: null,
  menuRestoreFocus: null,
  trashDock: null,
  trashWindow: null,
  trashBody: null,
  trashItems: [],
  trashSelected: new Set(),
  trashCursor: null,
  trashHasMore: false,
  trashSummary: { total: 0, media: 0, tasks: 0 },
  trashCapabilities: {},
  trashQuery: "",
  trashEntityType: "all",
  trashLoading: false,
  preview: null,
  confirm: null,
  longPressTimer: 0,
  longPressStart: null,
  summaryTimer: 0,
};

function q(selector, root = document) {
  return root?.querySelector?.(selector) || null;
}

function qa(selector, root = document) {
  return [...(root?.querySelectorAll?.(selector) || [])];
}

function create(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function svgIcon(name, size = 18) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  (ICONS[name] || ICONS.info).forEach((data) => {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", data);
    svg.append(path);
  });
  return svg;
}

function compact(value, limit = 140) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}…` : text;
}

function routePath() {
  const raw = String(window.location.hash || "").replace(/^#/, "");
  return (`/${raw.split("?")[0] || ""}`).replace(/\/{2,}/g, "/").replace(/\/$/, "") || "/";
}

function normalizeResponse(response) {
  return response?.data && typeof response.data === "object" && !Array.isArray(response.data)
    ? response.data
    : response || {};
}

function friendlyError(error) {
  const code = String(error?.serverCode || error?.code || "");
  const messages = {
    workspace_item_busy: "Файл ещё загружается. Дождитесь завершения и повторите действие.",
    workspace_item_access_denied: "Для этого объекта недостаточно прав.",
    workspace_item_purged: "Объект уже удалён окончательно.",
    workspace_trash_item_not_found: "Объект уже восстановлен или удалён.",
    workspace_empty_trash_access_denied: "Очищать всю корзину может владелец или администратор.",
    membership_required: "Для аккаунта ещё не назначена рабочая команда.",
    auth_session_required: "Сессия завершилась. Войдите снова.",
  };
  return messages[code] || compact(error?.message, 260) || "Действие не выполнено. Обновите рабочее место и повторите.";
}

async function getApi() {
  if (runtime.api) return runtime.api;
  if (!runtime.apiPromise) {
    runtime.apiPromise = (async () => {
      const config = Object.freeze({ ...(window.CONTENTENGINE_CONFIG || {}) });
      if (!config.SUPABASE_URL || !config.SUPABASE_PUBLISHABLE_KEY) {
        throw new Error("Supabase configuration is unavailable");
      }
      const { createClient } = await import(SUPABASE_SDK_URL);
      const supabase = createClient(
        config.SUPABASE_URL,
        config.SUPABASE_PUBLISHABLE_KEY,
        {
          auth: {
            persistSession: true,
            autoRefreshToken: true,
            detectSessionInUrl: false,
          },
        },
      );
      const { data, error } = await supabase.auth.getSession();
      if (error || !data?.session) {
        const sessionError = new Error("Сессия завершилась. Войдите снова.");
        sessionError.code = "auth_session_required";
        throw sessionError;
      }
      const api = new CreatorApi(supabase, config);
      const bootstrap = await api.bootstrap({ client_version: "desktop-v4-trash-v1" });
      api.commitBootstrapContext(bootstrap);
      runtime.api = api;
      return api;
    })().catch((error) => {
      runtime.apiPromise = null;
      throw error;
    });
  }
  return runtime.apiPromise;
}

async function readTrash({ append = false } = {}) {
  const api = await getApi();
  const payload = { page_size: TRASH_PAGE_SIZE };
  if (runtime.trashQuery) payload.search = runtime.trashQuery;
  if (runtime.trashEntityType !== "all") payload.entity_types = [runtime.trashEntityType];
  if (append && runtime.trashCursor) payload.cursor = runtime.trashCursor;
  return normalizeResponse(await api.call(RPC.browser, api.withOrganization(payload)));
}

async function mutateTrash(functionName, payload) {
  const api = await getApi();
  return normalizeResponse(await api.mutate(functionName, payload));
}

function entityDescriptor(node) {
  if (!(node instanceof Element)) return null;
  const finderCard = node.closest(".workspace-board__item[data-entity-type][data-entity-id]");
  if (finderCard) {
    return {
      type: String(finderCard.dataset.entityType || ""),
      id: String(finderCard.dataset.entityId || ""),
      title: compact(q(".workspace-board__item-copy strong", finderCard)?.textContent || "Объект"),
      node: finderCard,
      source: "finder",
    };
  }
  const taskCard = node.closest(".task-card[data-task-id], .tasks-desk-card[data-task-id]");
  if (taskCard) {
    return {
      type: "task",
      id: String(taskCard.dataset.taskId || ""),
      title: compact(q("h2, h3, strong", taskCard)?.textContent || "Задача"),
      node: taskCard,
      source: "tasks",
    };
  }
  return null;
}

function folderDescriptor(node) {
  if (!(node instanceof Element)) return null;
  const row = node.closest(".workspace-board__folder-row[data-folder-id]");
  const id = String(row?.dataset.folderId || "");
  if (!row || !id || id === "all" || id === "root") return null;
  return {
    id,
    name: compact(q(".workspace-board__folder-button span:nth-child(2)", row)?.textContent || "Папка"),
    row,
  };
}

function menuAction(label, iconName, run, options = {}) {
  return {
    label,
    iconName,
    run,
    danger: options.danger === true,
    disabled: options.disabled === true,
    shortcut: options.shortcut || "",
  };
}

function finderItemActions(entity) {
  const actions = [];
  actions.push(menuAction("Открыть", "open", () => {
    q('[data-action="open-workspace-item"]', entity.node)?.click();
  }, { shortcut: "↵" }));
  if (entity.type === "media") {
    actions.push(menuAction("Быстрый просмотр", "eye", () => {
      window.ContentEngineFinderV4?.openQuickLook?.(entity.node);
    }, { shortcut: "Space" }));
  }
  actions.push(menuAction("Переместить в папку…", "folder", () => {
    q('[data-action="open-workspace-item"]', entity.node)?.click();
    window.setTimeout(() => q(".workspace-board__move-panel button")?.focus({ preventScroll: true }), 80);
  }));
  actions.push({ separator: true });
  actions.push(menuAction("Скопировать название", "copy", () => copyText(entity.title, "Название скопировано")));
  actions.push(menuAction("Скопировать ID", "copy", () => copyText(entity.id, "ID скопирован")));
  actions.push({ separator: true });
  actions.push(menuAction("Переместить в Корзину", "trash", () => trashEntities([entity]), { danger: true, shortcut: "⌫" }));
  return actions;
}

function taskActions(entity) {
  return [
    menuAction("Открыть задачу", "open", () => focusTask(entity.node), { shortcut: "↵" }),
    menuAction("Показать в Finder", "folder", () => showEntityInFinder(entity.id)),
    { separator: true },
    menuAction("Скопировать название", "copy", () => copyText(entity.title, "Название скопировано")),
    menuAction("Скопировать ID", "copy", () => copyText(entity.id, "ID скопирован")),
    { separator: true },
    menuAction("Переместить в Корзину", "trash", () => trashEntities([entity]), { danger: true, shortcut: "⌫" }),
  ];
}

function folderActions(folder) {
  return [
    menuAction("Открыть папку", "folder", () => q(".workspace-board__folder-button", folder.row)?.click(), { shortcut: "↵" }),
    menuAction("Новая папка внутри", "plus", () => focusFolderEditor(folder, "create")),
    menuAction("Переименовать", "rename", () => focusFolderEditor(folder, "rename")),
    { separator: true },
    menuAction("Скопировать название", "copy", () => copyText(folder.name, "Название папки скопировано")),
    menuAction("Скопировать ID", "copy", () => copyText(folder.id, "ID папки скопирован")),
    { separator: true },
    menuAction("Архивировать пустую папку", "remove", () => archiveFolder(folder), { danger: true }),
  ];
}

function emptySurfaceActions(target) {
  const route = routePath();
  if (route === "/workspace/board") {
    return [
      menuAction("Новая папка", "plus", () => focusFolderEditor(null, "create")),
      menuAction("Добавить материал", "upload", () => { window.location.hash = "#/workspace/media"; }),
      { separator: true },
      menuAction("Сетка", "grid", () => q('[data-ce-v4-finder-view="grid"]')?.click()),
      menuAction("Список", "list", () => q('[data-ce-v4-finder-view="list"]')?.click()),
      { separator: true },
      menuAction("Обновить", "refresh", refreshCurrentWorkspace, { shortcut: "⌘R" }),
      menuAction("Открыть Корзину", "trash", openTrash),
    ];
  }
  if (route === "/workspace/tasks") {
    return [
      menuAction("Найти задачу", "search", () => q(".ce-v4-task-filter input")?.focus({ preventScroll: true })),
      menuAction("Обновить", "refresh", refreshCurrentWorkspace),
      { separator: true },
      menuAction("Открыть Корзину", "trash", openTrash),
    ];
  }
  return [
    menuAction("Рабочие столы", "grid", () => window.ContentEngineDesktopV4?.openMission?.()),
    menuAction("Spotlight", "search", () => window.ContentEngineDesktopV4?.openSpotlight?.(), { shortcut: "⌘K" }),
    { separator: true },
    menuAction("Открыть Корзину", "trash", openTrash),
    menuAction("Обновить", "refresh", refreshCurrentWorkspace),
  ];
}

function contextActions(target) {
  const entity = entityDescriptor(target);
  if (entity) return entity.source === "tasks" ? taskActions(entity) : finderItemActions(entity);
  const folder = folderDescriptor(target);
  if (folder) return folderActions(folder);
  return emptySurfaceActions(target);
}

function closeContextMenu({ restoreFocus = false } = {}) {
  const menu = runtime.menu;
  if (!menu) return;
  menu.remove();
  runtime.menu = null;
  document.body.classList.remove("ce-v4-context-open");
  if (restoreFocus && runtime.menuRestoreFocus instanceof HTMLElement) {
    runtime.menuRestoreFocus.focus({ preventScroll: true });
  }
  runtime.menuRestoreFocus = null;
}

function positionMenu(menu, x, y) {
  const margin = 8;
  const rect = menu.getBoundingClientRect();
  const left = Math.max(margin, Math.min(window.innerWidth - rect.width - margin, x));
  const top = Math.max(margin, Math.min(window.innerHeight - rect.height - margin, y));
  menu.style.left = `${left}px`;
  menu.style.top = `${top}px`;
}

function openContextMenu(target, x, y) {
  const actions = contextActions(target);
  if (!actions.length) return;
  closeContextMenu();
  const menu = create("div", "ce-v4-context-menu");
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "Действия");
  runtime.menuRestoreFocus = target instanceof HTMLElement ? target : null;

  actions.forEach((action) => {
    if (action.separator) {
      menu.append(create("div", "ce-v4-context-menu__separator"));
      return;
    }
    const button = create("button", `ce-v4-context-menu__item${action.danger ? " is-danger" : ""}`);
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.disabled = action.disabled;
    const mark = create("span", "ce-v4-context-menu__icon");
    mark.append(svgIcon(action.iconName, 17));
    button.append(mark, create("span", "ce-v4-context-menu__label", action.label));
    if (action.shortcut) button.append(create("kbd", "", action.shortcut));
    button.addEventListener("click", () => {
      closeContextMenu();
      Promise.resolve(action.run()).catch((error) => showToast(friendlyError(error), "error"));
    });
    menu.append(button);
  });

  document.body.append(menu);
  runtime.menu = menu;
  document.body.classList.add("ce-v4-context-open");
  positionMenu(menu, x, y);
  const first = q("button:not(:disabled)", menu);
  first?.focus({ preventScroll: true });
  if (!REDUCED_MOTION.matches && typeof menu.animate === "function") {
    menu.animate(
      [{ opacity: 0, transform: "translateY(-5px) scale(.97)" }, { opacity: 1, transform: "translateY(0) scale(1)" }],
      { duration: 150, easing: "cubic-bezier(.16,1,.3,1)" },
    );
  }
}

function contextTarget(target) {
  if (!(target instanceof Element)) return null;
  return target.closest(
    ".workspace-board__item, .workspace-board__folder-row, .workspace-board__grid, "
      + ".task-card, .tasks-desk-card, .tasks-desk-stage, .ce-v4-page, .ce-v4-trash-dock",
  );
}

function handleContextMenu(event) {
  const target = contextTarget(event.target);
  if (!target) return;
  event.preventDefault();
  if (target.classList.contains("ce-v4-trash-dock")) {
    openContextMenuForTrashDock(event.clientX, event.clientY);
    return;
  }
  openContextMenu(target, event.clientX, event.clientY);
}

function openContextMenuForTrashDock(x, y) {
  closeContextMenu();
  const actions = [
    menuAction("Открыть Корзину", "trash", openTrash),
    menuAction(
      "Очистить Корзину…",
      "remove",
      () => confirmEmptyTrash(),
      { danger: true, disabled: !runtime.trashSummary.total || !runtime.trashCapabilities.empty_trash },
    ),
  ];
  const anchor = runtime.trashDock || document.body;
  const fake = create("span");
  fake.dataset.ceV4TrashMenu = "true";
  anchor.append(fake);
  const originalResolver = contextActions;
  void originalResolver;
  closeContextMenu();
  const menu = create("div", "ce-v4-context-menu");
  menu.setAttribute("role", "menu");
  actions.forEach((action) => {
    const button = create("button", `ce-v4-context-menu__item${action.danger ? " is-danger" : ""}`);
    button.type = "button";
    button.disabled = action.disabled;
    button.setAttribute("role", "menuitem");
    const mark = create("span", "ce-v4-context-menu__icon");
    mark.append(svgIcon(action.iconName, 17));
    button.append(mark, create("span", "ce-v4-context-menu__label", action.label));
    button.addEventListener("click", () => {
      closeContextMenu();
      Promise.resolve(action.run()).catch((error) => showToast(friendlyError(error), "error"));
    });
    menu.append(button);
  });
  fake.remove();
  document.body.append(menu);
  runtime.menu = menu;
  document.body.classList.add("ce-v4-context-open");
  positionMenu(menu, x, y);
  q("button:not(:disabled)", menu)?.focus({ preventScroll: true });
}

function handleMenuKeyboard(event) {
  if (!runtime.menu) return;
  const buttons = qa("button:not(:disabled)", runtime.menu);
  const current = buttons.indexOf(document.activeElement);
  if (event.key === "Escape") {
    event.preventDefault();
    closeContextMenu({ restoreFocus: true });
  }
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const delta = event.key === "ArrowDown" ? 1 : -1;
    buttons[(Math.max(0, current) + delta + buttons.length) % buttons.length]?.focus({ preventScroll: true });
  }
  if (event.key === "Home") {
    event.preventDefault();
    buttons[0]?.focus({ preventScroll: true });
  }
  if (event.key === "End") {
    event.preventDefault();
    buttons.at(-1)?.focus({ preventScroll: true });
  }
}

function focusTask(card) {
  if (!(card instanceof Element)) return;
  const id = String(card.dataset.taskId || "");
  q(`.tasks-desk-list-item[data-tasks-desk-id="${CSS.escape(id)}"]`)?.click();
  q("button, a, input, textarea, select", card)?.focus({ preventScroll: true });
}

function showEntityInFinder(value) {
  try { window.sessionStorage.setItem(FINDER_QUERY_KEY, String(value || "")); }
  catch { /* optional */ }
  window.location.hash = "#/workspace/board";
}

function focusFolderEditor(folder, mode) {
  if (folder?.row) q(".workspace-board__folder-button", folder.row)?.click();
  window.setTimeout(() => {
    const selector = mode === "rename" ? "#workspace-folder-edit-name" : "#workspace-folder-name";
    const input = q(selector);
    input?.focus({ preventScroll: true });
    input?.select?.();
  }, 80);
}

function archiveFolder(folder) {
  q(".workspace-board__folder-button", folder.row)?.click();
  window.setTimeout(() => {
    const archive = q(`[data-action="archive-workspace-folder"][data-folder-id="${CSS.escape(folder.id)}"]`);
    archive?.click();
  }, 80);
}

async function copyText(value, successMessage) {
  const text = String(value || "");
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const textarea = create("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  showToast(successMessage || "Скопировано", "success");
}

function refreshCurrentWorkspace() {
  closeContextMenu();
  if (routePath() === "/workspace/board") {
    const form = q("#workspace-board-filter-form");
    if (form) {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
      return;
    }
  }
  window.location.reload();
}

function removeEntityFromCurrentSurface(entity) {
  if (entity.source === "finder") {
    const form = q("#workspace-board-filter-form");
    form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    return;
  }
  const card = entity.node;
  const id = String(card?.dataset.taskId || "");
  const listItem = q(`.tasks-desk-list-item[data-tasks-desk-id="${CSS.escape(id)}"]`);
  const next = listItem?.nextElementSibling || listItem?.previousElementSibling;
  card?.remove();
  listItem?.remove();
  if (next instanceof HTMLElement) next.click();
  const count = q("[data-tasks-desk-count]");
  if (count) count.textContent = `${qa(".tasks-desk-list-item").length} задач`;
}

async function trashEntities(entities) {
  const normalized = entities
    .filter((entity) => entity?.id && ["media", "task"].includes(entity.type))
    .map((entity) => ({ type: entity.type, id: entity.id }));
  if (!normalized.length) return;
  await mutateTrash(RPC.trash, { items: normalized });
  entities.forEach(removeEntityFromCurrentSurface);
  await refreshTrashSummary();
  const label = entities.length === 1 ? entities[0].title : `${entities.length} объектов`;
  showUndoToast(`${label} перемещено в Корзину`, async () => {
    await mutateTrash(RPC.restore, { items: normalized });
    await refreshTrashSummary();
    if (routePath() === "/workspace/board") {
      q("#workspace-board-filter-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    }
    showToast("Объект восстановлен", "success");
  });
}

function showToast(message, tone = "info", action = null) {
  const region = q("#toast-region") || document.body;
  const toast = create("div", `ce-v4-system-toast is-${tone}`);
  toast.setAttribute("role", tone === "error" ? "alert" : "status");
  toast.append(create("span", "", message));
  if (action) {
    const button = create("button", "", action.label);
    button.type = "button";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try { await action.run(); toast.remove(); }
      catch (error) { button.disabled = false; showToast(friendlyError(error), "error"); }
    });
    toast.append(button);
  }
  region.append(toast);
  window.setTimeout(() => toast.remove(), action ? 8000 : 4200);
}

function showUndoToast(message, undo) {
  showToast(message, "success", { label: "Вернуть", run: undo });
}

function ensureTrashDock() {
  const glass = q(".ce-v4-dock__glass");
  if (!glass) return null;
  if (runtime.trashDock?.isConnected) return runtime.trashDock;
  let button = q(".ce-v4-trash-dock", glass);
  if (!button) {
    const separator = create("span", "ce-v4-dock__separator ce-v4-trash-separator");
    button = create("button", "ce-v4-dock__item ce-v4-dock__utility ce-v4-trash-dock");
    button.type = "button";
    button.setAttribute("aria-label", "Корзина");
    const tooltip = create("span", "ce-v4-dock__tooltip", "Корзина");
    const tile = create("span", "ce-v4-dock__tile");
    tile.append(svgIcon("trash", 22));
    button.append(tooltip, tile, create("i"));
    glass.append(separator, button);
    button.addEventListener("click", openTrash);
  }
  runtime.trashDock = button;
  updateTrashDock();
  return button;
}

function updateTrashDock() {
  const button = ensureTrashDock();
  if (!button) return;
  let badge = q(".ce-v4-trash-dock__badge", button);
  const count = Math.max(0, Number(runtime.trashSummary.total) || 0);
  if (!count) {
    badge?.remove();
    button.classList.remove("has-items");
    button.setAttribute("aria-label", "Корзина пуста");
    return;
  }
  if (!badge) {
    badge = create("b", "ce-v4-trash-dock__badge");
    q(".ce-v4-dock__tile", button)?.append(badge);
  }
  badge.textContent = count > 99 ? "99+" : String(count);
  button.classList.add("has-items");
  button.setAttribute("aria-label", `Корзина: ${count} объектов`);
}

async function refreshTrashSummary() {
  if (!q(".workspace-shell, .ce-v4-menubar")) return;
  try {
    const api = await getApi();
    const data = normalizeResponse(await api.call(
      RPC.browser,
      api.withOrganization({ page_size: 1 }),
    ));
    runtime.trashSummary = data.summary || { total: 0, media: 0, tasks: 0 };
    runtime.trashCapabilities = data.capabilities || {};
    updateTrashDock();
    syncTrashWindowHeader();
  } catch {
    // Auth/bootstrap can still be settling. The next route or visibility event retries.
  }
}

function syncTrashWindowHeader() {
  if (!runtime.trashWindow) return;
  const count = q("[data-ce-v4-trash-total]", runtime.trashWindow);
  if (count) count.textContent = `${runtime.trashSummary.total || 0}`;
  const empty = q("[data-ce-v4-trash-empty]", runtime.trashWindow);
  if (empty) {
    empty.disabled = !runtime.trashSummary.total || !runtime.trashCapabilities.empty_trash || runtime.trashLoading;
  }
}

function createTrashWindow() {
  const backdrop = create("div", "ce-v4-trash-backdrop");
  const dialog = create("section", "ce-v4-trash-window");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", "Корзина ContentEngine");

  const header = create("header", "ce-v4-trash-window__header");
  const titleGroup = create("div", "ce-v4-trash-window__title");
  const mark = create("span", "ce-v4-trash-window__mark");
  mark.append(svgIcon("trash", 21));
  const copy = create("span");
  const title = create("strong", "", "Корзина");
  const subtitle = create("small");
  subtitle.append(create("b", "", "0"), document.createTextNode(" объектов · удаление сначала обратимо"));
  q("b", subtitle).dataset.ceV4TrashTotal = "true";
  copy.append(title, subtitle);
  titleGroup.append(mark, copy);

  const headerActions = create("div", "ce-v4-trash-window__header-actions");
  const emptyButton = create("button", "ce-v4-trash-empty", "Очистить Корзину…");
  emptyButton.type = "button";
  emptyButton.dataset.ceV4TrashEmpty = "true";
  const close = create("button", "ce-v4-trash-close");
  close.type = "button";
  close.setAttribute("aria-label", "Закрыть Корзину");
  close.append(svgIcon("close", 18));
  headerActions.append(emptyButton, close);
  header.append(titleGroup, headerActions);

  const toolbar = create("form", "ce-v4-trash-toolbar");
  toolbar.setAttribute("role", "search");
  const searchLabel = create("label", "ce-v4-trash-search");
  searchLabel.append(svgIcon("search", 17));
  const search = create("input");
  search.type = "search";
  search.placeholder = "Файл, задача, артикул или ID";
  search.setAttribute("aria-label", "Поиск в Корзине");
  searchLabel.append(search);
  const type = create("select", "ce-v4-trash-type");
  type.setAttribute("aria-label", "Тип объектов в Корзине");
  [["all", "Все"], ["media", "Файлы"], ["task", "Задачи"]].forEach(([value, label]) => {
    const option = create("option", "", label);
    option.value = value;
    type.append(option);
  });
  const restore = create("button", "ce-v4-trash-toolbar__action", "Восстановить");
  restore.type = "button";
  restore.dataset.ceV4TrashRestore = "true";
  const purge = create("button", "ce-v4-trash-toolbar__action is-danger", "Удалить окончательно…");
  purge.type = "button";
  purge.dataset.ceV4TrashPurge = "true";
  toolbar.append(searchLabel, type, restore, purge);

  const body = create("div", "ce-v4-trash-window__body");
  body.dataset.ceV4TrashBody = "true";
  const loading = create("div", "ce-v4-trash-loading");
  loading.append(create("span"), create("p", "", "Открываем Корзину…"));
  body.append(loading);

  const footer = create("footer", "ce-v4-trash-window__footer");
  footer.append(
    create("span", "", "Delete — в Корзину · Space — просмотр · Shift+Delete — окончательно только внутри Корзины"),
  );
  const more = create("button", "", "Показать ещё");
  more.type = "button";
  more.dataset.ceV4TrashMore = "true";
  more.hidden = true;
  footer.append(more);

  dialog.append(header, toolbar, body, footer);
  backdrop.append(dialog);

  close.addEventListener("click", closeTrash);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeTrash(); });
  emptyButton.addEventListener("click", confirmEmptyTrash);
  restore.addEventListener("click", restoreSelectedTrash);
  purge.addEventListener("click", purgeSelectedTrash);
  more.addEventListener("click", () => loadTrash({ append: true }));
  toolbar.addEventListener("submit", (event) => event.preventDefault());
  let searchTimer = 0;
  search.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      runtime.trashQuery = search.value.trim();
      void loadTrash();
    }, 220);
  });
  type.addEventListener("change", () => {
    runtime.trashEntityType = type.value;
    void loadTrash();
  });
  body.addEventListener("click", handleTrashBodyClick);
  body.addEventListener("dblclick", handleTrashBodyDoubleClick);
  body.addEventListener("contextmenu", handleTrashBodyContextMenu);

  return { backdrop, dialog, body, search };
}

async function openTrash() {
  closeContextMenu();
  if (runtime.trashWindow) return;
  const parts = createTrashWindow();
  document.body.append(parts.backdrop);
  runtime.trashWindow = parts.backdrop;
  runtime.trashBody = parts.body;
  document.body.classList.add("ce-v4-trash-open");
  syncTrashWindowHeader();
  parts.search.focus({ preventScroll: true });
  if (!REDUCED_MOTION.matches && typeof parts.dialog.animate === "function") {
    parts.dialog.animate(
      [{ opacity: 0, transform: "translateY(14px) scale(.975)" }, { opacity: 1, transform: "translateY(0) scale(1)" }],
      { duration: 360, easing: "cubic-bezier(.16,1,.3,1)" },
    );
  }
  await loadTrash();
}

function closeTrash() {
  closeContextMenu();
  closePreview();
  const windowNode = runtime.trashWindow;
  if (!windowNode) return;
  windowNode.remove();
  runtime.trashWindow = null;
  runtime.trashBody = null;
  runtime.trashItems = [];
  runtime.trashSelected.clear();
  runtime.trashCursor = null;
  document.body.classList.remove("ce-v4-trash-open");
  runtime.trashDock?.focus({ preventScroll: true });
}

async function loadTrash({ append = false } = {}) {
  if (!runtime.trashBody || runtime.trashLoading) return;
  runtime.trashLoading = true;
  updateTrashToolbar();
  if (!append) {
    runtime.trashItems = [];
    runtime.trashSelected.clear();
    runtime.trashCursor = null;
    runtime.trashHasMore = false;
    runtime.trashBody.replaceChildren(createTrashLoading());
  }
  try {
    const data = await readTrash({ append });
    const incoming = Array.isArray(data.items) ? data.items : [];
    runtime.trashItems = append ? [...runtime.trashItems, ...incoming] : incoming;
    runtime.trashCursor = data?._meta?.next_cursor || null;
    runtime.trashHasMore = data?._meta?.has_more === true;
    runtime.trashSummary = data.summary || runtime.trashSummary;
    runtime.trashCapabilities = data.capabilities || runtime.trashCapabilities;
    renderTrashItems();
    void hydrateTrashPreviews();
  } catch (error) {
    renderTrashError(friendlyError(error));
  } finally {
    runtime.trashLoading = false;
    updateTrashToolbar();
    updateTrashDock();
    syncTrashWindowHeader();
  }
}

function createTrashLoading() {
  const loading = create("div", "ce-v4-trash-loading");
  loading.append(create("span"), create("p", "", "Открываем Корзину…"));
  return loading;
}

function renderTrashError(message) {
  if (!runtime.trashBody) return;
  const error = create("section", "ce-v4-trash-error");
  error.append(svgIcon("warning", 34), create("h2", "", "Корзина не открылась"), create("p", "", message));
  const retry = create("button", "", "Повторить");
  retry.type = "button";
  retry.addEventListener("click", () => loadTrash());
  error.append(retry);
  runtime.trashBody.replaceChildren(error);
}

function trashItemCard(item) {
  const id = String(item.id || "");
  const type = String(item.type || "");
  const key = `${type}:${id}`;
  const selected = runtime.trashSelected.has(key);
  const card = create("article", `ce-v4-trash-item${selected ? " is-selected" : ""}`);
  card.dataset.trashKey = key;
  card.dataset.entityType = type;
  card.dataset.entityId = id;
  card.tabIndex = 0;

  const select = create("button", "ce-v4-trash-item__select");
  select.type = "button";
  select.dataset.trashSelect = key;
  select.setAttribute("aria-label", selected ? "Снять выбор" : "Выбрать объект");
  select.setAttribute("aria-pressed", String(selected));
  if (selected) select.append(svgIcon("check", 15));

  const preview = create("div", "ce-v4-trash-item__preview");
  preview.dataset.trashPreview = key;
  preview.append(svgIcon(type === "media" ? "eye" : "open", 27));

  const copy = create("div", "ce-v4-trash-item__copy");
  const typeLabel = type === "media" ? "ФАЙЛ" : "ЗАДАЧА";
  copy.append(
    create("small", "", typeLabel),
    create("strong", "", compact(item.title || `${typeLabel} ${id}`, 120)),
    create("span", "", compact(item.original_folder_name || "Без папки", 80)),
  );
  const meta = create("div", "ce-v4-trash-item__meta");
  meta.append(
    create("span", "", formatDate(item.trashed_at)),
    create("span", "", humanStatus(item.original_status)),
  );
  card.append(select, preview, copy, meta);
  return card;
}

function renderTrashItems() {
  if (!runtime.trashBody) return;
  if (!runtime.trashItems.length) {
    const empty = create("section", "ce-v4-trash-empty-state");
    const mark = create("span");
    mark.append(svgIcon("trash", 38));
    empty.append(mark, create("h2", "", "Корзина пуста"), create("p", "", "Файлы и задачи сначала попадают сюда. Их можно восстановить до окончательной очистки."));
    runtime.trashBody.replaceChildren(empty);
  } else {
    const grid = create("div", "ce-v4-trash-grid");
    runtime.trashItems.forEach((item) => grid.append(trashItemCard(item)));
    runtime.trashBody.replaceChildren(grid);
  }
  const more = q("[data-ce-v4-trash-more]", runtime.trashWindow);
  if (more) more.hidden = !runtime.trashHasMore;
  updateTrashToolbar();
}

function trashKey(item) {
  return `${item.type}:${item.id}`;
}

function selectedTrashItems() {
  return runtime.trashItems.filter((item) => runtime.trashSelected.has(trashKey(item)));
}

function updateTrashToolbar() {
  if (!runtime.trashWindow) return;
  const selected = selectedTrashItems();
  const restore = q("[data-ce-v4-trash-restore]", runtime.trashWindow);
  const purge = q("[data-ce-v4-trash-purge]", runtime.trashWindow);
  if (restore) {
    restore.disabled = !selected.length || runtime.trashLoading;
    restore.textContent = selected.length ? `Восстановить · ${selected.length}` : "Восстановить";
  }
  if (purge) {
    purge.disabled = !selected.length || !runtime.trashCapabilities.purge_items || runtime.trashLoading;
    purge.textContent = selected.length ? `Удалить окончательно · ${selected.length}` : "Удалить окончательно…";
  }
  syncTrashWindowHeader();
}

function handleTrashBodyClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  const selector = target?.closest("[data-trash-select]");
  const card = target?.closest(".ce-v4-trash-item[data-trash-key]");
  if (!selector && !card) return;
  const key = String(selector?.dataset.trashSelect || card?.dataset.trashKey || "");
  if (!key) return;
  if (runtime.trashSelected.has(key)) runtime.trashSelected.delete(key);
  else runtime.trashSelected.add(key);
  renderTrashItems();
  q(`.ce-v4-trash-item[data-trash-key="${CSS.escape(key)}"]`, runtime.trashBody)?.focus({ preventScroll: true });
}

function handleTrashBodyDoubleClick(event) {
  const card = event.target instanceof Element ? event.target.closest(".ce-v4-trash-item[data-trash-key]") : null;
  const item = runtime.trashItems.find((candidate) => trashKey(candidate) === card?.dataset.trashKey);
  if (item) void openTrashPreview(item);
}

function handleTrashBodyContextMenu(event) {
  const card = event.target instanceof Element ? event.target.closest(".ce-v4-trash-item[data-trash-key]") : null;
  if (!card) return;
  event.preventDefault();
  const item = runtime.trashItems.find((candidate) => trashKey(candidate) === card.dataset.trashKey);
  if (!item) return;
  closeContextMenu();
  const actions = [
    menuAction("Быстрый просмотр", "eye", () => openTrashPreview(item), { shortcut: "Space" }),
    menuAction("Восстановить", "restore", () => restoreTrashItems([item])),
    menuAction("Скопировать ID", "copy", () => copyText(item.id, "ID скопирован")),
    { separator: true },
    menuAction("Удалить окончательно…", "remove", () => confirmPurge([item]), { danger: true, disabled: !runtime.trashCapabilities.purge_items }),
  ];
  const menu = create("div", "ce-v4-context-menu");
  menu.setAttribute("role", "menu");
  actions.forEach((action) => {
    if (action.separator) {
      menu.append(create("div", "ce-v4-context-menu__separator"));
      return;
    }
    const button = create("button", `ce-v4-context-menu__item${action.danger ? " is-danger" : ""}`);
    button.type = "button";
    button.disabled = action.disabled;
    button.setAttribute("role", "menuitem");
    const mark = create("span", "ce-v4-context-menu__icon");
    mark.append(svgIcon(action.iconName, 17));
    button.append(mark, create("span", "ce-v4-context-menu__label", action.label));
    if (action.shortcut) button.append(create("kbd", "", action.shortcut));
    button.addEventListener("click", () => {
      closeContextMenu();
      Promise.resolve(action.run()).catch((error) => showToast(friendlyError(error), "error"));
    });
    menu.append(button);
  });
  document.body.append(menu);
  runtime.menu = menu;
  document.body.classList.add("ce-v4-context-open");
  positionMenu(menu, event.clientX, event.clientY);
  q("button:not(:disabled)", menu)?.focus({ preventScroll: true });
}

async function hydrateTrashPreviews() {
  const media = runtime.trashItems.filter((item) => item.type === "media" && item.object_name).slice(0, 36);
  if (!media.length || !runtime.trashBody) return;
  let api;
  try { api = await getApi(); }
  catch { return; }
  await Promise.all(media.map(async (item) => {
    const target = q(`[data-trash-preview="${CSS.escape(trashKey(item))}"]`, runtime.trashBody);
    if (!target || target.dataset.hydrated === "true") return;
    target.dataset.hydrated = "true";
    try {
      const { data, error } = await api.supabase.storage
        .from(item.bucket_id || "contentengine-private")
        .createSignedUrl(item.object_name, 600);
      if (error || !data?.signedUrl) return;
      if (String(item.mime_type || "").startsWith("image/")) {
        const image = create("img");
        image.src = data.signedUrl;
        image.alt = "";
        image.loading = "lazy";
        target.replaceChildren(image);
      }
    } catch {
      // A missing preview never blocks restore or purge.
    }
  }));
}

async function openTrashPreview(item) {
  closePreview();
  const backdrop = create("div", "ce-v4-trash-preview-backdrop");
  const dialog = create("section", "ce-v4-trash-preview");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", compact(item.title || "Объект Корзины"));
  const header = create("header");
  const copy = create("div");
  copy.append(create("small", "", "QUICK LOOK · КОРЗИНА"), create("strong", "", compact(item.title || item.id, 120)));
  const close = create("button");
  close.type = "button";
  close.setAttribute("aria-label", "Закрыть просмотр");
  close.append(svgIcon("close", 18));
  header.append(copy, close);
  const body = create("div", "ce-v4-trash-preview__body");
  const placeholder = create("div", "ce-v4-trash-preview__placeholder");
  placeholder.append(svgIcon(item.type === "media" ? "eye" : "open", 54));
  body.append(placeholder);
  const aside = create("aside");
  aside.append(
    fact("Тип", item.type === "media" ? "Файл" : "Задача"),
    fact("Была в папке", item.original_folder_name || "Без папки"),
    fact("Исходный статус", humanStatus(item.original_status)),
    fact("Удалено", formatDate(item.trashed_at)),
    fact("ID", item.id),
  );
  if (item.instructions) aside.append(create("p", "", compact(item.instructions, 600)));
  body.append(aside);
  dialog.append(header, body);
  backdrop.append(dialog);
  document.body.append(backdrop);
  runtime.preview = backdrop;
  close.addEventListener("click", closePreview);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closePreview(); });
  close.focus({ preventScroll: true });

  if (item.type === "media" && item.object_name) {
    try {
      const api = await getApi();
      const { data, error } = await api.supabase.storage
        .from(item.bucket_id || "contentengine-private")
        .createSignedUrl(item.object_name, 600);
      if (!error && data?.signedUrl && runtime.preview === backdrop) {
        let media;
        if (String(item.mime_type || "").startsWith("image/")) {
          media = create("img");
          media.alt = compact(item.title || "Файл");
        } else if (String(item.mime_type || "") === "video/mp4") {
          media = create("video");
          media.controls = true;
          media.preload = "metadata";
          media.playsInline = true;
        }
        if (media) {
          media.src = data.signedUrl;
          placeholder.replaceChildren(media);
        }
      }
    } catch {
      // Keep the metadata preview when signed media is unavailable.
    }
  }
}

function fact(label, value) {
  const row = create("dl");
  row.append(create("dt", "", label), create("dd", "", String(value || "—")));
  return row;
}

function closePreview() {
  q("video", runtime.preview)?.pause?.();
  runtime.preview?.remove();
  runtime.preview = null;
}

async function restoreSelectedTrash() {
  const items = selectedTrashItems();
  if (items.length) await restoreTrashItems(items);
}

async function restoreTrashItems(items) {
  runtime.trashLoading = true;
  updateTrashToolbar();
  try {
    await mutateTrash(RPC.restore, {
      items: items.map((item) => ({ type: item.type, id: item.id })),
    });
    showToast(items.length === 1 ? "Объект восстановлен" : `Восстановлено: ${items.length}`, "success");
    await refreshTrashSummary();
    await loadTrash();
    if (routePath() === "/workspace/board") {
      q("#workspace-board-filter-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    }
  } finally {
    runtime.trashLoading = false;
    updateTrashToolbar();
  }
}

async function purgeSelectedTrash() {
  const items = selectedTrashItems();
  if (items.length) confirmPurge(items);
}

function confirmPurge(items) {
  const count = items.length;
  openConfirm({
    title: count === 1 ? "Удалить объект окончательно?" : `Удалить окончательно: ${count}?`,
    description: "Восстановить эти файлы или задачи после удаления будет нельзя. Система сохранит только технический аудит операции.",
    actionLabel: "Удалить окончательно",
    danger: true,
    run: () => purgeTrashItems(items),
  });
}

function confirmEmptyTrash() {
  if (!runtime.trashSummary.total || !runtime.trashCapabilities.empty_trash) return;
  openConfirm({
    title: "Очистить всю Корзину?",
    description: `Будет окончательно удалено ${runtime.trashSummary.total} объектов. Для защиты введите ОЧИСТИТЬ.`,
    actionLabel: "Очистить Корзину",
    danger: true,
    phrase: "ОЧИСТИТЬ",
    run: emptyTrash,
  });
}

function openConfirm({ title, description, actionLabel, danger = false, phrase = "", run }) {
  closeConfirm();
  const backdrop = create("div", "ce-v4-confirm-backdrop");
  const dialog = create("section", "ce-v4-confirm");
  dialog.setAttribute("role", "alertdialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-label", title);
  const mark = create("span", `ce-v4-confirm__mark${danger ? " is-danger" : ""}`);
  mark.append(svgIcon(danger ? "warning" : "info", 25));
  dialog.append(mark, create("h2", "", title), create("p", "", description));
  let input = null;
  if (phrase) {
    input = create("input");
    input.type = "text";
    input.autocomplete = "off";
    input.placeholder = phrase;
    input.setAttribute("aria-label", `Введите ${phrase}`);
    dialog.append(input);
  }
  const actions = create("div", "ce-v4-confirm__actions");
  const cancel = create("button", "", "Отмена");
  cancel.type = "button";
  const action = create("button", danger ? "is-danger" : "", actionLabel);
  action.type = "button";
  action.disabled = Boolean(phrase);
  actions.append(cancel, action);
  dialog.append(actions);
  backdrop.append(dialog);
  document.body.append(backdrop);
  runtime.confirm = backdrop;
  cancel.addEventListener("click", closeConfirm);
  backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeConfirm(); });
  input?.addEventListener("input", () => { action.disabled = input.value.trim() !== phrase; });
  action.addEventListener("click", async () => {
    action.disabled = true;
    cancel.disabled = true;
    try {
      await run();
      closeConfirm();
    } catch (error) {
      action.disabled = false;
      cancel.disabled = false;
      showToast(friendlyError(error), "error");
    }
  });
  (input || cancel).focus({ preventScroll: true });
}

function closeConfirm() {
  runtime.confirm?.remove();
  runtime.confirm = null;
}

async function purgeTrashItems(items) {
  runtime.trashLoading = true;
  updateTrashToolbar();
  try {
    const response = await mutateTrash(RPC.purge, {
      items: items.map((item) => ({ type: item.type, id: item.id })),
    });
    const pending = await cleanupStorage(response.storage_cleanup || []);
    showToast(
      pending
        ? `Удалено: ${response.purged_count || items.length}. Очистка ${pending} файлов в хранилище будет повторена.`
        : `Удалено окончательно: ${response.purged_count || items.length}`,
      pending ? "warning" : "success",
    );
    await refreshTrashSummary();
    await loadTrash();
  } finally {
    runtime.trashLoading = false;
    updateTrashToolbar();
  }
}

async function emptyTrash() {
  runtime.trashLoading = true;
  updateTrashToolbar();
  let removed = 0;
  let pending = 0;
  let remaining = Math.max(0, Number(runtime.trashSummary.total) || 0);
  let passes = 0;
  try {
    while (remaining > 0 && passes < 20) {
      const response = await mutateTrash(RPC.purge, { all: true });
      removed += Number(response.purged_count) || 0;
      pending += await cleanupStorage(response.storage_cleanup || []);
      remaining = Math.max(0, Number(response.remaining_count) || 0);
      passes += 1;
      if (!response.purged_count) break;
    }
    showToast(
      pending
        ? `Корзина очищена: ${removed}. Очистка ${pending} файлов в хранилище будет повторена.`
        : `Корзина очищена: ${removed}`,
      pending ? "warning" : "success",
    );
    await refreshTrashSummary();
    await loadTrash();
  } finally {
    runtime.trashLoading = false;
    updateTrashToolbar();
  }
}

async function cleanupStorage(items) {
  const valid = items.filter((item) => item?.media_id && item?.object_name && item?.bucket_id);
  if (!valid.length) return 0;
  const api = await getApi();
  const groups = new Map();
  valid.forEach((item) => {
    if (!groups.has(item.bucket_id)) groups.set(item.bucket_id, []);
    groups.get(item.bucket_id).push(item);
  });
  const completed = [];
  let pending = 0;
  for (const [bucket, group] of groups) {
    try {
      const { error } = await api.supabase.storage.from(bucket).remove(group.map((item) => item.object_name));
      if (error) pending += group.length;
      else completed.push(...group.map((item) => item.media_id));
    } catch {
      pending += group.length;
    }
  }
  if (completed.length) {
    try {
      await mutateTrash(RPC.cleanupComplete, { media_ids: completed });
    } catch {
      // The object is already gone. A pending audit receipt can be reconciled later.
    }
  }
  return pending;
}

function humanStatus(value) {
  const labels = {
    ready: "Готово",
    archived: "Архив",
    failed: "Ошибка",
    todo: "Новая",
    in_progress: "В работе",
    submitted: "Отправлена",
    review: "Проверка",
    done: "Готово",
    blocked: "Блокер",
    cancelled: "Отменена",
  };
  return labels[String(value || "")] || compact(value || "Без статуса", 40);
}

function formatDate(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "Дата не указана";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function handleGlobalKeydown(event) {
  handleMenuKeyboard(event);
  if (event.key === "Escape") {
    if (runtime.confirm) { closeConfirm(); return; }
    if (runtime.preview) { closePreview(); return; }
    if (runtime.trashWindow) { closeTrash(); return; }
  }
  const editing = event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable='true']");
  if (editing) return;
  if (runtime.trashWindow && event.key === " ") {
    const card = document.activeElement instanceof Element ? document.activeElement.closest(".ce-v4-trash-item[data-trash-key]") : null;
    const item = runtime.trashItems.find((candidate) => trashKey(candidate) === card?.dataset.trashKey);
    if (item) { event.preventDefault(); void openTrashPreview(item); }
  }
  if (runtime.trashWindow && event.shiftKey && event.key === "Delete") {
    const items = selectedTrashItems();
    if (items.length && runtime.trashCapabilities.purge_items) {
      event.preventDefault();
      confirmPurge(items);
    }
    return;
  }
  if (!runtime.trashWindow && event.key === "Delete") {
    const entity = entityDescriptor(document.activeElement);
    if (entity) {
      event.preventDefault();
      void trashEntities([entity]);
    }
  }
}

function handlePointerDown(event) {
  if (FINE_POINTER.matches || event.pointerType === "mouse") return;
  const target = contextTarget(event.target);
  if (!target) return;
  runtime.longPressStart = { x: event.clientX, y: event.clientY, target };
  window.clearTimeout(runtime.longPressTimer);
  runtime.longPressTimer = window.setTimeout(() => {
    const start = runtime.longPressStart;
    if (start) openContextMenu(start.target, start.x, start.y);
    runtime.longPressStart = null;
  }, 560);
}

function cancelLongPress(event) {
  const start = runtime.longPressStart;
  if (start && event && Math.hypot(event.clientX - start.x, event.clientY - start.y) > 10) {
    runtime.longPressStart = null;
  }
  window.clearTimeout(runtime.longPressTimer);
}

function mount() {
  ensureTrashDock();
  updateTrashDock();
  if (!runtime.summaryTimer && q(".ce-v4-dock")) {
    runtime.summaryTimer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refreshTrashSummary();
    }, 90_000);
    void refreshTrashSummary();
  }
}

function schedule() {
  if (runtime.queued) return;
  runtime.queued = true;
  window.requestAnimationFrame(() => {
    runtime.queued = false;
    mount();
  });
}

document.addEventListener("contextmenu", handleContextMenu, true);
document.addEventListener("keydown", handleGlobalKeydown, true);
document.addEventListener("pointerdown", handlePointerDown, { passive: true });
document.addEventListener("pointermove", cancelLongPress, { passive: true });
document.addEventListener("pointerup", cancelLongPress, { passive: true });
document.addEventListener("pointercancel", cancelLongPress, { passive: true });
document.addEventListener("click", (event) => {
  if (runtime.menu && event.target instanceof Node && !runtime.menu.contains(event.target)) closeContextMenu();
}, true);
new MutationObserver(schedule).observe(document.querySelector("#app") || document.documentElement, { childList: true, subtree: true });
window.addEventListener("hashchange", schedule, { passive: true });
window.addEventListener("contentengine:v4-route-ready", schedule);
window.addEventListener("pageshow", schedule);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    schedule();
    void refreshTrashSummary();
  }
});
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
else schedule();

window.ContentEngineTrashV4 = Object.freeze({
  open: openTrash,
  close: closeTrash,
  refresh: refreshTrashSummary,
  trash: (items) => trashEntities(items),
});
