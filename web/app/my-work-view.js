const ITEM_TYPE_META = Object.freeze({
  task: Object.freeze({ label: "Задача", icon: "✓", href: "#/workspace/tasks" }),
  generation: Object.freeze({ label: "Генерация", icon: "✦", href: "#/workspace/generation" }),
  review: Object.freeze({ label: "Проверка", icon: "◉", href: "#/workspace/review" }),
  placement: Object.freeze({ label: "Публикация", icon: "↗", href: "#/workspace/placement" }),
  payout: Object.freeze({ label: "Выплата", icon: "₽", href: "#/workspace/payouts" }),
});

const STATUS_META = Object.freeze({
  queued: Object.freeze({ label: "В очереди", tone: "info" }),
  starting: Object.freeze({ label: "Запускается", tone: "info" }),
  submitted: Object.freeze({ label: "Отправлено", tone: "info" }),
  processing: Object.freeze({ label: "Обрабатывается", tone: "info" }),
  running: Object.freeze({ label: "Обрабатывается", tone: "info" }),
  todo: Object.freeze({ label: "Нужно начать", tone: "warning" }),
  in_progress: Object.freeze({ label: "В работе", tone: "warning" }),
  review: Object.freeze({ label: "Ждёт проверки", tone: "warning" }),
  awaiting_decision: Object.freeze({ label: "Нужно решение", tone: "warning" }),
  blocked: Object.freeze({ label: "Есть блокер", tone: "danger" }),
  failed: Object.freeze({ label: "Ошибка", tone: "danger" }),
  rejected: Object.freeze({ label: "Отклонено", tone: "danger" }),
  ready: Object.freeze({ label: "Готово", tone: "success" }),
  succeeded: Object.freeze({ label: "Готово", tone: "success" }),
  completed: Object.freeze({ label: "Завершено", tone: "success" }),
  done: Object.freeze({ label: "Завершено", tone: "success" }),
  approved: Object.freeze({ label: "Одобрено", tone: "success" }),
  scheduled: Object.freeze({ label: "Запланировано", tone: "info" }),
  published: Object.freeze({ label: "Опубликовано", tone: "success" }),
  pending: Object.freeze({ label: "Ждёт решения", tone: "warning" }),
  paid: Object.freeze({ label: "Выплачено", tone: "success" }),
});

export const MY_WORK_ITEM_TYPES = Object.freeze(Object.keys(ITEM_TYPE_META));

export function normalizeMyWork(raw) {
  const root = objectValue(raw?.data) || objectValue(raw) || {};
  const counts = objectValue(root.counts) || {};
  return {
    organizationId: String(root.organization_id ?? root.organizationId ?? ""),
    filters: normalizeMyWorkFilters(root.filters),
    counts: {
      total: positiveInteger(counts.total),
      task: positiveInteger(counts.task),
      generation: positiveInteger(counts.generation),
      review: positiveInteger(counts.review),
      placement: positiveInteger(counts.placement),
      payout: positiveInteger(counts.payout),
      actionRequired: positiveInteger(counts.action_required ?? counts.actionRequired),
      blockers: positiveInteger(counts.blockers),
      overdue: positiveInteger(counts.overdue),
    },
    items: arrayValue(root.items).map(normalizeWorkItem).filter((item) => item.id),
    nextCursor: objectValue(root.next_cursor ?? root.nextCursor),
  };
}

export function normalizeNotifications(raw) {
  const root = objectValue(raw?.data) || objectValue(raw) || {};
  const counts = objectValue(root.counts) || {};
  const items = arrayValue(root.items).map((item) => ({
    id: String(item?.id || ""),
    kind: cleanToken(item?.kind, "system"),
    severity: normalizeSeverity(item?.severity),
    title: cleanText(item?.title, "Новое событие"),
    body: cleanText(item?.body),
    deepLink: safeInternalLink(item?.deep_link ?? item?.deepLink),
    entityType: cleanToken(item?.entity_type ?? item?.entityType),
    entityId: String(item?.entity_id ?? item?.entityId ?? ""),
    readAt: cleanText(item?.read_at ?? item?.readAt),
    createdAt: cleanText(item?.created_at ?? item?.createdAt),
  })).filter((item) => item.id);
  return {
    organizationId: String(root.organization_id ?? root.organizationId ?? ""),
    counts: {
      total: Number.isFinite(Number(counts.total)) ? positiveInteger(counts.total) : items.length,
      unread: Number.isFinite(Number(counts.unread))
        ? positiveInteger(counts.unread)
        : items.filter((item) => !item.readAt).length,
    },
    items,
    nextCursor: objectValue(root.next_cursor ?? root.nextCursor),
  };
}

