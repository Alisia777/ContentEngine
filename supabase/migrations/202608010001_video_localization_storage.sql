begin;

create or replace function content_factory_private.valid_video_localization_modes(
  value jsonb
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select
    jsonb_typeof(value) = 'array'
    and jsonb_array_length(value) between 1 and 3
    and not exists (
      select 1
      from jsonb_array_elements(value) item(element)
      where jsonb_typeof(item.element) <> 'string'
         or item.element #>> '{}' not in (
           'subtitles', 'dub_audio', 'lip_sync'
         )
    )
    and (
      select count(*) = count(distinct mode)
      from jsonb_array_elements_text(value) item(mode)
    )
$$;

create or replace function content_factory_private.valid_video_localization_checklist(
  value jsonb
)
returns boolean
language sql
immutable
set search_path = ''
as $$
  select
    jsonb_typeof(value) = 'object'
    and value - array[
      'product_fidelity', 'language_quality',
      'no_common_defect', 'rights_ok'
    ]::text[] = '{}'::jsonb
    and not exists (
      select 1
      from jsonb_each(value) item(key, element)
      where jsonb_typeof(item.element) <> 'boolean'
    )
$$;

create or replace function content_factory_private.require_language_tag(value text)
returns text
language plpgsql
immutable
set search_path = ''
as $$
declare
  normalized text;
begin
  normalized := lower(btrim(coalesce(value, '')));
  if normalized !~ '^[a-z]{2,3}(-[a-z0-9]{2,8})*$' then
    raise exception using errcode = '22023', message = 'language_tag_invalid';
  end if;
  return normalized;
end;
$$;

create or replace function content_factory_private.video_localization_provider(
  mode_value text
)
returns text
language plpgsql
immutable
strict
set search_path = ''
as $$
begin
  case mode_value
    when 'subtitles' then return 'internal_captions';
    when 'dub_audio' then return 'elevenlabs_dubbing';
    when 'lip_sync' then return 'heygen_lipsync_speed';
    else
      raise exception using
        errcode = '22023',
        message = 'localization_mode_invalid';
  end case;
end;
$$;

create or replace function content_factory_private.video_localization_cost_microusd(
  provider_value text,
  duration_value integer
)
returns bigint
language plpgsql
immutable
strict
set search_path = ''
as $$
begin
  if duration_value < 1 or duration_value > 3600 then
    raise exception using errcode = '22023', message = 'duration_invalid';
  end if;

  case provider_value
    when 'internal_captions' then
      return ceil(duration_value * 50000.0 / 60.0)::bigint;
    when 'elevenlabs_dubbing' then
      return ceil(duration_value * 500000.0 / 60.0)::bigint;
    when 'heygen_audio' then
      return duration_value::bigint * 33300;
    when 'heygen_lipsync_speed' then
      return duration_value::bigint * 33300;
    when 'heygen_lipsync_precision' then
      return duration_value::bigint * 66700;
    else
      raise exception using
        errcode = '22023',
        message = 'localization_provider_invalid';
  end case;
end;
$$;

create table if not exists content_factory.video_source_approvals (
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    media_object_id uuid not null,
    product_id uuid not null,
    source_relationship text not null
      check (source_relationship in ('owned', 'licensed')),
    source_language text not null
      check (source_language ~ '^[a-z]{2,3}(-[a-z0-9]{2,8})*$'),
    duration_seconds integer not null
      check (duration_seconds between 1 and 3600),
    rights_confirmed boolean not null check (rights_confirmed),
    source_qa_approved boolean not null check (source_qa_approved),
    speech_present boolean not null default true,
    on_screen_text_present boolean not null default false,
    asset_sha256 text not null check (asset_sha256 ~ '^[0-9a-f]{64}$'),
    status text not null default 'active'
      check (status in ('active', 'revoked')),
    reason text not null check (length(btrim(reason)) between 10 and 1000),
    approved_by uuid not null,
    approved_at timestamptz not null default now(),
    revoked_by uuid,
    revoked_at timestamptz,
    version bigint not null default 1 check (version >= 1),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, media_object_id),
    foreign key (organization_id, media_object_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, approved_by)
      references content_factory.memberships(organization_id, profile_id),
    foreign key (organization_id, revoked_by)
      references content_factory.memberships(organization_id, profile_id),
    check (
      (status = 'active' and revoked_by is null and revoked_at is null)
      or (status = 'revoked' and revoked_by is not null and revoked_at is not null)
    )
);

