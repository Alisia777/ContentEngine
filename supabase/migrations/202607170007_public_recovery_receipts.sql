begin;

-- A public password-recovery request needs a durable, idempotent receipt even
-- before the Auth provider answers.  The browser only ever sees a keyed opaque
-- receipt token; the normalized address and provider/journal details stay in
-- this force-RLS server-only table.
create table content_factory.public_recovery_receipts (
  id uuid primary key default extensions.gen_random_uuid(),
  request_id uuid not null unique,
  receipt_hash text not null unique
    check (receipt_hash ~ '^[0-9a-f]{64}$'),
  email text not null check (
    length(email) between 3 and 320
    and email = lower(btrim(email))
    and email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
  ),
  status text not null default 'provider_outcome_unknown' check (
    status in ('accepted', 'failed', 'provider_outcome_unknown')
  ),
  reason_code text not null default 'recovery_receipt_reserved'
    check (reason_code ~ '^[a-z0-9_]{3,80}$'),
  organization_id uuid references content_factory.organizations(id),
  auth_attempt_id uuid unique
    references content_factory.auth_email_attempts(id),
  requested_at timestamptz not null default now(),
  retry_not_before timestamptz not null,
  expires_at timestamptz not null,
  finalized_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (retry_not_before >= requested_at + interval '10 minutes'),
  check (expires_at >= requested_at + interval '1 hour')
);

create index public_recovery_receipts_email_cooldown_idx
  on content_factory.public_recovery_receipts
  (email, requested_at desc, created_at desc);

create index public_recovery_receipts_expiry_idx
  on content_factory.public_recovery_receipts (expires_at);

alter table content_factory.public_recovery_receipts enable row level security;
alter table content_factory.public_recovery_receipts force row level security;

revoke all on table content_factory.public_recovery_receipts
  from public, anon, authenticated, service_role;

