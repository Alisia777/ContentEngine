from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "web/app/supabase-api.js"
API = API_PATH.read_text(encoding="utf-8")


def _run_node(script: str) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for strategy-spec API bridge tests")
    return subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_rpc_inventory_and_named_method_keep_caller_owned_request() -> None:
    assert (
        'prepareGenerationStrategySpec: "creator_prepare_generation_strategy_spec"'
        in API
    )
    start = API.index("  prepareGenerationStrategySpec(request = {})")
    end = API.index("\n  controlGenerationSpec(", start)
    method = API[start:end]
    assert "assertGenerationStrategySpecPrepareRequest(" in method
    assert "this.call(RPC.prepareGenerationStrategySpec, request)" in method
    assert "this.mutate(" not in method
    assert "withOrganization(" not in method
    assert "mutationKeys" not in method
    assert "idempotency_key:" not in method


def test_ugc_swap_and_rebuild_exact_dtos_are_forwarded_without_rekeying() -> None:
    script = f"""
import assert from 'node:assert/strict';
const {{CreatorApi}} = await import({json.dumps(API_PATH.as_uri())});
const storageWrites = [];
globalThis.window = {{sessionStorage: {{
  getItem() {{ return null; }},
  setItem(key, value) {{ storageWrites.push([key, value]); }},
}}}};
const ids = {{
  organization: '11111111-1111-4111-8111-111111111111',
  project: '22222222-2222-4222-8222-222222222222',
  source: '33333333-3333-4333-8333-333333333333',
  avatar: '44444444-4444-4444-8444-444444444444',
  product: '55555555-5555-4555-8555-555555555555',
  original: '66666666-6666-4666-8666-666666666666',
  secondProduct: '77777777-7777-4777-8777-777777777777',
  style: '88888888-8888-4888-8888-888888888888',
}};
const commonAttestations = () => ({{
  source_media_rights_confirmed: true,
  transformative_use_confirmed: true,
  product_assets_rights_confirmed: true,
  depicted_people_consent_confirmed: true,
}});
const mechanics = () => ({{
  version: 'generation-strategy-mechanics-summary-v1',
  hook: 'Открываем ролик крупным планом товара и быстрым обещанием результата.',
  beat_sequence: [
    'Показываем исходную ситуацию и проблему зрителя.',
    'Демонстрируем использование товара и итоговый результат.',
  ],
  pacing: 'Быстрый темп с короткими смысловыми паузами.',
  camera_language: 'Крупные планы товара и один устойчивый общий план.',
  composition: 'Товар остаётся главным объектом в центре вертикального кадра.',
  audio_pattern: 'Ритмичная музыка тише естественного голоса героя.',
  cta_pattern: 'Короткий призыв посмотреть карточку товара после результата.',
}});
const envelope = (selection, mechanicsSummary, suffix) => ({{
  version: 'generation-strategy-spec-prepare-request-v1',
  organization_id: ids.organization,
  project_id: ids.project,
  platform: 'instagram',
  product_category: 'cosmetics',
  selection,
  editable_intent: 'Скопировать механику успешного ролика с нашим товаром.',
  proposed_prompt: 'Создай рекламный ролик по подтверждённой механике исходника.',
  mechanics_summary: mechanicsSummary,
  confirmation: true,
  idempotency_key: `strategy-spec:${{suffix}}`,
  reason: 'Подготовка отдельной технической версии выбранной стратегии.',
  // Товар «Дуэта» приходит явным полем: фотографий товара у него нет. Другим
  // стратегиям этот ключ запрещён — у них товар назван снимками.
  ...(selection.strategy_id === 'viral_avatar_ugc'
    ? {{product_id: ids.product}}
    : {{}}),
}});
const ugc = envelope({{
  version: '2026-08-14.v1',
  strategy_id: 'viral_avatar_ugc',
  recipe_version: '2026-06',
  duration_seconds: 8,
  // «Дуэт» измеряется разрешением: кадр задаёт исходник. Ассет ровно один —
  // комментируемый ролик; ведущего даёт библиотека проекта, а не форма.
  resolution: '720p',
  audio: true,
  assets: [
    {{role: 'source_video', media_id: ids.source, duration_seconds: 8}},
  ],
  attestations: {{
    ...commonAttestations(),
    avatar_likeness_consent_confirmed: true,
  }},
}}, mechanics(), 'ugc:11111111');
const swap = envelope({{
  version: '2026-08-14.v1',
  strategy_id: 'viral_product_swap',
  recipe_version: '2026-06',
  duration_seconds: 9,
  resolution: '1080p',
  audio: false,
  assets: [
    {{role: 'source_video', media_id: ids.source, duration_seconds: 8.125}},
    {{role: 'original_product_image', media_id: ids.original}},
    {{role: 'new_product_image', media_id: ids.product, view: 'front'}},
    {{role: 'new_product_image', media_id: ids.secondProduct, view: 'side'}},
  ],
  attestations: commonAttestations(),
}}, null, 'swap:22222222');
const rebuild = envelope({{
  version: '2026-08-14.v1',
  strategy_id: 'viral_rebuild',
  recipe_version: '2026-06',
  duration_seconds: 10,
  ratio: '1080:1920',
  audio: true,
  assets: [
    {{role: 'source_video', media_id: ids.source}},
    {{role: 'product_image', media_id: ids.product}},
    {{role: 'style_image', media_id: ids.style}},
  ],
  attestations: commonAttestations(),
}}, mechanics(), 'rebuild:33333333');

const rawResponse = {{
  ok: true,
  version: 'generation-strategy-spec-prepare-response-v1',
  generation_spec: {{}}, history: [], recommended_next_action: 'review',
  strategy: {{}}, contract: {{}},
}};
const calls = [];
const supabase = {{
  schema() {{ return {{async rpc(name, parameters) {{
    calls.push([name, parameters.p_payload]);
    return {{data: rawResponse, error: null}};
  }}}}; }},
}};
const api = new CreatorApi(supabase, {{RPC_SCHEMA: 'public', STORAGE_BUCKET: 'media'}});
api.organizationId = ids.organization;
for (const request of [ugc, swap, rebuild]) {{
  const response = await api.prepareGenerationStrategySpec(request);
  assert.strictEqual(response, rawResponse);
}}
assert.equal(calls.length, 3);
for (let index = 0; index < calls.length; index += 1) {{
  assert.equal(calls[index][0], 'creator_prepare_generation_strategy_spec');
  assert.strictEqual(calls[index][1], [ugc, swap, rebuild][index]);
  assert.equal(calls[index][1].idempotency_key, [ugc, swap, rebuild][index].idempotency_key);
}}
assert.deepEqual(api.mutationKeys, {{}});
assert.deepEqual(storageWrites, []);
"""
    result = _run_node(script)
    assert result.returncode == 0, result.stderr


