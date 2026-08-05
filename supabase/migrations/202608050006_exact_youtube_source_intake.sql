begin;

-- A public YouTube URL identifies one source but does not contain the video's
-- frames or audio. Register that identity before any paid analysis, surface it
-- in Research and AI Center, and keep it fail-closed until lawful media is
-- attached through a later audited media event.
create table if not exists content_factory.research_exact_youtube_sources (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  video_id text not null check (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  canonical_url text not null check (
    canonical_url ~ '^https://youtube[.]com/watch[?]v=[A-Za-z0-9_-]{11}$'
  ),
  product_name text not null default '' check (length(product_name) <= 300),
  product_sku text not null default '' check (length(product_sku) <= 160),
  status text not null default 'awaiting_media' check (
    status = 'awaiting_media'
  ),
  media_required boolean not null default true check (media_required),
  requested_by uuid not null,
  idempotency_key text not null check (
    length(idempotency_key) between 8 and 180
  ),
  source_hash text not null check (source_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, project_id, video_id),
  unique (organization_id, idempotency_key),
  unique (source_hash),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, requested_by)
    references content_factory.memberships(organization_id, profile_id),
  check (right(canonical_url, 11) = video_id)
);

create index if not exists research_exact_youtube_project_created_idx
  on content_factory.research_exact_youtube_sources (
    organization_id, project_id, created_at desc, id desc
  );

alter table content_factory.research_exact_youtube_sources
  enable row level security;
revoke all on content_factory.research_exact_youtube_sources
  from public, anon, authenticated, service_role;
grant all on content_factory.research_exact_youtube_sources to service_role;

drop trigger if exists research_exact_youtube_source_append_only
  on content_factory.research_exact_youtube_sources;
create trigger research_exact_youtube_source_append_only
before update or delete on content_factory.research_exact_youtube_sources
for each row execute function
  content_factory_private.reject_research_ai_handoff_mutation();

