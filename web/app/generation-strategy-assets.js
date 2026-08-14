/*
 * Pure browser contract for the server-owned generation strategy asset list.
 *
 * The browser may display IDs and verified facts, but it never receives or
 * invents storage paths, signed URLs, media hashes, source binding IDs, or a
 * duration measured on the client. Product Swap is selectable only after the
 * server MP4 probe has published a duration fact for the exact source hash.
 */

export const GENERATION_STRATEGY_ASSET_CANDIDATES_VERSION =
  "generation-strategy-asset-candidates-response-v1";

export const GENERATION_STRATEGY_ASSET_CANDIDATES_REQUEST_VERSION =
  "generation-strategy-asset-candidates-request-v1";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const CODE_PATTERN = /^[a-z0-9][a-z0-9_.-]{0,127}$/u;
const MIME_BY_KIND = Object.freeze({
  product_photo: new Set(["image/jpeg", "image/png", "image/webp"]),
  packshot: new Set(["image/jpeg", "image/png", "image/webp"]),
  creator_reference: new Set(["image/jpeg", "image/png", "image/webp"]),
  source_video: new Set(["video/mp4"]),
});
const KINDS = Object.freeze(new Set(["all", ...Object.keys(MIME_BY_KIND)]));
const STRATEGY_ROLES = Object.freeze({
  viral_avatar_ugc: new Set(["source_video", "avatar_image", "product_image"]),
  viral_product_swap: new Set([
    "source_video",
    "original_product_image",
    "new_product_image",
  ]),
  viral_rebuild: new Set(["source_video", "product_image", "style_image"]),
});
const STRATEGY_IDS = Object.freeze(Object.keys(STRATEGY_ROLES));
const TOP_KEYS = Object.freeze([
  "ok",
  "version",
  "project_id",
  "assets",
  "_meta",
  "contract",
]);
const ASSET_KEYS = Object.freeze([
  "id",
  "kind",
  "mime_type",
  "duration_seconds",
  "status",
  "rights_confirmed",
  "product_id",
  "product_identity",
  "filename",
  "exact_youtube_attached",
  "eligible_roles",
  "eligible_strategy_roles",
  "eligible",
  "blocking_codes",
  "blocking_codes_by_strategy",
  "created_at",
  "_cursor",
]);
const PRODUCT_KEYS = Object.freeze([
  "product_id",
  "sku",
  "product_name",
  "identity_verified",
]);
const ELIGIBLE_ROLE_KEYS = Object.freeze(["strategy_id", "role"]);
const CURSOR_KEYS = Object.freeze(["at", "id"]);
const META_KEYS = Object.freeze([
  "page_size",
  "has_more",
  "next_cursor",
  "kind",
  "product_id",
  "cursor_mode",
]);
const CONTRACT_KEYS = Object.freeze([
  "read_only",
  "object_names_returned",
  "hashes_returned",
  "signed_urls_returned",
  "source_video_requires_exact_youtube_attachment",
]);

class AssetContractError extends Error {
  constructor(code, field) {
    super(code);
    this.name = "AssetContractError";
    this.code = code;
    this.field = field;
  }
}

function isPlainObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactObject(value, keys, field) {
  if (!isPlainObject(value)) throw new AssetContractError("object_required", field);
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (
    actual.length !== expected.length
    || actual.some((key, index) => key !== expected[index])
  ) {
    throw new AssetContractError("object_keys_mismatch", field);
  }
  return value;
}

function exactText(value, field, maxLength = 500) {
  if (typeof value !== "string") throw new AssetContractError("text_required", field);
  const normalized = value.trim();
  if (
    !normalized
    || normalized.length > maxLength
    || /[\u0000-\u001f\u007f]/u.test(normalized)
  ) {
    throw new AssetContractError("text_invalid", field);
  }
  return normalized;
}

function exactCode(value, field) {
  const normalized = exactText(value, field, 128).toLowerCase();
  if (!CODE_PATTERN.test(normalized)) throw new AssetContractError("code_invalid", field);
  return normalized;
}

function exactUuid(value, field) {
  const normalized = exactText(value, field, 36).toLowerCase();
  if (!UUID_PATTERN.test(normalized)) throw new AssetContractError("uuid_invalid", field);
  return normalized;
}

function exactTimestamp(value, field) {
  const normalized = exactText(value, field, 64);
  const timestamp = Date.parse(normalized);
  if (!Number.isFinite(timestamp)) throw new AssetContractError("timestamp_invalid", field);
  return normalized;
}

function exactBoolean(value, field) {
  if (typeof value !== "boolean") throw new AssetContractError("boolean_required", field);
  return value;
}

