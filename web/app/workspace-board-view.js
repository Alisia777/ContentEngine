// Workflow folders are durable, server-counted project records. The former
// MIME/status "smart folders" filtered only the currently loaded page and
// mixed source videos with generated videos, so they are intentionally retired.
const SMART_FOLDER_DEFINITIONS = Object.freeze([]);
const RESERVED_FOLDER_IDS = new Set(["all", "root"]);
const ENTITY_TYPE_PATTERN = /^[a-z][a-z0-9_-]{0,39}$/;
const ID_MAX_LENGTH = 180;
const QUERY_MAX_LENGTH = 120;
const NORMALIZED_BOARDS = new WeakSet();
const PROVENANCE_FILTERS = new Set(["all", "source", "research", "generated_output"]);

const ENTITY_LABELS = Object.freeze({
  media: "Материал",
  task: "Задача",
  generation: "Генерация",
  research: "Разбор товара",
  placement: "Публикация",
  publication: "Публикация",
  payout: "Выплата",
  feedback: "Запрос",
});

const ENTITY_ICONS = Object.freeze({
  media: "▧",
  task: "✓",
  generation: "✦",
  research: "⌕",
  placement: "↗",
  publication: "↗",
  payout: "₽",
  feedback: "+",
});

const ARTIFACT_CLASS_LABELS = Object.freeze({
  source: "Источник",
  generated_output: "Результат",
  unclassified: "Не классифицирован",
});

const LIFECYCLE_STAGE_LABELS = Object.freeze({
  sources: "Исходники",
  drafts: "Черновик",
  review: "На проверке",
  ready: "Готово",
  published: "Опубликовано",
  unclassified: "Этап не определён",
});

