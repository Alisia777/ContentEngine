# Destination Control Tower

v1.6 adds one operational screen for the destination/account network:

```text
setup
-> readiness
-> connection
-> publishing
-> metrics
-> performance
-> next action
```

The tower aggregates existing modules. It does not duplicate setup, CRM, connector, publishing, or performance services.

UI:

```text
/destination-control-tower
```

CLI:

```bash
python scripts/destination_control_snapshot.py --campaign-id 1
python scripts/destination_control_refresh.py --campaign-id 1
python scripts/destination_control_report.py --campaign-id 1
```

The action queue is safe/manual/gated. It points operators to the right module instead of performing risky account or publishing operations.

Safety boundaries:

- no external account auto-registration;
- no proxy, temporary email, or platform bypass logic;
- no unapproved auto-publish path;
- no raw secrets rendered or stored by the tower;
- no external provider calls in normal tests.