create or replace function public.contentengine_register_exact_youtube_source(
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
  video_id_value text;
  canonical_url_value text;
  product_name_value text := '';
  product_sku_value text := '';
  idempotency_key_value text;
  source_hash_value text;
  source_row content_factory.research_exact_youtube_sources%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'video_id', 'canonical_url',
    'product_name', 'product_sku', 'idempotency_key'
  ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'project_id', 'video_id', 'canonical_url', 'idempotency_key'
     ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_source_payload_invalid';
  end if;

  actor_id_value := content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );

  video_id_value := content_factory_private.require_text(
    p_payload, 'video_id', 11, 11
  );
  canonical_url_value := content_factory_private.require_text(
    p_payload, 'canonical_url', 39, 80
  );
  idempotency_key_value := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  if video_id_value !~ '^[A-Za-z0-9_-]{11}$'
     or canonical_url_value
       <> 'https://youtube.com/watch?v=' || video_id_value then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_source_url_invalid';
  end if;

  if p_payload ? 'product_name' then
    product_name_value := left(
      regexp_replace(coalesce(p_payload ->> 'product_name', ''), '\s+', ' ', 'g'),
      300
    );
    product_name_value := btrim(product_name_value);
  end if;
  if p_payload ? 'product_sku' then
    product_sku_value := left(
      regexp_replace(coalesce(p_payload ->> 'product_sku', ''), '\s+', ' ', 'g'),
      160
    );
    product_sku_value := btrim(product_sku_value);
  end if;

  source_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'exact-youtube-source-intake-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'video_id', video_id_value,
    'canonical_url', canonical_url_value
  ));

  insert into content_factory.research_exact_youtube_sources (
    organization_id, project_id, video_id, canonical_url,
    product_name, product_sku, requested_by, idempotency_key, source_hash
  ) values (
    organization_id_value, project_id_value, video_id_value,
    canonical_url_value, product_name_value, product_sku_value,
    actor_id_value, idempotency_key_value, source_hash_value
  )
  on conflict (organization_id, project_id, video_id) do nothing
  returning * into source_row;

  if source_row.id is null then
    select source.* into source_row
    from content_factory.research_exact_youtube_sources source
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
      and source.video_id = video_id_value;
  end if;
  if source_row.id is null
     or source_row.canonical_url <> canonical_url_value
     or source_row.source_hash <> source_hash_value then
    raise exception using
      errcode = '23505',
      message = 'exact_youtube_source_conflict';
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'exact-youtube-source-intake-v1',
    'source', jsonb_build_object(
      'id', source_row.id,
      'project_id', source_row.project_id,
      'video_id', source_row.video_id,
      'canonical_url', source_row.canonical_url,
      'product_name', source_row.product_name,
      'product_sku', source_row.product_sku,
      'status', source_row.status,
      'media_required', source_row.media_required,
      'source_hash', source_row.source_hash,
      'created_at', source_row.created_at
    ),
    'contract', jsonb_build_object(
      'registered_in_research', true,
      'visible_in_ai_center', true,
      'url_is_video_evidence', false,
      'requires_lawful_mp4', true,
      'paid_analysis_allowed', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_register_exact_youtube_source(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_register_exact_youtube_source(jsonb)
  to authenticated, service_role;

create or replace function public.contentengine_exact_youtube_source_queue(
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
  organization_id_value uuid;
  project_id_value uuid;
  limit_value integer := 30;
  sources_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'project_id', 'limit'
  ]::text[] <> '{}'::jsonb
     or not p_payload ? 'project_id' then
    raise exception using
      errcode = '22023',
      message = 'exact_youtube_source_queue_payload_invalid';
  end if;

  perform content_factory_private.current_profile_id();
  organization_id_value :=
    content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id_value, true, null
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );

  if p_payload ? 'limit' then
    if jsonb_typeof(p_payload -> 'limit') <> 'number'
       or coalesce(p_payload ->> 'limit', '') !~ '^[0-9]{1,2}$'
       or (p_payload ->> 'limit')::integer not between 1 and 50 then
      raise exception using
        errcode = '22023',
        message = 'exact_youtube_source_queue_limit_invalid';
    end if;
    limit_value := (p_payload ->> 'limit')::integer;
  end if;

  select coalesce(jsonb_agg(item.payload order by item.created_at desc),
                  '[]'::jsonb)
  into sources_value
  from (
    select source.created_at, jsonb_build_object(
      'id', source.id,
      'project_id', source.project_id,
      'video_id', source.video_id,
      'canonical_url', source.canonical_url,
      'product_name', source.product_name,
      'product_sku', source.product_sku,
      'status', source.status,
      'media_required', source.media_required,
      'source_hash', source.source_hash,
      'created_at', source.created_at,
      'next_action', 'upload_lawful_mp4',
      'files_deep_link', '#/workspace/board?project_id='
        || source.project_id::text || '&youtube_source=' || source.id::text
    ) as payload
    from content_factory.research_exact_youtube_sources source
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
    order by source.created_at desc, source.id desc
    limit limit_value
  ) item;

  return jsonb_build_object(
    'ok', true,
    'version', 'exact-youtube-source-queue-v1',
    'project_id', project_id_value,
    'sources', sources_value,
    'contract', jsonb_build_object(
      'url_is_video_evidence', false,
      'requires_lawful_mp4', true,
      'unattached_source_affects_learning', false,
      'unattached_source_affects_generation', false,
      'external_call_started', false,
      'paid_call_started', false
    )
  );
end;
$$;

revoke all on function
  public.contentengine_exact_youtube_source_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_exact_youtube_source_queue(jsonb)
  to authenticated, service_role;

comment on table content_factory.research_exact_youtube_sources is
  'Exact YouTube source identities registered before paid analysis. URL-only rows remain awaiting_media and cannot affect learning or generation.';
comment on function public.contentengine_register_exact_youtube_source(jsonb) is
  'Idempotently registers a canonical YouTube video identity with zero external or paid calls.';
comment on function public.contentengine_exact_youtube_source_queue(jsonb) is
  'Returns project-scoped exact YouTube sources waiting for lawful media; no provider call is made.';

notify pgrst, 'reload schema';

commit;