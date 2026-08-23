// Проверка потоковой приёмки настоящим HTTP, без облака и без ключей.
//
// Локальный сервер играет две роли сразу: CDN провайдера (отдаёт «ролик» по
// частям) и Storage Supabase (принимает POST /storage/v1/object/…, читает
// тело потоком и запоминает заголовки). Так проверяется именно то, что
// падало в проде: большой файл проходит, память не растёт на его размер,
// хеш и размер совпадают с тем, что получил Storage, а заголовок метаданных
// несёт sha256 первого прохода.

import { createHash } from "node:crypto";
import {
  archiveProviderOutputStream,
  PROVIDER_OUTPUT_SNIFF_BYTES,
  providerOutputMeter,
} from "./provider-output-archive.ts";

const MP4_HEAD = new Uint8Array([
  0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70, // ....ftyp
  0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x02, 0x00, // isom....
  0x69, 0x73, 0x6f, 0x6d, 0x69, 0x73, 0x6f, 0x32, // isomiso2
  0x61, 0x76, 0x63, 0x31, 0x6d, 0x70, 0x34, 0x31, // avc1mp41
]);

function isMp4(bytes: Uint8Array): boolean {
  return bytes.byteLength >= 12 && bytes[4] === 0x66 && bytes[5] === 0x74 &&
    bytes[6] === 0x79 && bytes[7] === 0x70;
}

// Детерминированный «ролик»: заголовок MP4 + псевдослучайные байты, чтобы
// хеш был осмысленным, а память не сжимала повторы.
function makeChunk(index: number, size: number): Uint8Array {
  const chunk = new Uint8Array(size);
  let state = (index + 1) * 2654435761 >>> 0;
  for (let i = 0; i < size; i += 1) {
    state = (state * 1664525 + 1013904223) >>> 0;
    chunk[i] = state >>> 24;
  }
  return chunk;
}

type Served = {
  totalBytes: number;
  sha256: string;
  stream: () => ReadableStream<Uint8Array>;
};

function makeServedVideo(totalBytes: number, chunkSize: number): Served {
  const hasher = createHash("sha256");
  const chunkCount = Math.ceil((totalBytes - MP4_HEAD.byteLength) / chunkSize);
  hasher.update(MP4_HEAD);
  let remaining = totalBytes - MP4_HEAD.byteLength;
  for (let index = 0; index < chunkCount; index += 1) {
    const size = Math.min(chunkSize, remaining);
    hasher.update(makeChunk(index, size));
    remaining -= size;
  }
  return {
    totalBytes,
    sha256: hasher.digest("hex"),
    stream: () => {
      let index = -1;
      let left = totalBytes - MP4_HEAD.byteLength;
      return new ReadableStream<Uint8Array>({
        pull(controller) {
          if (index < 0) {
            index = 0;
            controller.enqueue(MP4_HEAD);
            return;
          }
          if (left <= 0) {
            controller.close();
            return;
          }
          const size = Math.min(chunkSize, left);
          controller.enqueue(makeChunk(index, size));
          index += 1;
          left -= size;
        },
      });
    },
  };
}

type Upload = {
  path: string;
  headers: Headers;
  size: number;
  sha256: string;
};

async function withTestServer(
  served: Served,
  options: {
    videoStatus?: number;
    videoContentType?: string;
    declareLength?: boolean;
    uploadStatus?: number;
    // Второй проход получает другой файл: имитация CDN, сменившего байты.
    secondPassServed?: Served;
  },
  run: (origin: string, uploads: Upload[]) => Promise<void>,
): Promise<void> {
  const uploads: Upload[] = [];
  let videoHits = 0;
  const server = Deno.serve(
    { hostname: "127.0.0.1", port: 0, onListen: () => {} },
    async (request) => {
      const url = new URL(request.url);
      if (url.pathname === "/video") {
        videoHits += 1;
        const source = videoHits >= 2 && options.secondPassServed
          ? options.secondPassServed
          : served;
        const headers: Record<string, string> = {
          "content-type": options.videoContentType ?? "video/mp4",
        };
        if (options.declareLength !== false) {
          headers["content-length"] = String(source.totalBytes);
        }
        return new Response(source.stream(), {
          status: options.videoStatus ?? 200,
          headers,
        });
      }
      if (
        request.method === "POST" &&
        url.pathname.startsWith("/storage/v1/object/")
      ) {
        const hasher = createHash("sha256");
        let size = 0;
        for await (const chunk of request.body ?? new ReadableStream()) {
          hasher.update(chunk);
          size += chunk.byteLength;
        }
        uploads.push({
          path: url.pathname,
          headers: request.headers,
          size,
          sha256: hasher.digest("hex"),
        });
        return new Response(JSON.stringify({ Key: url.pathname }), {
          status: options.uploadStatus ?? 200,
          headers: { "content-type": "application/json" },
        });
      }
      return new Response("not found", { status: 404 });
    },
  );
  const origin = `http://127.0.0.1:${server.addr.port}`;
  try {
    await run(origin, uploads);
  } finally {
    await server.shutdown();
  }
}

