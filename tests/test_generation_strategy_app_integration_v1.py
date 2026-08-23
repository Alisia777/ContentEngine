from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API_PATH = ROOT / "web/app/supabase-api.js"
API = API_PATH.read_text(encoding="utf-8")
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(
    encoding="utf-8"
)
GUIDED = (ROOT / "web/app/workspace-os-v4-generation-guided.js").read_text(
    encoding="utf-8"
)
RUNTIME = (ROOT / "web/app/generation-strategy-runtime.js").read_text(
    encoding="utf-8"
)


def _frozen_string_list(source: str, name: str) -> tuple[str, ...]:
    """Return a `const NAME = Object.freeze([...])` list of string literals."""

    match = re.search(
        rf"const {re.escape(name)} = Object\.freeze\(\[(.*?)\]\);",
        source,
        re.DOTALL,
    )
    assert match is not None, f"{name} is not a frozen list literal"
    values = tuple(re.findall(r'"([^"]+)"', match.group(1)))
    assert values, f"{name} is empty"
    return values


def _top_level_function(source: str, name: str) -> str:
    marker = f"function {name}("
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    quote: str | None = None
    escaped = False
    template_expression_depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if quote == "`" and char == "$" and source[index + 1 : index + 2] == "{":
                template_expression_depth += 1
                continue
            if char == quote and template_expression_depth == 0:
                quote = None
                continue
            if quote == "`" and template_expression_depth:
                if char == "{":
                    template_expression_depth += 1
                elif char == "}":
                    template_expression_depth -= 1
                continue
            continue
        if char in {'"', "'", "`"}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Function {name} is incomplete")