export function normalizeSavedWorkViews(raw) {
  const root = objectValue(raw?.data) || objectValue(raw) || {};
  return arrayValue(root.views).map((view) => ({
    id: String(view?.id || ""),
    name: cleanText(view?.name, "Без названия"),
    filters: normalizeMyWorkFilters(view?.filters),
    isDefault: view?.is_default === true || view?.isDefault === true,
    version: Math.max(1, positiveInteger(view?.version) || 1),
    createdAt: cleanText(view?.created_at ?? view?.createdAt),
    updatedAt: cleanText(view?.updated_at ?? view?.updatedAt),
  })).filter((view) => view.id);
}

export function normalizeMyWorkFilters(raw = {}) {
  const source = objectValue(raw) || {};
  return {
    query: cleanText(source.query).slice(0, 120),
    itemTypes: uniqueTokens(source.item_types ?? source.itemTypes)
      .filter((itemType) => MY_WORK_ITEM_TYPES.includes(itemType))
      .slice(0, MY_WORK_ITEM_TYPES.length),
    statuses: uniqueTokens(source.statuses).slice(0, 20),
  };
}

export function readMyWorkFilters(form) {
  const values = new FormData(form);
  return normalizeMyWorkFilters({
    query: values.get("query"),
    item_types: values.getAll("item_types"),
    statuses: values.getAll("statuses"),
  });
}

export function myWorkRequestOptions(filters, cursor = null) {
  const normalized = normalizeMyWorkFilters(filters);
  const payload = {
    query: normalized.query,
    item_types: normalized.itemTypes,
    statuses: normalized.statuses,
    page_size: 50,
  };
  if (!payload.query) delete payload.query;
  if (!payload.item_types.length) delete payload.item_types;
  if (!payload.statuses.length) delete payload.statuses;
  if (cursor) payload.cursor = cursor;
  return payload;
}

