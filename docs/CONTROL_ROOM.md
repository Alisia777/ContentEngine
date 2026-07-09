# Unified Control Room

v3.5 turns `/control-room` into the primary role-based working interface.

EngineAudit explains what hurts. Control Room turns that scorecard into what to do next.

## Sections

- Role selector
- Engine score summary
- Executive snapshot for launch/no-launch decisions
- Scores by dimension from EngineAudit
- What is ready
- What is blocked
- Human review queue
- Safe actions
- Gated actions
- Road to 10/10
- Links to exact modules

## API

```http
GET /api/control-room/snapshot
POST /api/control-room/refresh
GET /api/control-room/roles/{role}
GET /api/control-room/actions
POST /api/control-room/actions/{id}/route
```

## CLI

```powershell
python scripts\control_room_snapshot.py
python scripts\control_room_dashboard.py --role owner
python scripts\control_room_dashboard.py --role content_lead
python scripts\control_room_dashboard.py --role reviewer
python scripts\control_room_dashboard.py --role metrics_operator
```

## Safety

The Control Room does not run providers, bypass spend gates, auto-publish, or create external accounts. Actions route to existing modules and preserve public pilot gates.

## Owner Signals

Owner dashboards must show enough to make a 30-second launch decision:

- overall production readiness;
- EngineAudit total score and dimension scores;
- campaign readiness;
- destination capacity;
- metrics coverage;
- payout exposure;
- paid smoke status;
- top blockers;
- executive next decisions.
