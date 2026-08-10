from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app" / "app.js"
CAPTURE = ROOT / "web" / "app" / "exact-youtube-research-capture.js"


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


def test_exact_submit_orders_fresh_identity_resign_capture_persist_then_paid_start() -> None:
    flow = submit_flow()
    fresh = flow.index("const freshSource = await requireFreshExactYoutubeResearchSource")
    resolve = flow.index("resolveExactYoutubeResearchCaptureMedia(", fresh)
    read = flow.index("readExactYoutubeResearchEvidence(context, verifiedVideo)", resolve)
    resign = flow.index("state.api.signedPrivateObjectUrls([freshObjectKey], 600)", read)
    trust = flow.index("isTrustedGenerationDownload(freshSignedUrl)", resign)
    capture = flow.index("captureContentReviewEvidence(captureVideo)", trust)
    persist = flow.index("persistContentReviewVideoEvidence(", capture)
    paid_flag = flow.index("paidDispatchStarted = true", persist)
    paid_start = flow.index("state.api.startProductResearch(", paid_flag)

    assert fresh < resolve < read < resign < trust < capture < persist < paid_flag < paid_start
    assert "const freshObjectKey = verifiedVideo.objectName" in flow[read:resign]
    assert "captureVideo = { ...verifiedVideo, url: freshSignedUrl }" in flow[trust:capture]
    assert "captureVideo,\n        capturedEvidence" in flow[persist:paid_flag]


def test_ready_and_commit_pending_evidence_bypass_resign_and_capture() -> None:
    flow = submit_flow()
    reuse_start = flow.index("let capturedEvidence = durableEvidence")
    persist_gate = flow.index('if (durableEvidence?.status !== "ready")', reuse_start)
    reuse = flow[reuse_start:persist_gate]

    assert "durableEvidence\n      ? { frames: [], technical_metrics: durableEvidence.technicalMetrics }" in reuse
    capture_gate = reuse.index("if (!capturedEvidence)")
    assert reuse.index("state.api.signedPrivateObjectUrls(") > capture_gate
    assert reuse.index("captureContentReviewEvidence(captureVideo)") > capture_gate

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
    assert "signedPrivateObjectUrls" not in pending_branch


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