function asRecord(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function normalizedId(value) {
  return String(value ?? "").trim().slice(0, ID_MAX_LENGTH);
}

function normalizedEntityType(value, fallback = "media") {
  const normalized = String(value || fallback).trim().toLowerCase();
  return ENTITY_TYPE_PATTERN.test(normalized) ? normalized : fallback;
}

function normalizedProvenanceFilter(value) {
  const normalized = String(value || "all").trim().toLowerCase();
  return PROVENANCE_FILTERS.has(normalized) ? normalized : "all";
}

function normalizedFolderReference(value) {
  const normalized = normalizedId(value);
  return !normalized || RESERVED_FOLDER_IDS.has(normalized) || isWorkspaceSmartFolderId(normalized)
    ? null
    : normalized;
}

export function isWorkspaceSmartFolderId(value) {
  void value;
  return false;
}

function normalizedStatus(value, fallback = "ready") {
  const normalized = String(value || fallback).trim().toLowerCase();
  return /^[a-z][a-z0-9_-]{0,39}$/.test(normalized) ? normalized : fallback;
}

function normalizedColorToken(value) {
  const normalized = String(value || "default").trim().toLowerCase();
  return /^[a-z][a-z0-9_-]{0,31}$/.test(normalized) ? normalized : "default";
}

function finiteNumber(...values) {
  for (const value of values) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function optionalFiniteNumber(...values) {
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function optionalBoolean(...values) {
  for (const value of values) {
    if (typeof value === "boolean") return value;
  }
  return null;
}

function safeText(value, maximumLength = 500) {
  return String(value ?? "").trim().slice(0, maximumLength);
}

function safeTextList(value, maximumItems = 12, maximumLength = 500) {
  if (!Array.isArray(value)) return Object.freeze([]);
  return Object.freeze(value
    .map((item) => {
      if (item && typeof item === "object" && !Array.isArray(item)) {
        return safeText(
          item.label ?? item.title ?? item.summary ?? item.text ?? item.conclusion,
          maximumLength,
        );
      }
      return safeText(item, maximumLength);
    })
    .filter(Boolean)
    .slice(0, maximumItems));
}

function safeWorkspaceDeepLink(value) {
  const candidate = safeText(value, 2_000);
  return candidate.startsWith("#/workspace/") ? candidate : "";
}

function normalizedHistory(value) {
  if (!Array.isArray(value)) return Object.freeze([]);
  return Object.freeze(value
    .map((entry) => {
      if (typeof entry === "string") {
        const label = safeText(entry, 300);
        return label ? Object.freeze({ label, at: "" }) : null;
      }
      const record = asRecord(entry);
      const label = safeText(
        record.label ?? record.title ?? record.status_label ?? record.status ?? record.action,
        300,
      );
      const at = safeText(
        record.at ?? record.created_at ?? record.updated_at ?? record.reviewed_at ?? record.published_at,
        80,
      );
      return label ? Object.freeze({ label, at }) : null;
    })
    .filter(Boolean)
    .slice(0, 12));
}

function normalizedRelations(source) {
  const result = [];
  const seen = new Set();
  const append = ({ type = "", id = "", label = "", status = "", deepLink = "" }) => {
    const relationId = normalizedId(id);
    const relationType = safeText(type, 60).toLowerCase();
    const relationLabel = safeText(label, 180);
    if (!relationId && !relationLabel) return;
    const key = `${relationType}:${relationId}:${relationLabel}`;
    if (seen.has(key)) return;
    seen.add(key);
    result.push(Object.freeze({
      type: relationType,
      id: relationId,
      label: relationLabel || relationId,
      status: safeText(status, 80),
      deepLink: safeWorkspaceDeepLink(deepLink),
    }));
  };
  const explicit = Array.isArray(source.relations) ? source.relations : [];
  explicit.slice(0, 12).forEach((value) => {
    const relation = asRecord(value);
    append({
      type: relation.type ?? relation.entity_type ?? relation.kind,
      id: relation.id ?? relation.entity_id,
      label: relation.label ?? relation.title ?? relation.name,
      status: relation.status,
      deepLink: relation.deep_link ?? relation.deepLink,
    });
  });
  const productId = normalizedId(source.product_id ?? source.productId);
  if (productId) append({
    type: "product",
    id: productId,
    label: safeText(source.product_name ?? source.productName ?? source.sku, 180) || "Товар",
  });
  const taskId = normalizedId(source.task_id ?? source.taskId);
  if (taskId) append({ type: "task", id: taskId, label: "Задача" });
  return Object.freeze(result);
}

function normalizeResearchQuickLook(source) {
  const receipt = asRecord(source.ai_receipt ?? source.aiReceipt);
  const disposition = asRecord(source.disposition);
  const selection = asRecord(source.learning_selection ?? source.learningSelection);
  const record = {
    source: safeText(
      source.research_source ?? source.researchSource ?? source.source_title ?? source.sourceTitle,
      600,
    ),
    evidenceSummary: safeText(
      source.evidence_summary ?? source.evidenceSummary,
      2_000,
    ),
    selectedConclusions: safeTextList(
      source.selected_conclusions ?? source.selectedConclusions,
      12,
      600,
    ),
    rejectedConclusions: safeTextList(
      source.rejected_conclusions ?? source.rejectedConclusions,
      12,
      600,
    ),
    nextAction: safeText(source.next_action ?? source.nextAction, 600),
    categoryBindingId: normalizedId(source.category_binding_id ?? source.categoryBindingId),
    receipt: Object.freeze({
      id: normalizedId(receipt.receipt_id ?? receipt.receiptId),
      status: safeText(receipt.status, 80),
      at: safeText(receipt.received_at ?? receipt.receivedAt, 80),
    }),
    disposition: Object.freeze({
      id: normalizedId(disposition.disposition_id ?? disposition.dispositionId),
      status: safeText(disposition.status ?? disposition.decision, 80),
      at: safeText(disposition.decided_at ?? disposition.decidedAt, 80),
    }),
    selection: Object.freeze({
      id: normalizedId(selection.selection_id ?? selection.selectionId),
      status: safeText(selection.status ?? selection.decision, 80),
      at: safeText(selection.selected_at ?? selection.selectedAt, 80),
    }),
  };
  return Object.freeze(record);
}

function normalizeGenerationQuickLook(source) {
  const parameters = asRecord(source.parameters);
  const metadata = asRecord(source.metadata);
  const snapshot = [
    source.generation_selection_snapshot,
    source.selection_snapshot,
    parameters.generation_selection_snapshot,
    parameters.selection_snapshot,
    metadata.generation_selection_snapshot,
    metadata.selection_snapshot,
  ].map(asRecord).find((value) => Object.keys(value).length) || {};
  const estimatedCostMinor = optionalFiniteNumber(
    snapshot.estimated_cost_minor,
    source.estimated_cost_minor,
    parameters.estimated_cost_minor,
  );
  const actualCostMinor = optionalFiniteNumber(
    source.actual_cost_minor,
    parameters.actual_cost_minor,
  );
  const referenceCount = optionalFiniteNumber(
    snapshot.reference_count,
    source.reference_count,
    parameters.reference_count,
  );
  const durationSeconds = optionalFiniteNumber(
    snapshot.requested_duration_seconds,
    source.duration_seconds,
    parameters.duration_seconds,
  );
  const record = {
    publicLabel: safeText(
      snapshot.model_public_label
        ?? source.model_public_label
        ?? source.modelPublicLabel,
      180,
    ),
    model: safeText(snapshot.model ?? source.model ?? parameters.model, 180),
    provider: safeText(snapshot.provider ?? source.provider ?? parameters.provider, 80).toLowerCase(),
    selectionSource: safeText(snapshot.selection_source ?? source.selection_source, 80).toLowerCase(),
    qualityStatus: safeText(
      snapshot.acceptance_status_at_launch ?? source.acceptance_status_at_launch,
      80,
    ).toLowerCase(),
    estimatedCostMinor: estimatedCostMinor !== null && estimatedCostMinor >= 0
      ? estimatedCostMinor
      : null,
    actualCostMinor: actualCostMinor !== null && actualCostMinor >= 0
      ? actualCostMinor
      : null,
    currency: safeText(
      snapshot.currency ?? source.currency ?? parameters.currency,
      3,
    ).toUpperCase(),
    inputMode: safeText(snapshot.input_mode ?? source.input_mode ?? parameters.input_mode, 80).toLowerCase(),
    referenceCount: referenceCount !== null && referenceCount >= 0
      ? Math.trunc(referenceCount)
      : null,
    durationSeconds: durationSeconds !== null && durationSeconds >= 0
      ? durationSeconds
      : null,
    audio: optionalBoolean(
      snapshot.requested_audio,
      source.audio,
      parameters.audio,
    ),
    ratio: safeText(snapshot.requested_ratio ?? source.ratio ?? parameters.ratio, 40),
    resolution: safeText(
      snapshot.requested_resolution ?? source.resolution ?? parameters.resolution,
      40,
    ),
    version: safeText(
      source.content_version ?? source.version_label ?? source.generation_version,
      100,
    ),
    reviewHistory: normalizedHistory(source.review_history ?? source.reviewHistory),
    publicationHistory: normalizedHistory(
      source.publication_history ?? source.publicationHistory,
    ),
  };
  return Object.freeze(record);
}

function itemSources(source) {
  if (Array.isArray(source)) return [{ items: source, fallbackType: "media" }];
  const record = asRecord(source);
  const definitions = [
    ["items", ""],
    ["workspace_items", ""],
    ["entities", ""],
    ["objects", ""],
    ["media", "media"],
    ["media_items", "media"],
    ["tasks", "task"],
    ["task_items", "task"],
    ["batches", "generation"],
    ["generation_batches", "generation"],
    ["research", "research"],
    ["research_runs", "research"],
    ["research_artifacts", "research"],
    ["placements", "placement"],
    ["placement_items", "placement"],
    ["publications", "publication"],
    ["payouts", "payout"],
    ["feedback", "feedback"],
  ];
  return definitions
    .filter(([key]) => Array.isArray(record[key]))
    .map(([key, fallbackType]) => ({ items: record[key], fallbackType }));
}

function inferEntityType(item, fallbackType) {
  if (fallbackType) return fallbackType;
  if (item.task_type || item.instructions || item.assignee_id) return "task";
  if (item.mime_type || item.object_key || item.object_name) return "media";
  if (item.generation_job_id || item.total_requested || item.parameters) return "generation";
  if (item.final_url || item.platform) return "placement";
  return "media";
}

function normalizeFolder(folder, index, canManageFolders = false) {
  const source = asRecord(folder);
  const id = normalizedId(source.id ?? source.public_id ?? source.folder_id);
  if (!id || RESERVED_FOLDER_IDS.has(id)) return null;
  const name = safeText(source.name ?? source.title ?? source.label, 120) || `Папка ${index + 1}`;
  const parentId = normalizedFolderReference(source.parent_id ?? source.parentId);
  const rawKind = safeText(source.kind ?? source.folder_kind, 20).toLowerCase();
  const systemRole = safeText(source.system_role ?? source.systemRole, 40).toLowerCase();
  return {
    id,
    parentId,
    kind: rawKind === "project" || (!rawKind && !parentId) ? "project" : "folder",
    projectId: normalizedFolderReference(source.project_id ?? source.projectId),
    systemRole,
    name,
    status: normalizedStatus(source.status, "active"),
    version: Math.max(1, Math.trunc(finiteNumber(source.version, 1))),
    colorToken: normalizedColorToken(source.color_token ?? source.colorToken),
    itemCount: Math.max(
      0,
      Math.trunc(
        finiteNumber(
          source.item_count,
          source.items_count,
          source.count,
          Number(source.media_count || 0) + Number(source.task_count || 0),
        ),
      ),
    ),
    sortOrder: finiteNumber(source.position, source.sort_order, source.sortOrder, index),
    editable: !systemRole && (source.can_edit === true
      || source.editable === true
      || (
        source.can_edit === undefined
        && source.editable === undefined
        && canManageFolders
      )),
    createdAt: safeText(source.created_at ?? source.createdAt, 80),
    updatedAt: safeText(source.updated_at ?? source.updatedAt, 80),
  };
}

function normalizeItem(item, index, fallbackType = "") {
  const source = asRecord(item);
  const id = normalizedId(source.public_id ?? source.id ?? source.item_id);
  if (!id) return null;
  const entityType = normalizedEntityType(
    source.entity_type ?? source.entityType ?? source.object_type ?? source.type,
    inferEntityType(source, fallbackType),
  );
  const researchArtifact = entityType === "research";
  const key = workspaceBoardItemKey(entityType, id);
  if (!key) return null;
  const title = safeText(
    source.title ??
      source.name ??
      source.original_filename ??
      source.product_name ??
      source.sku ??
      (researchArtifact ? "Исследование товара" : null) ??
      `${ENTITY_LABELS[entityType] || "Объект"} ${id}`,
    240,
  );
  const description = safeText(
    source.description ?? source.instructions ?? source.details ?? source.reason,
    2_000,
  );
  const subtitle = safeText(
    source.subtitle ??
      source.kind ??
      source.task_type ??
      source.sku ??
      source.platform ??
      description,
    240,
  );
  const mimeType = safeText(source.mime_type ?? source.mimeType, 160).toLowerCase();
  const artifactClass = safeText(
    source.artifact_class ?? source.artifactClass,
    40,
  ).toLowerCase();
  const lifecycleStage = safeText(
    source.lifecycle_stage ?? source.lifecycleStage,
    40,
  ).toLowerCase();
  const deepLink = safeWorkspaceDeepLink(source.deep_link ?? source.deepLink);
  const aiReceipt = asRecord(source.ai_receipt ?? source.aiReceipt);
  const aiDeepLink = safeWorkspaceDeepLink(aiReceipt.deep_link ?? aiReceipt.deepLink);
  const metadata = asRecord(source.metadata);
  const imagePreviewUrl = safeText(
    source.poster_url
      ?? source.posterUrl
      ?? source.poster
      ?? source.thumbnail_url
      ?? source.thumbnailUrl
      ?? source.thumbnail
      ?? source.preview_image_url
      ?? source.previewImageUrl
      ?? source.preview_image
      ?? source.image_url
      ?? source.imageUrl
      ?? source.image
      ?? metadata.poster_url
      ?? metadata.posterUrl
      ?? metadata.poster
      ?? metadata.thumbnail_url
      ?? metadata.thumbnailUrl
      ?? metadata.thumbnail
      ?? metadata.preview_image_url
      ?? metadata.previewImageUrl
      ?? metadata.preview_image
      ?? metadata.image_url
      ?? metadata.imageUrl
      ?? metadata.image,
    2_000,
  );
  const accessPreviewUrl = safeText(
    source.signed_url
      ?? source.preview_url
      ?? source.previewUrl
      ?? source.access_url
      ?? source.accessUrl
      ?? (mimeType.startsWith("image/") ? source.thumbnail_url ?? source.thumbnailUrl : ""),
    2_000,
  );
  const durationSeconds = optionalFiniteNumber(
    source.duration_seconds,
    source.durationSeconds,
    metadata.duration_seconds,
    metadata.durationSeconds,
  );
  const width = optionalFiniteNumber(source.width, source.width_px, metadata.width, metadata.width_px);
  const height = optionalFiniteNumber(source.height, source.height_px, metadata.height, metadata.height_px);
  const explicitVersions = Array.isArray(source.versions) ? source.versions : null;
  const versionCount = optionalFiniteNumber(
    source.version_count,
    source.versions_count,
    source.versionCount,
    explicitVersions?.length,
  );
  const sourceIdentity = [
    source.source_identity,
    source.sourceIdentity,
    source.original_filename,
    source.originalFilename,
    source.object_key,
    source.object_name,
  ].map((value) => safeText(value, 500)).find(Boolean) || "";
  const creatorId = normalizedId(
    researchArtifact
      ? source.created_by ?? source.createdBy
      : source.owner_id ?? source.ownerId ?? source.created_by ?? source.createdBy,
  );
  const creatorName = safeText(
    source.owner_display_name
      ?? source.ownerDisplayName
      ?? source.owner_name
      ?? source.ownerName
      ?? source.created_by_name
      ?? source.createdByName
      ?? source.creator_name
      ?? source.creatorName,
    180,
  );
  return {
    key,
    id,
    entityType,
    folderId: normalizedFolderReference(source.folder_id ?? source.folderId ?? source.workspace_folder_id),
    title: title || `${ENTITY_LABELS[entityType] || "Объект"} ${id}`,
    subtitle,
    description,
    status: normalizedStatus(source.status, "ready"),
    kind: safeText(source.kind ?? source.task_type ?? source.object_kind, 120),
    artifactClass: Object.hasOwn(ARTIFACT_CLASS_LABELS, artifactClass)
      ? artifactClass
      : "",
    lifecycleStage: Object.hasOwn(LIFECYCLE_STAGE_LABELS, lifecycleStage)
      ? lifecycleStage
      : "",
    mimeType,
    previewUrl: accessPreviewUrl,
    imagePreviewUrl,
    sizeBytes: Math.max(0, finiteNumber(source.size_bytes, source.sizeBytes)),
    createdAt: safeText(source.created_at ?? source.createdAt, 80),
    updatedAt: safeText(source.updated_at ?? source.updatedAt, 80),
    sortOrder: finiteNumber(source.position, source.sort_order, source.sortOrder, index),
    movable: source.can_move !== false && source.movable !== false,
    readOnly: source.read_only === true || source.readOnly === true || researchArtifact,
    deepLink,
    aiReceiptId: normalizedId(aiReceipt.receipt_id ?? aiReceipt.receiptId),
    aiReceiptStatus: normalizedStatus(aiReceipt.status, ""),
    aiDeepLink,
    creatorId,
    creatorName,
    projectId: normalizedId(source.project_id ?? source.projectId),
    productId: normalizedId(source.product_id ?? source.productId),
    productName: safeText(source.product_name ?? source.productName, 240),
    sku: safeText(source.sku, 120),
    wbArticle: safeText(source.wb_article ?? source.wbArticle, 120),
    taskId: normalizedId(source.task_id ?? source.taskId),
    originalFilename: safeText(
      source.original_filename ?? source.originalFilename ?? metadata.original_filename,
      300,
    ),
    objectName: safeText(source.object_key ?? source.object_name ?? source.objectName, 500),
    sourceIdentity,
    sha256: /^[0-9a-f]{64}$/iu.test(String(source.sha256 || "").trim())
      ? String(source.sha256).trim().toLowerCase()
      : "",
    durationSeconds: durationSeconds !== null && durationSeconds >= 0 ? durationSeconds : null,
    width: width !== null && width > 0 ? Math.trunc(width) : null,
    height: height !== null && height > 0 ? Math.trunc(height) : null,
    versionCount: versionCount !== null && versionCount > 0 ? Math.trunc(versionCount) : null,
    relations: normalizedRelations(source),
    researchQuickLook: normalizeResearchQuickLook(source),
    generationQuickLook: normalizeGenerationQuickLook(source),
  };
}

function smartFolderMatchesItem(folderId, item) {
  void folderId;
  void item;
  return false;
}

function smartFoldersForItems(items) {
  void items;
  return [];
}

function normalizeFolderParents(folders) {
  const byId = new Map(folders.map((folder) => [folder.id, folder]));
  const normalized = folders.map((folder) => {
    if (!folder.parentId || !byId.has(folder.parentId) || folder.parentId === folder.id) {
      return { ...folder, parentId: null };
    }
    const visited = new Set([folder.id]);
    let parentId = folder.parentId;
    while (parentId) {
      if (visited.has(parentId)) return { ...folder, parentId: null };
      visited.add(parentId);
      parentId = byId.get(parentId)?.parentId || null;
    }
    return folder;
  });
  const normalizedById = new Map(normalized.map((folder) => [folder.id, folder]));
  return normalized.map((folder) => {
    if (folder.kind === "project") return { ...folder, projectId: folder.id };
    let cursor = folder;
    let depth = 0;
    while (cursor?.parentId && depth < 12) {
      cursor = normalizedById.get(cursor.parentId);
      if (!cursor) break;
      if (cursor.kind === "project") return { ...folder, projectId: cursor.id };
      depth += 1;
    }
    return { ...folder, projectId: folder.projectId || null };
  });
}

function freezeBoard(board) {
  board.folders.forEach(Object.freeze);
  board.items.forEach(Object.freeze);
  Object.freeze(board.folders);
  Object.freeze(board.items);
  Object.freeze(board.entityTypes);
  Object.freeze(board.counts);
  Object.freeze(board.capabilities.researchArtifacts);
  Object.freeze(board.capabilities);
  Object.freeze(board);
  NORMALIZED_BOARDS.add(board);
  return board;
}

export function workspaceBoardItemKey(type, id) {
  const entityType = normalizedEntityType(type, "");
  const entityId = normalizedId(id);
  return entityType && entityId ? `${entityType}:${entityId}` : "";
}

export function workspaceBoardPaginationState(meta, exactMediaAccepted = false) {
  if (exactMediaAccepted === true) return { hasMore: false, nextCursor: null };
  const source = asRecord(meta);
  return {
    hasMore: source.has_more === true,
    nextCursor: source.next_cursor && typeof source.next_cursor === "object"
      && !Array.isArray(source.next_cursor)
      ? source.next_cursor
      : null,
  };
}

export function normalizeWorkspaceBoard(raw) {
  if (raw && typeof raw === "object" && NORMALIZED_BOARDS.has(raw)) {
    return raw;
  }
  const payload = raw?.data ?? raw;
  const source = asRecord(payload);
  const rawCapabilities = asRecord(source.capabilities);
  const rawResearchArtifacts = asRecord(
    rawCapabilities.research_artifacts ?? rawCapabilities.researchArtifacts,
  );
  const researchArtifactScope = safeText(rawResearchArtifacts.scope, 20).toLowerCase();
  const capabilities = {
    manageFolders: rawCapabilities.manage_folders === true || rawCapabilities.manageFolders === true,
    moveItems: rawCapabilities.move_items === true || rawCapabilities.moveItems === true,
    researchArtifacts: {
      readOnly: rawResearchArtifacts.read_only === true || rawResearchArtifacts.readOnly === true,
      scope: ["own", "project", "none"].includes(researchArtifactScope)
        ? researchArtifactScope
        : "none",
    },
  };
  const rawFolders = Array.isArray(source.folders)
    ? source.folders
    : Array.isArray(source.workspace_folders)
      ? source.workspace_folders
      : Array.isArray(source.media_folders)
        ? source.media_folders
        : [];
  const folderMap = new Map();
  rawFolders.forEach((folder, index) => {
    const normalized = normalizeFolder(folder, index, capabilities.manageFolders);
    if (normalized && !folderMap.has(normalized.id)) folderMap.set(normalized.id, normalized);
  });
  const realFolders = normalizeFolderParents([...folderMap.values()])
    .filter((folder) => folder.status !== "deleted")
    .sort((left, right) => (
      right.sortOrder - left.sortOrder ||
      left.name.localeCompare(right.name, "ru-RU", { sensitivity: "base" }) ||
      left.id.localeCompare(right.id)
    ));
  const folderIds = new Set(realFolders.map((folder) => folder.id));

  const itemMap = new Map();
  itemSources(Array.isArray(payload) ? payload : source).forEach(({ items, fallbackType }) => {
    items.forEach((item, index) => {
      const normalized = normalizeItem(item, index, fallbackType);
      if (!normalized || itemMap.has(normalized.key)) return;
      itemMap.set(normalized.key, {
        ...normalized,
        folderId: normalized.folderId && folderIds.has(normalized.folderId)
          ? normalized.folderId
          : null,
        movable: normalized.movable && !normalized.readOnly && capabilities.moveItems,
      });
    });
  });
  const items = [...itemMap.values()]
    .filter((item) => item.status !== "deleted")
    .sort((left, right) => (
      right.sortOrder - left.sortOrder ||
      String(right.createdAt).localeCompare(String(left.createdAt)) ||
      left.key.localeCompare(right.key)
    ));
  const smartFolders = smartFoldersForItems(items);
  const folders = [...smartFolders, ...realFolders];
  // Research is a separate read-only provenance projection, not a mutable
  // workspace-browser entity type. Exposing it in this selector would make
  // the client send an entity_types value that the exact RPC correctly
  // rejects. The dedicated provenance selector owns this view.
  const entityTypes = ["media", "task"];
  const counts = {
    all: items.length,
    files: items.filter((item) => item.entityType === "media").length,
    root: items.filter((item) => item.entityType !== "research" && !item.folderId).length,
    research: items.filter((item) => item.entityType === "research").length,
  };
  smartFolders.forEach((folder) => {
    counts[folder.id] = folder.itemCount;
  });
  realFolders.forEach((folder) => {
    const calculated = items.filter((item) => item.folderId === folder.id).length;
    counts[folder.id] = Math.max(folder.itemCount, calculated);
  });
  return freezeBoard({
    normalizedWorkspaceBoard: true,
    folders,
    items,
    entityTypes,
    counts,
    capabilities,
    partial: source?._meta?.has_more === true,
  });
}

export function workspaceBoardItemByKey(board, key) {
  const normalizedKey = safeText(key, ID_MAX_LENGTH * 2 + 1);
  if (!normalizedKey) return null;
  const normalizedBoard = normalizeWorkspaceBoard(board);
  return normalizedBoard.items.find((item) => item.key === normalizedKey) || null;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safePreviewUrl(value) {
  const candidate = safeText(value, 2_000);
  if (!candidate) return "";
  try {
    const parsed = new URL(candidate);
    // Локальный стенд подписывает URL по http с того же хоста, что и сама
    // страница — это тот же наш приватный сторедж. На проде
    // страница живёт на https, поэтому http-превью там по-прежнему отвергаются;
    // адресных литералов здесь нет намеренно — их запрещает сборка Pages.
    const sameHostHttp = parsed.protocol === "http:"
      && typeof window !== "undefined"
      && window.location?.protocol === "http:"
      && parsed.hostname === window.location.hostname;
    return parsed.protocol === "https:" || parsed.protocol === "blob:" || sameHostHttp
      ? parsed.href
      : "";
  } catch {
    return "";
  }
}

function domToken(value) {
  const normalized = String(value || "").replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  return normalized.slice(0, 120) || "item";
}

function humanEntityType(entityType) {
  return ENTITY_LABELS[entityType] || safeText(entityType, 40) || "Объект";
}

function humanStatus(status) {
  const labels = {
    active: "Активна",
    archived: "В архиве",
    ready: "Готово",
    todo: "Новая",
    in_progress: "В работе",
    submitted: "Отправлена",
    review: "Проверка",
    done: "Готово",
    blocked: "Блокер",
    failed: "Ошибка",
    processing: "Обработка",
    queued: "В очереди",
    published: "Опубликовано",
  };
  return labels[status] || safeText(status, 40) || "Без статуса";
}

function artifactClassLabel(artifactClass) {
  return ARTIFACT_CLASS_LABELS[artifactClass] || "";
}

function lifecycleStageLabel(lifecycleStage) {
  return LIFECYCLE_STAGE_LABELS[lifecycleStage] || "";
}

function folderDisplayName(folder) {
  if (!folder?.systemRole) return folder?.name || "Папка";
  if (folder.systemRole === "sources") return "Источники";
  return `Результаты · ${folder.name}`;
}

function boardLoadedCount(board, count, { authoritative = false } = {}) {
  const normalized = Math.max(0, Number(count) || 0);
  return `${normalized}${board.partial && !authoritative ? "+" : ""}`;
}

function formatBytes(value) {
  const bytes = Math.max(0, Number(value) || 0);
  if (!bytes) return "";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 || unit === 0 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

function formatDate(value) {
  const date = new Date(value || "");
  if (!Number.isFinite(date.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function selectedFolder(options, board) {
  const candidate = safeText(options.selectedFolderId || "all", ID_MAX_LENGTH);
  if (candidate === "all" || candidate === "root") return candidate;
  return board.folders.some((folder) => folder.id === candidate) ? candidate : "all";
}

function itemMatchesQuery(item, query) {
  if (!query) return true;
  const haystack = [
    item.title,
    item.subtitle,
    item.description,
    item.kind,
    item.status,
    artifactClassLabel(item.artifactClass),
    lifecycleStageLabel(item.lifecycleStage),
    item.id,
  ].join(" ").normalize("NFKC").toLocaleLowerCase("ru-RU");
  return haystack.includes(query.normalize("NFKC").toLocaleLowerCase("ru-RU"));
}

function filteredItems(board, folderId, query, entityType, provenanceFilter) {
  return board.items.filter((item) => {
    if (item.entityType === "research" && folderId !== "all") return false;
    if (folderId === "root" && item.folderId) return false;
    if (isWorkspaceSmartFolderId(folderId) && !smartFolderMatchesItem(folderId, item)) return false;
    if (
      folderId !== "all"
      && folderId !== "root"
      && !isWorkspaceSmartFolderId(folderId)
      && item.folderId !== folderId
    ) return false;
    if (
      provenanceFilter === "all"
      && entityType !== "all"
      && item.entityType !== entityType
    ) return false;
    if (provenanceFilter === "source" && (
      item.entityType !== "media" || item.artifactClass !== "source"
    )) return false;
    if (provenanceFilter === "research" && item.entityType !== "research") return false;
    if (provenanceFilter === "generated_output" && (
      item.entityType !== "media" || item.artifactClass !== "generated_output"
    )) return false;
    return itemMatchesQuery(item, query);
  });
}

function compactObjectId(value) {
  const normalized = safeText(value, ID_MAX_LENGTH);
  if (!normalized) return "";
  return normalized.length > 12
    ? `${normalized.slice(0, 8)}…${normalized.slice(-4)}`
    : normalized;
}

function itemCreatorAttribution(item, options) {
  const creatorId = safeText(item?.creatorId, ID_MAX_LENGTH);
  if (!creatorId) return null;
  const viewerProfileId = safeText(options?.viewerProfileId, ID_MAX_LENGTH);
  const viewerName = safeText(options?.viewerName, 180);
  const ownArtifact = Boolean(viewerProfileId && creatorId === viewerProfileId);
  const person = ownArtifact
    ? viewerName ? `${viewerName} (вы)` : "Вы"
    : item.creatorName || `Участник проекта · ${compactObjectId(creatorId)}`;
  return {
    label: item.entityType === "media" ? "Загрузил" : "Создал",
    person,
    creatorId,
  };
}

function folderBreadcrumbs(board, selectedFolderId) {
  if (selectedFolderId === "all") return [{ id: "all", name: "Все файлы", projectId: "" }];
  if (selectedFolderId === "root") return [{ id: "root", name: "Без папки", projectId: "" }];
  const selected = board.folders.find((folder) => folder.id === selectedFolderId);
  if (!selected) return [{ id: "all", name: "Все файлы", projectId: "" }];
  if (selected.smart === true) return [{ id: selected.id, name: selected.name, projectId: "" }];

  const byId = new Map(board.folders.map((folder) => [folder.id, folder]));
  const lineage = [];
  const visited = new Set();
  let cursor = selected;
  while (cursor && !visited.has(cursor.id) && lineage.length < 12) {
    visited.add(cursor.id);
    lineage.unshift({
      id: cursor.id,
      name: folderDisplayName(cursor),
      projectId: cursor.projectId || "",
    });
    cursor = cursor.parentId ? byId.get(cursor.parentId) : null;
  }
  return lineage;
}

function folderBreadcrumbMarkup(board, selectedFolderId, busy) {
  const breadcrumbs = folderBreadcrumbs(board, selectedFolderId);
  return `
    <nav class="workspace-board__breadcrumb" aria-label="Путь к папке">
      <ol>
        ${breadcrumbs.map((folder, index) => {
          const current = index === breadcrumbs.length - 1;
          return `
            <li>
              ${index ? '<span aria-hidden="true">›</span>' : ""}
              <button type="button"
                      data-action="select-workspace-folder"
                      data-folder-id="${escapeHtml(folder.id)}"
                      data-project-id="${escapeHtml(folder.projectId)}"
                      ${current ? 'aria-current="page"' : ""}
                      ${busy ? "disabled" : ""}>${escapeHtml(folder.name)}</button>
            </li>`;
        }).join("")}
      </ol>
    </nav>`;
}

function folderTreeMarkup(board, selectedFolderId, busy) {
  const children = new Map();
  const smartFolders = board.folders.filter((folder) => folder.smart === true);
  const realFolders = board.folders.filter((folder) => folder.smart !== true);
  realFolders.forEach((folder) => {
    const parentId = folder.parentId || "root";
    if (!children.has(parentId)) children.set(parentId, []);
    children.get(parentId).push(folder);
  });
  const renderBranch = (parentId, depth, ancestors = new Set()) => {
    if (depth > 12) return "";
    return (children.get(parentId) || []).map((folder) => {
      if (ancestors.has(folder.id)) return "";
      const nextAncestors = new Set(ancestors);
      nextAncestors.add(folder.id);
      const selected = selectedFolderId === folder.id;
      const nested = renderBranch(folder.id, depth + 1, nextAncestors);
      const displayName = folderDisplayName(folder);
      return `
        <li class="workspace-board__folder-row ${selected ? "is-selected" : ""}"
            ${folder.systemRole ? 'data-system-folder="true"' : "data-workspace-drop-folder"}
            data-folder-id="${escapeHtml(folder.id)}"
            data-parent-folder-id="${escapeHtml(folder.parentId || "root")}"
            data-project-id="${escapeHtml(folder.projectId || "")}"
            data-folder-kind="${escapeHtml(folder.kind || "folder")}"
            data-system-role="${escapeHtml(folder.systemRole || "")}"
            data-has-children="${nested ? "true" : "false"}"
            data-folder-version="${folder.version}"
            data-folder-color="${escapeHtml(folder.colorToken)}"
            style="--workspace-folder-depth:${depth}">
          ${nested ? `
            <button class="workspace-board__folder-toggle"
                    type="button"
                    data-folder-toggle="${escapeHtml(folder.id)}"
                    aria-controls="workspace-folder-branch-${escapeHtml(domToken(folder.id))}"
                    aria-expanded="true"
                    aria-label="Свернуть папку «${escapeHtml(displayName)}»">⌄</button>` : ""}
          <button class="workspace-board__folder-button"
                  type="button"
                  data-action="select-workspace-folder"
                  data-folder-id="${escapeHtml(folder.id)}"
                  ${selected ? 'aria-current="page"' : ""}
                  ${busy ? "disabled" : ""}>
            <span class="workspace-board__folder-icon" aria-hidden="true">◇</span>
            <span>${escapeHtml(displayName)}</span>
            <small>${boardLoadedCount(board, board.counts[folder.id], {
              authoritative: Boolean(folder.systemRole),
            })}</small>
          </button>
          <button class="workspace-board__context-trigger"
                  type="button"
                  data-ce-v4-context-trigger="folder"
                  aria-label="Действия с папкой «${escapeHtml(displayName)}»"
                  title="Действия с папкой"
                  ${busy ? "disabled" : ""}>⋯</button>
          ${nested ? `<ul id="workspace-folder-branch-${escapeHtml(domToken(folder.id))}"
                           class="workspace-board__folder-branch"
                           data-folder-branch="${escapeHtml(folder.id)}">${nested}</ul>` : ""}
        </li>`;
    }).join("");
  };

  return `
    <nav class="workspace-board__folders" aria-label="Папки рабочего пространства">
      <ul class="workspace-board__folder-list">
        <li class="workspace-board__folder-group-label">Быстрый доступ</li>
        <li class="workspace-board__folder-row workspace-board__folder-row--system ${selectedFolderId === "all" ? "is-selected" : ""}"
            data-folder-id="all"
            data-system-folder="true">
          <button class="workspace-board__folder-button"
                  type="button"
                  data-action="select-workspace-folder"
                  data-folder-id="all"
                  ${selectedFolderId === "all" ? 'aria-current="page"' : ""}
                  ${busy ? "disabled" : ""}>
            <span class="workspace-board__folder-icon" aria-hidden="true">▦</span>
            <span>Все файлы</span>
            <small>${boardLoadedCount(board, board.counts.all)}</small>
          </button>
          <button class="workspace-board__context-trigger"
                  type="button"
                  data-ce-v4-context-trigger="folder"
                  aria-label="Действия с папкой «Все файлы»"
                  title="Действия с папкой"
                  ${busy ? "disabled" : ""}>⋯</button>
        </li>
        <li class="workspace-board__folder-row workspace-board__folder-row--system">
          <a class="workspace-board__folder-button"
             style="text-decoration:none"
             href="#/workspace/media?view=recent"
             title="Список загруженных фото и видео: загрузка, забор по ссылке и подготовка исходников">
            <span class="workspace-board__folder-icon" aria-hidden="true">▧</span>
            <span>Материалы</span>
          </a>
        </li>
        ${smartFolders.map((folder) => `
          <li class="workspace-board__folder-row workspace-board__folder-row--system ${selectedFolderId === folder.id ? "is-selected" : ""}"
              data-folder-id="${escapeHtml(folder.id)}"
              data-system-folder="true">
            <button class="workspace-board__folder-button"
                    type="button"
                    data-action="select-workspace-folder"
                    data-folder-id="${escapeHtml(folder.id)}"
                    ${selectedFolderId === folder.id ? 'aria-current="page"' : ""}
                    ${busy ? "disabled" : ""}>
              <span class="workspace-board__folder-icon" aria-hidden="true">${escapeHtml(folder.icon)}</span>
              <span>${escapeHtml(folder.name)}</span>
              <small>${Number(board.counts[folder.id] || 0)}</small>
            </button>
            <button class="workspace-board__context-trigger"
                    type="button"
                    data-ce-v4-context-trigger="folder"
                    aria-label="Действия с папкой «${escapeHtml(folder.name)}»"
                    title="Действия с папкой"
                    ${busy ? "disabled" : ""}>⋯</button>
          </li>`).join("")}
        <li class="workspace-board__folder-group-label">Проекты и папки</li>
        <li class="workspace-board__folder-row workspace-board__folder-row--system ${selectedFolderId === "root" ? "is-selected" : ""}"
            data-workspace-drop-folder
            data-folder-id="root"
            data-system-folder="true">
          <button class="workspace-board__folder-button"
                  type="button"
                  data-action="select-workspace-folder"
                  data-folder-id="root"
                  ${selectedFolderId === "root" ? 'aria-current="page"' : ""}
                  ${busy ? "disabled" : ""}>
            <span class="workspace-board__folder-icon" aria-hidden="true">⌂</span>
            <span>Без папки</span>
            <small>${boardLoadedCount(board, board.counts.root)}</small>
          </button>
          <button class="workspace-board__context-trigger"
                  type="button"
                  data-ce-v4-context-trigger="folder"
                  aria-label="Действия с папкой «Без папки»"
                  title="Действия с папкой"
                  ${busy ? "disabled" : ""}>⋯</button>
        </li>
        ${renderBranch("root", 0)}
      </ul>
    </nav>`;
}

function folderManagementMarkup(board, selectedFolderId, busy, pendingArchiveFolderId = "") {
  const selected = board.folders.find(
    (folder) => folder.id === selectedFolderId && folder.smart !== true,
  ) || null;
  if (!board.capabilities.manageFolders) {
    return `
      <div class="workspace-board__folder-management">
        <p class="workspace-board__muted">Создавать, переименовывать и архивировать папки может руководитель. Доступные вам объекты можно перемещать.</p>
      </div>`;
  }
  const selectedIsSystem = Boolean(selected?.systemRole);
  const parentFolderId = selectedIsSystem
    ? selected.projectId || "root"
    : selected?.id || "root";
  const confirmingArchive = Boolean(
    selected?.editable && String(pendingArchiveFolderId || "") === selected.id,
  );
  const selectedIsProject = selected?.kind === "project";
  const archiveLabel = selectedIsProject ? "Архивировать проект" : "Архивировать папку";
  const archiveHint = selectedIsProject
    ? "Проект можно архивировать, когда в нём нет материалов, задач и публикаций."
    : "Папка должна быть пустой.";
  return `
    <div class="workspace-board__folder-management">
      <form id="workspace-folder-create-form" class="workspace-board__compact-form">
        <input type="hidden" name="parent_folder_id" value="${escapeHtml(parentFolderId)}" />
        <label for="workspace-folder-name">Новая папка</label>
        <div>
          <input id="workspace-folder-name"
                 name="folder_name"
                 required
                 minlength="1"
                 maxlength="120"
                 autocomplete="off"
                  placeholder="${selectedIsSystem
                    ? "Пользовательская папка в корне проекта"
                    : selected
                      ? "Внутри выбранной папки"
                      : "Например: Материалы августа"}"
                 ${busy ? "disabled" : ""} />
          <button class="workspace-board__icon-button"
                  type="submit"
                  aria-label="Создать папку"
                  title="Создать папку"
                  ${busy ? "disabled" : ""}>+</button>
        </div>
      </form>
      <form id="workspace-folder-edit-form"
            class="workspace-board__compact-form"
            ${selected && selected.editable ? "" : 'hidden aria-hidden="true"'}>
          <input type="hidden" name="folder_id" value="${escapeHtml(selected?.id || "")}" />
          <input type="hidden" name="folder_version" value="${selected?.version || 1}" />
           <label for="workspace-folder-edit-name">${selectedIsProject ? "Название проекта" : "Название папки"}</label>
          <div>
            <input id="workspace-folder-edit-name"
                   name="folder_name"
                   required
                   minlength="1"
                   maxlength="120"
                   value="${escapeHtml(selected?.name || "")}"
                   autocomplete="off"
                   ${busy || !selected?.editable ? "disabled" : ""} />
            <button class="workspace-board__icon-button"
                    type="submit"
                     aria-label="Сохранить название"
                     title="Сохранить название"
                    ${busy || !selected?.editable ? "disabled" : ""}>✓</button>
          </div>
          <button class="workspace-board__text-action workspace-board__text-action--danger"
                  type="button"
                  data-action="archive-workspace-folder"
                  data-folder-id="${escapeHtml(selected?.id || "")}"
                  data-folder-version="${selected?.version || 1}"
                   ${busy || !selected?.editable ? "disabled" : ""}>${escapeHtml(archiveLabel)}</button>
          ${confirmingArchive ? `
            <div class="workspace-board__inline-confirm" role="group" aria-label="Подтверждение архивации папки">
              <strong>Архивировать «${escapeHtml(selected.name)}»?</strong>
               <span>${escapeHtml(archiveHint)} Это действие не открывает отдельное окно.</span>
              <div>
                <button type="button" data-action="cancel-archive-workspace-folder">Отмена</button>
                <button type="button"
                        class="workspace-board__text-action--danger"
                        data-action="confirm-archive-workspace-folder"
                        data-folder-id="${escapeHtml(selected.id)}"
                        data-folder-version="${selected.version || 1}">Да, архивировать</button>
              </div>
            </div>` : ""}
        </form>
    </div>`;
}

function filterMarkup(board, options, resultCount, busy) {
  const selectedProvenance = normalizedProvenanceFilter(options.provenanceFilter);
  const selectedType = selectedProvenance === "all" && board.entityTypes.includes(options.entityType)
    ? options.entityType
    : "all";
  return `
    <form id="workspace-board-filter-form" class="workspace-board__filters" role="search">
      <label class="workspace-board__search">
        <span>Поиск</span>
        <input name="query"
               type="search"
               maxlength="${QUERY_MAX_LENGTH}"
               value="${escapeHtml(options.query)}"
               placeholder="Название, артикул или ID"
               autocomplete="off"
               ${busy ? "disabled" : ""} />
      </label>
      <label>
        <span>Тип объекта</span>
        <select name="entity_type" ${busy ? "disabled" : ""}>
          <option value="all" ${selectedType === "all" ? "selected" : ""}>Все типы</option>
          ${board.entityTypes.map((entityType) => `
            <option value="${escapeHtml(entityType)}" ${selectedType === entityType ? "selected" : ""}>
              ${escapeHtml(humanEntityType(entityType))}
            </option>`).join("")}
        </select>
      </label>
      <label>
        <span>Происхождение</span>
        <select name="provenance_filter" ${busy ? "disabled" : ""}>
          <option value="all" ${selectedProvenance === "all" ? "selected" : ""}>Все</option>
          <option value="source" ${selectedProvenance === "source" ? "selected" : ""}>Источники</option>
          <option value="research" ${selectedProvenance === "research" ? "selected" : ""}>Исследования</option>
          <option value="generated_output" ${selectedProvenance === "generated_output" ? "selected" : ""}>Результаты</option>
        </select>
      </label>
      <button class="workspace-board__filter-submit" type="submit" ${busy ? "disabled" : ""}>Показать</button>
      <button class="workspace-board__filter-reset"
              type="button"
              data-action="reset-workspace-filters"
              ${busy ? "disabled" : ""}>Сбросить</button>
      <p class="workspace-board__filter-result" role="status" aria-live="polite">
        ${board.partial ? "Показано" : "Найдено"}: <strong>${resultCount}${board.partial ? "+" : ""}</strong>
      </p>
    </form>`;
}

function workspaceBoardOverviewMarkup(board, busy) {
  const sourceFolder = board.folders.find((folder) => folder.systemRole === "sources") || null;
  const workflowOrder = new Map([
    ["drafts", 0],
    ["review", 1],
    ["ready", 2],
    ["published", 3],
  ]);
  const workflowFolders = board.folders
    .filter((folder) => workflowOrder.has(folder.systemRole))
    .sort((left, right) => (
      workflowOrder.get(left.systemRole) - workflowOrder.get(right.systemRole)
      || String(left.id).localeCompare(String(right.id))
    ));
  const sourceCount = sourceFolder
    ? board.counts[sourceFolder.id]
    : board.items.filter((item) => (
      item.entityType === "media" && item.artifactClass === "source"
    )).length;
  const researchCount = board.counts.research;
  const generatedCount = board.items.filter((item) => (
    item.entityType === "media" && item.artifactClass === "generated_output"
  )).length;
  const primaryCollections = [
    {
      key: "source",
      icon: "↙",
      eyebrow: "Входящие исходники",
      title: "Материалы",
      copy: "Фото, видео и документы, которые загрузили люди и подключённые источники.",
      count: boardLoadedCount(board, sourceCount, { authoritative: Boolean(sourceFolder) }),
      action: sourceFolder ? "select-workspace-folder" : "select-workspace-provenance",
      folderId: sourceFolder?.id || "all",
      projectId: sourceFolder?.projectId || "",
      provenance: sourceFolder ? "" : "source",
    },
    {
      key: "research",
      icon: "⌕",
      eyebrow: "Read-only журнал",
      title: "Исследования",
      copy: "Отдельная проекция запусков и квитанций ИИ. Она не является папкой и не перемещается.",
      count: boardLoadedCount(board, researchCount),
      action: "select-workspace-provenance",
      folderId: "all",
      projectId: "",
      provenance: "research",
    },
    {
      key: "generated_output",
      icon: "✦",
      eyebrow: "Созданный контент",
      title: "Результаты",
      copy: "Изображения и видео, созданные в производственном цикле, независимо от текущего этапа.",
      count: boardLoadedCount(board, generatedCount),
      action: "select-workspace-provenance",
      folderId: "all",
      projectId: "",
      provenance: "generated_output",
    },
  ];
  return `
    <section class="workspace-board__overview" aria-labelledby="workspace-board-overview-title">
      <div class="workspace-board__overview-head">
        <div>
          <p>Обзор проекта</p>
          <h2 id="workspace-board-overview-title">Файлы разделены по происхождению</h2>
        </div>
        <span>${boardLoadedCount(board, board.counts.all)} объектов доступно</span>
      </div>
      <div class="workspace-board__overview-grid">
        ${primaryCollections.map((collection) => `
          <button class="workspace-board__overview-card"
                  type="button"
                  data-action="${collection.action}"
                  data-folder-id="${escapeHtml(collection.folderId)}"
                  data-project-id="${escapeHtml(collection.projectId)}"
                  ${collection.provenance
                    ? `data-provenance-filter="${escapeHtml(collection.provenance)}"`
                    : ""}
                  data-overview-kind="${escapeHtml(collection.key)}"
                  ${busy ? "disabled" : ""}>
            <span class="workspace-board__overview-icon" aria-hidden="true">${collection.icon}</span>
            <span class="workspace-board__overview-copy">
              <small>${escapeHtml(collection.eyebrow)}</small>
              <strong>${escapeHtml(collection.title)}</strong>
              <span>${escapeHtml(collection.copy)}</span>
            </span>
            <span class="workspace-board__overview-count">${escapeHtml(collection.count)}</span>
          </button>`).join("")}
      </div>
      ${workflowFolders.length ? `
        <section class="workspace-board__workflow" aria-labelledby="workspace-board-workflow-title">
          <div>
            <p>Производственный путь</p>
            <h3 id="workspace-board-workflow-title">Результаты по этапам</h3>
          </div>
          <div class="workspace-board__workflow-folders">
            ${workflowFolders.map((folder) => `
              <button type="button"
                      data-action="select-workspace-folder"
                      data-folder-id="${escapeHtml(folder.id)}"
                      data-project-id="${escapeHtml(folder.projectId || "")}"
                      data-system-role="${escapeHtml(folder.systemRole)}"
                      ${busy ? "disabled" : ""}>
                <span>${escapeHtml(folderDisplayName(folder))}</span>
                <strong>${boardLoadedCount(board, board.counts[folder.id], { authoritative: true })}</strong>
              </button>`).join("")}
          </div>
        </section>` : ""}
      <div class="workspace-board__overview-all">
        <div>
          <strong>Нужен единый список?</strong>
          <span>Смешанный режим остаётся доступен, но открывается только по явному выбору.</span>
        </div>
        <button type="button"
                data-action="select-workspace-folder"
                data-folder-id="all"
                ${busy ? "disabled" : ""}>Показать все объекты · ${boardLoadedCount(board, board.counts.all)}</button>
      </div>
    </section>`;
}

// Снятый кадр живёт в кэше по id материала: перерисовки списка (поллинг,
// обновления) больше не пересоздают <video> и не мигают чёрным — карточка
// рисует лёгкий <img> из кэша. Снимаем кадр один раз, когда видео его отдало.
const previewFrameCache = new Map();

function capturePreviewFrame(video) {
  const mediaId = String(video?.dataset?.previewCapture || "");
  if (!mediaId || previewFrameCache.has(mediaId)) return;
  try {
    const width = Math.max(1, Math.min(480, video.videoWidth || 0));
    const height = Math.max(
      1,
      Math.round(width * ((video.videoHeight || 1) / (video.videoWidth || 1))),
    );
    if (!video.videoWidth || !video.videoHeight) return;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    canvas.getContext("2d").drawImage(video, 0, 0, width, height);
    const frame = canvas.toDataURL("image/jpeg", 0.72);
    if (!frame.startsWith("data:image/")) return;
    previewFrameCache.set(mediaId, frame);
    // Живой узел меняем на месте: до следующей перерисовки карточка уже не
    // держит видеоэлемент и не перезапросит файл.
    const img = document.createElement("img");
    img.className = "workspace-board__preview-frame";
    img.src = frame;
    img.alt = "";
    img.decoding = "async";
    video.replaceWith(img);
  } catch {
    // Кадр не снялся (например, хранилище без CORS): видео остаётся видимым
    // кадром само по себе, просто без кэша.
  }
}

if (typeof document !== "undefined" && !globalThis.__ceBoardPreviewCaptureBound) {
  globalThis.__ceBoardPreviewCaptureBound = true;
  document.addEventListener(
    "loadeddata",
    (event) => {
      const video = event.target;
      if (video instanceof HTMLVideoElement && video.dataset.previewCapture) {
        capturePreviewFrame(video);
      }
    },
    true,
  );
}

function itemPreviewMarkup(item, detailed = false) {
  const previewUrl = safePreviewUrl(item.previewUrl);
  const imagePreviewUrl = safePreviewUrl(item.imagePreviewUrl);
  if (previewUrl && item.mimeType.startsWith("video/") && detailed) {
    return `<video src="${escapeHtml(previewUrl)}" controls preload="none" playsinline${imagePreviewUrl ? ` poster="${escapeHtml(imagePreviewUrl)}"` : ""} aria-label="Видео: ${escapeHtml(item.title)}"></video>`;
  }
  if (item.mimeType.startsWith("image/") && (previewUrl || imagePreviewUrl)) {
    return `<img src="${escapeHtml(detailed ? previewUrl || imagePreviewUrl : imagePreviewUrl || previewUrl)}" alt="" loading="lazy" decoding="async" />`;
  }
  if (imagePreviewUrl) {
    return `<img src="${escapeHtml(imagePreviewUrl)}" alt="" loading="lazy" decoding="async" />`;
  }
  if (previewUrl && item.mimeType.startsWith("video/")) {
    const cachedFrame = previewFrameCache.get(String(item.id));
    if (cachedFrame) {
      return `<img class="workspace-board__preview-frame" src="${cachedFrame}" alt="" decoding="async" /><span class="workspace-board__preview-play" aria-hidden="true">▶</span>`;
    }
    // Первый кадр вместо фиолетовой заглушки: фрагмент #t= заставляет браузер
    // отрисовать кадр, не проигрывая и не скачивая ролик целиком (metadata +
    // один кадр). Элемент немой и не интерактивный — карточкой остаётся сама
    // плитка; после загрузки кадр уходит в кэш и карточка живёт лёгким <img>.
    return `<video class="workspace-board__preview-frame" src="${escapeHtml(previewUrl)}#t=0.4" preload="metadata" muted playsinline disablepictureinpicture disableremoteplayback tabindex="-1" aria-hidden="true" crossorigin="anonymous" data-preview-capture="${escapeHtml(item.id)}"></video><span class="workspace-board__preview-play" aria-hidden="true">▶</span>`;
  }
  return `<span class="workspace-board__preview-symbol" aria-hidden="true">${escapeHtml(ENTITY_ICONS[item.entityType] || "◇")}</span>`;
}

function formatQuickLookDuration(value) {
  if (value === null || value === undefined || value === "") return "";
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  const rounded = Math.round(seconds * 10) / 10;
  if (rounded < 60) return `${rounded.toLocaleString("ru-RU")} сек.`;
  const minutes = Math.floor(rounded / 60);
  const remainder = Math.round((rounded - minutes * 60) * 10) / 10;
  return remainder
    ? `${minutes} мин. ${remainder.toLocaleString("ru-RU")} сек.`
    : `${minutes} мин.`;
}

function formatQuickLookCost(minor, currency) {
  if (minor === null || minor === undefined || minor === "") return "";
  const amount = Number(minor);
  if (!Number.isFinite(amount)) return "";
  const normalizedCurrency = safeText(currency, 3).toUpperCase();
  if (/^[A-Z]{3}$/u.test(normalizedCurrency)) {
    try {
      return new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: normalizedCurrency,
        minimumFractionDigits: 2,
      }).format(amount / 100);
    } catch {
      // Preserve the exact minor-unit record when a browser does not know the currency code.
    }
  }
  return `${Math.round(amount).toLocaleString("ru-RU")} мин. ед.`;
}

function quickLookFactMarkup(label, value, { code = false } = {}) {
  const normalized = safeText(value, 1_000);
  if (!normalized) return "";
  return `<div><dt>${escapeHtml(label)}</dt><dd>${code
    ? `<code>${escapeHtml(normalized)}</code>`
    : escapeHtml(normalized)}</dd></div>`;
}

function quickLookListMarkup(title, items, tone = "") {
  if (!items?.length) return "";
  return `
    <section class="workspace-board__quicklook-list ${tone ? `is-${escapeHtml(tone)}` : ""}">
      <h4>${escapeHtml(title)}</h4>
      <ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </section>`;
}

function quickLookHistoryMarkup(title, items) {
  if (!items?.length) return "";
  return `
    <section class="workspace-board__quicklook-history">
      <h4>${escapeHtml(title)}</h4>
      <ol>${items.map((item) => `
        <li>
          <span>${escapeHtml(item.label)}</span>
          ${formatDate(item.at) ? `<time datetime="${escapeHtml(item.at)}">${escapeHtml(formatDate(item.at))}</time>` : ""}
        </li>`).join("")}</ol>
    </section>`;
}

function quickLookRelationsMarkup(relations) {
  if (!relations?.length) return "";
  return `
    <section class="workspace-board__quicklook-relations" aria-labelledby="workspace-board-quicklook-relations-title">
      <h4 id="workspace-board-quicklook-relations-title">Связи</h4>
      <ul>${relations.map((relation) => `
        <li>
          ${relation.deepLink
            ? `<a href="${escapeHtml(relation.deepLink)}">${escapeHtml(relation.label)}</a>`
            : `<span>${escapeHtml(relation.label)}</span>`}
          ${relation.status ? `<small>${escapeHtml(relation.status)}</small>` : ""}
          ${relation.id ? `<code>${escapeHtml(compactObjectId(relation.id))}</code>` : ""}
        </li>`).join("")}</ul>
    </section>`;
}

function quickLookProviderLabel(value) {
  const provider = safeText(value, 80).toLowerCase();
  const labels = {
    runway: "Runway",
    google: "Google",
    bytedance: "ByteDance",
    openai: "OpenAI",
  };
  return labels[provider] || provider;
}

function researchAuditStatusLabel(value) {
  const status = safeText(value, 80).toLowerCase();
  const labels = {
    accepted: "Принято",
    accepted_with_edits: "Принято с правками",
    rejected: "Отклонено",
    learned: "Учтено",
    selected: "Выбрано",
    excluded: "Исключено",
    pending: "Ожидает решения",
    ready: "Готово",
  };
  return labels[status] || status;
}

function generatedQuickLookMarkup(item) {
  const record = item.generationQuickLook;
  const inputLabels = { text: "Текст", image: "Изображение", video: "Видео" };
  const selectionLabels = {
    system_recommendation: "Рекомендация системы",
    research_recommendation: "Рекомендация исследования",
    performance_recommendation: "Рекомендация по результатам",
    manual_choice: "Ручной выбор человека",
    alternative_after_block: "Альтернатива после блокировки",
  };
  const qualityLabels = {
    accepted: "Проверено",
    needs_revalidation: "Нужна перепроверка",
    unproven: "Экспериментально",
  };
  const recorded = Boolean(
    record.publicLabel
    || record.model
    || record.provider
    || record.estimatedCostMinor !== null
    || record.actualCostMinor !== null
    || record.inputMode
    || record.version
    || record.reviewHistory.length
    || record.publicationHistory.length
  );
  const inputValue = record.inputMode
    ? `${inputLabels[record.inputMode] || record.inputMode}${record.referenceCount !== null
      ? ` · референсов: ${Math.max(0, Math.trunc(record.referenceCount))}`
      : ""}`
    : "";
  return `
    <section class="workspace-board__quicklook-section" data-quicklook-section="generated" aria-labelledby="workspace-board-quicklook-generated-title">
      <div class="workspace-board__quicklook-section-head">
        <p>Запись запуска</p>
        <h3 id="workspace-board-quicklook-generated-title">Созданный объект</h3>
      </div>
      ${recorded ? `
        <dl class="workspace-board__quicklook-facts">
          ${quickLookFactMarkup("Модель", record.publicLabel || record.model)}
          ${record.publicLabel && record.model ? quickLookFactMarkup("Код модели", record.model, { code: true }) : ""}
          ${quickLookFactMarkup("Провайдер", quickLookProviderLabel(record.provider))}
          ${quickLookFactMarkup("Источник выбора", selectionLabels[record.selectionSource] || record.selectionSource)}
          ${quickLookFactMarkup("Статус качества", qualityLabels[record.qualityStatus] || record.qualityStatus)}
          ${quickLookFactMarkup("Вход", inputValue)}
          ${quickLookFactMarkup("Длительность", formatQuickLookDuration(record.durationSeconds))}
          ${quickLookFactMarkup("Формат", [record.ratio, record.resolution].filter(Boolean).join(" · "))}
          ${record.audio !== null ? quickLookFactMarkup("Звук", record.audio ? "Со звуком или речью" : "Без звука") : ""}
          ${quickLookFactMarkup("Версия", record.version)}
          ${quickLookFactMarkup("Оценка стоимости", formatQuickLookCost(record.estimatedCostMinor, record.currency))}
          ${quickLookFactMarkup("Фактическая стоимость", formatQuickLookCost(record.actualCostMinor, record.currency))}
        </dl>` : `
        <p class="workspace-board__quicklook-unavailable">Модель, стоимость и входы не переданы в проекцию «Файлы». Quick Look не подставляет текущую модель вместо исторической записи.</p>`}
      ${quickLookHistoryMarkup("История проверки", record.reviewHistory)}
      ${quickLookHistoryMarkup("История публикации", record.publicationHistory)}
      ${quickLookRelationsMarkup(item.relations)}
    </section>`;
}

function researchQuickLookMarkup(item) {
  const record = item.researchQuickLook;
  const auditFacts = [
    record.categoryBindingId
      ? quickLookFactMarkup("Привязка категории", record.categoryBindingId, { code: true })
      : "",
    record.receipt.id
      ? quickLookFactMarkup("Квитанция ИИ", `${researchAuditStatusLabel(record.receipt.status) || "Зафиксирована"} · ${compactObjectId(record.receipt.id)}`)
      : "",
    record.disposition.id
      ? quickLookFactMarkup("Решение человека", `${researchAuditStatusLabel(record.disposition.status) || "Зафиксировано"} · ${compactObjectId(record.disposition.id)}`)
      : "",
    record.selection.id
      ? quickLookFactMarkup("Выбор для обучения", `${researchAuditStatusLabel(record.selection.status) || "Зафиксирован"} · ${compactObjectId(record.selection.id)}`)
      : "",
  ].filter(Boolean);
  const hasResearchContent = Boolean(
    record.source
    || record.evidenceSummary
    || record.selectedConclusions.length
    || record.rejectedConclusions.length
    || record.nextAction
  );
  return `
    <section class="workspace-board__quicklook-section" data-quicklook-section="research" aria-labelledby="workspace-board-quicklook-research-title">
      <div class="workspace-board__quicklook-section-head">
        <p>Read-only запись</p>
        <h3 id="workspace-board-quicklook-research-title">Исследование</h3>
      </div>
      ${hasResearchContent ? `
        <dl class="workspace-board__quicklook-facts">
          ${quickLookFactMarkup("Источник", record.source)}
          ${quickLookFactMarkup("Сводка доказательств", record.evidenceSummary)}
          ${quickLookFactMarkup("Следующее действие", record.nextAction)}
        </dl>
        ${quickLookListMarkup("Принятые выводы", record.selectedConclusions, "accepted")}
        ${quickLookListMarkup("Отклонённые выводы", record.rejectedConclusions, "rejected")}` : `
        <p class="workspace-board__quicklook-unavailable">Доказательства и выводы не входят в безопасную проекцию «Файлы». Откройте точную запись исследования; Quick Look не пересказывает её по косвенным данным.</p>`}
      ${auditFacts.length ? `<dl class="workspace-board__quicklook-facts workspace-board__quicklook-facts--audit">${auditFacts.join("")}</dl>` : ""}
    </section>`;
}

function sourceMediaQuickLookMarkup(item) {
  const isVideo = item.mimeType.startsWith("video/");
  const isImage = item.mimeType.startsWith("image/");
  if (!isVideo && !isImage) return quickLookRelationsMarkup(item.relations);
  const dimensions = item.width && item.height ? `${item.width} × ${item.height} px` : "";
  return `
    <section class="workspace-board__quicklook-section" data-quicklook-section="${isVideo ? "video" : "image"}" aria-labelledby="workspace-board-quicklook-media-title">
      <div class="workspace-board__quicklook-section-head">
        <p>${isVideo ? "Видео" : "Изображение"}</p>
        <h3 id="workspace-board-quicklook-media-title">Точная запись файла</h3>
      </div>
      <dl class="workspace-board__quicklook-facts">
        ${quickLookFactMarkup("Источник", item.sourceIdentity || item.originalFilename)}
        ${isVideo ? quickLookFactMarkup("Длительность", formatQuickLookDuration(item.durationSeconds)) : ""}
        ${quickLookFactMarkup("Размер кадра", dimensions)}
        ${item.versionCount !== null ? quickLookFactMarkup("Версий", String(item.versionCount)) : ""}
        ${quickLookFactMarkup("Товар", item.productName)}
        ${quickLookFactMarkup("SKU", item.sku)}
        ${quickLookFactMarkup("Артикул WB", item.wbArticle)}
      </dl>
      ${quickLookRelationsMarkup(item.relations)}
    </section>`;
}

function itemQuickLookMetadataMarkup(item) {
  if (item.entityType === "research") return researchQuickLookMarkup(item);
  if (item.entityType === "generation" || item.artifactClass === "generated_output") {
    return generatedQuickLookMarkup(item);
  }
  return sourceMediaQuickLookMarkup(item);
}

function itemCardMarkup(item, selectedItemKey, busy) {
  const selected = item.key === selectedItemKey;
  const descriptionId = `workspace-item-${domToken(item.key)}-description`;
  const artifactLabel = artifactClassLabel(item.artifactClass);
  const lifecycleLabel = lifecycleStageLabel(item.lifecycleStage);
  return `
    <article class="workspace-board__item ${selected ? "is-selected" : ""}"
             data-workspace-item-key="${escapeHtml(item.key)}"
             data-entity-type="${escapeHtml(item.entityType)}"
             data-entity-id="${escapeHtml(item.id)}"
             data-entity-kind="${escapeHtml(item.kind)}"
             data-artifact-class="${escapeHtml(item.artifactClass)}"
             data-lifecycle-stage="${escapeHtml(item.lifecycleStage)}"
             data-folder-id="${escapeHtml(item.folderId || "root")}"
             data-created-at="${escapeHtml(item.createdAt)}"
             data-read-only="${item.readOnly ? "true" : "false"}"
             data-selected="false"
             role="option"
             aria-selected="false">
      <button class="workspace-board__item-open"
              type="button"
              data-action="open-workspace-item"
              data-item-key="${escapeHtml(item.key)}"
              data-entity-type="${escapeHtml(item.entityType)}"
              data-entity-id="${escapeHtml(item.id)}"
              aria-describedby="${escapeHtml(descriptionId)}"
              aria-controls="workspace-board-item-drawer"
              aria-expanded="${selected ? "true" : "false"}"
              ${busy ? "disabled" : ""}>
        <span class="workspace-board__item-preview">${itemPreviewMarkup(item)}</span>
        <span class="workspace-board__item-copy">
          <small class="workspace-board__classification">
            <span>${escapeHtml(humanEntityType(item.entityType))}</span>
            ${artifactLabel ? `<span class="workspace-board__artifact-badge"
              data-artifact-class="${escapeHtml(item.artifactClass)}">${escapeHtml(artifactLabel)}</span>` : ""}
            ${lifecycleLabel ? `<span class="workspace-board__lifecycle-badge"
              data-lifecycle-stage="${escapeHtml(item.lifecycleStage)}">${escapeHtml(lifecycleLabel)}</span>` : ""}
          </small>
          <strong>${escapeHtml(item.title)}</strong>
          <span id="${escapeHtml(descriptionId)}">${escapeHtml(item.subtitle || humanStatus(item.status))}</span>
        </span>
        <span class="workspace-board__status" data-status="${escapeHtml(item.status)}">
          ${escapeHtml(humanStatus(item.status))}
        </span>
      </button>
      ${!item.readOnly ? `<button class="workspace-board__select-item"
              type="button"
              data-ce-v4-select-item
              data-item-key="${escapeHtml(item.key)}"
              title="Выбрать для группового действия"
              aria-label="Выбрать «${escapeHtml(item.title)}»"
              aria-pressed="false"
              ${busy ? "disabled" : ""}><span aria-hidden="true">✓</span></button>
      <button class="workspace-board__context-trigger workspace-board__context-trigger--item"
              type="button"
              data-ce-v4-context-trigger="item"
              aria-label="Действия с файлом «${escapeHtml(item.title)}»"
              title="Действия"
              ${busy ? "disabled" : ""}>⋯</button>` : ""}
      ${item.movable ? `
        <button class="workspace-board__drag-handle"
                type="button"
                draggable="${busy ? "false" : "true"}"
                data-action="open-workspace-item"
                data-workspace-drag-item
                data-entity-type="${escapeHtml(item.entityType)}"
                data-entity-id="${escapeHtml(item.id)}"
                data-item-key="${escapeHtml(item.key)}"
                aria-label="Переместить: ${escapeHtml(item.title)}"
                aria-describedby="${escapeHtml(descriptionId)}"
                title="Перетащить или нажать, чтобы выбрать место"
                ${busy ? "disabled" : ""}>
          <span aria-hidden="true">⠿</span>
        </button>` : ""}
    </article>`;
}

function itemDrawerMarkup(board, selectedItem, busy, options) {
  if (!selectedItem) {
    return `
      <aside id="workspace-board-item-drawer"
             class="workspace-board__drawer workspace-board__drawer--empty"
             aria-label="Сведения об объекте">
        <span class="workspace-board__drawer-mark" aria-hidden="true">◇</span>
        <h2>Выберите объект</h2>
        <p>Нажмите карточку, чтобы открыть детали и переместить объект без перетаскивания.</p>
      </aside>`;
  }
  const currentFolder = board.folders.find((folder) => folder.id === selectedItem.folderId);
  const moveTargets = [
    { id: "root", name: "Без папки" },
    ...board.folders
      .filter((folder) => (
        folder.status === "active"
        && folder.smart !== true
        && !folder.systemRole
      ))
      .map((folder) => ({ ...folder, name: folderDisplayName(folder) })),
  ].filter((folder) => folder.id !== (selectedItem.folderId || "root"));
  const formattedSize = formatBytes(selectedItem.sizeBytes);
  const formattedDate = formatDate(selectedItem.createdAt);
  const creator = itemCreatorAttribution(selectedItem, options);
  const researchLinks = selectedItem.entityType === "research"
    ? [
      selectedItem.deepLink ? { href: selectedItem.deepLink, label: "Открыть исследование" } : null,
      selectedItem.aiDeepLink ? { href: selectedItem.aiDeepLink, label: "Открыть квитанцию в ИИ-центре" } : null,
    ].filter(Boolean)
    : [];
  return `
    <aside id="workspace-board-item-drawer"
           class="workspace-board__drawer"
           aria-labelledby="workspace-board-drawer-title"
           data-workspace-item-drawer
           data-item-key="${escapeHtml(selectedItem.key)}"
           data-entity-type="${escapeHtml(selectedItem.entityType)}"
           data-artifact-class="${escapeHtml(selectedItem.artifactClass)}">
      <div class="workspace-board__drawer-head">
        <div>
          <p>${escapeHtml(humanEntityType(selectedItem.entityType))}</p>
          <h2 id="workspace-board-drawer-title">${escapeHtml(selectedItem.title)}</h2>
        </div>
        <button class="workspace-board__drawer-close"
                type="button"
                data-action="close-workspace-item"
                aria-label="Закрыть сведения об объекте">×</button>
      </div>
      <div class="workspace-board__drawer-preview">${itemPreviewMarkup(selectedItem, true)}</div>
      ${selectedItem.description ? `<p class="workspace-board__drawer-description">${escapeHtml(selectedItem.description)}</p>` : ""}
      <div class="workspace-board__quicklook-sections">
        ${itemQuickLookMetadataMarkup(selectedItem)}
      </div>
      ${selectedItem.entityType === "media" && ["product_photo", "packshot"].includes(selectedItem.kind) ? `
        <div class="workspace-board__drawer-actions" aria-label="Доступные действия">
          <button class="btn" type="button"
                  data-action="create-from-workspace-media"
                  data-entity-id="${escapeHtml(selectedItem.id)}"
                  ${busy ? "disabled" : ""}>Создать из этого файла</button>
        </div>` : ""}
      ${selectedItem.entityType === "media" && selectedItem.kind === "generated_video" && selectedItem.status === "ready" ? `
        <div class="workspace-board__drawer-actions" aria-label="Доступные действия">
          <button class="btn btn-primary" type="button"
                  data-action="publish-workspace-result"
                  data-entity-id="${escapeHtml(selectedItem.id)}"
                  data-entity-title="${escapeHtml(selectedItem.title)}"
                  ${busy ? "disabled" : ""}>Одобрить и разместить</button>
        </div>` : ""}
      ${selectedItem.entityType === "media" && selectedItem.kind === "generated_video" && selectedItem.status === "ready" ? `
        <div class="workspace-board__drawer-actions" aria-label="Доступные действия">
          <button class="btn btn-primary" type="button"
                  data-action="publish-workspace-result"
                  data-entity-id="${escapeHtml(selectedItem.id)}"
                  data-entity-title="${escapeHtml(selectedItem.title)}"
                  ${busy ? "disabled" : ""}>Одобрить и разместить</button>
        </div>` : ""}
      ${researchLinks.length ? `
        <div class="workspace-board__research-links" aria-label="Доступные действия">
          ${researchLinks.map((link) => `<a class="btn btn-secondary" href="${escapeHtml(link.href)}">${escapeHtml(link.label)}</a>`).join("")}
        </div>` : ""}
      <dl class="workspace-board__drawer-facts">
        <div><dt>Статус</dt><dd>${escapeHtml(humanStatus(selectedItem.status))}</dd></div>
        <div><dt>Папка</dt><dd>${escapeHtml(
          selectedItem.entityType === "research"
            ? "Отдельный журнал исследования"
            : currentFolder ? folderDisplayName(currentFolder) : "Без папки",
        )}</dd></div>
        ${selectedItem.artifactClass ? `<div><dt>Роль файла</dt><dd><span class="workspace-board__artifact-badge"
          data-artifact-class="${escapeHtml(selectedItem.artifactClass)}">${escapeHtml(artifactClassLabel(selectedItem.artifactClass))}</span></dd></div>` : ""}
        ${selectedItem.lifecycleStage ? `<div><dt>Этап</dt><dd><span class="workspace-board__lifecycle-badge"
          data-lifecycle-stage="${escapeHtml(selectedItem.lifecycleStage)}">${escapeHtml(lifecycleStageLabel(selectedItem.lifecycleStage))}</span></dd></div>` : ""}
        ${selectedItem.kind ? `<div><dt>Тип</dt><dd>${escapeHtml(selectedItem.kind)}</dd></div>` : ""}
        ${creator ? `<div><dt>${escapeHtml(creator.label)}</dt><dd>
          <span title="ID ${escapeHtml(creator.creatorId)}">${escapeHtml(creator.person)}</span>
        </dd></div>` : ""}
        ${formattedSize ? `<div><dt>Размер</dt><dd>${escapeHtml(formattedSize)}</dd></div>` : ""}
        ${formattedDate ? `<div><dt>Добавлено</dt><dd>${escapeHtml(formattedDate)}</dd></div>` : ""}
        <div><dt>ID</dt><dd><code>${escapeHtml(selectedItem.id)}</code></dd></div>
      </dl>
      ${selectedItem.objectName || selectedItem.sha256 ? `
        <details class="workspace-board__quicklook-technical">
          <summary>Техническая идентичность</summary>
          <dl>
            ${quickLookFactMarkup("Объект", selectedItem.objectName, { code: true })}
            ${quickLookFactMarkup("SHA-256", selectedItem.sha256, { code: true })}
          </dl>
        </details>` : ""}
      ${selectedItem.movable ? `
        <section class="workspace-board__move-panel" aria-labelledby="workspace-board-move-title">
          <h3 id="workspace-board-move-title">Переместить в папку</h3>
          <p>Это доступная замена drag-and-drop для клавиатуры и телефона.</p>
          <div class="workspace-board__move-targets">
            ${moveTargets.length ? moveTargets.map((folder) => `
              <button type="button"
                      data-action="move-workspace-item"
                      data-item-key="${escapeHtml(selectedItem.key)}"
                      data-entity-type="${escapeHtml(selectedItem.entityType)}"
                      data-entity-id="${escapeHtml(selectedItem.id)}"
                      data-folder-id="${escapeHtml(folder.id)}"
                      data-target-folder-id="${escapeHtml(folder.id)}"
                      ${busy ? "disabled" : ""}>
                <span aria-hidden="true">◇</span>
                <span>${escapeHtml(folder.name)}</span>
              </button>`).join("") : `<span class="workspace-board__muted">Других папок пока нет.</span>`}
          </div>
        </section>` : ""}
    </aside>`;
}

export function workspaceBoardMarkup(board, options = {}) {
  const normalizedBoard = normalizeWorkspaceBoard(board);
  const normalizedOptions = {
    selectedFolderId: selectedFolder(options, normalizedBoard),
    selectedItemKey: safeText(options.selectedItemKey, ID_MAX_LENGTH * 2 + 1),
    query: safeText(options.query, QUERY_MAX_LENGTH),
    entityType: normalizedEntityType(options.entityType, "media"),
    provenanceFilter: normalizedProvenanceFilter(options.provenanceFilter),
    busy: options.busy === true,
    notice: safeText(options.notice, 1_000),
    error: safeText(options.error, 1_000),
    pendingArchiveFolderId: safeText(options.pendingArchiveFolderId, ID_MAX_LENGTH),
    visibleItemLimit: Math.min(300, Math.max(1, Number(options.visibleItemLimit) || 80)),
    landingOverview: options.landingOverview === true,
    viewerProfileId: normalizedId(options.viewerProfileId),
    viewerName: safeText(options.viewerName, 180),
  };
  if (options.entityType === "all") normalizedOptions.entityType = "all";
  if (
    normalizedOptions.entityType !== "all" &&
    !normalizedBoard.entityTypes.includes(normalizedOptions.entityType)
  ) normalizedOptions.entityType = "all";
  const items = filteredItems(
    normalizedBoard,
    normalizedOptions.selectedFolderId,
    normalizedOptions.query,
    normalizedOptions.entityType,
    normalizedOptions.provenanceFilter,
  );
  const visibleItems = items.slice(0, normalizedOptions.visibleItemLimit);
  const selectedItem = workspaceBoardItemByKey(normalizedBoard, normalizedOptions.selectedItemKey);
  const showLandingOverview = Boolean(
    normalizedOptions.landingOverview
    && normalizedOptions.selectedFolderId === "all"
    && !normalizedOptions.selectedItemKey
    && !normalizedOptions.query
    && normalizedOptions.entityType === "all"
    && normalizedOptions.provenanceFilter === "all"
  );
  const selectedFolderName = normalizedOptions.selectedFolderId === "all"
    ? "Все файлы"
    : normalizedOptions.selectedFolderId === "root"
      ? "Без папки"
      : folderDisplayName(
        normalizedBoard.folders.find((folder) => folder.id === normalizedOptions.selectedFolderId),
      );

  return `
    <section class="workspace-board"
             aria-labelledby="workspace-board-title"
             aria-busy="${normalizedOptions.busy ? "true" : "false"}">
      <div id="workspace-board-announcer"
           class="workspace-board__sr-only"
           role="status"
           aria-live="polite"
           aria-atomic="true">${escapeHtml(normalizedOptions.notice)}</div>
      <header class="workspace-board__head">
        <div>
          <p class="workspace-board__eyebrow">Рабочее пространство</p>
          <h1 id="workspace-board-title">Файлы, исследования и папки</h1>
          <p>Источники, исследовательские журналы и созданные результаты разделены по происхождению. Откройте карточку, чтобы увидеть точную запись.</p>
        </div>
        <span class="workspace-board__head-count">${normalizedBoard.items.length} ${normalizedBoard.partial ? "загружено" : "объектов"}</span>
      </header>
      ${normalizedOptions.error ? `
        <div class="workspace-board__message workspace-board__message--error" role="alert">
          <strong>Действие не выполнено</strong>
          <span>${escapeHtml(normalizedOptions.error)}</span>
        </div>` : ""}
      ${normalizedOptions.notice ? `
        <div class="workspace-board__message workspace-board__message--notice">
          <span>${escapeHtml(normalizedOptions.notice)}</span>
          <button type="button" data-action="refresh-section" data-section="board">Повторить</button>
        </div>` : ""}
      <div class="workspace-board__layout">
        <aside class="workspace-board__sidebar" aria-label="Управление папками">
          <div class="workspace-board__sidebar-head">
            <p>Проекты и папки</p>
            <small>Корневая папка — отдельный проект</small>
          </div>
          ${folderTreeMarkup(
            normalizedBoard,
            showLandingOverview ? "" : normalizedOptions.selectedFolderId,
            normalizedOptions.busy,
          )}
          ${folderManagementMarkup(
            normalizedBoard,
            normalizedOptions.selectedFolderId,
            normalizedOptions.busy,
            normalizedOptions.pendingArchiveFolderId,
          )}
        </aside>
        <section class="workspace-board__content" aria-labelledby="workspace-board-collection-title">
          ${showLandingOverview
            ? workspaceBoardOverviewMarkup(normalizedBoard, normalizedOptions.busy)
            : `
              ${folderBreadcrumbMarkup(normalizedBoard, normalizedOptions.selectedFolderId, normalizedOptions.busy)}
              ${filterMarkup(normalizedBoard, normalizedOptions, items.length, normalizedOptions.busy)}
              <div class="workspace-board__collection-head">
                <div>
                  <p>Открытая папка</p>
                  <h2 id="workspace-board-collection-title">${escapeHtml(selectedFolderName)}</h2>
                </div>
                <div class="workspace-board__collection-meta">
                  <small>${visibleItems.length}${visibleItems.length < items.length ? ` из ${items.length}` : ""} на экране</small>
                  <span class="workspace-board__context-hint">ПКМ или ⋯ — быстрые действия</span>
                </div>
              </div>
              ${items.length ? `
                <div class="workspace-board__grid"
                     role="listbox"
                     aria-label="Объекты папки"
                     aria-multiselectable="true">
                  ${visibleItems.map((item) => itemCardMarkup(
                    item,
                    normalizedOptions.selectedItemKey,
                    normalizedOptions.busy,
                  )).join("")}
                </div>
                ${visibleItems.length < items.length ? `
                  <div class="workspace-board-pagination">
                    <button class="btn btn-secondary" type="button" data-action="show-more-workspace-items">
                      Показать следующие ${Math.min(80, items.length - visibleItems.length)}
                    </button>
                    <span class="muted tiny">Число карточек на экране ограничено, чтобы браузер не зависал.</span>
                  </div>` : ""}` : `
                <div class="workspace-board__empty">
                  <span aria-hidden="true">◇</span>
                  <h3>Здесь пока пусто</h3>
                  <p>${normalizedOptions.query || normalizedOptions.entityType !== "all" || normalizedOptions.provenanceFilter !== "all"
                    ? "Сбросьте фильтры или выберите другую папку."
                    : "Добавьте объект или переместите его сюда из другой папки."}</p>
                  ${normalizedOptions.query || normalizedOptions.entityType !== "all" || normalizedOptions.provenanceFilter !== "all" ? `
                    <button type="button" data-action="reset-workspace-filters">Сбросить фильтры</button>` : ""}
                </div>`}`}
        </section>
        ${itemDrawerMarkup(normalizedBoard, selectedItem, normalizedOptions.busy, normalizedOptions)}
      </div>
    </section>`;
}
