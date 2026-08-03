const [playwrightPath, executablePath, baseUrl] = process.argv.slice(2);

if (!playwrightPath || !executablePath || !baseUrl) {
  throw new Error(
    "Usage: node webkit_full_app_matrix_v45_probe.cjs <playwright> <webkit> <base-url>",
  );
}

const { webkit } = require(playwrightPath);
const fs = require("fs");
const path = require("path");

const visualOutput = String(process.env.CE_VISUAL_OUTPUT || "").trim();
const matrixDeviceScaleFactor = Math.max(
  1,
  Math.min(2, Number(process.env.CE_MATRIX_DEVICE_SCALE_FACTOR || 1) || 1),
);
const visualDiagnostics = [];
const VISUAL_ROWS = new Set([
  "home:default",
  "board:browse",
  "generation:create",
  "work:notifications",
  "research:handoff",
  "team:health",
]);

if (visualOutput) fs.mkdirSync(visualOutput, { recursive: true });

function writeVisualProgress(step, detail = {}) {
  if (!visualOutput) return;
  fs.writeFileSync(
    path.join(visualOutput, "visual-progress.json"),
    JSON.stringify({ step, detail, at: new Date().toISOString() }, null, 2),
  );
}

const SUPABASE_ORIGIN = "https://iyckwryrucqrxwlowxow.supabase.co";
const AUTH_STORAGE_KEY =
  "contentengine.creator-workspace.iyckwryrucqrxwlowxow.supabase.co.auth-session.v1";
const USER_ID = "11111111-1111-4111-8111-111111111111";
const OTHER_USER_ID = "22222222-2222-4222-8222-222222222222";
const SESSION_ID = "33333333-3333-4333-8333-333333333333";
const ORGANIZATION_ID = "44444444-4444-4444-8444-444444444444";
const TASK_ID = "55555555-5555-4555-8555-555555555555";
const PLACEMENT_ID = "66666666-6666-4666-8666-666666666666";
const PAYOUT_ID = "77777777-7777-4777-8777-777777777777";
const MEDIA_ID = "88888888-8888-4888-8888-888888888888";
const RESEARCH_ID = "99999999-9999-4999-8999-999999999999";
const DRAFT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const SOURCE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const PRACTICAL_REVIEW_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const CAMPAIGN_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

const CERTIFIED_MODULE_CODES = Object.freeze([
  "factory_basics",
  "video_quality",
  "publishing_funnel",
  "security_wb",
]);

const NAVIGATION_CONTROL_MATRIX = Object.freeze([
  Object.freeze({ kind: "dock", route: "/workspace/home", section: "home", hash: "#/workspace/home", marker: ".workspace-home .home-next-action" }),
  Object.freeze({ kind: "dock", route: "/workspace/board", section: "board", hash: "#/workspace/board", marker: '.workspace-board[data-ce-v4-finder-mode="browse"]' }),
  Object.freeze({ kind: "dock", route: "/workspace/generation", section: "generation", hash: "#/workspace/generation", marker: "[data-generation-view]" }),
  Object.freeze({ kind: "dock", route: "/workspace/review", section: "review", hash: "#/workspace/review", marker: "[data-review-view]" }),
  Object.freeze({ kind: "dock", route: "/workspace/placement", section: "placement", hash: "#/workspace/placement", marker: "[data-placement-view]" }),
  Object.freeze({ kind: "dock", route: "/workspace/stats", section: "stats", hash: "#/workspace/stats", marker: "[data-stats-view]" }),
  Object.freeze({ kind: "tools", route: "/workspace/tasks", section: "tasks", hash: "#/workspace/tasks", marker: "[data-task-view]" }),
  Object.freeze({ kind: "tools", route: "/workspace/work", section: "work", hash: "#/workspace/work", marker: "[data-work-view]" }),
  Object.freeze({ kind: "tools", route: "/workspace/media", section: "media", hash: "#/workspace/media", marker: "[data-media-view]" }),
  Object.freeze({ kind: "tools", route: "/workspace/payouts", section: "payouts", hash: "#/workspace/payouts", marker: "[data-payout-view]" }),
  Object.freeze({ kind: "tools", route: "/workspace/research", section: "research", hash: "#/workspace/research", marker: "[data-research-view]" }),
  Object.freeze({ kind: "tools", route: "/workspace/feedback", section: "feedback", hash: "#/workspace/feedback", marker: "[data-feedback-view]" }),
  Object.freeze({ kind: "tools", route: "/workspace/team", section: "team", hash: "#/workspace/team", marker: "[data-team-view]" }),
]);

const FULL_MATRIX = Object.freeze([
  {
    section: "home",
    view: null,
    hash: "#/workspace/home",
    marker: ".workspace-home .home-next-action",
    primary: [1],
  },
  {
    section: "board",
    view: "browse",
    hash: "#/workspace/board?view=browse",
    marker: '.workspace-board[data-ce-v4-finder-mode="browse"]',
    primary: [0],
  },
  {
    section: "board",
    view: "organize",
    hash: "#/workspace/board?view=organize",
    marker: '.workspace-board[data-ce-v4-finder-mode="organize"]',
    primary: [0],
  },
  {
    section: "generation",
    view: "create",
    hash: "#/workspace/generation?view=create",
    marker: '[data-generation-view="create"]',
    primary: [0],
  },
  {
    section: "generation",
    view: "history",
    hash: "#/workspace/generation?view=history",
    marker: '[data-generation-view="history"]',
    primary: [0],
  },
  {
    section: "generation",
    view: "products",
    hash: "#/workspace/generation?view=products",
    marker: '[data-generation-view="products"]',
    primary: [0],
  },
  {
    section: "review",
    view: "new",
    hash: "#/workspace/review?view=new",
    marker: '[data-review-view="new"]',
    primary: [0],
  },
  {
    section: "review",
    view: "current",
    hash: "#/workspace/review?view=current",
    marker: '[data-review-view="current"]',
    primary: [0],
  },
  {
    section: "review",
    view: "history",
    hash: "#/workspace/review?view=history",
    marker: '[data-review-view="history"]',
    primary: [0],
  },
  {
    section: "work",
    view: "next",
    hash: "#/workspace/work?view=next",
    marker: '[data-work-view="next"]',
    primary: [1],
  },
  {
    section: "work",
    view: "queue",
    hash: "#/workspace/work?view=queue",
    marker: '[data-work-view="queue"]',
    primary: [1],
  },
  {
    section: "work",
    view: "views",
    hash: "#/workspace/work?view=views",
    marker: '[data-work-view="views"]',
    primary: [1],
  },
  {
    section: "work",
    view: "notifications",
    hash: "#/workspace/work?view=notifications",
    marker:
      '[data-work-view="notifications"] [data-notification-center-inline]',
    primary: [1],
  },
  {
    section: "placement",
    view: "next",
    hash: "#/workspace/placement?view=next",
    marker: '[data-placement-view="next"]',
    primary: [1],
  },
  {
    section: "placement",
    view: "history",
    hash: "#/workspace/placement?view=history",
    marker: '[data-placement-view="history"]',
    primary: [0],
  },
  {
    section: "stats",
    view: "overview",
    hash: "#/workspace/stats?view=overview",
    marker: '[data-stats-view="overview"]',
    primary: [0],
  },
  {
    section: "stats",
    view: "new",
    hash: "#/workspace/stats?view=new",
    marker: '[data-stats-view="new"]',
    primary: [1],
  },
  {
    section: "payouts",
    view: "next",
    hash: "#/workspace/payouts?view=next",
    marker: '[data-payout-view="next"]',
    primary: [1],
  },
  {
    section: "payouts",
    view: "history",
    hash: "#/workspace/payouts?view=history",
    marker: '[data-payout-view="history"]',
    primary: [0],
  },
  {
    section: "tasks",
    view: "next",
    hash: "#/workspace/tasks?view=next",
    marker: '[data-task-view="next"]',
    primary: [1],
  },
  {
    section: "tasks",
    view: "queue",
    hash: "#/workspace/tasks?view=queue",
    marker: '[data-task-view="queue"]',
    primary: [0],
  },
  {
    section: "research",
    view: "evidence",
    hash: "#/workspace/research?view=evidence",
    marker: '[data-research-view="evidence"]',
    primary: [0],
  },
  {
    section: "research",
    view: "corrections",
    hash: "#/workspace/research?view=corrections",
    marker: '[data-research-view="corrections"]',
    primary: [1],
  },
  {
    section: "research",
    view: "brief",
    hash: "#/workspace/research?view=brief",
    marker: '[data-research-view="brief"]',
    primary: [1],
  },
  {
    section: "research",
    view: "approve",
    hash: "#/workspace/research?view=approve",
    marker: '[data-research-view="approve"]',
    primary: [1],
  },
  {
    section: "research",
    view: "handoff",
    hash: "#/workspace/research?view=handoff",
    marker:
      '[data-research-view="handoff"] .product-research-approved',
    primary: [1],
  },
  {
    section: "media",
    view: "upload",
    hash: "#/workspace/media?view=upload",
    marker: '[data-media-view="upload"]',
    primary: [0],
  },
  {
    section: "media",
    view: "recent",
    hash: "#/workspace/media?view=recent",
    marker: '[data-media-view="recent"]',
    primary: [0],
  },
  {
    section: "feedback",
    view: "new",
    hash: "#/workspace/feedback?view=new",
    marker: '[data-feedback-view="new"]',
    primary: [1],
  },
  {
    section: "feedback",
    view: "history",
    hash: "#/workspace/feedback?view=history",
    marker: '[data-feedback-view="history"]',
    primary: [0],
  },
  {
    section: "team",
    view: "members",
    hash: "#/workspace/team?view=members",
    marker: '[data-team-view="members"]',
    primary: [0],
  },
  {
    section: "team",
    view: "invite",
    hash: "#/workspace/team?view=invite",
    marker: '[data-team-view="invite"]',
    primary: [1],
  },
  {
    section: "team",
    view: "access",
    hash: "#/workspace/team?view=access",
    marker: '[data-team-view="access"]',
    primary: [0],
  },
  {
    section: "team",
    view: "reviews",
    hash: "#/workspace/team?view=reviews",
    marker:
      '[data-team-view="reviews"] [data-practical-review-mode="queue"]',
    primary: [0],
  },
  {
    section: "team",
    view: "review",
    hash:
      "#/workspace/team?view=review&review=" + PRACTICAL_REVIEW_ID,
    marker:
      '[data-team-view="review"] [data-practical-review-mode="detail"]',
    primary: [1],
  },
  {
    section: "team",
    view: "budget",
    hash: "#/workspace/team?view=budget",
    marker: '[data-team-view="budget"]',
    primary: [1],
  },
  {
    section: "team",
    view: "campaigns",
    hash: "#/workspace/team?view=campaigns",
    marker: '[data-team-view="campaigns"]',
    primary: [0],
  },
  {
    section: "team",
    view: "campaign",
    hash:
      "#/workspace/team?view=campaign&campaign=" + CAMPAIGN_ID,
    marker:
      '[data-team-view="campaign"] [data-campaign-id="' +
      CAMPAIGN_ID +
      '"]',
    primary: [1],
  },
  {
    section: "team",
    view: "new-campaign",
    hash: "#/workspace/team?view=new-campaign",
    marker:
      '[data-team-view="new-campaign"] #generation-campaign-create-form',
    primary: [1],
  },
  {
    section: "team",
    view: "health",
    hash: "#/workspace/team?view=health",
    marker: '[data-team-view="health"] .team-health-panel',
    primary: [0],
  },
]);

