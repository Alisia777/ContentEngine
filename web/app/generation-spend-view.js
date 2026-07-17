const BLOCKER_MESSAGES = Object.freeze({
  paid_generation_paused: "Платная генерация приостановлена руководителем.",
  paid_generation_policy_missing: "Для команды ещё не настроен безопасный денежный лимит.",
  generation_daily_budget_exceeded: "Дневной бюджет платной генерации исчерпан.",
  generation_monthly_budget_exceeded: "Месячный бюджет платной генерации исчерпан.",
  generation_per_request_budget_exceeded: "Цена этого запуска превышает лимит одной генерации.",
  generation_budget_reservation_invalid: "Сервер не подтвердил резерв денег для запуска.",
  generation_budget_policy_changed: "Лимиты изменились. Обновите остаток перед новым запуском.",
  generation_spend_platform_control_missing: "Общий защитный рубильник платной генерации не настроен.",
  generation_spend_platform_disabled: "Платная генерация остановлена общим защитным рубильником.",
  generation_spend_policy_missing: "Для команды ещё не настроен безопасный денежный лимит.",
  generation_spend_organization_disabled: "Платная генерация приостановлена руководителем.",
  generation_spend_daily_limit_exceeded: "Дневной бюджет платной генерации исчерпан.",
  generation_spend_monthly_limit_exceeded: "Месячный бюджет платной генерации исчерпан.",
  generation_spend_per_request_limit_exceeded: "Цена этого запуска превышает лимит одной генерации.",
  generation_spend_reservation_missing: "Сервер не подтвердил денежный резерв для запуска.",
  generation_spend_reservation_frozen: "Денежный резерв заморожен до ручной сверки запуска.",
  real_generation_reconciliation_required: "Новый платный запуск остановлен до ручной сверки предыдущего запроса.",
});

export function normalizeGenerationSpendOverview(value = {}) {
  const source = objectValue(value?.data) || objectValue(value) || {};
  const policySource = objectValue(source.policy) || {};
  const usageSource = objectValue(source.usage) || {};
  const daySource = objectValue(usageSource.day) || {};
  const monthSource = objectValue(usageSource.month) || {};
  const policyPresent = [
    "paid_generation_enabled",
    "daily_limit_minor",
    "monthly_limit_minor",
    "per_request_limit_minor",
    "version",
  ].some((key) => Object.prototype.hasOwnProperty.call(policySource, key));
  const policy = {
    present: policyPresent,
    paidGenerationEnabled: policySource.paid_generation_enabled === true,
    dailyLimitMinor: minorValue(policySource.daily_limit_minor),
    monthlyLimitMinor: minorValue(policySource.monthly_limit_minor),
    perRequestLimitMinor: minorValue(policySource.per_request_limit_minor),
    timezone: safeText(policySource.timezone) || "Europe/Moscow",
    version: nonNegativeInteger(policySource.version),
    reason: safeText(policySource.reason),
    updatedAt: safeText(policySource.updated_at),
    updatedBy: safeText(policySource.updated_by),
  };
  const day = normalizePeriod(daySource);
  const month = normalizePeriod(monthSource);
  const explicitBlocker = safeCode(source.blocker_code);
  const blockerCode = explicitBlocker
    || (policyPresent && !policy.paidGenerationEnabled ? "paid_generation_paused" : "")
    || (!policyPresent ? "paid_generation_policy_missing" : "");
  const campaigns = Array.isArray(source.campaigns)
    ? source.campaigns.map(normalizeCampaign).filter(Boolean)
    : [];

  return {
    ok: source.ok === true,
    organizationId: safeText(source.organization_id),
    currency: safeText(source.currency).toUpperCase() || "USD",
    blockerCode,
    blockerMessage: spendBlockerMessage(blockerCode),
    policy,
    day,
    month,
    campaigns,
  };
}

export function generationSpendAllowsMinor(value, requestMinor) {
  const overview = isNormalizedOverview(value) ? value : normalizeGenerationSpendOverview(value);
  const amount = minorValue(requestMinor);
  if (!overview.policy.present) return false;
  if (!overview.policy.paidGenerationEnabled || overview.blockerCode) return false;
  if (amount === null) return true;
  const limits = [
    overview.policy.perRequestLimitMinor,
    overview.day.remainingMinor,
    overview.month.remainingMinor,
  ];
  if (limits.some((item) => item === null)) return false;
  return limits.every((limit) => limit >= amount);
}