const MIME = new Set(["video/mp4", "application/mp4", "application/octet-stream"]);

function archiveArgs(origin: string, overrides: Record<string, unknown> = {}) {
  return {
    url: `${origin}/video`,
    timeoutMs: 60_000,
    maximumBytes: 52_428_800,
    allowedMimeTypes: MIME,
    sniff: isMp4,
    storage: {
      supabaseUrl: origin,
      serviceRoleKey: "service-role-test-key",
      bucket: "contentengine-private",
    },
    objectName: "org/actor/generated/strategy/job-1.mp4",
    contentType: "video/mp4",
    ...overrides,
  };
}

Deno.test("large output streams to storage without buffering the file", async () => {
  // 48 МБ — близко к потолку MAX_OUTPUT_BYTES и в четыре раза больше ролика,
  // на котором функция падала в проде.
  const served = makeServedVideo(48 * 1024 * 1024, 256 * 1024);
  await withTestServer(served, {}, async (origin, uploads) => {
    const before = Deno.memoryUsage().rss;
    const result = await archiveProviderOutputStream(archiveArgs(origin));
    const after = Deno.memoryUsage().rss;
    if (!result.ok) throw new Error(`archive failed: ${result.code}`);
    if (result.size_bytes !== served.totalBytes) {
      throw new Error(`size ${result.size_bytes} != ${served.totalBytes}`);
    }
    if (result.sha256 !== served.sha256) throw new Error("sha256 mismatch");
    if (uploads.length !== 1) throw new Error(`uploads ${uploads.length}`);
    const upload = uploads[0];
    if (upload.size !== served.totalBytes || upload.sha256 !== served.sha256) {
      throw new Error("storage received different bytes");
    }
    if (
      upload.path !==
        "/storage/v1/object/contentengine-private/org/actor/generated/strategy/job-1.mp4"
    ) throw new Error(`unexpected path ${upload.path}`);
    if (upload.headers.get("x-upsert") !== "true") throw new Error("x-upsert");
    if (upload.headers.get("content-type") !== "video/mp4") {
      throw new Error("content-type");
    }
    if (upload.headers.get("authorization") !== "Bearer service-role-test-key") {
      throw new Error("authorization");
    }
    if (upload.headers.get("apikey") !== "service-role-test-key") {
      throw new Error("apikey");
    }
    const metadata = JSON.parse(atob(upload.headers.get("x-metadata") ?? ""));
    if (metadata.sha256 !== served.sha256) throw new Error("x-metadata sha256");
    // Память: сам сервер и клиент живут в одном процессе, поэтому допуск
    // щедрый — но он всё равно втрое меньше размера файла. Буферизация
    // целиком (как раньше: части + склейка + тело загрузки) дала бы рост
    // на 2–3 размера файла, то есть 100–150 МБ.
    const growth = after - before;
    const limit = 16 * 1024 * 1024;
    if (growth > limit) {
      throw new Error(
        `rss grew by ${Math.round(growth / 1024 / 1024)} MB for a ` +
          `${Math.round(served.totalBytes / 1024 / 1024)} MB file`,
      );
    }
  });
});

Deno.test("oversized output is refused before storage", async () => {
  const served = makeServedVideo(3 * 1024 * 1024, 64 * 1024);
  await withTestServer(served, { declareLength: false }, async (origin, uploads) => {
    const result = await archiveProviderOutputStream(
      archiveArgs(origin, { maximumBytes: 2 * 1024 * 1024 }),
    );
    if (result.ok || result.code !== "output_validation_failed") {
      throw new Error(`expected validation failure, got ${JSON.stringify(result)}`);
    }
    if (uploads.length !== 0) throw new Error("storage must not be touched");
  });
});