const ALLOWED_PASSIVE_RPCS = new Set([
  "creator_bootstrap",
  "creator_capture_event",
  "creator_content_review_catalog",
  "creator_generation_archive",
  "creator_generation_model_acceptance",
  "creator_generation_spend_overview",
  "creator_invite_delivery_attempts",
  "creator_manager_dashboard",
  "creator_my_work",
  "creator_notifications",
  "creator_operational_health",
  "creator_product_research_status",
  "creator_saved_work_views",
  "creator_workspace_browser",
  "creator_workspace_section",
  "workspace_trash_browser",
]);

function hermeticCreateClient(projectUrl, publishableKey, clientOptions) {
  const options = clientOptions || {};
  const authOptions = options.auth || {};
  const storage = authOptions.storage || globalThis.sessionStorage;
  const storageKey = String(authOptions.storageKey || "");

  async function readSession() {
    let raw = null;
    try {
      raw = await Promise.resolve(storage.getItem(storageKey));
    } catch {
      raw = null;
    }
    if (!raw) return null;
    try {
      return typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch {
      return null;
    }
  }

  async function rpc(name, args, schemaName) {
    try {
      const response = await fetch(
        String(projectUrl).replace(/\/$/u, "") +
          "/rest/v1/rpc/" +
          encodeURIComponent(name),
        {
          method: "POST",
          headers: {
            apikey: String(publishableKey || ""),
            authorization:
              "Bearer " +
              String((await readSession())?.access_token || publishableKey || ""),
            "content-profile": String(schemaName || "public"),
            "content-type": "application/json",
            "x-client-info": "contentengine-webkit-hermetic-sdk/1",
          },
          body: JSON.stringify(args || {}),
        },
      );
      const data = await response.json();
      if (!response.ok) {
        return {
          data: null,
          error: {
            message: String(data?.message || "rpc_request_failed"),
            code: String(data?.code || response.status),
            details: data?.details || null,
            hint: data?.hint || null,
          },
        };
      }
      return { data, error: null };
    } catch (error) {
      return {
        data: null,
        error: {
          message: String(error?.message || error || "rpc_request_failed"),
          code: "network_error",
        },
      };
    }
  }

  const auth = {
    async getSession() {
      return { data: { session: await readSession() }, error: null };
    },
    onAuthStateChange() {
      return {
        data: {
          subscription: {
            unsubscribe() {},
          },
        },
      };
    },
    async signOut() {
      try {
        await Promise.resolve(storage.removeItem(storageKey));
      } catch {
        // The production app treats storage cleanup as best effort.
      }
      return { error: null };
    },
    async refreshSession() {
      return { data: { session: await readSession() }, error: null };
    },
    async updateUser() {
      return {
        data: { user: (await readSession())?.user || null },
        error: null,
      };
    },
    async signInWithPassword() {
      return { data: { session: await readSession() }, error: null };
    },
    async verifyOtp() {
      return { data: { session: await readSession() }, error: null };
    },
    async exchangeCodeForSession() {
      return { data: { session: await readSession() }, error: null };
    },
    async setSession() {
      return { data: { session: await readSession() }, error: null };
    },
  };

  return {
    auth,
    schema(schemaName) {
      return {
        rpc(name, args) {
          return rpc(name, args, schemaName);
        },
      };
    },
    functions: {
      async invoke(name, requestOptions) {
        try {
          const response = await fetch(
            String(projectUrl).replace(/\/$/u, "") +
              "/functions/v1/" +
              encodeURIComponent(name),
            {
              method: "POST",
              headers: {
                apikey: String(publishableKey || ""),
                authorization:
                  "Bearer " +
                  String((await readSession())?.access_token || publishableKey || ""),
                "content-type": "application/json",
              },
              body: JSON.stringify(requestOptions?.body || {}),
            },
          );
          const data = await response.json();
          return response.ok
            ? { data, error: null }
            : { data: null, error: data };
        } catch (error) {
          return { data: null, error };
        }
      },
    },
    storage: {
      from() {
        return {
          async createSignedUrls(paths) {
            return {
              data: (Array.isArray(paths) ? paths : []).map(function signed(path) {
                return {
                  path,
                  signedUrl:
                    "https://example.test/private/" +
                    encodeURIComponent(String(path || "")),
                };
              }),
              error: null,
            };
          },
          async createSignedUrl(path) {
            return {
              data: {
                path,
                signedUrl:
                  "https://example.test/private/" +
                  encodeURIComponent(String(path || "")),
              },
              error: null,
            };
          },
          async upload(path) {
            return { data: { path }, error: null };
          },
          async remove(paths) {
            return { data: Array.isArray(paths) ? paths : [], error: null };
          },
        };
      },
    },
  };
}

function base64Url(value) {
  return Buffer.from(JSON.stringify(value), "utf8")
    .toString("base64")
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replace(/=+$/u, "");
}

function authSession() {
  const now = Math.floor(Date.now() / 1000);
  const user = {
    id: USER_ID,
    aud: "authenticated",
    role: "authenticated",
    email: "manager@example.test",
    app_metadata: {
      provider: "email",
      providers: ["email"],
      contentengine_password_change_completed: true,
    },
    user_metadata: {
      display_name: "WebKit Matrix Manager",
    },
    identities: [],
    created_at: "2026-08-03T00:00:00.000Z",
  };
  const accessToken = [
    base64Url({ alg: "HS256", typ: "JWT" }),
    base64Url({
      aud: "authenticated",
      exp: now + 3600,
      iat: now - 10,
      sub: USER_ID,
      role: "authenticated",
      email: user.email,
      session_id: SESSION_ID,
    }),
    "webkit-e2e-signature",
  ].join(".");
  return {
    access_token: accessToken,
    refresh_token: "webkit-e2e-refresh-token",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: now + 3600,
    user,
  };
}

function certifiedTrainingModules() {
  return CERTIFIED_MODULE_CODES.map(function moduleFixture(code, moduleIndex) {
    return {
      code,
      type: "course",
      title: "Certified WebKit course " + String(moduleIndex + 1),
      description: "A complete server-owned course fixture for the startup gate.",
      order: moduleIndex + 1,
      completed: true,
      content: {
        lessons: [
          {
            id: code + "-lesson-1",
            title: "Certified lesson",
            body: "Server-owned learning content.",
            audiences: ["all"],
            required_core: true,
          },
        ],
        knowledge_check: {
          title: "Certified knowledge check",
          pass_score: 6,
          questions: Array.from({ length: 6 }, function questionFixture(_, questionIndex) {
            return {
              id: code + "-question-" + String(questionIndex + 1),
              question_type: "single_choice",
              prompt: "Choose the safe verified action " + String(questionIndex + 1),
              requires_rationale: false,
              options: [
                { value: "safe", label: "Use verified evidence" },
                { value: "unsafe", label: "Skip verification" },
              ],
            };
          }),
        },
      },
    };
  });
}

function bootstrapPayload(options) {
  const scenario = String(options.scenario || "workspace");
  const waiverActive = options.waiverActive !== false;
  const role = String(options.role || "owner");
  const learningOnly = scenario === "learning";
  const missingAccess = scenario === "access-required";
  const certified = scenario === "certified";
  return {
    state: learningOnly
      ? "learning"
      : missingAccess
        ? "membership_required"
        : certified
          ? "workspace_open"
          : "learning",
    workspace_access: !learningOnly && !missingAccess,
    workspace_open: certified,
    profile: {
      id: USER_ID,
      display_name: "WebKit Matrix Manager",
      email: "manager@example.test",
    },
    membership: missingAccess
      ? {}
      : {
        organization_id: ORGANIZATION_ID,
        role,
        status: "active",
      },
    organization: missingAccess
      ? {}
      : {
        id: ORGANIZATION_ID,
        name: "WebKit Matrix Factory",
      },
    training: {
      completed_modules: certified ? [...CERTIFIED_MODULE_CODES] : [],
      modules: certified ? certifiedTrainingModules() : [],
      practical_project: certified
        ? {
          id: PRACTICAL_REVIEW_ID,
          status: "approved",
          platform: "instagram",
          evidence_url: "https://example.test/certified-practical",
          reviewed_at: "2026-08-03T00:00:00.000Z",
        }
        : null,
      exam: certified
        ? {
          passed: true,
          score: 100,
          pass_score: 10,
          question_count: 12,
          attempt_count: 1,
          available: true,
        }
        : {},
      access_waiver: {
        active: waiverActive && !learningOnly && !missingAccess && !certified,
        scope:
          waiverActive && !learningOnly && !missingAccess && !certified
            ? "workspace_generation"
            : "",
        reason: "webkit-full-app-matrix",
        granted_at: "2026-08-03T00:00:00.000Z",
      },
      practical_reviews: [
        {
          id: PRACTICAL_REVIEW_ID,
          status: "submitted",
          learner_name: "WebKit Learner",
          learner_profile_id: OTHER_USER_ID,
          media_id: MEDIA_ID,
          original_filename: "webkit-practical.mp4",
          mime_type: "video/mp4",
          submitted_at: "2026-08-03T00:00:00.000Z",
        },
      ],
    },
    storage: {
      bucket: "contentengine-private",
      path_prefix: "organizations/" + ORGANIZATION_ID + "/",
    },
    capabilities: {},
    summary: {},
  };
}

function generationSpendPayload() {
  return {
    ok: true,
    organization_id: ORGANIZATION_ID,
    currency: "USD",
    blocker_code: null,
    policy: {
      paid_generation_enabled: false,
      daily_limit_minor: 2000,
      monthly_limit_minor: 10000,
      per_request_limit_minor: 300,
      timezone: "Europe/Moscow",
      version: 7,
      reason: "WebKit matrix budget",
      updated_at: "2026-08-03T00:00:00.000Z",
    },
    usage: {
      day: {
        reserved_minor: 0,
        committed_minor: 0,
        remaining_minor: 2000,
      },
      month: {
        reserved_minor: 0,
        committed_minor: 0,
        remaining_minor: 10000,
      },
    },
    campaigns: [
      {
        id: CAMPAIGN_ID,
        name: "WebKit Matrix Campaign",
        status: "paused",
        enabled: false,
        policy: {
          paid_generation_enabled: false,
          daily_limit_minor: 1000,
          monthly_limit_minor: 5000,
          per_request_limit_minor: 200,
          version: 3,
        },
        usage: {
          day: { remaining_minor: 1000 },
          month: { remaining_minor: 5000 },
        },
      },
    ],
  };
}

function researchPayload() {
  return {
    run: {
      id: RESEARCH_ID,
      status: "approved",
      product_name: "WebKit Matrix Product",
      sku: "WK-MATRIX-01",
      updated_at: "2026-08-03T00:00:00.000Z",
    },
    approval: {
      status: "approved",
      draft_id: DRAFT_ID,
      approved_at: "2026-08-03T00:00:00.000Z",
    },
    latest_draft: {
      id: DRAFT_ID,
      status: "approved",
      title: "WebKit Matrix Brief",
      brief: {
        title: "WebKit Matrix Brief",
        target_audience: "QA audience",
        key_message: "Verified product message",
        proof_points: ["Verified packaging"],
        avoid_claims: ["No unsupported claims"],
        visual_direction: "Neutral tabletop",
        cta: "Open product card",
        scenarios: [
          {
            title: "Photo",
            platform: "wildberries",
            generation_mode: "real_photo",
            hook: "Exact packshot",
            script: "",
            shot_list: "Front\nSide\nLabel",
            task_title: "Create product photo",
          },
          {
            title: "Silent video",
            platform: "instagram",
            generation_mode: "real_gen4",
            hook: "Show the product",
            script: "",
            shot_list: "Rotate product",
            task_title: "Create silent video",
          },
          {
            title: "UGC",
            platform: "youtube",
            generation_mode: "real_seedance",
            hook: "Short review",
            script: "This is the exact product from the task.",
            shot_list: "Show package\nShow label",
            task_title: "Create UGC video",
          },
        ],
      },
    },
    analysis: {
      prediction: {
        score: 78,
        confidence: "high",
        summary: "Evidence is sufficient for the matrix fixture.",
        recommended_scenario_position: 2,
        recommended_scenario_reason: "Best fit for the verified inputs.",
      },
    },
    sources: [
      {
        id: SOURCE_ID,
        title: "Official product card",
        url: "https://example.com/product",
        kind: "official",
        claim: "The product identity is verified.",
        verified: true,
      },
    ],
    source_ids: [SOURCE_ID],
  };
}

function workspaceSectionPayload(section) {
  const media = {
    id: MEDIA_ID,
    media_id: MEDIA_ID,
    filename: "webkit-product.png",
    name: "WebKit product photo",
    title: "WebKit product photo",
    mime_type: "image/png",
    kind: "product_photo",
    sku: "WK-MATRIX-01",
  };
  const task = {
    id: TASK_ID,
    task_id: TASK_ID,
    status: "todo",
    title: "Verify the WebKit matrix task",
    instructions: "Perform one deterministic action.",
    task_type: "content",
  };
  const placement = {
    id: PLACEMENT_ID,
    placement_id: PLACEMENT_ID,
    status: "ready",
    title: "Publish the WebKit matrix item",
    platform: "instagram",
    tracking_url: "https://example.com/track/webkit",
  };
  const payout = {
    id: PAYOUT_ID,
    payout_id: PAYOUT_ID,
    profile_id: OTHER_USER_ID,
    status: "pending",
    amount_minor: 15000,
    amount_rub: 150,
    participant_name: "Other WebKit User",
    created_at: "2026-08-03T00:00:00.000Z",
  };
  const values = {
    media: { media: [media], items: [media] },
    generation: { batches: [], aliases: [], products: [] },
    tasks: { tasks: [task], items: [task] },
    placement: { placements: [placement], items: [placement] },
    stats: {
      publications: [],
      publication_options: [
        {
          id: PLACEMENT_ID,
          placement_id: PLACEMENT_ID,
          title: "WebKit matrix publication",
          platform: "instagram",
          final_url: "https://example.com/post/webkit",
        },
      ],
      summary: {},
    },
    payouts: { payouts: [payout], items: [payout], summary: {} },
    feedback: { feedback: [], items: [] },
    team: {
      members: [
        {
          profile_id: USER_ID,
          id: USER_ID,
          display_name: "WebKit Matrix Manager",
          email: "manager@example.test",
          role: "owner",
          status: "active",
        },
        {
          profile_id: OTHER_USER_ID,
          id: OTHER_USER_ID,
          display_name: "Other WebKit User",
          email: "other@example.test",
          role: "operator",
          status: "active",
        },
      ],
    },
  };
  return values[section] || {};
}

function rpcPayload(name, body, options) {
  const payload =
    body && body.p_payload && typeof body.p_payload === "object"
      ? body.p_payload
      : {};
  if (name === "creator_bootstrap") return bootstrapPayload(options);
  if (name === "creator_workspace_section") {
    return workspaceSectionPayload(String(payload.section || ""));
  }
  if (name === "creator_workspace_browser") {
    return {
      folders: [],
      items: [],
      entity_types: [],
      _meta: { has_more: false, next_cursor: null },
    };
  }
  if (name === "creator_content_review_catalog") {
    return { runs: [], media: [], summary: {} };
  }
  if (name === "creator_generation_archive") {
    return { batches: [], _meta: { has_more: false, next_cursor: null } };
  }
  if (name === "creator_my_work") {
    return {
      counts: {
        total: 1,
        task: 1,
        action_required: 1,
        blockers: 0,
      },
      items: [
        {
          item_type: "task",
          id: TASK_ID,
          status: "todo",
          title: "Verify the WebKit matrix task",
          deep_link: "#/workspace/tasks?view=next&item=" + TASK_ID,
          action_required: true,
        },
      ],
      _meta: { has_more: false, next_cursor: null },
    };
  }
  if (name === "creator_notifications") {
    return {
      counts: { total: 1, unread: 1 },
      items: [
        {
          id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
          kind: "generation_ready",
          severity: "success",
          title: "WebKit matrix notification",
          body: "The deterministic item is ready.",
          deep_link: "#/workspace/generation?view=history",
          read_at: null,
          created_at: "2026-08-03T00:00:00.000Z",
        },
      ],
      next_cursor: null,
    };
  }
  if (name === "creator_saved_work_views") return { items: [], views: [] };
  if (name === "creator_invite_delivery_attempts") return { results: [] };
  if (name === "creator_generation_spend_overview") {
    return generationSpendPayload();
  }
  if (name === "creator_generation_model_acceptance") {
    return { items: [], models: [], accepted: [] };
  }
  if (name === "creator_manager_dashboard") {
    return { summary: {}, members: [], tasks: [], alerts: [] };
  }
  if (name === "creator_operational_health") {
    return { summary: {}, checks: [], incidents: [] };
  }
  if (name === "creator_product_research_status") {
    return researchPayload();
  }
  if (name === "creator_capture_event") return { accepted: true };
  return {};
}

async function installSessionAndApi(context, options, ledger) {
  const session = authSession();
  await context.addInitScript(
    function seed(payload) {
      globalThis.__CE_FULL_APP_RUNTIME_ERRORS = [];
      globalThis.__CE_FULL_APP_ROUTE_EVENTS = {
        replaced: [],
        ready: [],
      };
      globalThis.addEventListener(
        "contentengine:route-replaced",
        function onRouteReplaced(event) {
          globalThis.__CE_FULL_APP_ROUTE_EVENTS.replaced.push(
            String(event.detail && event.detail.route ? event.detail.route : ""),
          );
        },
      );
      globalThis.addEventListener(
        "contentengine:v4-route-ready",
        function onRouteReady(event) {
          globalThis.__CE_FULL_APP_ROUTE_EVENTS.ready.push(
            String(event.detail && event.detail.route ? event.detail.route : ""),
          );
        },
      );
      globalThis.addEventListener("error", function onError(event) {
        globalThis.__CE_FULL_APP_RUNTIME_ERRORS.push({
          type: "error",
          message: String(event.message || event.error || "window-error"),
        });
      });
      globalThis.addEventListener(
        "unhandledrejection",
        function onUnhandled(event) {
          globalThis.__CE_FULL_APP_RUNTIME_ERRORS.push({
            type: "unhandledrejection",
            message: String(
              event.reason && (event.reason.stack || event.reason.message)
                ? event.reason.stack || event.reason.message
                : event.reason || "unhandled-rejection",
            ),
          });
        },
      );
      globalThis.addEventListener(
        "securitypolicyviolation",
        function onPolicy(event) {
          globalThis.__CE_FULL_APP_RUNTIME_ERRORS.push({
            type: "securitypolicyviolation",
            message:
              String(event.violatedDirective || "") +
              " " +
              String(event.blockedURI || ""),
          });
        },
      );
      try {
        sessionStorage.setItem(payload.authStorageKey, JSON.stringify(payload.session));
        sessionStorage.setItem("contentengine.session-id.v1", payload.sessionId);
        sessionStorage.setItem(payload.researchStorageKey, payload.researchId);
        localStorage.setItem("contentengine.portal-theme.v1", "obsidian");
        localStorage.setItem("contentengine.navigation-mode.v1", "all");
      } catch (error) {
        globalThis.__CE_FULL_APP_RUNTIME_ERRORS.push({
          type: "storage",
          message: String(error && error.message ? error.message : error),
        });
      }
    },
    {
      authStorageKey: AUTH_STORAGE_KEY,
      session,
      sessionId: SESSION_ID,
      researchStorageKey:
        "contentengine.product-research-run.v1:" +
        ORGANIZATION_ID +
        ":" +
        USER_ID,
      researchId: RESEARCH_ID,
    },
  );

  // The production CSP upgrades relative subresources to HTTPS. The local QA
  // server is intentionally plain HTTP, so adapt only the served test document
  // and keep every other production CSP directive intact.
  await context.route("**/web/app/index.html*", async function localHttpCsp(route) {
    const response = await route.fetch();
    const source = await response.text();
    const body = source.replace(/;\s*upgrade-insecure-requests/g, "");
    if (body === source) {
      ledger.unexpected.push({
        method: route.request().method(),
        path: new URL(route.request().url()).pathname,
        reason: "local-csp-adaptation-missing",
      });
    } else {
      ledger.localCspAdaptations += 1;
    }
    const headers = response.headers();
    delete headers["content-length"];
    await route.fulfill({
      response,
      headers: {
        ...headers,
        "content-type": "text/html; charset=utf-8",
      },
      body,
    });
  });

  await context.route(
    "**/npm/@supabase/supabase-js@2.57.4/+esm*",
    async function sdk(route) {
      ledger.sdkRequests += 1;
      await route.fulfill({
        status: 200,
        headers: {
          "access-control-allow-origin": "*",
          "cache-control": "no-store",
          "content-type": "application/javascript; charset=utf-8",
        },
        body:
          "export const createClient = " +
          hermeticCreateClient.toString() +
          ";",
      });
    },
  );

  await context.route(SUPABASE_ORIGIN + "/**", async function handle(route) {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method().toUpperCase();
    const origin = request.headers().origin || "*";
    const cors = {
      "access-control-allow-origin": origin,
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers":
        request.headers()["access-control-request-headers"] ||
        "authorization, apikey, content-profile, x-client-info, content-type, prefer",
      "access-control-expose-headers": "content-range, x-supabase-api-version",
      "content-type": "application/json; charset=utf-8",
    };

    if (method === "OPTIONS") {
      ledger.preflights += 1;
      await route.fulfill({ status: 204, headers: cors, body: "" });
      return;
    }

    if (url.pathname.startsWith("/auth/v1/")) {
      ledger.authRequests.push({ method, path: url.pathname + url.search });
      const authBody =
        url.pathname === "/auth/v1/user"
          ? session.user
          : session;
      await route.fulfill({
        status: 200,
        headers: cors,
        body: JSON.stringify(authBody),
      });
      return;
    }

    const rpcMatch = url.pathname.match(/^\/rest\/v1\/rpc\/([^/]+)$/u);
    if (method === "POST" && rpcMatch) {
      const name = decodeURIComponent(rpcMatch[1]);
      let body = {};
      try {
        body = request.postDataJSON() || {};
      } catch (error) {
        ledger.unexpected.push({
          method,
          path: url.pathname,
          reason: "invalid-json",
          detail: String(error && error.message ? error.message : error),
        });
      }
      ledger.rpcs.push({ name, body });
      if (!ALLOWED_PASSIVE_RPCS.has(name)) {
        ledger.unexpected.push({
          method,
          path: url.pathname,
          reason: "unexpected-passive-rpc",
          name,
        });
        await route.fulfill({
          status: 501,
          headers: cors,
          body: JSON.stringify({ message: "unexpected_passive_rpc" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        headers: cors,
        body: JSON.stringify(rpcPayload(name, body, options)),
      });
      return;
    }

    ledger.unexpected.push({
      method,
      path: url.pathname + url.search,
      reason: "unexpected-supabase-request",
    });
    await route.fulfill({
      status: 501,
      headers: cors,
      body: JSON.stringify({ message: "unexpected_supabase_request" }),
    });
  });
}

function attachDiagnostics(page, diagnostics) {
  page.on("pageerror", function onPageError(error) {
    diagnostics.pageErrors.push(String(error && error.stack ? error.stack : error));
  });
  page.on("console", function onConsole(message) {
    const entry = {
      type: message.type(),
      text: message.text(),
      location: message.location(),
    };
    if (
      entry.type === "error" &&
      entry.text ===
        "The Content Security Policy directive 'frame-ancestors' is ignored when delivered via an HTML meta element."
    ) {
      diagnostics.consoleAdvisories.push(entry);
    } else if (entry.type === "error") {
      diagnostics.consoleErrors.push(entry);
    }
    if (entry.type === "warning") diagnostics.consoleWarnings.push(entry);
  });
  page.on("requestfailed", function onRequestFailed(request) {
    diagnostics.requestFailures.push({
      method: request.method(),
      url: request.url(),
      error: request.failure() ? request.failure().errorText : "",
    });
  });
  page.on("response", function onResponse(response) {
    if (response.status() >= 400) {
      diagnostics.httpErrors.push({
        status: response.status(),
        url: response.url(),
      });
    }
  });
}

async function waitForStableWorkspace(page, row, timeout = 30000) {
  try {
    await page.waitForFunction(
      function ready(expected) {
        const shell = document.querySelector(
          '.workspace-shell[data-workspace-section="' +
            expected.section +
            '"]',
        );
        const content = document.querySelector("#workspace-content");
        return (
          location.hash === expected.hash &&
          shell &&
          content &&
          content.dataset.ceV4InitialLoading === "false" &&
          document.querySelector(expected.marker) &&
          document.body.classList.contains("contentengine-desktop-v4") &&
          document.body.dataset.ceV4Stable === "true" &&
          document.documentElement.dataset.ceV4Ready === "true" &&
          document.documentElement.dataset.ceV4Loading !== "true" &&
          document.documentElement.dataset.ceV4Failed !== "true" &&
          document.querySelectorAll(".ce-v4-menubar").length === 1 &&
          document.querySelectorAll(".ce-v4-dock").length === 1 &&
          !document.querySelector("#main-content.route-enter")
        );
      },
      row,
      { timeout, polling: "raf" },
    );
  } catch (error) {
    const state = await page.evaluate(
      function debug(expected) {
        const shell = document.querySelector(".workspace-shell");
        const content = document.querySelector("#workspace-content");
        return {
          expected,
          hash: location.hash,
          title: document.title,
          shellSection: shell ? shell.dataset.workspaceSection || "" : "",
          shellCount: document.querySelectorAll(".workspace-shell").length,
          contentCount: document.querySelectorAll("#workspace-content").length,
          initialLoading: content
            ? content.dataset.ceV4InitialLoading || ""
            : "",
          marker: Boolean(document.querySelector(expected.marker)),
          bodyClass: document.body.className,
          stable: document.body.dataset.ceV4Stable || "",
          ready: document.documentElement.dataset.ceV4Ready || "",
          loading: document.documentElement.dataset.ceV4Loading || "",
          failed: document.documentElement.dataset.ceV4Failed || "",
          menubars: document.querySelectorAll(".ce-v4-menubar").length,
          docks: document.querySelectorAll(".ce-v4-dock").length,
          routeEnter: Boolean(
            document.querySelector("#main-content.route-enter"),
          ),
          boot: Boolean(document.querySelector(".boot-screen")),
          setup: Boolean(document.querySelector(".setup-screen")),
          fatal: Boolean(document.querySelector(".error-page")),
          login: Boolean(document.querySelector("#login-form")),
          runtimeErrors:
            globalThis.__CE_FULL_APP_RUNTIME_ERRORS
              ? globalThis.__CE_FULL_APP_RUNTIME_ERRORS.slice()
              : [],
          appText: String(
            document.querySelector("#app") &&
              document.querySelector("#app").textContent ||
              "",
          )
            .replace(/\s+/gu, " ")
            .trim()
            .slice(0, 500),
        };
      },
      row,
    );
    throw new Error(
      String(error && error.message ? error.message : error) +
      "\nWorkspace wait state: " +
      JSON.stringify(state),
    );
  }

  await page.evaluate(function resetContentStability() {
    globalThis.__CE_FULL_APP_CONTENT_STABILITY = {
      signature: "",
      frames: 0,
    };
  });
  await page.waitForFunction(
    function contentStable() {
      const content = document.querySelector("#workspace-content");
      if (!content) return false;
      const state = globalThis.__CE_FULL_APP_CONTENT_STABILITY;
      const signature =
        String(content.dataset.ceV4RenderSignature || "") +
        ":" +
        String(content.childElementCount) +
        ":" +
        String(content.textContent ? content.textContent.length : 0);
      if (state.signature !== signature) {
        state.signature = signature;
        state.frames = 0;
        return false;
      }
      state.frames += 1;
      return state.frames >= 4;
    },
    null,
    { timeout, polling: "raf" },
  );
}

async function workspaceSnapshot(page, row, captureIdentity) {
  return page.evaluate(
    function inspect(payload) {
      const isVisible = function visible(element) {
        if (!(element instanceof Element) || element.hidden) return false;
        let current = element;
        while (current instanceof Element) {
          const style = getComputedStyle(current);
          if (
            current.hidden ||
            style.display === "none" ||
            style.visibility === "hidden" ||
            Number(style.opacity) === 0
          ) {
            return false;
          }
          current = current.parentElement;
        }
        return element.getClientRects().length > 0;
      };
      const shell = document.querySelector(".workspace-shell");
      const menubar = document.querySelector(".ce-v4-menubar");
      const dock = document.querySelector(".ce-v4-dock");
      const menubarRect = menubar ? menubar.getBoundingClientRect() : null;
      const menubarStart = menubar && menubar.querySelector(".ce-v4-menubar__start");
      const menubarLocation = menubar && menubar.querySelector(".ce-v4-menubar__location");
      const menubarActions = menubar && menubar.querySelector(".ce-v4-menubar__actions");
      const startRect = menubarStart ? menubarStart.getBoundingClientRect() : null;
      const locationRect = menubarLocation ? menubarLocation.getBoundingClientRect() : null;
      const actionsRect = menubarActions ? menubarActions.getBoundingClientRect() : null;
      const menubarGeometryStable = Boolean(
        menubarRect &&
        startRect &&
        locationRect &&
        actionsRect &&
        Math.abs(menubarRect.left) <= 1 &&
        Math.abs(menubarRect.right - innerWidth) <= 1 &&
        startRect.width > 0 &&
        locationRect.width > 0 &&
        actionsRect.width > 0 &&
        startRect.left >= menubarRect.left - 1 &&
        actionsRect.right <= menubarRect.right + 1 &&
        Math.abs((locationRect.left + locationRect.right) / 2 - innerWidth / 2) <= 1 &&
        menubar.querySelectorAll(".ce-v4-traffic i").length === 3
      );
      if (payload.captureIdentity) {
        globalThis.__CE_FULL_APP_IDENTITIES = { shell, menubar, dock };
      }
      const identities = globalThis.__CE_FULL_APP_IDENTITIES || {};
      const primaryNodes = Array.from(
        new Set([
          ...document.querySelectorAll('[data-primary-action="true"]'),
          ...document.querySelectorAll("[data-ce-v4-home-action]"),
        ]),
      ).filter(isVisible);
      const dialogs = Array.from(
        document.querySelectorAll(
          '[role="dialog"], [aria-modal="true"], [class*="backdrop"]',
        ),
      ).filter(isVisible);
      const root = document.documentElement;
      return {
        hash: location.hash,
        section: shell ? shell.dataset.workspaceSection || "" : "",
        marker: Boolean(document.querySelector(payload.row.marker)),
        shellCount: document.querySelectorAll(".workspace-shell").length,
        contentCount: document.querySelectorAll("#workspace-content").length,
        menubarCount: document.querySelectorAll(".ce-v4-menubar").length,
        menubarAnimationFillMode: menubar ? getComputedStyle(menubar).animationFillMode : "",
        menubarGeometryStable,
        dockCount: document.querySelectorAll(".ce-v4-dock").length,
        academyCount: document.querySelectorAll(
          ".learning-gate-shell, .academy-os-window, [data-learning-route]",
        ).length,
        workspaceAcademyLinkCount: document.querySelectorAll(
          '.workspace-shell a[href^="#/learn"]',
        ).length,
        primaryCount: primaryNodes.length,
        primaryLabels: primaryNodes.map(function label(node) {
          return String(node.textContent || node.getAttribute("aria-label") || "")
            .replace(/\s+/gu, " ")
            .trim()
            .slice(0, 120);
        }),
        dialogCount: dialogs.length,
        inertCount: document.querySelectorAll("[inert]").length,
        horizontalOverflow: Math.max(
          0,
          root.scrollWidth - root.clientWidth,
        ),
        ready: root.dataset.ceV4Ready === "true",
        loading: root.dataset.ceV4Loading === "true",
        failed: root.dataset.ceV4Failed === "true",
        stable: document.body.dataset.ceV4Stable === "true",
        routeEnter: Boolean(
          document.querySelector("#main-content.route-enter"),
        ),
        shellSame: identities.shell === shell,
        menubarSame: identities.menubar === menubar,
        dockSame: identities.dock === dock,
        runtimeErrors:
          globalThis.__CE_FULL_APP_RUNTIME_ERRORS
            ? globalThis.__CE_FULL_APP_RUNTIME_ERRORS.slice()
            : [],
        routeEvents: globalThis.__CE_FULL_APP_ROUTE_EVENTS
          ? {
            replaced: globalThis.__CE_FULL_APP_ROUTE_EVENTS.replaced.slice(),
            ready: globalThis.__CE_FULL_APP_ROUTE_EVENTS.ready.slice(),
          }
          : { replaced: [], ready: [] },
      };
    },
    { row, captureIdentity },
  );
}

async function captureVisual(page, row) {
  if (!visualOutput) return;
  const key = row.section + ":" + String(row.view || "default");
  if (!VISUAL_ROWS.has(key)) return;
  const shellGeometry = async function shellGeometry(phase) {
    return page.evaluate(function inspectShell(label) {
      const read = function read(selector) {
        const node = document.querySelector(selector);
        if (!(node instanceof Element)) return null;
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        return {
          selector,
          text: String(node.textContent || "").replace(/\s+/gu, " ").trim().slice(0, 120),
          rect: {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          },
          display: style.display,
          visibility: style.visibility,
          opacity: style.opacity,
          position: style.position,
          zIndex: style.zIndex,
          animationName: style.animationName,
          animationFillMode: style.animationFillMode,
          transform: style.transform,
        };
      };
      return {
        phase: label,
        hash: location.hash,
        bodyStable: document.body.dataset.ceV4Stable || "",
        menubar: read(".ce-v4-menubar"),
        start: read(".ce-v4-menubar__start"),
        traffic: read(".ce-v4-traffic"),
        identity: read(".ce-v4-menubar__identity"),
        location: read(".ce-v4-menubar__location"),
        actions: read(".ce-v4-menubar__actions"),
        visibleLocalTopbars: Array.from(document.querySelectorAll(
          ".review-os-topbar, .generation-os-topbar, .media-finder-topbar, " +
          ".work-stage-topbar, .tasks-desk-topbar, .publishing-os-topbar, " +
          ".results-os-topbar, .payout-ledger-topbar, .academy-os-topbar, .academy-v2-topbar",
        )).filter(function visible(node) {
          const style = getComputedStyle(node);
          return style.display !== "none" && style.visibility !== "hidden" && node.getClientRects().length > 0;
        }).map(function describe(node) {
          const rect = node.getBoundingClientRect();
          return {
            className: node.className,
            rect: {
              x: Math.round(rect.x),
              y: Math.round(rect.y),
              width: Math.round(rect.width),
              height: Math.round(rect.height),
            },
            position: getComputedStyle(node).position,
            zIndex: getComputedStyle(node).zIndex,
          };
        }),
      };
    }, phase);
  };
  const record = { key, phases: [await shellGeometry("immediate")] };
  await page.screenshot({
    path: path.join(visualOutput, key.replace(":", "-") + ".png"),
    fullPage: false,
  });
  await page.waitForTimeout(420);
  record.phases.push(await shellGeometry("settled"));
  await page.screenshot({
    path: path.join(visualOutput, key.replace(":", "-") + "-settled.png"),
    fullPage: false,
  });
  visualDiagnostics.push(record);
  fs.writeFileSync(
    path.join(visualOutput, "visual-diagnostics.json"),
    JSON.stringify(visualDiagnostics, null, 2),
  );
}

function createLedger() {
  return {
    rpcs: [],
    unexpected: [],
    authRequests: [],
    preflights: 0,
    sdkRequests: 0,
    localCspAdaptations: 0,
  };
}

function createDiagnostics() {
  return {
    pageErrors: [],
    consoleErrors: [],
    consoleAdvisories: [],
    consoleWarnings: [],
    requestFailures: [],
    httpErrors: [],
  };
}

async function runOwnerMatrix(browser) {
  const options = {
    role: "owner",
    scenario: "workspace",
    waiverActive: true,
  };
  const ledger = createLedger();
  const diagnostics = createDiagnostics();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: matrixDeviceScaleFactor,
    reducedMotion: "no-preference",
  });
  await installSessionAndApi(context, options, ledger);
  const page = await context.newPage();
  attachDiagnostics(page, diagnostics);
  const rows = [];
  try {
    writeVisualProgress("owner:navigate:home");
    await page.goto(
      baseUrl + "/web/app/index.html" + FULL_MATRIX[0].hash,
      { waitUntil: "load" },
    );
    writeVisualProgress("owner:loaded:home");
    for (let index = 0; index < FULL_MATRIX.length; index += 1) {
      const row = FULL_MATRIX[index];
      const routeStartedAt = Date.now();
      if (index > 0) {
        await page.evaluate(function navigate(hash) {
          location.hash = hash;
        }, row.hash);
      }
      writeVisualProgress("owner:waiting", { index, hash: row.hash });
      await waitForStableWorkspace(page, row);
      writeVisualProgress("owner:stable", { index, hash: row.hash });
      const snapshot = await workspaceSnapshot(page, row, index === 0);
      snapshot.settleMs = Date.now() - routeStartedAt;
      rows.push(snapshot);
      await captureVisual(page, row);
    }

    const rejectRow = {
      section: "payouts",
      hash:
        "#/workspace/payouts?view=next&payout=" +
        PAYOUT_ID +
        "&decision=reject",
      marker:
        '[data-payout-view="next"] [data-danger-primary="true"]',
    };
    await page.evaluate(function navigate(hash) {
      location.hash = hash;
    }, rejectRow.hash);
    await waitForStableWorkspace(page, rejectRow);
    const reject = await workspaceSnapshot(page, rejectRow, false);
    if (visualOutput) {
      await page.screenshot({
        path: path.join(visualOutput, "payouts-reject.png"),
        fullPage: false,
      });
    }
    reject.dangerPrimary = await page.evaluate(function inspectDanger() {
      const danger = document.querySelector('[data-danger-primary="true"]');
      return danger
        ? {
          count: document.querySelectorAll('[data-danger-primary="true"]').length,
          label: String(danger.textContent || "").replace(/\s+/gu, " ").trim(),
          backgroundImage: getComputedStyle(danger).backgroundImage,
        }
        : { count: 0, label: "", backgroundImage: "" };
    });

    return {
      rows,
      reject,
      ledger,
      diagnostics,
    };
  } catch (error) {
    throw new Error(
      String(error && error.stack ? error.stack : error) +
      "\nOwner ledger: " +
      JSON.stringify(ledger) +
      "\nOwner diagnostics: " +
      JSON.stringify(diagnostics),
    );
  } finally {
    await context.close();
  }
}

async function runNavigationControlScenario(browser) {
  const options = {
    role: "owner",
    scenario: "workspace",
    waiverActive: true,
  };
  const ledger = createLedger();
  const diagnostics = createDiagnostics();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: matrixDeviceScaleFactor,
    reducedMotion: "no-preference",
  });
  await installSessionAndApi(context, options, ledger);
  const page = await context.newPage();
  attachDiagnostics(page, diagnostics);
  const rows = [];
  try {
    const home = NAVIGATION_CONTROL_MATRIX[0];
    await page.goto(baseUrl + "/web/app/index.html" + home.hash, {
      waitUntil: "load",
    });
    await waitForStableWorkspace(page, home);
    await workspaceSnapshot(page, home, true);

    for (const row of NAVIGATION_CONTROL_MATRIX) {
      const selector = row.kind === "dock"
        ? '[data-ce-v4-route="' + row.route + '"]'
        : '[data-ce-v4-tools-route="' + row.route + '"]';
      if (row.kind === "tools") {
        await page.locator("[data-ce-v4-tools-trigger]").click();
        await page.waitForFunction(function toolsOpen() {
          const trigger = document.querySelector("[data-ce-v4-tools-trigger]");
          const menu = document.querySelector("[data-ce-v4-tools-menu]");
          return trigger?.getAttribute("aria-expanded") === "true" && menu?.hidden === false;
        });
      }
      await page.locator(selector).click();
      await waitForStableWorkspace(page, row);
      const snapshot = await workspaceSnapshot(page, row, false);
      const control = await page.evaluate(
        function inspectControl(payload) {
          const selector = payload.kind === "dock"
            ? '[data-ce-v4-route="' + payload.route + '"]'
            : '[data-ce-v4-tools-route="' + payload.route + '"]';
          const node = document.querySelector(selector);
          const shell = document.querySelector(".workspace-shell");
          return {
            exists: Boolean(node),
            current: node?.getAttribute("aria-current") || "",
            href: node?.getAttribute("href") || "",
            shellRoute: shell?.dataset.workspaceRoute || "",
            shellView: shell?.dataset.workspaceView || "",
            dockRoutes: document.querySelectorAll("[data-ce-v4-route]").length,
            visibleToolRoutes: Array.from(
              document.querySelectorAll("[data-ce-v4-tools-route]"),
            ).filter(function visible(item) {
              return !item.hidden;
            }).length,
          };
        },
        row,
      );
      rows.push({ ...row, snapshot, control });
    }

    return { rows, ledger, diagnostics };
  } catch (error) {
    throw new Error(
      String(error && error.stack ? error.stack : error) +
      "\nNavigation ledger: " +
      JSON.stringify(ledger) +
      "\nNavigation diagnostics: " +
      JSON.stringify(diagnostics),
    );
  } finally {
    await context.close();
  }
}

