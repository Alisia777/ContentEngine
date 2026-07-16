const ACTIVE_STATUSES = new Set(["queued", "starting", "researching", "processing", "running"]);
const READY_STATUSES = new Set(["ready", "completed", "succeeded", "draft", "approved"]);

export function normalizeProductResearch(raw, previous = null) {
  const root = objectValue(raw?.data) || objectValue(raw) || {};
  const run = objectValue(root.run) || objectValue(root.research) || root;
  const result = objectValue(run.result) || objectValue(root.result) || {};
  const analysis = objectValue(run.analysis) || objectValue(result.analysis) || objectValue(root.analysis) || result;
  const latestDraft = objectValue(root.latest_draft) || objectValue(root.draft) || objectValue(run.latest_draft) || {};
  const latestBrief = objectValue(latestDraft.brief) || {};
  const summary = objectValue(run.summary) || objectValue(root.summary) || {};
  const forecast = objectValue(arrayValue(root.forecasts)[0]) || objectValue(root.forecast) || {};
  const prediction = objectValue(analysis.prediction)
    || objectValue(analysis.forecast)
    || objectValue(latestBrief.creative_potential)
    || objectValue(summary.creative_potential)
    || forecast;
  const briefSource = Object.keys(latestBrief).length
    ? { ...latestBrief, title: latestDraft.title || latestBrief.title }
    : objectValue(run.brief_draft)
      || objectValue(run.brief)
      || objectValue(analysis.brief)
      || objectValue(result.brief)
      || previous?.brief;
  const brief = normalizeBrief(briefSource);
  const scenarios = normalizeScenarios(
    arrayValue(brief.scenarios).length
      ? brief.scenarios
      : arrayValue(analysis.scenarios).length
        ? analysis.scenarios
        : arrayValue(result.scenarios).length
          ? result.scenarios
          : previous?.scenarios,
  );
  const score = clampScore(
    prediction.score
      ?? prediction.success_score
      ?? analysis.success_score
      ?? analysis.score
      ?? run.success_score
      ?? previous?.score,
  );
  const taskIds = [root.task_ids, run.task_ids, result.task_ids, previous?.taskIds]
    .map(stringArray)
    .find((items) => items.length) || [];
  const rawApproval = root.approval ?? run.approval ?? result.approval ?? previous?.approval ?? null;
  const approval = objectValue(rawApproval) || {};
  const approvalStatus = String(
    typeof rawApproval === "string" ? rawApproval : approval.status || latestDraft.status || "",
  ).toLowerCase();
  const approved = rawApproval === true
    || approvalStatus === "approved"
    || Boolean(approval.approved_at || approval.approvedAt)
    || taskIds.length > 0
    || previous?.approved === true;
  const runStatus = String(run.status || root.status || previous?.status || "queued").toLowerCase();
  const status = approved ? "approved" : runStatus;
  const id = String(run.id || root.run_id || root.research_id || root.id || previous?.id || "");

  return {
    id,
    status,
    productName: String(run.product_name || run.product?.name || root.product_name || previous?.productName || ""),
    sku: String(run.sku || run.product?.sku || root.sku || previous?.sku || ""),
    score,
    confidence: normalizeConfidence(prediction.confidence_label || prediction.confidence || analysis.confidence || run.confidence || previous?.confidence),
    forecastSummary: String(prediction.summary || prediction.explanation || forecast.factors?.summary || analysis.forecast_summary || previous?.forecastSummary || ""),
    factors: normalizeFactors(forecast.factors || prediction.factors || analysis.score_factors || analysis.factors || previous?.factors),
    sources: normalizeSources(root.sources || run.sources || analysis.sources || result.sources || previous?.sources),
    brief: { ...brief, scenarios },
    rawBrief: Object.keys(latestBrief).length ? latestBrief : (previous?.rawBrief || {}),
    rawTaskBlueprint: arrayValue(latestDraft.task_blueprint).length ? latestDraft.task_blueprint : (previous?.rawTaskBlueprint || []),
    draftId: String(approval.draft_id || approval.draftId || latestDraft.id || root.draft_id || previous?.draftId || ""),
    sourceIds: stringArray(root.source_ids).length
      ? stringArray(root.source_ids)
      : normalizeSources(root.sources || run.sources).map((source) => source.id).filter(Boolean).length
        ? normalizeSources(root.sources || run.sources).map((source) => source.id).filter(Boolean)
        : stringArray(previous?.sourceIds),
    scenarios,
    approval,
    approved,
    taskIds,
    failureMessage: String(run.error_message || run.failure_message || root.error_message || root.failure_message || root.error?.message || ""),
    updatedAt: String(run.updated_at || root.updated_at || previous?.updatedAt || ""),
  };
}

