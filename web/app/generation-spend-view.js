const BLOCKER_MESSAGES = Object.freeze({
  paid_generation_paused: "Платная генерация приостановлена руководителем.",
  paid_generation_policy_missing: "Для команды ещё не настроен безопасный денежный лимит.",
  generation_daily_budget_exceeded: "Дневной бюджет платной генерации исчерпан.",
  generation_monthly_budget_exceeded: "Месячный бюджет платной генерации исчерпан.",
  generation_per_request_budget_exceeded: "Цена этого запуска превышает лимит одной генерации.",
  generation_budget_reservation_invalid: "Сервер не подтвердил резерв денег для запуска.",
  generation_budget_policy_changed: "Лимиты изменились. Обновите остаток перед новым запуском.",
  paid_generation_campaign_required: "Выберите кампанию, из бюджета которой будет оплачен ролик.",
  paid_generation_campaign_not_active: "Выбранная кампания не активна. Выберите другую или обратитесь к руководителю.",
  paid_generation_campaign_policy_missing: "Для выбранной кампании ещё не настроен денежный лимит.",
  paid_generation_campaign_paused: "Платные запуски в этой кампании приостановлены.",
  generation_campaign_per_request_budget_exceeded: "Цена ролика превышает разовый лимит выбранной кампании.",
  generation_campaign_daily_budget_exceeded: "Дневной бюджет выбранной кампании исчерпан.",
  generation_campaign_monthly_budget_exceeded: "Месячный бюджет выбранной кампании исчерпан.",
  generation_campaign_budget_policy_changed: "Лимит кампании изменился. Обновите остаток и повторите запуск.",
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
  const policyFieldsPresent = [
    "paid_generation_enabled",
    "daily_limit_minor",
    "monthly_limit_minor",
    "per_request_limit_minor",
    "version",
  ].every((key) => Object.prototype.hasOwnProperty.call(policySource, key));
  const policy = {
    present: false,
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
  const policyPresent = policyFieldsPresent
    && policy.dailyLimitMinor !== null
    && policy.monthlyLimitMinor !== null
    && policy.perRequestLimitMinor !== null
    && policy.version > 0;
  policy.present = policyPresent;
  const day = normalizePeriod(daySource);
  const month = normalizePeriod(monthSource);
  const explicitBlocker = safeCode(source.blocker_code);
  const blockerCode = explicitBlocker
    || (policyPresent && !policy.paidGenerationEnabled ? "paid_generation_paused" : "")
    || (!policyPresent ? "paid_generation_policy_missing" : "");
  const campaigns = Array.isArray(source.campaigns)
    ? source.campaigns.map(normalizeCampaign).filter(Boolean)
    : [];
  // «Потрачено на брак»: срез по failed-нарядам приезжает тем же RPC
  // (обёртка generation-failed-spend-v1); отсутствие ключа — старый сервер.
  const failedSource = objectValue(source.failed_spend) || {};
  const failedSpend = {
    present: failedSource.version === "generation-failed-spend-v1",
    dayMinor: minorValue(failedSource.day_minor),
    monthMinor: minorValue(failedSource.month_minor),
    allTimeMinor: minorValue(failedSource.all_time_minor),
    sharePercent: Number.isFinite(Number(failedSource.share_percent))
      ? Number(failedSource.share_percent)
      : null,
  };

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
    failedSpend,
  };
}

export function generationCampaignSelectionState(value = {}, {
  status = "ready",
  currentCampaignId = "",
  preferredCampaignId = "",
  requiresExplicitSelection = false,
} = {}) {
  const overview = isNormalizedOverview(value)
    ? value
    : normalizeGenerationSpendOverview(value);
  const trusted = status === "ready"
    && overview.ok === true
    && overview.policy.present === true
    && Number.isSafeInteger(overview.day.remainingMinor)
    && Number.isSafeInteger(overview.month.remainingMinor);
  const idCounts = new Map();
  if (trusted) {
    for (const campaign of overview.campaigns) {
      const id = campaignIdValue(campaign?.id);
      if (id) idCounts.set(id, (idCounts.get(id) || 0) + 1);
    }
  }
  const campaigns = trusted
    ? overview.campaigns.filter((campaign) => {
        const id = campaignIdValue(campaign?.id);
        return Boolean(
          id
          && idCounts.get(id) === 1
          && campaign.enabled === true
          && !campaign.blockerCode,
        );
      })
    : [];
  const currentId = campaignIdValue(currentCampaignId);
  const preferredId = campaignIdValue(preferredCampaignId);
  const hasCurrentSelection = Boolean(safeText(currentCampaignId));
  const hasPreferredSelection = Boolean(safeText(preferredCampaignId));
  let selectedId = "";
  if (requiresExplicitSelection === true) {
    selectedId = "";
  } else if (hasPreferredSelection) {
    selectedId = campaigns.find((campaign) => campaign.id === preferredId)?.id || "";
  } else if (hasCurrentSelection) {
    selectedId = campaigns.find((campaign) => campaign.id === currentId)?.id || "";
  } else {
    selectedId = campaigns[0]?.id || "";
  }
  return {
    ready: trusted,
    campaigns,
    selectedId,
    selectionChanged: selectedId !== currentId,
    explicitSelectionRejected: Boolean(
      requiresExplicitSelection === true
      || ((hasPreferredSelection || hasCurrentSelection) && !selectedId),
    ),
    preferredSelectionResolved: Boolean(
      preferredId && selectedId === preferredId,
    ),
  };
}

export function generationSpendAllowsMinor(value, requestMinor, campaignId = "") {
  const overview = isNormalizedOverview(value) ? value : normalizeGenerationSpendOverview(value);
  const amount = minorValue(requestMinor);
  if (overview.ok !== true) return false;
  if (!overview.policy.present) return false;
  if (!overview.policy.paidGenerationEnabled || overview.blockerCode) return false;
  if (amount === null) return false;
  const limits = [
    overview.policy.perRequestLimitMinor,
    overview.day.remainingMinor,
    overview.month.remainingMinor,
  ];
  if (limits.some((item) => item === null)) return false;
  if (!limits.every((limit) => limit >= amount)) return false;
  if (!overview.campaigns.length) return false;
  const normalizedCampaignId = campaignIdValue(campaignId);
  const campaign = overview.campaigns.find((item) => item.id === normalizedCampaignId);
  if (overview.campaigns.filter(
    (item) => item.id === normalizedCampaignId,
  ).length !== 1) return false;
  if (!campaign || !campaign.enabled || campaign.blockerCode) return false;
  const campaignLimits = [
    campaign.policy.perRequestLimitMinor,
    campaign.day.remainingMinor,
    campaign.month.remainingMinor,
  ];
  if (campaignLimits.some((item) => item === null)) return false;
  return campaignLimits.every((limit) => limit >= amount);
}

export function managerGenerationSpendMarkup(state = {}, {
  canEdit = false,
  view = "policy",
  campaignId = "",
} = {}) {
  const spendView = ["policy", "campaigns", "campaign", "new-campaign"].includes(view)
    ? view
    : "policy";
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
      || "Перед каждым платным запросом к провайдеру сервер атомарно резервирует сумму и повторно сверяет лимиты.";
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
        ${overview.failedSpend?.present ? `
          <div class="manager-spend-limit"><small>Потрачено на брак</small><strong>${formatUsd(overview.failedSpend.monthMinor ?? 0)}</strong><span>за месяц · всего ${formatUsd(overview.failedSpend.allTimeMinor ?? 0)}${overview.failedSpend.sharePercent !== null ? ` (${escapeHtml(String(overview.failedSpend.sharePercent))}% всех трат)` : ""}</span></div>
        ` : ""}
      </div>
      ${spendView === "policy" ? controls : ""}
      ${spendView === "policy" ? "" : campaignSpendMarkup(overview, {
        canEdit,
        saving,
        disabled: !trusted || loading || staleError,
        mode: spendView,
        campaignId,
      })}
      <footer class="manager-spend-foot">
        <span>Версия правил: ${formatInteger(overview.policy.version)}</span>
        <span>${overview.policy.updatedAt ? `Обновлено ${escapeHtml(formatDateTime(overview.policy.updatedAt))}` : "Правила ещё не изменялись"}</span>
        <button class="btn btn-secondary btn-small" type="button" data-action="refresh-generation-spend" ${loading || saving ? "disabled" : ""}>Обновить остаток</button>
      </footer>
    </section>
  `;
}

export function generationSpendSnapshotMarkup(state = {}, { requestMinor = null, campaignId = "" } = {}) {
  const hasData = Boolean(state?.data && typeof state.data === "object");
  const loading = ["idle", "loading", "refreshing"].includes(String(state?.status || "idle"));
  if (!hasData) {
    const failed = state?.status === "error";
    return `
      <aside class="generation-spend-snapshot generation-spend-snapshot-${failed ? "warning" : "neutral"}" aria-busy="${loading ? "true" : "false"}" role="status">
        <div><strong>${failed ? "Остаток не загрузился" : "Проверяем денежный лимит"}</strong><span>${failed ? "Сервер всё равно проверит бюджет до платного запроса; dry-run задач работает без файлов и списаний." : "Dry-run задач доступен сразу, не создаёт медиафайлы и не расходует бюджет."}</span></div>
        ${failed ? `<button class="btn btn-secondary btn-small" type="button" data-action="refresh-generation-spend">Повторить</button>` : ""}
      </aside>
    `;
  }

  const overview = normalizeGenerationSpendOverview(state.data);
  const stale = state?.status === "error";
  const estimateMissing = requestMinor === null || requestMinor === undefined;
  if (!stale && estimateMissing) {
    return `
      <aside class="generation-spend-snapshot generation-spend-snapshot-neutral" role="status">
        <div><strong>Стоимость ещё не подтверждена</strong><span>Выберите модель и параметры, затем выполните бесплатную серверную проверку. Остаток не разрешает платный запуск без точной цены.</span></div>
        <dl>
          <div><dt>Сегодня</dt><dd>${formatUsd(overview.day.remainingMinor)}</dd></div>
          <div><dt>Месяц</dt><dd>${formatUsd(overview.month.remainingMinor)}</dd></div>
          <div><dt>Один запуск</dt><dd>${formatUsd(overview.policy.perRequestLimitMinor)}</dd></div>
        </dl>
      </aside>
    `;
  }
  const allowed = !stale && generationSpendAllowsMinor(overview, requestMinor, campaignId);
  const selectedCampaign = overview.campaigns.find((campaign) => campaign.id === safeText(campaignId));
  const campaignMessage = !safeText(campaignId)
    ? "Для платного запуска нужна активная кампания с отдельным бюджетом."
    : !selectedCampaign
      ? "Выбранная кампания больше недоступна. Обновите сводку и выберите другую."
      : selectedCampaign.blockerCode
        ? spendBlockerMessage(selectedCampaign.blockerCode)
        : "";
  const title = allowed ? "Денежный лимит подтверждён" : "Платный запуск сейчас недоступен";
  const message = stale
    ? "Не удалось подтвердить свежий остаток. Обновите сводку; до этого сервер не разрешит платный запрос."
    : overview.blockerMessage
    || campaignMessage
    || (allowed
      ? "Сумма будет сначала зарезервирована, а затем предварительно учтена после приёма запроса провайдером."
      : "Для выбранной цены не хватает дневного, месячного или разового остатка. Dry-run задач без файлов остаётся доступен.");
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
          <button class="btn btn-small" type="submit" name="policy_action" value="save" data-primary-action="true">${saving ? "Сохраняем…" : "Сохранить лимиты"}</button>
          ${enabled
            ? `<button class="btn btn-danger btn-small" type="submit" name="policy_action" value="pause">Приостановить платные запуски</button>`
            : `<button class="btn btn-secondary btn-small" type="submit" name="policy_action" value="resume">Включить платные запуски</button>`}
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

function campaignSpendMarkup(overview, {
  canEdit = false,
  saving = false,
  disabled = false,
  mode = "campaigns",
  campaignId = "",
} = {}) {
  const campaigns = overview.campaigns;
  const selectedCampaign = campaigns.find((campaign) => campaign.id === safeText(campaignId)) || null;
  if (!campaigns.length && !canEdit) return "";
  const campaignControlsDisabled = disabled || !overview.policy.present;
  const createForm = canEdit && mode === "new-campaign"
    ? generationCampaignCreateForm(overview, { saving, disabled: campaignControlsDisabled })
    : "";
  return `
    <section class="manager-spend-campaigns" aria-labelledby="manager-spend-campaigns-title">
      <div><p class="eyebrow">Кампании</p><h4 id="manager-spend-campaigns-title">Отдельные лимиты</h4><p class="manager-spend-campaign-copy">Каждый платный ролик списывается из выбранной кампании. Лимит кампании не может быть выше общего лимита команды.</p></div>
      ${mode === "campaigns" && campaigns.length ? `
        <div class="table-wrap"><table class="data-table"><thead><tr><th>Кампания</th><th>Статус</th><th>Учтено</th><th>Резерв</th><th>Остаток</th></tr></thead><tbody>
          ${campaigns.map((item) => `<tr data-campaign-id="${escapeHtml(item.id)}"><td><a href="#/workspace/team?view=campaign&campaign=${encodeURIComponent(item.id)}"><strong>${escapeHtml(item.name || item.productName || "Кампания")}</strong></a>${item.kind === "default" ? `<br /><small>Основная для команды</small>` : ""}</td><td>${item.enabled ? "Работает" : "Пауза"}</td><td>${formatUsd(item.committedMinor)}</td><td>${formatUsd(item.reservedMinor)}</td><td>${formatUsd(item.remainingMinor)}</td></tr>`).join("")}
        </tbody></table></div>
      ` : mode === "campaigns" ? `<p class="manager-spend-message manager-spend-message-error" role="alert">Активных кампаний пока нет. До создания кампании платные запуски закрыты.</p>` : ""}
      ${canEdit && !overview.policy.present ? `<p class="manager-spend-message" role="status">Сначала сохраните общий бюджет команды. После этого можно создавать и настраивать кампании.</p>` : ""}
      ${canEdit && mode === "campaign" && selectedCampaign ? `<div class="manager-spend-campaign-editors">${generationCampaignPolicyForm(selectedCampaign, { saving, disabled: campaignControlsDisabled })}</div>` : ""}
      ${mode === "campaign" && selectedCampaign ? `
        <div class="inline-actions" style="margin-top:12px">
          <button class="btn btn-secondary btn-small" type="button" data-action="open-client-review-issue" data-campaign-id="${escapeHtml(selectedCampaign.id)}" data-campaign-name="${escapeHtml(selectedCampaign.name || "Кампания")}">Ссылка клиенту · витрина согласования</button>
          <button class="btn btn-ghost btn-small" type="button" data-action="open-client-review-links" data-campaign-id="${escapeHtml(selectedCampaign.id)}" data-campaign-name="${escapeHtml(selectedCampaign.name || "Кампания")}">Ссылки и решения клиента</button>
        </div>
      ` : ""}
      ${mode === "campaign" && !selectedCampaign ? `<p class="manager-spend-message manager-spend-message-error" role="alert">Кампания не найдена. Вернитесь в список и выберите доступную запись.</p>` : ""}
      ${createForm}
    </section>
  `;
}

function generationCampaignPolicyForm(campaign, { saving = false, disabled = false } = {}) {
  const enabled = campaign.policy.paidGenerationEnabled && campaign.status === "active";
  return `
    <details class="manager-spend-campaign-editor">
      <summary><span><strong>${escapeHtml(campaign.name || "Кампания")}</strong><small>${enabled ? "Платные запуски включены" : "Платные запуски на паузе"}</small></span><span>${formatUsd(campaign.month.remainingMinor)} на месяц</span></summary>
      <form class="manager-spend-form generation-campaign-policy-form" data-campaign-id="${escapeHtml(campaign.id)}" novalidate>
        <input type="hidden" name="expected_version" value="${escapeHtml(String(campaign.policy.version))}" />
        <fieldset ${saving || disabled ? "disabled" : ""}>
          <legend>Бюджет кампании «${escapeHtml(campaign.name || "Кампания")}»</legend>
          <div class="manager-spend-form-grid">
            ${moneyField("daily_limit_usd", "На день, $", campaign.policy.dailyLimitMinor)}
            ${moneyField("monthly_limit_usd", "На месяц, $", campaign.policy.monthlyLimitMinor)}
            ${moneyField("per_request_limit_usd", "На один запуск, $", campaign.policy.perRequestLimitMinor)}
          </div>
          <label class="field manager-spend-reason"><span>Причина изменения *</span><textarea name="reason" required minlength="8" maxlength="500" placeholder="Например: бюджет роликов товара на эту неделю"></textarea></label>
          <div class="manager-spend-actions">
            <button class="btn btn-small" type="submit" name="campaign_policy_action" value="save" data-primary-action="true">Сохранить бюджет</button>
            ${enabled
              ? `<button class="btn btn-danger btn-small" type="submit" name="campaign_policy_action" value="pause">Поставить кампанию на паузу</button>`
              : `<button class="btn btn-secondary btn-small" type="submit" name="campaign_policy_action" value="resume">Включить кампанию</button>`}
          </div>
        </fieldset>
      </form>
    </details>
  `;
}

function generationCampaignCreateForm(overview, { saving = false, disabled = false } = {}) {
  return `
    <details class="manager-spend-campaign-create" open>
      <summary><strong>+ Создать кампанию для нового товара или проекта</strong></summary>
      <form id="generation-campaign-create-form" class="manager-spend-form" novalidate>
        <fieldset ${saving || disabled ? "disabled" : ""}>
          <legend>Новая кампания</legend>
          <label class="field"><span>Название *</span><input name="campaign_name" required minlength="2" maxlength="160" autocomplete="off" placeholder="Например: Кровавый пилинг · июль" /></label>
          <div class="manager-spend-form-grid">
            ${moneyField("daily_limit_usd", "На день, $", overview.policy.dailyLimitMinor)}
            ${moneyField("monthly_limit_usd", "На месяц, $", overview.policy.monthlyLimitMinor)}
            ${moneyField("per_request_limit_usd", "На один запуск, $", overview.policy.perRequestLimitMinor)}
          </div>
          <label class="field manager-spend-reason"><span>Основание бюджета *</span><textarea name="reason" required minlength="8" maxlength="500" placeholder="Например: согласован тест трёх роликов товара"></textarea></label>
          <label class="option"><input type="checkbox" name="paid_generation_enabled" value="true" checked /><span><strong>Сразу разрешить платные запуски</strong><br /><small>Кампания появится в обязательном списке при создании ролика.</small></span></label>
          <div class="manager-spend-actions"><button class="btn btn-small" type="submit" data-primary-action="true">Создать кампанию</button></div>
        </fieldset>
      </form>
    </details>
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
  const policySource = objectValue(source.policy) || {};
  const usageSource = objectValue(source.usage) || {};
  const status = safeCode(source.status);
  const policy = {
    paidGenerationEnabled: policySource.paid_generation_enabled === true,
    dailyLimitMinor: minorValue(policySource.daily_limit_minor),
    monthlyLimitMinor: minorValue(policySource.monthly_limit_minor),
    perRequestLimitMinor: minorValue(policySource.per_request_limit_minor),
    version: nonNegativeInteger(policySource.version),
    reason: safeText(policySource.reason),
    updatedAt: safeText(policySource.updated_at),
  };
  const policyPresent = [
    "paid_generation_enabled",
    "daily_limit_minor",
    "monthly_limit_minor",
    "per_request_limit_minor",
    "version",
  ].every((key) => Object.prototype.hasOwnProperty.call(policySource, key))
    && policy.dailyLimitMinor !== null
    && policy.monthlyLimitMinor !== null
    && policy.perRequestLimitMinor !== null
    && policy.version > 0;
  const day = normalizePeriod(objectValue(usageSource.day) || {});
  const month = normalizePeriod(objectValue(usageSource.month) || {});
  const hasExplicitEnabled = Object.prototype.hasOwnProperty.call(source, "enabled");
  const explicitEnabled = hasExplicitEnabled ? source.enabled === true : null;
  const explicitBlocker = safeCode(source.blocker_code);
  const blockerCode = explicitBlocker
    || (status !== "active" ? "paid_generation_campaign_not_active" : "")
    || (!policyPresent ? "paid_generation_campaign_policy_missing" : "")
    || (!policy.paidGenerationEnabled ? "paid_generation_campaign_paused" : "")
    || (day.remainingMinor === null || month.remainingMinor === null
      ? "generation_campaign_budget_policy_changed"
      : "")
    || (day.remainingMinor === 0
      ? "generation_campaign_daily_budget_exceeded"
      : "")
    || (month.remainingMinor === 0
      ? "generation_campaign_monthly_budget_exceeded"
      : "")
    || (hasExplicitEnabled && explicitEnabled !== true
      ? "generation_campaign_budget_policy_changed"
      : "");
  const fallbackRemainingMinor = day.remainingMinor === null
    || month.remainingMinor === null
    ? null
    : Math.min(day.remainingMinor, month.remainingMinor);
  return {
    id: campaignIdValue(source.id || source.campaign_id)
      || safeText(source.id || source.campaign_id),
    name: safeText(source.name || source.campaign_name),
    productName: safeText(source.product_name),
    sku: safeText(source.sku),
    kind: safeText(source.kind),
    status,
    enabled: status === "active"
      && policyPresent
      && policy.paidGenerationEnabled
      && explicitEnabled !== false
      && !blockerCode,
    blockerCode,
    policy,
    day,
    month,
    committedMinor: minorValue(source.committed_minor ?? source.settled_minor) ?? 0,
    reservedMinor: minorValue(source.reserved_minor) ?? 0,
    remainingMinor: minorValue(source.remaining_minor) ?? fallbackRemainingMinor,
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

function campaignIdValue(value) {
  const id = safeText(value).toLowerCase();
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u.test(id)
    ? id
    : "";
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
