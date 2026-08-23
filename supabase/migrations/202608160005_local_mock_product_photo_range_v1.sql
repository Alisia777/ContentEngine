begin;

-- Bug 9 (AUDIT_CONTENT_FACTORY_2026-08-16): the local mock authority required
-- exactly 3-5 new-product photos while the strategy catalog, the full
-- constructor UI and the paid bind authority (202608130006) all accept 1-10.
-- A legal binding with 1-2 or 6-10 photos passed bind but failed mock
-- preflight/complete with local_mock_generation_strategy_copy_assets_invalid.
-- This migration re-creates the function from 202608160002 with the photo
-- range relaxed to 1-10; everything else is byte-identical.  202608160002 is
-- already recorded in contentengine_deploy.schema_migrations by sha256 and
-- must never be edited in place.
-- Local Product Swap completion deliberately reuses the canonical generation
-- batch/job/media records.  It is not a paid-start path, a provider adapter or
-- a second spend ledger.  creator-generate is expected to call this service-
-- only RPC only while its local mock gates are enabled.
create or replace function public.system_local_mock_generation_strategy(
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
  operation_value text;
  organization_id_value uuid;
  project_id_value uuid;
  actor_id_value uuid;
  binding_id_value uuid;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  selection_hash_value text;
  idempotency_key_value text;
  execution_hash_value text;
  output_object_name_value text;
  binding_row content_factory.generation_spec_strategy_bindings%rowtype;
  selection_row content_factory.generation_strategy_binding_selections%rowtype;
  source_media_id_value uuid;
  source_sha256_value text;
  source_duration_ms_value bigint;
  original_product_media_id_value uuid;
  new_product_media_ids_value uuid[] := array[]::uuid[];
  input_media_ids_value uuid[] := array[]::uuid[];
  source_count_value integer := 0;
  original_count_value integer := 0;
  new_product_count_value integer := 0;
  unexpected_asset_count_value integer := 0;
  identity_value jsonb;
  inputs_value jsonb;
  output_value jsonb;
  generation_value jsonb;
  contract_value jsonb := jsonb_build_object(
    'mode', 'mock',
    'provider', 'mock',
    'model', 'local_product_swap_v1',
    'allow_real_spend', false,
    'estimated_cost_minor', 0,
    'actual_cost_minor', 0,
    'provider_call_started', false,
    'paid_authority_used', false,
    'spend_ledger_written', false
  );
  output_payload_value jsonb;
  output_bucket_value text;
  output_mime_value text;
  output_size_value bigint;
  output_sha256_value text;
  output_duration_ms_value bigint;
  storage_metadata_value jsonb;
  storage_size_value bigint;
  storage_mime_value text;
  request_payload_value jsonb;
  replay_value jsonb;
  batch_id_value uuid;
  job_id_value uuid;
  output_media_id_value uuid;
  batch_input_value jsonb;
  job_input_value jsonb;
  job_output_value jsonb;
  result_value jsonb;
  job_row content_factory.generation_jobs%rowtype;
  batch_row content_factory.generation_batches%rowtype;
  snapshot_row content_factory.generation_job_strategy_snapshots%rowtype;
  output_media_row content_factory.media_objects%rowtype;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  operation_value := lower(btrim(coalesce(p_payload ->> 'operation', '')));

  if length(p_payload::text) > 32768
     or p_payload ->> 'version' <>
       'local-mock-generation-strategy-request-v1'
     or operation_value not in ('preflight', 'complete', 'status')
     or p_payload ->> 'mode' <> 'mock'
     or p_payload -> 'allow_real_spend' is distinct from 'false'::jsonb
     or p_payload -> 'provider_call_started' is distinct from 'false'::jsonb
  then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_payload_invalid';
  end if;

  if operation_value = 'status' then
    if p_payload - array[
         'version', 'operation', 'organization_id', 'project_id', 'actor_id',
         'generation_job_id', 'mode', 'allow_real_spend',
         'provider_call_started'
       ]::text[] <> '{}'::jsonb
       or not p_payload ?& array[
         'version', 'operation', 'organization_id', 'project_id', 'actor_id',
         'generation_job_id', 'mode', 'allow_real_spend',
         'provider_call_started'
       ]::text[] then
      raise exception using errcode = '22023',
        message = 'local_mock_generation_strategy_payload_invalid';
    end if;
  else
    if p_payload - (
         array[
           'version', 'operation', 'organization_id', 'project_id', 'actor_id',
           'spec_strategy_binding_id', 'spec_id', 'spec_version', 'spec_hash',
           'selection_hash', 'mode', 'allow_real_spend',
           'provider_call_started', 'confirmation', 'idempotency_key'
         ]::text[] || case when operation_value = 'complete'
           then array['output']::text[] else array[]::text[] end
       ) <> '{}'::jsonb
       or not p_payload ?& array[
         'version', 'operation', 'organization_id', 'project_id', 'actor_id',
         'spec_strategy_binding_id', 'spec_id', 'spec_version', 'spec_hash',
         'selection_hash', 'mode', 'allow_real_spend',
         'provider_call_started', 'confirmation', 'idempotency_key'
       ]::text[]
       or p_payload ->> 'confirmation' <> 'LOCAL_MOCK_ONLY'
       or (operation_value = 'preflight' and p_payload ? 'output')
       or (operation_value = 'complete'
         and jsonb_typeof(p_payload -> 'output') <> 'object')
       or jsonb_typeof(p_payload -> 'spec_version') <> 'number'
       or coalesce(p_payload ->> 'spec_version', '') !~ '^[1-9][0-9]{0,5}$'
    then
      raise exception using errcode = '22023',
        message = 'local_mock_generation_strategy_payload_invalid';
    end if;
  end if;

  organization_id_value := content_factory_private.require_uuid(
    p_payload, 'organization_id'
  );
  project_id_value := content_factory_private.require_uuid(
    p_payload, 'project_id'
  );
  actor_id_value := content_factory_private.require_uuid(p_payload, 'actor_id');

  perform 1
  from content_factory.organizations organization
  join content_factory.memberships membership
    on membership.organization_id = organization.id
   and membership.profile_id = actor_id_value
   and membership.status = 'active'
   and membership.role in ('owner', 'admin', 'producer', 'operator')
  join content_factory.profiles profile
    on profile.id = membership.profile_id
   and profile.status = 'active'
  where organization.id = organization_id_value
    and organization.status = 'active';
  if not found
     or not content_factory_private.workspace_project_access_allowed(
       organization_id_value, project_id_value, actor_id_value
     ) then
    raise exception using errcode = '42501',
      message = 'local_mock_generation_strategy_access_required';
  end if;

  if operation_value = 'status' then
    job_id_value := content_factory_private.require_uuid(
      p_payload, 'generation_job_id'
    );
    select job.* into job_row
    from content_factory.generation_jobs job
    where job.organization_id = organization_id_value
      and job.project_id = project_id_value
      and job.id = job_id_value
      and job.requested_by = actor_id_value
      and job.assigned_to = actor_id_value
      and job.mode = 'mock'
      and job.provider = 'mock'
      and not job.allow_real_spend
      and job.estimated_cost_minor = 0
      and job.actual_cost_minor = 0
      and job.status = 'mock_ready'
      and job.input ->> 'version' =
        'local-mock-generation-strategy-job-input-v1'
      and job.input ->> 'model' = 'local_product_swap_v1'
      and job.input ->> 'strategy_id' = 'viral_product_swap'
      and job.input -> 'provider_call_started' = 'false'::jsonb
      and job.output ->> 'version' =
        'local-mock-generation-strategy-job-output-v1'
      and job.output -> 'provider_call_started' = 'false'::jsonb;
    if job_row.id is null then
      raise exception using errcode = 'P0002',
        message = 'local_mock_generation_strategy_job_not_found';
    end if;

    select batch.* into batch_row
    from content_factory.generation_batches batch
    where batch.organization_id = organization_id_value
      and batch.project_id = project_id_value
      and batch.id = job_row.batch_id
      and batch.created_by = actor_id_value
      and batch.mode = 'mock'
      and batch.provider = 'mock'
      and batch.model = 'mock'
      and not batch.allow_real_spend
      and batch.estimated_cost_minor = 0
      and batch.estimated_credits = 0
      and batch.status = 'mock_ready';
    select snapshot.* into snapshot_row
    from content_factory.generation_job_strategy_snapshots snapshot
    where snapshot.organization_id = organization_id_value
      and snapshot.project_id = project_id_value
      and snapshot.generation_job_id = job_row.id
      and snapshot.batch_id = job_row.batch_id
      and snapshot.strategy_id = 'viral_product_swap';
    if batch_row.id is null or snapshot_row.id is null
       or job_row.generation_spec_id is distinct from snapshot_row.spec_id
       or job_row.generation_spec_version is distinct from
            snapshot_row.spec_version
       or job_row.generation_spec_hash is distinct from snapshot_row.spec_hash
    then
      raise exception using errcode = '55000',
        message = 'local_mock_generation_strategy_status_invalid';
    end if;

    select binding.* into binding_row
    from content_factory.generation_spec_strategy_bindings binding
    where binding.organization_id = organization_id_value
      and binding.id = snapshot_row.spec_strategy_binding_id
      and binding.project_id = project_id_value
      and binding.strategy_id = 'viral_product_swap';
    select selection.* into selection_row
    from content_factory.generation_strategy_binding_selections selection
    where selection.organization_id = organization_id_value
      and selection.project_id = project_id_value
      and selection.spec_strategy_binding_id = snapshot_row.spec_strategy_binding_id
      and selection.strategy_id = 'viral_product_swap';
    begin
      output_media_id_value :=
        (job_row.output ->> 'output_media_id')::uuid;
    exception when invalid_text_representation then
      output_media_id_value := null;
    end;
    select media.* into output_media_row
    from content_factory.media_objects media
    where media.organization_id = organization_id_value
      and media.project_id = project_id_value
      and media.id = output_media_id_value
      and media.owner_id = actor_id_value
      and media.status = 'ready'
      and media.mime_type = 'video/mp4'
      and media.metadata ->> 'kind' = 'generated_video'
      and media.metadata ->> 'provider' = 'mock'
      and media.metadata ->> 'model' = 'local_product_swap_v1'
      and media.metadata ->> 'generation_job_id' = job_row.id::text
      and media.metadata -> 'provider_call_started' = 'false'::jsonb;
    if binding_row.id is null or selection_row.id is null
       or selection_row.selection_hash <>
            job_row.input ->> 'selection_hash'
       or output_media_row.id is null
       or output_media_row.object_name <>
            job_row.output ->> 'output_object_name'
       or output_media_row.sha256 <> job_row.output ->> 'output_sha256'
       or output_media_row.size_bytes::text <>
            job_row.output ->> 'output_size_bytes'
    then
      raise exception using errcode = '55000',
        message = 'local_mock_generation_strategy_status_invalid';
    end if;

    identity_value := jsonb_build_object(
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'actor_id', actor_id_value,
      'spec_strategy_binding_id', binding_row.id,
      'binding_hash', binding_row.binding_hash,
      'spec_id', snapshot_row.spec_id,
      'spec_version', snapshot_row.spec_version,
      'spec_hash', snapshot_row.spec_hash,
      'selection_hash', selection_row.selection_hash,
      'strategy_id', 'viral_product_swap'
    );
    inputs_value := jsonb_build_object(
      'source_video_media_id', job_row.input -> 'source_video_media_id',
      'source_video_sha256', job_row.input -> 'source_video_sha256',
      'source_video_duration_ms',
        job_row.input -> 'source_video_duration_ms',
      'original_product_media_id',
        job_row.input -> 'original_product_media_id',
      'new_product_media_ids', job_row.input -> 'new_product_media_ids'
    );
    output_value := jsonb_build_object(
      'bucket_id', output_media_row.bucket_id,
      'object_name', output_media_row.object_name,
      'mime_type', output_media_row.mime_type,
      'media_id', output_media_row.id,
      'size_bytes', output_media_row.size_bytes,
      'sha256', output_media_row.sha256,
      'duration_ms', job_row.output -> 'duration_ms'
    );
    generation_value := jsonb_build_object(
      'batch_id', batch_row.id,
      'generation_job_id', job_row.id,
      'status', job_row.status,
      'provider', job_row.provider,
      'persisted_model', batch_row.model,
      'logical_model', 'local_product_swap_v1'
    );
    return jsonb_build_object(
      'ok', true,
      'version', 'local-mock-generation-strategy-response-v1',
      'operation', 'status',
      'replay', false,
      'identity', identity_value,
      'inputs', inputs_value,
      'output', output_value,
      'generation', generation_value,
      'contract', contract_value
    );
  end if;

  binding_id_value := content_factory_private.require_uuid(
    p_payload, 'spec_strategy_binding_id'
  );
  spec_id_value := content_factory_private.require_uuid(p_payload, 'spec_id');
  spec_version_value := (p_payload ->> 'spec_version')::integer;
  spec_hash_value := lower(btrim(p_payload ->> 'spec_hash'));
  selection_hash_value := lower(btrim(p_payload ->> 'selection_hash'));
  idempotency_key_value := btrim(p_payload ->> 'idempotency_key');
  if spec_hash_value !~ '^[0-9a-f]{64}$'
     or selection_hash_value !~ '^[0-9a-f]{64}$'
     or length(idempotency_key_value) not between 12 and 120
     or idempotency_key_value ~ '[[:cntrl:]]' then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_payload_invalid';
  end if;

  select binding.* into binding_row
  from content_factory.generation_spec_strategy_bindings binding
  where binding.organization_id = organization_id_value
    and binding.project_id = project_id_value
    and binding.id = binding_id_value
    and binding.spec_id = spec_id_value
    and binding.spec_version = spec_version_value
    and binding.spec_hash = spec_hash_value
    and binding.selection_hash = selection_hash_value
    and binding.strategy_id = 'viral_product_swap'
    and binding.source_basis = 'exact_source_video'
    and binding.confirmed_by = actor_id_value
    and binding.confirmation
  for share;
  if binding_row.id is null
     or not content_factory_private.generation_strategy_binding_current(
       organization_id_value, binding_id_value
     ) then
    raise exception using errcode = '55000',
      message = 'local_mock_generation_strategy_binding_not_current';
  end if;

  select selection.* into selection_row
  from content_factory.generation_strategy_binding_selections selection
  where selection.organization_id = organization_id_value
    and selection.project_id = project_id_value
    and selection.bound_by = actor_id_value
    and selection.spec_strategy_binding_id = binding_id_value
    and selection.binding_hash = binding_row.binding_hash
    and selection.strategy_id = 'viral_product_swap'
    and selection.recipe = 'product_swap'
    and selection.selection_hash = selection_hash_value
    and content_factory_private.generation_strategy_selection_snapshot_valid_v1(
      selection.selection_snapshot
    )
  for share;
  if selection_row.id is null then
    raise exception using errcode = '55000',
      message = 'local_mock_generation_strategy_selection_not_current';
  end if;

  select
    count(*) filter (where asset.role = 'source_video')::integer,
    count(*) filter (where asset.role = 'original_product')::integer,
    count(*) filter (
      where asset.role in ('product_primary', 'product_reference')
    )::integer,
    count(*) filter (
      where asset.role not in (
        'source_video', 'original_product',
        'product_primary', 'product_reference'
      )
    )::integer
  into source_count_value, original_count_value,
       new_product_count_value, unexpected_asset_count_value
  from content_factory.generation_spec_strategy_assets asset
  where asset.organization_id = organization_id_value
    and asset.binding_id = binding_id_value;
  if source_count_value <> 1
     or original_count_value <> 1
     or new_product_count_value not between 1 and 10
     or unexpected_asset_count_value <> 0 then
    raise exception using errcode = '55000',
      message = 'local_mock_generation_strategy_copy_assets_invalid';
  end if;

  select
    asset.media_object_id,
    asset.media_sha256_snapshot,
    round(duration.duration_seconds * 1000)::bigint
  into source_media_id_value, source_sha256_value,
       source_duration_ms_value
  from content_factory.generation_spec_strategy_assets asset
  join content_factory.generation_strategy_media_durations duration
    on duration.organization_id = asset.organization_id
   and duration.project_id = project_id_value
   and duration.media_object_id = asset.media_object_id
   and duration.attachment_id = binding_row.source_binding_id
   and duration.attachment_hash = binding_row.source_binding_hash
   and duration.media_sha256_snapshot = asset.media_sha256_snapshot
  where asset.organization_id = organization_id_value
    and asset.binding_id = binding_id_value
    and asset.role = 'source_video'
    and duration.duration_seconds between 1.8 and 15;
  select asset.media_object_id into original_product_media_id_value
  from content_factory.generation_spec_strategy_assets asset
  where asset.organization_id = organization_id_value
    and asset.binding_id = binding_id_value
    and asset.role = 'original_product';
  select coalesce(
    array_agg(
      asset.media_object_id
      order by case when asset.role = 'product_primary' then 0 else 1 end,
               asset.ordinal
    ),
    array[]::uuid[]
  ) into new_product_media_ids_value
  from content_factory.generation_spec_strategy_assets asset
  where asset.organization_id = organization_id_value
    and asset.binding_id = binding_id_value
    and asset.role in ('product_primary', 'product_reference');
  if source_media_id_value is null
     or source_duration_ms_value not between 1800 and 15000
     or original_product_media_id_value is null
     or cardinality(new_product_media_ids_value) not between 1 and 10 then
    raise exception using errcode = '55000',
      message = 'local_mock_generation_strategy_source_probe_required';
  end if;
  input_media_ids_value :=
    array[source_media_id_value, original_product_media_id_value]
      || new_product_media_ids_value;

  execution_hash_value := content_factory_private.json_hash(
    jsonb_build_object(
      'version', 'local-mock-generation-strategy-identity-v1',
      'organization_id', organization_id_value,
      'project_id', project_id_value,
      'actor_id', actor_id_value,
      'spec_strategy_binding_id', binding_id_value,
      'spec_id', spec_id_value,
      'spec_version', spec_version_value,
      'spec_hash', spec_hash_value,
      'selection_hash', selection_hash_value,
      'idempotency_key', idempotency_key_value
    )
  );
  output_object_name_value := concat(
    organization_id_value::text, '/', actor_id_value::text,
    '/local-mock-output/viral_product_swap/',
    substr(execution_hash_value, 1, 2), '/', execution_hash_value, '.mp4'
  );
  identity_value := jsonb_build_object(
    'organization_id', organization_id_value,
    'project_id', project_id_value,
    'actor_id', actor_id_value,
    'spec_strategy_binding_id', binding_id_value,
    'binding_hash', binding_row.binding_hash,
    'spec_id', spec_id_value,
    'spec_version', spec_version_value,
    'spec_hash', spec_hash_value,
    'selection_hash', selection_hash_value,
    'strategy_id', 'viral_product_swap'
  );
  inputs_value := jsonb_build_object(
    'source_video_media_id', source_media_id_value,
    'source_video_sha256', source_sha256_value,
    'source_video_duration_ms', source_duration_ms_value,
    'original_product_media_id', original_product_media_id_value,
    'new_product_media_ids', to_jsonb(new_product_media_ids_value)
  );

  if operation_value = 'preflight' then
    output_value := jsonb_build_object(
      'bucket_id', 'contentengine-private',
      'object_name', output_object_name_value,
      'mime_type', 'video/mp4'
    );
    return jsonb_build_object(
      'ok', true,
      'version', 'local-mock-generation-strategy-response-v1',
      'operation', 'preflight',
      'replay', false,
      'identity', identity_value,
      'inputs', inputs_value,
      'output', output_value,
      'generation', 'null'::jsonb,
      'contract', contract_value
    );
  end if;

  output_payload_value := p_payload -> 'output';
  if output_payload_value - array[
       'bucket_id', 'object_name', 'mime_type', 'size_bytes', 'sha256',
       'duration_ms', 'http_status', 'download_complete', 'parser_version',
       'mvhd_count', 'fragmented', 'verification_method'
     ]::text[] <> '{}'::jsonb
     or not output_payload_value ?& array[
       'bucket_id', 'object_name', 'mime_type', 'size_bytes', 'sha256',
       'duration_ms', 'http_status', 'download_complete', 'parser_version',
       'mvhd_count', 'fragmented', 'verification_method'
     ]::text[]
     or jsonb_typeof(output_payload_value -> 'size_bytes') <> 'number'
     or coalesce(output_payload_value ->> 'size_bytes', '') !~ '^[0-9]+$'
     or jsonb_typeof(output_payload_value -> 'duration_ms') <> 'number'
     or coalesce(output_payload_value ->> 'duration_ms', '') !~ '^[0-9]+$'
     or output_payload_value -> 'http_status' is distinct from '200'::jsonb
     or output_payload_value -> 'download_complete' is distinct from
          'true'::jsonb
     or output_payload_value ->> 'parser_version' <> 'iso-bmff-mvhd-v1'
     or output_payload_value -> 'mvhd_count' is distinct from '1'::jsonb
     or output_payload_value -> 'fragmented' is distinct from 'false'::jsonb
     or output_payload_value ->> 'verification_method' <>
          'creator-generate-local-mock-full-object-v1'
  then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_output_invalid';
  end if;
  output_bucket_value := btrim(output_payload_value ->> 'bucket_id');
  output_mime_value := lower(btrim(output_payload_value ->> 'mime_type'));
  output_sha256_value := lower(btrim(output_payload_value ->> 'sha256'));
  begin
    output_size_value := (output_payload_value ->> 'size_bytes')::bigint;
    output_duration_ms_value :=
      (output_payload_value ->> 'duration_ms')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_output_invalid';
  end;
  if output_bucket_value <> 'contentengine-private'
     or output_payload_value ->> 'object_name' <>
          output_object_name_value
     or output_mime_value <> 'video/mp4'
     or output_size_value not between 1 and 52428800
     or output_sha256_value !~ '^[0-9a-f]{64}$'
     or output_sha256_value = source_sha256_value
     or output_duration_ms_value not between 1800 and 15000
     or exists (
       select 1
       from content_factory.generation_spec_strategy_assets asset
       where asset.organization_id = organization_id_value
         and asset.binding_id = binding_id_value
         and asset.media_sha256_snapshot = output_sha256_value
     ) then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_output_invalid';
  end if;

  request_payload_value := p_payload - 'idempotency_key';
  replay_value := content_factory_private.begin_command(
    organization_id_value,
    'system_local_mock_generation_strategy_complete',
    idempotency_key_value,
    request_payload_value
  );
  if replay_value is not null then
    return jsonb_set(replay_value, '{replay}', 'true'::jsonb, false);
  end if;

  -- This is the same object-scoped lock used by media registration and the
  -- unregistered-upload delete policy.  The Edge caller has already verified
  -- the full bytes; SQL independently pins the authoritative Storage size and
  -- MIME metadata before registering the generated output.
  perform pg_advisory_xact_lock(
    hashtext(output_bucket_value), hashtext(output_object_name_value)
  );
  select storage_object.metadata into storage_metadata_value
  from storage.objects storage_object
  where storage_object.bucket_id = output_bucket_value
    and storage_object.name = output_object_name_value
  for update;
  if storage_metadata_value is null then
    raise exception using errcode = 'P0002',
      message = 'local_mock_generation_strategy_output_not_found';
  end if;
  if jsonb_typeof(storage_metadata_value) <> 'object'
     or coalesce(storage_metadata_value ->> 'size', '') !~ '^[0-9]+$'
     or nullif(btrim(coalesce(
       storage_metadata_value ->> 'mimetype', ''
     )), '') is null then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_storage_metadata_invalid';
  end if;
  begin
    storage_size_value := (storage_metadata_value ->> 'size')::bigint;
  exception when numeric_value_out_of_range then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_storage_metadata_invalid';
  end;
  storage_mime_value := lower(btrim(storage_metadata_value ->> 'mimetype'));
  if storage_size_value <> output_size_value
     or storage_mime_value <> output_mime_value then
    raise exception using errcode = '22023',
      message = 'local_mock_generation_strategy_storage_metadata_mismatch';
  end if;
  if exists (
    select 1
    from content_factory.media_objects media
    where (media.bucket_id = output_bucket_value
      and media.object_name = output_object_name_value)
      or (media.organization_id = organization_id_value
        and media.idempotency_key =
          'local-mock-copy-output:' || execution_hash_value)
  ) then
    raise exception using errcode = '23505',
      message = 'local_mock_generation_strategy_output_conflict';
  end if;

  batch_id_value := extensions.gen_random_uuid();
  job_id_value := extensions.gen_random_uuid();
  output_media_id_value := extensions.gen_random_uuid();
  batch_input_value := jsonb_build_object(
    'version', 'local-mock-generation-strategy-batch-input-v1',
    'model', 'local_product_swap_v1',
    'strategy_id', 'viral_product_swap',
    'spec_strategy_binding_id', binding_id_value,
    'binding_hash', binding_row.binding_hash,
    'selection_hash', selection_hash_value,
    'media_ids', to_jsonb(input_media_ids_value),
    'source_video_media_id', source_media_id_value,
    'original_product_media_id', original_product_media_id_value,
    'new_product_media_ids', to_jsonb(new_product_media_ids_value),
    'output_media_id', output_media_id_value,
    'provider_call_started', false,
    'allow_real_spend', false
  );
  job_input_value := jsonb_build_object(
    'version', 'local-mock-generation-strategy-job-input-v1',
    'model', 'local_product_swap_v1',
    'strategy_id', 'viral_product_swap',
    'spec_strategy_binding_id', binding_id_value,
    'binding_hash', binding_row.binding_hash,
    'selection_hash', selection_hash_value,
    'source_video_media_id', source_media_id_value,
    'source_video_sha256', source_sha256_value,
    'source_video_duration_ms', source_duration_ms_value,
    'original_product_media_id', original_product_media_id_value,
    'new_product_media_ids', to_jsonb(new_product_media_ids_value),
    'media_ids', to_jsonb(input_media_ids_value),
    'output_object_name', output_object_name_value,
    'provider_call_started', false,
    'allow_real_spend', false
  );
  job_output_value := jsonb_build_object(
    'version', 'local-mock-generation-strategy-job-output-v1',
    'output_media_id', output_media_id_value,
    'output_object_name', output_object_name_value,
    'output_sha256', output_sha256_value,
    'output_size_bytes', output_size_value,
    'duration_ms', output_duration_ms_value,
    'provider_call_started', false,
    'provider_called', false,
    'archive_ready', true
  );

  insert into content_factory.generation_batches (
    id, organization_id, product_id, created_by, name, mode,
    allow_real_spend, status, total_requested, total_created, input,
    request_hash, idempotency_key, provider, model, duration_seconds,
    audio, estimated_cost_minor, estimated_credits, currency, project_id
  ) values (
    batch_id_value, organization_id_value, binding_row.product_id,
    actor_id_value, 'Local mock Copy ' || substr(execution_hash_value, 1, 16),
    'mock', false, 'mock_ready', 1, 1, batch_input_value,
    content_factory_private.json_hash(batch_input_value),
    'local-mock-copy-batch:' || execution_hash_value,
    'mock', 'mock', 0, false, 0, 0, 'USD', project_id_value
  );

  insert into content_factory.media_objects (
    id, organization_id, owner_id, product_id, project_id,
    bucket_id, object_name, mime_type, size_bytes, sha256,
    status, metadata, idempotency_key
  ) values (
    output_media_id_value, organization_id_value, actor_id_value,
    binding_row.product_id, project_id_value, output_bucket_value,
    output_object_name_value, output_mime_value, output_size_value,
    output_sha256_value, 'ready',
    jsonb_build_object(
      'original_filename', 'local-mock-copy-' ||
        substr(execution_hash_value, 1, 16) || '.mp4',
      'kind', 'generated_video',
      'provider', 'mock',
      'model', 'local_product_swap_v1',
      'generation_job_id', job_id_value,
      'generation_batch_id', batch_id_value,
      'strategy_id', 'viral_product_swap',
      'spec_strategy_binding_id', binding_id_value,
      'source_media_id', source_media_id_value,
      'rights_confirmed', true,
      'local_mock', true,
      'verification_method',
        'creator-generate-local-mock-full-object-v1',
      'provider_call_started', false
    ),
    'local-mock-copy-output:' || execution_hash_value
  );

  insert into content_factory.generation_jobs (
    id, organization_id, product_id, batch_id, ordinal, requested_by,
    assigned_to, mode, provider, allow_real_spend, estimated_cost_minor,
    actual_cost_minor, status, input, output, request_hash, idempotency_key,
    project_id, generation_spec_id, generation_spec_version,
    generation_spec_hash, generation_video_reference_decided
  ) values (
    job_id_value, organization_id_value, binding_row.product_id,
    batch_id_value, 1, actor_id_value, actor_id_value, 'mock', 'mock',
    false, 0, 0, 'mock_ready', job_input_value, job_output_value,
    content_factory_private.json_hash(job_input_value),
    'local-mock-copy-job:' || execution_hash_value, project_id_value,
    spec_id_value, spec_version_value, spec_hash_value, false
  );

  if not exists (
    select 1
    from content_factory.generation_job_strategy_snapshots snapshot
    where snapshot.organization_id = organization_id_value
      and snapshot.generation_job_id = job_id_value
      and snapshot.spec_strategy_binding_id = binding_id_value
      and snapshot.strategy_id = 'viral_product_swap'
  ) or not exists (
    select 1
    from content_factory.generation_strategy_status_events event
    where event.organization_id = organization_id_value
      and event.generation_job_id = job_id_value
      and event.transition_ordinal = 1
      and event.job_status = 'mock_ready'
  ) then
    raise exception using errcode = '55000',
      message = 'local_mock_generation_strategy_snapshot_missing';
  end if;

  output_value := jsonb_build_object(
    'bucket_id', output_bucket_value,
    'object_name', output_object_name_value,
    'mime_type', output_mime_value,
    'media_id', output_media_id_value,
    'size_bytes', output_size_value,
    'sha256', output_sha256_value,
    'duration_ms', output_duration_ms_value
  );
  generation_value := jsonb_build_object(
    'batch_id', batch_id_value,
    'generation_job_id', job_id_value,
    'status', 'mock_ready',
    'provider', 'mock',
    'persisted_model', 'mock',
    'logical_model', 'local_product_swap_v1'
  );
  result_value := jsonb_build_object(
    'ok', true,
    'version', 'local-mock-generation-strategy-response-v1',
    'operation', 'complete',
    'replay', false,
    'identity', identity_value,
    'inputs', inputs_value,
    'output', output_value,
    'generation', generation_value,
    'contract', contract_value
  );
  return content_factory_private.finish_command(
    organization_id_value,
    actor_id_value,
    'system_local_mock_generation_strategy_complete',
    idempotency_key_value,
    request_payload_value,
    result_value
  );
end;
$$;

revoke all on function public.system_local_mock_generation_strategy(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.system_local_mock_generation_strategy(jsonb)
  to service_role;

comment on function public.system_local_mock_generation_strategy(jsonb) is
  'Service-only local Product Swap preflight/complete/status authority. It can create only zero-cost mock rows, never claims paid spend, never dispatches a provider, and reuses the canonical generation/media records without a second ledger.';

notify pgrst, 'reload schema';

commit;
