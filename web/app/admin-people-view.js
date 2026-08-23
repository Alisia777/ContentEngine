const ADMIN_VIEWS = new Set(["people", "accounts"]);

const ROLE_LABELS = Object.freeze({
  owner: "Владелец",
  admin: "Администратор",
  producer: "Продюсер",
  reviewer: "Проверяющий",
  operator: "Оператор",
  trainee: "Стажёр",
  viewer: "Наблюдатель",
});

const STATUS_LABELS = Object.freeze({
  active: "Активен",
  suspended: "Приостановлен",
  revoked: "Удалён из команды",
  archived: "В архиве",
  invited: "Приглашение принято",
  already_exists: "Аккаунт подключён",
  pending_verification: "Нужно обновить",
  rate_limited: "Лимит отправки",
  smtp_required: "Почта не настроена",
  failed: "Ошибка",
});

const PLATFORM_LABELS = Object.freeze({
  instagram: "Instagram",
  youtube: "YouTube",
  vk: "VK",
  telegram: "Telegram",
  tiktok: "TikTok",
  wildberries: "Wildberries",
  ozon: "Ozon",
  rutube: "Rutube",
  other: "Другая площадка",
});

export const ADMIN_ACCOUNT_PLATFORMS = Object.freeze(
  Object.entries(PLATFORM_LABELS).map(([value, label]) => Object.freeze({ value, label })),
);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function text(value, fallback = "") {
  const normalized = String(value ?? "").trim();
  return normalized || fallback;
}

function finiteNumber(value, fallback = 0) {
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : fallback;
}

function optionalDate(value) {
  const normalized = text(value);
  return normalized && Number.isFinite(Date.parse(normalized)) ? normalized : "";
}

function safeExternalUrl(value) {
  const normalized = text(value);
  if (!normalized) return "";
  try {
    const parsed = new URL(normalized);
    return ["https:", "http:"].includes(parsed.protocol)
      && !parsed.username
      && !parsed.password
      ? parsed.href
      : "";
  } catch {
    return "";
  }
}

function normalizeAccount(value) {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  return Object.freeze({
    id: text(source.id || source.account_id),
    platform: text(source.platform, "other").toLowerCase(),
    label: text(source.label, "Аккаунт без названия"),
    handle: text(source.handle),
    url: safeExternalUrl(source.url),
    notes: text(source.notes),
    status: text(source.status, "active").toLowerCase(),
    createdAt: optionalDate(source.created_at),
    updatedAt: optionalDate(source.updated_at),
    assignedProfileId: text(source.assigned_profile_id),
    assignmentId: text(source.assignment_id),
    assignedAt: optionalDate(source.assigned_at),
    ownershipKind: text(source.ownership_kind, "personal_issued").toLowerCase(),
    custodianProfileId: text(source.custodian_profile_id),
    registrationEmailAlias: text(source.registration_email_alias),
    registrationPhoneRef: text(source.registration_phone_ref),
    externalAccountId: text(source.external_account_id),
    postingMode: text(source.posting_mode, "assisted").toLowerCase(),
    connectionStatus: text(source.connection_status, "not_connected").toLowerCase(),
  });
}

// Владение аккаунтом на площадке (фаза 0 контура авторазмещения). Вид владения
// говорит, какой механизм площадки гарантирует «ушедший оставляет аккаунт
// компании»; personal_issued — исключение, при уходе обязательна ротация пароля.
export const ADMIN_OWNERSHIP_KINDS = Object.freeze([
  Object.freeze({ value: "business_portfolio", label: "Бизнес-портфолио (Meta Business)" }),
  Object.freeze({ value: "brand_account", label: "Brand-аккаунт (YouTube)" }),
  Object.freeze({ value: "community", label: "Сообщество (VK)" }),
  Object.freeze({ value: "channel_bot", label: "Канал с ботом (Telegram)" }),
  Object.freeze({ value: "marketplace", label: "Кабинет продавца (Wildberries / Ozon)" }),
  Object.freeze({ value: "personal_issued", label: "Личный аккаунт, выданный сотруднику" }),
]);

const POSTING_MODE_LABELS = Object.freeze({
  api: "Через API (публикует воркер)",
  assisted: "Вручную с подсказкой",
  disabled: "Публикации закрыты",
});

