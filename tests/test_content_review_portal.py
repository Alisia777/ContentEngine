import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
APP = (APP_DIR / "app.js").read_text(encoding="utf-8")
API = (APP_DIR / "supabase-api.js").read_text(encoding="utf-8")
VIEW = (APP_DIR / "content-review-view.js").read_text(encoding="utf-8")
STYLES = (APP_DIR / "content-review.css").read_text(encoding="utf-8")
CATALOG = (APP_DIR / "catalog.js").read_text(encoding="utf-8")
INDEX = (APP_DIR / "index.html").read_text(encoding="utf-8")


def test_review_is_a_first_class_versioned_workspace_stage() -> None:
    assert '["review", "Проверка контента", "◈"]' in CATALOG
    flow = APP[APP.index("const FACTORY_FLOW") : APP.index("const HOME_SECTION_KEYS")]
    assert re.search(r'key:\s*"review",\s*step:\s*"03"', flow)
    assert "Шаг 3 из 5" in APP
    assert '<ol style="--workflow-step-count:${FACTORY_FLOW.length}">' in APP
    assert "review: renderContentReviewSection" in APP
    assert 'section === "review"' in APP
    assert 'state.api.contentReviewCatalog({ limit: 50, projectId })' in APP
    assert './content-review-view.js?v=20260812.os4.36' in APP
    assert './content-review.css?v=20260812.os4.36' in INDEX
    assert './app.js?v=20260812.os4.36' in INDEX
    assert "20260716.1" not in INDEX
    assert "20260716.1" not in "\n".join(
        line for line in APP.splitlines() if line.startswith("import ")
    )


def test_review_form_covers_context_rights_advertising_and_disclosures() -> None:
    direct_fields = (
        "media_id",
        "platform",
        "content_kind",
        "product_category",
        "caption_text",
        "script_text",
        "advertiser_name",
        "erid",
        "people_present",
    )
    checkbox_fields = (
        "rights_confirmed",
        "claims_verified",
        "ad_label_confirmed",
        "ord_confirmed",
        "audience_over_10000",
        "rkn_registered",
        "person_consent_confirmed",
        "external_ai_processing_confirmed",
        "ai_generated",
        "ai_disclosure_confirmed",
        "captions_confirmed",
        "mandatory_warning_confirmed",
    )
    for field in direct_fields:
        assert f'name="{field}"' in VIEW
        assert field in API
    for field in checkbox_fields:
        assert f'checkMarkup("{field}"' in VIEW
        assert field in API
    for category in (
        "cosmetics",
        "baa",
        "sports_food",
        "food",
        "household",
        "apparel",
        "electronics",
        "other",
    ):
        assert category in VIEW
        assert category in API
    assert "syncContentReviewFormVisibility" in VIEW
    assert "[data-review-advertising]" in VIEW
    assert "[data-review-baa]" in VIEW
    assert "[data-review-person-consent]" in VIEW
    assert "[data-review-ai-disclosure]" in VIEW
    assert "[data-review-rkn]" in VIEW


def test_review_accepts_up_to_five_photos_of_one_product_and_queues_each_file() -> None:
    assert 'type="checkbox" name="media_id"' in VIEW
    assert "MAX_CONTENT_REVIEW_IMAGE_SELECTION = 5" in VIEW
    assert "До 5 фото одного товара" in VIEW
    assert "data-content-review-media-count" in VIEW
    assert "resolveContentReviewMediaSelection" in VIEW
    assert "content_review_product_mismatch" in VIEW
    assert "content_review_video_single_only" in VIEW
    assert "async function submitContentReviewImageBatch" in APP
    assert "for (let index = 0; index < mediaItems.length; index += 1)" in APP
    assert "batch_size: mediaItems.length" in APP
    assert "batch_position: index + 1" in APP
    assert "Запущено ${started.length} независимых проверок фото одного товара" in APP
    assert "contentReviewIsBusy(review.phase, null)" in APP
    assert "contentReviewIsBusy(phase, null)" in VIEW


