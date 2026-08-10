from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "web" / "app"
HANDOFF = APP_DIR / "exact-youtube-media-handoff.js"
DRAFT = APP_DIR / "exact-youtube-research-draft.js"
APP = APP_DIR / "app.js"
API = APP_DIR / "supabase-api.js"
RECOVERY = APP_DIR / "workspace-research-failure-recovery.js"
AI_QUEUE = APP_DIR / "workspace-ai-exact-youtube-sources.js"
RESEARCH_INTAKE = APP_DIR / "workspace-research-video-intake.js"


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
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_handoff_is_bound_to_org_user_tab_project_source_and_preserves_retry() -> None:
    script = f"""
      const mod = await import({json.dumps(HANDOFF.as_uri())});
      const values = new Map();
      const storage = {{
        getItem: (key) => values.has(key) ? values.get(key) : null,
        setItem: (key, value) => values.set(key, value),
        removeItem: (key) => values.delete(key),
      }};
      const context = {{
        organization_id: '11111111-1111-4111-8111-111111111111',
        user_id: '22222222-2222-4222-8222-222222222222',
        session_id: '33333333-3333-4333-8333-333333333333',
        project_id: '44444444-4444-4444-8444-444444444444',
        source_id: '55555555-5555-4555-8555-555555555555',
      }};
      const now = Date.now();
      const requestedAt = new Date(now - 5 * 60 * 1000).toISOString();
      const wrote = mod.writeExactYoutubeMediaHandoff(storage, {{
        ...context,
        canonical_url: 'https://youtube.com/watch?v=RIJ_v--Yncw',
        product_name: 'Аэрогриль  MILIO A425D-Black',
        product_sku: 'WB-518413561',
        requested_at: requestedAt,
      }});
      const exact = mod.readExactYoutubeMediaHandoff(storage, context, {{ now }});
      const wrongUser = mod.readExactYoutubeMediaHandoff(storage, {{
        ...context,
        user_id: '66666666-6666-4666-8666-666666666666',
      }}, {{ now }});
      const wrongTab = mod.readExactYoutubeMediaHandoff(storage, {{
        ...context,
        session_id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      }}, {{ now }});
      const expired = mod.readExactYoutubeMediaHandoff(storage, context, {{
        now: now + mod.EXACT_YOUTUBE_MEDIA_HANDOFF_MAX_AGE_MS + 1,
      }});
      const progress = mod.updateExactYoutubeMediaHandoffProgress(
        storage,
        context,
        {{
          object_key: `${{context.organization_id}}/${{context.user_id}}/uploads/2026-08/source.mp4`,
          original_filename: 'source.mp4',
          mime_type: 'video/mp4',
          size_bytes: 123456,
          sha256: 'a'.repeat(64),
          media_id: '77777777-7777-4777-8777-777777777777',
        }},
      );
      mod.writeExactYoutubeMediaHandoff(storage, {{
        ...context,
        canonical_url: 'https://youtube.com/watch?v=RIJ_v--Yncw',
        product_name: 'Аэрогриль MILIO A425D-Black',
        product_sku: 'WB-518413561',
        requested_at: new Date(now).toISOString(),
      }});
      const preserved = mod.readExactYoutubeMediaHandoff(storage, context, {{
        now: now + 60 * 1000,
      }});
      const attachmentId = '99999999-9999-4999-8999-999999999999';
      const reviewRoute = mod.exactYoutubeResearchEvidenceRoute({{
        projectId: context.project_id,
        sourceId: context.source_id,
        mediaId: preserved.handoff?.progress?.media_id,
        attachmentId,
        productName: preserved.handoff?.product_name,
        productSku: preserved.handoff?.product_sku,
      }});
      const reviewParams = new URLSearchParams(reviewRoute.split('?')[1] || '');
      const wrongClear = mod.clearExactYoutubeMediaHandoff(storage, {{
        ...context,
        project_id: '88888888-8888-4888-8888-888888888888',
      }});
      const stillThere = values.has(mod.EXACT_YOUTUBE_MEDIA_HANDOFF_STORAGE_KEY);
      const exactClear = mod.clearExactYoutubeMediaHandoff(storage, context);
      process.stdout.write(JSON.stringify({{
        wrote,
        exact: exact.ok,
        wrongUser: wrongUser.code,
        wrongTab: wrongTab.code,
        expired: expired.code,
        progress: progress.ok,
        mediaId: preserved.handoff?.progress?.media_id,
        productName: preserved.handoff?.product_name,
        productSku: preserved.handoff?.product_sku,
        reviewPath: reviewRoute.split('?')[0],
        reviewSource: reviewParams.get('youtube_source'),
        reviewAttachment: reviewParams.get('attachment'),
        reviewMedia: reviewParams.get('media'),
        reviewProductName: reviewParams.get('product_name'),
        reviewProductSku: reviewParams.get('product_sku'),
        wrongClear,
        stillThere,
        exactClear,
        removed: !values.has(mod.EXACT_YOUTUBE_MEDIA_HANDOFF_STORAGE_KEY),
      }}));
    """
    value = run_node(script)
    assert value == {
        "wrote": True,
        "exact": True,
        "wrongUser": "handoff_scope_mismatch",
        "wrongTab": "handoff_scope_mismatch",
        "expired": "handoff_expired",
        "progress": True,
        "mediaId": "77777777-7777-4777-8777-777777777777",
        "productName": "Аэрогриль MILIO A425D-Black",
        "productSku": "WB-518413561",
        "reviewPath": "/workspace/review",
        "reviewSource": "55555555-5555-4555-8555-555555555555",
        "reviewAttachment": "99999999-9999-4999-8999-999999999999",
        "reviewMedia": "77777777-7777-4777-8777-777777777777",
        "reviewProductName": "Аэрогриль MILIO A425D-Black",
        "reviewProductSku": "WB-518413561",
        "wrongClear": False,
        "stillThere": True,
        "exactClear": True,
        "removed": True,
    }