async function runSameWorkspaceViewScenario(browser) {
  const options = {
    role: "owner",
    scenario: "workspace",
    waiverActive: true,
  };
  const ledger = createLedger();
  const diagnostics = createDiagnostics();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: matrixDeviceScaleFactor,
    reducedMotion: "no-preference",
  });
  await installSessionAndApi(context, options, ledger);
  const page = await context.newPage();
  attachDiagnostics(page, diagnostics);
  const start = {
    section: "work",
    hash: "#/workspace/work?view=next",
    marker: '[data-work-view="next"]',
  };
  const finish = {
    section: "work",
    hash: "#/workspace/work?view=notifications",
    marker: '[data-work-view="notifications"] [data-notification-center-inline]',
  };
  try {
    await page.goto(baseUrl + "/web/app/index.html" + start.hash, {
      waitUntil: "load",
    });
    await waitForStableWorkspace(page, start);
    await workspaceSnapshot(page, start, true);
    const setup = await page.evaluate(function installViewTransitionProbe() {
      const content = document.querySelector("#workspace-content");
      const main = document.querySelector("#main-content");
      const focusTarget = content?.querySelector(
        '.work-action-switch a[href="#/workspace/work?view=notifications"]',
      );
      if (!(content instanceof HTMLElement)) throw new Error("workspace_content_missing");
      if (!(main instanceof HTMLElement)) throw new Error("workspace_main_missing");
      if (!(focusTarget instanceof HTMLElement)) throw new Error("notifications_switch_missing");

      const spacer = document.createElement("div");
      spacer.dataset.ceSameViewScrollSpacer = "true";
      spacer.setAttribute("aria-hidden", "true");
      spacer.style.height = "1400px";
      spacer.style.flex = "0 0 1400px";
      main.style.height = "320px";
      main.style.maxHeight = "320px";
      main.style.overflow = "auto";
      main.append(spacer);
      focusTarget.focus({ preventScroll: true });
      main.scrollTop = Math.min(173, Math.max(0, main.scrollHeight - main.clientHeight));

      const motion = {
        revealAdds: 0,
        routeEnterAdds: 0,
        animationNames: [],
        mutationAnimationNames: [],
      };
      const observer = new MutationObserver(function mutations(entries) {
        entries.forEach(function inspect(entry) {
          if (entry.type !== "attributes" || entry.attributeName !== "class") return;
          if (
            entry.target === content &&
            content.classList.contains("ce-v4-content-reveal")
          ) {
            motion.revealAdds += 1;
            const pageWrap = content.querySelector(":scope > .page-wrap");
            motion.mutationAnimationNames.push(
              pageWrap ? getComputedStyle(pageWrap).animationName : "",
            );
          }
          if (
            entry.target === main &&
            main.classList.contains("route-enter")
          ) motion.routeEnterAdds += 1;
        });
      });
      observer.observe(content, { attributes: true, attributeFilter: ["class"] });
      observer.observe(main, { attributes: true, attributeFilter: ["class"] });
      document.addEventListener("animationstart", function animationStarted(event) {
        if (content.contains(event.target) || event.target === main) {
          motion.animationNames.push(String(event.animationName || ""));
        }
      }, true);
      globalThis.__CE_SAME_VIEW_PROBE = {
        content,
        main,
        focusTarget,
        shell: document.querySelector(".workspace-shell"),
        menubar: document.querySelector(".ce-v4-menubar"),
        dock: document.querySelector(".ce-v4-dock"),
        scrollTop: main.scrollTop,
        motion,
        observer,
      };
      return {
        focusTag: focusTarget.tagName,
        scrollTop: main.scrollTop,
        scrollHeight: main.scrollHeight,
        clientHeight: main.clientHeight,
      };
    });
    await page.evaluate(function clickNotificationsView() {
      globalThis.__CE_SAME_VIEW_PROBE.focusTarget.click();
    });
    await page.waitForFunction(function transitionObserved() {
      return location.hash === "#/workspace/work?view=notifications"
        && Boolean(document.querySelector(
          '[data-work-view="notifications"] [data-notification-center-inline]',
        ));
    }, null, { timeout: 30000, polling: "raf" });
    await waitForStableWorkspace(page, finish);
    await page.waitForTimeout(380);
    const transition = await page.evaluate(function inspectViewTransition() {
      const probe = globalThis.__CE_SAME_VIEW_PROBE;
      const content = document.querySelector("#workspace-content");
      const main = document.querySelector("#main-content");
      return {
        hash: location.hash,
        marker: Boolean(document.querySelector(
          '[data-work-view="notifications"] [data-notification-center-inline]',
        )),
        shellSame: probe.shell === document.querySelector(".workspace-shell"),
        menubarSame: probe.menubar === document.querySelector(".ce-v4-menubar"),
        dockSame: probe.dock === document.querySelector(".ce-v4-dock"),
        contentSame: probe.content === content,
        focusSame: probe.focusTarget === document.activeElement,
        focusConnected: probe.focusTarget.isConnected,
        scrollTop: main?.scrollTop || 0,
        expectedScrollTop: probe.scrollTop,
        revealClassPresent: content?.classList.contains("ce-v4-content-reveal") || false,
        routeEnterPresent: main?.classList.contains("route-enter") || false,
        revealAdds: probe.motion.revealAdds,
        routeEnterAdds: probe.motion.routeEnterAdds,
        animationNames: probe.motion.animationNames.slice(),
        mutationAnimationNames: probe.motion.mutationAnimationNames.slice(),
        shellCount: document.querySelectorAll(".workspace-shell").length,
        menubarCount: document.querySelectorAll(".ce-v4-menubar").length,
        dockCount: document.querySelectorAll(".ce-v4-dock").length,
        academyCount: document.querySelectorAll(
          ".learning-gate-shell, .academy-os-window, [data-learning-route]",
        ).length,
      };
    });
    const countsBeforeSameUrl = {
      revealAdds: transition.revealAdds,
      routeEnterAdds: transition.routeEnterAdds,
      animationCount: transition.animationNames.length,
    };
    await page.evaluate(function clickCurrentViewAgain() {
      const active = document.querySelector(
        '#workspace-content .work-action-switch a[href="#/workspace/work?view=notifications"]',
      );
      active?.click();
    });
    await page.waitForTimeout(450);
    const sameUrl = await page.evaluate(function inspectSameUrlRefresh(before) {
      const probe = globalThis.__CE_SAME_VIEW_PROBE;
      const content = document.querySelector("#workspace-content");
      const main = document.querySelector("#main-content");
      return {
        hash: location.hash,
        shellSame: probe.shell === document.querySelector(".workspace-shell"),
        menubarSame: probe.menubar === document.querySelector(".ce-v4-menubar"),
        dockSame: probe.dock === document.querySelector(".ce-v4-dock"),
        contentSame: probe.content === content,
        focusSame: probe.focusTarget === document.activeElement,
        scrollTop: main?.scrollTop || 0,
        expectedScrollTop: probe.scrollTop,
        revealClassPresent: content?.classList.contains("ce-v4-content-reveal") || false,
        routeEnterPresent: main?.classList.contains("route-enter") || false,
        revealAddsUnchanged: probe.motion.revealAdds === before.revealAdds,
        routeEnterAddsUnchanged: probe.motion.routeEnterAdds === before.routeEnterAdds,
        animationCountUnchanged: probe.motion.animationNames.length === before.animationCount,
      };
    }, countsBeforeSameUrl);
    return { setup, transition, sameUrl, ledger, diagnostics };
  } catch (error) {
    throw new Error(
      String(error && error.stack ? error.stack : error) +
      "\nSame-view ledger: " +
      JSON.stringify(ledger) +
      "\nSame-view diagnostics: " +
      JSON.stringify(diagnostics),
    );
  } finally {
    await context.close();
  }
}

