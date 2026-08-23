from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "web/app/generation-strategy-spec.js"
SOURCE = MODULE.read_text(encoding="utf-8")


FIXTURE = r"""
import * as subject from './subject.mjs';

const clone = (value) => JSON.parse(JSON.stringify(value));
const hash = (seed) => Number(seed).toString(16).padStart(64, '0');
const uuid = (seed, head = '90000000') =>
  `${head}-0000-4000-8000-${Number(seed).toString(16).padStart(12, '0')}`;
const ids = Object.freeze({
  organization: '10000000-0000-4000-8000-000000000001',
  project: '20000000-0000-4000-8000-000000000002',
  source: '30000000-0000-4000-8000-0000000000ff',
  avatar: '40000000-0000-4000-8000-000000000004',
  avatarSide: '40000000-0000-4000-8000-00000000000b',
  productMedia: '50000000-0000-4000-8000-000000000005',
  original: '60000000-0000-4000-8000-000000000006',
  style: '70000000-0000-4000-8000-000000000007',
  product: '80000000-0000-4000-8000-000000000008',
  reviewer: 'a0000000-0000-4000-8000-00000000000a',
});
const mechanics = () => ({
  version: 'generation-strategy-mechanics-summary-v1',
  hook: 'Hands reveal the problem before the product enters frame.',
  beat_sequence: [
    'Open on the practical pain point in one readable action.',
    'Introduce the product and demonstrate the useful transformation.',
  ],
  pacing: 'Fast opening, measured proof, then a clean close.',
  camera_language: 'Handheld close-up followed by a stable product detail.',
  composition: 'Keep the action central and the product label readable.',
  audio_pattern: 'Short spoken hook with quiet demonstration sounds.',
  cta_pattern: 'Close with one direct benefit-led invitation.',
});
const attestations = (avatar = false) => ({
  source_media_rights_confirmed: true,
  transformative_use_confirmed: true,
  product_assets_rights_confirmed: true,
  depicted_people_consent_confirmed: true,
  ...(avatar ? {avatar_likeness_consent_confirmed: true} : {}),
});
const selection = (strategy = 'viral_avatar_ugc', sourceId = ids.source) => {
  if (strategy === 'viral_product_swap') return {
    version: '2026-08-14.v1', strategy_id: strategy,
    recipe_version: '2026-06', duration_seconds: 4,
    resolution: '720p', audio: true,
    assets: [
      {role: 'source_video', media_id: sourceId, duration_seconds: 4},
      {role: 'original_product_image', media_id: ids.original},
      {role: 'new_product_image', media_id: ids.productMedia, view: 'front'},
    ], attestations: attestations(false),
  };
  if (strategy === 'viral_rebuild') return {
    version: '2026-08-14.v1', strategy_id: strategy,
    recipe_version: '2026-06', duration_seconds: 6,
    ratio: '1280:720', audio: false,
    assets: [
      {role: 'source_video', media_id: sourceId},
      {role: 'product_image', media_id: ids.productMedia},
      {role: 'style_image', media_id: ids.style},
    ], attestations: attestations(false),
  };
  // «Дуэт»: ровно один ассет — комментируемый ролик. Измерение разрешением:
  // кадр задаёт исходник. Длительность у ассета обязательна — по ней считается
  // посекундная цена ведущего.
  return {
    version: '2026-08-14.v1', strategy_id: strategy,
    recipe_version: '2026-06', duration_seconds: 4,
    resolution: '720p', audio: true,
    assets: [
      {role: 'source_video', media_id: sourceId, duration_seconds: 4},
    ], attestations: attestations(true),
  };
};
const input = (strategy = 'viral_avatar_ugc', index = 1) => ({
  organization_id: ids.organization,
  project_id: ids.project,
  platform: 'tiktok',
  product_category: 'other',
  selection: selection(strategy, index === 1 ? ids.source : uuid(index, '30000000')),
  editable_intent: `Create an exact product story for source ${index}.`,
  proposed_prompt: `Show a clear product demonstration for source ${index}.`,
  // Разбор механики присылает только «Создание»: правки готового видео
  // получают сцену целиком, а не пересказом.
  mechanics_summary: strategy === 'viral_product_swap' ? null : mechanics(),
  confirmation: true,
  reason: `Human prepared strategy specification ${index}.`,
  idempotency_key: `strategy-source-${index}`,
  // Товар «Дуэта» приходит ЯВНЫМ полем: фотографий товара у него нет, и
  // вывести его больше неоткуда. Остальным стратегиям этот ключ ЗАПРЕЩЁН —
  // у них товар уже назван снимками, и второй его источник однажды разойдётся
  // с первым молча.
  ...(strategy === 'viral_avatar_ugc' ? {product_id: ids.product} : {}),
});
const rules = Object.freeze({
  viral_avatar_ugc: {
    recipe: 'product_ugc', inputMode: 'video_and_avatar_images',
    // Кадр приходит из исходника — он задаёт размер холста, поверх которого
    // врезается ведущий. Но провайдеру исходник НЕ уходит: ведущего снимают
    // отдельно, соединение делает наш ffmpeg. Отсюда referenceVideo false при
    // ratio 'source' — две разные вещи, которые легко спутать.
    ratio: 'source', resolution: '720p', referenceVideo: false,
  },
  viral_product_swap: {
    recipe: 'product_swap', inputMode: 'video_and_product_images',
    ratio: 'source', resolution: '720p', referenceVideo: true,
  },
  viral_rebuild: {
    recipe: 'product_ad', inputMode: 'product_images',
    ratio: '1280:720', resolution: '720p', referenceVideo: false,
  },
});
const makeResponse = (request, index = 1) => {
  const selected = request.selection;
  const rule = rules[selected.strategy_id];
  const assetSnapshot = selected.assets.map((asset, ordinal) => {
    const source = asset.role === 'source_video';
    const product = ['product_image', 'new_product_image'].includes(asset.role);
    return {
      selection_role: asset.role,
      selection_ordinal: ordinal + 1,
      media_id: asset.media_id,
      sha256: hash(index * 100 + ordinal + 1),
      kind: source ? 'source_video' : product ? 'product_photo' : 'creator_reference',
      mime_type: source ? 'video/mp4' : 'image/png',
      product_id: product ? ids.product : null,
      rights_confirmed: true,
    };
  });
  const sourceAsset = assetSnapshot.find((asset) =>
    asset.selection_role === 'source_video');
  const sourceSelection = selected.assets.find((asset) =>
    asset.role === 'source_video');
  const source = {
    version: 'generation-strategy-exact-source-snapshot-v1',
    attachment_id: uuid(index, 'b0000000'),
    attachment_hash: hash(index * 100 + 20),
    source_id: uuid(index, 'c0000000'),
    source_hash: hash(index * 100 + 21),
    media_object_id: sourceSelection.media_id,
    media_sha256: sourceAsset.sha256,
    size_bytes: 4096 + index,
    // Длительность несут те стратегии, чей исходник уходит провайдеру: «Копия»
    // с самого начала и «Аватар» с 22.08.2026. «Создание» собирает ролик с нуля
    // и исходник видит только как разобранную механику.
    duration_seconds: rule.referenceVideo
      ? sourceSelection.duration_seconds : null,
  };
  const mechanicsSnapshot = selected.strategy_id === 'viral_product_swap'
    ? null : {
      version: 'generation-strategy-mechanics-snapshot-v1',
      strategy_id: selected.strategy_id,
      source_attachment_id: source.attachment_id,
      source_attachment_hash: source.attachment_hash,
      source_media_id: source.media_object_id,
      source_media_sha256: source.media_sha256,
      summary: clone(request.mechanics_summary),
      reviewed_by: ids.reviewer,
      review_confirmation: true,
    };
  // Цель работы зависит от стратегии: у «Копии» новый товар, у «Создания» —
  // фотографии товара, у «Дуэта» — сам комментируемый ролик: он и есть то,
  // ПРО ЧТО делается запуск.
  const targetRoles = {
    viral_avatar_ugc: ['source_video'],
    viral_product_swap: ['new_product_image'],
    viral_rebuild: ['product_image'],
  }[selected.strategy_id];
  const targetIds = selected.assets
    .filter((asset) => targetRoles.includes(asset.role))
    .map((asset) => asset.media_id);
  const scope = {
    version: 'generation-strategy-spec-scope-v1',
    authority_kind: 'strategy_recipe',
    primary_media_id: targetIds[0] ?? null,
    media_ids: targetIds.slice(0, 5),
    platform: request.platform,
    provider: 'runway',
    strategy_id: selected.strategy_id,
    recipe: rule.recipe,
    input_mode: rule.inputMode,
    duration_seconds: selected.duration_seconds,
    product_category: request.product_category,
    format: rule.ratio,
    ratio: rule.ratio,
    resolution: rule.resolution,
    audio: selected.audio,
    spoken_dialogue: false,
    reference_count: selected.assets.length - 1,
    reference_video: rule.referenceVideo,
    first_frame: false,
    last_frame: false,
    selection: clone(selected),
    selection_hash: hash(index * 100 + 30),
    asset_snapshot: assetSnapshot,
    asset_snapshot_hash: hash(index * 100 + 31),
    source,
    source_hash: hash(index * 100 + 32),
    mechanics: mechanicsSnapshot,
    mechanics_hash: mechanicsSnapshot === null ? null : hash(index * 100 + 33),
  };
  const spec = {
    spec_id: uuid(index, 'd0000000'),
    spec_version: 1,
    spec_hash: hash(index * 100 + 40),
    status: 'draft',
    exact_scope: scope,
    editable_intent: request.editable_intent,
    compiled_prompt: request.proposed_prompt,
    prompt_hash: hash(index * 100 + 41),
    research_provenance: null,
    performance_policy_provenance: null,
    repair_provenance: null,
    outcome_selection_id: null,
    created_at: '2026-08-14T08:00:00.000Z',
    updated_at: '2026-08-14T08:00:00.000Z',
  };
  return {
    ok: true,
    version: 'generation-strategy-spec-prepare-response-v1',
    generation_spec: spec,
    history: [clone(spec)],
    recommended_next_action: {
      code: 'review_and_approve_generation_spec', action: 'approve',
      label: 'Review and approve', reason: 'A human must approve this exact version.',
      requires_confirmation: true, provider_action: false, spend_action: false,
    },
    strategy: {
      strategy_id: selected.strategy_id,
      recipe: rule.recipe,
      selection_hash: scope.selection_hash,
      source_media_id: source.media_object_id,
      source_snapshot_hash: scope.source_hash,
      mechanics_required: mechanicsSnapshot !== null,
      mechanics_snapshot_hash: scope.mechanics_hash,
      human_approval_required: true,
    },
    contract: {
      server_resolved_recipe: true,
      server_resolved_source: true,
      browser_hashes_accepted: false,
      browser_source_binding_accepted: false,
      mechanics_text_is_proposal_until_spec_approval: true,
      provider_call_started: false,
      paid_start_integrated: false,
      automatic_approval: false,
    },
  };
};
const controlResponse = (prepare) => {
  const approved = clone(prepare.generation_spec);
  approved.status = 'approved';
  approved.updated_at = '2026-08-14T08:01:00.000Z';
  approved.approved_at = '2026-08-14T08:01:00.000Z';
  return {
    ok: true, version: 'generation-spec-control-v1',
    generation_spec: approved, history: [clone(approved)],
    recommended_next_action: {
      code: 'confirm_spend_for_approved_spec', action: 'confirm_spend',
      label: 'Confirm paid generation',
      reason: 'The exact immutable version was explicitly approved.',
      requires_confirmation: true, provider_action: false, spend_action: false,
    },
    automatic_approval: false,
    automatic_spend: false,
    automatic_generation: false,
  };
};
"""