export function managerGenerationSpendMarkup(state = {}, { canEdit = false } = {}) {
  const hasData = Boolean(state?.data && typeof state.data === "object");
  const overview = normalizeGenerationSpendOverview(state?.data || {});
  const status = String(state?.status || "idle");
  const loading = ["idle", "loading", "refreshing"].includes(status);
  const saving = state?.saving === true;
  const staleError = status === "error";
  const trusted = status === "ready";
  const stateError = typeof state?.error === "string"
    ? state.error
    : state?.error
      ? "Не удалось обновить остаток. Показана последняя подтверждённая версия."
      : "";

  if (!hasData) {
    const message = staleError
      ? "Не удалось получить денежный контур. Платный запуск всё равно будет проверен сервером до обращения к провайдеру."
      : "Сверяем лимиты, зарезервированные суммы и подтверждённые расходы.";
    return `
      <section class="manager-spend manager-spend-loading" aria-labelledby="manager-spend-title" aria-busy="${loading ? "true" : "false"}">
        <div><p class="eyebrow">Денежный контур</p><h3 id="manager-spend-title">${staleError ? "Остаток временно не получен" : "Проверяем бюджет генерации"}</h3><p>${escapeHtml(message)}</p></div>
        <button class="btn btn-secondary btn-small" type="button" data-action="refresh-generation-spend" ${loading ? "disabled" : ""}>Проверить снова</button>
      </section>
    `;
  }

  const enabled = trusted && overview.policy.paidGenerationEnabled && !overview.blockerCode;
  const tone = trusted ? (enabled ? "success" : "danger") : "neutral";
  const title = staleError
    ? "Свежий остаток не подтверждён"
    : loading
      ? "Обновляем денежный контур"
      : enabled
        ? "Платные запуски разрешены"
        : "Платные запуски остановлены";
  const note = staleError
    ? "Последняя сводка сохранена только для справки. До успешного обновления менять лимиты и запускать платную генерацию нельзя."
    : loading
      ? "Пока идёт проверка, сохранённые значения показаны только для справки."
      : overview.blockerMessage
      || "Перед каждым запросом к Runway сервер атомарно резервирует сумму и повторно сверяет лимиты.";
  const controls = canEdit
    ? generationSpendPolicyForm(overview, { saving, disabled: !trusted || loading || staleError })
    : `<p class="manager-spend-readonly">Изменить рубильник и лимиты может только владелец или администратор команды.</p>`;
  const switchLabel = trusted ? (enabled ? "Включено" : "Пауза") : "Проверка";

  return `
    <section class="manager-spend manager-spend-${tone}" aria-labelledby="manager-spend-title" aria-busy="${loading || saving ? "true" : "false"}">
      <header class="manager-spend-head">
        <div>
          <p class="eyebrow">Денежный контур · ${escapeHtml(overview.currency)}</p>
          <h3 id="manager-spend-title">${escapeHtml(title)}</h3>
          <p>${escapeHtml(note)}</p>
        </div>
        <span class="manager-spend-switch" data-enabled="${trusted ? (enabled ? "true" : "false") : "unknown"}"><i aria-hidden="true"></i>${switchLabel}</span>
      </header>
      ${state?.notice ? `<p class="manager-spend-message manager-spend-message-success" role="status">${escapeHtml(state.notice)}</p>` : ""}
      ${stateError ? `<p class="manager-spend-message manager-spend-message-error" role="alert">${escapeHtml(stateError)}</p>` : ""}
      ${staleError ? `<p class="manager-spend-message" role="status">Ниже сохранена последняя подтверждённая сводка; обновление не удалось.</p>` : ""}
      <div class="manager-spend-periods">
        ${spendPeriodMarkup("Сегодня", overview.day, overview.policy.dailyLimitMinor)}
        ${spendPeriodMarkup("Этот месяц", overview.month, overview.policy.monthlyLimitMinor)}
        <div class="manager-spend-limit"><small>Один запуск</small><strong>${formatUsd(overview.policy.perRequestLimitMinor)}</strong><span>максимальный резерв</span></div>
      </div>
      ${controls}
      ${campaignSpendMarkup(overview.campaigns)}
      <footer class="manager-spend-foot">
        <span>Версия правил: ${formatInteger(overview.policy.version)}</span>
        <span>${overview.policy.updatedAt ? `Обновлено ${escapeHtml(formatDateTime(overview.policy.updatedAt))}` : "Правила ещё не изменялись"}</span>
        <button class="btn btn-secondary btn-small" type="button" data-action="refresh-generation-spend" ${loading || saving ? "disabled" : ""}>Обновить остаток</button>
      </footer>
    </section>
  `;
}

