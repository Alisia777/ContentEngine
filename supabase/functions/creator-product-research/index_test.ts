import {
  applyResearchStageRecompute,
  promptForRun,
  readExactVideoResearchEvidence,
  readResearchResult,
  readResearchStageRecomputeContext,
  type ResearchRun,
} from "./index.ts";

type SourceFixture = {
  id: string;
  title: string;
  url: string | null;
  publisher: string;
  published_at: string | null;
  accessed_at: string;
  source_type: string;
};

type FixtureOptions = {
  asOf?: string;
  competitorCoverage?: "limited" | "sufficient";
  secondCompetitorName?: string;
  secondSourceUrl?: string;
  includePhoto?: boolean;
  trendConfidence?: "low" | "medium" | "high";
  trendSourceIds?: string[];
};

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function assertNull(value: unknown, message: string): void {
  assert(value === null, message);
}

function utcDay(offsetDays = 0): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

function validFixture(options: FixtureOptions = {}) {
  const accessedAt = new Date().toISOString();
  const secondSourceUrl = options.secondSourceUrl ||
    "https://beta.example/competitor-b";
  const sources: SourceFixture[] = [
    {
      id: "web:alpha",
      title: "Alpha competitor page",
      url: "https://alpha.example/competitor-a",
      publisher: "Alpha",
      published_at: utcDay(-10),
      accessed_at: accessedAt,
      source_type: "competitor",
    },
    {
      id: "web:beta",
      title: "Beta competitor page",
      url: secondSourceUrl,
      publisher: "Beta",
      published_at: utcDay(-20),
      accessed_at: accessedAt,
      source_type: "competitor",
    },
  ];
  if (options.includePhoto) {
    sources.push({
      id: "photo:1",
      title: "User product photo",
      url: null,
      publisher: "User upload",
      published_at: null,
      accessed_at: accessedAt,
      source_type: "input_photo",
    });
  }

  const sufficient = options.competitorCoverage !== "limited";
  const competitors = [
    {
      name: "Alpha Brand",
      positioning: "Compact product for a practical daily routine",
      price_positioning: "Middle price segment",
      recurring_formats: ["Problem first then product demonstration"],
      strengths: ["Clear product demonstration"],
      weaknesses: ["Limited context of use"],
      reusable_structures: ["Show one task and one visible result"],
      source_ids: ["web:alpha"],
    },
    {
      name: options.secondCompetitorName || "Beta Brand",
      positioning: "Simple alternative focused on ease of use",
      price_positioning: "Upper middle price segment",
      recurring_formats: ["Use case followed by feature proof"],
      strengths: ["Specific use case"],
      weaknesses: ["Few independent details"],
      reusable_structures: ["Demonstrate the product in one clear action"],
      source_ids: ["web:beta"],
    },
  ];

  return {
    summary:
      "The product has a clear practical use case, while claims still require source-aware human review.",
    category_analysis: {
      category_name: "Compact household tools",
      market_category_key: "compact_household_tools",
      compliance_category: "household",
      confidence: "medium",
      maturity: "established",
      definition:
        "Products designed to simplify one recurring household task with a compact form factor.",
      buyer_jobs: ["Complete a recurring household task with less effort"],
      substitute_categories: ["Manual household tools"],
      unknowns: ["Long-term durability is not established"],
      source_ids: ["web:alpha", "web:beta"],
    },
    competitor_analysis: {
      coverage: sufficient ? "sufficient" : "limited",
      competitors: sufficient ? competitors : competitors.slice(0, 1),
      saturated_patterns: [
        {
          pattern: "Problem first then a single product demonstration",
          source_ids: ["web:alpha", "web:beta"],
        },
      ],
      content_gaps: [
        {
          gap: "Few sources explain the practical setup before first use",
          source_ids: ["web:alpha", "web:beta"],
        },
      ],
      limitations: ["The public competitor sample is intentionally small"],
    },
    trend_analysis: {
      signal_catalog_version: "structural_v1",
      as_of: options.asOf || utcDay(),
      signals: [
        {
          signal_key: "format.single_action_demo",
          signal: "Practical single-action demonstrations are growing",
          direction: "growing",
          confidence: options.trendConfidence || "medium",
          evidence:
            "Two independently published pages use a focused single-action demonstration.",
          source_ids: options.trendSourceIds || ["web:alpha", "web:beta"],
          recommended_use: "test",
        },
      ],
      limitations: ["Publication dates are extracted from public pages"],
    },
    guidance: {
      status: sufficient ? "ready_for_brief" : "needs_more_evidence",
      recommended_next_step: sufficient
        ? "Test one source-backed practical demonstration"
        : "Collect another independent competitor source",
      reason: sufficient
        ? "The category, competitors, and one bounded trend are corroborated"
        : "The competitor sample is still limited",
      questions_for_user: [],
      suggested_actions: ["Keep all factual wording tied to cited evidence"],
    },
    sources,
    facts: [
      {
        statement: "The compared products address a recurring household task",
        evidence: "Both public competitor pages describe a concrete use case",
        source_ids: ["web:alpha", "web:beta"],
        confidence: "medium",
      },
      {
        statement: "A compact form factor is part of the public positioning",
        evidence: "The product pages show and describe compact use",
        source_ids: ["web:alpha", "web:beta"],
        confidence: "medium",
      },
    ],
    audience: [
      {
        name: "Practical household buyers",
        profile: "People looking to simplify a repeated household task",
        needs: ["A clear and realistic use case"],
        triggers: ["Visible product action"],
        source_ids: ["web:alpha", "web:beta"],
      },
    ],
    pains: [
      {
        pain: "The recurring task can feel inconvenient",
        evidence: "Both sources frame convenience as a product benefit",
        source_ids: ["web:alpha", "web:beta"],
      },
    ],
    objections: [
      {
        objection: "The product may be difficult to set up",
        answer: "Show only the setup steps supported by the exact product",
        source_ids: ["web:alpha", "web:beta"],
      },
    ],
    claims: {
      safe: [
        {
          claim: "Designed for one practical household task",
          basis: "The cited pages describe that intended use",
          source_ids: ["web:alpha", "web:beta"],
        },
      ],
      forbidden: [
        {
          claim: "Guaranteed to save time for every buyer",
          reason: "No cited source establishes a universal result",
          safer_alternative: "Show the exact task without promising an outcome",
          source_ids: ["web:alpha", "web:beta"],
        },
      ],
    },
    scenarios: [1, 2, 3].map((position) => ({
      title: `Practical demonstration ${position}`,
      angle: `Show one bounded household use case ${position}`,
      target_segment: "Practical household buyers",
      platform: "instagram",
      goal: "Test comprehension of the product use case",
      recommended_generation_mode: "real_gen4",
      generation_mode_reason:
        "One silent product action is sufficient for this bounded concept",
      hook: "One clear task, shown without unsupported promises",
      spoken_script: "",
      shot_list: [
        {
          seconds: "0–5 секунд",
          visual: "The exact product performs one simple supported action",
          voiceover: "без голоса",
          on_screen_text: "без текста",
        },
      ],
      cta: "Review the exact product details before deciding",
      proof_points: ["Use only the exact product shown in the references"],
      risks: ["Do not imply a guaranteed result"],
    })),
    task_blueprint: {
      title: "Create three source-aware product concepts",
      objective:
        "Test three bounded ways to explain the exact product use case",
      deliverables: ["Three distinct concepts"],
      product_facts: ["Use only facts supported by the cited sources"],
      mandatory_shots: ["Show the exact product clearly"],
      do_not_say: ["Do not promise guaranteed outcomes"],
      publication_notes: ["Complete a human factual review before publishing"],
      review_checklist: [
        "Verify the exact product",
        "Verify every factual claim",
        "Verify the final platform disclosure",
      ],
    },
    creative_potential: {
      method: "prepublication_heuristic_not_probability",
      score: 68,
      confidence: 0.62,
      confidence_label: "medium",
      summary:
        "The concept is clear and feasible but still depends on execution",
      strengths: ["Clear product visibility"],
      risks: ["The public evidence sample is small"],
      limitations: ["No publication performance data is available"],
      assumptions: ["The supplied product reference is current"],
      recommended_scenario_position: 1,
      recommended_scenario_reason:
        "The first scenario gives the clearest bounded product demonstration",
    },
  };
}