def test_multi_photo_selection_rejects_mixed_products_video_and_oversized_batches() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
import {{ resolveContentReviewMediaSelection }} from {json.dumps(module_url)};
const media = [
  ...Array.from({{ length: 6 }}, (_, index) => ({{
    id: `photo-${{index + 1}}`,
    productId: "product-a",
    isImage: true,
    isVideo: false,
    supported: true,
  }})),
  {{ id: "other", productId: "product-b", isImage: true, isVideo: false, supported: true }},
  {{ id: "video", productId: "product-a", isImage: false, isVideo: true, supported: true }},
];
const valid = resolveContentReviewMediaSelection(media, ["photo-1", "photo-2", "photo-3"]);
if (!valid.ok || valid.items.length !== 3) throw new Error("valid same-product batch rejected");
const mixed = resolveContentReviewMediaSelection(media, ["photo-1", "other"]);
if (mixed.ok || mixed.code !== "content_review_product_mismatch") throw new Error("mixed product accepted");
const video = resolveContentReviewMediaSelection(media, ["photo-1", "video"]);
if (video.ok || video.code !== "content_review_video_single_only") throw new Error("mixed video accepted");
const oversized = resolveContentReviewMediaSelection(
  media,
  ["photo-1", "photo-2", "photo-3", "photo-4", "photo-5", "photo-6"],
);
if (oversized.ok || oversized.code !== "content_review_media_limit") throw new Error("oversized batch accepted");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_browser_persists_bounded_frames_and_metrics_but_never_sends_raw_video() -> None:
    for marker in (
        "MAX_FRAME_CHARACTERS = 330_000",
        "MAX_TOTAL_FRAME_CHARACTERS = 1_650_000",
        "sampleTimes(duration)",
        "four_control_frames_plus_timeline_atlas_v1",
        "adjacent_frame_difference",
        "black_frame_ratio",
        "frozen_frame_ratio",
        "frozen_frame_suspected",
        "raw_video_sent: false",
        "audio_analysis_status",
        "audio_silence_ratio",
        "audio_clipping_ratio",
        'canvas.toDataURL("image/jpeg", quality)',
    ):
        assert marker in VIEW
    assert "buildContentReviewFrameFiles" in VIEW
    assert "jpegDataUriToBlob" in VIEW
    assert 'crypto.subtle.digest("SHA-256"' in VIEW
    assert "normalizedFrameCount !== 5" in API
    assert 'prepareContentReviewEvidence: "creator_prepare_content_review_evidence"' in API
    assert 'commitContentReviewEvidence: "creator_commit_content_review_evidence"' in API
    generated_start = API.index("async startGeneratedVideoReview(")
    start = API[API.index("async startContentReview(") : generated_start]
    generated = API[generated_start : API.index("contentReviewStatus(")]
    dispatch_pattern = re.compile(
        r"invokeContentReview\(\{\s*action: \"analyze\",\s*"
        r"review_id: reviewId,\s*project_id: normalizedProjectId,\s*\}\)"
    )
    for flow in (start, generated):
        assert dispatch_pattern.search(flow)
    assert "frames:" not in start
    assert "evidence_id: evidenceId" in start
    assert "raw_video_sent: false" in APP
    assert "0.2," in VIEW
    assert "1," in VIEW
    assert "2," in VIEW
    assert "differences.filter((value) => value < 0.015).length / differences.length" in VIEW
    assert "Исходный MP4 передаётся в OpenAI Transcriptions только" in VIEW
    assert 'speech_transcription_notice_version: "openai_mp4_v1"' in VIEW
    assert "readResponseArrayBufferBounded" in VIEW
    assert "decodeAudioData" in VIEW
    assert "input_audio" not in VIEW
    assert 'new Blob([bytes], { type: "image/jpeg" })' in VIEW


def test_durable_video_review_orders_upload_commit_and_run_fail_closed() -> None:
    flow = APP[
        APP.index("async function persistContentReviewVideoEvidence") :
        APP.index("async function submitContentReview(")
    ]
    assert flow.index("buildContentReviewFrameFiles") < flow.index("prepareContentReviewEvidence")
    assert flow.index("prepareContentReviewEvidence") < flow.index("uploadPrivateObject")
    assert flow.index("uploadPrivateObject") < flow.index("commitStarted = true")
    commit_started_at = flow.index("commitStarted = true")
    assert commit_started_at < flow.index("commitContentReviewEvidence", commit_started_at)
    assert "if (!commitStarted && uploadedObjectNames.length)" in flow
    assert "removePrivateObjects(uploadedObjectNames)" in flow
    assert "committed/ambiguous evidence is left for server reconciliation/sweeping" in flow

    submit = APP[
        APP.index("async function submitContentReview(") :
        APP.index("async function submitContentReviewDecision(")
    ]
    assert "evidence_id: durableEvidence.evidenceId" in submit
    assert "frames: evidence.frames" not in submit
    assert "clearContentReviewDraft();" in submit
    assert "вкладку можно закрыть" in submit


def test_ambiguous_evidence_commit_reuses_exact_manifest_and_key_without_reupload() -> None:
    flow = APP[
        APP.index("async function persistContentReviewVideoEvidence") :
        APP.index("async function submitContentReview(")
    ]
    retry_branch = flow[
        flow.index('if (existing?.status === "commit_pending")') :
        flow.index("const frameFiles = await buildContentReviewFrameFiles")
    ]
    assert "uploadPrivateObject" not in retry_branch
    assert "frames: existing.frames" in retry_branch
    assert "technicalMetrics: existing.technicalMetrics" in retry_branch
    assert "idempotencyKey: existing.commitIdempotencyKey" in retry_branch
    assert retry_branch.index("await state.api.commitContentReviewEvidence") < retry_branch.index("return promoteReady(existing)")

    assert 'status: "commit_pending"' in flow
    assert "commitIdempotencyKey: crypto.randomUUID()" in flow
    assert "frames: frameFiles.map" in flow
    assert flow.index("persistEvidence(pending)") < flow.index("commitStarted = true")
    assert "idempotencyKey: pending.commitIdempotencyKey" in flow
    assert 'status: "ready"' in flow
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 10" in APP
    assert "GENERATED_VIDEO_QA_STORAGE_VERSION = 6" in APP
    assert "upsert: false" in API


def test_content_review_draft_and_progress_are_recoverable_and_accessible() -> None:
    for marker in (
        "contentReviewDraftStorageKey",
        "persistContentReviewDraft",
        "restoreContentReviewDraft",
        "clearContentReviewDraft",
        "CONTENT_REVIEW_DRAFT_MAX_AGE_MS",
        "state.contentReview.durableEvidence",
    ):
        assert marker in APP
    assert "organizationId}:${userId}" in APP
    assert 'data-content-review-draft-status role="status" aria-live="polite"' in VIEW
    assert 'aria-busy="${busy ? "true" : "false"}"' in VIEW
    assert 'phase === "saving_evidence"' in VIEW
    assert 'phase === "queueing"' in VIEW
    assert "Сохраняем evidence" in VIEW
    assert "Проверка в фоновой очереди" in VIEW
    assert "Можно закрыть вкладку" in VIEW


