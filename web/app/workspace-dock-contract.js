/*
 * Workspace Dock shortcut contract v4.9.1.
 *
 * This module owns only deterministic data validation and state transitions.
 * Rendering, command dispatch, preference transport, file authority and business
 * operations remain with their existing production owners.
 */

export const WORKSPACE_DOCK_CONTRACT_VERSION = "4.9.1";
export const WORKSPACE_DOCK_PREFERENCE_VERSION = "contentengine-dock-preferences-v3.1";
export const WORKSPACE_DOCK_PIN_HOVER_MS = 450;
export const WORKSPACE_DOCK_POINTER_SLOP_PX = 6;
export const WORKSPACE_DOCK_MINIMUM_VISIBLE_ITEMS = 6;
export const WORKSPACE_DOCK_SHORTCUT_LIMITS = Object.freeze({ files: 6, links: 6 });

export const WORKSPACE_DOCK_SHORTCUT_TYPES = Object.freeze([
  "file_shortcut",
  "internal_link_shortcut",
  "external_link_shortcut",
]);

export const WORKSPACE_DOCK_ACTIONS = Object.freeze([
  "enterEdit",
  "doneEdit",
  "cancelEdit",
  "pinApp",
  "addShortcut",
  "editExternalLink",
  "unpin",
  "pointerReorder",
  "keyboardTakeOrDrop",
  "keyboardMove",
  "keyboardDelete",
  "keyboardCancelMove",
  "authoritativeFileInvalidated",
  "pinZoneEnter",
  "pinZoneTick",
  "pinZoneLeave",
  "pinZoneDrop",
]);

// Док читается как конвейер владельца (24.08): Создать → Проверить →
// Опубликовать → Результаты. «Результаты» стоят сразу после «Опубликовать» —
// «так их хоть найти можно».
export const WORKSPACE_DOCK_DEFAULT_CATALOG = Object.freeze([
  Object.freeze({ key: "finder", kind: "app", appId: "finder", protected: true }),
  Object.freeze({ key: "research", kind: "app", appId: "research", removable: true }),
  Object.freeze({ key: "ai", kind: "app", appId: "ai", removable: true }),
  Object.freeze({ key: "create", kind: "app", appId: "create", removable: true }),
  Object.freeze({ key: "review", kind: "app", appId: "review", protected: true }),
  Object.freeze({ key: "publish", kind: "app", appId: "publish", removable: true }),
  Object.freeze({ key: "results", kind: "app", appId: "results", removable: true }),
  Object.freeze({ key: "passports", kind: "app", appId: "passports", removable: true }),
  Object.freeze({ key: "hypotheses", kind: "app", appId: "hypotheses", removable: true }),
  Object.freeze({ key: "processes", kind: "app", appId: "processes", removable: true }),
  Object.freeze({ key: "settings", kind: "app", appId: "settings", removable: true }),
  Object.freeze({ key: "trash", kind: "trash", appId: "trash", protected: true }),
]);

const DEFAULT_ORDER = Object.freeze(WORKSPACE_DOCK_DEFAULT_CATALOG.map((item) => item.key));

// Порядок эпохи до 24.08 («Результаты» вторыми). Сохранённое предпочтение,
// в точности равное старому дефолту, — это не осознанная перестановка
// человека, а снимок прежней канона: такое апгрейдим на новый конвейер.
// Любой действительно свой порядок остаётся неприкосновенным.
const LEGACY_DEFAULT_ORDERS = Object.freeze([
  Object.freeze([
    "finder", "results", "research", "ai", "create",
    "review", "publish", "processes", "settings", "trash",
  ]),
  // Дефолт эпохи до 26.08 — без «Паспортов». Сохранённый в точности такой
  // порядок — снимок прежнего канона, а не ручная перестановка: апгрейдим,
  // чтобы новое приложение появилось у всех, кто док не переставлял.
  Object.freeze([
    "finder", "research", "ai", "create", "review",
    "publish", "results", "processes", "settings", "trash",
  ]),
  // Дефолт вечера 26.08 — с «Паспортами», но ещё без «Гипотез».
  Object.freeze([
    "finder", "research", "ai", "create", "review",
    "publish", "results", "passports", "processes", "settings", "trash",
  ]),
]);

function upgradeLegacyDefaultOrder(order) {
  const plain = Array.isArray(order) ? order.map((key) => String(key)) : [];
  const isLegacyDefault = LEGACY_DEFAULT_ORDERS.some((legacy) => (
    legacy.length === plain.length
    && legacy.every((key, index) => key === plain[index])
  ));
  return isLegacyDefault ? [...DEFAULT_ORDER] : order;
}

