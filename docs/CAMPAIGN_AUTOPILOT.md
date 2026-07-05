# Campaign Autopilot

Campaign Autopilot is the campaign-scale layer above the existing AI Content Factory. It orchestrates ContentRun preparation, prompt-only safe actions, review blockers, approved package backlog, distribution planning, and performance feedback.

```text
Product Matrix
-> Campaign
-> Target videos per SKU
-> Content Autopilot runs per SKU
-> Prompt-ready / blocked / needs review
-> Approved publishing packages
-> Distribution plan
-> Calendar tasks
-> Performance feedback
```

## Safety Boundary

Campaign Autopilot does not create external platform accounts, does not bypass approvals, does not auto-publish unreviewed videos, and does not make paid provider calls in tests or campaign preparation.

It calls the existing `ContentRunOrchestrator` for safe content preparation and prompt-only actions.

## CLI Flow

```bash
python scripts/import_product_matrix.py --csv sample_data/product_matrix.csv
python scripts/create_campaign.py --name "Bombar Launch Wave 1" --import-id 1 --target-videos 350 --target-destinations 120
python scripts/prepare_campaign.py --campaign-id 1
python scripts/campaign_state.py --campaign-id 1
python scripts/run_campaign_prompt_only.py --campaign-id 1
python scripts/campaign_report.py --campaign-id 1
python scripts/generate_campaign_distribution_plan.py --campaign-id 1
```

The UI is available at `/campaign-autopilot`.

## Scale Defaults

- 40 SKU.
- 300-350 target videos.
- 120 publishing destinations.
- 7-9 video targets per SKU.
- Higher priority SKU receive more targets.
- Low-stock SKU receive fewer demand-generation targets.
- SKU with missing references can still receive prompt-only targets.

## Campaign State

The campaign state reports SKU coverage, prompt-ready count, real-smoke-ready count, blockers, missing references, missing geometry lock, human review needs, publishing-ready package count, and next actions by SKU.