export function productResearchStatusKind(status) {
  const normalized = String(status || "").toLowerCase();
  if (READY_STATUSES.has(normalized)) return "ready";
  if (["failed", "cancelled", "rejected"].includes(normalized)) return "failed";
  return ACTIVE_STATUSES.has(normalized) ? "active" : "active";
}

export function productResearchInputMarkup({ media = [], mediaLoading = false, error = "" } = {}) {
  const mediaMarkup = media.length
    ? `<div class="product-research-media-grid">${media.map((item) => researchMediaMarkup(item)).join("")}</div>`
    : `<div class="product-research-media-empty">
        <span aria-hidden="true">▧</span>
        <div><strong>${mediaLoading ? "Загружаем медиатеку…" : "В медиатеке пока нет фотографий"}</strong><p>${mediaLoading ? "Подождите несколько секунд." : "Сначала добавьте точные фото упаковки и этикетки."}</p></div>
        ${mediaLoading ? "" : `<a class="btn btn-secondary btn-small" href="#/workspace/media">Открыть материалы</a>`}
      </div>`;
  return `
    ${error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
    <section class="product-research-start-grid" aria-labelledby="product-research-form-title">
      <form id="product-research-start-form" class="card card-pad form-stack" novalidate>
        <div class="product-research-card-heading">
          <span class="product-research-step" aria-hidden="true">01</span>
          <div><p class="eyebrow">Исходные данные</p><h2 id="product-research-form-title">Что именно разбираем</h2><p>Заполните то, что знаете. Не придумывайте свойства товара — неизвестное найдёт анализ или отметит как гипотезу.</p></div>
        </div>
        <div class="form-grid-2">
          <label class="field"><span>Название товара *</span><input name="product_name" required maxlength="180" autocomplete="off" placeholder="Например: сывороточный протеин Bombbar" /></label>
          <label class="field"><span>Артикул / SKU *</span><input name="sku" required maxlength="120" autocomplete="off" placeholder="Например: 159068498" /></label>
        </div>
        <label class="field"><span>Ссылка на карточку товара</span><input name="marketplace_url" type="url" inputmode="url" placeholder="https://www.wildberries.ru/catalog/…" /><small class="field-hint">Только публичная HTTPS-ссылка. Пароли и ссылки из личного кабинета сюда не вставляйте.</small></label>
        <fieldset class="product-research-platforms">
          <legend>Для каких площадок готовим ролики *</legend>
          <label><input type="checkbox" name="platforms" value="instagram" /> <span>Instagram Reels</span></label>
          <label><input type="checkbox" name="platforms" value="youtube" /> <span>YouTube Shorts</span></label>
          <label><input type="checkbox" name="platforms" value="vk" /> <span>VK Клипы</span></label>
        </fieldset>
        <label class="field"><span>Главная цель</span><select name="objective"><option value="conversion">Заказы и переходы</option><option value="awareness">Узнаваемость товара</option><option value="ugc">Нативный UGC-обзор</option><option value="education">Объяснить применение</option></select></label>
        <label class="field"><span>Подтверждённые вводные</span><textarea name="known_facts" maxlength="1200" placeholder="Состав, объём, комплектация, способ применения — только то, что подтверждено упаковкой или документами."></textarea><small class="field-hint">Каждый факт будет отделён от найденных источников и гипотез ИИ.</small></label>
        <div class="product-research-media-field">
          <div><strong>Фото из «Материалов»</strong><small>Выберите упаковку, этикетку и товар целиком. Лучше 3–6 точных кадров.</small></div>
          ${mediaMarkup}
        </div>
        <div class="alert alert-warning" role="note"><strong aria-hidden="true">₽</strong><span><strong>Это платный ИИ-анализ.</strong> Используется поиск в интернете и модель анализа; итоговая стоимость определяется подключённым тарифом сервиса.</span></div>
        <label class="check-row"><input type="checkbox" name="paid_analysis_ack" required /><span><strong>Запускаю платный ИИ-анализ с поиском в интернете</strong><br /><small>Повторный клик с теми же вводными не создаст второй запуск.</small></span></label>
        <label class="check-row"><input type="checkbox" name="human_review_ack" required /><span><strong>Я проверю итог перед созданием задач</strong><br /><small>ИИ готовит черновик, но не принимает за человека факты, обещания и юридические решения.</small></span></label>
        <button class="btn btn-block" type="submit">Запустить платный анализ и собрать 3 сценария <span aria-hidden="true">→</span></button>
      </form>
      <aside class="card card-pad product-research-explainer" aria-label="Что получится после анализа">
        <p class="eyebrow">На выходе</p>
        <h2>Не «магия», а проверяемый рабочий черновик</h2>
        <ol>
          <li><span>1</span><div><strong>Источники и факты</strong><p>У каждой находки будет ссылка и пометка, откуда она взялась.</p></div></li>
          <li><span>2</span><div><strong>ТЗ и три сценария</strong><p>Хуки, реплики, кадры, доказательства и стоп-формулировки можно исправить.</p></div></li>
          <li><span>3</span><div><strong>Оценка потенциала</strong><p>Сильные стороны и риски — без обещания «вирусности».</p></div></li>
          <li><span>4</span><div><strong>Задачи одним нажатием</strong><p>Только после вашего финального подтверждения.</p></div></li>
        </ol>
        <div class="product-research-privacy"><strong>Что анализ не делает</strong><p>Не входит в чужие кабинеты, не обходит защиту площадок и не считает неподтверждённое свойство фактом.</p></div>
      </aside>
    </section>`;
}