def _source_slice(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def _evaluate_archive_details(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy archive contracts")
    parser = _top_level_function(APP, "generationStrategyExecutionArchiveDetails")
    script = f"""
{parser}
const strategy = {{strategyId: 'viral_product_swap'}};
const selection = () => ({{
  version: '2026-08-14.v1',
  strategy_id: 'viral_product_swap',
  recipe_version: '2026-06',
  duration_seconds: 10,
  ratio: '',
  resolution: '720p',
  audio: true,
}});
const price = () => ({{
  version: 'generation-strategy-price-snapshot-v1',
  strategy_id: 'viral_product_swap',
  provider: 'runway',
  recipe: 'product_swap',
  catalog_version: '2026-08-14.v1',
  recipe_version: '2026-06',
  pricing_version: 'runway-recipe-credits-2026-08-14.v1',
  display_only: true,
  requires_fresh_server_price: true,
  price_hash: null,
  spend_confirmation: null,
  estimated_cost_minor: 428,
  estimated_credits: 428,
}});
const details = (priceOverrides) => generationStrategyExecutionArchiveDetails(
  {{
    generation_strategy_execution_selection: selection(),
    generation_strategy_price_reference: {{...price(), ...priceOverrides}},
  }},
  strategy,
);
const value = {expression};
process.stdout.write(JSON.stringify(value));
"""
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "archive.mjs"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _evaluate_repeat(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy repeat contracts")
    repeat_normalizer = _top_level_function(
        APP, "normalizeGenerationStrategyRepeatEnvelope"
    )
    uuid_helper = _top_level_function(APP, "contentReviewUuid")
    script = f"""
{uuid_helper}
{repeat_normalizer}
const jobId = '11111111-1111-4111-8111-111111111111';
const specId = '22222222-2222-4222-8222-222222222222';
const productId = '33333333-3333-4333-8333-333333333333';
const sourceId = '44444444-4444-4444-8444-444444444444';
const avatarId = '55555555-5555-4555-8555-555555555555';
const productMediaId = '66666666-6666-4666-8666-666666666666';
const response = () => ({{
  ok: true,
  version: 'generation-strategy-repeat-response-v1',
  generation_job_id: jobId,
  legacy_strategy_absent: false,
  repeat_data: {{
    version: 'generation-strategy-repeat-data-v2',
    generation_job_id: jobId,
    strategy_id: 'viral_avatar_ugc',
    source_basis: 'exact_source_video',
    spec_strategy_binding_id: '77777777-7777-4777-8777-777777777777',
    spec_id: specId,
    spec_version: 4,
    spec_hash: 'a'.repeat(64),
    product_id: productId,
    job_strategy_snapshot_hash: 'b'.repeat(64),
    live_assets_current: true,
    selection_template: {{
      version: '2026-08-14.v1',
      strategy_id: 'viral_avatar_ugc',
      recipe_version: '2026-06',
      duration_seconds: 8,
      // «Дуэт» измеряется разрешением: кадр задаёт исходник.
      resolution: '720p',
      audio: true,
      // Ассет ровно один — комментируемый ролик.
      assets: [
        {{role:'source_video',media_id:sourceId,duration_seconds:8}},
      ],
      attestations: {{
        source_media_rights_confirmed:false,
        transformative_use_confirmed:false,
        product_assets_rights_confirmed:false,
        depicted_people_consent_confirmed:false,
        avatar_likeness_consent_confirmed:false,
      }},
    }},
    price_reference: {{
      display_only:true,
      requires_fresh_server_price:true,
      price_hash:null,
      spend_confirmation:null,
    }},
    strategy_prompt_hash:'c'.repeat(64),
    binding_id:null,
    binding_hash:null,
    readiness_receipt_id:null,
    readiness_receipt_hash:null,
    confirmation:false,
    requires_fresh_binding:true,
    requires_fresh_human_confirmation:true,
    requires_fresh_provider_readiness_receipt:true,
    requires_fresh_price_confirmation:true,
  }},
  contract: {{
    read_only:true,
    legacy_null_preserved:true,
    confirmation_reused:false,
    readiness_receipt_reused:false,
    provider_call_started:false,
    mutation_started:false,
    selection_authority_reused:false,
    media_hash_authority_reused:false,
    attestations_reset:true,
    price_confirmation_reset:true,
  }},
}});
const value = {expression};
process.stdout.write(JSON.stringify(value));
"""
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "repeat.mjs"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_repeat_template_is_exact_and_never_restores_human_confirmations() -> None:
    result = _evaluate_repeat(
        "normalizeGenerationStrategyRepeatEnvelope(response(), jobId)"
    )
    assert result == {
        "strategyId": "viral_avatar_ugc",
        "liveAssetsCurrent": True,
        "values": {
            "generation_strategy_id": "viral_avatar_ugc",
            "generation_strategy_product_id":
                "33333333-3333-4333-8333-333333333333",
            "generation_strategy_duration_seconds": 8,
            # Кадр «Дуэту» задаёт исходник: измерение идёт разрешением, а поле
            # соотношения сторон остаётся пустым.
            "generation_strategy_ratio": "",
            "generation_strategy_resolution": "720p",
            "generation_strategy_audio": "true",
            "generation_strategy_source_video_id":
                "44444444-4444-4444-8444-444444444444",
            # Ни лица, ни товара в повторе нет: ведущий приходит из библиотеки
            # проекта, а товара у стратегии нет вовсе.
            "generation_strategy_avatar_media_id": "",
            "generation_strategy_original_product_media_id": "",
            "generation_strategy_product_media_ids": [],
        },
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "value.repeat_data.selection_template.attestations.source_media_rights_confirmed=true",
        "value.repeat_data.price_reference.price_hash='d'.repeat(64)",
        "value.repeat_data.confirmation=true",
        "value.contract.selection_authority_reused=true",
        # Возврат прежней формы «Аватара»: к единственному исходнику дописан
        # ассет лица. Повтор обязан отвергнуть такой шаблон, а не собрать наряд
        # по составу, которого у стратегии больше нет.
        "value.repeat_data.selection_template.assets.push("
        "{role:'avatar_image',media_id:avatarId})",
        # Второй исходник — тоже не дуэт: комментируют один ролик.
        "value.repeat_data.selection_template.assets.push("
        "{role:'source_video',media_id:productMediaId,duration_seconds:8})",
    ],
)
def test_repeat_rejects_reused_authority_or_changed_identity(mutation: str) -> None:
    result = _evaluate_repeat(
        f"(()=>{{const value=response(); {mutation}; return "
        "normalizeGenerationStrategyRepeatEnvelope(value,jobId);})()"
    )
    assert result is None


def test_repeat_handler_uses_dedicated_rpc_and_clears_every_paid_authority() -> None:
    handler = _top_level_function(APP, "repeatGenerationStrategyFromArchive")
    for marker in (
        "state.api.generationStrategyRepeatData",
        "normalizeGenerationStrategyRepeatEnvelope",
        "clearAllGenerationPreflightRetries();",
        "state.generationPreflight.entries.clear();",
        "resetGenerationSpecState();",
        'form.elements.real_spend_confirmation.checked = false',
        'form.elements.real_spend_confirmation.value = ""',
        'input.checked = false',
        '"contentengine:generation-restore-strategy"',
    ):
        assert marker in handler
    assert "startRealGeneration" not in handler
    assert "bindGenerationStrategy" not in handler

    click_handler = _source_slice(
        APP,
        "async function handleClick(event)",
        "async function handleSubmit(event)",
    )
    assert 'action === "repeat-generation-strategy"' in click_handler
    assert "repeatGenerationStrategyFromArchive(control.dataset.jobId, control)" in click_handler


def test_guided_restore_waits_for_server_candidates_and_never_restores_rights() -> None:
    restore = _top_level_function(GUIDED, "applyStrategyRestore")
    loader = _source_slice(
        GUIDED,
        "async function loadGenerationStrategyAssets",
        "function replaceStrategyOptions",
    )
    for marker in (
        "runtime.pendingStrategyRestore",
        "runtime.strategyAssetStatus",
        "loadGenerationStrategyAssets(form, { append: loadNextProductPage })",
        'input[data-generation-strategy-attestation]',
        "input.checked = false",
        "generation_strategy_product_media_ids",
    ):
        assert marker in restore
    assert "applyStrategyRestore(form, pendingRestore.values)" in loader


def test_repeat_product_plan_restores_exact_server_order_and_primary() -> None:
    failure = _top_level_function(
        GUIDED, "generationStrategyRepeatProductFailure"
    )
    planner = _top_level_function(GUIDED, "generationStrategyRepeatProductPlan")
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy repeat product contracts")
    script = rf"""
const STRATEGY_REPEAT_MEDIA_ID_PATTERN =
  /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-8][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/iu;
const PRODUCT_SWAP_REPEAT_MEDIA_LIMIT = 10;
const generationStrategyAssetEligibility = (asset, strategyId, role) => ({{
  eligible: asset?.eligible === true
    && asset.eligible_strategy_roles?.some((entry) => (
      entry.strategy_id === strategyId && entry.role === role
    )),
  blockers: Object.freeze([]),
}});
{failure}
{planner}
const projectId = '11111111-1111-4111-8111-111111111111';
const productId = '7d97ff56-747f-45c1-8458-aedf3aaa9c9a';
const ids = Object.freeze([
  'bcd03126-a319-47ce-82bb-2860ff9e1aad',
  'ee5e7c10-cde8-487f-ace2-3349d8286cd2',
  '4c7abc6d-598e-4cd2-ae63-98531c8f6056',
  '72bdf85f-4f43-4372-bc5f-0ad2966fff60',
]);
const asset = (id, overrides = {{}}) => Object.freeze({{
  id,
  kind: 'product_photo',
  project_id: projectId,
  status: 'ready',
  rights_confirmed: true,
  product_id: productId,
  product_identity: Object.freeze({{
    product_id: productId,
    sku: 'CHELSEA-SUEDE-FUR-BLACK',
    product_name: 'Ботинки-челси замшевые на меху, чёрные',
    identity_verified: true,
  }}),
  eligible: true,
  eligible_strategy_roles: Object.freeze([
    Object.freeze({{strategy_id:'viral_product_swap',role:'new_product_image'}}),
  ]),
  filename: `${{id}}.jpg`,
  ...overrides,
}});
const assets = Object.freeze(ids.map((id) => asset(id)));
const page = (nextAssets = assets) => Object.freeze({{
  version: 'generation-strategy-asset-candidates-response-v1',
  project_id: projectId,
  assets: Object.freeze([...nextAssets]),
  contract: Object.freeze({{
    read_only: true,
    object_names_returned: false,
    hashes_returned: false,
    signed_urls_returned: false,
  }}),
}});
const plan = generationStrategyRepeatProductPlan(page(), ids, productId);
const missing = generationStrategyRepeatProductPlan(
  page(assets.slice(0, 3)), ids, productId,
);
const duplicate = generationStrategyRepeatProductPlan(
  page(), [ids[0], ids[0]], productId,
);
const badRights = generationStrategyRepeatProductPlan(
  page([asset(ids[0], {{rights_confirmed:false}}), ...assets.slice(1)]),
  ids,
  productId,
);
process.stdout.write(JSON.stringify({{
  plan: {{
    ok: plan.ok,
    product_id: plan.product_id,
    primary_media_id: plan.primary_media_id,
    media_ids: plan.media_ids,
    asset_ids: plan.assets.map((item) => item.id),
    sku: plan.assets[0]?.product_identity?.sku,
    frozen: Object.isFrozen(plan) && Object.isFrozen(plan.media_ids),
  }},
  missing,
  duplicate,
  badRights,
}}));
"""
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "repeat-product-plan.mjs"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    outcome = json.loads(result.stdout)
    assert outcome["plan"] == {
        "ok": True,
        "product_id": "7d97ff56-747f-45c1-8458-aedf3aaa9c9a",
        "primary_media_id": "bcd03126-a319-47ce-82bb-2860ff9e1aad",
        "media_ids": [
            "bcd03126-a319-47ce-82bb-2860ff9e1aad",
            "ee5e7c10-cde8-487f-ace2-3349d8286cd2",
            "4c7abc6d-598e-4cd2-ae63-98531c8f6056",
            "72bdf85f-4f43-4372-bc5f-0ad2966fff60",
        ],
        "asset_ids": [
            "bcd03126-a319-47ce-82bb-2860ff9e1aad",
            "ee5e7c10-cde8-487f-ace2-3349d8286cd2",
            "4c7abc6d-598e-4cd2-ae63-98531c8f6056",
            "72bdf85f-4f43-4372-bc5f-0ad2966fff60",
        ],
        "sku": "CHELSEA-SUEDE-FUR-BLACK",
        "frozen": True,
    }
    for case, code in (
        ("missing", "repeat_product_asset_missing"),
        ("duplicate", "repeat_product_ids_invalid"),
        ("badRights", "repeat_product_asset_invalid"),
    ):
        assert outcome[case]["ok"] is False
        assert outcome[case]["code"] == code
        assert outcome[case]["media_ids"] == []
        assert outcome[case]["primary_media_id"] == ""


def test_repeat_product_materialization_keeps_server_identity_and_native_cap() -> None:
    materialize = _top_level_function(
        GUIDED, "materializeStrategyRepeatProductPlan"
    )
    synthetic = _source_slice(
        GUIDED,
        "function strategyRepeatSyntheticProductOption",
        "function materializeStrategyRepeatProductPlan",
    )
    restore = _top_level_function(GUIDED, "applyStrategyRestore")
    for marker in (
        'input.dataset.mediaIdentityVerified = "true"',
        'input.dataset.mediaRightsConfirmed = "true"',
        "input.dataset.mediaProductId = identity.product_id",
        "input.dataset.mediaSku = identity.sku",
        "input.dataset.mediaProductName = identity.product_name",
        'option.dataset.paidReady = "true"',
    ):
        assert marker in synthetic
    for marker in (
        "plan.primary_media_id",
        "JSON.stringify(exactOrder) !== JSON.stringify(plan.media_ids)",
        'new Event("change", { bubbles: true })',
    ):
        assert marker in materialize
    assert 'strategyId === "viral_product_swap"' in restore
    assert "PRODUCT_SWAP_REPEAT_MEDIA_LIMIT = 10" in GUIDED
    assert "MAX_REAL_GENERATION_REFERENCES = 5" in (
        ROOT / "web/app/generation-autopilot.js"
    ).read_text(encoding="utf-8")


def test_strategy_catalog_failure_keeps_bounded_code_and_logs_no_payload() -> None:
    helper = _top_level_function(GUIDED, "generationStrategyCatalogFailure")
    loader = _source_slice(
        GUIDED,
        "async function loadStrategyCatalog",
        "function routePath",
    )
    for marker in (
        '"catalog_unavailable"',
        "/^[a-z0-9_]{3,96}$/u",
        ".slice(0, 300)",
        'console.warn("generation strategy catalog load failed"',
        "code: failure.code",
        "message: failure.message",
        "error: { code: failure.code, field: failure.field }",
    ):
        assert marker in helper + loader
    for forbidden in (
        "console.error",
        "console.log",
        "error.stack",
        "error.details",
        "error.response",
        "requestBody",
        "accessToken",
    ):
        assert forbidden not in loader


def test_archive_renders_only_frozen_strategy_selection_and_display_price() -> None:
    parser = _top_level_function(APP, "generationStrategyExecutionArchiveDetails")
    markup = _source_slice(
        APP,
        "function generationStrategyArchiveMarkup",
        "function generationBatchDetails",
    )
    # Провайдер архива перестал быть словом "runway", но проверка обязана
    # остаться закрытой: набор движков и набор версий прайса берутся из
    # замороженного рантайма, поэтому разойтись они не могут. Появится третий
    # маршрут — тест упадёт на архиве, а не в проде.
    providers = _frozen_string_list(RUNTIME, "STRATEGY_PROVIDERS")
    pricing_versions = _frozen_string_list(RUNTIME, "PRICING_VERSIONS")
    assert len(providers) > 1, "проверка архива обязана быть многопровайдерной"
    assert "runway" in providers and "fal" in providers
    for marker in (
        '"generation_strategy_execution_selection"',
        '"generation_strategy_price_reference"',
        'price.display_only !== true',
        'price.requires_fresh_server_price !== true',
        'price.price_hash !== null',
        'price.spend_confirmation !== null',
        "const routePriceMatches = (",
        'provider === "runway"',
        'provider === "fal"',
        "|| !routePriceMatches",
        "].includes(price.pricing_version)",
        *(f'"{version}"' for version in pricing_versions),
    ):
        assert marker in parser
    assert "state.generationModelCatalog" not in parser
    assert "generationSkuForForm" not in parser
    assert "strategyExecution" in markup
    assert "formatGenerationUsd(execution.estimatedCostMinor)" in markup


def test_archive_accepts_every_known_route_and_rejects_unknown_ones() -> None:
    # Прежний тест сторожил ОТСУТСТВИЕ второго маршрута: он требовал маркер
    # price.provider !== "runway". Сторожить надо обратное — что архив
    # принимает каждый включённый маршрут и по-прежнему отвергает всё, чего в
    # закрытых наборах нет. Проверка исполняемая: строку в исходнике можно
    # написать и не выполнить.
    outcome = _evaluate_archive_details(
        """({
          runway: details({}),
          falPerRun: details({
            provider: 'fal',
            pricing_version: 'fal-usd-per-run-2026-08-18.v1',
            estimated_cost_minor: 47,
            estimated_credits: 47,
          }),
          falPerSecond: details({
            provider: 'fal',
            pricing_version: 'fal-usd-per-second-2026-08-18.v1',
            estimated_cost_minor: 95,
            estimated_credits: 95,
          }),
          unknownProvider: details({provider: 'openai'}),
          emptyProvider: details({provider: ''}),
          unknownPricingVersion: details({
            pricing_version: 'fal-usd-per-run-2026-09-01.v1',
          }),
          displayOnlyDropped: details({display_only: false}),
          priceHashLeaked: details({price_hash: 'a'.repeat(64)}),
        })"""
    )
    assert outcome["runway"] == {
        "provider": "runway",
        "recipe": "product_swap",
        "durationSeconds": 10,
        "ratio": "",
        "resolution": "720p",
        "audio": True,
        "estimatedCostMinor": 428,
        "pricingVersion": "runway-recipe-credits-2026-08-14.v1",
    }
    assert outcome["falPerRun"]["provider"] == "fal"
    assert outcome["falPerRun"]["estimatedCostMinor"] == 47
    assert outcome["falPerRun"]["pricingVersion"] == "fal-usd-per-run-2026-08-18.v1"
    assert outcome["falPerSecond"]["pricingVersion"] == (
        "fal-usd-per-second-2026-08-18.v1"
    )
    assert outcome["falPerSecond"]["provider"] == "fal"
    for rejected in (
        "unknownProvider",
        "emptyProvider",
        "unknownPricingVersion",
        "displayOnlyDropped",
        "priceHashLeaked",
    ):
        assert outcome[rejected] is None, rejected


def test_strategy_runtime_is_a_separate_branch_before_legacy_mode_and_sku() -> None:
    submit_batch = _top_level_function(APP, "submitGenerationBatch")
    submit_strategy = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function pollGenerationStrategyStatuses",
    )
    assert submit_batch.index("if (strategyId)") < submit_batch.index(
        'const mode = String(values.get("generation_mode")'
    )
    assert "generationStrategySelectionsForForm(form)" in submit_batch
    assert "submitGenerationStrategyExactTen(" in submit_batch
    assert "submitGenerationStrategy(" in submit_batch
    assert "submitRealGeneration(" in submit_batch
    for forbidden in (
        "generationSkuForForm",
        "runGenerationPreflightForPaidStart",
        "startRealGeneration",
        "generation_selection_snapshot",
    ):
        assert forbidden not in submit_strategy
    for required in (
        "generationStrategyRuntimeBindRequest",
        "generationStrategyRuntimePreflightRequest",
        "generationStrategyRuntimeStartRequest",
        "generationStrategyRuntimeStatusRequest",
        "buildGenerationStrategySpecPrepareRequest",
        "buildGenerationStrategySpecApprovalRequest",
        "createGenerationStrategyQueue",
        "planGenerationStrategyQueueFreeWork",
        "planGenerationStrategyQueueSequentialStarts",
        "state.api.bindGenerationStrategy",
        "state.api.preflightGenerationStrategy",
        "requestApi.startGenerationStrategy",
        "requestApi.generationStrategyStatus",
    ):
        assert required in APP


def test_product_swap_dispatch_is_exactly_one_and_character_performance_is_closed() -> None:
    submit_batch = _top_level_function(APP, "submitGenerationBatch")
    selections = _top_level_function(APP, "generationStrategySelectionsForForm")

    assert "generationStrategySourceProjectionForForm(form)?.required_count" in selections
    assert "[1, 10].includes(requiredCount)" in selections
    assert "value.length === requiredCount" in selections

    # «Копия» и «Аватар» — оба один исходник на один результат, поэтому идут
    # одной ветвью. Порядок проверок внутри неё — часть защиты: количество
    # исходников и количество выборов сверяются ДО вызова платного старта.
    swap_branch = submit_batch.index('strategyId === "viral_product_swap"')
    swap_count = submit_batch.index("sourceProjection.required_count === 1", swap_branch)
    swap_selection_count = submit_batch.index("strategySelections?.length === 1", swap_count)
    swap_submit = submit_batch.index("await submitGenerationStrategy(", swap_selection_count)
    assert swap_branch < swap_count < swap_selection_count < swap_submit
    assert 'strategyId === "viral_avatar_ugc"' in submit_batch[swap_branch:swap_count]

    # «Создание» больше НЕ закрывается клиентским стоп-краном, и это правка
    # намерения, а не ослабление. 23.08.2026 замок переехал на сервер и
    # перестал быть именным: миграция 202608230010 отвергает привязку любой
    # стратегии, у которой нет ни одной включённой и разрешённой строки реестра
    # маршрутов, — отказом generation_strategy_no_executable_route ДО строки в
    # книге трат и ДО создания наряда. Витрина считает доступность по тому же
    # признаку (202608230011).
    #
    # Клиентский флаг был назван временным в собственном комментарии и выключал
    # не только платный старт, но и БЕСПЛАТНУЮ подготовку ТЗ: она вызывается
    # только изнутри submitGenerationStrategyExactTen, а тот стоял после
    # стоп-крана. Оператор не мог ни заплатить, ни подготовить.
    assert "REBUILD_PAID_START_CLOSED" not in submit_batch
    rebuild_branch = submit_batch.index('strategyId === "viral_rebuild"', swap_submit)
    rebuild_count = submit_batch.index("sourceProjection.required_count === 10", rebuild_branch)
    rebuild_selection_count = submit_batch.index(
        "strategySelections?.length === 10", rebuild_count
    )
    rebuild_submit = submit_batch.index(
        "await submitGenerationStrategyExactTen(", rebuild_selection_count
    )
    assert swap_submit < rebuild_branch
    assert rebuild_branch < rebuild_count < rebuild_selection_count < rebuild_submit
    # Порядок проверок внутри ветки — по-прежнему часть защиты: количество
    # исходников и количество выборов сверяются ДО вызова платного старта.
    assert "generation_strategy_no_executable_route" in EDGE

    # Прежний клиентский feature gate «Аватара» снят намеренно: он был
    # единственной защитой, и стоял в браузере, тогда как сервер отдавал
    # стратегию включённой. Теперь недоступность выражена выключенными
    # маршрутами в реестре — её проверяет и сервер, и расчёт готовности.
    assert "Character Performance пока закрыт feature gate" not in submit_batch


def test_single_product_swap_uses_approved_strategy_spec_and_one_creator_runtime() -> None:
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategy(",
        "async function pollGenerationStrategyStatuses",
    )

    # С 23.08.2026 путь один для обеих одноисходниковых стратегий: проекция и
    # выбор сверяются со стратегией записи, а не с литералом «Копии».
    for marker in (
        '!["viral_product_swap", "viral_avatar_ugc"].includes(singleSourceStrategyId)',
        "sourceProjection?.strategy_id !== singleSourceStrategyId",
        "sourceProjection.required_count !== 1",
        "sourceProjection.all_selected_ready !== true",
        "selection?.strategy_id !== singleSourceStrategyId",
        "prepareGenerationStrategySpecs(form, [currentEntry], projectId)",
        "approveGenerationStrategySpecs(form, [currentEntry], projectId)",
        "generationStrategyRuntimeContextForApprovedSpec(",
        "specRecord?.approvedContext || null",
        "requestApi.bindGenerationStrategy(bindPlan.request)",
        "requestApi.preflightGenerationStrategy(",
        "requestApi.startGenerationStrategy(startPlan.request)",
        "requestApi.bindRealGenerationClientContext(startPlan.request",
        "generationRequestContextIsCurrent(requestContext)",
        "state.api === requestApi",
        "!REAL_GENERATION_ENABLED",
    ):
        assert marker in submit

    for forbidden in (
        "currentApprovedGenerationSpecContext",
        "ensurePreparedGenerationSpecForPaidStart",
        "generationStrategyRuntimeContext(",
        "generationSkuForForm",
        "startRealGeneration",
    ):
        assert forbidden not in submit

    built = submit.index("generationStrategyRuntimeStartRequest(")
    reserved = submit.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested", built
    )
    transported = submit.index(
        "requestApi.startGenerationStrategy(startPlan.request)", reserved
    )
    verified = submit.index("const verified = reduceGenerationStrategyRuntimeState(")
    committed = submit.index("setGenerationStrategyRuntime(sourceMediaId, runtimeState)", verified)
    assert built < reserved < transported < verified < committed
    assert submit.count("requestApi.startGenerationStrategy(startPlan.request)") == 1


