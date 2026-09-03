/**
 * The only module allowed to know the Supabase RPC/Storage contract.
 *
 * Database functions are narrow SECURITY DEFINER entry points. Every function
 * receives one `p_payload jsonb` argument and derives the current user from
 * auth.uid(); the browser never sends a user/profile/organization authority.
 * Keeping this boundary in one file makes a later transport change mechanical.
 */

export const RPC = Object.freeze({
  bootstrap: "creator_bootstrap",
  completeModule: "creator_complete_module",
  submitCourseCheck: "creator_submit_course_check",
  submitPlatformSimulator: "creator_submit_platform_simulator",
  submitExam: "creator_submit_exam",
  workspaceSection: "creator_workspace_section",
  projectFlow: "creator_project_flow",
  projectMembers: "creator_project_members",
  grantProjectMember: "creator_grant_project_member",
  revokeProjectMember: "creator_revoke_project_member",
  projectMedia: "creator_project_media",
  projectPlacement: "creator_project_placement",
  createProject: "creator_create_workspace_project",
  archiveProject: "creator_archive_workspace_project",
  requestWorkspaceAccess: "creator_request_workspace_access",
  generationMediaIdentity: "creator_generation_media_identity",
  generationLearningPolicy: "creator_generation_learning_policy",
  aiLearningControlRoom: "creator_ai_learning_control_room",
  aiLearningMarketScopeIndex: "creator_ai_learning_market_scope_index",
  registerAiKnowledgeSource: "creator_register_ai_knowledge_source",
  decideAiTeachingCard: "creator_decide_ai_teaching_card",
  decideAiHistoricalCase: "creator_decide_ai_historical_case",
  decideAiResearchReceipt: "creator_decide_ai_research_receipt",
  generationRepairPolicy: "creator_generation_repair_policy",
  generationSpecStatus: "creator_generation_spec_status",
  prepareGenerationSpec: "creator_prepare_generation_spec",
  prepareGenerationStrategySpec: "creator_prepare_generation_strategy_spec",
  controlGenerationSpec: "creator_control_generation_spec",
  generationSpecEffectivePolicy: "creator_generation_spec_effective_policy",
  bindGenerationSpecAiResearch:
    "contentengine_bind_generation_spec_ai_research",
  generationSpecAiResearchBinding:
    "contentengine_generation_spec_ai_research_binding",
  generationResearchRecommendation:
    "contentengine_generation_research_recommendation",
  generationAiResearchWorkingDraft:
    "contentengine_generation_ai_research_working_draft",
  bindGenerationSpecVideoReference:
    "contentengine_bind_generation_spec_video_reference",
  generationVideoReferenceLineage:
    "contentengine_generation_video_reference_lineage",
  generationArchive: "creator_generation_archive",
  generationStrategyRepeatData: "creator_generation_strategy_repeat_data",
  generationStrategyAssetCandidates:
    "creator_generation_strategy_asset_candidates",
  archiveGenerationBatch: "creator_archive_generation_batch",
  workspaceBrowser: "creator_workspace_browser",
  createWorkspaceFolder: "creator_create_workspace_folder",
  updateWorkspaceFolder: "creator_update_workspace_folder",
  moveWorkspaceItems: "creator_move_workspace_items",
  createMockBatch: "creator_create_mock_batch",
  recordMetric: "creator_record_metric",
  configureTrackingLink: "creator_configure_tracking_link",
  setWbAlias: "creator_set_wb_alias",
  decidePayout: "creator_decide_payout",
  confirmPlacement: "creator_confirm_placement",
  transitionTask: "creator_transition_task",
  createFeedback: "creator_create_feedback",
  registerMedia: "creator_register_media",
  attachExactYoutubeMedia: "contentengine_attach_exact_youtube_media",
  exactYoutubeSourceQueue: "contentengine_exact_youtube_source_queue",
  captureEvent: "creator_capture_event",
  inviteAttempts: "creator_invite_delivery_attempts",
  adminSnapshot: "creator_admin_snapshot",
  adminMutate: "creator_admin_mutate",
  adminAccountOwnership: "creator_admin_account_ownership",
  publishingAccounts: "creator_publishing_accounts",
  enqueuePublishingJob: "creator_enqueue_publishing_job",
  enqueueVideoFinalization: "creator_enqueue_video_finalization",
  issueClientReviewLink: "creator_issue_client_review_link",
  revokeClientReviewLink: "creator_revoke_client_review_link",
  listClientReviewLinks: "creator_list_client_review_links",
  listCampaignReviewCandidates: "creator_list_campaign_review_candidates",
  configureClientReviewIntake: "creator_configure_client_review_intake",
  listClientIntake: "creator_list_client_intake",
  decideClientIntakeBrief: "creator_decide_client_intake_brief",
  appendClientReviewLinkItems: "creator_append_client_review_link_items",
  publishGenerationResult: "creator_publish_generation_result",
  rejectGenerationResult: "creator_reject_generation_result",
  teamAccounts: "creator_team_accounts",
  resultsFunnel: "creator_results_funnel",
  contentPassportRegistry: "creator_content_passport_registry",
  contentResultPassport: "creator_content_result_passport",
  contentHypotheses: "creator_content_hypotheses",
  contentHypothesis: "creator_content_hypothesis",
  saveContentHypothesis: "creator_save_content_hypothesis",
  approveContentHypothesisVersion: "creator_approve_content_hypothesis_version",
  decideContentHypothesis: "creator_decide_content_hypothesis",
  managerDashboard: "creator_manager_dashboard",
  operationalHealth: "creator_operational_health",
  generationSpendOverview: "creator_generation_spend_overview",
  generationModelAcceptance: "creator_generation_model_acceptance",
  updateGenerationSpendPolicy: "creator_update_generation_spend_policy",
  createGenerationCampaign: "creator_create_generation_campaign",
  updateGenerationCampaignSpendPolicy: "creator_update_generation_campaign_spend_policy",
  myWork: "creator_my_work",
  notifications: "creator_notifications",
  markNotificationsRead: "creator_mark_notifications_read",
  notificationCenter: "creator_notification_center",
  validateNotificationAction: "creator_validate_notification_action",
  markVisibleNotificationsRead: "creator_mark_visible_notifications_read",
  trainingProgress: "creator_training_progress",
  saveTrainingProgress: "creator_save_training_progress",
  savePracticalProject: "creator_save_practical_project",
  decidePracticalProject: "creator_decide_practical_project",
  savedWorkViews: "creator_saved_work_views",
  startProductResearch: "creator_start_project_research",
  productResearchStatus: "creator_project_research_status",
  researchStageControlStatus: "creator_research_stage_control_status",
  controlResearchStage: "creator_control_research_stage",
  researchCategoryLearningStatus: "creator_research_category_learning_status",
  captureResearchCategoryReadiness: "creator_capture_research_category_readiness",
  correctResearchSourceAnalysis: "creator_correct_research_source_analysis",
  correctResearchYoutubeObservationAnalysis:
    "creator_correct_research_youtube_observation_analysis",
  configureResearchSourceCollectionPolicy:
    "creator_configure_research_source_collection_policy",
  researchWatchlistStatus: "creator_research_watchlist_status",
  configureResearchWatchlist: "creator_configure_research_watchlist",
  researchProviderStatus: "creator_research_provider_status",
  researchMarketCategoryRegistry: "creator_research_market_category_registry",
  resolveResearchMarketCategory: "creator_resolve_research_market_category",
  reaffirmResearchMarketCategory:
    "creator_reaffirm_research_market_category",
  retireResearchMarketCategory: "creator_retire_research_market_category",
  researchOutcomeLearningScopes: "creator_research_outcome_learning_scopes",
  researchOutcomeLearningStatus: "creator_research_outcome_learning_status",
  refreshResearchOutcomeLearning: "creator_refresh_research_outcome_learning",
  decideResearchOutcomeLearning: "creator_decide_research_outcome_learning",
  researchYoutubeOverview: "creator_research_youtube_overview",
  researchYoutubeStatus: "creator_research_youtube_status",
  requestResearchYoutubeCanary: "creator_request_research_youtube_canary",
  requestResearchYoutubeRefresh: "creator_request_research_youtube_refresh",
  decideResearchYoutubeRollout: "creator_decide_research_youtube_rollout",
  decideResearchYoutubeCandidate: "creator_decide_research_youtube_candidate",
  saveCreativeBriefDraft: "creator_save_project_creative_brief_draft",
  approveCreativeBrief: "creator_approve_project_creative_brief",
  contentReviewCatalog: "creator_content_review_catalog",
  prepareContentReviewEvidence: "creator_prepare_content_review_evidence",
  commitContentReviewEvidence: "creator_commit_content_review_evidence",
  startContentReview: "creator_start_content_review",
  startGeneratedVideoReview: "creator_start_generated_video_review",
  contentReviewStatus: "creator_content_review_status",
  decideContentReview: "creator_decide_content_review",
  recoverContentReviewSoundAssessment:
    "creator_recover_content_review_sound_assessment",
  restoreProjectPlacement: "creator_restore_project_placement",
  approveGeneratedPhotoWithContext:
    "creator_approve_generated_photo_review_with_context",
  approveGeneratedVideoWithContext:
    "creator_approve_generated_video_review_with_context",
});

export const PRODUCT_RESEARCH_PLATFORMS = Object.freeze([
  "instagram",
  "youtube",
  "vk",
  "wildberries",
  "ozon",
]);
export const AI_PRODUCT_CATEGORIES = Object.freeze([
  "cosmetics",
  "baa",
  "sports_food",
  "food",
  "household",
  "apparel",
  "electronics",
  "other",
]);
export const AI_KNOWLEDGE_BUCKET = "contentengine-knowledge";
const AI_PRODUCT_CATEGORY_SET = new Set(AI_PRODUCT_CATEGORIES);
const EXACT_YOUTUBE_RESEARCH_LIFECYCLE_ACTIONS = Object.freeze({
  not_started: "prepare_exact_media_analysis",
  analysis_in_progress: "open_research",
  analysis_failed: "open_research",
  completed_without_ai_receipt: "open_research",
  awaiting_learning_selection: "review_ai_learning",
  recommendations_ready: "open_generation",
  excluded: "open_research",
});
const EXACT_YOUTUBE_RESEARCH_RUN_STATUS_SET = new Set([
  "queued",
  "processing",
  "completed",
  "failed",
  "cancelled",
]);
const AI_KNOWLEDGE_MIME_TYPES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
  "text/markdown",
  "text/plain",
]);
const PRODUCT_RESEARCH_PLATFORM_SET = new Set(PRODUCT_RESEARCH_PLATFORMS);
const PRODUCT_RESEARCH_PAID_AUTHORIZATION_KEYS = Object.freeze([
  "version",
  "provider",
  "provider_key",
  "adapter_version",
  "model",
  "currency",
  "billing_mode",
  "service_tier",
  "input_usd_per_million_tokens",
  "output_usd_per_million_tokens",
  "long_context_threshold_input_tokens",
  "long_context_input_usd_per_million_tokens",
  "long_context_output_usd_per_million_tokens",
  "web_search_usd_per_call",
  "max_output_tokens",
  "max_provider_attempts",
  "fixed_total",
  "confirmation_value",
]);
const PRODUCT_RESEARCH_PAID_AUTHORIZATION_EXACT = Object.freeze({
  version: "openai-api-2026-08-13-gpt-5.5-standard-context-v3",
  provider: "openai",
  provider_key: "openai_web_search",
  adapter_version: "openai-responses-web-search-v1",
  model: "gpt-5.5",
  currency: "USD",
  billing_mode: "metered_actual_usage",
  service_tier: "default",
  input_usd_per_million_tokens: "5.00",
  output_usd_per_million_tokens: "30.00",
  long_context_threshold_input_tokens: 272_000,
  long_context_input_usd_per_million_tokens: "10.00",
  long_context_output_usd_per_million_tokens: "45.00",
  web_search_usd_per_call: "0.01",
  max_output_tokens: 18_000,
  max_provider_attempts: 1,
  fixed_total: false,
  confirmation_value:
    "OPENAI_GPT_5_5_WEB_RESEARCH_20260813_DEFAULT_SHORT_IN_5_OUT_30_LONG_GT272K_IN_10_OUT_45_SEARCH_0_01_MAXOUT_18000",
});
const RESEARCH_STAGE_SET = new Set([
  "sources",
  "category",
  "competitors",
  "trends",
  "guidance",
  "brief",
  "scenarios",
]);
const RESEARCH_STAGE_ACTION_SET = new Set([
  "patch",
  "reject",
  "revert",
  "fork",
  "recompute",
  "cancel",
]);
const RESEARCH_STAGE_HASH_PATTERN = /^[0-9a-f]{64}$/u;
const RESEARCH_STAGE_BRANCH_KEY_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/u;
const RESEARCH_COLLECTION_PROVIDER_PATTERN = /^[a-z][a-z0-9_.-]{1,79}$/u;
const RESEARCH_ANALYSIS_FORBIDDEN_KEYS = new Set([
  "caption",
  "captions",
  "raw_caption",
  "raw_captions",
  "transcript",
  "transcripts",
  "raw_transcript",
  "raw_transcripts",
  "raw_text",
  "source_text",
  "full_text",
]);
const RESEARCH_SOURCE_ANALYSIS_SCHEMA_VERSION =
  "research-source-interpretation-v1";
const RESEARCH_SOURCE_ANALYSIS_CLASSIFICATIONS = new Set([
  "competitor",
  "adjacent",
  "trend_signal",
  "reference",
  "irrelevant",
  "unknown",
]);
const RESEARCH_SOURCE_ANALYSIS_CONFIDENCE = new Set([
  "low",
  "medium",
  "high",
]);
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_SCHEMA_VERSION =
  "research-youtube-observation-analysis-v1";
const RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_CLASSIFICATIONS = new Set([
  "potential_competitor",
  "adjacent",
  "unknown",
]);
const RESEARCH_SOURCE_STRUCTURAL_SIGNAL_PATTERN =
  /^[a-z][a-z0-9_]*\.[a-z][a-z0-9_.]*$/u;

const REAL_GENERATION_FUNCTION = "creator-generate";
const GENERATION_STRATEGY_EDGE_ACTIONS = Object.freeze(new Set([
  "strategy_catalog",
  "strategy_media_probe",
  "strategy_bind",
  "strategy_preflight",
  "strategy_start",
  "strategy_status",
  "strategy_reconcile",
]));
const GENERATION_STRATEGY_IDEMPOTENT_ACTIONS = Object.freeze(new Set([
  "strategy_media_probe",
  "strategy_bind",
  "strategy_preflight",
  "strategy_start",
  "strategy_reconcile",
]));
const GENERATION_STRATEGY_IDEMPOTENCY_PATTERN =
  /^[A-Za-z0-9._:-]{8,180}$/u;
const GENERATION_STRATEGY_UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/u;
const GENERATION_STRATEGY_SHA256_PATTERN = /^[0-9a-f]{64}$/u;
// Необязательные ключи запроса привязки. Набор ЗАКРЫТЫЙ и упорядоченный: он же
// задаёт порядок ключей в собранном списке.
const GENERATION_STRATEGY_BIND_OPTIONAL_KEYS = Object.freeze([
  "engine",
  "duet_presenter_id",
]);
const GENERATION_STRATEGY_REQUEST_KEYS = Object.freeze({
  strategy_catalog: Object.freeze([
    "action",
    "organization_id",
  ]),
  strategy_media_probe: Object.freeze([
    "action",
    "organization_id",
    "project_id",
    "media_id",
    "confirmation",
    "idempotency_key",
  ]),
  strategy_bind: Object.freeze([
    "action",
    "organization_id",
    "project_id",
    "spec_id",
    "spec_version",
    "spec_hash",
    "generation_strategy",
    "confirmation",
    "idempotency_key",
  ]),
  // Тот же запрос с выбранным движком каскада. Оставлен как ЭТАЛОННАЯ форма:
  // именно на него ссылаются проверки, и по нему видно, куда встают
  // необязательные ключи. Сама сверка идёт через
  // generationStrategyBindRequestKeys — необязательных ключей стало два
  // (движок и ведущий «Дуэта»), и четыре замороженных списка на два ключа
  // разошлись бы между собой на первой же правке.
  //
  // Точность при этом не потеряна: список строится из ЗАКРЫТОГО набора
  // GENERATION_STRATEGY_BIND_OPTIONAL_KEYS, пересечённого с тем, что реально
  // пришло. Чужой ключ по-прежнему роняет совпадение — он просто не может
  // попасть в список.
  strategy_bind_engine: Object.freeze([
    "action",
    "organization_id",
    "project_id",
    "spec_id",
    "spec_version",
    "spec_hash",
    "generation_strategy",
    "engine",
    "confirmation",
    "idempotency_key",
  ]),
  strategy_preflight: Object.freeze([
    "action",
    "organization_id",
    "project_id",
    "spec_id",
    "spec_version",
    "spec_hash",
    "binding_id",
    "binding_hash",
    "selection_hash",
    "price_hash",
    "spend_confirmation",
    "confirmation",
    "idempotency_key",
  ]),
  strategy_start: Object.freeze([
    "action",
    "organization_id",
    "project_id",
    "spec_id",
    "spec_version",
    "spec_hash",
    "binding_id",
    "binding_hash",
    "selection_hash",
    "price_hash",
    "spend_confirmation",
    "confirmation",
    "receipt_id",
    "receipt_hash",
    "campaign_id",
    "idempotency_key",
  ]),
  strategy_status: Object.freeze([
    "action",
    "organization_id",
    "project_id",
    "generation_job_id",
  ]),
  // Mirrors readGenerationStrategyReconcilePayload in the Edge function.
  // The stable recipe identity is independent from the paid provider route;
  // provider_task_id is appended exclusively for attach_existing_task.
  strategy_reconcile: Object.freeze([
    "action",
    "organization_id",
    "project_id",
    "generation_job_id",
    "dispatch_result_id",
    "incident_id",
    "resolution",
    "confirmation",
    "evidence_reference",
    "reason",
    "idempotency_key",
  ]),
});
const GENERATION_STRATEGY_RECONCILE_ATTACH_REQUEST_KEYS = Object.freeze([
  ...GENERATION_STRATEGY_REQUEST_KEYS.strategy_reconcile,
  "provider_task_id",
]);
const GENERATION_STRATEGY_RUNWAY_TASK_ID_PATTERN =
  /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u;
const GENERATION_STRATEGY_FAL_REQUEST_ID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
// Идентификатор готового ролика HeyGen: у «Дуэта» задача опознаётся роликом, а
// не задачей. Форма повторяет HEYGEN_VIDEO_ID из контракта edge — расходиться
// им нельзя, иначе одна сторона примет то, что другая отвергнет.
const GENERATION_STRATEGY_HEYGEN_VIDEO_ID_PATTERN =
  /^[A-Za-z0-9_-]{8,128}$/u;
const GENERATION_STRATEGY_RESPONSE_CONTRACTS = Object.freeze({
  strategy_catalog: Object.freeze({
    keys: Object.freeze([
      "ok",
      "catalog",
    ]),
  }),
  strategy_media_probe: Object.freeze({
    version: "generation-strategy-media-probe-response-v1",
    keys: Object.freeze([
      "ok",
      "version",
      "media_id",
      "duration_seconds",
      "verified_at",
      "replay",
    ]),
  }),
  strategy_bind: Object.freeze({
    version: "generation-strategy-resolve-bind-response-v1",
    keys: Object.freeze([
      "ok",
      "version",
      "binding",
      "selection",
      "price",
      "contract",
    ]),
  }),
  strategy_preflight: Object.freeze({
    version: "generation-strategy-preflight-response-v1",
    keys: Object.freeze([
      "ok",
      "version",
      "replay",
      "receipt",
      "provider_preflight",
      "launch_enabled",
      "contract",
    ]),
  }),
  strategy_start: Object.freeze({
    version: "generation-strategy-status-response-v1",
    keys: Object.freeze([
      "ok",
      "version",
      "job",
      "strategy",
      "selection",
      "price",
      "dispatch",
      "reconciliation",
      "output",
      "error",
      "contract",
    ]),
  }),
  strategy_status: Object.freeze({
    version: "generation-strategy-status-response-v1",
    keys: Object.freeze([
      "ok",
      "version",
      "job",
      "strategy",
      "selection",
      "price",
      "dispatch",
      "reconciliation",
      "output",
      "error",
      "contract",
    ]),
  }),
  strategy_reconcile: Object.freeze({
    version: "generation-strategy-status-response-v1",
    keys: Object.freeze([
      "ok",
      "version",
      "job",
      "strategy",
      "selection",
      "price",
      "dispatch",
      "reconciliation",
      "output",
      "error",
      "contract",
    ]),
  }),
});
const GENERATION_STRATEGY_SPEC_PREPARE_REQUEST_KEYS = Object.freeze([
  "version",
  "organization_id",
  "project_id",
  "platform",
  "product_category",
  "selection",
  "editable_intent",
  "proposed_prompt",
  "mechanics_summary",
  "confirmation",
  "idempotency_key",
  "reason",
]);
// Товар «Дуэта» приходит ЯВНЫМ полем: фотографий товара у него нет, и вывести
// его больше неоткуда. У «Копии» и «Создания» товар уже назван снимками, и
// второй источник того же факта здесь запрещён — два источника однажды
// разойдутся молча. Отсюда ДВА состава ключей, а не один необязательный ключ:
// «не прислали, где надо» и «прислали, где нельзя» — разные ошибки формы.
const GENERATION_STRATEGY_SPEC_PREPARE_DUET_KEYS = Object.freeze([
  ...GENERATION_STRATEGY_SPEC_PREPARE_REQUEST_KEYS,
  "product_id",
]);
const GENERATION_STRATEGY_MECHANICS_KEYS = Object.freeze([
  "version",
  "hook",
  "beat_sequence",
  "pacing",
  "camera_language",
  "composition",
  "audio_pattern",
  "cta_pattern",
]);
const GENERATION_STRATEGY_SPEC_SELECTION_RULES = Object.freeze({
  // «Дуэт»: кадр задаёт исходник, ассет ровно один — ведущего даёт библиотека.
  viral_avatar_ugc: Object.freeze({
    dimension: "resolution",
    dimensions: Object.freeze(["720p", "1080p"]),
    attestations: Object.freeze([
      "source_media_rights_confirmed",
      "transformative_use_confirmed",
      "product_assets_rights_confirmed",
      "depicted_people_consent_confirmed",
      "avatar_likeness_consent_confirmed",
    ]),
    roles: Object.freeze({
      source_video: Object.freeze([1, 1]),
    }),
  }),
  viral_product_swap: Object.freeze({
    dimension: "resolution",
    dimensions: Object.freeze(["720p", "1080p"]),
    attestations: Object.freeze([
      "source_media_rights_confirmed",
      "transformative_use_confirmed",
      "product_assets_rights_confirmed",
      "depicted_people_consent_confirmed",
    ]),
    roles: Object.freeze({
      source_video: Object.freeze([1, 1]),
      original_product_image: Object.freeze([1, 1]),
      new_product_image: Object.freeze([1, 10]),
    }),
  }),
  viral_rebuild: Object.freeze({
    dimension: "ratio",
    dimensions: Object.freeze([
      "1280:720",
      "720:1280",
      "960:960",
      "834:1112",
      "1920:1080",
      "1080:1920",
      "1440:1440",
      "1248:1664",
    ]),
    attestations: Object.freeze([
      "source_media_rights_confirmed",
      "transformative_use_confirmed",
      "product_assets_rights_confirmed",
      "depicted_people_consent_confirmed",
    ]),
    roles: Object.freeze({
      source_video: Object.freeze([1, 1]),
      product_image: Object.freeze([1, 10]),
      style_image: Object.freeze([0, 4]),
    }),
  }),
});
const PRODUCT_RESEARCH_FUNCTION = "creator-product-research";
const RESEARCH_INGESTION_FUNCTION = "creator-research-ingestion";
const AI_HISTORICAL_CASE_IMPORT_FUNCTION = "creator-ai-case-import";
const RESEARCH_SATELLITE_TIMEOUT_MS = 3500;
const RESEARCH_YOUTUBE_TERMS_VERSION = "youtube-developer-policies-2026-08-03-v1";
const RESEARCH_OUTCOME_PLATFORMS = new Set([
  "instagram",
  "tiktok",
  "youtube",
  "vk",
  "telegram",
  "wildberries",
]);
const RESEARCH_OUTCOME_MODELS = new Set([
  "gen4_turbo",
  "seedance2_fast",
  "seedream5_lite",
]);
const CONTENT_REVIEW_FUNCTION = "creator-content-review";
const ACCESS_FUNCTION = "creator-access";
const PUBLIC_RECOVERY_FUNCTION = "creator-recovery";
const GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8";
const PROVIDER_READINESS_RECEIPT_VERSION =
  "generation-provider-readiness-receipt-v3";
const PROVIDER_READINESS_RECEIPT_VERSION_V4 =
  "generation-provider-readiness-receipt-v4";
const PROVIDER_READINESS_V4_RUNWAY_MODELS = new Set([
  "gen4.5",
  "seedance2_mini",
  "veo3.1_fast",
  "gemini_omni_flash",
]);
const PROVIDER_READINESS_UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu;
const PROVIDER_READINESS_SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const PROVIDER_READINESS_TTL_MS = 15 * 60 * 1_000;
const PROVIDER_READINESS_FUTURE_SKEW_MS = 60 * 1_000;
const REAL_GENERATION_SKUS = Object.freeze({
  gen4_turbo: Object.freeze({
    audio: false,
    prompt_max_length: 1000,
    min_duration_seconds: 2,
    max_duration_seconds: 10,
    credits_per_second: 5,
  }),
  seedance2_fast: Object.freeze({
    audio: true,
    format: "9:16",
    prompt_max_length: 1200,
    min_duration_seconds: 4,
    max_duration_seconds: 15,
    credits_per_second: 29,
  }),
  seedream5_lite: Object.freeze({
    duration_seconds: 0,
    audio: false,
    format: "1:1",
    prompt_max_length: 1200,
    confirmation: "RUNWAY_SEEDREAM5_LITE_2K_USD_0.04",
    estimated_usd: "0.04",
  }),
});

function realGenerationSku(model, durationSeconds) {
  const normalizedModel = String(model || "");
  const base = REAL_GENERATION_SKUS[normalizedModel];
  const duration = Number(durationSeconds);
  if (!base) return null;
  if (normalizedModel === "seedream5_lite") {
    return duration === 0 ? base : null;
  }
  if (
    !Number.isInteger(duration)
    || duration < base.min_duration_seconds
    || duration > base.max_duration_seconds
  ) return null;
  const estimatedCredits = duration * base.credits_per_second;
  const estimatedUsd = (estimatedCredits / 100).toFixed(2);
  return Object.freeze({
    ...base,
    duration_seconds: duration,
    estimated_credits: estimatedCredits,
    estimated_usd: estimatedUsd,
    confirmation: normalizedModel === "seedance2_fast"
      ? `RUNWAY_SEEDANCE2_FAST_${duration}S_AUDIO_USD_${estimatedUsd}`
      : `RUNWAY_GEN4_TURBO_${duration}S_USD_${estimatedUsd}`,
  });
}

const PROVIDER_READINESS_FIELDS = Object.freeze([
  "version", "receipt_id", "receipt_hash", "organization_id", "checked_by",
  "provider", "model", "input_mode", "duration_seconds", "format",
  "resolution", "audio", "last_frame", "ready", "estimated_cost_minor",
  "estimated_credits", "credential_configured", "balance_sufficient",
  "model_available", "daily_quota_available", "failure_code",
  "catalog_version", "pricing_version", "learning_gate_version",
  "checked_at", "expires_at", "status", "fresh", "spend_confirmation",
  "automatic_generation", "automatic_spend",
]);
const PROVIDER_READINESS_V4_FIELDS = Object.freeze([
  ...PROVIDER_READINESS_FIELDS,
  "project_id", "spec_id", "spec_version", "spec_hash", "scope_hash",
]);

function apiGenerationPreflightRequiresV4(provider, model) {
  return provider === "runway"
    && PROVIDER_READINESS_V4_RUNWAY_MODELS.has(model);
}

function normalizeApiGenerationProviderPreflight(value, expected = {}) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const provider = String(value.provider || "").trim();
  const model = typeof value.model === "string"
    ? value.model.trim()
    : "";
  const requiresV4 = apiGenerationPreflightRequiresV4(provider, model);
  const expectedVersion = requiresV4
    ? PROVIDER_READINESS_RECEIPT_VERSION_V4
    : PROVIDER_READINESS_RECEIPT_VERSION;
  if (!hasExactObjectKeys(
    value,
    requiresV4 ? PROVIDER_READINESS_V4_FIELDS : PROVIDER_READINESS_FIELDS,
  )) return null;
  const checkedAt = typeof value.checked_at === "string"
    ? value.checked_at.trim()
    : "";
  const expiresAt = typeof value.expires_at === "string"
    ? value.expires_at.trim()
    : "";
  const checkedAtMs = Date.parse(checkedAt);
  const expiresAtMs = Date.parse(expiresAt);
  const nowMs = Date.now();
  const expectedSpec = expected.generation_spec_context;
  if (
    value.version !== expectedVersion ||
    !["runway", "google"].includes(provider) ||
    !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u.test(model) ||
    value.input_mode !== "image" ||
    !Number.isSafeInteger(value.duration_seconds) ||
    value.duration_seconds < 0 ||
    !/^\d{1,4}:\d{1,4}$/u.test(String(value.format || "")) ||
    !/^(?:\d{3,4}p|[1-9]\d?K)$/u.test(String(value.resolution || "")) ||
    typeof value.audio !== "boolean" ||
    typeof value.last_frame !== "boolean" ||
    value.ready !== true ||
    value.status !== "ready" ||
    value.credential_configured !== true ||
    value.model_available !== true ||
    value.failure_code !== null ||
    !Number.isSafeInteger(value.estimated_cost_minor) ||
    value.estimated_cost_minor < 0 ||
    !(value.estimated_credits === null || Number.isSafeInteger(value.estimated_credits)) ||
    !(value.balance_sufficient === null || value.balance_sufficient === true) ||
    !(value.daily_quota_available === null || value.daily_quota_available === true) ||
    (provider === "runway" && !Number.isSafeInteger(value.estimated_credits)) ||
    (provider === "runway" && value.balance_sufficient !== true) ||
    (provider === "runway" && value.daily_quota_available !== true) ||
    (provider === "google" && value.estimated_credits !== null) ||
    value.learning_gate_version !== GENERATION_LEARNING_GATE_VERSION ||
    value.fresh !== true ||
    value.automatic_generation !== false ||
    value.automatic_spend !== false ||
    !/^[A-Z0-9][A-Z0-9_.:-]{2,255}$/u.test(String(value.spend_confirmation || "")) ||
    !PROVIDER_READINESS_UUID_PATTERN.test(
      String(value.receipt_id || "").trim(),
    ) ||
    !PROVIDER_READINESS_SHA256_PATTERN.test(
      String(value.receipt_hash || "").trim(),
    ) ||
    !Number.isFinite(checkedAtMs) ||
    !Number.isFinite(expiresAtMs) ||
    checkedAtMs > nowMs + PROVIDER_READINESS_FUTURE_SKEW_MS ||
    expiresAtMs <= nowMs ||
    expiresAtMs - checkedAtMs !== PROVIDER_READINESS_TTL_MS ||
    (expected.provider && provider !== expected.provider) ||
    (expected.model && model !== expected.model) ||
    (expected.input_mode && value.input_mode !== expected.input_mode) ||
    (Number.isSafeInteger(expected.duration_seconds)
      && value.duration_seconds !== expected.duration_seconds) ||
    (expected.format && value.format !== expected.format) ||
    (expected.resolution && value.resolution !== expected.resolution) ||
    (typeof expected.audio === "boolean" && value.audio !== expected.audio) ||
    (typeof expected.last_frame === "boolean"
      && value.last_frame !== expected.last_frame) ||
    (requiresV4 && (
      !PROVIDER_READINESS_UUID_PATTERN.test(String(value.project_id || "")) ||
      !PROVIDER_READINESS_UUID_PATTERN.test(String(value.spec_id || "")) ||
      !Number.isSafeInteger(value.spec_version) ||
      value.spec_version < 1 ||
      value.spec_version > 100_000 ||
      !PROVIDER_READINESS_SHA256_PATTERN.test(String(value.spec_hash || "")) ||
      !PROVIDER_READINESS_SHA256_PATTERN.test(String(value.scope_hash || "")) ||
      !PROVIDER_READINESS_UUID_PATTERN.test(String(expected.project_id || "")) ||
      !expectedSpec ||
      typeof expectedSpec !== "object" ||
      Array.isArray(expectedSpec) ||
      value.project_id !== expected.project_id ||
      value.spec_id !== expectedSpec.spec_id ||
      value.spec_version !== expectedSpec.spec_version ||
      value.spec_hash !== expectedSpec.spec_hash
    ))
  ) {
    return null;
  }
  return Object.freeze({ ...value });
}

export function mediaKindRequiresProduct(kind) {
  return ["product_photo", "packshot"].includes(String(kind || "").trim());
}

async function settleResearchSatellite(callPromise, code) {
  let timeoutId;
  try {
    return await Promise.race([
      Promise.resolve(callPromise).then(
        (value) => ({ ok: true, value }),
        (error) => ({ ok: false, error }),
      ),
      new Promise((resolve) => {
        timeoutId = globalThis.setTimeout(() => resolve({
          ok: false,
          error: { code: `${code}_timeout` },
        }), RESEARCH_SATELLITE_TIMEOUT_MS);
      }),
    ]);
  } finally {
    if (timeoutId !== undefined) globalThis.clearTimeout(timeoutId);
  }
}

function requireResearchOutcomeScope(value) {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const marketCategoryId = String(
    source.market_category_id || source.marketCategoryId || "",
  ).trim().toLowerCase();
  const platform = String(source.platform || "").trim().toLowerCase();
  const model = String(source.model || "").trim().toLowerCase();
  if (
    !isUuid(marketCategoryId)
    || !RESEARCH_OUTCOME_PLATFORMS.has(platform)
    || !RESEARCH_OUTCOME_MODELS.has(model)
  ) {
    throw new CreatorApiError("Обновите исследование и выберите точный контур результата.", {
      code: "research_outcome_scope_invalid",
    });
  }
  return { market_category_id: marketCategoryId, platform, model };
}

function researchOutcomeScopeKey(scope) {
  const exact = requireResearchOutcomeScope(scope);
  return `${exact.market_category_id}:${exact.platform}:${exact.model}`;
}

function readResearchOutcomeScopeRegistry(value, expectedRunId) {
  const source = value?.data && typeof value.data === "object" && !Array.isArray(value.data)
    ? value.data
    : value && typeof value === "object" && !Array.isArray(value)
      ? value
      : null;
  if (
    !source
    || source.ok !== true
    || source.version !== "research-outcome-scope-registry-v1"
    || String(source.run_id || "").toLowerCase() !== expectedRunId
    || !isUuid(String(source.product_id || ""))
    || typeof source.truncated !== "boolean"
    || !Array.isArray(source.scopes)
    || source.scopes.length > 50
    || Number(source.returned_scope_count) !== source.scopes.length
  ) return null;
  const seen = new Set();
  const scopes = [];
  for (const item of source.scopes) {
    if (!item || typeof item !== "object" || Array.isArray(item)) return null;
    let scope;
    try {
      scope = requireResearchOutcomeScope(item.scope);
    } catch {
      return null;
    }
    const key = researchOutcomeScopeKey(scope);
    if (item.scope_key !== key || seen.has(key)) return null;
    const category = item.market_category;
    if (
      !category
      || typeof category !== "object"
      || Array.isArray(category)
      || String(category.market_category_id || "").toLowerCase()
        !== scope.market_category_id
      || typeof category.canonical_name !== "string"
      || !["active", "retired"].includes(String(category.status || ""))
    ) return null;
    seen.add(key);
    scopes.push({ key, scope, raw: item });
  }
  return { raw: source, scopes, truncated: source.truncated };
}

// Действия ведущего «Дуэта» в creator-generate: у них собственная форма ответа.
const DUET_PRESENTER_ACTIONS = new Set([
  "duet_presenter_catalog",
  "duet_presenter_generate",
  "duet_presenter_generation_status",
]);

export class CreatorApiError extends Error {
  constructor(message, details = {}) {
    super(message);
    this.name = "CreatorApiError";
    this.code = details.code || "creator_api_error";
    this.serverCode = /^[a-z0-9_]{3,96}$/u.test(String(details.message || ""))
      ? String(details.message)
      : null;
    this.details = details.details || null;
    this.hint = details.hint || null;
    this.job = details.job && typeof details.job === "object" && !Array.isArray(details.job)
      ? { ...details.job }
      : null;
  }
}

export function normalizeProductResearchPaidAuthorization(value) {
  if (!hasExactObjectKeys(value, PRODUCT_RESEARCH_PAID_AUTHORIZATION_KEYS)) {
    throw new CreatorApiError("Точный тариф платного анализа устарел. Обновите проект и подтвердите его заново.", {
      code: "product_research_paid_authorization_invalid",
    });
  }
  const exactEntriesValid = Object.entries(
    PRODUCT_RESEARCH_PAID_AUTHORIZATION_EXACT,
  ).every(([key, expected]) => value[key] === expected);
  if (
    !exactEntriesValid
  ) {
    throw new CreatorApiError("Точный тариф платного анализа устарел. Обновите проект и подтвердите его заново.", {
      code: "product_research_paid_authorization_invalid",
    });
  }
  // Clone the canonical object whole: the RPC compares all keys and values.
  return JSON.parse(JSON.stringify(value));
}

function productResearchMutationFingerprintPayload(payload) {
  const sanitized = { ...payload };
  const authorization = sanitized.paid_analysis_authorization;
  delete sanitized.paid_analysis_authorization;
  if (authorization) {
    sanitized.paid_analysis_tariff = {
      version: authorization.version,
      provider_key: authorization.provider_key,
      adapter_version: authorization.adapter_version,
      model: authorization.model,
      currency: authorization.currency,
      billing_mode: authorization.billing_mode,
      service_tier: authorization.service_tier,
      input_usd_per_million_tokens:
        authorization.input_usd_per_million_tokens,
      output_usd_per_million_tokens:
        authorization.output_usd_per_million_tokens,
      long_context_threshold_input_tokens:
        authorization.long_context_threshold_input_tokens,
      long_context_input_usd_per_million_tokens:
        authorization.long_context_input_usd_per_million_tokens,
      long_context_output_usd_per_million_tokens:
        authorization.long_context_output_usd_per_million_tokens,
      web_search_usd_per_call: authorization.web_search_usd_per_call,
      max_output_tokens: authorization.max_output_tokens,
      max_provider_attempts: authorization.max_provider_attempts,
      fixed_total: authorization.fixed_total,
    };
  }
  return sanitized;
}

function normalizeManagedAccountInput(value) {
  const source = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const platform = String(source.platform || "").trim().toLowerCase();
  const label = String(source.label || "").trim();
  const handle = String(source.handle || "").trim();
  const url = String(source.url || "").trim();
  const notes = String(source.notes || "").trim();
  if (!/^[a-z0-9][a-z0-9_-]{1,39}$/u.test(platform)) {
    throw new CreatorApiError("Выберите площадку из списка.", {
      code: "admin_account_platform_invalid",
    });
  }
  if (label.length < 2 || label.length > 160 || /[\u0000-\u001f\u007f]/u.test(label)) {
    throw new CreatorApiError("Название аккаунта должно содержать от 2 до 160 символов.", {
      code: "admin_account_label_invalid",
    });
  }
  if (handle.length > 160 || /[\u0000-\u001f\u007f]/u.test(handle)) {
    throw new CreatorApiError("Логин аккаунта имеет неверный формат.", {
      code: "admin_account_handle_invalid",
    });
  }
  if (notes.length > 1000 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(notes)) {
    throw new CreatorApiError("Безопасная заметка слишком длинная или имеет неверный формат.", {
      code: "admin_account_notes_invalid",
    });
  }
  if (url) {
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      parsed = null;
    }
    if (
      !parsed
      || !["https:", "http:"].includes(parsed.protocol)
      || parsed.username
      || parsed.password
      || parsed.href.length > 500
    ) {
      throw new CreatorApiError("Укажите публичную ссылку http или https.", {
        code: "admin_account_url_invalid",
      });
    }
  }
  return {
    platform,
    label,
    handle: handle || null,
    url: url || null,
    notes: notes || null,
  };
}

export class CreatorApi {
  constructor(supabase, config) {
    this.supabase = supabase;
    this.config = config;
    this.rpcClient = supabase.schema(config.RPC_SCHEMA || "public");
    this.organizationId = null;
    this.storageBucket = config.STORAGE_BUCKET;
    this.storagePrefix = null;
    this.mutationKeys = readMutationKeys();
    this.realGenerationClientContexts = new WeakMap();
    this.researchRecomputeInvocations = new Set();
  }

  async call(functionName, payload = {}) {
    const { data, error } = await this.rpcClient.rpc(functionName, { p_payload: payload });

    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }

    if (data && typeof data === "object" && !Array.isArray(data) && data.error) {
      throw new CreatorApiError(toFriendlyMessage(data.error), data.error);
    }

    return data ?? {};
  }

  async callAsExpectedActor(functionName, payload, expectedActorIdValue, {
    isContextCurrent = null,
  } = {}) {
    const expectedActorId = String(expectedActorIdValue || "")
      .trim()
      .toLowerCase();
    if (
      !/^[a-z][a-z0-9_]{2,95}$/u.test(String(functionName || ""))
      || !isUuid(expectedActorId)
    ) {
      throw new CreatorApiError("Не удалось зафиксировать точный контур сотрудника для неизменяемого решения.", {
        code: "auth_session_actor_invalid",
      });
    }
    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = String(sessionData?.session?.access_token || "").trim();
    const actorId = String(sessionData?.session?.user?.id || "")
      .trim()
      .toLowerCase();
    if (sessionError || !accessToken || !isUuid(actorId)) {
      throw new CreatorApiError("Сессия истекла. Войдите снова перед сохранением решения.", {
        code: "auth_session_required",
      });
    }
    if (actorId !== expectedActorId) {
      throw new CreatorApiError("Сессия сотрудника изменилась. Решение не отправлено; откройте ИИ-центр заново.", {
        code: "auth_session_actor_changed",
      });
    }
    if (isContextCurrent !== null) {
      let contextCurrent = false;
      try {
        contextCurrent = typeof isContextCurrent === "function"
          && isContextCurrent() === true;
      } catch {
        contextCurrent = false;
      }
      if (!contextCurrent) {
        throw new CreatorApiError("Контекст решения изменился во время проверки сессии. RPC не отправлен.", {
          code: "auth_session_context_changed",
        });
      }
    }
    const baseUrl = String(this.config?.SUPABASE_URL || "").trim();
    const publishableKey = String(
      this.config?.SUPABASE_PUBLISHABLE_KEY
      || this.config?.SUPABASE_ANON_KEY
      || "",
    ).trim();
    let endpoint;
    try {
      endpoint = new URL(
        `/rest/v1/rpc/${encodeURIComponent(functionName)}`,
        baseUrl,
      );
    } catch {
      endpoint = null;
    }
    if (
      !endpoint
      || endpoint.protocol !== "https:"
      || !/^[a-z0-9-]+\.supabase\.co$/iu.test(endpoint.hostname)
      || !publishableKey
    ) {
      throw new CreatorApiError("Конфигурация защищённого RPC недоступна. Решение не отправлено.", {
        code: "rpc_transport_config_invalid",
      });
    }
    let response;
    try {
      response = await fetch(endpoint, {
        method: "POST",
        headers: {
          apikey: publishableKey,
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
          Accept: "application/json",
          "Content-Profile": String(this.config?.RPC_SCHEMA || "public"),
          "Accept-Profile": String(this.config?.RPC_SCHEMA || "public"),
        },
        body: JSON.stringify({ p_payload: payload || {} }),
      });
    } catch (cause) {
      throw new CreatorApiError("Не удалось связаться с защищённым RPC. Новый запрос решения не отправляйте до восстановления связи.", {
        code: "rpc_request_failed",
        cause,
      });
    }
    let data = null;
    try {
      const body = await response.text();
      data = body ? JSON.parse(body) : null;
    } catch {
      data = null;
    }
    if (!response.ok) {
      const details = data && typeof data === "object" && !Array.isArray(data)
        ? data
        : {
            code: "rpc_request_failed",
            message: `RPC request failed (${response.status})`,
          };
      throw new CreatorApiError(toFriendlyMessage(details), details);
    }
    if (data && typeof data === "object" && !Array.isArray(data) && data.error) {
      throw new CreatorApiError(toFriendlyMessage(data.error), data.error);
    }
    return data ?? {};
  }

  async bootstrap(clientContext = {}) {
    return this.call(RPC.bootstrap, {
      client_version: "supabase-spa-v1",
      ...clientContext,
    });
  }

  commitBootstrapContext(response) {
    const source = response?.data && typeof response.data === "object" ? response.data : response;
    const organizationId =
      source?.organization?.id ??
      source?.membership?.organization_id ??
      source?.organization_id ??
      null;
    const serverBucket = source?.storage?.bucket;
    if (serverBucket && serverBucket !== this.config.STORAGE_BUCKET) {
      throw new CreatorApiError("Защищённое хранилище вернуло неожиданный ответ.", {
        code: "storage_bucket_mismatch",
      });
    }
    const storageBucket = serverBucket || this.config.STORAGE_BUCKET;
    const storagePrefix = source?.storage?.path_prefix || null;

    this.organizationId = organizationId;
    this.storageBucket = storageBucket;
    this.storagePrefix = storagePrefix;
  }

  clearBootstrapContext() {
    this.organizationId = null;
    this.storageBucket = this.config.STORAGE_BUCKET;
    this.storagePrefix = null;
  }

  completeModule(moduleCode) {
    return this.mutate(RPC.completeModule, { module_code: moduleCode });
  }

  submitCourseCheck(moduleCode, answers, rationales = {}) {
    return this.mutate(RPC.submitCourseCheck, {
      module_code: moduleCode,
      answers,
      rationales,
    });
  }

  submitPlatformSimulator({ platformId, assessmentVersion = 1, decisions = {}, rationales = {} }) {
    const platform = String(platformId || "").trim().toLowerCase();
    if (!["instagram", "youtube", "vk"].includes(platform)) {
      throw new CreatorApiError("Выберите Instagram, YouTube или VK.", {
        code: "platform_simulator_platform_invalid",
      });
    }
    return this.mutate(RPC.submitPlatformSimulator, {
      platform,
      assessment_version: Number(assessmentVersion),
      decisions,
      rationales,
    });
  }

  submitExam(answers, rationales) {
    return this.mutate(RPC.submitExam, {
      module_code: "operator_final_exam",
      answers,
      rationales,
    });
  }

  workspaceSection(section, options = {}) {
    const payload = { section };
    const organizationSection = ["team", "feedback"].includes(section);
    const projectId = organizationSection
      ? ""
      : requiredProjectId(options.project_id ?? options.projectId);
    if (!organizationSection) payload.project_id = projectId;
    if (options.page_size !== undefined) {
      const pageSize = Number(options.page_size);
      if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
        throw new CreatorApiError("Можно загрузить от 1 до 100 записей за один запрос.", {
          code: "workspace_page_size_invalid",
        });
      }
      payload.page_size = pageSize;
    }
    if (options.cursor !== undefined) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор истории имеет неверный формат.", {
          code: "workspace_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(
      RPC.workspaceSection,
      this.withOrganization(payload),
    ).then((response) => {
      if (section !== "generation") return response;

      const source = response?.data && typeof response.data === "object"
        ? response.data
        : response;
      const mediaIds = [...new Set(
        (Array.isArray(source?.media) ? source.media : [])
          .map((item) => String(item?.public_id || item?.id || "").trim())
          .filter((mediaId) => isUuid(mediaId)),
      )].slice(0, 100);
      if (!mediaIds.length) return response;

      return this.generationMediaIdentity(mediaIds, { projectId })
        .then((identityResponse) =>
          mergeGenerationMediaIdentity(response, identityResponse)
        )
        .catch((error) => {
          console.warn(
            "Generation media identity unavailable",
            error?.serverCode || error?.code || "",
          );
          return mergeGenerationMediaIdentity(response, { items: [] });
        });
    });
  }

  generationMediaIdentity(mediaIds, {
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
    const normalized = [...new Set(
      (Array.isArray(mediaIds) ? mediaIds : [])
        .map((mediaId) => String(mediaId || "").trim())
        .filter(Boolean),
    )];
    if (
      normalized.length < 1
      || normalized.length > 100
      || normalized.some((mediaId) => !isUuid(mediaId))
    ) {
      throw new CreatorApiError("Не удалось проверить привязку фото к товару.", {
        code: "generation_media_identity_ids_invalid",
      });
    }
    return this.call(RPC.generationMediaIdentity, this.withOrganization({
      media_ids: normalized,
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
  }

  generationLearningPolicy({
    mediaId,
    platform,
    model,
    productCategory,
    projectId = "",
    project_id: projectIdSnake = "",
  }) {
    const normalizedMediaId = String(mediaId || "").trim();
    const normalizedPlatform = String(platform || "").trim().toLowerCase();
    const normalizedModel = String(model || "").trim().toLowerCase();
    const normalizedProductCategory = String(productCategory || "")
      .trim()
      .toLowerCase();
    if (!isUuid(normalizedMediaId)) {
      throw new CreatorApiError("Не удалось определить исходник для самообучения.", {
        code: "generation_learning_policy_media_invalid",
      });
    }
    if (!["instagram", "tiktok", "youtube", "vk", "telegram", "wildberries"].includes(normalizedPlatform)) {
      throw new CreatorApiError("Выберите площадку для подбора обученного ТЗ.", {
        code: "generation_learning_policy_scope_invalid",
      });
    }
    if (!Object.hasOwn(REAL_GENERATION_SKUS, normalizedModel)) {
      throw new CreatorApiError("Выберите режим генерации для обученного ТЗ.", {
        code: "generation_learning_policy_scope_invalid",
      });
    }
    if (
      ![
        "cosmetics",
        "baa",
        "sports_food",
        "food",
        "household",
        "apparel",
        "electronics",
        "other",
      ].includes(normalizedProductCategory)
    ) {
      throw new CreatorApiError("Выберите категорию для отдельного контура обучения.", {
        code: "generation_learning_policy_category_invalid",
      });
    }
    return this.call(RPC.generationLearningPolicy, this.withOrganization({
      media_id: normalizedMediaId,
      platform: normalizedPlatform,
      model: normalizedModel,
      product_category: normalizedProductCategory,
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
  }

  aiLearningControlRoom({ category = "cosmetics" } = {}) {
    const normalizedCategory = String(category || "").trim().toLowerCase();
    if (!AI_PRODUCT_CATEGORY_SET.has(normalizedCategory)) {
      throw new CreatorApiError("Выберите точную товарную категорию ИИ‑центра.", {
        code: "ai_learning_category_invalid",
      });
    }
    return this.call(
      RPC.aiLearningControlRoom,
      this.withOrganization({ product_category: normalizedCategory }),
    );
  }

  aiLearningMarketScopeIndex({ projectId, limit = 50 } = {}) {
    const normalizedLimit = Number(limit);
    if (
      !Number.isSafeInteger(normalizedLimit)
      || normalizedLimit < 1
      || normalizedLimit > 50
    ) {
      throw new CreatorApiError("Проверьте ограничение списка рыночных категорий.", {
        code: "ai_learning_market_scope_index_limit_invalid",
      });
    }
    return this.call(
      RPC.aiLearningMarketScopeIndex,
      this.withOrganization({
        project_id: requiredProjectId(projectId),
        limit: normalizedLimit,
      }),
    );
  }

  registerAiKnowledgeSource(source = {}) {
    const productCategory = String(source.product_category || "")
      .trim()
      .toLowerCase();
    const sourceKind = String(source.source_kind || "").trim().toLowerCase();
    const title = String(source.title || "").replace(/\s+/gu, " ").trim();
    const note = String(source.note || "").replace(/\s+/gu, " ").trim();
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory)) {
      throw new CreatorApiError("Источник должен относиться к одной точной товарной категории.", {
        code: "ai_learning_category_invalid",
      });
    }
    if (!new Set(["link", "file"]).has(sourceKind)) {
      throw new CreatorApiError("Добавьте HTTPS‑ссылку или поддерживаемый файл.", {
        code: "ai_knowledge_source_kind_invalid",
      });
    }
    if (title.length < 2 || title.length > 180 || note.length > 1_000) {
      throw new CreatorApiError("Проверьте название и короткое пояснение к источнику.", {
        code: "ai_knowledge_source_copy_invalid",
      });
    }
    if (source.rights_confirmed !== true) {
      throw new CreatorApiError("Подтвердите право команды использовать источник для обучения.", {
        code: "ai_knowledge_source_rights_required",
      });
    }

    const payload = {
      product_category: productCategory,
      source_kind: sourceKind,
      title,
      note,
      rights_confirmed: true,
    };
    if (sourceKind === "link") {
      const sourceUrl = String(source.source_url || "").trim();
      let parsed;
      try {
        parsed = new URL(sourceUrl);
      } catch {
        parsed = null;
      }
      if (
        !parsed
        || parsed.protocol !== "https:"
        || parsed.username
        || parsed.password
        || sourceUrl.length > 2_048
      ) {
        throw new CreatorApiError("Добавьте публичную HTTPS‑ссылку без логина и пароля.", {
          code: "ai_knowledge_source_url_invalid",
        });
      }
      payload.source_url = parsed.href;
    } else {
      const objectKey = String(source.object_key || "").trim();
      const originalFilename = String(source.original_filename || "").trim();
      const mimeType = String(source.mime_type || "").trim().toLowerCase();
      const sizeBytes = Number(source.size_bytes);
      const sha256 = String(source.sha256 || "").trim().toLowerCase();
      this.assertAiKnowledgeObjectKey(AI_KNOWLEDGE_BUCKET, objectKey);
      if (
        originalFilename.length < 1
        || originalFilename.length > 240
        || !AI_KNOWLEDGE_MIME_TYPES.has(mimeType)
        || !Number.isInteger(sizeBytes)
        || sizeBytes < 1
        || sizeBytes > 25 * 1024 * 1024
        || !/^[0-9a-f]{64}$/u.test(sha256)
      ) {
        throw new CreatorApiError("Файл знаний не прошёл проверку типа, размера или контрольной суммы.", {
          code: "ai_knowledge_source_file_invalid",
        });
      }
      Object.assign(payload, {
        bucket: AI_KNOWLEDGE_BUCKET,
        object_key: objectKey,
        original_filename: originalFilename,
        mime_type: mimeType,
        size_bytes: sizeBytes,
        sha256,
      });
    }
    return this.mutate(RPC.registerAiKnowledgeSource, payload);
  }

  decideAiTeachingCard(input = {}) {
    const productCategory = String(input.product_category || "")
      .trim()
      .toLowerCase();
    const cardId = String(input.card_id || "").trim().toLowerCase();
    const cardHash = String(input.card_hash || "").trim().toLowerCase();
    const decision = String(input.decision || "").trim().toLowerCase();
    const cardVersion = Number(input.card_version);
    const expectedScopeVersion = Number(input.expected_scope_version);
    const reasonCode = String(input.reason_code || "").trim().toLowerCase();
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory)) {
      throw new CreatorApiError("Карточка обратной связи относится к другой категории.", {
        code: "ai_learning_category_invalid",
      });
    }
    if (
      !isUuid(cardId)
      || !/^[0-9a-f]{64}$/u.test(cardHash)
      || !["approve", "reject"].includes(decision)
      || !Number.isInteger(cardVersion)
      || cardVersion < 1
      || !Number.isInteger(expectedScopeVersion)
      || expectedScopeVersion < 0
      || !["operator_confirmed", "operator_rejected"].includes(reasonCode)
      || input.confirmation !== true
    ) {
      throw new CreatorApiError("Карточка изменилась. Обновите ИИ‑центр и повторите решение.", {
        code: "ai_teaching_decision_invalid",
      });
    }
    return this.mutate(RPC.decideAiTeachingCard, {
      product_category: productCategory,
      card_id: cardId,
      card_hash: cardHash,
      card_version: cardVersion,
      expected_scope_version: expectedScopeVersion,
      decision,
      reason_code: reasonCode,
      confirmation: true,
    });
  }

  decideAiHistoricalCase(input = {}) {
    const productCategory = String(input.product_category || "")
      .trim()
      .toLowerCase();
    const caseId = String(input.case_id || "").trim().toLowerCase();
    const eventId = String(input.event_id || "").trim().toLowerCase();
    const decision = String(input.decision || "").trim().toLowerCase();
    const expectedScopeVersion = Number(input.expected_scope_version);
    const expectedEventCursor = Number(input.expected_event_cursor);
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory)) {
      throw new CreatorApiError("Исторический кейс относится к другой товарной категории.", {
        code: "ai_historical_case_category_invalid",
      });
    }
    if (
      !isUuid(caseId)
      || !isUuid(eventId)
      || !["confirm", "reject"].includes(decision)
      || !Number.isSafeInteger(expectedScopeVersion)
      || expectedScopeVersion < 0
      || !Number.isSafeInteger(expectedEventCursor)
      || expectedEventCursor < 1
      || input.confirmation !== true
    ) {
      throw new CreatorApiError("Кейс изменился. Обновите ИИ‑центр и повторите решение.", {
        code: "ai_historical_case_decision_invalid",
      });
    }
    return this.mutate(RPC.decideAiHistoricalCase, {
      product_category: productCategory,
      case_id: caseId,
      event_id: eventId,
      expected_scope_version: expectedScopeVersion,
      expected_event_cursor: expectedEventCursor,
      decision,
      confirmation: true,
    });
  }

  decideAiResearchReceipt(input = {}) {
    const productCategory = String(input.product_category || "")
      .trim()
      .toLowerCase();
    const receiptId = String(input.receipt_id || "").trim().toLowerCase();
    const receiptHash = String(input.receipt_hash || "").trim().toLowerCase();
    const decision = String(input.decision || "").trim().toLowerCase();
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory)) {
      throw new CreatorApiError("Исследование относится к другой товарной категории. Обновите ИИ-центр.", {
        code: "ai_research_receipt_category_invalid",
      });
    }
    if (
      !isUuid(receiptId)
      || !/^[0-9a-f]{64}$/u.test(receiptHash)
      || !["approve", "reject"].includes(decision)
      || input.confirmation !== true
    ) {
      throw new CreatorApiError("Запись исследования изменилась. Обновите ИИ-центр и повторите решение.", {
        code: "ai_research_receipt_decision_invalid",
      });
    }
    return this.mutate(RPC.decideAiResearchReceipt, {
      product_category: productCategory,
      receipt_id: receiptId,
      receipt_hash: receiptHash,
      decision,
      confirmation: true,
    });
  }

  async invokeAiHistoricalCaseImport(input = {}) {
    const productCategory = String(input.product_category || "")
      .trim()
      .toLowerCase();
    const sourceId = String(input.source_id || "").trim().toLowerCase();
    const adapter = String(input.adapter || "auto").trim().toLowerCase();
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory) || !isUuid(sourceId)) {
      throw new CreatorApiError("Не удалось связать таблицу с категорией и журналом источников.", {
        code: "ai_historical_case_import_scope_invalid",
      });
    }
    if (!["auto", "harley_effect_content_v1", "qeep_funnel_v1", "canonical_v1"].includes(adapter)) {
      throw new CreatorApiError("Не удалось выбрать безопасный адаптер таблицы.", {
        code: "ai_historical_case_import_adapter_invalid",
      });
    }
    const scopedPayload = this.withOrganization({
      action: "parse_and_import",
      product_category: productCategory,
      source_id: sourceId,
      adapter,
      commit: true,
    });
    const fingerprint = `${AI_HISTORICAL_CASE_IMPORT_FUNCTION}:${stableStringify(scopedPayload)}`;
    const requestedIdempotencyKey = String(input.idempotency_key || "")
      .trim()
      .toLowerCase();
    if (requestedIdempotencyKey && !isUuid(requestedIdempotencyKey)) {
      throw new CreatorApiError("Ключ безопасного повтора разбора повреждён.", {
        code: "ai_historical_case_import_idempotency_invalid",
      });
    }
    const idempotencyKey = requestedIdempotencyKey
      || this.mutationKeys[fingerprint]
      || crypto.randomUUID();
    this.mutationKeys[fingerprint] = idempotencyKey;
    writeMutationKeys(this.mutationKeys);

    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла перед разбором таблицы.", {
        code: "auth_session_required",
      });
    }
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(
        AI_HISTORICAL_CASE_IMPORT_FUNCTION,
        {
          body: { ...scopedPayload, idempotency_key: idempotencyKey },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      ));
    } catch {
      throw new CreatorApiError("Источник сохранён, но сервис разбора таблиц сейчас недоступен. Повторите разбор — файл загружать заново не нужно.", {
        code: "ai_historical_case_import_unavailable",
      });
    }
    if (error) {
      throw new CreatorApiError("Источник сохранён, но разбор таблицы не завершён. Повторите разбор без новой загрузки.", {
        code: error?.code || "ai_historical_case_import_failed",
        message: error?.message,
      });
    }
    const response = data?.data && typeof data.data === "object" && !Array.isArray(data.data)
      ? data.data
      : data;
    const rawStatus = String(
      response?.batch?.status || response?.batch?.import_status
        || response?.status || response?.import_status || "",
    ).trim().toLowerCase();
    const responseStatus = String(
      response?.status || response?.import_status || "",
    ).trim().toLowerCase();
    const status = ({
      pending: "queued",
      in_progress: "processing",
      parsing: "processing",
      importing: "processing",
      imported: "completed",
      done: "completed",
      completed_with_quarantine: "completed",
      quarantined: "completed",
      parser_rejected: "failed",
      parser_rejected_all: "failed",
    })[rawStatus] || rawStatus;
    const persistedParserRejection = response?.ok === false
      && responseStatus === "parser_rejected_all"
      && response?.retryable === true
      && response?.batch_persisted === true
      && response?.batch
      && typeof response.batch === "object"
      && !Array.isArray(response.batch)
      && response?.snapshot
      && typeof response.snapshot === "object"
      && !Array.isArray(response.snapshot);
    if (
      !response
      || typeof response !== "object"
      || Array.isArray(response)
      || (
        !persistedParserRejection
        && (
          response.ok === false
          || response.error
          || !["queued", "processing", "completed"].includes(status)
        )
      )
    ) {
      throw new CreatorApiError("Сервис разбора вернул неполный статус. Источник сохранён; повторите разбор позже.", {
        code: "ai_historical_case_import_response_invalid",
      });
    }
    delete this.mutationKeys[fingerprint];
    writeMutationKeys(this.mutationKeys);
    return response;
  }


  generationRepairPolicy(reviewId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedReviewId = String(reviewId || "").trim();
    if (!isUuid(normalizedReviewId)) {
      throw new CreatorApiError("Не удалось определить проверку для исправления.", {
        code: "generation_repair_review_invalid",
      });
    }
    return this.call(RPC.generationRepairPolicy, this.withOrganization({
      review_id: normalizedReviewId,
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
  }

  generationSpecStatus(context = {}) {
    return this.call(
      RPC.generationSpecStatus,
      this.withOrganization({
        ...normalizeGenerationSpecReference({
          spec_id: context.spec_id,
          spec_version: context.spec_version,
          spec_hash: context.spec_hash,
        }),
        project_id: requiredProjectId(context.project_id || context.projectId),
      }),
    );
  }

  prepareGenerationSpec(input = {}) {
    const exactScope = normalizeGenerationSpecScopeInput(input.exact_scope);
    const editableIntent = String(input.editable_intent || "").trim();
    const proposedPrompt = String(input.proposed_prompt || "").trim();
    const reason = String(input.reason || "").trim();
    if (
      editableIntent.length < 1
      || editableIntent.length > 1_200
      || proposedPrompt.length < 1
      || proposedPrompt.length > 1_200
      || reason.length < 3
      || reason.length > 500
      || input.confirmation !== true
    ) {
      throw new CreatorApiError("Проверьте замысел и подготовленное ТЗ перед сохранением версии.", {
        code: "generation_spec_prepare_payload_invalid",
      });
    }
    return this.mutate(RPC.prepareGenerationSpec, {
      project_id: requiredProjectId(input.project_id || input.projectId),
      exact_scope: exactScope,
      editable_intent: editableIntent,
      proposed_prompt: proposedPrompt,
      learning_context: normalizeGenerationSpecLearningContext(
        input.learning_context,
      ),
      repair_context: normalizeGenerationSpecRepairContext(
        input.repair_context,
      ),
      research_provenance: normalizeGenerationSpecResearchProvenance(
        input.research_provenance,
      ),
      performance_policy_provenance:
        normalizeGenerationSpecPerformanceProvenance(
          input.performance_policy_provenance,
        ),
      repair_provenance: normalizeGenerationSpecRepairProvenance(
        input.repair_provenance,
      ),
      ...(input.outcome_selection_id
        ? { outcome_selection_id: requireGenerationSpecUuid(
            input.outcome_selection_id,
            "generation_spec_outcome_selection_invalid",
          ) }
        : {}),
      confirmation: true,
      reason,
    });
  }

  prepareGenerationStrategySpec(request = {}) {
    assertGenerationStrategySpecPrepareRequest(request, this.organizationId);
    return this.call(RPC.prepareGenerationStrategySpec, request);
  }

  controlGenerationSpec(input = {}) {
    const reference = normalizeGenerationSpecReference({
      spec_id: input.spec_id,
      spec_version: input.expected_spec_version,
      spec_hash: input.expected_spec_hash,
    });
    const action = String(input.action || "").trim().toLowerCase();
    const reason = String(input.reason || "").trim();
    if (
      !["patch", "approve", "reject", "revert", "recompute"].includes(action)
      || input.confirmation !== true
      || reason.length < 3
      || reason.length > 500
    ) {
      throw new CreatorApiError("Действие с версией ТЗ заполнено не полностью.", {
        code: "generation_spec_control_payload_invalid",
      });
    }
    const payload = {
      project_id: requiredProjectId(input.project_id || input.projectId),
      spec_id: reference.spec_id,
      expected_spec_version: reference.spec_version,
      expected_spec_hash: reference.spec_hash,
      action,
      confirmation: true,
      reason,
    };
    if (action === "patch") {
      payload.patch = normalizeGenerationSpecPatch(input.patch);
    }
    if (action === "revert") {
      const target = Number(input.target_spec_version);
      if (!Number.isInteger(target) || target < 1 || target >= reference.spec_version) {
        throw new CreatorApiError("Выберите существующую прошлую версию ТЗ.", {
          code: "generation_spec_revert_target_invalid",
        });
      }
      payload.target_spec_version = target;
    }
    return this.mutate(RPC.controlGenerationSpec, payload);
  }

  generationSpecEffectivePolicy(context = {}) {
    return this.call(
      RPC.generationSpecEffectivePolicy,
      this.withOrganization({
        ...normalizeGenerationSpecReference({
          spec_id: context.spec_id,
          spec_version: context.spec_version,
          spec_hash: context.spec_hash,
        }),
        project_id: requiredProjectId(context.project_id || context.projectId),
      }),
    );
  }

  bindGenerationSpecAiResearch(input = {}) {
    const reference = normalizeGenerationSpecReference({
      spec_id: input.spec_id,
      spec_version: input.spec_version,
      spec_hash: input.spec_hash,
    });
    const recommendationPosition = Number(input.recommendation_position);
    if (
      !Number.isInteger(recommendationPosition)
      || recommendationPosition < 1
      || recommendationPosition > 3
      || input.confirmation !== true
    ) {
      throw new CreatorApiError(
        "Не удалось подтвердить выбранную рекомендацию ИИ‑центра.",
        { code: "generation_spec_ai_research_binding_payload_invalid" },
      );
    }
    return this.call(
      RPC.bindGenerationSpecAiResearch,
      this.withOrganization({
        project_id: requiredProjectId(input.project_id || input.projectId),
        ...reference,
        selection_id: requireGenerationSpecUuid(
          input.selection_id,
          "generation_spec_ai_research_binding_payload_invalid",
        ),
        recommendation_position: recommendationPosition,
        confirmation: true,
      }),
    );
  }

  generationSpecAiResearchBinding(context = {}) {
    return this.call(
      RPC.generationSpecAiResearchBinding,
      this.withOrganization({
        project_id: requiredProjectId(
          context.project_id || context.projectId,
        ),
        ...normalizeGenerationSpecReference({
          spec_id: context.spec_id,
          spec_version: context.spec_version,
          spec_hash: context.spec_hash,
        }),
      }),
    );
  }

  generationResearchRecommendation(input = {}) {
    const recommendationPosition = Number(input.recommendation_position);
    if (![1, 2, 3].includes(recommendationPosition)) {
      throw new CreatorApiError(
        "Выбранный вариант рекомендации имеет неверную позицию.",
        { code: "generation_research_recommendation_payload_invalid" },
      );
    }
    return this.call(
      RPC.generationResearchRecommendation,
      this.withOrganization({
        project_id: requiredProjectId(input.project_id || input.projectId),
        selection_id: requireGenerationSpecUuid(
          input.selection_id,
          "generation_research_recommendation_payload_invalid",
        ),
        recommendation_position: recommendationPosition,
      }),
    );
  }

  generationAiResearchWorkingDraft(input = {}) {
    const action = String(input.action || "read").trim().toLowerCase();
    if (!["read", "save", "clear"].includes(action)) {
      throw new CreatorApiError(
        "Не удалось определить действие с общим черновиком.",
        { code: "generation_ai_research_working_draft_payload_invalid" },
      );
    }
    const payload = {
      project_id: requiredProjectId(input.project_id || input.projectId),
      action,
    };
    if (action === "read") {
      return this.call(
        RPC.generationAiResearchWorkingDraft,
        this.withOrganization(payload),
      );
    }
    const expectedRevision = Number(input.expected_revision);
    const mutationId = String(input.mutation_id || "").trim().toLowerCase();
    if (
      !Number.isSafeInteger(expectedRevision)
      || expectedRevision < 0
      || !isUuid(mutationId)
    ) {
      throw new CreatorApiError(
        "Общий черновик изменился или имеет неверную версию.",
        { code: "generation_ai_research_working_draft_payload_invalid" },
      );
    }
    Object.assign(payload, {
      expected_revision: expectedRevision,
      mutation_id: mutationId,
    });
    if (action === "clear") {
      return this.call(
        RPC.generationAiResearchWorkingDraft,
        this.withOrganization(payload),
      );
    }
    const position = Number(input.recommendation_position);
    if (![1, 2, 3].includes(position)) {
      throw new CreatorApiError(
        "Выбранный вариант рекомендации имеет неверную позицию.",
        { code: "generation_ai_research_working_draft_payload_invalid" },
      );
    }
    Object.assign(payload, {
      selection_id: requireGenerationSpecUuid(
        input.selection_id,
        "generation_ai_research_working_draft_payload_invalid",
      ),
      recommendation_position: position,
      editable_fields: input.editable_fields,
      applied_fields: input.applied_fields,
      touched_fields: input.touched_fields,
      previous_values: input.previous_values,
      last_applied_values: input.last_applied_values,
      auto_apply_disabled: input.auto_apply_disabled === true,
    });
    return this.call(
      RPC.generationAiResearchWorkingDraft,
      this.withOrganization(payload),
    );
  }

  bindGenerationSpecVideoReference(input = {}) {
    const reference = normalizeGenerationSpecReference(input);
    const videoId = String(input.video_id || "").trim();
    const canonicalUrl = String(input.canonical_url || "").trim();
    const mechanicsSummary = String(input.mechanics_summary || "")
      .replace(/\s+/gu, " ").trim();
    if (
      !/^[A-Za-z0-9_-]{11}$/u.test(videoId)
      || canonicalUrl !== `https://youtube.com/watch?v=${videoId}`
      || mechanicsSummary.length < 20
      || mechanicsSummary.length > 360
      || /(?:https?:\/\/|www\.|youtube(?:-nocookie)?\.com|youtu\.be)/iu
        .test(mechanicsSummary)
      || input.source_access_confirmed !== true
      || input.transformative_use_confirmed !== true
      || input.confirmation !== true
    ) {
      throw new CreatorApiError(
        "Проверьте видеореференс, описание механики и два подтверждения.",
        { code: "generation_video_reference_binding_payload_invalid" },
      );
    }
    return this.call(
      RPC.bindGenerationSpecVideoReference,
      this.withOrganization({
        project_id: requiredProjectId(input.project_id || input.projectId),
        ...reference,
        video_id: videoId,
        canonical_url: canonicalUrl,
        mechanics_summary: mechanicsSummary,
        source_access_confirmed: true,
        transformative_use_confirmed: true,
        attestation_version: "generation-video-reference-v1",
        confirmation: true,
      }),
    );
  }

  generationVideoReferenceLineage(input = {}) {
    const projectId = requiredProjectId(input.project_id || input.projectId);
    if (input.generation_job_id) {
      return this.call(
        RPC.generationVideoReferenceLineage,
        this.withOrganization({
          project_id: projectId,
          generation_job_id: requireGenerationSpecUuid(
            input.generation_job_id,
            "generation_video_reference_lineage_payload_invalid",
          ),
        }),
      );
    }
    return this.call(
      RPC.generationVideoReferenceLineage,
      this.withOrganization({
        project_id: projectId,
        ...normalizeGenerationSpecReference(input),
      }),
    );
  }

  savePracticalProject(payload) {
    return this.mutate(RPC.savePracticalProject, payload);
  }

  decidePracticalProject(payload) {
    return this.mutate(RPC.decidePracticalProject, payload);
  }

  generationArchive(options = {}) {
    const periods = new Set(["week", "4w", "12w", "all"]);
    const statuses = new Set(["all", "active", "ready", "issue"]);
    const providers = new Set(["all", "runway", "google", "fal"]);
    const strategies = new Set([
      "all",
      "viral_avatar_ugc",
      "viral_product_swap",
      "viral_rebuild",
    ]);
    const contentKinds = new Set(["all", "video", "photo"]);
    const selectionSources = new Set([
      "all",
      "system_recommendation",
      "research_recommendation",
      "performance_recommendation",
      "manual_choice",
      "alternative_after_block",
    ]);
    const qualityStatuses = new Set(["all", "accepted", "needs_revalidation", "unproven"]);
    const period = String(options.period || "4w").trim().toLowerCase();
    const status = String(options.status || "all").trim().toLowerCase();
    const provider = String(options.provider || "all").trim().toLowerCase();
    const model = String(options.model || "all").trim().toLowerCase();
    const strategyId = String(
      options.strategy_id ?? options.strategyId ?? "all",
    ).trim().toLowerCase();
    const contentKind = String(options.content_kind ?? options.contentKind ?? "all").trim().toLowerCase();
    const selectionSource = String(options.selection_source ?? options.selectionSource ?? "all").trim().toLowerCase();
    const qualityStatus = String(options.quality_status ?? options.qualityStatus ?? "all").trim().toLowerCase();
    const query = String(options.query || "").trim();
    const pageSize = options.page_size === undefined ? 50 : Number(options.page_size);
    if (!periods.has(period)) {
      throw new CreatorApiError("Выберите доступный период архива.", {
        code: "generation_archive_period_invalid",
      });
    }
    if (!statuses.has(status)) {
      throw new CreatorApiError("Выберите доступную группу статусов.", {
        code: "generation_archive_status_invalid",
      });
    }
    if (!providers.has(provider)) {
      throw new CreatorApiError("Выберите доступного поставщика ИИ.", {
        code: "generation_archive_provider_invalid",
      });
    }
    if (model !== "all" && !/^[a-z0-9][a-z0-9._-]{0,79}$/u.test(model)) {
      throw new CreatorApiError("Выберите доступную модель генерации.", {
        code: "generation_archive_model_invalid",
      });
    }
    if (!strategies.has(strategyId)) {
      throw new CreatorApiError("Выберите доступную стратегию генерации.", {
        code: "generation_archive_strategy_id_invalid",
      });
    }
    if (!contentKinds.has(contentKind)) {
      throw new CreatorApiError("Выберите фото или видео.", {
        code: "generation_archive_content_kind_invalid",
      });
    }
    if (!selectionSources.has(selectionSource)) {
      throw new CreatorApiError("Выберите источник решения о модели.", {
        code: "generation_archive_selection_source_invalid",
      });
    }
    if (!qualityStatuses.has(qualityStatus)) {
      throw new CreatorApiError("Выберите статус качества модели.", {
        code: "generation_archive_quality_status_invalid",
      });
    }
    if (query.length > 120 || /[\u0000-\u001f\u007f]/u.test(query)) {
      throw new CreatorApiError("Сократите поиск до 120 символов.", {
        code: "generation_archive_query_invalid",
      });
    }
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Можно загрузить от 1 до 100 запусков за один запрос.", {
        code: "generation_archive_page_size_invalid",
      });
    }
    const payload = {
      period,
      status,
      page_size: pageSize,
    };
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    payload.project_id = projectId;
    if (query) payload.query = query;
    if (provider !== "all") payload.provider = provider;
    if (model !== "all") payload.model = model;
    if (strategyId !== "all") payload.strategy_id = strategyId;
    if (contentKind !== "all") payload.content_kind = contentKind;
    if (selectionSource !== "all") payload.selection_source = selectionSource;
    if (qualityStatus !== "all") payload.quality_status = qualityStatus;
    if (options.cursor !== undefined && options.cursor !== null) {
      const cursor = options.cursor;
      if (
        !cursor
        || typeof cursor !== "object"
        || Array.isArray(cursor)
        || Object.keys(cursor).some((key) => !["at", "id"].includes(key))
        || !String(cursor.at || "").trim()
        || !String(cursor.id || "").trim()
      ) {
        throw new CreatorApiError("Курсор архива имеет неверный формат.", {
          code: "generation_archive_cursor_invalid",
        });
      }
      payload.cursor = {
        at: String(cursor.at).trim(),
        id: String(cursor.id).trim(),
      };
    }
    return this.call(RPC.generationArchive, this.withOrganization(payload));
  }

  generationStrategyRepeatData(generationJobId, options = {}) {
    const normalizedJobId = String(generationJobId || "").trim().toLowerCase();
    if (!isUuid(normalizedJobId)) {
      throw new CreatorApiError("Не удалось определить исходный запуск стратегии.", {
        code: "generation_strategy_repeat_job_invalid",
      });
    }
    return this.call(
      RPC.generationStrategyRepeatData,
      this.withOrganization({
        version: "generation-strategy-repeat-request-v1",
        project_id: requiredProjectId(
          options.project_id ?? options.projectId,
        ),
        generation_job_id: normalizedJobId,
      }),
    );
  }

  generationStrategyAssetCandidates(options = {}) {
    const projectId = requiredProjectId(
      options.project_id ?? options.projectId,
    );
    const kind = String(options.kind || "all").trim().toLowerCase();
    if (![
      "all",
      "product_photo",
      "packshot",
      "creator_reference",
      "source_video",
    ].includes(kind)) {
      throw new CreatorApiError("Неизвестный тип исходника стратегии.", {
        code: "generation_strategy_asset_kind_invalid",
      });
    }
    const productIdSource = options.product_id ?? options.productId;
    const productId = productIdSource === undefined || productIdSource === null
      || String(productIdSource).trim() === ""
      ? null
      : String(productIdSource).trim().toLowerCase();
    if (productId !== null && !isUuid(productId)) {
      throw new CreatorApiError("Не удалось определить точный товар для исходников.", {
        code: "generation_strategy_asset_product_invalid",
      });
    }
    const pageSizeSource = options.page_size ?? options.pageSize ?? 50;
    const pageSize = Number(pageSizeSource);
    if (!Number.isSafeInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Размер страницы исходников имеет неверный формат.", {
        code: "generation_strategy_asset_page_size_invalid",
      });
    }
    const payload = {
      version: "generation-strategy-asset-candidates-request-v1",
      project_id: projectId,
      kind,
      page_size: pageSize,
      ...(productId ? { product_id: productId } : {}),
    };
    if (options.cursor !== undefined && options.cursor !== null) {
      const cursor = options.cursor;
      const cursorAt = String(cursor?.at || "").trim();
      const cursorId = String(cursor?.id || "").trim().toLowerCase();
      if (
        !cursor
        || typeof cursor !== "object"
        || Array.isArray(cursor)
        || Object.keys(cursor).length !== 2
        || !Object.hasOwn(cursor, "at")
        || !Object.hasOwn(cursor, "id")
        || !Number.isFinite(Date.parse(cursorAt))
        || !isUuid(cursorId)
      ) {
        throw new CreatorApiError("Курсор исходников имеет неверный формат.", {
          code: "generation_strategy_asset_cursor_invalid",
        });
      }
      payload.cursor = { at: cursorAt, id: cursorId };
    }
    return this.call(
      RPC.generationStrategyAssetCandidates,
      this.withOrganization(payload),
    );
  }

  archiveGenerationBatch(batchId, options = {}) {
    const normalizedBatchId = String(batchId || "").trim().toLowerCase();
    if (!isUuid(normalizedBatchId)) {
      throw new CreatorApiError("Не удалось определить запуск.", {
        code: "generation_batch_id_invalid",
      });
    }
    return this.mutate(
      RPC.archiveGenerationBatch,
      this.withOrganization({
        project_id: requiredProjectId(
          options.project_id ?? options.projectId,
        ),
        batch_id: normalizedBatchId,
        confirmation: options.confirmation === true,
      }),
    );
  }

  workspaceBrowser(options = {}) {
    const payload = {};
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    payload.project_id = projectId;
    if (
      Object.prototype.hasOwnProperty.call(options, "folder_id")
      || Object.prototype.hasOwnProperty.call(options, "folderId")
    ) {
      const folderId = options.folder_id ?? options.folderId;
      payload.folder_id = folderId && folderId !== "root" ? String(folderId) : null;
    }
    if (options.page_size !== undefined) {
      const pageSize = Number(options.page_size);
      if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
        throw new CreatorApiError("Можно загрузить от 1 до 100 объектов за один запрос.", {
          code: "workspace_page_size_invalid",
        });
      }
      payload.page_size = pageSize;
    }
    if (options.search !== undefined) {
      const search = String(options.search || "").trim();
      if (search.length > 120 || /[\u0000-\u001f\u007f]/u.test(search)) {
        throw new CreatorApiError("Сократите запрос поиска до 120 символов.", {
          code: "workspace_search_invalid",
        });
      }
      if (search) payload.search = search;
    }
    if (options.entity_types !== undefined) {
      const supported = new Set(["media", "task"]);
      if (
        !Array.isArray(options.entity_types)
        || options.entity_types.length < 1
        || options.entity_types.length > 2
        || options.entity_types.some((type) => !supported.has(String(type)))
      ) {
        throw new CreatorApiError("Выберите материалы, задачи или оба типа объектов.", {
          code: "workspace_entity_types_invalid",
        });
      }
      payload.entity_types = [...new Set(options.entity_types.map(String))];
    }
    if (options.artifact_classes !== undefined) {
      const supported = new Set(["source", "generated_output", "unclassified"]);
      if (
        !Array.isArray(options.artifact_classes)
        || options.artifact_classes.length < 1
        || options.artifact_classes.length > 3
        || options.artifact_classes.some((value) => !supported.has(String(value)))
      ) {
        throw new CreatorApiError("Выберите источники, результаты или неклассифицированные материалы.", {
          code: "workspace_artifact_classes_invalid",
        });
      }
      payload.artifact_classes = [...new Set(options.artifact_classes.map(String))];
    }
    if (options.cursor !== undefined) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор рабочего пространства имеет неверный формат.", {
          code: "workspace_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(RPC.workspaceBrowser, this.withOrganization(payload));
  }

  createWorkspaceFolder({
    name,
    parentId = null,
    colorToken = "emerald",
    projectId = "",
    project_id: projectIdSnake = "",
  }) {
    const folderName = String(name || "").trim();
    const color = String(colorToken || "emerald").trim().toLowerCase();
    if (!folderName || folderName.length > 120 || /[\u0000-\u001f\u007f]/u.test(folderName)) {
      throw new CreatorApiError("Укажите название папки длиной до 120 символов.", {
        code: "workspace_folder_name_invalid",
      });
    }
    if (!["emerald", "gold", "rose", "blue", "violet", "slate"].includes(color)) {
      throw new CreatorApiError("Выберите доступный цвет папки.", {
        code: "workspace_folder_color_invalid",
      });
    }
    return this.mutate(RPC.createWorkspaceFolder, {
      project_id: requiredProjectId(projectIdSnake || projectId),
      name: folderName,
      parent_id: parentId || null,
      color_token: color,
    });
  }

  projectFlow({ projectId = "", project_id: projectIdSnake = "", includeProjects = true } = {}) {
    const normalizedProjectId = optionalProjectId(projectIdSnake || projectId);
    if (typeof includeProjects !== "boolean") {
      throw new CreatorApiError("Не удалось определить состав списка проектов.", {
        code: "project_flow_include_projects_invalid",
      });
    }
    return this.call(RPC.projectFlow, this.withOrganization({
      ...(normalizedProjectId ? { project_id: normalizedProjectId } : {}),
      ...(includeProjects === false ? { include_projects: false } : {}),
    }));
  }

  projectMembers({ projectId = "", project_id: projectIdSnake = "" } = {}) {
    return this.call(RPC.projectMembers, this.withOrganization({
      project_id: requiredProjectId(projectIdSnake || projectId),
    }));
  }

  grantProjectMember(
    profileId,
    { projectId = "", project_id: projectIdSnake = "" } = {},
  ) {
    const normalizedProfileId = String(profileId || "").trim().toLowerCase();
    if (!isUuid(normalizedProfileId)) {
      throw new CreatorApiError("Не удалось определить участника команды.", {
        code: "project_member_profile_id_invalid",
      });
    }
    return this.mutate(RPC.grantProjectMember, {
      project_id: requiredProjectId(projectIdSnake || projectId),
      profile_id: normalizedProfileId,
    });
  }

  revokeProjectMember(
    profileId,
    { projectId = "", project_id: projectIdSnake = "" } = {},
  ) {
    const normalizedProfileId = String(profileId || "").trim().toLowerCase();
    if (!isUuid(normalizedProfileId)) {
      throw new CreatorApiError("Не удалось определить участника команды.", {
        code: "project_member_profile_id_invalid",
      });
    }
    return this.mutate(RPC.revokeProjectMember, {
      project_id: requiredProjectId(projectIdSnake || projectId),
      profile_id: normalizedProfileId,
    });
  }

  projectMedia(
    mediaId,
    {
      projectId = "",
      project_id: projectIdSnake = "",
      surface = "",
    } = {},
  ) {
    const normalizedMediaId = String(mediaId || "").trim().toLowerCase();
    const normalizedSurface = String(surface || "").trim().toLowerCase();
    if (!isUuid(normalizedMediaId)) {
      throw new CreatorApiError("Некорректная ссылка на материал.", {
        code: "project_media_id_invalid",
      });
    }
    if (!["generation", "review", "files"].includes(normalizedSurface)) {
      throw new CreatorApiError("Некорректный раздел материала.", {
        code: "project_media_surface_invalid",
      });
    }
    return this.call(RPC.projectMedia, this.withOrganization({
      project_id: requiredProjectId(projectIdSnake || projectId),
      media_id: normalizedMediaId,
      surface: normalizedSurface,
    }));
  }

  projectPlacement(
    placementId,
    { projectId = "", project_id: projectIdSnake = "" } = {},
  ) {
    const normalizedPlacementId = String(placementId || "").trim().toLowerCase();
    if (!isUuid(normalizedPlacementId)) {
      throw new CreatorApiError("Некорректная ссылка на публикацию.", {
        code: "project_placement_id_invalid",
      });
    }
    return this.call(RPC.projectPlacement, this.withOrganization({
      project_id: requiredProjectId(projectIdSnake || projectId),
      placement_id: normalizedPlacementId,
    }));
  }

  createProject({ name, colorToken = "emerald", color_token: colorTokenSnake = "" } = {}) {
    const projectName = String(name || "").trim();
    const color = String(colorTokenSnake || colorToken || "emerald").trim().toLowerCase();
    if (!projectName || projectName.length > 120 || /[\u0000-\u001f\u007f]/u.test(projectName)) {
      throw new CreatorApiError("Укажите название проекта длиной до 120 символов.", {
        code: "workspace_project_name_invalid",
      });
    }
    if (!["emerald", "gold", "rose", "blue", "violet", "slate"].includes(color)) {
      throw new CreatorApiError("Выберите доступный цвет проекта.", {
        code: "workspace_project_color_invalid",
      });
    }
    return this.mutate(RPC.createProject, {
      name: projectName,
      color_token: color,
    });
  }

  archiveProject(projectId, expectedVersion) {
    const normalizedProjectId = requiredProjectId(projectId);
    const normalizedVersion = Number(expectedVersion);
    if (!Number.isInteger(normalizedVersion) || normalizedVersion < 1) {
      throw new CreatorApiError("Проект изменился. Обновите Finder и повторите действие.", {
        code: "workspace_project_version_invalid",
      });
    }
    return this.mutate(RPC.archiveProject, {
      project_id: normalizedProjectId,
      expected_version: normalizedVersion,
    });
  }

  requestWorkspaceAccess() {
    return this.mutate(RPC.requestWorkspaceAccess, {});
  }

  updateWorkspaceFolder(folderId, changes = {}) {
    const expectedVersion = Number(changes.expectedVersion);
    if (!folderId || !Number.isInteger(expectedVersion) || expectedVersion < 1) {
      throw new CreatorApiError("Папка изменилась. Обновите рабочий стол и повторите действие.", {
        code: "workspace_folder_version_invalid",
      });
    }
    const payload = {
      project_id: requiredProjectId(changes.project_id || changes.projectId),
      folder_id: String(folderId),
      expected_version: expectedVersion,
    };
    if (changes.name !== undefined) {
      const name = String(changes.name || "").trim();
      if (!name || name.length > 120 || /[\u0000-\u001f\u007f]/u.test(name)) {
        throw new CreatorApiError("Укажите название папки длиной до 120 символов.", {
          code: "workspace_folder_name_invalid",
        });
      }
      payload.name = name;
    }
    if (Object.prototype.hasOwnProperty.call(changes, "parentId")) {
      payload.parent_id = changes.parentId || null;
    }
    if (changes.colorToken !== undefined) {
      payload.color_token = String(changes.colorToken || "").trim().toLowerCase();
    }
    if (changes.archive === true) payload.archive = true;
    if (Object.keys(payload).length === 3) {
      throw new CreatorApiError("Выберите изменение папки.", {
        code: "workspace_folder_update_payload_invalid",
      });
    }
    return this.mutate(RPC.updateWorkspaceFolder, payload);
  }

  moveWorkspaceItems(items, destinationFolderId = null, scope = {}) {
    const normalized = Array.isArray(items)
      ? items.map((item) => ({
          type: String(item?.type || ""),
          id: String(item?.id || ""),
        }))
      : [];
    if (
      normalized.length < 1
      || normalized.length > 100
      || normalized.some((item) => !["media", "task"].includes(item.type) || !item.id)
    ) {
      throw new CreatorApiError("Выберите от 1 до 100 доступных материалов или задач.", {
        code: "workspace_items_invalid",
      });
    }
    return this.mutate(RPC.moveWorkspaceItems, {
      project_id: requiredProjectId(scope.project_id || scope.projectId),
      destination_folder_id: destinationFolderId || null,
      items: normalized,
    });
  }

  inviteAttempts() {
    return this.call(RPC.inviteAttempts, this.withOrganization({}));
  }

  adminSnapshot() {
    return this.call(RPC.adminSnapshot, this.withOrganization({}));
  }

  adminMemberAction(action, { profileId, reason } = {}) {
    const normalizedAction = String(action || "").trim().toLowerCase();
    const normalizedProfileId = String(profileId || "").trim().toLowerCase();
    const normalizedReason = String(reason || "").trim();
    if (!new Set(["suspend_member", "reactivate_member", "revoke_member"]).has(normalizedAction)) {
      throw new CreatorApiError("Не удалось определить действие с участником.", {
        code: "admin_member_action_invalid",
      });
    }
    if (!isUuid(normalizedProfileId)) {
      throw new CreatorApiError("Не удалось определить участника. Обновите список.", {
        code: "admin_member_profile_invalid",
      });
    }
    if (normalizedReason.length < 10 || normalizedReason.length > 500) {
      throw new CreatorApiError("Укажите проверяемую причину длиной от 10 до 500 символов.", {
        code: "admin_reason_invalid",
      });
    }
    return this.mutate(RPC.adminMutate, {
      action: normalizedAction,
      target_profile_id: normalizedProfileId,
      reason: normalizedReason,
      ...(normalizedAction === "revoke_member"
        ? { confirmation: "REVOKE_MEMBER" }
        : {}),
    });
  }

  createManagedAccount(account = {}) {
    return this.mutate(RPC.adminMutate, {
      action: "create_account",
      ...normalizeManagedAccountInput(account),
    });
  }

  updateManagedAccount(accountId, expectedUpdatedAt, account = {}) {
    const normalizedAccountId = String(accountId || "").trim().toLowerCase();
    const normalizedExpectedAt = String(expectedUpdatedAt || "").trim();
    if (!isUuid(normalizedAccountId) || !Number.isFinite(Date.parse(normalizedExpectedAt))) {
      throw new CreatorApiError("Карточка аккаунта устарела. Обновите список.", {
        code: "admin_account_version_invalid",
      });
    }
    return this.mutate(RPC.adminMutate, {
      action: "update_account",
      account_id: normalizedAccountId,
      expected_updated_at: normalizedExpectedAt,
      ...normalizeManagedAccountInput(account),
    });
  }

  /*
   * Поля владения аккаунтом компании (фаза 0 контура авторазмещения):
   * вид владения, хранитель, на что заведён аккаунт, внешний ID, режим
   * публикации. Секретов здесь нет и быть не может — их место в Vault.
   */
  setManagedAccountOwnership(accountId, expectedUpdatedAt, ownership = {}) {
    const normalizedAccountId = String(accountId || "").trim().toLowerCase();
    const normalizedExpectedAt = String(expectedUpdatedAt || "").trim();
    if (!isUuid(normalizedAccountId) || !Number.isFinite(Date.parse(normalizedExpectedAt))) {
      throw new CreatorApiError("Карточка аккаунта устарела. Обновите список.", {
        code: "admin_account_version_invalid",
      });
    }
    const textOrNull = (value, limit) => {
      const normalized = String(value || "").trim().slice(0, limit);
      return normalized ? normalized : null;
    };
    const custodian = String(ownership.custodianProfileId || "").trim().toLowerCase();
    return this.mutate(RPC.adminAccountOwnership, {
      action: "set_ownership",
      account_id: normalizedAccountId,
      expected_updated_at: normalizedExpectedAt,
      ownership_kind: textOrNull(ownership.ownershipKind, 40),
      custodian_profile_id: isUuid(custodian) ? custodian : null,
      registration_email_alias: textOrNull(ownership.registrationEmailAlias, 120),
      registration_phone_ref: textOrNull(ownership.registrationPhoneRef, 40),
      external_account_id: textOrNull(ownership.externalAccountId, 120),
      posting_mode: textOrNull(ownership.postingMode, 20),
    });
  }

  archiveManagedAccount(accountId, expectedUpdatedAt, reason) {
    const normalizedAccountId = String(accountId || "").trim().toLowerCase();
    const normalizedExpectedAt = String(expectedUpdatedAt || "").trim();
    const normalizedReason = String(reason || "").trim();
    if (!isUuid(normalizedAccountId) || !Number.isFinite(Date.parse(normalizedExpectedAt))) {
      throw new CreatorApiError("Карточка аккаунта устарела. Обновите список.", {
        code: "admin_account_version_invalid",
      });
    }
    if (normalizedReason.length < 10 || normalizedReason.length > 500) {
      throw new CreatorApiError("Укажите проверяемую причину длиной от 10 до 500 символов.", {
        code: "admin_reason_invalid",
      });
    }
    return this.mutate(RPC.adminMutate, {
      action: "archive_account",
      account_id: normalizedAccountId,
      expected_updated_at: normalizedExpectedAt,
      reason: normalizedReason,
      confirmation: "ARCHIVE_ACCOUNT",
    });
  }

  assignManagedAccount(accountId, profileId = "") {
    const normalizedAccountId = String(accountId || "").trim().toLowerCase();
    const normalizedProfileId = String(profileId || "").trim().toLowerCase();
    if (!isUuid(normalizedAccountId)) {
      throw new CreatorApiError("Не удалось определить рабочий аккаунт. Обновите список.", {
        code: "admin_account_id_invalid",
      });
    }
    if (normalizedProfileId && !isUuid(normalizedProfileId)) {
      throw new CreatorApiError("Не удалось определить участника. Обновите список.", {
        code: "admin_member_profile_invalid",
      });
    }
    return this.mutate(RPC.adminMutate, normalizedProfileId
      ? {
          action: "bind_account",
          account_id: normalizedAccountId,
          target_profile_id: normalizedProfileId,
        }
      : {
          action: "unbind_account",
          account_id: normalizedAccountId,
        });
  }

  managerDashboard() {
    return this.call(RPC.managerDashboard, this.withOrganization({}));
  }

  operationalHealth() {
    return this.call(RPC.operationalHealth, this.withOrganization({}));
  }

  generationSpendOverview() {
    return this.call(RPC.generationSpendOverview, this.withOrganization({}));
  }

  generationModelAcceptance() {
    return this.call(
      RPC.generationModelAcceptance,
      this.withOrganization({}),
    );
  }

  updateGenerationSpendPolicy(policy = {}) {
    const dailyLimitMinor = normalizeSpendLimit(policy.daily_limit_minor, "дневной");
    const monthlyLimitMinor = normalizeSpendLimit(policy.monthly_limit_minor, "месячный");
    const perRequestLimitMinor = normalizeSpendLimit(policy.per_request_limit_minor, "разовый");
    const enabled = policy.paid_generation_enabled === true;
    const expectedVersion = Number(policy.expected_version);
    const timezone = String(policy.timezone || "Europe/Moscow").trim();
    const reason = String(policy.reason || "").trim();
    if (!Number.isSafeInteger(expectedVersion) || expectedVersion < 0) {
      throw new CreatorApiError("Сводка лимитов устарела. Обновите остаток и повторите изменение.", {
        code: "generation_budget_policy_changed",
      });
    }
    if (!/^[A-Za-z0-9_+./-]{1,80}$/u.test(timezone)) {
      throw new CreatorApiError("Не удалось определить часовой пояс денежного лимита.", {
        code: "generation_budget_timezone_invalid",
      });
    }
    if (reason.length < 10 || reason.length > 500 || /[\u0000-\u001f\u007f]/u.test(reason)) {
      throw new CreatorApiError("Укажите причину изменения бюджета длиной от 10 до 500 символов.", {
        code: "generation_budget_reason_invalid",
      });
    }
    if (
      enabled
      && (perRequestLimitMinor > dailyLimitMinor || dailyLimitMinor > monthlyLimitMinor)
    ) {
      throw new CreatorApiError("Лимит одного запуска должен быть не больше дневного, а дневной — не больше месячного.", {
        code: "generation_budget_limits_invalid",
      });
    }
    return this.mutate(RPC.updateGenerationSpendPolicy, {
      paid_generation_enabled: enabled,
      daily_limit_minor: dailyLimitMinor,
      monthly_limit_minor: monthlyLimitMinor,
      per_request_limit_minor: perRequestLimitMinor,
      timezone,
      reason,
      expected_version: expectedVersion,
    });
  }

  createGenerationCampaign(campaign = {}) {
    const name = String(campaign.name || "").trim();
    const dailyLimitMinor = normalizeSpendLimit(campaign.daily_limit_minor, "дневной");
    const monthlyLimitMinor = normalizeSpendLimit(campaign.monthly_limit_minor, "месячный");
    const perRequestLimitMinor = normalizeSpendLimit(campaign.per_request_limit_minor, "разовый");
    const reason = String(campaign.reason || "").trim();
    if (name.length < 2 || name.length > 160 || /[\u0000-\u001f\u007f]/u.test(name)) {
      throw new CreatorApiError("Название кампании должно содержать от 2 до 160 символов.", {
        code: "generation_campaign_name_invalid",
      });
    }
    validateCampaignPolicyInput({
      dailyLimitMinor,
      monthlyLimitMinor,
      perRequestLimitMinor,
      reason,
    });
    return this.mutate(RPC.createGenerationCampaign, {
      name,
      paid_generation_enabled: campaign.paid_generation_enabled === true,
      daily_limit_minor: dailyLimitMinor,
      monthly_limit_minor: monthlyLimitMinor,
      per_request_limit_minor: perRequestLimitMinor,
      reason,
    });
  }

  updateGenerationCampaignSpendPolicy(campaignId, policy = {}) {
    const normalizedCampaignId = String(campaignId || "").trim();
    const dailyLimitMinor = normalizeSpendLimit(policy.daily_limit_minor, "дневной");
    const monthlyLimitMinor = normalizeSpendLimit(policy.monthly_limit_minor, "месячный");
    const perRequestLimitMinor = normalizeSpendLimit(policy.per_request_limit_minor, "разовый");
    const reason = String(policy.reason || "").trim();
    const expectedVersion = Number(policy.expected_version);
    if (!isUuid(normalizedCampaignId)) {
      throw new CreatorApiError("Выберите кампанию из свежего списка.", {
        code: "paid_generation_campaign_required",
      });
    }
    if (!Number.isSafeInteger(expectedVersion) || expectedVersion < 1) {
      throw new CreatorApiError("Лимит кампании устарел. Обновите сводку.", {
        code: "generation_campaign_budget_policy_changed",
      });
    }
    validateCampaignPolicyInput({
      dailyLimitMinor,
      monthlyLimitMinor,
      perRequestLimitMinor,
      reason,
    });
    return this.mutate(RPC.updateGenerationCampaignSpendPolicy, {
      campaign_id: normalizedCampaignId,
      paid_generation_enabled: policy.paid_generation_enabled === true,
      daily_limit_minor: dailyLimitMinor,
      monthly_limit_minor: monthlyLimitMinor,
      per_request_limit_minor: perRequestLimitMinor,
      expected_version: expectedVersion,
      reason,
    });
  }

  inspectAccess(email) {
    return this.invokeAccess("inspect", email);
  }

  repairAccess(email, requestId = "") {
    return this.invokeAccess("repair", email, { requestId });
  }

  async invokeAccess(action, email, { requestId = "" } = {}) {
    const normalizedAction = String(action || "").trim().toLowerCase();
    const normalizedEmail = normalizeAccessEmail(email);
    if (!["inspect", "repair"].includes(normalizedAction)) {
      throw new CreatorApiError("Не удалось определить безопасное действие с доступом.", {
        code: "access_action_invalid",
      });
    }
    if (!normalizedEmail) {
      throw new CreatorApiError("Укажите точный рабочий email участника.", {
        code: "access_email_invalid",
      });
    }

    const payload = { action: normalizedAction, email: normalizedEmail };
    if (normalizedAction === "repair") {
      const normalizedRequestId = String(requestId || "").trim() || crypto.randomUUID();
      if (!isUuid(normalizedRequestId)) {
        throw new CreatorApiError("Не удалось подготовить безопасный номер восстановления.", {
          code: "access_request_id_invalid",
        });
      }
      payload.request_id = normalizedRequestId;
    }

    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия завершилась. Войдите снова перед проверкой доступа.", {
        code: "auth_session_required",
      });
    }

    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(ACCESS_FUNCTION, {
        body: payload,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Сервис доступа временно не ответил. Обновите сводку и повторите позже.", {
        code: "access_request_failed",
      });
    }
    if (error) throw await accessFunctionError(error);

    const source = data?.data && typeof data.data === "object" && !Array.isArray(data.data)
      ? data.data
      : data;
    if (
      !source
      || typeof source !== "object"
      || Array.isArray(source)
      || source.ok !== true
      || String(source.action || "") !== normalizedAction
      || normalizeAccessEmail(source.email) !== normalizedEmail
      || !source.access
      || typeof source.access !== "object"
      || Array.isArray(source.access)
    ) {
      throw new CreatorApiError("Сервис доступа вернул неполный ответ. Новое письмо не отправляйте.", {
        code: "access_response_invalid",
      });
    }
    return source;
  }

  async requestPublicPasswordRecovery({ email, requestId }) {
    const normalizedEmail = normalizeAccessEmail(email);
    const normalizedRequestId = String(requestId || "").trim();
    if (!normalizedEmail) {
      throw new CreatorApiError("Укажите рабочую почту в формате name@company.ru.", {
        code: "public_recovery_email_invalid",
      });
    }
    if (!isUuid(normalizedRequestId)) {
      throw new CreatorApiError("Не удалось подготовить безопасный номер запроса.", {
        code: "public_recovery_request_id_invalid",
      });
    }

    return this.invokePublicRecovery("request", {
      email: normalizedEmail,
      request_id: normalizedRequestId,
    });
  }

  async getPublicRecoveryReceipt({ receiptToken } = {}) {
    const normalizedReceiptToken = normalizePublicRecoveryToken(receiptToken);
    if (!normalizedReceiptToken) {
      throw new CreatorApiError("Сохранённая квитанция недоступна.", {
        code: "public_recovery_receipt_invalid",
      });
    }
    return this.invokePublicRecovery("status", { receipt_token: normalizedReceiptToken });
  }

  async invokePublicRecovery(action, payload) {
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(PUBLIC_RECOVERY_FUNCTION, {
        body: { action, ...payload },
      }));
    } catch {
      throw new CreatorApiError("Сервис восстановления временно не ответил. Сохраните квитанцию и повторите проверку позже.", {
        code: "public_recovery_request_failed",
      });
    }
    if (error) throw await publicRecoveryFunctionError(error);
    return normalizePublicRecoveryResponse(data, action, payload);
  }

  myWork(options = {}) {
    const payload = {};
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    payload.project_id = projectId;
    const query = String(options.query || "").trim();
    if (query.length > 120 || /[\u0000-\u001f\u007f]/u.test(query)) {
      throw new CreatorApiError("Сократите запрос поиска до 120 символов.", {
        code: "my_work_query_invalid",
      });
    }
    if (query) payload.query = query;

    const itemTypes = normalizeStringArray(options.item_types ?? options.itemTypes);
    const supportedItemTypes = new Set(["task", "generation", "review", "placement", "payout"]);
    if (
      itemTypes.length > supportedItemTypes.size
      || itemTypes.some((itemType) => !supportedItemTypes.has(itemType))
    ) {
      throw new CreatorApiError("Выберите доступные типы рабочих объектов.", {
        code: "my_work_item_types_invalid",
      });
    }
    if (itemTypes.length) payload.item_types = itemTypes;

    const statuses = normalizeStringArray(options.statuses);
    if (
      statuses.length > 20
      || statuses.some((status) => !/^[a-z0-9_-]{1,80}$/u.test(status))
    ) {
      throw new CreatorApiError("Проверьте выбранные статусы очереди.", {
        code: "my_work_statuses_invalid",
      });
    }
    if (statuses.length) payload.statuses = statuses;

    const pageSize = options.page_size === undefined ? 50 : Number(options.page_size);
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Можно загрузить от 1 до 100 рабочих объектов.", {
        code: "my_work_page_size_invalid",
      });
    }
    payload.page_size = pageSize;
    if (options.cursor !== undefined && options.cursor !== null) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор рабочей очереди имеет неверный формат.", {
          code: "my_work_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(RPC.myWork, this.withOrganization(payload));
  }

  notifications(options = {}) {
    const pageSize = options.page_size === undefined ? 50 : Number(options.page_size);
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Можно загрузить от 1 до 100 уведомлений.", {
        code: "notifications_page_size_invalid",
      });
    }
    const payload = {
      unread_only: options.unread_only === true,
      page_size: pageSize,
    };
    if (options.cursor !== undefined && options.cursor !== null) {
      if (!options.cursor || typeof options.cursor !== "object" || Array.isArray(options.cursor)) {
        throw new CreatorApiError("Курсор уведомлений имеет неверный формат.", {
          code: "notifications_cursor_invalid",
        });
      }
      payload.cursor = options.cursor;
    }
    return this.call(RPC.notifications, this.withOrganization(payload));
  }

  markNotificationsRead(notificationIds, isRead = true) {
    const ids = normalizeStringArray(notificationIds);
    if (
      ids.length < 1
      || ids.length > 100
      || ids.some((id) => !/^[0-9a-f]{8}-[0-9a-f-]{27,36}$/iu.test(id))
    ) {
      throw new CreatorApiError("Выберите от 1 до 100 уведомлений.", {
        code: "notification_ids_invalid",
      });
    }
    return this.mutate(RPC.markNotificationsRead, {
      notification_ids: ids,
      is_read: isRead === true,
    });
  }

  markAllNotificationsRead() {
    return this.mutate(RPC.markNotificationsRead, {
      all_unread: true,
      is_read: true,
    });
  }

  notificationCenter(options = {}) {
    const filters = new Set([
      "all", "unread", "action_required", "mentions", "processes", "system",
    ]);
    const filter = String(options.filter || "all").trim().toLowerCase();
    const pageSize = options.page_size === undefined
      ? 50
      : Number(options.page_size);
    if (!filters.has(filter)) {
      throw new CreatorApiError("Выберите доступный фильтр уведомлений.", {
        code: "notification_center_filter_invalid",
      });
    }
    if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 100) {
      throw new CreatorApiError("Можно загрузить от 1 до 100 уведомлений.", {
        code: "notification_center_page_size_invalid",
      });
    }
    const payload = { filter, page_size: pageSize };
    if (options.cursor !== undefined && options.cursor !== null) {
      const cursor = options.cursor;
      const cursorKeys = cursor && typeof cursor === "object" && !Array.isArray(cursor)
        ? Object.keys(cursor)
        : [];
      const createdAt = String(cursor?.created_at || "").trim();
      const id = String(cursor?.id || "").trim().toLowerCase();
      if (
        cursorKeys.length !== 2
        || !cursorKeys.every((key) => ["created_at", "id"].includes(key))
        || !Number.isFinite(Date.parse(createdAt))
        || !isUuid(id)
      ) {
        throw new CreatorApiError("Список уведомлений изменился. Обновите панель.", {
          code: "notification_center_cursor_invalid",
        });
      }
      payload.cursor = { created_at: createdAt, id };
    }
    return this.call(RPC.notificationCenter, this.withOrganization(payload));
  }

  validateNotificationAction(intent = {}) {
    const notificationId = String(
      intent.notification_id ?? intent.notificationId ?? "",
    ).trim().toLowerCase();
    const actionKey = String(intent.action_key ?? intent.actionKey ?? "")
      .trim()
      .toLowerCase();
    const projectId = String(intent.project_id ?? intent.projectId ?? "")
      .trim()
      .toLowerCase();
    const objectId = String(intent.object_id ?? intent.objectId ?? "")
      .trim()
      .toLowerCase();
    const processId = String(intent.process_id ?? intent.processId ?? "")
      .trim()
      .toLowerCase();
    if (!isUuid(notificationId)) {
      throw new CreatorApiError("Уведомление больше недоступно. Обновите панель.", {
        code: "notification_id_invalid",
      });
    }
    if (![
      "ai.open-decisions", "process.open", "review.open-object", "object.open",
    ].includes(actionKey)) {
      throw new CreatorApiError("Действие недоступно в этой версии интерфейса.", {
        code: "notification_action_key_invalid",
      });
    }
    if (
      (projectId && !isUuid(projectId))
      || (objectId && !isUuid(objectId))
      || (processId && !isUuid(processId))
    ) {
      throw new CreatorApiError("Точная цель уведомления изменилась. Обновите панель.", {
        code: "notification_action_intent_invalid",
      });
    }
    return this.call(RPC.validateNotificationAction, this.withOrganization({
      notification_id: notificationId,
      action_key: actionKey,
      project_id: projectId || null,
      object_id: objectId || null,
      process_id: processId || null,
    }));
  }

  markVisibleNotificationsRead(notificationIds, filter = "all") {
    const ids = normalizeStringArray(notificationIds)
      .map((id) => id.toLowerCase());
    const normalizedFilter = String(filter || "").trim().toLowerCase();
    if (
      ids.length < 1
      || ids.length > 100
      || new Set(ids).size !== ids.length
      || ids.some((id) => !isUuid(id))
    ) {
      throw new CreatorApiError("Выберите от 1 до 100 видимых уведомлений.", {
        code: "notification_ids_invalid",
      });
    }
    if (![
      "all", "unread", "action_required", "mentions", "processes", "system",
    ].includes(normalizedFilter)) {
      throw new CreatorApiError("Выберите доступный фильтр уведомлений.", {
        code: "notification_center_filter_invalid",
      });
    }
    return this.mutate(RPC.markVisibleNotificationsRead, {
      filter: normalizedFilter,
      notification_ids: ids,
    });
  }

  trainingProgress(moduleCode = "") {
    const normalizedModuleCode = String(moduleCode || "").trim();
    if (
      normalizedModuleCode
      && !/^[a-z0-9_:-]{1,120}$/iu.test(normalizedModuleCode)
    ) {
      throw new CreatorApiError("Код учебного блока имеет неверный формат.", {
        code: "training_module_code_invalid",
      });
    }
    return this.call(RPC.trainingProgress, this.withOrganization(
      normalizedModuleCode ? { module_code: normalizedModuleCode } : {},
    ));
  }

  saveTrainingProgress(progress) {
    const moduleCode = String(progress?.module_code || "").trim();
    const walkthroughId = String(progress?.walkthrough_id || "").trim();
    if (
      !/^[a-z0-9_:-]{1,120}$/iu.test(moduleCode)
      || !/^[a-z0-9_:-]{1,160}$/iu.test(walkthroughId)
    ) {
      throw new CreatorApiError("Не удалось определить учебный тренажёр.", {
        code: "training_progress_identity_invalid",
      });
    }
    const completedFrameIds = normalizeStringArray(progress?.completed_frame_ids);
    if (
      completedFrameIds.length > 200
      || completedFrameIds.some((frameId) => frameId.length > 160)
    ) {
      throw new CreatorApiError("Прогресс учебного тренажёра имеет неверный формат.", {
        code: "training_progress_frames_invalid",
      });
    }
    const positionSeconds = Number(progress?.position_seconds || 0);
    if (!Number.isFinite(positionSeconds) || positionSeconds < 0 || positionSeconds > 86_400) {
      throw new CreatorApiError("Позиция учебного видео имеет неверный формат.", {
        code: "training_progress_position_invalid",
      });
    }
    const payload = {
      module_code: moduleCode,
      walkthrough_id: walkthroughId,
      current_frame_id: progress?.current_frame_id
        ? String(progress.current_frame_id).slice(0, 160)
        : null,
      position_seconds: positionSeconds,
      completed_frame_ids: completedFrameIds,
      completed: progress?.completed === true,
    };
    if (progress?.expected_version !== undefined && progress?.expected_version !== null) {
      const expectedVersion = Number(progress.expected_version);
      if (!Number.isInteger(expectedVersion) || expectedVersion < 1) {
        throw new CreatorApiError("Версия учебного прогресса устарела.", {
          code: "training_progress_version_invalid",
        });
      }
      payload.expected_version = expectedVersion;
    }
    return this.mutate(RPC.saveTrainingProgress, payload);
  }

  savedWorkViews(options = {}) {
    const action = String(options.action || "list").trim().toLowerCase();
    if (!["list", "upsert", "delete", "set_default"].includes(action)) {
      throw new CreatorApiError("Неизвестное действие с сохранённым фильтром.", {
        code: "saved_work_view_action_invalid",
      });
    }
    const payload = { action };
    if (options.view_id) payload.view_id = String(options.view_id);
    if (options.expected_version !== undefined) {
      const expectedVersion = Number(options.expected_version);
      if (!Number.isInteger(expectedVersion) || expectedVersion < 1) {
        throw new CreatorApiError("Версия сохранённого фильтра устарела.", {
          code: "saved_work_view_version_invalid",
        });
      }
      payload.expected_version = expectedVersion;
    }
    if (action === "upsert") {
      const name = String(options.name || "").trim();
      if (name.length < 2 || name.length > 80 || /[\u0000-\u001f\u007f]/u.test(name)) {
        throw new CreatorApiError("Введите название фильтра от 2 до 80 символов.", {
          code: "saved_work_view_name_invalid",
        });
      }
      payload.name = name;
      if (
        options.is_default !== undefined
        && typeof options.is_default !== "boolean"
      ) {
        throw new CreatorApiError("Признак фильтра по умолчанию имеет неверный формат.", {
          code: "saved_work_view_is_default_invalid",
        });
      }
      payload.is_default = options.is_default === true;
      payload.filters = {
        query: String(options.filters?.query || "").trim().slice(0, 120),
        statuses: normalizeStringArray(options.filters?.statuses).slice(0, 20),
        item_types: normalizeStringArray(
          options.filters?.item_types ?? options.filters?.itemTypes,
        ).filter((itemType) => ["task", "generation", "review", "placement", "payout"].includes(itemType)),
      };
    }
    if (action === "list") {
      return this.call(RPC.savedWorkViews, this.withOrganization(payload));
    }
    return this.mutate(RPC.savedWorkViews, payload);
  }

  async startProductResearch(input, {
    onRunCreated,
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
    const productName = String(input?.product_name || "").trim();
    const sku = String(input?.sku || "").trim();
    if (!productName || !sku || productName.length > 180 || sku.length > 120) {
      throw new CreatorApiError("Укажите название товара и проверьте артикул.", {
        code: "product_research_input_invalid",
      });
    }
    if (input?.paid_analysis_ack !== true) {
      throw new CreatorApiError("Подтвердите платный ИИ-анализ перед запуском.", {
        code: "product_research_paid_confirmation_required",
      });
    }
    const paidAuthorizationProvided = Object.prototype.hasOwnProperty.call(
      input || {},
      "paid_analysis_authorization",
    );
    const paidAnalysisAuthorization = paidAuthorizationProvided
      ? normalizeProductResearchPaidAuthorization(
          input.paid_analysis_authorization,
        )
      : null;
    const productCategory = String(input?.product_category || "")
      .trim()
      .toLowerCase();
    if (!AI_PRODUCT_CATEGORY_SET.has(productCategory)) {
      throw new CreatorApiError("Выберите одну категорию для входящих ИИ-центра.", {
        code: "product_research_ai_category_required",
      });
    }
    if (
      !Array.isArray(input?.platforms)
      || input.platforms.length < 1
      || input.platforms.some((platform) =>
        !PRODUCT_RESEARCH_PLATFORM_SET.has(String(platform))
      )
    ) {
      throw new CreatorApiError("Выберите хотя бы одну площадку для будущих роликов.", {
        code: "product_research_platform_required",
      });
    }

    const normalizedProjectId = requiredProjectId(
      projectIdSnake || projectId || input?.project_id || input?.projectId,
    );
    const exactBundleKeys = [
      "exact_youtube_source_id",
      "exact_youtube_attachment_id",
      "exact_youtube_media_id",
      "exact_video_evidence_id",
      "media_matches_registered_source",
      "source_match_basis",
    ];
    const exactBundleRequested = exactBundleKeys.some((key) => (
      input?.[key] !== undefined && input?.[key] !== null
    ));
    if (exactBundleRequested) {
      const exactIds = [
        input?.product_id,
        input?.exact_youtube_source_id,
        input?.exact_youtube_attachment_id,
        input?.exact_youtube_media_id,
        input?.exact_video_evidence_id,
      ].map((value) => String(value || "").trim().toLowerCase());
      if (
        exactIds.some((value) => !isUuid(value))
        || input?.media_matches_registered_source !== true
        || input?.source_match_basis
          !== "operator_compared_uploaded_media_to_registered_source"
      ) {
        throw new CreatorApiError(
          "Подготовка точного видеоисточника заполнена не полностью. Платный анализ не запущен — вернитесь в ИИ-центр и повторите подготовку кадров.",
          { code: "exact_video_research_binding_payload_invalid" },
        );
      }
    }
    const payload = {
      ...input,
      product_category: productCategory,
      project_id: normalizedProjectId,
    };
    if (paidAnalysisAuthorization) {
      payload.paid_analysis_authorization = paidAnalysisAuthorization;
    } else {
      delete payload.paid_analysis_authorization;
    }
    delete payload.projectId;
    // The media id is a client-side expected receipt value. The SQL binding
    // derives its authoritative media from the append-only attachment and
    // deliberately does not accept a caller-selected media id.
    delete payload.exact_youtube_media_id;
    const created = await this.mutate(RPC.startProductResearch, payload, {
      fingerprintPayload: productResearchMutationFingerprintPayload(payload),
    });
    const source = created?.data && typeof created.data === "object" ? created.data : created;
    const run = source?.run || source?.research || {};
    const runId = String(run?.id || source?.run_id || source?.research_id || source?.id || "").trim();
    if (!runId) {
      throw new CreatorApiError("Сервер не вернул номер исследования. Обновите раздел и повторите.", {
        code: "product_research_run_missing",
      });
    }
    if (exactBundleRequested) {
      const exactVideo = source?.exact_video;
      const exactVideoValid = exactVideo
        && typeof exactVideo === "object"
        && !Array.isArray(exactVideo)
        && String(source?.project_id || "").trim().toLowerCase()
          === normalizedProjectId
        && isUuid(String(exactVideo.binding_id || "").trim().toLowerCase())
        && String(exactVideo.source_id || "").trim().toLowerCase()
          === String(input.exact_youtube_source_id).trim().toLowerCase()
        && String(exactVideo.attachment_id || "").trim().toLowerCase()
          === String(input.exact_youtube_attachment_id).trim().toLowerCase()
        && String(exactVideo.media_id || "").trim().toLowerCase()
          === String(input.exact_youtube_media_id).trim().toLowerCase()
        && String(exactVideo.evidence_id || "").trim().toLowerCase()
          === String(input.exact_video_evidence_id).trim().toLowerCase()
        && /^https:\/\/youtube[.]com\/watch[?]v=[A-Za-z0-9_-]{11}$/u
          .test(String(exactVideo.canonical_url || "").trim())
        && exactVideo.analysis_scope === "sampled_frames_only"
        && exactVideo.full_stream_access === false
        && exactVideo.transcript_available === false
        && exactVideo.content_review_provider_started === false
        && exactVideo.product_research_provider_started === false
        && isUuid(runId);
      if (!exactVideoValid) {
        const error = new CreatorApiError(
          "Исследование сохранено, но сервер не подтвердил связь с точным MP4 и пятью кадрами. Платный анализ не запущен; обновите статус этого исследования.",
          { code: "exact_video_research_binding_response_invalid" },
        );
        error.job = { id: runId, status: String(run?.status || "queued") };
        throw error;
      }
    }
    if (typeof onRunCreated === "function") {
      try {
        onRunCreated({
          id: runId,
          status: String(run?.status || "queued"),
          project_id: normalizedProjectId,
        });
      } catch {
        // Recovery storage is a UI convenience; it must not cancel a paid run.
      }
    }

    let accepted;
    try {
      accepted = await this.invokeProductResearch({
        action: "analyze",
        research_id: runId,
        project_id: normalizedProjectId,
      });
    } catch (error) {
      error.job = { id: runId, status: String(run?.status || "queued") };
      throw error;
    }
    return { ...source, run: { ...run, id: runId }, analysis_request: accepted };
  }

  async productResearchStatus(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const scopedPayload = this.withOrganization({ run_id: normalizedRunId });
    const projectScopedPayload = {
      ...scopedPayload,
      project_id: requiredProjectId(options.project_id ?? options.projectId),
    };
    // Advance a saved background OpenAI response before reading the database
    // snapshot. This call only performs GET polling for processing rows; the
    // Edge Function explicitly refuses to turn a queued status read into the
    // one paid POST. A temporary Edge outage must not hide the last durable
    // result already stored in Postgres.
    try {
      await this.invokeProductResearch({
        action: "status",
        research_id: normalizedRunId,
        project_id: projectScopedPayload.project_id,
      });
    } catch (error) {
      console.warn(
        "Research background status refresh unavailable",
        error?.serverCode || error?.code || "",
      );
    }
    const requestedOutcomeScope = options?.outcome_scope
      ? requireResearchOutcomeScope(options.outcome_scope)
      : null;
    const [
      status,
      monitorResult,
      providerResult,
      marketRegistryResult,
      outcomeScopeRegistryResult,
      youtubeOverviewResult,
      categoryLearningResult,
    ] = await Promise.all([
      this.call(RPC.productResearchStatus, projectScopedPayload),
      settleResearchSatellite(
        this.call(RPC.researchWatchlistStatus, scopedPayload),
        "research_watchlist_status",
      ),
      settleResearchSatellite(
        this.call(RPC.researchProviderStatus, scopedPayload),
        "research_provider_status",
      ),
      settleResearchSatellite(
        this.call(RPC.researchMarketCategoryRegistry, scopedPayload),
        "research_market_registry",
      ),
      settleResearchSatellite(
        this.call(RPC.researchOutcomeLearningScopes, {
          ...scopedPayload,
          limit: 50,
        }),
        "research_outcome_scope_registry",
      ),
      settleResearchSatellite(
        this.call(RPC.researchYoutubeOverview, {
          ...scopedPayload,
          limit: 12,
        }),
        "research_youtube_overview",
      ),
      settleResearchSatellite(
        this.call(RPC.researchCategoryLearningStatus, scopedPayload),
        "research_category_learning_status",
      ),
    ]);
    const statusRoot = status?.data && typeof status.data === "object"
      && !Array.isArray(status.data)
      ? status.data
      : status;
    const result = {
      ...(statusRoot && typeof statusRoot === "object" ? statusRoot : {}),
    };
    if (!monitorResult.ok) {
      console.warn(
        "Research watchlist status unavailable",
        monitorResult.error?.serverCode || monitorResult.error?.code || "",
      );
      result.watchlist_monitor_unavailable = true;
    } else {
      const monitor = monitorResult.value?.data
        && typeof monitorResult.value.data === "object"
        && !Array.isArray(monitorResult.value.data)
        ? monitorResult.value.data
        : monitorResult.value;
      result.watchlist = monitor?.watchlist ?? null;
      result.watchlist_history = Array.isArray(monitor?.snapshots)
        ? monitor.snapshots
        : [];
      result.watchlist_proposal = monitor?.proposal ?? null;
      result.watchlist_guidance = monitor?.guidance ?? null;
      result.watchlist_monitor_unavailable = false;
    }
    if (!providerResult.ok) {
      console.warn(
        "Research provider control status unavailable",
        providerResult.error?.serverCode || providerResult.error?.code || "",
      );
      result.research_provider_control = null;
      result.research_provider_control_unavailable = true;
    } else {
      result.research_provider_control = providerResult.value?.data
        && typeof providerResult.value.data === "object"
        && !Array.isArray(providerResult.value.data)
        ? providerResult.value.data
        : providerResult.value;
      result.research_provider_control_unavailable = false;
    }
    if (!marketRegistryResult.ok) {
      console.warn(
        "Research market category registry unavailable",
        marketRegistryResult.error?.serverCode || marketRegistryResult.error?.code || "",
      );
      result.research_market_registry = null;
      result.research_market_registry_unavailable = true;
    } else {
      result.research_market_registry = marketRegistryResult.value?.data
        && typeof marketRegistryResult.value.data === "object"
        && !Array.isArray(marketRegistryResult.value.data)
        ? marketRegistryResult.value.data
        : marketRegistryResult.value;
      result.research_market_registry_unavailable = false;
    }
    if (!categoryLearningResult.ok) {
      console.warn(
        "Research category evidence readiness unavailable",
        categoryLearningResult.error?.serverCode
          || categoryLearningResult.error?.code
          || "",
      );
      result.research_category_learning = null;
      result.research_category_learning_unavailable = true;
    } else {
      result.research_category_learning = categoryLearningResult.value?.data
        && typeof categoryLearningResult.value.data === "object"
        && !Array.isArray(categoryLearningResult.value.data)
        ? categoryLearningResult.value.data
        : categoryLearningResult.value;
      result.research_category_learning_unavailable = false;
    }
    let outcomeScopeRegistry = null;
    if (!outcomeScopeRegistryResult.ok) {
      console.warn(
        "Research outcome scope registry unavailable",
        outcomeScopeRegistryResult.error?.serverCode
          || outcomeScopeRegistryResult.error?.code
          || "",
      );
      result.research_outcome_scope_registry = null;
      result.research_outcome_scope_registry_unavailable = true;
    } else {
      outcomeScopeRegistry = readResearchOutcomeScopeRegistry(
        outcomeScopeRegistryResult.value,
        normalizedRunId,
      );
      result.research_outcome_scope_registry = outcomeScopeRegistry?.raw || null;
      result.research_outcome_scope_registry_unavailable = !outcomeScopeRegistry;
    }
    let outcomeScope = null;
    if (outcomeScopeRegistry) {
      if (requestedOutcomeScope) {
        const requestedKey = researchOutcomeScopeKey(requestedOutcomeScope);
        outcomeScope = outcomeScopeRegistry.scopes
          .find((entry) => entry.key === requestedKey)?.scope || null;
      } else if (!outcomeScopeRegistry.truncated && outcomeScopeRegistry.scopes.length === 1) {
        outcomeScope = outcomeScopeRegistry.scopes[0].scope;
      }
    }
    result.research_outcome_learning_scope = outcomeScope;
    result.research_outcome_learning_scope_missing = outcomeScope === null;
    if (outcomeScope) {
      const outcomeResult = await settleResearchSatellite(
        this.call(
          RPC.researchOutcomeLearningStatus,
          this.withOrganization(outcomeScope),
        ),
        "research_outcome_learning_status",
      );
      if (!outcomeResult.ok) {
        console.warn(
          "Research outcome learning status unavailable",
          outcomeResult.error?.serverCode || outcomeResult.error?.code || "",
        );
        result.research_outcome_learning = null;
        result.research_outcome_learning_unavailable = true;
      } else {
        result.research_outcome_learning = outcomeResult.value?.data
          && typeof outcomeResult.value.data === "object"
          && !Array.isArray(outcomeResult.value.data)
          ? outcomeResult.value.data
          : outcomeResult.value;
        result.research_outcome_learning_unavailable = false;
      }
    } else {
      result.research_outcome_learning = null;
      result.research_outcome_learning_unavailable = false;
    }
    let youtubeOverview = null;
    if (!youtubeOverviewResult.ok) {
      console.warn(
        "Research YouTube overview unavailable",
        youtubeOverviewResult.error?.serverCode
          || youtubeOverviewResult.error?.code
          || "",
      );
      result.research_youtube_overview = null;
      result.research_youtube_overview_unavailable = true;
      result.research_youtube_latest = null;
      result.research_youtube_latest_unavailable = true;
    } else {
      const candidate = youtubeOverviewResult.value?.data
        && typeof youtubeOverviewResult.value.data === "object"
        && !Array.isArray(youtubeOverviewResult.value.data)
        ? youtubeOverviewResult.value.data
        : youtubeOverviewResult.value;
      youtubeOverview = candidate
        && typeof candidate === "object"
        && !Array.isArray(candidate)
        && candidate.ok === true
        && candidate.version === "research-youtube-live-ingestion-v1"
        && String(candidate.run_id || "").toLowerCase() === normalizedRunId
        && Array.isArray(candidate.ingestions)
        && candidate.ingestions.length <= 20
        ? candidate
        : null;
      result.research_youtube_overview = youtubeOverview;
      result.research_youtube_overview_unavailable = !youtubeOverview;
      const latestIngestionId = String(
        youtubeOverview?.ingestions?.[0]?.ingestion_id || "",
      ).trim().toLowerCase();
      if (isUuid(latestIngestionId)) {
        const youtubeStatusResult = await settleResearchSatellite(
          this.call(RPC.researchYoutubeStatus, {
            ingestion_id: latestIngestionId,
          }),
          "research_youtube_status",
        );
        if (youtubeStatusResult.ok) {
          result.research_youtube_latest = youtubeStatusResult.value?.data
            && typeof youtubeStatusResult.value.data === "object"
            && !Array.isArray(youtubeStatusResult.value.data)
            ? youtubeStatusResult.value.data
            : youtubeStatusResult.value;
          result.research_youtube_latest_unavailable = false;
        } else {
          result.research_youtube_latest = null;
          result.research_youtube_latest_unavailable = true;
        }
      } else {
        result.research_youtube_latest = null;
        result.research_youtube_latest_unavailable = false;
      }
    }
    return result;
  }

  async revalidateProductResearchResponse(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    await this.invokeProductResearch({
      action: "revalidate",
      research_id: normalizedRunId,
      project_id: projectId,
    });
    return this.productResearchStatus(normalizedRunId, { projectId });
  }

  researchStageControlStatus(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const projectId = requiredProjectId(
      options.project_id ?? options.projectId,
    );
    const payload = {
      run_id: normalizedRunId,
      project_id: projectId,
    };
    if (options.branch_id !== undefined || options.branchId !== undefined) {
      const branchId = String(
        options.branch_id ?? options.branchId ?? "",
      ).trim().toLowerCase();
      if (!isUuid(branchId)) {
        throw new CreatorApiError("Не удалось определить ветку исправлений.", {
          code: "research_stage_branch_invalid",
        });
      }
      payload.branch_id = branchId;
    }
    if (options.history_limit !== undefined || options.historyLimit !== undefined) {
      const historyLimit = Number(
        options.history_limit ?? options.historyLimit,
      );
      if (!Number.isInteger(historyLimit) || historyLimit < 1 || historyLimit > 100) {
        throw new CreatorApiError("История этапов может содержать от 1 до 100 событий.", {
          code: "research_stage_history_limit_invalid",
        });
      }
      payload.history_limit = historyLimit;
    }
    return this.call(
      RPC.researchStageControlStatus,
      this.withOrganization(payload),
    );
  }

  async controlResearchStage(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const projectId = requiredProjectId(
      options.project_id ?? options.projectId,
    );
    const branchId = String(
      options.branch_id ?? options.branchId ?? "",
    ).trim().toLowerCase();
    const stage = String(options.stage || "").trim().toLowerCase();
    const action = String(options.action || "").trim().toLowerCase();
    const expectedHeadEventId = String(
      options.expected_head_event_id ?? options.expectedHeadEventId ?? "",
    ).trim().toLowerCase();
    const expectedArtifactId = String(
      options.expected_artifact_id ?? options.expectedArtifactId ?? "",
    ).trim().toLowerCase();
    const expectedContentHash = String(
      options.expected_content_hash ?? options.expectedContentHash ?? "",
    ).trim().toLowerCase();
    const expectedBranchRevisionHash = String(
      options.expected_branch_revision_hash
        ?? options.expectedBranchRevisionHash
        ?? "",
    ).trim().toLowerCase();
    const reason = String(options.reason || "").trim();
    if (
      !isUuid(branchId)
      || !RESEARCH_STAGE_SET.has(stage)
      || !RESEARCH_STAGE_ACTION_SET.has(action)
      || !isUuid(expectedHeadEventId)
      || !isUuid(expectedArtifactId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedContentHash)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedBranchRevisionHash)
      || reason.length < 3
      || reason.length > 500
      || options.confirmation !== true
    ) {
      throw new CreatorApiError("Снимок этапа изменился или команда заполнена не полностью.", {
        code: "research_stage_control_invalid",
      });
    }

    const payload = {
      run_id: normalizedRunId,
      project_id: projectId,
      branch_id: branchId,
      stage,
      action,
      expected_head_event_id: expectedHeadEventId,
      expected_artifact_id: expectedArtifactId,
      expected_content_hash: expectedContentHash,
      expected_branch_revision_hash: expectedBranchRevisionHash,
      reason,
      confirmation: true,
    };
    if (action === "patch") {
      const replacement = options.replacement;
      const userInput = String(
        options.user_input ?? options.userInput ?? "",
      ).trim();
      if (
        !replacement
        || typeof replacement !== "object"
        || Array.isArray(replacement)
        || stableStringify(replacement).length > 524_288
        || userInput.length < 3
        || userInput.length > 4_000
      ) {
        throw new CreatorApiError("Для правки нужен структурированный JSON и объяснение от 3 до 4000 символов.", {
          code: "research_stage_patch_invalid",
        });
      }
      payload.replacement = replacement;
      payload.user_input = userInput;
    } else if (action === "revert") {
      const targetArtifactId = String(
        options.target_artifact_id ?? options.targetArtifactId ?? "",
      ).trim().toLowerCase();
      if (!isUuid(targetArtifactId) || targetArtifactId === expectedArtifactId) {
        throw new CreatorApiError("Выберите другую точную версию этапа для отката.", {
          code: "research_stage_revert_invalid",
        });
      }
      payload.target_artifact_id = targetArtifactId;
    } else if (action === "fork") {
      const newBranchKey = String(
        options.new_branch_key ?? options.newBranchKey ?? "",
      ).trim().toLowerCase();
      if (
        newBranchKey === "main"
        || newBranchKey.length < 3
        || !RESEARCH_STAGE_BRANCH_KEY_PATTERN.test(newBranchKey)
      ) {
        throw new CreatorApiError("Ключ новой ветки: 3–64 строчных латинских символа, цифры, _ или -.", {
          code: "research_stage_fork_invalid",
        });
      }
      payload.new_branch_key = newBranchKey;
    } else if (action === "recompute") {
      const userInput = String(
        options.user_input ?? options.userInput ?? "",
      ).trim();
      if (
        stage === "sources"
        || options.paid_analysis_ack !== true
        || userInput.length < 3
        || userInput.length > 4_000
      ) {
        throw new CreatorApiError("Для пересчёта опишите изменение и отдельно подтвердите платный анализ.", {
          code: "research_stage_recompute_invalid",
        });
      }
      payload.user_input = userInput;
      payload.paid_analysis_ack = true;
    }

    const prepared = await this.mutate(RPC.controlResearchStage, payload);
    if (action !== "recompute") return prepared;

    const source = prepared?.data && typeof prepared.data === "object"
      && !Array.isArray(prepared.data)
      ? prepared.data
      : prepared;
    const recompute = source?.recompute_request;
    const requestId = String(recompute?.request_id || "").trim().toLowerCase();
    const childRunId = String(recompute?.child_run_id || "").trim().toLowerCase();
    if (
      !recompute
      || typeof recompute !== "object"
      || Array.isArray(recompute)
      || !isUuid(requestId)
      || !isUuid(childRunId)
      || recompute.status !== "queued"
      || recompute.paid_analysis_ack !== true
      || recompute.automatic_provider_action !== false
      || recompute.max_provider_attempts !== 1
      || recompute.invoke?.action !== "analyze"
      || String(recompute.invoke?.research_id || "").toLowerCase() !== childRunId
      || String(recompute.invoke?.project_id || "").toLowerCase() !== projectId
    ) {
      throw new CreatorApiError("Запрос пересчёта сохранён, но точный дочерний запуск не подтверждён. Не повторяйте команду.", {
        code: "research_stage_recompute_prepare_invalid",
      });
    }

    if (this.researchRecomputeInvocations.has(requestId)) {
      return {
        ...source,
        analysis_request: {
          ok: true,
          skipped: true,
          reason: "recompute_invoke_already_attempted",
        },
      };
    }
    this.researchRecomputeInvocations.add(requestId);
    try {
      const accepted = await this.invokeProductResearch({
        action: "analyze",
        research_id: childRunId,
        project_id: projectId,
      });
      return { ...source, analysis_request: accepted };
    } catch (error) {
      error.job = {
        id: childRunId,
        status: "queued",
        recompute_request_id: requestId,
      };
      error.stageControl = source;
      throw error;
    }
  }

  async resumeResearchStageRecompute(childRunId, requestId, options = {}) {
    const normalizedChildRunId = String(childRunId || "").trim().toLowerCase();
    const normalizedRequestId = String(requestId || "").trim().toLowerCase();
    const projectId = requiredProjectId(
      options.project_id ?? options.projectId,
    );
    if (!isUuid(normalizedChildRunId) || !isUuid(normalizedRequestId)) {
      throw new CreatorApiError("Сохранённый пересчёт изменился. Сначала обновите его статус.", {
        code: "research_stage_recompute_resume_invalid",
      });
    }
    try {
      return await this.invokeProductResearch({
        action: "analyze",
        research_id: normalizedChildRunId,
        project_id: projectId,
      });
    } catch (error) {
      error.job = {
        id: normalizedChildRunId,
        status: "queued",
        recompute_request_id: normalizedRequestId,
      };
      throw error;
    }
  }

  researchCategoryLearningStatus(runId) {
    const normalizedRunId = this.requireResearchRunId(runId);
    return this.call(
      RPC.researchCategoryLearningStatus,
      this.withOrganization({ run_id: normalizedRunId }),
    );
  }

  async captureResearchCategoryReadiness(runId, expectedEvidenceHash) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const normalizedHash = String(expectedEvidenceHash || "")
      .trim()
      .toLowerCase();
    if (!RESEARCH_STAGE_HASH_PATTERN.test(normalizedHash)) {
      throw new CreatorApiError(
        "Снимок готовности устарел. Обновите доказательную базу категории.",
        { code: "research_category_readiness_hash_invalid" },
      );
    }
    const response = await this.mutate(RPC.captureResearchCategoryReadiness, {
      run_id: normalizedRunId,
      expected_evidence_hash: normalizedHash,
    });
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    const snapshot = source?.snapshot;
    if (
      !hasExactObjectKeys(source, [
        "ok",
        "metric_kind",
        "source_ledger_rows_registered",
        "snapshot",
        "external_call_started",
      ])
      || source.ok !== true
      || source.metric_kind !== "category_evidence_readiness_not_model_iq"
      || source.external_call_started !== false
      || !Number.isInteger(source.source_ledger_rows_registered)
      || source.source_ledger_rows_registered < 0
      || !hasExactObjectKeys(snapshot, [
        "snapshot_id",
        "score",
        "dimensions",
        "evidence_hash",
        "snapshot_hash",
        "captured_at",
      ])
      || !isUuid(String(snapshot.snapshot_id || "").toLowerCase())
      || !Number.isInteger(snapshot.score)
      || snapshot.score < 0
      || snapshot.score > 100
      || !Array.isArray(snapshot.dimensions)
      || snapshot.dimensions.length !== 6
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(snapshot.evidence_hash || ""))
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(snapshot.snapshot_hash || ""))
      || typeof snapshot.captured_at !== "string"
      || !Number.isFinite(Date.parse(snapshot.captured_at))
    ) {
      throw new CreatorApiError(
        "Снимок готовности сохранён с неожиданным ответом. Не повторяйте действие автоматически.",
        { code: "research_category_readiness_capture_invalid" },
      );
    }
    return source;
  }

  async correctResearchSourceAnalysis(options = {}) {
    const sourceLedgerId = String(
      options.source_ledger_id ?? options.sourceLedgerId ?? "",
    ).trim().toLowerCase();
    const expectedHeadEventId = String(
      options.expected_head_event_id ?? options.expectedHeadEventId ?? "",
    ).trim().toLowerCase();
    const expectedHeadHash = String(
      options.expected_head_hash ?? options.expectedHeadHash ?? "",
    ).trim().toLowerCase();
    const correctionReason = String(
      options.correction_reason ?? options.correctionReason ?? "",
    ).replace(/\s+/gu, " ").trim();
    const analysis = options.analysis;
    let analysisBytes = Number.POSITIVE_INFINITY;
    try {
      analysisBytes = new TextEncoder().encode(stableStringify(analysis)).length;
    } catch {
      analysisBytes = Number.POSITIVE_INFINITY;
    }
    if (
      !isUuid(sourceLedgerId)
      || !isUuid(expectedHeadEventId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedHeadHash)
      || !researchSourceAnalysisIsValid(analysis)
      || analysisBytes > 32_768
      || correctionReason.length < 3
      || correctionReason.length > 1_000
    ) {
      throw new CreatorApiError(
        "Проверьте структурированный разбор, точную версию источника и причину исправления.",
        { code: "research_source_correction_invalid" },
      );
    }
    const response = await this.mutate(RPC.correctResearchSourceAnalysis, {
      source_ledger_id: sourceLedgerId,
      expected_head_event_id: expectedHeadEventId,
      expected_head_hash: expectedHeadHash,
      analysis,
      correction_reason: correctionReason,
    });
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    if (
      !hasExactObjectKeys(source, [
        "ok",
        "event_id",
        "event_hash",
        "analysis_version",
        "origin",
        "external_call_started",
      ])
      || source.ok !== true
      || !isUuid(String(source.event_id || "").toLowerCase())
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(source.event_hash || ""))
      || !Number.isInteger(source.analysis_version)
      || source.analysis_version < 2
      || source.origin !== "human_correction"
      || source.external_call_started !== false
    ) {
      throw new CreatorApiError(
        "Исправление сохранено с неожиданным ответом. Не повторяйте его автоматически.",
        { code: "research_source_correction_response_invalid" },
      );
    }
    return source;
  }

  async correctResearchYoutubeObservationAnalysis(options = {}) {
    const observationId = String(
      options.observation_id ?? options.observationId ?? "",
    ).trim().toLowerCase();
    const observationHash = String(
      options.observation_hash ?? options.observationHash ?? "",
    ).trim().toLowerCase();
    const expectedHeadEventId = String(
      options.expected_head_event_id ?? options.expectedHeadEventId ?? "",
    ).trim().toLowerCase();
    const expectedHeadHash = String(
      options.expected_head_hash ?? options.expectedHeadHash ?? "",
    ).trim().toLowerCase();
    const expectedRetentionExpiresAt = String(
      options.expected_retention_expires_at
        ?? options.expectedRetentionExpiresAt
        ?? "",
    ).trim();
    const expectedRetentionExpiresAtMs = Date.parse(
      expectedRetentionExpiresAt,
    );
    const correctionReason = String(
      options.correction_reason ?? options.correctionReason ?? "",
    ).replace(/\s+/gu, " ").trim();
    const analysis = options.analysis;
    let analysisBytes = Number.POSITIVE_INFINITY;
    try {
      analysisBytes = new TextEncoder().encode(stableStringify(analysis)).length;
    } catch {
      analysisBytes = Number.POSITIVE_INFINITY;
    }
    if (
      !isUuid(observationId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(observationHash)
      || !isUuid(expectedHeadEventId)
      || !RESEARCH_STAGE_HASH_PATTERN.test(expectedHeadHash)
      || !Number.isFinite(expectedRetentionExpiresAtMs)
      || !researchYoutubeObservationAnalysisIsValid(analysis)
      || analysisBytes > 16_384
      || correctionReason.length < 3
      || correctionReason.length > 1_000
    ) {
      throw new CreatorApiError(
        "Проверьте гипотезу, точную версию YouTube-наблюдения и причину исправления.",
        { code: "research_youtube_observation_analysis_correction_invalid" },
      );
    }
    const response = await this.mutate(
      RPC.correctResearchYoutubeObservationAnalysis,
      {
        observation_id: observationId,
        observation_hash: observationHash,
        expected_head_event_id: expectedHeadEventId,
        expected_head_hash: expectedHeadHash,
        analysis,
        correction_reason: correctionReason,
      },
    );
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    if (
      !hasExactObjectKeys(source, [
        "ok",
        "event_id",
        "event_hash",
        "analysis_version",
        "origin",
        "retention_expires_at",
        "external_call_started",
        "provider_attempt_count",
        "automatic_retry_started",
      ])
      || source.ok !== true
      || !isUuid(String(source.event_id || "").toLowerCase())
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(source.event_hash || ""))
      || !Number.isInteger(source.analysis_version)
      || source.analysis_version < 2
      || source.origin !== "human_correction"
      || typeof source.retention_expires_at !== "string"
      || !Number.isFinite(Date.parse(source.retention_expires_at))
      || Date.parse(source.retention_expires_at)
        !== expectedRetentionExpiresAtMs
      || source.external_call_started !== false
      || source.provider_attempt_count !== 0
      || source.automatic_retry_started !== false
    ) {
      throw new CreatorApiError(
        "Исправление гипотезы сохранено с неожиданным ответом. Не повторяйте его автоматически.",
        { code: "research_youtube_observation_analysis_response_invalid" },
      );
    }
    return source;
  }

  async configureResearchSourceCollectionPolicy(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const platform = String(options.platform || "").trim().toLowerCase();
    const providerKey = String(
      options.provider_key ?? options.providerKey ?? "",
    ).trim().toLowerCase();
    const status = String(options.status || "").trim().toLowerCase();
    const cadenceHours = Number(
      options.cadence_hours ?? options.cadenceHours,
    );
    const maxRecords = Number(options.max_records ?? options.maxRecords);
    const monthlyHardBudgetUnits = Number(
      options.monthly_hard_budget_units ?? options.monthlyHardBudgetUnits,
    );
    const termsVersion = String(
      options.terms_version ?? options.termsVersion ?? "",
    ).trim();
    const termsAck = options.terms_ack;
    const quotaAck = options.quota_ack;
    const noRetryAck = options.no_retry_ack;
    const legalReviewReference = String(
      options.legal_review_reference ?? options.legalReviewReference ?? "",
    ).replace(/\s+/gu, " ").trim();
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    const expectedPolicyId = options.expected_policy_id
      ?? options.expectedPolicyId
      ?? null;
    const expectedPolicyHash = options.expected_policy_hash
      ?? options.expectedPolicyHash
      ?? null;
    const normalizedPolicyId = expectedPolicyId === null
      ? null
      : String(expectedPolicyId).trim().toLowerCase();
    const normalizedPolicyHash = expectedPolicyHash === null
      ? null
      : String(expectedPolicyHash).trim().toLowerCase();
    const expectedPairValid = normalizedPolicyId === null
      ? normalizedPolicyHash === null
      : isUuid(normalizedPolicyId)
        && RESEARCH_STAGE_HASH_PATTERN.test(normalizedPolicyHash || "");
    if (
      !["youtube", "instagram"].includes(platform)
      || !RESEARCH_COLLECTION_PROVIDER_PATTERN.test(providerKey)
      || !["paused", "enabled"].includes(status)
      || typeof options.automatic_collection_ack !== "boolean"
      || termsVersion.length < 3
      || termsVersion.length > 80
      || typeof termsAck !== "boolean"
      || typeof quotaAck !== "boolean"
      || typeof noRetryAck !== "boolean"
      || !Number.isInteger(cadenceHours)
      || cadenceHours < 24
      || cadenceHours > 720
      || !Number.isInteger(maxRecords)
      || maxRecords < 1
      || maxRecords > 25
      || !Number.isInteger(monthlyHardBudgetUnits)
      || monthlyHardBudgetUnits < 0
      || monthlyHardBudgetUnits > 100
      || (legalReviewReference && (
        legalReviewReference.length < 3
        || legalReviewReference.length > 160
      ))
      || reason.length < 3
      || reason.length > 500
      || !expectedPairValid
      || (status === "enabled" && (
        platform !== "youtube"
        || providerKey !== "youtube_data_api_v3"
        || options.automatic_collection_ack !== true
        || termsVersion !== RESEARCH_YOUTUBE_TERMS_VERSION
        || termsAck !== true
        || quotaAck !== true
        || noRetryAck !== true
        || monthlyHardBudgetUnits < 2
        || !legalReviewReference
      ))
    ) {
      throw new CreatorApiError(
        "Политика автосбора заполнена не полностью или не поддерживается выбранным provider-контуром.",
        { code: "research_collection_policy_invalid" },
      );
    }
    const response = await this.mutate(
      RPC.configureResearchSourceCollectionPolicy,
      {
        run_id: normalizedRunId,
        platform,
        provider_key: providerKey,
        status,
        automatic_collection_ack: options.automatic_collection_ack,
        terms_version: termsVersion,
        terms_ack: termsAck,
        quota_ack: quotaAck,
        no_retry_ack: noRetryAck,
        cadence_hours: cadenceHours,
        max_records: maxRecords,
        monthly_hard_budget_units: monthlyHardBudgetUnits,
        legal_review_reference: legalReviewReference || null,
        reason,
        expected_policy_id: normalizedPolicyId,
        expected_policy_hash: normalizedPolicyHash,
      },
    );
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    const policy = source?.policy;
    const capability = source?.capability;
    if (
      !hasExactObjectKeys(source, ["ok", "policy", "capability"])
      || source.ok !== true
      || !hasExactObjectKeys(policy, [
        "policy_id",
        "policy_hash",
        "policy_version",
        "platform",
        "provider_key",
        "status",
        "automatic_collection_ack",
        "terms_version",
        "terms_ack",
        "quota_ack",
        "no_retry_ack",
        "cadence_hours",
        "max_records",
        "monthly_hard_budget_units",
      ])
      || !isUuid(String(policy.policy_id || "").toLowerCase())
      || !RESEARCH_STAGE_HASH_PATTERN.test(String(policy.policy_hash || ""))
      || !Number.isInteger(policy.policy_version)
      || policy.policy_version < 1
      || policy.platform !== platform
      || policy.provider_key !== providerKey
      || policy.status !== status
      || policy.automatic_collection_ack !== options.automatic_collection_ack
      || policy.terms_version !== termsVersion
      || policy.terms_ack !== termsAck
      || policy.quota_ack !== quotaAck
      || policy.no_retry_ack !== noRetryAck
      || policy.cadence_hours !== cadenceHours
      || policy.max_records !== maxRecords
      || policy.monthly_hard_budget_units !== monthlyHardBudgetUnits
      || !hasExactObjectKeys(capability, [
        "automatic_enqueue_supported",
        "external_call_started",
        "queued_ingestion_is_claimed_by_internal_worker",
        "instagram_enabled",
      ])
      || capability.automatic_enqueue_supported !== (status === "enabled")
      || capability.external_call_started !== false
      || capability.queued_ingestion_is_claimed_by_internal_worker !== true
      || capability.instagram_enabled !== false
    ) {
      throw new CreatorApiError(
        "Политика сохранена с неожиданным ответом. Не повторяйте изменение автоматически.",
        { code: "research_collection_policy_response_invalid" },
      );
    }
    return source;
  }

  async configureResearchWatchlist(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const action = String(options.action || "").trim().toLowerCase();
    if (!["enable", "update", "pause", "resume"].includes(action)) {
      throw new CreatorApiError("Выберите действие для наблюдения за исследованием.", {
        code: "research_watchlist_action_invalid",
      });
    }
    const payload = { run_id: normalizedRunId, action };
    if (["enable", "update", "resume"].includes(action)) {
      const intervalDays = Number(options.refresh_interval_days);
      if (!Number.isInteger(intervalDays) || intervalDays < 3 || intervalDays > 90) {
        throw new CreatorApiError("Интервал наблюдения должен быть от 3 до 90 дней.", {
          code: "research_watchlist_interval_invalid",
        });
      }
      payload.refresh_interval_days = intervalDays;
    }
    const projectId = requiredProjectId(options.project_id ?? options.projectId);
    await this.mutate(RPC.configureResearchWatchlist, payload);
    return this.productResearchStatus(normalizedRunId, { projectId });
  }

  async resolveResearchMarketCategory(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const action = String(options.action || "").trim().toLowerCase();
    const createActions = new Set(["create_and_bind", "create_and_reclassify"]);
    const existingActions = new Set(["bind_existing", "reclassify", "reaffirm"]);
    if (!createActions.has(action) && !existingActions.has(action)) {
      throw new CreatorApiError("Выберите, как подтвердить рыночную категорию.", {
        code: "research_market_decision_action_invalid",
      });
    }
    if (options.confirmation !== true) {
      throw new CreatorApiError("Подтвердите решение по рыночной категории.", {
        code: "research_market_decision_confirmation_required",
      });
    }
    const candidateHash = String(options.candidate_hash || "").trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/u.test(candidateHash)) {
      throw new CreatorApiError("Предложение категории устарело. Обновите исследование.", {
        code: "research_market_category_candidate_stale",
      });
    }
    const payload = {
      run_id: normalizedRunId,
      action,
      candidate_hash: candidateHash,
      confirmation: true,
    };
    if (existingActions.has(action)) {
      const categoryId = String(options.category_id || "").trim();
      if (!isUuid(categoryId)) {
        throw new CreatorApiError("Выберите сохранённую рыночную категорию.", {
          code: "research_market_category_not_found",
        });
      }
      payload.category_id = categoryId;
    } else {
      const canonicalName = String(options.canonical_name || "").replace(/\s+/gu, " ").trim();
      const definition = String(options.definition || "").trim();
      const aliases = [];
      const aliasKeys = new Set();
      (Array.isArray(options.aliases) ? options.aliases : []).forEach((item) => {
        const alias = String(item || "").replace(/\s+/gu, " ").trim();
        const aliasKey = alias.toLocaleLowerCase("ru-RU");
        if (alias && !aliasKeys.has(aliasKey)) {
          aliasKeys.add(aliasKey);
          aliases.push(alias);
        }
      });
      if (canonicalName.length < 2 || canonicalName.length > 160) {
        throw new CreatorApiError("Укажите название рыночной категории длиной 2–160 символов.", {
          code: "canonical_name_invalid",
        });
      }
      if (definition.length < 10 || definition.length > 2000) {
        throw new CreatorApiError("Опишите границы категории длиной 10–2000 символов.", {
          code: "research_market_category_definition_invalid",
        });
      }
      if (aliases.length > 10 || aliases.some((value) => value.length < 2 || value.length > 160)) {
        throw new CreatorApiError("Добавьте не более 10 корректных названий-синонимов.", {
          code: "research_market_aliases_invalid",
        });
      }
      payload.canonical_name = canonicalName;
      payload.definition = definition;
      payload.aliases = aliases;
    }
    const reason = String(options.reason || "").trim();
    if (reason || action === "reaffirm") {
      if (reason.length < 3 || reason.length > 500) {
        throw new CreatorApiError("Кратко объясните решение по категории (3–500 символов).", {
          code: "research_market_decision_reason_invalid",
        });
      }
      payload.reason = reason;
    }
    return this.mutate(
      action === "reaffirm"
        ? RPC.reaffirmResearchMarketCategory
        : RPC.resolveResearchMarketCategory,
      payload,
    );
  }

  async retireResearchMarketCategory(categoryId, options = {}) {
    const normalizedCategoryId = String(categoryId || "").trim().toLowerCase();
    if (!isUuid(normalizedCategoryId)) {
      throw new CreatorApiError("Рыночная категория не найдена.", {
        code: "research_market_category_not_found",
      });
    }
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    if (reason.length < 3 || reason.length > 500) {
      throw new CreatorApiError(
        "Объясните причину вывода категории из использования (3–500 символов).",
        { code: "research_market_category_retirement_reason_invalid" },
      );
    }
    if (options.confirmation !== true) {
      throw new CreatorApiError("Подтвердите вывод категории из использования.", {
        code: "research_market_category_retirement_confirmation_required",
      });
    }
    return this.mutate(RPC.retireResearchMarketCategory, {
      category_id: normalizedCategoryId,
      reason,
      confirmation: true,
    });
  }

  searchResearchMarketCategories(runId, query) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const normalizedQuery = String(query || "").replace(/\s+/gu, " ").trim();
    if (normalizedQuery.length < 2 || normalizedQuery.length > 160) {
      throw new CreatorApiError("Введите точное название или синоним категории.", {
        code: "research_market_registry_query_invalid",
      });
    }
    return this.call(
      RPC.researchMarketCategoryRegistry,
      this.withOrganization({
        run_id: normalizedRunId,
        query: normalizedQuery,
        limit: 20,
      }),
    );
  }

  researchOutcomeLearningScopes(runId) {
    const normalizedRunId = this.requireResearchRunId(runId);
    return this.call(
      RPC.researchOutcomeLearningScopes,
      this.withOrganization({ run_id: normalizedRunId, limit: 50 }),
    );
  }

  researchOutcomeLearningStatus(scope) {
    return this.call(
      RPC.researchOutcomeLearningStatus,
      this.withOrganization(requireResearchOutcomeScope(scope)),
    );
  }

  refreshResearchOutcomeLearning(scope) {
    return this.mutate(
      RPC.refreshResearchOutcomeLearning,
      requireResearchOutcomeScope(scope),
    );
  }

  decideResearchOutcomeLearning(scope, options = {}) {
    requireResearchOutcomeScope(scope);
    const action = String(options.action || "").trim().toLowerCase();
    if (!["activate", "reject", "quarantine", "deactivate", "revert"].includes(action)) {
      throw new CreatorApiError("Выберите допустимое решение по обучающей памяти.", {
        code: "research_outcome_decision_action_invalid",
      });
    }
    if (options.confirmation !== true) {
      throw new CreatorApiError("Подтвердите решение по обучающей памяти.", {
        code: "research_outcome_decision_confirmation_required",
      });
    }
    const candidateId = String(options.candidate_id || "").trim().toLowerCase();
    const candidateHash = String(options.candidate_hash || "").trim().toLowerCase();
    const candidateVersion = Number(options.candidate_version);
    const expectedScopeVersion = Number(options.expected_scope_version);
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    if (!isUuid(candidateId)) {
      throw new CreatorApiError("Кандидат обучения устарел. Обновите статус.", {
        code: "research_outcome_candidate_not_found",
      });
    }
    if (!/^[0-9a-f]{64}$/u.test(candidateHash)) {
      throw new CreatorApiError("Кандидат обучения изменился. Обновите статус.", {
        code: "research_outcome_candidate_stale",
      });
    }
    if (
      !Number.isInteger(candidateVersion)
      || candidateVersion < 1
      || candidateVersion > 100000
      || !Number.isInteger(expectedScopeVersion)
      || expectedScopeVersion < 0
      || expectedScopeVersion > 100000
    ) {
      throw new CreatorApiError("Версия обучающей памяти изменилась. Обновите статус.", {
        code: "research_outcome_decision_version_invalid",
      });
    }
    if (reason.length < 3 || reason.length > 500) {
      throw new CreatorApiError("Кратко объясните решение (3–500 символов).", {
        code: "research_outcome_decision_reason_invalid",
      });
    }
    const payload = {
      candidate_id: candidateId,
      action,
      candidate_version: candidateVersion,
      candidate_hash: candidateHash,
      expected_scope_version: expectedScopeVersion,
      reason,
      confirmation: true,
    };
    if (action === "revert") {
      const rollbackId = String(options.rollback_memory_version_id || "")
        .trim().toLowerCase();
      if (!isUuid(rollbackId)) {
        throw new CreatorApiError("Точная версия для отката больше недоступна.", {
          code: "research_outcome_rollback_target_invalid",
        });
      }
      payload.rollback_memory_version_id = rollbackId;
    } else if (options.rollback_memory_version_id) {
      throw new CreatorApiError("Версия отката допустима только для действия «откатить».", {
        code: "research_outcome_rollback_target_unexpected",
      });
    }
    return this.mutate(RPC.decideResearchOutcomeLearning, payload);
  }

  researchYoutubeStatus(ingestionId) {
    const normalizedId = String(ingestionId || "").trim().toLowerCase();
    if (!isUuid(normalizedId)) {
      throw new CreatorApiError("Не удалось определить запуск YouTube‑проверки.", {
        code: "research_youtube_ingestion_not_found",
      });
    }
    return this.call(RPC.researchYoutubeStatus, { ingestion_id: normalizedId });
  }

  async requestResearchYoutube(runId, options = {}) {
    const normalizedRunId = this.requireResearchRunId(runId);
    const mode = String(options.mode || "").trim().toLowerCase();
    if (!["manual_canary", "category_refresh"].includes(mode)) {
      throw new CreatorApiError("Выберите ручной canary или явное обновление категории.", {
        code: "research_youtube_request_payload_invalid",
      });
    }
    const queryText = String(options.query_text || "")
      .replace(/\s+/gu, " ")
      .trim();
    const regionCode = String(options.region_code || "").trim().toUpperCase();
    const relevanceLanguage = String(options.relevance_language || "").trim();
    const publishedAfterRaw = String(options.published_after || "").trim();
    const maxResults = Number(options.max_results);
    const expectedResults = mode === "manual_canary" ? 1 : maxResults;
    if (
      queryText.length < 2
      || queryText.length > 200
      || /[\u0000-\u001f\u007f]/u.test(queryText)
    ) {
      throw new CreatorApiError("Укажите точный YouTube‑запрос длиной 2–200 символов.", {
        code: "research_youtube_query_invalid",
      });
    }
    if (regionCode && !/^[A-Z]{2}$/u.test(regionCode)) {
      throw new CreatorApiError("Код региона должен состоять из двух латинских букв.", {
        code: "research_youtube_locale_invalid",
      });
    }
    if (
      relevanceLanguage
      && !/^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/u.test(relevanceLanguage)
    ) {
      throw new CreatorApiError("Проверьте языковой код YouTube, например ru или zh-Hans.", {
        code: "research_youtube_locale_invalid",
      });
    }
    let publishedAfter = null;
    if (publishedAfterRaw) {
      const timestamp = Date.parse(publishedAfterRaw);
      if (
        !Number.isFinite(timestamp)
        || timestamp < Date.now() - 366 * 86_400_000
        || timestamp > Date.now() + 60_000
      ) {
        throw new CreatorApiError("Дата начала поиска должна быть в пределах последних 366 дней.", {
          code: "research_youtube_published_after_invalid",
        });
      }
      publishedAfter = new Date(timestamp).toISOString();
    }
    if (
      !Number.isInteger(expectedResults)
      || expectedResults < 1
      || expectedResults > 25
      || (mode === "manual_canary" && maxResults !== 1)
    ) {
      throw new CreatorApiError("Canary проверяет 1 видео, обновление — от 1 до 25.", {
        code: "research_youtube_quota_plan_invalid",
      });
    }
    if (
      options.quota_ack !== true
      || options.no_retry_ack !== true
      || options.terms_ack !== true
      || String(options.terms_version || "") !== RESEARCH_YOUTUBE_TERMS_VERSION
    ) {
      throw new CreatorApiError("Подтвердите квоту, отсутствие повтора и актуальные условия YouTube API.", {
        code: "research_youtube_confirmation_required",
      });
    }
    const payload = {
      run_id: normalizedRunId,
      query_text: queryText,
      region_code: regionCode || null,
      relevance_language: relevanceLanguage || null,
      published_after: publishedAfter,
      max_results: expectedResults,
      max_http_requests: 2,
      max_quota_units: 2,
      quota_ack: true,
      no_retry_ack: true,
      terms_ack: true,
      terms_version: RESEARCH_YOUTUBE_TERMS_VERSION,
    };
    const rpcName = mode === "manual_canary"
      ? RPC.requestResearchYoutubeCanary
      : RPC.requestResearchYoutubeRefresh;
    const requested = await this.mutate(rpcName, payload);
    const source = requested?.data && typeof requested.data === "object"
      && !Array.isArray(requested.data)
      ? requested.data
      : requested;
    const ingestion = source?.ingestion;
    const ingestionId = String(ingestion?.id || "").trim().toLowerCase();
    if (
      source?.ok !== true
      || source?.version !== "research-youtube-live-ingestion-v1"
      || !isUuid(ingestionId)
      || ingestion?.status !== "queued"
      || ingestion?.mode !== mode
      || Number(ingestion?.max_http_requests) !== 2
      || Number(ingestion?.max_quota_units) !== 2
    ) {
      throw new CreatorApiError("Сервер не подтвердил ограниченный план YouTube‑запроса.", {
        code: "research_youtube_request_response_invalid",
      });
    }
    let execution;
    try {
      execution = await this.invokeResearchIngestion(ingestionId);
    } catch (error) {
      error.job = { id: ingestionId, status: "queued", kind: "youtube_ingestion" };
      throw error;
    }
    return { request: source, execution };
  }

  decideResearchYoutubeRollout(options = {}) {
    const decision = String(options.decision || "").trim().toLowerCase();
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    if (!["enable_category_refresh", "pause_category_refresh"].includes(decision)) {
      throw new CreatorApiError("Выберите включение или паузу обновлений YouTube.", {
        code: "research_youtube_rollout_decision_invalid",
      });
    }
    if (reason.length < 3 || reason.length > 500) {
      throw new CreatorApiError("Кратко объясните решение по rollout (3–500 символов).", {
        code: "research_youtube_rollout_payload_invalid",
      });
    }
    if (
      options.terms_ack !== true
      || String(options.terms_version || "") !== RESEARCH_YOUTUBE_TERMS_VERSION
    ) {
      throw new CreatorApiError("Подтвердите актуальную версию условий YouTube API.", {
        code: "research_youtube_confirmation_required",
      });
    }
    const payload = {
      decision,
      reason,
      terms_ack: true,
      terms_version: RESEARCH_YOUTUBE_TERMS_VERSION,
    };
    if (decision === "enable_category_refresh") {
      const canaryId = String(options.canary_ingestion_id || "").trim().toLowerCase();
      if (!isUuid(canaryId)) {
        throw new CreatorApiError("Сначала завершите свежий двухэтапный canary.", {
          code: "research_youtube_fresh_canary_required",
        });
      }
      payload.canary_ingestion_id = canaryId;
    }
    return this.mutate(RPC.decideResearchYoutubeRollout, payload);
  }

  decideResearchYoutubeCandidate(options = {}) {
    const ingestionId = String(options.ingestion_id || "").trim().toLowerCase();
    const observationId = String(options.observation_id || "").trim().toLowerCase();
    const observationHash = String(options.observation_hash || "").trim().toLowerCase();
    const decision = String(options.decision || "").trim().toLowerCase();
    const reason = String(options.reason || "").replace(/\s+/gu, " ").trim();
    if (
      !isUuid(ingestionId)
      || !isUuid(observationId)
      || !/^[0-9a-f]{64}$/u.test(observationHash)
      || !["confirm_candidate", "exclude_candidate"].includes(decision)
    ) {
      throw new CreatorApiError("Кандидат YouTube изменился. Обновите статус.", {
        code: "research_youtube_candidate_stale",
      });
    }
    if (options.confirmation !== true || reason.length < 3 || reason.length > 500) {
      throw new CreatorApiError("Подтвердите временное решение и укажите причину (3–500 символов).", {
        code: "research_youtube_candidate_payload_invalid",
      });
    }
    return this.mutate(RPC.decideResearchYoutubeCandidate, {
      ingestion_id: ingestionId,
      observation_id: observationId,
      observation_hash: observationHash,
      decision,
      reason,
      confirmation: true,
    });
  }

  async invokeResearchIngestion(ingestionId) {
    const normalizedId = String(ingestionId || "").trim().toLowerCase();
    if (!isUuid(normalizedId)) {
      throw new CreatorApiError("Не удалось определить YouTube‑запуск.", {
        code: "research_youtube_ingestion_not_found",
      });
    }
    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла перед ручным YouTube‑запросом.", {
        code: "auth_session_required",
      });
    }
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(
        RESEARCH_INGESTION_FUNCTION,
        {
          body: { action: "ingest", ingestion_id: normalizedId },
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      ));
    } catch {
      throw new CreatorApiError("Запуск сохранён, но транспорт YouTube не подтвердил начало.", {
        code: "research_youtube_ingestion_unavailable",
      });
    }
    if (error) throw await researchIngestionFunctionError(error);
    const source = data?.data && typeof data.data === "object" && !Array.isArray(data.data)
      ? data.data
      : data;
    if (
      !source
      || typeof source !== "object"
      || Array.isArray(source)
      || source.ok !== true
      || source.version !== "research-youtube-live-ingestion-v1"
      || String(source.ingestion?.id || "").toLowerCase() !== normalizedId
      || !["queued", "processing", "completed", "failed"].includes(
        String(source.ingestion?.status || ""),
      )
    ) {
      throw new CreatorApiError("YouTube‑транспорт вернул неполный статус. Не повторяйте запрос автоматически.", {
        code: "research_youtube_ingestion_response_invalid",
      });
    }
    return source;
  }

  saveCreativeBriefDraft(runId, draft, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    return this.mutate(RPC.saveCreativeBriefDraft, {
      run_id: this.requireResearchRunId(runId),
      project_id: requiredProjectId(projectIdSnake || projectId),
      title: draft?.title,
      brief: draft?.brief,
      source_ids: draft?.source_ids,
      task_blueprint: draft?.task_blueprint,
    });
  }

  approveCreativeBrief(draftId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedDraftId = String(draftId || "").trim();
    if (!normalizedDraftId || normalizedDraftId.length > 128) {
      throw new CreatorApiError("Сначала сохраните актуальный черновик ТЗ.", {
        code: "creative_brief_draft_invalid",
      });
    }
    return this.mutate(RPC.approveCreativeBrief, {
      draft_id: normalizedDraftId,
      project_id: requiredProjectId(projectIdSnake || projectId),
    });
  }

  requireResearchRunId(value) {
    const runId = String(value || "").trim();
    if (!runId || runId.length > 128) {
      throw new CreatorApiError("Не удалось определить исследование. Начните новый разбор.", {
        code: "product_research_run_invalid",
      });
    }
    return runId;
  }

  async invokeProductResearch(payload) {
    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла. Войдите снова перед запуском анализа.", {
        code: "auth_session_required",
      });
    }

    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(PRODUCT_RESEARCH_FUNCTION, {
        body: payload,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Не удалось запустить анализ товара. Повторите попытку позже.", {
        code: "product_research_request_failed",
      });
    }
    if (error) {
      throw new CreatorApiError("Сервис анализа товара временно недоступен. Запуск сохранён — проверьте его статус позже.", {
        code: error?.code || "product_research_request_failed",
      });
    }
    if (
      data && typeof data === "object" && !Array.isArray(data)
      && data.ok === false && typeof data.code === "string"
    ) {
      throw new CreatorApiError("Сохранённый ответ нельзя повторно проверить.", {
        code: data.code,
      });
    }
    if (!data || typeof data !== "object" || Array.isArray(data) || data.ok === false || data.error) {
      throw new CreatorApiError("Сервис анализа товара вернул некорректный ответ.", {
        code: "product_research_response_invalid",
      });
    }
    return data;
  }

  contentReviewCatalog({ limit = 50, projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedLimit = Number(limit);
    if (!Number.isInteger(normalizedLimit) || normalizedLimit < 1 || normalizedLimit > 50) {
      throw new CreatorApiError("История проверки может содержать от 1 до 50 записей.", {
        code: "content_review_limit_invalid",
      });
    }
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.call(RPC.contentReviewCatalog, this.withOrganization({
      media_limit: normalizedLimit,
      run_limit: normalizedLimit,
      project_id: normalizedProjectId,
    }));
  }

  async prepareContentReviewEvidence({
    mediaId,
    frameCount,
    projectId = "",
    project_id: projectIdSnake = "",
  }) {
    const normalizedMediaId = String(mediaId || "").trim();
    const normalizedFrameCount = Number(frameCount);
    if (!isUuid(normalizedMediaId)) {
      throw new CreatorApiError("Не удалось определить видео для сохранения кадров.", {
        code: "content_review_media_required",
      });
    }
    if (!Number.isInteger(normalizedFrameCount) || normalizedFrameCount !== 5) {
      throw new CreatorApiError("Для MP4 нужно подготовить четыре кадра и пятый JPEG-атлас.", {
        code: "content_review_frames_invalid",
      });
    }
    const response = await this.mutate(RPC.prepareContentReviewEvidence, {
      media_id: normalizedMediaId,
      frame_count: normalizedFrameCount,
      project_id: requiredProjectId(projectIdSnake || projectId),
    });
    const source = response?.data && typeof response.data === "object" && !Array.isArray(response.data)
      ? response.data
      : response;
    const evidenceId = String(source?.evidence_id || source?.evidence?.id || "").trim();
    const objectNames = Array.isArray(source?.frame_object_names)
      ? source.frame_object_names.map((value) => String(value || "").trim())
      : [];
    const expiresAt = String(source?.expires_at || source?.evidence?.expires_at || "").trim();
    if (
      !isUuid(evidenceId)
      || objectNames.length !== normalizedFrameCount
      || new Set(objectNames).size !== objectNames.length
      || !Number.isFinite(Date.parse(expiresAt))
      || Date.parse(expiresAt) <= Date.now()
    ) {
      throw new CreatorApiError("Сервер не подготовил защищённые места для всех кадров.", {
        code: "content_review_evidence_prepare_invalid",
      });
    }
    objectNames.forEach((objectName) => this.assertPrivateObjectKey(objectName));
    return {
      evidenceId,
      frameObjectNames: objectNames,
      expiresAt,
    };
  }

  async commitContentReviewEvidence({
    evidenceId,
    frames,
    technicalMetrics,
    idempotencyKey = "",
    projectId = "",
    project_id: projectIdSnake = "",
  }) {
    const normalizedEvidenceId = String(evidenceId || "").trim();
    const normalizedIdempotencyKey = String(idempotencyKey || "").trim().toLowerCase();
    if (
      !isUuid(normalizedEvidenceId)
      || !Array.isArray(frames)
      || frames.length !== 5
      || !technicalMetrics
      || typeof technicalMetrics !== "object"
      || Array.isArray(technicalMetrics)
      || String(technicalMetrics.source_type || "").toLowerCase() !== "video"
      || !validContentReviewTechnicalMetrics(technicalMetrics)
      || (normalizedIdempotencyKey && !isUuid(normalizedIdempotencyKey))
    ) {
      throw new CreatorApiError("Не удалось подтвердить полный набор контрольных кадров.", {
        code: "content_review_evidence_commit_invalid",
      });
    }
    const normalizedFrames = frames.map((frame) => {
      const objectName = String(frame?.object_name || "").trim();
      const sha256 = String(frame?.sha256 || "").trim().toLowerCase();
      const sizeBytes = Number(frame?.size_bytes);
      const timecodeSeconds = Number(frame?.timecode_seconds);
      this.assertPrivateObjectKey(objectName);
      if (
        !/^[0-9a-f]{64}$/u.test(sha256)
        || !Number.isInteger(sizeBytes)
        || sizeBytes < 128
        || sizeBytes > 250_000
        || !Number.isFinite(timecodeSeconds)
        || timecodeSeconds < 0
        || timecodeSeconds > 3_600
      ) {
        throw new CreatorApiError("Один из контрольных кадров имеет неверные параметры.", {
          code: "content_review_evidence_frame_invalid",
        });
      }
      return {
        object_name: objectName,
        sha256,
        size_bytes: sizeBytes,
        timecode_seconds: Math.round(timecodeSeconds * 1_000) / 1_000,
      };
    });
    if (new Set(normalizedFrames.map((frame) => frame.object_name)).size !== normalizedFrames.length) {
      throw new CreatorApiError("Контрольные кадры должны иметь разные защищённые имена.", {
        code: "content_review_evidence_frame_invalid",
      });
    }
    const commitPayload = {
      evidence_id: normalizedEvidenceId,
      frames: normalizedFrames,
      technical_metrics: technicalMetrics,
      project_id: requiredProjectId(projectIdSnake || projectId),
    };
    const response = normalizedIdempotencyKey
      ? await this.call(RPC.commitContentReviewEvidence, {
          ...this.withOrganization(commitPayload),
          idempotency_key: normalizedIdempotencyKey,
        })
      : await this.mutate(RPC.commitContentReviewEvidence, commitPayload);
    const source = response?.data && typeof response.data === "object" && !Array.isArray(response.data)
      ? response.data
      : response;
    const returnedEvidenceId = String(source?.evidence_id || source?.evidence?.id || normalizedEvidenceId).trim();
    const status = String(source?.status || source?.evidence?.status || "").trim().toLowerCase();
    if (returnedEvidenceId !== normalizedEvidenceId || status !== "ready") {
      throw new CreatorApiError("Сервер не подтвердил сохранение контрольных кадров.", {
        code: "content_review_evidence_commit_invalid",
      });
    }
    return { ...source, evidence_id: normalizedEvidenceId, status: "ready" };
  }

  async startContentReview(input, { onRunCreated } = {}) {
    const mediaId = String(input?.media_id || "").trim();
    const normalizedProjectId = requiredProjectId(input?.project_id ?? input?.projectId);
    const platform = String(input?.platform || "").trim().toLowerCase();
    const contentKind = String(input?.content_kind || "").trim().toLowerCase();
    const productCategory = String(input?.product_category || "").trim().toLowerCase();
    const peoplePresent = String(input?.people_present || "unknown").trim().toLowerCase();
    const supportedPlatforms = new Set(["instagram", "youtube", "vk", "tiktok", "telegram", "wildberries", "other"]);
    const supportedContentKinds = new Set(["unknown", "informational", "advertising"]);
    const supportedCategories = new Set(["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]);
    if (!mediaId || mediaId.length > 180) {
      throw new CreatorApiError("Выберите точное изображение или MP4 из раздела «Материалы».", {
        code: "content_review_media_required",
      });
    }
    if (!supportedPlatforms.has(platform) || !supportedContentKinds.has(contentKind)) {
      throw new CreatorApiError("Проверьте площадку и рекламный статус материала.", {
        code: "content_review_context_invalid",
      });
    }
    if (!supportedCategories.has(productCategory) || !["unknown", "yes", "no"].includes(peoplePresent)) {
      throw new CreatorApiError("Проверьте категорию товара и наличие людей в кадре.", {
        code: "content_review_context_invalid",
      });
    }
    if (peoplePresent !== "no" && input?.external_ai_processing_confirmed !== true) {
      throw new CreatorApiError("Подтвердите законное основание и информирование для передачи контрольных кадров с узнаваемыми людьми внешнему AI-провайдеру.", {
        code: "content_review_external_ai_processing_required",
      });
    }
    const captionText = String(input?.caption_text || "").trim();
    const scriptText = String(input?.script_text || "").trim();
    if (captionText.length > 6_000 || scriptText.length > 6_000) {
      throw new CreatorApiError("Сократите подпись и сценарий до 6000 символов каждый.", {
        code: "content_review_text_too_large",
      });
    }
    const technicalMetrics = input?.technical_metrics;
    if (!technicalMetrics || typeof technicalMetrics !== "object" || Array.isArray(technicalMetrics)) {
      throw new CreatorApiError("Браузер не смог подготовить технические параметры файла.", {
        code: "content_review_metrics_required",
      });
    }
    const sourceType = String(technicalMetrics.source_type || "").toLowerCase();
    if (!validContentReviewTechnicalMetrics(technicalMetrics)) {
      throw new CreatorApiError("Технические параметры файла неполны или повреждены.", {
        code: "content_review_metrics_invalid",
      });
    }
    const evidenceId = String(input?.evidence_id || "").trim();
    if (sourceType === "video" && !isUuid(evidenceId)) {
      throw new CreatorApiError("Сначала сохраните контрольные кадры MP4.", {
        code: "content_review_evidence_required",
      });
    }
    if (evidenceId && !isUuid(evidenceId)) {
      throw new CreatorApiError("Сохранённый набор кадров имеет неверный номер.", {
        code: "content_review_evidence_invalid",
      });
    }

    const payload = {
      media_id: mediaId,
      project_id: normalizedProjectId,
      ...(input?.parent_review_id ? { parent_review_id: String(input.parent_review_id) } : {}),
      platform,
      content_kind: contentKind,
      product_category: productCategory,
      caption_text: captionText,
      script_text: scriptText,
      advertiser_name: String(input?.advertiser_name || "").trim(),
      erid: String(input?.erid || "").trim(),
      technical_metrics: technicalMetrics,
      ...(evidenceId ? { evidence_id: evidenceId } : {}),
      rights_confirmed: input?.rights_confirmed === true,
      claims_verified: input?.claims_verified === true,
      ad_label_confirmed: input?.ad_label_confirmed === true,
      ord_confirmed: input?.ord_confirmed === true,
      audience_over_10000: input?.audience_over_10000 === true,
      rkn_registered: input?.rkn_registered === true,
      people_present: peoplePresent,
      person_consent_confirmed: input?.person_consent_confirmed === true,
      external_ai_processing_confirmed: input?.external_ai_processing_confirmed === true,
      ai_generated: input?.ai_generated === true,
      ai_disclosure_confirmed: input?.ai_disclosure_confirmed === true,
      captions_confirmed: input?.captions_confirmed === true,
      mandatory_warning_confirmed: input?.mandatory_warning_confirmed === true,
    };
    const created = await this.mutate(RPC.startContentReview, payload);
    const source = created?.data && typeof created.data === "object" ? created.data : created;
    const run = source?.run || source?.review || {};
    const reviewId = String(run?.id || source?.review_id || source?.id || "").trim();
    if (!reviewId) {
      throw new CreatorApiError("Сервер не вернул номер проверки. Обновите раздел и повторите.", {
        code: "content_review_run_missing",
      });
    }
    if (typeof onRunCreated === "function") {
      try {
        onRunCreated({ ...run, id: reviewId, status: String(run?.status || "queued") });
      } catch {
        // UI recovery must never cancel the durable server-side run.
      }
    }

    const accepted = {
      ok: true,
      status: "background_queued",
    };
    // This dispatch is only a latency optimization. The durable worker owns
    // completion, so the user never waits for an Edge/provider round trip and
    // closing the tab cannot invalidate the queued run.
    void this.invokeContentReview({
      action: "analyze",
      review_id: reviewId,
      project_id: normalizedProjectId,
    }).catch(() => {});
    return {
      ...source,
      run: { ...run, id: reviewId },
      analysis_request: accepted,
    };
  }

  async startGeneratedVideoReview({ mediaId, evidenceId, projectId = "", project_id: projectIdSnake = "" } = {}, {
    onRunCreated,
  } = {}) {
    const normalizedMediaId = String(mediaId || "").trim();
    const normalizedEvidenceId = String(evidenceId || "").trim();
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    if (!isUuid(normalizedMediaId) || !isUuid(normalizedEvidenceId)) {
      throw new CreatorApiError("Сначала дождитесь сохранения точного MP4 и его контрольных кадров.", {
        code: "generated_video_review_evidence_required",
      });
    }
    const created = await this.mutate(RPC.startGeneratedVideoReview, {
      media_id: normalizedMediaId,
      evidence_id: normalizedEvidenceId,
      project_id: normalizedProjectId,
    });
    const source = created?.data && typeof created.data === "object"
      ? created.data
      : created;
    const run = source?.run || source?.review || {};
    const reviewId = String(
      run?.id || source?.review_id || source?.id || "",
    ).trim();
    if (!isUuid(reviewId)) {
      throw new CreatorApiError("Сервер не вернул номер проверки готового ролика.", {
        code: "content_review_run_missing",
      });
    }
    if (source?.transcription_requested !== false) {
      throw new CreatorApiError("Без отдельного разрешения транскрипция ролика должна оставаться выключенной.", {
        code: "generated_video_transcription_guard_failed",
      });
    }
    if (typeof onRunCreated === "function") {
      try {
        onRunCreated({
          ...run,
          id: reviewId,
          status: String(run?.status || "queued"),
        });
      } catch {
        // UI recovery is best effort; the durable run remains authoritative.
      }
    }
    void this.invokeContentReview({
      action: "analyze",
      review_id: reviewId,
      project_id: normalizedProjectId,
    }).catch(() => {});
    return {
      ...source,
      run: { ...run, id: reviewId },
      analysis_request: {
        ok: true,
        status: "background_queued",
        transcription_requested: false,
      },
    };
  }

  contentReviewStatus(reviewId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.call(RPC.contentReviewStatus, this.withOrganization({
      review_id: this.requireContentReviewId(reviewId),
      project_id: normalizedProjectId,
    }));
  }

  decideContentReview(reviewId, decision, comment, {
    resolvedRecommendationCodes = [],
    riskAcknowledgements = [],
    mediaWatchedConfirmed = false,
    projectId = "",
    project_id: projectIdSnake = "",
    soundAssessment = null,
  } = {}) {
    const normalizedDecision = String(decision || "").trim().toLowerCase();
    const normalizedComment = String(comment || "").trim();
    if (!["approved", "needs_changes", "rejected"].includes(normalizedDecision)) {
      throw new CreatorApiError("Выберите итог проверки: одобрить, доработать или отклонить.", {
        code: "content_review_decision_invalid",
      });
    }
    if (normalizedComment.length < 10 || normalizedComment.length > 2_000) {
      throw new CreatorApiError("Объясните решение текстом от 10 до 2000 символов.", {
        code: "content_review_decision_reason_invalid",
      });
    }
    const safeResolvedCodes = normalizeContentReviewCodes(resolvedRecommendationCodes);
    const safeRiskAcknowledgements = normalizeContentReviewCodes(riskAcknowledgements);
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const safeSoundAssessment = normalizeGeneratedVideoSoundAssessment(
      soundAssessment,
      { required: false },
    );
    if (mediaWatchedConfirmed !== true) {
      throw new CreatorApiError("Перед решением полностью просмотрите защищённый файл со звуком и субтитрами.", {
        code: "content_review_media_watch_required",
      });
    }
    return this.mutate(RPC.decideContentReview, {
      review_id: this.requireContentReviewId(reviewId),
      decision: normalizedDecision,
      comment: normalizedComment,
      resolved_recommendation_codes: safeResolvedCodes,
      risk_acknowledgements: safeRiskAcknowledgements,
      media_watched_confirmed: true,
      project_id: normalizedProjectId,
      ...(safeSoundAssessment
        ? { sound_assessment: safeSoundAssessment }
        : {}),
    });
  }

  recoverContentReviewSoundAssessment(reviewId, soundAssessment, {
    mediaWatchedConfirmed = false,
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
    if (mediaWatchedConfirmed !== true) {
      throw new CreatorApiError("Перед восстановлением оценки полностью прослушайте защищённый MP4 с включённым звуком.", {
        code: "content_review_sound_recovery_confirmation_required",
      });
    }
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const safeSoundAssessment = normalizeGeneratedVideoSoundAssessment(
      soundAssessment,
      { required: true },
    );
    return this.mutate(RPC.recoverContentReviewSoundAssessment, {
      review_id: this.requireContentReviewId(reviewId),
      project_id: normalizedProjectId,
      media_watched_confirmed: true,
      sound_assessment: safeSoundAssessment,
    });
  }

  restoreProjectPlacement(reviewId, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    return this.mutate(RPC.restoreProjectPlacement, {
      review_id: this.requireContentReviewId(reviewId),
      project_id: requiredProjectId(projectIdSnake || projectId),
    });
  }

  approveGeneratedPhotoReviewWithContext(reviewId, comment, context, {
    riskAcknowledgements = [],
    resolvedRecommendationCodes = [],
    mediaWatchedConfirmed = false,
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
    const normalizedComment = String(comment || "").trim();
    const productCategory = String(context?.productCategory || "").trim().toLowerCase();
    const advertiserName = String(context?.advertiserName || "").trim();
    const erid = String(context?.erid || "").trim();
    const peoplePresent = String(context?.peoplePresent || "").trim().toLowerCase();
    if (normalizedComment.length < 10 || normalizedComment.length > 2_000) {
      throw new CreatorApiError("Объясните решение текстом от 10 до 2000 символов.", {
        code: "content_review_decision_reason_invalid",
      });
    }
    if (
      !["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]
        .includes(productCategory)
      || advertiserName.length < 2
      || advertiserName.length > 240
      || erid.length < 6
      || erid.length > 180
      || !["yes", "no"].includes(peoplePresent)
    ) {
      throw new CreatorApiError("Заполните категорию, рекламодателя, ERID и наличие людей для точного PNG.", {
        code: "generated_photo_context_approval_invalid",
      });
    }
    if (
      context?.adLabelConfirmed !== true
      || context?.ordConfirmed !== true
      || context?.rightsConfirmed !== true
      || context?.claimsVerified !== true
      || (peoplePresent === "yes" && context?.personConsentConfirmed !== true)
      || mediaWatchedConfirmed !== true
    ) {
      throw new CreatorApiError("Подтвердите осмотр PNG, маркировку, ОРД, права, claims и согласия людей.", {
        code: "generated_photo_context_approval_invalid",
      });
    }
    const safeRiskAcknowledgements = normalizeContentReviewCodes(riskAcknowledgements);
    const safeResolvedCodes = normalizeContentReviewCodes(resolvedRecommendationCodes);
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.mutate(RPC.approveGeneratedPhotoWithContext, {
      review_id: this.requireContentReviewId(reviewId),
      reason: normalizedComment,
      product_category: productCategory,
      advertiser_name: advertiserName,
      erid,
      people_present: peoplePresent,
      media_watched_confirmed: true,
      ad_label_confirmed: true,
      ord_confirmed: true,
      rights_confirmed: true,
      claims_verified: true,
      person_consent_confirmed: context?.personConsentConfirmed === true,
      ai_disclosure_confirmed: context?.aiDisclosureConfirmed === true,
      mandatory_warning_confirmed: context?.mandatoryWarningConfirmed === true,
      audience_over_10000: context?.audienceOver10000 === true,
      rkn_registered: context?.rknRegistered === true,
      risk_acknowledgements: safeRiskAcknowledgements,
      resolved_recommendation_codes: safeResolvedCodes,
      project_id: normalizedProjectId,
    });
  }

  approveGeneratedVideoReviewWithContext(reviewId, comment, context, {
    riskAcknowledgements = [],
    resolvedRecommendationCodes = [],
    mediaWatchedConfirmed = false,
    projectId = "",
    project_id: projectIdSnake = "",
    soundAssessment = null,
  } = {}) {
    const normalizedComment = String(comment || "").trim();
    const productCategory = String(context?.productCategory || "").trim().toLowerCase();
    const advertiserName = String(context?.advertiserName || "").trim();
    const erid = String(context?.erid || "").trim();
    const peoplePresent = String(context?.peoplePresent || "").trim().toLowerCase();
    if (normalizedComment.length < 10 || normalizedComment.length > 2_000) {
      throw new CreatorApiError("Объясните решение текстом от 10 до 2000 символов.", {
        code: "content_review_decision_reason_invalid",
      });
    }
    if (
      !["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]
        .includes(productCategory)
      || advertiserName.length < 2
      || advertiserName.length > 240
      || erid.length < 6
      || erid.length > 180
      || !["yes", "no"].includes(peoplePresent)
    ) {
      throw new CreatorApiError("Заполните категорию, рекламодателя, ERID и наличие людей для точного MP4.", {
        code: "generated_video_context_approval_invalid",
      });
    }
    if (
      context?.adLabelConfirmed !== true
      || context?.ordConfirmed !== true
      || context?.rightsConfirmed !== true
      || context?.claimsVerified !== true
      || (context?.captionsRequired === true && context?.captionsConfirmed !== true)
      || (peoplePresent === "yes" && context?.personConsentConfirmed !== true)
      || mediaWatchedConfirmed !== true
    ) {
      throw new CreatorApiError("Подтвердите полный просмотр MP4, маркировку, ОРД, права, claims, субтитры и согласия людей.", {
        code: "generated_video_context_approval_invalid",
      });
    }
    const safeRiskAcknowledgements = normalizeContentReviewCodes(riskAcknowledgements);
    const safeResolvedCodes = normalizeContentReviewCodes(resolvedRecommendationCodes);
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const safeSoundAssessment = normalizeGeneratedVideoSoundAssessment(
      soundAssessment,
      { required: true },
    );
    return this.mutate(RPC.approveGeneratedVideoWithContext, {
      review_id: this.requireContentReviewId(reviewId),
      reason: normalizedComment,
      product_category: productCategory,
      advertiser_name: advertiserName,
      erid,
      people_present: peoplePresent,
      media_watched_confirmed: true,
      ad_label_confirmed: true,
      ord_confirmed: true,
      rights_confirmed: true,
      claims_verified: true,
      captions_confirmed: context?.captionsConfirmed === true,
      person_consent_confirmed: context?.personConsentConfirmed === true,
      ai_disclosure_confirmed: context?.aiDisclosureConfirmed === true,
      mandatory_warning_confirmed: context?.mandatoryWarningConfirmed === true,
      audience_over_10000: context?.audienceOver10000 === true,
      rkn_registered: context?.rknRegistered === true,
      risk_acknowledgements: safeRiskAcknowledgements,
      resolved_recommendation_codes: safeResolvedCodes,
      project_id: normalizedProjectId,
      sound_assessment: safeSoundAssessment,
    });
  }

  requireContentReviewId(value) {
    const reviewId = String(value || "").trim();
    if (!reviewId || reviewId.length > 180) {
      throw new CreatorApiError("Не удалось определить проверку. Обновите раздел.", {
        code: "content_review_id_invalid",
      });
    }
    return reviewId;
  }

  async invokeContentReview(payload) {
    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла. Войдите снова перед проверкой контента.", {
        code: "auth_session_required",
      });
    }
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(CONTENT_REVIEW_FUNCTION, {
        body: payload,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Не удалось запустить проверку контента. Запись сохранена — проверьте статус позже.", {
        code: "content_review_request_failed",
      });
    }
    if (error) {
      throw await contentReviewFunctionError(error);
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new CreatorApiError("Сервис проверки контента вернул некорректный ответ.", {
        code: "content_review_response_invalid",
      });
    }
    if (data.ok === false || data.error) {
      const responseError = data.error && typeof data.error === "object" && !Array.isArray(data.error)
        ? data.error
        : {
            code: data.code || (typeof data.error === "string" ? data.error : "content_review_response_invalid"),
            details: data.details || null,
            hint: data.hint || null,
          };
      throw new CreatorApiError(safeContentReviewMessage(responseError), responseError);
    }
    return data;
  }

  createMockBatch(batch) {
    const projectId = requiredProjectId(batch?.project_id ?? batch?.projectId);
    const batchPayload = { ...(batch || {}) };
    delete batchPayload.projectId;
    const count = Number(batch?.count);
    if (!Number.isInteger(count) || count < 1 || count > 50) {
      throw new CreatorApiError("За один раз можно создать от 1 до 50 тестовых вариантов.", {
        code: "invalid_batch_size",
      });
    }
    const platforms = new Set(["instagram", "tiktok", "youtube", "vk", "telegram", "wildberries"]);
    const destination = String(batch?.destination_ref || "").trim();
    if (!platforms.has(batch?.platform) || destination.length < 2 || destination.length > 240) {
      throw new CreatorApiError("Проверьте площадку и точный аккаунт или карточку размещения.", {
        code: "placement_destination_invalid",
      });
    }
    if (!Array.isArray(batch?.media_ids) || batch.media_ids.length < 1) {
      throw new CreatorApiError("Добавьте точное фото товара или упаковки из раздела «Материалы».", {
        code: "exact_product_media_required",
      });
    }
    if (
      batch?.payout_minor !== undefined &&
      (!Number.isSafeInteger(batch.payout_minor) || batch.payout_minor < 0 || batch.payout_minor > 1_000_000)
    ) {
      throw new CreatorApiError("Проверьте сумму вознаграждения.", {
        code: "payout_minor_invalid",
      });
    }
    return this.mutate(RPC.createMockBatch, {
      ...batchPayload,
      project_id: projectId,
      mode: "mock",
      allow_real_spend: false,
      spend_confirmation: "MOCK_ONLY",
    });
  }

  bindRealGenerationClientContext(payload, {
    expectedActorId: expectedActorIdValue = "",
    isContextCurrent = null,
  } = {}) {
    const expectedActorId = String(expectedActorIdValue || "")
      .trim()
      .toLowerCase();
    if (
      !payload
      || typeof payload !== "object"
      || Array.isArray(payload)
      || !isUuid(expectedActorId)
      || typeof isContextCurrent !== "function"
    ) {
      throw new CreatorApiError("Не удалось зафиксировать точный контур сотрудника для платного запуска.", {
        code: "auth_session_changed",
      });
    }
    if (!(this.realGenerationClientContexts instanceof WeakMap)) {
      this.realGenerationClientContexts = new WeakMap();
    }
    this.realGenerationClientContexts.set(payload, Object.freeze({
      expectedActorId,
      isContextCurrent,
    }));
    return payload;
  }

  takeRealGenerationClientContext(payload) {
    const contexts = this.realGenerationClientContexts;
    if (!(contexts instanceof WeakMap) || !payload || typeof payload !== "object") {
      return null;
    }
    const context = contexts.get(payload) || null;
    contexts.delete(payload);
    return context;
  }

  startRealGeneration(batch) {
    const clientContext = this.takeRealGenerationClientContext(batch);
    if (!clientContext) {
      throw new CreatorApiError("Сессия сотрудника изменилась перед платным запуском. Обновите страницу и подтвердите запуск заново.", {
        code: "auth_session_changed",
      });
    }
    const projectId = requiredProjectId(batch?.project_id ?? batch?.projectId);
    const batchPayload = { ...(batch || {}) };
    delete batchPayload.projectId;
    if (this.config.REAL_GENERATION_ENABLED !== true) {
      throw new CreatorApiError("Платная генерация выключена в конфигурации портала.", {
        code: "real_generation_is_disabled",
      });
    }
    if (
      !Array.isArray(batch?.media_ids)
      || batch.media_ids.length < 1
      || batch.media_ids.length > 5
      || new Set(batch.media_ids.map(String)).size !== batch.media_ids.length
      || batch.media_ids.some((mediaId) => !isUuid(String(mediaId || "")))
    ) {
      throw new CreatorApiError("Выберите от одного до пяти точных фото одного товара.", {
        code: "real_generation_product_references_invalid",
      });
    }
    const campaignId = String(batch?.campaign_id || "").trim();
    if (!isUuid(campaignId)) {
      throw new CreatorApiError("Выберите активную кампанию из свежей денежной сводки.", {
        code: "paid_generation_campaign_required",
      });
    }
    const provider = String(batch?.provider || "").trim().toLowerCase();
    const model = String(batch?.model || "").trim();
    const inputMode = String(batch?.input_mode || "").trim().toLowerCase();
    const durationSeconds = Number(batch?.duration_seconds);
    const format = String(batch?.format || "").trim();
    const resolution = String(batch?.resolution || "").trim();
    const audio = batch?.audio;
    const lastFrame = batch?.last_frame;
    if (
      !["runway", "google"].includes(provider)
      || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u.test(model)
      || inputMode !== "image"
      || !Number.isSafeInteger(durationSeconds)
      || durationSeconds < 0
      || !/^\d{1,4}:\d{1,4}$/u.test(format)
      || !/^(?:\d{3,4}p|[1-9]\d?K)$/u.test(resolution)
      || typeof audio !== "boolean"
      || typeof lastFrame !== "boolean"
    ) {
      throw new CreatorApiError("Параметры платного режима не совпадают с подтверждённой ценой.", {
        code: "real_generation_sku_invalid",
      });
    }
    if (!/^[A-Z0-9][A-Z0-9_.:-]{2,255}$/u.test(String(batch?.spend_confirmation || ""))) {
      throw new CreatorApiError("Подтвердите точную стоимость из свежей серверной проверки.", {
        code: "real_spend_confirmation_required",
      });
    }
    if (
      !isUuid(String(batch?.provider_readiness_receipt_id || ""))
      || !PROVIDER_READINESS_SHA256_PATTERN.test(
        String(batch?.provider_readiness_receipt_hash || ""),
      )
      || !batch?.generation_selection_snapshot
      || typeof batch.generation_selection_snapshot !== "object"
      || Array.isArray(batch.generation_selection_snapshot)
    ) {
      throw new CreatorApiError("Серверная квитанция выбранной модели устарела.", {
        code: "provider_readiness_receipt_required",
      });
    }
    const brief = String(batch?.brief || "").trim();
    const promptMaxLength = Number(batch?.prompt_max_length);
    if (
      !brief
      || !Number.isSafeInteger(promptMaxLength)
      || promptMaxLength < 1
      || promptMaxLength > 100_000
      || brief.length > promptMaxLength
    ) {
      throw new CreatorApiError(
        "Сократите ТЗ до лимита выбранной серверной модели.",
        { code: "brief_invalid" },
      );
    }
    const productCategory = String(batch?.product_category || "").trim().toLowerCase();
    if (
      !["cosmetics", "baa", "sports_food", "food", "household", "apparel", "electronics", "other"]
        .includes(productCategory)
    ) {
      throw new CreatorApiError(
        "Выберите категорию товара для правил QA и обязательных предупреждений.",
        { code: "paid_generation_product_category_invalid" },
      );
    }
    const learningContext = batch?.learning_context;
    if (
      !learningContext
      || typeof learningContext !== "object"
      || Array.isArray(learningContext)
    ) {
      throw new CreatorApiError(
        "Восстановите безопасное авто-ТЗ и дождитесь проверки обучения.",
        { code: "generation_learning_context_required" },
      );
    }
    if (!hasExactObjectKeys(batch?.generation_spec_context, [
      "spec_id", "spec_version", "spec_hash",
    ])) {
      throw new CreatorApiError(
        "Подготовьте и утвердите актуальную серверную версию ТЗ.",
        { code: "generation_spec_context_required" },
      );
    }
    const generationSpecContext = normalizeGenerationSpecReference(
      batch.generation_spec_context,
    );
    let generationReferenceContext;
    if (batch?.generation_reference_context !== undefined) {
      const context = batch.generation_reference_context;
      if (
        !hasExactObjectKeys(context, ["binding_id", "binding_hash"])
        || !isUuid(String(context.binding_id || ""))
        || !/^[0-9a-f]{64}$/u.test(String(context.binding_hash || ""))
      ) {
        throw new CreatorApiError(
          "Видеореференс не привязан к точной версии ТЗ.",
          { code: "generation_video_reference_context_invalid" },
        );
      }
      generationReferenceContext = {
        binding_id: String(context.binding_id).toLowerCase(),
        binding_hash: String(context.binding_hash).toLowerCase(),
      };
    }
    if (
      batch?.learning_opt_out !== undefined
      && (
        batch.learning_opt_out !== true
        || learningContext.source === "performance_learning"
      )
    ) {
      throw new CreatorApiError(
        "Не удалось подтвердить осознанное отключение обученного ракурса.",
        { code: "generation_learning_opt_out_invalid" },
      );
    }
    const repairContext = batch?.repair_context;
    if (repairContext !== undefined) {
      const allowedRepairCodes = new Set([
        "product_fidelity",
        "technical_stability",
        "audio_quality",
        "speech_fidelity",
        "hook_clarity",
        "visual_quality",
        "trust",
        "platform_fit",
      ]);
      const guardCodes = repairContext?.guard_codes;
      if (
        !repairContext
        || typeof repairContext !== "object"
        || Array.isArray(repairContext)
        || repairContext.compiler_version !== "review-repair-v1"
        || !isUuid(String(repairContext.source_review_id || ""))
        || !isUuid(String(repairContext.source_generation_job_id || ""))
        || !/^[0-9a-f]{64}$/u.test(String(repairContext.policy_hash || ""))
        || !Array.isArray(guardCodes)
        || guardCodes.length < 1
        || guardCodes.length > 3
        || new Set(guardCodes).size !== guardCodes.length
        || guardCodes.some((code) => !allowedRepairCodes.has(code))
        || Object.keys(repairContext).some((key) => ![
          "source_review_id",
          "source_generation_job_id",
          "guard_codes",
          "policy_hash",
          "compiler_version",
        ].includes(key))
        || Object.keys(repairContext).length !== 5
      ) {
        throw new CreatorApiError(
          "Исправление после QA устарело. Вернитесь в проверку и подготовьте его снова.",
          { code: "generation_repair_context_invalid" },
        );
      }
    }

    const {
      // Browser-only guard: the authoritative Edge derives the same limit
      // from its catalog and rejects unknown START keys.
      prompt_max_length: _clientPromptMaxLength,
      ...serverBatchPayload
    } = batchPayload;
    const invocationPayload = {
      ...serverBatchPayload,
      project_id: projectId,
      generation_spec_context: generationSpecContext,
      ...(generationReferenceContext
        ? { generation_reference_context: generationReferenceContext }
        : {}),
      campaign_id: campaignId,
      count: 1,
      media_ids: batch.media_ids.map(String),
      mode: "real",
      provider,
      model,
      input_mode: inputMode,
      duration_seconds: durationSeconds,
      format,
      resolution,
      audio,
      last_frame: lastFrame,
      allow_real_spend: true,
      spend_confirmation: String(batch.spend_confirmation),
    };
    this.bindRealGenerationClientContext(invocationPayload, clientContext);
    return this.invokeRealGeneration("start", invocationPayload);
  }

  realGenerationPreflight(selection, legacyDurationSeconds = undefined) {
    const legacy = typeof selection === "string";
    const source = legacy
      ? {
          provider: "runway",
          model: String(selection || "").trim(),
          input_mode: "image",
          duration_seconds: Number(legacyDurationSeconds),
          format: selection === "seedream5_lite" ? "1:1" : "9:16",
          resolution: selection === "seedream5_lite" ? "2K" : "720p",
          audio: selection === "seedance2_fast",
          last_frame: false,
        }
      : { ...(selection || {}) };
    const exact = {
      provider: String(source.provider || "").trim().toLowerCase(),
      model: String(source.model || "").trim(),
      input_mode: String(source.input_mode || "").trim().toLowerCase(),
      duration_seconds: Number(source.duration_seconds),
      format: String(source.format || "").trim(),
      resolution: String(source.resolution || "").trim(),
      audio: source.audio,
      last_frame: source.last_frame,
    };
    if (
      !["runway", "google"].includes(exact.provider)
      || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u.test(String(exact.model || ""))
      || exact.input_mode !== "image"
      || !Number.isSafeInteger(exact.duration_seconds)
      || !/^\d{1,4}:\d{1,4}$/u.test(String(exact.format || ""))
      || !/^(?:\d{3,4}p|[1-9]\d?K)$/u.test(String(exact.resolution || ""))
      || typeof exact.audio !== "boolean"
      || typeof exact.last_frame !== "boolean"
    ) {
      throw new CreatorApiError("Выберите доступный платный режим.", {
        code: "real_generation_sku_invalid",
      });
    }
    if (apiGenerationPreflightRequiresV4(exact.provider, exact.model)) {
      const projectId = requiredProjectId(source.project_id);
      const specContext = normalizeGenerationSpecReference(
        source.generation_spec_context,
      );
      if (
        !hasExactObjectKeys(source.generation_spec_context, [
          "spec_id", "spec_version", "spec_hash",
        ]) ||
        !specContext
      ) {
        throw new CreatorApiError(
          "Сначала подготовьте точную серверную версию ТЗ для выбранной модели.",
          { code: "generation_spec_context_required" },
        );
      }
      return this.invokeRealGeneration("preflight", {
        ...exact,
        project_id: projectId,
        generation_spec_context: specContext,
      });
    }
    return this.invokeRealGeneration("preflight", exact);
  }

  async generationModelCatalog() {
    const data = await this.invokeRealGeneration("model_catalog");
    const catalog = data?.catalog;
    if (
      !catalog
      || typeof catalog !== "object"
      || Array.isArray(catalog)
      || typeof catalog.version !== "string"
      || !catalog.version.trim()
      || !Array.isArray(catalog.models)
      || catalog.models.some((entry) => (
        !entry
        || typeof entry !== "object"
        || Array.isArray(entry)
        || typeof entry.provider !== "string"
        || !entry.provider.trim()
        || typeof entry.model !== "string"
        || !entry.model.trim()
        || typeof entry.publicLabel !== "string"
        || !entry.publicLabel.trim()
        || typeof entry.enabled !== "boolean"
      ))
    ) {
      throw new CreatorApiError(
        "Каталог моделей генерации временно недоступен. Текущий выбор и платные подтверждения не изменены.",
        { code: "generation_model_catalog_invalid" },
      );
    }
    return data;
  }

  /*
   * Ведущие проекта для формата «Дуэт».
   *
   * Витрина отдаёт НАШ идентификатор ведущего и его раскладку, но не личность у
   * провайдера: avatar_id и voice_id браузеру не нужны и не приходят. Форма
   * выбирает ведущего по нашему id, а сервер сам подставляет личность в платный
   * запрос — подменить её из браузера нельзя.
   */
  async duetPresenters(projectId) {
    const data = await this.call("creator_list_duet_presenters", {
      organization_id: String(this.organizationId || ""),
      project_id: String(projectId || ""),
    });
    if (
      !hasExactObjectKeys(data, ["ok", "version", "presenters"])
      || data.ok !== true
      || data.version !== "generation-duet-presenters-v1"
      || !Array.isArray(data.presenters)
    ) {
      throw new CreatorApiError("Список ведущих пришёл в неизвестной форме.");
    }
    // Личность провайдера не должна доехать до браузера ни при какой версии
    // сервера. Если доехала — это утечка, и молча принимать её нельзя.
    for (const presenter of data.presenters) {
      if (
        presenter
        && typeof presenter === "object"
        && ("provider_avatar_id" in presenter || "provider_voice_id" in presenter)
      ) {
        throw new CreatorApiError(
          "Сервер вернул идентификаторы провайдера в списке ведущих.",
        );
      }
    }
    return data.presenters;
  }

  /*
   * Каталог личностей ведущего из кабинета провайдера: фото-аватары,
   * видеоаватары и голоса. Ключ провайдера живёт на сервере — списки читает
   * edge и отдаёт только идентификаторы, имена и превью.
   */
  async duetPresenterCatalog() {
    const data = await this.invokeRealGeneration("duet_presenter_catalog", {
      action: "duet_presenter_catalog",
      organization_id: String(this.organizationId || ""),
    });
    if (
      !hasExactObjectKeys(data, ["ok", "version", "presenters", "voices"])
      || data.ok !== true
      || data.version !== "duet-presenter-catalog-v1"
      || !Array.isArray(data.presenters)
      || !Array.isArray(data.voices)
    ) {
      throw new CreatorApiError("Каталог ведущих пришёл в неизвестной форме.");
    }
    const text = (value, limit) => String(value || "").trim().slice(0, limit);
    return {
      presenters: data.presenters
        .filter((item) => item && typeof item === "object")
        .map((item) => ({
          kind: item.kind === "avatar" ? "avatar" : "talking_photo",
          id: text(item.id, 128),
          name: text(item.name, 120),
          preview_image_url: typeof item.preview_image_url === "string"
            && item.preview_image_url.startsWith("https://")
            ? item.preview_image_url
            : null,
        }))
        .filter((item) => item.id),
      voices: data.voices
        .filter((item) => item && typeof item === "object")
        .map((item) => ({
          id: text(item.id, 128),
          name: text(item.name, 120),
          language: text(item.language, 60),
          gender: text(item.gender, 20),
        }))
        .filter((item) => item.id),
    };
  }

  /*
   * Регистрация ведущего проекта: наша запись о личности у провайдера. Один
   * раз на проект; дальше он тот же во всех роликах.
   */
  async registerDuetPresenter(projectId, input) {
    const payload = {
      organization_id: String(this.organizationId || ""),
      project_id: String(projectId || ""),
      display_name: String(input?.displayName || "").trim(),
      provider_avatar_id: String(input?.providerAvatarId || "").trim(),
      provider_voice_id: String(input?.providerVoiceId || "").trim(),
      provider_avatar_kind: input?.providerAvatarKind === "avatar"
        ? "avatar"
        : "talking_photo",
      aspect_ratio: "9:16",
      is_default: input?.isDefault !== false,
      // Живой человек заводится только с записанным согласием: сервер отвергнет
      // real_person без него (duet_presenter_likeness_consent_required).
      likeness_kind: input?.likenessKind === "real_person" ? "real_person" : "synthetic",
    };
    if (payload.likeness_kind === "real_person") {
      payload.likeness_consent_confirmed = input?.likenessConsentConfirmed === true;
    }
    const data = await this.call("creator_register_duet_presenter", payload);
    if (
      !data
      || typeof data !== "object"
      || data.ok !== true
      || !data.presenter
      || typeof data.presenter !== "object"
      || typeof data.presenter.id !== "string"
    ) {
      throw new CreatorApiError("Ведущий не зарегистрирован: ответ сервера неизвестной формы.");
    }
    return data.presenter;
  }

  /*
   * Персонаж по описанию: сервер просит HeyGen собрать фото-аватар из текста
   * (синтетическая личность, живого человека за ней нет). Возвращает
   * идентификатор образа; готовность опрашивается отдельно.
   */
  async duetPresenterGenerate(input) {
    const name = String(input?.name || "").trim();
    const prompt = String(input?.prompt || "").trim();
    if (name.length < 2 || name.length > 80) {
      throw new CreatorApiError("Дайте персонажу имя от 2 до 80 знаков.", {
        code: "duet_presenter_name_invalid",
      });
    }
    if (prompt.length < 10 || prompt.length > 1000) {
      throw new CreatorApiError("Опишите персонажа: от 10 до 1000 знаков.", {
        code: "duet_presenter_prompt_invalid",
      });
    }
    const data = await this.invokeRealGeneration("duet_presenter_generate", {
      action: "duet_presenter_generate",
      organization_id: String(this.organizationId || ""),
      name,
      prompt,
      aspect_ratio: ["9:16", "1:1", "16:9"].includes(input?.aspectRatio)
        ? input.aspectRatio
        : "9:16",
    });
    if (
      !hasExactObjectKeys(data, ["ok", "version", "look_id", "group_id", "status"])
      || data.ok !== true
      || data.version !== "duet-presenter-generation-v1"
      || typeof data.look_id !== "string"
      || !/^[A-Za-z0-9_-]{1,128}$/u.test(data.look_id)
    ) {
      throw new CreatorApiError("Сервер не подтвердил создание персонажа.", {
        code: "duet_presenter_generation_response_invalid",
      });
    }
    return { lookId: data.look_id, status: String(data.status || "processing") };
  }

  async duetPresenterGenerationStatus(lookId) {
    const id = String(lookId || "").trim();
    if (!/^[A-Za-z0-9_-]{1,128}$/u.test(id)) {
      throw new CreatorApiError("Идентификатор персонажа повреждён.", {
        code: "duet_presenter_look_id_invalid",
      });
    }
    const data = await this.invokeRealGeneration("duet_presenter_generation_status", {
      action: "duet_presenter_generation_status",
      organization_id: String(this.organizationId || ""),
      look_id: id,
    });
    if (
      !hasExactObjectKeys(data, ["ok", "version", "look_id", "status", "error_message", "presenter"])
      || data.ok !== true
      || data.version !== "duet-presenter-generation-status-v1"
      || data.look_id !== id
    ) {
      throw new CreatorApiError("Сервер вернул состояние персонажа в неизвестной форме.", {
        code: "duet_presenter_generation_response_invalid",
      });
    }
    const text = (value, limit) => String(value || "").trim().slice(0, limit);
    const presenter = data.presenter && typeof data.presenter === "object"
      ? {
        kind: data.presenter.kind === "avatar" ? "avatar" : "talking_photo",
        id: text(data.presenter.id, 128),
        name: text(data.presenter.name, 120),
        preview_image_url: typeof data.presenter.preview_image_url === "string"
          && data.presenter.preview_image_url.startsWith("https://")
          ? data.presenter.preview_image_url
          : null,
        catalog_confirmed: data.presenter.catalog_confirmed === true,
      }
      : null;
    return {
      lookId: id,
      status: text(data.status, 40) || "processing",
      errorMessage: text(data.error_message, 300),
      presenter: presenter && presenter.id ? presenter : null,
    };
  }

  /*
   * Раскладка врезки: где встанет ведущий и каким видом. Меняется отдельно от
   * самого ведущего — сменить угол не значит завести нового человека.
   */
  async updateDuetPresenterLayout(projectId, presenterId, layout) {
    const payload = {
      organization_id: String(this.organizationId || ""),
      project_id: String(projectId || ""),
      presenter_id: String(presenterId || ""),
    };
    if (layout?.corner) payload.overlay_corner = String(layout.corner);
    if (layout?.shape) payload.overlay_shape = String(layout.shape);
    if (Number.isInteger(layout?.widthPercent)) {
      payload.overlay_width_percent = layout.widthPercent;
    }
    const data = await this.call("creator_update_duet_presenter_layout", payload);
    if (
      !hasExactObjectKeys(data, ["ok", "version", "presenter"])
      || data.ok !== true
      || data.version !== "generation-duet-presenter-v1"
    ) {
      throw new CreatorApiError("Раскладка ведущего сохранена не полностью.");
    }
    return data.presenter;
  }

  async generationStrategyCatalog() {
    const data = await this.invokeRealGeneration("strategy_catalog", {
      action: "strategy_catalog",
      organization_id: String(this.organizationId || ""),
    });
    const catalog = data?.catalog;
    const strategyIds = Array.isArray(catalog?.strategies)
      ? catalog.strategies.map((entry) => String(entry?.strategy_id || ""))
      : [];
    if (
      !hasExactObjectKeys(data, ["ok", "catalog"])
      || data.ok !== true
      // strategyProviderRoutes появляется, когда у стратегии больше одного
      // движка. Поле необязательное: миграция базы и деплой функции не
      // атомарны, поэтому каталог обязан читаться и с ним, и без него.
      || !hasExactObjectKeys(
        catalog && typeof catalog === "object" && !Array.isArray(catalog)
          ? Object.fromEntries(
            Object.entries(catalog).filter(
              ([key]) => key !== "strategyProviderRoutes",
            ),
          )
          : catalog,
        [
          "strategyCatalogVersion",
          "strategyRecipeVersion",
          "strategyPricingVersion",
          "strategies",
        ],
      )
      || (catalog.strategyProviderRoutes !== undefined && (
        !catalog.strategyProviderRoutes
        || typeof catalog.strategyProviderRoutes !== "object"
        || Array.isArray(catalog.strategyProviderRoutes)
      ))
      || typeof catalog.strategyCatalogVersion !== "string"
      || !catalog.strategyCatalogVersion.trim()
      || typeof catalog.strategyRecipeVersion !== "string"
      || !catalog.strategyRecipeVersion.trim()
      || typeof catalog.strategyPricingVersion !== "string"
      || !catalog.strategyPricingVersion.trim()
      || !Array.isArray(catalog.strategies)
      || catalog.strategies.length !== 3
      || catalog.strategies.some((entry) => (
        !entry
        || typeof entry !== "object"
        || Array.isArray(entry)
        || typeof entry.strategy_id !== "string"
        || !entry.strategy_id.trim()
        || typeof entry.public_label !== "string"
        || !entry.public_label.trim()
        || typeof entry.enabled !== "boolean"
      ))
      || new Set(strategyIds).size !== 3
    ) {
      throw new CreatorApiError(
        "Каталог стратегий генерации временно недоступен. Ничего не выбрано и платный запуск не изменён.",
        { code: "generation_strategy_catalog_invalid" },
      );
    }
    return data;
  }

  probeGenerationStrategyMedia(request = {}) {
    return this.invokeRealGeneration("strategy_media_probe", request);
  }

  preflightGenerationStrategy(request = {}) {
    return this.invokeRealGeneration("strategy_preflight", request);
  }

  startGenerationStrategy(request = {}) {
    if (this.config.REAL_GENERATION_ENABLED !== true) {
      throw new CreatorApiError("Платная генерация выключена в конфигурации портала.", {
        code: "real_generation_is_disabled",
      });
    }
    return this.invokeRealGeneration("strategy_start", request);
  }

  generationStrategyStatus(request = {}) {
    return this.invokeRealGeneration("strategy_status", request);
  }

  bindGenerationStrategy(input = {}) {
    if (
      input
      && typeof input === "object"
      && !Array.isArray(input)
      && Object.prototype.hasOwnProperty.call(input, "action")
    ) {
      return this.invokeRealGeneration("strategy_bind", input);
    }
    const projectId = requiredProjectId(input.project_id ?? input.projectId);
    const specContext = normalizeGenerationSpecReference(
      input.generation_spec_context ?? input.generationSpecContext,
    );
    const selection = input.generation_strategy ?? input.generationStrategy;
    if (!specContext) {
      throw new CreatorApiError(
        "Сначала подготовьте и одобрите точную серверную версию ТЗ.",
        { code: "generation_spec_context_required" },
      );
    }
    if (
      !selection
      || typeof selection !== "object"
      || Array.isArray(selection)
      || !hasExactObjectKeys(selection, [
        "version",
        "strategy_id",
        "recipe_version",
        "duration_seconds",
        ...(String(selection.strategy_id || "") === "viral_product_swap"
          ? ["resolution"]
          : ["ratio"]),
        "audio",
        "assets",
        "attestations",
      ])
      || !["viral_avatar_ugc", "viral_product_swap", "viral_rebuild"]
        .includes(String(selection.strategy_id || ""))
      || !Array.isArray(selection.assets)
      || !selection.attestations
      || typeof selection.attestations !== "object"
      || Array.isArray(selection.attestations)
    ) {
      throw new CreatorApiError(
        "Проверьте стратегию, исходники, параметры результата и подтверждения прав.",
        { code: "generation_strategy_selection_invalid" },
      );
    }
    return this.invokeRealGeneration("strategy_bind", {
      project_id: projectId,
      spec_id: specContext.spec_id,
      spec_version: specContext.spec_version,
      spec_hash: specContext.spec_hash,
      generation_strategy: selection,
      confirmation: true,
    });
  }

  realGenerationStatus(jobId, {
    projectId = "",
    project_id: projectIdSnake = "",
  } = {}) {
    const normalizedJobId = String(jobId || "").trim();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(normalizedJobId)) {
      throw new CreatorApiError("Не удалось определить платную задачу. Обновите раздел.", {
        code: "generation_job_id_invalid",
      });
    }
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.invokeRealGeneration("status", {
      job_id: normalizedJobId,
      project_id: normalizedProjectId,
    });
  }

  reconcileRealGeneration(jobId, details = {}) {
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const normalizedJobId = String(jobId || "").trim();
    const incidentId = String(details.incident_id || "").trim();
    const resolution = String(details.resolution || "").trim();
    const evidenceReference = String(details.evidence_reference || "").trim();
    const reason = String(details.reason || "").trim();
    const providerTaskId = String(details.provider_task_id || "").trim();
    const provider = String(details.provider || "").trim().toLowerCase();
    const projectId = requiredProjectId(details.project_id ?? details.projectId);
    const attachExistingTask = resolution === "attach_existing_task";
    const confirmNoSubmission = resolution === "confirm_no_submission";

    if (!uuidPattern.test(normalizedJobId) || !uuidPattern.test(incidentId)) {
      throw new CreatorApiError("Не удалось определить инцидент платного запуска. Обновите раздел.", {
        code: "generation_reconciliation_incident_invalid",
      });
    }
    if (!attachExistingTask && !confirmNoSubmission) {
      throw new CreatorApiError("Выберите результат ручной сверки платного запуска.", {
        code: "generation_reconciliation_resolution_invalid",
      });
    }
    if (!new Set(["runway", "google", "fal"]).has(provider)) {
      throw new CreatorApiError("Не удалось подтвердить сервис этого запуска. Обновите карточку.", {
        code: "generation_reconciliation_provider_invalid",
      });
    }
    if (
      evidenceReference.length < 8
      || evidenceReference.length > 500
      || reason.length < 20
      || reason.length > 1_000
    ) {
      throw new CreatorApiError("Добавьте проверяемое основание и подробную причину ручной сверки.", {
        code: "generation_reconciliation_evidence_invalid",
      });
    }
    const providerTaskValid = provider === "google"
      ? /^models\/veo-3\.1-lite-generate-preview\/operations\/[A-Za-z0-9][A-Za-z0-9._~-]{0,255}$/u
        .test(providerTaskId)
      : provider === "fal"
      ? GENERATION_STRATEGY_FAL_REQUEST_ID_PATTERN.test(providerTaskId)
      : GENERATION_STRATEGY_RUNWAY_TASK_ID_PATTERN.test(providerTaskId);
    if (attachExistingTask && !providerTaskValid) {
      throw new CreatorApiError(provider === "google"
        ? "Укажите точное имя Google operation из панели сервиса."
        : provider === "fal"
        ? "Укажите точный fal request ID из панели сервиса."
        : "Укажите точный Runway task ID из панели видеосервиса.", {
        code: "generation_reconciliation_task_id_invalid",
      });
    }

    return this.invokeRealGeneration("reconcile", {
      job_id: normalizedJobId,
      project_id: projectId,
      incident_id: incidentId,
      resolution,
      evidence_reference: evidenceReference,
      reason,
      confirmation: provider === "google"
        ? attachExistingTask
          ? "GOOGLE_OPERATION_ID_VERIFIED"
          : "GOOGLE_NO_OPERATION_VERIFIED"
        : provider === "fal"
        ? attachExistingTask
          ? "FAL_REQUEST_ID_VERIFIED"
          : "FAL_NO_REQUEST_VERIFIED"
        : attachExistingTask
          ? "RUNWAY_TASK_ID_VERIFIED"
          : "RUNWAY_NO_TASK_VERIFIED",
      ...(attachExistingTask ? { provider_task_id: providerTaskId } : {}),
    });
  }

  reconcileGenerationStrategy(jobId, details = {}) {
    const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const normalizedJobId = String(jobId || "").trim();
    const incidentId = String(details.incident_id || "").trim();
    const dispatchResultId = String(details.dispatch_result_id || "").trim();
    const resolution = String(details.resolution || "").trim();
    const evidenceReference = String(details.evidence_reference || "").trim();
    const reason = String(details.reason || "").trim();
    const providerTaskId = String(details.provider_task_id || "").trim();
    const provider = String(details.provider || "").trim().toLowerCase();
    const projectId = requiredProjectId(details.project_id ?? details.projectId);
    const attachExistingTask = resolution === "attach_existing_task";
    const confirmNoSubmission = resolution === "confirm_no_submission";

    if (
      !uuidPattern.test(normalizedJobId)
      || !uuidPattern.test(incidentId)
      || !uuidPattern.test(dispatchResultId)
    ) {
      throw new CreatorApiError("Не удалось определить инцидент платного запуска стратегии. Обновите карточку и повторите сверку.", {
        code: "generation_reconciliation_incident_invalid",
      });
    }
    if (!attachExistingTask && !confirmNoSubmission) {
      throw new CreatorApiError("Выберите результат ручной сверки платного запуска.", {
        code: "generation_reconciliation_resolution_invalid",
      });
    }
    // «Дуэт» исполняет heygen, и до 24.08.2026 его разбор отвергался здесь —
    // раньше, чем запрос вообще уходил. Это был первый из трёх замков на одной
    // двери: браузер, edge и база отвергали heygen каждый по своему списку, и
    // повисшая бронь дуэта не расшивалась ничем.
    if (!new Set(["runway", "fal", "heygen"]).has(provider)) {
      throw new CreatorApiError("Не удалось подтвердить сервис этого запуска. Обновите карточку.", {
        code: "generation_reconciliation_provider_invalid",
      });
    }
    if (
      evidenceReference.length < 8
      || evidenceReference.length > 500
      || reason.length < 20
      || reason.length > 1_000
    ) {
      throw new CreatorApiError("Добавьте проверяемое основание и подробную причину ручной сверки.", {
        code: "generation_reconciliation_evidence_invalid",
      });
    }
    const providerTaskValid = provider === "fal"
      ? GENERATION_STRATEGY_FAL_REQUEST_ID_PATTERN.test(providerTaskId)
      : GENERATION_STRATEGY_RUNWAY_TASK_ID_PATTERN.test(providerTaskId);
    if (attachExistingTask && !providerTaskValid) {
      throw new CreatorApiError(provider === "fal"
        ? "Укажите точный fal request ID из панели сервиса."
        : "Укажите точный Runway task ID из панели видеосервиса.", {
        code: "generation_reconciliation_task_id_invalid",
      });
    }

    return this.invokeRealGeneration("strategy_reconcile", {
      action: "strategy_reconcile",
      organization_id: this.organizationId,
      project_id: projectId,
      generation_job_id: normalizedJobId,
      dispatch_result_id: dispatchResultId,
      incident_id: incidentId,
      resolution,
      confirmation: provider === "heygen"
        ? attachExistingTask
          ? "HEYGEN_VIDEO_ID_VERIFIED"
          : "HEYGEN_NO_VIDEO_VERIFIED"
        : provider === "fal"
        ? attachExistingTask
          ? "FAL_REQUEST_ID_VERIFIED"
          : "FAL_NO_REQUEST_VERIFIED"
        : attachExistingTask
        ? "RUNWAY_TASK_ID_VERIFIED"
        : "RUNWAY_NO_TASK_VERIFIED",
      evidence_reference: evidenceReference,
      reason,
      idempotency_key: `strategy-reconcile:${incidentId}:${resolution}`,
      ...(attachExistingTask ? { provider_task_id: providerTaskId } : {}),
    });
  }

  async invokeRealGeneration(action, payload = {}) {
    const legacyAction = new Set([
      "model_catalog",
      "preflight",
      "start",
      "status",
      "reconcile",
      // Каталог личностей ведущего из кабинета HeyGen — чтение без денег;
      // форма запроса та же, что у model_catalog: действие + организация.
      "duet_presenter_catalog",
      // Персонаж по описанию: тратит кредиты кабинета HeyGen, но не деньги
      // завода — резервов и квитанций у него нет.
      "duet_presenter_generate",
      "duet_presenter_generation_status",
    ]).has(action);
    if (!legacyAction && !GENERATION_STRATEGY_EDGE_ACTIONS.has(action)) {
      throw new CreatorApiError("Неизвестное действие платной генерации.", {
        code: "real_generation_action_invalid",
      });
    }

    const clientContext = this.takeRealGenerationClientContext(payload);
    const strategyRuntimeRequest = GENERATION_STRATEGY_EDGE_ACTIONS.has(action)
      && (action !== "strategy_bind" || (
        payload
        && typeof payload === "object"
        && Object.prototype.hasOwnProperty.call(payload, "action")
      ));
    if (strategyRuntimeRequest) {
      assertGenerationStrategyRuntimeRequest(
        action,
        payload,
        this.organizationId,
      );
    }

    const expectedActorId = String(
      clientContext?.expectedActorId || "",
    ).trim().toLowerCase();
    const isContextCurrent = clientContext?.isContextCurrent || null;
    if (["start", "strategy_start"].includes(action) && !clientContext) {
      throw new CreatorApiError("Точный контур сотрудника для платного запуска не подтверждён.", {
        code: "auth_session_changed",
      });
    }
    if (expectedActorId && !isUuid(expectedActorId)) {
      throw new CreatorApiError("Сессия сотрудника перед платным запуском имеет неверный формат.", {
        code: "auth_session_changed",
      });
    }

    const { data: sessionData, error: sessionError } = await this.supabase.auth.getSession();
    const accessToken = sessionData?.session?.access_token;
    if (sessionError || !accessToken) {
      throw new CreatorApiError("Сессия истекла. Войдите снова перед платным запуском.", {
        code: "auth_session_required",
      });
    }

    const actorId = String(
      sessionData.session?.user?.id || "",
    ).trim().toLowerCase();
    if (expectedActorId && actorId !== expectedActorId) {
      throw new CreatorApiError("Сессия сотрудника изменилась перед платным запуском. Платный запрос не отправлен; обновите страницу и подтвердите запуск заново.", {
        code: "auth_session_changed",
      });
    }
    if (isContextCurrent !== null) {
      let contextCurrent = false;
      try {
        contextCurrent = typeof isContextCurrent === "function"
          && isContextCurrent() === true;
      } catch {
        contextCurrent = false;
      }
      if (!contextCurrent) {
        throw new CreatorApiError("Контекст платного запуска изменился во время проверки сессии. Платный запрос не отправлен.", {
          code: "real_generation_context_changed",
        });
      }
    }
    const scopedPayload = this.withOrganization({ ...payload, action });
    const fingerprint = `edge:${REAL_GENERATION_FUNCTION}:${actorId}:${stableStringify(scopedPayload)}`;
    const callerIdempotencyKey = strategyRuntimeRequest
      && GENERATION_STRATEGY_IDEMPOTENT_ACTIONS.has(action)
      ? payload.idempotency_key
      : null;
    const generatedIdempotencyKey = callerIdempotencyKey === null && new Set([
      "start", "reconcile", "strategy_bind",
    ]).has(action)
      ? (this.mutationKeys[fingerprint] || crypto.randomUUID())
      : null;
    if (generatedIdempotencyKey) {
      this.mutationKeys[fingerprint] = generatedIdempotencyKey;
      writeMutationKeys(this.mutationKeys);
    }

    const requestBody = generatedIdempotencyKey
      ? { ...scopedPayload, idempotency_key: generatedIdempotencyKey }
      : scopedPayload;
    let data;
    let error;
    try {
      ({ data, error } = await this.supabase.functions.invoke(REAL_GENERATION_FUNCTION, {
        body: requestBody,
        headers: { Authorization: `Bearer ${accessToken}` },
      }));
    } catch {
      throw new CreatorApiError("Не удалось связаться с сервисом платной генерации. Повторите попытку позже.", {
        code: "real_generation_request_failed",
      });
    }

    if (error) {
      throw await creatorFunctionError(error);
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new CreatorApiError("Сервис генерации вернул некорректный ответ.", {
        code: "real_generation_response_invalid",
      });
    }
    if (data.ok === false || (!strategyRuntimeRequest && data.error)) {
      const details = data.error && typeof data.error === "object"
        ? data.error
        : {
            code: data.code || "real_generation_failed",
            message: String(data.error || data.code || "Generation failed"),
      };
      throw new CreatorApiError(safeGenerationMessage(details), details);
    }
    if (strategyRuntimeRequest) {
      return assertGenerationStrategyPublicResponse(action, data);
    }
    if (action === "preflight") {
      const preflight = normalizeApiGenerationProviderPreflight(
        data.preflight,
        payload,
      );
      if (preflight === null) {
        throw new CreatorApiError(
          "Провайдер не подтвердил доступность и точную стоимость выбранной модели. Платный запуск не создан.",
          { code: "provider_preflight_invalid" },
        );
      }
      return { ...data, preflight };
    }
    if (action === "model_catalog") return data;
    // Действия ведущего «Дуэта» — чтение каталога и персонаж по описанию —
    // отвечают своей формой, без `job`: проверка ниже написана для платного
    // запуска и на них не распространяется. До 23.08 каталог HeyGen на проде
    // из-за неё не открывался вовсе («Сервис генерации вернул некорректную
    // задачу»), а созданный персонаж терялся на стороне браузера.
    if (DUET_PRESENTER_ACTIONS.has(action)) return data;
    if (action === "strategy_bind") {
      if (generatedIdempotencyKey) {
        delete this.mutationKeys[fingerprint];
        writeMutationKeys(this.mutationKeys);
      }
      return data;
    }
    if (!data.job || typeof data.job !== "object" || !data.job.id || !data.job.status) {
      throw new CreatorApiError("Сервис генерации вернул некорректную задачу.", {
        code: "real_generation_response_invalid",
      });
    }

    if (generatedIdempotencyKey) {
      delete this.mutationKeys[fingerprint];
      writeMutationKeys(this.mutationKeys);
    }
    return data;
  }

  recordMetric(snapshot) {
    const projectId = requiredProjectId(snapshot?.project_id ?? snapshot?.projectId);
    const snapshotPayload = { ...(snapshot || {}) };
    delete snapshotPayload.projectId;
    return this.mutate(RPC.recordMetric, {
      ...snapshotPayload,
      project_id: projectId,
      source: "manual",
    });
  }

  configureTrackingLink(placementId, targetUrl, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.mutate(RPC.configureTrackingLink, {
      placement_id: placementId,
      target_url: targetUrl,
      project_id: normalizedProjectId,
    });
  }

  setWbAlias(alias) {
    return this.mutate(RPC.setWbAlias, alias);
  }

  decidePayout(payoutId, decision, details = {}) {
    const projectId = requiredProjectId(details?.project_id ?? details?.projectId);
    const payload = { ...(details || {}) };
    delete payload.projectId;
    return this.mutate(RPC.decidePayout, {
      payout_id: payoutId,
      decision,
      ...payload,
      project_id: projectId,
    });
  }

  // Аккаунты компании, на которые физически можно публиковать: активные и с
  // включённым режимом размещения. Источник — реестр владения (фаза 0).
  async publishingAccounts({ projectId = "", project_id: projectIdSnake = "" } = {}) {
    const payload = { organization_id: String(this.organizationId || "") };
    const normalizedProjectId = String(projectIdSnake || projectId || "").trim();
    if (normalizedProjectId) payload.project_id = normalizedProjectId;
    const data = await this.call(RPC.publishingAccounts, payload);
    if (
      !data || data.ok !== true
      || data.version !== "publishing-accounts-v1"
      || !Array.isArray(data.accounts)
    ) {
      throw new CreatorApiError("Список аккаунтов для размещения пришёл в неизвестной форме.");
    }
    return data.accounts;
  }

  // «Запланировать публикацию»: наряд очереди авторазмещения (фаза 1).
  // Нарочно НЕ через mutate(): у creator_enqueue_publishing_job строгий
  // список ключей payload (лишний idempotency_key — отказ
  // publishing_enqueue_payload_invalid), а идемпотентность живёт на сервере:
  // unique (organization_id, placement_id), повтор возвращает существующий
  // наряд с already_enqueued: true. Аккаунт и ролик сервер выводит из самого
  // размещения — клиент их не передаёт.
  async enqueuePublishingJob(input) {
    const projectId = requiredProjectId(input?.project_id ?? input?.projectId);
    const placementId = String(input?.placement_id || "").trim();
    const scheduledAt = String(input?.scheduled_at || "").trim();
    const erid = String(input?.erid || "").trim().toUpperCase();
    if (!placementId || !scheduledAt || !/^[A-Z0-9-]{4,64}$/.test(erid)) {
      throw new CreatorApiError(
        "Для постановки в очередь нужны размещение, время выхода и ERID (или ORGANIC).",
        { code: "publishing_enqueue_payload_invalid" },
      );
    }
    const payload = {
      organization_id: String(this.organizationId || ""),
      project_id: projectId,
      placement_id: placementId,
      scheduled_at: scheduledAt,
      erid,
    };
    if (erid !== "ORGANIC") {
      const advertiser = String(input?.advertiser || "").trim();
      if (advertiser.length < 2) {
        throw new CreatorApiError(
          "Для рекламы обязателен рекламодатель — он войдёт в автоподпись маркировки.",
          { code: "publishing_enqueue_payload_invalid" },
        );
      }
      payload.advertiser = advertiser;
      const ordProvider = String(input?.ord_provider || "").trim();
      if (ordProvider) payload.ord_provider = ordProvider;
      const contractRef = String(input?.contract_ref || "").trim();
      if (contractRef) payload.contract_ref = contractRef;
    }
    const caption = String(input?.caption || "").trim();
    if (caption) payload.caption = caption;
    const hashtags = String(input?.hashtags || "").trim();
    if (hashtags) payload.hashtags = hashtags;
    const data = await this.call(RPC.enqueuePublishingJob, payload);
    if (
      !data || data.ok !== true
      || data.version !== "publishing-enqueue-v1"
      || !data.job || typeof data.job !== "object"
    ) {
      throw new CreatorApiError("Очередь публикаций ответила в неизвестной форме.");
    }
    return data;
  }

  // «Финализация» готового ролика: наряд локального воркера сборки MP4
  // (TTS-озвучка + drawtext-плашки), денег и провайдеров нет. Нарочно мимо
  // mutate(): идемпотентность серверная — одно активное задание на ролик
  // (partial-индекс очереди), повтор возвращает already_enqueued: true.
  async enqueueVideoFinalization(input) {
    const projectId = requiredProjectId(input?.project_id ?? input?.projectId);
    const mediaId = String(input?.media_id || "").trim().toLowerCase();
    const generationJobId = String(input?.generation_job_id || "")
      .trim().toLowerCase();
    const captions = [
      String(input?.caption_top || "").trim(),
      String(input?.caption_mid || "").trim(),
      String(input?.caption_bottom || "").trim(),
    ];
    const narration = String(input?.narration_text || "").trim();
    const voice = String(input?.narration_voice || "").trim();
    const captionWindows = Array.isArray(input?.caption_windows)
      ? input.caption_windows
      : null;
    const windowsValid = captionWindows === null || (
      captionWindows.length === 3
      && captionWindows.every((pair) => (
        Array.isArray(pair) && pair.length === 2
        && Number.isFinite(pair[0]) && Number.isFinite(pair[1])
        && pair[0] >= 0 && pair[1] > pair[0] && pair[1] <= 600
      ))
    );
    // Раскладка и звук: опциональные словари третьей итерации; отсутствие
    // ключа = дефолт воркера (верх/низ/низ, medium, replace).
    const captionPositions = Array.isArray(input?.caption_positions)
      ? input.caption_positions
      : null;
    const positionsValid = captionPositions === null || (
      captionPositions.length === 3
      && captionPositions.every((slot) => ["top", "bottom"].includes(slot))
    );
    const fontScale = String(input?.font_scale || "").trim();
    const audioMode = String(input?.audio_mode || "").trim();
    if (
      (!mediaId && !generationJobId)
      || captions.some((text) => !text || text.length > 80)
      || !narration || narration.length > 300
      || !windowsValid
      || !positionsValid
      || (fontScale && !["small", "medium", "large"].includes(fontScale))
      || (audioMode && !["replace", "duck"].includes(audioMode))
      || ![
        "minimax_lovely_girl", "minimax_lively_girl", "minimax_calm_woman",
        "minimax_wise_woman", "minimax_deep_voice_man",
        "minimax_friendly_person", "edge_svetlana", "edge_dmitry",
      ].includes(voice)
    ) {
      throw new CreatorApiError(
        "Для финализации нужны ролик, три плашки (до 80 знаков каждая), текст диктора (до 300 знаков) и голос из списка.",
        { code: "video_finalization_payload_invalid" },
      );
    }
    // Сервер принимает РОВНО ОДИН способ назвать ролик: media_id, а когда
    // архив его не отдал — generation_job_id (поиск по metadata наряда).
    const data = await this.call(RPC.enqueueVideoFinalization, {
      organization_id: String(this.organizationId || ""),
      project_id: projectId,
      ...(mediaId
        ? { media_id: mediaId }
        : { generation_job_id: generationJobId }),
      caption_top: captions[0],
      caption_mid: captions[1],
      caption_bottom: captions[2],
      narration_text: narration,
      voice,
      ...(captionWindows ? { caption_windows: captionWindows } : {}),
      ...(captionPositions ? { caption_positions: captionPositions } : {}),
      ...(fontScale ? { font_scale: fontScale } : {}),
      ...(audioMode ? { audio_mode: audioMode } : {}),
    });
    if (
      !data || data.ok !== true
      || data.version !== "video-finalization-enqueue-v1"
      || !data.job || typeof data.job !== "object"
    ) {
      throw new CreatorApiError("Очередь финализации ответила в неизвестной форме.");
    }
    return data;
  }

  // Витрина согласования (ступень 1): выдача токен-ссылки клиенту. Токен
  // возвращается РОВНО один раз — повтор по idempotency_key честно отвечает
  // replayed:true без токена (восстановить нельзя, только отозвать и выдать
  // новую). Идемпотентность серверная, метод мимо mutate().
  async issueClientReviewLink(input) {
    const campaignId = String(input?.campaign_id || "").trim().toLowerCase();
    const clientLabel = String(input?.client_label || "").trim();
    const mediaIds = Array.isArray(input?.media_ids)
      ? input.media_ids.map((value) => String(value || "").trim().toLowerCase())
        .filter(Boolean)
      : [];
    const ttlDays = Number(input?.ttl_days || 14);
    if (
      !campaignId
      || clientLabel.length < 2 || clientLabel.length > 120
      || !mediaIds.length || mediaIds.length > 50
      || !Number.isInteger(ttlDays) || ttlDays < 1 || ttlDays > 90
    ) {
      throw new CreatorApiError(
        "Для ссылки клиенту нужны кампания, подпись (2–120 знаков) и хотя бы один ролик.",
        { code: "client_review_payload_invalid" },
      );
    }
    const data = await this.call(RPC.issueClientReviewLink, {
      organization_id: String(this.organizationId || ""),
      campaign_id: campaignId,
      client_label: clientLabel,
      media_ids: mediaIds,
      curator_attested: input?.curator_attested === true,
      ttl_days: ttlDays,
      idempotency_key: String(
        input?.idempotency_key || `client-review-${crypto.randomUUID()}`,
      ),
    });
    if (
      !data || data.ok !== true
      || data.version !== "client-review-links-v1"
      || !data.link || typeof data.link !== "object"
    ) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  async revokeClientReviewLink(input) {
    const linkId = String(input?.link_id || "").trim().toLowerCase();
    if (!linkId) {
      throw new CreatorApiError(
        "Не удалось определить ссылку для отзыва.",
        { code: "client_review_payload_invalid" },
      );
    }
    const data = await this.call(RPC.revokeClientReviewLink, {
      organization_id: String(this.organizationId || ""),
      link_id: linkId,
    });
    if (!data || data.ok !== true) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  async listClientReviewLinks(input) {
    const data = await this.call(RPC.listClientReviewLinks, {
      organization_id: String(this.organizationId || ""),
      campaign_id: String(input?.campaign_id || "").trim().toLowerCase(),
    });
    if (!data || data.ok !== true || !Array.isArray(data.links)) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  async listCampaignReviewCandidates(input) {
    const data = await this.call(RPC.listCampaignReviewCandidates, {
      organization_id: String(this.organizationId || ""),
      campaign_id: String(input?.campaign_id || "").trim().toLowerCase(),
    });
    if (!data || data.ok !== true || !Array.isArray(data.candidates)) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  // До-добавление роликов в живую ссылку: клиент видит новые по той же
  // ссылке (фидбек первого прогона: «а дальше роликов нет»).
  async appendClientReviewLinkItems(input) {
    const linkId = String(input?.link_id || "").trim().toLowerCase();
    const mediaIds = Array.isArray(input?.media_ids)
      ? input.media_ids.map((value) => String(value || "").trim().toLowerCase())
        .filter(Boolean)
      : [];
    if (!linkId || !mediaIds.length || mediaIds.length > 50) {
      throw new CreatorApiError(
        "Выберите от 1 до 50 роликов для добавления в ссылку.",
        { code: "client_review_media_ids_invalid" },
      );
    }
    const data = await this.call(RPC.appendClientReviewLinkItems, {
      organization_id: String(this.organizationId || ""),
      link_id: linkId,
      media_ids: mediaIds,
      curator_attested: input?.curator_attested === true,
    });
    if (!data || data.ok !== true) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  // Ступень 2: клиентский ввод («Материалы и бриф» на том же токене).
  async configureClientReviewIntake(input) {
    const data = await this.call(RPC.configureClientReviewIntake, {
      organization_id: String(this.organizationId || ""),
      link_id: String(input?.link_id || "").trim().toLowerCase(),
      intake_enabled: input?.intake_enabled === true,
    });
    if (!data || data.ok !== true) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  async listClientIntake(input) {
    const data = await this.call(RPC.listClientIntake, {
      organization_id: String(this.organizationId || ""),
      link_id: String(input?.link_id || "").trim().toLowerCase(),
    });
    if (
      !data || data.ok !== true
      || !Array.isArray(data.briefs) || !Array.isArray(data.uploads)
    ) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  async decideClientIntakeBrief(input) {
    const decision = String(input?.decision || "").trim();
    const comment = String(input?.comment || "").trim();
    if (!["accepted", "returned"].includes(decision)
      || (decision === "returned" && comment.length < 3)) {
      throw new CreatorApiError(
        "Для возврата брифа нужен комментарий клиенту (от 3 знаков).",
        { code: "client_intake_decision_invalid" },
      );
    }
    const data = await this.call(RPC.decideClientIntakeBrief, {
      organization_id: String(this.organizationId || ""),
      brief_id: String(input?.brief_id || "").trim().toLowerCase(),
      decision,
      ...(comment ? { comment } : {}),
    });
    if (!data || data.ok !== true) {
      throw new CreatorApiError("Витрина ответила в неизвестной форме.");
    }
    return data;
  }

  // «Одобрить и разместить» готовый результат: явное подтверждение полного
  // просмотра + выданный аккаунт + ERID. Создаёт задачу размещения и строку
  // placements; финальную ссылку подтверждает confirmPlacement.
  publishGenerationResult(input) {
    const projectId = requiredProjectId(input?.project_id ?? input?.projectId);
    const erid = String(input?.erid || "").trim().toUpperCase();
    if (!/^[A-Z0-9-]{4,64}$/.test(erid)) {
      throw new CreatorApiError(
        "Укажите ERID маркировки (4–64 знака: латиница, цифры, дефис). Для немаркируемой органики напишите ORGANIC.",
        { code: "publish_result_erid_invalid" },
      );
    }
    if (input?.watch_confirmed !== true) {
      throw new CreatorApiError(
        "Подтвердите, что просмотрели ролик целиком — без этого размещение не создаётся.",
        { code: "publish_result_watch_confirmation_required" },
      );
    }
    // Задача выводится сервером из самого файла; ключ generation_job_id —
    // только когда он реально известен, пустая строка ломает require_uuid.
    const generationJobId = String(input?.generation_job_id || "").trim();
    return this.mutate(RPC.publishGenerationResult, {
      project_id: projectId,
      ...(generationJobId ? { generation_job_id: generationJobId } : {}),
      media_id: String(input?.media_id || "").trim(),
      managed_account_id: String(input?.managed_account_id || "").trim(),
      erid,
      watch_confirmed: true,
      ...(String(input?.note || "").trim()
        ? { note: String(input.note).trim().slice(0, 500) }
        : {}),
    });
  }

  // «Отвергнуть» просмотренный результат: причина обязательна, файл честно
  // уезжает в «Корзину» (восстановим), решение остаётся в metadata и событии.
  rejectGenerationResult(input) {
    const projectId = requiredProjectId(input?.project_id ?? input?.projectId);
    const reason = String(input?.reason || "").trim();
    if (reason.length < 5 || reason.length > 500) {
      throw new CreatorApiError(
        "Коротко объясните, почему ролик отвергнут (от 5 до 500 знаков) — причина сохранится на файле.",
        { code: "reject_result_reason_invalid" },
      );
    }
    if (input?.watch_confirmed !== true) {
      throw new CreatorApiError(
        "Подтвердите, что просмотрели ролик целиком — отказ без просмотра не принимается.",
        { code: "reject_result_watch_confirmation_required" },
      );
    }
    return this.mutate(RPC.rejectGenerationResult, {
      project_id: projectId,
      media_id: String(input?.media_id || "").trim(),
      reason,
      watch_confirmed: true,
    });
  }

  // Голова воронки «Результатов»: сколько роликов на каждом этапе прямо
  // сейчас — из тех же таблиц, которыми живут разделы.
  async resultsFunnel({ projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const data = await this.call(RPC.resultsFunnel, {
      organization_id: String(this.organizationId || ""),
      project_id: normalizedProjectId,
    });
    if (
      !data || data.ok !== true
      || data.version !== "results-funnel-v1"
      || !data.funnel || typeof data.funnel !== "object"
    ) {
      throw new CreatorApiError("Воронка результатов пришла в неизвестной форме.");
    }
    return data.funnel;
  }

  // «Паспорта»: реестр готовых роликов проекта с кратким срезом — товар,
  // движок, деньги, публикации, последние метрики. Одна server-owned
  // read-модель для всех экранов паспорта.
  async contentPassportRegistry({ projectId = "", project_id: projectIdSnake = "", limit = 100 } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const data = await this.call(RPC.contentPassportRegistry, {
      organization_id: String(this.organizationId || ""),
      project_id: normalizedProjectId,
      limit,
    });
    if (
      !data || data.ok !== true
      || data.version !== "content-passport-registry-v1"
      || !Array.isArray(data.passports)
    ) {
      throw new CreatorApiError("Реестр паспортов пришёл в неизвестной форме.");
    }
    return data;
  }

  // Полный паспорт одного готового ролика: продукт, ТЗ, материалы,
  // производство, публикации, метрики числителями/знаменателями, хронология.
  async contentResultPassport({ projectId = "", project_id: projectIdSnake = "", mediaId = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const data = await this.call(RPC.contentResultPassport, {
      organization_id: String(this.organizationId || ""),
      project_id: normalizedProjectId,
      media_id: String(mediaId || ""),
    });
    if (
      !data || data.ok !== true
      || data.version !== "content-result-passport-v1"
      || !data.media || typeof data.media !== "object"
      || !data.execution || typeof data.execution !== "object"
      || !Array.isArray(data.timeline)
    ) {
      throw new CreatorApiError("Паспорт ролика пришёл в неизвестной форме.");
    }
    return data;
  }

  // Папка «Гипотезы» (контур №3): проверяемые утверждения с версиями и
  // человеческими решениями. Confirmed ставит только человек.
  async contentHypotheses({ projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const data = await this.call(RPC.contentHypotheses, {
      organization_id: String(this.organizationId || ""),
      project_id: normalizedProjectId,
    });
    if (
      !data || data.ok !== true
      || data.version !== "content-hypotheses-v1"
      || !Array.isArray(data.hypotheses)
    ) {
      throw new CreatorApiError("Список гипотез пришёл в неизвестной форме.");
    }
    return data;
  }

  async contentHypothesis({ projectId = "", project_id: projectIdSnake = "", hypothesisId = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const data = await this.call(RPC.contentHypothesis, {
      organization_id: String(this.organizationId || ""),
      project_id: normalizedProjectId,
      hypothesis_id: String(hypothesisId || ""),
    });
    if (
      !data || data.ok !== true
      || data.version !== "content-hypothesis-v1"
      || !data.hypothesis || typeof data.hypothesis !== "object"
      || !Array.isArray(data.versions)
    ) {
      throw new CreatorApiError("Гипотеза пришла в неизвестной форме.");
    }
    return data;
  }

  async saveContentHypothesis(payload = {}) {
    const data = await this.call(RPC.saveContentHypothesis, {
      organization_id: String(this.organizationId || ""),
      ...payload,
    });
    if (!data || data.ok !== true || data.version !== "content-hypothesis-save-v1") {
      throw new CreatorApiError("Гипотеза сохранена не полностью. Обновите раздел.");
    }
    return data;
  }

  async approveContentHypothesisVersion({ hypothesisVersionId = "" } = {}) {
    const data = await this.call(RPC.approveContentHypothesisVersion, {
      organization_id: String(this.organizationId || ""),
      hypothesis_version_id: String(hypothesisVersionId || ""),
    });
    if (!data || data.ok !== true || data.status !== "approved") {
      throw new CreatorApiError("Версия гипотезы не утвердилась. Обновите раздел.");
    }
    return data;
  }

  async decideContentHypothesis({ hypothesisId = "", action = "", reason = "" } = {}) {
    const data = await this.call(RPC.decideContentHypothesis, {
      organization_id: String(this.organizationId || ""),
      hypothesis_id: String(hypothesisId || ""),
      action: String(action || ""),
      reason: String(reason || ""),
    });
    if (!data || data.ok !== true || data.version !== "content-hypothesis-decision-v1") {
      throw new CreatorApiError("Решение по гипотезе не записалось. Обновите раздел.");
    }
    return data;
  }

  // Вкладка «Команда → Аккаунты»: реестр владения с выдачами, подключениями
  // и счётчиками размещений. Без регистрационных реквизитов.
  async teamAccounts() {
    const data = await this.call(RPC.teamAccounts, {
      organization_id: String(this.organizationId || ""),
    });
    if (
      !data || data.ok !== true
      || data.version !== "team-accounts-v1"
      || !Array.isArray(data.accounts)
    ) {
      throw new CreatorApiError("Реестр аккаунтов пришёл в неизвестной форме.");
    }
    return data.accounts;
  }

  confirmPlacement(taskId, finalUrl, complianceAck) {
    const projectScope = arguments[3] && typeof arguments[3] === "object"
      ? arguments[3]
      : {};
    const normalizedProjectId = requiredProjectId(
      projectScope.project_id ?? projectScope.projectId,
    );
    return this.mutate(RPC.confirmPlacement, {
      task_id: taskId,
      final_url: finalUrl,
      compliance_ack: complianceAck === true,
      project_id: normalizedProjectId,
    });
  }

  transitionTask(taskId, status, result = {}, { projectId = "", project_id: projectIdSnake = "" } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    return this.mutate(RPC.transitionTask, {
      task_id: taskId,
      status,
      result,
      project_id: normalizedProjectId,
    });
  }

  createFeedback(feedback) {
    return this.mutate(RPC.createFeedback, feedback);
  }

  registerMedia(media) {
    const kind = String(media?.kind || "").trim();
    const projectId = requiredProjectId(media?.project_id ?? media?.projectId);
    const mediaPayload = { ...(media || {}) };
    delete mediaPayload.projectId;
    const payload = {
      ...mediaPayload,
      kind,
      project_id: projectId,
    };
    if (mediaKindRequiresProduct(kind)) {
      const sku = String(media?.sku || "").trim();
      const productName = String(media?.product_name || "").trim();
      if (!sku || sku.length > 120) {
        throw new CreatorApiError(
          "Укажите точный артикул товара длиной до 120 символов.",
          { code: "media_sku_required" },
        );
      }
      if (productName.length < 2 || productName.length > 180) {
        throw new CreatorApiError(
          "Укажите точное название товара длиной от 2 до 180 символов.",
          { code: "media_product_name_required" },
        );
      }
      payload.sku = sku;
      payload.product_name = productName;
    } else {
      delete payload.sku;
      delete payload.product_name;
    }
    return this.mutate(RPC.registerMedia, payload);
  }

  async exactYoutubeSourceQueue({
    projectId = "",
    project_id: projectIdSnake = "",
    limit = 50,
  } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const normalizedLimit = Number(limit);
    if (
      !Number.isInteger(normalizedLimit)
      || normalizedLimit < 1
      || normalizedLimit > 50
    ) {
      throw new CreatorApiError("Лимит источников имеет неверный формат.", {
        code: "exact_youtube_source_queue_limit_invalid",
      });
    }
    const response = await this.call(
      RPC.exactYoutubeSourceQueue,
      this.withOrganization({
        project_id: normalizedProjectId,
        limit: normalizedLimit,
      }),
    );
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    const lifecycleProjected =
      source?.contract?.research_lifecycle_projected === true;
    const optionalUuidInvalid = (value) => value !== undefined
      && value !== null
      && !isUuid(String(value || "").trim().toLowerCase());
    const optionalDateInvalid = (value) => value !== undefined
      && value !== null
      && (
        typeof value !== "string"
        || !Number.isFinite(Date.parse(value))
      );
    const lifecycleInvalid = (item) => {
      if (!lifecycleProjected) return false;
      if (
        typeof item?.media_ready !== "boolean"
        || item.media_ready !== item.analysis_ready
      ) return true;
      const lifecycle = item?.research_lifecycle;
      if (!lifecycle || typeof lifecycle !== "object" || Array.isArray(lifecycle)) {
        return true;
      }
      const state = String(lifecycle.state || "").trim();
      if (
        EXACT_YOUTUBE_RESEARCH_LIFECYCLE_ACTIONS[state]
          !== lifecycle.next_action
      ) return true;
      const effective = lifecycle.effective;
      if (
        !effective
        || typeof effective !== "object"
        || Array.isArray(effective)
        || typeof effective.has_approved_recommendations !== "boolean"
      ) return true;
      const effectiveHasApproval = effective.has_approved_recommendations;
      if (effectiveHasApproval) {
        if (
          !isUuid(String(effective.selection_id || "").trim().toLowerCase())
          || !isUuid(String(effective.run_id || "").trim().toLowerCase())
          || !isUuid(String(effective.receipt_id || "").trim().toLowerCase())
          || !effective.selected_at
          || optionalDateInvalid(effective.selected_at)
        ) return true;
      } else if (
        optionalUuidInvalid(effective.selection_id)
        || optionalUuidInvalid(effective.run_id)
        || optionalUuidInvalid(effective.receipt_id)
        || optionalDateInvalid(effective.selected_at)
      ) return true;

      const latest = lifecycle.latest;
      if (state === "not_started") {
        return latest !== null || effectiveHasApproval;
      }
      if (!latest || typeof latest !== "object" || Array.isArray(latest)) {
        return true;
      }
      const runStatus = String(latest.run_status || "").trim();
      const receiptId = String(latest.receipt_id || "").trim().toLowerCase();
      const selectionId = String(latest.learning_selection_id || "")
        .trim()
        .toLowerCase();
      const dispositionDecision = String(latest.disposition_decision || "")
        .trim();
      const learningDecision = String(latest.learning_decision || "").trim();
      if (
        !isUuid(String(latest.binding_id || "").trim().toLowerCase())
        || !isUuid(String(latest.run_id || "").trim().toLowerCase())
        || !EXACT_YOUTUBE_RESEARCH_RUN_STATUS_SET.has(runStatus)
        || !AI_PRODUCT_CATEGORY_SET.has(
          String(latest.product_category || "").trim().toLowerCase(),
        )
        || !latest.bound_at
        || optionalDateInvalid(latest.bound_at)
        || optionalDateInvalid(latest.finished_at)
        || optionalDateInvalid(latest.received_at)
        || optionalDateInvalid(latest.selected_at)
        || (receiptId && !isUuid(receiptId))
        || (selectionId && !isUuid(selectionId))
        || (receiptId && latest.receipt_status !== "awaiting_human_review")
        || (!receiptId && latest.receipt_status !== undefined)
        || (!receiptId && latest.received_at !== undefined)
        || (!receiptId && dispositionDecision)
        || (!receiptId && selectionId)
        || (selectionId && !latest.selected_at)
        || (dispositionDecision
          && !new Set(["approve", "reject"]).has(dispositionDecision))
        || (learningDecision
          && !new Set(["approve", "reject"]).has(learningDecision))
        || Boolean(selectionId) !== Boolean(learningDecision)
      ) return true;

      if (state === "analysis_in_progress") {
        return !new Set(["queued", "processing"]).has(runStatus)
          || Boolean(receiptId);
      }
      if (state === "analysis_failed") {
        return !new Set(["failed", "cancelled"]).has(runStatus)
          || Boolean(receiptId);
      }
      if (runStatus !== "completed") return true;
      if (state === "completed_without_ai_receipt") {
        return Boolean(receiptId) || Boolean(selectionId);
      }
      if (!receiptId) return true;
      if (state === "awaiting_learning_selection") {
        return Boolean(selectionId) || dispositionDecision === "reject";
      }
      if (state === "recommendations_ready") {
        return learningDecision !== "approve" || !effectiveHasApproval;
      }
      if (state === "excluded") {
        return learningDecision !== "reject" && dispositionDecision !== "reject";
      }
      return true;
    };
    const attachedItemInvalid = (item) => {
      if (source?.version !== "exact-youtube-source-queue-v2") return false;
      if (item?.status === "awaiting_media") {
        return item?.media_required !== true
          || item?.attachment !== null
          || item?.media !== null
          || item?.analysis_ready !== false
          || item?.next_action !== "upload_lawful_mp4";
      }
      const sourceId = String(item?.id || "").trim().toLowerCase();
      const attachmentMediaId = String(item?.attachment?.media_id || "")
        .trim()
        .toLowerCase();
      const mediaId = String(item?.media?.id || "").trim().toLowerCase();
      const sourceHash = String(item?.source_hash || "").trim().toLowerCase();
      const mediaSha256 = String(item?.media?.sha256 || "").trim().toLowerCase();
      const attachmentInvalid = item?.status !== "media_attached"
        || item?.media_required !== false
        || !isUuid(String(item?.attachment?.id || "").trim().toLowerCase())
        || item?.attachment?.status !== "attached"
        || String(item?.attachment?.source_id || "").trim().toLowerCase()
          !== sourceId
        || !isUuid(attachmentMediaId)
        || item?.attachment?.rights_confirmed !== true
        || item?.attachment?.media_matches_registered_source !== true
        || !PROVIDER_READINESS_SHA256_PATTERN.test(sourceHash)
        || String(item?.attachment?.source_hash_snapshot || "")
          .trim().toLowerCase() !== sourceHash;
      if (attachmentInvalid) return true;
      if (item?.analysis_ready !== true) {
        return item?.analysis_ready !== false
          || item?.next_action !== "restore_attached_media"
          || (item?.media !== null && (
            mediaId !== attachmentMediaId
            || String(item?.media?.project_id || "").trim().toLowerCase()
              !== normalizedProjectId
          ));
      }
      return item?.next_action !== "start_exact_media_analysis"
        || attachmentMediaId !== mediaId
        || !PROVIDER_READINESS_SHA256_PATTERN.test(mediaSha256)
        || String(item?.attachment?.media_sha256_snapshot || "")
          .trim().toLowerCase() !== mediaSha256
        || String(item?.media?.project_id || "").trim().toLowerCase()
          !== normalizedProjectId
        || item?.media?.status !== "ready"
        || item?.media?.mime_type !== "video/mp4"
        || item?.media?.kind !== "source_video"
        || item?.media?.artifact_class !== "source"
        || item?.media?.lifecycle_stage !== "sources";
    };
    if (
      source?.ok !== true
      || !new Set([
        "exact-youtube-source-queue-v1",
        "exact-youtube-source-queue-v2",
      ]).has(source?.version)
      || String(source?.project_id || "").trim().toLowerCase()
        !== normalizedProjectId
      || !Array.isArray(source?.sources)
      || source.sources.some((item) => (
        !item
        || typeof item !== "object"
        || Array.isArray(item)
        || !isUuid(String(item.id || "").trim().toLowerCase())
        || String(item.project_id || "").trim().toLowerCase()
          !== normalizedProjectId
        || lifecycleInvalid(item)
        || attachedItemInvalid(item)
      ))
      || source?.contract?.url_is_video_evidence !== false
      || source?.contract?.requires_lawful_mp4 !== true
      || source?.contract?.unattached_source_affects_learning !== false
      || source?.contract?.unattached_source_affects_generation !== false
      || source?.contract?.external_call_started !== false
      || source?.contract?.paid_call_started !== false
      || (source?.version === "exact-youtube-source-queue-v2" && (
        source?.contract?.attachment_is_append_only !== true
        || source?.contract?.attached_source_affects_learning !== false
        || source?.contract?.attached_source_affects_generation !== false
        || source?.contract?.attachment_starts_analysis !== false
        || source?.contract?.source_row_mutated !== false
        || (lifecycleProjected && (
          source?.contract?.analysis_ready_is_media_ready !== true
          || source?.contract?.research_lifecycle_read_only !== true
          || source?.contract?.research_lifecycle_starts_analysis !== false
          || source?.contract?.research_lifecycle_starts_provider_call !== false
        ))
      ))
    ) {
      throw new CreatorApiError(
        "Сервер не подтвердил актуальную очередь точных YouTube-источников.",
        { code: "exact_youtube_source_queue_response_invalid" },
      );
    }
    return source;
  }

  async attachExactYoutubeMedia({
    projectId = "",
    project_id: projectIdSnake = "",
    sourceId = "",
    source_id: sourceIdSnake = "",
    mediaId = "",
    media_id: mediaIdSnake = "",
    rightsConfirmed = false,
    rights_confirmed: rightsConfirmedSnake = false,
    mediaMatchesRegisteredSource = false,
    media_matches_registered_source: mediaMatchesRegisteredSourceSnake = false,
  } = {}) {
    const normalizedProjectId = requiredProjectId(projectIdSnake || projectId);
    const normalizedSourceId = String(sourceIdSnake || sourceId || "")
      .trim()
      .toLowerCase();
    const normalizedMediaId = String(mediaIdSnake || mediaId || "")
      .trim()
      .toLowerCase();
    if (!isUuid(normalizedSourceId)) {
      throw new CreatorApiError(
        "Не удалось определить точный YouTube-источник. Вернитесь в ИИ-центр и откройте загрузку заново.",
        { code: "exact_youtube_media_attachment_source_required" },
      );
    }
    if (!isUuid(normalizedMediaId)) {
      throw new CreatorApiError(
        "MP4 сохранён, но сервер не вернул его идентификатор. Обновите Файлы перед повтором.",
        { code: "exact_youtube_media_attachment_media_required" },
      );
    }
    if (rightsConfirmed !== true && rightsConfirmedSnake !== true) {
      throw new CreatorApiError(
        "Подтвердите право команды использовать MP4 для разбора.",
        { code: "exact_youtube_media_attachment_rights_required" },
      );
    }
    if (
      mediaMatchesRegisteredSource !== true
      && mediaMatchesRegisteredSourceSnake !== true
    ) {
      throw new CreatorApiError(
        "Подтвердите, что MP4 является именно зарегистрированным YouTube-роликом, а не другим видео по теме.",
        { code: "exact_youtube_media_attachment_source_match_required" },
      );
    }
    const response = await this.mutate(RPC.attachExactYoutubeMedia, {
      project_id: normalizedProjectId,
      source_id: normalizedSourceId,
      media_id: normalizedMediaId,
      rights_confirmed: true,
      media_matches_registered_source: true,
    });
    const source = response?.data && typeof response.data === "object"
      && !Array.isArray(response.data)
      ? response.data
      : response;
    if (
      source?.ok !== true
      || source?.version !== "exact-youtube-media-attachment-v1"
      || String(source?.project_id || "").trim().toLowerCase()
        !== normalizedProjectId
      || String(source?.source?.id || "").trim().toLowerCase()
        !== normalizedSourceId
      || source?.source?.derived_status !== "media_attached"
      || String(source?.attachment?.source_id || "").trim().toLowerCase()
        !== normalizedSourceId
      || String(source?.attachment?.media_id || "").trim().toLowerCase()
        !== normalizedMediaId
      || !isUuid(String(source?.attachment?.id || "").trim().toLowerCase())
      || source?.attachment?.status !== "attached"
      || source?.attachment?.rights_confirmed !== true
      || source?.attachment?.media_matches_registered_source !== true
      || String(source?.media?.id || "").trim().toLowerCase()
        !== normalizedMediaId
      || String(source?.media?.project_id || "").trim().toLowerCase()
        !== normalizedProjectId
      || source?.media?.mime_type !== "video/mp4"
      || source?.media?.kind !== "source_video"
      || source?.contract?.append_only !== true
      || source?.contract?.exact_project_scope !== true
      || source?.contract?.registered_media_reused !== true
      || source?.contract?.identity_attestation_recorded !== true
      || source?.contract?.source_row_mutated !== false
      || source?.contract?.analysis_ready !== true
      || source?.contract?.analysis_started !== false
      || source?.contract?.external_call_started !== false
      || source?.contract?.paid_call_started !== false
    ) {
      throw new CreatorApiError(
        "MP4 сохранён, но сервер не подтвердил точную привязку к исследованию. Повторите только привязку — файл загружать заново не нужно.",
        { code: "exact_youtube_media_attachment_response_invalid" },
      );
    }
    return source;
  }

  captureEvent(event) {
    return this.mutate(RPC.captureEvent, event, { retainOnError: false });
  }

  withOrganization(payload) {
    if (this.organizationId === null || this.organizationId === undefined) {
      throw new CreatorApiError(
        "Для аккаунта ещё не назначена команда. Обратитесь к руководителю.",
        { code: "membership_required" },
      );
    }
    return { ...payload, organization_id: this.organizationId };
  }

  async mutate(functionName, payload, {
    retainOnError = true,
    fingerprintPayload = null,
  } = {}) {
    const scopedPayload = this.withOrganization(payload);
    const fingerprintScope = fingerprintPayload === null
      ? scopedPayload
      : this.withOrganization(fingerprintPayload);
    const fingerprint = `${functionName}:${stableStringify(fingerprintScope)}`;
    const idempotencyKey = this.mutationKeys[fingerprint] || crypto.randomUUID();
    this.mutationKeys[fingerprint] = idempotencyKey;
    writeMutationKeys(this.mutationKeys);

    try {
      const response = await this.call(functionName, {
        ...scopedPayload,
        idempotency_key: idempotencyKey,
      });
      delete this.mutationKeys[fingerprint];
      writeMutationKeys(this.mutationKeys);
      return response;
    } catch (error) {
      if (!retainOnError) {
        delete this.mutationKeys[fingerprint];
        writeMutationKeys(this.mutationKeys);
      }
      throw error;
    }
  }

  async uploadPrivateObject(objectKey, file) {
    this.assertPrivateObjectKey(objectKey);
    const { data, error } = await this.supabase.storage
      .from(this.storageBucket)
      .upload(objectKey, file, {
        cacheControl: "3600",
        contentType: file.type || "application/octet-stream",
        upsert: false,
      });

    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }
    return data;
  }

  async uploadAiKnowledgeObject(objectKey, file, contentType = file?.type) {
    this.assertAiKnowledgeObjectKey(AI_KNOWLEDGE_BUCKET, objectKey);
    const mimeType = String(contentType || "").trim().toLowerCase();
    const sizeBytes = Number(file?.size);
    if (
      !AI_KNOWLEDGE_MIME_TYPES.has(mimeType)
      || !Number.isInteger(sizeBytes)
      || sizeBytes < 1
      || sizeBytes > 25 * 1024 * 1024
    ) {
      throw new CreatorApiError("Файл знаний не прошёл проверку типа или размера.", {
        code: "ai_knowledge_source_file_invalid",
      });
    }
    const { data, error } = await this.supabase.storage
      .from(AI_KNOWLEDGE_BUCKET)
      .upload(objectKey, file, {
        cacheControl: "3600",
        contentType: mimeType,
        upsert: false,
      });
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return data;
  }

  async removeAiKnowledgeObject(objectKey) {
    this.assertAiKnowledgeObjectKey(AI_KNOWLEDGE_BUCKET, objectKey);
    const { error } = await this.supabase.storage
      .from(AI_KNOWLEDGE_BUCKET)
      .remove([objectKey]);
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
  }


  async removePrivateObject(objectKey) {
    this.assertPrivateObjectKey(objectKey);
    const { error } = await this.supabase.storage
      .from(this.storageBucket)
      .remove([objectKey]);
    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }
  }

  async downloadPrivateObject(objectKey) {
    this.assertReadableObjectKey(objectKey);
    const { data, error } = await this.supabase.storage
      .from(this.storageBucket)
      .download(objectKey);
    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }
    if (!data || typeof data.arrayBuffer !== "function") {
      throw new CreatorApiError(
        "Защищённый файл не был возвращён хранилищем.",
        { code: "private_object_download_missing" },
      );
    }
    return data;
  }

  async removePrivateObjects(objectKeys) {
    const keys = [...new Set((objectKeys || []).map((value) => String(value || "").trim()).filter(Boolean))];
    if (!keys.length) return;
    keys.forEach((objectKey) => this.assertPrivateObjectKey(objectKey));
    const { error } = await this.supabase.storage
      .from(this.storageBucket)
      .remove(keys);
    if (error) {
      throw new CreatorApiError(toFriendlyMessage(error), error);
    }
  }

  async signedPrivateObjectUrls(objectKeys, expiresIn = 600) {
    const keys = [...new Set((objectKeys || []).map(String).filter(Boolean))];
    if (!keys.length) return new Map();
    keys.forEach((key) => this.assertReadableObjectKey(key));
    const { data, error } = await this.supabase.storage
      .from(this.storageBucket)
      .createSignedUrls(keys, Math.min(900, Math.max(60, Number(expiresIn) || 600)));
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return new Map(
      (data || [])
        .filter((item) => item?.path && item?.signedUrl && !item?.error)
        .map((item) => [item.path, item.signedUrl]),
    );
  }

  async uploadTrainingPracticalObject(bucketId, pathPrefix, objectKey, file) {
    this.assertTrainingPracticalObjectKey(bucketId, pathPrefix, objectKey, true);
    const { data, error } = await this.supabase.storage
      .from(bucketId)
      .upload(objectKey, file, {
        cacheControl: "3600",
        contentType: file.type || "video/mp4",
        upsert: false,
      });
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return data;
  }

  async removeTrainingPracticalObject(bucketId, pathPrefix, objectKey) {
    this.assertTrainingPracticalObjectKey(bucketId, pathPrefix, objectKey, true);
    const { error } = await this.supabase.storage.from(bucketId).remove([objectKey]);
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
  }

  async signedTrainingPracticalObjectUrls(bucketId, objectKeys, expiresIn = 600) {
    const keys = [...new Set((objectKeys || []).map(String).filter(Boolean))];
    if (!keys.length) return new Map();
    keys.forEach((key) => this.assertTrainingPracticalObjectKey(bucketId, "", key, false));
    const { data, error } = await this.supabase.storage
      .from(bucketId)
      .createSignedUrls(keys, Math.min(900, Math.max(60, Number(expiresIn) || 600)));
    if (error) throw new CreatorApiError(toFriendlyMessage(error), error);
    return new Map(
      (data || [])
        .filter((item) => item?.path && item?.signedUrl && !item?.error)
        .map((item) => [item.path, item.signedUrl]),
    );
  }

  assertTrainingPracticalObjectKey(bucketId, pathPrefix, objectKey, requireOwnPrefix) {
    const bucket = String(bucketId || "");
    const prefix = String(pathPrefix || "");
    const key = String(objectKey || "");
    const uuid = "[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}";
    const pattern = new RegExp(`^${uuid}/${uuid}/practical/[0-9a-f-]{20,80}\\.(?:mp4|webm|mov)$`, "iu");
    if (
      bucket !== "contentengine-training"
      || !pattern.test(key)
      || key.includes("..")
      || key.includes("\\")
      || (requireOwnPrefix && (!prefix || !key.startsWith(prefix)))
    ) {
      throw new CreatorApiError("Нет доступа к защищённой пробной работе.", {
        code: "training_practical_storage_denied",
      });
    }
  }

  assertPrivateObjectKey(objectKey) {
    const key = String(objectKey || "");
    if (
      !this.storagePrefix ||
      !key.startsWith(this.storagePrefix) ||
      key === this.storagePrefix ||
      key.includes("..") ||
      key.includes("\\")
    ) {
      throw new CreatorApiError("Нет доступа к этой папке медиатеки.", {
        code: "storage_access_denied",
      });
    }
  }

  assertAiKnowledgeObjectKey(bucketId, objectKey) {
    const key = String(objectKey || "");
    if (
      bucketId !== AI_KNOWLEDGE_BUCKET
      || !this.storagePrefix
      || !key.startsWith(`${this.storagePrefix}ai-knowledge/`)
      || key === `${this.storagePrefix}ai-knowledge/`
      || key.includes("..")
      || key.includes("\\")
    ) {
      throw new CreatorApiError("Нет доступа к защищённой базе знаний.", {
        code: "storage_access_denied",
      });
    }
  }


  assertReadableObjectKey(objectKey) {
    const key = String(objectKey || "");
    const organizationPrefix = String(this.storagePrefix || "").split("/")[0];
    const withinOrganization = organizationPrefix && key.startsWith(`${organizationPrefix}/`);
    if (!withinOrganization || key.includes("..") || key.includes("\\")) {
      throw new CreatorApiError("Нет доступа к этой папке медиатеки.", {
        code: "storage_access_denied",
      });
    }
  }
}

function normalizeContentReviewCodes(values) {
  if (!Array.isArray(values) || values.length > 80) {
    throw new CreatorApiError("Список подтверждений проверки имеет неверный формат.", {
      code: "content_review_decision_codes_invalid",
    });
  }
  const normalized = [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))];
  if (normalized.some((value) => value.length > 120 || !/^[a-z0-9_.:-]+$/iu.test(value))) {
    throw new CreatorApiError("Список подтверждений проверки имеет неверный формат.", {
      code: "content_review_decision_codes_invalid",
    });
  }
  return normalized;
}

const GENERATED_VIDEO_SOUND_ISSUE_CODES = new Set([
  "slurred_words",
  "wrong_words",
  "foreign_accent",
  "numbers_units",
  "wrong_voice_tone",
  "lip_sync",
  "noise_clipping",
  "silence_dropout",
  "unexpected_audio",
  "other",
]);

function normalizeGeneratedVideoSoundAssessment(value, { required = false } = {}) {
  if (value === null || value === undefined || value === "") {
    if (!required) return null;
    throw new CreatorApiError("После полного прослушивания зафиксируйте отдельную оценку звука.", {
      code: "content_review_sound_assessment_required",
    });
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CreatorApiError("Оценка звука имеет неверный формат.", {
      code: "content_review_sound_assessment_invalid",
    });
  }
  const status = String(value.status || "").trim().toLowerCase();
  if (!status && !required) return null;
  const issueCodes = [...new Set(
    (Array.isArray(value.issueCodes) ? value.issueCodes : [])
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean),
  )];
  const note = String(value.note || "").trim();
  if (
    !["clear", "issues_found", "silent_expected"].includes(status)
    || issueCodes.length > GENERATED_VIDEO_SOUND_ISSUE_CODES.size
    || issueCodes.some((code) => !GENERATED_VIDEO_SOUND_ISSUE_CODES.has(code))
    || note.length > 1_000
  ) {
    throw new CreatorApiError("Оценка звука имеет неверный формат.", {
      code: "content_review_sound_assessment_invalid",
    });
  }
  return {
    audio: value.audio === true,
    status,
    issue_codes: issueCodes,
    spoken_script_heard_exactly_confirmed:
      value.spokenScriptHeardExactlyConfirmed === true,
    diction_clear_confirmed: value.dictionClearConfirmed === true,
    voice_style_confirmed: value.voiceStyleConfirmed === true,
    audio_sync_confirmed: value.audioSyncConfirmed === true,
    silence_expected_confirmed: value.silenceExpectedConfirmed === true,
    note,
  };
}

const MUTATION_KEY_STORAGE = "contentengine.pending-mutation-keys.v1";

function readMutationKeys() {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(MUTATION_KEY_STORAGE) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function writeMutationKeys(keys) {
  try {
    window.sessionStorage.setItem(MUTATION_KEY_STORAGE, JSON.stringify(keys));
  } catch {
    // RPC idempotency still works for retries made before a page reload.
  }
}

function hasExactObjectKeys(value, keys) {
  return Boolean(value)
    && typeof value === "object"
    && !Array.isArray(value)
    && Object.keys(value).length === keys.length
    && keys.every((key) => Object.prototype.hasOwnProperty.call(value, key));
}

function generationStrategyExactUuid(value) {
  return typeof value === "string"
    && value !== "00000000-0000-0000-0000-000000000000"
    && GENERATION_STRATEGY_UUID_PATTERN.test(value);
}

function generationStrategyExactBoundedText(value, minimum, maximum) {
  return typeof value === "string"
    && value === value.trim()
    && value.length >= minimum
    && value.length <= maximum
    && !/[\u0000-\u001f\u007f-\u009f]/u.test(value);
}

function generationStrategySpecSelectionValid(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const strategyId = value.strategy_id;
  const rules = GENERATION_STRATEGY_SPEC_SELECTION_RULES[strategyId];
  if (!rules) return false;
  const dimension = rules.dimension;
  if (
    !hasExactObjectKeys(value, [
      "version",
      "strategy_id",
      "recipe_version",
      "duration_seconds",
      dimension,
      "audio",
      "assets",
      "attestations",
    ])
    || value.version !== "2026-08-14.v1"
    || value.recipe_version !== "2026-06"
    || !Number.isSafeInteger(value.duration_seconds)
    || value.duration_seconds < 4
    || value.duration_seconds > 15
    || typeof value.audio !== "boolean"
    || typeof value[dimension] !== "string"
    || !rules.dimensions.includes(value[dimension])
    || !Array.isArray(value.assets)
    // Нижняя граница — один: у «Дуэта» ровно один ассет, и двойка отвергала бы
    // его ещё до проверки ролей.
    || value.assets.length < 1
    || value.assets.length > 15
    || !hasExactObjectKeys(value.attestations, rules.attestations)
    || rules.attestations.some((key) => value.attestations[key] !== true)
  ) return false;

  const counts = new Map();
  const mediaIds = new Set();
  for (const asset of value.assets) {
    if (!asset || typeof asset !== "object" || Array.isArray(asset)) return false;
    const role = asset.role;
    if (!Object.prototype.hasOwnProperty.call(rules.roles, role)) return false;
    const optionalKeys = [
      ...(Object.prototype.hasOwnProperty.call(asset, "duration_seconds")
        ? ["duration_seconds"]
        : []),
      ...(Object.prototype.hasOwnProperty.call(asset, "view") ? ["view"] : []),
    ];
    if (
      !hasExactObjectKeys(asset, ["role", "media_id", ...optionalKeys])
      || !generationStrategyExactUuid(asset.media_id)
      || mediaIds.has(asset.media_id)
    ) return false;
    mediaIds.add(asset.media_id);
    counts.set(role, (counts.get(role) || 0) + 1);

    const hasDuration = Object.prototype.hasOwnProperty.call(
      asset,
      "duration_seconds",
    );
    const hasView = Object.prototype.hasOwnProperty.call(asset, "view");
    if (role === "source_video") {
      if (
        hasView
        || (hasDuration && (
          typeof asset.duration_seconds !== "number"
          || !Number.isFinite(asset.duration_seconds)
          || asset.duration_seconds <= 0
          || asset.duration_seconds > 3_600
        ))
        || (strategyId === "viral_product_swap" && (
          !hasDuration
          || asset.duration_seconds < 1.8
          || asset.duration_seconds > 15
        ))
      ) return false;
    } else if (hasDuration) {
      return false;
    }
    if (role === "new_product_image") {
      if (hasView && !["front", "side", "back"].includes(asset.view)) {
        return false;
      }
    } else if (hasView) {
      return false;
    }
  }
  return Object.entries(rules.roles).every(([role, limits]) => {
    const count = counts.get(role) || 0;
    return count >= limits[0] && count <= limits[1];
  });
}

function generationStrategyMechanicsSummaryValid(value) {
  if (
    !hasExactObjectKeys(value, GENERATION_STRATEGY_MECHANICS_KEYS)
    || value.version !== "generation-strategy-mechanics-summary-v1"
    || !generationStrategyExactBoundedText(value.hook, 20, 160)
    || !generationStrategyExactBoundedText(value.pacing, 8, 100)
    || !generationStrategyExactBoundedText(value.camera_language, 8, 100)
    || !generationStrategyExactBoundedText(value.composition, 8, 100)
    || !generationStrategyExactBoundedText(value.audio_pattern, 8, 100)
    || !generationStrategyExactBoundedText(value.cta_pattern, 8, 100)
    || !Array.isArray(value.beat_sequence)
    || value.beat_sequence.length < 2
    || value.beat_sequence.length > 6
    || value.beat_sequence.some((beat) =>
      !generationStrategyExactBoundedText(beat, 12, 120)
    )
    || new Set(value.beat_sequence).size !== value.beat_sequence.length
  ) return false;
  try {
    return JSON.stringify(value).length <= 4_096;
  } catch {
    return false;
  }
}

function assertGenerationStrategySpecPrepareRequest(request, organizationId) {
  const organization = String(organizationId || "");
  const selectionValid = generationStrategySpecSelectionValid(
    request?.selection,
  );
  const strategyId = selectionValid ? request.selection.strategy_id : "";
  const mechanicsValid = strategyId === "viral_product_swap"
    ? request?.mechanics_summary === null
    : ["viral_avatar_ugc", "viral_rebuild"].includes(strategyId)
      && generationStrategyMechanicsSummaryValid(request?.mechanics_summary);
  const duetProduct = strategyId === "viral_avatar_ugc";
  if (
    !hasExactObjectKeys(
      request,
      duetProduct
        ? GENERATION_STRATEGY_SPEC_PREPARE_DUET_KEYS
        : GENERATION_STRATEGY_SPEC_PREPARE_REQUEST_KEYS,
    )
    || (duetProduct && !generationStrategyExactUuid(request.product_id))
    || request.version !== "generation-strategy-spec-prepare-request-v1"
    || !generationStrategyExactUuid(organization)
    || request.organization_id !== organization
    || !generationStrategyExactUuid(request.project_id)
    || !RESEARCH_OUTCOME_PLATFORMS.has(request.platform)
    || !AI_PRODUCT_CATEGORY_SET.has(request.product_category)
    || !selectionValid
    || !generationStrategyExactBoundedText(request.editable_intent, 1, 800)
    || !generationStrategyExactBoundedText(request.proposed_prompt, 1, 1_200)
    || !mechanicsValid
    || request.confirmation !== true
    || !generationStrategyExactBoundedText(request.idempotency_key, 8, 120)
    || !generationStrategyExactBoundedText(request.reason, 3, 500)
  ) {
    throw new CreatorApiError(
      "Параметры стратегии или механики изменились. Обновите форму и подготовьте техническую версию заново.",
      { code: "generation_strategy_spec_prepare_payload_invalid" },
    );
  }
  return request;
}

// Список ключей привязки под конкретный запрос: обязательные плюс те из
// закрытого набора необязательных, что действительно пришли. Необязательные
// встают перед confirmation — там же, где стоит engine в эталонной форме
// strategy_bind_engine.
function generationStrategyBindRequestKeys(request) {
  const base = GENERATION_STRATEGY_REQUEST_KEYS.strategy_bind;
  const present = GENERATION_STRATEGY_BIND_OPTIONAL_KEYS.filter((key) =>
    request
    && typeof request === "object"
    && Object.prototype.hasOwnProperty.call(request, key)
  );
  if (present.length === 0) return base;
  const cut = base.indexOf("confirmation");
  return Object.freeze([
    ...base.slice(0, cut),
    ...present,
    ...base.slice(cut),
  ]);
}

function assertGenerationStrategyRuntimeRequest(action, request, organizationId) {
  const bindWithEngine = action === "strategy_bind"
    && request
    && typeof request === "object"
    && Object.prototype.hasOwnProperty.call(request, "engine");
  const bindWithPresenter = action === "strategy_bind"
    && request
    && typeof request === "object"
    && Object.prototype.hasOwnProperty.call(request, "duet_presenter_id");
  const keys = action === "strategy_reconcile"
    && request?.resolution === "attach_existing_task"
    ? GENERATION_STRATEGY_RECONCILE_ATTACH_REQUEST_KEYS
    : action === "strategy_bind"
    ? generationStrategyBindRequestKeys(request)
    : GENERATION_STRATEGY_REQUEST_KEYS[action];
  const organization = String(organizationId || "");
  const uuidFields = {
    strategy_media_probe: ["organization_id", "project_id", "media_id"],
    strategy_bind: ["organization_id", "project_id", "spec_id"],
    strategy_preflight: [
      "organization_id",
      "project_id",
      "spec_id",
      "binding_id",
    ],
    strategy_start: [
      "organization_id",
      "project_id",
      "spec_id",
      "binding_id",
      "receipt_id",
      "campaign_id",
    ],
    strategy_status: ["organization_id", "project_id", "generation_job_id"],
    strategy_reconcile: [
      "organization_id",
      "project_id",
      "generation_job_id",
      "dispatch_result_id",
      "incident_id",
    ],
  }[action] || [];
  const hashFields = {
    strategy_bind: ["spec_hash"],
    strategy_preflight: [
      "spec_hash",
      "binding_hash",
      "selection_hash",
      "price_hash",
    ],
    strategy_start: [
      "spec_hash",
      "binding_hash",
      "selection_hash",
      "price_hash",
      "receipt_hash",
    ],
  }[action] || [];
  const hasSpecVersion = [
    "strategy_bind",
    "strategy_preflight",
    "strategy_start",
  ].includes(action);
  const hasConfirmation = ![
    "strategy_catalog",
    "strategy_status",
    "strategy_reconcile",
  ].includes(action);
  const hasSpendConfirmation = [
    "strategy_preflight",
    "strategy_start",
  ].includes(action);
  const strategyReconcileAttach = action === "strategy_reconcile"
    && request?.resolution === "attach_existing_task";
  const strategyReconcileConfirmation = action === "strategy_reconcile"
    ? String(request?.confirmation || "")
    : "";
  const strategyReconcileConfirmationValid = action !== "strategy_reconcile"
    || (strategyReconcileAttach
      ? new Set([
        "RUNWAY_TASK_ID_VERIFIED",
        "FAL_REQUEST_ID_VERIFIED",
        "HEYGEN_VIDEO_ID_VERIFIED",
      ]).has(strategyReconcileConfirmation)
      : request?.resolution === "confirm_no_submission" && new Set([
        "RUNWAY_NO_TASK_VERIFIED",
        "FAL_NO_REQUEST_VERIFIED",
        "HEYGEN_NO_VIDEO_VERIFIED",
      ]).has(strategyReconcileConfirmation));
  const strategyReconcileTaskIdValid = !strategyReconcileAttach
    || (strategyReconcileConfirmation === "FAL_REQUEST_ID_VERIFIED"
      ? GENERATION_STRATEGY_FAL_REQUEST_ID_PATTERN
        .test(String(request?.provider_task_id || ""))
      : strategyReconcileConfirmation === "HEYGEN_VIDEO_ID_VERIFIED"
      ? GENERATION_STRATEGY_HEYGEN_VIDEO_ID_PATTERN
        .test(String(request?.provider_task_id || ""))
      : strategyReconcileConfirmation === "RUNWAY_TASK_ID_VERIFIED"
      && GENERATION_STRATEGY_RUNWAY_TASK_ID_PATTERN
        .test(String(request?.provider_task_id || "")));
  if (
    !keys
    || !hasExactObjectKeys(request, keys)
    || request.action !== action
    || !generationStrategyExactUuid(organization)
    || request.organization_id !== organization
    || uuidFields.some((field) => !generationStrategyExactUuid(request[field]))
    || hashFields.some((field) => (
      typeof request[field] !== "string"
      || !GENERATION_STRATEGY_SHA256_PATTERN.test(request[field])
    ))
    || (hasSpecVersion && (
      !Number.isSafeInteger(request.spec_version)
      || request.spec_version < 1
      || request.spec_version > 100_000
    ))
    || (hasConfirmation && request.confirmation !== true)
    || (GENERATION_STRATEGY_IDEMPOTENT_ACTIONS.has(action) && (
      typeof request.idempotency_key !== "string"
      || !GENERATION_STRATEGY_IDEMPOTENCY_PATTERN.test(request.idempotency_key)
    ))
    || (action === "strategy_bind" && (
      !request.generation_strategy
      || typeof request.generation_strategy !== "object"
      || Array.isArray(request.generation_strategy)
    ))
    // Движок каскада: ровно два поля и обе строки непустые. Существует ли
    // такой маршрут и сколько он стоит, решает сервер по реестру — браузер
    // проверяет только форму, чтобы неполный выбор не ушёл в запрос.
    || (bindWithEngine && (
      !request.engine
      || typeof request.engine !== "object"
      || Array.isArray(request.engine)
      || !hasExactObjectKeys(request.engine, ["provider", "model_key"])
      || !generationStrategyExactBoundedText(request.engine.provider, 2, 40)
      || !generationStrategyExactBoundedText(request.engine.model_key, 2, 120)
    ))
    // Ведущий «Дуэта»: браузер проверяет только форму. Существует ли такой
    // ведущий, активен ли он и подтверждено ли согласие на его образ — решает
    // сервер, читая реестр перед каждой отправкой. Второй список ведущих здесь
    // разошёлся бы с реестром на первой же архивации.
    || (bindWithPresenter
      && !generationStrategyExactUuid(request.duet_presenter_id))
    || (hasSpendConfirmation && (
      typeof request.spend_confirmation !== "string"
      // Провайдер стоит в самой строке подтверждения, и нижняя граница
      // длительности у маршрутов разная: рецепт Runway начинается с четырёх
      // секунд, у fal ролик может быть короче. Эта проверка повторяет ту, что
      // стоит в edge; расходиться им нельзя — иначе запрос молча не уйдёт.
      //
      // 23.08.2026 они и разошлись: edge узнал HEYGEN и шестьдесят секунд,
      // а браузер остался на двух провайдерах и пятнадцати. «Дуэт» с его
      // HEYGEN_PRODUCT_UGC_24S_… не проходил бы здесь — то есть запрос не
      // уходил бы вовсе, без единого объяснения оператору.
      || !/^(?:RUNWAY|FAL|HEYGEN)_(?:PRODUCT_UGC|PRODUCT_SWAP|PRODUCT_AD)_(?:[1-9]|[1-5][0-9]|60)S_(?:720P|1080P)_(?:AUDIO|SILENT)_USD_[0-9]{1,4}[.][0-9]{2}$/u
        .test(request.spend_confirmation)
    ))
    || (action === "strategy_reconcile" && (
      !["attach_existing_task", "confirm_no_submission"]
        .includes(request.resolution)
      || !strategyReconcileConfirmationValid
      || !generationStrategyExactBoundedText(request.evidence_reference, 8, 500)
      || !generationStrategyExactBoundedText(request.reason, 20, 1_000)
      || !strategyReconcileTaskIdValid
    ))
  ) {
    throw new CreatorApiError(
      "Параметры запуска стратегии изменились. Обновите форму и повторите бесплатную проверку.",
      { code: "generation_strategy_request_invalid" },
    );
  }
  return request;
}

function assertGenerationStrategyPublicResponse(action, data) {
  const contract = GENERATION_STRATEGY_RESPONSE_CONTRACTS[action];
  if (
    !contract
    || !hasExactObjectKeys(data, contract.keys)
    || data.ok !== true
    || (contract.version !== undefined && data.version !== contract.version)
  ) {
    throw new CreatorApiError(
      "Сервис генерации вернул некорректный ответ стратегии.",
      { code: "generation_strategy_response_invalid" },
    );
  }
  return data;
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function researchAnalysisHasForbiddenKeys(value) {
  const pending = [value];
  let visitedNodes = 0;
  while (pending.length) {
    const current = pending.pop();
    if (!current || typeof current !== "object") continue;
    visitedNodes += 1;
    if (visitedNodes > 10_000) return true;
    if (Array.isArray(current)) {
      pending.push(...current);
      continue;
    }
    for (const [key, child] of Object.entries(current)) {
      if (RESEARCH_ANALYSIS_FORBIDDEN_KEYS.has(key.toLowerCase())) return true;
      if (child && typeof child === "object") pending.push(child);
    }
  }
  return false;
}

function researchSourceAnalysisIsValid(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const exactKeys = [
    "schema_version",
    "classification",
    "relevance_score",
    "confidence",
    "summary",
    "structural_signal_keys",
    "limitations",
  ];
  if (
    Object.keys(value).length !== exactKeys.length
    || exactKeys.some((key) => !Object.prototype.hasOwnProperty.call(value, key))
    || value.schema_version !== RESEARCH_SOURCE_ANALYSIS_SCHEMA_VERSION
    || !RESEARCH_SOURCE_ANALYSIS_CLASSIFICATIONS.has(value.classification)
    || !Number.isInteger(value.relevance_score)
    || value.relevance_score < 0
    || value.relevance_score > 100
    || !RESEARCH_SOURCE_ANALYSIS_CONFIDENCE.has(value.confidence)
    || typeof value.summary !== "string"
    || value.summary.trim().length < 20
    || value.summary.trim().length > 2_000
    || !Array.isArray(value.structural_signal_keys)
    || value.structural_signal_keys.length > 20
    || !Array.isArray(value.limitations)
    || value.limitations.length > 20
    || researchAnalysisHasForbiddenKeys(value)
  ) return false;
  const structuralSignals = value.structural_signal_keys.map((item) =>
    typeof item === "string" ? item.trim() : ""
  );
  if (
    structuralSignals.some((item) =>
      item.length < 3
      || item.length > 100
      || !RESEARCH_SOURCE_STRUCTURAL_SIGNAL_PATTERN.test(item)
    )
    || new Set(structuralSignals).size !== structuralSignals.length
    || value.limitations.some((item) =>
      typeof item !== "string"
      || item.trim().length < 3
      || item.trim().length > 500
    )
  ) return false;
  return true;
}

function researchYoutubeObservationAnalysisIsValid(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const exactKeys = [
    "schema_version",
    "classification",
    "review_priority",
    "confidence",
    "recommendation",
    "signals",
    "summary",
    "limitations",
  ];
  const signals = value.signals;
  const signalKeys = [
    "search_position",
    "query_token_overlap_count",
    "query_token_count",
    "published_age_days",
    "same_channel_observation_count",
    "counters_present",
  ];
  if (
    Object.keys(value).length !== exactKeys.length
    || exactKeys.some((key) => !Object.prototype.hasOwnProperty.call(value, key))
    || value.schema_version
      !== RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_SCHEMA_VERSION
    || !RESEARCH_YOUTUBE_OBSERVATION_ANALYSIS_CLASSIFICATIONS.has(
      value.classification,
    )
    || !Number.isInteger(value.review_priority)
    || value.review_priority < 0
    || value.review_priority > 100
    || !["low", "medium"].includes(value.confidence)
    || !["review_candidate", "needs_more_evidence"].includes(
      value.recommendation,
    )
    || !signals
    || typeof signals !== "object"
    || Array.isArray(signals)
    || Object.keys(signals).length !== signalKeys.length
    || signalKeys.some((key) =>
      !Object.prototype.hasOwnProperty.call(signals, key)
    )
    || !Number.isInteger(signals.search_position)
    || signals.search_position < 1
    || signals.search_position > 25
    || !Number.isInteger(signals.query_token_overlap_count)
    || signals.query_token_overlap_count < 0
    || signals.query_token_overlap_count > 999
    || !Number.isInteger(signals.query_token_count)
    || signals.query_token_count < signals.query_token_overlap_count
    || signals.query_token_count > 999
    || !Number.isInteger(signals.published_age_days)
    || signals.published_age_days < 0
    || signals.published_age_days > 9_999_999
    || !Number.isInteger(signals.same_channel_observation_count)
    || signals.same_channel_observation_count < 1
    || signals.same_channel_observation_count > 9_999_999
    || typeof signals.counters_present !== "boolean"
    || typeof value.summary !== "string"
    || value.summary.trim().length < 20
    || value.summary.trim().length > 1_200
    || !Array.isArray(value.limitations)
    || value.limitations.length < 1
    || value.limitations.length > 8
    || value.limitations.some((item) =>
      typeof item !== "string"
      || item.trim().length < 3
      || item.trim().length > 500
    )
    || researchAnalysisHasForbiddenKeys(value)
  ) return false;
  return true;
}

function normalizeStringArray(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(
    value
      .map((item) => String(item || "").trim().toLowerCase())
      .filter(Boolean),
  )];
}

function normalizeGenerationSpecReference(value = {}) {
  if (!hasExactObjectKeys(value, ["spec_id", "spec_version", "spec_hash"])) {
    throw new CreatorApiError("Для проверки нужны точные id, версия и hash ТЗ.", {
      code: "generation_spec_reference_invalid",
    });
  }
  const specId = requireGenerationSpecUuid(
    value.spec_id,
    "generation_spec_id_invalid",
  );
  const specVersion = Number(value.spec_version);
  const specHash = String(value.spec_hash || "").trim().toLowerCase();
  if (
    !Number.isInteger(specVersion)
    || specVersion < 1
    || specVersion > 100_000
    || !/^[0-9a-f]{64}$/u.test(specHash)
  ) {
    throw new CreatorApiError("Серверная версия ТЗ устарела или повреждена.", {
      code: "generation_spec_reference_invalid",
    });
  }
  return {
    spec_id: specId,
    spec_version: specVersion,
    spec_hash: specHash,
  };
}

function normalizeGenerationSpecScopeInput(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CreatorApiError("Заполните точный товар и режим управляемого ТЗ.", {
      code: "generation_spec_scope_invalid",
    });
  }
  const allowedKeys = [
    "primary_media_id",
    "media_ids",
    "platform",
    "model",
    "duration_seconds",
    "product_category",
    "format",
    "audio",
  ];
  if (!hasExactObjectKeys(value, allowedKeys)) {
    throw new CreatorApiError("Параметры управляемого ТЗ заполнены не полностью.", {
      code: "generation_spec_scope_invalid",
    });
  }
  const primaryMediaId = requireGenerationSpecUuid(
    value.primary_media_id,
    "generation_spec_scope_invalid",
  );
  const mediaIds = Array.isArray(value.media_ids)
    ? value.media_ids.map((item) => requireGenerationSpecUuid(
        item,
        "generation_spec_scope_invalid",
      ))
    : [];
  const platform = String(value.platform || "").trim().toLowerCase();
  const model = String(value.model || "").trim().toLowerCase();
  const productCategory = String(value.product_category || "").trim().toLowerCase();
  const format = String(value.format || "").trim();
  const audio = value.audio;
  const durationSeconds = Number(value.duration_seconds);
  const validDuration = model === "seedream5_lite"
    ? durationSeconds === 0
    : model === "gen4_turbo"
      ? [2, 5, 8, 10].includes(durationSeconds)
      : [4, 8, 12, 15].includes(durationSeconds);
  if (
    mediaIds.length < 1
    || mediaIds.length > 5
    || new Set(mediaIds).size !== mediaIds.length
    || mediaIds[0] !== primaryMediaId
    || !["instagram", "tiktok", "youtube", "vk", "telegram", "wildberries"]
      .includes(platform)
    || !["gen4_turbo", "seedance2_fast", "seedream5_lite"].includes(model)
    || ![
      "cosmetics", "baa", "sports_food", "food", "household", "apparel",
      "electronics", "other",
    ].includes(productCategory)
    || !["9:16", "1:1", "16:9"].includes(format)
    || typeof audio !== "boolean"
    || !validDuration
  ) {
    throw new CreatorApiError("Параметры управляемого ТЗ не совпадают с выбранным режимом.", {
      code: "generation_spec_scope_invalid",
    });
  }
  return {
    primary_media_id: primaryMediaId,
    media_ids: mediaIds,
    platform,
    model,
    duration_seconds: durationSeconds,
    product_category: productCategory,
    format,
    audio,
  };
}

function normalizeGenerationSpecResearchProvenance(value) {
  if (value === null || value === undefined) return null;
  if (
    !hasExactObjectKeys(value, [
      "research_id", "creative_brief_draft_id", "scenario_position",
    ])
    || ![1, 2, 3].includes(Number(value.scenario_position))
  ) {
    throw new CreatorApiError("Связь ТЗ с утверждённым исследованием устарела.", {
      code: "generation_spec_research_provenance_invalid",
    });
  }
  return {
    research_id: requireGenerationSpecUuid(
      value.research_id,
      "generation_spec_research_provenance_invalid",
    ),
    creative_brief_draft_id: requireGenerationSpecUuid(
      value.creative_brief_draft_id,
      "generation_spec_research_provenance_invalid",
    ),
    scenario_position: Number(value.scenario_position),
  };
}

function normalizeGenerationSpecPerformanceProvenance(value) {
  if (value === null || value === undefined) return null;
  if (!hasExactObjectKeys(value, ["policy_hash", "policy_version"])) {
    throw new CreatorApiError("Связь ТЗ с обученной политикой устарела.", {
      code: "generation_spec_performance_provenance_invalid",
    });
  }
  const policyHash = String(value.policy_hash || "").trim().toLowerCase();
  const policyVersion = String(value.policy_version || "").trim();
  if (
    !/^[0-9a-f]{64}$/u.test(policyHash)
    || policyVersion.length < 3
    || policyVersion.length > 80
  ) {
    throw new CreatorApiError("Связь ТЗ с обученной политикой устарела.", {
      code: "generation_spec_performance_provenance_invalid",
    });
  }
  return { policy_hash: policyHash, policy_version: policyVersion };
}

function normalizeGenerationSpecRepairProvenance(value) {
  if (value === null || value === undefined) return null;
  if (!hasExactObjectKeys(value, [
    "source_review_id", "source_generation_job_id", "policy_hash",
  ])) {
    throw new CreatorApiError("Связь исправления с QA устарела.", {
      code: "generation_spec_repair_provenance_invalid",
    });
  }
  const policyHash = String(value.policy_hash || "").trim().toLowerCase();
  if (!/^[0-9a-f]{64}$/u.test(policyHash)) {
    throw new CreatorApiError("Связь исправления с QA устарела.", {
      code: "generation_spec_repair_provenance_invalid",
    });
  }
  return {
    source_review_id: requireGenerationSpecUuid(
      value.source_review_id,
      "generation_spec_repair_provenance_invalid",
    ),
    source_generation_job_id: requireGenerationSpecUuid(
      value.source_generation_job_id,
      "generation_spec_repair_provenance_invalid",
    ),
    policy_hash: policyHash,
  };
}

function normalizeGenerationSpecLearningContext(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CreatorApiError("Контекст обучения для ТЗ отсутствует.", {
      code: "generation_spec_learning_context_invalid",
    });
  }
  const source = String(value.source || "").trim().toLowerCase();
  const required = [
    "creative_angle", "hook_patterns", "source", "compiler_version",
    "product_category",
  ];
  const optional = source === "performance_learning"
    ? ["applied_policy_hash"]
    : source === "approved_research"
      ? ["creative_brief_draft_id", "scenario_position"]
      : [];
  if (!hasExactObjectKeys(value, [...required, ...optional])) {
    throw new CreatorApiError("Контекст обучения для ТЗ имеет неизвестные поля.", {
      code: "generation_spec_learning_context_invalid",
    });
  }
  const creativeAngle = String(value.creative_angle || "").trim().toLowerCase();
  const hooks = Array.isArray(value.hook_patterns)
    ? value.hook_patterns.map((item) => String(item || "").trim().toLowerCase())
    : [];
  const compilerVersion = String(value.compiler_version || "").trim();
  const productCategory = String(value.product_category || "").trim().toLowerCase();
  const allowedAngles = new Set([
    "product_focus", "trust_builder", "demonstration", "comparison",
    "objection_handling", "curiosity_gap",
  ]);
  const allowedHooks = new Set([
    "question_led", "why_explanation", "before_buying", "comparison",
    "demonstration", "first_person", "numbered", "concise",
  ]);
  if (
    !["baseline", "approved_research", "performance_learning"].includes(source)
    || !allowedAngles.has(creativeAngle)
    || hooks.length > 8
    || new Set(hooks).size !== hooks.length
    || hooks.some((item) => !allowedHooks.has(item))
    || !/^[a-z0-9][a-z0-9._-]{2,63}$/u.test(compilerVersion)
    || ![
      "cosmetics", "baa", "sports_food", "food", "household", "apparel",
      "electronics", "other",
    ].includes(productCategory)
    || (source === "baseline" && (
      creativeAngle !== "product_focus" || hooks.length !== 0
    ))
  ) {
    throw new CreatorApiError("Контекст обучения для ТЗ устарел.", {
      code: "generation_spec_learning_context_invalid",
    });
  }
  const normalized = {
    creative_angle: creativeAngle,
    hook_patterns: hooks,
    source,
    compiler_version: compilerVersion,
    product_category: productCategory,
  };
  if (source === "performance_learning") {
    const hash = String(value.applied_policy_hash || "").trim().toLowerCase();
    if (!/^[0-9a-f]{64}$/u.test(hash)) {
      throw new CreatorApiError("Hash обученной политики для ТЗ устарел.", {
        code: "generation_spec_learning_context_invalid",
      });
    }
    normalized.applied_policy_hash = hash;
  } else if (source === "approved_research") {
    const position = Number(value.scenario_position);
    if (![1, 2, 3].includes(position)) {
      throw new CreatorApiError("Позиция исследовательского сценария устарела.", {
        code: "generation_spec_learning_context_invalid",
      });
    }
    normalized.creative_brief_draft_id = requireGenerationSpecUuid(
      value.creative_brief_draft_id,
      "generation_spec_learning_context_invalid",
    );
    normalized.scenario_position = position;
  }
  return normalized;
}

function normalizeGenerationSpecRepairContext(value) {
  if (value === null || value === undefined) return null;
  if (!hasExactObjectKeys(value, [
    "source_review_id", "source_generation_job_id", "guard_codes",
    "policy_hash", "compiler_version",
  ])) {
    throw new CreatorApiError("Контекст исправления для ТЗ устарел.", {
      code: "generation_spec_repair_context_invalid",
    });
  }
  const guardCodes = Array.isArray(value.guard_codes)
    ? value.guard_codes.map((item) => String(item || "").trim().toLowerCase())
    : [];
  const allowed = new Set([
    "product_fidelity", "technical_stability", "audio_quality",
    "speech_fidelity", "hook_clarity", "visual_quality", "trust",
    "platform_fit",
  ]);
  const policyHash = String(value.policy_hash || "").trim().toLowerCase();
  if (
    value.compiler_version !== "review-repair-v1"
    || guardCodes.length < 1
    || guardCodes.length > 3
    || new Set(guardCodes).size !== guardCodes.length
    || guardCodes.some((code) => !allowed.has(code))
    || !/^[0-9a-f]{64}$/u.test(policyHash)
  ) {
    throw new CreatorApiError("Контекст исправления для ТЗ устарел.", {
      code: "generation_spec_repair_context_invalid",
    });
  }
  return {
    source_review_id: requireGenerationSpecUuid(
      value.source_review_id,
      "generation_spec_repair_context_invalid",
    ),
    source_generation_job_id: requireGenerationSpecUuid(
      value.source_generation_job_id,
      "generation_spec_repair_context_invalid",
    ),
    guard_codes: guardCodes,
    policy_hash: policyHash,
    compiler_version: "review-repair-v1",
  };
}

function normalizeGenerationSpecPatch(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CreatorApiError("Исправленная версия ТЗ заполнена не полностью.", {
      code: "generation_spec_patch_invalid",
    });
  }
  const allowed = [
    "exact_scope",
    "editable_intent",
    "proposed_prompt",
    "learning_context",
    "repair_context",
    "research_provenance",
    "performance_policy_provenance",
    "repair_provenance",
    "outcome_selection_id",
  ];
  if (
    Object.keys(value).some((key) => !allowed.includes(key))
    || !Object.hasOwn(value, "exact_scope")
    || !Object.hasOwn(value, "editable_intent")
    || !Object.hasOwn(value, "proposed_prompt")
    || !Object.hasOwn(value, "learning_context")
    || !Object.hasOwn(value, "repair_context")
  ) {
    throw new CreatorApiError("Исправленная версия ТЗ содержит неизвестные поля.", {
      code: "generation_spec_patch_invalid",
    });
  }
  const editableIntent = String(value.editable_intent || "").trim();
  const proposedPrompt = String(value.proposed_prompt || "").trim();
  if (
    editableIntent.length < 1
    || editableIntent.length > 1_200
    || proposedPrompt.length < 1
    || proposedPrompt.length > 1_200
  ) {
    throw new CreatorApiError("Исправленный замысел или prompt имеет неверную длину.", {
      code: "generation_spec_patch_invalid",
    });
  }
  return {
    exact_scope: normalizeGenerationSpecScopeInput(value.exact_scope),
    editable_intent: editableIntent,
    proposed_prompt: proposedPrompt,
    learning_context: normalizeGenerationSpecLearningContext(
      value.learning_context,
    ),
    repair_context: normalizeGenerationSpecRepairContext(
      value.repair_context,
    ),
    research_provenance: normalizeGenerationSpecResearchProvenance(
      value.research_provenance,
    ),
    performance_policy_provenance:
      normalizeGenerationSpecPerformanceProvenance(
        value.performance_policy_provenance,
      ),
    repair_provenance: normalizeGenerationSpecRepairProvenance(
      value.repair_provenance,
    ),
    ...(value.outcome_selection_id
      ? { outcome_selection_id: requireGenerationSpecUuid(
          value.outcome_selection_id,
          "generation_spec_outcome_selection_invalid",
        ) }
      : {}),
  };
}

function requireGenerationSpecUuid(value, code) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!isUuid(normalized)) {
    throw new CreatorApiError("Ссылка управляемого ТЗ имеет неверный формат.", {
      code,
    });
  }
  return normalized;
}

function normalizeSpendLimit(value, label) {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1 || number > 100_000_000) {
    throw new CreatorApiError(`Укажите ${label} лимит от $0.01 до $1 000 000.`, {
      code: "generation_budget_limits_invalid",
    });
  }
  return number;
}

function validateCampaignPolicyInput({
  dailyLimitMinor,
  monthlyLimitMinor,
  perRequestLimitMinor,
  reason,
}) {
  if (perRequestLimitMinor > dailyLimitMinor || dailyLimitMinor > monthlyLimitMinor) {
    throw new CreatorApiError("Лимит одного запуска должен быть не больше дневного, а дневной — месячного.", {
      code: "generation_campaign_policy_values_invalid",
    });
  }
  if (reason.length < 8 || reason.length > 500 || /[\u0000-\u001f\u007f]/u.test(reason)) {
    throw new CreatorApiError("Укажите причину изменения бюджета кампании длиной от 8 до 500 символов.", {
      code: "generation_budget_reason_invalid",
    });
  }
}

function normalizeAccessEmail(value) {
  const email = String(value || "").trim().toLowerCase();
  if (
    !email
    || email.length > 320
    || !/^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,63}$/u.test(email)
  ) return "";
  return email;
}

export function mergeGenerationMediaIdentity(response, identityResponse) {
  const wrapped = response?.data && typeof response.data === "object"
    && !Array.isArray(response.data);
  const source = wrapped ? response.data : response;
  if (!source || typeof source !== "object" || Array.isArray(source)) {
    return response;
  }
  const identitySource = identityResponse?.data
    && typeof identityResponse.data === "object"
    && !Array.isArray(identityResponse.data)
    ? identityResponse.data
    : identityResponse;
  const identities = Array.isArray(identitySource?.items)
    ? identitySource.items
    : [];
  const identityById = new Map();
  for (const item of identities) {
    const id = String(item?.public_id || item?.id || "").trim();
    const sku = String(item?.sku || "").trim();
    const productName = String(item?.product_name || "").trim();
    if (
      !isUuid(id)
      || item?.identity_verified !== true
      || !sku
      || !productName
    ) continue;
    identityById.set(id, {
      product_id: String(item?.product_id || "").trim(),
      sku,
      product_name: productName,
      rights_confirmed: item?.rights_confirmed === true,
      identity_verified: true,
    });
  }
  const media = Array.isArray(source.media) ? source.media : [];
  const mergedSource = {
    ...source,
    media: media.map((item) => {
      const id = String(item?.public_id || item?.id || "").trim();
      const identity = identityById.get(id);
      return identity
        ? { ...item, ...identity }
        : {
            ...item,
            identity_verified: false,
            rights_confirmed: false,
          };
    }),
  };
  return wrapped
    ? { ...response, data: mergedSource }
    : mergedSource;
}

function isUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu.test(
    String(value || ""),
  );
}

function optionalProjectId(value) {
  const projectId = String(value || "").trim().toLowerCase();
  if (!projectId) return "";
  if (!isUuid(projectId)) {
    throw new CreatorApiError("Не удалось определить активный проект. Вернитесь на рабочий стол и откройте проект снова.", {
      code: "project_id_invalid",
    });
  }
  return projectId;
}

function requiredProjectId(value) {
  const projectId = optionalProjectId(value);
  if (!projectId) {
    throw new CreatorApiError("Сначала выберите проект. Исследование, ТЗ и задачи не могут быть общей очередью компании.", {
      code: "project_id_required",
    });
  }
  return projectId;
}

export function validContentReviewTechnicalMetrics(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const sourceType = String(value.source_type || "").trim().toLowerCase();
  const finiteInRange = (field, minimum, maximum) =>
    typeof value[field] === "number"
    && Number.isFinite(value[field])
    && value[field] >= minimum
    && value[field] <= maximum;
  if (sourceType === "image") {
    return Number.isInteger(Number(value.frame_count))
      && Number(value.frame_count) === 1;
  }
  const temporalScanValid = value.temporal_scan_status === "completed"
    && value.temporal_scan_strategy === "uniform_full_duration_v1"
    && Number.isInteger(value.temporal_scan_frame_count)
    && value.temporal_scan_frame_count >= 12
    && value.temporal_scan_frame_count <= 24
    && finiteInRange("duration_seconds", 0.001, 3_600)
    && finiteInRange("temporal_scan_first_second", 0, 3_600)
    && finiteInRange("temporal_scan_last_second", 0, 3_600)
    && value.temporal_scan_last_second > value.temporal_scan_first_second
    && value.temporal_scan_last_second <= value.duration_seconds
    && finiteInRange("temporal_scan_coverage_ratio", 0.9, 1)
    && Math.abs(
      (
        value.temporal_scan_last_second - value.temporal_scan_first_second
      ) / value.duration_seconds - value.temporal_scan_coverage_ratio,
    ) <= 0.02
    && finiteInRange("temporal_black_frame_ratio", 0, 1)
    && finiteInRange("temporal_frozen_transition_ratio", 0, 1)
    && finiteInRange("temporal_mean_frame_difference", 0, 1);
  const sampledAt = Array.isArray(value.sampled_at_seconds)
    ? value.sampled_at_seconds
    : [];
  const sampledAtValid = sampledAt.length === 5
    && sampledAt.every((item, index) =>
      typeof item === "number"
      && Number.isFinite(item)
      && item >= 0
      && item <= value.duration_seconds
      && (index === 0 || item > sampledAt[index - 1])
    );
  const timelineAtlasValid = value.timeline_atlas_status === "completed"
    && value.timeline_atlas_version === "dense_full_duration_v1"
    && value.timeline_atlas_frame_ordinal === 5
    && Number.isInteger(value.timeline_atlas_frame_count)
    && value.timeline_atlas_frame_count >= 12
    && value.timeline_atlas_frame_count <= 24
    && value.timeline_atlas_frame_count === value.temporal_scan_frame_count
    && finiteInRange("timeline_atlas_first_second", 0, 3_600)
    && finiteInRange("timeline_atlas_last_second", 0, 3_600)
    && value.timeline_atlas_last_second > value.timeline_atlas_first_second
    && value.timeline_atlas_last_second <= value.duration_seconds
    && Math.abs(
      value.timeline_atlas_first_second - value.temporal_scan_first_second,
    ) <= 0.002
    && Math.abs(
      value.timeline_atlas_last_second - value.temporal_scan_last_second,
    ) <= 0.002
    && finiteInRange("timeline_atlas_coverage_ratio", 0.9, 1)
    && Math.abs(
      value.timeline_atlas_coverage_ratio - value.temporal_scan_coverage_ratio,
    ) <= 0.002
    && finiteInRange("timeline_atlas_max_gap_seconds", 0.001, 3_600)
    && value.timeline_atlas_max_gap_seconds <= value.duration_seconds
    && finiteInRange("timeline_atlas_sample_rate_fps", 0.003, 24_000)
    && Math.abs(
      value.timeline_atlas_sample_rate_fps -
        value.timeline_atlas_frame_count / value.duration_seconds,
    ) <= 0.02
    && Number.isInteger(value.timeline_atlas_columns)
    && value.timeline_atlas_columns >= 2
    && value.timeline_atlas_columns <= 8
    && Number.isInteger(value.timeline_atlas_rows)
    && value.timeline_atlas_rows >= 2
    && value.timeline_atlas_rows <= 8
    && value.timeline_atlas_columns * value.timeline_atlas_rows >=
      value.timeline_atlas_frame_count
    && value.timeline_atlas_columns * (value.timeline_atlas_rows - 1) <
      value.timeline_atlas_frame_count
    && value.timeline_atlas_order === "row_major_chronological"
    && typeof value.timeline_atlas_dense_short_video === "boolean"
    && value.timeline_atlas_dense_short_video === (
      value.duration_seconds <= 10
      && value.timeline_atlas_coverage_ratio >= 0.9
      && value.timeline_atlas_max_gap_seconds <= 0.5
    )
    && sampledAtValid
    && Math.abs(
      sampledAt.at(-1) - value.timeline_atlas_last_second,
    ) <= 0.002;
  const exactContinuityFields = (expected) => {
    const actual = Object.keys(value).filter((key) => (
      key.startsWith("continuity_")
    ));
    return actual.length === expected.length
      && expected.every((key) => (
        Object.prototype.hasOwnProperty.call(value, key)
      ));
  };
  const completedContinuityFields = [
    "continuity_scan_status",
    "continuity_scan_strategy",
    "continuity_scan_first_second",
    "continuity_scan_last_second",
    "continuity_scan_coverage_ratio",
    "continuity_scan_max_gap_seconds",
    "continuity_black_frame_ratio",
    "continuity_longest_black_run_seconds",
    "continuity_duplicate_transition_ratio",
    "continuity_longest_duplicate_run_seconds",
    "continuity_mean_frame_difference",
    "continuity_raw_frames_persisted",
  ];
  const continuityCompletedShared = value.continuity_scan_status === "completed"
    && finiteInRange("continuity_scan_first_second", 0, 15)
    && finiteInRange("continuity_scan_last_second", 0, 15)
    && value.continuity_scan_last_second > value.continuity_scan_first_second
    && value.continuity_scan_last_second <= value.duration_seconds
    && finiteInRange("continuity_scan_coverage_ratio", 0.8, 1)
    && Math.abs(
      (
        value.continuity_scan_last_second -
        value.continuity_scan_first_second
      ) / value.duration_seconds - value.continuity_scan_coverage_ratio,
    ) <= 0.02
    && finiteInRange("continuity_scan_max_gap_seconds", 0, 0.5)
    && finiteInRange("continuity_black_frame_ratio", 0, 1)
    && finiteInRange(
      "continuity_longest_black_run_seconds",
      0,
      value.duration_seconds,
    )
    && finiteInRange("continuity_duplicate_transition_ratio", 0, 1)
    && finiteInRange(
      "continuity_longest_duplicate_run_seconds",
      0,
      value.duration_seconds,
    )
    && finiteInRange("continuity_mean_frame_difference", 0, 1)
    && value.continuity_raw_frames_persisted === false;
  const continuityPresentedFrameV1 = continuityCompletedShared
    && value.continuity_scan_strategy === "browser_presented_frames_v1"
    && exactContinuityFields([
      ...completedContinuityFields,
      "continuity_scan_callback_count",
      "continuity_scan_presented_frame_count",
      "continuity_scan_missed_frame_count",
    ])
    && Number.isInteger(value.continuity_scan_callback_count)
    && value.continuity_scan_callback_count >= 2
    && value.continuity_scan_callback_count <= 3_600
    && Number.isInteger(value.continuity_scan_presented_frame_count)
    && value.continuity_scan_presented_frame_count ===
      value.continuity_scan_callback_count
    && value.continuity_scan_presented_frame_count <= 10_000
    && Number.isInteger(value.continuity_scan_missed_frame_count)
    && value.continuity_scan_missed_frame_count === 0;
  const denseSeekExpectedCount = Math.min(
    151,
    Math.max(16, Math.ceil(value.duration_seconds * 10) + 1),
  );
  const denseSeekExpectedMargin = Math.min(
    0.01,
    value.duration_seconds * 0.01,
  );
  const continuityDenseSeekV2 = continuityCompletedShared
    && value.continuity_scan_strategy === "browser_dense_seek_v2"
    && exactContinuityFields([
      ...completedContinuityFields,
      "continuity_scan_sample_count",
      "continuity_scan_target_fps",
      "continuity_scan_target_max_drift_seconds",
      "continuity_scan_fallback_reason",
    ])
    && Number.isInteger(value.continuity_scan_sample_count)
    && value.continuity_scan_sample_count === denseSeekExpectedCount
    && value.continuity_scan_target_fps === 10
    && finiteInRange(
      "continuity_scan_target_max_drift_seconds",
      0,
      0.02,
    )
    && [
      "rvfc_unavailable",
      "rvfc_coverage_unreliable",
      "rvfc_max_gap_unreliable",
      "rvfc_missed_frames",
    ].includes(value.continuity_scan_fallback_reason)
    && value.continuity_scan_coverage_ratio >= 0.98
    && value.continuity_scan_max_gap_seconds <= 0.125
    && Math.abs(
      value.continuity_scan_first_second - denseSeekExpectedMargin,
    ) <= 0.0201
    && Math.abs(
      value.duration_seconds - value.continuity_scan_last_second -
        denseSeekExpectedMargin,
    ) <= 0.0201
    && Math.abs(
      value.continuity_scan_max_gap_seconds -
        (
          value.continuity_scan_last_second -
          value.continuity_scan_first_second
        ) / (value.continuity_scan_sample_count - 1),
    ) <= 0.04;
  const continuityScanValid = value.duration_seconds <= 15
    ? continuityPresentedFrameV1 || continuityDenseSeekV2
    : value.continuity_scan_status === "not_applicable"
      && value.continuity_scan_strategy === "browser_presented_frames_v1"
      && value.continuity_scan_not_applicable_reason ===
        "duration_above_short_video_limit"
      && value.continuity_scan_duration_limit_seconds === 15
      && exactContinuityFields([
        "continuity_scan_status",
        "continuity_scan_strategy",
        "continuity_scan_not_applicable_reason",
        "continuity_scan_duration_limit_seconds",
      ]);
  if (
    sourceType !== "video"
    || !Number.isInteger(Number(value.frame_count))
    || Number(value.frame_count) !== 5
    || typeof value.audio_analyzed !== "boolean"
    || !["completed", "unavailable"].includes(
      String(value.audio_analysis_status || ""),
    )
    || !(
      value.audio_expected === null
      || typeof value.audio_expected === "boolean"
    )
    || value.speech_transcription_notice_version !== "openai_mp4_v1"
    || !temporalScanValid
    || !timelineAtlasValid
    || !continuityScanValid
  ) return false;
  if (value.audio_analysis_status === "unavailable") {
    return value.audio_analyzed === false;
  }
  return value.audio_analyzed === true
    && Number.isInteger(value.audio_channel_count)
    && value.audio_channel_count >= 1
    && value.audio_channel_count <= 32
    && Number.isInteger(value.audio_sample_rate_hz)
    && value.audio_sample_rate_hz >= 8_000
    && value.audio_sample_rate_hz <= 384_000
    && finiteInRange("audio_duration_seconds", 0.001, 3_600)
    && (
      value.audio_video_duration_delta_seconds === null
      || finiteInRange("audio_video_duration_delta_seconds", 0, 3_600)
    )
    && finiteInRange("audio_peak_dbfs", -160, 0)
    && finiteInRange("audio_rms_dbfs", -160, 0)
    && finiteInRange("audio_silence_ratio", 0, 1)
    && finiteInRange("audio_clipping_ratio", 0, 1);
}

function normalizePublicRecoveryToken(value) {
  const token = String(value || "").trim();
  if (token.length < 16 || token.length > 512 || !/^[a-z0-9._~-]+$/iu.test(token)) return "";
  return token;
}

function normalizePublicRecoveryResponse(data, expectedAction, context = {}) {
  const source = data?.data && typeof data.data === "object" && !Array.isArray(data.data)
    ? data.data
    : data;
  const receipt = source?.receipt && typeof source.receipt === "object" && !Array.isArray(source.receipt)
    ? source.receipt
    : source;
  const action = String(source?.action || receipt?.action || expectedAction).trim().toLowerCase();
  const receiptToken = normalizePublicRecoveryToken(
    receipt?.receipt_token || source?.receipt_token || context.receipt_token,
  );
  const requestId = String(
    receipt?.request_id || source?.request_id || context.request_id || "",
  ).trim();
  const status = String(receipt?.status || source?.status || "accepted").trim().toLowerCase();
  const retryAfterSeconds = Number(
    receipt?.retry_after_seconds ?? source?.retry_after_seconds ?? 0,
  );
  const requestedAt = String(receipt?.requested_at || source?.requested_at || "").trim();
  const cooldownCandidate = String(
    receipt?.cooldown_until || source?.cooldown_until
      || receipt?.retry_not_before || source?.retry_not_before || "",
  ).trim();
  const cooldownDate = cooldownCandidate ? new Date(cooldownCandidate) : null;
  const requestedDate = requestedAt ? new Date(requestedAt) : null;

  if (
    !source
    || typeof source !== "object"
    || Array.isArray(source)
    || source.ok !== true
    || action !== expectedAction
    || !receiptToken
    || (expectedAction === "request" && !isUuid(requestId))
    || !/^[a-z0-9_]{2,64}$/u.test(status)
    || !Number.isInteger(retryAfterSeconds)
    || retryAfterSeconds < 0
    || retryAfterSeconds > 86_400
    || (requestedDate && Number.isNaN(requestedDate.getTime()))
    || (cooldownDate && Number.isNaN(cooldownDate.getTime()))
  ) {
    throw new CreatorApiError("Сервис восстановления вернул неполную квитанцию. Не запускайте новый запрос.", {
      code: "public_recovery_response_invalid",
    });
  }

  return {
    receiptToken,
    requestId,
    status,
    requestedAt: requestedDate?.toISOString() || new Date().toISOString(),
    cooldownUntil: cooldownDate?.toISOString()
      || new Date(Date.now() + retryAfterSeconds * 1000).toISOString(),
    retryAfterSeconds,
  };
}

async function publicRecoveryFunctionError(error) {
  let code = String(error?.code || "public_recovery_request_failed");
  let retryAfterSeconds = 0;
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body && typeof body === "object" && !Array.isArray(body)) {
        const candidate = String(body.code || body.error?.code || "");
        if (/^[a-z0-9_]{3,96}$/u.test(candidate)) code = candidate;
        const retryCandidate = Number(body.retry_after_seconds || body.error?.retry_after_seconds);
        if (Number.isInteger(retryCandidate) && retryCandidate > 0 && retryCandidate <= 86_400) {
          retryAfterSeconds = retryCandidate;
        }
      }
    } catch {
      // Never expose account existence or raw Auth provider responses.
    }
  }
  const retry = retryAfterSeconds
    ? ` Повторная проверка станет доступна примерно через ${retryAfterSeconds} сек.`
    : "";
  const message = ["email_rate_limited", "public_recovery_rate_limited"].includes(code)
    ? `Запрос уже принят сервером.${retry}`
    : "Сервис восстановления временно не ответил. Квитанция сохранена; повторите проверку позже.";
  return new CreatorApiError(message, {
    code,
    details: retryAfterSeconds ? { retry_after_seconds: retryAfterSeconds } : null,
  });
}

async function accessFunctionError(error) {
  let code = String(error?.code || "access_request_failed");
  let retryAfterSeconds = 0;
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body && typeof body === "object" && !Array.isArray(body)) {
        const candidate = String(body.code || body.error?.code || "");
        if (/^[a-z0-9_]{3,96}$/u.test(candidate)) code = candidate;
        const retryCandidate = Number(body.retry_after_seconds || body.error?.retry_after_seconds);
        if (Number.isInteger(retryCandidate) && retryCandidate > 0 && retryCandidate <= 86_400) {
          retryAfterSeconds = retryCandidate;
        }
      }
    } catch {
      // Do not expose raw provider, Auth, or delivery responses to the browser.
    }
  }

  return new CreatorApiError(safeAccessMessage(code, retryAfterSeconds), {
    code,
    details: retryAfterSeconds ? { retry_after_seconds: retryAfterSeconds } : null,
  });
}

function safeAccessMessage(code, retryAfterSeconds = 0) {
  const retry = retryAfterSeconds
    ? ` Повторите проверку примерно через ${retryAfterSeconds} сек.`
    : "";
  const messages = {
    access_action_invalid: "Не удалось определить безопасное действие с доступом.",
    access_email_invalid: "Укажите точный рабочий email участника.",
    access_request_id_invalid: "Не удалось подготовить безопасный номер восстановления.",
    authentication_required: "Сессия завершилась. Войдите снова перед проверкой доступа.",
    auth_session_required: "Сессия завершилась. Войдите снова перед проверкой доступа.",
    authorization_required: "Проверять доступ может только руководитель команды.",
    role_not_allowed: "Проверять доступ может только руководитель команды.",
    email_rate_limited: `Почтовый сервис временно ограничил повтор.${retry}`,
    manual_review_required: "Автоматическое восстановление остановлено. Проверьте адрес и состояние участника вручную.",
    access_status_unavailable: "Состояние доступа временно не удалось проверить. Новое письмо не отправляйте.",
    access_journal_unavailable: "Журнал писем временно недоступен. Новое письмо не отправляйте.",
    access_journal_finalize_failed: "Действие принято, но журнал не подтвердил итог. Обновите сводку перед повтором.",
    auth_runtime_not_configured: "Сервис восстановления требует настройки руководителем системы.",
    recovery_provider_unavailable: "Почтовый сервис восстановления временно недоступен.",
    recovery_provider_failed: "Почтовый сервис не подтвердил восстановление. Проверьте статус перед повтором.",
    recovery_provider_outcome_unknown: "Итог восстановления не подтверждён. Не запускайте повтор до обновления статуса.",
    invite_provider_outcome_unknown: "Итог приглашения не подтверждён. Не запускайте повтор до обновления статуса.",
    access_request_failed: "Сервис доступа временно не ответил. Обновите сводку и повторите позже.",
    access_response_invalid: "Сервис доступа вернул неполный ответ. Новое письмо не отправляйте.",
  };
  return messages[code] || "Не удалось безопасно проверить доступ. Обновите сводку и повторите позже.";
}

async function researchIngestionFunctionError(error) {
  let code = String(error?.code || "research_youtube_ingestion_unavailable");
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body && typeof body === "object" && !Array.isArray(body)) {
        const candidate = String(
          body.code
          || (body.error && typeof body.error === "object" ? body.error.code : body.error)
          || "",
        );
        if (/^[a-z0-9_]{3,96}$/u.test(candidate)) code = candidate;
      }
    } catch {
      // Never expose raw provider or infrastructure responses to the browser.
    }
  }
  const messages = {
    authentication_required: "Сессия завершилась. Войдите снова перед ручной YouTube‑проверкой.",
    auth_session_required: "Сессия завершилась. Войдите снова перед ручной YouTube‑проверкой.",
    authorization_required: "У этой роли нет права запускать внешний YouTube‑запрос.",
    research_youtube_invoke_not_authorized: "Сервер не подтвердил право этого пользователя на сохранённый YouTube‑запуск.",
    research_youtube_global_rollout_gate_required: "Глобальный контур YouTube пока закрыт оператором.",
    research_youtube_rollout_gate_required: "Обновление категории ещё не включено после успешного canary.",
    research_youtube_retention_control_required: "YouTube‑запрос остановлен: сервер не подтвердил свежую очистку API‑данных.",
    research_youtube_transport_gate_closed: "Условия запуска изменились до внешнего вызова. Запрос остановлен без автоматического повтора.",
    research_youtube_ingestion_lease_inactive: "Безопасная аренда запуска истекла. Запрос завершён без автоматического повтора.",
    research_youtube_local_daily_quota_exhausted: "Дневной лимит YouTube‑запросов по тихоокеанскому времени исчерпан.",
    provider_configuration_error: "Ключ YouTube Data API не настроен. Внешний запрос не выполнен.",
    provider_authentication_failed: "YouTube Data API отклонил ключ. Внешний запрос остановлен.",
    provider_quota_exhausted: "Квота YouTube Data API исчерпана. Автоматического повтора не будет.",
    provider_rate_limited: "YouTube временно ограничил запрос. Автоматического повтора не будет.",
    provider_request_rejected: "YouTube отклонил параметры запроса. Проверьте статус запуска.",
    provider_unavailable: "YouTube Data API временно не ответил. Автоматического повтора не будет.",
    provider_response_invalid: "YouTube вернул неполный ответ. Данные не приняты.",
    provider_outcome_unknown: "Результат внешнего вызова не подтверждён. Не повторяйте запрос до обновления статуса.",
    youtube_transport_receipt_failed: "Квитанция внешнего вызова не сохранена. Не повторяйте запрос до проверки статуса.",
    ingestion_rejected: "Сервер остановил YouTube‑запуск до безопасного завершения.",
    ingestion_unavailable: "Запуск сохранён, но транспорт YouTube временно недоступен. Проверьте статус перед новым запросом.",
    research_youtube_ingestion_unavailable: "Запуск сохранён, но транспорт YouTube временно недоступен. Проверьте статус перед новым запросом.",
  };
  return new CreatorApiError(
    messages[code]
      || "YouTube‑запуск не завершён. Обновите статус и не повторяйте внешний запрос автоматически.",
    { code, message: /^[a-z0-9_]{3,96}$/u.test(code) ? code : null },
  );
}

async function creatorFunctionError(error) {
  let details = {
    code: error?.code || "real_generation_request_failed",
    message: error?.message || "Не удалось вызвать сервис платной генерации.",
  };
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body?.error && typeof body.error === "object") details = { ...details, ...body.error };
      else if (body && typeof body === "object") details = { ...details, ...body };
    } catch {
      // Do not surface raw provider or infrastructure responses to the browser.
    }
  }
  return new CreatorApiError(safeGenerationMessage(details), details);
}

async function contentReviewFunctionError(error) {
  let details = {
    code: error?.code || "content_review_request_failed",
    message: error?.message || "Не удалось вызвать сервис проверки контента.",
  };
  const response = error?.context;
  if (response && typeof response.clone === "function") {
    try {
      const body = await response.clone().json();
      if (body?.error && typeof body.error === "object" && !Array.isArray(body.error)) {
        details = { ...details, ...body.error };
      } else if (body && typeof body === "object" && !Array.isArray(body)) {
        details = {
          ...details,
          ...body,
          code: body.code || (typeof body.error === "string" ? body.error : details.code),
        };
      }
    } catch {
      // Never expose raw provider or infrastructure responses to the browser.
    }
  }
  return new CreatorApiError(safeContentReviewMessage(details), details);
}

function safeContentReviewMessage(details) {
  return toFriendlyMessage({
    code: details?.code || "content_review_request_failed",
    message: "Сервис проверки временно недоступен. Запуск сохранён — проверьте его статус позже.",
  });
}

function safeGenerationMessage(details) {
  return toFriendlyMessage({
    code: details?.code || "real_generation_request_failed",
    message: "Не удалось выполнить платную генерацию. Повторите попытку позже.",
  });
}

function toFriendlyMessage(error) {
  const raw = String(error?.message || "Неизвестная ошибка");
  const diagnostic = [error?.code, error?.message, error?.details, error?.hint]
    .filter(Boolean)
    .join(" ");
  const known = {
    project_id_required: "Выберите активный проект и заново подготовьте версию ТЗ.",
    duet_provider_key_missing: "Ключ HeyGen не настроен на сервере — каталог и создание персонажа недоступны.",
    duet_provider_credits_unavailable: "В кабинете HeyGen не хватает кредитов на создание персонажа.",
    duet_provider_authentication_failed: "HeyGen не принял ключ сервера. Проверьте секрет HEYGEN_API_KEY.",
    duet_provider_generation_rejected: "HeyGen отклонил запрос на создание персонажа.",
    duet_provider_response_invalid: "HeyGen ответил в неизвестной форме; персонаж не создан.",
    duet_provider_catalog_unavailable: "Кабинет HeyGen сейчас недоступен. Повторите позже.",
    workspace_project_not_found: "Активный проект больше недоступен. Вернитесь на рабочий стол и выберите проект заново.",
    workspace_project_access_required: "Нет доступа к выбранному проекту. Попросите владельца или администратора добавить вас в проект.",
    research_run_project_scope_mismatch: "Исследование относится к другому проекту. Откройте исходный проект и обновите снимок этапов.",
    research_stage_recompute_child_project_scope_mismatch: "Сохранённый пересчёт не привязан к этому проекту. Платный запуск остановлен; обновите статус без повтора.",
    project_members_payload_invalid: "Параметры списка доступа устарели. Выберите проект заново.",
    publishing_enqueue_placement_not_found: "Размещение не найдено. Обновите раздел публикаций.",
    publishing_enqueue_placement_not_open: "Это размещение уже закрыто — в очередь ставятся только открытые задачи.",
    publishing_enqueue_placement_foreign: "Задача назначена другому исполнителю. Ставить её в очередь может он, продюсер или администратор.",
    publishing_enqueue_account_missing: "У размещения не указан аккаунт компании — очередь не знает, куда публиковать.",
    publishing_enqueue_account_unavailable: "Аккаунт размещения отключён или удалён из реестра. Проверьте «Люди → Аккаунты».",
    publishing_enqueue_account_posting_disabled: "У аккаунта выключен режим размещения. Включите его в реестре «Люди → Аккаунты».",
    publishing_enqueue_account_not_assigned: "Аккаунт не выдан вам. Попросите владельца выдать доступ в «Люди → Аккаунты».",
    publishing_enqueue_media_required: "У размещения нет привязанного ролика — очередь не знает, что публиковать.",
    publishing_enqueue_media_not_found: "Привязанный ролик не найден или ещё не готов.",
    publishing_enqueue_media_not_generated_video: "В очередь публикаций ставятся только готовые ролики генерации.",
    publishing_enqueue_scheduled_at_invalid: "Время выхода не прочиталось. Укажите дату и время публикации.",
    publishing_enqueue_scheduled_at_out_of_range: "Время выхода — от текущего момента до 90 дней вперёд.",
    publishing_enqueue_erid_invalid: "ERID — 4–64 знака: латиница, цифры, дефис. Для органики — ORGANIC.",
    publishing_enqueue_organic_with_advertiser: "У органики не бывает рекламодателя. Уберите рекламные реквизиты или укажите ERID рекламы.",
    publishing_enqueue_caption_required: "Для органики подпись обязательна: без маркировки текст поста не собирается сам.",
    publishing_enqueue_caption_too_long: "Подпись с хэштегами и маркировкой длиннее 4000 знаков. Сократите текст.",
    publishing_enqueue_project_mismatch: "Размещение относится к другому проекту. Откройте его исходный проект.",
    publishing_enqueue_media_mismatch: "Указанный ролик не совпадает с привязанным к размещению.",
    ord_provider_invalid: "Название ОРД — от 2 до 80 знаков.",
    contract_ref_invalid: "Реквизит договора — от 2 до 180 знаков.",
    video_finalization_payload_invalid: "Проверьте плашки (до 80 знаков), текст диктора (до 300 знаков) и голос из списка.",
    video_finalization_media_not_found: "Ролик не найден или ещё не готов. Обновите «Запуски и готовые файлы».",
    video_finalization_kind_not_generated_video: "Финализируются только готовые ролики генерации.",
    video_finalization_voice_invalid: "Выбранный голос недоступен. Выберите голос из списка.",
    video_finalization_too_short: "Ролик короче 5 секунд — плашкам не хватит места. Финализируйте ролик подлиннее.",
    video_finalization_media_reference_invalid: "Ролик не распознан. Обновите «Запуски и готовые файлы» и попробуйте снова.",
    video_finalization_caption_windows_invalid: "Тайминги плашек — три пары секунд, начало каждого окна меньше конца.",
    video_finalization_caption_positions_invalid: "Позиции плашек — три значения «верх» или «низ».",
    video_finalization_font_scale_invalid: "Размер плашек — мелкий, средний или крупный.",
    video_finalization_audio_mode_invalid: "Режим звука — «убрать» или «оставить тихо под голосом».",
    client_review_campaign_not_found: "Кампания не найдена или не активна. Обновите экран бюджета.",
    client_review_media_ids_invalid: "Выберите от 1 до 50 роликов для витрины.",
    client_review_media_not_reviewable: "В ссылку попадают только готовые ролики генерации и финализации.",
    client_review_media_not_accepted: "У ролика нет принятой QA-проверки. Отметьте кураторскую ответственность или проведите ролик через QA.",
    client_review_ttl_invalid: "Срок ссылки — от 1 до 90 дней.",
    client_review_link_not_found: "Ссылка не найдена. Обновите список ссылок кампании.",
    client_intake_decision_invalid: "Решение по брифу — «принять» или «вернуть с комментарием».",
    client_intake_comment_required: "Для возврата брифа нужен комментарий клиенту.",
    client_intake_brief_not_found: "Бриф не найден. Обновите список ссылок.",
    project_member_grant_payload_invalid: "Не удалось безопасно выдать доступ. Обновите список проекта.",
    project_member_revoke_payload_invalid: "Не удалось безопасно отозвать доступ. Обновите список проекта.",
    project_member_profile_id_invalid: "Не удалось определить участника команды. Обновите список.",
    project_members_response_invalid: "Сервер вернул неполный список доступа. Обновите выбранный проект.",
    project_member_mutation_response_invalid: "Сервер не подтвердил изменение доступа. Обновите список перед повтором.",
    project_member_target_not_operational: "Доступ к проекту можно выдать только активному участнику с рабочей ролью.",
    project_member_not_found: "Участник уже не имеет доступа к этому проекту. Список будет обновлён.",
    project_member_is_protected: "Доступ владельца, администратора или создателя проекта нельзя отозвать.",
    generation_spec_project_scope_mismatch: "Исследование, товар или исходники относятся к другому проекту. Платный запуск остановлен.",
    generation_spec_research_category_rule_stale: "Правило категории из исследования изменилось. Бесплатно пересчитайте ТЗ и утвердите новую версию.",
    onboarding_required: "Сначала завершите обучение и сдайте экзамен.",
    final_exam_required: "Рабочий кабинет откроется после итогового экзамена.",
    four_courses_required: "Сначала завершите все четыре обязательных курса.",
    required_courses_incomplete: "Сначала завершите все четыре обязательных курса.",
    refreshed_courses_required: "Пройдите обновлённые рабочие аттестации всех четырёх блоков и завершите каждый блок заново.",
    course_not_found: "Учебный модуль больше недоступен. Обновите каталог.",
    course_knowledge_check_required: "Сначала пройдите рабочую аттестацию этого блока на сервере.",
    course_practice_required: "Сначала завершите обязательную практику этого блока.",
    training_progress_sync_required: "Не удалось подтвердить практику на сервере. Проверьте соединение и повторите завершение блока — прогресс на экране сохранён.",
    course_check_answers_invalid: "Проверьте все решения рабочей аттестации и отправьте их ещё раз.",
    course_check_catalog_unavailable: "Рабочая аттестация временно недоступна. Обновите страницу.",
    unknown_course_check_question: "Аттестация обновилась. Обновите страницу и ответьте заново.",
    course_check_cooldown: "Следующая попытка рабочей аттестации откроется после обязательной паузы.",
    course_check_daily_attempt_limit: "Лимит попыток рабочей аттестации за 24 часа исчерпан. Повторите материал и вернитесь позже.",
    practical_project_self_review_not_allowed: "Свою пробную работу принимать нельзя: её должен независимо проверить другой руководитель.",
    practical_project_private_file_required: "Финальный допуск выдаётся только по защищённому MP4. Верните внешнюю ссылку на доработку и запросите файл.",
    practical_project_review_pending: "Работа уже отправлена и ожидает решения руководителя.",
    practical_project_version_conflict: "Работа изменилась в другой вкладке. Обновите очередь перед решением.",
    exam_catalog_unavailable: "Каталог экзамена временно недоступен. Обновите страницу позже.",
    exam_cooldown: "Новая попытка экзамена пока недоступна. Дождитесь времени, указанного на экране.",
    exam_attempt_limit_active: "Лимит попыток за 24 часа исчерпан. Дождитесь времени следующей попытки на экране.",
    membership_required: "Для аккаунта ещё не назначена команда. Обратитесь к руководителю.",
    membership_suspended: "Доступ приостановлен. Обратитесь к руководителю вашей команды.",
    membership_revoked: "Доступ отозван. Обратитесь к руководителю вашей команды.",
    admin_snapshot_invalid: "Сервер не подтвердил безопасный административный снимок.",
    admin_action_invalid: "Не удалось определить административное действие.",
    admin_member_action_invalid: "Не удалось определить действие с участником.",
    admin_member_profile_invalid: "Участник больше не найден. Обновите список.",
    admin_reason_invalid: "Укажите проверяемую причину длиной от 10 до 500 символов.",
    admin_account_id_invalid: "Рабочий аккаунт больше не найден. Обновите список.",
    admin_account_version_invalid: "Карточка аккаунта устарела. Обновите список.",
    admin_account_platform_invalid: "Выберите площадку из списка.",
    admin_account_label_invalid: "Название аккаунта должно содержать от 2 до 160 символов.",
    admin_account_handle_invalid: "Логин аккаунта имеет неверный формат.",
    admin_account_url_invalid: "Укажите публичную ссылку http или https.",
    admin_account_notes_invalid: "Безопасная заметка слишком длинная или имеет неверный формат.",
    auth_account_not_active: "Текущая учётная запись не подтверждена или заблокирована.",
    self_membership_change_forbidden: "Нельзя приостановить или удалить собственное членство.",
    owner_membership_protected: "Доступ владельца защищён. Передайте владение отдельной процедурой.",
    admin_membership_protected: "Администратор не может изменить другого администратора.",
    target_member_not_found: "Участник больше не найден. Обновите список.",
    target_account_not_active: "Учётная запись участника не подтверждена или отключена.",
    target_membership_not_active: "Закрепить аккаунт можно только за активным подтверждённым участником.",
    revoked_member_cannot_be_suspended: "Удалённого участника нельзя приостановить.",
    revoked_member_cannot_be_reactivated: "Удалённого участника нельзя восстановить обычной кнопкой.",
    managed_account_not_found: "Рабочий аккаунт больше не найден. Обновите список.",
    managed_account_archived: "Рабочий аккаунт уже находится в архиве.",
    managed_account_stale: "Карточка аккаунта изменилась в другой вкладке. Обновите список.",
    account_assignment_protected: "Это назначение руководителя может изменить только владелец.",
    revocation_confirmation_invalid: "Подтверждение удаления участника не прошло проверку.",
    archive_confirmation_invalid: "Подтверждение архивирования не прошло проверку.",
    admin_snapshot_timeout: "Админка не ответила вовремя. Обновите данные перед повтором.",
    admin_mutation_timeout: "Сервер не подтвердил изменение вовремя. Сначала обновите список.",
    inactive_membership: "Доступ к команде приостановлен. Обратитесь к руководителю.",
    active_membership_required: "Доступ к команде приостановлен. Обратитесь к руководителю.",
    profile_not_active: "Аккаунт приостановлен. Обратитесь к руководителю.",
    verified_email_required: "Для работы нужен аккаунт с подтверждённой почтой.",
    role_not_allowed: "У вашей роли нет права на это действие.",
    mock_only_required: "Платная генерация отключена. Доступен только dry-run задач без файлов и списаний.",
    real_generation_is_disabled: "Платная генерация сейчас недоступна. Используйте dry-run задач без файлов и списаний.",
    real_generation_exactly_one_media_required: "Для платного запуска выберите ровно одно точное фото товара.",
    real_generation_product_references_invalid: "Выберите от одного до пяти точных фото одного товара.",
    product_reference_media_ids_invalid: "Выберите от одного до пяти разных ракурсов одного товара.",
    exact_product_reference_bundle_mismatch: "Выбранные фото должны принадлежать одному товару и иметь подтверждённые права.",
    generation_product_interaction_invalid: "Восстановите безопасное ТЗ с учётом реального размера и способа использования товара.",
    real_spend_confirmation_required: "Подтвердите создание одного платного видео по указанной цене.",
    real_generation_payload_invalid: "Форма платного запуска несовместима с сервером. Обновите портал перед повторной попыткой.",
    real_generation_sku_invalid: "Параметры платного режима не совпадают с подтверждённой ценой.",
    real_generation_sku_binding_invalid: "Сервер не смог связать длительность, звук и подтверждённую цену запуска.",
    real_generation_action_invalid: "Неизвестное действие платной генерации.",
    real_generation_response_invalid: "Сервис генерации вернул некорректный ответ.",
    real_generation_request_failed: "Не удалось вызвать сервис платной генерации. Повторите попытку позже.",
    provider_preflight_invalid: "Сервис генерации не подтвердил готовность выбранной модели. Платный запуск не создан.",
    provider_configuration_error: "Доступ к выбранному сервису генерации не настроен. Платный запуск не создан.",
    provider_authentication_failed: "Сервис генерации отклонил ключ доступа. Платный запуск не создан.",
    provider_credits_unavailable: "В выбранном сервисе недостаточно средств для запуска. Деньги не списаны.",
    provider_balance_insufficient: "На счёте сервиса генерации не хватает кредитов для этого запуска. Пополните баланс провайдера и снова нажмите «Показать цену» — деньги не списаны.",
    provider_readiness_unavailable: "Сервис генерации не ответил на бесплатную проверку готовности. Платный запуск не создан, деньги не списаны.",
    real_generation_user_daily_quota_exceeded: "Исчерпан суточный лимит платных запусков для вашей учётной записи (10 за 24 часа). Дождитесь освобождения окна и повторите — деньги не списаны.",
    real_generation_organization_daily_quota_exceeded: "Исчерпан суточный лимит платных запусков организации (50 за 24 часа). Деньги не списаны.",
    real_generation_assignee_concurrency_exceeded: "У вас уже есть незавершённый платный запуск. Дождитесь его результата — деньги не списаны.",
    real_generation_organization_concurrency_exceeded: "В организации уже идут три платных запуска. Дождитесь их завершения — деньги не списаны.",
    provider_rate_limited: "Суточная квота выбранного сервиса исчерпана. Платный запуск не создан.",
    provider_request_rejected: "Выбранная модель сейчас недоступна в сервисе генерации. Платный запуск не создан.",
    provider_request_failed: "Сервис генерации не ответил на бесплатную проверку готовности. Платный запуск не создан.",
    provider_response_invalid: "Сервис генерации вернул некорректный ответ проверки. Платный запуск не создан.",
    real_generation_failed: "Платная генерация завершилась ошибкой. Проверьте статус задачи.",
    real_generation_user_daily_quota_exceeded: "Дневной лимит платных запусков исчерпан. Продолжите после обновления лимита.",
    real_generation_organization_daily_quota_exceeded: "Командный дневной лимит платных запусков исчерпан. Обратитесь к руководителю.",
    real_generation_assignee_concurrency_exceeded: "У выбранного исполнителя уже создаётся платный ролик. Дождитесь его завершения — повторная оплата не требуется.",
    real_generation_organization_concurrency_exceeded: "Командная очередь платных роликов заполнена. Дождитесь завершения текущих задач.",
    paid_generation_paused: "Платная генерация приостановлена руководителем. Dry-run задач без файлов остаётся доступен.",
    paid_generation_policy_missing: "Для команды ещё не настроен безопасный денежный лимит платной генерации.",
    generation_daily_budget_exceeded: "Дневной бюджет платной генерации исчерпан. Dry-run задач без файлов остаётся доступен.",
    generation_monthly_budget_exceeded: "Месячный бюджет платной генерации исчерпан. Обратитесь к руководителю.",
    generation_per_request_budget_exceeded: "Цена запуска превышает утверждённый разовый лимит.",
    generation_budget_reservation_invalid: "Сервер не подтвердил резерв денег. Платный запрос провайдеру не отправлен.",
    generation_budget_policy_changed: "Лимиты изменились. Обновите остаток перед новым платным запуском.",
    generation_budget_limits_invalid: "Лимит одного запуска должен быть не больше дневного, а дневной — не больше месячного.",
    generation_budget_reason_invalid: "Укажите проверяемую причину изменения денежного лимита.",
    generation_budget_timezone_invalid: "Не удалось определить часовой пояс денежного лимита.",
    paid_generation_campaign_required: "Выберите активную кампанию для платного запуска.",
    paid_generation_campaign_not_active: "Выбранная кампания не активна.",
    paid_generation_product_category_invalid: "Выберите категорию товара для правил QA и обязательных предупреждений.",
    paid_generation_product_category_binding_invalid: "Сервер не смог связать категорию с точным товаром платного запуска.",
    ai_learning_category_invalid: "Выберите точную товарную категорию ИИ‑центра.",
    ai_learning_control_room_payload_invalid: "Параметры ИИ‑центра устарели. Откройте категорию заново.",
    ai_learning_market_scope_index_payload_invalid: "Параметры списка рыночных категорий устарели. Обновите ИИ‑центр.",
    ai_learning_market_scope_index_limit_invalid: "Не удалось безопасно ограничить список рыночных категорий.",
    ai_knowledge_source_kind_invalid: "Добавьте HTTPS‑ссылку или поддерживаемый файл.",
    ai_knowledge_source_payload_invalid: "Форма источника устарела. Обновите ИИ‑центр и повторите добавление.",
    ai_knowledge_source_copy_invalid: "Проверьте название и пояснение к источнику.",
    ai_knowledge_source_rights_required: "Подтвердите право команды использовать источник для обучения.",
    ai_knowledge_source_link_invalid: "Проверьте ссылку и её контрольные данные.",
    ai_knowledge_source_url_invalid: "Добавьте публичную HTTPS‑ссылку без логина и пароля.",
    ai_knowledge_source_file_invalid: "Файл знаний не прошёл проверку типа, размера или контрольной суммы.",
    ai_knowledge_storage_access_denied: "Сервер отклонил путь файла вне защищённой папки этой команды.",
    ai_knowledge_storage_object_not_found: "Загруженный файл не найден в защищённой папке команды.",
    ai_knowledge_storage_metadata_invalid: "Хранилище вернуло неполные контрольные данные файла.",
    ai_knowledge_storage_metadata_mismatch: "Размер или тип файла изменился при загрузке; источник не зарегистрирован.",
    ai_knowledge_source_quota_exceeded: "Для этой категории уже зарегистрировано слишком много источников.",
    ai_knowledge_storage_quota_exceeded: "Лимит закрытой базы знаний исчерпан.",
    ai_teaching_card_not_found: "Карточка обучения изменилась. Обновите ИИ‑центр.",
    ai_teaching_card_stale: "Версия карточки изменилась. Решение не применено — обновите ИИ‑центр.",
    ai_teaching_scope_version_conflict: "Эта категория уже получила новую обратную связь. Данные обновлены; повторите решение осознанно.",
    ai_teaching_decision_payload_invalid: "Форма решения устарела. Обновите ИИ‑центр.",
    ai_teaching_decision_identity_invalid: "Не удалось подтвердить точную версию карточки и категории.",
    ai_teaching_decision_invalid: "Проверьте решение по карточке обучения.",
    paid_generation_campaign_policy_missing: "Для кампании ещё не настроен денежный лимит.",
    paid_generation_campaign_paused: "Платные запуски в этой кампании приостановлены.",
    generation_campaign_per_request_budget_exceeded: "Цена ролика превышает разовый лимит кампании.",
    generation_campaign_daily_budget_exceeded: "Дневной бюджет кампании исчерпан.",
    generation_campaign_monthly_budget_exceeded: "Месячный бюджет кампании исчерпан.",
    generation_campaign_budget_policy_changed: "Лимит кампании изменился. Обновите сводку и повторите запуск.",
    generation_campaign_name_invalid: "Укажите понятное название кампании длиной от 2 до 160 символов.",
    generation_campaign_payload_invalid: "Форма новой кампании устарела. Обновите страницу и повторите.",
    generation_campaign_policy_payload_invalid: "Форма бюджета кампании устарела. Обновите страницу и повторите.",
    generation_campaign_policy_values_invalid: "Лимиты кампании должны быть положительными, согласованными между собой и не выше лимитов команды.",
    generation_campaign_not_found: "Кампания больше недоступна. Обновите денежную сводку.",
    generation_campaign_quota_exceeded: "В команде уже создано слишком много кампаний. Завершите или архивируйте старые.",
    generation_spend_platform_control_missing: "Общий защитный рубильник платной генерации не настроен.",
    generation_spend_platform_disabled: "Платная генерация остановлена общим защитным рубильником. Dry-run задач без файлов доступен.",
    generation_spend_policy_missing: "Для команды ещё не настроен безопасный денежный лимит.",
    generation_spend_organization_disabled: "Платная генерация приостановлена руководителем. Dry-run задач без файлов доступен.",
    generation_spend_daily_limit_exceeded: "Дневной бюджет платной генерации исчерпан.",
    generation_spend_monthly_limit_exceeded: "Месячный бюджет платной генерации исчерпан.",
    generation_spend_per_request_limit_exceeded: "Цена запуска превышает утверждённый разовый лимит.",
    generation_spend_reservation_missing: "Сервер не подтвердил денежный резерв. Запрос провайдеру не отправлен.",
    generation_spend_reservation_not_active: "Денежный резерв запуска уже закрыт. Обновите очередь.",
    generation_spend_reservation_frozen: "Денежный резерв заморожен до ручной сверки запуска.",
    generation_spend_policy_version_conflict: "Лимиты уже изменились в другой вкладке. Обновите остаток.",
    generation_spend_policy_values_invalid: "Проверьте денежные лимиты, часовой пояс и причину изменения.",
    generation_spend_active_reservations_exist: "Часовой пояс нельзя изменить, пока есть активные денежные резервы.",
    seedance_approved_product_media_required: "Для восьмисекундного ролика выберите подтверждённое точное фото этого товара.",
    generation_job_id_invalid: "Не удалось определить платную задачу. Обновите раздел.",
    generation_reconciliation_incident_invalid: "Не удалось определить инцидент платного запуска. Обновите раздел.",
    generation_reconciliation_resolution_invalid: "Выберите результат ручной сверки платного запуска.",
    generation_reconciliation_evidence_invalid: "Добавьте проверяемое основание и подробную причину ручной сверки.",
    generation_reconciliation_provider_invalid: "Не удалось подтвердить сервис этого запуска. Обновите карточку.",
    generation_reconciliation_task_id_invalid: "Укажите точный task ID или Google operation из панели сервиса генерации.",
    generation_reconciliation_forbidden: "Ручную сверку платного запуска может выполнить только владелец или администратор команды.",
    generation_strategy_readiness_prompt_invalid: "Речь ведущего не уложилась в длительность ролика: около 15 знаков на секунду и не больше 1500. Сократите текст и повторите бесплатную проверку.",
    posting_mode_requires_connection: "Режим «через API» включается подключением аккаунта к публикации, а не вручную: без живого подключения воркеру нечем публиковать.",
    custodian_not_eligible: "Хранителем аккаунта может быть только активный владелец, администратор или продюсер.",
    ownership_kind_invalid: "Неизвестный вид владения аккаунтом.",
    registration_email_alias_invalid: "Почтовый алиас регистрации должен быть адресом вида имя@домен.",
    account_changed_concurrently: "Карточку аккаунта уже изменил другой администратор. Обновите список и повторите.",
    generation_strategy_reconciliation_forbidden: "Ручную сверку запуска стратегии может выполнить только владелец или администратор команды.",
    generation_reconciliation_task_not_found: "Задача сервиса с таким ID не найдена. Проверьте точный идентификатор в панели провайдера.",
    generation_reconciliation_task_mismatch: "Задача сервиса не совпадает со временем этого запуска. Не прикрепляйте чужую задачу.",
    generation_reconciliation_wait_required: "Для подтверждения отсутствия задачи сервиса подождите две минуты после фиксации инцидента.",
    generation_reconciliation_rejected: "Состояние запуска изменилось. Обновите очередь перед ручной сверкой.",
    generation_strategy_reconciliation_not_current: "Состояние сверки этого запуска изменилось. Обновите карточку: возможно, сверка уже выполнена.",
    generation_strategy_reconciliation_task_mismatch: "Сервис генерации не подтвердил этот task/request ID для данного запуска. Проверьте точный идентификатор и время создания в панели выбранного провайдера.",
    generation_strategy_reconciliation_rejected: "Сервер отклонил ручную сверку стратегии. Обновите карточку запуска и проверьте данные ещё раз.",
    real_generation_reconciliation_required: "Новый платный запуск временно закрыт: сначала владелец или администратор должен завершить ручную сверку предыдущего запроса к сервису генерации.",
    generation_learning_context_required: "Восстановите безопасное авто-ТЗ и дождитесь бесплатной проверки обучения.",
    generation_learning_policy_category_invalid: "Выберите категорию товара для отдельного контура обучения.",
    generation_learning_category_mismatch: "Категория товара изменилась. Дождитесь нового обучения с нуля и восстановите авто-ТЗ.",
    generation_learning_category_binding_invalid: "Сервер не смог сохранить категорию вместе с обучающим сигналом. Платный запуск не создан.",
    generation_learning_opt_out_invalid: "Не удалось подтвердить осознанное отключение обученного ракурса.",
    generation_learning_unavailable: "Обученное ТЗ временно не проверено. Платный запуск не создан.",
    generation_learning_policy_required: "Для товара уже есть подтверждённое обучение. Обновите авто-ТЗ перед запуском.",
    generation_learning_policy_stale: "Обученное ТЗ обновилось. Восстановите авто-ТЗ и повторите запуск.",
    generation_learning_prompt_binding_invalid: "Обученные инструкции не попали в фактическое ТЗ. Восстановите безопасное авто-ТЗ перед запуском.",
    generation_mode_prompt_binding_invalid: "ТЗ не соответствует техническому контракту выбранной модели. Восстановите безопасное авто-ТЗ: точный товар, формат, длительность, реплика и запрет надписей будут проверены заново.",
    generation_strategy_selection_invalid: "Проверьте выбранную стратегию, точные исходники, параметры результата и все подтверждения прав.",
    generation_strategy_binding_payload_invalid: "Параметры стратегии изменились. Проверьте форму и выполните бесплатную привязку заново.",
    generation_strategy_binding_project_access_required: "Нет доступа к проекту выбранной стратегии. Вернитесь на рабочий стол и обновите проект.",
    generation_strategy_binding_spec_invalid: "Стратегия не совпадает с текущей технической версией. Подготовьте ТЗ заново.",
    generation_strategy_binding_spec_not_approved: "Перед проверкой цены прочитайте и отдельно одобрите точную техническую версию.",
    generation_strategy_binding_conflict: "К этой версии ТЗ уже привязана другая стратегия или другой набор исходников. Подготовьте новую версию.",
    generation_strategy_binding_invalid: "Сервер не подтвердил точные исходники и права стратегии. Обновите файлы и повторите бесплатную проверку.",
    generation_spec_context_required: "Портал не привязал техническое ТЗ к запуску. Деньги не списаны — повторите запуск.",
    generation_spec_baseline_required: "Эта новая модель пока запускается только с базовым ТЗ без применённого Research или обученного сценария. Выберите доступную модель либо подготовьте базовый замысел — деньги не списаны.",
    generation_spec_context_invalid: "Техническая версия устарела. Деньги не списаны — повторите запуск.",
    generation_video_reference_binding_payload_invalid: "Проверьте YouTube-ссылку и описание механики видеореференса.",
    generation_video_reference_attestation_required: "Подтвердите законный доступ к референсу и перенос только механики.",
    generation_video_reference_prompt_binding_invalid: "Механика референса не вошла в проверяемое ТЗ. Деньги не списаны.",
    generation_video_reference_marker_invalid: "Служебная строка видеореференса повреждена или добавлена вручную. Обновите авто-ТЗ — деньги не списаны.",
    generation_video_reference_context_invalid: "Видеореференс не привязан к платному запуску. Деньги не списаны.",
    generation_video_reference_scope_mismatch: "Видеореференс относится к другому проекту или версии ТЗ.",
    generation_video_reference_job_binding_invalid: "Сервер не сохранил lineage видеореференса. Деньги не списаны.",
    generation_video_reference_lineage_response_invalid: "Общая запись видеореференса повреждена. Обновите запуск или обратитесь к руководителю.",
    generation_spec_prepare_payload_invalid: "Портал не смог подготовить техническое ТЗ. Проверьте замысел и выбранный товар.",
    generation_spec_control_payload_invalid: "Техническая версия изменилась. Повторите запуск — платный запрос не выполнялся.",
    generation_spec_patch_invalid: "Не удалось сохранить исправленный замысел в технической версии. Повторите запуск.",
    generation_spec_ai_research_binding_payload_invalid: "Не удалось связать техническую версию с выбранной рекомендацией ИИ‑центра. Платный запуск остановлен.",
    generation_spec_ai_research_binding_confirmation_required: "Подтвердите применение рекомендательного пресета ИИ‑центра ещё раз.",
    generation_spec_ai_research_binding_version_invalid: "Версия технического замысла изменилась. Платный запуск остановлен — повторите подготовку.",
    generation_spec_ai_research_binding_hash_invalid: "Контрольная версия технического замысла устарела. Платный запуск остановлен.",
    generation_spec_ai_research_binding_position_invalid: "Выбранная рекомендация ИИ‑центра больше недоступна. Обновите варианты.",
    generation_spec_ai_research_binding_scope_mismatch: "Рекомендация ИИ‑центра относится к другому проекту или категории. Платный запуск остановлен.",
    generation_spec_ai_research_binding_recommendation_missing: "Сохранённая рекомендация ИИ‑центра изменилась. Обновите варианты перед запуском.",
    generation_spec_ai_research_binding_conflict: "К этой версии уже привязана другая рекомендация ИИ‑центра. Подготовьте новую версию замысла.",
    generation_spec_ai_research_binding_response_invalid: "Сервер не подтвердил связь замысла с рекомендацией ИИ‑центра. Платный запуск остановлен.",
    generation_spec_response_invalid: "Сервер вернул неполную техническую версию. Платный запрос не выполнялся — повторите запуск.",
    generation_spec_prepare_unavailable: "Заполните замысел и выберите точные исходники товара.",
    generation_spec_patch_required: "Замысел изменился. Портал подготовит новую техническую версию при следующем запуске.",
    generation_spec_launch_confirmation_stale: "Техническая версия изменилась во время проверки. Платный запрос не выполнен — повторите запуск.",
    generation_spec_effective_payload_invalid: "Сервер не смог проверить точную версию ТЗ. Обновите карточку перед запуском.",
    generation_spec_effective_policy_invalid: "Сервер вернул неполную проверку ТЗ. Платный запуск остановлен.",
    generation_spec_effective_policy_unavailable: "Проверка актуальности ТЗ временно недоступна. Провайдер и списание не запускались.",
    generation_spec_exact_scope_invalid: "Товар, ракурсы, модель, длительность, формат или аудио не совпадают с версией ТЗ.",
    generation_spec_approval_required: "Техническая версия устарела во время запуска. Деньги не списаны — повторите запуск.",
    generation_batch_id_invalid: "Не удалось определить запуск в истории.",
    generation_batch_archive_payload_invalid: "Не удалось подтвердить удаление запуска из истории.",
    generation_batch_not_found: "Этот запуск уже удалён из истории или относится к другому проекту.",
    generation_batch_archive_forbidden: "Удалить этот запуск из истории может его автор или руководитель.",
    generation_batch_archive_active: "Активный запуск нельзя удалить: дождитесь результата или ошибки.",
    generation_spec_approval_state_invalid: "Статус технической версии изменился. Деньги не списаны — повторите запуск.",
    generation_spec_stale: "Исходники или правила качества изменились. Портал пересчитает ТЗ при следующем запуске.",
    generation_spec_head_invalid: "Появилась более новая версия ТЗ. Обновите историю перед решением.",
    generation_spec_media_stale: "Один из исходников ТЗ изменился или недоступен. Проверьте точные ракурсы.",
    generation_spec_request_mismatch: "Поля запуска отличаются от утверждённой версии ТЗ. Сохраните их новой версией.",
    generation_spec_learning_binding_invalid: "Обученная политика не совпадает с утверждённым ТЗ. Пересчитайте версию бесплатно.",
    generation_spec_repair_binding_invalid: "QA-исправление не совпадает с утверждённым ТЗ. Подготовьте новую версию.",
    generation_spec_outcome_binding_invalid: "Выбор результата обучения изменился. Обновите advisory и подготовьте новую версию ТЗ.",
    generation_spec_provider_start_stale: "ТЗ устарело непосредственно перед запуском. Провайдер и списание остановлены.",
    generation_spec_policy_blocked: "Серверная политика качества остановила эту версию. Проверьте рекомендуемый следующий шаг.",
    generation_spec_prompt_binding_invalid: "Фактический prompt отличается от утверждённой серверной версии. Платный запуск остановлен.",
    generation_spec_policy_binding_invalid: "Контекст обучения или QA отличается от утверждённой версии ТЗ.",
    generation_spec_scope_binding_invalid: "Параметры платного режима отличаются от утверждённой версии ТЗ.",
    generation_spec_state_conflict: "Сервер остановил запуск из-за конфликта истории ТЗ. Обновите карточку; провайдер не вызван.",
    generation_learning_rejection_guard_blocked: "Эта модель временно остановлена серверным контуром качества. Портал подберёт безопасную альтернативу без запуска провайдера.",
    generation_quality_guard_control_review_pending: "Контрольный результат уже создан и ждёт независимого QA. Новый платный контроль не нужен.",
    generation_research_claim_evidence_invalid: "Одобренное исследование не содержит проверяемую immutable-базу safe/forbidden claims. Платный запуск не создан: обновите AI-исследование и одобрите его без ручной подмены.",
    auth_session_required: "Сессия истекла. Войдите снова перед платным запуском.",
    authentication_required: "Сессия истекла. Войдите снова перед платным запуском.",
    invalid_payload: "Проверьте поля платного запуска и выбранный исходник.",
    origin_not_allowed: "Платная генерация недоступна с этого адреса портала.",
    generation_rejected: "Сервер отклонил платный запуск. Проверьте доступ, исходник и подтверждение расходов.",
    generation_unavailable: "Сервис платной генерации временно недоступен. Повторите попытку позже.",
    generation_campaign_daily_budget_exceeded: "Дневной бюджет выбранной кампании исчерпан. Деньги не списаны: поднимите дневной лимит кампании или продолжите завтра.",
    generation_campaign_monthly_budget_exceeded: "Месячный бюджет выбранной кампании исчерпан. Деньги не списаны: поднимите месячный лимит кампании.",
    generation_campaign_per_request_budget_exceeded: "Запуск дороже лимита одного запуска кампании. Деньги не списаны: поднимите лимит запуска или выберите модель дешевле.",
    generation_daily_budget_exceeded: "Дневной бюджет организации на платную генерацию исчерпан. Деньги не списаны; лимит меняет владелец.",
    generation_monthly_budget_exceeded: "Месячный бюджет организации на платную генерацию исчерпан. Деньги не списаны; лимит меняет владелец.",
    generation_per_request_budget_exceeded: "Запуск дороже разрешённой цены одного запуска организации. Деньги не списаны; лимит меняет владелец.",
    generation_route_unresolved: "Сервер не смог подтвердить, каким движком выполняется этот запуск, и не стал опрашивать провайдера наугад. Деньги уже зарезервированы: не запускайте повторно — сообщите руководителю, чтобы запуск сверили вручную.",
    generation_strategy_source_duration_mismatch: "У выбранной модели секунда стоит денег, а длительность задаёт исходник. Длительность в форме должна совпадать с проверенной сервером длиной исходного ролика — обновите шаг «Длительность» и повторите. Деньги не списаны.",
    product_research_input_invalid: "Проверьте название товара и артикул.",
    research_youtube_source_requires_media: "YouTube-ссылка относится к отдельному видеоисточнику. Сначала добавьте разрешённый MP4 в исследование или исключите YouTube-ссылку из рыночного запроса.",
    exact_youtube_media_attachment_payload_invalid: "Контекст загрузки MP4 устарел. Вернитесь в ИИ-центр и откройте точный источник заново.",
    exact_youtube_media_attachment_rights_required: "Подтвердите право команды использовать MP4 для разбора.",
    exact_youtube_media_attachment_source_match_required: "Подтвердите, что MP4 является именно зарегистрированным YouTube-роликом. Другое видео нужно добавить как отдельный источник.",
    exact_youtube_media_attachment_identity_required: "Подтвердите, что MP4 является именно зарегистрированным YouTube-роликом. Другое видео нужно добавить как отдельный источник.",
    exact_youtube_media_attachment_source_scope_mismatch: "YouTube-источник относится к другому проекту или больше недоступен. Обновите ИИ-центр.",
    exact_youtube_media_attachment_media_invalid: "Для этого источника нужен сохранённый исходный MP4 с подтверждёнными правами. Сгенерированные ролики и другие типы файлов не подходят.",
    exact_youtube_media_attachment_conflict: "Источник или MP4 уже связан с другой записью. Обновите ИИ-центр перед продолжением.",
    exact_youtube_media_attachment_project_access_required: "Доступ к проекту изменился. Откройте проект заново перед привязкой MP4.",
    exact_youtube_media_attachment_hash_invalid: "Не удалось подтвердить целостность привязки MP4. Обновите ИИ-центр и повторите только привязку.",
    exact_video_research_binding_payload_invalid: "Подготовка точного видеоисточника заполнена не полностью. Платный анализ не запущен — повторите подготовку пяти кадров.",
    exact_video_research_binding_response_invalid: "Исследование сохранено, но связь с точным MP4 и пятью кадрами не подтверждена. Новый платный запуск не создавайте; обновите статус сохранённого исследования.",
    exact_video_research_evidence_not_ready: "Пять контрольных кадров ещё не получили серверный статус ready. Платный анализ не запущен.",
    exact_video_research_binding_conflict: "Этот attachment уже связан с другим исследованием. Обновите ИИ-центр и откройте сохранённый результат.",
    exact_video_research_source_scope_mismatch: "Видеоисточник, attachment, evidence или товар относятся к другому проекту. Платный анализ не запущен.",
    exact_youtube_source_queue_payload_invalid: "Не удалось определить проект очереди видеоисточников. Вернитесь в ИИ-центр.",
    exact_youtube_source_queue_limit_invalid: "Не удалось безопасно прочитать очередь видеоисточников. Обновите ИИ-центр.",
    exact_youtube_source_queue_response_invalid: "Сервер не подтвердил актуальную очередь точных YouTube-источников. Платный анализ не запущен.",
    exact_youtube_research_payload_invalid: "Данные точного видеоисточника заполнены не полностью. Платный анализ не запущен.",
    exact_youtube_research_source_scope_mismatch: "Точный YouTube-источник относится к другому проекту или изменился. Платный анализ не запущен.",
    exact_youtube_research_product_identity_mismatch: "Товар у фото не совпадает с названием или SKU зарегистрированного видеоисточника. Платный анализ не запущен.",
    exact_youtube_research_attachment_scope_mismatch: "Связь YouTube-источника с MP4 изменилась. Обновите ИИ-центр; платный анализ не запущен.",
    exact_youtube_research_media_invalid: "Привязанный MP4 больше не проходит проверку исходного файла. Платный анализ не запущен.",
    exact_youtube_research_evidence_invalid: "Пять контрольных JPEG не прошли серверную проверку. Платный анализ не запущен.",
    exact_youtube_research_start_result_invalid: "Сервер не подтвердил созданное исследование. Новый платный запуск не создавайте; обновите историю.",
    exact_youtube_research_binding_conflict: "Этот точный источник уже связан с другим исследованием. Обновите ИИ-центр и историю.",
    exact_youtube_research_evidence_not_ready: "Пять контрольных JPEG ещё не готовы или уже использованы другим запуском. Платный анализ не запущен.",
    exact_youtube_research_evidence_consume_conflict: "Набор контрольных кадров уже использован. Обновите историю; новый платный запуск не создавайте.",
    exact_youtube_research_project_access_required: "Доступ к проекту изменился. Платный анализ не запущен.",
    exact_youtube_research_binding_hash_invalid: "Не удалось подтвердить целостность связи источника и исследования. Платный анализ не запущен.",
    product_research_paid_confirmation_required: "Подтвердите платный ИИ-анализ перед запуском.",
    paid_analysis_ack_required: "Подтвердите платный ИИ-анализ перед запуском.",
    research_execution_authorization_required: "Сервер не получил подтверждение платного анализа. Начните новый запуск и подтвердите расход ещё раз.",
    research_provider_attempt_not_authorized: "Платный вызов не авторизован сервером. Новый внешний запрос не выполнен.",
    research_provider_attempt_conflict: "Провайдер уже привязан к этому запуску с другими параметрами. Обновите статус.",
    research_provider_not_active: "Выбранный исследовательский провайдер не активен. Новый внешний запрос не выполнен.",
    research_market_decision_confirmation_required: "Подтвердите решение по рыночной категории.",
    research_market_decision_action_invalid: "Выберите допустимое действие с рыночной категорией.",
    research_market_decision_action_payload_invalid: "Проверьте поля выбранного действия с рыночной категорией.",
    research_market_category_candidate_stale: "Предложение категории изменилось. Обновите исследование и подтвердите его заново.",
    research_market_category_not_found: "Выбранная рыночная категория больше недоступна. Обновите список.",
    research_market_category_reclassify_required: "У товара уже есть категория. Используйте явную переклассификацию.",
    research_market_category_binding_required: "Сначала подтвердите исходную рыночную категорию товара.",
    research_market_category_unchanged: "Выберите категорию, отличную от текущей.",
    research_market_category_alias_conflict: "Такое название уже принадлежит другой рыночной категории.",
    research_market_category_alias_already_registered: "Этот синоним уже связан с текущей категорией. Обновите исследование.",
    research_market_category_reaffirmation_stale: "Текущая категория изменилась. Обновите исследование перед подтверждением синонима.",
    research_market_category_reaffirmation_source_failed: "Не удалось связать источники исследования с подтверждённым синонимом. Решение не сохранено.",
    research_market_aliases_invalid: "Добавьте не более 10 корректных названий-синонимов.",
    research_market_registry_query_invalid: "Введите точное название или сохранённый синоним категории.",
    research_outcome_refresh_payload_invalid: "Не удалось определить точный контур результатов. Обновите исследование.",
    research_outcome_scope_invalid: "Выберите точную рыночную категорию, площадку и модель.",
    research_outcome_status_payload_invalid: "Статус обучающей памяти запрошен с некорректным контуром.",
    research_outcome_decision_payload_invalid: "Проверьте поля решения по обучающей памяти.",
    research_outcome_decision_action_invalid: "Выберите допустимое решение по обучающей памяти.",
    research_outcome_decision_confirmation_required: "Подтвердите решение по обучающей памяти.",
    research_outcome_decision_version_invalid: "Версия обучающей памяти изменилась. Обновите статус.",
    research_outcome_candidate_not_found: "Кандидат обучения больше недоступен. Обновите статус.",
    research_outcome_refresh_required: "Появились новые зрелые результаты. Сначала явно обновите evidence и проверьте нового кандидата.",
    research_outcome_candidate_stale: "Доказательства кандидата изменились. Обновите и проверьте их заново.",
    research_outcome_candidate_superseded: "Появился более новый кандидат. Проверьте его перед активацией.",
    research_outcome_scope_version_stale: "Активная версия памяти уже изменилась. Обновите статус.",
    research_outcome_candidate_already_decided: "По этому кандидату уже принято решение. Обновите историю.",
    research_outcome_active_memory_mismatch: "Выбранный кандидат сейчас не активен. Обновите статус.",
    research_outcome_rollback_target_invalid: "Точная версия для отката больше недоступна.",
    research_outcome_rollback_target_unexpected: "Версия отката допустима только для действия «откатить».",
    research_youtube_request_payload_invalid: "Параметры YouTube‑проверки устарели. Обновите исследование.",
    research_youtube_query_invalid: "Укажите точный YouTube‑запрос длиной 2–200 символов.",
    research_youtube_locale_invalid: "Проверьте код региона и язык YouTube‑запроса.",
    research_youtube_published_after_invalid: "Дата начала поиска должна быть в пределах последних 366 дней.",
    research_youtube_quota_plan_invalid: "Canary допускает ровно 1 результат и 2 запроса; обновление — 1–25 результатов и 2 запроса.",
    research_youtube_confirmation_required: "Подтвердите квоту, отсутствие автоматического повтора и условия YouTube API.",
    research_youtube_terms_version_invalid: "Версия подтверждённых условий YouTube API устарела. Обновите раздел.",
    research_youtube_market_category_required: "Сначала подтвердите актуальную рыночную категорию товара.",
    research_youtube_provider_contract_invalid: "Контракт провайдера YouTube ещё не разрешён оператором.",
    research_youtube_retention_control_required: "Сервер не подтвердил свежую очистку YouTube API‑данных.",
    research_youtube_global_rollout_gate_required: "Глобальный контур YouTube пока закрыт оператором.",
    research_youtube_rollout_gate_required: "Сначала завершите canary и явно включите обновление категории.",
    research_youtube_fresh_canary_required: "Для включения нужен свежий успешный canary через search.list и videos.list.",
    research_youtube_rollout_decision_invalid: "Выберите включение или паузу обновлений YouTube.",
    research_youtube_rollout_payload_invalid: "Кратко объясните решение по YouTube rollout.",
    research_youtube_rollout_canary_unexpected: "Для паузы не нужно указывать canary. Обновите раздел.",
    research_youtube_ingestion_not_found: "YouTube‑запуск больше недоступен. Обновите исследование.",
    research_youtube_ingestion_lease_inactive: "Безопасная аренда YouTube‑запуска истекла; автоматического повтора не будет.",
    research_youtube_invoke_not_authorized: "Сервер не подтвердил право этого пользователя на сохранённый YouTube‑запуск.",
    research_youtube_local_daily_quota_exhausted: "Дневной лимит YouTube‑запросов по тихоокеанскому времени исчерпан.",
    research_youtube_transport_gate_closed: "Условия запуска изменились до внешнего вызова. Запрос остановлен.",
    research_youtube_candidate_payload_invalid: "Подтвердите временное решение по наблюдению и укажите причину.",
    research_youtube_candidate_stale: "Наблюдение YouTube изменилось или удалено по сроку хранения. Обновите статус.",
    research_youtube_overview_payload_invalid: "Не удалось определить исследование для YouTube‑сводки.",
    research_youtube_overview_limit_invalid: "Лимит истории YouTube‑запусков должен быть от 1 до 20.",
    research_youtube_status_payload_invalid: "Не удалось определить точный YouTube‑запуск.",
    canonical_name_invalid: "Укажите корректное каноническое название рыночной категории.",
    candidate_hash_invalid: "Предложение категории устарело. Обновите исследование.",
    product_research_platform_required: "Выберите хотя бы одну площадку для будущего контента.",
    product_research_run_missing: "Сервер не вернул номер исследования. Обновите раздел и повторите.",
    product_research_run_invalid: "Не удалось определить исследование. Начните новый разбор.",
    product_research_request_failed: "Не удалось запустить анализ товара. Повторите попытку позже.",
    product_research_response_invalid: "Сервис анализа товара вернул некорректный ответ.",
    research_category_learning_status_payload_invalid: "Не удалось определить исследование для готовности доказательной базы.",
    research_market_category_required: "Сначала подтвердите устойчивую рыночную категорию товара.",
    research_market_category_inactive: "Рыночная категория больше не активна. Обновите привязку перед сбором доказательств.",
    research_category_readiness_capture_payload_invalid: "Снимок готовности заполнен не полностью. Обновите статус.",
    research_category_evidence_changed: "Доказательная база изменилась. Проверьте новый процент перед фиксацией.",
    research_source_correction_payload_invalid: "Проверьте точный head, JSON-разбор и причину исправления.",
    research_source_analysis_head_stale: "Разбор источника уже изменился. Обновите ledger и проверьте новую версию.",
    research_source_analysis_invalid: "Разбор должен соответствовать schema v1 и не содержать raw captions, transcript или полный чужой текст.",
    research_source_ledger_not_found: "Источник больше не доступен в выбранной категории. Обновите ledger.",
    research_youtube_analysis_correction_payload_invalid: "Проверьте точный head, JSON-гипотезу и причину исправления YouTube-наблюдения.",
    research_youtube_observation_analysis_invalid: "Гипотеза должна соответствовать retention-bound schema v1 и не может содержать raw captions, transcript или provider payload.",
    research_youtube_derived_analysis_approval_required: "Разбор YouTube остановлен до принятого analytics amendment и точного approval reference.",
    research_youtube_observation_analysis_head_stale: "Гипотеза YouTube уже изменилась. Обновите статус и проверьте новую версию.",
    research_youtube_observation_not_found: "YouTube-наблюдение изменилось или удалено по сроку хранения. Обновите статус.",
    research_collection_policy_payload_invalid: "Политика автосбора заполнена не полностью. Обновите статус.",
    research_collection_policy_invalid: "Проверьте provider, период, hard budget и четыре явных подтверждения.",
    research_collection_expected_policy_invalid: "Точная версия политики не определена. Обновите статус.",
    research_collection_policy_head_stale: "Политика уже изменилась. Обновите статус перед новым решением.",
    research_instagram_provider_legal_choice_required: "Автосбор Instagram остаётся paused до выбора provider и подтверждённой legal-политики.",
    research_youtube_automatic_policy_ack_required: "Для YouTube подтвердите terms, quota, no-retry, hard budget и legal review.",
    legal_review_reference_invalid: "Укажите корректный номер или ссылку на legal review длиной 3–160 символов.",
    research_stage_branch_not_found: "Ветка исправлений больше недоступна. Обновите снимок этапов.",
    research_stage_branch_revision_stale: "Ветка изменилась после загрузки. Обновите точный снимок всей ветки перед решением.",
    research_stage_head_missing: "Точная версия этапа не найдена. Обновите снимок перед решением.",
    research_stage_head_stale: "Этап уже изменился в другой вкладке. Обновите снимок и повторно проверьте решение.",
    research_stage_run_locked: "Main-версия уже утверждена. Ветки доступны только для сравнения; для новой управляемой версии начните отдельное исследование.",
    research_stage_recompute_main_branch_required: "Пересчёт разрешён только для main-ветки. Сравните текущую ветку отдельно.",
    research_stage_recompute_pending: "Сохранённый пересчёт ещё не завершён. Проверьте его статус без нового запуска.",
    research_stage_recompute_active: "В ветке уже есть сохранённый пересчёт. Проверьте или явно отмените его без нового запуска.",
    research_stage_recompute_not_active: "Сохранённый пересчёт уже завершён или изменился. Обновите его статус.",
    research_stage_recompute_lease_active: "Попытка провайдера ещё защищена активной серверной блокировкой. Отмена сейчас закрыта.",
    research_stage_recompute_cancel_invalid: "Условия безопасной отмены изменились. Обновите сохранённый статус без повторного запуска.",
    research_stage_recompute_cancel_not_allowed: "Этот пересчёт нельзя отменить в текущем состоянии. Обновите сохранённый статус.",
    research_stage_comparison_branch_read_only: "Ветка сравнения доступна только для чтения. Вернитесь в main для управляемых изменений.",
    research_stage_revert_target_invalid: "Выбранная версия не подходит для отката. Обновите ограниченную историю этапа.",
    research_stage_replacement_schema_invalid: "Структурная версия не соответствует схеме этапа. Исправьте JSON, не меняя типы обязательных полей.",
    research_stage_rejected: "Один из этапов отклонён. Исправьте или верните его до утверждения.",
    research_stage_dependencies_stale: "Зависимый этап устарел после правки. Начните с самого раннего проблемного этапа.",
    research_stage_snapshot_mismatch: "Семь этапов не привязаны к одному точному черновику. Восстановите снимок перед утверждением.",
    research_v2_human_draft_required: "ИИ-версию должен проверить человек и сохранить как точный review-снимок.",
    research_payload_too_large: "Слишком много вводных для одного разбора. Сократите текст или количество фотографий.",
    research_payload_invalid: "Проверьте название, артикул, ссылку и вводные товара.",
    marketplace_url_invalid: "Укажите полную публичную ссылку на карточку товара, начиная с https://.",
    source_media_ids_invalid: "Можно выбрать не более пяти фотографий товара.",
    platforms_invalid: "Выберите хотя бы одну площадку: Instagram, YouTube, VK, Wildberries или Ozon.",
    content_review_limit_invalid: "История проверки может содержать от 1 до 50 записей.",
    content_review_media_required: "Выберите точное изображение или MP4 из раздела «Материалы».",
    content_review_context_invalid: "Проверьте площадку, статус публикации, категорию товара и наличие людей.",
    content_review_text_too_large: "Сократите подпись и сценарий до 6000 символов каждый.",
    content_review_metrics_required: "Браузер не смог подготовить технические параметры файла.",
    content_review_frames_invalid: "Не удалось подготовить безопасную выборку кадров.",
    content_review_evidence_required: "Сначала сохраните контрольные кадры MP4 в защищённой папке.",
    content_review_evidence_invalid: "Сохранённый набор кадров недоступен или устарел. Подготовьте его заново.",
    content_review_evidence_prepare_invalid: "Сервер не подготовил защищённые места для кадров. Повторите запуск.",
    content_review_evidence_commit_invalid: "Сервер не подтвердил сохранение всех кадров. Повторите запуск.",
    content_review_evidence_frame_invalid: "Один из контрольных кадров повреждён или имеет неверные параметры.",
    content_review_video_evidence_required: "Для MP4 сначала сохраните контрольные кадры в защищённой папке.",
    content_review_video_evidence_not_ready: "Контрольные кадры MP4 ещё не подтверждены. Безопасно повторите подтверждение.",
    content_review_evidence_prepare_payload_invalid: "Не удалось подготовить безопасный запрос для кадров.",
    content_review_evidence_frame_count_invalid: "Для MP4 нужно подготовить четыре кадра и пятый JPEG-атлас.",
    content_review_evidence_audio_metrics_invalid: "Локальные аудиометрики неполны. Подготовьте evidence заново и обязательно прослушайте точный MP4.",
    content_review_evidence_temporal_metrics_invalid: "Локальный скан таймлайна неполон. Обновите страницу и подготовьте evidence заново без нового рендера.",
    content_review_evidence_media_not_accessible: "Видео недоступно вашей роли или уже изменилось. Обновите материалы.",
    content_review_evidence_media_type_invalid: "Для этого evidence выбран неподдерживаемый тип исходного файла.",
    content_review_evidence_active_limit: "Для этого видео уже сохраняется набор кадров. Подождите и повторите запуск.",
    content_review_evidence_daily_limit: "Дневной лимит подготовки кадров исчерпан. Обратитесь к руководителю.",
    content_review_evidence_commit_payload_invalid: "Сервер отклонил неполный запрос подтверждения кадров.",
    content_review_evidence_manifest_invalid: "Список сохранённых кадров имеет неверный формат.",
    content_review_evidence_not_accessible: "Сохранённый evidence недоступен этому аккаунту.",
    content_review_evidence_source_stale: "Исходное видео изменилось после подготовки кадров. Запустите проверку заново.",
    content_review_evidence_object_path_invalid: "Сервер вернул неверный защищённый путь кадра.",
    content_review_evidence_storage_object_invalid: "Один из кадров не найден в защищённой папке.",
    content_review_evidence_storage_metadata_invalid: "Защищённое хранилище не подтвердило тип или размер кадра.",
    content_review_evidence_storage_metadata_mismatch: "Параметры загруженного кадра не совпали с подтверждением.",
    content_review_evidence_total_size_exceeded: "Контрольные кадры слишком велики. Подготовьте их заново.",
    content_review_evidence_storage_object_count_mismatch: "Не все контрольные кадры были загружены.",
    content_review_evidence_manifest_conflict: "Evidence уже подтверждён с другим составом кадров.",
    content_review_evidence_metrics_mismatch: "Технические параметры видео изменились после подтверждения кадров. Используйте восстановленный черновик или начните новую проверку.",
    content_review_evidence_commit_conflict: "Подтверждение evidence изменилось в другой вкладке. Обновите раздел перед повтором.",
    content_review_evidence_not_preparing: "Evidence уже закрыт для изменений. Подготовьте новый набор.",
    content_review_evidence_expired: "Время подготовки кадров истекло. Запустите проверку заново.",
    content_review_run_evidence_bind_invalid: "Не удалось безопасно связать проверку с сохранёнными кадрами.",
    content_review_evidence_already_consumed: "Этот evidence уже использован другой проверкой.",
    content_review_evidence_bind_conflict: "Evidence уже связан с другой проверкой.",
    content_review_video_evidence_invalid: "Сохранённые кадры видео неполны или устарели. Запустите новую проверку.",
    content_review_run_missing: "Сервер не вернул номер проверки. Обновите раздел и повторите.",
    content_review_id_invalid: "Не удалось определить проверку. Обновите раздел.",
    content_review_request_failed: "Сервис проверки временно недоступен. Запуск сохранён — проверьте его статус позже.",
    content_review_response_invalid: "Сервис проверки контента вернул некорректный ответ.",
    content_review_decision_invalid: "Выберите итог проверки: одобрить, доработать или отклонить.",
    content_review_decision_reason_invalid: "Объясните решение текстом от 10 до 2000 символов.",
    content_review_decision_codes_invalid: "Список подтверждений проверки имеет неверный формат.",
    content_review_media_watch_required: "Перед решением полностью просмотрите защищённый файл со звуком и субтитрами.",
    content_review_sound_assessment_required: "После полного прослушивания зафиксируйте отдельную оценку звука.",
    content_review_sound_assessment_invalid: "Оценка звука неполна или имеет неверный формат. Проверьте дикцию и отмеченные ошибки.",
    content_review_sound_assessment_payload_invalid: "Оценка звука неполна или имеет неверный формат. Проверьте дикцию и отмеченные ошибки.",
    content_review_sound_assessment_boolean_invalid: "Подтверждения проверки звука имеют неверный формат. Обновите страницу и повторите оценку.",
    content_review_sound_assessment_value_invalid: "Оценка звука содержит недопустимое значение. Проверьте отметки и заметку.",
    content_review_sound_assessment_conflict: "Для этой точной версии уже сохранена другая оценка звука. Обновите проверку.",
    content_review_sound_issues_block_approval: "Ролик со звуковой ошибкой нельзя одобрить. Верните его на доработку или отклоните.",
    content_review_sound_clear_confirmation_required: "Для чистого звука подтвердите дословную реплику, дикцию, голос и синхронизацию.",
    content_review_sound_clear_invalid: "Для чистого звука подтвердите дословную реплику, дикцию, голос и синхронизацию.",
    content_review_sound_issues_invalid: "Проверьте выбранные типы звуковых ошибок и ожидаемый режим аудио.",
    content_review_sound_issues_note_required: "Опишите найденную звуковую ошибку минимум пятью символами.",
    content_review_sound_silence_invalid: "Для немого режима подтвердите тишину либо зафиксируйте неожиданный звук как ошибку.",
    content_review_sound_audio_mismatch: "Режим звука не совпал с защищёнными данными генерации. Обновите проверку.",
    content_review_sound_spoken_script_provenance_invalid: "Точная реплика не привязана к защищённому заданию генерации. Одобрение заблокировано.",
    content_review_sound_source_invalid: "Защищённый MP4 или завершённая проверка изменились. Обновите статус.",
    content_review_sound_provenance_invalid: "Не удалось подтвердить происхождение звука из точного задания генерации.",
    content_review_sound_decision_invalid: "Оценка звука не совпала с неизменяемым решением. Обновите проверку.",
    content_review_sound_assessment_version_invalid: "Версия формы оценки звука устарела. Обновите портал.",
    content_review_sound_assessment_not_normalized: "Оценка звука изменилась при серверной проверке. Обновите форму и повторите.",
    content_review_sound_assessment_not_applicable: "Оценка звука доступна только для сгенерированного MP4.",
    content_review_sound_lineage_invalid: "Не удалось подтвердить связь оценки звука с этой версией ролика.",
    content_review_sound_context_lineage_invalid: "Контекстная версия ролика потеряла связь с исходной оценкой звука.",
    content_review_sound_recovery_payload_invalid: "Данные восстановления оценки звука неполны. Обновите проверку и заполните форму заново.",
    content_review_sound_recovery_confirmation_required: "Полностью прослушайте точный защищённый MP4 и подтвердите просмотр перед сохранением оценки звука.",
    content_review_sound_recovery_not_allowed: "Добавить пропущенную оценку может только тот же допущенный сотрудник, который сохранил это неизменяемое решение.",
    content_review_sound_recovery_media_not_ready: "Точная версия MP4 больше не активна или изменилась. Восстановление звуковой истории остановлено.",
    content_review_external_ai_processing_required: "Для контрольных кадров с узнаваемыми людьми подтвердите законное основание и необходимое информирование о внешней AI-обработке.",
    external_ai_processing_basis_required: "Для контрольных кадров с узнаваемыми людьми подтвердите законное основание и необходимое информирование о передаче данных внешнему AI-провайдеру.",
    content_review_not_completed: "Решение можно сохранить только после завершения проверки.",
    content_review_already_decided: "По этой версии уже сохранено неизменяемое решение.",
    content_review_approval_blocked: "Одобрение недоступно, пока в результате есть критические блокеры.",
    content_review_media_unavailable: "Выбранный материал недоступен вашей команде.",
    content_review_start_payload_invalid: "Проверьте поля новой проверки и выбранный материал.",
    content_review_input_invalid: "Проверьте площадку, категорию, тексты и подтверждения.",
    content_review_media_not_accessible: "Выбранный материал недоступен вашей роли или уже удалён.",
    content_review_certification_required: "Сначала завершите обучение и итоговый экзамен оператора.",
    content_review_product_category_unverified: "Категория товара ещё не подтверждена руководителем. Попросите владельца или проверяющего классифицировать товар.",
    content_review_product_category_mismatch: "Выбранная категория не совпадает с сохранённой категорией этого товара.",
    content_review_already_active: "Для этого файла уже выполняется проверка. Откройте её в истории.",
    content_review_user_daily_limit: "Дневной лимит проверок для аккаунта исчерпан.",
    content_review_org_daily_limit: "Командный дневной лимит проверок исчерпан.",
    content_review_not_found: "Проверка не найдена или недоступна вашей роли.",
    content_review_not_decidable: "Решение можно сохранить только после завершения проверки.",
    content_review_decision_already_recorded: "По этой версии уже сохранено неизменяемое решение.",
    content_review_blockers_unresolved: "Одобрение недоступно, пока остаются критические блокеры.",
    content_review_risk_acknowledgement_required: "Отметьте риск, который был проверен человеком.",
    risk_acknowledgement_unknown: "Подтверждать можно только риски из текущего неизменяемого результата.",
    resolved_recommendation_code_unknown: "Отмечать исправленными можно только рекомендации из текущего результата.",
    content_review_media_stale: "Файл изменился после проверки. Запустите новую проверку этой версии.",
    high_risk_content_requires_independent_review: "Контент высокого риска должен проверить другой руководитель.",
    content_review_generation_not_succeeded: "Готовый ролик ещё не подтверждён видеосервисом. Обновите генерацию и не принимайте задачу вручную.",
    content_review_approval_evidence_required: "Задачу готового ролика можно завершить только через сохранённое решение в разделе «Проверка контента».",
    generated_video_review_task_invalid: "Задача готового ролика изменилась или уже обработана. Обновите задачи и проверку контента.",
    generated_video_job_invalid: "Готовый файл больше не совпадает с подтверждённым платным запуском. Обновите генерацию и обратитесь к руководителю.",
    generated_video_review_start_payload_invalid: "Запрос запуска AI-проверки ролика устарел. Обновите генерацию.",
    generated_video_review_source_invalid: "Точный MP4 или его evidence изменились. Обновите генерацию и подготовьте кадры заново.",
    generated_video_review_platform_invalid: "Площадка ролика не подходит для безопасного автоматического QA.",
    generated_video_review_category_required: "Категория товара наследуется автоматически из платного запуска. Этот старый запуск сохранён без категории, поэтому один раз подтвердите её в полной форме проверки — дальше портал будет подставлять её сам.",
    generated_video_review_evidence_required: "Сначала дождитесь сохранения пяти evidence-изображений точного MP4.",
    generated_video_transcription_guard_failed: "Проверка остановлена: без отдельного разрешения транскрипция ролика должна оставаться выключенной.",
    generated_video_autopilot_input_invalid: "Сервер не подтвердил происхождение ролика для ускоренного QA. Откройте полную форму проверки.",
    generated_video_autopilot_input_not_bound: "Проверка остановлена: сервер не смог неизменяемо запретить транскрипцию и связать evidence.",
    generated_video_platform_prohibited: "Платную рекламную публикацию на выбранной площадке выпускать нельзя. Выберите разрешённый канал и создайте новое задание.",
    generated_video_review_context_invalid: "Контекст проверки не совпадает с платным заданием: площадка, рекламный статус или AI-происхождение изменились.",
    generated_video_product_context_invalid: "Категория или товар изменились после проверки. Запустите новую проверку из актуальной карточки товара.",
    generated_video_placement_input_invalid: "У платного запуска не подтверждены площадка или точный аккаунт размещения. Исправьте вводные до одобрения.",
    generated_video_context_approval_payload_invalid: "Форма одобрения ролика устарела. Обновите проверку и заполните реквизиты заново.",
    generated_video_context_approval_boolean_invalid: "Одно из подтверждений ролика имеет неверный формат. Обновите страницу.",
    generated_video_context_approval_invalid: "Заполните рекламодателя, ERID, наличие людей и все обязательные подтверждения точного MP4.",
    generated_video_context_source_invalid: "AI-проверка ролика уже обработана или больше не совпадает с точным MP4 и evidence.",
    generated_video_context_platform_invalid: "Для этой площадки, категории или ролика не хватает раскрытия, предупреждения, субтитров либо регистрации канала.",
    generated_video_context_non_context_blockers: "У ролика остались замечания к изображению, звуку или смыслу. Используйте «На доработку» — контекст их не скрывает.",
    generated_video_context_review_not_bound: "Сервер не смог связать реквизиты с точным MP4 и evidence. Решение не сохранено.",
    generated_video_independent_review_required: "Готовый ролик должен принять другой руководитель или проверяющий, не участвовавший в платном запуске.",
    generated_image_review_task_invalid: "Задача товарного фото изменилась или уже обработана. Обновите генерацию и проверку контента.",
    generated_image_job_invalid: "PNG больше не совпадает с подтверждённым платным запуском. Обновите генерацию и обратитесь к руководителю.",
    generated_image_platform_invalid: "Площадка товарного фото не совпадает с разрешённым каналом платного запуска.",
    generated_image_product_invalid: "Товар сгенерированного фото больше недоступен. Обновите карточку товара перед новой проверкой.",
    generated_image_review_requester_invalid: "Проверку сгенерированного фото нужно начать заново из текущего аккаунта.",
    generated_image_independent_review_required: "Сгенерированное фото должен принять другой руководитель или проверяющий, не участвовавший в платном запуске.",
    generated_image_review_context_invalid: "Фото нельзя выпускать по автоматическому черновику. Запустите новую проверку PNG и подтвердите категорию товара, маркировку рекламы, ОРД, ERID, права и обещания.",
    generated_photo_context_approval_payload_invalid: "Форма одобрения фото устарела. Обновите проверку и заполните реквизиты заново.",
    generated_photo_context_approval_boolean_invalid: "Одно из подтверждений фото имеет неверный формат. Обновите страницу.",
    generated_photo_context_approval_invalid: "Заполните категорию, рекламодателя, ERID, наличие людей и все обязательные подтверждения.",
    generated_photo_context_source_invalid: "Автоматическая проверка фото уже обработана или больше не совпадает с платным PNG. Обновите раздел.",
    generated_photo_context_platform_invalid: "Для этой площадки или категории не хватает обязательного раскрытия, предупреждения либо регистрации канала.",
    generated_photo_context_non_context_blockers: "У фото остались замечания к самому содержанию. Используйте «На доработку» — контекст не может скрыть визуальный или смысловой блокер.",
    generated_photo_context_review_not_bound: "Сервер не смог неизменяемо связать рекламный контекст с точным PNG. Решение не сохранено.",
    generation_repair_review_lineage_invalid: "Связь исправления с исходной QA-проверкой изменилась. Новый анализ не запущен: обновите генерацию и проверку контента.",
    generation_repair_review_job_mismatch: "Исправленный файл больше не совпадает с защищённым заданием генерации. Новый анализ не запущен.",
    generation_repair_review_lineage_not_bound: "Сервер не смог связать исправление с точным исходным QA-решением. Новый анализ не запущен.",
    final_url_platform_mismatch: "Финальная ссылка ведёт не на ту площадку, которая указана в задаче размещения.",
    content_review_placement_task_conflict: "Публикационная задача для этого решения уже существует в другом состоянии. Обновите задачи.",
    content_review_placement_conflict: "Публикация для этого решения уже существует в другом состоянии. Обновите раздел публикаций.",
    parent_content_review_invalid: "Предыдущая проверка для сравнения недоступна.",
    parent_content_review_product_mismatch: "Сравнивать можно только версии того же товара.",
    research_source_required: "Добавьте публичную ссылку на товар или точное фото из «Материалов».",
    research_user_daily_limit: "Ваш дневной лимит анализов исчерпан. Новые платные запросы будут доступны после обновления лимита.",
    research_org_daily_limit: "Дневной лимит анализов команды исчерпан. Обратитесь к руководителю.",
    research_media_not_allowed: "Выбранное фото недоступно для анализа. Проверьте формат, права и статус материала.",
    research_run_not_found: "Исследование не найдено. Начните новый разбор.",
    research_run_not_allowed: "У вас нет доступа к этому исследованию.",
    research_run_not_completed: "Анализ ещё не завершён. Сначала обновите его статус.",
    research_watchlist_payload_invalid: "Параметры наблюдения устарели. Обновите раздел и повторите действие.",
    research_watchlist_action_invalid: "Выберите доступное действие: подключить, изменить, поставить на паузу или возобновить.",
    refresh_interval_days_invalid: "Интервал наблюдения должен быть от 3 до 90 дней.",
    approved_research_v2_draft_required: "Для наблюдения нужен утверждённый человеком результат с категорией, конкурентами, трендами и рекомендацией.",
    research_watchlist_use_resume: "Наблюдение уже существует и стоит на паузе. Используйте «Возобновить».",
    research_watchlist_not_found: "Наблюдение для этого товара ещё не подключено.",
    input_validation_failed: "Сервис не смог безопасно прочитать исходные данные. Проверьте товар и начните новый разбор.",
    processing_lease_expired: "Анализ завершён по безопасному таймауту и не будет запущен повторно автоматически. Новый запуск требует отдельного подтверждения.",
    provider_outcome_unknown: "Провайдер мог принять платный запрос, но результат не подтверждён. Автоматического повторного списания нет — перед новым запуском проверьте расходы.",
    source_ids_invalid: "У ТЗ нет подтверждённых источников. Обновите исследование.",
    brief_source_mismatch: "Один из источников больше не относится к этому исследованию. Обновите раздел.",
    task_blueprint_invalid: "Проверьте названия и содержание трёх будущих задач.",
    creative_brief_draft_invalid: "Сначала сохраните актуальный черновик ТЗ.",
    creative_brief_not_latest: "ТЗ уже изменилось в другой вкладке. Обновите раздел перед утверждением.",
    creative_brief_not_approvable: "Этот черновик уже обработан. Обновите раздел.",
    provider_unavailable: "Сервис видео временно недоступен. Повторите проверку позже — новый платный запуск не требуется.",
    invalid_batch_size: "За один раз можно создать от 1 до 50 тестовых вариантов.",
    count_invalid: "За один раз можно создать от 1 до 50 тестовых вариантов.",
    platform_invalid: "Выберите поддерживаемую площадку размещения.",
    format_invalid: "Выберите поддерживаемый формат видео.",
    brief_invalid: "Сократите описание ролика до 1200 символов.",
    exact_product_media_required: "Добавьте и выберите точное фото товара или упаковки из раздела «Материалы».",
    placement_destination_invalid: "Проверьте площадку и точный аккаунт или карточку размещения.",
    payout_minor_invalid: "Проверьте сумму вознаграждения.",
    certified_assignee_required: "Выберите активного участника, который уже сдал итоговый экзамен.",
    payout_role_not_allowed: "Вознаграждение может назначить только руководитель.",
    assignee_role_not_allowed: "Назначать задачу другому участнику может только руководитель.",
    invalid_final_url: "Проверьте публичную ссылку на опубликованный ролик.",
    placement_not_found: "Задача размещения не найдена. Обновите раздел.",
    placement_access_denied: "Эта задача размещения назначена другому участнику.",
    placement_not_publishable: "Публикацию нельзя подтвердить в текущем статусе.",
    placement_already_published: "Для этой публикации уже сохранена другая ссылка на пост.",
    placement_compliance_ack_required: "Подтвердите проверку рекламного статуса и реквизитов из инструкции задачи.",
    placement_compliance_audit_failed: "Не удалось сохранить подтверждение рекламной проверки. Обновите задачу и повторите.",
    published_placement_required: "Сначала подтвердите публикацию и сохраните ссылку на пост.",
    observed_at_in_future: "Время снятия метрик не может быть в будущем.",
    observed_at_before_publication: "Снимок метрик должен быть сделан после публикации.",
    cumulative_metric_regression: "Накопительные метрики не могут быть меньше предыдущего снимка.",
    metric_payload_invalid: "Проверьте значения ручного снимка метрик.",
    tracking_link_payload_invalid: "Не удалось подготовить ссылку учёта.",
    tracking_target_invalid: "Укажите прямую HTTPS-ссылку на товар или лендинг.",
    tracking_placement_not_found: "Публикационная задача для ссылки не найдена.",
    tracking_link_access_denied: "Эта публикация назначена другому участнику.",
    tracking_placement_not_configurable: "Для закрытой публикации нельзя создать новую ссылку.",
    tracking_link_target_immutable: "У этой публикации уже есть ссылка на другой адрес. Создайте новую публикационную задачу.",
    tracking_slug_generation_failed: "Не удалось выпустить безопасную короткую ссылку. Повторите ещё раз.",
    storage_access_denied: "Нет доступа к этой папке раздела «Материалы».",
    storage_object_not_found: "Загруженный файл не найден в защищённом хранилище. Повторите загрузку.",
    media_metadata_invalid: "Проверьте тип, размер и формат файла.",
    media_size_invalid: "Проверьте размер загружаемого файла.",
    media_object_conflict: "Файл с таким путём уже зарегистрирован с другими данными.",
    media_access_denied: "Один из выбранных исходников больше недоступен. Обновите раздел «Материалы».",
    storage_bucket_mismatch: "Защищённое хранилище вернуло неожиданный ответ.",
    invalid_workspace_section: "Этот раздел кабинета недоступен.",
    workspace_section_invalid: "Этот раздел кабинета недоступен.",
    workspace_browser_payload_invalid: "Фильтры рабочего пространства имеют неверный формат.",
    workspace_page_size_invalid: "Можно загрузить от 1 до 100 объектов за один запрос.",
    workspace_search_invalid: "Сократите запрос поиска до 120 символов.",
    workspace_entity_types_invalid: "Выберите материалы, задачи или оба типа объектов.",
    workspace_artifact_classes_invalid: "Выберите корректный фильтр: источники, исследования или созданные результаты.",
    workspace_media_kinds_invalid: "Один из типов материалов больше не поддерживается.",
    workspace_task_statuses_invalid: "Один из статусов задач больше не поддерживается.",
    workspace_cursor_invalid: "Список объектов изменился. Обновите рабочий стол.",
    notification_center_payload_invalid: "Параметры панели уведомлений устарели. Откройте панель заново.",
    notification_center_filter_invalid: "Выберите доступный фильтр уведомлений.",
    notification_center_page_size_invalid: "Можно загрузить от 1 до 100 уведомлений.",
    notification_center_cursor_invalid: "Список уведомлений изменился. Обновите панель.",
    notification_visible_mark_payload_invalid: "Не удалось определить видимые уведомления. Обновите панель.",
    notification_visible_scope_denied: "Список уведомлений изменился. Ничего не отмечено прочитанным; обновите панель.",
    notification_action_validation_payload_invalid: "Точная команда уведомления устарела. Обновите панель.",
    notification_action_intent_invalid: "Точная цель уведомления изменилась. Обновите панель.",
    workspace_folder_create_payload_invalid: "Проверьте название и расположение новой папки.",
    workspace_folder_update_payload_invalid: "Выберите изменение папки и повторите действие.",
    workspace_folder_name_invalid: "Укажите понятное название папки длиной до 120 символов.",
    workspace_folder_color_invalid: "Выберите доступный цвет папки.",
    workspace_folder_name_conflict: "В этой папке уже есть папка с таким названием.",
    workspace_folder_parent_not_found: "Родительская папка больше не существует. Обновите рабочий стол.",
    workspace_folder_not_found: "Папка больше не существует или недоступна.",
    workspace_folder_archived: "Папка уже находится в архиве.",
    workspace_folder_version_invalid: "Папка изменилась. Обновите рабочий стол и повторите действие.",
    workspace_folder_version_conflict: "Папка была изменена в другой вкладке. Обновите рабочий стол.",
    workspace_folder_not_empty: "Перед архивацией переместите из папки все объекты и вложенные папки.",
    workspace_folder_cycle: "Папку нельзя переместить внутрь самой себя.",
    workspace_folder_depth_exceeded: "Достигнута максимальная глубина: восемь уровней папок.",
    workspace_active_folder_quota_exceeded: "В команде уже создано слишком много активных папок.",
    workspace_total_folder_quota_exceeded: "Лимит истории папок исчерпан. Обратитесь к администратору.",
    workspace_position_exhausted: "Не удалось определить порядок объектов. Обновите рабочий стол.",
    workspace_move_payload_invalid: "Не удалось прочитать команду перемещения.",
    workspace_items_invalid: "Выберите от 1 до 100 доступных материалов или задач.",
    workspace_items_duplicate: "Один объект выбран для перемещения несколько раз.",
    workspace_item_access_denied: "Один из выбранных объектов недоступен вашей роли.",
    payout_decision_forbidden: "Решение по выплате доступно только руководителю.",
    self_payout_decision_forbidden: "Собственное начисление должен проверить другой руководитель.",
    payout_rejection_reason_required: "Укажите понятную причину отказа — не меньше 10 символов.",
    external_payment_reference_required: "Укажите номер внешней оплаты.",
    payout_must_be_approved_first: "Сначала одобрите начисление, затем фиксируйте оплату.",
    payout_not_found: "Начисление не найдено. Обновите реестр.",
    payout_not_pending: "Начисление уже обработано. Обновите реестр.",
    payout_already_paid: "Выплата уже подтверждена с другим номером оплаты.",
    payout_already_rejected: "Начисление уже отклонено с другой причиной.",
    wb_alias_forbidden: "Изменять связи артикулов может только уполномоченный участник команды.",
    wb_article_invalid: "Проверьте текущий и подменный артикулы Wildberries.",
    wb_alias_already_assigned: "Этот подменный артикул уже связан с другим товаром.",
    wb_alias_product_immutable: "Существующую связь артикулов нельзя перенести на другой товар.",
    product_not_found: "Товар с таким артикулом не найден. Сначала добавьте товар и его точный исходник.",
    feedback_category_invalid: "Проверьте тип и раздел запроса.",
    task_not_found: "Задача не найдена. Обновите список.",
    task_access_denied: "Эта задача назначена другому участнику.",
    task_transition_not_allowed: "Для текущего статуса это действие недоступно. Обновите список задач.",
    final_exam_rationales_required: "Письменно разберите четыре ключевых кейса итогового экзамена.",
    final_exam_rationale_invalid: "Заполните обоснование по схеме «Риск / Проверка / Действие» своими словами.",
    final_exam_rationales_must_be_unique: "Для каждого ключевого кейса нужно отдельное обоснование.",
    final_exam_rationales_immutable: "Уже отправленные обоснования этой попытки нельзя изменить. Обновите экзамен.",
    idempotency_key_conflict: "Запрос изменился во время повтора. Обновите раздел и выполните действие ещё раз.",
  };

  const matched = Object.keys(known).find((code) => diagnostic.includes(code));
  if (matched) return known[matched];
  if (raw.toLowerCase().includes("function") && raw.toLowerCase().includes("not found")) {
    return "Рабочий сервис ещё не обновлён. Повторите попытку позже или сообщите руководителю.";
  }
  if (/network|fetch|timeout|connection/i.test(raw)) {
    return "Связь прервалась. Проверьте интернет и повторите действие.";
  }
  return "Не удалось выполнить действие. Обновите раздел и попробуйте ещё раз.";
}
