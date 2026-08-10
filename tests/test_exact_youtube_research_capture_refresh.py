from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app" / "app.js"
CAPTURE = ROOT / "web" / "app" / "exact-youtube-research-capture.js"
API = ROOT / "web" / "app" / "supabase-api.js"
VIEW = ROOT / "web" / "app" / "content-review-view.js"


def run_node(script: str) -> object:
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def submit_flow() -> str:
    app = APP.read_text(encoding="utf-8")
    start = app.index("async function submitExactYoutubeResearchEvidence(form)")
    end = app.index("async function submitContentReview(form)", start)
    return app[start:end]


def test_capture_media_resolver_rejects_every_identity_or_size_mismatch() -> None:
    script = f"""
import {{ resolveExactYoutubeResearchCaptureMedia }} from {json.dumps(CAPTURE.as_uri())};

const projectId = "11111111-1111-4111-8111-111111111111";
const mediaId = "22222222-2222-4222-8222-222222222222";
const sha256 = "a".repeat(64);
const objectName = "33333333-3333-4333-8333-333333333333/"
  + "44444444-4444-4444-8444-444444444444/media/source.mp4";
const cached = {{
  id: mediaId,
  status: "ready",
  kind: "source_video",
  mimeType: "video/mp4",
  sha256,
  objectName,
  sizeBytes: 33_619_696,
  url: "https://storage.example.test/stale-token",
  isVideo: true,
}};
const freshSource = {{ media: {{
  id: mediaId,
  project_id: projectId,
  status: "ready",
  kind: "source_video",
  mime_type: "video/mp4",
  artifact_class: "source",
  lifecycle_stage: "sources",
  sha256,
  object_key: objectName,
  size_bytes: 33_619_696,
}} }};
const resolve = (cachedPatch = {{}}, freshPatch = {{}}, scopePatch = {{}}) => (
  resolveExactYoutubeResearchCaptureMedia(
    {{ ...cached, ...cachedPatch }},
    {{ media: {{ ...freshSource.media, ...freshPatch }} }},
    {{ projectId, mediaId, ...scopePatch }},
  )
);
const exact = resolve();
const failures = [
  resolve({{ id: "55555555-5555-4555-8555-555555555555" }}),
  resolve({{ sha256: "b".repeat(64) }}),
  resolve({{ objectName: `${{objectName}}.other` }}),
  resolve({{ sizeBytes: 33_619_695 }}),
  resolve({{}}, {{ id: "55555555-5555-4555-8555-555555555555" }}),
  resolve({{}}, {{ project_id: "55555555-5555-4555-8555-555555555555" }}),
  resolve({{}}, {{ size_bytes: 0 }}),
  resolve({{}}, {{ size_bytes: 33_619_695 }}),
  resolve({{}}, {{ status: "uploading" }}),
  resolve({{}}, {{ mime_type: "video/webm" }}),
  resolve({{}}, {{}}, {{ mediaId: "55555555-5555-4555-8555-555555555555" }}),
];
console.log(JSON.stringify({{
  exact: {{
    ok: exact.ok,
    code: exact.code,
    id: exact.media?.id,
    projectId: exact.media?.projectId,
    objectName: exact.media?.objectName,
    sizeBytes: exact.media?.sizeBytes,
    url: exact.media?.url,
  }},
  failures: failures.map((item) => ({{ ok: item.ok, code: item.code, media: item.media }})),
}}));
"""
    assert run_node(script) == {
        "exact": {
            "ok": True,
            "code": "ok",
            "id": "22222222-2222-4222-8222-222222222222",
            "projectId": "11111111-1111-4111-8111-111111111111",
            "objectName": (
                "33333333-3333-4333-8333-333333333333/"
                "44444444-4444-4444-8444-444444444444/media/source.mp4"
            ),
            "sizeBytes": 33_619_696,
            "url": "",
        },
        "failures": [
            {
                "ok": False,
                "code": "exact_youtube_research_capture_media_mismatch",
                "media": None,
            }
        ]
        * 11,
    }