def test_creator_api_attaches_only_with_identity_attestation_and_validates_receipt() -> None:
    script = f"""
      const {{ CreatorApi }} = await import({json.dumps(API.as_uri())});
      const org = '11111111-1111-4111-8111-111111111111';
      const project = '22222222-2222-4222-8222-222222222222';
      const source = '33333333-3333-4333-8333-333333333333';
      const media = '44444444-4444-4444-8444-444444444444';
      const attachment = '55555555-5555-4555-8555-555555555555';
      const calls = [];
      const receipt = {{
        ok: true,
        version: 'exact-youtube-media-attachment-v1',
        project_id: project,
        source: {{ id: source, derived_status: 'media_attached' }},
        attachment: {{
          id: attachment, status: 'attached', source_id: source, media_id: media,
          rights_confirmed: true, media_matches_registered_source: true,
        }},
        media: {{
          id: media, project_id: project, mime_type: 'video/mp4',
          kind: 'source_video',
        }},
        contract: {{
          append_only: true, exact_project_scope: true,
          registered_media_reused: true, identity_attestation_recorded: true,
          source_row_mutated: false, analysis_ready: true,
          analysis_started: false, external_call_started: false,
          paid_call_started: false,
        }},
      }};
      const supabase = {{ schema: () => ({{
        rpc: async (name, args) => {{ calls.push({{ name, args }}); return {{ data: receipt, error: null }}; }},
      }}) }};
      const api = new CreatorApi(supabase, {{
        RPC_SCHEMA: 'public', STORAGE_BUCKET: 'contentengine-private',
      }});
      api.organizationId = org;
      let rejectedCode = '';
      try {{
        await api.attachExactYoutubeMedia({{
          projectId: project, sourceId: source, mediaId: media,
          rightsConfirmed: true,
        }});
      }} catch (error) {{ rejectedCode = error.code; }}
      const result = await api.attachExactYoutubeMedia({{
        projectId: project, sourceId: source, mediaId: media,
        rightsConfirmed: true, mediaMatchesRegisteredSource: true,
      }});
      process.stdout.write(JSON.stringify({{
        rejectedCode,
        callCount: calls.length,
        name: calls[0]?.name,
        payload: calls[0]?.args?.p_payload,
        version: result.version,
      }}));
    """
    value = run_node(script)
    assert value["rejectedCode"] == (
        "exact_youtube_media_attachment_source_match_required"
    )
    assert value["callCount"] == 1
    assert value["name"] == "contentengine_attach_exact_youtube_media"
    assert value["payload"]["organization_id"] == (
        "11111111-1111-4111-8111-111111111111"
    )
    assert value["payload"]["project_id"] == (
        "22222222-2222-4222-8222-222222222222"
    )
    assert value["payload"]["source_id"] == (
        "33333333-3333-4333-8333-333333333333"
    )
    assert value["payload"]["media_id"] == (
        "44444444-4444-4444-8444-444444444444"
    )
    assert value["payload"]["rights_confirmed"] is True
    assert value["payload"]["media_matches_registered_source"] is True
    assert isinstance(value["payload"]["idempotency_key"], str)
    assert value["version"] == "exact-youtube-media-attachment-v1"


