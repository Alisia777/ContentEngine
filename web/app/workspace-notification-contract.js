/*
 * Workspace Notification Center data contract v4.9.1.
 *
 * This module owns only deterministic record validation, recipient admission,
 * expiry, replacement/dedupe, read-state transitions, filtering and inert
 * action intents. It deliberately has no DOM, router, storage, transport,
 * permission or command-dispatch authority. Exact command execution remains
 * with workspace-command-registry.js after an authoritative recheck.
 */

export const WORKSPACE_NOTIFICATION_CONTRACT_VERSION = "4.9.1";
export const WORKSPACE_NOTIFICATION_READ_STATE_VERSION =
  "contentengine-notification-read-v4.9.1";

export const WORKSPACE_NOTIFICATION_TYPES = Object.freeze([
  "action_required",
  "mention",
  "assignment",
  "process_complete",
  "warning",
  "error",
  "access_change",
  "system_info",
]);

export const WORKSPACE_NOTIFICATION_SEVERITIES = Object.freeze([
  "neutral",
  "info",
  "success",
  "warning",
  "danger",
]);

export const WORKSPACE_NOTIFICATION_FILTERS = Object.freeze([
  "all",
  "unread",
  "action_required",
  "mentions",
  "processes",
  "system",
]);

/*
 * This is the Notification Center's exact accepted vocabulary, not a second
 * command registry. The module only emits an inert intent for one of these
 * keys; it never imports, copies or executes command definitions.
 */
export const WORKSPACE_NOTIFICATION_ACTION_KEYS = Object.freeze([
  "ai.open-decisions",
  "process.open",
  "review.open-object",
  "object.open",
]);

export const WORKSPACE_NOTIFICATION_ACTION_STATES = Object.freeze([
  "none",
  "inert",
  "blocked",
]);

const TYPE_SEVERITY = Object.freeze({
  action_required: "warning",
  mention: "info",
  assignment: "info",
  process_complete: "success",
  warning: "warning",
  error: "danger",
  access_change: "neutral",
  system_info: "neutral",
});

const FIXED_REQUIRES_ACTION = Object.freeze({
  action_required: true,
  assignment: true,
  process_complete: false,
  warning: true,
  error: true,
  system_info: false,
});

