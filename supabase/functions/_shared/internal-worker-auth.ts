export const INTERNAL_WORKER_HEADER = "x-contentengine-internal-worker";
export const INTERNAL_WORKER_SECRET_HEADER = "x-contentengine-worker-secret";

function hasControlCharacter(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code <= 0x1f || code === 0x7f) return true;
  }
  return false;
}

function isBoundedSecret(value: string): boolean {
  return value.length >= 32 && value.length <= 512 &&
    value === value.trim() && !hasControlCharacter(value);
}

async function timingSafeEqual(left: string, right: string): Promise<boolean> {
  const ephemeralKey = crypto.getRandomValues(new Uint8Array(32));
  const key = await crypto.subtle.importKey(
    "raw",
    ephemeralKey,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const encoder = new TextEncoder();
  const [leftSignature, rightSignature] = await Promise.all([
    crypto.subtle.sign("HMAC", key, encoder.encode(left)),
    crypto.subtle.sign("HMAC", key, encoder.encode(right)),
  ]);
  const leftBytes = new Uint8Array(leftSignature);
  const rightBytes = new Uint8Array(rightSignature);
  if (leftBytes.byteLength !== rightBytes.byteLength) return false;
  let difference = 0;
  for (let index = 0; index < leftBytes.byteLength; index += 1) {
    difference |= leftBytes[index] ^ rightBytes[index];
  }
  return difference === 0;
}

export function isInternalWorkerRequest(request: Request): boolean {
  return request.headers.get(INTERNAL_WORKER_HEADER) === "1";
}

export async function isInternalWorkerAuthorized(
  request: Request,
): Promise<boolean> {
  if (
    request.headers.get("origin") !== null ||
    !isInternalWorkerRequest(request)
  ) return false;
  const expected = Deno.env.get("CONTENTENGINE_WORKER_SECRET") ?? "";
  const provided = request.headers.get(INTERNAL_WORKER_SECRET_HEADER) ?? "";
  if (!isBoundedSecret(expected) || !isBoundedSecret(provided)) return false;
  return await timingSafeEqual(expected, provided);
}