def test_single_product_swap_paid_review_uses_only_server_confirmation() -> None:
    readiness = _source_slice(
        APP,
        "function syncGenerationStrategySingleFormReadiness",
        "function syncGenerationStrategyFormReadiness",
    )
    unsupported = _top_level_function(
        APP, "syncUnsupportedGenerationStrategyFormReadiness"
    )
    reset = _source_slice(
        APP,
        "function resetGenerationStrategyQueueState",
        "function generationStrategyQueueProjection",
    )

    for marker in (
        '["viral_product_swap", "viral_avatar_ugc"].includes(singleSourceStrategyId)',
        "sourceProjection?.strategy_id === singleSourceStrategyId",
        "sourceProjection.required_count === 1",
        "sourceProjection.selected_count === 1",
        "sourceProjection.exact_required_selected === true",
        "sourceProjection.all_selected_ready === true",
        "selections[0]?.selection?.strategy_id === singleSourceStrategyId",
        "generationStrategyReceiptIsFresh(runtimeState)",
        "runtimeProjection.readiness.launch_enabled === true",
        "runtimeProjection.price.spend_confirmation",
        "confirmation.value === runtimeProjection?.price?.spend_confirmation",
        "REAL_GENERATION_ENABLED",
    ):
        assert marker in readiness
    assert "GENERATION_STRATEGY_EXACT_10" not in readiness

    # Ветка «стратегия не подключена» больше не знает «Аватара» по имени: с
    # 22.08.2026 он идёт по тому же расчёту готовности, что и «Копия», а его
    # недоступность выражается выключенными маршрутами в реестре. Клиентский
    # feature gate был единственной защитой и стоял в браузере, тогда как сервер
    # отдавал стратегию включённой — теперь проверяют оба.
    assert 'strategyId === "viral_avatar_ugc"' not in unsupported
    assert "Character Performance пока закрыт feature gate" not in unsupported
    # Ветка при этом жива и продолжает глушить всё, чего нет в расчёте: у
    # «Создания» нет исполнимого маршрута, и она называет причину.
    assert 'strategyId === "viral_rebuild"' in unsupported
    assert "нет исполнимого маршрута" in unsupported
    assert "generationStrategyHasPaidAuthority()" in reset


