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
    assert "Шаг 3 из 7" in APP
    assert "<h2>${FACTORY_FLOW.length} этапов одного результата</h2>" in APP
    assert "review: renderContentReviewSection" in APP
    assert 'section === "review"' in APP
    assert 'state.api.contentReviewCatalog({ limit: 50 })' in APP
    assert './content-review-view.js?v=20260717.1' in APP
    assert './content-review.css?v=20260716.3' in INDEX
    assert './app.js?v=20260718.5' in INDEX
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


def test_browser_persists_bounded_frames_and_metrics_but_never_sends_raw_video() -> None:
    for marker in (
        "MAX_FRAME_CHARACTERS = 330_000",
        "MAX_TOTAL_FRAME_CHARACTERS = 1_650_000",
        "sampleTimes(duration)",
        "early_0_2_1_2_plus_late_distribution",
        "adjacent_frame_difference",
        "black_frame_ratio",
        "frozen_frame_ratio",
        "frozen_frame_suspected",
        "raw_video_sent: false",
        "audio_analyzed: false",
        'canvas.toDataURL("image/jpeg", quality)',
    ):
        assert marker in VIEW
    assert "buildContentReviewFrameFiles" in VIEW
    assert "jpegDataUriToBlob" in VIEW
    assert 'crypto.subtle.digest("SHA-256"' in VIEW
    assert "normalizedFrameCount < 4 || normalizedFrameCount > 5" in API
    assert 'prepareContentReviewEvidence: "creator_prepare_content_review_evidence"' in API
    assert 'commitContentReviewEvidence: "creator_commit_content_review_evidence"' in API
    start = API[API.index("async startContentReview(") : API.index("contentReviewStatus(")]
    assert 'action: "analyze"' in start
    assert "review_id: reviewId" in start
    assert "frames:" not in start
    assert "evidence_id: evidenceId" in start
    assert "raw_video_sent: false" in APP
    assert "0.2," in VIEW
    assert "1," in VIEW
    assert "2," in VIEW
    assert "differences.filter((value) => value < 0.015).length / differences.length" in VIEW
    assert "Исходный MP4 и его звук в ИИ-сервис не отправляются" in VIEW
    assert "fetch(media.url" not in VIEW
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
    assert flow.index("persistContentReviewDraft(form, { durableEvidence: pending })") < flow.index("commitStarted = true")
    assert "idempotencyKey: pending.commitIdempotencyKey" in flow
    assert 'status: "ready"' in flow
    assert "CONTENT_REVIEW_DRAFT_STORAGE_VERSION = 2" in APP
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
const frames = Array.from({{ length: 4 }}, () => `data:image/jpeg;base64,${{encoded}}`);
const files = await buildContentReviewFrameFiles({{
  frames,
  technical_metrics: {{
    source_type: "video",
    sampled_at_seconds: [0.2, 1, 2, 7.125]
  }}
}});
if (files.length !== 4) throw new Error("frame count");
for (const file of files) {{
  if (!(file.blob instanceof Blob) || file.blob.type !== "image/jpeg") throw new Error("blob");
  if (!/^[0-9a-f]{{64}}$/.test(file.sha256)) throw new Error("sha256");
  if (file.sizeBytes !== 160) throw new Error("size");
}}
if (files[3].timecodeSeconds !== 7.125) throw new Error("timecode");
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
const evidenceId = "44444444-4444-4444-8444-444444444444";
const reviewId = "55555555-5555-4555-8555-555555555555";
const commitKey = "66666666-6666-4666-8666-666666666666";
const prefix = `${{organizationId}}/${{userId}}/`;
const objectNames = Array.from({{ length: 4 }}, (_, index) => `${{prefix}}review-evidence/${{evidenceId}}/${{index}}.jpg`);
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
const prepared = await api.prepareContentReviewEvidence({{ mediaId, frameCount: 4 }});
if (prepared.evidenceId !== evidenceId || prepared.frameObjectNames.length !== 4) throw new Error("prepare");
await api.commitContentReviewEvidence({{
  evidenceId,
  technicalMetrics: {{ source_type: "video", frame_count: 4 }},
  idempotencyKey: commitKey,
  frames: objectNames.map((object_name, index) => ({{
    object_name, sha256: "a".repeat(64), size_bytes: 160, timecode_seconds: index
  }}))
}});
const started = await api.startContentReview({{
  media_id: mediaId,
  platform: "youtube",
  content_kind: "informational",
  product_category: "other",
  people_present: "no",
  technical_metrics: {{ source_type: "video", frame_count: 4 }},
  evidence_id: evidenceId
}});
await new Promise((resolve) => setTimeout(resolve, 0));
if (started.run.id !== reviewId) throw new Error("run lost");
if (started.analysis_request.status !== "background_queued") throw new Error("dispatch not queued");
if (invoked.length !== 1 || Object.keys(invoked[0]).sort().join(",") !== "action,review_id") throw new Error(JSON.stringify(invoked));
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
    assert "Сравнение с прошлой проверкой" in VIEW
    assert "escapeHtml(item.title)" in VIEW
    assert "escapeHtml(item.detail)" in VIEW
    assert "escapeHtml(item.action)" in VIEW
    assert ".innerHTML" not in VIEW
    assert "Это фильтр рисков, а не автоматическая юридическая экспертиза" in VIEW


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
            "точный файл не загрузился",
    ):
        assert marker in APP
    assert "data-content-review-exact-media" in VIEW
    assert 'data-exact-media-state="${mediaAvailable ? "loading" : "unavailable"}"' in VIEW
    assert "data-review-decision-submit disabled" in VIEW
    assert "Это подтверждение пользователя, а не автоматическое доказательство качества" in VIEW
    assert "state.api.contentReviewStatus(reviewId)" in APP
    assert "state.api.contentReviewCatalog({ limit: 50 })" in APP
    assert "Content review post-decision refresh failed" in APP


def test_generated_video_task_routes_to_content_review_instead_of_generic_acceptance() -> None:
    assert 'String(result.generation_status || "").toLowerCase() === "succeeded"' in APP
    assert "result.output_media_id" in APP
    assert 'data-action="open-generated-content-review"' in APP
    assert "Открыть проверку контента" in APP
    assert "state.contentReview.pendingMediaId = mediaId" in APP
    assert 'navigate("/workspace/review")' in APP
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
    assert 'String(media.metadata?.kind || "") === "generated_video"' in APP
    assert 'input.content_kind = "advertising"' in APP
    assert "input.ai_generated = true" in APP
    assert "Готовый платный AI-ролик проверяется только как реклама" in APP
    assert "external_ai_processing_basis_required" in API


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
    assert "productId: text(raw.product_id || metadata.product_id" in VIEW
    assert "const previousSameMedia = completedRuns.find" in APP
    assert "const previousSameProduct = media.productId" in APP
    assert "item.media?.productId === media.productId" in APP
    assert "const previous = previousSameMedia || previousSameProduct || null" in APP
    assert "parent_review_id: previous?.id || null" in APP
    assert "предыдущего файла того же товара" in APP
    assert 'comparison_scope: previousSameMedia ? "same_media" : previousSameProduct ? "same_product" : "none"' in APP


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
import {{ contentReviewWorkspaceMarkup }} from {json.dumps(module_url)};
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
