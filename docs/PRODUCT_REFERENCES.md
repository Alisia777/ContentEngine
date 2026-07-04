# Product References

Sprint 06 adds the practical reference-preparation layer required before real video generation.

Target flow:

```text
selected creative variant
-> approved primary product reference
-> provider reference bundle
-> prompt pack with references
-> one-scene real smoke eligibility
```

Asset sources:

- local upload through API/UI
- URL attachment through API/UI/CLI
- existing `Product.images_json` import through the asset kit builder

Local uploads are stored under:

```text
media/products/{product_id}/assets/{asset_id}_{safe_filename}
```

The upload flow sanitizes filenames, calculates a SHA-256 checksum, and stores metadata. URL attachment does not download remote files in Sprint 06. Signed/private URL query parameters are stripped before storing references in reports or provider bundles.

Readiness rules:

- real generation requires at least one approved primary reference asset
- packshot or general product image can be the primary reference
- rejected assets are never used in bundles
- unsupported file types are blocked
- missing primary reference blocks real generation
- missing label closeup or lifestyle image creates warnings, not blockers
- provider reference support is warned when not confirmed

Provider bundles are internal payloads until adapter fields are confirmed. For Runway, the bundle contains approved reference image refs, asset ids, primary asset id, and an explicit adapter TODO. The app does not guess final provider API fields as truth.

CLI:

```bash
python scripts/attach_product_asset.py --product-id 1 --url https://example.com/packshot.png --asset-type packshot --primary
python scripts/check_product_references.py --product-id 1 --provider runway
python scripts/generate_from_variant.py --creative-variant-id 1 --build-prompts-only
```
