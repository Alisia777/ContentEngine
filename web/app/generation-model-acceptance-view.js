const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const REVIEW_STATUSES = new Set([
  "not_started",
  "queued",
  "processing",
  "completed",
  "failed",
  "cancelled",
]);
const NEXT_ACTION_CODES = new Set([
  "none",
  "run_paid_smoke_and_approve",
  "review_succeeded_output",
  "complete_context_approval",
  "generate_replacement_and_approve",
]);

function safeInteger(value) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function validEvidence(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const decision = safeText(value.decision);
  const score = Number(value.overall_score);
  const blockers = Number(value.blockers_count);
  const decidedAt = safeText(value.decided_at);
  const expiresAt = safeText(value.expires_at);
  const decidedAtMs = Date.parse(decidedAt);
  const expiresAtMs = Date.parse(expiresAt);
  const fresh = Boolean(
    value.fresh === true
    && Number.isFinite(decidedAtMs)
    && Number.isFinite(expiresAtMs)
    && expiresAtMs > decidedAtMs,
  );
  if (
    !UUID_PATTERN.test(safeText(value.generation_job_id))
    || !UUID_PATTERN.test(safeText(value.media_id))
    || !UUID_PATTERN.test(safeText(value.review_id))
    || !UUID_PATTERN.test(safeText(value.decision_id))
    || !SHA256_PATTERN.test(safeText(value.media_sha256))
    || !SHA256_PATTERN.test(safeText(value.review_completion_hash))
    || !["approved", "needs_changes", "rejected"].includes(decision)
    || !Number.isInteger(score)
    || score < 0
    || score > 100
    || !Number.isInteger(blockers)
    || blockers < 0
    || value.media_watched_confirmed !== true
    || value.independent_reviewer !== true
  ) return null;
  return Object.freeze({
    generationJobId: safeText(value.generation_job_id),
    mediaId: safeText(value.media_id),
    mediaSha256: safeText(value.media_sha256),
    reviewId: safeText(value.review_id),
    reviewCompletionHash: safeText(value.review_completion_hash),
    reviewModelProvider: safeText(value.review_model_provider),
    reviewModelVersion: safeText(value.review_model_version),
    decisionId: safeText(value.decision_id),
    decision,
    decidedAt,
    expiresAt,
    fresh,
    overallScore: score,
    blockersCount: blockers,
    complianceStatus: safeText(value.compliance_status),
    contextBound: value.context_bound === true,
  });
}

function validPendingReview(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const generationJobId = safeText(value.generation_job_id);
  const mediaId = safeText(value.media_id);
  const reviewId = safeText(value.review_id);
  const reviewStatus = safeText(value.review_status);
  if (
    !UUID_PATTERN.test(generationJobId)
    || !UUID_PATTERN.test(mediaId)
    || (reviewId && !UUID_PATTERN.test(reviewId))
    || !REVIEW_STATUSES.has(reviewStatus)
    || (reviewId && reviewStatus === "not_started")
    || (!reviewId && reviewStatus !== "not_started")
  ) return null;
  return Object.freeze({
    generationJobId,
    mediaId,
    reviewId,
    reviewStatus,
    createdAt: safeText(value.created_at),
  });
}

function acceptanceCatalog(source, catalogSnapshot) {
  const canonical = Array.isArray(catalogSnapshot?.models)
    ? catalogSnapshot.models
    : [];
  // Union, не подмена: серверный каталог приёмки может знать идентичности
  // (рецепты стратегий), которых ещё нет в edge-снимке — иначе они
  // исчезали бы из панели после загрузки edge-каталога.
  const sourceRows = Array.isArray(source.models) ? source.models : [];
  const rows = canonical.length ? [...canonical, ...sourceRows] : sourceRows;
  const seen = new Set();
  return rows.flatMap((entry) => {
    const provider = safeText(entry?.provider || source.provider || "runway").toLowerCase();
    const model = safeText(entry?.model).toLowerCase();
    const key = provider && model ? `${provider}:${model}` : "";
    if (!key || seen.has(key)) return [];
    seen.add(key);
    const contentKind = safeText(entry?.contentKind || entry?.content_kind).toLowerCase();
    const detail = contentKind === "photo"
      ? "товарное фото"
      : contentKind === "video"
        ? "видеогенерация"
        : safeText(entry?.detail) || "модель генерации";
    return [Object.freeze({
      provider,
      model,
      label: safeText(entry?.publicLabel || entry?.public_label || entry?.label) || model,
      detail,
    })];
  });
}

