begin;

-- Production access mail has a separate lifecycle journal.  The legacy invite
-- journal remains intact for the existing creator-invite contract, while this
-- table records one immutable attempt identity per server request and supports
-- both invitations and password recovery.
create table content_factory.auth_email_attempts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null
    references content_factory.organizations(id),
  request_id uuid not null,
  email text not null check (
    length(email) between 3 and 320
    and email = lower(btrim(email))
    and email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
  ),
  purpose text not null check (purpose in ('invite', 'recovery')),
  status text not null default 'reserved' check (
    status in ('reserved', 'accepted', 'failed', 'suppressed')
  ),
  reason_code text not null default 'email_attempt_reserved'
    check (reason_code ~ '^[a-z0-9_]{3,80}$'),
  delivery_status text not null default 'unknown' check (
    delivery_status in (
      'unknown',
      'accepted_unconfirmed',
      'deferred',
      'delivered',
      'failed',
      'bounced',
      'suppressed',
      'complained'
    )
  ),
  correlation_status text not null default 'unmatched' check (
    correlation_status in ('exact', 'ambiguous', 'unmatched')
  ),
  correlation_basis text not null default 'none' check (
    correlation_basis in (
      'none',
      'provider_message_id',
      'unique_recipient_window',
      'multiple_recipient_window'
    )
  ),
  provider text check (
    provider is null or provider ~ '^[a-z0-9][a-z0-9_-]{1,39}$'
  ),
  provider_message_id text check (
    provider_message_id is null
    or length(provider_message_id) between 1 and 255
  ),
  membership_provisioned boolean not null default false,
  requested_by uuid not null references content_factory.profiles(id),
  requested_at timestamptz not null,
  finalized_at timestamptz,
  delivery_event_at timestamptz,
  duplicate_of_attempt_id uuid
    references content_factory.auth_email_attempts(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint auth_email_attempts_request_uq
    unique (organization_id, request_id, email, purpose),
  check (
    (status = 'reserved' and finalized_at is null)
    or (status <> 'reserved' and finalized_at is not null)
  ),
  check (
    status = 'suppressed'
    or duplicate_of_attempt_id is null
  ),
  check (provider_message_id is null or provider is not null)
);

create index auth_email_attempts_latest_idx
  on content_factory.auth_email_attempts
  (organization_id, email, requested_at desc, created_at desc);

create index auth_email_attempts_correlation_idx
  on content_factory.auth_email_attempts
  (email, requested_at desc)
  where status in ('reserved', 'accepted');

create unique index auth_email_attempts_provider_message_uq
  on content_factory.auth_email_attempts (provider, provider_message_id)
  where provider is not null and provider_message_id is not null;

-- Provider callbacks are an immutable evidence ledger.  Raw webhook bodies,
-- headers and secrets are deliberately excluded.
create table content_factory.auth_email_delivery_events (
  id uuid primary key default extensions.gen_random_uuid(),
  provider text not null check (
    provider ~ '^[a-z0-9][a-z0-9_-]{1,39}$'
  ),
  provider_event_id text not null
    check (length(provider_event_id) between 1 and 255),
  provider_message_id text
    check (
      provider_message_id is null
      or length(provider_message_id) between 1 and 255
    ),
  recipient text not null check (
    length(recipient) between 3 and 320
    and recipient = lower(btrim(recipient))
    and recipient ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
  ),
  event_type text not null
    check (event_type ~ '^[a-z0-9][a-z0-9_.-]{2,79}$'),
  delivery_status text not null check (
    delivery_status in (
      'unknown',
      'accepted_unconfirmed',
      'deferred',
      'delivered',
      'failed',
      'bounced',
      'suppressed',
      'complained'
    )
  ),
  event_created_at timestamptz not null,
  received_at timestamptz not null default now(),
  attempt_id uuid references content_factory.auth_email_attempts(id),
  organization_id uuid references content_factory.organizations(id),
  correlation_status text not null check (
    correlation_status in ('exact', 'ambiguous', 'unmatched')
  ),
  correlation_basis text not null check (
    correlation_basis in (
      'none',
      'provider_message_id',
      'unique_recipient_window',
      'multiple_recipient_window'
    )
  ),
  constraint auth_email_delivery_events_provider_event_uq
    unique (provider, provider_event_id),
  check (
    (correlation_status = 'exact' and attempt_id is not null
      and organization_id is not null)
    or (correlation_status <> 'exact' and attempt_id is null
      and organization_id is null)
  )
);

create index auth_email_delivery_events_message_idx
  on content_factory.auth_email_delivery_events
  (provider, provider_message_id, event_created_at desc)
  where provider_message_id is not null;

create index auth_email_delivery_events_recipient_idx
  on content_factory.auth_email_delivery_events
  (recipient, event_created_at desc, received_at desc);

alter table content_factory.auth_email_attempts enable row level security;
alter table content_factory.auth_email_attempts force row level security;
alter table content_factory.auth_email_delivery_events enable row level security;
alter table content_factory.auth_email_delivery_events force row level security;

revoke all on table content_factory.auth_email_attempts
  from public, anon, authenticated, service_role;
revoke all on table content_factory.auth_email_delivery_events
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.auth_email_delivery_rank(
  p_status text
)
returns integer
language sql
immutable
strict
set search_path = ''
as $$
  select case p_status
    when 'unknown' then 0
    when 'accepted_unconfirmed' then 10
    when 'deferred' then 20
    when 'delivered' then 30
    when 'failed' then 35
    when 'bounced' then 40
    when 'suppressed' then 45
    when 'complained' then 50
    else -1
  end;