Deno.test("declared oversized content-length is refused without reading", async () => {
  const served = makeServedVideo(3 * 1024 * 1024, 64 * 1024);
  await withTestServer(served, {}, async (origin, uploads) => {
    const result = await archiveProviderOutputStream(
      archiveArgs(origin, { maximumBytes: 1024 }),
    );
    if (result.ok || result.code !== "output_validation_failed") {
      throw new Error(`expected validation failure, got ${JSON.stringify(result)}`);
    }
    if (uploads.length !== 0) throw new Error("storage must not be touched");
  });
});

Deno.test("non-mp4 bytes are refused by the sniff", async () => {
  const served = makeServedVideo(1024 * 1024, 64 * 1024);
  await withTestServer(served, {}, async (origin, uploads) => {
    const result = await archiveProviderOutputStream(
      archiveArgs(origin, { sniff: () => false }),
    );
    if (result.ok || result.code !== "output_validation_failed") {
      throw new Error(`expected validation failure, got ${JSON.stringify(result)}`);
    }
    if (uploads.length !== 0) throw new Error("storage must not be touched");
  });
});

Deno.test("wrong content-type is refused", async () => {
  const served = makeServedVideo(1024 * 1024, 64 * 1024);
  await withTestServer(
    served,
    { videoContentType: "text/html" },
    async (origin, uploads) => {
      const result = await archiveProviderOutputStream(archiveArgs(origin));
      if (result.ok || result.code !== "output_validation_failed") {
        throw new Error(`expected validation failure, got ${JSON.stringify(result)}`);
      }
      if (uploads.length !== 0) throw new Error("storage must not be touched");
    },
  );
});

Deno.test("provider refusal is a download failure", async () => {
  const served = makeServedVideo(1024 * 1024, 64 * 1024);
  await withTestServer(served, { videoStatus: 404 }, async (origin, uploads) => {
    const result = await archiveProviderOutputStream(archiveArgs(origin));
    if (result.ok || result.code !== "output_download_failed") {
      throw new Error(`expected download failure, got ${JSON.stringify(result)}`);
    }
    if (uploads.length !== 0) throw new Error("storage must not be touched");
  });
});

Deno.test("storage refusal is an upload failure", async () => {
  const served = makeServedVideo(1024 * 1024, 64 * 1024);
  await withTestServer(served, { uploadStatus: 403 }, async (origin) => {
    const result = await archiveProviderOutputStream(archiveArgs(origin));
    if (result.ok || result.code !== "output_upload_failed") {
      throw new Error(`expected upload failure, got ${JSON.stringify(result)}`);
    }
  });
});

Deno.test("bytes changing between passes are not accepted as the result", async () => {
  const served = makeServedVideo(1024 * 1024, 64 * 1024);
  const other = makeServedVideo(1024 * 1024, 32 * 1024);
  if (served.sha256 === other.sha256) throw new Error("fixture collision");
  await withTestServer(served, { secondPassServed: other }, async (origin) => {
    const result = await archiveProviderOutputStream(archiveArgs(origin));
    if (result.ok || result.code !== "output_download_failed") {
      throw new Error(`expected download failure, got ${JSON.stringify(result)}`);
    }
  });
});

Deno.test("missing storage target is an upload failure before any request", async () => {
  const served = makeServedVideo(64 * 1024, 16 * 1024);
  await withTestServer(served, {}, async (origin, uploads) => {
    const result = await archiveProviderOutputStream(
      archiveArgs(origin, {
        storage: { supabaseUrl: "", serviceRoleKey: "", bucket: "" },
      }),
    );
    if (result.ok || result.code !== "output_upload_failed") {
      throw new Error(`expected upload failure, got ${JSON.stringify(result)}`);
    }
    if (uploads.length !== 0) throw new Error("storage must not be touched");
  });
});

Deno.test("meter hashes like a one-shot digest and sniffs the head", async () => {
  const served = makeServedVideo(300 * 1024, 7 * 1024 + 13);
  const failure = { code: null as null | string };
  const seen: Uint8Array[] = [];
  const meter = providerOutputMeter(
    1024 * 1024,
    (head) => {
      seen.push(head);
      return isMp4(head);
    },
    failure as { code: null },
  );
  await served.stream().pipeThrough(meter.stream).pipeTo(
    new WritableStream<Uint8Array>(),
  );
  const finished = meter.finish();
  if (finished.size !== served.totalBytes) throw new Error("meter size");
  if (finished.sha256 !== served.sha256) throw new Error("meter sha256");
  if (seen.length !== 1 || seen[0].byteLength !== PROVIDER_OUTPUT_SNIFF_BYTES) {
    throw new Error("sniff must run once on the first 32 bytes");
  }
  if (failure.code !== null) throw new Error("unexpected failure code");
});