function exactNullableUuid(value, field) {
  return value === null ? null : exactUuid(value, field);
}

function exactDuration(value, field) {
  if (value === null) return null;
  if (
    typeof value !== "number"
    || !Number.isFinite(value)
    || value <= 0
    || value > 3_600
    || Math.round(value * 1_000) !== value * 1_000
  ) {
    throw new AssetContractError("duration_invalid", field);
  }
  return value;
}

function exactCodes(value, field) {
  if (!Array.isArray(value) || value.length > 16) {
    throw new AssetContractError("codes_invalid", field);
  }
  const normalized = value.map((entry, index) => exactCode(entry, `${field}.${index}`));
  if (new Set(normalized).size !== normalized.length) {
    throw new AssetContractError("codes_duplicate", field);
  }
  return Object.freeze(normalized);
}

function exactCursor(value, field) {
  exactObject(value, CURSOR_KEYS, field);
  const at = exactTimestamp(value.at, `${field}.at`);
  const id = exactUuid(value.id, `${field}.id`);
  return Object.freeze({ at, id });
}

function normalizeProductIdentity(value, productId, field) {
  if (value === null) {
    if (productId !== null) {
      throw new AssetContractError("product_identity_missing", field);
    }
    return null;
  }
  exactObject(value, PRODUCT_KEYS, field);
  const identity = Object.freeze({
    product_id: exactUuid(value.product_id, `${field}.product_id`),
    sku: exactText(value.sku, `${field}.sku`, 160),
    product_name: exactText(value.product_name, `${field}.product_name`, 260),
    identity_verified: exactBoolean(
      value.identity_verified,
      `${field}.identity_verified`,
    ),
  });
  if (!identity.identity_verified || identity.product_id !== productId) {
    throw new AssetContractError("product_identity_invalid", field);
  }
  return identity;
}

function normalizeEligibleStrategyRoles(value, field) {
  if (!Array.isArray(value) || value.length > 8) {
    throw new AssetContractError("eligible_strategy_roles_invalid", field);
  }
  const seen = new Set();
  const normalized = value.map((entry, index) => {
    const itemField = `${field}.${index}`;
    exactObject(entry, ELIGIBLE_ROLE_KEYS, itemField);
    const strategyId = exactCode(entry.strategy_id, `${itemField}.strategy_id`);
    const role = exactCode(entry.role, `${itemField}.role`);
    if (!STRATEGY_ROLES[strategyId]?.has(role)) {
      throw new AssetContractError("eligible_strategy_role_invalid", itemField);
    }
    const key = `${strategyId}:${role}`;
    if (seen.has(key)) throw new AssetContractError("eligible_strategy_role_duplicate", itemField);
    seen.add(key);
    return Object.freeze({ strategy_id: strategyId, role });
  });
  return Object.freeze(normalized);
}

function normalizeBlockingByStrategy(value, field) {
  exactObject(value, STRATEGY_IDS, field);
  return Object.freeze(Object.fromEntries(STRATEGY_IDS.map((strategyId) => [
    strategyId,
    exactCodes(value[strategyId], `${field}.${strategyId}`),
  ])));
}

