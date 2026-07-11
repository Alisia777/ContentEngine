# Public Pilot Auth Setup

This document describes the safe public pilot foundation for ContentEngine / ALTEA.

## Environment

Use `.env` locally or deployment secrets in production. Do not commit `.env`.

Required placeholders are documented in `.env.example`:

```env
QVF_AUTH_REQUIRED=true
QVF_PUBLIC_PILOT_MODE=true
QVF_PUBLIC_PILOT_INVITE_ONLY=true

QVF_LOCAL_AUTH_EMAIL=
QVF_LOCAL_AUTH_PASSWORD_HASH=
QVF_LOCAL_SESSION_SECRET=
QVF_LOCAL_SESSION_TTL_SECONDS=28800

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

For a protected local installation, configure `QVF_LOCAL_AUTH_EMAIL`, a PBKDF2 password hash in `QVF_LOCAL_AUTH_PASSWORD_HASH`, and a random signing secret in `QVF_LOCAL_SESSION_SECRET`. The plaintext password is never stored by ContentEngine. When local auth is configured, `POST /login` creates an eight-hour signed HttpOnly session for the owner role.

## Session Cookie

The app reads the signed token from either:

- `Authorization: Bearer <jwt>`;
- the HttpOnly session cookie named by `QVF_SESSION_COOKIE_NAME`.

Every protected request validates the token signature and expiry in middleware. `/media`, dashboards, workbenches, generation reports, and API routes are closed without a valid session. Only `/login`, `/logout`, `/health`, and local static assets remain public.

This build verifies local signed sessions and Supabase `HS256` tokens when `SUPABASE_JWT_SECRET` is configured. Merely setting `SUPABASE_JWKS_URL` is not treated as verification: asymmetric tokens fail closed until a JWKS signature verifier is installed. Never place the app behind a proxy that only parses JWT claims without verifying the signature.

With `QVF_PUBLIC_PILOT_INVITE_ONLY=true` (the default), a valid external token is not enough to join the default organization. The profile and active membership must already exist. The role is read from that membership, not from a self-supplied token claim.

The repository contains no real local password hash, session signing secret, Supabase secret, account credential, or provider key.

## Unprotected Dev Mode

For local acceptance, keep:

```env
QVF_AUTH_REQUIRED=false
QVF_PUBLIC_PILOT_MODE=true
```

Use this mode only for isolated tests. When auth is not required, the app creates a local demo user from headers:

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
- optional real, correctly scored quiz attempts and certifications for reviewer/operator/admin/owner demo profiles.

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

Required certifications:

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