function providerSources(fixture: ReturnType<typeof validFixture>) {
  return new Map(
    fixture.sources.flatMap((source) =>
      source.url === null ? [] : [[source.url, source.url] as const]
    ),
  );
}

function validate(
  fixture: ReturnType<typeof validFixture>,
  photoCount = 0,
  expectedAsOf?: string,
) {
  return readResearchResult(
    fixture,
    providerSources(fixture),
    photoCount,
    ["instagram"],
    expectedAsOf,
  );
}

const RUN_ID = "00000000-0000-4000-8000-000000000001";
const ROOT_RUN_ID = "00000000-0000-4000-8000-000000000002";
const BRANCH_ID = "00000000-0000-4000-8000-000000000003";
const REQUEST_ID = "00000000-0000-4000-8000-000000000004";
const ORGANIZATION_ID = "00000000-0000-4000-8000-000000000005";
const CORRECTION_SOURCE_ID = "00000000-0000-4000-8000-000000000006";
const BRANCH_REVISION_HASH = "b".repeat(64);
const RESEARCH_STAGES = [
  "sources",
  "category",
  "competitors",
  "trends",
  "guidance",
  "brief",
  "scenarios",
] as const;

function fixtureUuid(index: number): string {
  return `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`;
}

function recomputeContextFixture() {
  const heads = RESEARCH_STAGES.map((stage, index) => ({
    stage,
    head_event_id: fixtureUuid(100 + index),
    state: "current",
    artifact_id: fixtureUuid(200 + index),
    content_hash: String(index + 1).repeat(64),
    dependency_hash: String(index + 2).repeat(64),
    payload: { stage, retained_intent: `prior ${stage} structure` },
  }));
  return {
    schema_version: "research-stage-recompute-context-v1",
    request_id: REQUEST_ID,
    root_run_id: ROOT_RUN_ID,
    branch_id: BRANCH_ID,
    requested_stage: "competitors",
    correction: "Compare independent competitors in the narrower category.",
    input_snapshot_hash: "a".repeat(64),
    input_snapshot: {
      schema_version: "research-stage-recompute-input-v1",
      organization_id: ORGANIZATION_ID,
      run_id: ROOT_RUN_ID,
      branch_id: BRANCH_ID,
      branch_revision_hash: BRANCH_REVISION_HASH,
      requested_stage: "competitors",
      requested_head_event_id: heads[2].head_event_id,
      correction_source_id: CORRECTION_SOURCE_ID,
      heads,
    },
  };
}

