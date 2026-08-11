from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608110004_exact_youtube_source_research_lifecycle.sql"
)
PGTAP = (
    ROOT
    / "supabase"
    / "tests"
    / "exact_youtube_source_research_lifecycle_test.sql"
)
API = ROOT / "web" / "app" / "supabase-api.js"
QUEUE = ROOT / "web" / "app" / "workspace-ai-exact-youtube-sources.js"
BOOTSTRAP = ROOT / "web" / "app" / "workspace-research-training-bootstrap.js"
INDEX = ROOT / "web" / "app" / "index.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_node(script: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser contract tests")
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_migration_is_additive_authoritative_and_provider_free() -> None:
    sql = read(MIGRATION)
    parse_sql(sql)
    body = sql.split("as $$", 1)[1].split("$$;", 1)[0].lower()

    assert "'version', 'exact-youtube-source-queue-v2'" in body
    assert "'analysis_ready_is_media_ready', true" in body
    assert "'research_lifecycle_projected', true" in body
    assert "'research_lifecycle_read_only', true" in body
    assert "'research_lifecycle_starts_provider_call', false" in body
    assert "require_workspace_project_access" in body
    assert "research_exact_youtube_research_bindings binding" in body
    assert "product_research_runs run" in body
    assert "ai_research_evidence_receipts receipt" in body
    assert "ai_research_evidence_dispositions disposition" in body
    assert "ai_research_learning_selections selection" in body
    assert "binding.organization_id = source.organization_id" in body
    assert "binding.project_id = source.project_id" in body
    assert "binding.source_id = source.id" in body
    assert "binding.attachment_id = attachment.id" in body
    assert "selection.project_id = binding.project_id" in body
    assert "selection.run_id = binding.run_id" in body
    assert "order by binding.bound_at desc, binding.id desc" in body
    assert "order by selection.selected_at desc, selection.event_cursor desc" in body
    assert "exact_youtube_research_source_lifecycle_idx" in sql
    for state in (
        "not_started",
        "analysis_in_progress",
        "analysis_failed",
        "completed_without_ai_receipt",
        "awaiting_learning_selection",
        "recommendations_ready",
        "excluded",
    ):
        assert f"'{state}'" in body

    assert re.search(r"\b(insert|update|delete|merge|truncate)\b", body) is None
    assert "research_provider_attempt" not in body
    assert "net.http" not in body
    assert "extensions.http" not in body


