const RESERVED_FOLDER_IDS = new Set(["all", "root"]);
const ENTITY_TYPE_PATTERN = /^[a-z][a-z0-9_-]{0,39}$/;
const ID_MAX_LENGTH = 180;
const QUERY_MAX_LENGTH = 120;
const NORMALIZED_BOARDS = new WeakSet();

const ENTITY_LABELS = Object.freeze({
  media: "Материал",
  task: "Задача",
  generation: "Генерация",
  research: "Разбор товара",
  placement: "Публикация",
  publication: "Публикация",
  payout: "Выплата",
  feedback: "Запрос",
});

const ENTITY_ICONS = Object.freeze({
  media: "▧",
  task: "✓",
  generation: "✦",
  research: "⌕",
  placement: "↗",
  publication: "↗",
  payout: "₽",
  feedback: "+",
});

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function normalizedId(value) {
  return String(value ?? "").trim().slice(0, ID_MAX_LENGTH);
}

function normalizedEntityType(value, fallback = "media") {
  const normalized = String(value || fallback).trim().toLowerCase();
  return ENTITY_TYPE_PATTERN.test(normalized) ? normalized : fallback;
}

function normalizedFolderReference(value) {
  const normalized = normalizedId(value);
  return !normalized || RESERVED_FOLDER_IDS.has(normalized) ? null : normalized;
}

function normalizedStatus(value, fallback = "ready") {
  const normalized = String(value || fallback).trim().toLowerCase();
  return /^[a-z][a-z0-9_-]{0,39}$/.test(normalized) ? normalized : fallback;
}

function normalizedColorToken(value) {
  const normalized = String(value || "default").trim().toLowerCase();
  return /^[a-z][a-z0-9_-]{0,31}$/.test(normalized) ? normalized : "default";
}

