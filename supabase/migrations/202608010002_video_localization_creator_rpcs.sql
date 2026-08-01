begin;

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
    and value ?& array[
      'product_fidelity', 'language_quality',
      'no_common_defect', 'rights_ok'
    ]::text[]
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
  on_screen_text_value boolean;
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
    raise exception using
      errcode = '22023',
      message = 'localization_source_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer']
  );
  media_id := content_factory_private.require_uuid(p_payload, 'media_id');
  product_id_value := content_factory_private.require_uuid(
    p_payload,
    'product_id'
  );
  relationship_value := content_factory_private.require_text(
    p_payload,
    'source_relationship',
    5,
    20
  );
  language_value := content_factory_private.require_language_tag(
    p_payload ->> 'source_language'
  );
  reason_value := content_factory_private.require_text(
    p_payload,
    'reason',
    10,
    1000
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  if relationship_value not in ('owned', 'licensed')
     or p_payload -> 'rights_confirmed' is distinct from 'true'::jsonb
     or p_payload -> 'source_qa_approved' is distinct from 'true'::jsonb then
    raise exception using
      errcode = '42501',
      message = 'localization_source_rights_or_qa_required';
  end if;
  if coalesce(p_payload ->> 'duration_seconds', '') !~ '^[0-9]+$' then
    raise exception using errcode = '22023', message = 'duration_invalid';
  end if;
  begin
    duration_value := (p_payload ->> 'duration_seconds')::integer;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023', message = 'duration_invalid';
  end;
  if duration_value not between 1 and 3600 then
    raise exception using errcode = '22023', message = 'duration_invalid';
  end if;
  if jsonb_typeof(p_payload -> 'speech_present') is distinct from 'boolean'
     or jsonb_typeof(p_payload -> 'on_screen_text_present') is distinct from 'boolean' then
    raise exception using
      errcode = '22023',
      message = 'localization_source_flags_invalid';
  end if;
  speech_value := (p_payload ->> 'speech_present')::boolean;
  on_screen_text_value := (p_payload ->> 'on_screen_text_present')::boolean;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_approve_video_localization_source',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('video_localization_source:' || media_id::text)
  );

  select
    media.id,
    media.product_id,
    media.sha256,
    media.mime_type,
    media.status
  into media_row
  from content_factory.media_objects media
  where media.organization_id = organization_id
    and media.id = media_id
  for update;

  if media_row.id is null
     or media_row.status <> 'ready'
     or media_row.product_id is distinct from product_id_value
     or media_row.mime_type not like 'video/%' then
    raise exception using
      errcode = '55000',
      message = 'localization_source_media_invalid';
  end if;
  if not exists (
    select 1
    from content_factory.products product
    where product.organization_id = organization_id
      and product.id = product_id_value
      and product.status = 'active'
  ) then
    raise exception using
      errcode = '55000',
      message = 'localization_product_invalid';
  end if;

  insert into content_factory.video_source_approvals (
    organization_id,
    media_object_id,
    product_id,
    source_relationship,
    source_language,
    duration_seconds,
    rights_confirmed,
    source_qa_approved,
    speech_present,
    on_screen_text_present,
    asset_sha256,
    status,
    reason,
    approved_by,
    approved_at,
    revoked_by,
    revoked_at
  ) values (
    organization_id,
    media_id,
    product_id_value,
    relationship_value,
    language_value,
    duration_value,
    true,
    true,
    speech_value,
    on_screen_text_value,
    media_row.sha256,
    'active',
    reason_value,
    user_id,
    now(),
    null,
    null
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
    'on_screen_text_present', on_screen_text_value,
    'asset_sha256', media_row.sha256
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'video_localization_source_approved',
    'media_object',
    media_id::text,
    jsonb_build_object(
      'product_id', product_id_value,
      'source_relationship', relationship_value,
      'duration_seconds', duration_value
    ),
    'video_localization_source:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_approve_video_localization_source',
    idempotency_key,
    request_payload,
    result
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
  submitted_modes jsonb;
  normalized_modes jsonb := '["subtitles", "dub_audio"]'::jsonb;
  target_language_value text;
  idempotency_key text;
  approved_count integer;
  distinct_sha_count integer;
  speech_count integer;
  rate_card_id constant text := '2026-08-01.public-provider-rate-card.v2';
  rate_card_value jsonb;
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
    raise exception using
      errcode = '22023',
      message = 'localization_batch_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  product_id_value := content_factory_private.require_uuid(
    p_payload,
    'product_id'
  );
  source_ids := p_payload -> 'source_media_ids';
  submitted_modes := p_payload -> 'modes';
  target_language_value := content_factory_private.require_language_tag(
    p_payload ->> 'target_language'
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  if jsonb_typeof(source_ids) is distinct from 'array'
     or jsonb_array_length(source_ids) <> 5 then
    raise exception using
      errcode = '22023',
      message = 'harly_five_sources_required';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(source_ids) item(value)
    where jsonb_typeof(item.value) <> 'string'
       or item.value #>> '{}' !~* (
         '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-'
         || '[0-9a-f]{4}-[0-9a-f]{12}$'
       )
  ) or (
    select count(*) <> count(distinct lower(value))
    from jsonb_array_elements_text(source_ids) item(value)
  ) then
    raise exception using
      errcode = '22023',
      message = 'localization_source_ids_invalid';
  end if;

  if not content_factory_private.valid_video_localization_modes(submitted_modes)
     or jsonb_array_length(submitted_modes) <> 2
     or not submitted_modes @> normalized_modes
     or not normalized_modes @> submitted_modes then
    raise exception using
      errcode = '22023',
      message = 'harly_subtitles_and_dub_modes_required';
  end if;
  if coalesce(p_payload ->> 'target_count', '') <> '10'
     or coalesce(p_payload ->> 'qa_gate_after_sequence', '') <> '2' then
    raise exception using
      errcode = '22023',
      message = 'harly_ten_output_contract_required';
  end if;

  if not exists (
    select 1
    from content_factory.products product
    where product.organization_id = organization_id
      and product.id = product_id_value
      and product.status = 'active'
  ) then
    raise exception using
      errcode = '55000',
      message = 'localization_product_invalid';
  end if;

  select
    count(*)::integer,
    count(distinct approval.asset_sha256)::integer,
    count(*) filter (where approval.speech_present)::integer
  into approved_count, distinct_sha_count, speech_count
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
  where approval.source_language <> target_language_value;

  if approved_count <> 5 then
    raise exception using
      errcode = '42501',
      message = 'approved_localization_sources_required';
  end if;
  if distinct_sha_count <> 5 then
    raise exception using
      errcode = '22023',
      message = 'duplicate_localization_source_asset';
  end if;
  if speech_count <> 5 then
    raise exception using
      errcode = '55000',
      message = 'harly_dubbing_requires_speech_in_all_sources';
  end if;

  rate_card_value := jsonb_build_object(
    'internal_captions_microusd_per_minute', 50000,
    'elevenlabs_dubbing_microusd_per_minute', 500000,
    'heygen_audio_microusd_per_second', 33300,
    'heygen_lipsync_speed_microusd_per_second', 33300,
    'heygen_lipsync_precision_microusd_per_second', 66700,
    'seedance_baseline_microusd_per_second', 290000
  );

  with source_page as (
    select
      approval.media_object_id,
      approval.product_id,
      approval.source_language,
      approval.duration_seconds,
      approval.asset_sha256,
      approval.on_screen_text_present,
      requested.source_order
    from jsonb_array_elements_text(source_ids)
      with ordinality requested(media_id, source_order)
    join content_factory.video_source_approvals approval
      on approval.organization_id = organization_id
     and approval.media_object_id = requested.media_id::uuid
     and approval.product_id = product_id_value
     and approval.status = 'active'
  ),
  modes(mode, mode_order) as (
    values ('subtitles'::text, 1), ('dub_audio'::text, 2)
  ),
  selected as (
    select
      source_page.*,
      modes.mode,
      modes.mode_order,
      ((source_page.source_order - 1) * 2 + modes.mode_order)::integer
        as sequence,
      content_factory_private.video_localization_provider(modes.mode)
        as provider
    from source_page
    cross join modes
  ),
  normalized as (
    select jsonb_build_object(
      'sequence', selected.sequence,
      'wave', case when selected.sequence <= 2 then 1 else 2 end,
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
          selected.provider,
          selected.duration_seconds
        ),
      'assignment_hash', content_factory_private.json_hash(jsonb_build_object(
        'schema_version', 'video_localization_assignment.v1',
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

  if jsonb_array_length(assignments_value) <> 10 then
    raise exception using
      errcode = '55000',
      message = 'harly_ten_assignment_plan_invalid';
  end if;

  plan_hash_value := content_factory_private.json_hash(jsonb_build_object(
    'schema_version', 'video_localization_plan.v1',
    'organization_id', organization_id,
    'product_id', product_id_value,
    'target_language', target_language_value,
    'target_count', 10,
    'qa_gate_after_sequence', 2,
    'modes', normalized_modes,
    'rate_card_snapshot_id', rate_card_id,
    'assignments', assignments_value
  ));

  request_payload := jsonb_build_object(
    'product_id', product_id_value,
    'source_media_ids', source_ids,
    'target_language', target_language_value,
    'modes', normalized_modes,
    'target_count', 10,
    'qa_gate_after_sequence', 2,
    'plan_hash', plan_hash_value
  );
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_create_video_localization_batch',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('video_localization_batch:' || product_id_value::text)
  );

  if exists (
    select 1
    from content_factory.video_localization_batches batch
    where batch.organization_id = organization_id
      and batch.product_id = product_id_value
      and batch.status not in ('completed', 'failed', 'cancelled')
  ) then
    raise exception using
      errcode = '55000',
      message = 'video_localization_batch_already_active';
  end if;

  insert into content_factory.video_localization_batches (
    organization_id,
    product_id,
    created_by,
    target_language,
    target_count,
    source_count,
    modes,
    qa_gate_after_sequence,
    status,
    rate_card_snapshot_id,
    rate_card_snapshot,
    plan_hash,
    total_estimated_cost_microusd,
    full_generation_baseline_microusd,
    idempotency_key
  ) values (
    organization_id,
    product_id_value,
    user_id,
    target_language_value,
    10,
    5,
    normalized_modes,
    2,
    'wave1_ready',
    rate_card_id,
    rate_card_value,
    plan_hash_value,
    total_cost_value,
    baseline_cost_value,
    idempotency_key
  ) returning id into batch_id_value;

  insert into content_factory.video_localization_assignments (
    organization_id,
    batch_id,
    product_id,
    source_media_id,
    sequence,
    wave,
    mode,
    provider,
    source_language,
    target_language,
    duration_seconds,
    source_asset_sha256,
    assignment_hash,
    estimated_cost_microusd,
    requires_manual_text_edit,
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
    'target_count', 10,
    'source_count', 5,
    'target_language', target_language_value,
    'modes', normalized_modes,
    'qa_gate_after_sequence', 2,
    'rate_card_snapshot_id', rate_card_id,
    'total_estimated_cost_microusd', total_cost_value,
    'full_generation_baseline_microusd', baseline_cost_value,
    'estimated_savings_ratio', case
      when baseline_cost_value = 0 then 0
      else round(1 - total_cost_value::numeric / baseline_cost_value::numeric, 8)
    end,
    'assignments', assignments_value
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'video_localization_batch_created',
    'video_localization_batch',
    batch_id_value::text,
    jsonb_build_object(
      'product_id', product_id_value,
      'target_count', 10,
      'source_count', 5,
      'plan_hash', plan_hash_value,
      'estimated_cost_microusd', total_cost_value
    ),
    'video_localization_batch:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_create_video_localization_batch',
    idempotency_key,
    request_payload,
    result
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
    raise exception using
      errcode = '22023',
      message = 'localization_batch_read_payload_invalid';
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
    raise exception using
      errcode = 'P0002',
      message = 'localization_batch_not_found';
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
    raise exception using
      errcode = '22023',
      message = 'localization_qa_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'reviewer']
  );
  batch_id_value := content_factory_private.require_uuid(p_payload, 'batch_id');
  decision_value := content_factory_private.require_text(
    p_payload,
    'decision',
    8,
    8
  );
  checklist_value := p_payload -> 'checklist';
  reason_value := content_factory_private.require_text(
    p_payload,
    'reason',
    5,
    1000
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  if decision_value not in ('approved', 'rejected')
     or not content_factory_private.valid_video_localization_checklist(
       checklist_value
     ) then
    raise exception using
      errcode = '22023',
      message = 'localization_qa_payload_invalid';
  end if;
  if decision_value = 'approved' and exists (
    select 1
    from jsonb_each(checklist_value) item(key, value)
    where item.value <> 'true'::jsonb
  ) then
    raise exception using
      errcode = '42501',
      message = 'localization_qa_checklist_incomplete';
  end if;

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_decide_video_localization_wave',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

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
    raise exception using
      errcode = 'P0002',
      message = 'localization_batch_not_found';
  end if;
  if batch_row.status <> 'qa_required' then
    raise exception using
      errcode = '55000',
      message = 'localization_batch_not_waiting_for_qa';
  end if;
  if exists (
    select 1
    from content_factory.video_localization_qa_decisions decision
    where decision.organization_id = organization_id
      and decision.batch_id = batch_id_value
      and decision.wave = 1
  ) then
    raise exception using
      errcode = '55000',
      message = 'localization_qa_already_decided';
  end if;
  if (
    select count(*)
    from content_factory.video_localization_assignments assignment
    where assignment.organization_id = organization_id
      and assignment.batch_id = batch_id_value
      and assignment.wave = 1
      and assignment.status = 'succeeded'
  ) <> 2 then
    raise exception using
      errcode = '55000',
      message = 'localization_wave1_outputs_incomplete';
  end if;

  insert into content_factory.video_localization_qa_decisions (
    organization_id,
    batch_id,
    wave,
    decision,
    checklist,
    reason,
    decided_by,
    idempotency_key
  ) values (
    organization_id,
    batch_id_value,
    1,
    decision_value,
    checklist_value,
    reason_value,
    user_id,
    idempotency_key
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
    'status', case
      when decision_value = 'approved' then 'wave2_ready'
      else 'paused'
    end
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    case
      when decision_value = 'approved'
        then 'video_localization_wave_approved'
      else 'video_localization_wave_rejected'
    end,
    'video_localization_batch',
    batch_id_value::text,
    jsonb_build_object('wave', 1, 'decision', decision_value),
    'video_localization_qa:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_decide_video_localization_wave',
    idempotency_key,
    request_payload,
    result
  );
end;
$$;

create or replace function public.creator_cancel_video_localization_batch(
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
  batch_id_value uuid;
  reason_value text;
  idempotency_key text;
  batch_row content_factory.video_localization_batches%rowtype;
  request_payload jsonb;
  replay jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  if p_payload - array[
    'organization_id', 'batch_id', 'reason', 'idempotency_key'
  ]::text[] <> '{}'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'localization_cancel_payload_invalid';
  end if;

  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  actor_role := content_factory_private.membership_role(
    organization_id,
    true,
    array['owner', 'admin', 'producer', 'operator']
  );
  batch_id_value := content_factory_private.require_uuid(p_payload, 'batch_id');
  reason_value := content_factory_private.require_text(
    p_payload,
    'reason',
    5,
    1000
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );

  request_payload := p_payload - 'organization_id' - 'idempotency_key';
  replay := content_factory_private.begin_command(
    organization_id,
    'creator_cancel_video_localization_batch',
    idempotency_key,
    request_payload
  );
  if replay is not null then
    return replay;
  end if;

  perform pg_advisory_xact_lock(
    hashtext(organization_id::text),
    hashtext('video_localization_batch:' || batch_id_value::text)
  );

  select batch.* into batch_row
  from content_factory.video_localization_batches batch
  where batch.organization_id = organization_id
    and batch.id = batch_id_value
  for update;
  if batch_row.id is null then
    raise exception using
      errcode = 'P0002',
      message = 'localization_batch_not_found';
  end if;
  if actor_role = 'operator' and batch_row.created_by <> user_id then
    raise exception using
      errcode = '42501',
      message = 'localization_cancel_access_denied';
  end if;
  if batch_row.status in ('completed', 'failed', 'cancelled') then
    raise exception using
      errcode = '55000',
      message = 'localization_batch_terminal';
  end if;
  if exists (
    select 1
    from content_factory.video_localization_assignments assignment
    where assignment.organization_id = organization_id
      and assignment.batch_id = batch_id_value
      and assignment.status in (
        'reserved', 'submitted', 'processing', 'unknown'
      )
  ) then
    raise exception using
      errcode = '55000',
      message = 'localization_reconciliation_required';
  end if;

  update content_factory.video_localization_assignments assignment
  set status = 'cancelled',
      failure_code = 'batch_cancelled'
  where assignment.organization_id = organization_id
    and assignment.batch_id = batch_id_value
    and assignment.status in ('planned', 'ready', 'blocked');

  update content_factory.video_localization_batches batch
  set status = 'cancelled',
      version = batch.version + 1
  where batch.organization_id = organization_id
    and batch.id = batch_id_value;

  result := jsonb_build_object(
    'ok', true,
    'batch_id', batch_id_value,
    'status', 'cancelled'
  );

  perform content_factory_private.emit_event(
    organization_id,
    user_id,
    'video_localization_batch_cancelled',
    'video_localization_batch',
    batch_id_value::text,
    jsonb_build_object('reason', reason_value),
    'video_localization_cancel:' || idempotency_key
  );

  return content_factory_private.finish_command(
    organization_id,
    user_id,
    'creator_cancel_video_localization_batch',
    idempotency_key,
    request_payload,
    result
  );
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
revoke all on function public.creator_cancel_video_localization_batch(jsonb)
  from public, anon;

grant execute on function public.creator_approve_video_localization_source(jsonb)
  to authenticated;
grant execute on function public.creator_create_video_localization_batch(jsonb)
  to authenticated;
grant execute on function public.creator_video_localization_batch(jsonb)
  to authenticated;
grant execute on function public.creator_decide_video_localization_wave(jsonb)
  to authenticated;
grant execute on function public.creator_cancel_video_localization_batch(jsonb)
  to authenticated;

commit;