export function myWorkWorkspaceMarkup({
  work,
  notifications,
  savedViews = [],
  filters = {},
  selectedViewId = "",
  notice = "",
  error = "",
  loadingMore = false,
} = {}) {
  const normalizedWork = normalizeMyWork(work);
  const normalizedNotifications = normalizeNotifications(notifications);
  const normalizedFilters = normalizeMyWorkFilters(filters);
  const views = Array.isArray(savedViews) ? savedViews : normalizeSavedWorkViews(savedViews);
  const activeFilters = normalizedFilters.itemTypes.length
    + normalizedFilters.statuses.length
    + (normalizedFilters.query ? 1 : 0);
  const summaryCards = [
    ["Всего", normalizedWork.counts.total, "Все найденные объекты", "all"],
    [
      "Требуют действия",
      normalizedWork.counts.actionRequired,
      normalizedWork.counts.blockers
        ? `Блокеров: ${formatNumber(normalizedWork.counts.blockers)}`
        : "Начните с них",
      "action",
    ],
    ["Просрочено", normalizedWork.counts.overdue, "Нужна реакция сегодня", "overdue"],
    ["Уведомления", normalizedNotifications.counts.unread, "Непрочитанные события", "notifications"],
  ];

  return `
    <div class="page-wrap my-work-page">
      <section class="my-work-hero">
        <div>
          <p class="eyebrow">Единая рабочая очередь</p>
          <h1>Моя работа</h1>
          <p>Задачи, генерации, проверки, публикации и выплаты собраны в одном месте. Сначала разберите блокеры и просрочки.</p>
        </div>
        <div class="my-work-hero-actions">
          <button class="btn btn-secondary btn-small" type="button" data-action="refresh-my-work">Обновить</button>
          <button class="btn btn-small" type="button" data-action="toggle-work-notifications" aria-expanded="false">
            Уведомления${normalizedNotifications.counts.unread ? ` · ${formatNumber(normalizedNotifications.counts.unread)}` : ""}
          </button>
        </div>
      </section>

      ${notice ? alertMarkup(notice, "success") : ""}
      ${error ? alertMarkup(error, "danger") : ""}

      <div class="my-work-summary" aria-label="Сводка очереди">
        ${summaryCards.map(([label, value, hint, tone]) => `
          <article class="my-work-summary-card my-work-summary-card--${tone}">
            <span>${escapeHtml(label)}</span>
            <strong>${formatNumber(value)}</strong>
            <small>${escapeHtml(hint)}</small>
          </article>
        `).join("")}
      </div>

      <div class="my-work-layout">
        <aside class="my-work-sidebar">
          <section class="card card-pad">
            <div class="my-work-section-heading">
              <div><p class="eyebrow">Представления</p><h2>Мои фильтры</h2></div>
              <span class="badge">${formatNumber(views.length)}</span>
            </div>
            <div class="my-work-view-list">
              <button class="my-work-view-button ${selectedViewId ? "" : "active"}" type="button" data-action="apply-my-work-view" data-view-id="">Все объекты</button>
              ${views.map((view) => `
                <div class="my-work-view-row">
                  <button class="my-work-view-button ${String(selectedViewId) === view.id ? "active" : ""}" type="button" data-action="apply-my-work-view" data-view-id="${escapeHtml(view.id)}">
                    <span>${escapeHtml(view.name)}</span>${view.isDefault ? "<small>по умолчанию</small>" : ""}
                  </button>
                  <button class="my-work-view-delete" type="button" data-action="delete-my-work-view" data-view-id="${escapeHtml(view.id)}" data-view-version="${view.version}" aria-label="Удалить фильтр ${escapeHtml(view.name)}">×</button>
                </div>
              `).join("")}
            </div>
            <form id="save-my-work-view-form" class="form-stack my-work-save-view" novalidate>
              <label class="field"><span>Название текущего фильтра</span><input name="name" minlength="2" maxlength="80" required placeholder="Например: срочные публикации" /></label>
              <label class="check-row"><input type="checkbox" name="is_default" value="true" /><span>Открывать по умолчанию</span></label>
              <button class="btn btn-secondary btn-small" type="submit">Сохранить представление</button>
            </form>
          </section>
        </aside>

        <div class="my-work-main">
          <form id="my-work-filter-form" class="card card-pad my-work-filter" novalidate>
            <div class="my-work-filter-top">
              <label class="field my-work-search">
                <span>Поиск по работе</span>
                <input name="query" type="search" maxlength="120" value="${escapeHtml(normalizedFilters.query)}" placeholder="Товар, задача, статус…" />
              </label>
              <button class="btn" type="submit">Найти</button>
              <button class="btn btn-secondary" type="button" data-action="reset-my-work-filters" ${activeFilters ? "" : "disabled"}>Сбросить</button>
            </div>
            <fieldset class="my-work-filter-group">
              <legend>Что показать</legend>
              ${MY_WORK_ITEM_TYPES.map((itemType) => filterChip(
                "item_types",
                itemType,
                ITEM_TYPE_META[itemType].label,
                normalizedFilters.itemTypes.includes(itemType),
              )).join("")}
            </fieldset>
            <fieldset class="my-work-filter-group">
              <legend>Состояние</legend>
              ${[
                ["todo", "Нужно начать"],
                ["in_progress", "В работе"],
                ["review", "Ждёт проверки"],
                ["awaiting_decision", "Нужно решение"],
                ["blocked", "Блокер"],
                ["failed", "Ошибка"],
                ["pending", "Ждёт решения"],
              ].map(([status, label]) => filterChip(
                "statuses",
                status,
                label,
                normalizedFilters.statuses.includes(status),
              )).join("")}
            </fieldset>
          </form>

          <section class="my-work-queue" aria-labelledby="my-work-queue-title">
            <div class="my-work-section-heading">
              <div><p class="eyebrow">Приоритетная очередь</p><h2 id="my-work-queue-title">${activeFilters ? "Результаты фильтра" : "Что требует внимания"}</h2></div>
              <span class="badge">${formatNumber(normalizedWork.counts.total)}</span>
            </div>
            ${normalizedWork.items.length
              ? normalizedWork.items.map(workItemMarkup).join("")
              : emptyWorkMarkup(activeFilters)}
            ${normalizedWork.nextCursor ? `
              <button class="btn btn-secondary btn-block" type="button" data-action="load-more-my-work" ${loadingMore ? "disabled" : ""}>
                ${loadingMore ? "Загружаем…" : "Показать ещё"}
              </button>
            ` : ""}
          </section>
        </div>
      </div>
    </div>
  `;
}

