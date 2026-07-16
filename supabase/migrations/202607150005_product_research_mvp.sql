begin;

create table if not exists content_factory.product_research_runs (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    product_id uuid not null,
    created_by uuid not null,
    status text not null default 'queued'
      check (status in ('queued', 'processing', 'completed', 'failed', 'cancelled')),
    input jsonb not null check (jsonb_typeof(input) = 'object'),
    summary jsonb not null default '{}'::jsonb
      check (jsonb_typeof(summary) = 'object'),
    error_code text,
    error_message text,
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    completion_hash text check (completion_hash is null or completion_hash ~ '^[0-9a-f]{64}$'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    started_at timestamptz,
    lease_expires_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (organization_id, id),
    check (error_code is null or length(error_code) between 3 and 100),
    check (error_message is null or length(error_message) between 3 and 2000),
    check (
      (status = 'queued' and finished_at is null and lease_expires_at is null)
      or (status = 'processing' and finished_at is null and lease_expires_at is not null)
      or (
        status in ('completed', 'failed', 'cancelled')
        and finished_at is not null and lease_expires_at is null
      )
    ),
    check (status <> 'failed' or error_code is not null),
    check (status <> 'completed' or (error_code is null and error_message is null))
);

create index if not exists product_research_runs_queue_idx
  on content_factory.product_research_runs (status, created_at, id)
  where status in ('queued', 'processing');
create index if not exists product_research_runs_org_created_idx
  on content_factory.product_research_runs (organization_id, created_at desc, id desc);

create table if not exists content_factory.product_research_sources (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    product_id uuid not null,
    created_by uuid not null,
    source_type text not null check (source_type in (
      'user_input', 'product_photo', 'marketplace_page', 'review',
      'competitor', 'social_video', 'market_data', 'other'
    )),
    source_url text,
    media_object_id uuid,
    title text not null check (length(btrim(title)) between 2 and 300),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    trust_level text not null default 'unverified'
      check (trust_level in ('first_party', 'official', 'public', 'unverified')),
    extracted_facts jsonb not null default '[]'::jsonb
      check (jsonb_typeof(extracted_facts) = 'array'),
    metadata jsonb not null default '{}'::jsonb
      check (jsonb_typeof(metadata) = 'object'),
    fetched_at timestamptz,
    published_at timestamptz,
    created_at timestamptz not null default now(),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    unique (organization_id, id),
    unique (run_id, content_hash),
    check (source_url is null or (
      length(source_url) between 10 and 2048
      and source_url ~* '^https://[^[:space:]]+$'
    )),
    check (media_object_id is null or source_type = 'product_photo'),
    check (source_url is not null or media_object_id is not null or source_type = 'user_input'),
    check (length(extracted_facts::text) <= 65536),
    check (length(metadata::text) <= 32768)
);

create index if not exists product_research_sources_run_idx
  on content_factory.product_research_sources (organization_id, run_id, created_at, id);

create table if not exists content_factory.creative_brief_drafts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    product_id uuid not null,
    previous_draft_id uuid,
    created_by uuid not null,
    origin text not null check (origin in ('ai', 'human')),
    version integer not null check (version between 1 and 10000),
    status text not null default 'draft'
      check (status in ('draft', 'approved', 'superseded', 'rejected')),
    title text not null check (length(btrim(title)) between 3 and 240),
    brief jsonb not null check (jsonb_typeof(brief) = 'object'),
    source_ids jsonb not null check (jsonb_typeof(source_ids) = 'array'),
    task_blueprint jsonb not null check (jsonb_typeof(task_blueprint) = 'array'),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    approved_by uuid references content_factory.profiles(id),
    approved_at timestamptz,
    superseded_at timestamptz,
    created_at timestamptz not null default now(),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, previous_draft_id)
      references content_factory.creative_brief_drafts(organization_id, id),
    unique (organization_id, id),
    unique (run_id, version),
    check (jsonb_array_length(source_ids) between 1 and 100),
    check (jsonb_array_length(task_blueprint) between 1 and 20),
    check (length(brief::text) <= 131072),
    check (length(task_blueprint::text) <= 131072),
    check (
      (status = 'approved' and approved_by is not null and approved_at is not null)
      or (status <> 'approved' and approved_by is null and approved_at is null)
    ),
    check ((status = 'superseded') = (superseded_at is not null))
);

create index if not exists creative_brief_drafts_run_version_idx
  on content_factory.creative_brief_drafts (organization_id, run_id, version desc);
create unique index if not exists creative_brief_drafts_one_approved_idx
  on content_factory.creative_brief_drafts (run_id)
  where status = 'approved';

create table if not exists content_factory.creative_forecasts (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    run_id uuid not null,
    draft_id uuid not null,
    created_by uuid not null,
    forecast_kind text not null default 'pre_publish'
      check (forecast_kind in ('pre_publish', 'post_publish')),
    score numeric(5,2) not null check (score between 0 and 100),
    confidence numeric(4,3) not null check (confidence between 0 and 1),
    model_provider text not null check (length(btrim(model_provider)) between 2 and 80),
    model_version text not null check (length(btrim(model_version)) between 1 and 120),
    factors jsonb not null default '{}'::jsonb check (jsonb_typeof(factors) = 'object'),
    limitations jsonb not null default '[]'::jsonb check (jsonb_typeof(limitations) = 'array'),
    evidence_source_ids jsonb not null check (jsonb_typeof(evidence_source_ids) = 'array'),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    created_at timestamptz not null default now(),
    foreign key (organization_id, run_id)
      references content_factory.product_research_runs(organization_id, id),
    foreign key (organization_id, draft_id)
      references content_factory.creative_brief_drafts(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (organization_id, id),
    check (jsonb_array_length(evidence_source_ids) between 1 and 100),
    check (jsonb_array_length(limitations) <= 30),
    check (length(factors::text) <= 65536),
    check (length(limitations::text) <= 32768)
);

create index if not exists creative_forecasts_draft_idx
  on content_factory.creative_forecasts (organization_id, draft_id, created_at desc, id desc);

alter table content_factory.creator_tasks
  add column if not exists creative_brief_draft_id uuid;

do $constraint$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'content_factory.creator_tasks'::regclass
      and conname = 'creator_tasks_creative_brief_draft_fk'
  ) then
    alter table content_factory.creator_tasks
      add constraint creator_tasks_creative_brief_draft_fk
      foreign key (organization_id, creative_brief_draft_id)
      references content_factory.creative_brief_drafts(organization_id, id);
  end if;
end;
$constraint$;

create index if not exists creator_tasks_creative_brief_idx
  on content_factory.creator_tasks (organization_id, creative_brief_draft_id, created_at);

alter table content_factory.product_research_runs enable row level security;
alter table content_factory.product_research_sources enable row level security;
alter table content_factory.creative_brief_drafts enable row level security;
alter table content_factory.creative_forecasts enable row level security;

