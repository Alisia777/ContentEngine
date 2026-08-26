/*
 * ContentEngine Desktop Command Registry contract v4.8 / v4.9.1.
 *
 * This is a bounded, deterministic resolver. It normalizes exact targets and
 * produces at most one inert command envelope for one gesture. Existing
 * owners remain responsible for navigation, authoritative rechecks,
 * confirmations, persistence and business mutations.
 */

export const WORKSPACE_COMMAND_REGISTRY_CONTRACT_VERSION = "4.9.1";

const MAX_STABLE_ID_LENGTH = 160;
const MAX_INTERNAL_TARGET_LENGTH = 2048;
const SAFE_STABLE_ID = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,159}$/u;
const SAFE_ACTION_KEY = /^[a-z][a-z0-9]*(?:[.:-][a-z0-9]+)*$/u;
const CONTROL_OR_WHITESPACE = /[\u0000-\u0020\u007F]/u;
const SECRETISH_ID = /^(?:bearer|secret|signed[-_]?url|token|[spr]k[-_])/iu;

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function deepFreeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  Object.values(value).forEach((item) => deepFreeze(item));
  return Object.freeze(value);
}

function owns(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function hasExactKeys(value, allowed, required = allowed) {
  if (!isRecord(value)) return false;
  const allowedSet = new Set(allowed);
  const keys = Object.keys(value);
  return keys.every((key) => allowedSet.has(key))
    && required.every((key) => owns(value, key));
}

function normalizeStableId(value) {
  if (typeof value !== "string") return "";
  const candidate = value.trim();
  if (
    !candidate
    || candidate.length > MAX_STABLE_ID_LENGTH
    || candidate !== value
    || !SAFE_STABLE_ID.test(candidate)
    || SECRETISH_ID.test(candidate)
    || candidate.includes("://")
  ) return "";
  return candidate;
}

export const WORKSPACE_OBJECT_REF_TYPES = Object.freeze([
  "project",
  "folder",
  "file",
  "smart_folder",
  "alias",
  "stack",
  "content_object",
  "process",
]);

export const WORKSPACE_COMMAND_SOURCES = Object.freeze([
  "context_menu",
  "desktop",
  "dock",
  "drag_drop",
  "finder",
  "keyboard",
  "menu",
  "notification",
  "quick_look",
  "toolbar",
]);

export const WORKSPACE_INTERNAL_SPACES = Object.freeze([
  "bombbar",
  "blacktiger",
]);

export const WORKSPACE_INTERNAL_APP_TABS = deepFreeze({
  results: ["pulse", "plan", "drivers", "exceptions"],
  research: ["today", "materials", "runs", "results"],
  ai: ["today", "sources", "analyses", "decisions", "recommendations", "history"],
  create: ["material", "motion", "model", "cost"],
  review: ["mine", "rework"],
  publish: ["ready", "planned"],
  passports: [],
  hypotheses: [],
  processes: ["active", "ready", "attention"],
  settings: [],
});

export const WORKSPACE_COMMAND_AUTHORITY_STATES = deepFreeze({
  permission: ["allowed", "denied", "unknown"],
  existence: ["present", "missing", "unknown"],
  freshness: ["current", "stale", "unknown"],
});

export const WORKSPACE_COMMAND_BLOCK_REASONS = Object.freeze([
  "invalid_request",
  "unknown_action",
  "source_not_allowed",
  "invalid_target",
  "target_type_not_allowed",
  "target_conflict",
  "invalid_authority",
  "permission_denied",
  "permission_unknown",
  "target_missing",
  "existence_unknown",
  "target_stale",
  "freshness_unknown",
]);

const OBJECT_OR_ALIAS_TYPES = Object.freeze([
  "project",
  "folder",
  "file",
  "smart_folder",
  "alias",
  "stack",
  "content_object",
]);
const FILE_TYPES = Object.freeze(["file", "content_object"]);
const FOLDER_TYPES = Object.freeze(["folder"]);
const PROJECT_TYPES = Object.freeze(["project"]);

const ACTION_DEFINITIONS = deepFreeze({
  "object.create-folder": {
    targetShape: "internal",
    internalConstraint: "container",
    sources: ["context_menu", "desktop", "finder", "keyboard", "menu", "toolbar"],
    effect: "authoritative_create_request",
    navigation: "none",
  },
  "smart-folder.create": {
    targetShape: "internal",
    internalConstraint: "container",
    sources: ["context_menu", "desktop", "finder", "menu", "toolbar"],
    effect: "open_query_builder",
    navigation: "exact_owner",
  },
  "finder.open-object": {
    targetShape: "object",
    objectTypes: OBJECT_OR_ALIAS_TYPES,
    sources: ["context_menu", "desktop", "dock", "finder", "keyboard", "menu"],
    effect: "open",
    navigation: "exact_owner",
  },
  "window.open-finder": {
    targetShape: "object",
    objectTypes: ["project", "folder"],
    sources: ["context_menu", "desktop", "dock", "finder", "menu"],
    effect: "open_window",
    navigation: "exact_owner",
  },
  "dock.pin-shortcut": {
    targetShape: "object",
    objectTypes: ["project", "folder", "smart_folder", "alias"],
    sources: ["context_menu", "desktop", "dock", "finder", "menu"],
    effect: "preference_request",
    navigation: "none",
  },
  "dock.pin-file-shortcut": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "dock", "finder", "quick_look", "toolbar"],
    effect: "preference_request",
    navigation: "none",
  },
  "dock.pin-internal-shortcut": {
    targetShape: "internal",
    internalConstraint: "any",
    sources: ["context_menu", "desktop", "dock", "menu", "toolbar"],
    effect: "preference_request",
    navigation: "none",
  },
  "internal-target.open": {
    targetShape: "internal",
    internalConstraint: "any",
    sources: ["dock", "keyboard", "menu", "notification"],
    effect: "open",
    navigation: "exact_owner",
  },
  "object.open": {
    targetShape: "object",
    objectTypes: OBJECT_OR_ALIAS_TYPES,
    sources: ["context_menu", "desktop", "dock", "finder", "keyboard", "notification", "quick_look"],
    effect: "open",
    navigation: "exact_owner",
  },
  "quicklook.open": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "dock", "finder", "keyboard", "quick_look", "toolbar"],
    effect: "preview",
    navigation: "none",
  },
  "relation.add:research": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "dock", "drag_drop", "finder", "quick_look", "toolbar"],
    effect: "relation_request",
    navigation: "none",
  },
  "relation.add:create": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "dock", "drag_drop", "finder", "quick_look", "toolbar"],
    effect: "draft_attachment_request",
    navigation: "none",
  },
  "relation.add:review": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "dock", "drag_drop", "finder", "quick_look", "toolbar"],
    effect: "relation_request",
    navigation: "none",
  },
  "versions.open": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "finder", "quick_look", "toolbar"],
    effect: "open_versions",
    navigation: "none",
  },
  "trash.move": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "dock", "drag_drop", "finder", "keyboard", "quick_look"],
    effect: "reversible_mutation_request",
    navigation: "none",
  },
  "trash.restore": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "finder", "keyboard", "quick_look", "toolbar"],
    effect: "restore_request",
    navigation: "none",
  },
  "trash.delete-permanent": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "finder", "keyboard", "quick_look", "toolbar"],
    effect: "confirmation_request",
    navigation: "none",
    requiresSeparateConfirmation: true,
  },
  "object.move": {
    targetShape: "object_destination",
    objectTypes: FILE_TYPES,
    destinationTypes: FOLDER_TYPES,
    sources: ["context_menu", "drag_drop", "finder", "keyboard"],
    effect: "move_request",
    navigation: "none",
  },
  "project.transfer.prepare": {
    targetShape: "object_destination",
    objectTypes: FILE_TYPES,
    destinationTypes: PROJECT_TYPES,
    sources: ["dock", "drag_drop", "finder"],
    effect: "move_copy_decision_request",
    navigation: "none",
    decisionRequired: "move_or_copy",
  },
  "ai.open-decisions": {
    targetShape: "internal",
    internalConstraint: "ai_decisions",
    sources: ["dock", "menu", "notification"],
    effect: "open",
    navigation: "exact_owner",
  },
  "process.open": {
    targetShape: "object",
    objectTypes: ["process"],
    sources: ["dock", "menu", "notification"],
    effect: "open",
    navigation: "exact_owner",
  },
  "review.open-object": {
    targetShape: "object",
    objectTypes: FILE_TYPES,
    sources: ["context_menu", "dock", "menu", "notification"],
    effect: "open",
    navigation: "exact_owner",
  },
});

