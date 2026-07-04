# Product Asset Kit

Sprint 05 adds a product-safe asset layer before creative variants and provider prompts.

The asset kit is built from `Product.images_json` and stores normalized asset descriptors plus validation warnings. V1 is metadata-only:

- no computer vision inspection
- no image generation
- no visual claims about packaging correctness
- local image dimensions are read only when available
- private URL query parameters are stripped before persistence

Asset classification is best-effort using filename and metadata heuristics:

- `packshot`
- `label_closeup`
- `lifestyle`
- `logo`
- `unknown`

The validator checks that each reference is either a URL or an existing local path, uses a supported image extension when possible, and records missing required asset types.

Real provider generation is blocked unless a usable product image and packshot are available, unless an explicit override is passed. Missing label closeups and lifestyle assets remain visible warnings because they affect first-frame and variant quality.

CLI:

```bash
python scripts/build_asset_kit.py --product-id 1
```