async function runBootstrapRouteScenario(browser, specification) {
  const ledger = createLedger();
  const diagnostics = createDiagnostics();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    reducedMotion: "no-preference",
  });
  await installSessionAndApi(context, specification.options, ledger);
  const page = await context.newPage();
  attachDiagnostics(page, diagnostics);
  try {
    await page.goto(baseUrl + "/web/app/index.html" + specification.initialHash, {
      waitUntil: "load",
    });
    await page.waitForFunction(
      function bootstrapViewReady(expected) {
        return location.hash === expected.hash
          && Boolean(document.querySelector(expected.marker))
          && !document.querySelector(".boot-screen")
          && !document.querySelector(".setup-screen")
          && !document.querySelector(".error-page:not(.workspace-access-required)");
      },
      specification.expected,
      { timeout: 30000, polling: "raf" },
    );
    await page.waitForTimeout(80);
    const snapshot = await page.evaluate(function inspectBootstrapView() {
      const shell = document.querySelector(".workspace-shell");
      return {
        hash: location.hash,
        learningShellCount: document.querySelectorAll(".learning-gate-shell").length,
        learningRoute: document.querySelector(".learning-gate-shell")?.dataset.learningRoute || "",
        accessRequiredCount: document.querySelectorAll(".workspace-access-required").length,
        workspaceShellCount: document.querySelectorAll(".workspace-shell").length,
        workspaceSection: shell?.dataset.workspaceSection || "",
        menubarCount: document.querySelectorAll(".ce-v4-menubar").length,
        dockCount: document.querySelectorAll(".ce-v4-dock").length,
        academyCount: document.querySelectorAll(
          ".learning-gate-shell, .academy-os-window, [data-learning-route]",
        ).length,
        workspaceAcademyLinkCount: document.querySelectorAll(
          '.workspace-shell a[href^="#/learn"]',
        ).length,
        runtimeErrors: globalThis.__CE_FULL_APP_RUNTIME_ERRORS?.slice() || [],
        routeEvents: globalThis.__CE_FULL_APP_ROUTE_EVENTS
          ? {
            replaced: globalThis.__CE_FULL_APP_ROUTE_EVENTS.replaced.slice(),
            ready: globalThis.__CE_FULL_APP_ROUTE_EVENTS.ready.slice(),
          }
          : { replaced: [], ready: [] },
      };
    });
    return {
      name: specification.name,
      expected: specification.expected,
      snapshot,
      ledger,
      diagnostics,
    };
  } finally {
    await context.close();
  }
}