-- Reserve the public receipt first and, when an eligible organization manager
-- can be selected, reserve the existing access-email journal in the same
-- transaction.  A receipt remains a complete fail-safe journal even for an
-- address that is not a portal member: the Edge Function can therefore call
-- Supabase Auth for every syntactically valid address without creating a timing
-- or response-shape account-enumeration oracle.
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
  receipt_hash_value text;
  email_value text;
  now_value timestamptz := now();
  existing_receipt content_factory.public_recovery_receipts%rowtype;
  prior_receipt content_factory.public_recovery_receipts%rowtype;
  created_receipt content_factory.public_recovery_receipts%rowtype;
  organization_id_value uuid;
  manager_id_value uuid;
  reservation jsonb;
  attempt_id_value uuid;
  retry_after_seconds integer := 600;
  dispatch_required boolean := true;
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
  receipt_hash_value := lower(btrim(coalesce(p_payload ->> 'receipt_hash', '')));
  if receipt_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023', message = 'receipt_hash_invalid';
  end if;
  email_value := lower(btrim(coalesce(p_payload ->> 'email', '')));
  if length(email_value) not between 3 and 320
     or email_value !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
    raise exception using errcode = '22023', message = 'email_invalid';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-public-recovery-request:' || request_id_value::text,
      0
    )
  );

  select receipt.* into existing_receipt
  from content_factory.public_recovery_receipts receipt
  where receipt.request_id = request_id_value;

  if existing_receipt.id is not null then
    if existing_receipt.email <> email_value
       or existing_receipt.receipt_hash <> receipt_hash_value then
      return jsonb_build_object(
        'ok', true,
        'conflict', true,
        'replayed', true,
        'dispatch_required', false,
        'receipt_id', existing_receipt.id,
        'request_id', existing_receipt.request_id,
        'status', existing_receipt.status,
        'retry_after_seconds', greatest(
          0,
          ceil(extract(epoch from (
            existing_receipt.retry_not_before - now_value
          )))::integer
        ),
        'requested_at', existing_receipt.requested_at,
        'retry_not_before', existing_receipt.retry_not_before,
        'expires_at', existing_receipt.expires_at
      );
    end if;
    return jsonb_build_object(
      'ok', true,
      'conflict', false,
      'replayed', true,
      'dispatch_required', false,
      'receipt_id', existing_receipt.id,
      'request_id', existing_receipt.request_id,
      'status', existing_receipt.status,
      'retry_after_seconds', greatest(
        0,
        ceil(extract(epoch from (
          existing_receipt.retry_not_before - now_value
        )))::integer
      ),
      'requested_at', existing_receipt.requested_at,
      'retry_not_before', existing_receipt.retry_not_before,
      'expires_at', existing_receipt.expires_at
    );
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-public-recovery-email:' || email_value,
      0
    )
  );

  select receipt.* into prior_receipt
  from content_factory.public_recovery_receipts receipt
  where receipt.email = email_value
    and receipt.requested_at > now_value - interval '10 minutes'
  order by receipt.requested_at desc, receipt.created_at desc
  limit 1;

  if prior_receipt.id is not null then
    retry_after_seconds := greatest(
      0,
      ceil(extract(epoch from (
        prior_receipt.requested_at + interval '10 minutes' - now_value
      )))::integer
    );
    insert into content_factory.public_recovery_receipts (
      request_id,
      receipt_hash,
      email,
      status,
      reason_code,
      requested_at,
      retry_not_before,
      expires_at,
      finalized_at
    ) values (
      request_id_value,
      receipt_hash_value,
      email_value,
      'accepted',
      'recovery_cooldown_active',
      now_value,
      now_value + interval '10 minutes',
      now_value + interval '24 hours',
      now_value
    )
    returning * into created_receipt;

    return jsonb_build_object(
      'ok', true,
      'conflict', false,
      'replayed', false,
      'dispatch_required', false,
      'receipt_id', created_receipt.id,
      'request_id', created_receipt.request_id,
      'status', created_receipt.status,
      'retry_after_seconds', greatest(600, retry_after_seconds),
      'requested_at', created_receipt.requested_at,
      'retry_not_before', created_receipt.retry_not_before,
      'expires_at', created_receipt.expires_at
    );
  end if;

  insert into content_factory.public_recovery_receipts (
    request_id,
    receipt_hash,
    email,
    status,
    reason_code,
    requested_at,
    retry_not_before,
    expires_at
  ) values (
    request_id_value,
    receipt_hash_value,
    email_value,
    'provider_outcome_unknown',
    'recovery_receipt_reserved',
    now_value,
    now_value + interval '10 minutes',
    now_value + interval '24 hours'
  )
  returning * into created_receipt;

  -- Prefer the target's own active organization and its least-privileged
  -- eligible manager as the audited requester.  This lookup never leaves the
  -- security-definer boundary and therefore reveals nothing about membership.
  select
    target_membership.organization_id,
    manager_membership.profile_id
  into organization_id_value, manager_id_value
  from content_factory.profiles target_profile
  join content_factory.memberships target_membership
    on target_membership.profile_id = target_profile.id
   and target_membership.status = 'active'
  join content_factory.organizations organization
    on organization.id = target_membership.organization_id
   and organization.status = 'active'
  join content_factory.memberships manager_membership
    on manager_membership.organization_id = organization.id
   and manager_membership.status = 'active'
   and manager_membership.role in ('owner', 'admin')
  join content_factory.profiles manager_profile
    on manager_profile.id = manager_membership.profile_id
   and manager_profile.status = 'active'
  join content_factory.training_certifications certification
    on certification.organization_id = organization.id
   and certification.profile_id = manager_membership.profile_id
   and certification.module_code = 'operator_final_exam'
   and certification.status = 'passed'
   and (
     certification.expires_at is null
     or certification.expires_at > now_value
   )
  where lower(btrim(target_profile.email)) = email_value
  order by
    case manager_membership.role when 'owner' then 1 else 2 end,
    manager_membership.created_at,
    organization.created_at
  limit 1;

  if organization_id_value is not null and manager_id_value is not null then
    begin
      reservation := public.system_reserve_auth_email_attempt(
        jsonb_build_object(
          'organization_id', organization_id_value,
          'requested_by', manager_id_value,
          'request_id', request_id_value,
          'requested_at', now_value,
          'email', email_value,
          'purpose', 'recovery'
        )
      );
      if coalesce((reservation ->> 'reserved')::boolean, false) then
        attempt_id_value := (reservation ->> 'attempt_id')::uuid;
        update content_factory.public_recovery_receipts receipt
        set
          organization_id = organization_id_value,
          auth_attempt_id = attempt_id_value,
          updated_at = now_value
        where receipt.id = created_receipt.id;
      else
        dispatch_required := false;
        retry_after_seconds := greatest(
          600,
          coalesce((reservation ->> 'retry_after_seconds')::integer, 600)
        );
        update content_factory.public_recovery_receipts receipt
        set
          organization_id = organization_id_value,
          status = 'accepted',
          reason_code = 'recovery_cooldown_active',
          retry_not_before = now_value
            + pg_catalog.make_interval(secs => retry_after_seconds),
          finalized_at = now_value,
          updated_at = now_value
        where receipt.id = created_receipt.id;
      end if;
    exception when others then
      -- The receipt itself is already the durable pre-provider reservation.
      -- Do not expose whether the secondary organization journal was available.
      update content_factory.public_recovery_receipts receipt
      set
        reason_code = 'recovery_receipt_reserved_without_access_attempt',
        updated_at = now_value
      where receipt.id = created_receipt.id;
    end;
  else
    update content_factory.public_recovery_receipts receipt
    set
      reason_code = 'recovery_receipt_reserved_without_access_attempt',
      updated_at = now_value
    where receipt.id = created_receipt.id;
  end if;

  return jsonb_build_object(
    'ok', true,
    'conflict', false,
    'replayed', false,
    'dispatch_required', dispatch_required,
    'receipt_id', created_receipt.id,
    'request_id', request_id_value,
    'status', case
      when dispatch_required then 'provider_outcome_unknown'
      else 'accepted'
    end,
    'retry_after_seconds', retry_after_seconds,
    'requested_at', created_receipt.requested_at,
    'retry_not_before', case
      when dispatch_required then created_receipt.retry_not_before
      else now_value + pg_catalog.make_interval(secs => retry_after_seconds)
    end,
    'expires_at', created_receipt.expires_at
  );
