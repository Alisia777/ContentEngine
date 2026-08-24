from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "supabase/migrations/202608030010_research_outcome_learning_control.sql"
)
GENERATION_CONSUMPTION_MIGRATION_PATH = (
    ROOT
    / "supabase/migrations/202608030013_research_outcome_generation_consumption.sql"
)
API_PATH = ROOT / "web/app/supabase-api.js"
VIEW_PATH = ROOT / "web/app/product-research-view.js"
APP_PATH = ROOT / "web/app/app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _sql_function(source: str, name: str) -> str:
    header = re.compile(
        rf"\bcreate\s+(?:or\s+replace\s+)?function\s+public\.{re.escape(name)}\s*\(",
        re.IGNORECASE,
    )
    match = header.search(source)
    assert match is not None, f"SQL function public.{name} is missing"
    next_function = re.search(
        r"\bcreate\s+(?:or\s+replace\s+)?function\s+",
        source[match.end() :],
        re.IGNORECASE,
    )
    end = len(source) if next_function is None else match.end() + next_function.start()
    return source[match.start() : end]


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable outcome-learning contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(_read(path), encoding="utf-8")
        (directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const result = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_outcome_learning_migration_parses_and_writes_only_its_ledger() -> None:
    sql = _read(MIGRATION_PATH)
    try:
        from pglast import parse_sql
    except ImportError:
        pytest.skip("pglast is required for the PostgreSQL syntax contract")
    parse_sql(sql)

    refresh = _sql_function(sql, "creator_refresh_research_outcome_learning")
    decide = _sql_function(sql, "creator_decide_research_outcome_learning")
    status = _sql_function(sql, "creator_research_outcome_learning_status")
    mutable = f"{refresh}\n{decide}".casefold()

    allowed_insert_targets = {
        "research_outcome_lineage_snapshots",
        "research_outcome_learning_candidates",
        "research_outcome_learning_candidate_evidence",
        "research_outcome_learning_decisions",
        "research_outcome_learning_memory_versions",
    }
    insert_targets = set(
        re.findall(
            r"\binsert\s+into\s+content_factory\.([a-z0-9_]+)",
            mutable,
            re.IGNORECASE,
        )
    )
    assert insert_targets
    assert insert_targets <= allowed_insert_targets

    forbidden_tables = (
        "product_research_runs",
        "creative_brief_drafts",
        "generation_jobs",
        "generation_creative_signals",
        "media_objects",
        "content_review_runs",
        "content_review_decisions",
        "placements",
        "metric_snapshots",
        "research_provider_attempts",
        "generation_spend_reservations",
    )
    for table in forbidden_tables:
        assert not re.search(
            rf"\b(?:insert\s+into|update|delete\s+from|merge\s+into)\s+"
            rf"content_factory\.{table}\b",
            mutable,
            re.IGNORECASE,
        )

    for forbidden_call in (
        "creator_start_product_research",
        "creator_start_real_generation",
        "creator_confirm_placement",
        "creator_record_metric",
        "creator-product-research",
        "creator-generate",
        "fetch(",
        "http.",
        "net.",
    ):
        assert forbidden_call not in mutable

    status_folded = status.casefold()
    assert not re.search(
        r"\b(?:insert\s+into|update|delete\s+from|merge\s+into|truncate)\b",
        status_folded,
    )
    assert "begin_command" not in status_folded
    assert "finish_command" not in status_folded
    assert "pg_advisory_xact_lock" not in status_folded
    assert "limit 20" in status_folded
    assert "limit 10000" in status_folded
    assert "'automatic_activation', false" in status_folded
    assert "'generation_consumption', 'not_wired'" in status_folded

    refresh_folded = refresh.casefold()
    assert "research_current_eligible_outcomes" in refresh_folded
    assert "from current_outcomes latest" in refresh_folded
    evidence_set = _between(
        refresh_folded,
        "select coalesce(jsonb_agg(jsonb_build_object(",
        "evidence_hash_value :=",
    )
    assert "from current_outcomes latest" in evidence_set
    assert "preferred_angle_value" not in evidence_set
    assert "comparator_angle_value" not in evidence_set

    decide_folded = decide.casefold()
    assert "research_current_eligible_outcomes" in decide_folded
    assert "research_outcome_refresh_required" in decide_folded
    assert "'recommended_next_step', case action_value" in decide_folded
    stale_guard = _between(
        decide_folded,
        "if action_value = 'activate' and exists (",
        "message = 'research_outcome_candidate_stale'",
    )
    assert "limit 10000" in stale_guard
    assert "evidence_difference" in stale_guard
    assert stale_guard.count(" except\n") == 2
    assert "current_outcomes.id from current_outcomes" in stale_guard
    assert "candidate_evidence.id from candidate_evidence" in stale_guard


def test_outcome_learning_sql_disambiguates_values_and_confirmation() -> None:
    learning_sql = _read(MIGRATION_PATH)
    generation_sql = _read(GENERATION_CONSUMPTION_MIGRATION_PATH)
    try:
        from pglast import parse_sql
    except ImportError:
        pytest.skip("pglast is required for the PostgreSQL syntax contract")
    parse_sql(learning_sql)
    parse_sql(generation_sql)

    refresh = _sql_function(
        learning_sql, "creator_refresh_research_outcome_learning"
    ).casefold()
    assert (
        "on conflict on constraint "
        "research_outcome_lineage_org_placement_metric_uq" in refresh
    )
    assert "on conflict (organization_id, placement_id, metric_snapshot_id)" not in refresh
    assert "decided_at timestamptz not null default clock_timestamp()" in learning_sql
    for field in (
        "preferred_count",
        "preferred_product_count",
        "preferred_views",
        "preferred_clicks",
        "preferred_orders",
        "preferred_revenue",
        "preferred_ctr",
        "preferred_order_rate",
        "preferred_score",
        "comparator_count",
        "comparator_product_count",
        "comparator_views",
        "comparator_clicks",
        "comparator_orders",
        "comparator_revenue",
        "comparator_ctr",
        "comparator_order_rate",
        "comparator_score",
    ):
        assert f"summary.{field}" in refresh

    prepare = _sql_function(
        generation_sql, "creator_prepare_research_outcome_generation_selection"
    ).casefold()
    assert (
        "jsonb_typeof(p_payload -> 'confirmation') is distinct from 'boolean'"
        in prepare
    )
    assert (
        "p_payload -> 'confirmation' is distinct from 'true'::jsonb" in prepare
    )


def test_api_declares_scope_registry_and_three_outcome_control_rpcs() -> None:
    api_source = _read(API_PATH)
    assert './supabase-api.js?v=20260823.copy-engines.61' in _read(APP_PATH)
    rpc_values = set(
        re.findall(r'"(creator_[a-z0-9_]*research_outcome_learning[a-z0-9_]*)"', api_source)
    )
    assert rpc_values == {
        "creator_research_outcome_learning_scopes",
        "creator_research_outcome_learning_status",
        "creator_refresh_research_outcome_learning",
        "creator_decide_research_outcome_learning",
    }

    result = _run_module(
        API_PATH,
        """
        const categoryId = "20000000-0000-4000-8000-000000000001";
        const productId = "30000000-0000-4000-8000-000000000001";
        const projectId = "40000000-0000-4000-8000-000000000001";
        const scopeItem = (scope) => ({
          scope_key: `${scope.market_category_id}:${scope.platform}:${scope.model}`,
          scope,
          market_category: {
            market_category_id: scope.market_category_id,
            canonical_name: "Уход за кожей",
            status: "active",
          },
        });
        const makeApi = (scopes, outcomeImpl) => {
          const calls = [];
          const api = Object.create(subject.CreatorApi.prototype);
          api.organizationId = "10000000-0000-4000-8000-000000000001";
          api.call = async (rpc, payload) => {
            calls.push({ rpc, payload });
            if (rpc === "creator_project_research_status") {
              return {
                run: { id: payload.run_id, status: "completed" },
              };
            }
            if (rpc === "creator_research_watchlist_status") {
              return { watchlist: null, snapshots: [] };
            }
            if (rpc === "creator_research_provider_status") {
              return { ok: true };
            }
            if (rpc === "creator_research_market_category_registry") {
              return { current_binding: { category_key: categoryId } };
            }
            if (rpc === "creator_research_outcome_learning_scopes") {
              return {
                ok: true,
                version: "research-outcome-scope-registry-v1",
                run_id: payload.run_id,
                product_id: productId,
                returned_scope_count: scopes.length,
                truncated: false,
                scopes: scopes.map(scopeItem),
              };
            }
            if (rpc === "creator_research_youtube_overview") return {};
            if (rpc === "creator_research_outcome_learning_status") {
              return outcomeImpl(payload);
            }
            throw new Error(`unexpected ${rpc}`);
          };
          return { api, calls };
        };

        const selectedScope = {
          market_category_id: categoryId,
          platform: "youtube",
          model: "seedance2_fast",
        };
        const valid = makeApi([
          { market_category_id: categoryId, platform: "tiktok", model: "gen4_turbo" },
          selectedScope,
          { market_category_id: categoryId, platform: "vk", model: "seedream5_lite" },
        ], async () => ({ ok: true, marker: "outcome" }));
        const status = await valid.api.productResearchStatus("run-valid", {
          outcome_scope: selectedScope,
          projectId,
        });
        const outcomeCall = valid.calls.find(
          (item) => item.rpc === "creator_research_outcome_learning_status",
        );

        const missing = makeApi([selectedScope], async () => {
          throw new Error("scope must suppress this call");
        });
        const missingStatus = await missing.api.productResearchStatus("run-missing", {
          outcome_scope: {
            market_category_id: categoryId,
            platform: "telegram",
            model: "gen4_turbo",
          },
          projectId,
        });

        return {
          scope: status.research_outcome_learning_scope,
          outcomePayload: outcomeCall?.payload,
          outcomeMarker: status.research_outcome_learning.marker,
          outcomeUnavailable: status.research_outcome_learning_unavailable,
          missingScope: missingStatus.research_outcome_learning_scope,
          missingFlag: missingStatus.research_outcome_learning_scope_missing,
          missingUnavailable: missingStatus.research_outcome_learning_unavailable,
          missingOutcome: missingStatus.research_outcome_learning,
          missingOutcomeCalls: missing.calls.filter(
            (item) => item.rpc === "creator_research_outcome_learning_status",
          ).length,
        };
        """,
    )

    expected_scope = {
        "market_category_id": "20000000-0000-4000-8000-000000000001",
        "platform": "youtube",
        "model": "seedance2_fast",
    }
    assert result == {
        "scope": expected_scope,
        "outcomePayload": {
            **expected_scope,
            "organization_id": "10000000-0000-4000-8000-000000000001",
        },
        "outcomeMarker": "outcome",
        "outcomeUnavailable": False,
        "missingScope": None,
        "missingFlag": True,
        "missingUnavailable": False,
        "missingOutcome": None,
        "missingOutcomeCalls": 0,
    }


def test_outcome_status_is_a_bounded_satellite_without_losing_core_status() -> None:
    result = _run_module(
        API_PATH,
        """
        const categoryId = "20000000-0000-4000-8000-000000000001";
        const projectId = "40000000-0000-4000-8000-000000000001";
        const api = Object.create(subject.CreatorApi.prototype);
        api.organizationId = "10000000-0000-4000-8000-000000000001";
        api.call = async (rpc, payload) => {
          if (rpc === "creator_project_research_status") {
            return {
              run: { id: payload.run_id, status: "processing" },
              latest_draft: { brief: { scenarios: [{
                platform: "youtube",
                recommended_generation_mode: "real_gen4",
              }], creative_potential: { recommended_scenario_position: 1 } } },
            };
          }
          if (rpc === "creator_research_watchlist_status") {
            return { watchlist: null, snapshots: [] };
          }
          if (rpc === "creator_research_provider_status") return { ok: true };
          if (rpc === "creator_research_market_category_registry") {
            return { current_binding: { category_id: categoryId } };
          }
          if (rpc === "creator_research_outcome_learning_scopes") {
            const scope = {
              market_category_id: categoryId,
              platform: "youtube",
              model: "gen4_turbo",
            };
            return {
              ok: true,
              version: "research-outcome-scope-registry-v1",
              run_id: payload.run_id,
              product_id: "30000000-0000-4000-8000-000000000001",
              returned_scope_count: 1,
              truncated: false,
              scopes: [{
                scope_key: `${categoryId}:youtube:gen4_turbo`,
                scope,
                market_category: {
                  market_category_id: categoryId,
                  canonical_name: "Уход за кожей",
                  status: "active",
                },
              }],
            };
          }
          if (rpc === "creator_research_youtube_overview") return {};
          if (rpc === "creator_research_outcome_learning_status") {
            return await new Promise(() => {});
          }
          throw new Error(`unexpected ${rpc}`);
        };
        const nativeSetTimeout = globalThis.setTimeout;
        const nativeClearTimeout = globalThis.clearTimeout;
        globalThis.setTimeout = (callback) => { queueMicrotask(callback); return 1; };
        globalThis.clearTimeout = () => {};
        try {
          const status = await api.productResearchStatus("run-active", { projectId });
          return {
            runStatus: status.run.status,
            scope: status.research_outcome_learning_scope,
            scopeMissing: status.research_outcome_learning_scope_missing,
            outcomeUnavailable: status.research_outcome_learning_unavailable,
            outcome: status.research_outcome_learning,
          };
        } finally {
          globalThis.setTimeout = nativeSetTimeout;
          globalThis.clearTimeout = nativeClearTimeout;
        }
        """,
    )
    assert result == {
        "runStatus": "processing",
        "scope": {
            "market_category_id": "20000000-0000-4000-8000-000000000001",
            "platform": "youtube",
            "model": "gen4_turbo",
        },
        "scopeMissing": False,
        "outcomeUnavailable": True,
        "outcome": None,
    }


def test_api_decision_payload_is_strict_and_revert_is_a_separate_branch() -> None:
    result = _run_module(
        API_PATH,
        """
        const calls = [];
        const api = Object.create(subject.CreatorApi.prototype);
        api.mutate = async (rpc, payload) => { calls.push({ rpc, payload }); return { ok: true }; };
        const scope = {
          marketCategoryId: "20000000-0000-4000-8000-000000000001",
          platform: "YouTube",
          model: "seedance2_fast",
        };
        const base = {
          candidate_id: "30000000-0000-4000-8000-000000000001",
          candidate_version: 7,
          candidate_hash: "a".repeat(64),
          expected_scope_version: 2,
          reason: "  Проверены   зрелые результаты  ",
          confirmation: true,
          ignored_field: "must-not-cross-boundary",
        };
        await api.decideResearchOutcomeLearning(scope, {
          ...base,
          action: "activate",
        });
        await api.decideResearchOutcomeLearning(scope, {
          ...base,
          action: "revert",
          rollback_memory_version_id: "40000000-0000-4000-8000-000000000001",
        });

        const rejected = [];
        for (const [label, invalidScope, options] of [
          ["action", scope, { ...base, action: "auto_activate" }],
          ["confirmation", scope, { ...base, action: "activate", confirmation: false }],
          ["revert_missing", scope, { ...base, action: "revert" }],
          ["rollback_unexpected", scope, { ...base, action: "reject", rollback_memory_version_id: "40000000-0000-4000-8000-000000000001" }],
          ["scope", { ...scope, platform: "ozon" }, { ...base, action: "reject" }],
        ]) {
          try {
            await api.decideResearchOutcomeLearning(invalidScope, options);
          } catch (error) {
            rejected.push([label, error.code]);
          }
        }
        return { calls, rejected };
        """,
    )

    common = {
        "candidate_id": "30000000-0000-4000-8000-000000000001",
        "candidate_version": 7,
        "candidate_hash": "a" * 64,
        "expected_scope_version": 2,
        "reason": "Проверены зрелые результаты",
        "confirmation": True,
    }
    assert result["calls"] == [
        {
            "rpc": "creator_decide_research_outcome_learning",
            "payload": {**common, "action": "activate"},
        },
        {
            "rpc": "creator_decide_research_outcome_learning",
            "payload": {
                **common,
                "action": "revert",
                "rollback_memory_version_id": (
                    "40000000-0000-4000-8000-000000000001"
                ),
            },
        },
    ]
    assert result["rejected"] == [
        ["action", "research_outcome_decision_action_invalid"],
        ["confirmation", "research_outcome_decision_confirmation_required"],
        ["revert_missing", "research_outcome_rollback_target_invalid"],
        ["rollback_unexpected", "research_outcome_rollback_target_unexpected"],
        ["scope", "research_outcome_scope_invalid"],
    ]


def test_view_fails_closed_and_keeps_a_new_candidate_inactive_and_xss_safe() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const scope = {
          market_category_id: "20000000-0000-4000-8000-000000000001",
          platform: "youtube",
          model: "seedance2_fast",
        };
        const makeCandidate = (overrides = {}) => ({
          candidate_id: "30000000-0000-4000-8000-000000000001",
          candidate_version: 1,
          candidate_hash: "b".repeat(64),
          candidate_kind: "creative_angle_preference",
          scope,
          candidate_payload: {
            schema_version: "research-outcome-learning-v1",
            candidate_kind: "creative_angle_preference",
            scope,
            preferred_creative_angle: "product_focus",
            avoid_creative_angle: null,
            ruleset_version: "outcome-v1",
          },
          effectiveness_evidence: {
            eligible_outcome_count: 6,
            eligible_angle_count: 2,
            minimum_outcomes_per_angle: 3,
            minimum_views_per_outcome: 100,
            minimum_maturity_hours: 72,
            maximum_outcomes_considered: 100,
            overlapping_product_count: 2,
            preferred: { creative_angle: "product_focus", outcome_count: 3, mean_ctr: 0.2, mean_order_rate: 0.04, total_orders: 4, total_revenue_minor: 1000 },
            comparator: { creative_angle: "demonstration", outcome_count: 3, mean_ctr: 0.1, mean_order_rate: 0.02, total_orders: 2, total_revenue_minor: 500 },
            absolute_deltas: { mean_ctr: 0.1, mean_order_rate: 0.02 },
            views_are_not_a_rank_signal: true,
          },
          guard_evidence: {
            qa_approved_outcome_count: 6,
            first_party_metric_outcome_count: 6,
            distinct_product_count: 2,
            market_category_exact: true,
            tenant_scope_exact: true,
            raw_competitor_content_excluded: true,
            raw_prompt_caption_url_excluded: true,
            automatic_activation: false,
            advisory_only: true,
            generation_consumption: "not_wired",
          },
          status: "pending",
          created_at: "2026-08-03T10:00:00Z",
          advisory_only: true,
          generation_consumption: "not_wired",
          ...overrides,
        });
        const guidance = {
          status: "candidate_requires_decision",
          recommended_next_step: "review_activate_reject_or_quarantine",
          reason_codes: ["bounded_first_party_evidence"],
          automatic_activation: false,
          advisory_only: true,
          generation_consumption: "not_wired",
          provider_action: false,
          spend_action: false,
          generation_action: false,
          publication_action: false,
        };
        const control = {
          ok: true,
          version: "research-outcome-learning-control-v1",
          can_decide: true,
          can_refresh: true,
          market_category: {
            market_category_id: scope.market_category_id,
            canonical_name: "</strong><script>alert(1)</script>",
            status: "active",
          },
          scope,
          captured_current_outcome_count: 6,
          candidates: [makeCandidate()],
          current_memory: null,
          rollback_target: null,
          decision_history: [],
          guidance,
        };
        const envelope = { control, scope, unavailable: false, scopeMissing: false };
        const normalized = subject.normalizeResearchOutcomeLearning(envelope);
        const invalid = [
          { ...control, version: "research-outcome-learning-control-v2" },
          { ...control, unexpected_autonomy: true },
          { ...control, guidance: { ...guidance, automatic_activation: true } },
          { ...control, candidates: [makeCandidate({ raw_caption: "steal me" })] },
          { ...control, candidates: [makeCandidate({ generation_consumption: "wired" })] },
          { ...control, current_memory: {
            memory_version_id: "40000000-0000-4000-8000-000000000001",
            memory_version: 1,
            state: "active",
            action: "activate",
            candidate_id: makeCandidate().candidate_id,
            candidate: makeCandidate({ status: "pending" }),
            previous_memory_version_id: null,
            rollback_target_memory_version_id: null,
            created_at: "2026-08-03T10:05:00Z",
            advisory_only: true,
            generation_consumption: "not_wired",
          } },
        ].map((candidateControl) => subject.normalizeResearchOutcomeLearning({
          control: candidateControl,
          scope,
          unavailable: false,
          scopeMissing: false,
        }));
        const record = { id: "run-1", outcomeLearning: normalized };
        const afterRefresh = subject.applyResearchOutcomeLearningMutation(record, {
          ok: true,
          version: "research-outcome-learning-control-v1",
          candidate_created: true,
          eligible_outcome_count: 6,
          candidate: makeCandidate(),
          guidance,
        });
        const decisionGuidance = {
          ...guidance,
          status: "advisory_memory_active",
          recommended_next_step: "monitor_effectiveness_and_keep_rollback_ready",
          reason_codes: [],
        };
        const afterDecision = subject.applyResearchOutcomeLearningMutation(record, {
          ok: true,
          version: "research-outcome-learning-control-v1",
          action: "activate",
          decision: {
            candidate_id: makeCandidate().candidate_id,
            candidate_version: 1,
            candidate_hash: "b".repeat(64),
            expected_scope_version: 0,
            rollback_memory_version_id: null,
          },
          memory: {
            memory_version_id: "40000000-0000-4000-8000-000000000001",
            memory_version: 1,
            state: "active",
            candidate_id: makeCandidate().candidate_id,
            previous_memory_version_id: null,
            rollback_target_memory_version_id: null,
            advisory_only: true,
            generation_consumption: "not_wired",
          },
          guidance: decisionGuidance,
        });
        const contradictoryDecision = subject.applyResearchOutcomeLearningMutation(record, {
          ok: true,
          version: "research-outcome-learning-control-v1",
          action: "activate",
          decision: {
            candidate_id: makeCandidate().candidate_id,
            candidate_version: 1,
            candidate_hash: "b".repeat(64),
            expected_scope_version: 0,
            rollback_memory_version_id: null,
          },
          memory: {
            memory_version_id: "40000000-0000-4000-8000-000000000002",
            memory_version: 1,
            state: "inactive",
            candidate_id: null,
            previous_memory_version_id: null,
            rollback_target_memory_version_id: null,
            advisory_only: true,
            generation_consumption: "not_wired",
          },
          guidance: decisionGuidance,
        });
        const markup = subject.researchOutcomeLearningMarkup(normalized);
        return {
          available: normalized.available,
          antiAutonomy: [
            normalized.guidance.automaticActivation,
            normalized.guidance.advisoryOnly,
            normalized.guidance.generationConsumption,
            normalized.guidance.providerAction,
            normalized.guidance.spendAction,
            normalized.guidance.generationAction,
            normalized.guidance.publicationAction,
          ],
          invalidFailClosed: invalid.every((item) => item.available === false),
          pendingStatus: normalized.candidates[0].status,
          noActiveMemory: normalized.currentMemory === null,
          refreshStillPending: afterRefresh.outcomeLearning.candidates[0].status,
          refreshDidNotActivate: afterRefresh.outcomeLearning.currentMemory === null,
          decisionSurvivesReadFailure: afterDecision.outcomeLearning.currentMemory?.state === "active"
            && afterDecision.outcomeLearning.candidates[0].status === "active",
          contradictoryDecisionRejected: contradictoryDecision.outcomeLearning.currentMemory === null
            && contradictoryDecision.outcomeLearning.candidates[0].status === "pending",
          escapedXss: markup.includes("&lt;script&gt;alert(1)&lt;/script&gt;") && !markup.includes("<script>"),
          activeBlock: markup.includes("product-research-outcome-active"),
          advisoryWarning: markup.includes("не подключён к генератору") || markup.includes("не влияет на платную генерацию"),
        };
        """,
    )
    assert result == {
        "available": True,
        "antiAutonomy": [False, True, "not_wired", False, False, False, False],
        "invalidFailClosed": True,
        "pendingStatus": "pending",
        "noActiveMemory": True,
        "refreshStillPending": "pending",
        "refreshDidNotActivate": True,
        "decisionSurvivesReadFailure": True,
        "contradictoryDecisionRejected": True,
        "escapedXss": True,
        "activeBlock": False,
        "advisoryWarning": True,
    }


def test_view_renders_explicit_confirmed_forms_for_all_five_decisions() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const scope = {
          market_category_id: "20000000-0000-4000-8000-000000000001",
          platform: "youtube",
          model: "gen4_turbo",
        };
        const makeCandidate = (id, version, letter, status, preferred, comparator) => ({
          candidate_id: id,
          candidate_version: version,
          candidate_hash: letter.repeat(64),
          candidate_kind: "creative_angle_preference",
          scope,
          candidate_payload: {
            schema_version: "research-outcome-learning-v1",
            candidate_kind: "creative_angle_preference",
            scope,
            preferred_creative_angle: preferred,
            avoid_creative_angle: null,
            ruleset_version: "outcome-v1",
          },
          effectiveness_evidence: {
            eligible_outcome_count: 6,
            eligible_angle_count: 2,
            minimum_outcomes_per_angle: 3,
            minimum_views_per_outcome: 100,
            minimum_maturity_hours: 72,
            maximum_outcomes_considered: 100,
            overlapping_product_count: 2,
            preferred: { creative_angle: preferred, outcome_count: 3, mean_ctr: 0.2, mean_order_rate: 0.04, total_orders: 4, total_revenue_minor: 1000 },
            comparator: { creative_angle: comparator, outcome_count: 3, mean_ctr: 0.1, mean_order_rate: 0.02, total_orders: 2, total_revenue_minor: 500 },
            absolute_deltas: { mean_ctr: 0.1, mean_order_rate: 0.02 },
            views_are_not_a_rank_signal: true,
          },
          guard_evidence: {
            qa_approved_outcome_count: 6,
            first_party_metric_outcome_count: 6,
            distinct_product_count: 2,
            market_category_exact: true,
            tenant_scope_exact: true,
            raw_competitor_content_excluded: true,
            raw_prompt_caption_url_excluded: true,
            automatic_activation: false,
            advisory_only: true,
            generation_consumption: "not_wired",
          },
          status,
          created_at: "2026-08-03T10:00:00Z",
          advisory_only: true,
          generation_consumption: "not_wired",
        });
        const pending = makeCandidate("30000000-0000-4000-8000-000000000001", 3, "a", "pending", "product_focus", "demonstration");
        const active = makeCandidate("30000000-0000-4000-8000-000000000002", 2, "b", "active", "trust_builder", "comparison");
        const prior = makeCandidate("30000000-0000-4000-8000-000000000003", 1, "c", "superseded", "curiosity_gap", "objection_handling");
        const guidance = {
          status: "candidate_requires_decision",
          recommended_next_step: "review_activate_reject_or_quarantine",
          reason_codes: [],
          automatic_activation: false,
          advisory_only: true,
          generation_consumption: "not_wired",
          provider_action: false,
          spend_action: false,
          generation_action: false,
          publication_action: false,
        };
        const normalized = subject.normalizeResearchOutcomeLearning({
          scope,
          unavailable: false,
          scopeMissing: false,
          control: {
            ok: true,
            version: "research-outcome-learning-control-v1",
            can_decide: true,
            can_refresh: true,
            market_category: { market_category_id: scope.market_category_id, canonical_name: "Уход", status: "active" },
            scope,
            captured_current_outcome_count: 12,
            candidates: [pending, active, prior],
            current_memory: {
              memory_version_id: "40000000-0000-4000-8000-000000000003",
              memory_version: 3,
              state: "active",
              action: "activate",
              candidate_id: active.candidate_id,
              candidate: active,
              previous_memory_version_id: "40000000-0000-4000-8000-000000000002",
              rollback_target_memory_version_id: null,
              created_at: "2026-08-03T10:05:00Z",
              advisory_only: true,
              generation_consumption: "not_wired",
            },
            rollback_target: {
              memory_version_id: "40000000-0000-4000-8000-000000000001",
              memory_version: 1,
              candidate_id: prior.candidate_id,
              candidate_hash: prior.candidate_hash,
              candidate_version: prior.candidate_version,
              candidate: prior,
            },
            decision_history: [{
              action: "reject",
              candidate_id: pending.candidate_id,
              candidate_version: pending.candidate_version,
              candidate_hash: pending.candidate_hash,
              expected_scope_version: 3,
              rollback_memory_version_id: null,
              reason: "<img src=x onerror=alert(1)>",
              decided_at: "2026-08-03T10:10:00Z",
            }],
            guidance,
          },
        });
        const markup = subject.researchOutcomeLearningMarkup(normalized);
        const actions = [...markup.matchAll(/data-outcome-action="([a-z]+)"/gu)]
          .map((match) => match[1]).sort();
        return {
          available: normalized.available,
          actions,
          decisionForms: (markup.match(/product-research-outcome-form/g) || []).length,
          confirmations: (markup.match(/name="outcome_confirmation"/g) || []).length,
          reasons: (markup.match(/name="reason"/g) || []).length,
          submitButtons: (markup.match(/type="submit" data-outcome-action=/g) || []).length,
          hiddenHashes: (markup.match(/name="candidate_hash"/g) || []).length,
          expectedVersions: (markup.match(/name="expected_scope_version"/g) || []).length,
          rollbackBound: markup.includes('name="rollback_memory_version_id" value="40000000-0000-4000-8000-000000000001"'),
          historyEscaped: markup.includes("&lt;img src=x onerror=alert(1)&gt;") && !markup.includes("<img src=x"),
        };
        """,
    )
    assert result == {
        "available": True,
        "actions": ["activate", "deactivate", "quarantine", "reject", "revert"],
        "decisionForms": 3,
        "confirmations": 3,
        "reasons": 3,
        "submitButtons": 5,
        "hiddenHashes": 3,
        "expectedVersions": 3,
        "rollbackBound": True,
        "historyEscaped": True,
    }


