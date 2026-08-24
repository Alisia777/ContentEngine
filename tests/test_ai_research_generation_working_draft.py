import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pglast import parse_sql


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608110006_ai_research_generation_working_draft.sql"
)
CONFLICT_HOTFIX_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202608160001_stop_working_draft_conflict_retry_storm.sql"
)
PGTAP_PATH = (
    ROOT
    / "supabase"
    / "tests"
    / "ai_research_generation_working_draft_test.sql"
)
MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")
CONFLICT_HOTFIX = CONFLICT_HOTFIX_PATH.read_text(encoding="utf-8")
PGTAP = PGTAP_PATH.read_text(encoding="utf-8")
GENERATION = (
    ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
).read_text(encoding="utf-8")
TRAINING = (
    ROOT / "web" / "app" / "workspace-ai-research-training.js"
).read_text(encoding="utf-8")
WORKING_MODULE = (
    ROOT / "web" / "app" / "generation-ai-research-working-draft.js"
).read_text(encoding="utf-8")
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
BOOTSTRAP = (
    ROOT / "web" / "app" / "workspace-research-training-bootstrap.js"
).read_text(encoding="utf-8")


def test_sql_and_executable_pgtap_parse() -> None:
    assert parse_sql(MIGRATION)
    assert parse_sql(CONFLICT_HOTFIX)
    assert parse_sql(PGTAP)


