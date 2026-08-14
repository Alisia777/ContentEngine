import { type SupabaseContext, withSupabase } from "npm:@supabase/server@1.3.0";
import {
  INTERNAL_WORKER_HEADER,
  isInternalWorkerAuthorized,
  isInternalWorkerRequest,
} from "../_shared/internal-worker-auth.ts";
import {
  estimateGenerationModelCostMinor,
  GENERATION_MODEL_CATALOG_VERSION,
  GENERATION_MODEL_FEATURE_FLAGS,
  generationModelCatalogEntry,
  GOOGLE_VEO_PRICING_VERSION,
  publicGenerationModelCatalog,
  RUNWAY_PRICING_VERSION,
  validateGenerationModelSelection,
} from "../_shared/generation-model-catalog.js";
import {
  GENERATION_SELECTION_SNAPSHOT_FIELDS,
  readGenerationSelectionSnapshot,
} from "../_shared/generation-selection-snapshot.js";
import {
  buildGenerationProviderRequest,
} from "../_shared/generation-provider-adapters.js";
import {
  estimateGenerationStrategyCredits,
  GENERATION_STRATEGY_CATALOG,
  GENERATION_STRATEGY_CATALOG_VERSION,
  generationStrategyCatalogEntry,
  publicGenerationStrategyCatalog,
  RUNWAY_RECIPE_PRICING_VERSION,
  RUNWAY_RECIPE_VERSION,
  validateGenerationStrategySelection,
} from "../_shared/generation-strategy-catalog.js";
import {
  buildRunwayRecipeRequest,
} from "../_shared/generation-recipe-adapters.js";
import {
  ISO_BMFF_DURATION_PARSER_VERSION,
  ISO_BMFF_MAX_BYTES,
  parseIsoBmffDuration,
} from "../_shared/iso-bmff-duration.js";
import {
  classifyRunwayRecipeCreateOutcome,
  isRunwayTaskId as isStrategyRunwayTaskId,
  preDispatchStrategyFailure,
  publicGenerationStrategyProbeResult,
  readGenerationStrategyDispatchAttempt,
  readGenerationStrategyDispatchResult,
  readGenerationStrategyProbeContext,
  readGenerationStrategyProviderPolicy,
  readGenerationStrategyProviderStatusResult,
  readGenerationStrategyReadiness,
  readGenerationStrategyReconciliationResult,
  readGenerationStrategyStartClaim,
  readPublicGenerationStrategyStatus,
  runwayStrategyProviderStatus,
} from "../_shared/generation-strategy-edge-contract.js";

const PUBLIC_APP_ORIGIN = "https://alisia777.github.io";
const LOCAL_QA_APP_ORIGIN = "http://127.0.0.1:8767";
const USER_APP_ORIGINS = new Set([
  PUBLIC_APP_ORIGIN,
  LOCAL_QA_APP_ORIGIN,
]);
const RUNWAY_API_ORIGIN = "https://api.dev.runwayml.com";
const RUNWAY_API_VERSION = "2024-11-06";
const GOOGLE_GENERATIVE_LANGUAGE_API_ORIGIN =
  "https://generativelanguage.googleapis.com";
const GOOGLE_GENERATIVE_LANGUAGE_API_VERSION = "v1beta";
const GOOGLE_VEO_LITE_MODEL = "veo-3.1-lite-generate-preview";
const GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8";
const PROVIDER_READINESS_RECEIPT_V3 =
  "generation-provider-readiness-receipt-v3";
const PROVIDER_READINESS_RECEIPT_V4 =
  "generation-provider-readiness-receipt-v4";
const RUNWAY_PRODUCT_REFERENCE_TAG = "ProductReference";
const GENERATED_TEXT_GUARD =
  "Без сгенерированных надписей, субтитров и декоративного текста.";
const SEEDANCE_RUSSIAN_DICTION_GUARD =
  "Русская дикция: чётко, без акцента/лишних гласных; все слова/окончания; числа/градусы/названия точно; чёткие паузы.";
const RUNWAY_OUTPUT_HOST = "dnznrvs05pmza.cloudfront.net";
const STORAGE_BUCKET = "contentengine-private";
const MAX_BODY_BYTES = 16_384;
const MAX_PROVIDER_JSON_BYTES = 65_536;
// Google image input is embedded as base64 in the documented REST request.
// Keep the decoded frame and final serialized request bounded separately.
const MAX_GOOGLE_INPUT_IMAGE_BYTES = 8 * 1024 * 1024;
const MAX_GOOGLE_PROVIDER_REQUEST_BYTES = 24 * 1024 * 1024;
const MAX_OUTPUT_BYTES = 52_428_800;
const INPUT_URL_TTL_SECONDS = 3_600;
const OUTPUT_URL_TTL_SECONDS = 300;
const PROVIDER_TIMEOUT_MS = 20_000;
const MIN_PROVIDER_POLL_INTERVAL_MS = 5_000;
const STARTING_RECONCILIATION_AFTER_MS = 90_000;
const RECONCILIATION_TASK_EARLY_SKEW_MS = 2 * 60_000;
const RECONCILIATION_TASK_LATE_SKEW_MS = 10 * 60_000;
// The background worker gives the whole status dispatch 135 seconds. Keep a
// deterministic margin for hashing, the private Storage upload, the database
// success transaction, readback and response serialization after the provider
// poll (20s) and output download have completed.
const OUTPUT_TIMEOUT_MS = 70_000;
const OUTPUT_STORAGE_TIMEOUT_MS = 20_000;
const OUTPUT_DATABASE_TIMEOUT_MS = 5_000;
const OUTPUT_ACCESS_TIMEOUT_MS = 10_000;
const STRATEGY_INPUT_HEAD_TIMEOUT_MS = 10_000;
const STRATEGY_MEDIA_PROBE_TIMEOUT_MS = 70_000;
const STRATEGY_SIGNED_URL_MAX_LENGTH = 2_048;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const TASK_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u;
const GOOGLE_OPERATION_NAME_PATTERN =
  /^models\/veo-3\.1-lite-generate-preview\/operations\/[A-Za-z0-9][A-Za-z0-9._~-]{0,255}$/u;
const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{8,180}$/u;
const LIVE_GENERATION_EXECUTION_KEYS = new Set([
  "runway:gen4_turbo",
  "runway:seedance2_fast",
  "runway:seedream5_lite",
  "runway:gen4.5",
  "runway:seedance2_mini",
  "runway:veo3.1_fast",
  "runway:gemini_omni_flash",
  "google:veo-3.1-lite-generate-preview",
]);
const RUNWAY_PROVIDER_ENDPOINTS = new Set([
  "/v1/image_to_video",
  "/v1/text_to_video",
  "/v1/video_to_video",
  "/v1/text_to_image",
  "/v1/recipes/product_ugc",
  "/v1/recipes/product_swap",
  "/v1/recipes/product_ad",
]);
const SPEC_BOUND_RUNWAY_MODELS: ReadonlySet<string> = new Set([
  "gen4.5",
  "seedance2_mini",
  "veo3.1_fast",
  "gemini_omni_flash",
]);
const RUNWAY_SKU_CONFIG = Object.freeze({
  gen4_turbo: Object.freeze({
    minimumDuration: 2,
    maximumDuration: 10,
    creditsPerSecond: 5,
  }),
  seedance2_fast: Object.freeze({
    minimumDuration: 4,
    maximumDuration: 15,
    creditsPerSecond: 29,
  }),
  seedream5_lite: Object.freeze({
    minimumDuration: 0,
    maximumDuration: 0,
    creditsPerSecond: 0,
    fixedCredits: 4,
  }),
});
const DEFINITIVE_CREATE_HTTP_STATUSES = new Set([
  400,
  401,
  402,
  403,
  404,
  405,
  422,
  429,
]);
const JOB_STATUSES = new Set([
  "queued",
  "starting",
  "submitted",
  "processing",
  "succeeded",
  "failed",
]);
const FAILURE_CODES = new Set([
  "provider_configuration_error",
  "provider_authentication_failed",
  "provider_credits_unavailable",
  "provider_rate_limited",
  "provider_request_rejected",
  "provider_request_failed",
  "provider_task_failed",
  "provider_timeout",
  "provider_response_invalid",
  "provider_submission_not_found",
  "output_download_failed",
  "output_validation_failed",
  "output_upload_failed",
  "output_access_failed",
  "generation_spec_provider_start_stale",
  "internal_error",
]);
const BUDGET_ERROR_CODES: ReadonlySet<string> = new Set([
  "paid_generation_paused",
  "paid_generation_policy_missing",
  "generation_daily_budget_exceeded",
  "generation_monthly_budget_exceeded",
  "generation_per_request_budget_exceeded",
  "generation_budget_reservation_invalid",
  "generation_budget_policy_changed",
  "paid_generation_campaign_required",
  "paid_generation_campaign_not_active",
  "paid_generation_campaign_policy_missing",
  "paid_generation_campaign_paused",
  "generation_campaign_per_request_budget_exceeded",
  "generation_campaign_daily_budget_exceeded",
  "generation_campaign_monthly_budget_exceeded",
  "generation_campaign_budget_policy_changed",
]);
const GENERATION_SPEC_VALIDATION_ERROR_CODES = new Set([
  "project_id_required",
  "workspace_project_not_found",
  "generation_spec_context_invalid",
  "generation_spec_effective_payload_invalid",
  "generation_spec_prepare_payload_invalid",
  "generation_spec_control_payload_invalid",
  "generation_spec_control_version_invalid",
  "generation_spec_status_payload_invalid",
  "generation_spec_exact_scope_invalid",
  "generation_spec_editable_intent_invalid",
  "generation_spec_prompt_invalid",
  "generation_spec_learning_context_invalid",
  "generation_spec_baseline_learning_invalid",
  "generation_spec_research_provenance_invalid",
  "generation_spec_performance_provenance_invalid",
  "generation_spec_repair_provenance_invalid",
  "generation_spec_patch_invalid",
  "generation_spec_revert_invalid",
  "generation_spec_not_found",
  "generation_spec_primary_media_invalid",
  "generation_spec_reference_bundle_invalid",
]);
const GENERATION_SPEC_CONFLICT_ERROR_CODES = new Set([
  "generation_spec_project_scope_mismatch",
  "generation_spec_research_category_rule_stale",
  "generation_spec_approval_required",
  "generation_spec_approval_state_invalid",
  "generation_spec_stale",
  "generation_spec_head_invalid",
  "generation_spec_media_stale",
  "generation_spec_request_mismatch",
  "generation_spec_job_binding_invalid",
  "generation_spec_job_identity_immutable",
  "generation_spec_learning_binding_invalid",
  "generation_spec_repair_binding_invalid",
  "generation_spec_outcome_binding_invalid",
  "generation_spec_provider_start_stale",
  "generation_spec_research_learning_mismatch",
  "generation_spec_research_provenance_stale",
  "generation_spec_performance_learning_mismatch",
  "generation_spec_performance_policy_stale",
  "generation_spec_repair_policy_stale",
  "generation_spec_outcome_selection_stale",
  "generation_spec_outcome_apply_revalidation_required",
  "generation_spec_policy_blocked",
  "generation_spec_previous_version_invalid",
  "generation_spec_version_sequence_invalid",
  "generation_spec_revert_target_invalid",
  "idempotency_key_conflict",
]);
const GENERATION_SPEC_INTERNAL_ERROR_CODES = new Set([
  "project_context_invalid",
  "generation_spec_ledger_append_only",
  "research_outcome_generation_assignment_binding_invalid",
  "research_outcome_generation_assignment_invalid",
]);
const GENERATION_STRATEGY_BIND_VALIDATION_ERROR_CODES = new Set([
  "generation_strategy_resolve_bind_payload_invalid",
  "generation_strategy_binding_payload_invalid",
  "generation_strategy_catalog_selection_invalid",
  "generation_strategy_catalog_attestation_invalid",
  "generation_strategy_catalog_asset_invalid",
  "generation_strategy_catalog_asset_count_invalid",
  "generation_strategy_role_asset_invalid",
  "generation_strategy_snapshot_invalid",
]);
const GENERATION_STRATEGY_BIND_ACCESS_ERROR_CODES = new Set([
  "generation_strategy_binding_project_access_required",
]);
const GENERATION_STRATEGY_BIND_CONFLICT_ERROR_CODES = new Set([
  "generation_strategy_binding_spec_invalid",
  "generation_strategy_binding_spec_not_approved",
  "generation_strategy_catalog_spec_assets_invalid",
  "generation_strategy_exact_source_attachment_required",
  "generation_strategy_source_binding_invalid",
  "generation_strategy_binding_conflict",
  "generation_strategy_binding_invalid",
]);

type BudgetErrorCode =
  | "paid_generation_paused"
  | "paid_generation_policy_missing"
  | "generation_daily_budget_exceeded"
  | "generation_monthly_budget_exceeded"
  | "generation_per_request_budget_exceeded"
  | "generation_budget_reservation_invalid"
  | "generation_budget_policy_changed"
  | "paid_generation_campaign_required"
  | "paid_generation_campaign_not_active"
  | "paid_generation_campaign_policy_missing"
  | "paid_generation_campaign_paused"
  | "generation_campaign_per_request_budget_exceeded"
  | "generation_campaign_daily_budget_exceeded"
  | "generation_campaign_monthly_budget_exceeded"
  | "generation_campaign_budget_policy_changed";

type ClaimErrorCode =
  | BudgetErrorCode
  | "real_generation_reconciliation_required"
  | "generation_spec_provider_start_stale";

type ClaimResult =
  | { outcome: "claimed"; claimed: boolean }
  | {
    outcome: "budget_rejected";
    code: BudgetErrorCode | "real_generation_reconciliation_required";
  }
  | {
    outcome: "terminal_rejected";
    code: "generation_spec_provider_start_stale";
  }
  | { outcome: "unavailable" };

type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

type ContentEngineDatabase = {
  public: {
    Tables: Record<string, never>;
    Views: Record<string, never>;
    Functions: {
      creator_start_real_generation: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_real_generation_status: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_real_generation_reconciliation_context: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_generation_spend_overview: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_generation_provider_policy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_generation_model_feature_flags: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_generation_learning_policy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_generation_repair_policy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_generation_spec_effective_policy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_resolve_and_bind_generation_strategy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_generation_strategy_catalog_policy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_generation_strategy_provider_policy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_generation_strategy_media_probe_context: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_record_generation_strategy_media_duration: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_record_generation_strategy_readiness: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_claim_generation_strategy_start: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_mark_generation_strategy_dispatch_attempt: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_record_generation_strategy_dispatch_result: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_reconcile_generation_strategy_dispatch: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_record_generation_strategy_provider_status: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_generation_strategy_status: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_record_generation_provider_readiness: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_update_real_generation: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_complete_seedream5_lite_photo: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_mark_real_generation_reconciliation_required: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      system_reconcile_real_generation: {
        Args: { p_payload: Json };
        Returns: Json;
      };
    };
  };
  content_factory: {
    Tables: {
      generation_jobs: {
        Row: {
          id: string;
          organization_id: string;
          project_id: string;
          batch_id: string;
          campaign_id: string;
          status: string;
          mode: string;
          provider: string;
          input: Json;
          output: Json;
          estimated_cost_minor: number;
          actual_cost_minor: number | null;
          updated_at: string;
        };
        Insert: Record<string, never>;
        Update: Record<string, never>;
        Relationships: [];
      };
      generation_campaigns: {
        Row: {
          id: string;
          organization_id: string;
          name: string;
        };
        Insert: Record<string, never>;
        Update: Record<string, never>;
        Relationships: [];
      };
      generation_strategy_start_claims: {
        Row: {
          organization_id: string;
          project_id: string;
          actor_id: string;
          generation_job_id: string;
        };
        Insert: Record<string, never>;
        Update: Record<string, never>;
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
  };
};

type ProductCategory =
  | "cosmetics"
  | "baa"
  | "sports_food"
  | "food"
  | "household"
  | "apparel"
  | "electronics"
  | "other";

type GenerationFormat =
  | "21:9"
  | "16:9"
  | "4:3"
  | "3:2"
  | "1:1"
  | "2:3"
  | "3:4"
  | "9:16";

type CommonStartPayload = {
  action: "start";
  organization_id: string;
  project_id: string;
  campaign_id: string;
  idempotency_key: string;
  sku: string;
  product_name: string;
  product_category: ProductCategory;
  count: 1;
  format: GenerationFormat;
  brief: string;
  media_ids: string[];
  platform:
    | "instagram"
    | "tiktok"
    | "youtube"
    | "vk"
    | "telegram"
    | "wildberries";
  destination_ref: string;
  assignee_id?: string;
  payout_minor?: number;
  mode: "real";
  provider: "runway" | "google";
  allow_real_spend: true;
  learning_context: GenerationLearningContext;
  generation_spec_context: GenerationSpecContext;
  generation_reference_context?: GenerationVideoReferenceContext;
  learning_opt_out?: true;
  repair_context?: GenerationRepairContext;
  review_autostart_confirmed?: true;
  review_autostart_terms_version?: "generated-video-qa-autostart-v1";
};

type GenerationVideoReferenceContext = {
  binding_id: string;
  binding_hash: string;
};

type GenerationLearningContext = {
  creative_angle:
    | "product_focus"
    | "trust_builder"
    | "demonstration"
    | "comparison"
    | "objection_handling"
    | "curiosity_gap";
  hook_patterns: (
    | "question_led"
    | "why_explanation"
    | "before_buying"
    | "comparison"
    | "demonstration"
    | "first_person"
    | "numbered"
    | "concise"
  )[];
  source: "baseline" | "approved_research" | "performance_learning";
  compiler_version: string;
  product_category: ProductCategory;
  applied_policy_hash?: string;
  creative_brief_draft_id?: string;
  scenario_position?: 1 | 2 | 3;
};

type GenerationRepairContext = {
  source_review_id: string;
  source_generation_job_id: string;
  guard_codes: (
    | "product_fidelity"
    | "technical_stability"
    | "audio_quality"
    | "speech_fidelity"
    | "hook_clarity"
    | "visual_quality"
    | "trust"
    | "platform_fit"
  )[];
  policy_hash: string;
  compiler_version: "review-repair-v1";
};

type GenerationSpecContext = {
  spec_id: string;
  spec_version: number;
  spec_hash: string;
};

type ExistingRunwayModel = keyof typeof RUNWAY_SKU_CONFIG;
type AdditionalRunwayModel =
  | "gen4.5"
  | "seedance2_mini"
  | "veo3.1_fast"
  | "gemini_omni_flash";
type RunwayModel = ExistingRunwayModel | AdditionalRunwayModel;
type GoogleModel = typeof GOOGLE_VEO_LITE_MODEL;
type GenerationProvider = "runway" | "google";
type GenerationModel = RunwayModel | GoogleModel;
type GenerationResolution =
  | "2K"
  | "3K"
  | "480p"
  | "720p"
  | "1080p"
  | "4K";

type GenerationSpecScope = {
  primary_media_id: string;
  media_ids: string[];
  platform: CommonStartPayload["platform"];
  provider: GenerationProvider;
  model: GenerationModel;
  input_mode: "image";
  duration_seconds: number;
  product_category: ProductCategory;
  format: CommonStartPayload["format"];
  ratio: CommonStartPayload["format"];
  resolution: GenerationResolution;
  audio: boolean;
  spoken_dialogue: boolean;
  reference_count: number;
  reference_video: false;
  first_frame: boolean;
  last_frame: boolean;
};

type GenerationSpecEffectivePolicy = {
  projectId: string;
  generationSpecContext: GenerationSpecContext;
  exactScope: GenerationSpecScope;
  compiledPrompt: string;
  promptHash: string;
  learningContext: GenerationLearningContext;
  repairContext: GenerationRepairContext | null;
  finalPolicyHash: string;
  outcomeSelection: {
    selection_id: string;
    selection_hash: string;
    selection_action: "apply" | "control";
    expires_at: string;
  } | null;
};

type StartPayload = CommonStartPayload & {
  provider: GenerationProvider;
  model: GenerationModel;
  input_mode: "image";
  duration_seconds: number;
  resolution: GenerationResolution;
  audio: boolean;
  last_frame: boolean;
  spend_confirmation: string;
  provider_readiness_receipt_id: string;
  provider_readiness_receipt_hash: string;
  generation_selection_snapshot: Record<string, Json>;
};

type PreflightPayload = {
  action: "preflight";
  organization_id: string;
  provider: GenerationProvider;
  model: GenerationModel;
  input_mode: "image";
  duration_seconds: number;
  format: CommonStartPayload["format"];
  resolution: GenerationResolution;
  audio: boolean;
  last_frame: boolean;
  project_id?: string;
  generation_spec_context?: GenerationSpecContext;
};

type ModelCatalogPayload = {
  action: "model_catalog";
  organization_id: string;
};

type GenerationProviderPolicy = {
  provider: GenerationProvider;
  model: GenerationModel;
  launchEnabled: boolean;
  disabledReasonCode: string | null;
};

type GenerationStrategyId =
  | "viral_avatar_ugc"
  | "viral_product_swap"
  | "viral_rebuild";
type RunwayRecipe = "product_ugc" | "product_swap" | "product_ad";
type GenerationStrategyCatalogPolicy = {
  executionCapabilities: Record<string, unknown>;
  selectEnabled: boolean;
  preflightEnabled: boolean;
};
type GenerationStrategyPayload =
  | {
    ok: true;
    strategyId: GenerationStrategyId;
    recipe: RunwayRecipe;
    selection: Record<string, unknown>;
  }
  | { ok: false };
type GenerationStrategyBindPayload = {
  action: "strategy_bind";
  organization_id: string;
  project_id: string;
  spec_id: string;
  spec_version: number;
  spec_hash: string;
  generation_strategy: Record<string, unknown>;
  confirmation: true;
  idempotency_key: string;
};
type GenerationStrategyMediaProbePayload = {
  action: "strategy_media_probe";
  organization_id: string;
  project_id: string;
  media_id: string;
  confirmation: true;
  idempotency_key: string;
};
type GenerationStrategyPreflightPayload = {
  action: "strategy_preflight";
  organization_id: string;
  project_id: string;
  spec_id: string;
  spec_version: number;
  spec_hash: string;
  binding_id: string;
  binding_hash: string;
  selection_hash: string;
  price_hash: string;
  spend_confirmation: string;
  confirmation: true;
  idempotency_key: string;
};
type GenerationStrategyStartPayload =
  & Omit<
    GenerationStrategyPreflightPayload,
    "action" | "idempotency_key"
  >
  & {
    action: "strategy_start";
    receipt_id: string;
    receipt_hash: string;
    campaign_id: string;
    idempotency_key: string;
  };
type GenerationStrategyStatusPayload = {
  action: "strategy_status";
  organization_id: string;
  project_id: string;
  generation_job_id: string;
  worker_context?: GenerationStrategyWorkerContext;
};
type GenerationStrategyReconcilePayload = {
  action: "strategy_reconcile";
  organization_id: string;
  project_id: string;
  generation_job_id: string;
  dispatch_result_id: string;
  incident_id: string;
  resolution: "attach_existing_task" | "confirm_no_submission";
  provider_task_id?: string;
  confirmation: "RUNWAY_TASK_ID_VERIFIED" | "RUNWAY_NO_TASK_VERIFIED";
  evidence_reference: string;
  reason: string;
  idempotency_key: string;
};
type GenerationStrategyWorkerContext = {
  version: "generation-strategy-worker-dispatch-v1";
  actor_id: string;
  start_claim_id: string;
  claim_hash: string;
  phase: "pre_dispatch" | "dispatch_unknown" | "provider_poll";
  dispatch_attempt_id: string | null;
  attempt_hash: string | null;
  dispatch_token: string | null;
  provider_task_id: string | null;
  lease_id: string;
  lease_token: string;
  lease_hash: string;
};
type GenerationStrategySignedRoleAsset = {
  role:
    | "source_video"
    | "avatar_image"
    | "product_image"
    | "original_product_image"
    | "new_product_image"
    | "style_image";
  uri: string;
  view?: "front" | "side" | "back";
};
type GenerationStrategyRecipeContext = {
  strategyVersion: string;
  strategyId: GenerationStrategyId;
  recipe: RunwayRecipe;
  recipeVersion: string;
  durationSeconds: number;
  audio: boolean;
  ratio?: string;
  resolution?: string;
  productInfo?: string;
  userConcept?: string;
};
type PublicGenerationStrategyCatalogEntry = {
  strategy_id: GenerationStrategyId;
  public_label: string;
  public_summary: string;
  transformation_kind: string;
  source_reference_mode: string;
  preservation_notice: string;
  human_review_required: boolean;
  provider: "runway";
  recipe: RunwayRecipe;
  recipe_version: string;
  asset_roles: unknown[];
  required_attestations: unknown[];
  output_rules: unknown;
  pricing: unknown;
  enabled: boolean;
  disabled_reason: string | null;
};

type GenerationModelFeatureFlags = {
  googleVeoLite: boolean;
  runwayPremium: boolean;
};

type StatusPayload = {
  action: "status";
  organization_id: string;
  project_id: string;
  job_id: string;
};

type ReconcilePayload = {
  action: "reconcile";
  organization_id: string;
  project_id: string;
  job_id: string;
  incident_id: string;
  idempotency_key: string;
  resolution: "attach_existing_task" | "confirm_no_submission";
  provider_task_id?: string;
  evidence_reference: string;
  reason: string;
  confirmation:
    | "RUNWAY_TASK_ID_VERIFIED"
    | "RUNWAY_NO_TASK_VERIFIED"
    | "GOOGLE_OPERATION_ID_VERIFIED"
    | "GOOGLE_NO_OPERATION_VERIFIED";
};

type ReconciliationContext = {
  actorId: string;
  incidentId: string;
  provider: GenerationProvider;
  startingAt: string;
  requiredAt: string;
};

type RunwayProviderReadinessSnapshot = {
  ready: boolean;
  model: RunwayModel;
  durationSeconds: number;
  estimatedCredits: number;
  balanceSufficient: boolean;
  modelAvailable: boolean;
  dailyQuotaAvailable: boolean;
};

type RunwayProviderReadiness =
  | (RunwayProviderReadinessSnapshot & {
    ready: true;
    balanceSufficient: true;
    modelAvailable: true;
    dailyQuotaAvailable: true;
  })
  | {
    ready: false;
    model: RunwayModel;
    durationSeconds: number;
    estimatedCredits: number;
    balanceSufficient: boolean;
    modelAvailable: boolean;
    dailyQuotaAvailable: boolean;
    failureCode: string;
  };

type ProviderReadiness = {
  ready: boolean;
  provider: GenerationProvider;
  model: GenerationModel;
  inputMode: "image";
  durationSeconds: number;
  format: CommonStartPayload["format"];
  resolution: GenerationResolution;
  audio: boolean;
  lastFrame: boolean;
  estimatedCostMinor: number;
  estimatedCredits: number | null;
  credentialConfigured: boolean;
  balanceSufficient: boolean | null;
  modelAvailable: boolean;
  dailyQuotaAvailable: boolean | null;
  spendConfirmation: string;
  failureCode?: string;
};

type ProviderReadinessReceipt = {
  version:
    | typeof PROVIDER_READINESS_RECEIPT_V3
    | typeof PROVIDER_READINESS_RECEIPT_V4;
  receiptId: string;
  receiptHash: string;
  checkedBy: string;
  checkedAt: string;
  expiresAt: string;
  projectId?: string;
  specId?: string;
  specVersion?: number;
  specHash?: string;
  scopeHash?: string;
};

type ProviderReadinessRecordResult = {
  receipt: ProviderReadinessReceipt | null;
  errorCode: "generation_spec_baseline_required" | null;
};

type StartJob = {
  id: string;
  batchId: string;
  campaignId: string;
  campaignName: string;
  status: string;
  provider: GenerationProvider;
  model: GenerationModel;
  inputMode: "image";
  durationSeconds: number;
  resolution: GenerationResolution;
  audio: boolean;
  lastFrame: boolean;
  ratio: string;
  promptText: string;
  inputObjectName: string;
  referenceObjectNames: string[];
  outputObjectName: string;
  estimatedCostMinor: number;
  estimatedCredits: number | null;
  reviewAutostartConfirmed: boolean;
  reviewAutostartTermsVersion: string | null;
};

type StatusJob = {
  id: string;
  batchId: string;
  campaignId: string;
  campaignName: string;
  status: string;
  provider: GenerationProvider;
  providerTaskId: string | null;
  model: GenerationModel;
  inputMode: "image";
  durationSeconds: number;
  resolution: GenerationResolution;
  audio: boolean;
  lastFrame: boolean;
  ratio: string;
  estimatedCostMinor: number;
  estimatedCredits: number | null;
  actualCostMinor: number | null;
  outputObjectName: string;
  outputMediaId: string | null;
  failureCode: string | null;
  submissionState: string | null;
  reconciliationRequired: boolean;
  reconciliationIncidentId: string | null;
  reconciliationRequiredAt: string | null;
  reconciliationReasonCode: string | null;
  reconciliationResolution: string | null;
  canReconcile: boolean;
  reviewAutostartConfirmed: boolean;
  reviewAutostartTermsVersion: string | null;
  updatedAt: string;
};

type SafeJob = {
  id: string;
  batch_id: string;
  campaign_id: string;
  campaign_name: string;
  status: string;
  provider: GenerationProvider;
  provider_task_id: string | null;
  model: GenerationModel;
  input_mode: "image";
  duration_seconds: number;
  resolution: GenerationResolution;
  audio: boolean;
  last_frame: boolean;
  ratio: string;
  estimated_cost_minor: number;
  estimated_credits: number | null;
  actual_cost_minor: number | null;
  output_object_name: string;
  output_media_id: string | null;
  failure_code: string | null;
  submission_state: string | null;
  reconciliation_required: boolean;
  reconciliation_incident_id: string | null;
  reconciliation_required_at: string | null;
  reconciliation_reason_code: string | null;
  reconciliation_resolution: string | null;
  can_reconcile: boolean;
  review_autostart_confirmed: boolean;
  review_autostart_terms_version: string | null;
  updated_at: string;
};

function responseHeaders(request: Request): Headers {
  const headers = new Headers({
    "access-control-allow-headers":
      "authorization, apikey, content-type, x-client-info",
    "access-control-allow-methods": "POST, OPTIONS",
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    vary: "Origin",
    "x-contentengine-learning-gate": GENERATION_LEARNING_GATE_VERSION,
    "x-content-type-options": "nosniff",
  });
  const origin = request.headers.get("origin");
  if (origin !== null && USER_APP_ORIGINS.has(origin)) {
    headers.set("access-control-allow-origin", origin);
  }
  return headers;
}

function json(request: Request, body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: responseHeaders(request),
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readBudgetErrorCode(value: unknown): BudgetErrorCode | null {
  if (!isRecord(value) || typeof value.message !== "string") return null;
  return BUDGET_ERROR_CODES.has(value.message)
    ? value.message as BudgetErrorCode
    : null;
}

function readSafeStartRpcErrorCode(value: unknown): string | null {
  if (!isRecord(value) || typeof value.message !== "string") return null;
  const code = value.message.trim();
  return /^(?:(?:real_|paid_)?generation|idempotency|product_reference|exact_product|media|brief|format|platform|payout|assignee|certified_assignee)_[a-z0-9_]{2,95}$/u
      .test(code)
    ? code
    : null;
}

function readGenerationSpecRpcError(value: unknown): {
  code: string;
  status: 409 | 422;
  internal: boolean;
} | null {
  if (!isRecord(value) || typeof value.message !== "string") return null;
  const code = value.message.trim();
  if (GENERATION_SPEC_VALIDATION_ERROR_CODES.has(code)) {
    return { code, status: 422, internal: false };
  }
  if (GENERATION_SPEC_CONFLICT_ERROR_CODES.has(code)) {
    return { code, status: 409, internal: false };
  }
  if (GENERATION_SPEC_INTERNAL_ERROR_CODES.has(code)) {
    return {
      code: "generation_spec_state_conflict",
      status: 409,
      internal: true,
    };
  }
  return null;
}

function readGenerationStrategyBindRpcError(value: unknown): {
  code: string;
  status: 403 | 409 | 422;
} | null {
  if (!isRecord(value) || typeof value.message !== "string") return null;
  const code = value.message.trim();
  if (GENERATION_STRATEGY_BIND_VALIDATION_ERROR_CODES.has(code)) {
    return { code, status: 422 };
  }
  if (GENERATION_STRATEGY_BIND_ACCESS_ERROR_CODES.has(code)) {
    return { code, status: 403 };
  }
  if (GENERATION_STRATEGY_BIND_CONFLICT_ERROR_CODES.has(code)) {
    return { code, status: 409 };
  }
  return null;
}

function readClaimErrorCode(value: unknown): ClaimErrorCode | null {
  if (!isRecord(value)) return null;
  const code = typeof value.message === "string"
    ? value.message
    : typeof value.code === "string"
    ? value.code
    : null;
  if (code === null) return null;
  const budgetCode = readBudgetErrorCode({ message: code });
  if (budgetCode !== null) return budgetCode;
  if (code === "real_generation_reconciliation_required") return code;
  return code === "generation_spec_provider_start_stale" ? code : null;
}

function readTerminalClaimErrorCode(
  value: unknown,
  jobId: string,
): "generation_spec_provider_start_stale" | null {
  const keys = new Set([
    "ok",
    "claimed",
    "terminal",
    "code",
    "retryable",
    "job",
  ]);
  const jobKeys = new Set([
    "id",
    "batch_id",
    "status",
    "provider",
    "failure_code",
    "updated_at",
  ]);
  if (
    !isRecord(value) || !hasOnlyKeys(value, keys) ||
    Object.keys(value).length !== keys.size || value.ok !== false ||
    value.claimed !== false || value.terminal !== true ||
    value.retryable !== false || !isRecord(value.job)
  ) {
    return null;
  }
  const code = readClaimErrorCode(value);
  const job = value.job;
  if (
    code !== "generation_spec_provider_start_stale" ||
    !hasOnlyKeys(job, jobKeys) || Object.keys(job).length !== jobKeys.size ||
    job.id !== jobId || !isUuid(job.id) || !isUuid(job.batch_id) ||
    job.status !== "failed" || readGenerationProvider(job.provider) === null ||
    job.failure_code !== code || typeof job.updated_at !== "string" ||
    !Number.isFinite(Date.parse(job.updated_at))
  ) {
    return null;
  }
  return code;
}

function budgetErrorHttpStatus(code: BudgetErrorCode): 403 | 409 {
  return code === "paid_generation_paused" ||
      code === "paid_generation_policy_missing" ||
      code === "paid_generation_campaign_required" ||
      code === "paid_generation_campaign_not_active" ||
      code === "paid_generation_campaign_policy_missing" ||
      code === "paid_generation_campaign_paused"
    ? 403
    : 409;
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowed: ReadonlySet<string>,
): boolean {
  return Object.keys(value).every((key) => allowed.has(key));
}

function hasExactKeys(
  value: unknown,
  keys: readonly string[],
): value is Record<string, unknown> {
  if (!isRecord(value)) return false;
  const allowed = new Set(keys);
  return Object.keys(value).length === allowed.size &&
    hasOnlyKeys(value, allowed);
}

function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_PATTERN.test(value);
}

function isIntegerInRange(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return Number.isSafeInteger(value) &&
    (value as number) >= minimum && (value as number) <= maximum;
}

function hasForbiddenControl(
  value: string,
  allowTextWhitespace: boolean,
): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code === 0x7f) return true;
    if (code <= 0x1f) {
      const allowed = allowTextWhitespace &&
        (code === 0x09 || code === 0x0a || code === 0x0d);
      if (!allowed) return true;
    }
  }
  return false;
}

