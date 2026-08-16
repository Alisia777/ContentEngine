# ContentEngine agent guardrails

These rules apply to every file in this repository.

- `supabase/functions/creator-generate` is the only authority allowed to start a paid generation. Do not create a second paid endpoint, worker, script, or spend authority.
- The existing database-backed generation budget and reservation records are the only spend ledger. Do not add a second spend ledger in files, SQLite, browser storage, logs, or another table.
- Never issue a real provider `POST` without separate, explicit human permission for that exact controlled smoke. Local development must keep `QVF_ALLOW_REAL_SPEND=false` and use mock providers.
- Never commit secrets, service-role keys, provider credentials, access tokens, private signing material, or generated local environment files. Browser config may contain only a local publishable key.
- Never disable, skip, weaken, delete, or rewrite tests merely to make CI green. Fix the product or the test contract instead.
- Character Performance remains feature-gated until its exact provider adapter, request shape, pricing, reconciliation, and archive contract are independently confirmed.