def test_app_parses_under_the_browser_esm_goal() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    app_path = ROOT / "web" / "app" / "app.js"
    script = f"""
      import fs from 'node:fs';
      import vm from 'node:vm';
      const source = fs.readFileSync({json.dumps(str(app_path))}, 'utf8');
      new vm.SourceTextModule(source, {{identifier: 'app.js'}});
      console.log('app-esm-parse: PASS');
    """
    result = subprocess.run(
        [node, "--experimental-vm-modules", "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    assert "app-esm-parse: PASS" in result.stdout
    assert "window.queueMicrotask(async () => {" in APP


def test_resolver_derives_identity_and_never_accepts_url_category() -> None:
    resolver_start = MIGRATION.index(
        "public.contentengine_generation_research_recommendation("
    )
    resolver_end = MIGRATION.index(
        "create table if not exists\n  content_factory.generation_ai_research_working_drafts",
        resolver_start,
    )
    resolver = MIGRATION[resolver_start:resolver_end]

    assert "'organization_id', 'project_id', 'selection_id'" in resolver
    assert "'recommendation_position'" in resolver
    assert "product_category" not in resolver.split(
        "content_factory_private.ai_research_recommendation_snapshot", 1
    )[0]
    assert "'category_is_server_derived', true" in resolver
    assert "'product_identity_is_server_derived', true" in resolver
    assert "'url_category_is_not_authority', true" in resolver
    assert "'selection_does_not_prove_current_media_identity', true" in resolver
    assert "'can_auto_apply', false" in MIGRATION
    assert "'scope_match', 'selected_product_advisory'" in MIGRATION


def test_shared_table_is_one_project_draft_and_stores_no_operational_authority() -> None:
    table_start = MIGRATION.index(
        "content_factory.generation_ai_research_working_drafts ("
    )
    table_end = MIGRATION.index(
        "create index if not exists generation_ai_research_working_updated_idx",
        table_start,
    )
    table = MIGRATION[table_start:table_end].lower()
    for forbidden in (
        "campaign_id",
        "destination_ref",
        "media_id",
        "count",
        "spend_confirmation",
        "access_token",
        "authorization",
        "blob",
    ):
        assert forbidden not in table
    assert "unique (organization_id, project_id)" in table
    assert "revision bigint" in table
    assert "last_mutation_id uuid" in table
    assert "status in ('active', 'cleared')" in table
    assert "enable row level security" in MIGRATION.lower()
    assert "optimistic_concurrency" in MIGRATION
    assert "one_active_draft_per_project" in MIGRATION


def test_working_rpc_has_cas_idempotency_and_project_acl() -> None:
    assert "require_workspace_project_access(" in MIGRATION
    assert "for update;" in MIGRATION
    assert "current_row.last_mutation_id = mutation_id_value" in MIGRATION
    assert "coalesce(current_row.revision, 0) <> expected_revision_value" in MIGRATION
    assert "generation_ai_research_working_draft_revision_conflict" in MIGRATION
    # 202608110006 применена в облако с sha256 в трекере и обязана оставаться
    # байт-в-байт применённой формой (errcode 40001). Терминальный PT409
    # приходит ТОЛЬКО хотфиксом 202608160001 — он и даёт финальное состояние.
    assert "errcode = '40001'" in MIGRATION
    assert "errcode = 'PT409'" not in MIGRATION
    assert "retryable_fragment constant text := 'errcode = ''40001'''" in CONFLICT_HOTFIX
    assert "terminal_fragment constant text := 'errcode = ''PT409'''" in CONFLICT_HOTFIX
    assert "revision = draft.revision + 1" in MIGRATION
    assert "from public, anon;" in MIGRATION
    assert "to authenticated, service_role;" in MIGRATION
    # The immutable learning selection needs no SELECT lock in a STABLE helper.
    snapshot_start = MIGRATION.index(
        "content_factory_private.ai_research_recommendation_snapshot("
    )
    snapshot_end = MIGRATION.index(
        "public.contentengine_generation_research_recommendation(", snapshot_start
    )
    assert "for share" not in MIGRATION[snapshot_start:snapshot_end].lower()


def test_client_conflicts_stop_retries_and_offer_explicit_recovery() -> None:
    stop_start = GENERATION.index("function stopWorkingDraftConflictRetries()")
    stop_end = GENERATION.index(
        "function scheduleWorkingDraftHydrateRetry", stop_start
    )
    stop_block = GENERATION[stop_start:stop_end]
    assert "runtime.workingDraftConflict = true" in stop_block
    assert "runtime.workingDraftSavePending = false" in stop_block
    assert "window.clearTimeout(runtime.workingDraftSaveTimer)" in stop_block
    assert 'renderWorkingDraftRecovery("conflict")' in stop_block

    schedule_start = GENERATION.index("function scheduleWorkingDraftSave()")
    schedule_end = GENERATION.index("async function clearWorkingDraft()", schedule_start)
    schedule_block = GENERATION[schedule_start:schedule_end]
    assert "if (runtime.workingDraftConflict)" in schedule_block
    assert "return;" in schedule_block
    drop_branch = schedule_block[
        schedule_block.index("if (runtime.workingDraftConflict)") :
        schedule_block.index("return;")
    ]
    # A silently swallowed sync re-asserts the persistent banner instead.
    assert 'renderWorkingDraftRecovery("conflict")' in drop_branch

    hydrate_start = GENERATION.index("async function hydrateSharedWorkingDraft")
    hydrate_end = GENERATION.index("function briefControl", hydrate_start)
    hydrate_block = GENERATION[hydrate_start:hydrate_end]
    assert 'setWorkingDraftAuthority(context.projectId, "verified")' in hydrate_block
    assert "runtime.workingDraftConflict = false" in hydrate_block

    resolve_start = GENERATION.index(
        "async function resolveWorkingDraftConflict("
    )
    resolve_end = GENERATION.index(
        "function applySharedWorkingDraft(", resolve_start
    )
    resolve = GENERATION[resolve_start:resolve_end]
    # Both strategies begin with an authoritative force re-read (no cache join)
    # guarded against in-flight save/hydrate and cross-form/project races.
    assert "{ force: true }" in resolve
    assert "runtime.workingDraftSaving" in resolve
    assert "runtime.workingDraftHydrating" in resolve
    assert "runtime.form !== form" in resolve
    assert "formContext(form).projectId !== context.projectId" in resolve
    theirs_start = resolve.index('if (strategy === "theirs")')
    mine_start = resolve.index("scheduleWorkingDraftSave()")
    assert theirs_start < mine_start
    assert "applySharedWorkingDraft(form, fresh)" in resolve[theirs_start:mine_start]
    # Binding decision: a cleared tombstone is never silently re-created by
    # "keep mine" — the fresh tombstone leaves only the take-theirs action.
    tombstone_guard = resolve[
        resolve.index('if (strategy === "mine" && freshTombstone)') :
        resolve.index('if (strategy === "theirs")')
    ]
    assert 'renderWorkingDraftRecovery("conflict")' in tombstone_guard
    assert "return;" in tombstone_guard
    assert "authorizeTombstoneReplacement" not in resolve
    assert resolve.index("runtime.workingDraftConflict = false") > resolve.index(
        'if (strategy === "mine" && freshTombstone)'
    )


def test_ai_center_cta_carries_only_server_selection_and_position() -> None:
    assert "generationRecommendationDeepLink" in TRAINING
    assert "selection_id: selectionId" in TRAINING
    assert "recommendation_position: String(position)" in TRAINING
    deep_link = TRAINING[
        TRAINING.index("function generationRecommendationDeepLink") :
        TRAINING.index("function learnedRecommendationCard")
    ]
    assert "category" not in deep_link
    assert "product_name" not in deep_link
    assert "Использовать этот вариант в «Создать»" in TRAINING


def test_multiple_variants_wait_for_human_and_preserve_arbitrary_position() -> None:
    insight_start = TRAINING.index("function insightCard(")
    insight_end = TRAINING.index("function categoryInsight(", insight_start)
    insight = TRAINING[insight_start:insight_end]
    scenario_start = TRAINING.index("function scenarioCard(")
    scenario_end = TRAINING.index("function sourceCard(", scenario_start)
    scenario = TRAINING[scenario_start:scenario_end]
    assert "checkbox.checked = false;" in insight
    assert "checkbox.checked = false;" in scenario
    assert "checkbox.checked = position === 1" not in scenario
    assert "checked:" not in TRAINING
    assert "learned.recommendations.forEach" in TRAINING
    assert "requestExplicitRecommendation(selectedEnvelope())" in GENERATION
    assert "applyRecommendation(defaultPreview" not in GENERATION
    assert "applyRecommendation(first" not in GENERATION
    assert "activeIndex: -1" in GENERATION
    assert "all_approved_variants_returned" in MIGRATION

    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    generation_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    training_url = (
        ROOT / "web" / "app" / "workspace-ai-research-training.js"
    ).as_uri()
    script = f"""
      const generation = await import({json.dumps(generation_url)});
      const training = await import({json.dumps(training_url)});
      const selectionId = 'b979e33c-4ab6-4592-9c13-90eabd1ba712';
      const variants = [1, 2, 3].map((position) => ({{
        selection_id: selectionId,
        recommendation_position: position,
        recommendation: {{position, title: `Option ${{position}}`}},
      }}));
      const learned = training.normalizeLearnedResearch({{
        selection_id: selectionId,
        project_id: '22222222-2222-4222-8222-222222222222',
        decision: 'approve',
        selected_scenario_positions: [1, 2, 3],
        recommendations: variants.map((item) => item.recommendation),
      }});
      const chosen = [3, 1, 2].map((recommendationPosition) => (
        generation.explicitResearchRecommendationForTarget(variants, {{
          selectionId, recommendationPosition,
        }})?.recommendation_position ?? null
      ));
      const noChoice = generation.explicitResearchRecommendationForTarget(
        variants, null,
      );
      const ambiguous = generation.explicitResearchRecommendationForTarget(
        [...variants, variants[0]],
        {{selectionId, recommendationPosition: 1}},
      );
      const auto = generation.shouldAutoApplyResearchRecommendation({{
        brief: '', touched: false, canAutoApply: true, recommendation: variants[0],
      }});
      console.log(JSON.stringify({{
        learnedPositions: learned.recommendations.map((item) => item.position),
        chosen,
        noChoice: noChoice ?? null,
        ambiguous: ambiguous ?? null,
        auto,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value == {
        "learnedPositions": [1, 2, 3],
        "chosen": [3, 1, 2],
        "noChoice": None,
        "ambiguous": None,
        "auto": False,
    }


def test_generation_uses_exact_selection_resolver_before_category_lookup() -> None:
    assert 'const RPC_RECOMMENDATION = "contentengine_generation_research_recommendation"' in GENERATION
    assert "routeRecommendationTarget()" in GENERATION
    assert "rememberedSelectionId" in GENERATION
    assert "api.generationResearchRecommendation" in GENERATION
    assert "selection_id: target.selectionId" in GENERATION
    assert "recommendation_position: target.recommendationPosition" in GENERATION
    assert "generation_research_recommendation_response_mismatch" in GENERATION
    assert 'form.dataset.researchRecommendationVerificationState = "verified"' in GENERATION
    assert "applyRecommendation(selected, { explicit: true })" in GENERATION


def test_server_hydration_precedes_session_fallback_and_tombstone_wins() -> None:
    restore_start = APP.index("async function restoreGenerationFormDraft(form)")
    restore_end = APP.index("function clearGenerationFormDraft()", restore_start)
    restore = APP[restore_start:restore_end]
    assert restore.index("readGenerationAiResearchWorkingDraft(") < restore.index(
        "restoreLocalGenerationFormDraft(form)"
    )
    assert "Number(shared?.revision) > 0" in restore
    assert "clearStoredGenerationAiResearchSelectionHints()" in restore
    assert "clearGenerationAiResearchLineageFromForm(form)" in restore
    assert "authoritativeEmptyHandled" in restore
    assert "Старая локальная рекомендация не восстановлена" in restore


def test_active_server_draft_merges_only_tab_local_operational_choices_first() -> None:
    restore_start = APP.index("async function restoreGenerationFormDraft(form)")
    restore_end = APP.index("function clearGenerationFormDraft()", restore_start)
    restore = APP[restore_start:restore_end]
    active = restore[
        restore.index("if (shared?.draft)") : restore.index(
            "else if (Number(shared?.revision) > 0)"
        )
    ]
    assert active.index(
        "restoreLocalGenerationFormDraft(form, { operationalOnly: true })"
    ) < active.index("applyGenerationAiResearchWorkingDraft(form, shared)")
    local_start = APP.index("function restoreLocalGenerationFormDraft(")
    local_end = APP.index("function applyGenerationAiResearchWorkingDraft", local_start)
    local = APP[local_start:local_end]
    for field in (
        "campaign_id",
        "destination_ref",
        "media_id",
        "primary_media_id",
        "assignee_id",
        "payout_rub",
        "count",
        "generation_reference_url",
        "generation_reference_mechanics",
    ):
        assert field in local
    assert "if (!operationalOnly && values.scenario_intent)" in local
    assert "if (!restoredMediaCount && !operationalOnly)" in local
    assert "Подтверждение оплаты никогда не сохраняется" in local


def test_server_unavailable_local_ai_is_blocked_until_exact_verification() -> None:
    assert "storedGenerationAiResearchSelectionHint()" in APP
    assert "requireGenerationAiResearchSelectionVerification(" in APP
    assert 'serverUnavailable ? "failed" : "pending"' in APP
    assert "Локальный ИИ‑замысел показан" in APP
    prepare_start = APP.index("function generationSpecPreparePayload(form)")
    prepare_end = APP.index("function generationSpecPayloadKey", prepare_start)
    prepare = APP[prepare_start:prepare_end]
    assert "researchRecommendationVerificationRequired" in prepare
    assert "researchRecommendationVerificationState !== \"verified\"" in prepare
    assert "return null" in prepare


def test_second_user_response_contains_verified_product_and_creative_fields() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "generation-ai-research-working-draft.js"
    ).as_uri()
    response = {
        "ok": True,
        "version": "generation-ai-research-working-draft-v1",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "project_id": "22222222-2222-4222-8222-222222222222",
        "revision": 4,
        "draft": {
            "id": "33333333-3333-4333-8333-333333333333",
            "revision": 4,
            "selection_id": "b979e33c-4ab6-4592-9c13-90eabd1ba712",
            "recommendation_position": 2,
            "editable_fields": {
                "product_category": "household",
                "platform": "youtube",
                "generation_mode": "real_seedance",
                "duration_seconds": 8,
                "format": "9:16",
                "brief": "MILIO option 2 shared brief",
            },
            "applied_fields": [
                "product_category",
                "platform",
                "mode",
                "duration_seconds",
                "format",
                "brief",
            ],
            "touched_fields": ["brief"],
            "previous_values": {"brief": ""},
            "last_applied_values": {"brief": "MILIO option 2 original"},
            "auto_apply_disabled": False,
            "updated_by": "44444444-4444-4444-8444-444444444444",
            "updated_at": "2026-08-11T12:00:00Z",
            "recommendation": {
                "selection_id": "b979e33c-4ab6-4592-9c13-90eabd1ba712",
                "selection_hash": "a" * 64,
                "recommendation_hash": "b" * 64,
                "recommendation_position": 2,
                "project_id": "22222222-2222-4222-8222-222222222222",
                "product_id": "55555555-5555-4555-8555-555555555555",
                "product_category": "household",
                "source_product_name": "Аэрогриль MILIO A425D-Black",
                "source_product_sku": "518413561",
                "scope_match": "selected_product_advisory",
                "can_auto_apply": False,
                "preset": {"product_category": "household"},
                "recommendation": {"position": 2, "title": "Option 2"},
            },
        },
        "contract": {
            "server_backed": True,
            "project_shared": True,
            "one_active_draft_per_project": True,
            "optimistic_concurrency": True,
            "financial_fields_stored": False,
            "spend_confirmation_stored": False,
            "authorization_stored": False,
            "media_or_blobs_stored": False,
            "external_call_started": False,
            "paid_call_started": False,
        },
    }
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const value = mod.normalizeGenerationAiResearchWorkingDraftResponse(
        {json.dumps(response, ensure_ascii=False)},
        '22222222-2222-4222-8222-222222222222',
      );
      console.log(JSON.stringify(value));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value["revision"] == 4
    assert value["draft"]["selectionId"] == "b979e33c-4ab6-4592-9c13-90eabd1ba712"
    assert value["draft"]["recommendationPosition"] == 2
    assert value["draft"]["editableFields"] == response["draft"]["editable_fields"]
    assert value["draft"]["recommendation"]["source_product_sku"] == "518413561"
    assert value["draft"]["recommendation"]["source_product_name"].startswith("Аэрогриль MILIO")


def test_fresh_and_cleared_server_snapshots_normalize_without_local_fallback() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "generation-ai-research-working-draft.js"
    ).as_uri()
    contract = {
        "server_backed": True,
        "project_shared": True,
        "one_active_draft_per_project": True,
        "optimistic_concurrency": True,
        "financial_fields_stored": False,
        "spend_confirmation_stored": False,
        "authorization_stored": False,
        "media_or_blobs_stored": False,
        "external_call_started": False,
        "paid_call_started": False,
    }
    base = {
        "ok": True,
        "version": "generation-ai-research-working-draft-v1",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "project_id": "22222222-2222-4222-8222-222222222222",
        "draft": None,
        "contract": contract,
    }
    responses = [
        {**base, "revision": 0},
        {
            **base,
            "revision": 8,
            "cleared_at": "2026-08-11T12:10:00Z",
            "updated_by": "44444444-4444-4444-8444-444444444444",
        },
    ]
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const values = {json.dumps(responses)}.map((raw) =>
        mod.normalizeGenerationAiResearchWorkingDraftResponse(
          raw,
          '22222222-2222-4222-8222-222222222222',
        )
      );
      console.log(JSON.stringify(values));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    values = json.loads(result.stdout)
    assert [value["revision"] for value in values] == [0, 8]
    assert all(value["draft"] is None for value in values)
    assert MIGRATION.count("'spend_confirmation_stored', false") >= 3


def test_exact_product_identity_blocks_target_shared_and_later_media_mismatch() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "generation-ai-research-working-draft.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const recommendation = '55555555-5555-4555-8555-555555555555';
      const otherMedia = '66666666-6666-4666-8666-666666666666';
      console.log(JSON.stringify({{
        emptyMediaHydration: mod.resolveGenerationAiResearchProductIdentity(
          recommendation, ''
        ),
        exactMedia: mod.resolveGenerationAiResearchProductIdentity(
          recommendation, recommendation, {{ requireSelectedMedia: true }}
        ),
        targetedMismatch: mod.resolveGenerationAiResearchProductIdentity(
          recommendation, otherMedia
        ),
        laterMediaSwitch: mod.resolveGenerationAiResearchProductIdentity(
          recommendation, otherMedia, {{ requireSelectedMedia: true }}
        ),
        exactHandoff: mod.resolveGenerationExpectedProductMatch({{
          expectedSku: 'BAD-LION-001',
          expectedProductName: 'Ежовик гребенчатый',
          candidateSku: 'BAD-LION-001',
          candidateProductName: 'Ежовик гребенчатый',
        }}),
        oldAirfryerHandoff: mod.resolveGenerationExpectedProductMatch({{
          expectedSku: 'BAD-LION-001',
          expectedProductName: 'Ежовик гребенчатый',
          candidateSku: 'AIR-425',
          candidateProductName: 'Аэрогриль MILIO',
        }}),
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    decisions = json.loads(result.stdout)
    assert decisions["emptyMediaHydration"] == {
        "ok": True,
        "code": "authoritative_product_without_media",
    }
    assert decisions["exactMedia"] == {"ok": True, "code": "exact_product_match"}
    assert decisions["targetedMismatch"] == {"ok": False, "code": "product_mismatch"}
    assert decisions["laterMediaSwitch"] == {"ok": False, "code": "product_mismatch"}
    assert decisions["exactHandoff"] == {
        "required": True,
        "ok": True,
        "code": "exact_handoff_product_match",
    }
    assert decisions["oldAirfryerHandoff"] == {
        "required": True,
        "ok": False,
        "code": "handoff_product_mismatch",
    }

    # The executable decision is wired into all three stateful boundaries.
    assert "if (!recommendationProductIdentityMatches(form, exactTarget))" in GENERATION
    assert "if (!applyAuthoritativeRecommendationProduct(runtime.form, envelope))" in GENERATION
    assert "if (!applyAuthoritativeRecommendationProduct(form, draft.recommendation))" in GENERATION
    assert "generation_research_recommendation_product_mismatch" in GENERATION
    assert "generationAiResearchProductIdentityMatches(form, identity);" in APP
    assert "if (!generationAiResearchProductIdentityMatches(form, identity)) return null;" in APP
    assert 'form.elements.real_spend_confirmation.checked = false' in APP


def test_passive_shared_draft_requires_exact_selected_product_before_writing_fields() -> None:
    app_start = APP.index("function applyGenerationAiResearchWorkingDraft(")
    app_end = APP.index("async function restoreGenerationFormDraft(", app_start)
    app_apply = APP[app_start:app_end]
    shared_start = GENERATION.index("function applySharedWorkingDraft(")
    shared_end = GENERATION.index(
        "async function hydrateSharedWorkingDraft(", shared_start
    )
    shared_apply = GENERATION[shared_start:shared_end]
    provider_start = APP.index(
        "async function hydrateGenerationAiResearchProviderPrompt("
    )
    provider_end = min(
        index
        for index in (
            APP.find("\nfunction ", provider_start + 1),
            APP.find("\nasync function ", provider_start + 1),
        )
        if index >= 0
    )
    provider = APP[provider_start:provider_end]

    for source in (app_apply, shared_apply, provider):
        assert "requireSelectedMedia: true" in source
    assert "if (productFailure)" in app_apply
    assert app_apply.index("if (productFailure)") < app_apply.index(
        'setValue("sku"'
    )
    assert "if (passiveProductFailure)" in shared_apply
    assert shared_apply.index("if (passiveProductFailure)") < shared_apply.index(
        "applyAuthoritativeRecommendationProduct(form, draft.recommendation)"
    )
    assert "selected_media_product_unverified" in app_apply
    assert "selected_media_product_unverified" in provider
    assert "generation_research_selected_media_required" in provider
    assert "resolveGenerationExpectedProductMatch" in app_apply
    assert "handoff_product_mismatch" in app_apply
    assert "resolveGenerationExpectedProductMatch" in shared_apply
    assert "passiveProductFailure" in shared_apply

    render_start = APP.index("function renderGenerationSection(")
    render_end = APP.index("function ", render_start + 1)
    render = APP[render_start:render_end]
    assert "const handoffProduct = handoff" in render
    assert "expectedSku: String(handoff.sku" in render
    assert "expectedProductName: String(handoff.productName" in render
    assert render.count("...handoffProduct") >= 2
    assert 'data-generation-handoff-sku="${escapeHtml(' in render
    assert 'data-generation-handoff-product-name="${escapeHtml(' in render
    route_selection = render[
        render.index("const routeSelectedMedia =") : render.index(
            "const automaticMediaId ="
        )
    ]
    assert "chooseInitialGenerationMedia([routeSelectedMedia]" in route_selection
    assert "...handoffProduct" in route_selection


def test_verified_media_identity_survives_exact_resolver_and_shared_draft_reapply() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    readiness_url = (
        ROOT / "web" / "app" / "generation-form-readiness.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const readinessMod = await import({json.dumps(readiness_url)});
      const productId = '55555555-5555-4555-8555-555555555555';
      const otherProductId = '77777777-7777-4777-8777-777777777777';
      const mediaId = '66666666-6666-4666-8666-666666666666';

      function fixture(
        identityProductId = productId,
        rightsConfirmed = true,
        extraMedia = null,
      ) {{
        const sku = {{value: '518413561', readOnly: true, dataset: {{
          mediaIdentityValue: '518413561'
        }}}};
        const productName = {{
          value: 'Аэрогриль MILIO A425D-Black', readOnly: true, dataset: {{
            mediaIdentityValue: 'Аэрогриль MILIO A425D-Black'
          }},
        }};
        const media = {{
          name: 'media_id', value: mediaId, checked: true, disabled: false,
          dataset: {{
            mediaIdentityVerified: 'true', mediaProductId: identityProductId,
            mediaRightsConfirmed: rightsConfirmed ? 'true' : 'false',
            mediaSku: '518413561',
            mediaProductName: 'Аэрогриль MILIO A425D-Black',
          }},
        }};
        const primary = {{
          name: 'primary_media_id', value: mediaId, checked: true,
          disabled: false, dataset: {{}},
        }};
        const mediaItems = [media, ...(extraMedia ? [extraMedia] : [])];
        return {{
          sku, productName,
          form: {{
            dataset: {{
              identityProductId,
              primaryGenerationMediaId: mediaId,
            }},
            elements: {{sku, product_name: productName}},
            querySelectorAll(selector) {{
              if (selector === 'input[name="media_id"]') return mediaItems;
              if (selector === 'input[name="primary_media_id"]') return [primary];
              return [];
            }},
          }},
        }};
      }}

      const exact = fixture();
      const missingDisplayFields = {{
        product_id: productId,
        product_category: 'household',
        source_product_sku: '',
        source_product_name: '',
      }};
      // The delayed exact resolver and the shared-draft hydrate both use this
      // boundary. Repeating it must not erase the identity populated at step 5.
      const exactResolver = mod.applyAuthoritativeRecommendationProduct(
        exact.form, missingDisplayFields,
      );
      const afterExactResolver = {{
        sku: exact.sku.value, productName: exact.productName.value,
      }};
      const sharedHydrate = mod.applyAuthoritativeRecommendationProduct(
        exact.form, missingDisplayFields,
      );
      const afterSharedHydrate = {{
        sku: exact.sku.value, productName: exact.productName.value,
      }};
      const readiness = readinessMod.evaluateGenerationFormReadiness({{
        mode: 'real_seedance',
        sku: exact.sku.value,
        productName: exact.productName.value,
        productCategory: 'household',
        platform: 'youtube',
        destinationRef: '@milio',
        mediaCount: 1,
        brief: 'Точный замысел из выбранного человеком варианта ИИ-центра.',
        campaignId: '88888888-8888-4888-8888-888888888888',
        spendAllowed: true,
        confirmationMatches: true,
        count: 1,
        maxMockCount: 10,
      }});

      const manual = mod.resolveAuthoritativeRecommendationProductFields({{
        recommendationSku: '', recommendationProductName: '',
        currentSku: '518413561', currentProductName: 'Моё точное название',
      }});
      const recommendation = mod.resolveAuthoritativeRecommendationProductFields({{
        recommendationSku: 'SERVER-SKU',
        recommendationProductName: 'Серверное название',
        currentSku: 'HUMAN-SKU', currentProductName: 'Ручное название',
      }});
      const incompleteRecommendation =
        mod.resolveAuthoritativeRecommendationProductFields({{
          recommendationSku: 'PARTIAL-SERVER-SKU',
          recommendationProductName: '',
          currentSku: '518413561',
          currentProductName: 'Моё точное название',
        }});
      const noRights = fixture(productId, false);
      const noRightsApplied = mod.applyAuthoritativeRecommendationProduct(
        noRights.form,
        {{
          product_id: productId,
          source_product_sku: 'SERVER-SKU',
          source_product_name: 'Серверное название',
        }},
      );
      const noRightsValues = [noRights.sku.value, noRights.productName.value];
      const mixed = fixture(productId, true, {{
        name: 'media_id',
        value: '99999999-9999-4999-8999-999999999999',
        checked: true,
        disabled: false,
        dataset: {{
          mediaIdentityVerified: 'true',
          mediaRightsConfirmed: 'true',
          mediaProductId: otherProductId,
          mediaSku: 'OTHER-SKU',
          mediaProductName: 'Different product',
        }},
      }});
      const mixedBefore = [mixed.sku.value, mixed.productName.value];
      const mixedApplied = mod.applyAuthoritativeRecommendationProduct(
        mixed.form, missingDisplayFields,
      );
      const mixedAfter = [mixed.sku.value, mixed.productName.value];
      const mismatch = fixture(otherProductId);
      const mismatchBefore = [mismatch.sku.value, mismatch.productName.value];
      const mismatchApplied = mod.applyAuthoritativeRecommendationProduct(
        mismatch.form, missingDisplayFields,
      );
      const mismatchAfter = [mismatch.sku.value, mismatch.productName.value];
      console.log(JSON.stringify({{
        exactResolver, sharedHydrate, afterExactResolver, afterSharedHydrate,
        readiness: {{
          ready: readiness.ready,
          productComplete:
            readiness.steps.find((step) => step.key === 'product')?.complete,
        }},
        readOnly: [exact.sku.readOnly, exact.productName.readOnly],
        mediaIdentityValues: [
          exact.sku.dataset.mediaIdentityValue,
          exact.productName.dataset.mediaIdentityValue,
        ],
        productCategory: exact.form.dataset.researchRecommendationProductCategory,
        manual, recommendation, incompleteRecommendation,
        noRightsApplied, noRightsValues,
        mixedApplied, mixedBefore, mixedAfter,
        mismatchApplied, mismatchBefore, mismatchAfter,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    exact = {
        "sku": "518413561",
        "productName": "Аэрогриль MILIO A425D-Black",
    }
    assert value["exactResolver"] is True
    assert value["sharedHydrate"] is True
    assert value["afterExactResolver"] == exact
    assert value["afterSharedHydrate"] == exact
    assert value["readiness"] == {"ready": True, "productComplete": True}
    assert value["readOnly"] == [True, True]
    assert value["mediaIdentityValues"] == list(exact.values())
    assert value["productCategory"] == "household"
    assert value["manual"] == {
        "sku": "518413561",
        "productName": "Моё точное название",
        "source": "preserved",
    }
    assert value["recommendation"] == {
        "sku": "SERVER-SKU",
        "productName": "Серверное название",
        "source": "recommendation",
    }
    assert value["incompleteRecommendation"] == {
        "sku": "518413561",
        "productName": "Моё точное название",
        "source": "preserved",
    }
    assert value["noRightsApplied"] is False
    assert value["noRightsValues"] == list(exact.values())
    assert value["mixedApplied"] is False
    assert value["mixedBefore"] == value["mixedAfter"] == list(exact.values())
    assert value["mismatchApplied"] is False
    assert value["mismatchBefore"] == value["mismatchAfter"]


def test_non_deep_link_choice_requires_exact_server_resolution_and_never_silent_applies() -> None:
    assert "requestExplicitRecommendation(selectedEnvelope())" in GENERATION
    assert "generationResearchRecommendation" in GENERATION
    assert "researchRecommendationVerificationState !== \"verified\"" in GENERATION
    assert "applyRecommendation(first, { explicit: false })" not in GENERATION
    assert "return false;\n}" in GENERATION[
        GENERATION.index("export function shouldAutoApplyResearchRecommendation") :
        GENERATION.index("function el(", GENERATION.index("export function shouldAutoApplyResearchRecommendation"))
    ]
    assert "generationAiResearchSelectionContextMatches(form)" in APP
    assert "selection_verification_missing" in APP
    assert "generation_spec_ai_research_selection_unverified" in APP


def test_active_lineage_category_change_is_a_stable_fail_closed_blocker() -> None:
    assert "function generationAiResearchLineageActive(form)" in APP
    assert '"category_mismatch"' in APP
    assert "Категория изменена после применения рекомендации ИИ‑центра" in APP
    binding_start = APP.index("function generationSpecAiResearchBindingMatches(")
    binding_end = APP.index("function normalizeGenerationSpecAiResearchBinding", binding_start)
    binding = APP[binding_start:binding_end]
    assert "return !generationAiResearchLineageActive(form)" in binding
    prepare_start = APP.index("function generationSpecPreparePayload(form)")
    prepare_end = APP.index("function generationSpecPayloadKey", prepare_start)
    assert "generationAiResearchSelectionContextMatches(form)" in APP[
        prepare_start:prepare_end
    ]


def test_cache_race_prefers_newer_tombstone_across_force_reads_and_runtime() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "generation-ai-research-working-draft.js"
    ).as_uri()
    contract = {
        "server_backed": True,
        "project_shared": True,
        "one_active_draft_per_project": True,
        "optimistic_concurrency": True,
        "financial_fields_stored": False,
        "spend_confirmation_stored": False,
        "authorization_stored": False,
        "media_or_blobs_stored": False,
        "external_call_started": False,
        "paid_call_started": False,
    }
    project_id = "22222222-2222-4222-8222-222222222222"
    fresh = {
        "ok": True,
        "version": "generation-ai-research-working-draft-v1",
        "organization_id": "11111111-1111-4111-8111-111111111111",
        "project_id": project_id,
        "revision": 0,
        "draft": None,
        "contract": contract,
    }
    tombstone = {**fresh, "revision": 8}
    script = f"""
      const mod = await import({json.dumps(module_url)});
      let resolveOld;
      let resolveNew;
      let calls = 0;
      const api = {{
        call() {{}},
        generationAiResearchWorkingDraft() {{
          calls += 1;
          return new Promise((resolve) => {{
            if (calls === 1) resolveOld = resolve;
            else resolveNew = resolve;
          }});
        }},
      }};
      const oldRead = mod.readGenerationAiResearchWorkingDraft(
        api, {json.dumps(project_id)}, {{ force: true }}
      );
      const newRead = mod.readGenerationAiResearchWorkingDraft(
        api, {json.dumps(project_id)}, {{ force: true }}
      );
      resolveNew({json.dumps(tombstone)});
      const newest = await newRead;
      resolveOld({json.dumps(fresh)});
      const staleResult = await oldRead;
      const cached = mod.cachedGenerationAiResearchWorkingDraft(
        {json.dumps(project_id)}
      );
      const runtimeChoice = mod.preferAuthoritativeGenerationAiResearchWorkingDraft(
        {{ revision: 7, draft: {{ selectionId: 'stale' }} }},
        cached,
      );
      console.log(JSON.stringify({{ newest, staleResult, cached, runtimeChoice }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    for key in ("newest", "staleResult", "cached", "runtimeChoice"):
        assert value[key]["revision"] == 8
        assert value[key]["draft"] is None
    assert "authoritativeWorkingDraft(context" in GENERATION
    assert "preferAuthoritativeGenerationAiResearchWorkingDraft" in GENERATION
    mount_start = GENERATION.index("function mount()")
    mount_end = GENERATION.index("function scheduleMount()", mount_start)
    mount = GENERATION[mount_start:mount_end]
    assert "applySharedWorkingDraft(form, knownShared)" not in mount
    assert "const shouldHydrate = shouldHydrateGenerationResearchWorkingDraft" in mount
    assert "if (!shouldHydrate) {" in mount
    assert "generationResearchRecommendationMountResolveAction" in mount
    assert 'if (resolveAction === "replay") runtime.loadPending = true' in mount
    assert 'else if (resolveAction === "force") scheduleLoad({ force: true })' in mount
    assert 'setWorkingDraftAuthority(context.projectId, "unknown")' in mount
    assert "void hydrateSharedWorkingDraft(form, context)" in mount


def test_mutation_observer_mount_does_not_restart_settled_working_draft_hydration() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const projectId = '22222222-2222-4222-8222-222222222222';
      const matrix = {{
        firstForm: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: true,
          authorityProjectId: '',
          contextProjectId: projectId,
        }}),
        observerMutation: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: false,
          authorityProjectId: projectId,
          contextProjectId: projectId,
          authority: 'unknown',
          hydrating: true,
        }}),
        settledVerified: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: false,
          authorityProjectId: projectId,
          contextProjectId: projectId,
          authority: 'verified',
          hydrating: false,
        }}),
        settledFailed: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: false,
          authorityProjectId: projectId,
          contextProjectId: projectId,
          authority: 'failed',
          hydrating: false,
        }}),
        failedRetryDue: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: false,
          authorityProjectId: projectId,
          contextProjectId: projectId,
          authority: 'failed',
          hydrating: false,
          hydrateRetryDue: true,
        }}),
        failedRetryDueWhileHydrating: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: false,
          authorityProjectId: projectId,
          contextProjectId: projectId,
          authority: 'failed',
          hydrating: true,
          hydrateRetryDue: true,
        }}),
        orphanedUnknown: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: false,
          authorityProjectId: projectId,
          contextProjectId: projectId,
          authority: 'unknown',
          hydrating: false,
        }}),
        replacementForm: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: true,
          authorityProjectId: projectId,
          contextProjectId: projectId,
        }}),
        projectSwitch: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: false,
          authorityProjectId: projectId,
          contextProjectId: '33333333-3333-4333-8333-333333333333',
        }}),
        unscoped: mod.shouldHydrateGenerationResearchWorkingDraft({{
          formChanged: true,
          authorityProjectId: '',
          contextProjectId: '',
        }}),
      }};
      console.log(JSON.stringify(matrix));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    assert json.loads(result.stdout) == {
        "firstForm": True,
        "observerMutation": False,
        "settledVerified": False,
        # The observer anti-loop invariant: a settled failure without an
        # explicitly granted retry never restarts hydration on its own.
        "settledFailed": False,
        "failedRetryDue": True,
        "failedRetryDueWhileHydrating": False,
        "orphanedUnknown": True,
        "replacementForm": True,
        "projectSwitch": True,
        "unscoped": False,
    }