async function runRedirectScenario(browser, initialHash, options) {
  const ledger = createLedger();
  const diagnostics = createDiagnostics();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    reducedMotion: "no-preference",
  });
  await installSessionAndApi(context, options, ledger);
  const page = await context.newPage();
  attachDiagnostics(page, diagnostics);
  try {
    await page.goto(baseUrl + "/web/app/index.html" + initialHash, {
      waitUntil: "load",
    });
    const expected = {
      section: "home",
      hash: "#/workspace/home",
      marker: ".workspace-home .home-next-action",
    };
    await waitForStableWorkspace(page, expected);
    return {
      snapshot: await workspaceSnapshot(page, expected, true),
      ledger,
      diagnostics,
    };
  } finally {
    await context.close();
  }
}

async function runRoleScenario(browser, role, expected) {
  const options = {
    role,
    scenario: "workspace",
    waiverActive: true,
  };
  const ledger = createLedger();
  const diagnostics = createDiagnostics();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    reducedMotion: "no-preference",
  });
  await installSessionAndApi(context, options, ledger);
  const page = await context.newPage();
  attachDiagnostics(page, diagnostics);
  try {
    const home = {
      section: "home",
      hash: "#/workspace/home",
      marker: ".workspace-home .home-next-action",
    };
    await page.goto(baseUrl + "/web/app/index.html" + home.hash, {
      waitUntil: "load",
    });
    await waitForStableWorkspace(page, home);
    const availability = await page.evaluate(function inspect() {
      const shell = document.querySelector(".workspace-shell");
      return {
        sections: String(shell && shell.dataset.workspaceAvailableSections || "")
          .split(/\s+/u)
          .filter(Boolean),
        visibleTools: Array.from(
          document.querySelectorAll("[data-ce-v4-tools-route]"),
        )
          .filter(function visible(item) {
            return !item.hidden;
          })
          .map(function route(item) {
            return item.dataset.ceV4ToolsRoute;
          }),
      };
    });
    const redirects = [];
    for (const forbiddenHash of expected.forbidden) {
      await page.evaluate(function navigate(hash) {
        location.hash = hash;
      }, forbiddenHash);
      await waitForStableWorkspace(page, home);
      redirects.push({
        requested: forbiddenHash,
        finalHash: await page.evaluate(function hash() {
          return location.hash;
        }),
      });
    }
    return {
      role,
      availability,
      redirects,
      ledger,
      diagnostics,
    };
  } finally {
    await context.close();
  }
}

