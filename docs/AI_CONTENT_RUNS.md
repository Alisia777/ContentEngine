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
- rules-based AI review precheck
- blockers and next actions

Prepare does not call paid video providers.

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
