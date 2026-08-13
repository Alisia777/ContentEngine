const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const CATEGORIES = new Set([
  "cosmetics", "baa", "sports_food", "food", "household",
  "apparel", "electronics", "other",
]);
const PLATFORMS = new Set([
  "", "instagram", "tiktok", "youtube", "vk", "telegram", "wildberries",
]);
const MODES = new Set(["mock", "real_photo", "real_gen4", "real_seedance"]);
const FORMATS = new Set(["9:16", "1:1", "16:9"]);
const DURATIONS = Object.freeze({
  real_gen4: new Set([2, 5, 8, 10]),
  real_seedance: new Set([4, 8, 12, 15]),
});

export const GENERATION_AI_RESEARCH_EDITABLE_FIELDS = Object.freeze([
  "product_category",
  "platform",
  "mode",
  "duration_seconds",
  "format",
  "brief",
]);

export const GENERATION_AI_RESEARCH_WORKING_DRAFT_RPC =
  "contentengine_generation_ai_research_working_draft";
export const GENERATION_AI_RESEARCH_RECOMMENDATION_RPC =
  "contentengine_generation_research_recommendation";

const cache = new Map();

function workingDraftRevision(value) {
  const revision = Number(value?.revision);
  return Number.isSafeInteger(revision) && revision >= 0 ? revision : -1;
}

export function preferAuthoritativeGenerationAiResearchWorkingDraft(...values) {
  return values.filter(Boolean).reduce((current, candidate) => {
    if (!current) return candidate;
    const currentRevision = workingDraftRevision(current);
    const candidateRevision = workingDraftRevision(candidate);
    if (candidateRevision > currentRevision) return candidate;
    if (candidateRevision < currentRevision) return current;
    // A cleared response wins an equal-revision tie so stale active UI can
    // never resurrect after an authoritative tombstone.
    if (candidate?.draft === null && current?.draft !== null) return candidate;
    return current;
  }, null);
}

function object(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value
    : {};
}

function uuid(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return UUID_RE.test(normalized) ? normalized : "";
}

function normalizedPosition(value) {
  const numeric = Number(value);
  return [1, 2, 3].includes(numeric) ? numeric : null;
}

export function resolveGenerationAiResearchProductIdentity(
  recommendationProductId,
  selectedMediaProductId = "",
  { requireSelectedMedia = false } = {},
) {
  const recommendationProduct = uuid(recommendationProductId);
  const selectedProduct = uuid(selectedMediaProductId);
  if (!recommendationProduct) {
    return { ok: false, code: "recommendation_product_unverified" };
  }
  if (!selectedProduct) {
    return requireSelectedMedia
      ? { ok: false, code: "selected_media_product_unverified" }
      : { ok: true, code: "authoritative_product_without_media" };
  }
  if (selectedProduct !== recommendationProduct) {
    return { ok: false, code: "product_mismatch" };
  }
  return { ok: true, code: "exact_product_match" };
}

export function resolveGenerationExpectedProductMatch({
  expectedSku = "",
  expectedProductName = "",
  candidateSku = "",
  candidateProductName = "",
} = {}) {
  const expectedSkuValue = String(expectedSku || "").trim();
  const expectedNameValue = String(expectedProductName || "").trim();
  const candidateSkuValue = String(candidateSku || "").trim();
  const candidateNameValue = String(candidateProductName || "").trim();
  const expected = Boolean(expectedSkuValue || expectedNameValue);
  if (!expected) return { required: false, ok: true, code: "expected_product_absent" };
  if (!(expectedSkuValue && expectedNameValue)) {
    return { required: true, ok: false, code: "expected_product_invalid" };
  }
  if (!(candidateSkuValue && candidateNameValue)) {
    return { required: true, ok: false, code: "candidate_product_unverified" };
  }
  if (
    candidateSkuValue !== expectedSkuValue
    || candidateNameValue !== expectedNameValue
  ) {
    return { required: true, ok: false, code: "handoff_product_mismatch" };
  }
  return { required: true, ok: true, code: "exact_handoff_product_match" };
}

