const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const MAX_EXACT_VIDEO_CAPTURE_BYTES = 52_428_800;

function normalized(value) {
  return String(value || "").trim().toLowerCase();
}

function objectKey(value) {
  const candidate = String(value || "").trim();
  return candidate && candidate.length <= 1_000 ? candidate : "";
}

function byteHex(buffer) {
  return Array.from(new Uint8Array(buffer), (byte) => (
    byte.toString(16).padStart(2, "0")
  )).join("");
}

export async function verifyExactYoutubeResearchCaptureBlob(
  media,
  blob,
  {
    subtle = globalThis.crypto?.subtle,
  } = {},
) {
  const expectedSize = Number(media?.sizeBytes);
  const expectedSha256 = normalized(media?.sha256);
  if (
    normalized(media?.mimeType) !== "video/mp4"
    || !Number.isInteger(expectedSize)
    || expectedSize < 1
    || expectedSize > MAX_EXACT_VIDEO_CAPTURE_BYTES
    || !SHA256_PATTERN.test(expectedSha256)
    || typeof blob?.arrayBuffer !== "function"
    || typeof blob?.slice !== "function"
    || typeof subtle?.digest !== "function"
  ) {
    return { ok: false, code: "exact_youtube_capture_blob_context_invalid" };
  }
  if (Number(blob.size) !== expectedSize) {
    return { ok: false, code: "exact_youtube_capture_blob_size_mismatch" };
  }
  try {
    const bytes = await blob.arrayBuffer();
    if (
      bytes.byteLength !== expectedSize
      || bytes.byteLength > MAX_EXACT_VIDEO_CAPTURE_BYTES
    ) {
      return {
        ok: false,
        code: "exact_youtube_capture_blob_size_mismatch",
      };
    }
    const actualSha256 = byteHex(await subtle.digest("SHA-256", bytes));
    if (actualSha256 !== expectedSha256) {
      return {
        ok: false,
        code: "exact_youtube_capture_blob_hash_mismatch",
      };
    }
    const normalizedBlob = blob.slice(0, expectedSize, "video/mp4");
    if (
      Number(normalizedBlob?.size) !== expectedSize
      || String(normalizedBlob?.type || "").toLowerCase() !== "video/mp4"
    ) {
      return {
        ok: false,
        code: "exact_youtube_capture_blob_read_failed",
      };
    }
    return {
      ok: true,
      code: "ok",
      blob: normalizedBlob,
      sizeBytes: bytes.byteLength,
      sha256: actualSha256,
    };
  } catch {
    return {
      ok: false,
      code: "exact_youtube_capture_blob_read_failed",
    };
  }
}

export async function captureVerifiedPrivateVideoBlob(
  media,
  blob,
  capture,
  {
    subtle = globalThis.crypto?.subtle,
    createObjectURL = (value) => globalThis.URL.createObjectURL(value),
    revokeObjectURL = (value) => globalThis.URL.revokeObjectURL(value),
  } = {},
) {
  if (
    typeof capture !== "function"
    || typeof createObjectURL !== "function"
    || typeof revokeObjectURL !== "function"
  ) {
    return { ok: false, code: "private_video_capture_callback_invalid" };
  }
  const verified = await verifyExactYoutubeResearchCaptureBlob(
    media,
    blob,
    { subtle },
  );
  if (!verified.ok) return verified;
  let objectUrl = "";
  try {
    objectUrl = String(createObjectURL(verified.blob) || "").trim();
    if (!objectUrl.startsWith("blob:")) {
      return { ok: false, code: "private_video_capture_object_url_invalid" };
    }
    const evidence = await capture({ ...media, url: objectUrl });
    return {
      ok: true,
      code: "ok",
      evidence,
      sizeBytes: verified.sizeBytes,
      sha256: verified.sha256,
    };
  } finally {
    if (objectUrl) revokeObjectURL(objectUrl);
  }
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