def test_single_expired_receipt_refresh_preserves_binding_and_other_paid_authority() -> None:
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategy(",
        "async function pollGenerationStrategyStatuses",
    )

    assert "generationStrategySingleHasOtherPaidAuthority(sourceMediaId)" in submit
    assert "createGenerationStrategyRuntimeFingerprint(context)" in submit
    selected = submit.index('if (runtimeState.phase === "selected")')
    bind_key = submit.index("generationStrategyRequestIdempotencyKey(", selected)
    bind_call = submit.index("requestApi.bindGenerationStrategy(bindPlan.request)")
    refresh = submit.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.preflightRefreshRequested"
    )
    preflight = submit.index("requestApi.preflightGenerationStrategy(", refresh)
    assert selected < bind_key < bind_call < refresh < preflight
    assert "createGenerationStrategyRuntimeFingerprint(liveContext)" in submit
    assert "liveRuntime === expectedRuntime" in submit
    assert 'refreshRequested.phase !== "bound"' in submit
    assert "refreshRequested.bind?.binding?.id !== runtimeState.bind?.binding?.id" in submit
    assert "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.reset" not in submit
    assert "state.generationStrategyRequestKeys.delete(key)" not in submit


def test_status_poll_validates_off_copy_before_preserving_paid_state() -> None:
    poll = _top_level_function(APP, "pollGenerationStrategyStatuses")

    reduced = poll.index("const candidate = reduceGenerationStrategyRuntimeState(")
    guarded = poll.index('if (candidate?.phase !== "status")', reduced)
    queue_reduced = poll.index("const updated = updateGenerationStrategyQueueRow(", guarded)
    queue_committed = poll.index("state.generationStrategyQueue = updated.queue", queue_reduced)
    single_committed = poll.index("setGenerationStrategyRuntime(sourceMediaId, candidate)")
    assert reduced < guarded < queue_reduced < queue_committed
    assert guarded < single_committed
    assert "applyGenerationStrategyQueueRow(sourceMediaId, action)" not in poll
    assert "Последнее подтверждённое состояние и блокировка сохранены" in poll
    assert "повторный POST запрещён" in poll