create index if not exists video_source_approvals_active_idx
  on content_factory.video_source_approvals (
    organization_id, product_id, approved_at desc, media_object_id
  ) where status = 'active';

create table if not exists content_factory.video_localization_batches (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null
      references content_factory.organizations(id) on delete cascade,
    product_id uuid not null,
    created_by uuid not null,
    target_language text not null
      check (target_language ~ '^[a-z]{2,3}(-[a-z0-9]{2,8})*$'),
    target_count integer not null default 10 check (target_count = 10),
    source_count integer not null check (source_count between 1 and 10),
    modes jsonb not null
      check (content_factory_private.valid_video_localization_modes(modes)),
    qa_gate_after_sequence integer not null default 2
      check (qa_gate_after_sequence = 2),
    status text not null default 'wave1_ready'
      check (status in (
        'wave1_ready', 'wave1_running', 'qa_required',
        'wave2_ready', 'wave2_running', 'completed',
        'paused', 'failed', 'cancelled'
      )),
    rate_card_snapshot_id text not null
      check (length(rate_card_snapshot_id) between 8 and 120),
    rate_card_snapshot jsonb not null
      check (jsonb_typeof(rate_card_snapshot) = 'object'),
    plan_hash text not null check (plan_hash ~ '^[0-9a-f]{64}$'),
    total_estimated_cost_microusd bigint not null
      check (total_estimated_cost_microusd >= 0),
    full_generation_baseline_microusd bigint not null
      check (full_generation_baseline_microusd >= 0),
    idempotency_key text not null
      check (length(idempotency_key) between 8 and 180),
    version bigint not null default 1 check (version >= 1),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, created_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key),
    unique (organization_id, id)
);

create index if not exists video_localization_batches_queue_idx
  on content_factory.video_localization_batches (
    organization_id, status, created_at desc, id desc
  );

create table if not exists content_factory.video_localization_assignments (
    id uuid primary key default extensions.gen_random_uuid(),
    organization_id uuid not null,
    batch_id uuid not null,
    product_id uuid not null,
    source_media_id uuid not null,
    output_media_id uuid,
    sequence integer not null check (sequence between 1 and 100),
    wave integer not null check (wave in (1, 2)),
    mode text not null
      check (mode in ('subtitles', 'dub_audio', 'lip_sync')),
    provider text not null
      check (provider in (
        'internal_captions', 'elevenlabs_dubbing',
        'heygen_audio', 'heygen_lipsync_speed',
        'heygen_lipsync_precision'
      )),
    source_language text not null
      check (source_language ~ '^[a-z]{2,3}(-[a-z0-9]{2,8})*$'),
    target_language text not null
      check (target_language ~ '^[a-z]{2,3}(-[a-z0-9]{2,8})*$'),
    duration_seconds integer not null check (duration_seconds between 1 and 3600),
    source_asset_sha256 text not null check (source_asset_sha256 ~ '^[0-9a-f]{64}$'),
    assignment_hash text not null check (assignment_hash ~ '^[0-9a-f]{64}$'),
    estimated_cost_microusd bigint not null check (estimated_cost_microusd >= 0),
    actual_cost_microusd bigint check (actual_cost_microusd >= 0),
    requires_manual_text_edit boolean not null default false,
    status text not null default 'planned'
      check (status in (
        'planned', 'ready', 'reserved', 'submitted', 'processing',
        'succeeded', 'failed', 'unknown', 'blocked', 'cancelled'
      )),
    failure_code text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (organization_id, batch_id)
      references content_factory.video_localization_batches(organization_id, id)
      on delete cascade,
    foreign key (organization_id, product_id)
      references content_factory.products(organization_id, id),
    foreign key (organization_id, source_media_id)
      references content_factory.media_objects(organization_id, id),
    foreign key (organization_id, output_media_id)
      references content_factory.media_objects(organization_id, id),
    unique (batch_id, sequence),
    unique (batch_id, assignment_hash),
    unique (organization_id, id),
    check (source_language <> target_language),
    check (
      (status = 'succeeded' and output_media_id is not null)
      or (status <> 'succeeded' and output_media_id is null)
    ),
    check (failure_code is null or length(failure_code) between 3 and 120)
);