export function notificationCenterMarkup(raw, { open = false, loading = false, error = "" } = {}) {
  const notifications = normalizeNotifications(raw);
  return `
    <div class="notification-layer ${open ? "open" : ""}" data-notification-layer ${open ? "" : "hidden"}>
      <button class="notification-backdrop" type="button" data-action="toggle-work-notifications" aria-label="Закрыть уведомления"></button>
      <aside class="notification-drawer" role="dialog" aria-modal="true" aria-labelledby="notification-center-title">
        <header>
          <div><p class="eyebrow">Центр событий</p><h2 id="notification-center-title">Уведомления</h2></div>
          <button class="notification-close" type="button" data-action="toggle-work-notifications" aria-label="Закрыть">×</button>
        </header>
        <div class="notification-toolbar">
          <span>${formatNumber(notifications.counts.unread)} непрочитанных</span>
          ${notifications.counts.unread ? `<button class="text-link" type="button" data-action="mark-all-notifications-read">Прочитать все</button>` : ""}
        </div>
        ${error ? alertMarkup(error, "danger") : ""}
        ${loading ? `<div class="notification-loading" role="status">Загружаем события…</div>` : notifications.items.length
          ? `<div class="notification-list">${notifications.items.map(notificationMarkup).join("")}</div>`
          : `<div class="notification-empty"><span aria-hidden="true">✓</span><strong>Новых событий нет</strong><p>Здесь появятся готовые ролики, блокеры, решения и выплаты.</p></div>`}
      </aside>
    </div>
  `;
}

function normalizeWorkItem(item) {
  const itemType = cleanToken(item?.item_type ?? item?.itemType);
  const meta = ITEM_TYPE_META[itemType] || ITEM_TYPE_META.task;
  const dueAt = cleanText(item?.due_at ?? item?.dueAt);
  const dueDate = dueAt ? new Date(dueAt) : null;
  const overdue = dueDate && Number.isFinite(dueDate.getTime())
    && dueDate.getTime() < Date.now()
    && !["done", "completed", "succeeded", "paid", "published", "cancelled"].includes(cleanToken(item?.status));
  return {
    itemType: ITEM_TYPE_META[itemType] ? itemType : "task",
    id: String(item?.id || ""),
    status: cleanToken(item?.status, "todo"),
    title: cleanText(item?.title, `${meta.label} без названия`),
    summary: cleanText(item?.summary),
    deepLink: safeInternalLink(item?.deep_link ?? item?.deepLink) || meta.href,
    productId: String(item?.product_id ?? item?.productId ?? ""),
    taskId: String(item?.task_id ?? item?.taskId ?? ""),
    assigneeId: String(item?.assignee_id ?? item?.assigneeId ?? ""),
    dueAt,
    updatedAt: cleanText(item?.updated_at ?? item?.updatedAt),
    amountMinor: Number.isFinite(Number(item?.amount_minor ?? item?.amountMinor))
      ? Math.max(0, Number(item?.amount_minor ?? item?.amountMinor))
      : null,
    currency: cleanToken(item?.currency, "rub").toUpperCase(),
    metadata: objectValue(item?.metadata) || {},
    actionRequired: item?.action_required === true || item?.actionRequired === true,
    blocker: item?.blocker === true,
    overdue,
  };
}

function workItemMarkup(item) {
  const typeMeta = ITEM_TYPE_META[item.itemType] || ITEM_TYPE_META.task;
  const statusMeta = STATUS_META[item.status] || { label: humanizeToken(item.status), tone: "info" };
  const actionLabel = item.metadata.action_label || item.metadata.actionLabel || actionLabelFor(item);
  return `
    <article
      class="my-work-item ${item.overdue ? "my-work-item--overdue" : ""}"
      data-work-item-type="${escapeHtml(item.itemType)}"
      data-work-item-id="${escapeHtml(item.id)}"
      data-work-item-action-required="${item.actionRequired ? "true" : "false"}"
      data-work-item-blocker="${item.blocker ? "true" : "false"}"
      tabindex="-1"
    >
      <div class="my-work-item-icon" aria-hidden="true">${escapeHtml(typeMeta.icon)}</div>
      <div class="my-work-item-copy">
        <div class="my-work-item-meta">
          <span>${escapeHtml(typeMeta.label)}</span>
          <span class="my-work-status my-work-status--${escapeHtml(statusMeta.tone)}">${escapeHtml(statusMeta.label)}</span>
          ${item.overdue ? '<span class="my-work-overdue">Просрочено</span>' : ""}
        </div>
        <h3>${escapeHtml(item.title)}</h3>
        ${item.summary ? `<p>${escapeHtml(item.summary)}</p>` : ""}
        <div class="my-work-item-facts">
          ${item.dueAt ? `<span><small>Срок</small>${escapeHtml(formatDateTime(item.dueAt))}</span>` : ""}
          ${item.updatedAt ? `<span><small>Обновлено</small>${escapeHtml(formatDateTime(item.updatedAt))}</span>` : ""}
          ${item.amountMinor !== null ? `<span><small>Сумма</small>${escapeHtml(formatMoney(item.amountMinor, item.currency))}</span>` : ""}
        </div>
      </div>
      <a class="btn btn-secondary btn-small my-work-item-action" href="${escapeHtml(item.deepLink)}">${escapeHtml(actionLabel)} <span aria-hidden="true">→</span></a>
    </article>
  `;
}