export const WORKSPACE_COMMAND_ACTIONS = Object.freeze(Object.keys(ACTION_DEFINITIONS));

export function workspaceCommandDefinition(actionKey) {
  const key = typeof actionKey === "string" ? actionKey : "";
  return ACTION_DEFINITIONS[key] || null;
}

export function normalizeWorkspaceObjectRef(raw) {
  if (!hasExactKeys(raw, ["type", "id"])) return null;
  const rawType = typeof raw.type === "string" ? raw.type.trim().toLowerCase() : "";
  const type = rawType === "smart-folder" ? "smart_folder" : rawType;
  const id = normalizeStableId(raw.id);
  if (!WORKSPACE_OBJECT_REF_TYPES.includes(type) || !id) return null;
  return deepFreeze({ type, id });
}

function decodeExactPathSegment(pathname) {
  if (typeof pathname !== "string" || !/^\/[^/]+$/u.test(pathname)) return "";
  try {
    return decodeURIComponent(pathname.slice(1));
  } catch {
    return "";
  }
}

function exactQueryValue(searchParams, key) {
  const values = searchParams.getAll(key);
  if (values.length !== 1) return "";
  const value = values[0];
  if (!value || value !== value.trim() || value !== value.toLowerCase()) return "";
  return value;
}

function internalTargetDescriptor(kind, canonicalTarget, details) {
  return deepFreeze({ kind, canonicalTarget, ...details });
}

