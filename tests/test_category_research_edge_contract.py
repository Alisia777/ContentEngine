from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/creator-product-research/index.ts"


def _source() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_v2_schema_requires_the_four_exact_research_sections() -> None:
    source = _source()
    schema = source[
        source.index("const PRODUCT_RESEARCH_SCHEMA") :
        source.index("function schemaForResponsesApi")
    ]

    for section in (
        "category_analysis",
        "competitor_analysis",
        "trend_analysis",
        "guidance",
    ):
        assert f"{section}: strictObject(" in schema

    for field in (
        "category_name",
        "market_category_key",
        "compliance_category",
        "confidence",
        "maturity",
        "definition",
        "buyer_jobs",
        "substitute_categories",
        "unknowns",
        "coverage",
        "competitors",
        "saturated_patterns",
        "content_gaps",
        "as_of",
        "signal_catalog_version",
        "signals",
        "signal_key",
        "recommended_use",
        "recommended_next_step",
        "questions_for_user",
        "suggested_actions",
    ):
        assert field in schema

    assert 'enum: ["none", "limited", "sufficient"]' in schema
    assert 'enum: ["emerging", "growing", "stable", "declining", "unclear"]' in schema
    assert 'enum: ["test", "monitor", "avoid"]' in schema
    assert "const STRUCTURAL_SIGNAL_KEYS = new Set([" in source
    assert "MARKET_CATEGORY_KEY_PATTERN.test" in source
    assert "COMPLIANCE_CATEGORIES.has" in source
    assert '"ready_for_brief"' in schema
    assert '"needs_more_evidence"' in schema
    assert '"needs_user_decision"' in schema
    assert 'pattern: "^\\\\d{4}-\\\\d{2}-\\\\d{2}$"' in schema

    response_schema = source[
        source.index("function schemaForResponsesApi") :
        source.index("function canonicalSourceKey")
    ]
    assert 'const requiredV2Sections = [' in response_schema
    assert 'throw new Error("product_research_v2_schema_invalid")' in response_schema


def test_competitor_and_trend_evidence_can_be_empty_but_facts_are_cited() -> None:
    source = _source()
    validator = source[
        source.index("function readResearchResult") :
        source.index("function promptForRun")
    ]

    assert "competitorAnalysis.competitors.length > 12" in validator
    assert "trendAnalysis.signals.length > 12" in validator
    assert "STRUCTURAL_SIGNAL_KEYS.has(String(signal.signal_key))" in validator
    assert "trendSignals.map((signal)" in validator
    assert "competitorAnalysis.competitors.length < 1" not in validator
    assert "trendAnalysis.signals.length < 1" not in validator
    assert '(competitorCoverage === "none" && competitorRows.length !== 0)' in validator
    assert '(competitorCoverage !== "none" && competitorRows.length === 0)' in validator
    assert 'if (competitorCoverage === "sufficient")' in validator
    assert "distinctNames.size < 2" in validator
    assert "citedWebSourceIds.size < 2" in validator
    assert "independentPublisherDomains.size < 2" in validator
    assert 'competitorAnalysis.coverage = "limited"' in validator
    assert "competitorEvidenceDowngraded = true" in validator

    for cited_guard in (
        "validRefs(categoryAnalysis.source_ids)",
        "validRefs(competitor.source_ids)",
        "validRefs(row.source_ids)",
        "validRefs(signal.source_ids)",
    ):
        assert cited_guard in validator


def test_competitor_patterns_are_structural_and_never_raw_copy_fields() -> None:
    source = _source()
    validator = source[
        source.index("function isStructuralPatternText") :
        source.index("function promptForRun")
    ]

    assert "countWords(value) > 32" in validator
    assert "raw[\\s_-]*caption" in validator
    assert "shot[\\s_-]*sequence" in validator
    assert "isStructuralPatternArray(competitor.recurring_formats, 0, 8)" in validator
    assert "isStructuralPatternArray(competitor.reusable_structures, 0, 8)" in validator
    assert "isStructuralPatternText(row.pattern)" in validator

    instructions = source[
        source.index("const RESEARCH_INSTRUCTIONS") :
        source.index("function openAiRequestBody")
    ]
    assert "short abstract structural patterns only" in instructions
    assert "Never copy or reconstruct" in instructions
    assert "raw captions" in instructions
    assert "exact shot" in instructions
    assert "Если public_url ведёт на YouTube" in instructions
    assert "Не утверждай, что просмотрел кадры или" in instructions
    assert "Несколько роликов YouTube не" in instructions
    assert "считай независимыми издателями" in instructions


