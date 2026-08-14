/*
 * Strict, full-buffer ISO Base Media File Format duration parser.
 *
 * The caller is responsible for resolving an authorized private media object,
 * downloading it without redirects, checking its Content-Type/Content-Length,
 * and matching the complete object SHA-256 before trusting this evidence. This
 * module is deliberately pure: it has no network, storage, database, browser,
 * credential, or provider access.
 *
 * Accepted files have one unambiguous movie header only:
 * - the first top-level box is a structurally valid `ftyp`;
 * - there is exactly one top-level `moov`;
 * - `moov` contains exactly one direct `mvhd` version 0 or 1;
 * - fragmented media (`moof` or `moov/mvex`) is rejected;
 * - zero-sized, truncated, overflowing, duplicate, or unknown-duration boxes
 *   are rejected instead of being guessed around.
 */

export const ISO_BMFF_DURATION_PARSER_VERSION = "iso-bmff-mvhd-v1";
export const ISO_BMFF_MAX_BYTES = 32 * 1024 * 1024;

const MAX_SAFE_BIGINT = BigInt(Number.MAX_SAFE_INTEGER);
const MAX_DURATION_MILLISECONDS = 60 * 60 * 1_000;

export class IsoBmffDurationError extends Error {
  constructor(code) {
    super(`iso_bmff_duration:${code}`);
    this.name = "IsoBmffDurationError";
    this.code = code;
  }
}

function fail(code) {
  throw new IsoBmffDurationError(code);
}

function exactBytes(value) {
  let bytes;
  if (value instanceof Uint8Array) {
    bytes = new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  } else if (value instanceof ArrayBuffer) {
    bytes = new Uint8Array(value);
  } else {
    fail("input_invalid");
  }
  if (bytes.byteLength < 8) fail("input_too_small");
  if (bytes.byteLength > ISO_BMFF_MAX_BYTES) fail("input_too_large");
  return bytes;
}

function readUint32(bytes, offset, end, code = "box_header_truncated") {
  if (!Number.isSafeInteger(offset) || offset < 0 || offset + 4 > end) {
    fail(code);
  }
  return new DataView(
    bytes.buffer,
    bytes.byteOffset + offset,
    4,
  ).getUint32(0, false);
}

function readUint64(bytes, offset, end, code = "box_header_truncated") {
  const high = readUint32(bytes, offset, end, code);
  const low = readUint32(bytes, offset + 4, end, code);
  return (BigInt(high) << 32n) | BigInt(low);
}

function readFourCc(bytes, offset, end, code = "box_type_invalid") {
  if (!Number.isSafeInteger(offset) || offset < 0 || offset + 4 > end) {
    fail(code);
  }
  let value = "";
  for (let index = 0; index < 4; index += 1) {
    const unit = bytes[offset + index];
    if (unit < 0x20 || unit > 0x7e) fail(code);
    value += String.fromCharCode(unit);
  }
  return value;
}

function readBoxes(bytes, start, end) {
  if (
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(end) ||
    start < 0 ||
    end < start ||
    end > bytes.byteLength
  ) fail("box_bounds_invalid");

  const boxes = [];
  let offset = start;
  while (offset < end) {
    if (end - offset < 8) fail("box_header_truncated");
    const size32 = readUint32(bytes, offset, end);
    const type = readFourCc(bytes, offset + 4, end);
    let headerSize = 8;
    let size;

    if (size32 === 0) {
      fail("box_size_ambiguous");
    } else if (size32 === 1) {
      if (end - offset < 16) fail("box_header_truncated");
      headerSize = 16;
      const size64 = readUint64(bytes, offset + 8, end);
      if (size64 > MAX_SAFE_BIGINT) fail("box_size_overflow");
      size = Number(size64);
    } else {
      size = size32;
    }

    if (!Number.isSafeInteger(size) || size < headerSize) {
      fail("box_size_invalid");
    }
    if (size > end - offset) fail("box_truncated");
    const boxEnd = offset + size;
    if (!Number.isSafeInteger(boxEnd) || boxEnd <= offset) {
      fail("box_size_overflow");
    }
    boxes.push(Object.freeze({
      type,
      start: offset,
      payloadStart: offset + headerSize,
      end: boxEnd,
      payloadLength: size - headerSize,
    }));
    offset = boxEnd;
  }
  if (offset !== end) fail("box_bounds_invalid");
  return boxes;
}

