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
WORKER_PATH = ROOT / "supabase/functions/creator-background-worker/index.ts"
WATCHLIST_MIGRATION_PATH = (
    ROOT / "supabase/migrations/202608030002_research_watchlist_memory.sql"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _all_migrations() -> str:
    return "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "supabase/migrations").glob("*.sql"))
    )


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


def _typescript_function_containing(source: str, needle: str) -> tuple[str, str]:
    needle_index = source.index(needle)
    headers = list(
        re.finditer(
            r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
            source,
        )
    )
    for index, header in enumerate(headers):
        start = header.start()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(source)
        if start <= needle_index < end:
            return header.group(1), source[start:end]
    raise AssertionError(f"{needle!r} must live in an isolated named worker function")


def _run_module(path: Path, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for executable watchlist contracts")
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


def test_watchlist_sql_keeps_monitoring_separate_from_paid_research_runs() -> None:
    sql = _all_migrations()
    configure = _sql_function(sql, "creator_configure_research_watchlist")
    status = _sql_function(sql, "creator_research_watchlist_status")
    propose = _sql_function(
        _read(WATCHLIST_MIGRATION_PATH),
        "system_propose_due_research_refreshes",
    )

    configure_folded = re.sub(r"\s+", " ", configure).casefold()
    status_folded = re.sub(r"\s+", " ", status).casefold()
    propose_folded = re.sub(r"\s+", " ", propose).casefold()

    for action in ("enable", "update", "pause", "resume"):
        assert action in configure_folded
    for contract in (
        "refresh_interval_days",
        "security definer",
        "current_profile_id",
        "organization",
        "approved",
    ):
        assert contract in configure_folded

    for result_field in (
        "watchlist",
        "snapshots",
        "proposal",
        "freshness",
        "change",
        "contradiction",
        "guidance",
    ):
        assert result_field in status_folded
    assert "security definer" in status_folded
    assert "current_profile_id" in status_folded
    assert "organization" in status_folded

    assert "security definer" in propose_folded
    assert "proposal" in propose_folded
    assert "product_research_runs" not in propose_folded
    assert "creator_start_product_research" not in propose_folded
    assert "creator-product-research" not in propose_folded

    grants = re.sub(r"\s+", " ", sql).casefold()
    for creator_rpc in (
        "creator_configure_research_watchlist",
        "creator_research_watchlist_status",
    ):
        assert re.search(
            rf"grant execute on function public\.{creator_rpc}\s*\([^;]*\)\s*to authenticated",
            grants,
        )
    assert re.search(
        r"grant execute on function public\.system_propose_due_research_refreshes\s*\([^;]*\)\s*to service_role",
        grants,
    )
    assert not re.search(
        r"grant execute on function public\.system_propose_due_research_refreshes\s*\([^;]*\)\s*to (?:authenticated|anon|public)",
        grants,
    )


def test_browser_api_reads_monitor_status_and_requires_explicit_actions() -> None:
    result = _run_module(
        API_PATH,
        """
        const calls = [];
        const api = Object.create(subject.CreatorApi.prototype);
        api.withOrganization = (payload) => ({
          ...payload,
          organization_id: "00000000-0000-4000-8000-000000000001",
        });
        api.call = async (rpc, payload) => {
          calls.push({ kind: "call", rpc, payload });
          if (rpc === "creator_product_research_status") {
            return { run: { id: payload.run_id, status: "approved" } };
          }
          if (rpc === "creator_research_watchlist_status") {
            return {
              watchlist: {
                id: "watch-1",
                status: "active",
                freshness: "due",
                refresh_interval_days: 14,
              },
              snapshots: [{ id: "snapshot-1" }],
              proposal: { id: "proposal-1", status: "open" },
              guidance: { code: "refresh_due" },
            };
          }
          if (rpc === "creator_research_provider_status") {
            return { providers: [], run_control: null, controls: {} };
          }
          if (rpc === "creator_research_market_category_registry") {
            return { categories: [], trend_timeline: [], guidance: {} };
          }
          throw new Error(`unexpected call: ${rpc}`);
        };
        api.mutate = async (rpc, payload) => {
          calls.push({ kind: "mutate", rpc, payload });
          return { ok: true };
        };

        const status = await api.productResearchStatus(
          "10000000-0000-4000-8000-000000000001",
        );
        await api.configureResearchWatchlist(
          "10000000-0000-4000-8000-000000000001",
          { action: "enable", refresh_interval_days: 7 },
        );
        await api.configureResearchWatchlist(
          "10000000-0000-4000-8000-000000000001",
          { action: "update", refresh_interval_days: 21 },
        );
        await api.configureResearchWatchlist(
          "10000000-0000-4000-8000-000000000001",
          { action: "pause" },
        );
        await api.configureResearchWatchlist(
          "10000000-0000-4000-8000-000000000001",
          { action: "resume", refresh_interval_days: 14 },
        );

        const rejected = [];
        for (const options of [
          { action: "run_paid_refresh", refresh_interval_days: 14 },
          { action: "enable", refresh_interval_days: 1 },
        ]) {
          try {
            await api.configureResearchWatchlist(
              "10000000-0000-4000-8000-000000000001",
              options,
            );
          } catch (error) {
            rejected.push(String(error?.code || ""));
          }
        }
        return {
          envelope: {
            runStatus: status.run.status,
            watchlistId: status.watchlist.id,
            history: status.watchlist_history.length,
            proposalId: status.watchlist_proposal.id,
            guidanceCode: status.watchlist_guidance.code,
          },
          mutations: calls
            .filter((item) => item.kind === "mutate")
            .map((item) => ({ rpc: item.rpc, payload: item.payload })),
          statusRpcs: [...new Set(calls
            .filter((item) => item.kind === "call")
            .map((item) => item.rpc))].sort(),
          rejected,
        };
        """,
    )

    assert result["envelope"] == {
        "runStatus": "approved",
        "watchlistId": "watch-1",
        "history": 1,
        "proposalId": "proposal-1",
        "guidanceCode": "refresh_due",
    }
    assert result["statusRpcs"] == [
        "creator_product_research_status",
        "creator_research_category_learning_status",
        "creator_research_market_category_registry",
        "creator_research_outcome_learning_scopes",
        "creator_research_provider_status",
        "creator_research_watchlist_status",
        "creator_research_youtube_overview",
    ]
    assert result["mutations"] == [
        {
            "rpc": "creator_configure_research_watchlist",
            "payload": {
                "run_id": "10000000-0000-4000-8000-000000000001",
                "action": "enable",
                "refresh_interval_days": 7,
            },
        },
        {
            "rpc": "creator_configure_research_watchlist",
            "payload": {
                "run_id": "10000000-0000-4000-8000-000000000001",
                "action": "update",
                "refresh_interval_days": 21,
            },
        },
        {
            "rpc": "creator_configure_research_watchlist",
            "payload": {
                "run_id": "10000000-0000-4000-8000-000000000001",
                "action": "pause",
            },
        },
        {
            "rpc": "creator_configure_research_watchlist",
            "payload": {
                "run_id": "10000000-0000-4000-8000-000000000001",
                "action": "resume",
                "refresh_interval_days": 14,
            },
        },
    ]
    assert result["rejected"] == [
        "research_watchlist_action_invalid",
        "research_watchlist_interval_invalid",
    ]


def test_approved_result_normalizes_and_renders_watchlist_history() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const base = {
          run: {
            id: "10000000-0000-4000-8000-000000000001",
            status: "approved",
            product_name: "Тестовый товар",
          },
          latest_draft: {
            id: "20000000-0000-4000-8000-000000000001",
            status: "approved",
            brief: {
              summary: "Утверждённый результат",
              scenarios: [{}, {}, {}],
              guidance: { status: "ready_for_brief" },
            },
          },
          approval: {
            status: "approved",
            draft_id: "20000000-0000-4000-8000-000000000001",
          },
          watchlist: {
            id: "watch-1",
            status: "active",
            freshness: "stale",
            refresh_interval_days: 14,
            last_snapshot_at: "2026-07-20T10:00:00.000Z",
            next_refresh_at: "2026-08-03T10:00:00.000Z",
            snapshot_count: 2,
            version: 3,
          },
          watchlist_history: [{
            id: "snapshot-old",
            observed_at: "2026-07-06T10:00:00.000Z",
            source_count: 2,
            change_set: { baseline: true },
          }, {
            id: "snapshot-new",
            observed_at: "2026-07-20T10:00:00.000Z",
            source_count: 4,
            change_set: {
              has_changes: true,
              has_potential_contradiction: true,
              contradiction_count: 2,
              category: { changed: false },
              competitors: {
                added_names: ["Конкурент Beta"],
                removed_names: [],
                changed_names: [],
              },
              trends: {
                added_signals: ["Демонстрационный хук"],
                removed_signals: [],
                changed_signals: [],
                direction_changes: [{
                  signal: "Сравнение в кадре",
                  from: "growing",
                  to: "declining",
                  contradiction: true,
                }],
                direction_contradictions: [{
                  signal: "Источники расходятся",
                  from: "growing",
                  to: "declining",
                }],
                contradiction_count: 2,
              },
            },
          }],
          watchlist_proposal: {
            id: "proposal-1",
            status: "open",
            reason_code: "refresh_due",
            due_at: "2026-08-03T10:00:00.000Z",
          },
          watchlist_guidance: {
            status: "needs_user_decision",
            code: "refresh_due",
            title: "Решите, нужен ли свежий снимок",
            reason: "Изменение остаётся гипотезой до новой проверки.",
            suggested_actions: ["Подтвердить новый анализ"],
          },
        };
        const active = subject.normalizeProductResearch(base);
        const activeHtml = subject.productResearchResultMarkup(active);
        const paused = subject.normalizeProductResearch({
          ...base,
          watchlist: { ...base.watchlist, status: "paused", freshness: "paused" },
        });
        const pausedHtml = subject.productResearchResultMarkup(paused);
        const disabled = subject.normalizeProductResearch({
          ...base,
          watchlist: null,
          watchlist_history: [],
          watchlist_proposal: null,
          watchlist_guidance: null,
        });
        const disabledHtml = subject.productResearchResultMarkup(disabled);
        const actionPattern = (action) => new RegExp(
          `(?:data-[\\w-]+|name|value)=["'][^"']*${action}[^"']*["']`,
          "i",
        );
        const lowerHtml = activeHtml.toLocaleLowerCase("ru");
        return {
          normalized: {
            freshness: active.watchlist.freshness,
            historyOrder: active.watchlist.snapshots.map((item) => item.id),
            material: active.watchlist.snapshots[0].change.material,
            contradictionCount:
              active.watchlist.snapshots[0].change.contradictionCount,
            paidConfirmation:
              active.watchlist.guidance.paidRefreshRequiresConfirmation,
          },
          actions: {
            enable: actionPattern("enable").test(disabledHtml),
            update: actionPattern("update").test(activeHtml),
            pause: actionPattern("pause").test(activeHtml),
            resume: actionPattern("resume").test(pausedHtml),
          },
          visible: {
            freshness: /свежест|устарел/.test(lowerHtml),
            history: /истори|снимк/.test(lowerHtml),
            change: activeHtml.includes("Конкурент Beta")
              || activeHtml.includes("Демонстрационный хук"),
            contradiction: /противореч|расходятся/.test(lowerHtml),
            hypothesis: lowerHtml.includes("гипотез"),
            paidConfirmation: lowerHtml.includes("новый платный анализ")
              && lowerHtml.includes("только после подтвержден"),
          },
        };
        """,
    )

    assert result == {
        "normalized": {
            "freshness": "stale",
            "historyOrder": ["snapshot-new", "snapshot-old"],
            "material": True,
            "contradictionCount": 2,
            "paidConfirmation": True,
        },
        "actions": {
            "enable": True,
            "update": True,
            "pause": True,
            "resume": True,
        },
        "visible": {
            "freshness": True,
            "history": True,
            "change": True,
            "contradiction": True,
            "hypothesis": True,
            "paidConfirmation": True,
        },
    }


def test_ui_routes_watchlist_controls_without_starting_paid_analysis() -> None:
    app = _read(APP_PATH)
    view = _read(VIEW_PATH)

    assert "configureResearchWatchlist" in app
    assert 'safeWorkspaceRouteEntityId("research")' in app
    assert 'navigate("/workspace/research", true)' in app
    assert "#/workspace/research?research=" in _all_migrations()
    for action in ("enable", "update", "pause", "resume"):
        assert re.search(
            rf"(?:data-[\w-]+|value)=[\"'][^\"']*{action}[^\"']*[\"']",
            view,
            re.IGNORECASE,
        )

    call_index = app.index("configureResearchWatchlist")
    start = max(0, app.rfind("async function", 0, call_index))
    next_function = app.find("async function", call_index + 1)
    end = len(app) if next_function < 0 else next_function
    handler = app[start:end]
    assert "startProductResearch" not in handler
    assert "invokeProductResearch" not in handler
    assert "paid_analysis_ack" not in handler


def test_canonical_signal_upgrade_is_rendered_as_a_new_baseline() -> None:
    result = _run_module(
        VIEW_PATH,
        """
        const monitor = subject.normalizeResearchWatchlist({
          watchlist: {
            id: "watch-canonical",
            status: "active",
            freshness: "fresh",
            refresh_interval_days: 14,
            snapshot_count: 2,
          },
          snapshots: [{
            id: "snapshot-canonical",
            observed_at: "2026-08-03T10:00:00.000Z",
            change_set: {
              has_changes: true,
              trends: {
                comparison_mode: "canonical_reset",
                added_signals: [],
                removed_signals: [],
                contradiction_count: 0,
              },
            },
          }],
        });
        const html = subject.researchWatchlistMarkup(monitor, {
          runId: "10000000-0000-4000-8000-000000000001",
        });
        return {
          comparisonMode: monitor.snapshots[0].change.comparisonMode,
          canonicalBaseline: html.includes("Структурные ID трендов включены впервые"),
          noFalseAddition: !html.includes("Появились сигналы:"),
        };
        """,
    )
    assert result == {
        "comparisonMode": "canonical_reset",
        "canonicalBaseline": True,
        "noFalseAddition": True,
    }


def test_background_worker_only_requests_due_refresh_proposals() -> None:
    worker = _read(WORKER_PATH)
    function_name, proposal_function = _typescript_function_containing(
        worker,
        "system_propose_due_research_refreshes",
    )

    rpc_names = re.findall(
        r"\.rpc\(\s*[\"'`]([^\"'`]+)[\"'`]",
        proposal_function,
    )
    assert rpc_names == ["system_propose_due_research_refreshes"]
    assert worker.count(function_name) >= 2, "the proposal-only helper must be invoked"
    for forbidden in (
        ".from(",
        ".insert(",
        "creator_start_product_research",
        "creator-product-research",
        "product_research_runs",
    ):
        assert forbidden not in proposal_function

    assert not re.search(
        r"\.from\(\s*[\"'`]product_research_runs[\"'`]\s*\)\s*\.insert\(",
        worker,
        re.IGNORECASE | re.DOTALL,
    )