function isBoundedText(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string {
  return typeof value === "string" && value === value.trim() &&
    value.length >= minimum && value.length <= maximum &&
    !hasForbiddenControl(value, true);
}

function isObjectName(value: unknown): value is string {
  if (!isBoundedText(value, 3, 1_024)) return false;
  if (value.startsWith("/") || value.endsWith("/")) return false;
  if (value.includes("?") || value.includes("#") || value.includes("\\")) {
    return false;
  }
  return value.split("/").every((part) =>
    part.length > 0 && part !== "." && part !== ".."
  );
}

function readRunwayModel(value: unknown): RunwayModel | null {
  return value === "gen4_turbo" ||
      value === "seedance2_fast" ||
      value === "seedream5_lite" ||
      value === "gen4.5" ||
      value === "seedance2_mini" ||
      value === "veo3.1_fast" ||
      value === "gemini_omni_flash"
    ? value
    : null;
}

function readProviderReadinessRpcErrorCode(
  value: unknown,
): "generation_spec_baseline_required" | null {
  if (!isRecord(value) || typeof value.message !== "string") return null;
  return value.message.trim() === "generation_multimodel_baseline_required"
    ? "generation_spec_baseline_required"
    : null;
}

function readGenerationProvider(value: unknown): GenerationProvider | null {
  return value === "runway" || value === "google" ? value : null;
}

function readGenerationModel(
  provider: GenerationProvider | null,
  value: unknown,
): GenerationModel | null {
  if (provider === "runway") return readRunwayModel(value);
  return provider === "google" && value === GOOGLE_VEO_LITE_MODEL
    ? value
    : null;
}

function generationModelRequiresReadinessV4(
  provider: GenerationProvider,
  model: GenerationModel,
): boolean {
  return provider === "runway" && SPEC_BOUND_RUNWAY_MODELS.has(model);
}

function generationProviderForModel(
  model: GenerationModel,
): GenerationProvider {
  return model === GOOGLE_VEO_LITE_MODEL ? "google" : "runway";
}

function generationCatalogEntryForModel(model: GenerationModel) {
  return generationModelCatalogEntry(
    generationProviderForModel(model),
    model,
  );
}

function generationModelSupportsAudio(model: GenerationModel): boolean {
  return generationCatalogEntryForModel(model)?.supportsGeneratedAudio === true;
}

function readRunwayGenerationSku(
  model: ExistingRunwayModel,
  durationSeconds: unknown,
): {
  model: ExistingRunwayModel;
  durationSeconds: number;
  estimatedCredits: number;
  estimatedUsd: string;
  confirmation: string;
} | null {
  const duration = Number(durationSeconds);
  const config = RUNWAY_SKU_CONFIG[model];
  if (
    !Number.isInteger(duration) ||
    duration < config.minimumDuration ||
    duration > config.maximumDuration
  ) return null;
  if (model === "seedream5_lite") {
    return duration === 0
      ? {
        model,
        durationSeconds: 0,
        estimatedCredits: 4,
        estimatedUsd: "0.04",
        confirmation: "RUNWAY_SEEDREAM5_LITE_2K_USD_0.04",
      }
      : null;
  }
  const estimatedCredits = duration * config.creditsPerSecond;
  const estimatedUsd = (estimatedCredits / 100).toFixed(2);
  return {
    model,
    durationSeconds: duration,
    estimatedCredits,
    estimatedUsd,
    confirmation: model === "seedance2_fast"
      ? `RUNWAY_SEEDANCE2_FAST_${duration}S_AUDIO_USD_${estimatedUsd}`
      : `RUNWAY_GEN4_TURBO_${duration}S_USD_${estimatedUsd}`,
  };
}

function seedanceSpokenWordLimit(durationSeconds: number): number {
  return Math.max(10, Math.min(42, Math.floor(durationSeconds * 22 / 8)));
}

function countPromptWords(value: string): number {
  return value.match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu)?.length || 0;
}

function generationModePromptIsBound(payload: StartPayload): boolean {
  const commonRequirements = [
    `Точный товар: ${payload.product_name}, артикул ${payload.sku}.`,
    "Сохрани форму, цвет, упаковку, этикетку и пропорции без изменений.",
    "Не добавляй новые свойства, результаты, медицинские обещания, логотипы, текст на упаковке или другой вариант товара.",
  ];
  const silentVideoRequirements = [
    `Создай один непрерывный ролик длительностью ${payload.duration_seconds} секунд с соотношением сторон ${payload.format}.`,
    "Без речи, дикторского текста и сгенерированных надписей.",
  ];
  const audioVideoRequirements = [
    `Создай один непрерывный UGC-ролик длительностью ${payload.duration_seconds} секунд с соотношением сторон ${payload.format}.`,
    GENERATED_TEXT_GUARD,
  ];
  const modelRequirements: Record<GenerationModel, string[]> = {
    seedream5_lite: [
      "Создай одно квадратное товарное фото 2048 × 2048.",
      `Используй @${RUNWAY_PRODUCT_REFERENCE_TAG} как главный точный референс товара; остальные выбранные ракурсы уточняют форму и детали.`,
      "Без бейджей, декоративного текста, рук, людей, реквизита и других товаров. Не перерисовывай текст и логотип референса.",
    ],
    gen4_turbo: [
      `Создай один непрерывный вертикальный ролик длительностью ${payload.duration_seconds} секунд.`,
      "Без речи, дикторского текста и сгенерированных надписей.",
    ],
    seedance2_fast: [
      `Создай один непрерывный вертикальный UGC-ролик длительностью ${payload.duration_seconds} секунд.`,
      GENERATED_TEXT_GUARD,
    ],
    "gen4.5": silentVideoRequirements,
    seedance2_mini: audioVideoRequirements,
    "veo3.1_fast": payload.audio
      ? audioVideoRequirements
      : silentVideoRequirements,
    gemini_omni_flash: audioVideoRequirements,
    "veo-3.1-lite-generate-preview": audioVideoRequirements,
  };
  if (
    payload.model !== "seedream5_lite" &&
    !payload.brief.includes(productInteractionRequirement(
      payload.product_name,
      payload.product_category,
    ))
  ) return false;
  if (
    [...commonRequirements, ...modelRequirements[payload.model]].some(
      (requirement) => !payload.brief.includes(requirement),
    )
  ) return false;
  const spokenMatch = /Реплика героя дословно:\s*«([^»]+)»/u.exec(
    payload.brief,
  );
  if (payload.audio) {
    if (spokenMatch === null || spokenMatch[1].includes("[СОКРАТИТЕ")) {
      return false;
    }
    if (
      /\p{Script=Cyrillic}/u.test(spokenMatch[1]) &&
      !payload.brief.includes(SEEDANCE_RUSSIAN_DICTION_GUARD)
    ) return false;
    const spokenWords = countPromptWords(spokenMatch[1]);
    return spokenWords >= 1 &&
      spokenWords <= seedanceSpokenWordLimit(payload.duration_seconds);
  }
  return spokenMatch === null;
}

function productInteractionRequirement(
  productName: string,
  productCategory: CommonStartPayload["product_category"],
): string {
  const normalizedName = productName.trim().toLocaleLowerCase("ru-RU");
  if (
    /(?:пароварк|мультиварк|аэрогрил|духовк|микроволнов|кофемашин|кофеварк|электрогрил|тостер|соковыжимал|хлебопеч|кухонн\p{L}*\s+комбайн|стационарн\p{L}*\s+блендер|steamer|air\s*fryer|microwave|coffee\s*machine|countertop\s*appliance)/iu
      .test(normalizedName)
  ) {
    return "Масштаб и действие: товар показан целиком в естественном размере на устойчивой столешнице; герой взаимодействует с крышкой, панелью управления и готовым результатом.";
  }
  if (
    /(?:холодильник|морозильник|стиральн\p{L}*\s+машин|сушильн\p{L}*\s+машин|посудомоеч|телевизор|матрас|диван|кресл|стол\b|шкаф|комод|пылесос|кондиционер|обогревател|велосипед|самокат|коляск|refrigerator|washing\s*machine|dishwasher|television|mattress|sofa|wardrobe|vacuum)/iu
      .test(normalizedName)
  ) {
    return "Масштаб и действие: товар показан целиком в естественном размере на месте использования; герой взаимодействует с управлением или рабочей частью.";
  }
  const requirements: Record<CommonStartPayload["product_category"], string> = {
    cosmetics:
      "Масштаб и действие: точная упаковка показана на столе или в руках на уровне корпуса; в кадре только дозатор, текстура и подтверждённые детали без демонстрации эффекта на лице.",
    baa:
      "Масштаб и действие: упаковка БАДа показана целиком на столе; в кадре этикетка и форма выпуска без сцены приёма и медицинских обещаний.",
    sports_food:
      "Масштаб и действие: точная упаковка спортивного питания показана на столе рядом с мерной порцией; в кадре только продукт и подтверждённые детали этикетки.",
    food:
      "Масштаб и действие: точная упаковка еды или напитка показана на столе рядом с естественной порцией; камера показывает фактуру без выдуманных свойств.",
    household:
      "Масштаб и действие: товар для дома показан целиком в естественном размере на устойчивой поверхности; герой демонстрирует одну видимую рабочую часть и понятное безопасное действие.",
    apparel:
      "Масштаб и действие: товар показан надетым или разложенным в естественном масштабе; камера переходит от общего вида к материалу и деталям.",
    electronics:
      "Масштаб и действие: устройство показано целиком на столе или рабочем месте; камера переходит к интерфейсу, управлению и видимым разъёмам без выдуманных функций.",
    other:
      "Масштаб и действие: товар целиком в естественном масштабе на устойчивой поверхности; камера показывает только видимые детали.",
  };
  return requirements[productCategory];
}

function readStartPayload(value: unknown): StartPayload | null {
  if (!isRecord(value)) return null;
  const required = new Set([
    "action",
    "organization_id",
    "project_id",
    "campaign_id",
    "idempotency_key",
    "sku",
    "product_name",
    "product_category",
    "count",
    "format",
    "brief",
    "media_ids",
    "platform",
    "destination_ref",
    "mode",
    "provider",
    "model",
    "input_mode",
    "duration_seconds",
    "resolution",
    "audio",
    "last_frame",
    "allow_real_spend",
    "spend_confirmation",
    "provider_readiness_receipt_id",
    "provider_readiness_receipt_hash",
    "generation_selection_snapshot",
    "learning_context",
    "generation_spec_context",
  ]);
  const allowed = new Set([
    ...required,
    "assignee_id",
    "payout_minor",
    "learning_opt_out",
    "repair_context",
    "review_autostart_confirmed",
    "review_autostart_terms_version",
    "generation_reference_context",
  ]);
  if (!hasOnlyKeys(value, allowed)) return null;
  if (![...required].every((key) => Object.hasOwn(value, key))) return null;

  const mediaIds = value.media_ids;
  const provider = readGenerationProvider(value.provider);
  const model = readGenerationModel(provider, value.model);
  const reviewAutostartKeyPresent =
    Object.hasOwn(value, "review_autostart_confirmed") ||
    Object.hasOwn(value, "review_autostart_terms_version");
  const promptLimit = provider === null || model === null
    ? 0
    : Number(generationModelCatalogEntry(provider, model)?.promptLimit || 0);
  if (
    !Array.isArray(mediaIds) ||
    mediaIds.length < 1 ||
    mediaIds.length > 5 ||
    mediaIds.some((mediaId) => !isUuid(mediaId)) ||
    new Set(mediaIds).size !== mediaIds.length
  ) {
    return null;
  }
  const platforms = new Set([
    "instagram",
    "tiktok",
    "youtube",
    "vk",
    "telegram",
    "wildberries",
  ]);
  const productCategories = new Set([
    "cosmetics",
    "baa",
    "sports_food",
    "food",
    "household",
    "apparel",
    "electronics",
    "other",
  ]);
  if (
    value.action !== "start" ||
    !isUuid(value.organization_id) ||
    !isUuid(value.campaign_id) ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key) ||
    !isBoundedText(value.sku, 1, 120) ||
    !isBoundedText(value.product_name, 2, 180) ||
    typeof value.product_category !== "string" ||
    !productCategories.has(value.product_category) ||
    value.count !== 1 ||
    typeof value.format !== "string" ||
    !isBoundedText(value.brief, 1, promptLimit) ||
    typeof value.platform !== "string" || !platforms.has(value.platform) ||
    !isBoundedText(value.destination_ref, 2, 240) ||
    value.mode !== "real" || value.input_mode !== "image" ||
    provider === null || model === null ||
    !isIntegerInRange(value.duration_seconds, 0, 15) ||
    typeof value.resolution !== "string" ||
    typeof value.audio !== "boolean" ||
    typeof value.last_frame !== "boolean" ||
    value.allow_real_spend !== true ||
    !isBoundedText(value.spend_confirmation, 8, 180)
  ) {
    return null;
  }
  if (
    reviewAutostartKeyPresent &&
    (
      model === "seedream5_lite" ||
      value.review_autostart_confirmed !== true ||
      value.review_autostart_terms_version !==
        "generated-video-qa-autostart-v1"
    )
  ) {
    return null;
  }
  if (
    !isUuid(value.provider_readiness_receipt_id) ||
    typeof value.provider_readiness_receipt_hash !== "string" ||
    !SHA256_PATTERN.test(value.provider_readiness_receipt_hash) ||
    !isRecord(value.generation_selection_snapshot)
  ) return null;
  if (Object.hasOwn(value, "assignee_id") && !isUuid(value.assignee_id)) {
    return null;
  }
  if (!isUuid(value.project_id)) {
    return null;
  }
  if (
    Object.hasOwn(value, "payout_minor") &&
    !isIntegerInRange(value.payout_minor, 0, 1_000_000)
  ) {
    return null;
  }
  const learningContext = readGenerationLearningContext(value.learning_context);
  if (learningContext === null) {
    return null;
  }
  if (readGenerationSpecContext(value.generation_spec_context) === null) {
    return null;
  }
  if (
    Object.hasOwn(value, "generation_reference_context") &&
    readGenerationVideoReferenceContext(
        value.generation_reference_context,
      ) === null
  ) return null;
  if (
    Object.hasOwn(value, "learning_opt_out") &&
    (
      value.learning_opt_out !== true ||
      learningContext.source === "performance_learning"
    )
  ) {
    return null;
  }
  if (
    Object.hasOwn(value, "repair_context") &&
    readGenerationRepairContext(value.repair_context) === null
  ) {
    return null;
  }
  return value as StartPayload;
}

function readPreflightPayload(value: unknown): PreflightPayload | null {
  if (!isRecord(value)) return null;
  const baseKeys = [
    "action",
    "organization_id",
    "provider",
    "model",
    "input_mode",
    "duration_seconds",
    "format",
    "resolution",
    "audio",
    "last_frame",
  ];
  const provider = readGenerationProvider(value.provider);
  const model = readGenerationModel(provider, value.model);
  if (provider === null || model === null) return null;
  const requiresSpec = generationModelRequiresReadinessV4(provider, model);
  const allowed = new Set([
    ...baseKeys,
    ...(requiresSpec ? ["project_id", "generation_spec_context"] : []),
  ]);
  const specContext = requiresSpec
    ? readGenerationSpecContext(value.generation_spec_context)
    : null;
  if (
    !hasOnlyKeys(value, allowed) ||
    Object.keys(value).length !== allowed.size ||
    value.action !== "preflight" ||
    !isUuid(value.organization_id) ||
    value.input_mode !== "image" ||
    !isIntegerInRange(value.duration_seconds, 0, 15) ||
    typeof value.format !== "string" ||
    typeof value.resolution !== "string" ||
    typeof value.audio !== "boolean" ||
    typeof value.last_frame !== "boolean" ||
    (requiresSpec && (!isUuid(value.project_id) || specContext === null))
  ) {
    return null;
  }
  return {
    action: "preflight",
    organization_id: value.organization_id,
    provider,
    model,
    input_mode: "image",
    duration_seconds: value.duration_seconds,
    format: value.format as CommonStartPayload["format"],
    resolution: value.resolution as GenerationResolution,
    audio: value.audio,
    last_frame: value.last_frame,
    ...(requiresSpec
      ? {
        project_id: value.project_id as string,
        generation_spec_context: specContext as GenerationSpecContext,
      }
      : {}),
  };
}

function readModelCatalogPayload(value: unknown): ModelCatalogPayload | null {
  if (!isRecord(value)) return null;
  const keys = new Set(["action", "organization_id"]);
  if (
    !hasOnlyKeys(value, keys) ||
    Object.keys(value).length !== keys.size ||
    value.action !== "model_catalog" ||
    !isUuid(value.organization_id)
  ) return null;
  return {
    action: "model_catalog",
    organization_id: value.organization_id,
  };
}

function readGenerationStrategyId(value: unknown): GenerationStrategyId | null {
  return value === "viral_avatar_ugc" || value === "viral_product_swap" ||
      value === "viral_rebuild"
    ? value
    : null;
}

function readRunwayRecipe(value: unknown): RunwayRecipe | null {
  return value === "product_ugc" || value === "product_swap" ||
      value === "product_ad"
    ? value
    : null;
}

function readGenerationStrategyBindPayload(
  value: unknown,
): GenerationStrategyBindPayload | null {
  const keys = [
    "action",
    "organization_id",
    "project_id",
    "spec_id",
    "spec_version",
    "spec_hash",
    "generation_strategy",
    "confirmation",
    "idempotency_key",
  ] as const;
  if (
    !hasExactKeys(value, keys) || value.action !== "strategy_bind" ||
    !isUuid(value.organization_id) || !isUuid(value.project_id) ||
    !isUuid(value.spec_id) ||
    !isIntegerInRange(value.spec_version, 1, 100_000) ||
    typeof value.spec_hash !== "string" ||
    !SHA256_PATTERN.test(value.spec_hash) || value.confirmation !== true ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key) ||
    !isRecord(value.generation_strategy)
  ) return null;
  const validated = validateGenerationStrategySelection(
    value.generation_strategy,
  );
  if (!isRecord(validated) || validated.ok !== true) return null;
  const strategyId = readGenerationStrategyId(validated.strategy_id);
  const recipe = readRunwayRecipe(validated.recipe);
  const entry = strategyId === null
    ? null
    : generationStrategyCatalogEntry(strategyId);
  if (
    strategyId === null || recipe === null || entry === null ||
    entry.provider !== "runway" || entry.recipe !== recipe ||
    entry.recipe_version !== value.generation_strategy.recipe_version
  ) return null;
  return {
    action: "strategy_bind",
    organization_id: value.organization_id,
    project_id: value.project_id,
    spec_id: value.spec_id,
    spec_version: value.spec_version,
    spec_hash: value.spec_hash,
    generation_strategy: value.generation_strategy,
    confirmation: true,
    idempotency_key: value.idempotency_key,
  };
}

function readGenerationStrategyMediaProbePayload(
  value: unknown,
): GenerationStrategyMediaProbePayload | null {
  const keys = [
    "action",
    "organization_id",
    "project_id",
    "media_id",
    "confirmation",
    "idempotency_key",
  ] as const;
  if (
    !hasExactKeys(value, keys) ||
    value.action !== "strategy_media_probe" ||
    !isUuid(value.organization_id) || !isUuid(value.project_id) ||
    !isUuid(value.media_id) || value.confirmation !== true ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key)
  ) return null;
  return value as GenerationStrategyMediaProbePayload;
}

function readGenerationStrategyPreflightPayload(
  value: unknown,
): GenerationStrategyPreflightPayload | null {
  const keys = [
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
  ] as const;
  if (
    !hasExactKeys(value, keys) || value.action !== "strategy_preflight" ||
    !isUuid(value.organization_id) || !isUuid(value.project_id) ||
    !isUuid(value.spec_id) ||
    !isIntegerInRange(value.spec_version, 1, 100_000) ||
    typeof value.spec_hash !== "string" ||
    !SHA256_PATTERN.test(value.spec_hash) || !isUuid(value.binding_id) ||
    typeof value.binding_hash !== "string" ||
    !SHA256_PATTERN.test(value.binding_hash) ||
    typeof value.selection_hash !== "string" ||
    !SHA256_PATTERN.test(value.selection_hash) ||
    typeof value.price_hash !== "string" ||
    !SHA256_PATTERN.test(value.price_hash) ||
    typeof value.spend_confirmation !== "string" ||
    readStrategySpendConfirmation(value.spend_confirmation) === null ||
    value.confirmation !== true ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key)
  ) return null;
  return value as GenerationStrategyPreflightPayload;
}

function readGenerationStrategyStartPayload(
  value: unknown,
): GenerationStrategyStartPayload | null {
  const keys = [
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
  ] as const;
  if (!hasExactKeys(value, keys) || value.action !== "strategy_start") {
    return null;
  }
  const preflight = readGenerationStrategyPreflightPayload({
    action: "strategy_preflight",
    organization_id: value.organization_id,
    project_id: value.project_id,
    spec_id: value.spec_id,
    spec_version: value.spec_version,
    spec_hash: value.spec_hash,
    binding_id: value.binding_id,
    binding_hash: value.binding_hash,
    selection_hash: value.selection_hash,
    price_hash: value.price_hash,
    spend_confirmation: value.spend_confirmation,
    confirmation: value.confirmation,
    idempotency_key: value.idempotency_key,
  });
  if (
    preflight === null || !isUuid(value.receipt_id) ||
    typeof value.receipt_hash !== "string" ||
    !SHA256_PATTERN.test(value.receipt_hash) || !isUuid(value.campaign_id)
  ) return null;
  return value as GenerationStrategyStartPayload;
}

function readGenerationStrategyWorkerContext(
  value: unknown,
): GenerationStrategyWorkerContext | null {
  const keys = [
    "version",
    "actor_id",
    "start_claim_id",
    "claim_hash",
    "phase",
    "dispatch_attempt_id",
    "attempt_hash",
    "dispatch_token",
    "provider_task_id",
    "lease_id",
    "lease_token",
    "lease_hash",
  ] as const;
  if (
    !hasExactKeys(value, keys) ||
    value.version !== "generation-strategy-worker-dispatch-v1" ||
    !isUuid(value.actor_id) || !isUuid(value.start_claim_id) ||
    typeof value.claim_hash !== "string" ||
    !SHA256_PATTERN.test(value.claim_hash) ||
    !["pre_dispatch", "dispatch_unknown", "provider_poll"].includes(
      String(value.phase),
    ) || !isUuid(value.lease_id) || !isUuid(value.lease_token) ||
    typeof value.lease_hash !== "string" ||
    !SHA256_PATTERN.test(value.lease_hash)
  ) return null;
  const attemptNull = value.dispatch_attempt_id === null &&
    value.attempt_hash === null && value.dispatch_token === null;
  const attemptExact = isUuid(value.dispatch_attempt_id) &&
    typeof value.attempt_hash === "string" &&
    SHA256_PATTERN.test(value.attempt_hash) && isUuid(value.dispatch_token);
  if (
    (value.phase === "pre_dispatch" &&
      (!attemptNull || value.provider_task_id !== null)) ||
    (value.phase === "dispatch_unknown" &&
      (!attemptExact || value.provider_task_id !== null)) ||
    (value.phase === "provider_poll" &&
      (!attemptNull || !isValidTaskId(value.provider_task_id)))
  ) return null;
  return value as GenerationStrategyWorkerContext;
}

function readGenerationStrategyStatusPayload(
  value: unknown,
  internalWorker: boolean,
): GenerationStrategyStatusPayload | null {
  const keys = internalWorker
    ? [
      "action",
      "organization_id",
      "project_id",
      "generation_job_id",
      "worker_context",
    ] as const
    : [
      "action",
      "organization_id",
      "project_id",
      "generation_job_id",
    ] as const;
  if (
    !hasExactKeys(value, keys) || value.action !== "strategy_status" ||
    !isUuid(value.organization_id) || !isUuid(value.project_id) ||
    !isUuid(value.generation_job_id)
  ) return null;
  if (internalWorker) {
    const workerContext = readGenerationStrategyWorkerContext(
      value.worker_context,
    );
    if (workerContext === null) return null;
    return {
      ...value,
      worker_context: workerContext,
    } as GenerationStrategyStatusPayload;
  }
  return value as GenerationStrategyStatusPayload;
}

function readGenerationStrategyReconcilePayload(
  value: unknown,
): GenerationStrategyReconcilePayload | null {
  const required = [
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
  ] as const;
  const attach = isRecord(value) &&
    value.resolution === "attach_existing_task";
  const keys = attach ? [...required, "provider_task_id"] : required;
  if (
    !hasExactKeys(value, keys) || value.action !== "strategy_reconcile" ||
    !isUuid(value.organization_id) || !isUuid(value.project_id) ||
    !isUuid(value.generation_job_id) ||
    !isUuid(value.dispatch_result_id) || !isUuid(value.incident_id) ||
    !isBoundedText(value.evidence_reference, 8, 500) ||
    !isBoundedText(value.reason, 20, 1_000) ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key) ||
    (attach && (
      !isValidTaskId(value.provider_task_id) ||
      value.confirmation !== "RUNWAY_TASK_ID_VERIFIED"
    )) ||
    (!attach && (
      value.resolution !== "confirm_no_submission" ||
      value.confirmation !== "RUNWAY_NO_TASK_VERIFIED"
    ))
  ) return null;
  return value as GenerationStrategyReconcilePayload;
}

function readStrategySpendConfirmation(value: unknown): {
  strategyId: GenerationStrategyId;
  recipe: RunwayRecipe;
  estimatedCredits: number;
} | null {
  if (typeof value !== "string") return null;
  const match = value.match(
    /^RUNWAY_(PRODUCT_UGC|PRODUCT_SWAP|PRODUCT_AD)_([4-9]|1[0-5])S_(720P|1080P)_(AUDIO|SILENT)_USD_([0-9]{1,4})[.]([0-9]{2})$/u,
  );
  if (match === null) return null;
  const recipe = match[1].toLocaleLowerCase("en-US") as RunwayRecipe;
  const entry = GENERATION_STRATEGY_CATALOG.find((candidate: {
    recipe: string;
    strategy_id: string;
  }) => candidate.recipe === recipe);
  const estimatedCredits = Number(match[5]) * 100 + Number(match[6]);
  if (
    entry === undefined || !Number.isSafeInteger(estimatedCredits) ||
    estimatedCredits <= 0
  ) return null;
  return {
    strategyId: entry.strategy_id as GenerationStrategyId,
    recipe,
    estimatedCredits,
  };
}

function readGenerationStrategyPayload(
  value: unknown,
): GenerationStrategyPayload | null {
  if (!isRecord(value) || !Object.hasOwn(value, "generation_strategy")) {
    return null;
  }
  if (value.action !== "start" || !isRecord(value.generation_strategy)) {
    return { ok: false };
  }
  const validated = validateGenerationStrategySelection(
    value.generation_strategy,
  );
  if (!isRecord(validated) || validated.ok !== true) return { ok: false };
  const strategyId = readGenerationStrategyId(validated.strategy_id);
  const recipe = readRunwayRecipe(validated.recipe);
  if (strategyId === null || recipe === null) return { ok: false };
  const entry = generationStrategyCatalogEntry(strategyId);
  if (
    entry === null || entry.provider !== "runway" || entry.recipe !== recipe ||
    entry.recipe_version !== value.generation_strategy.recipe_version ||
    !RUNWAY_PROVIDER_ENDPOINTS.has(entry.server.provider_path)
  ) return { ok: false };
  return {
    ok: true,
    strategyId,
    recipe,
    selection: value.generation_strategy,
  };
}

function readGenerationProviderPolicy(
  value: unknown,
  provider: GenerationProvider,
  model: GenerationModel,
): GenerationProviderPolicy | null {
  if (!isRecord(value)) return null;
  const keys = new Set([
    "ok",
    "provider",
    "model",
    "launch_enabled",
    "catalog_version",
    "automatic_generation",
    "automatic_spend",
  ]);
  const withReasonKeys = new Set([...keys, "disabled_reason_code"]);
  const disabledReasonCode = value.disabled_reason_code === null ||
      value.disabled_reason_code === undefined
    ? null
    : typeof value.disabled_reason_code === "string" &&
        /^[a-z][a-z0-9_]{2,63}$/u.test(value.disabled_reason_code)
    ? value.disabled_reason_code
    : "";
  if (
    (!hasOnlyKeys(value, keys) && !hasOnlyKeys(value, withReasonKeys)) ||
    ![keys.size, withReasonKeys.size].includes(Object.keys(value).length) ||
    value.ok !== true || value.provider !== provider || value.model !== model ||
    typeof value.launch_enabled !== "boolean" ||
    disabledReasonCode === "" ||
    (value.launch_enabled && disabledReasonCode !== null) ||
    value.catalog_version !== GENERATION_MODEL_CATALOG_VERSION ||
    value.automatic_generation !== false || value.automatic_spend !== false
  ) return null;
  return {
    provider,
    model,
    launchEnabled: value.launch_enabled,
    disabledReasonCode,
  };
}

function readGenerationStrategyCatalogPolicy(
  value: unknown,
): GenerationStrategyCatalogPolicy | null {
  if (
    !hasExactKeys(value, [
      "ok",
      "version",
      "execution_capabilities",
      "checks",
      "select_enabled",
      "preflight_enabled",
      "paid_start_authorized",
      "contract",
    ]) || value.ok !== true ||
    value.version !== "generation-strategy-catalog-policy-response-v1" ||
    typeof value.select_enabled !== "boolean" ||
    typeof value.preflight_enabled !== "boolean" ||
    value.paid_start_authorized !== false ||
    !hasExactKeys(value.checks, [
      "organization_active",
      "sql_provider_configuration_enabled",
      "execution_chain_installed",
      "edge_secret_check_required_at_preflight",
    ]) ||
    !Object.values(value.checks).every((item) => typeof item === "boolean") ||
    !hasExactKeys(value.contract, [
      "read_only",
      "server_authoritative",
      "provider_call_started",
      "receipt_required_for_paid_start",
      "catalog_policy_is_not_paid_authority",
    ]) || value.contract.read_only !== true ||
    value.contract.server_authoritative !== true ||
    value.contract.provider_call_started !== false ||
    value.contract.receipt_required_for_paid_start !== true ||
    value.contract.catalog_policy_is_not_paid_authority !== true ||
    !isRecord(value.execution_capabilities)
  ) return null;
  const capabilities = value.execution_capabilities;
  const expectedIds = new Set(GENERATION_STRATEGY_CATALOG.map((entry: {
    strategy_id: string;
  }) => entry.strategy_id));
  if (
    Object.keys(capabilities).length !== expectedIds.size ||
    Object.keys(capabilities).some((id) => !expectedIds.has(id))
  ) return null;
  for (const entry of GENERATION_STRATEGY_CATALOG) {
    const capability = capabilities[entry.strategy_id];
    if (
      !hasExactKeys(capability, [
        "enabled",
        "catalog_version",
        "strategy_id",
        "provider",
        "recipe",
        "recipe_version",
        "provider_path",
        "pricing_version",
      ]) || typeof capability.enabled !== "boolean" ||
      capability.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
      capability.strategy_id !== entry.strategy_id ||
      capability.provider !== "runway" || capability.recipe !== entry.recipe ||
      capability.recipe_version !== RUNWAY_RECIPE_VERSION ||
      capability.provider_path !== entry.server.provider_path ||
      capability.pricing_version !== RUNWAY_RECIPE_PRICING_VERSION
    ) return null;
  }
  return {
    executionCapabilities: capabilities,
    selectEnabled: value.select_enabled,
    preflightEnabled: value.preflight_enabled,
  };
}