def _evaluate(expression: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for generation strategy spec contracts")
    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        (directory / "subject.mjs").write_text(SOURCE, encoding="utf-8")
        (directory / "contract.mjs").write_text(
            FIXTURE
            + f"\nconst result = {expression};\n"
            + "process.stdout.write(JSON.stringify(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [node, "contract.mjs"],
            cwd=directory,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_module_is_pure_and_exports_the_full_strategy_spec_handshake() -> None:
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "document.",
        "window.",
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "supabase",
    ):
        assert forbidden not in SOURCE
    for exported in (
        "normalizeGenerationStrategySpecMechanics",
        "buildGenerationStrategySpecPrepareRequest",
        "normalizeGenerationStrategySpecPrepareResponse",
        "generationStrategySpecIdentity",
        "generationStrategySpecSafeProjection",
        "buildGenerationStrategySpecApprovalRequest",
        "normalizeGenerationStrategySpecControlResponse",
    ):
        assert f"export function {exported}" in SOURCE
    assert "automatic_approval: true" not in SOURCE
    assert "provider_call_started: true" not in SOURCE
    assert "paid_start_integrated: true" not in SOURCE


def test_mechanics_are_exact_nontrivial_and_swap_is_null_only() -> None:
    result = _evaluate(
        """
        (() => {
          // Разбор механики остался только у «Создания»: правки готового видео
          // получают сцену целиком, а не пересказом. Поэтому и валидный разбор,
          // и его нарушения проверяются на viral_rebuild, а обе правки видео —
          // на том, что механику у них присылать НЕЛЬЗЯ.
          const valid = subject.normalizeGenerationStrategySpecMechanics(
            mechanics(), 'viral_rebuild');
          const duplicate = mechanics();
          duplicate.beat_sequence[1] = duplicate.beat_sequence[0];
          const extra = mechanics(); extra.camera_motion = 'browser authority';
          return {
            valid: valid.ok,
            frozen: Object.isFrozen(valid.value.beat_sequence),
            duplicate: subject.normalizeGenerationStrategySpecMechanics(
              duplicate, 'viral_rebuild').error.code,
            extra: subject.normalizeGenerationStrategySpecMechanics(
              extra, 'viral_rebuild').error.code,
            swapNull: subject.normalizeGenerationStrategySpecMechanics(
              null, 'viral_product_swap').ok,
            swapText: subject.normalizeGenerationStrategySpecMechanics(
              mechanics(), 'viral_product_swap').error.code,
            avatarNull: subject.normalizeGenerationStrategySpecMechanics(
              null, 'viral_avatar_ugc').error.code,
            avatarText: subject.normalizeGenerationStrategySpecMechanics(
              mechanics(), 'viral_avatar_ugc').ok,
          };
        })()
        """
    )
    assert result == {
        "valid": True,
        "frozen": True,
        "duplicate": "mechanics_beats_duplicate",
        "extra": "object_keys_mismatch",
        "swapNull": True,
        "swapText": "mechanics_must_be_null",
        # ДУЭТ разбор ОБЯЗАН прислать: он и есть материал для речи ведущего.
        # Пустой разбор здесь — отказ, а не «поле можно опустить».
        "avatarNull": "object_required",
        "avatarText": True,
    }


def test_prepare_builder_emits_only_the_exact_server_dto() -> None:
    result = _evaluate(
        """
        (() => {
          // Разбор механики присылает только «Создание»: у обеих правок видео
          // его быть не должно, и это проверяется ниже отдельно.
          const ugc = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_rebuild'));
          const swap = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_product_swap'));
          const avatar = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_avatar_ugc'));
          const forbidden = input(); forbidden.spec_id = uuid(99);
          return {
            ugcOk: ugc.ok,
            keys: Object.keys(ugc.request).sort(),
            version: ugc.request.version,
            mechanicsVersion: ugc.request.mechanics_summary.version,
            swapOk: swap.ok,
            swapMechanics: swap.request.mechanics_summary,
            avatarOk: avatar.ok,
            avatarMechanicsVersion: avatar.request.mechanics_summary.version,
            forbidden: subject.buildGenerationStrategySpecPrepareRequest(
              forbidden).error.code,
            frozen: Object.isFrozen(ugc.request.selection.assets),
          };
        })()
        """
    )
    assert result == {
        "ugcOk": True,
        "keys": sorted(
            [
                "version",
                "organization_id",
                "project_id",
                "platform",
                "product_category",
                "selection",
                "editable_intent",
                "proposed_prompt",
                "mechanics_summary",
                "confirmation",
                "reason",
                "idempotency_key",
            ]
        ),
        "version": "generation-strategy-spec-prepare-request-v1",
        "mechanicsVersion": "generation-strategy-mechanics-summary-v1",
        "swapOk": True,
        "swapMechanics": None,
        # ДУЭТ разбор ролика присылает: он и есть материал для речи ведущего.
        # Без «Копии» здесь остаются двое, и это единственная стратегия с null.
        "avatarOk": True,
        "avatarMechanicsVersion": "generation-strategy-mechanics-summary-v1",
        "forbidden": "object_keys_mismatch",
        "frozen": True,
    }


def test_prepare_response_normalizes_full_scope_but_projection_strips_consent() -> None:
    result = _evaluate(
        """
        (() => {
          // Снимок механики остался только у «Создания»: правки готового
          // видео его не собирают вовсе.
          const request = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_rebuild'));
          const raw = makeResponse(request.request);
          const normalized = subject.normalizeGenerationStrategySpecPrepareResponse(
            raw, request);
          const identity = subject.generationStrategySpecIdentity(normalized);
          const projection = subject.generationStrategySpecSafeProjection(normalized);
          const serialized = JSON.stringify(projection);
          return {
            ok: normalized.ok,
            scopeVersion: normalized.value.generationSpec.exact_scope.version,
            mechanicsHash: identity.mechanics_snapshot_hash,
            identityStatus: identity.status,
            projection,
            leakedConsent: serialized.includes('attestation')
              || serialized.includes('review_confirmation')
              || serialized.includes('beat_sequence')
              || serialized.includes('compiled_prompt')
              || serialized.includes('editable_intent'),
          };
        })()
        """
    )
    assert result["ok"] is True
    assert result["scopeVersion"] == "generation-strategy-spec-scope-v2"
    assert result["identityStatus"] == "draft"
    assert len(result["mechanicsHash"]) == 64
    assert result["leakedConsent"] is False
    assert result["projection"]["human_approval_required"] is True
    assert result["projection"]["next_action"] == "approve"


def test_scope_v2_is_provider_neutral_and_v1_is_dual_read_as_deferred_route() -> None:
    result = _evaluate(
        """
        (() => {
          const request = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_product_swap'));
          const legacyRaw = makeResponse(request.request);
          const legacy = subject.normalizeGenerationStrategySpecPrepareResponse(
            legacyRaw, request);

          const v2Raw = makeResponse(request.request);
          for (const spec of [v2Raw.generation_spec, v2Raw.history[0]]) {
            spec.exact_scope.version = 'generation-strategy-spec-scope-v2';
            delete spec.exact_scope.provider;
            spec.exact_scope.route_policy = {
              version: 'generation-strategy-route-policy-v1',
              authority: 'generation_strategy_provider_routes',
              binding: 'deferred_until_preflight',
            };
          }
          const v2 = subject.normalizeGenerationStrategySpecPrepareResponse(
            v2Raw, request);
          const projection = subject.generationStrategySpecSafeProjection(v2);

          const injected = clone(v2Raw);
          injected.generation_spec.exact_scope.provider = 'runway';
          injected.history[0].exact_scope.provider = 'runway';
          const injectedResult =
            subject.normalizeGenerationStrategySpecPrepareResponse(
              injected, request);

          const forged = clone(v2Raw);
          forged.generation_spec.exact_scope.route_policy.provider = 'fal';
          forged.history[0].exact_scope.route_policy.provider = 'fal';
          const forgedResult =
            subject.normalizeGenerationStrategySpecPrepareResponse(
              forged, request);
          return {
            legacyOk: legacy.ok,
            legacyProviderPresent:
              'provider' in legacy.value.generationSpec.exact_scope,
            legacyCanonicalVersion:
              legacy.value.generationSpec.exact_scope.version,
            legacyPolicy: legacy.value.generationSpec.exact_scope.route_policy,
            v2Ok: v2.ok,
            v2Version: v2.value.generationSpec.exact_scope.version,
            v2ProviderPresent: 'provider' in v2.value.generationSpec.exact_scope,
            projectionRoute: projection.execution_route,
            injected: injectedResult.error.code,
            forged: forgedResult.error.code,
          };
        })()
        """
    )
    expected_policy = {
        "version": "generation-strategy-route-policy-v1",
        "authority": "generation_strategy_provider_routes",
        "binding": "deferred_until_preflight",
    }
    assert result == {
        "legacyOk": True,
        "legacyProviderPresent": False,
        "legacyCanonicalVersion": "generation-strategy-spec-scope-v2",
        "legacyPolicy": expected_policy,
        "v2Ok": True,
        "v2Version": "generation-strategy-spec-scope-v2",
        "v2ProviderPresent": False,
        "projectionRoute": expected_policy,
        "injected": "object_keys_mismatch",
        "forged": "object_keys_mismatch",
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            "raw.strategy.source_snapshot_hash = hash(9999);",
            "prepare_strategy_mismatch",
        ),
        (
            "raw.generation_spec.exact_scope.mechanics.source_media_sha256 = hash(9998);",
            "mechanics_source_mismatch",
        ),
        (
            "raw.generation_spec.exact_scope.asset_snapshot[2].sha256 = hash(9997);",
            "prepare_history_mismatch",
        ),
        (
            "raw.contract.automatic_approval = true;",
            "prepare_contract_invalid",
        ),
        (
            "raw.generation_spec.spec_version = 2; raw.history[0].spec_version = 2;",
            "independent_spec_required",
        ),
    ],
)
def test_prepare_response_fails_closed_on_server_authority_drift(
    mutation: str,
    code: str,
) -> None:
    result = _evaluate(
        f"""
        (() => {{
          // Снимок механики остался только у «Создания»: правки готового
          // видео его не собирают вовсе.
          const request = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_rebuild'));
          const raw = makeResponse(request.request);
          {mutation}
          return subject.normalizeGenerationStrategySpecPrepareResponse(
            raw, request).error.code;
        }})()
        """
    )
    assert result == code


