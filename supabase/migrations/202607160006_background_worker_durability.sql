begin;

-- Terminal work and user notification delivery are separate durable facts.
-- The outbox is written by database triggers in the same transaction that
-- makes a generation, research run, or review terminal. A transient Edge/RPC
-- failure therefore cannot erase the obligation to notify the recipient.
create table if not exists content_factory.notification_outbox (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    recipient_id uuid not null,
    kind text not null check (kind ~ '^[a-z][a-z0-9_]{2,79}$'),
    severity text not null
      check (severity in ('info', 'success', 'warning', 'error')),
    title text not null check (length(btrim(title)) between 3 and 180),
    body text not null check (length(btrim(body)) between 1 and 2000),
    deep_link text not null check (
      length(deep_link) between 3 and 600
      and deep_link ~ '^#/[-A-Za-z0-9_./?=&%:]+$'
    ),
    entity_type text not null
      check (entity_type ~ '^[a-z][a-z0-9_]{1,79}$'),
    entity_id text not null
      check (length(btrim(entity_id)) between 1 and 180),
    properties jsonb not null default '{}'::jsonb check (
      jsonb_typeof(properties) = 'object'
      and length(properties::text) <= 32768
    ),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    dedupe_key text not null check (length(dedupe_key) between 8 and 180),
    status text not null default 'pending'
      check (status in ('pending', 'delivering', 'delivered', 'failed')),
    attempt_count integer not null default 0
      check (attempt_count between 0 and 1000),
    next_attempt_at timestamptz not null default now(),
    lease_token uuid,
    lease_expires_at timestamptz,
    last_error_code text check (
      last_error_code is null
      or last_error_code ~ '^[a-z][a-z0-9_]{2,99}$'
    ),
    delivered_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, recipient_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, recipient_id, dedupe_key),
    unique (organization_id, id),
    check (
      (status = 'pending'
        and lease_token is null
        and lease_expires_at is null
        and delivered_at is null)
      or (status = 'delivering'
        and lease_token is not null
        and lease_expires_at is not null
        and delivered_at is null)
      or (status = 'delivered'
        and lease_token is null
        and lease_expires_at is null
        and delivered_at is not null)
      or (status = 'failed'
        and lease_token is null
        and lease_expires_at is null
        and delivered_at is null
        and last_error_code is not null)
    )
);

create index if not exists notification_outbox_due_idx
  on content_factory.notification_outbox
  (next_attempt_at, created_at, id)
  where status = 'pending';
create index if not exists notification_outbox_lease_idx
  on content_factory.notification_outbox
  (lease_expires_at, id)
  where status = 'delivering';
create index if not exists notification_outbox_unresolved_idx
  on content_factory.notification_outbox
  (organization_id, status, created_at, id)
  where status <> 'delivered';

alter table content_factory.notification_outbox enable row level security;
revoke all on content_factory.notification_outbox
  from public, anon, authenticated;
grant all on content_factory.notification_outbox to service_role;

create or replace function
  content_factory_private.guard_notification_outbox()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_deletion_forbidden';
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
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_identity_immutable';
  end if;
  if old.status = 'delivered' and new is distinct from old then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_delivered';
  end if;
  if old.status = 'failed' and new is distinct from old then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_failed';
  end if;
  if new.status <> old.status and not (
    (old.status = 'pending' and new.status in ('delivering', 'delivered'))
    or (
      old.status = 'delivering'
      and new.status in ('pending', 'delivered', 'failed')
    )
  ) then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_status_transition_invalid';
  end if;
  if old.status = 'pending' and new.status = 'delivering' then
    if new.attempt_count <> old.attempt_count + 1 then
      raise exception using
        errcode = '55000',
        message = 'notification_outbox_attempt_invalid';
    end if;
  elsif new.attempt_count <> old.attempt_count then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_attempt_invalid';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists guard_notification_outbox
  on content_factory.notification_outbox;
create trigger guard_notification_outbox
before update or delete on content_factory.notification_outbox
for each row execute function
  content_factory_private.guard_notification_outbox();

create or replace function
  content_factory_private.enqueue_terminal_notification()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  recipient_id_value uuid;
  work_kind text;
  status_value text;
  severity_value text;
  title_value text;
  body_value text;
  deep_link_value text;
  entity_type_value text;
  entity_id_value text;
  properties_value jsonb;
  dedupe_key_value text;
  request_hash_value text;