export function productResearchProgressMarkup(record, error = "") {
  const failed = productResearchStatusKind(record?.status) === "failed";
  return `
    <section class="card card-pad product-research-progress" ${failed || error ? 'role="alert"' : 'role="status"'} aria-live="polite">
      <div class="product-research-orbit" aria-hidden="true"><span></span><b>A</b></div>
      <p class="eyebrow">${failed || error ? "Нужна проверка" : "Исследование запущено"}</p>
      <h2>${failed || error ? "Анализ не завершился" : `Собираем доказательства для «${escapeHtml(record?.productName || "товара") }»`}</h2>
      <p>${escapeHtml(error || record?.failureMessage || "Проверяем карточку, доступные публичные источники, формулировки покупателей и будущие сценарии. Страницу можно оставить открытой — статус обновляется автоматически.")}</p>
      ${failed || error
        ? `<div class="inline-actions"><button class="btn btn-secondary" type="button" data-action="refresh-product-research">Проверить статус</button><button class="btn btn-ghost" type="button" data-action="new-product-research">Начать заново</button></div>`
        : `<div class="product-research-progress-steps" aria-hidden="true"><span class="done">Вводные</span><span class="active">Источники</span><span>ТЗ</span><span>Прогноз</span></div><button class="btn btn-secondary btn-small" type="button" data-action="refresh-product-research">Проверить сейчас</button>`}
    </section>`;
}

