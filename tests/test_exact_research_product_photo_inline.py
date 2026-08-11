from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EDGE = ROOT / "supabase/functions/creator-product-research/index.ts"


def _read() -> str:
    return EDGE.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    return source[start_index : source.index(end, start_index)]


def test_claim_keeps_authoritative_product_photo_hash() -> None:
    edge = _read()
    parser = _between(edge, "export function readPhoto(", "export function readExactVideo")

    assert "const sha256 = value.sha256" in parser
    assert "!SHA256_PATTERN.test(sha256)" in parser
    assert "sha256," in parser


def test_exact_branch_downloads_and_inlines_but_regular_branch_keeps_signed_urls() -> None:
    edge = _read()
    paid = _between(
        edge,
        "} else {\n    const productImageUrls",
        "const exactVideoInputFrames",
    )
    exact = _between(
        paid,
        "if (claim.run.exactVideo !== null) {",
        "} else {\n      const signedImageUrls",
    )
    regular = paid[paid.index("} else {\n      const signedImageUrls") :]

    claimed_total = exact.index("claimedExactProductPhotoBytes")
    cap = exact.index("MAX_EXACT_PRODUCT_PHOTO_TOTAL_BYTES", claimed_total)
    download = exact.index(".download(photo.objectName)", cap)
    incremental = exact.index("exactProductPhotoBytes += photo.sizeBytes", cap)
    verify = exact.index("verifyExactProductPhoto(photo, photoBlob)", download)

    assert claimed_total < cap < incremental < download < verify
    assert "createSignedUrl" not in exact
    assert "verification.dataUrl" in exact
    assert ".createSignedUrl(photo.objectName, SIGNED_IMAGE_TTL_SECONDS)" in regular
    assert ".download(photo.objectName)" not in regular
    assert "productImageUrls.push(...signedImageUrls)" in regular


def test_photo_verifier_checks_mime_size_hash_and_all_three_magic_types() -> None:
    edge = _read()
    verifier = _between(
        edge,
        "export async function verifyExactProductPhoto(",
        "function nullableStringSchema",
    )

    assert "blob.type.toLowerCase().trim() !== photo.mimeType" in verifier
    assert "blob.size !== photo.sizeBytes" in verifier
    assert "imageMagicMatchesMime(bytes, photo.mimeType)" in verifier
    assert "(await sha256Hex(bytes)) !== photo.sha256" in verifier
    assert "imageDataUrl(bytes, photo.mimeType)" in verifier
    assert 'mimeType === "image/jpeg"' in edge
    assert 'mimeType === "image/png"' in edge
    assert 'mimeType === "image/webp"' in edge


def test_serialized_request_cap_precedes_receipt_and_paid_post() -> None:
    edge = _read()
    bounded = _between(
        edge,
        "export async function beginBoundedProviderPost",
        "async function fetchWithTimeout",
    )
    paid = _between(
        edge,
        "} else {\n    const productImageUrls",
        "const outputText",
    )

    serialize = bounded.index("JSON.stringify(requestBody)")
    cap = bounded.index("MAX_PROVIDER_REQUEST_JSON_BYTES", serialize)
    begin = bounded.index("await beginAttempt(model)", cap)
    post = bounded.index("await post(serializedBody)", begin)
    body = paid.index("providerRequestBody = openAiRequestBody(")
    launch = paid.index("const providerLaunch = await beginBoundedProviderPost(", body)

    assert serialize < cap < begin < post
    assert body < launch
    assert "body: serializedBody" in paid
    assert "body: JSON.stringify" not in paid
    assert paid.count('method: "POST"') == 1
