from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
CONTRACT = APP / "generation-strategy-intake-contract-v2.js"
SHIM = APP / "generation-strategy-intake-v2.js"
ADAPTER = APP / "generation-strategy-intake-v3.js"
CSS = APP / "generation-strategy-intake-v2.css"
CSS_OVERRIDE = APP / "generation-strategy-intake-v3.css"
MIGRATION = ROOT / "supabase" / "migrations" / "202608140001_generation_intake_v2.sql"
NAMESPACE_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608140002_generation_intake_v2_rpc_namespace.sql"
)
LOADER = APP / "workspace-os-v4-loader.js"


def run_node(expression: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    script = f"""
      import * as intake from {json.dumps(CONTRACT.as_uri())};
      const result = await (async () => {{ {expression} }})();
      console.log(JSON.stringify(result));
    """
    completed = subprocess.run(
        [
            node,
            "--experimental-default-type=module",
            "--input-type=module",
            "-e",
            script,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_three_operator_routes_have_separate_visible_fields() -> None:
    result = run_node(
        """
        return Object.fromEntries(intake.GENERATION_INTAKE_STRATEGIES.map((item) => [
          item.strategy_id,
          {
            formKind: item.form_kind,
            fields: item.fields.map((field) => `${field.id}:${field.required ? 'required' : 'optional'}`),
            recipe: item.preparation_recipe,
            authority: item.authority_strategy_id,
          },
        ]));
        """
    )
    assert result == {
        "copy_video": {
            "formKind": "compact",
            "fields": [
                "source_url:required",
                "product_media_ids:required",
                "description:optional",
            ],
            "recipe": "product_swap",
            "authority": "viral_product_swap",
        },
        "avatar_video": {
            "formKind": "compact",
            "fields": [
                "avatar_wishes:required",
                "source_url:required",
                "description:optional",
            ],
            "recipe": "character_performance",
            "authority": None,
        },
        "strategy_video": {
            "formKind": "full",
            "fields": [],
            "recipe": "generation_spec",
            "authority": "viral_rebuild",
        },
    }


def test_copy_form_accepts_one_source_product_photo_and_empty_description() -> None:
    result = run_node(
        """
        const draft = intake.createGenerationIntakeDraft('copy_video', {
          version: intake.GENERATION_INTAKE_VERSION,
          source_url: 'https://youtu.be/dQw4w9WgXcQ',
          product_media_ids: ['44444444-4444-4444-8444-444444444444'],
          description: '',
        });
        return {
          validation: intake.validateGenerationIntakeDraft(draft),
          brief: intake.generationIntakeInternalBrief(draft),
        };
        """
    )
    assert result["validation"]["ok"] is True
    assert result["validation"]["normalized"]["source_url"] == (
        "https://youtube.com/watch?v=dQw4w9WgXcQ"
    )
    assert "Повтори исходный ролик максимально близко" in result["brief"]
    assert "Дополнительное пожелание" not in result["brief"]


def test_avatar_form_requires_only_wishes_source_and_optional_description() -> None:
    result = run_node(
        """
        const draft = intake.createGenerationIntakeDraft('avatar_video', {
          version: intake.GENERATION_INTAKE_VERSION,
          source_url: 'https://www.youtube.com/shorts/dQw4w9WgXcQ',
          avatar_wishes: 'Уверенная девушка в лаконичном чёрном образе.',
          description: '',
          product_media_ids: [],
        });
        return {
          validation: intake.validateGenerationIntakeDraft(draft),
          brief: intake.generationIntakeInternalBrief(draft),
        };
        """
    )
    assert result["validation"]["ok"] is True
    normalized = result["validation"]["normalized"]
    assert normalized["product_media_ids"] == []
    assert normalized["description"] == ""
    assert "Создай аватара" in result["brief"]


def test_invalid_cross_strategy_fields_fail_closed() -> None:
    result = run_node(
        """
        const copy = intake.createGenerationIntakeDraft('copy_video', {
          version: intake.GENERATION_INTAKE_VERSION,
          source_url: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
          avatar_wishes: 'Это поле не должно попасть в копирование.',
          product_media_ids: ['44444444-4444-4444-8444-444444444444'],
        });
        const avatar = intake.createGenerationIntakeDraft('avatar_video', {
          version: intake.GENERATION_INTAKE_VERSION,
          source_url: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
          avatar_wishes: 'коротко',
          product_media_ids: ['55555555-5555-4555-8555-555555555555'],
        });
        return {
          copy: intake.validateGenerationIntakeDraft(copy),
          avatar: intake.validateGenerationIntakeDraft(avatar),
          badUrl: intake.canonicalGenerationIntakeSourceUrl('http://example.com/video'),
        };
        """
    )
    assert result["copy"]["ok"] is False
    assert {item["code"] for item in result["copy"]["errors"]} == {
        "avatar_wishes_forbidden"
    }
    assert result["avatar"]["ok"] is False
    avatar_errors = {item["code"] for item in result["avatar"]["errors"]}
    assert "avatar_wishes_required" in avatar_errors
    assert "product_media_forbidden" in avatar_errors
    assert result["badUrl"] == ""


def test_dom_adapter_preserves_paid_authority_and_uses_preparation_rpcs() -> None:
    script = ADAPTER.read_text(encoding="utf-8")
    for marker in (
        'const RPC_SOURCE = "contentengine_register_exact_youtube_source"',
        'const RPC_INTAKE = "contentengine_save_generation_intake_v2"',
        'data-generation-strategy-action="SELECT"',
        'strategy?.form_kind !== "full"',
        'generation_intake_preparation_recipe',
        'generation_intake_next_action',
        'event.stopImmediatePropagation()',
        'root?.contract?.paid_call_started !== false',
        'root?.contract?.provider_call_started !== false',
        'root?.contract?.budget_reserved !== false',
        'generation_intake_server_id',
        'Изображение исходного товара из ролика система извлекает сама',
        'У каждого способа своя форма',
    ):
        assert marker in script
    assert "RUNWAYML_API_SECRET" not in script
    assert "Authorization" not in script
    assert "fetch(" not in script
    assert "cloneNode" not in script


def test_compact_intake_server_contract_is_append_only_and_non_paid() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    namespace_sql = NAMESPACE_MIGRATION.read_text(encoding="utf-8")
    for marker in (
        "create table if not exists content_factory.generation_intakes_v2",
        "strategy_id in ('copy_video', 'avatar_video')",
        "creator_save_generation_intake_v2",
        "generation_intake_v2_append_only",
        "'provider_call_started', false",
        "'paid_call_started', false",
        "'budget_reserved', false",
        "'browser_price_authority', false",
        "'browser_provider_authority', false",
        "'human_review_required', true",
        "generation_intake_v2_copy_fields_invalid",
        "generation_intake_v2_avatar_fields_invalid",
        "preparation_recipe in ('product_swap', 'character_performance')",
        "research_exact_youtube_media_attachments",
        "generation_intake_v2_product_media_scope_invalid",
        "source_media_ready_for_preparation",
    ):
        assert marker in sql
    for marker in (
        "rename to contentengine_save_generation_intake_v2",
        "public.contentengine_save_generation_intake_v2(jsonb)",
        "to authenticated, service_role",
        "never reserves budget or starts a provider call",
    ):
        assert marker in namespace_sql
    assert "http_post" not in sql.lower()
    assert "net.http" not in sql.lower()
    assert "http_post" not in namespace_sql.lower()
    assert "net.http" not in namespace_sql.lower()


def test_styles_are_responsive_and_reduced_motion_safe() -> None:
    css = CSS.read_text(encoding="utf-8")
    override = CSS_OVERRIDE.read_text(encoding="utf-8")
    assert css.count("{") == css.count("}")
    assert override.count("{") == override.count("}")
    assert "@media (max-width: 980px)" in css
    assert "@media (max-width: 680px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert 'data-generation-intake-display="compact"' in css
    assert '> :not(.generation-intake-v2)' in override
    assert 'data-state="source-ready"' in override


def test_generation_route_loader_loads_the_new_intake_after_guided_form() -> None:
    loader = LOADER.read_text(encoding="utf-8")
    assert 'generation-strategy-intake-v2.css?v=${GENERATION_INTAKE_BUILD}' in loader
    assert 'generation-strategy-intake-v2.js?v=${GENERATION_INTAKE_BUILD}' in loader
    assert loader.index('workspace-os-v4-generation-guided.js') < loader.index(
        'generation-strategy-intake-v2.js'
    )


def test_new_javascript_files_parse() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")
    assert 'generation-strategy-intake-v3.js' in SHIM.read_text(encoding="utf-8")
    for path in (CONTRACT, SHIM, ADAPTER, LOADER):
        subprocess.run(
            [node, "--check", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