function boundedString(value, limit) {
  const normalized = String(value ?? "");
  return normalized.length <= limit ? normalized : normalized.slice(0, limit);
}

function normalizedFieldNames(value, { requireOne = false } = {}) {
  if (!Array.isArray(value)) return null;
  const fields = [...new Set(value.map((item) => String(item || "").trim()))];
  if (
    fields.length > GENERATION_AI_RESEARCH_EDITABLE_FIELDS.length
    || (requireOne && !fields.length)
    || fields.some((field) => !GENERATION_AI_RESEARCH_EDITABLE_FIELDS.includes(field))
  ) return null;
  return fields;
}

function normalizedValueMap(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const result = {};
  for (const [field, raw] of Object.entries(value)) {
    if (
      !GENERATION_AI_RESEARCH_EDITABLE_FIELDS.includes(field)
      || typeof raw !== "string"
      || raw.length > 1200
    ) return null;
    result[field] = raw;
  }
  return result;
}

export function normalizeGenerationAiResearchEditableFields(value) {
  const source = object(value);
  if (
    Object.keys(source).length !== 6
    || !CATEGORIES.has(String(source.product_category || ""))
    || !PLATFORMS.has(String(source.platform ?? ""))
    || !MODES.has(String(source.generation_mode || ""))
    || !FORMATS.has(String(source.format || ""))
    || typeof source.brief !== "string"
    || source.brief.length > 1200
  ) return null;
  const mode = String(source.generation_mode);
  const duration = source.duration_seconds === null
    ? null
    : Number(source.duration_seconds);
  if (
    (DURATIONS[mode] && !DURATIONS[mode].has(duration))
    || (!DURATIONS[mode] && duration !== null)
  ) return null;
  return {
    product_category: String(source.product_category),
    platform: String(source.platform ?? ""),
    generation_mode: mode,
    duration_seconds: duration,
    format: String(source.format),
    brief: source.brief,
  };
}

function normalizeRecommendationEnvelope(value, selectionId, position) {
  const source = object(value);
  if (
    uuid(source.selection_id) !== selectionId
    || normalizedPosition(source.recommendation_position) !== position
    || uuid(source.project_id) === ""
    || uuid(source.product_id) === ""
    || !CATEGORIES.has(String(source.product_category || ""))
    || !/^[0-9a-f]{64}$/u.test(String(source.selection_hash || ""))
    || !/^[0-9a-f]{64}$/u.test(String(source.recommendation_hash || ""))
    || !source.recommendation
    || typeof source.recommendation !== "object"
    || Array.isArray(source.recommendation)
  ) return null;
  return source;
}

export function normalizeGenerationAiResearchWorkingDraftResponse(
  raw,
  expectedProjectId = "",
) {
  const source = object(raw?.data || raw);
  const projectId = uuid(source.project_id);
  const expected = uuid(expectedProjectId);
  const revision = Number(source.revision);
  const contract = object(source.contract);
  if (
    source.version !== "generation-ai-research-working-draft-v1"
    || !projectId
    || (expected && projectId !== expected)
    || !Number.isSafeInteger(revision)
    || revision < 0
    || contract.server_backed !== true
    || contract.project_shared !== true
    || contract.one_active_draft_per_project !== true
    || contract.optimistic_concurrency !== true
    || contract.financial_fields_stored !== false
    || contract.spend_confirmation_stored !== false
    || contract.authorization_stored !== false
    || contract.media_or_blobs_stored !== false
    || contract.external_call_started !== false
    || contract.paid_call_started !== false
  ) return null;
  if (source.draft === null || source.draft === undefined) {
    return { projectId, revision, draft: null, contract };
  }
  const draft = object(source.draft);
  const selectionId = uuid(draft.selection_id);
  const position = normalizedPosition(draft.recommendation_position);
  const editableFields = normalizeGenerationAiResearchEditableFields(
    draft.editable_fields,
  );
  const appliedFields = normalizedFieldNames(draft.applied_fields, {
    requireOne: true,
  });
  const touchedFields = normalizedFieldNames(draft.touched_fields);
  const previousValues = normalizedValueMap(draft.previous_values);
  const lastAppliedValues = normalizedValueMap(draft.last_applied_values);
  const recommendation = normalizeRecommendationEnvelope(
    draft.recommendation,
    selectionId,
    position,
  );
  if (
    !uuid(draft.id)
    || Number(draft.revision) !== revision
    || !selectionId
    || position === null
    || !editableFields
    || !appliedFields
    || !touchedFields
    || !previousValues
    || !lastAppliedValues
    || typeof draft.auto_apply_disabled !== "boolean"
    || !recommendation
    || uuid(recommendation.project_id) !== projectId
  ) return null;
  return {
    projectId,
    revision,
    draft: {
      id: uuid(draft.id),
      revision,
      selectionId,
      recommendationPosition: position,
      editableFields,
      appliedFields,
      touchedFields,
      previousValues,
      lastAppliedValues,
      autoApplyDisabled: draft.auto_apply_disabled === true,
      recommendation,
      updatedAt: String(draft.updated_at || ""),
      updatedBy: uuid(draft.updated_by),
    },
    contract,
  };
}