def test_frame_materialization_produces_exact_jpeg_blobs_hashes_and_timecodes() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
import {{ buildContentReviewFrameFiles }} from {json.dumps(module_url)};
const bytes = new Uint8Array(160).fill(127);
const encoded = btoa(String.fromCharCode(...bytes));
const frames = Array.from({{ length: 5 }}, () => `data:image/jpeg;base64,${{encoded}}`);
const files = await buildContentReviewFrameFiles({{
  frames,
  technical_metrics: {{
    source_type: "video",
    sampled_at_seconds: [0.2, 1, 2, 5.76, 7.98]
  }}
}});
if (files.length !== 5) throw new Error("frame count");
for (const file of files) {{
  if (!(file.blob instanceof Blob) || file.blob.type !== "image/jpeg") throw new Error("blob");
  if (!/^[0-9a-f]{{64}}$/.test(file.sha256)) throw new Error("sha256");
  if (file.sizeBytes !== 160) throw new Error("size");
}}
if (files[4].timecodeSeconds !== 7.98) throw new Error("timecode");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_api_uses_evidence_rpcs_and_edge_dispatch_is_non_blocking() -> None:
    module_url = (APP_DIR / "supabase-api.js").resolve().as_uri()
    script = f"""
globalThis.window = {{
  sessionStorage: {{ getItem: () => null, setItem: () => {{}} }}
}};
const {{ CreatorApi }} = await import({json.dumps(module_url)});
const organizationId = "11111111-1111-4111-8111-111111111111";
const userId = "22222222-2222-4222-8222-222222222222";
const mediaId = "33333333-3333-4333-8333-333333333333";
const projectId = "77777777-7777-4777-8777-777777777777";
const evidenceId = "44444444-4444-4444-8444-444444444444";
const reviewId = "55555555-5555-4555-8555-555555555555";
const commitKey = "66666666-6666-4666-8666-666666666666";
const prefix = `${{organizationId}}/${{userId}}/`;
const objectNames = Array.from({{ length: 5 }}, (_, index) => `${{prefix}}review-evidence/${{evidenceId}}/${{index}}.jpg`);
const calls = [];
const rpc = async (name, {{ p_payload }}) => {{
  calls.push([name, p_payload]);
  if (name === "creator_prepare_content_review_evidence") return {{ data: {{
    evidence_id: evidenceId,
    frame_object_names: objectNames,
    expires_at: new Date(Date.now() + 600000).toISOString()
  }}, error: null }};
  if (name === "creator_commit_content_review_evidence") return {{ data: {{ evidence_id: evidenceId, status: "ready" }}, error: null }};
  if (name === "creator_start_content_review") return {{ data: {{ review_id: reviewId, status: "queued" }}, error: null }};
  throw new Error(name);
}};
const invoked = [];
const api = new CreatorApi({{
  schema: () => ({{ rpc }}),
  auth: {{ getSession: async () => ({{ data: {{ session: {{ access_token: "token" }} }}, error: null }}) }},
  functions: {{ invoke: async (_name, options) => {{ invoked.push(options.body); return {{ data: null, error: {{ code: "functions_http_error" }} }}; }} }},
  storage: {{ from: () => ({{ upload: async () => ({{ data: {{}}, error: null }}), remove: async () => ({{ error: null }}) }}) }}
}}, {{ RPC_SCHEMA: "public", STORAGE_BUCKET: "contentengine-private" }});
api.commitBootstrapContext({{
  organization: {{ id: organizationId }},
  storage: {{ bucket: "contentengine-private", path_prefix: prefix }}
}});
const prepared = await api.prepareContentReviewEvidence({{ mediaId, frameCount: 5, projectId }});
if (prepared.evidenceId !== evidenceId || prepared.frameObjectNames.length !== 5) throw new Error("prepare");
await api.commitContentReviewEvidence({{
  evidenceId,
  projectId,
  technicalMetrics: {{
        source_type: "video",
        frame_count: 5,
        duration_seconds: 8,
        sampled_at_seconds: [0.2, 1, 2, 5.76, 7.98],
        speech_transcription_notice_version: "openai_mp4_v1",
        audio_expected: null,
    audio_analyzed: false,
    audio_analysis_status: "unavailable",
    temporal_scan_status: "completed",
    temporal_scan_strategy: "uniform_full_duration_v1",
    temporal_scan_frame_count: 24,
    temporal_scan_first_second: 0.02,
    temporal_scan_last_second: 7.98,
    temporal_scan_coverage_ratio: 0.995,
    temporal_black_frame_ratio: 0,
    temporal_frozen_transition_ratio: 0.1,
    temporal_mean_frame_difference: 0.12,
    timeline_atlas_status: "completed",
    timeline_atlas_version: "dense_full_duration_v1",
    timeline_atlas_frame_ordinal: 5,
    timeline_atlas_frame_count: 24,
    timeline_atlas_first_second: 0.02,
    timeline_atlas_last_second: 7.98,
    timeline_atlas_coverage_ratio: 0.995,
    timeline_atlas_max_gap_seconds: 0.3461,
    timeline_atlas_sample_rate_fps: 3,
    timeline_atlas_columns: 8,
    timeline_atlas_rows: 3,
    timeline_atlas_order: "row_major_chronological",
    timeline_atlas_dense_short_video: true,
    continuity_scan_status: "completed",
    continuity_scan_strategy: "browser_presented_frames_v1",
    continuity_scan_callback_count: 240,
    continuity_scan_presented_frame_count: 240,
    continuity_scan_missed_frame_count: 0,
    continuity_scan_first_second: 0,
    continuity_scan_last_second: 7.9667,
    continuity_scan_coverage_ratio: 0.9958,
    continuity_scan_max_gap_seconds: 0.0334,
    continuity_black_frame_ratio: 0,
    continuity_longest_black_run_seconds: 0,
    continuity_duplicate_transition_ratio: 0.02,
    continuity_longest_duplicate_run_seconds: 0.0667,
    continuity_mean_frame_difference: 0.08,
    continuity_raw_frames_persisted: false
  }},
  idempotencyKey: commitKey,
  frames: objectNames.map((object_name, index) => ({{
    object_name, sha256: "a".repeat(64), size_bytes: 160, timecode_seconds: index
  }}))
}});
const started = await api.startContentReview({{
  media_id: mediaId,
  project_id: projectId,
  platform: "youtube",
  content_kind: "informational",
  product_category: "other",
  people_present: "no",
  technical_metrics: {{
        source_type: "video",
        frame_count: 5,
        duration_seconds: 8,
        sampled_at_seconds: [0.2, 1, 2, 5.76, 7.98],
        speech_transcription_notice_version: "openai_mp4_v1",
        audio_expected: null,
    audio_analyzed: false,
    audio_analysis_status: "unavailable",
    temporal_scan_status: "completed",
    temporal_scan_strategy: "uniform_full_duration_v1",
    temporal_scan_frame_count: 24,
    temporal_scan_first_second: 0.02,
    temporal_scan_last_second: 7.98,
    temporal_scan_coverage_ratio: 0.995,
    temporal_black_frame_ratio: 0,
    temporal_frozen_transition_ratio: 0.1,
    temporal_mean_frame_difference: 0.12,
    timeline_atlas_status: "completed",
    timeline_atlas_version: "dense_full_duration_v1",
    timeline_atlas_frame_ordinal: 5,
    timeline_atlas_frame_count: 24,
    timeline_atlas_first_second: 0.02,
    timeline_atlas_last_second: 7.98,
    timeline_atlas_coverage_ratio: 0.995,
    timeline_atlas_max_gap_seconds: 0.3461,
    timeline_atlas_sample_rate_fps: 3,
    timeline_atlas_columns: 8,
    timeline_atlas_rows: 3,
    timeline_atlas_order: "row_major_chronological",
    timeline_atlas_dense_short_video: true,
    continuity_scan_status: "completed",
    continuity_scan_strategy: "browser_presented_frames_v1",
    continuity_scan_callback_count: 240,
    continuity_scan_presented_frame_count: 240,
    continuity_scan_missed_frame_count: 0,
    continuity_scan_first_second: 0,
    continuity_scan_last_second: 7.9667,
    continuity_scan_coverage_ratio: 0.9958,
    continuity_scan_max_gap_seconds: 0.0334,
    continuity_black_frame_ratio: 0,
    continuity_longest_black_run_seconds: 0,
    continuity_duplicate_transition_ratio: 0.02,
    continuity_longest_duplicate_run_seconds: 0.0667,
    continuity_mean_frame_difference: 0.08,
    continuity_raw_frames_persisted: false
  }},
  evidence_id: evidenceId
}});
await new Promise((resolve) => setTimeout(resolve, 0));
if (started.run.id !== reviewId) throw new Error("run lost");
if (started.analysis_request.status !== "background_queued") throw new Error("dispatch not queued");
if (invoked.length !== 1 || Object.keys(invoked[0]).sort().join(",") !== "action,project_id,review_id") throw new Error(JSON.stringify(invoked));
if (invoked[0].project_id !== projectId) throw new Error("dispatch project scope");
const startPayload = calls.find(([name]) => name === "creator_start_content_review")[1];
if (startPayload.evidence_id !== evidenceId || "frames" in startPayload) throw new Error("start payload");
const commitPayload = calls.find(([name]) => name === "creator_commit_content_review_evidence")[1];
if (commitPayload.technical_metrics?.source_type !== "video") throw new Error("evidence metrics");
if (commitPayload.idempotency_key !== commitKey) throw new Error("evidence commit key");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_quality_compliance_and_recommendations_are_independent_and_escaped() -> None:
    for field in (
        "overall_score",
        "scores",
        "compliance_status",
        "blockers_count",
        "warnings_count",
        "strengths",
        "findings",
        "recommendations",
        "comparison",
    ):
        assert field in VIEW
    assert "contentReviewHasBlockers" in VIEW
    assert "Высокий балл качества не отменяет" in VIEW
    assert "Что улучшить по приоритету" in VIEW
    assert "deduplicateRecommendations" in VIEW
    assert "findingTitles.has(key)" in VIEW
    assert "Сравнение с прошлой проверкой" in VIEW
    assert "escapeHtml(item.title)" in VIEW
    assert "escapeHtml(item.detail)" in VIEW
    assert "escapeHtml(item.action)" in VIEW
    assert ".innerHTML" not in VIEW
    assert "Это фильтр рисков, а не автоматическая юридическая экспертиза" in VIEW


def test_recommendation_list_hides_finding_repeats_and_duplicate_titles() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
import {{ normalizeContentReviewRun }} from {json.dumps(module_url)};
const run = normalizeContentReviewRun({{
  id: "11111111-1111-4111-8111-111111111111",
  status: "completed",
  result: {{
    findings: [
      {{ code: "AD.ERID", title: "Нет идентификатора рекламы", detail: "ERID отсутствует" }}
    ],
    recommendations: [
      {{ code: "FIX.AD.ERID", title: "Нет идентификатора рекламы", detail: "Добавить ERID" }},
      {{ code: "EDIT.HOOK.1", title: "Усилить первые секунды", detail: "Показать результат" }},
      {{ code: "EDIT.HOOK.2", title: "  УСИЛИТЬ   ПЕРВЫЕ СЕКУНДЫ  ", detail: "Дубликат" }}
    ]
  }}
}});
if (run.result.recommendations.length !== 1) throw new Error(JSON.stringify(run.result.recommendations));
if (run.result.recommendations[0].title !== "Усилить первые секунды") throw new Error("wrong recommendation");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_normalized_review_can_be_rendered_again_without_losing_audit_metadata() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
import {{ normalizeContentReviewRun }} from {json.dumps(module_url)};
const first = normalizeContentReviewRun({{
  id: "11111111-1111-4111-8111-111111111111",
  status: "completed",
  created_at: "2026-07-30T13:20:17.936314Z",
  finished_at: "2026-07-30T13:23:21.028155Z",
  ruleset_version: "ru-content-compliance-2026-07-16.1",
  error_message: "safe failure detail"
}});
const second = normalizeContentReviewRun(first);
for (const [key, expected] of Object.entries({{
  createdAt: "2026-07-30T13:20:17.936314Z",
  completedAt: "2026-07-30T13:23:21.028155Z",
  rulesetVersion: "ru-content-compliance-2026-07-16.1",
  failureMessage: "safe failure detail"
}})) {{
  if (second[key] !== expected) throw new Error(`${{key}}=${{second[key]}}`);
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_catalog_envelope_and_immutable_human_decision_match_sql_contract() -> None:
    assert '"recent_reviews"' in VIEW
    assert "source.ruleset?.version" in VIEW
    assert "source.result_summary" in VIEW
    assert "source.finished_at" in VIEW
    assert "metadata.original_filename" in VIEW
    assert "media_limit: normalizedLimit" in API
    assert "run_limit: normalizedLimit" in API
    for field in (
        "comment",
        "resolved_recommendation_codes",
        "risk_acknowledgements",
        "media_watched_confirmed",
    ):
        assert field in API
    assert 'name="media_watched_confirmed"' in VIEW
    assert "Я подтверждаю, что лично просмотрел(а) именно этот защищённый файл до конца" in VIEW
    assert "Кадры ИИ — вспомогательная выборка" in VIEW
    assert "contentReviewHasBlockers(review.record)" in APP
    assert "contentReviewRequiredRiskCodes(review.record)" in APP
    assert "missingRiskCodes.length" in APP
    assert "После сохранения решение нельзя переписать" in VIEW


def test_exact_media_is_refreshed_loaded_and_watched_before_decision() -> None:
    for marker in (
        "singularHolders",
        "root.run",
        "root.review",
        "refreshSignedUrls: true",
        'state.contentReview.phase = "refreshing"',
        "bindContentReviewDecisionMedia()",
        'media.addEventListener("loadedmetadata", onLoadedMetadata)',
        'media.addEventListener("ended", onEnded)',
        "media.dataset.contentReviewLoadedSrc === currentSource",
        "media.dataset.contentReviewEndedSrc === currentSource",
        "contentReviewExactMediaReady(form)",
            "MP4 не загрузился",
            "точное изображение не загрузилось",
    ):
        assert marker in APP
    assert "data-content-review-exact-media" in VIEW
    assert 'data-exact-media-state="${mediaAvailable ? "loading" : "unavailable"}"' in VIEW
    assert "data-review-decision-submit disabled" in VIEW
    assert "Это подтверждение пользователя, а не автоматическое доказательство качества" in VIEW
    assert "state.api.contentReviewStatus(reviewId, { projectId: currentWorkspaceProjectId() })" in APP
    assert "state.api.contentReviewCatalog({ limit: 50, projectId })" in APP
    assert "Content review post-decision refresh failed" in APP


def test_exact_video_has_conservative_platform_safe_zone_preview() -> None:
    for platform in ("instagram", "tiktok", "youtube", "vk"):
        assert f"{platform}: Object.freeze(" in VIEW
        assert 'data-safe-zone-platform="${escapeHtml(normalizedPlatform)}"'
    for marker in (
        "PLATFORM_SAFE_ZONE_GUIDES",
        "platformSafeZoneVideoMarkup(run.input?.platform, exactVideo)",
        "data-content-review-safe-zone-toggle",
        "data-content-review-safe-zone-stage",
        "syncContentReviewSafeZoneStage",
        "media.videoWidth / media.videoHeight",
        "--content-review-exact-video-width",
        "--content-review-exact-video-ratio",
        "Показывать зоны риска интерфейса",
        "консервативный индикатор риска, а не точный шаблон публикации",
        "нативном предпросмотре площадки",
        'rel="noopener noreferrer"',
        ".content-review-safe-zone__overlay",
        ".content-review-safe-zone__frame",
        "[data-content-review-safe-zone-toggle]:not(:checked)",
        '@media (max-width: 560px)',
    ):
        assert marker in VIEW or marker in STYLES
    assert "pointer-events: none" in STYLES
    assert "syncContentReviewSafeZoneStage(media, { clear: true })" in APP
    assert "syncContentReviewSafeZoneStage(media);" in APP
    assert "data-content-review-exact-media" in VIEW
    assert 'media.addEventListener("ended", onEnded)' in APP
    assert 'name="media_watched_confirmed"' in VIEW


def test_generated_video_task_routes_to_content_review_instead_of_generic_acceptance() -> None:
    assert 'String(result.generation_status || "").toLowerCase() === "succeeded"' in APP
    assert "result.output_media_id" in APP
    assert 'data-action="open-generated-content-review"' in APP
    assert "Открыть проверку контента" in APP
    assert "state.contentReview.pendingMediaId = mediaId" in APP
    assert 'navigate(`/workspace/review?project_id=${encodeURIComponent(projectId)}`)' in APP
    for code in (
        "content_review_generation_not_succeeded",
        "content_review_approval_evidence_required",
        "generated_video_review_task_invalid",
        "generated_video_job_invalid",
        "generated_video_placement_input_invalid",
    ):
        assert code in API


def test_baa_is_distinct_from_protein_and_external_ai_processing_is_explicit() -> None:
    assert 'baa: "БАД — зарегистрированный БАД"' in VIEW
    assert 'sports_food: "Протеин и спортивное питание"' in VIEW
    assert 'food: "Еда и напитки"' in VIEW
    assert 'const baa = String(form.elements.product_category?.value || "other") === "baa"' in VIEW
    assert "Для БАД нельзя создавать впечатление" in VIEW
    assert "external_ai_processing_confirmed" in VIEW
    assert "external_ai_processing_confirmed" in API
    assert "input.people_present !== \"no\" && !input.external_ai_processing_confirmed" in APP
    assert 'peoplePresent !== "no" && input?.external_ai_processing_confirmed !== true' in API
    assert 'const peopleMayBePresent = String(form.elements.people_present?.value || "unknown") !== "no"' in VIEW
    assert 'toggleConditional(form, "[data-review-person-consent]", peopleMayBePresent)' in VIEW


def test_generated_paid_video_is_prefilled_as_advertising_before_paid_review() -> None:
    assert 'media.kind === "generated_video"' in APP
    assert "applyGeneratedMediaReviewDefaults" in APP
    assert 'input.content_kind = "advertising"' in APP
    assert "input.ai_generated = true" in APP
    assert "categoryControl.value = media.productCategory" in APP
    assert "platformControl.value = media.platform" in APP
    assert "Готовый платный AI-ролик проверяется только как реклама" not in APP
    assert "Проверка продолжится, но публикация, скорее всего, будет заблокирована" in APP
    assert "external_ai_processing_basis_required" in API


def test_successful_generated_video_prepares_durable_technical_qa_automatically() -> None:
    apply_result = APP[
        APP.index("function applyRealGenerationResult") :
        APP.index("function applyRealGenerationStatusError")
    ]
    assert "scheduleGeneratedVideoTechnicalQa(job" in apply_result
    assert '["succeeded", "completed"].includes(nextStatus)' in apply_result
    assert 'String(job.model || "") !== "seedream5_lite"' in apply_result
    assert "contentReviewUuid(job.output_media_id)" in apply_result

    prepare = APP[
        APP.index("async function prepareGeneratedVideoTechnicalQa") :
        APP.index("function resumeGeneratedVideoTechnicalQa")
    ]
    assert "loadGeneratedVideoQaMedia" in prepare
    assert "captureVerifiedPrivateVideoEvidence" in prepare
    assert "persistContentReviewVideoEvidence" in prepare
    assert "saveGeneratedVideoQaEvidence" in prepare
    assert "startContentReview" not in prepare
    assert "startRealGeneration" not in prepare
    assert "external_ai_processing_confirmed" not in prepare

    loader = APP[
        APP.index("async function loadGeneratedVideoQaMedia") :
        APP.index("async function prepareGeneratedVideoTechnicalQa")
    ]
    assert "state.api.contentReviewCatalog({ limit: 50, projectId: currentWorkspaceProjectId() })" in loader
    assert "refreshSignedUrls: true" in loader
    assert 'media.kind !== "generated_video"' in loader
    assert "/^[0-9a-f]{64}$/u.test(media.sha256)" in loader


def test_generated_video_qa_is_serial_recoverable_and_never_auto_approves() -> None:
    resume = APP[
        APP.index("function resumeGeneratedVideoTechnicalQa") :
        APP.index("function scheduleGeneratedVideoTechnicalQa")
    ]
    assert "state.generatedVideoQa.activePromise" in resume
    assert 'entry.status === "queued"' in resume
    assert 'state.route.path !== "/workspace/generation"' in resume
    assert 'document.visibilityState !== "visible"' in resume

    registry = APP[
        APP.index("function generatedVideoQaStorageKey") :
        APP.index("function setGeneratedVideoQaStatus")
    ]
    assert "organizationId}:${userId}" in registry
    assert "GENERATED_VIDEO_QA_MAX_EVIDENCE" in registry
    assert "usableContentReviewEvidence" in registry
    assert 'status: "consumed"' in registry

    markup = APP[
        APP.index("function generatedVideoTechnicalQaMarkup") :
        APP.index("function generationActionsMarkup")
    ]
    assert "Технический скан готов автоматически" in markup
    assert "Пятое изображение — хронологический атлас" in markup
    assert "Визуальный AI-QA ставится в фоновую очередь автоматически" in markup
    assert "транскрипция остаётся выключенной" in markup
    assert "Автоматическое одобрение отключено" in markup
    assert 'data-action="retry-generated-video-qa"' in markup

    submit = APP[
        APP.index("async function submitContentReview(") :
        APP.index("async function submitContentReviewDecision(")
    ]
    assert "markGeneratedVideoQaEvidenceConsumed(media.id, review.record.id)" in submit
    assert "clearContentReviewDraft();" in submit


def test_content_review_edge_errors_keep_safe_specific_user_guidance() -> None:
    module_url = (APP_DIR / "supabase-api.js").resolve().as_uri()
    script = f"""