def test_creator_api_accepts_exact_lifecycle_and_rejects_false_transitions() -> None:
    script = f"""
      const {{ CreatorApi }} = await import({json.dumps(API.as_uri())});
      const ids = {{
        org: '11111111-1111-4111-8111-111111111111',
        project: '22222222-2222-4222-8222-222222222222',
        source: '33333333-3333-4333-8333-333333333333',
        attachment: '44444444-4444-4444-8444-444444444444',
        media: '55555555-5555-4555-8555-555555555555',
        binding: '66666666-6666-4666-8666-666666666666',
        run: '77777777-7777-4777-8777-777777777777',
        receipt: '88888888-8888-4888-8888-888888888888',
        selection: '99999999-9999-4999-8999-999999999999',
        oldRun: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
        oldReceipt: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        oldSelection: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      }};
      const at = '2026-08-11T08:00:00.000Z';
      const sourceHash = 'a'.repeat(64);
      const mediaSha = 'b'.repeat(64);
      const contract = {{
        url_is_video_evidence: false,
        requires_lawful_mp4: true,
        unattached_source_affects_learning: false,
        unattached_source_affects_generation: false,
        attachment_is_append_only: true,
        attached_source_affects_learning: false,
        attached_source_affects_generation: false,
        attachment_starts_analysis: false,
        source_row_mutated: false,
        analysis_ready_is_media_ready: true,
        research_lifecycle_projected: true,
        research_lifecycle_read_only: true,
        research_lifecycle_starts_analysis: false,
        research_lifecycle_starts_provider_call: false,
        external_call_started: false,
        paid_call_started: false,
      }};
      const base = {{
        id: ids.source,
        project_id: ids.project,
        status: 'media_attached',
        media_required: false,
        analysis_ready: true,
        media_ready: true,
        next_action: 'start_exact_media_analysis',
        source_hash: sourceHash,
        attachment: {{
          id: ids.attachment,
          status: 'attached',
          source_id: ids.source,
          media_id: ids.media,
          rights_confirmed: true,
          media_matches_registered_source: true,
          source_hash_snapshot: sourceHash,
          media_sha256_snapshot: mediaSha,
        }},
        media: {{
          id: ids.media,
          project_id: ids.project,
          sha256: mediaSha,
          status: 'ready',
          mime_type: 'video/mp4',
          kind: 'source_video',
          artifact_class: 'source',
          lifecycle_stage: 'sources',
        }},
      }};
      const effectiveNone = {{ has_approved_recommendations: false }};
      const latest = (status, extra = {{}}) => ({{
        binding_id: ids.binding,
        run_id: ids.run,
        run_status: status,
        product_category: 'household',
        bound_at: at,
        ...extra,
      }});
      const call = async (research_lifecycle, itemPatch = {{}}, contractPatch = {{}}) => {{
        const item = {{ ...base, ...itemPatch, research_lifecycle }};
        const supabase = {{ schema: () => ({{ rpc: async () => ({{
          data: {{
            ok: true,
            version: 'exact-youtube-source-queue-v2',
            project_id: ids.project,
            sources: [item],
            contract: {{ ...contract, ...contractPatch }},
          }},
          error: null,
        }}) }}) }};
        const api = new CreatorApi(supabase, {{ RPC_SCHEMA: 'public' }});
        api.organizationId = ids.org;
        return api.exactYoutubeSourceQueue({{ projectId: ids.project }});
      }};

      const notStarted = await call({{
        state: 'not_started',
        next_action: 'prepare_exact_media_analysis',
        latest: null,
        effective: effectiveNone,
      }});
      const processing = await call({{
        state: 'analysis_in_progress',
        next_action: 'open_research',
        latest: latest('processing'),
        effective: effectiveNone,
      }});
      const awaiting = await call({{
        state: 'awaiting_learning_selection',
        next_action: 'review_ai_learning',
        latest: latest('completed', {{
          finished_at: at,
          receipt_id: ids.receipt,
          receipt_status: 'awaiting_human_review',
          received_at: at,
        }}),
        effective: effectiveNone,
      }});
      const legacyApprovedStillAwaits = await call({{
        state: 'awaiting_learning_selection',
        next_action: 'review_ai_learning',
        latest: latest('completed', {{
          finished_at: at,
          receipt_id: ids.receipt,
          receipt_status: 'awaiting_human_review',
          received_at: at,
          disposition_decision: 'approve',
        }}),
        effective: effectiveNone,
      }});
      const ready = await call({{
        state: 'recommendations_ready',
        next_action: 'open_generation',
        latest: latest('completed', {{
          finished_at: at,
          receipt_id: ids.receipt,
          receipt_status: 'awaiting_human_review',
          received_at: at,
          learning_selection_id: ids.selection,
          learning_decision: 'approve',
          selected_at: at,
        }}),
        effective: {{
          has_approved_recommendations: true,
          selection_id: ids.selection,
          run_id: ids.run,
          receipt_id: ids.receipt,
          selected_at: at,
        }},
      }});
      const failedRetryWithEffectiveOlderSelection = await call({{
        state: 'analysis_failed',
        next_action: 'open_research',
        latest: latest('failed', {{ finished_at: at }}),
        effective: {{
          has_approved_recommendations: true,
          selection_id: ids.oldSelection,
          run_id: ids.oldRun,
          receipt_id: ids.oldReceipt,
          selected_at: at,
        }},
      }});

      let wrongAction = '';
      try {{
        await call({{
          state: 'awaiting_learning_selection',
          next_action: 'prepare_exact_media_analysis',
          latest: awaiting.sources[0].research_lifecycle.latest,
          effective: effectiveNone,
        }});
      }} catch (error) {{ wrongAction = error.code; }}
      let falseReady = '';
      try {{
        await call({{
          state: 'recommendations_ready',
          next_action: 'open_generation',
          latest: awaiting.sources[0].research_lifecycle.latest,
          effective: effectiveNone,
        }});
      }} catch (error) {{ falseReady = error.code; }}
      let mismatchedMediaAlias = '';
      try {{
        await call(notStarted.sources[0].research_lifecycle, {{ media_ready: false }});
      }} catch (error) {{ mismatchedMediaAlias = error.code; }}

      process.stdout.write(JSON.stringify({{
        states: [
          notStarted,
          processing,
          awaiting,
          legacyApprovedStillAwaits,
          ready,
          failedRetryWithEffectiveOlderSelection,
        ].map((value) => value.sources[0].research_lifecycle.state),
        legacyDispositionState:
          legacyApprovedStillAwaits.sources[0].research_lifecycle.state,
        effectiveSurvivesFailedRetry:
          failedRetryWithEffectiveOlderSelection.sources[0]
            .research_lifecycle.effective.has_approved_recommendations,
        wrongAction,
        falseReady,
        mismatchedMediaAlias,
      }}));
    """
    assert run_node(script) == {
        "states": [
            "not_started",
            "analysis_in_progress",
            "awaiting_learning_selection",
            "awaiting_learning_selection",
            "recommendations_ready",
            "analysis_failed",
        ],
        "legacyDispositionState": "awaiting_learning_selection",
        "effectiveSurvivesFailedRetry": True,
        "wrongAction": "exact_youtube_source_queue_response_invalid",
        "falseReady": "exact_youtube_source_queue_response_invalid",
        "mismatchedMediaAlias": "exact_youtube_source_queue_response_invalid",
    }


