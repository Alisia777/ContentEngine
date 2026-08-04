from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "web/app/supabase-api.js"
APP_PATH = ROOT / "web/app/app.js"
VIEW_PATH = ROOT / "web/app/product-research-view.js"
EDGE_PATH = ROOT / "supabase/functions/creator-product-research/index.ts"
PROVIDER_SQL_PATH = (
    ROOT / "supabase/migrations/202608030008_research_provider_control_plane.sql"
)
MARKET_SQL_PATH = (
    ROOT / "supabase/migrations/202608030009_research_market_intelligence_identity.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
        pytest.skip("Node.js is required for executable research contracts")
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


def test_provider_sql_requires_paid_authorization_and_never_auto_canaries() -> None:
    sql = _read(PROVIDER_SQL_PATH)
    start = _sql_function(sql, "creator_start_product_research")
    claim = _sql_function(sql, "system_claim_product_research")
    status = _sql_function(sql, "creator_research_provider_status")

    assert "paid_analysis_ack" in start
    assert "paid_analysis_ack_required" in start
    assert "research_execution_authorizations" in start
    assert "research_execution_authorization_required" in claim
    assert "research_execution_authorizations" in claim
    assert "'automatic_canary', false" in status
    assert "'automatic_fallback', false" in status
    assert "'external_call_performed', false" in status
    assert "youtube_data_api_v3" in sql
    assert "openai_web_search" in sql
    assert re.search(r"check\s*\(not automatic_canary_allowed\)", sql, re.I)
    assert re.search(r"check\s*\(not automatic_fallback_allowed\)", sql, re.I)
    assert not re.search(r"\b(?:cron|http|net)\s*\.", status, re.I)


def test_edge_binds_provider_before_the_only_paid_transport() -> None:
    edge = _read(EDGE_PATH)
    analyze = edge[edge.index("const providerRequestedAt") : edge.index("const completed =")]
    assert analyze.index("beginProviderAttempt(model)") < analyze.index("fetchWithTimeout(")
    assert analyze.count("fetchWithTimeout(") == 1
    assert "provider_outcome_unknown" in analyze
    assert 'recordProviderHealth(\n    providerAttemptId,\n    "ready"' in analyze
    assert "automatic fallback" not in analyze.casefold()
    assert "retry" not in analyze.casefold()


def test_browser_status_degrades_satellite_controls_independently() -> None:
    result = _run_module(
        API_PATH,
        """
        const calls = [];
        const projectId = "40000000-0000-4000-8000-000000000001";
        const api = Object.create(subject.CreatorApi.prototype);
        api.withOrganization = (payload) => ({ ...payload, organization_id: "org-1" });
        api.call = async (rpc, payload) => {
          calls.push(rpc);
          if (rpc === "creator_project_research_status") {
            return { run: { id: payload.run_id, status: "completed" } };
          }
          if (rpc === "creator_research_provider_status") {
            return { providers: [{ provider_key: "openai_web_search" }], run_control: null };
          }
          if (rpc === "creator_research_watchlist_status") throw Object.assign(new Error("watch"), { code: "watch_down" });
          if (rpc === "creator_research_market_category_registry") throw Object.assign(new Error("market"), { code: "market_down" });
          throw new Error(`unexpected ${rpc}`);
        };
        const status = await api.productResearchStatus("run-1", { projectId });
        return {
          runStatus: status.run.status,
          watchUnavailable: status.watchlist_monitor_unavailable,
          providerUnavailable: status.research_provider_control_unavailable,
          providerKey: status.research_provider_control.providers[0].provider_key,
          marketUnavailable: status.research_market_registry_unavailable,
          calls: calls.sort(),
        };
        """,
    )

    assert result == {
        "runStatus": "completed",
        "watchUnavailable": True,
        "providerUnavailable": False,
        "providerKey": "openai_web_search",
        "marketUnavailable": True,
            "calls": [
                "creator_project_research_status",
                "creator_research_category_learning_status",
                "creator_research_market_category_registry",
            "creator_research_outcome_learning_scopes",
            "creator_research_provider_status",
            "creator_research_watchlist_status",
            "creator_research_youtube_overview",
        ],
    }


def test_never_settling_provider_status_is_bounded_without_losing_core_run() -> None:
    result = _run_module(
        API_PATH,
        """
        const projectId = "40000000-0000-4000-8000-000000000001";
        const api = Object.create(subject.CreatorApi.prototype);
        api.withOrganization = (payload) => ({ ...payload, organization_id: "org-1" });
        api.call = async (rpc, payload) => {
          if (rpc === "creator_project_research_status") return { run: { id: payload.run_id, status: "processing" } };
          if (rpc === "creator_research_provider_status") return await new Promise(() => {});
          if (rpc === "creator_research_watchlist_status") return { watchlist: null, snapshots: [] };
          if (rpc === "creator_research_market_category_registry") return { ok: true, can_resolve: true, categories: [], trend_timeline: [], guidance: {} };
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
            providerUnavailable: status.research_provider_control_unavailable,
            watchUnavailable: status.watchlist_monitor_unavailable,
          };
        } finally {
          globalThis.setTimeout = nativeSetTimeout;
          globalThis.clearTimeout = nativeClearTimeout;
        }
        """,
    )
    assert result == {
        "runStatus": "processing",
        "providerUnavailable": True,
        "watchUnavailable": False,
    }


def test_provider_view_fails_closed_on_incompatible_control_envelopes() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const base = {
          ok: true,
          version: "research-provider-control-plane-v1",
          providers: [{ provider_key: "openai_web_search", adapter_version: "openai-responses-web-search-v1" }],
          run_control: null,
          controls: { explicit_paid_analysis_required: true, creates_research_runs: false, automatic_canary: false, automatic_fallback: false, external_call_performed: false },
        };
        const candidates = [
          null,
          {},
          { ...base, ok: false },
          { ...base, version: "unknown-v2" },
          { ...base, controls: { ...base.controls, automatic_fallback: true } },
          { ...base, providers: [] },
        ];
        const normalized = candidates.map((control) => subject.normalizeResearchProviderControl({ control, unavailable: false }));
        const markup = normalized.map((control) => subject.researchProviderControlMarkup(control));
        const activeProgress = subject.productResearchProgressMarkup({
          status: "processing",
          productName: "Товар",
          statusNotice: "Статус временно недоступен",
        }, "Сеть временно не ответила");
        return {
          allUnavailable: normalized.every((control) => control.available === false),
          noSafetyClaim: markup.every((value) => !value.includes("Автоматические canary и fallback выключены")),
          activeOffersRestart: activeProgress.includes("Начать заново"),
          activeShowsNotice: activeProgress.includes("Статус временно недоступен"),
        };
        """,
    )
    assert result == {
        "allUnavailable": True,
        "noSafetyClaim": True,
        "activeOffersRestart": False,
        "activeShowsNotice": True,
    }


def test_market_category_api_sends_only_the_confirmed_action_branch() -> None:
    result = _run_module(
        API_PATH,
        """
        const calls = [];
        const reads = [];
        const api = Object.create(subject.CreatorApi.prototype);
        api.withOrganization = (payload) => ({ ...payload, organization_id: "org-1" });
        api.call = async (rpc, payload) => { reads.push({ rpc, payload }); return { ok: true, categories: [] }; };
        api.mutate = async (rpc, payload) => { calls.push({ rpc, payload }); return { ok: true }; };
        api.productResearchStatus = async () => ({ reloaded: true });
        const runId = "10000000-0000-4000-8000-000000000001";
        const categoryId = "20000000-0000-4000-8000-000000000001";
        const hash = "a".repeat(64);
        await api.resolveResearchMarketCategory(runId, {
          action: "create_and_bind",
          candidate_hash: hash,
          confirmation: true,
          canonical_name: "Уход за Волосами",
          definition: "Средства для ежедневного ухода за волосами",
          aliases: ["Несмываемый Уход", "несмываемый уход"],
        });
        await api.resolveResearchMarketCategory(runId, {
          action: "reclassify",
          candidate_hash: hash,
          confirmation: true,
          category_id: categoryId,
          reason: "Уточнены границы рынка",
          canonical_name: "must be ignored",
        });
        await api.searchResearchMarketCategories(runId, "  Уход   за волосами ");
        const rejected = [];
        for (const options of [
          { action: "auto_bind", candidate_hash: hash, confirmation: true },
          { action: "bind_existing", candidate_hash: hash, confirmation: false, category_id: categoryId },
          { action: "bind_existing", candidate_hash: "bad", confirmation: true, category_id: categoryId },
        ]) {
          try { await api.resolveResearchMarketCategory(runId, options); }
          catch (error) { rejected.push(error.code); }
        }
        return { calls, reads, rejected };
        """,
    )

    create_payload = result["calls"][0]["payload"]
    reclassify_payload = result["calls"][1]["payload"]
    assert result["calls"][0]["rpc"] == "creator_resolve_research_market_category"
    assert create_payload["action"] == "create_and_bind"
    assert create_payload["aliases"] == ["Несмываемый Уход"]
    assert "category_id" not in create_payload
    assert reclassify_payload["action"] == "reclassify"
    assert reclassify_payload["category_id"] == "20000000-0000-4000-8000-000000000001"
    assert "canonical_name" not in reclassify_payload
    assert result["reads"] == [{
        "rpc": "creator_research_market_category_registry",
        "payload": {
            "run_id": "10000000-0000-4000-8000-000000000001",
            "query": "Уход за волосами",
            "limit": 20,
            "organization_id": "org-1",
        },
    }]
    assert result["rejected"] == [
        "research_market_decision_action_invalid",
        "research_market_decision_confirmation_required",
        "research_market_category_candidate_stale",
    ]


def test_market_identity_ui_keeps_category_decisions_explicit_and_reset_safe() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const hash = "b".repeat(64);
        const currentId = "20000000-0000-4000-8000-000000000001";
        const otherId = "30000000-0000-4000-8000-000000000001";
        const nullProvider = subject.normalizeResearchProviderControl({
          control: {
            ok: true,
            version: "research-provider-control-plane-v1",
            providers: [
              { provider_key: "openai_web_search", adapter_version: "openai-responses-web-search-v1", display_name: "OpenAI web search", lifecycle_status: "active", rollout_stage: "production" },
              { provider_key: "youtube_data_api_v3", adapter_version: "youtube-data-api-v3-public-metadata-v1", display_name: "YouTube Data", lifecycle_status: "disabled", rollout_stage: "planned" },
            ],
            run_control: null,
            controls: { explicit_paid_analysis_required: true, creates_research_runs: false, automatic_canary: false, automatic_fallback: false, external_call_performed: false },
          },
          unavailable: false,
        });
        const providerMarkup = subject.researchProviderControlMarkup(nullProvider);
        const unboundRegistry = {
          ok: true,
          can_resolve: true,
          candidate: { candidate_hash: hash, category_name: "<script>Новая</script>", definition: "Проверяемые границы новой категории" },
          categories: [{ category_key: otherId, canonical_name: "Сохранённая", definition: "Существующая граница" }],
          trend_timeline: [{ signal_key: "hook.problem_first", canonical_label: "Проблема сначала", direction: "growing", previous_direction: "declining", comparison_mode: "canonical_reset", direction_changed: false, potential_contradiction: false }],
          trend_velocity: [{
            snapshot_id: "40000000-0000-4000-8000-000000000001",
            previous_snapshot_id: "40000000-0000-4000-8000-000000000002",
            run_id: "50000000-0000-4000-8000-000000000001",
            observed_at: "2026-08-03T12:00:00Z",
            previous_observed_at: "2026-07-20T12:00:00Z",
            category_key: otherId,
            signal_key: "hook.problem_first",
            canonical_label: "Проблема сначала",
            definition_version: "approved-structural-support-velocity-v1",
            comparison_mode: "comparable",
            current_present: true,
            previous_present: true,
            current_direction: "growing",
            previous_direction: "stable",
            current_source_count: 3,
            previous_source_count: 1,
            current_total_source_count: 5,
            previous_total_source_count: 4,
            current_support_bps: 6000,
            previous_support_bps: 2500,
            support_delta_bps: 3500,
            elapsed_seconds: 1209600,
            support_velocity_bps_per_30d: 7500,
            lineage_hash: "d".repeat(64),
            event_hash: "e".repeat(64),
            claim_allowed: true,
            support_state: "support_breadth_increasing",
            recommended_next_step: "review_support_velocity",
          }],
          guidance: {
            status: "needs_user_decision",
            paid_provider_action: false,
            trend_velocity: {
              status: "review_support_velocity",
              recommended_next_step: "review_support_velocity",
              metric_kind: "approved_structural_evidence_support_not_performance",
              minimum_interval_hours: 72,
              human_correction_stage: "trends",
            },
          },
        };
        const unbound = subject.normalizeResearchMarketRegistry({ registry: unboundRegistry });
        const wrongDeltaRegistry = structuredClone(unboundRegistry);
        wrongDeltaRegistry.trend_velocity[0].support_delta_bps = 3499;
        const stringCountRegistry = structuredClone(unboundRegistry);
        stringCountRegistry.trend_velocity[0].current_source_count = "3";
        const wrongStateRegistry = structuredClone(unboundRegistry);
        wrongStateRegistry.trend_velocity[0].support_state = "support_breadth_stable";
        const absentCountRegistry = structuredClone(unboundRegistry);
        Object.assign(absentCountRegistry.trend_velocity[0], {
          comparison_mode: "category_reset",
          previous_present: false,
          previous_direction: null,
          support_delta_bps: null,
          support_velocity_bps_per_30d: null,
          claim_allowed: false,
          support_state: "no_velocity_claim",
          recommended_next_step: "establish_new_category_baseline",
        });
        Object.assign(absentCountRegistry.guidance.trend_velocity, {
          status: "establish_new_category_baseline",
          recommended_next_step: "establish_new_category_baseline",
        });
        const zeroIntervalRegistry = structuredClone(unboundRegistry);
        Object.assign(zeroIntervalRegistry.trend_velocity[0], {
          previous_observed_at: "2026-08-03T12:00:00Z",
          comparison_mode: "interval_too_short",
          support_delta_bps: null,
          elapsed_seconds: 0,
          support_velocity_bps_per_30d: null,
          claim_allowed: false,
          support_state: "no_velocity_claim",
          recommended_next_step: "wait_for_minimum_interval",
        });
        Object.assign(zeroIntervalRegistry.guidance.trend_velocity, {
          status: "wait_for_minimum_interval",
          recommended_next_step: "wait_for_minimum_interval",
        });
        const categoryResetRegistry = structuredClone(unboundRegistry);
        Object.assign(categoryResetRegistry.trend_velocity[0], {
          comparison_mode: "category_reset",
          previous_present: false,
          previous_direction: null,
          previous_source_count: 0,
          previous_support_bps: 0,
          support_delta_bps: null,
          support_velocity_bps_per_30d: null,
          claim_allowed: false,
          support_state: "no_velocity_claim",
          recommended_next_step: "establish_new_category_baseline",
        });
        Object.assign(categoryResetRegistry.guidance.trend_velocity, {
          status: "establish_new_category_baseline",
          recommended_next_step: "establish_new_category_baseline",
        });
        const microsecondIntervalRegistry = structuredClone(zeroIntervalRegistry);
        Object.assign(microsecondIntervalRegistry.trend_velocity[0], {
          previous_observed_at: "2026-08-03T12:00:00.000999Z",
          observed_at: "2026-08-03T12:00:01.000001Z",
          elapsed_seconds: 0,
        });
        const mixedVelocityRegistry = structuredClone(unboundRegistry);
        const invalidMixedEvent = structuredClone(
          mixedVelocityRegistry.trend_velocity[0],
        );
        invalidMixedEvent.snapshot_id = "40000000-0000-4000-8000-000000000003";
        invalidMixedEvent.event_hash = "f".repeat(64);
        invalidMixedEvent.support_delta_bps = 3499;
        mixedVelocityRegistry.trend_velocity.unshift(invalidMixedEvent);
        const mixedVelocity = subject.normalizeResearchMarketRegistry({
          registry: mixedVelocityRegistry,
        });
        const mixedVelocityMarkup = subject.researchMarketCategoryMarkup(
          mixedVelocity,
          { runId: "run-1" },
        );
        const bound = subject.normalizeResearchMarketRegistry({ registry: {
          ok: true,
          can_resolve: true,
          current_binding: { category_key: currentId, canonical_name: "Текущая", definition: "Текущая граница" },
          candidate: { candidate_hash: hash, category_name: "Новая", definition: "Проверяемые границы новой категории" },
          categories: [
            { category_key: currentId, canonical_name: "Текущая", definition: "Текущая граница" },
            { category_key: otherId, canonical_name: "Другая", definition: "Другая граница" },
          ],
          trend_timeline: [],
          guidance: { status: "ready", paid_provider_action: false },
        }});
        const unboundMarkup = subject.researchMarketCategoryMarkup(unbound, { runId: "run-1" });
        const boundMarkup = subject.researchMarketCategoryMarkup(bound, { runId: "run-1" });
        return {
          runControlIsNull: nullProvider.runControl === null,
          plannedProviderShownAsSelected: providerMarkup.includes("YouTube Data"),
          escapedCandidate: unboundMarkup.includes("&lt;script&gt;Новая&lt;/script&gt;") && !unboundMarkup.includes("<script>"),
          unboundActions: [unboundMarkup.includes('data-market-category-action="bind_existing"'), unboundMarkup.includes('data-market-category-action="create_and_bind"')],
          boundActions: [boundMarkup.includes('data-market-category-action="reclassify"'), boundMarkup.includes('data-market-category-action="create_and_reclassify"')],
          splitForms: unboundMarkup.includes('id="product-research-market-category-existing-form"') && unboundMarkup.includes('id="product-research-market-category-create-form"') && (unboundMarkup.match(/product-research-market-category-form/g) || []).length === 2,
          exactSearch: unboundMarkup.includes('id="product-research-market-category-search-form"') && unboundMarkup.includes("точное каноническое название"),
          currentIdLeaked: boundMarkup.includes(currentId),
          otherIdSelectable: boundMarkup.includes(`value="${otherId}"`),
          resetLabel: unboundMarkup.includes("новая база") && !unboundMarkup.includes("снижается → растёт"),
          velocity: unbound.trendVelocity.length === 1
            && unboundMarkup.includes("25,0% → 60,0%")
            && unboundMarkup.includes("+35,0 п.п.")
            && unboundMarkup.includes("+75,0 п.п. / 30 дней")
            && unboundMarkup.includes('data-action="focus-research-trends-stage"')
            && unboundMarkup.includes("не просмотры, не продажи"),
          corruptVelocityFailsClosed: [
            wrongDeltaRegistry,
            stringCountRegistry,
            wrongStateRegistry,
            absentCountRegistry,
          ].every((registry) => subject.normalizeResearchMarketRegistry({ registry }).available === false),
          zeroIntervalAccepted: subject.normalizeResearchMarketRegistry({
            registry: zeroIntervalRegistry,
          }).trendVelocity[0].elapsedSeconds === 0,
          categoryResetNewSignalAccepted: subject.normalizeResearchMarketRegistry({
            registry: categoryResetRegistry,
          }).trendVelocity[0].comparisonMode === "category_reset",
          microsecondIntervalAccepted: subject.normalizeResearchMarketRegistry({
            registry: microsecondIntervalRegistry,
          }).trendVelocity[0].elapsedSeconds === 0,
          mixedVelocityHidden: mixedVelocity.available === false
            && mixedVelocity.trendVelocity.length === 0
            && !mixedVelocityMarkup.includes("+75,0 п.п. / 30 дней"),
          noPaidCopy: boundMarkup.includes("не запускает новый анализ") && boundMarkup.includes("не обращается к платному провайдеру"),
        };
        """,
    )

    assert result == {
        "runControlIsNull": True,
        "plannedProviderShownAsSelected": False,
        "escapedCandidate": True,
        "unboundActions": [True, True],
        "boundActions": [True, True],
        "splitForms": True,
        "exactSearch": True,
        "currentIdLeaked": False,
        "otherIdSelectable": True,
        "resetLabel": True,
        "velocity": True,
        "corruptVelocityFailsClosed": True,
        "zeroIntervalAccepted": True,
        "categoryResetNewSignalAccepted": True,
        "microsecondIntervalAccepted": True,
        "mixedVelocityHidden": True,
        "noPaidCopy": True,
    }


