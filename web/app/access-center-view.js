const DELIVERY_META = Object.freeze({
  delivered: Object.freeze({
    label: "Доставлено",
    detail: "Почтовый сервис подтвердил доставку последнего письма.",
    tone: "success",
  }),
  deferred: Object.freeze({
    label: "Доставка отложена",
    detail: "Почтовый сервис временно отложил доставку. Не отправляйте письма подряд.",
    tone: "warning",
  }),
  bounced: Object.freeze({
    label: "Письмо возвращено",
    detail: "Адрес или почтовый ящик отклонил письмо. Автоматический повтор отключён.",
    tone: "danger",
  }),
  complained: Object.freeze({
    label: "Жалоба на письмо",
    detail: "Получатель отметил письмо как нежелательное. Автоматический повтор отключён.",
    tone: "danger",
  }),
  failed: Object.freeze({
    label: "Ошибка почтового провайдера",
    detail: "Провайдер завершил попытку ошибкой. Автоматический повтор остановлен до ручной проверки причины и адреса.",
    tone: "danger",
  }),
  suppressed: Object.freeze({
    label: "Повтор подавлен",
    detail: "Новое письмо не отправлялось: сервер остановил дубль или слишком частый запрос. Проверьте последнюю попытку и защитный интервал.",
    tone: "warning",
  }),
  accepted: Object.freeze({
    label: "Принято почтовым сервисом",
    detail: "Запрос принят, но доставка письма ещё не подтверждена.",
    tone: "info",
  }),
  unknown: Object.freeze({
    label: "Доставка не подтверждена",
    detail: "Надёжного события доставки последнего письма пока нет.",
    tone: "neutral",
  }),
});

const OUTCOME_COPY = Object.freeze({
  already_ready: "Доступ уже готов: новое письмо не отправлялось.",
  pending_delivery: "Предыдущее письмо ещё обрабатывается. Используйте только самое свежее письмо и не запускайте повторы подряд.",
  recovery_requested: "Сервис принял запрос восстановления. Доставка письма пока не подтверждена.",
  invite_requested: "Сервис принял новое приглашение. Доставка письма пока не подтверждена.",
  membership_connected_recovery_requested: "Существующий аккаунт подключён к команде, запрос восстановления принят.",
  invite_pending_verification: "Приглашение принято, но итог доставки ещё проверяется.",
  cooldown: "Повтор временно закрыт защитным интервалом. Сначала проверьте статус самого свежего письма.",
  provider_outcome_pending: "Почтовый сервис мог принять письмо, но ответ не успел вернуться. Повтор временно закрыт, пока сервер проверяет результат.",
  manual_review: "Автоматическое восстановление остановлено. Случай требует ручной проверки руководителем.",
  invite_failed: "Почтовый сервис не подтвердил приглашение. Проверьте статус ниже перед новой попыткой.",
});

const ACCOUNT_STATE_COPY = Object.freeze({
  ready: "Готов к входу",
  recovery_required: "Нужно восстановление",
  invite_required: "Нужно приглашение",
  pending_delivery: "Письмо обрабатывается",
  disabled: "Доступ отключён",
  unknown: "Требуется проверка",
});

const MEMBERSHIP_STATUS_COPY = Object.freeze({
  active: "Активно",
  invited: "Приглашён",
  pending: "Ожидает активации",
  suspended: "Приостановлено",
  revoked: "Отозвано",
  disabled: "Отключено",
});

const REPAIR_BLOCKED_DELIVERY = new Set(["bounced", "complained", "failed", "suppressed"]);
const SAFE_ACCOUNT_STATES = new Set(Object.keys(ACCOUNT_STATE_COPY));
const SAFE_OUTCOMES = new Set(Object.keys(OUTCOME_COPY));
const SAFE_RECOMMENDATIONS = new Set(["none", "recovery", "invite", "wait", "manual_review"]);

export function ensureAccessCenterStyles() {
  if (typeof document === "undefined" || document.querySelector("link[data-access-center-styles]")) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = "./access-center.css?v=20260717.1";
  link.dataset.accessCenterStyles = "true";
  document.head.append(link);
}

export function normalizeAccessCenterEmail(value) {
  return String(value || "").trim().toLowerCase();
}