def test_invalid_scope_selection_mechanics_and_strings_never_reach_rpc() -> None:
    script = f"""
import assert from 'node:assert/strict';
const {{CreatorApi}} = await import({json.dumps(API_PATH.as_uri())});
globalThis.window = {{sessionStorage: {{getItem() {{return null;}}, setItem() {{}}}}}};
const ids = {{
  organization: '11111111-1111-4111-8111-111111111111',
  project: '22222222-2222-4222-8222-222222222222',
  source: '33333333-3333-4333-8333-333333333333',
  avatar: '44444444-4444-4444-8444-444444444444',
  product: '55555555-5555-4555-8555-555555555555',
}};
const mechanics = {{
  version: 'generation-strategy-mechanics-summary-v1',
  hook: 'Сразу показываем товар и понятный результат его использования.',
  beat_sequence: [
    'Фиксируем исходную проблему пользователя в первом кадре.',
    'Показываем применение товара и видимый итоговый эффект.',
  ],
  pacing: 'Быстрый темп без резких непонятных переходов.',
  camera_language: 'Крупные планы товара чередуются с общим планом.',
  composition: 'Главный объект остаётся в безопасной центральной зоне.',
  audio_pattern: 'Музыка поддерживает темп и не заглушает основной голос.',
  cta_pattern: 'После результата появляется короткий устный призыв к действию.',
}};
const valid = {{
  version: 'generation-strategy-spec-prepare-request-v1',
  organization_id: ids.organization,
  project_id: ids.project,
  platform: 'tiktok',
  product_category: 'cosmetics',
  selection: {{
    version: '2026-08-14.v1', strategy_id: 'viral_avatar_ugc',
    recipe_version: '2026-06', duration_seconds: 8, resolution: '720p',
    audio: true,
    assets: [
      {{role: 'source_video', media_id: ids.source, duration_seconds: 8}},
    ],
    attestations: {{
      source_media_rights_confirmed: true,
      transformative_use_confirmed: true,
      product_assets_rights_confirmed: true,
      depicted_people_consent_confirmed: true,
      avatar_likeness_consent_confirmed: true,
    }},
  }},
  editable_intent: 'Повторить механику ролика с нашим товаром.',
  proposed_prompt: 'Создай ролик по проверенной механике исходника.',
  mechanics_summary: mechanics,
  confirmation: true,
  idempotency_key: 'strategy-spec:ugc:11111111',
  reason: 'Подготовка технической версии стратегии.',
}};
const clone = (value) => structuredClone(value);
const invalid = [];
invalid.push({{...clone(valid), extra: true}});
invalid.push({{...clone(valid), organization_id: ids.project}});
invalid.push({{...clone(valid), platform: 'TikTok'}});
invalid.push({{...clone(valid), editable_intent: ' padded intent '}});
invalid.push({{...clone(valid), idempotency_key: ' short '}});
invalid.push({{...clone(valid), mechanics_summary: null}});
const falseRight = clone(valid);
falseRight.selection.attestations.transformative_use_confirmed = false;
invalid.push(falseRight);
const extraSelection = clone(valid);
extraSelection.selection.model = 'hidden-proxy';
invalid.push(extraSelection);
// Соотношение сторон «Дуэту» чужое: кадр приходит из исходника, и выбирать его
// нечем. Ключ в наборе означает форму другой стратегии.
const foreignRatio = clone(valid);
foreignRatio.selection.ratio = '9:16';
invalid.push(foreignRatio);
const wrongResolution = clone(valid);
wrongResolution.selection.resolution = '480p';
invalid.push(wrongResolution);
const duplicateBeat = clone(valid);
duplicateBeat.mechanics_summary.beat_sequence[1] =
  duplicateBeat.mechanics_summary.beat_sequence[0];
invalid.push(duplicateBeat);
const swapWithMechanics = clone(valid);
swapWithMechanics.selection = {{
  version: '2026-08-14.v1', strategy_id: 'viral_product_swap',
  recipe_version: '2026-06', duration_seconds: 8, resolution: '720p',
  audio: false,
  assets: [
    {{role: 'source_video', media_id: ids.source, duration_seconds: 8}},
    {{role: 'original_product_image', media_id: ids.avatar}},
    {{role: 'new_product_image', media_id: ids.product}},
  ],
  attestations: {{
    source_media_rights_confirmed: true,
    transformative_use_confirmed: true,
    product_assets_rights_confirmed: true,
    depicted_people_consent_confirmed: true,
  }},
}};
invalid.push(swapWithMechanics);
// Один файл в двух ролях проверяется на «Копии»: у «Дуэта» ассет один, и
// повторить в нём нечего.
const duplicateAsset = clone(swapWithMechanics);
duplicateAsset.mechanics_summary = null;
duplicateAsset.selection.assets[2].media_id = ids.avatar;
invalid.push(duplicateAsset);

let calls = 0;
const supabase = {{schema() {{return {{async rpc() {{calls += 1; return {{data: {{}}, error: null}};}}}};}}}};
const api = new CreatorApi(supabase, {{RPC_SCHEMA: 'public', STORAGE_BUCKET: 'media'}});
api.organizationId = ids.organization;
for (const request of invalid) {{
  await assert.rejects(
    Promise.resolve().then(() => api.prepareGenerationStrategySpec(request)),
    (error) => error?.code === 'generation_strategy_spec_prepare_payload_invalid',
  );
}}
assert.equal(calls, 0);
"""
    result = _run_node(script)
    assert result.returncode == 0, result.stderr
