from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "web" / "app" / "generation-strategy-intake-v4.js"


def _run_node(source: str) -> dict[str, object]:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI regressions"
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_media_kind_mime_guard_rejects_cross_kind_files_before_runtime() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        subject = Path(temporary_directory) / "subject.mjs"
        shutil.copyfile(INTAKE, subject)
        payload = _run_node(
            f"""
class File {{
  constructor(name, type) {{
    this.name = name;
    this.type = type;
    this.size = 64;
  }}
}}
globalThis.File = File;
globalThis.CSS = {{ escape(value) {{ return String(value); }} }};
let runtimeCalls = 0;
globalThis.window = {{
  location: {{ hash: "#/outside" }},
  addEventListener() {{}},
  ContentEngineWorkspaceRuntime: {{
    getApi() {{
      runtimeCalls += 1;
      return {{
        uploadPrivateObject() {{ throw new Error("upload_must_not_start"); }},
        registerMedia() {{ throw new Error("register_must_not_start"); }},
      }};
    }},
  }},
}};
globalThis.document = {{
  documentElement: {{}},
  querySelector() {{ return null; }},
  querySelectorAll() {{ return []; }},
}};
globalThis.MutationObserver = class {{ observe() {{}} }};

const subject = await import({json.dumps(subject.as_uri())});
const imageKinds = ["product_photo", "packshot", "creator_reference"];
const imageMimes = ["image/jpeg", "image/png", "image/webp"];
const accepted = [];
for (const kind of imageKinds) {{
  for (const mime of imageMimes) {{
    accepted.push(subject.assertMediaKindMime(new File("shoe.webp", mime), kind));
  }}
}}
accepted.push(subject.assertMediaKindMime(
  new File("source.mp4", "video/mp4"),
  "source_video",
));

const rejected = [];
for (const [file, kind] of [
  [new File("boots.mp4", "video/mp4"), "product_photo"],
  [new File("grill.webp", "image/webp"), "source_video"],
]) {{
  try {{
    subject.assertMediaKindMime(file, kind);
  }} catch (error) {{
    rejected.push({{
      code: error.message,
      filename: error.filename,
      expectedClass: error.expectedClass,
      message: subject.mediaKindMimeMismatchMessage(error),
    }});
  }}
  try {{
    await subject.uploadProjectMedia(file, kind);
  }} catch (error) {{
    if (error.message !== "media_kind_mime_mismatch") throw error;
  }}
}}

console.log(JSON.stringify({{ accepted, rejected, runtimeCalls }}));
"""
        )

    assert payload["accepted"] == [True] * 10
    assert payload["runtimeCalls"] == 0
    assert payload["rejected"] == [
        {
            "code": "media_kind_mime_mismatch",
            "filename": "boots.mp4",
            "expectedClass": "изображение JPG, PNG или WEBP",
            "message": (
                "«boots.mp4» не принят: ожидалось изображение JPG, PNG или WEBP, "
                "получено video/mp4. Файл не загружен и не зарегистрирован."
            ),
        },
        {
            "code": "media_kind_mime_mismatch",
            "filename": "grill.webp",
            "expectedClass": "видео MP4",
            "message": (
                "«grill.webp» не принят: ожидалось видео MP4, получено image/webp. "
                "Файл не загружен и не зарегистрирован."
            ),
        },
    ]


def test_compact_inputs_and_upload_helpers_share_the_fail_closed_contract() -> None:
    source = INTAKE.read_text(encoding="utf-8")
    upload = source.split("async function uploadProjectMedia", 1)[1].split(
        "function panelFor", 1
    )[0]
    register = source.split("async function registerUploadedMedia", 1)[1].split(
        "async function registerCopyOriginalFrame", 1
    )[0]

    assert 'input.accept = "video/mp4,.mp4"' in source
    assert (
        'input.accept = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp"'
        in source
    )
    assert upload.index("assertMediaKindMime(file, kind)") < upload.index(
        "apiRuntime()"
    )
    assert upload.index("assertMediaKindMime(file, kind)") < upload.index(
        "uploadPrivateObject"
    )
    assert upload.index("assertMediaKindMime(file, kind)") < upload.index(
        "registerUploadedMedia"
    )
    assert register.index("assertMediaKindMime(file, kind)") < register.index(
        "api.registerMedia"
    )
    assert "mediaKindMimeMismatchMessage(imageError, file.name)" in source
    assert source.count('error?.message === "media_kind_mime_mismatch"') >= 4
    assert "media_kind_mime_mismatch: mediaKindMimeMismatchMessage" in source