$$;

create or replace function content_factory_private.normalize_auth_email(
  p_email text
)
returns text
language plpgsql
immutable
strict
set search_path = ''
as $$
declare
  normalized_email text := lower(btrim(p_email));
begin
  if length(normalized_email) not between 3 and 320
     or normalized_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
    raise exception using errcode = '22023', message = 'email_invalid';
  end if;
  return normalized_email;
end;
$$;

create or replace function content_factory_private.auth_password_change_required(
  p_user_id uuid
)
returns boolean
language sql
security definer
stable
set search_path = ''
as $$
  select coalesce((
    select case
      when auth_user.raw_app_meta_data
        -> 'contentengine_password_change_required' = 'true'::jsonb then true
      when auth_user.raw_app_meta_data
        -> 'contentengine_password_change_completed' = 'true'::jsonb then false
      else
        auth_user.raw_app_meta_data
          -> 'contentengine_github_member_provisioned' = 'true'::jsonb
        or auth_user.raw_app_meta_data
          -> 'contentengine_owner_password_reset_once_20260714' = 'true'::jsonb
    end
    from auth.users auth_user
    where auth_user.id = p_user_id
  ), false);
$$;

revoke all on function
  content_factory_private.auth_email_delivery_rank(text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.normalize_auth_email(text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.auth_password_change_required(uuid)
  from public, anon, authenticated, service_role;

create or replace function content_factory_private.guard_auth_email_attempt_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.id is distinct from old.id
     or new.organization_id is distinct from old.organization_id
     or new.request_id is distinct from old.request_id
     or new.email is distinct from old.email
     or new.purpose is distinct from old.purpose
     or new.requested_by is distinct from old.requested_by
     or new.requested_at is distinct from old.requested_at
     or new.created_at is distinct from old.created_at
     or new.duplicate_of_attempt_id is distinct from old.duplicate_of_attempt_id then
    raise exception using
      errcode = '55000',
      message = 'auth_email_attempt_identity_is_immutable';
  end if;

  if old.status <> 'reserved' and new.status <> old.status then
    raise exception using
      errcode = '55000',
      message = 'auth_email_attempt_is_finalized';
  end if;
  if old.status = 'reserved'
     and new.status not in ('reserved', 'accepted', 'failed') then
    raise exception using
      errcode = '55000',
      message = 'auth_email_attempt_transition_invalid';
  end if;
  if old.finalized_at is not null
     and new.finalized_at is distinct from old.finalized_at then
    raise exception using
      errcode = '55000',
      message = 'auth_email_attempt_finalized_at_is_immutable';
  end if;
  if old.status <> 'reserved'
     and new.reason_code is distinct from old.reason_code then
    raise exception using
      errcode = '55000',
      message = 'auth_email_attempt_reason_is_immutable';
  end if;
  if old.membership_provisioned and not new.membership_provisioned then
    raise exception using
      errcode = '55000',
      message = 'auth_email_membership_projection_cannot_regress';
  end if;
  if old.provider is not null and new.provider is distinct from old.provider then
    raise exception using
      errcode = '55000',
      message = 'auth_email_provider_is_immutable';
  end if;
  if old.provider_message_id is not null
     and new.provider_message_id is distinct from old.provider_message_id then
    raise exception using
      errcode = '55000',
      message = 'auth_email_provider_message_is_immutable';
  end if;
  if content_factory_private.auth_email_delivery_rank(new.delivery_status)
       < content_factory_private.auth_email_delivery_rank(old.delivery_status) then
    raise exception using
      errcode = '55000',
      message = 'auth_email_delivery_projection_cannot_regress';
  end if;
  if old.correlation_status = 'exact'
     and new.correlation_status <> 'exact' then
    raise exception using
      errcode = '55000',
      message = 'auth_email_correlation_cannot_regress';
  end if;

  new.updated_at := now();
  return new;
end;
$$;

create or replace function content_factory_private.reject_auth_email_event_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'auth_email_delivery_events_are_append_only';
end;
$$;

create or replace function content_factory_private.reject_auth_email_attempt_delete()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'auth_email_attempts_are_append_only';
end;
$$;

revoke all on function
  content_factory_private.guard_auth_email_attempt_update()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.reject_auth_email_event_mutation()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.reject_auth_email_attempt_delete()
  from public, anon, authenticated, service_role;

create trigger auth_email_attempt_identity_guard
before update on content_factory.auth_email_attempts
for each row execute function
  content_factory_private.guard_auth_email_attempt_update();

create trigger auth_email_attempts_append_only_guard
before delete on content_factory.auth_email_attempts
for each row execute function
  content_factory_private.reject_auth_email_attempt_delete();

create trigger auth_email_delivery_events_append_only_guard
before update or delete on content_factory.auth_email_delivery_events
for each row execute function
  content_factory_private.reject_auth_email_event_mutation();

-- Existing creator-invite remains a supported producer.  Mirror every future
-- reservation/finalization into the normalized journal so bulk invitations and
-- the new one-click access flow have one delivery view.
create or replace function
  content_factory_private.mirror_legacy_invite_delivery_attempt()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  mirrored_status text;
  mirrored_delivery text;
  mirrored_finalized_at timestamptz;
  duplicate_attempt_id uuid;
begin
  mirrored_status := case
    when new.reason_code = 'duplicate_request_suppressed' then 'suppressed'
    when new.status = 'pending_verification' then 'reserved'
    when new.status in ('invited', 'already_exists') then 'accepted'
    else 'failed'
  end;
  mirrored_delivery := case
    when new.delivery_status = 'not_requested' then 'unknown'
    else new.delivery_status
  end;
  mirrored_finalized_at := case
    when mirrored_status = 'reserved' then null
    else coalesce(new.created_at, now())
  end;
  if mirrored_status = 'suppressed' then
    select attempt.id into duplicate_attempt_id
    from content_factory.auth_email_attempts attempt
    where attempt.organization_id = new.organization_id
      and attempt.email = lower(btrim(new.email))
      and attempt.purpose = 'invite'
      and attempt.request_id <> new.request_id
      and attempt.requested_at >= new.requested_at - interval '10 minutes'
      and attempt.requested_at <= new.requested_at + interval '2 minutes'
      and attempt.status in ('reserved', 'accepted')
    order by attempt.requested_at desc, attempt.created_at desc
    limit 1;
  end if;

  insert into content_factory.auth_email_attempts (
    organization_id,
    request_id,
    email,
    purpose,
    status,
    reason_code,
    delivery_status,
    membership_provisioned,
    requested_by,
    requested_at,
    finalized_at,
    duplicate_of_attempt_id,
    created_at,
    updated_at
  ) values (
    new.organization_id,
    new.request_id,
    lower(btrim(new.email)),
    'invite',
    mirrored_status,
    new.reason_code,
    mirrored_delivery,
    new.membership_provisioned,
    new.requested_by,
    new.requested_at,
    mirrored_finalized_at,
    duplicate_attempt_id,
    new.created_at,
    now()
  )
  on conflict on constraint auth_email_attempts_request_uq do nothing;

  -- Only a reserved attempt may be finalized.  A terminal mirrored attempt is
  -- never rewritten; later provider evidence may still advance delivery.
  update content_factory.auth_email_attempts attempt
  set
    status = case
      when attempt.status = 'reserved'
        and mirrored_status in ('accepted', 'failed') then mirrored_status
      else attempt.status
    end,
    reason_code = case
      when attempt.status = 'reserved'
        and mirrored_status in ('reserved', 'accepted', 'failed')
        then new.reason_code
      else attempt.reason_code
    end,
    delivery_status = case
      when content_factory_private.auth_email_delivery_rank(mirrored_delivery)
         > content_factory_private.auth_email_delivery_rank(
           attempt.delivery_status
         ) then mirrored_delivery
      else attempt.delivery_status
    end,
    membership_provisioned =
      attempt.membership_provisioned or new.membership_provisioned,
    finalized_at = case
      when attempt.status = 'reserved'
        and mirrored_status in ('accepted', 'failed')
        then coalesce(attempt.finalized_at, mirrored_finalized_at, now())
      else attempt.finalized_at
    end
  where attempt.organization_id = new.organization_id
    and attempt.request_id = new.request_id
    and attempt.email = lower(btrim(new.email))
    and attempt.purpose = 'invite';

  return new;
end;
$$;

revoke all on function
  content_factory_private.mirror_legacy_invite_delivery_attempt()
  from public, anon, authenticated, service_role;

create trigger invite_delivery_attempts_auth_email_mirror
after insert or update of
  status, reason_code, delivery_status, membership_provisioned
on content_factory.invite_delivery_attempts
for each row execute function
  content_factory_private.mirror_legacy_invite_delivery_attempt();

-- Cover pre-existing rows once; the trigger above covers all future writes.
insert into content_factory.auth_email_attempts (
  organization_id,
  request_id,
  email,
  purpose,
  status,
  reason_code,
  delivery_status,
  membership_provisioned,
  requested_by,
  requested_at,
  finalized_at,
  created_at,
  updated_at
)
select
  attempt.organization_id,
  attempt.request_id,
  lower(btrim(attempt.email)),
  'invite',
  case
    when attempt.reason_code = 'duplicate_request_suppressed' then 'suppressed'
    when attempt.status = 'pending_verification' then 'reserved'
    when attempt.status in ('invited', 'already_exists') then 'accepted'
    else 'failed'
  end,
  attempt.reason_code,
  case
    when attempt.delivery_status = 'not_requested' then 'unknown'
    else attempt.delivery_status
  end,
  attempt.membership_provisioned,
  attempt.requested_by,
  attempt.requested_at,
  case
    when attempt.status = 'pending_verification'
      and attempt.reason_code <> 'duplicate_request_suppressed' then null
    else attempt.created_at
  end,
  attempt.created_at,
  now()
from content_factory.invite_delivery_attempts attempt
on conflict on constraint auth_email_attempts_request_uq do nothing;

create or replace function public.system_reserve_auth_email_attempt(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  requested_by_value uuid;
  request_id_value uuid;
  requested_at_value timestamptz;
  email_value text;
  purpose_value text;
  existing_attempt content_factory.auth_email_attempts%rowtype;
  prior_attempt content_factory.auth_email_attempts%rowtype;
  created_attempt content_factory.auth_email_attempts%rowtype;
  retry_after_seconds integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id_value :=
    content_factory_private.require_uuid(p_payload, 'organization_id');
  requested_by_value :=
    content_factory_private.require_uuid(p_payload, 'requested_by');
  request_id_value :=
    content_factory_private.require_uuid(p_payload, 'request_id');
  email_value := content_factory_private.normalize_auth_email(
    content_factory_private.require_text(p_payload, 'email', 3, 320)
  );
  purpose_value :=
    content_factory_private.require_text(p_payload, 'purpose', 3, 20);

  if purpose_value not in ('invite', 'recovery') then
    raise exception using errcode = '22023', message = 'email_purpose_invalid';
  end if;
  begin
    requested_at_value := (p_payload ->> 'requested_at')::timestamptz;
  exception when invalid_text_representation or datetime_field_overflow then
    raise exception using errcode = '22023', message = 'email_attempt_time_invalid';
  end;
  if requested_at_value is null
     or requested_at_value < now() - interval '15 minutes'
     or requested_at_value > now() + interval '2 minutes' then
    raise exception using errcode = '22023', message = 'email_attempt_time_invalid';
  end if;

  if not exists (
    select 1
    from content_factory.memberships membership
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = organization_id_value
      and membership.profile_id = requested_by_value
      and membership.status = 'active'
      and membership.role in ('owner', 'admin')
      and exists (
        select 1
        from content_factory.training_certifications certification
        where certification.organization_id = organization_id_value
          and certification.profile_id = requested_by_value
          and certification.module_code = 'operator_final_exam'
          and certification.status = 'passed'
          and (
            certification.expires_at is null
            or certification.expires_at > now()
          )
      )
  ) then
    raise exception using errcode = '42501', message = 'requester_not_authorized';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-auth-email:'
        || organization_id_value::text || ':'
        || email_value || ':' || purpose_value,
      0
    )
  );

  select attempt.* into existing_attempt
  from content_factory.auth_email_attempts attempt
  where attempt.organization_id = organization_id_value
    and attempt.request_id = request_id_value
    and attempt.email = email_value
    and attempt.purpose = purpose_value;

  if existing_attempt.id is not null then
    return jsonb_build_object(
      'ok', true,
      'reserved', false,
      'replayed', true,
      'attempt_id', existing_attempt.id,
      'request_id', existing_attempt.request_id,
      'purpose', existing_attempt.purpose,
      'email', existing_attempt.email,
      'status', existing_attempt.status,
      'reason_code', existing_attempt.reason_code,
      'delivery_status', existing_attempt.delivery_status,
      'retry_after_seconds', 0
    );
  end if;

  select attempt.* into prior_attempt
  from content_factory.auth_email_attempts attempt
  where attempt.organization_id = organization_id_value
    and attempt.email = email_value
    and attempt.purpose = purpose_value
    and attempt.requested_at >= requested_at_value - interval '10 minutes'
    and attempt.requested_at <= requested_at_value + interval '2 minutes'
    and (
      attempt.status = 'reserved'
      or (
        attempt.status = 'accepted'
        and attempt.delivery_status in (
          'unknown', 'accepted_unconfirmed', 'deferred', 'delivered'
        )
      )
    )
  order by attempt.requested_at desc, attempt.created_at desc
  limit 1;

  if prior_attempt.id is not null then
    retry_after_seconds := greatest(
      0,
      ceil(extract(epoch from (
        prior_attempt.requested_at + interval '10 minutes' - now()
      )))::integer
    );
    insert into content_factory.auth_email_attempts (
      organization_id,
      request_id,
      email,
      purpose,
      status,
      reason_code,
      delivery_status,
      requested_by,
      requested_at,
      finalized_at,
      duplicate_of_attempt_id
    ) values (
      organization_id_value,
      request_id_value,
      email_value,
      purpose_value,
      'suppressed',
      'duplicate_request_suppressed',
      'unknown',
      requested_by_value,
      requested_at_value,
      now(),
      prior_attempt.id
    )
    returning * into created_attempt;

    return jsonb_build_object(
      'ok', true,
      'reserved', false,
      'replayed', false,
      'attempt_id', created_attempt.id,
      'request_id', created_attempt.request_id,
      'purpose', created_attempt.purpose,
      'email', created_attempt.email,
      'status', created_attempt.status,
      'reason_code', created_attempt.reason_code,
      'delivery_status', created_attempt.delivery_status,
      'retry_after_seconds', retry_after_seconds
    );
  end if;

  insert into content_factory.auth_email_attempts (
    organization_id,
    request_id,
    email,
    purpose,
    requested_by,
    requested_at
  ) values (
    organization_id_value,
    request_id_value,
    email_value,
    purpose_value,
    requested_by_value,
    requested_at_value
  )
  returning * into created_attempt;

  return jsonb_build_object(
    'ok', true,
    'reserved', true,
    'replayed', false,
    'attempt_id', created_attempt.id,
    'request_id', created_attempt.request_id,
    'purpose', created_attempt.purpose,
    'email', created_attempt.email,
    'status', created_attempt.status,
    'reason_code', created_attempt.reason_code,
    'delivery_status', created_attempt.delivery_status,
    'retry_after_seconds', 0
  );
end;
$$;

create or replace function public.system_finalize_auth_email_attempt(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  attempt_id_value uuid;
  request_id_value uuid;
  status_value text;
  reason_value text;
  delivery_value text;
  provider_value text;
  provider_message_value text;
  membership_value boolean;
  attempt_row content_factory.auth_email_attempts%rowtype;
  effective_delivery text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  attempt_id_value :=
    content_factory_private.require_uuid(p_payload, 'attempt_id');
  request_id_value :=
    content_factory_private.require_uuid(p_payload, 'request_id');
  status_value :=
    content_factory_private.require_text(p_payload, 'status', 3, 20);
  reason_value :=
    content_factory_private.require_text(p_payload, 'reason_code', 3, 80);
  delivery_value :=
    content_factory_private.require_text(p_payload, 'delivery_status', 3, 40);

  if status_value not in ('accepted', 'failed')
     or reason_value !~ '^[a-z0-9_]{3,80}$'
     or delivery_value not in (
       'unknown',
       'accepted_unconfirmed',
       'deferred',
       'delivered',
       'failed',
       'bounced',
       'suppressed',
       'complained'
     )
     or jsonb_typeof(p_payload -> 'membership_provisioned') <> 'boolean' then
    raise exception using errcode = '22023', message = 'email_finalize_invalid';
  end if;
  membership_value := (p_payload ->> 'membership_provisioned')::boolean;

  provider_value := nullif(lower(btrim(coalesce(p_payload ->> 'provider', ''))), '');
  provider_message_value :=
    nullif(btrim(coalesce(p_payload ->> 'provider_message_id', '')), '');
  if provider_value is not null
     and provider_value !~ '^[a-z0-9][a-z0-9_-]{1,39}$' then
    raise exception using errcode = '22023', message = 'email_provider_invalid';
  end if;
  if provider_message_value is not null
     and (
       provider_value is null
       or length(provider_message_value) > 255
     ) then
    raise exception using
      errcode = '22023',
      message = 'email_provider_message_invalid';
  end if;

  select attempt.* into attempt_row
  from content_factory.auth_email_attempts attempt
  where attempt.id = attempt_id_value
  for update;

  if attempt_row.id is null or attempt_row.request_id <> request_id_value then
    raise exception using errcode = 'P0002', message = 'email_attempt_not_found';
  end if;
  if attempt_row.status = 'suppressed' then
    raise exception using
      errcode = '55000',
      message = 'email_attempt_was_suppressed';
  end if;

  if attempt_row.status <> 'reserved' then
    if attempt_row.status = status_value
       and attempt_row.reason_code = reason_value
       and attempt_row.membership_provisioned = membership_value
       and (
         provider_value is null
         or attempt_row.provider = provider_value
       )
       and (
         provider_message_value is null
         or attempt_row.provider_message_id = provider_message_value
       ) then
      return jsonb_build_object(
        'ok', true,
        'replayed', true,
        'attempt_id', attempt_row.id,
        'request_id', attempt_row.request_id,
        'purpose', attempt_row.purpose,
        'email', attempt_row.email,
        'status', attempt_row.status,
        'reason_code', attempt_row.reason_code,
        'delivery_status', attempt_row.delivery_status,
        'correlation_status', attempt_row.correlation_status,
        'membership_provisioned', attempt_row.membership_provisioned,
        'finalized_at', attempt_row.finalized_at
      );
    end if;
    raise exception using
      errcode = '55000',
      message = 'email_attempt_already_finalized';
  end if;

  effective_delivery := case
    when content_factory_private.auth_email_delivery_rank(delivery_value)
       > content_factory_private.auth_email_delivery_rank(
         attempt_row.delivery_status
       ) then delivery_value
    else attempt_row.delivery_status
  end;

  update content_factory.auth_email_attempts attempt
  set
    status = status_value,
    reason_code = reason_value,
    delivery_status = effective_delivery,
    membership_provisioned =
      attempt.membership_provisioned or membership_value,
    provider = coalesce(attempt.provider, provider_value),
    provider_message_id =
      coalesce(attempt.provider_message_id, provider_message_value),
    finalized_at = now()
  where attempt.id = attempt_id_value
  returning * into attempt_row;

  return jsonb_build_object(
    'ok', true,
    'replayed', false,
    'attempt_id', attempt_row.id,
    'request_id', attempt_row.request_id,
    'purpose', attempt_row.purpose,
    'email', attempt_row.email,
    'status', attempt_row.status,
    'reason_code', attempt_row.reason_code,
    'delivery_status', attempt_row.delivery_status,
    'correlation_status', attempt_row.correlation_status,
    'membership_provisioned', attempt_row.membership_provisioned,
    'finalized_at', attempt_row.finalized_at
  );
end;
$$;

create or replace function public.system_ingest_auth_email_delivery_event(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  provider_value text;
  provider_event_value text;
  provider_message_value text;
  event_type_value text;
  delivery_value text;
  recipient_value text;
  event_created_value timestamptz;
  existing_event content_factory.auth_email_delivery_events%rowtype;
  inserted_event content_factory.auth_email_delivery_events%rowtype;
  matched_attempt content_factory.auth_email_attempts%rowtype;
  matched_attempt_id uuid;
  candidate_count integer := 0;
  correlation_value text := 'unmatched';
  basis_value text := 'none';
  projected boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  provider_value := lower(
    content_factory_private.require_text(p_payload, 'provider', 2, 40)
  );
  provider_event_value :=
    content_factory_private.require_text(p_payload, 'provider_event_id', 1, 255);
  provider_message_value :=
    nullif(btrim(coalesce(p_payload ->> 'provider_message_id', '')), '');
  event_type_value := lower(
    content_factory_private.require_text(p_payload, 'event_type', 3, 80)
  );
  delivery_value :=
    content_factory_private.require_text(p_payload, 'delivery_status', 3, 40);
  recipient_value := content_factory_private.normalize_auth_email(
    content_factory_private.require_text(p_payload, 'recipient', 3, 320)
  );

  if provider_value !~ '^[a-z0-9][a-z0-9_-]{1,39}$'
     or event_type_value !~ '^[a-z0-9][a-z0-9_.-]{2,79}$'
     or delivery_value not in (
       'unknown',
       'accepted_unconfirmed',
       'deferred',
       'delivered',
       'failed',
       'bounced',
       'suppressed',
       'complained'
     )
     or (
       provider_message_value is not null
       and length(provider_message_value) > 255
     ) then
    raise exception using errcode = '22023', message = 'email_event_invalid';
  end if;
  begin
    event_created_value := (p_payload ->> 'event_created_at')::timestamptz;
  exception when invalid_text_representation or datetime_field_overflow then
    raise exception using errcode = '22023', message = 'email_event_time_invalid';
  end;
  if event_created_value is null
     or event_created_value < now() - interval '90 days'
     or event_created_value > now() + interval '5 minutes' then
    raise exception using errcode = '22023', message = 'email_event_time_invalid';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-email-event:'
        || provider_value || ':' || provider_event_value,
      0
    )
  );

  select event.* into existing_event
  from content_factory.auth_email_delivery_events event
  where event.provider = provider_value
    and event.provider_event_id = provider_event_value;

  if existing_event.id is not null then
    if existing_event.provider_message_id
         is distinct from provider_message_value
       or existing_event.recipient <> recipient_value
       or existing_event.event_type <> event_type_value
       or existing_event.delivery_status <> delivery_value
       or existing_event.event_created_at <> event_created_value then
      raise exception using
        errcode = '55000',
        message = 'email_event_replay_conflict';
    end if;
    return jsonb_build_object(
      'ok', true,
      'inserted', false,
      'event_id', existing_event.id,
      'correlation_status', existing_event.correlation_status,
      'correlation_basis', existing_event.correlation_basis,
      'attempt_id', existing_event.attempt_id,
      'delivery_projected', false
    );
  end if;

  if provider_message_value is not null then
    select count(*), (array_agg(attempt.id))[1]
      into candidate_count, matched_attempt_id
    from content_factory.auth_email_attempts attempt
    where attempt.provider = provider_value
      and attempt.provider_message_id = provider_message_value;

    if candidate_count = 1 then
      select attempt.* into matched_attempt
      from content_factory.auth_email_attempts attempt
      where attempt.id = matched_attempt_id;
      correlation_value := 'exact';
      basis_value := 'provider_message_id';
    end if;
  end if;

  if correlation_value <> 'exact' then
    matched_attempt_id := null;
    select count(*), (array_agg(
      attempt.id order by attempt.requested_at desc, attempt.created_at desc
    ))[1]
      into candidate_count, matched_attempt_id
    from content_factory.auth_email_attempts attempt
    where attempt.email = recipient_value
      and attempt.status in ('reserved', 'accepted')
      and (
        attempt.provider is null
        or attempt.provider = provider_value
      )
      and (
        provider_message_value is null
        or attempt.provider_message_id is null
        or attempt.provider_message_id = provider_message_value
      )
      and attempt.requested_at >= event_created_value - interval '72 hours'
      and attempt.requested_at <= event_created_value + interval '5 minutes';

    if candidate_count = 1 then
      select attempt.* into matched_attempt
      from content_factory.auth_email_attempts attempt
      where attempt.id = matched_attempt_id;
      correlation_value := 'exact';
      basis_value := 'unique_recipient_window';
    elsif candidate_count > 1 then
      matched_attempt_id := null;
      correlation_value := 'ambiguous';
      basis_value := 'multiple_recipient_window';
    else
      matched_attempt_id := null;
      correlation_value := 'unmatched';
      basis_value := 'none';
    end if;
  end if;

  insert into content_factory.auth_email_delivery_events (
    provider,
    provider_event_id,
    provider_message_id,
    recipient,
    event_type,
    delivery_status,
    event_created_at,
    attempt_id,
    organization_id,
    correlation_status,
    correlation_basis
  ) values (
    provider_value,
    provider_event_value,
    provider_message_value,
    recipient_value,
    event_type_value,
    delivery_value,
    event_created_value,
    case when correlation_value = 'exact' then matched_attempt.id end,
    case when correlation_value = 'exact'
      then matched_attempt.organization_id end,
    correlation_value,
    basis_value
  )
  returning * into inserted_event;

  if correlation_value = 'exact'
     and content_factory_private.auth_email_delivery_rank(delivery_value)
       > content_factory_private.auth_email_delivery_rank(
         matched_attempt.delivery_status
       ) then
    update content_factory.auth_email_attempts attempt
    set
      delivery_status = delivery_value,
      delivery_event_at = event_created_value,
      correlation_status = 'exact',
      correlation_basis = basis_value,
      provider = coalesce(attempt.provider, provider_value),
      provider_message_id =
        coalesce(attempt.provider_message_id, provider_message_value)
    where attempt.id = matched_attempt.id;
    projected := true;
  elsif correlation_value = 'exact' then
    update content_factory.auth_email_attempts attempt
    set
      delivery_event_at = case
        when content_factory_private.auth_email_delivery_rank(delivery_value)
          = content_factory_private.auth_email_delivery_rank(
            attempt.delivery_status
          )
          and (
            attempt.delivery_event_at is null
            or event_created_value > attempt.delivery_event_at
          ) then event_created_value
        else attempt.delivery_event_at
      end,
      correlation_status = 'exact',
      correlation_basis = basis_value,
      provider = coalesce(attempt.provider, provider_value),
      provider_message_id =
        coalesce(attempt.provider_message_id, provider_message_value)
    where attempt.id = matched_attempt.id;
  end if;

  return jsonb_build_object(
    'ok', true,
    'inserted', true,
    'event_id', inserted_event.id,
    'correlation_status', inserted_event.correlation_status,
    'correlation_basis', inserted_event.correlation_basis,
    'attempt_id', inserted_event.attempt_id,
    'delivery_projected', projected
  );
end;
$$;

create or replace function public.creator_account_access_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  email_value text;
  target_profile_id uuid;
  membership_role_value text;
  membership_status_value text;
  profile_status_value text;
  auth_present boolean := false;
  auth_email_confirmed boolean := false;
  auth_last_sign_in_at timestamptz;
  auth_banned boolean := false;
  auth_deleted boolean := false;
  password_required boolean := false;
  delivery_snapshot jsonb;
  ambiguous_event record;
  account_state_value text;
  recommended_action_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin']
  );
  email_value := content_factory_private.normalize_auth_email(
    content_factory_private.require_text(p_payload, 'email', 3, 320)
  );

  select
    profile.id,
    membership.role,
    membership.status,
    profile.status
  into
    target_profile_id,
    membership_role_value,
    membership_status_value,
    profile_status_value
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
  where membership.organization_id = organization_id_value
    and lower(profile.email) = email_value
  order by
    case membership.status when 'active' then 0 else 1 end,
    membership.created_at desc
  limit 1;

  if target_profile_id is not null then
    select
      true,
      auth_user.email_confirmed_at is not null,
      auth_user.last_sign_in_at,
      coalesce(auth_user.banned_until > now(), false),
      auth_user.deleted_at is not null
    into
      auth_present,
      auth_email_confirmed,
      auth_last_sign_in_at,
      auth_banned,
      auth_deleted
    from auth.users auth_user
    where auth_user.id = target_profile_id;
    auth_present := coalesce(auth_present, false);
    auth_email_confirmed := coalesce(auth_email_confirmed, false);
    auth_banned := coalesce(auth_banned, false);
    auth_deleted := coalesce(auth_deleted, false);
    password_required :=
      content_factory_private.auth_password_change_required(target_profile_id);
  end if;

  with delivery_candidates as (
    select
      attempt.requested_at,
      attempt.created_at,
      jsonb_build_object(
        'purpose', attempt.purpose,
        'status', attempt.status,
        'reason_code', attempt.reason_code,
        'delivery_status', attempt.delivery_status,
        'correlation_status', attempt.correlation_status,
        'correlation_basis', attempt.correlation_basis,
        'membership_provisioned', attempt.membership_provisioned,
        'requested_at', attempt.requested_at,
        'finalized_at', attempt.finalized_at,
        'event_at', attempt.delivery_event_at
      ) as snapshot
    from content_factory.auth_email_attempts attempt
    where attempt.organization_id = organization_id_value
      and attempt.email = email_value
      and attempt.duplicate_of_attempt_id is null
    union all
    select
      attempt.requested_at,
      attempt.created_at,
      jsonb_build_object(
        'purpose', 'invite',
        'status', case
          when attempt.status in ('invited', 'already_exists') then 'accepted'
          when attempt.status = 'pending_verification' then 'reserved'
          else 'failed'
        end,
        'reason_code', attempt.reason_code,
        'delivery_status', case
          when attempt.delivery_status = 'not_requested' then 'unknown'
          else attempt.delivery_status
        end,
        'correlation_status', 'unmatched',
        'correlation_basis', 'none',
        'membership_provisioned', attempt.membership_provisioned,
        'requested_at', attempt.requested_at,
        'finalized_at', attempt.created_at,
        'event_at', null
      ) as snapshot
    from content_factory.invite_delivery_attempts attempt
    where attempt.organization_id = organization_id_value
      and attempt.email = email_value
      and not exists (
        select 1
        from content_factory.auth_email_attempts mirrored
        where mirrored.organization_id = attempt.organization_id
          and mirrored.request_id = attempt.request_id
          and mirrored.email = attempt.email
          and mirrored.purpose = 'invite'
      )
  )
  select candidate.snapshot into delivery_snapshot
  from delivery_candidates candidate
  order by candidate.requested_at desc, candidate.created_at desc
  limit 1;

  if delivery_snapshot is not null
     and coalesce(delivery_snapshot ->> 'correlation_status', '') <> 'exact' then
    select
      event.correlation_status,
      event.correlation_basis
    into ambiguous_event
    from content_factory.auth_email_delivery_events event
    where event.recipient = email_value
      and event.correlation_status = 'ambiguous'
      and event.event_created_at >=
        (delivery_snapshot ->> 'requested_at')::timestamptz - interval '5 minutes'
      and event.event_created_at <=
        (delivery_snapshot ->> 'requested_at')::timestamptz + interval '72 hours'
    order by event.event_created_at desc, event.received_at desc
    limit 1;
    if ambiguous_event.correlation_status = 'ambiguous' then
      delivery_snapshot := jsonb_set(
        delivery_snapshot,
        '{correlation_status}',
        '"ambiguous"'::jsonb,
        true
      );
      delivery_snapshot := jsonb_set(
        delivery_snapshot,
        '{correlation_basis}',
        to_jsonb(ambiguous_event.correlation_basis),
        true
      );
    end if;
  end if;

  if target_profile_id is not null then
    if membership_status_value <> 'active'
       or profile_status_value <> 'active'
       or not auth_present
       or auth_banned
       or auth_deleted then
      account_state_value := 'disabled';
      recommended_action_value := 'manual_review';
    elsif not password_required
       and auth_email_confirmed
       and auth_last_sign_in_at is not null then
      account_state_value := 'ready';
      recommended_action_value := 'none';
    elsif delivery_snapshot is not null
       and delivery_snapshot ->> 'status' in (
         'reserved', 'accepted', 'suppressed'
       )
       and delivery_snapshot ->> 'delivery_status' in (
         'unknown',
         'accepted_unconfirmed',
         'deferred',
         'delivered'
       )
       and (delivery_snapshot ->> 'requested_at')::timestamptz
         >= now() - interval '60 minutes' then
      account_state_value := 'pending_delivery';
      recommended_action_value := 'wait';
    elsif delivery_snapshot ->> 'delivery_status' in (
        'failed', 'bounced', 'suppressed', 'complained'
      ) then
      account_state_value := 'disabled';
      recommended_action_value := 'manual_review';
    else
      account_state_value := 'recovery_required';
      recommended_action_value := 'recovery';
    end if;
  elsif delivery_snapshot is null then
    account_state_value := 'invite_required';
    recommended_action_value := 'invite';
  elsif delivery_snapshot ->> 'status' in (
      'reserved', 'accepted', 'suppressed'
    )
    and delivery_snapshot ->> 'delivery_status' in (
      'unknown',
      'accepted_unconfirmed',
      'deferred',
      'delivered'
    )
    and (delivery_snapshot ->> 'requested_at')::timestamptz
      >= now() - interval '60 minutes' then
    account_state_value := 'pending_delivery';
    recommended_action_value := 'wait';
  elsif delivery_snapshot ->> 'delivery_status' in (
      'failed', 'bounced', 'suppressed', 'complained'
    ) then
    account_state_value := 'disabled';
    recommended_action_value := 'manual_review';
  else
    account_state_value := 'invite_required';
    recommended_action_value := 'invite';
  end if;

  return jsonb_build_object(
    'ok', true,
    'organization_id', organization_id_value,
    'email', email_value,
    'checked_at', now(),
    'account_state', account_state_value,
    'recommended_action', recommended_action_value,
    'membership', jsonb_build_object(
      'exists', target_profile_id is not null,
      'role', membership_role_value,
      'status', membership_status_value,
      'profile_status', profile_status_value
    ),
    -- Identity facts are disclosed only after the email is proven to be a
    -- member of this organization. Non-members cannot enumerate global Auth.
    'identity', jsonb_build_object(
      'exists', case
        when target_profile_id is null then false
        else auth_present
      end,
      'email_confirmed', case
        when target_profile_id is null then false
        else auth_email_confirmed
      end,
      'disabled', case
        when target_profile_id is null then false
        else (
          not auth_present
          or membership_status_value <> 'active'
          or profile_status_value <> 'active'
          or auth_banned
          or auth_deleted
        )
      end,
      'last_sign_in_at', case
        when target_profile_id is null then null
        else auth_last_sign_in_at
      end,
      'password_change_required', case
        when target_profile_id is null then false
        else password_required
      end
    ),
    'delivery', delivery_snapshot
  );