export function normalizeWorkspaceInternalTarget(raw) {
  if (
    typeof raw !== "string"
    || !raw.startsWith("contentengine://")
    || !raw
    || raw.length > MAX_INTERNAL_TARGET_LENGTH
    || CONTROL_OR_WHITESPACE.test(raw)
    || raw.includes("#")
  ) return null;

  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    return null;
  }
  if (
    parsed.protocol !== "contentengine:"
    || parsed.username
    || parsed.password
    || parsed.port
    || parsed.hash
  ) return null;

  const host = parsed.hostname;
  if (!Object.freeze(["desktop", "object", "folder", "app"]).includes(host)) return null;
  const segment = decodeExactPathSegment(parsed.pathname);
  if (!segment) return null;

  const queryKeys = [...parsed.searchParams.keys()];
  const uniqueQueryKeys = new Set(queryKeys);
  if (queryKeys.length !== uniqueQueryKeys.size) return null;

  if (host === "desktop") {
    if (raw.includes("?") || !WORKSPACE_INTERNAL_SPACES.includes(segment)) return null;
    return internalTargetDescriptor(
      "desktop",
      `contentengine://desktop/${segment}`,
      { space: segment },
    );
  }

  if (host === "object" || host === "folder") {
    if (raw.includes("?")) return null;
    const id = normalizeStableId(segment);
    if (!id) return null;
    const type = host === "folder" ? "folder" : "content_object";
    const objectRef = deepFreeze({ type, id });
    return internalTargetDescriptor(
      host,
      `contentengine://${host}/${encodeURIComponent(id)}`,
      { objectRef },
    );
  }

  if (!owns(WORKSPACE_INTERNAL_APP_TABS, segment)) return null;
  if (!queryKeys.every((key) => ["space", "tab", "view"].includes(key))) return null;
  if (parsed.searchParams.has("tab") && parsed.searchParams.has("view")) return null;

  const space = exactQueryValue(parsed.searchParams, "space");
  if (!WORKSPACE_INTERNAL_SPACES.includes(space)) return null;
  const appTabs = WORKSPACE_INTERNAL_APP_TABS[segment];
  const tabKey = parsed.searchParams.has("tab") ? "tab" : "view";
  const tab = parsed.searchParams.has(tabKey)
    ? exactQueryValue(parsed.searchParams, tabKey)
    : "";
  if ((appTabs.length > 0 && !appTabs.includes(tab)) || (appTabs.length === 0 && tab)) return null;
  if (queryKeys.length !== (tab ? 2 : 1)) return null;

  const canonicalTarget = `contentengine://app/${segment}?space=${encodeURIComponent(space)}`
    + (tab ? `&tab=${encodeURIComponent(tab)}` : "");
  return internalTargetDescriptor(
    "app",
    canonicalTarget,
    { appId: segment, space, tab },
  );
}