import {{ CreatorApi }} from {json.dumps(module_url)};

const base = {{
  schema: () => ({{ rpc: async () => ({{ data: {{}}, error: null }}) }}),
  auth: {{
    getSession: async () => ({{
      data: {{ session: {{ access_token: "test-token" }} }},
      error: null
    }})
  }}
}};
const functionErrorApi = new CreatorApi({{
  ...base,
  functions: {{
    invoke: async () => ({{
      data: null,
      error: {{
        code: "functions_http_error",
        message: "Edge Function returned a non-2xx status code",
        context: new Response(JSON.stringify({{
          error: {{
            code: "external_ai_processing_basis_required",
            message: "SECRET_PROVIDER_STACK"
          }}
        }}), {{ status: 400, headers: {{ "content-type": "application/json" }} }})
      }}
    }})
  }}
}}, {{ RPC_SCHEMA: "public" }});

const responseErrorApi = new CreatorApi({{
  ...base,
  functions: {{
    invoke: async () => ({{
      data: {{
        ok: false,
        error: {{
          code: "external_ai_processing_basis_required",
          message: "SECRET_PROVIDER_STACK"
        }}
      }},
      error: null
    }})
  }}
}}, {{ RPC_SCHEMA: "public" }});

for (const api of [functionErrorApi, responseErrorApi]) {{
  try {{
    await api.invokeContentReview({{ action: "analyze", review_id: "review-1", frames: [] }});
    throw new Error("Expected a content-review error");
  }} catch (error) {{
    if (error.code !== "external_ai_processing_basis_required") throw error;
    if (!error.message.includes("законное основание")) throw new Error(error.message);
    if (error.message.includes("SECRET_PROVIDER_STACK")) throw new Error("Raw provider error leaked");
  }}
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_all_high_and_human_required_risks_are_required_for_approval() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
import {{ contentReviewRequiredRiskCodes }} from {json.dumps(module_url)};
const codes = contentReviewRequiredRiskCodes({{
  result: {{
    complianceStatus: "human_review",
    findings: [
      {{ code: "HIGH.ONE", severity: "high", humanReviewRequired: false }},
      {{ code: "HUMAN.TWO", severity: "medium", humanReviewRequired: true }},
      {{ code: "OPTIONAL.THREE", severity: "medium", humanReviewRequired: false }},
      {{ code: "HIGH.ONE", severity: "high", humanReviewRequired: true }}
    ]
  }}
}});
if (JSON.stringify(codes) !== JSON.stringify(["HIGH.ONE", "HUMAN.TWO"])) throw new Error(JSON.stringify(codes));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert 'data-required-risk="true"' in VIEW


def test_new_media_of_the_same_product_keeps_comparison_history() -> None:
    assert "productId: text(raw.product_id || raw.productId || metadata.product_id" in VIEW
    assert "const previousSameMedia = completedRuns.find" in APP
    assert "const previousSameProduct = media.productId" in APP
    assert "item.media?.productId === media.productId" in APP
    assert "const previous = previousSameMedia || previousSameProduct || null" in APP
    assert "parent_review_id: previous?.id || null" in APP
    assert "предыдущего файла того же товара" in APP
    assert 'comparison_scope: repairSourceReviewId' in APP
    assert '? "repair_source"' in APP
    assert '? "same_media"' in APP
    assert '? "same_product"' in APP


def test_legal_source_keys_have_human_readable_disclosure() -> None:
    expected = {
        "ad_law_38fz": "Федеральный закон № 38-ФЗ",
        "ad_definition_1087": "Критерии отнесения информации к рекламе",
        "restricted_resources_72fz": "Федеральный закон № 72-ФЗ",
        "erid_order_68": "Приказ Роскомнадзора № 68",
        "ord_rules_974": "Правила передачи сведений",
        "publisher_registry_238": "аудиторией более 10 000",
        "personal_data_152fz": "Федеральный закон № 152-ФЗ",
        "image_rights_152_1": "Статья 152.1 ГК РФ",
        "cosmetics_tr_ts_009": "ТР ТС 009/2011",
        "food_label_tr_ts_022": "ТР ТС 022/2011",
        "youtube_synthetic": "Правила YouTube",
    }
    for key, label in expected.items():
        assert key in VIEW
        assert label in VIEW
    assert "Версия правил и пределы проверки" in VIEW
    assert "не заменяет юриста" in VIEW


def test_legal_source_links_use_fixed_allowlist_and_ignore_model_urls() -> None:
    for domain in (
        "government.ru",
        "publication.pravo.gov.ru",
        "eec.eaeunion.org",
        "support.google.com",
    ):
        assert domain in VIEW
    assert "const SOURCE_URLS = Object.freeze({" in VIEW
    assert 'target="_blank" rel="noopener noreferrer"' in VIEW
    assert "item.evidence?.legal_source_url" not in VIEW

    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
globalThis.window = {{ location: {{ href: "https://portal.test/" }} }};
const {{ contentReviewWorkspaceMarkup }} = await import({json.dumps(module_url)});
const run = {{
  id: "review-1",
  status: "completed",
  input: {{ platform: "youtube", content_kind: "advertising", product_category: "cosmetics" }},
  result: {{
    overall_score: 72,
    compliance_status: "human_review",
    findings: [{{
      severity: "high",
      category: "legal",
      title: "<img src=x onerror=alert(1)>",
      detail: "Проверить маркировку",
      source_key: "ad_law_38fz",
      evidence: {{ legal_source_url: "javascript:alert(1)" }}
    }}]
  }}
}};
const html = contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [run] }},
  currentRun: run,
  canDecide: false
}});
if (!html.includes('href="https://government.ru/docs/all/98086/"')) throw new Error("allowlisted source missing");
if (!html.includes('target="_blank" rel="noopener noreferrer"')) throw new Error("safe external-link attributes missing");
if (html.includes("javascript:alert(1)")) throw new Error("model URL reached markup");
if (html.includes("<img src=x")) throw new Error("finding content was not escaped");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_completed_readonly_video_can_be_watched_with_sound_and_downloaded() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
globalThis.window = {{ location: {{ href: "https://portal.test/" }} }};
const {{ contentReviewWorkspaceMarkup }} = await import({json.dumps(module_url)});
const run = {{
  id: "00000000-0000-4000-8000-000000000101",
  status: "completed",
  media: {{
    id: "00000000-0000-4000-8000-000000000102",
    name: "steamer-result.mp4",
    mime_type: "video/mp4",
    kind: "generated_video",
    status: "ready",
    signed_url: "https://example.test/steamer-result.mp4"
  }},
  input: {{ platform: "tiktok", content_kind: "advertising", product_category: "electronics" }},
  result: {{ overall_score: 82, compliance_status: "human_review", findings: [] }}
}};
const html = contentReviewWorkspaceMarkup({{
  catalog: {{ media: [], runs: [run] }},
  currentRun: run,
  canDecide: false
}});
if (!html.includes("Просмотрите точный MP4 со звуком")) throw new Error("sound review prompt missing");
if (!html.includes("<video")) throw new Error("exact video missing");
if (!html.includes(" controls ")) throw new Error("video controls missing");
if (html.includes(" muted")) throw new Error("readonly exact video was muted");
if (!html.includes('data-action="download-content-review-media"')) throw new Error("secure download action missing");
if (!html.includes(">Скачать MP4</button>")) throw new Error("download label missing");
if (html.includes(">Открыть отдельно</a>")) throw new Error("duplicate separate-window action still rendered");
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert 'action === "download-content-review-media"' in APP
    assert "refreshSignedUrls: true" in APP
    assert "await downloadGenerationOutput(run.media.url" in APP


