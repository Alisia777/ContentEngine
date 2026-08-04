from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607290003_category_scoped_generation_learning.sql"
).read_text(encoding="utf-8")
APP = (ROOT / "web" / "app" / "app.js").read_text(encoding="utf-8")
API = (ROOT / "web" / "app" / "supabase-api.js").read_text(encoding="utf-8")
HANDOFF = (
    ROOT / "web" / "app" / "content-generation-handoff.js"
).read_text(encoding="utf-8")
EDGE = (
    ROOT / "supabase" / "functions" / "creator-generate" / "index.ts"
).read_text(encoding="utf-8")


def test_learning_rpc_and_browser_request_bind_product_category():
    assert "generationLearningPolicy({" in API
    assert "product_category: normalizedProductCategory" in API
    assert "project_id: requiredProjectId(projectIdSnake || projectId)" in API
    assert APP.count("productCategory: String(") >= 2
    assert APP.count("projectId: requireWorkspaceProjectId()") >= 2
    assert APP.count("product_category: productCategory") >= 3
    assert '"product_category",' in EDGE
    assert "product_category: startPayload.product_category" in EDGE


def test_policy_scopes_every_learning_layer_and_hash_to_category():
    for function_name in (
        "creator_generation_learning_performance_policy_v1",
        "creator_generation_learning_policy_exploration_v2",
        "creator_generation_learning_policy_independent_quality_v3",
        "creator_generation_learning_policy_quality_guards_v4",
        "creator_generation_learning_policy_audio_speech_v5",
        "creator_generation_learning_policy_rejection_v6",
    ):
        assert function_name in MIGRATION
    assert "signal.product_category = current_setting(" in MIGRATION
    assert "'product_category', category_value" in MIGRATION
    assert "'category_cold_start', category_evidence_count = 0" in MIGRATION
    assert "'cross_category_learning_forbidden', true" in MIGRATION
    assert "content_factory_private.json_hash(policy_without_hash)" in MIGRATION


def test_paid_start_snapshots_and_rejects_category_mismatch_before_delegation():
    mismatch = MIGRATION.index("message = 'generation_learning_category_mismatch'")
    delegated = MIGRATION.index(
        ".creator_start_real_generation_pre_category_learning_v14(",
        mismatch,
    )
    assert mismatch < delegated
    assert "content_factory.generation_product_category" in MIGRATION
    assert "'{product_category}'" in MIGRATION
    assert "learning_context - 'product_category'" in MIGRATION
    assert (
        "learningPolicy.product_category !== startPayload.product_category"
        in EDGE
    )


def test_unknown_historical_category_is_not_inferred_from_current_product():
    assert "review.input ->> 'product_category'" in MIGRATION
    assert "product_category_verified" in MIGRATION
    assert "product.metadata" not in MIGRATION
    assert "unknown_historical_category_excluded" in MIGRATION


def test_normalized_policy_exposes_category_cold_start_to_ux():
    assert '"category_evidence_count"' in HANDOFF
    assert '"category_cold_start"' in HANDOFF
    assert 'title = "Cold start категории"' in APP
    assert "результаты других категорий исключены" in APP


def test_old_category_rejection_cannot_block_new_category_readiness():
    safety = APP[
        APP.index("function generationPaidSafetyState(form)"):
        APP.index("function syncGenerationFormReadiness(form)")
    ]
    assert "const activePolicy = learningStateMatches" in safety
    assert (
        "const learningGenerationAllowed = !learningStateMatches"
        in safety
    )
    assert "activePolicy?.generationAllowed !== false" in safety