function generationStrategyBindingAssetsValid(
  value: unknown,
  strategyId: GenerationStrategyId,
  productId: string,
): boolean {
  if (!Array.isArray(value) || value.length < 2 || value.length > 16) {
    return false;
  }
  const counts = new Map<string, number>();
  const identities = new Set<string>();
  for (const asset of value) {
    if (
      !hasExactKeys(asset, [
        "role",
        "ordinal",
        "media_object_id",
        "sha256",
        "kind",
        "mime_type",
        "product_id",
        "rights_confirmed",
        "likeness_consent",
      ]) ||
      typeof asset.role !== "string" ||
      ![
        "product_primary",
        "product_reference",
        "creator_avatar",
        "original_product",
        "source_video",
        "style_reference",
      ].includes(asset.role) || !isUuid(asset.media_object_id) ||
      typeof asset.sha256 !== "string" ||
      !SHA256_PATTERN.test(asset.sha256) ||
      !isIntegerInRange(asset.ordinal, 1, 99) ||
      typeof asset.kind !== "string" || typeof asset.mime_type !== "string" ||
      (asset.product_id !== null && !isUuid(asset.product_id)) ||
      asset.rights_confirmed !== true ||
      typeof asset.likeness_consent !== "boolean"
    ) return false;
    const image = ["image/jpeg", "image/png", "image/webp"].includes(
      asset.mime_type,
    );
    if (
      (asset.role === "product_primary" ||
          asset.role === "product_reference") &&
        (!image || !["product_photo", "packshot"].includes(asset.kind) ||
          asset.product_id !== productId || asset.likeness_consent) ||
      (["creator_avatar", "original_product", "style_reference"].includes(
        asset.role,
      ) && (!image || asset.kind !== "creator_reference")) ||
      (asset.role === "source_video" &&
        (asset.kind !== "source_video" || asset.mime_type !== "video/mp4" ||
          asset.likeness_consent)) ||
      ((asset.role === "creator_avatar") !== asset.likeness_consent) ||
      (asset.role === "product_primary" && asset.ordinal !== 1) ||
      (["creator_avatar", "original_product", "source_video"].includes(
        asset.role,
      ) && asset.ordinal !== 1) ||
      (asset.role === "product_reference" && asset.ordinal > 9) ||
      (asset.role === "style_reference" && asset.ordinal > 4)
    ) return false;
    const identity = `${asset.role}:${asset.ordinal}`;
    if (identities.has(identity) || identities.has(asset.media_object_id)) {
      return false;
    }
    identities.add(identity);
    identities.add(asset.media_object_id);
    counts.set(asset.role, (counts.get(asset.role) || 0) + 1);
  }
  const count = (role: string) => counts.get(role) || 0;
  if (count("product_primary") !== 1) return false;
  if (strategyId === "viral_avatar_ugc") {
    return value.length === 2 && count("creator_avatar") === 1 &&
      count("product_reference") === 0 && count("original_product") === 0 &&
      count("source_video") === 0 && count("style_reference") === 0;
  }
  if (strategyId === "viral_product_swap") {
    return count("creator_avatar") === 0 && count("original_product") === 1 &&
      count("source_video") === 1 && count("style_reference") === 0 &&
      count("product_reference") <= 9 &&
      value.length === count("product_reference") + 3;
  }
  return count("creator_avatar") === 0 && count("original_product") === 0 &&
    count("source_video") === 1 && count("product_reference") <= 9 &&
    count("style_reference") <= 4 &&
    value.length ===
      count("product_reference") + count("style_reference") + 2;
}

function generationStrategyPriceValid(
  value: unknown,
  payload: GenerationStrategyBindPayload,
  strategyId: GenerationStrategyId,
  recipe: RunwayRecipe,
): boolean {
  if (
    !hasExactKeys(value, [
      "version",
      "strategy_id",
      "provider",
      "recipe",
      "input_mode",
      "duration_seconds",
      "resolution",
      "ratio",
      "audio",
      "estimated_credits",
      "estimated_pre_tax_usd_minor",
      "estimated_cost_minor",
      "estimated_cost_usd",
      "currency",
      "credit_unit_cost_minor",
      "catalog_version",
      "pricing_version",
      "recipe_version",
      "spend_confirmation",
      "price_hash",
    ])
  ) return false;
  const selection = payload.generation_strategy;
  const estimatedCredits = value.estimated_credits;
  const expectedPrice = estimateGenerationStrategyCredits(
    strategyId,
    selection,
  );
  if (
    !isRecord(expectedPrice) || expectedPrice.ok !== true ||
    value.estimated_credits !== expectedPrice.estimated_credits ||
    value.estimated_pre_tax_usd_minor !==
      expectedPrice.estimated_pre_tax_usd_minor ||
    value.version !== "generation-strategy-price-snapshot-v1" ||
    value.strategy_id !== strategyId || value.provider !== "runway" ||
    value.recipe !== recipe ||
    value.input_mode !==
      (strategyId === "viral_avatar_ugc"
        ? "character_and_product_images"
        : strategyId === "viral_product_swap"
        ? "video_and_product_images"
        : "product_images") ||
    value.duration_seconds !== selection.duration_seconds ||
    !["720p", "1080p"].includes(String(value.resolution)) ||
    value.audio !== selection.audio ||
    !isIntegerInRange(estimatedCredits, 0, 1_000_000) ||
    value.estimated_pre_tax_usd_minor !== estimatedCredits ||
    value.estimated_cost_minor !== estimatedCredits ||
    value.estimated_cost_usd !== (estimatedCredits / 100).toFixed(2) ||
    value.currency !== "USD" || value.credit_unit_cost_minor !== 1 ||
    value.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    value.pricing_version !== RUNWAY_RECIPE_PRICING_VERSION ||
    value.recipe_version !== RUNWAY_RECIPE_VERSION ||
    typeof value.price_hash !== "string" ||
    !SHA256_PATTERN.test(value.price_hash)
  ) return false;
  if (
    strategyId === "viral_product_swap"
      ? value.ratio !== "source" ||
        value.resolution !== selection.resolution
      : value.ratio !== selection.ratio
  ) return false;
  const expectedConfirmation = `RUNWAY_${recipe.toUpperCase()}_${
    String(value.duration_seconds)
  }S_${String(value.resolution).toUpperCase()}_${
    value.audio ? "AUDIO" : "SILENT"
  }_USD_${value.estimated_cost_usd}`;
  return value.spend_confirmation === expectedConfirmation;
}

function readGenerationStrategyBindResult(
  value: unknown,
  payload: GenerationStrategyBindPayload,
): Record<string, unknown> | null {
  if (
    !hasExactKeys(value, [
      "ok",
      "version",
      "binding",
      "selection",
      "price",
      "contract",
    ]) || value.ok !== true ||
    value.version !== "generation-strategy-resolve-bind-response-v1" ||
    !hasExactKeys(value.selection, [
      "catalog_version",
      "recipe_version",
      "pricing_version",
      "strategy_id",
      "recipe",
      "selection_hash",
    ])
  ) return null;
  const strategyId = readGenerationStrategyId(value.selection.strategy_id);
  const recipe = readRunwayRecipe(value.selection.recipe);
  const expectedStrategyId = readGenerationStrategyId(
    payload.generation_strategy.strategy_id,
  );
  const entry = strategyId === null
    ? null
    : generationStrategyCatalogEntry(strategyId);
  if (
    strategyId === null || recipe === null ||
    strategyId !== expectedStrategyId ||
    entry === null || entry.recipe !== recipe ||
    value.selection.catalog_version !== GENERATION_STRATEGY_CATALOG_VERSION ||
    value.selection.recipe_version !== RUNWAY_RECIPE_VERSION ||
    value.selection.pricing_version !== RUNWAY_RECIPE_PRICING_VERSION ||
    typeof value.selection.selection_hash !== "string" ||
    !SHA256_PATTERN.test(value.selection.selection_hash) ||
    !hasExactKeys(value.binding, [
      "id",
      "project_id",
      "spec_id",
      "spec_version",
      "spec_hash",
      "product_id",
      "strategy_id",
      "selection_hash",
      "source_basis",
      "source_binding_id",
      "source_binding_hash",
      "role_assets",
      "strategy_snapshot_hash",
      "binding_hash",
      "bound_at",
    ]) || !isUuid(value.binding.id) ||
    value.binding.project_id !== payload.project_id ||
    value.binding.spec_id !== payload.spec_id ||
    value.binding.spec_version !== payload.spec_version ||
    value.binding.spec_hash !== payload.spec_hash ||
    !isUuid(value.binding.product_id) ||
    value.binding.strategy_id !== strategyId ||
    value.binding.selection_hash !== value.selection.selection_hash ||
    value.binding.source_basis !== "exact_source_video" ||
    !isUuid(value.binding.source_binding_id) ||
    typeof value.binding.source_binding_hash !== "string" ||
    !SHA256_PATTERN.test(value.binding.source_binding_hash) ||
    typeof value.binding.strategy_snapshot_hash !== "string" ||
    !SHA256_PATTERN.test(value.binding.strategy_snapshot_hash) ||
    typeof value.binding.binding_hash !== "string" ||
    !SHA256_PATTERN.test(value.binding.binding_hash) ||
    typeof value.binding.bound_at !== "string" ||
    !Number.isFinite(Date.parse(value.binding.bound_at)) ||
    !generationStrategyBindingAssetsValid(
      value.binding.role_assets,
      strategyId,
      value.binding.product_id,
    ) || !generationStrategyPriceValid(
      value.price,
      payload,
      strategyId,
      recipe,
    ) ||
    !hasExactKeys(value.contract, [
      "server_resolved_source_binding",
      "server_resolved_media_hashes",
      "browser_hashes_accepted",
      "browser_source_binding_accepted",
      "provider_call_started",
      "paid_start_integrated",
      "launch_enabled",
    ]) || value.contract.server_resolved_source_binding !== true ||
    value.contract.server_resolved_media_hashes !== true ||
    value.contract.browser_hashes_accepted !== false ||
    value.contract.browser_source_binding_accepted !== false ||
    value.contract.provider_call_started !== false ||
    value.contract.paid_start_integrated !== false ||
    value.contract.launch_enabled !== false
  ) return null;
  return value;
}

function readGenerationModelFeatureFlags(
  value: unknown,
): GenerationModelFeatureFlags | null {
  if (!isRecord(value)) return null;
  const keys = new Set([
    "ok",
    "catalog_version",
    "google_veo_lite",
    "runway_premium",
  ]);
  if (
    !hasOnlyKeys(value, keys) || Object.keys(value).length !== keys.size ||
    value.ok !== true ||
    value.catalog_version !== GENERATION_MODEL_CATALOG_VERSION ||
    typeof value.google_veo_lite !== "boolean" ||
    typeof value.runway_premium !== "boolean"
  ) return null;
  return {
    googleVeoLite: value.google_veo_lite,
    runwayPremium: value.runway_premium,
  };
}

type ExactGenerationSku = {
  provider: GenerationProvider;
  model: GenerationModel;
  inputMode: "image";
  durationSeconds: number;
  format: CommonStartPayload["format"];
  resolution: GenerationResolution;
  audio: boolean;
  lastFrame: boolean;
  referenceImageCount: number;
  estimatedCostMinor: number;
  estimatedCredits: number | null;
  confirmation: string;
  pricingVersion: string;
};

function providerFeatureFlags(
  provider: GenerationProvider,
  launchEnabled: boolean,
): Record<string, boolean> {
  return provider === "google" && launchEnabled
    ? { [GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]: true }
    : {};
}

function generationReferenceImageCount(
  model: GenerationModel,
  mediaCount: number,
  lastFrame: boolean,
): number | null {
  if (!Number.isInteger(mediaCount) || mediaCount < 1 || mediaCount > 5) {
    return null;
  }
  if (
    model === "seedream5_lite" || model === "seedance2_fast" ||
    model === "seedance2_mini"
  ) return lastFrame ? null : mediaCount;
  return mediaCount === (lastFrame ? 2 : 1) ? 0 : null;
}

function generationExecutionSemantics(
  model: GenerationModel,
  audio: boolean,
  lastFrame: boolean,
  mediaCount: number,
): {
  spokenDialogue: boolean;
  referenceImageCount: number;
  firstFrame: boolean;
} | null {
  const audioRequired = model === "seedance2_fast" ||
    model === "seedance2_mini" || model === "gemini_omni_flash" ||
    model === GOOGLE_VEO_LITE_MODEL;
  const audioForbidden = model === "seedream5_lite" ||
    model === "gen4_turbo" || model === "gen4.5";
  if ((audioRequired && !audio) || (audioForbidden && audio)) return null;
  const referenceImageCount = generationReferenceImageCount(
    model,
    mediaCount,
    lastFrame,
  );
  if (referenceImageCount === null) return null;
  const referenceMode = model === "seedream5_lite" ||
    model === "seedance2_fast" || model === "seedance2_mini";
  return {
    spokenDialogue: audio && generationModelSupportsAudio(model),
    referenceImageCount,
    firstFrame: !referenceMode,
  };
}

function exactGenerationSku(
  provider: GenerationProvider,
  model: GenerationModel,
  durationSeconds: unknown,
  format: unknown,
  resolution: unknown,
  audio: unknown,
  lastFrame: unknown,
  mediaCount: number,
  featureFlags: Record<string, boolean> = {},
): ExactGenerationSku | null {
  if (!LIVE_GENERATION_EXECUTION_KEYS.has(`${provider}:${model}`)) return null;
  if (typeof format !== "string" || typeof resolution !== "string") return null;
  if (typeof audio !== "boolean" || typeof lastFrame !== "boolean") return null;
  const semantics = generationExecutionSemantics(
    model,
    audio,
    lastFrame,
    mediaCount,
  );
  if (semantics === null) return null;
  const entry = generationModelCatalogEntry(provider, model);
  if (!entry) return null;
  const selection = {
    inputMode: "image",
    durationSeconds: Number(durationSeconds),
    ratio: format,
    resolution,
    audio,
    spokenDialogue: semantics.spokenDialogue,
    referenceImageCount: semantics.referenceImageCount,
    referenceVideo: false,
    firstFrame: semantics.firstFrame,
    lastFrame,
  };
  const validated = validateGenerationModelSelection(entry, selection, {
    featureFlags,
  });
  if (!validated.ok) return null;
  // Seedream's historical paid contract is intentionally narrower than the
  // provider's full catalog capability. The model-catalog action projects the
  // same exact subset so the browser never offers an unlaunchable 3K/ratio SKU.
  if (
    model === "seedream5_lite" &&
    (validated.ratio !== "1:1" || validated.resolution !== "2K")
  ) return null;
  const estimate = estimateGenerationModelCostMinor(entry, validated, {
    featureFlags,
  });
  if (!estimate.ok || !Number.isSafeInteger(estimate.estimatedCostMinor)) {
    return null;
  }
  const estimatedCredits = provider === "runway"
    ? Number(estimate.estimatedCredits)
    : null;
  if (provider === "runway" && !Number.isSafeInteger(estimatedCredits)) {
    return null;
  }
  const estimatedUsd = (estimate.estimatedCostMinor / 100).toFixed(2);
  const legacySku = provider === "runway" &&
      Object.hasOwn(RUNWAY_SKU_CONFIG, model)
    ? readRunwayGenerationSku(model as ExistingRunwayModel, durationSeconds)
    : null;
  if (
    provider === "runway" && Object.hasOwn(RUNWAY_SKU_CONFIG, model) &&
    (legacySku === null ||
      legacySku.durationSeconds !== estimate.durationSeconds ||
      legacySku.estimatedCredits !== estimatedCredits ||
      legacySku.estimatedUsd !== estimatedUsd)
  ) return null;
  let confirmation: string;
  if (legacySku !== null) {
    confirmation = legacySku.confirmation;
  } else {
    const prefix = provider === "google"
      ? "GOOGLE_VEO3_1_LITE"
      : `RUNWAY_${model.toUpperCase().replaceAll(".", "_")}`;
    confirmation =
      `${prefix}_${estimate.durationSeconds}S_${resolution.toUpperCase()}_${
        audio ? "AUDIO" : "SILENT"
      }_USD_${estimatedUsd}`;
  }
  return {
    provider,
    model,
    inputMode: "image",
    durationSeconds: estimate.durationSeconds,
    format: validated.ratio as GenerationFormat,
    resolution: validated.resolution as GenerationResolution,
    audio,
    lastFrame,
    referenceImageCount: semantics.referenceImageCount,
    estimatedCostMinor: estimate.estimatedCostMinor,
    estimatedCredits,
    confirmation,
    pricingVersion: entry.pricingVersion,
  };
}

function startSelectionSnapshotMatches(
  payload: StartPayload,
  sku: ExactGenerationSku,
): boolean {
  try {
    const parsed = readGenerationSelectionSnapshot(
      payload.generation_selection_snapshot,
    );
    if (parsed?.state !== "present" || !isRecord(parsed.snapshot)) return false;
    const snapshot = parsed.snapshot;
    return Object.keys(snapshot).length ===
        GENERATION_SELECTION_SNAPSHOT_FIELDS.length &&
      snapshot.provider === sku.provider &&
      snapshot.model === sku.model &&
      snapshot.recommendation_catalog_version ===
        GENERATION_MODEL_CATALOG_VERSION &&
      snapshot.pricing_version === sku.pricingVersion &&
      snapshot.estimated_cost_minor === sku.estimatedCostMinor &&
      snapshot.requested_duration_seconds === sku.durationSeconds &&
      snapshot.requested_ratio === sku.format &&
      snapshot.requested_resolution === sku.resolution &&
      snapshot.requested_audio === sku.audio &&
      snapshot.input_mode === sku.inputMode &&
      snapshot.reference_count === sku.referenceImageCount &&
      snapshot.provider_readiness_receipt_id ===
        payload.provider_readiness_receipt_id;
  } catch {
    return false;
  }
}

function publicExecutionPolicy(provider: string, model: string) {
  const key = `${provider}:${model}`;
  const policies: Record<string, Record<string, Json>> = {
    "runway:seedream5_lite": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 0,
        format: "1:1",
        resolution: "2K",
        audio: false,
        lastFrame: false,
      },
      allowedRatios: ["1:1"],
      allowedResolutions: ["2K"],
      maxReferenceImages: 5,
      audioModes: [false],
      lastFrameSupported: false,
    },
    "runway:gen4_turbo": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 5,
        format: "9:16",
        resolution: "720p",
        audio: false,
        lastFrame: false,
      },
      audioModes: [false],
      lastFrameSupported: false,
    },
    "runway:seedance2_fast": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 8,
        format: "9:16",
        resolution: "720p",
        audio: true,
        lastFrame: false,
      },
      maxReferenceImages: 5,
      audioModes: [true],
      lastFrameSupported: false,
    },
    "runway:gen4.5": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 5,
        format: "9:16",
        resolution: "720p",
        audio: false,
        lastFrame: false,
      },
      audioModes: [false],
      lastFrameSupported: false,
    },
    "runway:seedance2_mini": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 4,
        format: "9:16",
        resolution: "720p",
        audio: true,
        lastFrame: false,
      },
      maxReferenceImages: 5,
      audioModes: [true],
      lastFrameSupported: false,
    },
    "runway:veo3.1_fast": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 8,
        format: "9:16",
        resolution: "720p",
        audio: true,
        lastFrame: false,
      },
      audioModes: [false, true],
      lastFrameSupported: true,
    },
    "runway:gemini_omni_flash": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 5,
        format: "9:16",
        resolution: "720p",
        audio: true,
        lastFrame: false,
      },
      audioModes: [true],
      lastFrameSupported: false,
      bestFor: [
        "быстрый ролик со звуком из одного исходного кадра",
        "короткий UGC-черновик с речью",
      ],
      avoidFor: [
        "вариация готового видео в текущем маршруте",
        "1080p, 4K или точный последний кадр",
      ],
    },
    "google:veo-3.1-lite-generate-preview": {
      selectionDefaults: {
        inputMode: "image",
        durationSeconds: 8,
        format: "9:16",
        resolution: "720p",
        audio: true,
        lastFrame: false,
      },
      audioModes: [true],
      lastFrameSupported: true,
    },
  };
  return LIVE_GENERATION_EXECUTION_KEYS.has(key) ? policies[key] || {} : {};
}

function readGenerationLearningContext(
  value: unknown,
): GenerationLearningContext | null {
  if (!isRecord(value)) return null;
  const allowed = new Set([
    "creative_angle",
    "hook_patterns",
    "source",
    "compiler_version",
    "product_category",
    "applied_policy_hash",
    "creative_brief_draft_id",
    "scenario_position",
  ]);
  const required = [
    "creative_angle",
    "hook_patterns",
    "source",
    "compiler_version",
    "product_category",
  ];
  if (
    !hasOnlyKeys(value, allowed) ||
    !required.every((key) => Object.hasOwn(value, key))
  ) {
    return null;
  }
  const angles = new Set([
    "product_focus",
    "trust_builder",
    "demonstration",
    "comparison",
    "objection_handling",
    "curiosity_gap",
  ]);
  const patterns = new Set([
    "question_led",
    "why_explanation",
    "before_buying",
    "comparison",
    "demonstration",
    "first_person",
    "numbered",
    "concise",
  ]);
  const sources = new Set([
    "baseline",
    "approved_research",
    "performance_learning",
  ]);
  const productCategories = new Set([
    "cosmetics",
    "baa",
    "sports_food",
    "food",
    "household",
    "apparel",
    "electronics",
    "other",
  ]);
  const hookPatterns = value.hook_patterns;
  if (
    typeof value.creative_angle !== "string" ||
    !angles.has(value.creative_angle) ||
    !Array.isArray(hookPatterns) ||
    hookPatterns.length > 8 ||
    hookPatterns.some((pattern) =>
      typeof pattern !== "string" || !patterns.has(pattern)
    ) ||
    new Set(hookPatterns).size !== hookPatterns.length ||
    typeof value.source !== "string" ||
    !sources.has(value.source) ||
    typeof value.compiler_version !== "string" ||
    !/^[a-z0-9][a-z0-9._-]{2,63}$/u.test(value.compiler_version) ||
    typeof value.product_category !== "string" ||
    !productCategories.has(value.product_category) ||
    (
      Object.hasOwn(value, "applied_policy_hash") &&
      (
        typeof value.applied_policy_hash !== "string" ||
        !/^[0-9a-f]{64}$/u.test(value.applied_policy_hash)
      )
    )
  ) {
    return null;
  }
  if (
    value.source === "approved_research" &&
    (
      !isUuid(value.creative_brief_draft_id) ||
      ![1, 2, 3].includes(Number(value.scenario_position)) ||
      Object.hasOwn(value, "applied_policy_hash")
    )
  ) {
    return null;
  }
  if (
    value.source === "performance_learning" &&
    (
      typeof value.applied_policy_hash !== "string" ||
      !/^[0-9a-f]{64}$/u.test(value.applied_policy_hash) ||
      Object.hasOwn(value, "creative_brief_draft_id") ||
      Object.hasOwn(value, "scenario_position")
    )
  ) {
    return null;
  }
  if (
    value.source === "baseline" &&
    (
      value.creative_angle !== "product_focus" ||
      hookPatterns.length !== 0 ||
      Object.hasOwn(value, "applied_policy_hash") ||
      Object.hasOwn(value, "creative_brief_draft_id") ||
      Object.hasOwn(value, "scenario_position")
    )
  ) {
    return null;
  }
  return value as GenerationLearningContext;
}

function readGenerationRepairContext(
  value: unknown,
): GenerationRepairContext | null {
  if (!isRecord(value)) return null;
  const allowed = new Set([
    "source_review_id",
    "source_generation_job_id",
    "guard_codes",
    "policy_hash",
    "compiler_version",
  ]);
  const guardCodes = value.guard_codes;
  const validGuardCodes = new Set([
    "product_fidelity",
    "technical_stability",
    "audio_quality",
    "speech_fidelity",
    "hook_clarity",
    "visual_quality",
    "trust",
    "platform_fit",
  ]);
  if (
    !hasOnlyKeys(value, allowed) ||
    Object.keys(value).length !== allowed.size ||
    !isUuid(value.source_review_id) ||
    !isUuid(value.source_generation_job_id) ||
    !Array.isArray(guardCodes) ||
    guardCodes.length < 1 ||
    guardCodes.length > 3 ||
    guardCodes.some((code) =>
      typeof code !== "string" || !validGuardCodes.has(code)
    ) ||
    new Set(guardCodes).size !== guardCodes.length ||
    typeof value.policy_hash !== "string" ||
    !/^[0-9a-f]{64}$/u.test(value.policy_hash) ||
    value.compiler_version !== "review-repair-v1"
  ) {
    return null;
  }
  return value as GenerationRepairContext;
}

function readGenerationSpecContext(
  value: unknown,
): GenerationSpecContext | null {
  if (!isRecord(value)) return null;
  const keys = new Set(["spec_id", "spec_version", "spec_hash"]);
  if (
    !hasOnlyKeys(value, keys) || Object.keys(value).length !== keys.size ||
    !isUuid(value.spec_id) ||
    !isIntegerInRange(value.spec_version, 1, 100_000) ||
    typeof value.spec_hash !== "string" ||
    !SHA256_PATTERN.test(value.spec_hash)
  ) return null;
  return value as GenerationSpecContext;
}

function readGenerationVideoReferenceContext(
  value: unknown,
): GenerationVideoReferenceContext | null {
  if (!isRecord(value)) return null;
  const keys = new Set(["binding_id", "binding_hash"]);
  if (
    !hasOnlyKeys(value, keys) ||
    Object.keys(value).length !== keys.size ||
    !isUuid(value.binding_id) ||
    typeof value.binding_hash !== "string" ||
    !SHA256_PATTERN.test(value.binding_hash)
  ) return null;
  return value as GenerationVideoReferenceContext;
}

function readGenerationSpecScope(
  value: unknown,
  featureFlags: Record<string, boolean> = {},
): GenerationSpecScope | null {
  if (!isRecord(value)) return null;
  const keys = new Set([
    "primary_media_id",
    "media_ids",
    "platform",
    "provider",
    "model",
    "input_mode",
    "duration_seconds",
    "product_category",
    "format",
    "ratio",
    "resolution",
    "audio",
    "spoken_dialogue",
    "reference_count",
    "reference_video",
    "first_frame",
    "last_frame",
  ]);
  if (!hasOnlyKeys(value, keys) || Object.keys(value).length !== keys.size) {
    return null;
  }
  const provider = readGenerationProvider(value.provider);
  const model = readGenerationModel(provider, value.model);
  const mediaIds = value.media_ids;
  const platforms = new Set([
    "instagram",
    "tiktok",
    "youtube",
    "vk",
    "telegram",
    "wildberries",
  ]);
  const categories = new Set([
    "cosmetics",
    "baa",
    "sports_food",
    "food",
    "household",
    "apparel",
    "electronics",
    "other",
  ]);
  if (
    !isUuid(value.primary_media_id) ||
    !Array.isArray(mediaIds) || mediaIds.length < 1 || mediaIds.length > 5 ||
    mediaIds.some((item) => !isUuid(item)) ||
    new Set(mediaIds).size !== mediaIds.length ||
    mediaIds[0] !== value.primary_media_id ||
    typeof value.platform !== "string" || !platforms.has(value.platform) ||
    provider === null || model === null || value.input_mode !== "image" ||
    typeof value.product_category !== "string" ||
    !categories.has(value.product_category) ||
    typeof value.format !== "string" ||
    value.ratio !== value.format ||
    typeof value.resolution !== "string" ||
    typeof value.audio !== "boolean" ||
    typeof value.spoken_dialogue !== "boolean" ||
    !isIntegerInRange(value.reference_count, 0, 5) ||
    value.reference_video !== false ||
    typeof value.first_frame !== "boolean" ||
    typeof value.last_frame !== "boolean"
  ) return null;
  const exact = exactGenerationSku(
    provider,
    model,
    value.duration_seconds,
    value.format,
    value.resolution,
    value.audio,
    value.last_frame,
    mediaIds.length,
    featureFlags,
  );
  const semantics = generationExecutionSemantics(
    model,
    value.audio,
    value.last_frame,
    mediaIds.length,
  );
  if (
    exact === null || semantics === null ||
    value.reference_count !== exact.referenceImageCount ||
    value.first_frame !== semantics.firstFrame ||
    value.spoken_dialogue !== semantics.spokenDialogue
  ) return null;
  return {
    primary_media_id: value.primary_media_id,
    media_ids: [...mediaIds],
    platform: value.platform as CommonStartPayload["platform"],
    provider,
    model,
    input_mode: "image",
    duration_seconds: exact.durationSeconds,
    product_category: value.product_category as ProductCategory,
    format: exact.format,
    ratio: exact.format,
    resolution: exact.resolution,
    audio: exact.audio,
    spoken_dialogue: semantics.spokenDialogue,
    reference_count: semantics.referenceImageCount,
    reference_video: false,
    first_frame: semantics.firstFrame,
    last_frame: exact.lastFrame,
  };
}

function readGenerationSpecEffectivePolicy(
  value: unknown,
  featureFlags: Record<string, boolean> = {},
): GenerationSpecEffectivePolicy | null {
  if (!isRecord(value)) return null;
  const keys = new Set([
    "ok",
    "version",
    "project_id",
    "generation_spec_context",
    "status",
    "exact_scope",
    "compiled_prompt",
    "prompt_hash",
    "learning_context",
    "repair_context",
    "final_policy_hash",
    "outcome_selection",
    "automatic_approval",
    "automatic_spend",
    "automatic_generation",
  ]);
  if (
    !hasOnlyKeys(value, keys) || Object.keys(value).length !== keys.size ||
    value.ok !== true ||
    value.version !== "generation-spec-effective-policy-v1" ||
    !isUuid(value.project_id) ||
    value.status !== "approved_current" ||
    value.automatic_approval !== false ||
    value.automatic_spend !== false ||
    value.automatic_generation !== false
  ) return null;
  const context = readGenerationSpecContext(value.generation_spec_context);
  const scope = readGenerationSpecScope(value.exact_scope, featureFlags);
  const learningContext = readGenerationLearningContext(value.learning_context);
  const repairContext = value.repair_context === null
    ? null
    : readGenerationRepairContext(value.repair_context);
  const outcome = value.outcome_selection;
  let outcomeSelection: GenerationSpecEffectivePolicy["outcomeSelection"] =
    null;
  if (outcome !== null) {
    const outcomeKeys = new Set([
      "selection_id",
      "selection_hash",
      "selection_action",
      "expires_at",
    ]);
    if (
      !isRecord(outcome) || !hasOnlyKeys(outcome, outcomeKeys) ||
      Object.keys(outcome).length !== outcomeKeys.size ||
      !isUuid(outcome.selection_id) ||
      typeof outcome.selection_hash !== "string" ||
      !SHA256_PATTERN.test(outcome.selection_hash) ||
      !["apply", "control"].includes(String(outcome.selection_action)) ||
      typeof outcome.expires_at !== "string" ||
      !Number.isFinite(Date.parse(outcome.expires_at))
    ) return null;
    outcomeSelection =
      outcome as GenerationSpecEffectivePolicy["outcomeSelection"];
  }
  if (
    context === null || scope === null || learningContext === null ||
    (value.repair_context !== null && repairContext === null) ||
    !isBoundedText(
      value.compiled_prompt,
      1,
      Number(generationCatalogEntryForModel(scope.model)?.promptLimit || 0),
    ) ||
    typeof value.prompt_hash !== "string" ||
    !SHA256_PATTERN.test(value.prompt_hash) ||
    typeof value.final_policy_hash !== "string" ||
    !SHA256_PATTERN.test(value.final_policy_hash)
  ) return null;
  return {
    projectId: value.project_id,
    generationSpecContext: context,
    exactScope: scope,
    compiledPrompt: value.compiled_prompt,
    promptHash: value.prompt_hash,
    learningContext,
    repairContext,
    finalPolicyHash: value.final_policy_hash,
    outcomeSelection,
  };
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (isRecord(value)) {
    return `{${
      Object.keys(value).sort().map((key) =>
        `${JSON.stringify(key)}:${stableJson(value[key])}`
      ).join(",")
    }}`;
  }
  return JSON.stringify(value);
}