def test_failed_working_draft_hydration_schedules_bounded_retry_and_manual_button() -> None:
    assert (
        "const WORKING_DRAFT_HYDRATE_RETRY_DELAYS_MS = "
        "Object.freeze([2_000, 5_000, 15_000]);"
        in GENERATION
    )

    retry_start = GENERATION.index("function scheduleWorkingDraftHydrateRetry(")
    retry_end = GENERATION.index("function selectedVerifiedMediaProduct", retry_start)
    retry = GENERATION[retry_start:retry_end]
    # Bounded: after the third automatic attempt only the explicit button remains.
    assert "if (attempt >= WORKING_DRAFT_HYDRATE_RETRY_DELAYS_MS.length)" in retry
    assert 'renderWorkingDraftRecovery("hydrate_failed")' in retry
    assert "runtime.workingDraftHydrateRetryCount = attempt + 1" in retry
    assert "WORKING_DRAFT_HYDRATE_RETRY_DELAYS_MS[attempt]" in retry
    # The timer only arms the one-shot due flag and re-mounts; it never calls
    # hydrateSharedWorkingDraft directly, keeping mount() the single driver.
    assert "runtime.workingDraftHydrateRetryDue = true" in retry
    assert "scheduleMount()" in retry
    assert "hydrateSharedWorkingDraft(" not in retry
    assert 'runtime.workingDraftAuthority !== "failed"' in retry

    hydrate_start = GENERATION.index("async function hydrateSharedWorkingDraft")
    hydrate_end = GENERATION.index("function briefControl", hydrate_start)
    hydrate = GENERATION[hydrate_start:hydrate_end]
    failed = 'setWorkingDraftAuthority(context.projectId, "failed")'
    assert hydrate.index(failed) < hydrate.index(
        "scheduleWorkingDraftHydrateRetry(form, context)"
    )
    # A successful authoritative read resets the retry budget and the panel.
    verified = 'setWorkingDraftAuthority(context.projectId, "verified")'
    assert hydrate.index(verified) < hydrate.index(
        "runtime.workingDraftHydrateRetryCount = 0"
    )
    assert "renderWorkingDraftRecovery(null)" in hydrate

    click_start = GENERATION.index("function handleRootClick(event)")
    click_end = GENERATION.index("function presetFieldForControl", click_start)
    click = GENERATION[click_start:click_end]
    retry_branch = click[
        click.index("data-research-recommendation-working-draft-retry") :
        click.index("data-research-recommendation-conflict-take-theirs")
    ]
    assert "runtime.workingDraftHydrateRetryCount = 0" in retry_branch
    assert "runtime.workingDraftHydrateRetryDue = true" in retry_branch
    assert "scheduleMount()" in retry_branch

    mount_start = GENERATION.index("function mount()")
    mount_end = GENERATION.index("function scheduleMount()", mount_start)
    mount = GENERATION[mount_start:mount_end]
    assert "hydrateRetryDue: runtime.workingDraftHydrateRetryDue" in mount
    # One-shot consumption happens before the fresh authoritative read starts.
    assert mount.index("runtime.workingDraftHydrateRetryDue = false") < mount.index(
        'setWorkingDraftAuthority(context.projectId, "unknown")'
    )

    # A project/form switch starts a clean retry budget.
    authority_start = GENERATION.index("function setWorkingDraftAuthority(")
    authority_end = GENERATION.index(
        "function workingDraftAuthorityVerified(", authority_start
    )
    authority = GENERATION[authority_start:authority_end]
    assert "runtime.workingDraftHydrateRetryCount = 0" in authority
    assert "runtime.workingDraftHydrateRetryDue = false" in authority
    assert "window.clearTimeout(runtime.workingDraftHydrateRetryTimer)" in authority