function actionKeyForResult(value) {
  return typeof value === "string" && SAFE_ACTION_KEY.test(value) ? value : "";
}

function targetResult(ok, actionKey, reason, target = null) {
  return deepFreeze({
    ok,
    status: ok ? "valid" : "blocked",
    actionKey: actionKeyForResult(actionKey),
    reason: ok ? null : reason,
    target: ok ? target : null,
  });
}

function internalConstraintAllows(constraint, descriptor) {
  if (constraint === "any") return true;
  if (constraint === "container") return descriptor.kind === "desktop" || descriptor.kind === "folder";
  if (constraint === "ai_decisions") {
    return descriptor.kind === "app"
      && descriptor.appId === "ai"
      && descriptor.tab === "decisions"
      && WORKSPACE_INTERNAL_SPACES.includes(descriptor.space);
  }
  return false;
}

function normalizeObjectCommandTarget(definition, rawTarget) {
  if (!hasExactKeys(rawTarget, ["kind", "objectRef"]) || rawTarget.kind !== "object") {
    return { reason: "invalid_target" };
  }
  const objectRef = normalizeWorkspaceObjectRef(rawTarget.objectRef);
  if (!objectRef) return { reason: "invalid_target" };
  if (!definition.objectTypes.includes(objectRef.type)) return { reason: "target_type_not_allowed" };
  return { target: deepFreeze({ kind: "object", objectRef }) };
}

function normalizeInternalCommandTarget(definition, rawTarget) {
  if (!hasExactKeys(rawTarget, ["kind", "canonicalTarget"]) || rawTarget.kind !== "internal") {
    return { reason: "invalid_target" };
  }
  const descriptor = normalizeWorkspaceInternalTarget(rawTarget.canonicalTarget);
  if (!descriptor || !internalConstraintAllows(definition.internalConstraint, descriptor)) {
    return { reason: "invalid_target" };
  }
  return {
    target: deepFreeze({
      kind: "internal",
      canonicalTarget: descriptor.canonicalTarget,
      descriptor,
    }),
  };
}

function normalizeDestinationCommandTarget(definition, rawTarget) {
  if (
    !hasExactKeys(rawTarget, ["kind", "objectRef", "destinationRef"])
    || rawTarget.kind !== "object_destination"
  ) return { reason: "invalid_target" };
  const objectRef = normalizeWorkspaceObjectRef(rawTarget.objectRef);
  const destinationRef = normalizeWorkspaceObjectRef(rawTarget.destinationRef);
  if (!objectRef || !destinationRef) return { reason: "invalid_target" };
  if (!definition.objectTypes.includes(objectRef.type)) return { reason: "target_type_not_allowed" };
  if (!definition.destinationTypes.includes(destinationRef.type)) return { reason: "target_type_not_allowed" };
  if (objectRef.id === destinationRef.id) return { reason: "target_conflict" };
  return {
    target: deepFreeze({
      kind: "object_destination",
      objectRef,
      destinationRef,
    }),
  };
}

export function validateWorkspaceCommandTarget(actionKey, rawTarget) {
  const definition = workspaceCommandDefinition(actionKey);
  if (!definition) return targetResult(false, actionKey, "unknown_action");
  const normalized = definition.targetShape === "object"
    ? normalizeObjectCommandTarget(definition, rawTarget)
    : definition.targetShape === "internal"
      ? normalizeInternalCommandTarget(definition, rawTarget)
      : definition.targetShape === "object_destination"
        ? normalizeDestinationCommandTarget(definition, rawTarget)
        : { reason: "invalid_target" };
  return normalized.target
    ? targetResult(true, actionKey, null, normalized.target)
    : targetResult(false, actionKey, normalized.reason || "invalid_target");
}

function blockedCommand(actionKey, reason, blockedAt = "request") {
  return deepFreeze({
    ok: false,
    status: "blocked",
    actionKey: actionKeyForResult(actionKey),
    reason,
    blockedAt,
    envelope: null,
  });
}

