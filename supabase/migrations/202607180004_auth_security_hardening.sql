begin;

-- The invite journal is reachable only through audited SECURITY DEFINER RPCs.
-- Make the database boundary explicit as well: direct access is default-deny,
-- including accidental future grants to browser roles.
alter table content_factory.invite_delivery_attempts enable row level security;
alter table content_factory.invite_delivery_attempts force row level security;

drop policy if exists invite_delivery_attempts_deny_direct
  on content_factory.invite_delivery_attempts;
create policy invite_delivery_attempts_deny_direct
  on content_factory.invite_delivery_attempts
  as restrictive
  for all
  to public
  using (false)
  with check (false);

revoke all on table content_factory.invite_delivery_attempts
  from public, anon, authenticated, service_role;

-- A credential may be supplied through a protected per-account secret, but it
-- may only be applied once.  The journal stores keyed fingerprints produced by
-- the provisioning process, never an email address or credential.
create table content_factory.member_password_dispatches (
  id uuid primary key default extensions.gen_random_uuid(),
  dispatch_id text not null unique check (
    length(dispatch_id) between 8 and 200
    and dispatch_id ~ '^[A-Za-z0-9._:-]+$'
  ),
  account_slot text not null check (
    account_slot in ('guest', 'klimov', 'pavlenko')
  ),
  email_fingerprint text not null check (
    email_fingerprint ~ '^[0-9a-f]{64}$'
  ),
  password_fingerprint text not null unique check (
    password_fingerprint ~ '^[0-9a-f]{64}$'
  ),
  status text not null default 'reserved' check (
    status in ('reserved', 'identity_applied', 'completed', 'failed')
  ),
  created_at timestamptz not null default now(),
  identity_applied_at timestamptz,
  finished_at timestamptz,
  check (
    (status = 'reserved'
      and identity_applied_at is null
      and finished_at is null)
    or (status = 'identity_applied'
      and identity_applied_at is not null
      and finished_at is null)
    or (status = 'completed'
      and identity_applied_at is not null
      and finished_at is not null)
    or (status = 'failed'
      and finished_at is not null)
  )
);

create index member_password_dispatches_slot_created_idx
  on content_factory.member_password_dispatches
  (account_slot, created_at desc);

create unique index member_password_dispatches_open_email_uq
  on content_factory.member_password_dispatches (email_fingerprint)
  where status in ('reserved', 'identity_applied');

alter table content_factory.member_password_dispatches enable row level security;
alter table content_factory.member_password_dispatches force row level security;

drop policy if exists member_password_dispatches_deny_direct
  on content_factory.member_password_dispatches;
create policy member_password_dispatches_deny_direct
  on content_factory.member_password_dispatches
  as restrictive
  for all
  to public
  using (false)
  with check (false);

revoke all on table content_factory.member_password_dispatches
  from public, anon, authenticated, service_role;

-- Fixed-window counters protect the unauthenticated recovery endpoint before
-- a provider email can be requested.  scope_hash is either a keyed client
-- fingerprint from the Edge runtime or a fixed non-secret global marker; raw
-- network addresses never enter Postgres.
create table content_factory.public_recovery_quota_buckets (
  scope text not null check (scope in ('client', 'global')),
  scope_hash text not null check (scope_hash ~ '^[0-9a-f]{64}$'),
  bucket_started_at timestamptz not null,
  request_count integer not null default 0 check (
    request_count between 0 and 1000000
  ),
  updated_at timestamptz not null default now(),
  primary key (scope, scope_hash, bucket_started_at)
);

create index public_recovery_quota_buckets_expiry_idx
  on content_factory.public_recovery_quota_buckets (bucket_started_at);

alter table content_factory.public_recovery_quota_buckets
  enable row level security;
alter table content_factory.public_recovery_quota_buckets
  force row level security;

drop policy if exists public_recovery_quota_buckets_deny_direct
  on content_factory.public_recovery_quota_buckets;
create policy public_recovery_quota_buckets_deny_direct
  on content_factory.public_recovery_quota_buckets
  as restrictive
  for all
  to public
  using (false)
  with check (false);

revoke all on table content_factory.public_recovery_quota_buckets
  from public, anon, authenticated, service_role;

-- Preserve the already-audited receipt implementation behind a private
-- boundary, then add a server-side quota wrapper.  Existing request_id replays
-- are idempotent and do not consume another quota unit.
alter function public.system_reserve_public_recovery_receipt(jsonb)
  rename to system_reserve_public_recovery_receipt_pre_abuse_quota;
alter function public.system_reserve_public_recovery_receipt_pre_abuse_quota(jsonb)
  set schema content_factory_private;