function recomputeRunFixture(): ResearchRun {
  const recomputeContext = readResearchStageRecomputeContext(
    recomputeContextFixture(),
  );
  assert(recomputeContext !== null, "expected recompute context fixture");
  return {
    id: RUN_ID,
    status: "processing",
    productId: "00000000-0000-4000-8000-000000000007",
    productName: "Example product",
    productUrl: "https://example.com/product",
    sku: "SKU-1",
    marketplace: "example.com",
    brief: "Research the exact product and its public market context.",
    goal: "Research the exact product and its public market context.",
    platforms: ["instagram"],
    photos: [],
    recomputeContext,
    exactVideo: null,
  };
}

function exactVideoEvidenceFixture() {
  const mediaSha = "c".repeat(64);
  const sourceHash = "d".repeat(64);
  const organizationId = fixtureUuid(300);
  const mediaId = fixtureUuid(301);
  const frames = [1, 2, 3, 4, 5].map((ordinal) => ({
    ordinal,
    bucket_id: "contentengine-private",
    object_name: `${organizationId}/${fixtureUuid(302)}/review-evidence/${
      fixtureUuid(303)
    }/frame-${String(ordinal).padStart(2, "0")}.jpg`,
    mime_type: "image/jpeg",
    size_bytes: 128,
    sha256: String(ordinal).repeat(64),
    timecode_seconds: ordinal * 2.5,
  }));
  return {
    version: "exact-youtube-research-evidence-v1",
    organization_id: organizationId,
    project_id: fixtureUuid(304),
    binding_id: fixtureUuid(305),
    product_id: fixtureUuid(306),
    product_category: "household",
    source: {
      id: fixtureUuid(307),
      video_id: "ABCDEFGHIJK",
      canonical_url: "https://youtube.com/watch?v=ABCDEFGHIJK",
      source_hash: sourceHash,
    },
    attachment: {
      id: fixtureUuid(308),
      attachment_hash: "e".repeat(64),
      source_hash_snapshot: sourceHash,
      media_sha256_snapshot: mediaSha,
      rights_confirmed: true,
      media_matches_registered_source: true,
      attached_by: fixtureUuid(309),
      attached_at: "2026-08-10T12:00:00.000Z",
    },
    media: {
      id: mediaId,
      mime_type: "video/mp4",
      size_bytes: 10_000,
      sha256: mediaSha,
    },
    evidence: {
      id: fixtureUuid(303),
      status: "consumed",
      source_media_id: mediaId,
      source_media_sha256: mediaSha,
      manifest_hash: "f".repeat(64),
      frame_count: 5,
      total_size_bytes: 640,
      technical_metrics: { duration_seconds: 17.381 },
      frames,
    },
    provenance: {
      analysis_scope: "sampled_frames_only",
      sampled_evidence_only: true,
      full_stream_access: false,
      transcript_available: false,
      exact_source_identity_attested: true,
      source_match_basis:
        "operator_compared_uploaded_media_to_registered_source",
      source_match_attested_by: fixtureUuid(309),
      source_match_attested_at: "2026-08-10T12:00:00.000Z",
      client_authored_conclusions: false,
      content_review_provider_used: false,
    },
  };
}