export function normalizeAccessCenterResult(raw, fallbackEmail = "") {
  const root = objectValue(raw?.data) || objectValue(raw) || {};
  const access = objectValue(root.access) || root;
  const membership = objectValue(access.membership) || {};
  const identity = objectValue(access.identity) || {};
  const delivery = objectValue(access.delivery) || {};
  const eventDeliveryStatus = normalizeDeliveryStatus(
    root.delivery_status || delivery.delivery_status || delivery.status,
  );
  // Dispatch failures and duplicate suppression are retryable server decisions,
  // not provider evidence about the recipient mailbox.  Only the normalized
  // delivery projection may permanently block automated repair.
  const deliveryStatus = eventDeliveryStatus;
  const accountState = safeEnum(access.account_state, SAFE_ACCOUNT_STATES, "unknown");
  const recommendedAction = safeEnum(access.recommended_action, SAFE_RECOMMENDATIONS, "manual_review");
  const outcome = safeEnum(root.outcome, SAFE_OUTCOMES, "");
  const email = normalizeAccessCenterEmail(root.email || access.email || fallbackEmail);

  return {
    email,
    accountState,
    recommendedAction,
    outcome,
    retryAfterSeconds: safePositiveInteger(root.retry_after_seconds),
    membership: {
      exists: membership.exists === true,
      status: safeToken(membership.status),
      role: safeToken(membership.role),
    },
    identity: {
      exists: identity.exists === true,
      emailConfirmed: identity.email_confirmed === true,
      disabled: identity.disabled === true,
      lastSignInAt: safeTimestamp(identity.last_sign_in_at),
    },
    delivery: {
      status: deliveryStatus,
      purpose: safeToken(delivery.purpose),
      requestedAt: safeTimestamp(delivery.requested_at),
      eventAt: safeTimestamp(delivery.event_at),
    },
    repairBlocked: REPAIR_BLOCKED_DELIVERY.has(deliveryStatus),
  };
}

export function accessCenterMarkup(viewState = {}) {
  const status = String(viewState.status || "idle");
  const record = viewState.result ? normalizeAccessCenterResult(viewState.result, viewState.email) : null;
  const email = normalizeAccessCenterEmail(viewState.email || record?.email || "");
  const busy = ["checking", "repairing"].includes(status);
  const blocked = record?.repairBlocked === true;
  const submitLabel = status === "checking"
    ? "Проверяем точный аккаунт…"
    : status === "repairing"
      ? "Восстанавливаем доступ…"
      : "Проверить и восстановить доступ";
  const statusText = status === "checking"
    ? `Проверяем аккаунт ${email || "по указанному адресу"}.`
    : status === "repairing"
      ? `Проверка завершена. Сервер выполняет допустимое восстановление для ${email}.`
      : String(viewState.notice || "");

  return `
    <section class="access-center" aria-labelledby="manager-access-title" data-access-center>
      <header class="access-center-head">
        <div>
          <p class="eyebrow">Точечное восстановление</p>
          <h2 id="manager-access-title">Центр доступа участника</h2>
          <p>Введите точный рабочий email. Портал сначала сверит Auth, членство и последнее письмо, а затем выполнит только допустимое сервером действие.</p>
        </div>
        <span class="access-center-safety">Без паролей и повторов вслепую</span>
      </header>
      <form id="manager-access-form" class="access-center-form" novalidate>
        <label class="field" for="manager-access-email">
          <span>Точный email участника *</span>
          <input
            id="manager-access-email"
            name="email"
            type="email"
            inputmode="email"
            autocomplete="off"
            maxlength="320"
            required
            value="${escapeHtml(email)}"
            aria-describedby="manager-access-help"
          />
        </label>
        <p id="manager-access-help" class="access-center-help">Адрес проверяется целиком. Портал не отправляет письмо, пока сервер не определит состояние доступа.</p>
        <button
          class="btn access-center-submit"
          type="submit"
          ${busy || blocked ? 'disabled aria-disabled="true"' : ""}
        >${escapeHtml(submitLabel)}</button>
        ${blocked ? `<button class="btn btn-secondary access-center-reset" type="button" data-action="reset-manager-access">Проверить другой email</button>` : ""}
      </form>
      <div class="access-center-live" role="status" aria-live="polite">${statusText ? escapeHtml(statusText) : ""}</div>
      ${viewState.error ? `<div class="access-center-alert access-center-alert-danger" role="alert">${escapeHtml(viewState.error)}</div>` : ""}
      ${record ? accessRecordMarkup(record) : initialStateMarkup()}
    </section>
  `;
}