def test_failure_recovery_truth_table_is_executable_and_cost_honest() -> None:
    script = f"""
import {{ exactYoutubeResearchFailureRecovery }} from {json.dumps(CAPTURE.as_uri())};

const rows = {{
  none: exactYoutubeResearchFailureRecovery(null),
  invalid: exactYoutubeResearchFailureRecovery({{ status: "expired" }}),
  pending: exactYoutubeResearchFailureRecovery({{ status: "commit_pending" }}),
  ready: exactYoutubeResearchFailureRecovery({{ status: "ready" }}),
  pendingAfterDispatch: exactYoutubeResearchFailureRecovery(
    {{ status: "commit_pending" }},
    {{ paidDispatchStarted: true }},
  ),
  readyAfterDispatch: exactYoutubeResearchFailureRecovery(
    {{ status: "ready" }},
    {{ paidDispatchStarted: true }},
  ),
}};
const view = Object.fromEntries(Object.entries(rows).map(([key, value]) => [key, {{
  status: value.status,
  unsaved: value.message.includes("Кадры не сохранены"),
  uploaded: value.message.includes("Кадры загружены"),
  confirmed: value.message.includes("Пять кадров уже подтверждены"),
  unpaid: value.message.includes("Платный анализ не начат"),
  ambiguous: value.message.includes("Статус платного анализа не подтверждён"),
  sameCommit: value.message.includes("тот же серверный commit"),
  noNewRead: value.message.includes("без нового чтения MP4"),
}}]));
console.log(JSON.stringify(view));
"""
    assert run_node(script) == {
        "none": {
            "status": "none",
            "unsaved": True,
            "uploaded": False,
            "confirmed": False,
            "unpaid": True,
            "ambiguous": False,
            "sameCommit": False,
            "noNewRead": False,
        },
        "invalid": {
            "status": "none",
            "unsaved": True,
            "uploaded": False,
            "confirmed": False,
            "unpaid": True,
            "ambiguous": False,
            "sameCommit": False,
            "noNewRead": False,
        },
        "pending": {
            "status": "commit_pending",
            "unsaved": False,
            "uploaded": True,
            "confirmed": False,
            "unpaid": True,
            "ambiguous": False,
            "sameCommit": True,
            "noNewRead": False,
        },
        "ready": {
            "status": "ready",
            "unsaved": False,
            "uploaded": False,
            "confirmed": True,
            "unpaid": True,
            "ambiguous": False,
            "sameCommit": False,
            "noNewRead": True,
        },
        "pendingAfterDispatch": {
            "status": "commit_pending",
            "unsaved": False,
            "uploaded": True,
            "confirmed": False,
            "unpaid": False,
            "ambiguous": True,
            "sameCommit": True,
            "noNewRead": False,
        },
        "readyAfterDispatch": {
            "status": "ready",
            "unsaved": False,
            "uploaded": False,
            "confirmed": True,
            "unpaid": False,
            "ambiguous": True,
            "sameCommit": False,
            "noNewRead": True,
        },
    }