function normalizeAsset(value, index, projectId) {
  const field = `assets.${index}`;
  exactObject(value, ASSET_KEYS, field);
  const id = exactUuid(value.id, `${field}.id`);
  const kind = exactCode(value.kind, `${field}.kind`);
  if (!Object.hasOwn(MIME_BY_KIND, kind)) {
    throw new AssetContractError("kind_invalid", `${field}.kind`);
  }
  const mimeType = exactText(value.mime_type, `${field}.mime_type`, 100).toLowerCase();
  if (!MIME_BY_KIND[kind].has(mimeType)) {
    throw new AssetContractError("mime_type_invalid", `${field}.mime_type`);
  }
  const durationSeconds = exactDuration(
    value.duration_seconds,
    `${field}.duration_seconds`,
  );
  if (kind !== "source_video" && durationSeconds !== null) {
    throw new AssetContractError("duration_not_applicable", `${field}.duration_seconds`);
  }
  const status = exactCode(value.status, `${field}.status`);
  const rightsConfirmed = exactBoolean(
    value.rights_confirmed,
    `${field}.rights_confirmed`,
  );
  if (status !== "ready" || !rightsConfirmed) {
    throw new AssetContractError("asset_not_server_ready", field);
  }
  const productId = exactNullableUuid(value.product_id, `${field}.product_id`);
  const productIdentity = normalizeProductIdentity(
    value.product_identity,
    productId,
    `${field}.product_identity`,
  );
  const exactYoutubeAttached = exactBoolean(
    value.exact_youtube_attached,
    `${field}.exact_youtube_attached`,
  );
  if (kind === "source_video" && !exactYoutubeAttached) {
    throw new AssetContractError("source_attachment_required", field);
  }
  if (kind !== "source_video" && exactYoutubeAttached) {
    throw new AssetContractError("source_attachment_not_applicable", field);
  }
  if (!Array.isArray(value.eligible_roles) || value.eligible_roles.length > 8) {
    throw new AssetContractError("eligible_roles_invalid", `${field}.eligible_roles`);
  }
  const eligibleRoles = value.eligible_roles.map((role, roleIndex) =>
    exactCode(role, `${field}.eligible_roles.${roleIndex}`));
  if (new Set(eligibleRoles).size !== eligibleRoles.length) {
    throw new AssetContractError("eligible_roles_duplicate", `${field}.eligible_roles`);
  }
  const eligibleStrategyRoles = normalizeEligibleStrategyRoles(
    value.eligible_strategy_roles,
    `${field}.eligible_strategy_roles`,
  );
  const pairRoles = new Set(eligibleStrategyRoles.map((entry) => entry.role));
  if (eligibleRoles.some((role) => !pairRoles.has(role))) {
    throw new AssetContractError("eligible_roles_unbound", `${field}.eligible_roles`);
  }
  const eligible = exactBoolean(value.eligible, `${field}.eligible`);
  const blockingCodes = exactCodes(value.blocking_codes, `${field}.blocking_codes`);
  const blockingCodesByStrategy = normalizeBlockingByStrategy(
    value.blocking_codes_by_strategy,
    `${field}.blocking_codes_by_strategy`,
  );
  if (eligible === (blockingCodes.length > 0)) {
    throw new AssetContractError("eligible_blocker_mismatch", field);
  }
  const createdAt = exactTimestamp(value.created_at, `${field}.created_at`);
  const cursor = exactCursor(value._cursor, `${field}._cursor`);
  if (cursor.id !== id || cursor.at !== createdAt) {
    throw new AssetContractError("cursor_identity_mismatch", `${field}._cursor`);
  }
  return Object.freeze({
    id,
    kind,
    mime_type: mimeType,
    duration_seconds: durationSeconds,
    status,
    rights_confirmed: rightsConfirmed,
    product_id: productId,
    product_identity: productIdentity,
    filename: exactText(value.filename, `${field}.filename`, 255),
    exact_youtube_attached: exactYoutubeAttached,
    eligible_roles: Object.freeze(eligibleRoles),
    eligible_strategy_roles: eligibleStrategyRoles,
    eligible,
    blocking_codes: blockingCodes,
    blocking_codes_by_strategy: blockingCodesByStrategy,
    created_at: createdAt,
    _cursor: cursor,
    project_id: projectId,
  });
}

function normalizeMeta(value, field) {
  exactObject(value, META_KEYS, field);
  if (!Number.isSafeInteger(value.page_size) || value.page_size < 1 || value.page_size > 100) {
    throw new AssetContractError("page_size_invalid", `${field}.page_size`);
  }
  const hasMore = exactBoolean(value.has_more, `${field}.has_more`);
  const nextCursor = value.next_cursor === null
    ? null
    : exactCursor(value.next_cursor, `${field}.next_cursor`);
  if (hasMore !== Boolean(nextCursor)) {
    throw new AssetContractError("pagination_state_invalid", field);
  }
  const kind = exactCode(value.kind, `${field}.kind`);
  if (!KINDS.has(kind)) throw new AssetContractError("kind_invalid", `${field}.kind`);
  const cursorMode = exactCode(value.cursor_mode, `${field}.cursor_mode`);
  if (cursorMode !== "keyset_created_at_id") {
    throw new AssetContractError("cursor_mode_invalid", `${field}.cursor_mode`);
  }
  return Object.freeze({
    page_size: value.page_size,
    has_more: hasMore,
    next_cursor: nextCursor,
    kind,
    product_id: exactNullableUuid(value.product_id, `${field}.product_id`),
    cursor_mode: cursorMode,
  });
}

function normalizeContract(value, field) {
  exactObject(value, CONTRACT_KEYS, field);
  const normalized = Object.freeze({
    read_only: exactBoolean(value.read_only, `${field}.read_only`),
    object_names_returned: exactBoolean(
      value.object_names_returned,
      `${field}.object_names_returned`,
    ),
    hashes_returned: exactBoolean(value.hashes_returned, `${field}.hashes_returned`),
    signed_urls_returned: exactBoolean(
      value.signed_urls_returned,
      `${field}.signed_urls_returned`,
    ),
    source_video_requires_exact_youtube_attachment: exactBoolean(
      value.source_video_requires_exact_youtube_attachment,
      `${field}.source_video_requires_exact_youtube_attachment`,
    ),
  });
  if (
    !normalized.read_only
    || normalized.object_names_returned
    || normalized.hashes_returned
    || normalized.signed_urls_returned
    || !normalized.source_video_requires_exact_youtube_attachment
  ) {
    throw new AssetContractError("unsafe_contract", field);
  }
  return normalized;
}

