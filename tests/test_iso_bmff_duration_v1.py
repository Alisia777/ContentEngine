from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
PARSER_MODULE = ROOT / "supabase/functions/_shared/iso-bmff-duration.js"
PARSER_SOURCE = PARSER_MODULE.read_text(encoding="utf-8")


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for ISO-BMFF duration contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        (directory / "iso-bmff-duration.js").write_text(
            PARSER_SOURCE, encoding="utf-8"
        )
        (directory / "contract.js").write_text(
            "import * as subject from './iso-bmff-duration.js';\n"
            "const attempt = (callback) => {\n"
            "  try { return {ok:true,value:callback()}; }\n"
            "  catch (error) { return {ok:false,code:error?.code || '',message:error?.message || ''}; }\n"
            "};\n"
            "const u32 = (value) => Uint8Array.of(\n"
            "  (value >>> 24) & 255, (value >>> 16) & 255,\n"
            "  (value >>> 8) & 255, value & 255\n"
            ");\n"
            "const u64 = (value) => {\n"
            "  const exact = BigInt(value);\n"
            "  return Uint8Array.of(\n"
            "    Number((exact >> 56n) & 255n), Number((exact >> 48n) & 255n),\n"
            "    Number((exact >> 40n) & 255n), Number((exact >> 32n) & 255n),\n"
            "    Number((exact >> 24n) & 255n), Number((exact >> 16n) & 255n),\n"
            "    Number((exact >> 8n) & 255n), Number(exact & 255n)\n"
            "  );\n"
            "};\n"
            "const fourcc = (value) => Uint8Array.from([...value].map((unit) => unit.charCodeAt(0)));\n"
            "const concat = (...parts) => {\n"
            "  const output = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));\n"
            "  let offset = 0;\n"
            "  for (const part of parts) { output.set(part, offset); offset += part.length; }\n"
            "  return output;\n"
            "};\n"
            "const box = (type, payload = new Uint8Array(), extended = false) => extended\n"
            "  ? concat(u32(1), fourcc(type), u64(BigInt(payload.length + 16)), payload)\n"
            "  : concat(u32(payload.length + 8), fourcc(type), payload);\n"
            "const ftyp = () => box('ftyp', concat(fourcc('isom'), u32(512), fourcc('isom'), fourcc('mp42')));\n"
            "const mvhd = ({version = 0, timescale = 1000, duration = 8000n, flags = 0, extra = 0} = {}) => {\n"
            "  const payload = new Uint8Array((version === 0 ? 100 : 112) + extra);\n"
            "  payload[0] = version; payload[1] = (flags >>> 16) & 255;\n"
            "  payload[2] = (flags >>> 8) & 255; payload[3] = flags & 255;\n"
            "  const offset = version === 0 ? 12 : 20;\n"
            "  payload.set(u32(timescale), offset);\n"
            "  payload.set(version === 0 ? u32(Number(duration)) : u64(duration), offset + 4);\n"
            "  return box('mvhd', payload);\n"
            "};\n"
            "const file = (...children) => concat(ftyp(), box('free'), box('moov', concat(...children)), box('mdat'));\n"
            f"const result = {expression};\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_parser_is_pure_inert_and_has_a_narrow_api() -> None:
    for forbidden in (
        "Deno.env",
        "process.env",
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "document.",
        "window.",
        "WebSocket",
        "crypto.subtle",
        "Authorization",
        "Bearer ",
    ):
        assert forbidden not in PARSER_SOURCE

    result = _evaluate(
        """
        (() => ({
          exports: Object.keys(subject).sort(),
          version: subject.ISO_BMFF_DURATION_PARSER_VERSION,
          maxBytes: subject.ISO_BMFF_MAX_BYTES,
        }))()
        """
    )
    assert result == {
        "exports": [
            "ISO_BMFF_DURATION_PARSER_VERSION",
            "ISO_BMFF_MAX_BYTES",
            "IsoBmffDurationError",
            "parseIsoBmffDuration",
        ],
        "version": "iso-bmff-mvhd-v1",
        "maxBytes": 33_554_432,
    }


def test_parser_reads_exact_v0_and_v1_movie_header_evidence() -> None:
    result = _evaluate(
        """
        (() => {
          const v0 = subject.parseIsoBmffDuration(file(mvhd({
            version:0, timescale:30000, duration:299970n,
          })));
          const v1Bytes = file(mvhd({
            version:1, timescale:90000, duration:1350045n,
          }));
          const padded = new Uint8Array(v1Bytes.length + 9);
          padded.set(v1Bytes, 4);
          const v1 = subject.parseIsoBmffDuration(padded.subarray(4, 4 + v1Bytes.length));
          return {
            v0,
            v1,
            frozen: Object.isFrozen(v0) && Object.isFrozen(v1),
          };
        })()
        """
    )
    assert result == {
        "v0": {
            "parser_version": "iso-bmff-mvhd-v1",
            "timescale": 30_000,
            "duration_units": 299_970,
            "duration_ms": 9_999,
            "duration_seconds": 9.999,
            "mvhd_count": 1,
            "fragmented": False,
        },
        "v1": {
            "parser_version": "iso-bmff-mvhd-v1",
            "timescale": 90_000,
            "duration_units": 1_350_045,
            "duration_ms": 15_001,
            "duration_seconds": 15.001,
            "mvhd_count": 1,
            "fragmented": False,
        },
        "frozen": True,
    }


def test_parser_accepts_bounded_extended_size_boxes_without_number_loss() -> None:
    result = _evaluate(
        """
        (() => {
          const movie = box('moov', mvhd({
            version:1, timescale:48000, duration:86400n,
          }), true);
          return subject.parseIsoBmffDuration(concat(ftyp(), movie, box('mdat')));
        })()
        """
    )
    assert result["timescale"] == 48_000
    assert result["duration_units"] == 86_400
    assert result["duration_ms"] == 1_800
    assert result["duration_seconds"] == 1.8


def test_parser_rejects_ambiguous_container_and_fragmented_media() -> None:
    result = _evaluate(
        """
        (() => {
          const validMvhd = mvhd();
          const validMoov = box('moov', validMvhd);
          const zeroSized = concat(u32(0), fourcc('mdat'));
          return {
            ftypMissing: attempt(() => subject.parseIsoBmffDuration(concat(validMoov, box('mdat')))),
            ftypDuplicate: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), ftyp(), validMoov))),
            ftypMalformed: attempt(() => subject.parseIsoBmffDuration(concat(box('ftyp', fourcc('isom')), validMoov))),
            moovMissing: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), box('mdat')))),
            moovDuplicate: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), validMoov, validMoov))),
            mvhdMissing: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), box('moov', box('trak'))))),
            mvhdDuplicate: attempt(() => subject.parseIsoBmffDuration(file(validMvhd, validMvhd))),
            moof: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), validMoov, box('moof')))),
            mvex: attempt(() => subject.parseIsoBmffDuration(file(validMvhd, box('mvex')))),
            zeroSized: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), validMoov, zeroSized))),
          };
        })()
        """
    )
    assert {key: value["code"] for key, value in result.items()} == {
        "ftypMissing": "ftyp_not_first",
        "ftypDuplicate": "ftyp_count_invalid",
        "ftypMalformed": "ftyp_invalid",
        "moovMissing": "moov_count_invalid",
        "moovDuplicate": "moov_count_invalid",
        "mvhdMissing": "mvhd_count_invalid",
        "mvhdDuplicate": "mvhd_count_invalid",
        "moof": "fragmented_not_supported",
        "mvex": "fragmented_not_supported",
        "zeroSized": "box_size_ambiguous",
    }
    assert all(value["ok"] is False for value in result.values())


def test_parser_rejects_untrusted_mvhd_values_and_noncanonical_sizes() -> None:
    result = _evaluate(
        """
        (() => ({
          version: attempt(() => subject.parseIsoBmffDuration(file(mvhd({version:2})))),
          flags: attempt(() => subject.parseIsoBmffDuration(file(mvhd({flags:1})))),
          size: attempt(() => subject.parseIsoBmffDuration(file(mvhd({extra:4})))),
          timescaleZero: attempt(() => subject.parseIsoBmffDuration(file(mvhd({timescale:0})))),
          durationZero: attempt(() => subject.parseIsoBmffDuration(file(mvhd({duration:0n})))),
          unknownV0: attempt(() => subject.parseIsoBmffDuration(file(mvhd({duration:0xffffffffn})))),
          unknownV1: attempt(() => subject.parseIsoBmffDuration(file(mvhd({
            version:1,duration:0xffffffffffffffffn,
          })))),
          unsafeV1: attempt(() => subject.parseIsoBmffDuration(file(mvhd({
            version:1,duration:9007199254740992n,
          })))),
          overHour: attempt(() => subject.parseIsoBmffDuration(file(mvhd({
            version:1,timescale:1000,duration:3600001n,
          })))),
        }))()
        """
    )
    assert {key: value["code"] for key, value in result.items()} == {
        "version": "mvhd_version_invalid",
        "flags": "mvhd_flags_invalid",
        "size": "mvhd_size_invalid",
        "timescaleZero": "mvhd_timescale_zero",
        "durationZero": "mvhd_duration_zero",
        "unknownV0": "mvhd_duration_unknown",
        "unknownV1": "mvhd_duration_unknown",
        "unsafeV1": "mvhd_duration_overflow",
        "overHour": "mvhd_duration_out_of_range",
    }


def test_parser_rejects_truncation_overflow_invalid_input_and_oversize() -> None:
    result = _evaluate(
        """
        (() => {
          const valid = file(mvhd());
          const hugeHeader = concat(u32(1), fourcc('free'), u64(9007199254740992n));
          const shortExtended = concat(u32(1), fourcc('free'), u32(16));
          const truncatedBody = concat(
            ftyp(), box('moov', mvhd()), u32(16), fourcc('mdat'), new Uint8Array(4)
          );
          const tooLarge = new Uint8Array(subject.ISO_BMFF_MAX_BYTES + 1);
          return {
            invalid: attempt(() => subject.parseIsoBmffDuration('not bytes')),
            tiny: attempt(() => subject.parseIsoBmffDuration(new Uint8Array(7))),
            tooLarge: attempt(() => subject.parseIsoBmffDuration(tooLarge)),
            headerTail: attempt(() => subject.parseIsoBmffDuration(concat(valid, Uint8Array.of(1)))),
            truncatedBox: attempt(() => subject.parseIsoBmffDuration(truncatedBody)),
            extendedHeader: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), box('moov', mvhd()), shortExtended))),
            sizeOverflow: attempt(() => subject.parseIsoBmffDuration(concat(ftyp(), box('moov', mvhd()), hugeHeader))),
          };
        })()
        """
    )
    assert {key: value["code"] for key, value in result.items()} == {
        "invalid": "input_invalid",
        "tiny": "input_too_small",
        "tooLarge": "input_too_large",
        "headerTail": "box_header_truncated",
        "truncatedBox": "box_truncated",
        "extendedHeader": "box_header_truncated",
        "sizeOverflow": "box_size_overflow",
    }
