# Participant Portal

v1.7 adds one personal workspace for content-factory participants:

```text
participant
-> destinations/channels
-> assigned briefs
-> submissions
-> publishing tasks/final URLs
-> metrics
-> payout ledger
-> recommendations
```

Roles:

- `creator`
- `publisher`
- `partner`
- `reviewer`
- `operator`
- `admin`

The portal aggregates existing campaign, destination, publishing, connector, and performance data. It does not create external accounts, bypass approvals, publish unreviewed videos, store bank data, or run paid providers in tests.

UI:

```text
/participant-portal
```

CLI:

```bash
python scripts/add_participant.py --name "Creator One" --role creator --platforms reels,shorts
python scripts/link_participant_destination.py --participant-id 1 --destination-id 1 --relationship owner
python scripts/create_participant_assignment.py --participant-id 1 --content-run-id 1 --assignment-type create_video
python scripts/participant_dashboard.py --participant-id 1
```
