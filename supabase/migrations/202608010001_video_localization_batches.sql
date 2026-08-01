begin;

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
    rights_confirmed boolean not null default false
      check (rights_confirmed),
    source_qa_approved boolean not null default false
      check (source_qa_approved),
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
    modes jsonb not null check (
      jsonb_typeof(modes) = 'array'
      and jsonb_array_length(modes) between 1 and 3
    ),
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
    unique (organization_id, assignment_hash),
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
    checklist jsonb not null check (jsonb_typeof(checklist) = 'object'),
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

create trigger set_video_source_approvals_updated_at
before update on content_factory.video_source_approvals
for each row execute function content_factory_private.set_updated_at();

create trigger set_video_localization_batches_updated_at
before update on content_factory.video_localization_batches
for each row execute function content_factory_private.set_updated_at();

create trigger set_video_localization_assignments_updated_at
before update on content_factory.video_localization_assignments
for each row execute function content_factory_private.set_updated_at();

create trigger set_video_localization_provider_operations_updated_at
before update on content_factory_private.video_localization_provider_operations
for each row execute function content_factory_private.set_updated_at();

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

create or replace function content_factory_private.video_localization_provider(mode_value text)
returns text
language sql
immutable
strict
set search_path = ''
as $$
  select case mode_value
    when 'subtitles' then 'internal_captions'
    when 'dub_audio' then 'elevenlabs_dubbing'
    when 'lip_sync' then 'heygen_lipsync_speed'
    else null
  end
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
  return case provider_value
    when 'internal_captions' then ceil(duration_value * 50000.0 / 60.0)::bigint
    when 'elevenlabs_dubbing' then ceil(duration_value * 500000.0 / 60.0)::bigint
    when 'heygen_audio' then duration_value::bigint * 33300
    when 'heygen_lipsync_speed' then duration_value::bigint * 33300
    when 'heygen_lipsync_precision' then duration_value::bigint * 66700
    else raise exception using errcode = '22023', message = 'localization_provider_invalid'
  end;
end;
$$;

create or replace function public.creator_approve_video_localization_source(
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
  media_id uuid;
  product_id_value uuid;
  relationship_value text;
  language_value text;
  duration_value integer;
  speech_value boolean;
  text_value boolean;
  reason_value text;
  idempotency_key text;
  media_row record;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'media_id', 'product_id', 'source_relationship',
    'source_language', 'duration_seconds', 'speech_present',
    'on_screen_text_present', 'rights_confirmed', 'source_qa_approved',
    'reason', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'localization_source_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer']
  );
  media_id := content_factory_private.require_uuid(p_payload, 'media_id');
  product_id_value := content_factory_private.require_uuid(p_payload, 'product_id');
  relationship_value := content_factory_private.require_text(
    p_payload, 'source_relationship', 5, 20
  );
  language_value := content_factory_private.require_language_tag(
    p_payload ->> 'source_language'
  );
  reason_value := content_factory_private.require_text(p_payload, 'reason', 10, 1000);
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  if relationship_value not in ('owned', 'licensed')
     or p_payload -> 'rights_confirmed' is distinct from 'true'::jsonb
     or p_payload -> 'source_qa_approved' is distinct from 'true'::jsonb then
    raise exception using errcode = '42501', message = 'localization_source_rights_or_qa_required';
  end if;
  if coalesce(p_payload ->> 'duration_seconds', '') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'duration_invalid';
  end if;
  duration_value := (p_payload ->> 'duration_seconds')::integer;
  if duration_value not between 1 and 3600 then
    raise exception using errcode = '22023', message = 'duration_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'speech_present') <> 'boolean'
     or jsonb_typeof(p_payload -> 'on_screen_text_present') <> 'boolean' then
    raise exception using errcode = '22023', message = 'localization_source_flags_invalid';
  end if;
  speech_value := (p_payload ->> 'speech_present')::boolean;
  text_value := (p_payload ->> 'on_screen_text_present')::boolean;

  select media.id, media.product_id, media.sha256, media.mime_type, media.status
    into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id
  for update;
  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.product_id is distinct from product_id_value
     or media_row.mime_type not like 'video/%' then
    raise exception using errcode = '55000', message = 'localization_source_media_invalid';
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_approve_video_localization_source',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  insert into content_factory.video_source_approvals (
    organization_id, media_object_id, product_id,
    source_relationship, source_language, duration_seconds,
    rights_confirmed, source_qa_approved,
    speech_present, on_screen_text_present,
    asset_sha256, status, reason, approved_by,
    approved_at, revoked_by, revoked_at
  ) values (
    organization_id, media_id, product_id_value,
    relationship_value, language_value, duration_value,
    true, true, speech_value, text_value,
    media_row.sha256, 'active', reason_value, user_id,
    now(), null, null
  )
  on conflict (organization_id, media_object_id)
  do update set
    product_id = excluded.product_id,
    source_relationship = excluded.source_relationship,
    source_language = excluded.source_language,
    duration_seconds = excluded.duration_seconds,
    rights_confirmed = true,
    source_qa_approved = true,
    speech_present = excluded.speech_present,
    on_screen_text_present = excluded.on_screen_text_present,
    asset_sha256 = excluded.asset_sha256,
    status = 'active',
    reason = excluded.reason,
    approved_by = excluded.approved_by,
    approved_at = now(),
    revoked_by = null,
    revoked_at = null,
    version = content_factory.video_source_approvals.version + 1;

  result := jsonb_build_object(
    'ok', true,
    'media_id', media_id,
    'product_id', product_id_value,
    'status', 'active',
    'source_relationship', relationship_value,
    'source_language', language_value,
    'duration_seconds', duration_value,
    'speech_present', speech_value,
    'on_screen_text_present', text_value,
    'asset_sha256', media_row.sha256
  );

  perform content_factory_private.emit_event(
    organization_id, user_id,
    'video_localization_source_approved',
    'media_object', media_id::text,
    jsonb_build_object(
      'product_id', product_id_value,
      'source_relationship', relationship_value,
      'duration_seconds', duration_value
    ),
    'video_localization_source:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id, user_id,
    'creator_approve_video_localization_source',
    idempotency_key, request_payload, result
  );
