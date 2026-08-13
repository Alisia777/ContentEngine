begin;

-- Notification Center v4.9.1 is an additive extension of the only durable
-- notification chain:
--
--   content_factory.notification_outbox
--     -> public.system_emit_notification(jsonb)
--     -> content_factory.user_notifications
--
-- Deploy after 202608040005_project_scoped_workflow.sql and before any v4.9.1
-- producer or Notification Center UI. The background worker wire envelope is
-- deliberately unchanged so the already deployed worker can drain both legacy
-- and v4.9.1 rows during a rolling deployment.
--
-- Rollback: before any v4.9.1 producer is enabled, revoke/drop the two new
-- authenticated RPCs and the private v4.9.1 helpers, then restore the four
-- replaced legacy RPC/guard definitions from 202607160005/006. Once a v4.9.1
-- producer has committed rows, do not drop these columns or indexes: disable
-- producers/UI first and roll forward. Inbox/outbox rows remain server-owned;
-- no rollback path grants client DELETE.

alter table content_factory.user_notifications
  add column if not exists contract_version smallint not null default 1,
  add column if not exists event_created_at timestamptz not null default now(),
  add column if not exists expires_at timestamptz not null
    default (now() + interval '180 days'),
  add column if not exists resolved_at timestamptz,
  add column if not exists source_section text,
  add column if not exists requires_action boolean,
  add column if not exists action_key text,
  add column if not exists project_id uuid,
  add column if not exists object_id uuid,
  add column if not exists process_id uuid,
  add column if not exists recipient_role_ids text[],
  add column if not exists canonical_dedupe_key text,
  add column if not exists dedupe_version bigint not null default 0,
  add column if not exists read_state_version smallint not null default 1;

alter table content_factory.notification_outbox
  add column if not exists contract_version smallint not null default 1,
  add column if not exists event_created_at timestamptz not null default now(),
  add column if not exists expires_at timestamptz not null
    default (now() + interval '180 days'),
  add column if not exists resolved_at timestamptz,
  add column if not exists source_section text,
  add column if not exists requires_action boolean,
  add column if not exists action_key text,
  add column if not exists project_id uuid,
  add column if not exists object_id uuid,
  add column if not exists process_id uuid,
  add column if not exists recipient_role_ids text[],
  add column if not exists canonical_dedupe_key text,
  add column if not exists dedupe_version bigint not null default 0;

-- Existing rows are explicitly legacy. Their recipient remains the original
-- direct recipient; no role, source or exact action target is inferred. A
-- finite 180-day visibility horizon is the only policy backfill.
drop trigger if exists guard_user_notification
  on content_factory.user_notifications;
drop trigger if exists guard_notification_outbox
  on content_factory.notification_outbox;

update content_factory.user_notifications notification
set contract_version = 1,
    event_created_at = notification.created_at,
    expires_at = notification.created_at + interval '180 days',
    dedupe_version = 0,
    read_state_version = 1,
    kind = case when notification.kind = 'system'
      then 'system_info' else notification.kind end,
    request_hash = case when notification.kind = 'system' then
      content_factory_private.json_hash(jsonb_build_object(
        'recipient_id', notification.recipient_id,
        'kind', 'system_info',
        'severity', notification.severity,
        'title', notification.title,
        'body', notification.body,
        'deep_link', notification.deep_link,
        'entity_type', notification.entity_type,
        'entity_id', notification.entity_id,
        'properties', notification.properties
      ))
      else notification.request_hash
    end;

update content_factory.notification_outbox outbox
set contract_version = 1,
    event_created_at = outbox.created_at,
    expires_at = outbox.created_at + interval '180 days',
    dedupe_version = 0,
    kind = case when outbox.kind = 'system'
      then 'system_info' else outbox.kind end,
    request_hash = case when outbox.kind = 'system' then
      content_factory_private.json_hash(jsonb_build_object(
        'recipient_id', outbox.recipient_id,
        'kind', 'system_info',
        'severity', outbox.severity,
        'title', outbox.title,
        'body', outbox.body,
        'deep_link', outbox.deep_link,
        'entity_type', outbox.entity_type,
        'entity_id', outbox.entity_id,
        'properties', outbox.properties
      ))
      else outbox.request_hash
    end;

create or replace function
  content_factory_private.notification_role_ids_valid_v491(p_roles text[])
returns boolean
language sql
immutable
set search_path = ''
as $function$
  select p_roles is null or (
    cardinality(p_roles) between 1 and 7
    and p_roles <@ array[
      'owner', 'admin', 'producer', 'reviewer', 'operator', 'trainee',
      'viewer'
    ]::text[]
    and p_roles = (
      select array_agg(role_id order by role_id)
      from (
        select distinct role_id
        from unnest(p_roles) role_value(role_id)
      ) normalized
    )
  )
$function$;

create or replace function
  content_factory_private.notification_payload_sensitive_v491(p_value jsonb)
returns boolean
language plpgsql
immutable
set search_path = ''
as $function$
declare
  item record;
  scalar_value text;
begin
  if p_value is null or p_value = 'null'::jsonb then
    return false;
  end if;

  if jsonb_typeof(p_value) = 'object' then
    for item in select key, value from jsonb_each(p_value)
    loop
      if item.key ~* (
        '(^|_)(access_token|refresh_token|id_token|token|authorization|' ||
        'auth|api_key|secret|signature|credential|password|passwd|cookie|' ||
        'session|session_id|jwt|signed_url|action_payload|raw_data|' ||
        'raw_payload|raw_form|form_values|file_content|file_bytes|' ||
        'provider_payload|provider_response|paid_confirmation|prompt)($|_)'
      ) or content_factory_private.notification_payload_sensitive_v491(
        item.value
      ) then
        return true;
      end if;
    end loop;
    return false;
  end if;

  if jsonb_typeof(p_value) = 'array' then
    for item in select value from jsonb_array_elements(p_value)
    loop
      if content_factory_private.notification_payload_sensitive_v491(
        item.value
      ) then
        return true;
      end if;
    end loop;
    return false;
  end if;

  if jsonb_typeof(p_value) <> 'string' then
    return false;
  end if;
  scalar_value := p_value #>> '{}';
  return scalar_value ~* (
    '(^|[[:space:]])(bearer|basic)[[:space:]]+[A-Za-z0-9+/=_-]{12,}' ||
    '|(^|[[:space:]])(sk[-_]|rk_live_|pk_live_|gh[pousr]_|xox[baprs]-|' ||
    'AIza)[A-Za-z0-9_-]{8,}' ||
    '|eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}' ||
    '|[?&#](access_?token|refresh_?token|token|secret|signature|jwt|' ||
    'api_?key)='
  );
end;
$function$;

create or replace function public.system_claim_notification_outbox(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  limit_value integer := 12;
  items_value jsonb := '[]'::jsonb;
  recovered_count integer := 0;
  observed_count integer := 0;
  expired_count integer := 0;
  unresolved_count integer := 0;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 1024
     or p_payload - array['limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'notification_outbox_claim_payload_invalid';
  end if;
  if p_payload ? 'limit' then
    begin
      limit_value := (p_payload ->> 'limit')::integer;
    exception when invalid_text_representation or numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'notification_outbox_claim_limit_invalid';
    end;
  end if;
  if limit_value not between 1 and 50 then
    raise exception using
      errcode = '22023',
      message = 'notification_outbox_claim_limit_invalid';
  end if;

  -- A lost delivery response is observed by physical legacy key or by the
  -- canonical dedupe family/version. A newer inbox revision also proves that
  -- every older delivery in the same family is obsolete and resolved.
  update content_factory.notification_outbox outbox
  set status = 'delivered',
      delivered_at = notification.event_created_at,
      lease_token = null,
      lease_expires_at = null,
      last_error_code = null
  from content_factory.user_notifications notification
  where outbox.status in ('pending', 'delivering')
    and notification.organization_id = outbox.organization_id
    and notification.recipient_id = outbox.recipient_id
    and (
      (outbox.contract_version = 1
        and notification.dedupe_key = outbox.dedupe_key)
      or (outbox.contract_version = 491
        and notification.contract_version = 491
        and notification.canonical_dedupe_key =
          outbox.canonical_dedupe_key
        and notification.dedupe_version >= outbox.dedupe_version)
    );
  get diagnostics observed_count = row_count;

  -- Expiry resolves the delivery obligation without creating an already stale
  -- inbox item. Expired is terminal but is not a worker failure/dead letter.
  update content_factory.notification_outbox outbox
  set status = 'expired',
      lease_token = null,
      lease_expires_at = null,
      last_error_code = 'notification_expired'
  where outbox.status in ('pending', 'delivering')
    and outbox.expires_at <= now();
  get diagnostics expired_count = row_count;

  update content_factory.notification_outbox outbox
  set status = 'pending',
      lease_token = null,
      lease_expires_at = null,
      next_attempt_at = now(),
      last_error_code = coalesce(
        outbox.last_error_code, 'delivery_lease_expired'
      )
  where outbox.status = 'delivering'
    and outbox.lease_expires_at <= now();
  get diagnostics recovered_count = row_count;

  with candidates as (
    select outbox.id
    from content_factory.notification_outbox outbox
    where outbox.status = 'pending'
      and outbox.next_attempt_at <= now()
      and outbox.expires_at > now()
    order by outbox.next_attempt_at, outbox.created_at, outbox.id
    for update skip locked
    limit limit_value
  ),
  claimed as (
    update content_factory.notification_outbox outbox
    set status = 'delivering',
        attempt_count = outbox.attempt_count + 1,
        lease_token = extensions.gen_random_uuid(),
        lease_expires_at = now() + interval '3 minutes'
    from candidates
    where outbox.id = candidates.id
      and outbox.status = 'pending'
    returning outbox.*
  )
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', claimed.id,
    'lease_token', claimed.lease_token,
    'attempt_count', claimed.attempt_count,
    -- Keep this exact 11-key payload shape: the deployed Edge worker validates
    -- it strictly. v4.9.1 metadata is nested inside safe properties.
    'payload', jsonb_build_object(
      'organization_id', claimed.organization_id,
      'recipient_id', claimed.recipient_id,
      'kind', claimed.kind,
      'severity', claimed.severity,
      'title', claimed.title,
      'body', claimed.body,
      'deep_link', claimed.deep_link,
      'entity_type', claimed.entity_type,
      'entity_id', claimed.entity_id,
      'properties', claimed.properties,
      'idempotency_key', claimed.dedupe_key
    )
  ) order by claimed.next_attempt_at, claimed.created_at, claimed.id),
    '[]'::jsonb)
  into items_value
  from claimed;

  select count(*)::integer into unresolved_count
  from content_factory.notification_outbox outbox
  where outbox.status not in ('delivered', 'expired');

  return jsonb_build_object(
    'ok', true,
    'items', items_value,
    'recovered_leases', recovered_count,
    'observed_deliveries', observed_count,
    'expired', expired_count,
    'unresolved', unresolved_count
  );
