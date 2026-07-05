# AI Content Factory Autopilot

`/content-autopilot` is the v0.5 control layer for operating many SKUs without manually opening each production screen.

The loop is:

```text
Product / SKU
-> ContentRun
-> state inspection
-> rules-based decision
-> next action
-> optional safe execution
-> decision log
-> dashboard queue
```

The autopilot inspects product data, demand, CreativeSpec, selected variant, prompt pack, references, geometry/scale readiness, VideoJob, generation report presence, quality review, publishing package/task, and performance metrics.

It does not add batch generation, Telegram, external account creation, approval bypasses, paid calls in tests, or visual verification claims.

## CLI

```bash
python scripts/content_autopilot_run.py --product-id 1
python scripts/content_autopilot_run.py --all-products
python scripts/content_autopilot_run.py --product-id 1 --execute-safe
python scripts/content_autopilot_state.py --product-id 1
python scripts/content_autopilot_execute.py --decision-id 1
python scripts/content_autopilot_queue.py
```

Safe execution supports no-paid actions such as preparing a content run, prompt-only rebuilds, draft publishing package creation, regeneration request creation, and stats import placeholders.

Paid real smoke is blocked unless explicitly allowed. Publishing actions are blocked unless explicitly allowed and approval gates are satisfied.