def test_working_draft_conflict_banner_persists_and_offers_explicit_resolution() -> None:
    build_start = GENERATION.index("function buildRoot()")
    build_end = GENERATION.index("function ensureRoot(", build_start)
    build = GENERATION[build_start:build_end]
    assert 'recovery.dataset.researchRecommendationRecovery = "true"' in build
    assert (
        "root.append(header, options, preview, recovery, status, actions)"
        in build
    )

    # renderRecommendationPanel only clears options/preview/actions, so the
    # persistent recovery banner survives every re-render and later edit.
    render_start = GENERATION.index("function renderRecommendationPanel()")
    render_end = GENERATION.index("function buildRoot()", render_start)
    render = GENERATION[render_start:render_end]
    assert "recovery" not in render
    assert "data-research-recommendation-recovery" not in render

    panel_start = GENERATION.index("function renderWorkingDraftRecovery(")
    panel_end = GENERATION.index("function selectedEnvelope(", panel_start)
    panel = GENERATION[panel_start:panel_end]
    assert "researchRecommendationWorkingDraftRetry" in panel
    assert "researchRecommendationConflictTakeTheirs" in panel
    assert "researchRecommendationConflictKeepMine" in panel
    assert "Взять версию коллеги" in panel
    assert "Оставить мою" in panel
    # Binding decision: over a cleared tombstone only take-theirs is offered.
    assert "if (!clearedTombstone)" in panel
    keep_mine_offer = panel[panel.index("if (!clearedTombstone)") :]
    assert "researchRecommendationConflictKeepMine" in keep_mine_offer
    tombstone_check = panel.index("authoritative?.draft === null")
    assert tombstone_check < panel.index("researchRecommendationConflictTakeTheirs")

    click_start = GENERATION.index("function handleRootClick(event)")
    click_end = GENERATION.index("function presetFieldForControl", click_start)
    click = GENERATION[click_start:click_end]
    take_theirs_branch = click[
        click.index("data-research-recommendation-conflict-take-theirs") :
        click.index("data-research-recommendation-conflict-keep-mine")
    ]
    assert 'void resolveWorkingDraftConflict("theirs")' in take_theirs_branch
    keep_mine_branch = click[
        click.index("data-research-recommendation-conflict-keep-mine") :
        click.index("data-recommendation-index")
    ]
    assert 'void resolveWorkingDraftConflict("mine")' in keep_mine_branch

    # Keep-mine adopts the fresh revision first, then saves via revision CAS.
    resolve_start = GENERATION.index("async function resolveWorkingDraftConflict(")
    resolve_end = GENERATION.index("function applySharedWorkingDraft(", resolve_start)
    resolve = GENERATION[resolve_start:resolve_end]
    adopt = resolve.index(
        "form.dataset.generationAiResearchWorkingRevision = String(fresh.revision)"
    )
    assert adopt < resolve.index("scheduleWorkingDraftSave()")
    assert resolve.index("runtime.workingDraft = fresh") < resolve.index(
        "scheduleWorkingDraftSave()"
    )

    # Edits made while the conflict is latched are labeled as not syncing.
    edit_start = GENERATION.index("function markHumanEdit(")
    edit_end = GENERATION.index("function optOutResearchRecommendation(", edit_start)
    edit = GENERATION[edit_start:edit_end]
    assert "if (runtime.workingDraftConflict)" in edit
    assert "не синхронизируется" in edit
    assert '"danger"' in edit