begin
  if tg_op = 'UPDATE' and new.status is not distinct from old.status then
    return new;
  end if;

  if tg_table_name = 'generation_jobs' then
    if new.mode <> 'real'
       or new.provider <> 'runway'
       or new.status not in ('succeeded', 'failed', 'cancelled') then
      return new;
    end if;
    organization_id_value := new.organization_id;
    recipient_id_value := new.requested_by;
    work_kind := 'generation';
    status_value := new.status;
    deep_link_value := '#/workspace/generation';
    entity_type_value := 'generation_job';
    if status_value = 'failed' then
      severity_value := 'error';
      title_value := 'Генерация завершилась с ошибкой';
      body_value :=
        'Фоновая проверка зафиксировала ошибку Runway. Новый платный запуск автоматически не выполнялся.';
    elsif status_value = 'cancelled' then
      severity_value := 'warning';
      title_value := 'Генерация отменена';
      body_value :=
        'Задача генерации отменена без повторного платного запуска.';
    else
      severity_value := 'success';
      title_value := 'Видео готово';
      body_value :=
        'Runway завершил видео, файл проверен и сохранён в защищённых материалах.';
    end if;
  elsif tg_table_name = 'product_research_runs' then
    if new.status not in ('completed', 'failed', 'cancelled') then
      return new;
    end if;
    organization_id_value := new.organization_id;
    recipient_id_value := new.created_by;
    work_kind := 'research';
    status_value := new.status;
    deep_link_value := '#/workspace/tasks';
    entity_type_value := 'product_research';
    if status_value = 'failed' then
      severity_value := 'error';
      title_value := 'Анализ товара завершился с ошибкой';
      body_value :=
        'Исследование безопасно закрыто без автоматического повтора платного запроса.';
    elsif status_value = 'cancelled' then
      severity_value := 'warning';
      title_value := 'Анализ товара отменён';
      body_value :=
        'Исследование отменено; при необходимости создайте новый запуск вручную.';
    else
      severity_value := 'success';
      title_value := 'Анализ товара готов';
      body_value :=
        'Черновик ТЗ, источники и прогноз готовы к проверке человеком.';
    end if;
  elsif tg_table_name = 'content_review_runs' then
    if new.status not in ('completed', 'failed', 'cancelled') then
      return new;
    end if;
    organization_id_value := new.organization_id;
    recipient_id_value := new.requested_by;
    work_kind := 'review';
    status_value := new.status;
    deep_link_value := '#/workspace/review';
    entity_type_value := 'content_review';
    if status_value = 'failed' then
      severity_value := 'error';
      title_value := 'Проверка контента завершилась с ошибкой';
      body_value :=
        'Проверка безопасно закрыта без автоматического повтора платного запроса.';
    elsif status_value = 'cancelled' then
      severity_value := 'warning';
      title_value := 'Проверка контента отменена';
      body_value :=
        'Проверка отменена; исходный файл не публиковался автоматически.';
    else
      severity_value := 'success';
      title_value := 'Проверка контента готова';
      body_value :=
        'Оценка качества, риски и рекомендации доступны в рабочем пространстве.';
    end if;
  else
    return new;
  end if;

  entity_id_value := new.id::text;
  properties_value := jsonb_build_object(
    'source', 'creator_background_worker',
    'status', status_value
  );
  dedupe_key_value := left(
    'background-worker:' || work_kind || ':' ||
      entity_id_value || ':' || status_value,
    180
  );
  request_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'recipient_id', recipient_id_value,
      'kind', 'background_' || work_kind || '_' || status_value,
      'severity', severity_value,
      'title', title_value,
      'body', body_value,
      'deep_link', deep_link_value,
      'entity_type', entity_type_value,
      'entity_id', entity_id_value,
      'properties', properties_value
    )
  );

  insert into content_factory.notification_outbox (
    organization_id, recipient_id, kind, severity, title, body,
    deep_link, entity_type, entity_id, properties, request_hash,
    dedupe_key
  ) values (
    organization_id_value, recipient_id_value,
    'background_' || work_kind || '_' || status_value,
    severity_value, title_value, body_value, deep_link_value,
    entity_type_value, entity_id_value, properties_value,
    request_hash_value, dedupe_key_value
  )
  on conflict (organization_id, recipient_id, dedupe_key) do nothing;

  return new;
end;
$$;

drop trigger if exists enqueue_generation_terminal_notification
  on content_factory.generation_jobs;
create trigger enqueue_generation_terminal_notification
after insert or update on content_factory.generation_jobs
for each row execute function
  content_factory_private.enqueue_terminal_notification();

drop trigger if exists enqueue_research_terminal_notification
  on content_factory.product_research_runs;
create trigger enqueue_research_terminal_notification
after insert or update on content_factory.product_research_runs
for each row execute function
  content_factory_private.enqueue_terminal_notification();

