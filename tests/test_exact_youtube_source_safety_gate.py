from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
SOURCE = (APP / "workspace-research-video-intake.js").read_text(encoding="utf-8")
SOURCE_PATH = APP / "workspace-research-video-intake.js"
PRODUCT_RESEARCH_VIEW = APP / "product-research-view.js"
STYLES = (APP / "workspace-research-video-intake.css").read_text(encoding="utf-8")


def test_exact_youtube_url_is_an_identity_not_ingested_video_evidence() -> None:
    for marker in (
        "A YouTube page URL is an identity and metadata pointer, not a video file",
        "paid_analysis_allowed: false",
        "required_input: \"lawful_mp4\"",
        "blockUrlOnlySubmit",
        "event.preventDefault()",
        "event.stopImmediatePropagation()",
        "Остановлено до списания",
        "Перейти в Файлы и загрузить MP4",
        "Продолжить исследование рынка без разбора ролика",
    ):
        assert marker in SOURCE

    submit_handler = SOURCE.split(
        'form.addEventListener("submit", (event) => {', 1
    )[1].split("}, { capture: true });", 1)[0]
    assert "mergeResearchVideoReference(" not in submit_handler
    assert "blockUrlOnlySubmit(" in submit_handler


def test_zero_citation_provider_failure_disables_blind_paid_retry() -> None:
    for marker in (
        "zeroCitationProviderFailure",
        "0 цитат",
        "провайдер отклонил запрос",
        "retry.disabled = true",
        "Не повторять: источник не прочитан",
        "Новый такой же запуск платить не нужно",
        "Загрузить MP4 для настоящего разбора",
    ):
        assert marker in SOURCE
    assert ".research-youtube-failure-guard" in STYLES
    assert '[data-source-mode="media-required"]' in STYLES