-- The tables are intentionally RPC-only. RLS remains a second boundary if the
-- content_factory schema is exposed in the future.
revoke all on content_factory.product_research_runs from public, anon, authenticated;
revoke all on content_factory.product_research_sources from public, anon, authenticated;
revoke all on content_factory.creative_brief_drafts from public, anon, authenticated;
revoke all on content_factory.creative_forecasts from public, anon, authenticated;
grant all on content_factory.product_research_runs to service_role;
grant all on content_factory.product_research_sources to service_role;
grant all on content_factory.creative_brief_drafts to service_role;
grant all on content_factory.creative_forecasts to service_role;

create or replace function content_factory_private.guard_research_run_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using errcode = '55000', message = 'research_run_deletion_forbidden';
  end if;
  if new.organization_id <> old.organization_id
     or new.product_id <> old.product_id
     or new.created_by <> old.created_by
     or new.input <> old.input
     or new.request_hash <> old.request_hash
     or new.idempotency_key <> old.idempotency_key
     or new.created_at <> old.created_at then
    raise exception using errcode = '55000', message = 'research_run_identity_immutable';
  end if;
  if old.status in ('completed', 'failed', 'cancelled') and new is distinct from old then
    raise exception using errcode = '55000', message = 'research_run_terminal';
  end if;
  if new.status <> old.status and not (
    (old.status = 'queued' and new.status in ('processing', 'cancelled'))
    or (old.status = 'processing' and new.status in ('completed', 'failed', 'cancelled'))
  ) then
    raise exception using errcode = '55000', message = 'research_status_transition_invalid';
  end if;
  if old.status = 'queued' and new.status = 'processing' then
    new.started_at := coalesce(new.started_at, now());
    new.lease_expires_at := coalesce(new.lease_expires_at, now() + interval '5 minutes');
  end if;
  if new.status in ('completed', 'failed', 'cancelled') and new.status <> old.status then
    new.finished_at := coalesce(new.finished_at, now());
    new.lease_expires_at := null;
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create or replace function public.creator_start_product_research(
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
  idempotency_key text;
  product_id_value uuid;
  sku_value text;
  product_name text;
  objective_value text;
  marketplace_url_value text;
  media_ids jsonb := coalesce(p_payload -> 'source_media_ids', '[]'::jsonb);
  platforms_value jsonb := coalesce(p_payload -> 'platforms', '[]'::jsonb);
  media_text text;
  media_id_value uuid;
  media_row content_factory.media_objects%rowtype;
  run_id_value uuid;
  source_count integer := 0;
  user_daily_count integer;
  organization_daily_count integer;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 131072 then
    raise exception using errcode = '22023', message = 'research_payload_too_large';
  end if;
  if p_payload - array[
    'organization_id', 'idempotency_key', 'product_id', 'sku', 'product_name',
    'objective', 'marketplace_url', 'source_media_ids', 'platforms'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'research_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  objective_value := content_factory_private.require_text(p_payload, 'objective', 3, 2000);
  marketplace_url_value := nullif(btrim(coalesce(p_payload ->> 'marketplace_url', '')), '');
  if marketplace_url_value is not null and (
    length(marketplace_url_value) > 2048
    or marketplace_url_value !~* '^https://[^[:space:]]+$'
  ) then
    raise exception using errcode = '22023', message = 'marketplace_url_invalid';
  end if;
  if jsonb_typeof(media_ids) <> 'array' or jsonb_array_length(media_ids) > 5 then
    raise exception using errcode = '22023', message = 'source_media_ids_invalid';
  end if;
  if jsonb_typeof(platforms_value) <> 'array'
     or jsonb_array_length(platforms_value) < 1
     or jsonb_array_length(platforms_value) > 8
     or exists (
       select 1 from jsonb_array_elements_text(platforms_value) platform(value)
       where platform.value not in ('instagram', 'youtube', 'vk', 'wildberries', 'ozon')
     ) then
    raise exception using errcode = '22023', message = 'platforms_invalid';
  end if;
  if marketplace_url_value is null and jsonb_array_length(media_ids) = 0 then
    raise exception using errcode = '22023', message = 'research_source_required';
  end if;

  if nullif(btrim(coalesce(p_payload ->> 'product_id', '')), '') is not null then
    product_id_value := content_factory_private.require_uuid(p_payload, 'product_id');
    select product.sku, product.title
      into sku_value, product_name
    from content_factory.products product
    where product.organization_id = organization_id
      and product.id = product_id_value
      and product.status = 'active';
    if sku_value is null then
      raise exception using errcode = '22023', message = 'product_not_found';
    end if;
  else
    sku_value := content_factory_private.require_text(p_payload, 'sku', 1, 120);
    product_name := content_factory_private.require_text(p_payload, 'product_name', 2, 240);
    insert into content_factory.products (
      organization_id, sku, title, status, created_by
    ) values (
      organization_id, sku_value, product_name, 'active', user_id
    )
    on conflict on constraint products_org_sku_uq do nothing
    returning id into product_id_value;
    if product_id_value is null then
      select product.id, product.title into product_id_value, product_name
      from content_factory.products product
      where product.organization_id = organization_id
        and product.sku = sku_value
        and product.status = 'active';
      if product_id_value is null then
        raise exception using errcode = '55000', message = 'product_upsert_failed';
      end if;
    end if;
  end if;

  request_payload := jsonb_build_object(
    'product_id', product_id_value,
    'objective', objective_value,
    'marketplace_url', marketplace_url_value,
    'source_media_ids', media_ids,
    'platforms', platforms_value
  );
  replay := content_factory_private.begin_command(
    organization_id, 'creator_start_product_research', idempotency_key, request_payload
  );
  if replay is not null then return replay; end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text), hashtext('product_research_quota:organization')
  );
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text || ':' || user_id::text),
    hashtext('product_research_quota:user')
  );
  select
    count(*) filter (where run.created_by = user_id)::integer,
    count(*)::integer
  into user_daily_count, organization_daily_count
  from content_factory.product_research_runs run
  where run.organization_id = organization_id
    and run.created_at >= now() - interval '24 hours';
  if user_daily_count >= 10 then
    raise exception using errcode = '54000', message = 'research_user_daily_limit';
  end if;
  if organization_daily_count >= 50 then
    raise exception using errcode = '54000', message = 'research_org_daily_limit';
  end if;

  insert into content_factory.product_research_runs (
    organization_id, product_id, created_by, status, input,
    request_hash, idempotency_key
  ) values (
    organization_id, product_id_value, user_id, 'queued', request_payload,
    content_factory_private.json_hash(request_payload), idempotency_key
  ) returning id into run_id_value;

  if marketplace_url_value is not null then
    insert into content_factory.product_research_sources (
      organization_id, run_id, product_id, created_by, source_type,
      source_url, title, content_hash, trust_level, metadata
    ) values (
      organization_id, run_id_value, product_id_value, user_id, 'marketplace_page',
      marketplace_url_value, 'Карточка товара',
      content_factory_private.json_hash(jsonb_build_object('url', marketplace_url_value)),
      'public', jsonb_build_object('input', true)
    );
    source_count := source_count + 1;
  end if;

  for media_text in select value from jsonb_array_elements_text(media_ids) loop
    begin media_id_value := media_text::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023', message = 'source_media_id_invalid';
    end;
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id
      and media.id = media_id_value
      and media.status = 'ready'
      and media.mime_type in ('image/jpeg', 'image/png', 'image/webp')
      and media.metadata ->> 'kind' in ('product_photo', 'packshot')
      and media.metadata -> 'rights_confirmed' is not distinct from 'true'::jsonb
      and (
        media.owner_id = user_id
        or actor_role = any(array['owner', 'admin', 'producer'])
      );
    if media_row.id is null then
      raise exception using errcode = '42501', message = 'research_media_not_allowed';
    end if;
    insert into content_factory.product_research_sources (
      organization_id, run_id, product_id, created_by, source_type,
      media_object_id, title, content_hash, trust_level, metadata
    ) values (
      organization_id, run_id_value, product_id_value, user_id, 'product_photo',
      media_row.id, 'Фото товара', media_row.sha256, 'first_party',
      jsonb_build_object('input', true, 'mime_type', media_row.mime_type)
    ) on conflict (run_id, content_hash) do nothing;
  end loop;

  select count(*)::integer into source_count
  from content_factory.product_research_sources source
  where source.organization_id = organization_id and source.run_id = run_id_value;

  result := jsonb_build_object(
    'ok', true,
    'run', jsonb_build_object(
      'id', run_id_value,
      'product_id', product_id_value,
      'status', 'queued',
      'source_count', source_count
    )
  );
  perform content_factory_private.emit_event(
    organization_id, user_id, 'product_research_started', 'product_research_run',
    run_id_value::text,
    jsonb_build_object('product_id', product_id_value, 'source_count', source_count),
    'product_research:' || idempotency_key
  );
  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_start_product_research',
    idempotency_key, request_payload, result
  );
