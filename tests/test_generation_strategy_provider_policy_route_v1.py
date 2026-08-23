from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "supabase/functions/_shared/generation-strategy-edge-contract.js"
CATALOG = ROOT / "supabase/functions/_shared/generation-strategy-catalog.js"
MIGRATION = ROOT / (
    "supabase/migrations/"
    "202608200002_generation_strategy_provider_policy_route_aware_v1.sql"
)


def _read_policy_route(
    provider: str,
    model_key: str,
    provider_path: str,
    poll_kind: str,
    pricing_version: str,
) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy Edge contract tests")
    route = json.dumps(
        {
            "provider": provider,
            "model_key": model_key,
            "provider_path": provider_path,
            "poll_kind": poll_kind,
            "pricing_version": pricing_version,
        }
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "package.json").write_text(
            '{"type":"module"}', encoding="utf-8"
        )
        for source in (CONTRACT, CATALOG):
            (directory / source.name).write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
        (directory / "run.js").write_text(
            f"""
import * as subject from './{CONTRACT.name}';
const route = {route};
const ids = {{
  binding: '11111111-1111-4111-8111-111111111111',
  receipt: '22222222-2222-4222-8222-222222222222',
}};
const h = (value) => value.repeat(64);
const value = {{
  ok: true,
  version: 'generation-strategy-provider-policy-response-v2',
  execution_capabilities: {{
    viral_product_swap: {{
      enabled: true,
      catalog_version: '2026-08-14.v1',
      strategy_id: 'viral_product_swap',
      provider: route.provider,
      model_key: route.model_key,
      recipe: 'product_swap',
      recipe_version: '2026-06',
      provider_path: route.provider_path,
      poll_kind: route.poll_kind,
      pricing_version: route.pricing_version,
    }},
  }},
  context: {{
    strategy_id: 'viral_product_swap',
    provider: route.provider,
    model_key: route.model_key,
    recipe: 'product_swap',
    provider_path: route.provider_path,
    poll_kind: route.poll_kind,
    binding_id: ids.binding,
    binding_hash: h('a'),
    provider_readiness_receipt_id: ids.receipt,
    provider_readiness_receipt_hash: h('b'),
    catalog_version: '2026-08-14.v1',
    recipe_version: '2026-06',
    pricing_version: route.pricing_version,
  }},
  checks: {{
    strategy_binding_current: true,
    generation_spec_approved: true,
    provider_readiness_receipt_current: true,
    provider_readiness_receipt_unconsumed: true,
    provider_route_current: true,
    sql_provider_configuration_enabled: true,
    start_path_integrated: true,
  }},
  blockers: [],
  launch_enabled: true,
  contract: {{
    read_only: true,
    server_authoritative: true,
    provider_call_started: false,
    paid_start_integrated: true,
    receipt_single_use: true,
    launch_enabled: true,
  }},
}};
const result = subject.readGenerationStrategyProviderPolicy(value, {{
  strategyId: 'viral_product_swap',
  provider: route.provider,
  pricingVersion: route.pricing_version,
  bindingId: ids.binding,
  bindingHash: h('a'),
  receiptId: ids.receipt,
  receiptHash: h('b'),
}});
process.stdout.write(JSON.stringify(result));
""",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "run.js"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    ("provider", "model_key", "provider_path", "poll_kind", "pricing_version"),
    [
        (
            "runway",
            "aleph2",
            "/v1/video_to_video",
            "runway_task",
            "runway-recipe-credits-2026-08-14.v1",
        ),
        (
            "fal",
            "fal-ai/pika/v2/pikaswaps",
            "fal-ai/pika/v2/pikaswaps",
            "fal_request",
            "fal-usd-per-run-2026-08-18.v1",
        ),
        (
            "fal",
            "fal-ai/kling-video/o3/pro/video-to-video/edit",
            "fal-ai/kling-video/o3/pro/video-to-video/edit",
            "fal_request",
            "fal-usd-per-second-2026-08-18.v1",
        ),
        # Движки «Копии», заведённые 23.08.2026 (миграция 202608230020).
        (
            "fal",
            "fal-ai/kling-video/o3/standard/video-to-video/edit",
            "fal-ai/kling-video/o3/standard/video-to-video/edit",
            "fal_request",
            "fal-usd-per-second-kling-standard-2026-08-23.v1",
        ),
        (
            "fal",
            "alibaba/happy-horse/video-edit",
            "alibaba/happy-horse/video-edit",
            "fal_request",
            "fal-usd-per-second-happy-horse-2026-08-23.v1",
        ),
        (
            "fal",
            "bytedance/seedance-2.5/reference-to-video",
            "bytedance/seedance-2.5/reference-to-video",
            "fal_request",
            "fal-usd-per-second-bytedance-2-5-2026-08-23.v1",
        ),
        (
            "fal",
            "minimax/h3/reference-to-video",
            "minimax/h3/reference-to-video",
            "fal_request",
            "fal-usd-per-second-minimax-h3-2026-08-23.v1",
        ),
    ],
)
def test_exact_product_swap_provider_policy_routes_are_accepted(
    provider: str,
    model_key: str,
    provider_path: str,
    poll_kind: str,
    pricing_version: str,
) -> None:
    result = _read_policy_route(
        provider, model_key, provider_path, poll_kind, pricing_version
    )
    assert result == {
        "launchEnabled": True,
        "blockers": [],
        "provider": provider,
        "modelKey": model_key,
        "pollKind": poll_kind,
    }


def test_unknown_fal_product_swap_route_fails_closed() -> None:
    assert _read_policy_route(
        "fal",
        "fal-ai/unknown/video-to-video",
        "fal-ai/unknown/video-to-video",
        "fal_request",
        "fal-usd-per-run-2026-08-18.v1",
    ) is None


def test_known_fal_model_with_the_wrong_poll_contract_fails_closed() -> None:
    assert _read_policy_route(
        "fal",
        "fal-ai/pika/v2/pikaswaps",
        "fal-ai/pika/v2/pikaswaps",
        "runway_task",
        "fal-usd-per-run-2026-08-18.v1",
    ) is None


def test_append_only_migration_replaces_the_latest_route_pricing_authority() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    policy = sql.split(
        "create or replace function public.system_generation_strategy_provider_policy(",
        1,
    )[1].split(
        "revoke all on function\n"
        "  public.system_generation_strategy_provider_policy(jsonb)",
        1,
    )[0]

    assert MIGRATION.name.startswith("202608200002_")
    assert "202608190013" in sql
    assert (
        "create or replace function "
        "public.system_generation_strategy_provider_policy(" in sql
    )
    assert "generation_strategy_provider_route_allowed" in sql
    assert "generation_strategy_route_provider_current" in sql
    assert "do $readiness_exact_route$" in sql
    assert "exact signed route" in sql
    assert "generation-strategy-provider-policy-response-v2" in sql
    assert "'model_key', route_model_key_value" in policy
    assert "route_current_value" in policy
    assert "organization_id_value, 'runway', 'gen4_turbo'" not in policy
