begin;

-- P0 containment for Auth email delivery evidence.
--
-- A recipient and a time window are useful triage hints, but they cannot prove
-- which request caused a provider callback.  In particular, a public password
-- reset can have the same recipient and timestamp window as a manager invite.
-- Only a provider message id already bound to an attempt by the trusted sender
-- may project delivery.  This migration deliberately does not change how mail
-- is sent; until a sender can persist that id, callbacks remain ambiguous.
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

  -- Exact means all three immutable dispatch facts agree: provider, provider
  -- message id, and normalized recipient.  A legacy not_requested invite is
  -- explicitly ineligible because no outbound message existed.
  if provider_message_value is not null then
    select count(*), (array_agg(attempt.id))[1]
      into candidate_count, matched_attempt_id
    from content_factory.auth_email_attempts attempt
    where attempt.provider = provider_value
      and attempt.provider_message_id = provider_message_value
      and attempt.email = recipient_value
      and attempt.status <> 'suppressed'
      and not (
        attempt.correlation_status = 'exact'
        and attempt.correlation_basis = 'unique_recipient_window'
      )
      and not exists (
        select 1
        from content_factory.invite_delivery_attempts legacy_attempt
        where legacy_attempt.organization_id = attempt.organization_id
          and legacy_attempt.request_id = attempt.request_id
          and lower(btrim(legacy_attempt.email)) = attempt.email
          and attempt.purpose = 'invite'
          and legacy_attempt.delivery_status = 'not_requested'
      );

    if candidate_count = 1 then
      select attempt.* into matched_attempt
      from content_factory.auth_email_attempts attempt
      where attempt.id = matched_attempt_id;
      correlation_value := 'exact';
      basis_value := 'provider_message_id';
    end if;
  end if;

  -- Recipient-window matching is evidence for an operator, never identity.
  -- Keep the existing JSON vocabulary/basis values, but report one candidate
  -- as ambiguous and never attach its id or project provider delivery.
  if correlation_value <> 'exact' then
    matched_attempt_id := null;
    select count(*)
      into candidate_count
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
      and attempt.requested_at <= event_created_value + interval '5 minutes'
      and not exists (
        select 1
        from content_factory.invite_delivery_attempts legacy_attempt
        where legacy_attempt.organization_id = attempt.organization_id
          and legacy_attempt.request_id = attempt.request_id
          and lower(btrim(legacy_attempt.email)) = attempt.email
          and attempt.purpose = 'invite'
          and legacy_attempt.delivery_status = 'not_requested'
      );

    if candidate_count = 1 then
      correlation_value := 'ambiguous';
      basis_value := 'unique_recipient_window';
    elsif candidate_count > 1 then
      correlation_value := 'ambiguous';
      basis_value := 'multiple_recipient_window';
    else
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
      correlation_basis = 'provider_message_id'
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
      correlation_basis = 'provider_message_id'
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

-- Retain the complete, already-audited diagnosis as the base implementation.
-- The wrapper only tightens automatic actions when delivery correlation is not
-- trustworthy; its response keeps exactly the same keys and object layout.
alter function public.creator_account_access_status(jsonb)
  rename to creator_account_access_status_pre_trusted_correlation;
alter function public.creator_account_access_status_pre_trusted_correlation(jsonb)
  set schema content_factory_private;

revoke all on function
  content_factory_private.creator_account_access_status_pre_trusted_correlation(jsonb)
  from public, anon, authenticated, service_role;

create or replace function public.creator_account_access_status(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
declare
  result jsonb;
  delivery_snapshot jsonb;
  delivery_was_not_requested boolean := false;
  delivery_is_unresolved boolean := false;
  membership_exists boolean := false;
  identity_disabled boolean := false;
begin
  result :=
    content_factory_private.creator_account_access_status_pre_trusted_correlation(
      p_payload
    );
  delivery_snapshot := result -> 'delivery';

  if delivery_snapshot is null
     or delivery_snapshot = 'null'::jsonb then
    return result;
  end if;

  if delivery_snapshot ->> 'purpose' = 'invite' then
    select exists (
      select 1
      from content_factory.invite_delivery_attempts legacy_attempt
      where legacy_attempt.organization_id =
          (result ->> 'organization_id')::uuid
        and lower(btrim(legacy_attempt.email)) = result ->> 'email'
        and legacy_attempt.delivery_status = 'not_requested'
        and legacy_attempt.requested_at =
          (delivery_snapshot ->> 'requested_at')::timestamptz
        and legacy_attempt.reason_code = delivery_snapshot ->> 'reason_code'
    ) into delivery_was_not_requested;
  end if;

  membership_exists :=
    coalesce((result #>> '{membership,exists}')::boolean, false);
  identity_disabled :=
    coalesce((result #>> '{identity,disabled}')::boolean, false);

  -- A known not_requested result proves there was no invite email to wait for.
  -- It is therefore safe to return the ordinary invite/recovery action unless
  -- the account itself is disabled or already ready.
  if delivery_was_not_requested
     and result ->> 'recommended_action' not in ('none', 'manual_review')
     and not identity_disabled then
    if membership_exists then
      result := jsonb_set(
        result, '{account_state}', '"recovery_required"'::jsonb, false
      );
      result := jsonb_set(
        result, '{recommended_action}', '"recovery"'::jsonb, false
      );
    else
      result := jsonb_set(
        result, '{account_state}', '"invite_required"'::jsonb, false
      );
      result := jsonb_set(
        result, '{recommended_action}', '"invite"'::jsonb, false
      );
    end if;
    return result;
  end if;

  delivery_is_unresolved :=
    delivery_snapshot ->> 'status' in ('reserved', 'accepted')
    and not (
      delivery_snapshot ->> 'correlation_status' = 'exact'
      and delivery_snapshot ->> 'correlation_basis' = 'provider_message_id'
    );

  -- Keep the short pending-delivery cooldown, but once it expires never turn
  -- an ambiguous/unmatched accepted send into an automatic resend action.
  if delivery_is_unresolved
     and result ->> 'recommended_action' in ('invite', 'recovery') then
    result := jsonb_set(
      result, '{account_state}', '"unknown"'::jsonb, false
    );
    result := jsonb_set(
      result, '{recommended_action}', '"manual_review"'::jsonb, false
    );
  end if;

  return result;
end;
$$;

revoke all on function public.system_ingest_auth_email_delivery_event(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_ingest_auth_email_delivery_event(jsonb)
  to service_role;

revoke all on function public.creator_account_access_status(jsonb)
  from public, anon, service_role;
grant execute on function public.creator_account_access_status(jsonb)
  to authenticated;

comment on function public.system_ingest_auth_email_delivery_event(jsonb) is
  'Append-only provider event ingest; only pre-bound provider/message/recipient identity may project delivery.';
comment on function public.creator_account_access_status(jsonb) is
  'Owner/admin exact-email access diagnosis; unresolved delivery evidence requires manual review before retry.';

commit;