def test_private_download_blob_is_verified_by_exact_size_sha_and_rewrapped_as_mp4() -> None:
    script = f"""
import {{ webcrypto }} from "node:crypto";
import {{ verifyExactYoutubeResearchCaptureBlob }} from {json.dumps(CAPTURE.as_uri())};

const bytes = new TextEncoder().encode("private MILIO source mp4 bytes");
const sha = Array.from(
  new Uint8Array(await webcrypto.subtle.digest("SHA-256", bytes)),
  (byte) => byte.toString(16).padStart(2, "0"),
).join("");
const media = {{ mimeType: "video/mp4", sizeBytes: bytes.byteLength, sha256: sha }};
const verified = await verifyExactYoutubeResearchCaptureBlob(
  media,
  new Blob([bytes], {{ type: "application/octet-stream" }}),
  {{ subtle: webcrypto.subtle }},
);
const wrongSize = await verifyExactYoutubeResearchCaptureBlob(
  media,
  new Blob([bytes, new Uint8Array([0])]),
  {{ subtle: webcrypto.subtle }},
);
const wrongHash = await verifyExactYoutubeResearchCaptureBlob(
  {{ ...media, sha256: "0".repeat(64) }},
  new Blob([bytes]),
  {{ subtle: webcrypto.subtle }},
);
const oversized = await verifyExactYoutubeResearchCaptureBlob(
  {{ ...media, sizeBytes: 52_428_801 }},
  new Blob([bytes]),
  {{ subtle: webcrypto.subtle }},
);
console.log(JSON.stringify({{
  verified: {{
    ok: verified.ok,
    code: verified.code,
    size: verified.blob?.size,
    type: verified.blob?.type,
    sizeBytes: verified.sizeBytes,
    sha256: verified.sha256,
  }},
  wrongSize: {{ ok: wrongSize.ok, code: wrongSize.code }},
  wrongHash: {{ ok: wrongHash.ok, code: wrongHash.code }},
  oversized: {{ ok: oversized.ok, code: oversized.code }},
}}));
"""
    result = run_node(script)
    assert result["verified"] == {
        "ok": True,
        "code": "ok",
        "size": len("private MILIO source mp4 bytes".encode()),
        "type": "video/mp4",
        "sizeBytes": len("private MILIO source mp4 bytes".encode()),
        "sha256": result["verified"]["sha256"],
    }
    assert len(result["verified"]["sha256"]) == 64
    assert result["wrongSize"] == {
        "ok": False,
        "code": "exact_youtube_capture_blob_size_mismatch",
    }
    assert result["wrongHash"] == {
        "ok": False,
        "code": "exact_youtube_capture_blob_hash_mismatch",
    }
    assert result["oversized"] == {
        "ok": False,
        "code": "exact_youtube_capture_blob_context_invalid",
    }


def test_private_video_helper_orders_download_then_verified_local_capture() -> None:
    app = APP.read_text(encoding="utf-8")
    start = app.index("async function captureVerifiedPrivateVideoEvidence(")
    end = app.index("async function resolveGeneratedVideoReviewMedia(", start)
    helper = app[start:end]
    download = helper.index("state.api.downloadPrivateObject(objectName)")
    verified_capture = helper.index("captureVerifiedPrivateVideoBlob(", download)
    capture = helper.index("captureContentReviewEvidence(localMedia", verified_capture)
    assert download < verified_capture < capture
    assert "signedPrivateObjectUrls" not in helper

    module = CAPTURE.read_text(encoding="utf-8")
    lifecycle_start = module.index("export async function captureVerifiedPrivateVideoBlob(")
    lifecycle_end = module.index("export function resolveExactYoutubeResearchCaptureMedia(", lifecycle_start)
    lifecycle = module[lifecycle_start:lifecycle_end]
    verify = lifecycle.index("verifyExactYoutubeResearchCaptureBlob(")
    object_url = lifecycle.index("createObjectURL(verified.blob)", verify)
    local_capture = lifecycle.index("await capture({ ...media, url: objectUrl })", object_url)
    revoke = lifecycle.index("revokeObjectURL(objectUrl)", local_capture)
    assert verify < object_url < local_capture < revoke
    assert "finally" in lifecycle[local_capture:revoke]


