import base64
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
EXPERIENCE = (ROOT / "web" / "app" / "portal-experience.js").read_text(encoding="utf-8")
CSS = (ROOT / "web" / "app" / "portal-experience.css").read_text(encoding="utf-8")


def _node(script: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for multimodel archive UI tests")
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


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_archive_ui_stays_inside_existing_generation_owner() -> None:
    archive = _between(APP, "function generationArchiveMarkup", "async function submitGenerationArchiveFilters")
    repeat = _between(APP, "function repeatGenerationSettingsFromArchive", "function productResearchPaidStartContext")

    assert APP.count('id="generation-archive-filter-form"') == 1
    for control in [
        'name="provider"',
        'name="model"',
        'name="content_kind"',
        'name="selection_source"',
        'name="quality_status"',
    ]:
        assert control in archive
    assert "Модель не зафиксирована · старый запуск" in APP
    assert "Повторить настройки" in APP
    assert 'data-action="repeat-generation-settings"' in APP
    assert "contentengine:generation-repeat-settings" in repeat
    assert "clearAllGenerationPreflightRetries()" in repeat
    assert "state.generationPreflight.entries.clear()" in repeat
    assert "resetGenerationSpecState()" in repeat
    assert "real_spend_confirmation.checked = false" in repeat
    assert ".generation-model-record" in CSS
    assert ".generation-model-record__quality" in CSS
    assert "generation_archive_provider_invalid" in API
    assert "generation_archive_selection_source_invalid" in API


def test_archive_filters_match_provider_model_and_honest_server_snapshot() -> None:
    encoded = base64.b64encode(EXPERIENCE.encode("utf-8")).decode("ascii")
    result = _node(
        f"""
        const subject = await import('data:text/javascript;base64,{encoded}');
        const base = {{
          created_at: '2026-08-13T10:00:00Z', status: 'succeeded',
          sku: 'SKU-1', product_name: 'Товар', content_kind: 'video',
          generation_selection_snapshot: {{
            provider: 'runway', model: 'gen4.5', model_public_label: 'Gen-4.5',
            selection_source: 'manual_choice', acceptance_status_at_launch: 'accepted',
          }},
        }};
        const legacySpoof = {{
          ...base,
          id: 'legacy-spoof',
          generation_selection_snapshot: null,
          provider: null,
          model: null,
          model_public_label: null,
          content_kind: null,
          selection_source: null,
          quality_status: null,
          parameters: {{
            provider: 'google', model: 'veo-3.1-lite-generate-preview',
            model_public_label: 'Veo 3.1 Lite', content_kind: 'video',
            selection_source: 'system_recommendation', quality_status: 'unproven',
            generation_selection_snapshot: {{
              provider: 'google', model: 'veo-3.1-lite-generate-preview',
              model_public_label: 'Veo 3.1 Lite', selection_source: 'system_recommendation',
              acceptance_status_at_launch: 'unproven',
            }},
          }},
        }};
        const items = [base, {{ ...base, id: 'google', generation_selection_snapshot: {{
          ...base.generation_selection_snapshot, provider: 'google', model: 'veo-3.1-lite-generate-preview',
          model_public_label: 'Veo 3.1 Lite', selection_source: 'system_recommendation',
          acceptance_status_at_launch: 'unproven',
        }} }}, legacySpoof];
        const ids = (filters) => subject.filterGenerationBatches(items, {{ period: 'all', ...filters }}).map((item) => item.id || 'runway');
        process.stdout.write(JSON.stringify({{
          runway: ids({{ provider: 'runway' }}),
          google: ids({{ provider: 'google' }}),
          model: ids({{ model: 'gen4.5' }}),
          manual: ids({{ selectionSource: 'manual_choice' }}),
          experimental: ids({{ qualityStatus: 'unproven' }}),
          searchPublic: ids({{ query: 'Veo 3.1 Lite' }}),
          legacySpoofNotReinterpreted: !ids({{ provider: 'google' }}).includes('legacy-spoof'),
        }}));
        """
    )
    assert result == {
        "runway": ["runway"],
        "google": ["google"],
        "model": ["runway"],
        "manual": ["runway"],
        "experimental": ["google"],
        "searchPublic": ["google"],
        "legacySpoofNotReinterpreted": True,
    }


def test_archive_row_renders_exact_snapshot_and_legacy_state_without_guessing() -> None:
    functions = _between(APP, "function generationTable", "function generationBatchDetails")
    result = _node(
        f"""
        const state = {{ realGenerationResults: new Map() }};
        function escapeHtml(value) {{ return String(value ?? ''); }}
        function formatNumber(value) {{ return String(value); }}
        function formatDate() {{ return '13.08.2026'; }}
        function generationWeekLabel() {{ return '11 — 17 авг.'; }}
        function generationFailureMessage() {{ return ''; }}
        function trustedCachedGenerationUrl() {{ return ''; }}
        function generationActionsMarkup() {{ return ''; }}
        function generationVideoReferenceLineageMarkup() {{ return ''; }}
        function generatedVideoTechnicalQaMarkup() {{ return ''; }}
        function generationStageMarkup() {{ return 'Готово'; }}
        function generationCostMarkup() {{ return 'Стоимость'; }}
        function statusBadge() {{ return 'Готово'; }}
        function formatGenerationUsd(value) {{ return '$' + (Number(value) / 100).toFixed(2); }}
        let exact = true;
        function generationBatchDetails(item) {{ return {{
          item, parameters: {{}}, real: true, jobId: 'job-1', status: 'succeeded',
          failureCode: '', photo: false, duration: 8, audio: true,
          reconciliationRequired: false, transientError: '', checkedAt: null,
          actualMinor: 215,
          selectionSnapshot: exact ? {{
            provider: 'runway', model: 'seedance2_fast', model_public_label: 'Seedance 2 Fast',
            selection_source: 'manual_choice', recommendation_reason_codes: ['manual_override'],
            recommendation_catalog_version: '2026-08-13.v1', pricing_version: 'runway-credits-2026-08-13.v1',
            estimated_cost_minor: 232, requested_duration_seconds: 8, requested_ratio: '9:16',
            requested_resolution: '720p', requested_audio: true, input_mode: 'image', reference_count: 3,
            acceptance_status_at_launch: 'accepted', provider_readiness_receipt_id: '',
          }} : null,
        }}; }}
        {functions}
        const item = {{ id: 'batch-1', name: 'Запуск', sku: 'SKU-1', created_at: '2026-08-13T10:00:00Z' }};
        const current = generationTable([item], false);
        exact = false;
        const legacy = generationTable([item], false);
        process.stdout.write(JSON.stringify({{
          current: [
            'Seedance 2 Fast', 'RUNWAY', 'Ручной выбор человека', 'Проверено',
            '9:16 · 720p', '3 реф.', 'Оценка $2.32 · фактически $2.15',
            'seedance2_fast', '2026-08-13.v1', 'Повторить настройки',
          ].every((copy) => current.includes(copy)),
          legacyHonest: legacy.includes('Модель не зафиксирована · старый запуск'),
          legacyNoRepeat: !legacy.includes('Повторить настройки'),
        }}));
        """
    )
    assert result == {"current": True, "legacyHonest": True, "legacyNoRepeat": True}
