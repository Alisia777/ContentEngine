// Потоковая приёмка результата провайдера: скачать ролик, посчитать sha256,
// положить в Storage — НЕ держа файл в памяти целиком.
//
// ПОЧЕМУ. Раньше ролик читался в изолят целиком: массив частей, склейка в
// один буфер, копия в теле загрузки в Storage — три-четыре копии файла в
// одной функции. Пятисекундный Kling (11 МБ) проходил, двенадцатисекундный
// (≈30 МБ) валил `creator-generate` с «Memory limit exceeded» (HTTP 546) на
// каждом опросе воркера, и оплаченный наряд висел в `processing` сутками с
// нулём опросов. Деньги зарезервированы, ролика нет, очередь заперта.
//
// КАК. Ролик проходит потоком дважды и ни разу не буферизуется целиком:
//   1-й проход — только sha256 и размер (node:crypto считает хеш по частям);
//   2-й проход — тот же адрес льётся в Storage потоком, а хеш с первого
//   прохода уходит в user-metadata объекта: база сверяет его при зачёте
//   результата (`generation_strategy_provider_output_storage_mismatch`), и
//   узнать хеш раньше, чем отправить заголовки загрузки, иначе нельзя.
// Второй проход пересчитывает хеш и размер и обязан совпасть с первым: если
// провайдер отдал другие байты, объект в Storage результатом не считается.
// Два прохода по сети дешевле одной потерянной оплаченной задачи.
//
// ПРЕДЕЛЫ. Размер ограничен `maximumBytes` на лету (лишний байт — отказ до
// того, как он попадёт в Storage), тип файла сверяется по первым байтам
// (`sniff`), один дедлайн держится на всём пути, включая тела ответов: CDN,
// отдавший заголовки и замолчавший, не оставит наряд в `processing` навсегда.
//
// Модуль не знает ни про наряды, ни про провайдеров: на входе адрес и имя
// объекта, на выходе размер и хеш либо закрытый код отказа. Поэтому его можно
// проверить настоящим HTTP без облака — см. provider-output-archive_test.ts.

import { createHash } from "node:crypto";

export type ProviderOutputArchiveFailureCode =
  | "output_download_failed"
  | "output_validation_failed"
  | "output_upload_failed";

export type ProviderOutputArchiveResult =
  | { ok: true; size_bytes: number; sha256: string }
  | { ok: false; code: ProviderOutputArchiveFailureCode };

export type ProviderOutputArchiveArgs = {
  url: string;
  headers?: Record<string, string>;
  timeoutMs: number;
  maximumBytes: number;
  allowedMimeTypes: ReadonlySet<string>;
  // Первые байты файла (до PROVIDER_OUTPUT_SNIFF_BYTES): MP4 — `ftyp` по
  // смещению 4, PNG — сигнатура и `IHDR`. Короткий файл проверяется тем, что
  // есть.
  sniff: (head: Uint8Array) => boolean;
  storage: { supabaseUrl: string; serviceRoleKey: string; bucket: string };
  objectName: string;
  contentType: string;
};

export const PROVIDER_OUTPUT_SNIFF_BYTES = 32;

class ProviderOutputSizeInvalidError extends Error {
  constructor() {
    super("provider_output_size_invalid");
    this.name = "ProviderOutputSizeInvalidError";
  }
}

class ProviderOutputSniffInvalidError extends Error {
  constructor() {
    super("provider_output_sniff_invalid");
    this.name = "ProviderOutputSniffInvalidError";
  }
}

function mimeTypeOf(response: Response): string {
  return (response.headers.get("content-type") ?? "")
    .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
}

async function openProviderOutputStream(
  url: string,
  headers: Record<string, string>,
  signal: AbortSignal,
  allowedMimeTypes: ReadonlySet<string>,
  maximumBytes: number,
): Promise<
  | { ok: true; response: Response; declaredSize: number | null }
  | { ok: false; code: ProviderOutputArchiveFailureCode }
> {
  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      redirect: "manual",
      headers,
      signal,
    });
  } catch {
    return { ok: false, code: "output_download_failed" };
  }
  if (response.status !== 200 || response.body === null) {
    await response.body?.cancel();
    return { ok: false, code: "output_download_failed" };
  }
  if (!allowedMimeTypes.has(mimeTypeOf(response))) {
    await response.body.cancel();
    return { ok: false, code: "output_validation_failed" };
  }
  const declared = response.headers.get("content-length");
  let declaredSize: number | null = null;
  if (declared !== null) {
    const size = Number(declared);
    if (!Number.isSafeInteger(size) || size < 1 || size > maximumBytes) {
      await response.body.cancel();
      return { ok: false, code: "output_validation_failed" };
    }
    declaredSize = size;
  }
  return { ok: true, response, declaredSize };
}

