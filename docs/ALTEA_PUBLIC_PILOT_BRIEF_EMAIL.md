# ALTEA Public Pilot Brief Email

Subject: ALTEA Public Pilot - access, roles, gates and acceptance scope

Hi team,

We are preparing the ALTEA public pilot foundation for ContentEngine. This release is not a paid video-generation run yet. It is the controlled access and operations layer that must be accepted before any paid smoke test.

Pilot scope:

- premium ALTEA motion shell;
- login and public pilot entrypoint;
- Control Room;
- role-based access matrix;
- training/certification gates;
- audit logs for protected actions;
- one-video / output / publishing protection kept intact.

Roles:

- owner/admin: can operate the system, but paid generation still requires spend gates;
- producer: can prepare content and prompt-only work, cannot approve output;
- reviewer: can review/approve only with QA certification;
- operator: can publishing/metrics operations only with publishing certification;
- trainee: training only;
- viewer: read-only.

What we are not doing in this step:

- no paid provider calls;
- no external account registration;
- no auto-publishing;
- no secrets committed to the repository;
- no bypass of spend, review, publishing or output safety gates.

Acceptance commands:

```powershell
python -m pytest -q
python scripts/public_pilot_seed.py --with-certifications
python scripts/public_pilot_acceptance.py
```

Acceptance routes:

- `/login`;
- `/control-room`;
- `/settings/access`;
- `/altea-motion/splash`;
- `/altea-motion/login`;
- `/altea-motion/auth-loading`;
- `/altea-motion/dashboard-loading`;
- `/altea-motion/dashboard`.

After this is accepted, the next step can be one controlled paid smoke only, with confirmed credits, valid role/certification gates, prompt-only approval, and human review after output.