end;
$$;

create or replace function public.creator_product_research_status(
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
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  sources_value jsonb;
  draft_value jsonb;
  forecasts_value jsonb;
  approval_value jsonb;
  approved_task_ids jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'run_id']::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'research_status_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');

  -- A run UUID is globally unique, so status polling does not need the browser
  -- to guess an organization.  The membership join deliberately makes an
  -- inaccessible run indistinguishable from a missing run.
  if nullif(btrim(coalesce(p_payload ->> 'organization_id', '')), '') is not null then
    organization_id := content_factory_private.resolve_organization(p_payload);
    actor_role := content_factory_private.membership_role(organization_id, false, null);
  else
    select run.organization_id, membership.role
      into organization_id, actor_role
    from content_factory.product_research_runs run
    join content_factory.memberships membership
      on membership.organization_id = run.organization_id
     and membership.profile_id = user_id
     and membership.status = 'active'
    join content_factory.organizations organization
      on organization.id = run.organization_id
     and organization.status = 'active'
    where run.id = run_id_value;
    if organization_id is null then
      raise exception using errcode = '22023', message = 'research_run_not_found';
    end if;
  end if;

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id and run.id = run_id_value;
  if run_row.id is null then
    raise exception using errcode = '22023', message = 'research_run_not_found';
  end if;
  if actor_role not in ('owner', 'admin', 'producer', 'reviewer')
     and run_row.created_by <> user_id then
    raise exception using errcode = '42501', message = 'research_run_not_allowed';
  end if;

  -- Never re-claim a paid call after an uncertain worker failure.  Expiration
  -- is terminal and a user must explicitly create a new run to spend again.
  if run_row.status = 'processing' and run_row.lease_expires_at <= now() then
    update content_factory.product_research_runs run
    set status = 'failed',
        error_code = 'processing_lease_expired',
        error_message = 'Analysis timed out safely. Start a new research run.'
    where run.organization_id = organization_id
      and run.id = run_id_value
      and run.status = 'processing'
      and run.lease_expires_at <= now()
    returning * into run_row;
    if not found then
      select run.* into run_row
      from content_factory.product_research_runs run
      where run.organization_id = organization_id and run.id = run_id_value;
    end if;
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', source.id,
    'source_type', source.source_type,
    'source_url', source.source_url,
    'media_object_id', source.media_object_id,
    'title', source.title,
    'trust_level', source.trust_level,
    'extracted_facts', source.extracted_facts,
    'metadata', source.metadata,
    'fetched_at', source.fetched_at,
    'published_at', source.published_at,
    'created_at', source.created_at
  ) order by source.created_at, source.id), '[]'::jsonb)
  into sources_value
  from content_factory.product_research_sources source
  where source.organization_id = organization_id and source.run_id = run_id_value;

  select jsonb_build_object(
    'id', draft.id, 'run_id', draft.run_id, 'version', draft.version,
    'origin', draft.origin, 'status', draft.status, 'title', draft.title,
    'brief', draft.brief, 'source_ids', draft.source_ids,
    'task_blueprint', draft.task_blueprint, 'content_hash', draft.content_hash,
    'created_at', draft.created_at, 'approved_at', draft.approved_at
  ) into draft_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id and draft.run_id = run_id_value
  order by draft.version desc limit 1;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', forecast.id, 'draft_id', forecast.draft_id,
    'forecast_kind', forecast.forecast_kind, 'score', forecast.score,
    'confidence', forecast.confidence, 'model_provider', forecast.model_provider,
    'model_version', forecast.model_version, 'factors', forecast.factors,
    'limitations', forecast.limitations,
    'evidence_source_ids', forecast.evidence_source_ids,
    'created_at', forecast.created_at
  ) order by forecast.created_at desc, forecast.id desc), '[]'::jsonb)
  into forecasts_value
  from content_factory.creative_forecasts forecast
  where forecast.organization_id = organization_id and forecast.run_id = run_id_value;

  if draft_value ->> 'status' = 'approved' then
    select coalesce(jsonb_agg(task.id order by task.created_at, task.id), '[]'::jsonb)
      into approved_task_ids
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.creative_brief_draft_id = (draft_value ->> 'id')::uuid;
  end if;
  approval_value := jsonb_build_object(
    'status', coalesce(draft_value ->> 'status', 'none'),
    'is_approved', coalesce(draft_value ->> 'status' = 'approved', false),
    'draft_id', draft_value -> 'id',
    'approved_at', draft_value -> 'approved_at',
    'task_count', jsonb_array_length(approved_task_ids),
    'task_ids', approved_task_ids
  );

  return jsonb_build_object(
    'ok', true,
    'run', jsonb_build_object(
      'id', run_row.id, 'product_id', run_row.product_id,
      'status', run_row.status, 'input', run_row.input,
      'summary', run_row.summary, 'error_code', run_row.error_code,
      'error_message', run_row.error_message, 'created_at', run_row.created_at,
      'started_at', run_row.started_at, 'lease_expires_at', run_row.lease_expires_at,
      'finished_at', run_row.finished_at
    ),
    'sources', sources_value,
    'latest_draft', draft_value,
    'forecasts', forecasts_value,
    'approval', approval_value,
    'task_ids', approved_task_ids
  );
