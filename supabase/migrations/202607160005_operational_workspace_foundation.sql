begin;

-- Operational workspace foundation. The browser never receives direct table
-- privileges: every read/write crosses a narrow, organization-scoped RPC.
create table if not exists content_factory.user_notifications (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    recipient_id uuid not null,
    kind text not null check (kind ~ '^[a-z][a-z0-9_]{2,79}$'),
    severity text not null default 'info'
      check (severity in ('info', 'success', 'warning', 'error')),
    title text not null check (length(btrim(title)) between 3 and 180),
    body text not null check (length(btrim(body)) between 1 and 2000),
    deep_link text not null check (
      length(deep_link) between 3 and 600
      and deep_link ~ '^#/[-A-Za-z0-9_./?=&%:]+$'
    ),
    entity_type text check (
      entity_type is null
      or entity_type ~ '^[a-z][a-z0-9_]{1,79}$'
    ),
    entity_id text check (
      entity_id is null
      or length(btrim(entity_id)) between 1 and 180
    ),
    properties jsonb not null default '{}'::jsonb check (
      jsonb_typeof(properties) = 'object'
      and length(properties::text) <= 32768
    ),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    dedupe_key text not null check (length(dedupe_key) between 8 and 180),
    read_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, recipient_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, recipient_id, dedupe_key),
    unique (organization_id, id)
);

create index if not exists user_notifications_recipient_page_idx
  on content_factory.user_notifications
  (organization_id, recipient_id, created_at desc, id desc);
create index if not exists user_notifications_recipient_unread_idx
  on content_factory.user_notifications
  (organization_id, recipient_id, created_at desc, id desc)
  where read_at is null;

create table if not exists content_factory.training_walkthrough_progress (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    module_code text not null
      references content_factory.training_modules(code),
    walkthrough_id text not null
      check (walkthrough_id ~ '^[a-z0-9][a-z0-9_]{2,79}$'),
    current_frame_id text check (
      current_frame_id is null
      or current_frame_id ~ '^[a-z0-9][a-z0-9_]{1,79}$'
    ),
    position_seconds numeric(10,3) not null default 0
      check (position_seconds between 0 and 86400),
    completed_frame_ids jsonb not null default '[]'::jsonb check (
      jsonb_typeof(completed_frame_ids) = 'array'
      and jsonb_array_length(completed_frame_ids) <= 200
      and length(completed_frame_ids::text) <= 32768
    ),
    completed boolean not null default false,
    completed_at timestamptz,
    version bigint not null default 1 check (version >= 1),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, profile_id, module_code, walkthrough_id),
    unique (organization_id, id),
    check (
      (completed and completed_at is not null)
      or (not completed and completed_at is null)
    )
);

create index if not exists training_walkthrough_progress_profile_idx
  on content_factory.training_walkthrough_progress
  (organization_id, profile_id, updated_at desc, id desc);

create table if not exists content_factory.saved_work_views (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    profile_id uuid not null,
    name text not null check (
      length(btrim(name)) between 2 and 80
      and name !~ '[[:cntrl:]]'
    ),
    filters jsonb not null default '{}'::jsonb check (
      jsonb_typeof(filters) = 'object'
      and length(filters::text) <= 16384
    ),
    is_default boolean not null default false,
    version bigint not null default 1 check (version >= 1),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, profile_id)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, id)
);

create unique index if not exists saved_work_views_profile_name_uq
  on content_factory.saved_work_views
  (organization_id, profile_id, lower(btrim(name)));
create unique index if not exists saved_work_views_one_default_uq
  on content_factory.saved_work_views (organization_id, profile_id)
  where is_default;
create index if not exists saved_work_views_profile_page_idx
  on content_factory.saved_work_views
  (organization_id, profile_id, updated_at desc, id desc);

alter table content_factory.user_notifications enable row level security;
alter table content_factory.training_walkthrough_progress
  enable row level security;
alter table content_factory.saved_work_views enable row level security;

revoke all on content_factory.user_notifications
  from public, anon, authenticated;
revoke all on content_factory.training_walkthrough_progress
  from public, anon, authenticated;
revoke all on content_factory.saved_work_views
  from public, anon, authenticated;
grant all on content_factory.user_notifications to service_role;
grant all on content_factory.training_walkthrough_progress to service_role;
grant all on content_factory.saved_work_views to service_role;

create or replace function content_factory_private.guard_user_notification()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using
      errcode = '55000',
      message = 'notification_deletion_forbidden';
  end if;
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.recipient_id <> old.recipient_id
     or new.kind <> old.kind
     or new.severity <> old.severity
     or new.title <> old.title
     or new.body <> old.body
     or new.deep_link <> old.deep_link
     or new.entity_type is distinct from old.entity_type
     or new.entity_id is distinct from old.entity_id
     or new.properties <> old.properties
     or new.request_hash <> old.request_hash
     or new.dedupe_key <> old.dedupe_key
     or new.created_at <> old.created_at then
    raise exception using
      errcode = '55000',
      message = 'notification_identity_immutable';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists guard_user_notification
  on content_factory.user_notifications;
create trigger guard_user_notification
before update or delete on content_factory.user_notifications
for each row execute function
  content_factory_private.guard_user_notification();

create or replace function
  content_factory_private.guard_training_walkthrough_progress()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE' then
    if new.id <> old.id
       or new.organization_id <> old.organization_id
       or new.profile_id <> old.profile_id
       or new.module_code <> old.module_code
       or new.walkthrough_id <> old.walkthrough_id
       or new.created_at <> old.created_at then
      raise exception using
        errcode = '55000',
        message = 'training_progress_identity_immutable';
    end if;
    if new.position_seconds < old.position_seconds
       or not (old.completed_frame_ids <@ new.completed_frame_ids)
       or (old.completed and not new.completed) then
      raise exception using
        errcode = '55000',
        message = 'training_progress_regression_forbidden';
    end if;
    new.version := old.version + 1;
    new.updated_at := now();
  end if;
  if new.completed then
    new.completed_at := case
      when tg_op = 'UPDATE'
        then coalesce(old.completed_at, new.completed_at, now())
      else coalesce(new.completed_at, now())
    end;
  else
    new.completed_at := null;
  end if;
  return new;
end;
$$;

drop trigger if exists guard_training_walkthrough_progress
  on content_factory.training_walkthrough_progress;
create trigger guard_training_walkthrough_progress
before insert or update on content_factory.training_walkthrough_progress
for each row execute function
  content_factory_private.guard_training_walkthrough_progress();

create or replace function content_factory_private.guard_saved_work_view()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.name := btrim(new.name);
  if tg_op = 'UPDATE' then
    if new.id <> old.id
       or new.organization_id <> old.organization_id
       or new.profile_id <> old.profile_id
       or new.created_at <> old.created_at then
      raise exception using
        errcode = '55000',
        message = 'saved_work_view_identity_immutable';
    end if;
    new.version := old.version + 1;
    new.updated_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists guard_saved_work_view
  on content_factory.saved_work_views;
