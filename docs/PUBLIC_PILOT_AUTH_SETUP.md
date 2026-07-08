# Public Pilot Auth Setup

This document describes the safe public pilot foundation for ContentEngine / ALTEA.

## Environment

Use `.env` locally or deployment secrets in production. Do not commit `.env`.

Required placeholders are documented in `.env.example`:

```env
QVF_AUTH_REQUIRED=true
QVF_PUBLIC_PILOT_MODE=true

SUPABASE_URL=
SUPABASE_PROJECT_REF=
SUPABASE_JWT_SECRET=
SUPABASE_JWKS_URL=
SUPABASE_ISSUER=
SUPABASE_AUDIENCE=authenticated

QVF_SESSION_COOKIE_NAME=qvf_session
QVF_SESSION_COOKIE_SECURE=false
QVF_SESSION_COOKIE_SAMESITE=lax
```

Production should set `QVF_SESSION_COOKIE_SECURE=true` behind HTTPS.

## Session Cookie

The app reads the bearer token from either:

- `Authorization: Bearer <jwt>`;
- the HttpOnly session cookie named by `QVF_SESSION_COOKIE_NAME`.

The repository contains no real Supabase secrets, no real account credentials, and no provider keys.

## Local Dev Mode

For local acceptance, keep:

```env
QVF_AUTH_REQUIRED=false
QVF_PUBLIC_PILOT_MODE=true
```

When auth is not required, the app creates a local demo user from headers:

- `x-public-pilot-email`;
- `x-public-pilot-role`;
- `x-public-pilot-name`.

If headers are omitted, the local user is `owner@local.contentengine` with role `owner`.

## Seed Demo Users

```powershell
python scripts/public_pilot_seed.py --with-certifications
```

This creates:

- Organization: `ALTEA Beauty`;
- profiles and memberships for `owner`, `admin`, `producer`, `reviewer`, `operator`, `trainee`, `viewer`;
- training modules;
- optional certifications for reviewer/operator/admin/owner.

Use `--reset-demo` to rebuild the demo state.

## Role Gates

Dangerous actions are checked through `app/public_pilot/gate_matrix.py`.

Protected actions include:

- real video smoke runs;
- one-video real run;
- output review;
- video approve/reject;
- publishing approve;
- metrics import.

Owner/admin may perform dangerous actions, but paid generation still requires an explicit spend gate. Producer can prepare content and prompt-only work but cannot approve output. Reviewer requires QA certification for review/approval. Operator requires publishing certification for publishing/metrics operations. Trainee and viewer are blocked from dangerous actions.

## Training Gates

When `QVF_PUBLIC_PILOT_STRICT_TRAINING_GATES=true`, non-owner/admin roles must hold the required certification before approval/publishing/metrics actions.

Seeded certifications:

- `review_qa`;
- `publishing_manual_upload`.

## Audit Logs

Every denied protected action writes `AuditLog` with:

- user/profile id when available;
- action;
- `status=denied`;
- reason;
- sanitized payload.

Every allowed dangerous action writes `AuditLog` with:

- action;
- `status=allowed`;
- role;
- certifications;
- spend gate status;
- sanitized payload.

Payload sanitizer masks keys containing `secret`, `token`, `key`, `password`, `authorization`, `cookie`, or `signed_url`.

## Acceptance

```powershell
python -m pytest -q
python scripts/public_pilot_seed.py --with-certifications
python scripts/public_pilot_acceptance.py
```

Open:

- `/login`;
- `/control-room`;
- `/settings/access`;
- `/altea-motion/splash`;
- `/altea-motion/login`;
- `/altea-motion/auth-loading`;
- `/altea-motion/dashboard-loading`;
- `/altea-motion/dashboard`.

Paid providers must not be called during this acceptance.