def test_time_based_trend_requires_independent_dated_sources() -> None:
    source = _source()
    validator = source[
        source.index("const trendDirections") :
        source.index("const guidance = value.guidance")
    ]

    assert (
        'const timeBasedDirections = new Set(["emerging", "growing", "declining"])'
        in validator
    )
    assert "timeBasedDirections.has(String(signal.direction))" in validator
    assert "directionalSourceIds.length < 2" in validator
    assert "independentPublishers.size < 2" in validator
    assert "datedWebSourceIds.length < 2" in validator
    assert 'sourcePublishers.get(id) !== "input_photo"' in validator
    assert 'if (signal.confidence === "high") signal.confidence = "medium"' in validator
    assert "publishedDays.size < 2" in validator
    assert "publishedAfterSnapshot" in validator
    assert "!hasRecentEvidence" in validator
    assert "!allEvidenceInLookback" in validator
    assert 'signal.direction = "unclear"' in validator
    assert 'signal.confidence = "low"' in validator
    assert 'signal.recommended_use = "monitor"' in validator
    assert "45 * 86_400_000" in validator
    assert "180 * 86_400_000" in validator
    assert "sourcePublishers.get(id)" in validator
    assert "sourcePublishedAt.get(id)" in validator
    assert "publisherDomainKey(trustedUrl)" in source
    assert 'replace(/^www\\./u, "")' in source
    assert 'labels.slice(-3).join(".")' in source
    assert "publishedTimestamp > accessedTimestamp" in source
    assert "accessedTimestamp > Date.now() + 300_000" in source
    assert 'new Set(["test", "monitor", "avoid"]).has(' in validator
    # validRefs rejects duplicate IDs before the temporal corroboration guard.
    assert "new Set(refs).size === refs.length" in source
    assert "!Array.isArray(signal.source_ids) || !validRefs(signal.source_ids)" in validator


def test_trend_snapshot_date_is_a_valid_non_future_utc_day() -> None:
    source = _source()
    validator = source[
        source.index("function isIsoCalendarDate") :
        source.index("function hasExactKeys")
    ]

    assert "new Date(timestamp).toISOString().slice(0, 10) === value" in validator
    assert "value === expectedUtcDate" in validator
    assert "providerRequestedAt.slice(0, 10)" in source
    assert "Date.now() + 86_400_000" not in validator


def test_guidance_is_proactive_and_v2_sections_reach_summary_and_brief() -> None:
    source = _source()
    validator = source[
        source.index("const guidance = value.guidance") :
        source.index("return value;", source.index("const guidance = value.guidance"))
    ]

    assert 'guidance.status === "needs_user_decision"' in validator
    assert "guidance.questions_for_user.length < 1" in validator
    assert 'guidance.status === "ready_for_brief"' in validator
    assert 'guidance.status = "needs_more_evidence"' in validator
    assert 'competitorCoverage !== "sufficient" || !hasActionableTrend' in validator
    assert 'signal.recommended_use === "test"' in validator
    assert '["medium", "high"].includes(String(signal.confidence))' in validator
    assert 'signal.direction !== "unclear"' in validator
    assert "isTextArray(guidance.suggested_actions, 1, 8, 600)" in validator
    assert "пересчитайте только нужный этап" in validator

    completion = source[
        source.index("function buildCompletionPayload") :
        source.index("const CREATOR_PRODUCT_RESEARCH_USER_OPTIONS")
    ]
    for section in (
        "category_analysis",
        "competitor_analysis",
        "trend_analysis",
        "guidance",
    ):
        assert completion.count(f"{section}: result.{section} as Json") == 2


def test_edge_platform_contract_matches_latest_research_rpc_and_schema() -> None:
    source = _source()
    accepted = {"instagram", "youtube", "vk", "wildberries", "ozon"}
    platform_block = source[
        source.index("const PLATFORMS = new Set([") :
        source.index("]);", source.index("const PLATFORMS = new Set([")) + 3
    ]
    scenarios = source.index("scenarios: {")
    platform_schema = source[
        source.index("platform: {", scenarios) :
        source.index("},", source.index("platform: {", scenarios)) + 2
    ]
    for platform in accepted:
        assert f'"{platform}"' in platform_block
        assert f'"{platform}"' in platform_schema
    for unsupported in {"tiktok", "telegram"}:
        assert f'"{unsupported}"' not in platform_block
    assert "PLATFORMS.has(platform)" in source
    assert "instagram, youtube, vk, wildberries или ozon" in source