create index if not exists video_localization_assignments_queue_idx
  on content_factory.video_localization_assignments (
    organization_id, status, wave, sequence, id
  );

create index if not exists video_localization_assignments_batch_idx
  on content_factory.video_localization_assignments (
    organization_id, batch_id, sequence
  );

create table if not exists content_factory.video_localization_qa_decisions (
    organization_id uuid not null,
    batch_id uuid not null,
    wave integer not null check (wave = 1),
    decision text not null check (decision in ('approved', 'rejected')),
    checklist jsonb not null
      check (content_factory_private.valid_video_localization_checklist(checklist)),
    reason text not null check (length(btrim(reason)) between 5 and 1000),
    decided_by uuid not null,
    decided_at timestamptz not null default now(),
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    primary key (organization_id, batch_id, wave),
    foreign key (organization_id, batch_id)
      references content_factory.video_localization_batches(organization_id, id)
      on delete cascade,
    foreign key (organization_id, decided_by)
      references content_factory.memberships(organization_id, profile_id),
    unique (organization_id, idempotency_key)
);

create table if not exists content_factory_private.video_localization_provider_operations (
    organization_id uuid not null,
    assignment_id uuid not null,
    provider text not null,
    idempotency_key text not null check (length(idempotency_key) between 8 and 180),
    request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    provider_task_ref_hash text check (provider_task_ref_hash ~ '^[0-9a-f]{64}$'),
    status text not null
      check (status in (
        'reserved', 'submitted', 'processing',
        'settled', 'released', 'frozen', 'failed'
      )),
    reserved_cost_microusd bigint not null check (reserved_cost_microusd >= 0),
    actual_cost_microusd bigint check (actual_cost_microusd >= 0),
    failure_code text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (organization_id, assignment_id),
    foreign key (organization_id, assignment_id)
      references content_factory.video_localization_assignments(organization_id, id)
      on delete cascade,
    unique (organization_id, idempotency_key),
    check (failure_code is null or length(failure_code) between 3 and 120)
);

alter table content_factory.video_source_approvals enable row level security;
alter table content_factory.video_localization_batches enable row level security;
alter table content_factory.video_localization_assignments enable row level security;
alter table content_factory.video_localization_qa_decisions enable row level security;

revoke all on content_factory.video_source_approvals
  from public, anon, authenticated;
revoke all on content_factory.video_localization_batches
  from public, anon, authenticated;
revoke all on content_factory.video_localization_assignments
  from public, anon, authenticated;
revoke all on content_factory.video_localization_qa_decisions
  from public, anon, authenticated;
revoke all on content_factory_private.video_localization_provider_operations
  from public, anon, authenticated;

grant all on content_factory.video_source_approvals to service_role;
grant all on content_factory.video_localization_batches to service_role;
grant all on content_factory.video_localization_assignments to service_role;
grant all on content_factory.video_localization_qa_decisions to service_role;
grant all on content_factory_private.video_localization_provider_operations to service_role;

drop trigger if exists set_video_source_approvals_updated_at
  on content_factory.video_source_approvals;
create trigger set_video_source_approvals_updated_at
before update on content_factory.video_source_approvals
for each row execute function content_factory_private.set_updated_at();

drop trigger if exists set_video_localization_batches_updated_at
  on content_factory.video_localization_batches;
create trigger set_video_localization_batches_updated_at
before update on content_factory.video_localization_batches
for each row execute function content_factory_private.set_updated_at();

drop trigger if exists set_video_localization_assignments_updated_at
  on content_factory.video_localization_assignments;
create trigger set_video_localization_assignments_updated_at
before update on content_factory.video_localization_assignments
for each row execute function content_factory_private.set_updated_at();

drop trigger if exists set_video_localization_provider_operations_updated_at
  on content_factory_private.video_localization_provider_operations;
create trigger set_video_localization_provider_operations_updated_at
before update on content_factory_private.video_localization_provider_operations
for each row execute function content_factory_private.set_updated_at();

commit;