drop trigger if exists enqueue_review_terminal_notification
  on content_factory.content_review_runs;
create trigger enqueue_review_terminal_notification
after insert or update on content_factory.content_review_runs
for each row execute function
  content_factory_private.enqueue_terminal_notification();

-- Close expired paid AI leases atomically. Research and review calls are made
-- terminal instead of being requeued: an uncertain provider POST must never
-- be repeated automatically. Generation rows are deliberately untouched.
create or replace function public.system_reconcile_background_leases(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  limit_value integer := 50;
  research_count integer := 0;
  review_count integer := 0;
  timeout_message text :=
    'Processing lease expired safely. Start a new run manually after review.';
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 1024
     or p_payload - array['limit']::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'background_reconcile_payload_invalid';
  end if;
  if p_payload ? 'limit' then
    begin
      limit_value := (p_payload ->> 'limit')::integer;
    exception when invalid_text_representation or numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'background_reconcile_limit_invalid';
    end;
  end if;
  if limit_value not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'background_reconcile_limit_invalid';
  end if;

  with expired as (
    select run.id
    from content_factory.product_research_runs run
    where run.status = 'processing'
      and run.lease_expires_at <= now()
    order by run.lease_expires_at, run.id
    for update skip locked
    limit limit_value
  )
  update content_factory.product_research_runs run
  set status = 'failed',
      error_code = 'processing_lease_expired',
      error_message = timeout_message,
      completion_hash = content_factory_private.json_hash(
        jsonb_build_object(
          'status', 'failed',
          'error_code', 'processing_lease_expired',
          'error_message', timeout_message
        )
      )
  from expired
  where run.id = expired.id
    and run.status = 'processing'
    and run.lease_expires_at <= now();
  get diagnostics research_count = row_count;

  with expired as (
    select review.id
    from content_factory.content_review_runs review
    where review.status = 'processing'
      and review.lease_expires_at <= now()
    order by review.lease_expires_at, review.id
    for update skip locked
    limit limit_value
  )
  update content_factory.content_review_runs review
  set status = 'failed',
      error_code = 'processing_lease_expired',
      error_message = timeout_message,
      completion_hash = content_factory_private.json_hash(
        jsonb_build_object(
          'status', 'failed',
          'error_code', 'processing_lease_expired',
          'error_message', timeout_message
        )
      )
  from expired
  where review.id = expired.id
    and review.status = 'processing'
    and review.lease_expires_at <= now();
  get diagnostics review_count = row_count;

  return jsonb_build_object(
    'ok', true,
    'expired', jsonb_build_object(
      'research', research_count,
      'review', review_count
    )
  );
end;
$$;

create or replace function public.system_claim_notification_outbox(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  limit_value integer := 12;
  items_value jsonb := '[]'::jsonb;
  recovered_count integer := 0;
  observed_count integer := 0;
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

  -- An earlier attempt may have committed system_emit_notification and lost
  -- the RPC response. Observing the same dedupe key proves delivery and avoids
  -- treating that ambiguous response as a new notification.
  update content_factory.notification_outbox outbox
  set status = 'delivered',
      delivered_at = notification.created_at,
      lease_token = null,
      lease_expires_at = null,
      last_error_code = null
  from content_factory.user_notifications notification
  where outbox.status in ('pending', 'delivering')
    and notification.organization_id = outbox.organization_id
    and notification.recipient_id = outbox.recipient_id
    and notification.dedupe_key = outbox.dedupe_key;
  get diagnostics observed_count = row_count;

  update content_factory.notification_outbox outbox
  set status = 'pending',
      lease_token = null,
      lease_expires_at = null,
      next_attempt_at = now(),
      last_error_code = coalesce(
        outbox.last_error_code,
        'delivery_lease_expired'
      )
  where outbox.status = 'delivering'
    and outbox.lease_expires_at <= now();
  get diagnostics recovered_count = row_count;

  with candidates as (
    select outbox.id
    from content_factory.notification_outbox outbox
    where outbox.status = 'pending'
      and outbox.next_attempt_at <= now()
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
  ) order by claimed.next_attempt_at, claimed.created_at, claimed.id), '[]'::jsonb)
  into items_value
  from claimed;

  select count(*)::integer into unresolved_count
  from content_factory.notification_outbox outbox
  where outbox.status <> 'delivered';

  return jsonb_build_object(
    'ok', true,
    'items', items_value,
    'recovered_leases', recovered_count,
    'observed_deliveries', observed_count,
    'unresolved', unresolved_count
  );
end;
$$;