Deno.test("exact-video claim accepts only one hash-bound five-frame bundle", () => {
  const parsed = readExactVideoResearchEvidence(exactVideoEvidenceFixture());
  assert(parsed !== null, "the canonical exact-video envelope must pass");
  assert(
    parsed.frames.length === 5 && parsed.frames[4].timecodeSeconds === 12.5,
    "all ordered sampled frames must survive parsing",
  );

  const wrongOrdinal = exactVideoEvidenceFixture();
  wrongOrdinal.evidence.frames[4].ordinal = 4;
  assertNull(
    readExactVideoResearchEvidence(wrongOrdinal),
    "duplicate or missing ordinals must fail closed",
  );

  const wrongIdentity = exactVideoEvidenceFixture();
  wrongIdentity.attachment.media_matches_registered_source = false;
  assertNull(
    readExactVideoResearchEvidence(wrongIdentity),
    "an unattested MP4 must never enter exact-source research",
  );
});

Deno.test("exact-video research requires its canonical social source and fact", () => {
  const parsed = readExactVideoResearchEvidence(exactVideoEvidenceFixture());
  assert(parsed !== null, "expected exact-video fixture");
  const fixture = validFixture();
  fixture.sources.push({
    id: "social:exact",
    title: "Exact registered social video",
    url: parsed.canonicalUrl,
    publisher: "YouTube",
    published_at: null,
    accessed_at: new Date().toISOString(),
    source_type: "social",
  });
  fixture.facts.push({
    statement: "The sampled frames use a visible product-first payoff",
    evidence: "This is limited to five sampled visual frames",
    source_ids: ["social:exact"],
    confidence: "low",
  });
  const sources = providerSources(fixture);
  assert(
    readResearchResult(
      fixture,
      sources,
      0,
      ["instagram"],
      utcDay(),
      parsed,
    ) !== null,
    "provider-cited canonical source with a sampled-frame fact must pass",
  );
  assert(
    fixture.sources[2].url === parsed.canonicalUrl,
    "the registered server canonical URL must be retained",
  );

  const missingFact = validFixture();
  missingFact.sources.push({ ...fixture.sources[2] });
  assertNull(
    readResearchResult(
      missingFact,
      providerSources(missingFact),
      0,
      ["instagram"],
      utcDay(),
      parsed,
    ),
    "an unused exact-video citation must not pretend frames influenced research",
  );

  const missingProviderCitation = providerSources(fixture);
  missingProviderCitation.delete(parsed.canonicalUrl);
  assert(
    readResearchResult(
      fixture,
      missingProviderCitation,
      0,
      ["instagram"],
      utcDay(),
      parsed,
    ) !== null,
    "server-bound exact frames must not depend on brittle YouTube web_search",
  );

  const wrongUrl = validFixture();
  wrongUrl.sources.push({
    ...fixture.sources[2],
    url: "https://youtube.com/watch?v=LMNOPQRSTUV",
  });
  wrongUrl.facts.push({ ...fixture.facts[2] });
  assertNull(
    readResearchResult(
      wrongUrl,
      providerSources(wrongUrl),
      0,
      ["instagram"],
      utcDay(),
      parsed,
    ),
    "a different YouTube video must not inherit the exact frame lineage",
  );
});