def test_paid_strategy_reserves_runtime_start_before_network_and_never_rekeys() -> None:
    submit_strategy = _source_slice(
        APP,
        "async function startGenerationStrategyQueueSequentially",
        "function handleGenerationStrategySourcesChanged",
    )
    built = submit_strategy.index("generationStrategyRuntimeStartRequest(")
    reserved = submit_strategy.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested"
    )
    transported = submit_strategy.index(
        "requestApi.startGenerationStrategy(startPlan.request)"
    )
    assert built < reserved < transported
    assert "crypto.randomUUID()" not in submit_strategy
    assert "startPlan.request" in submit_strategy
    assert "bindRealGenerationClientContext(startPlan.request" in submit_strategy
    assert "generationRequestContextIsCurrent(requestContext)" in submit_strategy
    assert "state.api === requestApi" in submit_strategy
    assert 'currentRuntime?.phase === "start_once"' in submit_strategy
    assert "currentRuntime.start_context_fingerprint === reserved.start_context_fingerprint" in submit_strategy
    verified = submit_strategy.index("reduceGenerationStrategyRuntimeState(")
    committed = submit_strategy.index(
        "applyGenerationStrategyQueueRow(sourceMediaId, resolvedAction)"
    )
    assert transported < verified < committed


def test_exact_ten_paid_gate_requires_fresh_receipts_and_real_generation() -> None:
    confirmation = _top_level_function(
        APP, "confirmGenerationStrategyQueueForPaidStart"
    )
    sequential = _source_slice(
        APP,
        "async function startGenerationStrategyQueueSequentially",
        "function handleGenerationStrategySourcesChanged",
    )
    readiness = _source_slice(
        APP,
        "function syncGenerationStrategyFormReadiness",
        "async function probeSelectedGenerationStrategyMedia",
    )
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function submitGenerationStrategy(form,",
    )
    assert "!REAL_GENERATION_ENABLED" in confirmation
    assert "generationStrategyQueueReceiptsAreFresh" in confirmation
    assert "let confirmedQueue = state.generationStrategyQueue" in confirmation
    assert "state.generationStrategyQueue = confirmedQueue" in confirmation
    assert "!REAL_GENERATION_ENABLED" in sequential
    assert "generationStrategyReceiptIsFresh" in sequential
    assert sequential.index("generationStrategyReceiptIsFresh") < sequential.index(
        "type: GENERATION_STRATEGY_RUNTIME_ACTIONS.startRequested"
    )
    assert "receiptWindowReady" in readiness
    assert "&& REAL_GENERATION_ENABLED" in readiness
    assert "Обновить 10 точных цен" in readiness
    assert "resetGenerationStrategyQueueState({ clearSpecs: false })" not in submit
    assert "generationStrategyQueueReviewPreflightRefreshTargets()" in submit
    assert "refreshGenerationStrategyQueuePreflights(" in submit
    assert "state.generationStrategyQueueReview = refreshedReview.review" in submit
    assert "prepareGenerationStrategyQueueFree(form, selections, projectId)" in submit


def test_paid_resume_refreshes_only_unstarted_receipts_before_more_starts() -> None:
    targets = _top_level_function(
        APP, "generationStrategyQueuePreflightRefreshTargets"
    )
    refresh = _source_slice(
        APP,
        "async function refreshGenerationStrategyQueuePreflights",
        "function confirmGenerationStrategyQueueForPaidStart",
    )
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function submitGenerationStrategy(form,",
    )
    readiness = _source_slice(
        APP,
        "function syncGenerationStrategyFormReadiness",
        "async function probeSelectedGenerationStrategyMedia",
    )

    assert 'runtimeState?.phase !== "human_confirmed"' in targets
    assert "generationStrategyReceiptWindowMs(remaining)" in targets
    assert "remaining -= 1" in targets

    for marker in (
        '"preflight_refresh"',
        "oldReceipt.receipt_hash",
        "generationStrategyRuntimePreflightRequest(",
        "requestApi.preflightGenerationStrategy(operation.plan.request)",
        "Promise.allSettled",
        "generationRequestContextIsCurrent(requestContext)",
        "state.generationStrategyQueueSourceRevision !== sourceRevision",
        "live?.phase !== operation.priorPhase",
        "reduceGenerationStrategyRuntimeState(",
        "operation.requestState",
        'const expectedPhase = paidRefresh',
        'verified.phase !== expectedPhase',
        "verified.start_context_fingerprint === live.start_context_fingerprint",
        "applyGenerationStrategyQueueRow(",
        "clearGenerationStrategyRequestIdempotencyKey(operation.idempotency.key)",
    ):
        assert marker in refresh
    verified = refresh.index("const verified = reduceGenerationStrategyRuntimeState(")
    committed = refresh.index("applyGenerationStrategyQueueRow(", verified)
    assert verified < committed
    assert "GENERATION_STRATEGY_RUNTIME_ACTIONS.humanConfirmed" not in refresh
    assert "startGenerationStrategy" not in refresh

    paid_branch = submit.index("if (generationStrategyQueueHasPaidAuthority())")
    plan = submit.index("planGenerationStrategyQueueSequentialStarts(", paid_branch)
    ready_gate = submit.index('paidPlan.plan.state !== "ready"', plan)
    refresh_gate = submit.index(
        "if (generationStrategyQueuePaidReceiptsNeedRefresh())",
        ready_gate,
    )
    refresh_call = submit.index(
        "await refreshGenerationStrategyQueuePreflights(",
        refresh_gate,
    )
    paid_start = submit.index(
        "await startGenerationStrategyQueueSequentially(",
        refresh_call,
    )
    assert paid_branch < plan < ready_gate < refresh_gate < refresh_call < paid_start
    assert "ТЗ, ассеты, кампания и уже созданные job-ID сохранены" in submit
    assert "провайдер не запускался" in submit
    assert "Обновить проверки оставшихся роликов бесплатно" in readiness