def test_verified_video_object_url_is_revoked_on_success_and_capture_failure() -> None:
    script = f"""
import {{ webcrypto }} from "node:crypto";
import {{ captureVerifiedPrivateVideoBlob }} from {json.dumps(CAPTURE.as_uri())};

const bytes = new TextEncoder().encode("verified private video");
const sha256 = Array.from(
  new Uint8Array(await webcrypto.subtle.digest("SHA-256", bytes)),
  (byte) => byte.toString(16).padStart(2, "0"),
).join("");
const media = {{
  id: "media-1",
  mimeType: "video/mp4",
  sizeBytes: bytes.byteLength,
  sha256,
}};
const revoked = [];
let createdTypes = [];
const deps = {{
  subtle: webcrypto.subtle,
  createObjectURL: (blob) => {{
    createdTypes.push(blob.type);
    return `blob:verified-${{createdTypes.length}}`;
  }},
  revokeObjectURL: (url) => revoked.push(url),
}};
const success = await captureVerifiedPrivateVideoBlob(
  media,
  new Blob([bytes], {{ type: "application/octet-stream" }}),
  async (localMedia) => ({{ url: localMedia.url, frames: 5 }}),
  deps,
);
let failure = "";
try {{
  await captureVerifiedPrivateVideoBlob(
    media,
    new Blob([bytes]),
    async () => {{ throw new Error("capture_failed"); }},
    deps,
  );
}} catch (error) {{
  failure = error.message;
}}
console.log(JSON.stringify({{
  success: {{ ok: success.ok, evidence: success.evidence }},
  createdTypes,
  revoked,
  failure,
}}));
"""
    result = run_node(script)
    assert result == {
        "success": {
            "ok": True,
            "evidence": {"url": "blob:verified-1", "frames": 5},
        },
        "createdTypes": ["video/mp4", "video/mp4"],
        "revoked": ["blob:verified-1", "blob:verified-2"],
        "failure": "capture_failed",
    }


def test_exact_submit_orders_fresh_identity_capture_persist_then_paid_start() -> None:
    flow = submit_flow()
    fresh = flow.index("const freshSource = await requireFreshExactYoutubeResearchSource")
    resolve = flow.index("resolveExactYoutubeResearchCaptureMedia(", fresh)
    read = flow.index("readExactYoutubeResearchEvidence(context, verifiedVideo)", resolve)
    capture = flow.index("captureVerifiedPrivateVideoEvidence(", read)
    persist = flow.index("persistContentReviewVideoEvidence(", capture)
    paid_flag = flow.index("paidDispatchStarted = true", persist)
    paid_start = flow.index("state.api.startProductResearch(", paid_flag)

    assert fresh < resolve < read < capture < persist < paid_flag < paid_start
    assert "const freshObjectKey = verifiedVideo.objectName" in flow[read:capture]
    assert "{ ...verifiedVideo, objectName: freshObjectKey }" in flow[capture:persist]
    assert "captureVideo,\n        capturedEvidence" in flow[persist:paid_flag]
    assert "signedPrivateObjectUrls" not in flow[read:persist]


def test_all_private_video_capture_callsites_use_verified_download_helper() -> None:
    app = APP.read_text(encoding="utf-8")
    generated = app[
        app.index("async function prepareGeneratedVideoTechnicalQa") :
        app.index("function resumeGeneratedVideoTechnicalQa")
    ]
    review = app[
        app.index("async function submitContentReview(form)") :
        app.index("async function submitContentReviewDecision(")
    ]
    exact = submit_flow()
    assert "captureVerifiedPrivateVideoEvidence(" in generated
    assert "captureVerifiedPrivateVideoEvidence(" in exact
    assert "media.isVideo\n        ? await captureVerifiedPrivateVideoEvidence(media)" in review
    assert "captureContentReviewEvidence(media)" in review
    assert "media.isVideo\n        ? await captureContentReviewEvidence(media)" not in review


def test_private_download_uses_authenticated_readable_object_scope() -> None:
    api = API.read_text(encoding="utf-8")
    start = api.index("async downloadPrivateObject(objectKey)")
    end = api.index("async removePrivateObjects(objectKeys)", start)
    method = api[start:end]
    assert method.index("this.assertReadableObjectKey(objectKey)") < method.index(
        ".download(objectKey)"
    )
    assert ".from(this.storageBucket)" in method
    assert "this.assertPrivateObjectKey(objectKey)" not in method
    assert 'typeof data.arrayBuffer !== "function"' in method