end;
$$;

create or replace function content_factory_private.reject_immutable_research_row()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception using errcode = '55000', message = tg_table_name || '_immutable';
end;
$$;

create or replace function content_factory_private.guard_creative_brief_state()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception using errcode = '55000', message = 'creative_brief_deletion_forbidden';
  end if;
  if new.organization_id <> old.organization_id
     or new.run_id <> old.run_id
     or new.product_id <> old.product_id
     or new.previous_draft_id is distinct from old.previous_draft_id
     or new.created_by <> old.created_by
     or new.origin <> old.origin
     or new.version <> old.version
     or new.title <> old.title
     or new.brief <> old.brief
     or new.source_ids <> old.source_ids
     or new.task_blueprint <> old.task_blueprint
     or new.content_hash <> old.content_hash
     or new.created_at <> old.created_at then
    raise exception using errcode = '55000', message = 'creative_brief_payload_immutable';
  end if;
  if old.status <> 'draft' and new is distinct from old then
    raise exception using errcode = '55000', message = 'creative_brief_terminal';
  end if;
  if new.status <> old.status and not (
    old.status = 'draft' and new.status in ('approved', 'superseded', 'rejected')
  ) then
    raise exception using errcode = '55000', message = 'creative_brief_status_transition_invalid';
  end if;
  return new;
end;
$$;

drop trigger if exists guard_research_run_mutation on content_factory.product_research_runs;
create trigger guard_research_run_mutation
before update or delete on content_factory.product_research_runs
for each row execute function content_factory_private.guard_research_run_mutation();

drop trigger if exists reject_research_source_mutation on content_factory.product_research_sources;
create trigger reject_research_source_mutation
before update or delete on content_factory.product_research_sources
for each row execute function content_factory_private.reject_immutable_research_row();

drop trigger if exists guard_creative_brief_state on content_factory.creative_brief_drafts;
create trigger guard_creative_brief_state
before update or delete on content_factory.creative_brief_drafts
for each row execute function content_factory_private.guard_creative_brief_state();

drop trigger if exists reject_creative_forecast_mutation on content_factory.creative_forecasts;
create trigger reject_creative_forecast_mutation
before update or delete on content_factory.creative_forecasts
for each row execute function content_factory_private.reject_immutable_research_row();

create or replace function content_factory_private.validate_research_task_blueprint(value jsonb)
returns void
language plpgsql
stable
set search_path = ''
as $$
declare
  item jsonb;
  priority_value integer;
  payout_value bigint;
  due_value timestamptz;
begin
  if jsonb_typeof(value) <> 'array'
     or jsonb_array_length(value) < 1
     or jsonb_array_length(value) > 20
     or length(value::text) > 131072 then
    raise exception using errcode = '22023', message = 'task_blueprint_invalid';
  end if;
  for item in select element.value from jsonb_array_elements(value) as element(value) loop
    if jsonb_typeof(item) <> 'object'
       or length(btrim(coalesce(item ->> 'title', ''))) not between 3 and 240
       or length(coalesce(item ->> 'instructions', '')) > 12000
       or coalesce(item ->> 'task_type', 'general') not in
         ('video_review', 'placement', 'metrics', 'general') then
      raise exception using errcode = '22023', message = 'task_blueprint_invalid';
    end if;
    if nullif(item ->> 'assignee_id', '') is not null then
      begin perform (item ->> 'assignee_id')::uuid;
      exception when invalid_text_representation then
        raise exception using errcode = '22023', message = 'task_assignee_invalid';
      end;
    end if;
    if coalesce(item ->> 'priority', '3') !~ '^[1-5]$' then
      raise exception using errcode = '22023', message = 'task_priority_invalid';
    end if;
    priority_value := coalesce((item ->> 'priority')::integer, 3);
    if priority_value not between 1 and 5 then
      raise exception using errcode = '22023', message = 'task_priority_invalid';
    end if;
    if coalesce(item ->> 'payout_minor', '0') !~ '^[0-9]{1,12}$' then
      raise exception using errcode = '22023', message = 'task_payout_invalid';
    end if;
    payout_value := coalesce((item ->> 'payout_minor')::bigint, 0);
    if payout_value > 100000000 then
      raise exception using errcode = '22023', message = 'task_payout_invalid';
    end if;
    if nullif(item ->> 'due_at', '') is not null then
      begin due_value := (item ->> 'due_at')::timestamptz;
      exception when invalid_text_representation or datetime_field_overflow then
        raise exception using errcode = '22023', message = 'task_due_at_invalid';
      end;
      if due_value < now() - interval '5 minutes' or due_value > now() + interval '365 days' then
        raise exception using errcode = '22023', message = 'task_due_at_invalid';
      end if;
    end if;
  end loop;
end;
$$;

create or replace function public.system_claim_product_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  claimed_value boolean := false;
  product_value jsonb;
  photos_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['run_id']::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'research_claim_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');

  update content_factory.product_research_runs run
  set status = 'processing'
  where run.id = run_id_value and run.status = 'queued'
  returning * into run_row;
  if run_row.id is not null then
    claimed_value := true;
  else
    select run.* into run_row
    from content_factory.product_research_runs run
    where run.id = run_id_value;
  end if;
  if run_row.id is null then
    raise exception using errcode = '22023', message = 'research_run_not_found';
  end if;

  select jsonb_build_object(
    'id', product.id, 'sku', product.sku, 'name', product.title,
    'brand', product.metadata ->> 'brand',
    'description', product.metadata ->> 'description'
  ) into product_value
  from content_factory.products product
  where product.organization_id = run_row.organization_id
    and product.id = run_row.product_id;

  select coalesce(jsonb_agg(jsonb_build_object(
    'media_id', media.id,
    'object_name', media.object_name,
    'mime_type', media.mime_type,
    'product_id', run_row.product_id,
    'sha256', media.sha256,
    'size_bytes', media.size_bytes
  ) order by media.created_at, media.id), '[]'::jsonb)
  into photos_value
  from content_factory.media_objects media
  where media.organization_id = run_row.organization_id
    and media.status = 'ready'
    and media.mime_type in ('image/jpeg', 'image/png', 'image/webp')
    and media.metadata ->> 'kind' in ('product_photo', 'packshot')
    and media.metadata -> 'rights_confirmed' is not distinct from 'true'::jsonb
    and media.id in (
      select selected.value::uuid
      from jsonb_array_elements_text(
        run_row.input -> 'source_media_ids'
      ) as selected(value)
    );

  return jsonb_build_object(
    'ok', true,
    'claimed', claimed_value,
    'run', jsonb_build_object(
      'id', run_row.id,
      'status', run_row.status,
      'lease_expires_at', run_row.lease_expires_at,
      'organization_id', run_row.organization_id,
      'product_id', run_row.product_id,
      'creator_id', run_row.created_by,
      'input', run_row.input,
      'objective', run_row.input ->> 'objective',
      'marketplace_url', run_row.input ->> 'marketplace_url',
      'platforms', run_row.input -> 'platforms',
      'product', product_value,
      'photos', photos_value
    )
  );