function generationLearningPromptRequirements(
  value: unknown,
  model: GenerationModel,
): string[] | null {
  if (!isRecord(value) || value.applied !== true) return null;
  const photo = model === "seedream5_lite";
  const angle = typeof value.preferred_angle === "string"
    ? value.preferred_angle
    : "";
  const angleRequirements = photo
    ? {
      product_focus: "Обученный ракурс: товар целиком, строгий фокус.",
      trust_builder: "Обученный ракурс: естественная предметная подача.",
      demonstration: "Обученный ракурс: одна видимая деталь товара.",
      comparison: "Обученный ракурс: ясный масштаб без второго товара.",
      objection_handling: "Обученный ракурс: упаковка и проверяемые детали.",
      curiosity_gap:
        "Обученный ракурс: выразительная деталь при видимом целом товаре.",
    }
    : {
      product_focus: "Обученное направление: товар главный во всех кадрах.",
      trust_builder:
        "Обученное направление: естественная подача без преувеличений.",
      demonstration: "Обученное направление: одно видимое действие с товаром.",
      comparison:
        "Обученное направление: сравнение без второго товара и обещаний.",
      objection_handling:
        "Обученное направление: одна проверяемая деталь товара.",
      curiosity_gap:
        "Обученное направление: заметная деталь, затем товар целиком.",
    };
  const angleRequirement =
    angleRequirements[angle as keyof typeof angleRequirements];
  if (typeof angleRequirement !== "string") return null;
  const requirements = [angleRequirement];

  const hookPatterns = value.preferred_hook_patterns;
  if (!Array.isArray(hookPatterns) || hookPatterns.length > 4) return null;
  if (!photo && hookPatterns.length > 0) {
    const hookRequirements = {
      question_led:
        "Структурный hook: визуальный вопрос сразу раскрывается точным товаром.",
      why_explanation:
        "Структурный hook: видимая причина рассмотреть товар, без утверждений.",
      before_buying:
        "Структурный hook: спокойная проверка товара перед выбором.",
      comparison:
        "Структурный hook: сравнение без второго товара, цифр и обещаний.",
      demonstration: "Структурный hook: одно простое действие с товаром.",
      first_person:
        "Структурный hook: от первого лица; товар целиком и в фокусе.",
      numbered: "Структурный hook: один понятный шаг без цифр и надписей.",
      concise: "Структурный hook: простой первый кадр сразу показывает товар.",
    };
    const firstHook = hookPatterns[0];
    if (typeof firstHook !== "string") return null;
    const hookRequirement =
      hookRequirements[firstHook as keyof typeof hookRequirements];
    if (typeof hookRequirement !== "string") return null;
    requirements.push(hookRequirement);
  }

  const guardCodes = value.quality_guard_codes ?? [];
  if (
    !Array.isArray(guardCodes) || guardCodes.length > 3 ||
    new Set(guardCodes).size !== guardCodes.length
  ) {
    return null;
  }
  const guardVariantsValue = value.quality_guard_variants;
  const guardVariants: Record<string, 1 | 2> = {};
  if (guardVariantsValue === undefined) {
    for (const guardCode of guardCodes) {
      if (typeof guardCode !== "string") return null;
      guardVariants[guardCode] = 1;
    }
  } else if (
    !isRecord(guardVariantsValue) ||
    Object.keys(guardVariantsValue).length !== guardCodes.length
  ) {
    return null;
  } else {
    for (const guardCode of guardCodes) {
      if (
        typeof guardCode !== "string" ||
        ![1, 2].includes(Number(guardVariantsValue[guardCode]))
      ) {
        return null;
      }
      guardVariants[guardCode] = Number(
        guardVariantsValue[guardCode],
      ) as 1 | 2;
    }
    if (
      Object.keys(guardVariantsValue).some((code) => !guardCodes.includes(code))
    ) {
      return null;
    }
  }
  const guardRequirements = photo
    ? {
      product_fidelity: {
        1: "QA: точная геометрия, этикетка, текст, цвет и пропорции.",
        2: "QA+: один товар строго по исходнику; не изменять ни одну букву, край, цвет или пропорцию упаковки.",
      },
      technical_stability: {
        1: "QA: резкий товар, ровный свет, без пересвета и размытия.",
        2: "QA+: нейтральный ровный свет; весь товар резкий, без бликов, шума и размытия.",
      },
      hook_clarity: {
        1: "QA: товар считывается первым.",
        2: "QA+: товар занимает главный визуальный акцент и считывается без второго объекта.",
      },
      visual_quality: {
        1: "QA: чистые края без дублей, деформаций и AI-артефактов.",
        2: "QA+: цельный чистый силуэт; никаких лишних деталей, дублей, швов и AI-артефактов.",
      },
      trust: {
        1: "QA: естественные материалы, свет и масштаб.",
        2: "QA+: реалистичные материалы, масштаб и тени как в предметной съёмке.",
      },
      platform_fit: {
        1: "QA: мастер 1:1, безопасные поля.",
        2: "QA+: квадрат 1:1; упаковка целиком внутри безопасных полей.",
      },
    }
    : {
      product_fidelity: {
        1: "QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.",
        2: "QA+: один точный товар по исходнику; упаковка, этикетка, текст, цвет и пропорции неизменны в каждом кадре.",
      },
      technical_stability: {
        1: "QA: стабильный проход без чёрных кадров, скачков и мерцания.",
        2: "QA+: один непрерывный стабильный проход; без скачков, чёрных кадров, морфинга и мерцания.",
      },
      audio_quality: {
        1: "QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.",
        2: "QA+: непрерывная разборчивая дорожка; без тишины, клиппинга, шума и рассинхронизации.",
      },
      speech_fidelity: {
        1: "QA: реплика произносится дословно, без пропусков, замен и новых слов.",
        2: "QA+: произнести только точную реплику дословно; без пропусков, замен, повторов и новых слов.",
      },
      hook_clarity: {
        1: "QA: точный товар и одно действие видны в первые 2 секунды.",
        2: "QA+: точный товар — главный объект первого кадра; одно действие начинается в первые 2 секунды.",
      },
      visual_quality: {
        1: "QA: руки, лицо и фактуры без деформаций, дублей и мерцания.",
        2: "QA+: постоянные руки, лицо, упаковка и фактуры; без деформаций, дублей, швов и мерцания.",
      },
      trust: {
        1: "QA: естественная подача без гиперболы и новых обещаний.",
        2: "QA+: естественный свет, материалы и движение; без гиперболы, постановочного эффекта и новых обещаний.",
      },
      platform_fit: {
        1: "QA: мастер 9:16; товар и лицо в безопасных полях.",
        2: "QA+: вертикальный мастер 9:16; товар и лицо целиком остаются в безопасных полях.",
      },
    };
  for (const guardCode of guardCodes) {
    if (typeof guardCode !== "string") return null;
    if (
      ["audio_quality", "speech_fidelity"].includes(guardCode) &&
      !generationModelSupportsAudio(model)
    ) return null;
    const requirement =
      guardRequirements[guardCode as keyof typeof guardRequirements]
        ?.[guardVariants[guardCode]];
    if (typeof requirement !== "string") return null;
    requirements.push(requirement);
  }
  return requirements;
}

function generationLearningPromptIsBound(
  policy: unknown,
  payload: StartPayload,
): boolean {
  const requirements = generationLearningPromptRequirements(
    policy,
    payload.model,
  );
  return requirements !== null &&
    requirements.every((requirement) => payload.brief.includes(requirement));
}

function generationApprovedResearchCategoryRuleIsBound(
  policy: GenerationSpecEffectivePolicy,
): boolean {
  const context = policy.learningContext;
  if (context.source !== "approved_research") return false;
  const reservedTokens = policy.compiledPrompt.match(
    /researchcategoryrule\//giu,
  ) || [];
  if (reservedTokens.length !== 1) return false;
  const ruleLines = policy.compiledPrompt.split(/\r?\n/u).filter((line) =>
    line.startsWith("ResearchCategoryRule/")
  );
  if (ruleLines.length !== 1) return false;
  const match =
    /^ResearchCategoryRule\/v2 category_maturity=([a-z_]+) competitor_coverage=([a-z_]+) primary_signal=([a-z0-9._]+) creative_angle=([a-z_]+) primary_hook=([a-z_]+)\.$/u
      .exec(ruleLines[0]);
  if (match === null) return false;
  const categoryMaturities = new Set([
    "emerging",
    "growing",
    "established",
    "saturated",
    "unknown",
  ]);
  const competitorCoverages = new Set(["none", "limited", "sufficient"]);
  const structuralSignals = new Set([
    "none",
    "hook.problem_first",
    "hook.result_first",
    "format.single_action_demo",
    "format.step_by_step",
    "format.comparison",
    "format.unboxing",
    "format.creator_explainer",
    "proof.product_in_use",
    "proof.before_after",
    "proof.social_proof",
    "offer.bundle",
    "offer.price_anchor",
    "channel.marketplace_native_video",
    "channel.short_vertical_video",
  ]);
  const angles = new Set([
    "product_focus",
    "trust_builder",
    "demonstration",
    "comparison",
    "objection_handling",
    "curiosity_gap",
  ]);
  const hooks = new Set([
    "none",
    "question_led",
    "why_explanation",
    "before_buying",
    "comparison",
    "demonstration",
    "first_person",
    "numbered",
    "concise",
  ]);
  const expectedPrimaryHook = context.hook_patterns[0] || "none";
  return categoryMaturities.has(match[1]) &&
    competitorCoverages.has(match[2]) &&
    structuralSignals.has(match[3]) &&
    angles.has(match[4]) &&
    hooks.has(match[5]) &&
    match[4] === context.creative_angle &&
    match[5] === expectedPrimaryHook;
}

function generationRepairPromptRequirements(
  guardCodes: unknown,
  model: GenerationModel,
): string[] | null {
  if (
    !Array.isArray(guardCodes) ||
    guardCodes.length < 1 ||
    guardCodes.length > 3 ||
    new Set(guardCodes).size !== guardCodes.length
  ) {
    return null;
  }
  const photo = model === "seedream5_lite";
  const requirements = photo
    ? {
      product_fidelity:
        "QA: точная геометрия, этикетка, текст, цвет и пропорции.",
      technical_stability:
        "QA: резкий товар, ровный свет, без пересвета и размытия.",
      hook_clarity: "QA: товар считывается первым.",
      visual_quality: "QA: чистые края без дублей, деформаций и AI-артефактов.",
      trust: "QA: естественные материалы, свет и масштаб.",
      platform_fit: "QA: мастер 1:1, безопасные поля.",
    }
    : {
      product_fidelity:
        "QA: упаковка без морфинга; постоянны этикетка, цвет, текст и пропорции.",
      technical_stability:
        "QA: стабильный проход без чёрных кадров, скачков и мерцания.",
      audio_quality:
        "QA: слышимая чистая речь без тишины, клиппинга и рассинхронизации.",
      speech_fidelity:
        "QA: реплика произносится дословно, без пропусков, замен и новых слов.",
      hook_clarity:
        "QA: точный товар и одно действие видны в первые 2 секунды.",
      visual_quality:
        "QA: руки, лицо и фактуры без деформаций, дублей и мерцания.",
      trust: "QA: естественная подача без гиперболы и новых обещаний.",
      platform_fit: "QA: мастер 9:16; товар и лицо в безопасных полях.",
    };
  const result: string[] = [];
  for (const code of guardCodes) {
    if (typeof code !== "string") return null;
    if (
      ["audio_quality", "speech_fidelity"].includes(code) &&
      !generationModelSupportsAudio(model)
    ) return null;
    const requirement = requirements[code as keyof typeof requirements];
    if (typeof requirement !== "string") return null;
    result.push(requirement);
  }
  return result;
}

function generationRepairPromptIsBound(
  policy: unknown,
  payload: StartPayload,
): boolean {
  if (!isRecord(policy) || policy.applied !== true) return false;
  const requirements = generationRepairPromptRequirements(
    policy.guard_codes,
    payload.model,
  );
  return requirements !== null &&
    requirements.every((requirement) => payload.brief.includes(requirement));
}

function readStatusPayload(value: unknown): StatusPayload | null {
  if (!isRecord(value)) return null;
  const required = new Set([
    "action",
    "organization_id",
    "project_id",
    "job_id",
  ]);
  if (
    !hasOnlyKeys(value, required) || Object.keys(value).length !== required.size
  ) {
    return null;
  }
  if (
    value.action !== "status" || !isUuid(value.organization_id) ||
    !isUuid(value.project_id) || !isUuid(value.job_id)
  ) {
    return null;
  }
  return value as StatusPayload;
}

function readReconcilePayload(value: unknown): ReconcilePayload | null {
  if (!isRecord(value)) return null;
  const required = new Set([
    "action",
    "organization_id",
    "project_id",
    "job_id",
    "incident_id",
    "idempotency_key",
    "resolution",
    "evidence_reference",
    "reason",
    "confirmation",
  ]);
  const allowed = new Set([...required, "provider_task_id"]);
  if (
    !hasOnlyKeys(value, allowed) ||
    ![...required].every((key) => Object.hasOwn(value, key))
  ) {
    return null;
  }
  const attach = value.resolution === "attach_existing_task";
  const noSubmission = value.resolution === "confirm_no_submission";
  if (
    value.action !== "reconcile" ||
    !isUuid(value.organization_id) ||
    !isUuid(value.project_id) ||
    !isUuid(value.job_id) ||
    !isUuid(value.incident_id) ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key) ||
    (!attach && !noSubmission) ||
    !isBoundedText(value.evidence_reference, 8, 500) ||
    !isBoundedText(value.reason, 20, 1_000) ||
    (attach && (
      (!isValidTaskId(value.provider_task_id) &&
        !isValidGoogleOperationName(value.provider_task_id)) ||
      !new Set([
        "RUNWAY_TASK_ID_VERIFIED",
        "GOOGLE_OPERATION_ID_VERIFIED",
      ]).has(String(value.confirmation || ""))
    )) ||
    (noSubmission && (
      Object.hasOwn(value, "provider_task_id") ||
      !new Set([
        "RUNWAY_NO_TASK_VERIFIED",
        "GOOGLE_NO_OPERATION_VERIFIED",
      ]).has(String(value.confirmation || ""))
    ))
  ) {
    return null;
  }
  return value as ReconcilePayload;
}

function rpcPayload(payload: StartPayload | StatusPayload): Json {
  const {
    action: _action,
    ...rest
  } = payload;
  if ("learning_opt_out" in rest) {
    delete (rest as Partial<StartPayload>).learning_opt_out;
  }
  return rest as Json;
}

function publicRatioFromProvider(
  model: GenerationModel,
  providerRatio: unknown,
  resolution: unknown,
): CommonStartPayload["format"] | null {
  if (typeof providerRatio !== "string" || typeof resolution !== "string") {
    return null;
  }
  const ratios = generationCatalogEntryForModel(model)
    ?.server?.providerRatios?.[resolution];
  if (!isRecord(ratios)) return null;
  for (const [publicRatio, exactProviderRatio] of Object.entries(ratios)) {
    if (exactProviderRatio === providerRatio) {
      return publicRatio as CommonStartPayload["format"];
    }
  }
  return null;
}

function readGenerationSku(
  job: Record<string, unknown>,
  persistedByAuthoritativeRpc: boolean,
): {
  provider: GenerationProvider;
  model: GenerationModel;
  inputMode: "image";
  durationSeconds: number;
  resolution: GenerationResolution;
  audio: boolean;
  lastFrame: boolean;
  ratio: string;
  estimatedCostMinor: number;
  estimatedCredits: number | null;
} | null {
  const provider = readGenerationProvider(job.provider);
  const model = readGenerationModel(provider, job.model);
  const legacyResolution = model === "seedream5_lite" ? "2K" : "720p";
  const resolution = typeof job.resolution === "string"
    ? job.resolution
    : legacyResolution;
  const publicRatio = model === null
    ? null
    : publicRatioFromProvider(model, job.ratio, resolution);
  if (provider === null || model === null || publicRatio === null) return null;
  const referenceCount = isIntegerInRange(job.reference_image_count, 0, 5)
    ? job.reference_image_count
    : model === "seedream5_lite" || model === "seedance2_fast" ||
        model === "seedance2_mini"
    ? 1
    : 0;
  const mediaCount = referenceCount > 0
    ? referenceCount
    : job.last_frame === true
    ? 2
    : 1;
  const exact = exactGenerationSku(
    provider,
    model,
    job.duration_seconds,
    publicRatio,
    resolution,
    job.audio === true,
    job.last_frame === true,
    mediaCount,
    providerFeatureFlags(
      provider,
      persistedByAuthoritativeRpc && provider === "google",
    ),
  );
  if (
    exact === null || job.estimated_cost_minor !== exact.estimatedCostMinor ||
    job.estimated_credits !== exact.estimatedCredits
  ) return null;
  const entry = generationModelCatalogEntry(provider, model);
  const providerRatio = entry?.server?.providerRatios?.[exact.resolution]
    ?.[exact.format];
  if (typeof providerRatio !== "string" || job.ratio !== providerRatio) {
    return null;
  }
  return { ...exact, ratio: providerRatio };
}

function readStartJob(value: unknown): StartJob | null {
  if (!isRecord(value)) return null;
  const batch = value.batch;
  const job = value.job;
  if (value.ok !== true || !isRecord(batch) || !isRecord(job)) return null;
  if (
    !isUuid(batch.id) || typeof batch.status !== "string" ||
    !isUuid(batch.campaign_id)
  ) return null;
  // The start RPC has already applied the immutable provider policy and
  // receipt gates. This flag only lets the pure catalog parse that persisted
  // Google SKU; it is never used as launch authorization.
  const sku = readGenerationSku(job, true);
  const reviewAutostartConfirmed = job.review_autostart_confirmed === true;
  const reviewAutostartTermsVersion =
    typeof job.review_autostart_terms_version === "string"
      ? job.review_autostart_terms_version
      : null;
  const referenceObjectNames = Array.isArray(job.reference_object_names)
    ? job.reference_object_names
    : [job.input_object_name];
  if (
    !isUuid(job.id) || !isUuid(job.batch_id) || job.batch_id !== batch.id ||
    !isUuid(job.campaign_id) || !isBoundedText(job.campaign_name, 2, 160) ||
    job.campaign_id !== batch.campaign_id ||
    typeof job.status !== "string" || !JOB_STATUSES.has(job.status) ||
    sku === null || job.provider !== sku.provider ||
    !isBoundedText(
      job.prompt_text,
      1,
      Number(
        generationModelCatalogEntry(sku.provider, sku.model)?.promptLimit || 0,
      ),
    ) ||
    !isObjectName(job.input_object_name) ||
    referenceObjectNames.length < 1 ||
    referenceObjectNames.length > 5 ||
    referenceObjectNames.some((objectName) => !isObjectName(objectName)) ||
    referenceObjectNames[0] !== job.input_object_name ||
    new Set(referenceObjectNames).size !== referenceObjectNames.length ||
    !isObjectName(job.output_object_name) ||
    !isIntegerInRange(job.estimated_cost_minor, 0, 1_000_000) ||
    (job.estimated_credits !== null &&
      !isIntegerInRange(job.estimated_credits, 0, 1_000_000)) ||
    typeof job.review_autostart_confirmed !== "boolean" ||
    (
      reviewAutostartConfirmed &&
      reviewAutostartTermsVersion !==
        "generated-video-qa-autostart-v1"
    ) ||
    (
      !reviewAutostartConfirmed &&
      reviewAutostartTermsVersion !== null
    )
  ) {
    return null;
  }
  return {
    id: job.id,
    batchId: job.batch_id,
    campaignId: job.campaign_id,
    campaignName: job.campaign_name,
    status: job.status,
    provider: sku.provider,
    model: sku.model,
    inputMode: "image",
    durationSeconds: sku.durationSeconds,
    resolution: sku.resolution,
    audio: sku.audio,
    lastFrame: sku.lastFrame,
    ratio: sku.ratio,
    promptText: job.prompt_text,
    inputObjectName: job.input_object_name,
    referenceObjectNames: referenceObjectNames as string[],
    outputObjectName: job.output_object_name,
    estimatedCostMinor: sku.estimatedCostMinor,
    estimatedCredits: sku.estimatedCredits,
    reviewAutostartConfirmed,
    reviewAutostartTermsVersion,
  };
}

type ProviderRequestEnvelope = {
  provider: "runway" | "google";
  endpointPath: string;
  method: "POST";
  body: Record<string, Json>;
  pollKind: "runway_task" | "google_long_running_operation";
};

export function buildGenerationStrategyProviderRequest(
  context: GenerationStrategyRecipeContext,
  signedRoleAssets: GenerationStrategySignedRoleAsset[],
): ProviderRequestEnvelope | null {
  const entry = generationStrategyCatalogEntry(context.strategyId);
  if (
    entry === null || entry.provider !== "runway" ||
    entry.recipe !== context.recipe ||
    entry.recipe_version !== context.recipeVersion ||
    !RUNWAY_PROVIDER_ENDPOINTS.has(entry.server.provider_path) ||
    !Array.isArray(signedRoleAssets) || signedRoleAssets.length < 1
  ) return null;

  const mappedAssets: Array<Record<string, string>> = [];
  let productIndex = 0;
  for (const asset of signedRoleAssets) {
    if (!isRecord(asset)) return null;
    const withView = Object.hasOwn(asset, "view");
    const allowedFields = new Set(
      withView ? ["role", "uri", "view"] : ["role", "uri"],
    );
    if (
      !hasOnlyKeys(asset, allowedFields) ||
      Object.keys(asset).length !== allowedFields.size
    ) return null;

    if (context.recipe === "product_ugc") {
      if (withView) return null;
      if (asset.role === "avatar_image") {
        mappedAssets.push({ role: "avatar", uri: String(asset.uri) });
      } else if (asset.role === "product_image") {
        mappedAssets.push({ role: "product_primary", uri: String(asset.uri) });
      } else {
        // The source video is mechanics-only for Product UGC and is never
        // accepted as a signed provider input.
        return null;
      }
    } else if (context.recipe === "product_swap") {
      if (asset.role === "source_video") {
        if (withView) return null;
        mappedAssets.push({ role: "source_video", uri: String(asset.uri) });
      } else if (asset.role === "original_product_image") {
        if (withView) return null;
        mappedAssets.push({
          role: "original_product",
          uri: String(asset.uri),
        });
      } else if (asset.role === "new_product_image") {
        mappedAssets.push({
          role: productIndex++ === 0 ? "product_primary" : "product_reference",
          uri: String(asset.uri),
          ...(withView ? { view: String(asset.view) } : {}),
        });
      } else {
        return null;
      }
    } else if (asset.role === "product_image") {
      mappedAssets.push({
        role: productIndex++ === 0 ? "product_primary" : "product_reference",
        uri: String(asset.uri),
        ...(withView ? { view: String(asset.view) } : {}),
      });
    } else if (asset.role === "style_image") {
      mappedAssets.push({
        role: "style_reference",
        uri: String(asset.uri),
        ...(withView ? { view: String(asset.view) } : {}),
      });
    } else {
      // Product Ad consumes the source only through server-compiled mechanics
      // in userConcept; it must never receive the source video URI.
      return null;
    }
  }

  const commonSelection = {
    strategyVersion: context.strategyVersion,
    strategyId: context.strategyId,
    recipe: context.recipe,
    recipeVersion: context.recipeVersion,
    durationSeconds: context.durationSeconds,
    audio: context.audio,
  };
  const selection = context.recipe === "product_swap"
    ? { ...commonSelection, resolution: context.resolution }
    : {
      ...commonSelection,
      ratio: context.ratio,
      productInfo: context.productInfo,
      userConcept: context.userConcept,
    };
  try {
    const envelope = buildRunwayRecipeRequest(selection, mappedAssets);
    if (
      envelope?.provider !== "runway" || envelope.method !== "POST" ||
      envelope.pollKind !== "runway_task" ||
      envelope.endpointPath !== entry.server.provider_path ||
      !RUNWAY_PROVIDER_ENDPOINTS.has(envelope.endpointPath) ||
      !isRecord(envelope.body)
    ) return null;
    return envelope as ProviderRequestEnvelope;
  } catch {
    return null;
  }
}

function buildProviderRequest(
  job: StartJob,
  signedReferenceUrls: string[],
  googleInlineImages: Array<{
    mimeType: "image/png" | "image/jpeg" | "image/webp";
    data: string;
  }> = [],
  featureFlags: Record<string, boolean> = {},
): ProviderRequestEnvelope | null {
  const entry = generationModelCatalogEntry(job.provider, job.model);
  const ratio = publicRatioFromProvider(job.model, job.ratio, job.resolution);
  if (!entry || ratio === null || signedReferenceUrls.length < 1) return null;

  const photo = job.model === "seedream5_lite";
  const seedance = job.model === "seedance2_fast" ||
    job.model === "seedance2_mini";
  const referenceImageCount = photo || seedance
    ? signedReferenceUrls.length
    : 0;
  const selected = validateGenerationModelSelection(entry, {
    inputMode: "image",
    durationSeconds: job.durationSeconds,
    ratio,
    resolution: job.resolution,
    audio: job.audio,
    spokenDialogue: job.audio,
    referenceImageCount,
    referenceVideo: false,
    firstFrame: !photo && !seedance,
    lastFrame: job.lastFrame,
  }, { featureFlags });
  if (!selected.ok) return null;

  const input = job.provider === "google"
    ? googleInlineImages.length === signedReferenceUrls.length
      ? {
        promptText: job.promptText,
        imageInlineData: googleInlineImages[0],
        ...(job.lastFrame
          ? { lastFrameInlineData: googleInlineImages[1] }
          : {}),
      }
      : null
    : photo || seedance
    ? {
      promptText: job.promptText,
      referenceImageUrls: signedReferenceUrls,
    }
    : {
      promptText: job.promptText,
      firstFrameUrl: signedReferenceUrls[0],
      ...(job.lastFrame ? { lastFrameUrl: signedReferenceUrls[1] } : {}),
    };
  if (input === null) return null;
  try {
    const envelope = buildGenerationProviderRequest(entry, selected, input);
    if (
      envelope?.provider !== job.provider ||
      envelope.method !== "POST" ||
      envelope.pollKind !==
        (job.provider === "google"
          ? "google_long_running_operation"
          : "runway_task") ||
      (job.provider === "runway" &&
        !RUNWAY_PROVIDER_ENDPOINTS.has(envelope.endpointPath)) ||
      (job.provider === "google" &&
        envelope.endpointPath !==
          `/v1beta/models/${GOOGLE_VEO_LITE_MODEL}:predictLongRunning`) ||
      !isRecord(envelope.body) ||
      typeof envelope.endpointPath !== "string"
    ) return null;
    return envelope as ProviderRequestEnvelope;
  } catch {
    return null;
  }
}

function readStatusJob(value: unknown): StatusJob | null {
  if (!isRecord(value) || value.ok !== true || !isRecord(value.job)) {
    return null;
  }
  const job = value.job;
  const providerTaskId = job.provider_task_id;
  const actualCostMinor = job.actual_cost_minor;
  const outputMediaId = job.output_media_id;
  const failureCode = job.failure_code;
  const submissionState = job.submission_state;
  const reconciliationIncidentId = job.reconciliation_incident_id;
  const reconciliationRequiredAt = job.reconciliation_required_at;
  const reconciliationReasonCode = job.reconciliation_reason_code;
  const reconciliationResolution = job.reconciliation_resolution;
  const reviewAutostartConfirmed = job.review_autostart_confirmed === true;
  const reviewAutostartTermsVersion =
    typeof job.review_autostart_terms_version === "string"
      ? job.review_autostart_terms_version
      : null;
  // Status must remain readable for an already-authorized Google job even if
  // the organization later disables new launches.
  const sku = readGenerationSku(job, true);
  if (
    !isUuid(job.id) || !isUuid(job.batch_id) ||
    !isUuid(job.campaign_id) || !isBoundedText(job.campaign_name, 2, 160) ||
    typeof job.status !== "string" || !JOB_STATUSES.has(job.status) ||
    sku === null || job.provider !== sku.provider ||
    (providerTaskId !== null &&
      !isValidProviderTaskId(sku.provider, providerTaskId)) ||
    !isIntegerInRange(job.estimated_cost_minor, 0, 1_000_000) ||
    (job.estimated_credits !== null &&
      !isIntegerInRange(job.estimated_credits, 0, 1_000_000)) ||
    (actualCostMinor !== null &&
      !isIntegerInRange(actualCostMinor, 0, 1_000_000)) ||
    !isObjectName(job.output_object_name) ||
    (outputMediaId !== null && !isUuid(outputMediaId)) ||
    (failureCode !== null &&
      (typeof failureCode !== "string" || !FAILURE_CODES.has(failureCode))) ||
    (submissionState !== null &&
      (typeof submissionState !== "string" ||
        !["unknown", "confirmed_submitted", "confirmed_not_submitted"].includes(
          submissionState,
        ))) ||
    typeof job.reconciliation_required !== "boolean" ||
    (reconciliationIncidentId !== null &&
      !isUuid(reconciliationIncidentId)) ||
    (reconciliationRequiredAt !== null &&
      (typeof reconciliationRequiredAt !== "string" ||
        !Number.isFinite(Date.parse(reconciliationRequiredAt)))) ||
    (reconciliationReasonCode !== null &&
      !isBoundedText(reconciliationReasonCode, 8, 80)) ||
    (reconciliationResolution !== null &&
      (typeof reconciliationResolution !== "string" ||
        !["attach_existing_task", "confirm_no_submission"].includes(
          reconciliationResolution,
        ))) ||
    typeof job.can_reconcile !== "boolean" ||
    typeof job.review_autostart_confirmed !== "boolean" ||
    (
      reviewAutostartConfirmed &&
      reviewAutostartTermsVersion !==
        "generated-video-qa-autostart-v1"
    ) ||
    (
      !reviewAutostartConfirmed &&
      reviewAutostartTermsVersion !== null
    ) ||
    typeof job.updated_at !== "string" ||
    !Number.isFinite(Date.parse(job.updated_at))
  ) {
    return null;
  }
  return {
    id: job.id,
    batchId: job.batch_id,
    campaignId: job.campaign_id,
    campaignName: job.campaign_name,
    status: job.status,
    provider: sku.provider,
    providerTaskId,
    model: sku.model,
    inputMode: "image",
    durationSeconds: sku.durationSeconds,
    resolution: sku.resolution,
    audio: sku.audio,
    lastFrame: sku.lastFrame,
    ratio: sku.ratio,
    estimatedCostMinor: sku.estimatedCostMinor,
    estimatedCredits: sku.estimatedCredits,
    actualCostMinor,
    outputObjectName: job.output_object_name,
    outputMediaId,
    failureCode,
    submissionState,
    reconciliationRequired: job.reconciliation_required,
    reconciliationIncidentId,
    reconciliationRequiredAt,
    reconciliationReasonCode,
    reconciliationResolution,
    canReconcile: job.can_reconcile,
    reviewAutostartConfirmed,
    reviewAutostartTermsVersion,
    updatedAt: job.updated_at,
  };
}

function nullableString(
  value: Record<string, unknown>,
  key: string,
): string | null {
  return typeof value[key] === "string" ? value[key] as string : null;
}

function readInternalStatusRow(value: unknown): StatusJob | null {
  if (
    !isRecord(value) || !isRecord(value.input) || !isRecord(value.output)
  ) {
    return null;
  }
  const input = value.input;
  const output = value.output;
  const billing = isRecord(input.billing) ? input.billing : {};
  return readStatusJob({
    ok: true,
    job: {
      id: value.id,
      batch_id: value.batch_id,
      campaign_id: value.campaign_id,
      campaign_name: value.campaign_name,
      status: value.status,
      provider: value.provider,
      provider_task_id: nullableString(output, "provider_task_id"),
      model: input.model,
      input_mode: input.input_mode,
      duration_seconds: input.duration_seconds,
      resolution: input.resolution,
      audio: input.audio === true,
      last_frame: input.last_frame === true,
      ratio: input.ratio,
      estimated_cost_minor: value.estimated_cost_minor,
      estimated_credits: billing.estimated_credits,
      actual_cost_minor: value.actual_cost_minor,
      output_object_name: input.output_object_name,
      output_media_id: nullableString(output, "output_media_id"),
      failure_code: nullableString(output, "failure_code"),
      submission_state: nullableString(output, "submission_state"),
      reconciliation_required: output.reconciliation_required === true,
      reconciliation_incident_id: nullableString(
        output,
        "reconciliation_incident_id",
      ),
      reconciliation_required_at: nullableString(
        output,
        "reconciliation_required_at",
      ),
      reconciliation_reason_code: nullableString(
        output,
        "reconciliation_reason_code",
      ),
      reconciliation_resolution: nullableString(
        output,
        "reconciliation_resolution",
      ),
      can_reconcile: false,
      review_autostart_confirmed: false,
      review_autostart_terms_version: null,
      updated_at: value.updated_at,
    },
  });
}

function readReconciliationContext(
  value: unknown,
  payload: ReconcilePayload,
): ReconciliationContext | null {
  if (
    !isRecord(value) || value.ok !== true || !isUuid(value.actor_id) ||
    !isRecord(value.job)
  ) {
    return null;
  }
  const job = value.job;
  if (
    job.id !== payload.job_id ||
    job.organization_id !== payload.organization_id ||
    job.project_id !== payload.project_id ||
    job.status !== "starting" ||
    readGenerationProvider(job.provider) === null ||
    job.reconciliation_incident_id !== payload.incident_id ||
    typeof job.starting_at !== "string" ||
    !Number.isFinite(Date.parse(job.starting_at)) ||
    typeof job.reconciliation_required_at !== "string" ||
    !Number.isFinite(Date.parse(job.reconciliation_required_at))
  ) {
    return null;
  }
  return {
    actorId: value.actor_id,
    incidentId: job.reconciliation_incident_id,
    provider: job.provider as GenerationProvider,
    startingAt: job.starting_at,
    requiredAt: job.reconciliation_required_at,
  };
}