def test_approval_builder_requires_explicit_human_confirmation_and_exact_cas() -> None:
    result = _evaluate(
        """
        (() => {
          // Снимок механики остался только у «Создания»: правки готового
          // видео его не собирают вовсе.
          const request = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_rebuild'));
          const draft = subject.normalizeGenerationStrategySpecPrepareResponse(
            makeResponse(request.request), request);
          const approved = subject.buildGenerationStrategySpecApprovalRequest({
            project_id: ids.project, draft,
            human_confirmation: true,
            reason: 'Human explicitly approved the exact strategy specification.',
          });
          const blocked = subject.buildGenerationStrategySpecApprovalRequest({
            project_id: ids.project, draft,
            human_confirmation: false,
            reason: 'Human explicitly approved the exact strategy specification.',
          });
          return {approved, blocked: blocked.error.code};
        })()
        """
    )
    assert result["approved"] == {
        "ok": True,
        "request": {
            "project_id": "20000000-0000-4000-8000-000000000002",
            "spec_id": "d0000000-0000-4000-8000-000000000001",
            "expected_spec_version": 1,
            "expected_spec_hash": format(140, "064x"),
            "action": "approve",
            "confirmation": True,
            "reason": "Human explicitly approved the exact strategy specification.",
        },
        "error": None,
    }
    assert result["blocked"] == "human_approval_confirmation_required"


