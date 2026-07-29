import { type SupabaseContext, withSupabase } from "npm:@supabase/server@1.3.0";
import {
  INTERNAL_WORKER_HEADER,
  isInternalWorkerAuthorized,
  isInternalWorkerRequest,
} from "../_shared/internal-worker-auth.ts";

const PUBLIC_APP_ORIGIN = "https://alisia777.github.io";
const LOCAL_QA_APP_ORIGIN = "http://127.0.0.1:8767";
const USER_APP_ORIGINS = new Set([
  PUBLIC_APP_ORIGIN,
  LOCAL_QA_APP_ORIGIN,
]);
const RUNWAY_API_ORIGIN = "https://api.dev.runwayml.com";
const RUNWAY_API_VERSION = "2024-11-06";
const GENERATION_LEARNING_GATE_VERSION = "2026-07-29.v8";
const RUNWAY_PRODUCT_REFERENCE_TAG = "ProductReference";
const GENERATED_TEXT_GUARD =
  "Без сгенерированных надписей, субтитров и декоративного текста.";
const RUNWAY_OUTPUT_HOST = "dnznrvs05pmza.cloudfront.net";
const STORAGE_BUCKET = "contentengine-private";
const MAX_BODY_BYTES = 16_384;
const MAX_PROVIDER_JSON_BYTES = 65_536;
const MAX_OUTPUT_BYTES = 52_428_800;
const INPUT_URL_TTL_SECONDS = 3_600;
const OUTPUT_URL_TTL_SECONDS = 300;
const PROVIDER_TIMEOUT_MS = 20_000;
const MIN_PROVIDER_POLL_INTERVAL_MS = 5_000;
const STARTING_RECONCILIATION_AFTER_MS = 90_000;
const RECONCILIATION_TASK_EARLY_SKEW_MS = 2 * 60_000;
const RECONCILIATION_TASK_LATE_SKEW_MS = 10 * 60_000;
const OUTPUT_TIMEOUT_MS = 120_000;
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu;
const SHA256_PATTERN = /^[0-9a-f]{64}$/u;
const TASK_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u;
const IDEMPOTENCY_PATTERN = /^[A-Za-z0-9._:-]{8,180}$/u;
const GEN4_RATIOS = new Set(["1280:720", "720:1280", "960:960"]);
const SEEDANCE_FAST_RATIO = "720:1280";
const SEEDREAM5_LITE_RATIO = "2048:2048";
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
const RUNWAY_PROMPT_LIMITS = Object.freeze({
  gen4_turbo: 1_000,
  seedance2_fast: 1_200,
  seedream5_lite: 1_200,
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
  | "real_generation_reconciliation_required";

type ClaimResult =
  | { outcome: "claimed"; claimed: boolean }
  | { outcome: "budget_rejected"; code: ClaimErrorCode }
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
      creator_generation_learning_policy: {
        Args: { p_payload: Json };
        Returns: Json;
      };
      creator_generation_repair_policy: {
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

type CommonStartPayload = {
  action: "start";
  organization_id: string;
  campaign_id: string;
  idempotency_key: string;
  sku: string;
  product_name: string;
  product_category: ProductCategory;
  count: 1;
  format: "9:16" | "1:1" | "16:9";
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
  provider: "runway";
  allow_real_spend: true;
  learning_context: GenerationLearningContext;
  learning_opt_out?: true;
  repair_context?: GenerationRepairContext;
  review_autostart_confirmed?: true;
  review_autostart_terms_version?: "generated-video-qa-autostart-v1";
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

type StartPayload =
  & CommonStartPayload
  & (
    | {
      model: "gen4_turbo";
      duration_seconds: number;
      audio?: false;
      spend_confirmation: string;
    }
    | {
      model: "seedance2_fast";
      duration_seconds: number;
      audio: true;
      format: "9:16";
      spend_confirmation: string;
    }
    | {
      model: "seedream5_lite";
      duration_seconds: 0;
      audio?: false;
      format: "1:1";
      spend_confirmation: "RUNWAY_SEEDREAM5_LITE_2K_USD_0.04";
    }
  );

type RunwayModel = keyof typeof RUNWAY_SKU_CONFIG;

type PreflightPayload = {
  action: "preflight";
  organization_id: string;
  model: RunwayModel;
  duration_seconds: number;
};

type StatusPayload = {
  action: "status";
  organization_id: string;
  job_id: string;
};

type ReconcilePayload = {
  action: "reconcile";
  organization_id: string;
  job_id: string;
  incident_id: string;
  idempotency_key: string;
  resolution: "attach_existing_task" | "confirm_no_submission";
  provider_task_id?: string;
  evidence_reference: string;
  reason: string;
  confirmation:
    | "RUNWAY_TASK_ID_VERIFIED"
    | "RUNWAY_NO_TASK_VERIFIED";
};

type ReconciliationContext = {
  actorId: string;
  incidentId: string;
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

type ProviderReadinessReceipt = {
  receiptId: string;
  receiptHash: string;
  checkedAt: string;
  expiresAt: string;
};

type StartJob = {
  id: string;
  batchId: string;
  campaignId: string;
  campaignName: string;
  status: string;
  provider: "runway";
  model: "gen4_turbo" | "seedance2_fast" | "seedream5_lite";
  durationSeconds: number;
  audio: boolean;
  ratio: string;
  promptText: string;
  inputObjectName: string;
  referenceObjectNames: string[];
  outputObjectName: string;
  estimatedCostMinor: number;
  estimatedCredits: number;
  reviewAutostartConfirmed: boolean;
  reviewAutostartTermsVersion: string | null;
};

type StatusJob = {
  id: string;
  batchId: string;
  campaignId: string;
  campaignName: string;
  status: string;
  provider: "runway";
  providerTaskId: string | null;
  model: "gen4_turbo" | "seedance2_fast" | "seedream5_lite";
  durationSeconds: number;
  audio: boolean;
  ratio: string;
  estimatedCostMinor: number;
  estimatedCredits: number;
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
  provider: "runway";
  provider_task_id: string | null;
  model: "gen4_turbo" | "seedance2_fast" | "seedream5_lite";
  duration_seconds: number;
  audio: boolean;
  ratio: string;
  estimated_cost_minor: number;
  estimated_credits: number;
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

function readClaimErrorCode(value: unknown): ClaimErrorCode | null {
  const budgetCode = readBudgetErrorCode(value);
  if (budgetCode !== null) return budgetCode;
  return isRecord(value) &&
      value.message === "real_generation_reconciliation_required"
    ? "real_generation_reconciliation_required"
    : null;
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
      value === "seedream5_lite"
    ? value
    : null;
}

function readRunwayGenerationSku(
  model: RunwayModel,
  durationSeconds: unknown,
): {
  model: RunwayModel;
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
  const modelRequirements: Record<RunwayModel, string[]> = {
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
  if (payload.model === "seedance2_fast") {
    if (spokenMatch === null || spokenMatch[1].includes("[СОКРАТИТЕ")) {
      return false;
    }
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
    "duration_seconds",
    "allow_real_spend",
    "spend_confirmation",
    "learning_context",
  ]);
  const allowed = new Set([
    ...required,
    "audio",
    "assignee_id",
    "payout_minor",
    "learning_opt_out",
    "repair_context",
    "review_autostart_confirmed",
    "review_autostart_terms_version",
  ]);
  if (!hasOnlyKeys(value, allowed)) return null;
  if (![...required].every((key) => Object.hasOwn(value, key))) return null;

  const mediaIds = value.media_ids;
  const model = readRunwayModel(value.model);
  const sku = model === null
    ? null
    : readRunwayGenerationSku(model, value.duration_seconds);
  const gen4Sku = value.model === "gen4_turbo" &&
    sku?.model === "gen4_turbo" &&
    (!Object.hasOwn(value, "audio") || value.audio === false) &&
    value.spend_confirmation === sku.confirmation;
  const seedanceSku = value.model === "seedance2_fast" &&
    sku?.model === "seedance2_fast" && value.audio === true &&
    value.format === "9:16" &&
    value.spend_confirmation === sku.confirmation;
  const seedreamSku = value.model === "seedream5_lite" &&
    sku?.model === "seedream5_lite" &&
    (!Object.hasOwn(value, "audio") || value.audio === false) &&
    value.format === "1:1" &&
    value.spend_confirmation === sku.confirmation;
  const reviewAutostartKeyPresent =
    Object.hasOwn(value, "review_autostart_confirmed") ||
    Object.hasOwn(value, "review_autostart_terms_version");
  const promptLimit = model === null ? 0 : RUNWAY_PROMPT_LIMITS[model];
  if (
    !Array.isArray(mediaIds) ||
    mediaIds.length < 1 ||
    mediaIds.length > 5 ||
    mediaIds.some((mediaId) => !isUuid(mediaId)) ||
    new Set(mediaIds).size !== mediaIds.length
  ) {
    return null;
  }
  const formats = new Set(["9:16", "1:1", "16:9"]);
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
    typeof value.format !== "string" || !formats.has(value.format) ||
    !isBoundedText(value.brief, 1, promptLimit) ||
    typeof value.platform !== "string" || !platforms.has(value.platform) ||
    !isBoundedText(value.destination_ref, 2, 240) ||
    value.mode !== "real" || value.provider !== "runway" ||
    value.allow_real_spend !== true ||
    (!gen4Sku && !seedanceSku && !seedreamSku)
  ) {
    return null;
  }
  if (
    reviewAutostartKeyPresent &&
    (
      seedreamSku ||
      value.review_autostart_confirmed !== true ||
      value.review_autostart_terms_version !==
        "generated-video-qa-autostart-v1"
    )
  ) {
    return null;
  }
  if (Object.hasOwn(value, "assignee_id") && !isUuid(value.assignee_id)) {
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
  const allowed = new Set([
    "action",
    "organization_id",
    "model",
    "duration_seconds",
  ]);
  const model = readRunwayModel(value.model);
  const sku = model === null
    ? null
    : readRunwayGenerationSku(model, value.duration_seconds);
  if (
    !hasOnlyKeys(value, allowed) ||
    Object.keys(value).length !== allowed.size ||
    value.action !== "preflight" ||
    !isUuid(value.organization_id) ||
    model === null ||
    sku === null
  ) {
    return null;
  }
  return {
    action: "preflight",
    organization_id: value.organization_id,
    model,
    duration_seconds: sku.durationSeconds,
  };
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

function generationLearningPromptRequirements(
  value: unknown,
  model: RunwayModel,
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
      model !== "seedance2_fast"
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

function generationRepairPromptRequirements(
  guardCodes: unknown,
  model: RunwayModel,
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
      model !== "seedance2_fast"
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
  const allowed = new Set(["action", "organization_id", "job_id"]);
  if (!hasOnlyKeys(value, allowed) || Object.keys(value).length !== 3) {
    return null;
  }
  if (
    value.action !== "status" || !isUuid(value.organization_id) ||
    !isUuid(value.job_id)
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
    !isUuid(value.job_id) ||
    !isUuid(value.incident_id) ||
    typeof value.idempotency_key !== "string" ||
    !IDEMPOTENCY_PATTERN.test(value.idempotency_key) ||
    (!attach && !noSubmission) ||
    !isBoundedText(value.evidence_reference, 8, 500) ||
    !isBoundedText(value.reason, 20, 1_000) ||
    (attach && (
      !isValidTaskId(value.provider_task_id) ||
      value.confirmation !== "RUNWAY_TASK_ID_VERIFIED"
    )) ||
    (noSubmission && (
      Object.hasOwn(value, "provider_task_id") ||
      value.confirmation !== "RUNWAY_NO_TASK_VERIFIED"
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

function readRunwaySku(job: Record<string, unknown>): {
  model: "gen4_turbo" | "seedance2_fast" | "seedream5_lite";
  durationSeconds: number;
  audio: boolean;
  ratio: string;
  estimatedCostMinor: number;
  estimatedCredits: number;
} | null {
  const model = readRunwayModel(job.model);
  const sku = model === null
    ? null
    : readRunwayGenerationSku(model, job.duration_seconds);
  if (
    sku?.model === "gen4_turbo" &&
    job.audio === false && typeof job.ratio === "string" &&
    GEN4_RATIOS.has(job.ratio) &&
    job.estimated_cost_minor === sku.estimatedCredits &&
    job.estimated_credits === sku.estimatedCredits
  ) {
    return {
      model: "gen4_turbo",
      durationSeconds: sku.durationSeconds,
      audio: false,
      ratio: job.ratio,
      estimatedCostMinor: sku.estimatedCredits,
      estimatedCredits: sku.estimatedCredits,
    };
  }
  if (
    sku?.model === "seedance2_fast" &&
    job.audio === true && job.ratio === SEEDANCE_FAST_RATIO &&
    job.estimated_cost_minor === sku.estimatedCredits &&
    job.estimated_credits === sku.estimatedCredits
  ) {
    return {
      model: "seedance2_fast",
      durationSeconds: sku.durationSeconds,
      audio: true,
      ratio: SEEDANCE_FAST_RATIO,
      estimatedCostMinor: sku.estimatedCredits,
      estimatedCredits: sku.estimatedCredits,
    };
  }
  if (
    sku?.model === "seedream5_lite" &&
    job.audio === false && job.ratio === SEEDREAM5_LITE_RATIO &&
    job.estimated_cost_minor === 4 && job.estimated_credits === 4
  ) {
    return {
      model: "seedream5_lite",
      durationSeconds: 0,
      audio: false,
      ratio: SEEDREAM5_LITE_RATIO,
      estimatedCostMinor: 4,
      estimatedCredits: 4,
    };
  }
  return null;
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
  const sku = readRunwaySku(job);
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
    job.provider !== "runway" || sku === null ||
    !isBoundedText(job.prompt_text, 1, 1_200) ||
    !isObjectName(job.input_object_name) ||
    referenceObjectNames.length < 1 ||
    referenceObjectNames.length > 5 ||
    referenceObjectNames.some((objectName) => !isObjectName(objectName)) ||
    referenceObjectNames[0] !== job.input_object_name ||
    new Set(referenceObjectNames).size !== referenceObjectNames.length ||
    !isObjectName(job.output_object_name) ||
    !isIntegerInRange(job.estimated_cost_minor, 0, 1_000_000) ||
    !isIntegerInRange(job.estimated_credits, 0, 1_000_000) ||
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
    provider: "runway",
    model: sku.model,
    durationSeconds: sku.durationSeconds,
    audio: sku.audio,
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
  const sku = readRunwaySku(job);
  if (
    !isUuid(job.id) || !isUuid(job.batch_id) ||
    !isUuid(job.campaign_id) || !isBoundedText(job.campaign_name, 2, 160) ||
    typeof job.status !== "string" || !JOB_STATUSES.has(job.status) ||
    job.provider !== "runway" || sku === null ||
    (providerTaskId !== null && !isValidTaskId(providerTaskId)) ||
    !isIntegerInRange(job.estimated_cost_minor, 0, 1_000_000) ||
    !isIntegerInRange(job.estimated_credits, 0, 1_000_000) ||
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
    provider: "runway",
    providerTaskId,
    model: sku.model,
    durationSeconds: sku.durationSeconds,
    audio: sku.audio,
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
      duration_seconds: input.duration_seconds,
      audio: input.audio === true,
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
    job.status !== "starting" ||
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
    duration_seconds: job.durationSeconds,
    audio: job.audio,
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

function readNonNegativeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : null;
}

function parseRunwayOrganizationReadiness(
  value: unknown,
  model: RunwayModel,
  durationSeconds: number,
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
  const sku = readRunwayGenerationSku(model, durationSeconds);
  if (sku === null) return null;
  const estimatedCredits = sku.estimatedCredits;
  const modelAvailable = maxDaily !== null && maxDaily > 0;
  const balanceSufficient = creditBalance >= estimatedCredits;
  const dailyQuotaAvailable = modelAvailable &&
    dailyGenerations !== null && dailyGenerations < maxDaily;
  return {
    ready: balanceSufficient && modelAvailable && dailyQuotaAvailable,
    model,
    durationSeconds: sku.durationSeconds,
    estimatedCredits,
    balanceSufficient,
    modelAvailable,
    dailyQuotaAvailable,
  };
}

async function checkRunwayProviderReadiness(
  secret: string,
  model: RunwayModel,
  durationSeconds: number,
): Promise<RunwayProviderReadiness> {
  const sku = readRunwayGenerationSku(model, durationSeconds);
  if (sku === null) {
    return {
      ready: false,
      model,
      durationSeconds,
      estimatedCredits: 0,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: "provider_request_rejected",
    };
  }
  const estimatedCredits = sku.estimatedCredits;
  let response: Response;
  try {
    response = await fetchWithTimeout(
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
      ready: false,
      model,
      durationSeconds: sku.durationSeconds,
      estimatedCredits,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: "provider_request_failed",
    };
  }
  if (!response.ok) {
    await response.body?.cancel();
    return {
      ready: false,
      model,
      durationSeconds: sku.durationSeconds,
      estimatedCredits,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: providerFailureForHttp(response.status),
    };
  }
  let value: unknown;
  try {
    value = await readProviderJson(response);
  } catch {
    return {
      ready: false,
      model,
      durationSeconds: sku.durationSeconds,
      estimatedCredits,
      balanceSufficient: false,
      modelAvailable: false,
      dailyQuotaAvailable: false,
      failureCode: "provider_response_invalid",
    };
  }
  const parsed = parseRunwayOrganizationReadiness(
    value,
    model,
    sku.durationSeconds,
  );
  if (parsed === null) {
    return {
      ready: false,
      model,
      durationSeconds: sku.durationSeconds,
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

function parseProviderReadinessReceipt(
  value: unknown,
  organizationId: string,
  readiness: RunwayProviderReadiness,
): ProviderReadinessReceipt | null {
  if (!isRecord(value)) return null;
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
    value.version !== "generation-provider-readiness-receipt-v2" ||
    value.organization_id !== organizationId ||
    value.provider !== "runway" ||
    value.model !== readiness.model ||
    value.duration_seconds !== readiness.durationSeconds ||
    value.ready !== readiness.ready ||
    value.estimated_credits !== readiness.estimatedCredits ||
    value.balance_sufficient !== readiness.balanceSufficient ||
    value.model_available !== readiness.modelAvailable ||
    value.daily_quota_available !== readiness.dailyQuotaAvailable ||
    value.failure_code !== expectedFailure ||
    value.learning_gate_version !== GENERATION_LEARNING_GATE_VERSION ||
    value.status !== (readiness.ready ? "ready" : "blocked") ||
    value.fresh !== true ||
    !isUuid(value.receipt_id) ||
    typeof value.receipt_hash !== "string" ||
    !SHA256_PATTERN.test(value.receipt_hash) ||
    !Number.isFinite(checkedAtMs) ||
    !Number.isFinite(expiresAtMs) ||
    checkedAtMs > Date.now() + 60_000 ||
    expiresAtMs <= checkedAtMs ||
    expiresAtMs - checkedAtMs !== 15 * 60_000 ||
    expiresAtMs <= Date.now()
  ) {
    return null;
  }
  return {
    receiptId: value.receipt_id,
    receiptHash: value.receipt_hash,
    checkedAt,
    expiresAt,
  };
}

async function fetchWithTimeout(
  input: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
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
      throw new Error("response_size_invalid");
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
        throw new Error("response_size_invalid");
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
  const bytes = await readBoundedBytes(response, MAX_PROVIDER_JSON_BYTES);
  try {
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    throw new Error("provider_response_invalid");
  }
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

  const readCurrentStatus = async (
    organizationId: string,
    jobId: string,
  ): Promise<StatusJob | null> => {
    if (internalWorker) {
      try {
        const { data, error } = await supabaseAdmin
          .schema("content_factory")
          .from("generation_jobs")
          .select(
            "id, organization_id, batch_id, campaign_id, status, mode, provider, input, output, estimated_cost_minor, actual_cost_minor, updated_at",
          )
          .eq("organization_id", organizationId)
          .eq("id", jobId)
          .eq("mode", "real")
          .eq("provider", "runway")
          .maybeSingle();
        if (error || !isRecord(data) || !isUuid(data.campaign_id)) return null;
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
        { p_payload: { organization_id: organizationId, job_id: jobId } },
      );
      if (error) return null;
      const job = readStatusJob(data);
      if (job === null || job.id !== jobId) return null;
      return job;
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
        return claimCode === null
          ? { outcome: "unavailable" }
          : { outcome: "budget_rejected", code: claimCode };
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
    if (isValidTaskId(providerTaskId)) {
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
      const { data, error } = await supabaseAdmin.storage.from(
        STORAGE_BUCKET,
      ).createSignedUrl(job.outputObjectName, OUTPUT_URL_TTL_SECONDS);
      if (error || data === null) return null;
      return validateSupabaseSignedUrl(data.signedUrl);
    } catch {
      return null;
    }
  };

  const respondWithCurrent = async (
    organizationId: string,
    jobId: string,
    batch?: { id: string; status: string },
  ): Promise<Response> => {
    const current = await readCurrentStatus(organizationId, jobId);
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
    batch?: { id: string; status: string },
  ): Promise<Response> => {
    const current = await readCurrentStatus(organizationId, jobId);
    return json(request, {
      ok: false,
      code: "provider_unavailable",
      ...(batch ? { batch } : {}),
      ...(current ? { job: safeJob(current) } : {}),
    }, 503);
  };

  const handleStatus = async (
    payload: StatusPayload,
    currentOverride?: StatusJob,
    batch?: { id: string; status: string },
  ): Promise<Response> => {
    let current = currentOverride ?? await readCurrentStatus(
      payload.organization_id,
      payload.job_id,
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
        current = await readCurrentStatus(
          payload.organization_id,
          payload.job_id,
        ) ??
          current;
      }
      return json(request, {
        ok: true,
        ...(batch ? { batch } : {}),
        job: safeJob(current),
      });
    }
    if (!isValidTaskId(current.providerTaskId)) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
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
    const secret = runwaySecret();
    if (secret === null) {
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }

    let providerResponse: Response;
    try {
      providerResponse = await fetchWithTimeout(
        `${RUNWAY_API_ORIGIN}/v1/tasks/${current.providerTaskId}`,
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
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }
    if (!providerResponse.ok) {
      await providerResponse.body?.cancel();
      return json(request, {
        ok: false,
        code: "provider_unavailable",
        job: safeJob(current),
      }, 503);
    }

    let providerValue: unknown;
    try {
      providerValue = await readProviderJson(providerResponse);
    } catch {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    const providerTask = parseRunwayTask(providerValue);
    if (
      providerTask === null || providerTask.id !== current.providerTaskId
    ) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
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
      const processing = await updateSystemJob({
        job_id: current.id,
        provider_task_id: current.providerTaskId,
        status: "processing",
      });
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
        current.providerTaskId,
        failure.providerFailureCode,
        failure.billingOutcome,
      );
      return await respondWithCurrent(
        payload.organization_id,
        payload.job_id,
        batch,
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
      );
    }
    if (current.status === "submitted") {
      const processing = await updateSystemJob({
        job_id: current.id,
        provider_task_id: current.providerTaskId,
        status: "processing",
      });
      if (processing === null) {
        return json(request, {
          ok: false,
          code: "generation_unavailable",
          job: safeJob(current),
        }, 503);
      }
      const refreshed = await readCurrentStatus(
        payload.organization_id,
        payload.job_id,
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
    const outputUrl = validateRunwayOutputUrl(providerValue.output[0]);
    if (outputUrl === null) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }

    const photoOutput = current.model === "seedream5_lite";
    const outputMimeType = photoOutput ? "image/png" : "video/mp4";
    let outputBytes: Uint8Array<ArrayBuffer>;
    try {
      const outputResponse = await fetchWithTimeout(
        outputUrl,
        { method: "GET", redirect: "manual" },
        OUTPUT_TIMEOUT_MS,
      );
      const mimeType = (outputResponse.headers.get("content-type") ?? "")
        .split(";", 1)[0].trim().toLocaleLowerCase("en-US");
      if (
        !outputResponse.ok ||
        !(photoOutput
          ? mimeType === "image/png"
          : new Set(["video/mp4", "application/mp4"]).has(mimeType))
      ) {
        await outputResponse.body?.cancel();
        return await respondProviderUnavailable(
          payload.organization_id,
          payload.job_id,
          batch,
        );
      }
      outputBytes = await readBoundedBytes(
        outputResponse,
        MAX_OUTPUT_BYTES,
      );
    } catch {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
      );
    }
    if (
      photoOutput ? !isPng(outputBytes) : !isMp4(outputBytes)
    ) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
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
    const { error: uploadError } = await storage.upload(
      current.outputObjectName,
      outputBytes,
      uploadOptions,
    );
    if (uploadError) {
      return await respondProviderUnavailable(
        payload.organization_id,
        payload.job_id,
        batch,
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
    const completed = photoOutput
      ? await completeSeedreamPhoto(successPayload)
      : await updateSystemJob(successPayload);
    if (completed === null) {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    current = await readCurrentStatus(
      payload.organization_id,
      payload.job_id,
    );
    if (current === null || current.status !== "succeeded") {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
    const signedUrl = await signOutput(current);
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
      const secret = runwaySecret();
      if (secret === null) {
        return json(
          request,
          { ok: false, code: "provider_unavailable" },
          503,
        );
      }
      let providerResponse: Response;
      try {
        providerResponse = await fetchWithTimeout(
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
        return json(
          request,
          { ok: false, code: "provider_unavailable" },
          503,
        );
      }
      if (!providerResponse.ok) {
        await providerResponse.body?.cancel();
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
      let providerValue: unknown;
      try {
        providerValue = await readProviderJson(providerResponse);
      } catch {
        return json(
          request,
          { ok: false, code: "provider_unavailable" },
          503,
        );
      }
      const providerTask = parseRunwayTask(providerValue);
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
      if (
        providerTask === null ||
        providerTask.id !== payload.provider_task_id ||
        !allowedStatuses.has(providerTask.status) ||
        !Number.isFinite(providerCreatedAt) ||
        providerCreatedAt <
          startingAt - RECONCILIATION_TASK_EARLY_SKEW_MS ||
        providerCreatedAt > startingAt + RECONCILIATION_TASK_LATE_SKEW_MS ||
        providerCreatedAt > Date.now() + 60_000
      ) {
        return json(
          request,
          { ok: false, code: "generation_reconciliation_task_mismatch" },
          422,
        );
      }
      systemPayload.provider_task_id = providerTask.id;
      systemPayload.provider_task_created_at = providerTask.createdAt;
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
    );
  };

  const recordProviderReadiness = async (
    organizationId: string,
    readiness: RunwayProviderReadiness,
  ): Promise<ProviderReadinessReceipt | null> => {
    const checkedBy = context.userClaims?.id;
    if (typeof checkedBy !== "string" || !isUuid(checkedBy)) return null;
    try {
      const { data, error } = await supabaseAdmin.rpc(
        "system_record_generation_provider_readiness",
        {
          p_payload: {
            organization_id: organizationId,
            checked_by: checkedBy,
            provider: "runway",
            model: readiness.model,
            duration_seconds: readiness.durationSeconds,
            ready: readiness.ready,
            estimated_credits: readiness.estimatedCredits,
            balance_sufficient: readiness.balanceSufficient,
            model_available: readiness.modelAvailable,
            daily_quota_available: readiness.dailyQuotaAvailable,
            failure_code: readiness.ready ? null : readiness.failureCode,
            learning_gate_version: GENERATION_LEARNING_GATE_VERSION,
          },
        },
      );
      if (error !== null) return null;
      return parseProviderReadinessReceipt(
        data,
        organizationId,
        readiness,
      );
    } catch {
      return null;
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
    const secret = runwaySecret();
    if (secret === null) {
      const unavailable: RunwayProviderReadiness = {
        ready: false,
        model: payload.model,
        durationSeconds: payload.duration_seconds,
        estimatedCredits: readRunwayGenerationSku(
          payload.model,
          payload.duration_seconds,
        )?.estimatedCredits ?? 0,
        balanceSufficient: false,
        modelAvailable: false,
        dailyQuotaAvailable: false,
        failureCode: "provider_configuration_error",
      };
      if (
        await recordProviderReadiness(
          payload.organization_id,
          unavailable,
        ) === null
      ) {
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
    const readiness = await checkRunwayProviderReadiness(
      secret,
      payload.model,
      payload.duration_seconds,
    );
    const receipt = await recordProviderReadiness(
      payload.organization_id,
      readiness,
    );
    if (receipt === null) {
      return json(
        request,
        { ok: false, code: "generation_unavailable" },
        503,
      );
    }
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
        provider: "runway",
        model: readiness.model,
        duration_seconds: readiness.durationSeconds,
        ready: true,
        estimated_credits: readiness.estimatedCredits,
        balance_sufficient: readiness.balanceSufficient,
        model_available: readiness.modelAvailable,
        daily_quota_available: readiness.dailyQuotaAvailable,
        learning_gate_version: GENERATION_LEARNING_GATE_VERSION,
        checked_at: receipt.checkedAt,
        expires_at: receipt.expiresAt,
        receipt_id: receipt.receiptId,
        receipt_hash: receipt.receiptHash,
        receipt_version: "generation-provider-readiness-receipt-v2",
        fresh: true,
      },
    });
  };

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

  const startPayload = readStartPayload(body);
  if (startPayload === null) {
    return json(request, { ok: false, code: "invalid_payload" }, 400);
  }
  if (!generationModePromptIsBound(startPayload)) {
    return json(
      request,
      { ok: false, code: "generation_mode_prompt_binding_invalid" },
      409,
    );
  }
  let learningPolicy: Record<string, unknown> | null = null;
  try {
    const { data, error } = await context.supabase.rpc(
      "creator_generation_learning_policy",
      {
        p_payload: {
          organization_id: startPayload.organization_id,
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
  if (
    learningPolicy === null ||
    typeof learningPolicy.applied !== "boolean"
  ) {
    return json(
      request,
      { ok: false, code: "generation_learning_unavailable" },
      503,
    );
  }
  if (
    learningPolicy.product_category !== startPayload.product_category ||
    startPayload.learning_context.product_category !==
      startPayload.product_category
  ) {
    return json(
      request,
      { ok: false, code: "generation_learning_category_mismatch" },
      409,
    );
  }
  if (learningPolicy.generation_allowed === false) {
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
  const learningSource = startPayload.learning_context.source;
  if (
    learningPolicy.applied &&
    learningSource !== "performance_learning" &&
    startPayload.learning_opt_out !== true
  ) {
    return json(
      request,
      { ok: false, code: "generation_learning_policy_required" },
      409,
    );
  }
  if (!learningPolicy.applied && learningSource === "performance_learning") {
    return json(
      request,
      { ok: false, code: "generation_learning_policy_stale" },
      409,
    );
  }
  if (
    learningSource === "performance_learning" &&
    !generationLearningPromptIsBound(learningPolicy, startPayload)
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
    const learningCode = [
        "generation_learning_context_invalid",
        "generation_learning_policy_stale",
        "generation_learning_prompt_binding_invalid",
        "generation_learning_research_provenance_invalid",
        "generation_mode_prompt_binding_invalid",
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
        : repairCode ?? learningCode ?? "generation_rejected");
    const status = budgetCode !== null
      ? budgetErrorHttpStatus(budgetCode)
      : code === "generation_rejected"
      ? 403
      : code === "generation_learning_context_invalid" ||
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
    );
  }

  const secret = runwaySecret();
  if (secret === null) {
    await markFailed(startJob.id, "provider_configuration_error");
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  const providerReadiness = await checkRunwayProviderReadiness(
    secret,
    startJob.model,
    startJob.durationSeconds,
  );
  if (!providerReadiness.ready) {
    await markFailed(startJob.id, providerReadiness.failureCode);
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
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
    await markFailed(startJob.id, "provider_configuration_error");
    return await respondWithCurrent(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  const validReferenceUrls = signedReferenceUrls as string[];
  const signedInputUrl = validReferenceUrls[0];

  const photoGeneration = startJob.model === "seedream5_lite";
  const providerRequestBody = photoGeneration
    ? {
      model: startJob.model,
      promptText: startJob.promptText,
      ratio: startJob.ratio,
      outputFormat: "png",
      outputCount: 1,
      referenceImages: validReferenceUrls.map((uri, index) => ({
        uri,
        tag: index === 0
          ? RUNWAY_PRODUCT_REFERENCE_TAG
          : `${RUNWAY_PRODUCT_REFERENCE_TAG}${index + 1}`,
      })),
    }
    : startJob.model === "seedance2_fast"
    ? {
      model: startJob.model,
      duration: startJob.durationSeconds,
      ratio: startJob.ratio,
      promptText: startJob.promptText,
      promptImage: validReferenceUrls.map((uri, index) => ({
        uri,
        position: index === 0 ? "first" : "reference",
      })),
      audio: true,
    }
    : {
      model: startJob.model,
      duration: startJob.durationSeconds,
      ratio: startJob.ratio,
      promptText: startJob.promptText,
      promptImage: signedInputUrl,
    };
  const providerEndpoint = photoGeneration
    ? `${RUNWAY_API_ORIGIN}/v1/text_to_image`
    : `${RUNWAY_API_ORIGIN}/v1/image_to_video`;

  let createResponse: Response;
  try {
    createResponse = await fetchWithTimeout(
      providerEndpoint,
      {
        method: "POST",
        redirect: "manual",
        headers: {
          authorization: `Bearer ${secret}`,
          "content-type": "application/json",
          "x-runway-version": RUNWAY_API_VERSION,
        },
        body: JSON.stringify(providerRequestBody),
      },
      PROVIDER_TIMEOUT_MS,
    );
  } catch {
    await markReconciliationRequired(
      startJob.id,
      "provider_create_timeout",
    );
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  if (!createResponse.ok) {
    await createResponse.body?.cancel();
    if (DEFINITIVE_CREATE_HTTP_STATUSES.has(createResponse.status)) {
      await markFailed(
        startJob.id,
        providerFailureForHttp(createResponse.status),
      );
      return await respondWithCurrent(
        startPayload.organization_id,
        startJob.id,
        batch,
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
    );
  }

  let createdValue: unknown;
  try {
    createdValue = await readProviderJson(createResponse);
  } catch {
    await markReconciliationRequired(
      startJob.id,
      "provider_create_response_unknown",
    );
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
    );
  }
  const providerTask = parseCreatedRunwayTask(createdValue);
  if (providerTask === null) {
    await markReconciliationRequired(
      startJob.id,
      "provider_create_response_unknown",
    );
    return await respondProviderUnavailable(
      startPayload.organization_id,
      startJob.id,
      batch,
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
    );
  }
  return await respondWithCurrent(
    startPayload.organization_id,
    startJob.id,
    batch,
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
