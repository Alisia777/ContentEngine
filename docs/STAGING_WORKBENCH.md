# ContentEngine staging workbench

The staging workbench is a local, static preview of the real ContentEngine
browser application. It points only to an already-provisioned, separate
Supabase staging project. It does not create a project, link a repository,
apply migrations, deploy Edge Functions, start an application worker, or call a
generation provider.

## Safety boundary

The generated browser configuration always contains:

- REAL_GENERATION_ENABLED=false;
- ALLOW_REAL_SPEND=false;
- CREATOR_GENERATE_MOCK_ONLY=true;
- CHARACTER_PERFORMANCE_ENABLED=false.

Those values are code-owned and cannot be overridden through the staging env
file. The env contract accepts exactly three browser-public values: the staging
Supabase HTTPS origin, its 20-character project ref, and an sb_publishable_*
key. The workbench rejects loopback origins, the production project ref, URL/ref
mismatches, legacy JWT/anon keys, placeholders, service-role keys, secret keys,
database URLs, and any extra credential field.

MOCK_ENABLED=true is intentional: it permits free staging mock flows while
CREATOR_GENERATE_MOCK_ONLY=true and REAL_GENERATION_ENABLED=false prevent those
flows from becoming paid provider dispatches. ALLOW_REAL_SPEND=false remains an
independent second fail-closed gate.

Supabase link, database push, Edge Function deployment, provider POSTs, and
remote provisioning are intentionally outside this scaffold.

## Configure

Create the ignored runtime file from the committed example:

~~~powershell
Copy-Item .env.staging.example .env.staging
~~~

Replace all three placeholders with coordinates from a dedicated non-production
Supabase project. Do not put a production ref or any server credential in this
file. Add http://127.0.0.1:8768/ to that staging project's permitted Auth
redirect URLs through the controlled staging administration process; the
workbench does not change remote Auth settings itself.

The actual .env.staging is ignored by Git. Only .env.staging.example is
committed.

## Commands

~~~powershell
make staging-build
make staging-up
make staging-status
make staging-test
make staging-down
~~~

staging-build copies web/app to the ignored .local/staging/site directory,
excludes the production web/app/config.js, and generates only
.local/staging/site/config.js from the validated public coordinates. It never
edits the production browser config.

staging-up rebuilds the artifact and starts one Nginx container. Compose binds
Nginx only to http://127.0.0.1:8768, mounts the generated site read-only, and
does not define application, worker, provider, or Supabase services.

staging-test runs the focused contract tests, validates the standalone Compose
file, and parses a generated staging config with Node when one exists. Without
.env.staging, the committed browser config example is parsed instead; no remote
system is contacted.

## What this scaffold does not prove

A green local staging workbench proves static artifact generation, strict public
configuration, loopback-only serving, and fail-closed generation flags. It does
not prove staging migrations, RLS, Storage policy, Auth redirects, Edge Function
deployment, or paid-provider readiness. Those remain separate controlled
staging rollout and verification steps.
