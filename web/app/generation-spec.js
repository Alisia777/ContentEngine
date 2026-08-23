export const GENERATION_SPEC_CONTROL_VERSION = "generation-spec-control-v1";

export function generationSpecPreparationRoute(generationStrategyId = "") {
  const strategyId = String(generationStrategyId || "").trim().toLowerCase();
  if (!strategyId) {
    return Object.freeze({
      kind: "legacy",
      strategyId: "",
      legacyAllowed: true,
      prepareRpc: "creator_prepare_generation_spec",
      code: "",
      message: "",
    });
  }
  return Object.freeze({
    kind: "strategy_v2",
    strategyId,
    legacyAllowed: false,
    prepareRpc: "creator_prepare_generation_strategy_spec",
    code: "generation_strategy_spec_route_required",
    message:
      "Для выбранной стратегии используется отдельное точное ТЗ. Подготовьте его основной кнопкой Product Swap или выбранной стратегии.",
  });
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const PLATFORM_SET = new Set([
  "instagram",
  "tiktok",
  "youtube",
  "vk",
  "telegram",
  "wildberries",
]);
const PROVIDER_PATTERN = /^[a-z][a-z0-9_-]{0,31}$/u;
const MODEL_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const RATIO_PATTERN = /^\d{1,4}:\d{1,4}$/u;
const RESOLUTION_PATTERN = /^(?:\d{3,4}p|[1-9]\d?K)$/u;
const CATEGORY_SET = new Set([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]);
const SPEC_STATUS_SET = new Set([
  "draft",
  "approved",
  "rejected",
  "superseded",
  "stale",
  "needs_revision",
]);
const CONTROL_ACTION_SET = new Set([
  "prepare",
  "patch",
  "approve",
  "reject",
  "revert",
  "recompute",
  "start_new_research",
  "refresh",
  "review",
  "confirm_spend",
]);
const ENVELOPE_KEYS = Object.freeze([
  "ok",
  "version",
  "generation_spec",
  "history",
  "recommended_next_action",
  "automatic_approval",
  "automatic_spend",
  "automatic_generation",
]);
const ACTION_KEYS = Object.freeze([
  "code",
  "action",
  "label",
  "reason",
  "requires_confirmation",
  "provider_action",
  "spend_action",
]);
const LEGACY_SCOPE_KEYS = Object.freeze([
  "primary_media_id",
  "media_ids",
  "platform",
  "model",
  "duration_seconds",
  "product_category",
  "format",
  "audio",
]);
const SCOPE_KEYS = Object.freeze([
  "primary_media_id",
  "media_ids",
  "platform",
  "provider",
  "model",
  "input_mode",
  "duration_seconds",
  "product_category",
  "format",
  "ratio",
  "resolution",
  "audio",
  "spoken_dialogue",
  "reference_count",
  "reference_video",
  "first_frame",
  "last_frame",
]);
const RESEARCH_KEYS = Object.freeze([
  "research_id",
  "creative_brief_draft_id",
  "scenario_position",
]);
const PERFORMANCE_KEYS = Object.freeze(["policy_hash", "policy_version"]);
const REPAIR_KEYS = Object.freeze([
  "source_review_id",
  "source_generation_job_id",
  "policy_hash",
]);
const SPEC_REQUIRED_KEYS = Object.freeze([
  "spec_id",
  "spec_version",
  "spec_hash",
  "status",
  "exact_scope",
  "editable_intent",
  "compiled_prompt",
  "prompt_hash",
  "research_provenance",
  "performance_policy_provenance",
  "repair_provenance",
  "outcome_selection_id",
  "created_at",
  "updated_at",
]);
const SPEC_OPTIONAL_KEYS = Object.freeze(["approved_at"]);

export function normalizeGenerationSpecScope(value) {
  if (hasExactKeys(value, LEGACY_SCOPE_KEYS)) {
    const legacyModel = clean(value.model).toLowerCase();
    if (!["gen4_turbo", "seedance2_fast", "seedream5_lite"].includes(legacyModel)) {
      return null;
    }
    const mediaCount = Array.isArray(value.media_ids) ? value.media_ids.length : 0;
    return normalizeGenerationSpecScope({
      ...value,
      provider: "runway",
      input_mode: "image",
      ratio: value.format,
      resolution: legacyModel === "seedream5_lite" ? "2K" : "720p",
      spoken_dialogue: legacyModel === "seedance2_fast" && value.audio === true,
      reference_count: legacyModel === "gen4_turbo" ? 0 : mediaCount,
      reference_video: false,
      first_frame: legacyModel === "gen4_turbo",
      last_frame: false,
    });
  }
  if (!hasExactKeys(value, SCOPE_KEYS)) return null;
  const primaryMediaId = normalizedUuid(value.primary_media_id);
  const mediaIds = Array.isArray(value.media_ids)
    ? value.media_ids.map(normalizedUuid)
    : [];
  const platform = clean(value.platform).toLowerCase();
  const provider = clean(value.provider).toLowerCase();
  const model = clean(value.model);
  const inputMode = clean(value.input_mode).toLowerCase();
  const productCategory = clean(value.product_category).toLowerCase();
  const format = clean(value.format);
  const ratio = clean(value.ratio);
  const resolution = clean(value.resolution);
  const audio = value.audio;
  const spokenDialogue = value.spoken_dialogue;
  const referenceCount = Number(value.reference_count);
  const referenceVideo = value.reference_video;
  const firstFrame = value.first_frame;
  const lastFrame = value.last_frame;
  const durationSeconds = Number(value.duration_seconds);
  if (
    !primaryMediaId
    || mediaIds.length < 1
    || mediaIds.length > 5
    || mediaIds.some((item) => !item)
    || new Set(mediaIds).size !== mediaIds.length
    || mediaIds[0] !== primaryMediaId
    || !PLATFORM_SET.has(platform)
    || !PROVIDER_PATTERN.test(provider)
    || !MODEL_PATTERN.test(model)
    || !["text", "image", "video"].includes(inputMode)
    || !CATEGORY_SET.has(productCategory)
    || !RATIO_PATTERN.test(format)
    || !RATIO_PATTERN.test(ratio)
    || format !== ratio
    || !RESOLUTION_PATTERN.test(resolution)
    || typeof audio !== "boolean"
    || typeof spokenDialogue !== "boolean"
    || (spokenDialogue && !audio)
    || !Number.isSafeInteger(referenceCount)
    || referenceCount < 0
    || referenceCount > 5
    || typeof referenceVideo !== "boolean"
    || typeof firstFrame !== "boolean"
    || typeof lastFrame !== "boolean"
    || !Number.isSafeInteger(durationSeconds)
    || durationSeconds < 0
    || durationSeconds > 3_600
  ) return null;
  return Object.freeze({
    primary_media_id: primaryMediaId,
    media_ids: Object.freeze(mediaIds),
    platform,
    provider,
    model,
    input_mode: inputMode,
    duration_seconds: durationSeconds,
    product_category: productCategory,
    format,
    ratio,
    resolution,
    audio,
    spoken_dialogue: spokenDialogue,
    reference_count: referenceCount,
    reference_video: referenceVideo,
    first_frame: firstFrame,
    last_frame: lastFrame,
  });
}

export function generationSpecScopesMatch(left, right) {
  const a = normalizeGenerationSpecScope(left);
  const b = normalizeGenerationSpecScope(right);
  return Boolean(a && b && stableStringify(a) === stableStringify(b));
}

export function normalizeGenerationSpecEnvelope(raw, {
  expectedScope = null,
  expectedContext = null,
} = {}) {
  const value = raw?.data && isRecord(raw.data) ? raw.data : raw;
  if (
    !hasExactKeys(value, ENVELOPE_KEYS)
    || value.ok !== true
    || value.version !== GENERATION_SPEC_CONTROL_VERSION
    || value.automatic_approval !== false
    || value.automatic_spend !== false
    || value.automatic_generation !== false
  ) return null;
  const action = normalizeRecommendedAction(value.recommended_next_action);
  if (!action) return null;
  const spec = value.generation_spec === null
    ? null
    : normalizeGenerationSpec(value.generation_spec);
  if (value.generation_spec !== null && !spec) return null;
  if (!Array.isArray(value.history) || value.history.length > 20) return null;
  const history = [];
  const seenVersions = new Set();
  let previousVersion = Number.POSITIVE_INFINITY;
  for (const item of value.history) {
    const normalized = normalizeGenerationSpec(item);
    if (
      !normalized
      || seenVersions.has(normalized.spec_version)
      || (spec && normalized.spec_id !== spec.spec_id)
      || normalized.spec_version >= previousVersion
    ) return null;
    seenVersions.add(normalized.spec_version);
    previousVersion = normalized.spec_version;
    history.push(normalized);
  }
  if (
    spec
    && (
      history.length < 1
      || !["draft", "approved", "rejected"].includes(spec.status)
      || stableStringify(history[0]) !== stableStringify(spec)
      || history.slice(1).some((item) => item.status !== "superseded")
    )
  ) return null;
  if (!spec && history.length !== 0) return null;
  if (spec && expectedScope && !generationSpecScopesMatch(spec.exact_scope, expectedScope)) {
    return null;
  }
  if (spec && expectedContext) {
    const context = normalizeGenerationSpecContext(expectedContext);
    if (
      !context
      || context.spec_id !== spec.spec_id
      || context.spec_version !== spec.spec_version
      || context.spec_hash !== spec.spec_hash
    ) return null;
  }
  return Object.freeze({
    version: GENERATION_SPEC_CONTROL_VERSION,
    generationSpec: spec,
    history: Object.freeze(history),
    recommendedNextAction: action,
    automaticApproval: false,
    automaticSpend: false,
    automaticGeneration: false,
  });
}

export function normalizeGenerationSpecContext(value) {
  if (!hasExactKeys(value, ["spec_id", "spec_version", "spec_hash"])) return null;
  const specId = normalizedUuid(value.spec_id);
  const specVersion = Number(value.spec_version);
  const specHash = clean(value.spec_hash).toLowerCase();
  if (
    !specId
    || !Number.isInteger(specVersion)
    || specVersion < 1
    || specVersion > 100_000
    || !SHA256_PATTERN.test(specHash)
  ) return null;
  return Object.freeze({
    spec_id: specId,
    spec_version: specVersion,
    spec_hash: specHash,
  });
}

export function approvedGenerationSpecContext(envelope, {
  expectedScope = null,
  dirty = false,
} = {}) {
  const spec = envelope?.generationSpec;
  if (
    dirty
    || !spec
    || spec.status !== "approved"
    || (expectedScope && !generationSpecScopesMatch(spec.exact_scope, expectedScope))
  ) return null;
  return normalizeGenerationSpecContext({
    spec_id: spec.spec_id,
    spec_version: spec.spec_version,
    spec_hash: spec.spec_hash,
  });
}

export function generationSpecApprovalReviewTuple(spec) {
  const specId = normalizedUuid(spec?.spec_id);
  const specVersion = Number(spec?.spec_version);
  const specHash = clean(spec?.spec_hash).toLowerCase();
  const promptHash = clean(spec?.prompt_hash).toLowerCase();
  if (
    !specId
    || !Number.isInteger(specVersion)
    || specVersion < 1
    || specVersion > 100_000
    || !SHA256_PATTERN.test(specHash)
    || !SHA256_PATTERN.test(promptHash)
  ) return null;
  return Object.freeze({
    specId,
    specVersion,
    specHash,
    promptHash,
    key: JSON.stringify([specId, specVersion, specHash, promptHash]),
  });
}

export function generationSpecApprovalReviewState(spec, {
  confirmed = false,
} = {}) {
  const tuple = generationSpecApprovalReviewTuple(spec);
  if (!tuple) return null;
  return Object.freeze({
    open: true,
    confirmed: confirmed === true,
    ...tuple,
  });
}

export function generationSpecApprovalReviewMatches(review, spec) {
  const tuple = generationSpecApprovalReviewTuple(spec);
  return Boolean(
    tuple
    && review?.open === true
    && review.specId === tuple.specId
    && Number(review.specVersion) === tuple.specVersion
    && review.specHash === tuple.specHash
    && review.promptHash === tuple.promptHash
    && review.key === tuple.key
  );
}

export function generationSpecSpokenReview(spec) {
  const audioExpected = spec?.exact_scope?.audio === true;
  if (!audioExpected) {
    return Object.freeze({
      audioExpected: false,
      ready: true,
      spokenLine: "",
      message: "В этой версии речь не предусмотрена.",
    });
  }
  const spokenLines = [...String(spec?.compiled_prompt || "").matchAll(
    /Реплика героя дословно:\s*«([^»]+)»/gu,
  )].map((match) => clean(match[1])).filter(Boolean);
  const ready = spokenLines.length === 1;
  return Object.freeze({
    audioExpected: true,
    ready,
    spokenLine: ready ? spokenLines[0] : "",
    message: ready
      ? "Сверьте эту реплику слово в слово перед одобрением."
      : "В точном prompt нет одной однозначной дословной реплики. Эту версию нельзя одобрить.",
  });
}

export function generationSpecApprovalReviewDecision({
  decision = "",
  review = null,
  spec = null,
  dirty = false,
  confirmed = false,
} = {}) {
  const normalizedDecision = clean(decision).toLowerCase();
  if (normalizedDecision === "cancel") {
    return Object.freeze({ ok: true, kind: "cancel", rpcAction: null });
  }
  if (normalizedDecision === "open") {
    const nextReview = generationSpecApprovalReviewState(spec);
    return Object.freeze({
      ok: Boolean(nextReview),
      kind: nextReview ? "open" : "stale",
      rpcAction: null,
      review: nextReview,
    });
  }
  const current = generationSpecApprovalReviewMatches(review, spec)
    && spec?.status === "draft"
    && dirty !== true;
  if (!current) {
    return Object.freeze({ ok: false, kind: "stale", rpcAction: null });
  }
  if (normalizedDecision === "revision") {
    return Object.freeze({ ok: true, kind: "revision", rpcAction: "reject" });
  }
  const speech = generationSpecSpokenReview(spec);
  if (
    normalizedDecision !== "approve"
    || confirmed !== true
    || review?.confirmed !== true
    || !speech.ready
  ) {
    return Object.freeze({ ok: false, kind: "blocked", rpcAction: null });
  }
  return Object.freeze({ ok: true, kind: "approve", rpcAction: "approve" });
}

export function generationSpecCardMarkup(state = {}, { expectedScope = null } = {}) {
  const envelope = state.data || null;
  const spec = envelope?.generationSpec || null;
  const dirty = state.dirty === true;
  const approved = Boolean(
    approvedGenerationSpecContext(envelope, { expectedScope, dirty }),
  );
  const loading = state.status === "loading" || state.saving === true;
  const next = envelope?.recommendedNextAction || null;
  const approvalReviewRequired = Boolean(
    !dirty
    && spec?.status === "draft"
    && next?.action === "approve"
    && next.requiresConfirmation === true
  );
  const approvalReviewActive = Boolean(
    approvalReviewRequired
    && generationSpecApprovalReviewMatches(state.approvalReview, spec)
  );
  const approvalReviewConfirmed = Boolean(
    approvalReviewActive && state.approvalReview?.confirmed === true
  );
  const spokenReview = generationSpecSpokenReview(spec);
  const statusLabel = loading
    ? "Проверяем серверную версию"
    : approved
      ? "Утверждено и актуально"
      : dirty
        ? "Нужна новая версия"
        : spec
          ? humanSpecStatus(spec.status)
          : "Версия ещё не подготовлена";
  const primaryAction = dirty
    ? (spec ? "patch" : "prepare")
    : approvalReviewRequired
      ? "review"
      : next?.action || (spec ? "patch" : "prepare");
  const primaryLabel = dirty
    ? spec
      ? "Сохранить правки как новую версию"
      : "Подготовить серверное ТЗ бесплатно"
    : approvalReviewRequired
      ? (approvalReviewActive ? "Продолжить проверку ТЗ" : "Открыть и проверить ТЗ")
      : next?.label || (spec
        ? "Подготовить исправленную версию"
        : "Подготовить серверное ТЗ бесплатно");
  const primaryReason = dirty
    ? "Поля изменились после последней серверной проверки. Старая версия не будет утверждена автоматически."
    : next?.reason || "Сервер зафиксирует точный prompt и его происхождение без платного вызова провайдера.";
  const controls = spec
    ? [
        ["patch", "Сохранить правки"],
        ...(approvalReviewRequired ? [] : [["approve", "Утвердить эту версию"]]),
        ["reject", "Отклонить"],
        ["revert", "Вернуть прошлую"],
        ["recompute", "Пересчитать"],
      ]
    : [["prepare", "Подготовить версию"]];
  const provenance = spec
    ? [
        spec.research_provenance
          ? `Исследование: сценарий ${spec.research_provenance.scenario_position}, draft ${spec.research_provenance.creative_brief_draft_id.slice(0, 8)}…`
          : "Исследование: не применено",
        spec.performance_policy_provenance
          ? `Performance policy: ${spec.performance_policy_provenance.policy_version}, ${spec.performance_policy_provenance.policy_hash.slice(0, 12)}…`
          : "Performance policy: не применена",
        spec.repair_provenance
          ? `QA repair: review ${spec.repair_provenance.source_review_id.slice(0, 8)}… · policy ${spec.repair_provenance.policy_hash.slice(0, 12)}…`
          : "QA repair: не применён",
      ]
    : [];
  const history = Array.isArray(envelope?.history) ? envelope.history : [];
  const aiResearchBinding = state.aiResearchBinding;
  const aiResearchBindingReady = Boolean(
    !dirty
    && spec
    && aiResearchBinding
    && String(aiResearchBinding.spec_id || "").toLowerCase() === spec.spec_id
    && Number(aiResearchBinding.spec_version) === spec.spec_version
    && String(aiResearchBinding.spec_hash || "").toLowerCase() === spec.spec_hash
    && String(aiResearchBinding.compiled_prompt_hash || "") === spec.prompt_hash
    && normalizedUuid(aiResearchBinding.selection_id)
    && [1, 2, 3].includes(Number(aiResearchBinding.recommendation_position))
    && String(aiResearchBinding.provider_prompt_fragment_version || "")
      === "ai-research-provider-fragment-v1"
    && SHA256_PATTERN.test(
      String(aiResearchBinding.provider_prompt_fragment_hash || ""),
    )
    && String(aiResearchBinding.human_intent_fragment_version || "")
      === "ai-research-human-intent-v1"
    && SHA256_PATTERN.test(
      String(aiResearchBinding.human_intent_fragment_hash || ""),
    )
    && SHA256_PATTERN.test(
      String(aiResearchBinding.prompt_binding_proof_hash || ""),
    )
    && aiResearchBinding.legacy === false
  );
  return `
    <section class="generation-spec-card generation-learning-status" id="generation-spec-card" data-state="${escapeHtml(loading ? "loading" : approved ? "approved" : dirty ? "dirty" : spec?.status || "missing")}" aria-live="polite" aria-busy="${loading ? "true" : "false"}" style="display:block !important">
      <div class="generation-spec-card__header">
        <div><p class="eyebrow">Управляемое ТЗ</p><h3>Серверная версия перед оплатой</h3></div>
        <span class="badge ${approved ? "badge-info" : "badge-warning"}">${escapeHtml(statusLabel)}</span>
      </div>
      <p class="muted tiny">Ваш замысел остаётся редактируемым. Подготовка и правка бесплатны — без вызова провайдера и списания. Платный рендер запускается только отдельным подтверждением человека.</p>
      ${aiResearchBindingReady ? `
        <dl class="generation-spec-card__meta" data-generation-spec-ai-research-binding data-selection-id="${escapeHtml(aiResearchBinding.selection_id)}" data-recommendation-position="${Number(aiResearchBinding.recommendation_position)}" data-provider-prompt-fragment-hash="${escapeHtml(aiResearchBinding.provider_prompt_fragment_hash)}">
          <div><dt>AI selection_id</dt><dd><code>${escapeHtml(aiResearchBinding.selection_id)}</code></dd></div>
          <div><dt>Выбранный вариант</dt><dd>${Number(aiResearchBinding.recommendation_position)}</dd></div>
          <div><dt>Provider kernel hash</dt><dd><code>${escapeHtml(aiResearchBinding.provider_prompt_fragment_hash)}</code></dd></div>
          <div><dt>Human intent hash</dt><dd><code>${escapeHtml(aiResearchBinding.human_intent_fragment_hash)}</code></dd></div>
          <div><dt>Binding proof hash</dt><dd><code>${escapeHtml(aiResearchBinding.prompt_binding_proof_hash)}</code></dd></div>
        </dl>
      ` : ""}
      ${spec ? `
        <dl class="generation-spec-card__meta">
          <div><dt>Версия</dt><dd>${spec.spec_version}</dd></div>
          <div><dt>Spec hash</dt><dd><code>${escapeHtml(spec.spec_hash.slice(0, 12))}…</code></dd></div>
          <div><dt>Prompt hash</dt><dd><code>${escapeHtml(spec.prompt_hash.slice(0, 12))}…</code></dd></div>
        </dl>
        <details class="generation-spec-card__prompt" ${approvalReviewActive ? "open" : ""}>
          <summary>Проверить точный prompt этой версии</summary>
          <pre>${escapeHtml(spec.compiled_prompt)}</pre>
        </details>
        <details class="generation-spec-card__provenance">
          <summary>Источники и политики этой версии</summary>
          <ul>${provenance.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </details>
      ` : ""}
      ${history.length ? `
        <details class="generation-spec-card__history">
          <summary>История решений · ${history.length}</summary>
          <ol>${history.map((item) => `
            <li>
              <strong>v${item.spec_version} · ${escapeHtml(humanSpecStatus(item.status))}</strong><br>
              <small>${escapeHtml(item.updated_at)} · prompt ${escapeHtml(item.prompt_hash.slice(0, 12))}…</small>
              <ul>
                <li>${item.research_provenance
                  ? `Research draft ${escapeHtml(item.research_provenance.creative_brief_draft_id.slice(0, 8))}… · сценарий ${item.research_provenance.scenario_position}`
                  : "Research: не применён"}</li>
                <li>${item.performance_policy_provenance
                  ? `Performance ${escapeHtml(item.performance_policy_provenance.policy_version)} · ${escapeHtml(item.performance_policy_provenance.policy_hash.slice(0, 12))}…`
                  : "Performance policy: не применена"}</li>
                <li>${item.repair_provenance
                  ? `QA ${escapeHtml(item.repair_provenance.source_review_id.slice(0, 8))}… · ${escapeHtml(item.repair_provenance.policy_hash.slice(0, 12))}…`
                  : "QA repair: не применён"}</li>
              </ul>
              ${spec && item.spec_version < spec.spec_version
                ? `<button class="btn btn-ghost btn-small" type="button" data-action="control-generation-spec" data-generation-spec-control="revert" data-target-spec-version="${item.spec_version}" ${loading ? "disabled" : ""}>Вернуть v${item.spec_version} новой версией</button>`
                : ""}
            </li>
          `).join("")}</ol>
        </details>
      ` : ""}
      ${state.error ? `<p class="alert alert-error">${escapeHtml(state.error)}</p>` : ""}
      <div class="generation-spec-card__recommendation">
        <strong>Рекомендуемый следующий шаг</strong>
        <p>${escapeHtml(primaryReason)}</p>
        <button class="btn btn-secondary btn-small" type="button" data-action="run-generation-spec-recommended-action" data-generation-spec-control="${escapeHtml(primaryAction)}" ${loading ? "disabled" : ""}>${escapeHtml(primaryLabel)}</button>
      </div>
      ${approvalReviewActive ? `
        <section class="generation-spec-card__approval-review" data-generation-spec-approval-review data-review-key="${escapeHtml(state.approvalReview.key)}" data-spec-id="${escapeHtml(state.approvalReview.specId)}" data-spec-version="${state.approvalReview.specVersion}" data-spec-hash="${escapeHtml(state.approvalReview.specHash)}" data-prompt-hash="${escapeHtml(state.approvalReview.promptHash)}" aria-label="Проверка точной версии ТЗ">
          <div>
            <p class="eyebrow">Решение человека</p>
            <h4>Проверьте эту точную версию до одобрения</h4>
            <p class="muted tiny">Подтверждение относится только к v${state.approvalReview.specVersion}, spec ${escapeHtml(state.approvalReview.specHash.slice(0, 12))}… и prompt ${escapeHtml(state.approvalReview.promptHash.slice(0, 12))}…. Любое изменение сбросит его.</p>
          </div>
          <div class="generation-spec-card__speech" data-generation-spec-spoken-review data-state="${spokenReview.ready ? "ready" : "blocked"}">
            <strong>${spokenReview.audioExpected ? "Дословная реплика" : "Звук"}</strong>
            ${spokenReview.spokenLine ? `<blockquote>«${escapeHtml(spokenReview.spokenLine)}»</blockquote>` : ""}
            <p class="muted tiny">${escapeHtml(spokenReview.message)}</p>
          </div>
          <label class="recipe-confirm">
            <input type="checkbox" data-generation-spec-approval-confirm ${approvalReviewConfirmed ? "checked" : ""} ${loading || !spokenReview.ready ? "disabled" : ""}>
            <span>Я полностью прочитал точный prompt и ${spokenReview.audioExpected ? "сверил дословную реплику" : "подтвердил режим без речи"}. Я одобряю только указанные выше version и hash.</span>
          </label>
          <div class="inline-actions">
            <button class="btn" type="button" data-action="confirm-generation-spec-approval" ${loading || !approvalReviewConfirmed || !spokenReview.ready ? "disabled" : ""}>Одобрить эту точную версию</button>
            <button class="btn btn-secondary" type="button" data-action="request-generation-spec-revision" ${loading ? "disabled" : ""}>На доработку</button>
            <button class="btn btn-ghost" type="button" data-action="cancel-generation-spec-review" ${loading ? "disabled" : ""}>Отмена</button>
          </div>
        </section>
      ` : ""}
      <details class="generation-spec-card__controls">
        <summary>Другие доступные действия</summary>
        <div class="inline-actions">
          ${controls.map(([action, label]) => `<button class="btn btn-ghost btn-small" type="button" data-action="control-generation-spec" data-generation-spec-control="${action}" ${loading || (action === "revert" && (!spec || spec.spec_version < 2)) || (dirty && ["approve", "reject", "recompute"].includes(action)) ? "disabled" : ""}>${label}</button>`).join("")}
        </div>
      </details>
    </section>
  `;
}

function normalizeGenerationSpec(value) {
  if (!hasOnlyKeys(value, [...SPEC_REQUIRED_KEYS, ...SPEC_OPTIONAL_KEYS])) return null;
  if (!SPEC_REQUIRED_KEYS.every((key) => Object.hasOwn(value, key))) return null;
  const context = normalizeGenerationSpecContext({
    spec_id: value.spec_id,
    spec_version: value.spec_version,
    spec_hash: value.spec_hash,
  });
  const status = clean(value.status).toLowerCase();
  const scope = normalizeGenerationSpecScope(value.exact_scope);
  const editableIntent = clean(value.editable_intent);
  const compiledPrompt = clean(value.compiled_prompt);
  const promptHash = clean(value.prompt_hash).toLowerCase();
  const research = normalizeResearchProvenance(value.research_provenance);
  const performance = normalizePerformanceProvenance(
    value.performance_policy_provenance,
  );
  const repair = normalizeRepairProvenance(value.repair_provenance);
  const outcomeSelectionId = value.outcome_selection_id === null
    ? null
    : normalizedUuid(value.outcome_selection_id);
  const createdAt = normalizedTimestamp(value.created_at);
  const updatedAt = normalizedTimestamp(value.updated_at);
  const approvedAt = value.approved_at === undefined || value.approved_at === null
    ? null
    : normalizedTimestamp(value.approved_at);
  if (
    !context
    || !SPEC_STATUS_SET.has(status)
    || !scope
    || editableIntent.length < 1
    || editableIntent.length > 1_200
    || compiledPrompt.length < 1
    || compiledPrompt.length > 1_200
    || !SHA256_PATTERN.test(promptHash)
    || (value.research_provenance !== null && !research)
    || (value.performance_policy_provenance !== null && !performance)
    || (value.repair_provenance !== null && !repair)
    || (value.outcome_selection_id !== null && !outcomeSelectionId)
    || !createdAt
    || !updatedAt
    || (value.approved_at !== undefined && value.approved_at !== null && !approvedAt)
    || (status === "approved" && !approvedAt)
    || (status !== "approved" && Object.hasOwn(value, "approved_at"))
  ) return null;
  return Object.freeze({
    ...context,
    status,
    exact_scope: scope,
    editable_intent: editableIntent,
    compiled_prompt: compiledPrompt,
    prompt_hash: promptHash,
    research_provenance: research,
    performance_policy_provenance: performance,
    repair_provenance: repair,
    outcome_selection_id: outcomeSelectionId,
    created_at: createdAt,
    updated_at: updatedAt,
    approved_at: approvedAt,
  });
}

function normalizeRecommendedAction(value) {
  if (!hasExactKeys(value, ACTION_KEYS)) return null;
  const code = clean(value.code).toLowerCase();
  const action = clean(value.action).toLowerCase();
  const label = clean(value.label);
  const reason = clean(value.reason);
  if (
    !/^[a-z][a-z0-9_]{2,79}$/u.test(code)
    || !CONTROL_ACTION_SET.has(action)
    || label.length < 2
    || label.length > 120
    || reason.length < 3
    || reason.length > 500
    || typeof value.requires_confirmation !== "boolean"
    || value.provider_action !== false
    || value.spend_action !== false
  ) return null;
  return Object.freeze({
    code,
    action,
    label,
    reason,
    requiresConfirmation: value.requires_confirmation,
    providerAction: false,
    spendAction: false,
  });
}

function normalizeResearchProvenance(value) {
  if (value === null) return null;
  if (!hasExactKeys(value, RESEARCH_KEYS)) return null;
  const researchId = normalizedUuid(value.research_id);
  const draftId = normalizedUuid(value.creative_brief_draft_id);
  const position = Number(value.scenario_position);
  if (!researchId || !draftId || ![1, 2, 3].includes(position)) return null;
  return Object.freeze({
    research_id: researchId,
    creative_brief_draft_id: draftId,
    scenario_position: position,
  });
}

function normalizePerformanceProvenance(value) {
  if (value === null) return null;
  if (!hasExactKeys(value, PERFORMANCE_KEYS)) return null;
  const hash = clean(value.policy_hash).toLowerCase();
  const version = clean(value.policy_version);
  if (!SHA256_PATTERN.test(hash) || version.length < 3 || version.length > 80) return null;
  return Object.freeze({ policy_hash: hash, policy_version: version });
}

function normalizeRepairProvenance(value) {
  if (value === null) return null;
  if (!hasExactKeys(value, REPAIR_KEYS)) return null;
  const sourceReviewId = normalizedUuid(value.source_review_id);
  const sourceJobId = normalizedUuid(value.source_generation_job_id);
  const hash = clean(value.policy_hash).toLowerCase();
  if (!sourceReviewId || !sourceJobId || !SHA256_PATTERN.test(hash)) return null;
  return Object.freeze({
    source_review_id: sourceReviewId,
    source_generation_job_id: sourceJobId,
    policy_hash: hash,
  });
}

function normalizedUuid(value) {
  const normalized = clean(value).toLowerCase();
  return UUID_PATTERN.test(normalized) ? normalized : "";
}

function normalizedTimestamp(value) {
  const normalized = clean(value);
  const timestamp = Date.parse(normalized);
  return normalized && Number.isFinite(timestamp) ? normalized : "";
}

function humanSpecStatus(status) {
  return {
    approved: "Утверждено и актуально",
    draft: "Черновик ждёт решения",
    rejected: "Версия отклонена",
    superseded: "Есть более новая версия",
    stale: "Источники или политика изменились",
    needs_revision: "Нужна корректировка",
  }[status] || "Нужна проверка";
}

function hasExactKeys(value, keys) {
  return isRecord(value)
    && Object.keys(value).length === keys.length
    && keys.every((key) => Object.hasOwn(value, key));
}

function hasOnlyKeys(value, keys) {
  return isRecord(value)
    && Object.keys(value).every((key) => keys.includes(key));
}

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => (
      `${JSON.stringify(key)}:${stableStringify(value[key])}`
    )).join(",")}}`;
  }
  return JSON.stringify(value);
}

function clean(value) {
  return String(value ?? "").trim();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"]/gu, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
  })[character]);
}