create trigger guard_saved_work_view
before insert or update on content_factory.saved_work_views
for each row execute function content_factory_private.guard_saved_work_view();

create or replace function content_factory_private.normalize_work_filters(
  value jsonb
)
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  query_value text := '';
  statuses_value jsonb := '[]'::jsonb;
  item_types_value jsonb := '[]'::jsonb;
  item jsonb;
begin
  value := coalesce(value, '{}'::jsonb);
  if jsonb_typeof(value) <> 'object'
     or length(value::text) > 16384
     or value - array['query', 'statuses', 'item_types']::text[]
          <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'work_filters_invalid';
  end if;

  if value ? 'query' then
    if jsonb_typeof(value -> 'query') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'work_query_invalid';
    end if;
    query_value := lower(btrim(value ->> 'query'));
    if length(query_value) > 120 or query_value ~ '[[:cntrl:]]' then
      raise exception using
        errcode = '22023',
        message = 'work_query_invalid';
    end if;
  end if;

  if value ? 'statuses' then
    if jsonb_typeof(value -> 'statuses') <> 'array'
       or jsonb_array_length(value -> 'statuses') > 20 then
      raise exception using
        errcode = '22023',
        message = 'work_statuses_invalid';
    end if;
    for item in
      select element.value
      from jsonb_array_elements(value -> 'statuses') element(value)
    loop
      if jsonb_typeof(item) <> 'string'
         or lower(btrim(item #>> '{}'))
              !~ '^[a-z][a-z0-9_]{1,39}$' then
        raise exception using
          errcode = '22023',
          message = 'work_status_invalid';
      end if;
    end loop;
    select coalesce(
      jsonb_agg(normalized.status order by normalized.status),
      '[]'::jsonb
    )
    into statuses_value
    from (
      select distinct lower(btrim(element.value)) as status
      from jsonb_array_elements_text(value -> 'statuses') element(value)
    ) normalized;
  end if;

  if value ? 'item_types' then
    if jsonb_typeof(value -> 'item_types') <> 'array'
       or jsonb_array_length(value -> 'item_types') > 5 then
      raise exception using
        errcode = '22023',
        message = 'work_item_types_invalid';
    end if;
    for item in
      select element.value
      from jsonb_array_elements(value -> 'item_types') element(value)
    loop
      if jsonb_typeof(item) <> 'string'
         or lower(btrim(item #>> '{}')) not in (
           'task', 'generation', 'review', 'placement', 'payout'
         ) then
        raise exception using
          errcode = '22023',
          message = 'work_item_type_invalid';
      end if;
    end loop;
    select coalesce(
      jsonb_agg(normalized.item_type order by normalized.item_type),
      '[]'::jsonb
    )
    into item_types_value
    from (
      select distinct lower(btrim(element.value)) as item_type
      from jsonb_array_elements_text(value -> 'item_types') element(value)
    ) normalized;
  end if;

  return jsonb_build_object(
    'query', query_value,
    'statuses', statuses_value,
    'item_types', item_types_value
  );
end;
$$;

create or replace function content_factory_private.saved_work_views_json(
  organization_id uuid,
  profile_id uuid
)
returns jsonb
language sql
security definer
stable
set search_path = ''
as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'id', view.id,
    'name', view.name,
    'filters', view.filters,
    'is_default', view.is_default,
    'version', view.version,
    'created_at', view.created_at,
    'updated_at', view.updated_at
  ) order by view.is_default desc, view.updated_at desc, view.id desc), '[]'::jsonb)
  from content_factory.saved_work_views view
  where view.organization_id = saved_work_views_json.organization_id
    and view.profile_id = saved_work_views_json.profile_id;
$$;

create index if not exists creator_tasks_my_work_idx
  on content_factory.creator_tasks
  (organization_id, assignee_id, updated_at desc, id desc);
create index if not exists generation_jobs_my_work_active_idx
  on content_factory.generation_jobs
  (organization_id, assigned_to, updated_at desc, id desc)
  where status in (
    'queued', 'starting', 'submitted', 'processing', 'failed'
  );
create index if not exists content_review_runs_my_work_idx
  on content_factory.content_review_runs
  (organization_id, requested_by, updated_at desc, id desc)
  where status in ('queued', 'processing', 'completed', 'failed');
create index if not exists content_review_runs_parent_retry_idx
  on content_factory.content_review_runs
  (organization_id, parent_review_id, created_at desc, id desc)
  where parent_review_id is not null;
create index if not exists placements_my_work_idx
  on content_factory.placements
  (organization_id, assigned_to, updated_at desc, id desc);
create index if not exists creator_payouts_my_work_idx
  on content_factory.creator_payouts
  (organization_id, profile_id, updated_at desc, id desc);