end;
$$;

create or replace function public.system_complete_product_research(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  run_id_value uuid;
  status_value text;
  run_row content_factory.product_research_runs%rowtype;
  completion_payload jsonb;
  completion_hash_value text;
  summary_value jsonb := coalesce(p_payload -> 'summary', '{}'::jsonb);
  sources_value jsonb := coalesce(p_payload -> 'sources', '[]'::jsonb);
  draft_value jsonb := p_payload -> 'draft';
  forecast_value jsonb := p_payload -> 'forecast';
  item jsonb;
  source_type_value text;
  source_url_value text;
  media_object_id_value uuid;
  source_title_value text;
  source_hash_value text;
  trust_value text;
  facts_value jsonb;
  metadata_value jsonb;
  fetched_value timestamptz;
  published_value timestamptz;
  source_ids_value jsonb;
  previous_draft_id_value uuid;
  draft_id_value uuid;
  forecast_id_value uuid;
  version_value integer;
  task_blueprint_value jsonb;
  brief_value jsonb;
  title_value text;
  score_value numeric;
  confidence_value numeric;
  factors_value jsonb;
  limitations_value jsonb;
  error_code_value text;
  error_message_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 524288 then
    raise exception using errcode = '22023', message = 'research_completion_too_large';
  end if;
  if p_payload - array[
    'run_id', 'status', 'summary', 'sources', 'draft', 'forecast',
    'error_code', 'error_message'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'research_completion_payload_invalid';
  end if;
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  status_value := btrim(coalesce(p_payload ->> 'status', ''));
  if status_value not in ('completed', 'failed') then
    raise exception using errcode = '22023', message = 'research_completion_status_invalid';
  end if;
  completion_payload := p_payload - 'run_id';
  completion_hash_value := content_factory_private.json_hash(completion_payload);

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.id = run_id_value
  for update;
  if run_row.id is null then
    raise exception using errcode = '22023', message = 'research_run_not_found';
  end if;
  if run_row.status in ('completed', 'failed') then
    if run_row.completion_hash = completion_hash_value and run_row.status = status_value then
      select coalesce(jsonb_agg(source.id order by source.created_at, source.id), '[]'::jsonb)
        into source_ids_value
      from content_factory.product_research_sources source
      where source.organization_id = run_row.organization_id and source.run_id = run_id_value;
      select draft.id into draft_id_value
      from content_factory.creative_brief_drafts draft
      where draft.organization_id = run_row.organization_id and draft.run_id = run_id_value
        and draft.origin = 'ai'
      order by draft.version desc limit 1;
      select forecast.id into forecast_id_value
      from content_factory.creative_forecasts forecast
      where forecast.organization_id = run_row.organization_id
        and forecast.run_id = run_id_value
        and forecast.draft_id = draft_id_value
      order by forecast.created_at desc limit 1;
      return jsonb_build_object(
        'ok', true, 'run_id', run_id_value, 'status', status_value,
        'draft_id', draft_id_value, 'forecast_id', forecast_id_value,
        'source_ids', source_ids_value
      );
    end if;
    raise exception using errcode = '23505', message = 'research_completion_conflict';
  end if;
  if run_row.status <> 'processing' then
    raise exception using errcode = '55000', message = 'research_run_not_claimed';
  end if;

  if status_value = 'failed' then
    error_code_value := btrim(coalesce(p_payload ->> 'error_code', ''));
    error_message_value := nullif(btrim(coalesce(p_payload ->> 'error_message', '')), '');
    if length(error_code_value) not between 3 and 100
       or (error_message_value is not null and length(error_message_value) > 2000) then
      raise exception using errcode = '22023', message = 'research_error_invalid';
    end if;
    update content_factory.product_research_runs run
    set status = 'failed', error_code = error_code_value,
        error_message = error_message_value, completion_hash = completion_hash_value
    where run.id = run_id_value;
    select coalesce(jsonb_agg(source.id order by source.created_at, source.id), '[]'::jsonb)
      into source_ids_value
    from content_factory.product_research_sources source
    where source.organization_id = run_row.organization_id and source.run_id = run_id_value;
    return jsonb_build_object(
      'ok', true, 'run_id', run_id_value, 'status', 'failed',
      'draft_id', null, 'forecast_id', null, 'source_ids', source_ids_value
    );
  end if;

  if jsonb_typeof(summary_value) <> 'object' or length(summary_value::text) > 131072
     or jsonb_typeof(sources_value) <> 'array' or jsonb_array_length(sources_value) > 100 then
    raise exception using errcode = '22023', message = 'research_result_invalid';
  end if;
  for item in select element.value from jsonb_array_elements(sources_value) as element(value) loop
    if jsonb_typeof(item) <> 'object' then
      raise exception using errcode = '22023', message = 'research_source_invalid';
    end if;
    source_type_value := btrim(coalesce(item ->> 'source_type', ''));
    source_url_value := nullif(btrim(coalesce(item ->> 'source_url', '')), '');
    media_object_id_value := null;
    if nullif(btrim(coalesce(item ->> 'media_object_id', '')), '') is not null then
      begin media_object_id_value := (item ->> 'media_object_id')::uuid;
      exception when invalid_text_representation then
        raise exception using errcode = '22023', message = 'research_source_invalid';
      end;
    end if;
    source_title_value := btrim(coalesce(item ->> 'title', ''));
    trust_value := coalesce(nullif(btrim(item ->> 'trust_level'), ''), 'unverified');
    facts_value := coalesce(item -> 'extracted_facts', '[]'::jsonb);
    metadata_value := coalesce(item -> 'metadata', '{}'::jsonb);
    if source_type_value not in (
       'product_photo', 'user_input', 'marketplace_page', 'review',
       'competitor', 'social_video', 'market_data', 'other'
    ) or length(source_title_value) not between 2 and 300
       or trust_value not in ('first_party', 'official', 'public', 'unverified')
       or jsonb_typeof(facts_value) <> 'array' or length(facts_value::text) > 65536
       or jsonb_typeof(metadata_value) <> 'object' or length(metadata_value::text) > 32768 then
      raise exception using errcode = '22023', message = 'research_source_invalid';
    end if;
    if source_type_value = 'product_photo' then
      if source_url_value is not null or media_object_id_value is null
         or trust_value <> 'first_party'
         or not exists (
           select 1
           from content_factory.product_research_sources input_source
           where input_source.organization_id = run_row.organization_id
             and input_source.run_id = run_id_value
             and input_source.source_type = 'product_photo'
             and input_source.media_object_id = media_object_id_value
             and input_source.metadata -> 'input' is not distinct from 'true'::jsonb
         ) then
        raise exception using errcode = '22023', message = 'research_source_invalid';
      end if;
    elsif source_url_value is null or media_object_id_value is not null
       or length(source_url_value) > 2048
       or source_url_value !~* '^https://[^[:space:]]+$' then
      raise exception using errcode = '22023', message = 'research_source_invalid';
    end if;
    source_hash_value := nullif(btrim(coalesce(item ->> 'content_hash', '')), '');
    if source_hash_value is null then
      source_hash_value := content_factory_private.json_hash(jsonb_build_object(
        'source_url', source_url_value, 'media_object_id', media_object_id_value,
        'extracted_facts', facts_value, 'model_source_id', metadata_value -> 'model_source_id'
      ));
    elsif source_hash_value !~ '^[0-9a-f]{64}$' then
      raise exception using errcode = '22023', message = 'research_source_hash_invalid';
    end if;
    begin
      fetched_value := coalesce(nullif(item ->> 'fetched_at', '')::timestamptz, now());
      published_value := nullif(item ->> 'published_at', '')::timestamptz;
    exception when invalid_text_representation or datetime_field_overflow then
      raise exception using errcode = '22023', message = 'research_source_time_invalid';
    end;
    insert into content_factory.product_research_sources (
      organization_id, run_id, product_id, created_by, source_type,
      source_url, media_object_id, title, content_hash, trust_level, extracted_facts,
      metadata, fetched_at, published_at
    ) values (
      run_row.organization_id, run_id_value, run_row.product_id, run_row.created_by,
      source_type_value, source_url_value, media_object_id_value, source_title_value, source_hash_value,
      trust_value, facts_value, metadata_value, fetched_value, published_value
    ) on conflict (run_id, content_hash) do nothing;
  end loop;

  select coalesce(jsonb_agg(source.id order by source.created_at, source.id), '[]'::jsonb)
    into source_ids_value
  from content_factory.product_research_sources source
  where source.organization_id = run_row.organization_id and source.run_id = run_id_value;
  if jsonb_array_length(source_ids_value) < 1 then
    raise exception using errcode = '22023', message = 'research_source_required';
  end if;

  if draft_value is not null then
    if jsonb_typeof(draft_value) <> 'object' then
      raise exception using errcode = '22023', message = 'brief_invalid';
    end if;
    title_value := btrim(coalesce(draft_value ->> 'title', ''));
    brief_value := coalesce(draft_value -> 'brief', 'null'::jsonb);
    task_blueprint_value := coalesce(draft_value -> 'task_blueprint', 'null'::jsonb);
    if length(title_value) not between 3 and 240
       or jsonb_typeof(brief_value) <> 'object' or length(brief_value::text) > 131072 then
      raise exception using errcode = '22023', message = 'brief_invalid';
    end if;
    perform content_factory_private.validate_research_task_blueprint(task_blueprint_value);
    select draft.id, draft.version into previous_draft_id_value, version_value
    from content_factory.creative_brief_drafts draft
    where draft.organization_id = run_row.organization_id and draft.run_id = run_id_value
    order by draft.version desc limit 1;
    version_value := coalesce(version_value, 0) + 1;
    insert into content_factory.creative_brief_drafts (
      organization_id, run_id, product_id, previous_draft_id, created_by,
      origin, version, status, title, brief, source_ids, task_blueprint, content_hash
    ) values (
      run_row.organization_id, run_id_value, run_row.product_id,
      previous_draft_id_value, run_row.created_by, 'ai', version_value, 'draft',
      title_value, brief_value, source_ids_value, task_blueprint_value,
      content_factory_private.json_hash(jsonb_build_object(
        'title', title_value, 'brief', brief_value, 'source_ids', source_ids_value,
        'task_blueprint', task_blueprint_value
      ))
    ) returning id into draft_id_value;
  end if;

  if forecast_value is not null then
    if draft_id_value is null or jsonb_typeof(forecast_value) <> 'object'
       or coalesce(forecast_value ->> 'score', '') !~ '^[0-9]+([.][0-9]+)?$'
       or coalesce(forecast_value ->> 'confidence', '') !~ '^(0([.][0-9]+)?|1([.]0+)?)$' then
      raise exception using errcode = '22023', message = 'forecast_invalid';
    end if;
    score_value := (forecast_value ->> 'score')::numeric;
    confidence_value := (forecast_value ->> 'confidence')::numeric;
    factors_value := coalesce(forecast_value -> 'factors', '{}'::jsonb);
    limitations_value := coalesce(forecast_value -> 'limitations', '[]'::jsonb);
    if score_value not between 0 and 100 or confidence_value not between 0 and 1
       or length(btrim(coalesce(forecast_value ->> 'model_provider', ''))) not between 2 and 80
       or length(btrim(coalesce(forecast_value ->> 'model_version', ''))) not between 1 and 120
       or jsonb_typeof(factors_value) <> 'object'
       or jsonb_typeof(limitations_value) <> 'array'
       or jsonb_array_length(limitations_value) > 30 then
      raise exception using errcode = '22023', message = 'forecast_invalid';
    end if;
    insert into content_factory.creative_forecasts (
      organization_id, run_id, draft_id, created_by, forecast_kind,
      score, confidence, model_provider, model_version, factors,
      limitations, evidence_source_ids, idempotency_key
    ) values (
      run_row.organization_id, run_id_value, draft_id_value, run_row.created_by,
      'pre_publish', score_value, confidence_value,
      btrim(forecast_value ->> 'model_provider'),
      btrim(forecast_value ->> 'model_version'), factors_value,
      limitations_value, source_ids_value,
      'system_forecast:' || content_factory_private.json_hash(jsonb_build_object(
        'run_id', run_id_value, 'completion_hash', completion_hash_value
      ))
    ) returning id into forecast_id_value;
  end if;

  update content_factory.product_research_runs run
  set status = 'completed', summary = summary_value,
      error_code = null, error_message = null, completion_hash = completion_hash_value
  where run.id = run_id_value;

  return jsonb_build_object(
    'ok', true, 'run_id', run_id_value, 'status', 'completed',
    'draft_id', draft_id_value, 'forecast_id', forecast_id_value,
    'source_ids', source_ids_value
  );
end;
$$;

create or replace function public.creator_save_creative_brief_draft(
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
  idempotency_key text;
  run_id_value uuid;
  run_row content_factory.product_research_runs%rowtype;
  title_value text;
  brief_value jsonb := coalesce(p_payload -> 'brief', 'null'::jsonb);
  source_ids_value jsonb := coalesce(p_payload -> 'source_ids', 'null'::jsonb);
  task_blueprint_value jsonb := coalesce(p_payload -> 'task_blueprint', 'null'::jsonb);
  forecast_value jsonb := p_payload -> 'forecast';
  source_text text;
  source_id_value uuid;
  source_input_count integer;
  source_found_count integer;
  previous_draft_id_value uuid;
  version_value integer;
  draft_id_value uuid;
  forecast_id_value uuid;
  score_value numeric;
  confidence_value numeric;
  model_provider_value text;
  model_version_value text;
  factors_value jsonb;
  limitations_value jsonb;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if length(p_payload::text) > 262144 then
    raise exception using errcode = '22023', message = 'creative_brief_payload_too_large';
  end if;
  if p_payload - array[
    'organization_id', 'idempotency_key', 'run_id', 'title', 'brief',
    'source_ids', 'task_blueprint', 'forecast'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'creative_brief_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, false, array['owner', 'admin', 'producer', 'reviewer']
  );
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  run_id_value := content_factory_private.require_uuid(p_payload, 'run_id');
  title_value := content_factory_private.require_text(p_payload, 'title', 3, 240);
  if jsonb_typeof(brief_value) <> 'object' or length(brief_value::text) > 131072 then
    raise exception using errcode = '22023', message = 'brief_invalid';
  end if;
  if jsonb_typeof(source_ids_value) <> 'array'
     or jsonb_array_length(source_ids_value) < 1
     or jsonb_array_length(source_ids_value) > 100 then
    raise exception using errcode = '22023', message = 'source_ids_invalid';
  end if;
  perform content_factory_private.validate_research_task_blueprint(task_blueprint_value);

  select run.* into run_row
  from content_factory.product_research_runs run
  where run.organization_id = organization_id and run.id = run_id_value;
  if run_row.id is null then
    raise exception using errcode = '22023', message = 'research_run_not_found';
  end if;
  if run_row.status <> 'completed' then
    raise exception using errcode = '55000', message = 'research_run_not_completed';
  end if;

  for source_text in select value from jsonb_array_elements_text(source_ids_value) loop
    begin source_id_value := source_text::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023', message = 'source_id_invalid';
    end;
  end loop;
  select count(distinct value)::integer into source_input_count
  from jsonb_array_elements_text(source_ids_value);
  select count(*)::integer into source_found_count
  from content_factory.product_research_sources source
  where source.organization_id = organization_id
    and source.run_id = run_id_value
    and source.id in (
      select value::uuid from jsonb_array_elements_text(source_ids_value)
    );
  if source_input_count <> source_found_count then
    raise exception using errcode = '42501', message = 'brief_source_mismatch';
  end if;

  if forecast_value is not null then
    if jsonb_typeof(forecast_value) <> 'object'
       or coalesce(forecast_value ->> 'score', '') !~ '^[0-9]+([.][0-9]+)?$'
       or coalesce(forecast_value ->> 'confidence', '') !~ '^(0([.][0-9]+)?|1([.]0+)?)$' then
      raise exception using errcode = '22023', message = 'forecast_invalid';
    end if;
    score_value := (forecast_value ->> 'score')::numeric;
    confidence_value := (forecast_value ->> 'confidence')::numeric;
    if score_value not between 0 and 100 or confidence_value not between 0 and 1 then
      raise exception using errcode = '22023', message = 'forecast_invalid';
    end if;
    model_provider_value := btrim(coalesce(forecast_value ->> 'model_provider', 'human'));
    model_version_value := btrim(coalesce(forecast_value ->> 'model_version', 'manual-v1'));
    factors_value := coalesce(forecast_value -> 'factors', '{}'::jsonb);
    limitations_value := coalesce(forecast_value -> 'limitations', '[]'::jsonb);
    if length(model_provider_value) not between 2 and 80
       or length(model_version_value) not between 1 and 120
       or jsonb_typeof(factors_value) <> 'object'
       or jsonb_typeof(limitations_value) <> 'array'
       or jsonb_array_length(limitations_value) > 30
       or length(factors_value::text) > 65536
       or length(limitations_value::text) > 32768 then
      raise exception using errcode = '22023', message = 'forecast_invalid';
    end if;
  end if;

  request_payload := jsonb_build_object(
    'run_id', run_id_value, 'title', title_value, 'brief', brief_value,
    'source_ids', source_ids_value, 'task_blueprint', task_blueprint_value,
    'forecast', forecast_value
  );
  replay := content_factory_private.begin_command(
    organization_id, 'creator_save_creative_brief_draft', idempotency_key, request_payload
  );
  if replay is not null then return replay; end if;
  perform pg_advisory_xact_lock(hashtext(organization_id::text), hashtext('brief:' || run_id_value::text));

  if exists (
    select 1 from content_factory.creative_brief_drafts draft
    where draft.organization_id = organization_id
      and draft.run_id = run_id_value
      and draft.status = 'approved'
  ) then
    raise exception using errcode = '55000', message = 'creative_brief_already_approved';
  end if;

  select draft.id, draft.version into previous_draft_id_value, version_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id and draft.run_id = run_id_value
  order by draft.version desc limit 1;
  version_value := coalesce(version_value, 0) + 1;

  insert into content_factory.creative_brief_drafts (
    organization_id, run_id, product_id, previous_draft_id, created_by,
    origin, version, status, title, brief, source_ids, task_blueprint, content_hash
  ) values (
    organization_id, run_id_value, run_row.product_id, previous_draft_id_value, user_id,
    'human', version_value, 'draft', title_value, brief_value, source_ids_value,
    task_blueprint_value,
    content_factory_private.json_hash(jsonb_build_object(
      'title', title_value, 'brief', brief_value, 'source_ids', source_ids_value,
      'task_blueprint', task_blueprint_value
    ))
  ) returning id into draft_id_value;

  if forecast_value is not null then
    insert into content_factory.creative_forecasts (
      organization_id, run_id, draft_id, created_by, forecast_kind,
      score, confidence, model_provider, model_version, factors,
      limitations, evidence_source_ids, idempotency_key
    ) values (
      organization_id, run_id_value, draft_id_value, user_id, 'pre_publish',
      score_value, confidence_value, model_provider_value, model_version_value,
      factors_value, limitations_value, source_ids_value,
      'draft_forecast:' || content_factory_private.json_hash(jsonb_build_object(
        'draft_id', draft_id_value, 'idempotency_key', idempotency_key
      ))
    ) returning id into forecast_id_value;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'draft', jsonb_build_object(
      'id', draft_id_value, 'run_id', run_id_value, 'version', version_value,
      'status', 'draft', 'content_hash', content_factory_private.json_hash(
        jsonb_build_object('title', title_value, 'brief', brief_value,
          'source_ids', source_ids_value, 'task_blueprint', task_blueprint_value)
      )
    ),
    'forecast_id', forecast_id_value
  );
  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_save_creative_brief_draft',
    idempotency_key, request_payload, result
  );
end;
$$;

create or replace function public.creator_approve_creative_brief(
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
  idempotency_key text;
  draft_id_value uuid;
  draft_run_id_value uuid;
  draft_row content_factory.creative_brief_drafts%rowtype;
  latest_version integer;
  item jsonb;
  ordinal_value integer := 0;
  assignee_id_value uuid;
  task_id_value uuid;
  task_ids jsonb := '[]'::jsonb;
  payout_value bigint;
  due_value timestamptz;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'idempotency_key', 'draft_id'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'creative_brief_approval_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  idempotency_key := content_factory_private.require_text(p_payload, 'idempotency_key', 8, 180);
  draft_id_value := content_factory_private.require_uuid(p_payload, 'draft_id');
  request_payload := jsonb_build_object('draft_id', draft_id_value);
  replay := content_factory_private.begin_command(
    organization_id, 'creator_approve_creative_brief', idempotency_key, request_payload
  );
  if replay is not null then return replay; end if;

  perform pg_advisory_xact_lock(hashtext(organization_id::text), hashtext('approve:' || draft_id_value::text));
  select draft.run_id into draft_run_id_value
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id and draft.id = draft_id_value;
  if draft_run_id_value is null then
    raise exception using errcode = '22023', message = 'creative_brief_not_found';
  end if;
  perform pg_advisory_xact_lock(
    hashtext(organization_id::text), hashtext('brief:' || draft_run_id_value::text)
  );
  select draft.* into draft_row
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id and draft.id = draft_id_value
  for update;
  if draft_row.id is null then
    raise exception using errcode = '22023', message = 'creative_brief_not_found';
  end if;
  if draft_row.status = 'approved' then
    select coalesce(jsonb_agg(task.id order by task.created_at, task.id), '[]'::jsonb)
      into task_ids
    from content_factory.creator_tasks task
    where task.organization_id = organization_id
      and task.creative_brief_draft_id = draft_id_value;
    result := jsonb_build_object(
      'ok', true, 'already_approved', true, 'draft_id', draft_id_value,
      'run_id', draft_row.run_id, 'product_id', draft_row.product_id,
      'source_ids', draft_row.source_ids, 'task_ids', task_ids
    );
    return content_factory_private.finish_command(
      organization_id, user_id, 'creator_approve_creative_brief',
      idempotency_key, request_payload, result
    );
  end if;
  if draft_row.status <> 'draft' then
    raise exception using errcode = '55000', message = 'creative_brief_not_approvable';
  end if;
  select max(draft.version) into latest_version
  from content_factory.creative_brief_drafts draft
  where draft.organization_id = organization_id and draft.run_id = draft_row.run_id;
  if draft_row.version <> latest_version then
    raise exception using errcode = '55000', message = 'creative_brief_not_latest';
  end if;

  perform content_factory_private.validate_research_task_blueprint(draft_row.task_blueprint);
  for item in
    select element.value
    from jsonb_array_elements(draft_row.task_blueprint) as element(value)
  loop
    ordinal_value := ordinal_value + 1;
    assignee_id_value := coalesce(nullif(item ->> 'assignee_id', '')::uuid, user_id);
    payout_value := coalesce((item ->> 'payout_minor')::bigint, 0);
    if payout_value > 0 and actor_role not in ('owner', 'admin') then
      raise exception using errcode = '42501', message = 'payout_role_not_allowed';
    end if;
    if not exists (
      select 1 from content_factory.memberships membership
      join content_factory.profiles profile on profile.id = membership.profile_id
        and profile.status = 'active'
      where membership.organization_id = organization_id
        and membership.profile_id = assignee_id_value
        and membership.status = 'active'
    ) then
      raise exception using errcode = '42501', message = 'task_assignee_not_active';
    end if;
    due_value := case when nullif(item ->> 'due_at', '') is null then null
      else (item ->> 'due_at')::timestamptz end;
    insert into content_factory.creator_tasks (
      organization_id, assignee_id, created_by, product_id,
      creative_brief_draft_id, task_type, title, instructions,
      status, priority, payout_minor, due_at, result, idempotency_key
    ) values (
      organization_id, assignee_id_value, user_id, draft_row.product_id,
      draft_id_value, coalesce(item ->> 'task_type', 'general'), item ->> 'title',
      nullif(item ->> 'instructions', ''), 'todo',
      coalesce((item ->> 'priority')::integer, 3), payout_value, due_value,
      jsonb_build_object(
        'product_research_run_id', draft_row.run_id,
        'creative_brief_draft_id', draft_id_value,
        'brief_version', draft_row.version,
        'source_ids', draft_row.source_ids,
        'blueprint_ordinal', ordinal_value
      ),
      'research_task:' || content_factory_private.json_hash(jsonb_build_object(
        'draft_id', draft_id_value, 'ordinal', ordinal_value
      ))
    ) returning id into task_id_value;
    task_ids := task_ids || jsonb_build_array(task_id_value);
  end loop;

  update content_factory.creative_brief_drafts draft
  set status = 'superseded', superseded_at = now()
  where draft.organization_id = organization_id
    and draft.run_id = draft_row.run_id
    and draft.id <> draft_id_value
    and draft.status = 'draft';
  update content_factory.creative_brief_drafts draft
  set status = 'approved', approved_by = user_id, approved_at = now()
  where draft.organization_id = organization_id and draft.id = draft_id_value;

  result := jsonb_build_object(
    'ok', true, 'already_approved', false, 'draft_id', draft_id_value,
    'run_id', draft_row.run_id, 'product_id', draft_row.product_id,
    'source_ids', draft_row.source_ids, 'task_ids', task_ids
  );
  perform content_factory_private.emit_event(
    organization_id, user_id, 'creative_brief_approved', 'creative_brief_draft',
    draft_id_value::text, jsonb_build_object(
      'run_id', draft_row.run_id, 'task_count', jsonb_array_length(task_ids)
    ), 'creative_brief_approved:' || draft_id_value::text
  );
  return content_factory_private.finish_command(
    organization_id, user_id, 'creator_approve_creative_brief',
    idempotency_key, request_payload, result
  );
end;
$$;

revoke all on function public.creator_start_product_research(jsonb) from public, anon;
revoke all on function public.creator_product_research_status(jsonb) from public, anon;
revoke all on function public.creator_save_creative_brief_draft(jsonb) from public, anon;
revoke all on function public.creator_approve_creative_brief(jsonb) from public, anon;
grant execute on function public.creator_start_product_research(jsonb) to authenticated;
grant execute on function public.creator_product_research_status(jsonb) to authenticated;
grant execute on function public.creator_save_creative_brief_draft(jsonb) to authenticated;
grant execute on function public.creator_approve_creative_brief(jsonb) to authenticated;

revoke all on function public.system_claim_product_research(jsonb)
  from public, anon, authenticated;
revoke all on function public.system_complete_product_research(jsonb)
  from public, anon, authenticated;
grant execute on function public.system_claim_product_research(jsonb) to service_role;
grant execute on function public.system_complete_product_research(jsonb) to service_role;

revoke all on all functions in schema content_factory_private
  from public, anon, authenticated;
grant execute on all functions in schema content_factory_private to service_role;

commit;