def test_optimistic_deactivate_and_revert_use_embedded_bounded_candidates() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const active = {
          id: "30000000-0000-4000-8000-000000000021",
          version: 21,
          hash: "a".repeat(64),
          status: "active",
        };
        const rollback = {
          id: "30000000-0000-4000-8000-000000000001",
          version: 1,
          hash: "b".repeat(64),
          status: "superseded",
        };
        const memoryId = "40000000-0000-4000-8000-000000000004";
        const rollbackMemoryId = "40000000-0000-4000-8000-000000000001";
        const base = {
          id: "run-1",
          outcomeLearning: {
            available: true,
            candidates: [],
            currentMemory: { id: memoryId, version: 4, candidate: active },
            rollbackTarget: { memoryId: rollbackMemoryId, candidate: rollback },
          },
        };
        const guidance = (status, next) => ({
          status,
          recommended_next_step: next,
          reason_codes: [],
          automatic_activation: false,
          advisory_only: true,
          generation_consumption: "not_wired",
          provider_action: false,
          spend_action: false,
          generation_action: false,
          publication_action: false,
        });
        const common = (candidate, action, rollbackId = null) => ({
          ok: true,
          version: "research-outcome-learning-control-v1",
          action,
          decision: {
            candidate_id: candidate.id,
            candidate_version: candidate.version,
            candidate_hash: candidate.hash,
            expected_scope_version: 4,
            rollback_memory_version_id: rollbackId,
          },
        });
        const afterDeactivate = subject.applyResearchOutcomeLearningMutation(base, {
          ...common(active, "deactivate"),
          memory: {
            memory_version_id: "40000000-0000-4000-8000-000000000005",
            memory_version: 5,
            state: "inactive",
            candidate_id: null,
            previous_memory_version_id: memoryId,
            rollback_target_memory_version_id: memoryId,
            advisory_only: true,
            generation_consumption: "not_wired",
          },
          guidance: guidance("advisory_memory_inactive", "review_rollback_target"),
        });
        const afterRevert = subject.applyResearchOutcomeLearningMutation(base, {
          ...common(rollback, "revert", rollbackMemoryId),
          memory: {
            memory_version_id: "40000000-0000-4000-8000-000000000005",
            memory_version: 5,
            state: "active",
            candidate_id: rollback.id,
            previous_memory_version_id: memoryId,
            rollback_target_memory_version_id: rollbackMemoryId,
            advisory_only: true,
            generation_consumption: "not_wired",
          },
          guidance: guidance("prior_advisory_memory_restored", "monitor_restored_memory"),
        });
        return {
          deactivateState: afterDeactivate.outcomeLearning.currentMemory.state,
          deactivateCandidate: afterDeactivate.outcomeLearning.currentMemory.candidate,
          revertState: afterRevert.outcomeLearning.currentMemory.state,
          revertCandidate: afterRevert.outcomeLearning.currentMemory.candidateId,
        };
        """,
    )
    assert result == {
        "deactivateState": "inactive",
        "deactivateCandidate": None,
        "revertState": "active",
        "revertCandidate": "30000000-0000-4000-8000-000000000001",
    }


def test_app_outcome_handlers_are_single_mutation_and_side_effect_free() -> None:
    app = _read(APP_PATH)
    refresh = _between(
        app,
        "async function submitProductResearchOutcomeRefresh",
        "async function submitProductResearchOutcomeDecision",
    )
    decision = _between(
        app,
        "async function submitProductResearchOutcomeDecision",
        "async function refreshProductResearchAfterYoutubeAction",
    )
    submit_router = _between(app, "async function handleSubmit", "function campaignPolicyPayload")

    assert refresh.count("state.api.refreshResearchOutcomeLearning(") == 1
    assert decision.count("state.api.decideResearchOutcomeLearning(") == 1
    assert decision.count("decideResearchOutcomeLearning(") == 1
    assert "refreshResearchOutcomeLearning" not in decision
    assert "submitProductResearchOutcomeDecision(form, event.submitter)" in submit_router
    assert "submitter?.dataset?.outcomeAction" in decision
    assert "form.elements.outcome_confirmation?.checked !== true" in decision

    for handler, mutation in (
        (refresh, "applyResearchOutcomeLearningMutation"),
        (decision, "applyResearchOutcomeLearningMutation"),
    ):
        assert handler.index(mutation) < handler.index("let statusRefreshUnavailable")
        assert handler.index("let statusRefreshUnavailable") < handler.index(
            "state.api.productResearchStatus"
        )
        assert "catch {\n      statusRefreshUnavailable = true;\n    }" in handler
        assert "statusRefreshUnavailable" in handler
        assert "не повторяйте" in handler.casefold()

    refresh_telemetry = _between(
        refresh,
        'await track("product_research_outcome_refreshed"',
        "  } catch (error)",
    )
    decision_telemetry = _between(
        decision,
        'await track("product_research_outcome_decided"',
        "  } catch (error)",
    )
    for telemetry in (refresh_telemetry, decision_telemetry):
        assert "reason" not in telemetry.casefold()
        for flag in (
            "paid_provider_action: false",
            "generation_action: false",
            "placement_action: false",
            "publication_action: false",
        ):
            assert flag in telemetry

    handlers = f"{refresh}\n{decision}"
    for forbidden in (
        "startProductResearch",
        "startRealGeneration",
        "confirmPlacement",
        "recordMetric",
        "invokeProductResearch",
        "fetch(",
        "fetchWithTimeout",
        ".functions.invoke",
        "creator-product-research",
        "creator-generate",
    ):
        assert forbidden not in handlers


def test_outcome_conflicts_never_retry_and_active_paid_restart_guard_remains() -> None:
    app = _read(APP_PATH)
    api = _read(API_PATH)
    decision = _between(
        app,
        "async function submitProductResearchOutcomeDecision",
        "async function refreshProductResearchAfterYoutubeAction",
    )
    conflict = decision[decision.index("const conflictCodes") :]
    assert "state.api.decideResearchOutcomeLearning" not in conflict
    assert conflict.count("state.api.productResearchStatus") == 1
    assert '"research_outcome_refresh_required"' in conflict
    assert "A stale decision is never retried automatically." in conflict
    assert "research_outcome_refresh_required:" in api
    assert "Сначала явно обновите evidence" in api

    new_research = _between(
        app,
        'if (action === "new-product-research")',
        'if (action === "reset-generation-filters")',
    )
    guard = 'productResearchStatusKind(state.productResearch.record?.status) === "active"'
    assert guard in new_research
    assert new_research.index(guard) < new_research.index("clearProductResearchRunId()")
    guarded_branch = new_research[: new_research.index("const previousRecord")]
    assert "await pollProductResearchStatus({ silent: false })" in guarded_branch
    assert "return;" in guarded_branch
