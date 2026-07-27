const MODEL_CATALOG = Object.freeze([
  Object.freeze({
    model: "seedream5_lite",
    label: "Seedream 5 Lite",
    detail: "товарное фото 2K",
  }),
  Object.freeze({
    model: "gen4_turbo",
    label: "Gen-4 Turbo",
    detail: "видео 5 секунд",
  }),
  Object.freeze({
    model: "seedance2_fast",
    label: "Seedance 2 Fast",
    detail: "видео 8 секунд с речью",
  }),
]);

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

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
    decidedAt: safeText(value.decided_at),
    overallScore: score,
    blockersCount: blockers,
    complianceStatus: safeText(value.compliance_status),
    contextBound: value.context_bound === true,
  });
}

export function normalizeGenerationModelAcceptance(raw) {
  const source = raw && typeof raw === "object" && !Array.isArray(raw)
    ? raw
    : {};
  const sourceModels = Array.isArray(source.models) ? source.models : [];
  const byModel = new Map(
    sourceModels
      .filter((item) => item && typeof item === "object" && !Array.isArray(item))
      .map((item) => [safeText(item.model), item]),
  );
  const models = MODEL_CATALOG.map((catalog) => {
    const item = byModel.get(catalog.model) || {};
    const evidence = validEvidence(item.evidence);
    const threshold = safeInteger(item.quality_threshold) || 80;
    const serverStatus = safeText(item.status);
    const accepted = Boolean(
      serverStatus === "accepted"
      && evidence?.decision === "approved"
      && evidence.contextBound
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
    return Object.freeze({
      ...catalog,
      status,
      reasonCode: safeText(item.reason_code) || "evidence_missing",
      nextActionCode: safeText(item.next_action_code)
        || "run_paid_smoke_and_approve",
      qualityThreshold: threshold,
      successfulRuns: safeInteger(item.successful_runs),
      reviewedRuns: safeInteger(item.reviewed_runs),
      acceptedRuns: safeInteger(item.accepted_runs),
      pendingReviewRuns: safeInteger(item.pending_review_runs),
      evidence,
    });
  });
  const acceptedCount = models.filter((item) => item.status === "accepted").length;
  return Object.freeze({
    version: safeText(source.version),
    provider: safeText(source.provider) || "runway",
    qualityThreshold: safeInteger(source.quality_threshold) || 80,
    acceptedCount,
    totalModels: MODEL_CATALOG.length,
    allModelsAccepted: acceptedCount === MODEL_CATALOG.length,
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
    const detail = model.evidence?.decision === "approved"
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

export function generationModelAcceptanceMarkup(state = {}) {
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
          <span>Статус качества не подтверждён: серверное доказательство временно не загрузилось. Доступность Runway, остаток бюджета и успешный API-ответ не считаются проверкой качества.</span>
        </div>
      </section>
    `;
  }

  const normalized = normalizeGenerationModelAcceptance(state.data);
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
      <p class="muted tiny">«Проверено» появляется только после реального платного файла, завершённого AI-QA и принятия другим участником. Баланс Runway и успешный API-ответ этого не доказывают.</p>
      <div class="generation-model-acceptance__grid">
        ${normalized.models.map((model) => {
          const copy = modelStatusCopy(model);
          return `
            <article class="generation-model-acceptance__item" data-model="${escapeHtml(model.model)}" data-acceptance-status="${escapeHtml(model.status)}">
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
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
}