Deno.test("readResearchResult accepts a complete corroborated v2 result", () => {
  const fixture = validFixture();
  assert(validate(fixture) !== null, "expected the canonical fixture to pass");
});

Deno.test("unsupported sufficient coverage is preserved as limited evidence", () => {
  const duplicate = validFixture({ secondCompetitorName: "ALPHA—BRAND" });
  assert(
    validate(duplicate) !== null,
    "duplicate competitor names should preserve the paid result",
  );
  assert(
    duplicate.competitor_analysis.coverage === "limited" &&
      duplicate.guidance.status === "needs_more_evidence",
    "duplicate names must downgrade coverage and guidance",
  );

  const sameDomain = validFixture({
    secondSourceUrl: "https://news.alpha.example/competitor-b",
  });
  assert(
    validate(sameDomain) !== null,
    "one-domain evidence should remain available for correction",
  );
  assert(
    sameDomain.competitor_analysis.coverage === "limited" &&
      sameDomain.trend_analysis.signals[0].direction === "unclear" &&
      sameDomain.trend_analysis.signals[0].recommended_use === "monitor",
    "one publisher must not support sufficient coverage or a trend direction",
  );
});

Deno.test("YouTube video aliases resolve to the provider-cited URL", () => {
  const fixture = validFixture();
  fixture.sources[0].url =
    "https://www.youtube.com/watch?v=ABCDEFGHIJK&utm_source=creator";
  const sources = new Map([
    [
      "https://youtube.com/watch?v=ABCDEFGHIJK",
      "https://youtu.be/ABCDEFGHIJK?si=provider-receipt",
    ],
    ["https://beta.example/competitor-b", "https://beta.example/competitor-b"],
  ]);
  const result = readResearchResult(
    fixture,
    sources,
    0,
    ["instagram"],
  );
  assert(result !== null, "equivalent YouTube video URLs must verify");
  assert(
    fixture.sources[0].url ===
      "https://youtu.be/ABCDEFGHIJK?si=provider-receipt",
    "only the exact provider-disclosed URL may be persisted",
  );
});

