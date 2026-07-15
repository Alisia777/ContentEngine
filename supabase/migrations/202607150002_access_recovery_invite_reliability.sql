begin;

create table if not exists content_factory.invite_delivery_attempts (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null
    references content_factory.organizations(id) on delete cascade,
  request_id uuid not null,
  email text not null check (length(email) between 3 and 320),
  status text not null check (
    status in ('invited', 'already_exists', 'rate_limited', 'smtp_required', 'failed')
  ),
  reason_code text not null check (reason_code ~ '^[a-z0-9_]{3,80}$'),
  delivery_status text not null check (
    delivery_status in ('accepted_unconfirmed', 'not_requested')
  ),
  membership_provisioned boolean not null default false,
  requested_by uuid not null references content_factory.profiles(id),
  requested_at timestamptz not null,
  created_at timestamptz not null default now(),
  constraint invite_delivery_attempts_request_email_uq
    unique (organization_id, request_id, email)
);

create index if not exists invite_delivery_attempts_latest_idx
  on content_factory.invite_delivery_attempts
  (organization_id, requested_at desc, request_id, created_at desc);

create or replace function public.system_record_invite_delivery_attempts(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  requested_by_id uuid;
  request_id_value uuid;
  requested_at_value timestamptz;
  results_value jsonb;
  result_item jsonb;
  email_value text;
  status_value text;
  reason_value text;
  delivery_value text;
  membership_value boolean;
  inserted_count integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  organization_id := content_factory_private.require_uuid(p_payload, 'organization_id');
  requested_by_id := content_factory_private.require_uuid(p_payload, 'requested_by');
  request_id_value := content_factory_private.require_uuid(p_payload, 'request_id');
  results_value := coalesce(p_payload -> 'results', '[]'::jsonb);

  if jsonb_typeof(results_value) <> 'array'
     or jsonb_array_length(results_value) < 1
     or jsonb_array_length(results_value) > 50 then
    raise exception using errcode = '22023', message = 'invite_attempt_results_invalid';
  end if;
  begin
    requested_at_value := (p_payload ->> 'requested_at')::timestamptz;
  exception when invalid_text_representation or datetime_field_overflow then
    raise exception using errcode = '22023', message = 'invite_attempt_time_invalid';
  end;
  if requested_at_value < now() - interval '15 minutes'
     or requested_at_value > now() + interval '2 minutes' then
    raise exception using errcode = '22023', message = 'invite_attempt_time_invalid';
  end if;

  if not exists (
    select 1
    from content_factory.memberships membership
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = organization_id
      and membership.profile_id = requested_by_id
      and membership.status = 'active'
      and membership.role in ('owner', 'admin')
      and exists (
        select 1
        from content_factory.training_certifications certification
        where certification.organization_id = organization_id
          and certification.profile_id = requested_by_id
          and certification.module_code = 'operator_final_exam'
          and certification.status = 'passed'
          and (certification.expires_at is null or certification.expires_at > now())
      )
  ) then
    raise exception using errcode = '42501', message = 'inviter_not_authorized';
  end if;

  for result_item in select value from jsonb_array_elements(results_value)
  loop
    if jsonb_typeof(result_item) <> 'object' then
      raise exception using errcode = '22023', message = 'invite_attempt_result_invalid';
    end if;
    email_value := lower(content_factory_private.require_text(result_item, 'email', 3, 320));
    status_value := content_factory_private.require_text(result_item, 'status', 3, 40);
    reason_value := content_factory_private.require_text(result_item, 'reason_code', 3, 80);
    delivery_value := content_factory_private.require_text(result_item, 'delivery_status', 3, 40);
    if email_value !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
       or status_value not in ('invited', 'already_exists', 'rate_limited', 'smtp_required', 'failed')
       or reason_value !~ '^[a-z0-9_]{3,80}$'
       or delivery_value not in ('accepted_unconfirmed', 'not_requested')
       or jsonb_typeof(result_item -> 'membership_provisioned') <> 'boolean' then
      raise exception using errcode = '22023', message = 'invite_attempt_result_invalid';
    end if;
    membership_value := (result_item ->> 'membership_provisioned')::boolean;

    insert into content_factory.invite_delivery_attempts (
      organization_id,
      request_id,
      email,
      status,
      reason_code,
      delivery_status,
      membership_provisioned,
      requested_by,
      requested_at
    ) values (
      organization_id,
      request_id_value,
      email_value,
      status_value,
      reason_value,
      delivery_value,
      membership_value,
      requested_by_id,
      requested_at_value
    )
    on conflict on constraint invite_delivery_attempts_request_email_uq do update set
      status = excluded.status,
      reason_code = excluded.reason_code,
      delivery_status = excluded.delivery_status,
      membership_provisioned = excluded.membership_provisioned;
    inserted_count := inserted_count + 1;
  end loop;

  perform content_factory_private.emit_event(
    organization_id,
    requested_by_id,
    'invite_delivery_attempts_recorded',
    'invite_request',
    request_id_value::text,
    jsonb_build_object('result_count', inserted_count),
    'invite-delivery:' || request_id_value::text,
    'system'
  );

  return jsonb_build_object(
    'ok', true,
    'request_id', request_id_value,
    'stored', inserted_count
  );
end;
$$;

create or replace function public.creator_invite_delivery_attempts(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  latest_request_id uuid;
  latest_requested_at timestamptz;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin']
  );

  select attempt.request_id, attempt.requested_at
    into latest_request_id, latest_requested_at
  from content_factory.invite_delivery_attempts attempt
  where attempt.organization_id = organization_id
  order by attempt.requested_at desc, attempt.created_at desc
  limit 1;

  if latest_request_id is null then
    return jsonb_build_object(
      'ok', true,
      'requested', 0,
      'invited', 0,
      'already_exists', 0,
      'failed', 0,
      'results', '[]'::jsonb,
      'delivery_confirmed', false,
      'persistence', 'stored'
    );
  end if;

  select jsonb_build_object(
    'ok', true,
    'request_id', latest_request_id,
    'requested_at', latest_requested_at,
    'requested', count(*),
    'invited', count(*) filter (where attempt.status = 'invited'),
    'already_exists', count(*) filter (where attempt.status = 'already_exists'),
    'failed', count(*) filter (where attempt.status not in ('invited', 'already_exists')),
    'results', coalesce(jsonb_agg(jsonb_build_object(
      'email', attempt.email,
      'status', attempt.status,
      'reason_code', attempt.reason_code,
      'delivery_status', attempt.delivery_status,
      'membership_provisioned', attempt.membership_provisioned
    ) order by attempt.created_at, attempt.email), '[]'::jsonb),
    'delivery_confirmed', false,
    'persistence', 'stored'
  ) into result
  from content_factory.invite_delivery_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.request_id = latest_request_id;

  return result;
end;
$$;

revoke all on table content_factory.invite_delivery_attempts from public, anon, authenticated;
revoke all on function public.system_record_invite_delivery_attempts(jsonb)
  from public, anon, authenticated;
revoke all on function public.creator_invite_delivery_attempts(jsonb)
  from public, anon;
grant execute on function public.system_record_invite_delivery_attempts(jsonb)
  to service_role;
grant execute on function public.creator_invite_delivery_attempts(jsonb)
  to authenticated;

commit;