function diagnosticsClean(value) {
  return (
    value.pageErrors.length === 0 &&
    value.consoleErrors.length === 0 &&
    value.requestFailures.length === 0 &&
    value.httpErrors.length === 0
  );
}

function ledgerClean(value) {
  return (
    value.unexpected.length === 0 &&
    value.authRequests.length === 0 &&
    value.sdkRequests === 1 &&
    value.localCspAdaptations === 1 &&
    value.rpcs.some(function hasBootstrap(item) {
      return item.name === "creator_bootstrap";
    })
  );
}

function rowPassed(row, snapshot) {
  return (
    snapshot.hash === row.hash &&
    snapshot.section === row.section &&
    snapshot.marker &&
    snapshot.shellCount === 1 &&
    snapshot.contentCount === 1 &&
    snapshot.menubarCount === 1 &&
    snapshot.menubarAnimationFillMode === "none" &&
    snapshot.menubarGeometryStable &&
    snapshot.dockCount === 1 &&
    snapshot.academyCount === 0 &&
    row.primary.includes(snapshot.primaryCount) &&
    snapshot.primaryCount <= 1 &&
    snapshot.dialogCount === 0 &&
    snapshot.inertCount === 0 &&
    snapshot.horizontalOverflow === 0 &&
    snapshot.ready &&
    !snapshot.loading &&
    !snapshot.failed &&
    snapshot.stable &&
    !snapshot.routeEnter &&
    snapshot.shellSame &&
    snapshot.menubarSame &&
    snapshot.dockSame &&
    snapshot.runtimeErrors.length === 0
  );
}