def test_creator_api_queue_v2_validates_attached_lineage_and_allows_restore_state() -> None:
    script = f"""
      const {{ CreatorApi }} = await import({json.dumps(API.as_uri())});
      const org = '11111111-1111-4111-8111-111111111111';
      const project = '22222222-2222-4222-8222-222222222222';
      const sourceId = '33333333-3333-4333-8333-333333333333';
      const attachmentId = '44444444-4444-4444-8444-444444444444';
      const mediaId = '55555555-5555-4555-8555-555555555555';
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
        external_call_started: false,
        paid_call_started: false,
      }};
      const attached = {{
        id: sourceId, project_id: project, status: 'media_attached',
        media_required: false, analysis_ready: true,
        next_action: 'start_exact_media_analysis', source_hash: sourceHash,
        attachment: {{
          id: attachmentId, status: 'attached', source_id: sourceId,
          media_id: mediaId, rights_confirmed: true,
          media_matches_registered_source: true,
          source_hash_snapshot: sourceHash, media_sha256_snapshot: mediaSha,
        }},
        media: {{
          id: mediaId, project_id: project, sha256: mediaSha, status: 'ready',
          mime_type: 'video/mp4', kind: 'source_video',
          artifact_class: 'source', lifecycle_stage: 'sources',
        }},
      }};
      const buildApi = (item) => {{
        const supabase = {{ schema: () => ({{ rpc: async () => ({{
          data: {{ ok: true, version: 'exact-youtube-source-queue-v2',
            project_id: project, sources: [item], contract }},
          error: null,
        }}) }}) }};
        const api = new CreatorApi(supabase, {{ RPC_SCHEMA: 'public' }});
        api.organizationId = org;
        return api;
      }};
      const valid = await buildApi(attached).exactYoutubeSourceQueue({{
        projectId: project,
      }});
      const restore = await buildApi({{
        ...attached, analysis_ready: false, next_action: 'restore_attached_media',
        media: null,
      }}).exactYoutubeSourceQueue({{ projectId: project }});
      let badCode = '';
      try {{
        await buildApi({{
          ...attached,
          media: {{ ...attached.media, sha256: 'c'.repeat(64) }},
        }}).exactYoutubeSourceQueue({{ projectId: project }});
      }} catch (error) {{ badCode = error.code; }}
      process.stdout.write(JSON.stringify({{
        valid: valid.sources[0].analysis_ready,
        restore: restore.sources[0].next_action,
        badCode,
      }}));
    """
    assert run_node(script) == {
        "valid": True,
        "restore": "restore_attached_media",
        "badCode": "exact_youtube_source_queue_response_invalid",
    }


def test_upload_flow_preserves_registered_media_and_normal_uploads_stay_unlinked() -> None:
    app = read(APP)
    submit = app[
        app.index("async function submitMedia(form)") : app.index(
            "async function track", app.index("async function submitMedia(form)")
        )
    ]
    for marker in (
        "exactYoutubeMediaRouteIntent(projectId)",
        "readExactYoutubeMediaHandoff",
        "exactYoutubeRegisteredMediaId(registration)",
        "updateExactYoutubeMediaHandoffProgress",
        "media_matches_registered_source",
        'kind !== "source_video"',
        "!isExactYoutubeMp4(files[0])",
        "await attachRegisteredExactYoutubeMedia",
        "exactYoutubeReviewRoute",
        "MP4 уже сохранён и не удалён",
    ):
        assert marker in app
    assert "if (objectUploaded && objectKey && !exactIntent.active)" in submit
    assert "await state.api.removePrivateObject(objectKey)" in submit
    assert "if (exactIntent.active)" in submit
    assert "state.api.attachExactYoutubeMedia" in app
    # Generic uploads still register through the existing payload and never
    # acquire a source id unless the exact handoff branch is active.
    assert "source_id: exactIntent.sourceId" not in submit[
        submit.index("const registration = await state.api.registerMedia") :
        submit.index("mediaRegistered = true")
    ]