export function generationSpendSnapshotMarkup(state = {}, { requestMinor = null } = {}) {
  const hasData = Boolean(state?.data && typeof state.data === "object");
  const loading = ["idle", "loading", "refreshing"].includes(String(state?.status || "idle"));
  if (!hasData) {
    const failed = state?.status === "error";
    return `
      <aside class="generation-spend-snapshot generation-spend-snapshot-${failed ? "warning" : "neutral"}" aria-busy="${loading ? "true" : "false"}" role="status">
        <div><strong>${failed ? "Остаток не загрузился" : "Проверяем денежный лимит"}</strong><span>${failed ? "Сервер всё равно проверит бюджет до платного запроса; тестовый режим работает без списаний." : "Тестовые варианты доступны сразу и не расходуют бюджет."}</span></div>
        ${failed ? `<button class="btn btn-secondary btn-small" type="button" data-action="refresh-generation-spend">Повторить</button>` : ""}
      </aside>
    `;
  }

  const overview = normalizeGenerationSpendOverview(state.data);
  const stale = state?.status === "error";
  const allowed = !stale && generationSpendAllowsMinor(overview, requestMinor);
  const title = allowed ? "Денежный лимит подтверждён" : "Платный запуск сейчас недоступен";
  const message = stale
    ? "Не удалось подтвердить свежий остаток. Обновите сводку; до этого сервер не разрешит платный запрос."
    : overview.blockerMessage
    || (allowed
      ? "Сумма будет сначала зарезервирована, а затем предварительно учтена после приёма запроса провайдером."
      : "Для выбранной цены не хватает дневного, месячного или разового остатка. Тестовый режим остаётся доступен.");
  return `
    <aside class="generation-spend-snapshot generation-spend-snapshot-${allowed ? "success" : "danger"}" role="status">
      <div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span></div>
      <dl>
        <div><dt>Сегодня</dt><dd>${formatUsd(overview.day.remainingMinor)}</dd></div>
        <div><dt>Месяц</dt><dd>${formatUsd(overview.month.remainingMinor)}</dd></div>
        <div><dt>Один запуск</dt><dd>${formatUsd(overview.policy.perRequestLimitMinor)}</dd></div>
      </dl>
    </aside>
  `;
}

export function spendBlockerMessage(code) {
  const normalized = safeCode(code);
  return BLOCKER_MESSAGES[normalized] || (normalized ? "Денежный контур остановил платный запуск. Обновите сводку или обратитесь к руководителю." : "");
}

function generationSpendPolicyForm(overview, { saving, disabled = false }) {
  const enabled = overview.policy.paidGenerationEnabled;
  return `
    <form id="generation-spend-policy-form" class="manager-spend-form" novalidate>
      <input type="hidden" name="expected_version" value="${escapeHtml(String(overview.policy.version))}" />
      <input type="hidden" name="timezone" value="${escapeHtml(overview.policy.timezone)}" />
      <fieldset ${saving || disabled ? "disabled" : ""}>
        <legend>Лимиты платной генерации</legend>
        <div class="manager-spend-form-grid">
          ${moneyField("daily_limit_usd", "На день, $", overview.policy.dailyLimitMinor)}
          ${moneyField("monthly_limit_usd", "На месяц, $", overview.policy.monthlyLimitMinor)}
          ${moneyField("per_request_limit_usd", "На один запуск, $", overview.policy.perRequestLimitMinor)}
        </div>
        <label class="field manager-spend-reason"><span>Причина изменения *</span><textarea name="reason" required minlength="10" maxlength="500" placeholder="Например: утверждён бюджет кампании на неделю"></textarea><small class="field-hint">Причина попадёт в журнал. Пароли и платёжные реквизиты сюда не добавляют.</small></label>
        <div class="manager-spend-actions">
          <button class="btn btn-small" type="submit" name="policy_action" value="save">${saving ? "Сохраняем…" : "Сохранить лимиты"}</button>
          ${enabled
            ? `<button class="btn btn-danger btn-small" type="submit" name="policy_action" value="pause">Приостановить платные запуски</button>`
            : `<button class="btn btn-small" type="submit" name="policy_action" value="resume">Включить платные запуски</button>`}
        </div>
      </fieldset>
    </form>
  `;
}

