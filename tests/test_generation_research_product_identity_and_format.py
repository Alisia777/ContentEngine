"""Contracts for safe product identity and editable generation format advice."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
MIGRATION = MIGRATIONS / "202608100005_generation_research_product_identity.sql"
PRESET_MIGRATION = MIGRATIONS / "202608100001_research_ai_center_generation_presets.sql"
RECOMMENDATIONS = ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
AUTOPILOT = ROOT / "web" / "app" / "generation-autopilot.js"
APP = ROOT / "web" / "app" / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(source: str) -> str:
    return re.sub(r"\s+", " ", source.lower()).strip()


def _node_json(script: str) -> object:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return json.loads(result.stdout)


def test_identity_migration_is_ordered_transactional_and_parseable() -> None:
    source = _read(MIGRATION)
    versions = [path.name.split("_", 1)[0] for path in MIGRATIONS.glob("*.sql")]

    assert MIGRATION.is_file()
    assert (MIGRATIONS / "202608100004_research_stage_project_scope.sql").is_file()
    assert (MIGRATIONS / "202608100006_generated_media_lifecycle_folders.sql").is_file()
    assert versions.count("202608100005") == 1
    assert source.lstrip().casefold().startswith("begin;")
    assert source.rstrip().casefold().endswith("commit;")
    assert "notify pgrst, 'reload schema';" in source.casefold()
    parse_sql(source)


def test_latest_public_rpc_keeps_project_acl_and_requires_stable_exact_identity() -> None:
    source = _normalized(_read(MIGRATION))

    assert (
        "create or replace function public.contentengine_generation_research_recommendations"
        in source
    )
    assert "'organization_id', 'project_id', 'product_id', 'product_category'" in source
    assert "content_factory_private.require_workspace_project_access(" in source
    assert "content_factory_private.require_uuid( p_payload, 'product_id' )" in source
    assert "selection.product_id = product_id_value then 4" in source
    assert "count(distinct selection.product_id) as distinct_product_count" in source
    assert "coalesce(sku_identity.distinct_product_count, 0) = 1 then 3" in source
    assert "product_id_value is null and sku_value <> ''" in source
    assert "'can_auto_apply', candidate.match_rank >= 3" in source
    assert "'exact_product_id_or_unique_sku_required', true" in source
    assert "'product_id_precedes_sku', true" in source
    assert "'paid_call_started', false" in source


def test_duplicate_title_with_different_sku_is_category_only_and_never_auto_applies() -> None:
    """Negative contract: copy equality is not identity authority."""

    source = _normalized(_read(MIGRATION))
    title_branch = (
        "when product_name_value <> '' and lower(selection.product_name) = "
        "lower(product_name_value) then 2"
    )

    assert title_branch in source
    assert "when 2 then 'exact_product'" not in source
    assert "when 2 then 'exact_sku'" not in source
    assert "when 2 then 'title_advisory'" in source
    assert (
        "'scope_match', case candidate.match_rank when 4 then 'exact_product' "
        "when 3 then 'exact_sku' else 'category' end"
    ) in source
    assert "candidate.match_rank >= 3" in source
    assert "'product_title_never_auto_applies', true" in source


def test_old_v2_session_namespace_cannot_restore_unsafe_title_lineage() -> None:
    source = _read(RECOMMENDATIONS)

    assert (
        'const STATE_PREFIX = "contentengine.generation.research-recommendation.v3";'
        in source
    )
    assert "contentengine.generation.research-recommendation.v2" not in source
    assert "window.sessionStorage.getItem(stateKey(context))" in source


def test_fixed_generation_modes_normalize_sql_and_ui_format_consistently() -> None:
    sql = _normalized(_read(PRESET_MIGRATION))
    module_url = RECOMMENDATIONS.as_uri()
    value = _node_json(
        f"""
        const mod = await import({json.dumps(module_url)});
        class Control extends EventTarget {{
          constructor(name, value, options) {{
            super();
            this.name = name;
            this.value = value;
            this.defaultValue = value;
            this.dataset = {{}};
            this.options = options.map((candidate) => ({{ value: candidate }}));
          }}
        }}
        class Form extends EventTarget {{
          constructor(mode = 'mock', format = '16:9') {{
            super();
            this.dataset = {{}};
            this.elements = {{
              generation_mode: new Control(
                'generation_mode',
                mode,
                ['mock', 'real_seedance', 'real_photo', 'real_gen4'],
              ),
              format: new Control('format', format, ['9:16', '1:1', '16:9']),
            }};
            this.elements.generation_mode.addEventListener('change', () => {{
              if (this.elements.generation_mode.value === 'real_seedance') {{
                this.elements.format.value = '9:16';
              }} else if (this.elements.generation_mode.value === 'real_photo') {{
                this.elements.format.value = '1:1';
              }}
            }});
          }}
        }}
        function apply(mode, format, position) {{
          const form = new Form();
          let event = null;
          form.addEventListener(
            'contentengine:generation-research-preset-applied',
            (candidate) => {{ event = candidate.detail; }},
          );
          const result = mod.applyResearchRecommendationPresetToForm(form, {{
            selection_id: `55555555-5555-4555-8555-${{String(position).padStart(12, '0')}}`,
            recommendation_position: position,
            scope_match: 'exact_product',
            preset: {{ generation_mode: mode, format }},
          }});
          return {{
            normalized: result.preset.format,
            control: form.elements.format.value,
            event: event?.preset?.format || null,
          }};
        }}
        console.log(JSON.stringify({{
          seedance: apply('real_seedance', '16:9', 1),
          photo: apply('real_photo', '16:9', 2),
          gen4: apply('real_gen4', 'landscape', 3),
          mock: apply('mock', 'square', 1),
        }}));
        """
    )

    assert value["seedance"] == {
        "normalized": "9:16",
        "control": "9:16",
        "event": "9:16",
    }
    assert value["photo"] == {
        "normalized": "1:1",
        "control": "1:1",
        "event": "1:1",
    }
    assert value["gen4"] == {
        "normalized": "16:9",
        "control": "16:9",
        "event": "16:9",
    }
    assert value["mock"] == {
        "normalized": "1:1",
        "control": "1:1",
        "event": "1:1",
    }
    assert "if mode_value = 'real_seedance' then format_value := '9:16'" in sql
    assert "elsif mode_value = 'real_photo' then format_value := '1:1'" in sql
    assert "elsif format_value not in ('9:16', '16:9', '1:1') then" in sql


def test_format_is_normalized_applied_touched_restored_and_opted_out_safely() -> None:
    module_url = RECOMMENDATIONS.as_uri()
    value = _node_json(
        f"""
        const mod = await import({json.dumps(module_url)});
        class Control extends EventTarget {{
          constructor(name, value, options = []) {{
            super();
            this.name = name;
            this.value = value;
            this.defaultValue = value;
            this.dataset = {{}};
            this.options = options.map((candidate) => ({{ value: candidate }}));
          }}
        }}
        class Form extends EventTarget {{
          constructor(elements) {{ super(); this.elements = elements; this.dataset = {{}}; }}
        }}
        const elements = {{
          product_category: new Control('product_category', 'food', ['food']),
          platform: new Control('platform', 'instagram', ['instagram', 'youtube']),
          generation_mode: new Control('generation_mode', 'mock', ['mock', 'real_gen4']),
          duration_seconds: new Control('duration_seconds', '5', ['5', '8']),
          format: new Control('format', '9:16', ['9:16', '1:1', '16:9']),
          brief: new Control('brief', ''),
          campaign_id: new Control('campaign_id', 'campaign-safe'),
          destination_ref: new Control('destination_ref', '@safe'),
          media_id: new Control('media_id', 'media-safe'),
          count: new Control('count', '1'),
          real_spend_confirmation: new Control('real_spend_confirmation', 'CONFIRM'),
        }};
        elements.real_spend_confirmation.checked = true;
        const form = new Form(elements);
        const envelope = {{
          selection_id: '55555555-5555-4555-8555-555555555555',
          recommendation_position: 1,
          scope_match: 'exact_product',
          preset: {{
            product_category: 'food',
            platform: 'youtube',
            generation_mode: 'real_gen4',
            duration_seconds: 5,
            aspect_ratio: 'landscape',
            brief: 'Замысел ИИ',
            campaign_id: 'unsafe-campaign',
            destination_ref: 'unsafe-destination',
            media_id: 'unsafe-media',
            spend_confirmation: 'unsafe-spend',
          }},
          recommendation: {{ position: 1, title: 'Безопасный формат' }},
        }};
        let appliedEvent = null;
        let optOutEvent = null;
        form.addEventListener(
          'contentengine:generation-research-preset-applied',
          (event) => {{ appliedEvent = event.detail; }},
        );
        form.addEventListener(
          'contentengine:generation-research-preset-opt-out',
          (event) => {{ optOutEvent = event.detail; }},
        );
        const applied = mod.applyResearchRecommendationPresetToForm(form, envelope);
        elements.format.value = '1:1';
        const beforeRestore = elements.format.value;
        const restored = mod.restoreResearchRecommendationPresetLineage(
          form,
          envelope,
          {{
            selectionId: envelope.selection_id,
            recommendationPosition: 1,
            appliedFields: applied.appliedFields,
            touchedFields: ['format'],
          }},
        );
        const blocked = mod.resolveResearchPresetAppliedFields({{
          preset: applied.preset,
          exact: true,
          touchedFields: ['format'],
        }});
        mod.optOutResearchRecommendationForForm(form, envelope);
        console.log(JSON.stringify({{
          preset: applied.preset,
          appliedFields: applied.appliedFields,
          appliedEvent,
          beforeRestore,
          afterRestore: elements.format.value,
          restored,
          blocked,
          optOutEvent,
          untouched: {{
            campaign: elements.campaign_id.value,
            destination: elements.destination_ref.value,
            media: elements.media_id.value,
            count: elements.count.value,
            spendValue: elements.real_spend_confirmation.value,
            spendChecked: elements.real_spend_confirmation.checked,
          }},
        }}));
        """
    )

    assert value["preset"]["format"] == "16:9"
    assert "format" in value["appliedFields"]
    assert value["appliedEvent"]["preset"]["format"] == "16:9"
    assert "format" in value["appliedEvent"]["applied_fields"]
    assert value["beforeRestore"] == value["afterRestore"] == "1:1"
    assert value["restored"]["restored"] is True
    assert "format" not in value["blocked"]
    assert value["optOutEvent"]["opted_out"] is True
    assert value["optOutEvent"]["preset"]["format"] == "16:9"
    assert value["untouched"] == {
        "campaign": "campaign-safe",
        "destination": "@safe",
        "media": "media-safe",
        "count": "1",
        "spendValue": "CONFIRM",
        "spendChecked": True,
    }


def test_product_id_survives_media_selection_and_recommendation_payload() -> None:
    module_url = AUTOPILOT.as_uri()
    first_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    second_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    value = _node_json(
        f"""
        const mod = await import({json.dumps(module_url)});
        const base = {{
          selected: true,
          paidReady: true,
          sku: 'DUPLICATE-SKU',
          productName: 'Одинаковое название',
        }};
        const exact = mod.resolveGenerationMediaSelection([
          {{ ...base, id: 'front', productId: '{first_id}' }},
          {{ ...base, id: 'side', productId: '{first_id}' }},
        ], {{ real: true, primaryMediaId: 'side' }});
        const mixed = mod.resolveGenerationMediaSelection([
          {{ ...base, id: 'front', productId: '{first_id}' }},
          {{ ...base, id: 'other', productId: '{second_id}' }},
        ], {{ real: true }});
        const legacy = mod.resolveGenerationMediaSelection([
          {{ ...base, id: 'legacy' }},
        ], {{ real: true }});
        const mixedDryRun = mod.resolveGenerationMediaSelection([
          {{ ...base, id: 'dry-front', productId: '{first_id}' }},
          {{
            ...base,
            id: 'dry-other',
            productId: '{second_id}',
            sku: 'OTHER-SKU',
          }},
        ], {{ real: false }});
        console.log(JSON.stringify({{ exact, mixed, legacy, mixedDryRun }}));
        """
    )

    assert value["exact"]["valid"] is True
    assert value["exact"]["primaryMediaId"] == "side"
    assert value["exact"]["productId"] == first_id
    assert value["mixed"]["valid"] is False
    assert value["mixed"]["code"] == "mixed_product_references"
    assert value["legacy"]["valid"] is True
    assert value["legacy"]["productId"] == ""
    assert value["mixedDryRun"]["valid"] is True
    assert value["mixedDryRun"]["identityConsistent"] is False
    assert value["mixedDryRun"]["productId"] == ""
    assert value["mixedDryRun"]["sku"] == ""

    app = _read(APP)
    recommendations = _read(RECOMMENDATIONS)
    assert "data-media-product-id" in app
    assert "productId: input.dataset.mediaProductId" in app
    assert "form.dataset.identityProductId = productId" in app
    assert "selection.identityConsistent === false" in app
    assert '"duration_seconds", "format", "brief"' in app
    assert "productId: normalizedUuid(form?.dataset?.identityProductId)" in recommendations
    assert "...(context.productId ? { product_id: context.productId } : {})" in recommendations
    assert "context.productId" in recommendations
    assert '"media_id", "primary_media_id"' in recommendations