const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/u;
const BIDI_OVERRIDE = /[\u202A-\u202E\u2066-\u2069]/gu;
const WHITESPACE = /\s/u;
const SAFE_ACTION_KEY = /^[a-z][a-z0-9]*(?:[.:-][a-z0-9]+)*$/u;
const ISO_TIMESTAMP =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})$/u;
const FORBIDDEN_PAYLOAD_KEY = /^(?:access[_-]?token|refresh[_-]?token|id[_-]?token|token|authorization|auth|api[_-]?key|secret|signature|credential|password|passwd|cookie|session|session[_-]?id|jwt|signed[_-]?url|action[_-]?payload|raw[_-]?(?:data|payload|form|form[_-]?values|response)|file[_-]?(?:content|bytes)|provider[_-]?(?:payload|response)|paid[_-]?confirmation|prompt)$/iu;
const SECRET_VALUE = /(?:^\s*(?:bearer|basic)\s+[A-Za-z0-9+/=_-]+|^(?:sk[-_]|rk_live_|pk_live_|gh[pousr]_|xox[baprs]-|AIza)[A-Za-z0-9_-]+|^eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}$|[?#&](?:access_?token|refresh_?token|token|secret|signature|jwt|api_?key)=)/iu;

const FIELD_ALIASES = Object.freeze({
  notificationId: ["notificationId", "notification_id"],
  organizationId: ["organizationId", "organization_id"],
  recipientUserId: ["recipientUserId", "recipient_user_id"],
  recipientRoleId: ["recipientRoleId", "recipient_role_id"],
  recipientRoleIds: ["recipientRoleIds", "recipient_role_ids"],
  dedupeKey: ["dedupeKey", "dedupe_key"],
  type: ["type"],
  severity: ["severity"],
  sourceSection: ["sourceSection", "source_section"],
  title: ["title"],
  body: ["body"],
  createdAt: ["createdAt", "created_at"],
  expiresAt: ["expiresAt", "expires_at"],
  resolvedAt: ["resolvedAt", "resolved_at"],
  requiresAction: ["requiresAction", "requires_action"],
  projectId: ["projectId", "project_id"],
  objectId: ["objectId", "object_id"],
  processId: ["processId", "process_id"],
  actionKey: ["actionKey", "action_key"],
});

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function owns(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function deepFreeze(value, seen = new WeakSet()) {
  if (!value || typeof value !== "object" || seen.has(value)) return value;
  seen.add(value);
  Object.values(value).forEach((item) => deepFreeze(item, seen));
  return Object.freeze(value);
}

function equivalentAliasValues(left, right) {
  if (Object.is(left, right)) return true;
  if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) return false;
  return left.every((value, index) => Object.is(value, right[index]));
}

function aliasValue(source, field, issues) {
  const aliases = FIELD_ALIASES[field];
  const present = aliases.filter((key) => owns(source, key));
  if (!present.length) return undefined;
  const value = source[present[0]];
  if (present.slice(1).some((key) => !equivalentAliasValues(value, source[key]))) {
    issues.push(`ambiguous_${field}`);
  }
  return value;
}

function sanitizedText(value, maxLength, { required = false } = {}) {
  if (value === undefined || value === null) return required ? null : "";
  if (typeof value !== "string" || CONTROL.test(value)) return null;
  const normalized = value
    .replace(/\r\n?/gu, "\n")
    .replace(BIDI_OVERRIDE, "")
    .normalize("NFC")
    .trim();
  if ((required && !normalized) || normalized.length > maxLength || SECRET_VALUE.test(normalized)) {
    return null;
  }
  return normalized;
}

function stableId(value, { required = false } = {}) {
  const candidate = sanitizedText(value, 256, { required });
  if (candidate === null) return null;
  if (!candidate) return required ? null : "";
  return WHITESPACE.test(candidate) ? null : candidate;
}

function canonicalTimestamp(value, { required = false, nullable = false } = {}) {
  if ((value === undefined || value === null) && nullable) return null;
  if (value === undefined || value === null || value === "") return required ? null : "";
  if (typeof value !== "string" || !ISO_TIMESTAMP.test(value.trim())) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? new Date(parsed).toISOString() : null;
}

function containsSensitivePayload(value, seen = new WeakSet(), depth = 0) {
  if (typeof value === "string") return SECRET_VALUE.test(value);
  if (!value || typeof value !== "object") return false;
  if (seen.has(value) || depth > 12) return false;
  seen.add(value);
  if (Array.isArray(value)) {
    return value.some((item) => containsSensitivePayload(item, seen, depth + 1));
  }
  return Object.entries(value).some(([key, item]) => (
    FORBIDDEN_PAYLOAD_KEY.test(key)
    || containsSensitivePayload(item, seen, depth + 1)
  ));
}

function uniqueIssues(issues) {
  return [...new Set(issues)];
}

function normalizeRoleList(raw, fieldWasPresent, issues) {
  if (!fieldWasPresent) return [];
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > 64) {
    issues.push("recipient_roles_invalid");
    return [];
  }
  const values = [];
  raw.forEach((item) => {
    const roleId = stableId(item, { required: true });
    if (!roleId) {
      issues.push("recipient_roles_invalid");
      return;
    }
    if (!values.includes(roleId)) values.push(roleId);
  });
  return values.sort((left, right) => left.localeCompare(right));
}

function addOptionalId(notification, field, raw, issues) {
  if (raw === undefined || raw === null) return;
  const value = stableId(raw, { required: true });
  if (!value) issues.push(`${field}_invalid`);
  else notification[field] = value;
}