end;
$$;

create or replace function public.creator_create_video_localization_batch(
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
  product_id_value uuid;
  source_ids jsonb;
  modes_value jsonb;
  target_language_value text;
  target_count_value integer;
  qa_gate_value integer;
  idempotency_key text;
  source_count_value integer;
  available_count integer;
  rate_card_id constant text := '2026-08-01.public-provider-rate-card.v2';
  rate_card_value constant jsonb := jsonb_build_object(
    'internal_captions_microusd_per_minute', 50000,
    'elevenlabs_dubbing_microusd_per_minute', 500000,
    'heygen_audio_microusd_per_second', 33300,
    'heygen_lipsync_speed_microusd_per_second', 33300,
    'heygen_lipsync_precision_microusd_per_second', 66700,
    'seedance_baseline_microusd_per_second', 290000
  );
  assignments_value jsonb;
  plan_hash_value text;
  total_cost_value bigint;
  baseline_cost_value bigint;
  batch_id_value uuid;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'product_id', 'source_media_ids',
    'target_language', 'modes', 'target_count',
    'qa_gate_after_sequence', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'localization_batch_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id, true, array['owner', 'admin', 'producer', 'operator']
  );
  product_id_value := content_factory_private.require_uuid(p_payload, 'product_id');
  source_ids := p_payload -> 'source_media_ids';
  modes_value := p_payload -> 'modes';
  target_language_value := content_factory_private.require_language_tag(
    p_payload ->> 'target_language'
  );
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  if jsonb_typeof(source_ids) <> 'array'
     or jsonb_array_length(source_ids) not between 1 and 10
     or exists (
       select 1
       from jsonb_array_elements(source_ids) item(value)
       where jsonb_typeof(item.value) <> 'string'
          or item.value #>> '{}' !~* (
            '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
            || '[0-9a-f]{4}-[0-9a-f]{12}$'
          )
     )
     or (
       select count(*) <> count(distinct lower(value))
       from jsonb_array_elements_text(source_ids) item(value)
     ) then
    raise exception using errcode = '22023', message = 'localization_source_ids_invalid';
  end if;

  if jsonb_typeof(modes_value) <> 'array'
     or jsonb_array_length(modes_value) not between 1 and 3
     or exists (
       select 1
       from jsonb_array_elements(modes_value) item(value)
       where jsonb_typeof(item.value) <> 'string'
          or item.value #>> '{}' not in ('subtitles', 'dub_audio', 'lip_sync')
     )
     or (
       select count(*) <> count(distinct value)
       from jsonb_array_elements_text(modes_value) item(value)
     ) then
    raise exception using errcode = '22023', message = 'localization_modes_invalid';
  end if;

  if coalesce(p_payload ->> 'target_count', '') <> '10'
     or coalesce(p_payload ->> 'qa_gate_after_sequence', '') <> '2' then
    raise exception using errcode = '22023', message = 'harly_ten_output_contract_required';
  end if;
  target_count_value := 10;
  qa_gate_value := 2;
  source_count_value := jsonb_array_length(source_ids);

  if not exists (
    select 1 from content_factory.products product
    where product.organization_id = organization_id
      and product.id = product_id_value
      and product.status = 'active'
  ) then
    raise exception using errcode = '55000', message = 'localization_product_invalid';
  end if;

  if (
    select count(*)
    from jsonb_array_elements_text(source_ids) requested(media_id)
    join content_factory.video_source_approvals approval
      on approval.organization_id = organization_id
     and approval.media_object_id = requested.media_id::uuid
     and approval.product_id = product_id_value
     and approval.status = 'active'
     and approval.rights_confirmed
     and approval.source_qa_approved
    join content_factory.media_objects media
      on media.organization_id = approval.organization_id
     and media.id = approval.media_object_id
     and media.product_id = approval.product_id
     and media.status = 'ready'
     and media.mime_type like 'video/%'
     and media.sha256 = approval.asset_sha256
    where approval.source_language <> target_language_value
  ) <> source_count_value then
    raise exception using errcode = '42501', message = 'approved_localization_sources_required';
  end if;

  select count(*)::integer
    into available_count
  from jsonb_array_elements_text(source_ids) with ordinality requested(media_id, source_order)
  join content_factory.video_source_approvals approval
    on approval.organization_id = organization_id
   and approval.media_object_id = requested.media_id::uuid
   and approval.status = 'active'
  cross join jsonb_array_elements_text(modes_value) with ordinality mode_item(mode, mode_order)
  where mode_item.mode = 'subtitles'
     or approval.speech_present;

  if available_count < target_count_value then
    raise exception using
      errcode = '55000',
      message = 'not_enough_unique_localization_combinations',
      detail = available_count::text || '/10';
  end if;

  with combinations as (
    select
      approval.media_object_id,
      approval.product_id,
      approval.source_language,
      approval.duration_seconds,
      approval.asset_sha256,
      approval.on_screen_text_present,
      requested.source_order,
      mode_item.mode,
      mode_item.mode_order,
      content_factory_private.video_localization_provider(mode_item.mode) as provider
    from jsonb_array_elements_text(source_ids)
      with ordinality requested(media_id, source_order)
    join content_factory.video_source_approvals approval
      on approval.organization_id = organization_id
     and approval.media_object_id = requested.media_id::uuid
     and approval.product_id = product_id_value
     and approval.status = 'active'
    cross join jsonb_array_elements_text(modes_value)
      with ordinality mode_item(mode, mode_order)
    where mode_item.mode = 'subtitles' or approval.speech_present
  ),
  selected as (
    select
      combination.*,
      row_number() over (
        order by combination.source_order, combination.mode_order
      )::integer as sequence
    from combinations combination
    order by combination.source_order, combination.mode_order
    limit target_count_value
  ),
  normalized as (
    select jsonb_build_object(
      'sequence', selected.sequence,
      'wave', case when selected.sequence <= qa_gate_value then 1 else 2 end,
      'source_media_id', selected.media_object_id,
      'product_id', selected.product_id,
      'source_language', selected.source_language,
      'target_language', target_language_value,
      'mode', selected.mode,
      'provider', selected.provider,
      'duration_seconds', selected.duration_seconds,
      'source_asset_sha256', selected.asset_sha256,
      'requires_manual_text_edit', selected.on_screen_text_present,
      'estimated_cost_microusd',
        content_factory_private.video_localization_cost_microusd(
          selected.provider, selected.duration_seconds
        ),
      'assignment_hash', content_factory_private.json_hash(jsonb_build_object(
        'source_asset_sha256', selected.asset_sha256,
        'target_language', target_language_value,
        'mode', selected.mode,
        'provider', selected.provider,
        'rate_card_snapshot_id', rate_card_id
      ))
    ) as item
    from selected
  )
  select
    jsonb_agg(item order by (item ->> 'sequence')::integer),
    sum((item ->> 'estimated_cost_microusd')::bigint),
    sum((item ->> 'duration_seconds')::bigint * 290000)
  into assignments_value, total_cost_value, baseline_cost_value
  from normalized;

  plan_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'video_localization_plan.v1',
    'organization_id', organization_id,
    'product_id', product_id_value,
    'target_language', target_language_value,
    'target_count', target_count_value,
    'qa_gate_after_sequence', qa_gate_value,
    'rate_card_snapshot_id', rate_card_id,
    'assignments', assignments_value
  ));

  request_payload := jsonb_build_object(
    'product_id', product_id_value,
    'source_media_ids', source_ids,
    'target_language', target_language_value,
    'modes', modes_value,
    'target_count', target_count_value,
    'qa_gate_after_sequence', qa_gate_value,
    'plan_hash', plan_hash_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_create_video_localization_batch',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('video_localization_batch:' || product_id_value::text)
  );

  insert into content_factory.video_localization_batches (
    organization_id, product_id, created_by,
    target_language, target_count, source_count, modes,
    qa_gate_after_sequence, status,
    rate_card_snapshot_id, rate_card_snapshot,
    plan_hash, total_estimated_cost_microusd,
    full_generation_baseline_microusd,
    idempotency_key
  ) values (
    organization_id, product_id_value, user_id,
    target_language_value, target_count_value, source_count_value, modes_value,
    qa_gate_value, 'wave1_ready',
    rate_card_id, rate_card_value,
    plan_hash_value, total_cost_value,
    baseline_cost_value,
    idempotency_key
  ) returning id into batch_id_value;

  insert into content_factory.video_localization_assignments (
    organization_id, batch_id, product_id,
    source_media_id, sequence, wave, mode, provider,
    source_language, target_language, duration_seconds,
    source_asset_sha256, assignment_hash,
    estimated_cost_microusd, requires_manual_text_edit,
    status
  )
  select
    organization_id,
    batch_id_value,
    product_id_value,
    (item ->> 'source_media_id')::uuid,
    (item ->> 'sequence')::integer,
    (item ->> 'wave')::integer,
    item ->> 'mode',
    item ->> 'provider',
    item ->> 'source_language',
    item ->> 'target_language',
    (item ->> 'duration_seconds')::integer,
    item ->> 'source_asset_sha256',
    item ->> 'assignment_hash',
    (item ->> 'estimated_cost_microusd')::bigint,
    (item ->> 'requires_manual_text_edit')::boolean,
    case when (item ->> 'wave')::integer = 1 then 'ready' else 'planned' end
  from jsonb_array_elements(assignments_value) assignment(item);

  result := jsonb_build_object(
    'ok', true,
    'batch_id', batch_id_value,
    'status', 'wave1_ready',
    'plan_hash', plan_hash_value,
    'target_count', target_count_value,
    'source_count', source_count_value,
    'target_language', target_language_value,
    'modes', modes_value,
    'qa_gate_after_sequence', qa_gate_value,
    'rate_card_snapshot_id', rate_card_id,
    'total_estimated_cost_microusd', total_cost_value,
    'full_generation_baseline_microusd', baseline_cost_value,
    'assignments', assignments_value
  );

  perform content_factory_private.emit_event(
    organization_id, user_id,
    'video_localization_batch_created',
    'video_localization_batch', batch_id_value::text,
    jsonb_build_object(
      'product_id', product_id_value,
      'target_count', target_count_value,
      'source_count', source_count_value,
      'plan_hash', plan_hash_value,
      'estimated_cost_microusd', total_cost_value
    ),
    'video_localization_batch:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id, user_id,
    'creator_create_video_localization_batch',
    idempotency_key, request_payload, result
  );