function authorityRecord(raw) {
  if (!hasExactKeys(raw, ["permission", "existence", "freshness"])) return null;
  const permission = typeof raw.permission === "string" ? raw.permission : "unknown";
  const existence = typeof raw.existence === "string" ? raw.existence : "unknown";
  const freshness = typeof raw.freshness === "string" ? raw.freshness : "unknown";
  if (!WORKSPACE_COMMAND_AUTHORITY_STATES.permission.includes(permission)) return null;
  if (!WORKSPACE_COMMAND_AUTHORITY_STATES.existence.includes(existence)) return null;
  if (!WORKSPACE_COMMAND_AUTHORITY_STATES.freshness.includes(freshness)) return null;
  return { permission, existence, freshness };
}

function authorityRecords(raw, targetShape) {
  if (targetShape !== "object_destination") {
    const target = authorityRecord(raw);
    return target ? [{ blockedAt: "target", value: target }] : null;
  }
  if (!hasExactKeys(raw, ["target", "destination"])) return null;
  const target = authorityRecord(raw.target);
  const destination = authorityRecord(raw.destination);
  if (!target || !destination) return null;
  return [
    { blockedAt: "target", value: target },
    { blockedAt: "destination", value: destination },
  ];
}

function authorityFailure(records) {
  for (const record of records) {
    if (record.value.permission === "denied") {
      return { reason: "permission_denied", blockedAt: record.blockedAt };
    }
    if (record.value.permission === "unknown") {
      return { reason: "permission_unknown", blockedAt: record.blockedAt };
    }
  }
  for (const record of records) {
    if (record.value.existence === "missing") {
      return { reason: "target_missing", blockedAt: record.blockedAt };
    }
    if (record.value.existence === "unknown") {
      return { reason: "existence_unknown", blockedAt: record.blockedAt };
    }
  }
  for (const record of records) {
    if (record.value.freshness === "stale") {
      return { reason: "target_stale", blockedAt: record.blockedAt };
    }
    if (record.value.freshness === "unknown") {
      return { reason: "freshness_unknown", blockedAt: record.blockedAt };
    }
  }
  return null;
}

function normalizeCommandSource(value) {
  return typeof value === "string" && WORKSPACE_COMMAND_SOURCES.includes(value) ? value : "";
}

function commandPolicy(definition) {
  return deepFreeze({
    dispatchCount: 1,
    paidAction: false,
    startsAnalysis: false,
    startsGeneration: false,
    requiresAuthoritativeRecheck: true,
    requiresSeparateConfirmation: definition.requiresSeparateConfirmation === true,
    decisionRequired: definition.decisionRequired || null,
    effect: definition.effect,
    navigation: definition.navigation,
  });
}

export function resolveWorkspaceCommand(rawRequest) {
  if (!isRecord(rawRequest)) return blockedCommand("", "invalid_request");
  const actionKey = typeof rawRequest.actionKey === "string" ? rawRequest.actionKey : "";
  const definition = workspaceCommandDefinition(actionKey);
  if (!definition) return blockedCommand(actionKey, "unknown_action", "registry");
  if (!hasExactKeys(
    rawRequest,
    ["gestureId", "source", "actionKey", "target", "authority"],
    ["gestureId", "source", "actionKey", "target"],
  )) return blockedCommand(actionKey, "invalid_request");

  const gestureId = normalizeStableId(rawRequest.gestureId);
  if (!gestureId) return blockedCommand(actionKey, "invalid_request", "gesture");
  const source = normalizeCommandSource(rawRequest.source);
  if (!source || !definition.sources.includes(source)) {
    return blockedCommand(actionKey, "source_not_allowed", "source");
  }

  const targetValidation = validateWorkspaceCommandTarget(actionKey, rawRequest.target);
  if (!targetValidation.ok) {
    return blockedCommand(actionKey, targetValidation.reason, "target");
  }

  const records = authorityRecords(rawRequest.authority, definition.targetShape);
  if (!records) return blockedCommand(actionKey, "invalid_authority", "authority");
  const failure = authorityFailure(records);
  if (failure) return blockedCommand(actionKey, failure.reason, failure.blockedAt);

  const envelope = deepFreeze({
    version: WORKSPACE_COMMAND_REGISTRY_CONTRACT_VERSION,
    commandId: `workspace-command:${gestureId}`,
    gestureId,
    source,
    actionKey,
    target: targetValidation.target,
    policy: commandPolicy(definition),
  });
  return deepFreeze({
    ok: true,
    status: "ready",
    actionKey,
    reason: null,
    blockedAt: null,
    envelope,
  });
}