def test_stale_processing_phase_does_not_lock_an_empty_review_form() -> None:
    module_url = (APP_DIR / "content-review-view.js").resolve().as_uri()
    script = f"""
import {{ contentReviewIsBusy, contentReviewWorkspaceMarkup }} from {json.dumps(module_url)};
if (contentReviewIsBusy("processing", null)) throw new Error("stale state stayed busy");
if (!contentReviewIsBusy("processing", {{ status: "queued" }})) {{
  throw new Error("active run was not busy");
}}
const html = contentReviewWorkspaceMarkup({{
  catalog: {{
    media: [{{
      id: "00000000-0000-4000-8000-000000000001",
      name: "product.png",
      supported: true,
      isVideo: false,
      url: "https://example.test/product.png"
    }}],
    runs: []
  }},
  currentRun: null,
  phase: "processing"
}});
if (!html.includes('aria-busy="false"')) throw new Error("empty form stayed busy");
if (!html.includes(">Проверить выбранные файлы</button>")) {{
  throw new Error("action label did not recover");
}}
if (html.includes("Проверка уже выполняется…")) {{
  throw new Error("stale processing label leaked into empty form");
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_pkce_verifier_crosses_tabs_without_persisting_the_auth_session() -> None:
    assert "createHybridAuthStorage()" in APP
    assert "isPkceVerifierStorageKey(key)" in APP
    assert "const verifierStorage = window.localStorage" in APP
    assert "const sessionStorage = window.sessionStorage" in APP
    assert "if (!isPkceVerifierStorageKey(key))" in APP
    assert "safeStorageSet(sessionStorage, key, value)" in APP
    assert "safeStorageSet(verifierStorage, key, value)" in APP
    assert "clearStoredPkceVerifier();" in APP
    assert "storage: createHybridAuthStorage()" in APP
    assert "storage: window.localStorage" not in APP
    assert "persistSession: true" in APP
    assert "flowType: \"pkce\"" in APP


def test_product_research_tasks_keep_approved_evidence_and_prohibitions() -> None:
    assert "productResearchTaskBlueprint(draft)" in APP
    assert "const proofPoints = splitResearchLines(draft.proof_points)" in APP
    assert "const avoidClaims = splitResearchLines(draft.avoid_claims)" in APP
    for copy in (
        "Подтверждённые доказательства — использовать только в этой формулировке",
        "Запрещённые и неподтверждённые обещания — не использовать",
        "Визуальное направление:",
        "Разрешённый призыв к действию:",
        "Ручная проверка перед сдачей:",
    ):
        assert copy in APP


def test_review_styles_are_responsive_theme_aware_and_motion_safe() -> None:
    for marker in (
        "var(--portal-primary)",
        "var(--portal-surface)",
        "var(--portal-ink)",
        ".content-review-layout",
        ".content-review-score-grid",
        ".content-review-decision-preview__media",
        "@media (max-width: 820px)",
        "@media (max-width: 560px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert marker in STYLES
