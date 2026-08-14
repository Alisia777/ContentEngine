begin;

-- Three business strategies are creative-input authority, not provider/model
-- selection authority.  Keep them in their own append-only ledgers so the
-- strict generation-selection-snapshot-v1 contract and every historical row
-- remain unchanged.

create or replace function
  content_factory_private.generation_strategy_role_order(p_role text)
returns integer
language sql
immutable
strict
set search_path = ''
as $$
  select case p_role
    when 'product_primary' then 1
    when 'product_reference' then 2
    when 'creator_avatar' then 3
    when 'original_product' then 4
    when 'source_video' then 5
    when 'style_reference' then 6
    else 100
  end
$$;

revoke all on function
  content_factory_private.generation_strategy_role_order(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_strategy_asset_snapshot_valid(
    p_value jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select
    jsonb_typeof(p_value) = 'array'
    and jsonb_array_length(p_value) between 1 and 16
    and not exists (
      select 1
      from jsonb_array_elements(p_value) asset(value)
      where jsonb_typeof(asset.value) <> 'object'
         or asset.value - array[
              'role', 'ordinal', 'media_object_id', 'sha256', 'kind',
              'mime_type', 'product_id', 'rights_confirmed',
              'likeness_consent'
            ]::text[] <> '{}'::jsonb
         or not asset.value ?& array[
              'role', 'ordinal', 'media_object_id', 'sha256', 'kind',
              'mime_type', 'product_id', 'rights_confirmed',
              'likeness_consent'
            ]::text[]
         or asset.value ->> 'role' not in (
              'product_primary', 'product_reference', 'creator_avatar',
              'original_product', 'source_video', 'style_reference'
            )
         or jsonb_typeof(asset.value -> 'ordinal') <> 'number'
         or coalesce(asset.value ->> 'ordinal', '') !~ '^[1-9][0-9]?$'
         or coalesce(asset.value ->> 'media_object_id', '') !~
              '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
         or coalesce(asset.value ->> 'sha256', '') !~ '^[0-9a-f]{64}$'
         or asset.value ->> 'kind' not in (
              'product_photo', 'packshot', 'creator_reference', 'source_video'
            )
         or asset.value ->> 'mime_type' not in (
              'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
            )
         or jsonb_typeof(asset.value -> 'product_id') not in ('string', 'null')
         or (
              jsonb_typeof(asset.value -> 'product_id') = 'string'
              and coalesce(asset.value ->> 'product_id', '') !~
                '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
            )
         or asset.value -> 'rights_confirmed' is distinct from 'true'::jsonb
         or jsonb_typeof(asset.value -> 'likeness_consent') <> 'boolean'
    )
    and jsonb_array_length(p_value) = (
      select count(distinct (
        asset.value ->> 'role', asset.value ->> 'ordinal'
      ))
      from jsonb_array_elements(p_value) asset(value)
    )
    and jsonb_array_length(p_value) = (
      select count(distinct asset.value ->> 'media_object_id')
      from jsonb_array_elements(p_value) asset(value)
    )
$$;

revoke all on function
  content_factory_private.generation_strategy_asset_snapshot_valid(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_strategy_source_snapshot_valid(
    p_basis text,
    p_value jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select case p_basis
    when 'ai_research_recommendation' then
      jsonb_typeof(p_value) = 'object'
      and p_value - array[
        'basis', 'binding_id', 'binding_hash', 'selection_id',
        'selection_hash', 'recommendation_position', 'recommendation_hash'
      ]::text[] = '{}'::jsonb
      and p_value ?& array[
        'basis', 'binding_id', 'binding_hash', 'selection_id',
        'selection_hash', 'recommendation_position', 'recommendation_hash'
      ]::text[]
      and p_value ->> 'basis' = p_basis
      and p_value ->> 'binding_hash' ~ '^[0-9a-f]{64}$'
      and p_value ->> 'selection_hash' ~ '^[0-9a-f]{64}$'
      and p_value ->> 'recommendation_hash' ~ '^[0-9a-f]{64}$'
      and p_value ->> 'recommendation_position' ~ '^[1-3]$'
    when 'operator_summary_only' then
      jsonb_typeof(p_value) = 'object'
      and p_value - array[
        'basis', 'binding_id', 'binding_hash', 'reference_hash',
        'analysis_basis', 'ai_watched', 'evidence_verified'
      ]::text[] = '{}'::jsonb
      and p_value ?& array[
        'basis', 'binding_id', 'binding_hash', 'reference_hash',
        'analysis_basis', 'ai_watched', 'evidence_verified'
      ]::text[]
      and p_value ->> 'basis' = p_basis
      and p_value ->> 'binding_hash' ~ '^[0-9a-f]{64}$'
      and p_value ->> 'reference_hash' ~ '^[0-9a-f]{64}$'
      and p_value ->> 'analysis_basis' = 'operator_summary'
      and p_value -> 'ai_watched' = 'false'::jsonb
      and p_value -> 'evidence_verified' = 'false'::jsonb
    when 'exact_source_video' then
      jsonb_typeof(p_value) = 'object'
      and p_value - array[
        'basis', 'binding_id', 'binding_hash', 'source_id', 'source_hash',
        'media_object_id', 'media_sha256'
      ]::text[] = '{}'::jsonb
      and p_value ?& array[
        'basis', 'binding_id', 'binding_hash', 'source_id', 'source_hash',
        'media_object_id', 'media_sha256'
      ]::text[]
      and p_value ->> 'basis' = p_basis
      and p_value ->> 'binding_hash' ~ '^[0-9a-f]{64}$'
      and p_value ->> 'source_hash' ~ '^[0-9a-f]{64}$'
      and p_value ->> 'media_sha256' ~ '^[0-9a-f]{64}$'
    else false
  end
$$;

revoke all on function
  content_factory_private.generation_strategy_source_snapshot_valid(
    text, jsonb
  ) from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_spec_strategy_snapshot_valid(
    p_value jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select
    jsonb_typeof(p_value) = 'object'
    and p_value - array[
      'version', 'strategy_id', 'selection_hash', 'source_basis', 'spec',
      'product_id', 'source', 'role_assets', 'attestations'
    ]::text[] = '{}'::jsonb
    and p_value ?& array[
      'version', 'strategy_id', 'selection_hash', 'source_basis', 'spec',
      'product_id', 'source', 'role_assets', 'attestations'
    ]::text[]
    and p_value ->> 'version' = 'generation-spec-strategy-snapshot-v1'
    and p_value ->> 'strategy_id' in (
      'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
    )
    and p_value ->> 'selection_hash' ~ '^[0-9a-f]{64}$'
    and p_value ->> 'source_basis' in (
      'ai_research_recommendation', 'operator_summary_only',
      'exact_source_video'
    )
    and jsonb_typeof(p_value -> 'spec') = 'object'
    and (p_value -> 'spec') - array[
      'spec_id', 'spec_version', 'spec_hash', 'prompt_hash'
    ]::text[] = '{}'::jsonb
    and (p_value -> 'spec') ?& array[
      'spec_id', 'spec_version', 'spec_hash', 'prompt_hash'
    ]::text[]
    and p_value #>> '{spec,spec_hash}' ~ '^[0-9a-f]{64}$'
    and p_value #>> '{spec,prompt_hash}' ~ '^[0-9a-f]{64}$'
    and content_factory_private.generation_strategy_source_snapshot_valid(
      p_value ->> 'source_basis', p_value -> 'source'
    )
    and content_factory_private.generation_strategy_asset_snapshot_valid(
      p_value -> 'role_assets'
    )
    and jsonb_typeof(p_value -> 'attestations') = 'object'
    and (p_value -> 'attestations') - array[
      'version', 'source_media_rights_confirmed',
      'transformative_use_confirmed', 'product_assets_rights_confirmed',
      'depicted_people_consent_confirmed',
      'avatar_likeness_consent_confirmed'
    ]::text[] = '{}'::jsonb
    and (p_value -> 'attestations') ?& array[
      'version', 'source_media_rights_confirmed',
      'transformative_use_confirmed', 'product_assets_rights_confirmed',
      'depicted_people_consent_confirmed',
      'avatar_likeness_consent_confirmed'
    ]::text[]
    and p_value #>> '{attestations,version}' =
      'generation-strategy-attestation-v1'
    and p_value #> '{attestations,source_media_rights_confirmed}' =
      'true'::jsonb
    and p_value #> '{attestations,transformative_use_confirmed}' =
      'true'::jsonb
    and p_value #> '{attestations,product_assets_rights_confirmed}' =
      'true'::jsonb
    and p_value #> '{attestations,depicted_people_consent_confirmed}' =
      'true'::jsonb
    and jsonb_typeof(
      p_value #> '{attestations,avatar_likeness_consent_confirmed}'
    ) = 'boolean'
$$;

revoke all on function
  content_factory_private.generation_spec_strategy_snapshot_valid(jsonb)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_job_strategy_snapshot_valid(
    p_value jsonb
  )
returns boolean
language sql
immutable
set search_path = ''
as $$
  select
    jsonb_typeof(p_value) = 'object'
    and p_value - array[
      'version', 'organization_id', 'project_id', 'batch_id',
      'generation_job_id', 'spec_strategy_binding_id', 'strategy'
    ]::text[] = '{}'::jsonb
    and p_value ?& array[
      'version', 'organization_id', 'project_id', 'batch_id',
      'generation_job_id', 'spec_strategy_binding_id', 'strategy'
    ]::text[]
    and p_value ->> 'version' = 'generation-job-strategy-snapshot-v1'
    and content_factory_private.generation_spec_strategy_snapshot_valid(
      p_value -> 'strategy'
    )
$$;

revoke all on function
  content_factory_private.generation_job_strategy_snapshot_valid(jsonb)
  from public, anon, authenticated, service_role;

create table content_factory.generation_spec_strategy_bindings (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  spec_id uuid not null,
  spec_version integer not null check (spec_version between 1 and 100000),
  spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
  prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
  product_id uuid not null,
  strategy_id text not null check (strategy_id in (
    'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
  )),
  selection_hash text not null check (selection_hash ~ '^[0-9a-f]{64}$'),
  source_basis text not null check (source_basis in (
    'ai_research_recommendation', 'operator_summary_only',
    'exact_source_video'
  )),
  source_binding_id uuid not null,
  source_binding_hash text not null check (
    source_binding_hash ~ '^[0-9a-f]{64}$'
  ),
  source_snapshot jsonb not null check (
    content_factory_private.generation_strategy_source_snapshot_valid(
      source_basis, source_snapshot
    )
  ),
  source_snapshot_hash text not null check (
    source_snapshot_hash = content_factory_private.json_hash(source_snapshot)
  ),
  role_asset_snapshot jsonb not null check (
    content_factory_private.generation_strategy_asset_snapshot_valid(
      role_asset_snapshot
    )
  ),
  role_asset_snapshot_hash text not null check (
    role_asset_snapshot_hash =
      content_factory_private.json_hash(role_asset_snapshot)
  ),
  strategy_snapshot jsonb not null check (
    content_factory_private.generation_spec_strategy_snapshot_valid(
      strategy_snapshot
    )
  ),
  strategy_snapshot_hash text not null check (
    strategy_snapshot_hash = content_factory_private.json_hash(strategy_snapshot)
  ),
  attestation_version text not null check (
    attestation_version = 'generation-strategy-attestation-v1'
  ),
  source_rights_confirmed boolean not null check (source_rights_confirmed),
  transformative_use_confirmed boolean not null
    check (transformative_use_confirmed),
  product_assets_rights_confirmed boolean not null
    check (product_assets_rights_confirmed),
  depicted_people_consent_confirmed boolean not null
    check (depicted_people_consent_confirmed),
  likeness_consent_confirmed boolean not null,
  confirmation boolean not null check (confirmation),
  confirmed_by uuid not null,
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  binding_hash text not null check (binding_hash ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (
    length(idempotency_key) between 8 and 180
  ),
  bound_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, spec_id, spec_version),
  unique (organization_id, spec_id, spec_hash),
  unique (organization_id, binding_hash),
  unique (organization_id, idempotency_key),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, spec_id, spec_version, spec_hash)
    references content_factory.generation_spec_versions(
      organization_id, spec_id, spec_version, spec_hash
    ),
  foreign key (organization_id, product_id)
    references content_factory.products(organization_id, id),
  foreign key (organization_id, confirmed_by)
    references content_factory.memberships(organization_id, profile_id),
  check ((strategy_id = 'viral_avatar_ugc') = likeness_consent_confirmed),
  check (strategy_snapshot ->> 'strategy_id' = strategy_id),
  check (strategy_snapshot ->> 'selection_hash' = selection_hash),
  check (strategy_snapshot ->> 'source_basis' = source_basis),
  check (strategy_snapshot -> 'source' = source_snapshot),
  check (strategy_snapshot -> 'role_assets' = role_asset_snapshot),
  check (strategy_snapshot ->> 'product_id' = product_id::text),
  check (strategy_snapshot #>> '{spec,spec_id}' = spec_id::text),
  check ((strategy_snapshot #>> '{spec,spec_version}')::integer = spec_version),
  check (strategy_snapshot #>> '{spec,spec_hash}' = spec_hash),
  check (strategy_snapshot #>> '{spec,prompt_hash}' = prompt_hash),
  check (
    (strategy_snapshot #> '{attestations,source_media_rights_confirmed}')
      ::boolean
      = source_rights_confirmed
  ),
  check (
    (strategy_snapshot #> '{attestations,transformative_use_confirmed}')
      ::boolean = transformative_use_confirmed
  ),
  check (
    (strategy_snapshot #> '{attestations,product_assets_rights_confirmed}')
      ::boolean = product_assets_rights_confirmed
  ),
  check (
    (strategy_snapshot #> '{attestations,depicted_people_consent_confirmed}')
      ::boolean = depicted_people_consent_confirmed
  ),
  check (
    (strategy_snapshot #> '{attestations,avatar_likeness_consent_confirmed}')
      ::boolean = likeness_consent_confirmed
  ),
  check (
    binding_hash = content_factory_private.json_hash(jsonb_build_object(
      'version', 'generation-spec-strategy-binding-v1',
      'organization_id', organization_id,
      'project_id', project_id,
      'spec_id', spec_id,
      'spec_version', spec_version,
      'spec_hash', spec_hash,
      'selection_hash', selection_hash,
      'strategy_snapshot_hash', strategy_snapshot_hash,
      'confirmed_by', confirmed_by
    ))
  )
);

create table content_factory.generation_spec_strategy_assets (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  binding_id uuid not null,
  project_id uuid not null,
  product_id uuid not null,
  role text not null check (role in (
    'product_primary', 'product_reference', 'creator_avatar',
    'original_product', 'source_video', 'style_reference'
  )),
  ordinal smallint not null check (ordinal between 1 and 99),
  media_object_id uuid not null,
  media_sha256_snapshot text not null check (
    media_sha256_snapshot ~ '^[0-9a-f]{64}$'
  ),
  media_kind_snapshot text not null check (media_kind_snapshot in (
    'product_photo', 'packshot', 'creator_reference', 'source_video'
  )),
  mime_type_snapshot text not null check (mime_type_snapshot in (
    'image/jpeg', 'image/png', 'image/webp', 'video/mp4'
  )),
  media_product_id_snapshot uuid,
  rights_confirmed_snapshot boolean not null
    check (rights_confirmed_snapshot),
  likeness_consent_snapshot boolean not null,
  bound_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, binding_id, role, ordinal),
  unique (organization_id, binding_id, media_object_id),
  foreign key (organization_id, binding_id)
    references content_factory.generation_spec_strategy_bindings(
      organization_id, id
    ),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, product_id)
    references content_factory.products(organization_id, id),
  foreign key (organization_id, media_object_id)
    references content_factory.media_objects(organization_id, id),
  check ((role = 'creator_avatar') = likeness_consent_snapshot),
  check (
    (role = 'product_primary' and ordinal = 1)
    or (role = 'product_reference' and ordinal between 1 and 9)
    or (role in ('creator_avatar', 'original_product', 'source_video')
      and ordinal = 1)
    or (role = 'style_reference' and ordinal between 1 and 4)
  ),
  check (
    (role in ('product_primary', 'product_reference')
      and media_kind_snapshot in ('product_photo', 'packshot')
      and mime_type_snapshot in ('image/jpeg', 'image/png', 'image/webp')
      and media_product_id_snapshot = product_id)
    or (role in ('creator_avatar', 'original_product', 'style_reference')
      and media_kind_snapshot = 'creator_reference'
      and mime_type_snapshot in ('image/jpeg', 'image/png', 'image/webp'))
    or (role = 'source_video'
      and media_kind_snapshot = 'source_video'
      and mime_type_snapshot = 'video/mp4')
  )
);

create table content_factory.generation_job_strategy_snapshots (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  batch_id uuid not null,
  generation_job_id uuid not null,
  spec_strategy_binding_id uuid not null,
  spec_id uuid not null,
  spec_version integer not null check (spec_version between 1 and 100000),
  spec_hash text not null check (spec_hash ~ '^[0-9a-f]{64}$'),
  product_id uuid not null,
  strategy_id text not null check (strategy_id in (
    'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
  )),
  source_basis text not null check (source_basis in (
    'ai_research_recommendation', 'operator_summary_only',
    'exact_source_video'
  )),
  snapshot_version text not null check (
    snapshot_version = 'generation-job-strategy-snapshot-v1'
  ),
  strategy_snapshot jsonb not null check (
    content_factory_private.generation_job_strategy_snapshot_valid(
      strategy_snapshot
    )
  ),
  strategy_snapshot_hash text not null check (
    strategy_snapshot_hash = content_factory_private.json_hash(strategy_snapshot)
  ),
  bound_by uuid not null,
  bound_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, generation_job_id),
  unique (organization_id, batch_id),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, generation_job_id)
    references content_factory.generation_jobs(organization_id, id),
  foreign key (organization_id, batch_id)
    references content_factory.generation_batches(organization_id, id),
  foreign key (organization_id, spec_strategy_binding_id)
    references content_factory.generation_spec_strategy_bindings(
      organization_id, id
    ),
  foreign key (organization_id, spec_id, spec_version, spec_hash)
    references content_factory.generation_spec_versions(
      organization_id, spec_id, spec_version, spec_hash
    ),
  foreign key (organization_id, product_id)
    references content_factory.products(organization_id, id),
  foreign key (organization_id, bound_by)
    references content_factory.memberships(organization_id, profile_id),
  check (strategy_snapshot ->> 'organization_id' = organization_id::text),
  check (strategy_snapshot ->> 'project_id' = project_id::text),
  check (strategy_snapshot ->> 'batch_id' = batch_id::text),
  check (strategy_snapshot ->> 'generation_job_id' = generation_job_id::text),
  check (
    strategy_snapshot ->> 'spec_strategy_binding_id' =
      spec_strategy_binding_id::text
  ),
  check (strategy_snapshot #>> '{strategy,strategy_id}' = strategy_id),
  check (strategy_snapshot #>> '{strategy,source_basis}' = source_basis)
);

create table content_factory.generation_strategy_status_events (
  id uuid primary key default extensions.gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  batch_id uuid not null,
  generation_job_id uuid not null,
  spec_strategy_binding_id uuid not null,
  strategy_id text not null check (strategy_id in (
    'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
  )),
  transition_ordinal integer not null check (
    transition_ordinal between 1 and 100000
  ),
  event_name text not null check (event_name in (
    'generation_strategy_job_created',
    'generation_strategy_job_status_changed'
  )),
  previous_status text,
  job_status text not null check (job_status in (
    'mock_ready', 'queued', 'starting', 'submitted', 'processing',
    'succeeded', 'failed', 'cancelled'
  )),
  event_hash text not null check (event_hash ~ '^[0-9a-f]{64}$'),
  occurred_at timestamptz not null default clock_timestamp(),
  unique (organization_id, id),
  unique (organization_id, generation_job_id, transition_ordinal),
  foreign key (organization_id, project_id)
    references content_factory.workspace_folders(organization_id, id),
  foreign key (organization_id, batch_id)
    references content_factory.generation_batches(organization_id, id),
  foreign key (organization_id, generation_job_id)
    references content_factory.generation_jobs(organization_id, id),
  foreign key (organization_id, spec_strategy_binding_id)
    references content_factory.generation_spec_strategy_bindings(
      organization_id, id
    ),
  check (
    (transition_ordinal = 1 and previous_status is null
      and event_name = 'generation_strategy_job_created')
    or
    (transition_ordinal > 1 and previous_status in (
      'mock_ready', 'queued', 'starting', 'submitted', 'processing',
      'succeeded', 'failed', 'cancelled'
    ) and previous_status <> job_status
      and event_name = 'generation_strategy_job_status_changed')
  ),
  check (
    event_hash = content_factory_private.json_hash(jsonb_build_object(
      'version', 'generation-strategy-status-event-v1',
      'organization_id', organization_id,
      'project_id', project_id,
      'batch_id', batch_id,
      'generation_job_id', generation_job_id,
      'spec_strategy_binding_id', spec_strategy_binding_id,
      'strategy_id', strategy_id,
      'transition_ordinal', transition_ordinal,
      'event_name', event_name,
      'previous_status', to_jsonb(previous_status),
      'job_status', job_status
    ))
  )
);

create index generation_spec_strategy_project_idx
  on content_factory.generation_spec_strategy_bindings (
    organization_id, project_id, bound_at desc, id desc
  );
create index generation_job_strategy_archive_idx
  on content_factory.generation_job_strategy_snapshots (
    organization_id, project_id, strategy_id, bound_at desc, batch_id
  );
create index generation_strategy_status_event_job_idx
  on content_factory.generation_strategy_status_events (
    organization_id, project_id, generation_job_id,
    transition_ordinal desc
  );

alter table content_factory.generation_spec_strategy_bindings
  enable row level security;
alter table content_factory.generation_spec_strategy_assets
  enable row level security;
alter table content_factory.generation_job_strategy_snapshots
  enable row level security;
alter table content_factory.generation_strategy_status_events
  enable row level security;

revoke all on content_factory.generation_spec_strategy_bindings
  from public, anon, authenticated, service_role;
revoke all on content_factory.generation_spec_strategy_assets
  from public, anon, authenticated, service_role;
revoke all on content_factory.generation_job_strategy_snapshots
  from public, anon, authenticated, service_role;
revoke all on content_factory.generation_strategy_status_events
  from public, anon, authenticated, service_role;
grant all on content_factory.generation_spec_strategy_bindings to service_role;
grant all on content_factory.generation_spec_strategy_assets to service_role;
grant all on content_factory.generation_job_strategy_snapshots to service_role;
grant all on content_factory.generation_strategy_status_events to service_role;

create or replace function
  content_factory_private.reject_generation_strategy_mutation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  raise exception using
    errcode = '55000', message = 'generation_strategy_ledger_append_only';
end;
$$;

revoke all on function
  content_factory_private.reject_generation_strategy_mutation()
  from public, anon, authenticated, service_role;

create trigger generation_spec_strategy_binding_append_only
before update or delete on content_factory.generation_spec_strategy_bindings
for each row execute function
  content_factory_private.reject_generation_strategy_mutation();
create trigger generation_spec_strategy_asset_append_only
before update or delete on content_factory.generation_spec_strategy_assets
for each row execute function
  content_factory_private.reject_generation_strategy_mutation();
create trigger generation_job_strategy_snapshot_append_only
before update or delete on content_factory.generation_job_strategy_snapshots
for each row execute function
  content_factory_private.reject_generation_strategy_mutation();
create trigger generation_strategy_status_event_append_only
before update or delete on content_factory.generation_strategy_status_events
for each row execute function
  content_factory_private.reject_generation_strategy_mutation();

create or replace function
  content_factory_private.generation_strategy_binding_current(
    p_organization_id uuid,
    p_binding_id uuid
  )
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  spec_row content_factory.generation_spec_versions%rowtype;
  source_snapshot_value jsonb;
  asset_snapshot_value jsonb;
  asset_count integer := 0;
  live_asset_count integer := 0;
  primary_count integer := 0;
  product_reference_count integer := 0;
  creator_count integer := 0;
  original_product_count integer := 0;
  source_video_count integer := 0;
  style_reference_count integer := 0;
  spec_product_asset_count integer := 0;
  exact_source_media_id uuid;
begin
  select binding.* into binding_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = p_organization_id
    and binding.id = p_binding_id;
  if binding_row.id is null then
    return false;
  end if;

  perform 1
  from content_factory.workspace_folders project
  join content_factory.products product
    on product.organization_id = project.organization_id
   and product.id = binding_row.product_id
   and product.status = 'active'
  join content_factory.memberships membership
    on membership.organization_id = project.organization_id
   and membership.profile_id = binding_row.confirmed_by
   and membership.status = 'active'
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where project.organization_id = binding_row.organization_id
    and project.id = binding_row.project_id
    and project.kind = 'project'
    and project.status = 'active';
  if not found then
    return false;
  end if;

  perform 1
  from content_factory.generation_spec_head_events head
  where head.organization_id = binding_row.organization_id
    and head.spec_id = binding_row.spec_id
    and head.spec_version = binding_row.spec_version
    and head.spec_hash = binding_row.spec_hash
    and head.state = 'approved'
    and not exists (
      select 1
      from content_factory.generation_spec_head_events later
      where later.organization_id = head.organization_id
        and later.spec_id = head.spec_id
        and later.event_sequence > head.event_sequence
    );
  if not found then
    return false;
  end if;

  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = binding_row.organization_id
    and version.spec_id = binding_row.spec_id
    and version.spec_version = binding_row.spec_version
    and version.spec_hash = binding_row.spec_hash
    and version.prompt_hash = binding_row.prompt_hash
    and version.product_id = binding_row.product_id;
  if spec_row.version_id is null then
    return false;
  end if;

  if binding_row.source_basis = 'ai_research_recommendation' then
    select jsonb_build_object(
      'basis', 'ai_research_recommendation',
      'binding_id', source.id,
      'binding_hash', source.recommendation_hash,
      'selection_id', source.selection_id,
      'selection_hash', source.selection_hash,
      'recommendation_position', source.recommendation_position,
      'recommendation_hash', source.recommendation_hash
    ) into source_snapshot_value
    from content_factory.generation_spec_ai_research_bindings source
    where source.organization_id = binding_row.organization_id
      and source.project_id = binding_row.project_id
      and source.spec_id = binding_row.spec_id
      and source.spec_version = binding_row.spec_version
      and source.spec_hash = binding_row.spec_hash
      and source.id = binding_row.source_binding_id
      and source.recommendation_hash = binding_row.source_binding_hash;
  elsif binding_row.source_basis = 'operator_summary_only' then
    select jsonb_build_object(
      'basis', 'operator_summary_only',
      'binding_id', source.id,
      'binding_hash', source.binding_hash,
      'reference_hash', source.reference_hash,
      'analysis_basis', source.analysis_basis,
      'ai_watched', source.ai_watched,
      'evidence_verified', source.evidence_verified
    ) into source_snapshot_value
    from content_factory.generation_spec_video_reference_bindings source
    where source.organization_id = binding_row.organization_id
      and source.project_id = binding_row.project_id
      and source.spec_id = binding_row.spec_id
      and source.spec_version = binding_row.spec_version
      and source.spec_hash = binding_row.spec_hash
      and source.id = binding_row.source_binding_id
      and source.binding_hash = binding_row.source_binding_hash
      and source.analysis_basis = 'operator_summary'
      and not source.ai_watched
      and not source.evidence_verified;
  elsif binding_row.source_basis = 'exact_source_video' then
    select
      jsonb_build_object(
        'basis', 'exact_source_video',
        'binding_id', source.id,
        'binding_hash', source.attachment_hash,
        'source_id', source.source_id,
        'source_hash', source.source_hash_snapshot,
        'media_object_id', source.media_object_id,
        'media_sha256', source.media_sha256_snapshot
      ),
      source.media_object_id
    into source_snapshot_value, exact_source_media_id
    from content_factory.research_exact_youtube_media_attachments source
    where source.organization_id = binding_row.organization_id
      and source.project_id = binding_row.project_id
      and source.id = binding_row.source_binding_id
      and source.attachment_hash = binding_row.source_binding_hash
      and source.rights_confirmed
      and source.media_matches_registered_source
      and source.status = 'attached';
  end if;
  if source_snapshot_value is null
     or source_snapshot_value is distinct from binding_row.source_snapshot
     or content_factory_private.json_hash(source_snapshot_value)
          is distinct from binding_row.source_snapshot_hash then
    return false;
  end if;

  select
    count(*)::integer,
    count(*) filter (where asset.role = 'product_primary')::integer,
    count(*) filter (where asset.role = 'product_reference')::integer,
    count(*) filter (where asset.role = 'creator_avatar')::integer,
    count(*) filter (where asset.role = 'original_product')::integer,
    count(*) filter (where asset.role = 'source_video')::integer,
    count(*) filter (where asset.role = 'style_reference')::integer,
    count(*) filter (
      where asset.role in ('product_primary', 'product_reference')
        and asset.media_object_id = any(spec_row.media_ids)
    )::integer,
    count(*) filter (
      where media.id is not null
        and media.project_id = binding_row.project_id
        and media.status = 'ready'
        and media.sha256 = asset.media_sha256_snapshot
        and media.mime_type = asset.mime_type_snapshot
        and media.metadata ->> 'kind' = asset.media_kind_snapshot
        and media.product_id is not distinct from
              asset.media_product_id_snapshot
        and (
          media.product_id is null
          or exists (
            select 1
            from content_factory.products media_product
            where media_product.organization_id = media.organization_id
              and media_product.id = media.product_id
              and media_product.status = 'active'
          )
        )
        and media.metadata -> 'rights_confirmed' = 'true'::jsonb
        and media.artifact_class = 'source'
        and media.lifecycle_stage = 'sources'
        and not (media.metadata ?| array[
          'generation_job_id', 'provider_job_id', 'generation_provider',
          'generated_from_job_id', 'output_media_id'
        ])
    )::integer,
    jsonb_agg(jsonb_build_object(
      'role', asset.role,
      'ordinal', asset.ordinal,
      'media_object_id', asset.media_object_id,
      'sha256', asset.media_sha256_snapshot,
      'kind', asset.media_kind_snapshot,
      'mime_type', asset.mime_type_snapshot,
      'product_id', to_jsonb(asset.media_product_id_snapshot),
      'rights_confirmed', asset.rights_confirmed_snapshot,
      'likeness_consent', asset.likeness_consent_snapshot
    ) order by
      content_factory_private.generation_strategy_role_order(asset.role),
      asset.ordinal)
  into
    asset_count, primary_count, product_reference_count, creator_count,
    original_product_count, source_video_count, style_reference_count,
    spec_product_asset_count, live_asset_count, asset_snapshot_value
  from content_factory.generation_spec_strategy_assets asset
  left join content_factory.media_objects media
    on media.organization_id = asset.organization_id
   and media.id = asset.media_object_id
  where asset.organization_id = binding_row.organization_id
    and asset.binding_id = binding_row.id;

  if asset_count < 1
     or live_asset_count <> asset_count
     or asset_snapshot_value is distinct from binding_row.role_asset_snapshot
     or content_factory_private.json_hash(asset_snapshot_value)
          is distinct from binding_row.role_asset_snapshot_hash
     or primary_count <> 1
     or not exists (
       select 1
       from content_factory.generation_spec_strategy_assets primary_asset
       where primary_asset.organization_id = binding_row.organization_id
         and primary_asset.binding_id = binding_row.id
         and primary_asset.role = 'product_primary'
         and primary_asset.media_object_id = spec_row.primary_media_id
     )
     or spec_product_asset_count <> cardinality(spec_row.media_ids)
     or primary_count + product_reference_count not between
          cardinality(spec_row.media_ids) and 10
     or exists (
       select 1
       from generate_series(1, product_reference_count) expected(ordinal)
       where not exists (
         select 1
         from content_factory.generation_spec_strategy_assets asset
         where asset.organization_id = binding_row.organization_id
           and asset.binding_id = binding_row.id
           and asset.role = 'product_reference'
           and asset.ordinal = expected.ordinal
       )
     )
     or exists (
       select 1
       from generate_series(1, style_reference_count) expected(ordinal)
       where not exists (
         select 1
         from content_factory.generation_spec_strategy_assets asset
         where asset.organization_id = binding_row.organization_id
           and asset.binding_id = binding_row.id
           and asset.role = 'style_reference'
           and asset.ordinal = expected.ordinal
       )
     )
     or exists (
       select 1
       from (
         select
           selected.media_id,
           row_number() over (order by selected.source_ordinal)::integer
             as expected_ordinal
         from unnest(spec_row.media_ids) with ordinality
           selected(media_id, source_ordinal)
         where selected.media_id <> spec_row.primary_media_id
       ) expected
       left join content_factory.generation_spec_strategy_assets asset
         on asset.organization_id = binding_row.organization_id
        and asset.binding_id = binding_row.id
        and asset.role = 'product_reference'
        and asset.media_object_id = expected.media_id
        and asset.ordinal = expected.expected_ordinal
       where asset.id is null
     ) then
    return false;
  end if;

  if binding_row.strategy_id = 'viral_avatar_ugc' then
    if binding_row.source_basis not in (
         'ai_research_recommendation', 'operator_summary_only',
         'exact_source_video'
       )
       or cardinality(spec_row.media_ids) <> 1
       or asset_count <> 2
       or primary_count + product_reference_count <> 1
       or creator_count <> 1
       or original_product_count <> 0
       or source_video_count <> 0
       or style_reference_count <> 0
       or not binding_row.likeness_consent_confirmed then
      return false;
    end if;
  elsif binding_row.strategy_id = 'viral_product_swap' then
    if binding_row.source_basis <> 'exact_source_video'
       or creator_count <> 0
       or original_product_count <> 1
       or source_video_count <> 1
       or style_reference_count <> 0
       or primary_count + product_reference_count not between 1 and 10
       or asset_count <> primary_count + product_reference_count + 2
       or binding_row.likeness_consent_confirmed
       or not exists (
         select 1
         from content_factory.generation_spec_strategy_assets source_asset
         where source_asset.organization_id = binding_row.organization_id
           and source_asset.binding_id = binding_row.id
           and source_asset.role = 'source_video'
           and source_asset.media_object_id = exact_source_media_id
       ) then
      return false;
    end if;
  elsif binding_row.strategy_id = 'viral_rebuild' then
    if binding_row.source_basis not in (
         'operator_summary_only', 'exact_source_video'
       )
       or creator_count <> 0
       or original_product_count <> 0
       or style_reference_count not between 0 and 4
       or primary_count + product_reference_count not between 1 and 10
       or asset_count <> primary_count + product_reference_count
             + style_reference_count +
             (case when binding_row.source_basis = 'exact_source_video'
               then 1 else 0 end)
       or source_video_count <>
            (case when binding_row.source_basis = 'exact_source_video'
              then 1 else 0 end)
       or binding_row.likeness_consent_confirmed
       or (
         binding_row.source_basis = 'exact_source_video'
         and not exists (
           select 1
           from content_factory.generation_spec_strategy_assets source_asset
           where source_asset.organization_id = binding_row.organization_id
             and source_asset.binding_id = binding_row.id
             and source_asset.role = 'source_video'
             and source_asset.media_object_id = exact_source_media_id
         )
       ) then
      return false;
    end if;
  else
    return false;
  end if;

  return
    binding_row.source_rights_confirmed
    and binding_row.transformative_use_confirmed
    and binding_row.product_assets_rights_confirmed
    and binding_row.depicted_people_consent_confirmed
    and binding_row.confirmation
    and binding_row.strategy_snapshot -> 'source' = source_snapshot_value
    and binding_row.strategy_snapshot -> 'role_assets' = asset_snapshot_value
    and content_factory_private.json_hash(binding_row.strategy_snapshot)
          = binding_row.strategy_snapshot_hash;
end;
$$;

revoke all on function
  content_factory_private.generation_strategy_binding_current(uuid, uuid)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.enforce_generation_strategy_binding_current()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not content_factory_private.generation_strategy_binding_current(
    new.organization_id,
    coalesce(
      nullif(to_jsonb(new) ->> 'binding_id', '')::uuid,
      nullif(to_jsonb(new) ->> 'id', '')::uuid
    )
  ) then
    raise exception using
      errcode = '55000',
      message = 'generation_strategy_binding_invalid';
  end if;
  return null;
end;
$$;

revoke all on function
  content_factory_private.enforce_generation_strategy_binding_current()
  from public, anon, authenticated, service_role;

create constraint trigger generation_spec_strategy_binding_current_guard
after insert on content_factory.generation_spec_strategy_bindings
deferrable initially deferred
for each row execute function
  content_factory_private.enforce_generation_strategy_binding_current();
create constraint trigger generation_spec_strategy_asset_current_guard
after insert on content_factory.generation_spec_strategy_assets
deferrable initially deferred
for each row execute function
  content_factory_private.enforce_generation_strategy_binding_current();

create or replace function public.system_bind_generation_spec_strategy(
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
  actor_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  selection_hash_value text;
  strategy_id_value text;
  source_basis_value text;
  source_binding_id_value uuid;
  source_binding_hash_value text;
  idempotency_key_value text;
  actor_role_value text;
  spec_row content_factory.generation_spec_versions%rowtype;
  media_row content_factory.media_objects%rowtype;
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  existing_row content_factory.generation_spec_strategy_bindings%rowtype;
  source_snapshot_value jsonb;
  role_asset_snapshot_value jsonb := '[]'::jsonb;
  strategy_snapshot_value jsonb;
  request_hash_value text;
  binding_hash_value text;
  role_asset_snapshot_hash_value text;
  strategy_snapshot_hash_value text;
  asset_request jsonb;
  asset_role_value text;
  asset_ordinal_value integer;
  asset_media_id_value uuid;
  asset_sha256_value text;
  source_rights_value boolean;
  transformative_use_value boolean;
  product_assets_rights_value boolean;
  depicted_people_consent_value boolean;
  likeness_consent_value boolean;
  approved_spec_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'strategy_id', 'selection_hash',
       'source_basis',
       'source_binding_id', 'source_binding_hash', 'role_assets',
       'source_media_rights_confirmed', 'transformative_use_confirmed',
       'product_assets_rights_confirmed',
       'depicted_people_consent_confirmed',
       'avatar_likeness_consent_confirmed', 'confirmation', 'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'strategy_id', 'selection_hash',
       'source_basis',
       'source_binding_id', 'source_binding_hash', 'role_assets',
       'source_media_rights_confirmed', 'transformative_use_confirmed',
       'product_assets_rights_confirmed',
       'depicted_people_consent_confirmed',
       'avatar_likeness_consent_confirmed', 'confirmation', 'idempotency_key'
     ]::text[] then
    raise exception using errcode = '22023',
      message = 'generation_strategy_binding_payload_invalid';
  end if;
  if p_payload ->> 'version' <> 'generation-strategy-binding-request-v1'
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb
     or p_payload -> 'source_media_rights_confirmed'
          is distinct from 'true'::jsonb
     or p_payload -> 'transformative_use_confirmed'
           is distinct from 'true'::jsonb
     or p_payload -> 'product_assets_rights_confirmed'
          is distinct from 'true'::jsonb
     or p_payload -> 'depicted_people_consent_confirmed'
          is distinct from 'true'::jsonb
     or jsonb_typeof(p_payload -> 'avatar_likeness_consent_confirmed') <>
          'boolean'
     or jsonb_typeof(p_payload -> 'role_assets') <> 'array'
     or jsonb_array_length(p_payload -> 'role_assets') not between 1 and 16
     or jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[1-9][0-9]{0,5}$'
  then
    raise exception using errcode = '22023',
      message = 'generation_strategy_binding_payload_invalid';
  end if;

  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(
    p_payload, 'actor_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  strategy_id_value := lower(btrim(p_payload ->> 'strategy_id'));
  selection_hash_value := lower(btrim(p_payload ->> 'selection_hash'));
  source_basis_value := lower(btrim(p_payload ->> 'source_basis'));
  source_binding_id_value := content_factory_private.require_uuid(
    p_payload, 'source_binding_id'
  );
  source_binding_hash_value := lower(btrim(
    p_payload ->> 'source_binding_hash'
  ));
  idempotency_key_value := btrim(p_payload ->> 'idempotency_key');
  source_rights_value :=
    (p_payload ->> 'source_media_rights_confirmed')::boolean;
  transformative_use_value :=
    (p_payload ->> 'transformative_use_confirmed')::boolean;
  product_assets_rights_value :=
    (p_payload ->> 'product_assets_rights_confirmed')::boolean;
  depicted_people_consent_value :=
    (p_payload ->> 'depicted_people_consent_confirmed')::boolean;
  likeness_consent_value :=
    (p_payload ->> 'avatar_likeness_consent_confirmed')::boolean;
  if spec_hash_value !~ '^[0-9a-f]{64}$'
     or selection_hash_value !~ '^[0-9a-f]{64}$'
     or source_binding_hash_value !~ '^[0-9a-f]{64}$'
     or strategy_id_value not in (
       'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
     )
     or source_basis_value not in (
       'ai_research_recommendation', 'operator_summary_only',
       'exact_source_video'
     )
     or length(idempotency_key_value) not between 8 and 180
     or idempotency_key_value ~ '[[:cntrl:]]'
     or ((strategy_id_value = 'viral_avatar_ugc') <>
          likeness_consent_value) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_binding_payload_invalid';
  end if;

  select membership.role into actor_role_value
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = organization_id_value
    and membership.profile_id = actor_id_value
    and membership.status = 'active'
    and membership.role in ('owner', 'admin', 'producer', 'operator');
  if actor_role_value is null
     or not content_factory_private.workspace_project_access_allowed(
       organization_id_value, project_id_value, actor_id_value
     ) then
    raise exception using errcode = '42501',
      message = 'generation_strategy_binding_project_access_required';
  end if;
  perform 1
  from content_factory.workspace_folders project
  where project.organization_id = organization_id_value
    and project.id = project_id_value
    and project.kind = 'project'
    and project.status = 'active';
  if not found then
    raise exception using errcode = '42501',
      message = 'generation_strategy_binding_project_access_required';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id_value::text),
    hashtext('generation-strategy:' || spec_id_value::text)
  );
  select version.* into spec_row
  from content_factory.generation_spec_versions version
  join content_factory.products product
    on product.organization_id = version.organization_id
   and product.id = version.product_id
   and product.status = 'active'
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value
  for share of version, product;
  if spec_row.version_id is null then
    raise exception using errcode = '42501',
      message = 'generation_strategy_binding_spec_invalid';
  end if;
  if (
    select count(*)
    from unnest(spec_row.media_ids) selected(media_id)
    join content_factory.media_objects media
      on media.organization_id = organization_id_value
     and media.project_id = project_id_value
     and media.id = selected.media_id
     and media.product_id = spec_row.product_id
  ) <> cardinality(spec_row.media_ids) then
    raise exception using errcode = '42501',
      message = 'generation_strategy_binding_spec_invalid';
  end if;
  perform content_factory_private.require_generation_project_provenance_v49(
    organization_id_value, project_id_value, spec_row.product_id,
    spec_row.research_provenance, spec_row.repair_provenance,
    spec_row.performance_policy_provenance, spec_row.final_policy
  );
  select coalesce(
    head.state = 'approved'
    and head.spec_version = spec_version_value
    and head.spec_hash = spec_hash_value,
    false
  ) into approved_spec_value
  from content_factory.generation_spec_head_events head
  where head.organization_id = organization_id_value
    and head.spec_id = spec_id_value
  order by head.event_sequence desc
  limit 1;
  if not coalesce(approved_spec_value, false) then
    raise exception using errcode = '55000',
      message = 'generation_strategy_binding_spec_not_approved';
  end if;

  if source_basis_value = 'ai_research_recommendation' then
    select jsonb_build_object(
      'basis', 'ai_research_recommendation',
      'binding_id', source.id,
      'binding_hash', source.recommendation_hash,
      'selection_id', source.selection_id,
      'selection_hash', source.selection_hash,
      'recommendation_position', source.recommendation_position,
      'recommendation_hash', source.recommendation_hash
    ) into source_snapshot_value
    from content_factory.generation_spec_ai_research_bindings source
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
      and source.spec_id = spec_id_value
      and source.spec_version = spec_version_value
      and source.spec_hash = spec_hash_value
      and source.id = source_binding_id_value
      and source.recommendation_hash = source_binding_hash_value;
  elsif source_basis_value = 'operator_summary_only' then
    select jsonb_build_object(
      'basis', 'operator_summary_only',
      'binding_id', source.id,
      'binding_hash', source.binding_hash,
      'reference_hash', source.reference_hash,
      'analysis_basis', source.analysis_basis,
      'ai_watched', source.ai_watched,
      'evidence_verified', source.evidence_verified
    ) into source_snapshot_value
    from content_factory.generation_spec_video_reference_bindings source
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
      and source.spec_id = spec_id_value
      and source.spec_version = spec_version_value
      and source.spec_hash = spec_hash_value
      and source.id = source_binding_id_value
      and source.binding_hash = source_binding_hash_value
      and source.analysis_basis = 'operator_summary'
      and not source.ai_watched
      and not source.evidence_verified;
  else
    select jsonb_build_object(
      'basis', 'exact_source_video',
      'binding_id', source.id,
      'binding_hash', source.attachment_hash,
      'source_id', source.source_id,
      'source_hash', source.source_hash_snapshot,
      'media_object_id', source.media_object_id,
      'media_sha256', source.media_sha256_snapshot
    ) into source_snapshot_value
    from content_factory.research_exact_youtube_media_attachments source
    where source.organization_id = organization_id_value
      and source.project_id = project_id_value
      and source.id = source_binding_id_value
      and source.attachment_hash = source_binding_hash_value
      and source.rights_confirmed
      and source.media_matches_registered_source
      and source.status = 'attached';
  end if;
  if source_snapshot_value is null
     or (strategy_id_value = 'viral_product_swap'
          and source_basis_value <> 'exact_source_video')
     or (strategy_id_value = 'viral_rebuild'
          and source_basis_value = 'ai_research_recommendation') then
    raise exception using errcode = '42501',
      message = 'generation_strategy_source_binding_invalid';
  end if;

  for asset_request in
    select item.value
    from jsonb_array_elements(p_payload -> 'role_assets') item(value)
    order by
      content_factory_private.generation_strategy_role_order(
        item.value ->> 'role'
      ),
      case when item.value ->> 'ordinal' ~ '^[1-9][0-9]?$'
        then (item.value ->> 'ordinal')::integer else 100 end
  loop
    if jsonb_typeof(asset_request) <> 'object'
       or asset_request - array[
         'role', 'ordinal', 'media_object_id', 'sha256'
       ]::text[] <> '{}'::jsonb
       or not asset_request ?& array[
         'role', 'ordinal', 'media_object_id', 'sha256'
       ]::text[]
       or jsonb_typeof(asset_request -> 'ordinal') <> 'number'
       or coalesce(asset_request ->> 'ordinal', '') !~ '^[1-9][0-9]?$'
       or coalesce(asset_request ->> 'sha256', '') !~ '^[0-9a-f]{64}$'
    then
      raise exception using errcode = '22023',
        message = 'generation_strategy_role_asset_invalid';
    end if;
    asset_role_value := asset_request ->> 'role';
    asset_ordinal_value := (asset_request ->> 'ordinal')::integer;
    begin
      asset_media_id_value := (asset_request ->> 'media_object_id')::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023',
        message = 'generation_strategy_role_asset_invalid';
    end;
    asset_sha256_value := lower(asset_request ->> 'sha256');
    if asset_role_value not in (
      'product_primary', 'product_reference', 'creator_avatar',
      'original_product', 'source_video', 'style_reference'
    ) then
      raise exception using errcode = '22023',
        message = 'generation_strategy_role_asset_invalid';
    end if;

    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = asset_media_id_value
      and media.status = 'ready'
      and media.sha256 = asset_sha256_value
      and media.metadata -> 'rights_confirmed' = 'true'::jsonb
      and media.artifact_class = 'source'
      and media.lifecycle_stage = 'sources'
      and not (media.metadata ?| array[
        'generation_job_id', 'provider_job_id', 'generation_provider',
        'generated_from_job_id', 'output_media_id'
      ])
    for share;
    if media_row.id is null
       or (
         media_row.product_id is not null
         and not exists (
           select 1
           from content_factory.products media_product
           where media_product.organization_id = organization_id_value
             and media_product.id = media_row.product_id
             and media_product.status = 'active'
         )
       )
       or (
          asset_role_value in ('product_primary', 'product_reference')
          and (
            media_row.product_id is distinct from spec_row.product_id
            or media_row.mime_type not in (
             'image/jpeg', 'image/png', 'image/webp'
           )
           or media_row.metadata ->> 'kind' not in (
             'product_photo', 'packshot'
           )
         )
       )
       or (
          asset_role_value in (
            'creator_avatar', 'original_product', 'style_reference'
          )
         and (
           media_row.mime_type not in (
             'image/jpeg', 'image/png', 'image/webp'
           )
           or media_row.metadata ->> 'kind' <> 'creator_reference'
         )
       )
       or (
         asset_role_value = 'source_video'
         and (
           media_row.mime_type <> 'video/mp4'
           or media_row.metadata ->> 'kind' <> 'source_video'
         )
       ) then
      raise exception using errcode = '42501',
        message = 'generation_strategy_role_asset_invalid';
    end if;

    role_asset_snapshot_value := role_asset_snapshot_value ||
      jsonb_build_array(jsonb_build_object(
        'role', asset_role_value,
        'ordinal', asset_ordinal_value,
        'media_object_id', media_row.id,
        'sha256', media_row.sha256,
        'kind', media_row.metadata ->> 'kind',
        'mime_type', media_row.mime_type,
        'product_id', to_jsonb(media_row.product_id),
        'rights_confirmed', true,
        'likeness_consent',
          asset_role_value = 'creator_avatar' and likeness_consent_value
      ));
  end loop;

  if not content_factory_private.generation_strategy_asset_snapshot_valid(
       role_asset_snapshot_value
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_role_asset_invalid';
  end if;

  strategy_snapshot_value := jsonb_build_object(
    'version', 'generation-spec-strategy-snapshot-v1',
    'strategy_id', strategy_id_value,
    'selection_hash', selection_hash_value,
    'source_basis', source_basis_value,
    'spec', jsonb_build_object(
      'spec_id', spec_row.spec_id,
      'spec_version', spec_row.spec_version,
      'spec_hash', spec_row.spec_hash,
      'prompt_hash', spec_row.prompt_hash
    ),
    'product_id', spec_row.product_id,
    'source', source_snapshot_value,
    'role_assets', role_asset_snapshot_value,
    'attestations', jsonb_build_object(
      'version', 'generation-strategy-attestation-v1',
      'source_media_rights_confirmed', source_rights_value,
      'transformative_use_confirmed', transformative_use_value,
      'product_assets_rights_confirmed', product_assets_rights_value,
      'depicted_people_consent_confirmed', depicted_people_consent_value,
      'avatar_likeness_consent_confirmed', likeness_consent_value
    )
  );
  if not content_factory_private.generation_spec_strategy_snapshot_valid(
       strategy_snapshot_value
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_snapshot_invalid';
  end if;

  role_asset_snapshot_hash_value := content_factory_private.json_hash(
    role_asset_snapshot_value
  );
  strategy_snapshot_hash_value := content_factory_private.json_hash(
    strategy_snapshot_value
  );
  request_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'generation-strategy-binding-request-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'actor_id', actor_id_value,
    'spec_id', spec_row.spec_id,
    'spec_version', spec_row.spec_version,
    'spec_hash', spec_row.spec_hash,
    'strategy_id', strategy_id_value,
    'selection_hash', selection_hash_value,
    'source_basis', source_basis_value,
    'source_binding_id', source_binding_id_value,
    'source_binding_hash', source_binding_hash_value,
    'role_assets', role_asset_snapshot_value,
    'source_media_rights_confirmed', source_rights_value,
    'transformative_use_confirmed', transformative_use_value,
    'product_assets_rights_confirmed', product_assets_rights_value,
    'depicted_people_consent_confirmed', depicted_people_consent_value,
    'avatar_likeness_consent_confirmed', likeness_consent_value,
    'confirmation', true
  ));
  binding_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'generation-spec-strategy-binding-v1',
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'spec_id', spec_row.spec_id,
    'spec_version', spec_row.spec_version,
    'spec_hash', spec_row.spec_hash,
    'selection_hash', selection_hash_value,
    'strategy_snapshot_hash', strategy_snapshot_hash_value,
    'confirmed_by', actor_id_value
  ));

  select binding.* into existing_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = organization_id_value
    and (
      binding.idempotency_key = idempotency_key_value
      or (
        binding.spec_id = spec_row.spec_id
        and binding.spec_version = spec_row.spec_version
      )
    )
  order by (binding.idempotency_key = idempotency_key_value) desc
  limit 1;
  if existing_row.id is not null then
    if existing_row.request_hash <> request_hash_value
       or existing_row.binding_hash <> binding_hash_value
       or existing_row.strategy_snapshot <> strategy_snapshot_value then
      raise exception using errcode = '23505',
        message = 'generation_strategy_binding_conflict';
    end if;
    binding_row := existing_row;
  else
    insert into content_factory.generation_spec_strategy_bindings (
      organization_id, project_id, spec_id, spec_version, spec_hash,
      prompt_hash, product_id, strategy_id, selection_hash, source_basis,
      source_binding_id, source_binding_hash, source_snapshot,
      source_snapshot_hash, role_asset_snapshot, role_asset_snapshot_hash,
      strategy_snapshot, strategy_snapshot_hash, attestation_version,
      source_rights_confirmed, transformative_use_confirmed,
      product_assets_rights_confirmed, depicted_people_consent_confirmed,
      likeness_consent_confirmed, confirmation, confirmed_by,
      request_hash, binding_hash, idempotency_key
    ) values (
      organization_id_value, project_id_value, spec_row.spec_id,
      spec_row.spec_version, spec_row.spec_hash, spec_row.prompt_hash,
      spec_row.product_id, strategy_id_value, selection_hash_value,
      source_basis_value,
      source_binding_id_value, source_binding_hash_value,
      source_snapshot_value,
      content_factory_private.json_hash(source_snapshot_value),
      role_asset_snapshot_value, role_asset_snapshot_hash_value,
      strategy_snapshot_value, strategy_snapshot_hash_value,
      'generation-strategy-attestation-v1', source_rights_value,
      transformative_use_value, product_assets_rights_value,
      depicted_people_consent_value, likeness_consent_value, true,
      actor_id_value, request_hash_value, binding_hash_value,
      idempotency_key_value
    ) returning * into binding_row;

    insert into content_factory.generation_spec_strategy_assets (
      organization_id, binding_id, project_id, product_id, role, ordinal,
      media_object_id, media_sha256_snapshot, media_kind_snapshot,
      mime_type_snapshot, media_product_id_snapshot,
      rights_confirmed_snapshot, likeness_consent_snapshot
    )
    select
      organization_id_value, binding_row.id, project_id_value,
      spec_row.product_id, asset.value ->> 'role',
      (asset.value ->> 'ordinal')::smallint,
      (asset.value ->> 'media_object_id')::uuid,
      asset.value ->> 'sha256', asset.value ->> 'kind',
      asset.value ->> 'mime_type',
      nullif(asset.value ->> 'product_id', '')::uuid,
      true, (asset.value ->> 'likeness_consent')::boolean
    from jsonb_array_elements(role_asset_snapshot_value) asset(value);

    if not content_factory_private.generation_strategy_binding_current(
      organization_id_value, binding_row.id
    ) then
      raise exception using errcode = '55000',
        message = 'generation_strategy_binding_invalid';
    end if;

    insert into content_factory.factory_events (
      organization_id, profile_id, event_name, source, entity_type,
      entity_id, properties, idempotency_key
    ) values (
      organization_id_value, actor_id_value, 'generation_strategy_bound',
      'system', 'generation_spec_strategy_binding', binding_row.id::text,
      jsonb_build_object(
        'project_id', project_id_value,
        'spec_id', spec_row.spec_id,
        'spec_version', spec_row.spec_version,
        'strategy_id', strategy_id_value,
        'source_basis', source_basis_value,
        'strategy_snapshot_hash', strategy_snapshot_hash_value,
        'provider_call_started', false,
        'paid_start_integrated', false
      ),
      'generation-strategy-bound:' || binding_row.id::text
    );
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-spec-strategy-binding-v1',
    'binding', jsonb_build_object(
      'id', binding_row.id,
      'project_id', binding_row.project_id,
      'spec_id', binding_row.spec_id,
      'spec_version', binding_row.spec_version,
      'spec_hash', binding_row.spec_hash,
      'product_id', binding_row.product_id,
      'strategy_id', binding_row.strategy_id,
      'selection_hash', binding_row.selection_hash,
      'source_basis', binding_row.source_basis,
      'source_binding_id', binding_row.source_binding_id,
      'source_binding_hash', binding_row.source_binding_hash,
      'role_assets', binding_row.role_asset_snapshot,
      'strategy_snapshot_hash', binding_row.strategy_snapshot_hash,
      'binding_hash', binding_row.binding_hash,
      'bound_at', binding_row.bound_at
    ),
    'contract', jsonb_build_object(
      'append_only', true,
      'paid_start_integrated', false,
      'provider_call_started', false,
      'job_snapshot_created', false,
      'edge_must_call_binder', true,
      'launch_enabled', false
    )
  );
end;
$$;

revoke all on function public.system_bind_generation_spec_strategy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_bind_generation_spec_strategy(jsonb)
  to service_role;

create or replace function
  content_factory_private.snapshot_generation_job_strategy()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  snapshot_value jsonb;
  snapshot_hash_value text;
begin
  -- A NULL strategy binding is the explicit legacy path.  Never infer a
  -- strategy from provider/model/input fields on historical or ordinary jobs.
  if new.generation_spec_id is null then
    return new;
  end if;

  select binding.* into binding_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = new.organization_id
    and binding.spec_id = new.generation_spec_id
    and binding.spec_version = new.generation_spec_version
    and binding.spec_hash = new.generation_spec_hash;
  if binding_row.id is null then
    return new;
  end if;

  if new.project_id is distinct from binding_row.project_id
     or new.product_id is distinct from binding_row.product_id
     or new.requested_by is distinct from binding_row.confirmed_by
     or not content_factory_private.generation_strategy_binding_current(
       new.organization_id, binding_row.id
     ) then
    raise exception using errcode = '55000',
      message = 'generation_job_strategy_binding_invalid';
  end if;

  snapshot_value := jsonb_build_object(
    'version', 'generation-job-strategy-snapshot-v1',
    'organization_id', new.organization_id,
    'project_id', new.project_id,
    'batch_id', new.batch_id,
    'generation_job_id', new.id,
    'spec_strategy_binding_id', binding_row.id,
    'strategy', binding_row.strategy_snapshot
  );
  snapshot_hash_value := content_factory_private.json_hash(snapshot_value);

  insert into content_factory.generation_job_strategy_snapshots (
    organization_id, project_id, batch_id, generation_job_id,
    spec_strategy_binding_id, spec_id, spec_version, spec_hash, product_id,
    strategy_id, source_basis, snapshot_version, strategy_snapshot,
    strategy_snapshot_hash, bound_by
  ) values (
    new.organization_id, new.project_id, new.batch_id, new.id,
    binding_row.id, binding_row.spec_id, binding_row.spec_version,
    binding_row.spec_hash, binding_row.product_id, binding_row.strategy_id,
    binding_row.source_basis, 'generation-job-strategy-snapshot-v1',
    snapshot_value, snapshot_hash_value, binding_row.confirmed_by
  );

  insert into content_factory.factory_events (
    organization_id, profile_id, event_name, source, entity_type,
    entity_id, properties, idempotency_key
  ) values (
    new.organization_id, new.requested_by,
    'generation_strategy_snapshotted', 'system',
    'generation_job_strategy_snapshot', new.id::text,
    jsonb_build_object(
      'project_id', new.project_id,
      'batch_id', new.batch_id,
      'spec_strategy_binding_id', binding_row.id,
      'strategy_id', binding_row.strategy_id,
      'source_basis', binding_row.source_basis,
      'strategy_snapshot_hash', snapshot_hash_value,
      'provider_call_started', false
    ),
    'generation-strategy-snapshotted:' || new.id::text
  );
  return new;
end;
$$;

revoke all on function
  content_factory_private.snapshot_generation_job_strategy()
  from public, anon, authenticated, service_role;

create trigger generation_job_strategy_snapshot_capture
after insert on content_factory.generation_jobs
for each row execute function
  content_factory_private.snapshot_generation_job_strategy();

create or replace function
  content_factory_private.record_generation_strategy_status_event()
returns trigger
language plpgsql
volatile
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  snapshot_row content_factory.generation_job_strategy_snapshots%rowtype;
  transition_ordinal_value integer;
  previous_status_value text;
  event_name_value text;
  event_hash_value text;
begin
  if tg_op = 'UPDATE' and new.status is not distinct from old.status then
    return new;
  end if;
  select snapshot.* into snapshot_row
  from content_factory.generation_job_strategy_snapshots snapshot
  where snapshot.organization_id = new.organization_id
    and snapshot.generation_job_id = new.id;
  if snapshot_row.id is null then
    return new;
  end if;

  if tg_op = 'INSERT' then
    transition_ordinal_value := 1;
    previous_status_value := null;
    event_name_value := 'generation_strategy_job_created';
  else
    select coalesce(max(event.transition_ordinal), 0) + 1
      into transition_ordinal_value
    from content_factory.generation_strategy_status_events event
    where event.organization_id = new.organization_id
      and event.generation_job_id = new.id;
    previous_status_value := old.status;
    event_name_value := 'generation_strategy_job_status_changed';
  end if;

  event_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'version', 'generation-strategy-status-event-v1',
    'organization_id', new.organization_id,
    'project_id', snapshot_row.project_id,
    'batch_id', new.batch_id,
    'generation_job_id', new.id,
    'spec_strategy_binding_id', snapshot_row.spec_strategy_binding_id,
    'strategy_id', snapshot_row.strategy_id,
    'transition_ordinal', transition_ordinal_value,
    'event_name', event_name_value,
    'previous_status', to_jsonb(previous_status_value),
    'job_status', new.status
  ));
  insert into content_factory.generation_strategy_status_events (
    organization_id, project_id, batch_id, generation_job_id,
    spec_strategy_binding_id, strategy_id, transition_ordinal, event_name,
    previous_status, job_status, event_hash
  ) values (
    new.organization_id, snapshot_row.project_id, new.batch_id, new.id,
    snapshot_row.spec_strategy_binding_id, snapshot_row.strategy_id,
    transition_ordinal_value, event_name_value, previous_status_value,
    new.status, event_hash_value
  );
  return new;
end;
$$;

revoke all on function
  content_factory_private.record_generation_strategy_status_event()
  from public, anon, authenticated, service_role;

create trigger generation_job_strategy_status_capture
after insert or update of status on content_factory.generation_jobs
for each row execute function
  content_factory_private.record_generation_strategy_status_event();

create view content_factory.generation_strategy_status_projection as
select distinct on (event.organization_id, event.generation_job_id)
  event.organization_id,
  event.project_id,
  event.batch_id,
  event.generation_job_id,
  event.spec_strategy_binding_id,
  event.strategy_id,
  event.transition_ordinal,
  event.event_name,
  event.previous_status,
  event.job_status,
  event.event_hash,
  event.occurred_at
from content_factory.generation_strategy_status_events event
order by
  event.organization_id, event.generation_job_id,
  event.transition_ordinal desc;

revoke all on content_factory.generation_strategy_status_projection
  from public, anon, authenticated, service_role;
grant select on content_factory.generation_strategy_status_projection
  to service_role;

create or replace function
  content_factory_private.generation_strategy_recipe(p_strategy_id text)
returns text
language sql
immutable
strict
set search_path = ''
as $$
  select case p_strategy_id
    when 'viral_avatar_ugc' then 'product_ugc'
    when 'viral_product_swap' then 'product_swap'
    when 'viral_rebuild' then 'product_ad'
    else null
  end
$$;

revoke all on function
  content_factory_private.generation_strategy_recipe(text)
  from public, anon, authenticated, service_role;

create or replace function
  content_factory_private.generation_strategy_recipe_price(
    p_strategy_id text,
    p_duration_seconds integer,
    p_resolution text,
    p_ratio text,
    p_audio boolean
  )
returns jsonb
language plpgsql
immutable
strict
set search_path = ''
as $$
#variable_conflict use_variable
declare
  recipe_value text;
  base_credits integer;
  incremental_credits integer;
  credits_value integer;
  cost_usd_value text;
  input_mode_value text;
begin
  recipe_value := content_factory_private.generation_strategy_recipe(
    p_strategy_id
  );
  if recipe_value is null
     or p_duration_seconds not between 4 and 15
     or p_resolution not in ('720p', '1080p')
     or (
       p_strategy_id = 'viral_avatar_ugc'
       and p_ratio <> case p_resolution
         when '720p' then '720:1280' else '1080:1920' end
     )
     or (p_strategy_id = 'viral_product_swap' and p_ratio <> 'source')
     or (
       p_strategy_id = 'viral_rebuild'
       and not (
         (p_resolution = '720p' and p_ratio in (
           '1280:720', '720:1280', '960:960', '834:1112'
         ))
         or
         (p_resolution = '1080p' and p_ratio in (
           '1920:1080', '1080:1920', '1440:1440', '1248:1664'
         ))
       )
     ) then
    return null;
  end if;

  base_credits := case p_strategy_id
    when 'viral_avatar_ugc' then
      case p_resolution when '720p' then 192 else 208 end
    when 'viral_product_swap' then
      case p_resolution when '720p' then 212 else 228 end
    when 'viral_rebuild' then
      case p_resolution when '720p' then 200 else 216 end
  end;
  incremental_credits := case p_resolution
    when '720p' then 36 else 40 end;
  credits_value := base_credits
    + ((p_duration_seconds - 4) * incremental_credits);
  cost_usd_value := to_char(
    credits_value::numeric / 100::numeric, 'FM999990.00'
  );
  input_mode_value := case p_strategy_id
    when 'viral_avatar_ugc' then 'character_and_product_images'
    when 'viral_product_swap' then 'video_and_product_images'
    when 'viral_rebuild' then 'product_images'
  end;

  return jsonb_build_object(
    'version', 'generation-strategy-price-snapshot-v1',
    'strategy_id', p_strategy_id,
    'provider', 'runway',
    'recipe', recipe_value,
    'input_mode', input_mode_value,
    'duration_seconds', p_duration_seconds,
    'resolution', p_resolution,
    'ratio', p_ratio,
    'audio', p_audio,
    'estimated_credits', credits_value,
    'estimated_pre_tax_usd_minor', credits_value,
    'estimated_cost_minor', credits_value,
    'estimated_cost_usd', cost_usd_value,
    'currency', 'USD',
    'credit_unit_cost_minor', 1,
    'catalog_version', '2026-08-14.v1',
    'pricing_version', 'runway-recipe-credits-2026-08-14.v1',
    'recipe_version', '2026-06',
    'spend_confirmation', concat(
      'RUNWAY_', upper(recipe_value), '_', p_duration_seconds::text, 'S_',
      upper(p_resolution), '_',
      case when p_audio then 'AUDIO' else 'SILENT' end,
      '_USD_', cost_usd_value
    )
  );
end;
$$;

revoke all on function
  content_factory_private.generation_strategy_recipe_price(
    text, integer, text, text, boolean
  ) from public, anon, authenticated, service_role;

create or replace function public.system_resolve_generation_strategy_price(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  strategy_id_value text;
  duration_seconds_value integer;
  resolution_value text;
  ratio_value text;
  audio_value boolean;
  price_value jsonb;
  price_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'strategy_id', 'duration_seconds', 'resolution', 'ratio',
       'audio'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'strategy_id', 'duration_seconds', 'resolution', 'ratio',
       'audio'
     ]::text[]
     or p_payload ->> 'version' <>
          'generation-strategy-price-request-v1'
     or jsonb_typeof(p_payload -> 'duration_seconds') <> 'number'
     or coalesce(p_payload ->> 'duration_seconds', '') !~ '^[0-9]{1,2}$'
     or jsonb_typeof(p_payload -> 'audio') <> 'boolean' then
    raise exception using errcode = '22023',
      message = 'generation_strategy_price_payload_invalid';
  end if;
  strategy_id_value := lower(btrim(p_payload ->> 'strategy_id'));
  duration_seconds_value := (p_payload ->> 'duration_seconds')::integer;
  resolution_value := lower(btrim(p_payload ->> 'resolution'));
  ratio_value := lower(btrim(p_payload ->> 'ratio'));
  audio_value := (p_payload ->> 'audio')::boolean;
  price_value := content_factory_private.generation_strategy_recipe_price(
    strategy_id_value, duration_seconds_value, resolution_value,
    ratio_value, audio_value
  );
  if price_value is null then
    raise exception using errcode = '22023',
      message = 'generation_strategy_price_sku_invalid';
  end if;
  price_hash_value := content_factory_private.json_hash(price_value);
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-price-response-v1',
    'price', price_value || jsonb_build_object(
      'price_hash', price_hash_value
    ),
    'contract', jsonb_build_object(
      'server_authoritative', true,
      'provider_call_started', false,
      'paid_start_integrated', false,
      'launch_enabled', false
    )
  );
end;
$$;

revoke all on function public.system_resolve_generation_strategy_price(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_resolve_generation_strategy_price(jsonb)
  to service_role;

create or replace function public.system_resolve_and_bind_generation_strategy(
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
  actor_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  idempotency_key_value text;
  selection_value jsonb;
  attestations_value jsonb;
  assets_value jsonb;
  strategy_id_value text;
  duration_seconds_value integer;
  resolution_value text;
  ratio_value text;
  audio_value boolean;
  asset_value jsonb;
  asset_role_value text;
  asset_media_id_value uuid;
  asset_duration_value numeric;
  seen_media_ids uuid[] := array[]::uuid[];
  source_media_id_value uuid;
  avatar_media_id_value uuid;
  original_product_media_id_value uuid;
  target_media_ids uuid[] := array[]::uuid[];
  style_media_ids uuid[] := array[]::uuid[];
  source_count integer := 0;
  avatar_count integer := 0;
  original_product_count integer := 0;
  target_count integer := 0;
  style_count integer := 0;
  reference_ordinal integer := 0;
  style_ordinal integer := 0;
  spec_row content_factory.generation_spec_versions%rowtype;
  media_row content_factory.media_objects%rowtype;
  source_attachment_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  role_assets_value jsonb := '[]'::jsonb;
  low_level_result jsonb;
  price_value jsonb;
  price_hash_value text;
  selection_hash_value text;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'selection', 'confirmation',
       'idempotency_key'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'selection', 'confirmation',
       'idempotency_key'
     ]::text[]
     or p_payload ->> 'version' <>
          'generation-strategy-resolve-bind-request-v1'
     or p_payload -> 'confirmation' is distinct from 'true'::jsonb
     or jsonb_typeof(p_payload -> 'selection') <> 'object'
     or jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[1-9][0-9]{0,5}$'
  then
    raise exception using errcode = '22023',
      message = 'generation_strategy_resolve_bind_payload_invalid';
  end if;
  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(p_payload, 'actor_id');
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  idempotency_key_value := btrim(p_payload ->> 'idempotency_key');
  selection_value := p_payload -> 'selection';
  if spec_hash_value !~ '^[0-9a-f]{64}$'
     or length(idempotency_key_value) not between 8 and 180
     or idempotency_key_value ~ '[[:cntrl:]]' then
    raise exception using errcode = '22023',
      message = 'generation_strategy_resolve_bind_payload_invalid';
  end if;

  strategy_id_value := lower(btrim(selection_value ->> 'strategy_id'));
  if strategy_id_value not in (
       'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
     )
     or selection_value ->> 'version' <> '2026-08-14.v1'
     or selection_value ->> 'recipe_version' <> '2026-06'
     or jsonb_typeof(selection_value -> 'duration_seconds') <> 'number'
     or coalesce(selection_value ->> 'duration_seconds', '') !~
          '^[0-9]{1,2}$'
     or jsonb_typeof(selection_value -> 'audio') <> 'boolean'
     or jsonb_typeof(selection_value -> 'assets') <> 'array'
     or jsonb_typeof(selection_value -> 'attestations') <> 'object' then
    raise exception using errcode = '22023',
      message = 'generation_strategy_catalog_selection_invalid';
  end if;
  duration_seconds_value :=
    (selection_value ->> 'duration_seconds')::integer;
  audio_value := (selection_value ->> 'audio')::boolean;
  assets_value := selection_value -> 'assets';
  attestations_value := selection_value -> 'attestations';

  if strategy_id_value = 'viral_product_swap' then
    if selection_value - array[
         'version', 'strategy_id', 'recipe_version', 'duration_seconds',
         'resolution', 'audio', 'assets', 'attestations'
       ]::text[] <> '{}'::jsonb
       or not selection_value ?& array[
         'version', 'strategy_id', 'recipe_version', 'duration_seconds',
         'resolution', 'audio', 'assets', 'attestations'
       ]::text[]
       or jsonb_typeof(selection_value -> 'resolution') <> 'string' then
      raise exception using errcode = '22023',
        message = 'generation_strategy_catalog_selection_invalid';
    end if;
    resolution_value := lower(btrim(selection_value ->> 'resolution'));
    ratio_value := 'source';
  else
    if selection_value - array[
         'version', 'strategy_id', 'recipe_version', 'duration_seconds',
         'ratio', 'audio', 'assets', 'attestations'
       ]::text[] <> '{}'::jsonb
       or not selection_value ?& array[
         'version', 'strategy_id', 'recipe_version', 'duration_seconds',
         'ratio', 'audio', 'assets', 'attestations'
       ]::text[]
       or jsonb_typeof(selection_value -> 'ratio') <> 'string' then
      raise exception using errcode = '22023',
        message = 'generation_strategy_catalog_selection_invalid';
    end if;
    ratio_value := lower(btrim(selection_value ->> 'ratio'));
    resolution_value := case ratio_value
      when '720:1280' then '720p'
      when '1280:720' then '720p'
      when '960:960' then '720p'
      when '834:1112' then '720p'
      when '1080:1920' then '1080p'
      when '1920:1080' then '1080p'
      when '1440:1440' then '1080p'
      when '1248:1664' then '1080p'
      else null
    end;
  end if;
  price_value := content_factory_private.generation_strategy_recipe_price(
    strategy_id_value, duration_seconds_value, resolution_value,
    ratio_value, audio_value
  );
  if price_value is null then
    raise exception using errcode = '22023',
      message = 'generation_strategy_catalog_selection_invalid';
  end if;
  price_hash_value := content_factory_private.json_hash(price_value);

  if attestations_value - (case
       when strategy_id_value = 'viral_avatar_ugc'
       then array[
         'source_media_rights_confirmed', 'transformative_use_confirmed',
         'product_assets_rights_confirmed',
         'depicted_people_consent_confirmed',
         'avatar_likeness_consent_confirmed'
       ]::text[]
       else array[
         'source_media_rights_confirmed', 'transformative_use_confirmed',
         'product_assets_rights_confirmed',
         'depicted_people_consent_confirmed'
       ]::text[] end) <> '{}'::jsonb
     or not (attestations_value ?& (case
       when strategy_id_value = 'viral_avatar_ugc' then array[
         'source_media_rights_confirmed', 'transformative_use_confirmed',
         'product_assets_rights_confirmed',
         'depicted_people_consent_confirmed',
         'avatar_likeness_consent_confirmed'
       ]::text[]
       else array[
         'source_media_rights_confirmed', 'transformative_use_confirmed',
         'product_assets_rights_confirmed',
         'depicted_people_consent_confirmed'
       ]::text[] end))
     or exists (
       select 1
       from jsonb_each(attestations_value) attestation(key, value)
       where attestation.value is distinct from 'true'::jsonb
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_catalog_attestation_invalid';
  end if;

  for asset_value in
    select item.value
    from jsonb_array_elements(assets_value) with ordinality
      item(value, source_ordinal)
    order by item.source_ordinal
  loop
    if jsonb_typeof(asset_value) <> 'object'
       or jsonb_typeof(asset_value -> 'role') <> 'string'
       or jsonb_typeof(asset_value -> 'media_id') <> 'string' then
      raise exception using errcode = '22023',
        message = 'generation_strategy_catalog_asset_invalid';
    end if;
    asset_role_value := asset_value ->> 'role';
    begin
      asset_media_id_value := (asset_value ->> 'media_id')::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023',
        message = 'generation_strategy_catalog_asset_invalid';
    end;
    if asset_media_id_value =
         '00000000-0000-0000-0000-000000000000'::uuid
       or asset_media_id_value = any(seen_media_ids) then
      raise exception using errcode = '22023',
        message = 'generation_strategy_catalog_asset_invalid';
    end if;
    seen_media_ids := array_append(seen_media_ids, asset_media_id_value);

    if asset_role_value = 'source_video' then
      if asset_value - array[
           'role', 'media_id', 'duration_seconds'
         ]::text[] <> '{}'::jsonb
         or (
           strategy_id_value = 'viral_product_swap'
           and not (asset_value ? 'duration_seconds')
         )
         or (
           asset_value ? 'duration_seconds'
           and (
             jsonb_typeof(asset_value -> 'duration_seconds') <> 'number'
             or coalesce(asset_value ->> 'duration_seconds', '') !~
                  '^[0-9]+([.][0-9]+)?$'
           )
         ) then
        raise exception using errcode = '22023',
          message = 'generation_strategy_catalog_asset_invalid';
      end if;
      if asset_value ? 'duration_seconds' then
        asset_duration_value :=
          (asset_value ->> 'duration_seconds')::numeric;
        if asset_duration_value <= 0
           or (strategy_id_value = 'viral_product_swap'
             and asset_duration_value not between 1.8 and 15) then
          raise exception using errcode = '22023',
            message = 'generation_strategy_catalog_asset_invalid';
        end if;
      end if;
      source_count := source_count + 1;
      source_media_id_value := asset_media_id_value;
    elsif asset_role_value = 'avatar_image'
          and strategy_id_value = 'viral_avatar_ugc' then
      if asset_value - array['role', 'media_id']::text[] <> '{}'::jsonb then
        raise exception using errcode = '22023',
          message = 'generation_strategy_catalog_asset_invalid';
      end if;
      avatar_count := avatar_count + 1;
      avatar_media_id_value := asset_media_id_value;
    elsif asset_role_value = 'original_product_image'
          and strategy_id_value = 'viral_product_swap' then
      if asset_value - array['role', 'media_id']::text[] <> '{}'::jsonb then
        raise exception using errcode = '22023',
          message = 'generation_strategy_catalog_asset_invalid';
      end if;
      original_product_count := original_product_count + 1;
      original_product_media_id_value := asset_media_id_value;
    elsif asset_role_value = 'new_product_image'
          and strategy_id_value = 'viral_product_swap' then
      if asset_value - array['role', 'media_id', 'view']::text[] <>
           '{}'::jsonb
         or (
           asset_value ? 'view'
           and (
             jsonb_typeof(asset_value -> 'view') <> 'string'
             or asset_value ->> 'view' not in ('front', 'side', 'back')
           )
         ) then
        raise exception using errcode = '22023',
          message = 'generation_strategy_catalog_asset_invalid';
      end if;
      target_count := target_count + 1;
      target_media_ids := array_append(target_media_ids, asset_media_id_value);
    elsif asset_role_value = 'product_image'
          and strategy_id_value in ('viral_avatar_ugc', 'viral_rebuild') then
      if asset_value - array['role', 'media_id']::text[] <> '{}'::jsonb then
        raise exception using errcode = '22023',
          message = 'generation_strategy_catalog_asset_invalid';
      end if;
      target_count := target_count + 1;
      target_media_ids := array_append(target_media_ids, asset_media_id_value);
    elsif asset_role_value = 'style_image'
          and strategy_id_value = 'viral_rebuild' then
      if asset_value - array['role', 'media_id']::text[] <> '{}'::jsonb then
        raise exception using errcode = '22023',
          message = 'generation_strategy_catalog_asset_invalid';
      end if;
      style_count := style_count + 1;
      style_media_ids := array_append(style_media_ids, asset_media_id_value);
    else
      raise exception using errcode = '22023',
        message = 'generation_strategy_catalog_asset_invalid';
    end if;
  end loop;

  if source_count <> 1
     or (
       strategy_id_value = 'viral_avatar_ugc'
       and (avatar_count <> 1 or target_count <> 1
         or original_product_count <> 0 or style_count <> 0)
     )
     or (
       strategy_id_value = 'viral_product_swap'
       and (avatar_count <> 0 or original_product_count <> 1
         or target_count not between 1 and 10 or style_count <> 0)
     )
     or (
       strategy_id_value = 'viral_rebuild'
       and (avatar_count <> 0 or original_product_count <> 0
         or target_count not between 1 and 10
         or style_count not between 0 and 4)
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_catalog_asset_count_invalid';
  end if;

  select version.* into spec_row
  from content_factory.generation_spec_versions version
  where version.organization_id = organization_id_value
    and version.spec_id = spec_id_value
    and version.spec_version = spec_version_value
    and version.spec_hash = spec_hash_value;
  if spec_row.version_id is null
     or not (spec_row.media_ids <@ target_media_ids)
     or not (spec_row.primary_media_id = any(target_media_ids))
     or (
       strategy_id_value = 'viral_avatar_ugc'
       and cardinality(spec_row.media_ids) <> 1
     ) then
    raise exception using errcode = '42501',
      message = 'generation_strategy_catalog_spec_assets_invalid';
  end if;

  select attachment.* into source_attachment_row
  from content_factory.research_exact_youtube_media_attachments attachment
  join content_factory.media_objects media
    on media.organization_id = attachment.organization_id
   and media.id = attachment.media_object_id
   and media.project_id = project_id_value
   and media.status = 'ready'
   and media.sha256 = attachment.media_sha256_snapshot
   and media.mime_type = 'video/mp4'
   and media.metadata ->> 'kind' = 'source_video'
   and media.metadata -> 'rights_confirmed' = 'true'::jsonb
   and media.artifact_class = 'source'
   and media.lifecycle_stage = 'sources'
  where attachment.organization_id = organization_id_value
    and attachment.project_id = project_id_value
    and attachment.media_object_id = source_media_id_value
    and attachment.rights_confirmed
    and attachment.media_matches_registered_source
    and attachment.status = 'attached';
  if source_attachment_row.id is null then
    raise exception using errcode = '42501',
      message = 'generation_strategy_exact_source_attachment_required';
  end if;

  select media.* into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id_value
    and media.project_id = project_id_value
    and media.id = spec_row.primary_media_id;
  if media_row.id is null then
    raise exception using errcode = '42501',
      message = 'generation_strategy_catalog_asset_invalid';
  end if;
  role_assets_value := role_assets_value || jsonb_build_array(
    jsonb_build_object(
      'role', 'product_primary', 'ordinal', 1,
      'media_object_id', media_row.id, 'sha256', media_row.sha256
    )
  );

  foreach asset_media_id_value in array spec_row.media_ids loop
    if asset_media_id_value <> spec_row.primary_media_id then
      reference_ordinal := reference_ordinal + 1;
      select media.* into media_row
      from content_factory.media_objects media
      where media.organization_id = organization_id_value
        and media.project_id = project_id_value
        and media.id = asset_media_id_value;
      role_assets_value := role_assets_value || jsonb_build_array(
        jsonb_build_object(
          'role', 'product_reference', 'ordinal', reference_ordinal,
          'media_object_id', media_row.id, 'sha256', media_row.sha256
        )
      );
    end if;
  end loop;
  foreach asset_media_id_value in array target_media_ids loop
    if not (asset_media_id_value = any(spec_row.media_ids)) then
      reference_ordinal := reference_ordinal + 1;
      select media.* into media_row
      from content_factory.media_objects media
      where media.organization_id = organization_id_value
        and media.project_id = project_id_value
        and media.id = asset_media_id_value;
      if media_row.id is null then
        raise exception using errcode = '42501',
          message = 'generation_strategy_catalog_asset_invalid';
      end if;
      role_assets_value := role_assets_value || jsonb_build_array(
        jsonb_build_object(
          'role', 'product_reference', 'ordinal', reference_ordinal,
          'media_object_id', media_row.id, 'sha256', media_row.sha256
        )
      );
    end if;
  end loop;

  if avatar_media_id_value is not null then
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = avatar_media_id_value;
    if media_row.id is null then
      raise exception using errcode = '42501',
        message = 'generation_strategy_catalog_asset_invalid';
    end if;
    role_assets_value := role_assets_value || jsonb_build_array(
      jsonb_build_object(
        'role', 'creator_avatar', 'ordinal', 1,
        'media_object_id', media_row.id, 'sha256', media_row.sha256
      )
    );
  end if;
  if original_product_media_id_value is not null then
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = original_product_media_id_value;
    if media_row.id is null then
      raise exception using errcode = '42501',
        message = 'generation_strategy_catalog_asset_invalid';
    end if;
    role_assets_value := role_assets_value || jsonb_build_array(
      jsonb_build_object(
        'role', 'original_product', 'ordinal', 1,
        'media_object_id', media_row.id, 'sha256', media_row.sha256
      )
    );
  end if;
  if strategy_id_value in ('viral_product_swap', 'viral_rebuild') then
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = source_media_id_value;
    role_assets_value := role_assets_value || jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video', 'ordinal', 1,
        'media_object_id', media_row.id, 'sha256', media_row.sha256
      )
    );
  end if;
  foreach asset_media_id_value in array style_media_ids loop
    style_ordinal := style_ordinal + 1;
    select media.* into media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = asset_media_id_value;
    if media_row.id is null then
      raise exception using errcode = '42501',
        message = 'generation_strategy_catalog_asset_invalid';
    end if;
    role_assets_value := role_assets_value || jsonb_build_array(
      jsonb_build_object(
        'role', 'style_reference', 'ordinal', style_ordinal,
        'media_object_id', media_row.id, 'sha256', media_row.sha256
      )
    );
  end loop;

  selection_hash_value := content_factory_private.json_hash(selection_value);
  low_level_result := public.system_bind_generation_spec_strategy(
    jsonb_build_object(
      'version', 'generation-strategy-binding-request-v1',
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'actor_id', actor_id_value,
      'spec_id', spec_id_value,
      'spec_version', spec_version_value,
      'spec_hash', spec_hash_value,
      'strategy_id', strategy_id_value,
      'selection_hash', selection_hash_value,
      'source_basis', 'exact_source_video',
      'source_binding_id', source_attachment_row.id,
      'source_binding_hash', source_attachment_row.attachment_hash,
      'role_assets', role_assets_value,
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true,
      'avatar_likeness_consent_confirmed',
        strategy_id_value = 'viral_avatar_ugc',
      'confirmation', true,
      'idempotency_key', idempotency_key_value
    )
  );
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-resolve-bind-response-v1',
    'binding', low_level_result -> 'binding',
    'selection', jsonb_build_object(
      'catalog_version', '2026-08-14.v1',
      'recipe_version', '2026-06',
      'pricing_version', 'runway-recipe-credits-2026-08-14.v1',
      'strategy_id', strategy_id_value,
      'recipe', content_factory_private.generation_strategy_recipe(
        strategy_id_value
      ),
      'selection_hash', selection_hash_value
    ),
    'price', price_value || jsonb_build_object(
      'price_hash', price_hash_value
    ),
    'contract', jsonb_build_object(
      'server_resolved_source_binding', true,
      'server_resolved_media_hashes', true,
      'browser_hashes_accepted', false,
      'browser_source_binding_accepted', false,
      'provider_call_started', false,
      'paid_start_integrated', false,
      'launch_enabled', false
    )
  );
end;
$$;

revoke all on function
  public.system_resolve_and_bind_generation_strategy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_resolve_and_bind_generation_strategy(jsonb)
  to service_role;

create or replace function public.system_generation_strategy_provider_policy(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id_value uuid;
  project_id_value uuid;
  actor_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  strategy_id_value text;
  receipt_id_value uuid;
  receipt_hash_value text;
  actor_role_value text;
  recipe_value text;
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  receipt_row content_factory.generation_provider_readiness_receipts%rowtype;
  binding_current_value boolean := false;
  approved_spec_value boolean := false;
  receipt_current_value boolean := false;
  start_path_integrated_value boolean := false;
  blockers_value jsonb := '[]'::jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'strategy_id',
       'provider_readiness_receipt_id',
       'provider_readiness_receipt_hash'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'actor_id', 'spec_id',
       'spec_version', 'spec_hash', 'strategy_id',
       'provider_readiness_receipt_id',
       'provider_readiness_receipt_hash'
     ]::text[]
     or p_payload ->> 'version' <>
          'generation-strategy-provider-policy-request-v1'
     or jsonb_typeof(p_payload -> 'spec_version') <> 'number'
     or coalesce(p_payload ->> 'spec_version', '') !~ '^[1-9][0-9]{0,5}$'
     or jsonb_typeof(p_payload -> 'provider_readiness_receipt_id')
          not in ('string', 'null')
     or jsonb_typeof(p_payload -> 'provider_readiness_receipt_hash')
          not in ('string', 'null')
     or (
       jsonb_typeof(p_payload -> 'provider_readiness_receipt_id') = 'null'
       and jsonb_typeof(p_payload -> 'provider_readiness_receipt_hash') <>
         'null'
     )
     or (
       jsonb_typeof(p_payload -> 'provider_readiness_receipt_id') = 'string'
       and jsonb_typeof(p_payload -> 'provider_readiness_receipt_hash') <>
         'string'
     ) then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_policy_payload_invalid';
  end if;

  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(p_payload, 'actor_id');
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  strategy_id_value := lower(btrim(p_payload ->> 'strategy_id'));
  recipe_value := content_factory_private.generation_strategy_recipe(
    strategy_id_value
  );
  if spec_hash_value !~ '^[0-9a-f]{64}$' or recipe_value is null then
    raise exception using errcode = '22023',
      message = 'generation_strategy_provider_policy_payload_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'provider_readiness_receipt_id') = 'string'
  then
    begin
      receipt_id_value :=
        (p_payload ->> 'provider_readiness_receipt_id')::uuid;
    exception when invalid_text_representation then
      raise exception using errcode = '22023',
        message = 'generation_strategy_provider_policy_payload_invalid';
    end;
    receipt_hash_value := lower(btrim(
      p_payload ->> 'provider_readiness_receipt_hash'
    ));
    if receipt_hash_value !~ '^[0-9a-f]{64}$' then
      raise exception using errcode = '22023',
        message = 'generation_strategy_provider_policy_payload_invalid';
    end if;
  end if;

  select membership.role into actor_role_value
  from content_factory.memberships membership
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where membership.organization_id = organization_id_value
    and membership.profile_id = actor_id_value
    and membership.status = 'active'
    and membership.role in ('owner', 'admin', 'producer', 'operator');
  if actor_role_value is null
     or not content_factory_private.workspace_project_access_allowed(
       organization_id_value, project_id_value, actor_id_value
     ) then
    raise exception using errcode = '42501',
      message = 'generation_strategy_provider_policy_access_required';
  end if;
  perform 1
  from content_factory.workspace_folders project
  where project.organization_id = organization_id_value
    and project.id = project_id_value
    and project.kind = 'project'
    and project.status = 'active';
  if not found then
    raise exception using errcode = '42501',
      message = 'generation_strategy_provider_policy_access_required';
  end if;

  select binding.* into binding_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value
    and binding.spec_hash = spec_hash_value
    and binding.strategy_id = strategy_id_value;
  binding_current_value := binding_row.id is not null
    and content_factory_private.generation_strategy_binding_current(
      organization_id_value, binding_row.id
    );

  select coalesce(
    head.state = 'approved'
      and head.spec_version = spec_version_value
      and head.spec_hash = spec_hash_value,
    false
  ) into approved_spec_value
  from content_factory.generation_spec_head_events head
  where head.organization_id = organization_id_value
    and head.spec_id = spec_id_value
  order by head.event_sequence desc
  limit 1;
  approved_spec_value := coalesce(approved_spec_value, false);

  if receipt_id_value is not null then
    select receipt.* into receipt_row
    from content_factory.generation_provider_readiness_receipts receipt
    where receipt.organization_id = organization_id_value
      and receipt.id = receipt_id_value
      and receipt.receipt_hash = receipt_hash_value
      and receipt.checked_by = actor_id_value
      and receipt.project_id = project_id_value
      and receipt.spec_id = spec_id_value
      and receipt.spec_version = spec_version_value
      and receipt.spec_hash = spec_hash_value
      and receipt.provider = 'runway'
      and receipt.model = recipe_value
      and receipt.receipt_version =
        'generation-strategy-provider-readiness-receipt-v1'
      and receipt.pricing_version =
        'runway-recipe-credits-2026-08-14.v1'
      and receipt.ready
      and receipt.expires_at > statement_timestamp();
    receipt_current_value := receipt_row.id is not null;
  end if;

  if binding_row.id is null then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_strategy_binding_missing');
  elsif not binding_current_value then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_strategy_binding_not_current');
  end if;
  if not approved_spec_value then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_spec_not_approved');
  end if;
  if receipt_id_value is null then
    blockers_value := blockers_value ||
      jsonb_build_array('provider_readiness_receipt_missing');
  elsif not receipt_current_value then
    blockers_value := blockers_value ||
      jsonb_build_array('provider_readiness_receipt_not_current');
  end if;
  if not start_path_integrated_value then
    blockers_value := blockers_value ||
      jsonb_build_array('generation_strategy_start_path_not_integrated');
  end if;

  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-provider-policy-response-v1',
    'execution_capabilities', jsonb_build_object(
      strategy_id_value, jsonb_build_object(
        'enabled', false,
        'catalog_version', '2026-08-14.v1',
        'strategy_id', strategy_id_value,
        'provider', 'runway',
        'recipe', recipe_value,
        'recipe_version', '2026-06',
        'provider_path', '/v1/recipes/' || recipe_value,
        'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
      )
    ),
    'context', jsonb_build_object(
      'strategy_id', strategy_id_value,
      'provider', 'runway',
      'recipe', recipe_value,
      'binding_id', to_jsonb(binding_row.id),
      'binding_hash', to_jsonb(binding_row.binding_hash),
      'provider_readiness_receipt_id', to_jsonb(receipt_row.id),
      'provider_readiness_receipt_hash', to_jsonb(receipt_row.receipt_hash),
      'catalog_version', '2026-08-14.v1',
      'recipe_version', '2026-06',
      'pricing_version', 'runway-recipe-credits-2026-08-14.v1'
    ),
    'checks', jsonb_build_object(
      'strategy_binding_current', binding_current_value,
      'generation_spec_approved', approved_spec_value,
      'provider_readiness_receipt_current', receipt_current_value,
      'start_path_integrated', start_path_integrated_value
    ),
    'blockers', blockers_value,
    'launch_enabled', false,
    'contract', jsonb_build_object(
      'read_only', true,
      'server_authoritative', true,
      'provider_call_started', false,
      'paid_start_integrated', false,
      'launch_enabled', false
    )
  );
end;
$$;

revoke all on function
  public.system_generation_strategy_provider_policy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.system_generation_strategy_provider_policy(jsonb)
  to service_role;

create or replace function public.creator_generation_strategy_repeat_data(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id_value uuid;
  project_id_value uuid;
  generation_job_id_value uuid;
  actor_role_value text;
  team_scope_value boolean;
  job_row content_factory.generation_jobs%rowtype;
  snapshot_row content_factory.generation_job_strategy_snapshots%rowtype;
  live_assets_current_value boolean := false;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
       'version', 'organization_id', 'project_id', 'generation_job_id'
     ]::text[] <> '{}'::jsonb
     or not p_payload ?& array[
       'version', 'organization_id', 'project_id', 'generation_job_id'
     ]::text[]
     or p_payload ->> 'version' <>
          'generation-strategy-repeat-request-v1' then
    raise exception using errcode = '22023',
      message = 'generation_strategy_repeat_payload_invalid';
  end if;
  user_id := content_factory_private.current_profile_id();
  organization_id_value := content_factory_private.resolve_organization(
    p_payload
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  generation_job_id_value := content_factory_private.require_uuid(
    p_payload, 'generation_job_id'
  );
  actor_role_value := content_factory_private.membership_role(
    organization_id_value, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope_value := actor_role_value = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);
  perform content_factory_private.require_workspace_project(
    organization_id_value, project_id_value
  );

  select job.* into job_row
  from content_factory.generation_jobs job
  join content_factory.generation_batches batch
    on batch.organization_id = job.organization_id
   and batch.id = job.batch_id
   and batch.project_id = project_id_value
  where job.organization_id = organization_id_value
    and job.id = generation_job_id_value
    and job.project_id = project_id_value
    and (team_scope_value or batch.created_by = user_id);
  if job_row.id is null then
    raise exception using errcode = '42501',
      message = 'generation_strategy_repeat_job_access_required';
  end if;

  select snapshot.* into snapshot_row
  from content_factory.generation_job_strategy_snapshots snapshot
  where snapshot.organization_id = organization_id_value
    and snapshot.project_id = project_id_value
    and snapshot.generation_job_id = generation_job_id_value;
  if snapshot_row.id is null then
    return jsonb_build_object(
      'ok', true,
      'version', 'generation-strategy-repeat-response-v1',
      'generation_job_id', generation_job_id_value,
      'legacy_strategy_absent', true,
      'repeat_data', null,
      'contract', jsonb_build_object(
        'read_only', true,
        'legacy_null_preserved', true,
        'confirmation_reused', false,
        'readiness_receipt_reused', false,
        'provider_call_started', false,
        'mutation_started', false
      )
    );
  end if;

  live_assets_current_value :=
    content_factory_private.generation_strategy_binding_current(
      organization_id_value, snapshot_row.spec_strategy_binding_id
    );
  return jsonb_build_object(
    'ok', true,
    'version', 'generation-strategy-repeat-response-v1',
    'generation_job_id', generation_job_id_value,
    'legacy_strategy_absent', false,
    'repeat_data', jsonb_build_object(
      'version', 'generation-strategy-repeat-data-v1',
      'strategy_id', snapshot_row.strategy_id,
      'source_basis', snapshot_row.source_basis,
      'spec_strategy_binding_id', snapshot_row.spec_strategy_binding_id,
      'spec_id', snapshot_row.spec_id,
      'spec_version', snapshot_row.spec_version,
      'spec_hash', snapshot_row.spec_hash,
      'product_id', snapshot_row.product_id,
      'strategy_snapshot', snapshot_row.strategy_snapshot -> 'strategy',
      'job_strategy_snapshot_hash', snapshot_row.strategy_snapshot_hash,
      'live_assets_current', live_assets_current_value,
      'requires_fresh_binding', true,
      'requires_fresh_human_confirmation', true,
      'requires_fresh_provider_readiness_receipt', true,
      'requires_fresh_price_confirmation', true
    ),
    'contract', jsonb_build_object(
      'read_only', true,
      'legacy_null_preserved', true,
      'confirmation_reused', false,
      'readiness_receipt_reused', false,
      'provider_call_started', false,
      'mutation_started', false
    )
  );
end;
$$;

revoke all on function public.creator_generation_strategy_repeat_data(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_generation_strategy_repeat_data(jsonb)
  to authenticated;


-- Strategy-aware override of the existing archive.  The source function is
-- copied byte-for-byte from 202608130003 except for the additive strategy
-- filter/fields and joins to immutable strategy ledgers.  Existing ACL,
-- period/status/provider/model/selection/quality filters and keyset order
-- remain unchanged; historical rows retain explicit NULL strategy fields.
create or replace function public.creator_generation_archive(
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
  user_id uuid;
  organization_id uuid;
  project_id_value uuid;
  actor_role text;
  team_scope boolean;
  period_value text := '4w';
  status_value text := 'all';
  provider_value text := 'all';
  model_value text := 'all';
  strategy_id_value text := 'all';
  content_kind_value text := 'all';
  selection_source_value text := 'all';
  quality_status_value text := 'all';
  query_value text := '';
  page_size integer := 50;
  cursor_at timestamptz;
  cursor_id uuid;
  period_cutoff timestamptz;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();

  if p_payload - array[
       'organization_id', 'project_id', 'period', 'status', 'provider',
       'model', 'strategy_id', 'content_kind', 'selection_source',
       'quality_status',
       'query', 'page_size', 'cursor'
     ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023', message = 'generation_archive_payload_invalid';
  end if;

  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id, true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  team_scope := actor_role = any(array[
    'owner', 'admin', 'producer', 'reviewer'
  ]);

  if not (p_payload ? 'project_id') then
    raise exception using errcode = '22023', message = 'project_id_required';
  end if;
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  perform content_factory_private.require_workspace_project(
    organization_id, project_id_value
  );

  if p_payload ? 'period' then
    if jsonb_typeof(p_payload -> 'period') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_period_invalid';
    end if;
    period_value := lower(btrim(p_payload ->> 'period'));
  end if;
  if period_value not in ('week', '4w', '12w', 'all') then
    raise exception using
      errcode = '22023', message = 'generation_archive_period_invalid';
  end if;

  if p_payload ? 'status' then
    if jsonb_typeof(p_payload -> 'status') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_status_invalid';
    end if;
    status_value := lower(btrim(p_payload ->> 'status'));
  end if;
  if status_value not in ('all', 'active', 'ready', 'issue') then
    raise exception using
      errcode = '22023', message = 'generation_archive_status_invalid';
  end if;

  if p_payload ? 'provider' then
    if jsonb_typeof(p_payload -> 'provider') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_provider_invalid';
    end if;
    provider_value := lower(btrim(p_payload ->> 'provider'));
  end if;
  if provider_value not in ('all', 'runway', 'google') then
    raise exception using
      errcode = '22023', message = 'generation_archive_provider_invalid';
  end if;

  if p_payload ? 'model' then
    if jsonb_typeof(p_payload -> 'model') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_model_invalid';
    end if;
    model_value := lower(btrim(p_payload ->> 'model'));
  end if;
  if model_value <> 'all'
     and model_value !~ '^[a-z0-9][a-z0-9._-]{0,79}$' then
    raise exception using
      errcode = '22023', message = 'generation_archive_model_invalid';
  end if;

  if p_payload ? 'strategy_id' then
    if jsonb_typeof(p_payload -> 'strategy_id') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_archive_strategy_id_invalid';
    end if;
    strategy_id_value := lower(btrim(p_payload ->> 'strategy_id'));
  end if;
  if strategy_id_value not in (
       'all', 'viral_avatar_ugc', 'viral_product_swap', 'viral_rebuild'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_archive_strategy_id_invalid';
  end if;

  if p_payload ? 'content_kind' then
    if jsonb_typeof(p_payload -> 'content_kind') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_archive_content_kind_invalid';
    end if;
    content_kind_value := lower(btrim(p_payload ->> 'content_kind'));
  end if;
  if content_kind_value not in ('all', 'photo', 'video') then
    raise exception using
      errcode = '22023',
      message = 'generation_archive_content_kind_invalid';
  end if;

  if p_payload ? 'selection_source' then
    if jsonb_typeof(p_payload -> 'selection_source') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_archive_selection_source_invalid';
    end if;
    selection_source_value :=
      lower(btrim(p_payload ->> 'selection_source'));
  end if;
  if selection_source_value not in (
       'all', 'system_recommendation', 'research_recommendation',
       'performance_recommendation', 'manual_choice',
       'alternative_after_block'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_archive_selection_source_invalid';
  end if;

  if p_payload ? 'quality_status' then
    if jsonb_typeof(p_payload -> 'quality_status') <> 'string' then
      raise exception using
        errcode = '22023',
        message = 'generation_archive_quality_status_invalid';
    end if;
    quality_status_value := lower(btrim(p_payload ->> 'quality_status'));
  end if;
  if quality_status_value not in (
       'all', 'accepted', 'needs_revalidation', 'unproven'
     ) then
    raise exception using
      errcode = '22023',
      message = 'generation_archive_quality_status_invalid';
  end if;

  if p_payload ? 'query' then
    if jsonb_typeof(p_payload -> 'query') <> 'string' then
      raise exception using
        errcode = '22023', message = 'generation_archive_query_invalid';
    end if;
    query_value := btrim(p_payload ->> 'query');
  end if;
  if length(query_value) > 120 or query_value ~ '[[:cntrl:]]' then
    raise exception using
      errcode = '22023', message = 'generation_archive_query_invalid';
  end if;

  if p_payload ? 'page_size' then
    if jsonb_typeof(p_payload -> 'page_size') <> 'number'
       or coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$' then
      raise exception using
        errcode = '22023', message = 'generation_archive_page_size_invalid';
    end if;
    begin
      page_size := (p_payload ->> 'page_size')::integer;
    exception when numeric_value_out_of_range then
      raise exception using
        errcode = '22023', message = 'generation_archive_page_size_invalid';
    end;
  end if;
  if page_size not between 1 and 100 then
    raise exception using
      errcode = '22023', message = 'generation_archive_page_size_invalid';
  end if;

  if p_payload ? 'cursor' then
    if jsonb_typeof(p_payload -> 'cursor') <> 'object' then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    if exists (
      select 1
      from jsonb_object_keys(p_payload -> 'cursor') cursor_key
      where cursor_key <> all(array['at', 'id'])
    ) then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    if jsonb_typeof(p_payload #> '{cursor,at}') <> 'string'
       or jsonb_typeof(p_payload #> '{cursor,id}') <> 'string'
       or nullif(btrim(coalesce(p_payload #>> '{cursor,at}', '')), '') is null
       or nullif(btrim(coalesce(p_payload #>> '{cursor,id}', '')), '') is null
    then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end if;
    begin
      cursor_at := (p_payload #>> '{cursor,at}')::timestamptz;
      cursor_id := (p_payload #>> '{cursor,id}')::uuid;
    exception
      when invalid_text_representation
        or invalid_datetime_format
        or datetime_field_overflow then
      raise exception using
        errcode = '22023', message = 'generation_archive_cursor_invalid';
    end;
  end if;

  period_cutoff := case period_value
    when 'week' then date_trunc('week', now())
    when '4w' then date_trunc('week', now()) - interval '3 weeks'
    when '12w' then date_trunc('week', now()) - interval '11 weeks'
    else null
  end;

  with candidates as materialized (
    select
      batch.id,
      batch.project_id,
      batch.name,
      batch.mode,
      batch.status,
      batch.total_requested,
      batch.total_created,
      batch.input,
      batch.created_at,
      product.sku,
      product.title as product_name,
      launch.selection_snapshot as generation_selection_snapshot,
      launch.snapshot_version as generation_selection_snapshot_version,
      launch.snapshot_hash as generation_selection_snapshot_hash,
      launch.provider,
      launch.model,
      launch.selection_snapshot ->> 'model_public_label'
        as model_public_label,
      launch.content_kind,
      launch.selection_source,
      launch.quality_status,
      launch.catalog_version,
      launch.pricing_version,
      launch.estimated_cost_minor,
      launch.estimated_credits,
      strategy_snapshot.strategy_id,
      strategy_snapshot.source_basis as strategy_source_basis,
      strategy_snapshot.snapshot_version
        as generation_strategy_snapshot_version,
      strategy_snapshot.strategy_snapshot
        as generation_strategy_snapshot,
      strategy_snapshot.strategy_snapshot_hash
        as generation_strategy_snapshot_hash,
      strategy_status.job_status as strategy_status,
      strategy_status.event_hash as strategy_status_event_hash
    from content_factory.generation_batches batch
    join content_factory.products product
      on product.organization_id = batch.organization_id
     and product.id = batch.product_id
    left join content_factory.generation_job_selection_snapshots launch
      on launch.organization_id = batch.organization_id
     and launch.project_id = batch.project_id
     and launch.batch_id = batch.id
    left join content_factory.generation_job_strategy_snapshots strategy_snapshot
      on strategy_snapshot.organization_id = batch.organization_id
     and strategy_snapshot.project_id = batch.project_id
     and strategy_snapshot.batch_id = batch.id
    left join content_factory.generation_strategy_status_projection
      strategy_status
      on strategy_status.organization_id = strategy_snapshot.organization_id
     and strategy_status.project_id = strategy_snapshot.project_id
     and strategy_status.generation_job_id =
           strategy_snapshot.generation_job_id
    where batch.organization_id = organization_id
      and batch.project_id = project_id_value
      and batch.archived_at is null
      and (team_scope or batch.created_by = user_id)
      and (period_cutoff is null or batch.created_at >= period_cutoff)
      and (
        status_value = 'all'
        or (
          status_value = 'active'
          and batch.status in ('queued', 'starting', 'submitted', 'processing')
        )
        or (
          status_value = 'ready'
          and batch.status in ('mock_ready', 'succeeded')
        )
        or (
          status_value = 'issue'
          and batch.status in ('failed', 'cancelled')
        )
      )
      and (provider_value = 'all' or launch.provider = provider_value)
      and (model_value = 'all' or lower(launch.model) = model_value)
      and (
        content_kind_value = 'all'
        or launch.content_kind = content_kind_value
      )
      and (
        selection_source_value = 'all'
        or launch.selection_source = selection_source_value
      )
      and (
        quality_status_value = 'all'
        or launch.quality_status = quality_status_value
      )
      and (
        strategy_id_value = 'all'
        or strategy_snapshot.strategy_id = strategy_id_value
      )
      and (
        query_value = ''
        or position(
          lower(query_value) in lower(concat_ws(
            ' ', batch.name, batch.id::text, product.sku, product.title,
            launch.model,
            launch.selection_snapshot ->> 'model_public_label',
            strategy_snapshot.strategy_id,
            strategy_snapshot.source_basis
          ))
        ) > 0
      )
      and (
        cursor_at is null
        or (batch.created_at, batch.id) < (cursor_at, cursor_id)
      )
    order by batch.created_at desc, batch.id desc
    limit page_size + 1
  ),
  page as materialized (
    select candidate.*
    from candidates candidate
    order by candidate.created_at desc, candidate.id desc
    limit page_size
  ),
  page_stats as (
    select count(*) > page_size as has_more
    from candidates
  ),
  last_row as (
    select page.created_at, page.id
    from page
    order by page.created_at asc, page.id asc
    limit 1
  )
  select jsonb_build_object(
    'ok', true,
    'project_id', project_id_value,
    'batches', coalesce((
      select jsonb_agg(jsonb_build_object(
        'id', page.id,
        'public_id', page.id,
        'project_id', page.project_id,
        'name', page.name,
        'sku', page.sku,
        'product_name', page.product_name,
        'mode', page.mode,
        'status', page.status,
        'total_requested', page.total_requested,
        'total_created', page.total_created,
        'total_accepted', page.total_created,
        'parameters', page.input,
        'provider', page.provider,
        'model', page.model,
        'model_public_label', page.model_public_label,
        'content_kind', page.content_kind,
        'selection_source', page.selection_source,
        'quality_status', page.quality_status,
        'catalog_version', page.catalog_version,
        'pricing_version', page.pricing_version,
        'estimated_cost_minor', page.estimated_cost_minor,
        'estimated_credits', page.estimated_credits,
        'generation_selection_snapshot', page.generation_selection_snapshot,
        'generation_selection_snapshot_version',
          page.generation_selection_snapshot_version,
        'generation_selection_snapshot_hash',
          page.generation_selection_snapshot_hash,
        'strategy_id', page.strategy_id,
        'strategy_source_basis', page.strategy_source_basis,
        'generation_strategy_snapshot', page.generation_strategy_snapshot,
        'generation_strategy_snapshot_version',
          page.generation_strategy_snapshot_version,
        'generation_strategy_snapshot_hash',
          page.generation_strategy_snapshot_hash,
        'strategy_status', page.strategy_status,
        'strategy_status_event_hash', page.strategy_status_event_hash,
        'strategy_repeat_data', case
          when page.strategy_id is null then null
          else jsonb_build_object(
            'version', 'generation-strategy-repeat-data-v1',
            'strategy_id', page.strategy_id,
            'source_basis', page.strategy_source_basis,
            'strategy_snapshot',
              page.generation_strategy_snapshot -> 'strategy',
            'job_strategy_snapshot_hash',
              page.generation_strategy_snapshot_hash,
            'requires_fresh_binding', true,
            'requires_fresh_human_confirmation', true,
            'requires_fresh_provider_readiness_receipt', true,
            'requires_fresh_price_confirmation', true
          )
        end,
        'created_at', page.created_at,
        '_cursor', jsonb_build_object(
          'at', page.created_at,
          'id', page.id
        )
      ) order by page.created_at desc, page.id desc)
      from page
    ), '[]'::jsonb),
    '_meta', jsonb_build_object(
      'page_size', page_size,
      'has_more', page_stats.has_more,
      'next_cursor', case
        when page_stats.has_more then jsonb_build_object(
          'at', last_row.created_at,
          'id', last_row.id
        )
        else null
      end,
      'period', period_value,
      'status', status_value,
      'provider', provider_value,
      'model', model_value,
      'strategy_id', strategy_id_value,
      'content_kind', content_kind_value,
      'selection_source', selection_source_value,
      'quality_status', quality_status_value,
      'query', query_value,
      'cursor_mode', 'keyset_created_at_id'
    )
  )
  into result
  from page_stats
  left join last_row on true;

  return result;
end;
$$;

revoke all on function public.creator_generation_archive(jsonb)
  from public, anon;
grant execute on function public.creator_generation_archive(jsonb)
  to authenticated;

comment on table content_factory.generation_spec_strategy_bindings is
  'Append-only human-confirmed binding of one approved spec version to one canonical business generation strategy.';
comment on table content_factory.generation_spec_strategy_assets is
  'Append-only exact role/media/hash ledger for one generation strategy binding; contains no object paths or signed URLs.';
comment on table content_factory.generation_job_strategy_snapshots is
  'Immutable job-time copy of the full canonical generation strategy binding.';
comment on table content_factory.generation_strategy_status_events is
  'Append-only strategy job status transition journal; the projection view selects only its latest event.';
comment on function public.system_bind_generation_spec_strategy(jsonb) is
  'Service-only low-level binder. Callers must server-resolve all source/media IDs and hashes; it does not start or authorize paid generation.';
comment on function public.system_resolve_generation_strategy_price(jsonb) is
  'Service-only canonical Runway recipe tariff resolver; performs no provider call and grants no launch authority.';
comment on function public.system_resolve_and_bind_generation_strategy(jsonb) is
  'Service-only catalog-selection wrapper: accepts browser media IDs but server-resolves exact source attachment identities and all media hashes before calling the low-level binder.';
comment on function public.system_generation_strategy_provider_policy(jsonb) is
  'Service-only fail-closed strategy launch policy projection; v1 remains disabled until the exact receipt writer and atomic start path are installed.';
comment on function public.creator_generation_strategy_repeat_data(jsonb) is
  'Read-only archived strategy settings. It never reuses confirmation, readiness, price authority, or starts a provider.';

notify pgrst, 'reload schema';

commit;
