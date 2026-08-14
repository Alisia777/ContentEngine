begin;

-- Operator-facing generation intakes are intentionally separate from paid
-- generation jobs. A saved intake may register intent and source identity, but
-- it cannot reserve budget, call a provider, or authorize a generation.

create or replace function
  content_factory_private.generation_intake_v2_media_ids_valid(
    p_value jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select
    jsonb_typeof(p_value) = 'array'
    and jsonb_array_length(p_value) between 0 and 10
    and not exists (
      select 1
      from jsonb_array_elements(p_value) item(value)
      where jsonb_typeof(item.value) <> 'string'
         or coalesce(item.value #>> '{}', '') !~
           '^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    )
    and jsonb_array_length(p_value) = (
      select count(distinct item.value #>> '{}')
      from jsonb_array_elements(p_value) item(value)
    )
$$;

revoke all on function
  content_factory_private.generation_intake_v2_media_ids_valid(jsonb)
  from public, anon, authenticated, service_role;

create table if not exists content_factory.generation_intakes_v2 (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  strategy_id text not null check (
    strategy_id in ('copy_video', 'avatar_video')
  ),
  legacy_strategy_id text not null check (
    legacy_strategy_id in ('viral_product_swap', 'viral_avatar_ugc')
  ),
  avatar_wishes text not null default '' check (
    length(avatar_wishes) <= 1200
  ),
  description text not null default '' check (
    length(description) <= 1200
  ),
  product_media_ids jsonb not null default '[]'::jsonb,
  status text not null default 'awaiting_source_media' check (
    status in (
      'awaiting_source_media',
      'source_media_ready',
      'awaiting_internal_preparation',
      'ready_for_generation_spec',
      'cancelled'
    )
  ),
  requested_by uuid not null,
  idempotency_key text not null check (
    length(idempotency_key) between 8 and 180
  ),
  input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, idempotency_key),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, source_id)
    references content_factory.research_exact_youtube_sources(
      organization_id, id
    ),
  foreign key (organization_id, requested_by)
    references content_factory.memberships(organization_id, profile_id),
  check (
    content_factory_private.generation_intake_v2_media_ids_valid(
      product_media_ids
    )
  ),
  check (
    (
      strategy_id = 'copy_video'
      and legacy_strategy_id = 'viral_product_swap'
      and avatar_wishes = ''
      and jsonb_array_length(product_media_ids) between 1 and 10
    )
    or
    (
      strategy_id = 'avatar_video'
      and legacy_strategy_id = 'viral_avatar_ugc'
      and length(avatar_wishes) between 10 and 1200
      and jsonb_array_length(product_media_ids) = 0
    )
  )
);

create index if not exists generation_intakes_v2_project_created_idx
  on content_factory.generation_intakes_v2 (
    organization_id, project_id, created_at desc, id desc
  );

alter table content_factory.generation_intakes_v2 enable row level security;
revoke all on content_factory.generation_intakes_v2
  from public, anon, authenticated, service_role;
grant all on content_factory.generation_intakes_v2 to service_role;

create or replace function
  content_factory_private.reject_generation_intake_v2_mutation()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'generation_intake_v2_append_only';
end;
$$;

revoke all on function
  content_factory_private.reject_generation_intake_v2_mutation()
  from public, anon, authenticated, service_role;

drop trigger if exists generation_intakes_v2_append_only
  on content_factory.generation_intakes_v2;
create trigger generation_intakes_v2_append_only
before update or delete on content_factory.generation_intakes_v2
for each row execute function
  content_factory_private.reject_generation_intake_v2_mutation();

create or replace function public.creator_save_generation_intake_v2(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  actor_id_value uuid;
  organization_id_value uuid;
  project_id_value uuid;
  source_id_value uuid;
  strategy_id_value text;
  legacy_strategy_id_value text;
  avatar_wishes_value text := '';
  description_value text := '';
  product_media_ids_value jsonb := '[]'::jsonb;
  idempotency_key_value text;
  input_hash_value text;
  source_row content_factory.research_exact_youtube_sources%rowtype;
  intake_row content_factory.generation_intakes_v2%rowtype;
  next_action_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'organization_id', 'project_id', 'source_id', 'strategy_id',
       'avatar_wishes', 'description', 'product_media_ids',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'source_id', 'strategy_id', 'idempotency_key'
     ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'generation_intake_v2_payload_invalid';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );
  source_id_value := content_factory_private.require_uuid(
    p_payload, 'source_id'
  );
  strategy_id_value := content_factory_private.require_text(
    p_payload, 'strategy_id', 1, 80
  );
  if strategy_id_value not in ('copy_video', 'avatar_video') then
    raise exception using
      errcode = '22023',
      message = 'generation_intake_v2_strategy_invalid';
  end if;
  legacy_strategy_id_value := case strategy_id_value
    when 'copy_video' then 'viral_product_swap'
    when 'avatar_video' then 'viral_avatar_ugc'
  end;

  if p_payload ? 'avatar_wishes' then
    if jsonb_typeof(p_payload -> 'avatar_wishes') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_intake_v2_avatar_wishes_invalid';
    end if;
    avatar_wishes_value := left(
      regexp_replace(
        coalesce(p_payload ->> 'avatar_wishes', ''),
        '[[:space:]]+', ' ', 'g'
      ),
      1200
    );
    avatar_wishes_value := btrim(avatar_wishes_value);
  end if;
  if p_payload ? 'description' then
    if jsonb_typeof(p_payload -> 'description') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_intake_v2_description_invalid';
    end if;
    description_value := left(
      regexp_replace(
        coalesce(p_payload ->> 'description', ''),
        '[[:space:]]+', ' ', 'g'
      ),
      1200
    );
    description_value := btrim(description_value);
  end if;
  if p_payload ? 'product_media_ids' then
    product_media_ids_value := p_payload -> 'product_media_ids';
  end if;
  if jsonb_typeof(product_media_ids_value) <> 'array'
     or jsonb_array_length(product_media_ids_value) > 10
     or exists (
       select 1
       from jsonb_array_elements(product_media_ids_value) item(value)
       where jsonb_typeof(item.value) <> 'string'
          or coalesce(item.value #>> '{}', '') !~
            '^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
     )
     or jsonb_array_length(product_media_ids_value) <> (
       select count(distinct item.value #>> '{}')
       from jsonb_array_elements(product_media_ids_value) item(value)
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_intake_v2_product_media_invalid';
  end if;
  if strategy_id_value = 'copy_video' then
    if avatar_wishes_value <> ''
       or jsonb_array_length(product_media_ids_value) not between 1 and 10 then
      raise exception using
        errcode = '22023',
        message = 'generation_intake_v2_copy_fields_invalid';
    end if;
  elsif length(avatar_wishes_value) not between 10 and 1200
        or jsonb_array_length(product_media_ids_value) <> 0 then
    raise exception using
      errcode = '22023',
      message = 'generation_intake_v2_avatar_fields_invalid';
  end if;

  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  select source.* into source_row
  from content_factory.research_exact_youtube_sources source
  where source.organization_id = organization_id_value
    and source.project_id = project_id_value
    and source.id = source_id_value;
  if source_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'generation_intake_v2_source_not_found';
  end if;

  input_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'generation-intake-v2',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'source_id', source_id_value,
    'source_hash', source_row.source_hash,
    'strategy_id', strategy_id_value,
    'legacy_strategy_id', legacy_strategy_id_value,
    'avatar_wishes', avatar_wishes_value,
    'description', description_value,
    'product_media_ids', product_media_ids_value
  ));

  insert into content_factory.generation_intakes_v2 (
    organization_id,
    project_id,
    source_id,
    strategy_id,
    legacy_strategy_id,
    avatar_wishes,
    description,
    product_media_ids,
    requested_by,
    idempotency_key,
    input_hash
  ) values (
    organization_id_value,
    project_id_value,
    source_id_value,
    strategy_id_value,
    legacy_strategy_id_value,
    avatar_wishes_value,
    description_value,
    product_media_ids_value,
    actor_id_value,
    idempotency_key_value,
    input_hash_value
  )
  on conflict (organization_id, idempotency_key) do nothing
  returning * into intake_row;

  if intake_row.id is null then
    select intake.* into intake_row
    from content_factory.generation_intakes_v2 intake
    where intake.organization_id = organization_id_value
      and intake.idempotency_key = idempotency_key_value;
  end if;
  if intake_row.id is null or intake_row.input_hash <> input_hash_value then
    raise exception using
      errcode = '23505',
      message = 'generation_intake_v2_idempotency_conflict';
  end if;

  next_action_value := case
    when source_row.status in ('ready', 'media_ready', 'analyzed') then
      'prepare_internal_references'
    else 'attach_lawful_mp4'
  end;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-intake-v2',
    'intake', jsonb_build_object(
      'id', intake_row.id,
      'project_id', intake_row.project_id,
      'source_id', intake_row.source_id,
      'strategy_id', intake_row.strategy_id,
      'legacy_strategy_id', intake_row.legacy_strategy_id,
      'status', intake_row.status,
      'product_media_count', jsonb_array_length(
        intake_row.product_media_ids
      ),
      'avatar_wishes_present', intake_row.avatar_wishes <> '',
      'description_present', intake_row.description <> '',
      'input_hash', intake_row.input_hash,
      'created_at', intake_row.created_at,
      'next_action', next_action_value
    ),
    'source', jsonb_build_object(
      'id', source_row.id,
      'canonical_url', source_row.canonical_url,
      'status', source_row.status,
      'media_required', source_row.media_required
    ),
    'contract', jsonb_build_object(
      'separate_operator_form', true,
      'provider_call_started', false,
      'paid_call_started', false,
      'budget_reserved', false,
      'browser_price_authority', false,
      'browser_provider_authority', false,
      'human_review_required', true
    )
  );
end;
$$;

revoke all on function public.creator_save_generation_intake_v2(jsonb)
  from public, anon;
grant execute on function public.creator_save_generation_intake_v2(jsonb)
  to authenticated, service_role;

comment on table content_factory.generation_intakes_v2 is
  'Append-only operator intakes for Copy video and Avatar video. Saving an intake never starts or pays for generation.';
comment on function public.creator_save_generation_intake_v2(jsonb) is
  'Validates and stores one compact generation intake after exact source registration; no provider or paid action.';

notify pgrst, 'reload schema';

commit;
