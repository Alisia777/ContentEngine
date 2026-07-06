# Destination Readiness CRM

v1.4 manages owned publishing destinations after they are created by the Destination Setup Factory.

## Workflow

```text
Destination setup task
-> internal destination
-> readiness status
-> warmup/posting mode
-> capacity
-> publishing eligibility
-> performance snapshot
-> next actions
```

## Readiness Rules

- destination must be active;
- posting mode must be `manual`, `api`, or `telegram_bot`;
- manual destinations require a final handle or URL;
- API destinations require `token_valid` or `api_ready`;
- paused and disabled destinations are blocked;
- effective daily and weekly capacity must be above zero;
- warmup phase can reduce effective capacity;
- publishing still requires approved packages and operator-safe scheduling.

The CRM does not register accounts on external platforms, bypass platform rules, use proxy or anti-detect tooling, or auto-publish unreviewed content.

## CLI

```bash
python scripts/destination_crm_readiness.py --destination-id 1
python scripts/destination_crm_refresh.py --destination-id 1
python scripts/destination_crm_campaign_capacity.py --campaign-id 1
python scripts/destination_crm_health.py --campaign-id 1
```

## API

- `GET /api/destination-crm/destinations`
- `GET /api/destination-crm/destinations/{id}/readiness`
- `POST /api/destination-crm/destinations/{id}/refresh-readiness`
- `POST /api/destination-crm/destinations/{id}/warmup-plan`
- `PATCH /api/destination-crm/destinations/{id}/warmup-plan`
- `GET /api/destination-crm/campaigns/{campaign_id}/capacity`
- `GET /api/destination-crm/campaigns/{campaign_id}/health`
- `GET /api/destination-crm/actions`