create or replace function public.creator_my_work(
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
  actor_role text;
  review_team_scope boolean;
  filters_value jsonb;
  query_value text;
  statuses_value text[];
  item_types_value text[];
  page_size integer := 50;
  cursor_updated_at timestamptz;
  cursor_item_type text;
  cursor_id uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 32768
     or p_payload - array[
       'organization_id', 'query', 'statuses', 'item_types',
       'page_size', 'cursor'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'my_work_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true, null
  );
  review_team_scope := actor_role = any(
    array['owner', 'admin', 'producer', 'reviewer']
  );
  filters_value := content_factory_private.normalize_work_filters(
    jsonb_build_object(
      'query', coalesce(p_payload -> 'query', '""'::jsonb),
      'statuses', coalesce(p_payload -> 'statuses', '[]'::jsonb),
      'item_types', coalesce(p_payload -> 'item_types', '[]'::jsonb)
    )
  );
  query_value := filters_value ->> 'query';
  select coalesce(array_agg(item.value), array[]::text[])
    into statuses_value
  from jsonb_array_elements_text(filters_value -> 'statuses') item(value);
  select coalesce(array_agg(item.value), array[]::text[])
    into item_types_value
  from jsonb_array_elements_text(filters_value -> 'item_types') item(value);

  if p_payload ? 'page_size' then
    if jsonb_typeof(p_payload -> 'page_size') <> 'number'
       or coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'my_work_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'my_work_page_size_invalid';
    end;
  end if;
  if page_size not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'my_work_page_size_invalid';
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object'
       or (p_payload -> 'cursor') - array[
         'updated_at', 'item_type', 'id'
       ]::text[] <> '{}'::jsonb
       or not ((p_payload -> 'cursor') ?& array[
         'updated_at', 'item_type', 'id'
       ]) then
      raise exception using
        errcode = '22023',
        message = 'my_work_cursor_invalid';
    end if;
    begin
      cursor_updated_at :=
        (p_payload #>> '{cursor,updated_at}')::timestamptz;
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation
        or invalid_datetime_format
        or datetime_field_overflow then
      raise exception using
        errcode = '22023',
        message = 'my_work_cursor_invalid';
    end;
    cursor_item_type := lower(btrim(
      p_payload #>> '{cursor,item_type}'
    ));
    if cursor_updated_at is null
       or cursor_id is null
       or cursor_item_type not in (
         'task', 'generation', 'review', 'placement', 'payout'
       ) then
      raise exception using
        errcode = '22023',
        message = 'my_work_cursor_invalid';
    end if;
  end if;

  with all_items as materialized (
    select
      'task'::text as item_type,
      task.id,
      task.status,
      task.title,
      left(coalesce(task.instructions, ''), 500) as summary,
      '#/workspace/tasks?item=' || task.id::text as deep_link,
      task.product_id,
      task.id as task_id,
      task.assignee_id,
      task.due_at,
      task.updated_at,
      null::bigint as amount_minor,
      null::text as currency,
      jsonb_build_object(
        'task_type', task.task_type,
        'priority', task.priority,
        'payout_minor', task.payout_minor
      ) as metadata,
      task.status in ('todo', 'in_progress', 'blocked') as action_required,
      task.status = 'blocked' as blocker,
      (
        task.due_at is not null
        and task.due_at < now()
        and task.status not in ('done', 'cancelled')
      ) as overdue,
      lower(concat_ws(' ', task.title, task.instructions)) as search_text
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.assignee_id = user_id

    union all

    select
      'generation'::text,
      job.id,
      job.status,
      'Генерация: ' || product.title,
      left(coalesce(batch.name, product.sku), 500),
      '#/workspace/generation?job=' || job.id::text,
      job.product_id,
      review_task.id,
      job.assigned_to,
      null::timestamptz,
      job.updated_at,
      job.actual_cost_minor,
      'USD'::text,
      jsonb_build_object(
        'batch_id', job.batch_id,
        'provider', job.provider,
        'model', job.input ->> 'model',
        'estimated_cost_minor', job.estimated_cost_minor,
        'provider_task_id', job.output ->> 'provider_task_id',
        'failure_code', coalesce(
          job.output ->> 'failure_code',
          job.output ->> 'error_code'
        ),
        'reconciliation_required',
          content_factory_private.real_generation_reconciliation_unresolved(
            job.output
          )
      ),
      job.status = 'failed',
      job.status = 'failed',
      false,
      lower(concat_ws(
        ' ', product.title, product.sku, batch.name,
        job.input ->> 'model', job.output ->> 'provider_task_id',
        job.output ->> 'failure_code', job.output ->> 'error_code'
      ))
    from content_factory.generation_jobs job
    join content_factory.products product
      on product.organization_id = job.organization_id
     and product.id = job.product_id
    join content_factory.generation_batches batch
      on batch.organization_id = job.organization_id
     and batch.id = job.batch_id
    left join lateral (
      select task.id, task.status
      from content_factory.creator_tasks task
      where task.organization_id = job.organization_id
        and task.generation_job_id = job.id
        and task.task_type = 'video_review'
      order by task.created_at desc, task.id desc
      limit 1
    ) review_task on true
    where job.organization_id = organization_id
      and (job.assigned_to = user_id or job.requested_by = user_id)
      and job.status in (
        'queued', 'starting', 'submitted', 'processing', 'failed'
      )
      and (
        job.status <> 'failed'
        or content_factory_private.real_generation_reconciliation_unresolved(
          job.output
        )
        or review_task.id is null
        or review_task.status not in ('done', 'cancelled')
      )

    union all

    select
      'review'::text,
      review.id,
      case
        when review.status = 'completed' and decision.id is null
          then 'awaiting_decision'
        else review.status
      end,
      'Проверка: ' || coalesce(
        nullif(media.metadata ->> 'original_filename', ''),
        product.title,
        media.object_name
      ),
      left(coalesce(
        review.error_message,
        review.result ->> 'ad_classification_summary',
        review.ruleset_version
      ), 500),
      '#/workspace/review?review=' || review.id::text,
      media.product_id,
      media.task_id,
      media.owner_id,
      null::timestamptz,
      review.updated_at,
      null::bigint,
      null::text,
      jsonb_build_object(
        'media_object_id', review.media_object_id,
        'requested_by', review.requested_by,
        'ruleset_version', review.ruleset_version,
        'overall_score', review.result -> 'overall_score',
        'decision', decision.decision,
        'error_code', review.error_code,
        'retry_review_id', retry_review.id
      ),
      (
        (review.status = 'completed' and decision.id is null)
        or (review.status = 'failed' and retry_review.id is null)
      ),
      review.status = 'failed' and retry_review.id is null,
      false,
      lower(concat_ws(
        ' ', media.metadata ->> 'original_filename', media.object_name,
        product.title, product.sku, review.ruleset_version,
        review.error_message
      ))
    from content_factory.content_review_runs review
    join content_factory.media_objects media
      on media.organization_id = review.organization_id
     and media.id = review.media_object_id
    left join content_factory.products product
      on product.organization_id = media.organization_id
     and product.id = media.product_id
    left join content_factory.content_review_decisions decision
      on decision.organization_id = review.organization_id
     and decision.review_id = review.id
    left join lateral (
      select child.id
      from content_factory.content_review_runs child
      where child.organization_id = review.organization_id
        and child.parent_review_id = review.id
        and child.status <> 'cancelled'
      order by child.created_at desc, child.id desc
      limit 1
    ) retry_review on true
    where review.organization_id = organization_id
      and (review_team_scope or review.requested_by = user_id)
      and review.status in ('queued', 'processing', 'completed', 'failed')
      and not (
        review.status = 'completed'
        and decision.id is not null
      )
      and not (
        review.status = 'failed'
        and retry_review.id is not null
      )

    union all

    select
      'placement'::text,
      placement.id,
      placement.status,
      coalesce(task.title, 'Публикация: ' || product.title),
      left(concat_ws(
        ' · ', placement.platform, placement.destination_ref,
        task.instructions
      ), 500),
      '#/workspace/placement?placement=' || placement.id::text,
      placement.product_id,
      placement.task_id,
      placement.assigned_to,
      coalesce(placement.scheduled_at, task.due_at),
      placement.updated_at,
      null::bigint,
      null::text,
      jsonb_build_object(
        'platform', placement.platform,
        'destination_ref', placement.destination_ref,
        'tracking_url', placement.tracking_url,
        'final_url', placement.final_url
      ),
      placement.status in ('ready', 'failed'),
      placement.status = 'failed',
      (
        placement.scheduled_at is not null
        and placement.scheduled_at < now()
        and placement.status in ('scheduled', 'ready')
      ),
      lower(concat_ws(
        ' ', task.title, task.instructions, product.title, product.sku,
        placement.platform, placement.destination_ref, placement.final_url
      ))
    from content_factory.placements placement
    join content_factory.products product
      on product.organization_id = placement.organization_id
     and product.id = placement.product_id
    left join content_factory.creator_tasks task
      on task.organization_id = placement.organization_id
     and task.id = placement.task_id
    where placement.organization_id = organization_id
      and placement.assigned_to = user_id

    union all

    select
      'payout'::text,
      payout.id,
      payout.status,
      'Выплата: ' || task.title,
      left(coalesce(payout.reason, ''), 500),
      '#/workspace/payouts?payout=' || payout.id::text,
      task.product_id,
      payout.task_id,
      payout.profile_id,
      null::timestamptz,
      payout.updated_at,
      payout.amount_minor,
      payout.currency,
      jsonb_build_object(
        'external_payment_reference', payout.external_payment_reference,
        'approved_at', payout.approved_at,
        'paid_at', payout.paid_at
      ),
      payout.status = 'rejected',
      payout.status = 'rejected',
      false,
      lower(concat_ws(
        ' ', task.title, payout.reason, payout.external_payment_reference,
        payout.amount_minor::text, payout.currency
      ))
    from content_factory.creator_payouts payout
    join content_factory.creator_tasks task
      on task.organization_id = payout.organization_id
     and task.id = payout.task_id
    where payout.organization_id = organization_id
      and payout.profile_id = user_id
  ),
  filtered as materialized (
    select item.*
    from all_items item
    where (
        cardinality(statuses_value) = 0
        or item.status = any(statuses_value)
      )
      and (
        cardinality(item_types_value) = 0
        or item.item_type = any(item_types_value)
      )
      and (
        query_value = ''
        or item.search_text like '%' || query_value || '%'
      )
  ),
  candidates as materialized (
    select item.*
    from filtered item
    where cursor_updated_at is null
      or (item.updated_at, item.item_type, item.id)
           < (cursor_updated_at, cursor_item_type, cursor_id)
    order by item.updated_at desc, item.item_type desc, item.id desc
    limit page_size + 1
  ),
  page as materialized (
    select item.*
    from candidates item
    order by item.updated_at desc, item.item_type desc, item.id desc
    limit page_size
  ),
  last_item as (
    select item.updated_at, item.item_type, item.id
    from page item
    order by item.updated_at asc, item.item_type asc, item.id asc
    limit 1
  )
  select jsonb_build_object(
    'organization_id', organization_id,
    'filters', filters_value,
    'counts', jsonb_build_object(
      'total', count(*),
      'task', count(*) filter (where item_type = 'task'),
      'generation', count(*) filter (where item_type = 'generation'),
      'review', count(*) filter (where item_type = 'review'),
      'placement', count(*) filter (where item_type = 'placement'),
      'payout', count(*) filter (where item_type = 'payout'),
      'action_required', count(*) filter (where action_required),
      'blockers', count(*) filter (where blocker),
      'overdue', count(*) filter (where overdue)
    ),
    'items', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'item_type', item.item_type,
        'id', item.id,
        'status', item.status,
        'title', item.title,
        'summary', item.summary,
        'deep_link', item.deep_link,
        'product_id', item.product_id,
        'task_id', item.task_id,
        'assignee_id', item.assignee_id,
        'due_at', item.due_at,
        'updated_at', item.updated_at,
        'amount_minor', item.amount_minor,
        'currency', item.currency,
        'action_required', item.action_required,
        'blocker', item.blocker,
        'overdue', item.overdue,
        'metadata', item.metadata
      ) order by item.updated_at desc, item.item_type desc, item.id desc), '[]'::jsonb)
      from page item
    ),
    'next_cursor', case
      when (select count(*) from candidates) > page_size then (
        select jsonb_build_object(
          'updated_at', item.updated_at,
          'item_type', item.item_type,
          'id', item.id
        )
        from last_item item
      )
      else null
    end,
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'cap', 100,
      'cursor_mode', 'keyset_updated_at_type_id'
    )
  )
  into result_value
  from filtered;

  return result_value;