function addOptionalTimestamp(notification, field, raw, issues) {
  if (raw === undefined) return;
  const value = canonicalTimestamp(raw, { nullable: true });
  if (value === null && raw !== null) issues.push(`${field}_invalid`);
  else notification[field] = value;
}

export function normalizeWorkspaceNotification(rawNotification) {
  if (!isRecord(rawNotification)) {
    return deepFreeze({ ok: false, notification: null, legacyExpired: false, issues: ["record_invalid"] });
  }

  const issues = [];
  if (containsSensitivePayload(rawNotification)) issues.push("sensitive_payload_rejected");

  const values = {};
  Object.keys(FIELD_ALIASES).forEach((field) => {
    values[field] = aliasValue(rawNotification, field, issues);
  });

  const notificationId = stableId(values.notificationId, { required: true });
  if (!notificationId) issues.push("notification_id_invalid");

  const rawType = sanitizedText(values.type, 64, { required: true });
  const type = rawType === "system" ? "system_info" : rawType;
  if (!WORKSPACE_NOTIFICATION_TYPES.includes(type)) issues.push("type_invalid");

  const severity = sanitizedText(values.severity, 32, { required: true });
  if (!WORKSPACE_NOTIFICATION_SEVERITIES.includes(severity)) issues.push("severity_invalid");
  if (TYPE_SEVERITY[type] && severity && TYPE_SEVERITY[type] !== severity) {
    issues.push("severity_type_mismatch");
  }

  const sourceSection = sanitizedText(values.sourceSection, 64, { required: true });
  const title = sanitizedText(values.title, 140, { required: true });
  const body = sanitizedText(values.body, 500, { required: true });
  if (!sourceSection) issues.push("source_section_invalid");
  if (!title) issues.push("title_invalid");
  if (!body) issues.push("body_invalid");

  const createdAt = canonicalTimestamp(values.createdAt, { required: true });
  if (!createdAt) issues.push("created_at_invalid");

  const requiresAction = values.requiresAction;
  if (typeof requiresAction !== "boolean") issues.push("requires_action_invalid");
  if (
    typeof requiresAction === "boolean"
    && owns(FIXED_REQUIRES_ACTION, type)
    && FIXED_REQUIRES_ACTION[type] !== requiresAction
  ) issues.push("requires_action_type_mismatch");

  const notification = {
    notificationId: notificationId || "",
    type: WORKSPACE_NOTIFICATION_TYPES.includes(type) ? type : "system_info",
    severity: WORKSPACE_NOTIFICATION_SEVERITIES.includes(severity) ? severity : "neutral",
    sourceSection: sourceSection || "",
    title: title || "",
    body: body || "",
    createdAt: createdAt || "1970-01-01T00:00:00.000Z",
    requiresAction: requiresAction === true,
  };

  addOptionalId(notification, "organizationId", values.organizationId, issues);
  addOptionalId(notification, "recipientUserId", values.recipientUserId, issues);
  addOptionalId(notification, "recipientRoleId", values.recipientRoleId, issues);

  const roleListPresent = FIELD_ALIASES.recipientRoleIds.some((key) => owns(rawNotification, key));
  const recipientRoleIds = normalizeRoleList(values.recipientRoleIds, roleListPresent, issues);
  if (roleListPresent && recipientRoleIds.length) notification.recipientRoleIds = recipientRoleIds;

  const rawDedupeKey = values.dedupeKey;
  if (rawDedupeKey !== undefined && rawDedupeKey !== null) {
    const dedupeKey = sanitizedText(rawDedupeKey, 512, { required: true });
    if (!dedupeKey || CONTROL.test(dedupeKey)) issues.push("dedupe_key_invalid");
    else notification.dedupeKey = dedupeKey;
  }

  addOptionalTimestamp(notification, "expiresAt", values.expiresAt, issues);
  addOptionalTimestamp(notification, "resolvedAt", values.resolvedAt, issues);
  addOptionalId(notification, "projectId", values.projectId, issues);
  addOptionalId(notification, "objectId", values.objectId, issues);
  addOptionalId(notification, "processId", values.processId, issues);

  if (values.actionKey !== undefined && values.actionKey !== null) {
    const actionKey = sanitizedText(values.actionKey, 120, { required: true });
    if (!actionKey || !SAFE_ACTION_KEY.test(actionKey)) issues.push("action_key_invalid");
    else notification.actionKey = actionKey;
  }

  let legacyExpired = false;
  if (owns(rawNotification, "expired")) {
    if (typeof rawNotification.expired !== "boolean") issues.push("legacy_expired_invalid");
    else legacyExpired = rawNotification.expired;
  }

  const finalIssues = uniqueIssues(issues);
  if (finalIssues.length) {
    return deepFreeze({ ok: false, notification: null, legacyExpired, issues: finalIssues });
  }
  return deepFreeze({ ok: true, notification, legacyExpired, issues: [] });
}