def test_ai_card_never_treats_media_integrity_as_completed_research() -> None:
    queue = read(QUEUE)
    assert "function mediaReady(source)" in queue
    assert "function researchLifecycle(source)" in queue
    assert 'if (state === "not_started")' in queue
    assert 'if (state === "awaiting_learning_selection")' in queue
    assert 'if (state === "recommendations_ready")' in queue
    assert 'if (effective)' in queue
    assert '"Исследование завершено · нужен отбор"' in queue
    assert '"Отобрать для обучения"' in queue
    assert '"Рекомендации ИИ готовы"' in queue
    assert '"Создать с рекомендациями"' in queue
    assert 'unknown ? `${unknown} уточняют статус`' in queue
    assert 'workspaceHash("/workspace/generation"' in queue
    assert 'research_receipt: clean(latest?.receipt_id' in queue
    assert "Новый платный запуск не нужен" in queue
    assert (
        "Разбор пяти контрольных кадров и визуальной механики ещё не выполнен"
        not in queue
    )
    assert (
        "До отдельной квитанции исследования источник не влияет"
        not in queue
    )

    awaiting_block = queue[
        queue.index('if (state === "awaiting_learning_selection")') :
        queue.index('if (state === "recommendations_ready")')
    ]
    assert 'workspaceHash("/workspace/review"' not in awaiting_block
    assert "exactReviewHash(" not in awaiting_block