end;
$$;

create or replace function public.creator_notifications(
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
  unread_only boolean := false;
  page_size integer := 50;
  cursor_created_at timestamptz;
  cursor_id uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 8192
     or p_payload - array[
       'organization_id', 'unread_only', 'page_size', 'cursor'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'notifications_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, false, null
  );

  if p_payload ? 'unread_only' then
    if jsonb_typeof(p_payload -> 'unread_only') <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'notifications_unread_only_invalid';
    end if;
    unread_only := (p_payload ->> 'unread_only')::boolean;
  end if;
  if p_payload ? 'page_size' then
    if jsonb_typeof(p_payload -> 'page_size') <> 'number'
       or coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'notifications_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'notifications_page_size_invalid';
    end;
  end if;
  if page_size not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'notifications_page_size_invalid';
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object'
       or (p_payload -> 'cursor') - array[
         'created_at', 'id'
       ]::text[] <> '{}'::jsonb
       or not ((p_payload -> 'cursor') ?& array['created_at', 'id']) then
      raise exception using
        errcode = '22023',
        message = 'notifications_cursor_invalid';
    end if;
    begin
      cursor_created_at :=
        (p_payload #>> '{cursor,created_at}')::timestamptz;
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation
        or invalid_datetime_format
        or datetime_field_overflow then
      raise exception using
        errcode = '22023',
        message = 'notifications_cursor_invalid';
    end;
    if cursor_created_at is null or cursor_id is null then
      raise exception using
        errcode = '22023',
        message = 'notifications_cursor_invalid';
    end if;
  end if;

  with candidates as materialized (
    select notification.*
    from content_factory.user_notifications notification
    where notification.organization_id = organization_id
      and notification.recipient_id = user_id
      and (not unread_only or notification.read_at is null)
      and (
        cursor_created_at is null
        or (notification.created_at, notification.id)
          < (cursor_created_at, cursor_id)
      )
    order by notification.created_at desc, notification.id desc
    limit page_size + 1
  ),
  page as materialized (
    select notification.*
    from candidates notification
    order by notification.created_at desc, notification.id desc
    limit page_size
  ),
  last_item as (
    select notification.created_at, notification.id
    from page notification
    order by notification.created_at asc, notification.id asc
    limit 1
  )
  select jsonb_build_object(
    'organization_id', organization_id,
    'counts', jsonb_build_object(
      'total', (
        select count(*)
        from content_factory.user_notifications notification
        where notification.organization_id = organization_id
          and notification.recipient_id = user_id
      ),
      'unread', (
        select count(*)
        from content_factory.user_notifications notification
        where notification.organization_id = organization_id
          and notification.recipient_id = user_id
          and notification.read_at is null
      )
    ),
    'items', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'id', notification.id,
        'kind', notification.kind,
        'severity', notification.severity,
        'title', notification.title,
        'body', notification.body,
        'deep_link', notification.deep_link,
        'entity_type', notification.entity_type,
        'entity_id', notification.entity_id,
        'properties', notification.properties,
        'read_at', notification.read_at,
        'created_at', notification.created_at
      ) order by notification.created_at desc, notification.id desc), '[]'::jsonb)
      from page notification
    ),
    'next_cursor', case
      when (select count(*) from candidates) > page_size then (
        select jsonb_build_object(
          'created_at', notification.created_at,
          'id', notification.id
        )
        from last_item notification
      )
      else null
    end,
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'cap', 100,
      'cursor_mode', 'keyset_created_at_id'
    )
  )
  into result_value;

  return result_value;
