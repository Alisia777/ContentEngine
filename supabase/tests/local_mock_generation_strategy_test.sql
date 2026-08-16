begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select no_plan();

select has_function(
  'public', 'system_local_mock_generation_strategy', array['jsonb'],
  'one local mock strategy RPC is installed'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_local_mock_generation_strategy(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'public.system_local_mock_generation_strategy(jsonb)', 'execute'
  )
  and not has_function_privilege(
    'anon',
    'public.system_local_mock_generation_strategy(jsonb)', 'execute'
  ),
  'local mock strategy RPC is service-role only'
);
select ok(
  position(
    'system_claim_generation_strategy_start' in pg_get_functiondef(
      'public.system_local_mock_generation_strategy(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    'generation_strategy_dispatch_attempts' in pg_get_functiondef(
      'public.system_local_mock_generation_strategy(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    'generation_strategy_dispatch_results' in pg_get_functiondef(
      'public.system_local_mock_generation_strategy(jsonb)'::regprocedure
    )
  ) = 0
  and position(
    'generation_spend_ledger' in pg_get_functiondef(
      'public.system_local_mock_generation_strategy(jsonb)'::regprocedure
    )
  ) = 0,
  'local mock RPC contains no paid claim, dispatch or spend-ledger writer'
);
select ok(
  position(
    'new_product_count_value not between 1 and 10' in pg_get_functiondef(
      'public.system_local_mock_generation_strategy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    'duration.duration_seconds between 1.8 and 15' in pg_get_functiondef(
      'public.system_local_mock_generation_strategy(jsonb)'::regprocedure
    )
  ) > 0
  and position(
    '''creator-generate-local-mock-full-object-v1''' in pg_get_functiondef(
      'public.system_local_mock_generation_strategy(jsonb)'::regprocedure
    )
  ) > 0,
  'Copy cardinality, source probe and full-object verification fail closed'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'cb100000-0000-4000-8000-000000000001'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated',
  'local-mock-copy-owner@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Local Mock Copy Owner"}'::jsonb,
  now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'cb110000-0000-4000-8000-000000000001'::uuid,
  'Local Mock Copy pgTAP', 'local-mock-copy-pgtap', 'active'
);

update content_factory.profiles profile
set status = 'active'
where profile.id = 'cb100000-0000-4000-8000-000000000001'::uuid;

insert into content_factory.memberships (
  organization_id, profile_id, role, status
) values (
  'cb110000-0000-4000-8000-000000000001'::uuid,
  'cb100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'active'
);

insert into content_factory.training_access_waivers (
  organization_id, profile_id, previous_role, granted_role,
  grant_reason, granted_by
) values (
  'cb110000-0000-4000-8000-000000000001'::uuid,
  'cb100000-0000-4000-8000-000000000001'::uuid,
  'owner', 'owner',
  'TEST-ONLY waiver for local mock Product Swap.',
  'cb100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.workspace_folders (
  id, organization_id, parent_id, name, color_token, kind,
  status, position, created_by, updated_by
) values (
  'cb120000-0000-4000-8000-000000000001'::uuid,
  'cb110000-0000-4000-8000-000000000001'::uuid,
  null, 'Local mock Copy project', 'gold', 'project',
  'active', 1024,
  'cb100000-0000-4000-8000-000000000001'::uuid,
  'cb100000-0000-4000-8000-000000000001'::uuid
);

insert into content_factory.products (
  id, organization_id, sku, title, status, created_by
) values (
  'cb130000-0000-4000-8000-000000000001'::uuid,
  'cb110000-0000-4000-8000-000000000001'::uuid,
  'LOCAL-MOCK-COPY-001', 'Local Mock Copy Product', 'active',
  'cb100000-0000-4000-8000-000000000001'::uuid
);