def test_ai_card_routes_each_authoritative_state_without_restarting_research() -> None:
    script = f"""
      globalThis.window = {{
        location: {{
          hash: '#/workspace/ai?project_id=22222222-2222-4222-8222-222222222222',
        }},
      }};
      const {{ lifecyclePresentation }} = await import({json.dumps(QUEUE.as_uri())});
      const ids = {{
        source: '33333333-3333-4333-8333-333333333333',
        attachment: '44444444-4444-4444-8444-444444444444',
        media: '55555555-5555-4555-8555-555555555555',
        run: '77777777-7777-4777-8777-777777777777',
        receipt: '88888888-8888-4888-8888-888888888888',
        selection: '99999999-9999-4999-8999-999999999999',
      }};
      const base = {{
        id: ids.source,
        canonical_url: 'https://youtube.com/watch?v=RIJ_v--Yncw',
        attachment: {{ id: ids.attachment }},
      }};
      const effectiveNone = {{ has_approved_recommendations: false }};
      const latest = {{
        run_id: ids.run,
        product_category: 'household',
        receipt_id: ids.receipt,
      }};
      const view = (state, nextAction, latestValue, effective) =>
        lifecyclePresentation({{
          ...base,
          research_lifecycle: {{
            state,
            next_action: nextAction,
            latest: latestValue,
            effective,
          }},
        }}, ids.media);
      const notStarted = view(
        'not_started',
        'prepare_exact_media_analysis',
        null,
        effectiveNone,
      );
      const awaiting = view(
        'awaiting_learning_selection',
        'review_ai_learning',
        latest,
        effectiveNone,
      );
      const ready = view(
        'recommendations_ready',
        'open_generation',
        {{ ...latest, learning_decision: 'approve' }},
        {{
          has_approved_recommendations: true,
          selection_id: ids.selection,
          run_id: ids.run,
          receipt_id: ids.receipt,
        }},
      );
      const failedRetryWithOlderApproval = view(
        'analysis_failed',
        'open_research',
        {{ ...latest, receipt_id: undefined }},
        {{
          has_approved_recommendations: true,
          selection_id: ids.selection,
          run_id: ids.run,
          receipt_id: ids.receipt,
        }},
      );
      const legacy = lifecyclePresentation(base, ids.media);
      const awaitingParams = new URLSearchParams(
        awaiting.primaryHref.split('?')[1] || '',
      );
      process.stdout.write(JSON.stringify({{
        notStartedPath: notStarted.primaryHref.split('?')[0],
        awaitingPath: awaiting.primaryHref.split('?')[0],
        awaitingCategory: awaitingParams.get('category'),
        awaitingReceipt: awaitingParams.get('research_receipt'),
        readyPath: ready.primaryHref.split('?')[0],
        failedEffectivePath:
          failedRetryWithOlderApproval.primaryHref.split('?')[0],
        failedEffectiveStatus: failedRetryWithOlderApproval.status,
        legacyPath: legacy.primaryHref.split('?')[0],
        legacyStatus: legacy.status,
      }}));
    """
    assert run_node(script) == {
        "notStartedPath": "#/workspace/review",
        "awaitingPath": "#/workspace/ai",
        "awaitingCategory": "household",
        "awaitingReceipt": "88888888-8888-4888-8888-888888888888",
        "readyPath": "#/workspace/generation",
        "failedEffectivePath": "#/workspace/generation",
        "failedEffectiveStatus": (
            "Рекомендации ИИ готовы · проверьте последний запуск"
        ),
        "legacyPath": "#/workspace/research",
        "legacyStatus": "MP4 готов · статус исследования уточняется",
    }


def test_cache_bump_is_scoped_to_ai_center_runtime_modules() -> None:
    bootstrap = read(BOOTSTRAP)
    index = read(INDEX)
    assert 'const BUILD = "20260810.research.30"' in bootstrap
    assert '"workspace-ai-exact-youtube-sources.js":' in bootstrap
    assert '"20260811.ai-center-runtime-owned.1"' in bootstrap
    assert "ASSET_BUILD_OVERRIDES[file] || BUILD" in bootstrap
    assert (
        "workspace-research-training-bootstrap.js?"
        "v=sha256-"
        in index
    )
    assert PGTAP.exists()