export function generationAiResearchEditableFieldsFromForm(form) {
  const read = (name) => String(form?.elements?.[name]?.value ?? "");
  const mode = read("generation_mode");
  const duration = DURATIONS[mode]
    ? Number(read("duration_seconds"))
    : null;
  return normalizeGenerationAiResearchEditableFields({
    product_category: read("product_category"),
    platform: read("platform"),
    generation_mode: mode,
    duration_seconds: duration,
    format: read("format"),
    brief: boundedString(read("brief"), 1200),
  });
}

function scopedPayload(api, payload) {
  if (typeof api?.withOrganization === "function") {
    return api.withOrganization(payload);
  }
  if (api?.organizationId) {
    return { organization_id: api.organizationId, ...payload };
  }
  return payload;
}

async function callWorkingDraft(api, payload) {
  if (typeof api?.generationAiResearchWorkingDraft === "function") {
    return api.generationAiResearchWorkingDraft(payload);
  }
  if (typeof api?.call !== "function") throw new Error("api_runtime_unavailable");
  return api.call(
    GENERATION_AI_RESEARCH_WORKING_DRAFT_RPC,
    scopedPayload(api, payload),
  );
}

export function cachedGenerationAiResearchWorkingDraft(projectId) {
  return cache.get(uuid(projectId))?.value || null;
}

export async function readGenerationAiResearchWorkingDraft(
  api,
  projectId,
  { force = false } = {},
) {
  const normalizedProjectId = uuid(projectId);
  if (!normalizedProjectId) throw new Error("workspace_project_required");
  const previous = cache.get(normalizedProjectId);
  if (!force && previous?.promise) return previous.promise;
  if (!force && previous?.value) return previous.value;
  const promise = Promise.resolve(callWorkingDraft(api, {
    action: "read",
    project_id: normalizedProjectId,
  })).then((raw) => {
    const value = normalizeGenerationAiResearchWorkingDraftResponse(
      raw,
      normalizedProjectId,
    );
    if (!value) throw new Error("generation_ai_research_working_draft_response_invalid");
    const current = cache.get(normalizedProjectId);
    const authoritative = preferAuthoritativeGenerationAiResearchWorkingDraft(
      current?.value,
      value,
    );
    if (current?.promise === promise) {
      cache.set(normalizedProjectId, { value: authoritative, promise: null });
    } else if (authoritative !== current?.value) {
      cache.set(normalizedProjectId, {
        value: authoritative,
        promise: current?.promise || null,
      });
    }
    return authoritative;
  }).catch((error) => {
    const current = cache.get(normalizedProjectId);
    if (current?.promise === promise) {
      if (current.value) {
        cache.set(normalizedProjectId, { value: current.value, promise: null });
      } else {
        cache.delete(normalizedProjectId);
      }
    }
    throw error;
  });
  cache.set(normalizedProjectId, {
    value: previous?.value || null,
    promise,
  });
  return promise;
}