function validateFileType(bytes, box) {
  if (box.payloadLength < 8 || (box.payloadLength - 8) % 4 !== 0) {
    fail("ftyp_invalid");
  }
  readFourCc(bytes, box.payloadStart, box.end, "ftyp_invalid");
  for (
    let offset = box.payloadStart + 8;
    offset < box.end;
    offset += 4
  ) {
    readFourCc(bytes, offset, box.end, "ftyp_invalid");
  }
}

function parseMovieHeader(bytes, box) {
  if (box.payloadLength < 4) fail("mvhd_truncated");
  const version = bytes[box.payloadStart];
  const flags = (bytes[box.payloadStart + 1] << 16) |
    (bytes[box.payloadStart + 2] << 8) |
    bytes[box.payloadStart + 3];
  if (flags !== 0) fail("mvhd_flags_invalid");

  let timescale;
  let durationUnits;
  if (version === 0) {
    if (box.payloadLength !== 100) fail("mvhd_size_invalid");
    timescale = readUint32(
      bytes,
      box.payloadStart + 12,
      box.end,
      "mvhd_truncated",
    );
    const duration = readUint32(
      bytes,
      box.payloadStart + 16,
      box.end,
      "mvhd_truncated",
    );
    if (duration === 0xffffffff) fail("mvhd_duration_unknown");
    durationUnits = BigInt(duration);
  } else if (version === 1) {
    if (box.payloadLength !== 112) fail("mvhd_size_invalid");
    timescale = readUint32(
      bytes,
      box.payloadStart + 20,
      box.end,
      "mvhd_truncated",
    );
    durationUnits = readUint64(
      bytes,
      box.payloadStart + 24,
      box.end,
      "mvhd_truncated",
    );
    if (durationUnits === 0xffffffffffffffffn) {
      fail("mvhd_duration_unknown");
    }
  } else {
    fail("mvhd_version_invalid");
  }

  if (timescale === 0) fail("mvhd_timescale_zero");
  if (durationUnits === 0n) fail("mvhd_duration_zero");
  if (durationUnits > MAX_SAFE_BIGINT) fail("mvhd_duration_overflow");

  const timescaleBig = BigInt(timescale);
  const durationMillisecondsBig = (durationUnits * 1_000n + timescaleBig / 2n) /
    timescaleBig;
  if (
    durationMillisecondsBig === 0n ||
    durationMillisecondsBig > BigInt(MAX_DURATION_MILLISECONDS)
  ) fail("mvhd_duration_out_of_range");

  const durationMilliseconds = Number(durationMillisecondsBig);
  return {
    timescale,
    durationUnits: Number(durationUnits),
    durationMilliseconds,
  };
}

export function parseIsoBmffDuration(value) {
  const bytes = exactBytes(value);
  const topLevel = readBoxes(bytes, 0, bytes.byteLength);
  if (topLevel.length === 0 || topLevel[0].type !== "ftyp") {
    fail("ftyp_not_first");
  }
  const fileTypes = topLevel.filter((box) => box.type === "ftyp");
  if (fileTypes.length !== 1) fail("ftyp_count_invalid");
  validateFileType(bytes, fileTypes[0]);
  if (topLevel.some((box) => box.type === "moof")) {
    fail("fragmented_not_supported");
  }

  const movies = topLevel.filter((box) => box.type === "moov");
  if (movies.length !== 1) fail("moov_count_invalid");
  const movieChildren = readBoxes(bytes, movies[0].payloadStart, movies[0].end);
  if (movieChildren.some((box) => box.type === "mvex")) {
    fail("fragmented_not_supported");
  }
  const movieHeaders = movieChildren.filter((box) => box.type === "mvhd");
  if (movieHeaders.length !== 1) fail("mvhd_count_invalid");

  const parsed = parseMovieHeader(bytes, movieHeaders[0]);
  const durationSeconds = parsed.durationMilliseconds / 1_000;
  return Object.freeze({
    parser_version: ISO_BMFF_DURATION_PARSER_VERSION,
    timescale: parsed.timescale,
    duration_units: parsed.durationUnits,
    duration_ms: parsed.durationMilliseconds,
    duration_seconds: durationSeconds,
    mvhd_count: 1,
    fragmented: false,
  });
}