(async function main() {
  if (FULL_MATRIX.length !== 40) {
    throw new Error("Full application matrix must contain exactly 40 views");
  }
  if (new Set(FULL_MATRIX.map(function route(row) {
    return row.section;
  })).size !== 13) {
    throw new Error("Full application matrix must contain exactly 13 routes");
  }

  const browser = await webkit.launch({
    headless: true,
    executablePath,
  });
  try {
    const owner = await runOwnerMatrix(browser);
    const navigationControls = await runNavigationControlScenario(browser);
    const sameWorkspaceView = await runSameWorkspaceViewScenario(browser);
    const redirectRoot = await runRedirectScenario(
      browser,
      "#/",
      { role: "owner", scenario: "workspace", waiverActive: true },
    );
    const redirectLearn = await runRedirectScenario(
      browser,
      "#/learn",
      { role: "owner", scenario: "workspace", waiverActive: true },
    );
    const redirectCertifiedLearn = await runRedirectScenario(
      browser,
      "#/learn",
      { role: "owner", scenario: "certified", waiverActive: false },
    );
    const bootstrapLearning = await runBootstrapRouteScenario(browser, {
      name: "learning-without-waiver",
      initialHash: "#/workspace/home",
      options: { role: "owner", scenario: "learning", waiverActive: false },
      expected: {
        hash: "#/learn",
        marker: '.learning-gate-shell[data-learning-route="/learn"]',
      },
    });
    const bootstrapMissingAccess = await runBootstrapRouteScenario(browser, {
      name: "missing-membership-and-access",
      initialHash: "#/learn",
      options: { role: "owner", scenario: "access-required", waiverActive: false },
      expected: {
        hash: "#/access-required",
        marker: ".workspace-access-required",
      },
    });
    const roles = [];
    roles.push(
      await runRoleScenario(browser, "admin", {
        sections: 13,
        tools: 7,
        forbidden: [],
      }),
    );
    roles.push(
      await runRoleScenario(browser, "producer", {
        sections: 12,
        tools: 6,
        forbidden: ["#/workspace/team"],
      }),
    );
    roles.push(
      await runRoleScenario(browser, "reviewer", {
        sections: 11,
        tools: 5,
        forbidden: ["#/workspace/research", "#/workspace/team"],
      }),
    );
    roles.push(
      await runRoleScenario(browser, "operator", {
        sections: 11,
        tools: 5,
        forbidden: ["#/workspace/research", "#/workspace/team"],
      }),
    );

    const rowChecks = Object.fromEntries(
      FULL_MATRIX.map(function check(row, index) {
        return [
          row.section + ":" + String(row.view || "default"),
          rowPassed(row, owner.rows[index]),
        ];
      }),
    );
    const roleExpectations = {
      admin: { sections: 13, tools: 7 },
      producer: { sections: 12, tools: 6 },
      reviewer: { sections: 11, tools: 5 },
      operator: { sections: 11, tools: 5 },
    };
    const roleChecks = Object.fromEntries(
      roles.map(function check(result) {
        const expected = roleExpectations[result.role];
        return [
          result.role,
          result.availability.sections.length === expected.sections &&
            result.availability.visibleTools.length === expected.tools &&
            result.redirects.every(function redirected(item) {
              return item.finalHash === "#/workspace/home";
            }) &&
            ledgerClean(result.ledger) &&
            diagnosticsClean(result.diagnostics),
        ];
      }),
    );
    const routeDurations = owner.rows.slice(1).map(function duration(row) {
      return row.settleMs;
    }).sort(function ascending(left, right) {
      return left - right;
    });
    const routeP95 = routeDurations[Math.max(0, Math.ceil(routeDurations.length * 0.95) - 1)] || 0;
    const routeMax = routeDurations.at(-1) || 0;
    const rejectCheck =
      owner.reject.hash.includes("decision=reject") &&
      owner.reject.marker &&
      owner.reject.primaryCount === 1 &&
      owner.reject.dangerPrimary.count === 1 &&
      owner.reject.dangerPrimary.label.includes("Отклонить") &&
      owner.reject.dangerPrimary.backgroundImage !== "none" &&
      owner.reject.dialogCount === 0;
    const redirectCheck = function check(result) {
      const routeEvents = result.snapshot.routeEvents;
      return (
        result.snapshot.hash === "#/workspace/home" &&
        result.snapshot.section === "home" &&
        result.snapshot.shellCount === 1 &&
        result.snapshot.menubarCount === 1 &&
        result.snapshot.dockCount === 1 &&
        result.snapshot.academyCount === 0 &&
        result.snapshot.workspaceAcademyLinkCount === 0 &&
        result.snapshot.ready &&
        result.snapshot.stable &&
        !result.snapshot.routeEnter &&
        routeEvents.replaced.length === 1 &&
        routeEvents.replaced[0] === "/workspace/home" &&
        routeEvents.ready.filter(function home(route) {
          return route === "/workspace/home";
        }).length === 1 &&
        ledgerClean(result.ledger) &&
        diagnosticsClean(result.diagnostics)
      );
    };
    const navigationControlCheck =
      navigationControls.rows.length === NAVIGATION_CONTROL_MATRIX.length &&
      navigationControls.rows.filter(function dock(row) {
        return row.kind === "dock";
      }).length === 6 &&
      navigationControls.rows.filter(function tools(row) {
        return row.kind === "tools";
      }).length === 7 &&
      navigationControls.rows.every(function controlPassed(row) {
        const snapshot = row.snapshot;
        return snapshot.hash === row.hash &&
          snapshot.section === row.section &&
          snapshot.marker &&
          snapshot.shellCount === 1 &&
          snapshot.contentCount === 1 &&
          snapshot.menubarCount === 1 &&
          snapshot.dockCount === 1 &&
          snapshot.academyCount === 0 &&
          snapshot.workspaceAcademyLinkCount === 0 &&
          snapshot.ready &&
          snapshot.stable &&
          !snapshot.routeEnter &&
          snapshot.shellSame &&
          snapshot.menubarSame &&
          snapshot.dockSame &&
          snapshot.runtimeErrors.length === 0 &&
          row.control.exists &&
          row.control.current === "page" &&
          row.control.href === row.hash &&
          row.control.shellRoute === row.route &&
          row.control.shellView === row.route &&
          row.control.dockRoutes === 6 &&
          row.control.visibleToolRoutes === 7;
      }) &&
      ledgerClean(navigationControls.ledger) &&
      diagnosticsClean(navigationControls.diagnostics);
    const sameWorkspaceViewCheck =
      sameWorkspaceView.setup.scrollTop > 0 &&
      sameWorkspaceView.transition.hash === "#/workspace/work?view=notifications" &&
      sameWorkspaceView.transition.marker &&
      sameWorkspaceView.transition.shellSame &&
      sameWorkspaceView.transition.menubarSame &&
      sameWorkspaceView.transition.dockSame &&
      sameWorkspaceView.transition.contentSame &&
      sameWorkspaceView.transition.focusSame &&
      sameWorkspaceView.transition.focusConnected &&
      Math.abs(
        sameWorkspaceView.transition.scrollTop -
        sameWorkspaceView.transition.expectedScrollTop,
      ) <= 1 &&
      sameWorkspaceView.transition.routeEnterAdds === 0 &&
      sameWorkspaceView.transition.animationNames.filter(function reveal(name) {
        return name === "ce-v4-content-reveal";
      }).length === 1 &&
      !sameWorkspaceView.transition.animationNames.includes("ce-v4-route-enter") &&
      !sameWorkspaceView.transition.revealClassPresent &&
      !sameWorkspaceView.transition.routeEnterPresent &&
      sameWorkspaceView.transition.shellCount === 1 &&
      sameWorkspaceView.transition.menubarCount === 1 &&
      sameWorkspaceView.transition.dockCount === 1 &&
      sameWorkspaceView.transition.academyCount === 0 &&
      sameWorkspaceView.sameUrl.hash === "#/workspace/work?view=notifications" &&
      sameWorkspaceView.sameUrl.shellSame &&
      sameWorkspaceView.sameUrl.menubarSame &&
      sameWorkspaceView.sameUrl.dockSame &&
      sameWorkspaceView.sameUrl.contentSame &&
      sameWorkspaceView.sameUrl.focusSame &&
      Math.abs(
        sameWorkspaceView.sameUrl.scrollTop -
        sameWorkspaceView.sameUrl.expectedScrollTop,
      ) <= 1 &&
      !sameWorkspaceView.sameUrl.revealClassPresent &&
      !sameWorkspaceView.sameUrl.routeEnterPresent &&
      sameWorkspaceView.sameUrl.revealAddsUnchanged &&
      sameWorkspaceView.sameUrl.routeEnterAddsUnchanged &&
      sameWorkspaceView.sameUrl.animationCountUnchanged &&
      ledgerClean(sameWorkspaceView.ledger) &&
      diagnosticsClean(sameWorkspaceView.diagnostics);
    const learningBootstrapCheck =
      bootstrapLearning.snapshot.hash === "#/learn" &&
      bootstrapLearning.snapshot.learningShellCount === 1 &&
      bootstrapLearning.snapshot.learningRoute === "/learn" &&
      bootstrapLearning.snapshot.accessRequiredCount === 0 &&
      bootstrapLearning.snapshot.workspaceShellCount === 0 &&
      bootstrapLearning.snapshot.menubarCount === 0 &&
      bootstrapLearning.snapshot.dockCount === 0 &&
      bootstrapLearning.snapshot.academyCount === 1 &&
      bootstrapLearning.snapshot.runtimeErrors.length === 0 &&
      bootstrapLearning.snapshot.routeEvents.replaced.includes("/learn") &&
      ledgerClean(bootstrapLearning.ledger) &&
      diagnosticsClean(bootstrapLearning.diagnostics);
    const missingAccessBootstrapCheck =
      bootstrapMissingAccess.snapshot.hash === "#/access-required" &&
      bootstrapMissingAccess.snapshot.learningShellCount === 0 &&
      bootstrapMissingAccess.snapshot.accessRequiredCount === 1 &&
      bootstrapMissingAccess.snapshot.workspaceShellCount === 0 &&
      bootstrapMissingAccess.snapshot.menubarCount === 0 &&
      bootstrapMissingAccess.snapshot.dockCount === 0 &&
      bootstrapMissingAccess.snapshot.academyCount === 0 &&
      bootstrapMissingAccess.snapshot.runtimeErrors.length === 0 &&
      bootstrapMissingAccess.snapshot.routeEvents.replaced.includes("/access-required") &&
      ledgerClean(bootstrapMissingAccess.ledger) &&
      diagnosticsClean(bootstrapMissingAccess.diagnostics);
    const checks = {
      matrixShape:
        FULL_MATRIX.length === 40 &&
        new Set(FULL_MATRIX.map(function route(row) {
          return row.section;
        })).size === 13,
      ownerRows: Object.values(rowChecks).every(Boolean),
      directHomeRouteEvents:
        owner.rows[0].routeEvents.replaced.length === 0 &&
        owner.rows[0].routeEvents.ready.filter(function home(route) {
          return route === "/workspace/home";
        }).length === 1,
      ownerLedger: ledgerClean(owner.ledger),
      ownerDiagnostics: diagnosticsClean(owner.diagnostics),
      payoutRejectDangerPrimary: rejectCheck,
      navigationControls: navigationControlCheck,
      sameWorkspaceViewContentMotion: sameWorkspaceViewCheck,
      bootstrapLearningWithoutWaiver: learningBootstrapCheck,
      redirectRoot: redirectCheck(redirectRoot),
      redirectWaivedLearn: redirectCheck(redirectLearn),
      redirectCertifiedLearn: redirectCheck(redirectCertifiedLearn),
      bootstrapMissingAccess: missingAccessBootstrapCheck,
      roles: Object.values(roleChecks).every(Boolean),
      routePerformance: routeP95 <= 2000 && routeMax <= 4000,
    };
    const passed = Object.values(checks).every(Boolean);
    const report = {
      passed,
      checks,
      rowChecks,
      roleChecks,
      performance: {
        deviceScaleFactor: matrixDeviceScaleFactor,
        routeP95,
        routeMax,
        routeDurations,
      },
      owner,
      navigationControls,
      sameWorkspaceView,
      bootstrapLearning,
      bootstrapMissingAccess,
      redirectRoot,
      redirectLearn,
      redirectCertifiedLearn,
      roles,
    };
    const output = process.env.CE_MATRIX_COMPACT === "1"
      ? {
          passed,
          checks,
          rowChecks,
          roleChecks,
          performance: report.performance,
          sameWorkspaceView,
        }
      : report;
    console.log(
      JSON.stringify(output, null, 2),
    );
    if (!passed) process.exitCode = 1;
  } finally {
    await browser.close();
  }
})().catch(function failed(error) {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