export function productResearchResultMarkup(record, {
  saving = false,
  approving = false,
  notice = "",
  error = "",
  members = [],
  defaultAssigneeId = "",
} = {}) {
  const brief = normalizeBrief(record?.brief);
  const scenarios = normalizeScenarios(record?.scenarios);
  const confidence = confidenceCopy(record?.confidence);
  const score = clampScore(record?.score);
  const sourceMarkup = record?.sources?.length
    ? record.sources.map(sourceMarkupItem).join("")
    : `<div class="product-research-empty-note"><strong>Публичные источники не подтверждены</strong><p>Не переносите найденные ИИ формулировки в ролик как факт, пока не добавите доказательство.</p></div>`;
  const taskIds = stringArray(record?.taskIds);
  const approved = record?.approved === true || taskIds.length > 0;
  const assignees = normalizeResearchMembers(members, defaultAssigneeId);
  const fallbackAssigneeId = String(defaultAssigneeId || assignees[0]?.profileId || "");
  return `
    ${error ? `<div class="alert alert-danger" role="alert"><strong aria-hidden="true">!</strong><span>${escapeHtml(error)}</span></div>` : ""}
    ${notice ? `<div class="alert alert-success" role="status"><strong aria-hidden="true">✓</strong><span>${escapeHtml(notice)}</span></div>` : ""}
    ${approved ? `<section class="card card-pad product-research-approved" role="status"><span aria-hidden="true">✓</span><div><p class="eyebrow">ТЗ утверждено</p><h2>${taskIds.length ? `Задачи созданы: ${taskIds.length}` : "Задачи созданы"}</h2><p>Исполнители уже назначены. Повторное сохранение и утверждение заблокированы, чтобы ТЗ не разошлось с созданными задачами.</p></div><a class="btn" href="#/workspace/tasks">Открыть задачи →</a></section>` : ""}
    <section class="product-research-scoreboard" aria-label="Предварительная оценка роликов">
      <div class="card card-pad product-research-score" style="--research-score:${score}">
        <div class="product-research-score-ring"><strong>${score}</strong><small>из 100</small></div>
        <div><p class="eyebrow">Креативный потенциал</p><h2>${scoreLabel(score)}</h2><p>${escapeHtml(record?.forecastSummary || "Оценка показывает качество вводных и сценарной идеи.")}</p><small class="product-research-score-note">Это предпубликационная эвристика: она не гарантирует просмотры или продажи.</small></div>
      </div>
      <div class="card card-pad product-research-confidence"><span class="badge">${escapeHtml(confidence.label)}</span><h2>Уверенность: ${escapeHtml(confidence.label.toLowerCase())}</h2><p>${escapeHtml(confidence.description)}</p></div>
    </section>
    <div class="product-research-result-grid">
      <section class="card product-research-sources" aria-labelledby="research-sources-title">
        <div class="card-header"><div><p class="eyebrow">Доказательства</p><h2 id="research-sources-title">Что найдено и откуда</h2></div><span class="badge">${record?.sources?.length || 0} источников</span></div>
        <div class="product-research-source-list">${sourceMarkup}</div>
      </section>
      <section class="card product-research-factors" aria-labelledby="research-factors-title">
        <div class="card-header"><div><p class="eyebrow">Почему такой балл</p><h2 id="research-factors-title">Сильные стороны и риски</h2></div></div>
        <ul>${normalizeFactors(record?.factors).map((factor) => `<li class="${factor.impact < 0 ? "risk" : "strength"}"><span aria-hidden="true">${factor.impact < 0 ? "!" : "+"}</span><div><strong>${escapeHtml(factor.label)}</strong><p>${escapeHtml(factor.detail)}</p></div></li>`).join("") || `<li><div><strong>Недостаточно данных</strong><p>Добавьте источники и уточните ТЗ — оценка станет точнее.</p></div></li>`}</ul>
      </section>
    </div>
    <form id="product-research-brief-form" class="card product-research-brief" data-research-id="${escapeHtml(record?.id || "")}" novalidate>
      <div class="card-header"><div><p class="eyebrow">${approved ? "Утверждённый результат" : "Редактируемый результат"}</p><h2>ТЗ для команды</h2><p>${approved ? "Это ТЗ уже превратилось в задачи. Чтобы не менять работу исполнителей незаметно, поля заблокированы." : "Исправьте всё, что звучит неточно. Сохранение не создаёт задачи."}</p></div><span class="badge">${approved ? "Утверждено" : "Черновик"}</span></div>
      <div class="product-research-brief-body">
        <div class="form-grid-2">
          ${textField("brief_title", "Название ТЗ", brief.title, 180, approved)}
          ${textField("target_audience", "Для кого ролик", brief.targetAudience, 500, approved)}
        </div>
        ${textArea("key_message", "Главная мысль", brief.keyMessage, "Что зритель должен понять за первые секунды", 1200, approved)}
        <div class="form-grid-2">
          ${textArea("proof_points", "Что показать как доказательство", brief.proofPoints, "По одному пункту на строку", 2500, approved)}
          ${textArea("avoid_claims", "Что нельзя обещать", brief.avoidClaims, "Неподтверждённые, медицинские или абсолютные обещания", 2500, approved)}
        </div>
        <div class="form-grid-2">
          ${textArea("visual_direction", "Визуальный стиль", brief.visualDirection, "Локация, свет, план, товар в кадре", 1800, approved)}
          ${textArea("cta", "Безопасный CTA", brief.cta, "Что зритель делает после ролика", 800, approved)}
        </div>
        <div class="product-research-scenarios-heading"><div><p class="eyebrow">Три разные гипотезы</p><h2>Сценарии и будущие задачи</h2></div><p>Не делайте три копии одного хука — меняйте угол подачи.</p></div>
        <div class="product-research-scenarios">${scenarios.map((scenario, index) => scenarioEditor(scenario, index, {
          members: assignees,
          defaultAssigneeId: fallbackAssigneeId,
          disabled: approved,
        })).join("")}</div>
        <label class="check-row product-research-approval"><input type="checkbox" name="approve_ack" ${approved ? "checked disabled" : ""} /><span><strong>Факты, формулировки и три сценария проверены человеком</strong><br /><small>${approved ? "Проверка завершена: задачи уже созданы и назначены выбранным участникам." : "При утверждении портал создаст задачи и назначит каждую выбранному выше исполнителю."}</small></span></label>
      </div>
      <div class="product-research-brief-actions">
        <button class="btn btn-secondary" type="submit" data-research-submit="save" ${saving || approving || approved ? "disabled" : ""}>${approved ? "Сохранение заблокировано" : saving ? "Сохраняем…" : "Сохранить черновик"}</button>
        <button class="btn" type="submit" data-research-submit="approve" ${saving || approving || approved ? "disabled" : ""}>${approving ? "Создаём задачи…" : approved ? "Задачи уже созданы" : "Утвердить и создать 3 задачи →"}</button>
      </div>
    </form>`;
}