def test_recovery_requires_exact_mp4_identity_and_queue_v2_links_to_review() -> None:
    recovery = read(RECOVERY)
    queue = read(AI_QUEUE)
    for marker in (
        'name="media_matches_registered_source"',
        'form="media-upload-form"',
        "это тот же ролик",
        "Другой референс нужно зарегистрировать отдельно",
        'kind.value = "source_video"',
        'option.disabled = option.value !== "source_video"',
        "currentUploadHandoff(sourceId)",
        "Повторяем только привязку уже сохранённого MP4",
    ):
        assert marker in recovery
    for marker in (
        '"exact-youtube-source-queue-v2"',
        'source?.status === "media_attached"',
        'source?.analysis_ready === true',
        'workspaceHash("/workspace/review"',
        'view: "new"',
        'media: attachedMediaId',
        'product_name: clean(source.product_name, 300)',
        'product_sku: clean(source.product_sku, 160)',
        '"Подготовить кадры для исследования"',
        "До отдельной квитанции исследования источник не влияет на рекомендации ИИ",
        "речь, аудио и полный видеопоток внешнему ИИ не передаются",
    ):
        assert marker in queue
    mount = recovery[
        recovery.index("function mountMediaHandoff(") : recovery.index(
            "function repairAiCenterLinks(",
            recovery.index("function mountMediaHandoff("),
        )
    ]
    assert "const initialHandoff = currentUploadHandoff(sourceId)" in mount
    assert "rememberUploadHandoff(" not in mount
    assert "if (!initialHandoff.ok)" in mount
    assert "primary.addEventListener(\"click\"" in queue
    assert "beginMediaHandoff(source)" in queue


def test_ai_queue_explicit_click_contract_creates_handoff_but_direct_url_does_not() -> None:
    script = f"""
      const handoff = await import({json.dumps(HANDOFF.as_uri())});
      const queue = await import({json.dumps(AI_QUEUE.as_uri())});
      const values = new Map();
      const storage = {{
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
        removeItem: (key) => values.delete(key),
      }};
      const context = {{
        organization_id: '11111111-1111-4111-8111-111111111111',
        user_id: '22222222-2222-4222-8222-222222222222',
        session_id: '33333333-3333-4333-8333-333333333333',
        project_id: '44444444-4444-4444-8444-444444444444',
        source_id: '55555555-5555-4555-8555-555555555555',
      }};
      globalThis.window = {{
        location: {{ hash: `#/workspace/ai?project_id=${{context.project_id}}` }},
        sessionStorage: storage,
        ContentEngineWorkspaceRuntime: {{
          getExactYoutubeHandoffContext: () => context,
        }},
      }};
      const before = handoff.readExactYoutubeMediaHandoff(storage, context);
      const began = queue.beginMediaHandoff({{
        id: context.source_id,
        canonical_url: 'https://youtube.com/watch?v=RIJ_v--Yncw',
        product_name: 'MILIO A425D-Black',
        product_sku: 'WB-518413561',
      }});
      const after = handoff.readExactYoutubeMediaHandoff(storage, context);
      process.stdout.write(JSON.stringify({{
        before: before.code,
        began,
        after: after.ok,
        product: after.handoff?.product_name,
      }}));
    """
    assert run_node(script) == {
        "before": "handoff_missing",
        "began": True,
        "after": True,
        "product": "MILIO A425D-Black",
    }