def test_exact_terminal_failure_uses_server_evidence_without_citation_heuristic() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = f"""
      const intake = await import({json.dumps(SOURCE_PATH.as_uri())});
      const view = await import({json.dumps(PRODUCT_RESEARCH_VIEW.as_uri())});
      const ids = {{
        binding_id: '11111111-1111-4111-8111-111111111111',
        source_id: '22222222-2222-4222-8222-222222222222',
        attachment_id: '33333333-3333-4333-8333-333333333333',
        media_id: '44444444-4444-4444-8444-444444444444',
        evidence_id: '55555555-5555-4555-8555-555555555555'
      }};
      const exactEnvelope = {{
        run: {{
          id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
          status: 'failed',
          product_name: 'MILIO',
          sku: '518413561'
        }},
        exact_video: {{
          verified: true,
          marker_source: 'server_exact_video_binding',
          ...ids,
          frame_count: 5,
          analysis_scope: 'sampled_frames_only',
          full_stream_access: false,
          transcript_available: false,
          media_matches_registered_source: true
        }}
      }};
      const exact = view.normalizeProductResearch(exactEnvelope);
      exact.failureCode = 'provider_unavailable';
      exact.providerControl = {{
        runControl: {{ attempt: {{ providerKey: 'openai_web_search' }} }},
        responseState: {{ bindingState: 'bound', providerStatus: 'failed' }}
      }};
      const exactMarkup = view.productResearchProgressMarkup(exact);
      const queuedWithTerminalDiagnostic = {{
        ...exact,
        providerControl: {{
          ...exact.providerControl,
          responseState: {{
            bindingState: 'bound',
            providerStatus: 'queued',
            terminalDiagnostic: {{ terminalStatus: 'failed' }}
          }}
        }}
      }};
      const queuedTerminalMarkup = view.productResearchProgressMarkup(
        queuedWithTerminalDiagnostic
      );
      const incomplete = {{
        ...exact,
        failureCode: 'provider_response_invalid',
        providerControl: {{
          ...exact.providerControl,
          responseState: {{
            bindingState: 'bound',
            providerStatus: 'incomplete',
            terminalDiagnostic: {{ terminalStatus: 'incomplete' }}
          }}
        }}
      }};
      const incompleteMarkup = view.productResearchProgressMarkup(incomplete);
      const exactFailure = intake.exactVideoTerminalFailure({{
        evidence: {{
          verified: 'verified',
          markerSource: exact.exactVideo?.markerSource,
          sourceId: exact.exactVideo?.sourceId,
          attachmentId: exact.exactVideo?.attachmentId,
          mediaId: exact.exactVideo?.mediaId,
          evidenceId: exact.exactVideo?.evidenceId,
          frameCount: exact.exactVideo?.frameCount,
          analysisScope: exact.exactVideo?.analysisScope,
          productName: 'MILIO',
          productSku: '518413561'
        }},
        terminalStatus: 'failed'
      }});
      const legacy = view.normalizeProductResearch({{
        run: {{ id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', status: 'failed' }}
      }}, exact);
      const unrelated = intake.exactVideoTerminalFailure({{
        evidence: null,
        terminalStatus: 'failed'
      }});
      const tampered = intake.exactVideoFailureEvidence({{
        ...exactFailure.evidence,
        productName: 'x'.repeat(181),
        productSku: 'y'.repeat(121)
      }});
      process.stdout.write(JSON.stringify({{
        exactFailure: Boolean(exactFailure),
        exactMarkupHasMarker: exactMarkup.includes('data-research-exact-video-evidence="verified"'),
        exactMarkupIsHonest: exactMarkup.includes('Отсутствие подтверждённых цитат не означает, что кадры не передавались'),
        exactMarkupHasProduct: exactMarkup.includes('data-exact-video-product-name="MILIO"')
          && exactMarkup.includes('data-exact-video-product-sku="518413561"'),
        queuedDiagnosticWins: queuedTerminalMarkup.includes(
          'data-provider-terminal-status="failed"'
        ),
        incompleteUsesFreshEvidence: incompleteMarkup.includes(
          'data-provider-terminal-status="incomplete"'
        ) && !incompleteMarkup.includes(
          'data-action="revalidate-product-research-response"'
        ),
        exactProduct: [exactFailure?.evidence.productName, exactFailure?.evidence.productSku],
        legacyHasExact: Boolean(legacy.exactVideo),
        unrelated: Boolean(unrelated),
        tamperedProduct: [tampered?.productName, tampered?.productSku]
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    value = json.loads(result.stdout)
    assert value == {
        "exactFailure": True,
        "exactMarkupHasMarker": True,
        "exactMarkupIsHonest": True,
        "exactMarkupHasProduct": True,
        "queuedDiagnosticWins": True,
        "incompleteUsesFreshEvidence": True,
        "exactProduct": ["MILIO", "518413561"],
        "legacyHasExact": False,
        "unrelated": False,
        "tamperedProduct": ["", ""],
    }


def test_exact_recovery_reuses_saved_mp4_but_requires_fresh_evidence_and_consent() -> None:
    for marker in (
        "exactVideoTerminalFailure",
        "terminalStatus",
        "Создать новый набор из 5 кадров из сохранённого MP4",
        "Повторно загружать MP4 не нужно",
        "отдельных подтверждений обработки ИИ и оплаты",
        "exactYoutubeResearchEvidenceRoute",
        "data-research-exact-video-evidence",
        "productName: exactTerminalFailure.evidence.productName",
        "productSku: exactTerminalFailure.evidence.productSku",
    ):
        assert marker in SOURCE
    legacy_guard = SOURCE.split(
        "if (exactTerminalFailure) {", 1
    )[1].split('const guard = el("section", "research-youtube-failure-guard', 1)[1]
    assert "Shorts распознан как ссылка, но не был передан как видео" in legacy_guard
    assert 'text.includes("0 цитат")' in SOURCE


def test_exact_acceptance_short_still_canonicalizes_without_network_or_spend() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    script = f"""
      const mod = await import({json.dumps(SOURCE_PATH.as_uri())});
      const values = [
        'https://www.youtube.com/shorts/CXssfXBVInw',
        'https://youtu.be/CXssfXBVInw?si=test',
        'https://www.youtube.com/watch?v=CXssfXBVInw&utm_source=test'
      ].map(mod.canonicalResearchVideoUrl);
      console.log(JSON.stringify(values));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    values = json.loads(result.stdout)
    assert values == ["https://youtube.com/watch?v=CXssfXBVInw"] * 3


def test_youtube_source_gate_is_valid_javascript() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    subprocess.run(
        [node, "--check", str(APP / "workspace-research-video-intake.js")],
        check=True,
    )