Deno.test("two YouTube videos stay usable without claiming publisher independence", () => {
  const fixture = validFixture({
    secondSourceUrl: "https://youtube.com/watch?v=LMNOPQRSTUV",
  });
  fixture.sources[0].url = "https://youtube.com/watch?v=ABCDEFGHIJK";
  const result = validate(fixture);
  assert(result !== null, "a two-video YouTube sample must remain correctable");
  assert(
    fixture.competitor_analysis.coverage === "limited" &&
      fixture.trend_analysis.signals[0].direction === "unclear" &&
      fixture.guidance.status === "needs_more_evidence",
    "two videos without channel proof must not claim independent publishers",
  );
});

Deno.test("trend snapshot must be the current UTC day", () => {
  const fixture = validFixture({ asOf: utcDay(-1) });
  assertNull(validate(fixture), "a stale trend snapshot must fail closed");
});

Deno.test("snapshot day stays bound to the provider request across UTC midnight", () => {
  const requestedDay = utcDay(-1);
  const fixture = validFixture({ asOf: requestedDay });
  assert(
    validate(fixture, 0, requestedDay) !== null,
    "a response must be checked against its trusted request day, not completion day",
  );
});

Deno.test("a photo cannot manufacture temporal publisher independence", () => {
  const fixture = validFixture({
    competitorCoverage: "limited",
    secondSourceUrl: "https://news.alpha.example/competitor-b",
    includePhoto: true,
    trendSourceIds: ["web:alpha", "web:beta", "photo:1"],
  });
  assert(
    validate(fixture, 1) !== null,
    "weak temporal evidence should preserve a correctable result",
  );
  assert(
    fixture.trend_analysis.signals[0].direction === "unclear" &&
      fixture.trend_analysis.signals[0].confidence === "low" &&
      fixture.trend_analysis.signals[0].recommended_use === "monitor" &&
      fixture.guidance.status === "needs_more_evidence",
    "same-domain evidence plus a photo must only produce a monitored hypothesis",
  );
});

Deno.test("corroborated high temporal confidence is safely downgraded", () => {
  const fixture = validFixture({ trendConfidence: "high" });
  assert(
    validate(fixture) !== null,
    "two-domain temporal evidence should pass",
  );
  assert(
    fixture.trend_analysis.signals[0].confidence === "medium",
    "model-extracted publication dates must cap confidence at medium",
  );
});

Deno.test("every nested evidence reference must resolve", () => {
  const fixture = validFixture();
  fixture.category_analysis.source_ids = ["web:missing"];
  assertNull(validate(fixture), "an unknown nested source id must fail closed");
});

Deno.test("market and compliance category identities are independently bounded", () => {
  const invalidKey = validFixture();
  invalidKey.category_analysis.market_category_key = "Household tools";
  assertNull(validate(invalidKey), "a free-text market category key must fail");

  const invalidCompliance = validFixture();
  invalidCompliance.category_analysis.compliance_category = "pet_care";
  assertNull(
    validate(invalidCompliance),
    "a dynamic market category must not expand the compliance allowlist",
  );
});

Deno.test("trend identity is allowlisted and unique inside one snapshot", () => {
  const unknown = validFixture();
  unknown.trend_analysis.signals[0].signal_key = "brand.alpha_slogan";
  assertNull(validate(unknown), "model-authored trend keys must fail closed");

  const duplicate = validFixture();
  duplicate.trend_analysis.signals.push({
    ...duplicate.trend_analysis.signals[0],
    signal: "The same abstract structure described with different wording",
  });
  assertNull(
    validate(duplicate),
    "paraphrases must not create duplicate canonical observations",
  );
});

