begin;

-- A request is journaled before any external email call. These two explicit
-- states preserve the honest outcome when an Edge Function is interrupted:
-- delivery may have happened, but the server did not observe a final result.
alter table content_factory.invite_delivery_attempts
  drop constraint if exists invite_delivery_attempts_status_check;
alter table content_factory.invite_delivery_attempts
  add constraint invite_delivery_attempts_status_check check (
    status in (
      'invited',
      'already_exists',
      'rate_limited',
      'smtp_required',
      'pending_verification',
      'failed'
    )
  );

alter table content_factory.invite_delivery_attempts
  drop constraint if exists invite_delivery_attempts_delivery_status_check;
alter table content_factory.invite_delivery_attempts
  add constraint invite_delivery_attempts_delivery_status_check check (
    delivery_status in ('accepted_unconfirmed', 'not_requested', 'unknown')
  );

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
  prior_request_id uuid;
  suppressed_value jsonb := '[]'::jsonb;
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

  -- Serialize only the short reservation/upsert transaction per organization.
  -- External mail calls happen after commit and never hold this lock.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      'contentengine-invite:' || organization_id::text,
      0
    )
  );

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
       or status_value not in (
         'invited',
         'already_exists',
         'rate_limited',
         'smtp_required',
         'pending_verification',
         'failed'
       )
       or reason_value !~ '^[a-z0-9_]{3,80}$'
       or delivery_value not in ('accepted_unconfirmed', 'not_requested', 'unknown')
       or jsonb_typeof(result_item -> 'membership_provisioned') <> 'boolean' then
      raise exception using errcode = '22023', message = 'invite_attempt_result_invalid';
    end if;
    membership_value := (result_item ->> 'membership_provisioned')::boolean;

    prior_request_id := null;
    if reason_value = 'invite_processing_started' then
      select attempt.request_id
        into prior_request_id
      from content_factory.invite_delivery_attempts attempt
      where attempt.organization_id = organization_id
        and attempt.email = email_value
        and attempt.request_id <> request_id_value
        and attempt.requested_at >= now() - interval '10 minutes'
        and (
          attempt.status = 'pending_verification'
          or attempt.delivery_status = 'accepted_unconfirmed'
        )
      order by attempt.requested_at desc, attempt.created_at desc
      limit 1;

      if prior_request_id is not null then
        status_value := 'pending_verification';
        reason_value := 'duplicate_request_suppressed';
        delivery_value := 'unknown';
        membership_value := false;
        suppressed_value := suppressed_value || jsonb_build_array(email_value);
      end if;
    end if;

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
    'stored', inserted_count,
    'suppressed', suppressed_value
  );
end;
$$;

revoke all on function public.system_record_invite_delivery_attempts(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_record_invite_delivery_attempts(jsonb)
  to service_role;

commit;