end;
$$;

create or replace function public.creator_mark_notifications_read(
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
  notification_ids uuid[];
  mark_all_unread boolean := false;
  is_read_value boolean := true;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  changed_count integer;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 32768
     or p_payload - array[
       'organization_id', 'notification_ids', 'all_unread', 'is_read',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'notification_mark_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, false, null
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if p_payload ? 'all_unread' then
    if jsonb_typeof(p_payload -> 'all_unread') <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'notification_all_unread_invalid';
    end if;
    mark_all_unread := (p_payload ->> 'all_unread')::boolean;
  end if;
  if p_payload ? 'is_read' then
    if jsonb_typeof(p_payload -> 'is_read') <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'notification_is_read_invalid';
    end if;
    is_read_value := (p_payload ->> 'is_read')::boolean;
  end if;
  if mark_all_unread then
    if p_payload ? 'notification_ids' or not is_read_value then
      raise exception using
        errcode = '22023',
        message = 'notification_mark_scope_invalid';
    end if;
  elsif not (p_payload ? 'notification_ids')
     or jsonb_typeof(p_payload -> 'notification_ids') <> 'array'
     or jsonb_array_length(p_payload -> 'notification_ids')
          not between 1 and 100 then
    raise exception using
      errcode = '22023',
      message = 'notification_mark_payload_invalid';
  end if;

  if not mark_all_unread then
    begin
      select array_agg(
        distinct element.value::uuid
        order by element.value::uuid
      )
        into notification_ids
      from jsonb_array_elements_text(
        p_payload -> 'notification_ids'
      ) element(value);
    exception when invalid_text_representation then
      raise exception using
        errcode = '22023',
        message = 'notification_id_invalid';
    end;
    if cardinality(notification_ids) <>
         jsonb_array_length(p_payload -> 'notification_ids') then
      raise exception using
        errcode = '22023',
        message = 'notification_id_duplicate';
    end if;
  end if;

  request_payload := jsonb_build_object(
    'notification_ids', case
      when mark_all_unread then null
      else to_jsonb(notification_ids)
    end,
    'all_unread', mark_all_unread,
    'is_read', is_read_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_mark_notifications_read',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  if mark_all_unread then
    perform 1
    from content_factory.user_notifications notification
    where notification.organization_id = organization_id
      and notification.recipient_id = user_id
      and notification.read_at is null
    for update;

    update content_factory.user_notifications notification
    set read_at = now()
    where notification.organization_id = organization_id
      and notification.recipient_id = user_id
      and notification.read_at is null;
    get diagnostics changed_count = row_count;

    result_value := jsonb_build_object(
      'ok', true,
      'organization_id', organization_id,
      'updated_count', changed_count,
      'is_read', true,
      'scope', 'all_unread',
      'remaining_unread', 0,
      'notifications', '[]'::jsonb
    );
  else
    perform 1
    from content_factory.user_notifications notification
    where notification.organization_id = organization_id
      and notification.recipient_id = user_id
      and notification.id = any(notification_ids)
    for update;

    if (
      select count(*)
      from content_factory.user_notifications notification
      where notification.organization_id = organization_id
        and notification.recipient_id = user_id
        and notification.id = any(notification_ids)
    ) <> cardinality(notification_ids) then
      raise exception using
        errcode = '42501',
        message = 'notification_access_denied';
    end if;

    update content_factory.user_notifications notification
    set read_at = case when is_read_value then now() else null end
    where notification.organization_id = organization_id
      and notification.recipient_id = user_id
      and notification.id = any(notification_ids)
      and (
        (is_read_value and notification.read_at is null)
        or (not is_read_value and notification.read_at is not null)
      );
    get diagnostics changed_count = row_count;

    select jsonb_build_object(
      'ok', true,
      'organization_id', organization_id,
      'updated_count', changed_count,
      'is_read', is_read_value,
      'scope', 'selected',
      'notifications', coalesce(jsonb_agg(jsonb_build_object(
        'id', notification.id,
        'read_at', notification.read_at
      ) order by notification.created_at desc, notification.id desc), '[]'::jsonb)
    )
    into result_value
    from content_factory.user_notifications notification
    where notification.organization_id = organization_id
      and notification.recipient_id = user_id
      and notification.id = any(notification_ids);
  end if;

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case when is_read_value
      then 'notifications_marked_read'
      else 'notifications_marked_unread'
    end,
    'notification',
    null,
    jsonb_build_object(
      'notification_count', case
        when mark_all_unread then changed_count
        else cardinality(notification_ids)
      end,
      'scope', case
        when mark_all_unread then 'all_unread'
        else 'selected'
      end,
      'changed_count', changed_count
    ),
    'notification-mark:' || idempotency_key_value
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_mark_notifications_read',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.system_emit_notification(
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
      errcode = '22023',
      message = 'system_notification_payload_invalid';
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
     or (
       entity_type_value is not null
       and entity_type_value !~ '^[a-z][a-z0-9_]{1,79}$'
     )
     or (
       entity_id_value is not null
       and length(entity_id_value) not between 1 and 180
     )
     or jsonb_typeof(properties_value) <> 'object'
     or length(properties_value::text) > 32768 then
    raise exception using
      errcode = '22023',
      message = 'system_notification_invalid';
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
      errcode = 'P0002',
      message = 'notification_recipient_not_found';
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
  request_hash_value :=
    content_factory_private.json_hash(request_payload);

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('notification:' || recipient_id::text || ':' ||
      idempotency_key_value)
  );
  select notification.*
    into notification_row
  from content_factory.user_notifications notification
  where notification.organization_id = organization_id
    and notification.recipient_id = recipient_id
    and notification.dedupe_key = idempotency_key_value;
  existing_hash := notification_row.request_hash;

  if existing_hash is not null and existing_hash <> request_hash_value then
    raise exception using
      errcode = '23505',
      message = 'notification_idempotency_conflict';
  end if;
  if existing_hash is null then
    insert into content_factory.user_notifications (
      organization_id, recipient_id, kind, severity, title, body,
      deep_link, entity_type, entity_id, properties, request_hash,
      dedupe_key
    ) values (
      organization_id, recipient_id, kind_value, severity_value,
      title_value, body_value, deep_link_value, entity_type_value,
      entity_id_value, properties_value, request_hash_value,
      idempotency_key_value
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
      'created_at', notification_row.created_at
    )
  );
  return result_value;
end;
$$;

create or replace function public.creator_training_progress(
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
  module_code_value text;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 4096
     or p_payload - array[
       'organization_id', 'module_code'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'training_progress_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, false, null
  );
  module_code_value := nullif(lower(btrim(coalesce(
    p_payload ->> 'module_code', ''
  ))), '');
  if module_code_value is not null
     and module_code_value !~ '^[a-z0-9_]{3,80}$' then
    raise exception using
      errcode = '22023',
      message = 'module_code_invalid';
  end if;

  select jsonb_build_object(
    'organization_id', organization_id,
    'items', coalesce(jsonb_agg(jsonb_build_object(
      'module_code', progress.module_code,
      'walkthrough_id', progress.walkthrough_id,
      'current_frame_id', progress.current_frame_id,
      'position_seconds', progress.position_seconds,
      'completed_frame_ids', progress.completed_frame_ids,
      'completed', progress.completed,
      'completed_at', progress.completed_at,
      'updated_at', progress.updated_at,
      'version', progress.version
    ) order by progress.updated_at desc, progress.id desc), '[]'::jsonb)
  )
  into result_value
  from content_factory.training_walkthrough_progress progress
  where progress.organization_id = organization_id
    and progress.profile_id = user_id
    and (
      module_code_value is null
      or progress.module_code = module_code_value
    );

  return result_value;
end;
$$;

create or replace function public.creator_save_training_progress(
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
  module_code_value text;
  walkthrough_id_value text;
  current_frame_id_value text;
  position_seconds_value numeric(10,3) := 0;
  completed_frame_ids_value jsonb := '[]'::jsonb;
  normalized_frame_ids jsonb := '[]'::jsonb;
  completed_value boolean := false;
  expected_version_value bigint;
  idempotency_key_value text;
  walkthrough_value jsonb;
  all_frame_ids jsonb;
  duration_seconds_value integer;
  item jsonb;
  request_payload jsonb;
  replay jsonb;
  progress_row content_factory.training_walkthrough_progress%rowtype;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 49152
     or p_payload - array[
       'organization_id', 'module_code', 'walkthrough_id',
       'current_frame_id', 'position_seconds', 'completed_frame_ids',
       'completed', 'expected_version', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'training_progress_save_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, false, null
  );
  module_code_value := lower(content_factory_private.require_text(
    p_payload, 'module_code', 3, 80
  ));
  walkthrough_id_value := lower(content_factory_private.require_text(
    p_payload, 'walkthrough_id', 3, 80
  ));
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  current_frame_id_value := nullif(lower(btrim(coalesce(
    p_payload ->> 'current_frame_id', ''
  ))), '');
  if module_code_value !~ '^[a-z0-9_]{3,80}$'
     or walkthrough_id_value !~ '^[a-z0-9][a-z0-9_]{2,79}$'
     or (
       current_frame_id_value is not null
       and current_frame_id_value !~ '^[a-z0-9][a-z0-9_]{1,79}$'
     ) then
    raise exception using
      errcode = '22023',
      message = 'training_progress_identity_invalid';
  end if;
  if p_payload ? 'position_seconds' then
    if jsonb_typeof(p_payload -> 'position_seconds') <> 'number'
       or coalesce(p_payload ->> 'position_seconds', '')
            !~ '^[0-9]+([.][0-9]{1,3})?$' then
      raise exception using
        errcode = '22023',
        message = 'training_position_invalid';
    end if;
    begin
      position_seconds_value :=
        (p_payload ->> 'position_seconds')::numeric(10,3);
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'training_position_invalid';
    end;
  end if;
  if position_seconds_value not between 0 and 86400 then
    raise exception using
      errcode = '22023',
      message = 'training_position_invalid';
  end if;
  if p_payload ? 'completed' then
    if jsonb_typeof(p_payload -> 'completed') <> 'boolean' then
      raise exception using
        errcode = '22023',
        message = 'training_completed_invalid';
    end if;
    completed_value := (p_payload ->> 'completed')::boolean;
  end if;
  if p_payload ? 'expected_version' then
    if jsonb_typeof(p_payload -> 'expected_version') <> 'number'
       or coalesce(p_payload ->> 'expected_version', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'training_expected_version_invalid';
    end if;
    begin
      expected_version_value :=
        (p_payload ->> 'expected_version')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'training_expected_version_invalid';
    end;
    if expected_version_value < 1 then
      raise exception using
        errcode = '22023',
        message = 'training_expected_version_invalid';
    end if;
  end if;

  completed_frame_ids_value := coalesce(
    p_payload -> 'completed_frame_ids', '[]'::jsonb
  );
  if jsonb_typeof(completed_frame_ids_value) <> 'array'
     or jsonb_array_length(completed_frame_ids_value) > 200
     or length(completed_frame_ids_value::text) > 32768 then
    raise exception using
      errcode = '22023',
      message = 'training_completed_frames_invalid';
  end if;
  for item in
    select element.value
    from jsonb_array_elements(completed_frame_ids_value) element(value)
  loop
    if jsonb_typeof(item) <> 'string'
       or lower(btrim(item #>> '{}'))
            !~ '^[a-z0-9][a-z0-9_]{1,79}$' then
      raise exception using
        errcode = '22023',
        message = 'training_completed_frame_invalid';
    end if;
  end loop;
  select coalesce(
    jsonb_agg(normalized.frame_id order by normalized.frame_id),
    '[]'::jsonb
  )
  into normalized_frame_ids
  from (
    select distinct lower(btrim(element.value)) as frame_id
    from jsonb_array_elements_text(completed_frame_ids_value) element(value)
  ) normalized;

  select walkthrough.value
    into walkthrough_value
  from content_factory.training_modules module
  cross join lateral jsonb_array_elements(
    module.content -> 'interactive_walkthroughs'
  ) walkthrough(value)
  where module.code = module_code_value
    and module.module_type = 'course'
    and module.is_active
    and walkthrough.value ->> 'id' = walkthrough_id_value;
  if walkthrough_value is null then
    raise exception using
      errcode = 'P0002',
      message = 'training_walkthrough_not_found';
  end if;
  if jsonb_typeof(walkthrough_value -> 'frames') <> 'array'
     or jsonb_array_length(walkthrough_value -> 'frames') < 1
     or coalesce(walkthrough_value ->> 'duration_seconds', '') !~ '^[0-9]+$' then
    raise exception using
      errcode = '55000',
      message = 'training_walkthrough_catalog_invalid';
  end if;
  duration_seconds_value :=
    (walkthrough_value ->> 'duration_seconds')::integer;
  select coalesce(
    jsonb_agg(frame.value ->> 'id' order by frame.ordinality),
    '[]'::jsonb
  )
  into all_frame_ids
  from jsonb_array_elements(walkthrough_value -> 'frames')
    with ordinality frame(value, ordinality);

  if current_frame_id_value is not null
     and not (all_frame_ids @> jsonb_build_array(current_frame_id_value)) then
    raise exception using
      errcode = '22023',
      message = 'training_current_frame_unknown';
  end if;
  if exists (
    select 1
    from jsonb_array_elements_text(normalized_frame_ids) supplied(value)
    where not (all_frame_ids @> jsonb_build_array(supplied.value))
  ) then
    raise exception using
      errcode = '22023',
      message = 'training_completed_frame_unknown';
  end if;
  if completed_value then
    normalized_frame_ids := all_frame_ids;
    position_seconds_value :=
      greatest(position_seconds_value, duration_seconds_value);
  end if;
  position_seconds_value :=
    least(position_seconds_value, duration_seconds_value);

  request_payload := jsonb_build_object(
    'module_code', module_code_value,
    'walkthrough_id', walkthrough_id_value,
    'current_frame_id', current_frame_id_value,
    'position_seconds', position_seconds_value,
    'completed_frame_ids', normalized_frame_ids,
    'completed', completed_value,
    'expected_version', expected_version_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_save_training_progress',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext(
      'training-progress:' || user_id::text || ':' ||
      module_code_value || ':' || walkthrough_id_value
    )
  );
  select progress.*
    into progress_row
  from content_factory.training_walkthrough_progress progress
  where progress.organization_id = organization_id
    and progress.profile_id = user_id
    and progress.module_code = module_code_value
    and progress.walkthrough_id = walkthrough_id_value
  for update;

  if progress_row.id is null then
    if expected_version_value is not null then
      raise exception using
        errcode = '40001',
        message = 'training_progress_version_conflict';
    end if;
    insert into content_factory.training_walkthrough_progress (
      organization_id, profile_id, module_code, walkthrough_id,
      current_frame_id, position_seconds, completed_frame_ids, completed,
      completed_at
    ) values (
      organization_id, user_id, module_code_value, walkthrough_id_value,
      current_frame_id_value, position_seconds_value, normalized_frame_ids,
      completed_value, case when completed_value then now() else null end
    )
    returning * into progress_row;
  else
    if expected_version_value is not null
       and progress_row.version <> expected_version_value then
      raise exception using
        errcode = '40001',
        message = 'training_progress_version_conflict';
    end if;
    select coalesce(
      jsonb_agg(frame_id order by frame_id), '[]'::jsonb
    )
    into normalized_frame_ids
    from (
      select distinct existing.value as frame_id
      from jsonb_array_elements_text(
        progress_row.completed_frame_ids || normalized_frame_ids
      ) existing(value)
    ) combined;
    update content_factory.training_walkthrough_progress progress
    set current_frame_id = coalesce(
          current_frame_id_value, progress.current_frame_id
        ),
        position_seconds = greatest(
          progress.position_seconds, position_seconds_value
        ),
        completed_frame_ids = normalized_frame_ids,
        completed = progress.completed or completed_value,
        completed_at = case
          when progress.completed or completed_value
            then coalesce(progress.completed_at, now())
          else null
        end
    where progress.id = progress_row.id
    returning * into progress_row;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'progress', jsonb_build_object(
      'module_code', progress_row.module_code,
      'walkthrough_id', progress_row.walkthrough_id,
      'current_frame_id', progress_row.current_frame_id,
      'position_seconds', progress_row.position_seconds,
      'completed_frame_ids', progress_row.completed_frame_ids,
      'completed', progress_row.completed,
      'completed_at', progress_row.completed_at,
      'updated_at', progress_row.updated_at,
      'version', progress_row.version
    )
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'training_walkthrough_progress_saved',
    'training_walkthrough',
    module_code_value || ':' || walkthrough_id_value,
    jsonb_build_object(
      'module_code', module_code_value,
      'walkthrough_id', walkthrough_id_value,
      'completed', progress_row.completed,
      'version', progress_row.version
    ),
    'training-progress:' || idempotency_key_value
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_save_training_progress',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

create or replace function public.creator_saved_work_views(
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
  action_value text := 'list';
  view_id_value uuid;
  name_value text;
  filters_value jsonb;
  make_default_value boolean := false;
  expected_version_value bigint;
  idempotency_key_value text;
  request_payload jsonb;
  replay jsonb;
  view_row content_factory.saved_work_views%rowtype;
  affected_id uuid;
  result_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 32768
     or p_payload - array[
       'organization_id', 'action', 'view_id', 'name', 'filters',
       'is_default', 'expected_version', 'idempotency_key'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'saved_work_views_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, null
  );
  action_value := lower(btrim(coalesce(
    p_payload ->> 'action', 'list'
  )));
  if action_value not in ('list', 'upsert', 'delete', 'set_default') then
    raise exception using
      errcode = '22023',
      message = 'saved_work_view_action_invalid';
  end if;

  if action_value = 'list' then
    if p_payload - array[
      'organization_id', 'action'
    ]::text[] <> '{}'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'saved_work_view_list_payload_invalid';
    end if;
    return jsonb_build_object(
      'ok', true,
      'organization_id', organization_id,
      'action', action_value,
      'views', content_factory_private.saved_work_views_json(
        organization_id, user_id
      )
    );
  end if;

  if action_value = 'upsert' then
    if p_payload - array[
      'organization_id', 'action', 'view_id', 'name', 'filters',
      'is_default', 'expected_version', 'idempotency_key'
    ]::text[] <> '{}'::jsonb then
      raise exception using
        errcode = '22023',
        message = 'saved_work_view_upsert_payload_invalid';
    end if;
  elsif p_payload - array[
    'organization_id', 'action', 'view_id', 'expected_version',
    'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'saved_work_view_mutation_payload_invalid';
  end if;

  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if p_payload ? 'view_id' then
    view_id_value := content_factory_private.require_uuid(
      p_payload, 'view_id'
    );
  end if;
  if p_payload ? 'expected_version' then
    if jsonb_typeof(p_payload -> 'expected_version') <> 'number'
       or coalesce(p_payload ->> 'expected_version', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023',
        message = 'saved_work_view_expected_version_invalid';
    end if;
    begin
      expected_version_value :=
        (p_payload ->> 'expected_version')::bigint;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023',
        message = 'saved_work_view_expected_version_invalid';
    end;
    if expected_version_value < 1 then
      raise exception using
        errcode = '22023',
        message = 'saved_work_view_expected_version_invalid';
    end if;
  end if;

  if action_value = 'upsert' then
    if p_payload ? 'is_default' then
      if jsonb_typeof(p_payload -> 'is_default') <> 'boolean' then
        raise exception using
          errcode = '22023',
          message = 'saved_work_view_is_default_invalid';
      end if;
      make_default_value := (p_payload ->> 'is_default')::boolean;
    end if;
    name_value := content_factory_private.require_text(
      p_payload, 'name', 2, 80
    );
    if name_value ~ '[[:cntrl:]]' then
      raise exception using
        errcode = '22023',
        message = 'saved_work_view_name_invalid';
    end if;
    filters_value := content_factory_private.normalize_work_filters(
      coalesce(p_payload -> 'filters', '{}'::jsonb)
    );
    request_payload := jsonb_build_object(
      'action', action_value,
      'view_id', view_id_value,
      'name', name_value,
      'filters', filters_value,
      'is_default', make_default_value,
      'expected_version', expected_version_value
    );
  else
    if view_id_value is null then
      raise exception using
        errcode = '22023',
        message = 'saved_work_view_id_required';
    end if;
    request_payload := jsonb_build_object(
      'action', action_value,
      'view_id', view_id_value,
      'expected_version', expected_version_value
    );
  end if;

  replay := content_factory_private.begin_command(
    organization_id,
    'creator_saved_work_views',
    idempotency_key_value,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('saved-work-views:' || user_id::text)
  );

  if action_value = 'upsert' and view_id_value is null then
    if (
      select count(*)
      from content_factory.saved_work_views view
      where view.organization_id = organization_id
        and view.profile_id = user_id
    ) >= 50 then
      raise exception using
        errcode = '54000',
        message = 'saved_work_view_limit_exceeded';
    end if;
    if make_default_value then
      update content_factory.saved_work_views view
      set is_default = false
      where view.organization_id = organization_id
        and view.profile_id = user_id
        and view.is_default;
    end if;
    begin
      insert into content_factory.saved_work_views (
        organization_id, profile_id, name, filters, is_default
      ) values (
        organization_id, user_id, name_value, filters_value,
        make_default_value
      )
      returning * into view_row;
    exception when unique_violation then
      raise exception using
        errcode = '23505',
        message = 'saved_work_view_name_conflict';
    end;
    affected_id := view_row.id;
  elsif action_value = 'upsert' then
    select view.*
      into view_row
    from content_factory.saved_work_views view
    where view.organization_id = organization_id
      and view.profile_id = user_id
      and view.id = view_id_value
    for update;
    if view_row.id is null then
      raise exception using
        errcode = 'P0002',
        message = 'saved_work_view_not_found';
    end if;
    if expected_version_value is not null
       and view_row.version <> expected_version_value then
      raise exception using
        errcode = '40001',
        message = 'saved_work_view_version_conflict';
    end if;
    if make_default_value then
      update content_factory.saved_work_views view
      set is_default = false
      where view.organization_id = organization_id
        and view.profile_id = user_id
        and view.is_default
        and view.id <> view_id_value;
    end if;
    begin
      update content_factory.saved_work_views view
      set name = name_value,
          filters = filters_value,
          is_default = case
            when make_default_value then true
            else view.is_default
          end
      where view.organization_id = organization_id
        and view.profile_id = user_id
        and view.id = view_id_value
      returning * into view_row;
    exception when unique_violation then
      raise exception using
        errcode = '23505',
        message = 'saved_work_view_name_conflict';
    end;
    affected_id := view_row.id;
  elsif action_value = 'delete' then
    delete from content_factory.saved_work_views view
    where view.organization_id = organization_id
      and view.profile_id = user_id
      and view.id = view_id_value
      and (
        expected_version_value is null
        or view.version = expected_version_value
      )
    returning view.id into affected_id;
    if affected_id is null then
      if exists (
        select 1
        from content_factory.saved_work_views view
        where view.organization_id = organization_id
          and view.profile_id = user_id
          and view.id = view_id_value
      ) then
        raise exception using
          errcode = '40001',
          message = 'saved_work_view_version_conflict';
      end if;
      raise exception using
        errcode = 'P0002',
        message = 'saved_work_view_not_found';
    end if;
  else
    select view.*
      into view_row
    from content_factory.saved_work_views view
    where view.organization_id = organization_id
      and view.profile_id = user_id
      and view.id = view_id_value
    for update;
    if view_row.id is null then
      raise exception using
        errcode = 'P0002',
        message = 'saved_work_view_not_found';
    end if;
    if expected_version_value is not null
       and view_row.version <> expected_version_value then
      raise exception using
        errcode = '40001',
        message = 'saved_work_view_version_conflict';
    end if;
    update content_factory.saved_work_views view
    set is_default = false
    where view.organization_id = organization_id
      and view.profile_id = user_id
      and view.is_default
      and view.id <> view_id_value;
    update content_factory.saved_work_views view
    set is_default = true
    where view.organization_id = organization_id
      and view.profile_id = user_id
      and view.id = view_id_value
    returning * into view_row;
    affected_id := view_row.id;
  end if;

  result_value := jsonb_build_object(
    'ok', true,
    'organization_id', organization_id,
    'action', action_value,
    'affected_view_id', affected_id,
    'views', content_factory_private.saved_work_views_json(
      organization_id, user_id
    )
  );
  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'saved_work_view_' || action_value,
    'saved_work_view',
    affected_id::text,
    jsonb_build_object(
      'action', action_value,
      'view_id', affected_id,
      'is_default', coalesce(view_row.is_default, false)
    ),
    'saved-work-view:' || idempotency_key_value
  );
  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_saved_work_views',
    idempotency_key_value,
    request_payload,
    result_value
  );
end;
$$;

revoke all on function public.creator_my_work(jsonb)
  from public, anon;
revoke all on function public.creator_notifications(jsonb)
  from public, anon;
revoke all on function public.creator_mark_notifications_read(jsonb)
  from public, anon;
revoke all on function public.creator_training_progress(jsonb)
  from public, anon;
revoke all on function public.creator_save_training_progress(jsonb)
  from public, anon;
revoke all on function public.creator_saved_work_views(jsonb)
  from public, anon;

grant execute on function public.creator_my_work(jsonb)
  to authenticated;
grant execute on function public.creator_notifications(jsonb)
  to authenticated;
grant execute on function public.creator_mark_notifications_read(jsonb)
  to authenticated;
grant execute on function public.creator_training_progress(jsonb)
  to authenticated;
grant execute on function public.creator_save_training_progress(jsonb)
  to authenticated;
grant execute on function public.creator_saved_work_views(jsonb)
  to authenticated;

revoke all on function public.system_emit_notification(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_emit_notification(jsonb)
  to service_role;

revoke all on all functions in schema content_factory_private
  from public, anon, authenticated;
grant execute on all functions in schema content_factory_private
  to service_role;

commit;
