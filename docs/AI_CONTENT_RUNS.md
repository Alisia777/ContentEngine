# AI Content Runs

A `ContentRun` records one automated production pass for a product and platform.

`prepare_content_run` creates:

- demand hypothesis
- creative spec
- asset/reference readiness result
- first-frame options
- creative variants
- selected variant
- prompt pack
- product identity readiness
- product geometry/scale readiness
- publishing readiness
- rules-based AI review precheck
- blockers and next actions

Prepare does not call paid video providers.

The CLI and API output include buyer need, safe promise, selected variant, prompt pack, reference readiness, geometry readiness, human review requirement, blockers, and next actions.

CLI:

```bash
python scripts/prepare_content_run.py --product-id 1 --platform "Instagram Reels" --duration 15 --variant-count 5
python scripts/run_content_prompt_only.py --content-run-id 1
python scripts/review_content_run.py --content-run-id 1
python scripts/content_factory_dashboard.py
```

API:

- `POST /api/content-factory/runs/prepare`
- `POST /api/content-factory/runs/{id}/prompt-only`
- `POST /api/content-factory/runs/{id}/real-smoke`
- `POST /api/content-factory/runs/{id}/review`
- `GET /api/content-factory/runs/{id}`
- `GET /api/content-factory/runs/{id}/recommendations`

AI review is metadata/rules-based and intentionally keeps visual identity and packaging correctness in human review.

## Geometry-Aware Review

`ContentRun` stores `geometry_readiness` in `run_json`. The readiness check requires:

- product geometry rules
- product scale rules
- geometry lock enabled in the prompt pack
- negative prompt terms that block product size and proportion drift

Missing geometry data adds `geometry_lock_missing` and produces the `add_geometry_lock` recommendation. Explicit human feedback such as `product_geometry_mismatch` moves the run to `needs_regeneration` and produces `request_geometry_regeneration`.

Publishing readiness is also tracked, but it does not become `ready` until a real output exists and review/approval gates are satisfied.