function mutationId() {
  if (typeof globalThis.crypto?.randomUUID !== "function") {
    throw new Error("secure_mutation_id_unavailable");
  }
  return globalThis.crypto.randomUUID();
}

export async function saveGenerationAiResearchWorkingDraft(
  api,
  projectId,
  state,
  expectedRevision,
) {
  const normalizedProjectId = uuid(projectId);
  const selectionId = uuid(state?.selectionId || state?.selection_id);
  const position = normalizedPosition(
    state?.recommendationPosition ?? state?.recommendation_position,
  );
  const editableFields = normalizeGenerationAiResearchEditableFields(
    state?.editableFields || state?.editable_fields,
  );
  const appliedFields = normalizedFieldNames(
    state?.appliedFields || state?.applied_fields,
    { requireOne: true },
  );
  const touchedFields = normalizedFieldNames(
    state?.touchedFields || state?.touched_fields || [],
  );
  const previousValues = normalizedValueMap(
    state?.previousValues || state?.previous_values || {},
  );
  const lastAppliedValues = normalizedValueMap(
    state?.lastAppliedValues || state?.last_applied_values || {},
  );
  const revision = Number(expectedRevision);
  if (
    !normalizedProjectId
    || !selectionId
    || position === null
    || !editableFields
    || !appliedFields
    || !touchedFields
    || !previousValues
    || !lastAppliedValues
    || !Number.isSafeInteger(revision)
    || revision < 0
  ) throw new Error("generation_ai_research_working_draft_payload_invalid");
  const raw = await callWorkingDraft(api, {
    action: "save",
    project_id: normalizedProjectId,
    expected_revision: revision,
    mutation_id: mutationId(),
    selection_id: selectionId,
    recommendation_position: position,
    editable_fields: editableFields,
    applied_fields: appliedFields,
    touched_fields: touchedFields,
    previous_values: previousValues,
    last_applied_values: lastAppliedValues,
    auto_apply_disabled: state?.autoApplyDisabled === true
      || state?.auto_apply_disabled === true,
  });
  const value = normalizeGenerationAiResearchWorkingDraftResponse(
    raw,
    normalizedProjectId,
  );
  if (!value?.draft) {
    throw new Error("generation_ai_research_working_draft_response_invalid");
  }
  const current = cache.get(normalizedProjectId);
  const authoritative = preferAuthoritativeGenerationAiResearchWorkingDraft(
    current?.value,
    value,
  );
  cache.set(normalizedProjectId, {
    value: authoritative,
    promise: current?.promise || null,
  });
  if (authoritative !== value) {
    throw new Error("generation_ai_research_working_draft_response_superseded");
  }
  return authoritative;
}

export async function clearGenerationAiResearchWorkingDraft(
  api,
  projectId,
  expectedRevision,
) {
  const normalizedProjectId = uuid(projectId);
  const revision = Number(expectedRevision);
  if (
    !normalizedProjectId
    || !Number.isSafeInteger(revision)
    || revision < 0
  ) throw new Error("generation_ai_research_working_draft_payload_invalid");
  const raw = await callWorkingDraft(api, {
    action: "clear",
    project_id: normalizedProjectId,
    expected_revision: revision,
    mutation_id: mutationId(),
  });
  const value = normalizeGenerationAiResearchWorkingDraftResponse(
    raw,
    normalizedProjectId,
  );
  if (!value || value.draft !== null) {
    throw new Error("generation_ai_research_working_draft_response_invalid");
  }
  const current = cache.get(normalizedProjectId);
  const authoritative = preferAuthoritativeGenerationAiResearchWorkingDraft(
    current?.value,
    value,
  );
  cache.set(normalizedProjectId, {
    value: authoritative,
    promise: current?.promise || null,
  });
  if (authoritative !== value) {
    throw new Error("generation_ai_research_working_draft_response_superseded");
  }
  return authoritative;
}

export function invalidateGenerationAiResearchWorkingDraft(projectId) {
  cache.delete(uuid(projectId));
}
