# Engine Quality Scorecard

v3.4 adds a measurable 1-10 audit layer for ContentEngine readiness. The audit is intentionally read-only for production workflows: it does not call video providers, does not publish content, and does not bypass spend or review gates.

## Dimensions

The scorecard measures nine areas:

- Interface usability
- Video quality
- AI brief quality
- Asset readiness
- Creator clarity
- Training readiness
- Metrics traceability
- Destination readiness
- Production readiness

Each dimension includes:

- score from 1 to 10;
- status: `strong`, `ok`, `weak`, or `blocked`;
- reasons why the score is low;
- required fixes;
- next action;
- links to exact modules;
- evidence counts from current database records.

## Persistence

Each run creates:

- `EngineAuditRun`
- one `EngineAuditScore` per dimension

The scorecard does not change product, video, publishing, metrics, or destination records.

## UI

Open:

```text
/engine-audit
```

The page shows:

- overall score;
- scores by dimension;
- blockers;
- required fixes;
- Road to 10/10;
- links to exact modules.

## CLI

```powershell
python scripts\engine_audit_run.py
python scripts\engine_audit_run.py --write-report
python scripts\engine_audit_report.py
```

The legacy wrapper remains available:

```powershell
python scripts\run_engine_audit.py --write-report
```

## API

```http
POST /api/engine-audit/run
GET /api/engine-audit/runs/{id}
GET /api/engine-audit/latest
GET /api/engine-audit/recommendations
GET /api/engine-audit/report
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

The audit does not:

- run paid providers;
- auto-publish;
- approve videos;
- change spend gates;
- create external accounts;
- delete local media.

Use it before paid smoke or pilot planning to see what still blocks production readiness.