def test_exact_ten_resume_and_spec_review_recovery_are_explicit() -> None:
    submit = _source_slice(
        APP,
        "async function submitGenerationStrategyExactTen",
        "async function submitGenerationStrategy(form,",
    )
    approvals = _source_slice(
        APP,
        "async function approveGenerationStrategySpecs",
        "async function prepareGenerationStrategyQueueFree",
    )
    review = _source_slice(
        APP,
        "function generationStrategySpecMechanicsMarkup",
        "function generationStrategySpecReviewMarkup",
    )
    paid_branch = submit.index("if (generationStrategyQueueHasPaidAuthority())")
    aggregate_branch = submit.index("const currentReview = state.generationStrategyQueue")
    assert paid_branch < aggregate_branch
    assert "planGenerationStrategyQueueSequentialStarts" in submit
    assert "startGenerationStrategyQueueSequentially" in submit
    assert "Promise.allSettled" in approvals
    assert 'result.status === "fulfilled"' in approvals
    assert "if (rejected) throw rejected.reason" in approvals
    for marker in (
        "selection.assets.map",
        "selection.attestations",
        "scope.platform",
        "scope.product_category",
        "scope.asset_snapshot.map",
        "scope.source",
        "scope.strategy_id",
        "scope.input_mode",
        "scope.reference_video",
        "scope.spoken_dialogue",
        "avatar_likeness_consent_confirmed",
    ):
        assert marker in review
    for forbidden in ("object_name", "signed_url", "sha256", "price_hash"):
        assert forbidden not in review
    assert 'goToStep?.("media")' in submit
    assert 'goToStep?.("launch")' in submit
    review_rows = _source_slice(
        APP,
        "function generationStrategySpecReviewMarkup",
        "function syncGenerationStrategySpecReviewUi",
    )
    assert "aria-labelledby" in review_rows
    assert "для ролика ${entry.position} из 10" in review_rows
    assert "Я прочитал(а) версию ролика ${entry.position} из 10" in review_rows


def test_mechanics_edit_invalidates_only_its_exact_queue_row() -> None:
    activity = _source_slice(
        APP,
        "function handleFormActivity",
        "function handleGenerationGuidedStepCommitted",
    )
    invalidator = _top_level_function(
        APP, "invalidateGenerationStrategyQueueSource"
    )
    ensure_queue = _source_slice(
        APP,
        "function ensureGenerationStrategyQueue",
        "function syncGenerationStrategyQueueUi",
    )
    assert "event.target.dataset?.generationStrategySourceMediaId" in activity
    assert 'startsWith("generation_strategy_mechanics_")' in activity
    assert "invalidateGenerationStrategyQueueSource(" in activity
    assert "state.generationStrategySpecs.delete(sourceMediaId)" in invalidator
    assert "state.generationStrategySpecRequestKeys.delete(sourceMediaId)" in invalidator
    assert "invalidateGenerationStrategyQueueRow(" in invalidator
    assert 'runtimeState?.phase !== "invalid"' in ensure_queue
    assert "GENERATION_STRATEGY_RUNTIME_ACTIONS.reset" in ensure_queue
    assert "GENERATION_STRATEGY_RUNTIME_ACTIONS.select" in ensure_queue


def test_asset_refresh_invalidates_only_when_selected_source_authority_changes() -> None:
    loader = _source_slice(
        GUIDED,
        "async function loadGenerationStrategyAssets",
        "function replaceStrategyOptions",
    )
    assert 'form.dataset.generationStrategyPaidLocked === "true"' in loader
    assert "const selectedAuthorityBefore = JSON.stringify" in loader
    assert "nextSourceProjection?.selected" in loader
    assert '"contentengine:generation-strategy-sources-changed"' in loader
    assert loader.index("nextSourceProjection?.selected") < loader.index(
        '"contentengine:generation-strategy-sources-changed"'
    )


def test_strategy_probe_is_free_explicit_and_refreshes_server_candidates() -> None:
    probe = _source_slice(
        APP,
        "async function probeSelectedGenerationStrategyMedia",
        "async function submitGenerationStrategyExactTen",
    )
    for marker in (
        "generationStrategyRuntimeProbeRequest",
        "state.api.probeGenerationStrategyMedia(plan.request)",
        "normalizeGenerationStrategyProbeResponse",
        "refreshStrategyAssets",
    ):
        assert marker in probe
    for forbidden in (
        "startGenerationStrategy",
        "bindGenerationStrategy",
        "preflightGenerationStrategy",
    ):
        assert forbidden not in probe
    assert 'data-action="probe-generation-strategy-media"' in APP


def test_strategy_disables_blank_required_legacy_mode_without_model_proxy() -> None:
    visibility = _top_level_function(GUIDED, "syncLegacyModelVisibility")
    assert "modeControl.disabled = strategySelected" in visibility
    assert "modeControl.required = !strategySelected" in visibility
    assert 'model.model === "seedance2_fast"' not in GUIDED
    assert "const proxyModel" not in GUIDED
    assert 'advisor.dataset.strategyAdvisoryOnly = strategySelected ? "true" : "false"' in visibility


def test_status_poll_keeps_non_terminal_jobs_alive_without_provider_poll() -> None:
    poll = _top_level_function(APP, "pollGenerationStrategyStatuses")
    helper = _top_level_function(APP, "generationStrategyStatusPollNeeded")
    terminal = _source_slice(
        APP,
        "const GENERATION_STRATEGY_TERMINAL_JOB_STATUSES",
        "function generationStrategyStatusPollNeeded",
    )

    # Free strategy_status polling must keep every non-terminal job alive even
    # when the provider-poll contract (can_poll) is false, e.g. queued/starting
    # rows whose dispatch is still driven server-side.
    assert poll.count("generationStrategyStatusPollNeeded(") == 3
    assert "!projection?.can_poll" not in poll
    assert "liveProjection?.can_poll" not in poll
    assert "nextProjection?.can_poll" not in poll
    assert "if (shouldContinue) scheduleGenerationStrategyPolling(5_000)" in poll

    assert 'runtimeState?.phase !== "status"' in helper
    assert "projection.can_poll" in helper
    assert "!GENERATION_STRATEGY_TERMINAL_JOB_STATUSES.has(jobStatus)" in helper
    for status in ('"succeeded"', '"failed"', '"cancelled"'):
        assert status in terminal
    for status in ('"queued"', '"starting"', '"submitted"', '"processing"'):
        assert status not in terminal