create or replace function public.system_complete_notification_outbox(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
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
  if (
    delivered_value
    and error_code_value is not null
  ) or (
    not delivered_value
    and (
      error_code_value is null
      or error_code_value !~ '^[a-z][a-z0-9_]{2,99}$'
    )
  ) then
    raise exception using
      errcode = '22023',
      message = 'notification_outbox_completion_invalid';
  end if;

  select outbox.* into outbox_row
  from content_factory.notification_outbox outbox
  where outbox.id = outbox_id_value
  for update;
  if outbox_row.id is null then
    raise exception using
      errcode = '22023',
      message = 'notification_outbox_not_found';
  end if;
  if outbox_row.status in ('delivered', 'failed') then
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
      errcode = '55000',
      message = 'notification_outbox_lease_mismatch';
  end if;
  if outbox_row.lease_expires_at <= now() then
    raise exception using
      errcode = '55000',
      message = 'notification_outbox_lease_expired';
  end if;

  if delivered_value then
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
        next_attempt_at = now() + make_interval(secs => retry_seconds),
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
$$;

create or replace function public.system_notification_outbox_health(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  pending_count integer;
  delivering_count integer;
  failed_count integer;
  due_count integer;
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
    )::integer
  into pending_count, delivering_count, failed_count, due_count
  from content_factory.notification_outbox outbox;

  return jsonb_build_object(
    'ok', true,
    'unresolved', pending_count + delivering_count + failed_count,
    'pending', pending_count,
    'delivering', delivering_count,
    'failed', failed_count,
    'due', due_count
  );
end;
$$;

-- Backfill all terminal work that does not yet have a transactional outbox
-- row. Existing user notifications are observed as delivered by the claim RPC.
insert into content_factory.notification_outbox (
  organization_id, recipient_id, kind, severity, title, body,
  deep_link, entity_type, entity_id, properties, request_hash, dedupe_key
)
select
  job.organization_id,
  job.requested_by,
  'background_generation_' || job.status,
  case job.status
    when 'failed' then 'error'
    when 'cancelled' then 'warning'
    else 'success'
  end,
  case job.status
    when 'failed' then 'Генерация завершилась с ошибкой'
    when 'cancelled' then 'Генерация отменена'
    else 'Видео готово'
  end,
  case job.status
    when 'failed' then
      'Фоновая проверка зафиксировала ошибку Runway. Новый платный запуск автоматически не выполнялся.'
    when 'cancelled' then
      'Задача генерации отменена без повторного платного запуска.'
    else
      'Runway завершил видео, файл проверен и сохранён в защищённых материалах.'
  end,
  '#/workspace/generation',
  'generation_job',
  job.id::text,
  jsonb_build_object(
    'source', 'creator_background_worker',
    'status', job.status
  ),
  content_factory_private.json_hash(jsonb_build_object(
    'recipient_id', job.requested_by,
    'kind', 'background_generation_' || job.status,
    'severity', case job.status
      when 'failed' then 'error'
      when 'cancelled' then 'warning'
      else 'success'
    end,
    'title', case job.status
      when 'failed' then 'Генерация завершилась с ошибкой'
      when 'cancelled' then 'Генерация отменена'
      else 'Видео готово'
    end,
    'body', case job.status
      when 'failed' then
        'Фоновая проверка зафиксировала ошибку Runway. Новый платный запуск автоматически не выполнялся.'
      when 'cancelled' then
        'Задача генерации отменена без повторного платного запуска.'
      else
        'Runway завершил видео, файл проверен и сохранён в защищённых материалах.'
    end,
    'deep_link', '#/workspace/generation',
    'entity_type', 'generation_job',
    'entity_id', job.id::text,
    'properties', jsonb_build_object(
      'source', 'creator_background_worker',
      'status', job.status
    )
  )),
  left(
    'background-worker:generation:' || job.id::text || ':' || job.status,
    180
  )
from content_factory.generation_jobs job
where job.mode = 'real'
  and job.provider = 'runway'
  and job.status in ('succeeded', 'failed', 'cancelled')
on conflict (organization_id, recipient_id, dedupe_key) do nothing;

insert into content_factory.notification_outbox (
  organization_id, recipient_id, kind, severity, title, body,
  deep_link, entity_type, entity_id, properties, request_hash, dedupe_key
)
select
  run.organization_id,
  run.created_by,
  'background_research_' || run.status,
  case run.status
    when 'failed' then 'error'
    when 'cancelled' then 'warning'
    else 'success'
  end,
  case run.status
    when 'failed' then 'Анализ товара завершился с ошибкой'
    when 'cancelled' then 'Анализ товара отменён'
    else 'Анализ товара готов'
  end,
  case run.status
    when 'failed' then
      'Исследование безопасно закрыто без автоматического повтора платного запроса.'
    when 'cancelled' then
      'Исследование отменено; при необходимости создайте новый запуск вручную.'
    else
      'Черновик ТЗ, источники и прогноз готовы к проверке человеком.'
  end,
  '#/workspace/tasks',
  'product_research',
  run.id::text,
  jsonb_build_object(
    'source', 'creator_background_worker',
    'status', run.status
  ),
  content_factory_private.json_hash(jsonb_build_object(
    'recipient_id', run.created_by,
    'kind', 'background_research_' || run.status,
    'severity', case run.status
      when 'failed' then 'error'
      when 'cancelled' then 'warning'
      else 'success'
    end,
    'title', case run.status
      when 'failed' then 'Анализ товара завершился с ошибкой'
      when 'cancelled' then 'Анализ товара отменён'
      else 'Анализ товара готов'
    end,
    'body', case run.status
      when 'failed' then
        'Исследование безопасно закрыто без автоматического повтора платного запроса.'
      when 'cancelled' then
        'Исследование отменено; при необходимости создайте новый запуск вручную.'
      else
        'Черновик ТЗ, источники и прогноз готовы к проверке человеком.'
    end,
    'deep_link', '#/workspace/tasks',
    'entity_type', 'product_research',
    'entity_id', run.id::text,
    'properties', jsonb_build_object(
      'source', 'creator_background_worker',
      'status', run.status
    )
  )),
  left(
    'background-worker:research:' || run.id::text || ':' || run.status,
    180
  )
from content_factory.product_research_runs run
where run.status in ('completed', 'failed', 'cancelled')
on conflict (organization_id, recipient_id, dedupe_key) do nothing;

insert into content_factory.notification_outbox (
  organization_id, recipient_id, kind, severity, title, body,
  deep_link, entity_type, entity_id, properties, request_hash, dedupe_key
)
select
  review.organization_id,
  review.requested_by,
  'background_review_' || review.status,
  case review.status
    when 'failed' then 'error'
    when 'cancelled' then 'warning'
    else 'success'
  end,
  case review.status
    when 'failed' then 'Проверка контента завершилась с ошибкой'
    when 'cancelled' then 'Проверка контента отменена'
    else 'Проверка контента готова'
  end,
  case review.status
    when 'failed' then
      'Проверка безопасно закрыта без автоматического повтора платного запроса.'
    when 'cancelled' then
      'Проверка отменена; исходный файл не публиковался автоматически.'
    else
      'Оценка качества, риски и рекомендации доступны в рабочем пространстве.'
  end,
  '#/workspace/review',
  'content_review',
  review.id::text,
  jsonb_build_object(
    'source', 'creator_background_worker',
    'status', review.status
  ),
  content_factory_private.json_hash(jsonb_build_object(
    'recipient_id', review.requested_by,
    'kind', 'background_review_' || review.status,
    'severity', case review.status
      when 'failed' then 'error'
      when 'cancelled' then 'warning'
      else 'success'
    end,
    'title', case review.status
      when 'failed' then 'Проверка контента завершилась с ошибкой'
      when 'cancelled' then 'Проверка контента отменена'
      else 'Проверка контента готова'
    end,
    'body', case review.status
      when 'failed' then
        'Проверка безопасно закрыта без автоматического повтора платного запроса.'
      when 'cancelled' then
        'Проверка отменена; исходный файл не публиковался автоматически.'
      else
        'Оценка качества, риски и рекомендации доступны в рабочем пространстве.'
    end,
    'deep_link', '#/workspace/review',
    'entity_type', 'content_review',
    'entity_id', review.id::text,
    'properties', jsonb_build_object(
      'source', 'creator_background_worker',
      'status', review.status
    )
  )),
  left(
    'background-worker:review:' || review.id::text || ':' || review.status,
    180
  )
from content_factory.content_review_runs review
where review.status in ('completed', 'failed', 'cancelled')
on conflict (organization_id, recipient_id, dedupe_key) do nothing;

revoke all on function
  content_factory_private.guard_notification_outbox()
  from public, anon, authenticated, service_role;
revoke all on function
  content_factory_private.enqueue_terminal_notification()
  from public, anon, authenticated, service_role;

revoke all on function public.system_reconcile_background_leases(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_claim_notification_outbox(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_complete_notification_outbox(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_notification_outbox_health(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_reconcile_background_leases(jsonb)
  to service_role;
grant execute on function public.system_claim_notification_outbox(jsonb)
  to service_role;
grant execute on function public.system_complete_notification_outbox(jsonb)
  to service_role;
grant execute on function public.system_notification_outbox_health(jsonb)
  to service_role;

commit;