def test_settled_mount_re_resolves_programmatically_restored_exact_selection() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const selectionId = 'b979e33c-4ab6-4592-9c13-90eabd1ba712';
      const base = {{
        contextKey: 'project|selection|2|product|household|sku|name|youtube',
        loadedKey: 'project|selection|2|product|household|sku|name|youtube',
        selectionId,
        recommendationPosition: 2,
        verificationRequired: true,
      }};
      console.log(JSON.stringify({{
        restoredPending:
          mod.generationResearchRecommendationMountResolveAction({{
            ...base, verificationState: 'pending',
          }}),
        alreadyVerified:
          mod.generationResearchRecommendationMountResolveAction({{
            ...base, verificationState: 'verified',
          }}),
        changedContext:
          mod.generationResearchRecommendationMountResolveAction({{
            ...base,
            loadedKey: 'project|||||||',
            verificationState: 'verified',
          }}),
        invalidPendingTarget:
          mod.generationResearchRecommendationMountResolveAction({{
            ...base,
            selectionId: '',
            verificationState: 'pending',
          }}),
        failedStable:
          mod.generationResearchRecommendationMountResolveAction({{
            ...base, verificationState: 'failed',
          }}),
        sameExactInFlight:
          mod.generationResearchRecommendationMountResolveAction({{
            ...base, verificationState: 'pending', loading: true,
          }}),
        changedInFlight:
          mod.generationResearchRecommendationMountResolveAction({{
            ...base,
            loadedKey: 'project|||||||',
            verificationState: 'verified',
            loading: true,
          }}),
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    assert json.loads(result.stdout) == {
        "restoredPending": "force",
        "alreadyVerified": "none",
        "changedContext": "schedule",
        "invalidPendingTarget": "none",
        "failedStable": "none",
        "sameExactInFlight": "in_flight",
        "changedInFlight": "replay",
    }
    schedule_start = GENERATION.index("function scheduleLoad(")
    schedule_end = GENERATION.index("function handleRootClick(", schedule_start)
    schedule = GENERATION[schedule_start:schedule_end]
    assert "force === true && runtime.loadForcePending && runtime.loadTimer" in schedule
    assert (
        "runtime.loadForcePending = runtime.loadForcePending || force === true"
        in schedule
    )
    assert "runtime.loadTimer = 0" in schedule
    assert "&& !forceLoad" in schedule


def test_verified_exact_reload_rehydrates_runtime_provenance_without_field_writes() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const projectId = '4f0fcfa2-7233-4c0c-9e16-2c20e0aae379';
      const selectionId = 'b979e33c-4ab6-4592-9c13-90eabd1ba712';
      const productId = '88a117e4-83a4-4b77-a047-96d1a39b59f7';
      const controls = {{
        product_category: {{ value: 'household' }},
        platform: {{ value: 'youtube' }},
        generation_mode: {{ value: 'real_seedance' }},
        duration_seconds: {{ value: '8' }},
        format: {{ value: '9:16' }},
        brief: {{ value: 'Человеческая правка должна остаться дословно.' }},
      }};
      class Form extends EventTarget {{
        constructor() {{
          super();
          this.elements = controls;
          this.dataset = {{
          identityProductId: productId,
          researchRecommendationLineage: 'active',
          researchRecommendationProductId: productId,
          researchRecommendationVerificationRequired: 'true',
          researchRecommendationVerificationState: 'verified',
          researchRecommendationVerificationSelectionId: selectionId,
          researchRecommendationVerificationPosition: '2',
          }};
        }}
      }}
      const form = new Form();
      const envelope = {{
        project_id: projectId,
        selection_id: selectionId,
        recommendation_position: 2,
        product_id: productId,
        product_category: 'household',
        provider_prompt_fragment_version: 'ai-research-provider-fragment-v1',
        provider_prompt_fragment:
          'AIResearchSelection/v1 C=кухня|H=честный тест|CTA=сравнить|P=4л|A=без выдумок',
        provider_prompt_fragment_hash: 'a'.repeat(64),
        preset: {{
          product_category: 'household',
          platform: 'youtube',
          generation_mode: 'real_seedance',
          duration_seconds: 8,
          format: '9:16',
          brief: 'Серверный исходный текст не должен заменить правку.',
        }},
        recommendation: {{ position: 2, title: 'Точный вариант' }},
      }};
      const state = {{
        appliedFields: [
          'product_category', 'platform', 'mode', 'duration_seconds',
          'format', 'brief',
        ],
      }};
      const snapshot = () => Object.fromEntries(
        Object.entries(controls).map(([key, control]) => [key, control.value]),
      );
      const before = snapshot();
      const categoryInitiallyAbsent =
        !form.dataset.researchRecommendationProductCategory;
      const productBound = mod.applyAuthoritativeRecommendationProduct(
        form, envelope,
      );
      const populatedCategory =
        form.dataset.researchRecommendationProductCategory || null;
      const detail = mod.verifiedResearchRecommendationProvenanceDetail(
        form, envelope, state, {{ projectId, productName: 'MILIO A425D-Black' }},
      );
      let emitted = null;
      form.addEventListener(
        'contentengine:generation-research-preset-applied',
        (event) => {{ emitted = event.detail; }},
      );
      const dispatched = mod.dispatchVerifiedResearchRecommendationProvenance(
        form, envelope, state, {{ projectId, productName: 'MILIO A425D-Black' }},
      );
      const after = snapshot();
      const projectMismatch = mod.verifiedResearchRecommendationProvenanceDetail(
        form,
        {{ ...envelope, project_id: '22222222-2222-4222-8222-222222222222' }},
        state,
        {{ projectId }},
      );
      const productMismatch = mod.verifiedResearchRecommendationProvenanceDetail(
        {{ ...form, dataset: {{ ...form.dataset,
          identityProductId: '33333333-3333-4333-8333-333333333333',
        }} }},
        envelope,
        state,
        {{ projectId }},
      );
      const pending = mod.verifiedResearchRecommendationProvenanceDetail(
        {{ ...form, dataset: {{ ...form.dataset,
          researchRecommendationVerificationState: 'pending',
        }} }},
        envelope,
        state,
        {{ projectId }},
      );
      const badProvider = mod.verifiedResearchRecommendationProvenanceDetail(
        form,
        {{ ...envelope, provider_prompt_fragment_hash: 'A'.repeat(64) }},
        state,
        {{ projectId }},
      );
      console.log(JSON.stringify({{
        before, after, categoryInitiallyAbsent, productBound,
        populatedCategory, detail, emitted, dispatched, projectMismatch,
        productMismatch, pending, badProvider,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value["before"] == value["after"]
    assert value["categoryInitiallyAbsent"] is True
    assert value["productBound"] is True
    assert value["populatedCategory"] == "household"
    assert value["detail"] == {
        "verification_only": True,
        "authoritative_project_id": "4f0fcfa2-7233-4c0c-9e16-2c20e0aae379",
        "selection_id": "b979e33c-4ab6-4592-9c13-90eabd1ba712",
        "recommendation_position": 2,
        "authoritative_product_id": "88a117e4-83a4-4b77-a047-96d1a39b59f7",
        "authoritative_product_category": "household",
        "preset": {
            "product_category": "household",
            "platform": "youtube",
            "mode": "real_seedance",
            "duration_seconds": 8,
            "format": "9:16",
            "brief": "Серверный исходный текст не должен заменить правку.",
        },
        "applied_fields": [
            "product_category", "platform", "mode", "duration_seconds",
            "format", "brief",
        ],
        "provider_prompt_fragment_version": "ai-research-provider-fragment-v1",
        "provider_prompt_fragment": (
            "AIResearchSelection/v1 C=кухня|H=честный тест|CTA=сравнить|"
            "P=4л|A=без выдумок"
        ),
        "provider_prompt_fragment_hash": "a" * 64,
    }
    assert value["emitted"] == value["detail"]
    assert value["dispatched"] is True
    assert value["projectMismatch"] is None
    assert value["productMismatch"] is None
    assert value["pending"] is None
    assert value["badProvider"] is None
    load_start = GENERATION.index("async function loadRecommendations(")
    load_end = GENERATION.index("function scheduleLoad(", load_start)
    load = GENERATION[load_start:load_end]
    assert "dispatchVerifiedResearchRecommendationProvenance(" in load
    assert "verification_only" in GENERATION


def test_recommendation_panel_is_owned_by_the_runtime_dom_patcher() -> None:
    dom_patch = (
        ROOT / "web" / "app" / "workspace-dom-patch.js"
    ).read_text(encoding="utf-8")
    assert (
        'root.dataset.ceV4Owned = "generation-research-recommendations";'
        in GENERATION
    )
    assert "[data-ce-v4-owned]" in dom_patch


def test_cross_project_inflight_work_is_origin_guarded_and_replays_latest_form() -> None:
    hydrate_start = GENERATION.index("async function hydrateSharedWorkingDraft(")
    hydrate_end = GENERATION.index("function briefControl(", hydrate_start)
    hydrate = GENERATION[hydrate_start:hydrate_end]
    assert "runtime.workingDraftHydratePending = { form, context }" in hydrate
    assert "pending?.form === runtime.form" in hydrate
    assert "runtime.form !== form" in hydrate
    assert "formContext(form).projectId !== context.projectId" in hydrate

    clear_start = GENERATION.index("async function clearWorkingDraft()")
    clear_end = GENERATION.index("function applySharedWorkingDraft", clear_start)
    clear = GENERATION[clear_start:clear_end]
    assert "const originForm = runtime.form" in clear
    assert "runtime.form !== originForm" in clear
    assert "formContext(originForm).projectId !== context.projectId" in clear
    assert "if (runtime.workingDraftClearPending)" in clear
    assert "void clearWorkingDraft()" in clear

    load_start = GENERATION.index("async function loadRecommendations(")
    load_end = GENERATION.index("function scheduleLoad(", load_start)
    load = GENERATION[load_start:load_end]
    assert "runtime.form !== form" in load
    assert "!form.isConnected" in load
    assert "const requestRoot = runtime.root" in load
    assert "const replayForm = runtime.form" in load
    assert "replayForm?.isConnected" in load
    assert "loadRecommendations(replayForm, nextContext)" in load


def test_consumed_deep_link_and_tombstone_guard_prevent_opt_out_resurrection() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const target = {{
        selectionId: 'b979e33c-4ab6-4592-9c13-90eabd1ba712',
        recommendationPosition: 2,
        intent: 'd979e33c-4ab6-4592-9c13-90eabd1ba713',
      }};
      const now = 1786453200000;
      const record = JSON.stringify({{
        selectionId: target.selectionId,
        recommendationPosition: target.recommendationPosition,
        createdAt: now - 1000,
      }});
      const freshIntent = mod.validExplicitResearchRecommendationIntent(
        target, record, now,
      );
      const plainReload = mod.validExplicitResearchRecommendationIntent(
        {{selectionId: target.selectionId, recommendationPosition: 2}}, record, now,
      );
      const expiredIntent = mod.validExplicitResearchRecommendationIntent(
        target,
        JSON.stringify({{
          selectionId: target.selectionId,
          recommendationPosition: 2,
          createdAt: now - (6 * 60 * 1000),
        }}),
        now,
      );
      const projectOne = '22222222-2222-4222-8222-222222222222';
      const projectTwo = '33333333-3333-4333-8333-333333333333';
      const authorizationKeys = [
        mod.researchRecommendationReplacementAuthorizationKey(projectOne, target),
        mod.researchRecommendationReplacementAuthorizationKey(projectOne, {{
          selectionId: target.selectionId, recommendationPosition: 1,
        }}),
        mod.researchRecommendationReplacementAuthorizationKey(projectTwo, target),
      ];
      const first = mod.routeAfterResearchRecommendationConsumption(
        '#/workspace/generation?project_id=22222222-2222-4222-8222-222222222222&selection_id=b979e33c-4ab6-4592-9c13-90eabd1ba712&recommendation_position=2&recommendation_intent=d979e33c-4ab6-4592-9c13-90eabd1ba713',
        target,
      );
      const reload = mod.routeAfterResearchRecommendationConsumption(first, target);
      const targetKey = `${{target.selectionId}}:${{target.recommendationPosition}}`;
      const application = {{
        freshIntent: mod.researchRecommendationApplicationAuthorized(target, {{
          freshRouteTargetKey: targetKey,
        }}),
        explicitButton: mod.researchRecommendationApplicationAuthorized(target, {{
          explicitApplyTargetKey: targetKey,
        }}),
        plainRoute: mod.researchRecommendationApplicationAuthorized(target),
        staleOtherTarget: mod.researchRecommendationApplicationAuthorized(target, {{
          freshRouteTargetKey: `${{target.selectionId}}:1`,
        }}),
      }};
      console.log(JSON.stringify({{
        first, reload, freshIntent, plainReload, expiredIntent, authorizationKeys,
        application,
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value["first"] == (
        "#/workspace/generation?"
        "project_id=22222222-2222-4222-8222-222222222222"
    )
    assert "selection_id" not in value["reload"]
    assert "recommendation_position" not in value["reload"]
    assert "recommendation_intent" not in value["reload"]
    assert value["freshIntent"] is True
    assert value["plainReload"] is False
    assert value["expiredIntent"] is False
    assert value["application"] == {
        "freshIntent": True,
        "explicitButton": True,
        "plainRoute": False,
        "staleOtherTarget": False,
    }
    assert len(set(value["authorizationKeys"])) == 3
    load_start = GENERATION.index("async function loadRecommendations(")
    load_end = GENERATION.index("function scheduleLoad(", load_start)
    load = GENERATION[load_start:load_end]
    assert "consumeExplicitResearchRecommendationIntent(routedTarget)" in load
    assert "researchRecommendationApplicationAuthorized(" in load
    assert "&& (routeRecommendationTarget() || explicitApplyRequested)" not in load
    mount_start = GENERATION.index("function mount()")
    mount_end = GENERATION.index("function scheduleMount()", mount_start)
    off_route = GENERATION[mount_start:mount_end]
    assert 'runtime.freshRouteApplyTargetKey = ""' in off_route
    assert 'runtime.freshRouteApplyProjectId = ""' in off_route
    assert 'runtime.explicitApplyTargetKey = ""' in off_route
    assert 'runtime.tombstoneReplacementKey = ""' in off_route
    assert "authoritativeDraft?.draft === null" in GENERATION
    assert "Старый deep link не применён повторно" in GENERATION
    assert "allowTombstoneReplacement" not in GENERATION
    assert "tombstoneReplacementKey" in GENERATION
    assert "tombstoneReplacementAuthorized(context, target)" in GENERATION
    assert "clearTombstoneReplacementAuthorization(context, target)" in GENERATION
    assert "explicitResearchRecommendationIntentIsFresh(routedTarget)" in GENERATION
    assert "runtime.activeIndex = -1" in GENERATION
    assert "runtime.loadPending = true" in GENERATION
    assert "runtime.response" in GENERATION
    assert "&& !freshExplicitRoute" in GENERATION
    assert "if (target && !workingDraftAuthorityVerified(context))" in GENERATION
    assert 'researchRecommendationVerificationFailure = "working_draft_unverified"' in GENERATION
    assert "runtime.response = null" in GENERATION
    assert 'if (requestRoot?.dataset) requestRoot.dataset.loading = "false"' in GENERATION
    assert "armGenerationRecommendationIntent" in TRAINING
    assert "recommendation_intent" in TRAINING


def test_long_option_two_brief_keeps_complete_safety_tail() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    cta = "Сравните размеры своей кухни и сохраните ролик перед покупкой."
    script = f"""
      const mod = await import({json.dumps(module_url)});
      const envelope = {{
        selection_id: 'b979e33c-4ab6-4592-9c13-90eabd1ba712',
        recommendation_position: 2,
        recommendation: {{
          position: 2,
          title: 'YouTube Shorts: «Стоит ли брать аэрогриль на маленькую кухню?» ' + 'концепция '.repeat(18),
          hook: 'Маленькая кухня — это не повод отказываться от аэрогриля. '.repeat(14),
          key_message: 'Показываем реальный размер, окно и горизонтальную корзину. '.repeat(13),
          target_audience: ['маленькая кухня '.repeat(12), 'семья '.repeat(10)],
          spoken_script: 'Честно проверяем, сколько места занимает прибор и как выглядит корзина. '.repeat(22),
          shot_list: Array.from({{length: 9}}, (_, i) => ({{
            seconds: `${{i}}–${{i + 1}} сек`,
            visual: 'подробный контрольный кадр маленькой кухни и прибора '.repeat(6),
            on_screen_text: 'реальный размер и безопасная формулировка',
          }})),
          visual_direction: 'Вертикальная съёмка без искажения габаритов. '.repeat(12),
          cta: {json.dumps(cta, ensure_ascii=False)},
          proof_points: ['4 литра', '1500 Вт', '10 программ', 'окно просмотра', 'гарантия 3 года'],
          avoid_claims: ['не обещать замену духовки', 'не говорить о 8 программах', 'не скрывать ограничения объёма'],
        }},
      }};
      const brief = mod.formatResearchRecommendation(envelope, {{
        productName: 'MILIO A425D-Black',
      }});
      console.log(JSON.stringify({{brief, length: brief.length}}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    brief = value["brief"]
    assert value["length"] <= 1180
    assert f"CTA:\n{cta}" in brief
    assert "ДОКАЗАТЕЛЬСТВА:\n" in brief
    assert "ДОКАЗАТЕЛЬСТВА:\n\n" not in brief
    assert "НЕ ОБЕЩАТЬ / УЧЕСТЬ:\n" in brief
    assert "не говорить о 8 программах" in brief
    assert not brief.rstrip().endswith("CTA:")


def test_opt_out_rolls_back_untouched_fields_and_retains_edited_lineage() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    module_url = (
        ROOT / "web" / "app" / "workspace-generation-research-recommendations.js"
    ).as_uri()
    script = f"""
      const mod = await import({json.dumps(module_url)});
      class Control extends EventTarget {{
        constructor(name, value, choices = []) {{
          super(); this.name = name; this.value = value; this.defaultValue = value;
          this.dataset = {{}}; this.options = choices.map((choice) => ({{value: choice}}));
        }}
      }}
      class Form extends EventTarget {{
        constructor(elements) {{ super(); this.elements = elements; this.dataset = {{}}; }}
      }}
      const elements = {{
        product_category: new Control('product_category', 'other', ['other', 'household']),
        platform: new Control('platform', 'instagram', ['instagram', 'youtube']),
        generation_mode: new Control('generation_mode', 'mock', ['mock', 'real_seedance']),
        duration_seconds: new Control('duration_seconds', '4', ['4', '8']),
        format: new Control('format', '1:1', ['1:1', '9:16']),
        brief: new Control('brief', 'Мой исходный замысел'),
      }};
      const form = new Form(elements);
      const envelope = {{
        selection_id: 'b979e33c-4ab6-4592-9c13-90eabd1ba712',
        recommendation_position: 2,
        scope_match: 'selected_product_advisory',
        preset: {{
          product_category: 'household', platform: 'youtube',
          generation_mode: 'real_seedance', duration_seconds: 8,
          format: '9:16', brief: 'ИИ option 2',
        }},
        recommendation: {{position: 2, title: 'Option 2'}},
      }};
      const applied = mod.applyResearchRecommendationPresetToForm(
        form, envelope, {{explicit: true, dispatch: false}},
      );
      elements.brief.value = 'Моя правка на основе option 2';
      const state = {{
        appliedFields: applied.appliedFields,
        touchedFields: ['brief'],
        previousValues: applied.previousValues,
        lastAppliedValues: Object.fromEntries(
          applied.appliedFields.map((field) => [field, String(applied.preset[field] ?? '')]),
        ),
      }};
      const result = mod.optOutResearchRecommendationForForm(
        form, envelope, {{state, dispatch: false}},
      );
      console.log(JSON.stringify({{
        result,
        values: Object.fromEntries(Object.entries(elements).map(([key, control]) => [key, control.value])),
        lineage: form.dataset.researchRecommendationLineage || null,
        lineageFields: form.dataset.researchRecommendationAppliedFields || '',
      }}));
    """
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(result.stdout)
    assert value["values"] == {
        "product_category": "other",
        "platform": "instagram",
        "generation_mode": "mock",
        "duration_seconds": "4",
        "format": "1:1",
        "brief": "Моя правка на основе option 2",
    }
    assert value["result"]["rolled_back_fields"] == [
        "product_category", "platform", "mode", "duration_seconds", "format"
    ]
    assert value["result"]["retained_fields"] == ["brief"]
    assert value["result"]["lineage_retained"] is True
    assert value["lineage"] == "active"
    assert value["lineageFields"] == "brief"


def test_copy_separates_openai_advice_from_runway_render_requirement() -> None:
    assert "OpenAI помогает с исследованием" in GENERATION
    # С 23.08.2026 рендер идёт движком из каскада (fal / HeyGen / Runway), и
    # подпись больше не называет одного провайдера; суть та же: применение
    # совета провайдера не вызывает и ничего не списывает.
    assert "рендерит выбранный в каскаде движок" in GENERATION
    assert "провайдера не вызывает и ничего не списывает" in GENERATION


def test_api_boundary_and_scoped_cache_edges_are_wired() -> None:
    assert '"contentengine_generation_research_recommendation"' in API
    assert '"contentengine_generation_ai_research_working_draft"' in API
    assert "generationResearchRecommendation(input = {})" in API
    assert "generationAiResearchWorkingDraft(input = {})" in API
    assert '"workspace-ai-research-training.js":\n      "20260823.copy-engines.64"' in BOOTSTRAP
    assert '"workspace-generation-research-recommendations.js":\n      "20260823.copy-engines.64"' in BOOTSTRAP
    assert "generation-ai-research-working-draft.js?v=20260823.copy-engines.64" in APP
    assert "generation-ai-research-working-draft.js?v=20260823.copy-engines.64" in GENERATION


def test_pgtap_executes_read_clear_conflict_and_second_user_semantics() -> None:
    lowered = PGTAP.lower()
    for marker in (
        "first user reads the authoritative cleared revision",
        "a matching optimistic revision advances exactly once",
        "a stale participant cannot overwrite the shared project revision",
        "a second project member sees the same active revision",
        "owner saves the real approved option 2 through the public cas rpc",
        "the exact option 2 resolver keeps all approved siblings while option 2 remains authoritative",
        "an explicit option 2 to option 1 switch advances the shared draft without reranking",
        "owner reload sees the second member explicit option 1 and never reranks to first implicitly",
        "second exact project member reads the same selected variant and product",
        "second member receives the same six editable non-financial fields",
        "a url/client category is rejected instead of trusted",
        "a missing/category-only selection cannot be upgraded to exact auto-apply",
        "the shared draft proves that financial fields are absent",
    ):
        assert marker in lowered
    assert "public.contentengine_generation_ai_research_working_draft(" in lowered
    assert "public.contentengine_generation_research_recommendation(" in lowered