Deno.test("recompute context is exact, cross-bound, and prompt-labeled as direction", () => {
  const parsed = readResearchStageRecomputeContext(recomputeContextFixture());
  assert(parsed !== null, "the exact migration envelope must pass");
  const prompt = JSON.parse(
    promptForRun(recomputeRunFixture(), "2026-08-03T12:00:00.000Z"),
  );
  assert(
    prompt.stage_recompute.control_policy.correction_role ===
      "human_direction_not_factual_evidence",
    "the correction must be labeled as direction rather than evidence",
  );
  assert(
    prompt.stage_recompute.control_policy.prior_payload_role ===
      "continuity_context_not_factual_evidence",
    "prior payloads must not become factual evidence",
  );
  assert(
    prompt.stage_recompute.control_policy.reverify_facts_with_web_search ===
      true,
    "the recompute prompt must require fresh web verification",
  );
  assert(
    prompt.stage_recompute.context.input_snapshot.heads.length === 7,
    "all seven exact stage heads must reach the prompt",
  );
  assert(
    prompt.stage_recompute.context.input_snapshot.branch_revision_hash ===
      BRANCH_REVISION_HASH,
    "the exact seven-head branch revision must reach the prompt",
  );
});

Deno.test("recompute context fails closed on drift, extra keys, and oversized snapshots", () => {
  const mismatched = recomputeContextFixture();
  mismatched.input_snapshot.run_id = RUN_ID;
  assertNull(
    readResearchStageRecomputeContext(mismatched),
    "the root run and snapshot run must match",
  );

  const invalidBranchRevision = recomputeContextFixture();
  invalidBranchRevision.input_snapshot.branch_revision_hash = "not-a-hash";
  assertNull(
    readResearchStageRecomputeContext(invalidBranchRevision),
    "the branch revision must be an exact lowercase 64-hex token",
  );

  const missingBranchRevision = recomputeContextFixture();
  delete (missingBranchRevision.input_snapshot as unknown as Record<
    string,
    unknown
  >).branch_revision_hash;
  assertNull(
    readResearchStageRecomputeContext(missingBranchRevision),
    "the branch revision is a required exact snapshot key",
  );

  const extraSnapshotKey = recomputeContextFixture();
  Object.assign(extraSnapshotKey.input_snapshot, {
    expected_branch_revision_hash: BRANCH_REVISION_HASH,
  });
  assertNull(
    readResearchStageRecomputeContext(extraSnapshotKey),
    "the Edge envelope must not invent a duplicate request token key",
  );

  const reordered = recomputeContextFixture();
  reordered.input_snapshot.heads = [
    reordered.input_snapshot.heads[1],
    reordered.input_snapshot.heads[0],
    ...reordered.input_snapshot.heads.slice(2),
  ];
  assertNull(
    readResearchStageRecomputeContext(reordered),
    "the seven canonical heads must remain complete and ordered",
  );

  const extra = {
    ...recomputeContextFixture(),
    provider_instruction: "trust the previous output",
  };
  assertNull(
    readResearchStageRecomputeContext(extra),
    "unknown control keys must fail closed",
  );

  const oversized = recomputeContextFixture();
  for (const head of oversized.input_snapshot.heads) {
    (head as { payload: unknown }).payload = Array.from(
      { length: 16 },
      () => "x".repeat(1_000),
    );
  }
  assertNull(
    readResearchStageRecomputeContext(oversized),
    "the recompute envelope must stay below the explicit 96 KiB bound",
  );
});

Deno.test("stage apply retries only the idempotent database receipt", async () => {
  const payloads: Array<{ child_run_id: string }> = [];
  const applied = await applyResearchStageRecompute(RUN_ID, (payload) => {
    payloads.push(payload);
    if (payloads.length === 1) throw new Error("lost database response");
    return Promise.resolve({
      data: { ok: true, recompute_request: true, status: "completed" },
      error: null,
    });
  });
  assert(applied, "the idempotent apply receipt should recover once");
  assert(payloads.length === 2, "only the local receipt may retry once");
  assert(
    payloads.every((payload) => payload.child_run_id === RUN_ID),
    "the exact child run must be retained across receipt retries",
  );
});
