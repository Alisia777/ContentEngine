const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;

function normalized(value) {
  return String(value || "").trim().toLowerCase();
}

function objectKey(value) {
  const candidate = String(value || "").trim();
  return candidate && candidate.length <= 1_000 ? candidate : "";
}

export function resolveExactYoutubeResearchCaptureMedia(
  cachedMedia,
  freshSource,
  { projectId = "", mediaId = "" } = {},
) {
  const expectedProjectId = normalized(projectId);
  const expectedMediaId = normalized(mediaId);
  const cached = cachedMedia && typeof cachedMedia === "object"
    ? cachedMedia
    : {};
  const fresh = freshSource?.media && typeof freshSource.media === "object"
    ? freshSource.media
    : {};
  const cachedIdentity = {
    id: normalized(cached.id),
    status: normalized(cached.status),
    kind: normalized(cached.kind),
    mimeType: normalized(cached.mimeType),
    sha256: normalized(cached.sha256),
    objectName: objectKey(cached.objectName),
    sizeBytes: Number(cached.sizeBytes),
  };
  const freshIdentity = {
    id: normalized(fresh.id),
    projectId: normalized(fresh.project_id),
    status: normalized(fresh.status),
    kind: normalized(fresh.kind),
    mimeType: normalized(fresh.mime_type),
    artifactClass: normalized(fresh.artifact_class),
    lifecycleStage: normalized(fresh.lifecycle_stage),
    sha256: normalized(fresh.sha256),
    objectName: objectKey(fresh.object_key),
    sizeBytes: Number(fresh.size_bytes),
  };
  const authoritative = Boolean(
    UUID_PATTERN.test(expectedProjectId)
    && UUID_PATTERN.test(expectedMediaId)
    && freshIdentity.id === expectedMediaId
    && freshIdentity.projectId === expectedProjectId
    && freshIdentity.status === "ready"
    && freshIdentity.kind === "source_video"
    && freshIdentity.mimeType === "video/mp4"
    && freshIdentity.artifactClass === "source"
    && freshIdentity.lifecycleStage === "sources"
    && SHA256_PATTERN.test(freshIdentity.sha256)
    && freshIdentity.objectName
    && Number.isInteger(freshIdentity.sizeBytes)
    && freshIdentity.sizeBytes > 0
  );
  const cachedMatches = Boolean(
    cachedIdentity.id === expectedMediaId
    && cachedIdentity.status === freshIdentity.status
    && cachedIdentity.kind === freshIdentity.kind
    && cachedIdentity.mimeType === freshIdentity.mimeType
    && cachedIdentity.sha256 === freshIdentity.sha256
    && cachedIdentity.objectName === freshIdentity.objectName
    && cachedIdentity.sizeBytes === freshIdentity.sizeBytes
  );
  if (!authoritative || !cachedMatches) {
    return {
      ok: false,
      code: "exact_youtube_research_capture_media_mismatch",
      media: null,
    };
  }
  return {
    ok: true,
    code: "ok",
    media: {
      ...cached,
      id: freshIdentity.id,
      projectId: freshIdentity.projectId,
      status: freshIdentity.status,
      kind: freshIdentity.kind,
      mimeType: freshIdentity.mimeType,
      artifactClass: freshIdentity.artifactClass,
      lifecycleStage: freshIdentity.lifecycleStage,
      sha256: freshIdentity.sha256,
      objectName: freshIdentity.objectName,
      sizeBytes: freshIdentity.sizeBytes,
      isVideo: true,
      isImage: false,
      supported: true,
      url: "",
    },
  };
}

export function exactYoutubeResearchFailureRecovery(
  evidence,
  { paidDispatchStarted = false } = {},
) {
  const status = normalized(evidence?.status);
  const payment = paidDispatchStarted
    ? "Статус платного анализа не подтверждён; не запускайте новый анализ до проверки текущей очереди."
    : "Платный анализ не начат.";
  if (status === "ready") {
    return {
      status,
      message: `Пять кадров уже подтверждены и будут использованы при повторе без нового чтения MP4. ${payment}`,
    };
  }
  if (status === "commit_pending") {
    return {
      status,
      message: `Кадры загружены; при повторе портал продолжит тот же серверный commit без повторного захвата. ${payment}`,
    };
  }
  return {
    status: "none",
    message: `Кадры не сохранены. ${payment} Безопасно повторите подготовку.`,
  };
}