export function readProductResearchBrief(form) {
  const data = new FormData(form);
  const scenarios = [0, 1, 2].map((index) => ({
    position: index + 1,
    title: value(data, `scenario_${index}_title`),
    platform: value(data, `scenario_${index}_platform`),
    hook: value(data, `scenario_${index}_hook`),
    script: value(data, `scenario_${index}_script`),
    shot_list: value(data, `scenario_${index}_shots`),
    task_title: value(data, `scenario_${index}_task_title`),
    assignee_id: value(data, `scenario_${index}_assignee_id`),
  }));
  return {
    title: value(data, "brief_title"),
    target_audience: value(data, "target_audience"),
    key_message: value(data, "key_message"),
    proof_points: value(data, "proof_points"),
    avoid_claims: value(data, "avoid_claims"),
    visual_direction: value(data, "visual_direction"),
    cta: value(data, "cta"),
    scenarios,
  };
}

function normalizeBrief(value) {
  const source = objectValue(value) || {};
  return {
    title: String(source.title || source.name || "ТЗ на три товарных ролика"),
    targetAudience: String(source.target_audience || source.targetAudience || formatAudience(source.audience)),
    keyMessage: String(source.key_message || source.keyMessage || source.message || source.summary || ""),
    proofPoints: lines(source.proof_points || source.proofPoints || source.proofs || formatFacts(source.facts)),
    avoidClaims: lines(source.avoid_claims || source.avoidClaims || source.restrictions || formatForbiddenClaims(source.claims)),
    visualDirection: String(source.visual_direction || source.visualDirection || source.visual_style || lines(source.task_blueprint?.mandatory_shots)),
    cta: String(source.cta || source.call_to_action || arrayValue(source.scenarios)[0]?.cta || ""),
    scenarios: arrayValue(source.scenarios),
  };
}

function normalizeScenarios(value) {
  const source = arrayValue(value);
  return [0, 1, 2].map((index) => {
    const item = objectValue(source[index]) || {};
    return {
      position: index + 1,
      title: String(item.title || item.name || `Сценарий ${index + 1}`),
      platform: normalizePlatform(item.platform),
      hook: String(item.hook || ""),
      script: String(item.script || item.spoken_script || item.voiceover || item.text || ""),
      shotList: formatShotList(item.shot_list || item.shotList || item.shots),
      taskTitle: String(item.task_title || item.taskTitle || item.title || `Снять сценарий ${index + 1}`),
      assigneeId: String(item.assignee_id || item.assigneeId || ""),
    };
  });
}

function normalizeSources(value) {
  return arrayValue(value).slice(0, 30).map((item, index) => {
    const source = objectValue(item) || {};
    return {
      id: String(source.id || ""),
      title: String(source.title || source.name || `Источник ${index + 1}`),
      url: safeHttpsUrl(source.url || source.source_url || source.href),
      kind: String(source.kind || source.type || source.source_type || "public"),
      claim: String(source.claim || source.fact || source.finding || source.summary || formatExtractedFacts(source.extracted_facts)),
      excerpt: String(source.excerpt || source.note || ""),
      verified: source.verified === true || source.confidence === "high" || ["first_party", "official"].includes(source.trust_level),
    };
  });
}