select set_config(
  'request.jwt.claim.sub',
  'cb100000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

create temporary table local_mock_copy_context (
  source_media_id uuid,
  original_product_media_id uuid,
  new_product_media_id_1 uuid,
  new_product_media_id_2 uuid,
  new_product_media_id_3 uuid,
  source_attachment_id uuid,
  source_attachment_hash text,
  selection jsonb,
  spec_id uuid,
  spec_version integer,
  spec_hash text,
  selection_hash text,
  binding_id uuid,
  preflight jsonb,
  complete_result jsonb,
  replay_result jsonb,
  status_result jsonb
) on commit drop;
insert into local_mock_copy_context default values;

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  'cb110000-0000-4000-8000-000000000001/' ||
    'cb100000-0000-4000-8000-000000000001/uploads/' || fixture.filename,
  jsonb_build_object('size', fixture.size_bytes, 'mimetype', fixture.mime_type)
from (values
  ('copy-source.mp4', 4096, 'video/mp4'),
  ('copy-original.webp', 1024, 'image/webp'),
  ('copy-new-front.png', 1024, 'image/png'),
  ('copy-new-side.png', 1024, 'image/png'),
  ('copy-new-back.png', 1024, 'image/png')
) fixture(filename, size_bytes, mime_type);

do $register_local_mock_copy_inputs$
declare
  response_value jsonb;
begin
  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'cb110000-0000-4000-8000-000000000001/' ||
      'cb100000-0000-4000-8000-000000000001/uploads/copy-source.mp4',
    'original_filename', 'copy-source.mp4', 'mime_type', 'video/mp4',
    'size_bytes', 4096, 'sha256', repeat('a', 64),
    'kind', 'source_video', 'rights_confirmed', true,
    'idempotency_key', 'local-mock-copy-source-register-0001'
  ));
  update local_mock_copy_context
  set source_media_id = (response_value #>> '{media,id}')::uuid;

  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'cb110000-0000-4000-8000-000000000001/' ||
      'cb100000-0000-4000-8000-000000000001/uploads/copy-original.webp',
    'original_filename', 'copy-original.webp', 'mime_type', 'image/webp',
    'size_bytes', 1024, 'sha256', repeat('b', 64),
    'kind', 'creator_reference', 'rights_confirmed', true,
    'idempotency_key', 'local-mock-copy-original-register-0001'
  ));
  update local_mock_copy_context
  set original_product_media_id = (response_value #>> '{media,id}')::uuid;

  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'product_id', 'cb130000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'cb110000-0000-4000-8000-000000000001/' ||
      'cb100000-0000-4000-8000-000000000001/uploads/copy-new-front.png',
    'original_filename', 'copy-new-front.png', 'mime_type', 'image/png',
    'size_bytes', 1024, 'sha256', repeat('c', 64),
    'kind', 'product_photo', 'rights_confirmed', true,
    'idempotency_key', 'local-mock-copy-new-front-register-0001'
  ));
  update local_mock_copy_context
  set new_product_media_id_1 = (response_value #>> '{media,id}')::uuid;

  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'product_id', 'cb130000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'cb110000-0000-4000-8000-000000000001/' ||
      'cb100000-0000-4000-8000-000000000001/uploads/copy-new-side.png',
    'original_filename', 'copy-new-side.png', 'mime_type', 'image/png',
    'size_bytes', 1024, 'sha256', repeat('d', 64),
    'kind', 'product_photo', 'rights_confirmed', true,
    'idempotency_key', 'local-mock-copy-new-side-register-0001'
  ));
  update local_mock_copy_context
  set new_product_media_id_2 = (response_value #>> '{media,id}')::uuid;

  response_value := public.creator_register_media(jsonb_build_object(
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'product_id', 'cb130000-0000-4000-8000-000000000001',
    'bucket', 'contentengine-private',
    'object_key', 'cb110000-0000-4000-8000-000000000001/' ||
      'cb100000-0000-4000-8000-000000000001/uploads/copy-new-back.png',
    'original_filename', 'copy-new-back.png', 'mime_type', 'image/png',
    'size_bytes', 1024, 'sha256', repeat('e', 64),
    'kind', 'product_photo', 'rights_confirmed', true,
    'idempotency_key', 'local-mock-copy-new-back-register-0001'
  ));
  update local_mock_copy_context
  set new_product_media_id_3 = (response_value #>> '{media,id}')::uuid;
end;
$register_local_mock_copy_inputs$;

do $attach_and_probe_local_mock_copy_source$
declare
  response_value jsonb;
begin
  response_value := public.contentengine_attach_generation_direct_mp4(
    jsonb_build_object(
      'organization_id', 'cb110000-0000-4000-8000-000000000001',
      'project_id', 'cb120000-0000-4000-8000-000000000001',
      'media_id', (select source_media_id from local_mock_copy_context),
      'idempotency_key', 'local-mock-copy-source-attachment-0001'
    )
  );
  update local_mock_copy_context set
    source_attachment_id = (response_value #>> '{attachment,id}')::uuid,
    source_attachment_hash = response_value #>> '{attachment,attachment_hash}';

  perform public.system_record_generation_strategy_media_duration(
    jsonb_build_object(
      'version', 'generation-strategy-media-duration-record-request-v1',
      'organization_id', 'cb110000-0000-4000-8000-000000000001',
      'project_id', 'cb120000-0000-4000-8000-000000000001',
      'actor_id', 'cb100000-0000-4000-8000-000000000001',
      'media_id', (select source_media_id from local_mock_copy_context),
      'attachment_id',
        (select source_attachment_id from local_mock_copy_context),
      'attachment_hash',
        (select source_attachment_hash from local_mock_copy_context),
      'media_sha256', repeat('a', 64), 'size_bytes', 4096,
      'http_status', 200, 'content_type', 'video/mp4',
      'download_complete', true, 'parser_version', 'iso-bmff-mvhd-v1',
      'timescale', 1000, 'duration_units', 8000, 'duration_ms', 8000,
      'mvhd_count', 1, 'fragmented', false,
      'verification_method', 'server_mp4_probe',
      'evidence_hash', repeat('9', 64),
      'idempotency_key', 'local-mock-copy-source-probe-0001'
    )
  );
end;
$attach_and_probe_local_mock_copy_source$;

do $prepare_approve_bind_local_mock_copy$
declare
  selection_value jsonb;
  asset_snapshot_value jsonb;
  source_snapshot_value jsonb;
  exact_scope_value jsonb;
  response_value jsonb;
  spec_id_value uuid;
  spec_version_value integer;
  spec_hash_value text;
  source_media_row content_factory.media_objects%rowtype;
  source_attachment_row
    content_factory.research_exact_youtube_media_attachments%rowtype;
  source_duration_value numeric;
begin
  select jsonb_build_object(
    'version', '2026-08-14.v1',
    'strategy_id', 'viral_product_swap',
    'recipe_version', '2026-06',
    'duration_seconds', 4,
    'resolution', '720p',
    'audio', true,
    'assets', jsonb_build_array(
      jsonb_build_object(
        'role', 'source_video',
        'media_id', source_media_id,
        'duration_seconds', 8.000
      ),
      jsonb_build_object(
        'role', 'original_product_image',
        'media_id', original_product_media_id
      ),
      jsonb_build_object(
        'role', 'new_product_image',
        'media_id', new_product_media_id_1,
        'view', 'front'
      ),
      jsonb_build_object(
        'role', 'new_product_image',
        'media_id', new_product_media_id_2,
        'view', 'side'
      ),
      jsonb_build_object(
        'role', 'new_product_image',
        'media_id', new_product_media_id_3,
        'view', 'back'
      )
    ),
    'attestations', jsonb_build_object(
      'source_media_rights_confirmed', true,
      'transformative_use_confirmed', true,
      'product_assets_rights_confirmed', true,
      'depicted_people_consent_confirmed', true
    )
  ) into selection_value
  from local_mock_copy_context;
  update local_mock_copy_context set selection = selection_value;

  select media.* into source_media_row
  from content_factory.media_objects media
  where media.id = (
    select source_media_id from local_mock_copy_context
  );
  select attachment.* into source_attachment_row
  from content_factory.research_exact_youtube_media_attachments attachment
  where attachment.id = (
    select source_attachment_id from local_mock_copy_context
  );
  select duration.duration_seconds into source_duration_value
  from content_factory.generation_strategy_media_durations duration
  where duration.organization_id =
      'cb110000-0000-4000-8000-000000000001'::uuid
    and duration.media_object_id = source_media_row.id;
  select jsonb_agg(
    jsonb_build_object(
      'selection_role', item.value ->> 'role',
      'selection_ordinal', item.ordinality::integer,
      'media_id', media.id,
      'sha256', media.sha256,
      'kind', media.metadata ->> 'kind',
      'mime_type', media.mime_type,
      'product_id', to_jsonb(media.product_id),
      'rights_confirmed', true
    ) order by item.ordinality
  ) into asset_snapshot_value
  from jsonb_array_elements(selection_value -> 'assets') with ordinality
    item(value, ordinality)
  join content_factory.media_objects media
    on media.organization_id =
         'cb110000-0000-4000-8000-000000000001'::uuid
   and media.id = (item.value ->> 'media_id')::uuid;
  source_snapshot_value := jsonb_build_object(
    'version', 'generation-strategy-exact-source-snapshot-v1',
    'attachment_id', source_attachment_row.id,
    'attachment_hash', source_attachment_row.attachment_hash,
    'source_id', source_attachment_row.source_id,
    'source_hash', source_attachment_row.source_hash_snapshot,
    'media_object_id', source_media_row.id,
    'media_sha256', source_media_row.sha256,
    'size_bytes', source_media_row.size_bytes,
    'duration_seconds', to_jsonb(source_duration_value)
  );
  exact_scope_value := jsonb_build_object(
    'version', 'generation-strategy-spec-scope-v1',
    'authority_kind', 'strategy_recipe',
    'primary_media_id',
      (select new_product_media_id_1 from local_mock_copy_context),
    'media_ids', (
      select jsonb_build_array(
        new_product_media_id_1,
        new_product_media_id_2,
        new_product_media_id_3
      ) from local_mock_copy_context
    ),
    'platform', 'tiktok',
    'provider', 'runway',
    'strategy_id', 'viral_product_swap',
    'recipe', 'product_swap',
    'input_mode', 'video_and_product_images',
    'duration_seconds', 4,
    'product_category', 'other',
    'format', 'source',
    'ratio', 'source',
    'resolution', '720p',
    'audio', true,
    'spoken_dialogue', false,
    'reference_count', 4,
    'reference_video', true,
    'first_frame', false,
    'last_frame', false,
    'selection', selection_value,
    'selection_hash', content_factory_private.json_hash(selection_value),
    'asset_snapshot', asset_snapshot_value,
    'asset_snapshot_hash',
      content_factory_private.json_hash(asset_snapshot_value),
    'source', source_snapshot_value,
    'source_hash', content_factory_private.json_hash(source_snapshot_value),
    'mechanics', 'null'::jsonb,
    'mechanics_hash', 'null'::jsonb
  );
  if content_factory_private.generation_strategy_spec_scope_v1(
       exact_scope_value
     ) is distinct from exact_scope_value then
    raise exception 'local mock test exact scope invalid';
  end if;

  response_value := public.creator_prepare_generation_spec(
    jsonb_build_object(
      'organization_id', 'cb110000-0000-4000-8000-000000000001',
      'project_id', 'cb120000-0000-4000-8000-000000000001',
      'idempotency_key', 'strategy-spec:local-mock-copy-spec-prepare-0001',
      'exact_scope', exact_scope_value,
      'editable_intent',
        'Replace only the original product while preserving motion and light.',
      'proposed_prompt',
        'Replace the original product with the supplied product references.',
      'learning_context', jsonb_build_object(
        'creative_angle', 'product_focus',
        'hook_patterns', '[]'::jsonb,
        'source', 'baseline',
        'compiler_version', 'safe-brief-v7',
        'product_category', 'other'
      ),
      'repair_context', 'null'::jsonb,
      'research_provenance', 'null'::jsonb,
      'performance_policy_provenance', 'null'::jsonb,
      'repair_provenance', 'null'::jsonb,
      'confirmation', true,
      'reason', 'Prepare the local mock Product Swap integration fixture.'
    )
  );
  spec_id_value := (response_value #>> '{generation_spec,spec_id}')::uuid;
  spec_version_value :=
    (response_value #>> '{generation_spec,spec_version}')::integer;
  spec_hash_value := response_value #>> '{generation_spec,spec_hash}';
  update local_mock_copy_context set
    spec_id = spec_id_value,
    spec_version = spec_version_value,
    spec_hash = spec_hash_value,
    selection_hash = content_factory_private.json_hash(selection_value);

  perform public.creator_control_generation_spec(jsonb_build_object(
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'spec_id', spec_id_value,
    'expected_spec_version', spec_version_value,
    'expected_spec_hash', spec_hash_value,
    'action', 'approve',
    'confirmation', true,
    'reason', 'Approve the exact local mock Copy test fixture.',
    'idempotency_key', 'local-mock-copy-spec-approve-0001'
  ));

  response_value := public.system_resolve_and_bind_generation_strategy(
    jsonb_build_object(
      'version', 'generation-strategy-resolve-bind-request-v1',
      'organization_id', 'cb110000-0000-4000-8000-000000000001',
      'project_id', 'cb120000-0000-4000-8000-000000000001',
      'actor_id', 'cb100000-0000-4000-8000-000000000001',
      'spec_id', spec_id_value,
      'spec_version', spec_version_value,
      'spec_hash', spec_hash_value,
      'selection', selection_value,
      'confirmation', true,
      'idempotency_key', 'local-mock-copy-strategy-bind-0001'
    )
  );
  update local_mock_copy_context
  set binding_id = (response_value #>> '{binding,id}')::uuid;
end;
$prepare_approve_bind_local_mock_copy$;

do $preflight_local_mock_copy$
declare
  response_value jsonb;
begin
  select public.system_local_mock_generation_strategy(jsonb_build_object(
    'version', 'local-mock-generation-strategy-request-v1',
    'operation', 'preflight',
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'actor_id', 'cb100000-0000-4000-8000-000000000001',
    'spec_strategy_binding_id', binding_id,
    'spec_id', spec_id,
    'spec_version', spec_version,
    'spec_hash', spec_hash,
    'selection_hash', selection_hash,
    'mode', 'mock',
    'allow_real_spend', false,
    'provider_call_started', false,
    'confirmation', 'LOCAL_MOCK_ONLY',
    'idempotency_key', 'local-mock-copy-complete-0001'
  )) into response_value
  from local_mock_copy_context;
  update local_mock_copy_context set preflight = response_value;
end;
$preflight_local_mock_copy$;

select is(
  (
    select jsonb_agg(key order by key)
    from local_mock_copy_context context,
      jsonb_object_keys(context.preflight) key
  ),
  '["contract","generation","identity","inputs","ok","operation","output","replay","version"]'::jsonb,
  'preflight returns the exact shared top-level response keyset'
);
select is(
  (select preflight -> 'generation' from local_mock_copy_context),
  'null'::jsonb,
  'preflight creates no generation aggregate'
);
select is(
  (select preflight #>> '{contract,model}' from local_mock_copy_context),
  'local_product_swap_v1',
  'preflight exposes the exact logical local model'
);
select is(
  (select jsonb_array_length(
    preflight #> '{inputs,new_product_media_ids}'
  ) from local_mock_copy_context),
  3,
  'preflight pins exactly three new-product references'
);
select ok(
  (select preflight #>> '{output,object_name}'
   from local_mock_copy_context) like
    'cb110000-0000-4000-8000-000000000001/' ||
      'cb100000-0000-4000-8000-000000000001/local-mock-output/' ||
      'viral_product_swap/%',
  'preflight derives an actor-scoped private output path'
);

insert into storage.objects (bucket_id, name, metadata)
select
  'contentengine-private',
  preflight #>> '{output,object_name}',
  jsonb_build_object('size', 8192, 'mimetype', 'video/mp4')
from local_mock_copy_context;

select throws_ok(
  $$
    select public.system_local_mock_generation_strategy(jsonb_build_object(
      'version', 'local-mock-generation-strategy-request-v1',
      'operation', 'complete',
      'organization_id', 'cb110000-0000-4000-8000-000000000001',
      'project_id', 'cb120000-0000-4000-8000-000000000001',
      'actor_id', 'cb100000-0000-4000-8000-000000000001',
      'spec_strategy_binding_id', binding_id,
      'spec_id', spec_id,
      'spec_version', spec_version,
      'spec_hash', spec_hash,
      'selection_hash', selection_hash,
      'mode', 'mock', 'allow_real_spend', false,
      'provider_call_started', false,
      'confirmation', 'LOCAL_MOCK_ONLY',
      'idempotency_key', 'local-mock-copy-complete-0001',
      'output', jsonb_build_object(
        'bucket_id', 'contentengine-private',
        'object_name', preflight #>> '{output,object_name}',
        'mime_type', 'video/mp4', 'size_bytes', 8193,
        'sha256', repeat('f', 64), 'duration_ms', 8000,
        'http_status', 200, 'download_complete', true,
        'parser_version', 'iso-bmff-mvhd-v1', 'mvhd_count', 1,
        'fragmented', false,
        'verification_method',
          'creator-generate-local-mock-full-object-v1'
      )
    ))
    from local_mock_copy_context
  $$,
  '22023', 'local_mock_generation_strategy_storage_metadata_mismatch',
  'Storage size mismatch fails before any aggregate is committed'
);
select is(
  (
    select count(*)::integer
    from content_factory.generation_batches batch
    where batch.organization_id =
      'cb110000-0000-4000-8000-000000000001'::uuid
  ),
  0,
  'failed completion leaves no partial batch'
);

do $complete_replay_status_local_mock_copy$
declare
  request_value jsonb;
  response_value jsonb;
begin
  select jsonb_build_object(
    'version', 'local-mock-generation-strategy-request-v1',
    'operation', 'complete',
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'actor_id', 'cb100000-0000-4000-8000-000000000001',
    'spec_strategy_binding_id', binding_id,
    'spec_id', spec_id,
    'spec_version', spec_version,
    'spec_hash', spec_hash,
    'selection_hash', selection_hash,
    'mode', 'mock', 'allow_real_spend', false,
    'provider_call_started', false,
    'confirmation', 'LOCAL_MOCK_ONLY',
    'idempotency_key', 'local-mock-copy-complete-0001',
    'output', jsonb_build_object(
      'bucket_id', 'contentengine-private',
      'object_name', preflight #>> '{output,object_name}',
      'mime_type', 'video/mp4', 'size_bytes', 8192,
      'sha256', repeat('f', 64), 'duration_ms', 8000,
      'http_status', 200, 'download_complete', true,
      'parser_version', 'iso-bmff-mvhd-v1', 'mvhd_count', 1,
      'fragmented', false,
      'verification_method', 'creator-generate-local-mock-full-object-v1'
    )
  ) into request_value
  from local_mock_copy_context;

  response_value := public.system_local_mock_generation_strategy(
    request_value
  );
  update local_mock_copy_context set complete_result = response_value;
  response_value := public.system_local_mock_generation_strategy(
    request_value
  );
  update local_mock_copy_context set replay_result = response_value;

  select public.system_local_mock_generation_strategy(jsonb_build_object(
    'version', 'local-mock-generation-strategy-request-v1',
    'operation', 'status',
    'organization_id', 'cb110000-0000-4000-8000-000000000001',
    'project_id', 'cb120000-0000-4000-8000-000000000001',
    'actor_id', 'cb100000-0000-4000-8000-000000000001',
    'generation_job_id',
      response_value #>> '{generation,generation_job_id}',
    'mode', 'mock',
    'allow_real_spend', false,
    'provider_call_started', false
  )) into response_value;
  update local_mock_copy_context set status_result = response_value;
end;
$complete_replay_status_local_mock_copy$;

select is(
  (
    select jsonb_agg(key order by key)
    from local_mock_copy_context context,
      jsonb_object_keys(context.complete_result) key
  ),
  '["contract","generation","identity","inputs","ok","operation","output","replay","version"]'::jsonb,
  'complete returns the exact shared top-level response keyset'
);
select is(
  (
    select jsonb_agg(key order by key)
    from local_mock_copy_context context,
      jsonb_object_keys(context.status_result) key
  ),
  '["contract","generation","identity","inputs","ok","operation","output","replay","version"]'::jsonb,
  'status returns the exact shared top-level response keyset'
);
select ok(
  (select replay_result -> 'replay' from local_mock_copy_context) =
    'true'::jsonb
  and (select complete_result #>> '{generation,batch_id}'
       from local_mock_copy_context) =
      (select replay_result #>> '{generation,batch_id}'
       from local_mock_copy_context)
  and (select complete_result #>> '{generation,generation_job_id}'
       from local_mock_copy_context) =
      (select replay_result #>> '{generation,generation_job_id}'
       from local_mock_copy_context),
  'complete replay returns the same batch and job IDs'
);
select is(
  (select status_result #>> '{generation,status}'
   from local_mock_copy_context),
  'mock_ready',
  'status reads the completed mock job through its immutable snapshot'
);
select ok(
  exists (
    select 1
    from content_factory.generation_batches batch
    join content_factory.generation_jobs job
      on job.organization_id = batch.organization_id
     and job.batch_id = batch.id
    where batch.id = (
      select (complete_result #>> '{generation,batch_id}')::uuid
      from local_mock_copy_context
    )
      and batch.mode = 'mock' and batch.provider = 'mock'
      and batch.model = 'mock' and not batch.allow_real_spend
      and batch.estimated_cost_minor = 0 and batch.estimated_credits = 0
      and batch.status = 'mock_ready'
      and job.mode = 'mock' and job.provider = 'mock'
      and not job.allow_real_spend
      and job.estimated_cost_minor = 0 and job.actual_cost_minor = 0
      and job.status = 'mock_ready'
      and job.input ->> 'model' = 'local_product_swap_v1'
      and job.generation_spec_id is not null
  ),
  'completion stores only the canonical zero-cost mock batch/job contract'
);
select ok(
  exists (
    select 1
    from content_factory.media_objects media
    where media.id = (
      select (complete_result #>> '{output,media_id}')::uuid
      from local_mock_copy_context
    )
      and media.status = 'ready'
      and media.artifact_class = 'generated_output'
      and media.lifecycle_stage = 'drafts'
      and media.metadata ->> 'kind' = 'generated_video'
      and media.metadata ->> 'provider' = 'mock'
      and media.metadata -> 'provider_call_started' = 'false'::jsonb
  ),
  'verified Storage object becomes one generated-video media row'
);
select is(
  (
    select count(*)::integer
    from content_factory.generation_job_strategy_snapshots snapshot
    where snapshot.generation_job_id = (
      select (complete_result #>> '{generation,generation_job_id}')::uuid
      from local_mock_copy_context
    )
      and snapshot.strategy_id = 'viral_product_swap'
  ),
  1,
  'existing trigger creates one immutable Product Swap job snapshot'
);
select is(
  (
    select count(*)::integer
    from content_factory.generation_strategy_status_events event
    where event.generation_job_id = (
      select (complete_result #>> '{generation,generation_job_id}')::uuid
      from local_mock_copy_context
    )
      and event.transition_ordinal = 1
      and event.job_status = 'mock_ready'
  ),
  1,
  'existing trigger records the initial mock_ready strategy status'
);
select is(
  (
    select count(*)::integer
    from content_factory.command_receipts receipt
    where receipt.organization_id =
      'cb110000-0000-4000-8000-000000000001'::uuid
      and receipt.command_name =
        'system_local_mock_generation_strategy_complete'
  ),
  1,
  'idempotency reuses the existing command receipt instead of a new ledger'
);
select is(
  (
    select
      (select count(*)
       from content_factory.generation_strategy_start_claims claim
       where claim.organization_id =
         'cb110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_strategy_dispatch_attempts attempt
       where attempt.organization_id =
         'cb110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_strategy_dispatch_results result
       where result.organization_id =
         'cb110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_strategy_readiness_receipts receipt
       where receipt.organization_id =
         'cb110000-0000-4000-8000-000000000001'::uuid)
      +
      (select count(*)
       from content_factory.generation_spend_ledger ledger
       where ledger.organization_id =
         'cb110000-0000-4000-8000-000000000001'::uuid)
  )::integer,
  0,
  'mock completion creates no readiness, paid claim, dispatch or spend row'
);
select is(
  (select status_result #>> '{contract,provider_call_started}'
   from local_mock_copy_context),
  'false',
  'status proves that no provider call started'
);

select * from finish();
rollback;