function moneyField(name, label, minor) {
  const value = minor === null ? "" : (minor / 100).toFixed(2);
  return `<label class="field"><span>${escapeHtml(label)}</span><input name="${escapeHtml(name)}" type="number" min="0.01" max="1000000" step="0.01" value="${escapeHtml(value)}" required inputmode="decimal" /></label>`;
}

function spendPeriodMarkup(label, period, limitMinor) {
  const committed = period.committedMinor;
  const reserved = period.reservedMinor;
  return `
    <article class="manager-spend-period">
      <div><small>${escapeHtml(label)}</small><strong>${formatUsd(period.remainingMinor)}</strong><span>доступно из ${formatUsd(limitMinor)}</span></div>
      <dl>
        <div><dt>Предварительно учтено</dt><dd>${formatUsd(committed)}</dd></div>
        <div><dt>Зарезервировано</dt><dd>${formatUsd(reserved)}</dd></div>
      </dl>
    </article>
  `;
}

function campaignSpendMarkup(campaigns) {
  if (!campaigns.length) return "";
  return `
    <section class="manager-spend-campaigns" aria-labelledby="manager-spend-campaigns-title">
      <div><p class="eyebrow">Кампании</p><h4 id="manager-spend-campaigns-title">Отдельные лимиты</h4></div>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Кампания</th><th>Статус</th><th>Учтено</th><th>Резерв</th><th>Остаток</th></tr></thead><tbody>
        ${campaigns.map((item) => `<tr><td><strong>${escapeHtml(item.name || item.productName || "Кампания")}</strong>${item.sku ? `<br /><small>${escapeHtml(item.sku)}</small>` : ""}</td><td>${item.enabled ? "Работает" : "Пауза"}</td><td>${formatUsd(item.committedMinor)}</td><td>${formatUsd(item.reservedMinor)}</td><td>${formatUsd(item.remainingMinor)}</td></tr>`).join("")}
      </tbody></table></div>
    </section>
  `;
}

function normalizePeriod(value) {
  return {
    periodStart: safeText(value.period_start),
    periodEnd: safeText(value.period_end),
    reservedMinor: minorValue(value.reserved_minor) ?? 0,
    committedMinor: minorValue(value.committed_minor ?? value.settled_minor) ?? 0,
    remainingMinor: minorValue(value.remaining_minor),
  };
}

function normalizeCampaign(value) {
  const source = objectValue(value);
  if (!source) return null;
  return {
    id: safeText(source.id || source.campaign_id),
    name: safeText(source.name || source.campaign_name),
    productName: safeText(source.product_name),
    sku: safeText(source.sku),
    enabled: source.enabled === true || source.status === "active",
    committedMinor: minorValue(source.committed_minor ?? source.settled_minor) ?? 0,
    reservedMinor: minorValue(source.reserved_minor) ?? 0,
    remainingMinor: minorValue(source.remaining_minor),
  };
}

function minorValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function nonNegativeInteger(value) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : 0;
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function isNormalizedOverview(value) {
  return Boolean(value?.policy && Object.prototype.hasOwnProperty.call(value.policy, "paidGenerationEnabled"));
}

function safeText(value) {
  return String(value ?? "").trim().slice(0, 500);
}

function safeCode(value) {
  const code = safeText(value).toLowerCase();
  return /^[a-z0-9_]{3,96}$/u.test(code) ? code : "";
}

function formatUsd(minor) {
  return minor === null || minor === undefined
    ? "—"
    : new Intl.NumberFormat("ru-RU", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(Number(minor) / 100);
}

function formatInteger(value) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Number(value) || 0);
}

function formatDateTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(date);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