export function normalizeGenerationStrategyAssetCandidates(raw, expected = {}) {
  try {
    exactObject(raw, TOP_KEYS, "response");
    if (raw.ok !== true || raw.version !== GENERATION_STRATEGY_ASSET_CANDIDATES_VERSION) {
      throw new AssetContractError("response_version_invalid", "response.version");
    }
    const projectId = exactUuid(raw.project_id, "response.project_id");
    if (expected.projectId && projectId !== exactUuid(expected.projectId, "expected.projectId")) {
      throw new AssetContractError("project_mismatch", "response.project_id");
    }
    if (!Array.isArray(raw.assets) || raw.assets.length > 100) {
      throw new AssetContractError("assets_invalid", "response.assets");
    }
    const assets = raw.assets.map((asset, index) => normalizeAsset(asset, index, projectId));
    if (new Set(assets.map((asset) => asset.id)).size !== assets.length) {
      throw new AssetContractError("asset_duplicate", "response.assets");
    }
    const meta = normalizeMeta(raw._meta, "response._meta");
    if (expected.kind && meta.kind !== exactCode(expected.kind, "expected.kind")) {
      throw new AssetContractError("kind_mismatch", "response._meta.kind");
    }
    if (
      expected.productId !== undefined
      && meta.product_id !== exactNullableUuid(expected.productId, "expected.productId")
    ) {
      throw new AssetContractError("product_mismatch", "response._meta.product_id");
    }
    if (meta.has_more && assets.length !== meta.page_size) {
      throw new AssetContractError("page_length_invalid", "response.assets");
    }
    const page = Object.freeze({
      version: raw.version,
      project_id: projectId,
      assets: Object.freeze(assets),
      _meta: meta,
      contract: normalizeContract(raw.contract, "response.contract"),
    });
    return Object.freeze({ ok: true, page, error: null });
  } catch (error) {
    return Object.freeze({
      ok: false,
      page: null,
      error: Object.freeze({
        code: error instanceof AssetContractError ? error.code : "contract_invalid",
        field: error instanceof AssetContractError ? error.field : "response",
      }),
    });
  }
}

export function generationStrategyAssetEligibility(asset, strategyId, role) {
  const normalizedStrategy = String(strategyId || "").trim().toLowerCase();
  const normalizedRole = String(role || "").trim().toLowerCase();
  if (!STRATEGY_ROLES[normalizedStrategy]?.has(normalizedRole)) {
    return Object.freeze({ eligible: false, blockers: Object.freeze(["strategy_role_invalid"]) });
  }
  if (!asset || typeof asset !== "object") {
    return Object.freeze({ eligible: false, blockers: Object.freeze(["asset_missing"]) });
  }
  const blockers = Array.isArray(asset.blocking_codes_by_strategy?.[normalizedStrategy])
    ? [...asset.blocking_codes_by_strategy[normalizedStrategy]]
    : ["asset_contract_invalid"];
  const roleAllowed = Array.isArray(asset.eligible_strategy_roles)
    && asset.eligible_strategy_roles.some((entry) => (
      entry.strategy_id === normalizedStrategy && entry.role === normalizedRole
    ));
  if (!roleAllowed && blockers.length === 0) blockers.push("strategy_role_not_eligible");
  return Object.freeze({
    eligible: asset.eligible === true && roleAllowed && blockers.length === 0,
    blockers: Object.freeze(blockers),
  });
}

export function mergeGenerationStrategyAssetPages(current, incoming) {
  if (!incoming || typeof incoming !== "object" || !Array.isArray(incoming.assets)) {
    return current || null;
  }
  if (!current) return incoming;
  if (
    current.version !== incoming.version
    || current.project_id !== incoming.project_id
    || current._meta?.kind !== incoming._meta?.kind
    || current._meta?.product_id !== incoming._meta?.product_id
  ) return incoming;
  const byId = new Map(current.assets.map((asset) => [asset.id, asset]));
  incoming.assets.forEach((asset) => byId.set(asset.id, asset));
  const assets = [...byId.values()].sort((left, right) => {
    const byDate = Date.parse(right.created_at) - Date.parse(left.created_at);
    return byDate || right.id.localeCompare(left.id);
  });
  return Object.freeze({
    ...incoming,
    assets: Object.freeze(assets),
  });
}