def test_ready_and_commit_pending_evidence_bypass_download_and_capture() -> None:
    flow = submit_flow()
    reuse_start = flow.index("let capturedEvidence = durableEvidence")
    persist_gate = flow.index('if (durableEvidence?.status !== "ready")', reuse_start)
    reuse = flow[reuse_start:persist_gate]

    assert "durableEvidence\n      ? { frames: [], technical_metrics: durableEvidence.technicalMetrics }" in reuse
    capture_gate = reuse.index("if (!capturedEvidence)")
    assert reuse.index("captureVerifiedPrivateVideoEvidence(") > capture_gate

    persist_start = flow.index("persistContentReviewVideoEvidence(", persist_gate)
    assert "existingEvidence: durableEvidence" in flow[persist_start:]

    app = APP.read_text(encoding="utf-8")
    helper_start = app.index("async function persistContentReviewVideoEvidence(")
    helper_end = app.index("async function submitContentReviewImageBatch(", helper_start)
    helper = app[helper_start:helper_end]
    ready = helper.index('if (existing?.status === "ready") return existing')
    pending = helper.index('if (existing?.status === "commit_pending")', ready)
    materialize = helper.index("const frameFiles = await buildContentReviewFrameFiles", pending)
    pending_branch = helper[pending:materialize]
    assert ready < pending < materialize
    assert "commitContentReviewEvidence" in pending_branch
    assert "uploadPrivateObject" not in pending_branch
    assert "captureContentReviewEvidence" not in pending_branch
    assert "downloadPrivateObject" not in pending_branch


def test_paid_dispatch_cannot_start_before_server_ready_evidence() -> None:
    flow = submit_flow()
    ready_gate = flow.index('if (!durableEvidence || durableEvidence.status !== "ready")')
    ready_failure = flow.index('code: "exact_video_research_evidence_not_ready"', ready_gate)
    paid_flag = flow.index("paidDispatchStarted = true", ready_failure)
    paid_start = flow.index("state.api.startProductResearch(", paid_flag)
    assert ready_gate < ready_failure < paid_flag < paid_start
    assert "startProductResearch" not in flow[:paid_flag]


def test_video_metadata_listeners_are_installed_before_src_and_explicit_load() -> None:
    view = VIEW.read_text(encoding="utf-8")
    start = view.index("function loadVideoMetadata(video, url")
    end = view.index("function drawSource(", start)
    loader = view[start:end]
    loaded_listener = loader.index('video.addEventListener("loadedmetadata", onSuccess')
    error_listener = loader.index('video.addEventListener("error", onError')
    src = loader.index("video.src = url")
    load = loader.index("video.load()", src)
    ready_fast_path = loader.index("if (video.readyState >= 1)", load)
    assert loaded_listener < src
    assert error_listener < src
    assert src < load < ready_fast_path
    assert "video.error?.code" in loader
    assert "video.networkState" in loader
    assert "video.readyState" in loader


