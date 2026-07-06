# Launch Readiness

Launch readiness answers one operator question:

```text
Can this campaign launch now? If not, what exactly blocks it?
```

`LaunchReadinessService` aggregates:

- Campaign and CampaignProduct counts.
- CampaignExecutionSnapshot prompt/review/package counts.
- ContentRun and VideoJob readiness.
- LaunchQualityGate results.
- DestinationCapacitySnapshot.
- PublishingPackage and PublishingTask readiness.
- CampaignDistributionPlan blockers.
- Bombar Production Dry Run report metadata when available.

The service persists `LaunchReadinessSnapshot` records so the UI and API can show the latest launch state without duplicating campaign core logic.

## Status

`ready` means no launch blockers were found.

`blocked` means at least one quality, destination, distribution, review, or publishing blocker exists.

## API

```bash
GET /api/launch-operations/campaigns/{campaign_id}/readiness
POST /api/launch-operations/campaigns/{campaign_id}/refresh
GET /api/launch-operations/campaigns/{campaign_id}/report
```