export function normalizeGenerationModelAcceptance(raw, catalogSnapshot = null) {
  const source = raw && typeof raw === "object" && !Array.isArray(raw)
    ? raw
    : {};
  const sourceModels = Array.isArray(source.models) ? source.models : [];
  const byIdentity = new Map(
    sourceModels
      .filter((item) => item && typeof item === "object" && !Array.isArray(item))
      .map((item) => [
        `${safeText(item.provider || source.provider || "runway").toLowerCase()}:${safeText(item.model).toLowerCase()}`,
        item,
      ]),
  );
  const catalog = acceptanceCatalog(source, catalogSnapshot);
  const models = catalog.map((catalogEntry) => {
    const item = byIdentity.get(`${catalogEntry.provider}:${catalogEntry.model}`) || {};
    const evidence = validEvidence(item.evidence);
    const pendingReview = validPendingReview(item.pending_review);
    const threshold = safeInteger(item.quality_threshold) || 80;
    const successfulRuns = safeInteger(item.successful_runs);
    const serverStatus = safeText(item.status);
    const accepted = Boolean(
      serverStatus === "accepted"
      && evidence?.decision === "approved"
      && evidence.contextBound
      && evidence.fresh
      && evidence.overallScore >= threshold
      && evidence.blockersCount === 0
      && evidence.complianceStatus.length > 0
      && evidence.complianceStatus !== "block",
    );
    const status = accepted
      ? "accepted"
      : evidence
        ? "needs_revalidation"
        : "unproven";
    const serverNextActionCode = safeText(item.next_action_code);
    let nextActionCode;
    if (accepted) {
      nextActionCode = "none";
    } else if (
      NEXT_ACTION_CODES.has(serverNextActionCode)
      && serverNextActionCode !== "none"
      && !(
        serverNextActionCode === "run_paid_smoke_and_approve"
        && successfulRuns > 0
      )
    ) {
      nextActionCode = serverNextActionCode;
    } else if (serverNextActionCode) {
      nextActionCode = "status_refresh_required";
    } else if (evidence) {
      nextActionCode = "generate_replacement_and_approve";
    } else if (successfulRuns > 0) {
      nextActionCode = "review_succeeded_output";
    } else {
      nextActionCode = "run_paid_smoke_and_approve";
    }
    return Object.freeze({
      ...catalogEntry,
      status,
      reasonCode: safeText(item.reason_code) || "evidence_missing",
      nextActionCode,
      qualityThreshold: threshold,
      evidenceMaxAgeDays:
        safeInteger(item.evidence_max_age_days) || 90,
      successfulRuns,
      reviewedRuns: safeInteger(item.reviewed_runs),
      acceptedRuns: safeInteger(item.accepted_runs),
      pendingReviewRuns: safeInteger(item.pending_review_runs),
      evidence,
      pendingReview,
    });
  });
  const acceptedCount = models.filter((item) => item.status === "accepted").length;
  return Object.freeze({
    version: safeText(source.version),
    provider: safeText(source.provider) || "runway",
    qualityThreshold: safeInteger(source.quality_threshold) || 80,
    acceptedCount,
    totalModels: catalog.length,
    allModelsAccepted: catalog.length > 0 && acceptedCount === catalog.length,
    evaluatedAt: safeText(source.evaluated_at),
    models: Object.freeze(models),
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  const parsed = Date.parse(String(value || ""));
  if (!Number.isFinite(parsed)) return "дата не зафиксирована";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(parsed));
}

function modelStatusCopy(model) {
  if (model.status === "accepted") {
    return {
      badge: "ПРОВЕРЕНО",
      badgeClass: "badge-success",
      summary:
        `Результат принят другим участником: ${model.evidence.overallScore}/100, без блокеров.`,
    };
  }
  if (model.status === "needs_revalidation") {
    const detail = model.reasonCode === "acceptance_evidence_stale"
      ? `Контроль качества старше ${model.evidenceMaxAgeDays} дней. Нужен один новый независимо проверенный результат.`
      : model.evidence?.decision === "approved"
        ? `Последнее принятие не прошло порог ${model.qualityThreshold}/100 или не связано с полным контекстом.`
        : "Последнее независимое решение не приняло результат.";
    return {
      badge: "ПОВТОРИТЬ QA",
      badgeClass: "badge-warning",
      summary: detail,
    };
  }
  if (model.successfulRuns > 0) {
    return {
      badge: "ЖДЁТ ПРИНЯТИЯ",
      badgeClass: "badge-warning",
      summary:
        "Реальный файл уже создан, но нет полного независимого принятия после AI-QA.",
    };
  }
  return {
    badge: "НЕ ДОКАЗАНО",
    badgeClass: "badge-mock",
    summary:
      "Ещё нет оплаченного реального результата, прошедшего AI-QA и независимое принятие.",
  };
}

function modelNextAction(model) {
  if (!model || model.status === "accepted") return null;
  if (model.pendingReview?.reviewId) {
    return Object.freeze({
      kind: "review",
      label: "Открыть точный QA",
      reviewId: model.pendingReview.reviewId,
    });
  }
  if (model.pendingReview?.mediaId) {
    return Object.freeze({
      kind: "media",
      label: "Открыть файл в QA",
      mediaId: model.pendingReview.mediaId,
    });
  }
  if (
    model.nextActionCode === "complete_context_approval"
    && model.evidence?.reviewId
  ) {
    return Object.freeze({
      kind: "review",
      label: "Завершить принятие",
      reviewId: model.evidence.reviewId,
    });
  }
  if (
    [
      "review_succeeded_output",
      "status_refresh_required",
      "complete_context_approval",
    ].includes(model.nextActionCode)
  ) {
    return Object.freeze({
      kind: "refresh",
      label: "Обновить безопасный статус",
    });
  }
  if (
    [
      "run_paid_smoke_and_approve",
      "generate_replacement_and_approve",
    ].includes(model.nextActionCode)
  ) {
    return Object.freeze({
      kind: "prepare",
      label: model.reasonCode === "acceptance_evidence_stale"
        ? "Подготовить перепроверку"
        : model.status === "needs_revalidation"
          ? "Подготовить новый вариант"
          : "Подготовить проверку",
    });
  }
  return Object.freeze({
    kind: "refresh",
    label: "Обновить безопасный статус",
  });
}

function modelActionMarkup(model, action = modelNextAction(model)) {
  if (!action) return "";
  if (action.kind === "review") {
    return `
      <a class="btn btn-secondary btn-small" href="#/workspace/review?view=current&amp;review=${encodeURIComponent(String(action.reviewId))}">
        ${escapeHtml(action.label)}
      </a>
    `;
  }
  if (action.kind === "media") {
    return `
      <button
        class="btn btn-secondary btn-small"
        type="button"
        data-action="open-generated-content-review"
        data-media-id="${escapeHtml(action.mediaId)}"
      >
        ${escapeHtml(action.label)}
      </button>
    `;
  }
  if (action.kind === "prepare") {
    return `
      <button
        class="btn btn-secondary btn-small"
        type="button"
        data-action="prepare-generation-acceptance"
        data-generation-model="${escapeHtml(model.model)}"
      >
        ${escapeHtml(action.label)}
      </button>
    `;
  }
  return `
    <button
      class="btn btn-secondary btn-small"
      type="button"
      data-action="refresh-generation-model-acceptance"
      data-generation-model="${escapeHtml(model.model)}"
    >
      ${escapeHtml(action.label)}
    </button>
  `;
}

export function nextGenerationModelAcceptanceAction(normalized = {}) {
  const actions = Array.isArray(normalized.models)
    ? normalized.models
      .map((model) => ({
        model,
        action: modelNextAction(model),
      }))
      .filter((item) => item.action)
    : [];
  const exact = actions.find((item) =>
    ["review", "media"].includes(item.action.kind)
  );
  const refresh = actions.find((item) => item.action.kind === "refresh");
  const replacement = actions.find((item) =>
    item.action.kind === "prepare"
    && item.model.status === "needs_revalidation"
  );
  const selected = exact || refresh || replacement || actions[0] || null;
  if (!selected) return null;
  return Object.freeze({
    ...selected.action,
    model: selected.model.model,
    modelLabel: selected.model.label,
  });
}

export function generationModelAcceptanceMarkup(state = {}, catalogSnapshot = null) {
  const status = safeText(state.status) || "idle";
  if (["idle", "loading"].includes(status)) {
    return `
      <section class="generation-model-acceptance" aria-busy="true">
        <div>
          <p class="eyebrow">Production quality</p>
          <h3>Проверка качества моделей</h3>
        </div>
        <p class="muted tiny">Сверяем реальные результаты, AI-QA и решения команды…</p>
      </section>
    `;
  }
  if (status === "error") {
    return `
      <section class="generation-model-acceptance">
        <div>
          <p class="eyebrow">Production quality</p>
          <h3>Проверка качества моделей</h3>
        </div>
        <div class="alert alert-warning" role="status">
          <strong aria-hidden="true">!</strong>
          <span>Статус качества не подтверждён: серверное доказательство временно не загрузилось. Доступность провайдера, остаток бюджета и успешный API-ответ не считаются проверкой качества.</span>
        </div>
      </section>
    `;
  }

  const normalized = normalizeGenerationModelAcceptance(state.data, catalogSnapshot);
  const primaryAction = nextGenerationModelAcceptanceAction(normalized);
  const primaryModel = primaryAction
    ? normalized.models.find((model) => model.model === primaryAction.model)
    : null;
  return `
    <section class="generation-model-acceptance" aria-label="Проверка production-качества моделей">
      <div class="generation-model-acceptance__header">
        <div>
          <p class="eyebrow">Production quality</p>
          <h3>Проверка качества моделей</h3>
        </div>
        <span class="badge ${normalized.allModelsAccepted ? "badge-success" : "badge-warning"}">
          ${normalized.acceptedCount}/${normalized.totalModels}
        </span>
      </div>
      <p class="muted tiny">«Проверено» появляется только после реального платного файла, завершённого AI-QA и принятия другим участником. Баланс провайдера и успешный API-ответ этого не доказывают.</p>
      ${primaryAction && primaryModel ? `
        <div class="generation-model-acceptance__actions">
          <strong>Следующий безопасный шаг: ${escapeHtml(primaryAction.modelLabel)}</strong>
          ${modelActionMarkup(primaryModel, primaryAction)}
        </div>
      ` : ""}
      <div class="generation-model-acceptance__grid">
        ${normalized.models.map((model) => {
          const copy = modelStatusCopy(model);
          return `
            <article class="generation-model-acceptance__item" data-provider="${escapeHtml(model.provider)}" data-model="${escapeHtml(model.model)}" data-acceptance-status="${escapeHtml(model.status)}">
              <div class="generation-model-acceptance__item-head">
                <div>
                  <strong>${escapeHtml(model.label)}</strong>
                  <small>${escapeHtml(model.detail)}</small>
                </div>
                <span class="badge ${copy.badgeClass}">${copy.badge}</span>
              </div>
              <p>${escapeHtml(copy.summary)}</p>
              <small class="muted">
                ${model.evidence
                  ? `Решение: ${escapeHtml(formatDate(model.evidence.decidedAt))} · SHA ${escapeHtml(model.evidence.mediaSha256.slice(0, 10))}…`
                  : `Успешных реальных файлов: ${model.successfulRuns}; ждут решения: ${model.pendingReviewRuns}.`}
              </small>
              <div class="generation-model-acceptance__actions">
                ${modelActionMarkup(model)}
              </div>
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
}