def test_transport_failed_start_keeps_key_and_replays_identical_request() -> None:
    sequential = _source_slice(
        APP,
        "async function startGenerationStrategyQueueSequentially",
        "function handleGenerationStrategySourcesChanged",
    )
    single = _source_slice(
        APP,
        "async function submitGenerationStrategy(form,",
        "async function pollGenerationStrategyStatuses",
    )
    auto_retry = _source_slice(
        APP,
        "async function retryGenerationStrategyStartAfterTransportFailure",
        "async function retryGenerationStrategyReservedStart",
    )
    manual_retry = _source_slice(
        APP,
        "async function retryGenerationStrategyReservedStart",
        "async function submitGenerationBatch",
    )
    remember = _top_level_function(
        APP, "rememberGenerationStrategyStartTransportFailure"
    )

    # Both paid start flows route a thrown strategy_start into the
    # identical-replay path instead of stranding the start_once reservation.
    assert sequential.count("retryGenerationStrategyStartAfterTransportFailure(") == 1
    assert single.count("retryGenerationStrategyStartAfterTransportFailure(") == 1
    assert "request: startPlan.request" in sequential
    assert "request: startPlan.request" in single

    # The automatic retry re-sends the exact same request object with the same
    # idempotency key and never mints a replacement key.
    assert "requestApi.startGenerationStrategy(request)" in auto_retry
    assert (
        "request?.idempotency_key !== reserved?.start_attempt_idempotency_key"
        in auto_retry
    )
    assert "bindClientContext();" in auto_retry
    assert "GENERATION_STRATEGY_START_RETRY_DELAY_MS" in auto_retry
    assert "crypto.randomUUID" not in auto_retry
    assert "crypto.randomUUID" not in manual_retry

    # The stored reservation pins the reserved key and receipt for the manual
    # retry, which replays the frozen original request byte for byte.
    assert "state.generationStrategyStartRetries.set(sourceMediaId, Object.freeze({" in remember
    assert "idempotency_key: reserved.start_attempt_idempotency_key" in remember
    assert (
        "reserved.start_attempt_idempotency_key !== pending.idempotency_key"
        in manual_retry
    )
    assert "pending.request?.idempotency_key !== pending.idempotency_key" in manual_retry
    assert "pending.request?.receipt_id !== reserved.preflight?.receipt?.id" in manual_retry
    assert "requestApi.startGenerationStrategy(pending.request)" in manual_retry
    assert "idempotency_key: live.start_attempt_idempotency_key" in manual_retry

    # The retry is visible in the queue UI and wired to the click dispatcher.
    queue_ui = _source_slice(
        APP,
        "function syncGenerationStrategyQueueUi",
        "function generationStrategySpecRequestKey",
    )
    assert "appendGenerationStrategyStartRetryActions(mount)" in queue_ui
    assert 'data-action="retry-generation-strategy-start"' in queue_ui
    assert "Повторить тот же платный старт" in queue_ui
    click_handler = _source_slice(
        APP,
        "async function handleClick(event)",
        "async function handleSubmit(event)",
    )
    assert 'action === "retry-generation-strategy-start"' in click_handler
    assert "retryGenerationStrategyReservedStart(form, sourceMediaId)" in click_handler


def test_archive_strategy_card_never_invokes_legacy_status_or_reconcile() -> None:
    actions = _source_slice(
        APP,
        "function generationActionsMarkup",
        "function generationCostMarkup",
    )
    strategy_branch = _source_slice(
        actions,
        "if (details.strategy) {",
        "const reviewAction = details.photo",
    )
    assert 'data-action="check-generation-strategy"' in strategy_branch
    assert 'data-output-action="preview"' in strategy_branch
    assert 'data-output-action="download"' in strategy_branch
    assert "check-real-generation" not in strategy_branch
    assert 'data-strategy-job="true"' in actions
    # The strategy «Проверить сейчас» branch renders before — and instead of —
    # the legacy status button that 503s on recipe jobs.
    assert actions.index(
        'data-action="refresh-generation-strategy-status"'
    ) < actions.index(
        'data-action="check-real-generation" data-output-action="status"'
    )

    manual_handler = _source_slice(
        APP,
        'if (action === "refresh-generation-strategy-status")',
        'if (action === "check-generation-strategy")',
    )
    assert "refreshGenerationStrategyArchiveStatus(control.dataset.jobId, control)" in manual_handler
    for forbidden in (
        "waitForRealGenerationStatus",
        "state.api.realGenerationStatus",
        "startGenerationStrategy",
        "repeatGenerationStrategyFromArchive",
    ):
        assert forbidden not in manual_handler

    handler = _source_slice(
        APP,
        'if (action === "check-generation-strategy")',
        'if (action === "check-real-generation")',
    )
    assert "requestGenerationStrategyArchiveStatus(jobId)" in handler
    for forbidden in (
        "waitForRealGenerationStatus",
        "state.api.realGenerationStatus",
        "requestRealGenerationStatus",
        "api.reconcileRealGeneration",
    ):
        assert forbidden not in handler
    # Preview and download of a succeeded strategy job go through the
    # storage signing path — strategy_status never returns signed URLs.
    for required in (
        "resolveGenerationStrategyOutputObjectName",
        "state.api.downloadPrivateObject(objectName)",
        "state.api.signedPrivateObjectUrls([objectName])",
        "deliverGenerationOutputBlob(blob, jobId, false)",
        "isTrustedGenerationDownload(signedUrl)",
    ):
        assert required in handler

    status_request = _top_level_function(
        APP, "requestGenerationStrategyArchiveStatus"
    )
    assert "state.api.generationStrategyStatus(request)" in status_request
    assert "realGenerationStatus" not in status_request
    builder = _top_level_function(APP, "generationStrategyArchiveStatusRequest")
    assert '"strategy_status"' in builder

    resolver = _top_level_function(
        APP, "resolveGenerationStrategyOutputObjectName"
    )
    assert "normalizeContentReviewCatalog" in resolver
    assert 'media.kind !== "generated_video"' in resolver
    assert "media.objectName" in resolver

    jobs = _source_slice(
        APP,
        "function realGenerationJobsFromBatches",
        "function realGenerationReconciliationJobsFromBatches",
    )
    assert "&& !details.strategy" in jobs
    assert "cached?.strategy === true" in jobs
    recovery = _top_level_function(APP, "resumeGeneratedVideoQaRecovery")
    assert "!details.strategy" in recovery


def test_strategy_reconciliation_form_submits_through_strategy_reconcile() -> None:
    submit = _source_slice(
        APP,
        "async function submitRealGenerationReconciliation",
        "async function submitRealGeneration(form",
    )
    assert 'form.dataset.strategyJob === "true"' in submit
    assert "state.api.reconcileGenerationStrategy(jobId" in submit
    assert "requestGenerationStrategyArchiveStatus(jobId)" in submit
    assert "dispatch_result_id: dispatchResultId" in submit
    assert "applyGenerationStrategyArchiveStatus(jobId, result, { projectId })" in submit
    assert "scheduleGenerationStrategyPolling(0)" in submit
    strategy_branch = _source_slice(submit, "if (strategyJob) {", "} else {")
    assert "reconcileRealGeneration" not in strategy_branch
    # Legacy catalog-model launches keep the legacy reconcile path untouched.
    assert "state.api.reconcileRealGeneration(jobId" in submit