end;
$$;

create or replace function public.creator_video_localization_batch(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
stable
set search_path = ''
as $$
#variable_conflict use_variable
declare
  organization_id uuid;
  batch_id_value uuid;
  batch_row content_factory.video_localization_batches%rowtype;
  assignments_value jsonb;
  decision_value jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array['organization_id', 'batch_id']::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'localization_batch_read_payload_invalid';
  end if;
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer', 'operator']
  );
  batch_id_value := content_factory_private.require_uuid(p_payload, 'batch_id');

  select batch.* into batch_row
  from content_factory.video_localization_batches batch
  where batch.organization_id = organization_id
    and batch.id = batch_id_value;
  if batch_row.id is null then
    raise exception using errcode = 'P0002', message = 'localization_batch_not_found';
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'id', assignment.id,
    'sequence', assignment.sequence,
    'wave', assignment.wave,
    'source_media_id', assignment.source_media_id,
    'output_media_id', assignment.output_media_id,
    'mode', assignment.mode,
    'provider', assignment.provider,
    'source_language', assignment.source_language,
    'target_language', assignment.target_language,
    'duration_seconds', assignment.duration_seconds,
    'source_asset_sha256', assignment.source_asset_sha256,
    'assignment_hash', assignment.assignment_hash,
    'estimated_cost_microusd', assignment.estimated_cost_microusd,
    'actual_cost_microusd', assignment.actual_cost_microusd,
    'requires_manual_text_edit', assignment.requires_manual_text_edit,
    'status', assignment.status,
    'failure_code', assignment.failure_code
  ) order by assignment.sequence), '[]'::jsonb)
  into assignments_value
  from content_factory.video_localization_assignments assignment
  where assignment.organization_id = organization_id
    and assignment.batch_id = batch_id_value;

  select jsonb_build_object(
    'wave', decision.wave,
    'decision', decision.decision,
    'checklist', decision.checklist,
    'reason', decision.reason,
    'decided_by', decision.decided_by,
    'decided_at', decision.decided_at
  ) into decision_value
  from content_factory.video_localization_qa_decisions decision
  where decision.organization_id = organization_id
    and decision.batch_id = batch_id_value
    and decision.wave = 1;

  return jsonb_build_object(
    'ok', true,
    'batch', jsonb_build_object(
      'id', batch_row.id,
      'product_id', batch_row.product_id,
      'created_by', batch_row.created_by,
      'target_language', batch_row.target_language,
      'target_count', batch_row.target_count,
      'source_count', batch_row.source_count,
      'modes', batch_row.modes,
      'qa_gate_after_sequence', batch_row.qa_gate_after_sequence,
      'status', batch_row.status,
      'rate_card_snapshot_id', batch_row.rate_card_snapshot_id,
      'rate_card_snapshot', batch_row.rate_card_snapshot,
      'plan_hash', batch_row.plan_hash,
      'total_estimated_cost_microusd', batch_row.total_estimated_cost_microusd,
      'full_generation_baseline_microusd', batch_row.full_generation_baseline_microusd,
      'version', batch_row.version,
      'created_at', batch_row.created_at,
      'updated_at', batch_row.updated_at
    ),
    'assignments', assignments_value,
    'wave1_decision', decision_value
  );
