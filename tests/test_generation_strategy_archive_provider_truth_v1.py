import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "web" / "app" / "app.js"
API_PATH = ROOT / "web" / "app" / "supabase-api.js"
PORTAL_PATH = ROOT / "web" / "app" / "portal-experience.js"
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608200004_generation_strategy_archive_provider_truth_v1.sql"
)

APP = APP_PATH.read_text(encoding="utf-8")
API = API_PATH.read_text(encoding="utf-8")
PORTAL = PORTAL_PATH.read_text(encoding="utf-8")
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def _node(script: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for archive provider regressions")
    result = subprocess.run(
        [node, "-"],
        input=script,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _node_module(module_source: str, body: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for archive provider regressions")
    with tempfile.TemporaryDirectory() as temporary_directory:
        module_directory = Path(temporary_directory)
        (module_directory / "subject.mjs").write_text(
            module_source,
            encoding="utf-8",
        )
        (module_directory / "contract.mjs").write_text(
            "import * as subject from './subject.mjs';\n"
            f"const payload = await (async () => {{\n{body}\n}})();\n"
            "process.stdout.write(JSON.stringify(payload));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=module_directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _provider_runtime_source() -> str:
    execution = _between(
        APP,
        "function generationStrategyExecutionArchiveDetails",
        "function generationSelectionArchiveMarkup",
    )
    details = _between(
        APP,
        "function generationBatchDetails(item)",
        "function generationDeepLinkStatusKind",
    )
    classifier = _between(
        APP,
        "function generationDeepLinkStatusKind",
        "function mergeGenerationDeepLinkedBatch",
    )
    return "\n".join((execution, details, classifier))


def test_append_only_archive_patch_uses_batch_then_signed_receipt_provider() -> None:
    assert MIGRATION_PATH.is_file()
    migration_paths = sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
    assert len(
        list((ROOT / "supabase" / "migrations").glob("202608200004_*.sql"))
    ) == 1
    for later_path in (
        path for path in migration_paths if path.name > MIGRATION_PATH.name
    ):
        assert "creator_generation_archive_pre_execution_v1(jsonb)" not in (
            later_path.read_text(encoding="utf-8")
        )
    for marker in (
        "creator_generation_archive_pre_execution_v1(jsonb)",
        "case when strategy_snapshot.id is not null then batch.provider else launch.provider end",
        "provider_value not in ('all', 'runway', 'google', 'fal')",
        "coalesce(launch.generation_job_id,strategy_snapshot.generation_job_id)asgeneration_job_id",
        "'generation_job_id', page.generation_job_id",
        "'provider', receipt_row.provider",
        "receipt_row.provider is distinct from batch_value ->> 'provider'",
        "generation_strategy_archive_provider_mismatch",
        "archive_provider_patch_anchor_invalid",
        "base_compact := lower(regexp_replace(",
        "'[[:space:]]+'",
    ):
        assert marker in MIGRATION
    assert "p_expected_hits" in MIGRATION
    assert "begin;" == MIGRATION.splitlines()[0]
    assert MIGRATION.rstrip().endswith("commit;")


def test_archive_provider_filter_contract_is_fal_aware_end_to_end() -> None:
    assert 'new Set(["all", "runway", "google", "fal"])' in API
    assert 'new Set(["all", "runway", "google", "fal"])' in PORTAL
    assert '<option value="fal" ${filters.provider === "fal"' in APP
    assert "fal (Pika / Kling)" in APP


def test_fal_archive_filter_normalizes_and_reaches_rpc_payload() -> None:
    normalized = _node_module(
        PORTAL,
        """
        return subject.normalizeGenerationFilters({ provider: " FAL " });
        """,
    )
    assert normalized["provider"] == "fal"

    result = _node_module(
        API,
        """
        const calls = [];
        const rpcClient = {
          rpc: async (functionName, args) => {
            calls.push({ functionName, args });
            return { data: { ok: true, batches: [] }, error: null };
          },
        };
        const api = new subject.CreatorApi({ schema: () => rpcClient }, {
          RPC_SCHEMA: "public",
          STORAGE_BUCKET: "creator-private",
        });
        api.organizationId = "organization-1";
        await api.generationArchive({
          projectId: "11111111-1111-4111-8111-111111111111",
          provider: " FAL ",
        });
        return calls[0];
        """,
    )
    assert result == {
        "functionName": "creator_generation_archive",
        "args": {
            "p_payload": {
                "period": "4w",
                "status": "all",
                "page_size": 50,
                "project_id": "11111111-1111-4111-8111-111111111111",
                "provider": "fal",
                "organization_id": "organization-1",
            }
        },
    }


def test_provider_authority_precedence_and_route_labels_execute() -> None:
    runtime = _provider_runtime_source()
    result = _node(
        f"""
        const JOB = 'e62235c7-57c5-473f-88bf-c33bb319ee04';
        const HASH = 'a'.repeat(64);
        const state = {{ realGenerationResults: new Map() }};
        function firstFiniteNumber(...values) {{
          for (const value of values) {{
            if (value === null || value === undefined || value === '') continue;
            const number = Number(value);
            if (Number.isFinite(number)) return number;
          }}
          return null;
        }}
        function normalizeBoolean(value) {{
          return value === true || value === 'true' || value === 1 || value === '1';
        }}
        function contentReviewUuid(value) {{
          return /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-5][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/u
            .test(String(value || '').trim().toLowerCase());
        }}
        function listFrom(data, ...keys) {{
          for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
          return [];
        }}
        {runtime}
        const selection = {{
          version: '2026-08-14.v1', strategy_id: 'viral_product_swap',
          recipe_version: '2026-06', duration_seconds: 5,
          resolution: '720p', audio: false,
        }};
        const price = (provider, pricingVersion) => ({{
          version: 'generation-strategy-price-snapshot-v1',
          strategy_id: 'viral_product_swap', provider,
          recipe: 'product_swap', catalog_version: '2026-08-14.v1',
          recipe_version: '2026-06', pricing_version: pricingVersion,
          display_only: true, requires_fresh_server_price: true,
          price_hash: null, spend_confirmation: null,
          estimated_cost_minor: 85, estimated_credits: 85,
        }});
        const strategyRow = (provider, pricingVersion) => ({{
          mode: 'real', status: 'starting', provider: 'runway',
          generation_job_id: JOB, generation_selection_snapshot: null,
          strategy_id: 'viral_product_swap',
          generation_strategy_snapshot_version: 'generation-job-strategy-snapshot-v1',
          generation_strategy_snapshot_hash: HASH,
          generation_strategy_snapshot: {{
            version: 'generation-job-strategy-snapshot-v1',
            generation_job_id: JOB,
            strategy: {{
              strategy_id: 'viral_product_swap', source_basis: 'exact_source_video',
              role_assets: [],
            }},
          }},
          generation_strategy_execution_selection: selection,
          generation_strategy_price_reference: price(provider, pricingVersion),
          parameters: {{ job_id: JOB }},
        }});
        const falRow = strategyRow('fal', 'fal-usd-per-second-2026-08-18.v1');
        const frozenFal = generationBatchDetails(falRow).provider;
        state.realGenerationResults.set(JOB, {{ job: {{ provider: 'fal' }} }});
        const cachedFal = generationBatchDetails(falRow).provider;
        state.realGenerationResults.set(JOB, {{ job: {{ provider: 'runway' }} }});
        const signedConflict = generationBatchDetails(falRow).provider;
        state.realGenerationResults.clear();
        const runwayRow = strategyRow(
          'runway', 'runway-recipe-credits-2026-08-14.v1',
        );
        const preservedRunway = generationBatchDetails(runwayRow).provider;
        const routeMismatch = generationStrategyExecutionArchiveDetails(
          {{
            ...runwayRow,
            generation_strategy_price_reference: price(
              'runway', 'fal-usd-per-second-2026-08-18.v1',
            ),
          }},
          generationBatchDetails(runwayRow).strategy,
        );
        process.stdout.write(JSON.stringify({{
          frozenFal, cachedFal, signedConflict, preservedRunway,
          routeMismatchRejected: routeMismatch === null,
          labels: {{
            pika: generationStrategyExecutionPublicLabel({{
              provider: 'fal', pricingVersion: 'fal-usd-per-run-2026-08-18.v1',
              recipe: 'product_swap',
            }}),
            kling: generationStrategyExecutionPublicLabel({{
              provider: 'fal', pricingVersion: 'fal-usd-per-second-2026-08-18.v1',
              recipe: 'product_swap',
            }}),
            runway: generationStrategyExecutionPublicLabel({{
              provider: 'runway',
              pricingVersion: 'runway-recipe-credits-2026-08-14.v1',
              recipe: 'product_swap',
            }}),
            unknown: generationStrategyExecutionPublicLabel({{
              provider: 'fal', pricingVersion: 'unknown', recipe: 'product_swap',
            }}),
          }},
        }}));
        """
    )
    assert result == {
        "frozenFal": "fal",
        "cachedFal": "fal",
        "signedConflict": "",
        "preservedRunway": "runway",
        "routeMismatchRejected": True,
        "labels": {
            "pika": "Pika Swaps",
            "kling": "Kling O3 Pro",
            "runway": "Runway Product Swap",
            "unknown": "",
        },
    }


def test_deep_link_status_contract_classification_executes_all_states() -> None:
    runtime = _provider_runtime_source()
    result = _node(
        f"""
        const JOB = 'e62235c7-57c5-473f-88bf-c33bb319ee04';
        const HASH = 'b'.repeat(64);
        const state = {{ realGenerationResults: new Map() }};
        function firstFiniteNumber(...values) {{
          for (const value of values) {{
            if (value === null || value === undefined || value === '') continue;
            const number = Number(value);
            if (Number.isFinite(number)) return number;
          }}
          return null;
        }}
        function normalizeBoolean(value) {{ return value === true; }}
        function contentReviewUuid(value) {{
          return /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-5][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/u
            .test(String(value || '').trim().toLowerCase());
        }}
        function listFrom(data, ...keys) {{
          for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
          return [];
        }}
        {runtime}
        const strategy = {{
          mode: 'real', status: 'starting', provider: 'fal',
          generation_job_id: JOB, generation_selection_snapshot: null,
          strategy_id: 'viral_product_swap',
          generation_strategy_snapshot_version: 'generation-job-strategy-snapshot-v1',
          generation_strategy_snapshot_hash: HASH,
          generation_strategy_snapshot: {{
            version: 'generation-job-strategy-snapshot-v1',
            generation_job_id: JOB,
            strategy: {{
              strategy_id: 'viral_product_swap', source_basis: 'exact_source_video',
              role_assets: [],
            }},
          }},
          generation_strategy_execution_selection: {{
            version: '2026-08-14.v1', strategy_id: 'viral_product_swap',
            recipe_version: '2026-06', duration_seconds: 5,
            resolution: '720p', audio: false,
          }},
          generation_strategy_price_reference: {{
            version: 'generation-strategy-price-snapshot-v1',
            strategy_id: 'viral_product_swap', provider: 'fal',
            recipe: 'product_swap', catalog_version: '2026-08-14.v1',
            recipe_version: '2026-06',
            pricing_version: 'fal-usd-per-second-2026-08-18.v1',
            display_only: true, requires_fresh_server_price: true,
            price_hash: null, spend_confirmation: null,
            estimated_cost_minor: 85, estimated_credits: 85,
          }},
          parameters: {{ job_id: JOB }},
        }};
        const legacy = {{
          mode: 'real', provider: 'runway', generation_job_id: JOB,
          generation_strategy_snapshot: null,
          generation_selection_snapshot: null,
          parameters: {{ job_id: '00000000-0000-4000-8000-000000000000' }},
        }};
        const malformed = {{
          ...strategy,
          generation_strategy_snapshot_hash: 'bad',
        }};
        process.stdout.write(JSON.stringify({{
          strategy: generationDeepLinkStatusKind({{ batches: [strategy] }}, JOB, true),
          legacy: generationDeepLinkStatusKind({{ batches: [legacy] }}, JOB, true),
          missing: generationDeepLinkStatusKind({{ batches: [] }}, JOB, true),
          malformed: generationDeepLinkStatusKind({{ batches: [malformed] }}, JOB, true),
          rejectedArchive: generationDeepLinkStatusKind(
            {{ batches: [strategy] }}, JOB, false,
          ),
          duplicate: generationDeepLinkStatusKind(
            {{ batches: [strategy, strategy] }}, JOB, true,
          ),
        }}));
        """
    )
    assert result == {
        "strategy": "strategy",
        "legacy": "legacy",
        "missing": "unknown",
        "malformed": "unknown",
        "rejectedArchive": "unknown",
        "duplicate": "unknown",
    }


def test_initial_deep_link_never_defaults_unknown_to_legacy_status() -> None:
    load = _between(APP, "async function loadSection", "function beginMyWorkNotificationFetch")
    archive_index = load.index("const archiveOutcome = await generationArchiveRequest")
    classify_index = load.index("const deepLinkKind = generationDeepLinkStatusKind")
    strategy_index = load.index("state.api.generationStrategyStatus(strategyRequest)")
    legacy_index = load.index("state.api.realGenerationStatus(")
    assert archive_index < classify_index < strategy_index
    assert classify_index < legacy_index
    assert 'if (deepLinkKind === "unknown")' in load
    unknown_branch = _between(
        load,
        'if (deepLinkKind === "unknown")',
        "generationDeepLinkRequest = withUiTimeout",
    )
    assert "status request skipped" in unknown_branch
    assert "realGenerationStatus" not in unknown_branch.split("} else {", 1)[0]