function notificationMarkup(item) {
  const body = `
    <div class="notification-icon notification-icon--${escapeHtml(item.severity)}" aria-hidden="true">${notificationIcon(item.severity)}</div>
    <div>
      <div class="notification-title"><strong>${escapeHtml(item.title)}</strong>${item.readAt ? "" : '<span class="notification-unread" aria-label="Новое"></span>'}</div>
      ${item.body ? `<p>${escapeHtml(item.body)}</p>` : ""}
      <time datetime="${escapeHtml(item.createdAt)}">${escapeHtml(formatDateTime(item.createdAt))}</time>
    </div>
  `;
  const markRead = item.readAt ? "" : ` data-action="open-work-notification" data-notification-id="${escapeHtml(item.id)}"`;
  return item.deepLink
    ? `<a class="notification-item ${item.readAt ? "read" : ""}" href="${escapeHtml(item.deepLink)}"${markRead}>${body}</a>`
    : `<button class="notification-item ${item.readAt ? "read" : ""}" type="button"${markRead}>${body}</button>`;
}

function filterChip(name, value, label, checked) {
  return `<label class="my-work-filter-chip"><input type="checkbox" name="${escapeHtml(name)}" value="${escapeHtml(value)}" ${checked ? "checked" : ""} /><span>${escapeHtml(label)}</span></label>`;
}

function emptyWorkMarkup(activeFilters) {
  return `
    <div class="my-work-empty">
      <span aria-hidden="true">${activeFilters ? "⌕" : "✓"}</span>
      <h3>${activeFilters ? "По фильтру ничего не найдено" : "Очередь разобрана"}</h3>
      <p>${activeFilters ? "Измените условия или сбросьте фильтры." : "Сейчас нет объектов, которые требуют вашего действия."}</p>
    </div>
  `;
}

function actionLabelFor(item) {
  if (["blocked", "failed", "rejected"].includes(item.status)) return "Разобраться";
  if (item.status === "awaiting_decision") return "Принять решение";
  if (["review", "submitted", "pending"].includes(item.status)) return "Проверить";
  if (["ready", "succeeded", "completed", "done", "approved", "published", "paid"].includes(item.status)) return "Открыть";
  return "Продолжить";
}

function safeInternalLink(value) {
  const link = cleanText(value);
  if (!link) return "";
  return /^#\/(?:workspace|learn)(?:\/|$|\?)/u.test(link) ? link : "";
}

function normalizeSeverity(value) {
  const severity = cleanToken(value, "info");
  if (severity === "error") return "danger";
  return ["info", "success", "warning", "danger"].includes(severity) ? severity : "info";
}

function notificationIcon(severity) {
  return { success: "✓", warning: "!", danger: "×", info: "i" }[severity] || "i";
}

function humanizeToken(value) {
  const text = cleanText(value).replaceAll("_", " ");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Статус";
}

function formatMoney(minor, currency = "RUB") {
  try {
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: currency || "RUB",
      maximumFractionDigits: 2,
    }).format((Number(minor) || 0) / 100);
  } catch {
    return `${((Number(minor) || 0) / 100).toFixed(2)} ${currency || "RUB"}`;
  }
}

function formatDateTime(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "дата не указана";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatNumber(value) {
  return new Intl.NumberFormat("ru-RU").format(positiveInteger(value));
}

function positiveInteger(value) {
  return Math.max(0, Math.trunc(Number(value) || 0));
}

function uniqueTokens(value) {
  return [...new Set(arrayValue(value).map((item) => cleanToken(item)).filter(Boolean))];
}

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function cleanToken(value, fallback = "") {
  const token = String(value ?? fallback).trim().toLowerCase();
  return /^[a-z0-9_-]{1,80}$/u.test(token) ? token : fallback;
}

function cleanText(value, fallback = "") {
  return String(value ?? fallback).trim();
}

function alertMarkup(message, tone) {
  return `<div class="alert alert-${escapeHtml(tone)}" role="alert"><strong aria-hidden="true">${tone === "danger" ? "!" : "✓"}</strong><span>${escapeHtml(message)}</span></div>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