revoke all on function
  content_factory_private.system_reserve_public_recovery_receipt_pre_abuse_quota(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.system_reserve_public_recovery_receipt(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  request_id_value uuid;
  client_hash_value text;
  now_value timestamptz := now();
  bucket_started_value timestamptz;
  bucket_ends_value timestamptz;
  quota_count integer;
  global_allowed boolean := false;
  client_allowed boolean := false;
  quota_limited boolean := false;
  reserve_result jsonb;
  receipt_row content_factory.public_recovery_receipts%rowtype;
begin
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception using errcode = '22023', message = 'payload_invalid';
  end if;
  begin
    request_id_value := (p_payload ->> 'request_id')::uuid;
  exception when invalid_text_representation then
    raise exception using errcode = '22023', message = 'request_id_invalid';
  end;
  if request_id_value is null then
    raise exception using errcode = '22023', message = 'request_id_invalid';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-public-recovery-request:' || request_id_value::text,
      0
    )
  );

  client_hash_value := lower(btrim(coalesce(
    p_payload ->> 'client_key_hash',
    repeat('0', 64)
  )));
  if client_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023', message = 'client_key_hash_invalid';
  end if;

  -- Preserve legacy idempotency and per-address cooldown semantics first.
  -- Replays and suppressed duplicate dispatches return before any abuse bucket
  -- is charged, so quotas count only provider sends that would otherwise occur.
  reserve_result := content_factory_private.system_reserve_public_recovery_receipt_pre_abuse_quota(
    p_payload
  );
  if not coalesce((reserve_result ->> 'dispatch_required')::boolean, false) then
    return reserve_result;
  end if;

  bucket_started_value := pg_catalog.date_bin(
    interval '10 minutes',
    now_value,
    timestamptz '2000-01-01 00:00:00+00'
  );
  bucket_ends_value := bucket_started_value + interval '10 minutes';

  quota_count := null;
  insert into content_factory.public_recovery_quota_buckets as bucket (
    scope,
    scope_hash,
    bucket_started_at,
    request_count,
    updated_at
  ) values (
    'client',
    client_hash_value,
    bucket_started_value,
    1,
    now_value
  )
  on conflict (scope, scope_hash, bucket_started_at) do update set
    request_count = bucket.request_count + 1,
    updated_at = excluded.updated_at
  where bucket.request_count < 8
  returning request_count into quota_count;
  client_allowed := quota_count is not null;

  -- A client that has exhausted its own allowance must not consume or poison
  -- the shared global capacity.
  if client_allowed then
    quota_count := null;
    insert into content_factory.public_recovery_quota_buckets as bucket (
      scope,
      scope_hash,
      bucket_started_at,
      request_count,
      updated_at
    ) values (
      'global',
      repeat('0', 64),
      bucket_started_value,
      1,
      now_value
    )
    on conflict (scope, scope_hash, bucket_started_at) do update set
      request_count = bucket.request_count + 1,
      updated_at = excluded.updated_at
    where bucket.request_count < 120
    returning request_count into quota_count;
    global_allowed := quota_count is not null;
  end if;

  quota_limited := not global_allowed or not client_allowed;

  if quota_limited then
    select receipt.* into receipt_row
    from content_factory.public_recovery_receipts receipt
    where receipt.request_id = request_id_value
    for update;

    if receipt_row.auth_attempt_id is not null then
      begin
        perform public.system_finalize_auth_email_attempt(
          jsonb_build_object(
            'attempt_id', receipt_row.auth_attempt_id,
            'request_id', receipt_row.request_id,
            'status', 'failed',
            'reason_code', 'public_recovery_quota_limited',
            'delivery_status', 'unknown',
            'membership_provisioned', true
          )
        );
      exception when others then
        -- The public response remains non-enumerating even if the secondary
        -- manager journal cannot be finalized.
        null;
      end;
    end if;

    update content_factory.public_recovery_receipts receipt
    set
      status = 'accepted',
      reason_code = 'public_recovery_quota_limited',
      retry_not_before = greatest(receipt.retry_not_before, bucket_ends_value),
      finalized_at = coalesce(receipt.finalized_at, now_value),
      updated_at = now_value
    where receipt.id = receipt_row.id;

    reserve_result := reserve_result || jsonb_build_object(
      'dispatch_required', false,
      'status', 'accepted',
      'retry_after_seconds', greatest(
        0,
        ceil(extract(epoch from (bucket_ends_value - now_value)))::integer
      ),
      'retry_not_before', bucket_ends_value
    );
  end if;

  delete from content_factory.public_recovery_quota_buckets bucket
  where bucket.bucket_started_at < now_value - interval '48 hours';

  return reserve_result;
end;
$$;

revoke all on function public.system_reserve_public_recovery_receipt(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_reserve_public_recovery_receipt(jsonb)
  to service_role;

comment on table content_factory.invite_delivery_attempts is
  'Force-RLS server-only invite delivery journal; browser roles use audited RPC projections.';
comment on table content_factory.member_password_dispatches is
  'Server-only one-time password-dispatch fingerprint journal; contains no raw email or password.';
comment on table content_factory.public_recovery_quota_buckets is
  'Server-only fixed-window recovery abuse counters keyed by non-reversible client fingerprints.';
comment on function public.system_reserve_public_recovery_receipt(jsonb) is
  'Service-only idempotent recovery reservation with per-client and global provider-send quotas.';

commit;