def test_research_form_upload_click_opens_exact_media_context_with_product_identity() -> None:
    script = f"""
      const intake = await import({json.dumps(RESEARCH_INTAKE.as_uri())});
      const handoff = await import({json.dumps(HANDOFF.as_uri())});
      const values = new Map();
      const storage = {{
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
        removeItem: (key) => values.delete(key),
      }};
      const context = {{
        organization_id: '11111111-1111-4111-8111-111111111111',
        user_id: '22222222-2222-4222-8222-222222222222',
        session_id: '33333333-3333-4333-8333-333333333333',
        project_id: '44444444-4444-4444-8444-444444444444',
      }};
      const source = {{
        id: '55555555-5555-4555-8555-555555555555',
        project_id: context.project_id,
        canonical_url: 'https://youtube.com/watch?v=YiIjPmQ-XgU',
        product_name: 'MILIO A425D-Black',
        product_sku: '518413561',
      }};
      const prepared = intake.prepareResearchVideoMediaHandoff({{
        storage,
        context,
        source,
        canonicalUrl: 'https://www.youtube.com/watch?v=YiIjPmQ-XgU&t=64s',
        productName: 'ignored browser draft',
        productSku: 'ignored-sku',
      }});
      const [path, rawQuery = ''] = prepared.href.slice(1).split('?');
      const query = new URLSearchParams(rawQuery);
      const expected = {{
        ...context,
        source_id: query.get('youtube_source'),
      }};
      const mounted = handoff.readExactYoutubeMediaHandoff(storage, expected);
      process.stdout.write(JSON.stringify({{
        ok: prepared.ok,
        path,
        view: query.get('view'),
        project: query.get('project_id'),
        source: query.get('youtube_source'),
        canonical: query.get('video_url'),
        productName: query.get('product_name'),
        productSku: query.get('product_sku'),
        returnTo: query.get('return_to'),
        mountOk: mounted.ok,
        mountedCanonical: mounted.handoff?.canonical_url,
        mountedProductName: mounted.handoff?.product_name,
        mountedProductSku: mounted.handoff?.product_sku,
      }}));
    """
    assert run_node(script) == {
        "ok": True,
        "path": "/workspace/media",
        "view": "upload",
        "project": "44444444-4444-4444-8444-444444444444",
        "source": "55555555-5555-4555-8555-555555555555",
        "canonical": "https://youtube.com/watch?v=YiIjPmQ-XgU",
        "productName": "MILIO A425D-Black",
        "productSku": "518413561",
        "returnTo": (
            "#/workspace/research?"
            "project_id=44444444-4444-4444-8444-444444444444&"
            "source_url=https%3A%2F%2Fyoutube.com%2Fwatch%3Fv%3DYiIjPmQ-XgU"
        ),
        "mountOk": True,
        "mountedCanonical": "https://youtube.com/watch?v=YiIjPmQ-XgU",
        "mountedProductName": "MILIO A425D-Black",
        "mountedProductSku": "518413561",
    }

    intake_source = read(RESEARCH_INTAKE)
    recovery_source = read(RECOVERY)
    assert 'upload.addEventListener("click"' in intake_source
    assert "openResearchVideoMediaUpload(" in intake_source
    mount = recovery_source[
        recovery_source.index("function mountMediaHandoff(") : recovery_source.index(
            "function repairAiCenterLinks(",
            recovery_source.index("function mountMediaHandoff("),
        )
    ]
    for marker in (
        'name="media_matches_registered_source"',
        'sourceLabel.textContent = String(sourceSnapshot.canonical_url',
        '["product_name", sourceSnapshot.product_name]',
        '["sku", sourceSnapshot.product_sku]',
        'field.dataset.exactYoutubeIdentity = "true"',
    ):
        assert marker in mount


