from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
EDGE = (ROOT / "supabase/functions/creator-generate/index.ts").read_text(encoding="utf-8")


def _between(start: str, end: str) -> str:
    start_index = EDGE.index(start)
    return EDGE[start_index : EDGE.index(end, start_index)]


def test_edge_keeps_one_orchestrator_and_delegates_provider_body_shape() -> None:
    assert 'from "../_shared/generation-provider-adapters.js"' in EDGE
    assert 'from "../_shared/generation-model-catalog.js"' in EDGE
    builder = _between(
        "function buildProviderRequest(",
        "\nfunction readStatusJob(",
    )
    assert "generationModelCatalogEntry(job.provider, job.model)" in builder
    assert "validateGenerationModelSelection(entry" in builder
    assert "buildGenerationProviderRequest(entry, selected, input)" in builder
    assert "envelope?.provider !== job.provider" in builder
    assert '"google_long_running_operation"' in builder
    assert '"runway_task"' in builder
    assert "fetch(" not in builder
    assert "Deno.env" not in builder


def test_paid_boundary_builds_exactly_one_inert_envelope_after_claim_and_signed_media() -> None:
    start = EDGE.index("  const validReferenceUrls = signedReferenceUrls as string[];")
    end = EDGE.index("  const createdValue: unknown = createResponse.value;", start)
    submission = EDGE[start:end]
    assert submission.count("buildProviderRequest(") == 1
    assert "providerRequest === null" in submission
    rejected = submission[
        submission.index("if (providerRequest === null)") :
        submission.index("let serializedProviderRequest", submission.index("if (providerRequest === null)"))
    ]
    assert "await markFailed(" in rejected
    assert '"provider_request_rejected"' in rejected
    assert "startJob.provider" in rejected
    assert "`${RUNWAY_API_ORIGIN}${providerRequest.endpointPath}`" in submission
    assert "`${GOOGLE_GENERATIVE_LANGUAGE_API_ORIGIN}${providerRequest.endpointPath}`" in submission
    assert "serializedProviderRequest = JSON.stringify(providerRequest.body)" in submission
    assert "body: serializedProviderRequest" in submission
    assert "providerRequestBody" not in submission
    assert "referenceImages: validReferenceUrls.map" not in submission
    assert "promptImage: validReferenceUrls.map" not in submission

    claim = EDGE.index("const claim = await claimSystemJob(current.id);")
    sign = EDGE.index("const signedReferenceUrls = await Promise.all(", claim)
    build = EDGE.index("const providerRequest = buildProviderRequest(", sign)
    dispatch = EDGE.index("createResponse = await fetchProviderJsonWithDeadline(", build)
    assert claim < sign < build < dispatch


def test_legacy_catalog_mapping_is_exact_and_never_silently_changes_model() -> None:
    builder = _between(
        "function publicRatioFromProvider(",
        "\nfunction readStatusJob(",
    )
    for mapping in (
        ".server?.providerRatios?.[resolution]",
        "Object.entries(ratios)",
        "exactProviderRatio === providerRatio",
        'inputMode: "image"',
        'model === "seedream5_lite" ? "2K" : "720p"',
        "const referenceImageCount = photo || seedance",
        "firstFrame: !photo && !seedance",
    ):
        assert mapping in builder
    for stale_mapping in (
        'providerRatio === SEEDREAM5_LITE_RATIO ? "1:1" : null',
        '"1280:720": "16:9"',
        '"720:1280": "9:16"',
        '"960:960": "1:1"',
    ):
        assert stale_mapping not in builder
    assert not re.search(r"model\s*:\s*[\"'](?:gen4_turbo|seedance2_fast|seedream5_lite)[\"']", builder)


def test_seedream_adapter_preserves_exact_product_reference_tags() -> None:
    adapter = (
        ROOT / "supabase/functions/_shared/generation-provider-adapters.js"
    ).read_text(encoding="utf-8")
    seedream = adapter[
        adapter.index("function buildSeedream(") : adapter.index("\nfunction buildGen4(")
    ]
    assert 'const PRODUCT_REFERENCE_TAG = "ProductReference"' in adapter
    assert "index === 0 ? PRODUCT_REFERENCE_TAG" in seedream
    assert "`${PRODUCT_REFERENCE_TAG}${index + 1}`" in seedream