def test_strategy_reconcile_action_is_allowlisted_with_edge_exact_payload() -> None:
    allowlist = _source_slice(
        API,
        "const GENERATION_STRATEGY_EDGE_ACTIONS",
        "const GENERATION_STRATEGY_IDEMPOTENT_ACTIONS",
    )
    assert '"strategy_reconcile"' in allowlist
    idempotent = _source_slice(
        API,
        "const GENERATION_STRATEGY_IDEMPOTENT_ACTIONS",
        "const GENERATION_STRATEGY_IDEMPOTENCY_PATTERN",
    )
    assert '"strategy_reconcile"' in idempotent

    edge_parser = _source_slice(
        EDGE,
        "function readGenerationStrategyReconcilePayload",
        "function readStrategySpendConfirmation",
    )
    edge_required = re.findall(
        r'"([a-z_]+)"',
        _source_slice(edge_parser, "const required = [", "] as const"),
    )
    api_required = re.findall(
        r'"([a-z_]+)"',
        _source_slice(API, "strategy_reconcile: Object.freeze([", "])"),
    )
    assert api_required == edge_required
    assert '[...required, "provider_task_id"]' in edge_parser
    attach_keys = _source_slice(
        API,
        "const GENERATION_STRATEGY_RECONCILE_ATTACH_REQUEST_KEYS",
        ";",
    )
    assert '"provider_task_id"' in attach_keys

    method = _source_slice(
        API,
        "  reconcileGenerationStrategy(jobId, details = {})",
        "  async invokeRealGeneration",
    )
    for token in (
        'this.invokeRealGeneration("strategy_reconcile"',
        '"RUNWAY_TASK_ID_VERIFIED"',
        '"RUNWAY_NO_TASK_VERIFIED"',
        '"FAL_REQUEST_ID_VERIFIED"',
        '"FAL_NO_REQUEST_VERIFIED"',
        "dispatch_result_id",
        "generation_reconciliation_incident_invalid",
        "generation_reconciliation_resolution_invalid",
        "generation_reconciliation_evidence_invalid",
        "generation_reconciliation_task_id_invalid",
        "GENERATION_STRATEGY_RUNWAY_TASK_ID_PATTERN",
        "GENERATION_STRATEGY_FAL_REQUEST_ID_PATTERN",
    ):
        assert token in method
    # Strategy reconciliation supports the exact Runway/fal routes only;
    # Google remains a separate legacy provider path.
    assert "GOOGLE_" not in method
    assert "google" not in method


def test_strategy_reconcile_bridge_sends_exact_payload_without_random_keys() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy reconcile bridge contracts")
    script = (
        "import assert from 'node:assert/strict';\n"
        + "const { CreatorApi } = await import("
        + json.dumps(API_PATH.as_uri())
        + ");\n"
        + r"""
globalThis.window = {
  sessionStorage: { getItem() { return null; }, setItem() {} },
};
const actor = '11111111-1111-4111-8111-111111111111';
const organization = '22222222-2222-4222-8222-222222222222';
const project = '33333333-3333-4333-8333-333333333333';
const job = '44444444-4444-4444-8444-444444444444';
const dispatchResult = '55555555-5555-4555-8555-555555555555';
const incident = '66666666-6666-4666-8666-666666666666';
const response = {
  ok: true, version: 'generation-strategy-status-response-v1',
  job: {}, strategy: {}, selection: {}, price: {}, dispatch: {},
  reconciliation: {}, output: null, error: null, contract: {},
};
const calls = [];
const supabase = {
  schema() { return {rpc() {}}; },
  auth: {async getSession() {
    return {data: {session: {access_token: 'token', user: {id: actor}}}, error: null};
  }},
  functions: {async invoke(name, options) {
    assert.equal(name, 'creator-generate');
    calls.push(options.body);
    return {data: structuredClone(response), error: null};
  }},
};
const api = new CreatorApi(supabase, {
  RPC_SCHEMA: 'public', STORAGE_BUCKET: 'media', REAL_GENERATION_ENABLED: true,
});
api.organizationId = organization;

assert.throws(
  () => api.reconcileGenerationStrategy(job, {
    project_id: project,
    provider: 'runway',
    dispatch_result_id: 'not-a-uuid',
    incident_id: incident,
    resolution: 'attach_existing_task',
    provider_task_id: 'runway-task-77',
    evidence_reference: 'Runway dashboard, 16.08 14:35',
    reason: 'Task создан в 14:32 рядом со стартом этого товара.',
  }),
  (error) => error?.code === 'generation_reconciliation_incident_invalid',
);
assert.equal(calls.length, 0);

const attach = await api.reconcileGenerationStrategy(job, {
  project_id: project,
  provider: 'runway',
  dispatch_result_id: dispatchResult,
  incident_id: incident,
  resolution: 'attach_existing_task',
  provider_task_id: 'runway-task-77',
  evidence_reference: 'Runway dashboard, 16.08 14:35',
  reason: 'Task создан в 14:32 рядом со стартом этого товара.',
});
assert.deepEqual(attach, response);
assert.deepEqual(calls[0], {
  action: 'strategy_reconcile',
  organization_id: organization,
  project_id: project,
  generation_job_id: job,
  dispatch_result_id: dispatchResult,
  incident_id: incident,
  resolution: 'attach_existing_task',
  confirmation: 'RUNWAY_TASK_ID_VERIFIED',
  evidence_reference: 'Runway dashboard, 16.08 14:35',
  reason: 'Task создан в 14:32 рядом со стартом этого товара.',
  idempotency_key: 'strategy-reconcile:' + incident + ':attach_existing_task',
  provider_task_id: 'runway-task-77',
});

await api.reconcileGenerationStrategy(job, {
  project_id: project,
  provider: 'runway',
  dispatch_result_id: dispatchResult,
  incident_id: incident,
  resolution: 'confirm_no_submission',
  evidence_reference: 'Runway dashboard, 16.08 14:40',
  reason: 'В панели Runway нет task рядом со временем этого старта.',
});
assert.equal(calls.length, 2);
assert.equal(calls[1].confirmation, 'RUNWAY_NO_TASK_VERIFIED');
assert.equal(
  calls[1].idempotency_key,
  'strategy-reconcile:' + incident + ':confirm_no_submission',
);
assert.ok(!('provider_task_id' in calls[1]));
assert.deepEqual(api.mutationKeys, {});
"""
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        path = Path(temporary_directory) / "strategy-reconcile.mjs"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(
            [node, str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout


def test_typed_generation_strategy_rejections_are_never_auto_retried() -> None:
    guard = _top_level_function(APP, "generationStrategyStartFailureIsTransport")
    auto_retry = _source_slice(
        APP,
        "async function retryGenerationStrategyStartAfterTransportFailure",
        "async function retryGenerationStrategyReservedStart",
    )
    manual_retry = _source_slice(
        APP,
        "async function retryGenerationStrategyReservedStart",
        "async function submitGenerationBatch",
    )
    transport_codes = _source_slice(
        APP,
        "const GENERATION_STRATEGY_START_TRANSPORT_ERROR_CODES",
        "function generationStrategyStartFailureIsTransport",
    )

    # Only transport-level failures with an unknown outcome may replay the
    # identical request; deterministic typed rejections never do.
    assert 'startsWith("generation_strategy_")' in guard
    assert "return false" in guard
    assert '"real_generation_request_failed"' in transport_codes
    assert '"generation_unavailable"' in transport_codes
    assert '"real_generation_response_invalid"' not in transport_codes

    first_guard = auto_retry.index("!generationStrategyStartFailureIsTransport(error)")
    throw_original = auto_retry.index("throw error;", first_guard)
    transported = auto_retry.index("requestApi.startGenerationStrategy(request)")
    assert first_guard < throw_original < transported
    assert "if (generationStrategyStartFailureIsTransport(retryError))" in auto_retry
    assert "state.generationStrategyStartRetries.delete(sourceMediaId)" in auto_retry
    assert "if (generationStrategyStartFailureIsTransport(error))" in manual_retry
    assert "state.generationStrategyStartRetries.delete(sourceMediaId)" in manual_retry