function safeJob(job: StatusJob): SafeJob {
  return {
    id: job.id,
    batch_id: job.batchId,
    campaign_id: job.campaignId,
    campaign_name: job.campaignName,
    status: job.status,
    provider: job.provider,
    provider_task_id: job.providerTaskId,
    model: job.model,
    input_mode: job.inputMode,
    duration_seconds: job.durationSeconds,
    resolution: job.resolution,
    audio: job.audio,
    last_frame: job.lastFrame,
    ratio: job.ratio,
    estimated_cost_minor: job.estimatedCostMinor,
    estimated_credits: job.estimatedCredits,
    actual_cost_minor: job.actualCostMinor,
    output_object_name: job.outputObjectName,
    output_media_id: job.outputMediaId,
    failure_code: job.failureCode,
    submission_state: job.submissionState,
    reconciliation_required: job.reconciliationRequired,
    reconciliation_incident_id: job.reconciliationIncidentId,
    reconciliation_required_at: job.reconciliationRequiredAt,
    reconciliation_reason_code: job.reconciliationReasonCode,
    reconciliation_resolution: job.reconciliationResolution,
    can_reconcile: job.canReconcile,
    review_autostart_confirmed: job.reviewAutostartConfirmed,
    review_autostart_terms_version: job.reviewAutostartTermsVersion,
    updated_at: job.updatedAt,
  };
}

function isValidTaskId(value: unknown): value is string {
  return typeof value === "string" && TASK_ID_PATTERN.test(value);
}

function isValidGoogleOperationName(value: unknown): value is string {
  return typeof value === "string" &&
    GOOGLE_OPERATION_NAME_PATTERN.test(value);
}

function isValidProviderTaskId(
  provider: GenerationProvider,
  value: unknown,
): value is string {
  return provider === "google"
    ? isValidGoogleOperationName(value)
    : isValidTaskId(value);
}

function runwaySecret(): string | null {
  const value = Deno.env.get("RUNWAYML_API_SECRET") ?? "";
  if (
    value.length < 16 || value.length > 512 || value !== value.trim() ||
    hasForbiddenControl(value, false)
  ) {
    return null;
  }
  return value;
}

function googleApiKey(): string | null {
  const value = Deno.env.get("GEMINI_API_KEY") ?? "";
  if (
    value.length < 20 || value.length > 512 || value !== value.trim() ||
    hasForbiddenControl(value, false)
  ) return null;
  return value;
}

function readNonNegativeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : null;
}

type GenerationStrategyReadinessCheck = {
  credentialConfigured: boolean;
  providerAuthenticationConfirmed: boolean;
  balanceSufficient: boolean;
  failureCode:
    | "provider_configuration_error"
    | "provider_authentication_failed"
    | "provider_balance_insufficient"
    | "provider_readiness_unavailable"
    | null;
};

async function checkRunwayStrategyReadiness(
  secret: string | null,
  estimatedCredits: number,
): Promise<GenerationStrategyReadinessCheck> {
  if (secret === null) {
    return {
      credentialConfigured: false,
      providerAuthenticationConfirmed: false,
      balanceSufficient: false,
      failureCode: "provider_configuration_error",
    };
  }
  let response: ProviderJsonResult;
  try {
    response = await fetchProviderJsonWithDeadline(
      `${RUNWAY_API_ORIGIN}/v1/organization`,
      {
        method: "GET",
        redirect: "manual",
        headers: {
          authorization: `Bearer ${secret}`,
          "x-runway-version": RUNWAY_API_VERSION,
        },
      },
      PROVIDER_TIMEOUT_MS,
    );
  } catch {
    return {
      credentialConfigured: true,
      providerAuthenticationConfirmed: false,
      balanceSufficient: false,
      failureCode: "provider_readiness_unavailable",
    };
  }
  if (!response.ok) {
    return {
      credentialConfigured: true,
      providerAuthenticationConfirmed: false,
      balanceSufficient: false,
      failureCode: response.status === 401 || response.status === 403
        ? "provider_authentication_failed"
        : "provider_readiness_unavailable",
    };
  }
  const balance = isRecord(response.value)
    ? readNonNegativeNumber(response.value.creditBalance)
    : null;
  if (balance === null) {
    return {
      credentialConfigured: true,
      providerAuthenticationConfirmed: false,
      balanceSufficient: false,
      failureCode: "provider_readiness_unavailable",
    };
  }
  const sufficient = balance >= estimatedCredits;
  return {
    credentialConfigured: true,
    providerAuthenticationConfirmed: true,
    balanceSufficient: sufficient,
    failureCode: sufficient ? null : "provider_balance_insufficient",
  };
}

function readGenerationStrategyRpcError(value: unknown): {
  code: string;
  status: 403 | 409 | 422 | 503;
} | null {
  if (!isRecord(value) || typeof value.message !== "string") return null;
  const code = value.message.trim();
  if (!/^generation_strategy_[a-z0-9_]{3,110}$/u.test(code)) return null;
  if (code.endsWith("_access_required") || code.endsWith("_forbidden")) {
    return { code, status: 403 };
  }
  if (code.endsWith("_payload_invalid")) return { code, status: 422 };
  if (
    code.includes("_conflict") || code.includes("_not_current") ||
    code.includes("_expired") || code.includes("_consumed") ||
    code.includes("_required") || code.includes("_not_ready")
  ) return { code, status: 409 };
  return { code: "generation_unavailable", status: 503 };
}

function runwayProviderReadiness(
  payload: PreflightPayload,
  readiness: RunwayProviderReadiness,
): ProviderReadiness {
  const sku = exactGenerationSku(
    "runway",
    payload.model,
    payload.duration_seconds,
    payload.format,
    payload.resolution,
    payload.audio,
    payload.last_frame,
    payload.last_frame ? 2 : 1,
  );
  if (sku === null) {
    return {
      ready: false,
      provider: "runway",
      model: payload.model,
      inputMode: "image",
      durationSeconds: payload.duration_seconds,
      format: payload.format,
      resolution: payload.resolution,
      audio: payload.audio,
      lastFrame: payload.last_frame,
      estimatedCostMinor: 0,
      estimatedCredits: 0,
      credentialConfigured: true,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      spendConfirmation: "",
      failureCode: "provider_request_rejected",
    };
  }
  return {
    ready: readiness.ready,
    provider: "runway",
    model: payload.model,
    inputMode: "image",
    durationSeconds: sku.durationSeconds,
    format: sku.format,
    resolution: sku.resolution,
    audio: sku.audio,
    lastFrame: sku.lastFrame,
    estimatedCostMinor: sku.estimatedCostMinor,
    estimatedCredits: sku.estimatedCredits,
    credentialConfigured: true,
    balanceSufficient: readiness.balanceSufficient,
    modelAvailable: readiness.modelAvailable,
    dailyQuotaAvailable: readiness.dailyQuotaAvailable,
    spendConfirmation: sku.confirmation,
    ...(readiness.ready ? {} : { failureCode: readiness.failureCode }),
  };
}

function parseRunwayOrganizationReadiness(
  value: unknown,
  model: RunwayModel,
  durationSeconds: number,
  estimatedCredits: number,
): RunwayProviderReadinessSnapshot | null {
  if (!isRecord(value) || !isRecord(value.tier) || !isRecord(value.usage)) {
    return null;
  }
  const creditBalance = readNonNegativeNumber(value.creditBalance);
  const tierModels = value.tier.models;
  const usageModels = value.usage.models;
  if (
    creditBalance === null ||
    !isRecord(tierModels) ||
    !isRecord(usageModels)
  ) {
    return null;
  }
  const tierModel = tierModels[model];
  const usageModel = usageModels[model];
  const maxDaily = isRecord(tierModel)
    ? readNonNegativeNumber(tierModel.maxDailyGenerations)
    : null;
  const dailyGenerations = isRecord(usageModel)
    ? readNonNegativeNumber(usageModel.dailyGenerations)
    : 0;
  if (!Number.isSafeInteger(estimatedCredits) || estimatedCredits < 0) {
    return null;
  }
  const modelAvailable = maxDaily !== null && maxDaily > 0;
  const balanceSufficient = creditBalance >= estimatedCredits;
  const dailyQuotaAvailable = modelAvailable &&
    dailyGenerations !== null && dailyGenerations < maxDaily;
  return {
    ready: balanceSufficient && modelAvailable && dailyQuotaAvailable,
    model,
    durationSeconds,
    estimatedCredits,
    balanceSufficient,
    modelAvailable,
    dailyQuotaAvailable,
  };
}

async function checkRunwayProviderReadiness(
  secret: string,
  sku: ExactGenerationSku,
): Promise<RunwayProviderReadiness> {
  if (
    sku.provider !== "runway" ||
    !Number.isSafeInteger(sku.estimatedCredits)
  ) {
    return {
      ready: false,
      model: sku.model as RunwayModel,
      durationSeconds: sku.durationSeconds,
      estimatedCredits: 0,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: "provider_request_rejected",
    };
  }
  const model = sku.model as RunwayModel;
  const durationSeconds = sku.durationSeconds;
  const estimatedCredits = sku.estimatedCredits as number;
  let response: ProviderJsonResult;
  try {
    response = await fetchProviderJsonWithDeadline(
      `${RUNWAY_API_ORIGIN}/v1/organization`,
      {
        method: "GET",
        redirect: "manual",
        headers: {
          authorization: `Bearer ${secret}`,
          "x-runway-version": RUNWAY_API_VERSION,
        },
      },
      PROVIDER_TIMEOUT_MS,
    );
  } catch (error) {
    return {
      ready: false,
      model,
      durationSeconds,
      estimatedCredits,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: error instanceof ProviderResponseInvalidError
        ? "provider_response_invalid"
        : "provider_request_failed",
    };
  }
  if (!response.ok) {
    return {
      ready: false,
      model,
      durationSeconds,
      estimatedCredits,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: providerFailureForHttp(response.status),
    };
  }
  const parsed = parseRunwayOrganizationReadiness(
    response.value,
    model,
    durationSeconds,
    estimatedCredits,
  );
  if (parsed === null) {
    return {
      ready: false,
      model,
      durationSeconds,
      estimatedCredits,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: "provider_response_invalid",
    };
  }
  if (parsed.ready) {
    return {
      ...parsed,
      ready: true,
      balanceSufficient: true,
      modelAvailable: true,
      dailyQuotaAvailable: true,
    };
  }
  return {
    ...parsed,
    ready: false,
    failureCode: !parsed.modelAvailable
      ? "provider_request_rejected"
      : !parsed.balanceSufficient
      ? "provider_credits_unavailable"
      : "provider_rate_limited",
  };
}

async function checkGoogleProviderReadiness(
  apiKey: string,
  payload: PreflightPayload,
  sku: ExactGenerationSku,
): Promise<ProviderReadiness> {
  if (
    sku.provider !== "google" || sku.model !== payload.model ||
    sku.durationSeconds !== payload.duration_seconds ||
    sku.format !== payload.format || sku.resolution !== payload.resolution ||
    sku.audio !== payload.audio || sku.lastFrame !== payload.last_frame
  ) {
    throw new Error("provider_request_rejected");
  }
  let response: ProviderJsonResult;
  try {
    response = await fetchProviderJsonWithDeadline(
      `${GOOGLE_GENERATIVE_LANGUAGE_API_ORIGIN}/${GOOGLE_GENERATIVE_LANGUAGE_API_VERSION}/models/${GOOGLE_VEO_LITE_MODEL}`,
      {
        method: "GET",
        redirect: "manual",
        headers: { "x-goog-api-key": apiKey },
      },
      PROVIDER_TIMEOUT_MS,
    );
  } catch (error) {
    return {
      ...sku,
      ready: false,
      credentialConfigured: true,
      balanceSufficient: null,
      modelAvailable: false,
      dailyQuotaAvailable: null,
      spendConfirmation: sku.confirmation,
      failureCode: error instanceof ProviderResponseInvalidError
        ? "provider_response_invalid"
        : "provider_request_failed",
    };
  }
  if (!response.ok) {
    return {
      ...sku,
      ready: false,
      credentialConfigured: true,
      balanceSufficient: null,
      modelAvailable: false,
      dailyQuotaAvailable: null,
      spendConfirmation: sku.confirmation,
      failureCode: providerFailureForHttp(response.status),
    };
  }
  const value = response.value;
  const modelAvailable = isRecord(value) &&
    (value.name === `models/${GOOGLE_VEO_LITE_MODEL}` ||
      value.name === GOOGLE_VEO_LITE_MODEL) &&
    Array.isArray(value.supportedGenerationMethods) &&
    value.supportedGenerationMethods.includes("predictLongRunning");
  return {
    ...sku,
    ready: modelAvailable,
    credentialConfigured: true,
    balanceSufficient: null,
    modelAvailable,
    dailyQuotaAvailable: null,
    spendConfirmation: sku.confirmation,
    ...(modelAvailable ? {} : { failureCode: "provider_response_invalid" }),
  };
}

function parseProviderReadinessReceipt(
  value: unknown,
  payload: PreflightPayload,
  checkedBy: string,
  readiness: ProviderReadiness,
): ProviderReadinessReceipt | null {
  if (!isRecord(value)) return null;
  const specBound = generationModelRequiresReadinessV4(
    readiness.provider,
    readiness.model,
  );
  const expectedVersion = specBound
    ? PROVIDER_READINESS_RECEIPT_V4
    : PROVIDER_READINESS_RECEIPT_V3;
  const specContext = payload.generation_spec_context;
  const exactKeys = new Set([
    "version",
    "receipt_id",
    "receipt_hash",
    "organization_id",
    "checked_by",
    "provider",
    "model",
    "input_mode",
    "duration_seconds",
    "format",
    "resolution",
    "audio",
    "last_frame",
    "ready",
    "estimated_cost_minor",
    "estimated_credits",
    "credential_configured",
    "balance_sufficient",
    "model_available",
    "daily_quota_available",
    "failure_code",
    "catalog_version",
    "pricing_version",
    "learning_gate_version",
    "checked_at",
    "expires_at",
    "status",
    "fresh",
    "spend_confirmation",
    "automatic_generation",
    "automatic_spend",
    ...(specBound
      ? ["project_id", "spec_id", "spec_version", "spec_hash", "scope_hash"]
      : []),
  ]);
  const checkedAt = typeof value.checked_at === "string"
    ? value.checked_at
    : "";
  const expiresAt = typeof value.expires_at === "string"
    ? value.expires_at
    : "";
  const checkedAtMs = Date.parse(checkedAt);
  const expiresAtMs = Date.parse(expiresAt);
  const expectedFailure = readiness.ready ? null : readiness.failureCode;
  if (
    !hasOnlyKeys(value, exactKeys) ||
    Object.keys(value).length !== exactKeys.size ||
    value.version !== expectedVersion ||
    value.organization_id !== payload.organization_id ||
    value.checked_by !== checkedBy ||
    value.provider !== readiness.provider ||
    value.model !== readiness.model ||
    value.input_mode !== readiness.inputMode ||
    value.duration_seconds !== readiness.durationSeconds ||
    value.format !== readiness.format ||
    value.resolution !== readiness.resolution ||
    value.audio !== readiness.audio ||
    value.last_frame !== readiness.lastFrame ||
    value.ready !== readiness.ready ||
    value.estimated_cost_minor !== readiness.estimatedCostMinor ||
    value.estimated_credits !== readiness.estimatedCredits ||
    value.credential_configured !== readiness.credentialConfigured ||
    value.balance_sufficient !== readiness.balanceSufficient ||
    value.model_available !== readiness.modelAvailable ||
    value.daily_quota_available !== readiness.dailyQuotaAvailable ||
    value.failure_code !== expectedFailure ||
    value.catalog_version !== GENERATION_MODEL_CATALOG_VERSION ||
    value.pricing_version !==
      (readiness.provider === "google"
        ? GOOGLE_VEO_PRICING_VERSION
        : RUNWAY_PRICING_VERSION) ||
    value.learning_gate_version !== GENERATION_LEARNING_GATE_VERSION ||
    value.spend_confirmation !== readiness.spendConfirmation ||
    value.status !== (readiness.ready ? "ready" : "blocked") ||
    value.fresh !== true ||
    value.automatic_generation !== false ||
    value.automatic_spend !== false ||
    !isUuid(value.receipt_id) ||
    typeof value.receipt_hash !== "string" ||
    !SHA256_PATTERN.test(value.receipt_hash) ||
    !Number.isFinite(checkedAtMs) ||
    !Number.isFinite(expiresAtMs) ||
    checkedAtMs > Date.now() + 60_000 ||
    expiresAtMs <= checkedAtMs ||
    expiresAtMs - checkedAtMs !== 15 * 60_000 ||
    expiresAtMs <= Date.now() ||
    (specBound && (
      specContext === undefined ||
      value.project_id !== payload.project_id ||
      value.spec_id !== specContext.spec_id ||
      value.spec_version !== specContext.spec_version ||
      value.spec_hash !== specContext.spec_hash ||
      typeof value.scope_hash !== "string" ||
      !SHA256_PATTERN.test(value.scope_hash)
    ))
  ) {
    return null;
  }
  return {
    version: expectedVersion,
    receiptId: value.receipt_id,
    receiptHash: value.receipt_hash,
    checkedBy,
    checkedAt,
    expiresAt,
    ...(specBound
      ? {
        projectId: value.project_id as string,
        specId: value.spec_id as string,
        specVersion: value.spec_version as number,
        specHash: value.spec_hash as string,
        scopeHash: value.scope_hash as string,
      }
      : {}),
  };
}

async function withFetchDeadline<T>(
  input: string,
  init: RequestInit,
  timeoutMs: number,
  consume: (response: Response) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(input, { ...init, signal: controller.signal });
    // Unlike fetchWithTimeout, this deadline deliberately stays armed while
    // the response body is consumed. A CDN that sends headers and then stalls
    // must not strand an already-paid job in `processing` forever.
    return await consume(response);
  } finally {
    clearTimeout(timeout);
  }
}

class OperationDeadlineError extends Error {
  constructor() {
    super("operation_deadline_exceeded");
    this.name = "OperationDeadlineError";
  }
}

async function withOperationDeadline<T>(
  operation: PromiseLike<T>,
  timeoutMs: number,
): Promise<T> {
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      Promise.resolve(operation),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(
          () => reject(new OperationDeadlineError()),
          timeoutMs,
        );
      }),
    ]);
  } finally {
    if (timeout !== undefined) clearTimeout(timeout);
  }
}

class ResponseSizeInvalidError extends Error {
  constructor() {
    super("response_size_invalid");
    this.name = "ResponseSizeInvalidError";
  }
}

class ProviderResponseInvalidError extends Error {
  constructor() {
    super("provider_response_invalid");
    this.name = "ProviderResponseInvalidError";
  }
}

async function readBoundedBytes(
  response: Response,
  maximum: number,
): Promise<Uint8Array<ArrayBuffer>> {
  const declared = response.headers.get("content-length");
  if (declared !== null) {
    const size = Number(declared);
    if (!Number.isSafeInteger(size) || size < 0 || size > maximum) {
      throw new ResponseSizeInvalidError();
    }
  }
  return await readBoundedStream(response.body, maximum);
}

async function readBoundedStream(
  body: ReadableStream<Uint8Array> | null,
  maximum: number,
): Promise<Uint8Array<ArrayBuffer>> {
  if (body === null) throw new Error("response_body_missing");
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maximum) {
        await reader.cancel();
        throw new ResponseSizeInvalidError();
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const output = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

async function readProviderJson(response: Response): Promise<unknown> {
  try {
    const bytes = await readBoundedBytes(response, MAX_PROVIDER_JSON_BYTES);
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new ProviderResponseInvalidError();
  }
}

type ProviderJsonResult =
  | { ok: true; status: number; value: unknown }
  | { ok: false; status: number; value: null };

async function fetchProviderJsonWithDeadline(
  input: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<ProviderJsonResult> {
  return await withFetchDeadline(
    input,
    init,
    timeoutMs,
    async (response) => {
      if (!response.ok) {
        await response.body?.cancel();
        return { ok: false as const, status: response.status, value: null };
      }
      return {
        ok: true as const,
        status: response.status,
        value: await readProviderJson(response),
      };
    },
  );
}

function providerFailureForHttp(status: number): string {
  if (status === 401 || status === 403) {
    return "provider_authentication_failed";
  }
  if (status === 402) return "provider_credits_unavailable";
  if (status === 429) return "provider_rate_limited";
  if (status >= 400 && status < 500) return "provider_request_rejected";
  return "provider_request_failed";
}

type ProviderTaskFailure = {
  failureCode: string;
  providerFailureCode: string | null;
  billingOutcome: "refundable" | "non_refundable" | "unknown";
};

function providerTaskFailure(value: unknown): ProviderTaskFailure {
  const rawCode = isRecord(value) && typeof value.failureCode === "string"
    ? value.failureCode.trim().toLocaleUpperCase("en-US")
    : "";
  const providerFailureCode = /^[A-Z0-9][A-Z0-9._-]{0,159}$/u.test(rawCode)
    ? rawCode
    : null;
  let failureCode = "provider_task_failed";
  if (
    providerFailureCode?.includes("CREDITS") ||
    providerFailureCode?.includes("PAYMENT")
  ) {
    failureCode = "provider_credits_unavailable";
  } else if (providerFailureCode?.includes("RATE_LIMIT")) {
    failureCode = "provider_rate_limited";
  }

  // Runway documents SAFETY.INPUT.* and input-preprocessing safety failures
  // as non-refundable. Other task failures are refunded; an absent or
  // malformed provider code remains unknown and is never optimistically
  // refunded by our ledger.
  const billingOutcome = providerFailureCode === null
    ? "unknown"
    : providerFailureCode.startsWith("SAFETY.INPUT.") ||
        providerFailureCode === "INPUT_PREPROCESSING.SAFETY.TEXT"
    ? "non_refundable"
    : "refundable";
  return { failureCode, providerFailureCode, billingOutcome };
}

function isMp4(bytes: Uint8Array): boolean {
  return bytes.byteLength >= 12 && bytes[4] === 0x66 && bytes[5] === 0x74 &&
    bytes[6] === 0x79 && bytes[7] === 0x70;
}

function isPng(bytes: Uint8Array): boolean {
  if (
    bytes.byteLength < 24 ||
    !(
      bytes[0] === 0x89 && bytes[1] === 0x50 &&
      bytes[2] === 0x4e && bytes[3] === 0x47 &&
      bytes[4] === 0x0d && bytes[5] === 0x0a &&
      bytes[6] === 0x1a && bytes[7] === 0x0a
    ) ||
    bytes[12] !== 0x49 || bytes[13] !== 0x48 ||
    bytes[14] !== 0x44 || bytes[15] !== 0x52
  ) {
    return false;
  }
  const view = new DataView(
    bytes.buffer,
    bytes.byteOffset + 16,
    8,
  );
  return view.getUint32(0, false) === 2_048 &&
    view.getUint32(4, false) === 2_048;
}

async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((value) =>
    value.toString(16).padStart(2, "0")
  ).join("");
}

function validateRunwayOutputUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 2_048) return null;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" || url.hostname !== RUNWAY_OUTPUT_HOST ||
      (url.port !== "" && url.port !== "443") || url.username !== "" ||
      url.password !== ""
    ) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

function bytesToBase64(bytes: Uint8Array): string {
  const chunkSize = 0x8000;
  let binary = "";
  for (let offset = 0; offset < bytes.byteLength; offset += chunkSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(offset, offset + chunkSize),
    );
  }
  return btoa(binary);
}

async function readGoogleInlineImage(
  signedUrl: string,
): Promise<
  { mimeType: "image/png" | "image/jpeg" | "image/webp"; data: string }
> {
  return await withFetchDeadline(
    signedUrl,
    { method: "GET", redirect: "manual" },
    OUTPUT_TIMEOUT_MS,
    async (response) => {
      const mimeType = (response.headers.get("content-type") ?? "")
        .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
      if (
        !response.ok ||
        !new Set(["image/png", "image/jpeg", "image/webp"]).has(mimeType)
      ) {
        await response.body?.cancel();
        throw new Error("provider_input_invalid");
      }
      const bytes = await readBoundedBytes(
        response,
        MAX_GOOGLE_INPUT_IMAGE_BYTES,
      );
      return {
        mimeType: mimeType as "image/png" | "image/jpeg" | "image/webp",
        data: bytesToBase64(bytes),
      };
    },
  );
}

function validateGoogleOutputUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 4_096) return null;
  try {
    const url = new URL(value);
    if (
      url.protocol !== "https:" ||
      url.hostname !== "generativelanguage.googleapis.com" ||
      (url.port !== "" && url.port !== "443") ||
      url.username !== "" || url.password !== "" || url.hash !== "" ||
      !url.pathname.startsWith("/v1beta/files/")
    ) return null;
    return url.href;
  } catch {
    return null;
  }
}

function validateGoogleOutputRedirectUrl(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 8_192) return null;
  try {
    const url = new URL(value);
    const googleMediaHost = url.hostname ===
        "generativelanguage.googleapis.com" ||
      url.hostname === "storage.googleapis.com" ||
      url.hostname.endsWith(".googleusercontent.com");
    if (
      url.protocol !== "https:" || !googleMediaHost ||
      (url.port !== "" && url.port !== "443") ||
      url.username !== "" || url.password !== "" || url.hash !== ""
    ) return null;
    return url.href;
  } catch {
    return null;
  }
}

type OutputFetchResult =
  | { ok: true; bytes: Uint8Array<ArrayBuffer> }
  | {
    ok: false;
    code: "output_download_failed" | "output_validation_failed";
  };

type GoogleOutputStep =
  | { kind: "redirect"; next: string }
  | { kind: "output"; result: OutputFetchResult };

async function fetchGoogleOutput(
  outputUrl: string,
  apiKey: string,
): Promise<OutputFetchResult> {
  const validatedOutputUrl = validateGoogleOutputUrl(outputUrl);
  if (validatedOutputUrl === null) throw new Error("google_output_url_invalid");
  let current: string = validatedOutputUrl;
  for (let redirects = 0; redirects <= 3; redirects += 1) {
    const currentUrl: URL = new URL(current);
    const step: GoogleOutputStep = await withFetchDeadline(
      current,
      {
        method: "GET",
        redirect: "manual",
        headers: currentUrl.hostname === "generativelanguage.googleapis.com"
          ? { "x-goog-api-key": apiKey }
          : {},
      },
      OUTPUT_TIMEOUT_MS,
      async (response) => {
        if ([301, 302, 303, 307, 308].includes(response.status)) {
          const location = response.headers.get("location");
          await response.body?.cancel();
          if (redirects === 3 || location === null) {
            throw new Error("google_output_redirect_invalid");
          }
          const next = validateGoogleOutputRedirectUrl(
            new URL(location, current).href,
          );
          if (next === null) throw new Error("google_output_redirect_invalid");
          return { kind: "redirect" as const, next };
        }
        const mimeType = (response.headers.get("content-type") ?? "")
          .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
        if (!response.ok) {
          await response.body?.cancel();
          return {
            kind: "output" as const,
            result: {
              ok: false as const,
              code: "output_download_failed" as const,
            },
          };
        }
        if (
          !new Set([
            "video/mp4",
            "application/mp4",
            "application/octet-stream",
          ]).has(mimeType)
        ) {
          await response.body?.cancel();
          return {
            kind: "output" as const,
            result: {
              ok: false as const,
              code: "output_validation_failed" as const,
            },
          };
        }
        try {
          return {
            kind: "output" as const,
            result: {
              ok: true as const,
              bytes: await readBoundedBytes(response, MAX_OUTPUT_BYTES),
            },
          };
        } catch (error) {
          return {
            kind: "output" as const,
            result: {
              ok: false as const,
              code: error instanceof ResponseSizeInvalidError
                ? "output_validation_failed" as const
                : "output_download_failed" as const,
            },
          };
        }
      },
    );
    if (step.kind === "output") return step.result;
    current = step.next;
  }
  throw new Error("google_output_redirect_invalid");
}

function validateSupabaseSignedUrl(value: unknown): string | null {
  const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
  if (typeof value !== "string" || value.length > 4_096) return null;
  try {
    const expected = new URL(supabaseUrl);
    const actual = new URL(value);
    if (
      expected.protocol !== "https:" || actual.protocol !== "https:" ||
      actual.origin !== expected.origin || actual.username !== "" ||
      actual.password !== "" ||
      !actual.pathname.startsWith(
        `/storage/v1/object/sign/${STORAGE_BUCKET}/`,
      )
    ) {
      return null;
    }
    return actual.href;
  } catch {
    return null;
  }
}

function parseRunwayTask(
  value: unknown,
): { id: string; status: string; createdAt: string | null } | null {
  if (
    !isRecord(value) || !isValidTaskId(value.id) ||
    typeof value.status !== "string"
  ) {
    return null;
  }
  const createdAt = typeof value.createdAt === "string" &&
      Number.isFinite(Date.parse(value.createdAt))
    ? value.createdAt
    : null;
  return { id: value.id, status: value.status, createdAt };
}

function parseCreatedRunwayTask(value: unknown): { id: string } | null {
  if (!isRecord(value) || !isValidTaskId(value.id)) return null;
  return { id: value.id };
}

function parseCreatedGoogleOperation(value: unknown): { id: string } | null {
  if (!isRecord(value) || !isValidGoogleOperationName(value.name)) return null;
  return { id: value.name };
}

type GoogleOperation = {
  name: string;
  done: boolean;
  error: Record<string, unknown> | null;
  outputUrl: string | null;
};

function parseGoogleOperation(value: unknown): GoogleOperation | null {
  if (!isRecord(value) || !isValidGoogleOperationName(value.name)) return null;
  const done = Object.hasOwn(value, "done") ? value.done : false;
  if (typeof done !== "boolean") return null;
  if (!done) {
    if (Object.hasOwn(value, "error") || Object.hasOwn(value, "response")) {
      return null;
    }
    return { name: value.name, done: false, error: null, outputUrl: null };
  }
  if (isRecord(value.error)) {
    return {
      name: value.name,
      done: true,
      error: value.error,
      outputUrl: null,
    };
  }
  const response = isRecord(value.response) ? value.response : null;
  const generated = response && isRecord(response.generateVideoResponse)
    ? response.generateVideoResponse
    : null;
  const samples = generated && Array.isArray(generated.generatedSamples)
    ? generated.generatedSamples
    : null;
  const first = samples?.length === 1 && isRecord(samples[0])
    ? samples[0]
    : null;
  const video = first && isRecord(first.video) ? first.video : null;
  const outputUrl = validateGoogleOutputUrl(video?.uri);
  return outputUrl === null
    ? null
    : { name: value.name, done: true, error: null, outputUrl };
}

function googleOperationFailure(value: Record<string, unknown>): string {
  const status = typeof value.status === "string"
    ? value.status.toUpperCase()
    : "";
  if (status === "RESOURCE_EXHAUSTED") return "provider_credits_unavailable";
  if (status === "UNAUTHENTICATED" || status === "PERMISSION_DENIED") {
    return "provider_authentication_failed";
  }
  if (status === "INVALID_ARGUMENT" || status === "FAILED_PRECONDITION") {
    return "provider_request_rejected";
  }
  return "provider_task_failed";
}

const CREATOR_GENERATE_USER_OPTIONS = {
  auth: "user",
  cors: false,
} as const;

const CREATOR_GENERATE_WORKER_OPTIONS = {
  auth: "none",
  cors: false,
} as const;