def test_control_response_returns_only_safe_approved_context() -> None:
    result = _evaluate(
        """
        (() => {
          // Снимок механики остался только у «Создания»: правки готового
          // видео его не собирают вовсе.
          const request = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_rebuild'));
          const raw = makeResponse(request.request);
          const draft = subject.normalizeGenerationStrategySpecPrepareResponse(
            raw, request);
          const approved = subject.normalizeGenerationStrategySpecControlResponse(
            controlResponse(raw), draft);
          const projection = subject.generationStrategySpecSafeProjection(approved);
          const serialized = JSON.stringify(approved.value);
          return {
            ok: approved.ok,
            context: approved.value.approvedContext,
            projection,
            leaked: serialized.includes('beat_sequence')
              || serialized.includes('attestation')
              || serialized.includes('compiled_prompt'),
          };
        })()
        """
    )
    assert result["ok"] is True
    assert result["context"]["status"] == "approved"
    assert result["context"]["spec_version"] == 1
    assert result["projection"]["human_approval_required"] is False
    assert result["projection"]["next_action"] == "confirm_spend"
    assert result["leaked"] is False


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            "control.automatic_approval = true;",
            "control_response_identity_invalid",
        ),
        (
            "control.generation_spec.spec_hash = hash(999); control.history[0].spec_hash = hash(999);",
            "approved_spec_identity_mismatch",
        ),
        (
            "control.generation_spec.exact_scope.source_hash = hash(998); control.history[0].exact_scope.source_hash = hash(998);",
            "approved_spec_identity_mismatch",
        ),
        (
            "control.history[0].prompt_hash = hash(997);",
            "control_history_mismatch",
        ),
    ],
)
def test_control_response_rejects_cross_spec_or_non_exact_approval(
    mutation: str,
    code: str,
) -> None:
    result = _evaluate(
        f"""
        (() => {{
          // Снимок механики остался только у «Создания»: правки готового
          // видео его не собирают вовсе.
          const request = subject.buildGenerationStrategySpecPrepareRequest(
            input('viral_rebuild'));
          const raw = makeResponse(request.request);
          const draft = subject.normalizeGenerationStrategySpecPrepareResponse(
            raw, request);
          const control = controlResponse(raw);
          {mutation}
          return subject.normalizeGenerationStrategySpecControlResponse(
            control, draft).error.code;
        }})()
        """
    )
    assert result == code


