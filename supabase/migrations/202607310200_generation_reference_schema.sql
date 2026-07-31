begin;

-- User supplied examples are job-scoped creative guidance. They are not
-- trusted product facts and never become autonomous learning evidence without
-- a separate attribution release.
create table if not exists content_factory.generation_reference_sets (
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    id uuid not null default extensions.gen_random_uuid(),
    product_id uuid not null,
    primary_media_id uuid not null,
    created_by uuid not null,
    sku text not null check (length(sku) between 1 and 120),
    product_name text not null check (length(product_name) between 2 and 180),
    platform text not null check (platform in (
      'instagram', 'tiktok', 'youtube', 'vk', 'telegram', 'wildberries'
    )),
    model text not null check (model in (
      'gen4_turbo', 'seedance2_fast', 'seedream5_lite'
    )),
    duration_seconds integer not null check (
      (model = 'seedream5_lite' and duration_seconds = 0)
      or (model = 'gen4_turbo' and duration_seconds in (2, 5, 8, 10))
      or (model = 'seedance2_fast' and duration_seconds in (4, 8, 12, 15))
    ),
    user_direction text not null default '' check (length(user_direction) <= 1200),
    status text not null default 'draft' check (status in (
      'draft', 'queued', 'processing', 'ready', 'failed', 'bound', 'archived'
    )),
    version bigint not null default 1 check (version >= 1),
    parser_version text,
    provider_model text,
    digest jsonb,
    digest_hash text check (
      digest_hash is null or digest_hash ~ '^[0-9a-f]{64}$'
    ),
    error_code text,
    error_message text,
    armed_brief_hash text check (
      armed_brief_hash is null or armed_brief_hash ~ '^[0-9a-f]{64}$'
    ),
    armed_at timestamptz,
    armed_expires_at timestamptz,
    bound_generation_job_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    primary key (organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, primary_media_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, bound_generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    check (
      (status in ('draft', 'queued', 'processing', 'failed', 'archived')
       and bound_generation_job_id is null)
      or status = 'ready'
      or (status = 'bound' and bound_generation_job_id is not null)
    ),
    check (
      (armed_brief_hash is null and armed_at is null and armed_expires_at is null)
      or (
        status = 'ready'
        and armed_brief_hash is not null
        and armed_at is not null
        and armed_expires_at > armed_at
      )
    ),
    check (
      (status in ('ready', 'bound') and digest is not null
       and digest_hash is not null and parser_version is not null
       and completed_at is not null)
      or status not in ('ready', 'bound')
    )
);

create index if not exists generation_reference_sets_actor_idx
  on content_factory.generation_reference_sets (
    organization_id, created_by, status, updated_at desc, id desc
  );
create index if not exists generation_reference_sets_armed_idx
  on content_factory.generation_reference_sets (
    organization_id, created_by, armed_expires_at desc
  ) where status = 'ready' and armed_brief_hash is not null;

create table if not exists content_factory.generation_reference_sources (
    organization_id uuid not null,
    set_id uuid not null,
    id uuid not null default extensions.gen_random_uuid(),
    client_id text not null
      check (client_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$'),
    parent_source_id uuid,
    parent_client_id text,
    source_type text not null
      check (source_type in ('link', 'image', 'video', 'video_frame')),
    source_url text,
    platform text not null default 'web' check (platform in (
      'youtube', 'tiktok', 'instagram', 'vk', 'telegram', 'wildberries',
      'ozon', 'web', 'upload'
    )),
    title text not null check (length(title) between 1 and 240),
    user_note text not null default '' check (length(user_note) <= 600),
    bucket_id text,
    object_name text,
    mime_type text,
    size_bytes bigint,
    sha256 text,
    timecode_seconds numeric(10, 3),
    status text not null
      check (status in ('uploading', 'ready', 'failed', 'archived')),
    created_by uuid not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, id),
    unique (organization_id, set_id, id),
    unique (organization_id, set_id, client_id),
    unique (bucket_id, object_name),
    foreign key (organization_id, set_id)
      references content_factory.generation_reference_sets(organization_id, id)
      on delete cascade,
    foreign key (organization_id, set_id, parent_source_id)
      references content_factory.generation_reference_sources(
        organization_id, set_id, id
      ),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (source_type = 'link' and source_url is not null and bucket_id is null
       and object_name is null and mime_type is null and size_bytes is null
       and sha256 is null and status in ('ready', 'archived'))
      or
      (source_type in ('image', 'video', 'video_frame')
       and source_url is null and bucket_id = 'contentengine-private'
       and object_name is not null and mime_type is not null)
    ),
    check (
      (source_type = 'video_frame' and parent_client_id is not null
       and timecode_seconds is not null and timecode_seconds >= 0)
      or
      (source_type <> 'video_frame' and parent_source_id is null
       and timecode_seconds is null)
    ),
    check (size_bytes is null or size_bytes between 128 and 52428800),
    check (sha256 is null or sha256 ~ '^[0-9a-f]{64}$')
);

create index if not exists generation_reference_sources_set_idx
  on content_factory.generation_reference_sources (
    organization_id, set_id, created_at, id
  );

alter table content_factory.generation_jobs
  add column if not exists reference_set_id uuid;

do $$
begin
  if not exists (
    select 1 from pg_catalog.pg_constraint constraint_row
    where constraint_row.conrelid = 'content_factory.generation_jobs'::regclass
      and constraint_row.conname = 'generation_jobs_reference_set_fkey'
  ) then
    alter table content_factory.generation_jobs
      add constraint generation_jobs_reference_set_fkey
      foreign key (organization_id, reference_set_id)
      references content_factory.generation_reference_sets(organization_id, id);
  end if;
end;
$$;

create index if not exists generation_jobs_reference_set_idx
  on content_factory.generation_jobs (
    organization_id, reference_set_id, created_at desc
  ) where reference_set_id is not null;

create table if not exists content_factory.generation_reference_bindings (
    organization_id uuid not null,
    generation_job_id uuid not null,
    reference_set_id uuid not null,
    digest_hash text not null check (digest_hash ~ '^[0-9a-f]{64}$'),
    parser_version text not null,
    source_ids jsonb not null check (
      jsonb_typeof(source_ids) = 'array'
      and jsonb_array_length(source_ids) between 1 and 6
    ),
    prompt_hash text not null check (prompt_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    primary key (organization_id, generation_job_id),
    foreign key (organization_id, generation_job_id)
      references content_factory.generation_jobs(organization_id, id),
    foreign key (organization_id, reference_set_id)
      references content_factory.generation_reference_sets(organization_id, id)
);

alter table content_factory.generation_reference_sets enable row level security;
alter table content_factory.generation_reference_sources enable row level security;
alter table content_factory.generation_reference_bindings enable row level security;
revoke all on content_factory.generation_reference_sets
  from public, anon, authenticated;
revoke all on content_factory.generation_reference_sources
  from public, anon, authenticated;
revoke all on content_factory.generation_reference_bindings
  from public, anon, authenticated;
grant all on content_factory.generation_reference_sets to service_role;
grant all on content_factory.generation_reference_sources to service_role;
grant all on content_factory.generation_reference_bindings to service_role;

commit;
