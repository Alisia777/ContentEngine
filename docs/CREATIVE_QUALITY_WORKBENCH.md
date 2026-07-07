# Creative Quality Workbench

The Creative Quality Workbench is the operator surface for checking one SKU before real video smoke.

It does not create a new strategy or quality system. It links the existing `ProductStrategySpec`, `OfferStrategy`, `BloggerMeaningSpec`, `UGCAdScript`, `CreativeQualityScore`, reference policy, and `PromptPack` into one reviewable session.

## Page

Open:

```text
/creative-workbench
```

The page shows:

- product strategy scorecard;
- offer logic;
- UGC script and scene intent;
- creative quality score and required fixes;
- prompt preview;
- rewrite workflow;
- real-smoke readiness and blockers.

## CLI

```bash
python scripts/build_creative_workbench.py --product-id 1
python scripts/creative_workbench_readiness.py --session-id 1
python scripts/creative_workbench_prompt_preview.py --session-id 1
python scripts/creative_workbench_rewrite.py --session-id 1
python scripts/creative_workbench_approve.py --session-id 1 --reviewer "Operator"
```

`creative_workbench_readiness.py` exits with code `1` when real smoke is blocked. This is expected and should not be bypassed.

## Approval Rule

Approve for smoke only when all readiness gates pass:

- product strategy exists;
- offer strategy exists;
- blogger meaning exists;
- UGC script exists;
- creative quality score is passed;
- reference policy passes strict real generation;
- prompt pack exists.

Approval does not run a paid provider. It only marks the brief as operator-approved for a later limited smoke.
