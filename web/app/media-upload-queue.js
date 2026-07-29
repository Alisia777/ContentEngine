export const DEFAULT_MEDIA_UPLOAD_BATCH_LIMIT = 20;
export const DEFAULT_MEDIA_UPLOAD_CONCURRENCY = 3;

export const MEDIA_UPLOAD_MIME_TYPES = Object.freeze([
  "image/jpeg",
  "image/png",
  "image/webp",
  "video/mp4",
]);

export function mediaFileSelectionKey(file) {
  return [
    String(file?.name || ""),
    Number(file?.size) || 0,
    Number(file?.lastModified) || 0,
  ].join(":");
}

export function mergeMediaFileSelection(
  currentFiles,
  addedFiles,
  limit = DEFAULT_MEDIA_UPLOAD_BATCH_LIMIT,
) {
  const boundedLimit = Math.max(1, Math.min(50, Number(limit) || 1));
  const current = Array.from(currentFiles || []);
  const added = Array.from(addedFiles || []);
  const files = [];
  const seen = new Set();
  [...current, ...added].forEach((file) => {
    if (!file || !String(file.name || "") || Number(file.size) <= 0) return;
    const key = mediaFileSelectionKey(file);
    if (seen.has(key) || files.length >= boundedLimit) return;
    seen.add(key);
    files.push(file);
  });
  return {
    files,
    skipped: Math.max(0, current.length + added.length - files.length),
  };
}

export function mediaFileValidationError(file, maxUploadBytes) {
  if (!file || Number(file.size) <= 0) return "Файл пустой.";
  const maxBytes = Math.max(1, Number(maxUploadBytes) || 1);
  if (Number(file.size) > maxBytes) {
    return "Файл больше допустимого размера.";
  }
  if (!MEDIA_UPLOAD_MIME_TYPES.includes(String(file.type || ""))) {
    return "Нужен JPG, PNG, WEBP или MP4.";
  }
  return "";
}

export function mediaUploadWorkerCount(
  fileCount,
  concurrency = DEFAULT_MEDIA_UPLOAD_CONCURRENCY,
) {
  const total = Math.max(0, Math.floor(Number(fileCount) || 0));
  const maximum = Math.max(1, Math.floor(Number(concurrency) || 1));
  return Math.min(total, maximum);
}
