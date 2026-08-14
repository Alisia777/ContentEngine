from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase" / "functions" / "creator-generate" / "index.ts"
CATALOG = (
    ROOT
    / "supabase"
    / "functions"
    / "_shared"
    / "generation-model-catalog.js"
)
CLIENT = ROOT / "web" / "app" / "supabase-api.js"


def test_edge_imports_the_single_canonical_catalog() -> None:
    source = EDGE.read_text(encoding="utf-8")
    assert 'from "../_shared/generation-model-catalog.js"' in source
    assert "publicGenerationModelCatalog" in source
    assert "GENERATION_MODEL_CATALOG_VERSION" in source


def test_catalog_payload_is_exact_and_cannot_accept_feature_flags() -> None:
    source = EDGE.read_text(encoding="utf-8")
    start = source.index("function readModelCatalogPayload")
    end = source.index("\nfunction ", start + 10)
    parser = source[start:end]
    assert 'new Set(["action", "organization_id"])' in parser
    assert 'value.action !== "model_catalog"' in parser
    assert "Object.keys(value).length !== keys.size" in parser
    assert "feature" not in parser.lower()


def test_catalog_action_reuses_org_authority_and_never_accepts_client_flags() -> None:
    source = EDGE.read_text(encoding="utf-8")
    start = source.index("const modelCatalogPayload = readModelCatalogPayload(body)")
    end = source.index("\n  const readCurrentStatus", start)
    handler = source[start:end]
    assert '"creator_generation_spend_overview"' in handler
    assert "loadProviderPolicy(" in handler
    assert '"creator_generation_provider_policy"' in source
    assert "modelCatalogPayload.organization_id" in handler
    assert "publicGenerationModelCatalog({" in handler
    assert '"creator_generation_model_feature_flags"' in handler
    assert "readGenerationModelFeatureFlags(data)" in handler
    assert "modelFeatureFlags.googleVeoLite" in handler
    assert "modelFeatureFlags.runwayPremium" in handler
    assert "featureFlags: catalogFeatureFlags" in handler
    assert "policy?.launchEnabled === true" in handler
    assert "Deno.env" not in handler
    assert "fetch(" not in handler


def test_public_catalog_projection_has_no_server_execution_metadata() -> None:
    source = CATALOG.read_text(encoding="utf-8")
    public_fields_start = source.index("const PUBLIC_FIELDS")
    public_fields_end = source.index("];", public_fields_start)
    public_fields = source[public_fields_start:public_fields_end]
    for forbidden in ("server", "endpoints", "featureFlag", "authorization"):
        assert f'"{forbidden}"' not in public_fields
    assert "publicGenerationModelCatalog" in source
    assert '"lastFrameDurationSeconds"' in source


def test_browser_client_uses_the_existing_generation_transport_and_validates_projection() -> None:
    source = CLIENT.read_text(encoding="utf-8")
    start = source.index("  async generationModelCatalog()")
    end = source.index("\n  realGenerationStatus(", start)
    method = source[start:end]
    assert 'this.invokeRealGeneration("model_catalog")' in method
    for field in ("catalog.version", "catalog.models", "entry.provider", "entry.model", "entry.publicLabel", "entry.enabled"):
        assert field in method
    assert "fetch(" not in method
    assert "localStorage" not in method
    assert 'new Set(["model_catalog", "preflight", "start", "status", "reconcile"])' in source
    assert 'if (action === "model_catalog") return data;' in source