function nowMilliseconds(value) {
  if (value instanceof Date) return value.getTime();
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

export function isWorkspaceNotificationExpired(rawNotification, now) {
  const normalized = normalizeWorkspaceNotification(rawNotification);
  if (!normalized.ok || normalized.legacyExpired) return true;
  const expiresAt = normalized.notification.expiresAt;
  if (!expiresAt) return false;
  const currentTime = nowMilliseconds(now);
  return currentTime === null || Date.parse(expiresAt) <= currentTime;
}

function normalizeRecipientContext(rawContext) {
  const source = isRecord(rawContext) ? rawContext : {};
  const organizationId = stableId(
    source.organizationId ?? source.organization_id ?? source.activeOrganizationId,
  );
  const userId = stableId(
    source.userId ?? source.user_id ?? source.recipientUserId ?? source.activeUserId,
  );
  const rawRoles = source.roleIds
    ?? source.role_ids
    ?? source.activeRoleIds
    ?? source.recipientRoleIds
    ?? [];
  const roleIds = [];
  const candidates = Array.isArray(rawRoles) ? rawRoles : [rawRoles];
  candidates.forEach((item) => {
    const roleId = stableId(item);
    if (roleId && !roleIds.includes(roleId)) roleIds.push(roleId);
  });
  const singularRole = stableId(source.roleId ?? source.role_id ?? source.recipientRoleId);
  if (singularRole && !roleIds.includes(singularRole)) roleIds.push(singularRole);
  return { organizationId: organizationId || "", userId: userId || "", roleIds };
}

export function workspaceNotificationMatchesRecipient(rawNotification, rawContext) {
  const normalized = normalizeWorkspaceNotification(rawNotification);
  if (!normalized.ok) return false;
  const notification = normalized.notification;
  const context = normalizeRecipientContext(rawContext);
  if (!context.organizationId || !context.userId) return false;
  if (notification.organizationId && notification.organizationId !== context.organizationId) return false;
  if (notification.recipientUserId && notification.recipientUserId !== context.userId) return false;
  if (
    notification.recipientRoleId
    && !context.roleIds.includes(notification.recipientRoleId)
  ) return false;
  if (
    notification.recipientRoleIds?.length
    && !notification.recipientRoleIds.some((roleId) => context.roleIds.includes(roleId))
  ) return false;
  return true;
}

function requiredReadScope(rawScope) {
  const scope = normalizeRecipientContext(rawScope);
  return scope.organizationId && scope.userId
    ? { organizationId: scope.organizationId, userId: scope.userId }
    : null;
}

function normalizedReadIds(rawIds) {
  if (!Array.isArray(rawIds)) return [];
  const ids = [];
  rawIds.forEach((item) => {
    const id = stableId(item);
    if (id && !ids.includes(id)) ids.push(id);
  });
  return ids.sort((left, right) => left.localeCompare(right));
}

export function createWorkspaceNotificationReadState(rawScope, rawReadIds = []) {
  const scope = requiredReadScope(rawScope);
  if (!scope) return null;
  return deepFreeze({
    version: WORKSPACE_NOTIFICATION_READ_STATE_VERSION,
    scope,
    readNotificationIds: normalizedReadIds(rawReadIds),
  });
}

export function normalizeWorkspaceNotificationReadState(rawState, rawExpectedScope) {
  const expectedScope = requiredReadScope(rawExpectedScope);
  if (!expectedScope) {
    return deepFreeze({ ok: false, reason: "read_scope_required", state: null });
  }
  const emptyState = createWorkspaceNotificationReadState(expectedScope);
  if (!isRecord(rawState)) {
    return deepFreeze({ ok: false, reason: "read_state_missing", state: emptyState });
  }
  const rawScope = isRecord(rawState.scope) ? rawState.scope : rawState;
  const actualScope = requiredReadScope(rawScope);
  if (rawState.version !== WORKSPACE_NOTIFICATION_READ_STATE_VERSION) {
    return deepFreeze({ ok: false, reason: "read_schema_mismatch", state: emptyState });
  }
  if (
    !actualScope
    || actualScope.organizationId !== expectedScope.organizationId
    || actualScope.userId !== expectedScope.userId
  ) return deepFreeze({ ok: false, reason: "read_scope_mismatch", state: emptyState });
  if (!Array.isArray(rawState.readNotificationIds)) {
    return deepFreeze({ ok: false, reason: "read_ids_invalid", state: emptyState });
  }
  return deepFreeze({
    ok: true,
    reason: null,
    state: createWorkspaceNotificationReadState(expectedScope, rawState.readNotificationIds),
  });
}

function transitionNotificationId(rawNotification, rawExpectedScope, now) {
  const normalized = normalizeWorkspaceNotification(rawNotification);
  if (!normalized.ok) {
    return { notification: null, notificationId: "", reason: "notification_invalid" };
  }
  if (!workspaceNotificationMatchesRecipient(normalized.notification, rawExpectedScope)) {
    return { notification: null, notificationId: "", reason: "wrong_recipient" };
  }
  if (
    normalized.legacyExpired
    || isWorkspaceNotificationExpired(normalized.notification, now)
  ) return { notification: null, notificationId: "", reason: "expired" };
  return {
    notification: normalized.notification,
    notificationId: normalized.notification.notificationId,
    reason: null,
  };
}

export function applyWorkspaceNotificationReadTransition(rawState, rawTransition, rawExpectedScope) {
  const normalized = normalizeWorkspaceNotificationReadState(rawState, rawExpectedScope);
  if (!normalized.ok || !normalized.state || !isRecord(rawTransition)) {
    return deepFreeze({
      ok: false,
      changed: false,
      reason: normalized.reason || "transition_invalid",
      state: normalized.state,
    });
  }

  const currentIds = normalized.state.readNotificationIds;
  let candidateIds = [];
  let reason = null;
  let emptyIsNoop = false;
  if (rawTransition.type === "explicit_read") {
    const candidate = transitionNotificationId(
      rawTransition.notification,
      rawExpectedScope,
      rawTransition.now,
    );
    candidateIds = [candidate.notificationId];
    reason = candidate.reason;
  } else if (rawTransition.type === "mark_visible") {
    if (!Array.isArray(rawTransition.items)) reason = "visible_items_required";
    else {
      emptyIsNoop = true;
      candidateIds = filterWorkspaceNotificationItems(
        rawTransition.items,
        rawTransition.filter,
      )
        .filter((item) => {
          const notification = itemNotification(item);
          return notification
            && workspaceNotificationMatchesRecipient(notification, rawExpectedScope)
            && !isWorkspaceNotificationExpired(notification, rawTransition.now);
        })
        .map((item) => item.notification.notificationId);
    }
  } else if (rawTransition.type === "action_result") {
    if (
      rawTransition.outcome !== "success"
      || rawTransition.exactTargetValidated !== true
      || rawTransition.commandSucceeded !== true
    ) {
      return deepFreeze({
        ok: true,
        changed: false,
        reason: "action_not_successful",
        state: normalized.state,
      });
    }
    const candidate = transitionNotificationId(
      rawTransition.notification,
      rawExpectedScope,
      rawTransition.now,
    );
    candidateIds = [candidate.notificationId];
    reason = candidate.reason;
    if (!reason && notificationActionCandidate(candidate.notification).state !== "inert") {
      reason = "action_not_actionable";
    }
  } else {
    reason = "transition_unknown";
  }

  if (reason) {
    return deepFreeze({ ok: false, changed: false, reason, state: normalized.state });
  }
  const additions = normalizedReadIds(candidateIds);
  if (!additions.length) {
    if (emptyIsNoop) {
      return deepFreeze({
        ok: true,
        changed: false,
        reason: "no_visible_notifications",
        state: normalized.state,
      });
    }
    return deepFreeze({ ok: false, changed: false, reason: "notification_id_required", state: normalized.state });
  }
  const nextIds = normalizedReadIds([...currentIds, ...additions]);
  const changed = nextIds.length !== currentIds.length;
  return deepFreeze({
    ok: true,
    changed,
    reason: changed ? null : "already_read",
    state: changed
      ? createWorkspaceNotificationReadState(normalized.state.scope, nextIds)
      : normalized.state,
  });
}

function eventPriority(left, right) {
  const createdDifference = Date.parse(right.notification.createdAt)
    - Date.parse(left.notification.createdAt);
  if (createdDifference) return createdDifference;
  const leftId = left.notification.notificationId;
  const rightId = right.notification.notificationId;
  if (leftId !== rightId) return leftId < rightId ? -1 : 1;
  const leftCanonical = JSON.stringify(left.notification);
  const rightCanonical = JSON.stringify(right.notification);
  if (leftCanonical === rightCanonical) return 0;
  return leftCanonical < rightCanonical ? -1 : 1;
}

function dedupeNotifications(candidates) {
  const seenIds = new Map();
  const seenDedupeKeys = new Map();
  const kept = [];
  const discarded = [];
  [...candidates].sort(eventPriority).forEach((candidate) => {
    const notification = candidate.notification;
    const idWinner = seenIds.get(notification.notificationId);
    if (idWinner) {
      discarded.push({
        notificationId: notification.notificationId,
        reason: "duplicate_notification_id",
        winnerNotificationId: idWinner,
      });
      return;
    }
    const dedupeWinner = notification.dedupeKey
      ? seenDedupeKeys.get(notification.dedupeKey)
      : "";
    if (dedupeWinner) {
      discarded.push({
        notificationId: notification.notificationId,
        reason: "replaced_by_newer_dedupe_key",
        winnerNotificationId: dedupeWinner,
      });
      return;
    }
    seenIds.set(notification.notificationId, notification.notificationId);
    if (notification.dedupeKey) {
      seenDedupeKeys.set(notification.dedupeKey, notification.notificationId);
    }
    kept.push(candidate);
  });
  return { kept, discarded };
}

function noActionDescriptor(requiresAction) {
  return deepFreeze({
    state: requiresAction ? "blocked" : "none",
    reason: requiresAction ? "action_key_required" : "no_action",
    actionKey: "",
    targetIntent: null,
    executable: false,
    executionOwner: "workspace-command-registry",
  });
}

function blockedActionDescriptor(reason, actionKey = "", targetIntent = null) {
  return deepFreeze({
    state: "blocked",
    reason,
    actionKey: SAFE_ACTION_KEY.test(actionKey) ? actionKey : "",
    targetIntent,
    executable: false,
    executionOwner: "workspace-command-registry",
  });
}

function inertActionDescriptor(actionKey, targetIntent) {
  return deepFreeze({
    state: "inert",
    reason: "external_command_validation_required",
    actionKey,
    targetIntent,
    executable: false,
    executionOwner: "workspace-command-registry",
  });
}

function notificationActionCandidate(notification) {
  const actionKey = notification.actionKey || "";
  if (!actionKey) return noActionDescriptor(notification.requiresAction);
  if (!WORKSPACE_NOTIFICATION_ACTION_KEYS.includes(actionKey)) {
    return blockedActionDescriptor("unknown_action", actionKey);
  }
  if (actionKey === "ai.open-decisions") {
    return inertActionDescriptor(actionKey, deepFreeze({
      kind: "internal",
      appId: "ai",
      tab: "decisions",
      ...(notification.projectId ? { projectId: notification.projectId } : {}),
    }));
  }
  if (actionKey === "process.open") {
    if (!notification.processId) return blockedActionDescriptor("process_id_required", actionKey);
    return inertActionDescriptor(actionKey, deepFreeze({
      kind: "process",
      processId: notification.processId,
      ...(notification.projectId ? { projectId: notification.projectId } : {}),
    }));
  }
  if (!notification.objectId) return blockedActionDescriptor("object_id_required", actionKey);
  return inertActionDescriptor(actionKey, deepFreeze({
    kind: "object",
    objectId: notification.objectId,
    ...(notification.projectId ? { projectId: notification.projectId } : {}),
  }));
}

export function describeWorkspaceNotificationAction(rawNotification) {
  const normalized = normalizeWorkspaceNotification(rawNotification);
  if (!normalized.ok) return blockedActionDescriptor("notification_invalid");
  return notificationActionCandidate(normalized.notification);
}

export function evaluateWorkspaceNotificationAction(rawNotification, rawContext = {}) {
  const normalized = normalizeWorkspaceNotification(rawNotification);
  if (!normalized.ok) return blockedActionDescriptor("notification_invalid");
  const notification = normalized.notification;
  const context = isRecord(rawContext) ? rawContext : {};

  if (!owns(context, "recipient")) {
    return blockedActionDescriptor("recipient_recheck_required", notification.actionKey || "");
  }
  if (!workspaceNotificationMatchesRecipient(notification, context.recipient)) {
    return blockedActionDescriptor("wrong_recipient", notification.actionKey || "");
  }
  if (notification.expiresAt && nowMilliseconds(context.now) === null) {
    return blockedActionDescriptor("expiry_recheck_required", notification.actionKey || "");
  }
  if (normalized.legacyExpired || isWorkspaceNotificationExpired(notification, context.now)) {
    return blockedActionDescriptor("expired", notification.actionKey || "");
  }
  if (context.recordState !== "current") {
    return blockedActionDescriptor(
      ["stale", "missing"].includes(context.recordState)
        ? "stale_notification"
        : "notification_recheck_required",
      notification.actionKey || "",
    );
  }
  if (context.permissionState !== "allowed") {
    return blockedActionDescriptor(
      ["denied", "revoked"].includes(context.permissionState)
        ? "permission_denied"
        : "permission_recheck_required",
      notification.actionKey || "",
    );
  }

  const candidate = notificationActionCandidate(notification);
  if (candidate.state !== "inert") return candidate;
  if (
    candidate.targetIntent
    && ["object", "process"].includes(candidate.targetIntent.kind)
    && context.targetState !== "current"
  ) {
    return blockedActionDescriptor(
      ["stale", "missing", "revoked"].includes(context.targetState)
        ? "stale_target"
        : "target_recheck_required",
      candidate.actionKey,
      candidate.targetIntent,
    );
  }
  return candidate;
}

export function normalizeWorkspaceNotificationFeed(rawEvents, rawOptions = {}) {
  const events = Array.isArray(rawEvents) ? rawEvents : [];
  const options = isRecord(rawOptions) ? rawOptions : {};
  const admitted = [];
  const rejected = [];
  const excluded = [];

  events.forEach((rawEvent, index) => {
    const normalized = normalizeWorkspaceNotification(rawEvent);
    if (!normalized.ok) {
      rejected.push({ index, issues: normalized.issues });
      return;
    }
    if (!workspaceNotificationMatchesRecipient(normalized.notification, options.recipient)) {
      excluded.push({
        notificationId: normalized.notification.notificationId,
        reason: "wrong_recipient",
      });
      return;
    }
    admitted.push({
      notification: normalized.notification,
      legacyExpired: normalized.legacyExpired,
    });
  });

  const deduped = dedupeNotifications(admitted);
  const readState = normalizeWorkspaceNotificationReadState(options.readState, options.recipient);
  const readIds = new Set(readState.state ? readState.state.readNotificationIds : []);
  const items = [];
  deduped.kept.forEach((candidate) => {
    if (
      candidate.legacyExpired
      || isWorkspaceNotificationExpired(candidate.notification, options.now)
    ) {
      excluded.push({
        notificationId: candidate.notification.notificationId,
        reason: "expired",
      });
      return;
    }
    const read = readIds.has(candidate.notification.notificationId);
    items.push(deepFreeze({
      notification: candidate.notification,
      read,
      unread: !read,
      action: notificationActionCandidate(candidate.notification),
    }));
  });

  return deepFreeze({
    items,
    rejected,
    excluded,
    dedupe: deduped.discarded,
    readState: readState.state,
    readStateAccepted: readState.ok,
  });
}

function itemNotification(item) {
  return isRecord(item) && isRecord(item.notification) ? item.notification : null;
}

function processSource(notification) {
  const source = notification.sourceSection.toLocaleLowerCase("ru-RU");
  return notification.type === "process_complete"
    || notification.type === "error"
    || ["process", "processes", "процесс", "процессы"].includes(source);
}

function itemMatchesFilter(item, filter) {
  const notification = itemNotification(item);
  if (!notification) return false;
  if (filter === "all") return true;
  if (filter === "unread") return item.unread === true;
  if (filter === "action_required") {
    return notification.requiresAction === true && !notification.resolvedAt;
  }
  if (filter === "mentions") return notification.type === "mention";
  if (filter === "processes") return processSource(notification);
  if (filter === "system") {
    return notification.type === "system_info" || notification.type === "access_change";
  }
  return false;
}

export function filterWorkspaceNotificationItems(rawItems, rawFilter = "all") {
  const items = Array.isArray(rawItems) ? rawItems : [];
  const filter = WORKSPACE_NOTIFICATION_FILTERS.includes(rawFilter) ? rawFilter : "all";
  return items.filter((item) => itemMatchesFilter(item, filter));
}

export function countWorkspaceNotificationItems(rawItems) {
  const items = Array.isArray(rawItems) ? rawItems : [];
  return deepFreeze({
    all: filterWorkspaceNotificationItems(items, "all").length,
    unread: filterWorkspaceNotificationItems(items, "unread").length,
    actionRequired: filterWorkspaceNotificationItems(items, "action_required").length,
    mentions: filterWorkspaceNotificationItems(items, "mentions").length,
    processes: filterWorkspaceNotificationItems(items, "processes").length,
    system: filterWorkspaceNotificationItems(items, "system").length,
  });
}

export function formatWorkspaceNotificationBadge(rawCount) {
  const numeric = Number(rawCount);
  const count = Number.isFinite(numeric) && numeric > 0 ? Math.floor(numeric) : 0;
  return deepFreeze({
    count,
    hidden: count === 0,
    text: count === 0 ? "" : count > 99 ? "99+" : String(count),
    ariaLabel: count === 0
      ? "Уведомления"
      : `Уведомления · ${count} непрочитанных`,
  });
}