end;
$$;

create or replace function public.creator_decide_video_localization_wave(
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
  batch_id_value uuid;
  decision_value text;
  checklist_value jsonb;
  reason_value text;
  idempotency_key text;
  request_payload jsonb;
  replay jsonb;
  batch_row content_factory.video_localization_batches%rowtype;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'batch_id', 'decision',
    'checklist', 'reason', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'localization_qa_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  batch_id_value := content_factory_private.require_uuid(p_payload, 'batch_id');
  decision_value := content_factory_private.require_text(p_payload, 'decision', 8, 8);
  checklist_value := p_payload -> 'checklist';
  reason_value := content_factory_private.require_text(p_payload, 'reason', 5, 1000);
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );

  if decision_value not in ('approved', 'rejected')
     or jsonb_typeof(checklist_value) <> 'object'
     or checklist_value - array[
       'product_fidelity', 'language_quality',
       'no_common_defect', 'rights_ok'
     ]::text[] <> '{}'::jsonb
     or exists (
       select 1
       from jsonb_each(checklist_value) item(key, value)
       where jsonb_typeof(item.value) <> 'boolean'
     ) then
    raise exception using errcode = '22023', message = 'localization_qa_payload_invalid';
  end if;
  if decision_value = 'approved' and exists (
    select 1 from jsonb_each(checklist_value) item(key, value)
    where item.value <> 'true'::jsonb
  ) then
    raise exception using errcode = '42501', message = 'localization_qa_checklist_incomplete';
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_decide_video_localization_wave',
    idempotency_key,
    request_payload
  );
  if replay is not null then return replay; end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('video_localization_qa:' || batch_id_value::text)
  );

  select batch.* into batch_row
  from content_factory.video_localization_batches batch
  where batch.organization_id = organization_id
    and batch.id = batch_id_value
  for update;
  if batch_row.id is null then
    raise exception using errcode = 'P0002', message = 'localization_batch_not_found';
  end if;
  if batch_row.status <> 'qa_required' then
    raise exception using errcode = '55000', message = 'localization_batch_not_waiting_for_qa';
  end if;

  insert into content_factory.video_localization_qa_decisions (
    organization_id, batch_id, wave, decision,
    checklist, reason, decided_by, idempotency_key
  ) values (
    organization_id, batch_id_value, 1, decision_value,
    checklist_value, reason_value, user_id, idempotency_key
  );

  if decision_value = 'approved' then
    update content_factory.video_localization_assignments assignment
    set status = 'ready'
    where assignment.organization_id = organization_id
      and assignment.batch_id = batch_id_value
      and assignment.wave = 2
      and assignment.status = 'planned';

    update content_factory.video_localization_batches batch
    set status = 'wave2_ready',
        version = batch.version + 1
    where batch.organization_id = organization_id
      and batch.id = batch_id_value;
  else
    update content_factory.video_localization_assignments assignment
    set status = 'blocked',
        failure_code = 'wave1_qa_rejected'
    where assignment.organization_id = organization_id
      and assignment.batch_id = batch_id_value
      and assignment.wave = 2
      and assignment.status = 'planned';

    update content_factory.video_localization_batches batch
    set status = 'paused',
        version = batch.version + 1
    where batch.organization_id = organization_id
      and batch.id = batch_id_value;
  end if;

  result := jsonb_build_object(
    'ok', true,
    'batch_id', batch_id_value,
    'decision', decision_value,
    'status', case when decision_value = 'approved' then 'wave2_ready' else 'paused' end
  );

  perform content_factory_private.emit_event(
    organization_id, user_id,
    case
      when decision_value = 'approved' then 'video_localization_wave_approved'
      else 'video_localization_wave_rejected'
    end,
    'video_localization_batch', batch_id_value::text,
    jsonb_build_object('wave', 1, 'decision', decision_value),
    'video_localization_qa:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id, user_id,
    'creator_decide_video_localization_wave',
    idempotency_key, request_payload, result
  );
