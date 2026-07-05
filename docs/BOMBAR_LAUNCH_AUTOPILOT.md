# Bombar Launch Autopilot

Bombar Launch Autopilot turns a supplier product matrix into a safe launch workbench:

```text
Product matrix
-> ProductMatrixImport / ProductMatrixRow
-> Campaign
-> CampaignRunner content runs and prompt packs
-> Destination setup packs
-> CampaignDistributionPlanner
-> Publishing tasks
-> Final URLs and performance feedback
```

The workflow is campaign-scale, but Campaign Autopilot remains the single campaign core. Bombar Launch is an adapter for Bombar matrix mapping, setup packs, profile suggestions, and the launch dashboard. It does not create external platform accounts, does not use proxy or anti-detect logic, does not publish unapproved videos, and does not call paid providers during tests.

## Operator Flow

```bash
python scripts/import_bombar_matrix.py --file data/bombar_matrix.xlsx
python scripts/create_bombar_campaign.py --import-id 1 --target-videos 350 --target-destinations 120
python scripts/prepare_bombar_content.py --campaign-id 1
python scripts/generate_destination_setup_packs.py --campaign-id 1
python scripts/generate_bombar_distribution_plan.py --campaign-id 1
python scripts/bombar_launch_dashboard.py --campaign-id 1
```

Open `/bombar-launch` for the same workflow in the UI. The dashboard shows the linked Campaign ID and reuses generic campaign state/report data.

## Scale Defaults

- 40 SKU target.
- 300-350 target videos.
- 120 owned or partner destinations.
- 7-9 creative/video targets per SKU.
- 2-3 posts per destination per campaign wave.

## Safety Rules

- Missing product photos block real video generation, but demand and prompt generation can continue.
- Prompt-ready content is not publishing-ready.
- Only approved video packages can be scheduled for real publishing.
- Official API/OAuth upload is preferred where available.
- Manual-assisted upload is used when a platform has no supported API path.
- Destination setup packs are internal instructions; they are not external account registration automation.

## Dashboard Signals

The dashboard reports ready SKU, blocked SKU, missing references, review needs, publishing-ready tasks, top blockers, and next actions. A metadata score must not claim visual product identity verification; human review is still required for generated video output.
