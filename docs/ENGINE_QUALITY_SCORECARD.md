# Engine Quality Scorecard

v2.5 adds a measurable 1-10 audit layer for the ContentEngine foundation. The audit is intentionally read-only for production workflows: it does not call video providers, does not publish content, and does not bypass spend or review gates.

## Dimensions

The scorecard measures nine areas:

- Interface usability
- Video quality
- AI brief quality
- Creator clarity
- Training readiness
- Metrics traceability
- Destination readiness
- Campaign operations
- Production readiness

Each dimension includes:

- score from 1 to 10;
- status;
- reasons why the score is low;
- required fixes;
- next action;
- evidence counts from current database records.

## UI

Open:

```text
/engine-audit
```

The page shows the latest audit report and can run a fresh audit. Enable "Write JSON report" to persist a file under `reports/`.

## CLI

```powershell
python scripts\run_engine_audit.py --write-report
```

Expected output includes:

- audit report id;
- overall score;
- nine dimension scores;
- reasons and required fixes;
- Road to 10/10;
- report path.

## API

```http
GET /api/engine-audit/latest
POST /api/engine-audit/run
```

Example POST body:

```json
{
  "scope_type": "global",
  "scope_id": null,
  "write_report": true
}
```

## Safety

The audit only reads operational records and creates an `EngineAuditReport`. It does not:

- run paid providers;
- auto-publish;
- approve videos;
- change spend gates;
- create external accounts.