def test_ten_sources_create_ten_independent_prepare_and_approved_identities() -> None:
    result = _evaluate(
        """
        (() => {
          const requests = [];
          const draftIds = [];
          const approvedIds = [];
          for (let index = 1; index <= 10; index += 1) {
            const request = subject.buildGenerationStrategySpecPrepareRequest(
              input('viral_avatar_ugc', index));
            const raw = makeResponse(request.request, index);
            const draft = subject.normalizeGenerationStrategySpecPrepareResponse(
              raw, request);
            const approved = subject.normalizeGenerationStrategySpecControlResponse(
              controlResponse(raw), draft);
            requests.push(request.request);
            draftIds.push(subject.generationStrategySpecIdentity(draft).spec_id);
            approvedIds.push(approved.value.approvedContext.spec_id);
          }
          return {
            allBuilt: requests.length === 10,
            requestHasSpecId: requests.some((request) => 'spec_id' in request),
            idempotencyCount: new Set(requests.map((request) =>
              request.idempotency_key)).size,
            sourceCount: new Set(requests.map((request) =>
              request.selection.assets[0].media_id)).size,
            draftSpecCount: new Set(draftIds).size,
            approvedSpecCount: new Set(approvedIds).size,
            headsPreserved: draftIds.every((id, index) => id === approvedIds[index]),
          };
        })()
        """
    )
    assert result == {
        "allBuilt": True,
        "requestHasSpecId": False,
        "idempotencyCount": 10,
        "sourceCount": 10,
        "draftSpecCount": 10,
        "approvedSpecCount": 10,
        "headsPreserved": True,
    }


def test_all_three_strategy_recipes_and_swap_null_mechanics_round_trip() -> None:
    result = _evaluate(
        """
        (() => Object.fromEntries([
          'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild',
        ].map((strategy, index) => {
          const request = subject.buildGenerationStrategySpecPrepareRequest(
            input(strategy, index + 1));
          const response = subject.normalizeGenerationStrategySpecPrepareResponse(
            makeResponse(request.request, index + 1), request);
          return [strategy, {
            request: request.ok,
            response: response.ok,
            recipe: response.value?.strategy.recipe,
            mechanics: response.value?.generationSpec.exact_scope.mechanics,
          }];
        })))()
        """
    )
    assert result["viral_avatar_ugc"]["recipe"] == "product_ugc"
    assert result["viral_product_swap"] == {
        "request": True,
        "response": True,
        "recipe": "product_swap",
        "mechanics": None,
    }
    assert result["viral_rebuild"]["recipe"] == "product_ad"
    assert all(item["request"] and item["response"] for item in result.values())
