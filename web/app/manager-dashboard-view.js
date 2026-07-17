const STAGE_META = Object.freeze({
  email: Object.freeze({ label: "Письмо", icon: "@", tone: "warning" }),
  login: Object.freeze({ label: "Вход", icon: "→", tone: "warning" }),
  course: Object.freeze({ label: "Курс", icon: "1", tone: "info" }),
  exam: Object.freeze({ label: "Экзамен", icon: "✓", tone: "info" }),
  generation: Object.freeze({ label: "Генерация", icon: "✦", tone: "warning" }),
  task: Object.freeze({ label: "Задача", icon: "3", tone: "warning" }),
  publication: Object.freeze({ label: "Публикация", icon: "↗", tone: "warning" }),
  payout: Object.freeze({ label: "Выплата", icon: "₽", tone: "warning" }),
  access: Object.freeze({ label: "Доступ", icon: "!", tone: "danger" }),
  ready: Object.freeze({ label: "Готов", icon: "✓", tone: "success" }),
});

const REASON_COPY = Object.freeze({
  temporary_password_change_required: "Нужно заменить временный пароль",
  first_login_pending: "Ещё не было первого входа",
  courses_incomplete: "Не завершены обязательные курсы",
  final_exam_pending: "Курсы пройдены, экзамен ещё не сдан",
  generation_queued: "Запуск принят и ожидает обработки",
  generation_starting: "Проверяем запуск и возможное списание",
  generation_submitted: "Провайдер принял задачу",
  generation_processing: "Видео создаётся",
  generation_failed: "Генерация завершилась ошибкой",
  task_blocked: "Задача заблокирована",
  task_todo: "Задача ещё не начата",
  task_in_progress: "Задача находится в работе",
  task_submitted: "Результат задачи отправлен на проверку",
  task_review: "Задача ожидает решения проверяющего",
  placement_scheduled: "Публикация запланирована",
  placement_ready: "Ролик готов к публикации",
  placement_failed: "Публикация не подтверждена",
  payout_pending: "Начисление ожидает проверки",
  payout_approved_not_paid: "Начисление одобрено, перевод не отмечен",
  membership_suspended: "Доступ участника приостановлен",
  membership_revoked: "Доступ участника отозван",
  profile_suspended: "Профиль участника приостановлен",
  profile_disabled: "Профиль участника отключён",
  auth_user_banned: "Вход участника заблокирован в Auth",
  auth_user_deleted: "Учётная запись участника удалена из Auth",
  no_blocker: "Явных блокеров нет",
  provider_unavailable: "Сервис генерации временно недоступен",
  provider_configuration_error: "Сервис генерации требует настройки руководителем",
  provider_authentication_failed: "Сервис генерации не подтвердил доступ",
  provider_credits_unavailable: "Для генерации сейчас недоступен рабочий лимит",
  provider_rate_limited: "Сервис генерации временно ограничил частоту запросов",
  provider_request_rejected: "Сервис генерации отклонил запрос",
  provider_request_failed: "Не удалось передать запрос сервису генерации",
  provider_task_failed: "Сервис генерации не завершил задачу",
  provider_timeout: "Провайдер долго не ответил; повторный платный запуск не нужен",
  provider_failed: "Провайдер вернул ошибку",
  provider_response_invalid: "Сервис генерации вернул некорректный ответ",
  output_download_failed: "Не удалось безопасно сохранить готовый файл",
  output_validation_failed: "Готовый файл не прошёл проверку",
  output_upload_failed: "Не удалось сохранить готовый файл в рабочее хранилище",
  internal_error: "Внутренний статус требует проверки руководителем",
});

export function managerDashboardMarkup(payload = {}, operationalState = {}) {
  const summary = payload?.summary && typeof payload.summary === "object" ? payload.summary : {};
  const members = Array.isArray(payload?.members) ? payload.members : [];
  const pendingInvites = Array.isArray(payload?.pending_invites) ? payload.pending_invites : [];
  const stages = ["email", "login", "course", "exam", "generation", "task", "publication", "payout", "access", "ready"];
  const generatedAt = payload?.generated_at ? formatDateTime(payload.generated_at) : "ещё не обновлялась";

  return `
    <section class="manager-funnel" aria-labelledby="manager-funnel-title">
      <header class="manager-funnel-head">
        <div>
          <p class="eyebrow">Контроль без догадок</p>
          <h2 id="manager-funnel-title">Где команда остановилась сейчас</h2>
          <p>Статусы идут по реальному маршруту: письмо → вход → курс → экзамен → генерация → задача → публикация → выплата. Проблемы доступа вынесены отдельно.</p>
        </div>
        <div class="manager-funnel-refresh">
          <small>Сводка: ${escapeHtml(generatedAt)}</small>
          <button class="btn btn-secondary btn-small" type="button" data-action="refresh-manager-dashboard">Обновить</button>
        </div>
      </header>
      ${managerOperationalHealthMarkup(operationalState)}
      <div class="manager-stage-grid" aria-label="Количество участников на каждом этапе">
        ${stages.map((stage) => managerStageCard(stage, summary[stage])).join("")}
      </div>
      ${pendingInvites.length ? pendingInviteMarkup(pendingInvites) : ""}
      <div class="manager-queue-head">
        <div><p class="eyebrow">Участники</p><h3>Очередь внимания</h3></div>
        <span>${members.length ? `${formatNumber(members.length)} чел.` : "Нет данных"}</span>
      </div>
      ${members.length ? memberQueueMarkup(members) : `
        <div class="manager-empty"><span aria-hidden="true">◎</span><strong>Участников пока нет</strong><p>После приглашения и создания членства человек появится здесь.</p></div>
      `}
    </section>
  `;
}