function normalizeFactors(value) {
  const sourceValue = objectValue(value);
  const list = sourceValue
    ? [
        ...arrayValue(sourceValue.strengths).map((item) => ({ label: item, impact: 1 })),
        ...arrayValue(sourceValue.risks).map((item) => ({ label: item, impact: -1 })),
      ]
    : arrayValue(value);
  return list.slice(0, 12).map((item) => {
    if (typeof item === "string") return { label: item, detail: "", impact: 1 };
    const source = objectValue(item) || {};
    return {
      label: String(source.label || source.title || source.factor || "Фактор"),
      detail: String(source.detail || source.description || source.reason || ""),
      impact: Number(source.impact ?? source.weight ?? (source.kind === "risk" ? -1 : 1)) || 0,
    };
  });
}

function researchMediaMarkup(item) {
  const id = String(item.id || item.media_id || "");
  const label = String(item.title || item.filename || item.name || item.sku || "Фото товара");
  const preview = safeHttpsUrl(item.signed_url || item.preview_url || item.url);
  return `<label class="product-research-media-option">
    <input type="checkbox" name="source_media_ids" value="${escapeHtml(id)}" ${id ? "" : "disabled"} />
    <span class="product-research-media-thumb">${preview ? `<img src="${escapeHtml(preview)}" alt="" loading="lazy" />` : `<i aria-hidden="true">▧</i>`}</span>
    <span><strong>${escapeHtml(label)}</strong><small>${escapeHtml(String(item.sku || item.kind || "Материал"))}</small></span>
  </label>`;
}