const CONNECTION_STATUS_LABELS = Object.freeze({
  not_connected: "не подключён",
  connected: "подключён",
  expired: "подключение истекло",
  revoked: "подключение отозвано",
  error: "ошибка подключения",
});

function custodianOptions(snapshot, custodianProfileId = "") {
  const eligible = snapshot.members.filter((member) => (
    member.status === "active"
    && ["owner", "admin", "producer"].includes(member.role)
  ));
  return [
    `<option value="" ${custodianProfileId ? "" : "selected"}>Хранитель не назначен</option>`,
    ...eligible.map((member) => (
      `<option value="${escapeHtml(member.profileId)}" ${member.profileId === custodianProfileId ? "selected" : ""}>${escapeHtml(member.displayName || member.email)}</option>`
    )),
  ].join("");
}

function accountOwnershipForm(account, snapshot, disabled) {
  const apiAllowed = account.connectionStatus === "connected";
  return `
    <form class="admin-form admin-account-ownership-form" data-account-id="${escapeHtml(account.id)}" data-expected-updated-at="${escapeHtml(account.updatedAt)}">
      <p class="admin-action-note">Кто владеет аккаунтом на площадке и кто отвечает за восстановление. Секреты (пароли, коды, токены) сюда не вводятся.</p>
      <div class="admin-form-grid">
        <label><span>Вид владения</span><select name="ownership_kind">${ADMIN_OWNERSHIP_KINDS.map((item) => `<option value="${item.value}" ${item.value === account.ownershipKind ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}</select></label>
        <label><span>Хранитель</span><select name="custodian_profile_id">${custodianOptions(snapshot, account.custodianProfileId)}</select></label>
        <label><span>Почтовый алиас регистрации</span><input name="registration_email_alias" type="email" maxlength="120" value="${escapeHtml(account.registrationEmailAlias)}" placeholder="social+brand@company.ru" /></label>
        <label><span>Корпоративный номер (код из пула)</span><input name="registration_phone_ref" maxlength="40" value="${escapeHtml(account.registrationPhoneRef)}" placeholder="SIM-07" /></label>
        <label><span>ID у площадки</span><input name="external_account_id" maxlength="120" value="${escapeHtml(account.externalAccountId)}" placeholder="channelId / chat_id / ig-user-id" /></label>
        <label><span>Режим публикации</span><select name="posting_mode">${Object.entries(POSTING_MODE_LABELS).map(([value, label]) => `<option value="${value}" ${value === account.postingMode ? "selected" : ""} ${value === "api" && !apiAllowed ? "disabled" : ""}>${escapeHtml(label)}</option>`).join("")}</select></label>
      </div>
      <p class="admin-action-note">Подключение к публикации: <strong>${escapeHtml(CONNECTION_STATUS_LABELS[account.connectionStatus] || account.connectionStatus)}</strong>${apiAllowed ? "" : " — режим «через API» откроется после подключения."}</p>
      <button class="btn btn-secondary btn-small" type="submit" ${disabled}>Сохранить владение</button>
    </form>`;
}

function normalizeMember(value) {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  return Object.freeze({
    membershipId: text(source.membership_id),
    profileId: text(source.profile_id),
    email: text(source.email),
    displayName: text(source.display_name),
    role: text(source.role, "trainee").toLowerCase(),
    status: text(source.status, "active").toLowerCase(),
    joinedAt: optionalDate(source.joined_at),
    updatedAt: optionalDate(source.updated_at),
    authConfirmed: source.auth_confirmed === true,
    authActive: source.auth_active === true,
    coursesCompleted: Math.max(0, finiteNumber(source.courses_completed)),
    coursesRequired: Math.max(0, finiteNumber(source.courses_required, 4)),
    examPassed: source.exam_passed === true,
    accessWaiverActive: source.access_waiver_active === true,
    accessWaiverReason: text(source.access_waiver_reason),
    accounts: Object.freeze(
      (Array.isArray(source.accounts) ? source.accounts : []).map(normalizeAccount),
    ),
  });
}

export function normalizeAdminView(value) {
  const normalized = text(value, "people").toLowerCase();
  return ADMIN_VIEWS.has(normalized) ? normalized : "people";
}

export function normalizeAdminSnapshot(raw) {
  const source = raw?.data && typeof raw.data === "object" && !Array.isArray(raw.data)
    ? raw.data
    : raw && typeof raw === "object" && !Array.isArray(raw)
      ? raw
      : {};
  const members = (Array.isArray(source.members) ? source.members : []).map(normalizeMember);
  const accounts = (Array.isArray(source.accounts) ? source.accounts : []).map(normalizeAccount);
  return Object.freeze({
    ok: source.ok === true,
    organization: Object.freeze({
      id: text(source.organization?.id),
      name: text(source.organization?.name, "Команда"),
    }),
    actor: Object.freeze({
      profileId: text(source.actor?.profile_id),
      role: text(source.actor?.role).toLowerCase(),
    }),
    members: Object.freeze(members),
    accounts: Object.freeze(accounts),
  });
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role || "Не назначена";
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status || "Неизвестно";
}

function platformLabel(platform) {
  return PLATFORM_LABELS[platform] || platform || PLATFORM_LABELS.other;
}

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(value));
  } catch {
    return "—";
  }
}

function statusPill(status) {
  return `<span class="admin-status admin-status--${escapeHtml(status)}">${escapeHtml(statusLabel(status))}</span>`;
}

function identityPill(member) {
  if (!member.authActive) {
    return '<span class="admin-status admin-status--danger">Учётная запись отключена</span>';
  }
  if (!member.authConfirmed) {
    return '<span class="admin-status admin-status--warning">Email не подтверждён</span>';
  }
  return '<span class="admin-status admin-status--confirmed">Вход подтверждён</span>';
}

function accountChip(account) {
  const title = `${platformLabel(account.platform)} · ${account.label}`;
  return `<span class="admin-account-chip" title="${escapeHtml(title)}"><b>${escapeHtml(platformLabel(account.platform))}</b>${account.handle ? ` ${escapeHtml(account.handle)}` : ` ${escapeHtml(account.label)}`}</span>`;
}

function trainingSummary(member) {
  const progress = `${member.coursesCompleted}/${member.coursesRequired} курса`;
  if (member.examPassed) return `${escapeHtml(progress)} · экзамен сдан`;
  if (member.accessWaiverActive) {
    const reason = member.accessWaiverReason
      ? ` title="${escapeHtml(member.accessWaiverReason)}"`
      : "";
    return `${escapeHtml(progress)} · <span class="admin-waiver"${reason}>доступ по проверенному исключению</span>`;
  }
  return `${escapeHtml(progress)} · экзамен не сдан`;
}

function memberActions(member, actor, busyKey) {
  const protectedMember = member.profileId === actor.profileId
    || member.role === "owner"
    || (actor.role === "admin" && member.role === "admin");
  if (protectedMember) {
    const explanation = member.role === "owner"
      ? "Доступ владельца меняется только через отдельную процедуру передачи владения."
      : member.profileId === actor.profileId
        ? "Свой административный доступ меняет другой владелец."
        : "Доступ администратора может изменить только владелец.";
    return `<p class="admin-action-note">${explanation}</p>`;
  }
  if (member.status === "revoked") {
    return '<p class="admin-action-note">История сохранена. Возврат удалённого участника выполняется отдельным владельцем процесса.</p>';
  }
  const disabled = busyKey ? "disabled" : "";
  if (member.status === "suspended") {
    return `
      <form class="admin-inline-form admin-member-action-form" data-member-action="reactivate_member" data-profile-id="${escapeHtml(member.profileId)}">
        <label><span>Причина восстановления</span><input name="reason" required minlength="10" maxlength="500" placeholder="Например: сотрудник вернулся к работе" /></label>
        <button class="btn btn-small" type="submit" ${disabled}>Восстановить</button>
      </form>
      <details class="admin-danger-zone">
        <summary>Удалить из команды</summary>
        ${revokeMemberForm(member, disabled)}
      </details>`;
  }
  return `
    <details class="admin-action-details">
      <summary>Приостановить</summary>
      <form class="admin-inline-form admin-member-action-form" data-member-action="suspend_member" data-profile-id="${escapeHtml(member.profileId)}">
        <label><span>Причина</span><input name="reason" required minlength="10" maxlength="500" placeholder="Почему доступ временно закрывается" /></label>
        <button class="btn btn-secondary btn-small" type="submit" ${disabled}>Приостановить</button>
      </form>
    </details>
    <details class="admin-danger-zone">
      <summary>Удалить из команды</summary>
      ${revokeMemberForm(member, disabled)}
    </details>`;
}

function revokeMemberForm(member, disabled) {
  return `
    <form class="admin-inline-form admin-member-action-form" data-member-action="revoke_member" data-profile-id="${escapeHtml(member.profileId)}">
      <p>Будет отозвано членство и завершены активные привязки аккаунтов. Учебная и рабочая история останется.</p>
      <label><span>Причина удаления</span><input name="reason" required minlength="10" maxlength="500" placeholder="Укажите проверяемую причину" /></label>
      <label class="admin-confirm"><input name="confirm" type="checkbox" required /> <span>Понимаю, что обычное восстановление после удаления недоступно</span></label>
      <button class="btn btn-danger btn-small" type="submit" ${disabled}>Отозвать доступ</button>
    </form>`;
}

function peopleTable(snapshot, busyKey) {
  if (!snapshot.members.length) {
    return '<div class="admin-empty"><strong>В команде пока никого нет</strong><p>Добавьте первый рабочий email в форме выше.</p></div>';
  }
  return `
    <div class="admin-people-list">
      ${snapshot.members.map((member) => `
        <article class="admin-person" data-profile-id="${escapeHtml(member.profileId)}">
          <div class="admin-person__identity">
            <span class="admin-avatar" aria-hidden="true">${escapeHtml((member.displayName || member.email || "?").slice(0, 1).toUpperCase())}</span>
            <div>
              <h3>${escapeHtml(member.displayName || member.email || "Участник")}</h3>
              ${member.displayName && member.email ? `<a href="mailto:${escapeHtml(member.email)}">${escapeHtml(member.email)}</a>` : ""}
              <div class="admin-pill-row">${statusPill(member.status)}${identityPill(member)}<span class="admin-role">${escapeHtml(roleLabel(member.role))}</span></div>
            </div>
          </div>
          <dl class="admin-person__facts">
            <div><dt>Обучение</dt><dd>${trainingSummary(member)}</dd></div>
            <div><dt>В команде с</dt><dd>${escapeHtml(formatDate(member.joinedAt))}</dd></div>
            <div><dt>Рабочие аккаунты</dt><dd>${member.accounts.length ? member.accounts.map(accountChip).join("") : '<span class="admin-muted">Не закреплены</span>'}</dd></div>
          </dl>
          <div class="admin-person__actions">${memberActions(member, snapshot.actor, busyKey)}</div>
        </article>
      `).join("")}
    </div>`;
}

function invitePanel(inviteResult) {
  const rows = Array.isArray(inviteResult?.results) ? inviteResult.results : [];
  const reasonLabels = {
    invite_request_accepted: "Приглашение принято почтовым сервисом",
    existing_account_connected: "Существующий аккаунт подключён к команде",
    duplicate_request_suppressed: "Повтор подавлен; проверьте предыдущий запрос",
    invite_processing_started: "Запрос ещё обрабатывается",
    invite_processing_interrupted: "Обработка прервалась; обновите историю",
    membership_provision_failed: "Не удалось подготовить членство",
    membership_reconcile_failed: "Не удалось подключить существующий аккаунт",
    password_marker_failed: "Не удалось включить обязательную смену пароля",
    client_timeout: "Портал перестал ждать; итог нужно обновить с сервера",
  };
  return `
    <section class="admin-card admin-invite-card" aria-labelledby="admin-invite-title">
      <div>
        <p class="admin-kicker">Добавить человека</p>
        <h2 id="admin-invite-title">Пригласить по рабочей почте</h2>
        <p>Новый человек создаётся как стажёр. Рабочий допуск выдаёт сервер после подтверждённого обучения либо отдельного аудируемого исключения.</p>
      </div>
      <form id="admin-invite-form" class="admin-form">
        <label><span>Email — по одному на строку</span><textarea name="emails" rows="3" required maxlength="16000" spellcheck="false" autocomplete="off" placeholder="employee@company.ru"></textarea></label>
        <button class="btn" type="submit">Добавить и отправить приглашение</button>
      </form>
      ${rows.length ? `<details class="admin-invite-result"><summary>Последний сохранённый результат: ${rows.length}</summary><ul>${rows.map((row) => `<li><span>${escapeHtml(row.email || "—")}<small>${escapeHtml(reasonLabels[text(row.reason_code)] || text(row.reason_code, "Статус сохранён сервером"))}</small></span>${statusPill(text(row.status, "unknown"))}</li>`).join("")}</ul></details>` : ""}
    </section>`;
}

function peopleView(snapshot, busyKey, inviteResult) {
  const active = snapshot.members.filter((member) => member.status === "active").length;
  const suspended = snapshot.members.filter((member) => member.status === "suspended").length;
  const unconfirmed = snapshot.members.filter((member) => !member.authConfirmed).length;
  return `
    ${invitePanel(inviteResult)}
    <section class="admin-metrics" aria-label="Сводка команды">
      <div><span>Всего записей</span><strong>${snapshot.members.length}</strong></div>
      <div><span>Активны</span><strong>${active}</strong></div>
      <div><span>Приостановлены</span><strong>${suspended}</strong></div>
      <div><span>Email не подтверждён</span><strong>${unconfirmed}</strong></div>
    </section>
    <section class="admin-card" aria-labelledby="admin-people-title">
      <header class="admin-section-header"><div><p class="admin-kicker">Состав и доступ</p><h2 id="admin-people-title">Люди</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-admin-people" ${busyKey ? "disabled" : ""}>Обновить</button></header>
      ${peopleTable(snapshot, busyKey)}
    </section>`;
}

function memberOptions(snapshot, assignedProfileId = "") {
  const members = snapshot.members.filter((member) => (
    member.status === "active"
    && member.authActive
    && member.authConfirmed
    && (
      snapshot.actor.role === "owner"
      || !["owner", "admin"].includes(member.role)
    )
  ));
  const current = snapshot.members.find((member) => (
    member.profileId === assignedProfileId
    && !members.some((candidate) => candidate.profileId === member.profileId)
  ));
  const identityLabel = (member) => member.displayName
    ? `${member.displayName} · ${member.email}`
    : member.email;
  return [
    `<option value="" ${assignedProfileId ? "" : "selected"}>Не закреплён</option>`,
    ...(current ? [`<option value="${escapeHtml(current.profileId)}" selected>${escapeHtml(identityLabel(current))} · текущее назначение недоступно для новых привязок</option>`] : []),
    ...members.map((member) => `<option value="${escapeHtml(member.profileId)}" ${member.profileId === assignedProfileId ? "selected" : ""}>${escapeHtml(identityLabel(member))} · ${escapeHtml(roleLabel(member.role))}</option>`),
  ].join("");
}

function accountEditForm(account, disabled) {
  return `
    <form class="admin-form admin-account-edit-form" data-account-id="${escapeHtml(account.id)}" data-expected-updated-at="${escapeHtml(account.updatedAt)}">
      <div class="admin-form-grid">
        <label><span>Площадка</span><select name="platform" required>${ADMIN_ACCOUNT_PLATFORMS.map((item) => `<option value="${item.value}" ${item.value === account.platform ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("")}</select></label>
        <label><span>Название</span><input name="label" required minlength="2" maxlength="160" value="${escapeHtml(account.label)}" /></label>
        <label><span>Логин / @handle</span><input name="handle" maxlength="160" value="${escapeHtml(account.handle)}" /></label>
        <label><span>Публичная ссылка</span><input name="url" type="url" maxlength="500" value="${escapeHtml(account.url)}" /></label>
      </div>
      <label><span>Безопасная заметка</span><textarea name="notes" rows="2" maxlength="1000">${escapeHtml(account.notes)}</textarea></label>
      <button class="btn btn-secondary btn-small" type="submit" ${disabled}>Сохранить карточку</button>
    </form>`;
}

function accountCard(account, snapshot, busyKey) {
  const assignee = snapshot.members.find((member) => member.profileId === account.assignedProfileId);
  const disabled = busyKey ? "disabled" : "";
  const protectedAssignment = snapshot.actor.role === "admin"
    && assignee
    && ["owner", "admin"].includes(assignee.role);
  return `
    <article class="admin-account" data-account-id="${escapeHtml(account.id)}">
      <header>
        <div><span class="admin-platform">${escapeHtml(platformLabel(account.platform))}</span><h3>${escapeHtml(account.label)}</h3><p>${escapeHtml(account.handle || account.url || "Публичный идентификатор не указан")}</p></div>
        ${statusPill(account.status)}
      </header>
      ${account.url ? `<a class="admin-external-link" href="${escapeHtml(account.url)}" target="_blank" rel="noopener noreferrer">Открыть публичную страницу ↗</a>` : ""}
      ${account.notes ? `<p class="admin-account__notes">${escapeHtml(account.notes)}</p>` : ""}
      ${protectedAssignment ? `<p class="admin-action-note">Назначение руководителя может менять только владелец.</p>` : `<form class="admin-account-bind-form" data-account-id="${escapeHtml(account.id)}" data-current-profile-id="${escapeHtml(account.assignedProfileId)}">
        <label><span>Закреплён за сотрудником</span><select name="profile_id">${memberOptions(snapshot, account.assignedProfileId)}</select></label>
        <button class="btn btn-small" type="submit" ${disabled}>${account.assignedProfileId ? "Сохранить назначение" : "Закрепить"}</button>
      </form>`}
      <p class="admin-assignee-note">${assignee ? `Сейчас отвечает: <strong>${escapeHtml(assignee.displayName || assignee.email)}</strong>` : "Ответственный пока не назначен."}</p>
      ${protectedAssignment ? "" : `<div class="admin-account__actions">
        <details><summary>Изменить карточку</summary>${accountEditForm(account, disabled)}</details>
        <details><summary>Владение и хранитель</summary>${accountOwnershipForm(account, snapshot, disabled)}</details>
        <details class="admin-danger-zone"><summary>Архивировать аккаунт</summary>
          <form class="admin-inline-form admin-account-archive-form" data-account-id="${escapeHtml(account.id)}" data-expected-updated-at="${escapeHtml(account.updatedAt)}">
            <p>Аккаунт исчезнет из активной работы, а текущая привязка завершится. История сохранится.</p>
            <label><span>Причина</span><input name="reason" required minlength="10" maxlength="500" /></label>
            <label class="admin-confirm"><input name="confirm" type="checkbox" required /> <span>Подтверждаю архивирование</span></label>
            <button class="btn btn-danger btn-small" type="submit" ${disabled}>Архивировать</button>
          </form>
        </details>
      </div>`}
    </article>`;
}

function accountsView(snapshot, busyKey) {
  const activeAccounts = snapshot.accounts.filter((account) => account.status === "active");
  const assigned = activeAccounts.filter((account) => account.assignedProfileId).length;
  return `
    <section class="admin-card" aria-labelledby="admin-account-create-title">
      <div class="admin-section-header"><div><p class="admin-kicker">Новый рабочий аккаунт</p><h2 id="admin-account-create-title">Добавить площадку</h2><p>Сохраняются только публичные реквизиты и назначение. Пароли, cookies, коды 2FA и OAuth‑токены сюда вводить нельзя.</p></div></div>
      <form id="admin-account-create-form" class="admin-form">
        <div class="admin-form-grid">
          <label><span>Площадка *</span><select name="platform" required>${ADMIN_ACCOUNT_PLATFORMS.map((item) => `<option value="${item.value}">${escapeHtml(item.label)}</option>`).join("")}</select></label>
          <label><span>Название *</span><input name="label" required minlength="2" maxlength="160" placeholder="Основной Instagram бренда" /></label>
          <label><span>Логин / @handle</span><input name="handle" maxlength="160" placeholder="@brand" /></label>
          <label><span>Публичная ссылка</span><input name="url" type="url" maxlength="500" placeholder="https://…" /></label>
        </div>
        <label><span>Безопасная заметка</span><textarea name="notes" rows="2" maxlength="1000" placeholder="Что публикуем и для какого бренда. Без секретов."></textarea></label>
        <button class="btn" type="submit" ${busyKey ? "disabled" : ""}>Создать аккаунт</button>
      </form>
    </section>
    <section class="admin-metrics" aria-label="Сводка аккаунтов">
      <div><span>Активных аккаунтов</span><strong>${activeAccounts.length}</strong></div>
      <div><span>Закреплены</span><strong>${assigned}</strong></div>
      <div><span>Без ответственного</span><strong>${activeAccounts.length - assigned}</strong></div>
    </section>
    <section class="admin-card" aria-labelledby="admin-accounts-title">
      <header class="admin-section-header"><div><p class="admin-kicker">Реестр без секретов</p><h2 id="admin-accounts-title">Рабочие аккаунты</h2></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-admin-people" ${busyKey ? "disabled" : ""}>Обновить</button></header>
      <div class="admin-account-grid">${activeAccounts.length ? activeAccounts.map((account) => accountCard(account, snapshot, busyKey)).join("") : '<div class="admin-empty"><strong>Аккаунтов пока нет</strong><p>Создайте первую карточку площадки и закрепите её за сотрудником.</p></div>'}</div>
    </section>`;
}

export function adminPeopleMarkup({
  snapshot,
  status = "idle",
  error = "",
  notice = "",
  busyKey = "",
  view = "people",
  inviteResult = null,
  canOpenWorkspace = false,
} = {}) {
  const normalizedView = normalizeAdminView(view);
  const data = snapshot || normalizeAdminSnapshot(null);
  const body = !snapshot && ["idle", "loading"].includes(status)
    ? '<section class="admin-card admin-loading" role="status"><div class="loading-line" aria-hidden="true"><span></span></div><strong>Загружаем людей и рабочие аккаунты…</strong></section>'
    : !snapshot
      ? `<section class="admin-card admin-empty"><strong>Админка не загрузилась</strong><p>${escapeHtml(error || "Обновите данные и повторите попытку.")}</p><button class="btn" type="button" data-action="refresh-admin-people">Повторить</button></section>`
      : normalizedView === "accounts"
        ? accountsView(data, busyKey)
        : peopleView(data, busyKey, inviteResult);
  return `
    <div class="admin-shell" data-admin-view="${normalizedView}">
      <header class="admin-topbar">
        <a class="admin-brand" href="#/admin/people"><span aria-hidden="true">КИ</span><div><strong>ContentEngine</strong><small>Администрирование</small></div></a>
        <nav aria-label="Переходы"><a href="#/learn">Академия</a>${canOpenWorkspace ? '<a href="#/workspace/home">Рабочий стол</a>' : ""}<button class="btn btn-secondary btn-small" type="button" data-action="logout">Выйти</button></nav>
      </header>
      <main id="main-content" class="admin-main" tabindex="-1">
        <section class="admin-hero">
          <div><p class="admin-kicker">${escapeHtml(data.organization.name)}</p><h1>Люди и рабочие аккаунты</h1><p>Этот раздел доступен владельцу и администратору независимо от учебного допуска. Каждое изменение повторно проверяется сервером.</p></div>
          <span class="admin-actor">Вы вошли как ${escapeHtml(roleLabel(data.actor.role))}</span>
        </section>
        <nav class="admin-tabs" aria-label="Разделы администрирования">
          <a href="#/admin/people?view=people" class="${normalizedView === "people" ? "is-active" : ""}" ${normalizedView === "people" ? 'aria-current="page"' : ""}>Люди <span>${data.members.length}</span></a>
          <a href="#/admin/people?view=accounts" class="${normalizedView === "accounts" ? "is-active" : ""}" ${normalizedView === "accounts" ? 'aria-current="page"' : ""}>Рабочие аккаунты <span>${data.accounts.filter((account) => account.status === "active").length}</span></a>
        </nav>
        ${notice ? `<p class="admin-notice" role="status">${escapeHtml(notice)}</p>` : ""}
        ${error && snapshot ? `<p class="admin-error" role="alert">${escapeHtml(error)}</p>` : ""}
        ${busyKey ? '<p class="admin-busy" role="status">Сохраняем изменение на сервере…</p>' : ""}
        ${body}
      </main>
    </div>`;
}