export function managerOperationalHealthMarkup(state = {}) {
  const data = state?.data && typeof state.data === "object" ? state.data : {};
  const scheduler = data?.scheduler && typeof data.scheduler === "object" ? data.scheduler : {};
  const worker = data?.worker && typeof data.worker === "object" ? data.worker : {};
  const generation = data?.generation && typeof data.generation === "object" ? data.generation : {};
  const hasData = Boolean(state?.data && typeof state.data === "object");
  const loading = ["idle", "loading", "refreshing"].includes(String(state?.status || "idle"));
  const stalled = Math.max(0, Number(generation.stalled) || 0);
  const due = Math.max(0, Number(generation.due) || 0);
  const active = Math.max(0, Number(generation.active) || 0);
  const schedulerReady = scheduler.ready === true;
  const workerReady = worker.ready === true && worker.heartbeat_fresh === true;
  let tone = "neutral";
  let title = "Проверяем фоновую работу";
  let detail = "Сверяем расписание, последний сигнал обработчика и очередь генераций.";

  if (hasData) {
    if (!schedulerReady || !workerReady || stalled > 0) {
      tone = "danger";
      title = "Требуется внимание руководителя";
      detail = !schedulerReady
        ? "Фоновое расписание не подтвердило готовность. Откройте журнал развёртывания перед новыми платными запусками."
        : !workerReady
          ? "Обработчик давно не подтверждал работу. Уже отправленные Runway-задачи не запускайте повторно — сначала обновите состояние."
          : `${formatNumber(stalled)} генераций превысили безопасное время ожидания. Проверьте их статус без нового платного запуска.`;
    } else if (state.status === "error") {
      tone = "warning";
      title = "Показываем последнее подтверждённое состояние";
      detail = "Новое состояние не загрузилось за безопасное время. Данные ниже сохранены с предыдущей проверки.";
    } else if (state.status === "refreshing") {
      tone = "neutral";
      title = "Обновляем подтверждение";
      detail = "Последнее состояние остаётся на экране, пока сервер выполняет новую безопасную проверку.";
    } else if (due > 0 || active > 0) {
      tone = "warning";
      title = "Фоновая обработка идёт";
      detail = due > 0
        ? `${formatNumber(due)} задач готовы к очередной проверке провайдера.`
        : "Обработчик работает; часть задач ещё находится в очереди.";
    } else {
      tone = "success";
      title = "Фоновая работа в норме";
      detail = "Расписание и обработчик отвечают, зависших генераций нет.";
    }
  } else if (state?.status === "error") {
    tone = "warning";
    title = "Состояние пока не получено";
    detail = "Командная сводка доступна, но технический индикатор не ответил. Повторите безопасную проверку.";
  }

  const statusLabel = loading
    ? "Проверка"
    : tone === "success"
      ? "Работает"
      : tone === "danger"
        ? "Внимание"
        : "Наблюдаем";
  const heartbeat = hasData && worker.heartbeat_at
    ? formatDateTime(worker.heartbeat_at)
    : "нет свежего сигнала";

  return `
    <section class="manager-operations manager-operations-${tone}" aria-labelledby="manager-operations-title" aria-busy="${loading ? "true" : "false"}">
      <span class="sr-only" role="status" aria-live="polite">Фоновая работа: ${escapeHtml(statusLabel)}</span>
      <div class="manager-operations-copy">
        <span class="manager-operations-indicator" aria-hidden="true"></span>
        <div>
          <p class="eyebrow">Эксплуатация</p>
          <h3 id="manager-operations-title">${escapeHtml(title)}</h3>
          <p>${escapeHtml(detail)}</p>
        </div>
      </div>
      <div class="manager-operations-metrics" aria-label="Показатели фоновой обработки">
        <span><small>Статус</small><strong>${escapeHtml(statusLabel)}</strong></span>
        <span><small>Последний сигнал</small><strong>${escapeHtml(heartbeat)}</strong></span>
        <span><small>Активно</small><strong>${formatNumber(active)}</strong></span>
        <span><small>К проверке</small><strong>${formatNumber(due)}</strong></span>
        <span><small>Зависло</small><strong>${formatNumber(stalled)}</strong></span>
      </div>
      <button class="btn btn-secondary btn-small" type="button" data-action="refresh-manager-dashboard" ${loading ? "disabled" : ""}>Обновить состояние</button>
    </section>
  `;
}