async function handleCreatorGenerate(
  request: Request,
  context: SupabaseContext<ContentEngineDatabase>,
  internalWorker: boolean,
): Promise<Response> {
  if (internalWorker && !(await isInternalWorkerAuthorized(request))) {
    return json(request, { ok: false, code: "authentication_required" }, 401);
  }
  const supabaseAdmin = context.supabaseAdmin;
  if (request.method !== "POST") {
    return json(request, { ok: false, code: "method_not_allowed" }, 405);
  }
  if (
    (!internalWorker &&
      !USER_APP_ORIGINS.has(request.headers.get("origin") ?? "")) ||
    (internalWorker && request.headers.get("origin") !== null)
  ) {
    return json(request, { ok: false, code: "origin_not_allowed" }, 403);
  }
  if (
    internalWorker &&
    request.headers.get(INTERNAL_WORKER_HEADER) !== "1"
  ) {
    return json(
      request,
      { ok: false, code: "worker_request_required" },
      403,
    );
  }
  const contentType = request.headers.get("content-type") ?? "";
  if (
    !contentType.toLocaleLowerCase("en-US").startsWith("application/json")
  ) {
    return json(request, { ok: false, code: "content_type_invalid" }, 415);
  }
  const contentLength = Number(
    request.headers.get("content-length") ?? "0",
  );
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }
  if (!internalWorker && !context.userClaims?.id) {
    return json(
      request,
      { ok: false, code: "authentication_required" },
      401,
    );
  }

  let bodyText: string;
  try {
    const bodyBytes = await readBoundedStream(request.body, MAX_BODY_BYTES);
    bodyText = new TextDecoder("utf-8", { fatal: true }).decode(bodyBytes);
  } catch {
    return json(request, { ok: false, code: "request_too_large" }, 413);
  }
  let body: unknown;
  try {
    body = JSON.parse(bodyText);
  } catch {
    return json(request, { ok: false, code: "invalid_json" }, 400);
  }

  const loadProviderPolicy = async (
    organizationId: string,
    provider: GenerationProvider,
    model: GenerationModel,
  ): Promise<GenerationProviderPolicy | null> => {
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_generation_provider_policy",
        {
          p_payload: {
            organization_id: organizationId,
            provider,
            model,
          },
        },
      );
      if (error !== null) return null;
      return readGenerationProviderPolicy(data, provider, model);
    } catch {
      return null;
    }
  };

  const loadGenerationStrategyCatalogPolicy = async (
    organizationId: string,
  ): Promise<GenerationStrategyCatalogPolicy | null> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_generation_strategy_catalog_policy",
        {
          p_payload: {
            version: "generation-strategy-catalog-policy-request-v1",
            organization_id: organizationId,
          },
        },
      );
      if (error !== null) return null;
      return readGenerationStrategyCatalogPolicy(data);
    } catch {
      return null;
    }
  };

  const modelCatalogPayload = readModelCatalogPayload(body);
  if (!internalWorker && modelCatalogPayload !== null) {
    // Reuse the established generation overview boundary to prove that the
    // authenticated actor belongs to the requested organization. Feature
    // flags are deliberately not accepted from the browser. The dedicated
    // organization policy projection below is the only strategy capability
    // authority used for this read-only catalog response.
    try {
      const { error } = await context.supabase.rpc(
        "creator_generation_spend_overview",
        { p_payload: { organization_id: modelCatalogPayload.organization_id } },
      );
      if (error !== null) {
        return json(request, { ok: false, code: "generation_rejected" }, 403);
      }
    } catch {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    let modelFeatureFlags: GenerationModelFeatureFlags | null = null;
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_generation_model_feature_flags",
        {
          p_payload: {
            organization_id: modelCatalogPayload.organization_id,
          },
        },
      );
      if (error === null) {
        modelFeatureFlags = readGenerationModelFeatureFlags(data);
      }
    } catch {
      modelFeatureFlags = null;
    }
    if (modelFeatureFlags === null) {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    const catalogFeatureFlags = {
      [GENERATION_MODEL_FEATURE_FLAGS.googleVeoLite]:
        modelFeatureFlags.googleVeoLite,
      [GENERATION_MODEL_FEATURE_FLAGS.runwayPremium]:
        modelFeatureFlags.runwayPremium,
    };
    const baseCatalog = publicGenerationModelCatalog({
      featureFlags: catalogFeatureFlags,
    });
    const policyPairs = await Promise.all(
      baseCatalog.models.map(async (entry) => {
        const provider = readGenerationProvider(entry.provider);
        const model = readGenerationModel(provider, entry.model);
        if (provider === null || model === null) {
          return [
            `${entry.provider}:${entry.model}`,
            null,
          ] as const;
        }
        return [
          `${entry.provider}:${entry.model}`,
          await loadProviderPolicy(
            modelCatalogPayload.organization_id,
            provider,
            model,
          ),
        ] as const;
      }),
    );
    const policyByKey: Map<string, GenerationProviderPolicy | null> = new Map(
      policyPairs,
    );
    const strategyCatalogPolicy = await loadGenerationStrategyCatalogPolicy(
      modelCatalogPayload.organization_id,
    );
    if (strategyCatalogPolicy === null) {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    const publicStrategyCatalog = publicGenerationStrategyCatalog({
      executionCapabilities: strategyCatalogPolicy.executionCapabilities,
    }) as {
      version: string;
      recipe_version: string;
      pricing_version: string;
      strategies: PublicGenerationStrategyCatalogEntry[];
    };
    const catalog = publicGenerationModelCatalog({
      featureFlags: catalogFeatureFlags,
    });
    return json(request, {
      ok: true,
      catalog: {
        ...catalog,
        models: catalog.models.map((entry) => {
          const key = `${entry.provider}:${entry.model}`;
          const executionSupported = LIVE_GENERATION_EXECUTION_KEYS.has(key);
          const policy = policyByKey.get(key);
          const executionPolicy = publicExecutionPolicy(
            entry.provider,
            entry.model,
          );
          const imageCapabilities = isRecord(entry.inputCapabilities) &&
              isRecord(entry.inputCapabilities.image)
            ? entry.inputCapabilities.image
            : {};
          const allowedRatios = Array.isArray(executionPolicy.allowedRatios)
            ? executionPolicy.allowedRatios
            : Array.isArray(imageCapabilities.allowedRatios)
            ? imageCapabilities.allowedRatios
            : [];
          const allowedResolutions = Array.isArray(
              executionPolicy.allowedResolutions,
            )
            ? executionPolicy.allowedResolutions
            : Array.isArray(imageCapabilities.allowedResolutions)
            ? imageCapabilities.allowedResolutions
            : [];
          const maxReferenceImages = Number.isSafeInteger(
              executionPolicy.maxReferenceImages,
            )
            ? Number(executionPolicy.maxReferenceImages)
            : Number(imageCapabilities.maxReferenceImages || 0);
          const referenceBundle = key === "runway:seedream5_lite" ||
            key === "runway:seedance2_fast" ||
            key === "runway:seedance2_mini";
          const firstFrameSupported = executionSupported && !referenceBundle;
          const lastFrameSupported =
            executionPolicy.lastFrameSupported === true;
          const launchEnabled = entry.enabled && executionSupported &&
            policy?.launchEnabled === true;
          const disabledReasonCode = !entry.enabled
            ? entry.disabledReasonCode
            : !executionSupported
            ? "launch_route_pending"
            : !launchEnabled
            ? policy?.disabledReasonCode || "launch_route_pending"
            : null;
          return {
            ...entry,
            // The paid owner currently executes one exact image-input path.
            // Do not advertise catalog text/video capabilities as launchable.
            ...(executionSupported
              ? {
                inputModes: ["image"],
                allowedRatios,
                allowedResolutions,
                supportsReferenceImages: maxReferenceImages > 0,
                maxReferenceImages,
                supportsReferenceVideo: false,
                supportsFirstFrame: firstFrameSupported,
                supportsLastFrame: lastFrameSupported,
                inputCapabilities: {
                  image: {
                    ...imageCapabilities,
                    allowedRatios,
                    allowedResolutions,
                    maxReferenceImages,
                    supportsReferenceVideo: false,
                    supportsFirstFrame: firstFrameSupported,
                    supportsLastFrame: lastFrameSupported,
                  },
                },
              }
              : {}),
            executionSupported,
            launchEnabled,
            disabledReasonCode,
            ...executionPolicy,
          };
        }),
        strategyCatalogVersion: publicStrategyCatalog.version,
        strategyRecipeVersion: publicStrategyCatalog.recipe_version,
        strategyPricingVersion: publicStrategyCatalog.pricing_version,
        strategies: publicStrategyCatalog.strategies.map((entry) => {
          return {
            strategy_id: entry.strategy_id,
            public_label: entry.public_label,
            public_summary: entry.public_summary,
            transformation_kind: entry.transformation_kind,
            source_reference_mode: entry.source_reference_mode,
            preservation_notice: entry.preservation_notice,
            human_review_required: entry.human_review_required,
            provider: entry.provider,
            recipe: entry.recipe,
            recipe_version: entry.recipe_version,
            asset_roles: entry.asset_roles,
            required_attestations: entry.required_attestations,
            output_rules: entry.output_rules,
            pricing: entry.pricing,
            enabled: entry.enabled,
            disabled_reason: entry.disabled_reason,
          };
        }),
        version: GENERATION_MODEL_CATALOG_VERSION,
      },
    });
  }

  const strategyBindPayload = readGenerationStrategyBindPayload(body);
  if (!internalWorker && strategyBindPayload !== null) {
    const actorId = context.userClaims?.id;
    if (!isUuid(actorId)) {
      return json(
        request,
        { ok: false, code: "authentication_required" },
        401,
      );
    }
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_resolve_and_bind_generation_strategy",
        {
          p_payload: {
            version: "generation-strategy-resolve-bind-request-v1",
            organization_id: strategyBindPayload.organization_id,
            project_id: strategyBindPayload.project_id,
            actor_id: actorId,
            spec_id: strategyBindPayload.spec_id,
            spec_version: strategyBindPayload.spec_version,
            spec_hash: strategyBindPayload.spec_hash,
            selection: strategyBindPayload.generation_strategy as Json,
            confirmation: true,
            idempotency_key: strategyBindPayload.idempotency_key,
          },
        },
      );
      if (error !== null) {
        const mapped = readGenerationStrategyBindRpcError(error);
        if (mapped !== null) {
          return json(
            request,
            { ok: false, code: mapped.code },
            mapped.status,
          );
        }
        return json(
          request,
          { ok: false, code: "generation_unavailable" },
          503,
        );
      }
      const result = readGenerationStrategyBindResult(
        data,
        strategyBindPayload,
      );
      return result === null
        ? json(
          request,
          { ok: false, code: "generation_unavailable" },
          503,
        )
        : json(request, result);
    } catch {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
  }

  const strategyMediaProbePayload = readGenerationStrategyMediaProbePayload(
    body,
  );
  if (!internalWorker && strategyMediaProbePayload !== null) {
    const actorId = context.userClaims?.id;
    if (!isUuid(actorId)) {
      return json(request, { ok: false, code: "authentication_required" }, 401);
    }
    try {
      const contextResult = await supabaseAdmin.rpc(
        "system_generation_strategy_media_probe_context",
        {
          p_payload: {
            version: "generation-strategy-media-probe-context-request-v1",
            organization_id: strategyMediaProbePayload.organization_id,
            project_id: strategyMediaProbePayload.project_id,
            actor_id: actorId,
            media_id: strategyMediaProbePayload.media_id,
          },
        },
      );
      if (contextResult.error !== null) {
        const mapped = readGenerationStrategyRpcError(contextResult.error);
        return json(
          request,
          { ok: false, code: mapped?.code || "generation_unavailable" },
          mapped?.status || 503,
        );
      }
      const media = readGenerationStrategyProbeContext(contextResult.data, {
        mediaId: strategyMediaProbePayload.media_id,
      });
      if (media === null) {
        return json(
          request,
          { ok: false, code: "generation_unavailable" },
          503,
        );
      }
      const signed = await supabaseAdmin.storage.from(media.bucket_id)
        .createSignedUrl(media.object_name, INPUT_URL_TTL_SECONDS);
      const signedUrl = signed.error === null
        ? validateSupabaseSignedUrl(signed.data?.signedUrl)
        : null;
      if (
        signedUrl === null || signedUrl.length > STRATEGY_SIGNED_URL_MAX_LENGTH
      ) {
        return json(
          request,
          { ok: false, code: "strategy_media_probe_signing_failed" },
          503,
        );
      }
      const bytes = await withFetchDeadline(
        signedUrl,
        { method: "GET", redirect: "manual" },
        STRATEGY_MEDIA_PROBE_TIMEOUT_MS,
        async (response) => {
          const mimeType = (response.headers.get("content-type") ?? "")
            .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
          const declared = Number(response.headers.get("content-length") ?? "");
          if (
            response.status !== 200 || mimeType !== "video/mp4" ||
            !Number.isSafeInteger(declared) || declared !== media.size_bytes ||
            declared < 1 || declared > ISO_BMFF_MAX_BYTES
          ) {
            await response.body?.cancel();
            throw new Error("strategy_media_probe_response_invalid");
          }
          const bodyBytes = await readBoundedBytes(
            response,
            ISO_BMFF_MAX_BYTES,
          );
          if (bodyBytes.byteLength !== media.size_bytes) {
            throw new Error("strategy_media_probe_size_mismatch");
          }
          return bodyBytes;
        },
      );
      if (await sha256Hex(bytes) !== media.sha256) {
        return json(
          request,
          { ok: false, code: "strategy_media_probe_hash_mismatch" },
          409,
        );
      }
      const parsed = parseIsoBmffDuration(bytes);
      const evidenceHash = await sha256Hex(new TextEncoder().encode(stableJson({
        version: "generation-strategy-media-probe-evidence-v1",
        media_id: media.media_id,
        attachment_id: media.attachment_id,
        attachment_hash: media.attachment_hash,
        media_sha256: media.sha256,
        size_bytes: media.size_bytes,
        parser_version: parsed.parser_version,
        timescale: parsed.timescale,
        duration_units: parsed.duration_units,
        duration_ms: parsed.duration_ms,
      })));
      const recorded = await supabaseAdmin.rpc(
        "system_record_generation_strategy_media_duration",
        {
          p_payload: {
            version: "generation-strategy-media-duration-record-request-v1",
            organization_id: strategyMediaProbePayload.organization_id,
            project_id: strategyMediaProbePayload.project_id,
            actor_id: actorId,
            media_id: media.media_id,
            attachment_id: media.attachment_id,
            attachment_hash: media.attachment_hash,
            media_sha256: media.sha256,
            size_bytes: media.size_bytes,
            http_status: 200,
            content_type: "video/mp4",
            download_complete: true,
            parser_version: ISO_BMFF_DURATION_PARSER_VERSION,
            timescale: parsed.timescale,
            duration_units: parsed.duration_units,
            duration_ms: parsed.duration_ms,
            mvhd_count: parsed.mvhd_count,
            fragmented: parsed.fragmented,
            verification_method: "server_mp4_probe",
            evidence_hash: evidenceHash,
            idempotency_key: strategyMediaProbePayload.idempotency_key,
          },
        },
      );
      if (recorded.error !== null) {
        const mapped = readGenerationStrategyRpcError(recorded.error);
        return json(
          request,
          { ok: false, code: mapped?.code || "generation_unavailable" },
          mapped?.status || 503,
        );
      }
      const publicResult = publicGenerationStrategyProbeResult(recorded.data, {
        mediaId: media.media_id,
        attachmentId: media.attachment_id,
        attachmentHash: media.attachment_hash,
        mediaSha256: media.sha256,
        sizeBytes: media.size_bytes,
        timescale: parsed.timescale,
        durationUnits: parsed.duration_units,
        durationMs: parsed.duration_ms,
        durationSeconds: parsed.duration_seconds,
      });
      return publicResult === null
        ? json(request, { ok: false, code: "generation_unavailable" }, 503)
        : json(request, publicResult);
    } catch {
      return json(
        request,
        { ok: false, code: "strategy_media_probe_failed" },
        503,
      );
    }
  }

  const strategyPreflightPayload = readGenerationStrategyPreflightPayload(body);
  if (!internalWorker && strategyPreflightPayload !== null) {
    const actorId = context.userClaims?.id;
    const spend = readStrategySpendConfirmation(
      strategyPreflightPayload.spend_confirmation,
    );
    if (!isUuid(actorId) || spend === null) {
      return json(request, { ok: false, code: "invalid_payload" }, 400);
    }
    const readiness = await checkRunwayStrategyReadiness(
      runwaySecret(),
      spend.estimatedCredits,
    );
    try {
      const recorded = await supabaseAdmin.rpc(
        "system_record_generation_strategy_readiness",
        {
          p_payload: {
            version: "generation-strategy-readiness-record-request-v1",
            organization_id: strategyPreflightPayload.organization_id,
            project_id: strategyPreflightPayload.project_id,
            actor_id: actorId,
            binding_id: strategyPreflightPayload.binding_id,
            binding_hash: strategyPreflightPayload.binding_hash,
            selection_hash: strategyPreflightPayload.selection_hash,
            price_hash: strategyPreflightPayload.price_hash,
            spend_confirmation: strategyPreflightPayload.spend_confirmation,
            credential_configured: readiness.credentialConfigured,
            provider_authentication_confirmed:
              readiness.providerAuthenticationConfirmed,
            balance_sufficient: readiness.balanceSufficient,
            provider_failure_code: readiness.failureCode,
            confirmation: true,
            idempotency_key: strategyPreflightPayload.idempotency_key,
          },
        },
      );
      if (recorded.error !== null) {
        const mapped = readGenerationStrategyRpcError(recorded.error);
        return json(
          request,
          { ok: false, code: mapped?.code || "generation_unavailable" },
          mapped?.status || 503,
        );
      }
      const result = readGenerationStrategyReadiness(recorded.data, {
        bindingId: strategyPreflightPayload.binding_id,
        bindingHash: strategyPreflightPayload.binding_hash,
        selectionHash: strategyPreflightPayload.selection_hash,
        priceHash: strategyPreflightPayload.price_hash,
        spendConfirmation: strategyPreflightPayload.spend_confirmation,
      });
      if (
        result === null || result.receipt.strategy_id !== spend.strategyId ||
        result.receipt.recipe !== spend.recipe
      ) {
        return json(
          request,
          { ok: false, code: "generation_unavailable" },
          503,
        );
      }
      if (!result.receipt.ready) {
        return json(
          request,
          { ok: false, code: result.receipt.failure_code },
          result.receipt.failure_code === "provider_balance_insufficient"
            ? 409
            : 503,
        );
      }
      const policyRpc = await supabaseAdmin.rpc(
        "system_generation_strategy_provider_policy",
        {
          p_payload: {
            version: "generation-strategy-provider-policy-request-v1",
            organization_id: strategyPreflightPayload.organization_id,
            project_id: strategyPreflightPayload.project_id,
            actor_id: actorId,
            spec_id: strategyPreflightPayload.spec_id,
            spec_version: strategyPreflightPayload.spec_version,
            spec_hash: strategyPreflightPayload.spec_hash,
            strategy_id: spend.strategyId,
            provider_readiness_receipt_id: result.receipt.id,
            provider_readiness_receipt_hash: result.receipt.receipt_hash,
          },
        },
      );
      if (policyRpc.error !== null) {
        const mapped = readGenerationStrategyRpcError(policyRpc.error);
        return json(
          request,
          { ok: false, code: mapped?.code || "generation_unavailable" },
          mapped?.status || 503,
        );
      }
      const policy = readGenerationStrategyProviderPolicy(policyRpc.data, {
        strategyId: spend.strategyId,
        bindingId: strategyPreflightPayload.binding_id,
        bindingHash: strategyPreflightPayload.binding_hash,
        receiptId: result.receipt.id,
        receiptHash: result.receipt.receipt_hash,
      });
      if (policy === null) {
        return json(
          request,
          { ok: false, code: "generation_unavailable" },
          503,
        );
      }
      if (!policy.launchEnabled) {
        return json(
          request,
          {
            ok: false,
            code: policy.blockers[0] || "generation_strategy_launch_disabled",
          },
          409,
        );
      }
      return json(request, {
        ...result.publicResult,
        launch_enabled: true,
      });
    } catch {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
  }

  const readCurrentStatus = async (
    organizationId: string,
    jobId: string,
    projectId: string,
  ): Promise<StatusJob | null> => {
    if (internalWorker) {
      try {
        const query = supabaseAdmin
          .schema("content_factory")
          .from("generation_jobs")
          .select(
            "id, organization_id, project_id, batch_id, campaign_id, status, mode, provider, input, output, estimated_cost_minor, actual_cost_minor, updated_at",
          )
          .eq("organization_id", organizationId)
          .eq("project_id", projectId)
          .eq("id", jobId)
          .eq("mode", "real")
          .in("provider", ["runway", "google"]);
        const { data, error } = await query.maybeSingle();
        if (
          error || !isRecord(data) || data.project_id !== projectId ||
          !isUuid(data.campaign_id)
        ) return null;
        const { data: campaignData, error: campaignError } = await supabaseAdmin
          .schema("content_factory")
          .from("generation_campaigns")
          .select("id, name")
          .eq("organization_id", organizationId)
          .eq("id", data.campaign_id)
          .maybeSingle();
        if (
          campaignError || !isRecord(campaignData) ||
          !isBoundedText(campaignData.name, 2, 160)
        ) {
          return null;
        }
        return readInternalStatusRow({
          ...data,
          campaign_name: campaignData.name,
        });
      } catch {
        return null;
      }
    }
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_real_generation_status",
        {
          p_payload: {
            organization_id: organizationId,
            project_id: projectId,
            job_id: jobId,
          },
        },
      );
      if (error) return null;
      const job = readStatusJob(data);
      if (job === null || job.id !== jobId) return null;
      return job;
    } catch {
      return null;
    }
  };

  const readCurrentStatusWithinDeadline = async (
    organizationId: string,
    jobId: string,
    projectId: string,
  ): Promise<StatusJob | null> => {
    try {
      return await withOperationDeadline(
        readCurrentStatus(organizationId, jobId, projectId),
        OUTPUT_DATABASE_TIMEOUT_MS,
      );
    } catch {
      return null;
    }
  };

  const updateSystemJob = async (
    payload: Record<string, Json>,
  ): Promise<Json | null> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_update_real_generation",
        { p_payload: payload },
      );
      return error ? null : data;
    } catch {
      return null;
    }
  };

  const completeSeedreamPhoto = async (
    payload: Record<string, Json>,
  ): Promise<Json | null> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_complete_seedream5_lite_photo",
        { p_payload: payload },
      );
      return error ? null : data;
    } catch {
      return null;
    }
  };

  const claimSystemJob = async (jobId: string): Promise<ClaimResult> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_update_real_generation",
        { p_payload: { job_id: jobId, status: "starting" } },
      );
      if (error !== null) {
        const claimCode = readClaimErrorCode(error);
        if (claimCode === "generation_spec_provider_start_stale") {
          console.warn("generation claim terminalization unavailable", {
            code: "generation_spec_claim_terminalization_failed",
            job_id: jobId,
          });
          return { outcome: "unavailable" };
        }
        return claimCode === null
          ? { outcome: "unavailable" }
          : { outcome: "budget_rejected", code: claimCode };
      }
      const terminalCode = readTerminalClaimErrorCode(data, jobId);
      if (terminalCode !== null) {
        return { outcome: "terminal_rejected", code: terminalCode };
      }
      if (
        !isRecord(data) || data.ok !== true ||
        typeof data.claimed !== "boolean"
      ) {
        return { outcome: "unavailable" };
      }
      return { outcome: "claimed", claimed: data.claimed };
    } catch {
      return { outcome: "unavailable" };
    }
  };

  const markReconciliationRequired = async (
    jobId: string,
    reasonCode:
      | "provider_create_timeout"
      | "provider_create_http_unknown"
      | "provider_create_response_unknown"
      | "provider_create_state_stale",
  ): Promise<boolean> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_mark_real_generation_reconciliation_required",
        { p_payload: { job_id: jobId, reason_code: reasonCode } },
      );
      return error === null && isRecord(data) && data.ok === true;
    } catch {
      return false;
    }
  };

  const readReconciliationAuthorization = async (
    payload: ReconcilePayload,
  ): Promise<ReconciliationContext | null> => {
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_real_generation_reconciliation_context",
        {
          p_payload: {
            organization_id: payload.organization_id,
            project_id: payload.project_id,
            job_id: payload.job_id,
          },
        },
      );
      return error === null ? readReconciliationContext(data, payload) : null;
    } catch {
      return null;
    }
  };

  const reconcileSystemJob = async (
    payload: Record<string, Json>,
  ): Promise<boolean> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_reconcile_real_generation",
        { p_payload: payload },
      );
      return error === null && isRecord(data) && data.ok === true;
    } catch {
      return false;
    }
  };

  const markFailed = async (
    jobId: string,
    failureCode: string,
    provider: GenerationProvider = "runway",
    providerTaskId?: string,
    providerFailureCode?: string | null,
    billingOutcome?: "refundable" | "non_refundable" | "unknown",
  ) => {
    const safeCode = FAILURE_CODES.has(failureCode)
      ? failureCode
      : "internal_error";
    const failurePayload: Record<string, Json> = {
      job_id: jobId,
      status: "failed",
      failure_code: safeCode,
    };
    if (isValidProviderTaskId(provider, providerTaskId)) {
      failurePayload.provider_task_id = providerTaskId;
      failurePayload.billing_outcome = billingOutcome ?? "unknown";
      if (providerFailureCode !== null && providerFailureCode !== undefined) {
        failurePayload.provider_failure_code = providerFailureCode;
      }
    }
    await updateSystemJob(failurePayload);
  };

  const signOutput = async (job: StatusJob): Promise<string | null> => {
    try {
      const { data, error } = await withOperationDeadline(
        supabaseAdmin.storage.from(STORAGE_BUCKET).createSignedUrl(
          job.outputObjectName,
          OUTPUT_URL_TTL_SECONDS,
        ),
        OUTPUT_ACCESS_TIMEOUT_MS,
      );
      if (error || data === null) return null;
      return validateSupabaseSignedUrl(data.signedUrl);
    } catch {
      return null;
    }
  };

  const respondWithCurrent = async (
    organizationId: string,
    jobId: string,
    batch: { id: string; status: string } | undefined,
    projectId: string,
  ): Promise<Response> => {
    const current = await readCurrentStatusWithinDeadline(
      organizationId,
      jobId,
      projectId,
    );
    if (current === null) {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    const signedUrl = !internalWorker && current.status === "succeeded"
      ? await signOutput(current)
      : null;
    if (
      !internalWorker && current.status === "succeeded" && signedUrl === null
    ) {
      return json(request, {
        ok: false,
        code: "output_access_failed",
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      }, 503);
    }
    return json(request, {
      ok: true,
      ...(batch ? { batch } : {}),
      job: safeJob(current),
      ...(signedUrl ? { signed_url: signedUrl } : {}),
    });
  };

  const respondProviderUnavailable = async (
    organizationId: string,
    jobId: string,
    batch: { id: string; status: string } | undefined,
    projectId: string,
  ): Promise<Response> => {
    const current = await readCurrentStatusWithinDeadline(
      organizationId,
      jobId,
      projectId,
    );
    return json(request, {
      ok: false,
      code: "provider_unavailable",
      ...(batch ? { batch } : {}),
      ...(current ? { job: safeJob(current) } : {}),
    }, 503);
  };

  const respondOutputRetryable = async (
    code:
      | "output_download_failed"
      | "output_validation_failed"
      | "output_upload_failed"
      | "output_access_failed",
    organizationId: string,
    jobId: string,
    batch: { id: string; status: string } | undefined,
    projectId: string,
  ): Promise<Response> => {
    // Runway has already accepted and completed this paid task. Keep the exact
    // job recoverable and let status polling retry only finalization; this path
    // must never create another provider task or mutate the job to failed.
    const current = await readCurrentStatusWithinDeadline(
      organizationId,
      jobId,
      projectId,
    );
    return json(request, {
      ok: false,
      code,
      ...(batch ? { batch } : {}),
      ...(current ? { job: safeJob(current) } : {}),
    }, 503);
  };

  const handleStatus = async (
    payload: StatusPayload,
    currentOverride?: StatusJob,
    batch?: { id: string; status: string },
  ): Promise<Response> => {
    let current = currentOverride ?? await readCurrentStatusWithinDeadline(
      payload.organization_id,
      payload.job_id,
      payload.project_id,
    );
    if (current === null) {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    if (current.status === "succeeded") {
      const signedUrl = internalWorker ? null : await signOutput(current);
      if (!internalWorker && signedUrl === null) {
        return await respondOutputRetryable(
          "output_access_failed",
          payload.organization_id,
          payload.job_id,
          batch,
          payload.project_id,
        );
      }
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
        ...(signedUrl ? { signed_url: signedUrl } : {}),
      });
    }
    if (current.status === "failed" || current.status === "queued") {
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    if (current.status === "starting") {
      if (
        !current.reconciliationRequired &&
        Date.now() - Date.parse(current.updatedAt) >=
          STARTING_RECONCILIATION_AFTER_MS
      ) {
        await markReconciliationRequired(
          current.id,
          "provider_create_state_stale",
        );
        current = await readCurrentStatusWithinDeadline(
          payload.organization_id,
          payload.job_id,
          payload.project_id,
        ) ??
          current;
      }
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    if (!isValidProviderTaskId(current.provider, current.providerTaskId)) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    if (
      Date.now() - Date.parse(current.updatedAt) <
        MIN_PROVIDER_POLL_INTERVAL_MS
    ) {
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    const secret = current.provider === "google"
      ? googleApiKey()
      : runwaySecret();
    if (secret === null) {
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }

    let providerResponse: ProviderJsonResult;
    try {
      const providerStatusUrl = current.provider === "google"
        ? `${GOOGLE_GENERATIVE_LANGUAGE_API_ORIGIN}/${GOOGLE_GENERATIVE_LANGUAGE_API_VERSION}/${current.providerTaskId}`
        : `${RUNWAY_API_ORIGIN}/v1/tasks/${current.providerTaskId}`;
      providerResponse = await fetchProviderJsonWithDeadline(
        providerStatusUrl,
        {
          method: "GET",
          redirect: "manual",
          headers: current.provider === "google"
            ? { "x-goog-api-key": secret }
            : {
              authorization: `Bearer ${secret}`,
              "x-runway-version": RUNWAY_API_VERSION,
            },
        },
        PROVIDER_TIMEOUT_MS,
      );
    } catch {
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }
    if (!providerResponse.ok) {
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }

    let providerValue = providerResponse.value;
    if (current.provider === "google") {
      const operation = parseGoogleOperation(providerValue);
      if (operation === null || operation.name !== current.providerTaskId) {
        return await respondProviderUnavailable(
          payload.organization_id,
          payload.job_id,
          batch,
          payload.project_id,
        );
      }
      if (!operation.done) {
        if (current.status === "submitted") {
          await updateSystemJob({
            job_id: current.id,
            provider_task_id: current.providerTaskId,
            status: "processing",
          });
        }
        return await respondWithCurrent(
          payload.organization_id,
          payload.job_id,
          batch,
          payload.project_id,
        );
      }
      if (operation.error !== null) {
        await markFailed(
          current.id,
          googleOperationFailure(operation.error),
          "google",
          current.providerTaskId,
          null,
          "refundable",
        );
        return await respondWithCurrent(
          payload.organization_id,
          payload.job_id,
          batch,
          payload.project_id,
        );
      }
      if (operation.outputUrl === null) {
        return await respondProviderUnavailable(
          payload.organization_id,
          payload.job_id,
          batch,
          payload.project_id,
        );
      }
      providerValue = {
        id: current.providerTaskId,
        status: "SUCCEEDED",
        output: [operation.outputUrl],
      };
    }
    const providerTask = current.provider === "google"
      ? { id: current.providerTaskId, status: "SUCCEEDED", createdAt: null }
      : parseRunwayTask(providerValue);
    if (
      providerTask === null || providerTask.id !== current.providerTaskId
    ) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    if (
      providerTask.status === "PENDING" ||
      providerTask.status === "THROTTLED"
    ) {
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    if (providerTask.status === "RUNNING") {
      let processing: Json | null = null;
      try {
        processing = await withOperationDeadline(
          updateSystemJob({
            job_id: current.id,
            provider_task_id: current.providerTaskId,
            status: "processing",
          }),
          OUTPUT_DATABASE_TIMEOUT_MS,
        );
      } catch {
        processing = null;
      }
      if (processing === null) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(current),
        }, 503);
      }
      return await respondWithCurrent(
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    if (
      providerTask.status === "FAILED" ||
      providerTask.status === "CANCELED" ||
      providerTask.status === "CANCELLED"
    ) {
      const failure = providerTaskFailure(providerValue);
      await markFailed(
        current.id,
        failure.failureCode,
        current.provider,
        current.providerTaskId,
        failure.providerFailureCode,
        failure.billingOutcome,
      );
      return await respondWithCurrent(
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    if (
      providerTask.status !== "SUCCEEDED" || !isRecord(providerValue) ||
      !Array.isArray(providerValue.output)
    ) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    if (current.status === "submitted") {
      let processing: Json | null = null;
      try {
        processing = await withOperationDeadline(
          updateSystemJob({
            job_id: current.id,
            provider_task_id: current.providerTaskId,
            status: "processing",
          }),
          OUTPUT_DATABASE_TIMEOUT_MS,
        );
      } catch {
        processing = null;
      }
      if (processing === null) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(current),
        }, 503);
      }
      const refreshed = await readCurrentStatusWithinDeadline(
        payload.organization_id,
        payload.job_id,
        payload.project_id,
      );
      if (refreshed === null) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(current),
        }, 503);
      }
      if (
        refreshed.status === "succeeded" || refreshed.status === "failed"
      ) {
        return await respondWithCurrent(
          payload.organization_id,
          payload.job_id,
          batch,
          payload.project_id,
        );
      }
      if (
        refreshed.status !== "processing" ||
        refreshed.providerTaskId !== current.providerTaskId
      ) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(refreshed),
        }, 503);
      }
      current = refreshed;
    }
    const outputUrl = current.provider === "google"
      ? validateGoogleOutputUrl(providerValue.output[0])
      : validateRunwayOutputUrl(providerValue.output[0]);
    if (outputUrl === null) {
      return await respondOutputRetryable(
        "output_validation_failed",
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }

    const photoOutput = current.model === "seedream5_lite";
    const outputMimeType = photoOutput ? "image/png" : "video/mp4";
    let outputBytes: Uint8Array<ArrayBuffer>;
    try {
      const outputResult: OutputFetchResult = current.provider === "google"
        ? await fetchGoogleOutput(outputUrl, secret)
        : await withFetchDeadline(
          outputUrl,
          { method: "GET", redirect: "manual" },
          OUTPUT_TIMEOUT_MS,
          async (outputResponse) => {
            const mimeType = (outputResponse.headers.get("content-type") ?? "")
              .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
            if (!outputResponse.ok) {
              await outputResponse.body?.cancel();
              return {
                ok: false as const,
                code: "output_download_failed" as const,
              };
            }
            const allowedMimeTypes = photoOutput
              ? new Set(["image/png", "application/octet-stream"])
              : new Set([
                "video/mp4",
                "application/mp4",
                "application/octet-stream",
              ]);
            if (!allowedMimeTypes.has(mimeType)) {
              await outputResponse.body?.cancel();
              return {
                ok: false as const,
                code: "output_validation_failed" as const,
              };
            }
            try {
              return {
                ok: true as const,
                bytes: await readBoundedBytes(
                  outputResponse,
                  MAX_OUTPUT_BYTES,
                ),
              };
            } catch (error) {
              return {
                ok: false as const,
                code: error instanceof ResponseSizeInvalidError
                  ? "output_validation_failed" as const
                  : "output_download_failed" as const,
              };
            }
          },
        );
      if (!outputResult.ok) {
        return await respondOutputRetryable(
          outputResult.code,
          payload.organization_id,
          payload.job_id,
          batch,
          payload.project_id,
        );
      }
      outputBytes = outputResult.bytes;
    } catch {
      return await respondOutputRetryable(
        "output_download_failed",
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    if (
      photoOutput ? !isPng(outputBytes) : !isMp4(outputBytes)
    ) {
      return await respondOutputRetryable(
        "output_validation_failed",
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    const digest = await sha256Hex(outputBytes);
    const storage = supabaseAdmin.storage.from(STORAGE_BUCKET);
    const uploadOptions = photoOutput
      ? {
        cacheControl: "31536000",
        contentType: "image/png",
        upsert: true,
        metadata: { sha256: digest },
      }
      : {
        cacheControl: "31536000",
        contentType: "video/mp4",
        upsert: true,
        metadata: { sha256: digest },
      };
    let uploadError: unknown;
    try {
      const upload = await withOperationDeadline(
        storage.upload(
          current.outputObjectName,
          outputBytes,
          uploadOptions,
        ),
        OUTPUT_STORAGE_TIMEOUT_MS,
      );
      uploadError = upload.error;
    } catch {
      uploadError = new OperationDeadlineError();
    }
    if (uploadError) {
      return await respondOutputRetryable(
        "output_upload_failed",
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }

    const successPayload = {
      job_id: current.id,
      provider_task_id: current.providerTaskId,
      status: "succeeded",
      output_object_name: current.outputObjectName,
      mime_type: outputMimeType,
      size_bytes: outputBytes.byteLength,
      sha256: digest,
    } satisfies Record<string, Json>;
    let completed: Json | null = null;
    try {
      completed = await withOperationDeadline(
        photoOutput
          ? completeSeedreamPhoto(successPayload)
          : updateSystemJob(successPayload),
        OUTPUT_DATABASE_TIMEOUT_MS,
      );
    } catch {
      completed = null;
    }
    if (completed === null) {
      return await respondOutputRetryable(
        "output_upload_failed",
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    current = await readCurrentStatusWithinDeadline(
      payload.organization_id,
      payload.job_id,
      payload.project_id,
    );
    if (current === null || current.status !== "succeeded") {
      return await respondOutputRetryable(
        "output_upload_failed",
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    const signedUrl = internalWorker ? null : await signOutput(current);
    if (!internalWorker && signedUrl === null) {
      return await respondOutputRetryable(
        "output_access_failed",
        payload.organization_id,
        payload.job_id,
        batch,
        payload.project_id,
      );
    }
    return json(request, {
      ok: true,
      ...(batch ? { batch } : {}),
      job: safeJob(current),
      ...(signedUrl ? { signed_url: signedUrl } : {}),
    });
  };

  const handleReconciliation = async (
    payload: ReconcilePayload,
  ): Promise<Response> => {
    const authorization = await readReconciliationAuthorization(payload);
    if (authorization === null) {
      return json(
        request,
        { ok: false, code: "generation_reconciliation_forbidden" },
        403,
      );
    }
    const expectedConfirmation = authorization.provider === "google"
      ? payload.resolution === "attach_existing_task"
        ? "GOOGLE_OPERATION_ID_VERIFIED"
        : "GOOGLE_NO_OPERATION_VERIFIED"
      : payload.resolution === "attach_existing_task"
      ? "RUNWAY_TASK_ID_VERIFIED"
      : "RUNWAY_NO_TASK_VERIFIED";
    if (
      payload.confirmation !== expectedConfirmation ||
      (payload.resolution === "attach_existing_task" &&
        !isValidProviderTaskId(
          authorization.provider,
          payload.provider_task_id,
        ))
    ) {
      return json(
        request,
        { ok: false, code: "generation_reconciliation_task_mismatch" },
        422,
      );
    }

    const systemPayload: Record<string, Json> = {
      job_id: payload.job_id,
      actor_id: authorization.actorId,
      incident_id: authorization.incidentId,
      idempotency_key: payload.idempotency_key,
      resolution: payload.resolution,
      evidence_reference: payload.evidence_reference,
      reason: payload.reason,
    };

    if (payload.resolution === "attach_existing_task") {
      const secret = authorization.provider === "google"
        ? googleApiKey()
        : runwaySecret();
      if (secret === null) {
        return json(
          request,
          { ok: false, code: "provider_unavailable" },
          503,
        );
      }
      let providerResponse: ProviderJsonResult;
      try {
        const reconciliationStatusUrl = authorization.provider === "google"
          ? `${GOOGLE_GENERATIVE_LANGUAGE_API_ORIGIN}/${GOOGLE_GENERATIVE_LANGUAGE_API_VERSION}/${payload.provider_task_id}`
          : `${RUNWAY_API_ORIGIN}/v1/tasks/${payload.provider_task_id}`;
        providerResponse = await fetchProviderJsonWithDeadline(
          reconciliationStatusUrl,
          {
            method: "GET",
            redirect: "manual",
            headers: authorization.provider === "google"
              ? { "x-goog-api-key": secret }
              : {
                authorization: `Bearer ${secret}`,
                "x-runway-version": RUNWAY_API_VERSION,
              },
          },
          PROVIDER_TIMEOUT_MS,
        );
      } catch {
        return json(
          request,
          { ok: false, code: "provider_unavailable" },
          503,
        );
      }
      if (!providerResponse.ok) {
        return json(
          request,
          {
            ok: false,
            code: providerResponse.status === 404
              ? "generation_reconciliation_task_not_found"
              : "provider_unavailable",
          },
          providerResponse.status === 404 ? 422 : 503,
        );
      }
      const providerValue = providerResponse.value;
      const googleOperation = authorization.provider === "google"
        ? parseGoogleOperation(providerValue)
        : null;
      const providerTask = authorization.provider === "google"
        ? googleOperation === null ? null : {
          id: googleOperation.name,
          status: !googleOperation.done
            ? "RUNNING"
            : googleOperation.error !== null
            ? "FAILED"
            : "SUCCEEDED",
          // Gemini's documented LRO response has no provider-created
          // timestamp. Never manufacture one from our own starting_at.
          createdAt: null,
        }
        : parseRunwayTask(providerValue);
      const allowedStatuses = new Set([
        "PENDING",
        "THROTTLED",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELED",
        "CANCELLED",
      ]);
      const startingAt = Date.parse(authorization.startingAt);
      const providerCreatedAt = providerTask?.createdAt
        ? Date.parse(providerTask.createdAt)
        : Number.NaN;
      const providerTimestampMatches = authorization.provider === "google"
        ? providerTask?.createdAt === null
        : Number.isFinite(providerCreatedAt) &&
          providerCreatedAt >=
            startingAt - RECONCILIATION_TASK_EARLY_SKEW_MS &&
          providerCreatedAt <=
            startingAt + RECONCILIATION_TASK_LATE_SKEW_MS &&
          providerCreatedAt <= Date.now() + 60_000;
      if (
        providerTask === null ||
        providerTask.id !== payload.provider_task_id ||
        !allowedStatuses.has(providerTask.status) ||
        !providerTimestampMatches
      ) {
        return json(
          request,
          { ok: false, code: "generation_reconciliation_task_mismatch" },
          422,
        );
      }
      systemPayload.provider_task_id = providerTask.id;
      if (authorization.provider === "runway") {
        systemPayload.provider_task_created_at = providerTask.createdAt;
      }
      systemPayload.provider_status = providerTask.status;
    } else if (
      Date.now() - Date.parse(authorization.requiredAt) < 2 * 60_000
    ) {
      return json(
        request,
        { ok: false, code: "generation_reconciliation_wait_required" },
        409,
      );
    }

    if (!(await reconcileSystemJob(systemPayload))) {
      return json(
        request,
        { ok: false, code: "generation_reconciliation_rejected" },
        409,
      );
    }
    return await respondWithCurrent(
      payload.organization_id,
      payload.job_id,
      undefined,
      payload.project_id,
    );
  };

  const recordProviderReadiness = async (
    payload: PreflightPayload,
    readiness: ProviderReadiness,
  ): Promise<ProviderReadinessRecordResult> => {
    const checkedBy = context.userClaims?.id;
    if (typeof checkedBy !== "string" || !isUuid(checkedBy)) {
      return { receipt: null, errorCode: null };
    }
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_record_generation_provider_readiness",
        {
          p_payload: {
            organization_id: payload.organization_id,
            checked_by: checkedBy,
            provider: readiness.provider,
            model: readiness.model,
            input_mode: readiness.inputMode,
            duration_seconds: readiness.durationSeconds,
            format: readiness.format,
            resolution: readiness.resolution,
            audio: readiness.audio,
            last_frame: readiness.lastFrame,
            ready: readiness.ready,
            estimated_cost_minor: readiness.estimatedCostMinor,
            estimated_credits: readiness.estimatedCredits,
            credential_configured: readiness.credentialConfigured,
            balance_sufficient: readiness.balanceSufficient,
            model_available: readiness.modelAvailable,
            daily_quota_available: readiness.dailyQuotaAvailable,
            failure_code: readiness.ready ? null : readiness.failureCode,
            spend_confirmation: readiness.spendConfirmation,
            catalog_version: GENERATION_MODEL_CATALOG_VERSION,
            pricing_version: readiness.provider === "google"
              ? GOOGLE_VEO_PRICING_VERSION
              : RUNWAY_PRICING_VERSION,
            learning_gate_version: GENERATION_LEARNING_GATE_VERSION,
            automatic_generation: false,
            automatic_spend: false,
            ...(generationModelRequiresReadinessV4(
                readiness.provider,
                readiness.model,
              )
              ? {
                project_id: payload.project_id,
                spec_id: payload.generation_spec_context?.spec_id,
                spec_version: payload.generation_spec_context?.spec_version,
                spec_hash: payload.generation_spec_context?.spec_hash,
              }
              : {}),
          },
        },
      );
      if (error !== null) {
        return {
          receipt: null,
          errorCode: readProviderReadinessRpcErrorCode(error),
        };
      }
      return {
        receipt: parseProviderReadinessReceipt(
          data,
          payload,
          checkedBy,
          readiness,
        ),
        errorCode: null,
      };
    } catch {
      return { receipt: null, errorCode: null };
    }
  };

  const handlePreflight = async (
    payload: PreflightPayload,
  ): Promise<Response> => {
    try {
      const { error } = await context.supabase.rpc(
        "creator_generation_spend_overview",
        { p_payload: { organization_id: payload.organization_id } },
      );
      if (error !== null) {
        return json(
          request,
          { ok: false, code: "generation_rejected" },
          403,
        );
      }
    } catch {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    const providerPolicy = await loadProviderPolicy(
      payload.organization_id,
      payload.provider,
      payload.model,
    );
    if (providerPolicy === null) {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    if (!providerPolicy.launchEnabled) {
      return json(
        request,
        { ok: false, code: "generation_provider_launch_disabled" },
        409,
      );
    }
    const exact = exactGenerationSku(
      payload.provider,
      payload.model,
      payload.duration_seconds,
      payload.format,
      payload.resolution,
      payload.audio,
      payload.last_frame,
      payload.last_frame ? 2 : 1,
      providerFeatureFlags(payload.provider, providerPolicy.launchEnabled),
    );
    if (exact === null) {
      return json(request, { ok: false, code: "invalid_payload" }, 400);
    }
    const secret = payload.provider === "google"
      ? googleApiKey()
      : runwaySecret();
    if (secret === null) {
      const unavailable: ProviderReadiness = {
        ready: false,
        provider: payload.provider,
        model: payload.model,
        inputMode: "image",
        durationSeconds: payload.duration_seconds,
        format: payload.format,
        resolution: payload.resolution,
        audio: payload.audio,
        lastFrame: payload.last_frame,
        estimatedCostMinor: exact.estimatedCostMinor,
        estimatedCredits: exact.estimatedCredits,
        credentialConfigured: false,
        balanceSufficient: payload.provider === "google" ? null : false,
        modelAvailable: false,
        dailyQuotaAvailable: payload.provider === "google" ? null : false,
        spendConfirmation: exact.confirmation,
        failureCode: "provider_configuration_error",
      };
      const recordedUnavailable = await recordProviderReadiness(
        payload,
        unavailable,
      );
      if (recordedUnavailable.receipt === null) {
        if (recordedUnavailable.errorCode !== null) {
          return json(
            request,
            { ok: false, code: recordedUnavailable.errorCode },
            409,
          );
        }
        return json(
          request,
          { ok: false, code: "generation_unavailable" },
          503,
        );
      }
      return json(
        request,
        { ok: false, code: "provider_configuration_error" },
        503,
      );
    }
    let readiness: ProviderReadiness;
    if (payload.provider === "google") {
      readiness = await checkGoogleProviderReadiness(secret, payload, exact);
    } else {
      const runway = await checkRunwayProviderReadiness(
        secret,
        exact,
      );
      readiness = runwayProviderReadiness(payload, runway);
    }
    const recordedReadiness = await recordProviderReadiness(payload, readiness);
    if (recordedReadiness.receipt === null) {
      if (recordedReadiness.errorCode !== null) {
        return json(
          request,
          { ok: false, code: recordedReadiness.errorCode },
          409,
        );
      }
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    const receipt = recordedReadiness.receipt;
    if (!readiness.ready) {
      const status = readiness.failureCode === "provider_credits_unavailable" ||
          readiness.failureCode === "provider_rate_limited"
        ? 409
        : 503;
      return json(
        request,
        { ok: false, code: readiness.failureCode },
        status,
      );
    }
    return json(request, {
      ok: true,
      preflight: {
        version: receipt.version,
        receipt_id: receipt.receiptId,
        receipt_hash: receipt.receiptHash,
        organization_id: payload.organization_id,
        checked_by: receipt.checkedBy,
        provider: readiness.provider,
        model: readiness.model,
        input_mode: readiness.inputMode,
        duration_seconds: readiness.durationSeconds,
        format: readiness.format,
        resolution: readiness.resolution,
        audio: readiness.audio,
        last_frame: readiness.lastFrame,
        ready: true,
        estimated_cost_minor: readiness.estimatedCostMinor,
        estimated_credits: readiness.estimatedCredits,
        credential_configured: readiness.credentialConfigured,
        balance_sufficient: readiness.balanceSufficient,
        model_available: readiness.modelAvailable,
        daily_quota_available: readiness.dailyQuotaAvailable,
        failure_code: null,
        catalog_version: GENERATION_MODEL_CATALOG_VERSION,
        pricing_version: readiness.provider === "google"
          ? GOOGLE_VEO_PRICING_VERSION
          : RUNWAY_PRICING_VERSION,
        learning_gate_version: GENERATION_LEARNING_GATE_VERSION,
        checked_at: receipt.checkedAt,
        expires_at: receipt.expiresAt,
        status: "ready",
        fresh: true,
        spend_confirmation: readiness.spendConfirmation,
        automatic_generation: false,
        automatic_spend: false,
        ...(receipt.version === PROVIDER_READINESS_RECEIPT_V4
          ? {
            project_id: receipt.projectId,
            spec_id: receipt.specId,
            spec_version: receipt.specVersion,
            spec_hash: receipt.specHash,
            scope_hash: receipt.scopeHash,
          }
          : {
            // Legacy response: version: "generation-provider-readiness-receipt-v3".
          }),
      },
    });
  };

  const loadPublicGenerationStrategyStatus = async (
    organizationId: string,
    projectId: string,
    actorId: string,
    generationJobId: string,
  ): Promise<Record<string, unknown> | null> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_generation_strategy_status",
        {
          p_payload: {
            version: "generation-strategy-status-request-v1",
            organization_id: organizationId,
            project_id: projectId,
            actor_id: actorId,
            generation_job_id: generationJobId,
          },
        },
      );
      if (error !== null) return null;
      return readPublicGenerationStrategyStatus(data, {
        projectId,
        generationJobId,
      });
    } catch {
      return null;
    }
  };

  const strategyWorkerResponse = (
    generationJobId: string,
    status: string,
  ): Response =>
    json(request, {
      ok: true,
      job: { id: generationJobId, status },
    });

  const recordGenerationStrategyDispatchResult = async (
    identity: {
      organizationId: string;
      projectId: string;
      actorId: string;
      generationJobId: string;
      attemptId: string;
      attemptHash: string;
      dispatchToken: string;
    },
    outcome: {
      outcome: "submitted" | "ambiguous" | "rejected";
      provider_post_started: boolean;
      provider_http_status: number | null;
      provider_task_id: string | null;
      failure_code: string | null;
    },
    providerEvidenceHash: string,
  ): Promise<Record<string, unknown> | null> => {
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_record_generation_strategy_dispatch_result",
        {
          p_payload: {
            version: "generation-strategy-dispatch-result-request-v1",
            organization_id: identity.organizationId,
            project_id: identity.projectId,
            actor_id: identity.actorId,
            attempt_id: identity.attemptId,
            attempt_hash: identity.attemptHash,
            dispatch_token: identity.dispatchToken,
            generation_job_id: identity.generationJobId,
            outcome: outcome.outcome,
            provider_post_started: outcome.provider_post_started,
            provider_http_status: outcome.provider_http_status,
            provider_task_id: outcome.provider_task_id,
            failure_code: outcome.failure_code,
            provider_evidence_hash: providerEvidenceHash,
            confirmation: true,
            idempotency_key: `strategy-dispatch-result:${identity.attemptId}`,
          },
        },
      );
      if (error !== null) return null;
      return readGenerationStrategyDispatchResult(data, {
        attemptId: identity.attemptId,
        attemptHash: identity.attemptHash,
        generationJobId: identity.generationJobId,
      });
    } catch {
      return null;
    }
  };

  const signAndValidateGenerationStrategyAssets = async (
    assets: Array<Record<string, unknown>>,
  ): Promise<
    | { ok: true; assets: GenerationStrategySignedRoleAsset[] }
    | {
      ok: false;
      code:
        | "input_signing_failed"
        | "input_asset_not_current"
        | "signed_url_invalid";
    }
  > => {
    const output: GenerationStrategySignedRoleAsset[] = [];
    for (const asset of assets) {
      let signedUrl: string | null = null;
      try {
        const signed = await supabaseAdmin.storage.from(String(asset.bucket_id))
          .createSignedUrl(String(asset.object_name), INPUT_URL_TTL_SECONDS);
        signedUrl = signed.error === null
          ? validateSupabaseSignedUrl(signed.data?.signedUrl)
          : null;
      } catch {
        return { ok: false, code: "input_signing_failed" };
      }
      if (signedUrl === null) {
        return { ok: false, code: "input_signing_failed" };
      }
      if (signedUrl.length > STRATEGY_SIGNED_URL_MAX_LENGTH) {
        return { ok: false, code: "signed_url_invalid" };
      }
      try {
        const current = await withFetchDeadline(
          signedUrl,
          { method: "HEAD", redirect: "manual" },
          STRATEGY_INPUT_HEAD_TIMEOUT_MS,
          async (response) => {
            const mimeType = (response.headers.get("content-type") ?? "")
              .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
            const size = Number(response.headers.get("content-length") ?? "");
            await response.body?.cancel();
            return response.status === 200 && mimeType === asset.mime_type &&
              Number.isSafeInteger(size) && size === asset.size_bytes;
          },
        );
        if (!current) {
          return { ok: false, code: "input_asset_not_current" };
        }
      } catch {
        return { ok: false, code: "input_asset_not_current" };
      }
      output.push({
        role: asset.role as GenerationStrategySignedRoleAsset["role"],
        uri: signedUrl,
        ...(typeof asset.view === "string"
          ? { view: asset.view as "front" | "side" | "back" }
          : {}),
      });
    }
    return { ok: true, assets: output };
  };

  const strategyPromptHashesMatch = async (
    recipeContext: Record<string, unknown>,
  ): Promise<boolean> => {
    const productInfo = recipeContext.productInfo;
    const productInfoHash = recipeContext.productInfoHash;
    const userConcept = recipeContext.userConcept;
    const userConceptHash = recipeContext.userConceptHash;
    if (
      typeof productInfo === "string" &&
      await sha256Hex(new TextEncoder().encode(productInfo)) !== productInfoHash
    ) return false;
    if (
      productInfo === null && productInfoHash !== null ||
      typeof productInfo !== "string" && productInfo !== null
    ) return false;
    if (
      typeof userConcept === "string" &&
      await sha256Hex(new TextEncoder().encode(userConcept)) !== userConceptHash
    ) return false;
    return !(userConcept === null && userConceptHash !== null) &&
      (typeof userConcept === "string" || userConcept === null);
  };

  const continueGenerationStrategyClaim = async (
    identity: {
      organizationId: string;
      projectId: string;
      actorId: string;
      claimId: string;
      claimHash: string;
      generationJobId: string;
      campaignId?: string;
    },
  ): Promise<{ status: string; providerTaskId: string | null } | null> => {
    let attempt: Record<string, unknown> | null = null;
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_mark_generation_strategy_dispatch_attempt",
        {
          p_payload: {
            version: "generation-strategy-dispatch-attempt-request-v1",
            organization_id: identity.organizationId,
            project_id: identity.projectId,
            actor_id: identity.actorId,
            claim_id: identity.claimId,
            claim_hash: identity.claimHash,
            generation_job_id: identity.generationJobId,
            confirmation: true,
            idempotency_key: `strategy-dispatch-attempt:${identity.claimId}`,
          },
        },
      );
      if (error !== null) return null;
      attempt = readGenerationStrategyDispatchAttempt(data, {
        claimId: identity.claimId,
        claimHash: identity.claimHash,
        generationJobId: identity.generationJobId,
        ...(identity.campaignId ? { campaignId: identity.campaignId } : {}),
      });
    } catch {
      return null;
    }
    if (attempt === null) return null;
    if (
      attempt.dispatch_allowed !== true || attempt.replay !== false ||
      attempt.terminal_result !== null
    ) {
      return {
        status: attempt.terminal_result === null ? "starting" : "failed",
        providerTaskId: null,
      };
    }
    const attemptRow = attempt.attempt as Record<string, unknown>;
    const dispatchIdentity = {
      ...identity,
      attemptId: String(attemptRow.id),
      attemptHash: String(attemptRow.attempt_hash),
      dispatchToken: String(attemptRow.dispatch_token),
    };
    const rejectBeforePost = async (
      code:
        | "input_signing_failed"
        | "input_asset_not_current"
        | "signed_url_invalid",
    ): Promise<{ status: string; providerTaskId: string | null } | null> => {
      const rejected = preDispatchStrategyFailure(code);
      if (rejected === null) return null;
      const evidence = await sha256Hex(new TextEncoder().encode(stableJson({
        version: "generation-strategy-pre-dispatch-evidence-v1",
        attempt_id: dispatchIdentity.attemptId,
        code,
      })));
      const result = await recordGenerationStrategyDispatchResult(
        dispatchIdentity,
        rejected,
        evidence,
      );
      return result === null
        ? null
        : { status: "failed", providerTaskId: null };
    };

    const secret = runwaySecret();
    if (secret === null) return await rejectBeforePost("input_signing_failed");
    const recipeContext = attempt.recipe_context as Record<string, unknown>;
    if (!(await strategyPromptHashesMatch(recipeContext))) {
      return await rejectBeforePost("input_asset_not_current");
    }
    const signedAssets = await signAndValidateGenerationStrategyAssets(
      attempt.asset_context as Array<Record<string, unknown>>,
    );
    if (!signedAssets.ok) {
      return await rejectBeforePost(signedAssets.code);
    }
    const providerRequest = buildGenerationStrategyProviderRequest(
      recipeContext as unknown as GenerationStrategyRecipeContext,
      signedAssets.assets,
    );
    if (providerRequest === null) {
      return await rejectBeforePost("input_asset_not_current");
    }
    let serialized: string;
    try {
      serialized = JSON.stringify(providerRequest.body);
    } catch {
      return await rejectBeforePost("input_asset_not_current");
    }
    if (
      new TextEncoder().encode(serialized).byteLength > MAX_PROVIDER_JSON_BYTES
    ) {
      return await rejectBeforePost("input_asset_not_current");
    }

    let outcome: ReturnType<typeof classifyRunwayRecipeCreateOutcome>;
    let evidenceValue: unknown;
    try {
      // SQL C is the unique dispatch owner. This is the sole fetch call in this
      // continuation and providerPostStarted becomes true immediately before it.
      const response = await fetchProviderJsonWithDeadline(
        `${RUNWAY_API_ORIGIN}${providerRequest.endpointPath}`,
        {
          method: "POST",
          redirect: "manual",
          headers: {
            authorization: `Bearer ${secret}`,
            "content-type": "application/json",
            "x-runway-version": RUNWAY_API_VERSION,
          },
          body: serialized,
        },
        PROVIDER_TIMEOUT_MS,
      );
      const task = response.ok ? parseCreatedRunwayTask(response.value) : null;
      evidenceValue = {
        status: response.status,
        body: response.ok ? response.value : null,
      };
      outcome = classifyRunwayRecipeCreateOutcome({
        kind: "response",
        status: response.status,
        providerTaskId: task?.id || null,
      });
    } catch (error) {
      evidenceValue = {
        status: null,
        error: error instanceof ProviderResponseInvalidError
          ? "provider_response_invalid"
          : "provider_network_unknown",
      };
      outcome = classifyRunwayRecipeCreateOutcome({ kind: "network" });
    }
    if (outcome === null) return null;
    const evidenceHash = await sha256Hex(new TextEncoder().encode(stableJson({
      version: "generation-strategy-provider-create-evidence-v1",
      attempt_id: dispatchIdentity.attemptId,
      evidence: evidenceValue,
    })));
    const recorded = await recordGenerationStrategyDispatchResult(
      dispatchIdentity,
      outcome,
      evidenceHash,
    );
    if (recorded === null) return null;
    const result = recorded.result as Record<string, unknown>;
    return {
      status: result.outcome === "submitted"
        ? "submitted"
        : result.outcome === "ambiguous"
        ? "starting"
        : "failed",
      providerTaskId: typeof result.provider_task_id === "string"
        ? result.provider_task_id
        : null,
    };
  };

  const generationStrategyOutputObjectName = async (
    organizationId: string,
    projectId: string,
    actorId: string,
    generationJobId: string,
  ): Promise<string | null> => {
    try {
      const claims = await supabaseAdmin.schema("content_factory")
        .from("generation_strategy_start_claims")
        .select("organization_id, project_id, actor_id, generation_job_id")
        .eq("organization_id", organizationId)
        .eq("project_id", projectId)
        .eq("actor_id", actorId)
        .eq("generation_job_id", generationJobId)
        .maybeSingle();
      if (claims.error !== null || !isRecord(claims.data)) return null;
      const jobs = await supabaseAdmin.schema("content_factory")
        .from("generation_jobs")
        .select("id, organization_id, project_id, input")
        .eq("organization_id", organizationId)
        .eq("project_id", projectId)
        .eq("id", generationJobId)
        .maybeSingle();
      if (
        jobs.error !== null || !isRecord(jobs.data) ||
        !isRecord(jobs.data.input) ||
        !isObjectName(jobs.data.input.output_object_name)
      ) return null;
      return jobs.data.input.output_object_name;
    } catch {
      return null;
    }
  };

  const pollGenerationStrategyProvider = async (
    identity: {
      organizationId: string;
      projectId: string;
      actorId: string;
      generationJobId: string;
      providerTaskId: string;
    },
  ): Promise<string | null> => {
    const secret = runwaySecret();
    if (secret === null) return null;
    let response: ProviderJsonResult;
    try {
      response = await fetchProviderJsonWithDeadline(
        `${RUNWAY_API_ORIGIN}/v1/tasks/${identity.providerTaskId}`,
        {
          method: "GET",
          redirect: "manual",
          headers: {
            authorization: `Bearer ${secret}`,
            "x-runway-version": RUNWAY_API_VERSION,
          },
        },
        PROVIDER_TIMEOUT_MS,
      );
    } catch {
      return null;
    }
    if (!response.ok) return null;
    const providerState = runwayStrategyProviderStatus(response.value);
    if (
      providerState === null || !isRecord(response.value) ||
      response.value.id !== identity.providerTaskId
    ) return null;
    const evidenceHash = await sha256Hex(new TextEncoder().encode(stableJson({
      version: "generation-strategy-provider-status-evidence-v1",
      provider_task_id: identity.providerTaskId,
      response: response.value,
    })));
    let output: Record<string, Json> | null = null;
    if (providerState.providerStatus === "succeeded") {
      const outputUrl = validateRunwayOutputUrl(providerState.outputUrl);
      const outputObjectName = await generationStrategyOutputObjectName(
        identity.organizationId,
        identity.projectId,
        identity.actorId,
        identity.generationJobId,
      );
      if (outputUrl === null || outputObjectName === null) return null;
      let outputBytes: Uint8Array<ArrayBuffer>;
      try {
        outputBytes = await withFetchDeadline(
          outputUrl,
          { method: "GET", redirect: "manual" },
          OUTPUT_TIMEOUT_MS,
          async (outputResponse) => {
            const mimeType = (outputResponse.headers.get("content-type") ?? "")
              .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
            if (
              outputResponse.status !== 200 || !new Set([
                "video/mp4",
                "application/mp4",
                "application/octet-stream",
              ]).has(mimeType)
            ) {
              await outputResponse.body?.cancel();
              throw new Error("strategy_output_invalid");
            }
            return await readBoundedBytes(outputResponse, MAX_OUTPUT_BYTES);
          },
        );
      } catch {
        return null;
      }
      if (!isMp4(outputBytes)) return null;
      const digest = await sha256Hex(outputBytes);
      try {
        const uploaded = await withOperationDeadline(
          supabaseAdmin.storage.from(STORAGE_BUCKET).upload(
            outputObjectName,
            outputBytes,
            {
              cacheControl: "31536000",
              contentType: "video/mp4",
              upsert: true,
              metadata: { sha256: digest },
            },
          ),
          OUTPUT_STORAGE_TIMEOUT_MS,
        );
        if (uploaded.error !== null) return null;
      } catch {
        return null;
      }
      output = {
        output_object_name: outputObjectName,
        mime_type: "video/mp4",
        size_bytes: outputBytes.byteLength,
        sha256: digest,
      };
    }
    const idempotency =
      `strategy-provider-status:${identity.generationJobId}:` +
      `${providerState.providerStatus}:${evidenceHash.slice(0, 32)}`;
    try {
      const recorded = await supabaseAdmin.rpc(
        "system_record_generation_strategy_provider_status",
        {
          p_payload: {
            version: "generation-strategy-provider-status-record-request-v1",
            organization_id: identity.organizationId,
            project_id: identity.projectId,
            actor_id: identity.actorId,
            generation_job_id: identity.generationJobId,
            provider_task_id: identity.providerTaskId,
            provider_status: providerState.providerStatus,
            output,
            failure_code: providerState.failureCode,
            provider_evidence_hash: evidenceHash,
            confirmation: true,
            idempotency_key: idempotency,
          },
        },
      );
      if (recorded.error !== null) return null;
      const parsed = readGenerationStrategyProviderStatusResult(recorded.data, {
        generationJobId: identity.generationJobId,
        providerTaskId: identity.providerTaskId,
      });
      if (parsed === null) return null;
      const event = parsed.event as Record<string, unknown>;
      return event.provider_status === "succeeded"
        ? "succeeded"
        : event.provider_status === "failed"
        ? "failed"
        : event.provider_status === "cancelled"
        ? "cancelled"
        : "processing";
    } catch {
      return null;
    }
  };

  const handleGenerationStrategyStatus = async (
    payload: GenerationStrategyStatusPayload,
  ): Promise<Response> => {
    const actorId = internalWorker
      ? payload.worker_context?.actor_id
      : context.userClaims?.id;
    if (!isUuid(actorId)) {
      return json(request, { ok: false, code: "authentication_required" }, 401);
    }
    if (internalWorker && payload.worker_context !== undefined) {
      const worker = payload.worker_context;
      if (worker.phase === "pre_dispatch") {
        const continued = await continueGenerationStrategyClaim({
          organizationId: payload.organization_id,
          projectId: payload.project_id,
          actorId,
          claimId: worker.start_claim_id,
          claimHash: worker.claim_hash,
          generationJobId: payload.generation_job_id,
        });
        return continued === null
          ? json(request, { ok: false, code: "generation_unavailable" }, 503)
          : strategyWorkerResponse(payload.generation_job_id, continued.status);
      }
      if (worker.phase === "dispatch_unknown") {
        if (
          !isUuid(worker.dispatch_attempt_id) ||
          typeof worker.attempt_hash !== "string" ||
          !SHA256_PATTERN.test(worker.attempt_hash) ||
          !isUuid(worker.dispatch_token)
        ) {
          return json(request, { ok: false, code: "invalid_payload" }, 400);
        }
        const ambiguous = classifyRunwayRecipeCreateOutcome({
          kind: "network",
        });
        if (ambiguous === null) {
          return json(
            request,
            { ok: false, code: "generation_unavailable" },
            503,
          );
        }
        const evidenceHash = await sha256Hex(
          new TextEncoder().encode(stableJson({
            version: "generation-strategy-dispatch-unknown-evidence-v1",
            attempt_id: worker.dispatch_attempt_id,
            provider_post_outcome: "unknown_after_90_seconds",
          })),
        );
        const recorded = await recordGenerationStrategyDispatchResult(
          {
            organizationId: payload.organization_id,
            projectId: payload.project_id,
            actorId,
            generationJobId: payload.generation_job_id,
            attemptId: worker.dispatch_attempt_id,
            attemptHash: worker.attempt_hash,
            dispatchToken: worker.dispatch_token,
          },
          ambiguous,
          evidenceHash,
        );
        return recorded === null
          ? json(request, { ok: false, code: "generation_unavailable" }, 503)
          : strategyWorkerResponse(payload.generation_job_id, "starting");
      }
      if (
        worker.phase === "provider_poll" &&
        isStrategyRunwayTaskId(worker.provider_task_id)
      ) {
        const status = await pollGenerationStrategyProvider({
          organizationId: payload.organization_id,
          projectId: payload.project_id,
          actorId,
          generationJobId: payload.generation_job_id,
          providerTaskId: worker.provider_task_id as string,
        });
        return status === null
          ? json(request, { ok: false, code: "provider_unavailable" }, 503)
          : strategyWorkerResponse(payload.generation_job_id, status);
      }
      return json(request, { ok: false, code: "invalid_payload" }, 400);
    }

    const current = await loadPublicGenerationStrategyStatus(
      payload.organization_id,
      payload.project_id,
      actorId,
      payload.generation_job_id,
    );
    if (current === null) {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    const contract = current.contract as Record<string, unknown>;
    const job = current.job as Record<string, unknown>;
    if (
      contract.poll_provider_allowed === true &&
      isStrategyRunwayTaskId(job.provider_task_id)
    ) {
      await pollGenerationStrategyProvider({
        organizationId: payload.organization_id,
        projectId: payload.project_id,
        actorId,
        generationJobId: payload.generation_job_id,
        providerTaskId: job.provider_task_id as string,
      });
      const refreshed = await loadPublicGenerationStrategyStatus(
        payload.organization_id,
        payload.project_id,
        actorId,
        payload.generation_job_id,
      );
      if (refreshed !== null) return json(request, refreshed);
    }
    return json(request, current);
  };

  const handleGenerationStrategyStart = async (
    payload: GenerationStrategyStartPayload,
  ): Promise<Response> => {
    const actorId = context.userClaims?.id;
    if (!isUuid(actorId)) {
      return json(request, { ok: false, code: "authentication_required" }, 401);
    }
    let claim: Record<string, unknown> | null = null;
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_claim_generation_strategy_start",
        {
          p_payload: {
            version: "generation-strategy-start-claim-request-v1",
            organization_id: payload.organization_id,
            project_id: payload.project_id,
            actor_id: actorId,
            receipt_id: payload.receipt_id,
            receipt_hash: payload.receipt_hash,
            binding_id: payload.binding_id,
            binding_hash: payload.binding_hash,
            selection_hash: payload.selection_hash,
            price_hash: payload.price_hash,
            spend_confirmation: payload.spend_confirmation,
            campaign_id: payload.campaign_id,
            confirmation: true,
            idempotency_key: payload.idempotency_key,
          },
        },
      );
      if (error !== null) {
        const mapped = readGenerationStrategyRpcError(error);
        return json(
          request,
          { ok: false, code: mapped?.code || "generation_unavailable" },
          mapped?.status || 503,
        );
      }
      claim = readGenerationStrategyStartClaim(data, {
        receiptId: payload.receipt_id,
        receiptHash: payload.receipt_hash,
        bindingId: payload.binding_id,
        bindingHash: payload.binding_hash,
        selectionHash: payload.selection_hash,
        priceHash: payload.price_hash,
        spendConfirmation: payload.spend_confirmation,
        campaignId: payload.campaign_id,
      });
    } catch {
      claim = null;
    }
    if (claim === null) {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    const claimRow = claim.claim as Record<string, unknown>;
    const continued = await continueGenerationStrategyClaim({
      organizationId: payload.organization_id,
      projectId: payload.project_id,
      actorId,
      claimId: String(claimRow.id),
      claimHash: String(claimRow.claim_hash),
      generationJobId: String(claimRow.generation_job_id),
      campaignId: payload.campaign_id,
    });
    if (continued === null) {
      return json(request, {
        ok: false,
        code: "generation_dispatch_state_unavailable",
        generation_job_id: claimRow.generation_job_id,
      }, 503);
    }
    const current = await loadPublicGenerationStrategyStatus(
      payload.organization_id,
      payload.project_id,
      actorId,
      String(claimRow.generation_job_id),
    );
    return current === null
      ? json(request, { ok: false, code: "generation_unavailable" }, 503)
      : json(request, current);
  };

  const handleGenerationStrategyReconciliation = async (
    payload: GenerationStrategyReconcilePayload,
  ): Promise<Response> => {
    const actorId = context.userClaims?.id;
    if (!isUuid(actorId)) {
      return json(request, { ok: false, code: "authentication_required" }, 401);
    }
    const current = await loadPublicGenerationStrategyStatus(
      payload.organization_id,
      payload.project_id,
      actorId,
      payload.generation_job_id,
    );
    if (
      current === null || !isRecord(current.dispatch) ||
      current.dispatch.result_id !== payload.dispatch_result_id ||
      !isRecord(current.reconciliation) ||
      current.reconciliation.required !== true ||
      current.reconciliation.incident_id !== payload.incident_id
    ) {
      return json(
        request,
        { ok: false, code: "generation_strategy_reconciliation_not_current" },
        409,
      );
    }
    let providerTaskId: string | null = null;
    let providerTaskCreatedAt: string | null = null;
    let providerStatus: string | null = null;
    let providerEvidence: unknown = {
      evidence_reference: payload.evidence_reference,
      reason: payload.reason,
      resolution: payload.resolution,
    };
    if (payload.resolution === "attach_existing_task") {
      const secret = runwaySecret();
      if (
        secret === null || !isStrategyRunwayTaskId(payload.provider_task_id)
      ) {
        return json(request, { ok: false, code: "provider_unavailable" }, 503);
      }
      let response: ProviderJsonResult;
      try {
        response = await fetchProviderJsonWithDeadline(
          `${RUNWAY_API_ORIGIN}/v1/tasks/${payload.provider_task_id}`,
          {
            method: "GET",
            redirect: "manual",
            headers: {
              authorization: `Bearer ${secret}`,
              "x-runway-version": RUNWAY_API_VERSION,
            },
          },
          PROVIDER_TIMEOUT_MS,
        );
      } catch {
        return json(request, { ok: false, code: "provider_unavailable" }, 503);
      }
      const task = response.ok ? parseRunwayTask(response.value) : null;
      const state = response.ok
        ? runwayStrategyProviderStatus(response.value)
        : null;
      if (
        task === null || state === null ||
        task.id !== payload.provider_task_id ||
        task.createdAt === null
      ) {
        return json(
          request,
          {
            ok: false,
            code: "generation_strategy_reconciliation_task_mismatch",
          },
          422,
        );
      }
      providerTaskId = task.id;
      providerTaskCreatedAt = task.createdAt;
      providerStatus = state.providerStatus === "processing"
        ? task.status === "RUNNING" ? "processing" : "submitted"
        : state.providerStatus;
      providerEvidence = {
        ...providerEvidence as Record<string, unknown>,
        task: response.value,
      };
    }
    const evidenceHash = await sha256Hex(new TextEncoder().encode(stableJson({
      version: "generation-strategy-reconciliation-evidence-v1",
      evidence: providerEvidence,
    })));
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_reconcile_generation_strategy_dispatch",
        {
          p_payload: {
            version: "generation-strategy-dispatch-reconciliation-request-v1",
            organization_id: payload.organization_id,
            project_id: payload.project_id,
            actor_id: actorId,
            dispatch_result_id: payload.dispatch_result_id,
            generation_job_id: payload.generation_job_id,
            incident_id: payload.incident_id,
            resolution: payload.resolution === "attach_existing_task"
              ? "provider_task_attached"
              : "confirmed_not_submitted",
            provider_task_id: providerTaskId,
            provider_task_created_at: providerTaskCreatedAt,
            provider_status: providerStatus,
            external_evidence_hash: evidenceHash,
            confirmation: payload.confirmation,
            idempotency_key: payload.idempotency_key,
          },
        },
      );
      if (
        error !== null || readGenerationStrategyReconciliationResult(data, {
            dispatchResultId: payload.dispatch_result_id,
            generationJobId: payload.generation_job_id,
          }) === null
      ) {
        const mapped = readGenerationStrategyRpcError(error);
        return json(
          request,
          {
            ok: false,
            code: mapped?.code || "generation_strategy_reconciliation_rejected",
          },
          mapped?.status || 409,
        );
      }
    } catch {
      return json(request, { ok: false, code: "generation_unavailable" }, 503);
    }
    const refreshed = await loadPublicGenerationStrategyStatus(
      payload.organization_id,
      payload.project_id,
      actorId,
      payload.generation_job_id,
    );
    return refreshed === null
      ? json(request, { ok: false, code: "generation_unavailable" }, 503)
      : json(request, refreshed);
  };

  const strategyStartPayload = readGenerationStrategyStartPayload(body);
  if (!internalWorker && strategyStartPayload !== null) {
    return await handleGenerationStrategyStart(strategyStartPayload);
  }

  const strategyReconcilePayload = readGenerationStrategyReconcilePayload(body);
  if (!internalWorker && strategyReconcilePayload !== null) {
    return await handleGenerationStrategyReconciliation(
      strategyReconcilePayload,
    );
  }

  const generationStrategyStatusPayload = readGenerationStrategyStatusPayload(
    body,
    internalWorker,
  );
  if (generationStrategyStatusPayload !== null) {
    return await handleGenerationStrategyStatus(
      generationStrategyStatusPayload,
    );
  }

  const preflightPayload = readPreflightPayload(body);
  if (!internalWorker && preflightPayload !== null) {
    return await handlePreflight(preflightPayload);
  }

  const reconcilePayload = readReconcilePayload(body);
  if (!internalWorker && reconcilePayload !== null) {
    return await handleReconciliation(reconcilePayload);
  }

  const statusPayload = readStatusPayload(body);
  if (statusPayload !== null) return await handleStatus(statusPayload);

  if (internalWorker) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }

  const generationStrategyPayload = readGenerationStrategyPayload(body);
  if (generationStrategyPayload !== null) {
    if (!generationStrategyPayload.ok) {
      return json(request, { ok: false, code: "invalid_payload" }, 400);
    }
    // Parsing and provider-body construction are installed, but execution must
    // remain fail-closed until SQL returns one current spec-bound strategy
    // snapshot plus server-authorized signed assets and an exact launch policy.
    return json(
      request,
      { ok: false, code: "generation_strategy_start_not_ready" },
      409,
    );
  }

  const startPayload = readStartPayload(body);
  if (startPayload === null) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }
  const startProviderPolicy = await loadProviderPolicy(
    startPayload.organization_id,
    startPayload.provider,
    startPayload.model,
  );
  if (startProviderPolicy === null) {
    return json(
      request,
      { ok: false, code: "generation_unavailable" },
      503,
    );
  }
  if (!startProviderPolicy.launchEnabled) {
    return json(
      request,
      { ok: false, code: "generation_provider_launch_disabled" },
      409,
    );
  }
  const startProviderFeatureFlags = providerFeatureFlags(
    startPayload.provider,
    startProviderPolicy.launchEnabled,
  );
  const startSku = exactGenerationSku(
    startPayload.provider,
    startPayload.model,
    startPayload.duration_seconds,
    startPayload.format,
    startPayload.resolution,
    startPayload.audio,
    startPayload.last_frame,
    startPayload.media_ids.length,
    startProviderFeatureFlags,
  );
  if (
    startSku === null ||
    startPayload.spend_confirmation !== startSku.confirmation ||
    !startSelectionSnapshotMatches(startPayload, startSku)
  ) {
    return json(
      request,
      { ok: false, code: "generation_provider_selection_stale" },
      409,
    );
  }
  if (
    generationModelRequiresReadinessV4(
      startPayload.provider,
      startPayload.model,
    ) && startPayload.learning_context.source !== "baseline"
  ) {
    return json(
      request,
      { ok: false, code: "generation_spec_baseline_required" },
      409,
    );
  }
  if (!generationModePromptIsBound(startPayload)) {
    return json(
      request,
      { ok: false, code: "generation_mode_prompt_binding_invalid" },
      409,
    );
  }
  let effectiveGenerationPolicy: GenerationSpecEffectivePolicy | null = null;
  try {
    const { data, error } = await context.supabase.rpc(
      "creator_generation_spec_effective_policy",
      {
        p_payload: {
          organization_id: startPayload.organization_id,
          project_id: startPayload.project_id,
          ...startPayload.generation_spec_context,
        },
      },
    );
    if (error !== null) {
      const generationSpecError = readGenerationSpecRpcError(error);
      if (generationSpecError?.internal) {
        console.warn("Generation spec invariant rejected request", {
          stage: "effective_policy",
        });
      }
      return json(
        request,
        {
          ok: false,
          code: generationSpecError?.code ||
            "generation_spec_effective_policy_unavailable",
        },
        generationSpecError?.status || 503,
      );
    }
    effectiveGenerationPolicy = readGenerationSpecEffectivePolicy(
      data,
      startProviderFeatureFlags,
    );
  } catch {
    return json(
      request,
      { ok: false, code: "generation_spec_effective_policy_unavailable" },
      503,
    );
  }
  if (effectiveGenerationPolicy === null) {
    return json(
      request,
      { ok: false, code: "generation_spec_effective_policy_invalid" },
      503,
    );
  }
  const expectedSemantics = generationExecutionSemantics(
    startPayload.model,
    startPayload.audio,
    startPayload.last_frame,
    startPayload.media_ids.length,
  );
  if (expectedSemantics === null) {
    return json(
      request,
      { ok: false, code: "generation_spec_scope_binding_invalid" },
      409,
    );
  }
  const expectedScope: GenerationSpecScope = {
    primary_media_id: startPayload.media_ids[0],
    media_ids: startPayload.media_ids,
    platform: startPayload.platform,
    provider: startPayload.provider,
    model: startPayload.model,
    input_mode: startPayload.input_mode,
    duration_seconds: startPayload.duration_seconds,
    product_category: startPayload.product_category,
    format: startPayload.format,
    ratio: startPayload.format,
    resolution: startPayload.resolution,
    audio: startPayload.audio === true,
    spoken_dialogue: expectedSemantics.spokenDialogue,
    reference_count: expectedSemantics.referenceImageCount,
    reference_video: false,
    first_frame: expectedSemantics.firstFrame,
    last_frame: startPayload.last_frame,
  };
  const effectiveRepair = effectiveGenerationPolicy.repairContext;
  const requestedRepair = startPayload.repair_context || null;
  if (
    effectiveGenerationPolicy.projectId !== startPayload.project_id ||
    stableJson(effectiveGenerationPolicy.generationSpecContext) !==
      stableJson(startPayload.generation_spec_context) ||
    stableJson(effectiveGenerationPolicy.exactScope) !==
      stableJson(expectedScope)
  ) {
    return json(
      request,
      { ok: false, code: "generation_spec_scope_binding_invalid" },
      409,
    );
  }
  if (
    effectiveGenerationPolicy.compiledPrompt !== startPayload.brief ||
    await sha256Hex(new TextEncoder().encode(startPayload.brief)) !==
      effectiveGenerationPolicy.promptHash
  ) {
    return json(
      request,
      { ok: false, code: "generation_spec_prompt_binding_invalid" },
      422,
    );
  }
  if (
    stableJson(effectiveGenerationPolicy.learningContext) !==
      stableJson(startPayload.learning_context) ||
    stableJson(effectiveRepair) !== stableJson(requestedRepair)
  ) {
    return json(
      request,
      { ok: false, code: "generation_spec_policy_binding_invalid" },
      409,
    );
  }
  const learningSource = startPayload.learning_context.source;
  let learningPolicy: Record<string, unknown> | null = null;
  // Learning is advisory by default. Only an explicit "Применить совет"
  // selection binds performance learning to a paid request. Baseline and
  // research prompts do not wait for, or get vetoed by, the advice service.
  if (learningSource === "performance_learning") {
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_generation_learning_policy",
        {
          p_payload: {
            organization_id: startPayload.organization_id,
            project_id: startPayload.project_id,
            media_id: startPayload.media_ids[0],
            platform: startPayload.platform,
            model: startPayload.model,
            product_category: startPayload.product_category,
          },
        },
      );
      if (error !== null || !isRecord(data)) {
        return json(
          request,
          { ok: false, code: "generation_learning_unavailable" },
          503,
        );
      }
      learningPolicy = data;
    } catch {
      return json(
        request,
        { ok: false, code: "generation_learning_unavailable" },
        503,
      );
    }
    if (typeof learningPolicy.applied !== "boolean") {
      return json(
        request,
        { ok: false, code: "generation_learning_unavailable" },
        503,
      );
    }
  }
  if (
    (learningPolicy !== null &&
      learningPolicy.product_category !== startPayload.product_category) ||
    startPayload.learning_context.product_category !==
      startPayload.product_category
  ) {
    return json(
      request,
      { ok: false, code: "generation_learning_category_mismatch" },
      409,
    );
  }
  if (learningPolicy?.generation_allowed === false) {
    const effectivenessStatus =
      typeof learningPolicy.quality_guard_effectiveness_status === "string"
        ? learningPolicy.quality_guard_effectiveness_status
        : "";
    return json(
      request,
      {
        ok: false,
        code: effectivenessStatus === "control_pending_review"
          ? "generation_quality_guard_control_review_pending"
          : "generation_learning_rejection_guard_blocked",
      },
      409,
    );
  }
  const approvedResearchCategoryPrecedence =
    generationApprovedResearchCategoryRuleIsBound(effectiveGenerationPolicy);
  if (
    learningPolicy?.applied &&
    learningSource !== "performance_learning" &&
    startPayload.learning_opt_out !== true &&
    !approvedResearchCategoryPrecedence
  ) {
    return json(
      request,
      { ok: false, code: "generation_learning_policy_required" },
      409,
    );
  }
  if (
    learningPolicy?.applied === false &&
    learningSource === "performance_learning"
  ) {
    return json(
      request,
      { ok: false, code: "generation_learning_policy_stale" },
      409,
    );
  }
  if (
    learningSource === "performance_learning" &&
    (learningPolicy === null ||
      !generationLearningPromptIsBound(learningPolicy, startPayload))
  ) {
    return json(
      request,
      { ok: false, code: "generation_learning_prompt_binding_invalid" },
      422,
    );
  }
  if (startPayload.repair_context !== undefined) {
    let repairPolicy: Record<string, unknown> | null = null;
    try {
      const { data, error } = await context.supabase.rpc(
        "creator_generation_repair_policy",
        {
          p_payload: {
            organization_id: startPayload.organization_id,
            project_id: startPayload.project_id,
            review_id: startPayload.repair_context.source_review_id,
          },
        },
      );
      if (error !== null || !isRecord(data)) {
        return json(
          request,
          { ok: false, code: "generation_repair_unavailable" },
          503,
        );
      }
      repairPolicy = data;
    } catch {
      return json(
        request,
        { ok: false, code: "generation_repair_unavailable" },
        503,
      );
    }
    if (
      repairPolicy.applied !== true ||
      repairPolicy.policy_hash !== startPayload.repair_context.policy_hash ||
      repairPolicy.source_generation_job_id !==
        startPayload.repair_context.source_generation_job_id ||
      JSON.stringify(repairPolicy.guard_codes) !==
        JSON.stringify(startPayload.repair_context.guard_codes) ||
      repairPolicy.input_media_id !== startPayload.media_ids[0] ||
      repairPolicy.model !== startPayload.model ||
      repairPolicy.platform !== startPayload.platform ||
      repairPolicy.destination_ref !== startPayload.destination_ref
    ) {
      return json(
        request,
        { ok: false, code: "generation_repair_policy_stale" },
        409,
      );
    }
    if (!generationRepairPromptIsBound(repairPolicy, startPayload)) {
      return json(
        request,
        { ok: false, code: "generation_repair_prompt_binding_invalid" },
        422,
      );
    }
  }
  const { data: startData, error: startError } = await context.supabase.rpc(
    "creator_start_real_generation",
    { p_payload: rpcPayload(startPayload) },
  );
  if (startError) {
    const budgetCode = readBudgetErrorCode(startError);
    const generationSpecError = readGenerationSpecRpcError(startError);
    if (generationSpecError?.internal) {
      console.warn("Generation spec invariant rejected request", {
        stage: "paid_start",
      });
    }
    const safeStartRpcCode = readSafeStartRpcErrorCode(startError);
    const validationCode = [
        "real_generation_payload_invalid",
        "real_generation_sku_invalid",
        "real_generation_sku_binding_invalid",
        "product_reference_media_ids_invalid",
        "exact_product_reference_bundle_mismatch",
        "generation_reference_bundle_binding_invalid",
        "generation_product_interaction_invalid",
        "paid_generation_product_category_invalid",
        "paid_generation_product_category_binding_invalid",
        "generation_learning_context_invalid",
        "generation_learning_policy_stale",
        "generation_learning_prompt_binding_invalid",
        "generation_learning_research_provenance_invalid",
        "generation_learning_category_mismatch",
        "generation_learning_category_binding_invalid",
        "generation_mode_prompt_binding_invalid",
        "refreshed_courses_required",
        "required_courses_incomplete",
        "final_exam_required",
        "practical_project_approval_required",
      ].includes(startError.message)
      ? startError.message
      : null;
    const repairCode = [
        "generation_repair_context_invalid",
        "generation_repair_policy_stale",
        "generation_repair_prompt_binding_invalid",
        "generation_repair_job_binding_invalid",
        "generation_repair_signal_conflict",
      ].includes(startError.message)
      ? startError.message
      : null;
    const code = budgetCode ??
      (startError.message === "real_generation_reconciliation_required"
        ? "real_generation_reconciliation_required"
        : generationSpecError?.code ?? repairCode ?? validationCode ??
          safeStartRpcCode ??
          "generation_rejected");
    const status = budgetCode !== null
      ? budgetErrorHttpStatus(budgetCode)
      : generationSpecError !== null
      ? generationSpecError.status
      : code === "generation_rejected"
      ? 403
      : code === "real_generation_payload_invalid" ||
          code === "real_generation_sku_invalid" ||
          code === "real_generation_sku_binding_invalid" ||
          code === "product_reference_media_ids_invalid" ||
          code === "generation_reference_bundle_binding_invalid" ||
          code === "generation_product_interaction_invalid" ||
          code === "paid_generation_product_category_invalid" ||
          code === "paid_generation_product_category_binding_invalid" ||
          code === "generation_learning_context_invalid" ||
          code === "generation_learning_prompt_binding_invalid" ||
          code === "generation_mode_prompt_binding_invalid" ||
          code === "generation_repair_context_invalid" ||
          code === "generation_repair_prompt_binding_invalid"
      ? 422
      : 409;
    return json(
      request,
      { ok: false, code },
      status,
    );
  }
  const startJob = readStartJob(startData);
  if (
    startJob === null ||
    startJob.campaignId !== startPayload.campaign_id ||
    startJob.provider !== startSku.provider ||
    startJob.model !== startSku.model ||
    startJob.durationSeconds !== startSku.durationSeconds ||
    startJob.resolution !== startSku.resolution ||
    startJob.audio !== startSku.audio ||
    startJob.lastFrame !== startSku.lastFrame ||
    publicRatioFromProvider(
        startJob.model,
        startJob.ratio,
        startJob.resolution,
      ) !==
      startSku.format ||
    startJob.estimatedCostMinor !== startSku.estimatedCostMinor ||
    startJob.estimatedCredits !== startSku.estimatedCredits ||
    (
      startPayload.review_autostart_confirmed === true &&
      (
        !startJob.reviewAutostartConfirmed ||
        startJob.reviewAutostartTermsVersion !==
          "generated-video-qa-autostart-v1"
      )
    )
  ) {
    return json(request, { ok: false, code: "generation_rejected" }, 403);
  }
  const startRecord = startData as Record<string, unknown>;
  const startBatch = startRecord.batch as Record<string, unknown>;
  const batch = {
    id: startBatch.id as string,
    status: startBatch.status as string,
    campaign_id: startJob.campaignId,
    campaign_name: startJob.campaignName,
  };
  const current = await readCurrentStatus(
    startPayload.organization_id,
    startJob.id,
    startPayload.project_id,
  );
  if (
    current === null || current.batchId !== startJob.batchId ||
    current.campaignId !== startJob.campaignId ||
    current.campaignName !== startJob.campaignName ||
    current.outputObjectName !== startJob.outputObjectName
  ) {
    return json(
      request,
      { ok: false, code: "generation_unavailable" },
      503,
    );
  }
  const statusRequest: StatusPayload = {
    action: "status",
    organization_id: startPayload.organization_id,
    project_id: startPayload.project_id,
    job_id: startJob.id,
  };
  if (current.status !== "queued") {
    return await handleStatus(statusRequest, current, batch);
  }

  // This service-role RPC is the final paid-provider gate. The database
  // atomically validates the active reservation, organization kill switch,
  // policy version, and current spend limits while claiming queued -> starting.
  const claim = await claimSystemJob(current.id);
  if (claim.outcome === "budget_rejected") {
    return json(
      request,
      { ok: false, code: claim.code },
      claim.code === "real_generation_reconciliation_required"
        ? 409
        : budgetErrorHttpStatus(claim.code),
    );
  }
  if (claim.outcome === "terminal_rejected") {
    return json(
      request,
      {
        ok: false,
        code: claim.code,
        terminal: true,
        retryable: false,
      },
      409,
    );
  }
  if (claim.outcome !== "claimed") {
    return json(
      request,
      { ok: false, code: "generation_unavailable" },
      503,
    );
  }
  if (!claim.claimed) {
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }

  const secret = startJob.provider === "google"
    ? googleApiKey()
    : runwaySecret();
  if (secret === null) {
    await markFailed(
      startJob.id,
      "provider_configuration_error",
      startJob.provider,
    );
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  const preflightScope: PreflightPayload = {
    action: "preflight",
    organization_id: startPayload.organization_id,
    provider: startJob.provider,
    model: startJob.model,
    input_mode: "image",
    duration_seconds: startJob.durationSeconds,
    format: publicRatioFromProvider(
      startJob.model,
      startJob.ratio,
      startJob.resolution,
    ) ||
      startPayload.format,
    resolution: startJob.resolution,
    audio: startJob.audio,
    last_frame: startJob.lastFrame,
  };
  const providerReadiness = startJob.provider === "google"
    ? await checkGoogleProviderReadiness(secret, preflightScope, startSku)
    : runwayProviderReadiness(
      preflightScope,
      await checkRunwayProviderReadiness(
        secret,
        startSku,
      ),
    );
  if (!providerReadiness.ready) {
    await markFailed(
      startJob.id,
      providerReadiness.failureCode || "provider_request_failed",
      startJob.provider,
    );
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  const signedReferenceUrls = await Promise.all(
    startJob.referenceObjectNames.map(async (objectName) => {
      const { data, error } = await context.supabaseAdmin.storage
        .from(STORAGE_BUCKET)
        .createSignedUrl(objectName, INPUT_URL_TTL_SECONDS);
      return error ? null : validateSupabaseSignedUrl(data?.signedUrl);
    }),
  );
  if (signedReferenceUrls.some((url) => url === null)) {
    await markFailed(
      startJob.id,
      "provider_configuration_error",
      startJob.provider,
    );
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  const validReferenceUrls = signedReferenceUrls as string[];
  let googleInlineImages: Array<{
    mimeType: "image/png" | "image/jpeg" | "image/webp";
    data: string;
  }> = [];
  if (startJob.provider === "google") {
    try {
      googleInlineImages = await Promise.all(
        validReferenceUrls.map((url) => readGoogleInlineImage(url)),
      );
    } catch {
      await markFailed(startJob.id, "provider_request_rejected", "google");
      return await respondWithCurrent(
        startPayload.organization_id,
        startJob.id,
        batch,
        startPayload.project_id,
      );
    }
  }
  const providerRequest = buildProviderRequest(
    startJob,
    validReferenceUrls,
    googleInlineImages,
    startProviderFeatureFlags,
  );
  if (providerRequest === null) {
    await markFailed(
      startJob.id,
      "provider_request_rejected",
      startJob.provider,
    );
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  const providerEndpoint = providerRequest.provider === "google"
    ? `${GOOGLE_GENERATIVE_LANGUAGE_API_ORIGIN}${providerRequest.endpointPath}`
    : `${RUNWAY_API_ORIGIN}${providerRequest.endpointPath}`;
  let serializedProviderRequest: string;
  try {
    serializedProviderRequest = JSON.stringify(providerRequest.body);
  } catch {
    await markFailed(
      startJob.id,
      "provider_request_rejected",
      startJob.provider,
    );
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  const serializedRequestBytes = new TextEncoder().encode(
    serializedProviderRequest,
  ).byteLength;
  const providerRequestLimit = startJob.provider === "google"
    ? MAX_GOOGLE_PROVIDER_REQUEST_BYTES
    : MAX_PROVIDER_JSON_BYTES;
  if (serializedRequestBytes > providerRequestLimit) {
    await markFailed(
      startJob.id,
      "provider_request_rejected",
      startJob.provider,
    );
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }

  let createResponse: ProviderJsonResult;
  try {
    createResponse = await fetchProviderJsonWithDeadline(
      providerEndpoint,
      {
        method: "POST",
        redirect: "manual",
        headers: providerRequest.provider === "google"
          ? { "content-type": "application/json", "x-goog-api-key": secret }
          : {
            authorization: `Bearer ${secret}`,
            "content-type": "application/json",
            "x-runway-version": RUNWAY_API_VERSION,
          },
        body: serializedProviderRequest,
      },
      PROVIDER_TIMEOUT_MS,
    );
  } catch (error) {
    await markReconciliationRequired(
      startJob.id,
      error instanceof ProviderResponseInvalidError
        ? "provider_create_response_unknown"
        : "provider_create_timeout",
    );
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  if (!createResponse.ok) {
    if (DEFINITIVE_CREATE_HTTP_STATUSES.has(createResponse.status)) {
      await markFailed(
        startJob.id,
        providerFailureForHttp(createResponse.status),
        startJob.provider,
      );
      return await respondWithCurrent(
        startPayload.organization_id,
        startJob.id,
        batch,
        startPayload.project_id,
      );
    }
    await markReconciliationRequired(
      startJob.id,
      "provider_create_http_unknown",
    );
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }

  const createdValue: unknown = createResponse.value;
  const providerTask = startJob.provider === "google"
    ? parseCreatedGoogleOperation(createdValue)
    : parseCreatedRunwayTask(createdValue);
  if (providerTask === null) {
    await markReconciliationRequired(
      startJob.id,
      "provider_create_response_unknown",
    );
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  const submittedPayload: Record<string, Json> = {
    job_id: startJob.id,
    provider_task_id: providerTask.id,
    status: "submitted",
  };
  let submitted = await updateSystemJob(submittedPayload);
  if (submitted === null) {
    // Replaying the exact provider task id is safe and closes the common
    // response-loss window without ever issuing another paid provider call.
    submitted = await updateSystemJob(submittedPayload);
  }
  if (submitted === null) {
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
      startPayload.project_id,
    );
  }
  return await respondWithCurrent(
    startPayload.organization_id,
    startJob.id,
    batch,
    startPayload.project_id,
  );
}

const creatorGenerate = withSupabase<ContentEngineDatabase>(
  CREATOR_GENERATE_USER_OPTIONS,
  (request, context) => handleCreatorGenerate(request, context, false),
);
const creatorGenerateWorker = withSupabase<ContentEngineDatabase>(
  CREATOR_GENERATE_WORKER_OPTIONS,
  (request, context) => handleCreatorGenerate(request, context, true),
);

export default {
  fetch(request: Request): Promise<Response> | Response {
    if (request.method === "OPTIONS") {
      if (!USER_APP_ORIGINS.has(request.headers.get("origin") ?? "")) {
        return json(request, { ok: false, code: "origin_not_allowed" }, 403);
      }
      return new Response(null, {
        status: 204,
        headers: responseHeaders(request),
      });
    }
    if (isInternalWorkerRequest(request)) {
      return creatorGenerateWorker(request);
    }
    return creatorGenerate(request);
  },
};