end;
$$;

-- Keep old readers compatible if a future trusted process projects provider
-- delivery into the legacy invite journal.
alter table content_factory.invite_delivery_attempts
  drop constraint if exists invite_delivery_attempts_delivery_status_check;
alter table content_factory.invite_delivery_attempts
  add constraint invite_delivery_attempts_delivery_status_check check (
    delivery_status in (
      'accepted_unconfirmed',
      'not_requested',
      'unknown',
      'deferred',
      'delivered',
      'failed',
      'bounced',
      'suppressed',
      'complained'
    )
  );

-- Wrap the current audited bootstrap rather than duplicating it.  A temporary
-- password marker now closes the workspace at the database boundary even if a
-- browser bypasses its own route guard.
alter function public.creator_bootstrap(jsonb)
  rename to creator_bootstrap_pre_auth_email_gate;

alter function public.creator_bootstrap_pre_auth_email_gate(jsonb)
  set schema content_factory_private;

revoke all on function
  content_factory_private.creator_bootstrap_pre_auth_email_gate(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_bootstrap(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result jsonb;
begin
  result :=
    content_factory_private.creator_bootstrap_pre_auth_email_gate(p_payload);

  if content_factory_private.auth_password_change_required(auth.uid()) then
    if jsonb_typeof(result) <> 'object' then
      result := '{}'::jsonb;
    end if;
    result := jsonb_set(
      result, '{state}', '"password_change_required"'::jsonb, true
    );
    result := jsonb_set(
      result, '{workspace_open}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{password_change_required}', 'true'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,real_generation}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,mock_generation}', 'false'::jsonb, true
    );
    result := jsonb_set(
      result, '{capabilities,team_view}', 'false'::jsonb, true
    );
  else
    result := jsonb_set(
      result, '{password_change_required}', 'false'::jsonb, true
    );
  end if;

  return result;
end;
$$;

revoke all on function public.system_reserve_auth_email_attempt(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_finalize_auth_email_attempt(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_ingest_auth_email_delivery_event(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_account_access_status(jsonb)
  from public, anon;
revoke all on function public.creator_bootstrap(jsonb)
  from public, anon;

grant execute on function public.system_reserve_auth_email_attempt(jsonb)
  to service_role;
grant execute on function public.system_finalize_auth_email_attempt(jsonb)
  to service_role;
grant execute on function public.system_ingest_auth_email_delivery_event(jsonb)
  to service_role;
grant execute on function public.creator_account_access_status(jsonb)
  to authenticated;
grant execute on function public.creator_bootstrap(jsonb)
  to authenticated;

comment on table content_factory.auth_email_attempts is
  'Server-only lifecycle journal for invitation and password-recovery email attempts.';
comment on table content_factory.auth_email_delivery_events is
  'Append-only normalized provider delivery evidence; raw webhook material is never stored.';
comment on function public.creator_account_access_status(jsonb) is
  'Owner/admin exact-email access diagnosis scoped to one active organization.';

commit;