// Прозрачный счётчик: считает размер и хеш, сверяет первые байты, а части
// пропускает дальше без копирования. Отказ по форме или размеру бросается
// внутри потока, и его код запоминается снаружи, потому что fetch с
// телом-потоком оборачивает причину отказа в собственную ошибку.
export function providerOutputMeter(
  maximumBytes: number,
  sniff: (head: Uint8Array) => boolean,
  failure: { code: ProviderOutputArchiveFailureCode | null },
): {
  stream: TransformStream<Uint8Array, Uint8Array>;
  finish: () => { size: number; sha256: string };
} {
  const hasher = createHash("sha256");
  let size = 0;
  let head = new Uint8Array(0);
  let sniffed = false;
  const stream = new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      size += chunk.byteLength;
      if (size > maximumBytes) {
        failure.code = "output_validation_failed";
        throw new ProviderOutputSizeInvalidError();
      }
      if (!sniffed) {
        const merged = new Uint8Array(Math.min(
          PROVIDER_OUTPUT_SNIFF_BYTES,
          head.byteLength + chunk.byteLength,
        ));
        merged.set(head.subarray(0, merged.byteLength), 0);
        if (merged.byteLength > head.byteLength) {
          merged.set(
            chunk.subarray(0, merged.byteLength - head.byteLength),
            head.byteLength,
          );
        }
        head = merged;
        if (head.byteLength >= PROVIDER_OUTPUT_SNIFF_BYTES) {
          sniffed = true;
          if (!sniff(head)) {
            failure.code = "output_validation_failed";
            throw new ProviderOutputSniffInvalidError();
          }
        }
      }
      hasher.update(chunk);
      controller.enqueue(chunk);
    },
    flush() {
      // Файл короче окна сверки — проверяем то, что есть: пустой или
      // обрезанный ответ обязан упасть здесь, а не попасть в архив.
      if (!sniffed) {
        sniffed = true;
        if (size < 1 || !sniff(head)) {
          failure.code = "output_validation_failed";
          throw new ProviderOutputSniffInvalidError();
        }
      }
    },
  });
  return {
    stream,
    finish: () => ({ size, sha256: hasher.digest("hex") }),
  };
}

export function providerOutputStorageUrl(
  supabaseUrl: string,
  bucket: string,
  objectName: string,
): string {
  const objectPath = objectName.split("/").map((segment) =>
    encodeURIComponent(segment)
  ).join("/");
  return `${supabaseUrl.replace(/\/+$/u, "")}/storage/v1/object/${bucket}/` +
    objectPath;
}

export async function archiveProviderOutputStream(
  args: ProviderOutputArchiveArgs,
): Promise<ProviderOutputArchiveResult> {
  const { supabaseUrl, serviceRoleKey, bucket } = args.storage;
  if (supabaseUrl === "" || serviceRoleKey === "" || bucket === "") {
    return { ok: false, code: "output_upload_failed" };
  }
  const headers = args.headers ?? {};
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), args.timeoutMs);
  try {
    // Проход 1: хеш и размер без буфера.
    const first = await openProviderOutputStream(
      args.url,
      headers,
      controller.signal,
      args.allowedMimeTypes,
      args.maximumBytes,
    );
    if (!first.ok) return first;
    const firstFailure: { code: ProviderOutputArchiveFailureCode | null } = {
      code: null,
    };
    const firstMeter = providerOutputMeter(
      args.maximumBytes,
      args.sniff,
      firstFailure,
    );
    let firstPass: { size: number; sha256: string };
    try {
      await first.response.body!.pipeThrough(firstMeter.stream).pipeTo(
        new WritableStream<Uint8Array>(),
        { signal: controller.signal },
      );
      firstPass = firstMeter.finish();
    } catch {
      return { ok: false, code: firstFailure.code ?? "output_download_failed" };
    }
    if (first.declaredSize !== null && first.declaredSize !== firstPass.size) {
      return { ok: false, code: "output_download_failed" };
    }

    // Проход 2: тот же адрес — потоком в Storage, хеш уже известен.
    const second = await openProviderOutputStream(
      args.url,
      headers,
      controller.signal,
      args.allowedMimeTypes,
      args.maximumBytes,
    );
    if (!second.ok) return second;
    const secondFailure: { code: ProviderOutputArchiveFailureCode | null } = {
      code: null,
    };
    const secondMeter = providerOutputMeter(
      args.maximumBytes,
      args.sniff,
      secondFailure,
    );
    const metadata = btoa(JSON.stringify({ sha256: firstPass.sha256 }));
    let upload: Response;
    try {
      upload = await fetch(
        providerOutputStorageUrl(supabaseUrl, bucket, args.objectName),
        {
          method: "POST",
          headers: {
            authorization: `Bearer ${serviceRoleKey}`,
            apikey: serviceRoleKey,
            "content-type": args.contentType,
            "cache-control": "max-age=31536000",
            "x-upsert": "true",
            "x-metadata": metadata,
          },
          body: second.response.body!.pipeThrough(secondMeter.stream),
          signal: controller.signal,
          // Тело-поток по стандарту fetch требует явного полудуплекса; Deno
          // поле принимает, а TypeScript в RequestInit его не знает.
          ...({ duplex: "half" } as Record<string, string>),
        },
      );
    } catch {
      return {
        ok: false,
        code: secondFailure.code ?? "output_download_failed",
      };
    }
    // Тело ответа Storage нужно дочитать, иначе соединение не освободится.
    await upload.body?.cancel();
    if (secondFailure.code !== null) {
      return { ok: false, code: secondFailure.code };
    }
    if (!upload.ok) return { ok: false, code: "output_upload_failed" };
    const secondPass = secondMeter.finish();
    if (
      secondPass.size !== firstPass.size ||
      secondPass.sha256 !== firstPass.sha256
    ) {
      // Провайдер отдал другие байты между проходами: объект в Storage не
      // соответствует объявленному хешу и результатом считаться не может.
      // База всё равно отвергла бы его сверкой метаданных; здесь отказ
      // честнее и раньше.
      return { ok: false, code: "output_download_failed" };
    }
    return { ok: true, size_bytes: firstPass.size, sha256: firstPass.sha256 };
  } finally {
    clearTimeout(timeout);
  }
}