def test_research_upload_double_click_registers_once_and_starts_no_paid_call() -> None:
    script = f"""
      const handoff = await import({json.dumps(HANDOFF.as_uri())});
      const draft = await import({json.dumps(DRAFT.as_uri())});
      const values = new Map();
      const storage = {{
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
        removeItem: (key) => values.delete(key),
      }};
      const ids = {{
        organization_id: '11111111-1111-4111-8111-111111111111',
        user_id: '22222222-2222-4222-8222-222222222222',
        session_id: '33333333-3333-4333-8333-333333333333',
        project_id: '44444444-4444-4444-8444-444444444444',
        source_id: '55555555-5555-4555-8555-555555555555',
      }};
      let releaseRegistration;
      const registrationGate = new Promise((resolve) => {{
        releaseRegistration = resolve;
      }});
      const rpcNames = [];
      const api = {{
        organizationId: ids.organization_id,
        withOrganization: (payload) => ({{
          organization_id: ids.organization_id,
          ...payload,
        }}),
        call: async (name) => {{
          rpcNames.push(name);
          await registrationGate;
          return {{
            ok: true,
            version: 'exact-youtube-source-intake-v1',
            source: {{
              id: ids.source_id,
              project_id: ids.project_id,
              video_id: 'YiIjPmQ-XgU',
              canonical_url: 'https://youtube.com/watch?v=YiIjPmQ-XgU',
              product_name: 'MILIO A425D-Black',
              product_sku: '518413561',
              status: 'awaiting_media',
              media_required: true,
              source_hash: 'a'.repeat(64),
            }},
            contract: {{
              registered_in_research: true,
              visible_in_ai_center: true,
              url_is_video_evidence: false,
              paid_analysis_allowed: false,
              external_call_started: false,
              paid_call_started: false,
            }},
          }};
        }},
      }};
      globalThis.window = {{
        location: {{
          hash: `#/workspace/research?project_id=${{ids.project_id}}`,
        }},
        sessionStorage: storage,
        ContentEngineWorkspaceRuntime: {{
          getApi: () => api,
          getExactYoutubeHandoffContext: () => ({{
            organization_id: ids.organization_id,
            user_id: ids.user_id,
            session_id: ids.session_id,
            project_id: ids.project_id,
          }}),
        }},
      }};
      const intake = await import({json.dumps(RESEARCH_INTAKE.as_uri())});
      const productName = {{ value: 'MILIO A425D-Black', focus: () => {{}} }};
      const sku = {{ value: '518413561', focus: () => {{}} }};
      const fields = {{
        product_name: productName,
        sku,
        product_category: {{ value: 'household' }},
        category_name: {{ value: 'Аэрогрили и мультипечи' }},
        research_focus: {{ value: 'Результат сначала, быстрый процесс и payoff' }},
        marketplace_url: {{
          value: 'https://www.wildberries.ru/catalog/518413561/detail.aspx',
        }},
        competitor_references: {{ value: 'Только механика референса' }},
        objective: {{ value: 'conversion' }},
        known_facts: {{ value: '4 л; 1500 Вт; 10 программ; гарантия 3 года' }},
      }};
      const platforms = [
        {{ value: 'youtube' }}, {{ value: 'wildberries' }},
      ];
      const sourceMediaIds = [
        {{ value: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' }},
        {{ value: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb' }},
      ];
      const form = {{
        elements: {{ namedItem: (name) => fields[name] || null }},
        querySelectorAll: (selector) => {{
          if (selector === 'input[name="platforms"]:checked') return platforms;
          if (selector === 'input[name="source_media_ids"]:checked') {{
            return sourceMediaIds;
          }}
          return [];
        }},
      }};
      const input = {{
        value: 'https://www.youtube.com/watch?v=YiIjPmQ-XgU&t=64s',
        setCustomValidity: () => {{}},
        reportValidity: () => true,
        focus: () => {{}},
      }};
      const panel = {{ dataset: {{}} }};
      const status = {{ dataset: {{}}, textContent: '' }};
      const attributes = new Map();
      const upload = {{
        dataset: {{}},
        href: '',
        setAttribute: (key, value) => attributes.set(key, value),
        removeAttribute: (key) => attributes.delete(key),
      }};
      const firstEvent = {{ prevented: 0, preventDefault() {{ this.prevented += 1; }} }};
      const secondEvent = {{ prevented: 0, preventDefault() {{ this.prevented += 1; }} }};
      const first = intake.openResearchVideoMediaUpload(
        firstEvent, form, panel, input, status, upload,
      );
      const second = intake.openResearchVideoMediaUpload(
        secondEvent, form, panel, input, status, upload,
      );
      releaseRegistration();
      await Promise.all([first, second]);
      const routeQuery = new URLSearchParams(
        window.location.hash.split('?')[1] || '',
      );
      const stored = handoff.readExactYoutubeMediaHandoff(storage, ids);
      const storedDraft = draft.readExactYoutubeResearchDraft(storage, ids);
      process.stdout.write(JSON.stringify({{
        rpcNames,
        firstPrevented: firstEvent.prevented,
        secondPrevented: secondEvent.prevented,
        route: window.location.hash.split('?')[0],
        routeSource: routeQuery.get('youtube_source'),
        routeProduct: routeQuery.get('product_name'),
        routeSku: routeQuery.get('product_sku'),
        stored: stored.ok,
        storedSource: stored.handoff?.source_id,
        draftOk: storedDraft.ok,
        draftCategory: storedDraft.draft?.product_category,
        draftMarketplace: storedDraft.draft?.marketplace_url,
        draftPlatforms: storedDraft.draft?.platforms,
        draftPhotos: storedDraft.draft?.source_media_ids,
        draftFocus: storedDraft.draft?.research_focus,
        draftFacts: storedDraft.draft?.known_facts,
      }}));
    """
    assert run_node(script) == {
        "rpcNames": ["contentengine_register_exact_youtube_source"],
        "firstPrevented": 1,
        "secondPrevented": 1,
        "route": "/workspace/media",
        "routeSource": "55555555-5555-4555-8555-555555555555",
        "routeProduct": "MILIO A425D-Black",
        "routeSku": "518413561",
        "stored": True,
        "storedSource": "55555555-5555-4555-8555-555555555555",
        "draftOk": True,
        "draftCategory": "household",
        "draftMarketplace": (
            "https://www.wildberries.ru/catalog/518413561/detail.aspx"
        ),
        "draftPlatforms": ["youtube", "wildberries"],
        "draftPhotos": [
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        ],
        "draftFocus": "Результат сначала, быстрый процесс и payoff",
        "draftFacts": "4 л; 1500 Вт; 10 программ; гарантия 3 года",
    }