function finiteNumber(...values) {
  for (const value of values) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function safeText(value, maximumLength = 500) {
  return String(value ?? "").trim().slice(0, maximumLength);
}

function itemSources(source) {
  if (Array.isArray(source)) return [{ items: source, fallbackType: "media" }];
  const record = asRecord(source);
  const definitions = [
    ["items", ""],
    ["workspace_items", ""],
    ["entities", ""],
    ["objects", ""],
    ["media", "media"],
    ["media_items", "media"],
    ["tasks", "task"],
    ["task_items", "task"],
    ["batches", "generation"],
    ["generation_batches", "generation"],
    ["research", "research"],
    ["research_runs", "research"],
    ["placements", "placement"],
    ["placement_items", "placement"],
    ["publications", "publication"],
    ["payouts", "payout"],
    ["feedback", "feedback"],
  ];
  return definitions
    .filter(([key]) => Array.isArray(record[key]))
    .map(([key, fallbackType]) => ({ items: record[key], fallbackType }));
}

function inferEntityType(item, fallbackType) {
  if (fallbackType) return fallbackType;
  if (item.task_type || item.instructions || item.assignee_id) return "task";
  if (item.mime_type || item.object_key || item.object_name) return "media";
  if (item.generation_job_id || item.total_requested || item.parameters) return "generation";
  if (item.final_url || item.platform) return "placement";
  return "media";
}

function normalizeFolder(folder, index, canManageFolders = false) {
  const source = asRecord(folder);
  const id = normalizedId(source.id ?? source.public_id ?? source.folder_id);
  if (!id || RESERVED_FOLDER_IDS.has(id)) return null;
  const name = safeText(source.name ?? source.title ?? source.label, 120) || `Папка ${index + 1}`;
  return {
    id,
    parentId: normalizedFolderReference(source.parent_id ?? source.parentId),
    name,
    status: normalizedStatus(source.status, "active"),
    version: Math.max(1, Math.trunc(finiteNumber(source.version, 1))),
    colorToken: normalizedColorToken(source.color_token ?? source.colorToken),
    itemCount: Math.max(
      0,
      Math.trunc(
        finiteNumber(
          source.item_count,
          source.items_count,
          source.count,
          Number(source.media_count || 0) + Number(source.task_count || 0),
        ),
      ),
    ),
    sortOrder: finiteNumber(source.position, source.sort_order, source.sortOrder, index),
    editable: source.can_edit === true
      || source.editable === true
      || (
        source.can_edit === undefined
        && source.editable === undefined
        && canManageFolders
      ),
    createdAt: safeText(source.created_at ?? source.createdAt, 80),
    updatedAt: safeText(source.updated_at ?? source.updatedAt, 80),
  };
}

function normalizeItem(item, index, fallbackType = "") {
  const source = asRecord(item);
  const id = normalizedId(source.id ?? source.public_id ?? source.item_id);
  if (!id) return null;
  const entityType = normalizedEntityType(
    source.entity_type ?? source.entityType ?? source.object_type ?? source.type,
    inferEntityType(source, fallbackType),
  );
  const key = workspaceBoardItemKey(entityType, id);
  if (!key) return null;
  const title = safeText(
    source.title ??
      source.name ??
      source.original_filename ??
      source.product_name ??
      source.sku ??
      `${ENTITY_LABELS[entityType] || "Объект"} ${id}`,
    240,
  );
  const description = safeText(
    source.description ?? source.instructions ?? source.details ?? source.reason,
    2_000,
  );
  const subtitle = safeText(
    source.subtitle ??
      source.kind ??
      source.task_type ??
      source.sku ??
      source.platform ??
      description,
    240,
  );
  const mimeType = safeText(source.mime_type ?? source.mimeType, 160).toLowerCase();
  return {
    key,
    id,
    entityType,
    folderId: normalizedFolderReference(source.folder_id ?? source.folderId ?? source.workspace_folder_id),
    title: title || `${ENTITY_LABELS[entityType] || "Объект"} ${id}`,
    subtitle,
    description,
    status: normalizedStatus(source.status, "ready"),
    kind: safeText(source.kind ?? source.task_type ?? source.object_kind, 120),
    mimeType,
    previewUrl: safeText(
      source.signed_url ?? source.preview_url ?? source.access_url ?? source.thumbnail_url,
      2_000,
    ),
    sizeBytes: Math.max(0, finiteNumber(source.size_bytes, source.sizeBytes)),
    createdAt: safeText(source.created_at ?? source.createdAt, 80),
    updatedAt: safeText(source.updated_at ?? source.updatedAt, 80),
    sortOrder: finiteNumber(source.position, source.sort_order, source.sortOrder, index),
    movable: source.can_move !== false && source.movable !== false,
  };
}

function normalizeFolderParents(folders) {
  const byId = new Map(folders.map((folder) => [folder.id, folder]));
  return folders.map((folder) => {
    if (!folder.parentId || !byId.has(folder.parentId) || folder.parentId === folder.id) {
      return { ...folder, parentId: null };
    }
    const visited = new Set([folder.id]);
    let parentId = folder.parentId;
    while (parentId) {
      if (visited.has(parentId)) return { ...folder, parentId: null };
      visited.add(parentId);
      parentId = byId.get(parentId)?.parentId || null;
    }
    return folder;
  });
}

function freezeBoard(board) {
  board.folders.forEach(Object.freeze);
  board.items.forEach(Object.freeze);
  Object.freeze(board.folders);
  Object.freeze(board.items);
  Object.freeze(board.entityTypes);
  Object.freeze(board.counts);
  Object.freeze(board.capabilities);
  Object.freeze(board);
  NORMALIZED_BOARDS.add(board);
  return board;
}

export function workspaceBoardItemKey(type, id) {
  const entityType = normalizedEntityType(type, "");
  const entityId = normalizedId(id);
  return entityType && entityId ? `${entityType}:${entityId}` : "";
}

export function normalizeWorkspaceBoard(raw) {
  if (raw && typeof raw === "object" && NORMALIZED_BOARDS.has(raw)) {
    return raw;
  }
  const payload = raw?.data ?? raw;
  const source = asRecord(payload);
  const rawCapabilities = asRecord(source.capabilities);
  const capabilities = {
    manageFolders: rawCapabilities.manage_folders === true || rawCapabilities.manageFolders === true,
    moveItems: rawCapabilities.move_items === true || rawCapabilities.moveItems === true,
  };
  const rawFolders = Array.isArray(source.folders)
    ? source.folders
    : Array.isArray(source.workspace_folders)
      ? source.workspace_folders
      : Array.isArray(source.media_folders)
        ? source.media_folders
        : [];
  const folderMap = new Map();
  rawFolders.forEach((folder, index) => {
    const normalized = normalizeFolder(folder, index, capabilities.manageFolders);
    if (normalized && !folderMap.has(normalized.id)) folderMap.set(normalized.id, normalized);
  });
  const folders = normalizeFolderParents([...folderMap.values()])
    .filter((folder) => folder.status !== "deleted")
    .sort((left, right) => (
      right.sortOrder - left.sortOrder ||
      left.name.localeCompare(right.name, "ru-RU", { sensitivity: "base" }) ||
      left.id.localeCompare(right.id)
    ));
  const folderIds = new Set(folders.map((folder) => folder.id));

  const itemMap = new Map();
  itemSources(Array.isArray(payload) ? payload : source).forEach(({ items, fallbackType }) => {
    items.forEach((item, index) => {
      const normalized = normalizeItem(item, index, fallbackType);
      if (!normalized || itemMap.has(normalized.key)) return;
      itemMap.set(normalized.key, {
        ...normalized,
        folderId: normalized.folderId && folderIds.has(normalized.folderId)
          ? normalized.folderId
          : null,
        movable: normalized.movable && capabilities.moveItems,
      });
    });
  });
  const items = [...itemMap.values()]
    .filter((item) => item.status !== "deleted")
    .sort((left, right) => (
      right.sortOrder - left.sortOrder ||
      String(right.createdAt).localeCompare(String(left.createdAt)) ||
      left.key.localeCompare(right.key)
    ));
  const entityTypes = [...new Set(["media", "task", ...items.map((item) => item.entityType)])].sort();
  const counts = {
    all: items.length,
    root: items.filter((item) => !item.folderId).length,
  };
  folders.forEach((folder) => {
    const calculated = items.filter((item) => item.folderId === folder.id).length;
    counts[folder.id] = Math.max(folder.itemCount, calculated);
  });
  return freezeBoard({
    normalizedWorkspaceBoard: true,
    folders,
    items,
    entityTypes,
    counts,
    capabilities,
  });
}

export function workspaceBoardItemByKey(board, key) {
  const normalizedKey = safeText(key, ID_MAX_LENGTH * 2 + 1);
  if (!normalizedKey) return null;
  const normalizedBoard = normalizeWorkspaceBoard(board);
  return normalizedBoard.items.find((item) => item.key === normalizedKey) || null;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safePreviewUrl(value) {
  const candidate = safeText(value, 2_000);
  if (!candidate) return "";
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === "https:" || parsed.protocol === "blob:" ? parsed.href : "";
  } catch {
    return "";
  }
}

function domToken(value) {
  const normalized = String(value || "").replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  return normalized.slice(0, 120) || "item";
}

function humanEntityType(entityType) {
  return ENTITY_LABELS[entityType] || safeText(entityType, 40) || "Объект";
}

function humanStatus(status) {
  const labels = {
    active: "Активна",
    archived: "В архиве",
    ready: "Готово",
    todo: "Новая",
    in_progress: "В работе",
    submitted: "Отправлена",
    review: "Проверка",
    done: "Готово",
    blocked: "Блокер",
    failed: "Ошибка",
    processing: "Обработка",
    queued: "В очереди",
    published: "Опубликовано",
  };
  return labels[status] || safeText(status, 40) || "Без статуса";
}

function formatBytes(value) {
  const bytes = Math.max(0, Number(value) || 0);
  if (!bytes) return "";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 || unit === 0 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

function formatDate(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function selectedFolder(options, board) {
  const candidate = safeText(options.selectedFolderId || "all", ID_MAX_LENGTH);
  if (candidate === "all" || candidate === "root") return candidate;
  return board.folders.some((folder) => folder.id === candidate) ? candidate : "all";
}

function itemMatchesQuery(item, query) {
  if (!query) return true;
  const haystack = [
    item.title,
    item.subtitle,
    item.description,
    item.kind,
    item.status,
    item.id,
  ].join(" ").normalize("NFKC").toLocaleLowerCase("ru-RU");
  return haystack.includes(query.normalize("NFKC").toLocaleLowerCase("ru-RU"));
}

function filteredItems(board, folderId, query, entityType) {
  return board.items.filter((item) => {
    if (folderId === "root" && item.folderId) return false;
    if (folderId !== "all" && folderId !== "root" && item.folderId !== folderId) return false;
    if (entityType !== "all" && item.entityType !== entityType) return false;
    return itemMatchesQuery(item, query);
  });
}

function folderTreeMarkup(board, selectedFolderId, busy) {
  const children = new Map();
  board.folders.forEach((folder) => {
    const parentId = folder.parentId || "root";
    if (!children.has(parentId)) children.set(parentId, []);
    children.get(parentId).push(folder);
  });
  const renderBranch = (parentId, depth, ancestors = new Set()) => {
    if (depth > 12) return "";
    return (children.get(parentId) || []).map((folder) => {
      if (ancestors.has(folder.id)) return "";
      const nextAncestors = new Set(ancestors);
      nextAncestors.add(folder.id);
      const selected = selectedFolderId === folder.id;
      const nested = renderBranch(folder.id, depth + 1, nextAncestors);
      return `
        <li class="workspace-board__folder-row ${selected ? "is-selected" : ""}"
            data-workspace-drop-folder
            data-folder-id="${escapeHtml(folder.id)}"
            data-folder-version="${folder.version}"
            data-folder-color="${escapeHtml(folder.colorToken)}"
            style="--workspace-folder-depth:${depth}">
          <button class="workspace-board__folder-button"
                  type="button"
                  data-action="select-workspace-folder"
                  data-folder-id="${escapeHtml(folder.id)}"
                  ${selected ? 'aria-current="page"' : ""}
                  ${busy ? "disabled" : ""}>
            <span class="workspace-board__folder-icon" aria-hidden="true">◇</span>
            <span>${escapeHtml(folder.name)}</span>
            <small>${Number(board.counts[folder.id] || 0)}</small>
          </button>
          ${nested ? `<ul class="workspace-board__folder-branch">${nested}</ul>` : ""}
        </li>`;
    }).join("");
  };

  return `
    <nav class="workspace-board__folders" aria-label="Папки рабочего пространства">
      <ul class="workspace-board__folder-list">
        <li class="workspace-board__folder-row ${selectedFolderId === "all" ? "is-selected" : ""}">
          <button class="workspace-board__folder-button"
                  type="button"
                  data-action="select-workspace-folder"
                  data-folder-id="all"
                  ${selectedFolderId === "all" ? 'aria-current="page"' : ""}
                  ${busy ? "disabled" : ""}>
            <span class="workspace-board__folder-icon" aria-hidden="true">▦</span>
            <span>Все объекты</span>
            <small>${Number(board.counts.all || 0)}</small>
          </button>
        </li>
        <li class="workspace-board__folder-row ${selectedFolderId === "root" ? "is-selected" : ""}"
            data-workspace-drop-folder
            data-folder-id="root">
          <button class="workspace-board__folder-button"
                  type="button"
                  data-action="select-workspace-folder"
                  data-folder-id="root"
                  ${selectedFolderId === "root" ? 'aria-current="page"' : ""}
                  ${busy ? "disabled" : ""}>
            <span class="workspace-board__folder-icon" aria-hidden="true">⌂</span>
            <span>Без папки</span>
            <small>${Number(board.counts.root || 0)}</small>
          </button>
        </li>
        ${renderBranch("root", 0)}
      </ul>
    </nav>`;
}

function folderManagementMarkup(board, selectedFolderId, busy) {
  const selected = board.folders.find((folder) => folder.id === selectedFolderId) || null;
  if (!board.capabilities.manageFolders) {
    return `
      <div class="workspace-board__folder-management">
        <p class="workspace-board__muted">Создавать, переименовывать и архивировать папки может руководитель. Доступные вам объекты можно перемещать.</p>
      </div>`;
  }
  const parentFolderId = selected?.id || "root";
  return `
    <div class="workspace-board__folder-management">
      <form id="workspace-folder-create-form" class="workspace-board__compact-form">
        <input type="hidden" name="parent_folder_id" value="${escapeHtml(parentFolderId)}" />
        <label for="workspace-folder-name">Новая папка</label>
        <div>
          <input id="workspace-folder-name"
                 name="folder_name"
                 required
                 minlength="1"
                 maxlength="120"
                 autocomplete="off"
                 placeholder="${selected ? "Внутри выбранной папки" : "Например: Июль · Пилинг"}"
                 ${busy ? "disabled" : ""} />
          <button class="workspace-board__icon-button"
                  type="submit"
                  aria-label="Создать папку"
                  title="Создать папку"
                  ${busy ? "disabled" : ""}>+</button>
        </div>
      </form>
      <form id="workspace-folder-edit-form"
            class="workspace-board__compact-form"
            ${selected && selected.editable ? "" : 'hidden aria-hidden="true"'}>
          <input type="hidden" name="folder_id" value="${escapeHtml(selected?.id || "")}" />
          <input type="hidden" name="folder_version" value="${selected?.version || 1}" />
          <label for="workspace-folder-edit-name">Название выбранной папки</label>
          <div>
            <input id="workspace-folder-edit-name"
                   name="folder_name"
                   required
                   minlength="1"
                   maxlength="120"
                   value="${escapeHtml(selected?.name || "")}"
                   autocomplete="off"
                   ${busy || !selected?.editable ? "disabled" : ""} />
            <button class="workspace-board__icon-button"
                    type="submit"
                    aria-label="Сохранить название папки"
                    title="Сохранить название папки"
                    ${busy || !selected?.editable ? "disabled" : ""}>✓</button>
          </div>
          <button class="workspace-board__text-action workspace-board__text-action--danger"
                  type="button"
                  data-action="archive-workspace-folder"
                  data-folder-id="${escapeHtml(selected?.id || "")}"
                  data-folder-version="${selected?.version || 1}"
                  ${busy || !selected?.editable ? "disabled" : ""}>Архивировать папку</button>
        </form>
    </div>`;
}

function filterMarkup(board, options, resultCount, busy) {
  const selectedType = board.entityTypes.includes(options.entityType) ? options.entityType : "all";
  return `
    <form id="workspace-board-filter-form" class="workspace-board__filters" role="search">
      <label class="workspace-board__search">
        <span>Поиск</span>
        <input name="query"
               type="search"
               maxlength="${QUERY_MAX_LENGTH}"
               value="${escapeHtml(options.query)}"
               placeholder="Название, артикул или ID"
               autocomplete="off"
               ${busy ? "disabled" : ""} />
      </label>
      <label>
        <span>Тип объекта</span>
        <select name="entity_type" ${busy ? "disabled" : ""}>
          <option value="all" ${selectedType === "all" ? "selected" : ""}>Все типы</option>
          ${board.entityTypes.map((entityType) => `
            <option value="${escapeHtml(entityType)}" ${selectedType === entityType ? "selected" : ""}>
              ${escapeHtml(humanEntityType(entityType))}
            </option>`).join("")}
        </select>
      </label>
      <button class="workspace-board__filter-submit" type="submit" ${busy ? "disabled" : ""}>Показать</button>
      <button class="workspace-board__filter-reset"
              type="button"
              data-action="reset-workspace-filters"
              ${busy ? "disabled" : ""}>Сбросить</button>
      <p class="workspace-board__filter-result" role="status" aria-live="polite">
        Найдено: <strong>${resultCount}</strong>
      </p>
    </form>`;
}

function itemPreviewMarkup(item, detailed = false) {
  const previewUrl = safePreviewUrl(item.previewUrl);
  if (previewUrl && item.mimeType.startsWith("image/")) {
    return `<img src="${escapeHtml(previewUrl)}" alt="" loading="lazy" />`;
  }
  if (previewUrl && item.mimeType === "video/mp4" && detailed) {
    return `<video src="${escapeHtml(previewUrl)}" controls preload="none" playsinline aria-label="Видео: ${escapeHtml(item.title)}"></video>`;
  }
  if (previewUrl && item.mimeType === "video/mp4") {
    return `<span class="workspace-board__preview-symbol" aria-hidden="true">▶</span>`;
  }
  return `<span class="workspace-board__preview-symbol" aria-hidden="true">${escapeHtml(ENTITY_ICONS[item.entityType] || "◇")}</span>`;
}

function itemCardMarkup(item, selectedItemKey, busy) {
  const selected = item.key === selectedItemKey;
  const descriptionId = `workspace-item-${domToken(item.key)}-description`;
  return `
    <article class="workspace-board__item ${selected ? "is-selected" : ""}"
             data-workspace-item-key="${escapeHtml(item.key)}"
             data-entity-type="${escapeHtml(item.entityType)}"
             data-entity-id="${escapeHtml(item.id)}">
      <button class="workspace-board__item-open"
              type="button"
              data-action="open-workspace-item"
              data-item-key="${escapeHtml(item.key)}"
              data-entity-type="${escapeHtml(item.entityType)}"
              data-entity-id="${escapeHtml(item.id)}"
              aria-describedby="${escapeHtml(descriptionId)}"
              aria-controls="workspace-board-item-drawer"
              aria-expanded="${selected ? "true" : "false"}"
              ${busy ? "disabled" : ""}>
        <span class="workspace-board__item-preview">${itemPreviewMarkup(item)}</span>
        <span class="workspace-board__item-copy">
          <small>${escapeHtml(humanEntityType(item.entityType))}</small>
          <strong>${escapeHtml(item.title)}</strong>
          <span id="${escapeHtml(descriptionId)}">${escapeHtml(item.subtitle || humanStatus(item.status))}</span>
        </span>
        <span class="workspace-board__status" data-status="${escapeHtml(item.status)}">
          ${escapeHtml(humanStatus(item.status))}
        </span>
      </button>
      ${item.movable ? `
        <button class="workspace-board__drag-handle"
                type="button"
                draggable="${busy ? "false" : "true"}"
                data-action="open-workspace-item"
                data-workspace-drag-item
                data-entity-type="${escapeHtml(item.entityType)}"
                data-entity-id="${escapeHtml(item.id)}"
                data-item-key="${escapeHtml(item.key)}"
                aria-label="Переместить: ${escapeHtml(item.title)}"
                aria-describedby="${escapeHtml(descriptionId)}"
                title="Перетащить или нажать, чтобы выбрать место"
                ${busy ? "disabled" : ""}>
          <span aria-hidden="true">⠿</span>
        </button>` : ""}
    </article>`;
}

function itemDrawerMarkup(board, selectedItem, busy) {
  if (!selectedItem) {
    return `
      <aside id="workspace-board-item-drawer"
             class="workspace-board__drawer workspace-board__drawer--empty"
             aria-label="Сведения об объекте">
        <span class="workspace-board__drawer-mark" aria-hidden="true">◇</span>
        <h2>Выберите объект</h2>
        <p>Нажмите карточку, чтобы открыть детали и переместить объект без перетаскивания.</p>
      </aside>`;
  }
  const currentFolder = board.folders.find((folder) => folder.id === selectedItem.folderId);
  const moveTargets = [
    { id: "root", name: "Без папки" },
    ...board.folders.filter((folder) => folder.status === "active"),
  ].filter((folder) => folder.id !== (selectedItem.folderId || "root"));
  const formattedSize = formatBytes(selectedItem.sizeBytes);
  const formattedDate = formatDate(selectedItem.createdAt);
  return `
    <aside id="workspace-board-item-drawer"
           class="workspace-board__drawer"
           aria-labelledby="workspace-board-drawer-title"
           data-workspace-item-drawer
           data-item-key="${escapeHtml(selectedItem.key)}">
      <div class="workspace-board__drawer-head">
        <div>
          <p>${escapeHtml(humanEntityType(selectedItem.entityType))}</p>
          <h2 id="workspace-board-drawer-title">${escapeHtml(selectedItem.title)}</h2>
        </div>
        <button class="workspace-board__drawer-close"
                type="button"
                data-action="close-workspace-item"
                aria-label="Закрыть сведения об объекте">×</button>
      </div>
      <div class="workspace-board__drawer-preview">${itemPreviewMarkup(selectedItem, true)}</div>
      ${selectedItem.description ? `<p class="workspace-board__drawer-description">${escapeHtml(selectedItem.description)}</p>` : ""}
      <dl class="workspace-board__drawer-facts">
        <div><dt>Статус</dt><dd>${escapeHtml(humanStatus(selectedItem.status))}</dd></div>
        <div><dt>Папка</dt><dd>${escapeHtml(currentFolder?.name || "Без папки")}</dd></div>
        ${selectedItem.kind ? `<div><dt>Тип</dt><dd>${escapeHtml(selectedItem.kind)}</dd></div>` : ""}
        ${formattedSize ? `<div><dt>Размер</dt><dd>${escapeHtml(formattedSize)}</dd></div>` : ""}
        ${formattedDate ? `<div><dt>Добавлено</dt><dd>${escapeHtml(formattedDate)}</dd></div>` : ""}
        <div><dt>ID</dt><dd><code>${escapeHtml(selectedItem.id)}</code></dd></div>
      </dl>
      ${selectedItem.movable ? `
        <section class="workspace-board__move-panel" aria-labelledby="workspace-board-move-title">
          <h3 id="workspace-board-move-title">Переместить в папку</h3>
          <p>Это доступная замена drag-and-drop для клавиатуры и телефона.</p>
          <div class="workspace-board__move-targets">
            ${moveTargets.length ? moveTargets.map((folder) => `
              <button type="button"
                      data-action="move-workspace-item"
                      data-item-key="${escapeHtml(selectedItem.key)}"
                      data-entity-type="${escapeHtml(selectedItem.entityType)}"
                      data-entity-id="${escapeHtml(selectedItem.id)}"
                      data-folder-id="${escapeHtml(folder.id)}"
                      data-target-folder-id="${escapeHtml(folder.id)}"
                      ${busy ? "disabled" : ""}>
                <span aria-hidden="true">◇</span>
                <span>${escapeHtml(folder.name)}</span>
              </button>`).join("") : `<span class="workspace-board__muted">Других папок пока нет.</span>`}
          </div>
        </section>` : ""}
    </aside>`;
}

export function workspaceBoardMarkup(board, options = {}) {
  const normalizedBoard = normalizeWorkspaceBoard(board);
  const normalizedOptions = {
    selectedFolderId: selectedFolder(options, normalizedBoard),
    selectedItemKey: safeText(options.selectedItemKey, ID_MAX_LENGTH * 2 + 1),
    query: safeText(options.query, QUERY_MAX_LENGTH),
    entityType: normalizedEntityType(options.entityType, "all"),
    busy: options.busy === true,
    notice: safeText(options.notice, 1_000),
    error: safeText(options.error, 1_000),
  };
  if (options.entityType === "all" || !options.entityType) normalizedOptions.entityType = "all";
  if (
    normalizedOptions.entityType !== "all" &&
    !normalizedBoard.entityTypes.includes(normalizedOptions.entityType)
  ) normalizedOptions.entityType = "all";
  const items = filteredItems(
    normalizedBoard,
    normalizedOptions.selectedFolderId,
    normalizedOptions.query,
    normalizedOptions.entityType,
  );
  const selectedItem = workspaceBoardItemByKey(normalizedBoard, normalizedOptions.selectedItemKey);
  const selectedFolderName = normalizedOptions.selectedFolderId === "all"
    ? "Все объекты"
    : normalizedOptions.selectedFolderId === "root"
      ? "Без папки"
      : normalizedBoard.folders.find((folder) => folder.id === normalizedOptions.selectedFolderId)?.name || "Папка";

  return `
    <section class="workspace-board"
             aria-labelledby="workspace-board-title"
             aria-busy="${normalizedOptions.busy ? "true" : "false"}">
      <div id="workspace-board-announcer"
           class="workspace-board__sr-only"
           role="status"
           aria-live="polite"
           aria-atomic="true">${escapeHtml(normalizedOptions.notice)}</div>
      <header class="workspace-board__head">
        <div>
          <p class="workspace-board__eyebrow">Рабочее пространство</p>
          <h1 id="workspace-board-title">Объекты и папки</h1>
          <p>Откройте карточку нажатием. Для перемещения используйте ручку, либо выберите папку в панели объекта.</p>
        </div>
        <span class="workspace-board__head-count">${normalizedBoard.items.length} объектов</span>
      </header>
      ${normalizedOptions.error ? `
        <div class="workspace-board__message workspace-board__message--error" role="alert">
          <strong>Действие не выполнено</strong>
          <span>${escapeHtml(normalizedOptions.error)}</span>
        </div>` : ""}
      ${normalizedOptions.notice ? `
        <div class="workspace-board__message workspace-board__message--notice">
          <span>${escapeHtml(normalizedOptions.notice)}</span>
        </div>` : ""}
      <div class="workspace-board__layout">
        <aside class="workspace-board__sidebar" aria-label="Управление папками">
          <div class="workspace-board__sidebar-head">
            <p>Папки</p>
            <small>Перетащите объект на папку</small>
          </div>
          ${folderTreeMarkup(normalizedBoard, normalizedOptions.selectedFolderId, normalizedOptions.busy)}
          ${folderManagementMarkup(normalizedBoard, normalizedOptions.selectedFolderId, normalizedOptions.busy)}
        </aside>
        <section class="workspace-board__content" aria-labelledby="workspace-board-collection-title">
          ${filterMarkup(normalizedBoard, normalizedOptions, items.length, normalizedOptions.busy)}
          <div class="workspace-board__collection-head">
            <div>
              <p>Открытая папка</p>
              <h2 id="workspace-board-collection-title">${escapeHtml(selectedFolderName)}</h2>
            </div>
            <small>${items.length} на экране</small>
          </div>
          ${items.length ? `
            <div class="workspace-board__grid" aria-label="Объекты папки">
              ${items.map((item) => itemCardMarkup(
                item,
                normalizedOptions.selectedItemKey,
                normalizedOptions.busy,
              )).join("")}
            </div>` : `
            <div class="workspace-board__empty">
              <span aria-hidden="true">◇</span>
              <h3>Здесь пока пусто</h3>
              <p>${normalizedOptions.query || normalizedOptions.entityType !== "all"
                ? "Сбросьте фильтры или выберите другую папку."
                : "Добавьте объект или переместите его сюда из другой папки."}</p>
              ${normalizedOptions.query || normalizedOptions.entityType !== "all" ? `
                <button type="button" data-action="reset-workspace-filters">Сбросить фильтры</button>` : ""}
            </div>`}
        </section>
        ${itemDrawerMarkup(normalizedBoard, selectedItem, normalizedOptions.busy)}
      </div>
    </section>`;
}