def test_video_metadata_loader_handles_sync_success_error_and_timeout() -> None:
    view = VIEW.read_text(encoding="utf-8")
    start = view.index("function loadVideoMetadata(video, url")
    end = view.index("function drawSource(", start)
    loader = view[start:end]
    script = f"""
const window = {{
  setTimeout,
  clearTimeout,
  queueMicrotask,
}};
const userError = (message) => new Error(message);
{loader}

class FakeVideo {{
  constructor(mode) {{
    this.mode = mode;
    this.listeners = new Map();
    this.loads = 0;
    this.readyState = 0;
    this.networkState = 0;
    this.error = null;
  }}
  addEventListener(name, callback) {{ this.listeners.set(name, callback); }}
  removeEventListener(name, callback) {{
    if (this.listeners.get(name) === callback) this.listeners.delete(name);
  }}
  set src(value) {{
    this.source = value;
    if (this.mode === "success") {{
      this.readyState = 1;
      this.listeners.get("loadedmetadata")?.();
    }} else if (this.mode === "error") {{
      this.error = {{ code: 4 }};
      this.networkState = 3;
      this.listeners.get("error")?.();
    }}
  }}
  load() {{ this.loads += 1; }}
}}

const success = new FakeVideo("success");
await loadVideoMetadata(success, "blob:sync-success", 20);
const failed = new FakeVideo("error");
let errorMessage = "";
try {{ await loadVideoMetadata(failed, "blob:secret-token", 20); }}
catch (error) {{ errorMessage = error.message; }}
const timedOut = new FakeVideo("timeout");
let timeoutMessage = "";
try {{ await loadVideoMetadata(timedOut, "blob:timeout", 1); }}
catch (error) {{ timeoutMessage = error.message; }}
console.log(JSON.stringify({{
  successLoads: success.loads,
  errorLoads: failed.loads,
  timeoutLoads: timedOut.loads,
  errorMessage,
  timeoutMessage,
}}));
"""
    result = run_node(script)
    assert result["successLoads"] == 1
    assert result["errorLoads"] == 1
    assert result["timeoutLoads"] == 1
    assert "media=4" in result["errorMessage"]
    assert "network=3" in result["errorMessage"]
    assert "ready=0" in result["errorMessage"]
    assert "secret-token" not in result["errorMessage"]
    assert "15" in result["timeoutMessage"]
    assert result["timeoutMessage"] != result["errorMessage"]


def test_normalize_media_is_idempotent_for_camel_case_capture_fields() -> None:
    view = VIEW.read_text(encoding="utf-8")
    start = view.index("function normalizeMedia(raw)")
    end = view.index("function normalizeScores(raw)", start)
    normalize_source = view[start:end]
    script = f"""
const objectFrom = (value) => value && typeof value === "object" ? value : null;
const text = (value, max) => String(value ?? "").slice(0, max);
const safeMediaUrl = (value) => String(value ?? "");
const nonNegativeInteger = (value) => Number.isInteger(Number(value)) && Number(value) >= 0
  ? Number(value)
  : 0;
{normalize_source}
const first = normalizeMedia({{
  id: "media-1",
  productId: "product-1",
  originalFilename: "MILIO source.mp4",
  mimeType: "video/mp4",
  kind: "source_video",
  url: "blob:verified-private-mp4",
  objectName: "org/project/media/source.mp4",
  sizeBytes: 33619696,
  generationModel: "seedance_v2_fast",
  audioExpected: true,
  spokenScript: "Точный текст",
}});
const second = normalizeMedia(first);
console.log(JSON.stringify({{ first, second }}));
"""
    result = run_node(script)
    for normalized in (result["first"], result["second"]):
        assert normalized["id"] == "media-1"
        assert normalized["productId"] == "product-1"
        assert normalized["name"] == "MILIO source.mp4"
        assert normalized["mimeType"] == "video/mp4"
        assert normalized["isVideo"] is True
        assert normalized["url"] == "blob:verified-private-mp4"
        assert normalized["objectName"] == "org/project/media/source.mp4"
        assert normalized["sizeBytes"] == 33_619_696
        assert normalized["generationModel"] == "seedance_v2_fast"
        assert normalized["audioExpected"] is True
        assert normalized["spokenScript"] == "Точный текст"
    assert result["second"] == result["first"]


def test_failure_copy_is_truthful_and_paid_flag_is_set_once_immediately_before_dispatch() -> None:
    app = APP.read_text(encoding="utf-8")
    flow = submit_flow()
    old_false_copy = "Подтверждённые кадры сохранены для безопасного повтора."
    assert old_false_copy not in app
    assert "exactYoutubeResearchFailureRecovery(" in flow
    assert "${recovery.message}" in flow

    assert flow.count("paidDispatchStarted = true") == 1
    paid_flag = flow.index("paidDispatchStarted = true")
    paid_start = flow.index("const raw = await state.api.startProductResearch(", paid_flag)
    between = flow[paid_flag:paid_start]
    assert between.strip() == "paidDispatchStarted = true;"
    assert flow.index("exact_video_evidence_id: durableEvidence.evidenceId", paid_start) > paid_start