def test_category_reset_suppresses_legacy_watchlist_contradictions() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const monitor = subject.normalizeResearchWatchlist({
          watchlist: { id: "watch-1", status: "active", snapshot_count: 1 },
          snapshots: [{
            id: "snapshot-reset",
            observed_at: "2026-08-03T10:00:00Z",
            change_set: {
              comparison_mode: "legacy",
              contradiction_count: 1,
              contradictions: ["Старое ложное противоречие"],
            },
          }],
        });
        const markup = subject.researchWatchlistMarkup(monitor, {
          runId: "run-1",
          categoryResetSnapshotIds: ["snapshot-reset"],
        });
        return {
          baseline: markup.includes("этот снимок стал новой базой"),
          noLegacyContradiction: !markup.includes("Старое ложное противоречие"),
          zeroSummary: markup.includes("<small>Противоречия</small><strong>0</strong>"),
        };
        """,
    )
    assert result == {
        "baseline": True,
        "noLegacyContradiction": True,
        "zeroSummary": True,
    }


def test_market_resolver_is_append_only_and_app_never_auto_retries_decision() -> None:
    sql = _read(MARKET_SQL_PATH)
    resolver = _sql_function(sql, "creator_resolve_research_market_category")
    app = _read(APP_PATH)
    api = _read(API_PATH)
    api_resolver = api[
        api.index("async resolveResearchMarketCategory") :
        api.index("searchResearchMarketCategories")
    ]
    handler = app[
        app.index("async function submitProductResearchMarketCategory") :
        app.index("async function submitProductResearchWatchlist")
    ]

    for action in (
        "bind_existing",
        "create_and_bind",
        "reclassify",
        "create_and_reclassify",
    ):
        assert action in resolver
    assert "previous_binding_id" in resolver
    assert "binding_version" in resolver
    assert "research_market_category_candidate_stale" in resolver
    assert "confirmation" in resolver
    assert "insert into content_factory.product_research_runs" not in resolver.casefold()
    assert "creator_start_product_research" not in resolver

    assert "state.api.resolveResearchMarketCategory(runId, options)" in handler
    assert "applyResearchMarketCategoryResolution" in handler
    assert "statusRefreshUnavailable" in handler
    assert handler.index("resolveResearchMarketCategory") < handler.index("productResearchStatus")
    assert "state.api.startProductResearch" not in handler
    assert "invokeProductResearch" not in handler
    assert "paid_provider_action: false" in handler
    assert "compliance_category_changed: false" in handler
    assert handler.count("resolveResearchMarketCategory") == 1
    assert "return this.mutate(RPC.resolveResearchMarketCategory, payload)" in api_resolver
    assert "productResearchStatus" not in api_resolver

    new_research_handler = app[
        app.index('if (action === "new-product-research")') :
        app.index('if (action === "reset-generation-filters")')
    ]
    assert 'productResearchStatusKind(state.productResearch.record?.status) === "active"' in new_research_handler
    assert new_research_handler.index("productResearchStatusKind") < new_research_handler.index("clearProductResearchRunId()")
