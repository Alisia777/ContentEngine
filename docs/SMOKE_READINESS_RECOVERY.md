# One-Video Smoke Readiness Recovery

v3.6 adds a safe recovery layer before any paid one-video smoke run.

The goal is reproducibility: a clean local database must not fail with a confusing hard-coded `plan_id=3` error. The operator should be able to rebuild the one-video acceptance state, run prompt-only, update EngineAudit and Control Room, and see exactly what still blocks paid spend.

## Why Plan IDs Are Not Hard-Coded

`OneVideoRenderPlan` IDs are local database records. A plan that existed on one machine may not exist after a clean checkout, a fresh SQLite database, or a different demo seed. Paid smoke readiness must therefore start from product/reference state, not from a magic plan ID.

If a requested plan is missing, smoke readiness records `missing_plan` and returns `blocked_by_missing_plan`. It only rebuilds when the operator explicitly passes `--rebuild-plan`.

## Safe Recovery Flow

```powershell
# Safe status check. Provider is not called.
python scripts\smoke_readiness_recover.py --plan-id 3

# If the plan is missing but a product exists.
python scripts\smoke_readiness_recover.py --product-id 1 --rebuild-plan

# If the local DB is empty.
python scripts\smoke_readiness_recover.py --seed-demo --rebuild-plan

# Read the latest report.
python scripts\smoke_readiness_report.py --latest
```

`--seed-demo` creates only the demo Bombbar product. It does not create approved references.

`--seed-demo-refs` is intentionally separate. Use it only when you want explicit demo references for local acceptance. Real paid smoke should use real approved product references.

## Reading Blockers

Common blockers:

- `missing_plan`: requested plan ID does not exist.
- `missing_product`: product/SKU could not be found.
- `product_seed_required`: empty DB and `--seed-demo` was not passed.
- `missing_refs`: reference readiness or strict identity policy is blocked.
- `spend_gate_off`: `QVF_ALLOW_REAL_SPEND` is off.
- `generation_mode_not_real`: `QVF_GENERATION_MODE` is not `real`.
- `runway_key_missing`: `RUNWAYML_API_SECRET` is not configured.
- `runway_credits_unconfirmed`: credits were not explicitly confirmed by the operator.

The Runway key is reported only as configured yes/no. The value is never written to reports or UI.

## When Paid Smoke Is Allowed

Paid smoke is allowed only when the latest report says `ready_for_paid_smoke` and the operator has manually verified:

- one-video plan exists;
- prompt-only status is ready;
- reference policy is acceptable for the planned scenes;
- scene policy blocks unsafe bite/macro scenes when edible refs are weak;
- `QVF_GENERATION_MODE=real`;
- `QVF_ALLOW_REAL_SPEND=true`;
- `RUNWAYML_API_SECRET` is configured;
- Runway credits are confirmed;
- the run is limited to one scene;
- human review remains required after output.

## Manual Checklist Before Real Spend

1. Open `/one-video-acceptance` and review the selected plan.
2. Confirm product references are real, not placeholder URLs.
3. Run `python scripts\smoke_readiness_recover.py --product-id <id> --rebuild-plan`.
4. Run `python scripts\smoke_readiness_report.py --latest`.
5. Confirm the report has no missing plan/reference blockers.
6. Confirm Runway credits outside ContentEngine.
7. Set spend env vars only for the paid smoke terminal session.
8. Run exactly one paid smoke.
9. Send output to OutputAcceptance and human review.

Smoke readiness never calls a paid provider, never enables spend gates, never auto-approves output, and never publishes anything.