def test_exact_video_route_captures_five_frames_then_starts_product_research_only() -> None:
    app = read(APP)
    render = app[
        app.index("function exactYoutubeResearchEvidenceMarkup(") : app.index(
            "function renderContentReviewSection(",
            app.index("function exactYoutubeResearchEvidenceMarkup("),
        )
    ]
    submit = app[
        app.index("async function submitExactYoutubeResearchEvidence(") : app.index(
            "async function submitContentReview(form)",
            app.index("async function submitExactYoutubeResearchEvidence("),
        )
    ]
    for marker in (
        "Подготовка кадров для исследования",
        "Исходный поток и транскрипт внешнему ИИ не передаются",
        'name="media_matches_registered_source"',
        'name="external_ai_processing_ack"',
        'name="paid_analysis_ack"',
        'name="human_review_ack"',
        'name="source_media_id"',
        'value="${escapeHtml(context.productName)}"',
        'value="${escapeHtml(context.productSku)}"',
    ):
        assert marker in render
    for marker in (
        "requireFreshExactYoutubeResearchSource(context",
        "resolveExactYoutubeResearchCaptureMedia(",
        "captureVerifiedPrivateVideoEvidence(",
        "persistContentReviewVideoEvidence(",
        "saveExactYoutubeResearchEvidence(context, evidence)",
        "state.api.startProductResearch(",
        "product_id: productPhoto.productId",
        "source_media_ids: [productPhoto.id]",
        "exact_youtube_source_id: context.sourceId",
        "exact_youtube_attachment_id: context.attachmentId",
        "exact_youtube_media_id: context.mediaId",
        "exact_video_evidence_id: durableEvidence.evidenceId",
        "media_matches_registered_source: true",
        '"operator_compared_uploaded_media_to_registered_source"',
        'sampled_frame_count: 5',
        'raw_video_sent: false',
        'transcript_available: false',
        'navigate(`/workspace/research?${query.toString()}`)',
    ):
        assert marker in submit
    assert "state.api.exactYoutubeSourceQueue(" in app
    assert "startContentReview" not in submit
    assert "source_media_ids: [video.id]" not in submit