end;
$$;

create or replace function public.system_finalize_public_recovery_receipt(
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
  receipt_hash_value text;
  status_value text;
  reason_value text;
  receipt_row content_factory.public_recovery_receipts%rowtype;
  effective_status text;
  effective_reason text;
  now_value timestamptz := now();
begin
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception using errcode = '22023', message = 'payload_invalid';
  end if;
  begin
    request_id_value := (p_payload ->> 'request_id')::uuid;
  exception when invalid_text_representation then
    raise exception using errcode = '22023', message = 'request_id_invalid';
  end;
  receipt_hash_value := lower(btrim(coalesce(p_payload ->> 'receipt_hash', '')));
  status_value := lower(btrim(coalesce(p_payload ->> 'status', '')));
  reason_value := lower(btrim(coalesce(p_payload ->> 'reason_code', '')));
  if request_id_value is null
     or receipt_hash_value !~ '^[0-9a-f]{64}$'
     or status_value not in ('accepted', 'failed', 'provider_outcome_unknown')
     or reason_value !~ '^[a-z0-9_]{3,80}$' then
    raise exception using errcode = '22023', message = 'recovery_finalize_invalid';
  end if;

  select receipt.* into receipt_row
  from content_factory.public_recovery_receipts receipt
  where receipt.request_id = request_id_value
    and receipt.receipt_hash = receipt_hash_value
  for update;

  if receipt_row.id is null then
    return jsonb_build_object('ok', false, 'found', false);
  end if;
  if receipt_row.finalized_at is not null then
    return jsonb_build_object(
      'ok', true,
      'found', true,
      'replayed', true,
      'status', receipt_row.status,
      'retry_not_before', receipt_row.retry_not_before,
      'expires_at', receipt_row.expires_at
    );
  end if;

  effective_status := status_value;
  effective_reason := reason_value;
  if receipt_row.auth_attempt_id is not null
     and status_value in ('accepted', 'failed') then
    begin
      perform public.system_finalize_auth_email_attempt(
        jsonb_build_object(
          'attempt_id', receipt_row.auth_attempt_id,
          'request_id', receipt_row.request_id,
          'status', status_value,
          'reason_code', reason_value,
          'delivery_status', case
            when status_value = 'accepted' then 'accepted_unconfirmed'
            else 'unknown'
          end,
          'membership_provisioned', true
        )
      );
    exception when others then
      -- Provider acceptance without a finalized journal is not delivery proof.
      effective_status := 'provider_outcome_unknown';
      effective_reason := 'recovery_journal_finalize_failed';
    end;
  end if;

  update content_factory.public_recovery_receipts receipt
  set
    status = effective_status,
    reason_code = effective_reason,
    finalized_at = now_value,
    updated_at = now_value
  where receipt.id = receipt_row.id
  returning * into receipt_row;

  return jsonb_build_object(
    'ok', true,
    'found', true,
    'replayed', false,
    'status', receipt_row.status,
    'retry_not_before', receipt_row.retry_not_before,
    'expires_at', receipt_row.expires_at
  );
end;
$$;

create or replace function public.system_read_public_recovery_receipt(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  receipt_hash_value text;
  receipt_row content_factory.public_recovery_receipts%rowtype;
begin
  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception using errcode = '22023', message = 'payload_invalid';
  end if;
  receipt_hash_value := lower(btrim(coalesce(p_payload ->> 'receipt_hash', '')));
  if receipt_hash_value !~ '^[0-9a-f]{64}$' then
    raise exception using errcode = '22023', message = 'receipt_hash_invalid';
  end if;

  select receipt.* into receipt_row
  from content_factory.public_recovery_receipts receipt
  where receipt.receipt_hash = receipt_hash_value
    and receipt.expires_at > now();

  if receipt_row.id is null then
    return jsonb_build_object('ok', true, 'found', false);
  end if;

  -- Deliberately omit email, account/member existence, organization, request
  -- identity, internal reason, and provider details from this public projection.
  return jsonb_build_object(
    'ok', true,
    'found', true,
    'status', receipt_row.status,
    'requested_at', receipt_row.requested_at,
    'retry_not_before', receipt_row.retry_not_before,
    'retry_after_seconds', greatest(
      0,
      ceil(extract(epoch from (receipt_row.retry_not_before - now())))::integer
    ),
    'expires_at', receipt_row.expires_at,
    'delivery_confirmed', false
  );
end;
$$;

revoke all on function public.system_reserve_public_recovery_receipt(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_finalize_public_recovery_receipt(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_read_public_recovery_receipt(jsonb)
  from public, anon, authenticated;

grant execute on function public.system_reserve_public_recovery_receipt(jsonb)
  to service_role;
grant execute on function public.system_finalize_public_recovery_receipt(jsonb)
  to service_role;
grant execute on function public.system_read_public_recovery_receipt(jsonb)
  to service_role;

comment on table content_factory.public_recovery_receipts is
  'Server-only idempotency and public-safe receipt journal for password recovery requests.';
comment on function public.system_read_public_recovery_receipt(jsonb) is
  'Service-only public-safe projection that never returns an email or account-existence signal.';

commit;