const REQUIRED_KEYS = Object.freeze(["finder", "review", "trash"]);
const APP_DROP_TARGETS = Object.freeze(["research", "create", "review", "trash"]);
const MAX_PARSE_BYTES = 1_000_000;
const MAX_ORDER_ITEMS = 128;
const MAX_CATALOG_ITEMS = 256;
const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/u;
const SAFE_SECTION = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/u;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const CONTROL = /[\u0000-\u001F\u007F]/u;
const TRACKING_KEY = /^(?:utm_.+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|yclid|_hsenc|_hsmi)$/iu;
const SENSITIVE_KEY = /(?:^|[-_.])(?:access_?token|refresh_?token|id_?token|token|auth|authorization|api_?key|key|secret|signature|sig|credential|password|passwd|jwt|sso|session|sessionid|code|expires)(?:$|[-_.])/iu;
const SECRET_PREFIX = /^(?:bearer\s+|basic\s+|sk[-_]|pk_live_|rk_live_|gh[pousr]_|xox[baprs]-|AIza)/iu;
const JWT_VALUE = /^eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}$/u;
const FORBIDDEN_DESCRIPTOR_FIELDS = Object.freeze([
  "signedUrl",
  "signed_url",
  "accessToken",
  "access_token",
  "fileContent",
  "file_content",
  "rawFormValues",
  "raw_form_values",
  "paidConfirmation",
  "paid_confirmation",
]);

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function owns(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function safeId(value, fallback = "") {
  const candidate = typeof value === "string" ? value.trim() : "";
  return candidate && SAFE_ID.test(candidate) && !CONTROL.test(candidate) ? candidate : fallback;
}

function safeSection(value) {
  const candidate = typeof value === "string" ? value.trim().toLowerCase() : "";
  return candidate && SAFE_SECTION.test(candidate) ? candidate : "";
}

function safeLabel(value) {
  const candidate = typeof value === "string" ? value.trim() : "";
  if (!candidate || candidate.length > 160 || CONTROL.test(candidate) || tokenLike(candidate)) return "";
  return candidate;
}

function safeObjectId(value) {
  const candidate = safeId(value);
  if (!candidate || SECRET_PREFIX.test(candidate) || JWT_VALUE.test(candidate)) return "";
  return candidate;
}

function safeIsoTimestamp(value, fallback = "1970-01-01T00:00:00.000Z") {
  if (typeof value !== "string" || !value.trim()) return fallback;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : fallback;
}

function parsePreference(raw) {
  if (typeof raw !== "string") return raw;
  if (!raw || raw.length > MAX_PARSE_BYTES) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function equalJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function normalizedScope(raw, fallback = {}) {
  const source = isRecord(raw) ? raw : {};
  return {
    organizationId: safeId(
      source.organizationId ?? source.organization_id,
      safeId(fallback.organizationId ?? fallback.organization_id),
    ),
    userId: safeId(
      source.userId ?? source.user_id,
      safeId(fallback.userId ?? fallback.user_id),
    ),
  };
}

function scopeMatches(actual, expected) {
  if (!expected.organizationId || !expected.userId) return false;
  return actual.organizationId === expected.organizationId && actual.userId === expected.userId;
}

function typedShortcutPrefix(type) {
  if (type === "file_shortcut") return "file-shortcut";
  if (type === "internal_link_shortcut") return "internal-link";
  if (type === "external_link_shortcut") return "external-link";
  return "";
}

function isNewShortcutId(type, value) {
  const prefix = typedShortcutPrefix(type);
  if (!prefix || typeof value !== "string") return false;
  const [head, ...tail] = value.split(":");
  return head === prefix && tail.length === 1 && UUID.test(tail[0]);
}

export function allocateWorkspaceDockShortcutId(type, existingIds = [], uuidCandidates = []) {
  const prefix = typedShortcutPrefix(type);
  if (!prefix) return null;
  const occupied = new Set(Array.isArray(existingIds) ? existingIds.map((item) => String(item)) : []);
  const candidates = Array.isArray(uuidCandidates) ? uuidCandidates : [uuidCandidates];
  for (const rawCandidate of candidates) {
    const candidate = typeof rawCandidate === "string" ? rawCandidate.trim().toLowerCase() : "";
    if (!UUID.test(candidate)) continue;
    const shortcutId = `${prefix}:${candidate}`;
    if (!occupied.has(shortcutId)) return shortcutId;
  }
  return null;
}

function tokenLike(value) {
  if (typeof value !== "string" || !value) return false;
  if (SECRET_PREFIX.test(value) || JWT_VALUE.test(value)) return true;
  return value.length >= 40
    && /^[A-Za-z0-9_-]+$/u.test(value)
    && /[A-Za-z]/u.test(value)
    && /[0-9]/u.test(value);
}

export function normalizeWorkspaceDockExternalTarget(rawTarget) {
  if (typeof rawTarget !== "string") return { ok: false, error: "external_target_required" };
  const candidate = rawTarget.trim();
  if (!candidate || candidate.length > 4096 || CONTROL.test(candidate)) {
    return { ok: false, error: "external_target_invalid" };
  }

  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    return { ok: false, error: "external_target_invalid" };
  }
  if (parsed.protocol !== "https:") return { ok: false, error: "https_required" };
  if (parsed.username || parsed.password) return { ok: false, error: "credentials_forbidden" };
  if (!parsed.hostname) return { ok: false, error: "external_host_required" };

  let decodedPathname = parsed.pathname;
  try {
    decodedPathname = decodeURIComponent(decodedPathname);
  } catch {
    return { ok: false, error: "external_target_invalid" };
  }
  if (CONTROL.test(decodedPathname)) return { ok: false, error: "external_target_invalid" };

  const pairs = [];
  for (const [key, value] of parsed.searchParams.entries()) {
    if (CONTROL.test(key) || CONTROL.test(value)) {
      return { ok: false, error: "external_target_invalid" };
    }
    if (SENSITIVE_KEY.test(key)) return { ok: false, error: "sensitive_query_forbidden" };
    if (tokenLike(value)) return { ok: false, error: "secret_like_value_forbidden" };
    if (!TRACKING_KEY.test(key)) pairs.push([key, value]);
  }

  let decodedFragment = parsed.hash.slice(1);
  try {
    decodedFragment = decodeURIComponent(decodedFragment);
  } catch {
    return { ok: false, error: "unsafe_fragment" };
  }
  if (CONTROL.test(decodedFragment)
      || /(?:^|[?&#])(access_?token|token|secret|signature|jwt)=/iu.test(decodedFragment)
      || tokenLike(decodedFragment)) {
    return { ok: false, error: "unsafe_fragment" };
  }

  pairs.sort((left, right) => {
    if (left[0] !== right[0]) return left[0] < right[0] ? -1 : 1;
    if (left[1] === right[1]) return 0;
    return left[1] < right[1] ? -1 : 1;
  });
  parsed.search = "";
  pairs.forEach(([key, value]) => parsed.searchParams.append(key, value));
  return {
    ok: true,
    canonicalTarget: parsed.href,
    hostname: parsed.hostname.toLowerCase(),
  };
}

function normalizedInternalPolicy(raw = {}) {
  const source = isRecord(raw) ? raw : {};
  const spaces = [...new Set((Array.isArray(source.spaces) ? source.spaces : ["bombbar", "blacktiger"])
    .map((item) => safeId(item).toLowerCase())
    .filter(Boolean))];
  const apps = {};
  const rawApps = isRecord(source.apps) ? source.apps : {};
  Object.entries(rawApps).forEach(([rawAppId, rawTabs]) => {
    const appId = safeId(rawAppId).toLowerCase();
    if (!appId || !Array.isArray(rawTabs)) return;
    apps[appId] = [...new Set(rawTabs.map((item) => safeId(item).toLowerCase()).filter(Boolean))];
  });
  const defaultSpace = safeId(source.defaultSpace).toLowerCase();
  return {
    spaces,
    apps,
    defaultSpace: spaces.includes(defaultSpace) ? defaultSpace : "",
  };
}

function exactInternalId(rawValue) {
  if (typeof rawValue !== "string" || !rawValue || rawValue.length > 256 || CONTROL.test(rawValue)) {
    return "";
  }
  let decoded;
  try {
    decoded = decodeURIComponent(rawValue);
  } catch {
    return "";
  }
  return safeId(decoded);
}

export function normalizeWorkspaceDockInternalTarget(rawTarget, rawPolicy = {}) {
  if (typeof rawTarget !== "string" || CONTROL.test(rawTarget)) {
    return { ok: false, error: "internal_target_invalid" };
  }
  const candidate = rawTarget.trim();
  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    return { ok: false, error: "internal_target_invalid" };
  }
  if (parsed.protocol !== "contentengine:" || parsed.username || parsed.password || parsed.hash) {
    return { ok: false, error: "internal_target_invalid" };
  }

  const policy = normalizedInternalPolicy(rawPolicy);
  const owner = parsed.hostname.toLowerCase();
  const pathParts = parsed.pathname.split("/").filter(Boolean);
  const queryKeys = [...new Set([...parsed.searchParams.keys()])];
  if (!/^\/[^/]+$/u.test(parsed.pathname)) {
    return { ok: false, error: "internal_target_invalid" };
  }

  if (owner === "desktop") {
    const space = exactInternalId(pathParts[0] || "").toLowerCase();
    if (pathParts.length !== 1 || queryKeys.length || !policy.spaces.includes(space)) {
      return { ok: false, error: "desktop_space_not_allowed" };
    }
    return { ok: true, canonicalTarget: `contentengine://desktop/${encodeURIComponent(space)}` };
  }

  if (owner === "object" || owner === "folder") {
    const objectId = safeObjectId(exactInternalId(pathParts[0] || ""));
    if (pathParts.length !== 1 || queryKeys.length || !objectId) {
      return { ok: false, error: `${owner}_target_invalid` };
    }
    return {
      ok: true,
      canonicalTarget: `contentengine://${owner}/${encodeURIComponent(objectId)}`,
    };
  }

  if (owner !== "app" || pathParts.length !== 1) {
    return { ok: false, error: "internal_owner_not_allowed" };
  }
  const appId = exactInternalId(pathParts[0]).toLowerCase();
  const allowedTabs = policy.apps[appId];
  if (!allowedTabs) return { ok: false, error: "internal_app_not_allowed" };
  if (queryKeys.some((key) => !["space", "tab", "view"].includes(key))) {
    return { ok: false, error: "internal_query_not_allowed" };
  }
  if ([...parsed.searchParams.getAll("space")].length > 1
      || [...parsed.searchParams.getAll("tab")].length > 1
      || [...parsed.searchParams.getAll("view")].length > 1) {
    return { ok: false, error: "internal_query_ambiguous" };
  }
  const rawTab = parsed.searchParams.get("tab");
  const legacyView = parsed.searchParams.get("view");
  if (rawTab && legacyView && rawTab !== legacyView) {
    return { ok: false, error: "internal_tab_ambiguous" };
  }
  const space = exactInternalId(parsed.searchParams.get("space") || policy.defaultSpace).toLowerCase();
  const tab = exactInternalId(rawTab || legacyView || "").toLowerCase();
  if (!policy.spaces.includes(space)) return { ok: false, error: "internal_space_not_allowed" };
  if (!allowedTabs.includes(tab)) return { ok: false, error: "internal_tab_not_allowed" };
  return {
    ok: true,
    canonicalTarget: `contentengine://app/${encodeURIComponent(appId)}?space=${encodeURIComponent(space)}&tab=${encodeURIComponent(tab)}`,
    appId,
    space,
    tab,
  };
}

function normalizedCatalog(rawCatalog = WORKSPACE_DOCK_DEFAULT_CATALOG) {
  const source = Array.isArray(rawCatalog)
    ? rawCatalog
    : isRecord(rawCatalog)
      ? Object.entries(rawCatalog).map(([key, value]) => ({ key, ...(isRecord(value) ? value : {}) }))
      : WORKSPACE_DOCK_DEFAULT_CATALOG;
  const catalog = {};
  source.slice(0, MAX_CATALOG_ITEMS).forEach((raw) => {
    if (!isRecord(raw)) return;
    const key = safeId(raw.key);
    if (!key || owns(catalog, key)) return;
    const appId = safeId(raw.appId ?? raw.app_id).toLowerCase();
    catalog[key] = {
      key,
      kind: raw.kind === "trash" ? "trash" : raw.kind === "app" ? "app" : "system",
      ...(appId ? { appId } : {}),
      protected: raw.protected === true || REQUIRED_KEYS.includes(key),
      removable: raw.removable === true && !REQUIRED_KEYS.includes(key),
    };
  });
  WORKSPACE_DOCK_DEFAULT_CATALOG.forEach((raw) => {
    if (REQUIRED_KEYS.includes(raw.key) && !owns(catalog, raw.key)) catalog[raw.key] = { ...raw };
  });
  return catalog;
}

function descriptorAliases(raw, fallbackId) {
  return {
    shortcutId: raw.shortcutId ?? raw.shortcut_id ?? fallbackId,
    type: raw.type ?? raw.shortcutType ?? raw.shortcut_type,
    objectId: raw.objectId ?? raw.object_id,
    canonicalTarget: raw.canonicalTarget ?? raw.canonical_target,
    labelOverride: raw.labelOverride ?? raw.label_override,
    sectionKey: raw.sectionKey ?? raw.section_key,
    createdAt: raw.createdAt ?? raw.created_at,
  };
}

function normalizeDescriptor(raw, fallbackId, options = {}) {
  if (!isRecord(raw)) return { ok: false, error: "descriptor_invalid" };
  if (FORBIDDEN_DESCRIPTOR_FIELDS.some((field) => owns(raw, field))) {
    return { ok: false, error: "forbidden_descriptor_field" };
  }
  const migrated = descriptorAliases(raw, fallbackId);
  const type = WORKSPACE_DOCK_SHORTCUT_TYPES.includes(migrated.type) ? migrated.type : "";
  const shortcutId = safeId(migrated.shortcutId);
  if (!type || !shortcutId) return { ok: false, error: "descriptor_identity_invalid" };
  if (options.requireNewId === true && !isNewShortcutId(type, shortcutId)) {
    return { ok: false, error: "uuid_shortcut_id_required" };
  }

  const descriptor = {
    shortcutId,
    type,
    createdAt: safeIsoTimestamp(migrated.createdAt, safeIsoTimestamp(options.now)),
  };
  const labelOverride = safeLabel(migrated.labelOverride);
  const sectionKey = safeSection(migrated.sectionKey);
  if (sectionKey) descriptor.sectionKey = sectionKey;

  if (type === "file_shortcut") {
    const objectId = safeObjectId(migrated.objectId);
    if (!objectId) return { ok: false, error: "file_object_required" };
    descriptor.objectId = objectId;
    if (labelOverride) descriptor.labelOverride = labelOverride;
    return { ok: true, descriptor, dedupeKey: `file:${objectId}` };
  }

  if (type === "internal_link_shortcut") {
    const normalized = normalizeWorkspaceDockInternalTarget(
      migrated.canonicalTarget,
      options.internalPolicy,
    );
    if (!normalized.ok) return normalized;
    descriptor.canonicalTarget = normalized.canonicalTarget;
    if (labelOverride) descriptor.labelOverride = labelOverride;
    return { ok: true, descriptor, dedupeKey: `internal:${normalized.canonicalTarget}` };
  }

  const normalized = normalizeWorkspaceDockExternalTarget(migrated.canonicalTarget);
  if (!normalized.ok) return normalized;
  descriptor.canonicalTarget = normalized.canonicalTarget;
  descriptor.labelOverride = labelOverride || normalized.hostname;
  return { ok: true, descriptor, dedupeKey: `external:${normalized.canonicalTarget}` };
}

export function rehydrateWorkspaceDockCatalog(rawCatalog, rawShortcuts = {}) {
  const catalog = normalizedCatalog(rawCatalog);
  const shortcuts = isRecord(rawShortcuts) ? rawShortcuts : {};
  Object.values(shortcuts).forEach((descriptor) => {
    if (!isRecord(descriptor)) return;
    const key = safeId(descriptor.shortcutId);
    if (!key || owns(catalog, key)) return;
    catalog[key] = {
      key,
      kind: "shortcut",
      shortcutType: descriptor.type,
      ...(descriptor.objectId ? { objectId: descriptor.objectId } : {}),
      ...(descriptor.canonicalTarget ? { canonicalTarget: descriptor.canonicalTarget } : {}),
      protected: false,
      removable: true,
    };
  });
  return catalog;
}

function rootParts(parsed, expectedScope) {
  if (Array.isArray(parsed)) {
    return {
      order: parsed,
      shortcuts: {},
      scope: expectedScope,
      legacyArray: true,
      hasExplicitOrder: true,
    };
  }
  const source = isRecord(parsed) ? parsed : {};
  const rawScope = isRecord(source.scope) ? source.scope : source;
  return {
    order: Array.isArray(source.order) ? source.order : [],
    shortcuts: isRecord(source.shortcuts) ? source.shortcuts : {},
    scope: normalizedScope(rawScope, expectedScope),
    legacyArray: false,
    hasExplicitOrder: Array.isArray(source.order),
  };
}

function descriptorEntries(rawShortcuts, rawOrder) {
  const orderRank = new Map(rawOrder.map((item, index) => [String(item), index]));
  return Object.entries(rawShortcuts)
    .map(([fallbackId, descriptor], index) => ({
      fallbackId,
      descriptor,
      rank: orderRank.has(fallbackId) ? orderRank.get(fallbackId) : rawOrder.length + index,
    }))
    .sort((left, right) => left.rank - right.rank);
}

function enforceShortcutLimits(entries) {
  let fileCount = 0;
  let linkCount = 0;
  return entries.filter((entry) => {
    if (entry.descriptor.type === "file_shortcut") {
      fileCount += 1;
      return fileCount <= WORKSPACE_DOCK_SHORTCUT_LIMITS.files;
    }
    linkCount += 1;
    return linkCount <= WORKSPACE_DOCK_SHORTCUT_LIMITS.links;
  });
}

function normalizeOrder(rawOrder, shortcuts, catalog) {
  const order = [];
  const add = (value) => {
    const key = safeId(value);
    if (key && owns(catalog, key) && !order.includes(key) && order.length < MAX_ORDER_ITEMS) order.push(key);
  };
  rawOrder.forEach(add);
  Object.keys(shortcuts).forEach(add);
  REQUIRED_KEYS.forEach(add);
  const withoutFinder = order.filter((key) => key !== "finder");
  const withoutTrash = withoutFinder.filter((key) => key !== "trash");
  return ["finder", ...withoutTrash, "trash"];
}

export function normalizeWorkspaceDockPreference(rawPreference, rawOptions = {}) {
  const options = isRecord(rawOptions) ? rawOptions : {};
  const expectedScope = normalizedScope(options.scope);
  const parsed = parsePreference(rawPreference);
  const root = rootParts(parsed, expectedScope);
  const issues = [];

  if (!scopeMatches(root.scope, expectedScope)) {
    issues.push("scope_mismatch");
    const emptyCatalog = rehydrateWorkspaceDockCatalog(options.catalog, {});
    const preference = {
      version: WORKSPACE_DOCK_PREFERENCE_VERSION,
      scope: expectedScope,
      order: normalizeOrder(DEFAULT_ORDER, {}, emptyCatalog),
      shortcuts: {},
    };
    return { preference, catalog: emptyCatalog, repairRequired: true, issues };
  }

  const normalizedEntries = [];
  const keyAliases = new Map();
  const seenTargets = new Set();
  const seenIds = new Set();
  descriptorEntries(root.shortcuts, root.order).forEach((entry) => {
    const normalized = normalizeDescriptor(entry.descriptor, entry.fallbackId, {
      internalPolicy: options.internalPolicy,
      now: options.now,
    });
    if (!normalized.ok) {
      issues.push(normalized.error);
      return;
    }
    const { descriptor, dedupeKey } = normalized;
    if (seenIds.has(descriptor.shortcutId)) {
      issues.push("duplicate_shortcut_id");
      return;
    }
    if (seenTargets.has(dedupeKey)) {
      issues.push("duplicate_shortcut_target");
      return;
    }
    seenIds.add(descriptor.shortcutId);
    seenTargets.add(dedupeKey);
    keyAliases.set(entry.fallbackId, descriptor.shortcutId);
    normalizedEntries.push({ descriptor, rank: entry.rank });
  });

  const limitedEntries = enforceShortcutLimits(normalizedEntries);
  if (limitedEntries.length !== normalizedEntries.length) issues.push("shortcut_limit_exceeded");
  const shortcuts = {};
  limitedEntries.forEach(({ descriptor }) => {
    shortcuts[descriptor.shortcutId] = descriptor;
  });

  // Dynamic descriptors are deliberately rehydrated before the order is normalized.
  const catalog = rehydrateWorkspaceDockCatalog(options.catalog, shortcuts);
  const migratedOrder = upgradeLegacyDefaultOrder(
    root.order.map((key) => keyAliases.get(String(key)) || key),
  );
  const order = normalizeOrder(root.hasExplicitOrder ? migratedOrder : DEFAULT_ORDER, shortcuts, catalog);
  const preference = {
    version: WORKSPACE_DOCK_PREFERENCE_VERSION,
    scope: expectedScope,
    order,
    shortcuts,
  };
  const repairRequired = root.legacyArray
    || !isRecord(parsed)
    || !equalJson(parsed, preference);
  return { preference, catalog, repairRequired, issues };
}

export function serializeWorkspaceDockPreference(rawStateOrPreference) {
  const rawPreference = isRecord(rawStateOrPreference?.preference)
    ? rawStateOrPreference.preference
    : rawStateOrPreference;
  const source = isRecord(rawPreference) ? rawPreference : {};
  const scope = normalizedScope(source.scope);
  const shortcuts = {};
  const sourceShortcuts = isRecord(source.shortcuts) ? source.shortcuts : {};
  Object.entries(sourceShortcuts).forEach(([key, raw]) => {
    if (!isRecord(raw)) return;
    const descriptor = {
      shortcutId: safeId(raw.shortcutId, safeId(key)),
      type: WORKSPACE_DOCK_SHORTCUT_TYPES.includes(raw.type) ? raw.type : "",
      createdAt: safeIsoTimestamp(raw.createdAt),
    };
    if (!descriptor.shortcutId || !descriptor.type) return;
    if (descriptor.type === "file_shortcut") descriptor.objectId = safeObjectId(raw.objectId);
    else descriptor.canonicalTarget = typeof raw.canonicalTarget === "string" ? raw.canonicalTarget : "";
    const labelOverride = safeLabel(raw.labelOverride);
    const sectionKey = safeSection(raw.sectionKey);
    if (labelOverride) descriptor.labelOverride = labelOverride;
    if (sectionKey) descriptor.sectionKey = sectionKey;
    if ((descriptor.type === "file_shortcut" && descriptor.objectId)
        || (descriptor.type !== "file_shortcut" && descriptor.canonicalTarget)) {
      shortcuts[descriptor.shortcutId] = descriptor;
    }
  });
  const order = [];
  (Array.isArray(source.order) ? source.order : []).forEach((rawKey) => {
    const key = safeId(rawKey);
    if (key && !order.includes(key)) order.push(key);
  });
  REQUIRED_KEYS.forEach((key) => {
    if (!order.includes(key)) order.push(key);
  });
  const withoutFinder = order.filter((key) => key !== "finder");
  const withoutTrash = withoutFinder.filter((key) => key !== "trash");
  return {
    version: WORKSPACE_DOCK_PREFERENCE_VERSION,
    scope,
    order: ["finder", ...withoutTrash, "trash"],
    shortcuts,
  };
}

export function createWorkspaceDockPinZoneState() {
  return { phase: "idle", objectId: null, enteredAt: null };
}

export function workspaceDockPinZoneReducer(rawState, rawAction = {}) {
  const state = isRecord(rawState) ? rawState : createWorkspaceDockPinZoneState();
  const action = isRecord(rawAction) ? rawAction : {};
  if (action.type === "enter") {
    const objectId = safeObjectId(action.objectId ?? action.object_id);
    const enteredAt = Number(action.now);
    if (action.surface !== "empty_shelf" || action.dragKind !== "file" || !objectId
        || !Number.isFinite(enteredAt)) return createWorkspaceDockPinZoneState();
    return { phase: "arming", objectId, enteredAt };
  }
  if (action.type === "tick" && state.phase === "arming") {
    const now = Number(action.now);
    if (Number.isFinite(now) && now - state.enteredAt >= WORKSPACE_DOCK_PIN_HOVER_MS) {
      return { ...state, phase: "ready" };
    }
    return { ...state };
  }
  if (action.type === "leave" || action.type === "drop") return createWorkspaceDockPinZoneState();
  return { ...state };
}

export function classifyWorkspaceDockDrop(rawDrop = {}, rawPinZone = {}) {
  const drop = isRecord(rawDrop) ? rawDrop : {};
  const targetKey = safeId(drop.targetKey ?? drop.target_key);
  if (drop.dragKind !== "file") return { kind: "none", reason: "unsupported_drag" };
  if (drop.surface === "app_tile" && APP_DROP_TARGETS.includes(targetKey)) {
    return { kind: "app_action", appKey: targetKey };
  }
  if (drop.surface === "pin_zone"
      && rawPinZone.phase === "ready"
      && safeObjectId(rawPinZone.objectId)
      && safeObjectId(rawPinZone.objectId) === safeObjectId(drop.objectId ?? drop.object_id)) {
    return { kind: "pin_shortcut", objectId: safeObjectId(rawPinZone.objectId) };
  }
  return { kind: "none", reason: "pin_zone_not_ready" };
}

function statePolicy(rawPolicy) {
  return normalizedInternalPolicy(rawPolicy);
}

export function createWorkspaceDockState(rawPreference = {}, rawOptions = {}) {
  const options = isRecord(rawOptions) ? rawOptions : {};
  const normalized = normalizeWorkspaceDockPreference(rawPreference, options);
  return {
    version: WORKSPACE_DOCK_CONTRACT_VERSION,
    preference: normalized.preference,
    catalog: normalized.catalog,
    baseCatalog: normalizedCatalog(options.catalog),
    internalPolicy: statePolicy(options.internalPolicy),
    editSession: null,
    keyboardMove: null,
    pinZone: createWorkspaceDockPinZoneState(),
    repairRequired: normalized.repairRequired,
    issues: normalized.issues,
    effects: [],
  };
}

function freshState(rawState) {
  if (!isRecord(rawState) || !isRecord(rawState.preference)) return createWorkspaceDockState();
  return { ...rawState, issues: [], effects: [] };
}

function persistedEffect(preference, reason) {
  return {
    type: "persist_preference",
    reason,
    preference: serializeWorkspaceDockPreference(preference),
  };
}

function rebuildCatalog(state, preference) {
  return rehydrateWorkspaceDockCatalog(Object.values(state.baseCatalog), preference.shortcuts);
}

function withPreference(state, preference, reason, persistOutsideEdit = true) {
  const next = {
    ...state,
    preference,
    catalog: rebuildCatalog(state, preference),
    repairRequired: false,
  };
  if (persistOutsideEdit && !state.editSession) {
    next.effects = [persistedEffect(preference, reason)];
  }
  return next;
}

function shortcutDedupeKey(descriptor) {
  if (descriptor.type === "file_shortcut") return `file:${descriptor.objectId}`;
  if (descriptor.type === "internal_link_shortcut") return `internal:${descriptor.canonicalTarget}`;
  return `external:${descriptor.canonicalTarget}`;
}

function canAddDescriptor(preference, descriptor, ignoreShortcutId = "") {
  const descriptors = Object.values(preference.shortcuts)
    .filter((item) => item.shortcutId !== ignoreShortcutId);
  if (descriptors.some((item) => shortcutDedupeKey(item) === shortcutDedupeKey(descriptor))) {
    return "duplicate_shortcut_target";
  }
  const sameClass = descriptors.filter((item) => (
    descriptor.type === "file_shortcut"
      ? item.type === "file_shortcut"
      : item.type !== "file_shortcut"
  ));
  const limit = descriptor.type === "file_shortcut"
    ? WORKSPACE_DOCK_SHORTCUT_LIMITS.files
    : WORKSPACE_DOCK_SHORTCUT_LIMITS.links;
  return sameClass.length >= limit ? "shortcut_limit_exceeded" : "";
}

function reduceEnterEdit(state) {
  if (state.editSession) return state;
  return {
    ...state,
    editSession: { baseline: cloneJson(state.preference) },
    keyboardMove: null,
  };
}

function reduceDoneEdit(state) {
  if (!state.editSession) return state;
  // A migrated, de-duplicated or re-scoped preference is only repaired after
  // the human explicitly confirms the editor. Opening or cancelling remains a
  // zero-write operation.
  const changed = state.repairRequired === true
    || !equalJson(state.preference, state.editSession.baseline);
  return {
    ...state,
    editSession: null,
    keyboardMove: null,
    repairRequired: changed ? false : state.repairRequired,
    effects: changed ? [persistedEffect(state.preference, "edit_done")] : [],
  };
}

function reduceCancelEdit(state) {
  if (!state.editSession) return state;
  const preference = cloneJson(state.editSession.baseline);
  return {
    ...state,
    preference,
    catalog: rebuildCatalog(state, preference),
    editSession: null,
    keyboardMove: null,
    effects: [],
  };
}

function reduceAddShortcut(state, action) {
  const normalized = normalizeDescriptor(action.shortcut, action.shortcut?.shortcutId, {
    internalPolicy: state.internalPolicy,
    now: action.now,
    requireNewId: true,
  });
  if (!normalized.ok) return { ...state, issues: [normalized.error] };
  const { descriptor } = normalized;
  if (owns(state.preference.shortcuts, descriptor.shortcutId)) {
    return { ...state, issues: ["duplicate_shortcut_id"] };
  }
  const conflict = canAddDescriptor(state.preference, descriptor);
  if (conflict) return { ...state, issues: [conflict] };
  const shortcuts = { ...state.preference.shortcuts, [descriptor.shortcutId]: descriptor };
  const trashIndex = state.preference.order.indexOf("trash");
  const insertion = trashIndex < 0 ? state.preference.order.length : trashIndex;
  const order = [...state.preference.order];
  order.splice(insertion, 0, descriptor.shortcutId);
  return withPreference(state, { ...state.preference, shortcuts, order }, "shortcut_added");
}

function reducePinApp(state, action) {
  const key = safeId(action.key ?? action.appKey ?? action.app_key);
  const item = state.catalog[key] || state.baseCatalog[key];
  if (!key || !item || item.kind !== "app") {
    return { ...state, issues: ["app_not_found"] };
  }
  if (state.preference.order.includes(key)) {
    return { ...state, issues: ["app_already_pinned"] };
  }
  const order = [...state.preference.order];
  const canonicalOrder = Object.keys(state.baseCatalog);
  const canonicalIndex = canonicalOrder.indexOf(key);
  const nextPinnedKey = canonicalOrder
    .slice(canonicalIndex + 1)
    .find((candidate) => order.includes(candidate));
  const insertion = nextPinnedKey ? order.indexOf(nextPinnedKey) : order.indexOf("trash");
  order.splice(insertion < 0 ? order.length : insertion, 0, key);
  return withPreference(state, { ...state.preference, order }, "app_pinned");
}

function reduceEditExternalLink(state, action) {
  const shortcutId = safeId(action.shortcutId ?? action.shortcut_id);
  const current = state.preference.shortcuts[shortcutId];
  if (!current || current.type !== "external_link_shortcut") {
    return { ...state, issues: ["external_shortcut_not_found"] };
  }
  const normalizedTarget = normalizeWorkspaceDockExternalTarget(action.canonicalTarget ?? action.canonical_target);
  if (!normalizedTarget.ok) return { ...state, issues: [normalizedTarget.error] };
  const candidate = {
    ...current,
    canonicalTarget: normalizedTarget.canonicalTarget,
    labelOverride: safeLabel(action.labelOverride ?? action.label_override) || normalizedTarget.hostname,
  };
  const conflict = canAddDescriptor(state.preference, candidate, shortcutId);
  if (conflict) return { ...state, issues: [conflict] };
  const shortcuts = { ...state.preference.shortcuts, [shortcutId]: candidate };
  return withPreference(
    state,
    { ...state.preference, shortcuts },
    "external_shortcut_edited",
  );
}

function removableKey(state, key) {
  const item = state.catalog[key];
  return Boolean(item) && item.removable === true && item.protected !== true;
}

function removeKeyFromPreference(preference, key) {
  const shortcuts = { ...preference.shortcuts };
  delete shortcuts[key];
  return {
    ...preference,
    order: preference.order.filter((item) => item !== key),
    shortcuts,
  };
}

function reduceUnpin(state, action) {
  const key = safeId(action.shortcutId ?? action.key);
  if (!removableKey(state, key)) return { ...state, issues: ["item_not_removable"] };
  const next = withPreference(state, removeKeyFromPreference(state.preference, key), "shortcut_unpinned");
  if (state.keyboardMove?.key === key) next.keyboardMove = null;
  return next;
}

function movableBounds(order) {
  const first = order[0] === "finder" ? 1 : 0;
  const trash = order.indexOf("trash");
  return { first, last: Math.max(first, (trash < 0 ? order.length : trash) - 1) };
}

function moveKey(order, sourceKey, targetIndex) {
  const sourceIndex = order.indexOf(sourceKey);
  if (sourceIndex < 0) return order;
  const without = order.filter((key) => key !== sourceKey);
  const bounds = movableBounds(without);
  const insertion = Math.max(bounds.first, Math.min(bounds.last + 1, targetIndex));
  const next = [...without];
  next.splice(insertion, 0, sourceKey);
  return next;
}

function reducePointerReorder(state, action) {
  const sourceKey = safeId(action.sourceKey ?? action.source_key);
  const targetKey = safeId(action.targetKey ?? action.target_key);
  const movement = Number(action.movementPx ?? action.movement_px);
  const targetHalf = action.targetHalf ?? action.target_half;
  if (!Number.isFinite(movement) || movement < WORKSPACE_DOCK_POINTER_SLOP_PX) return state;
  if (!["before", "after"].includes(targetHalf)) return state;
  if (sourceKey === targetKey) return state;
  if (!removableKey(state, sourceKey) || !state.preference.order.includes(targetKey)) return state;
  const sourceIndex = state.preference.order.indexOf(sourceKey);
  const targetIndex = state.preference.order.indexOf(targetKey);
  const before = targetHalf === "before";
  const adjusted = before
    ? targetIndex - (sourceIndex < targetIndex ? 1 : 0)
    : targetIndex + (sourceIndex < targetIndex ? 0 : 1);
  const order = moveKey(state.preference.order, sourceKey, adjusted);
  if (equalJson(order, state.preference.order)) return state;
  const next = withPreference(state, { ...state.preference, order }, "pointer_reorder");
  next.effects = [
    ...(next.effects || []),
    { type: "suppress_open", key: sourceKey },
    { type: "announce", messageKey: "dock_item_moved", key: sourceKey },
  ];
  return next;
}

function reduceKeyboardTakeOrDrop(state, action) {
  const key = safeId(action.key ?? action.shortcutId);
  if (!state.keyboardMove) {
    if (!removableKey(state, key)) return state;
    return {
      ...state,
      keyboardMove: { key, baselineOrder: [...state.preference.order] },
      effects: [{ type: "announce", messageKey: "dock_item_taken", key }],
    };
  }
  if (key && key !== state.keyboardMove.key) return state;
  return {
    ...state,
    keyboardMove: null,
    effects: [{ type: "announce", messageKey: "dock_item_dropped", key: state.keyboardMove.key }],
  };
}

function reduceKeyboardMove(state, action) {
  if (!state.keyboardMove) return state;
  const key = state.keyboardMove.key;
  const currentIndex = state.preference.order.indexOf(key);
  if (currentIndex < 0) return { ...state, keyboardMove: null };
  const bounds = movableBounds(state.preference.order);
  const command = action.command;
  let targetIndex = currentIndex;
  if (command === "ArrowLeft") targetIndex -= 1;
  else if (command === "ArrowRight") targetIndex += 1;
  else if (command === "Home") targetIndex = bounds.first;
  else if (command === "End") targetIndex = bounds.last;
  else return state;
  const order = moveKey(state.preference.order, key, targetIndex);
  if (equalJson(order, state.preference.order)) return state;
  return {
    ...state,
    preference: { ...state.preference, order },
    effects: [{ type: "announce", messageKey: "dock_item_moved", key }],
  };
}

function reduceKeyboardCancel(state) {
  if (!state.keyboardMove) return state;
  return {
    ...state,
    preference: { ...state.preference, order: [...state.keyboardMove.baselineOrder] },
    keyboardMove: null,
    effects: [{ type: "announce", messageKey: "dock_move_cancelled" }],
  };
}

function reduceAuthoritativeInvalidation(state, action) {
  const objectId = safeObjectId(action.objectId ?? action.object_id);
  if (!objectId) return state;
  const ids = Object.values(state.preference.shortcuts)
    .filter((item) => item.type === "file_shortcut" && item.objectId === objectId)
    .map((item) => item.shortcutId);
  if (!ids.length) return state;
  const purge = (preference) => ids.reduce(removeKeyFromPreference, preference);
  const preference = purge(state.preference);
  const editSession = state.editSession
    ? { baseline: purge(state.editSession.baseline) }
    : null;
  const authoritativePreference = serializeWorkspaceDockPreference(
    editSession ? editSession.baseline : preference,
  );
  return {
    ...state,
    preference,
    catalog: rebuildCatalog(state, preference),
    editSession,
    keyboardMove: ids.includes(state.keyboardMove?.key) ? null : state.keyboardMove,
    effects: [{
      type: "authoritative_purge",
      shortcutIds: ids,
      objectId,
      preference: authoritativePreference,
    }],
  };
}

function reducePinZone(state, action) {
  const typeMap = {
    pinZoneEnter: "enter",
    pinZoneTick: "tick",
    pinZoneLeave: "leave",
    pinZoneDrop: "drop",
  };
  const mapped = { ...action, type: typeMap[action.type] };
  if (action.type === "pinZoneDrop") {
    const classification = classifyWorkspaceDockDrop(
      {
        surface: action.surface,
        targetKey: action.targetKey,
        dragKind: action.dragKind,
        objectId: action.objectId,
      },
      state.pinZone,
    );
    return {
      ...state,
      pinZone: workspaceDockPinZoneReducer(state.pinZone, mapped),
      effects: classification.kind === "none"
        ? []
        : [{ type: "dock_drop_intent", classification }],
    };
  }
  return {
    ...state,
    pinZone: workspaceDockPinZoneReducer(state.pinZone, mapped),
  };
}

export function workspaceDockReducer(rawState, rawAction = {}) {
  const state = freshState(rawState);
  const action = isRecord(rawAction) ? rawAction : {};
  switch (action.type) {
    case "enterEdit": return reduceEnterEdit(state);
    case "doneEdit": return reduceDoneEdit(state);
    case "cancelEdit": return reduceCancelEdit(state);
    case "pinApp": return reducePinApp(state, action);
    case "addShortcut": return reduceAddShortcut(state, action);
    case "editExternalLink": return reduceEditExternalLink(state, action);
    case "unpin": return reduceUnpin(state, action);
    case "pointerReorder": return reducePointerReorder(state, action);
    case "keyboardTakeOrDrop": return reduceKeyboardTakeOrDrop(state, action);
    case "keyboardMove": return reduceKeyboardMove(state, action);
    case "keyboardDelete": return reduceUnpin(state, { shortcutId: action.key });
    case "keyboardCancelMove": return reduceKeyboardCancel(state);
    case "authoritativeFileInvalidated": return reduceAuthoritativeInvalidation(state, action);
    case "pinZoneEnter":
    case "pinZoneTick":
    case "pinZoneLeave":
    case "pinZoneDrop":
      return reducePinZone(state, action);
    default:
      return state;
  }
}

export function resolveWorkspaceDockFileShortcut(rawDescriptor, rawObject) {
  const descriptor = isRecord(rawDescriptor) ? rawDescriptor : {};
  const objectId = safeObjectId(descriptor.objectId);
  if (descriptor.type !== "file_shortcut" || !objectId) {
    return { state: "unavailable", objectId: null, label: "Недоступно", purgeEligible: false };
  }
  const fallback = safeLabel(descriptor.labelOverride) || "Файл";
  if (!isRecord(rawObject) || safeObjectId(rawObject.objectId ?? rawObject.object_id) !== objectId) {
    return { state: "unavailable", objectId, label: fallback, purgeEligible: false };
  }
  const label = safeLabel(rawObject.name) || fallback;
  const parentId = safeId(rawObject.parentId ?? rawObject.parent_id);
  const permission = ["read", "comment", "edit", "owner"].includes(rawObject.permission)
    ? rawObject.permission
    : "read";
  const permanentlyDeleted = rawObject.permanentlyDeleted === true || rawObject.permanently_deleted === true;
  const accessRevoked = rawObject.accessState === "revoked" || rawObject.access_state === "revoked";
  if (permanentlyDeleted || accessRevoked) {
    return { state: "unavailable", objectId, label, parentId, permission, purgeEligible: true };
  }
  const trashed = rawObject.trashed === true || rawObject.trashState === "trashed" || rawObject.trash_state === "trashed";
  if (trashed) return { state: "trashed", objectId, label, parentId, permission, purgeEligible: false };
  return { state: "live", objectId, label, parentId, permission, purgeEligible: false };
}

export function selectWorkspaceDockShortcut(rawPreference, rawContext = {}, rawPolicy = {}) {
  const state = isRecord(rawPreference?.preference) ? rawPreference : null;
  const preference = state ? state.preference : rawPreference;
  const shortcuts = isRecord(preference?.shortcuts) ? Object.values(preference.shortcuts) : [];
  const context = isRecord(rawContext) ? rawContext : {};
  if (context.activeInternalTarget) {
    const normalized = normalizeWorkspaceDockInternalTarget(
      context.activeInternalTarget,
      Object.keys(rawPolicy || {}).length ? rawPolicy : state?.internalPolicy,
    );
    if (normalized.ok) {
      const exact = shortcuts.find((item) => (
        item.type === "internal_link_shortcut" && item.canonicalTarget === normalized.canonicalTarget
      ));
      if (exact) return exact.shortcutId;
    }
  }
  const quickLookObjectId = safeObjectId(context.quickLookObjectId ?? context.quick_look_object_id);
  if (quickLookObjectId) {
    const exact = shortcuts.find((item) => item.type === "file_shortcut" && item.objectId === quickLookObjectId);
    if (exact) return exact.shortcutId;
  }
  const activeAppId = safeId(context.activeAppId ?? context.active_app_id).toLowerCase();
  const finderObjectId = safeObjectId(context.finderSelectionObjectId ?? context.finder_selection_object_id);
  if (activeAppId === "finder" && finderObjectId) {
    const exact = shortcuts.find((item) => item.type === "file_shortcut" && item.objectId === finderObjectId);
    if (exact) return exact.shortcutId;
  }
  return null;
}

function activeAppCatalogKey(catalog, activeAppId) {
  const normalized = safeId(activeAppId).toLowerCase();
  if (!normalized) return "";
  return Object.values(catalog).find((item) => item.kind === "app" && item.appId === normalized)?.key || "";
}

export function injectWorkspaceDockActiveUnpinned(rawOrder, rawCatalog, activeAppId) {
  const catalog = normalizedCatalog(rawCatalog);
  const order = Array.isArray(rawOrder) ? [...rawOrder] : [];
  const activeKey = activeAppCatalogKey(catalog, activeAppId);
  if (!activeKey || order.includes(activeKey)) return { order, activeKey, injected: false };
  const trashIndex = order.indexOf("trash");
  order.splice(trashIndex < 0 ? order.length : trashIndex, 0, activeKey);
  return { order, activeKey, injected: true };
}

export function computeWorkspaceDockPresentation(rawStateOrPreference, rawOptions = {}) {
  const state = isRecord(rawStateOrPreference?.preference) ? rawStateOrPreference : null;
  const preference = state ? state.preference : rawStateOrPreference;
  const catalog = state?.catalog || rehydrateWorkspaceDockCatalog(rawOptions.catalog, preference?.shortcuts);
  const active = injectWorkspaceDockActiveUnpinned(preference?.order, Object.values(catalog), rawOptions.activeAppId);
  const selectedShortcutId = safeId(rawOptions.selectedShortcutId ?? rawOptions.selected_shortcut_id);
  const requestedCapacity = Math.round(Number(rawOptions.capacity));
  const capacity = Math.max(
    WORKSPACE_DOCK_MINIMUM_VISIBLE_ITEMS,
    Number.isFinite(requestedCapacity) ? requestedCapacity : active.order.length,
  );
  let visibleKeys = [...active.order];
  let hiddenKeys = [];
  if (active.order.length > capacity) {
    const mustKeep = new Set(["finder", "review", "trash", active.activeKey, selectedShortcutId].filter(Boolean));
    const selected = active.order.filter((key) => mustKeep.has(key));
    active.order.forEach((key) => {
      if (selected.length < capacity - 1 && !selected.includes(key)) selected.push(key);
    });
    const chosen = new Set(selected.slice(0, capacity - 1));
    visibleKeys = active.order.filter((key) => chosen.has(key));
    hiddenKeys = active.order.filter((key) => !chosen.has(key));
    const trashIndex = visibleKeys.indexOf("trash");
    visibleKeys.splice(trashIndex < 0 ? visibleKeys.length : trashIndex, 0, "__more__");
  }
  const runningAppIds = new Set((Array.isArray(rawOptions.runningAppIds) ? rawOptions.runningAppIds : [])
    .map((item) => safeId(item).toLowerCase())
    .filter(Boolean));
  if (safeId(rawOptions.activeAppId)) runningAppIds.add(safeId(rawOptions.activeAppId).toLowerCase());
  const items = visibleKeys.map((key) => {
    if (key === "__more__") return { key, kind: "overflow", running: false, selected: false };
    const item = catalog[key] || { key, kind: "unknown" };
    const running = item.kind === "app" && runningAppIds.has(item.appId);
    const selected = item.kind === "shortcut" && key === selectedShortcutId;
    return {
      ...item,
      running,
      selected,
      runningUnpinned: active.injected && key === active.activeKey,
      indicator: running ? "app_running" : selected ? "shortcut_selected" : null,
    };
  });
  return {
    capacity,
    visibleKeys,
    hiddenKeys,
    items,
    activeAppKey: active.activeKey || null,
    activeUnpinnedInjected: active.injected,
    overflow: hiddenKeys.length > 0,
  };
}