def test_exact_product_research_receipt_is_checked_before_paid_edge_invoke() -> None:
    script = f"""
      const {{ CreatorApi }} = await import({json.dumps(API.as_uri())});
      const ids = {{
        org: '11111111-1111-4111-8111-111111111111',
        project: '22222222-2222-4222-8222-222222222222',
        product: '33333333-3333-4333-8333-333333333333',
        source: '44444444-4444-4444-8444-444444444444',
        attachment: '55555555-5555-4555-8555-555555555555',
        evidence: '66666666-6666-4666-8666-666666666666',
        binding: '77777777-7777-4777-8777-777777777777',
        media: '88888888-8888-4888-8888-888888888888',
        photo: '99999999-9999-4999-8999-999999999999',
        run: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      }};
      const exactVideo = {{
        binding_id: ids.binding,
        source_id: ids.source,
        attachment_id: ids.attachment,
        media_id: ids.media,
        evidence_id: ids.evidence,
        canonical_url: 'https://youtube.com/watch?v=RIJ_v--Yncw',
        analysis_scope: 'sampled_frames_only',
        full_stream_access: false,
        transcript_available: false,
        content_review_provider_started: false,
        product_research_provider_started: false,
      }};
      const input = {{
        product_id: ids.product,
        sku: 'WB-518413561',
        product_name: 'MILIO A425D-Black',
        product_category: 'household',
        objective: 'Analyze sampled frames only',
        marketplace_url: 'https://www.wildberries.ru/catalog/518413561/detail.aspx',
        source_media_ids: [ids.photo],
        platforms: ['youtube', 'wildberries'],
        paid_analysis_ack: true,
        exact_youtube_source_id: ids.source,
        exact_youtube_attachment_id: ids.attachment,
        exact_youtube_media_id: ids.media,
        exact_video_evidence_id: ids.evidence,
        media_matches_registered_source: true,
        source_match_basis: 'operator_compared_uploaded_media_to_registered_source',
      }};
      const buildApi = (receipt) => {{
        let invokes = 0;
        let rpcPayload = null;
        const supabase = {{
          schema: () => ({{ rpc: async (_name, args) => {{
            rpcPayload = args?.p_payload || null;
            return {{ data: receipt, error: null }};
          }} }}),
          auth: {{ getSession: async () => ({{
            data: {{ session: {{ access_token: 'browser-token', user: {{ id: ids.org }} }} }},
            error: null,
          }}) }},
          functions: {{ invoke: async () => {{
            invokes += 1;
            return {{ data: {{ ok: true, accepted: true }}, error: null }};
          }} }},
        }};
        const api = new CreatorApi(supabase, {{
          RPC_SCHEMA: 'public', STORAGE_BUCKET: 'contentengine-private',
        }});
        api.organizationId = ids.org;
        return {{ api, invokes: () => invokes, rpcPayload: () => rpcPayload }};
      }};
      const valid = buildApi({{
        ok: true,
        project_id: ids.project,
        run: {{ id: ids.run, status: 'queued' }},
        exact_video: exactVideo,
      }});
      await valid.api.startProductResearch(input, {{ projectId: ids.project }});
      const invalid = buildApi({{
        ok: true,
        project_id: ids.project,
        run: {{ id: ids.run, status: 'queued' }},
        exact_video: {{
          ...exactVideo,
          media_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
        }},
      }});
      let invalidCode = '';
      let invalidJob = '';
      try {{
        await invalid.api.startProductResearch(input, {{ projectId: ids.project }});
      }} catch (error) {{
        invalidCode = error.code;
        invalidJob = error.job?.id || '';
      }}
      process.stdout.write(JSON.stringify({{
        validInvokes: valid.invokes(),
        clientOnlyMediaRemoved:
          valid.rpcPayload()?.exact_youtube_media_id === undefined,
        invalidInvokes: invalid.invokes(),
        invalidCode,
        invalidJob,
      }}));
    """
    value = run_node(script)
    assert value == {
        "validInvokes": 1,
        "clientOnlyMediaRemoved": True,
        "invalidInvokes": 0,
        "invalidCode": "exact_video_research_binding_response_invalid",
        "invalidJob": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    }


def test_exact_youtube_handoff_browser_modules_are_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser contract tests")
    for path in (HANDOFF, APP, API, RECOVERY, AI_QUEUE):
        result = subprocess.run(
            [node, "--check", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
        assert result.returncode == 0, f"{path.name}: {result.stderr}"