function sourceMarkupItem(source) {
  const kind = source.kind === "provided" ? "Дано заказчиком" : source.verified ? "Подтверждено источником" : "Публичный источник";
  return `<article class="product-research-source">
    <div><span class="badge">${escapeHtml(kind)}</span>${source.url ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer nofollow">Открыть источник <span aria-hidden="true">↗</span></a>` : ""}</div>
    <h3>${escapeHtml(source.title)}</h3>
    <p>${escapeHtml(source.claim || source.excerpt || "Источник добавлен, но подтверждённый вывод не указан.")}</p>
    ${source.claim && source.excerpt ? `<small>${escapeHtml(source.excerpt)}</small>` : ""}
  </article>`;
}

function scenarioEditor(item, index, { members = [], defaultAssigneeId = "", disabled = false } = {}) {
  const options = [["instagram", "Instagram Reels"], ["youtube", "YouTube Shorts"], ["vk", "VK Клипы"]];
  const selectedAssigneeId = String(item.assigneeId || defaultAssigneeId || members[0]?.profileId || "");
  const assigneeOptions = members.length
    ? members.map((member) => `<option value="${escapeHtml(member.profileId)}" ${member.profileId === selectedAssigneeId ? "selected" : ""}>${escapeHtml(member.label)}</option>`).join("")
    : '<option value="">Нет активных участников</option>';
  return `<fieldset class="product-research-scenario">
    <legend><span>${String(index + 1).padStart(2, "0")}</span> Гипотеза ${index + 1}</legend>
    <div class="form-grid-2">
      ${textField(`scenario_${index}_title`, "Угол подачи", item.title, 180, disabled)}
      <label class="field"><span>Площадка</span><select name="scenario_${index}_platform" ${disabled ? "disabled" : ""}>${options.map(([value, label]) => `<option value="${value}" ${item.platform === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
    </div>
    ${textArea(`scenario_${index}_hook`, "Хук первых секунд", item.hook, "Что зритель увидит и услышит сразу", 800, disabled)}
    ${textArea(`scenario_${index}_script`, "Реплика блогера", item.script, "Короткая разговорная реплика без неподтверждённых обещаний", 2400, disabled)}
    ${textArea(`scenario_${index}_shots`, "Кадры по порядку", item.shotList, "Один кадр на строку", 2400, disabled)}
    ${textField(`scenario_${index}_task_title`, "Название задачи", item.taskTitle, 180, disabled)}
    <label class="field"><span>Исполнитель задачи</span><select name="scenario_${index}_assignee_id" required ${disabled ? "disabled" : ""}>${assigneeOptions}</select><small class="field-hint">При утверждении эта задача будет назначена выбранному участнику.</small></label>
  </fieldset>`;
}

function textField(name, label, value, maxLength, disabled = false) {
  return `<label class="field"><span>${escapeHtml(label)}</span><input name="${escapeHtml(name)}" value="${escapeHtml(value || "")}" minlength="3" maxlength="${maxLength}" required ${disabled ? "disabled" : ""} /></label>`;
}

function textArea(name, label, value, placeholder, maxLength, disabled = false) {
  return `<label class="field"><span>${escapeHtml(label)}</span><textarea name="${escapeHtml(name)}" maxlength="${maxLength}" placeholder="${escapeHtml(placeholder)}" ${disabled ? "disabled" : ""}>${escapeHtml(value || "")}</textarea></label>`;
}

function normalizeResearchMembers(value, defaultAssigneeId = "") {
  const currentId = String(defaultAssigneeId || "");
  const seen = new Set();
  return arrayValue(value).flatMap((item) => {
    const member = objectValue(item) || {};
    const profileId = String(member.profileId || member.profile_id || member.id || "");
    if (!profileId || seen.has(profileId) || (member.status && member.status !== "active")) return [];
    seen.add(profileId);
    const name = String(member.label || member.display_name || member.displayName || member.email || "Участник команды");
    return [{
      profileId,
      label: `${name}${profileId === currentId ? " (вы)" : ""}`,
    }];
  });
}

function confidenceCopy(value) {
  const confidence = normalizeConfidence(value);
  if (confidence === "high") return { label: "Высокая", description: "Есть несколько согласованных источников и достаточно конкретные вводные. Результат всё равно нужно проверить человеком." };
  if (confidence === "medium") return { label: "Средняя", description: "Часть выводов подтверждена, но остаются гипотезы. Уточните факты и источники до запуска." };
  return { label: "Низкая", description: "Источников или вводных недостаточно. Используйте сценарии только как идеи, а не как готовые факты." };
}

function normalizeConfidence(value) {
  if (typeof value === "number") {
    if (value >= 0.7) return "high";
    if (value >= 0.4) return "medium";
    return "low";
  }
  const normalized = String(value || "low").toLowerCase();
  if (["high", "высокая", "высокий"].includes(normalized)) return "high";
  if (["medium", "средняя", "средний"].includes(normalized)) return "medium";
  return "low";
}

function normalizePlatform(value) {
  const normalized = String(value || "instagram").toLowerCase();
  if (normalized.includes("youtube")) return "youtube";
  if (normalized.includes("vk") || normalized.includes("вк")) return "vk";
  return "instagram";
}

function formatAudience(value) {
  return arrayValue(value).map((item) => {
    const source = objectValue(item) || {};
    return [source.name, source.profile].filter(Boolean).join(": ");
  }).filter(Boolean).join("\n");
}

function formatFacts(value) {
  return arrayValue(value).map((item) => String(item?.statement || item?.fact || item || "")).filter(Boolean);
}

function formatForbiddenClaims(value) {
  return arrayValue(objectValue(value)?.forbidden).map((item) => String(item?.claim || item || "")).filter(Boolean);
}

function formatExtractedFacts(value) {
  return arrayValue(value).map((item) => String(item?.statement || item?.fact || item || "")).filter(Boolean).join("; ");
}

function formatShotList(value) {
  return arrayValue(value).map((item) => {
    if (typeof item === "string") return item;
    const source = objectValue(item) || {};
    const timing = source.seconds ? `${source.seconds}: ` : "";
    const voice = source.voiceover ? ` Голос: ${source.voiceover}.` : "";
    const screen = source.on_screen_text ? ` Текст: ${source.on_screen_text}.` : "";
    return `${timing}${source.visual || "Кадр"}.${voice}${screen}`;
  }).filter(Boolean).join("\n");
}

function scoreLabel(score) {
  if (score >= 80) return "Сильная основа";
  if (score >= 60) return "Есть потенциал";
  if (score >= 40) return "Нужна доработка";
  return "Недостаточно данных";
}

function clampScore(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.round(Math.min(100, Math.max(0, numeric))) : 0;
}

function safeHttpsUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "https:" ? url.href : "";
  } catch {
    return "";
  }
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
}

function stringArray(value) {
  return arrayValue(value).map(String).filter(Boolean);
}

function lines(value) {
  return Array.isArray(value) ? value.map(String).filter(Boolean).join("\n") : String(value || "");
}

function value(data, name) {
  return String(data.get(name) || "").trim();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[character]);
}