end;
$function$;

create or replace function public.system_complete_notification_outbox(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  outbox_id_value uuid;
  lease_token_value uuid;
  delivered_value boolean;
  error_code_value text;
  outbox_row content_factory.notification_outbox%rowtype;
  retry_seconds integer;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 2048
     or p_payload - array[
       'outbox_id', 'lease_token', 'delivered', 'error_code'
     ]::text[] <> '{}'::jsonb
     or not p_payload ? 'delivered'
     or jsonb_typeof(p_payload -> 'delivered') <> 'boolean' then
    raise exception using
      errcode = '22023',
      message = 'notification_outbox_completion_payload_invalid';
  end if;
  outbox_id_value := content_factory_private.require_uuid(
    p_payload, 'outbox_id'
  );
  lease_token_value := content_factory_private.require_uuid(
    p_payload, 'lease_token'
  );
  delivered_value := (p_payload ->> 'delivered')::boolean;
  error_code_value := nullif(lower(btrim(coalesce(
    p_payload ->> 'error_code', ''
  ))), '');
  if (delivered_value and error_code_value is not null)
     or (not delivered_value and (
       error_code_value is null
       or error_code_value !~ '^[a-z][a-z0-9_]{2,99}$'
     )) then
    raise exception using
      errcode = '22023', message = 'notification_outbox_completion_invalid';
  end if;

  select outbox.* into outbox_row
  from content_factory.notification_outbox outbox
  where outbox.id = outbox_id_value
  for update;
  if outbox_row.id is null then
    raise exception using
      errcode = '22023', message = 'notification_outbox_not_found';
  end if;
  if outbox_row.status in ('delivered', 'failed', 'expired') then
    return jsonb_build_object(
      'ok', true,
      'outbox_id', outbox_row.id,
      'status', outbox_row.status,
      'attempt_count', outbox_row.attempt_count,
      'idempotent', true
    );
  end if;
  if outbox_row.status <> 'delivering'
     or outbox_row.lease_token is distinct from lease_token_value then
    raise exception using
      errcode = '55000', message = 'notification_outbox_lease_mismatch';
  end if;
  if outbox_row.lease_expires_at <= now() then
    raise exception using
      errcode = '55000', message = 'notification_outbox_lease_expired';
  end if;

  if outbox_row.expires_at <= now() then
    update content_factory.notification_outbox outbox
    set status = 'expired',
        lease_token = null,
        lease_expires_at = null,
        last_error_code = 'notification_expired'
    where outbox.id = outbox_id_value
    returning * into outbox_row;
  elsif delivered_value then
    update content_factory.notification_outbox outbox
    set status = 'delivered',
        delivered_at = now(),
        lease_token = null,
        lease_expires_at = null,
        last_error_code = null
    where outbox.id = outbox_id_value
    returning * into outbox_row;
  elsif outbox_row.attempt_count >= 12 then
    update content_factory.notification_outbox outbox
    set status = 'failed',
        lease_token = null,
        lease_expires_at = null,
        last_error_code = error_code_value
    where outbox.id = outbox_id_value
    returning * into outbox_row;
  else
    retry_seconds := least(
      3600,
      (30 * power(2, least(outbox_row.attempt_count - 1, 7)))::integer
    );
    update content_factory.notification_outbox outbox
    set status = 'pending',
        next_attempt_at = least(
          outbox_row.expires_at,
          now() + make_interval(secs => retry_seconds)
        ),
        lease_token = null,
        lease_expires_at = null,
        last_error_code = error_code_value
    where outbox.id = outbox_id_value
    returning * into outbox_row;
  end if;

  return jsonb_build_object(
    'ok', true,
    'outbox_id', outbox_row.id,
    'status', outbox_row.status,
    'attempt_count', outbox_row.attempt_count,
    'next_attempt_at', outbox_row.next_attempt_at,
    'idempotent', false
  );
end;
$function$;

create or replace function public.system_notification_outbox_health(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  pending_count integer;
  delivering_count integer;
  failed_count integer;
  due_count integer;
  expired_count integer;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'notification_outbox_health_payload_invalid';
  end if;
  select
    count(*) filter (where outbox.status = 'pending')::integer,
    count(*) filter (where outbox.status = 'delivering')::integer,
    count(*) filter (where outbox.status = 'failed')::integer,
    count(*) filter (
      where outbox.status = 'pending'
        and outbox.next_attempt_at <= now()
        and outbox.expires_at > now()
    )::integer,
    count(*) filter (where outbox.status = 'expired')::integer
  into pending_count, delivering_count, failed_count, due_count, expired_count
  from content_factory.notification_outbox outbox;
  return jsonb_build_object(
    'ok', true,
    'unresolved', pending_count + delivering_count + failed_count,
    'pending', pending_count,
    'delivering', delivering_count,
    'failed', failed_count,
    'due', due_count,
    'expired', expired_count
  );
end;
$function$;


create or replace function
  content_factory_private.deliver_notification_v491(p_payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  recipient_id_value uuid;
  notification_type_value text;
  severity_value text;
  title_value text;
  body_value text;
  deep_link_value text;
  entity_type_value text;
  entity_id_value text;
  wire_properties_value jsonb;
  properties_value jsonb;
  metadata_value jsonb;
  source_section_value text;
  requires_action_value boolean;
  action_key_value text;
  project_id_value uuid;
  object_id_value uuid;
  process_id_value uuid;
  recipient_roles_value text[];
  canonical_dedupe_key_value text;
  dedupe_version_value bigint;
  event_created_at_value timestamptz;
  expires_at_value timestamptz;
  resolved_at_value timestamptz;
  delivery_key_value text;
  expected_delivery_key text;
  request_payload jsonb;
  request_hash_value text;
  delivery_outbox content_factory.notification_outbox%rowtype;
  notification_row content_factory.user_notifications%rowtype;
  changed_value boolean := false;
begin
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  recipient_id_value := content_factory_private.require_uuid(
    p_payload, 'recipient_id'
  );
  notification_type_value := lower(content_factory_private.require_text(
    p_payload, 'kind', 3, 80
  ));
  severity_value := lower(content_factory_private.require_text(
    p_payload, 'severity', 3, 20
  ));
  title_value := content_factory_private.require_text(
    p_payload, 'title', 1, 140
  );
  body_value := content_factory_private.require_text(
    p_payload, 'body', 1, 500
  );
  deep_link_value := content_factory_private.require_text(
    p_payload, 'deep_link', 3, 600
  );
  entity_type_value := content_factory_private.require_text(
    p_payload, 'entity_type', 2, 80
  );
  entity_id_value := content_factory_private.require_text(
    p_payload, 'entity_id', 1, 180
  );
  delivery_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  wire_properties_value := p_payload -> 'properties';
  metadata_value := wire_properties_value -> '_notification_v491';
  if jsonb_typeof(wire_properties_value) <> 'object'
     or jsonb_typeof(metadata_value) <> 'object'
     or metadata_value - array[
       'contract_version', 'event_created_at', 'expires_at', 'resolved_at',
       'source_section', 'requires_action', 'action_key', 'project_id',
       'object_id', 'process_id', 'recipient_role_ids',
       'canonical_dedupe_key', 'dedupe_version'
     ]::text[] <> '{}'::jsonb
     or metadata_value #>> '{contract_version}' <> '491' then
    raise exception using
      errcode = '22023', message = 'notification_v491_metadata_invalid';
  end if;

  source_section_value := metadata_value ->> 'source_section';
  action_key_value := nullif(metadata_value ->> 'action_key', '');
  canonical_dedupe_key_value := metadata_value ->> 'canonical_dedupe_key';
  if jsonb_typeof(metadata_value -> 'requires_action') <> 'boolean'
     or jsonb_typeof(metadata_value -> 'dedupe_version') <> 'number'
     or coalesce(metadata_value ->> 'dedupe_version', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'notification_v491_metadata_invalid';
  end if;
  requires_action_value :=
    (metadata_value ->> 'requires_action')::boolean;
  begin
    dedupe_version_value :=
      (metadata_value ->> 'dedupe_version')::bigint;
    event_created_at_value :=
      (metadata_value ->> 'event_created_at')::timestamptz;
    expires_at_value := (metadata_value ->> 'expires_at')::timestamptz;
    resolved_at_value := nullif(
      metadata_value ->> 'resolved_at', ''
    )::timestamptz;
    project_id_value := nullif(metadata_value ->> 'project_id', '')::uuid;
    object_id_value := nullif(metadata_value ->> 'object_id', '')::uuid;
    process_id_value := nullif(metadata_value ->> 'process_id', '')::uuid;
  exception
    when invalid_text_representation or invalid_datetime_format
      or datetime_field_overflow or numeric_value_out_of_range then
      raise exception using
        errcode = '22023', message = 'notification_v491_metadata_invalid';
  end;

  recipient_roles_value := null;
  if metadata_value ? 'recipient_role_ids' then
    if jsonb_typeof(metadata_value -> 'recipient_role_ids') <> 'array'
       or exists (
         select 1
         from jsonb_array_elements(
           metadata_value -> 'recipient_role_ids'
         ) item
         where jsonb_typeof(item) <> 'string'
       ) then
      raise exception using
        errcode = '22023', message = 'notification_recipient_roles_invalid';
    end if;
    select array_agg(role_id order by role_id)
      into recipient_roles_value
    from (
      select distinct lower(btrim(value)) as role_id
      from jsonb_array_elements_text(
        metadata_value -> 'recipient_role_ids'
      ) role_value(value)
    ) normalized;
  end if;
  if not content_factory_private.notification_role_ids_valid_v491(
    recipient_roles_value
  ) then
    raise exception using
      errcode = '22023', message = 'notification_recipient_roles_invalid';
  end if;

  properties_value := wire_properties_value - '_notification_v491';
  if notification_type_value not in (
    'action_required', 'mention', 'assignment', 'process_complete',
    'warning', 'error', 'access_change', 'system_info'
  ) or source_section_value not in (
    'finder', 'results', 'research', 'ai', 'create', 'review', 'publish',
    'processes', 'settings', 'trash', 'system'
  ) or severity_value <> (case notification_type_value
    when 'action_required' then 'warning'
    when 'mention' then 'info'
    when 'assignment' then 'info'
    when 'process_complete' then 'success'
    when 'warning' then 'warning'
    when 'error' then 'danger'
    when 'access_change' then 'neutral'
    when 'system_info' then 'neutral'
  end) or (notification_type_value not in ('mention', 'access_change')
    and requires_action_value is distinct from (case notification_type_value
      when 'action_required' then true
      when 'assignment' then true
      when 'process_complete' then false
      when 'warning' then true
      when 'error' then true
      when 'system_info' then false
    end))
     or (requires_action_value and action_key_value is null)
     or (action_key_value is not null and action_key_value not in (
       'ai.open-decisions', 'process.open', 'review.open-object', 'object.open'
     ))
     or (action_key_value = 'ai.open-decisions' and project_id_value is null)
     or (action_key_value = 'process.open' and process_id_value is null)
     or (action_key_value in ('review.open-object', 'object.open')
       and object_id_value is null)
     or canonical_dedupe_key_value is null
     or canonical_dedupe_key_value !~
       '^[A-Za-z0-9][A-Za-z0-9:._/-]{7,179}$'
     or dedupe_version_value not between 1 and 2147483647
     or event_created_at_value > clock_timestamp() + interval '5 minutes'
     or expires_at_value <= event_created_at_value
     or expires_at_value > event_created_at_value + interval '180 days'
     or (resolved_at_value is not null and (
       resolved_at_value < event_created_at_value
       or resolved_at_value > expires_at_value
     ))
     or content_factory_private.notification_payload_sensitive_v491(
       jsonb_build_object(
         'title', title_value, 'body', body_value,
         'properties', properties_value
       )
     ) then
    raise exception using
      errcode = '22023', message = 'notification_v491_contract_invalid';
  end if;

  if deep_link_value <> content_factory_private.notification_route_v491(
    source_section_value, action_key_value, project_id_value,
    object_id_value, process_id_value
  ) then
    raise exception using
      errcode = '22023', message = 'notification_action_route_invalid';
  end if;
  expected_delivery_key :=
    'notification-v491:' || encode(extensions.digest(
      canonical_dedupe_key_value, 'sha256'
    ), 'hex') || ':' || dedupe_version_value::text;
  if delivery_key_value <> expected_delivery_key then
    raise exception using
      errcode = '22023', message = 'notification_delivery_key_invalid';
  end if;

  request_payload := jsonb_build_object(
    'recipient_id', recipient_id_value,
    'kind', notification_type_value,
    'severity', severity_value,
    'title', title_value,
    'body', body_value,
    'deep_link', deep_link_value,
    'entity_type', entity_type_value,
    'entity_id', entity_id_value,
    'properties', wire_properties_value
  );
  request_hash_value := content_factory_private.json_hash(request_payload);

  select outbox.* into delivery_outbox
  from content_factory.notification_outbox outbox
  where outbox.organization_id = organization_id_value
    and outbox.recipient_id = recipient_id_value
    and outbox.dedupe_key = delivery_key_value
    and outbox.contract_version = 491;
  if delivery_outbox.id is null
     or delivery_outbox.status <> 'delivering'
     or delivery_outbox.request_hash <> request_hash_value then
    raise exception using
      errcode = '55000', message = 'notification_delivery_not_claimed';
  end if;

  -- Delivery after recipient revocation/role change or after expiry resolves the
  -- durable obligation without fabricating an inbox row that cannot be seen.
  if expires_at_value <= now() or not exists (
    select 1
    from content_factory.memberships membership
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = organization_id_value
      and membership.profile_id = recipient_id_value
      and membership.status = 'active'
      and (recipient_roles_value is null
        or membership.role = any(recipient_roles_value))
  ) then
    return jsonb_build_object(
      'ok', true,
      'notification', null,
      'skipped', case when expires_at_value <= now()
        then 'expired' else 'recipient_inactive' end
    );
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('notification-v491:' || recipient_id_value::text || ':' ||
      canonical_dedupe_key_value)
  );
  select notification.* into notification_row
  from content_factory.user_notifications notification
  where notification.organization_id = organization_id_value
    and notification.recipient_id = recipient_id_value
    and notification.contract_version = 491
    and notification.canonical_dedupe_key = canonical_dedupe_key_value
  for update;

  if notification_row.id is null then
    insert into content_factory.user_notifications (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key, contract_version, event_created_at, expires_at,
      resolved_at, source_section, requires_action, action_key, project_id,
      object_id, process_id, recipient_role_ids, canonical_dedupe_key,
      dedupe_version, read_state_version
    ) values (
      organization_id_value, recipient_id_value, notification_type_value,
      severity_value, title_value, body_value, deep_link_value,
      entity_type_value, entity_id_value, properties_value,
      request_hash_value, delivery_key_value, 491, event_created_at_value,
      expires_at_value, resolved_at_value, source_section_value,
      requires_action_value, action_key_value, project_id_value,
      object_id_value, process_id_value, recipient_roles_value,
      canonical_dedupe_key_value, dedupe_version_value, 491
    )
    returning * into notification_row;
    changed_value := true;
  elsif notification_row.dedupe_version = dedupe_version_value then
    if notification_row.request_hash <> request_hash_value then
      raise exception using
        errcode = '23505', message = 'notification_idempotency_conflict';
    end if;
  elsif notification_row.dedupe_version < dedupe_version_value then
    update content_factory.user_notifications notification
    set kind = notification_type_value,
        severity = severity_value,
        title = title_value,
        body = body_value,
        deep_link = deep_link_value,
        entity_type = entity_type_value,
        entity_id = entity_id_value,
        properties = properties_value,
        request_hash = request_hash_value,
        dedupe_key = delivery_key_value,
        event_created_at = event_created_at_value,
        expires_at = expires_at_value,
        resolved_at = resolved_at_value,
        source_section = source_section_value,
        requires_action = requires_action_value,
        action_key = action_key_value,
        project_id = project_id_value,
        object_id = object_id_value,
        process_id = process_id_value,
        recipient_role_ids = recipient_roles_value,
        dedupe_version = dedupe_version_value,
        read_at = null
    where notification.id = notification_row.id
    returning * into notification_row;
    changed_value := true;
  end if;

  if changed_value then
    perform content_factory_private.emit_event(
      organization_id_value,
      recipient_id_value,
      'notification_emitted',
      coalesce(entity_type_value, 'notification'),
      coalesce(entity_id_value, notification_row.id::text),
      jsonb_build_object(
        'notification_id', notification_row.id,
        'kind', notification_type_value,
        'severity', severity_value,
        'recipient_id', recipient_id_value,
        'dedupe_version', dedupe_version_value
      ),
      left('notification-emitted:' || recipient_id_value::text || ':' ||
        delivery_key_value, 180),
      'system'
    );
  end if;

  return jsonb_build_object(
    'ok', true,
    'notification', jsonb_build_object(
      'id', notification_row.id,
      'organization_id', notification_row.organization_id,
      'recipient_id', notification_row.recipient_id,
      'type', notification_row.kind,
      'severity', notification_row.severity,
      'source_section', notification_row.source_section,
      'dedupe_key', notification_row.canonical_dedupe_key,
      'dedupe_version', notification_row.dedupe_version,
      'read_at', notification_row.read_at,
      'created_at', notification_row.event_created_at,
      'expires_at', notification_row.expires_at
    ),
    'changed', changed_value
  );
end;
$function$;

-- Backward-compatible delivery owner. Legacy callers retain the exact payload
-- and result shape; canonical rows are identified only by their validated
-- metadata envelope and delegated to the v4.9.1 delivery path.
create or replace function public.system_emit_notification(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  organization_id uuid;
  recipient_id uuid;
  kind_value text;
  severity_value text := 'info';
  title_value text;
  body_value text;
  deep_link_value text;
  entity_type_value text;
  entity_id_value text;
  properties_value jsonb;
  idempotency_key_value text;
  request_payload jsonb;
  request_hash_value text;
  existing_hash text;
  notification_row content_factory.user_notifications%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 49152
     or p_payload - array[
       'organization_id', 'recipient_id', 'kind', 'severity',
       'title', 'body', 'deep_link', 'entity_type', 'entity_id',
       'properties', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'system_notification_payload_invalid';
  end if;
  if p_payload #>> '{properties,_notification_v491,contract_version}' = '491' then
    return content_factory_private.deliver_notification_v491(p_payload);
  end if;

  organization_id := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  recipient_id := content_factory_private.require_uuid(
    p_payload, 'recipient_id'
  );
  kind_value := lower(content_factory_private.require_text(
    p_payload, 'kind', 3, 80
  ));
  if kind_value = 'system' then kind_value := 'system_info'; end if;
  severity_value := lower(btrim(coalesce(
    p_payload ->> 'severity', 'info'
  )));
  title_value := content_factory_private.require_text(
    p_payload, 'title', 3, 180
  );
  body_value := content_factory_private.require_text(
    p_payload, 'body', 1, 2000
  );
  deep_link_value := content_factory_private.require_text(
    p_payload, 'deep_link', 3, 600
  );
  entity_type_value := nullif(lower(btrim(coalesce(
    p_payload ->> 'entity_type', ''
  ))), '');
  entity_id_value := nullif(btrim(coalesce(
    p_payload ->> 'entity_id', ''
  )), '');
  properties_value := coalesce(p_payload -> 'properties', '{}'::jsonb);
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  if kind_value !~ '^[a-z][a-z0-9_]{2,79}$'
     or severity_value not in ('info', 'success', 'warning', 'error')
     or length(deep_link_value) not between 3 and 600
     or deep_link_value !~ '^#/[-A-Za-z0-9_./?=&%:]+$'
     or (entity_type_value is not null
       and entity_type_value !~ '^[a-z][a-z0-9_]{1,79}$')
     or (entity_id_value is not null
       and length(entity_id_value) not between 1 and 180)
     or jsonb_typeof(properties_value) <> 'object'
     or length(properties_value::text) > 32768 then
    raise exception using
      errcode = '22023', message = 'system_notification_invalid';
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
    where membership.organization_id = organization_id
      and membership.profile_id = recipient_id
      and membership.status = 'active'
  ) then
    raise exception using
      errcode = 'P0002', message = 'notification_recipient_not_found';
  end if;

  request_payload := jsonb_build_object(
    'recipient_id', recipient_id,
    'kind', kind_value,
    'severity', severity_value,
    'title', title_value,
    'body', body_value,
    'deep_link', deep_link_value,
    'entity_type', entity_type_value,
    'entity_id', entity_id_value,
    'properties', properties_value
  );
  request_hash_value := content_factory_private.json_hash(request_payload);
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('notification:' || recipient_id::text || ':' ||
      idempotency_key_value)
  );
  select notification.* into notification_row
  from content_factory.user_notifications notification
  where notification.organization_id = organization_id
    and notification.recipient_id = recipient_id
    and notification.dedupe_key = idempotency_key_value;
  existing_hash := notification_row.request_hash;
  if existing_hash is not null and existing_hash <> request_hash_value then
    raise exception using
      errcode = '23505', message = 'notification_idempotency_conflict';
  end if;
  if existing_hash is null then
    insert into content_factory.user_notifications (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key, contract_version, event_created_at, expires_at,
      dedupe_version
    ) values (
      organization_id, recipient_id, kind_value, severity_value,
      title_value, body_value, deep_link_value, entity_type_value,
      entity_id_value, properties_value, request_hash_value,
      idempotency_key_value, 1, statement_timestamp(),
      statement_timestamp() + interval '180 days', 0
    )
    returning * into notification_row;
    perform content_factory_private.emit_event(
      organization_id,
      recipient_id,
      'notification_emitted',
      coalesce(entity_type_value, 'notification'),
      coalesce(entity_id_value, notification_row.id::text),
      jsonb_build_object(
        'notification_id', notification_row.id,
        'kind', kind_value,
        'severity', severity_value,
        'recipient_id', recipient_id
      ),
      'notification-emitted:' || idempotency_key_value,
      'system'
    );
  end if;
  result_value := jsonb_build_object(
    'ok', true,
    'notification', jsonb_build_object(
      'id', notification_row.id,
      'organization_id', notification_row.organization_id,
      'recipient_id', notification_row.recipient_id,
      'kind', notification_row.kind,
      'severity', notification_row.severity,
      'title', notification_row.title,
      'body', notification_row.body,
      'deep_link', notification_row.deep_link,
      'entity_type', notification_row.entity_type,
      'entity_id', notification_row.entity_id,
      'read_at', notification_row.read_at,
      'created_at', notification_row.event_created_at,
      'expires_at', notification_row.expires_at,
      'contract_version', notification_row.contract_version
    )
  );
  return result_value;
end;
$function$;


create or replace function
  content_factory_private.notification_route_v491(
    p_source_section text,
    p_action_key text,
    p_project_id uuid,
    p_object_id uuid,
    p_process_id uuid
  )
returns text
language sql
immutable
set search_path = ''
as $function$
  select case p_action_key
    when 'ai.open-decisions' then
      '#/workspace/ai?project_id=' || p_project_id::text || '&tab=decisions'
    when 'process.open' then
      '#/workspace/work?process_id=' || p_process_id::text
    when 'review.open-object' then
      '#/workspace/review' || case when p_project_id is null then '' else
        '?project_id=' || p_project_id::text || '&object_id=' ||
        p_object_id::text end || case when p_project_id is null then
        '?object_id=' || p_object_id::text else '' end
    when 'object.open' then
      '#/workspace/board' || case when p_project_id is null then '' else
        '?project_id=' || p_project_id::text || '&object_id=' ||
        p_object_id::text end || case when p_project_id is null then
        '?object_id=' || p_object_id::text else '' end
    else case p_source_section
      when 'finder' then '#/workspace/board'
      when 'results' then '#/workspace/stats'
      when 'research' then '#/workspace/research'
      when 'ai' then '#/workspace/ai'
      when 'create' then '#/workspace/generation'
      when 'review' then '#/workspace/review'
      when 'publish' then '#/workspace/placement'
      when 'processes' then '#/workspace/work'
      when 'settings' then '#/workspace/team'
      when 'trash' then '#/workspace/trash'
      else '#/workspace/home'
    end
  end
$function$;

create or replace function
  content_factory_private.notification_type_v491(
    p_contract_version smallint,
    p_kind text
  )
returns text
language sql
immutable
set search_path = ''
as $function$
  select case
    when p_kind = 'system' then 'system_info'
    when p_kind in (
      'action_required', 'mention', 'assignment', 'process_complete',
      'warning', 'error', 'access_change', 'system_info'
    ) then p_kind
    else null
  end
$function$;

create or replace function
  content_factory_private.notification_filter_matches_v491(
    p_filter text,
    p_type text,
    p_source_section text,
    p_requires_action boolean,
    p_resolved_at timestamptz,
    p_read_at timestamptz
  )
returns boolean
language sql
immutable
set search_path = ''
as $function$
  select case p_filter
    when 'all' then true
    when 'unread' then p_read_at is null
    when 'action_required' then
      coalesce(p_requires_action, false) and p_resolved_at is null
    when 'mentions' then p_type = 'mention'
    when 'processes' then
      p_source_section = 'processes' or p_type = 'process_complete'
    when 'system' then p_type in ('system_info', 'access_change')
    else false
  end
$function$;

alter table content_factory.user_notifications
  drop constraint if exists user_notifications_severity_check;
alter table content_factory.user_notifications
  add constraint user_notifications_severity_v491_check check (
    severity in ('neutral', 'info', 'success', 'warning', 'danger', 'error')
  );

alter table content_factory.notification_outbox
  drop constraint if exists notification_outbox_severity_check,
  drop constraint if exists notification_outbox_status_check,
  drop constraint if exists notification_outbox_check;
alter table content_factory.notification_outbox
  add constraint notification_outbox_severity_v491_check check (
    severity in ('neutral', 'info', 'success', 'warning', 'danger', 'error')
  ),
  add constraint notification_outbox_status_v491_check check (
    status in ('pending', 'delivering', 'delivered', 'failed', 'expired')
  ),
  add constraint notification_outbox_state_v491_check check (
    (status = 'pending' and lease_token is null
      and lease_expires_at is null and delivered_at is null)
    or (status = 'delivering' and lease_token is not null
      and lease_expires_at is not null and delivered_at is null)
    or (status = 'delivered' and lease_token is null
      and lease_expires_at is null and delivered_at is not null)
    or (status in ('failed', 'expired') and lease_token is null
      and lease_expires_at is null and delivered_at is null
      and last_error_code is not null)
  );

alter table content_factory.user_notifications
  add constraint user_notifications_retention_v491_check check (
    expires_at > event_created_at
    and expires_at <= event_created_at + interval '180 days'
    and (resolved_at is null or (
      resolved_at >= event_created_at and resolved_at <= expires_at
    ))
  ),
  add constraint user_notifications_contract_v491_check check (
    contract_version = 1 or (
      contract_version = 491
      and kind in (
        'action_required', 'mention', 'assignment', 'process_complete',
        'warning', 'error', 'access_change', 'system_info'
      )
      and source_section in (
        'finder', 'results', 'research', 'ai', 'create', 'review',
        'publish', 'processes', 'settings', 'trash', 'system'
      )
      and severity = case kind
        when 'action_required' then 'warning'
        when 'mention' then 'info'
        when 'assignment' then 'info'
        when 'process_complete' then 'success'
        when 'warning' then 'warning'
        when 'error' then 'danger'
        when 'access_change' then 'neutral'
        when 'system_info' then 'neutral'
      end
      and requires_action is not null
      and (kind in ('mention', 'access_change') or requires_action = case kind
        when 'action_required' then true
        when 'assignment' then true
        when 'process_complete' then false
        when 'warning' then true
        when 'error' then true
        when 'system_info' then false
      end)
      and (not requires_action or action_key is not null)
      and (action_key is null or action_key in (
        'ai.open-decisions', 'process.open', 'review.open-object',
        'object.open'
      ))
      and (action_key <> 'ai.open-decisions' or project_id is not null)
      and (action_key <> 'process.open' or process_id is not null)
      and (action_key not in ('review.open-object', 'object.open')
        or object_id is not null)
      and canonical_dedupe_key is not null
      and length(canonical_dedupe_key) between 8 and 180
      and canonical_dedupe_key ~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{7,179}$'
      and dedupe_version between 1 and 2147483647
      and read_state_version = 491
      and content_factory_private.notification_role_ids_valid_v491(
        recipient_role_ids
      )
      and not content_factory_private.notification_payload_sensitive_v491(
        properties
      )
    )
  );

alter table content_factory.notification_outbox
  add constraint notification_outbox_retention_v491_check check (
    expires_at > event_created_at
    and expires_at <= event_created_at + interval '180 days'
    and (resolved_at is null or (
      resolved_at >= event_created_at and resolved_at <= expires_at
    ))
  ),
  add constraint notification_outbox_contract_v491_check check (
    contract_version = 1 or (
      contract_version = 491
      and kind in (
        'action_required', 'mention', 'assignment', 'process_complete',
        'warning', 'error', 'access_change', 'system_info'
      )
      and source_section in (
        'finder', 'results', 'research', 'ai', 'create', 'review',
        'publish', 'processes', 'settings', 'trash', 'system'
      )
      and severity = case kind
        when 'action_required' then 'warning'
        when 'mention' then 'info'
        when 'assignment' then 'info'
        when 'process_complete' then 'success'
        when 'warning' then 'warning'
        when 'error' then 'danger'
        when 'access_change' then 'neutral'
        when 'system_info' then 'neutral'
      end
      and requires_action is not null
      and (kind in ('mention', 'access_change') or requires_action = case kind
        when 'action_required' then true
        when 'assignment' then true
        when 'process_complete' then false
        when 'warning' then true
        when 'error' then true
        when 'system_info' then false
      end)
      and (not requires_action or action_key is not null)
      and (action_key is null or action_key in (
        'ai.open-decisions', 'process.open', 'review.open-object',
        'object.open'
      ))
      and (action_key <> 'ai.open-decisions' or project_id is not null)
      and (action_key <> 'process.open' or process_id is not null)
      and (action_key not in ('review.open-object', 'object.open')
        or object_id is not null)
      and canonical_dedupe_key is not null
      and length(canonical_dedupe_key) between 8 and 180
      and canonical_dedupe_key ~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{7,179}$'
      and dedupe_version between 1 and 2147483647
      and content_factory_private.notification_role_ids_valid_v491(
        recipient_role_ids
      )
      and not content_factory_private.notification_payload_sensitive_v491(
        properties
      )
    )
  );

create unique index if not exists user_notifications_current_dedupe_v491_uq
  on content_factory.user_notifications (
    organization_id, recipient_id, canonical_dedupe_key
  )
  where contract_version = 491;
create index if not exists user_notifications_center_page_v491_idx
  on content_factory.user_notifications (
    organization_id, recipient_id, event_created_at desc, id desc
  )
  where expires_at is not null;
create index if not exists notification_outbox_dedupe_v491_idx
  on content_factory.notification_outbox (
    organization_id, recipient_id, canonical_dedupe_key,
    dedupe_version desc
  )
  where contract_version = 491;

create or replace function content_factory_private.guard_user_notification()
returns trigger
language plpgsql
set search_path = ''
as $function$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000', message = 'notification_deletion_forbidden';
  end if;
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.recipient_id <> old.recipient_id
     or new.contract_version <> old.contract_version
     or new.created_at <> old.created_at
     or new.canonical_dedupe_key is distinct from old.canonical_dedupe_key then
    raise exception using
      errcode = '55000', message = 'notification_identity_immutable';
  end if;

  if old.contract_version = 491 then
    if new.dedupe_version < old.dedupe_version then
      raise exception using
        errcode = '55000', message = 'notification_revision_regression';
    end if;
    if new.dedupe_version = old.dedupe_version then
      if new.kind <> old.kind
         or new.severity <> old.severity
         or new.title <> old.title
         or new.body <> old.body
         or new.deep_link <> old.deep_link
         or new.entity_type is distinct from old.entity_type
         or new.entity_id is distinct from old.entity_id
         or new.properties <> old.properties
         or new.request_hash <> old.request_hash
         or new.dedupe_key <> old.dedupe_key
         or new.event_created_at <> old.event_created_at
         or new.expires_at <> old.expires_at
         or new.resolved_at is distinct from old.resolved_at
         or new.source_section is distinct from old.source_section
         or new.requires_action is distinct from old.requires_action
         or new.action_key is distinct from old.action_key
         or new.project_id is distinct from old.project_id
         or new.object_id is distinct from old.object_id
         or new.process_id is distinct from old.process_id
         or new.recipient_role_ids is distinct from old.recipient_role_ids then
        raise exception using
          errcode = '55000', message = 'notification_revision_immutable';
      end if;
    elsif new.event_created_at < old.event_created_at or new.read_at is not null then
      raise exception using
        errcode = '55000', message = 'notification_revision_invalid';
    end if;
  elsif new.kind <> old.kind
     or new.severity <> old.severity
     or new.title <> old.title
     or new.body <> old.body
     or new.deep_link <> old.deep_link
     or new.entity_type is distinct from old.entity_type
     or new.entity_id is distinct from old.entity_id
     or new.properties <> old.properties
     or new.request_hash <> old.request_hash
     or new.dedupe_key <> old.dedupe_key
     or new.event_created_at <> old.event_created_at
     or new.expires_at <> old.expires_at
     or new.resolved_at is distinct from old.resolved_at
     or new.source_section is distinct from old.source_section
     or new.requires_action is distinct from old.requires_action
     or new.action_key is distinct from old.action_key
     or new.project_id is distinct from old.project_id
     or new.object_id is distinct from old.object_id
     or new.process_id is distinct from old.process_id
     or new.recipient_role_ids is distinct from old.recipient_role_ids
     or new.dedupe_version <> old.dedupe_version
     or new.read_state_version <> old.read_state_version then
    raise exception using
      errcode = '55000', message = 'notification_identity_immutable';
  end if;
  new.updated_at := now();
  return new;
end;
$function$;

create trigger guard_user_notification
before update or delete on content_factory.user_notifications
for each row execute function
  content_factory_private.guard_user_notification();

create or replace function
  content_factory_private.guard_notification_outbox()
returns trigger
language plpgsql
set search_path = ''
as $function$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000', message = 'notification_outbox_deletion_forbidden';
  end if;
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.recipient_id <> old.recipient_id
     or new.kind <> old.kind
     or new.severity <> old.severity
     or new.title <> old.title
     or new.body <> old.body
     or new.deep_link <> old.deep_link
     or new.entity_type <> old.entity_type
     or new.entity_id <> old.entity_id
     or new.properties <> old.properties
     or new.request_hash <> old.request_hash
     or new.dedupe_key <> old.dedupe_key
     or new.created_at <> old.created_at
     or new.contract_version <> old.contract_version
     or new.event_created_at <> old.event_created_at
     or new.expires_at <> old.expires_at
     or new.resolved_at is distinct from old.resolved_at
     or new.source_section is distinct from old.source_section
     or new.requires_action is distinct from old.requires_action
     or new.action_key is distinct from old.action_key
     or new.project_id is distinct from old.project_id
     or new.object_id is distinct from old.object_id
     or new.process_id is distinct from old.process_id
     or new.recipient_role_ids is distinct from old.recipient_role_ids
     or new.canonical_dedupe_key is distinct from old.canonical_dedupe_key
     or new.dedupe_version <> old.dedupe_version then
    raise exception using
      errcode = '55000', message = 'notification_outbox_identity_immutable';
  end if;
  if old.status in ('delivered', 'failed', 'expired')
     and new is distinct from old then
    raise exception using
      errcode = '55000', message = 'notification_outbox_resolved';
  end if;
  if new.status <> old.status and not (
    (old.status = 'pending'
      and new.status in ('delivering', 'delivered', 'expired'))
    or (old.status = 'delivering'
      and new.status in ('pending', 'delivered', 'failed', 'expired'))
  ) then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_status_transition_invalid';
  end if;
  if old.status = 'pending' and new.status = 'delivering' then
    if new.attempt_count <> old.attempt_count + 1 then
      raise exception using
        errcode = '55000', message = 'notification_outbox_attempt_invalid';
    end if;
  elsif new.attempt_count <> old.attempt_count then
    raise exception using
      errcode = '55000', message = 'notification_outbox_attempt_invalid';
  end if;
  new.updated_at := now();
  return new;
end;
$function$;

create trigger guard_notification_outbox
before update or delete on content_factory.notification_outbox
for each row execute function
  content_factory_private.guard_notification_outbox();

-- One canonical producer entrypoint. Role targeting is expanded here into one
-- existing-outbox row per active employee, preserving per-user read state.
-- Producers never write a shared role row with a shared read_at value.
create or replace function
  content_factory_private.enqueue_notification_v491(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  recipient_user_id_value uuid;
  recipient_roles_value text[];
  recipient_role_single text;
  notification_type_value text;
  severity_value text;
  source_section_value text;
  title_value text;
  body_value text;
  requires_action_value boolean;
  action_key_value text;
  project_id_value uuid;
  object_id_value uuid;
  process_id_value uuid;
  canonical_dedupe_key_value text;
  dedupe_version_value bigint;
  event_created_at_value timestamptz;
  expires_at_value timestamptz;
  resolved_at_value timestamptz;
  properties_value jsonb;
  metadata_value jsonb;
  wire_properties_value jsonb;
  deep_link_value text;
  entity_type_value text;
  entity_id_value text;
  delivery_key_value text;
  request_payload jsonb;
  request_hash_value text;
  existing_outbox content_factory.notification_outbox%rowtype;
  outbox_id_value uuid;
  latest_version_value bigint;
  recipient_snapshot_ids uuid[];
  target_count integer;
  enqueued_count integer := 0;
  idempotent_count integer := 0;
  stale_count integer := 0;
  target record;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 49152
     or p_payload - array[
       'organization_id', 'recipient_user_id', 'recipient_role_id',
       'recipient_role_ids', 'type', 'severity', 'source_section', 'title',
       'body', 'requires_action', 'action_key', 'project_id', 'object_id',
       'process_id', 'dedupe_key', 'dedupe_version', 'created_at', 'expires_at',
       'resolved_at', 'properties'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'notification_v491_payload_invalid';
  end if;

  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  if p_payload ? 'recipient_user_id' then
    recipient_user_id_value := content_factory_private.require_uuid(
      p_payload, 'recipient_user_id'
    );
  end if;

  recipient_roles_value := null;
  if p_payload ? 'recipient_role_ids' then
    if jsonb_typeof(p_payload -> 'recipient_role_ids') <> 'array'
       or jsonb_array_length(p_payload -> 'recipient_role_ids')
         not between 1 and 7
       or exists (
         select 1
         from jsonb_array_elements(p_payload -> 'recipient_role_ids') item
         where jsonb_typeof(item) <> 'string'
       ) then
      raise exception using
        errcode = '22023', message = 'notification_recipient_roles_invalid';
    end if;
    select array_agg(role_id order by role_id)
      into recipient_roles_value
    from (
      select distinct lower(btrim(value)) as role_id
      from jsonb_array_elements_text(
        p_payload -> 'recipient_role_ids'
      ) role_value(value)
    ) normalized;
  end if;
  if p_payload ? 'recipient_role_id' then
    recipient_role_single := lower(content_factory_private.require_text(
      p_payload, 'recipient_role_id', 3, 20
    ));
    select array_agg(role_id order by role_id)
      into recipient_roles_value
    from (
      select distinct role_id
      from unnest(
        coalesce(recipient_roles_value, '{}'::text[]) ||
          recipient_role_single
      ) role_value(role_id)
    ) normalized;
  end if;
  if recipient_user_id_value is null and recipient_roles_value is null then
    raise exception using
      errcode = '22023', message = 'notification_recipient_required';
  end if;
  if not content_factory_private.notification_role_ids_valid_v491(
    recipient_roles_value
  ) then
    raise exception using
      errcode = '22023', message = 'notification_recipient_roles_invalid';
  end if;

  notification_type_value := lower(content_factory_private.require_text(
    p_payload, 'type', 3, 40
  ));
  severity_value := lower(content_factory_private.require_text(
    p_payload, 'severity', 3, 20
  ));
  source_section_value := lower(content_factory_private.require_text(
    p_payload, 'source_section', 2, 40
  ));
  title_value := content_factory_private.require_text(
    p_payload, 'title', 1, 140
  );
  body_value := content_factory_private.require_text(
    p_payload, 'body', 1, 500
  );
  canonical_dedupe_key_value := content_factory_private.require_text(
    p_payload, 'dedupe_key', 8, 180
  );

  if notification_type_value = 'system' then
    notification_type_value := 'system_info';
  end if;
  if notification_type_value not in (
    'action_required', 'mention', 'assignment', 'process_complete',
    'warning', 'error', 'access_change', 'system_info'
  ) or source_section_value not in (
    'finder', 'results', 'research', 'ai', 'create', 'review', 'publish',
    'processes', 'settings', 'trash', 'system'
  ) or canonical_dedupe_key_value !~
    '^[A-Za-z0-9][A-Za-z0-9:._/-]{7,179}$' then
    raise exception using
      errcode = '22023', message = 'notification_v491_contract_invalid';
  end if;
  if severity_value <> (case notification_type_value
    when 'action_required' then 'warning'
    when 'mention' then 'info'
    when 'assignment' then 'info'
    when 'process_complete' then 'success'
    when 'warning' then 'warning'
    when 'error' then 'danger'
    when 'access_change' then 'neutral'
    when 'system_info' then 'neutral'
  end) then
    raise exception using
      errcode = '22023', message = 'notification_severity_type_mismatch';
  end if;

  if not p_payload ? 'requires_action'
     or jsonb_typeof(p_payload -> 'requires_action') <> 'boolean' then
    raise exception using
      errcode = '22023', message = 'notification_requires_action_invalid';
  end if;
  requires_action_value := (p_payload ->> 'requires_action')::boolean;
  if notification_type_value not in ('mention', 'access_change')
     and requires_action_value is distinct from (case notification_type_value
       when 'action_required' then true
       when 'assignment' then true
       when 'process_complete' then false
       when 'warning' then true
       when 'error' then true
       when 'system_info' then false
     end) then
    raise exception using
      errcode = '22023', message = 'notification_action_type_mismatch';
  end if;

  action_key_value := nullif(lower(btrim(coalesce(
    p_payload ->> 'action_key', ''
  ))), '');
  if action_key_value is not null and action_key_value not in (
    'ai.open-decisions', 'process.open', 'review.open-object', 'object.open'
  ) then
    raise exception using
      errcode = '22023', message = 'notification_action_key_invalid';
  end if;
  if requires_action_value and action_key_value is null then
    raise exception using
      errcode = '22023', message = 'notification_action_key_required';
  end if;

  begin
    project_id_value := nullif(p_payload ->> 'project_id', '')::uuid;
    object_id_value := nullif(p_payload ->> 'object_id', '')::uuid;
    process_id_value := nullif(p_payload ->> 'process_id', '')::uuid;
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023', message = 'notification_action_target_invalid';
  end;
  if (action_key_value = 'ai.open-decisions' and project_id_value is null)
     or (action_key_value = 'process.open' and process_id_value is null)
     or (action_key_value in ('review.open-object', 'object.open')
       and object_id_value is null) then
    raise exception using
      errcode = '22023', message = 'notification_action_target_required';
  end if;

  if jsonb_typeof(p_payload -> 'dedupe_version') <> 'number'
     or coalesce(p_payload ->> 'dedupe_version', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '22023', message = 'notification_dedupe_version_invalid';
  end if;
  begin
    dedupe_version_value := (p_payload ->> 'dedupe_version')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using
      errcode = '22023', message = 'notification_dedupe_version_invalid';
  end;
  if dedupe_version_value not between 1 and 2147483647 then
    raise exception using
      errcode = '22023', message = 'notification_dedupe_version_invalid';
  end if;

  if not p_payload ? 'created_at'
     or jsonb_typeof(p_payload -> 'created_at') <> 'string'
     or not p_payload ? 'expires_at'
     or jsonb_typeof(p_payload -> 'expires_at') <> 'string' then
    raise exception using
      errcode = '22023', message = 'notification_timestamps_required';
  end if;
  begin
    event_created_at_value := (p_payload ->> 'created_at')::timestamptz;
    expires_at_value := (p_payload ->> 'expires_at')::timestamptz;
    if p_payload ? 'resolved_at' and p_payload -> 'resolved_at' <> 'null'::jsonb then
      if jsonb_typeof(p_payload -> 'resolved_at') <> 'string' then
        raise exception using
          errcode = '22023', message = 'notification_timestamp_invalid';
      end if;
      resolved_at_value := (p_payload ->> 'resolved_at')::timestamptz;
    end if;
  exception
    when invalid_datetime_format or datetime_field_overflow then
      raise exception using
        errcode = '22023', message = 'notification_timestamp_invalid';
  end;
  if event_created_at_value > clock_timestamp() + interval '5 minutes'
     or expires_at_value <= event_created_at_value
     or expires_at_value > event_created_at_value + interval '180 days'
     or (resolved_at_value is not null and (
       resolved_at_value < event_created_at_value
       or resolved_at_value > expires_at_value
     )) then
    raise exception using
      errcode = '22023', message = 'notification_retention_invalid';
  end if;

  properties_value := coalesce(p_payload -> 'properties', '{}'::jsonb);
  if jsonb_typeof(properties_value) <> 'object'
     or length(properties_value::text) > 8192
     or properties_value ? '_notification_v491'
     or content_factory_private.notification_payload_sensitive_v491(
       jsonb_build_object(
         'title', title_value,
         'body', body_value,
         'dedupe_key', canonical_dedupe_key_value,
         'properties', properties_value
       )
     ) then
    raise exception using
      errcode = '22023', message = 'notification_sensitive_payload_rejected';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('notification-v491-targets:' || canonical_dedupe_key_value ||
      ':' || dedupe_version_value::text)
  );
  select array_agg(distinct outbox.recipient_id order by outbox.recipient_id)
    into recipient_snapshot_ids
  from content_factory.notification_outbox outbox
  where outbox.organization_id = organization_id_value
    and outbox.contract_version = 491
    and outbox.canonical_dedupe_key = canonical_dedupe_key_value
    and outbox.dedupe_version = dedupe_version_value;

  if recipient_snapshot_ids is null then
    select array_agg(membership.profile_id order by membership.profile_id)
      into recipient_snapshot_ids
    from content_factory.memberships membership
    join content_factory.organizations organization
      on organization.id = membership.organization_id
     and organization.status = 'active'
    join content_factory.profiles profile
      on profile.id = membership.profile_id
     and profile.status = 'active'
    where membership.organization_id = organization_id_value
      and membership.status = 'active'
      and (
        (recipient_user_id_value is not null
          and membership.profile_id = recipient_user_id_value
          and (recipient_roles_value is null
            or membership.role = any(recipient_roles_value)))
        or (recipient_user_id_value is null
          and membership.role = any(recipient_roles_value))
      );
  end if;
  target_count := coalesce(cardinality(recipient_snapshot_ids), 0);
  if target_count = 0 then
    raise exception using
      errcode = 'P0002', message = 'notification_recipient_not_found';
  end if;
  if target_count > 500 then
    raise exception using
      errcode = '54000', message = 'notification_recipient_limit_exceeded';
  end if;

  deep_link_value := content_factory_private.notification_route_v491(
    source_section_value, action_key_value, project_id_value,
    object_id_value, process_id_value
  );
  entity_type_value := case
    when process_id_value is not null then 'notification_process'
    when object_id_value is not null then 'notification_object'
    when project_id_value is not null then 'notification_project'
    else 'notification_event'
  end;
  entity_id_value := coalesce(
    process_id_value::text,
    object_id_value::text,
    project_id_value::text,
    canonical_dedupe_key_value
  );
  delivery_key_value :=
    'notification-v491:' || encode(extensions.digest(
      canonical_dedupe_key_value, 'sha256'
    ), 'hex') || ':' || dedupe_version_value::text;

  for target in
    select recipient_id as profile_id
    from unnest(recipient_snapshot_ids) recipient(recipient_id)
    order by recipient_id
  loop
    perform pg_advisory_xact_lock(
      hashtext(organization_id_value::text),
      hashtext('notification-v491:' || target.profile_id::text || ':' ||
        canonical_dedupe_key_value)
    );

    select max(version_value) into latest_version_value
    from (
      select outbox.dedupe_version as version_value
      from content_factory.notification_outbox outbox
      where outbox.organization_id = organization_id_value
        and outbox.recipient_id = target.profile_id
        and outbox.contract_version = 491
        and outbox.canonical_dedupe_key = canonical_dedupe_key_value
      union all
      select notification.dedupe_version
      from content_factory.user_notifications notification
      where notification.organization_id = organization_id_value
        and notification.recipient_id = target.profile_id
        and notification.contract_version = 491
        and notification.canonical_dedupe_key = canonical_dedupe_key_value
    ) versions;
    if latest_version_value is not null
       and latest_version_value > dedupe_version_value then
      stale_count := stale_count + 1;
      continue;
    end if;

    metadata_value := jsonb_strip_nulls(jsonb_build_object(
      'contract_version', 491,
      'event_created_at', event_created_at_value,
      'expires_at', expires_at_value,
      'resolved_at', resolved_at_value,
      'source_section', source_section_value,
      'requires_action', requires_action_value,
      'action_key', action_key_value,
      'project_id', project_id_value,
      'object_id', object_id_value,
      'process_id', process_id_value,
      'recipient_role_ids', case when recipient_roles_value is null
        then null else to_jsonb(recipient_roles_value) end,
      'canonical_dedupe_key', canonical_dedupe_key_value,
      'dedupe_version', dedupe_version_value
    ));
    wire_properties_value := properties_value || jsonb_build_object(
      '_notification_v491', metadata_value
    );
    request_payload := jsonb_build_object(
      'recipient_id', target.profile_id,
      'kind', notification_type_value,
      'severity', severity_value,
      'title', title_value,
      'body', body_value,
      'deep_link', deep_link_value,
      'entity_type', entity_type_value,
      'entity_id', entity_id_value,
      'properties', wire_properties_value
    );
    request_hash_value := content_factory_private.json_hash(request_payload);

    select outbox.* into existing_outbox
    from content_factory.notification_outbox outbox
    where outbox.organization_id = organization_id_value
      and outbox.recipient_id = target.profile_id
      and outbox.dedupe_key = delivery_key_value;
    if existing_outbox.id is not null then
      if existing_outbox.request_hash <> request_hash_value then
        raise exception using
          errcode = '23505', message = 'notification_idempotency_conflict';
      end if;
      idempotent_count := idempotent_count + 1;
      continue;
    end if;

    insert into content_factory.notification_outbox (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key, contract_version, event_created_at, expires_at,
      resolved_at, source_section, requires_action, action_key, project_id,
      object_id, process_id, recipient_role_ids, canonical_dedupe_key,
      dedupe_version
    ) values (
      organization_id_value, target.profile_id, notification_type_value,
      severity_value, title_value, body_value, deep_link_value,
      entity_type_value, entity_id_value, wire_properties_value,
      request_hash_value, delivery_key_value, 491, event_created_at_value,
      expires_at_value, resolved_at_value, source_section_value,
      requires_action_value, action_key_value, project_id_value,
      object_id_value, process_id_value, recipient_roles_value,
      canonical_dedupe_key_value, dedupe_version_value
    )
    returning id into outbox_id_value;
    enqueued_count := enqueued_count + 1;
  end loop;

  return jsonb_build_object(
    'ok', true,
    'contract_version', 491,
    'organization_id', organization_id_value,
    'dedupe_key', canonical_dedupe_key_value,
    'dedupe_version', dedupe_version_value,
    'recipient_count', target_count,
    'enqueued_count', enqueued_count,
    'idempotent_count', idempotent_count,
    'stale_count', stale_count
  );
end;
$function$;

-- Recipient-scoped, live server projection. Legacy direct-recipient rows remain
-- available and are explicitly tagged contract_version=1. Unknown legacy kind
-- is returned as legacy_kind with type=null rather than inventing a canonical
-- role/source/action target.
create or replace function public.creator_notification_center(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  filter_value text := 'all';
  page_size integer := 50;
  cursor_created_at timestamptz;
  cursor_id uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 8192
     or p_payload - array[
       'organization_id', 'filter', 'page_size', 'cursor'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'notification_center_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, false, null
  );
  filter_value := lower(btrim(coalesce(p_payload ->> 'filter', 'all')));
  if filter_value not in (
    'all', 'unread', 'action_required', 'mentions', 'processes', 'system'
  ) then
    raise exception using
      errcode = '22023', message = 'notification_center_filter_invalid';
  end if;
  if p_payload ? 'page_size' then
    if jsonb_typeof(p_payload -> 'page_size') <> 'number'
       or coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'notification_center_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023', message = 'notification_center_page_size_invalid';
    end;
  end if;
  if page_size not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'notification_center_page_size_invalid';
  end if;
  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object'
       or (p_payload -> 'cursor') - array[
         'created_at', 'id'
       ]::text[] <> '{}'::jsonb
       or not ((p_payload -> 'cursor') ?& array['created_at', 'id']) then
      raise exception using
        errcode = '22023', message = 'notification_center_cursor_invalid';
    end if;
    begin
      cursor_created_at :=
        (p_payload #>> '{cursor,created_at}')::timestamptz;
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation or invalid_datetime_format
        or datetime_field_overflow then
        raise exception using
          errcode = '22023', message = 'notification_center_cursor_invalid';
    end;
    if cursor_created_at is null or cursor_id is null then
      raise exception using
        errcode = '22023', message = 'notification_center_cursor_invalid';
    end if;
  end if;

  with scoped as materialized (
    select
      notification.*,
      content_factory_private.notification_type_v491(
        notification.contract_version,
        notification.kind
      ) as center_type,
      case notification.severity
        when 'error' then 'danger'
        else notification.severity
      end as center_severity
    from content_factory.user_notifications notification
    join content_factory.memberships membership
      on membership.organization_id = notification.organization_id
     and membership.profile_id = user_id
     and membership.status = 'active'
    join content_factory.organizations organization
      on organization.id = notification.organization_id
     and organization.status = 'active'
    join content_factory.profiles profile
      on profile.id = user_id
     and profile.status = 'active'
    where notification.organization_id = organization_id
      and notification.recipient_id = user_id
      and notification.expires_at > now()
      and (notification.recipient_role_ids is null
        or membership.role = any(notification.recipient_role_ids))
  ),
  filtered as materialized (
    select notification.*
    from scoped notification
    where content_factory_private.notification_filter_matches_v491(
      filter_value,
      notification.center_type,
      notification.source_section,
      notification.requires_action,
      notification.resolved_at,
      notification.read_at
    )
  ),
  candidates as materialized (
    select notification.*
    from filtered notification
    where cursor_created_at is null
      or (notification.event_created_at, notification.id)
        < (cursor_created_at, cursor_id)
    order by notification.event_created_at desc, notification.id desc
    limit page_size + 1
  ),
  page as materialized (
    select notification.*
    from candidates notification
    order by notification.event_created_at desc, notification.id desc
    limit page_size
  ),
  last_item as (
    select notification.event_created_at, notification.id
    from page notification
    order by notification.event_created_at asc, notification.id asc
    limit 1
  )
  select jsonb_build_object(
    'organization_id', organization_id,
    'recipient_user_id', user_id,
    'active_role_ids', jsonb_build_array(actor_role),
    'filter', filter_value,
    'counts', jsonb_build_object(
      'all', (select count(*) from scoped),
      'unread', (select count(*) from scoped where read_at is null),
      'action_required', (
        select count(*) from scoped notification
        where content_factory_private.notification_filter_matches_v491(
          'action_required', notification.center_type,
          notification.source_section, notification.requires_action,
          notification.resolved_at, notification.read_at
        )
      ),
      'mentions', (
        select count(*) from scoped where center_type = 'mention'
      ),
      'processes', (
        select count(*) from scoped notification
        where content_factory_private.notification_filter_matches_v491(
          'processes', notification.center_type,
          notification.source_section, notification.requires_action,
          notification.resolved_at, notification.read_at
        )
      ),
      'system', (
        select count(*) from scoped
        where center_type in ('system_info', 'access_change')
      )
    ),
    'items', (
      select coalesce(jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
        'notification_id', notification.id,
        'organization_id', notification.organization_id,
        'recipient_user_id', notification.recipient_id,
        'recipient_role_ids', notification.recipient_role_ids,
        'contract_version', notification.contract_version,
        'type', notification.center_type,
        'legacy_kind', case when notification.contract_version = 1
          then notification.kind else null end,
        'severity', notification.center_severity,
        'source_section', notification.source_section,
        'title', notification.title,
        'body', notification.body,
        'created_at', notification.event_created_at,
        'expires_at', notification.expires_at,
        'resolved_at', notification.resolved_at,
        'requires_action', notification.requires_action,
        'project_id', notification.project_id,
        'object_id', notification.object_id,
        'process_id', notification.process_id,
        'action_key', notification.action_key,
        'dedupe_key', coalesce(
          notification.canonical_dedupe_key,
          notification.dedupe_key
        ),
        'dedupe_version', notification.dedupe_version,
        'read_state_version', notification.read_state_version,
        'read_at', notification.read_at
      )) order by notification.event_created_at desc, notification.id desc),
        '[]'::jsonb)
      from page notification
    ),
    'next_cursor', case
      when (select count(*) from candidates) > page_size then (
        select jsonb_build_object(
          'created_at', notification.event_created_at,
          'id', notification.id
        )
        from last_item notification
      ) else null
    end,
    '_meta', jsonb_build_object(
      'contract_version', '4.9.1',
      'read_state_version', 'contentengine-notification-read-v4.9.1',
      'page_size', page_size,
      'cap', 100,
      'cursor_mode', 'keyset_event_created_at_id',
      'expired_excluded', true,
      'legacy_unknown_type_is_null', true
    )
  ) into result_value;
  return result_value;
end;
$function$;

-- Explicitly read only the IDs visible in the caller's current server filter.
-- There is no all_unread switch and no inference from a partial client page.
create or replace function
  public.creator_mark_visible_notifications_read(
    p_payload jsonb default '{}'::jsonb
  )
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  actor_role text;
  filter_value text;
  notification_ids uuid[];
  idempotency_key_value text;
  scoped_idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  visible_count integer;
  changed_count integer;
  remaining_unread integer;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 32768
     or p_payload - array[
       'organization_id', 'filter', 'notification_ids', 'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or jsonb_typeof(p_payload -> 'notification_ids') <> 'array'
     or jsonb_array_length(p_payload -> 'notification_ids')
       not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'notification_visible_mark_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, false, null
  );
  filter_value := lower(content_factory_private.require_text(
    p_payload, 'filter', 3, 24
  ));
  if filter_value not in (
    'all', 'unread', 'action_required', 'mentions', 'processes', 'system'
  ) then
    raise exception using
      errcode = '22023', message = 'notification_center_filter_invalid';
  end if;
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  scoped_idempotency_key_value := left(
    user_id::text || ':' || idempotency_key_value, 180
  );
  begin
    select array_agg(distinct element.value::uuid order by element.value::uuid)
      into notification_ids
    from jsonb_array_elements_text(
      p_payload -> 'notification_ids'
    ) element(value);
  exception when invalid_text_representation then
    raise exception using
      errcode = '22023', message = 'notification_id_invalid';
  end;
  if cardinality(notification_ids) <>
     jsonb_array_length(p_payload -> 'notification_ids') then
    raise exception using
      errcode = '22023', message = 'notification_id_duplicate';
  end if;

  request_payload := jsonb_build_object(
    'filter', filter_value,
    'notification_ids', to_jsonb(notification_ids),
    'read_state_version', 'contentengine-notification-read-v4.9.1'
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_mark_visible_notifications_read',
    scoped_idempotency_key_value,
    request_payload
  );
  if replay is not null then return replay; end if;

  perform 1
  from content_factory.user_notifications notification
  join content_factory.memberships membership
    on membership.organization_id = notification.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where notification.organization_id = organization_id
    and notification.recipient_id = user_id
    and notification.id = any(notification_ids)
  for update of notification;

  select count(*)::integer into visible_count
  from content_factory.user_notifications notification
  join content_factory.memberships membership
    on membership.organization_id = notification.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where notification.organization_id = organization_id
    and notification.recipient_id = user_id
    and notification.id = any(notification_ids)
    and notification.expires_at > now()
    and (notification.recipient_role_ids is null
      or membership.role = any(notification.recipient_role_ids))
    and content_factory_private.notification_filter_matches_v491(
      filter_value,
      content_factory_private.notification_type_v491(
        notification.contract_version, notification.kind
      ),
      notification.source_section,
      notification.requires_action,
      notification.resolved_at,
      notification.read_at
    );
  if visible_count <> cardinality(notification_ids) then
    raise exception using
      errcode = '42501', message = 'notification_visible_scope_denied';
  end if;

  update content_factory.user_notifications notification
  set read_at = now()
  from content_factory.memberships membership
  where notification.organization_id = organization_id
    and notification.recipient_id = user_id
    and notification.id = any(notification_ids)
    and notification.read_at is null
    and notification.expires_at > now()
    and membership.organization_id = notification.organization_id
    and membership.profile_id = user_id
    and membership.status = 'active'
    and (notification.recipient_role_ids is null
      or membership.role = any(notification.recipient_role_ids))
    and content_factory_private.notification_filter_matches_v491(
      filter_value,
      content_factory_private.notification_type_v491(
        notification.contract_version, notification.kind
      ),
      notification.source_section,
      notification.requires_action,
      notification.resolved_at,
      notification.read_at
    );
  get diagnostics changed_count = row_count;

  select count(*)::integer into remaining_unread
  from content_factory.user_notifications notification
  join content_factory.memberships membership
    on membership.organization_id = notification.organization_id
   and membership.profile_id = user_id
   and membership.status = 'active'
  where notification.organization_id = organization_id
    and notification.recipient_id = user_id
    and notification.read_at is null
    and notification.expires_at > now()
    and (notification.recipient_role_ids is null
      or membership.role = any(notification.recipient_role_ids));

  result_value := jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'recipient_user_id', user_id,
    'active_role_ids', jsonb_build_array(actor_role),
    'scope', 'visible_filter',
    'filter', filter_value,
    'updated_count', changed_count,
    'remaining_unread', remaining_unread,
    'notification_ids', to_jsonb(notification_ids),
    'read_state_version', 'contentengine-notification-read-v4.9.1'
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'notifications_marked_read',
    'notification',
    null,
    jsonb_build_object(
      'notification_count', cardinality(notification_ids),
      'scope', 'visible_filter',
      'filter', filter_value,
      'changed_count', changed_count
    ),
    left(
      'notification-visible-mark:' || scoped_idempotency_key_value,
      180
    )
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_mark_visible_notifications_read',
    scoped_idempotency_key_value,
    request_payload,
    result_value
  );
end;
$function$;

-- Preserve table RLS and grants. Only narrow SECURITY DEFINER projections are
-- browser-callable; durable delivery remains service-only; producer helpers
-- remain private even from service_role PostgREST calls.
revoke all on content_factory.user_notifications
  from public, anon, authenticated;
revoke all on content_factory.notification_outbox
  from public, anon, authenticated;
grant all on content_factory.user_notifications to service_role;
grant all on content_factory.notification_outbox to service_role;

revoke all on function public.creator_notification_center(jsonb)
  from public, anon;
revoke all on function
  public.creator_mark_visible_notifications_read(jsonb)
  from public, anon;
grant execute on function public.creator_notification_center(jsonb)
  to authenticated;
grant execute on function
  public.creator_mark_visible_notifications_read(jsonb)
  to authenticated;

revoke all on function public.system_emit_notification(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_claim_notification_outbox(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_complete_notification_outbox(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_notification_outbox_health(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_emit_notification(jsonb)
  to service_role;
grant execute on function public.system_claim_notification_outbox(jsonb)
  to service_role;
grant execute on function public.system_complete_notification_outbox(jsonb)
  to service_role;
grant execute on function public.system_notification_outbox_health(jsonb)
  to service_role;

revoke all on function
  content_factory_private.notification_role_ids_valid_v491(text[])
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.notification_payload_sensitive_v491(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.notification_route_v491(text, text, uuid, uuid, uuid)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.notification_type_v491(smallint, text)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.notification_filter_matches_v491(
    text, text, text, boolean, timestamptz, timestamptz
  )
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.enqueue_notification_v491(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.deliver_notification_v491(jsonb)
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.guard_user_notification()
  from public, anon, authenticated, service_role;
revoke all on function content_factory_private.guard_notification_outbox()
  from public, anon, authenticated, service_role;

comment on function
  content_factory_private.enqueue_notification_v491(jsonb) is
  'Single canonical v4.9.1 producer entrypoint. Expands active role recipients into the existing durable outbox; never creates a shared-read role row.';
comment on function public.creator_notification_center(jsonb) is
  'Live organization/user/active-role scoped Notification Center projection. Expired events are excluded before counts and pagination.';
comment on function
  public.creator_mark_visible_notifications_read(jsonb) is
  'Marks only exact recipient-scoped IDs admitted by the supplied visible filter; never performs global all_unread mutation.';

commit;