function managerStageCard(stage, rawCount) {
  const meta = STAGE_META[stage] || STAGE_META.ready;
  const count = Math.max(0, Number(rawCount) || 0);
  return `
    <article class="manager-stage manager-stage-${escapeHtml(meta.tone)}">
      <span class="manager-stage-icon" aria-hidden="true">${escapeHtml(meta.icon)}</span>
      <span>${escapeHtml(meta.label)}</span>
      <strong>${formatNumber(count)}</strong>
    </article>
  `;
}

function pendingInviteMarkup(invites) {
  return `
    <section class="manager-invite-queue" aria-labelledby="manager-invite-title">
      <div class="manager-queue-head">
        <div><p class="eyebrow">До первого входа</p><h3 id="manager-invite-title">Письмо ещё не превратилось в аккаунт</h3></div>
        <span>${formatNumber(invites.length)}</span>
      </div>
      <div class="manager-invite-list">
        ${invites.map((invite) => {
          const canRetry = String(invite.safe_action || "") === "retry_invite";
          const accepted = invite.delivery_status === "accepted_unconfirmed";
          const status = accepted
            ? "Запрос принят почтовым сервисом, доставка не подтверждена"
            : reasonLabel(invite.reason_code);
          return `
            <article class="manager-invite-row">
              <div><strong>${escapeHtml(invite.email || "—")}</strong><small>${escapeHtml(status)}</small></div>
              <time datetime="${escapeHtml(invite.requested_at || "")}">${escapeHtml(formatDateTime(invite.requested_at))}</time>
              ${canRetry ? `<button class="btn btn-secondary btn-small" type="button" data-action="open-manager-access" data-email="${escapeHtml(invite.email || "")}">Проверить и восстановить доступ</button>` : ""}
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function memberQueueMarkup(members) {
  return `
    <div class="manager-member-list">
      ${members.map((member) => {
        const stage = String(member.stage || "ready");
        const meta = STAGE_META[stage] || STAGE_META.ready;
        const reason = reasonLabel(member.reason_code);
        const progress = stage === "course"
          ? `${formatNumber(member.courses_completed || 0)} из ${formatNumber(member.courses_required || 0)} курсов`
          : reason;
        return `
          <article class="manager-member-row" data-manager-stage="${escapeHtml(stage)}">
            <div class="manager-member-person">
              <span class="manager-person-avatar" aria-hidden="true">${escapeHtml(initials(member.display_name || member.email))}</span>
              <div><strong>${escapeHtml(member.display_name || member.email || "Участник")}</strong><small>${escapeHtml(member.email || "")}</small></div>
            </div>
            <div class="manager-member-stage"><span class="manager-stage-pill manager-stage-${escapeHtml(meta.tone)}">${escapeHtml(meta.label)}</span><small>${escapeHtml(progress)}</small></div>
            <div class="manager-member-time"><span>Последняя активность</span><time datetime="${escapeHtml(member.last_activity_at || "")}">${escapeHtml(formatDateTime(member.last_activity_at))}</time></div>
            <div class="manager-member-action">${safeActionMarkup(member)}</div>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function safeActionMarkup(member) {
  const action = String(member.safe_action || "none");
  if (action === "recovery") {
    return `<button class="btn btn-secondary btn-small" type="button" data-action="open-manager-access" data-email="${escapeHtml(member.email || "")}">Проверить и восстановить доступ</button>`;
  }
  if (action === "learn" || action === "exam") {
    const stage = action === "exam" ? "экзамен" : "обучение";
    return `<button class="btn btn-secondary btn-small" type="button" data-action="copy-manager-reminder" data-email="${escapeHtml(member.email || "")}" data-stage="${stage}">Скопировать напоминание</button>`;
  }
  if (action === "generation_status") {
    return `<a class="btn btn-secondary btn-small" href="#/workspace/generation">Проверить без нового запуска</a>`;
  }
  if (action === "task") {
    return `<a class="btn btn-secondary btn-small" href="#/workspace/tasks">Открыть задачи</a>`;
  }
  if (action === "placement") {
    return `<a class="btn btn-secondary btn-small" href="#/workspace/placement">Открыть публикации</a>`;
  }
  if (action === "payout") {
    return `<a class="btn btn-secondary btn-small" href="#/workspace/payouts">Открыть выплаты</a>`;
  }
  if (action === "team") {
    return `<span class="manager-no-action">Решение руководителя</span>`;
  }
  return `<span class="manager-no-action">Действий не требуется</span>`;
}

function reasonLabel(reasonCode) {
  const code = String(reasonCode || "no_blocker");
  return REASON_COPY[code] || "Статус требует проверки руководителем";
}

function initials(value) {
  const words = String(value || "У").trim().split(/\s+/u).filter(Boolean);
  return words.slice(0, 2).map((word) => word.slice(0, 1).toUpperCase()).join("") || "У";
}

function formatNumber(value) {
  return new Intl.NumberFormat("ru-RU").format(Math.max(0, Number(value) || 0));
}

function formatDateTime(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "нет активности";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