end;
$$;

create or replace function public.system_update_video_localization_assignment(
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
  assignment_id_value uuid;
  idempotency_key text;
  request_hash_value text;
  status_value text;
  provider_task_hash_value text;
  output_media_id_value uuid;
  actual_cost_value bigint;
  failure_code_value text;
  assignment_row content_factory.video_localization_assignments%rowtype;
  operation_row content_factory_private.video_localization_provider_operations%rowtype;
  batch_status_value text;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'assignment_id', 'idempotency_key',
    'request_hash', 'status', 'provider_task_ref_hash',
    'output_media_id', 'actual_cost_microusd', 'failure_code'
  ]::text[] <> '{}'::jsonb then
    raise exception using errcode = '22023', message = 'localization_operation_payload_invalid';
  end if;

  organization_id := content_factory_private.require_uuid(p_payload, 'organization_id');
  assignment_id_value := content_factory_private.require_uuid(p_payload, 'assignment_id');
  idempotency_key := content_factory_private.require_text(
    p_payload, 'idempotency_key', 8, 180
  );
  request_hash_value := content_factory_private.require_text(
    p_payload, 'request_hash', 64, 64
  );
  status_value := content_factory_private.require_text(p_payload, 'status', 6, 20);
  provider_task_hash_value := nullif(btrim(coalesce(p_payload ->> 'provider_task_ref_hash', '')), '');
  failure_code_value := nullif(btrim(coalesce(p_payload ->> 'failure_code', '')), '');

  if request_hash_value !~ '^[0-9a-f]{64}$'
     or status_value not in (
       'reserved', 'submitted', 'processing',
       'succeeded', 'failed', 'unknown', 'released'
     )
     or (provider_task_hash_value is not null and provider_task_hash_value !~ '^[0-9a-f]{64}$')
     or (failure_code_value is not null and length(failure_code_value) not between 3 and 120) then
    raise exception using errcode = '22023', message = 'localization_operation_payload_invalid';
  end if;

  if p_payload ? 'actual_cost_microusd' then
    if coalesce(p_payload ->> 'actual_cost_microusd', '') !~ '^[0-9]+$' then
      raise exception using errcode = '22023', message = 'localization_actual_cost_invalid';
    end if;
    actual_cost_value := (p_payload ->> 'actual_cost_microusd')::bigint;
  end if;
  if p_payload ? 'output_media_id' then
    output_media_id_value := content_factory_private.require_uuid(p_payload, 'output_media_id');
  end if;
  if status_value = 'succeeded' and output_media_id_value is null then
    raise exception using errcode = '22023', message = 'localization_output_media_required';
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('video_localization_assignment:' || assignment_id_value::text)
  );

  select assignment.* into assignment_row
  from content_factory.video_localization_assignments assignment
  where assignment.organization_id = organization_id
    and assignment.id = assignment_id_value
  for update;
  if assignment_row.id is null then
    raise exception using errcode = 'P0002', message = 'localization_assignment_not_found';
  end if;

  select operation.* into operation_row
  from content_factory_private.video_localization_provider_operations operation
  where operation.organization_id = organization_id
    and operation.assignment_id = assignment_id_value
  for update;

  if operation_row.assignment_id is not null
     and operation_row.idempotency_key <> idempotency_key then
    raise exception using errcode = '55000', message = 'localization_operation_already_exists';
  end if;

  if operation_row.assignment_id is null then
    if status_value <> 'reserved' or assignment_row.status <> 'ready' then
      raise exception using errcode = '55000', message = 'localization_operation_reservation_required';
    end if;
    insert into content_factory_private.video_localization_provider_operations (
      organization_id, assignment_id, provider,
      idempotency_key, request_hash, status,
      reserved_cost_microusd
    ) values (
      organization_id, assignment_id_value, assignment_row.provider,
      idempotency_key, request_hash_value, 'reserved',
      assignment_row.estimated_cost_microusd
    );
    update content_factory.video_localization_assignments assignment
    set status = 'reserved'
    where assignment.organization_id = organization_id
      and assignment.id = assignment_id_value;
  else
    if operation_row.request_hash <> request_hash_value then
      raise exception using errcode = '55000', message = 'localization_operation_request_mismatch';
    end if;
    if status_value = 'reserved' then
      return jsonb_build_object(
        'ok', true,
        'assignment_id', assignment_id_value,
        'status', operation_row.status,
        'replay', true
      );
    end if;

    update content_factory_private.video_localization_provider_operations operation
    set status = case status_value
          when 'succeeded' then 'settled'
          when 'unknown' then 'frozen'
          when 'released' then 'released'
          else status_value
        end,
        provider_task_ref_hash = coalesce(
          provider_task_hash_value, operation.provider_task_ref_hash
        ),
        actual_cost_microusd = coalesce(
          actual_cost_value, operation.actual_cost_microusd
        ),
        failure_code = failure_code_value
    where operation.organization_id = organization_id
      and operation.assignment_id = assignment_id_value;

    if status_value = 'succeeded' then
      if not exists (
        select 1 from content_factory.media_objects media
        where media.organization_id = organization_id
          and media.id = output_media_id_value
          and media.product_id = assignment_row.product_id
          and media.status = 'ready'
          and media.mime_type like 'video/%'
      ) then
        raise exception using errcode = '55000', message = 'localization_output_media_invalid';
      end if;
      update content_factory.video_localization_assignments assignment
      set status = 'succeeded',
          output_media_id = output_media_id_value,
          actual_cost_microusd = coalesce(actual_cost_value, assignment.estimated_cost_microusd),
          failure_code = null
      where assignment.organization_id = organization_id
        and assignment.id = assignment_id_value;
    elsif status_value = 'unknown' then
      update content_factory.video_localization_assignments assignment
      set status = 'unknown',
          actual_cost_microusd = actual_cost_value,
          failure_code = coalesce(failure_code_value, 'provider_outcome_unknown')
      where assignment.organization_id = organization_id
        and assignment.id = assignment_id_value;
    elsif status_value = 'released' then
      update content_factory.video_localization_assignments assignment
      set status = 'ready',
          failure_code = null
      where assignment.organization_id = organization_id
        and assignment.id = assignment_id_value;
    else
      update content_factory.video_localization_assignments assignment
      set status = status_value,
          actual_cost_microusd = actual_cost_value,
          failure_code = failure_code_value
      where assignment.organization_id = organization_id
        and assignment.id = assignment_id_value;
    end if;
  end if;

  if status_value in ('failed', 'unknown') then
    update content_factory.video_localization_assignments assignment
    set status = 'blocked',
        failure_code = coalesce(
          assignment.failure_code,
          'batch_paused_after_provider_failure'
        )
    where assignment.organization_id = organization_id
      and assignment.batch_id = assignment_row.batch_id
      and assignment.id <> assignment_id_value
      and assignment.status in ('planned', 'ready');

    update content_factory.video_localization_batches batch
    set status = 'paused',
        version = batch.version + 1
    where batch.organization_id = organization_id
      and batch.id = assignment_row.batch_id;
  elsif status_value = 'succeeded' then
    if assignment_row.wave = 1 and not exists (
      select 1
      from content_factory.video_localization_assignments assignment
      where assignment.organization_id = organization_id
        and assignment.batch_id = assignment_row.batch_id
        and assignment.wave = 1
        and assignment.status <> 'succeeded'
    ) then
      update content_factory.video_localization_batches batch
      set status = 'qa_required',
          version = batch.version + 1
      where batch.organization_id = organization_id
        and batch.id = assignment_row.batch_id;
    elsif assignment_row.wave = 2 and not exists (
      select 1
      from content_factory.video_localization_assignments assignment
      where assignment.organization_id = organization_id
        and assignment.batch_id = assignment_row.batch_id
        and assignment.status <> 'succeeded'
    ) then
      update content_factory.video_localization_batches batch
      set status = 'completed',
          version = batch.version + 1
      where batch.organization_id = organization_id
        and batch.id = assignment_row.batch_id;
    end if;
  elsif status_value in ('reserved', 'submitted', 'processing') then
    update content_factory.video_localization_batches batch
    set status = case assignment_row.wave
          when 1 then 'wave1_running'
          else 'wave2_running'
        end,
        version = batch.version + 1
    where batch.organization_id = organization_id
      and batch.id = assignment_row.batch_id
      and batch.status not in ('paused', 'failed', 'cancelled', 'completed');
  end if;

  select batch.status into batch_status_value
  from content_factory.video_localization_batches batch
  where batch.organization_id = organization_id
    and batch.id = assignment_row.batch_id;

  result := jsonb_build_object(
    'ok', true,
    'assignment_id', assignment_id_value,
    'batch_id', assignment_row.batch_id,
    'assignment_status', case status_value
      when 'released' then 'ready'
      else status_value
    end,
    'batch_status', batch_status_value,
    'provider_outcome_replay_forbidden', status_value = 'unknown'
  );

  return result;
end;
$$;

revoke all on function public.creator_approve_video_localization_source(jsonb)
  from public, anon;
revoke all on function public.creator_create_video_localization_batch(jsonb)
  from public, anon;
revoke all on function public.creator_video_localization_batch(jsonb)
  from public, anon;
revoke all on function public.creator_decide_video_localization_wave(jsonb)
  from public, anon;
revoke all on function public.system_update_video_localization_assignment(jsonb)
  from public, anon, authenticated;

grant execute on function public.creator_approve_video_localization_source(jsonb)
  to authenticated;
grant execute on function public.creator_create_video_localization_batch(jsonb)
  to authenticated;
grant execute on function public.creator_video_localization_batch(jsonb)
  to authenticated;
grant execute on function public.creator_decide_video_localization_wave(jsonb)
  to authenticated;
grant execute on function public.system_update_video_localization_assignment(jsonb)
  to service_role;

commit;