function accessRecordMarkup(record) {
  const delivery = DELIVERY_META[record.delivery.status] || DELIVERY_META.unknown;
  const outcome = record.outcome ? OUTCOME_COPY[record.outcome] : "";
  const blockedCopy = record.repairBlocked
    ? `<div class="access-center-alert access-center-alert-danger" role="alert"><strong>Автоматический повтор запрещён.</strong> ${escapeHtml(delivery.detail)} Проверьте адрес с участником и разберите случай вручную.</div>`
    : "";
  const retryCopy = record.retryAfterSeconds
    ? ` Повтор будет доступен примерно через ${formatNumber(record.retryAfterSeconds)} сек.`
    : "";

  return `
    <article class="access-center-record" aria-labelledby="access-center-record-title">
      <div class="access-center-record-head">
        <div>
          <p class="eyebrow">Проверен точный адрес</p>
          <h3 id="access-center-record-title">${escapeHtml(record.email || "Email не определён")}</h3>
        </div>
        <span class="access-center-state">${escapeHtml(ACCOUNT_STATE_COPY[record.accountState] || ACCOUNT_STATE_COPY.unknown)}</span>
      </div>
      ${outcome ? `<div class="access-center-alert access-center-alert-info">${escapeHtml(outcome + retryCopy)}</div>` : ""}
      ${blockedCopy}
      <dl class="access-center-facts">
        <div>
          <dt>Учётная запись</dt>
          <dd>${record.identity.exists ? "Найдена" : "Не найдена"}</dd>
          <small>${identityDetail(record)}</small>
        </div>
        <div>
          <dt>Членство в команде</dt>
          <dd>${record.membership.exists ? membershipStatusLabel(record.membership.status) : "Не найдено"}</dd>
          <small>${record.membership.exists ? roleLabel(record.membership.role) : "Сервер проверит возможность безопасного подключения"}</small>
        </div>
        <div class="access-center-delivery access-center-delivery-${escapeHtml(delivery.tone)}">
          <dt>Последнее письмо</dt>
          <dd>${escapeHtml(delivery.label)}</dd>
          <small>${escapeHtml(delivery.detail)}</small>
        </div>
        <div>
          <dt>Последнее событие</dt>
          <dd>${escapeHtml(formatDateTime(record.delivery.eventAt || record.delivery.requestedAt))}</dd>
          <small>${escapeHtml(deliveryPurposeLabel(record.delivery.purpose))}</small>
        </div>
      </dl>
    </article>
  `;
}

function initialStateMarkup() {
  return `
    <div class="access-center-empty">
      <span aria-hidden="true">@</span>
      <div><strong>Начните с точного email</strong><p>Здесь появятся состояние учётной записи, членства и честный статус последнего письма.</p></div>
    </div>
  `;
}

function identityDetail(record) {
  if (!record.identity.exists) return "Сервер проверит возможность безопасного приглашения";
  if (record.identity.disabled) return "Вход отключён — требуется решение руководителя";
  if (!record.identity.emailConfirmed) return "Почта ещё не подтверждена";
  if (record.identity.lastSignInAt) return `Последний вход: ${formatDateTime(record.identity.lastSignInAt)}`;
  return "Почта подтверждена, первого входа ещё не было";
}

function membershipStatusLabel(status) {
  return MEMBERSHIP_STATUS_COPY[status] || "Статус требует проверки";
}

function roleLabel(role) {
  return {
    owner: "Руководитель",
    admin: "Администратор",
    producer: "Продюсер",
    reviewer: "Проверяющий",
    operator: "Оператор",
    trainee: "Стажёр",
    creator: "Креатор",
    viewer: "Наблюдатель",
  }[role] || "Роль определена сервером";
}

function deliveryPurposeLabel(purpose) {
  return {
    invite: "Приглашение",
    recovery: "Восстановление пароля",
    email_change: "Подтверждение почты",
  }[purpose] || "Тип письма не подтверждён";
}

function normalizeDeliveryStatus(value) {
  const normalized = safeToken(value);
  if (normalized === "delivered") return "delivered";
  if (normalized === "deferred") return "deferred";
  if (["bounced", "bounce"].includes(normalized)) return "bounced";
  if (["complained", "complaint"].includes(normalized)) return "complained";
  if (normalized === "failed") return "failed";
  if (normalized === "suppressed") return "suppressed";
  if (["accepted", "accepted_unconfirmed", "request_accepted", "invited"].includes(normalized)) return "accepted";
  return "unknown";
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function safeEnum(value, supported, fallback) {
  const normalized = safeToken(value);
  return supported.has(normalized) ? normalized : fallback;
}

function safeToken(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return /^[a-z0-9_.:-]{1,96}$/u.test(normalized) ? normalized : "";
}

function safeTimestamp(value) {
  const normalized = String(value || "").trim();
  const timestamp = Date.parse(normalized);
  return normalized && Number.isFinite(timestamp) ? normalized : "";
}

function safePositiveInteger(value) {
  const normalized = Number(value);
  return Number.isInteger(normalized) && normalized > 0 && normalized <= 86_400
    ? normalized
    : 0;
}

function formatDateTime(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "Событий пока нет";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatNumber(value) {
  return new Intl.NumberFormat("ru-RU").format(Math.max(0, Number(value) || 0));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
